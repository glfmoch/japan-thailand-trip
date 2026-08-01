"""Build the deploy-safe dataset from raw trip data.

Runs the offline pipeline over the raw sources in data/raw/ and writes the
committed artifacts the Streamlit app reads into data/processed/:

    spending.csv   parsed, categorized, USD-converted spending log
    route.json     per-country movement routes + visit markers
    photos.json    geotagged photos with thumbnails + vision matches
    meta.json      summary counts and totals

Usage:
    python build_dataset.py                # all stages; vision runs if API key set
    python build_dataset.py --no-vision    # skip the Anthropic vision matching
    python build_dataset.py --vision-only  # re-run vision over existing photos.json

Raw sources live in data/raw/ (gitignored). The outputs above are committed so
the public app has data to show without shipping the raw photos or location log.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

import pandas as pd

from pipeline import config, photos as photos_mod, spending as spending_mod, timeline


def _photos_dir():
    candidates = [p for p in config.RAW_DIR.rglob("Photos") if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No Photos/ folder under {config.RAW_DIR}")
    return candidates[0]


def _write_meta(spend_df: pd.DataFrame, photo_dicts: list[dict],
                route_data: dict) -> None:
    matched = sum(1 for p in photo_dicts if p.get("matched_spend_id"))
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spending_rows": int(len(spend_df)),
        "date_range": [spend_df["date"].min(), spend_df["date"].max()],
        "usd_total": round(float(spend_df["amount_usd"].sum()), 2),
        "usd_by_country": {
            k: round(float(v), 2)
            for k, v in spend_df.groupby("country")["amount_usd"].sum().items()
        },
        "photos_geotagged": len(photo_dicts),
        "photos_by_country": dict(Counter(p["country"] for p in photo_dicts)),
        "photos_matched": matched,
        "route_points": {k: len(v) for k, v in route_data["routes"].items()},
    }
    config.META_JSON.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-vision", action="store_true",
                    help="skip the Anthropic vision photo-matching step")
    ap.add_argument("--vision-only", action="store_true",
                    help="re-run vision over the existing photos.json")
    ap.add_argument("--workers", type=int, default=4,
                    help="vision API concurrency (default 4)")
    args = ap.parse_args()

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # ── Spending (needed for vision matching regardless of mode) ──────────────
    spend_rows = spending_mod.rows_to_dicts(spending_mod.parse_spending())
    spend_df = pd.DataFrame(spend_rows)

    if args.vision_only:
        # Reuse already-extracted photos/thumbnails; only redo the matching.
        photo_dicts = json.loads(config.PHOTOS_JSON.read_text(encoding="utf-8"))
        route_data = json.loads(config.ROUTE_JSON.read_text(encoding="utf-8"))
        print(f"Loaded {len(photo_dicts)} photos from {config.PHOTOS_JSON.name}")
    else:
        spend_df.to_csv(config.SPENDING_CSV, index=False, encoding="utf-8")
        print(f"Wrote {config.SPENDING_CSV.name}: {len(spend_df)} rows")

        route_data = timeline.build_routes()
        config.ROUTE_JSON.write_text(
            json.dumps(route_data, indent=2), encoding="utf-8")
        print("Wrote {}: {}".format(
            config.ROUTE_JSON.name,
            ", ".join(f"{k} {len(v)} pts"
                      for k, v in route_data["routes"].items())))

        photo_dicts = photos_mod.photos_to_dicts(photos_mod.extract_photos())
        from pipeline import corrections
        corrections.apply_photos(photo_dicts)
        print(f"Extracted {len(photo_dicts)} geotagged photos")

    # ── Vision matching (optional, needs API key) ─────────────────────────────
    run_vision = args.vision_only or (
        not args.no_vision and os.environ.get("ANTHROPIC_API_KEY"))
    if run_vision:
        from pipeline import vision

        def _progress(done, total, photo):
            tag = f"→ #{photo['matched_spend_id']}" if photo.get(
                "matched_spend_id") else "(no match)"
            print(f"  vision {done}/{total} {photo['filename']} {tag}")

        print(f"Running vision matching on {len(photo_dicts)} photos "
              f"({args.workers} workers, model {vision.MODEL})...")
        vision.enrich_photos(photo_dicts, spend_rows, _photos_dir(),
                             max_workers=args.workers, progress=_progress)
    elif not args.no_vision:
        print("ANTHROPIC_API_KEY not set — skipping vision matching. "
              "Set it and run `python build_dataset.py --vision-only` later.")

    # Curated (hand-matched) photo→purchase links — the no-API alternative.
    from pipeline import corrections as _corr
    _corr.apply_manual_matches(photo_dicts, spend_rows)
    n_matched = sum(1 for p in photo_dicts if p.get("matched_spend_id"))
    print(f"Applied curated matches: {n_matched} photos linked to a purchase")

    # High-res "view" images for the gallery lightbox — matched photos only,
    # written as static files (served lazily) so photos.json stays small.
    try:
        n_full = photos_mod.write_full_images(photo_dicts, _photos_dir())
        print(f"Wrote {n_full} full-size gallery images to {config.FULL_IMG_DIR}")
    except FileNotFoundError as e:
        print(f"Skipped full-size images ({e})")

    config.PHOTOS_JSON.write_text(
        json.dumps(photo_dicts, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {config.PHOTOS_JSON.name}: {len(photo_dicts)} photos")

    # Curated landmarks, validated against the photos/route we just wrote.
    from pipeline import landmarks
    lms = landmarks.write_landmarks()
    print(f"Wrote landmarks.json: {len(lms)} landmarks")

    meta = _write_meta(spend_df, photo_dicts, route_data)
    print(f"Wrote {config.META_JSON.name}")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()

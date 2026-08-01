"""Match each geotagged photo to a specific same-day purchase via the Anthropic
vision API.

For every photo we send the image plus that day's list of logged purchases and
ask the model to (a) describe what's visible and (b) pick the single purchase
the photo most likely depicts — e.g. a photo of matcha ice cream taken on a day
with a "¥400 Matcha ice cream" line matches that line at high confidence. Photos
that are just scenery, or whose day has no matching purchase, are left unmatched.

Requires ANTHROPIC_API_KEY in the environment. This is an offline enrichment
step run once by build_dataset.py; the deployed app never calls the API.
"""

from __future__ import annotations

import base64
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

from PIL import Image

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pass

# claude-sonnet-5: current, vision-capable, supports structured outputs (which
# the prompt's suggested claude-sonnet-4-6 does not). Change here to re-tune.
MODEL = "claude-sonnet-5"
VISION_MAX_PX = 768

_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {
            "type": "string",
            "description": "One sentence describing what is visible, focusing "
                           "on food, drink, products, or place.",
        },
        "matched_spend_id": {
            "type": "integer",
            "description": "The spend_id of the purchase this photo depicts, or "
                           "0 if none of the listed purchases match.",
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["description", "matched_spend_id", "confidence"],
    "additionalProperties": False,
}


def _encode_for_vision(path, max_px: int = VISION_MAX_PX) -> str:
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_px, max_px))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _prompt(date: str, country: str, candidates: list[dict]) -> str:
    if candidates:
        lines = "\n".join(
            f"  [{c['spend_id']}] {c['description']} "
            f"— {c['amount_original']:g} {c['currency']}"
            for c in candidates
        )
        purchases = f"Purchases logged on {date} in {country}:\n{lines}"
        rule = ("Then decide which single purchase (if any) the photo most "
                "likely depicts — a photo of an item, meal, drink, or activity "
                "that clearly matches one entry should return that entry's id. "
                "If the photo is scenery or shows nothing matching a listed "
                "purchase, return 0.")
    else:
        purchases = f"No purchases were logged on {date}."
        rule = "There are no purchases to match, so return matched_spend_id 0."

    return (
        f"This travel photo was taken on {date} in {country}.\n\n"
        f"{purchases}\n\n"
        "In one sentence, describe what is visible in the photo, focusing on "
        "any food, drink, product, or place. "
        f"{rule}"
    )


def _match_one(client, photo: dict, candidates: list[dict], photos_dir) -> dict:
    """Return the enrichment fields for one photo (never raises)."""
    result = {"description": "", "matched_spend_id": None, "match_confidence": ""}
    try:
        img_b64 = _encode_for_vision(photos_dir / photo["filename"])
        resp = client.messages.create(
            model=MODEL,
            max_tokens=400,
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": img_b64}},
                    {"type": "text", "text": _prompt(
                        photo.get("date") or "an unknown date",
                        photo["country"], candidates)},
                ],
            }],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        data = json.loads(text)
        result["description"] = data.get("description", "").strip()
        result["match_confidence"] = data.get("confidence", "")
        mid = data.get("matched_spend_id") or 0
        valid_ids = {c["spend_id"] for c in candidates}
        result["matched_spend_id"] = mid if mid in valid_ids else None
    except Exception as exc:  # keep going on any single-photo failure
        result["description"] = f"(vision skipped: {type(exc).__name__})"
    return result


def enrich_photos(photos: list[dict], spend_rows: list[dict], photos_dir,
                  max_workers: int = 4, progress=None) -> list[dict]:
    """Add description / matched_spend_id / match_confidence to each photo dict.

    Mutates and returns the same list of photo dicts.
    """
    import anthropic
    client = anthropic.Anthropic()

    by_date: dict[str, list[dict]] = defaultdict(list)
    for row in spend_rows:
        by_date[row["date"]].append(row)

    total = len(photos)
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_match_one, client, photo,
                        by_date.get(photo.get("date"), []), photos_dir): photo
            for photo in photos
        }
        for fut in as_completed(futures):
            photo = futures[fut]
            photo.update(fut.result())
            done += 1
            if progress:
                progress(done, total, photo)

    return photos

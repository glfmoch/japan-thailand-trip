"""Generate curation aids into data/raw/reference/ (gitignored):

  * sheet_NN.jpg   labelled contact sheets of every photo (filename + date +
                   country + a ✓ if it's already matched to a purchase) so you
                   can find the filename to put in data/matches.csv.
  * purchases.txt  every purchase in date order, marked [PHOTO] if a photo is
                   matched to it or [ no photo ] if not.

Run:  python make_reference.py
Then edit data/matches.csv and run  python apply_matches.py.
"""

from __future__ import annotations

import base64
import io
import json

from PIL import Image, ImageDraw, ImageFont

from pipeline import config, corrections, spending

REF = config.RAW_DIR / "reference"
REF.mkdir(parents=True, exist_ok=True)

photos = json.loads(config.PHOTOS_JSON.read_text(encoding="utf-8"))
photos.sort(key=lambda p: (p.get("datetime") or ""))
rows = spending.rows_to_dicts(spending.parse_spending())
matched_ids = {p["matched_spend_id"] for p in photos if p.get("matched_spend_id")}

# ── Contact sheets ────────────────────────────────────────────────────────────
CELL, LABEL, COLS, PER = 165, 20, 6, 36
try:
    font = ImageFont.truetype("arial.ttf", 12)
except Exception:
    font = ImageFont.load_default()

for s, start in enumerate(range(0, len(photos), PER)):
    batch = photos[start:start + PER]
    r_n = (len(batch) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * CELL, r_n * (CELL + LABEL)), "#111")
    draw = ImageDraw.Draw(sheet)
    for i, p in enumerate(batch):
        r, c = divmod(i, COLS)
        x, y = c * CELL, r * (CELL + LABEL)
        try:
            im = Image.open(io.BytesIO(base64.b64decode(p["thumb_b64"]))).convert("RGB")
            im.thumbnail((CELL - 4, CELL - 4))
            sheet.paste(im, (x + 2, y + LABEL))
        except Exception:
            pass
        mark = " ✓" if p.get("matched_spend_id") else ""
        stem = p["filename"].rsplit(".", 1)[0]
        draw.text((x + 3, y + 4),
                  f'{stem} {(p.get("date") or "")[5:]} {p["country"][:2]}{mark}',
                  fill="#e6d38a" if mark else "#ddd", font=font)
    sheet.save(REF / f"sheet_{s:02d}.jpg", "JPEG", quality=72)

# ── Purchases list ────────────────────────────────────────────────────────────
lines = ["Purchases in date order — [PHOTO] = a photo is matched to it.\n"]
for r in sorted(rows, key=lambda r: (r["date"], -r["amount_usd"])):
    tag = "[PHOTO]     " if r["spend_id"] in matched_ids else "[ no photo ]"
    lines.append(f'{r["date"]}  {tag}  {r["amount_original"]:>7g} {r["currency"]:<3} '
                 f'(${r["amount_usd"]:>6.2f})  {r["description"]}')
n_photo = sum(1 for r in rows if r["spend_id"] in matched_ids)
lines.append(f"\n{n_photo} of {len(rows)} purchases have a photo.")
(REF / "purchases.txt").write_text("\n".join(lines), encoding="utf-8")

print(f"Wrote reference sheets + purchases.txt to {REF}")
print(f"({len(photos)} photos, {n_photo}/{len(rows)} purchases have a photo)")

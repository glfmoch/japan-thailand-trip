"""Re-apply photo↔purchase matches from data/matches.csv to the dashboard data.

Workflow for curating the Moments gallery yourself:

    1. Open  data/matches.csv  and edit it:
         photo               a photo's filename without extension, e.g. IMG_6781
         date                the purchase date, YYYY-MM-DD (e.g. 2026-06-25)
         purchase_contains   a few words that appear in that day's purchase,
                             e.g. "green shell calzone"
         caption             the one-line description shown under the photo
         confidence          high | medium | low
       Add a row to match a new photo, delete a row to un-match one.
       Use the reference sheets in data/raw/reference/ to find photo filenames,
       and the "purchases" list there to see which purchases still have no photo.
    2. Run:   python apply_matches.py
    3. Refresh the Streamlit app.

This only updates the match links + captions; it does not re-read any photos.
"""

from __future__ import annotations

import json

from pipeline import config, corrections, spending

photos = json.loads(config.PHOTOS_JSON.read_text(encoding="utf-8"))
rows = spending.rows_to_dicts(spending.parse_spending())

corrections.apply_manual_matches(photos, rows)
config.PHOTOS_JSON.write_text(
    json.dumps(photos, ensure_ascii=False), encoding="utf-8")

matched = sum(1 for p in photos if p.get("matched_spend_id"))
print(f"Applied matches from {corrections.MATCHES_CSV.name}: "
      f"{matched} photos linked to a purchase.")

# Warn about rows that couldn't be resolved (bad filename / date / keyword).
stems = {p["filename"].rsplit(".", 1)[0] for p in photos}
resolved = {p["filename"].rsplit(".", 1)[0] for p in photos if p.get("matched_spend_id")}
for stem, m in corrections.load_matches().items():
    if stem not in stems:
        print(f"  ⚠  {stem}: no photo with that filename in the dataset")
    elif stem not in resolved:
        print(f"  ⚠  {stem}: no purchase on {m['date']} contains "
              f"\"{m['match']}\" — check the date/keyword")
print("Done. Refresh the app to see the changes.")

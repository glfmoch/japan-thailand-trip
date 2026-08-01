# Curating the photo → purchase matches

The **Caught Spending** gallery pairs photos with the exact purchase they show. You can
edit these matches by hand — no API key, no cost. Not every purchase has a photo
(and not every photo is a purchase), so this is a sparse, curated list.

## The 3-step loop

1. **See what's there** — generate the reference aids:

   ```bash
   python make_reference.py
   ```

   This writes to `data/raw/reference/` (kept private, gitignored):
   - `sheet_00.jpg … ` — contact sheets of every photo, each labelled with its
     **filename**, date, country, and a **✓** if it's already matched.
   - `purchases.txt` — every purchase in date order, marked `[PHOTO]` or
     `[ no photo ]` so you can see what still needs one.

2. **Edit the matches** — open **`data/matches.csv`** and add / change / delete rows:

   | column | meaning | example |
   |---|---|---|
   | `photo` | photo filename, no extension | `IMG_6781` |
   | `date` | the purchase date | `2026-06-25` |
   | `purchase_contains` | a few words from that day's purchase | `green shell calzone` |
   | `caption` | the line shown under the photo | `A green Koopa-shell calzone…` |
   | `confidence` | `high` / `medium` / `low` | `high` |

   Add a row to match a new photo; delete a row to un-match one.

3. **Apply and refresh**:

   ```bash
   python apply_matches.py
   ```

   It updates the dashboard data and warns about any row whose filename, date, or
   keyword didn't resolve. Refresh the Streamlit app to see the gallery change.

## Tips

- **Matching is fuzzy.** `purchase_contains` doesn't need exact spelling — the
  photo links to the same-day purchase that shares the most words, tolerant of
  plurals and small typos (e.g. `onigiri` → "onigiris", `izakaya` → "Isekai").
  Just describe the item in a few words.
- A photo can only match a purchase **on the same date**, so the photo's date
  has to line up with the purchase's date.
- **Editing in Excel is fine** — the loader accepts Excel's date format
  (`6/28/2026`) and either UTF-8 or ANSI encoding, so a normal Save won't break
  anything. (Editing in a plain text editor keeps the original ISO dates if you
  prefer.)
- Forgot to log a purchase that a photo shows? Add it to `SUPPLEMENTAL` in
  `pipeline/corrections.py` (date, country, category, description, amount), then
  it can be matched like any other.
- `python apply_matches.py` prints a ⚠ for any row it couldn't resolve, so you
  always know if a keyword/date needs a tweak.
- The matches live in `data/matches.csv` (committed). The reference sheets stay
  local and private.

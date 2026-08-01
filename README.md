# Japan & Thailand Trip — A Personal-Data Analysis

**Turning three messy real-world data sources — a Google Maps location history,
a hand-scribbled spending log, and 300+ phone photos — into a clean, reproducible
analysis and an interactive dashboard.**

> A summer portfolio project exploring what I can learn about my own trip when I
> treat it like an analytics problem: collect, clean, model, visualize, and
> surface insights. Built end-to-end in Python.

![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-ff4b4b)
![Python](https://img.shields.io/badge/Python-pandas-3776ab)
![Status](https://img.shields.io/badge/data-real%20trip-2dd4bf)

---

## The question

*Where did my money and time actually go across 27 days in Japan and Thailand —
and can I reconstruct the trip from the digital trail it left behind?*

---

## Key findings

- **Getting there cost more than being there.** Two long-haul US↔Asia flights
  plus the Japan→Thailand connector totalled **~$2,286** — roughly **2.3× the
  ~$998 spent on the ground** across three weeks. The flights, not daily life,
  were the trip's real expense (all-in cost **~$3,283**).
- **On the ground, the two legs cost about the same per day** — **~$36/day in
  Japan** vs **~$34/day in Thailand** — once airfare is separated out as a travel
  cost. The dramatic gap in raw totals was almost entirely airfare.
- **Food & Drink dominated** on-the-ground spending, the single largest category
  by a wide margin — a day-to-day trip, not a big-ticket one.
- **Souvenir shopping was almost entirely a Thailand thing** (crocodile leather
  goods, COS, Muji), a small share of Japan spend but a large share of Thailand's.
- **The Osaka Aquarium (Kaiyukan) was the single most-photographed place** —
  81 photos taken within 350 m — a clear signal of where I spent the most time.
- A **daily-consumption pattern**: dozens of convenience-store (*konbini*) runs
  and a steady boba / matcha habit that the log makes impossible to hide.

*(All figures are computed live in the dashboard from the parsed data — nothing
is hard-coded.)*

---

## What it does

An interactive **Streamlit** dashboard in four tabs:

| Tab | What it shows |
|---|---|
| 🗺️ **Map** | Every geotagged photo as a pin (Japan red, Thailand green), the Thailand GPS route, ⭐ landmarks sized by how many photos I took there, a photo-density heatmap, and a fullscreen view. |
| 💴 **Spending** | Key findings, KPIs, and six charts — by country, over time, by category, top purchases, **Japan vs Thailand head-to-head**, and cumulative spend. |
| 📸 **Caught Spending** | A gallery of photos each **matched to the exact purchase it captured**, with the price tagged on (a matcha-ice-cream photo → the matcha-ice-cream line item). |
| 📋 **Summary** | Trip metrics + a "trip in numbers" strip + the full sortable spending table. |

Responsive for desktop, tablet, and phone.

---

## Analytical process

```
data/raw/  ──►  build_dataset.py  ──►  data/processed/  ──►  app.py
 (private)        pipeline/*.py         (committed)          (dashboard)
   collect          clean + model         analyze              visualize
```

1. **Collect** — Google Takeout Timeline JSON, a `.docx` spending log, an
   iPhone photo export.
2. **Clean (the hard part)** — the spending log is genuinely messy: four
   currencies (¥/$/฿/NTD), inconsistent date headers (`June 25th`, `July 1st`),
   lines with no currency marker, multi-line entries, and an ATM withdrawal
   whose *fee* is the real cost. `pipeline/spending.py` normalizes all of it and
   infers a category per line. Known data-entry errors (a mistyped amount, a
   bundled two-item line) are handled through a **documented corrections layer**
   and a line-splitter — the raw file stays immutable and every adjustment is
   auditable.
3. **Model** — everything is converted to a common schema and a common currency
   (USD, at fixed trip rates), photos are reverse-geocoded to a country by
   bounding box, and Timeline segments are flattened into an ordered route.
4. **Enrich** — standout photos are matched **by hand** to the exact purchase
   they show — a curated, documented, reproducible set in `data/matches.csv`.
   (An experimental Claude-vision matcher lives in `pipeline/vision.py`, but
   every published match was made and verified manually.)
5. **Analyze & visualize** — findings and charts are computed with pandas and
   rendered with Plotly + Folium.

> **Full architecture:** see [`ARCHITECTURE.md`](ARCHITECTURE.md) for the
> build-vs-serve split, the module breakdown, and the data-flow diagram.

---

## Skills demonstrated

- **Data cleaning / wrangling** of unstructured, real-world text (multi-currency,
  free-form, inconsistent) — the messiest and most representative part of analyst
  work.
- **ETL pipeline design** — a modular, re-runnable `pipeline/` package with a
  single orchestrator, separating raw sources from committed, deploy-safe outputs.
- **Geospatial analysis** — EXIF GPS extraction, bounding-box classification,
  route reconstruction, proximity validation of landmarks (haversine).
- **Human-in-the-loop curation** — hand-matching photos to purchases through a
  documented, reproducible file layered over an immutable raw source, the way an
  analyst reconciles records they don't own.
- **Dashboarding & data storytelling** — a responsive, insight-first UI.
- **Reproducibility & data hygiene** — deterministic build, personal raw data
  kept out of version control.

---

## Tech stack

Python · pandas · Pillow + pillow-heif (HEIC EXIF) · Folium + streamlit-folium ·
Plotly · Streamlit.

*(An optional, experimental Claude-vision photo matcher is included in the code
(`pipeline/vision.py`) but was **not** used for the published dataset — the
photo→purchase matches are all hand-curated.)*

---

## Run it locally

```bash
python -m venv venv
venv\Scripts\activate           # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
streamlit run app.py            # uses the committed data/processed/ dataset
```

### Rebuild the dataset from raw sources

```bash
python build_dataset.py               # parse, extract, apply hand-curated matches
python build_dataset.py --no-vision   # same, explicitly skipping the vision matcher
```

The published photo→purchase matches are **hand-curated** in `data/matches.csv`
(no API key or cost). The experimental Claude-vision matcher is optional and was
not used for the published data; if you want to try it, set an API key and run
`python build_dataset.py --vision-only`.

---

## Deployment

Designed for **Streamlit Community Cloud** — connect the repo at
[share.streamlit.io](https://share.streamlit.io) with main file `app.py`. No
secrets or API calls are needed at runtime; the app reads the committed
`data/processed/` dataset.

---

## Data & privacy

Raw location history, the raw spending document, and full-resolution photos are
**never committed** (`data/raw/` is gitignored). What ships publicly is the
derived, deploy-safe dataset: 300 px thumbnails, the parsed spending table, the
movement route, and the validated landmark list — plus a larger (1100 px)
click-to-enlarge image for each of the ~97 purchase-matched gallery photos,
served as static files.

---

*Built by **Ryan Mathew** — Data Visualization, University of Washington Bothell.
Aspiring data analyst. [Add your LinkedIn here].*

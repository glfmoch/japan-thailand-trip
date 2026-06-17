# Japan & Thailand Trip — Personal Data Analysis

An end-to-end personal data pipeline built around a trip to Japan and Thailand.
Raw location history and spending logs are parsed with Python/pandas, stored in
PostgreSQL, and explored through a deployed Streamlit dashboard with an
interactive map.

> **Status:** Pre-trip scaffold. Data stubs and pipeline are in place; real
> analysis fills in after the trip.

---

## Stack

| Layer | Tool |
|---|---|
| Parsing | Python 3.13, pandas |
| Database | PostgreSQL + SQLAlchemy + psycopg2 |
| Dashboard | Streamlit |
| Version control | Git / GitHub |

---

## Data Sources

### 1. Google Maps Timeline JSON
Exported via Google Takeout → Location History.

Two possible formats:
- **Semantic Location History** (`YYYY/YYYY_MONTH.json`) — pre-parsed into
  `placeVisit` and `activitySegment` records. Preferred format.
- **Records.json** — raw GPS pings with timestamps. Fallback if semantic
  history isn't available.

Placed in `data/raw/` (gitignored — never committed).

### 2. Manual Spending Log
A CSV maintained during the trip tracking every expense:
`date, city, country, category, description, amount_local, currency, amount_usd`.

Categories: Food, Transport, Accommodation, Activities, Shopping.

Placed in `data/raw/spending.csv` (gitignored).

### 3. Photo EXIF (backup)
iPhone photos embed GPS coordinates and timestamps. If Timeline export is
sparse, EXIF data can fill gaps using the `exifread` or `Pillow` library.

---

## PostgreSQL Schema

```sql
-- Lookup table: one row per city visited
CREATE TABLE cities (
    city_id  SERIAL PRIMARY KEY,
    city     TEXT NOT NULL,
    country  TEXT NOT NULL,
    region   TEXT,
    UNIQUE (city, country)
);

-- One row per named place visited (sourced from Timeline or manual entry)
CREATE TABLE visits (
    visit_id            SERIAL PRIMARY KEY,
    city_id             INT REFERENCES cities(city_id),
    location_name       TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    arrival_datetime    TIMESTAMP WITH TIME ZONE,
    departure_datetime  TIMESTAMP WITH TIME ZONE,
    duration_hours      NUMERIC(6, 2),
    source              TEXT DEFAULT 'timeline'
);

-- One row per expense
CREATE TABLE spending (
    spend_id      SERIAL PRIMARY KEY,
    city_id       INT REFERENCES cities(city_id),
    spend_date    DATE NOT NULL,
    category      TEXT,
    description   TEXT,
    amount_local  NUMERIC(10, 2),
    currency      CHAR(3),
    amount_usd    NUMERIC(10, 2)
);
```

---

## Analysis Questions

| Question | Approach |
|---|---|
| Which locations did I spend the most time at? | `GROUP BY location_name ORDER BY SUM(duration_hours) DESC` |
| How did I move between cities day by day? | Timeline view joining visits ordered by `arrival_datetime` |
| What was my daily spend in USD? | `GROUP BY spend_date ORDER BY spend_date` |
| How does Japan spending compare to Thailand by category? | `GROUP BY country, category` pivot |
| What was the most expensive single day, and why? | `ORDER BY SUM(amount_usd) DESC LIMIT 1` |
| What transport modes did I use most? | Parse `activitySegment.activityType` from Timeline JSON |

---

## Project Structure

```
.
├── data/
│   ├── raw/          # Real exports — gitignored, never committed
│   ├── processed/    # Cleaned CSVs — gitignored
│   └── sample/       # Fake sample data — committed for demonstration
├── scripts/
│   ├── parse_timeline.py   # Timeline JSON → DataFrame
│   └── load_to_postgres.py # DataFrame → PostgreSQL
├── app/
│   └── streamlit_app.py    # Dashboard
├── requirements.txt
└── README.md
```

---

## Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up PostgreSQL connection (when ready)
#    Create a .env file (gitignored):
#    DATABASE_URL=postgresql://user:password@localhost:5432/japan_trip

# 4. Create database schema
python scripts/load_to_postgres.py

# 5. Run the dashboard
streamlit run app/streamlit_app.py
```

---

## Deployment

The Streamlit app is designed for **Streamlit Community Cloud**:
1. Push this repo to GitHub.
2. Connect at [share.streamlit.io](https://share.streamlit.io).
3. Set `DATABASE_URL` as a secret in the Streamlit Cloud dashboard.

---

*Built by Ryan Mathew — Data Visualization, University of Washington Bothell*

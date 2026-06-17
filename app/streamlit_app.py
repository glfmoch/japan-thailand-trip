"""
streamlit_app.py — Japan & Thailand Trip Dashboard

Run locally:
    streamlit run app/streamlit_app.py
"""

import streamlit as st
import pandas as pd
from pathlib import Path

SAMPLE_VISITS = Path(__file__).parent.parent / "data" / "sample" / "sample_visits.csv"
SAMPLE_SPENDING = Path(__file__).parent.parent / "data" / "sample" / "sample_spending.csv"

st.set_page_config(page_title="Japan & Thailand Trip", page_icon="✈️", layout="wide")

st.title("Japan & Thailand Trip — Personal Data Dashboard")
st.caption("End-to-end pipeline: Google Maps Timeline → PostgreSQL → Streamlit")

st.info(
    "**Work in progress.** The dashboard will populate with real data after the trip. "
    "For now it renders the sample dataset to validate the pipeline shape.",
    icon="🗺️",
)

st.divider()

# ── Sample data preview ───────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("Sample Visits")
    if SAMPLE_VISITS.exists():
        visits = pd.read_csv(SAMPLE_VISITS)
        st.dataframe(visits, use_container_width=True)
        st.caption(f"{len(visits)} rows · source: data/sample/sample_visits.csv")
    else:
        st.warning("sample_visits.csv not found.")

with col2:
    st.subheader("Sample Spending")
    if SAMPLE_SPENDING.exists():
        spending = pd.read_csv(SAMPLE_SPENDING)
        st.dataframe(spending, use_container_width=True)
        st.caption(f"{len(spending)} rows · source: data/sample/sample_spending.csv")
    else:
        st.warning("sample_spending.csv not found.")

st.divider()

# ── Planned sections (placeholders) ──────────────────────────────────────────

st.subheader("Planned Visualizations")

placeholders = [
    ("🗺️ Interactive Map", "Pydeck/Folium map of all visit locations, colored by country."),
    ("⏱️ Time per Location", "Bar chart: hours spent at each named location."),
    ("💴 Daily Spend", "Line chart: USD spend per day, annotated with city transitions."),
    ("🇯🇵 vs 🇹🇭 Spending Comparison", "Side-by-side breakdown by category (Food, Transport, etc.)."),
    ("🚶 Movement Patterns", "Timeline view of city transitions and transit segments."),
]

for icon_title, description in placeholders:
    with st.expander(icon_title):
        st.write(description)
        st.write("_Awaiting real data and SQL queries._")

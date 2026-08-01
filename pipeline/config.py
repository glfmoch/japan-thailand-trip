"""Shared configuration for the pipeline: paths, rates, categories, geo windows."""

from __future__ import annotations

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"

# Committed, deploy-safe outputs the Streamlit app reads
SPENDING_CSV = PROCESSED_DIR / "spending.csv"
PHOTOS_JSON = PROCESSED_DIR / "photos.json"
ROUTE_JSON = PROCESSED_DIR / "route.json"
META_JSON = PROCESSED_DIR / "meta.json"

# Full-size gallery images, served statically (Streamlit enableStaticServing) so
# they load lazily on click instead of bloating photos.json. Committed.
STATIC_DIR = PROJECT_ROOT / "static"
FULL_IMG_DIR = STATIC_DIR / "full"

TRIP_YEAR = 2026

# ── Fixed exchange rates (units of local currency per 1 USD) ──────────────────
USD_PER = {
    "USD": 1.0,
    "JPY": 155.0,
    "THB": 35.0,
    "NTD": 32.0,
}


def to_usd(amount: float, currency: str) -> float:
    """Convert a local amount to USD using the fixed trip rates."""
    rate = USD_PER.get(currency, 1.0)
    return round(amount / rate, 2)


# ── Geographic windows (rough bounding boxes) ─────────────────────────────────
# (lat_min, lat_max, lon_min, lon_max)
GEO_WINDOWS = {
    "Japan": (24.0, 46.0, 128.0, 146.0),
    "Thailand": (5.0, 21.0, 97.0, 106.0),
    "Taiwan": (21.0, 25.5, 119.0, 122.5),
}

# Pin colors used on the map
COUNTRY_COLOR = {"Japan": "red", "Thailand": "green", "Taiwan": "purple"}


def country_for_point(lat: float, lon: float) -> str | None:
    """Return the country name whose window contains (lat, lon), or None."""
    for name, (la0, la1, lo0, lo1) in GEO_WINDOWS.items():
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return name
    return None


# ── Spending categories ───────────────────────────────────────────────────────
# Categories are inferred from the description text. Rules are applied in the
# order below; the first matching group wins. Convenience-store markers win over
# generic food so a "Lawson onigiri" lands in Convenience Store, matching how the
# log was written.
CATEGORY = {
    "Flights": ["flight", "airfare", "plane ticket"],
    "Accommodation": ["airbnb", "hotel", "hostel", "guesthouse", "lodging",
                      "accommodation"],
    "Transit": [
        "suica", "train", "bus", "fare", "van ride", "transport", "transit",
        "airport train",
    ],
    "Convenience Store": [
        "7/11", "7-11", "seven", "lawson", "family mart", "familymart",
        "vending",
    ],
    "Activities & Entertainment": [
        "ticket", "day pass", " pass", "movie", "aquarium", "castle",
        "universal", "nintendo", "entry fee", "entry", "market entry",
    ],
    "Shopping": [
        "souvenir", "magnet", "wallet", "belt", "card holder", "cardholder",
        "t-shirt", "tshirt", "shirt", "clothes", "gift", "leather",
        "chocolates to bring", "cos ", "muji", "linen", "button up",
    ],
    "Health & Misc": [
        "esim", "sim", "pedicure", "haircut", "medicine", "cream", "eczema",
        "toilet paper", "chlorophyll", "debloat", "health drink", "donation",
    ],
}

# Order of precedence for category matching.
CATEGORY_ORDER = [
    "Flights",
    "Accommodation",
    "Convenience Store",
    "Transit",
    "Activities & Entertainment",
    "Shopping",
    "Health & Misc",
]
DEFAULT_CATEGORY = "Food & Drink"


def categorize(description: str) -> str:
    """Infer a spending category from a free-text description."""
    text = description.lower()
    for cat in CATEGORY_ORDER:
        for marker in CATEGORY[cat]:
            if marker in text:
                return cat
    return DEFAULT_CATEGORY

"""Documented, transparent corrections to the hand-kept spending log.

The raw ``.docx`` is treated as an immutable source. Known data-entry errors are
recorded here and applied *after* parsing, so every adjustment is auditable and
reproducible rather than silently editing the original file. This mirrors how a
real analyst handles corrections to a system-of-record they don't own.

Add a rule as a dict keyed by a stable matcher (date + a lowercase substring of
the description). Override ``amount_original`` (USD is recomputed) and/or other
fields, and always give a ``reason``.
"""

from __future__ import annotations

from . import config

CORRECTIONS: list[dict] = [
    {
        "date": "2026-07-12",
        "match": "crocodile leather wallet",
        "amount_original": 1300.0,   # logged as 3900฿ by mistake
        "reason": "Wallet mis-logged as 3900฿; actual price was 1300฿ (~$37).",
    },
    {
        "date": "2026-07-17",
        "match": "crocodile belt",
        "description": "Custom crocodile belt & card holder",
        "reason": "Belt (฿2000) + card holder (฿800) bought together at the "
                  "leather shop and shown in one photo — kept as a single ฿2800 "
                  "purchase.",
    },
    {
        "date": "2026-06-24",
        "match": "withdraw",
        "amount_original": 110.0,          # keep only the ¥110 ATM fee
        "description": "7-Eleven ATM fee",
        "reason": "The ¥10,000 cash withdrawn was spent through other logged "
                  "purchases, so counting it would double-count. Only the ¥110 "
                  "fee is a real, separate cost.",
    },
]

# Real expenses that weren't captured in the daily spending log. Added
# transparently rather than back-filled into the raw source.
#   - The two long-haul US<->Asia flights (the trip's biggest cost).
#   - My share of the Airbnb, paid to a friend and split across the group.
#   - NOT added: a $177.50 Japan->Thailand flight that was cancelled and fully
#     refunded; the $246 replacement is already in the log.
# (All three flights cross borders; "long-haul" just distinguishes the home
#  round-trip from the shorter Japan->Thailand connector.)
SUPPLEMENTAL: list[dict] = [
    {"date": "2026-06-23", "country": "Japan", "category": "Flights",
     "description": "International flight, US → Japan",
     "amount_original": 1215.00, "currency": "USD"},
    {"date": "2026-07-19", "country": "Thailand", "category": "Flights",
     "description": "International flight, Thailand → US",
     "amount_original": 824.74, "currency": "USD"},
    {"date": "2026-07-08", "country": "Thailand", "category": "Accommodation",
     "description": "Airbnb — my share of the week (split with friends)",
     "amount_original": 76.00, "currency": "USD"},
    # Forgotten at the time; recovered from a photo of the Lawson receipt (IMG_6834).
    {"date": "2026-06-28", "country": "Japan", "category": "Convenience Store",
     "description": "Lawson Special Parfait (chocolate-vanilla) and snacks",
     "amount_original": 1029.00, "currency": "JPY"},
    # Forgotten; recovered from a photo (IMG_7035). Amount is an estimate (~50฿).
    {"date": "2026-07-05", "country": "Thailand", "category": "Food & Drink",
     "description": "Coconut water and lychee soda from Lotus's",
     "amount_original": 50.00, "currency": "THB"},
    # Forgotten; recovered from photos (IMG_7078 / IMG_7079), both July 12.
    {"date": "2026-07-12", "country": "Thailand", "category": "Food & Drink",
     "description": "Dairy Queen chocolate ice cream",
     "amount_original": 55.00, "currency": "THB"},
    {"date": "2026-07-12", "country": "Thailand", "category": "Food & Drink",
     "description": "Meiji strawberry yogurt drink",
     "amount_original": 13.00, "currency": "THB"},
    # Forgotten; recovered from a photo (IMG_7109, in front of the Boost sign).
    {"date": "2026-07-15", "country": "Thailand", "category": "Food & Drink",
     "description": "Boost Mango Magic smoothie",
     "amount_original": 110.00, "currency": "THB"},
    # Forgotten; recovered from a photo (IMG_7112). Amount is an estimate (~105฿).
    {"date": "2026-07-15", "country": "Thailand", "category": "Convenience Store",
     "description": "Drinks and snacks from 7-Eleven",
     "amount_original": 105.00, "currency": "THB"},
]


# Photos whose embedded GPS is wrong (usually stale/cached from a previous city
# because the phone hadn't re-acquired signal — common in airports). Keyed by
# filename; overrides location + country so they map correctly.
PHOTO_CORRECTIONS: dict[str, dict] = {
    # Pineapple-cake gift bag, shot at Taipei (Taoyuan) airport but tagged with a
    # stale Bangkok fix — belongs with the other Taiwan-layover purchases.
    "IMG_7159.HEIC": {"lat": 25.0779, "lon": 121.2306, "country": "Taiwan",
                      "reason": "Stale Bangkok GPS; actually Taipei airport."},
    # Rainy Hogsmeade street at Universal Studios Japan — no GPS (shot in rain).
    "IMG_6795.JPG": {"lat": 34.6656, "lon": 135.4323, "country": "Japan",
                     "reason": "No GPS; Universal Studios Japan (Hogsmeade)."},
}


# Curated photo→purchase matches (the free alternative to the vision API).
# Each is keyed by photo filename stem; `match` is a distinctive substring of the
# purchase on that date. `desc` is an objective one-line caption for the gallery.
MANUAL_MATCHES: dict[str, dict] = {
    # ── Japan (Osaka) ──
    "IMG_6766": {"date": "2026-06-24", "match": "orange juice", "conf": "high",
                 "desc": "Bottled orange juice from FamilyMart."},
    "IMG_6774": {"date": "2026-06-24", "match": "gyoza", "conf": "medium",
                 "desc": "Pan-fried gyoza with a few side samples."},
    "IMG_6781": {"date": "2026-06-25", "match": "green shell calzone", "conf": "high",
                 "desc": "A green Koopa-shell calzone at Super Nintendo World."},
    "IMG_6790": {"date": "2026-06-25", "match": "yakisoba", "conf": "medium",
                 "desc": "A convenience-store food stop in Osaka."},
    "IMG_6806": {"date": "2026-06-27", "match": "miso soup", "conf": "high",
                 "desc": "A beef-rice set with miso soup and egg."},
    "IMG_6831": {"date": "2026-06-28", "match": "debloat", "conf": "high",
                 "desc": "A Japanese anti-bloat health drink."},
    "IMG_6836": {"date": "2026-06-28", "match": "chocolates to bring", "conf": "high",
                 "desc": "A box of Japanese chocolates to bring home."},
    "IMG_6839": {"date": "2026-06-29", "match": "moomin", "conf": "high",
                 "desc": "A Moomin-branded white soda from Lawson."},
    "IMG_6853": {"date": "2026-06-29", "match": "aquarium ticket", "conf": "medium",
                 "desc": "Fish at the Osaka Aquarium (Kaiyukan)."},
    # ── Thailand ──
    "IMG_7002": {"date": "2026-07-03", "match": "seafood", "conf": "medium",
                 "desc": "A Thai seafood dinner in Pattaya."},
    "IMG_7006": {"date": "2026-07-04", "match": "hershey", "conf": "high",
                 "desc": "A Hershey's almond-matcha bar."},
    "IMG_7021": {"date": "2026-07-04", "match": "mango toffee", "conf": "high",
                 "desc": "A bag of mango toffee from the floating market."},
    "IMG_7031": {"date": "2026-07-05", "match": "everything bagel", "conf": "high",
                 "desc": "An everything bagel."},
    "IMG_7033": {"date": "2026-07-05", "match": "mcdonald", "conf": "high",
                 "desc": "A McDonald's meal in Bangkok."},
    "IMG_7043": {"date": "2026-07-07", "match": "krispy", "conf": "high",
                 "desc": "A cookies-and-cream Krispy Kreme donut."},
    "IMG_7045": {"date": "2026-07-07", "match": "auntie", "conf": "high",
                 "desc": "An Auntie Anne's pretzel chicken dog."},
    "IMG_7048": {"date": "2026-07-08", "match": "swensen", "conf": "medium",
                 "desc": "A pandan soft-serve dessert from Swensen's."},
    "IMG_7061": {"date": "2026-07-10", "match": "mont blanc", "conf": "high",
                 "desc": "A GA/GA ube Mont Blanc coconut frappe with boba."},
    "IMG_7063": {"date": "2026-07-10", "match": "nuggets", "conf": "high",
                 "desc": "McDonald's nuggets and a sundae."},
    # ── Taiwan (layover home) ──
    "IMG_7159": {"date": "2026-07-19", "match": "pineapple", "conf": "high",
                 "desc": "A gift bag of Taiwanese pineapple cakes."},
    "IMG_7160": {"date": "2026-07-19", "match": "hey song", "conf": "high",
                 "desc": "A can of HeySong sarsaparilla from a vending machine."},
    "IMG_7161": {"date": "2026-07-19", "match": "dragon fruit", "conf": "high",
                 "desc": "Dried dragon fruit and Saint Peter tea biscuits."},
}


# You can edit the matches in data/matches.csv (photo, date, purchase_contains,
# caption, confidence). If that file is present it is the source of truth; the
# MANUAL_MATCHES dict above is the built-in default used when it is absent.
MATCHES_CSV = config.PROJECT_ROOT / "data" / "matches.csv"


def _norm_date(s: str) -> str:
    """Normalise a date to ISO YYYY-MM-DD.

    Excel silently rewrites ISO dates to M/D/YYYY when the CSV is saved, so accept
    both forms rather than let edits silently stop matching.
    """
    import re
    s = (s or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        mo, d, y = m.groups()
        y = ("20" + y) if len(y) == 2 else y
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return s


def load_matches() -> dict[str, dict]:
    """Return the active photo→purchase matches (CSV if present, else built-in).

    Excel saves CSVs as UTF-8, UTF-8-with-BOM, *or* the system ANSI codepage
    (cp1252 on Windows) depending on how you save — so decode defensively rather
    than let a save silently break every match.
    """
    if not MATCHES_CSV.exists():
        return MANUAL_MATCHES
    import csv
    import io
    text = None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = MATCHES_CSV.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = MATCHES_CSV.read_text(encoding="utf-8", errors="replace")

    out: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(text)):
        stem = (row.get("photo") or "").strip()
        if not stem or stem.startswith("#"):
            continue
        out[stem] = {
            "date": _norm_date(row.get("date") or ""),
            "match": (row.get("purchase_contains") or "").strip(),
            "conf": (row.get("confidence") or "high").strip() or "high",
            "desc": (row.get("caption") or "").strip(),
        }
    return out


_STOPWORDS = {"and", "with", "the", "a", "an", "of", "from", "to", "in", "on",
              "for", "at", "my", "some"}


def _tokens(s: str) -> set[str]:
    import re
    return {w for w in re.findall(r"[a-z0-9]+", str(s).lower())
            if len(w) >= 3 and w not in _STOPWORDS}


def _similar(a: str, b: str) -> bool:
    """Loose word equality: exact, plural/prefix, or close spelling."""
    if a == b:
        return True
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return True
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def _best_match(keyword: str, same_day_rows: list[dict], extra: str = ""):
    """Pick the same-day purchase that best fits a (possibly loose) keyword.

    Scores by shared significant words (tolerant of plurals and small typos),
    with a big bonus for an exact substring — so precise keywords pin exactly
    while natural / misspelled ones still land on the closest purchase. `extra`
    (the caption) is folded into the word matching so a descriptive caption can
    rescue a vague keyword.
    """
    kw = _tokens(f"{keyword} {extra}")
    low = keyword.lower().strip()
    best, best_score = None, 0
    for r in same_day_rows:
        desc_tokens = _tokens(r["description"])
        score = sum(1 for k in kw if any(_similar(k, d) for d in desc_tokens))
        if low and low in str(r["description"]).lower():
            score += 5
        if score > best_score:
            best, best_score = r, score
    return best if best_score >= 1 else None


def apply_manual_matches(photo_dicts: list[dict], spend_rows: list[dict]) -> list[dict]:
    """Attach curated photo→purchase matches (description, spend_id, confidence).

    Matching is fuzzy: a photo links to the same-day purchase sharing the most
    words with its keyword, so hand-written / misspelled keywords still resolve.
    Removing a row in data/matches.csv un-matches that photo on the next re-apply.
    """
    matches = load_matches()
    for p in photo_dicts:
        stem = str(p.get("filename", "")).rsplit(".", 1)[0]
        m = matches.get(stem)
        if not m:
            p["matched_spend_id"] = p.get("matched_spend_id") or None
            continue
        same_day = [r for r in spend_rows if r["date"] == m["date"]]
        best = _best_match(m["match"], same_day, extra=m["desc"])
        p["description"] = m["desc"]
        p["match_confidence"] = m["conf"]
        p["matched_spend_id"] = best["spend_id"] if best else None
    return photo_dicts


def apply_photos(photo_dicts: list[dict]) -> list[dict]:
    """Override location/country for photos with known-bad GPS, in place."""
    for p in photo_dicts:
        fix = PHOTO_CORRECTIONS.get(p.get("filename"))
        if fix:
            p["lat"], p["lon"] = fix["lat"], fix["lon"]
            p["country"] = fix["country"]
    return photo_dicts


def apply(rows):
    """Apply each correction rule to the parsed rows in place; returns rows."""
    for row in rows:
        for rule in CORRECTIONS:
            if rule["date"] == row.date and rule["match"] in row.description.lower():
                if "amount_original" in rule:
                    row.amount_original = rule["amount_original"]
                    row.amount_usd = config.to_usd(row.amount_original, row.currency)
                if "category" in rule:
                    row.category = rule["category"]
                if "description" in rule:
                    row.description = rule["description"]
    return rows

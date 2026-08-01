"""Parse the free-text .docx spending log into a clean, structured table.

The log is deliberately messy: inconsistent date headers ("June 25th",
"July 1st"), amounts in four currencies (¥ JPY, $ USD, Baht THB, NTD), some
lines with no currency marker at all, multi-line entries, and one ATM
withdrawal. This module normalizes all of that into rows of:

    date, country, category, description, amount_original, currency, amount_usd
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, asdict
from datetime import date

from . import config
from . import corrections

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# A date header like "June 23", "June 25th", "July 1st"
DATE_RE = re.compile(
    r"^\s*(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\s*$",
    re.IGNORECASE,
)
# First numeric amount in a line, e.g. 2000, 4.72, 1,065
AMOUNT_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)")
# Parenthesized sub-amounts, e.g. "belt (2000) & card holder (800)"
SUB_RE = re.compile(r"\((\d[\d,]*)\)")


@dataclass
class SpendRow:
    spend_id: int
    date: str            # ISO YYYY-MM-DD
    country: str         # Japan | Thailand | Taiwan
    category: str
    description: str
    amount_original: float
    currency: str
    amount_usd: float


def _read_docx_lines(path) -> list[str]:
    """Extract non-empty paragraph text from a .docx without external deps."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    lines: list[str] = []
    for para in re.split(r"</w:p>", xml):
        texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", para)
        line = "".join(texts).replace("&amp;", "&").strip()
        if line:
            lines.append(line)
    return lines


def _infer_currency(line: str, current_month: int) -> str:
    low = line.lower()
    if "$" in line:
        return "USD"
    if "¥" in line:
        return "JPY"
    if "ntd" in low:
        return "NTD"
    if "baht" in low:
        return "THB"
    # No marker: fall back to the prevailing country for the date.
    return "JPY" if current_month == 6 else "THB"


def _country_for(currency: str, month: int) -> str:
    if currency == "JPY":
        return "Japan"
    if currency == "THB":
        return "Thailand"
    if currency == "NTD":
        return "Taiwan"
    # USD (flight / eSIM) — attribute to where we were on that date.
    return "Japan" if month == 6 else "Thailand"


def _parse_amount(line: str, currency: str) -> float | None:
    """Return the transaction amount. ATM withdrawals use the fee, not the cash."""
    if "withdraw" in line.lower():
        # e.g. "¥10000 Withdrawl from 7/11 with ¥110 fee" — the real cost is the
        # fee. Use amounts attached to the ¥/$ symbol so "7/11" isn't picked up.
        sym = [float(a.replace(",", ""))
               for a in re.findall(r"[¥$](\d[\d,]*(?:\.\d+)?)", line)]
        if len(sym) >= 2:
            return sym[-1]
    amounts = [float(a.replace(",", "")) for a in AMOUNT_RE.findall(line)]
    return amounts[0] if amounts else None


def _split_subitems(desc: str, primary: float) -> list[tuple[str, float]] | None:
    """Split a bundled line like "belt (2000) & card holder (800)" into parts.

    Only splits when there are 2+ parenthesized amounts that sum to the line's
    primary amount, so ordinary parentheticals like "(hopefully real)" are left
    alone.
    """
    subs = [float(x.replace(",", "")) for x in SUB_RE.findall(desc)]
    if len(subs) < 2 or abs(sum(subs) - primary) > 1:
        return None
    segments = re.split(r"\(\d[\d,]*\)", desc)
    out: list[tuple[str, float]] = []
    for i, amt in enumerate(subs):
        seg = (segments[i] if i < len(segments) else "").strip(" &,+/").strip()
        out.append((seg or desc, amt))
    return out


def parse_spending(docx_path=None) -> list[SpendRow]:
    """Parse the spending .docx into a list of SpendRow records."""
    if docx_path is None:
        matches = list(config.RAW_DIR.rglob("*Spending*.docx"))
        if not matches:
            raise FileNotFoundError(
                f"No spending .docx found under {config.RAW_DIR}"
            )
        docx_path = matches[0]

    lines = _read_docx_lines(docx_path)

    rows: list[SpendRow] = []
    cur_date: date | None = None
    next_id = 1

    for line in lines:
        # Header line — ignore.
        if line.lower().startswith("project spending"):
            continue

        m = DATE_RE.match(line)
        if m:
            cur_date = date(config.TRIP_YEAR, MONTHS[m.group(1).lower()],
                            int(m.group(2)))
            continue

        if cur_date is None:
            continue  # stray text before the first date header

        starts_entry = bool(re.match(r"^\s*[¥$]|^\s*\d", line)) or \
            bool(re.search(r"\d+\s*(baht|ntd)", line, re.IGNORECASE))

        if not starts_entry and rows:
            # Continuation line (e.g. a multi-line address) — append to prior row.
            rows[-1].description = f"{rows[-1].description} {line}".strip()
            continue
        if not starts_entry:
            continue

        currency = _infer_currency(line, cur_date.month)
        amount = _parse_amount(line, currency)
        if amount is None:
            continue

        # Description = the line with the leading amount/currency token removed.
        desc = re.sub(r"^\s*[¥$]?\s*\d[\d,]*(?:\.\d+)?\s*(?:baht|ntd)?\s*",
                      "", line, count=1, flags=re.IGNORECASE).strip()
        desc = desc or line

        # Kept as one row per logged line (e.g. the crocodile belt + card holder
        # are one ฿2800 purchase, matching how they were bought and photographed).
        items = [(desc, amount)]
        for item_desc, item_amt in items:
            rows.append(SpendRow(
                spend_id=next_id,
                date=cur_date.isoformat(),
                country=_country_for(currency, cur_date.month),
                category=config.categorize(item_desc),
                description=item_desc,
                amount_original=item_amt,
                currency=currency,
                amount_usd=config.to_usd(item_amt, currency),
            ))
            next_id += 1

    rows = corrections.apply(rows)

    # Append documented expenses that weren't in the daily log (flights, Airbnb).
    for s in corrections.SUPPLEMENTAL:
        rows.append(SpendRow(
            spend_id=next_id,
            date=s["date"],
            country=s["country"],
            category=s["category"],
            description=s["description"],
            amount_original=s["amount_original"],
            currency=s["currency"],
            amount_usd=config.to_usd(s["amount_original"], s["currency"]),
        ))
        next_id += 1

    return rows


def rows_to_dicts(rows: list[SpendRow]) -> list[dict]:
    return [asdict(r) for r in rows]


if __name__ == "__main__":
    parsed = parse_spending()
    print(f"Parsed {len(parsed)} spending rows")
    for r in parsed[:8]:
        print(f"  {r.date} {r.currency:>3} {r.amount_original:>8.2f} "
              f"${r.amount_usd:>6.2f} [{r.category}] {r.description[:40]}")

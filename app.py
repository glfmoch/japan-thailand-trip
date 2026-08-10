"""Japan & Thailand Trip — interactive dashboard.

Reads the committed, deploy-safe dataset in data/processed/ (built offline by
build_dataset.py) and renders three tabs: an interactive map of geotagged
photos + landmarks, a spending breakdown, and a trip summary. No raw photos,
Timeline JSON, or API calls are needed at runtime.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import json
import re
from datetime import date
from html import escape
from pathlib import Path

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from branca.element import MacroElement
from folium.plugins import Fullscreen, HeatMap, MarkerCluster
from jinja2 import Template
from streamlit_folium import st_folium

DATA = Path(__file__).parent / "data" / "processed"
SAMPLE = Path(__file__).parent / "data" / "sample"

# ── Palette (muted, minimal — colour reserved for data, not chrome) ───────────
JP = "#cf7a63"      # Japan — muted terracotta
TH = "#5fa79a"      # Thailand — muted teal
TW = "#9b8bb0"      # Taiwan — muted violet
GOLD = "#c2a15e"    # the single restrained accent
INK = "#0e0e11"
PANEL = "#141417"
COUNTRY_ACCENT = {"Japan": JP, "Thailand": TH, "Taiwan": TW}
COUNTRY_PIN = {"Japan": "red", "Thailand": "green", "Taiwan": "purple"}
# Currency symbol per country — stamped on purchase pins so a "money" photo is
# distinguishable from a plain snapshot at a glance.
CURRENCY_SYMBOL = {"Japan": "¥", "Thailand": "฿", "Taiwan": "NT$"}
CAT_COLORS = {
    "Food & Drink": JP,
    "Convenience Store": GOLD,
    "Transit": TH,
    "Activities & Entertainment": "#7f92b8",
    "Shopping": "#bd8099",
    "Health & Misc": "#8a8a92",
    "Flights": "#9b8bb0",
    "Accommodation": "#b5895f",
}
KIND_EMOJI = {
    "castle": "🏯", "aquarium": "🐬", "park": "🎢", "food": "🍜",
    "shopping": "🛍️", "market": "🏮", "beach": "🏖️", "landmark": "📍",
}
# Clean, intentional chart chrome — no default Plotly toolbar hovering over every figure.
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}

# ── Objective label normalisation ─────────────────────────────────────────────
# Turn casual log shorthand into consistent, brand-correct, shortened labels for
# the table and charts (the raw text stays in the source data).
_BRAND_FIXES = [
    # brands / vendors
    (r"mcdonald['’]?s", "McDonald's"), (r"7/11|7-11|7-eleven", "7-Eleven"),
    (r"family ?mart", "FamilyMart"), (r"lawson", "Lawson"),
    (r"don quijote", "Don Quijote"), (r"ga/ ?ga", "GA/GA"), (r"\bcos\b", "COS"),
    (r"muji", "Muji"), (r"uniqlo", "Uniqlo"), (r"suica", "Suica"),
    (r"royce", "Royce"), (r"teamlab", "teamLab"), (r"nintendo", "Nintendo"),
    (r"universal studios", "Universal Studios"), (r"gong cha", "Gong Cha"),
    (r"auntie anne['’]?s", "Auntie Anne's"), (r"wingstop", "Wingstop"),
    (r"shake shack", "Shake Shack"), (r"krispy krea?me?", "Krispy Kreme"),
    (r"swensen['’]?s", "Swensen's"), (r"boncha[no]n", "Bonchon"),
    (r"yakiniku like", "Yakiniku Like"), (r"hama-?sushi", "Hama Sushi"),
    (r"hershey", "Hershey"), (r"red ?bull", "Red Bull"), (r"singha", "Singha"),
    (r"hey ?song", "HeySong"), (r"saint peter", "Saint Peter"),
    (r"minions?", "Minions"), (r"osaka castle", "Osaka Castle"),
    (r"isekai(ya)?", "Isekaiya"), (r"pangcha", "PangCha"), (r"boost", "Boost"),
    (r"gourmet market", "Gourmet Market"), (r"terminal 21", "Terminal 21"),
    (r"mr\.? donut", "Mister Donut"), (r"lotus['’]?s", "Lotus's"),
    (r"\besim\b", "eSIM"), (r"\bmoomin\b", "Moomin"), (r"mont blanc", "Mont Blanc"),
    # places / nationalities
    (r"\bjapan\b", "Japan"), (r"\bthailand\b", "Thailand"), (r"\btaiwan\b", "Taiwan"),
    (r"\b(us|usa)\b", "US"), (r"\bosaka\b", "Osaka"), (r"\bnagasaki\b", "Nagasaki"),
    (r"\bbangkok\b", "Bangkok"), (r"\b(pattaya)\b", "Pattaya"), (r"\bsiam\b", "Siam"),
    (r"\bemsphere\b", "EmSphere"), (r"\bkorean\b", "Korean"), (r"\bthai\b", "Thai"),
    (r"\bchengdu\b", "Chengdu"), (r"\bbk\b", "Bangkok"),
]


def clean_label(text: str, maxlen: int = 40) -> str:
    raw = str(text)
    if "withdraw" in raw.lower():
        return "7-Eleven ATM fee"
    s = re.sub(r"\s*\([^)]*\)", "", raw).strip()            # drop (...) asides
    s = re.sub(r"[¥$฿]\s?\d[\d,]*\.?\d*", "", s)             # drop stray amounts
    s = re.sub(r"\bw/\b", " with ", s, flags=re.I)
    s = re.sub(r"\bw\b", "with", s, flags=re.I)
    s = s.replace("&", "and")
    s = re.sub(r"\b(lunch|dinner|breakfast|brunch|combo|total|random|some)\b",
               " ", s, flags=re.I)
    s = re.sub(r"\s*/\s*", " ", s)                           # orphan slashes
    s = re.sub(r"^[^\w]+", "", s)                            # leading junk
    s = re.sub(r"\s{2,}", " ", s).strip(" -,")
    s = (s[:1].upper() + s[1:].lower()) if s else s
    for pat, repl in _BRAND_FIXES:
        s = re.sub(pat, repl, s, flags=re.I)
    if len(s) > maxlen:
        s = s[:maxlen].rsplit(" ", 1)[0].rstrip(" ,-") + "…"
    return s

st.set_page_config(page_title="Japan & Thailand Trip", page_icon="🗾",
                   layout="wide", initial_sidebar_state="collapsed")


# ── Global styling ────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500&family=Manrope:wght@300;400;500;600&display=swap');

html, body, [class*="css"], .stMarkdown, p, div, span, label { font-family:'Manrope',sans-serif; }
:root { --bg:#0e0e11; --panel:#141417; --border:rgba(255,255,255,.09);
        --text:#e9e9ec; --muted:#87878f; --accent:#c2a15e; }

/* Hide Streamlit chrome */
header[data-testid="stHeader"] { display:none !important; }
#MainMenu, footer { visibility:hidden; }
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stAppDeployButton"],
.stAppDeployButton, .stDeployButton { display:none !important; }

.block-container { padding:2rem 2.6rem 4rem; max-width:1800px; }
.stApp { background:var(--bg); }

/* Hero */
.hero { padding:8px 0 22px; border-bottom:1px solid var(--border); margin-bottom:26px; }
.hero-kicker { font-size:.7rem; letter-spacing:.3em; text-transform:uppercase;
    color:var(--muted); font-weight:500; }
.hero-title { font-family:'Fraunces',serif; font-weight:300; letter-spacing:.005em;
    font-size:clamp(2.3rem,4.6vw,3.7rem); line-height:1.05; margin:.34em 0 .3em;
    color:var(--text); }
.hero-sub { color:#a7a7ae; font-size:1rem; max-width:660px; line-height:1.6;
    margin:0; font-weight:300; }
.chips { display:flex; flex-wrap:wrap; gap:8px 10px; margin-top:20px; }
.chip { background:transparent; border:1px solid var(--border); color:#a7a7ae;
    padding:6px 13px; border-radius:2px; font-size:.82rem; font-weight:400; }
.chip b { color:var(--text); font-weight:500; }

/* KPI cards — hairline grid, flat, no accent bars */
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
    gap:1px; margin:6px 0 12px; background:var(--border); border:1px solid var(--border); }
.kpi { background:var(--bg); padding:20px 20px 18px; }
.kpi-label { color:var(--muted); font-size:.66rem; letter-spacing:.17em;
    text-transform:uppercase; font-weight:500; }
.kpi-value { font-family:'Fraunces',serif; font-weight:300; font-size:2rem;
    color:var(--text); margin-top:11px; line-height:1; }
.kpi-sub { color:var(--muted); font-size:.77rem; margin-top:8px; font-weight:300; }

/* Section titles */
.sec { font-family:'Fraunces',serif; font-weight:400; font-size:1.15rem;
    color:var(--text); margin:30px 0 12px; letter-spacing:.01em; }

/* Note / limitations panel */
.note { background:var(--panel); border:1px solid var(--border);
    border-left:2px solid var(--accent); border-radius:2px;
    padding:15px 20px; margin:4px 0 16px; }
.note-title { font-weight:600; color:var(--text); margin-bottom:5px;
    font-size:.82rem; letter-spacing:.02em; }
.note p { color:#a7a7ae; font-size:.88rem; line-height:1.6; margin:0; font-weight:300; }
.note b { color:var(--text); font-weight:500; }

/* Key findings */
.findings { display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr));
    gap:12px; margin:4px 0 16px; }
.finding { display:flex; gap:13px; align-items:flex-start; background:transparent;
    border:1px solid var(--border); border-radius:2px; padding:15px 17px; }
.finding-ico { font-size:1rem; line-height:1.5; opacity:.85; }
.finding-txt { color:#b2b2b9; font-size:.9rem; line-height:1.6; font-weight:300; }
.finding-txt b { color:var(--text); font-weight:600; }

/* Tabs — minimal underline */
[data-baseweb="tab-list"] { gap:26px; border-bottom:1px solid var(--border) !important;
    margin-bottom:22px; background:transparent; }
button[data-baseweb="tab"] { background:transparent !important; border:none !important;
    border-radius:0 !important; padding:6px 2px 12px; height:auto;
    border-bottom:1.5px solid transparent !important; }
button[data-baseweb="tab"] p { font-weight:500; font-size:.9rem;
    letter-spacing:.02em; color:var(--muted); }
button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom:1.5px solid var(--accent) !important; }
button[data-baseweb="tab"][aria-selected="true"] p { color:var(--text); }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display:none !important; }

/* Charts + map: quiet framing */
.stPlotlyChart, [data-testid="stPlotlyChart"] { background:transparent;
    border:1px solid var(--border); border-radius:2px; padding:8px 10px; }
iframe[title="streamlit_folium.st_folium"] { border-radius:2px;
    border:1px solid var(--border); }
[data-testid="stDataFrame"] { border:1px solid var(--border); border-radius:2px; }

/* Fun-facts strip — hairline grid */
.facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:1px; margin:6px 0 4px; background:var(--border); border:1px solid var(--border); }
.fact { background:var(--bg); padding:16px 18px; }
.fact-emoji { font-size:1.05rem; opacity:.8; }
.fact-value { font-family:'Fraunces',serif; font-weight:300; font-size:1.55rem;
    color:var(--text); margin-top:6px; }
.fact-label { color:var(--muted); font-size:.77rem; margin-top:2px; font-weight:300; }

/* Moments gallery */
.gallery { display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr));
    gap:16px; margin-top:10px; }
.moment { background:var(--panel); border:1px solid var(--border);
    border-radius:3px; overflow:hidden; }
.moment img { width:100%; aspect-ratio:4/3; object-fit:cover; display:block; }
.moment-body { padding:13px 15px; }
.moment-desc { color:#c7c7cc; font-size:.88rem; line-height:1.5; font-weight:300; }
.moment-buy { margin-top:10px; padding:9px 11px; border-radius:2px;
    background:var(--bg); border-left:2px solid var(--th,#5fa79a);
    font-size:.82rem; color:#a7a7ae; font-weight:300; }
.moment-buy b { color:var(--text); font-weight:500; }
.badge { display:inline-block; font-size:.64rem; font-weight:600; padding:2px 8px;
    border-radius:2px; letter-spacing:.08em; text-transform:uppercase; }
.moment-imgwrap { position:relative; line-height:0; display:block; cursor:zoom-in; }
.moment-price { position:absolute; top:9px; right:9px; background:rgba(14,14,17,.88);
    color:#fff; border:1px solid var(--accent); padding:3px 9px; border-radius:2px;
    font-size:.82rem; font-weight:600; letter-spacing:.02em; line-height:1.3; }
.moment-imgwrap::after { content:"⤢"; position:absolute; bottom:9px; right:9px;
    width:24px; height:24px; display:flex; align-items:center; justify-content:center;
    background:rgba(14,14,17,.82); color:#fff; border:1px solid var(--border);
    border-radius:2px; font-size:.82rem; opacity:0; transition:opacity .18s ease; }
.moment:hover .moment-imgwrap::after { opacity:.92; }

/* Click-to-enlarge lightbox — pure CSS via :target, no server reruns */
.lightbox { position:fixed; inset:0; z-index:9998; display:none; flex-direction:column;
    align-items:center; justify-content:center; padding:28px;
    background:rgba(6,6,8,.95); cursor:zoom-out; }
.lightbox:target { display:flex; }
.lightbox img { max-width:min(95vw,1100px); max-height:84vh; width:auto; height:auto;
    border-radius:3px; box-shadow:0 24px 70px rgba(0,0,0,.6); }
.lightbox .lb-cap { margin-top:15px; max-width:min(95vw,1100px); text-align:center;
    color:#c7c7cc; font-size:.86rem; font-weight:300; line-height:1.5; }
.lightbox .lb-cap b { color:#fff; font-weight:600; }
.lightbox .lb-cap .px { color:var(--accent); font-weight:600; }
.lightbox .lb-x { position:fixed; top:14px; right:22px; color:#fff; font-size:1.9rem;
    line-height:1; opacity:.7; text-decoration:none; }

/* Subtle hover — border only, no lift or shadow */
.finding, .moment { transition:border-color .18s ease; }
.finding:hover, .moment:hover { border-color:rgba(255,255,255,.2); }
.kpi-value, .fact-value, .chip b, .hero-title { font-variant-numeric:tabular-nums; }

/* Footer */
.foot { margin-top:48px; padding-top:20px; border-top:1px solid var(--border);
    color:var(--muted); font-size:.8rem; display:flex; justify-content:space-between;
    flex-wrap:wrap; gap:10px 24px; font-weight:300; letter-spacing:.01em; }
.foot .foot-r { color:#a7a7ae; }

/* Responsive */
@media (max-width:820px){
  .block-container { padding:1.2rem 1.1rem 2.6rem; }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.6rem !important; }
  [data-testid="stColumn"] { min-width:100% !important; flex:1 1 100% !important; }
  .hero-sub { font-size:.92rem; }
  .kpi-value { font-size:1.7rem; }
  [data-baseweb="tab-list"] { gap:18px; }
}
@media (max-width:480px){
  .kpi-grid { grid-template-columns:repeat(2,1fr); }
}
</style>
""", unsafe_allow_html=True)


inject_css()


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_spending() -> pd.DataFrame:
    path = DATA / "spending.csv"
    if not path.exists():
        path = SAMPLE / "sample_spending.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data
def load_json(name: str, default):
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


spend = load_spending()
photos = load_json("photos.json", [])
route = load_json("route.json", {"routes": {}, "visits": {}})
landmarks = load_json("landmarks.json", [])
meta = load_json("meta.json", {})

spend_by_id = {int(r.spend_id): r for r in spend.itertuples()}
airfare_total = float(spend.loc[spend.category == "Flights", "amount_usd"].sum())


# `work` drives all aggregates; the full log (incl. the flight) still shows in
# the Summary table. The one-off intra-trip flight is excluded from the analysis
# so it doesn't skew the daily-spend figures.
work = spend[spend.category != "Flights"]


# ── Derived figures ───────────────────────────────────────────────────────────
grand_total = float(spend.amount_usd.sum())   # whole-trip cost (always incl. flight)
jp_total = float(work.loc[work.country == "Japan", "amount_usd"].sum())
th_total = float(work.loc[work.country == "Thailand", "amount_usd"].sum())
tw_total = float(work.loc[work.country == "Taiwan", "amount_usd"].sum())
total = float(work.amount_usd.sum())
daily = work.groupby(work["date"].dt.date)["amount_usd"].sum()
jp_days = work.loc[work.country == "Japan", "date"].dt.date.nunique()
th_days = work.loc[work.country == "Thailand", "date"].dt.date.nunique()
matched = sum(1 for p in photos if p.get("matched_spend_id"))


def usd0(x: float) -> str:
    """Whole-dollar USD with round-half-up on exact cents, so the headline
    figures reconcile on screen. (Plain %.0f uses float/banker's rounding, which
    renders 3299.50 as "3,299" even though its rounded parts sum to 3,300.)"""
    return f"${(int(round(x * 100)) + 50) // 100:,}"


def _count(pattern: str) -> int:
    return int(work["description"].str.contains(
        pattern, case=False, regex=True, na=False).sum())


boba_n = _count(r"boba|milk tea|gong cha|ga/ ?ga|thai tea|bubble")
matcha_n = _count(r"matcha")
icecream_n = _count(r"ice ?cream")
conv_n = int((work.category == "Convenience Store").sum())
mcd_n = _count(r"mcdonald")
priciest = work.loc[work["amount_usd"].idxmax()]

FACTS = [
    ("🧋", boba_n, "boba / milk teas"),
    ("🍵", matcha_n, "matcha treats"),
    ("🍦", icecream_n, "ice creams"),
    ("🏪", conv_n, "konbini runs"),
    ("🍟", mcd_n, "McDonald's visits"),
    ("💥", f"${priciest.amount_usd:.0f}", "biggest single spend"),
]


# ── Key findings (auto-computed from the data) ────────────────────────────────
def _shop_share(country: str) -> float:
    ct = float(work.loc[work.country == country, "amount_usd"].sum())
    sh = float(work.loc[(work.country == country)
                        & (work.category == "Shopping"), "amount_usd"].sum())
    return sh / ct * 100 if ct else 0.0


jp_day = jp_total / jp_days if jp_days else 0
th_day = th_total / th_days if th_days else 0
pct_gap = abs(jp_day - th_day) / max(jp_day, th_day) * 100 if max(jp_day, th_day) else 0
on_ground = total  # `total` is the work (flights-excluded) sum
airfare_ratio = airfare_total / on_ground if on_ground else 0
_cat_tot = work.groupby("category")["amount_usd"].sum().sort_values(ascending=False)
_top_lm = landmarks[0] if landmarks else None

INSIGHTS = [
    ("✈️", f"<b>Getting there cost more than being there.</b> Airfare was "
           f"<b>${airfare_total:,.0f}</b> (two long-haul US↔Asia flights plus "
           f"the Japan→Thailand hop) against <b>${on_ground:,.0f}</b> spent on "
           f"the ground — roughly <b>{airfare_ratio:.1f}×</b> as much."),
    ("💸", f"On the ground the two legs were close: <b>${jp_day:.0f}/day in "
           f"Japan</b> vs <b>${th_day:.0f}/day in Thailand</b> "
           f"(~{pct_gap:.0f}% apart). The big gap in the raw totals was really "
           f"airfare, not day-to-day life."),
    ("🍜", f"<b>{escape(_cat_tot.index[0])}</b> was the largest on-the-ground "
           f"category at <b>${_cat_tot.iloc[0]:.0f}</b> — about "
           f"<b>{_cat_tot.iloc[0]/total*100:.0f}%</b> of on-the-ground spend."),
    ("🛍️", f"Souvenir shopping skewed heavily to Thailand: "
            f"<b>{_shop_share('Thailand'):.0f}%</b> of Thailand spend vs "
            f"<b>{_shop_share('Japan'):.0f}%</b> in Japan "
            f"(crocodile leather goods, COS, Muji)."),
]
if _top_lm:
    INSIGHTS.append(
        ("📸", f"<b>{escape(_top_lm['name'])}</b> was the single most-photographed "
               f"spot with <b>{_top_lm['photos_nearby']} photos</b> nearby — the "
               f"clear highlight of the Japan leg."))

# Story beats plotted on the spending timeline (dates from the log + itinerary).
MILESTONES = [
    ("2026-06-24", "Universal Studios"),
    ("2026-06-29", "Aquarium + book flight"),
    ("2026-07-01", "Fly → Bangkok"),
    ("2026-07-04", "Pattaya floating market"),
    ("2026-07-14", "Bangkok malls"),
    ("2026-07-19", "Fly home"),
]

dr = meta.get("date_range")
if dr:
    d0, d1 = date.fromisoformat(dr[0]), date.fromisoformat(dr[1])
    span_days = (d1 - d0).days + 1
    date_label = f"{d0.strftime('%b %d')} – {d1.strftime('%b %d, %Y')}"
else:
    span_days, date_label = jp_days + th_days, "the trip"


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  <div class="hero-kicker">{escape(date_label)} · Osaka → Bangkok</div>
  <div class="hero-title">Japan &amp; Thailand</div>
  <p class="hero-sub">A {span_days}-day trip, reconstructed from Google Maps
  location history, a hand-kept spending log, and {len(photos)} geotagged
  photos — with standout shots matched to the exact purchase they capture.</p>
  <div class="chips">
    <span class="chip"><b>{usd0(grand_total)}</b> all-in cost</span>
    <span class="chip"><b>{len(photos)}</b> geotagged photos</span>
    <span class="chip"><b>{len(landmarks)}</b> landmarks</span>
    <span class="chip"><b>2</b> countries · {span_days} days</span>
  </div>
</div>
""", unsafe_allow_html=True)


def kpi_grid(cards: list[tuple[str, str, str, str]]) -> None:
    html = ['<div class="kpi-grid">']
    for label, value, sub, accent in cards:
        html.append(
            f'<div class="kpi" style="--accent:{accent}">'
            f'<div class="kpi-label">{escape(label)}</div>'
            f'<div class="kpi-value">{value}</div>'
            f'<div class="kpi-sub">{escape(sub)}</div></div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def style_fig(fig, height=330, legend=False):
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", height=height,
        font=dict(family="Manrope, sans-serif", color="#9a9aa2", size=12),
        margin=dict(l=8, r=14, t=54, b=8), showlegend=legend,
        title=dict(font=dict(family="Manrope, sans-serif", size=12,
                             color="#87878f"), x=0.005, xanchor="left"),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.2,
                    font=dict(size=11)),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,.05)", zeroline=False,
                     linecolor="rgba(255,255,255,.09)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,.05)", zeroline=False,
                     linecolor="rgba(255,255,255,.09)")
    return fig


tab_map, tab_spend, tab_moments, tab_summary = st.tabs(
    ["Map", "Spending", "Caught Spending", "Summary"])


# ── Tab 1: Map ────────────────────────────────────────────────────────────────
def _popup_html(p: dict, idx: int | None = None) -> str:
    when = str(p.get("datetime") or p.get("date") or "").replace("T", " ")[:16]
    img = (f'<img src="data:image/jpeg;base64,{p["thumb_b64"]}" '
           f'style="width:230px;border-radius:8px;display:block">')
    # Wrap in a link to the in-map lightbox overlay (see _map_lightbox).
    if idx is not None and p.get("full_img"):
        img = (f'<a href="#mlb-{idx}" title="Enlarge" style="display:block;'
               f'position:relative;line-height:0;cursor:zoom-in">{img}'
               f'<span style="position:absolute;bottom:8px;right:8px;'
               f'background:rgba(14,14,17,.82);color:#fff;font-size:11px;'
               f'padding:2px 7px;border-radius:3px;font-family:Manrope,sans-serif">'
               f'⤢ Enlarge</span></a>')
    parts = [
        f'<div style="font-family:Manrope,sans-serif;width:230px">',
        img,
        f'<div style="font-size:11px;color:#8a8a8a;margin-top:5px">'
        f'{escape(when)} · {escape(p["country"])}</div>',
    ]
    if p.get("description"):
        parts.append(f'<div style="font-size:13px;color:#222;margin-top:3px">'
                     f'{escape(p["description"])}</div>')
    mid = p.get("matched_spend_id")
    if mid and int(mid) in spend_by_id:
        row = spend_by_id[int(mid)]
        sym = CURRENCY_SYMBOL.get(p["country"], "$")
        accent = COUNTRY_ACCENT.get(p["country"], TH)
        parts.append(
            f'<div style="margin-top:8px;padding:7px 9px;border-radius:4px;'
            f'background:rgba(0,0,0,.04);border-left:3px solid {accent}">'
            f'<div style="font-size:12px;color:#222;font-weight:600">'
            f'{escape(clean_label(str(row.description)))}</div>'
            f'<div style="font-size:15px;font-weight:800;color:{accent};'
            f'margin-top:2px">{sym}{row.amount_original:g}'
            f'<span style="font-size:11px;font-weight:500;color:#888"> '
            f'· ${row.amount_usd:.2f}</span></div></div>')
    parts.append("</div>")
    return "".join(parts)


def _purchase_icon(country: str) -> folium.DivIcon:
    """A round currency-symbol badge marking a photo that documents a purchase."""
    accent = COUNTRY_ACCENT.get(country, GOLD)
    sym = CURRENCY_SYMBOL.get(country, "$")
    fs = 13 if len(sym) <= 1 else 9
    html = (
        f'<div style="transform:translate(-50%,-50%);width:24px;height:24px;'
        f'display:flex;align-items:center;justify-content:center;background:{accent};'
        f'color:#0e0e11;border:2px solid #0e0e11;border-radius:50%;'
        f'font-family:Manrope,sans-serif;font-weight:800;font-size:{fs}px;'
        f'box-shadow:0 1px 5px rgba(0,0,0,.55)">{sym}</div>')
    return folium.DivIcon(html=html, icon_size=(0, 0), icon_anchor=(0, 0))


def _landmark_icon(lm: dict) -> folium.DivIcon:
    emoji = KIND_EMOJI.get(lm["kind"], "📍")
    accent = COUNTRY_ACCENT.get(lm["country"], GOLD)
    big = lm["photos_nearby"] >= 8
    count = (f'<span style="opacity:.7;font-weight:600"> · {lm["photos_nearby"]}📷</span>'
             if lm["photos_nearby"] else "")
    html = (
        f'<div style="display:flex;align-items:center;gap:5px;white-space:nowrap;'
        f'transform:translate(-6px,-50%);font-family:Manrope,sans-serif">'
        f'<span style="font-size:{18 if big else 15}px">{emoji}</span>'
        f'<span style="background:rgba(13,15,20,.82);color:#fff;'
        f'border:1px solid {accent};border-left:3px solid {accent};'
        f'padding:2px 8px;border-radius:8px;font-size:{12 if big else 11}px;'
        f'font-weight:{700 if big else 600}">{escape(lm["name"])}{count}</span></div>')
    return folium.DivIcon(html=html, icon_size=(0, 0), icon_anchor=(0, 0))


def _is_purchase(p: dict) -> bool:
    mid = p.get("matched_spend_id")
    return bool(mid) and int(mid) in spend_by_id


# Styles for the in-map lightbox. The image itself is set (lazily, on open) by
# the _LightboxIntoMap script — not by CSS — because the correct URL depends on
# the app's real base (Streamlit Cloud serves the component from a *different*
# origin, so a bare `/app/static/...` path would resolve to the wrong host).
_MAP_LB_CSS_HEAD = """<style>
.mlb{position:fixed;inset:0;z-index:100000;display:none;flex-direction:column;
  align-items:center;justify-content:center;background:rgba(6,6,8,.95);
  cursor:zoom-out;padding:20px;box-sizing:border-box;}
.mlb:target{display:flex;}
.mlb .pic{width:94vw;height:82vh;background-size:contain;background-position:center;
  background-repeat:no-repeat;filter:drop-shadow(0 18px 50px rgba(0,0,0,.6));}
.mlb .mcap{margin-top:12px;max-width:94vw;text-align:center;color:#d8d8dc;
  font:400 13px/1.5 Manrope,system-ui,sans-serif;}
.mlb .mcap b{color:#fff;font-weight:600;}
.mlb .mx{position:fixed;top:8px;right:16px;color:#fff;font-size:27px;line-height:1;
  text-decoration:none;opacity:.85;}
</style>"""


def _map_lightbox(plotted: list[dict]) -> str:
    """Full-screen click-to-enlarge overlays injected into the map document so a
    popup photo can be viewed large. Indices match _popup_html(p, idx).

    Each overlay carries `data-full` (the image's static path); the actual load
    happens on open via _LightboxIntoMap, which prefixes the app's true base URL.
    """
    boxes = ['<span id="mtop"></span>']
    for i, p in enumerate(plotted):
        if not p.get("full_img"):
            continue
        when = str(p.get("datetime") or p.get("date") or "").replace("T", " ")[:16]
        loc = f'{escape(when)} · {escape(p["country"])}'
        if _is_purchase(p):
            row = spend_by_id[int(p["matched_spend_id"])]
            sym = CURRENCY_SYMBOL.get(p["country"], "$")
            accent = COUNTRY_ACCENT.get(p["country"], TH)
            cap = (f'<b>{escape(clean_label(str(row.description), 44))}</b> · '
                   f'<span style="color:{accent}">{sym}{row.amount_original:g} · '
                   f'${row.amount_usd:.2f}</span> — {loc}')
        else:
            d = escape(p.get("description", "") or "")
            cap = (f'{d} — {loc}') if d else loc
        boxes.append(
            f'<a class="mlb" id="mlb-{i}" href="#mtop"><span class="mx">×</span>'
            f'<span class="pic" data-full="app/static/{p["full_img"]}"></span>'
            f'<span class="mcap">{cap}</span></a>')
    return _MAP_LB_CSS_HEAD + "".join(boxes)


class _LightboxIntoMap(MacroElement):
    """Wire up the in-map lightbox from inside st_folium's iframe.

    Runs via folium's script-macro, which — unlike a raw <body> <script> —
    executes inside the component iframe. It does two things:

    1. Reparents the overlays into the Leaflet container. The native Fullscreen
       API only paints the fullscreen element's subtree, so overlays left on
       <body> vanish in fullscreen; moving them into the container (the element
       that goes fullscreen) keeps them visible.
    2. Loads each full image on open, prefixing the app's real base URL. On
       Streamlit Cloud the component is served from a different origin than the
       app, so the base comes from the `streamlitUrl` param Streamlit passes into
       the component URL (falling back to an origin-absolute path locally).
    """
    _template = Template("""
        {% macro script(this, kwargs) %}
        (function(){
          var c = {{ this._parent.get_name() }}.getContainer();
          if(c){
            document.querySelectorAll('.mlb').forEach(function(b){ c.appendChild(b); });
            var t = document.getElementById('mtop'); if(t) c.appendChild(t);
          }
          var base = '/';
          try{ base = new URLSearchParams(window.location.search).get('streamlitUrl') || '/'; }catch(e){}
          if(base.slice(-1) !== '/') base += '/';
          function onhash(){
            var m = /^#mlb-(\\d+)$/.exec(window.location.hash || '');
            if(!m) return;
            var ov = document.getElementById('mlb-' + m[1]);
            var pic = ov && ov.querySelector('.pic');
            if(pic && !pic.style.backgroundImage){
              pic.style.backgroundImage = 'url("' + base + pic.getAttribute('data-full') + '")';
            }
          }
          window.addEventListener('hashchange', onhash);
          onhash();
        })();
        {% endmacro %}
    """)


def build_map(mode: str = "all") -> folium.Map:
    plotted = [p for p in photos if p["country"] in ("Japan", "Thailand", "Taiwan")]
    if mode == "purchases":
        plotted = [p for p in plotted if _is_purchase(p)]
    elif mode == "photos":
        plotted = [p for p in plotted if not _is_purchase(p)]
    if plotted:
        lats = [p["lat"] for p in plotted]
        lons = [p["lon"] for p in plotted]
        center = [sum(lats) / len(lats), sum(lons) / len(lons)]
    else:
        center = [15.87, 100.99]

    fmap = folium.Map(location=center, zoom_start=5, tiles="CartoDB dark_matter",
                      control_scale=True)
    Fullscreen(title="Fullscreen", title_cancel="Exit").add_to(fmap)

    th_route = route.get("routes", {}).get("Thailand", [])
    if th_route:
        fg = folium.FeatureGroup(name="🇹🇭 Thailand route", show=True).add_to(fmap)
        folium.PolyLine(th_route, color=TH, weight=2.5, opacity=.75,
                        tooltip="Thailand movement route (Timeline)").add_to(fg)

    idx_of = {id(p): i for i, p in enumerate(plotted)}
    for country in ("Japan", "Thailand", "Taiwan"):
        pts = [x for x in plotted if x["country"] == country]
        if not pts:
            continue
        cluster = MarkerCluster(name=f"📷 {country} photos").add_to(fmap)
        for p in pts:
            if _is_purchase(p):
                icon = _purchase_icon(country)
            else:
                icon = folium.Icon(color=COUNTRY_PIN[country], icon="camera",
                                   prefix="fa")
            folium.Marker(
                [p["lat"], p["lon"]],
                icon=icon,
                popup=folium.Popup(_popup_html(p, idx_of[id(p)]), max_width=250),
            ).add_to(cluster)

    if landmarks:
        lg = folium.FeatureGroup(name="⭐ Landmarks", show=True).add_to(fmap)
        for lm in landmarks:
            folium.Marker([lm["lat"], lm["lon"]], icon=_landmark_icon(lm),
                          zIndexOffset=1000).add_to(lg)

    heat = folium.FeatureGroup(name="🔥 Photo density", show=False).add_to(fmap)
    HeatMap([[p["lat"], p["lon"]] for p in plotted], radius=16, blur=22,
            min_opacity=0.35).add_to(heat)

    folium.LayerControl(collapsed=True, position="topright").add_to(fmap)

    # Click-to-enlarge overlays (indices align with the popup links above).
    if plotted:
        fmap.get_root().html.add_child(folium.Element(_map_lightbox(plotted)))
        _LightboxIntoMap().add_to(fmap)  # keep overlays visible in fullscreen

    # Frame both countries on load so Osaka and Bangkok/Pattaya are both visible.
    if plotted:
        fmap.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]],
                        padding=(30, 30))
    return fmap


with tab_map:
    if not photos:
        st.warning("No photo data found. Run `python build_dataset.py` first.")
    else:
        n_jp = sum(1 for p in photos if p["country"] == "Japan")
        n_th = sum(1 for p in photos if p["country"] == "Thailand")
        st.markdown(f"""
<div class="note">
  <div class="note-title">Why Japan looks different from Thailand</div>
  <p>I travelled Japan <b>without a SIM card</b>, so Google Maps Timeline
  recorded almost no location data there — which is why there's <b>no movement
  route across Japan</b> and every Japan pin (<span style="color:{JP}">●</span>
  {n_jp} photos) comes purely from <b>photo GPS</b>. In Thailand I used a local
  eSIM, so the full Timeline route is traced in <b style="color:{TH}">teal</b>
  and there are {n_th} geotagged photos (<span style="color:{TH}">●</span>).
  Landmarks like Osaka Castle, Kaiyukan Aquarium and the Bangkok malls are
  ⭐-marked and labelled with how many photos I took nearby. The Taiwan layover
  on the way home is up north (<span style="color:{TW}">●</span> purple). Use the
  ⛶ button (top-left) for true fullscreen.</p>
</div>""", unsafe_allow_html=True)
        n_buy = sum(1 for p in photos if _is_purchase(p))
        VIEWS = {
            f"All photos": "all",
            f"Purchases only ({n_buy})": "purchases",
            f"Photos only (no purchases)": "photos",
        }
        choice = st.radio("Map view", list(VIEWS), horizontal=True,
                          label_visibility="collapsed", key="mapview")
        mode = VIEWS[choice]
        st.caption("Purchase photos carry a ¥ / ฿ / NT$ pin; plain snapshots keep "
                   "the camera pin. Click any pin for the photo, time, and — for a "
                   "purchase — what it cost; click the photo to enlarge it.")
        st_folium(build_map(mode), use_container_width=True, height=820,
                  returned_objects=[], key=f"tripmap_{mode}")


# ── Tab 2: Spending ───────────────────────────────────────────────────────────
with tab_spend:
    st.markdown('<div class="sec">Key findings</div>', unsafe_allow_html=True)
    fh = ['<div class="findings">']
    for ico, txt in INSIGHTS:
        fh.append(f'<div class="finding"><div class="finding-ico">{ico}</div>'
                  f'<div class="finding-txt">{txt}</div></div>')
    fh.append("</div>")
    st.markdown("".join(fh), unsafe_allow_html=True)

    kpi_grid([
        ("On the ground", usd0(total), "Japan + Thailand + Taiwan", GOLD),
        ("Japan", usd0(jp_total), f"${jp_total/jp_days:,.0f}/day · {jp_days} days", JP),
        ("Thailand", usd0(th_total), f"${th_total/th_days:,.0f}/day · {th_days} days", TH),
        ("Taiwan", usd0(tw_total), "airport layover home", TW),
        ("Airfare", usd0(airfare_total), "2 long-haul + Japan→Thailand", "#c084fc"),
        ("All-in trip cost", usd0(grand_total), "on the ground + airfare", "#7aa2ff"),
    ])
    st.caption("Cards reconcile: Japan + Thailand + Taiwan = **on the ground**, and "
               "on the ground + airfare = **all-in**. Airfare is a separate travel "
               "cost and is **excluded** from the per-day and per-category charts "
               "below, which cover on-the-ground spending only.")

    # ── The journey: an annotated daily-spend timeline (the narrative) ────────
    st.markdown('<div class="sec">The journey, day by day</div>',
                unsafe_allow_html=True)
    st.caption("On-the-ground spend per day, coloured by country — annotated "
               "with the trip's turning points. You can read the whole three "
               "weeks left to right: theme parks in Osaka, the flight south, "
               "then markets and malls around Bangkok.")
    dc = (work.groupby([work["date"].dt.date, "country"])["amount_usd"]
          .sum().reset_index())
    dc.columns = ["date", "country", "amount_usd"]
    dc["date"] = pd.to_datetime(dc["date"])
    fig = px.area(dc, x="date", y="amount_usd", color="country",
                  color_discrete_map=COUNTRY_ACCENT)
    fig.update_traces(line=dict(width=1.4))
    for mdate, label in MILESTONES:
        x = pd.Timestamp(mdate)
        fig.add_vline(x=x, line_width=1, line_dash="dot",
                      line_color="rgba(255,255,255,.22)")
        fig.add_annotation(x=x, y=1.0, yref="paper", yanchor="bottom",
                           xanchor="left", xshift=4, text=label, showarrow=False,
                           font=dict(size=10, color="#8f8f97"))
    fig.update_yaxes(title="USD")
    fig.update_xaxes(title=None)
    st.plotly_chart(style_fig(fig, height=380, legend=True), width="stretch",
                    config=PLOTLY_CONFIG)

    r1c1, r1c2 = st.columns(2)
    by_country = (work.groupby("country", as_index=False)["amount_usd"].sum()
                  .sort_values("amount_usd", ascending=False))
    fig = px.bar(by_country, x="country", y="amount_usd", color="country",
                 color_discrete_map=COUNTRY_ACCENT, text_auto="$.0f",
                 title="Total spend by country")
    fig.update_traces(marker_line_width=0, textposition="outside")
    fig.update_yaxes(title="USD")
    fig.update_xaxes(title=None)
    r1c1.plotly_chart(style_fig(fig), width="stretch", config=PLOTLY_CONFIG)

    by_cat = (work.groupby("category", as_index=False)["amount_usd"].sum()
              .sort_values("amount_usd", ascending=False))
    fig = px.pie(by_cat, names="category", values="amount_usd", hole=.58,
                 color="category", color_discrete_map=CAT_COLORS,
                 title="Spend by category")
    fig.update_traces(textposition="outside", textinfo="label+percent",
                      marker=dict(line=dict(color=INK, width=2)))
    r1c2.plotly_chart(style_fig(fig, legend=False), width="stretch", config=PLOTLY_CONFIG)

    r2c1, r2c2 = st.columns(2)
    cc = (work[work.country.isin(["Japan", "Thailand"])]
          .groupby(["category", "country"], as_index=False)["amount_usd"].sum())
    order = (cc.groupby("category")["amount_usd"].sum()
             .sort_values(ascending=False).index.tolist())
    fig = px.bar(cc, x="category", y="amount_usd", color="country",
                 barmode="group", color_discrete_map=COUNTRY_ACCENT,
                 category_orders={"category": order},
                 title="Japan vs Thailand, by category")
    fig.update_yaxes(title="USD")
    fig.update_xaxes(title=None)
    r2c1.plotly_chart(style_fig(fig, legend=True), width="stretch", config=PLOTLY_CONFIG)

    top10 = work.nlargest(10, "amount_usd").sort_values("amount_usd")
    top10["label"] = top10["description"].map(lambda t: clean_label(t, 30))
    fig = px.bar(top10, x="amount_usd", y="label", orientation="h",
                 color="country", color_discrete_map=COUNTRY_ACCENT,
                 text_auto="$.0f", title="Top 10 single purchases")
    fig.update_traces(textposition="outside")
    fig.update_yaxes(title=None)
    fig.update_xaxes(title="USD")
    r2c2.plotly_chart(style_fig(fig, legend=False), width="stretch", config=PLOTLY_CONFIG)


# ── Tab 3: Caught Spending (photo → purchase matches) ─────────────────────────
CUR_SYM = {"JPY": "¥", "THB": "฿", "USD": "$", "NTD": "NT$"}


@st.fragment
def _render_gallery(items: list[dict]) -> None:
    """Gallery grid + a pure-CSS lightbox per photo.

    Isolated in a fragment so its ~17 MB of full-size images isn't re-sent to
    the browser every time an unrelated widget (e.g. the map filter) reruns.
    """
    cards = ['<span id="gtop"></span>', '<div class="gallery">']
    boxes = []
    for i, p in enumerate(items):
        row = spend_by_id[int(p["matched_spend_id"])]
        accent = COUNTRY_ACCENT.get(p["country"], TH)
        desc = escape(p.get("description", "") or "")
        buy = escape(clean_label(str(row.description), 44))
        sym = CUR_SYM.get(str(row.currency), "")
        price_tag = escape(f"{sym}{row.amount_original:g}")
        # Full-size image served lazily from ./static; fall back to the thumb.
        full = f'app/static/{p["full_img"]}' if p.get("full_img") \
            else f'data:image/jpeg;base64,{p["thumb_b64"]}'
        cards.append(
            f'<div class="moment" style="--th:{accent}">'
            f'<a class="moment-imgwrap" href="#lb-{i}">'
            f'<img src="data:image/jpeg;base64,{p["thumb_b64"]}" loading="lazy">'
            f'<span class="moment-price">{price_tag}</span></a>'
            f'<div class="moment-body">'
            f'<div class="moment-desc">{desc}</div>'
            f'<div class="moment-buy"><b>{buy}</b>'
            f'<br>{row.amount_original:g} {escape(str(row.currency))} · '
            f'${row.amount_usd:.2f} USD</div>'
            f'</div></div>')
        boxes.append(
            f'<a class="lightbox" id="lb-{i}" href="#gtop">'
            f'<span class="lb-x">×</span>'
            f'<img src="{full}" loading="lazy">'
            f'<span class="lb-cap"><b>{buy}</b> · '
            f'<span class="px" style="color:{accent}">{price_tag} '
            f'· ${row.amount_usd:.2f}</span>'
            f'{(" — " + desc) if desc else ""}</span></a>')
    cards.append("</div>")
    # st.html (not st.markdown): markdown parsing escapes ~half of a large HTML
    # blob into literal text; st.html injects it raw so all cards become elements.
    st.html("".join(cards) + "".join(boxes))


with tab_moments:
    st.markdown('<div class="sec">Caught spending — photos matched to what they cost</div>',
                unsafe_allow_html=True)
    matches = sorted(
        (p for p in photos if p.get("matched_spend_id")
         and int(p["matched_spend_id"]) in spend_by_id),
        key=lambda p: p.get("datetime") or p.get("date") or "")

    if not matches:
        st.markdown("""
<div class="note"><div class="note-title">No photo→purchase matches yet</div>
<p>Photos are matched to purchases by hand in <b>data/matches.csv</b> — each row
links a photo to the exact item it shows (a matcha-ice-cream photo to the
matcha-ice-cream line). Add matches there and run
<b>python build_dataset.py</b>, then refresh.</p></div>
""", unsafe_allow_html=True)
    else:
        st.caption(f"{len(matches)} photos matched to the exact purchase they "
                   "show — the trip as a visual receipt. Click any photo to enlarge.")
        _render_gallery(matches[:120])


# ── Tab 4: Summary ────────────────────────────────────────────────────────────
with tab_summary:
    top_cat = work.groupby("category")["amount_usd"].sum().idxmax()
    kpi_grid([
        ("Days in Japan", str(jp_days), "Osaka & around", JP),
        ("Days in Thailand", str(th_days), "Bangkok & Pattaya", TH),
        ("Geotagged photos", str(len(photos)), f"{matched} matched to a purchase", GOLD),
        ("Spending entries", str(len(spend)), f"top category: {top_cat}", "#f472b6"),
        ("Avg/day · Japan", f"${jp_total/jp_days:,.0f}" if jp_days else "—", "per active day", JP),
        ("Avg/day · Thailand", f"${th_total/th_days:,.0f}" if th_days else "—", "per active day", TH),
    ])

    st.markdown('<div class="sec">Trip in numbers</div>', unsafe_allow_html=True)
    facts_html = ['<div class="facts">']
    for emoji, value, label in FACTS:
        facts_html.append(
            f'<div class="fact"><div class="fact-emoji">{emoji}</div>'
            f'<div class="fact-value">{escape(str(value))}</div>'
            f'<div class="fact-label">{escape(label)}</div></div>')
    facts_html.append("</div>")
    st.markdown("".join(facts_html), unsafe_allow_html=True)

    st.markdown('<div class="sec">Every purchase</div>', unsafe_allow_html=True)
    st.caption("Sortable — click a column header. Four currencies, converted to "
               "USD at fixed trip rates (155 JPY / 35 THB / 32 NTD per USD).")
    table = spend[["date", "country", "category", "description",
                   "amount_original", "currency", "amount_usd"]].copy()
    table["date"] = table["date"].dt.date
    table["description"] = table["description"].map(lambda t: clean_label(t, 56))
    st.dataframe(
        table, width="stretch", hide_index=True, height=460,
        column_config={
            "date": "Date", "country": "Country", "category": "Category",
            "description": "Item",
            "amount_original": st.column_config.NumberColumn("Local", format="%.2f"),
            "currency": "Cur",
            "amount_usd": st.column_config.NumberColumn("USD", format="$%.2f"),
        })


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="foot">'
    '<div>Japan &amp; Thailand · a personal-data analysis '
    '(Google Timeline · spending log · photo GPS)</div>'
    '<div class="foot-r">Built by Ryan Mathew — Data Visualization, UW Bothell</div>'
    '</div>', unsafe_allow_html=True)

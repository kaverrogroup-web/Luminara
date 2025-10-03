# streamlit_app.py
import streamlit as st
from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterable, Tuple

# ================= App Config =================
st.set_page_config(
    page_title="Luminara",
    page_icon="🪐",
    layout="wide",
)

# ---------------- Utilities ----------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def section_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)

# ================= Global Theme (light + forest accents) =================
st.markdown("""
<style>
/* App base */
.stApp {
  background: #f8f9fa;  /* very light gray */
  color: #1c1c1c;
  font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans", "Liberation Sans", "Apple Color Emoji","Segoe UI Emoji";
}
h1,h2,h3,h4 { color:#1c1c1c; }

/* Accent palette */
:root {
  --accent-deep: #0f5132;     /* deep forest green */
  --accent:      #2e7d6b;     /* primary buttons */
  --accent-soft: #e9f2ee;     /* very soft green */
  --border:      #e6eaee;     /* soft borders */
}

/* -------- Sidebar (light, tab-like list) -------- */
section[data-testid="stSidebar"] {
  background: #ffffff;
  border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] .block-container { padding-top: .9rem; }

/* Radio -> list items (hide dots, style rows) */
section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] input { display:none; }
section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] label {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 12px;
  padding: 10px 12px;
  margin: 3px 2px;
  cursor: pointer;
  display: block;
  transition: background .12s, border-color .12s, box-shadow .12s;
}
section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] label:hover {
  background: #f3f4f6;
  border-color: var(--border);
}
/* Active tab pill (Streamlit adds data-selected="true" on the label) */
section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] label[data-selected="true"] {
  background: #ffffff;
  border: 1px solid #e9edf1;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}

/* Sidebar headings */
.st-sidebar-title { font-weight:700; letter-spacing:.2px; font-size:1.05rem; margin-bottom:.3rem; }
.st-sidebar-caption { color:#6b7280; margin-bottom:.65rem; }

/* Divider */
hr { border:none; border-top:1px solid #edf0f2; }

/* -------- Bento grid + cards (applies across all pages) -------- */
.bento-row { margin: 8px 0 14px 0; }

/* First child in each column -> card */
.bento-row [data-testid="column"] > div:first-child {
  background: #ffffff;
  border-radius: 14px;
  padding: 16px 16px 14px 16px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
  border: 1px solid #eef0f3;
}

/* Card internals */
.bento-row h2, .bento-row h3, .bento-row h4 { margin: 0 0 10px 0; }
.bento-row p { margin: 0; }
.bento-row hr { border: none; border-top: 1px solid #edf0f2; margin: 10px 0 12px 0; width: 100%; }

/* Metrics accent inside cards */
.bento-row [data-testid="stMetricValue"] { color: var(--accent-deep); font-weight: 700; }

/* Tables in cards */
.bento-row table tr:nth-child(even) { background: #fafbfc; }
.bento-row table { border-radius: 8px; overflow: hidden; }

/* Buttons (primary) */
.stButton>button {
  background-color: var(--accent);
  color: #fff;
  border-radius: 10px;
  border: none;
  padding: 0.55rem 0.9rem;
}
.stButton>button:hover { background-color: #266a5b; }

/* Inputs */
.stTextInput input, .stDateInput input, .stSelectbox div, .stNumberInput input {
  border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# ================= Ephemeris helpers (stubbed; ready to wire) =================
try:
    from skyfield.api import load  # make sure skyfield is in requirements.txt
except Exception:
    load = None

@st.cache_resource(show_spinner=False)
def get_ephemeris():
    """Load small JPL ephemeris (cached)."""
    if load is None:
        return None, None
    return load("de421.bsp"), load.timescale()

def wrap_angle_deg(x: float) -> float:
    return x % 360.0

def min_angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)

def nearest_target_delta(angle: float, targets: Iterable[float]) -> Tuple[float, float]:
    best = (9999.0, None)
    for t in targets:
        d = min_angle_diff(angle, t)
        if d < best[0]:
            best = (d, t)
    return best  # (diff, target)

# ================= Sidebar (text-only, tab-like) =================
PAGES = ["Dashboard", "Planet Pairs", "Backlog", "Settings", "About"]
if "page" not in st.session_state:
    st.session_state.page = PAGES[0]

with st.sidebar:
    st.markdown('<div class="st-sidebar-title">Luminara</div>', unsafe_allow_html=True)
    st.markdown('<div class="st-sidebar-caption">Astro-financial analytics</div>', unsafe_allow_html=True)
    page_choice = st.radio("", PAGES, index=PAGES.index(st.session_state.page), key="__menu__")
    st.markdown("---")
    st.caption(f"UTC: {utc_now_iso()}")

page = page_choice
st.session_state.page = page

# ================= Pages (all bento-styled) =================
if page == "Dashboard":
    st.title("Luminara")
    st.caption("Astro-financial analytics dashboard")

    # ---------- BENTO ROW 1: [8 | 4] ----------
    st.markdown('<div class="bento-row">', unsafe_allow_html=True)
    c1, c2 = st.columns([8, 4], gap="small")

    with c1:
        box = st.container()
        with box:
            st.subheader("Overview")
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Upcoming hits", 3)
            with m2: st.metric("Active pairs", 5)
            with m3: st.metric("Watch window", "7–21d")
            st.markdown("<hr/>", unsafe_allow_html=True)
            st.write("Recent timing signals (sample)")
            st.table(
                [{"Date (UTC)": "2025-10-03", "Pair": "Sun–Moon", "Angle": "90°", "Orb": "0.2°"},
                 {"Date (UTC)": "2025-10-06", "Pair": "Venus–Saturn", "Angle": "120°", "Orb": "0.8°"},
                 {"Date (UTC)": "2025-10-11", "Pair": "Mars–Jupiter", "Angle": "60°", "Orb": "0.5°"}]
            )

    with c2:
        box = st.container()
        with box:
            st.subheader("Next harmonics")
            st.write("Nearest matching angles in the next 30 days (sample).")
            st.table(
                [{"When (UTC)": "Oct 03 14:00", "Pair": "Sun–Moon", "Angle": "90°", "Δ": "0.2°"},
                 {"When (UTC)": "Oct 07 09:30", "Pair": "Mercury–Mars", "Angle": "45°", "Δ": "0.4°"},
                 {"When (UTC)": "Oct 12 18:15", "Pair": "Jupiter–Saturn", "Angle": "120°", "Δ": "0.7°"}]
            )
    st.markdown("</div>", unsafe_allow_html=True)

    # ---------- BENTO ROW 2: [5 | 7] ----------
    st.markdown('<div class="bento-row">', unsafe_allow_html=True)
    c3, c4 = st.columns([5, 7], gap="small")

    with c3:
        box = st.container()
        with box:
            st.subheader("Your notes")
            st.write("Quick scratchpad for ideas (not persisted yet).")
            st.text_area("Notes", placeholder="Observations, hypotheses, to-dos…",
                         label_visibility="collapsed", height=140)

    with c4:
        box = st.container()
        with box:
            st.subheader("Watchlist (sample)")
            st.table(
                [{"Asset": "XAUUSD", "Focus pair": "Sun–Moon",     "Angles": "0, 90, 180", "Window": "Action"},
                 {"Asset": "ES",     "Focus pair": "Venus–Saturn", "Angles": "60, 120",    "Window": "Watch"},
                 {"Asset": "BTCUSD", "Focus pair": "Mars–Jupiter", "Angles": "45, 135",    "Window": "Radar"}]
            )
    st.markdown("</div>", unsafe_allow_html=True)

    st.caption(f"**UTC:** {utc_now_iso()}")

elif page == "Planet Pairs":
    st.title("Planet Pairs")
    st.caption("Find upcoming harmonic angles between two planets (geocentric tropical).")

    # ---------- BENTO ROW 1: Controls card ----------
    st.markdown('<div class="bento-row">', unsafe_allow_html=True)
    c1 = st.columns([12], gap="small")[0]
    with c1:
        card = st.container()
        with card:
            st.subheader("Parameters")
            r1c1, r1c2, r1c3, r1c4 = st.columns([1,1,1,2])
            with r1c1:
                planet1 = st.selectbox("Planet 1",
                    ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Uranus","Neptune","Pluto"])
            with r1c2:
                planet2 = st.selectbox("Planet 2",
                    ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Uranus","Neptune","Pluto"], index=1)
            with r1c3:
                frame = st.selectbox("Frame",
                    ["Geocentric / Ecliptic (Tropical)", "Heliocentric / Ecliptic", "Geocentric / Right Ascension"], index=0)
            with r1c4:
                angles = st.multiselect("Harmonic Angles (deg)",
                    [0,30,45,60,72,90,120,135,144,150,180,225,240,270,315,330,360],
                    default=[0,60,90,120,180])

            r2c1, r2c2, r2c3 = st.columns(3)
            with r2c1:
                start_date = st.date_input("Start date (UTC)", value=datetime.utcnow().date())
            with r2c2:
                end_date   = st.date_input("End date (UTC)",
                                           value=datetime.utcnow().date().replace(year=datetime.utcnow().year + 1))
            with r2c3:
                orb = st.number_input("Orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)

            st.markdown("<hr/>", unsafe_allow_html=True)
            run = st.button("Compute")

    st.markdown("</div>", unsafe_allow_html=True)

    # ---------- BENTO ROW 2: Results card ----------
    st.markdown('<div class="bento-row">', unsafe_allow_html=True)
    c2 = st.columns([12], gap="small")[0]
    with c2:
        card = st.container()
        with card:
            st.subheader("Results")
            if run:
                st.info("Computation engine not wired yet. Next step: integrate Skyfield ephemerides and search for hits.")
                st.code(
                    f"""Params:
- Planet 1: {planet1}
- Planet 2: {planet2}
- Frame:    {frame}
- Angles:   {angles}
- Orb:      ±{orb}°
- Range:    {start_date} → {end_date} (UTC)""",
                    language="yaml",
                )
            else:
                st.write("Configure parameters above and press **Compute** to scan for harmonic hits.")
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Backlog":
    st.title("Backlog")
    st.caption("Log which assets reacted on which harmonic dates—build your private knowledge base.")

    # ---------- BENTO ROW: [Form | Recent] ----------
    st.markdown('<div class="bento-row">', unsafe_allow_html=True)
    left, right = st.columns([6,6], gap="small")

    with left:
        card = st.container()
        with card:
            st.subheader("New entry")
            st.info("Storage not wired yet; this is a mock to shape the UX.")
            with st.form("log_form", clear_on_submit=True):
                asset = st.text_input("Asset / Symbol", placeholder="e.g., XAUUSD")
                date  = st.date_input("Event date (UTC)")
                planets = st.text_input("Planet Pair / Pattern", placeholder="e.g., Sun–Moon 90°")
                note  = st.text_area("Notes", placeholder="What happened? Reaction type/strength? Price context?")
                submitted = st.form_submit_button("Add entry")
            if submitted:
                st.success("Entry captured (mock). Next: wire to SQLite using SQLAlchemy.")

    with right:
        card = st.container()
        with card:
            st.subheader("Recent entries")
            st.caption("This will show your persisted backlog once storage is wired.")
            st.table([{"Date (UTC)": "—", "Asset": "—", "Pattern": "—", "Notes": "—"}])

    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Settings":
    st.title("Settings")
    st.caption("App-wide configuration")

    # ---------- BENTO ROW: [Defaults | Time & locale] ----------
    st.markdown('<div class="bento-row">', unsafe_allow_html=True)
    a, b = st.columns([6,6], gap="small")

    with a:
        card = st.container()
        with card:
            st.subheader("Computation defaults")
            st.selectbox("Coordinate system",
                ["Geocentric / Tropical (recommended)", "Heliocentric", "Geocentric / Right Ascension"], index=0)
            st.number_input("Default orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
            st.multiselect("Default harmonic angles",
                [0,30,45,60,72,90,120,135,144,150,180,225,240,270,315,330,360],
                default=[0,60,90,120,180])

    with b:
        card = st.container()
        with card:
            st.subheader("Time & locale")
            st.selectbox("Display timezone", ["UTC (recommended)"], index=0,
                help="All calculations are done in UTC; display can localize later.")

    # ---------- BENTO ROW: [Data sources] ----------
    st.markdown('<div class="bento-row">', unsafe_allow_html=True)
    c = st.columns([12], gap="small")[0]
    with c:
        card = st.container()
        with card:
            st.subheader("Data sources")
            st.markdown("- Ephemerides: **Skyfield** with JPL DE files")
            st.markdown("- Price data (optional): discuss integrations (Polygon.io, Alpha Vantage, Binance)")
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "About":
    st.title("About Luminara")

    # ---------- Single card ----------
    st.markdown('<div class="bento-row">', unsafe_allow_html=True)
    full = st.columns([12], gap="small")[0]
    with full:
        card = st.container()
        with card:
            st.subheader("What is Luminara?")
            st.markdown(
                """
                **Luminara** helps traders analyze planetary cycles and harmonic angles
                to anticipate timing clusters. Built with Streamlit and Skyfield.

                **Roadmap**:
                1. Skyfield engine for geocentric tropical angles (UTC).
                2. Scanners for multi-angle hits + clustering and scoring.
                3. Backlog persistence + dashboard analytics.
                4. Optional price-data overlays & alerts.
                """
            )
    st.markdown("</div>", unsafe_allow_html=True)

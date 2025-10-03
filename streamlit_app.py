# streamlit_app.py

# ---------- Imports ----------
from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterable, Tuple
import math

import pandas as pd
import streamlit as st
from skyfield.api import load, Loader

# ---------- App Config ----------
st.set_page_config(
    page_title="Luminara",
    page_icon=":milky_way:",
    layout="wide",
)

# ---------- CSS (light app + light sidebar + list-style menu) ----------
st.markdown(
    """
    <style>
      /* App base */
      .stApp {
        background-color: #f8f9fa;   /* light background */
        color: #1c1c1c;
        font-family: Inter, ui-sans-serif, system-ui, Segoe UI, Roboto, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji;
      }

      /* Sidebar container (light) */
      section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e6e6e6;
      }

      /* Sidebar header: app title & caption (we remove any left-over image space) */
      section[data-testid="stSidebar"] .block-container {
        padding-top: 1.1rem;
      }

      /* Remove any accidental sidebar image spacing */
      section[data-testid="stSidebar"] img {
        display: none !important;
      }

      /* App title in sidebar */
      .lumi-title {
        font-weight: 700;
        letter-spacing: 0.2px;
        font-size: 1.1rem;
        margin-bottom: 0.35rem;
      }
      .lumi-sub {
        color: #6b7280;
        font-size: 0.9rem;
        margin-bottom: 0.75rem;
      }

      /* Divider in sidebar */
      .lumi-div {
        height: 1px;
        background: #e6e6e6;
        margin: 0.6rem 0 0.8rem 0;
      }

      /* ---- List-style menu (built with radio) ---- */
      /* Hide default radio dots */
      div[role="radiogroup"] > label span:first-child {
        display: none !important;
      }
      /* Make each item look like a menu row */
      div[role="radiogroup"] > label {
        width: 100%;
        border-radius: 10px;
        padding: 0.65rem 0.7rem;
        margin-bottom: 0.25rem;
        border: 1px solid transparent;
        cursor: pointer;
        background: transparent;
        display: block;
      }
      /* Text in menu item */
      div[role="radiogroup"] > label p {
        margin: 0;
        font-weight: 500;
        color: #1c1c1c;
      }
      /* Hover */
      div[role="radiogroup"] > label:hover {
        background: #f3f4f6;
        border-color: #e6e6e6;
      }
      /* Active (checked) */
      div[role="radiogroup"] > label[data-checked="true"] {
        background: #e9f2ee;             /* light forest green wash */
        border-color: #d3e7de;
      }
      div[role="radiogroup"] > label[data-checked="true"] p {
        color: #104b3f;                   /* deep forest text */
        font-weight: 600;
      }

      /* Metrics accent */
      [data-testid="stMetricValue"] {
        color: #0f6b58;                   /* forest green */
        font-weight: 700;
      }

      /* Buttons (primary) */
      .stButton>button {
        background-color: #2e7d6b;
        color: #fff;
        border-radius: 10px;
        border: none;
        padding: 0.55rem 0.8rem;
      }
      .stButton>button:hover {
        background-color: #266a5b;
      }

      /* Inputs */
      .stTextInput input, .stDateInput input, .stSelectbox div, .stNumberInput input {
        border-radius: 8px !important;
      }

      /* Tables */
      .stTable {
        border: 1px solid #e6e6e6;
        border-radius: 8px;
        overflow: hidden;
      }
      .stTable table tr:nth-child(even) {
        background: #fafafa;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Small UI helpers ----------
def section_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# ---------- Ephemeris helpers (Skyfield / geocentric tropical ecliptic) ----------
@st.cache_resource(show_spinner=False)
def get_ephemeris():
    # Skyfield caches ephemerides under ~/.skyfield in the Streamlit environment
    return load("de421.bsp"), load.timescale()

def _is_bary(name: str) -> bool:
    return "barycenter" in name

def _planet_key(name: str) -> str:
    n = name.lower()
    mapping = {
        "sun": "sun",
        "moon": "moon",
        "mercury": "mercury",
        "venus": "venus",
        "mars": "mars",
        "jupiter": "jupiter barycenter",
        "saturn": "saturn barycenter",
        "uranus": "uranus barycenter",
        "neptune": "neptune barycenter",
        "pluto": "pluto barycenter",
    }
    return mapping.get(n, n)

@lru_cache(maxsize=256)
def _planet_obj(name_lower: str):
    eph, _ = get_ephemeris()
    key = _planet_key(name_lower)
    body = eph[key]
    if _is_bary(key):
        body = body.planet
    return body

def wrap_angle_deg(x: float) -> float:
    return x % 360.0

def min_angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)

def geo_ecliptic_longitude_deg(planet_name: str, t):
    eph, ts = get_ephemeris()
    earth = eph["earth"]
    body = _planet_obj(planet_name.lower())
    app = earth.at(t).observe(body).apparent()
    lon, lat, dist = app.ecliptic_latlon()
    return wrap_angle_deg(lon.degrees)

# ---------- Sidebar (light, list-style) ----------
# App title (no image)
with st.sidebar:
    st.markdown('<div class="lumi-title">Luminara</div>', unsafe_allow_html=True)
    st.markdown('<div class="lumi-sub">Astro-financial analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="lumi-div"></div>', unsafe_allow_html=True)

PAGES = ["Dashboard", "Planet Pairs", "Backlog", "Settings", "About"]

# keep session page
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

with st.sidebar:
    menu_choice = st.radio(
        "MENU",
        PAGES,
        index=PAGES.index(st.session_state.page),
        label_visibility="collapsed",
    )
    st.session_state.page = menu_choice

    st.markdown('<div class="lumi-div"></div>', unsafe_allow_html=True)
    st.caption(f"UTC: {utc_now_iso()}")

# ---------- Routing ----------
if st.session_state.page == "Dashboard":
    st.title("Luminara")
    st.caption("Astro-financial analytics dashboard")

    section_header("Status")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Ephemeris", "Skyfield + JPL", help="High-precision ephemerides")
    with col2:
        st.metric("Coordinate System", "Geocentric / Tropical", help="Default for timing")
    with col3:
        st.metric("Time Basis", "UTC", help="All calculations in UTC, display can localize")

    st.divider()
    section_header("Quick Start", "What you can do next")
    st.markdown(
        """
        - Go to **Planet Pairs** to explore harmonic angles between any two bodies.  
        - Use **Backlog** to log which assets react to which harmonics.  
        - Configure defaults in **Settings** (timezone, angle sets, orbs, catalogs).
        """
    )

elif st.session_state.page == "Planet Pairs":
    st.title("Planet Pairs")
    st.caption("Find upcoming harmonic angles between two planets (geocentric tropical).")

    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        planet1 = st.selectbox("Planet 1", ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Uranus","Neptune","Pluto"])
    with c2:
        planet2 = st.selectbox("Planet 2", ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Uranus","Neptune","Pluto"], index=1)
    with c3:
        frame = st.selectbox(
            "Frame",
            ["Geocentric / Ecliptic (Tropical)", "Heliocentric / Ecliptic", "Geocentric / Right Ascension"],
            index=0
        )
    with c4:
        angles = st.multiselect(
            "Harmonic Angles (deg)",
            [0, 30, 45, 60, 72, 90, 120, 135, 144, 150, 180, 225, 240, 270, 315, 330, 360],
            default=[0, 60, 90, 120, 180],
        )

    lo, hi, orb_col = st.columns([1,1,1])
    with lo:
        start_date = st.date_input("Start date (UTC)", value=datetime.utcnow().date())
    with hi:
        end_date = st.date_input("End date (UTC)", value=datetime.utcnow().date().replace(year=datetime.utcnow().year + 1))
    with orb_col:
        orb = st.number_input("Orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)

    st.divider()
    if st.button("Compute"):
        st.info("Computation engine not wired yet. Next step is to integrate Skyfield ephemerides and search for hits.")
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

elif st.session_state.page == "Backlog":
    st.title("Backlog")
    st.caption("Log which assets reacted on which harmonic dates—build your private knowledge base.")

    st.info("Backlog storage will use SQLite locally (or a cloud DB later).")
    with st.form("log_form", clear_on_submit=True):
        asset = st.text_input("Asset / Symbol", placeholder="e.g., XAUUSD")
        date = st.date_input("Event date (UTC)")
        planets = st.text_input("Planet Pair / Pattern", placeholder="e.g., Sun–Moon 90°")
        note = st.text_area("Notes", placeholder="What happened? Reaction type/strength? Price context?")
        submitted = st.form_submit_button("Add entry")
    if submitted:
        st.success("Entry captured (mock). Next step: wire to SQLite using SQLAlchemy.")

    st.divider()
    st.subheader("Recent entries")
    st.caption("This will show your persisted backlog once storage is wired.")
    st.table([{"Date (UTC)": "—", "Asset": "—", "Pattern": "—", "Notes": "—"}])

elif st.session_state.page == "Settings":
    st.title("Settings")
    st.caption("App-wide configuration")

    section_header("Computation defaults")
    st.selectbox("Coordinate system", ["Geocentric / Tropical (recommended)", "Heliocentric", "Geocentric / Right Ascension"], index=0)
    st.number_input("Default orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
    st.multiselect("Default harmonic angles", [0, 30, 45, 60, 72, 90, 120, 135, 144, 150, 180, 225, 240, 270, 315, 330, 360], default=[0, 60, 90, 120, 180])

    section_header("Time & locale")
    st.selectbox("Display timezone", ["UTC (recommended)"], index=0, help="All calculations are done in UTC; display can localize later.")

    section_header("Data sources")
    st.markdown("- Ephemerides: **Skyfield** with JPL DE files")
    st.markdown("- Price data (optional): will discuss integrations (eg. Polygon.io, Alpha Vantage, Binance)")

elif st.session_state.page == "About":
    st.title("About Luminara")
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

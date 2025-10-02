import streamlit as st
from datetime import datetime, timezone

# ---------- Ephemeris + astro helpers ----------

from functools import lru_cache
import math
from typing import Iterable, Tuple, List
import pandas as pd

import streamlit as st
from skyfield.api import load
from skyfield.api import Loader

# Cachea resurser (hämtar ephemeris första gången, ~22 MB)
@st.cache_resource(show_spinner=False)
def get_ephemeris():
    # Skyfield kommer cache:a under /home/appuser/.skyfield på Streamlit Cloud
    # de421.bsp är liten + räcker gott för trading-användning
    return load("de421.bsp"), load.timescale()

def _planet_key(name: str) -> str:
    # Namn -> Skyfield-key i de421
    name = name.lower()
    mapping = {
        "sun": "sun",
        "moon": "moon",
        "mercury": "mercury",
        "venus": "venus",
        "mars": "mars",
        "jupiter": "jupiter barycenter",  # geocentriskt: observera själva jupiter nedan
        "saturn": "saturn barycenter",
        "uranus": "uranus barycenter",
        "neptune": "neptune barycenter",
        "pluto": "pluto barycenter",
    }
    # För barycenterplaneter använder vi (barycenter).planet för den riktiga kroppen
    return mapping.get(name, name)

def _is_bary(name: str) -> bool:
    return "barycenter" in name

def wrap_angle_deg(x: float) -> float:
    # 0..360
    return x % 360.0

def min_angle_diff(a: float, b: float) -> float:
    # minsta vinkel |a-b| modulo 360 (0..180)
    d = abs((a - b + 180.0) % 360.0 - 180.0)
    return d

def nearest_target_delta(angle: float, targets: Iterable[float]) -> Tuple[float, float]:
    """Returnera (minDiff, targetAngle) för närmaste target."""
    best = (9999.0, None)
    for t in targets:
        d = min_angle_diff(angle, t)
        if d < best[0]:
            best = (d, t)
    return best  # (diff, target)

@lru_cache(maxsize=256)
def _planet_obj(eph, name_lower: str):
    key = _planet_key(name_lower)
    body = eph[key]
    # Om barycenter – gå till den faktiska planeten (ex: 'jupiter barycenter' -> 'jupiter')
    if _is_bary(key):
        body = body.planet
    return body

def geo_ecliptic_longitude_deg(planet_name: str, t):
    """Geocentrisk tropisk ekliptisk longitud (grader) för planeten vid tiden t."""
    eph, ts = get_ephemeris()
    earth = eph["earth"]
    body = _planet_obj(eph, planet_name.lower())
    # Observera apparenta koordinater geocentriskt
    app = earth.at(t).observe(body).apparent()
    lon, lat, distance = app.ecliptic_latlon()
    return wrap_angle_deg(lon.degrees)

# -------------- App Config --------------
st.set_page_config(
    page_title="Luminara",
    page_icon=":milky_way:",
    layout="wide",
)

# -------------- Utilities --------------
def section_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# -------------- Sidebar --------------
st.sidebar.image(
    "https://raw.githubusercontent.com/github/explore/main/topics/astronomy/astronomy.png",
    use_column_width=True,
)
st.sidebar.markdown("## Luminara")
st.sidebar.caption("Astro-financial analytics for planetary cycles & harmonics")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Planet Pairs", "Backlog", "Settings", "About"],
    index=0,
)

st.sidebar.divider()
st.sidebar.markdown(f"**UTC:** {utc_now_iso()}")

# -------------- Pages --------------
if page == "Dashboard":
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

elif page == "Planet Pairs":
    st.title("Planet Pairs")
    elif page == "Planet Pairs":
    # ---------------- Planet Pairs ----------------
    st.title("Planet Pairs")
    st.caption("Scan for upcoming harmonic angles between two bodies (geocentric / tropical).")

    # --- Inputs ---
    left, mid1, mid2, right = st.columns([1.2, 1.0, 1.0, 1.8])
    with left:
        planet1 = st.selectbox(
            "Planet 1",
            ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"],
            index=0,
        )
    with mid1:
        planet2 = st.selectbox(
            "Planet 2",
            ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"],
            index=1,
        )
    with mid2:
        coord_frame = st.selectbox(
            "Frame",
            ["Geocentric / Ecliptic (Tropical)", "Heliocentric / Ecliptic", "Geocentric / Right Ascension"],
            index=0,
            help="Currently implemented: Geocentric / Tropical ecliptic longitude.",
        )
    with right:
        angles = st.multiselect(
            "Harmonic angles (deg)",
            [0, 30, 45, 60, 72, 90, 120, 135, 144, 150, 180, 225, 240, 270, 315, 330, 360],
            default=[0, 60, 90, 120, 180],
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        start_date = st.date_input("Start (UTC)", value=datetime.utcnow().date())
    with c2:
        end_date = st.date_input("End (UTC)", value=datetime.utcnow().date().replace(year=datetime.utcnow().year + 1))
    with c3:
        orb = st.number_input("Orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
    with c4:
        step_min = st.number_input("Step (minutes)", min_value=1, max_value=240, value=30, step=1,
                                   help="Time step for the search. Smaller is more precise, slower.")

    st.divider()

    # --- Compute ---
    run = st.button("Compute")
    if run:
        if coord_frame != "Geocentric / Ecliptic (Tropical)":
            st.warning("Only Geocentric / Tropical ecliptic longitudes are implemented in this preview.")
            st.stop()

        if planet1 == planet2:
            st.error("Planet 1 and Planet 2 must be different.")
            st.stop()

        if not angles:
            st.error("Please pick at least one harmonic angle.")
            st.stop()

        ts, eph = get_ephemeris()  # your cached ephemeris helper

        # build the timeline
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date,   datetime.min.time(), tzinfo=timezone.utc)
        if end_dt <= start_dt:
            st.error("End date must be after start date.")
            st.stop()

        # make a list of times with given step (minutes)
        total_minutes = int((end_dt - start_dt).total_seconds() // 60)
        times_utc = [start_dt + timedelta(minutes=m) for m in range(0, total_minutes + 1, int(step_min))]
        ts_times = ts.from_datetimes(times_utc)

        # resolve skyfield bodies (you should have a resolver in your helpers; here’s a simple inline one)
        def _resolve(body_name: str):
            name = body_name.lower()
            if name == "sun":     return eph["sun"]
            if name == "moon":    return eph["moon"]
            if name == "mercury": return eph["mercury barycenter"]
            if name == "venus":   return eph["venus barycenter"]
            if name == "mars":    return eph["mars barycenter"]
            if name == "jupiter": return eph["jupiter barycenter"]
            if name == "saturn":  return eph["saturn barycenter"]
            if name == "uranus":  return eph["uranus barycenter"]
            if name == "neptune": return eph["neptune barycenter"]
            if name == "pluto":   return eph["pluto barycenter"]
            raise ValueError(f"Unknown body: {body_name}")

        body1 = _resolve(planet1)
        body2 = _resolve(planet2)

        geocenter = eph["earth"]  # geocentric
        # ecliptic longitudes (tropical)
        lon1 = geo_ecliptic_longitude_deg(geocenter, body1, ts_times)  # -> np.array of degrees
        lon2 = geo_ecliptic_longitude_deg(geocenter, body2, ts_times)

        # angle between bodies (0..180)
        diff = angular_diff_deg(lon1, lon2)

        hits_rows = []
        for idx, dt in enumerate(times_utc):
            for a in angles:
                # minimal separation to this angle (wrap-aware)
                delta = nearest_angle_offset(diff[idx], float(a))  # signed, e.g. -0.2°..+0.2°
                if abs(delta) <= orb:
                    hits_rows.append({
                        "datetime_utc": dt.strftime("%Y-%m-%d %H:%M"),
                        "planet_1": planet1,
                        "planet_2": planet2,
                        "angle": a,
                        "delta_deg": round(float(delta), 3),
                    })

        if not hits_rows:
            st.info("No hits found for the selected range, angles, and orb.")
            st.stop()

        df = pd.DataFrame(hits_rows).sort_values(["datetime_utc", "angle"]).reset_index(drop=True)

        # --- Summary ---
        s1, s2, s3 = st.columns(3)
        with s1:
            st.metric("Matches", len(df))
        with s2:
            st.metric("Angles tested", len(angles))
        with s3:
            st.metric("Time step (min)", step_min)

        # --- Results table & download ---
        st.dataframe(df, use_container_width=True, height=420)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv, file_name="planet_pairs_hits.csv", mime="text/csv")

        with st.expander("Parameters"):
            st.code(
                f"""planet_1: {planet1}
planet_2: {planet2}
frame:    {coord_frame}
angles:   {angles}
orb:      ±{orb}°
step:     {step_min} min
range:    {start_dt:%Y-%m-%d %H:%M} → {end_dt:%Y-%m-%d %H:%M} (UTC)""",
                language="yaml",
            )

elif page == "Backlog":
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

elif page == "Settings":
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

elif page == "About":
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

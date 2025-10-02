import streamlit as st
from datetime import datetime, timezone

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
    st.caption("Find upcoming harmonic angles between two planets (geocentric tropical).")

    col = st.columns([1, 1, 1, 2])
    with col[0]:
        planet1 = st.selectbox("Planet 1", ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"])
    with col[1]:
        planet2 = st.selectbox("Planet 2", ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"], index=1)
    with col[2]:
        coordinate = st.selectbox("Frame", ["Geocentric / Ecliptic (Tropical)", "Heliocentric / Ecliptic", "Geocentric / Right Ascension"], index=0)
    with col[3]:
        angles = st.multiselect(
            "Harmonic Angles (deg)",
            [0, 30, 45, 60, 72, 90, 120, 135, 144, 150, 180, 225, 240, 270, 315, 330, 360],
            default=[0, 60, 90, 120, 180],
        )

    col_lo, col_hi, col_orb = st.columns(3)
    with col_lo:
        start_date = st.date_input("Start date (UTC)", value=datetime.utcnow().date())
    with col_hi:
        end_date = st.date_input("End date (UTC)", value=datetime.utcnow().date().replace(year=datetime.utcnow().year + 1))
    with col_orb:
        orb = st.number_input("Orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)

    st.divider()
    if st.button("Compute"):
        st.info("Computation engine not wired yet. Next step is to integrate Skyfield ephemerides and search for hits.")
        st.code(
            f"""Params:
- Planet 1: {planet1}
- Planet 2: {planet2}
- Frame:    {coordinate}
- Angles:   {angles}
- Orb:      ±{orb}°
- Range:    {start_date} → {end_date} (UTC)""",
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

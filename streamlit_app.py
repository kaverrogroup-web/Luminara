# streamlit_app.py
# Luminara — UI skeleton with light sidebar, robust nav, and Bento grid layout

import streamlit as st
from datetime import datetime, timezone
from contextlib import contextmanager

# -------------------------------- App config --------------------------------
st.set_page_config(
    page_title="Luminara",
    page_icon="🌌",
    layout="wide",
)

# ------------------------------- Small utils --------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def section_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)

# ------------------------------- Global CSS ---------------------------------
# Light sidebar + tab-style active state + soft app chrome
st.markdown("""
<style>
/* App background */
.stApp { background:#f8f9fa; color:#1c1c1c; }

/* Remove that little white square some browsers show for missing images */
img[alt="Logo"] { display:none; }

/* Sidebar: light, with subtle borders and a tab-like active item */
section[data-testid="stSidebar"] {
  background:#ffffff !important;
  border-right:1px solid #e6e6e6;
}
.sidebar-header { padding: 12px 8px 6px; }
.sidebar-title   { font-weight:700; font-size:1.05rem; margin-bottom:2px; }
.sidebar-sub     { font-size:.85rem; color:#6b7280; }

/* Menu list */
.menu-group { margin-top: 10px; }
.menu-item button[kind="secondary"] {
  width:100%;
  justify-content:flex-start;
  background:#ffffff;
  border:1px solid #e9ecef;
  color:#1c1c1c;
  padding:7px 10px;
  border-radius:10px;
}
.menu-item button[kind="secondary"]:hover {
  border-color:#d7dce1;
  background:#fafafa;
}
.menu-item.active button[kind="secondary"]{
  background:#f1f5f9;
  border-color:#cfd6dd;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,.02);
  font-weight:700;
}

/* UTC clock at bottom */
.sidebar-foot {
  padding: 10px 6px 14px;
  font-size:.8rem;
  color:#6b7280;
  border-top:1px solid #eef0f2;
  margin-top:14px;
}

/* Page titles */
h1, .stMarkdown h1 { letter-spacing:.2px; }

/* ----------------------- Bento grid (12 columns) ------------------------ */
.bento-grid{
  display:grid;
  grid-template-columns: repeat(12, minmax(0,1fr));
  gap:14px;
  align-items:start;
}
.bento-card{
  background:#ffffff;
  border:1px solid #e6e6e6;
  border-radius:14px;
  padding:14px 16px;
  box-shadow:0 1px 0 rgba(0,0,0,.02);
}
.bento-title{ font-weight:700; font-size:1.05rem; margin-bottom:8px; }
.bento-sub  { color:#6b7280; font-size:.9rem; margin:-2px 0 8px; }

/* Soft table borders inside cards */
.bento-card table{
  border-collapse:separate !important;
  border-spacing:0;
  width:100%;
}
.bento-card th, .bento-card td{
  border-top:1px solid #efefef !important;
}
.bento-card thead th{
  border-top:none !important;
  color:#6b7280; font-weight:600;
}
.bento-card tr:last-child td{
  border-bottom:1px solid #efefef !important;
}

/* Responsive stacking */
@media (max-width: 1100px){
  .span-12 { grid-column: span 12 !important; }
  .span-8  { grid-column: span 12 !important; }
  .span-6  { grid-column: span 12 !important; }
  .span-4  { grid-column: span 12 !important; }
}
</style>
""", unsafe_allow_html=True)

# ------------------------ Bento helpers (one-time) ---------------------------
def bento_open():
    st.markdown('<div class="bento-grid">', unsafe_allow_html=True)

def bento_close():
    st.markdown('</div>', unsafe_allow_html=True)

@contextmanager
def bento_card(span: int, title: str = "", subtitle: str | None = None):
    st.markdown(
        f'<div class="bento-card span-{span}" style="grid-column: span {span};">', 
        unsafe_allow_html=True
    )
    if title:
        st.markdown(f'<div class="bento-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="bento-sub">{subtitle}</div>', unsafe_allow_html=True)
    try:
        yield
    finally:
        st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------- Navigation ---------------------------------
PAGES = ["Dashboard", "Planet Pairs", "Backlog", "Settings", "About"]

# Initialize selected page if first load
if "page" not in st.session_state:
    st.session_state.page = PAGES[0]

# Sidebar (pure text, no collapse, light look)
with st.sidebar:
    st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">Luminara</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">Astro-financial analytics</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### Menu")
    for name in PAGES:
        active = (st.session_state.page == name)
        c = st.container()
        with c:
            st.markdown(
                f'<div class="menu-item {"active" if active else ""}">', 
                unsafe_allow_html=True
            )
            if st.button(name, key=f"nav_{name}", type="secondary"):
                st.session_state.page = name
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="sidebar-foot">UTC: {utc_now_iso()}</div>', unsafe_allow_html=True)

page = st.session_state.page  # convenience alias

# --------------------------------- Pages ------------------------------------
# 1) Dashboard (Bento)
if page == "Dashboard":
    st.title("Luminara")
    st.caption("Astro-financial analytics dashboard")

    bento_open()
    # Row 1 — 6 + 6
    with bento_card(6, "Overview"):
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Upcoming hits", "3")
        with c2: st.metric("Active pairs", "5")
        with c3: st.metric("Watch window", "7–21d")

        st.markdown("#### Recent timing signals (sample)")
        st.dataframe(
            [
                {"Date (UTC)": "2025-10-03", "Pair": "Sun–Moon",     "Angle": "90°",  "Orb": "0.2°"},
                {"Date (UTC)": "2025-10-06", "Pair": "Venus–Saturn", "Angle": "120°", "Orb": "0.8°"},
                {"Date (UTC)": "2025-10-11", "Pair": "Mars–Jupiter", "Angle": "60°",  "Orb": "0.5°"},
            ],
            use_container_width=True,
            hide_index=True
        )

    with bento_card(6, "Next harmonics", "Nearest matching angles in the next 30 days (sample)."):
        st.dataframe(
            [
                {"When (UTC)":"Oct 03 14:00","Pair":"Sun–Moon",     "Angle":"90°","Δ":"0.2°"},
                {"When (UTC)":"Oct 07 09:30","Pair":"Mercury–Mars","Angle":"45°","Δ":"0.4°"},
                {"When (UTC)":"Oct 12 18:15","Pair":"Jupiter–Saturn","Angle":"120°","Δ":"0.7°"},
            ],
            use_container_width=True,
            hide_index=True
        )

    # Row 2 — 8 + 4
    with bento_card(8, "Your notes"):
        st.caption("Quick scratchpad for ideas (not persisted yet).")
        st.text_area(" ", placeholder="Observations, hypotheses, to-dos…", label_visibility="hidden", height=160)

    with bento_card(4, "Watchlist (sample)"):
        st.dataframe(
            [
                {"Asset":"XAUUSD","Focus pair":"Sun–Moon",     "Angles":"0, 90, 180","Window":"Action"},
                {"Asset":"ES",    "Focus pair":"Venus–Saturn", "Angles":"60, 120",   "Window":"Watch"},
                {"Asset":"BTCUSD","Focus pair":"Mars–Jupiter", "Angles":"45, 135",   "Window":"Radar"},
            ],
            use_container_width=True,
            hide_index=True
        )
    bento_close()

# 2) Planet Pairs (Bento)
elif page == "Planet Pairs":
    st.title("Planet Pairs")
    st.caption("Find upcoming harmonic angles between two planets (geocentric tropical).")

    bento_open()

    with bento_card(12, "Parameters"):
        left, mid1, mid2, right = st.columns([1.2, 1.0, 1.0, 1.0])
        with left:
            planet1 = st.selectbox("Planet 1", ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Uranus","Neptune","Pluto"])
        with mid1:
            planet2 = st.selectbox("Planet 2", ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Uranus","Neptune","Pluto"], index=1)
        with mid2:
            coordinate = st.selectbox("Frame", ["Geocentric / Ecliptic (Tropical)", "Heliocentric / Ecliptic", "Geocentric / Right Ascension"], index=0)
        with right:
            angles = st.multiselect(
                "Harmonic Angles (deg)",
                [0,30,45,60,72,90,120,135,144,150,180,225,240,270,315,330,360],
                default=[0,60,90,120,180],
            )

        lo, hi, orbcol = st.columns(3)
        with lo:
            start_date = st.date_input("Start date (UTC)", value=datetime.utcnow().date())
        with hi:
            end_date = st.date_input("End date (UTC)", value=datetime.utcnow().date().replace(year=datetime.utcnow().year + 1))
        with orbcol:
            orb = st.number_input("Orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)

        run = st.button("Compute", type="primary")

    with bento_card(12, "Results"):
        if not run:
            st.info("Click **Compute** to search for hits (ephemeris engine comes in next step).")
        else:
            st.success("Parameters captured. Next step: integrate Skyfield search.")
            st.json({
                "planet1": planet1,
                "planet2": planet2,
                "frame": coordinate,
                "angles": angles,
                "orb": orb,
                "range": [str(start_date), str(end_date)],
            })
    bento_close()

# 3) Backlog (Bento)
elif page == "Backlog":
    st.title("Backlog")
    st.caption("Log which assets reacted on which harmonic dates—build your private knowledge base.")

    bento_open()
    with bento_card(6, "Add entry"):
        with st.form("log_form", clear_on_submit=True):
            asset = st.text_input("Asset / Symbol", placeholder="e.g., XAUUSD")
            date  = st.date_input("Event date (UTC)")
            pat   = st.text_input("Planet Pair / Pattern", placeholder="e.g., Sun–Moon 90°")
            note  = st.text_area("Notes", placeholder="What happened? Reaction type/strength? Price context?")
            submitted = st.form_submit_button("Add entry")
        if submitted:
            st.success("Entry captured (mock). Next step: wire to SQLite using SQLAlchemy.")

    with bento_card(6, "Recent entries"):
        st.caption("This will show your persisted backlog once storage is wired.")
        st.table([{"Date (UTC)":"—","Asset":"—","Pattern":"—","Notes":"—"}])
    bento_close()

# 4) Settings (Bento)
elif page == "Settings":
    st.title("Settings")
    st.caption("App-wide configuration")

    bento_open()
    with bento_card(6, "Computation defaults"):
        st.selectbox("Coordinate system", ["Geocentric / Tropical (recommended)", "Heliocentric", "Geocentric / Right Ascension"], index=0)
        st.number_input("Default orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
        st.multiselect(
            "Default harmonic angles",
            [0,30,45,60,72,90,120,135,144,150,180,225,240,270,315,330,360],
            default=[0,60,90,120,180]
        )

    with bento_card(6, "Time & locale"):
        st.selectbox("Display timezone", ["UTC (recommended)"], index=0, help="All calculations are done in UTC; display can localize later.")

    with bento_card(12, "Data sources"):
        st.markdown("- Ephemerides: **Skyfield** with JPL DE files")
        st.markdown("- Price data (optional): discuss integrations (eg. Polygon.io, Alpha Vantage, Binance)")
    bento_close()

# 5) About (Bento)
elif page == "About":
    st.title("About Luminara")
    bento_open()
    with bento_card(12, "What is Luminara?"):
        st.markdown(
            """
            **Luminara** helps traders analyze planetary cycles and harmonic angles
            to anticipate timing clusters. Built with Streamlit and (soon) Skyfield ephemerides.

            **Roadmap**
            1. Skyfield engine for geocentric tropical angles (UTC).
            2. Scanners for multi-angle hits + clustering and scoring.
            3. Backlog persistence + dashboard analytics.
            4. Optional price-data overlays & alerts.
            """
        )
    bento_close()

# streamlit_app.py
import streamlit as st
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from skyfield.api import load

# -------------------- App Config --------------------
st.set_page_config(page_title="Luminara", page_icon=":milky_way:", layout="wide")
st.title("Luminara")
st.caption("Single-page prototype — planetary harmonic timing (geocentric / tropical / UTC)")

# -------------------- Planets -----------------------
PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]

_DE421_KEY = {
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

@st.cache_resource(show_spinner=False)
def get_ephemeris():
    eph = load("de421.bsp")
    ts = load.timescale()
    return eph, ts

def _planet_obj(eph, planet_name: str):
    key = _DE421_KEY.get(planet_name.lower())
    if key is None:
        raise ValueError(f"Unknown planet name: {planet_name}")
    body = eph[key]
    if "barycenter" in key:
        body = body.planet
    return body

# -------------------- Angle Helpers -----------------
def nearest_target_delta(angle_deg: float, targets: list[float]) -> tuple[float, float]:
    """Return (delta, nearest_target)."""
    dmin, tmin = 999.0, None
    for t in targets:
        d = abs(((angle_deg - t + 180.0) % 360.0) - 180.0)
        if d < dmin:
            dmin, tmin = d, t
    return dmin, tmin

def bisection_refine(planet1, planet2, t_lo, t_hi, target_deg, max_iter=28):
    eph, ts = get_ephemeris()
    earth = eph["earth"]
    p1 = _planet_obj(eph, planet1)
    p2 = _planet_obj(eph, planet2)

    def angle_to_target(time):
        app1 = earth.at(time).observe(p1).apparent()
        app2 = earth.at(time).observe(p2).apparent()
        lon1, _, _ = app1.ecliptic_latlon()
        lon2, _, _ = app2.ecliptic_latlon()
        ang = (lon1.degrees - lon2.degrees) % 360.0
        d = abs(((ang - target_deg + 180.0) % 360.0) - 180.0)
        return d, ang

    lo = t_lo.utc_datetime()
    hi = t_hi.utc_datetime()

    best_t = t_lo
    best_delta, best_ang = angle_to_target(t_lo)

    for _ in range(max_iter):
        mid = lo + (hi - lo) / 2
        t_mid = ts.utc(mid.year, mid.month, mid.day, mid.hour, mid.minute,
                       mid.second + mid.microsecond / 1e6)
        d_mid, a_mid = angle_to_target(t_mid)

        if d_mid < best_delta:
            best_delta = d_mid
            best_t = t_mid
            best_ang = a_mid

        if d_mid < 1/60:  # arcminute precision
            break

        # shrink interval
        if a_mid > target_deg:
            hi = mid
        else:
            lo = mid

    return best_t, best_delta, best_ang

def scan_harmonic_hits(planet1, planet2, start_dt_utc, end_dt_utc, targets, orb_deg, coarse_step_min):
    eph, ts = get_ephemeris()
    earth = eph["earth"]
    p1 = _planet_obj(eph, planet1)
    p2 = _planet_obj(eph, planet2)

    step = max(1, int(coarse_step_min))
    grid = []
    cur = start_dt_utc
    while cur <= end_dt_utc:
        grid.append(cur)
        cur += timedelta(minutes=step)

    diffs, nearest = [], []
    for dt in grid:
        t = ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        app1 = earth.at(t).observe(p1).apparent()
        app2 = earth.at(t).observe(p2).apparent()
        lon1, _, _ = app1.ecliptic_latlon()
        lon2, _, _ = app2.ecliptic_latlon()
        ang = (lon1.degrees - lon2.degrees) % 360.0
        d, targ = nearest_target_delta(ang, targets)
        diffs.append(d)
        nearest.append(targ)

    diffs = np.asarray(diffs)

    minima_idx = []
    for i in range(1, len(diffs) - 1):
        if diffs[i] <= diffs[i - 1] and diffs[i] <= diffs[i + 1]:
            minima_idx.append(i)

    rows = []
    for i in minima_idx:
        dt_lo = grid[max(0, i - 1)]
        dt_hi = grid[min(len(grid) - 1, i + 1)]
        t_lo = ts.utc(dt_lo.year, dt_lo.month, dt_lo.day, dt_lo.hour, dt_lo.minute, dt_lo.second)
        t_hi = ts.utc(dt_hi.year, dt_hi.month, dt_hi.day, dt_hi.hour, dt_hi.minute, dt_hi.second)

        target = nearest[i]
        t_best, d_best, angle_at_best = bisection_refine(planet1, planet2, t_lo, t_hi, target)

        if d_best <= orb_deg:
            dt = t_best.utc_datetime().replace(microsecond=0)
            rows.append({
                "When (UTC)": dt,
                "Pair": f"{planet1}–{planet2}",
                "Angle": round(angle_at_best % 360.0, 2),
                "Target": target,
                "Δ (deg)": round(d_best, 3),
            })

    return pd.DataFrame(rows)

# -------------------- UI -----------------------
with st.container():
    st.subheader("Timing — planetary harmonics (geocentric / tropical / UTC)")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        p1 = st.selectbox("Planet 1", PLANETS, index=2)
    with c2:
        p2 = st.selectbox("Planet 2", PLANETS, index=5)
    with c3:
        orb = st.number_input("Orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)

    c4, c5 = st.columns(2)
    with c4:
        start_date = st.date_input("Start date (UTC)", value=datetime.utcnow().date())
    with c5:
        end_date = st.date_input("End date (UTC)", value=(datetime.utcnow() + timedelta(days=90)).date())

    c6, c7 = st.columns([2, 1])
    with c6:
        angles = st.multiselect(
            "Harmonic angles (deg)",
            [0, 30, 45, 60, 72, 90, 120, 135, 144, 150, 180],
            default=[0, 60, 90, 120, 180],
        )
    with c7:
        coarse_step = st.slider("Coarse step (minutes)", min_value=5, max_value=240, value=60, step=5)

    if st.button("Compute timing"):
        t0 = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        t1 = datetime.combine(end_date, datetime.min.time()).replace(tzinfo=timezone.utc)

        if p1 == p2:
            st.error("Pick two different planets.")
        elif len(angles) == 0:
            st.error("Pick at least one harmonic angle.")
        else:
            df = scan_harmonic_hits(p1, p2, t0, t1, angles, orb, coarse_step)
            st.metric("Upcoming hits", f"{len(df)}")
            if df.empty:
                st.info("No matches found.")
            else:
                st.dataframe(df, use_container_width=True)

# Footer
st.markdown(f"UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

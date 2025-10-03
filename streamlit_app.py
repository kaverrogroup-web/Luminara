# ------------------------------ Luminara (single page) ------------------------------
# Core prototype: planetary harmonic timing (geocentric / tropical / UTC)
# - Reliable Skyfield engine (DE421) + simple scanner
# - One page: inputs at the top, results table under the button
# -----------------------------------------------------------------------------------

import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta, timezone

# ============================== UI BASICS ==========================================
st.set_page_config(page_title="Luminara", page_icon=":milky_way:", layout="wide")
st.title("Luminara")
st.caption("Single-page prototype — planetary harmonic timing (geocentric / tropical / UTC)")

# ============================== Helpers: Ephemeris & angles =========================

# Planet list for selectors (geocentric tropical)
PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]

# Map selector names -> Skyfield DE421 keys (handle barycenters → .planet)
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

# ===== Skyfield engine (cached)
from functools import lru_cache
from skyfield.api import load

@lru_cache(maxsize=1)
def get_ephemeris():
    eph = load("de421.bsp")          # cached by Skyfield on first run (~22 MB)
    ts = load.timescale()
    return eph, ts

def wrap_angle_deg(x: float) -> float:
    return x % 360.0

def min_angle_diff(a: float, b: float) -> float:
    """Minimum absolute angular separation |a-b| on a circle (0..180°)."""
    return abs((a - b + 180.0) % 360.0 - 180.0)

def nearest_target_delta(angle: float, targets) -> tuple[float, float]:
    """Given current angle, return (minDiff, closestTarget)."""
    best = (9999.0, None)
    for t in targets:
        d = min_angle_diff(angle, t)
        if d < best[0]:
            best = (d, t)
    return best

@lru_cache(maxsize=256)
def _planet_obj(name_lower: str):
    eph, _ = get_ephemeris()
    key = _DE421_KEY[name_lower]
    body = eph[key]
    # if barycenter, switch to actual body (.planet)
    if "barycenter" in key:
        body = body.planet
    return body

def geo_ecliptic_longitude_deg(planet_name: str, t):
    """Geocentric tropical ecliptic longitude (deg) at time t (Skyfield Time)."""
    eph, _ = get_ephemeris()
    earth = eph["earth"]
    body = _planet_obj(planet_name.lower())
    app = earth.at(t).observe(body).apparent()
    # 'epoch="date"' ensures true-of-date ecliptic (tropical)
    lon, lat, _ = app.ecliptic_latlon(epoch="date")
    return wrap_angle_deg(lon.degrees)

def scan_harmonic_hits(
    p1: str,
    p2: str,
    start_dt_utc: datetime,
    end_dt_utc: datetime,
    targets_deg: list[float],
    orb_deg: float = 1.0,
    coarse_step_minutes: int = 60,
    refine_window_minutes: int = 30,
    refine_step_minutes: int = 5,
) -> list[dict]:
    """
    Coarse scan [start, end] for close approaches (|angle - target| <= orb),
    then refine locally in a small window for a better timestamp.
    Returns list of dict rows.
    """
    eph, ts = get_ephemeris()

    def to_ts(dt: datetime):
        return ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)

    # Coarse pass
    hits = []
    dt = start_dt_utc
    coarse = timedelta(minutes=coarse_step_minutes)

    while dt <= end_dt_utc:
        t = to_ts(dt)
        a1 = geo_ecliptic_longitude_deg(p1, t)
        a2 = geo_ecliptic_longitude_deg(p2, t)
        angle = wrap_angle_deg(a1 - a2)
        diff, target = nearest_target_delta(angle, targets_deg)
        if diff <= orb_deg:
            # refine around dt in ± refine_window_minutes using refine_step_minutes
            rw = timedelta(minutes=refine_window_minutes)
            rs = timedelta(minutes=refine_step_minutes)
            dt_lo = max(start_dt_utc, dt - rw)
            dt_hi = min(end_dt_utc, dt + rw)

            best = (diff, dt, angle, target)
            dt_ref = dt_lo
            while dt_ref <= dt_hi:
                t_ref = to_ts(dt_ref)
                a1r = geo_ecliptic_longitude_deg(p1, t_ref)
                a2r = geo_ecliptic_longitude_deg(p2, t_ref)
                ang = wrap_angle_deg(a1r - a2r)
                d = min_angle_diff(ang, target)
                if d < best[0]:
                    best = (d, dt_ref, ang, target)
                dt_ref += rs

            best_diff, best_dt, best_ang, best_target = best
            hits.append({
                "when_utc": best_dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "pair": f"{p1}–{p2}",
                "angle": round(best_ang, 2),
                "target": round(best_target, 2),
                "Δ (deg)": round(best_diff, 3),
            })

        dt += coarse

    # Deduplicate near-duplicates (keep smallest Δ within 90 minutes)
    hits.sort(key=lambda r: (r["when_utc"], r["Δ (deg)"]))
    deduped = []
    last_time = None
    for h in hits:
        if last_time is None:
            deduped.append(h)
            last_time = datetime.strptime(h["when_utc"], "%Y-%m-%d %H:%M")
        else:
            t_cur = datetime.strptime(h["when_utc"], "%Y-%m-%d %H:%M")
            if (t_cur - last_time) > timedelta(minutes=90):
                deduped.append(h)
                last_time = t_cur
            else:
                # within 90 min: keep the one already there (it had smaller Δ by sort)
                pass

    return deduped

# ============================== UI: inputs =========================================

timing = st.container()
with timing:
    st.subheader("Timing — planetary harmonics (geocentric / tropical / UTC)")

    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        p1 = st.selectbox("Planet 1", PLANETS, index=4)  # default Mars
    with c2:
        p2 = st.selectbox("Planet 2", PLANETS, index=5)  # default Jupiter
    with c3:
        orb = st.number_input("Orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
    with c4:
        # quick presets; user may edit later
        default_angles = [0, 60, 90, 120, 180]
        targets = st.multiselect(
            "Harmonic angles (deg)",
            [0, 30, 45, 60, 72, 90, 120, 135, 144, 150, 180, 225, 240, 270, 315, 330],
            default=default_angles,
        )

    c5, c6, c7 = st.columns([1, 1, 2])
    with c5:
        start_date = st.date_input("Start date (UTC)", value=date.today())
    with c6:
        end_date = st.date_input("End date (UTC)", value=date.today() + timedelta(days=30))
    with c7:
        step = st.slider("Coarse step (minutes)", min_value=5, max_value=240, value=60, step=5)

    st.caption("All calculations are done in UTC. Times shown below are UTC.")

# ============================== Action + Results ===================================

run = st.button("Compute timing")
placeholder = st.empty()

if run:
    with st.spinner("Computing timing hits…"):
        # build full UTC datetimes (00:00 → 23:59)
        start_dt = datetime.combine(start_date, time(0, 0), tzinfo=timezone.utc).replace(tzinfo=None)
        end_dt = datetime.combine(end_date, time(23, 59), tzinfo=timezone.utc).replace(tzinfo=None)

        rows = scan_harmonic_hits(
            p1=p1,
            p2=p2,
            start_dt_utc=start_dt,
            end_dt_utc=end_dt,
            targets_deg=[float(x) for x in targets],
            orb_deg=float(orb),
            coarse_step_minutes=int(step),
            refine_window_minutes=30,
            refine_step_minutes=5,
        )

        if not rows:
            placeholder.info("No hits found in the selected range with the current orb/angles.")
        else:
            df = pd.DataFrame(rows)
            df.index = pd.RangeIndex(start=1, stop=len(df)+1, step=1)
            st.subheader("Matches")
            st.dataframe(df, use_container_width=True)
            st.success(f"Found {len(df)} match(es).")

# ===================================================================================
# End of file
# ===================================================================================

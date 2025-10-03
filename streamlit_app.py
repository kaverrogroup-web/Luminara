# streamlit_app.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone, date, time
import math
from typing import Iterable, Tuple, List, Optional

import numpy as np
import pandas as pd
import streamlit as st
from skyfield.api import load


# --------------------------- App config ---------------------------
st.set_page_config(
    page_title="Luminara",
    page_icon="🌌",
    layout="wide",
)

st.title("Luminara")
st.caption("Single-page prototype — planetary harmonic timing (geocentric / tropical / UTC) + price projections")


# --------------------------- Styling ---------------------------
st.markdown(
    """
    <style>
      /* Subtle borders (like cards) via expanders */
      .st-expander {
        border: 1px solid #e6e6e6 !important;
        border-radius: 10px !important;
      }
      .st-expander .streamlit-expanderHeader {
        font-weight: 600 !important;
      }
      /* Make tag chips a tad tighter */
      .stMultiSelect [data-baseweb="tag"] {
        margin-right: 6px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------- Constants ---------------------------
PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]

# Map to Skyfield DE421 keys (handle barycenters → .planet)
_DE421_KEY = {
    "sun": "sun",
    "moon": "moon",
    "mercury": "mercury",
    "venus": "venus",
    "mars": "mars",

    # Gas giants and outer planets are barycenters in DE421
    "jupiter": "jupiter barycenter",
    "saturn": "saturn barycenter",
    "uranus": "uranus barycenter",
    "neptune": "neptune barycenter",
    "pluto": "pluto barycenter",
}


# --------------------------- Ephemeris cache ---------------------------
@st.cache_resource(show_spinner=False)
def get_ephemeris():
    # Small + perfectly fine for timing
    eph = load("de421.bsp")
    ts = load.timescale()
    return eph, ts


def _planet_obj(eph, planet_name: str):
    """
    Return a Skyfield planet object from a human name.
    Handles DE421 barycenters gracefully (use .planet if available).
    """
    key = _DE421_KEY.get(planet_name.lower())
    if key is None:
        raise ValueError(f"Unknown planet name: {planet_name}")
    body = eph[key]
    if "barycenter" in key and hasattr(body, "planet"):
        try:
            body = body.planet
        except Exception:
            pass  # fallback: keep barycenter if .planet not available
    return body


# --------------------------- Angle helpers ---------------------------
def wrap_angle_deg(x: float) -> float:
    return x % 360.0


def min_angle_diff(a: float, b: float) -> float:
    """Smallest absolute difference (0..180) between angles a, b."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def geo_ecliptic_longitude_deg(planet_name: str, t) -> float:
    """
    Geocentric *tropical* ecliptic longitude (deg) for planet at time t (Skyfield Time).
    """
    eph, ts = get_ephemeris()
    earth = eph["earth"]
    body = _planet_obj(eph, planet_name)
    app = earth.at(t).observe(body).apparent()
    lon, lat, distance = app.ecliptic_latlon()
    return wrap_angle_deg(lon.degrees)


def angle_between_longitudes(p1: str, p2: str, t) -> float:
    """Angle P1→P2 on the tropical ecliptic (0..360)."""
    a1 = geo_ecliptic_longitude_deg(p1, t)
    a2 = geo_ecliptic_longitude_deg(p2, t)
    return wrap_angle_deg(a2 - a1)


def refine_hit(
    p1: str,
    p2: str,
    t_lo,
    t_hi,
    target_angle: float,
    orb: float,
    max_iter: int = 24,
) -> Optional[Tuple[datetime, float, float]]:
    """
    Bisection around a coarse "hit" to the moment the angle is closest to target.
    Returns (dt_utc, angle, diff) or None.
    """
    eph, ts = get_ephemeris()
    best_t = None
    best_diff = 10**9
    best_ang = None

    for _ in range(max_iter):
        # mid-point in Skyfield time
        dt = t_lo.utc_datetime() + (t_hi.utc_datetime() - t_lo.utc_datetime()) / 2
        tm = ts.from_datetime(dt.replace(tzinfo=timezone.utc))
        ang = angle_between_longitudes(p1, p2, tm)
        diff = min_angle_diff(ang, target_angle)

        if diff < best_diff:
            best_diff = diff
            best_t = tm
            best_ang = ang

        # decide which half to keep: pick side whose endpoint is closer to target
        ang_lo = angle_between_longitudes(p1, p2, t_lo)
        ang_hi = angle_between_longitudes(p1, p2, t_hi)
        if min_angle_diff(ang_lo, target_angle) < min_angle_diff(ang_hi, target_angle):
            t_hi = tm
        else:
            t_lo = tm

        if best_diff <= 1e-3:  # about 0.001°
            break

    if best_t is None:
        return None

    # Only accept if we are inside the orb
    if best_diff <= orb + 1e-6:
        return best_t.utc_datetime().replace(tzinfo=timezone.utc), best_ang, best_diff
    return None


def scan_harmonic_hits(
    p1: str,
    p2: str,
    start_dt_utc: datetime,
    end_dt_utc: datetime,
    angles: List[float],
    orb: float,
    coarse_step_minutes: int,
) -> pd.DataFrame:
    """
    Coarse scan from start..end every N minutes.
    When within orb of any target angle, refine to the best time.
    """
    angles = sorted(set(angles))
    eph, ts = get_ephemeris()

    # iterate coarse grid
    t = ts.from_datetime(start_dt_utc)
    t_end = ts.from_datetime(end_dt_utc)

    rows = []
    prev_is_near = False
    prev_t = t
    prev_diff_min = None

    while t.tt <= t_end.tt + 1e-12:
        diffs = [min_angle_diff(angle_between_longitudes(p1, p2, t), a) for a in angles]
        diff_min = float(min(diffs))
        is_near = diff_min <= max(orb * 1.5, orb + 0.1)  # small cushion to trigger refinement

        if is_near and not prev_is_near:
            # refine on bracket [prev_t, t]
            # pick the closest angle as target
            ang_now = angle_between_longitudes(p1, p2, t)
            targets_by_closeness = sorted(angles, key=lambda A: min_angle_diff(ang_now, A))
            hit = None
            for target in targets_by_closeness[:3]:  # try a few closest targets
                got = refine_hit(p1, p2, prev_t, t, target, orb)
                if got is not None:
                    hit = (target, got)
                    break
            if hit is not None:
                target_angle, (best_dt, best_ang, best_diff) = hit
                rows.append(
                    dict(
                        when_utc=best_dt,
                        pair=f"{p1}–{p2}",
                        angle=round(best_ang, 2),
                        target=int(round(target_angle)),
                        Δ=round(best_diff, 3),
                    )
                )

        prev_is_near = is_near
        prev_t = t

        # advance
        t = ts.from_datetime(
            t.utc_datetime().replace(tzinfo=timezone.utc)
            + timedelta(minutes=coarse_step_minutes)
        )

    if not rows:
        return pd.DataFrame(columns=["when_utc", "pair", "angle", "target", "Δ"]).astype(
            {"when_utc": "datetime64[ns]"}
        )

    df = pd.DataFrame(rows).sort_values("when_utc").reset_index(drop=True)
    return df


# --------------------------- Price projections ---------------------------
def percent_grid_levels(anchor_price: float, percents: Iterable[float]) -> pd.DataFrame:
    rows = []
    for p in percents:
        up = anchor_price * (1 + p / 100.0)
        dn = anchor_price * (1 - p / 100.0)
        rows.append(dict(type="Up",  percent=p, level=round(up, 4)))
        rows.append(dict(type="Down", percent=p, level=round(dn, 4)))
    df = pd.DataFrame(rows).sort_values(["type", "percent"]).reset_index(drop=True)
    return df


def root_ladder_levels(anchor_price: float, root_step: float, turns: int) -> pd.DataFrame:
    """
    A simple multiplicative ladder around anchor:
    level = anchor * (1 + root_step)^n  and  anchor / (1 + root_step)^n
    where n = 1..turns
    """
    rows = []
    f = 1.0 + root_step
    for n in range(1, turns + 1):
        up = anchor_price * (f ** n)
        dn = anchor_price / (f ** n)
        rows.append(dict(type="Up",   n=n, level=round(up, 4)))
        rows.append(dict(type="Down", n=n, level=round(dn, 4)))
    df = pd.DataFrame(rows).sort_values(["type", "n"]).reset_index(drop=True)
    return df


# --------------------------- UI ---------------------------
with st.expander("Timing — planetary harmonics (geocentric / tropical / UTC)", expanded=True):
    c1, c2, c3 = st.columns([1, 1, 1.2])
    with c1:
        p1 = st.selectbox("Planet 1", PLANETS, index=PLANETS.index("Mars"))
        start_d = st.date_input("Start date (UTC)", value=datetime.utcnow().date())
    with c2:
        p2 = st.selectbox("Planet 2", PLANETS, index=PLANETS.index("Jupiter"))
        end_d = st.date_input("End date (UTC)", value=(datetime.utcnow().date() + timedelta(days=30)))
    with c3:
        orb = st.number_input("Orb (± degrees)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
        angles = st.multiselect(
            "Harmonic angles (deg)",
            [0, 30, 45, 60, 72, 90, 120, 135, 144, 150, 180],
            default=[0, 60, 90, 120, 180],
        )

    step = st.slider("Coarse step (minutes)", min_value=5, max_value=240, value=60)
    st.caption("All calculations are done in UTC. Times shown below are UTC.")

    run = st.button("Compute timing")
    timing_df = pd.DataFrame()

    if run:
        with st.spinner("Scanning for harmonic hits…"):
            start_dt = datetime.combine(start_d, time(0, 0), tzinfo=timezone.utc)
            end_dt = datetime.combine(end_d, time(23, 59), tzinfo=timezone.utc)
            timing_df = scan_harmonic_hits(
                p1=p1,
                p2=p2,
                start_dt_utc=start_dt,
                end_dt_utc=end_dt,
                angles=angles,
                orb=orb,
                coarse_step_minutes=step,
            )

    if not timing_df.empty:
        # A small bento-like summary
        s1, s2, s3 = st.columns([1, 1, 1])
        with s1:
            st.metric("Upcoming hits", f"{(timing_df['when_utc'] >= datetime.utcnow().replace(tzinfo=timezone.utc)).sum()}")
        with s2:
            st.metric("Active pair", f"{p1}–{p2}")
        with s3:
            days = (end_d - start_d).days + 1
            st.metric("Scan window", f"{days}d")

        st.dataframe(
            timing_df.rename(
                columns={
                    "when_utc": "When (UTC)",
                    "pair": "Pair",
                    "angle": "Angle",
                    "target": "Target",
                    "Δ": "Δ (deg)",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        if run:
            st.info("No hits found with current settings. Try a larger orb, longer window, or add more angles.")


with st.expander("Asset & price projections", expanded=True):
    asset = st.text_input("Asset (free text)", value="XAUUSD")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        anchor_date = st.date_input("Anchor date (UTC)", value=datetime.utcnow().date())
    with c2:
        anchor_hour = st.number_input("Hour (UTC)", min_value=0, max_value=23, value=0, step=1)
    with c3:
        anchor_min = st.number_input("Minute (UTC)", min_value=0, max_value=59, value=0, step=1)

    c4, c5 = st.columns([1, 1])
    with c4:
        anchor_price = st.number_input("Anchor price", min_value=0.0, value=2350.0, step=0.01, format="%.2f")
    with c5:
        st.caption("Set the anchor price/time from which to project levels.")

    st.markdown("##### Projection method")
    method = st.selectbox("Method", ["Percent grid", "Root ladder"], index=0)

    if method == "Percent grid":
        percent_str = st.text_input(
            "Percents (comma-separated)",
            value="12.5,25,33,37.5,50,62.5,66.67,75,87.5,100",
            help="e.g., 12.5,25,33,37.5,50…",
        )
        try:
            percents = [float(x.strip()) for x in percent_str.split(",") if x.strip()]
        except Exception:
            percents = []
            st.error("Could not parse percents. Please enter comma-separated numbers.")
        if st.button("Compute levels", key="pct_btn"):
            if percents:
                levels_df = percent_grid_levels(anchor_price, percents)
                st.dataframe(levels_df, hide_index=True, use_container_width=True)
            else:
                st.warning("Add at least one percent.")
    else:
        c1, c2 = st.columns([1, 1])
        with c1:
            root_step = st.number_input("√-step (for ladder)", value=0.013, min_value=0.0001, max_value=0.5, step=0.001, format="%.3f")
        with c2:
            turns = st.slider("Turns (up/down)", min_value=1, max_value=12, value=4)
        if st.button("Compute levels", key="root_btn"):
            levels_df = root_ladder_levels(anchor_price, root_step, turns)
            st.dataframe(levels_df, hide_index=True, use_container_width=True)


# Footer clock
st.caption(f"UTC: {datetime.utcnow().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

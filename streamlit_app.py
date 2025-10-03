# -*- coding: utf-8 -*-
import math
from functools import lru_cache
from datetime import datetime, date, time, timedelta, timezone

import numpy as np
import pandas as pd
import streamlit as st
from skyfield.api import load

# ---------------------------- App config ----------------------------
st.set_page_config(page_title="Luminara – Harmonics", page_icon=":milky_way:", layout="wide")

st.title("Luminara")
st.caption("Single-page prototype – planetary harmonic timing (geocentric / tropical / UTC) + price projections")

# ---------------------------- Helpers: Ephemeris & angles ----------------------------

PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]

# Map to Skyfield DE421 keys (handle barycenters -> .planet)
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

def _wrap360(x):
    return x % 360.0

def _min_angle_diff_deg(a, b):
    """Smallest unsigned separation between two angles (deg) in [0, 180]."""
    d = abs((a - b + 180.0) % 360.0 - 180.0)
    return d

@st.cache_resource(show_spinner=False)
def get_ephemeris():
    # ~22 MB; Streamlit Cloud caches under /home/appuser/.skyfield
    eph = load("de421.bsp")
    ts = load.timescale()
    return eph, ts

@lru_cache(maxsize=128)
def _planet(eph_name: str):
    eph, _ = get_ephemeris()
    body = eph[eph_name]
    # For barycenters, use the actual planet
    return getattr(body, "planet", body)

def geo_ecl_longitude_deg(body_name: str, t):
    """Geocentric, tropical, ecliptic longitude (deg) at Skyfield time t (UTC)."""
    eph, ts = get_ephemeris()
    earth = eph["earth"]
    body = _planet(_DE421_KEY[body_name.lower()])
    app = earth.at(t).observe(body).apparent()
    lon, lat, _ = app.ecliptic_latlon()  # tropical by default
    return _wrap360(lon.degrees)

def pair_separation_deg(p1: str, p2: str, t):
    """Unsigned separation (0..180) between two bodies at time t."""
    a = geo_ecl_longitude_deg(p1, t)
    b = geo_ecl_longitude_deg(p2, t)
    return _min_angle_diff_deg(a, b)

def _nearest_target(angle_deg: float, targets):
    """Return (min_diff, target) for the closest target angle."""
    best = (9999.0, None)
    for t in targets:
        d = _min_angle_diff_deg(angle_deg, t)
        if d < best[0]:
            best = (d, t)
    return best

def _refine_time(ts, t_left, t_right, p1, p2, target_deg, iters=18):
    """Binary-ish search to minimize |sep - target| between t_left and t_right."""
    t0 = t_left
    t1 = t_right
    for _ in range(iters):
        mid = t0 + (t1 - t0) * 0.5
        d0 = abs(pair_separation_deg(p1, p2, t0) - target_deg)
        dm = abs(pair_separation_deg(p1, p2, mid) - target_deg)
        d1 = abs(pair_separation_deg(p1, p2, t1) - target_deg)
        # keep the bracket where the min lies
        if d0 < dm and d0 < d1:
            t1 = mid
        elif d1 < dm and d1 < d0:
            t0 = mid
        else:
            # center looks best; tighten around it
            t0, t1 = t0 + (mid - t0) * 0.25, t1 - (t1 - mid) * 0.25
    candidates = [t0, t1, t0 + (t1 - t0) * 0.5]
    vals = [abs(pair_separation_deg(p1, p2, t) - target_deg) for t in candidates]
    idx = int(np.argmin(vals))
    return candidates[idx]

def _timespan_grid(ts, start_dt_utc: datetime, end_dt_utc: datetime, step_minutes: int):
    # inclusive grid
    total = max(1, int((end_dt_utc - start_dt_utc).total_seconds() // (60 * step_minutes)) + 1)
    dts = [start_dt_utc + timedelta(minutes=step_minutes * i) for i in range(total)]
    return ts.utc([dt.year for dt in dts],
                  [dt.month for dt in dts],
                  [dt.day for dt in dts],
                  [dt.hour for dt in dts],
                  [dt.minute for dt in dts],
                  [dt.second for dt in dts])

def scan_harmonics(p1, p2, start_dt_utc, end_dt_utc, targets, orb_deg=1.0, step_minutes=60):
    """
    Coarse scan on a time grid, then refine locally around best bins.
    Returns DataFrame with columns:
      ['UTC', 'Pair', 'AngleTarget', 'ExactAngle', 'Diff(arcmin)']
    """
    eph, ts = get_ephemeris()
    times = _timespan_grid(ts, start_dt_utc, end_dt_utc, step_minutes)
    seps = [pair_separation_deg(p1, p2, t) for t in times]

    rows = []
    for i, sep in enumerate(seps):
        dmin, tgt = _nearest_target(sep, targets)
        if dmin <= orb_deg:
            tL = times[max(0, i - 1)]
            tR = times[min(len(times) - 1, i + 1)]
            t_star = _refine_time(ts, tL, tR, p1, p2, tgt)
            exact = pair_separation_deg(p1, p2, t_star)
            diff_arcmin = abs(exact - tgt) * 60.0
            rows.append({
                "UTC": t_star.utc_datetime().replace(tzinfo=timezone.utc),
                "Pair": f"{p1}–{p2}",
                "AngleTarget": float(tgt),
                "ExactAngle": round(exact, 3),
                "Diff(arcmin)": round(diff_arcmin, 1),
            })

    if not rows:
        return pd.DataFrame(columns=["UTC", "Pair", "AngleTarget", "ExactAngle", "Diff(arcmin)"])

    df = pd.DataFrame(rows).drop_duplicates(subset=["UTC", "AngleTarget"]).sort_values("UTC").reset_index(drop=True)
    return df

def next_match_after(anchor_dt_utc, p1, p2, target_deg, search_days=200, step_minutes=60, orb_deg=0.5):
    """Find the next time AFTER anchor where separation hits target (±orb)."""
    start_dt = anchor_dt_utc + timedelta(minutes=step_minutes)
    end_dt = start_dt + timedelta(days=search_days)
    df = scan_harmonics(p1, p2, start_dt, end_dt, targets=[target_deg], orb_deg=orb_deg, step_minutes=step_minutes)
    if df.empty:
        return None
    return df.iloc[0]

# ---------------------------- Price projections ----------------------------

def percent_grid_levels(anchor_price: float, is_high: bool, perc_list=None):
    """
    Symmetric % grid around anchor.
    Returns DataFrame columns: ['Label','Level','Side','Δ%']
    """
    if perc_list is None:
        perc_list = [12.5, 25, 33.33, 37.5, 50, 62.5, 66.67, 75, 87.5, 100]
    rows = []
    for p in perc_list:
        up = anchor_price * (1 + p/100.0)
        dn = anchor_price * (1 - p/100.0)
        rows += [
            {"Label": f"+{p:.2f}%", "Level": up, "Side": "Above", "Δ%": +p},
            {"Label": f"-{p:.2f}%", "Level": dn, "Side": "Below", "Δ%": -p},
        ]
    df = pd.DataFrame(rows).sort_values("Level").reset_index(drop=True)
    return df

def sqrt_ladder_levels(anchor_price: float, root_step: float = 0.125, turns: int = 5):
    """
    Jenkins-like square-root ladder:
      level_k_up   = ( sqrt(P) + k*root_step )^2
      level_k_down = ( sqrt(P) - k*root_step )^2
    k = 1..turns
    Returns DataFrame columns: ['Label','Level','Side','Δ%']
    """
    s = math.sqrt(anchor_price)
    rows = [{"Label": "Anchor", "Level": anchor_price, "Side": "Anchor", "Δ%": 0.0}]
    for k in range(1, turns+1):
        up = (s + k*root_step)**2
        dn = (s - k*root_step)**2
        rows.append({"Label": f"+{k}·√step", "Level": up, "Side": "Above", "Δ%": (up/anchor_price - 1)*100})
        rows.append({"Label": f"-{k}·√step", "Level": dn, "Side": "Below", "Δ%": (dn/anchor_price - 1)*100})
    df = pd.DataFrame(rows).sort_values("Level").reset_index(drop=True)
    return df

def cross_join_time_price(df_time: pd.DataFrame, df_levels: pd.DataFrame):
    """
    Cartesian join so each timing hit gets all price levels.
    Adds helper columns for sorting.
    """
    if df_time.empty or df_levels.empty:
        return pd.DataFrame(columns=["UTC","Pair","AngleTarget","ExactAngle","Diff(arcmin)","Label","Level","Side","Δ%"])
    # cross join
    df_time["_tmp"] = 1
    df_levels["_tmp"] = 1
    out = pd.merge(df_time, df_levels, on="_tmp").drop(columns=["_tmp"])
    # ordering helpers
    out = out.sort_values(["UTC", "Level"]).reset_index(drop=True)
    return out

# ---------------------------- UI (single page) ----------------------------

with st.expander("Timing – planetary harmonics (geocentric / tropical / UTC)", expanded=True):
    col = st.columns([1, 1, 1, 2])
    with col[0]:
        p1 = st.selectbox("Planet 1", PLANETS, index=1)   # Moon default
    with col[1]:
        p2 = st.selectbox("Planet 2", PLANETS, index=0)   # Sun default
    with col[2]:
        orb = st.number_input("Orb (± degrees)", 0.0, 5.0, 1.0, 0.1)
    with col[3]:
        angle_choices = [0, 30, 45, 60, 72, 90, 120, 135, 144, 150, 180, 210, 225, 240, 270, 300, 315, 330]
        selected_angles = st.multiselect("Harmonic angles (deg)", angle_choices, default=[0, 60, 90, 120, 180])

    col_lo, col_hi, col_step = st.columns(3)
    with col_lo:
        start_date = st.date_input("Start date (UTC)", value=date.today())
    with col_hi:
        end_date = st.date_input("End date (UTC)", value=date.today() + timedelta(days=30))
    with col_step:
        step_minutes = st.slider("Coarse step (minutes)", min_value=5, max_value=240, value=60, step=5,
                                 help="Smaller step = slower but more precise.")

# Ensure UTC datetimes
start_dt_utc = datetime.combine(start_date, time(0, 0, 0), tzinfo=timezone.utc)
end_dt_utc   = datetime.combine(end_date,   time(23, 59, 59), tzinfo=timezone.utc)

# ---------------------------- Asset & Price ----------------------------
with st.expander("Asset & price projections", expanded=True):
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        asset = st.text_input("Asset (free text)", value="XAUUSD")
        anchor_type = st.selectbox("Anchor type", ["High", "Low"], index=0)
    with c2:
        anchor_date = st.date_input("Anchor date (UTC)", value=date.today())
        anchor_hour = st.number_input("Hour (UTC)", 0, 23, 0, 1)
    with c3:
        anchor_min  = st.number_input("Minute (UTC)", 0, 59, 0, 1)
        anchor_price = st.number_input("Anchor price", min_value=0.0, value=2350.0, step=0.1, format="%.2f")

    st.markdown("---")
    st.markdown("**Projection method**")
    m1, m2, m3 = st.columns([1.2,1.0,1.0])
    with m1:
        method = st.selectbox("Method", ["Percent grid", "Square-root ladder"], index=0)
    with m2:
        perc_list_txt = st.text_input("Percents (for Percent grid)", value="12.5,25,33.33,37.5,50,62.5,66.67,75,87.5,100")
    with m3:
        root_step = st.number_input("√-step (for Root ladder)", min_value=0.01, max_value=1.0, value=0.125, step=0.005)
        turns     = st.slider("Turns (up/down)", 1, 12, 5)

run = st.button("Compute timing + price", type="primary")
st.divider()

if run:
    # ---- 1) Timing scan
    with st.spinner("Computing timing hits…"):
        df_hits = scan_harmonics(
            p1, p2,
            start_dt_utc, end_dt_utc,
            targets=selected_angles,
            orb_deg=float(orb),
            step_minutes=int(step_minutes),
        )

    st.subheader("Timing results")
    if df_hits.empty:
        st.info("No timing matches found within your orb in the selected range.")
    else:
        st.dataframe(df_hits, use_container_width=True, hide_index=True)

    # ---- 2) Price projections
    with st.spinner("Building price projections…"):
        if method == "Percent grid":
            try:
                perc_vals = [float(x.strip()) for x in perc_list_txt.split(",") if x.strip()]
            except Exception:
                perc_vals = [12.5,25,33.33,37.5,50,62.5,66.67,75,87.5,100]
            df_levels = percent_grid_levels(anchor_price, is_high=(anchor_type=="High"), perc_list=perc_vals)
        else:
            df_levels = sqrt_ladder_levels(anchor_price, root_step=root_step, turns=int(turns))

    st.subheader(f"Price levels · {asset}")
    if df_levels.empty:
        st.info("No levels (unexpected).")
    else:
        st.dataframe(df_levels, use_container_width=True, hide_index=True)

    # ---- 3) Join: timing × price
    joined = cross_join_time_price(df_hits, df_levels)
    st.subheader("Joined timing × price")
    if joined.empty:
        st.info("No combined rows (likely because there were no hits).")
    else:
        # convenience: distance from anchor and side are already present
        joined["Anchor"] = anchor_price
        joined["Distance%"] = (joined["Level"]/anchor_price - 1.0) * 100.0
        joined = joined[["UTC","Pair","AngleTarget","ExactAngle","Diff(arcmin)","Label","Side","Level","Anchor","Distance%"]]
        st.dataframe(joined, use_container_width=True, hide_index=True)

        # downloads
        cdl, cdr = st.columns([1,1])
        with cdl:
            st.download_button(
                "Download timing CSV",
                df_hits.to_csv(index=False).encode("utf-8"),
                file_name=f"{asset}_timing.csv", mime="text/csv"
            )
        with cdr:
            st.download_button(
                "Download joined CSV",
                joined.to_csv(index=False).encode("utf-8"),
                file_name=f"{asset}_timing_levels.csv", mime="text/csv"
            )

# ---------------------------- Optional: next match tool ----------------------------
st.divider()
with st.expander("Next match after an anchor (optional)", expanded=False):
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        anchor_day = st.date_input("Anchor date (UTC)", value=date.today(), key="nm_day")
    with c2:
        anchor_h = st.number_input("Hour", 0, 23, 0, 1, key="nm_h")
    with c3:
        anchor_m = st.number_input("Minute", 0, 59, 0, 1, key="nm_m")
    with c4:
        target_angle = st.selectbox("Target angle", [0, 30, 45, 60, 72, 90, 120, 135, 144, 150, 180], index=2, key="nm_angle")

    c5, c6 = st.columns([1, 1])
    with c5:
        search_days = st.slider("Look ahead (days)", 1, 720, 200, 1, key="nm_days")
    with c6:
        refine_orb = st.number_input("Refine orb (±deg)", 0.1, 5.0, 0.5, 0.1, key="nm_orb")

    if st.button("Find next match"):
        anchor_dt = datetime.combine(anchor_day, time(anchor_h, anchor_m, 0), tzinfo=timezone.utc)
        with st.spinner("Searching…"):
            row = next_match_after(anchor_dt, p1, p2, float(target_angle),
                                   search_days=int(search_days), step_minutes=int(step_minutes), orb_deg=float(refine_orb))
        if row is None:
            st.warning("No match found in the search window.")
        else:
            st.success(f"Next ≈ **{row['AngleTarget']}°** at **{row['UTC']}** (Δ ≈ {row['Diff(arcmin)']}′).")
            st.dataframe(pd.DataFrame([row]), use_container_width=True, hide_index=True)

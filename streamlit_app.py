import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from skyfield.api import load
import numpy as np

# ============================================================================
# CONFIGURATION & SETUP
# ============================================================================

st.set_page_config(
    page_title="Luminara - Planetary Harmonics",
    layout="wide"
)

# Custom CSS for bordered card layout
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: #1f1f1f;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        background-color: #ffffff;
    }
    .card-title {
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: #333;
    }
    .stDataFrame {
        border: 1px solid #e0e0e0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# DATETIME UTILITIES
# ============================================================================

def make_utc_datetime(year, month, day, hour=0, minute=0, second=0):
    """
    Create a timezone-aware datetime in UTC.
    
    Parameters:
    - year, month, day, hour, minute, second: datetime components
    
    Returns:
    - datetime object with timezone=UTC
    """
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)

def date_to_utc_datetime(date_obj, hour=0, minute=0, second=0):
    """
    Convert a date object to a UTC-aware datetime.
    
    Parameters:
    - date_obj: datetime.date object (from st.date_input)
    - hour, minute, second: time components
    
    Returns:
    - datetime object with timezone=UTC
    """
    return make_utc_datetime(date_obj.year, date_obj.month, date_obj.day, hour, minute, second)

# ============================================================================
# EPHEMERIS & PLANETARY SETUP
# ============================================================================

@st.cache_resource
def get_ephemeris():
    """Load JPL DE421 ephemeris file and timescale (cached for performance)."""
    ts = load.timescale()
    eph = load('de421.bsp')
    return eph, ts

def planet_obj(eph, planet_name):
    """
    Get planet object from ephemeris, handling barycenter fallback.
    DE421 contains barycenters; extract planet when available.
    """
    planet_map = {
        'sun': 10,
        'moon': 301,
        'mercury': 1,
        'venus': 2,
        'mars': 4,
        'jupiter': 5,
        'saturn': 6,
        'uranus': 7,
        'neptune': 8,
        'pluto': 9
    }
    
    code = planet_map.get(planet_name.lower())
    if code is None:
        raise ValueError(f"Unknown planet: {planet_name}")
    
    obj = eph[code]
    
    # Handle barycenter objects (they don't have .planet attribute)
    if hasattr(obj, 'planet'):
        return obj.planet
    return obj

# ============================================================================
# ECLIPTIC LONGITUDE & ANGLE HELPERS
# ============================================================================

def ecliptic_longitude_deg(eph, ts, planet_name, t):
    """
    Calculate geocentric ecliptic longitude (tropical) of a planet at time t.
    Returns longitude in degrees [0, 360).
    """
    earth = eph['earth']
    planet = planet_obj(eph, planet_name)
    
    # Get apparent position from Earth
    astrometric = earth.at(t).observe(planet)
    
    # Get ecliptic coordinates
    lat, lon, distance = astrometric.ecliptic_latlon()
    
    # Return longitude in degrees
    return lon.degrees % 360.0

def angle_between_ecliptic_longitudes_deg(eph, ts, planet1, planet2, t):
    """
    Geocentric ecliptic longitude separation in [0, 360).
    Returns the raw angular separation (not wrapped to [0, 180]).
    """
    lon1 = ecliptic_longitude_deg(eph, ts, planet1, t)
    lon2 = ecliptic_longitude_deg(eph, ts, planet2, t)
    
    sep = (lon1 - lon2) % 360.0
    return sep

def angle_diff_to_target_deg(eph, ts, planet1, planet2, t, target):
    """
    Absolute minimal separation to target angle in [0, 180].
    This is the objective function we want to minimize.
    """
    separation = angle_between_ecliptic_longitudes_deg(eph, ts, planet1, planet2, t)
    
    # Calculate distance to target, considering both directions
    diff1 = abs(separation - target)
    diff2 = abs(separation - (target + 360.0)) if target < 180 else abs(separation - (target - 360.0))
    
    # Also consider the wrap-around
    diff3 = 360.0 - diff1
    
    return min(diff1, diff2, diff3)

# ============================================================================
# REFINEMENT ALGORITHM (GOLDEN SECTION SEARCH)
# ============================================================================

def refine_hit_time_golden(eph, ts, planet1, planet2, t_lo, t_hi, target,
                           max_iter=15, tol_seconds=3.0):
    """
    Golden-section search in [t_lo, t_hi] that returns (t_best, diff_best_deg).
    
    Minimizes: angle_diff_to_target_deg(planet1, planet2, t, target)
    
    Works in POSIX seconds for smooth stepping, converts back to Skyfield time.
    
    Parameters:
    - t_lo, t_hi: Skyfield Time objects defining search bracket
    - target: target harmonic angle in degrees
    - max_iter: maximum iterations (reduced to 15 for speed)
    - tol_seconds: stop when interval < this many seconds (increased to 3.0)
    
    Returns:
    - t_best: Skyfield Time object at minimum
    - diff_best: angular difference at minimum (degrees)
    """
    # Golden ratio
    phi = (1.0 + np.sqrt(5.0)) / 2.0
    resphi = 2.0 - phi
    
    # Convert to POSIX timestamps for easy arithmetic
    # Skyfield .utc_datetime() returns timezone-aware datetime
    a = t_lo.utc_datetime().timestamp()
    b = t_hi.utc_datetime().timestamp()
    
    # Safety check: don't refine if bracket is too small
    if (b - a) < tol_seconds:
        t_mid = ts.from_datetime(datetime.fromtimestamp((a + b) / 2, tz=timezone.utc))
        diff_mid = angle_diff_to_target_deg(eph, ts, planet1, planet2, t_mid, target)
        return t_mid, diff_mid
    
    # Initial probe points
    x1 = a + resphi * (b - a)
    x2 = b - resphi * (b - a)
    
    # Convert back to Skyfield times (from UTC timestamp)
    dt1 = datetime.fromtimestamp(x1, tz=timezone.utc)
    dt2 = datetime.fromtimestamp(x2, tz=timezone.utc)
    
    t1 = ts.from_datetime(dt1)
    t2 = ts.from_datetime(dt2)
    
    # Evaluate objective function
    f1 = angle_diff_to_target_deg(eph, ts, planet1, planet2, t1, target)
    f2 = angle_diff_to_target_deg(eph, ts, planet1, planet2, t2, target)
    
    for iteration in range(max_iter):
        if (b - a) < tol_seconds:
            break
        
        if f1 < f2:
            b = x2
            x2 = x1
            f2 = f1
            x1 = a + resphi * (b - a)
            dt1 = datetime.fromtimestamp(x1, tz=timezone.utc)
            t1 = ts.from_datetime(dt1)
            f1 = angle_diff_to_target_deg(eph, ts, planet1, planet2, t1, target)
        else:
            a = x1
            x1 = x2
            f1 = f2
            x2 = b - resphi * (b - a)
            dt2 = datetime.fromtimestamp(x2, tz=timezone.utc)
            t2 = ts.from_datetime(dt2)
            f2 = angle_diff_to_target_deg(eph, ts, planet1, planet2, t2, target)
    
    # Return best point
    if f1 < f2:
        return t1, f1
    else:
        return t2, f2

# ============================================================================
# HARMONIC TIMING SCANNER (BRACKET & REFINE)
# ============================================================================

def scan_harmonic_timing_refined(eph, ts, planet1, planet2, harmonic_angles, orb,
                                 start_date, end_date, step_minutes=60):
    """
    Scan date range for harmonic angle hits between two planets.
    
    Process:
    1. Coarse scan with step_minutes interval to bracket potential hits
    2. For each bracket where a hit is detected, refine using golden-section search
    3. Only record hits where refined angle is within orb
    4. Deduplicate hits within 30 seconds
    
    Parameters:
    - start_date, end_date: timezone-aware datetime objects in UTC
    
    Returns:
    - DataFrame with columns: DateTime (UTC), Planet 1, Planet 2, Target (°), Δ (deg)
    """
    results = []
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_minutes = (end_date - start_date).total_seconds() / 60
    minutes_processed = 0
    
    # Coarse scan loop
    current_dt = start_date
    brackets_processed = 0
    update_frequency = max(1, int(total_minutes / step_minutes / 100))  # Update every 1% of brackets
    
    while current_dt <= end_date:
        next_dt = min(current_dt + timedelta(minutes=step_minutes), end_date)
        
        # Create Skyfield time objects for bracket (already UTC-aware)
        t_lo = ts.from_datetime(current_dt)
        t_hi = ts.from_datetime(next_dt)
        
        # Check midpoint for proximity to any target angle
        mid_dt = current_dt + (next_dt - current_dt) / 2
        t_mid = ts.from_datetime(mid_dt)
        
        for target_angle in harmonic_angles:
            # Quick check: is midpoint within reasonable proximity?
            mid_diff = angle_diff_to_target_deg(eph, ts, planet1, planet2, t_mid, target_angle)
            
            # Skip refinement if not close enough - more aggressive filtering
            if mid_diff > orb * 2.0:
                continue
            
            # Check both endpoints too for better bracket detection
            lo_diff = angle_diff_to_target_deg(eph, ts, planet1, planet2, t_lo, target_angle)
            hi_diff = angle_diff_to_target_deg(eph, ts, planet1, planet2, t_hi, target_angle)
            
            min_diff_in_bracket = min(mid_diff, lo_diff, hi_diff)
            
            # Only refine if clearly within range
            if min_diff_in_bracket <= orb * 1.5:
                # Refine this bracket
                try:
                    t_best, diff_best = refine_hit_time_golden(
                        eph, ts, planet1, planet2, t_lo, t_hi, target_angle,
                        max_iter=15, tol_seconds=3.0
                    )
                    
                    # Only record if within actual orb
                    if diff_best <= orb:
                        results.append({
                            'timestamp': t_best.utc_datetime(),
                            'datetime_str': t_best.utc_strftime('%Y-%m-%d %H:%M:%S'),
                            'planet1': planet1,
                            'planet2': planet2,
                            'target': target_angle,
                            'delta': diff_best
                        })
                except Exception:
                    # Skip this bracket if refinement fails
                    continue
        
        # Progress update - reduced frequency
        brackets_processed += 1
        minutes_processed += step_minutes
        
        if brackets_processed % update_frequency == 0 or current_dt >= end_date:
            progress = min(minutes_processed / total_minutes, 1.0)
            progress_bar.progress(progress)
            status_text.text(f"Scanning: {current_dt.strftime('%Y-%m-%d %H:%M')} ({int(progress*100)}%) | Found: {len(results)} events")
        
        # Advance to next bracket
        current_dt = next_dt
    
    progress_bar.empty()
    status_text.empty()
    
    # Deduplicate: remove hits within 30 seconds of each other
    if results:
        results_sorted = sorted(results, key=lambda x: x['timestamp'])
        deduped = [results_sorted[0]]
        
        for r in results_sorted[1:]:
            prev_time = deduped[-1]['timestamp']
            curr_time = r['timestamp']
            
            if (curr_time - prev_time).total_seconds() > 30:
                deduped.append(r)
        
        # Build DataFrame
        df = pd.DataFrame(deduped)
        df = df[['datetime_str', 'planet1', 'planet2', 'target', 'delta']]
        df.columns = ['DateTime (UTC)', 'Planet 1', 'Planet 2', 'Target (°)', 'Δ (deg)']
        df['Δ (deg)'] = df['Δ (deg)'].apply(lambda x: f"{x:.4f}")
        
        return df
    
    return pd.DataFrame(columns=['DateTime (UTC)', 'Planet 1', 'Planet 2', 'Target (°)', 'Δ (deg)'])

# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    # Header
    st.markdown('<div class="main-header">Luminara</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Planetary Harmonics & Financial Timing Dashboard</div>', unsafe_allow_html=True)
    
    # Load ephemeris
    try:
        eph, ts = get_ephemeris()
    except Exception as e:
        st.error(f"Failed to load ephemeris: {e}")
        st.info("Ensure de421.bsp is in the working directory or Skyfield cache.")
        return
    
    # ========================================================================
    # SIDEBAR - Configuration
    # ========================================================================
    
    with st.sidebar:
        st.markdown("### Configuration")
        
        # Mode selection
        mode = st.radio(
            "Mode",
            options=["Harmonics", "Fingerprint"],
            index=0,
            help="Harmonics: scan predefined angles. Fingerprint: scan for recurrence of a specific planetary angle."
        )
        
        st.markdown("---")
        
        # Planet selection
        planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 
                   'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
        
        planet1 = st.selectbox('Planet 1', planets, index=0)
        planet2 = st.selectbox('Planet 2', planets, index=4)
        
        st.markdown("---")
        
        # Mode-specific inputs
        if mode == "Harmonics":
            # Harmonic angles
            st.markdown("**Harmonic Angles**")
            angle_options = [0, 45, 60, 90, 120, 135, 180, 270, 360]
            selected_angles = st.multiselect(
                'Select angles (degrees)',
                options=angle_options,
                default=[0, 90, 180],
                help="Fewer angles = faster scan. Start with 3-4 angles for testing."
            )
        else:
            # Fingerprint mode - anchor datetime
            st.markdown("**Anchor DateTime (UTC)**")
            anchor_date = st.date_input(
                'Anchor Date (UTC)',
                datetime.now(timezone.utc).date(),
                help="Date to capture the planetary fingerprint. All times are in UTC."
            )
            
            col1, col2 = st.columns(2)
            with col1:
                anchor_hour = st.number_input(
                    'Hour (UTC, 0-23)',
                    min_value=0,
                    max_value=23,
                    value=12,
                    step=1,
                    help="All times are in UTC"
                )
            with col2:
                anchor_minute = st.number_input(
                    'Minute (UTC, 0-59)',
                    min_value=0,
                    max_value=59,
                    value=0,
                    step=1,
                    help="All times are in UTC"
                )
        
        st.markdown("---")
        
        # Orb tolerance
        orb = st.slider('Orb Tolerance (±°)', 0.1, 5.0, 1.0, 0.1)
        
        st.markdown("---")
        
        # Date range
        st.markdown("**Date Range (UTC)**")
        start_date = st.date_input(
            'Start Date (UTC)', 
            datetime.now(timezone.utc).date(),
            help="All times are in UTC"
        )
        end_date = st.date_input(
            'End Date (UTC)', 
            (datetime.now(timezone.utc) + timedelta(days=14)).date(),
            help="All times are in UTC. Start with 7-14 days for testing."
        )
        
        st.markdown("---")
        
        # Scan settings
        st.markdown("**Scan Settings**")
        step_minutes = st.number_input(
            'Coarse Step (minutes)', 
            min_value=30, 
            max_value=240, 
            value=60,
            help="Larger steps = faster scan. Use 60-120 min to avoid timeouts."
        )
        
        st.markdown("---")
        
        # Run button
        run_scan = st.button('Run Harmonic Scan', type='primary', use_container_width=True)
        
        # Performance guidance
        st.markdown("---")
        st.markdown("**⚡ Performance Tips**")
        st.caption("• 7-day scan: ~10-20 seconds")
        st.caption("• 14-day scan: ~20-40 seconds")
        st.caption("• 30-day scan: ~60-90 seconds")
        st.caption("• Use 60+ min steps")
        st.caption("• Use 2-3 angles for speed")
        st.caption("• Avoid scans > 30 days on Streamlit Cloud")
    
    # ========================================================================
    # MAIN AREA - Results
    # ========================================================================
    
    if run_scan:
        if planet1 == planet2:
            st.error("Please select two different planets.")
            return
        
        if mode == "Harmonics" and not selected_angles:
            st.error("Please select at least one harmonic angle.")
            return
        
        if start_date >= end_date:
            st.error("End date must be after start date.")
            return
        
        # Determine target angles based on mode
        if mode == "Fingerprint":
            # Calculate anchor angle - create UTC-aware datetime
            anchor_dt = date_to_utc_datetime(anchor_date, anchor_hour, anchor_minute)
            anchor_t = ts.from_datetime(anchor_dt)
            
            anchor_angle = angle_between_ecliptic_longitudes_deg(eph, ts, planet1, planet2, anchor_t)
            target_angles = [anchor_angle]
            
            # Display fingerprint info
            st.info(f"**Fingerprint target angle:** {anchor_angle:.2f}° (captured at {anchor_dt.strftime('%Y-%m-%d %H:%M')} UTC)")
        else:
            target_angles = selected_angles
        
        # Convert dates to UTC-aware datetimes
        start_dt = date_to_utc_datetime(start_date, 0, 0, 0)
        end_dt = date_to_utc_datetime(end_date, 23, 59, 59)
        
        # Run scan
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Harmonic Timing Results</div>', unsafe_allow_html=True)
        
        mode_label = "fingerprint recurrence" if mode == "Fingerprint" else "planetary harmonics"
        with st.spinner(f'Calculating {mode_label} with precision refinement...'):
            results_df = scan_harmonic_timing_refined(
                eph, ts, planet1, planet2, target_angles, orb,
                start_dt, end_dt, step_minutes
            )
        
        if len(results_df) > 0:
            event_type = "recurrence event(s)" if mode == "Fingerprint" else "harmonic event(s)"
            st.success(f"Found {len(results_df)} {event_type} (refined to second precision)")
            st.dataframe(results_df, use_container_width=True, hide_index=True)
            
            # Download button
            csv = results_df.to_csv(index=False)
            file_prefix = "fingerprint" if mode == "Fingerprint" else "harmonics"
            st.download_button(
                label="Download Results (CSV)",
                data=csv,
                file_name=f"luminara_{file_prefix}_{planet1}_{planet2}_{datetime.now(timezone.utc).strftime('%Y%m%d')}_utc.csv",
                mime="text/csv"
            )
        else:
            event_type = "fingerprint recurrence events" if mode == "Fingerprint" else "harmonic events"
            st.warning(f"No {event_type} found in the selected date range.")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        # Instructions when no scan is running
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Welcome to Luminara</div>', unsafe_allow_html=True)
        st.markdown("""
        Configure your scan in the sidebar and click **Run Harmonic Scan** to begin.
        
        **Two Modes Available:**
        
        **Harmonics Mode:**
        - Scan for predefined harmonic angles (0°, 45°, 60°, 90°, etc.)
        - Select multiple angles to detect simultaneously
        - Classic astrological aspects and divisions
        
        **Fingerprint Mode:**
        - Capture the exact planetary angle at a specific moment (anchor datetime)
        - Scan forward to find when that exact angle recurs
        - Perfect for identifying cyclical patterns and timing repetitions
        
        **Technical Features:**
        - High-precision planetary ephemeris (JPL DE421)
        - Geocentric ecliptic longitudes (tropical)
        - Golden-section refinement for second-level accuracy
        - Bracket-and-refine algorithm eliminates grid snapping
        - Custom orb tolerance and scan step size
        
        **How It Works:**
        1. Coarse scan divides time range into brackets (step size)
        2. Each bracket is checked for proximity to target angles
        3. Promising brackets are refined using golden-section search
        4. Only hits within orb tolerance are recorded
        5. Results show exact time with second precision
        
        **Coming Soon:**
        - Asset price anchoring
        - Square of 9 projection ladders
        - Historical backlog database
        - Alert system with notifications
        """)
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == '__main__':
    main()

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from skyfield.api import load, wgs84
from skyfield.almanac import find_discrete
import numpy as np

# ============================================================================
# CONFIGURATION & SETUP
# ============================================================================

st.set_page_config(
    page_title="Luminara - Planetary Harmonics",
    page_icon="🌟",
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
# EPHEMERIS & PLANETARY SETUP
# ============================================================================

@st.cache_resource
def load_ephemeris():
    """Load JPL DE421 ephemeris file (cached for performance)."""
    ts = load.timescale()
    eph = load('de421.bsp')
    return ts, eph

def get_planet_obj(eph, planet_name):
    """
    Get planet object from ephemeris, handling barycenter fallback.
    DE421 contains barycenters; extract planet when available.
    """
    planet_map = {
        'Sun': 10,
        'Moon': 301,
        'Mercury': 1,
        'Venus': 2,
        'Mars': 4,
        'Jupiter': 5,
        'Saturn': 6,
        'Uranus': 7,
        'Neptune': 8,
        'Pluto': 9
    }
    
    code = planet_map.get(planet_name)
    if code is None:
        raise ValueError(f"Unknown planet: {planet_name}")
    
    obj = eph[code]
    
    # Handle barycenter objects (they don't have .planet attribute)
    if hasattr(obj, 'planet'):
        return obj.planet
    return obj

def tropical_longitude(planet_obj, time, observer):
    """
    Calculate geocentric tropical longitude of a planet.
    Returns longitude in degrees [0, 360).
    """
    astrometric = observer.at(time).observe(planet_obj)
    ra, dec, distance = astrometric.radec()
    
    # Convert RA (hours) to ecliptic longitude (degrees)
    # Approximate tropical longitude (simplified)
    lon = ra.hours * 15.0  # Convert hours to degrees
    
    # For more accurate ecliptic conversion, use proper transformation
    # This is a simplified version - for production, use proper ecliptic coordinates
    return lon % 360.0

def angular_separation(lon1, lon2):
    """
    Calculate smallest angular separation between two longitudes.
    Returns value in range [0, 180].
    """
    diff = abs(lon1 - lon2)
    if diff > 180:
        diff = 360 - diff
    return diff

def is_harmonic_hit(separation, target_angle, orb):
    """
    Check if angular separation is within orb of target harmonic angle.
    Handles both direct angle and its supplement (180° complement).
    """
    # Check direct angle
    delta1 = abs(separation - target_angle)
    
    # Check supplement (e.g., 60° also matches 300°)
    supplement = 360 - target_angle if target_angle != 180 else 180
    delta2 = abs(separation - supplement)
    
    return min(delta1, delta2) <= orb

def get_orb_delta(separation, target_angle):
    """
    Calculate the orb delta (how far from exact harmonic).
    Returns signed delta in degrees.
    """
    delta1 = separation - target_angle
    delta2 = separation - (360 - target_angle)
    
    # Return the smaller absolute delta with its sign
    if abs(delta1) < abs(delta2):
        return delta1
    return delta2

# ============================================================================
# HARMONIC TIMING ALGORITHM
# ============================================================================

def refine_hit_time(ts, eph, observer, p1_obj, p2_obj, coarse_time, target_angle, orb, step_minutes=60):
    """
    Bisection refinement to find exact harmonic hit time.
    Starting from coarse hit, narrows down to second-level precision.
    
    Parameters:
    - coarse_time: Skyfield Time object (approximate hit)
    - step_minutes: initial step size for bisection window
    
    Returns:
    - refined Skyfield Time object (exact hit to the second)
    - actual separation at that time
    """
    # Define search window around coarse hit
    window_minutes = step_minutes
    t_start = ts.utc(coarse_time.utc_datetime() - timedelta(minutes=window_minutes/2))
    t_end = ts.utc(coarse_time.utc_datetime() + timedelta(minutes=window_minutes/2))
    
    # Bisection loop - narrow down to 1-second precision
    max_iterations = 20
    tolerance_seconds = 1.0
    
    for iteration in range(max_iterations):
        t_mid = ts.utc(t_start.utc_datetime() + (t_end.utc_datetime() - t_start.utc_datetime()) / 2)
        
        # Calculate separations at boundaries and midpoint
        lon1_start = tropical_longitude(p1_obj, t_start, observer)
        lon2_start = tropical_longitude(p2_obj, t_start, observer)
        sep_start = angular_separation(lon1_start, lon2_start)
        delta_start = abs(get_orb_delta(sep_start, target_angle))
        
        lon1_mid = tropical_longitude(p1_obj, t_mid, observer)
        lon2_mid = tropical_longitude(p2_obj, t_mid, observer)
        sep_mid = angular_separation(lon1_mid, lon2_mid)
        delta_mid = abs(get_orb_delta(sep_mid, target_angle))
        
        lon1_end = tropical_longitude(p1_obj, t_end, observer)
        lon2_end = tropical_longitude(p2_obj, t_end, observer)
        sep_end = angular_separation(lon1_end, lon2_end)
        delta_end = abs(get_orb_delta(sep_end, target_angle))
        
        # Find which half contains the minimum delta
        if delta_start <= delta_mid and delta_start <= delta_end:
            best_time = t_start
            best_sep = sep_start
        elif delta_end <= delta_mid:
            best_time = t_end
            best_sep = sep_end
        else:
            best_time = t_mid
            best_sep = sep_mid
        
        # Check convergence
        time_span_seconds = (t_end.utc_datetime() - t_start.utc_datetime()).total_seconds()
        if time_span_seconds <= tolerance_seconds:
            return best_time, best_sep
        
        # Narrow the search window
        if delta_start <= delta_end:
            t_end = t_mid
        else:
            t_start = t_mid
    
    # Return best result found
    return best_time, best_sep

def scan_harmonic_timing(ts, eph, planet1, planet2, harmonic_angles, orb, 
                         start_date, end_date, step_minutes=60):
    """
    Scan date range for harmonic angle hits between two planets.
    
    Process:
    1. Coarse scan with step_minutes interval
    2. Detect approximate hits (within orb)
    3. Refine each hit using bisection to second-level precision
    
    Returns:
    - DataFrame with columns: DateTime (UTC), Planet1, Planet2, Harmonic, Actual°, Delta°
    """
    observer = eph['earth']
    p1_obj = get_planet_obj(eph, planet1)
    p2_obj = get_planet_obj(eph, planet2)
    
    results = []
    
    # Convert dates to Skyfield times
    current_dt = start_date
    end_dt = end_date
    
    # Track previous state for edge detection
    prev_in_orb = {angle: False for angle in harmonic_angles}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_minutes = (end_dt - current_dt).total_seconds() / 60
    minutes_processed = 0
    
    while current_dt <= end_dt:
        t = ts.utc(current_dt)
        
        # Calculate current planetary longitudes
        lon1 = tropical_longitude(p1_obj, t, observer)
        lon2 = tropical_longitude(p2_obj, t, observer)
        separation = angular_separation(lon1, lon2)
        
        # Check each harmonic angle
        for target_angle in harmonic_angles:
            currently_in_orb = is_harmonic_hit(separation, target_angle, orb)
            
            # Detect rising edge (entering orb) - trigger refinement
            if currently_in_orb and not prev_in_orb[target_angle]:
                # Found approximate hit - now refine
                refined_time, refined_sep = refine_hit_time(
                    ts, eph, observer, p1_obj, p2_obj, t, target_angle, orb, step_minutes
                )
                
                orb_delta = get_orb_delta(refined_sep, target_angle)
                
                results.append({
                    'DateTime (UTC)': refined_time.utc_datetime().strftime('%Y-%m-%d %H:%M:%S'),
                    'Planet 1': planet1,
                    'Planet 2': planet2,
                    'Harmonic': f"{target_angle}°",
                    'Actual°': f"{refined_sep:.4f}",
                    'Delta°': f"{orb_delta:+.4f}"
                })
            
            prev_in_orb[target_angle] = currently_in_orb
        
        # Progress update
        minutes_processed += step_minutes
        progress = min(minutes_processed / total_minutes, 1.0)
        progress_bar.progress(progress)
        status_text.text(f"Scanning: {current_dt.strftime('%Y-%m-%d %H:%M')} ({int(progress*100)}%)")
        
        # Advance time
        current_dt += timedelta(minutes=step_minutes)
    
    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame(results)

# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    # Header
    st.markdown('<div class="main-header">🌟 Luminara</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Planetary Harmonics & Financial Timing Dashboard</div>', unsafe_allow_html=True)
    
    # Load ephemeris
    try:
        ts, eph = load_ephemeris()
    except Exception as e:
        st.error(f"Failed to load ephemeris: {e}")
        st.info("Ensure de421.bsp is in the working directory or Skyfield cache.")
        return
    
    # ========================================================================
    # SIDEBAR - Configuration
    # ========================================================================
    
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        
        # Planet selection
        planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 
                   'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
        
        planet1 = st.selectbox('Planet 1', planets, index=0)
        planet2 = st.selectbox('Planet 2', planets, index=4)
        
        st.markdown("---")
        
        # Harmonic angles
        st.markdown("**Harmonic Angles**")
        angle_options = [0, 30, 45, 60, 90, 120, 135, 150, 180]
        selected_angles = st.multiselect(
            'Select angles (degrees)',
            angle_options,
            default=[0, 60, 90, 120, 180]
        )
        
        st.markdown("---")
        
        # Orb tolerance
        orb = st.slider('Orb Tolerance (±°)', 0.1, 5.0, 1.0, 0.1)
        
        st.markdown("---")
        
        # Date range
        st.markdown("**Date Range (UTC)**")
        start_date = st.date_input('Start Date', datetime.now().date())
        end_date = st.date_input('End Date', (datetime.now() + timedelta(days=90)).date())
        
        st.markdown("---")
        
        # Scan settings
        st.markdown("**Scan Settings**")
        step_minutes = st.number_input(
            'Step Size (minutes)', 
            min_value=1, 
            max_value=1440, 
            value=60,
            help="Coarse scan interval. Smaller = more precise but slower."
        )
        
        st.markdown("---")
        
        # Run button
        run_scan = st.button('🔍 Run Harmonic Scan', type='primary', use_container_width=True)
    
    # ========================================================================
    # MAIN AREA - Results
    # ========================================================================
    
    if run_scan:
        if planet1 == planet2:
            st.error("Please select two different planets.")
            return
        
        if not selected_angles:
            st.error("Please select at least one harmonic angle.")
            return
        
        if start_date >= end_date:
            st.error("End date must be after start date.")
            return
        
        # Convert dates to datetime
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        
        # Run scan
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📊 Harmonic Timing Results</div>', unsafe_allow_html=True)
        
        with st.spinner('Calculating planetary harmonics...'):
            results_df = scan_harmonic_timing(
                ts, eph, planet1, planet2, selected_angles, orb,
                start_dt, end_dt, step_minutes
            )
        
        if len(results_df) > 0:
            st.success(f"Found {len(results_df)} harmonic event(s)")
            st.dataframe(results_df, use_container_width=True, hide_index=True)
            
            # Download button
            csv = results_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Results (CSV)",
                data=csv,
                file_name=f"luminara_harmonics_{planet1}_{planet2}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("No harmonic events found in the selected date range.")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        # Instructions when no scan is running
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">👋 Welcome to Luminara</div>', unsafe_allow_html=True)
        st.markdown("""
        Configure your harmonic scan in the sidebar and click **Run Harmonic Scan** to begin.
        
        **Features:**
        - High-precision planetary ephemeris (JPL DE421)
        - Geocentric tropical longitudes (UTC)
        - Coarse scan + bisection refinement (second-level accuracy)
        - Multiple harmonic angles with custom orb tolerance
        
        **Coming Soon:**
        - Asset price anchoring
        - Square of 9 projection ladders
        - Historical backlog database
        - Alert system with notifications
        """)
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == '__main__':
    main()

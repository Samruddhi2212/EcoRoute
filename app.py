"""
app.py — EcoRoute Optimizer
A Streamlit app that finds eco-friendly routes and estimates CO2 emissions.
Supports address search and click-on-map stop entry.
"""

import streamlit as st
import streamlit.components.v1 as components
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from utils import (
    haversine,
    estimate_co2,
    nearest_neighbor_route,
    route_total_distance,
    eco_score,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="EcoRoute Optimizer",
    page_icon="🌿",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom click-map component
# ---------------------------------------------------------------------------
_click_map = components.declare_component("click_map", path="components/click_map")

def click_map(stops, key=None):
    """Render interactive Leaflet map. Returns {lat, lon} when user clicks."""
    return _click_map(
        stops=[{"name": s[0], "lat": s[1], "lon": s[2]} for s in stops],
        key=key,
        default=None,
    )

# ---------------------------------------------------------------------------
# Geocoding helpers (cached — no repeated API calls for same address)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def geocode(address):
    """Address string → (lat, lon) or None."""
    try:
        geo = Nominatim(user_agent="ecoroute-optimizer")
        loc = geo.geocode(address, timeout=5)
        if loc:
            return (loc.latitude, loc.longitude)
    except (GeocoderTimedOut, GeocoderServiceError):
        pass
    return None

@st.cache_data(show_spinner=False)
def reverse_geocode(lat, lon):
    """(lat, lon) → address string or fallback."""
    try:
        geo = Nominatim(user_agent="ecoroute-optimizer")
        loc = geo.reverse((lat, lon), timeout=5, language="en")
        if loc:
            return loc.address
    except (GeocoderTimedOut, GeocoderServiceError):
        pass
    return f"{lat:.5f}, {lon:.5f}"

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "stops_data" not in st.session_state:
    st.session_state.stops_data = [
        "Empire State Building, New York, NY",
        "Central Park, New York, NY",
        "Brooklyn Bridge, New York, NY",
        "Times Square, New York, NY",
    ]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
st.title("🌿 EcoRoute Optimizer")
st.caption("Plan smarter, greener routes — visualize your carbon footprint in real time.")

left, right = st.columns([1, 2])

# ── Left panel: settings + stops ──────────────────────────────────────────
with left:
    st.subheader("Settings")
    mode = st.selectbox(
        "Transport mode",
        options=["car", "bus", "train", "bike", "walk"],
        index=0,
    )

    st.subheader("Stops")
    st.caption("Type an address **or** click the map on the right to drop a pin.")

    updated = []
    for i, addr in enumerate(st.session_state.stops_data):
        cols = st.columns([5, 1])
        new_addr = cols[0].text_input(
            f"Stop {i + 1}", value=addr, key=f"addr_{i}",
            label_visibility="collapsed", placeholder="Enter address..."
        )
        if not cols[1].button("✕", key=f"del_{i}"):
            updated.append(new_addr)
    st.session_state.stops_data = updated

    c1, c2 = st.columns(2)
    if c1.button("+ Add stop"):
        st.session_state.stops_data.append("")
        st.rerun()

    optimize = st.checkbox("Optimize order (nearest-neighbor)", value=True)
    run = c2.button("Calculate Route", type="primary")

# ── Right panel: interactive map ──────────────────────────────────────────
with right:
    st.subheader("Map")

    # Resolve current addresses to coords for display on the click map
    resolved = []
    for addr in st.session_state.stops_data:
        if addr.strip():
            coords = geocode(addr.strip())
            if coords:
                resolved.append((addr.strip(), coords[0], coords[1]))

    # Render the clickable map; returns click coords when user clicks
    click_data = click_map(resolved, key="leaflet_map")

    # Handle click → reverse geocode → add to stops
    if click_data and isinstance(click_data, dict):
        lat, lon = click_data["lat"], click_data["lon"]
        with st.spinner("Looking up address for clicked point..."):
            address = reverse_geocode(lat, lon)
        st.session_state.stops_data.append(address)
        st.rerun()

# ---------------------------------------------------------------------------
# Calculate route
# ---------------------------------------------------------------------------
if run:
    stops = []
    errors = []

    with st.spinner("Looking up addresses..."):
        for addr in st.session_state.stops_data:
            if not addr.strip():
                continue
            coords = geocode(addr.strip())
            if coords:
                stops.append((addr.strip(), coords[0], coords[1]))
            else:
                errors.append(addr)

    if errors:
        st.warning(f"Could not find: {', '.join(errors)}. Try being more specific.")

    if len(stops) < 2:
        st.error("At least 2 valid addresses are needed.")
        st.stop()

    route = nearest_neighbor_route(stops) if optimize else stops
    distance = route_total_distance(route)
    co2 = estimate_co2(distance, mode)
    score = eco_score(distance, mode)

    # ── Metrics ────────────────────────────────────────────────────────────
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Distance", f"{distance:.1f} km")
    col2.metric("CO₂ Emissions", f"{co2:.0f} g")
    col3.metric("Eco Score", f"{score} / 100")

    # ── Static result map (folium) ─────────────────────────────────────────
    st.subheader("Optimized Route")
    center_lat = sum(s[1] for s in route) / len(route)
    center_lon = sum(s[2] for s in route) / len(route)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles="CartoDB positron")
    for i, (name, lat, lon) in enumerate(route):
        folium.Marker(
            [lat, lon], popup=name, tooltip=f"{i + 1}. {name}",
            icon=folium.Icon(color="green" if i == 0 else "blue",
                             icon="leaf" if i == 0 else "info-sign"),
        ).add_to(m)
    folium.PolyLine([[s[1], s[2]] for s in route], color="#2ecc71", weight=4, opacity=0.8).add_to(m)
    components.html(m.get_root().render(), height=460)

    # ── Route table ────────────────────────────────────────────────────────
    st.subheader("Route breakdown")
    lines = ["| # | Segment | Distance (km) | CO₂ (g) |",
             "|---|---------|--------------|---------|"]
    for i in range(len(route) - 1):
        seg_dist = haversine(route[i][1], route[i][2], route[i + 1][1], route[i + 1][2])
        seg_co2 = estimate_co2(seg_dist, mode)
        lines.append(f"| {i+1}→{i+2} | {route[i][0]} → {route[i+1][0]} | {seg_dist:.2f} | {seg_co2:.1f} |")
    st.markdown("\n".join(lines))

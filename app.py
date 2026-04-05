"""
app.py — EcoRoute Optimizer
A Streamlit app that finds eco-friendly routes and estimates CO2 emissions.
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
    return _click_map(
        stops=[{"name": s[0], "lat": s[1], "lon": s[2]} for s in stops],
        key=key,
        default=None,
    )

# ---------------------------------------------------------------------------
# Geocoding helpers
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def geocode(address):
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
if "start" not in st.session_state:
    st.session_state.start = "Empire State Building, New York, NY"
if "end" not in st.session_state:
    st.session_state.end = "Brooklyn Bridge, New York, NY"
if "waypoints" not in st.session_state:
    st.session_state.waypoints = [
        "Central Park, New York, NY",
        "Times Square, New York, NY",
    ]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
st.title("🌿 EcoRoute Optimizer")
st.caption("Plan smarter, greener routes — visualize your carbon footprint in real time.")

left, right = st.columns([1, 2])

# ── Left panel ─────────────────────────────────────────────────────────────
with left:
    st.subheader("Settings")
    mode = st.selectbox(
        "Transport mode",
        options=["car", "bus", "train", "bike", "walk"],
        index=0,
    )

    st.subheader("Route")
    st.caption("Type an address **or** click the map to drop a pin.")

    # Start
    st.markdown("🟢 **Start**")
    st.session_state.start = st.text_input(
        "Start", value=st.session_state.start,
        label_visibility="collapsed", placeholder="Starting address...",
        key="start_input"
    )

    # Waypoints
    st.markdown("🔵 **Stops**")
    updated_waypoints = []
    for i, wp in enumerate(st.session_state.waypoints):
        cols = st.columns([5, 1])
        new_wp = cols[0].text_input(
            f"Stop {i+1}", value=wp, key=f"wp_{i}",
            label_visibility="collapsed", placeholder="Address..."
        )
        if not cols[1].button("✕", key=f"del_wp_{i}"):
            updated_waypoints.append(new_wp)
    st.session_state.waypoints = updated_waypoints

    if st.button("＋ Add stop"):
        st.session_state.waypoints.append("")
        st.rerun()

    # End
    st.markdown("🔴 **End**")
    st.session_state.end = st.text_input(
        "End", value=st.session_state.end,
        label_visibility="collapsed", placeholder="Destination address...",
        key="end_input"
    )

    st.divider()
    optimize = st.checkbox("Optimize stop order (nearest-neighbor)", value=True)
    run = st.button("Calculate Route", type="primary", use_container_width=True)

# ── Right panel: interactive map ───────────────────────────────────────────
with right:
    st.subheader("Map")
    st.caption("Click anywhere to add a stop.")

    # Build resolved stops list for the click map display
    resolved = []
    for addr in [st.session_state.start] + st.session_state.waypoints + [st.session_state.end]:
        if addr.strip():
            coords = geocode(addr.strip())
            if coords:
                resolved.append((addr.strip(), coords[0], coords[1]))

    click_data = click_map(resolved, key="leaflet_map")

    # Handle map click → reverse geocode → add as waypoint
    if click_data and isinstance(click_data, dict):
        lat, lon = click_data["lat"], click_data["lon"]
        with st.spinner("Looking up address..."):
            address = reverse_geocode(lat, lon)
        st.session_state.waypoints.append(address)
        st.rerun()

# ---------------------------------------------------------------------------
# Calculate route
# ---------------------------------------------------------------------------
if run:
    def resolve(addr):
        return geocode(addr.strip()) if addr.strip() else None

    errors = []

    start_coords = resolve(st.session_state.start)
    if not start_coords:
        errors.append(f"Start: {st.session_state.start}")

    end_coords = resolve(st.session_state.end)
    if not end_coords:
        errors.append(f"End: {st.session_state.end}")

    waypoint_stops = []
    with st.spinner("Looking up addresses..."):
        for wp in st.session_state.waypoints:
            if not wp.strip():
                continue
            coords = resolve(wp)
            if coords:
                waypoint_stops.append((wp.strip(), coords[0], coords[1]))
            else:
                errors.append(wp)

    if errors:
        st.warning(f"Could not find: {', '.join(errors)}")

    if not start_coords or not end_coords:
        st.error("Start and End addresses are required.")
        st.stop()

    # Optimize waypoints only; start and end are fixed
    if optimize and len(waypoint_stops) > 1:
        waypoint_stops = nearest_neighbor_route(waypoint_stops)

    route = (
        [(st.session_state.start.strip(), start_coords[0], start_coords[1])]
        + waypoint_stops
        + [(st.session_state.end.strip(), end_coords[0], end_coords[1])]
    )

    distance = route_total_distance(route)
    co2 = estimate_co2(distance, mode)
    score = eco_score(distance, mode)

    # ── Metrics ────────────────────────────────────────────────────────────
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Distance", f"{distance:.1f} km")
    col2.metric("CO₂ Emissions", f"{co2:.0f} g")
    col3.metric("Eco Score", f"{score} / 100")

    # ── Result map ─────────────────────────────────────────────────────────
    st.subheader("Optimized Route")
    center_lat = sum(s[1] for s in route) / len(route)
    center_lon = sum(s[2] for s in route) / len(route)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles="CartoDB positron")

    for i, (name, lat, lon) in enumerate(route):
        if i == 0:
            color, icon = "green", "play"
        elif i == len(route) - 1:
            color, icon = "red", "stop"
        else:
            color, icon = "blue", "info-sign"

        folium.Marker(
            [lat, lon], popup=name, tooltip=f"{i+1}. {name}",
            icon=folium.Icon(color=color, icon=icon),
        ).add_to(m)

    folium.PolyLine([[s[1], s[2]] for s in route], color="#2ecc71", weight=4, opacity=0.8).add_to(m)
    components.html(m.get_root().render(), height=460)

    # ── Route table ────────────────────────────────────────────────────────
    st.subheader("Route breakdown")
    lines = ["| # | Segment | Distance (km) | CO₂ (g) |",
             "|---|---------|--------------|---------|"]
    for i in range(len(route) - 1):
        seg_dist = haversine(route[i][1], route[i][2], route[i+1][1], route[i+1][2])
        seg_co2 = estimate_co2(seg_dist, mode)
        lines.append(f"| {i+1}→{i+2} | {route[i][0]} → {route[i+1][0]} | {seg_dist:.2f} | {seg_co2:.1f} |")
    st.markdown("\n".join(lines))

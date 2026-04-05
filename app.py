"""
app.py — EcoRoute Optimizer
A Streamlit app that finds eco-friendly routes and estimates CO2 emissions.
"""

import streamlit as st
import streamlit.components.v1 as components
import folium

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

st.title("🌿 EcoRoute Optimizer")
st.caption("Plan smarter, greener routes — visualize your carbon footprint in real time.")

# ---------------------------------------------------------------------------
# Sidebar — transport mode & stop input
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    mode = st.selectbox(
        "Transport mode",
        options=["car", "bus", "train", "bike", "walk"],
        index=0,
    )

    st.subheader("Stops")
    st.caption("Edit name, lat, lon for each stop.")

    if "stops_data" not in st.session_state:
        st.session_state.stops_data = [
            {"Name": "Home",    "Lat": 40.7128, "Lon": -74.0060},
            {"Name": "Grocery", "Lat": 40.7282, "Lon": -73.7949},
            {"Name": "Office",  "Lat": 40.6892, "Lon": -74.0445},
            {"Name": "Park",    "Lat": 40.7549, "Lon": -73.9840},
        ]

    updated = []
    for i, stop in enumerate(st.session_state.stops_data):
        cols = st.columns([2, 2, 2, 1])
        name = cols[0].text_input("Name", value=stop["Name"], key=f"name_{i}", label_visibility="collapsed")
        lat  = cols[1].number_input("Lat",  value=float(stop["Lat"]), format="%.4f", key=f"lat_{i}",  label_visibility="collapsed")
        lon  = cols[2].number_input("Lon",  value=float(stop["Lon"]), format="%.4f", key=f"lon_{i}",  label_visibility="collapsed")
        if not cols[3].button("✕", key=f"del_{i}"):
            updated.append({"Name": name, "Lat": lat, "Lon": lon})
    st.session_state.stops_data = updated

    if st.button("+ Add stop"):
        st.session_state.stops_data.append({"Name": "New Stop", "Lat": 40.7128, "Lon": -74.0060})
        st.rerun()

    optimize = st.checkbox("Optimize route order (nearest-neighbor)", value=True)
    run = st.button("Calculate Route", type="primary")

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
if run:
    stops = [
        (s["Name"], s["Lat"], s["Lon"])
        for s in st.session_state.stops_data
        if s["Name"] and s["Lat"] is not None and s["Lon"] is not None
    ]

    if len(stops) < 2:
        st.warning("Add at least two stops to calculate a route.")
        st.stop()

    route = nearest_neighbor_route(stops) if optimize else stops

    distance = route_total_distance(route)
    co2 = estimate_co2(distance, mode)
    score = eco_score(distance, mode)

    # -----------------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Distance", f"{distance:.1f} km")
    col2.metric("CO₂ Emissions", f"{co2:.0f} g")
    col3.metric("Eco Score", f"{score} / 100")

    # -----------------------------------------------------------------------
    # Map — rendered as raw HTML to avoid streamlit-folium / pandas
    # -----------------------------------------------------------------------
    center_lat = sum(s[1] for s in route) / len(route)
    center_lon = sum(s[2] for s in route) / len(route)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")

    for i, (name, lat, lon) in enumerate(route):
        folium.Marker(
            [lat, lon],
            popup=name,
            tooltip=f"{i + 1}. {name}",
            icon=folium.Icon(
                color="green" if i == 0 else "blue",
                icon="leaf" if i == 0 else "info-sign",
            ),
        ).add_to(m)

    coords = [[s[1], s[2]] for s in route]
    folium.PolyLine(coords, color="#2ecc71", weight=4, opacity=0.8).add_to(m)

    # Render to HTML string — no pandas involved
    map_html = m.get_root().render()
    components.html(map_html, height=500)

    # -----------------------------------------------------------------------
    # Route table — plain markdown, no pandas
    # -----------------------------------------------------------------------
    st.subheader("Route breakdown")
    lines = ["| Segment | Distance (km) | CO₂ (g) |", "|---------|--------------|---------|"]
    for i in range(len(route) - 1):
        seg_dist = haversine(route[i][1], route[i][2], route[i + 1][1], route[i + 1][2])
        seg_co2 = estimate_co2(seg_dist, mode)
        lines.append(f"| {route[i][0]} → {route[i + 1][0]} | {seg_dist:.2f} | {seg_co2:.1f} |")
    st.markdown("\n".join(lines))

else:
    st.info("Configure your stops in the sidebar and click **Calculate Route**.")

"""
app.py — EcoRoute Optimizer
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
st.set_page_config(page_title="EcoRoute Optimizer", page_icon="🌿", layout="wide")

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------
THEMES = {
    "🍂 Autumn": {
        "primary":    "#c2410c",
        "secondary":  "#92400e",
        "accent":     "#f97316",
        "bg":         "#fff7ed",
        "card":       "#ffedd5",
        "border":     "#fed7aa",
        "text":       "#431407",
        "muted":      "#9a3412",
        "green":      "#4d7c0f",
        "grad_a":     "#c2410c",
        "grad_b":     "#b45309",
    },
    "🌸 Spring": {
        "primary":    "#16a34a",
        "secondary":  "#0d9488",
        "accent":     "#f472b6",
        "bg":         "#f0fdf4",
        "card":       "#dcfce7",
        "border":     "#86efac",
        "text":       "#14532d",
        "muted":      "#166534",
        "green":      "#15803d",
        "grad_a":     "#16a34a",
        "grad_b":     "#0d9488",
    },
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "theme"     not in st.session_state: st.session_state.theme     = "🌸 Spring"
if "start"     not in st.session_state: st.session_state.start     = "Empire State Building, New York, NY"
if "end"       not in st.session_state: st.session_state.end       = "Brooklyn Bridge, New York, NY"
if "waypoints" not in st.session_state: st.session_state.waypoints = ["Central Park, New York, NY", "Times Square, New York, NY"]

t = THEMES[st.session_state.theme]

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
  .stApp {{ background-color: {t['bg']}; }}

  /* Header banner */
  .eco-header {{
    background: linear-gradient(135deg, {t['grad_a']}, {t['grad_b']});
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 24px;
    color: white;
  }}
  .eco-header h1 {{ margin: 0; font-size: 2.2rem; font-weight: 700; }}
  .eco-header p  {{ margin: 6px 0 0; opacity: 0.88; font-size: 1rem; }}

  /* Cards */
  .eco-card {{
    background: {t['card']};
    border: 1.5px solid {t['border']};
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 14px;
  }}
  .eco-card-label {{
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {t['muted']};
    margin-bottom: 6px;
  }}

  /* Stop row label chips */
  .chip-start {{ background:{t['green']}; color:white; border-radius:20px; padding:2px 12px; font-size:0.78rem; font-weight:600; display:inline-block; margin-bottom:8px; }}
  .chip-stop  {{ background:{t['primary']}; color:white; border-radius:20px; padding:2px 12px; font-size:0.78rem; font-weight:600; display:inline-block; margin-bottom:8px; }}
  .chip-end   {{ background:#dc2626; color:white; border-radius:20px; padding:2px 12px; font-size:0.78rem; font-weight:600; display:inline-block; margin-bottom:8px; }}

  /* Metric cards */
  .metric-row {{ display:flex; gap:16px; margin:20px 0; }}
  .metric-card {{
    flex:1; background:{t['card']}; border:1.5px solid {t['border']};
    border-radius:12px; padding:16px 20px; text-align:center;
  }}
  .metric-card .val {{ font-size:1.9rem; font-weight:700; color:{t['primary']}; }}
  .metric-card .lbl {{ font-size:0.78rem; color:{t['muted']}; font-weight:500; margin-top:2px; }}

  /* Section title */
  .sec-title {{
    font-size:1rem; font-weight:700; color:{t['text']};
    margin:18px 0 10px; border-left:4px solid {t['primary']};
    padding-left:10px;
  }}

  /* Override Streamlit button */
  div.stButton > button {{
    background: {t['primary']} !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
  }}
  div.stButton > button:hover {{
    background: {t['secondary']} !important;
    color: white !important;
  }}

  /* Remove default input borders */
  .stTextInput > div > div > input {{
    border-radius: 8px !important;
    border: 1.5px solid {t['border']} !important;
    background: white !important;
  }}
  .stTextInput > div > div > input:focus {{
    border-color: {t['primary']} !important;
    box-shadow: 0 0 0 2px {t['border']} !important;
  }}

  /* Divider line */
  hr {{ border-color: {t['border']}; }}

  /* Hide Streamlit branding */
  #MainMenu, footer {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def geocode(address):
    try:
        loc = Nominatim(user_agent="ecoroute-optimizer").geocode(address, timeout=5)
        if loc: return (loc.latitude, loc.longitude)
    except (GeocoderTimedOut, GeocoderServiceError): pass
    return None

@st.cache_data(show_spinner=False)
def reverse_geocode(lat, lon):
    try:
        loc = Nominatim(user_agent="ecoroute-optimizer").reverse((lat, lon), timeout=5, language="en")
        if loc: return loc.address
    except (GeocoderTimedOut, GeocoderServiceError): pass
    return f"{lat:.5f}, {lon:.5f}"

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="eco-header">
  <h1>🌿 EcoRoute Optimizer</h1>
  <p>Plan smarter, greener routes — visualize your carbon footprint in real time.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Layout: left panel + right map
# ---------------------------------------------------------------------------
left, right = st.columns([1, 1.6], gap="large")

with left:
    # Theme + mode row
    c1, c2 = st.columns(2)
    st.session_state.theme = c1.selectbox("Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme), label_visibility="collapsed")
    t = THEMES[st.session_state.theme]  # refresh after potential change
    mode = c2.selectbox("Transport mode", ["car", "bus", "train", "bike", "walk"], label_visibility="collapsed")

    st.markdown('<div class="sec-title">Plan your route</div>', unsafe_allow_html=True)
    st.caption("Type an address for each stop.")

    # Start
    st.markdown('<span class="chip-start">🟢 Start</span>', unsafe_allow_html=True)
    st.session_state.start = st.text_input("start", value=st.session_state.start,
        label_visibility="collapsed", placeholder="Starting address…", key="start_input")

    # Waypoints
    st.markdown('<span class="chip-stop">🔵 Stops</span>', unsafe_allow_html=True)
    updated_wps = []
    for i, wp in enumerate(st.session_state.waypoints):
        ca, cb = st.columns([5, 1])
        new_wp = ca.text_input(f"wp{i}", value=wp, key=f"wp_{i}",
            label_visibility="collapsed", placeholder=f"Stop {i+1} address…")
        if not cb.button("✕", key=f"del_{i}"):
            updated_wps.append(new_wp)
    st.session_state.waypoints = updated_wps

    if st.button("＋ Add stop", use_container_width=True):
        st.session_state.waypoints.append("")
        st.rerun()

    # End
    st.markdown('<span class="chip-end">🔴 End</span>', unsafe_allow_html=True)
    st.session_state.end = st.text_input("end", value=st.session_state.end,
        label_visibility="collapsed", placeholder="Destination address…", key="end_input")

    st.markdown("")
    optimize = st.checkbox("Optimize stop order (nearest-neighbor)", value=True)
    run = st.button("🗺️ Calculate Route", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Right panel: live preview map
# ---------------------------------------------------------------------------
with right:
    st.markdown('<div class="sec-title">Map preview</div>', unsafe_allow_html=True)

    # Resolve all current addresses for the preview
    all_addrs = [st.session_state.start] + st.session_state.waypoints + [st.session_state.end]
    preview_stops = []
    for addr in all_addrs:
        if addr.strip():
            coords = geocode(addr.strip())
            if coords:
                preview_stops.append((addr.strip(), coords[0], coords[1]))

    if preview_stops:
        clat = sum(s[1] for s in preview_stops) / len(preview_stops)
        clon = sum(s[2] for s in preview_stops) / len(preview_stops)
        pm = folium.Map(location=[clat, clon], zoom_start=13, tiles="CartoDB positron")

        for i, (name, lat, lon) in enumerate(preview_stops):
            if i == 0:
                color = "green"
            elif i == len(preview_stops) - 1:
                color = "red"
            else:
                color = t["primary"].lstrip("#")  # fallback
                color = "orange" if "Autumn" in st.session_state.theme else "blue"

            folium.Marker([lat, lon], tooltip=f"{i+1}. {name}",
                icon=folium.Icon(color=color, icon="circle", prefix="fa")).add_to(pm)

        if len(preview_stops) > 1:
            folium.PolyLine([[s[1], s[2]] for s in preview_stops],
                color=t["primary"], weight=3, opacity=0.6, dash_array="6").add_to(pm)

        components.html(pm.get_root().render(), height=480)
    else:
        st.markdown(f"""
        <div style="height:480px; background:{t['card']}; border:1.5px dashed {t['border']};
             border-radius:12px; display:flex; align-items:center; justify-content:center;
             flex-direction:column; color:{t['muted']};">
          <div style="font-size:2.5rem;">🗺️</div>
          <div style="font-size:0.95rem; margin-top:10px;">Enter addresses to see the map</div>
        </div>
        """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if run:
    errors = []
    start_c = geocode(st.session_state.start.strip()) if st.session_state.start.strip() else None
    end_c   = geocode(st.session_state.end.strip())   if st.session_state.end.strip()   else None

    if not start_c: errors.append(st.session_state.start)
    if not end_c:   errors.append(st.session_state.end)

    wps = []
    with st.spinner("Looking up addresses…"):
        for wp in st.session_state.waypoints:
            if not wp.strip(): continue
            c = geocode(wp.strip())
            if c: wps.append((wp.strip(), c[0], c[1]))
            else: errors.append(wp)

    if errors:
        st.warning(f"Could not find: {', '.join(errors)}")
    if not start_c or not end_c:
        st.error("Start and End addresses are required.")
        st.stop()

    if optimize and len(wps) > 1:
        wps = nearest_neighbor_route(wps)

    route = [(st.session_state.start.strip(), start_c[0], start_c[1])] + wps + \
            [(st.session_state.end.strip(),   end_c[0],   end_c[1])]

    dist  = route_total_distance(route)
    co2   = estimate_co2(dist, mode)
    score = eco_score(dist, mode)

    st.markdown("---")

    # Metrics
    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-card">
        <div class="val">{dist:.1f} km</div>
        <div class="lbl">Total Distance</div>
      </div>
      <div class="metric-card">
        <div class="val">{co2:.0f} g</div>
        <div class="lbl">CO₂ Emissions</div>
      </div>
      <div class="metric-card">
        <div class="val">{score} / 100</div>
        <div class="lbl">Eco Score</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Result map
    st.markdown('<div class="sec-title">Optimized Route</div>', unsafe_allow_html=True)
    clat = sum(s[1] for s in route) / len(route)
    clon = sum(s[2] for s in route) / len(route)
    m = folium.Map(location=[clat, clon], zoom_start=13, tiles="CartoDB positron")

    for i, (name, lat, lon) in enumerate(route):
        color = "green" if i == 0 else ("red" if i == len(route)-1 else
                ("orange" if "Autumn" in st.session_state.theme else "blue"))
        folium.Marker([lat, lon], popup=name, tooltip=f"{i+1}. {name}",
            icon=folium.Icon(color=color, icon="circle", prefix="fa")).add_to(m)

    folium.PolyLine([[s[1], s[2]] for s in route],
        color=t["primary"], weight=4, opacity=0.85).add_to(m)
    components.html(m.get_root().render(), height=460)

    # Breakdown table
    st.markdown('<div class="sec-title">Route breakdown</div>', unsafe_allow_html=True)
    rows_html = ""
    for i in range(len(route) - 1):
        sd = haversine(route[i][1], route[i][2], route[i+1][1], route[i+1][2])
        sc = estimate_co2(sd, mode)
        rows_html += f"<tr><td>{i+1}→{i+2}</td><td>{route[i][0]} → {route[i+1][0]}</td><td>{sd:.2f}</td><td>{sc:.1f}</td></tr>"

    st.markdown(f"""
    <table style="width:100%; border-collapse:collapse; font-size:0.88rem;">
      <thead>
        <tr style="background:{t['card']}; color:{t['text']};">
          <th style="padding:10px 12px; text-align:left; border-bottom:2px solid {t['border']};">#</th>
          <th style="padding:10px 12px; text-align:left; border-bottom:2px solid {t['border']};">Segment</th>
          <th style="padding:10px 12px; text-align:left; border-bottom:2px solid {t['border']};">Distance (km)</th>
          <th style="padding:10px 12px; text-align:left; border-bottom:2px solid {t['border']};">CO₂ (g)</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)

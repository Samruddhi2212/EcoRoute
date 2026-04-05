"""
app.py — EcoRoute Optimizer  |  Itinerary Planner
"""

import streamlit as st
import streamlit.components.v1 as components
import folium
from datetime import datetime, time as dtime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from utils import (
    haversine, estimate_co2, nearest_neighbor_route,
    route_total_distance, eco_score,
    build_schedule, fmt_time, fmt_duration, travel_time_minutes,
)

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="EcoRoute Optimizer", page_icon="🌿", layout="wide")

# ── Color palette (warm sage-green + amber, eco-inspired) ───────────────────
C = {
    "primary":   "#2d6a4f",   # deep forest green
    "secondary": "#40916c",   # medium green
    "accent":    "#f4a261",   # warm amber
    "accent2":   "#e76f51",   # terracotta
    "bg":        "#f8f9f4",   # off-white with green tint
    "card":      "#ffffff",
    "border":    "#d8e8d8",
    "text":      "#1b2d24",
    "muted":     "#52796f",
    "start":     "#2d6a4f",
    "stop":      "#457b9d",
    "end":       "#e76f51",
}

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {C['bg']}; }}

.hero {{
    background: linear-gradient(135deg, {C['primary']} 0%, {C['secondary']} 60%, {C['accent']} 130%);
    border-radius: 16px; padding: 30px 36px; margin-bottom: 24px; color: white;
}}
.hero h1 {{ margin:0; font-size:2rem; font-weight:700; letter-spacing:-0.5px; }}
.hero p  {{ margin:6px 0 0; opacity:.85; font-size:.95rem; }}

.card {{
    background: {C['card']}; border: 1.5px solid {C['border']};
    border-radius: 12px; padding: 16px 18px; margin-bottom: 12px;
}}
.sec {{ font-size:.8rem; font-weight:700; text-transform:uppercase;
        letter-spacing:.08em; color:{C['muted']}; margin:16px 0 8px;
        border-left:3px solid {C['accent']}; padding-left:8px; }}

.chip {{ display:inline-block; border-radius:20px; padding:2px 12px;
         font-size:.75rem; font-weight:600; color:white; margin-bottom:6px; }}
.chip-s {{ background:{C['start']}; }}
.chip-w {{ background:{C['stop']}; }}
.chip-e {{ background:{C['end']}; }}

.metric-row {{ display:flex; gap:12px; margin:4px 0 20px; flex-wrap:wrap; }}
.metric-box {{
    flex:1; min-width:120px; background:{C['card']}; border:1.5px solid {C['border']};
    border-radius:12px; padding:14px 16px; text-align:center;
}}
.metric-box .val {{ font-size:1.7rem; font-weight:700; color:{C['primary']}; line-height:1.1; }}
.metric-box .lbl {{ font-size:.72rem; color:{C['muted']}; font-weight:500; margin-top:3px; }}

.sched-table {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
.sched-table th {{
    background:{C['bg']}; color:{C['text']}; font-weight:600;
    padding:9px 12px; text-align:left; border-bottom:2px solid {C['border']};
}}
.sched-table td {{ padding:9px 12px; border-bottom:1px solid {C['border']}; color:{C['text']}; }}
.sched-table tr:hover td {{ background:{C['bg']}; }}
.badge {{
    display:inline-block; border-radius:6px; padding:2px 8px;
    font-size:.72rem; font-weight:600; background:{C['primary']}22; color:{C['primary']};
}}

div.stButton > button {{
    background:{C['primary']} !important; color:white !important;
    border:none !important; border-radius:8px !important;
    font-weight:600 !important; transition:.2s !important;
}}
div.stButton > button:hover {{ background:{C['secondary']} !important; }}
.stTextInput > div > div > input {{
    border-radius:8px !important; border:1.5px solid {C['border']} !important;
    background:white !important; font-size:.9rem !important;
}}
.stTextInput > div > div > input:focus {{
    border-color:{C['primary']} !important;
    box-shadow:0 0 0 2px {C['primary']}22 !important;
}}
#MainMenu, footer {{ visibility:hidden; }}
</style>
""", unsafe_allow_html=True)

# ── Geocoding ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def geocode(address):
    try:
        loc = Nominatim(user_agent="ecoroute-optimizer").geocode(address, timeout=5)
        if loc: return (loc.latitude, loc.longitude)
    except (GeocoderTimedOut, GeocoderServiceError): pass
    return None

# ── Session state ────────────────────────────────────────────────────────────
def default_stop(address="", duration=30, note=""):
    return {"address": address, "duration": duration, "note": note}

if "start"     not in st.session_state:
    st.session_state.start = default_stop("Empire State Building, New York, NY", 0)
if "end"       not in st.session_state:
    st.session_state.end = default_stop("Brooklyn Bridge, New York, NY", 0)
if "waypoints" not in st.session_state:
    st.session_state.waypoints = [
        default_stop("Central Park, New York, NY", 60, "Picnic lunch"),
        default_stop("Times Square, New York, NY", 30, "Photos"),
    ]
if "trip_date"  not in st.session_state: st.session_state.trip_date  = datetime.today().date()
if "start_time" not in st.session_state: st.session_state.start_time = dtime(9, 0)
if "round_trip" not in st.session_state: st.session_state.round_trip = False

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  <h1>🌿 EcoRoute Optimizer</h1>
  <p>Plan smarter, greener journeys — schedule stops, estimate CO₂, and optimize your route.</p>
</div>
""", unsafe_allow_html=True)

# ── Layout ───────────────────────────────────────────────────────────────────
left, right = st.columns([1, 1.5], gap="large")

with left:
    # Trip settings
    st.markdown('<div class="sec">Trip Settings</div>', unsafe_allow_html=True)
    with st.container():
        ca, cb, cc = st.columns(3)
        mode       = ca.selectbox("Mode", ["car","bus","train","bike","walk"], label_visibility="collapsed")
        trip_date  = cb.date_input("Date", value=st.session_state.trip_date, label_visibility="collapsed")
        start_time = cc.time_input("Start time", value=st.session_state.start_time, label_visibility="collapsed", step=300)

    st.session_state.trip_date  = trip_date
    st.session_state.start_time = start_time
    round_trip = st.checkbox("🔄 Round trip (return to start)", value=st.session_state.round_trip)
    st.session_state.round_trip = round_trip

    # ── Start ────────────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Route</div>', unsafe_allow_html=True)
    st.markdown('<span class="chip chip-s">🟢 Start</span>', unsafe_allow_html=True)
    st.session_state.start["address"] = st.text_input(
        "start_addr", value=st.session_state.start["address"],
        label_visibility="collapsed", placeholder="Starting address…", key="si")

    # ── Waypoints ────────────────────────────────────────────────────────────
    st.markdown('<span class="chip chip-w">🔵 Stops</span>', unsafe_allow_html=True)
    updated_wps = []
    for i, wp in enumerate(st.session_state.waypoints):
        with st.expander(f"Stop {i+1}  —  {wp['address'][:40] or 'Empty'}", expanded=False):
            addr = st.text_input("Address", value=wp["address"], key=f"wa_{i}", placeholder="Address…")
            c1, c2 = st.columns([1,2])
            dur  = c1.number_input("Duration (min)", value=wp["duration"], min_value=0, max_value=480, step=15, key=f"wd_{i}")
            note = c2.text_input("Note", value=wp["note"], key=f"wn_{i}", placeholder="e.g. lunch, photos…")
            remove = st.button("Remove this stop", key=f"del_{i}")
        if not remove:
            updated_wps.append(default_stop(addr, dur, note))
    st.session_state.waypoints = updated_wps

    if st.button("＋ Add stop", use_container_width=True):
        st.session_state.waypoints.append(default_stop())
        st.rerun()

    # ── End ──────────────────────────────────────────────────────────────────
    st.markdown('<span class="chip chip-e">🔴 End</span>', unsafe_allow_html=True)
    st.session_state.end["address"] = st.text_input(
        "end_addr", value=st.session_state.end["address"],
        label_visibility="collapsed", placeholder="Destination address…", key="ei")

    st.markdown("")
    optimize = st.checkbox("Optimize stop order (nearest-neighbor)", value=True)
    run = st.button("🗺️ Calculate Route & Itinerary", type="primary", use_container_width=True)

# ── Right: preview map ───────────────────────────────────────────────────────
with right:
    st.markdown('<div class="sec">Map Preview</div>', unsafe_allow_html=True)

    all_addrs = (
        [st.session_state.start["address"]]
        + [w["address"] for w in st.session_state.waypoints]
        + [st.session_state.end["address"]]
    )
    preview = []
    for addr in all_addrs:
        if addr.strip():
            c = geocode(addr.strip())
            if c: preview.append((addr.strip(), c[0], c[1]))

    if preview:
        clat = sum(s[1] for s in preview) / len(preview)
        clon = sum(s[2] for s in preview) / len(preview)
        pm = folium.Map(location=[clat, clon], zoom_start=13, tiles="CartoDB positron")
        colors = ["green"] + ["blue"] * max(0, len(preview)-2) + ["red"]
        for i, (name, lat, lon) in enumerate(preview):
            folium.Marker([lat, lon], tooltip=f"{i+1}. {name}",
                icon=folium.Icon(color=colors[min(i, len(colors)-1)],
                                 icon="circle", prefix="fa")).add_to(pm)
        if len(preview) > 1:
            folium.PolyLine([[s[1], s[2]] for s in preview],
                color=C["primary"], weight=3, opacity=0.5, dash_array="8").add_to(pm)
        components.html(pm.get_root().render(), height=520)
    else:
        st.markdown(f"""
        <div style="height:520px;background:{C['card']};border:1.5px dashed {C['border']};
             border-radius:12px;display:flex;align-items:center;justify-content:center;
             flex-direction:column;color:{C['muted']};">
          <div style="font-size:3rem;">🗺️</div>
          <div style="margin-top:10px;font-size:.95rem;">Enter addresses to preview the map</div>
        </div>""", unsafe_allow_html=True)

# ── Results ──────────────────────────────────────────────────────────────────
if run:
    errors = []
    start_c = geocode(st.session_state.start["address"].strip()) if st.session_state.start["address"].strip() else None
    end_c   = geocode(st.session_state.end["address"].strip())   if st.session_state.end["address"].strip()   else None
    if not start_c: errors.append(st.session_state.start["address"] or "(empty start)")
    if not end_c:   errors.append(st.session_state.end["address"]   or "(empty end)")

    wps = []
    with st.spinner("Looking up addresses…"):
        for wp in st.session_state.waypoints:
            if not wp["address"].strip(): continue
            c = geocode(wp["address"].strip())
            if c: wps.append((wp["address"].strip(), c[0], c[1], wp["duration"], wp["note"]))
            else: errors.append(wp["address"])

    if errors:
        st.warning(f"Could not find: {', '.join(errors)}")
    if not start_c or not end_c:
        st.error("Start and End addresses are required.")
        st.stop()

    if optimize and len(wps) > 1:
        # Optimise only address/coords; carry duration & note along
        coords_only = [(w[0], w[1], w[2]) for w in wps]
        order = nearest_neighbor_route(coords_only)
        name_to_wp = {w[0]: w for w in wps}
        wps = [name_to_wp[o[0]] for o in order if o[0] in name_to_wp]

    # Build full route as (name, lat, lon)
    route = (
        [(st.session_state.start["address"].strip(), start_c[0], start_c[1])]
        + [(w[0], w[1], w[2]) for w in wps]
        + [(st.session_state.end["address"].strip(), end_c[0], end_c[1])]
    )
    if round_trip:
        route.append(route[0])

    durations = (
        [st.session_state.start["duration"]]
        + [w[3] for w in wps]
        + [st.session_state.end["duration"]]
        + ([0] if round_trip else [])
    )
    notes = (
        [st.session_state.start.get("note","")]
        + [w[4] for w in wps]
        + [st.session_state.end.get("note","")]
        + ([""] if round_trip else [])
    )

    dist  = route_total_distance(route)
    co2   = estimate_co2(dist, mode)
    score = eco_score(dist, mode)
    total_stop_time = sum(durations)
    start_min = st.session_state.start_time.hour * 60 + st.session_state.start_time.minute
    schedule  = build_schedule(route, mode, start_min, durations)
    total_travel_min = sum(s["travel_min"] for s in schedule)

    st.markdown("---")

    # ── Summary metrics ───────────────────────────────────────────────────
    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-box"><div class="val">{dist:.1f} km</div><div class="lbl">Total Distance</div></div>
      <div class="metric-box"><div class="val">{co2:.0f} g</div><div class="lbl">CO₂ Emissions</div></div>
      <div class="metric-box"><div class="val">{score}/100</div><div class="lbl">Eco Score</div></div>
      <div class="metric-box"><div class="val">{fmt_duration(total_travel_min)}</div><div class="lbl">Travel Time</div></div>
      <div class="metric-box"><div class="val">{fmt_duration(total_stop_time)}</div><div class="lbl">Time at Stops</div></div>
      <div class="metric-box"><div class="val">{fmt_time(schedule[-1]['depart_min'])}</div><div class="lbl">Est. Finish</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Itinerary schedule table ──────────────────────────────────────────
    st.markdown('<div class="sec">📋 Itinerary Schedule</div>', unsafe_allow_html=True)

    rows = ""
    for i, (s, note) in enumerate(zip(schedule, notes)):
        arrive_str  = fmt_time(s["arrive_min"])  if i > 0 else "—"
        depart_str  = fmt_time(s["depart_min"])  if s["dist_km"] > 0 or i < len(schedule)-1 else "—"
        travel_str  = fmt_duration(s["travel_min"]) if i > 0 else "—"
        dur_str     = fmt_duration(durations[i]) if durations[i] > 0 else "—"
        note_html   = f'<span style="color:{C["muted"]};font-size:.8rem;">📝 {note}</span>' if note else ""
        label       = "🟢" if i == 0 else ("🔴" if i == len(schedule)-1 and not round_trip else "🔵")
        rows += f"""<tr>
          <td><b>{i+1}</b></td>
          <td>{label} {s['name']}<br>{note_html}</td>
          <td>{arrive_str}</td>
          <td>{dur_str}</td>
          <td>{depart_str}</td>
          <td>{travel_str}</td>
          <td>{s['dist_km']:.2f} km</td>
        </tr>"""

    st.markdown(f"""
    <table class="sched-table">
      <thead><tr>
        <th>#</th><th>Location</th><th>Arrive</th><th>Duration</th>
        <th>Depart</th><th>Travel to next</th><th>Distance</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>""", unsafe_allow_html=True)

    # ── Export ────────────────────────────────────────────────────────────
    st.markdown('<div class="sec">📥 Export</div>', unsafe_allow_html=True)
    lines = [f"EcoRoute Itinerary — {trip_date.strftime('%B %d, %Y')}",
             f"Mode: {mode}  |  Distance: {dist:.1f} km  |  CO₂: {co2:.0f} g  |  Eco Score: {score}/100",
             f"Total travel time: {fmt_duration(total_travel_min)}  |  Estimated finish: {fmt_time(schedule[-1]['depart_min'])}",
             "", "SCHEDULE", "-"*60]
    for i, (s, note) in enumerate(zip(schedule, notes)):
        arrive = fmt_time(s["arrive_min"]) if i > 0 else "Start"
        depart = fmt_time(s["depart_min"])
        lines.append(f"{i+1}. {s['name']}")
        lines.append(f"   Arrive: {arrive}  |  Duration: {fmt_duration(durations[i])}  |  Depart: {depart}")
        if note: lines.append(f"   Note: {note}")
        if i < len(schedule)-1:
            lines.append(f"   ↓  {fmt_duration(schedule[i+1]['travel_min'])} travel  ({schedule[i+1]['dist_km']:.2f} km)")
        lines.append("")

    export_text = "\n".join(lines)
    st.download_button("⬇️ Download Itinerary (.txt)", data=export_text,
        file_name=f"ecoroute_{trip_date}.txt", mime="text/plain")

    # ── Optimised route map ───────────────────────────────────────────────
    st.markdown('<div class="sec">🗺️ Optimized Route Map</div>', unsafe_allow_html=True)
    clat = sum(s[1] for s in route) / len(route)
    clon = sum(s[2] for s in route) / len(route)
    m = folium.Map(location=[clat, clon], zoom_start=13, tiles="CartoDB positron")

    for i, (name, lat, lon) in enumerate(route):
        color = "green" if i == 0 else ("red" if i == len(route)-1 else "blue")
        folium.Marker([lat, lon], popup=name,
            tooltip=f"{i+1}. {name} | {fmt_time(schedule[i]['arrive_min'])}",
            icon=folium.Icon(color=color, icon="circle", prefix="fa")).add_to(m)

    folium.PolyLine([[s[1], s[2]] for s in route],
        color=C["primary"], weight=4, opacity=0.85).add_to(m)
    components.html(m.get_root().render(), height=460)

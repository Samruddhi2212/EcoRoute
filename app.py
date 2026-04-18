"""
app.py — EcoRoute Optimizer  |  Itinerary Planner
"""

import requests
import streamlit as st
import streamlit.components.v1 as components
import folium
from datetime import datetime, time as dtime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from utils import (
    haversine, estimate_co2_v2, nearest_neighbor_route,
    route_total_distance, eco_score,
    build_schedule, fmt_time, fmt_duration, travel_time_minutes,
    multi_mode_comparison, co2_equivalents, co2_savings,
    EMISSION_PROFILES, get_time_of_day_factor,
)

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="EcoRoute Optimizer", page_icon="🌿", layout="wide")

# ── Color palette ────────────────────────────────────────────────────────────
C = {
    "primary":   "#2d6a4f",
    "secondary": "#40916c",
    "accent":    "#f4a261",
    "accent2":   "#e76f51",
    "bg":        "#f8f9f4",
    "card":      "#ffffff",
    "border":    "#d8e8d8",
    "text":      "#1b2d24",
    "muted":     "#52796f",
    "start":     "#2d6a4f",
    "stop":      "#457b9d",
    "end":       "#e76f51",
    "green_bg":  "#f0f9f4",
    "warn_bg":   "#fff8e1",
    "warn_bdr":  "#ffcc80",
}

# ── CSS ──────────────────────────────────────────────────────────────────────
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

/* Mode comparison table */
.compare-table {{ width:100%; border-collapse:collapse; font-size:.84rem; }}
.compare-table th {{
    background:{C['bg']}; padding:8px 10px; font-weight:600;
    text-align:left; border-bottom:2px solid {C['border']};
}}
.compare-table td {{ padding:8px 10px; border-bottom:1px solid {C['border']}; }}
.compare-table .row-current td {{ background:#2d6a4f18; font-weight:600; }}
.compare-table .row-best td {{ }}

/* CO₂ impact panel */
.impact-panel {{
    background:{C['green_bg']}; border:1.5px solid {C['secondary']};
    border-radius:12px; padding:16px 20px; margin:12px 0;
}}
.impact-title {{ font-weight:700; color:{C['primary']}; font-size:1rem; margin-bottom:10px; }}
.impact-row {{ display:flex; gap:16px; flex-wrap:wrap; }}
.impact-item {{ flex:1; min-width:100px; text-align:center; }}
.impact-val {{ font-size:1.5rem; font-weight:700; color:{C['primary']}; }}
.impact-lbl {{ font-size:.7rem; color:{C['muted']}; margin-top:2px; }}

/* Inline badges */
.badge-green {{
    display:inline-block; background:{C['secondary']}; color:white;
    border-radius:8px; padding:3px 10px; font-size:.78rem; font-weight:600; margin:2px;
}}
.badge-warn {{
    display:inline-block; background:{C['warn_bg']}; color:#bf6000;
    border:1px solid {C['warn_bdr']}; border-radius:8px;
    padding:3px 10px; font-size:.78rem; font-weight:600; margin:2px;
}}
.badge-info {{
    display:inline-block; background:#e3f2fd; color:#1565c0;
    border:1px solid #90caf9; border-radius:8px;
    padding:3px 10px; font-size:.78rem; font-weight:600; margin:2px;
}}
.badge-eco {{
    display:inline-block; background:#e8f5e9; color:#2e7d32;
    border:1px solid #a5d6a7; border-radius:20px;
    padding:3px 12px; font-size:.8rem; font-weight:600;
}}

/* Recommendation box */
.rec-box {{
    background:#e8f5e9; border-left:4px solid {C['secondary']};
    border-radius:0 8px 8px 0; padding:10px 14px; margin:8px 0;
    font-size:.87rem; color:{C['text']};
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


# ── Geocoding ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def geocode(address):
    try:
        loc = Nominatim(user_agent="ecoroute-optimizer").geocode(address, timeout=5)
        if loc:
            return (loc.latitude, loc.longitude)
    except (GeocoderTimedOut, GeocoderServiceError):
        pass
    return None


# ── Weather (Open-Meteo — free, no API key) ───────────────────────────────────
@st.cache_data(show_spinner=False, ttl=1800)
def fetch_weather(lat, lon):
    """Fetch current conditions from Open-Meteo. Returns temp (°C), precipitation, icon."""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat:.4f}&longitude={lon:.4f}"
            f"&current=temperature_2m,precipitation,weathercode&timezone=auto"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            cur = resp.json().get("current", {})
            temp   = cur.get("temperature_2m", 20)
            precip = cur.get("precipitation", 0)
            wcode  = cur.get("weathercode", 0)
            return {
                "temp":       temp,
                "precip":     precip,
                "wcode":      wcode,
                "is_raining": precip > 0.1,
                "icon":       _weather_icon(wcode),
            }
    except Exception:
        pass
    return {"temp": 20, "precip": 0, "wcode": 0, "is_raining": False, "icon": "🌤️"}


def _weather_icon(wcode):
    if wcode == 0:        return "☀️"
    if wcode <= 3:        return "⛅"
    if wcode <= 48:       return "🌫️"
    if wcode <= 67:       return "🌧️"
    if wcode <= 77:       return "🌨️"
    if wcode <= 82:       return "🌦️"
    return "⛈️"


def _co2_color(co2_g):
    """Background colour for CO₂ cells in the comparison table."""
    if co2_g == 0:    return "#e8f5e9"
    if co2_g < 500:   return "#f1f8e9"
    if co2_g < 2000:  return "#fff9c4"
    if co2_g < 5000:  return "#ffe0b2"
    return "#ffcdd2"


# ── Session state ─────────────────────────────────────────────────────────────
def default_stop(address="", duration=30, note=""):
    return {"address": address, "duration": duration, "note": note}


if "start"      not in st.session_state:
    st.session_state.start = default_stop("Empire State Building, New York, NY", 0)
if "end"        not in st.session_state:
    st.session_state.end = default_stop("Brooklyn Bridge, New York, NY", 0)
if "waypoints"  not in st.session_state:
    st.session_state.waypoints = [
        default_stop("Central Park, New York, NY", 60, "Picnic lunch"),
        default_stop("Times Square, New York, NY", 30, "Photos"),
    ]
if "trip_date"  not in st.session_state: st.session_state.trip_date  = datetime.today().date()
if "start_time" not in st.session_state: st.session_state.start_time = dtime(9, 0)
if "round_trip" not in st.session_state: st.session_state.round_trip = False

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  <h1>🌿 EcoRoute Optimizer</h1>
  <p>Plan smarter, greener journeys — compare modes, quantify CO₂ impact, and schedule stops intelligently.</p>
</div>
""", unsafe_allow_html=True)

# ── Layout ────────────────────────────────────────────────────────────────────
left, right = st.columns([1, 1.5], gap="large")

with left:
    # ── Trip settings ────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Trip Settings</div>', unsafe_allow_html=True)

    # Vehicle type selector (grouped display via icons)
    vehicle_keys   = list(EMISSION_PROFILES.keys())
    vehicle_labels = {k: f"{EMISSION_PROFILES[k]['icon']} {EMISSION_PROFILES[k]['label']}" for k in vehicle_keys}

    ca, cb, cc = st.columns(3)
    vehicle_type = ca.selectbox(
        "Vehicle",
        options=vehicle_keys,
        format_func=lambda k: vehicle_labels[k],
        label_visibility="collapsed",
        key="vehicle_type_sel",
    )
    trip_date  = cb.date_input("Date", value=st.session_state.trip_date, label_visibility="collapsed")
    start_time = cc.time_input("Start time", value=st.session_state.start_time,
                               label_visibility="collapsed", step=300)

    st.session_state.trip_date  = trip_date
    st.session_state.start_time = start_time

    # Rush hour indicator
    start_min = start_time.hour * 60 + start_time.minute
    tod_factor = get_time_of_day_factor(start_min, vehicle_type)
    if tod_factor > 1.0:
        pct = round((tod_factor - 1) * 100)
        st.markdown(
            f'<span class="badge-warn">🚦 Rush hour — ~{pct}% longer journey & more emissions</span>',
            unsafe_allow_html=True,
        )
    elif tod_factor < 1.0:
        pct = round((1 - tod_factor) * 100)
        st.markdown(
            f'<span class="badge-eco">🌙 Off-peak — ~{pct}% faster & cleaner</span>',
            unsafe_allow_html=True,
        )

    round_trip = st.checkbox("🔄 Round trip (return to start)", value=st.session_state.round_trip)
    st.session_state.round_trip = round_trip

    # ── Route inputs ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Route</div>', unsafe_allow_html=True)
    st.markdown('<span class="chip chip-s">🟢 Start</span>', unsafe_allow_html=True)
    st.session_state.start["address"] = st.text_input(
        "start_addr", value=st.session_state.start["address"],
        label_visibility="collapsed", placeholder="Starting address…", key="si")

    st.markdown('<span class="chip chip-w">🔵 Stops</span>', unsafe_allow_html=True)
    updated_wps = []
    for i, wp in enumerate(st.session_state.waypoints):
        with st.expander(f"Stop {i+1}  —  {wp['address'][:40] or 'Empty'}", expanded=False):
            addr = st.text_input("Address", value=wp["address"], key=f"wa_{i}", placeholder="Address…")
            c1, c2 = st.columns([1, 2])
            dur  = c1.number_input("Duration (min)", value=wp["duration"], min_value=0,
                                   max_value=480, step=15, key=f"wd_{i}")
            note = c2.text_input("Note", value=wp["note"], key=f"wn_{i}", placeholder="e.g. lunch, photos…")
            remove = st.button("Remove this stop", key=f"del_{i}")
        if not remove:
            updated_wps.append(default_stop(addr, dur, note))
    st.session_state.waypoints = updated_wps

    if st.button("＋ Add stop", use_container_width=True):
        st.session_state.waypoints.append(default_stop())
        st.rerun()

    st.markdown('<span class="chip chip-e">🔴 End</span>', unsafe_allow_html=True)
    st.session_state.end["address"] = st.text_input(
        "end_addr", value=st.session_state.end["address"],
        label_visibility="collapsed", placeholder="Destination address…", key="ei")

    st.markdown("")
    optimize = st.checkbox("Optimize stop order (nearest-neighbor)", value=True)
    run = st.button("🗺️ Calculate Route & Itinerary", type="primary", use_container_width=True)


# ── Right: preview map ────────────────────────────────────────────────────────
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
            if c:
                preview.append((addr.strip(), c[0], c[1]))

    # Live weather badge for start location
    if preview:
        wx = fetch_weather(preview[0][1], preview[0][2])
        rain_txt = " · Raining" if wx["is_raining"] else ""
        st.markdown(
            f'<span class="badge-info">{wx["icon"]} {wx["temp"]:.0f}°C{rain_txt} at start location</span>',
            unsafe_allow_html=True,
        )

    if preview:
        clat = sum(s[1] for s in preview) / len(preview)
        clon = sum(s[2] for s in preview) / len(preview)
        pm = folium.Map(location=[clat, clon], zoom_start=13, tiles="CartoDB positron")
        colors = ["green"] + ["blue"] * max(0, len(preview) - 2) + ["red"]
        for i, (name, lat, lon) in enumerate(preview):
            folium.Marker(
                [lat, lon], tooltip=f"{i+1}. {name}",
                icon=folium.Icon(color=colors[min(i, len(colors) - 1)], icon="circle", prefix="fa"),
            ).add_to(pm)
        if len(preview) > 1:
            folium.PolyLine(
                [[s[1], s[2]] for s in preview],
                color=C["primary"], weight=3, opacity=0.5, dash_array="8",
            ).add_to(pm)
        components.html(pm.get_root().render(), height=500)
    else:
        st.markdown(f"""
        <div style="height:500px;background:{C['card']};border:1.5px dashed {C['border']};
             border-radius:12px;display:flex;align-items:center;justify-content:center;
             flex-direction:column;color:{C['muted']};">
          <div style="font-size:3rem;">🗺️</div>
          <div style="margin-top:10px;font-size:.95rem;">Enter addresses to preview the map</div>
        </div>""", unsafe_allow_html=True)


# ── Results ───────────────────────────────────────────────────────────────────
if run:
    errors = []
    start_c = geocode(st.session_state.start["address"].strip()) if st.session_state.start["address"].strip() else None
    end_c   = geocode(st.session_state.end["address"].strip())   if st.session_state.end["address"].strip()   else None
    if not start_c: errors.append(st.session_state.start["address"] or "(empty start)")
    if not end_c:   errors.append(st.session_state.end["address"]   or "(empty end)")

    wps = []
    with st.spinner("Looking up addresses…"):
        for wp in st.session_state.waypoints:
            if not wp["address"].strip():
                continue
            c = geocode(wp["address"].strip())
            if c:
                wps.append((wp["address"].strip(), c[0], c[1], wp["duration"], wp["note"]))
            else:
                errors.append(wp["address"])

    if errors:
        st.warning(f"Could not find: {', '.join(errors)}")
    if not start_c or not end_c:
        st.error("Start and End addresses are required.")
        st.stop()

    if optimize and len(wps) > 1:
        coords_only  = [(w[0], w[1], w[2]) for w in wps]
        order        = nearest_neighbor_route(coords_only)
        name_to_wp   = {w[0]: w for w in wps}
        wps          = [name_to_wp[o[0]] for o in order if o[0] in name_to_wp]

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
        [st.session_state.start.get("note", "")]
        + [w[4] for w in wps]
        + [st.session_state.end.get("note", "")]
        + ([""] if round_trip else [])
    )

    # Fetch weather at trip start
    wx = fetch_weather(start_c[0], start_c[1])

    dist     = route_total_distance(route)
    co2      = estimate_co2_v2(dist, vehicle_type, wx["temp"], wx["is_raining"], start_min)
    score    = eco_score(dist, vehicle_type, wx["temp"], wx["is_raining"], start_min)
    savings  = co2_savings(co2, dist, wx["temp"], wx["is_raining"], start_min)
    equivs   = co2_equivalents(co2)

    total_stop_time  = sum(durations)
    schedule         = build_schedule(route, vehicle_type, start_min, durations)
    total_travel_min = sum(s["travel_min"] for s in schedule)

    st.markdown("---")

    # ── Context badges ────────────────────────────────────────────────────────
    vp = EMISSION_PROFILES[vehicle_type]
    badges = [f'<span class="badge-info">{vp["icon"]} {vp["label"]}</span>']
    badges.append(f'<span class="badge-info">{wx["icon"]} {wx["temp"]:.0f}°C {"· Rain" if wx["is_raining"] else ""}</span>')
    if tod_factor > 1.0:
        badges.append(f'<span class="badge-warn">🚦 Rush hour (+{round((tod_factor-1)*100)}% time)</span>')
    elif tod_factor < 1.0:
        badges.append(f'<span class="badge-eco">🌙 Off-peak (−{round((1-tod_factor)*100)}%)</span>')
    st.markdown(" ".join(badges), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-box"><div class="val">{dist:.1f} km</div><div class="lbl">Total Distance</div></div>
      <div class="metric-box"><div class="val">{co2/1000:.2f} kg</div><div class="lbl">CO₂ Emitted</div></div>
      <div class="metric-box"><div class="val">{score}/100</div><div class="lbl">Eco Score</div></div>
      <div class="metric-box"><div class="val">{fmt_duration(total_travel_min)}</div><div class="lbl">Travel Time</div></div>
      <div class="metric-box"><div class="val">{fmt_duration(total_stop_time)}</div><div class="lbl">Time at Stops</div></div>
      <div class="metric-box"><div class="val">{fmt_time(schedule[-1]['depart_min'])}</div><div class="lbl">Est. Finish</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ── CO₂ Impact panel ──────────────────────────────────────────────────────
    st.markdown('<div class="sec">🌍 CO₂ Impact</div>', unsafe_allow_html=True)

    if savings["saved_g"] > 0:
        saved_kg   = savings["saved_g"] / 1000
        saved_pct  = savings["saved_pct"]
        header_txt = f"✅ You save <b>{saved_kg:.2f} kg CO₂</b> ({saved_pct:.0f}% less) vs driving a petrol car"
    else:
        header_txt = f"ℹ️ Emissions for this trip: <b>{co2/1000:.2f} kg CO₂</b>"

    # Suggest greener option
    comparison = multi_mode_comparison(dist, start_min, wx["temp"], wx["is_raining"])
    greenest   = comparison[0]   # lowest CO₂
    rec_html   = ""
    if greenest["type"] != vehicle_type and greenest["co2_g"] < co2 * 0.7:
        time_diff = greenest["time_min"] - total_travel_min
        time_txt  = f"+{fmt_duration(time_diff)} travel" if time_diff > 0 else f"−{fmt_duration(-time_diff)} travel"
        co2_save  = round((1 - greenest["co2_g"] / co2) * 100) if co2 > 0 else 0
        rec_html  = f"""
        <div class="rec-box">
          💡 <b>Switch to {greenest['icon']} {greenest['label']}</b> to cut emissions by
          <b>{co2_save}%</b> ({time_txt} time)
        </div>"""

    trees  = equivs["trees_days"]
    phones = int(equivs["phone_charges"])
    car_km = equivs["car_km"]

    st.markdown(f"""
    <div class="impact-panel">
      <div class="impact-title">{header_txt}</div>
      {rec_html}
      <div class="impact-row">
        <div class="impact-item">
          <div class="impact-val">🌳 {trees}</div>
          <div class="impact-lbl">tree-days to absorb<br>this CO₂</div>
        </div>
        <div class="impact-item">
          <div class="impact-val">📱 {phones}</div>
          <div class="impact-lbl">smartphone charges<br>equivalent energy</div>
        </div>
        <div class="impact-item">
          <div class="impact-val">🚗 {car_km} km</div>
          <div class="impact-lbl">equivalent petrol-car<br>distance</div>
        </div>
        <div class="impact-item">
          <div class="impact-val">{score}/100</div>
          <div class="impact-lbl">eco score<br>(higher = greener)</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Multi-mode comparison table ───────────────────────────────────────────
    st.markdown('<div class="sec">⚖️ Mode Comparison (same route)</div>', unsafe_allow_html=True)
    st.caption("All modes compared for the same straight-line distance. Road distances and availability will vary.")

    car_baseline = next((r["co2_g"] for r in comparison if r["type"] == "car_petrol"), co2)

    header = """
    <table class="compare-table">
      <thead><tr>
        <th>Mode</th>
        <th>Travel Time</th>
        <th>CO₂ Emitted</th>
        <th>g/km</th>
        <th>Eco Score</th>
        <th>vs Petrol Car</th>
      </tr></thead>
      <tbody>"""

    rows_html = ""
    for r in comparison:
        is_current = r["type"] == vehicle_type
        is_greenest = r["type"] == greenest["type"]
        row_class = "row-current" if is_current else ""

        if car_baseline > 0:
            diff_pct = round((r["co2_g"] - car_baseline) / car_baseline * 100)
            if diff_pct < 0:
                vs_txt = f'<span style="color:#2e7d32;font-weight:600;">−{abs(diff_pct)}%</span>'
            elif diff_pct == 0:
                vs_txt = '<span style="color:#666;">baseline</span>'
            else:
                vs_txt = f'<span style="color:#c62828;font-weight:600;">+{diff_pct}%</span>'
        else:
            vs_txt = "—"

        co2_disp = f"{r['co2_g']:.0f} g" if r["co2_g"] >= 1 else "0 g"
        co2_bg   = _co2_color(r["co2_g"])
        label    = r["icon"] + " " + r["label"]
        if is_current: label = f"<b>{label}</b> ✓"
        if is_greenest and not is_current: label += " 🌿"

        rows_html += f"""<tr class="{row_class}">
          <td>{label}</td>
          <td>{fmt_duration(r['time_min'])}</td>
          <td style="background:{co2_bg};">{co2_disp}</td>
          <td>{r['co2_per_km']:.1f}</td>
          <td>{r['eco_score']}</td>
          <td>{vs_txt}</td>
        </tr>"""

    st.markdown(header + rows_html + "</tbody></table>", unsafe_allow_html=True)

    # ── Itinerary schedule ────────────────────────────────────────────────────
    st.markdown('<div class="sec">📋 Itinerary Schedule</div>', unsafe_allow_html=True)

    rows = ""
    for i, (s, note) in enumerate(zip(schedule, notes)):
        arrive_str = fmt_time(s["arrive_min"]) if i > 0 else "—"
        depart_str = fmt_time(s["depart_min"]) if s["dist_km"] > 0 or i < len(schedule) - 1 else "—"
        travel_str = fmt_duration(s["travel_min"]) if i > 0 else "—"
        dur_str    = fmt_duration(durations[i]) if durations[i] > 0 else "—"
        note_html  = f'<span style="color:{C["muted"]};font-size:.8rem;">📝 {note}</span>' if note else ""
        label      = "🟢" if i == 0 else ("🔴" if i == len(schedule) - 1 and not round_trip else "🔵")
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

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown('<div class="sec">📥 Export</div>', unsafe_allow_html=True)
    lines = [
        f"EcoRoute Itinerary — {trip_date.strftime('%B %d, %Y')}",
        f"Vehicle: {vp['label']}  |  Distance: {dist:.1f} km  |  CO₂: {co2/1000:.2f} kg  |  Eco Score: {score}/100",
        f"Weather: {wx['icon']} {wx['temp']:.0f}°C{'  Rain' if wx['is_raining'] else ''}",
        f"Total travel time: {fmt_duration(total_travel_min)}  |  Estimated finish: {fmt_time(schedule[-1]['depart_min'])}",
        f"CO₂ saved vs petrol car: {savings['saved_g']/1000:.2f} kg ({savings['saved_pct']:.0f}%)",
        "", "SCHEDULE", "-" * 60,
    ]
    for i, (s, note) in enumerate(zip(schedule, notes)):
        arrive = fmt_time(s["arrive_min"]) if i > 0 else "Start"
        depart = fmt_time(s["depart_min"])
        lines.append(f"{i+1}. {s['name']}")
        lines.append(f"   Arrive: {arrive}  |  Duration: {fmt_duration(durations[i])}  |  Depart: {depart}")
        if note:
            lines.append(f"   Note: {note}")
        if i < len(schedule) - 1:
            lines.append(f"   ↓  {fmt_duration(schedule[i+1]['travel_min'])} travel  ({schedule[i+1]['dist_km']:.2f} km)")
        lines.append("")

    export_text = "\n".join(lines)
    st.download_button(
        "⬇️ Download Itinerary (.txt)", data=export_text,
        file_name=f"ecoroute_{trip_date}.txt", mime="text/plain",
    )

    # ── Optimised route map ───────────────────────────────────────────────────
    st.markdown('<div class="sec">🗺️ Optimized Route Map</div>', unsafe_allow_html=True)
    clat = sum(s[1] for s in route) / len(route)
    clon = sum(s[2] for s in route) / len(route)
    m    = folium.Map(location=[clat, clon], zoom_start=13, tiles="CartoDB positron")

    for i, (name, lat, lon) in enumerate(route):
        color = "green" if i == 0 else ("red" if i == len(route) - 1 else "blue")
        leg_co2 = estimate_co2_v2(schedule[i]["dist_km"], vehicle_type, wx["temp"], wx["is_raining"], start_min)
        popup_txt = (
            f"<b>{name}</b><br>"
            f"Arrive: {fmt_time(schedule[i]['arrive_min'])}<br>"
            f"Leg CO₂: {leg_co2:.0f} g"
        )
        folium.Marker(
            [lat, lon],
            popup=folium.Popup(popup_txt, max_width=220),
            tooltip=f"{i+1}. {name} | {fmt_time(schedule[i]['arrive_min'])}",
            icon=folium.Icon(color=color, icon="circle", prefix="fa"),
        ).add_to(m)

    folium.PolyLine(
        [[s[1], s[2]] for s in route],
        color=C["primary"], weight=4, opacity=0.85,
    ).add_to(m)
    components.html(m.get_root().render(), height=460)

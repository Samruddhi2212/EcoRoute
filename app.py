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
    eco_score,
    build_schedule, fmt_time, fmt_duration,
    multi_mode_comparison, co2_equivalents, co2_savings,
    EMISSION_PROFILES, get_time_of_day_factor,
    get_osrm_route, pareto_frontier, weighted_pareto_score,
    departure_time_sweep, ROUTE_FACTOR,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="EcoRoute Optimizer", page_icon="🌿", layout="wide")

C = {
    "primary":  "#2d6a4f", "secondary": "#40916c", "accent": "#f4a261",
    "accent2":  "#e76f51", "bg": "#f8f9f4", "card": "#ffffff",
    "border":   "#d8e8d8", "text": "#1b2d24", "muted": "#52796f",
    "start":    "#2d6a4f", "stop": "#457b9d", "end": "#e76f51",
    "green_bg": "#f0f9f4", "warn_bg": "#fff8e1", "warn_bdr": "#ffcc80",
}

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
.card {{ background:{C['card']}; border:1.5px solid {C['border']}; border-radius:12px; padding:16px 18px; margin-bottom:12px; }}
.sec {{ font-size:.8rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em;
        color:{C['muted']}; margin:16px 0 8px; border-left:3px solid {C['accent']}; padding-left:8px; }}
.chip {{ display:inline-block; border-radius:20px; padding:2px 12px; font-size:.75rem; font-weight:600; color:white; margin-bottom:6px; }}
.chip-s {{ background:{C['start']}; }} .chip-w {{ background:{C['stop']}; }} .chip-e {{ background:{C['end']}; }}
.metric-row {{ display:flex; gap:12px; margin:4px 0 20px; flex-wrap:wrap; }}
.metric-box {{
    flex:1; min-width:120px; background:{C['card']}; border:1.5px solid {C['border']};
    border-radius:12px; padding:14px 16px; text-align:center;
}}
.metric-box .val {{ font-size:1.7rem; font-weight:700; color:{C['primary']}; line-height:1.1; }}
.metric-box .lbl {{ font-size:.72rem; color:{C['muted']}; font-weight:500; margin-top:3px; }}
.sched-table {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
.sched-table th {{ background:{C['bg']}; color:{C['text']}; font-weight:600; padding:9px 12px; text-align:left; border-bottom:2px solid {C['border']}; }}
.sched-table td {{ padding:9px 12px; border-bottom:1px solid {C['border']}; color:{C['text']}; }}
.sched-table tr:hover td {{ background:{C['bg']}; }}
.compare-table {{ width:100%; border-collapse:collapse; font-size:.84rem; }}
.compare-table th {{ background:{C['bg']}; padding:8px 10px; font-weight:600; text-align:left; border-bottom:2px solid {C['border']}; }}
.compare-table td {{ padding:8px 10px; border-bottom:1px solid {C['border']}; }}
.compare-table .row-current td {{ background:#2d6a4f18; font-weight:600; }}
.impact-panel {{ background:{C['green_bg']}; border:1.5px solid {C['secondary']}; border-radius:12px; padding:16px 20px; margin:12px 0; }}
.impact-title {{ font-weight:700; color:{C['primary']}; font-size:1rem; margin-bottom:10px; }}
.impact-row {{ display:flex; gap:16px; flex-wrap:wrap; }}
.impact-item {{ flex:1; min-width:100px; text-align:center; }}
.impact-val {{ font-size:1.5rem; font-weight:700; color:{C['primary']}; }}
.impact-lbl {{ font-size:.7rem; color:{C['muted']}; margin-top:2px; }}
.badge-green {{ display:inline-block; background:{C['secondary']}; color:white; border-radius:8px; padding:3px 10px; font-size:.78rem; font-weight:600; margin:2px; }}
.badge-warn  {{ display:inline-block; background:{C['warn_bg']}; color:#bf6000; border:1px solid {C['warn_bdr']}; border-radius:8px; padding:3px 10px; font-size:.78rem; font-weight:600; margin:2px; }}
.badge-info  {{ display:inline-block; background:#e3f2fd; color:#1565c0; border:1px solid #90caf9; border-radius:8px; padding:3px 10px; font-size:.78rem; font-weight:600; margin:2px; }}
.badge-eco   {{ display:inline-block; background:#e8f5e9; color:#2e7d32; border:1px solid #a5d6a7; border-radius:20px; padding:3px 12px; font-size:.8rem; font-weight:600; }}
.badge-road  {{ display:inline-block; background:#f3e5f5; color:#6a1b9a; border:1px solid #ce93d8; border-radius:8px; padding:3px 10px; font-size:.78rem; font-weight:600; margin:2px; }}
.rec-box {{ background:#e8f5e9; border-left:4px solid {C['secondary']}; border-radius:0 8px 8px 0; padding:10px 14px; margin:8px 0; font-size:.87rem; color:{C['text']}; }}
.pareto-winner {{ background:{C['green_bg']}; border:1.5px solid {C['secondary']}; border-radius:10px; padding:12px 16px; margin:10px 0; font-size:.9rem; color:{C['text']}; }}
div.stButton > button {{ background:{C['primary']} !important; color:white !important; border:none !important; border-radius:8px !important; font-weight:600 !important; transition:.2s !important; }}
div.stButton > button:hover {{ background:{C['secondary']} !important; }}
.stTextInput > div > div > input {{ border-radius:8px !important; border:1.5px solid {C['border']} !important; background:white !important; font-size:.9rem !important; }}
.stTextInput > div > div > input:focus {{ border-color:{C['primary']} !important; box-shadow:0 0 0 2px {C['primary']}22 !important; }}
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


# ── Weather (Open-Meteo — free, no key) ───────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=1800)
def fetch_weather(lat, lon):
    try:
        url = (f"https://api.open-meteo.com/v1/forecast"
               f"?latitude={lat:.4f}&longitude={lon:.4f}"
               f"&current=temperature_2m,precipitation,weathercode&timezone=auto")
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            cur = resp.json().get("current", {})
            temp, precip, wcode = cur.get("temperature_2m", 20), cur.get("precipitation", 0), cur.get("weathercode", 0)
            return {"temp": temp, "precip": precip, "wcode": wcode,
                    "is_raining": precip > 0.1, "icon": _weather_icon(wcode)}
    except Exception:
        pass
    return {"temp": 20, "precip": 0, "wcode": 0, "is_raining": False, "icon": "🌤️"}


def _weather_icon(wcode):
    if wcode == 0: return "☀️"
    if wcode <= 3: return "⛅"
    if wcode <= 48: return "🌫️"
    if wcode <= 67: return "🌧️"
    if wcode <= 77: return "🌨️"
    if wcode <= 82: return "🌦️"
    return "⛈️"


# ── OSRM real road routing (cached) ──────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_osrm_route(coords_tuple, vehicle_type):
    """Thin cached wrapper around get_osrm_route. coords_tuple: ((lat,lon), ...)."""
    return get_osrm_route(list(coords_tuple), vehicle_type)


# ── SVG: Pareto scatter ───────────────────────────────────────────────────────
def _render_pareto_svg(comparison, current_type, frontier, best_type):
    W, H   = 560, 290
    PL, PR, PT, PB = 62, 20, 30, 48
    pw, ph = W - PL - PR, H - PT - PB

    times = [r["time_min"] for r in comparison]
    co2s  = [r["co2_g"]    for r in comparison]
    max_t = max(times) * 1.12 if times else 10
    max_c = max(co2s)  * 1.12 if max(co2s) > 0 else 100

    def px(t): return PL + (t / max_t) * pw
    def py(c): return H - PB - (c / max_c) * ph

    front_sorted = sorted([r for r in comparison if r["type"] in frontier],
                          key=lambda x: x["time_min"])

    L = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'style="font-family:Inter,sans-serif;background:#fafff8;border-radius:10px;">']

    # Grid
    for gi in range(5):
        yg = PT + gi * ph / 4
        cv = int(max_c * (4 - gi) / 4 / 100 + 0.5) * 100
        L.append(f'<line x1="{PL}" y1="{yg:.1f}" x2="{W-PR}" y2="{yg:.1f}" stroke="#e4ede4" stroke-width="1"/>')
        L.append(f'<text x="{PL-5}" y="{yg+4:.1f}" text-anchor="end" font-size="9" fill="#aaa">{cv}</text>')
    for gi in range(6):
        xg = PL + gi * pw / 5
        tv = int(max_t * gi / 5)
        L.append(f'<line x1="{xg:.1f}" y1="{PT}" x2="{xg:.1f}" y2="{H-PB}" stroke="#e4ede4" stroke-width="1"/>')
        L.append(f'<text x="{xg:.1f}" y="{H-PB+13}" text-anchor="middle" font-size="9" fill="#aaa">{tv}m</text>')

    # Axes + labels
    L.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{H-PB}" stroke="#ccc" stroke-width="1.5"/>')
    L.append(f'<line x1="{PL}" y1="{H-PB}" x2="{W-PR}" y2="{H-PB}" stroke="#ccc" stroke-width="1.5"/>')
    L.append(f'<text x="{W//2}" y="{H-3}" text-anchor="middle" font-size="11" fill="#666">← faster      Travel Time      slower →</text>')
    L.append(f'<text x="11" y="{H//2}" text-anchor="middle" font-size="11" fill="#666" transform="rotate(-90,11,{H//2})">CO₂ (g)</text>')

    # Frontier dashed line
    if len(front_sorted) > 1:
        pts = " ".join(f"{px(r['time_min']):.1f},{py(r['co2_g']):.1f}" for r in front_sorted)
        L.append(f'<polyline points="{pts}" fill="none" stroke="#40916c" stroke-width="2" stroke-dasharray="6,3" opacity="0.55"/>')

    # Dots
    for r in comparison:
        x, y        = px(r["time_min"]), py(r["co2_g"])
        on_front    = r["type"] in frontier
        is_curr     = r["type"] == current_type
        is_best     = r["type"] == best_type
        color  = "#2d6a4f" if on_front else "#c8c8c8"
        radius = 8 if on_front else 5

        # Halo for current selection
        if is_curr:
            L.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius+5}" fill="none" stroke="#f4a261" stroke-width="2.5"/>')
        # Star for Pareto-optimal best at current slider
        if is_best and not is_curr:
            L.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius+4}" fill="#ffd54f" opacity="0.7"/>')

        L.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" opacity="0.92"/>')

        if on_front or is_curr:
            icon = r["icon"]
            dy   = -13 if y > PT + 18 else 18
            L.append(f'<text x="{x:.1f}" y="{y+dy:.1f}" text-anchor="middle" font-size="13">{icon}</text>')
            short = r["label"].replace("Car ", "").replace("(", "").replace(")", "")
            L.append(f'<text x="{x:.1f}" y="{y+dy+12:.1f}" text-anchor="middle" font-size="8" fill="#555">{short}</text>')

    # Legend
    L.append(f'<circle cx="70" cy="{H-8}" r="5" fill="#2d6a4f"/>')
    L.append(f'<text x="78" y="{H-4}" font-size="9" fill="#555">Pareto frontier</text>')
    L.append(f'<circle cx="175" cy="{H-8}" r="5" fill="none" stroke="#f4a261" stroke-width="2"/>')
    L.append(f'<text x="183" y="{H-4}" font-size="9" fill="#555">Your selection</text>')
    L.append(f'<circle cx="280" cy="{H-8}" r="5" fill="#ffd54f" opacity="0.8"/>')
    L.append(f'<text x="288" y="{H-4}" font-size="9" fill="#555">Optimal at slider</text>')

    L.append('</svg>')
    return "\n".join(L)


# ── SVG: Departure time bar chart ─────────────────────────────────────────────
def _render_departure_svg(sweep, current_minute, vp):
    W, H   = 560, 185
    n      = len(sweep)
    bar_w  = (W - 60) / n if n > 0 else 10
    max_co2 = max((r["co2_g"] for r in sweep), default=1) or 1
    max_bar = H - 58
    opt_min = min(sweep, key=lambda r: r["co2_g"])["minute"] if sweep else 0

    L = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'style="font-family:Inter,sans-serif;background:#fafff8;border-radius:10px;">']
    L.append(f'<text x="{W//2}" y="17" text-anchor="middle" font-size="11" font-weight="600" fill="#2d6a4f">'
             f'CO₂ by Departure Time — {vp["icon"]} {vp["label"]}</text>')

    for i, slot in enumerate(sweep):
        bh = (slot["co2_g"] / max_co2) * max_bar if max_co2 > 0 else 0
        bx = 55 + i * bar_w
        by = H - 38 - bh
        is_curr = abs(slot["minute"] - current_minute) < (60 * 0.6)
        if is_curr:
            fill = "#f4a261"
        elif slot["minute"] == opt_min:
            fill = "#2d6a4f"
        elif slot["tod_factor"] > 1.0:
            fill = "#ffcc80"
        elif slot["tod_factor"] < 1.0:
            fill = "#a5d6a7"
        else:
            fill = "#c8e6c9"

        bw = max(bar_w - 1.5, 1)
        L.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{fill}" rx="2">'
                 f'<title>{slot["label"]} — {slot["co2_g"]:.0f} g CO₂, {slot["time_min"]:.0f} min</title></rect>')

        if i % 4 == 0:
            L.append(f'<text x="{bx + bar_w/2:.1f}" y="{H-6}" text-anchor="middle" font-size="8" fill="#999">{slot["label"]}</text>')

    # Y axis
    L.append(f'<line x1="55" y1="24" x2="55" y2="{H-38}" stroke="#ccc" stroke-width="1"/>')
    L.append(f'<line x1="55" y1="{H-38}" x2="{W-5}" y2="{H-38}" stroke="#ccc" stroke-width="1"/>')

    # Legend row
    legend = [("#f4a261", "Your time"), ("#2d6a4f", "Optimal"), ("#ffcc80", "Rush hour"), ("#a5d6a7", "Off-peak")]
    for li, (col, txt) in enumerate(legend):
        lx = 58 + li * 122
        L.append(f'<rect x="{lx}" y="{H-28}" width="9" height="9" fill="{col}" rx="2"/>')
        L.append(f'<text x="{lx+12}" y="{H-21}" font-size="9" fill="#666">{txt}</text>')

    L.append('</svg>')
    return "\n".join(L)


def _co2_color(co2_g):
    if co2_g == 0:   return "#e8f5e9"
    if co2_g < 500:  return "#f1f8e9"
    if co2_g < 2000: return "#fff9c4"
    if co2_g < 5000: return "#ffe0b2"
    return "#ffcdd2"


# ── Session state ─────────────────────────────────────────────────────────────
def default_stop(address="", duration=30, note=""):
    return {"address": address, "duration": duration, "note": note}


if "start"      not in st.session_state: st.session_state.start     = default_stop("Empire State Building, New York, NY", 0)
if "end"        not in st.session_state: st.session_state.end       = default_stop("Brooklyn Bridge, New York, NY", 0)
if "waypoints"  not in st.session_state: st.session_state.waypoints = [
    default_stop("Central Park, New York, NY", 60, "Picnic lunch"),
    default_stop("Times Square, New York, NY", 30, "Photos"),
]
if "trip_date"  not in st.session_state: st.session_state.trip_date  = datetime.today().date()
if "start_time" not in st.session_state: st.session_state.start_time = dtime(9, 0)
if "round_trip" not in st.session_state: st.session_state.round_trip = False

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🌿 EcoRoute Optimizer</h1>
  <p>Real road routing · Multi-objective Pareto optimization · Live weather · Departure intelligence</p>
</div>
""", unsafe_allow_html=True)

left, right = st.columns([1, 1.5], gap="large")

with left:
    st.markdown('<div class="sec">Trip Settings</div>', unsafe_allow_html=True)
    vehicle_keys   = list(EMISSION_PROFILES.keys())
    vehicle_labels = {k: f"{EMISSION_PROFILES[k]['icon']} {EMISSION_PROFILES[k]['label']}" for k in vehicle_keys}
    ca, cb, cc = st.columns(3)
    vehicle_type = ca.selectbox("Vehicle", options=vehicle_keys,
                                format_func=lambda k: vehicle_labels[k],
                                label_visibility="collapsed", key="vehicle_type_sel")
    trip_date  = cb.date_input("Date", value=st.session_state.trip_date, label_visibility="collapsed")
    start_time = cc.time_input("Start time", value=st.session_state.start_time,
                               label_visibility="collapsed", step=300)
    st.session_state.trip_date  = trip_date
    st.session_state.start_time = start_time

    start_min  = start_time.hour * 60 + start_time.minute
    tod_factor = get_time_of_day_factor(start_min, vehicle_type)
    if tod_factor > 1.0:
        st.markdown(f'<span class="badge-warn">🚦 Rush hour — ~{round((tod_factor-1)*100)}% longer & more emissions</span>', unsafe_allow_html=True)
    elif tod_factor < 1.0:
        st.markdown(f'<span class="badge-eco">🌙 Off-peak — ~{round((1-tod_factor)*100)}% faster & cleaner</span>', unsafe_allow_html=True)

    round_trip = st.checkbox("🔄 Round trip (return to start)", value=st.session_state.round_trip)
    st.session_state.round_trip = round_trip

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
            dur  = c1.number_input("Duration (min)", value=wp["duration"], min_value=0, max_value=480, step=15, key=f"wd_{i}")
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

with right:
    st.markdown('<div class="sec">Map Preview</div>', unsafe_allow_html=True)
    all_addrs = ([st.session_state.start["address"]]
                 + [w["address"] for w in st.session_state.waypoints]
                 + [st.session_state.end["address"]])
    preview = []
    for addr in all_addrs:
        if addr.strip():
            c = geocode(addr.strip())
            if c:
                preview.append((addr.strip(), c[0], c[1]))

    if preview:
        wx_prev = fetch_weather(preview[0][1], preview[0][2])
        rain_txt = " · Rain" if wx_prev["is_raining"] else ""
        st.markdown(f'<span class="badge-info">{wx_prev["icon"]} {wx_prev["temp"]:.0f}°C{rain_txt} at start</span>',
                    unsafe_allow_html=True)

    if preview:
        clat = sum(s[1] for s in preview) / len(preview)
        clon = sum(s[2] for s in preview) / len(preview)
        pm   = folium.Map(location=[clat, clon], zoom_start=13, tiles="CartoDB positron")
        colors = ["green"] + ["blue"] * max(0, len(preview) - 2) + ["red"]
        for i, (name, lat, lon) in enumerate(preview):
            folium.Marker([lat, lon], tooltip=f"{i+1}. {name}",
                          icon=folium.Icon(color=colors[min(i, len(colors)-1)], icon="circle", prefix="fa")).add_to(pm)
        if len(preview) > 1:
            folium.PolyLine([[s[1], s[2]] for s in preview],
                            color=C["primary"], weight=3, opacity=0.5, dash_array="8").add_to(pm)
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
    errors  = []
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

    if errors:        st.warning(f"Could not find: {', '.join(errors)}")
    if not start_c or not end_c:
        st.error("Start and End addresses are required.")
        st.stop()

    if optimize and len(wps) > 1:
        coords_only = [(w[0], w[1], w[2]) for w in wps]
        order       = nearest_neighbor_route(coords_only)
        name_to_wp  = {w[0]: w for w in wps}
        wps         = [name_to_wp[o[0]] for o in order if o[0] in name_to_wp]

    route = ([(st.session_state.start["address"].strip(), start_c[0], start_c[1])]
             + [(w[0], w[1], w[2]) for w in wps]
             + [(st.session_state.end["address"].strip(), end_c[0], end_c[1])])
    if round_trip:
        route.append(route[0])

    durations = ([st.session_state.start["duration"]]
                 + [w[3] for w in wps]
                 + [st.session_state.end["duration"]]
                 + ([0] if round_trip else []))
    notes = ([st.session_state.start.get("note", "")]
             + [w[4] for w in wps]
             + [st.session_state.end.get("note", "")]
             + ([""] if round_trip else []))

    # ── Real road routing via OSRM ────────────────────────────────────────────
    with st.spinner("Fetching real road route…"):
        route_coords = tuple((r[1], r[2]) for r in route)
        osrm = fetch_osrm_route(route_coords, vehicle_type)

    if osrm:
        leg_distances_km = [d / 1000 for d in osrm["leg_distances_m"]]
        dist             = sum(leg_distances_km)
        routing_src      = "road"
    else:
        # Fallback: haversine × correction factor for trains, plain haversine for others
        factor = ROUTE_FACTOR.get(vehicle_type, 1.0)
        leg_distances_km = [
            haversine(route[i][1], route[i][2], route[i+1][1], route[i+1][2]) * factor
            for i in range(len(route) - 1)
        ]
        dist        = sum(leg_distances_km)
        routing_src = "estimated"

    # Weather at start
    wx = fetch_weather(start_c[0], start_c[1])

    co2     = estimate_co2_v2(dist, vehicle_type, wx["temp"], wx["is_raining"], start_min)
    score   = eco_score(dist, vehicle_type, wx["temp"], wx["is_raining"], start_min)
    savings = co2_savings(co2, dist, wx["temp"], wx["is_raining"], start_min)
    equivs  = co2_equivalents(co2)

    total_stop_time  = sum(durations)
    schedule         = build_schedule(route, vehicle_type, start_min, durations, leg_distances_km)
    total_travel_min = sum(s["travel_min"] for s in schedule)

    st.markdown("---")

    # ── Context badges ────────────────────────────────────────────────────────
    vp = EMISSION_PROFILES[vehicle_type]
    road_badge = ('<span class="badge-road">🛣️ Real road distances</span>'
                  if routing_src == "road"
                  else '<span class="badge-warn">📐 Estimated distances (haversine)</span>')
    badges = [f'<span class="badge-info">{vp["icon"]} {vp["label"]}</span>',
              f'<span class="badge-info">{wx["icon"]} {wx["temp"]:.0f}°C{"  · Rain" if wx["is_raining"] else ""}</span>',
              road_badge]
    if tod_factor > 1.0:
        badges.append(f'<span class="badge-warn">🚦 Rush hour (+{round((tod_factor-1)*100)}%)</span>')
    elif tod_factor < 1.0:
        badges.append(f'<span class="badge-eco">🌙 Off-peak (−{round((1-tod_factor)*100)}%)</span>')
    st.markdown(" ".join(badges) + "<br><br>", unsafe_allow_html=True)

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-box"><div class="val">{dist:.1f} km</div><div class="lbl">Road Distance</div></div>
      <div class="metric-box"><div class="val">{co2/1000:.2f} kg</div><div class="lbl">CO₂ Emitted</div></div>
      <div class="metric-box"><div class="val">{score}/100</div><div class="lbl">Eco Score</div></div>
      <div class="metric-box"><div class="val">{fmt_duration(total_travel_min)}</div><div class="lbl">Travel Time</div></div>
      <div class="metric-box"><div class="val">{fmt_duration(total_stop_time)}</div><div class="lbl">Time at Stops</div></div>
      <div class="metric-box"><div class="val">{fmt_time(schedule[-1]['depart_min'])}</div><div class="lbl">Est. Finish</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ── CO₂ Impact panel ──────────────────────────────────────────────────────
    st.markdown('<div class="sec">🌍 CO₂ Impact</div>', unsafe_allow_html=True)
    comparison  = multi_mode_comparison(dist, start_min, wx["temp"], wx["is_raining"])
    greenest    = comparison[0]
    car_base_co2 = next((r["co2_g"] for r in comparison if r["type"] == "car_petrol"), co2)

    if savings["saved_g"] > 0:
        header_txt = (f'✅ You save <b>{savings["saved_g"]/1000:.2f} kg CO₂</b> '
                      f'({savings["saved_pct"]:.0f}% less) vs driving a petrol car')
    else:
        header_txt = f'ℹ️ Emissions for this trip: <b>{co2/1000:.2f} kg CO₂</b>'

    rec_html = ""
    if greenest["type"] != vehicle_type and greenest["co2_g"] < co2 * 0.7:
        time_diff = greenest["time_min"] - total_travel_min
        time_txt  = f"+{fmt_duration(time_diff)}" if time_diff > 0 else f"−{fmt_duration(-time_diff)}"
        co2_save  = round((1 - greenest["co2_g"] / co2) * 100) if co2 > 0 else 0
        rec_html  = (f'<div class="rec-box">💡 <b>Switch to {greenest["icon"]} {greenest["label"]}</b> '
                     f'to cut emissions by <b>{co2_save}%</b> ({time_txt} travel time)</div>')

    trees, phones, car_km = equivs["trees_days"], int(equivs["phone_charges"]), equivs["car_km"]
    st.markdown(f"""
    <div class="impact-panel">
      <div class="impact-title">{header_txt}</div>
      {rec_html}
      <div class="impact-row">
        <div class="impact-item"><div class="impact-val">🌳 {trees}</div><div class="impact-lbl">tree-days to<br>absorb this CO₂</div></div>
        <div class="impact-item"><div class="impact-val">📱 {phones}</div><div class="impact-lbl">smartphone charges<br>equivalent</div></div>
        <div class="impact-item"><div class="impact-val">🚗 {car_km} km</div><div class="impact-lbl">equivalent petrol-car<br>distance</div></div>
        <div class="impact-item"><div class="impact-val">{score}/100</div><div class="impact-lbl">eco score</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Multi-objective Pareto optimizer ─────────────────────────────────────
    st.markdown('<div class="sec">⚖️ Multi-Objective Pareto Optimizer</div>', unsafe_allow_html=True)
    st.caption("Drag the slider to shift weight between minimizing travel time and minimizing CO₂.")

    alpha = st.slider("⚡ Fastest  ←  →  🌿 Greenest", 0, 100, 40, key="pareto_slider") / 100

    max_time_all = max(r["time_min"] for r in comparison)
    max_co2_all  = max(r["co2_g"]   for r in comparison) or 1

    scored = sorted(comparison,
                    key=lambda r: weighted_pareto_score(r["time_min"], r["co2_g"],
                                                        alpha, max_time_all, max_co2_all))
    best = scored[0]
    frontier = pareto_frontier(comparison)

    # Winner box
    is_already_best = best["type"] == vehicle_type
    if is_already_best:
        winner_txt = f'✅ Your current choice <b>{best["icon"]} {best["label"]}</b> is already optimal for this balance.'
    else:
        b_time_diff = best["time_min"] - total_travel_min
        b_co2_diff  = best["co2_g"] - co2
        b_time_txt  = (f'+{fmt_duration(b_time_diff)}' if b_time_diff > 0 else f'−{fmt_duration(-b_time_diff)}')
        b_co2_txt   = (f'+{abs(b_co2_diff):.0f} g more CO₂' if b_co2_diff > 0 else f'−{abs(b_co2_diff):.0f} g less CO₂')
        winner_txt  = (f'🏆 Optimal for this balance: <b>{best["icon"]} {best["label"]}</b> '
                       f'— {b_time_txt} travel, {b_co2_txt}')
    st.markdown(f'<div class="pareto-winner">{winner_txt}</div>', unsafe_allow_html=True)

    # Top-3 weighted table
    top3_rows = ""
    for rank, r in enumerate(scored[:5]):
        ws    = weighted_pareto_score(r["time_min"], r["co2_g"], alpha, max_time_all, max_co2_all)
        medal = ["🥇", "🥈", "🥉", "4.", "5."][rank]
        curr  = " ✓" if r["type"] == vehicle_type else ""
        front = " 🌿" if r["type"] in frontier else ""
        top3_rows += (f'<tr><td>{medal}</td>'
                      f'<td><b>{r["icon"]} {r["label"]}</b>{curr}{front}</td>'
                      f'<td>{fmt_duration(r["time_min"])}</td>'
                      f'<td style="background:{_co2_color(r["co2_g"])};">{r["co2_g"]:.0f} g</td>'
                      f'<td>{ws:.3f}</td></tr>')

    st.markdown(f"""
    <table class="compare-table">
      <thead><tr><th>#</th><th>Mode</th><th>Time</th><th>CO₂</th><th>Score ↓</th></tr></thead>
      <tbody>{top3_rows}</tbody>
    </table>""", unsafe_allow_html=True)

    # Pareto scatter SVG
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f'<div style="border-radius:10px;overflow:hidden;">'
                f'{_render_pareto_svg(comparison, vehicle_type, frontier, best["type"])}</div>',
                unsafe_allow_html=True)
    st.caption("🌿 = Pareto frontier (no mode is better on both time AND CO₂)  ·  Orange ring = your selection  ·  Yellow = optimal at current slider")

    # ── All-mode comparison table ─────────────────────────────────────────────
    st.markdown('<div class="sec">📊 All Modes vs Petrol Car Baseline</div>', unsafe_allow_html=True)

    hdr = """<table class="compare-table"><thead><tr>
      <th>Mode</th><th>Travel Time</th><th>CO₂</th><th>g/km</th><th>Eco Score</th><th>vs Petrol Car</th>
    </tr></thead><tbody>"""
    rows_html = ""
    for r in comparison:
        is_curr = r["type"] == vehicle_type
        rc      = "row-current" if is_curr else ""
        diff    = round((r["co2_g"] - car_base_co2) / car_base_co2 * 100) if car_base_co2 > 0 else 0
        vs_txt  = ('<span style="color:#2e7d32;font-weight:600;">−' + str(abs(diff)) + '%</span>' if diff < 0
                   else '<span style="color:#666;">baseline</span>' if diff == 0
                   else '<span style="color:#c62828;font-weight:600;">+' + str(diff) + '%</span>')
        lbl = r["icon"] + " " + r["label"] + (" ✓" if is_curr else "") + (" 🌿" if r["type"] == greenest["type"] and not is_curr else "")
        rows_html += (f'<tr class="{rc}"><td>{"<b>"+lbl+"</b>" if is_curr else lbl}</td>'
                      f'<td>{fmt_duration(r["time_min"])}</td>'
                      f'<td style="background:{_co2_color(r["co2_g"])};">{r["co2_g"]:.0f} g</td>'
                      f'<td>{r["co2_per_km"]:.1f}</td><td>{r["eco_score"]}</td><td>{vs_txt}</td></tr>')
    st.markdown(hdr + rows_html + "</tbody></table>", unsafe_allow_html=True)

    # ── Departure time optimizer ──────────────────────────────────────────────
    st.markdown('<div class="sec">🕐 Departure Time Optimizer</div>', unsafe_allow_html=True)

    sweep    = departure_time_sweep(dist, vehicle_type, wx["temp"], wx["is_raining"])
    opt_slot = min(sweep, key=lambda r: r["co2_g"])
    cur_slot = min(sweep, key=lambda r: abs(r["minute"] - start_min))

    if opt_slot["co2_g"] < cur_slot["co2_g"] and cur_slot["co2_g"] > 0:
        savings_pct = round((cur_slot["co2_g"] - opt_slot["co2_g"]) / cur_slot["co2_g"] * 100)
        time_diff   = opt_slot["time_min"] - cur_slot["time_min"]
        time_note   = f" (+{fmt_duration(time_diff)} travel)" if time_diff > 1 else ""
        st.markdown(f'<div class="rec-box">⏰ <b>Leave at {opt_slot["label"]}</b> instead of '
                    f'{cur_slot["label"]} → save <b>{savings_pct}% CO₂{time_note}</b></div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="rec-box">✅ <b>{cur_slot["label"]}</b> is already the optimal departure window for this route.</div>',
                    unsafe_allow_html=True)

    st.markdown(f'<div style="border-radius:10px;overflow:hidden;">'
                f'{_render_departure_svg(sweep, start_min, vp)}</div>',
                unsafe_allow_html=True)

    if vehicle_type in {"train", "bike", "ebike", "walk"}:
        st.caption(f"ℹ️ {vp['label']} emissions don't vary with departure time — no rush-hour effect on this mode.")
    else:
        st.caption("Hover over bars for exact values. Orange = your departure, dark green = optimal, amber = rush hour, light green = off-peak.")

    # ── Itinerary schedule ────────────────────────────────────────────────────
    st.markdown('<div class="sec">📋 Itinerary Schedule</div>', unsafe_allow_html=True)
    rows = ""
    for i, (s, note) in enumerate(zip(schedule, notes)):
        arrive_str = fmt_time(s["arrive_min"]) if i > 0 else "—"
        depart_str = fmt_time(s["depart_min"]) if s["dist_km"] > 0 or i < len(schedule)-1 else "—"
        travel_str = fmt_duration(s["travel_min"]) if i > 0 else "—"
        dur_str    = fmt_duration(durations[i]) if durations[i] > 0 else "—"
        note_html  = f'<span style="color:{C["muted"]};font-size:.8rem;">📝 {note}</span>' if note else ""
        label      = "🟢" if i == 0 else ("🔴" if i == len(schedule)-1 and not round_trip else "🔵")
        rows += (f'<tr><td><b>{i+1}</b></td>'
                 f'<td>{label} {s["name"]}<br>{note_html}</td>'
                 f'<td>{arrive_str}</td><td>{dur_str}</td>'
                 f'<td>{depart_str}</td><td>{travel_str}</td>'
                 f'<td>{s["dist_km"]:.2f} km</td></tr>')

    st.markdown(f"""
    <table class="sched-table"><thead><tr>
      <th>#</th><th>Location</th><th>Arrive</th><th>Duration</th>
      <th>Depart</th><th>Travel to next</th><th>Distance</th>
    </tr></thead><tbody>{rows}</tbody></table>""", unsafe_allow_html=True)

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown('<div class="sec">📥 Export</div>', unsafe_allow_html=True)
    lines = [
        f"EcoRoute Itinerary — {trip_date.strftime('%B %d, %Y')}",
        f"Vehicle: {vp['label']}  |  Distance: {dist:.1f} km ({routing_src})  |  CO₂: {co2/1000:.2f} kg  |  Eco Score: {score}/100",
        f"Weather: {wx['icon']} {wx['temp']:.0f}°C{'  Rain' if wx['is_raining'] else ''}",
        f"Travel time: {fmt_duration(total_travel_min)}  |  Finish: {fmt_time(schedule[-1]['depart_min'])}",
        f"CO₂ saved vs petrol car: {savings['saved_g']/1000:.2f} kg ({savings['saved_pct']:.0f}%)",
        f"Optimal departure: {opt_slot['label']}",
        "", "SCHEDULE", "-" * 60,
    ]
    for i, (s, note) in enumerate(zip(schedule, notes)):
        lines.append(f"{i+1}. {s['name']}")
        arrive_str = fmt_time(s['arrive_min']) if i > 0 else 'Start'
        lines.append(f"   Arrive: {arrive_str}  |  Duration: {fmt_duration(durations[i])}  |  Depart: {fmt_time(s['depart_min'])}")
        if note: lines.append(f"   Note: {note}")
        if i < len(schedule)-1:
            lines.append(f"   ↓  {fmt_duration(schedule[i+1]['travel_min'])} ({schedule[i+1]['dist_km']:.2f} km)")
        lines.append("")

    st.download_button("⬇️ Download Itinerary (.txt)", data="\n".join(lines),
                       file_name=f"ecoroute_{trip_date}.txt", mime="text/plain")

    # ── Route map (real roads if OSRM, dashed straight line otherwise) ────────
    st.markdown('<div class="sec">🗺️ Optimized Route Map</div>', unsafe_allow_html=True)
    clat = sum(r[1] for r in route) / len(route)
    clon = sum(r[2] for r in route) / len(route)
    m    = folium.Map(location=[clat, clon], zoom_start=13, tiles="CartoDB positron")

    for i, (name, lat, lon) in enumerate(route):
        color = "green" if i == 0 else ("red" if i == len(route)-1 else "blue")
        leg_co2 = estimate_co2_v2(schedule[i]["dist_km"], vehicle_type, wx["temp"], wx["is_raining"], start_min)
        popup_txt = (f"<b>{name}</b><br>"
                     f"Arrive: {fmt_time(schedule[i]['arrive_min'])}<br>"
                     f"Leg CO₂: {leg_co2:.0f} g")
        folium.Marker([lat, lon],
                      popup=folium.Popup(popup_txt, max_width=220),
                      tooltip=f"{i+1}. {name} | {fmt_time(schedule[i]['arrive_min'])}",
                      icon=folium.Icon(color=color, icon="circle", prefix="fa")).add_to(m)

    if osrm:
        road_line = [[coord[1], coord[0]] for coord in osrm["geometry_lonlat"]]
        folium.PolyLine(road_line, color=C["primary"], weight=4, opacity=0.85,
                        tooltip="Real road path").add_to(m)
    else:
        folium.PolyLine([[r[1], r[2]] for r in route],
                        color=C["primary"], weight=4, opacity=0.65,
                        dash_array="8", tooltip="Estimated path").add_to(m)

    components.html(m.get_root().render(), height=480)

    if osrm:
        st.caption("🛣️ Route drawn on actual roads via OSRM.")
    else:
        st.caption("📐 Straight-line estimate shown (OSRM unavailable for this mode).")

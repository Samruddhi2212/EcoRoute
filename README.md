# 🌿 EcoRoute Optimizer

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://eco-route-optimizer.streamlit.app/)

> **Plan smarter, greener journeys — schedule stops, estimate CO₂, and optimize your route.**

**Live app:** https://eco-route-optimizer.streamlit.app/

EcoRoute Optimizer is an interactive itinerary planner and route optimizer that helps users plan multi-stop journeys while minimizing CO₂ emissions. It geocodes addresses, applies a nearest-neighbor heuristic to order stops efficiently, builds a time-based schedule, and maps the full route with a per-segment carbon breakdown.

---

## Demo

![EcoRoute demo map](assets/demo_map.png)

---

## Research Abstract

Urban transportation accounts for roughly 24% of global CO₂ emissions. Small optimizations in the order of everyday stops — groceries, school runs, errands — can meaningfully reduce fuel consumption and emissions at scale. EcoRoute Optimizer demonstrates that a lightweight greedy heuristic (nearest-neighbor TSP) combined with per-mode emission factors is sufficient to produce practical, eco-conscious route suggestions without requiring complex solvers or real-time traffic APIs. The app visualizes the trade-off between route distance and carbon output across five transport modes, giving users immediate, actionable feedback.

---

## Features

- **Address-based stop entry** — type any real-world address, automatically geocoded via OpenStreetMap
- **Multi-stop route optimization** via nearest-neighbor TSP heuristic
- **Itinerary scheduler** — set a trip date, start time, and duration per stop; get a full arrive/depart timeline
- **Notes per stop** — attach reminders like "pick up tickets" or "lunch break"
- **Round trip toggle** — automatically adds a return leg back to the start
- **CO₂ estimation** across 5 transport modes (car, bus, train, bike, walk)
- **Eco Score** (0–100) summarizing environmental impact at a glance
- **6 summary metrics** — distance, CO₂, eco score, travel time, time at stops, estimated finish
- **Interactive Folium map** — color-coded markers (green start, blue stops, red end) with a route polyline
- **Live map preview** — updates as you type addresses, before calculating
- **Download itinerary** — export the full schedule as a `.txt` file

---

## Tech Stack

### Frontend & UI
| Technology | Version | Purpose |
|---|---|---|
| [Streamlit](https://streamlit.io) | ≥ 1.32 | App framework — UI components, layout, session state, custom CSS injection |
| HTML / CSS | — | Custom styled cards, metric boxes, schedule table, hero banner via `st.markdown(unsafe_allow_html=True)` |
| `streamlit.components.v1` | built-in | Embeds raw Folium HTML and custom Leaflet components inside iframes |

### Mapping
| Technology | Version | Purpose |
|---|---|---|
| [Folium](https://python-visualization.github.io/folium/) | ≥ 0.16 | Generates interactive Leaflet.js maps as HTML — route polylines, colored markers |
| [Leaflet.js](https://leafletjs.com) | 1.9.4 (CDN) | Underlying JS map engine used by Folium and the custom click component |
| CartoDB Positron | — | Clean, minimal tile layer for the base map |

### Geocoding & Location
| Technology | Version | Purpose |
|---|---|---|
| [Geopy](https://geopy.readthedocs.io/) | ≥ 2.4 | Python geocoding library — wraps Nominatim API |
| [Nominatim](https://nominatim.openstreetmap.org/) (OpenStreetMap) | — | Free geocoding API — converts addresses → (lat, lon) and reverse |
| `@st.cache_data` | built-in | Caches geocode results so repeated addresses don't re-hit the API |

### Routing & Optimization
| Technology | Purpose |
|---|---|
| Nearest-neighbor heuristic | Greedy TSP approximation — iteratively picks the closest unvisited stop. O(n²), practical for < 20 stops |
| Haversine formula | Computes great-circle distance (km) between two GPS coordinates — no external API needed |
| Fixed start/end with optimized waypoints | Start and end points are locked; only intermediate stops are reordered |

### Emissions & Scheduling
| Component | Detail |
|---|---|
| CO₂ emission factors | g CO₂ per km by mode: car 120, bus 68, train 14, bike 0, walk 0 (UK DESNZ 2023) |
| Eco Score (0–100) | Normalized against a 100 km car baseline (~12,000 g CO₂) |
| Travel time estimation | Distance ÷ mode speed (car 50 km/h, bus 25, train 70, bike 15, walk 5) |
| Schedule builder | Chains arrive/depart times across all stops, accounting for travel time + user-defined dwell time per stop |

### Backend & Language
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Core language |
| [Requests](https://docs.python-requests.org/) | ≥ 2.31 | HTTP client (used internally by Geopy) |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | ≥ 1.0 | Loads `.env` files for any API keys |
| [OpenRouteService](https://openrouteservice.org/) SDK | ≥ 2.3 | Available for future road-accurate routing (not active by default) |

### Deployment & DevOps
| Technology | Purpose |
|---|---|
| [Streamlit Community Cloud](https://streamlit.io/cloud) | Free hosting — auto-redeploys on every push to `main` |
| [GitHub](https://github.com/Samruddhi2212/EcoRoute) | Source control and CI/CD trigger |
| GitHub Actions | Runs flake8 lint check on every push (`.github/workflows/ci.yml`) |
| `venv` | Isolated Python environment to avoid system-level dependency conflicts |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Samruddhi2212/EcoRoute.git
cd EcoRoute
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

---

## Project Structure

```
EcoRoute-Optimizer/
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions — lint on push
├── components/
│   └── click_map/
│       └── index.html    # Custom Leaflet component
├── data/                 # Static datasets (if needed)
├── assets/
│   └── demo_map.png      # Screenshot for README
├── .gitignore
├── README.md
├── requirements.txt
├── app.py                # Main Streamlit application
└── utils.py              # Haversine, CO₂ math, scheduler, optimizer
```

---

## Emission Factors

| Mode  | g CO₂ / km | Avg speed used |
|-------|-----------|----------------|
| Car   | 120       | 50 km/h        |
| Bus   | 68        | 25 km/h        |
| Train | 14        | 70 km/h        |
| Bike  | 0         | 15 km/h        |
| Walk  | 0         | 5 km/h         |

Sources: UK Dept. for Energy Security and Net Zero (2023 conversion factors).

---

## Future Work

- Integrate OpenRouteService / OSRM for road-accurate distances
- Add electric vehicle emission profiles
- Weather forecast per stop (Open-Meteo API)
- Export itinerary as PDF
- Multi-day trip planning

---

## License

MIT

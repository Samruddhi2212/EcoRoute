# 🌿 EcoRoute Optimizer

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://eco-route-optimizer.streamlit.app/)

> **Plan smarter, greener journeys — compare vehicle modes, quantify CO₂ impact, and schedule stops intelligently.**

**Live app:** https://eco-route-optimizer.streamlit.app/

EcoRoute Optimizer is an interactive itinerary planner and multi-objective route optimizer. It geocodes addresses, applies a nearest-neighbor heuristic to order stops efficiently, builds a time-based schedule with rush-hour awareness, fetches live weather to model real-world emissions, and compares all transport modes side-by-side so users can make genuinely informed decisions about their carbon footprint.

---

## Demo

![EcoRoute demo map](assets/demo_map.png)

---

## Research Abstract

Urban transportation accounts for roughly 24% of global CO₂ emissions. Small optimizations in the choice of mode, departure time, and stop order can meaningfully reduce fuel consumption and emissions at scale. EcoRoute Optimizer demonstrates a multi-objective decision framework: rather than simply finding the shortest path, it exposes the Pareto trade-off between travel time, cost, and carbon emissions across ten vehicle profiles. The carbon model incorporates vehicle-specific emission factors (DEFRA/EPA 2023), time-of-day traffic multipliers, and real-time weather coefficients — making it materially more accurate than flat per-km estimates. A mode comparison table and CO₂ equivalence panel (tree-days, smartphone charges) give users immediate, relatable feedback to drive behavior change.

---

## Features

### Core planning
- **Address-based stop entry** — type any real-world address, automatically geocoded via OpenStreetMap
- **Multi-stop route optimization** via nearest-neighbor TSP heuristic
- **Itinerary scheduler** — set trip date, start time, and dwell duration per stop; get a full arrive/depart timeline
- **Notes per stop** — attach reminders like "pick up tickets" or "lunch break"
- **Round trip toggle** — automatically adds a return leg to the start

### Intelligent emissions engine
- **10 vehicle profiles** — Car (Petrol / Diesel / Hybrid / Electric), Motorcycle, Bus, Train, E-Bike, Bike, Walk — each with real-world emission factors (g CO₂/km)
- **Time-of-day traffic model** — rush hour (7–9 AM, 5–7 PM) adds 20–35% to both travel time and fuel burn; night routes are 15–20% faster/cleaner
- **Live weather integration** — fetches real-time temperature and precipitation via [Open-Meteo](https://open-meteo.com/) (free, no API key); cold starts (<10 °C) and rain increase emissions by up to 20%
- **Rush-hour-aware scheduling** — each leg uses its actual departure time to calculate the correct traffic multiplier

### Multi-objective comparison
- **Mode comparison table** — all 10 modes ranked by CO₂ for the same route; color-coded cells from deep green (zero) to red (high); shows % savings vs petrol car baseline
- **Greenest-mode recommendation** — suggests switching if a greener option cuts CO₂ by ≥ 30% and shows the time cost
- **CO₂ impact panel** — savings vs petrol baseline, tree-days to absorb equivalent CO₂, smartphone charges equivalent, per-trip eco score (0–100)

### Visualization & export
- **7 summary metrics** — distance, CO₂ emitted, eco score, travel time, stop time, weather context, estimated finish
- **Interactive Folium map** — color-coded markers with per-leg CO₂ in popups
- **Live map preview** — updates as addresses are typed, before calculating
- **Download itinerary** — export the full schedule as a `.txt` file including weather and CO₂ savings

---

## Tech Stack

### Frontend & UI
| Technology | Version | Purpose |
|---|---|---|
| [Streamlit](https://streamlit.io) | ≥ 1.32 | App framework — UI components, layout, session state, custom CSS |
| HTML / CSS | — | Custom styled cards, comparison tables, impact panels, metric boxes |
| `streamlit.components.v1` | built-in | Embeds raw Folium HTML inside iframes |

### Mapping
| Technology | Version | Purpose |
|---|---|---|
| [Folium](https://python-visualization.github.io/folium/) | ≥ 0.16 | Generates interactive Leaflet.js maps as HTML |
| CartoDB Positron | — | Clean, minimal base map tile layer |

### Geocoding & Location
| Technology | Purpose |
|---|---|
| [Geopy](https://geopy.readthedocs.io/) ≥ 2.4 | Wraps Nominatim API for address → (lat, lon) |
| Nominatim (OpenStreetMap) | Free geocoding API |
| `@st.cache_data` | Caches geocode results to reduce API calls |

### Emissions & Intelligence
| Component | Detail |
|---|---|
| Vehicle emission profiles | 10 profiles with g CO₂/km from DEFRA/EPA 2023 conversion factors |
| Time-of-day traffic model | Rush hour +20–35% time/fuel; night −15–20%; per-leg departure-time aware |
| Weather coefficient | Open-Meteo API — cold start penalty + rain drag on real-time conditions |
| Eco Score (0–100) | Normalized against 100 km petrol-car baseline (~12,000 g CO₂) |
| Multi-mode comparison | All 10 modes evaluated against the same route; Pareto table by CO₂ |
| CO₂ equivalences | Tree-days, smartphone charges, equivalent petrol-car km |

### Routing & Optimization
| Component | Detail |
|---|---|
| Nearest-neighbor heuristic | Greedy TSP approximation — O(n²), practical for < 20 stops |
| Haversine formula | Great-circle distance (km) — no external API dependency |
| Fixed start/end with optimized waypoints | Only intermediate stops are reordered |

### Backend & Deployment
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Core language |
| [Requests](https://docs.python-requests.org/) | ≥ 2.31 | HTTP client for Open-Meteo weather API |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | ≥ 1.0 | Loads `.env` for any future API keys |
| [OpenRouteService](https://openrouteservice.org/) SDK | ≥ 2.3 | Available for road-accurate routing (inactive by default) |
| [Streamlit Community Cloud](https://streamlit.io/cloud) | — | Free hosting, auto-redeploys on push to `main` |
| GitHub Actions | — | Flake8 lint on every push |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Samruddhi2212/EcoRoute.git
cd EcoRoute/EcoRoute-Optimizer
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Project Structure

```
EcoRoute-Optimizer/
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions — lint on push
├── components/
│   └── click_map/
│       └── index.html    # Custom Leaflet component (future)
├── data/                 # Static datasets placeholder
├── assets/
│   └── demo_map.png      # Screenshot for README
├── .gitignore
├── README.md
├── requirements.txt
├── app.py                # Streamlit UI — layout, geocoding, weather, results
└── utils.py              # Emission engine, optimizer, scheduler, comparisons
```

---

## Emission Profiles

| Vehicle | g CO₂ / km | Avg speed | Source |
|---|---|---|---|
| Car (Petrol) | 120 | 50 km/h | DEFRA 2023 |
| Car (Diesel) | 105 | 50 km/h | DEFRA 2023 |
| Car (Hybrid) | 70  | 50 km/h | DEFRA 2023 |
| Car (Electric) | 47 | 50 km/h | UK grid avg 2023 |
| Motorcycle | 103 | 55 km/h | DEFRA 2023 |
| Bus | 68 | 25 km/h | EEA 2023 (per passenger) |
| Train | 14 | 70 km/h | EEA 2023 (per passenger) |
| E-Bike | 8 | 20 km/h | lifecycle grid estimate |
| Bike | 0 | 15 km/h | — |
| Walk | 0 | 5 km/h | — |

Traffic and weather multipliers are applied on top of base factors for road vehicles.

---

## Future Work

- OpenRouteService / OSRM integration for road-accurate distances (vs current haversine)
- Graph Neural Network routing on real road topology
- Reinforcement learning routing agent (minimize emissions + time jointly)
- Multi-day trip planning
- Export itinerary as PDF
- API mode — EcoRoute as a service

---

## License

MIT

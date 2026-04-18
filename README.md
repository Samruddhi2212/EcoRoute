# 🌿 EcoRoute Optimizer

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://eco-route-optimizer.streamlit.app/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Multi-objective carbon-aware routing with real road distances, Pareto optimization, and physics-grounded emission modeling.**

**Live app:** https://eco-route-optimizer.streamlit.app/  
**Repo:** https://github.com/Samruddhi2212/EcoRoute

---

## Abstract

Urban transportation is responsible for approximately 24% of global CO₂ emissions, with individual routing decisions representing one of the highest-leverage points for behavioral intervention. EcoRoute Optimizer frames trip planning as a **multi-objective optimization problem** over the objectives of travel time, carbon emissions, and route distance — rather than the single-objective shortest-path problem solved by conventional navigation.

The system implements a physics-grounded emission model that extends flat per-km factors with vehicle-specific profiles (DEFRA/EPA 2023), time-of-day traffic multipliers derived from empirical congestion patterns, and real-time weather coefficients capturing cold-start penalties and aerodynamic drag. Routes are sourced from the **OSRM Contraction Hierarchies** engine, providing actual road geometry and distances rather than Euclidean approximations. Stop ordering is solved with a **nearest-neighbor greedy TSP heuristic**. The Pareto frontier across all ten vehicle profiles is computed exactly, and a parametric slider exposes the full trade-off surface via a weighted scalarization. A 24-hour departure sweep identifies the globally optimal departure window for any given route under the current weather conditions.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        app.py  (UI layer)                       │
│  Streamlit + Folium + custom SVG charts                         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Geocoding   │  │   Weather    │  │   OSRM Routing       │  │
│  │  Nominatim   │  │  Open-Meteo  │  │  (real road paths)   │  │
│  │  (OSM)       │  │  REST API    │  │  REST API            │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                      utils.py  (engine layer)                   │
│                                                                  │
│  CO₂ Model  │  Pareto Frontier  │  TSP Heuristic  │  Scheduler │
└─────────────────────────────────────────────────────────────────┘
```

All three external API calls are wrapped in `@st.cache_data` with appropriate TTLs: geocoding (session-scoped), weather (1800 s), OSRM (3600 s).

---

## Mathematical Models

### 1. Distance — Haversine Formula

For two GPS coordinates $(\phi_1, \lambda_1)$ and $(\phi_2, \lambda_2)$:

$$d = 2R \arcsin\!\left(\sqrt{\sin^2\!\left(\frac{\Delta\phi}{2}\right) + \cos\phi_1\,\cos\phi_2\,\sin^2\!\left(\frac{\Delta\lambda}{2}\right)}\right)$$

where $R = 6371\,\text{km}$ (Earth's mean radius) and $\Delta\phi$, $\Delta\lambda$ are differences in latitude and longitude in radians. This gives the **great-circle (straight-line) distance**. OSRM road distances are 20–40% longer on average due to road network topology.

For trains (no OSRM profile), a correction factor $\kappa = 1.25$ is applied:

$$d_{\text{rail}} = \kappa \cdot d_{\text{haversine}}$$

---

### 2. CO₂ Emission Model

The core emission estimate for a trip of distance $d$ (km) is:

$$\text{CO}_2 \;[\text{g}] = d \;\cdot\; \varepsilon_v \;\cdot\; \gamma(t_{\text{dep}},\, v) \;\cdot\; \omega(T,\, r)$$

where:

| Symbol | Meaning |
|--------|---------|
| $\varepsilon_v$ | Vehicle emission factor (g CO₂ / km), see table below |
| $\gamma(t_{\text{dep}}, v)$ | Time-of-day traffic multiplier (§2.1) |
| $\omega(T, r)$ | Weather coefficient (§2.2) |
| $t_{\text{dep}}$ | Actual departure time of the leg (minutes since midnight) |

**Simplified forms by vehicle category:**

$$\text{CO}_2 = \begin{cases} d \cdot \varepsilon_v & v = \text{train} \\[4pt] d \cdot \varepsilon_v \cdot \gamma(t_{\text{dep}}, v) & v = \text{bus} \\[4pt] d \cdot \varepsilon_v \cdot \gamma(t_{\text{dep}}, v) \cdot \omega(T, r) & v \in \{\text{cars, motorcycle, e-bike}\} \\[4pt] 0 & v \in \{\text{bike, walk}\} \end{cases}$$

---

#### 2.1 Time-of-Day Traffic Multiplier

Empirically derived from urban congestion data. Applied per-leg using the **actual departure time** of each leg (not the trip start time), so a route that departs at 08:45 for leg 1 but 10:20 for leg 2 uses different multipliers for each leg.

$$\gamma(t, v) = \begin{cases} 1.35 & t \in [07{:}00,\,09{:}00) \cup [17{:}00,\,19{:}00),\quad v \neq \text{bus} \\ 1.20 & t \in [07{:}00,\,09{:}00) \cup [17{:}00,\,19{:}00),\quad v = \text{bus} \\ 0.80 & t \in [22{:}00,\,24{:}00) \cup [00{:}00,\,06{:}00),\quad v \neq \text{bus} \\ 0.90 & t \in [22{:}00,\,24{:}00) \cup [00{:}00,\,06{:}00),\quad v = \text{bus} \\ 1.00 & \text{otherwise} \end{cases}$$

$\gamma$ also applies to **travel time**: $t_{\text{leg}} = \dfrac{d}{s_v} \cdot \gamma(t_{\text{dep}}, v) \cdot 60$ minutes, where $s_v$ is the free-flow speed (km/h) for vehicle $v$.

For $v \in \{\text{train, bike, e-bike, walk}\}$, $\gamma \equiv 1$ (unaffected by road congestion).

---

#### 2.2 Weather Coefficient

Sourced from real-time conditions via Open-Meteo. Temperature effect models cold-start engine inefficiency and battery range loss; rain effect models aerodynamic drag and reduced speed.

$$\omega_T(T) = \begin{cases} 1 + 0.015\,(10 - T) & T < 10\,°\text{C} \\ 1 + 0.005\,(T - 35) & T > 35\,°\text{C} \\ 1.0 & \text{otherwise} \end{cases}$$

$$\omega_r(r) = \begin{cases} 1.08 & \text{precipitation} > 0.1\,\text{mm/h} \\ 1.0 & \text{otherwise} \end{cases}$$

$$\omega(T, r) = \omega_T(T) \cdot \omega_r(r)$$

Maximum combined weather penalty: ~35% at $T = -13\,°\text{C}$ with rain.

---

### 3. Eco Score

Normalized 0–100 score mapping emissions against a worst-case baseline (100 km petrol car ≈ 12,000 g CO₂):

$$S_{\text{eco}} = \max\!\left(0,\; 100 - \frac{\text{CO}_2}{12\,000} \times 100\right)$$

Score is intentionally absolute (not relative to mode) so that short trips score high regardless of vehicle, providing a useful proxy for total impact.

---

### 4. Pareto Frontier

Given the set of all modes $\mathcal{M}$, each with attributes $(t_m, c_m)$ for travel time and CO₂:

**Definition.** Mode $A$ **dominates** mode $B$ if and only if:

$$c_A \leq c_B \;\land\; t_A \leq t_B \;\land\; (c_A < c_B \;\lor\; t_A < t_B)$$

The **Pareto frontier** $\mathcal{F} \subseteq \mathcal{M}$ is the set of non-dominated modes — those for which no other mode is at least as good on both dimensions and strictly better on one:

$$\mathcal{F} = \{m \in \mathcal{M} \mid \nexists\; m' \in \mathcal{M} : m' \text{ dominates } m\}$$

For a typical 10 km urban trip: $\mathcal{F} = \{\text{Bike},\, \text{E-Bike},\, \text{Train}\}$.  
Walk is dominated by Bike (same zero CO₂, strictly less time). All car variants are dominated by Train (less CO₂ **and** less time).

---

### 5. Multi-Objective Weighted Scalarization (Pareto Slider)

To expose the full Pareto trade-off surface, a scalar preference parameter $\alpha \in [0, 1]$ controls weight between objectives. Both dimensions are min-max normalized over all modes before weighting:

$$\mathcal{S}(m,\, \alpha) = (1-\alpha)\cdot\frac{t_m}{t_{\max}} + \alpha\cdot\frac{c_m}{c_{\max}}$$

The optimal mode at preference $\alpha$ is:

$$m^*(\alpha) = \arg\min_{m \in \mathcal{M}}\; \mathcal{S}(m,\, \alpha)$$

- $\alpha = 0$ → pure time minimization → fastest mode
- $\alpha = 1$ → pure CO₂ minimization → greenest mode
- $\alpha \in (0,1)$ → weighted trade-off surface

As $\alpha$ sweeps from 0 to 1, $m^*(\alpha)$ traces the Pareto frontier modes in order of increasing CO₂ / decreasing time.

---

### 6. Schedule Builder — Recurrence Relation

The schedule is computed as a recurrence where each leg departure is the input to the next leg's time-of-day factor:

$$t^{(0)}_{\text{arrive}} = t^{(0)}_{\text{depart}} = t_{\text{start}}$$

For each subsequent stop $i \geq 1$:

$$t^{(i)}_{\text{arrive}} = t^{(i-1)}_{\text{depart}} + \frac{d_i}{s_v} \cdot \gamma\!\left(t^{(i-1)}_{\text{depart}},\, v\right) \cdot 60$$

$$t^{(i)}_{\text{depart}} = t^{(i)}_{\text{arrive}} + \Delta_i$$

where $d_i$ is the road distance of leg $i$ (from OSRM), $s_v$ is free-flow speed, and $\Delta_i$ is the user-specified dwell time at stop $i$.

---

### 7. Departure Time Optimizer

A full 24-hour sweep computes $\text{CO}_2$ and travel time for each 1-hour departure slot:

$$\text{CO}_2(t_{\text{dep}}) = d \cdot \varepsilon_v \cdot \gamma(t_{\text{dep}}, v) \cdot \omega(T, r)$$

The optimal departure is:

$$t^*_{\text{dep}} = \arg\min_{t_{\text{dep}} \in \{0, 60, 120, \ldots, 1380\}} \text{CO}_2(t_{\text{dep}})$$

For a petrol car, the optimal window is typically early morning (00:00–06:00) where $\gamma = 0.80$, yielding a **20% CO₂ reduction** vs a rush-hour departure.

---

### 8. Stop Order Optimization — Nearest-Neighbor TSP

Given $n$ intermediate waypoints, the full Travelling Salesman Problem is NP-hard. A greedy nearest-neighbor heuristic produces a good approximation in $O(n^2)$:

```
P ← [start]
V ← {all waypoints}
while V ≠ ∅:
    v* ← argmin_{v ∈ V} d(P[-1], v)   # haversine distance
    P.append(v*)
    V.remove(v*)
return P + [end]
```

Start and end points are fixed; only intermediate stops are reordered. For $n \leq 20$ stops the greedy solution is within ~25% of optimal on typical urban graphs (Rosenkrantz et al., 1977).

---

## Real Road Routing — OSRM

Routes are fetched from the **OSRM public demo server** (`router.project-osrm.org`) using the **Contraction Hierarchies (CH)** algorithm, which pre-processes the road graph offline to answer shortest-path queries in sub-millisecond time at query time.

**Endpoint format:**
```
GET /route/v1/{profile}/{lon1,lat1;lon2,lat2;...}
    ?overview=full&geometries=geojson
```

**Profiles used:**

| Vehicle category | OSRM profile |
|---|---|
| Car (all), Motorcycle, Bus | `driving` |
| Bike, E-Bike | `cycling` |
| Walk | `foot` |
| Train | — (haversine × 1.25 fallback) |

**Response fields used:**
- `routes[0].legs[i].distance` → per-leg road distance (m) → fed to CO₂ model and schedule
- `routes[0].geometry.coordinates` → GeoJSON `LineString` of 80–300+ points → drawn as actual road polyline in Folium
- `routes[0].duration` → OSRM free-flow time (cross-reference; not used for schedule since we apply $\gamma$ ourselves)

Road distances are consistently **20–45% longer** than haversine for urban routes, which has a proportional effect on CO₂ estimates. Using haversine alone systematically underestimates emissions.

---

## CO₂ Equivalences

To make abstract gram quantities tangible, emissions are converted to relatable units:

| Equivalent | Formula |
|---|---|
| Tree-days | $\text{CO}_2\,[\text{kg}] \div 0.022$ — average tree absorbs ~22 g CO₂/day via photosynthesis |
| Smartphone charges | $\text{CO}_2\,[\text{g}] \div 8.22$ — one full charge of a 15 Wh battery at 0.233 kg CO₂/kWh (UK grid 2023) |
| Petrol-car km | $\text{CO}_2\,[\text{kg}] \times 1000 \div 120$ — equivalent distance driven by avg petrol car |

---

## Emission Profiles

| Vehicle | $\varepsilon_v$ (g CO₂/km) | Free-flow speed | Category | Source |
|---|---|---|---|---|
| Car (Petrol) | 120 | 50 km/h | Driving | DEFRA 2023 |
| Car (Diesel) | 105 | 50 km/h | Driving | DEFRA 2023 |
| Car (Hybrid) | 70  | 50 km/h | Driving | DEFRA 2023 |
| Car (Electric) | 47 | 50 km/h | Driving | UK grid avg, DEFRA 2023 |
| Motorcycle | 103 | 55 km/h | Driving | DEFRA 2023 |
| Bus | 68  | 25 km/h | Transit | EEA 2023, per passenger |
| Train | 14  | 70 km/h | Transit | EEA 2023, per passenger |
| E-Bike | 8   | 20 km/h | Active  | Lifecycle grid avg |
| Bike | 0    | 15 km/h | Active  | — |
| Walk | 0    | 5 km/h  | Active  | — |

Notes:
- EV figure (47 g/km) uses UK average grid carbon intensity (233 g CO₂/kWh, DEFRA 2023) × typical consumption (0.2 kWh/km)
- Bus and Train factors are **per-passenger** averages at typical load factors (~30 passengers for bus, ~150 for commuter rail)
- Weather and time-of-day multipliers are applied on top of $\varepsilon_v$ for applicable categories

---

## API Integrations

| API | Purpose | Auth | Cache TTL |
|---|---|---|---|
| [Nominatim (OSM)](https://nominatim.openstreetmap.org/) | Address → (lat, lon) geocoding | None | Session |
| [Open-Meteo](https://open-meteo.com/) | Current temperature, precipitation, weather code | None | 30 min |
| [OSRM public server](http://router.project-osrm.org) | Real road distances + route geometry | None | 60 min |

All three are **free and keyless** — the app deploys to Streamlit Community Cloud with zero secrets configuration.

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| UI | Streamlit ≥ 1.32 | App framework, session state, widget reactivity |
| UI | HTML/CSS (inline) | Custom metric cards, comparison tables, SVG charts |
| Mapping | Folium ≥ 0.16 + Leaflet.js | Interactive maps rendered as HTML iframes |
| Mapping | CartoDB Positron | Base tile layer |
| Geocoding | Geopy ≥ 2.4 + Nominatim | Address resolution |
| Routing | OSRM public API | Contraction Hierarchies road routing + GeoJSON geometry |
| Weather | Open-Meteo REST API | Real-time temperature + precipitation |
| Emissions | `utils.py` (pure Python) | CO₂ model, Pareto frontier, departure sweep, TSP heuristic |
| Visualization | SVG (generated in Python) | Pareto scatter, departure bar chart |
| HTTP | Requests ≥ 2.31 | OSRM + Open-Meteo API calls |
| Deployment | Streamlit Community Cloud | Auto-redeploy on push to `main` |
| CI | GitHub Actions | Flake8 lint on every push |

---

## Setup

```bash
git clone https://github.com/Samruddhi2212/EcoRoute.git
cd EcoRoute/EcoRoute-Optimizer
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. No API keys or environment variables required.

---

## Project Structure

```
EcoRoute-Optimizer/
├── app.py          # UI layer: Streamlit layout, API calls, SVG rendering, Folium maps
├── utils.py        # Engine layer: CO₂ model, Pareto, TSP, scheduler, OSRM client
├── requirements.txt
├── .github/
│   └── workflows/ci.yml   # Flake8 lint on push
├── components/
│   └── click_map/index.html  # Custom Leaflet component (future)
└── data/           # Static dataset placeholder
```

`utils.py` is intentionally pure-Python (stdlib `math` + `requests` only) with no compiled extensions — all numerical work is done in native Python loops and arithmetic, keeping the module compatible with any deployment environment.

---

## Future Work

- **Graph Neural Network routing** — model road network as a graph; learn edge-weight embeddings that predict congestion-adjusted travel time and emissions jointly
- **Reinforcement learning routing agent** — Q-learning or PPO agent that learns routing policies by interacting with a simulated road environment (state: current node + time; action: next edge; reward: −CO₂ − λ·time)
- **Multi-day trip planning** — extend schedule builder across midnight boundaries with overnight stops
- **PDF itinerary export** — formatted report with map thumbnail and per-leg breakdown
- **EcoRoute API** — FastAPI wrapper exposing the emission engine and Pareto optimizer as a REST service

---

## License

MIT

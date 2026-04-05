# 🌿 EcoRoute Optimizer

> **Plan smarter, greener routes — visualize your carbon footprint in real time.**

EcoRoute Optimizer is an interactive web app built with [Streamlit](https://streamlit.io) that helps users plan multi-stop routes while minimizing CO₂ emissions. It applies a nearest-neighbor heuristic to order stops efficiently, then maps the route and breaks down the environmental impact by segment and transport mode.

---

## Demo

![EcoRoute demo map](assets/demo_map.png)

---

## Research Abstract

Urban transportation accounts for roughly 24% of global CO₂ emissions. Small optimizations in the order of everyday stops — groceries, school runs, errands — can meaningfully reduce fuel consumption and emissions at scale. EcoRoute Optimizer demonstrates that a lightweight greedy heuristic (nearest-neighbor TSP) combined with per-mode emission factors is sufficient to produce practical, eco-conscious route suggestions without requiring complex solvers or real-time traffic APIs. The app visualizes the trade-off between route distance and carbon output across five transport modes, giving users immediate, actionable feedback.

---

## Features

- **Multi-stop route optimization** via nearest-neighbor heuristic
- **CO₂ estimation** per segment across 5 transport modes (car, bus, train, bike, walk)
- **Eco Score** (0–100) to summarize the environmental impact at a glance
- **Interactive map** powered by Folium + streamlit-folium
- **Editable stop table** — add, remove, or reorder stops directly in the UI

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/EcoRoute-Optimizer.git
cd EcoRoute-Optimizer
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
├── .github/          # CI/CD workflows (optional)
├── data/             # Static JSON or CSV datasets
├── assets/           # Screenshots for README
│   └── demo_map.png
├── .gitignore
├── README.md
├── requirements.txt
├── app.py            # Streamlit application
└── utils.py          # Haversine distance, CO₂ math, route optimizer
```

---

## Emission Factors Used

| Mode  | g CO₂ / km |
|-------|-----------|
| Car   | 120       |
| Bus   | 68        |
| Train | 14        |
| Bike  | 0         |
| Walk  | 0         |

Sources: UK Dept. for Energy Security and Net Zero (2023 conversion factors).

---

## Future Work

- Integrate a real routing API (OpenRouteService / OSRM) for road-distance accuracy
- Add electric vehicle emission profiles
- Support round-trip optimization (TSP with return to origin)
- Export route summary as PDF

---

## License

MIT

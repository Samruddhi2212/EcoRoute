"""
graph.py — Road network graph builder for EcoRoute++

Builds a directed weighted graph (networkx.DiGraph) for a city area.
Each edge carries the attributes the optimizer needs:
  distance_km, speed_limit, road_type, elevation_change_m,
  traffic_factor, travel_time_min, fuel_liters, energy_kwh, co2_grams

Two modes:
  1. Synthetic grid  — always available, parameterized by city center + grid size
  2. OSM via Overpass API — fetches real roads with HTTP-only (no osmnx / geopandas)

Usage:
  from routing.graph import build_synthetic_graph, add_ml_edge_weights
  G = build_synthetic_graph()
  G = add_ml_edge_weights(G, vehicle_type="sedan", traffic_factor=1.0)
"""

import math
import random
from typing import Any

import networkx as nx

# ── Physics helpers (duplicated here to keep routing self-contained) ──────────

_ROAD_SPEED = {
    "residential": 30,
    "arterial":    50,
    "highway":     80,
    "motorway":   110,
}

_ROAD_TYPE_ENC = {"residential": 0, "arterial": 1, "highway": 2, "motorway": 3}
_VEHICLE_ENC   = {"sedan": 0, "suv": 1, "ev": 2}
_CO2_FACTOR    = {"sedan": 120, "suv": 175, "ev": 47}   # g/km baseline


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _fuel_consumption(
    distance_km: float,
    speed_kmh: float,
    elevation_gain_m: float,
    traffic: float,
    vehicle_type: str,
) -> tuple[float, float, float]:
    """Returns (fuel_liters, energy_kwh, co2_grams) for an edge."""
    sf = 1.0 + 0.8 * (abs(speed_kmh - 80) / 80) ** 1.6 if speed_kmh > 0 else 2.5
    grade = elevation_gain_m / (distance_km * 1000 + 1e-9) * 100
    ef = 1.0 + max(0.0, grade) * 0.04
    tf = 1.0 + max(0.0, traffic - 1.0) * 0.30

    if vehicle_type == "ev":
        kwh   = (distance_km / 100) * 16.0 * sf * ef * tf
        co2_g = kwh * 233.0
        return 0.0, round(kwh, 4), round(co2_g, 2)
    else:
        base_l  = 7.0 if vehicle_type == "sedan" else 10.5
        fuel_l  = (distance_km / 100) * base_l * sf * ef * tf
        co2_g   = fuel_l * 2310.0
        return round(fuel_l, 4), 0.0, round(co2_g, 2)


# ── Synthetic grid graph ──────────────────────────────────────────────────────

def build_synthetic_graph(
    center_lat: float  = 42.3601,   # Boston
    center_lon: float  = -71.0589,
    rows: int          = 12,
    cols: int          = 12,
    block_km: float    = 0.35,       # ~350 m city blocks
    seed: int          = 7,
) -> nx.DiGraph:
    """
    Build a directed grid road network.

    Node attributes:  lat, lon, elevation_m, node_id
    Edge attributes:  distance_km, speed_limit, road_type, elevation_change_m,
                      traffic_factor, base_time_min
    """
    rng = random.Random(seed)
    G   = nx.DiGraph()

    # Degree-to-km conversion at this latitude
    lat_per_km = 1.0 / 111.0
    lon_per_km = 1.0 / (111.0 * math.cos(math.radians(center_lat)))

    # Build elevation terrain (simple smooth hills)
    def _elevation(r: int, c: int) -> float:
        norm_r = r / max(rows - 1, 1)
        norm_c = c / max(cols - 1, 1)
        return (
            30.0
            + 25.0 * math.sin(norm_r * math.pi)
            + 15.0 * math.sin(norm_c * math.pi * 2)
            + rng.gauss(0, 3)
        )

    # ── Nodes ─────────────────────────────────────────────────────────────────
    elevations = {}
    for r in range(rows):
        for c in range(cols):
            nid  = r * cols + c
            lat  = center_lat + (r - rows // 2) * block_km * lat_per_km
            lon  = center_lon + (c - cols // 2) * block_km * lon_per_km
            elev = _elevation(r, c)
            elevations[nid] = elev
            G.add_node(nid, lat=round(lat, 6), lon=round(lon, 6),
                       elevation_m=round(elev, 1), node_id=nid)

    # ── Edges ──────────────────────────────────────────────────────────────────
    # Assign road types based on position (outer ring = highway, diagonals = arterial)
    def _road_type(r: int, c: int, dr: int, dc: int) -> str:
        # Ring road at the boundary
        if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
            return "highway"
        # Every 4th row/col = arterial
        if r % 4 == 0 or c % 4 == 0:
            return "arterial"
        return "residential"

    def _base_traffic(r: int, c: int) -> float:
        # Simulate city-center congestion
        dist_center = math.sqrt((r - rows // 2) ** 2 + (c - cols // 2) ** 2)
        max_dist    = math.sqrt((rows // 2) ** 2 + (cols // 2) ** 2)
        center_f    = 1.0 + 0.8 * (1.0 - dist_center / max(max_dist, 1))
        return round(center_f + rng.uniform(-0.15, 0.15), 2)

    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # E, S, W, N

    for r in range(rows):
        for c in range(cols):
            u   = r * cols + c
            ud  = G.nodes[u]
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    v   = nr * cols + nc
                    vd  = G.nodes[v]
                    rtype = _road_type(r, c, dr, dc)
                    dist  = _haversine(ud["lat"], ud["lon"], vd["lat"], vd["lon"])
                    elev_delta = vd["elevation_m"] - ud["elevation_m"]
                    speed = _ROAD_SPEED[rtype] + rng.randint(-5, 5)
                    tf    = _base_traffic(r, c)
                    eff_speed = max(speed / tf, 5)
                    G.add_edge(u, v,
                               distance_km      = round(dist, 4),
                               speed_limit      = speed,
                               road_type        = rtype,
                               road_type_enc    = _ROAD_TYPE_ENC[rtype],
                               elevation_change_m = round(elev_delta, 2),
                               traffic_factor   = tf,
                               base_time_min    = round(dist / eff_speed * 60, 3))

    # Add a few diagonal shortcut edges to make routing more interesting
    for r in range(0, rows - 1, 2):
        for c in range(0, cols - 1, 2):
            u  = r * cols + c
            v  = (r + 1) * cols + (c + 1)
            if G.has_node(u) and G.has_node(v):
                ud, vd = G.nodes[u], G.nodes[v]
                dist = _haversine(ud["lat"], ud["lon"], vd["lat"], vd["lon"])
                elev_delta = vd["elevation_m"] - ud["elevation_m"]
                G.add_edge(u, v,
                           distance_km       = round(dist, 4),
                           speed_limit       = 40,
                           road_type         = "arterial",
                           road_type_enc     = _ROAD_TYPE_ENC["arterial"],
                           elevation_change_m = round(elev_delta, 2),
                           traffic_factor    = round(1.0 + rng.uniform(-0.1, 0.3), 2),
                           base_time_min     = round(dist / 40 * 60, 3))

    return G


# ── Add ML-derived edge weights ───────────────────────────────────────────────

def add_ml_edge_weights(
    G: nx.DiGraph,
    vehicle_type: str  = "sedan",
    traffic_factor_override: float | None = None,
) -> nx.DiGraph:
    """
    Annotate every edge with fuel_liters, energy_kwh, co2_grams, travel_time_min.

    If a trained ML model is available, uses GradientBoostingRegressor predictions.
    Falls back to physics formula if models aren't trained yet.
    """
    try:
        from models.fuel_model import load_models, FEATURE_NAMES
        import numpy as np
        lr, gb, scaler, _ = load_models()

        def _predict_co2(feat: list) -> float:
            x = np.array([feat])
            return float(max(0.0, gb.predict(x)[0]))

        use_ml = True
    except Exception:
        use_ml = False

    venc = _VEHICLE_ENC.get(vehicle_type, 0)

    for u, v, data in G.edges(data=True):
        dist    = data["distance_km"]
        speed   = data["speed_limit"]
        elev_up = max(0.0, data["elevation_change_m"])
        elev_dn = max(0.0, -data["elevation_change_m"])
        tf      = traffic_factor_override if traffic_factor_override is not None else data["traffic_factor"]
        renc    = data["road_type_enc"]
        eff_spd = max(speed / tf, 5)
        t_min   = dist / eff_spd * 60

        if use_ml:
            feat = [dist, speed, elev_up, elev_dn, tf, renc, venc]
            co2  = _predict_co2(feat)
            # Derive fuel/energy from CO₂ using standard conversion
            if vehicle_type == "ev":
                kwh    = co2 / 233.0
                fuel_l = 0.0
            else:
                fuel_l = co2 / 2310.0
                kwh    = 0.0
        else:
            fuel_l, kwh, co2 = _fuel_consumption(dist, speed, elev_up, tf, vehicle_type)

        data["travel_time_min"] = round(t_min, 3)
        data["fuel_liters"]     = round(fuel_l, 4)
        data["energy_kwh"]      = round(kwh, 4)
        data["co2_grams"]       = round(co2, 2)

    return G


# ── Graph helpers ──────────────────────────────────────────────────────────────

def nearest_node(G: nx.DiGraph, lat: float, lon: float) -> int:
    """Return node ID closest to (lat, lon)."""
    return min(
        G.nodes,
        key=lambda n: _haversine(G.nodes[n]["lat"], G.nodes[n]["lon"], lat, lon),
    )


def graph_stats(G: nx.DiGraph) -> dict:
    """Summary statistics about the graph."""
    edges = list(G.edges(data=True))
    dists = [d["distance_km"] for _, _, d in edges]
    return {
        "nodes":           G.number_of_nodes(),
        "edges":           G.number_of_edges(),
        "total_km":        round(sum(dists), 2),
        "avg_edge_km":     round(sum(dists) / len(dists), 4) if dists else 0,
        "road_types":      list({d["road_type"] for _, _, d in edges}),
        "is_strongly_connected": nx.is_strongly_connected(G),
    }

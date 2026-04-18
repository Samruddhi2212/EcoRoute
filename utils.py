"""
utils.py — Math and optimization logic for EcoRoute Optimizer
"""

import math
import requests


# ── Vehicle emission profiles ─────────────────────────────────────────────────

EMISSION_PROFILES = {
    "car_petrol":  {"label": "Car (Petrol)",    "factor": 120, "speed": 50, "icon": "🚗", "category": "Driving"},
    "car_diesel":  {"label": "Car (Diesel)",    "factor": 105, "speed": 50, "icon": "🚗", "category": "Driving"},
    "car_hybrid":  {"label": "Car (Hybrid)",    "factor": 70,  "speed": 50, "icon": "🚘", "category": "Driving"},
    "car_ev":      {"label": "Car (Electric)",  "factor": 47,  "speed": 50, "icon": "⚡",  "category": "Driving"},
    "motorcycle":  {"label": "Motorcycle",      "factor": 103, "speed": 55, "icon": "🏍️", "category": "Driving"},
    "bus":         {"label": "Bus",             "factor": 68,  "speed": 25, "icon": "🚌", "category": "Transit"},
    "train":       {"label": "Train",           "factor": 14,  "speed": 70, "icon": "🚆", "category": "Transit"},
    "ebike":       {"label": "E-Bike",          "factor": 8,   "speed": 20, "icon": "🛵", "category": "Active"},
    "bike":        {"label": "Bike",            "factor": 0,   "speed": 15, "icon": "🚲", "category": "Active"},
    "walk":        {"label": "Walk",            "factor": 0,   "speed": 5,  "icon": "🚶", "category": "Active"},
}

MODE_TO_VEHICLE = {
    "car": "car_petrol", "bus": "bus", "train": "train",
    "bike": "bike", "walk": "walk",
}

_ROAD_FREE = {"train", "bike", "ebike", "walk"}


# ── Real road routing (OSRM) ──────────────────────────────────────────────────

_OSRM_BASE = "http://router.project-osrm.org/route/v1"

VEHICLE_TO_OSRM = {
    "car_petrol": "driving",
    "car_diesel": "driving",
    "car_hybrid": "driving",
    "car_ev":     "driving",
    "motorcycle": "driving",
    "bus":        "driving",
    "train":      None,        # fixed rail — no OSRM profile
    "ebike":      "cycling",
    "bike":       "cycling",
    "walk":       "foot",
}

# Haversine correction factors for modes without an OSRM profile
ROUTE_FACTOR = {"train": 1.25}


def get_osrm_route(coords_latlon, vehicle_type):
    """
    Fetch a real road route from the OSRM public API (free, no key needed).

    coords_latlon : list of (lat, lon) tuples in route order
    vehicle_type  : EMISSION_PROFILES key or legacy mode string

    Returns dict on success:
      distance_m, duration_s, geometry_lonlat, leg_distances_m, leg_durations_s
    Returns None on failure or unsupported vehicle type (train).
    """
    if vehicle_type in MODE_TO_VEHICLE:
        vehicle_type = MODE_TO_VEHICLE[vehicle_type]
    profile = VEHICLE_TO_OSRM.get(vehicle_type)
    if profile is None:
        return None

    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords_latlon)
    url = f"{_OSRM_BASE}/{profile}/{coord_str}?overview=full&geometries=geojson"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                r = data["routes"][0]
                return {
                    "distance_m":      r["distance"],
                    "duration_s":      r["duration"],
                    "geometry_lonlat": r["geometry"]["coordinates"],
                    "leg_distances_m": [leg["distance"] for leg in r.get("legs", [])],
                    "leg_durations_s": [leg["duration"] for leg in r.get("legs", [])],
                }
    except Exception:
        pass
    return None


# ── Distance ─────────────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance between two GPS coordinates (km)."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def route_total_distance(route):
    """Total haversine distance (km) for ordered list of (name, lat, lon) tuples."""
    total = 0.0
    for i in range(len(route) - 1):
        total += haversine(route[i][1], route[i][2], route[i + 1][1], route[i + 1][2])
    return total


# ── Time-of-day traffic factor ────────────────────────────────────────────────

def get_time_of_day_factor(start_minute, vehicle_type="car_petrol"):
    """
    Travel time / fuel-burn multiplier based on departure time.
    > 1.0 = slower / dirtier.  Rail, cycling, walking always 1.0.
    """
    if vehicle_type in _ROAD_FREE:
        return 1.0
    hour = (int(start_minute) // 60) % 24
    if (7 <= hour < 9) or (17 <= hour < 19):
        return 1.35 if vehicle_type != "bus" else 1.20
    if hour >= 22 or hour < 6:
        return 0.80 if vehicle_type != "bus" else 0.90
    return 1.0


# ── Weather emission factor ───────────────────────────────────────────────────

def weather_emission_factor(temp_celsius, is_raining):
    """Cold-start penalty + rain drag coefficient (road vehicles only)."""
    temp_f = 1.0
    if temp_celsius < 10:
        temp_f = 1.0 + (10 - temp_celsius) * 0.015
    elif temp_celsius > 35:
        temp_f = 1.0 + (temp_celsius - 35) * 0.005
    return temp_f * (1.08 if is_raining else 1.0)


# ── CO₂ estimation ────────────────────────────────────────────────────────────

def estimate_co2(distance_km, mode="car"):
    """Legacy flat CO₂ estimate — kept for backward compatibility."""
    factors = {"car": 120, "bus": 68, "train": 14, "bike": 0, "walk": 0}
    return distance_km * factors.get(mode, 120)


def estimate_co2_v2(distance_km, vehicle_type="car_petrol",
                    temp_celsius=20, is_raining=False, start_minute=540):
    """
    Enhanced CO₂ estimate (g): vehicle profile × weather × time-of-day.
    Trains unaffected by both; buses by traffic only; everything else by both.
    """
    if vehicle_type in MODE_TO_VEHICLE:
        vehicle_type = MODE_TO_VEHICLE[vehicle_type]
    profile = EMISSION_PROFILES.get(vehicle_type, EMISSION_PROFILES["car_petrol"])
    base = profile["factor"]
    if base == 0:
        return 0.0
    tod = get_time_of_day_factor(start_minute, vehicle_type)
    if vehicle_type == "train":
        return distance_km * base
    if vehicle_type == "bus":
        return distance_km * base * tod
    return distance_km * base * weather_emission_factor(temp_celsius, is_raining) * tod


def eco_score(distance_km, vehicle_type="car_petrol",
              temp_celsius=20, is_raining=False, start_minute=540):
    """0–100 score: lower emissions → higher. Baseline = 100 km petrol car."""
    if vehicle_type in MODE_TO_VEHICLE:
        vehicle_type = MODE_TO_VEHICLE[vehicle_type]
    emissions = estimate_co2_v2(distance_km, vehicle_type, temp_celsius, is_raining, start_minute)
    return round(max(0.0, 100.0 - (emissions / 12_000) * 100.0), 1)


# ── Multi-mode comparison ─────────────────────────────────────────────────────

def multi_mode_comparison(distance_km, start_minute=540, temp_celsius=20, is_raining=False):
    """All modes compared for same distance. Returns list sorted by CO₂ asc."""
    results = []
    for vtype, profile in EMISSION_PROFILES.items():
        tod      = get_time_of_day_factor(start_minute, vtype)
        time_min = (distance_km / profile["speed"]) * tod * 60 if profile["speed"] > 0 else 0
        co2      = estimate_co2_v2(distance_km, vtype, temp_celsius, is_raining, start_minute)
        results.append({
            "type":       vtype,
            "label":      profile["label"],
            "icon":       profile["icon"],
            "category":   profile["category"],
            "time_min":   time_min,
            "co2_g":      co2,
            "eco_score":  round(max(0, 100 - (co2 / 12_000) * 100), 1),
            "co2_per_km": round(co2 / distance_km, 1) if distance_km > 0 else 0,
        })
    return sorted(results, key=lambda x: x["co2_g"])


def co2_equivalents(co2_grams):
    kg = co2_grams / 1000
    return {
        "trees_days":    round(kg / 0.022, 1),
        "phone_charges": round(co2_grams / 8.22, 0),
        "car_km":        round(kg * 1000 / 120, 1),
    }


def co2_savings(co2_grams, distance_km, temp_celsius=20, is_raining=False, start_minute=540):
    baseline  = estimate_co2_v2(distance_km, "car_petrol", temp_celsius, is_raining, start_minute)
    saved_g   = max(0.0, baseline - co2_grams)
    saved_pct = (saved_g / baseline * 100) if baseline > 0 else 0
    return {"saved_g": saved_g, "saved_pct": round(saved_pct, 1), "baseline_g": baseline}


# ── Pareto frontier ───────────────────────────────────────────────────────────

def pareto_frontier(modes_data):
    """
    Return set of vehicle type strings on the time–CO₂ Pareto frontier.
    A mode is non-dominated if no other mode is at least as good on BOTH
    dimensions and strictly better on at least one.
    """
    frontier = set()
    for a in modes_data:
        dominated = False
        for b in modes_data:
            if b["type"] == a["type"]:
                continue
            if (b["co2_g"] <= a["co2_g"] and b["time_min"] <= a["time_min"] and
                    (b["co2_g"] < a["co2_g"] or b["time_min"] < a["time_min"])):
                dominated = True
                break
        if not dominated:
            frontier.add(a["type"])
    return frontier


def weighted_pareto_score(time_min, co2_g, alpha, max_time, max_co2):
    """
    Scalar score for Pareto slider: alpha=0 → fastest, alpha=1 → greenest.
    Lower = better. Both dimensions normalized to [0, 1].
    """
    t_norm = time_min / max_time if max_time > 0 else 0
    c_norm = co2_g   / max_co2  if max_co2  > 0 else 0
    return (1 - alpha) * t_norm + alpha * c_norm


# ── Departure time sweep ──────────────────────────────────────────────────────

def departure_time_sweep(distance_km, vehicle_type, temp_celsius=20, is_raining=False, step_min=60):
    """
    CO₂ and travel time for every step_min departure slot across 24 hours.
    Returns list of dicts: minute, label, co2_g, time_min, tod_factor.
    """
    if vehicle_type in MODE_TO_VEHICLE:
        vehicle_type = MODE_TO_VEHICLE[vehicle_type]
    results = []
    for m in range(0, 24 * 60, step_min):
        co2 = estimate_co2_v2(distance_km, vehicle_type, temp_celsius, is_raining, m)
        t   = travel_time_minutes(distance_km, vehicle_type, m)
        tod = get_time_of_day_factor(m, vehicle_type)
        results.append({"minute": m, "label": fmt_time(m), "co2_g": co2, "time_min": t, "tod_factor": tod})
    return results


# ── Routing ───────────────────────────────────────────────────────────────────

def nearest_neighbor_route(locations):
    """Greedy nearest-neighbor TSP heuristic on (name, lat, lon) tuples."""
    if not locations:
        return []
    unvisited = list(locations)
    route     = [unvisited.pop(0)]
    while unvisited:
        last    = route[-1]
        nearest = min(unvisited, key=lambda loc: haversine(last[1], last[2], loc[1], loc[2]))
        route.append(nearest)
        unvisited.remove(nearest)
    return route


# ── Schedule & travel time ────────────────────────────────────────────────────

def travel_time_minutes(distance_km, vehicle_type="car_petrol", start_minute=540):
    """Travel time (min) with time-of-day traffic multiplier."""
    if vehicle_type in MODE_TO_VEHICLE:
        vehicle_type = MODE_TO_VEHICLE[vehicle_type]
    profile = EMISSION_PROFILES.get(vehicle_type, EMISSION_PROFILES["car_petrol"])
    speed   = profile["speed"]
    if speed <= 0:
        return 0
    return (distance_km / speed) * get_time_of_day_factor(start_minute, vehicle_type) * 60


def build_schedule(route, vehicle_type, start_time_minutes, durations_minutes,
                   leg_distances_km=None):
    """
    Build stop-by-stop schedule.
    leg_distances_km: optional list of real road distances per leg (from OSRM).
    Falls back to haversine when not provided.
    Each leg uses its actual departure time for rush-hour calculation.
    """
    if vehicle_type in MODE_TO_VEHICLE:
        vehicle_type = MODE_TO_VEHICLE[vehicle_type]

    schedule     = []
    current_time = float(start_time_minutes)

    for i, (name, lat, lon) in enumerate(route):
        if i == 0:
            travel, dist = 0.0, 0.0
        else:
            if leg_distances_km and (i - 1) < len(leg_distances_km):
                dist = leg_distances_km[i - 1]
            else:
                prev = route[i - 1]
                dist = haversine(prev[1], prev[2], lat, lon)
            travel = travel_time_minutes(dist, vehicle_type, current_time)

        arrive   = current_time + travel
        duration = durations_minutes[i] if i < len(durations_minutes) else 0
        depart   = arrive + duration
        current_time = depart

        schedule.append({
            "name":       name,
            "arrive_min": arrive,
            "depart_min": depart,
            "travel_min": travel,
            "dist_km":    dist,
        })

    return schedule


# ── Formatting ────────────────────────────────────────────────────────────────

def fmt_time(minutes_since_midnight):
    total = int(minutes_since_midnight) % (24 * 60)
    h, m  = divmod(total, 60)
    return f"{h:02d}:{m:02d}"


def fmt_duration(minutes):
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if m else f"{h} h"

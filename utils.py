"""
utils.py — Math and optimization logic for EcoRoute Optimizer
"""

import math


# ── Vehicle emission profiles ─────────────────────────────────────────────────
# Emission factors in g CO2 per km (DEFRA / EPA / EEA 2023 averages)

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

# Legacy mode string → vehicle type key
MODE_TO_VEHICLE = {
    "car": "car_petrol", "bus": "bus", "train": "train",
    "bike": "bike", "walk": "walk",
}

# Vehicles unaffected by road traffic conditions
_ROAD_FREE = {"train", "bike", "ebike", "walk"}


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
    """Total distance (km) for ordered list of (name, lat, lon) tuples."""
    total = 0.0
    for i in range(len(route) - 1):
        total += haversine(route[i][1], route[i][2], route[i + 1][1], route[i + 1][2])
    return total


# ── Time-of-day traffic factor ────────────────────────────────────────────────

def get_time_of_day_factor(start_minute, vehicle_type="car_petrol"):
    """
    Multiplier for travel time and fuel burn based on departure time.
    Values > 1.0 mean slower / more fuel.  Rail, cycling, walking unaffected.
    """
    if vehicle_type in _ROAD_FREE:
        return 1.0
    hour = (int(start_minute) // 60) % 24
    is_rush = (7 <= hour < 9) or (17 <= hour < 19)
    is_night = hour >= 22 or hour < 6
    if is_rush:
        return 1.35 if vehicle_type != "bus" else 1.20
    if is_night:
        return 0.80 if vehicle_type != "bus" else 0.90
    return 1.0


# ── Weather emission factor ───────────────────────────────────────────────────

def weather_emission_factor(temp_celsius, is_raining):
    """
    Coefficient capturing cold-start penalty and rain drag.
    Only applied to road vehicles with non-zero emission factors.
    """
    temp_f = 1.0
    if temp_celsius < 10:
        temp_f = 1.0 + (10 - temp_celsius) * 0.015   # 1.5 % per °C below 10
    elif temp_celsius > 35:
        temp_f = 1.0 + (temp_celsius - 35) * 0.005   # AC penalty above 35 °C
    rain_f = 1.08 if is_raining else 1.0
    return temp_f * rain_f


# ── CO₂ estimation ────────────────────────────────────────────────────────────

def estimate_co2(distance_km, mode="car"):
    """Legacy CO₂ estimate in grams — kept for backward compatibility."""
    factors = {"car": 120, "bus": 68, "train": 14, "bike": 0, "walk": 0}
    return distance_km * factors.get(mode, 120)


def estimate_co2_v2(distance_km, vehicle_type="car_petrol",
                    temp_celsius=20, is_raining=False, start_minute=540):
    """
    Enhanced CO₂ estimate (grams) incorporating:
    - Vehicle-specific emission profile (g/km)
    - Time-of-day traffic multiplier (rush hour → more fuel)
    - Weather effects (cold / rain → engine inefficiency)
    Trains are unaffected by both; buses by traffic only.
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

    # Cars, motorcycles, e-bikes: weather + time-of-day
    weather = weather_emission_factor(temp_celsius, is_raining)
    return distance_km * base * weather * tod


def eco_score(distance_km, vehicle_type="car_petrol",
              temp_celsius=20, is_raining=False, start_minute=540):
    """
    0–100 eco score: lower emissions → higher score.
    Baseline = 100 km petrol car (~12 000 g CO₂).
    """
    if vehicle_type in MODE_TO_VEHICLE:
        vehicle_type = MODE_TO_VEHICLE[vehicle_type]
    baseline = 12_000
    emissions = estimate_co2_v2(distance_km, vehicle_type, temp_celsius, is_raining, start_minute)
    return round(max(0.0, 100.0 - (emissions / baseline) * 100.0), 1)


# ── Multi-objective mode comparison ──────────────────────────────────────────

def multi_mode_comparison(distance_km, start_minute=540, temp_celsius=20, is_raining=False):
    """
    Compare all transport modes for the same straight-line distance.
    Returns list of dicts sorted by CO₂ ascending (greenest first).
    Each dict: type, label, icon, category, time_min, co2_g, eco_score, co2_per_km
    """
    results = []
    for vtype, profile in EMISSION_PROFILES.items():
        tod = get_time_of_day_factor(start_minute, vtype)
        time_min = (distance_km / profile["speed"]) * tod * 60 if profile["speed"] > 0 else 0
        co2 = estimate_co2_v2(distance_km, vtype, temp_celsius, is_raining, start_minute)
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
    """
    Convert CO₂ grams into relatable real-world equivalents.
    Returns dict with trees_days, phone_charges, car_km.
    """
    kg = co2_grams / 1000
    return {
        "trees_days":    round(kg / 0.022, 1),        # avg tree absorbs ~22 g CO₂/day
        "phone_charges": round(co2_grams / 8.22, 0),  # ~8.22 g per full smartphone charge
        "car_km":        round(kg * 1000 / 120, 1),   # equivalent km in avg petrol car
    }


def co2_savings(co2_grams, distance_km, temp_celsius=20, is_raining=False, start_minute=540):
    """Compute CO₂ saved vs petrol car baseline (grams and percent)."""
    baseline = estimate_co2_v2(distance_km, "car_petrol", temp_celsius, is_raining, start_minute)
    saved_g = max(0.0, baseline - co2_grams)
    saved_pct = (saved_g / baseline * 100) if baseline > 0 else 0
    return {"saved_g": saved_g, "saved_pct": round(saved_pct, 1), "baseline_g": baseline}


# ── Routing ───────────────────────────────────────────────────────────────────

def nearest_neighbor_route(locations):
    """Greedy nearest-neighbor TSP heuristic on (name, lat, lon) tuples."""
    if not locations:
        return []
    unvisited = list(locations)
    route = [unvisited.pop(0)]
    while unvisited:
        last = route[-1]
        nearest = min(unvisited, key=lambda loc: haversine(last[1], last[2], loc[1], loc[2]))
        route.append(nearest)
        unvisited.remove(nearest)
    return route


# ── Schedule & travel time ────────────────────────────────────────────────────

def travel_time_minutes(distance_km, vehicle_type="car_petrol", start_minute=540):
    """
    Travel time in minutes accounting for time-of-day traffic.
    Rush hour increases travel time proportionally.
    """
    if vehicle_type in MODE_TO_VEHICLE:
        vehicle_type = MODE_TO_VEHICLE[vehicle_type]
    profile = EMISSION_PROFILES.get(vehicle_type, EMISSION_PROFILES["car_petrol"])
    speed = profile["speed"]
    if speed <= 0:
        return 0
    tod = get_time_of_day_factor(start_minute, vehicle_type)
    return (distance_km / speed) * tod * 60


def build_schedule(route, vehicle_type, start_time_minutes, durations_minutes):
    """
    Build stop-by-stop schedule.

    route              : list of (name, lat, lon)
    vehicle_type       : key from EMISSION_PROFILES, or legacy mode string
    start_time_minutes : trip start as minutes since midnight
    durations_minutes  : list of int (time spent at each stop)

    Each leg uses its actual departure time for rush-hour calculation.
    Returns list of dicts: name, arrive_min, depart_min, travel_min, dist_km
    """
    if vehicle_type in MODE_TO_VEHICLE:
        vehicle_type = MODE_TO_VEHICLE[vehicle_type]

    schedule = []
    current_time = float(start_time_minutes)

    for i, (name, lat, lon) in enumerate(route):
        if i == 0:
            travel = 0.0
            dist   = 0.0
        else:
            prev   = route[i - 1]
            dist   = haversine(prev[1], prev[2], lat, lon)
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
    """Convert minutes-since-midnight float to HH:MM string."""
    total = int(minutes_since_midnight) % (24 * 60)
    h, m = divmod(total, 60)
    return f"{h:02d}:{m:02d}"


def fmt_duration(minutes):
    """Format a duration in minutes as e.g. '1 h 25 min' or '45 min'."""
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if m else f"{h} h"

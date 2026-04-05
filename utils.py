"""
utils.py — Math and optimization logic for EcoRoute Optimizer
"""

import math


def haversine(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two GPS coordinates (km)."""
    R = 6371  # Earth's radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def estimate_co2(distance_km, mode="car"):
    """
    Estimate CO2 emissions in grams for a given distance and transport mode.

    Emission factors (g CO2 per km):
      car    : ~120 g/km (average petrol car)
      bus    : ~68  g/km per passenger
      train  : ~14  g/km per passenger
      bike   : 0
      walk   : 0
    """
    factors = {
        "car": 120,
        "bus": 68,
        "train": 14,
        "bike": 0,
        "walk": 0,
    }
    return distance_km * factors.get(mode, 120)


def nearest_neighbor_route(locations):
    """
    Greedy nearest-neighbor heuristic to build a short route through a list of
    (name, lat, lon) tuples. Returns ordered list of locations.
    """
    if not locations:
        return []

    unvisited = list(locations)
    route = [unvisited.pop(0)]

    while unvisited:
        last = route[-1]
        nearest = min(
            unvisited,
            key=lambda loc: haversine(last[1], last[2], loc[1], loc[2])
        )
        route.append(nearest)
        unvisited.remove(nearest)

    return route


def route_total_distance(route):
    """Return total distance (km) for an ordered list of (name, lat, lon) tuples."""
    total = 0.0
    for i in range(len(route) - 1):
        total += haversine(route[i][1], route[i][2], route[i + 1][1], route[i + 1][2])
    return total


def eco_score(distance_km, mode="car"):
    """
    Simple 0–100 eco score: lower emissions → higher score.
    Baseline is driving 100 km by car (~12 000 g CO2).
    """
    baseline = 12000  # g
    emissions = estimate_co2(distance_km, mode)
    score = max(0, 100 - (emissions / baseline) * 100)
    return round(score, 1)


# Average speeds (km/h) per transport mode for travel time estimation
MODE_SPEED_KMH = {
    "car":   50,
    "bus":   25,
    "train": 70,
    "bike":  15,
    "walk":   5,
}


def travel_time_minutes(distance_km, mode="car"):
    """Estimated travel time in minutes for a given distance and mode."""
    speed = MODE_SPEED_KMH.get(mode, 50)
    return (distance_km / speed) * 60


def build_schedule(route, mode, start_time_minutes, durations_minutes):
    """
    Build a schedule for the route.

    route               : list of (name, lat, lon)
    mode                : transport mode string
    start_time_minutes  : trip start time as minutes since midnight
    durations_minutes   : list of int, one per stop (time spent at each location)

    Returns list of dicts:
      { name, arrive_min, depart_min, travel_min, dist_km }
    """
    schedule = []
    current_time = start_time_minutes

    for i, (name, lat, lon) in enumerate(route):
        if i == 0:
            travel = 0.0
            dist   = 0.0
        else:
            prev = route[i - 1]
            dist   = haversine(prev[1], prev[2], lat, lon)
            travel = travel_time_minutes(dist, mode)

        arrive = current_time + travel
        duration = durations_minutes[i] if i < len(durations_minutes) else 0
        depart = arrive + duration
        current_time = depart

        schedule.append({
            "name":       name,
            "arrive_min": arrive,
            "depart_min": depart,
            "travel_min": travel,
            "dist_km":    dist,
        })

    return schedule


def fmt_time(minutes_since_midnight):
    """Convert minutes-since-midnight float to HH:MM string."""
    total = int(minutes_since_midnight) % (24 * 60)
    h, m = divmod(total, 60)
    return f"{h:02d}:{m:02d}"


def fmt_duration(minutes):
    """Format a duration in minutes as e.g. '1 h 25 min'."""
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if m else f"{h} h"

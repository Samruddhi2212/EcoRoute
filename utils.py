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

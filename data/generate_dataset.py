"""
generate_dataset.py — Synthetic fuel consumption dataset for EcoRoute++

Generates realistic road-segment samples using physics-based fuel models.
Saves to data/fuel_dataset.json (no pandas dependency).

Run:  python data/generate_dataset.py
"""

import json
import math
import random
import os

# ── Road type encoding ────────────────────────────────────────────────────────
ROAD_TYPES = {
    "residential": 0,
    "arterial":    1,
    "highway":     2,
    "motorway":    3,
}

# ── Vehicle type encoding ─────────────────────────────────────────────────────
VEHICLE_TYPES = {
    "sedan": 0,
    "suv":   1,
    "ev":    2,
}

# Base fuel consumption (L/100 km) at 60 km/h, flat road, no traffic
_BASE_L_PER_100KM = {
    "sedan": 7.0,
    "suv":   10.5,
    "ev":    0.0,   # EVs use kWh; we model energy_kwh_per_100km separately
}

_EV_BASE_KWH_PER_100KM = 16.0   # Tesla Model 3 reference


def _speed_factor(speed_kmh: float) -> float:
    """
    U-shaped fuel curve: most efficient ~80 km/h, worse at low/high speeds.
    Fitted to EPA-style data.
    """
    opt = 80.0
    if speed_kmh <= 0:
        return 2.5
    deviation = abs(speed_kmh - opt) / opt
    return 1.0 + 0.8 * deviation ** 1.6


def _elevation_factor(elevation_gain_m: float, distance_km: float) -> float:
    """Extra fuel for climbing (descent recovers ~40% for ICE, ~70% for EV via regen)."""
    if distance_km <= 0:
        return 1.0
    grade_pct = (elevation_gain_m / (distance_km * 1000)) * 100
    return 1.0 + max(0.0, grade_pct) * 0.04


def _traffic_factor(traffic: float) -> float:
    """traffic ∈ [0.5, 2.5] — stop-and-go at high values burns ~30% more."""
    return 1.0 + max(0.0, traffic - 1.0) * 0.30


def _road_type_factor(road_type: str) -> float:
    return {"residential": 1.10, "arterial": 1.02, "highway": 0.95, "motorway": 0.90}[road_type]


def compute_fuel_consumption(
    distance_km: float,
    speed_kmh: float,
    elevation_gain_m: float,
    elevation_loss_m: float,
    traffic: float,
    road_type: str,
    vehicle_type: str,
    noise_std: float = 0.05,
) -> dict:
    """
    Physics-based fuel consumption with added Gaussian noise.

    Returns dict with:
      fuel_liters     — petrol/diesel consumed (0 for EV)
      energy_kwh      — electricity consumed (0 for ICE)
      co2_grams       — CO₂ emitted
      travel_time_min — travel time with traffic
    """
    sf  = _speed_factor(speed_kmh)
    ef  = _elevation_factor(elevation_gain_m, distance_km)
    tf  = _traffic_factor(traffic)
    rf  = _road_type_factor(road_type)

    noise = 1.0 + random.gauss(0, noise_std)
    noise = max(0.85, min(1.20, noise))

    if vehicle_type == "ev":
        base_kwh = _EV_BASE_KWH_PER_100KM
        # EVs recover energy on descent
        regen_factor = 1.0 - max(0.0, elevation_loss_m / (distance_km * 1000 + 1e-9)) * 0.007
        energy_kwh = (distance_km / 100) * base_kwh * sf * ef * regen_factor * tf * rf * noise
        # UK grid average 233 g CO₂/kWh
        co2_g = energy_kwh * 233.0
        fuel_l = 0.0
    else:
        base = _BASE_L_PER_100KM[vehicle_type]
        fuel_l = (distance_km / 100) * base * sf * ef * tf * rf * noise
        # Petrol ≈ 2.31 kg CO₂/L, Diesel ≈ 2.68 (treating both as petrol here)
        co2_g = fuel_l * 2310.0
        energy_kwh = 0.0

    # Travel time: nominal speed reduced by traffic factor
    effective_speed = speed_kmh / tf if tf > 0 else speed_kmh
    travel_min = (distance_km / max(effective_speed, 1.0)) * 60.0

    return {
        "fuel_liters":      round(fuel_l, 4),
        "energy_kwh":       round(energy_kwh, 4),
        "co2_grams":        round(co2_g, 2),
        "travel_time_min":  round(travel_min, 3),
    }


def generate_dataset(n_samples: int = 6000, seed: int = 42) -> list[dict]:
    """
    Generate n_samples synthetic road-segment records.

    Feature columns (also stored in each record):
      distance_km, speed_kmh, elevation_gain_m, elevation_loss_m,
      traffic_factor, road_type_enc, vehicle_type_enc

    Target columns:
      fuel_liters, energy_kwh, co2_grams, travel_time_min
    """
    random.seed(seed)
    samples = []

    road_type_list    = list(ROAD_TYPES.keys())
    vehicle_type_list = list(VEHICLE_TYPES.keys())

    # Realistic speed ranges per road type
    speed_ranges = {
        "residential": (15, 50),
        "arterial":    (30, 70),
        "highway":     (60, 100),
        "motorway":    (90, 130),
    }

    for _ in range(n_samples):
        road_type    = random.choice(road_type_list)
        vehicle_type = random.choice(vehicle_type_list)

        distance_km      = round(random.uniform(0.1, 25.0), 3)
        sp_lo, sp_hi     = speed_ranges[road_type]
        speed_kmh        = round(random.uniform(sp_lo, sp_hi), 1)
        elevation_gain_m = round(random.uniform(0, 120), 1)
        elevation_loss_m = round(random.uniform(0, 120), 1)
        traffic_factor   = round(random.uniform(0.7, 2.2), 2)

        results = compute_fuel_consumption(
            distance_km, speed_kmh, elevation_gain_m, elevation_loss_m,
            traffic_factor, road_type, vehicle_type,
        )

        samples.append({
            # Features
            "distance_km":       distance_km,
            "speed_kmh":         speed_kmh,
            "elevation_gain_m":  elevation_gain_m,
            "elevation_loss_m":  elevation_loss_m,
            "traffic_factor":    traffic_factor,
            "road_type":         road_type,
            "road_type_enc":     ROAD_TYPES[road_type],
            "vehicle_type":      vehicle_type,
            "vehicle_type_enc":  VEHICLE_TYPES[vehicle_type],
            # Targets
            "fuel_liters":       results["fuel_liters"],
            "energy_kwh":        results["energy_kwh"],
            "co2_grams":         results["co2_grams"],
            "travel_time_min":   results["travel_time_min"],
        })

    return samples


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "fuel_dataset.json")

    print("Generating dataset…")
    data = generate_dataset(n_samples=6000)

    with open(out_path, "w") as f:
        json.dump(data, f, indent=None, separators=(",", ":"))

    print(f"Saved {len(data)} samples → {out_path}")

    # Quick sanity stats (no pandas)
    fuels   = [d["fuel_liters"] for d in data if d["vehicle_type"] != "ev"]
    kwhs    = [d["energy_kwh"]  for d in data if d["vehicle_type"] == "ev"]
    co2s    = [d["co2_grams"]   for d in data]
    avg_f   = sum(fuels) / len(fuels) if fuels else 0
    avg_kwh = sum(kwhs)  / len(kwhs)  if kwhs  else 0
    avg_co2 = sum(co2s)  / len(co2s)  if co2s  else 0

    print(f"ICE avg fuel  : {avg_f:.3f} L/segment")
    print(f"EV  avg energy: {avg_kwh:.3f} kWh/segment")
    print(f"Avg CO₂       : {avg_co2:.1f} g/segment")
    print(f"Vehicles      : {set(d['vehicle_type'] for d in data)}")
    print(f"Road types    : {set(d['road_type'] for d in data)}")


if __name__ == "__main__":
    main()

"""
fuel_model.py — Fuel & energy consumption ML models for EcoRoute++

Two models:
  1. LinearRegression  (baseline)
  2. GradientBoostingRegressor  (advanced)

Both trained on the synthetic dataset in data/fuel_dataset.json.
Includes feature importance analysis and RMSE/MAE evaluation.

Run:  python models/fuel_model.py
"""

import json
import math
import os
import pickle
import sys
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE       = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR   = os.path.join(_HERE, "..", "data")
_SAVED_DIR  = os.path.join(_HERE, "saved")
os.makedirs(_SAVED_DIR, exist_ok=True)

DATASET_PATH = os.path.join(_DATA_DIR,  "fuel_dataset.json")

# ── Feature configuration ─────────────────────────────────────────────────────
FEATURE_NAMES = [
    "distance_km",
    "speed_kmh",
    "elevation_gain_m",
    "elevation_loss_m",
    "traffic_factor",
    "road_type_enc",
    "vehicle_type_enc",
]

# Two separate targets (ICE and EV)
TARGET_FUEL   = "fuel_liters"
TARGET_ENERGY = "energy_kwh"

# Unified target: CO₂ (works for both ICE and EV)
TARGET_CO2 = "co2_grams"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_dataset(path: str = DATASET_PATH) -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset not found at {path}\n"
            "Run:  python data/generate_dataset.py"
        )
    with open(path) as f:
        return json.load(f)


def dataset_to_arrays(
    records: list[dict],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns X, y_fuel, y_energy, y_co2 as numpy arrays.
    Records for EVs have fuel_liters=0; ICE records have energy_kwh=0.
    """
    X        = np.array([[r[fn] for fn in FEATURE_NAMES] for r in records], dtype=np.float64)
    y_fuel   = np.array([r[TARGET_FUEL]   for r in records], dtype=np.float64)
    y_energy = np.array([r[TARGET_ENERGY] for r in records], dtype=np.float64)
    y_co2    = np.array([r[TARGET_CO2]    for r in records], dtype=np.float64)
    return X, y_fuel, y_energy, y_co2


# ── Training ──────────────────────────────────────────────────────────────────

def train_co2_models(
    X_train: np.ndarray,
    y_train: np.ndarray,
) -> tuple[Any, Any, StandardScaler]:
    """
    Train LinearRegression + GradientBoostingRegressor on CO₂ target.

    Returns (lr_model, gb_model, scaler).
    """
    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)

    lr = LinearRegression()
    lr.fit(X_scaled, y_train)

    gb = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        min_samples_leaf=5,
        random_state=42,
    )
    gb.fit(X_train, y_train)   # GB doesn't need scaling

    return lr, gb, scaler


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_model(
    model: Any,
    X_test: np.ndarray,
    y_test: np.ndarray,
    name: str,
    scaler: StandardScaler | None = None,
) -> dict:
    X_in = scaler.transform(X_test) if scaler else X_test
    y_pred = model.predict(X_in)
    rmse = root_mean_squared_error(y_test, y_pred)
    mae  = mean_absolute_error(y_test, y_pred)
    # R²
    ss_res = np.sum((y_test - y_pred) ** 2)
    ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {"model": name, "rmse": round(rmse, 3), "mae": round(mae, 3), "r2": round(r2, 4)}


def feature_importance_lr(model: LinearRegression, scaler: StandardScaler) -> list[dict]:
    """Scale-aware feature importances from LR coefficients."""
    coef = model.coef_
    # Undo standardization: importance ∝ |coef × std|
    importances = np.abs(coef * scaler.scale_)
    importances /= importances.sum() + 1e-12
    return sorted(
        [{"feature": fn, "importance": round(float(imp), 4)}
         for fn, imp in zip(FEATURE_NAMES, importances)],
        key=lambda d: d["importance"], reverse=True,
    )


def feature_importance_gb(model: GradientBoostingRegressor) -> list[dict]:
    importances = model.feature_importances_
    return sorted(
        [{"feature": fn, "importance": round(float(imp), 4)}
         for fn, imp in zip(FEATURE_NAMES, importances)],
        key=lambda d: d["importance"], reverse=True,
    )


# ── Save / load ───────────────────────────────────────────────────────────────

def save_models(lr, gb, scaler, metrics: list[dict], importances: dict) -> None:
    for name, obj in [("lr.pkl", lr), ("gb.pkl", gb), ("scaler.pkl", scaler)]:
        with open(os.path.join(_SAVED_DIR, name), "wb") as f:
            pickle.dump(obj, f)
    meta = {"metrics": metrics, "feature_names": FEATURE_NAMES, "importances": importances}
    with open(os.path.join(_SAVED_DIR, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Models saved to {_SAVED_DIR}/")


def load_models() -> tuple[Any, Any, StandardScaler, dict]:
    """Return (lr, gb, scaler, meta). Raises FileNotFoundError if not trained."""
    paths = {n: os.path.join(_SAVED_DIR, n) for n in ["lr.pkl", "gb.pkl", "scaler.pkl", "meta.json"]}
    for p in paths.values():
        if not os.path.exists(p):
            raise FileNotFoundError(f"Model file missing: {p}\nRun: python models/fuel_model.py")
    with open(paths["lr.pkl"],     "rb") as f: lr     = pickle.load(f)
    with open(paths["gb.pkl"],     "rb") as f: gb     = pickle.load(f)
    with open(paths["scaler.pkl"], "rb") as f: scaler = pickle.load(f)
    with open(paths["meta.json"])       as f: meta   = json.load(f)
    return lr, gb, scaler, meta


# ── Inference ─────────────────────────────────────────────────────────────────

def predict_co2(
    distance_km: float,
    speed_kmh: float,
    elevation_gain_m: float,
    elevation_loss_m: float,
    traffic_factor: float,
    road_type_enc: int,
    vehicle_type_enc: int,
    model: str = "gb",
) -> dict:
    """
    Predict CO₂ for a single road segment.

    model: "lr" | "gb"
    Returns {"co2_grams": float, "model": str, "features": dict}
    """
    lr, gb, scaler, _ = load_models()
    x = np.array([[distance_km, speed_kmh, elevation_gain_m, elevation_loss_m,
                   traffic_factor, road_type_enc, vehicle_type_enc]])
    if model == "lr":
        pred = float(lr.predict(scaler.transform(x))[0])
    else:
        pred = float(gb.predict(x)[0])
    pred = max(0.0, pred)
    return {
        "co2_grams": round(pred, 2),
        "model": model,
        "features": dict(zip(FEATURE_NAMES, x[0].tolist())),
    }


# ── Main: train + evaluate ────────────────────────────────────────────────────

def main() -> None:
    print("Loading dataset…")
    records = load_dataset()
    print(f"  {len(records)} records loaded")

    X, _, _, y_co2 = dataset_to_arrays(records)

    X_tr, X_te, y_tr, y_te = train_test_split(X, y_co2, test_size=0.2, random_state=42)

    print("\nTraining models…")
    lr, gb, scaler = train_co2_models(X_tr, y_tr)

    print("\n── Evaluation (test set, CO₂ target) ──")
    metrics = []
    for name, mdl, sc in [("LinearRegression", lr, scaler), ("GradientBoosting", gb, None)]:
        res = evaluate_model(mdl, X_te, y_te, name, sc)
        metrics.append(res)
        print(f"  {name:<24}  RMSE={res['rmse']:.2f} g   MAE={res['mae']:.2f} g   R²={res['r2']:.4f}")

    # Cross-validation for LR
    cv_scores = cross_val_score(
        LinearRegression(), scaler.transform(X), y_co2,
        cv=5, scoring="neg_root_mean_squared_error",
    )
    print(f"\n  LR  5-fold CV RMSE : {-cv_scores.mean():.2f} ± {cv_scores.std():.2f} g")

    print("\n── Feature Importances ──")
    lr_imp = feature_importance_lr(lr, scaler)
    gb_imp = feature_importance_gb(gb)

    print("\n  LinearRegression (scaled coeff magnitude):")
    for d in lr_imp:
        bar = "█" * int(d["importance"] * 40)
        print(f"    {d['feature']:<22}  {d['importance']:.4f}  {bar}")

    print("\n  GradientBoosting (split gain):")
    for d in gb_imp:
        bar = "█" * int(d["importance"] * 40)
        print(f"    {d['feature']:<22}  {d['importance']:.4f}  {bar}")

    importances = {"lr": lr_imp, "gb": gb_imp}
    save_models(lr, gb, scaler, metrics, importances)

    # Quick prediction smoke test
    sample = records[0]
    result = predict_co2(
        sample["distance_km"], sample["speed_kmh"],
        sample["elevation_gain_m"], sample["elevation_loss_m"],
        sample["traffic_factor"], sample["road_type_enc"], sample["vehicle_type_enc"],
    )
    print(f"\nSmoke test: predicted CO₂ = {result['co2_grams']} g  (actual = {sample['co2_grams']} g)")


if __name__ == "__main__":
    main()

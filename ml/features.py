"""Feature builder shared by training (ml/) and serving (backend/).

One row = one panchayat on one day. The model sees:
  * static terrain of the village (from data/terrain.csv),
  * where the village sits relative to the block centroid,
  * the season (day-of-year as sin/cos so 31 Dec and 1 Jan are neighbours),
  * the coarse block forecast for that day (all five variables = weather context).

Keeping this in one function guarantees the live API builds exactly the same
features the models were trained on.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# Variable key -> (Open-Meteo daily field, unit, short label)
VARIABLES = {
    "tmax":  ("temperature_2m_max",        "°C",   "max temperature"),
    "tmin":  ("temperature_2m_min",        "°C",   "min temperature"),
    "rain":  ("precipitation_sum",         "mm",   "rainfall"),
    "rh":    ("relative_humidity_2m_mean", "%",    "humidity"),
    "wind":  ("wind_speed_10m_max",        "km/h", "max wind"),
}
FIELD_TO_VAR = {field: v for v, (field, _, _) in VARIABLES.items()}

TERRAIN_FEATURES = [
    "elevation_m", "elev_diff_m", "slope_deg", "aspect_sin", "aspect_cos",
    "tpi_m", "dist_river_km", "dx_km", "dy_km",
]
SEASON_FEATURES = ["doy_sin", "doy_cos"]
BLOCK_FEATURES = [f"block_{v}" for v in VARIABLES]
FEATURES = TERRAIN_FEATURES + SEASON_FEATURES + BLOCK_FEATURES

# Plain-language names used in SHAP sentences.
FEATURE_LABELS = {
    "elevation_m": "elevation",
    "elev_diff_m": "height vs block centre",
    "slope_deg": "slope",
    "aspect_sin": "slope direction (E/W)",
    "aspect_cos": "slope direction (N/S)",
    "tpi_m": "local hill/hollow position",
    "dist_river_km": "distance to Krishna river",
    "dx_km": "east-west position",
    "dy_km": "north-south position",
    "doy_sin": "season",
    "doy_cos": "season",
    "block_tmax": "block max temperature",
    "block_tmin": "block min temperature",
    "block_rain": "block rainfall",
    "block_rh": "block humidity",
    "block_wind": "block wind",
}


def load_block_meta() -> dict:
    return json.loads((DATA / "manifest.json").read_text())["block"]


def load_terrain() -> pd.DataFrame:
    """Static per-village features, indexed by panchayat id."""
    t = pd.read_csv(DATA / "terrain.csv").set_index("id")
    block_elev = load_block_meta()["elevation_m"]
    out = pd.DataFrame(index=t.index)
    out["elevation_m"] = t.elevation_m
    out["elev_diff_m"] = t.elevation_m - block_elev
    out["slope_deg"] = t.slope_deg
    # Aspect is circular (359 deg is next to 1 deg), so encode as sin/cos.
    # A flat cell has no aspect -> (0, 0), i.e. "no direction".
    rad = np.radians(t.aspect_deg)
    out["aspect_sin"] = np.sin(rad).fillna(0.0)
    out["aspect_cos"] = np.cos(rad).fillna(0.0)
    out["tpi_m"] = t.tpi_m
    out["dist_river_km"] = t.dist_river_km
    out["dx_km"] = t.dx_km
    out["dy_km"] = t.dy_km
    return out


def season_features(dates: pd.Series) -> pd.DataFrame:
    doy = pd.to_datetime(dates).dt.dayofyear.to_numpy()
    angle = 2 * np.pi * (doy - 1) / 365.25
    return pd.DataFrame({"doy_sin": np.sin(angle), "doy_cos": np.cos(angle)}, index=dates.index)


def build_features(ids: pd.Series, dates: pd.Series, block: pd.DataFrame,
                   terrain: pd.DataFrame | None = None) -> pd.DataFrame:
    """Feature matrix for (panchayat id, date) pairs.

    ids, dates : aligned Series (one entry per row)
    block      : DataFrame aligned with ids/dates, columns block_tmax ... block_wind
    """
    terrain = load_terrain() if terrain is None else terrain
    missing = set(ids) - set(terrain.index)
    if missing:
        raise KeyError(f"No terrain for panchayats: {sorted(missing)[:5]}")
    X = terrain.loc[ids.to_numpy()].reset_index(drop=True)
    X.index = ids.index
    X = X.join(season_features(dates)).join(block[BLOCK_FEATURES])
    return X[FEATURES]

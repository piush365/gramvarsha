"""Physics-only terrain correction (fallback Tier B, and a baseline on /validation).

No training data needed -- just textbook meteorology:
  * Temperature falls ~6.5 °C per km of height (standard environmental lapse rate).
  * Rain increases on higher ground (orographic lift). The coefficient below is a
    deliberately modest literature-style assumption (+4 % per 100 m), NOT fitted.
  * Humidity and wind are passed through unchanged (no simple physical rule).
"""
from __future__ import annotations

import numpy as np

LAPSE_RATE_C_PER_KM = 6.5
OROGRAPHIC_RAIN_FRAC_PER_100M = 0.04


def lapse_rate_correction(temp_c: float, from_elev_m: float, to_elev_m: float,
                          lapse_c_per_km: float = LAPSE_RATE_C_PER_KM) -> float:
    """Move a temperature from one elevation to another. Higher -> cooler."""
    return temp_c - lapse_c_per_km * (to_elev_m - from_elev_m) / 1000.0


def orographic_rain(rain_mm: float, from_elev_m: float, to_elev_m: float,
                    frac_per_100m: float = OROGRAPHIC_RAIN_FRAC_PER_100M) -> float:
    """Scale rainfall by height difference; never negative, never below 50 % of input.

    Accepts scalars or numpy arrays.
    """
    factor = 1.0 + frac_per_100m * (np.asarray(to_elev_m) - from_elev_m) / 100.0
    return np.maximum(0.0, np.asarray(rain_mm) * np.maximum(factor, 0.5))


def physics_downscale(block: dict, from_elev_m: float, to_elev_m: float) -> dict:
    """Apply the physics rules to a dict of block values {tmax, tmin, rain, rh, wind}.

    Works on scalars or numpy/pandas arrays.
    """
    return {
        "tmax": lapse_rate_correction(block["tmax"], from_elev_m, to_elev_m),
        "tmin": lapse_rate_correction(block["tmin"], from_elev_m, to_elev_m),
        "rain": orographic_rain(block["rain"], from_elev_m, to_elev_m),
        "rh": block["rh"],
        "wind": block["wind"],
    }

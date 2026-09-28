"""Turn a panchayat's correction into plain sentences (SHAP -> words).

The total change vs the block value is split into:
  * the block's usual bias this month (same for every village),
  * the kriged local pattern -- how this spot usually differs from the taluka average,
  * the XGBoost part -- split further by TreeSHAP into per-feature contributions.

Contributions are then grouped honestly into two kinds:
  * LOCAL    -- terrain/position features: why THIS village differs from its neighbours;
  * BLOCK-WIDE -- season and today's block weather: a correction of the coarse forecast
                that applies to every village alike (evaluation shows most of the
                max-temperature and rainfall gain is of this kind).

Rainfall is modelled on the log1p scale; its contributions are rescaled so they add
up to the actual mm change (proportional attribution -- stated in the output).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features import FEATURE_LABELS, TERRAIN_FEATURES, VARIABLES

# Features that are two halves of one idea are reported together.
GROUPS = {"doy_sin": "season", "doy_cos": "season", "aspect_sin": "slope direction", "aspect_cos": "slope direction"}
KRIGING_LABEL = "usual local pattern this month (kriging)"
BIAS_LABEL = "coarse forecast's usual bias this month"
LOCAL = set(TERRAIN_FEATURES) | {KRIGING_LABEL, "slope direction"}


def _label(feature: str) -> str:
    return GROUPS.get(feature, FEATURE_LABELS.get(feature, feature))


def explain(var: str, block_value: float, final_value: float, kriged_res: float,
            shap_row: pd.Series, month_bias: float = 0.0, top_n: int = 3) -> dict:
    """Explanation for one panchayat, one variable, one day.

    kriged_res : kriged residual at this village (working scale)
    month_bias : taluka-wide mean residual for this month (the part of kriged_res
                 that is the same everywhere, i.e. plain bias correction)

    shap_row : TreeSHAP contributions for this row (feature -> value, plus 'bias'),
               on the model's working scale (log1p for rain).
    Returns {delta, unit, parts:[{label, value, kind}], sentence, note}.
    """
    unit = VARIABLES[var][1]
    delta = float(final_value - block_value)

    # Contributions on the working scale; the XGBoost 'bias' (expected value) is a
    # constant offset learned over all training rows -> block-wide by nature.
    parts: dict[str, float] = {BIAS_LABEL: float(month_bias), KRIGING_LABEL: float(kriged_res - month_bias)}
    for feat, val in shap_row.items():
        key = "overall model offset" if feat == "bias" else _label(feat)
        parts[key] = parts.get(key, 0.0) + float(val)

    note = None
    if var == "rain":
        total = sum(parts.values())
        scale = delta / total if abs(total) > 1e-9 else 0.0
        parts = {k: v * scale for k, v in parts.items()}
        note = "Rain is modelled on a log scale; contributions are shown in proportion to the mm change."

    ranked = sorted(parts.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top = [{"label": k, "value": round(v, 2), "kind": "local" if k in LOCAL else "block-wide"}
           for k, v in ranked[:top_n] if abs(v) >= 0.005]

    fmt = (lambda x: f"{x:+.1f}") if unit != "%" else (lambda x: f"{x:+.0f}")
    reasons = ", ".join(f"{p['label']} ({fmt(p['value'])})" for p in top)
    sentence = f"{fmt(delta)} {unit} vs block" + (f": {reasons}" if reasons else "")
    return {"delta": round(delta, 2), "unit": unit, "parts": top, "sentence": sentence, "note": note}


def local_share(parts: list[dict]) -> float:
    """Fraction of the explained change that is village-specific (0..1)."""
    tot = sum(abs(p["value"]) for p in parts)
    return float(np.round(sum(abs(p["value"]) for p in parts if p["kind"] == "local") / tot, 2)) if tot else 0.0

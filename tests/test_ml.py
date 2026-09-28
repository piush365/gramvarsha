"""Feature builder, physics fallback, residual maths and SHAP-sentence tests."""
import math

import numpy as np
import pandas as pd
import pytest

from ml.explain import KRIGING_LABEL, explain
from ml.features import BLOCK_FEATURES, FEATURES, build_features, season_features
from ml.kriging import apply_residual, residual
from ml.physics import lapse_rate_correction, orographic_rain, physics_downscale


@pytest.fixture
def terrain():
    return pd.DataFrame({
        "elevation_m": [600.0, 550.0], "elev_diff_m": [7.0, -43.0], "slope_deg": [1.0, 0.5],
        "aspect_sin": [1.0, 0.0], "aspect_cos": [0.0, 0.0], "tpi_m": [2.0, -1.0],
        "dist_river_km": [5.0, 0.3], "dx_km": [1.0, -20.0], "dy_km": [2.0, 3.0],
    }, index=["hill", "riverside"])


def block_rows(n):
    return pd.DataFrame({c: np.arange(n, dtype=float) + i for i, c in enumerate(BLOCK_FEATURES)})


# ---- feature builder -------------------------------------------------------
def test_features_columns_and_order(terrain):
    ids = pd.Series(["riverside", "hill", "hill"])
    dates = pd.Series(["2025-01-01", "2025-07-01", "2025-12-31"])
    X = build_features(ids, dates, block_rows(3), terrain)
    assert list(X.columns) == FEATURES
    assert X.loc[0, "dist_river_km"] == 0.3 and X.loc[1, "elevation_m"] == 600.0
    assert X.loc[2, "block_tmax"] == 2.0          # block values stay aligned to their row
    assert not X.isna().any().any()


def test_features_unknown_panchayat_raises(terrain):
    with pytest.raises(KeyError):
        build_features(pd.Series(["nowhere"]), pd.Series(["2025-01-01"]), block_rows(1), terrain)


def test_season_is_circular():
    s = season_features(pd.Series(["2025-01-01", "2025-12-31", "2025-07-02"]))
    jan, dec, jul = s.to_numpy()
    assert np.linalg.norm(jan - dec) < 0.05        # year end wraps round to year start
    assert np.linalg.norm(jan - jul) > 1.9         # mid-year is on the far side


# ---- physics fallback ------------------------------------------------------
def test_lapse_rate_cools_with_height():
    assert math.isclose(lapse_rate_correction(30.0, 500, 1500), 23.5)
    assert math.isclose(lapse_rate_correction(30.0, 600, 500), 30.65)
    assert lapse_rate_correction(30.0, 572, 572) == 30.0


def test_orographic_rain_bounds():
    assert math.isclose(float(orographic_rain(10.0, 500, 600)), 10.4)
    assert float(orographic_rain(0.0, 500, 900)) == 0.0
    assert float(orographic_rain(10.0, 2000, 0)) == 5.0          # floored at 50 %


def test_physics_leaves_rh_and_wind_alone():
    out = physics_downscale({"tmax": 33, "tmin": 22, "rain": 4, "rh": 70, "wind": 12}, 572, 650)
    assert out["rh"] == 70 and out["wind"] == 12 and out["tmax"] < 33


# ---- residual maths --------------------------------------------------------
@pytest.mark.parametrize("var", ["tmax", "rain"])
def test_residual_roundtrip(var):
    truth, block = np.array([0.0, 3.0, 25.0]), np.array([1.0, 0.0, 10.0])
    assert np.allclose(apply_residual(var, block, residual(var, truth, block)), truth)


def test_rain_never_negative():
    assert (apply_residual("rain", np.array([0.5]), np.array([-5.0])) >= 0).all()


# ---- SHAP -> sentence ------------------------------------------------------
def test_explain_sentence_and_kinds():
    shap_row = pd.Series({"elevation_m": -0.5, "block_rh": 0.9, "doy_sin": 0.1, "doy_cos": 0.1, "bias": 0.0})
    e = explain("tmax", 30.0, 31.0, kriged_res=0.4, shap_row=shap_row)
    assert e["delta"] == 1.0 and e["unit"] == "°C"
    labels = [p["label"] for p in e["parts"]]
    assert labels[0] == "block humidity"                     # largest |contribution| first
    assert "season" in labels or KRIGING_LABEL in labels     # doy sin+cos merged into one "season"
    kinds = {p["label"]: p["kind"] for p in e["parts"]}
    assert kinds["block humidity"] == "block-wide"
    assert e["sentence"].startswith("+1.0 °C vs block")


def test_explain_splits_bias_from_local_pattern():
    e = explain("wind", 20.0, 11.0, kriged_res=-9.0, shap_row=pd.Series({"bias": 0.0}), month_bias=-8.5)
    parts = {p["label"]: p for p in e["parts"]}
    assert parts["coarse forecast's usual bias this month"]["value"] == -8.5
    assert parts["coarse forecast's usual bias this month"]["kind"] == "block-wide"
    assert parts[KRIGING_LABEL]["value"] == -0.5 and parts[KRIGING_LABEL]["kind"] == "local"


def test_explain_rain_parts_sum_to_mm_change():
    shap_row = pd.Series({"dist_river_km": 0.2, "block_rain": 0.3, "bias": 0.0})
    e = explain("rain", 4.0, 6.0, kriged_res=0.1, shap_row=shap_row, month_bias=0.05, top_n=10)
    assert math.isclose(sum(p["value"] for p in e["parts"]), 2.0, abs_tol=0.02)
    assert e["note"]

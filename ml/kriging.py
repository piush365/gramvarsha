"""Ordinary Kriging of the block-vs-village residual.

What is kriged
--------------
residual = village truth - block value. On a FUTURE day nobody knows the truth, so we
cannot krige that day's residuals. Instead we krige each village's AVERAGE residual
for the calendar month, computed over the TRAINING period only. The result is a
smooth "how does this spot usually differ from the block in this month" surface,
which can be read off at any location, including villages with no data.

Coordinates are km east/north of the block centroid (dx_km, dy_km), so distances
are real kilometres, not degrees.

For rainfall the residual is taken on the log1p scale (rain is skewed), consistent
with the XGBoost step.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from pykrige.ok import OrdinaryKriging

VARIOGRAMS = ("spherical", "exponential")


def residual(var: str, truth, block):
    """Residual on the scale the model works in (log1p for rain)."""
    if var == "rain":
        return np.log1p(np.maximum(truth, 0)) - np.log1p(np.maximum(block, 0))
    return truth - block


def apply_residual(var: str, block, res):
    """Inverse of `residual`: block value + residual -> value in real units."""
    if var == "rain":
        return np.maximum(np.expm1(np.log1p(np.maximum(block, 0)) + res), 0.0)
    return block + res


def monthly_mean_residuals(train: pd.DataFrame, var: str) -> pd.DataFrame:
    """Table (village id x month 1..12) of mean residual over the training rows."""
    r = residual(var, train[f"truth_{var}"].to_numpy(), train[f"block_{var}"].to_numpy())
    month = pd.to_datetime(train.date).dt.month
    return pd.DataFrame({"id": train.id.to_numpy(), "month": month.to_numpy(), "r": r}) \
        .groupby(["id", "month"]).r.mean().unstack("month")


def _fit(x, y, z, variogram: str) -> OrdinaryKriging | None:
    """Fit OK; returns None when the field is (near) constant and kriging is pointless."""
    if np.nanstd(z) < 1e-9:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return OrdinaryKriging(x, y, z, variogram_model=variogram, verbose=False, enable_plotting=False)


def _predict(ok: OrdinaryKriging | None, z_mean: float, x, y) -> np.ndarray:
    if ok is None:
        return np.full(len(x), z_mean)
    pred, _ = ok.execute("points", np.asarray(x, float), np.asarray(y, float))
    return np.asarray(pred)


def loo_rmse(x, y, z, variogram: str) -> float:
    """Leave-one-village-out RMSE: krige each village from all the others."""
    errs = []
    for i in range(len(z)):
        m = np.arange(len(z)) != i
        ok = _fit(x[m], y[m], z[m], variogram)
        errs.append(_predict(ok, z[m].mean(), x[i:i + 1], y[i:i + 1])[0] - z[i])
    return float(np.sqrt(np.mean(np.square(errs))))


class ResidualField:
    """Kriged monthly residual surface for one variable.

    Stores the village coordinates and their monthly mean residuals, so it can be
    saved as JSON and re-kriged at any point at serving time.
    """

    def __init__(self, var: str, variogram: str, coords: pd.DataFrame, table: pd.DataFrame):
        self.var = var
        self.variogram = variogram
        self.coords = coords                    # index id -> dx_km, dy_km
        self.table = table                      # index id, columns months 1..12
        self._models: dict[int, OrdinaryKriging | None] = {}

    @classmethod
    def fit(cls, train: pd.DataFrame, terrain: pd.DataFrame, var: str, variogram: str | None = None):
        """Build from training rows. If variogram is None, pick the one with the lower
        leave-one-village-out error (uses training data only)."""
        table = monthly_mean_residuals(train, var)
        coords = terrain.loc[table.index, ["dx_km", "dy_km"]]
        cv = {}
        if variogram is None:
            x, y = coords.dx_km.to_numpy(), coords.dy_km.to_numpy()
            for vg in VARIOGRAMS:
                cv[vg] = float(np.mean([loo_rmse(x, y, table[m].to_numpy(), vg) for m in table.columns]))
            variogram = min(cv, key=cv.get)
        field = cls(var, variogram, coords, table)
        field.cv_rmse = cv
        return field

    def _model(self, month: int):
        if month not in self._models:
            z = self.table[month].to_numpy()
            self._models[month] = _fit(self.coords.dx_km.to_numpy(), self.coords.dy_km.to_numpy(), z, self.variogram)
        return self._models[month]

    def predict(self, dx_km, dy_km, months) -> np.ndarray:
        """Kriged residual at each (dx, dy, month)."""
        dx, dy, months = np.asarray(dx_km, float), np.asarray(dy_km, float), np.asarray(months)
        out = np.empty(len(dx))
        for m in np.unique(months):
            sel = months == m
            out[sel] = _predict(self._model(int(m)), float(self.table[m].mean()), dx[sel], dy[sel])
        return out

    # --- persistence --------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "var": self.var,
            "variogram": self.variogram,
            "cv_rmse": getattr(self, "cv_rmse", {}),
            "points": {
                pid: {"dx_km": float(self.coords.loc[pid, "dx_km"]), "dy_km": float(self.coords.loc[pid, "dy_km"]),
                      "monthly": [float(self.table.loc[pid, m]) for m in range(1, 13)]}
                for pid in self.table.index
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ResidualField":
        ids = list(d["points"])
        coords = pd.DataFrame({k: [d["points"][i][k] for i in ids] for k in ("dx_km", "dy_km")}, index=ids)
        table = pd.DataFrame([d["points"][i]["monthly"] for i in ids], index=ids, columns=range(1, 13))
        f = cls(d["var"], d["variogram"], coords, table)
        f.cv_rmse = d.get("cv_rmse", {})
        return f

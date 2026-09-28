"""The GramVarsha downscaler: block value -> kriged residual -> XGBoost residual.

    prediction = block  (+)  kriged monthly residual  (+)  XGBoost correction

"(+)" is plain addition for temperature/humidity/wind and addition on the log1p
scale for rainfall (see ml/kriging.py: residual / apply_residual).

The same class is used by train.py (fit + save), evaluate.py (fit on subsets for
honest holdouts) and the FastAPI backend (load + predict).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.features import BLOCK_FEATURES, FEATURES, VARIABLES, build_features
from ml.kriging import ResidualField, apply_residual, residual

MODELS_DIR = Path(__file__).resolve().parent / "models"

# Fixed, conservative settings -- chosen up front, NOT tuned on the test period.
# Early stopping uses the validation period only.
XGB_PARAMS = {
    "objective": "reg:squarederror",
    "max_depth": 4,
    "eta": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 20,
    "lambda": 1.0,
    "seed": 42,
    "nthread": 4,
}
MAX_ROUNDS = 2000
EARLY_STOP = 100
RAIN_WET_MM = 1.0  # rain error bands are computed separately for dry and wet predictions


def block_frame(df: pd.DataFrame) -> pd.DataFrame:
    return df[BLOCK_FEATURES]


class Downscaler:
    def __init__(self):
        self.fields: dict[str, ResidualField] = {}
        self.boosters: dict[str, xgb.Booster] = {}
        self.bands: dict[str, dict] = {}
        self.info: dict = {}
        self.use_xgb: dict[str, bool] = {}      # per variable, decided on validation weeks

    # ------------------------------------------------------------------ fit --
    def fit(self, train: pd.DataFrame, val: pd.DataFrame, terrain: pd.DataFrame,
            variables=tuple(VARIABLES), verbose: bool = True) -> "Downscaler":
        X_tr = build_features(train.id, train.date, block_frame(train), terrain)
        X_va = build_features(val.id, val.date, block_frame(val), terrain)
        for var in variables:
            field = ResidualField.fit(train, terrain, var)
            self.fields[var] = field
            y_tr = self._xgb_target(var, train, X_tr)
            y_va = self._xgb_target(var, val, X_va)
            dtr = xgb.DMatrix(X_tr, label=y_tr, feature_names=FEATURES)
            dva = xgb.DMatrix(X_va, label=y_va, feature_names=FEATURES)
            booster = xgb.train(XGB_PARAMS, dtr, MAX_ROUNDS, evals=[(dva, "val")],
                                early_stopping_rounds=EARLY_STOP, verbose_eval=False)
            self.boosters[var] = booster
            self.info[var] = {"variogram": field.variogram, "kriging_loo_rmse": field.cv_rmse,
                              "xgb_rounds": booster.best_iteration + 1}
            if verbose:
                print(f"   {var:5s} variogram={field.variogram:11s} xgb_rounds={booster.best_iteration + 1}")
        self._choose_methods(val, terrain, verbose)
        self._fit_bands(val, terrain)
        return self

    def _choose_methods(self, val: pd.DataFrame, terrain: pd.DataFrame, verbose: bool):
        """Per variable, keep the XGBoost step only if it beats kriging alone on the
        VALIDATION weeks. Rule fixed before looking at the test period. (Validation was
        also used for early stopping, which slightly favours XGBoost -- so a variable
        where XGBoost still loses here is one where it genuinely adds noise.)"""
        pred = self.predict(val, terrain)
        for var in self.boosters:
            t = val[f"truth_{var}"].to_numpy()
            rmse = {m: float(np.sqrt(np.mean((pred[f"{m}_{var}"].to_numpy() - t) ** 2))) for m in ("krig", "xgb")}
            self.use_xgb[var] = rmse["xgb"] < rmse["krig"]
            self.info[var]["val_rmse"] = rmse
            self.info[var]["method"] = "kriging+xgboost" if self.use_xgb[var] else "kriging"
            if verbose:
                print(f"   {var:5s} val RMSE kriging={rmse['krig']:.3f} +xgb={rmse['xgb']:.3f} -> {self.info[var]['method']}")

    def _kriged(self, var, df, X) -> np.ndarray:
        months = pd.to_datetime(df.date).dt.month.to_numpy()
        return self.fields[var].predict(X.dx_km, X.dy_km, months)

    def _xgb_target(self, var, df, X) -> np.ndarray:
        """What XGBoost must learn: whatever the kriged residual did not explain."""
        r = residual(var, df[f"truth_{var}"].to_numpy(), df[f"block_{var}"].to_numpy())
        return r - self._kriged(var, df, X)

    def _fit_bands(self, val: pd.DataFrame, terrain: pd.DataFrame):
        """Empirical 10-90 % error band from the VALIDATION period (not the test period)."""
        pred = self.predict(val, terrain)
        for var in self.boosters:
            err = val[f"truth_{var}"].to_numpy() - pred[f"final_{var}"].to_numpy()
            if var == "rain":
                wet = pred["final_rain"].to_numpy() >= RAIN_WET_MM
                self.bands[var] = {
                    "dry": [float(np.percentile(err[~wet], 10)), float(np.percentile(err[~wet], 90))],
                    "wet": [float(np.percentile(err[wet], 10)), float(np.percentile(err[wet], 90))],
                }
            else:
                self.bands[var] = {"all": [float(np.percentile(err, 10)), float(np.percentile(err, 90))]}

    # -------------------------------------------------------------- predict --
    def predict(self, df: pd.DataFrame, terrain: pd.DataFrame, X: pd.DataFrame | None = None) -> pd.DataFrame:
        """Predictions for every method, in real units.

        Columns per variable:
          block_<v>  raw block value (baseline a)
          bias_<v>   block + taluka-wide monthly mean residual (bias-corrected baseline)
          krig_<v>   block + kriged residual            (baseline b)
          xgb_<v>    block + kriged + XGBoost           (method c)
          final_<v>  what GramVarsha serves: xgb_<v>, or krig_<v> for variables where
                     XGBoost did not beat kriging on the validation weeks
        """
        X = build_features(df.id, df.date, block_frame(df), terrain) if X is None else X
        months = pd.to_datetime(df.date).dt.month.to_numpy()
        out = pd.DataFrame({"id": df.id.to_numpy(), "date": df.date.to_numpy()}, index=df.index)
        dm = xgb.DMatrix(X, feature_names=FEATURES)
        for var, booster in self.boosters.items():
            blk = df[f"block_{var}"].to_numpy()
            field = self.fields[var]
            bias = field.table.mean().reindex(months).to_numpy()
            krig = self._kriged(var, df, X)
            corr = booster.predict(dm, iteration_range=(0, booster.best_iteration + 1))
            out[f"block_{var}"] = blk
            out[f"bias_{var}"] = apply_residual(var, blk, bias)
            out[f"krig_{var}"] = apply_residual(var, blk, krig)
            out[f"xgb_{var}"] = apply_residual(var, blk, krig + corr)
            if var == "rh":   # humidity is physically bounded
                for m in ("bias", "krig", "xgb"):
                    out[f"{m}_rh"] = out[f"{m}_rh"].clip(0, 100)
            out[f"final_{var}"] = out[f"xgb_{var}" if self.use_xgb.get(var, True) else f"krig_{var}"]
        return out

    def contributions(self, var: str, X: pd.DataFrame) -> pd.DataFrame:
        """Exact TreeSHAP contributions of each feature to the XGBoost correction.

        Uses XGBoost's built-in TreeSHAP (pred_contribs) -- the same algorithm as
        shap.TreeExplainer, verified equal in evaluate.py -- so the serving image
        does not need the heavy `shap` package. Last column 'bias' = expected value.
        """
        booster = self.boosters[var]
        c = booster.predict(xgb.DMatrix(X, feature_names=FEATURES), pred_contribs=True,
                            iteration_range=(0, booster.best_iteration + 1))
        return pd.DataFrame(c, columns=FEATURES + ["bias"], index=X.index)

    # ---------------------------------------------------------- persistence --
    def save(self, path: Path = MODELS_DIR):
        path.mkdir(parents=True, exist_ok=True)
        for var, b in self.boosters.items():
            b.save_model(path / f"xgb_{var}.json")
        (path / "kriging.json").write_text(json.dumps({v: f.to_dict() for v, f in self.fields.items()}, indent=1))
        (path / "meta.json").write_text(json.dumps({
            "features": FEATURES, "bands": self.bands, "info": self.info,
            "best_iteration": {v: b.best_iteration for v, b in self.boosters.items()},
            "use_xgb": self.use_xgb,
            "xgb_params": XGB_PARAMS,
        }, indent=2))

    @classmethod
    def load(cls, path: Path = MODELS_DIR) -> "Downscaler":
        self = cls()
        meta = json.loads((path / "meta.json").read_text())
        if meta["features"] != FEATURES:
            raise ValueError("Saved models were trained on a different feature list; retrain.")
        fields = json.loads((path / "kriging.json").read_text())
        for var, best in meta["best_iteration"].items():
            b = xgb.Booster()
            b.load_model(path / f"xgb_{var}.json")
            b.set_attr(best_iteration=str(best))
            self.boosters[var] = b
            self.fields[var] = ResidualField.from_dict(fields[var])
        self.bands, self.info, self.use_xgb = meta["bands"], meta["info"], meta["use_xgb"]
        return self

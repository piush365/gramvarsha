"""Honest validation of the downscaler on data it has never seen.

    python -m ml.evaluate

Two holdouts, both scored ONLY on the test period (last 3 months):

  1. Temporal holdout -- the saved production model (trained on all villages,
     before TEST_START) forecasts the test months.
  2. Spatial holdout  -- 5-fold over villages: each fold's model (kriging + XGBoost)
     is fitted WITHOUT a fifth of the villages, then scored on those unseen villages
     in the test months. This is the realistic case: a panchayat with no station.

Methods compared, per variable:
  block    raw block (coarse) value -- what every panchayat gets today
  physics  lapse-rate / orographic rules, no training (Tier B)
  bias     block + taluka-wide monthly mean correction (removes only the block's
           systematic bias -- shows how much of any gain is NOT spatial)
  krig     block + kriged monthly residual
  xgb      block + kriged + XGBoost (GramVarsha, Tier A)

Writes ml/metrics.json for the /validation page. Numbers are reported as they come.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ml.build_dataset import GAP_DAYS, TEST_START, VAL_EVERY_N_WEEKS
from ml.features import FEATURES, VARIABLES, build_features, load_block_meta, load_terrain
from ml.model import MODELS_DIR, Downscaler, block_frame
from ml.physics import physics_downscale
from ml.train import load_dataset

METHODS = ["block", "physics", "bias", "krig", "xgb"]
N_FOLDS = 5
FOLD_SEED = 7
OUT = MODELS_DIR.parent / "metrics.json"


def scores(truth: np.ndarray, pred: np.ndarray) -> dict:
    e = pred - truth
    return {"rmse": float(np.sqrt(np.mean(e ** 2))), "mae": float(np.mean(np.abs(e))), "bias": float(np.mean(e))}


def add_physics(pred: pd.DataFrame, df: pd.DataFrame, terrain: pd.DataFrame) -> pd.DataFrame:
    """Physics baseline: move the block value from the GFS cell height to the village height."""
    gfs_elev = float(pd.read_parquet("data/raw/block_history.parquet").grid_elev_m.iloc[0])
    blk = {v: df[f"block_{v}"].to_numpy() for v in VARIABLES}
    phys = physics_downscale(blk, gfs_elev, terrain.loc[df.id, "elevation_m"].to_numpy())
    for v in VARIABLES:
        pred[f"physics_{v}"] = phys[v]
    return pred


def score_table(pred: pd.DataFrame, df: pd.DataFrame) -> dict:
    out = {}
    for v in VARIABLES:
        t = df[f"truth_{v}"].to_numpy()
        out[v] = {m: scores(t, pred[f"{m}_{v}"].to_numpy()) for m in METHODS}
        # Spatial skill: can the method reproduce the DIFFERENCES between villages on
        # the same day? Compare each village's deviation from that day's village mean.
        tt = df.assign(t=t, **{m: pred[f"{m}_{v}"].to_numpy() for m in METHODS})
        dev = tt.groupby("date")[["t"] + METHODS].transform(lambda s: s - s.mean())
        out[v]["spatial_pattern_rmse"] = {m: float(np.sqrt(np.mean((dev[m] - dev.t) ** 2))) for m in METHODS}
        out[v]["truth_spread_sd"] = float(dev.t.std())
    return out


def village_folds(ids: list[str]) -> list[list[str]]:
    rng = np.random.default_rng(FOLD_SEED)
    shuffled = rng.permutation(sorted(ids))
    return [list(shuffled[i::N_FOLDS]) for i in range(N_FOLDS)]


def shap_consistency(model: Downscaler, X: pd.DataFrame) -> float:
    """Max |difference| between shap.TreeExplainer and XGBoost's built-in TreeSHAP."""
    import shap
    worst = 0.0
    for var, booster in model.boosters.items():
        booster.set_param({"nthread": 1})
        ref = shap.TreeExplainer(booster).shap_values(X)
        ours = model.contributions(var, X)[FEATURES].to_numpy()
        worst = max(worst, float(np.abs(ref - ours).max()))
    return worst


def main():
    df = load_dataset()
    terrain = load_terrain()
    test = df[df.split == "test"].reset_index(drop=True)

    # ---- 1. temporal holdout with the saved production model ---------------
    print("temporal holdout (saved model, all villages, test months)")
    model = Downscaler.load(MODELS_DIR)
    X_test = build_features(test.id, test.date, block_frame(test), terrain)
    pred = add_physics(model.predict(test, terrain, X_test), test, terrain)
    temporal = score_table(pred, test)

    per_village = {}
    for pid, g in pred.groupby("id"):
        t = test.loc[g.index]
        per_village[pid] = {v: {m: round(scores(t[f"truth_{v}"].to_numpy(), g[f"{m}_{v}"].to_numpy())["rmse"], 3)
                                for m in ("block", "xgb")} for v in VARIABLES}

    # Feature importance = mean |SHAP| over the test rows, per variable.
    importance = {}
    for v in VARIABLES:
        c = model.contributions(v, X_test)[FEATURES].abs().mean()
        importance[v] = {k: round(float(c[k]), 4) for k in c.sort_values(ascending=False).index}

    shap_diff = shap_consistency(model, X_test.sample(300, random_state=0))
    print(f"   shap.TreeExplainer vs xgboost pred_contribs max |diff| = {shap_diff:.2e}")

    # ---- 2. spatial holdout: villages never seen in training ---------------
    print(f"spatial holdout ({N_FOLDS} folds over villages)")
    fit_rows = df[df.split.isin(["train", "val"])]
    spatial_preds = []
    for k, held in enumerate(village_folds(df.id.unique().tolist()), 1):
        print(f"   fold {k}: holding out {len(held)} villages")
        seen = ~fit_rows.id.isin(held)
        m = Downscaler().fit(fit_rows[seen & (fit_rows.split == "train")],
                             fit_rows[seen & (fit_rows.split == "val")], terrain, verbose=False)
        tf = test[test.id.isin(held)]
        spatial_preds.append(add_physics(m.predict(tf, terrain), tf, terrain))
    sp = pd.concat(spatial_preds).loc[test.index]
    spatial = score_table(sp, test)

    meta = load_block_meta()
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "test_period": {"start": TEST_START, "end": str(test.date.max()), "days": int(test.date.nunique()),
                        "rows": int(len(test))},
        "split": {"val_every_n_weeks": VAL_EVERY_N_WEEKS, "gap_days": GAP_DAYS,
                  "train_rows": int((df.split == "train").sum()), "val_rows": int((df.split == "val").sum())},
        "block": meta,
        "units": {v: VARIABLES[v][1] for v in VARIABLES},
        "methods": METHODS,
        "temporal": temporal,
        "spatial": spatial,
        "per_village_temporal_rmse": per_village,
        "feature_importance": importance,
        "shap_check_max_abs_diff": shap_diff,
        "model_info": model.info,
        "bands": model.bands,
        "notes": [
            "Truth is ECMWF IFS 9 km (pseudo ground truth), not station observations.",
            "The 47 villages fall in 17 IFS grid cells, so nearby villages share a truth value.",
            "Block value is archived GFS 0.25 deg at the taluka centroid (IMD block-forecast proxy).",
        ],
    }, indent=1))
    print_table(temporal, spatial)
    print(f"wrote {OUT}")


def print_table(temporal: dict, spatial: dict):
    print("\nRMSE on the test months (lower is better). Improvement = xgb vs block.")
    head = f"{'variable':6s} {'holdout':8s} " + " ".join(f"{m:>8s}" for m in METHODS) + "   xgb vs block   xgb vs bias"
    print(head)
    print("-" * len(head))
    for v in VARIABLES:
        for name, tab in (("time", temporal), ("village", spatial)):
            r = {m: tab[v][m]["rmse"] for m in METHODS}
            gain = 100 * (1 - r["xgb"] / r["block"])
            gain_b = 100 * (1 - r["xgb"] / r["bias"])
            print(f"{v:6s} {name:8s} " + " ".join(f"{r[m]:8.2f}" for m in METHODS)
                  + f"   {gain:+10.1f} %   {gain_b:+9.1f} %")
    print("\nSpatial-pattern RMSE (errors in village-to-village DIFFERENCES on the same day):")
    print(f"{'variable':6s} {'holdout':8s} " + " ".join(f"{m:>8s}" for m in METHODS) + f"  {'truth sd':>9s}")
    for v in VARIABLES:
        for name, tab in (("time", temporal), ("village", spatial)):
            r = tab[v]["spatial_pattern_rmse"]
            print(f"{v:6s} {name:8s} " + " ".join(f"{r[m]:8.2f}" for m in METHODS)
                  + f"  {tab[v]['truth_spread_sd']:9.2f}")


if __name__ == "__main__":
    main()

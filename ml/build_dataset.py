"""Pair the coarse block value with each village's fine value, day by day.

    python -m ml.build_dataset

Input : data/raw/block_history.parquet   (GFS at block centroid, one row per day)
        data/raw/truth_history.parquet   (ECMWF IFS 9 km at each village)
        data/imd_import/*.csv            (optional real station data, see README there)
Output: data/processed/dataset.parquet   one row per (panchayat, day):
        id, date, block_<var>, truth_<var>, split
"""
from __future__ import annotations

import pandas as pd

from ml.features import DATA, VARIABLES

PROCESSED = DATA / "processed"

# Time-based split.
#   TEST : the last 3 months (monsoon 2026). Untouched until ml/evaluate.py.
#   VAL  : every 5th week of the remaining period, used only for early stopping and
#          error bands. Spreading it across the year means it contains monsoon days;
#          a single contiguous Mar-May block would be almost rain-free.
#   GAP  : 3 days either side of each VAL week are dropped from TRAIN, because
#          weather on neighbouring days is correlated (prevents leakage).
#   TRAIN: everything else before TEST_START.
TEST_START = "2026-06-01"
VAL_EVERY_N_WEEKS = 5
GAP_DAYS = 3


def to_var_columns(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    rename = {field: f"{prefix}_{v}" for v, (field, _, _) in VARIABLES.items()}
    return df.rename(columns=rename)[["date"] + (["id"] if "id" in df else []) + list(rename.values())]


def load_station_overrides() -> pd.DataFrame | None:
    """Real IMD AWS/ARG observations, if someone dropped CSVs in data/imd_import/.

    Expected columns: id, date, and any of tmax, tmin, rain, rh, wind.
    Where present they REPLACE the pseudo-truth for that village/day.
    """
    files = sorted((DATA / "imd_import").glob("*.csv"))
    if not files:
        return None
    obs = pd.concat([pd.read_csv(f, dtype={"id": str, "date": str}) for f in files], ignore_index=True)
    keep = ["id", "date"] + [v for v in VARIABLES if v in obs]
    return obs[keep].rename(columns={v: f"truth_{v}" for v in VARIABLES})


def split_of(date: pd.Series) -> pd.Series:
    """Label each date train / val / gap / test (see the constants above)."""
    d = pd.to_datetime(date)
    days = pd.Series(d.unique()).sort_values()
    week_no = ((days - days.min()).dt.days // 7)
    val_days = set(days[(week_no % VAL_EVERY_N_WEEKS == VAL_EVERY_N_WEEKS - 1) & (days < TEST_START)])
    gap_days = {v + pd.Timedelta(days=k) for v in val_days
                for k in range(-GAP_DAYS, GAP_DAYS + 1) if k} - val_days
    label = pd.Series("train", index=date.index)
    label[d.isin(gap_days)] = "gap"
    label[d.isin(val_days)] = "val"
    label[d >= TEST_START] = "test"
    return label


def build() -> pd.DataFrame:
    block = to_var_columns(pd.read_parquet(DATA / "raw/block_history.parquet"), "block").drop(columns="id")
    truth = to_var_columns(pd.read_parquet(DATA / "raw/truth_history.parquet"), "truth")
    df = truth.merge(block, on="date", how="inner")

    obs = load_station_overrides()
    if obs is not None:
        df = df.set_index(["id", "date"])
        df.update(obs.set_index(["id", "date"]))
        df = df.reset_index()
        print(f"   applied {len(obs)} station observation rows from data/imd_import/")

    df = df.dropna().sort_values(["date", "id"]).reset_index(drop=True)
    df["split"] = split_of(df.date)
    return df


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df = build()
    df.to_parquet(PROCESSED / "dataset.parquet", index=False)
    counts = df.groupby("split").date.agg(["nunique", "min", "max"])
    print(f"dataset: {len(df)} rows, {df.id.nunique()} panchayats")
    print(counts.rename(columns={"nunique": "days"}).loc[["train", "gap", "val", "test"]].to_string())


if __name__ == "__main__":
    main()

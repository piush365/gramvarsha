"""Train the production downscaler.

    python -m ml.train

Kriging fields + XGBoost models are fitted on the TRAIN period for all villages,
early-stopped on the VALIDATION period, and saved to ml/models/. The TEST period
(last 3 months) is never touched here -- only ml/evaluate.py looks at it.
"""
from __future__ import annotations

import time

import pandas as pd

from ml.build_dataset import PROCESSED
from ml.features import load_terrain
from ml.model import MODELS_DIR, Downscaler


def load_dataset() -> pd.DataFrame:
    path = PROCESSED / "dataset.parquet"
    if not path.exists():
        raise SystemExit("data/processed/dataset.parquet missing -- run `python -m ml.build_dataset` first")
    return pd.read_parquet(path)


def main():
    df = load_dataset()
    terrain = load_terrain()
    t0 = time.time()
    print(f"training on {(df.split == 'train').sum()} rows, early-stopping on {(df.split == 'val').sum()}")
    model = Downscaler().fit(df[df.split == "train"], df[df.split == "val"], terrain)
    model.save(MODELS_DIR)
    print(f"saved to {MODELS_DIR} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

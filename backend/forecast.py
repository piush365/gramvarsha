"""Live forecast service: fetch the coarse block forecast, downscale it, cache it.

Flow (runs on startup and every REFRESH_HOURS):
  1. Fetch the 5-day GFS forecast at the block centroid (same model and settings
     as the training "block value", so the model sees what it was trained on).
  2. For every panchayat pick a tier:
       A  kriging + XGBoost (models loaded, terrain known)
       B  physics only: lapse rate + orographic factor (terrain known, no models)
       C  block value passed through, flagged "limited local data"
  3. Attach confidence bands (from validation errors) and SHAP explanations.
  4. Keep the result in memory and on disk. If a fetch fails, keep serving the
     last good result with a "stale since ..." flag. Never fail silently.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from ml.explain import explain, local_share
from ml.features import BLOCK_FEATURES, DATA, VARIABLES, build_features, load_block_meta, load_terrain
from ml.model import MODELS_DIR, RAIN_WET_MM, Downscaler
from ml.physics import physics_downscale

log = logging.getLogger("gramvarsha.forecast")

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_FILE = CACHE_DIR / "forecast.json"
# Last-resort copy shipped with the code (regenerated daily by GitHub Actions).
SNAPSHOT_FILES = [ROOT / "frontend/public/snapshot.json"]

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# Last good copy, regenerated daily by .github/workflows/refresh-snapshot.yml and committed
# to the public repo. Used when the live fetch fails, e.g. Open-Meteo rate-limiting a shared
# cloud IP with HTTP 429.
SNAPSHOT_URL = os.environ.get(
    "SNAPSHOT_URL", "https://raw.githubusercontent.com/piush365/gramvarsha/main/frontend/public/snapshot.json")
RETRY_WAITS_S = (10, 30)     # backoff between attempts on 429 / 5xx
BLOCK_MODEL = "gfs_global"
FORECAST_DAYS = 5
VALIDATED_LEADS = 2          # day 0 and day 1 match the archive used for validation
TZ = "Asia/Kolkata"

TIER_TEXT = {
    "A": "Full ML correction (kriging + XGBoost)",
    "B": "Physics-only terrain correction (lapse rate, orographic rain)",
    "C": "Limited local data: showing the block forecast unchanged",
}


# ---------------------------------------------------------------------------
# Tier selection (pure function -> unit tested)
# ---------------------------------------------------------------------------
@dataclass
class TierInputs:
    models_loaded: bool
    has_terrain: bool            # all terrain features present and finite
    has_elevation: bool          # at least the village elevation is known


def select_tier(t: TierInputs) -> str:
    if t.models_loaded and t.has_terrain:
        return "A"
    if t.has_elevation:
        return "B"
    return "C"


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def fetch_block_forecast(block: dict, timeout: float = 20) -> tuple[pd.DataFrame, float]:
    """5-day coarse forecast at the block centroid. Returns (daily frame, GFS cell elevation).

    Dates are pinned to "today in India" onwards: just after midnight IST the latest
    GFS run can still start on the previous calendar day.
    """
    today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()
    params = {
        "start_date": today.isoformat(), "end_date": (today + timedelta(days=FORECAST_DAYS - 1)).isoformat(),
        "latitude": block["lat"], "longitude": block["lon"], "elevation": "nan",
        "daily": ",".join(field for field, _, _ in VARIABLES.values()),
        "models": BLOCK_MODEL, "timezone": TZ,
    }
    for wait in (*RETRY_WAITS_S, None):
        r = requests.get(FORECAST_URL, timeout=timeout, params=params)
        if r.status_code not in (429, 500, 502, 503, 504) or wait is None:
            break
        retry_after = r.headers.get("Retry-After", "")
        wait = min(int(retry_after), 60) if retry_after.isdigit() else wait
        log.warning("Open-Meteo HTTP %s; retrying in %ss", r.status_code, wait)
        time.sleep(wait)
    r.raise_for_status()
    body = r.json()
    daily = pd.DataFrame(body["daily"]).rename(columns={"time": "date"})
    daily = daily.rename(columns={field: f"block_{v}" for v, (field, _, _) in VARIABLES.items()})
    if daily[BLOCK_FEATURES].isna().any().any():
        raise ValueError("block forecast has missing values")
    return daily, float(body["elevation"])


def fetch_remote_snapshot(timeout: float = 20) -> dict:
    """The website's published snapshot (same pipeline, run daily elsewhere)."""
    r = requests.get(SNAPSHOT_URL, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Downscaling
# ---------------------------------------------------------------------------
def _band(model: Downscaler | None, var: str, value: float) -> tuple[float, float] | None:
    if model is None or var not in model.bands:
        return None
    b = model.bands[var]
    lo, hi = (b["wet"] if value >= RAIN_WET_MM else b["dry"]) if var == "rain" else b["all"]
    low, high = value + lo, value + hi
    if var == "rain":
        low, high = max(0.0, low), max(0.0, high)
    if var == "rh":
        low, high = max(0.0, low), min(100.0, high)
    return round(low, 1), round(high, 1)


def load_places() -> pd.DataFrame:
    pts = pd.read_csv(DATA / "panchayats.csv", dtype={"lgd_code": str}).set_index("id")
    names = pd.read_csv(DATA / "village_names.csv").set_index("id")
    pts["name_mr"] = names.name_mr.reindex(pts.index).fillna(pts.name)
    # Hindi uses the same Devanagari spelling except the Marathi-only letter ळ -> ल.
    pts["name_hi"] = pts.name_mr.str.replace("ळ", "ल")
    return pts


def downscale(daily: pd.DataFrame, gfs_elev: float, model: Downscaler | None,
              terrain: pd.DataFrame, places: pd.DataFrame) -> list[dict]:
    """Run the tiered pipeline for every panchayat and every forecast day."""
    ids = places.index.tolist()
    grid = pd.DataFrame([(pid, d) for pid in ids for d in daily.date], columns=["id", "date"])
    grid = grid.merge(daily, on="date")

    finite = terrain.reindex(ids).notna().all(axis=1)
    tiers = {pid: select_tier(TierInputs(
        models_loaded=model is not None,
        has_terrain=bool(finite.get(pid, False)),
        has_elevation=pid in terrain.index and not math.isnan(terrain.loc[pid, "elevation_m"]),
    )) for pid in ids}

    # --- Tier A rows ---------------------------------------------------------
    a_rows = grid[grid.id.map(tiers) == "A"]
    pred, X, contribs, kriged = None, None, {}, {}
    if len(a_rows):
        X = build_features(a_rows.id, a_rows.date, a_rows[BLOCK_FEATURES], terrain)
        pred = model.predict(a_rows, terrain, X)
        months = pd.to_datetime(a_rows.date).dt.month.to_numpy()
        for v in VARIABLES:
            contribs[v] = model.contributions(v, X) if model.use_xgb.get(v, True) else None
            kriged[v] = model.fields[v].predict(X.dx_km, X.dy_km, months)

    out = []
    for pid in ids:
        p = places.loc[pid]
        tier = tiers[pid]
        days = []
        for lead, (_, row) in enumerate(grid[grid.id == pid].iterrows()):
            blk = {v: float(row[f"block_{v}"]) for v in VARIABLES}
            values = {}
            if tier == "A":
                month = pd.Timestamp(row.date).month
                for v in VARIABLES:
                    val = float(pred.at[row.name, f"final_{v}"])
                    shap_row = contribs[v].loc[row.name] if contribs[v] is not None else pd.Series({"bias": 0.0})
                    kr = float(kriged[v][a_rows.index.get_loc(row.name)])
                    ex = explain(v, blk[v], val, kr, shap_row, month_bias=float(model.fields[v].table[month].mean()))
                    ex["local_share"] = local_share(ex["parts"])
                    values[v] = {"block": round(blk[v], 1), "value": round(val, 1),
                                 "band": _band(model, v, val), "explanation": ex}
            elif tier == "B":
                phys = physics_downscale(blk, gfs_elev, float(terrain.loc[pid, "elevation_m"]))
                for v in VARIABLES:
                    val = float(phys[v])
                    values[v] = {"block": round(blk[v], 1), "value": round(val, 1), "band": None,
                                 "explanation": {"delta": round(val - blk[v], 2), "unit": VARIABLES[v][1],
                                                 "sentence": "Physics rule only (no trained model available).",
                                                 "parts": [], "note": None, "local_share": 1.0}}
            else:
                for v in VARIABLES:
                    values[v] = {"block": round(blk[v], 1), "value": round(blk[v], 1), "band": None,
                                 "explanation": {"delta": 0.0, "unit": VARIABLES[v][1],
                                                 "sentence": "Limited local data: block value shown unchanged.",
                                                 "parts": [], "note": None, "local_share": 0.0}}
            days.append({"date": row.date, "lead": lead, "validated": lead < VALIDATED_LEADS, "values": values})
        t = terrain.loc[pid] if pid in terrain.index else None
        out.append({
            "id": pid, "name": p["name"], "name_mr": p.name_mr, "name_hi": p.name_hi,
            "lat": float(p.lat), "lon": float(p.lon), "lgd_code": p.lgd_code if isinstance(p.lgd_code, str) else None,
            "elevation_m": None if t is None else float(t.elevation_m),
            "dist_river_km": None if t is None else float(t.dist_river_km),
            "tier": tier, "tier_text": TIER_TEXT[tier], "days": days,
        })
    return out


def spread(panchayats: list[dict]) -> list[dict]:
    """Max - min across panchayats, per day and variable (the header stat)."""
    n = len(panchayats[0]["days"]) if panchayats else 0
    res = []
    for d in range(n):
        vals = {v: [p["days"][d]["values"][v]["value"] for p in panchayats] for v in VARIABLES}
        res.append({v: round(max(x) - min(x), 1) for v, x in vals.items()})
    return res


# ---------------------------------------------------------------------------
# Service object used by the API
# ---------------------------------------------------------------------------
class ForecastService:
    def __init__(self):
        self.block = load_block_meta()
        self.terrain = load_terrain()
        self.places = load_places()
        try:
            self.model: Downscaler | None = Downscaler.load(MODELS_DIR)
        except Exception as e:                          # -> Tier B everywhere, loudly
            log.error("could not load models (%s); falling back to physics tier", e)
            self.model = None
        self.data: dict | None = None
        self.last_error: str | None = None

    def load_cached(self):
        for path in [CACHE_FILE, *SNAPSHOT_FILES]:
            if path.exists():
                try:
                    self.data = json.loads(path.read_text())
                    self.data["stale"] = True
                    self.data["stale_since"] = self.data.get("generated_at")
                    self.data["served_from"] = str(path.relative_to(ROOT))
                    log.info("loaded cached forecast from %s", path)
                    return
                except Exception as e:
                    log.warning("could not read %s: %s", path, e)

    def use_remote_snapshot_if_newer(self) -> bool:
        """After a failed live fetch: adopt the published snapshot if it is newer than what we serve."""
        try:
            snap = fetch_remote_snapshot()
        except Exception as e:
            log.warning("remote snapshot unavailable: %s", e)
            return False
        if self.data and snap.get("generated_at", "") <= self.data.get("generated_at", ""):
            return False
        snap.update({"stale": True, "stale_since": snap.get("generated_at"), "served_from": SNAPSHOT_URL})
        self.data = snap
        log.info("serving remote snapshot generated %s", snap.get("generated_at"))
        return True

    def refresh(self) -> bool:
        """Fetch + downscale. On any failure keep the previous data, marked stale."""
        try:
            daily, gfs_elev = fetch_block_forecast(self.block)
            panchayats = downscale(daily, gfs_elev, self.model, self.terrain, self.places)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.data = {
                "generated_at": now, "stale": False, "stale_since": None, "served_from": "live",
                "source": {"block_model": f"Open-Meteo {BLOCK_MODEL} (IMD-equivalent coarse forecast proxy)",
                           "gfs_cell_elevation_m": gfs_elev, "validated_leads": VALIDATED_LEADS},
                "block": {**self.block, "forecast": daily.rename(
                    columns={f"block_{v}": v for v in VARIABLES}).round(1).to_dict("records")},
                "dates": daily.date.tolist(),
                "units": {v: VARIABLES[v][1] for v in VARIABLES},
                "tiers": {t: sum(p["tier"] == t for p in panchayats) for t in "ABC"},
                "spread": spread(panchayats),
                "panchayats": panchayats,
            }
            CACHE_DIR.mkdir(exist_ok=True)
            CACHE_FILE.write_text(json.dumps(self.data, ensure_ascii=False))
            self.last_error = None
            log.info("forecast refreshed: %d panchayats, tiers %s", len(panchayats), self.data["tiers"])
            return True
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            log.error("forecast refresh failed: %s", self.last_error)
            if self.data is None:
                self.load_cached()
            elif not self.data.get("stale"):
                self.data["stale"] = True
                self.data["stale_since"] = self.data["generated_at"]
            self.use_remote_snapshot_if_newer()
            return False

    def panchayat(self, pid: str) -> dict | None:
        if not self.data:
            return None
        return next((p for p in self.data["panchayats"] if p["id"] == pid), None)

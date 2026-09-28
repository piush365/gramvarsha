"""Rebuild every cached input in data/ from free, open sources.

    python scripts/fetch_data.py            # fetch only what is missing
    python scripts/fetch_data.py --refresh  # re-download everything

Outputs (all committed, so the app/deploys never need these APIs):
    data/raw/osm_*.json               raw OSM responses (Overpass: boundary, villages; Nominatim: rivers)
    data/taluka_boundary.geojson      Miraj taluka polygon (OSM relation 9742028)
    data/rivers.geojson               Krishna river line near the taluka
    data/panchayats.csv               villages: id, name, name_mr, lat, lon, lgd_code
    data/voronoi.geojson              APPROXIMATE panchayat polygons (Voronoi, clipped)
    data/raw/dem_patches.parquet      5x5 DEM samples around each village
    data/terrain.csv                  elevation, slope, aspect, TPI, river distance
    data/raw/block_history.parquet    coarse GFS forecast at the block centroid (the "block value")
    data/raw/truth_history.parquet    ECMWF IFS 9 km at every village (pseudo ground truth)
    data/manifest.json                what was fetched, from where, when

Why these sources (see README "Data" for the long version):
  * IMD block forecasts / AWS archives have no open API, so the coarse GFS 0.25 deg
    forecast (archived by Open-Meteo's Historical Forecast API) stands in for the
    IMD block forecast. The live app uses the SAME model, so training and serving match.
  * Open-Meteo's ERA5-Land has no precipitation or wind, so the 9 km ECMWF IFS
    archive is used as pseudo "truth" for all five variables.
  * Model data is requested with elevation=nan so Open-Meteo does NOT apply its own
    lapse-rate correction -- the terrain signal must be learned by our model.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import LineString, MultiPoint, Point, mapping, shape
from shapely.ops import linemerge, polygonize, transform, unary_union, voronoi_diagram

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.terrain import PATCH_N, patch_offsets, slope_aspect, tpi  # noqa: E402

DATA = ROOT / "data"
RAW = DATA / "raw"

# ---- Study area ------------------------------------------------------------
TALUKA_RELATION_ID = 9742028          # OSM: Miraj taluka, LGD subdistrict 4302
# River for the distance-to-river feature. The Krishna forms Miraj's western edge; the
# Warna joins it at Haripur, just outside the taluka, so the Krishna alone is used.
RIVER_RELATIONS = {"Krishna": 337204}     # OSM relation ids
# OSM nodes inside the taluka whose name is clearly a mistake (e.g. a node named after
# a different city). Listed explicitly so the exclusion is visible and reviewable.
BAD_NAMES = {"pune"}

# ---- Time window: two full years, ending before the archive's ~5-day lag ---
START_DATE = "2024-09-01"
END_DATE = "2026-08-31"

DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
]
BLOCK_MODEL = "gfs_global"    # coarse (~25 km) -- the "block forecast" proxy
TRUTH_MODEL = "ecmwf_ifs"     # fine (~9 km)    -- pseudo ground truth
TZ = "Asia/Kolkata"           # daily totals follow Indian calendar days

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
UA = {"User-Agent": "GramVarsha-SIH-prototype/0.1 (open-data research demo)"}

# UTM zone 43N: metre-based CRS for distances and Voronoi geometry.
TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform
TO_WGS = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True).transform


# ---------------------------------------------------------------------------
# HTTP helpers (polite: retries with backoff, pauses between calls)
# ---------------------------------------------------------------------------
def overpass(query: str) -> dict:
    """Run an Overpass query, trying each mirror in turn."""
    last_err = None
    for attempt in range(2):
        for url in OVERPASS_MIRRORS:
            try:
                r = requests.post(url, data={"data": query}, headers=UA, timeout=180)
                if r.ok and r.text.lstrip().startswith("{"):
                    return r.json()
                last_err = f"{url}: HTTP {r.status_code} {r.text[:120]!r}"
            except requests.RequestException as e:
                last_err = f"{url}: {e}"
            print(f"   overpass mirror failed ({last_err}); trying next")
            time.sleep(5)
        time.sleep(30 * (attempt + 1))
    raise RuntimeError(f"All Overpass mirrors failed. Last error: {last_err}")


def get_json(url: str, params: dict, tries: int = 5):
    """GET with exponential backoff on 429/5xx (Open-Meteo free-tier friendly)."""
    for i in range(tries):
        r = requests.get(url, params=params, headers=UA, timeout=120)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            wait = 20 * 2**i
            print(f"   HTTP {r.status_code}; backing off {wait}s")
            time.sleep(wait)
            continue
        raise RuntimeError(f"{url} -> HTTP {r.status_code}: {r.text[:300]}")
    raise RuntimeError(f"{url} failed after {tries} tries")


def write_geojson(path: Path, features: list[dict]):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False))


# ---------------------------------------------------------------------------
# 1. OpenStreetMap: taluka boundary, villages, rivers
# ---------------------------------------------------------------------------
def fetch_osm(refresh: bool):
    for name, query in {
        "osm_boundary.json": f"[out:json][timeout:120];rel({TALUKA_RELATION_ID});out geom;",
        "osm_villages.json": (
            f"[out:json][timeout:120];rel({TALUKA_RELATION_ID});map_to_area->.a;"
            'node["place"~"^(village|hamlet)$"]["name"](area.a);out;'
        ),
    }.items():
        path = RAW / name
        if path.exists() and not refresh:
            print(f"   cached: {name}")
            continue
        print(f"   fetching {name} from Overpass ...")
        path.write_text(json.dumps(overpass(query), ensure_ascii=False))
        time.sleep(5)

    # River geometry comes from Nominatim's lookup of the OSM relation: one light request
    # instead of a heavy Overpass bbox query (the public Overpass servers often time out).
    path = RAW / "osm_rivers.json"
    if refresh or not path.exists():
        print("   fetching osm_rivers.json from Nominatim ...")
        res = get_json("https://nominatim.openstreetmap.org/lookup", {
            "osm_ids": ",".join(f"R{i}" for i in RIVER_RELATIONS.values()),
            "format": "jsonv2", "polygon_geojson": 1,
        })
        path.write_text(json.dumps(res, ensure_ascii=False))
    else:
        print("   cached: osm_rivers.json")


def build_boundary():
    """Assemble the taluka polygon from the relation's outer ways."""
    rel = json.loads((RAW / "osm_boundary.json").read_text())["elements"][0]
    lines = [
        LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        for m in rel["members"]
        if m["type"] == "way" and m.get("role", "outer") in ("outer", "") and "geometry" in m
    ]
    polys = list(polygonize(linemerge(lines)))
    if not polys:
        raise RuntimeError("Could not assemble taluka polygon from OSM ways")
    boundary = unary_union(polys)
    write_geojson(DATA / "taluka_boundary.geojson", [{
        "type": "Feature",
        "properties": {"name": "Miraj", "name_mr": rel["tags"].get("name:mr"),
                       "lgd_subdistrict": rel["tags"].get("ref:LGD:subdistrict"),
                       "osm_relation": TALUKA_RELATION_ID},
        "geometry": mapping(boundary),
    }])
    return boundary


def build_rivers(boundary):
    """River lines, clipped to a 15 km buffer around the taluka (the whole Krishna is 1,400 km)."""
    area = transform(TO_WGS, transform(TO_UTM, boundary).buffer(15_000))
    feats = []
    for r in json.loads((RAW / "osm_rivers.json").read_text()):
        name = next(k for k, v in RIVER_RELATIONS.items() if v == r["osm_id"])
        feats.append({
            "type": "Feature",
            "properties": {"name": name, "osm_relation": r["osm_id"]},
            "geometry": mapping(shape(r["geojson"]).intersection(area)),
        })
    write_geojson(DATA / "rivers.geojson", feats)
    return unary_union([shape(f["geometry"]) for f in feats])


def slugify(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def build_panchayats(boundary) -> pd.DataFrame:
    """Villages inside the taluka. Hamlets are only used if villages are too few."""
    nodes = json.loads((RAW / "osm_villages.json").read_text())["elements"]
    rows = []
    for n in nodes:
        t = n["tags"]
        if not boundary.contains(Point(n["lon"], n["lat"])):
            continue
        name = (t.get("name:en") or t["name"]).strip()
        if name.lower() in BAD_NAMES:
            continue
        if not name.istitle():      # OSM typos like "KAdamwadi" -> "Kadamwadi"
            name = name.title()
        rows.append({
            "name": name,
            # OSM name:mr is sparse and sometimes wrong (Arag is tagged "मुरगुंडि"), so the
            # Devanagari names come from a hand-checked list added with the advisory engine.
            "name_mr": "",
            "place": t["place"],
            "lat": round(n["lat"], 6),
            "lon": round(n["lon"], 6),
            "lgd_code": t.get("ref:LGD") or t.get("ref:LGD:village") or t.get("lgd_code") or "",
            "osm_id": n["id"],
        })
    df = pd.DataFrame(rows)
    villages = df[df.place == "village"]
    if len(villages) >= 25:
        df = villages
    df = df.drop_duplicates("name").sort_values("name").reset_index(drop=True)
    # Stable, URL-safe ids; disambiguate repeated slugs.
    ids = df.name.map(slugify)
    df.insert(0, "id", ids.where(~ids.duplicated(keep=False), ids + "-" + df.osm_id.astype(str)))
    df.to_csv(DATA / "panchayats.csv", index=False)
    print(f"   {len(df)} panchayat points ({(df.place == 'village').sum()} villages)")
    return df


def build_voronoi(pts: pd.DataFrame, boundary):
    """Approximate panchayat polygons: Voronoi cells of village points, clipped to the taluka.

    LGD / Bhunaksha boundaries replace these in production.
    """
    b_utm = transform(TO_UTM, boundary)
    mp = MultiPoint([TO_UTM(lon, lat) for lon, lat in zip(pts.lon, pts.lat)])
    cells = voronoi_diagram(mp, envelope=b_utm.buffer(5000))
    feats = []
    for _, row in pts.iterrows():
        p = Point(TO_UTM(row.lon, row.lat))
        cell = next(c for c in cells.geoms if c.contains(p))
        clipped = cell.intersection(b_utm)
        feats.append({
            "type": "Feature",
            "properties": {"id": row.id, "name": row["name"], "area_km2": round(clipped.area / 1e6, 2),
                           "approximate": True},
            "geometry": mapping(transform(TO_WGS, clipped).simplify(0.0003)),
        })
    write_geojson(DATA / "voronoi.geojson", feats)


# ---------------------------------------------------------------------------
# 2. Terrain from the Copernicus 90 m DEM (Open-Meteo Elevation API)
# ---------------------------------------------------------------------------
def fetch_dem(pts: pd.DataFrame, refresh: bool) -> pd.DataFrame:
    path = RAW / "dem_patches.parquet"
    if path.exists() and not refresh:
        cached = pd.read_parquet(path)
        if set(cached.id.unique()) >= set(pts.id):
            print("   cached: dem_patches.parquet")
            return cached
    rows = []
    for _, p in pts.iterrows():
        lats, lons = patch_offsets(p.lat, p.lon)
        for i in range(PATCH_N):
            for j in range(PATCH_N):
                rows.append({"id": p.id, "i": i, "j": j, "lat": lats[i, j], "lon": lons[i, j]})
    df = pd.DataFrame(rows)
    elev = []
    for start in range(0, len(df), 100):  # API accepts up to 100 points per call
        chunk = df.iloc[start:start + 100]
        res = get_json("https://api.open-meteo.com/v1/elevation", {
            "latitude": ",".join(f"{v:.6f}" for v in chunk.lat),
            "longitude": ",".join(f"{v:.6f}" for v in chunk.lon),
        })
        elev += res["elevation"]
        time.sleep(1)
    df["elevation"] = elev
    df.to_parquet(path, index=False)
    return df


def build_terrain(pts: pd.DataFrame, dem: pd.DataFrame, rivers, block: dict) -> pd.DataFrame:
    rivers_utm = transform(TO_UTM, rivers)
    bx, by = TO_UTM(block["lon"], block["lat"])
    out = []
    for _, p in pts.iterrows():
        z = dem[dem.id == p.id].sort_values(["i", "j"]).elevation.to_numpy().reshape(PATCH_N, PATCH_N)
        slope, aspect = slope_aspect(z)
        x, y = TO_UTM(p.lon, p.lat)
        out.append({
            "id": p.id,
            "elevation_m": float(z[PATCH_N // 2, PATCH_N // 2]),
            "slope_deg": round(slope, 2),
            "aspect_deg": None if np.isnan(aspect) else round(aspect, 1),
            "tpi_m": round(tpi(z), 1),
            "dist_river_km": round(Point(x, y).distance(rivers_utm) / 1000, 3),
            "dx_km": round((x - bx) / 1000, 3),   # east offset from block centroid
            "dy_km": round((y - by) / 1000, 3),   # north offset from block centroid
        })
    terrain = pd.DataFrame(out)
    terrain.to_csv(DATA / "terrain.csv", index=False)
    return terrain


# ---------------------------------------------------------------------------
# 3. Weather history: coarse block value + fine pseudo-truth
# ---------------------------------------------------------------------------
def _weather_frame(res, ids) -> pd.DataFrame:
    res = res if isinstance(res, list) else [res]
    frames = []
    for pid, r in zip(ids, res):
        d = pd.DataFrame(r["daily"]).rename(columns={"time": "date"})
        d.insert(0, "id", pid)
        d["grid_lat"], d["grid_lon"], d["grid_elev_m"] = r["latitude"], r["longitude"], r["elevation"]
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def fetch_block_history(block: dict, refresh: bool):
    path = RAW / "block_history.parquet"
    if path.exists() and not refresh:
        print("   cached: block_history.parquet")
        return
    res = get_json("https://historical-forecast-api.open-meteo.com/v1/forecast", {
        "latitude": block["lat"], "longitude": block["lon"], "elevation": "nan",
        "start_date": START_DATE, "end_date": END_DATE, "daily": ",".join(DAILY_VARS),
        "models": BLOCK_MODEL, "timezone": TZ,
    })
    df = _weather_frame(res, ["block"])
    df.to_parquet(path, index=False)
    print(f"   block history: {len(df)} days, GFS cell centre "
          f"({df.grid_lat[0]:.3f}, {df.grid_lon[0]:.3f}), cell elevation {df.grid_elev_m[0]:.0f} m")


def fetch_truth_history(pts: pd.DataFrame, refresh: bool):
    path = RAW / "truth_history.parquet"
    done = pd.read_parquet(path) if path.exists() and not refresh else None
    todo = pts if done is None else pts[~pts.id.isin(done.id)]
    if todo.empty:
        print("   cached: truth_history.parquet")
        return
    frames = [] if done is None else [done]
    for start in range(0, len(todo), 10):     # 10 locations per request
        chunk = todo.iloc[start:start + 10]
        print(f"   truth history: villages {start + 1}-{start + len(chunk)} of {len(todo)}")
        res = get_json("https://archive-api.open-meteo.com/v1/archive", {
            "latitude": ",".join(map(str, chunk.lat)), "longitude": ",".join(map(str, chunk.lon)),
            "elevation": ",".join(["nan"] * len(chunk)),
            "start_date": START_DATE, "end_date": END_DATE, "daily": ",".join(DAILY_VARS),
            "models": TRUTH_MODEL, "timezone": TZ,
        })
        frames.append(_weather_frame(res, chunk.id.tolist()))
        pd.concat(frames, ignore_index=True).to_parquet(path, index=False)  # checkpoint
        time.sleep(15)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-download everything")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    print("1/4 OpenStreetMap (boundary, villages, rivers)")
    fetch_osm(args.refresh)
    boundary = build_boundary()
    rivers = build_rivers(boundary)
    pts = build_panchayats(boundary)
    build_voronoi(pts, boundary)

    # The "block" is the taluka (= panchayat samiti block in Maharashtra); its forecast
    # is sampled at the polygon's centroid, the way a single block value is issued.
    c = boundary.centroid
    block = {"name": "Miraj", "lat": round(c.y, 5), "lon": round(c.x, 5),
             "area_km2": round(transform(TO_UTM, boundary).area / 1e6, 1)}

    print("2/4 Terrain (Copernicus DEM via Open-Meteo)")
    dem = fetch_dem(pts, args.refresh)
    build_terrain(pts, dem, rivers, block)
    block["elevation_m"] = get_json("https://api.open-meteo.com/v1/elevation",
                                    {"latitude": block["lat"], "longitude": block["lon"]})["elevation"][0]

    print(f"3/4 Block history ({BLOCK_MODEL} at centroid {block['lat']}, {block['lon']})")
    fetch_block_history(block, args.refresh)

    # Where the coarse forecast actually comes from: the GFS grid cell covering the centroid.
    bh = pd.read_parquet(RAW / "block_history.parquet")
    block["gfs_cell"] = {"lat": float(bh.grid_lat[0]), "lon": float(bh.grid_lon[0]),
                         "elevation_m": float(bh.grid_elev_m[0]), "size_deg": 0.25}

    print(f"4/4 Village truth history ({TRUTH_MODEL}, {len(pts)} points)")
    fetch_truth_history(pts, args.refresh)

    (DATA / "manifest.json").write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "block": block,
        "period": {"start": START_DATE, "end": END_DATE, "timezone": TZ},
        "variables": DAILY_VARS,
        "sources": {
            "block_value": f"Open-Meteo Historical Forecast API, model={BLOCK_MODEL}, elevation=nan "
                           "(IMD-equivalent coarse forecast proxy)",
            "truth": f"Open-Meteo Archive API, model={TRUTH_MODEL} (~9 km), elevation=nan "
                     "(pseudo ground truth; IMD AWS/ARG CSVs plug in via data/imd_import/)",
            "elevation": "Open-Meteo Elevation API (Copernicus GLO-90 DEM)",
            "villages_boundary_rivers": f"OpenStreetMap (Overpass: relation {TALUKA_RELATION_ID}; Nominatim: river relations {list(RIVER_RELATIONS.values())}), ODbL",
        },
        "counts": {"panchayats": int(len(pts))},
    }, indent=2, ensure_ascii=False))
    print("done ->", DATA / "manifest.json")


if __name__ == "__main__":
    main()

"""Terrain helpers: turn a small DEM patch around a village into slope/aspect/TPI.

Used by scripts/fetch_data.py when building data/terrain.csv, and covered by tests.
All maths is plain numpy so it can be explained on a whiteboard.
"""
from __future__ import annotations

import numpy as np

# The DEM patch fetched around every village: PATCH_N x PATCH_N points,
# PATCH_SPACING_M apart, centred on the village. 5 x 200 m covers ~800 m.
PATCH_N = 5
PATCH_SPACING_M = 200.0

M_PER_DEG_LAT = 111_320.0


def patch_offsets(lat: float, lon: float, n: int = PATCH_N, spacing_m: float = PATCH_SPACING_M):
    """Lat/lon of an n x n grid centred on (lat, lon).

    Returns two (n, n) arrays. Row 0 is the NORTHERN edge, column 0 the WESTERN
    edge, i.e. the same orientation as a map / image.
    """
    half = (n - 1) / 2
    idx = np.arange(n) - half
    dlat = spacing_m / M_PER_DEG_LAT
    dlon = spacing_m / (M_PER_DEG_LAT * np.cos(np.radians(lat)))
    lats = lat - idx[:, None] * dlat          # row 0 = north
    lons = lon + idx[None, :] * dlon          # col 0 = west
    return np.broadcast_to(lats, (n, n)).copy(), np.broadcast_to(lons, (n, n)).copy()


def slope_aspect(z: np.ndarray, spacing_m: float = PATCH_SPACING_M) -> tuple[float, float]:
    """Slope (degrees) and aspect (compass degrees the slope FACES) at the patch centre.

    Uses central differences on the 3x3 block around the centre.
    Aspect: 0 = north-facing, 90 = east-facing, 180 = south, 270 = west.
    A perfectly flat patch returns aspect NaN (it faces nowhere).
    """
    c = z.shape[0] // 2
    # Rows go north -> south, so "north minus south" gives dz/dy with y pointing north.
    dz_dx = (z[c, c + 1] - z[c, c - 1]) / (2 * spacing_m)   # rise towards east
    dz_dy = (z[c - 1, c] - z[c + 1, c]) / (2 * spacing_m)   # rise towards north
    slope = float(np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))))
    if dz_dx == 0 and dz_dy == 0:
        return slope, float("nan")
    # The slope faces downhill, i.e. along -gradient. Bearing = atan2(east, north).
    aspect = float(np.degrees(np.arctan2(-dz_dx, -dz_dy)) % 360)
    return slope, aspect


def tpi(z: np.ndarray) -> float:
    """Topographic Position Index: centre elevation minus patch mean (m).

    Positive = the village sits on a local rise; negative = in a hollow/valley.
    """
    c = z.shape[0] // 2
    return float(z[c, c] - z.mean())

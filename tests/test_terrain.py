"""Slope/aspect/TPI on synthetic DEM patches with known answers."""
import math

import numpy as np

from ml.terrain import PATCH_N, patch_offsets, slope_aspect, tpi

SP = 200.0  # metres between patch points


def plane(east_rise_per_m=0.0, north_rise_per_m=0.0):
    """A tilted plane on the patch grid (row 0 = north, col 0 = west)."""
    idx = np.arange(PATCH_N) - PATCH_N // 2
    x = idx[None, :] * SP          # metres east
    y = -idx[:, None] * SP         # metres north (row 0 is north)
    return 500 + east_rise_per_m * x + north_rise_per_m * y


def test_flat_patch_has_zero_slope_and_no_aspect():
    slope, aspect = slope_aspect(np.full((PATCH_N, PATCH_N), 600.0))
    assert slope == 0
    assert math.isnan(aspect)


def test_ground_rising_to_the_east_faces_west():
    slope, aspect = slope_aspect(plane(east_rise_per_m=0.01))   # 1 m per 100 m
    assert math.isclose(slope, math.degrees(math.atan(0.01)), rel_tol=1e-9)
    assert math.isclose(aspect, 270.0)


def test_ground_rising_to_the_north_faces_south():
    _, aspect = slope_aspect(plane(north_rise_per_m=0.02))
    assert math.isclose(aspect, 180.0)


def test_tpi_sign():
    z = np.full((PATCH_N, PATCH_N), 600.0)
    z[PATCH_N // 2, PATCH_N // 2] = 625.0
    assert tpi(z) > 0          # a local hilltop
    assert tpi(-z) < 0         # a hollow


def test_patch_orientation_and_spacing():
    lats, lons = patch_offsets(16.8, 74.6)
    c = PATCH_N // 2
    assert (lats[0, c], lons[c, c]) == (lats[0, c], 74.6)
    assert lats[0, c] > lats[-1, c]            # row 0 is north
    assert lons[c, 0] < lons[c, -1]            # col 0 is west
    assert math.isclose((lats[0, c] - lats[1, c]) * 111_320, SP, rel_tol=1e-9)

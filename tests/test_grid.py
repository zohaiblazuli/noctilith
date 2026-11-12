import numpy as np
import pytest

from server.grid import make_grid_wcs, sky_to_pixel


def test_grid_size():
    assert make_grid_wcs(150, 2.2, 0.1)[1] == 59


def test_center_maps_to_middle():
    wcs, n = make_grid_wcs(150, 2.2, 0.1)
    x, y = sky_to_pixel(wcs, np.array([150.0]), np.array([2.2]))
    assert x[0] == pytest.approx((n - 1) / 2, abs=0.01)
    assert y[0] == pytest.approx((n - 1) / 2, abs=0.01)


def test_east_is_left():
    wcs, n = make_grid_wcs(150, 2.2, 0.1)
    x, _ = sky_to_pixel(wcs, np.array([150.01]), np.array([2.2]))
    assert x[0] < (n - 1) / 2


def test_ra_wrap():
    wcs, n = make_grid_wcs(359.99, 0.0, 0.1)
    x, y = sky_to_pixel(wcs, np.array([0.005]), np.array([0.0]))
    assert x[0] < (n - 1) / 2
    assert 0 <= x[0] < n and 0 <= y[0] < n


def test_near_pole():
    wcs, n = make_grid_wcs(10.0, 89.9, 0.1)
    _, y = sky_to_pixel(wcs, np.array([10.0]), np.array([89.92]))
    assert y[0] > (n - 1) / 2

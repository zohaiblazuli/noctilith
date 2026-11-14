import numpy as np

from server.junk import fill_junk, junk_mask

TRANSIENT, OVERFLOW, SUR_ERROR, NONFUNC, OUTLIER = 1 << 0, 1 << 1, 1 << 2, 1 << 6, 1 << 19


def test_cosmic_ray_and_dead_pixel_are_filled_from_neighbours():
    img = np.full((5, 5), 10.0, np.float32)
    img[1, 1], img[3, 3] = 5000.0, -800.0
    flags = np.zeros((5, 5), np.int64)
    flags[1, 1], flags[3, 3] = TRANSIENT | SUR_ERROR, NONFUNC
    out = fill_junk(img, flags)
    assert out[1, 1] == 10.0 and out[3, 3] == 10.0
    assert img[1, 1] == 5000.0  # input untouched


def test_overflow_cores_and_outliers_are_left_alone():
    img = np.full((3, 3), 10.0, np.float32)
    img[1, 1] = 900.0
    for f in (OVERFLOW | SUR_ERROR, OUTLIER, 1 << 21):  # bright core, outlier, SOURCE
        flags = np.zeros((3, 3), np.int64)
        flags[1, 1] = f
        assert fill_junk(img, flags)[1, 1] == 900.0


def test_isolated_cluster_keeps_original_value_and_nan_flags_are_ok():
    img = np.arange(9, dtype=np.float32).reshape(3, 3)
    flags = np.full((3, 3), float(NONFUNC))  # everything junk: no good neighbour anywhere
    flags[0, 0] = np.nan
    out = fill_junk(img, flags)
    assert not junk_mask(flags)[0, 0]       # NaN flag = no flag
    assert out[1, 1] == 0.0                 # its one good neighbour is the unflagged corner
    for y, x in ((1, 2), (2, 1), (2, 2)):   # no good neighbour: original value kept
        assert out[y, x] == img[y, x]

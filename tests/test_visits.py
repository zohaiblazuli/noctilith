import io

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from PIL import Image

from server.overview import render
from server.sia import FrameMeta
from server.visits import NO_DATA, pick_visit_frames, render_window, tan_grid, visit_groups, window_for


def _f(mjd, det, center=(10.0, 40.0)):
    return FrameMeta(obs_id=f"o{mjd}", detector=det, mjd=mjd, iso="x", access_url="u",
                     band_um=(1, 2), center=center)


def test_visit_groups_match_the_browser_rule():
    frames = [_f(100, 1), _f(100.04, 2), _f(102, 1), _f(102.4, 1), _f(102.8, 1), _f(103.2, 1)]
    # 12 h gap splits 100 from 102; gaps of 0.4 d keep 102..102.8 together, but 103.2 is
    # 1.2 d after that visit started, so the 1-day cap starts a new visit
    assert [len(g) for g in visit_groups(frames)] == [2, 3, 1]


def test_pick_visit_frames_uses_one_detector_and_the_best_centred_frame():
    frames = [
        _f(100.0, 2, (10.5, 40.0)), _f(100.1, 1, (10.9, 40.0)), _f(100.2, 1, (10.1, 40.0)),  # visit 1
        _f(105.0, 1, (10.2, 40.0)), _f(105.1, 2, (10.0, 40.0)),                              # visit 2
        _f(110.0, 4, (10.0, 40.0)),                                                          # visit 3: no D1/D2
    ]
    picks = pick_visit_frames(frames, 10.0, 40.0)
    assert [(p.mjd, p.detector) for p in picks] == [(100.2, 1), (105.0, 1), (110.0, 4)]


def test_visit_window_lines_up_pixel_for_pixel_with_the_wide_view():
    h = fits.open("tests/fixtures/cutout_small.fits")["IMAGE"]
    img = np.zeros(h.data.shape, np.float32)
    img[8, 20] = 1000  # one bright "star" off-centre
    sky = WCS(h.header).celestial
    _, info = render(img, h.header)
    ra, dec = (float(v) for v in sky.pixel_to_world_values(20, 8))
    wx, wy = (float(v) for v in tan_grid(info).world_to_pixel_values(ra, dec))  # star on the wide grid

    centre = sky.pixel_to_world_values(14, 14)
    x0, y0, m = window_for(info, float(centre[0]), float(centre[1]), 0.04)
    arr = np.asarray(Image.open(io.BytesIO(render_window(img, sky, info, x0, y0, m))))
    row, col = np.unravel_index(np.argmax(arr), arr.shape)
    assert abs(col - (wx - x0)) <= 1.0 and abs((m - 1 - row) - (wy - y0)) <= 1.0
    assert arr[0, 0] == NO_DATA and arr[-1, -1] == NO_DATA  # outside the detector: opaque dark grey, not transparent

"""The shared target grid: north up, east left, SPHEREx pixel scale, centred on the target."""
import numpy as np
from astropy.wcs import WCS

from server.config import SETTINGS


def make_grid_wcs(ra: float, dec: float, fov: float) -> tuple[WCS, int]:
    p = SETTINGS.pixel_arcsec / 3600.0
    n = int(round(fov / p))
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.cdelt = [-p, p]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    return w, n


def sky_to_pixel(wcs: WCS, ra: np.ndarray, dec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x, y = wcs.world_to_pixel_values(np.asarray(ra, float), np.asarray(dec, float))
    return np.asarray(x), np.asarray(y)

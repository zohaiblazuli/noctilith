"""Fetch SPHEREx cutouts from IRSA (limited concurrency, retries) and reproject them onto the target grid."""
import asyncio
import base64
import io
import logging
import warnings

import httpx
import numpy as np
from astropy.io import fits
from astropy.utils.exceptions import AstropyWarning
from astropy.wcs import WCS
from reproject import reproject_interp

from server import cache
from server.grid import make_grid_wcs, sky_to_pixel
from server.junk import fill_junk

log = logging.getLogger(__name__)

# FLAGS bits (from the FLAGS header) that make a pixel unusable for analysis (it is still drawn).
# 22-28 = GHOST, GHOST_FPA, GHOST_EXT, STREAK, BLOOM, SNOWBALL, HALO (as IRSA's notebooks do).
# Informational: dichroic (7), full-sample (12), phantom-not-applied (14), SOURCE (21), and
# CROSSTALK (20), which blankets ~70% of pixels near bright objects like M31's core.
BAD_BITS = (0, 1, 2, 4, 5, 6, 9, 10, 11, 15, 17, 19, 22, 23, 24, 25, 26, 27, 28)
BAD_MASK = sum(1 << b for b in BAD_BITS)
MIN_COVERAGE = 0.5
BACKOFF_S = (2, 4)  # 3 attempts: a dead IRSA greys a tile in ~1 min, not ~5
TIMEOUT_S = 25
CUTOUT_MARGIN = 1.5  # cutout bigger than fov so rotated frames still fill the grid


class CutoutError(Exception):
    pass


async def fetch_cutout(client: httpx.AsyncClient, access_url: str, ra: float, dec: float,
                       fov: float, sem: asyncio.Semaphore) -> bytes:
    url = f"{access_url}?center={ra},{dec}&size={round(fov * CUTOUT_MARGIN, 6)}deg"
    last = None
    for attempt in range(len(BACKOFF_S) + 1):
        try:
            async with sem:
                r = await client.get(url, timeout=TIMEOUT_S)
            if r.status_code == 200:
                return r.content
            last = f"HTTP {r.status_code}"
            if r.status_code < 500:
                break
        except httpx.HTTPError as e:
            last = repr(e)
        if attempt < len(BACKOFF_S):
            await asyncio.sleep(BACKOFF_S[attempt])
    raise CutoutError(f"cutout failed ({last}): {url}")


def _b64(a: np.ndarray, dtype) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode()


def process_cutout(fits_bytes, ra: float, dec: float, fov: float) -> dict | None:
    """fits_bytes: raw FITS bytes, or an already-built HDUList (see server.slicer)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AstropyWarning)
        logging.getLogger("astropy").setLevel(logging.ERROR)
        hdul = fits_bytes if isinstance(fits_bytes, fits.HDUList) else fits.open(io.BytesIO(fits_bytes))
        hdr = hdul["IMAGE"].header
        sky = WCS(hdr)
        grid, n = make_grid_wcs(ra, dec, fov)

        # NASA-flagged junk is painted over on the detector, before reprojection smears it around;
        # the raw values travel along as a small patch so the page can show them on request
        raw_det = hdul["IMAGE"].data.astype(float)
        img, foot = reproject_interp((fill_junk(raw_det, hdul["FLAGS"].data), sky), grid, shape_out=(n, n))
        raw, _ = reproject_interp((raw_det, sky), grid, shape_out=(n, n))
        var, _ = reproject_interp((hdul["VARIANCE"].data.astype(float), sky), grid, shape_out=(n, n))
        flags, _ = reproject_interp((hdul["FLAGS"].data.astype(float), sky), grid, shape_out=(n, n), order=0)

        coverage = float(np.mean((foot > 0) & np.isfinite(img)))
        if coverage < MIN_COVERAGE:
            return None

        x, y = sky_to_pixel(sky, np.array([ra]), np.array([dec]))
        try:
            wave = WCS(hdr, fobj=hdul, key="W")
            lam = float(np.atleast_1d(wave.pixel_to_world_values(x[0], y[0]))[0])
        except Exception:  # pragma: no cover - fall back to header-free value
            lam = float("nan")

    flags_i = np.nan_to_num(flags, nan=0).astype(np.int64)
    bad = (~np.isfinite(img)) | ((flags_i & BAD_MASK) != 0)
    bg = float(np.nanmedian(img[~bad])) if (~bad).any() else 0.0
    img, raw = img - bg, raw - bg
    raw_idx = np.flatnonzero(np.isfinite(raw) & np.isfinite(img) & (raw != img))
    sigma = np.sqrt(np.clip(var, 0, None))

    return {
        "n": n,
        "mjd": float(hdr.get("MJD-AVG") or hdr.get("MJD-OBS")),
        "wavelength_um": lam,
        "image": _b64(img, "<f4"),
        "sigma": _b64(sigma, "<f4"),
        "bad": _b64(bad, "u1"),
        "raw_idx": _b64(raw_idx, "<i4"),
        "raw_val": _b64(raw.ravel()[raw_idx], "<f4"),
        "coverage": coverage,
    }


async def get_frame(client: httpx.AsyncClient, meta, ra: float, dec: float, fov: float,
                    sem: asyncio.Semaphore) -> dict | None:
    k = cache.key("frame-v4", meta.id, round(ra, 5), round(dec, 5), fov)
    hit = cache.get_json(k)
    if hit is not None:
        return hit.get("payload")
    from server import slicer  # lazy: slicer imports process_cutout from here
    payload, done = None, False
    mirror = slicer.mirror_url(meta.access_url)
    if mirror:  # fast path: read only the needed rows from NASA's AWS copy
        try:
            payload, done = await slicer.slice_payload(client, mirror, ra, dec, fov, sem), True
        except Exception as e:  # any trouble -> fall back to IRSA's cutout service
            log.info("mirror slice failed for %s: %r", meta.id, e)
    if not done:
        data = await fetch_cutout(client, meta.access_url, ra, dec, fov, sem)
        payload = await asyncio.to_thread(process_cutout, data, ra, dec, fov)
    if payload is not None:
        payload["id"] = meta.id
    cache.put_json(k, {"payload": payload})  # cache "no coverage" too
    return payload

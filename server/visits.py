"""Wide-view animation: one image per visit, cut out on the exact pixel grid of the wide view.

Same grid as the wide image (same tangent point, pixel size and north-up layout), so the browser
can draw each visit image on top of it pixel for pixel and the user can zoom while it plays.
Only the IMAGE rows covering the window are fetched (~7 MB per visit for 1 degree).
"""
import asyncio
import io
import math
import warnings

import httpx
import numpy as np
from astropy.utils.exceptions import AstropyWarning
from astropy.wcs import WCS
from PIL import Image
from reproject import reproject_interp

from server import cache, slicer
from server.config import SETTINGS
from server.junk import fill_junk
from server.overview import PREFERRED_DETECTORS, _sep_deg, stretch_u8

VISIT_GAP_D = 0.5   # must match web/logic.js visitGroups
VISIT_MAX_D = 1.0
TIMEOUT_S = 120
NO_DATA = 10        # grey level for "this visit's frame doesn't reach here" (opaque, so the static
                    # wide image underneath never passes for data from this visit)
_inflight: dict[str, asyncio.Task] = {}


class VisitError(Exception):
    pass


def visit_groups(frames) -> list[list]:
    """Frames grouped into visits: a new visit after a 12 h gap or after 1 day."""
    out, start, prev = [], None, None
    for f in sorted(frames, key=lambda f: f.mjd):
        if not out or f.mjd - prev > VISIT_GAP_D or f.mjd - start > VISIT_MAX_D:
            out.append([])
            start = f.mjd
        out[-1].append(f)
        prev = f.mjd
    return out


def pick_visit_frames(frames, ra: float, dec: float) -> list:
    """One frame per visit, from the same detector where possible (less colour flicker),
    the one whose centre is nearest the window centre."""
    groups = visit_groups(frames)
    counts = {d: sum(any(f.detector == d for f in g) for g in groups) for d in PREFERRED_DETECTORS}
    det = max(PREFERRED_DETECTORS, key=lambda d: (counts[d], -d))

    def dist(f):
        return _sep_deg(f.center, ra, dec) if f.center else 99

    picks = []
    for g in groups:
        same = [f for f in g if f.detector == det]
        picks.append(min(same or g, key=dist))
    return picks


def tan_grid(info: dict, x0: int = 0, y0: int = 0) -> WCS:
    """The wide view's TAN grid (see server/overview.py render), optionally shifted to a window."""
    n, p = info["n"], info["pixel_deg"]
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [info["ra0"], info["dec0"]]
    w.wcs.cdelt = [-p, p]
    w.wcs.crpix = [(n + 1) / 2 - x0, (n + 1) / 2 - y0]
    return w


def window_for(info: dict, ra: float, dec: float, size_deg: float) -> tuple[int, int, int]:
    """Square window (x0, y0, m) of wide-grid pixels, size_deg across, centred on ra/dec."""
    tx, ty = tan_grid(info).world_to_pixel_values(ra, dec)
    half = int(round(size_deg / info["pixel_deg"] / 2))
    return int(round(float(tx))) - half, int(round(float(ty))) - half, 2 * half + 1


def render_window(img: np.ndarray, sky: WCS, info: dict, x0: int, y0: int, m: int) -> bytes:
    """Reproject detector pixels onto the window of the wide grid; PNG (north up), no-data dark."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AstropyWarning)
        out, foot = reproject_interp((img, sky), tan_grid(info, x0, y0), shape_out=(m, m))
    out[foot <= 0] = np.nan
    gray = stretch_u8(out)
    gray[~np.isfinite(out)] = NO_DATA
    png = io.BytesIO()
    Image.fromarray(np.flipud(gray), "L").save(png, format="PNG", compress_level=6)
    return png.getvalue()


def png_path(frame_id: str, info: dict, x0: int, y0: int, m: int, raw: bool = False):
    k = cache.key("visit-v2", frame_id, round(info["ra0"], 6), round(info["dec0"], 6), info["n"], x0, y0, m)
    return SETTINGS.cache_dir / "visits" / f"{k}{'-raw' if raw else ''}.png"


async def _fetch_rows(client, meta, ra, dec, size_deg):
    url = slicer.mirror_url(meta.access_url)
    if not url:
        raise VisitError("frame is not on the public mirror")
    lay = await slicer.read_layout(client, url)
    hdr, off, _ = lay["IMAGE"]
    box = slicer._bbox(hdr, ra, dec, size_deg)
    if box is None:
        return None, None, None
    x0, x1, y0, y1 = box
    width = hdr["NAXIS1"]
    start, nbytes = off + y0 * width * 4, (y1 - y0) * width * 4
    r = await client.get(url, headers={"Range": f"bytes={start}-{start + nbytes - 1}"}, timeout=TIMEOUT_S)
    if r.status_code != 206 or len(r.content) != nbytes:
        raise VisitError(f"HTTP {r.status_code}, {len(r.content)} bytes")
    rows = np.frombuffer(r.content, ">f4").reshape(y1 - y0, width)[:, x0:x1].astype(np.float32)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AstropyWarning)
        sky = WCS(slicer._shift(hdr, x0, y0, x1 - x0, y1 - y0)).celestial
    fh, foff, _ = lay["FLAGS"]
    try:  # NASA's quality flags for the same rows (tile-compressed in DR1)
        flags, _ = await slicer._compressed_rows(client, url, fh, foff, y0, y1) if fh.get("ZIMAGE") else (None, None)
        clean = rows if flags is None else fill_junk(rows, flags[:, x0:x1])
    except Exception:  # display nicety only; never block a visit on it
        clean = rows
    return clean, rows, sky


async def _build(client, meta, info, ra, dec, size_deg, window, sem):
    x0, y0, m = window
    async with sem:
        clean, raw, sky = await _fetch_rows(client, meta, ra, dec, size_deg)
    if clean is None:
        raise VisitError("frame does not reach this area")
    pngs = await asyncio.gather(asyncio.to_thread(render_window, raw, sky, info, x0, y0, m),
                                asyncio.to_thread(render_window, clean, sky, info, x0, y0, m))
    for is_raw, data in zip((True, False), pngs):  # clean last: its file marks the pair as done
        pth = png_path(meta.id, info, x0, y0, m, raw=is_raw)
        pth.parent.mkdir(parents=True, exist_ok=True)
        tmp = pth.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(pth)


async def get_visit_png(client: httpx.AsyncClient, meta, info: dict, ra: float, dec: float,
                        size_deg: float, sem: asyncio.Semaphore, raw: bool = False):
    """Path to the cached PNG of one visit's frame on the wide-grid window around ra/dec
    (raw=True: NASA-flagged junk left in). Both versions are built together."""
    window = window_for(info, ra, dec, size_deg)
    done = png_path(meta.id, info, *window)
    if not done.exists():
        key = str(done)
        task = _inflight.get(key)
        if task is None:
            task = _inflight[key] = asyncio.create_task(_build(client, meta, info, ra, dec, size_deg, window, sem))
            task.add_done_callback(lambda _t: _inflight.pop(key, None))
        await task
    return png_path(meta.id, info, *window, raw=raw)


def visit_size_ok(size_deg: float) -> bool:
    return 0.1 <= size_deg <= 1.5 and math.isfinite(size_deg)

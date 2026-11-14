"""Read just the needed rows of a full SPHEREx image with HTTP byte-range requests.

Why: IRSA's cutout service always bundles a ~5 MB PSF cube, so on a ~3 MB/s link each
frame costs ~2 s of pure download plus ~10 s of server time. The full images are also on
NASA's public AWS bucket; reading only the rows we need is ~3x fewer bytes and no queue.
The result goes through the same process_cutout() as a normal cutout.
"""
import asyncio
import io
import logging
import warnings

import httpx
import numpy as np
from astropy.io import fits
from astropy.utils.exceptions import AstropyWarning
from astropy.wcs import WCS

from server.cutout import process_cutout
from server.grid import make_grid_wcs

IRSA_PREFIX = "https://irsa.ipac.caltech.edu/ibe/data/spherex/"
S3_PREFIX = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/"
BLOCK = 2880
HDR_CHUNK = 10 * BLOCK      # most SPHEREx headers fit in one read
WANTED = ("IMAGE", "FLAGS", "VARIANCE")
MAX_HDUS = 8
EDGE_PX = 3                 # extra pixels around the grid footprint for interpolation
TIMEOUT_S = 25


class SliceError(Exception):
    pass


def mirror_url(access_url: str) -> str | None:
    return S3_PREFIX + access_url[len(IRSA_PREFIX):] if access_url.startswith(IRSA_PREFIX) else None


async def _range(client: httpx.AsyncClient, url: str, start: int, n: int) -> bytes:
    r = await client.get(url, headers={"Range": f"bytes={start}-{start + n - 1}"}, timeout=TIMEOUT_S)
    if r.status_code == 206:
        return r.content
    if r.status_code == 200:  # server ignored Range
        return r.content[start:start + n]
    if r.status_code == 416:
        return b""
    raise SliceError(f"HTTP {r.status_code}")


def _end_card(buf: bytes) -> int:
    """Byte index just past the END card, or -1."""
    for i in range(0, len(buf) - 79, 80):
        if buf[i:i + 8] == b"END     ":
            return i + 80
    return -1


def _data_bytes(h: fits.Header) -> int:
    naxis = h.get("NAXIS", 0)
    if not naxis:
        return 0
    n = int(np.prod([h[f"NAXIS{i}"] for i in range(1, naxis + 1)]))
    return abs(h["BITPIX"]) // 8 * h.get("GCOUNT", 1) * (h.get("PCOUNT", 0) + n)


def _pad(n: int) -> int:
    return -(-n // BLOCK) * BLOCK


async def read_layout(client, url) -> dict:
    """EXTNAME -> (header, data_offset, data_nbytes), walking headers until WCS-WAVE."""
    out, off = {}, 0
    for _ in range(MAX_HDUS):
        buf = await _range(client, url, off, HDR_CHUNK)
        while (end := _end_card(buf)) < 0:
            more = await _range(client, url, off + len(buf), HDR_CHUNK)
            if not more:
                raise SliceError("no END card")
            buf += more
        if not buf:
            break
        h = fits.Header.fromstring(buf[:end].decode("ascii"))
        name = h.get("EXTNAME", "PRIMARY")
        data_off = off + _pad(end)
        out[name] = (h, data_off, _data_bytes(h))
        if name == "WCS-WAVE":
            break
        off = data_off + _pad(out[name][2])
    missing = [k for k in (*WANTED, "WCS-WAVE") if k not in out]
    if missing:
        raise SliceError(f"missing HDUs {missing}")
    return out


def _bbox(img_hdr, ra, dec, fov):
    """Detector pixel box (x0, x1, y0, y1), end-exclusive, covering the target grid, or None."""
    grid, n = make_grid_wcs(ra, dec, fov)
    t = np.linspace(-0.5, n - 0.5, 9)
    gx = np.concatenate([t, t, np.full(9, -0.5), np.full(9, n - 0.5)])
    gy = np.concatenate([np.full(9, -0.5), np.full(9, n - 0.5), t, t])
    sra, sdec = grid.pixel_to_world_values(gx, gy)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AstropyWarning)
        x, y = WCS(img_hdr).world_to_pixel_values(sra, sdec)
    nx, ny = img_hdr["NAXIS1"], img_hdr["NAXIS2"]
    x0 = max(int(np.floor(np.nanmin(x))) - EDGE_PX, 0)
    x1 = min(int(np.ceil(np.nanmax(x))) + EDGE_PX + 1, nx)
    y0 = max(int(np.floor(np.nanmin(y))) - EDGE_PX, 0)
    y1 = min(int(np.ceil(np.nanmax(y))) + EDGE_PX + 1, ny)
    return None if x1 <= x0 or y1 <= y0 else (x0, x1, y0, y1)


async def _compressed_rows(client, url, h: fits.Header, off: int, y0: int, y1: int):
    """Rows y0..y1 of a tile-compressed image HDU (DR1 ships FLAGS this way: RICE, one tile per row).

    Reads only those rows' tile pointers and their part of the heap, wraps them in a small
    FITS file and lets astropy decompress it. Returns (data, image-style header).
    """
    if (h.get("TFIELDS") != 1 or not str(h.get("TFORM1", "")).startswith("1P")
            or h.get("ZTILE2", 1) != 1 or h.get("ZTILE1") != h["ZNAXIS1"]):
        raise SliceError("unsupported compressed layout")  # caller falls back to IRSA cutout
    ny, rowlen = y1 - y0, h["NAXIS1"]
    desc = np.frombuffer(await _range(client, url, off + y0 * rowlen, ny * rowlen), ">i4").reshape(ny, 2)
    count, start = desc[:, 0].astype(np.int64), desc[:, 1].astype(np.int64)
    lo, hi = int(start.min()), int((start + count).max())
    theap = h.get("THEAP", rowlen * h["NAXIS2"])
    heap = await _range(client, url, off + theap + lo, hi - lo)

    hh = h.copy()
    hh["NAXIS2"], hh["ZNAXIS2"], hh["PCOUNT"] = ny, ny, hi - lo
    for k in ("THEAP", "CHECKSUM", "DATASUM", "ZHECKSUM", "ZDATASUM"):
        hh.remove(k, ignore_missing=True)
    body = np.stack([count, start - lo], axis=1).astype(">i4").tobytes() + heap
    blob = io.BytesIO()
    fits.PrimaryHDU().writeto(blob)
    blob.write(hh.tostring().encode("ascii") + body.ljust(_pad(len(body)), b"\0"))
    blob.seek(0)
    with fits.open(blob) as small:
        return np.array(small[1].data), small[1].header.copy()


def _shift(h: fits.Header, x0: int, y0: int, nx: int, ny: int) -> fits.Header:
    h = h.copy()
    for k in list(h.keys()):
        if k.startswith("CRPIX1"):
            h[k] -= x0
        elif k.startswith("CRPIX2"):
            h[k] -= y0
    h["NAXIS1"], h["NAXIS2"] = nx, ny
    return h


async def slice_hdul(client, url, ra, dec, fov) -> fits.HDUList | None:
    lay = await read_layout(client, url)
    img_hdr = lay["IMAGE"][0]
    box = _bbox(img_hdr, ra, dec, fov)
    if box is None:
        return None
    x0, x1, y0, y1 = box
    width = img_hdr["NAXIS1"]

    async def rows(name):
        h, off, _ = lay[name]
        if h.get("ZIMAGE"):
            data, h = await _compressed_rows(client, url, h, off, y0, y1)
            return data[:, x0:x1], h
        bpp = abs(h["BITPIX"]) // 8
        raw = await _range(client, url, off + y0 * width * bpp, (y1 - y0) * width * bpp)
        dt = {-32: ">f4", -64: ">f8", 32: ">i4", 16: ">i2", 8: "u1"}[h["BITPIX"]]
        return np.frombuffer(raw, dt).reshape(y1 - y0, width)[:, x0:x1], h

    h, off, nb = lay["WCS-WAVE"]
    *planes, table = await asyncio.gather(*[rows(n) for n in WANTED], _range(client, url, off, nb))
    hdus = [fits.PrimaryHDU(header=lay["PRIMARY"][0] if "PRIMARY" in lay else None)]
    for name, (data, hdr) in zip(WANTED, planes):
        hh = _shift(hdr, x0, y0, x1 - x0, y1 - y0)
        hdus.append(fits.ImageHDU(data=np.array(data), header=hh, name=name))
    hdus.append(fits.BinTableHDU.fromstring(h.tostring().encode("ascii") + table.ljust(_pad(nb), b"\0")))
    return fits.HDUList(hdus)


async def slice_payload(client, access_url, ra, dec, fov, sem) -> dict | None:
    """Same payload as process_cutout(), built from byte ranges. Raises SliceError/HTTPError on trouble."""
    async with sem:
        hdul = await slice_hdul(client, access_url, ra, dec, fov)
    if hdul is None:
        return None
    logging.getLogger("astropy").setLevel(logging.ERROR)
    return await asyncio.to_thread(process_cutout, hdul, ra, dec, fov)

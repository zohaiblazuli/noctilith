import asyncio
import base64
from pathlib import Path

import httpx
import numpy as np
from astropy.io import fits

from server.cutout import process_cutout
from server.slicer import mirror_url, read_layout, slice_payload

FIX = Path(__file__).parent / "fixtures"
FITS_BYTES = (FIX / "cutout_small.fits").read_bytes()


def _range_client(blob: bytes, log: list | None = None):
    def handler(request):
        a, b = request.headers["Range"].removeprefix("bytes=").split("-")
        a, b = int(a), min(int(b), len(blob) - 1)
        if log is not None:
            log.append(b - a + 1)
        if a >= len(blob):
            return httpx.Response(416)
        return httpx.Response(206, content=blob[a:b + 1])
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _f32(b64):
    return np.frombuffer(base64.b64decode(b64), dtype="<f4")


def test_mirror_url_maps_irsa_to_s3():
    u = "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/X/f.fits"
    assert mirror_url(u) == "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/qr2/level2/X/f.fits"
    assert mirror_url("https://elsewhere/f.fits") is None


def test_read_layout_finds_hdus_and_offsets():
    async def run():
        async with _range_client(FITS_BYTES) as c:
            return await read_layout(c, "https://x/f.fits")
    lay = asyncio.run(run())
    assert {"IMAGE", "FLAGS", "VARIANCE", "WCS-WAVE"} <= set(lay)
    ref = fits.open("tests/fixtures/cutout_small.fits")
    hdr, off, _ = lay["FLAGS"]
    raw = np.frombuffer(FITS_BYTES[off:off + 29 * 29 * 4], ">i4").reshape(29, 29)
    assert np.array_equal(raw, ref["FLAGS"].data)


def test_slice_matches_cutout_path():
    log = []

    async def run():
        async with _range_client(FITS_BYTES, log) as c:
            return await slice_payload(c, "https://x/f.fits", 150.0, 2.2, 0.03, asyncio.Semaphore(4))
    p = asyncio.run(run())
    ref = process_cutout(FITS_BYTES, 150.0, 2.2, 0.03)
    assert p["n"] == ref["n"]
    assert abs(p["wavelength_um"] - ref["wavelength_um"]) < 1e-6
    assert p["mjd"] == ref["mjd"]
    np.testing.assert_allclose(_f32(p["image"]), _f32(ref["image"]), rtol=1e-5, atol=1e-6, equal_nan=True)
    np.testing.assert_allclose(_f32(p["sigma"]), _f32(ref["sigma"]), rtol=1e-5, equal_nan=True)
    assert p["bad"] == ref["bad"]


def test_slice_outside_detector_is_none():
    async def run():
        async with _range_client(FITS_BYTES) as c:
            return await slice_payload(c, "https://x/f.fits", 151.0, 2.2, 0.03, asyncio.Semaphore(4))
    assert asyncio.run(run()) is None


def _meta():
    from server.sia import FrameMeta
    return FrameMeta(obs_id="T1", detector=5, mjd=60800.0, iso="", band_um=4.0, burst=0,
                     access_url="https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/x.fits")


def test_get_frame_prefers_mirror_then_falls_back(monkeypatch, tmp_path):
    from server import cache, cutout, slicer
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path, raising=False)
    monkeypatch.setattr(cache.SETTINGS, "cache_dir", tmp_path, raising=False)
    seen = []

    async def ok_slice(client, url, *a):
        seen.append(url)
        return {"n": 1}
    monkeypatch.setattr(slicer, "slice_payload", ok_slice)
    p = asyncio.run(cutout.get_frame(None, _meta(), 150.0, 2.2, 0.1, asyncio.Semaphore(2)))
    assert p["n"] == 1 and seen[0].startswith(slicer.S3_PREFIX)

    async def bad_slice(*a):
        raise slicer.SliceError("boom")

    async def fake_cutout(*a):
        return FITS_BYTES
    monkeypatch.setattr(slicer, "slice_payload", bad_slice)
    monkeypatch.setattr(cutout, "fetch_cutout", fake_cutout)
    p = asyncio.run(cutout.get_frame(None, _meta(), 150.0, 2.2, 0.03, asyncio.Semaphore(2)))
    assert p["n"] == 18

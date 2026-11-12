import asyncio
import base64
from pathlib import Path

import httpx
import numpy as np
import pytest

from server import cutout
from server.cutout import CutoutError, fetch_cutout, process_cutout

FIX = Path(__file__).parent / "fixtures"
FITS_BYTES = (FIX / "cutout_small.fits").read_bytes()


def _f32(b64):
    return np.frombuffer(base64.b64decode(b64), dtype="<f4")


def test_process_fixture():
    # fixture is a 0.05 deg, rotated cutout, so use a 0.03 deg grid that sits fully inside it
    p = process_cutout(FITS_BYTES, 150.0, 2.2, 0.03)
    assert p["n"] == 18
    assert 3.8 < p["wavelength_um"] < 5.0  # fixture is detector D5
    assert p["coverage"] > 0.9
    img = _f32(p["image"])
    assert img.size == 18 * 18
    assert abs(np.nanmedian(img)) < 1e-3
    assert _f32(p["sigma"]).size == 18 * 18
    assert len(base64.b64decode(p["bad"])) == 18 * 18
    assert p["mjd"] > 60000


def test_low_coverage_returns_none():
    assert process_cutout(FITS_BYTES, 150.1, 2.2, 0.03) is None


def _client(responses):
    calls = {"n": 0}

    def handler(request):
        r = responses[min(calls["n"], len(responses) - 1)]
        calls["n"] += 1
        return r

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def fake_sleep(_):
        return None
    monkeypatch.setattr(cutout.asyncio, "sleep", fake_sleep)


def test_retry_then_success():
    client, calls = _client([httpx.Response(503), httpx.Response(503), httpx.Response(200, content=b"ok")])

    async def run():
        async with client:
            return await fetch_cutout(client, "https://x/f.fits", 150, 2.2, 0.1, asyncio.Semaphore(6))

    assert asyncio.run(run()) == b"ok"
    assert calls["n"] == 3


def test_retry_exhausted():
    client, _ = _client([httpx.Response(503)])

    async def run():
        async with client:
            return await fetch_cutout(client, "https://x/f.fits", 150, 2.2, 0.1, asyncio.Semaphore(6))

    with pytest.raises(CutoutError):
        asyncio.run(run())


def test_cutout_url_has_margin():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, content=b"ok")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            await fetch_cutout(c, "https://x/f.fits", 150.0, 2.2, 0.1, asyncio.Semaphore(6))

    asyncio.run(run())
    assert "center=150.0,2.2" in seen["url"]
    assert "size=0.15deg" in seen["url"]

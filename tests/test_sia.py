import asyncio
from pathlib import Path

import httpx
import pytest

from server.sia import FrameMeta, assign_bursts, parse_sia_csv, query_frames

FIX = Path(__file__).parent / "fixtures"


def test_parse_fixture():
    frames = parse_sia_csv((FIX / "sia_sample.csv").read_text())
    assert len(frames) == 5
    assert [f.mjd for f in frames] == sorted(f.mjd for f in frames)
    f = frames[0]
    assert f.detector == 2
    assert f.id == f"{f.obs_id}D2"
    assert f.access_url.startswith("https://irsa.ipac.caltech.edu/ibe/")
    assert f.band_um == pytest.approx((1.1033, 1.6499), abs=1e-4)


def _meta(mjd):
    return FrameMeta(obs_id="x", detector=1, mjd=mjd, iso="", access_url="", band_um=(1.0, 2.0), burst=-1)


def test_bursts():
    frames = [_meta(m) for m in [0, 0.1, 1.5, 180, 181]]
    bursts = assign_bursts(frames)
    assert [f.burst for f in frames] == [0, 0, 0, 1, 1]
    assert [b["count"] for b in bursts] == [3, 2]


def test_empty_csv():
    header = (FIX / "sia_sample.csv").read_text().splitlines()[0] + "\n"
    assert parse_sia_csv(header) == []


def test_query_url():
    seen = {}

    def handler(request):
        seen["url"] = request.url
        return httpx.Response(200, text=(FIX / "sia_sample.csv").read_text())

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await query_frames(c, 150.0, 2.2, 0.1)

    frames = asyncio.run(run())
    q = seen["url"].params
    assert q.get_list("COLLECTION") == ["spherex_dr1", "spherex_qr3"]
    assert q["POS"] == "circle 150.0 2.2 0.001"
    assert q["RESPONSEFORMAT"] == "CSV"
    assert len(frames) == 5


def test_epochs_group_close_frames():
    from server.sia import epochs
    frames = [_meta(m) for m in [0.0, 0.1, 0.2, 2.0, 2.1]]
    assert epochs(frames) == [pytest.approx(0.1), pytest.approx(2.05)]


def test_cached_query_falls_back_when_irsa_down(tmp_path, monkeypatch):
    from server import sia
    monkeypatch.setattr(sia.cache.SETTINGS, "cache_dir", tmp_path)
    text = (FIX / "sia_sample.csv").read_text()
    ok = httpx.MockTransport(lambda r: httpx.Response(200, text=text))
    down = httpx.MockTransport(lambda r: httpx.Response(503))

    async def run(transport):
        async with httpx.AsyncClient(transport=transport) as c:
            return await sia.cached_query_frames(c, 150.0, 2.2, 0.1)

    assert len(asyncio.run(run(ok))) == 5
    assert len(asyncio.run(run(down))) == 5   # served from disk


def test_cached_query_raises_when_down_and_uncached(tmp_path, monkeypatch):
    from server import sia
    monkeypatch.setattr(sia.cache.SETTINGS, "cache_dir", tmp_path)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as c:
            return await sia.cached_query_frames(c, 1.0, 2.0, 0.1)

    with pytest.raises(httpx.HTTPError):
        asyncio.run(run())

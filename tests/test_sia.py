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
    assert q.get_list("COLLECTION") == ["spherex_dr1", "spherex_qr3", "spherex_dr1_deep", "spherex_qr3_deep"]
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
    monkeypatch.setattr(sia.SETTINGS, "sia_ttl_hours", 0.0)  # always try IRSA first
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


def _fm(mjd, det):
    from server.sia import FrameMeta
    return FrameMeta(obs_id=f"o{mjd:.4f}", detector=det, mjd=mjd, iso="x", access_url="u", band_um=(1, 2))


def test_thin_frames_leaves_normal_spots_alone():
    from server.sia import thin_frames
    frames = [_fm(100 + i * 0.1, i % 6 + 1) for i in range(50)]
    assert thin_frames(frames, budget=60) == frames


def test_thin_frames_samples_whole_days_evenly_one_per_detector():
    from server.sia import thin_frames
    # deep-field style: 400 days, 30 frames a day across 6 detectors
    frames = [_fm(1000 + d + k / 40, k % 6 + 1) for d in range(400) for k in range(30)]
    out = thin_frames(frames, budget=120)
    assert 100 <= len(out) <= 120
    days = {}
    for f in out:
        days.setdefault(int(f.mjd), []).append(f.detector)
    assert all(len(d) == len(set(d)) for d in days.values())  # one frame per detector per day
    assert len(days) == 20                                     # 120 // 6 sample days
    span = max(days) - min(days)
    assert span > 350                                          # spread over the whole range
    assert [f.mjd for f in out] == sorted(f.mjd for f in out)


def test_cached_query_reuses_recent_answer_without_asking_irsa(tmp_path, monkeypatch):
    from server import sia
    monkeypatch.setattr(sia.cache.SETTINGS, "cache_dir", tmp_path)
    monkeypatch.setattr(sia.SETTINGS, "sia_ttl_hours", 12.0)
    text = (FIX / "sia_sample.csv").read_text()
    calls = []

    def handler(r):
        calls.append(1)
        return httpx.Response(200, text=text)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await sia.cached_query_frames(c, 150.0, 2.2, 0.1)

    assert len(asyncio.run(run())) == 5
    assert len(asyncio.run(run())) == 5
    assert len(calls) == 1  # second answer came from disk

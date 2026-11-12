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
    assert q["COLLECTION"] == "spherex_qr2"
    assert q["POS"] == "circle 150.0 2.2 0.001"
    assert q["RESPONSEFORMAT"] == "CSV"
    assert len(frames) == 5

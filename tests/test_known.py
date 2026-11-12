import asyncio
from pathlib import Path

import httpx
import pytest

from server import known
from server.known import known_sso, known_stars, parse_skybot_text, sso_to_grid

FIX = Path(__file__).parent / "fixtures"
SKY = (FIX / "skybot_sample.txt").read_text()


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(known.cache.SETTINGS, "cache_dir", tmp_path)


def test_parse_skybot_fixture():
    objs = parse_skybot_text(SKY)
    assert len(objs) >= 5
    o = objs[0]
    assert o["name"] == "2007 UK86"
    assert o["ra"] == pytest.approx(150.00915, abs=1e-4)
    assert o["dec"] == pytest.approx(2.21545, abs=1e-4)
    assert o["vmag"] == 23.4
    assert o["dra"] == pytest.approx(54.641)


def test_parse_skybot_missing_vmag():
    line = " - | C/2025 X1 | 10 00 02.0 | +02 12 55.6 | Comet |  | 0.1 | 60.0 | 12.0 | -3.0 | 1.2 | 1.5 \n"
    objs = parse_skybot_text(line)
    assert len(objs) == 1
    assert objs[0]["vmag"] is None
    assert objs[0]["dra"] == 12.0


def test_parse_skybot_empty():
    assert parse_skybot_text("# Flag: 0\n# Ticket: 1\n") == []


def test_sso_pixels():
    o = sso_to_grid(parse_skybot_text(SKY), 150.0, 2.2, 0.1)[0]
    c = (59 - 1) / 2
    assert o["x"] < c  # east of centre -> left
    assert o["dx_per_hr"] == pytest.approx(-54.641 / 6.15, abs=1e-6)
    assert o["dy_per_hr"] == pytest.approx(-17.420 / 6.15, abs=1e-6)


def test_wrap_ra_skybot():
    objs = [{"name": "w", "cls": "MB", "ra": 359.995, "dec": 0.0, "vmag": 18, "dra": 0, "ddec": 0}]
    o = sso_to_grid(objs, 0.01, 0.0, 0.1)[0]
    assert 0 <= o["x"] < 59 and 0 <= o["y"] < 59


def _run(coro_fn, handler):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await coro_fn(c)
    return asyncio.run(run())


def test_known_sso_query_and_cache():
    calls = {"n": 0, "url": None}

    def handler(request):
        calls["n"] += 1
        calls["url"] = request.url
        return httpx.Response(200, text=SKY)

    for _ in range(2):
        out = _run(lambda c: known_sso(c, 150.0, 2.2, 0.1, 60900.0), handler)
    assert calls["n"] == 1  # second call served from cache
    assert len(out) >= 5
    assert calls["url"].params["-ep"] == "2460900.5"
    assert float(calls["url"].params["-rd"]) == pytest.approx(0.175)


def test_stars_failure_returns_empty():
    out = _run(lambda c: known_stars(c, 150.0, 2.2, 0.1), lambda r: httpx.Response(500))
    assert out == []


def test_stars_parse():
    csv_text = "source_id,ra,dec,phot_g_mean_mag\n123,150.0,2.2,12.5\n"
    seen = {}

    def handler(r):
        seen["url"] = r.url
        return httpx.Response(200, text=csv_text)

    out = _run(lambda c: known_stars(c, 150.0, 2.2, 0.1), handler)
    assert seen["url"].host == "gea.esac.esa.int"
    assert "gaiadr3.gaia_source" in seen["url"].params["QUERY"]
    assert out == [{"source_id": "123", "gmag": 12.5, "x": pytest.approx(29.0), "y": pytest.approx(29.0)}]

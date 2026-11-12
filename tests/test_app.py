from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app as app_mod
from server.cutout import CutoutError
from server.sia import parse_sia_csv

FIX = Path(__file__).parent / "fixtures"
FRAMES = parse_sia_csv((FIX / "sia_sample.csv").read_text())


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(app_mod.SETTINGS, "cache_dir", tmp_path)

    async def fake_query(c, ra, dec, fov):
        return [f for f in parse_sia_csv((FIX / "sia_sample.csv").read_text())]

    monkeypatch.setattr(app_mod, "query_frames", fake_query)
    with TestClient(app_mod.app) as c:
        yield c


def test_frames_ok(client):
    r = client.get("/api/frames", params={"ra": 270, "dec": 66.56})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"target", "bursts", "frames"}
    assert body["target"] == {"ra": 270.0, "dec": 66.56, "fov": 0.1, "n": 59}
    assert len(body["frames"]) == 5
    assert body["frames"][0]["id"].endswith("D2")


def test_bad_input(client):
    assert client.get("/api/frames", params={"ra": 400, "dec": 0}).status_code == 422
    assert client.get("/api/frames", params={"ra": 10, "dec": 0, "fov": 1}).status_code == 422


def test_frame_unavailable(client, monkeypatch):
    async def boom(*a, **k):
        raise CutoutError("x")

    monkeypatch.setattr(app_mod, "get_frame", boom)
    r = client.get("/api/frame", params={"id": FRAMES[0].id, "ra": 270, "dec": 66.56})
    assert r.status_code == 502
    assert r.json() == {"detail": "IRSA unavailable, try again"}


def test_frame_no_coverage(client, monkeypatch):
    async def none(*a, **k):
        return None

    monkeypatch.setattr(app_mod, "get_frame", none)
    r = client.get("/api/frame", params={"id": FRAMES[0].id, "ra": 270, "dec": 66.56})
    assert r.status_code == 404
    assert r.json() == {"detail": "no coverage"}


def test_frame_unknown_id(client):
    r = client.get("/api/frame", params={"id": "nope", "ra": 270, "dec": 66.56})
    assert r.status_code == 404


def test_known_routes(client, monkeypatch):
    async def sso(c, ra, dec, fov, mjd):
        return [{"name": "a"}]

    async def stars(c, ra, dec, fov):
        return [{"source_id": "1"}]

    monkeypatch.setattr(app_mod, "known_sso", sso)
    monkeypatch.setattr(app_mod, "known_stars", stars)
    assert client.get("/api/known/sso", params={"ra": 1, "dec": 1, "mjd": 60900}).json() == [{"name": "a"}]
    assert client.get("/api/known/stars", params={"ra": 1, "dec": 1}).json() == [{"source_id": "1"}]


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<canvas" in r.text

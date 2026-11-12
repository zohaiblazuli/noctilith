"""FastAPI app: JSON API under /api, static frontend from web/."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from server.config import SETTINGS
from server.cutout import CutoutError, get_frame
from server.grid import make_grid_wcs
from server.known import known_sso, known_stars
from server.sia import assign_bursts, cached_query_frames as query_frames

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

RA = Query(..., ge=0, lt=360)
DEC = Query(..., ge=-90, le=90)
FOV = Query(SETTINGS.fov_default, ge=SETTINGS.fov_min, le=SETTINGS.fov_max)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(follow_redirects=True)
    app.state.sem = asyncio.Semaphore(SETTINGS.max_concurrency)
    app.state.frames = {}  # (ra, dec) -> {id: FrameMeta}
    yield
    await app.state.client.aclose()


app = FastAPI(title="SPHEREx Time Explorer", lifespan=lifespan)


def _tkey(ra, dec):
    return (round(ra, 5), round(dec, 5))


async def _frames_for(ra: float, dec: float, fov: float):
    frames = await query_frames(app.state.client, ra, dec, fov)
    bursts = assign_bursts(frames)
    app.state.frames[_tkey(ra, dec)] = {f.id: f for f in frames}
    return frames, bursts


@app.get("/api/frames")
async def api_frames(ra: float = RA, dec: float = DEC, fov: float = FOV):
    try:
        frames, bursts = await _frames_for(ra, dec, fov)
    except httpx.HTTPError:
        raise HTTPException(502, "IRSA unavailable, try again")
    _, n = make_grid_wcs(ra, dec, fov)
    return {"target": {"ra": ra, "dec": dec, "fov": fov, "n": n},
            "bursts": bursts, "frames": [f.to_dict() for f in frames]}


@app.get("/api/frame")
async def api_frame(id: str, ra: float = RA, dec: float = DEC, fov: float = FOV):
    table = app.state.frames.get(_tkey(ra, dec))
    if table is None:  # e.g. server restarted since the page loaded
        try:
            await _frames_for(ra, dec, fov)
        except httpx.HTTPError:
            raise HTTPException(502, "IRSA unavailable, try again")
        table = app.state.frames[_tkey(ra, dec)]
    meta = table.get(id)
    if meta is None:
        raise HTTPException(404, "unknown frame")
    try:
        payload = await get_frame(app.state.client, meta, ra, dec, fov, app.state.sem)
    except CutoutError:
        raise HTTPException(502, "IRSA unavailable, try again")
    if payload is None:
        raise HTTPException(404, "no coverage")
    return payload


@app.get("/api/known/sso")
async def api_sso(mjd: float, ra: float = RA, dec: float = DEC, fov: float = FOV):
    return await known_sso(app.state.client, ra, dec, fov, mjd)


@app.get("/api/known/stars")
async def api_stars(ra: float = RA, dec: float = DEC, fov: float = FOV):
    return await known_stars(app.state.client, ra, dec, fov)


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

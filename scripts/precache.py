"""Warm the disk cache for every demo spot (all frames + known objects), so the demo never waits on IRSA.

Usage: python scripts/precache.py [--only "label substring"]
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server.config import SETTINGS  # noqa: E402
from server.cutout import CutoutError, get_frame  # noqa: E402
from server.known import known_sso, known_stars  # noqa: E402
from server.sia import cached_query_frames, epochs  # noqa: E402


async def warm(c, sem, spot):
    ra, dec, fov = spot["ra"], spot["dec"], spot["fov"]
    frames = await cached_query_frames(c, ra, dec, fov)
    await known_stars(c, ra, dec, fov)
    for mjd in epochs(frames):  # same grouping and rounding as web/features.js
        await known_sso(c, ra, dec, fov, float(f"{mjd:.4f}"))
    ok = empty = failed = 0

    async def one(f):
        nonlocal ok, empty, failed
        try:
            p = await get_frame(c, f, ra, dec, fov, sem)
            if p is None:
                empty += 1
            else:
                ok += 1
        except CutoutError:
            failed += 1

    await asyncio.gather(*(one(f) for f in frames))
    print(f"{spot['label']}: {ok}/{len(frames)} frames cached ({empty} edge-only, {failed} failed)", flush=True)
    return failed


async def main():
    spots = json.loads((ROOT / "web" / "demo-spots.json").read_text())
    if "--only" in sys.argv:
        key = sys.argv[sys.argv.index("--only") + 1].lower()
        spots = [s for s in spots if key in s["label"].lower()]
    sem = asyncio.Semaphore(SETTINGS.max_concurrency)
    async with httpx.AsyncClient(follow_redirects=True) as c:
        for s in spots:
            await warm(c, sem, s)


if __name__ == "__main__":
    asyncio.run(main())

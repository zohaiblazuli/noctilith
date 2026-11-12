"""Find demo spots where a bright known asteroid visibly moves through SPHEREx frames.

For trial positions along the ecliptic: find SPHEREx bursts, ask SkyBoT for bright (V<17) objects
nearby at each burst's midpoint, then re-centre on each object and count frames in that burst where
the object stays inside a 0.2 deg field. Prints the best candidates as demo-spots.json entries.

Usage: python scripts/find_demo_spots.py [n_trials]
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx
import numpy as np
from astropy.coordinates import GeocentricTrueEcliptic, SkyCoord
import astropy.units as u

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server.known import SKYBOT_URL, parse_skybot_text  # noqa: E402
from server.sia import assign_bursts, query_frames  # noqa: E402

FIELD = 0.2
HALF = FIELD / 2 * 0.8
VMAX = 17.0


async def skybot(c, ra, dec, mjd, rd=1.0):
    p = {"-ep": f"{mjd + 2400000.5}", "-ra": ra, "-dec": dec, "-rd": rd,
         "-mime": "text", "-output": "basic", "-loc": "500"}
    try:
        r = await c.get(SKYBOT_URL, params=p, timeout=90)
        return parse_skybot_text(r.text)
    except httpx.HTTPError:
        return []


def offset(o, hours):
    """Position of object `o` after `hours` (small-angle; dra already includes cos dec)."""
    dec = o["dec"] + o["ddec"] * hours / 3600
    ra = o["ra"] + o["dra"] * hours / 3600 / np.cos(np.radians(o["dec"]))
    return ra % 360, dec


async def evaluate(c, o, mjd_mid):
    ra0, dec0 = o["ra"], o["dec"]
    frames = await query_frames(c, ra0, dec0, FIELD)
    inside = []
    for f in frames:
        h = (f.mjd - mjd_mid) * 24
        ra, dec = offset(o, h)
        dra = (ra - ra0 + 180) % 360 - 180
        if abs(dra * np.cos(np.radians(dec0))) < HALF and abs(dec - dec0) < HALF:
            inside.append(f.mjd)
    if len(inside) < 4:
        return None
    span_h = (max(inside) - min(inside)) * 24
    move_px = np.hypot(o["dra"], o["ddec"]) * span_h / 6.15
    return {"frames_with_object": len(inside), "span_h": round(span_h, 1), "moves_px": round(move_px, 1)}


async def main(n_trials):
    lons = np.linspace(0, 360, n_trials, endpoint=False)
    ecl = SkyCoord(lon=lons * u.deg, lat=np.zeros(n_trials) * u.deg, frame=GeocentricTrueEcliptic)
    icrs = ecl.icrs
    found = []
    async with httpx.AsyncClient(follow_redirects=True) as c:
        for ra, dec in zip(icrs.ra.deg, icrs.dec.deg):
            frames = await query_frames(c, ra, dec, FIELD)
            bursts = assign_bursts(frames)
            print(f"trial {ra:7.2f} {dec:+6.2f}: {len(frames)} frames, {len(bursts)} bursts", flush=True)
            for b in bursts:
                fs = [f for f in frames if f.burst == b["id"]]
                if len(fs) < 6:
                    continue
                mid = float(np.mean([f.mjd for f in fs]))
                objs = [o for o in await skybot(c, ra, dec, mid) if o["vmag"] is not None and o["vmag"] < VMAX]
                for o in sorted(objs, key=lambda o: o["vmag"])[:3]:
                    ev = await evaluate(c, o, mid)
                    if ev and ev["moves_px"] >= 3:
                        found.append({**ev, "name": o["name"], "vmag": o["vmag"], "cls": o["cls"],
                                      "ra": round(o["ra"], 5), "dec": round(o["dec"], 5), "mjd": round(mid, 3)})
                        print("   candidate:", found[-1], flush=True)
    found.sort(key=lambda f: (f["vmag"], -f["frames_with_object"]))
    print(json.dumps(found[:8], indent=2))


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 18))

"""Known objects: solar-system bodies from SkyBoT and stars from Gaia DR3 (via VizieR TAP), in grid pixels."""
import csv
import io
import logging

import httpx
import numpy as np

from server import cache
from server.config import SETTINGS
from server.grid import make_grid_wcs, sky_to_pixel

log = logging.getLogger(__name__)

SKYBOT_URL = "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php"
GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap/sync"  # ESA Gaia archive (VizieR TAP unreachable here)
MJD_TO_JD = 2400000.5


def parse_skybot_text(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        c = [s.strip() for s in line.split("|")]
        if len(c) < 10:
            continue
        h, m, s = (float(v) for v in c[2].split())
        d, dm, ds = c[3].split()
        sign = -1 if d.startswith("-") else 1
        out.append({
            "name": c[1],
            "cls": c[4],
            "ra": 15 * (h + m / 60 + s / 3600),
            "dec": sign * (abs(float(d)) + float(dm) / 60 + float(ds) / 3600),
            "vmag": float(c[5]),
            "dra": float(c[8]),   # arcsec/hr, already multiplied by cos(dec) (SkyBoT convention)
            "ddec": float(c[9]),
        })
    return out


def sso_to_grid(objs: list[dict], ra: float, dec: float, fov: float) -> list[dict]:
    if not objs:
        return []
    wcs, _ = make_grid_wcs(ra, dec, fov)
    x, y = sky_to_pixel(wcs, np.array([o["ra"] for o in objs]), np.array([o["dec"] for o in objs]))
    p = SETTINGS.pixel_arcsec
    return [{
        "name": o["name"], "cls": o["cls"], "vmag": o["vmag"],
        "x": float(xi), "y": float(yi),
        "dx_per_hr": -o["dra"] / p,  # east is left
        "dy_per_hr": o["ddec"] / p,
    } for o, xi, yi in zip(objs, x, y)]


async def known_sso(client: httpx.AsyncClient, ra: float, dec: float, fov: float, mjd: float) -> list[dict]:
    k = cache.key("sso-v1", round(ra, 4), round(dec, 4), fov, round(mjd, 2))
    hit = cache.get_json(k)
    if hit is not None:
        return hit
    params = {"-ep": f"{mjd + MJD_TO_JD}", "-ra": ra, "-dec": dec, "-rd": round(fov * 0.75 + 0.1, 6),
              "-mime": "text", "-output": "basic", "-loc": "500"}
    try:
        r = await client.get(SKYBOT_URL, params=params, timeout=60)
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("SkyBoT failed: %r", e)
        return []
    out = sso_to_grid(parse_skybot_text(r.text), ra, dec, fov)
    cache.put_json(k, out)
    return out


async def known_stars(client: httpx.AsyncClient, ra: float, dec: float, fov: float, gmax: float = 17.0) -> list[dict]:
    k = cache.key("stars-v1", round(ra, 4), round(dec, 4), fov, gmax)
    hit = cache.get_json(k)
    if hit is not None:
        return hit
    adql = (f"SELECT source_id,ra,dec,phot_g_mean_mag FROM gaiadr3.gaia_source "
            f"WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra},{dec},{fov * 0.75})) "
            f"AND phot_g_mean_mag<{gmax}")
    try:
        r = await client.get(GAIA_TAP, params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv",
                                                 "QUERY": adql}, timeout=60)
        r.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(r.text)))
    except (httpx.HTTPError, csv.Error) as e:
        log.warning("Gaia query failed: %r", e)
        return []
    rows = [w for w in rows if w.get("ra") and w.get("phot_g_mean_mag")]
    if not rows:
        cache.put_json(k, [])
        return []
    wcs, _ = make_grid_wcs(ra, dec, fov)
    x, y = sky_to_pixel(wcs, np.array([float(w["ra"]) for w in rows]),
                        np.array([float(w["dec"]) for w in rows]))
    out = [{"source_id": w["source_id"], "gmag": float(w["phot_g_mean_mag"]), "x": float(xi), "y": float(yi)}
           for w, xi, yi in zip(rows, x, y)]
    cache.put_json(k, out)
    return out

"""Find SPHEREx frames covering a position via IRSA SIA v2, and group them into visit bursts."""
import csv
import io
from dataclasses import asdict, dataclass

import httpx
from astropy.time import Time

from server import cache
from server.config import SETTINGS

SIA_URL = "https://irsa.ipac.caltech.edu/SIA"
SEARCH_RADIUS_DEG = 0.001  # frame must contain the target centre


@dataclass
class FrameMeta:
    obs_id: str
    detector: int
    mjd: float
    iso: str
    access_url: str
    band_um: tuple[float, float]
    burst: int = -1
    center: tuple[float, float] | None = None  # detector centre (ra, dec), for the wide view

    @property
    def id(self) -> str:
        # obs_id is shared by the 6 detectors of one exposure; id is unique per frame
        return f"{self.obs_id}D{self.detector}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        d["band_um"] = list(self.band_um)
        d["center"] = list(self.center) if self.center else None
        return d


def parse_sia_csv(text: str) -> list[FrameMeta]:
    frames = []
    for r in csv.DictReader(io.StringIO(text)):
        if not r.get("access_url"):
            continue
        mjd = float(r["t_min"])
        frames.append(FrameMeta(
            obs_id=r["obs_id"],
            detector=int(r["energy_bandpassname"].rsplit("D", 1)[-1]),
            mjd=mjd,
            iso="",  # filled in below for all frames at once (one Time() per row is slow at 29k rows)
            access_url=r["access_url"],
            band_um=(float(r["em_min"]) * 1e6, float(r["em_max"]) * 1e6),
            center=(float(r["s_ra"]), float(r["s_dec"])) if r.get("s_ra") and r.get("s_dec") else None,
        ))
    if frames:
        for f, iso in zip(frames, Time([f.mjd for f in frames], format="mjd").isot):
            f.iso = iso[:19]
    frames.sort(key=lambda f: f.mjd)
    return frames


def thin_frames(frames: list[FrameMeta], budget: int) -> list[FrameMeta]:
    """Even sample for deep-survey spots (tens of thousands of frames), so loading stays ~minutes.

    Spots under budget are returned as is. Otherwise budget // 6 sample days are spread evenly
    over the whole time range; from each, up to one frame per detector is kept, so each sample
    day stacks into one visit image (see web/logic.js visitGroups).
    """
    if len(frames) <= budget:
        return frames
    by_day: dict[int, list[FrameMeta]] = {}
    for f in frames:
        by_day.setdefault(int(f.mjd), []).append(f)
    days = sorted(by_day)
    n = max(1, min(len(days), budget // 6))
    picks = sorted({days[round(i * (len(days) - 1) / max(1, n - 1))] for i in range(n)})
    out = []
    for d in picks:
        seen = set()
        for f in sorted(by_day[d], key=lambda f: f.mjd):
            if f.detector not in seen:
                seen.add(f.detector)
                out.append(f)
    return sorted(out, key=lambda f: f.mjd)


def assign_bursts(frames: list[FrameMeta], gap_days: float = 10.0) -> list[dict]:
    bursts: list[dict] = []
    prev = None
    for f in sorted(frames, key=lambda f: f.mjd):
        if prev is None or f.mjd - prev > gap_days:
            bursts.append({"id": len(bursts), "start_iso": f.iso, "end_iso": f.iso, "count": 0})
        f.burst = bursts[-1]["id"]
        bursts[-1]["end_iso"] = f.iso
        bursts[-1]["count"] += 1
        prev = f.mjd
    return bursts


async def query_frames(client: httpx.AsyncClient, ra: float, dec: float, fov: float) -> list[FrameMeta]:
    # IRSA ORs repeated COLLECTION params, so one request covers every release.
    params = [("COLLECTION", c.strip()) for c in SETTINGS.collection.split(",") if c.strip()]
    params += [("POS", f"circle {ra} {dec} {SEARCH_RADIUS_DEG}"), ("RESPONSEFORMAT", "CSV")]
    r = await client.get(SIA_URL, params=params, timeout=60)
    r.raise_for_status()
    return parse_sia_csv(r.text)


def epochs(frames: list[FrameMeta], gap_days: float = 0.5) -> list[float]:
    """Mean MJD of each group of frames less than gap_days apart (must match web/features.js)."""
    out, group, prev = [], [], None
    for f in sorted(frames, key=lambda f: f.mjd):
        if prev is not None and f.mjd - prev > gap_days:
            out.append(sum(g.mjd for g in group) / len(group)); group = []
        group.append(f); prev = f.mjd
    if group:
        out.append(sum(g.mjd for g in group) / len(group))
    return out


async def cached_query_frames(client: httpx.AsyncClient, ra: float, dec: float, fov: float) -> list[FrameMeta]:
    """SIA query, reusing an answer younger than sia_ttl_hours (new data still shows up within a day);
    falls back to the last good answer of any age if IRSA is down."""
    k = cache.key("sia-v1", SETTINGS.collection, round(ra, 5), round(dec, 5))

    def from_cache():
        hit = cache.get_json(k)
        return None if hit is None else [
            FrameMeta(**{**d, "band_um": tuple(d["band_um"]),
                         "center": tuple(d["center"]) if d.get("center") else None}) for d in hit]

    age = cache.age_s(k)
    if age is not None and age < SETTINGS.sia_ttl_hours * 3600:
        fresh = from_cache()
        if fresh is not None:
            return fresh
    try:
        frames = await query_frames(client, ra, dec, fov)
    except httpx.HTTPError:
        hit = from_cache()
        if hit is None:
            raise
        return hit
    cache.put_json(k, [{kk: v for kk, v in f.to_dict().items() if kk != "id"} for f in frames])
    return frames

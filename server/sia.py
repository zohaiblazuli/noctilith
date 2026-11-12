"""Find SPHEREx frames covering a position via IRSA SIA v2, and group them into visit bursts."""
import csv
import io
from dataclasses import asdict, dataclass

import httpx
from astropy.time import Time

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

    @property
    def id(self) -> str:
        # obs_id is shared by the 6 detectors of one exposure; id is unique per frame
        return f"{self.obs_id}D{self.detector}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        d["band_um"] = list(self.band_um)
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
            iso=Time(mjd, format="mjd").isot[:19],
            access_url=r["access_url"],
            band_um=(float(r["em_min"]) * 1e6, float(r["em_max"]) * 1e6),
        ))
    frames.sort(key=lambda f: f.mjd)
    return frames


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
    params = {
        "COLLECTION": SETTINGS.collection,
        "POS": f"circle {ra} {dec} {SEARCH_RADIUS_DEG}",
        "RESPONSEFORMAT": "CSV",
    }
    r = await client.get(SIA_URL, params=params, timeout=60)
    r.raise_for_status()
    return parse_sia_csv(r.text)

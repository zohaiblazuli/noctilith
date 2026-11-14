"""Project settings. Override any field with an env var SPHEREX_<FIELD> (upper case)."""
import os
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class Settings:
    collection: str = "spherex_dr1,spherex_qr3,spherex_dr1_deep,spherex_qr3_deep"  # comma-separated, all searched
    sia_ttl_hours: float = 12.0  # reuse a spot's frame list this long (deep fields are 27 MB to re-query)
    frame_budget: int = 720  # max frames per spot; deep-survey spots are sampled evenly down to this
    cache_dir: Path = field(default_factory=lambda: Path("cache"))
    max_concurrency: int = 12
    pixel_arcsec: float = 6.15
    fov_min: float = 0.02
    fov_max: float = 0.5
    fov_default: float = 0.1

    def __post_init__(self):
        for f in fields(self):
            env = os.environ.get(f"SPHEREX_{f.name.upper()}")
            if env is not None:
                cur = getattr(self, f.name)
                setattr(self, f.name, Path(env) if isinstance(cur, Path) else type(cur)(env))


SETTINGS = Settings()

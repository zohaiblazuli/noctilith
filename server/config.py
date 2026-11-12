"""Project settings. Override any field with an env var SPHEREX_<FIELD> (upper case)."""
import os
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class Settings:
    collection: str = "spherex_qr2"
    cache_dir: Path = field(default_factory=lambda: Path("cache"))
    max_concurrency: int = 6
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

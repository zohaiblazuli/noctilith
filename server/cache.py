"""Tiny disk JSON cache under SETTINGS.cache_dir."""
import hashlib
import json
import os
import tempfile

from server.config import SETTINGS


def key(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()


def _path(k: str):
    return SETTINGS.cache_dir / k[:2] / f"{k}.json"


def get_json(k: str) -> dict | None:
    p = _path(k)
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def put_json(k: str, obj) -> None:
    p = _path(k)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, p)

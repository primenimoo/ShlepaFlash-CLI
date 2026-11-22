from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .config import cache_dir


class CacheManager:
    def __init__(self) -> None:
        self.dir = cache_dir()
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        safe = "".join(ch for ch in name if ch.isalnum() or ch in "._-") or "cache"
        return self.dir / safe

    def set_json(self, name: str, data: Any) -> None:
        payload = {"ts": time.time(), "data": data}
        path = self._path(name)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def get_json(self, name: str, max_age_seconds: int | None = None) -> Any | None:
        path = self._path(name)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            ts = float(payload.get("ts", 0))
            if max_age_seconds is not None and (time.time() - ts) > max_age_seconds:
                return None
            return payload.get("data")
        except Exception:
            return None

    def get_json_with_age(self, name: str) -> tuple[Any | None, float | None]:
        path = self._path(name)
        if not path.exists():
            return None, None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            ts = float(payload.get("ts", 0))
            return payload.get("data"), ts
        except Exception:
            return None, None

    def set_bytes(self, name: str, data: bytes) -> Path:
        path = self._path(name)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return path

    def get_bytes(self, name: str) -> bytes | None:
        path = self._path(name)
        if not path.exists():
            return None
        try:
            return path.read_bytes()
        except Exception:
            return None

    def path_for(self, name: str) -> Path:
        return self._path(name)

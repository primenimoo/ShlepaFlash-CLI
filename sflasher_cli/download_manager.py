from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Callable

from .api_client import ApiClient
from .cache import CacheManager

log = logging.getLogger("sflasher.download")


class DownloadManager:
    def __init__(self, api: ApiClient, cache: CacheManager) -> None:
        self.api = api
        self.cache = cache
        self.download_dir = self.cache.dir / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def download(self, url: str, dest_name: str, expected_size: int | None = None,
                 progress_cb: Callable[[int, int], None] | None = None) -> Path:
        safe = "".join(ch for ch in dest_name if ch.isalnum() or ch in "._-") or "download.bin"
        dest = self.download_dir / safe
        data = self.api.download_bytes(url, expected_size=expected_size, chunk_cb=progress_cb)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(dest)
        log.info("Downloaded %s (%s bytes) sha256=%s", dest, len(data), hashlib.sha256(data).hexdigest())
        return dest

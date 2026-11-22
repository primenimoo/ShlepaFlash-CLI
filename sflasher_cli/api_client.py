from __future__ import annotations

import hashlib
import logging
from typing import Any

import requests

from .config import API_LIST_URL, SITE_ORIGIN

log = logging.getLogger("sflasher.api")


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, origin: str = SITE_ORIGIN, timeout: float = 12.0) -> None:
        self.origin = origin.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ShlepaFlash-CLI/1.0 (+https://sflasher.bot.nu)",
            "Accept": "application/json,*/*",
        })

    def list_url(self) -> str:
        if self.origin == SITE_ORIGIN:
            return API_LIST_URL
        return f"{self.origin}/api?action=list"

    def fetch_catalog(self) -> dict[str, Any]:
        url = self.list_url()
        log.info("Fetching catalog: %s", url)
        r = self.session.get(url, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ApiError("Unexpected catalog response")
        return data

    def download_bytes(self, url: str, expected_size: int | None = None, chunk_cb=None) -> bytes:
        full = self.resolve_url(url)
        log.info("Downloading %s", full)
        with self.session.get(full, timeout=max(self.timeout, 30), stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0) or (expected_size or 0)
            buf = bytearray()
            got = 0
            for chunk in r.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                buf.extend(chunk)
                got += len(chunk)
                if chunk_cb:
                    chunk_cb(got, total)
        data = bytes(buf)
        if expected_size and expected_size > 0 and len(data) != expected_size:
            log.warning("Downloaded size %s differs from expected %s for %s", len(data), expected_size, full)
        return data

    def resolve_url(self, url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if not url.startswith("/"):
            url = "/" + url
        return self.origin + url

    @staticmethod
    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

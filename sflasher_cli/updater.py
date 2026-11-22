from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from . import __version__

log = logging.getLogger("sflasher.updater")
GITHUB_LATEST = "https://api.github.com/repos/primenimoo/ShlepaFlash-CLI/releases/latest"


@dataclass
class UpdateInfo:
    current: str
    latest: str
    url: str
    available: bool


def check_update(timeout: float = 8.0) -> UpdateInfo | None:
    try:
        r = requests.get(GITHUB_LATEST, timeout=timeout, headers={"Accept": "application/vnd.github+json", "User-Agent": "ShlepaFlash-CLI"})
        if r.status_code != 200:
            return None
        data = r.json()
        latest = str(data.get("tag_name") or "").lstrip("v")
        url = str(data.get("html_url") or "")
        if not latest:
            return None
        return UpdateInfo(current=__version__, latest=latest, url=url, available=latest != __version__)
    except Exception as e:
        log.debug("Update check failed: %s", e)
        return None

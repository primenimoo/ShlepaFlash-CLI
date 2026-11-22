from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir, user_cache_dir, user_log_dir

APP_NAME = "ShlepaFlashCLI"
APP_AUTHOR = "ShlepaFlash"
SITE_ORIGIN = "https://sflasher.bot.nu"
API_LIST_URL = f"{SITE_ORIGIN}/api?action=list"


def config_dir() -> Path:
    p = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = Path(user_cache_dir(APP_NAME, APP_AUTHOR))
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_dir() -> Path:
    p = Path(user_log_dir(APP_NAME, APP_AUTHOR))
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "auto",  # auto|dark|light|orange|blue|purple|green|red|mono
    "language": "ru",  # ru|en
    "animations": True,
    "ui_scale": "normal",  # compact|normal|large
    "logging_enabled": True,
    "log_level": "INFO",
    "check_updates": True,
    "last_update_check": "",
    "erase_before_flash": False,
    "install_components": True,
}


@dataclass
class Settings:
    theme: str = DEFAULT_SETTINGS["theme"]
    language: str = DEFAULT_SETTINGS["language"]
    animations: bool = DEFAULT_SETTINGS["animations"]
    ui_scale: str = DEFAULT_SETTINGS["ui_scale"]
    logging_enabled: bool = DEFAULT_SETTINGS["logging_enabled"]
    log_level: str = DEFAULT_SETTINGS["log_level"]
    check_updates: bool = DEFAULT_SETTINGS["check_updates"]
    last_update_check: str = DEFAULT_SETTINGS["last_update_check"]
    erase_before_flash: bool = DEFAULT_SETTINGS["erase_before_flash"]
    install_components: bool = DEFAULT_SETTINGS["install_components"]

    @classmethod
    def load(cls) -> "Settings":
        path = config_dir() / "settings.json"
        data = dict(DEFAULT_SETTINGS)
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for k in DEFAULT_SETTINGS:
                        if k in raw:
                            data[k] = raw[k]
            except Exception:
                pass
        return cls(**{k: data.get(k, DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS})

    def save(self) -> None:
        path = config_dir() / "settings.json"
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def update(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.save()

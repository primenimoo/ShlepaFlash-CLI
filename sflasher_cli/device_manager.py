from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    chip: str
    family: str
    image: str
    description: str
    aliases: tuple[str, ...] = ()


# Sourced from ShlepaFlash site/device mapping. Keep conservative.
KNOWN_DEVICES: list[Device] = [
    Device("plus2", "M5StickC Plus 2", "ESP32", "m5stick", "assets/stick-plus2.png",
           "Compact M5Stack device with ESP32, display and buttons.", ("m5stickc plus2", "plus2")),
    Device("plus", "M5StickC Plus", "ESP32", "m5stick", "assets/stick-plus.png",
           "Classic M5StickC Plus ESP32 device.", ("m5stickc plus", "plus")),
    Device("s3", "M5Stick S3", "ESP32-S3", "m5stick", "assets/stick-s3.png",
           "M5Stack StickS3 with ESP32-S3.", ("sticks3", "m5sticks3", "s3")),
    Device("tembed", "T-Embed CC1101", "ESP32-S3", "t-embed", "assets/tembed.png",
           "LILYGO T-Embed with CC1101 and ESP32-S3.", ("t-embed", "tembed")),
    Device("flux", "Flux ESP32-S3", "ESP32-S3", "esp32", "assets/flux_esp32s3.png",
           "Flux ESP32-S3 compatible device.", ("flux",)),
    Device("cardputer", "M5Stack Cardputer", "ESP32-S3", "cardputer", "assets/cardputer.png",
           "M5Stack Cardputer with keyboard and ESP32-S3.", ("cardputer",)),
    Device("cardputer-adv", "M5Stack Cardputer ADV", "ESP32-S3", "cardputer", "assets/adv.png",
           "M5Stack Cardputer ADV with ESP32-S3.", ("cardputer adv", "cardputer-adv")),
    Device("cyd", "CYD-2432S028", "ESP32", "cyd", "assets/cyd.png",
           "Cheap Yellow Display ESP32-2432S028.", ("cyd", "2432s028")),
]


class DeviceManager:
    def __init__(self) -> None:
        self._devices = {d.id: d for d in KNOWN_DEVICES}

    def all(self) -> list[Device]:
        return list(KNOWN_DEVICES)

    def get(self, device_id: str) -> Device | None:
        return self._devices.get(device_id)

    def supported_ids(self) -> set[str]:
        return set(self._devices.keys())

    def from_catalog_item(self, item: dict[str, Any]) -> list[Device]:
        ids: set[str] = set()
        targets = item.get("targets") or []
        if isinstance(targets, list):
            ids.update([t for t in targets if isinstance(t, str)])
        for key in ("models", "extraFiles", "extras"):
            obj = item.get(key) or {}
            if isinstance(obj, dict):
                ids.update([k for k in obj.keys() if isinstance(k, str)])
        return [self._devices[i] for i in self._devices if i in ids]

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from serial.tools import list_ports

log = logging.getLogger("sflasher.serial")


@dataclass
class PortInfo:
    device: str
    description: str
    hwid: str
    vid: int | None
    pid: int | None
    manufacturer: str | None
    product: str | None
    serial_number: str | None
    chipset: str


_CHIP_HINTS = [
    ("303A:1001", "ESP32-S3 USB JTAG/Serial"),
    ("303A:", "Espressif USB"),
    ("1A86:55D4", "CH9102 (common ESP32-S3)"),
    ("1A86:7523", "CH340"),
    ("10C4:EA60", "CP2102/CP2104"),
    ("0403:6001", "FT232"),
    ("0403:6015", "FT231X"),
]

_PRODUCT_HINTS = [
    ("ESP32-S3", "ESP32-S3"),
    ("ESP32S3", "ESP32-S3"),
    ("ESP32-S2", "ESP32-S2"),
    ("ESP32C3", "ESP32-C3"),
    ("ESP32-C3", "ESP32-C3"),
    ("ESP32", "ESP32"),
    ("CP210", "CP210x (ESP-compatible)"),
    ("CH340", "CH340 (ESP-compatible)"),
    ("CH910", "CH9102 (ESP-compatible)"),
]


def _guess_chipset(p) -> str:
    hwid = (p.hwid or "").upper()
    for prefix, name in _CHIP_HINTS:
        if prefix in hwid:
            if "ESP32-S3" in name or "303A" in prefix:
                return "ESP32-S3"
            if "ESP32" in name:
                return "ESP32"
    blob = " ".join([str(p.description or ""), str(p.product or ""), str(p.manufacturer or "")]).upper()
    for needle, label in _PRODUCT_HINTS:
        if needle.upper() in blob:
            return label
    return "Unknown chipset"


class SerialManager:
    def list_ports(self) -> list[PortInfo]:
        ports: list[PortInfo] = []
        for p in list_ports.comports():
            info = PortInfo(
                device=p.device,
                description=p.description or p.device,
                hwid=p.hwid or "",
                vid=p.vid,
                pid=p.pid,
                manufacturer=p.manufacturer,
                product=p.product,
                serial_number=p.serial_number,
                chipset=_guess_chipset(p),
            )
            ports.append(info)
        ports.sort(key=lambda x: x.device)
        return ports

    def port_present(self, device: str) -> bool:
        return any(p.device == device for p in self.list_ports())

    def wait_for_port(self, device: str, timeout: float = 5.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if self.port_present(device):
                return True
            time.sleep(0.25)
        return False

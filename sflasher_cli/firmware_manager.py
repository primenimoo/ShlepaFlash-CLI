from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .device_manager import DeviceManager


@dataclass
class FirmwareDownload:
    device_id: str
    kind: str  # bin|package|extra
    url: str
    size: int
    file_name: str = ""
    format: str = ""


@dataclass
class Firmware:
    id: str
    name: str
    version: str
    channel: str
    description: str
    long_description: str
    logo_url: str
    targets: list[str]
    models: dict[str, Any]
    extra_files: dict[str, Any]
    extras: dict[str, Any]
    package: dict[str, Any] | None
    updated_at: str = ""

    def supports(self, device_id: str) -> bool:
        if self.targets and device_id in self.targets:
            return True
        if device_id in self.models or device_id in self.extra_files or device_id in self.extras:
            return True
        if self.package and isinstance(self.package.get("devices"), dict) and device_id in self.package["devices"]:
            return True
        return False

    def primary_download(self, device_id: str) -> FirmwareDownload | None:
        # package / multi / zip
        if self.package and isinstance(self.package, dict):
            mode = self.package.get("mode")
            per_device = self.package.get("perDevice") is True
            if per_device:
                devices = self.package.get("devices") or {}
                if device_id in devices:
                    size = int(devices[device_id].get("totalSize") or 0)
                    return FirmwareDownload(device_id, "package", f"/api?action=download&id={self.id}&model={device_id}", size, format=mode or "package")
            elif not self.targets or device_id in self.targets:
                size = int(self.package.get("totalSize") or 0)
                return FirmwareDownload(device_id, "package", f"/api?action=download&id={self.id}&model={device_id}", size, format=mode or "package")

        if device_id == "tembed":
            info = self.extra_files.get(device_id) or {}
            if info.get("fileName") or info.get("url"):
                size = int(info.get("size") or 0)
                name = str(info.get("name") or info.get("fileName") or "firmware.bin")
                fmt = name.rsplit(".", 1)[-1].lower() if "." in name else "bin"
                return FirmwareDownload(device_id, "bin", f"/api?action=download&id={self.id}&model={device_id}", size, name, fmt)

        info = self.models.get(device_id) or {}
        if info.get("fileName") or info.get("url"):
            size = int(info.get("size") or 0)
            name = str(info.get("name") or info.get("fileName") or "firmware.bin")
            return FirmwareDownload(device_id, "bin", f"/api?action=download&id={self.id}&model={device_id}", size, name, "bin")

        return None

    def extra_component(self, device_id: str) -> FirmwareDownload | None:
        extra = self.extras.get(device_id)
        if not isinstance(extra, dict):
            return None
        size = int(extra.get("size") or 0)
        name = str(extra.get("name") or "components.zip")
        return FirmwareDownload(device_id, "extra", f"/api?action=download&id={self.id}&model={device_id}&kind=extra", size, name, "zip")


class FirmwareManager:
    def __init__(self, device_manager: DeviceManager) -> None:
        self.device_manager = device_manager
        self.items: list[Firmware] = []

    def load_from_catalog(self, catalog: dict[str, Any]) -> list[Firmware]:
        items = catalog.get("items") or []
        out: list[Firmware] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            fw = Firmware(
                id=str(raw.get("id") or ""),
                name=str(raw.get("name") or ""),
                version=str(raw.get("version") or ""),
                channel=str(raw.get("channel") or "release"),
                description=str(raw.get("description") or ""),
                long_description=str(raw.get("longDescription") or ""),
                logo_url=str(raw.get("logoUrl") or ""),
                targets=[t for t in (raw.get("targets") or []) if isinstance(t, str)],
                models=raw.get("models") if isinstance(raw.get("models"), dict) else {},
                extra_files=raw.get("extraFiles") if isinstance(raw.get("extraFiles"), dict) else {},
                extras=raw.get("extras") if isinstance(raw.get("extras"), dict) else {},
                package=raw.get("package") if isinstance(raw.get("package"), dict) else None,
                updated_at=str(raw.get("updatedAt") or ""),
            )
            if fw.id and fw.name:
                out.append(fw)
        self.items = out
        return out

    def for_device(self, device_id: str) -> list[Firmware]:
        supported = self.device_manager.supported_ids()
        if device_id not in supported:
            return []
        return [fw for fw in self.items if fw.supports(device_id) and fw.primary_download(device_id)]

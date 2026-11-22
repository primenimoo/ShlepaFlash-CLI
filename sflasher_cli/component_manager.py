from __future__ import annotations

import io
import logging
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

log = logging.getLogger("sflasher.components")

PARTITION_MAGIC = b"\xAA\x50"
FLASH_SECTOR = 0x1000


def parse_partition_table(firmware_bytes: bytes) -> list[dict]:
    # scan for partition table at common offsets
    for base in (0x8000, 0x9000, 0xC000, 0xE000):
        if base + 2 > len(firmware_bytes):
            continue
        if firmware_bytes[base:base+2] != PARTITION_MAGIC:
            continue
        entries = []
        off = base
        while off + 32 <= len(firmware_bytes):
            chunk = firmware_bytes[off:off+32]
            if chunk[:2] != PARTITION_MAGIC:
                break
            ptype, subtype = chunk[2], chunk[3]
            addr = struct.unpack_from('<I', chunk, 4)[0] & 0xFFFFFF
            size = struct.unpack_from('<I', chunk, 8)[0] & 0xFFFFFF
            label = chunk[12:28].split(b'\x00')[0].split(b'\xff')[0].decode('utf-8', errors='ignore').strip()
            if addr and size:
                entries.append({"type": ptype, "subtype": subtype, "address": addr, "size": size, "label": label})
            off += 32
        if entries:
            return entries
    return []


def find_fs_partition(entries: list[dict]) -> dict | None:
    # data partitions with subtype littlefs/spiffs (0x82, 0x83) or labels
    for e in entries:
        if e["type"] == 0x01 and e["subtype"] in (0x82, 0x83):
            return e
    for e in entries:
        if e.get("label", "").lower() in ("littlefs", "spiffs", "fs", "storage") and e["type"] == 0x01:
            return e
    # fallback: largest data partition
    data = [e for e in entries if e["type"] == 0x01]
    return max(data, key=lambda e: e["size"]) if data else None


def build_littlefs_image(extra_zip: Path, size: int, log_cb: Callable[[str], None] | None = None) -> Path | None:
    # Try littlefs-python first
    try:
        import littlefs  # type: ignore
        return _build_with_littlefs_python(extra_zip, size, log_cb)
    except Exception as e:
        if log_cb: log_cb(f"littlefs-python недоступен: {e}")

    # Try mklittlefs / mklfs
    for cmd in ("mklittlefs", "mklfs"):
        if shutil.which(cmd):
            return _build_with_mklittlefs(cmd, extra_zip, size, log_cb)

    if log_cb:
        log_cb("Не найден инструмент создания LittleFS (littlefs-python/mklittlefs). Доп. компоненты пропущены.")
    return None


def _build_with_littlefs_python(extra_zip: Path, size: int, log_cb: Callable[[str], None] | None = None) -> Path:
    import littlefs  # type: ignore
    block_size = 4096
    block_count = size // block_size
    if block_count <= 0:
        raise ValueError("Недопустимый размер FS раздела")
    fs = littlefs.LFS(block_size=block_size, block_count=block_count)
    fs.format()
    fs.mount()
    with zipfile.ZipFile(extra_zip) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = "/" + info.filename.lstrip("/\\")
            # create parent dirs
            parts = [p for p in name.split("/") if p]
            cur = ""
            for p in parts[:-1]:
                cur += "/" + p
                try:
                    fs.mkdir(cur)
                except Exception:
                    pass
            data = zf.read(info)
            with fs.open(name, "wb") as f:
                f.write(data)
            if log_cb: log_cb(f"  + {name} ({len(data)} bytes)")
    fs.unmount()
    img = Path(tempfile.mkdtemp(prefix="sflasher-fs-")) / "littlefs.bin"
    img.write_bytes(fs.context.buffer)
    if log_cb: log_cb(f"LittleFS образ создан: {img} ({img.stat().st_size} bytes)")
    return img


def _build_with_mklittlefs(cmd: str, extra_zip: Path, size: int, log_cb: Callable[[str], None] | None = None) -> Path | None:
    tmp = Path(tempfile.mkdtemp(prefix="sflasher-fs-"))
    src = tmp / "src"
    src.mkdir()
    with zipfile.ZipFile(extra_zip) as zf:
        zf.extractall(src)
    img = tmp / "littlefs.bin"
    args = [cmd, "-c", str(src), "-s", str(size), str(img)]
    if log_cb: log_cb("$ " + " ".join(args))
    p = subprocess.run(args, capture_output=True, text=True)
    if p.stdout and log_cb: log_cb(p.stdout.strip())
    if p.stderr and log_cb: log_cb(p.stderr.strip())
    if p.returncode != 0 or not img.exists():
        if log_cb: log_cb("mklittlefs завершился с ошибкой")
        return None
    return img

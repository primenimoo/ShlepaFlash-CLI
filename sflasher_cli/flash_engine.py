from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log_cb_type = Callable[[str], None]
progress_cb_type = Callable[[int, str], None]


@dataclass
class FlashPlanItem:
    offset: int
    path: Path
    label: str = ""


@dataclass
class FlashResult:
    ok: bool
    message: str
    details: str = ""


ESP_IMAGE_MAGIC = 0xE9
PARTITION_MAGIC = b"\xAA\x50"


def detect_chip_for_model(model_id: str) -> str:
    esp32s3 = {"s3", "tembed", "flux", "cardputer", "cardputer-adv"}
    return "esp32s3" if model_id in esp32s3 else "esp32"


def looks_like_merged_image(data: bytes) -> bool:
    if len(data) < 0x9000:
        return False
    if data[0] != ESP_IMAGE_MAGIC:
        return False
    # Common merged image has bootloader at 0x0, partition table at 0x8000
    if data[0x8000:0x8002] == PARTITION_MAGIC:
        return True
    if data[0x9000:0x9002] == PARTITION_MAGIC:
        return True
    return False


def looks_like_app_image(data: bytes) -> bool:
    return len(data) >= 32 and data[0] == ESP_IMAGE_MAGIC


def plan_single_bin(path: Path, model_id: str) -> list[FlashPlanItem]:
    data = path.read_bytes()
    if looks_like_merged_image(data):
        return [FlashPlanItem(0x0, path, "merged image")]
    if looks_like_app_image(data):
        # App-only image: use default factory app offset.
        return [FlashPlanItem(0x10000, path, "app image")]
    raise ValueError("Файл не похож на ESP прошивку (нет магии ESP image).")


def _parse_flash_args(text: str) -> list[tuple[int, str]]:
    # esptool flash_args format: lines like "0x10000 app.bin"
    items: list[tuple[int, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(0x[0-9a-fA-F]+|\d+)\s+(.+)$", line)
        if m:
            off = int(m.group(1), 0)
            name = m.group(2).strip().strip('"')
            items.append((off, name))
    return items


def plan_zip_package(zip_path: Path, model_id: str) -> list[FlashPlanItem]:
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        # Look for manifest.json
        manifest_name = next((n for n in names if n.endswith("manifest.json")), None)
        flash_args_name = next((n for n in names if n.endswith("flash_args") or n.endswith("flash_args.txt")), None)
        tmpdir = Path(tempfile.mkdtemp(prefix="sflasher-pkg-"))
        extracted: list[FlashPlanItem] = []

        if manifest_name:
            manifest = json.loads(zf.read(manifest_name).decode("utf-8", errors="replace"))
            # Common manifest shapes: {"parts":[{"path":"bootloader.bin","offset":0},...]} or {"builds":[...]}
            parts = manifest.get("parts") or manifest.get("files") or manifest.get("components") or []
            if isinstance(parts, list) and parts:
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    p = part.get("path") or part.get("file") or part.get("name")
                    off = part.get("offset")
                    if p is None or off is None:
                        continue
                    if isinstance(off, str):
                        off = int(off, 0)
                    off = int(off)
                    member = _find_member(names, str(p))
                    if not member:
                        continue
                    out = tmpdir / Path(member).name
                    out.write_bytes(zf.read(member))
                    extracted.append(FlashPlanItem(off, out, Path(member).name))
                if extracted:
                    return sorted(extracted, key=lambda x: x.offset)

        if flash_args_name:
            text = zf.read(flash_args_name).decode("utf-8", errors="replace")
            for off, fname in _parse_flash_args(text):
                member = _find_member(names, fname)
                if not member:
                    continue
                out = tmpdir / Path(member).name
                out.write_bytes(zf.read(member))
                extracted.append(FlashPlanItem(off, out, Path(member).name))
            if extracted:
                return sorted(extracted, key=lambda x: x.offset)

        # Fallback: find .bin files and infer offsets by common names
        bins = [n for n in names if n.lower().endswith(".bin")]
        for b in bins:
            lower = b.lower()
            off = None
            if "bootloader" in lower:
                off = 0x0 if detect_chip_for_model(model_id) == "esp32s3" else 0x1000
            elif "partition" in lower:
                off = 0x8000
            elif "ota" in lower:
                off = 0xe000 if "data" in lower else None
            elif "app" in lower or "firmware" in lower:
                off = 0x10000
            if off is None:
                # try to detect merged/app
                data = zf.read(b)
                if looks_like_merged_image(data):
                    off = 0x0
                elif looks_like_app_image(data):
                    off = 0x10000
                else:
                    continue
            out = tmpdir / Path(b).name
            out.write_bytes(zf.read(b))
            extracted.append(FlashPlanItem(off, out, Path(b).name))
        if not extracted:
            raise ValueError("В ZIP не найдены пригодные компоненты прошивки (manifest/flash_args/bin).")
        # de-dupe by offset, prefer larger/specific
        by_off: dict[int, FlashPlanItem] = {}
        for item in sorted(extracted, key=lambda x: x.path.stat().st_size, reverse=True):
            by_off.setdefault(item.offset, item)
        return sorted(by_off.values(), key=lambda x: x.offset)


def _find_member(names: list[str], wanted: str) -> str | None:
    wanted_norm = wanted.replace("\\", "/").lstrip("./")
    base = Path(wanted_norm).name.lower()
    for n in names:
        nn = n.replace("\\", "/")
        if nn == wanted_norm or nn.endswith("/" + wanted_norm):
            return n
    for n in names:
        if Path(n).name.lower() == base:
            return n
    return None


class FlashEngine:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True
        p = self._proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass

    def _run(self, args: list[str], log_cb: log_cb_type | None, progress_cb: progress_cb_type | None,
             progress_base: int, progress_span: int, stage: str) -> tuple[int, str]:
        cmd = [sys.executable, "-m", "esptool", *args]
        if log_cb:
            log_cb(f"$ {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self._proc = proc
        out_lines: list[str] = []
        pct_re = re.compile(r"\((\d{1,3})\s*%\)")
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\n")
                out_lines.append(line)
                if log_cb:
                    log_cb(line)
                m = pct_re.search(line)
                if m and progress_cb:
                    pct = max(0, min(100, int(m.group(1))))
                    overall = progress_base + int(pct * progress_span / 100)
                    progress_cb(min(99, overall), stage)
                if self._cancel:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    break
            code = proc.wait(timeout=30)
        except Exception as e:
            try:
                proc.kill()
            except Exception:
                pass
            code = 1
            out_lines.append(str(e))
        finally:
            self._proc = None
        return code, "\n".join(out_lines)

    def flash(self, port: str, model_id: str, firmware_path: Path, erase: bool = False,
              log_cb: log_cb_type | None = None, progress_cb: progress_cb_type | None = None) -> FlashResult:
        self._cancel = False
        chip = detect_chip_for_model(model_id)
        try:
            plan = self._make_plan(firmware_path, model_id)
        except Exception as e:
            return FlashResult(False, f"Ошибка подготовки прошивки: {e}")

        if log_cb:
            log_cb(f"План прошивки: chip={chip}, port={port}, erase={erase}")
            for item in plan:
                log_cb(f" - {item.label or item.path.name} @ {hex(item.offset)} ({item.path.stat().st_size} bytes)")

        if erase:
            if progress_cb: progress_cb(1, "Стирание флеш-памяти")
            code, out = self._run(["--chip", chip, "--port", port, "erase_flash"], log_cb, progress_cb, 2, 18, "Стирание флеш-памяти")
            if self._cancel:
                return FlashResult(False, "Прошивка отменена пользователем", out)
            if code != 0:
                return FlashResult(False, "Ошибка стирания флеш-памяти", out)

        # write
        write_args = ["--chip", chip, "--port", port, "--baud", "460800", "write_flash", "-z"]
        for item in plan:
            write_args.extend([hex(item.offset), str(item.path)])
        base = 20 if erase else 2
        span = 75 if erase else 93
        if progress_cb: progress_cb(base, "Запись прошивки")
        code, out = self._run(write_args, log_cb, progress_cb, base, span, "Запись прошивки")
        if self._cancel:
            return FlashResult(False, "Прошивка отменена пользователем", out)
        if code != 0:
            return FlashResult(False, "Ошибка записи прошивки", out)

        if progress_cb: progress_cb(99, "Завершение")
        return FlashResult(True, "Прошивка успешно завершена", out)

    def hard_reset(self, port: str, model_id: str, log_cb: log_cb_type | None = None) -> FlashResult:
        chip = detect_chip_for_model(model_id)
        code, out = self._run(["--chip", chip, "--port", port, "run"], log_cb, None, 100, 0, "Перезапуск")
        if code != 0:
            return FlashResult(False, "Не удалось перезапустить устройство", out)
        return FlashResult(True, "Команда перезапуска отправлена", out)

    def write_image(self, port: str, model_id: str, offset: int, image_path: Path,
                    log_cb: log_cb_type | None = None, progress_cb: progress_cb_type | None = None,
                    progress_base: int = 60, progress_span: int = 35, stage: str = "Запись компонентов") -> FlashResult:
        self._cancel = False
        chip = detect_chip_for_model(model_id)
        args = ["--chip", chip, "--port", port, "--baud", "460800", "write_flash", "-z", hex(offset), str(image_path)]
        if progress_cb: progress_cb(progress_base, stage)
        code, out = self._run(args, log_cb, progress_cb, progress_base, progress_span, stage)
        if self._cancel:
            return FlashResult(False, "Операция отменена пользователем", out)
        if code != 0:
            return FlashResult(False, "Ошибка записи образа", out)
        return FlashResult(True, "Образ записан", out)

    def _make_plan(self, firmware_path: Path, model_id: str) -> list[FlashPlanItem]:
        name = firmware_path.name.lower()
        if name.endswith(".zip"):
            return plan_zip_package(firmware_path, model_id)
        return plan_single_bin(firmware_path, model_id)

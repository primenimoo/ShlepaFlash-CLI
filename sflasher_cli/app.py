from __future__ import annotations

import asyncio
import logging
import os
import platform
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Footer, Header, Label, ListItem, ListView, ProgressBar, Static

from . import __version__
from .api_client import ApiClient
from .cache import CacheManager
from .component_manager import build_littlefs_image, find_fs_partition, parse_partition_table
from .config import Settings
from .device_manager import DeviceManager
from .download_manager import DownloadManager
from .firmware_manager import Firmware, FirmwareManager
from .flash_engine import FlashEngine
from .i18n import t
from .logger import AppLogger
from .serial_manager import SerialManager
from .theme import THEMES, THEME_ORDER, resolve_theme, theme_css
from .updater import check_update

log = logging.getLogger("sflasher.app")


def load_logo() -> str:
    p = Path(__file__).resolve().parent / "assets" / "logo.txt"
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return "SHLEPAFLASH CLI"


def fmt_size(n: int) -> str:
    if n <= 0:
        return "—"
    units = ["B", "KB", "MB", "GB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.1f} {u}" if u != "B" else f"{int(x)} B"
        x /= 1024
    return f"{n} B"


class State:
    def __init__(self) -> None:
        self.settings = Settings.load()
        self.cache = CacheManager()
        self.api = ApiClient()
        self.devices = DeviceManager()
        self.firmware = FirmwareManager(self.devices)
        self.downloads = DownloadManager(self.api, self.cache)
        self.serial = SerialManager()
        self.flash = FlashEngine()
        self.logger = AppLogger(enabled=self.settings.logging_enabled, level=self.settings.log_level)
        self.catalog: dict[str, Any] | None = None
        self.catalog_from_cache = False
        self.catalog_age: float | None = None
        self.selected_device_id: str | None = None
        self.selected_firmware: Firmware | None = None
        self.selected_port: str | None = None
        self.erase_before_flash = self.settings.erase_before_flash
        self.install_components = self.settings.install_components
        self.last_flash_result: dict[str, Any] | None = None


STATE = State()


def run_checks() -> bool:
    ok = True
    for mod in ("textual", "requests", "serial", "esptool"):
        try:
            __import__(mod)
            print(f"[OK] {mod}")
        except Exception as e:
            print(f"[MISS] {mod}: {e}")
            ok = False
    print(f"Python {sys.version.split()[0]} on {platform.platform()}")
    return ok


class LogsModal(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, state: State):
        super().__init__()
        self.state = state
        self._auto = True

    def compose(self) -> ComposeResult:
        with Container(classes="dialog-wide"):
            yield Static(t("logs_title", self.state.settings.language), classes="panel-title")
            yield Static("Автопрокрутка включена" if self.state.settings.language == "ru" else "Auto-scroll enabled", id="log-auto")
            log_text = "\n".join(f"[{e.ts}] {e.level}: {e.message}" for e in self.state.logger.entries()) or "(пусто)"
            yield Static(log_text, id="log-text")
            with Horizontal(classes="modal-actions"):
                yield Button(t("copy_logs", self.state.settings.language), id="copy-logs")
                yield Button(t("clear_logs", self.state.settings.language), id="clear-logs")
                yield Button(t("close", self.state.settings.language), id="close-logs", variant="primary")

    def on_mount(self) -> None:
        self.set_interval(0.7, self.refresh_logs)
        self.state.logger.add_listener(self._on_entry)

    def on_unmount(self) -> None:
        try:
            self.state.logger.remove_listener(self._on_entry)
        except Exception:
            pass

    def _on_entry(self, entry):
        # will be refreshed by interval; avoid thread UI issues
        pass

    def refresh_logs(self) -> None:
        try:
            w = self.query_one("#log-text", Static)
            w.update("\n".join(f"[{e.ts}] {e.level}: {e.message}" for e in self.state.logger.entries()) or "(пусто)")
        except Exception:
            pass

    @on(Button.Pressed, "#close-logs")
    def action_close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#clear-logs")
    def clear_logs(self) -> None:
        self.state.logger.clear()
        self.refresh_logs()

    @on(Button.Pressed, "#copy-logs")
    def copy_logs(self) -> None:
        text = self.state.logger.get_text()
        copied = False
        try:
            import pyperclip  # type: ignore
            pyperclip.copy(text)
            copied = True
        except Exception:
            pass
        if not copied:
            try:
                # Textual clipboard
                self.app.copy_to_clipboard(text)
                copied = True
            except Exception:
                pass
        if copied:
            self.notify("Логи скопированы" if self.state.settings.language == "ru" else "Logs copied")
        else:
            p = Path(tempfile.gettempdir()) / "sflasher-logs.txt"
            p.write_text(text, encoding="utf-8")
            self.notify(f"Логи сохранены: {p}")


class SettingsModal(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, state: State):
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        s = self.state.settings
        lang = s.language
        with Container(classes="dialog"):
            yield Static(t("settings", lang), classes="panel-title")
            yield Static(f"{t('version', lang)}: {__version__}", classes="small")
            yield Static(f"{t('theme', lang)}: {s.theme}", id="set-theme")
            yield Horizontal(Button("◀ Theme", id="theme-prev"), Button("Theme ▶", id="theme-next"), classes="setting-row")
            yield Static(f"{t('language', lang)}: {s.language}", id="set-lang")
            yield Horizontal(Button("RU/EN", id="lang-toggle"), classes="setting-row")
            yield Static(f"{t('animations', lang)}: {'ON' if s.animations else 'OFF'}", id="set-anim")
            yield Horizontal(Button("Toggle animations", id="anim-toggle"), classes="setting-row")
            yield Static(f"{t('ui_size', lang)}: {s.ui_scale}", id="set-scale")
            yield Horizontal(Button("UI size", id="scale-toggle"), classes="setting-row")
            yield Static(f"{t('logging', lang)}: {'ON' if s.logging_enabled else 'OFF'}", id="set-log")
            yield Horizontal(Button("Toggle logging", id="log-toggle"), classes="setting-row")
            yield Static(f"{t('check_updates', lang)}: {'ON' if s.check_updates else 'OFF'}", id="set-upd")
            yield Horizontal(Button("Toggle updates", id="upd-toggle"), classes="setting-row")
            yield Static("Theme preview: ■■■■", id="theme-preview")
            with Horizontal(classes="modal-actions"):
                yield Button(t("close", lang), id="close-settings", variant="primary")

    def on_mount(self) -> None:
        self.refresh_preview()

    def refresh_labels(self) -> None:
        s = self.state.settings
        lang = s.language
        self.query_one("#set-theme", Static).update(f"{t('theme', lang)}: {s.theme}")
        self.query_one("#set-lang", Static).update(f"{t('language', lang)}: {s.language}")
        self.query_one("#set-anim", Static).update(f"{t('animations', lang)}: {'ON' if s.animations else 'OFF'}")
        self.query_one("#set-scale", Static).update(f"{t('ui_size', lang)}: {s.ui_scale}")
        self.query_one("#set-log", Static).update(f"{t('logging', lang)}: {'ON' if s.logging_enabled else 'OFF'}")
        self.query_one("#set-upd", Static).update(f"{t('check_updates', lang)}: {'ON' if s.check_updates else 'OFF'}")
        self.refresh_preview()

    def refresh_preview(self) -> None:
        theme = resolve_theme(self.state.settings.theme)
        txt = Text("Theme preview: ")
        for c in [theme.accent, theme.text, theme.success, theme.danger]:
            txt.append("■■ ", style=c)
        txt.append(theme.name, style=theme.muted)
        self.query_one("#theme-preview", Static).update(txt)

    def _apply_theme(self):
        app = self.app
        if isinstance(app, SFlasherApp):
            app.apply_theme()

    @on(Button.Pressed, "#theme-prev")
    def theme_prev(self):
        s = self.state.settings
        i = THEME_ORDER.index(s.theme) if s.theme in THEME_ORDER else 0
        s.theme = THEME_ORDER[(i - 1) % len(THEME_ORDER)]
        s.save(); self.refresh_labels(); self._apply_theme()

    @on(Button.Pressed, "#theme-next")
    def theme_next(self):
        s = self.state.settings
        i = THEME_ORDER.index(s.theme) if s.theme in THEME_ORDER else 0
        s.theme = THEME_ORDER[(i + 1) % len(THEME_ORDER)]
        s.save(); self.refresh_labels(); self._apply_theme()

    @on(Button.Pressed, "#lang-toggle")
    def lang_toggle(self):
        s = self.state.settings
        s.language = "en" if s.language == "ru" else "ru"
        s.save(); self.refresh_labels(); self.notify("Language: " + s.language)

    @on(Button.Pressed, "#anim-toggle")
    def anim_toggle(self):
        s = self.state.settings
        s.animations = not s.animations
        s.save(); self.refresh_labels()

    @on(Button.Pressed, "#scale-toggle")
    def scale_toggle(self):
        s = self.state.settings
        order = ["compact", "normal", "large"]
        i = order.index(s.ui_scale) if s.ui_scale in order else 1
        s.ui_scale = order[(i + 1) % len(order)]
        s.save(); self.refresh_labels()

    @on(Button.Pressed, "#log-toggle")
    def log_toggle(self):
        s = self.state.settings
        s.logging_enabled = not s.logging_enabled
        s.save(); self.refresh_labels()

    @on(Button.Pressed, "#upd-toggle")
    def upd_toggle(self):
        s = self.state.settings
        s.check_updates = not s.check_updates
        s.save(); self.refresh_labels()

    @on(Button.Pressed, "#close-settings")
    def action_close(self):
        self.dismiss(None)


class HomeScreen(Screen):
    def compose(self) -> ComposeResult:
        lang = STATE.settings.language
        yield Header(show_clock=False)
        with Container(id="main-wrap"):
            with Vertical(id="menu-box"):
                yield Static(load_logo(), id="logo")
                yield Static(t("app_title", lang), classes="menu-title")
                yield Button(f"🔥 {t('flash_device', lang)}", id="go-flash", classes="menu-btn", variant="primary")
                yield Button(f"⚙️ {t('settings', lang)}", id="go-settings", classes="menu-btn")
                yield Button(f"📋 {t('logs', lang)}", id="go-logs", classes="menu-btn")
                yield Button(f"❌ {t('exit', lang)}", id="go-exit", classes="exit-btn")
                yield Static(f"v{__version__} · sflasher.bot.nu", classes="small")
        yield Footer()

    @on(Button.Pressed, "#go-flash")
    def go_flash(self):
        self.app.push_screen(DeviceScreen(STATE))

    @on(Button.Pressed, "#go-settings")
    def go_settings(self):
        self.app.push_screen(SettingsModal(STATE))

    @on(Button.Pressed, "#go-logs")
    def go_logs(self):
        self.app.push_screen(LogsModal(STATE))

    @on(Button.Pressed, "#go-exit")
    def go_exit(self):
        self.app.exit()


class DeviceScreen(Screen):
    BINDINGS = [Binding("escape", "back", "Back")]

    def compose(self) -> ComposeResult:
        lang = STATE.settings.language
        yield Header(show_clock=False)
        with Vertical(id="main-wrap"):
            with Vertical(id="menu-box"):
                yield Static(t("select_device", lang), classes="panel-title")
                yield Static(t("loading_catalog", lang), id="catalog-status", classes="small")
                yield ListView(id="device-list", classes="device-list")
                with Horizontal(classes="modal-actions"):
                    yield Button(t("back", lang), id="dev-back")
                    yield Button(t("refresh", lang), id="dev-refresh")
        yield Footer()

    def on_mount(self) -> None:
        self.load_catalog()

    @work(thread=True)
    def load_catalog(self, force: bool = False) -> None:
        status = self.query_one("#catalog-status", Static)
        try:
            if STATE.catalog and not force:
                self.app.call_from_thread(self.populate_devices)
                return
            self.app.call_from_thread(status.update, t("loading_catalog", STATE.settings.language))
            data = STATE.api.fetch_catalog()
            STATE.cache.set_json("catalog.json", data)
            STATE.catalog = data
            STATE.catalog_from_cache = False
            STATE.catalog_age = time.time()
            STATE.firmware.load_from_catalog(data)
            self.app.call_from_thread(self.populate_devices)
        except Exception as e:
            log.warning("Catalog fetch failed: %s", e)
            cached, ts = STATE.cache.get_json_with_age("catalog.json")
            if isinstance(cached, dict) and isinstance(cached.get("items"), list):
                STATE.catalog = cached
                STATE.catalog_from_cache = True
                STATE.catalog_age = ts
                STATE.firmware.load_from_catalog(cached)
                self.app.call_from_thread(self.populate_devices)
                self.app.call_from_thread(status.update, t("catalog_cached", STATE.settings.language))
            else:
                self.app.call_from_thread(status.update, f"{t('site_unavailable', STATE.settings.language)}: {e}")

    def populate_devices(self) -> None:
        lv = self.query_one("#device-list", ListView)
        lv.clear()
        lang = STATE.settings.language
        status = self.query_one("#catalog-status", Static)
        count_fw = len(STATE.firmware.items)
        src = "cache" if STATE.catalog_from_cache else "online"
        status.update(f"Firmware: {count_fw} ({src}) — sflasher.bot.nu")
        for dev in STATE.devices.all():
            fws = STATE.firmware.for_device(dev.id)
            if not STATE.catalog:
                label = f"{dev.name}  [{dev.chip}]"
            else:
                label = f"{dev.name}  [{dev.chip}]  — {len(fws)} прошивок"
            lv.append(ListItem(Static(label), name=dev.id))
        if not lv.children:
            lv.append(ListItem(Static(t("no_firmware", lang))))

    @on(ListView.Selected, "#device-list")
    def selected(self, ev: ListView.Selected) -> None:
        dev_id = ev.item.name
        if dev_id:
            STATE.selected_device_id = dev_id
            self.app.push_screen(FirmwareScreen(STATE, dev_id))

    @on(Button.Pressed, "#dev-back")
    def action_back(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#dev-refresh")
    def refresh(self):
        STATE.catalog = None
        self.load_catalog(force=True)


class FirmwareScreen(Screen):
    BINDINGS = [Binding("escape", "back", "Back")]

    def __init__(self, state: State, device_id: str):
        super().__init__()
        self.state = state
        self.device_id = device_id

    def compose(self) -> ComposeResult:
        lang = self.state.settings.language
        dev = self.state.devices.get(self.device_id)
        title = f"{t('select_firmware', lang)} — {dev.name if dev else self.device_id}"
        yield Header(show_clock=False)
        with Vertical(id="main-wrap"):
            with Vertical(id="menu-box"):
                yield Static(title, classes="panel-title")
                yield ListView(id="fw-list", classes="fw-list")
                with Horizontal(classes="modal-actions"):
                    yield Button(t("back", lang), id="fw-back")
        yield Footer()

    def on_mount(self) -> None:
        lv = self.query_one("#fw-list", ListView)
        lang = self.state.settings.language
        fws = self.state.firmware.for_device(self.device_id)
        if not fws:
            lv.append(ListItem(Static(t("no_firmware", lang))))
            return
        for fw in fws:
            dl = fw.primary_download(self.device_id)
            size = fmt_size(dl.size) if dl else "—"
            lv.append(ListItem(Static(f"{fw.name}  v{fw.version}  [{size}]"), name=fw.id))

    @on(ListView.Selected, "#fw-list")
    def selected(self, ev: ListView.Selected) -> None:
        fw_id = ev.item.name
        fw = next((f for f in self.state.firmware.items if f.id == fw_id), None)
        if fw:
            self.state.selected_firmware = fw
            self.app.push_screen(PrepareScreen(self.state, self.device_id, fw))

    @on(Button.Pressed, "#fw-back")
    def action_back(self):
        self.app.pop_screen()


class PrepareScreen(Screen):
    BINDINGS = [Binding("escape", "back", "Back")]

    def __init__(self, state: State, device_id: str, firmware: Firmware):
        super().__init__()
        self.state = state
        self.device_id = device_id
        self.firmware = firmware

    def compose(self) -> ComposeResult:
        lang = self.state.settings.language
        dev = self.state.devices.get(self.device_id)
        dl = self.firmware.primary_download(self.device_id)
        extra = self.firmware.extra_component(self.device_id)
        yield Header(show_clock=False)
        with Vertical(id="main-wrap"):
            with Vertical(id="menu-box"):
                yield Static(t("prepare", lang), classes="panel-title")
                yield Static(f"{self.firmware.name} v{self.firmware.version}", classes="panel-title")
                yield Static(f"Устройство: {dev.name if dev else self.device_id}")
                yield Static(f"Размер: {fmt_size(dl.size if dl else 0)}")
                yield Static((self.firmware.description or "")[:300], classes="small")
                yield Checkbox(t("erase_before", lang), value=self.state.erase_before_flash, id="cb-erase")
                if extra:
                    yield Checkbox(f"{t('extra_components', lang)} ({fmt_size(extra.size)})", value=self.state.install_components, id="cb-extra")
                else:
                    yield Static("Доп. компоненты: недоступны для этой прошивки/устройства", classes="small")
                with Horizontal(classes="modal-actions"):
                    yield Button(t("back", lang), id="prep-back")
                    yield Button(t("connect", lang), id="prep-next", variant="primary")
        yield Footer()

    @on(Button.Pressed, "#prep-back")
    def action_back(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#prep-next")
    def next(self):
        self.state.erase_before_flash = bool(self.query_one("#cb-erase", Checkbox).value)
        try:
            self.state.install_components = bool(self.query_one("#cb-extra", Checkbox).value)
        except Exception:
            self.state.install_components = False
        self.state.settings.erase_before_flash = self.state.erase_before_flash
        self.state.settings.install_components = self.state.install_components
        self.state.settings.save()
        self.app.push_screen(ConnectScreen(self.state, self.device_id, self.firmware))


class ConnectScreen(Screen):
    BINDINGS = [Binding("escape", "back", "Back")]

    def __init__(self, state: State, device_id: str, firmware: Firmware):
        super().__init__()
        self.state = state
        self.device_id = device_id
        self.firmware = firmware
        self.ports = []

    def compose(self) -> ComposeResult:
        lang = self.state.settings.language
        dev = self.state.devices.get(self.device_id)
        yield Header(show_clock=False)
        with Vertical(id="main-wrap"):
            with Vertical(id="menu-box"):
                yield Static(t("connect", lang), classes="panel-title")
                yield Static(f"Целевое устройство: {dev.name if dev else self.device_id} ({dev.chip if dev else ''})")
                yield Static("Список портов обновляется автоматически каждые 2 сек.", classes="small")
                yield ListView(id="port-list", classes="port-list")
                yield Static("Порт не выбран", id="port-info", classes="info-box")
                with Horizontal(classes="modal-actions"):
                    yield Button(t("back", lang), id="conn-back")
                    yield Button(t("refresh", lang), id="conn-refresh")
                    yield Button(t("cancel", lang), id="conn-cancel")
                    yield Button(t("flash_btn", lang), id="conn-flash", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_ports()
        self.set_interval(2.0, self.refresh_ports)

    def refresh_ports(self) -> None:
        try:
            ports = self.state.serial.list_ports()
            self.ports = ports
            lv = self.query_one("#port-list", ListView)
            selected = self.state.selected_port
            lv.clear()
            if not ports:
                lv.append(ListItem(Static(t("no_ports", self.state.settings.language))))
                self.state.selected_port = None
                self.query_one("#port-info", Static).update("Порт не выбран")
                return
            for p in ports:
                label = f"{p.device} — {p.description} — {p.chipset}"
                lv.append(ListItem(Static(label), name=p.device))
            if selected and any(p.device == selected for p in ports):
                self.state.selected_port = selected
                self.update_port_info(selected)
            elif self.state.selected_port not in [p.device for p in ports]:
                self.state.selected_port = None
                self.query_one("#port-info", Static).update("Порт не выбран")
        except Exception as e:
            log.exception("Port refresh failed")
            try:
                self.query_one("#port-info", Static).update(f"Ошибка чтения портов: {e}")
            except Exception:
                pass

    def update_port_info(self, device: str) -> None:
        p = next((x for x in self.ports if x.device == device), None)
        if not p:
            return
        dev = self.state.devices.get(self.device_id)
        compat = "неизвестно"
        if dev:
            if dev.chip == "ESP32-S3" and "ESP32-S3" in p.chipset:
                compat = "OK"
            elif dev.chip == "ESP32" and p.chipset in ("ESP32", "CP210x (ESP-compatible)", "CH340 (ESP-compatible)", "CH9102 (ESP-compatible)"):
                compat = "вероятно OK"
            elif p.chipset == "Unknown chipset":
                compat = "не удалось определить"
            else:
                compat = "проверьте вручную"
        self.query_one("#port-info", Static).update(
            f"Порт: {p.device}\nОписание: {p.description}\nЧипсет: {p.chipset}\nСовместимость: {compat}\nПрошивка: {self.firmware.name} v{self.firmware.version}"
        )

    @on(ListView.Selected, "#port-list")
    def port_selected(self, ev: ListView.Selected) -> None:
        if ev.item.name:
            self.state.selected_port = ev.item.name
            self.update_port_info(ev.item.name)

    @on(Button.Pressed, "#conn-back")
    def action_back(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#conn-refresh")
    def manual_refresh(self):
        self.refresh_ports()

    @on(Button.Pressed, "#conn-cancel")
    def cancel(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#conn-flash")
    def start_flash(self):
        if not self.state.selected_port:
            self.notify("Выберите порт" if self.state.settings.language == "ru" else "Select a port", severity="error")
            return
        # Basic compatibility warning
        dev = self.state.devices.get(self.device_id)
        port = next((p for p in self.ports if p.device == self.state.selected_port), None)
        if dev and port and dev.chip == "ESP32-S3" and port.chipset == "ESP32":
            self.notify("Внимание: выбран порт ESP32, а устройство ESP32-S3", severity="warning")
        self.app.push_screen(FlashScreen(self.state, self.device_id, self.firmware, self.state.selected_port))


class FlashScreen(Screen):
    BINDINGS = [Binding("escape", "noop", "Noop")]

    def __init__(self, state: State, device_id: str, firmware: Firmware, port: str):
        super().__init__()
        self.state = state
        self.device_id = device_id
        self.firmware = firmware
        self.port = port
        self._done = False
        self._ok = False

    def compose(self) -> ComposeResult:
        lang = self.state.settings.language
        dev = self.state.devices.get(self.device_id)
        yield Header(show_clock=False)
        with Container(id="flash-wrap"):
            with Vertical(id="flash-box"):
                yield Static(t("flashing", lang), classes="panel-title")
                yield Static(f"{dev.name if dev else self.device_id} · {self.firmware.name} v{self.firmware.version}", classes="small")
                yield Static("0%", id="flash-percent")
                yield ProgressBar(total=100, show_eta=False, id="flash-bar")
                yield Static("Подготовка...", id="flash-stage", classes="small")
                yield Static("", id="flash-result", classes="info-box")
                with Horizontal(classes="modal-actions"):
                    yield Button("📋 " + t("logs", lang), id="flash-logs")
                    yield Button(t("cancel", lang), id="flash-cancel", classes="exit-btn")
                    yield Button(t("restart_device", lang), id="flash-restart", variant="primary")
                    yield Button(t("back", lang), id="flash-back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#flash-restart").display = False
        self.query_one("#flash-back").display = False
        self.run_flash()

    def action_noop(self):
        return

    def _ui(self, fn, *args):
        try:
            self.app.call_from_thread(fn, *args)
        except Exception:
            pass

    def _set_percent(self, pct: int, stage: str = ""):
        pct = max(0, min(100, int(pct)))
        self.query_one("#flash-percent", Static).update(f"{pct}%")
        self.query_one("#flash-bar", ProgressBar).update(progress=pct)
        if stage:
            self.query_one("#flash-stage", Static).update(stage)

    def _log(self, msg: str):
        log.info(msg)

    @work(thread=True)
    def run_flash(self) -> None:
        lang = self.state.settings.language
        dev = self.state.devices.get(self.device_id)
        dl = self.firmware.primary_download(self.device_id)
        if not dl:
            self._ui(self.finish_fail, "Нет файла прошивки для выбранного устройства")
            return
        try:
            self._ui(self._set_percent, 1, "Загрузка прошивки")
            self._log(f"Старт прошивки: {self.firmware.name} v{self.firmware.version} -> {self.port}")

            def dl_prog(got, total):
                if total > 0:
                    pct = int(got * 15 / total)
                    self._ui(self._set_percent, 1 + pct, f"Загрузка прошивки {fmt_size(got)}/{fmt_size(total)}")

            fw_path = self.state.downloads.download(dl.url, f"{self.firmware.id}-{self.device_id}.{dl.format or 'bin'}", dl.size or None, dl_prog)
            self._ui(self._set_percent, 16, "Проверка файла")
            data = fw_path.read_bytes()
            self._log(f"Файл загружен: {fw_path} ({len(data)} bytes), sha256={self.state.api.sha256(data)}")
            if len(data) < 1024:
                raise RuntimeError("Скачанный файл слишком мал — похоже на ошибку")

            # Compatibility basic check for bin images
            if fw_path.suffix.lower() == ".bin" and data[:1] != b"\xE9" and not fw_path.name.lower().endswith(".zip"):
                self._log("Предупреждение: файл не начинается с ESP image magic 0xE9")

            extra = self.firmware.extra_component(self.device_id) if self.state.install_components else None
            extra_path = None
            if extra:
                self._ui(self._set_percent, 17, "Загрузка доп. компонентов")
                extra_path = self.state.downloads.download(extra.url, f"{self.firmware.id}-{self.device_id}-extra.zip", extra.size or None)
                self._log(f"Доп. компоненты загружены: {extra_path} ({extra_path.stat().st_size} bytes)")

            self._ui(self._set_percent, 18, "Подключение к устройству")
            if not self.state.serial.port_present(self.port):
                raise RuntimeError(f"Порт {self.port} не найден. Подключите устройство и попробуйте снова.")

            def progress_cb(pct, stage):
                self._ui(self._set_percent, pct, stage)

            def log_cb(msg):
                self._log(msg)

            result = self.state.flash.flash(self.port, self.device_id, fw_path, erase=self.state.erase_before_flash,
                                            log_cb=log_cb, progress_cb=progress_cb)
            if not result.ok:
                self._ui(self.finish_fail, result.message)
                return

            if extra_path and extra_path.exists():
                self._ui(self._set_percent, 95, "Загрузка дополнительных компонентов...")
                self._log("Установка дополнительных компонентов")
                try:
                    fw_bytes = fw_path.read_bytes()
                    # if zip package, try to read merged bin inside? Use first .bin for partition scan
                    scan_bytes = fw_bytes
                    if fw_path.suffix.lower() == ".zip":
                        import zipfile, io
                        with zipfile.ZipFile(fw_path) as zf:
                            bins = [n for n in zf.namelist() if n.lower().endswith('.bin')]
                            if bins:
                                scan_bytes = zf.read(bins[0])
                    parts = parse_partition_table(scan_bytes)
                    fs_part = find_fs_partition(parts)
                    if not fs_part:
                        self._log("FS раздел не найден в прошивке; доп. компоненты пропущены")
                    else:
                        img = build_littlefs_image(extra_path, int(fs_part['size']), log_cb)
                        if img:
                            wr = self.state.flash.write_image(self.port, self.device_id, int(fs_part['address']), img, log_cb=log_cb,
                                                              progress_cb=progress_cb, progress_base=95, progress_span=4, stage="Запись доп. компонентов")
                            if not wr.ok:
                                self._log(f"Ошибка установки доп. компонентов: {wr.message}")
                        else:
                            self._log("Образ LittleFS не создан; доп. компоненты пропущены")
                except Exception as e:
                    self._log(f"Ошибка доп. компонентов: {e}")

            self._ui(self.finish_ok)
        except Exception as e:
            log.exception("Flash failed")
            self._ui(self.finish_fail, str(e))

    def finish_ok(self):
        self._done = True
        self._ok = True
        dev = self.state.devices.get(self.device_id)
        self._set_percent(100, t("done", self.state.settings.language))
        self.query_one("#flash-result", Static).update(
            f"[green]{t('success', self.state.settings.language)}[/green]\n"
            f"Устройство: {dev.name if dev else self.device_id}\n"
            f"Прошивка: {self.firmware.name} v{self.firmware.version}\n"
            f"Порт: {self.port}"
        )
        self.query_one("#flash-cancel").display = False
        self.query_one("#flash-restart").display = True
        self.query_one("#flash-back").display = True
        self.state.last_flash_result = {"ok": True, "device": self.device_id, "firmware": self.firmware.id}

    def finish_fail(self, message: str):
        self._done = True
        self._ok = False
        self.query_one("#flash-stage", Static).update("Ошибка")
        self.query_one("#flash-result", Static).update(f"[red]Ошибка:[/red] {message}\nПодробности смотрите в логах.")
        self.query_one("#flash-cancel").display = False
        self.query_one("#flash-back").display = True
        self.state.last_flash_result = {"ok": False, "error": message}

    @on(Button.Pressed, "#flash-logs")
    def open_logs(self):
        self.app.push_screen(LogsModal(self.state))

    @on(Button.Pressed, "#flash-cancel")
    def cancel(self):
        if self._done:
            return
        self.state.flash.cancel()
        self._log("Пользователь запросил отмену")
        self.query_one("#flash-stage", Static).update("Отмена...")

    @on(Button.Pressed, "#flash-restart")
    def restart(self):
        res = self.state.flash.hard_reset(self.port, self.device_id, log_cb=self._log)
        if res.ok:
            self.notify("Команда перезапуска отправлена")
        else:
            self.notify(res.message, severity="error")

    @on(Button.Pressed, "#flash-back")
    def back(self):
        # go back to home
        while len(self.app.screen_stack) > 2:
            self.app.pop_screen()


class BootScreen(Screen):
    def compose(self) -> ComposeResult:
        with Container(id="boot"):
            yield Static("", id="logo")
            yield Static("Загрузка ShlepaFlash CLI...", id="boot-status")
            yield Static("", id="boot-bar")

    def on_mount(self) -> None:
        self._pct = 0
        self._glare = 0
        self.set_interval(0.06, self._tick_glare)
        self.run_boot()

    def _render_bar(self) -> Text:
        width = 48
        filled = int(width * self._pct / 100)
        t = Text()
        for i in range(width):
            if i < filled:
                # moving white glare
                d = abs(i - self._glare)
                if d <= 1:
                    t.append("█", style="bold white")
                elif d <= 3:
                    t.append("█", style="#ffb066")
                else:
                    t.append("█", style="#ff6a00")
            else:
                t.append("░", style="#333333")
        t.append(f" {self._pct:3d}%", style="#aaaaaa")
        return t

    def _tick_glare(self):
        width = 48
        filled = max(1, int(width * self._pct / 100))
        self._glare = (self._glare + 1) % max(1, filled + 4)
        try:
            self.query_one("#boot-bar", Static).update(self._render_bar())
        except Exception:
            pass

    @work(thread=True)
    def run_boot(self) -> None:
        steps = [
            (10, "Инициализация..."),
            (25, "Загрузка настроек..."),
            (45, "Подготовка модулей..."),
            (65, "Проверка кэша каталога..."),
            (85, "Подключение к sflasher.bot.nu..."),
            (100, "Готово"),
        ]
        for pct, msg in steps:
            self._pct = pct
            self.app.call_from_thread(self._upd, pct, msg)
            time.sleep(0.22 if STATE.settings.animations else 0.02)
        try:
            cached, ts = STATE.cache.get_json_with_age("catalog.json")
            if isinstance(cached, dict):
                STATE.catalog = cached
                STATE.catalog_from_cache = True
                STATE.catalog_age = ts
                STATE.firmware.load_from_catalog(cached)
        except Exception:
            pass
        time.sleep(0.2 if STATE.settings.animations else 0)
        self.app.call_from_thread(self._show_logo)

    def _upd(self, pct, msg):
        self._pct = pct
        self.query_one("#boot-status", Static).update(msg)
        self.query_one("#boot-bar", Static).update(self._render_bar())

    def _show_logo(self):
        self.query_one("#boot-bar", Static).update("")
        self.query_one("#boot-status", Static).update("")
        self.query_one("#logo", Static).update(Text(load_logo(), style="#ff6a00"))
        self.set_timer(0.8 if STATE.settings.animations else 0.05, self.finish)

    def finish(self):
        try:
            self.app.pop_screen()
        except Exception:
            pass
        self.app.push_screen(HomeScreen())


class SFlasherApp(App):
    TITLE = "ShlepaFlash CLI"
    CSS_PATH = "ui/styles.tcss"
    BINDINGS = [Binding("q", "quit", "Quit", show=False)]

    def on_mount(self) -> None:
        self.apply_theme()
        self.push_screen(BootScreen())
        self.check_updates_bg()

    def apply_theme(self) -> None:
        theme = resolve_theme(STATE.settings.theme)
        css = (Path(__file__).resolve().parent / "ui" / "styles.tcss").read_text(encoding="utf-8")
        extra = f"""
Screen {{ background: {theme.bg}; color: {theme.text}; }}
#menu-box, .dialog, .dialog-wide, #flash-box {{ background: {theme.panel}; border: solid {theme.border}; }}
Button {{ background: {theme.panel_alt}; color: {theme.text}; border: solid {theme.border}; }}
Button:hover {{ border: solid {theme.accent}; color: {theme.accent}; }}
Button.-primary, Button#conn-flash, Button#prep-next {{ background: {theme.accent}; color: {theme.accent_text}; border: solid {theme.accent}; }}
Button.exit-btn, Button#flash-cancel {{ color: {theme.danger}; border: solid {theme.danger}; background: {theme.panel_alt}; }}
Button.exit-btn:hover, Button#flash-cancel:hover {{ background: {theme.danger}; color: white; }}
.small, #boot-status, #flash-stage {{ color: {theme.muted}; }}
#flash-percent {{ color: {theme.accent}; }}
ProgressBar > .bar--bar {{ color: {theme.accent}; }}
"""
        self.CSS = css + "\n" + extra
        try:
            self.refresh_css()
        except Exception:
            pass
        try:
            self.screen.styles.background = theme.bg
            self.screen.styles.color = theme.text
        except Exception:
            pass

    @work(thread=True)
    def check_updates_bg(self) -> None:
        if not STATE.settings.check_updates:
            return
        info = check_update()
        if info and info.available:
            self.call_from_thread(self.notify, f"Доступно обновление: {info.latest} ({info.url})", severity="information")


def run() -> int:
    try:
        app = SFlasherApp()
        app.run(mouse=True)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        log.exception("Fatal error")
        print("Критическая ошибка. Подробности в логах.", file=sys.stderr)
        return 1

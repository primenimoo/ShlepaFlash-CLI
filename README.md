<p align="center">
  <img src="https://sflasher.bot.nu/shlepaflash-logo.svg" alt="ShlepaFlash" width="420">
</p>

<p align="center">
  <b>Cross-platform terminal flasher for ShlepaFlash-supported ESP32 devices</b><br>
  TUI • Real catalog sync • Real esptool flashing • Themes • Logs
</p>

<p align="center">
  <a href="https://sflasher.bot.nu"><img alt="Website" src="https://img.shields.io/badge/Website-sflasher.bot.nu-ff6a00?style=for-the-badge&logo=googlechrome&logoColor=white"></a>
  <a href="https://t.me/primenimooo"><img alt="Telegram" src="https://img.shields.io/badge/Telegram-@primenimooo-ff6a00?style=for-the-badge&logo=telegram&logoColor=white"></a>
  <a href="https://www.tiktok.com/@primenimooo"><img alt="TikTok" src="https://img.shields.io/badge/TikTok-@primenimooo-ff6a00?style=for-the-badge&logo=tiktok&logoColor=white"></a>
</p>

---

## 🇬🇧 English | 🇷🇺 Русский

- [English](#english)
- [Русский](#русский)

---

## English

### Overview

**ShlepaFlash CLI** is a standalone cross-platform terminal application for flashing supported ESP32 devices with firmware from the [ShlepaFlash catalog](https://sflasher.bot.nu). It provides an interactive TUI (mouse + keyboard), real firmware synchronization, real flashing via `esptool`, logs, settings, and themes.

> ⚠️ **Status:** This repository contains a working Linux-focused implementation and code paths for Windows/macOS. Physical flashing was not fully validated on every supported device in this environment. See [Testing](#-testing).

### ✨ Features

- 🖥️ **Interactive TUI** — menu, device/firmware selection, modals, mouse and keyboard navigation.
- 🌍 **Cross-platform target** — Linux, Windows 10/11, macOS (Python 3.10+).
- 🔄 **Real catalog sync** — fetches firmware catalog from `https://sflasher.bot.nu/api?action=list`.
- 💾 **Cache fallback** — uses cached catalog when site is unavailable.
- 🔌 **Serial port detection** — auto-refresh every 2 seconds + manual refresh.
- 🔥 **Real flashing** — uses `esptool` for erase/write/reset operations.
- 📦 **ZIP/package planning** — detects manifest/flash_args/bin components in package archives.
- 🧩 **Extra components** — downloads extra component ZIP; attempts LittleFS image creation/flashing when FS partition and LittleFS tooling are available.
- 📋 **Logs modal** — live logs, copy/save, clear.
- ⚙️ **Settings** — theme, language, animations, UI size, logging, update check, version.
- 🎨 **Themes** — Dark, Light, Orange, Blue, Purple, Green, Red, Monochrome, Auto.
- 🚀 **One command** — run with `sflasher`.

### 🧰 Supported OS

| OS | Status |
|---|---|
| 🐧 Linux | Implemented / tested in this environment (limited) |
| 🪟 Windows 10/11 | Implemented, requires validation on real Windows machine |
| 🍎 macOS | Implemented, requires validation on real macOS machine |

### 📟 Supported Devices (from ShlepaFlash catalog mapping)

| Device | Chip | Notes |
|---|---|---|
| M5StickC Plus 2 | ESP32 | Supported by catalog |
| M5StickC Plus | ESP32 | Supported by catalog |
| M5Stick S3 | ESP32-S3 | Supported by catalog |
| T-Embed CC1101 | ESP32-S3 | Supported by catalog |
| Flux ESP32-S3 | ESP32-S3 | Supported by catalog |
| M5Stack Cardputer | ESP32-S3 | Supported by catalog |
| M5Stack Cardputer ADV | ESP32-S3 | Supported by catalog |
| CYD-2432S028 | ESP32 | Supported by catalog |

> The CLI only shows/install firmware that is marked compatible in the ShlepaFlash catalog.

### 📦 Supported Firmware

Firmware is loaded dynamically from ShlepaFlash. Examples currently present in catalog may include:

- Bruce Firmware
- CatHack
- M5 Launcher
- Marauder
- Nemo
- other firmware published on ShlepaFlash

Use the app to see the live, device-compatible list.

### 📥 Installation

#### Linux / macOS (shell)

```bash
curl -fsSL https://raw.githubusercontent.com/primenimoo/ShlepaFlash-CLI/main/install.sh | bash
```

#### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/primenimoo/ShlepaFlash-CLI/main/install.ps1 | iex
```

#### Manual install (all OS)

```bash
git clone https://github.com/primenimoo/ShlepaFlash-CLI.git
cd ShlepaFlash-CLI
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1
pip install -U pip
pip install .
sflasher
```

### 🚀 Run

```bash
sflasher
```

Checks:

```bash
sflasher --check
sflasher --version
```

### 🔥 Flashing Guide

1. Run `sflasher`.
2. Open **Flash device**.
3. Select your device.
4. Select compatible firmware.
5. Optionally enable **Erase before flashing** and **Install additional components**.
6. Select the serial port (auto-refresh every 2s).
7. Press **Flash device**.
8. Watch real progress and logs.
9. After success, use **Restart Device** if supported.

### ⚙️ Settings

- Theme: Auto/Dark/Light/Orange/Blue/Purple/Green/Red/Monochrome
- Language: RU/EN
- Animations: on/off
- UI size: compact/normal/large
- Logging: on/off
- Update checks: on/off
- Version info

Settings are saved in the user config directory.

### 🧪 Testing

What was checked in this environment:

- Python syntax compile: `python3 -m py_compile sflasher_cli/*.py sflasher_cli/ui/__init__.py` ✅
- Core unit tests: `pytest -q` *(run results listed in repository issue/PR or CI when available)*
- Catalog API shape inspected from `https://sflasher.bot.nu/api?action=list` ✅
- Real physical ESP32 flashing: **not performed in this environment** ⚠️
- Windows/macOS runtime: **not physically validated here** ⚠️

### 🛠 Troubleshooting

| Problem | Solution |
|---|---|
| `sflasher: command not found` | Add install bin dir to PATH (`~/.local/bin` or `%USERPROFILE%\.local\bin`) |
| No serial ports | Check USB cable/data cable, drivers (CH340/CP210x), permissions (`dialout` on Linux) |
| Site unavailable | CLI uses cached catalog if available; check internet connection |
| Flash fails | Open Logs, check port, cable, boot mode, chip compatibility, power |
| Extra components skipped | LittleFS tool/python package may be missing; main firmware can still be flashed |

### FAQ

**Does it use fake progress?**  
No. Flash progress is parsed from real `esptool` output; download progress uses actual bytes.

**Does it flash unsupported devices?**  
It warns about compatibility and uses catalog device mapping; do not force incompatible firmware.

**Where are logs/settings/cache?**  
In platform user directories (via `platformdirs`).

### 📄 License

MIT — see [LICENSE](./LICENSE).

### 🔗 Official Links

- Website: https://sflasher.bot.nu
- Telegram: https://t.me/primenimooo
- TikTok: https://www.tiktok.com/@primenimooo

---

## Русский

### Обзор

**ShlepaFlash CLI** — самостоятельное кроссплатформенное терминальное приложение для прошивки поддерживаемых ESP32-устройств прошивками из каталога [ShlepaFlash](https://sflasher.bot.nu). Интерфейс работает в терминале, поддерживает мышь и клавиатуру, синхронизируется с сайтом и использует реальный `esptool` для прошивки.

### Возможности

- Интерактивный TUI-интерфейс
- Синхронизация каталога с `sflasher.bot.nu`
- Кэш каталога при недоступности сайта
- Автообновление Serial-портов каждые 2 секунды
- Реальная прошивка через `esptool`
- Логи, настройки, темы
- Подготовка к доп. компонентам (LittleFS, если доступен инструмент)

### Установка

#### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/primenimoo/ShlepaFlash-CLI/main/install.sh | bash
```

#### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/primenimoo/ShlepaFlash-CLI/main/install.ps1 | iex
```

### Запуск

```bash
sflasher
```

### Важно

- Физическая прошивка всех устройств в этой среде не проверялась.
- Windows/macOS требуют проверки на реальных машинах.
- Не используйте несовместимые прошивки и проверяйте выбранный порт перед прошивкой.

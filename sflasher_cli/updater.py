from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

from . import __version__

log = logging.getLogger("sflasher.updater")
REPO = "primenimoo/ShlepaFlash-CLI"
GITHUB_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RAW_VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/main/sflasher_cli/__init__.py"
RAW_PYPROJECT_URL = f"https://raw.githubusercontent.com/{REPO}/main/pyproject.toml"


@dataclass
class UpdateInfo:
    current: str
    latest: str
    url: str
    available: bool
    notes: str = ""


def _parse_version(v: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(v))
    return tuple(int(p) for p in parts[:4]) or (0,)


def _is_newer(latest: str, current: str) -> bool:
    try:
        return _parse_version(latest) > _parse_version(current)
    except Exception:
        return latest.strip() != current.strip()


def _fetch_latest_from_release(timeout: float) -> UpdateInfo | None:
    try:
        r = requests.get(
            GITHUB_LATEST,
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "ShlepaFlash-CLI"},
        )
        if r.status_code != 200:
            return None
        data = r.json()
        latest = str(data.get("tag_name") or "").lstrip("v").strip()
        url = str(data.get("html_url") or f"https://github.com/{REPO}")
        notes = str(data.get("body") or "").strip()[:500]
        if not latest:
            return None
        return UpdateInfo(current=__version__, latest=latest, url=url, available=_is_newer(latest, __version__), notes=notes)
    except Exception as e:
        log.debug("Release check failed: %s", e)
        return None


def _fetch_latest_from_raw(timeout: float) -> UpdateInfo | None:
    for url in (RAW_VERSION_URL, RAW_PYPROJECT_URL):
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "ShlepaFlash-CLI"})
            if r.status_code != 200:
                continue
            text = r.text
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
            if not m:
                m = re.search(r'version\s*=\s*["\']([^"\']+)["\']', text)
            if not m:
                continue
            latest = m.group(1).strip().lstrip("v")
            if latest:
                return UpdateInfo(
                    current=__version__,
                    latest=latest,
                    url=f"https://github.com/{REPO}",
                    available=_is_newer(latest, __version__),
                )
        except Exception as e:
            log.debug("Raw version check failed: %s", e)
    return None


def check_update(timeout: float = 8.0) -> UpdateInfo | None:
    info = _fetch_latest_from_release(timeout)
    if info is not None:
        return info
    return _fetch_latest_from_raw(timeout)


def _install_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("SFLASHER_INSTALL_DIR") or (Path.home() / ".shlepaflash-cli"))
    return Path(os.environ.get("SFLASHER_INSTALL_DIR") or (Path.home() / ".local/share/shlepaflash-cli"))


def perform_update(log_cb=None) -> tuple[bool, str]:
    """Update ShlepaFlash CLI in place. Returns (ok, message)."""
    def emit(msg: str):
        log.info(msg)
        if log_cb:
            try:
                log_cb(msg)
            except Exception:
                pass

    install_dir = _install_dir()
    repo_dir = install_dir / "repo"
    venv_dir = install_dir / "venv"
    repo_url = f"https://github.com/{REPO}.git"

    try:
        emit(f"Install dir: {install_dir}")
        if repo_dir.exists() and (repo_dir / ".git").exists():
            emit("Updating repository...")
            git = shutil.which("git") or "git"
            p = subprocess.run([git, "-C", str(repo_dir), "pull", "--ff-only"], capture_output=True, text=True)
            if p.stdout.strip():
                emit(p.stdout.strip())
            if p.returncode != 0:
                emit(p.stderr.strip() or "git pull failed, recloning...")
                shutil.rmtree(repo_dir, ignore_errors=True)

        if not repo_dir.exists():
            emit("Cloning repository...")
            git = shutil.which("git") or "git"
            install_dir.mkdir(parents=True, exist_ok=True)
            p = subprocess.run([git, "clone", "--depth", "1", repo_url, str(repo_dir)], capture_output=True, text=True)
            if p.returncode != 0:
                return False, p.stderr.strip() or p.stdout.strip() or "git clone failed"

        py = None
        if os.name == "nt":
            cand = venv_dir / "Scripts" / "python.exe"
            if cand.exists():
                py = str(cand)
        else:
            cand = venv_dir / "bin" / "python"
            if cand.exists():
                py = str(cand)
        if not py:
            py = sys.executable

        emit("Installing updated package...")
        p = subprocess.run([py, "-m", "pip", "install", "--upgrade", str(repo_dir)], capture_output=True, text=True)
        if p.returncode != 0:
            msg = (p.stderr or p.stdout or "pip install failed").strip()
            emit(msg[-1000:])
            return False, msg[-500:]
        emit("Update installed successfully.")
        return True, "OK"
    except Exception as e:
        log.exception("Update failed")
        return False, str(e)


def relaunch_app() -> None:
    """Best-effort relaunch of sflasher after exit."""
    try:
        if os.name == "nt":
            bin_dir = Path.home() / ".local" / "bin"
            cmd_exe = bin_dir / "sflasher.cmd"
            if cmd_exe.exists():
                subprocess.Popen(["cmd", "/c", "start", "", str(cmd_exe)],
                                 cwd=str(Path.home()), close_fds=True)
                return
            subprocess.Popen(["cmd", "/c", "start", "", "sflasher"], cwd=str(Path.home()), close_fds=True)
            return
        sflasher = shutil.which("sflasher")
        if sflasher:
            subprocess.Popen([sflasher], start_new_session=True, cwd=str(Path.home()))
            return
        subprocess.Popen([sys.executable, "-m", "sflasher_cli"], start_new_session=True, cwd=str(Path.home()))
    except Exception:
        log.exception("Relaunch failed")

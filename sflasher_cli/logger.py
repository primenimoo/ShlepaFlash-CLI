from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import log_dir


@dataclass
class LogEntry:
    ts: str
    level: str
    message: str


class RingLogHandler(logging.Handler):
    def __init__(self, ring: deque[LogEntry], on_entry: Callable[[LogEntry], None] | None = None):
        super().__init__()
        self.ring = ring
        self.on_entry = on_entry

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = LogEntry(
                ts=datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                level=record.levelname,
                message=self.format(record),
            )
            self.ring.append(entry)
            if self.on_entry:
                self.on_entry(entry)
        except Exception:
            pass


class AppLogger:
    def __init__(self, enabled: bool = True, level: str = "INFO") -> None:
        self.ring: deque[LogEntry] = deque(maxlen=2000)
        self._listeners: list[Callable[[LogEntry], None]] = []
        self._lock = threading.Lock()
        self.logger = logging.getLogger("sflasher")
        self.logger.handlers.clear()
        self.logger.propagate = False
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.enabled = enabled
        self.file_path = log_dir() / "sflasher.log"

        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        ring_handler = RingLogHandler(self.ring, self._notify)
        ring_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(ring_handler)

        if enabled:
            try:
                fh = logging.FileHandler(self.file_path, encoding="utf-8")
                fh.setFormatter(formatter)
                self.logger.addHandler(fh)
            except Exception:
                pass

    def _notify(self, entry: LogEntry) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(entry)
            except Exception:
                pass

    def add_listener(self, cb: Callable[[LogEntry], None]) -> None:
        with self._lock:
            self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[LogEntry], None]) -> None:
        with self._lock:
            self._listeners = [l for l in self._listeners if l != cb]

    def entries(self) -> list[LogEntry]:
        return list(self.ring)

    def clear(self) -> None:
        self.ring.clear()

    def get_text(self) -> str:
        return "\n".join(f"[{e.ts}] {e.level}: {e.message}" for e in self.ring)

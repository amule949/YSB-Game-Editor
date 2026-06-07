# -*- coding: utf-8 -*-
"""Engine boundary audit helpers for the PageEngine / ProjectEngine split.

This module is diagnostic-first.  It must never crash the app and it must not
change editing data.  The goal is to show where old MainWindow-wide routes
(load/mode_chg/ref_tab/save/top-level popups) are still being awakened during
page-local work.
"""
from __future__ import annotations

import inspect
import os
import time
from pathlib import Path
from typing import Any, Iterable

try:
    from ysb.utils.runtime_logger import append_log, make_log_path, memory_text
except Exception:  # pragma: no cover - best-effort fallback
    append_log = None  # type: ignore
    make_log_path = None  # type: ignore

    def memory_text() -> str:  # type: ignore
        return "unknown"


class YSBEngineBoundaryAudit:
    """Small runtime audit logger for engine split residue.

    The audit records only compact state and call-site hints.  It is intended to
    be left enabled during refactor testing, then disabled from app_options if it
    becomes noisy.
    """

    def __init__(self, *, enabled: bool = True, log_path: str | os.PathLike[str] | None = None):
        self.enabled = bool(enabled)
        self.log_path = Path(log_path) if log_path else (make_log_path("engine_boundary") if make_log_path else None)
        self._last_by_key: dict[str, float] = {}
        self.start_time = time.monotonic()
        self.event_count = 0
        self.note("AUDIT_INIT", enabled=self.enabled, log_path=str(self.log_path) if self.log_path else "None")

    def note(self, event: str, *, throttle_ms: int = 0, stack: bool = False, **fields: Any) -> None:
        if not self.enabled or self.log_path is None or append_log is None:
            return
        try:
            key = str(event)
            if throttle_ms and throttle_ms > 0:
                now = time.monotonic() * 1000.0
                last = self._last_by_key.get(key)
                if last is not None and (now - last) < float(throttle_ms):
                    return
                self._last_by_key[key] = now
            self.event_count += 1
            fields.setdefault("memory", memory_text())
            if stack:
                fields.setdefault("caller", self.short_stack(skip=2))
            append_log(self.log_path, str(event), **fields)
        except Exception:
            pass

    def short_stack(self, *, skip: int = 1, limit: int = 5) -> str:
        try:
            frames = inspect.stack()[skip:skip + limit]
            parts: list[str] = []
            for fr in frames:
                filename = os.path.basename(fr.filename)
                parts.append(f"{filename}:{fr.lineno}:{fr.function}")
            return " <- ".join(parts)
        except Exception:
            return "unknown"

    def widget_summary(self, widgets: Iterable[Any]) -> list[str]:
        out: list[str] = []
        for w in list(widgets or []):
            try:
                cls = type(w).__name__
                title = ""
                try:
                    title = str(w.windowTitle() or "")
                except Exception:
                    title = ""
                obj = ""
                try:
                    obj = str(w.objectName() or "")
                except Exception:
                    obj = ""
                visible = bool(w.isVisible()) if hasattr(w, "isVisible") else False
                parent = w.parent() if hasattr(w, "parent") else None
                flags = int(w.windowFlags()) if hasattr(w, "windowFlags") else 0
                suspect = bool(visible and parent is None and cls not in {"MainWindow", "QMainWindow", "QApplication"})
                out.append(f"{cls}(obj={obj!r},title={title!r},visible={visible},parent_none={parent is None},flags={flags},suspect={suspect})")
            except Exception:
                continue
        return out

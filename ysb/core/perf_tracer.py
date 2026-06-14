# -*- coding: utf-8 -*-
"""Best-effort performance timing logger for YSB Game Editor.

This logger is diagnostic-only. It must never crash the app or mutate project
state. The goal is to make every user-visible action measurable so optimization
work can be based on timings instead of guesses.
"""
from __future__ import annotations

import inspect
import os
import time
from pathlib import Path
from typing import Any

try:
    from ysb.utils.runtime_logger import append_log, make_log_path, memory_text
except Exception:  # pragma: no cover
    append_log = None  # type: ignore
    make_log_path = None  # type: ignore

    def memory_text() -> str:  # type: ignore
        return "unknown"

_LOG_PATH: Path | None = None
_ACTION_SEQ = 0


def perf_counter() -> float:
    return time.perf_counter()


def elapsed_ms(start: float | int | None) -> int:
    try:
        return int(round((time.perf_counter() - float(start)) * 1000.0))
    except Exception:
        return -1


def _enabled(owner: Any = None) -> bool:
    try:
        opts = getattr(owner, "app_options", None)
        if isinstance(opts, dict):
            return bool(opts.get("performance_timing_enabled", True))
    except Exception:
        pass
    return True


def _path() -> Path | None:
    global _LOG_PATH
    if _LOG_PATH is not None:
        return _LOG_PATH
    try:
        _LOG_PATH = make_log_path("performance_timing") if make_log_path else None
    except Exception:
        _LOG_PATH = None
    return _LOG_PATH


def next_action_id(prefix: str = "action") -> str:
    global _ACTION_SEQ
    try:
        _ACTION_SEQ += 1
        return f"{prefix}-{int(time.time() * 1000)}-{_ACTION_SEQ}"
    except Exception:
        return str(prefix or "action")


def short_stack(skip: int = 2, limit: int = 5) -> str:
    try:
        frames = inspect.stack()[skip:skip + limit]
        parts: list[str] = []
        for fr in frames:
            parts.append(f"{os.path.basename(fr.filename)}:{fr.lineno}:{fr.function}")
        return " <- ".join(parts)
    except Exception:
        return "unknown"


def log(owner: Any, event: str, **fields: Any) -> None:
    if not _enabled(owner):
        return
    p = _path()
    if p is None or append_log is None:
        return
    try:
        fields.setdefault("memory", memory_text())
        try:
            fields.setdefault("page_idx", int(getattr(owner, "idx", -1)))
        except Exception:
            pass
        try:
            cb = getattr(owner, "cb_mode", None)
            if cb is not None and hasattr(cb, "currentIndex"):
                fields.setdefault("mode", int(cb.currentIndex()))
        except Exception:
            pass
        try:
            project_dir = str(getattr(owner, "project_dir", "") or "")
            if project_dir:
                fields.setdefault("project", project_dir)
        except Exception:
            pass
        append_log(p, str(event or "PERF"), **fields)
    except Exception:
        pass


def log_elapsed(owner: Any, event: str, start: float | int | None, **fields: Any) -> None:
    try:
        fields.setdefault("elapsed_ms", elapsed_ms(start))
        log(owner, event, **fields)
    except Exception:
        pass


class span:
    """Tiny context manager for timing a block.

    Example:
        with span(self, "PERF_USER_ACTION", action="save"):
            ...
    """

    def __init__(self, owner: Any, event: str, **fields: Any):
        self.owner = owner
        self.event = str(event or "PERF")
        self.fields = dict(fields or {})
        self.start = 0.0

    def __enter__(self):
        self.start = perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            fields = dict(self.fields)
            fields["ok"] = exc_type is None
            if exc_type is not None:
                fields["error_type"] = getattr(exc_type, "__name__", str(exc_type))
                fields["error"] = str(exc)
            log_elapsed(self.owner, self.event, self.start, **fields)
        except Exception:
            pass
        return False

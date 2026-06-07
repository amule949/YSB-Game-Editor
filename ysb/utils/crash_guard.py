# -*- coding: utf-8 -*-
"""Startup diagnostics for frozen YSB entry points.

This logger is intentionally tiny and dependency-light so it can be imported
before the Qt UI starts. It cannot catch native DLL/bootloader crashes, but it
makes Python-level import/startup errors visible in --windowed builds.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path


LOG_FILE_NAME = "ysb_startup_crash.log"
STAGE_FILE_NAME = "ysb_startup_stage.log"


def _candidate_log_dirs() -> list[Path]:
    dirs: list[Path] = []
    try:
        if getattr(sys, "frozen", False):
            dirs.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass
    try:
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local:
            dirs.append(Path(local) / "YSBGameEditor" / "logs")
    except Exception:
        pass
    try:
        dirs.append(Path.cwd())
    except Exception:
        pass
    try:
        dirs.append(Path(__file__).resolve().parents[2])
    except Exception:
        pass
    return dirs


def _first_writable_dir() -> Path | None:
    for d in _candidate_log_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            return d
        except Exception:
            continue
    return None


def append_startup_stage(message: str, *, entry_name: str = "YSB") -> Path | None:
    text = (
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
        f"[{entry_name}] {message}\n"
        f"  executable: {getattr(sys, 'executable', '')}\n"
        f"  frozen: {getattr(sys, 'frozen', False)}\n"
    )
    for d in _candidate_log_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            path = d / STAGE_FILE_NAME
            with path.open("a", encoding="utf-8") as f:
                f.write(text)
            return path
        except Exception:
            continue
    return None


def write_startup_crash_log(exc: BaseException, *, entry_name: str = "YSB") -> Path | None:
    try:
        from ysb.core.startup_compat import startup_state_summary
        cache_summary = startup_state_summary()
    except Exception:
        cache_summary = ""
    parts = [
        f"{entry_name} startup crash",
        time.strftime("%Y-%m-%d %H:%M:%S"),
        f"executable: {getattr(sys, 'executable', '')}",
        f"frozen: {getattr(sys, 'frozen', False)}",
        f"cwd: {os.getcwd() if hasattr(os, 'getcwd') else ''}",
        "",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    ]
    if cache_summary:
        parts.extend(["", "===== startup json cache shapes =====", cache_summary])
    text = "\n".join(parts)
    for d in _candidate_log_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            path = d / LOG_FILE_NAME
            path.write_text(text, encoding="utf-8")
            return path
        except Exception:
            continue
    return None


def show_startup_error_message(exc: BaseException, log_path: Path | None = None, *, title: str = "YSB Tool") -> None:
    message = f"프로그램 시작 중 오류가 발생했습니다.\n\n{exc}"
    if log_path:
        message += f"\n\n로그: {log_path}"
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except Exception:
            pass
    try:
        print(message, file=sys.stderr)
    except Exception:
        pass

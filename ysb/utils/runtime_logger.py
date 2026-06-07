# -*- coding: utf-8 -*-
"""Runtime diagnostics logger for YSB Game Editor.

This module is intentionally dependency-light.  It is safe to import from
workers and startup code, and every public function is best-effort: logging
must never crash the app.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
import threading
import traceback as _traceback
from pathlib import Path
from typing import Any

_LOG_LOCK = threading.RLock()
_FAULTHANDLER_FILE = None


def _now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _file_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def candidate_log_dirs() -> list[Path]:
    dirs: list[Path] = []
    try:
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local:
            dirs.append(Path(local) / "YSBGameEditor" / "logs")
    except Exception:
        pass
    try:
        if getattr(sys, "frozen", False):
            dirs.append(Path(sys.executable).resolve().parent / "logs")
    except Exception:
        pass
    try:
        dirs.append(Path.cwd() / "logs")
    except Exception:
        pass
    try:
        dirs.append(Path(__file__).resolve().parents[2] / "logs")
    except Exception:
        pass
    return dirs


def log_dir() -> Path:
    for d in candidate_log_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            return d
        except Exception:
            continue
    # Last resort.  Path.home() should normally be writable.
    fallback = Path.home() / "YSBGameEditor_logs"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def make_log_path(prefix: str, suffix: str = "log") -> Path:
    safe_prefix = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(prefix or "ysb"))
    try:
        pid = os.getpid()
    except Exception:
        pid = 0
    return log_dir() / f"{safe_prefix}_{_file_stamp()}_{pid}.{suffix.lstrip('.')}"


def append_log(path: str | os.PathLike[str] | None, event: str = "", **fields: Any) -> None:
    """Append one diagnostic line.

    The first text argument used to be named ``message``.  Keep accepting
    ``message=...`` as a log field too, because batch payloads often have a
    user-facing message.  A diagnostic logger must never be able to crash a
    running job merely because a field is called ``message``.
    """
    if path is None:
        return
    try:
        # Backward compatibility for accidental calls like append_log(path, message="...").
        # When an event name is already provided, keep fields["message"] as payload data.
        if not event and "message" in fields:
            try:
                event = str(fields.pop("message") or "")
            except Exception:
                event = ""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        pairs = []
        for k, v in fields.items():
            try:
                pairs.append(f"{k}={_format_field_value(v)}")
            except Exception:
                pairs.append(f"{k}=<unrepr>")
        tail = (" | " + " ".join(pairs)) if pairs else ""
        line = f"[{_now_stamp()}] {event}{tail}\n"
        with _LOG_LOCK:
            with p.open("a", encoding="utf-8", errors="replace") as f:
                f.write(line)
    except Exception:
        pass


def append_block(path: str | os.PathLike[str] | None, title: str, text: str) -> None:
    if path is None:
        return
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        block = f"\n[{_now_stamp()}] ===== {title} =====\n{text}\n===== END {title} =====\n"
        with _LOG_LOCK:
            with p.open("a", encoding="utf-8", errors="replace") as f:
                f.write(block)
    except Exception:
        pass


def _format_field_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    text = str(value)
    text = text.replace("\n", "\\n").replace("\r", "\\r")
    if len(text) > 500:
        text = text[:497] + "..."
    if " " in text:
        return repr(text)
    return text


def format_bytes(num: int | float | None) -> str:
    if num is None:
        return "unknown"
    try:
        n = float(num)
    except Exception:
        return "unknown"
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if abs(n) < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(n)}{unit}"
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"


def process_memory_mb() -> float | None:
    # Windows: query working set via psapi without requiring psutil.
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
            if ok:
                return float(counters.WorkingSetSize) / (1024.0 * 1024.0)
        except Exception:
            pass

    # Optional dependency fallback if present.
    try:
        import psutil  # type: ignore
        return float(psutil.Process(os.getpid()).memory_info().rss) / (1024.0 * 1024.0)
    except Exception:
        pass

    # POSIX fallback; ru_maxrss is platform-specific but good enough for diagnostics.
    try:
        import resource
        rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if sys.platform == "darwin":
            return rss / (1024.0 * 1024.0)
        return rss / 1024.0
    except Exception:
        return None


def memory_text() -> str:
    mb = process_memory_mb()
    return "unknown" if mb is None else f"{mb:.1f}MB"


def numpy_shape_text(value: Any) -> str:
    try:
        shape = getattr(value, "shape", None)
        dtype = getattr(value, "dtype", None)
        if shape is None:
            return "None"
        return f"shape={tuple(shape)},dtype={dtype}"
    except Exception:
        return "unknown"


def file_size(path: str | os.PathLike[str] | None) -> int | None:
    try:
        if not path:
            return None
        return Path(path).stat().st_size
    except Exception:
        return None


def image_size(path: str | os.PathLike[str] | None) -> tuple[int, int] | None:
    """Read common image dimensions without decoding the whole image."""
    try:
        if not path:
            return None
        p = Path(path)
        with p.open("rb") as f:
            head = f.read(64)
            if len(head) < 10:
                return None
            # PNG: width/height are big-endian at bytes 16..24.
            if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
                return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
            # BMP: width/height little-endian at bytes 18..26.
            if head.startswith(b"BM") and len(head) >= 26:
                w = int.from_bytes(head[18:22], "little", signed=True)
                h = int.from_bytes(head[22:26], "little", signed=True)
                return abs(w), abs(h)
            # GIF.
            if head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
                return int.from_bytes(head[6:8], "little"), int.from_bytes(head[8:10], "little")
            # WebP containers.
            if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
                chunk = head[12:16]
                if chunk == b"VP8X" and len(head) >= 30:
                    w = int.from_bytes(head[24:27], "little") + 1
                    h = int.from_bytes(head[27:30], "little") + 1
                    return w, h
                if chunk == b"VP8 " and len(head) >= 30:
                    # Lossy VP8 frame header.
                    if head[23:26] == b"\x9d\x01\x2a":
                        w = int.from_bytes(head[26:28], "little") & 0x3FFF
                        h = int.from_bytes(head[28:30], "little") & 0x3FFF
                        return w, h
                if chunk == b"VP8L" and len(head) >= 25:
                    b0, b1, b2, b3 = head[21], head[22], head[23], head[24]
                    w = 1 + (((b1 & 0x3F) << 8) | b0)
                    h = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
                    return w, h
            # JPEG: scan markers until a SOF segment.
            if head.startswith(b"\xff\xd8"):
                f.seek(2)
                while True:
                    marker_start = f.read(1)
                    if not marker_start:
                        return None
                    if marker_start != b"\xff":
                        continue
                    marker = f.read(1)
                    while marker == b"\xff":
                        marker = f.read(1)
                    if not marker:
                        return None
                    m = marker[0]
                    if m in (0xD8, 0xD9):
                        continue
                    size_bytes = f.read(2)
                    if len(size_bytes) != 2:
                        return None
                    seg_len = int.from_bytes(size_bytes, "big")
                    if seg_len < 2:
                        return None
                    if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        data = f.read(5)
                        if len(data) != 5:
                            return None
                        h = int.from_bytes(data[1:3], "big")
                        w = int.from_bytes(data[3:5], "big")
                        return w, h
                    f.seek(seg_len - 2, os.SEEK_CUR)
    except Exception:
        return None
    return None


def estimated_bgr_mb(size: tuple[int, int] | None) -> float | None:
    try:
        if not size:
            return None
        w, h = size
        return (float(w) * float(h) * 3.0) / (1024.0 * 1024.0)
    except Exception:
        return None


def exception_text(exc: BaseException) -> str:
    try:
        return "".join(_traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:
        return repr(exc)


def write_fatal_exception_log(exctype: type[BaseException], value: BaseException, tb: Any, formatted: str | None = None) -> Path | None:
    try:
        p = log_dir() / "ysb_fatal.log"
        text = formatted or "".join(_traceback.format_exception(exctype, value, tb))
        header = "\n".join([
            "YSB fatal exception",
            _now_stamp(),
            f"executable: {getattr(sys, 'executable', '')}",
            f"frozen: {getattr(sys, 'frozen', False)}",
            f"cwd: {os.getcwd()}",
            f"argv: {sys.argv!r}",
            f"memory: {memory_text()}",
            "",
        ])
        with _LOG_LOCK:
            with p.open("a", encoding="utf-8", errors="replace") as f:
                f.write(header)
                f.write(text)
                f.write("\n" + "=" * 80 + "\n")
        # Leave a tiny marker so the next clean launch can ask the user
        # whether to package recent logs. Best-effort only.
        try:
            from ysb.core.crash_reporter import write_fatal_marker
            write_fatal_marker(
                exctype_name=getattr(exctype, "__name__", str(exctype)),
                message=str(value),
                fatal_log_path=p,
            )
        except Exception:
            pass
        return p
    except Exception:
        return None


def install_faulthandler_log() -> Path | None:
    global _FAULTHANDLER_FILE
    try:
        import faulthandler
        p = log_dir() / "ysb_faulthandler.log"
        _FAULTHANDLER_FILE = p.open("a", encoding="utf-8", errors="replace")
        faulthandler.enable(file=_FAULTHANDLER_FILE, all_threads=True)
        append_log(p, "FAULTHANDLER ENABLED", executable=getattr(sys, "executable", ""), frozen=getattr(sys, "frozen", False))
        return p
    except Exception:
        return None

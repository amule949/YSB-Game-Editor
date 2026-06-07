# -*- coding: utf-8 -*-
"""Crash report packaging helpers for YSB Game Editor.

Stage 1 policy:
- Never send automatically.
- Never include project/image files automatically.
- Build a user-reviewable ZIP package and mail draft files only.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import uuid
import re
import subprocess
import sys
import webbrowser
import zipfile
from email import policy
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ysb.utils.runtime_logger import candidate_log_dirs, log_dir
from ysb.version_info import APP_VERSION, PRODUCT_NAME, SUPPORT_EMAIL

FATAL_MARKER_FILE_NAME = "ysb_fatal_marker.json"
CRASH_SESSION_MARKER_FILE_NAME = "ysb_crash_session_marker.json"
BUG_REPORT_DIR_NAME = "bug_reports"
BUG_REPORT_OPTION_NEVER_ASK = "bug_report_never_ask_after_fatal"
BUG_REPORT_OPTION_LAST_CREATED_AT = "bug_report_last_created_at"

_LOG_SUFFIXES = {".log", ".txt", ".json"}
_LOG_NAME_HINTS = (
    "ysb_",
    "engine_boundary",
    "startup",
    "fatal",
    "faulthandler",
    "runtime",
)


def _now() -> _dt.datetime:
    return _dt.datetime.now()


def _stamp() -> str:
    return _now().strftime("%Y%m%d_%H%M%S")


def fatal_marker_path() -> Path:
    return log_dir() / FATAL_MARKER_FILE_NAME


def crash_session_marker_path() -> Path:
    return log_dir() / CRASH_SESSION_MARKER_FILE_NAME


def _is_pid_alive(pid: Any) -> bool:
    try:
        pid_int = int(pid or 0)
    except Exception:
        return False
    if pid_int <= 0:
        return False
    try:
        if pid_int == os.getpid():
            return True
    except Exception:
        pass
    try:
        import psutil  # type: ignore
        return bool(psutil.pid_exists(pid_int))
    except Exception:
        pass
    try:
        # On POSIX this checks existence. On Windows this may not be available
        # for every process, so failures are treated as unknown/not alive.
        os.kill(pid_int, 0)
        return True
    except Exception:
        return False


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def detect_unclean_crash_session() -> dict[str, Any] | None:
    """Return previous running-session marker if the last app died uncleanly."""
    try:
        p = crash_session_marker_path()
        data = _read_json_file(p)
        if not data:
            return None
        if str(data.get("state") or "").lower() != "running":
            return None
        pid = data.get("pid")
        # If the pid is still alive, it is probably another currently running
        # instance or an in-progress launch. Do not report it as a crash.
        if _is_pid_alive(pid):
            return None
        data["_marker_path"] = str(p)
        data["detected_at"] = _now().isoformat(timespec="seconds")
        data["exctype"] = data.get("exctype") or "UncleanShutdown"
        data["message"] = data.get("message") or "Previous YSB Tool session ended without a clean shutdown."
        return data
    except Exception:
        return None


def start_crash_session_marker(*, runtime_log_path: str | os.PathLike[str] | None = None, faulthandler_log_path: str | os.PathLike[str] | None = None) -> dict[str, Any] | None:
    """Create a running marker early so native crashes can be detected next launch.

    Python exceptions can write ysb_fatal_marker.json after the fact. Native Qt/C++
    crashes often kill the process before Python can run cleanup, so we leave a
    running session marker at startup and remove/clean it only on normal shutdown.
    If a previous running marker is found and its pid is gone, it is promoted to
    the normal fatal marker so the existing bug-report dialog can reuse it.
    """
    previous = detect_unclean_crash_session()
    try:
        if previous and not fatal_marker_path().exists():
            write_fatal_marker(
                exctype_name=str(previous.get("exctype") or "UncleanShutdown"),
                message=str(previous.get("message") or "Previous YSB Tool session ended without a clean shutdown."),
                fatal_log_path=previous.get("faulthandler_log_path") or previous.get("fatal_log_path") or faulthandler_log_path or "",
                extra={"previous_session": previous},
            )
    except Exception:
        pass

    try:
        marker = {
            "state": "running",
            "session_id": uuid.uuid4().hex,
            "started_at": _now().isoformat(timespec="seconds"),
            "app_version": APP_VERSION,
            "product": PRODUCT_NAME,
            "pid": os.getpid(),
            "executable": getattr(sys, "executable", ""),
            "frozen": bool(getattr(sys, "frozen", False)),
            "cwd": os.getcwd(),
            "runtime_log_path": str(runtime_log_path or ""),
            "faulthandler_log_path": str(faulthandler_log_path or ""),
        }
        p = crash_session_marker_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return previous


def mark_crash_session_clean() -> None:
    try:
        p = crash_session_marker_path()
        data = _read_json_file(p) or {}
        if data and int(data.get("pid") or 0) not in (0, os.getpid()):
            return
        data.update({
            "state": "clean_exit",
            "ended_at": _now().isoformat(timespec="seconds"),
            "pid": os.getpid(),
        })
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def bug_reports_dir() -> Path:
    base = log_dir().parent / BUG_REPORT_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def _unique_report_dir(base_name: str) -> Path:
    root = bug_reports_dir()
    folder_name = _safe_file_part(base_name, "YSB_BugReport")
    candidate = root / folder_name
    if not candidate.exists():
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    for i in range(2, 1000):
        candidate = root / f"{folder_name}_{i}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
    candidate = root / f"{folder_name}_{uuid.uuid4().hex[:8]}"
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def write_fatal_marker(*, exctype_name: str = "", message: str = "", fatal_log_path: str | os.PathLike[str] | None = None, extra: dict[str, Any] | None = None) -> Path | None:
    """Write a marker so the next clean startup can offer a report package."""
    try:
        marker = {
            "created_at": _now().isoformat(timespec="seconds"),
            "exctype": str(exctype_name or ""),
            "message": str(message or ""),
            "fatal_log_path": str(fatal_log_path or ""),
            "app_version": APP_VERSION,
            "product": PRODUCT_NAME,
            "pid": os.getpid(),
            "executable": getattr(sys, "executable", ""),
            "frozen": bool(getattr(sys, "frozen", False)),
            "cwd": os.getcwd(),
        }
        if isinstance(extra, dict):
            marker.update(extra)
        p = fatal_marker_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        return p
    except Exception:
        return None


def load_pending_fatal_marker() -> dict[str, Any] | None:
    try:
        p = fatal_marker_path()
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        if isinstance(data, dict):
            data["_marker_path"] = str(p)
            return data
    except Exception:
        return None
    return None


def clear_pending_fatal_marker() -> None:
    try:
        fatal_marker_path().unlink(missing_ok=True)
    except Exception:
        pass


def _safe_file_part(value: str, fallback: str = "bug") -> str:
    s = str(value or fallback).strip()
    s = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "_", s)
    s = re.sub(r"\s+", "_", s).strip("._ ")
    if not s:
        s = fallback
    return s[:80]


def _redaction_tokens() -> list[str]:
    tokens: list[str] = []
    env_keys = ("USERPROFILE", "LOCALAPPDATA", "APPDATA", "HOME")
    for key in env_keys:
        try:
            v = os.environ.get(key)
            if v:
                tokens.append(str(Path(v)))
                tokens.append(str(Path(v)).replace("/", "\\"))
        except Exception:
            pass
    try:
        tokens.append(str(Path.cwd()))
    except Exception:
        pass
    try:
        tokens.append(str(Path(sys.executable).resolve().parent))
    except Exception:
        pass
    # Longer first so nested paths are masked in one pass.
    uniq = []
    seen = set()
    for t in sorted(tokens, key=len, reverse=True):
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def redact_text(text: str) -> str:
    out = str(text or "")
    for token in _redaction_tokens():
        try:
            out = out.replace(token, "<USER_PATH>")
            out = out.replace(token.replace("\\", "/"), "<USER_PATH>")
        except Exception:
            pass
    # Windows user folder leftovers.
    out = re.sub(r"[A-Za-z]:\\Users\\[^\\\r\n]+", r"<USER_PATH>", out)
    out = re.sub(r"/Users/[^/\r\n]+", r"<USER_PATH>", out)
    out = re.sub(r"/home/[^/\r\n]+", r"<USER_PATH>", out)
    return out


def _looks_like_log_file(path: Path) -> bool:
    try:
        name = path.name.lower()
        if path.suffix.lower() not in _LOG_SUFFIXES:
            return False
        return any(hint in name for hint in _LOG_NAME_HINTS)
    except Exception:
        return False


def _log_category(path: Path) -> str:
    """Return a coarse log category for bug-report packaging.

    The bug report should be compact: one latest file per category is usually
    enough for support, and it keeps the generated report folder readable.
    """
    try:
        name = path.name.lower()
        if name == FATAL_MARKER_FILE_NAME.lower():
            return "fatal_marker"
        if name == CRASH_SESSION_MARKER_FILE_NAME.lower():
            return "crash_session_marker"
        if "engine_boundary" in name:
            return "engine_boundary"
        if "faulthandler" in name:
            return "faulthandler"
        if "runtime" in name:
            return "runtime"
        if "fatal" in name:
            return "fatal"
        if "startup" in name:
            return "startup"
        if name.startswith("ysb_"):
            parts = name.split("_")
            if len(parts) >= 2:
                return f"ysb_{parts[1]}"
        return path.stem.lower() or "log"
    except Exception:
        return "log"


def _path_mtime(path: Path) -> float:
    try:
        return float(path.stat().st_mtime)
    except Exception:
        return 0.0


def collect_recent_log_files(*, max_files: int = 8, max_age_days: int = 21) -> list[Path]:
    """Collect compact diagnostic logs for a bug report.

    Policy: include the newest file for each meaningful log category
    (engine_boundary/runtime/faulthandler/markers/etc.) rather than many
    historical files of the same type. This keeps packages useful but small.
    """
    now = _now().timestamp()
    max_age = float(max_age_days) * 24.0 * 60.0 * 60.0
    found: dict[str, Path] = {}
    for d in candidate_log_dirs():
        try:
            if not d.exists():
                continue
            for p in d.glob("*"):
                try:
                    if not p.is_file() or not _looks_like_log_file(p):
                        continue
                    if now - _path_mtime(p) > max_age:
                        continue
                    found[str(p.resolve())] = p
                except Exception:
                    continue
        except Exception:
            continue
    try:
        mp = fatal_marker_path()
        if mp.exists():
            found[str(mp.resolve())] = mp
        sp = crash_session_marker_path()
        if sp.exists():
            found[str(sp.resolve())] = sp
    except Exception:
        pass

    latest_by_category: dict[str, Path] = {}
    for p in found.values():
        try:
            cat = _log_category(p)
            old = latest_by_category.get(cat)
            if old is None or _path_mtime(p) >= _path_mtime(old):
                latest_by_category[cat] = p
        except Exception:
            continue

    priority = {
        "engine_boundary": 0,
        "runtime": 1,
        "faulthandler": 2,
        "fatal_marker": 3,
        "crash_session_marker": 4,
        "fatal": 5,
        "startup": 6,
    }
    selected = sorted(
        latest_by_category.values(),
        key=lambda p: (priority.get(_log_category(p), 50), -_path_mtime(p), p.name.lower()),
    )
    return selected[:max_files]


def build_mail_subject(title: str | None = None) -> str:
    cleaned = str(title or "").strip()
    if not cleaned:
        cleaned = _now().strftime("Fatal crash %Y-%m-%d %H:%M")
    return f"[YSB Bug Report] {cleaned}"


def build_mail_body(*, title: str, description: str, marker: dict[str, Any] | None, zip_name: str | None = None) -> str:
    created_at = _now().strftime("%Y-%m-%d %H:%M:%S")
    marker = marker or {}
    lines = [
        "YSB Tool bug report",
        "",
        f"Title: {str(title or '').strip() or '(no title)'}",
        f"Created at: {created_at}",
        f"App version: {APP_VERSION}",
        f"OS: {platform.platform()}",
        f"Python: {platform.python_version()}",
        f"Fatal time: {marker.get('created_at', '(unknown)')}",
        f"Fatal type: {marker.get('exctype', '(unknown)')}",
        "",
        "User description:",
        str(description or "").strip() or "(Please describe what you were doing before the crash.)",
        "",
        "Attachment:",
        f"- {zip_name or 'YSB_BugReport_*.zip'}",
        "",
        "Privacy note:",
        "- This package is intended to include logs and diagnostic metadata only.",
        "- Project files and work images are not included automatically.",
        "- User paths in text logs are redacted on a best-effort basis.",
    ]
    return "\n".join(lines)


def _write_text_to_zip(zf: zipfile.ZipFile, arcname: str, text: str) -> None:
    zf.writestr(arcname, text.encode("utf-8", errors="replace"))


def _zip_log_file(zf: zipfile.ZipFile, path: Path, *, sanitize: bool = True, max_text_bytes: int = 4 * 1024 * 1024) -> None:
    try:
        name = _safe_file_part(path.name, "log")
        arcname = f"logs/{name}"
        data = path.read_bytes()
        if len(data) > max_text_bytes:
            data = data[-max_text_bytes:]
            prefix = b"[YSB bug report] Log was truncated to the last bytes for package size safety.\n\n"
            data = prefix + data
        try:
            text = data.decode("utf-8", errors="replace")
            if sanitize:
                text = redact_text(text)
            _write_text_to_zip(zf, arcname, text)
        except Exception:
            zf.writestr(arcname, data)
    except Exception:
        pass


def build_bug_report_package(*, title: str = "", description: str = "", marker: dict[str, Any] | None = None, include_logs: bool = True, sanitize_logs: bool = True) -> dict[str, Any]:
    marker = marker or load_pending_fatal_marker() or {}
    safe_title = _safe_file_part(title or "FatalCrash", "FatalCrash")
    base_name = f"YSB_BugReport_{_stamp()}_{safe_title}"
    out_dir = _unique_report_dir(base_name)
    zip_path = out_dir / f"{base_name}.zip"
    subject = build_mail_subject(title)
    body = build_mail_body(title=title, description=description, marker=marker, zip_name=zip_path.name)
    mail_body_path = out_dir / f"{base_name}_MAIL_BODY.txt"
    eml_path = out_dir / f"{base_name}.eml"

    log_files = collect_recent_log_files() if include_logs else []
    system_text = "\n".join([
        f"product: {PRODUCT_NAME}",
        f"app_version: {APP_VERSION}",
        f"support_email: {SUPPORT_EMAIL}",
        f"created_at: {_now().isoformat(timespec='seconds')}",
        f"platform: {platform.platform()}",
        f"python: {platform.python_version()}",
        f"executable: {getattr(sys, 'executable', '')}",
        f"frozen: {bool(getattr(sys, 'frozen', False))}",
        f"cwd: {os.getcwd()}",
    ])
    if sanitize_logs:
        system_text = redact_text(system_text)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_text_to_zip(zf, "README.txt", "This package contains YSB Tool diagnostic logs only. Project files and work images are not included automatically.\n")
        _write_text_to_zip(zf, "MAIL_BODY.txt", body)
        _write_text_to_zip(zf, "system_info.txt", system_text)
        try:
            _write_text_to_zip(zf, "fatal_marker.json", json.dumps(marker, ensure_ascii=False, indent=2))
        except Exception:
            pass
        for p in log_files:
            _zip_log_file(zf, p, sanitize=sanitize_logs)

    mail_body_path.write_text(body, encoding="utf-8")
    _write_eml(eml_path, subject=subject, body=body, attachment_path=zip_path)
    return {
        "zip_path": zip_path,
        "mail_body_path": mail_body_path,
        "eml_path": eml_path,
        "subject": subject,
        "body": body,
        "log_files": log_files,
    }


def _write_eml(path: Path, *, subject: str, body: str, attachment_path: Path | None = None) -> None:
    """Write a user-reviewable draft-style EML.

    `X-Unsent: 1` is understood by several desktop mail clients, including
    Outlook/Thunderbird-style handlers, as an unsent compose draft instead of
    a received/read-only message. Client support is not universal, so the
    mailto/TXT/ZIP fallback path is still kept by the UI.
    """
    msg = EmailMessage(policy=policy.SMTP)
    # Keep this header near the top so clients that support draft EML files
    # open the message in compose mode with To/Subject/body/attachment filled.
    msg["X-Unsent"] = "1"
    msg["X-YSB-Bug-Report-Draft"] = "1"
    msg["To"] = SUPPORT_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)
    if attachment_path and attachment_path.exists():
        data = attachment_path.read_bytes()
        msg.add_attachment(data, maintype="application", subtype="zip", filename=attachment_path.name)
    path.write_bytes(msg.as_bytes(policy=policy.SMTP))


def open_eml_draft(path: str | os.PathLike[str] | None) -> bool:
    """Open the generated draft EML with the user's default mail app.

    This is best-effort. If the user's system opens EML as a read-only viewer,
    the caller should still keep the mailto/TXT/ZIP fallback available.
    """
    try:
        if path is None:
            return False
        p = Path(path)
        if not p.exists():
            return False
        if sys.platform.startswith("win"):
            os.startfile(str(p))  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
            return True
        subprocess.Popen(["xdg-open", str(p)])
        return True
    except Exception:
        return False


def build_mailto_url(*, subject: str, body: str) -> str:
    return f"mailto:{SUPPORT_EMAIL}?subject={quote(subject)}&body={quote(body)}"


def open_mail_draft(*, subject: str, body: str) -> bool:
    try:
        return bool(webbrowser.open(build_mailto_url(subject=subject, body=body)))
    except Exception:
        return False


def reveal_path(path: str | os.PathLike[str] | None) -> bool:
    try:
        p = Path(path)
        target = p if p.is_dir() else p.parent
        if not target.exists():
            return False
        if sys.platform.startswith("win"):
            os.startfile(str(target))  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
            return True
        subprocess.Popen(["xdg-open", str(target)])
        return True
    except Exception:
        return False

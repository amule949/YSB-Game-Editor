# -*- coding: utf-8 -*-
"""Startup compatibility repair helpers for YSB Game Editor.

This module is intentionally dependency-light and must not import PyQt.
It repairs stale/corrupted user JSON caches left from older YSB/YSBG builds
before the Qt UI and settings dialogs are imported.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable


def _stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _safe_read_json(path: Path) -> tuple[bool, Any]:
    try:
        if not path.exists() or not path.is_file():
            return False, None
        return True, json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return True, None


def _backup_invalid(path: Path, reason: str = "invalid") -> Path | None:
    try:
        if not path.exists():
            return None
        safe_reason = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(reason or "invalid"))
        dst = path.with_name(f"{path.name}.{safe_reason}_{_stamp()}")
        i = 2
        while dst.exists():
            dst = path.with_name(f"{path.name}.{safe_reason}_{_stamp()}_{i}")
            i += 1
        path.replace(dst)
        return dst
    except Exception:
        return None


def _write_json(path: Path, value: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _ensure_json_kind(path: Path, *, valid_kinds: tuple[type, ...], default: Any | None = None, report: list[dict[str, Any]] | None = None) -> None:
    exists, data = _safe_read_json(path)
    if not exists:
        return
    if isinstance(data, valid_kinds):
        return
    backup = _backup_invalid(path, "schema")
    if default is not None:
        _write_json(path, default)
    if report is not None:
        report.append({
            "path": str(path),
            "expected": "/".join(t.__name__ for t in valid_kinds),
            "actual": type(data).__name__,
            "backup": str(backup or ""),
        })


def _cache_root_candidates() -> list[Path]:
    out: list[Path] = []
    try:
        from ysb.core.workspace_manager import cache_dir
        out.append(cache_dir())
    except Exception:
        pass
    # Legacy/default fallbacks. These are best-effort only; paths may not exist.
    try:
        home = Path.home()
        out.append(home / "Documents" / "YSB_Game_Editor" / "cache")
        out.append(home / "Documents" / "YSB_Translator" / "cache")
    except Exception:
        pass
    unique: list[Path] = []
    seen = set()
    for p in out:
        try:
            key = os.path.normcase(os.path.abspath(os.fspath(p)))
        except Exception:
            key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _appdata_log_dir() -> Path | None:
    try:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "YSBGameEditor" / "logs"
    except Exception:
        pass
    return None


def repair_startup_state() -> list[dict[str, Any]]:
    """Repair known top-level JSON cache shape mismatches.

    Old builds sometimes left a JSON list where new startup code expects a
    mapping.  The UI may crash before it can show the detailed traceback with
    ``'list' object has no attribute 'items'``.  We back up only files whose
    top-level JSON shape is definitely incompatible, then write a minimal
    default when that file is a settings cache.
    """
    report: list[dict[str, Any]] = []

    try:
        from ysb.core.workspace_manager import config_path
        _ensure_json_kind(config_path(), valid_kinds=(dict,), default={}, report=report)
    except Exception:
        pass

    for cache_root in _cache_root_candidates():
        try:
            _ensure_json_kind(cache_root / "app_options.json", valid_kinds=(dict,), default={}, report=report)
            _ensure_json_kind(cache_root / "api_cache.json", valid_kinds=(dict,), default={}, report=report)
            _ensure_json_kind(cache_root / "shortcut_cache.json", valid_kinds=(dict,), default={}, report=report)
            # recent_projects historically accepted both forms.
            _ensure_json_kind(cache_root / "recent_projects.json", valid_kinds=(dict, list), default={"recent_projects": []}, report=report)

            for rel in (
                Path("text_preset") / "_preset_state.json",
                Path("text_preset") / "_last_preset.json",
                Path("item_text_preset") / "_item_preset_state.json",
            ):
                _ensure_json_kind(cache_root / rel, valid_kinds=(dict,), default={}, report=report)

            for folder_name in ("text_preset", "item_text_preset"):
                folder = cache_root / folder_name
                if folder.is_dir():
                    for p in folder.glob("*.json"):
                        _ensure_json_kind(p, valid_kinds=(dict,), default={}, report=report)
        except Exception:
            continue

    log_dir = _appdata_log_dir()
    if log_dir is not None:
        for name in ("ysb_fatal_marker.json", "ysb_crash_session_marker.json"):
            _ensure_json_kind(log_dir / name, valid_kinds=(dict,), default=None, report=report)

    if report:
        try:
            log_dir = _appdata_log_dir()
            if log_dir is None:
                log_dir = Path.cwd() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "ysb_startup_cache_repair.json").write_text(
                json.dumps({"repaired_at": time.strftime("%Y-%m-%d %H:%M:%S"), "items": report}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
    return report


def startup_state_summary() -> str:
    """Return a tiny JSON-shape summary for crash logs."""
    rows: list[str] = []
    try:
        from ysb.core.workspace_manager import config_path
        paths: list[Path] = [config_path()]
    except Exception:
        paths = []
    for root in _cache_root_candidates():
        paths.extend([
            root / "app_options.json",
            root / "api_cache.json",
            root / "shortcut_cache.json",
            root / "recent_projects.json",
            root / "text_preset" / "_preset_state.json",
            root / "text_preset" / "_last_preset.json",
            root / "item_text_preset" / "_item_preset_state.json",
        ])
    seen = set()
    for p in paths:
        try:
            key = os.path.normcase(os.path.abspath(os.fspath(p)))
        except Exception:
            key = str(p)
        if key in seen:
            continue
        seen.add(key)
        exists, data = _safe_read_json(p)
        if not exists:
            continue
        rows.append(f"{p}: {type(data).__name__}")
    return "\n".join(rows)

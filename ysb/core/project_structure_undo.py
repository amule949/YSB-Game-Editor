from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List


def norm_path(path: str) -> str:
    try:
        return str(Path(str(path)).resolve()).lower()
    except Exception:
        return str(path).lower()


def make_rename_record(page_idx: int, apply_path: str, apply_original_name: str | None = None, *, reason: str = "원본 파일명 변경") -> Dict[str, Any]:
    return {
        "reason": reason,
        "page_idx": int(page_idx),
        "mode": 0,
        "_undo_scope": "project",
        "structure_diff": {
            "type": "rename",
            "page_idx": int(page_idx),
            "apply_path": str(apply_path),
            "apply_original_name": str(apply_original_name or os.path.basename(str(apply_path))),
        },
    }


def make_reorder_record(target_paths: List[str], current_page_idx: int = 0, *, reason: str = "페이지 순서 변경") -> Dict[str, Any]:
    return {
        "reason": reason,
        "page_idx": int(current_page_idx or 0),
        "mode": 0,
        "_undo_scope": "project",
        "structure_diff": {
            "type": "reorder",
            "target_paths": [str(p) for p in (target_paths or [])],
            "current_page_idx": int(current_page_idx or 0),
        },
    }


def apply_structure_diff(owner: Any, rec: Dict[str, Any]) -> bool:
    diff = (rec or {}).get("structure_diff")
    if not isinstance(diff, dict):
        return False
    kind = str(diff.get("type") or "")
    if kind == "rename":
        try:
            page_idx = int(diff.get("page_idx", rec.get("page_idx", 0)) or 0)
        except Exception:
            page_idx = int(getattr(owner, "idx", 0) or 0)
        path = str(diff.get("apply_path") or "")
        if not path:
            # file_rename_ops 기반 기록이면 to_path를 최종 path로 사용한다.
            ops = (rec or {}).get("file_rename_ops") or []
            if ops and isinstance(ops[0], dict):
                path = str(ops[0].get("to_path") or "")
        if not path:
            return True
        try:
            if 0 <= page_idx < len(getattr(owner, "paths", []) or []):
                owner.paths[page_idx] = path
        except Exception:
            pass
        try:
            if not isinstance(owner.data, dict):
                owner.data = {}
            curr = owner.data.get(page_idx) or {}
            curr["original_name"] = str(diff.get("apply_original_name") or os.path.basename(path))
            owner.data[page_idx] = curr
        except Exception:
            pass
        return True

    if kind == "reorder":
        target_paths = [str(p) for p in (diff.get("target_paths") or [])]
        if not target_paths:
            return True
        try:
            current_paths = list(getattr(owner, "paths", []) or [])
            current_data = getattr(owner, "data", {}) or {}
            by_path = {}
            for idx, path in enumerate(current_paths):
                try:
                    by_path[norm_path(path)] = current_data.get(idx)
                except Exception:
                    pass
            new_data = {}
            for idx, path in enumerate(target_paths):
                val = by_path.get(norm_path(path))
                if val is None:
                    val = current_data.get(idx, {})
                new_data[idx] = val
            owner.paths = list(target_paths)
            owner.data = new_data
        except Exception:
            try:
                owner.paths = list(target_paths)
            except Exception:
                pass
        try:
            owner.idx = max(0, min(int(diff.get("current_page_idx", rec.get("page_idx", 0)) or 0), len(owner.paths) - 1)) if owner.paths else 0
        except Exception:
            pass
        try:
            owner.remap_view_states_by_order([])
        except Exception:
            # 순서 Undo에서는 기존 view_state가 stale일 수 있으므로 안전하게 비운다.
            try:
                owner.project_ui_view_states = {}
            except Exception:
                pass
        return True
    return False

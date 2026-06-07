# -*- coding: utf-8 -*-
"""Undo record factory for YSB Game Editor.

Stage 2-1 keeps actual undo/redo stacks in MainWindowHistoryMixin, but moves the
record-building vocabulary into a core module.  This lets later feature patches
ask for "text line record", "UI record", "batch page record" through one object
instead of recreating dict shapes in scattered UI code.
"""

from __future__ import annotations

import copy
import os
from typing import Any, Mapping

import numpy as np


class UndoRecordFactory:
    def __init__(self, owner: Any):
        self.owner = owner

    # ------------------------------------------------------------------
    # owner helpers
    # ------------------------------------------------------------------
    def _page_idx(self, page_idx=None) -> int:
        if page_idx is None:
            page_idx = getattr(self.owner, "idx", 0)
        try:
            return int(page_idx)
        except Exception:
            return 0

    def _mode(self, mode=None) -> int:
        if mode is not None:
            try:
                return int(mode)
            except Exception:
                pass
        owner = self.owner
        try:
            return int(owner.cb_mode.currentIndex())
        except Exception:
            try:
                return int(getattr(owner, "last_mode", 0) or 0)
            except Exception:
                return 0

    def _view_state(self):
        try:
            return self.owner.capture_view_state()
        except Exception:
            return {}

    def _magic_wand_state(self):
        try:
            return self.owner.capture_magic_wand_state()
        except Exception:
            return {}

    def _ui_state(self):
        try:
            return self.owner.current_project_ui_state()
        except Exception:
            return {}

    def _copy_page_data(self, page_idx):
        try:
            return self.owner.copy_page_data_for_undo(page_idx)
        except Exception:
            return None

    def _copy_project_data(self):
        try:
            return self.owner.copy_project_data_for_undo()
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # public record builders
    # ------------------------------------------------------------------
    def make_batch_page_data_undo_record(self, reason="일괄 작업", page_indices=None, page_idx=None):
        owner = self.owner
        page_idx = self._page_idx(page_idx)
        unique: list[int] = []
        seen = set()
        paths = list(getattr(owner, "paths", []) or [])
        for raw in page_indices or []:
            try:
                i = int(raw)
            except Exception:
                continue
            if i in seen:
                continue
            if 0 <= i < len(paths):
                unique.append(i)
                seen.add(i)
        page_data = {}
        for i in unique:
            copied = self._copy_page_data(i)
            if copied is not None:
                page_data[i] = copied
        return {
            "reason": str(reason or "일괄 작업"),
            "page_idx": int(page_idx),
            "mode": self._mode(),
            "view_state": self._view_state(),
            "magic_wand_state": self._magic_wand_state(),
            "ui_state": self._ui_state(),
            "batch_page_data": page_data,
            "batch_page_indices": list(page_data.keys()),
            "_undo_scope": "project",
        }

    def make_project_undo_record(self, reason="작업", page_idx=None, full_project=False):
        owner = self.owner
        page_idx = self._page_idx(page_idx)
        rec = {
            "reason": str(reason or "작업"),
            "page_idx": int(page_idx),
            "mode": self._mode(),
            "view_state": self._view_state(),
            "magic_wand_state": self._magic_wand_state(),
            "ui_state": self._ui_state(),
        }
        if full_project:
            rec["project_paths"] = list(getattr(owner, "paths", []) or [])
            rec["project_data"] = self._copy_project_data()
        elif hasattr(owner, "is_project_structure_undo_reason") and owner.is_project_structure_undo_reason(reason, full_project=False):
            rec["page_data"] = self._copy_page_data(page_idx)
        else:
            include_masks = bool(hasattr(owner, "is_mask_light_undo_reason") and owner.is_mask_light_undo_reason(reason))
            rec["text_line_state"] = self.copy_text_line_state_for_undo(page_idx, include_masks=include_masks)
            rec["_undo_scope"] = "page"
        return rec

    def make_ui_undo_record(self, reason="화면 작업", page_idx=None, mode=None):
        page_idx = self._page_idx(page_idx)
        return {
            "reason": str(reason or "화면 작업"),
            "page_idx": int(page_idx),
            "mode": self._mode(mode),
            "view_state": self._view_state(),
            "magic_wand_state": self._magic_wand_state(),
            "ui_state": self._ui_state(),
            "ui_only": True,
        }

    def copy_text_line_state_for_undo(self, page_idx=None, include_masks=False):
        owner = self.owner
        page_idx = self._page_idx(page_idx)
        curr = (getattr(owner, "data", {}) or {}).get(page_idx)
        if not isinstance(curr, dict):
            return None
        state = {
            "data": copy.deepcopy(curr.get("data", []) or []),
            "ocr_analysis_regions": copy.deepcopy(curr.get("ocr_analysis_regions", []) or []),
        }
        try:
            owner.strip_text_transform_runtime_flags_from_snapshot(state)
        except Exception:
            pass
        if include_masks:
            for key in ("mask_merge", "mask_inpaint", "mask_merge_off", "mask_inpaint_off"):
                value = curr.get(key)
                state[key] = value.copy() if isinstance(value, np.ndarray) else copy.deepcopy(value)
            state["mask_toggle_enabled"] = bool(curr.get("mask_toggle_enabled", False))
        return state

    def make_text_line_undo_record(self, reason="텍스트 라인 변경", page_idx=None, include_masks=False):
        page_idx = self._page_idx(page_idx)
        return {
            "reason": str(reason or "텍스트 라인 변경"),
            "page_idx": int(page_idx),
            "mode": self._mode(),
            "view_state": self._view_state(),
            "magic_wand_state": self._magic_wand_state(),
            "ui_state": self._ui_state(),
            "text_line_state": self.copy_text_line_state_for_undo(page_idx, include_masks=include_masks),
        }

    def make_current_undo_record_like(self, rec: Mapping[str, Any] | None):
        """Create a current-state redo/undo counterpart with the same light unit."""
        owner = self.owner
        rec = rec or {}
        reason = str(rec.get("reason") or "작업")
        page_idx = self._page_idx(rec.get("page_idx", getattr(owner, "idx", 0)))

        def _attach_inverse_file_ops(out_rec):
            ops = rec.get("file_rename_ops")
            if isinstance(ops, list) and ops:
                try:
                    out_rec["file_rename_ops"] = owner.invert_file_rename_ops(ops)
                except Exception:
                    pass
            return out_rec

        structure_diff = rec.get("structure_diff")
        if isinstance(structure_diff, dict):
            try:
                from ysb.core.project_structure_undo import make_rename_record, make_reorder_record
                kind = str(structure_diff.get("type") or "")
                if kind == "rename":
                    curr_path = ""
                    curr_name = ""
                    try:
                        paths = list(getattr(owner, "paths", []) or [])
                        if 0 <= page_idx < len(paths):
                            curr_path = str(paths[page_idx])
                    except Exception:
                        curr_path = ""
                    try:
                        curr = (getattr(owner, "data", {}) or {}).get(page_idx) or {}
                        curr_name = str(curr.get("original_name") or os.path.basename(curr_path))
                    except Exception:
                        curr_name = os.path.basename(curr_path)
                    out_rec = make_rename_record(page_idx, curr_path, curr_name, reason=reason)
                    return _attach_inverse_file_ops(out_rec)
                if kind == "reorder":
                    return make_reorder_record(list(getattr(owner, "paths", []) or []), int(getattr(owner, "idx", page_idx) or 0), reason=reason)
            except Exception:
                pass

        if rec.get("paint_history"):
            return {
                "reason": reason,
                "page_idx": int(rec.get("page_idx", page_idx) or page_idx),
                "mode": int(getattr(owner, "last_mode", 0) or 0),
                "paint_history": True,
                "_undo_scope": "page",
            }

        text_diff_state = rec.get("text_diff_state")
        if isinstance(text_diff_state, dict):
            try:
                curr = (getattr(owner, "data", {}) or {}).get(page_idx, {})
                data_list = curr.get("data", []) if isinstance(curr, dict) else []
                ids = text_diff_state.get("ids") or []
                before_items = owner.text_engine.snapshot_items(data_list, ids=ids)
                return {
                    "reason": reason,
                    "page_idx": int(page_idx),
                    "mode": int(getattr(owner, "last_mode", 0) or 0),
                    "text_diff_state": {
                        "items": before_items,
                        "ids": [str(x) for x in ids if str(x)],
                        "fields": list(text_diff_state.get("fields") or []),
                    },
                    "selected_ids": [str(x) for x in ids if str(x)],
                    "_undo_scope": "page",
                }
            except Exception:
                pass

        text_line_state = rec.get("text_line_state")
        if isinstance(text_line_state, dict):
            include_masks = any(k in text_line_state for k in ("mask_merge", "mask_inpaint", "mask_merge_off", "mask_inpaint_off", "mask_toggle_enabled"))
            return _attach_inverse_file_ops(self.make_text_line_undo_record(reason, page_idx=page_idx, include_masks=include_masks))

        if rec.get("view_only"):
            return {
                "reason": reason,
                "page_idx": int(page_idx),
                "mode": self._mode(),
                "view_state": self._view_state(),
                "view_only": True,
                "ui_only": True,
                "_undo_scope": "page",
            }

        if rec.get("ui_only"):
            return _attach_inverse_file_ops(self.make_ui_undo_record(reason, page_idx=page_idx, mode=self._mode()))

        batch_page_data = rec.get("batch_page_data")
        if isinstance(batch_page_data, dict):
            indices = []
            for raw in rec.get("batch_page_indices") or batch_page_data.keys():
                try:
                    indices.append(int(raw))
                except Exception:
                    pass
            return _attach_inverse_file_ops(self.make_batch_page_data_undo_record(reason, indices, page_idx=page_idx))

        if isinstance(rec.get("project_data"), dict):
            return _attach_inverse_file_ops(self.make_project_undo_record(reason, page_idx=page_idx, full_project=True))
        return _attach_inverse_file_ops(self.make_project_undo_record(reason, page_idx=page_idx, full_project=False))

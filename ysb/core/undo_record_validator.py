# -*- coding: utf-8 -*-
"""Undo record validation helpers for YSB Game Editor.

Stage 3-5 purpose:
- Keep dict-based undo records for compatibility.
- Add a lightweight validation layer so missing keys / wrong scopes are caught
  before they silently corrupt undo/redo stacks.
- Validation is deliberately warning-friendly.  Only records that cannot be
  interpreted at all are treated as errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class UndoValidationResult:
    valid: bool = True
    scope: str = "unknown"
    kind: str = "unknown"
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(str(msg))

    def add_error(self, msg: str) -> None:
        self.errors.append(str(msg))
        self.valid = False

    def summary(self) -> str:
        parts = []
        if self.errors:
            parts.append("errors=" + "; ".join(self.errors[:6]))
        if self.warnings:
            parts.append("warnings=" + "; ".join(self.warnings[:6]))
        return " | ".join(parts)


class UndoRecordValidator:
    """Best-effort validator for current dict-based undo records."""

    PAGE_SCOPES = {"page", "page_view", "view"}
    PROJECT_SCOPES = {"project", "project_structure"}

    def _as_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except Exception:
            return None

    def infer_scope(self, record: Mapping[str, Any], expected_scope: str | None = None) -> str:
        raw = str(record.get("_undo_scope") or record.get("_undo_policy_scope") or expected_scope or "").strip().lower()
        if raw:
            if raw == "page_view":
                return "view"
            return raw
        if record.get("view_only") or record.get("view_state") is not None:
            return "view"
        if record.get("paint_history") or record.get("text_line_state") is not None:
            return "page"
        if record.get("batch_page_data") or record.get("project_data") or record.get("project_structure"):
            return "project"
        if record.get("page_idx") is not None:
            return "page"
        return "unknown"

    def infer_kind(self, record: Mapping[str, Any], scope: str) -> str:
        raw = str(record.get("_undo_unit") or record.get("_undo_policy_kind") or "").strip().lower()
        if raw:
            return raw
        if record.get("paint_history"):
            return "paint"
        if record.get("view_only") or record.get("view_state") is not None:
            return "view"
        if record.get("text_line_state") is not None:
            return "text_line"
        if record.get("batch_page_data"):
            return "batch"
        if scope == "project":
            return "project"
        return "generic"

    def validate(self, record: Any, *, expected_scope: str | None = None, source: str = "") -> UndoValidationResult:
        res = UndoValidationResult()
        if not isinstance(record, Mapping):
            res.add_error("record is not a mapping")
            return res
        if not record:
            res.add_error("record is empty")
            return res

        scope = self.infer_scope(record, expected_scope)
        kind = self.infer_kind(record, scope)
        reason = str(record.get("reason") or "")
        res.scope = scope
        res.kind = kind
        res.reason = reason

        if not reason:
            res.add_warning("missing reason")

        expected = str(expected_scope or "").strip().lower()
        if expected:
            normalized_expected = "view" if expected == "page_view" else expected
            normalized_scope = "view" if scope == "page_view" else scope
            if normalized_expected in {"page", "view", "project"} and normalized_scope not in {normalized_expected, "unknown"}:
                # View records may appear inside the page timeline for legacy compatibility.
                if not (normalized_expected == "page" and normalized_scope == "view"):
                    res.add_warning(f"scope mismatch: expected {expected}, got {scope}")

        if scope in self.PAGE_SCOPES or scope in {"page", "view"}:
            page_idx = self._as_int(record.get("page_idx"))
            if page_idx is None:
                res.add_warning("page/view record missing numeric page_idx")
        if kind == "view":
            if not isinstance(record.get("view_state"), Mapping):
                res.add_warning("view record missing view_state")
        if kind == "paint":
            if not record.get("paint_history"):
                res.add_warning("paint record missing paint_history marker")
        if kind == "text_line":
            state = record.get("text_line_state")
            if not isinstance(state, Mapping):
                res.add_warning("text_line record missing text_line_state mapping")
            elif not isinstance(state.get("data", []), list):
                res.add_warning("text_line_state.data is not a list")
        if scope == "project" and kind not in {"project", "batch", "generic"}:
            res.add_warning(f"project scope has unusual kind: {kind}")

        # Dangerous ambiguity: a record with neither page/project/view markers nor page_idx.
        if scope == "unknown" and record.get("page_idx") is None and not record.get("project_data") and not record.get("batch_page_data"):
            res.add_warning("record scope could not be inferred")

        return res

    def sanitize(self, record: dict[str, Any], *, expected_scope: str | None = None, default_page_idx: int | None = None, default_reason: str = "작업") -> dict[str, Any]:
        """Fill harmless default metadata in-place and return the record."""
        if not isinstance(record, dict):
            return record
        if not record.get("reason"):
            record["reason"] = default_reason
        if expected_scope and not record.get("_undo_scope"):
            record["_undo_scope"] = expected_scope
        if default_page_idx is not None and record.get("page_idx") is None and str(expected_scope or "").lower() in {"page", "view", "page_view"}:
            record["page_idx"] = int(default_page_idx)
        return record

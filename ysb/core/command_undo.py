# -*- coding: utf-8 -*-
"""Command/Diff undo primitives for YSB Game Editor.

Stage 1 of the command undo refactor intentionally does **not** migrate any
feature yet.  This module only defines the small data model that later patches
will use when text style, text geometry, view state, regions, and paint/mask
changes move away from whole-page snapshots.

Design rules:
- A command represents one user action.
- A field change represents one target field before/after diff.
- The runtime timeline may keep command objects directly.
- Project save/load formats are not changed in this stage.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping




def _values_equal(left: Any, right: Any) -> bool:
    """Robust equality for runtime command values, including numpy arrays.

    Plain ``==`` on numpy arrays returns an array and raises when converted to
    bool.  Undo no-op checks must never fail or turn into ambiguous truth-value
    errors, especially for mask/magic-wand runtime commands.
    """
    if left is right:
        return True
    try:
        import numpy as _np  # optional at runtime; already available in YSB
        if isinstance(left, _np.ndarray) or isinstance(right, _np.ndarray):
            if not (isinstance(left, _np.ndarray) and isinstance(right, _np.ndarray)):
                return False
            return bool(_np.array_equal(left, right))
    except Exception:
        pass
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left.keys()) != set(right.keys()):
            return False
        for key in left.keys():
            if not _values_equal(left.get(key), right.get(key)):
                return False
        return True
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        if len(left) != len(right):
            return False
        return all(_values_equal(a, b) for a, b in zip(left, right))
    try:
        result = left == right
        # numpy-like objects may still return an array/list-like truth value.
        if isinstance(result, bool):
            return result
        try:
            return bool(result)
        except Exception:
            return False
    except Exception:
        return False


def _compact_value(value: Any, *, limit: int = 120) -> str:
    """Return a short, log-safe representation for command diff diagnostics."""
    try:
        if isinstance(value, str):
            text = value.replace("\n", "\\n")
        else:
            text = repr(value)
    except Exception:
        text = f"<{type(value).__name__}>"
    try:
        limit = max(20, int(limit or 120))
    except Exception:
        limit = 120
    if len(text) > limit:
        text = text[: max(0, limit - 3)] + "..."
    return text


def summarize_field_changes(changes: Iterable[Any] | None, *, limit: int = 8, value_limit: int = 80) -> str:
    """Compact `target.field: before -> after` list for audit logs."""
    out: list[str] = []
    seq = list(changes or [])
    for raw in seq[: max(1, int(limit or 8))]:
        try:
            fc = FieldChange.from_mapping(raw)
            out.append(
                f"{str(fc.target_id)}.{str(fc.field)}:"
                f" {_compact_value(fc.before, limit=value_limit)} -> {_compact_value(fc.after, limit=value_limit)}"
            )
        except Exception:
            try:
                out.append(str(raw)[:value_limit])
            except Exception:
                pass
    if len(seq) > len(out):
        out.append(f"...(+{len(seq) - len(out)})")
    return " | ".join(out)


@dataclass
class FieldChange:
    """One field-level before/after diff on one component target."""

    target_id: str
    field: str
    before: Any = None
    after: Any = None
    component_type: str | None = None
    page_idx: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def is_noop(self) -> bool:
        return _values_equal(self.before, self.after)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": str(self.target_id),
            "field": str(self.field),
            "before": self.before,
            "after": self.after,
            "component_type": self.component_type,
            "page_idx": self.page_idx,
            "meta": dict(self.meta or {}),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | "FieldChange") -> "FieldChange":
        if isinstance(value, cls):
            return value
        value = value or {}
        page_idx = value.get("page_idx")
        try:
            page_idx = int(page_idx) if page_idx is not None else None
        except Exception:
            page_idx = None
        return cls(
            target_id=str(value.get("target_id") or value.get("id") or ""),
            field=str(value.get("field") or ""),
            before=value.get("before"),
            after=value.get("after"),
            component_type=(str(value.get("component_type")) if value.get("component_type") is not None else None),
            page_idx=page_idx,
            meta=dict(value.get("meta") or {}),
        )


@dataclass
class UndoCommand:
    """A single user-action command stored in the global UndoTimeline."""

    reason: str = "작업"
    page_idx: int = 0
    component_type: str = "component"
    changes: list[FieldChange] = field(default_factory=list)
    target_ids: list[str] = field(default_factory=list)
    command_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
    merge_key: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized: list[FieldChange] = []
        for change in self.changes or []:
            fc = FieldChange.from_mapping(change)
            if not fc.component_type:
                fc.component_type = self.component_type
            if fc.page_idx is None:
                fc.page_idx = self.page_idx
            normalized.append(fc)
        self.changes = normalized
        if not self.target_ids:
            seen: set[str] = set()
            for change in self.changes:
                tid = str(change.target_id or "")
                if tid and tid not in seen:
                    seen.add(tid)
                    self.target_ids.append(tid)

    @property
    def change_count(self) -> int:
        return len([c for c in self.changes if not c.is_noop()])

    def is_noop(self) -> bool:
        # Some runtime markers intentionally carry no field changes but still need
        # to occupy one user-visible timeline slot.  This is used for safe
        # creation-position anchors, where undoing the marker is a no-op but
        # prevents the following lifecycle command from deleting the new text too
        # early.
        try:
            if bool((self.meta or {}).get("force_record")):
                return False
        except Exception:
            pass
        return self.change_count <= 0

    def change_summary(self, *, limit: int = 8, value_limit: int = 80) -> str:
        return summarize_field_changes(self.changes, limit=limit, value_limit=value_limit)

    def summary(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "reason": self.reason,
            "page_idx": self.page_idx,
            "component_type": self.component_type,
            "target_count": len(self.target_ids or []),
            "change_count": self.change_count,
            "merge_key": self.merge_key or "",
            "change_summary": self.change_summary(),
            "force_record": bool((self.meta or {}).get("force_record")),
        }

    def to_dict(self, *, include_values: bool = True) -> dict[str, Any]:
        if include_values:
            changes = [c.to_dict() for c in self.changes]
        else:
            changes = [
                {
                    "target_id": c.target_id,
                    "field": c.field,
                    "component_type": c.component_type,
                    "page_idx": c.page_idx,
                }
                for c in self.changes
            ]
        return {
            "command_id": self.command_id,
            "reason": self.reason,
            "page_idx": int(self.page_idx or 0),
            "component_type": self.component_type,
            "target_ids": list(self.target_ids or []),
            "changes": changes,
            "timestamp": float(self.timestamp or 0),
            "merge_key": self.merge_key,
            "meta": dict(self.meta or {}),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | "UndoCommand") -> "UndoCommand":
        if isinstance(value, cls):
            return value
        value = value or {}
        try:
            page_idx = int(value.get("page_idx", 0) or 0)
        except Exception:
            page_idx = 0
        return cls(
            command_id=str(value.get("command_id") or uuid.uuid4().hex),
            reason=str(value.get("reason") or "작업"),
            page_idx=page_idx,
            component_type=str(value.get("component_type") or "component"),
            target_ids=[str(x) for x in (value.get("target_ids") or [])],
            changes=[FieldChange.from_mapping(x) for x in (value.get("changes") or [])],
            timestamp=float(value.get("timestamp") or time.time()),
            merge_key=(str(value.get("merge_key")) if value.get("merge_key") else None),
            meta=dict(value.get("meta") or {}),
        )

    def apply(self, owner: Any, *, redo: bool = False) -> bool:
        """Apply this command through the UI owner if a handler exists.

        Stage 1 provides only the dispatch contract.  Feature-specific logic is
        intentionally added in later patches through owner.apply_undo_command()
        or owner.apply_command_undo().  Returning False keeps the timeline entry
        in place and makes failures visible instead of silently dropping them.
        """
        if owner is None:
            return False
        for name in ("apply_undo_command", "apply_command_undo"):
            fn = getattr(owner, name, None)
            if callable(fn):
                try:
                    return bool(fn(self, redo=bool(redo)))
                except TypeError:
                    try:
                        return bool(fn(self, bool(redo)))
                    except Exception:
                        return False
                except Exception:
                    return False
        return False

    def undo(self, owner: Any) -> bool:
        return self.apply(owner, redo=False)

    def redo(self, owner: Any) -> bool:
        return self.apply(owner, redo=True)


class CommandTimeline:
    """Small standalone command stack helper for tests and future migrations.

    The app's canonical user-facing order remains YSBUndoManager.undo_timeline.
    This helper is deliberately lightweight so later patches can reuse merge and
    stack handling without forcing a second timeline into the UI.
    """

    def __init__(self, limit: int = 160):
        self.limit = max(20, int(limit or 160))
        self.undo_stack: list[UndoCommand] = []
        self.redo_stack: list[UndoCommand] = []

    def _trim(self, stack: list[UndoCommand]) -> None:
        while len(stack) > self.limit:
            stack.pop(0)

    def push(self, command: UndoCommand | Mapping[str, Any], *, clear_redo: bool = True) -> bool:
        cmd = UndoCommand.from_mapping(command)
        if cmd.is_noop():
            return False
        self.undo_stack.append(cmd)
        self._trim(self.undo_stack)
        if clear_redo:
            self.redo_stack.clear()
        return True

    def pop_undo(self) -> UndoCommand | None:
        return self.undo_stack.pop() if self.undo_stack else None

    def pop_redo(self) -> UndoCommand | None:
        return self.redo_stack.pop() if self.redo_stack else None

    def push_redo(self, command: UndoCommand | Mapping[str, Any]) -> bool:
        cmd = UndoCommand.from_mapping(command)
        if cmd.is_noop():
            return False
        self.redo_stack.append(cmd)
        self._trim(self.redo_stack)
        return True

    def push_undo_existing(self, command: UndoCommand | Mapping[str, Any]) -> bool:
        cmd = UndoCommand.from_mapping(command)
        if cmd.is_noop():
            return False
        self.undo_stack.append(cmd)
        self._trim(self.undo_stack)
        return True

    def clear_redo(self) -> None:
        self.redo_stack.clear()

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    def __len__(self) -> int:
        return len(self.undo_stack)


def coerce_command(value: UndoCommand | Mapping[str, Any] | None) -> UndoCommand | None:
    if value is None:
        return None
    try:
        return UndoCommand.from_mapping(value)
    except Exception:
        return None


def make_field_changes(changes: Iterable[Mapping[str, Any] | FieldChange]) -> list[FieldChange]:
    out: list[FieldChange] = []
    for change in changes or []:
        try:
            out.append(FieldChange.from_mapping(change))
        except Exception:
            continue
    return out

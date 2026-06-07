# -*- coding: utf-8 -*-
"""Central undo gateway for YSB Game Editor.

Stage 1 refactor goal:
- Do not replace the existing undo implementation yet.
- Provide one stable gateway that new code can use instead of touching
  MainWindowHistoryMixin stacks/functions directly.
- Internally delegate to the legacy methods so current behavior stays intact.

Future stages can move the real stack storage/restore logic into this module
without changing feature code that already uses YSBUndoManager.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Mapping

from ysb.core.undo_record_validator import UndoRecordValidator
from ysb.core.undo_policies import (
    KIND_MASK,
    KIND_PAINT,
    KIND_TEXT_LINE,
    KIND_UI,
    KIND_VIEW,
    SCOPE_BOUNDARY,
    SCOPE_PAGE,
    SCOPE_PROJECT,
    SCOPE_VIEW,
    policy_for,
)


PAGE_SCOPE = "page"
PROJECT_SCOPE = "project"
VIEW_SCOPE = "view"
BOUNDARY_SCOPE = "boundary"
RUNTIME_SCOPE = "runtime"


@dataclass
class UndoPolicy:
    """Small declarative policy attached to a new undo-producing feature.

    This is intentionally lightweight in stage 1.  It documents the intended
    scope and gives the manager enough information to route to the existing
    legacy functions safely.
    """

    scope: str = PAGE_SCOPE
    label: str = "작업"
    dirty_kinds: tuple[str, ...] = field(default_factory=tuple)
    page_idx: int | None = None
    merge_key: str | None = None
    boundary_policy: str = "none"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "UndoPolicy":
        if not isinstance(value, Mapping):
            return cls()
        dirty = value.get("dirty_kinds") or value.get("dirty") or ()
        if isinstance(dirty, str):
            dirty = (dirty,)
        try:
            page_idx = value.get("page_idx")
            page_idx = int(page_idx) if page_idx is not None else None
        except Exception:
            page_idx = None
        return cls(
            scope=str(value.get("scope") or PAGE_SCOPE),
            label=str(value.get("label") or value.get("reason") or "작업"),
            dirty_kinds=tuple(str(x) for x in (dirty or ())),
            page_idx=page_idx,
            merge_key=str(value.get("merge_key") or "") or None,
            boundary_policy=str(value.get("boundary_policy") or "none"),
        )


class YSBUndoManager:
    """Stage-1 central gateway around the existing undo system.

    The manager deliberately calls the current MainWindowHistoryMixin methods.
    This keeps the refactor low-risk while giving future code a single import
    and a single vocabulary: page/project/view/boundary/runtime.
    """

    def __init__(self, owner: Any | None = None):
        self.owner = owner
        self.enabled = True
        self.last_policy: UndoPolicy | None = None
        # Stage 3-2: UndoManager becomes the canonical owner of page/project
        # undo storage.  MainWindow keeps legacy attribute aliases for older code.
        self.page_undo_stacks: dict[int, list] = {}
        self.page_redo_stacks: dict[int, list] = {}
        self.page_view_undo_stacks: dict[int, list] = {}
        self.page_view_redo_stacks: dict[int, list] = {}
        self.project_undo_stack: list = []
        self.project_redo_stack: list = []
        # Stage 3-3: active Viewer paint history is now owned here.
        # The records still contain QGraphicsItem/QPixmap references, so this is
        # intentionally the active-viewer stack, not a persistent per-page stack.
        self.paint_history: list = []
        self.paint_redo_history: list = []
        self.paint_viewer: Any | None = None
        # Stage 4: the user-facing Ctrl+Z/Ctrl+Y order is a single timeline.
        # Legacy per-scope stacks remain as storage/compatibility backends.
        self.undo_timeline: list[dict[str, Any]] = []
        self.redo_timeline: list[dict[str, Any]] = []
        # Stage 5-1: diagnostic sequence for the single user-action timeline.
        # This is runtime-only and intentionally not persisted in project files.
        self._timeline_seq = 0
        self._restore_engine = None
        self.record_validator = UndoRecordValidator()

    def bind(self, owner: Any) -> "YSBUndoManager":
        self.owner = owner
        self.install_owner_stack_aliases()
        return self

    # ------------------------------------------------------------------
    # record validation - stage 3-5
    # ------------------------------------------------------------------
    def validate_record(self, record: Any, *, expected_scope: str | None = None, source: str = "") -> bool:
        try:
            res = self.record_validator.validate(record, expected_scope=expected_scope, source=source)
        except Exception as e:
            self._audit("UNDO_RECORD_VALIDATE_ERROR", source=str(source or ""), error=repr(e), throttle_ms=120)
            return True
        if not res.valid or res.warnings:
            self._audit(
                "UNDO_RECORD_VALIDATE",
                source=str(source or ""),
                valid=bool(res.valid),
                scope=str(res.scope),
                kind=str(res.kind),
                reason=str(res.reason),
                warnings="; ".join(res.warnings[:6]),
                errors="; ".join(res.errors[:6]),
                throttle_ms=120,
            )
        return bool(res.valid)

    def sanitize_record(self, record: dict[str, Any], *, expected_scope: str | None = None, page_idx: int | None = None, reason: str = "작업") -> dict[str, Any]:
        try:
            return self.record_validator.sanitize(record, expected_scope=expected_scope, default_page_idx=page_idx, default_reason=reason)
        except Exception:
            return record

    # ------------------------------------------------------------------
    # diagnostics
    # ------------------------------------------------------------------
    def _audit(self, event: str, **fields: Any) -> None:
        owner = self.owner
        try:
            if owner is not None and hasattr(owner, "audit_boundary_event"):
                owner.audit_boundary_event(event, **fields)
        except Exception:
            pass

    def _owner_method(self, name: str):
        owner = self.owner
        if owner is None:
            return None
        fn = getattr(owner, name, None)
        return fn if callable(fn) else None

    def _copy_record(self, rec: Mapping[str, Any] | None) -> dict[str, Any]:
        if not rec:
            return {}
        try:
            return copy.deepcopy(dict(rec))
        except Exception:
            try:
                return dict(rec)
            except Exception:
                return {}

    def _resolve_page_idx(self, rec: Mapping[str, Any] | None = None, page_idx: int | None = None) -> int:
        if page_idx is not None:
            try:
                return int(page_idx)
            except Exception:
                pass
        if isinstance(rec, Mapping) and rec.get("page_idx") is not None:
            try:
                return int(rec.get("page_idx"))
            except Exception:
                pass
        try:
            return int(getattr(self.owner, "idx", 0) or 0)
        except Exception:
            return 0

    def _policy_for_reason(self, reason: str | None):
        try:
            return policy_for(reason)
        except Exception:
            return None

    def _annotate_record_policy(self, record: dict[str, Any], *, reason: str | None = None, scope: str | None = None) -> dict[str, Any]:
        if not isinstance(record, dict):
            return record
        action = str(reason or record.get("reason") or "")
        pol = self._policy_for_reason(action)
        if pol is not None:
            record.setdefault("_undo_policy_action", pol.action)
            record.setdefault("_undo_policy_scope", pol.scope)
            record.setdefault("_undo_policy_kind", pol.kind)
            record.setdefault("_undo_policy_dirty", list(pol.dirty_kinds))
            if pol.merge_key:
                record.setdefault("_undo_policy_merge_key", pol.merge_key)
            if pol.boundary_policy and pol.boundary_policy != "none":
                record.setdefault("_undo_boundary_policy", pol.boundary_policy)
        if scope:
            record.setdefault("_undo_policy_scope", str(scope))
        return record

    def _factory(self):
        owner = self.owner
        if owner is None:
            return None
        try:
            if hasattr(owner, "get_undo_record_factory"):
                return owner.get_undo_record_factory()
        except Exception:
            return None
        return None

    # ------------------------------------------------------------------
    # stack access API - stage 3-2 ownership transfer
    # ------------------------------------------------------------------
    def _coerce_page_stack_map_keys(self, value: Any) -> dict[int, list]:
        out: dict[int, list] = {}
        if not isinstance(value, dict):
            return out
        for key, stack in value.items():
            try:
                page_idx = int(key)
            except Exception:
                continue
            if isinstance(stack, list):
                out[page_idx] = stack
            elif stack:
                try:
                    out[page_idx] = list(stack)
                except Exception:
                    out[page_idx] = []
            else:
                out[page_idx] = []
        return out

    def _merge_page_stack_map(self, target: dict[int, list], source: Any) -> dict[int, list]:
        source_map = self._coerce_page_stack_map_keys(source)
        if not source_map:
            return target
        for page_idx, stack in source_map.items():
            if page_idx not in target or not target.get(page_idx):
                target[page_idx] = stack
        return target

    def _merge_project_stack(self, target: list, source: Any) -> list:
        if source is target:
            return target
        if isinstance(source, list) and source and not target:
            target.extend(source)
        return target

    def install_owner_stack_aliases(self) -> bool:
        """Point legacy MainWindow stack attributes at manager-owned storage.

        Stage 3-2 moves the canonical containers here while preserving old
        attribute names as aliases.  That keeps older code paths working until
        Stage 3-4 moves the execution engine.
        """
        owner = self.owner
        if owner is None:
            return False
        try:
            self._merge_page_stack_map(self.page_undo_stacks, getattr(owner, "page_undo_stacks", None))
            self._merge_page_stack_map(self.page_redo_stacks, getattr(owner, "page_redo_stacks", None))
            self._merge_page_stack_map(self.page_view_undo_stacks, getattr(owner, "page_view_undo_stacks", None))
            self._merge_page_stack_map(self.page_view_redo_stacks, getattr(owner, "page_view_redo_stacks", None))
            self._merge_project_stack(self.project_undo_stack, getattr(owner, "project_undo_stack", None))
            self._merge_project_stack(self.project_redo_stack, getattr(owner, "project_redo_stack", None))

            owner.page_undo_stacks = self.page_undo_stacks
            owner.page_redo_stacks = self.page_redo_stacks
            owner.page_view_undo_stacks = self.page_view_undo_stacks
            owner.page_view_redo_stacks = self.page_view_redo_stacks
            owner.page_text_undo_stacks = self.page_undo_stacks
            owner.project_undo_stack = self.project_undo_stack
            owner.project_redo_stack = self.project_redo_stack
            owner.undo_timeline = self.undo_timeline
            owner.redo_timeline = self.redo_timeline
            try:
                if getattr(owner, "view", None) is not None:
                    self.bind_paint_viewer(owner.view)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def ensure_stack_state(self) -> bool:
        """Ensure manager-owned stacks exist and legacy aliases point here."""
        if not isinstance(getattr(self, "page_undo_stacks", None), dict):
            self.page_undo_stacks = {}
        if not isinstance(getattr(self, "page_redo_stacks", None), dict):
            self.page_redo_stacks = {}
        if not isinstance(getattr(self, "page_view_undo_stacks", None), dict):
            self.page_view_undo_stacks = {}
        if not isinstance(getattr(self, "page_view_redo_stacks", None), dict):
            self.page_view_redo_stacks = {}
        if not isinstance(getattr(self, "project_undo_stack", None), list):
            self.project_undo_stack = []
        if not isinstance(getattr(self, "project_redo_stack", None), list):
            self.project_redo_stack = []
        return self.install_owner_stack_aliases()

    def _page_stack_map(self, attr: str, create: bool = True):
        if create:
            self.ensure_stack_state()
        value = getattr(self, attr, None)
        if isinstance(value, dict):
            return value
        if not create:
            return None
        try:
            setattr(self, attr, {})
            self.install_owner_stack_aliases()
            return getattr(self, attr)
        except Exception:
            return None

    def _page_stack(self, attr: str, page_idx: int | None = None, create: bool = True):
        target_page = self._resolve_page_idx(page_idx=page_idx)
        stacks = self._page_stack_map(attr, create=create)
        if not isinstance(stacks, dict):
            return []
        if create:
            return stacks.setdefault(target_page, [])
        return stacks.get(target_page) or []

    def page_undo_stack(self, page_idx: int | None = None, create: bool = True):
        return self._page_stack("page_undo_stacks", page_idx=page_idx, create=create)

    def page_redo_stack(self, page_idx: int | None = None, create: bool = True):
        return self._page_stack("page_redo_stacks", page_idx=page_idx, create=create)

    def page_view_undo_stack(self, page_idx: int | None = None, create: bool = True):
        return self._page_stack("page_view_undo_stacks", page_idx=page_idx, create=create)

    def page_view_redo_stack(self, page_idx: int | None = None, create: bool = True):
        return self._page_stack("page_view_redo_stacks", page_idx=page_idx, create=create)

    def project_undo_stack_ref(self, create: bool = True):
        if create:
            self.ensure_stack_state()
        value = getattr(self, "project_undo_stack", None)
        if isinstance(value, list):
            return value
        if not create:
            return []
        self.project_undo_stack = []
        self.install_owner_stack_aliases()
        return self.project_undo_stack

    def project_redo_stack_ref(self, create: bool = True):
        if create:
            self.ensure_stack_state()
        value = getattr(self, "project_redo_stack", None)
        if isinstance(value, list):
            return value
        if not create:
            return []
        self.project_redo_stack = []
        self.install_owner_stack_aliases()
        return self.project_redo_stack

    def clear_page_storage(self, page_idx: int | None = None, *, undo: bool = True, redo: bool = True, view: bool = True, update: bool = True) -> bool:
        target_page = self._resolve_page_idx(page_idx=page_idx)
        changed = False
        try:
            self.ensure_stack_state()
            self.clear_timeline_for_page(target_page, undo=undo, redo=redo, reason="clear_page_storage")
            pairs = []
            if undo:
                pairs.append("page_undo_stacks")
            if redo:
                pairs.append("page_redo_stacks")
            if view and undo:
                pairs.append("page_view_undo_stacks")
            if view and redo:
                pairs.append("page_view_redo_stacks")
            for attr in pairs:
                stacks = self._page_stack_map(attr, create=True)
                if isinstance(stacks, dict):
                    stacks.pop(target_page, None)
                    changed = True
            owner = self.owner
            if owner is not None:
                try:
                    owner.page_text_undo_stacks = self.page_undo_stacks
                except Exception:
                    pass
                try:
                    if hasattr(owner, "page_engine") and owner.page_engine is not None and undo and redo:
                        owner.page_engine.clear_page_undo(target_page)
                except Exception:
                    pass
                if update and hasattr(owner, "update_undo_redo_buttons"):
                    owner.update_undo_redo_buttons()
            return changed
        except Exception:
            return False

    def clear_all_page_storage(self, *, update: bool = True) -> bool:
        try:
            self.ensure_stack_state()
            self.page_undo_stacks.clear()
            self.page_redo_stacks.clear()
            self.page_view_undo_stacks.clear()
            self.page_view_redo_stacks.clear()
            self.clear_all_timeline(undo=True, redo=True, reason="clear_all_page_storage")
            self.install_owner_stack_aliases()
            owner = self.owner
            if owner is not None:
                try:
                    if hasattr(owner, "page_engine") and owner.page_engine is not None:
                        owner.page_engine.clear_all_undo()
                except Exception:
                    try:
                        if hasattr(owner.page_engine, "pages"):
                            owner.page_engine.pages.clear()
                    except Exception:
                        pass
                if update and hasattr(owner, "update_undo_redo_buttons"):
                    owner.update_undo_redo_buttons()
            return True
        except Exception:
            return False

    def clear_project_storage(self, *, undo: bool = True, redo: bool = True, update: bool = True) -> bool:
        try:
            self.ensure_stack_state()
            if undo:
                self.project_undo_stack.clear()
            if redo:
                self.project_redo_stack.clear()
            if undo or redo:
                self.clear_all_timeline(undo=undo, redo=redo, reason="clear_project_storage")
            self.install_owner_stack_aliases()
            owner = self.owner
            if owner is not None and update and hasattr(owner, "update_undo_redo_buttons"):
                owner.update_undo_redo_buttons()
            return True
        except Exception:
            return False

    def page_stack_lengths(self, page_idx: int | None = None) -> dict[str, int]:
        target_page = self._resolve_page_idx(page_idx=page_idx)
        return {
            "page_undo": len(self.page_undo_stack(target_page, create=False) or []),
            "page_redo": len(self.page_redo_stack(target_page, create=False) or []),
            "view_undo": len(self.page_view_undo_stack(target_page, create=False) or []),
            "view_redo": len(self.page_view_redo_stack(target_page, create=False) or []),
            "project_undo": len(self.project_undo_stack_ref(create=False) or []),
            "project_redo": len(self.project_redo_stack_ref(create=False) or []),
        }

    # ------------------------------------------------------------------
    # single timeline API - stage 4
    # ------------------------------------------------------------------
    def _timeline_stack_from_record(self, rec: Mapping[str, Any] | None, stack: str | None = None) -> str:
        if stack:
            s = str(stack)
        else:
            scope = str((rec or {}).get("_undo_scope") or "")
            if scope == "command" or (rec or {}).get("command") is not None or (rec or {}).get("command_payload") is not None:
                s = "command"
            elif scope in ("page_view", "view"):
                s = "view"
            elif scope == "project":
                s = "project"
            else:
                s = "page"
        if s in ("command", "cmd"):
            return "command"
        if s in ("page_view", "view"):
            return "view"
        if s == "project":
            return "project"
        return "page"

    def _next_timeline_seq(self) -> int:
        try:
            self._timeline_seq = int(getattr(self, "_timeline_seq", 0) or 0) + 1
        except Exception:
            self._timeline_seq = 1
        return int(self._timeline_seq)

    def _timeline_entry(self, rec: Mapping[str, Any] | None, *, stack: str | None = None) -> dict[str, Any]:
        rec = dict(rec or {})
        command = rec.get("command")
        command_payload = rec.get("command_payload")
        if command is not None and command_payload is None:
            try:
                command_payload = command.to_dict(include_values=False)
            except Exception:
                command_payload = None
        if command is None and command_payload is not None:
            try:
                from ysb.core.command_undo import UndoCommand
                command = UndoCommand.from_mapping(command_payload)
            except Exception:
                command = None
        try:
            page_idx = int(rec.get("page_idx", getattr(command, "page_idx", self._resolve_page_idx())))
        except Exception:
            page_idx = self._resolve_page_idx()
        entry = {
            "seq": self._next_timeline_seq(),
            "stack": self._timeline_stack_from_record(rec, stack),
            "page_idx": page_idx,
            "reason": str(rec.get("reason") or getattr(command, "reason", None) or "작업"),
            "scope": str(rec.get("_undo_scope") or ("command" if command is not None else "")),
            "paint_history": bool(rec.get("paint_history")),
            "view_only": bool(rec.get("view_only") or (rec.get("ui_only") and rec.get("view_state"))),
        }
        if command is not None or entry.get("stack") == "command":
            if command is not None:
                entry["command"] = command
                entry["command_id"] = str(getattr(command, "command_id", "") or "")
                entry["component_type"] = str(getattr(command, "component_type", "") or "")
                entry["target_ids"] = list(getattr(command, "target_ids", []) or [])
                entry["change_count"] = int(getattr(command, "change_count", 0) or 0)
                entry["merge_key"] = str(getattr(command, "merge_key", "") or "")
            if command_payload is not None:
                entry["command_payload"] = command_payload
        return entry

    def _timeline_entry_summary(self, entry: Mapping[str, Any] | None) -> str:
        entry = entry or {}
        try:
            return "#{}:{}:p{}:{}".format(
                entry.get("seq", ""),
                entry.get("stack", "page"),
                entry.get("page_idx", ""),
                str(entry.get("reason") or "")[:40],
            )
        except Exception:
            return ""

    def _command_change_summary(self, entry: Mapping[str, Any] | None, *, limit: int = 8) -> str:
        try:
            command = (entry or {}).get("command")
            if command is not None and hasattr(command, "change_summary"):
                return str(command.change_summary(limit=limit))
            payload = (entry or {}).get("command_payload")
            if isinstance(payload, Mapping):
                from ysb.core.command_undo import UndoCommand
                return str(UndoCommand.from_mapping(payload).change_summary(limit=limit))
        except Exception:
            pass
        return ""

    def _timeline_audit_fields(self, entry: Mapping[str, Any] | None, *, source: str = "") -> dict[str, Any]:
        entry = entry or {}
        try:
            lengths = self.page_stack_lengths(entry.get("page_idx"))
        except Exception:
            lengths = {}
        command = entry.get("command")
        command_meta = {}
        try:
            command_meta = dict(getattr(command, "meta", {}) or {}) if command is not None else {}
        except Exception:
            command_meta = {}
        return {
            "seq": entry.get("seq", ""),
            "stack": entry.get("stack", "page"),
            "page_idx": entry.get("page_idx", ""),
            "reason": entry.get("reason", ""),
            "source": str(source or ""),
            "undo_size": len(getattr(self, "undo_timeline", []) or []),
            "redo_size": len(getattr(self, "redo_timeline", []) or []),
            "undo_tail": self._timeline_entry_summary((getattr(self, "undo_timeline", []) or [None])[-1]),
            "redo_tail": self._timeline_entry_summary((getattr(self, "redo_timeline", []) or [None])[-1]),
            "page_undo": lengths.get("page_undo", ""),
            "page_redo": lengths.get("page_redo", ""),
            "view_undo": lengths.get("view_undo", ""),
            "view_redo": lengths.get("view_redo", ""),
            "project_undo": lengths.get("project_undo", ""),
            "project_redo": lengths.get("project_redo", ""),
            "command_id": entry.get("command_id", ""),
            "component_type": entry.get("component_type", ""),
            "change_count": entry.get("change_count", ""),
            "merge_key": entry.get("merge_key", ""),
            "target_ids": ",".join([str(x) for x in (entry.get("target_ids") or [])][:8]) if isinstance(entry.get("target_ids"), list) else "",
            "change_summary": self._command_change_summary(entry),
            "force_record": bool(command_meta.get("force_record", False)),
            "marker": str(command_meta.get("marker") or ""),
        }

    def _trim_timeline(self, timeline: list, limit: int = 160) -> None:
        try:
            limit = max(20, int(limit or 160))
            while len(timeline) > limit:
                timeline.pop(0)
        except Exception:
            pass

    def _trim_timeline_stack_count(self, timeline: list, stack: str, limit: int) -> None:
        """Keep timeline entries aligned with legacy backend stack limits."""
        try:
            limit = max(1, int(limit or 1))
            seen = 0
            keep = []
            for entry in reversed(list(timeline)):
                if str((entry or {}).get("stack") or "page") == str(stack):
                    seen += 1
                    if seen > limit:
                        continue
                keep.append(entry)
            timeline[:] = list(reversed(keep))
        except Exception:
            pass

    def _legacy_limit_for_timeline_stack(self, stack: str) -> int:
        stack = str(stack or "page")
        if stack == "project":
            return 20
        if stack == "view":
            return 80
        if stack == "command":
            return 120
        return 40

    def clear_redo_timeline(self, reason: str = "redo boundary") -> bool:
        try:
            before = len(getattr(self, "redo_timeline", []) or [])
            self.redo_timeline.clear()
            self._audit("UNDO_TIMELINE_CLEAR_REDO", reason=str(reason or ""), before=before, after=0, throttle_ms=120)
            return True
        except Exception:
            return False

    def register_undo_record(self, rec: Mapping[str, Any] | None, *, stack: str | None = None, clear_redo: bool = True, source: str = "") -> bool:
        if not rec:
            return False
        try:
            entry = self._timeline_entry(rec, stack=stack)
            self.undo_timeline.append(entry)
            self._trim_timeline_stack_count(self.undo_timeline, entry.get("stack") or "page", self._legacy_limit_for_timeline_stack(entry.get("stack") or "page"))
            self._trim_timeline(self.undo_timeline)
            if clear_redo:
                self.clear_redo_timeline(reason=source or entry.get("reason") or "new undo")
            self._audit("UNDO_TIMELINE_PUSH", **self._timeline_audit_fields(entry, source=source), clear_redo=bool(clear_redo), throttle_ms=80)
            return True
        except Exception as e:
            self._audit("UNDO_TIMELINE_PUSH_ERROR", error=repr(e), throttle_ms=120)
            return False

    def register_redo_record(self, rec: Mapping[str, Any] | None, *, stack: str | None = None, source: str = "") -> bool:
        if not rec:
            return False
        try:
            entry = self._timeline_entry(rec, stack=stack)
            self.redo_timeline.append(entry)
            self._trim_timeline_stack_count(self.redo_timeline, entry.get("stack") or "page", self._legacy_limit_for_timeline_stack(entry.get("stack") or "page"))
            self._trim_timeline(self.redo_timeline)
            self._audit("UNDO_TIMELINE_PUSH_REDO", **self._timeline_audit_fields(entry, source=source), throttle_ms=80)
            return True
        except Exception as e:
            self._audit("UNDO_TIMELINE_PUSH_REDO_ERROR", error=repr(e), throttle_ms=120)
            return False

    def push_command(self, command: Any, *, clear_redo: bool = True, source: str = "push_command") -> bool:
        """Push a Command/Diff undo entry into the canonical single timeline.

        Stage 5-1 only exposes the runtime entry point.  No existing feature is
        migrated here yet, so legacy page/view/project stacks remain untouched.
        """
        try:
            from ysb.core.command_undo import UndoCommand
            cmd = UndoCommand.from_mapping(command)
        except Exception as e:
            self._audit("UNDO_COMMAND_PUSH_ERROR", error=repr(e), source=str(source or ""), throttle_ms=120)
            return False
        try:
            if cmd.is_noop():
                self._audit("UNDO_COMMAND_PUSH_SKIP_NOOP", **cmd.summary(), source=str(source or ""), throttle_ms=120)
                return False
            entry = self._timeline_entry({
                "command": cmd,
                "reason": cmd.reason,
                "page_idx": cmd.page_idx,
                "_undo_scope": "command",
            }, stack="command")
            self.undo_timeline.append(entry)
            self._trim_timeline_stack_count(self.undo_timeline, "command", self._legacy_limit_for_timeline_stack("command"))
            self._trim_timeline(self.undo_timeline)
            if clear_redo:
                self.clear_redo_timeline(reason=source or cmd.reason or "new command")
            self._audit("UNDO_COMMAND_PUSH", **self._timeline_audit_fields(entry, source=source), clear_redo=bool(clear_redo), throttle_ms=80)
            owner = self.owner
            if owner is not None and hasattr(owner, "update_undo_redo_buttons"):
                try:
                    owner.update_undo_redo_buttons()
                except Exception:
                    pass
            return True
        except Exception as e:
            self._audit("UNDO_COMMAND_PUSH_ERROR", error=repr(e), source=str(source or ""), throttle_ms=120)
            return False

    def register_command_redo_entry(self, entry: Mapping[str, Any] | None, *, source: str = "command_undo") -> bool:
        if not entry:
            return False
        try:
            item = dict(entry)
            self.redo_timeline.append(item)
            self._trim_timeline_stack_count(self.redo_timeline, "command", self._legacy_limit_for_timeline_stack("command"))
            self._trim_timeline(self.redo_timeline)
            self._audit("UNDO_COMMAND_PUSH_REDO", **self._timeline_audit_fields(item, source=source), throttle_ms=80)
            return True
        except Exception as e:
            self._audit("UNDO_COMMAND_PUSH_REDO_ERROR", error=repr(e), source=str(source or ""), throttle_ms=120)
            return False

    def register_command_undo_entry(self, entry: Mapping[str, Any] | None, *, source: str = "command_redo") -> bool:
        if not entry:
            return False
        try:
            item = dict(entry)
            self.undo_timeline.append(item)
            self._trim_timeline_stack_count(self.undo_timeline, "command", self._legacy_limit_for_timeline_stack("command"))
            self._trim_timeline(self.undo_timeline)
            self._audit("UNDO_COMMAND_PUSH_UNDO", **self._timeline_audit_fields(item, source=source), throttle_ms=80)
            return True
        except Exception as e:
            self._audit("UNDO_COMMAND_PUSH_UNDO_ERROR", error=repr(e), source=str(source or ""), throttle_ms=120)
            return False

    def clear_timeline_for_page(self, page_idx: int | None = None, *, undo: bool = True, redo: bool = True, reason: str = "page boundary") -> bool:
        target = self._resolve_page_idx(page_idx=page_idx)
        changed = False
        try:
            if undo:
                before = len(self.undo_timeline)
                self.undo_timeline[:] = [e for e in self.undo_timeline if int(e.get("page_idx", -999999)) != target]
                changed = changed or before != len(self.undo_timeline)
            if redo:
                before = len(self.redo_timeline)
                self.redo_timeline[:] = [e for e in self.redo_timeline if int(e.get("page_idx", -999999)) != target]
                changed = changed or before != len(self.redo_timeline)
            if changed:
                self._audit("UNDO_TIMELINE_CLEAR_PAGE", page_idx=target, reason=str(reason or ""), throttle_ms=120)
            return changed
        except Exception:
            return False

    def clear_all_timeline(self, *, undo: bool = True, redo: bool = True, reason: str = "boundary") -> bool:
        try:
            if undo:
                self.undo_timeline.clear()
            if redo:
                self.redo_timeline.clear()
            self._audit("UNDO_TIMELINE_CLEAR_ALL", undo=bool(undo), redo=bool(redo), reason=str(reason or ""), throttle_ms=120)
            return True
        except Exception:
            return False

    def can_undo_timeline(self) -> bool:
        return bool(getattr(self, "undo_timeline", None))

    def can_redo_timeline(self) -> bool:
        return bool(getattr(self, "redo_timeline", None))

    def undo_general(self) -> bool:
        return bool(self.restore_engine().undo_timeline())

    def redo_general(self) -> bool:
        return bool(self.restore_engine().redo_timeline())

    # ------------------------------------------------------------------
    # restore execution API - stage 3-4
    # ------------------------------------------------------------------
    def restore_engine(self):
        if self._restore_engine is None:
            from ysb.core.undo_restore_engine import YSBUndoRestoreEngine
            self._restore_engine = YSBUndoRestoreEngine(self)
        return self._restore_engine

    def undo_current_page_view(self) -> bool:
        return bool(self.undo_general())

    def redo_current_page_view(self) -> bool:
        return bool(self.redo_general())

    def undo_current_page(self) -> bool:
        return bool(self.undo_general())

    def redo_current_page(self) -> bool:
        return bool(self.redo_general())

    def undo_project(self) -> bool:
        return bool(self.undo_general())

    def redo_project(self) -> bool:
        return bool(self.redo_general())

    # ------------------------------------------------------------------
    # active viewer paint history API - stage 3-3
    # ------------------------------------------------------------------
    def bind_paint_viewer(self, viewer: Any | None = None, *, clear: bool = False) -> bool:
        """Bind the active viewer's paint history aliases to UndoManager storage.

        Paint records still hold live QGraphicsItem/QPixmap references, so the
        history is intentionally tied to the active viewer scene.  A real base
        image change must clear it.
        """
        if viewer is None:
            try:
                viewer = getattr(self.owner, "view", None)
            except Exception:
                viewer = None
        if viewer is None:
            return False
        try:
            if clear:
                self.paint_history.clear()
                self.paint_redo_history.clear()
            else:
                old_history = getattr(viewer, "history", None)
                if isinstance(old_history, list) and old_history is not self.paint_history and old_history and not self.paint_history:
                    self.paint_history.extend(old_history)
                old_redo = getattr(viewer, "redo_history", None)
                if isinstance(old_redo, list) and old_redo is not self.paint_redo_history and old_redo and not self.paint_redo_history:
                    self.paint_redo_history.extend(old_redo)
            viewer.history = self.paint_history
            viewer.redo_history = self.paint_redo_history
            self.paint_viewer = viewer
            return True
        except Exception:
            return False

    def paint_history_stack(self, viewer: Any | None = None, create: bool = True):
        if create:
            self.bind_paint_viewer(viewer)
        return self.paint_history

    def paint_redo_history_stack(self, viewer: Any | None = None, create: bool = True):
        if create:
            self.bind_paint_viewer(viewer)
        return self.paint_redo_history

    def clear_paint_history(self, *, viewer: Any | None = None, undo: bool = True, redo: bool = True, update: bool = True, reason: str = "paint history clear") -> bool:
        self.bind_paint_viewer(viewer)
        changed = False
        try:
            if undo:
                self.paint_history.clear()
                changed = True
            if redo:
                self.paint_redo_history.clear()
                changed = True
            if undo or redo:
                self.clear_timeline_for_page(self._resolve_page_idx(), undo=undo, redo=redo, reason=reason or "clear_paint_history")
            if self.paint_viewer is not None:
                self.paint_viewer.history = self.paint_history
                self.paint_viewer.redo_history = self.paint_redo_history
            owner = self.owner
            if update and owner is not None and hasattr(owner, "update_undo_redo_buttons"):
                owner.update_undo_redo_buttons()
            self._audit("UNDO_MANAGER_CLEAR_PAINT_HISTORY", undo=bool(undo), redo=bool(redo), reason=str(reason or ""), changed=bool(changed), throttle_ms=120)
            return changed
        except Exception:
            return False

    def paint_stack_lengths(self, viewer: Any | None = None) -> dict[str, int]:
        self.bind_paint_viewer(viewer)
        return {
            "paint_undo": len(self.paint_history),
            "paint_redo": len(self.paint_redo_history),
        }

    # ------------------------------------------------------------------
    # public push API for future features
    # ------------------------------------------------------------------
    def push(self, rec: Mapping[str, Any] | None, *, policy: Mapping[str, Any] | UndoPolicy | None = None, **kwargs: Any) -> bool:
        if isinstance(policy, UndoPolicy):
            pol = policy
        else:
            pol = UndoPolicy.from_mapping(policy)
        self.last_policy = pol
        scope = str(kwargs.pop("scope", None) or pol.scope or PAGE_SCOPE).lower()
        if scope in (PROJECT_SCOPE, "project_structure"):
            return self.push_project(rec, **kwargs)
        if scope in (VIEW_SCOPE, "page_view"):
            return self.push_view(rec, **kwargs)
        if scope == BOUNDARY_SCOPE:
            return self.break_boundary(kind=kwargs.get("kind") or pol.label, name=kwargs.get("name") or pol.label)
        if scope == RUNTIME_SCOPE:
            return self.clear_runtime(reason=kwargs.get("reason") or pol.label)
        return self.push_page(rec, page_idx=kwargs.get("page_idx", pol.page_idx), clear_redo=kwargs.get("clear_redo", True))

    def push_page(self, rec: Mapping[str, Any] | None, *, page_idx: int | None = None, clear_redo: bool = True, reason: str | None = None) -> bool:
        record = self._copy_record(rec)
        if not record:
            return False
        target_page = self._resolve_page_idx(record, page_idx)
        record["page_idx"] = target_page
        record.setdefault("_undo_scope", PAGE_SCOPE)
        if reason:
            record.setdefault("reason", str(reason))
        self.sanitize_record(record, expected_scope=PAGE_SCOPE, page_idx=target_page, reason=str(reason or record.get("reason") or "작업"))
        self._annotate_record_policy(record, reason=record.get("reason"), scope=PAGE_SCOPE)
        if not self.validate_record(record, expected_scope=PAGE_SCOPE, source="push_page"):
            return False
        self._audit("UNDO_MANAGER_PUSH_PAGE", page_idx=target_page, reason=str(record.get("reason") or ""), clear_redo=bool(clear_redo), throttle_ms=120)
        fn = self._owner_method("append_page_undo_record")
        if fn is None:
            return False
        return bool(fn(record, page_idx=target_page, clear_redo=clear_redo))

    def push_page_redo(self, rec: Mapping[str, Any] | None, *, page_idx: int | None = None) -> bool:
        record = self._copy_record(rec)
        if not record:
            return False
        target_page = self._resolve_page_idx(record, page_idx)
        record["page_idx"] = target_page
        record.setdefault("_undo_scope", PAGE_SCOPE)
        self.sanitize_record(record, expected_scope=PAGE_SCOPE, page_idx=target_page, reason=str(record.get("reason") or "작업"))
        if not self.validate_record(record, expected_scope=PAGE_SCOPE, source="push_page_redo"):
            return False
        self._audit("UNDO_MANAGER_PUSH_PAGE_REDO", page_idx=target_page, reason=str(record.get("reason") or ""), throttle_ms=120)
        fn = self._owner_method("append_page_redo_record")
        if fn is None:
            return False
        return bool(fn(record, page_idx=target_page))

    def push_project(self, rec: Mapping[str, Any] | None, *, clear_redo: bool = True, reason: str | None = None) -> bool:
        record = self._copy_record(rec)
        if not record:
            return False
        record.setdefault("_undo_scope", PROJECT_SCOPE)
        if reason:
            record.setdefault("reason", str(reason))
        self.sanitize_record(record, expected_scope=PROJECT_SCOPE, reason=str(reason or record.get("reason") or "작업"))
        self._annotate_record_policy(record, reason=record.get("reason"), scope=PROJECT_SCOPE)
        if not self.validate_record(record, expected_scope=PROJECT_SCOPE, source="push_project"):
            return False
        self._audit("UNDO_MANAGER_PUSH_PROJECT", reason=str(record.get("reason") or ""), clear_redo=bool(clear_redo), throttle_ms=120)
        fn = self._owner_method("append_project_undo_record")
        if fn is None:
            return False
        return bool(fn(record, clear_redo=clear_redo))

    def push_project_redo(self, rec: Mapping[str, Any] | None) -> bool:
        record = self._copy_record(rec)
        if not record:
            return False
        record.setdefault("_undo_scope", PROJECT_SCOPE)
        self.sanitize_record(record, expected_scope=PROJECT_SCOPE, reason=str(record.get("reason") or "작업"))
        if not self.validate_record(record, expected_scope=PROJECT_SCOPE, source="push_project_redo"):
            return False
        self._audit("UNDO_MANAGER_PUSH_PROJECT_REDO", reason=str(record.get("reason") or ""), throttle_ms=120)
        fn = self._owner_method("append_project_redo_record")
        if fn is None:
            return False
        return bool(fn(record))

    def push_view(self, rec: Mapping[str, Any] | None, *, page_idx: int | None = None, clear_redo: bool = True, reason: str | None = None) -> bool:
        record = self._copy_record(rec)
        if not record:
            return False
        target_page = self._resolve_page_idx(record, page_idx)
        record["page_idx"] = target_page
        record["view_only"] = True
        record["ui_only"] = True
        record["_undo_scope"] = "page_view"
        if reason:
            record.setdefault("reason", str(reason))
        self.sanitize_record(record, expected_scope="view", page_idx=target_page, reason=str(reason or record.get("reason") or "화면 이동"))
        self._annotate_record_policy(record, reason=record.get("reason"), scope=VIEW_SCOPE)
        if not self.validate_record(record, expected_scope="view", source="push_view"):
            return False
        self._audit("UNDO_MANAGER_PUSH_VIEW", page_idx=target_page, reason=str(record.get("reason") or ""), clear_redo=bool(clear_redo), throttle_ms=120)
        fn = self._owner_method("append_page_view_undo_record")
        if fn is not None:
            return bool(fn(record, page_idx=target_page, clear_redo=clear_redo))
        return self.push_page(record, page_idx=target_page, clear_redo=clear_redo)

    def push_view_redo(self, rec: Mapping[str, Any] | None, *, page_idx: int | None = None) -> bool:
        record = self._copy_record(rec)
        if not record:
            return False
        target_page = self._resolve_page_idx(record, page_idx)
        record["page_idx"] = target_page
        record["view_only"] = True
        record["ui_only"] = True
        record["_undo_scope"] = "page_view"
        self.sanitize_record(record, expected_scope="view", page_idx=target_page, reason=str(record.get("reason") or "화면 이동"))
        if not self.validate_record(record, expected_scope="view", source="push_view_redo"):
            return False
        self._audit("UNDO_MANAGER_PUSH_VIEW_REDO", page_idx=target_page, reason=str(record.get("reason") or ""), throttle_ms=120)
        fn = self._owner_method("append_page_view_redo_record")
        if fn is not None:
            return bool(fn(record, page_idx=target_page))
        return self.push_page_redo(record, page_idx=target_page)

    # ------------------------------------------------------------------
    # paint / mask gateway
    # ------------------------------------------------------------------
    def _paint_reason(self, kind: str | None = None, reason: str | None = None) -> str:
        if reason:
            return str(reason)
        k = str(kind or "").strip().lower()
        if k == "final_paint":
            return "최종 페인팅"
        if k == "mask":
            return "마스크 브러시"
        return "페인팅"

    def push_paint_marker(self, *, kind: str | None = None, reason: str | None = None, page_idx: int | None = None, mode: int | None = None, clear_redo: bool = True) -> bool:
        """Push the light page-undo marker for a viewer paint history item.

        Stage 2-3 still keeps the heavy QPixmap patch history inside Viewer.
        This method owns only the Ctrl+Z timeline marker that connects that
        viewer history entry to the page undo stack.
        """
        owner = self.owner
        target_page = self._resolve_page_idx(page_idx=page_idx)
        if mode is None:
            try:
                mode = int(owner.cb_mode.currentIndex()) if owner is not None and hasattr(owner, "cb_mode") else int(getattr(owner, "last_mode", 0) or 0)
            except Exception:
                mode = 0
        reason_s = self._paint_reason(kind, reason)
        rec = {
            "reason": reason_s,
            "page_idx": int(target_page),
            "mode": int(mode or 0),
            "paint_history": True,
            "paint_kind": str(kind or ""),
            "_undo_scope": PAGE_SCOPE,
            "_undo_unit": KIND_PAINT if str(kind or "").lower() == "final_paint" else KIND_MASK,
        }
        self._annotate_record_policy(rec, reason=reason_s, scope=PAGE_SCOPE)
        if not self.validate_record(rec, expected_scope=PAGE_SCOPE, source="push_paint_marker"):
            return False
        self._audit("UNDO_MANAGER_PUSH_PAINT_MARKER", page_idx=target_page, kind=str(kind or ""), reason=reason_s, clear_redo=bool(clear_redo), throttle_ms=100)
        return self.push_page(rec, page_idx=target_page, clear_redo=clear_redo)

    def clear_paint_redo(self, *, viewer: Any | None = None, page_idx: int | None = None, reason: str = "paint redo boundary") -> bool:
        """Clear paint redo through the manager-owned active paint stack."""
        self.bind_paint_viewer(viewer)
        changed = False
        try:
            self.paint_redo_history.clear()
            changed = True
            if self.paint_viewer is not None:
                self.paint_viewer.redo_history = self.paint_redo_history
        except Exception:
            pass
        self._audit("UNDO_MANAGER_CLEAR_PAINT_REDO", page_idx=self._resolve_page_idx(page_idx=page_idx), reason=str(reason or ""), changed=bool(changed), throttle_ms=100)
        return changed

    def _paint_layer_id_for_record(self, viewer: Any, target_item: Any = None, kind: str | None = None) -> str:
        """Return a stable runtime layer id for a paint/mask patch command."""
        k = str(kind or "").lower()
        try:
            if viewer is not None:
                if target_item is getattr(viewer, "final_paint_above_item", None):
                    return "paint_layer:final_paint_above"
                if target_item is getattr(viewer, "final_paint_item", None):
                    return "paint_layer:final_paint"
                if target_item is getattr(viewer, "user_mask_item", None):
                    return "paint_layer:mask"
        except Exception:
            pass
        if k == "mask":
            return "paint_layer:mask"
        return "paint_layer:final_paint"

    def _clone_paint_patch_list_for_command(self, patches: Any, *, target_item: Any = None, direction_current_as_after: bool = False) -> list[dict[str, Any]]:
        """Normalize brush/paint patch records into rect/before/after entries.

        Patch values intentionally keep QPixmap/QRect objects directly.  Stage 7
        paint/mask commands are runtime undo data only and are not written into
        the project file format.
        """
        out: list[dict[str, Any]] = []
        for patch in list(patches or []):
            if not isinstance(patch, dict):
                continue
            rect = patch.get("rect") or patch.get("dirty_rect")
            if rect is None:
                continue
            before = patch.get("before")
            after = patch.get("after")
            if before is None and patch.get("patch") is not None:
                before = patch.get("patch")
            if after is None and direction_current_as_after and target_item is not None:
                try:
                    after = target_item.pixmap().copy(rect)
                except Exception:
                    after = None
            if before is None or after is None:
                continue
            out.append({"rect": rect, "before": before, "after": after})
        return out


    def _pixmap_alpha_np_for_command(self, pixmap: Any):
        """Return the alpha channel of a QPixmap/QImage patch as uint8 numpy array."""
        if pixmap is None:
            return None
        try:
            import numpy as _np
            try:
                from PyQt6.QtGui import QImage
            except Exception:
                QImage = None
            qimg = pixmap.toImage() if hasattr(pixmap, "toImage") else pixmap
            if QImage is not None:
                qimg = qimg.convertToFormat(QImage.Format.Format_ARGB32)
            w = int(qimg.width())
            h = int(qimg.height())
            if w <= 0 or h <= 0:
                return None
            bpl = int(qimg.bytesPerLine())
            ptr = qimg.bits()
            ptr.setsize(int(qimg.sizeInBytes()))
            buf = _np.frombuffer(ptr, dtype=_np.uint8).reshape((h, bpl // 4, 4))
            return buf[:, :w, 3].copy()
        except Exception:
            return None

    def _build_mask_state_from_patch_list_for_command(self, viewer: Any, patch_list: Any):
        """Build full before/after editable mask states from bbox patches.

        New user-painted mask and loaded OCR/page masks must share the same Undo
        baseline.  The visible overlay is the editable mask in the current tab, so
        capture the current overlay alpha as `after` and reconstruct `before` by
        replacing the dirty bboxes with each patch's before alpha.  This makes
        erasing an already-loaded mask undo exactly like erasing a newly painted
        mask.
        """
        try:
            import numpy as _np
        except Exception:
            return None, None, {}
        if viewer is None:
            return None, None, {}
        try:
            after = viewer.get_mask_np()
        except Exception:
            after = None
        if not isinstance(after, _np.ndarray):
            return None, None, {}
        before = after.copy()
        changed_rects = 0
        for patch in list(patch_list or []):
            try:
                rect = patch.get("rect") if isinstance(patch, dict) else None
                before_pix = patch.get("before") if isinstance(patch, dict) else None
                alpha = self._pixmap_alpha_np_for_command(before_pix)
                if rect is None or alpha is None:
                    continue
                x = max(0, int(rect.x()))
                y = max(0, int(rect.y()))
                w = max(0, int(rect.width()))
                h = max(0, int(rect.height()))
                if w <= 0 or h <= 0:
                    continue
                h2 = min(h, before.shape[0] - y, alpha.shape[0])
                w2 = min(w, before.shape[1] - x, alpha.shape[1])
                if h2 <= 0 or w2 <= 0:
                    continue
                before[y:y+h2, x:x+w2] = alpha[:h2, :w2]
                changed_rects += 1
            except Exception:
                continue
        try:
            before_nonzero = int(_np.count_nonzero(before))
            after_nonzero = int(_np.count_nonzero(after))
        except Exception:
            before_nonzero = after_nonzero = -1
        return before, after.copy(), {
            "mask_state_patch_rects": changed_rects,
            "mask_before_nonzero": before_nonzero,
            "mask_after_nonzero": after_nonzero,
        }

    def _paint_record_to_patch_command(self, viewer: Any, record: Any, *, kind: str | None = None, reason: str | None = None, page_idx: int | None = None, mode: int | None = None):
        """Build a runtime Command/Diff paint/mask patch command from a viewer record."""
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return None
        if viewer is None or record is None:
            return None
        target_item = None
        patch_list = []
        record_kind = kind
        try:
            if isinstance(record, dict) and record.get("_brush_record"):
                target_item = record.get("target_item")
                record_kind = record.get("kind") or kind
                patch_list = self._clone_paint_patch_list_for_command(record.get("patches") or [], target_item=target_item)
            elif isinstance(record, dict) and record.get("dirty_rect") is not None:
                target_item = record.get("target_item")
                rect = record.get("dirty_rect")
                before = record.get("patch")
                after = None
                try:
                    after = target_item.pixmap().copy(rect) if target_item is not None and rect is not None else None
                except Exception:
                    after = None
                patch_list = self._clone_paint_patch_list_for_command(
                    [{"rect": rect, "before": before, "after": after}],
                    target_item=target_item,
                )
            else:
                return None
        except Exception:
            return None
        if not patch_list:
            return None
        target_page = self._resolve_page_idx(page_idx=page_idx)
        if mode is None:
            try:
                owner = self.owner
                mode = int(owner.cb_mode.currentIndex()) if owner is not None and hasattr(owner, "cb_mode") else int(getattr(owner, "last_mode", 0) or 0)
            except Exception:
                mode = 0
        layer_id = self._paint_layer_id_for_record(viewer, target_item=target_item, kind=record_kind)
        kind_s = str(record_kind or ("mask" if layer_id.endswith(":mask") else "final_paint"))
        reason_s = self._paint_reason(kind_s, reason)
        before_patches = [{"rect": p.get("rect"), "pixmap": p.get("before")} for p in patch_list]
        after_patches = [{"rect": p.get("rect"), "pixmap": p.get("after")} for p in patch_list]
        try:
            mode_i = int(mode or 0)
        except Exception:
            mode_i = 0
        command_meta = {
            "kind": kind_s,
            "layer_id": layer_id,
            "mode": mode_i,
            "patch_count": len(patch_list),
            "stage": "undo_command_diff_stage7_mask_state_stabilized",
        }
        changes = [FieldChange(
            target_id=layer_id,
            field="patches",
            before=before_patches,
            after=after_patches,
            component_type="paint_mask_patch",
            page_idx=int(target_page),
            meta=dict(command_meta),
        )]
        if str(kind_s).lower() == "mask" or str(layer_id).endswith(":mask"):
            before_mask, after_mask, mask_meta = self._build_mask_state_from_patch_list_for_command(viewer, patch_list)
            if before_mask is not None and after_mask is not None:
                active_key = ""
                try:
                    owner = self.owner
                    if owner is not None and hasattr(owner, "active_mask_key"):
                        active_key = str(owner.active_mask_key(mode_i) or "")
                except Exception:
                    active_key = ""
                state_meta = dict(command_meta)
                state_meta.update(mask_meta or {})
                state_meta["active_key"] = active_key
                state_meta["mask_state_full"] = True
                changes.append(FieldChange(
                    target_id=layer_id,
                    field="mask_state",
                    before=before_mask,
                    after=after_mask,
                    component_type="paint_mask_patch",
                    page_idx=int(target_page),
                    meta=state_meta,
                ))
                command_meta.update(mask_meta or {})
                command_meta["active_key"] = active_key
                command_meta["mask_state_full"] = True
        return UndoCommand(
            reason=reason_s,
            page_idx=int(target_page),
            component_type="paint_mask_patch",
            target_ids=[layer_id],
            changes=changes,
            merge_key=f"paint_mask_patch:{target_page}:{layer_id}:{reason_s}",
            meta=command_meta,
        )

    def push_paint_view_record(self, viewer: Any, record: Any, *, kind: str | None = None, reason: str | None = None, max_history: int = 80, page_idx: int | None = None, mode: int | None = None) -> bool:
        """Push paint/mask edits through the legacy viewer patch history.

        Text/style/geometry commands stay on the Command-Diff timeline, but
        paint and mask edits are pixel-patch operations.  Keeping the QPixmap
        patch payload in viewer.history is faster and matches the visible layer
        exactly, especially when erasing masks that already existed when the
        page was loaded.  The global timeline only receives a lightweight
        paint_history marker so Ctrl+Z order is still preserved.
        """
        if viewer is None or record is None:
            return False
        try:
            self.bind_paint_viewer(viewer)
            history = self.paint_history
            history.append(record)
            try:
                limit = max(1, int(max_history or 80))
            except Exception:
                limit = 80
            while len(history) > limit:
                history.pop(0)
            try:
                viewer.history = history
            except Exception:
                pass
            try:
                self.clear_paint_redo(viewer=viewer, page_idx=page_idx, reason=reason or "paint record")
            except Exception:
                pass
            ok = self.push_paint_marker(kind=kind, reason=reason, page_idx=page_idx, mode=mode, clear_redo=True)
            self._audit(
                "UNDO_MANAGER_PUSH_PAINT_RECORD_LEGACY",
                page_idx=self._resolve_page_idx(page_idx=page_idx),
                kind=str(kind or ""),
                reason=self._paint_reason(kind, reason),
                marker_ok=bool(ok),
                history_len=len(history),
                throttle_ms=100,
            )
            return bool(ok)
        except Exception as e:
            self._audit("UNDO_MANAGER_PUSH_PAINT_RECORD_ERROR", error=repr(e), throttle_ms=100)
            return False

    def commit_paint_layer(self, kind: str | None = None, *, delay_ms: int = 1200) -> bool:
        """Schedule the existing delayed layer commit through the manager."""
        owner = self.owner
        if owner is None:
            return False
        layer_kind = "final_paint" if str(kind or "").lower() == "final_paint" else "mask"
        self._audit("UNDO_MANAGER_COMMIT_PAINT_LAYER", kind=layer_kind, delay_ms=int(delay_ms or 1200), throttle_ms=100)
        fn = self._owner_method("schedule_deferred_view_layer_commit")
        if fn is None:
            return False
        try:
            fn(layer_kind, delay_ms=delay_ms)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # boundary / clearing API
    # ------------------------------------------------------------------
    def _boundary_policy_for(self, kind: str | None):
        raw = str(kind or "action").strip()
        # Dynamic batch markers currently arrive as batch_start/batch_finish or
        # batch_<reason>.  Keep those under the batch policy unless a more
        # specific policy exists.
        try:
            pol = self._policy_for_reason(raw)
            if pol is not None and pol.action != "작업":
                return pol
        except Exception:
            pass
        lower = raw.lower()
        alias = raw
        if lower.startswith("batch_"):
            alias = "batch_inpaint" if "inpaint" in lower else "batch"
        elif lower in ("analysis", "reanalyze", "translation", "inpaint", "clean_import", "clean_import_recovered", "restore_original_source", "use_background_as_source", "macro", "project_open"):
            alias = raw
        try:
            return self._policy_for_reason(alias)
        except Exception:
            return None

    def _mark_boundary(self, kind: str = "action", name: str = "", policy: str = "") -> None:
        owner = self.owner
        if owner is None:
            return
        try:
            owner.undo_boundary = {"kind": str(kind or "action"), "name": str(name or ""), "policy": str(policy or "")}
        except Exception:
            pass
        try:
            if hasattr(owner, "undo_boundary_log_text") and hasattr(owner, "log"):
                owner.log(owner.undo_boundary_log_text("set", kind, name))
        except Exception:
            pass
        try:
            if hasattr(owner, "update_undo_redo_buttons"):
                owner.update_undo_redo_buttons()
        except Exception:
            pass

    def apply_boundary(self, kind: str = "action", name: str = "", *, page_idx: int | None = None, selected_page_indices: Any | None = None) -> bool:
        """Apply an undo boundary using undo_policies instead of hard-coded calls.

        Stage 2-4 centralizes the decision of whether a boundary clears only the
        current page, all pages, project undo, or falls back to the legacy full
        clear.  Actual stack ownership still remains in MainWindowHistoryMixin.
        """
        raw_kind = str(kind or "action").strip() or "action"
        display_name = str(name or "")
        pol = self._boundary_policy_for(raw_kind)
        boundary_policy = str(getattr(pol, "boundary_policy", "") or "legacy_clear_all")
        action = str(getattr(pol, "action", raw_kind) or raw_kind)
        self._audit(
            "UNDO_MANAGER_APPLY_BOUNDARY",
            kind=raw_kind,
            name=display_name,
            action=action,
            policy=boundary_policy,
            page_idx=self._resolve_page_idx(page_idx=page_idx),
            throttle_ms=80,
        )

        # Any external commit/boundary invalidates deferred records.
        try:
            if self.owner is not None:
                self.owner._deferred_undo_records = {}
        except Exception:
            pass

        if boundary_policy in ("legacy", "legacy_clear_all", "policy"):
            return self.break_boundary(raw_kind, display_name)

        ok = False
        target_page = self._resolve_page_idx(page_idx=page_idx)
        if boundary_policy == "clear_page":
            ok = self.clear_page(page_idx=page_idx, reason=f"undo boundary: {raw_kind}")
        elif boundary_policy == "clear_all_pages":
            ok = self.clear_all_pages(reason=f"undo boundary: {raw_kind}")
            # Batch/multi-page external commits can invalidate project-level
            # redo/undo assumptions as well, so clear project stacks too.
            self.clear_project(reason=f"undo boundary: {raw_kind}")
        elif boundary_policy == "clear_all":
            ok = self.clear_all_pages(reason=f"undo boundary: {raw_kind}")
            self.clear_project(reason=f"undo boundary: {raw_kind}")
        elif boundary_policy == "page_or_batch":
            count = 0
            try:
                count = len(list(selected_page_indices or []))
            except Exception:
                count = 0
            if count > 1:
                ok = self.clear_all_pages(reason=f"undo boundary: {raw_kind}")
                self.clear_project(reason=f"undo boundary: {raw_kind}")
            else:
                ok = self.clear_page(page_idx=page_idx, reason=f"undo boundary: {raw_kind}")
        else:
            # Unknown policy: use the old full-clear behavior because it is the
            # safest fallback for external commits.
            return self.break_boundary(raw_kind, display_name)

        self._mark_boundary(raw_kind, display_name, boundary_policy)
        return bool(ok)

    def break_boundary(self, kind: str = "action", name: str = "") -> bool:
        self._audit("UNDO_MANAGER_BREAK_BOUNDARY_LEGACY", kind=str(kind or "action"), name=str(name or ""), throttle_ms=80)
        fn = self._owner_method("break_undo_chain")
        if fn is None:
            return False
        return bool(fn(kind, name))

    def clear_page(self, page_idx: int | None = None, reason: str = "page boundary") -> bool:
        target_page = self._resolve_page_idx(page_idx=page_idx)
        self._audit("UNDO_MANAGER_CLEAR_PAGE", page_idx=target_page, reason=str(reason or ""), throttle_ms=120)
        ok = self.clear_page_storage(page_idx=target_page, undo=True, redo=True, view=True, update=False)
        try:
            owner = self.owner
            current_page = int(getattr(owner, "idx", 0) or 0) if owner is not None else target_page
            if owner is not None and target_page == current_page and hasattr(owner, "_clear_view_runtime_undo"):
                owner._clear_view_runtime_undo()
            if owner is not None and hasattr(owner, "update_undo_redo_buttons"):
                owner.update_undo_redo_buttons()
        except Exception:
            pass
        return bool(ok)

    def clear_page_redo(self, page_idx: int | None = None, reason: str = "redo boundary") -> bool:
        """Clear redo stacks for one page through the central gateway."""
        target_page = self._resolve_page_idx(page_idx=page_idx)
        self._audit("UNDO_MANAGER_CLEAR_PAGE_REDO", page_idx=target_page, reason=str(reason or ""), throttle_ms=120)
        changed = False
        try:
            redo_stack = self.page_redo_stack(target_page, create=True)
            redo_stack.clear()
            changed = True
        except Exception:
            pass
        try:
            view_redo_stack = self.page_view_redo_stack(target_page, create=True)
            view_redo_stack.clear()
            changed = True
        except Exception:
            pass
        try:
            owner = self.owner
            if owner is not None and hasattr(owner, "update_undo_redo_buttons"):
                owner.update_undo_redo_buttons()
        except Exception:
            pass
        return changed

    def clear_all_pages(self, reason: str = "page boundary") -> bool:
        self._audit("UNDO_MANAGER_CLEAR_ALL_PAGES", reason=str(reason or ""), throttle_ms=120)
        ok = self.clear_all_page_storage(update=False)
        try:
            owner = self.owner
            if owner is not None and hasattr(owner, "_clear_view_runtime_undo"):
                owner._clear_view_runtime_undo()
            if owner is not None and hasattr(owner, "update_undo_redo_buttons"):
                owner.update_undo_redo_buttons()
        except Exception:
            pass
        return bool(ok)

    def clear_project(self, reason: str = "project boundary") -> bool:
        """Clear project-level undo/redo stacks through the central gateway."""
        self._audit("UNDO_MANAGER_CLEAR_PROJECT", reason=str(reason or ""), throttle_ms=120)
        return self.clear_project_storage(undo=True, redo=True, update=True)

    def clear_runtime(self, reason: str = "runtime") -> bool:
        self._audit("UNDO_MANAGER_CLEAR_RUNTIME", reason=str(reason or ""), throttle_ms=120)
        fn = self._owner_method("_clear_view_runtime_undo")
        if fn is None:
            return False
        fn()
        return True

    def push_text_line(self, reason: str = "텍스트 작업", *, page_idx: int | None = None, include_masks: bool | None = None, clear_redo: bool = True) -> bool:
        """Create and push a page-local text-line checkpoint through the manager.

        Stage 2-2 keeps the old record format, but text feature code can now
        enter through this policy-aware method instead of calling the legacy
        push_text_line_undo path directly.
        """
        owner = self.owner
        if owner is None:
            return False
        # Keep the same safety gates as the legacy push_text_line_undo path.
        try:
            if getattr(owner, "_project_undo_restore_lock", False):
                return False
            if getattr(owner, "macro_running", False) or getattr(owner, "_suppress_project_undo", False):
                return False
            if getattr(owner, "is_loading_project", False) or getattr(owner, "is_page_loading", False) or getattr(owner, "is_batch_running", False):
                return False
            paths = getattr(owner, "paths", []) or []
            data = getattr(owner, "data", {}) or {}
            if not paths or (page_idx is None and getattr(owner, "idx", 0) not in data):
                return False
        except Exception:
            return False
        pol = self._policy_for_reason(reason)
        if include_masks is None:
            try:
                include_masks = bool(pol and ("mask" in tuple(pol.dirty_kinds)))
            except Exception:
                include_masks = False
        target_page = self._resolve_page_idx(page_idx=page_idx)
        factory = self._factory()
        if factory is not None:
            rec = factory.make_text_line_undo_record(reason, page_idx=target_page, include_masks=bool(include_masks))
        else:
            fn = self._owner_method("make_text_line_undo_record")
            if fn is None:
                return False
            rec = fn(reason, page_idx=target_page, include_masks=bool(include_masks))
        rec.setdefault("_undo_scope", PAGE_SCOPE)
        rec.setdefault("_undo_unit", KIND_TEXT_LINE)
        self._annotate_record_policy(rec, reason=reason, scope=PAGE_SCOPE)
        self._audit("UNDO_MANAGER_PUSH_TEXT_LINE", page_idx=target_page, reason=str(reason or ""), include_masks=bool(include_masks), throttle_ms=120)
        return self.push_page(rec, page_idx=target_page, clear_redo=clear_redo)

    def push_text_checkpoint(self, reason: str = "텍스트 작업") -> bool:
        self._audit("UNDO_MANAGER_TEXT_CHECKPOINT", reason=str(reason or ""), throttle_ms=120)
        return self.push_text_line(reason=reason, include_masks=False)

    def push_ui_state(self, reason: str = "화면 작업", *, page_idx: int | None = None, mode: int | None = None, view_state: Mapping[str, Any] | None = None, clear_redo: bool = True) -> bool:
        """Push UI/page-mode/view state using the policy map to choose a route."""
        target_page = self._resolve_page_idx(page_idx=page_idx)
        factory = self._factory()
        if factory is not None:
            rec = factory.make_ui_undo_record(reason, page_idx=target_page, mode=mode)
        else:
            fn = self._owner_method("make_ui_undo_record")
            if fn is None:
                return False
            rec = fn(reason, page_idx=target_page, mode=mode)
        if view_state is not None:
            try:
                rec["view_state"] = copy.deepcopy(dict(view_state))
            except Exception:
                rec["view_state"] = copy.deepcopy(view_state)
        pol = self._policy_for_reason(reason)
        if pol is not None and pol.kind == KIND_VIEW:
            rec["view_only"] = True
            rec["ui_only"] = True
            rec["_undo_scope"] = "page_view"
            self._annotate_record_policy(rec, reason=reason, scope=SCOPE_VIEW)
            return self.push_view(rec, page_idx=target_page, clear_redo=clear_redo)
        rec["ui_only"] = True
        rec.setdefault("_undo_scope", SCOPE_PAGE)
        self._annotate_record_policy(rec, reason=reason, scope=SCOPE_PAGE)
        if pol is not None and pol.scope == SCOPE_PROJECT:
            rec["_undo_scope"] = SCOPE_PROJECT
            return self.push_project(rec, clear_redo=clear_redo)
        return self.push_page(rec, page_idx=target_page, clear_redo=clear_redo)

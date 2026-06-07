# -*- coding: utf-8 -*-
"""Undo/Redo restore execution engine for YSB Game Editor.

Stage 3-4 purpose:
- UndoManager already owns page/project/view/paint stacks.
- This engine owns the actual pop/restore/redo-push execution flow.
- MainWindowHistoryMixin keeps the low-level restore helpers and becomes a thin
  compatibility wrapper for Ctrl+Z/Ctrl+Y entry points.

This file intentionally calls owner restore helpers instead of duplicating the
heavy UI/data restore logic.  Stage 3-5 can add stronger record validation.
"""

from __future__ import annotations

from typing import Any


class YSBUndoRestoreEngine:
    def __init__(self, manager: Any):
        self.manager = manager

    @property
    def owner(self):
        return getattr(self.manager, "owner", None)

    def _update_buttons(self) -> None:
        owner = self.owner
        try:
            if owner is not None and hasattr(owner, "update_undo_redo_buttons"):
                owner.update_undo_redo_buttons()
        except Exception:
            pass

    def _log(self, message: str) -> None:
        owner = self.owner
        try:
            if owner is not None and hasattr(owner, "log"):
                owner.log(message)
        except Exception:
            pass

    def _audit(self, event: str, **fields: Any) -> None:
        try:
            if hasattr(self.manager, "_audit"):
                self.manager._audit(event, **fields)
                return
        except Exception:
            pass
        owner = self.owner
        try:
            if owner is not None and hasattr(owner, "audit_boundary_event"):
                owner.audit_boundary_event(event, **fields)
        except Exception:
            pass

    def _entry_summary(self, entry: dict | None) -> dict:
        entry = entry or {}
        return {
            "seq": entry.get("seq", ""),
            "stack": entry.get("stack", "page"),
            "page_idx": entry.get("page_idx", ""),
            "reason": entry.get("reason", ""),
            "command_id": entry.get("command_id", ""),
            "component_type": entry.get("component_type", ""),
            "change_count": entry.get("change_count", ""),
            "undo_size": len(getattr(self.manager, "undo_timeline", []) or []),
            "redo_size": len(getattr(self.manager, "redo_timeline", []) or []),
        }

    def _cancel_runtime(self) -> None:
        owner = self.owner
        try:
            if owner is not None and hasattr(owner, "cancel_live_text_transform_runtime"):
                owner.cancel_live_text_transform_runtime()
        except Exception:
            pass

    def _validate_record(self, rec, expected_scope: str, source: str) -> bool:
        try:
            if hasattr(self.manager, "validate_record"):
                return bool(self.manager.validate_record(rec, expected_scope=expected_scope, source=source))
        except Exception:
            return True
        return True

    def _coerce_command_from_entry(self, entry: dict):
        try:
            from ysb.core.command_undo import UndoCommand
            command = (entry or {}).get("command")
            if command is not None:
                return UndoCommand.from_mapping(command)
            payload = (entry or {}).get("command_payload")
            if payload is not None:
                return UndoCommand.from_mapping(payload)
        except Exception:
            return None
        return None

    def _timeline_dispatch_command(self, entry: dict, *, redo: bool = False) -> bool:
        command = self._coerce_command_from_entry(entry)
        if command is None:
            self._audit("UNDO_COMMAND_DISPATCH_MISSING", **self._entry_summary(entry), redo=bool(redo), throttle_ms=120)
            return False
        owner = self.owner
        try:
            self._cancel_runtime()
            ok = bool(command.redo(owner) if redo else command.undo(owner))
        except Exception as e:
            self._audit("UNDO_COMMAND_DISPATCH_ERROR", **self._entry_summary(entry), redo=bool(redo), error=repr(e), throttle_ms=120)
            return False
        if not ok:
            self._audit("UNDO_COMMAND_DISPATCH_FAILED", **self._entry_summary(entry), redo=bool(redo), throttle_ms=120)
            return False
        try:
            entry["command"] = command
            entry.setdefault("command_id", str(getattr(command, "command_id", "") or ""))
            entry.setdefault("component_type", str(getattr(command, "component_type", "") or ""))
            entry.setdefault("change_count", int(getattr(command, "change_count", 0) or 0))
            if redo:
                if hasattr(self.manager, "register_command_undo_entry"):
                    self.manager.register_command_undo_entry(entry, source="command_redo")
                else:
                    self.manager.undo_timeline.append(entry)
            else:
                if hasattr(self.manager, "register_command_redo_entry"):
                    self.manager.register_command_redo_entry(entry, source="command_undo")
                else:
                    self.manager.redo_timeline.append(entry)
            self._audit("UNDO_COMMAND_DISPATCH_OK", **self._entry_summary(entry), redo=bool(redo), throttle_ms=80)
            return True
        except Exception as e:
            self._audit("UNDO_COMMAND_DISPATCH_POST_ERROR", **self._entry_summary(entry), redo=bool(redo), error=repr(e), throttle_ms=120)
            return False

    def _timeline_dispatch(self, entry: dict, *, redo: bool = False) -> bool:
        stack = str((entry or {}).get("stack") or "page")
        try:
            self._audit("UNDO_TIMELINE_DISPATCH", **self._entry_summary(entry), redo=bool(redo), throttle_ms=80)
            if stack == "command":
                return self._timeline_dispatch_command(entry, redo=redo)
            if stack == "view":
                return self.redo_view() if redo else self.undo_view()
            if stack == "project":
                return self.redo_project() if redo else self.undo_project()
            return self.redo_page() if redo else self.undo_page()
        except Exception as e:
            self._audit("UNDO_TIMELINE_DISPATCH_ERROR", **self._entry_summary(entry), redo=bool(redo), error=repr(e), throttle_ms=120)
            self._update_buttons()
            return False

    def undo_timeline(self) -> bool:
        """Undo exactly the latest user action in one global timeline."""
        timeline = getattr(self.manager, "undo_timeline", None)
        if not timeline:
            # Legacy fallback for stacks that were created before Stage 4 timeline existed.
            if self.undo_page():
                return True
            if self.undo_project():
                return True
            if self.undo_view():
                return True
            return False
        entry = timeline.pop()
        self._audit("UNDO_TIMELINE_POP", **self._entry_summary(entry), redo=False, throttle_ms=80)
        ok = self._timeline_dispatch(entry, redo=False)
        if not ok:
            timeline.append(entry)
            self._audit("UNDO_TIMELINE_RESTORE_ENTRY_AFTER_FAIL", **self._entry_summary(entry), redo=False, throttle_ms=120)
        self._update_buttons()
        return bool(ok)

    def redo_timeline(self) -> bool:
        """Redo exactly the latest undone user action in one global timeline."""
        timeline = getattr(self.manager, "redo_timeline", None)
        if not timeline:
            if self.redo_page():
                return True
            if self.redo_project():
                return True
            if self.redo_view():
                return True
            return False
        entry = timeline.pop()
        self._audit("UNDO_TIMELINE_POP", **self._entry_summary(entry), redo=True, throttle_ms=80)
        ok = self._timeline_dispatch(entry, redo=True)
        if not ok:
            timeline.append(entry)
            self._audit("UNDO_TIMELINE_RESTORE_ENTRY_AFTER_FAIL", **self._entry_summary(entry), redo=True, throttle_ms=120)
        self._update_buttons()
        return bool(ok)

    def undo_view(self) -> bool:
        owner = self.owner
        if owner is None:
            return False
        try:
            owner.ensure_page_undo_state()
            page_idx = int(getattr(owner, "idx", 0) or 0)
            stack = self.manager.page_view_undo_stack(page_idx, create=True)
            if not stack:
                try:
                    if hasattr(owner, "audit_boundary_event"):
                        owner.audit_boundary_event("UNDO_CURRENT_PAGE_EMPTY", page_idx=page_idx, throttle_ms=200)
                except Exception:
                    pass
                self._update_buttons()
                return False

            rec = stack.pop()
            if not self._validate_record(rec, "view", "undo_view"):
                stack.append(rec)
                self._update_buttons()
                return False
            try:
                if hasattr(owner, "audit_boundary_event"):
                    owner.audit_boundary_event(
                        "UNDO_CURRENT_PAGE_VIEW_POP",
                        page_idx=page_idx,
                        reason=str(rec.get("reason") or ""),
                        keys=",".join(sorted([str(k) for k in rec.keys()])),
                        remain=len(stack),
                        throttle_ms=80,
                    )
            except Exception:
                pass

            redo_rec = owner.make_view_history_record_for_state(rec, owner.capture_view_state())
            if not owner.restore_page_view_history_record(rec):
                stack.append(rec)
                self._update_buttons()
                return False

            owner.append_page_view_redo_record(redo_rec, page_idx=page_idx)
            self._log(f"↩️ {rec.get('reason', '화면 이동')} 되돌림")
            self._update_buttons()
            return True
        except Exception:
            self._update_buttons()
            return False

    def redo_view(self) -> bool:
        owner = self.owner
        if owner is None:
            return False
        try:
            owner.ensure_page_undo_state()
            page_idx = int(getattr(owner, "idx", 0) or 0)
            stack = self.manager.page_view_redo_stack(page_idx, create=True)
            if not stack:
                self._update_buttons()
                return False

            rec = stack.pop()
            if not self._validate_record(rec, "view", "redo_view"):
                stack.append(rec)
                self._update_buttons()
                return False
            undo_rec = owner.make_view_history_record_for_state(rec, owner.capture_view_state())
            if not owner.restore_page_view_history_record(rec):
                stack.append(rec)
                self._update_buttons()
                return False

            owner.append_page_view_undo_record(undo_rec, page_idx=page_idx, clear_redo=False)
            self._log(f"↷ {rec.get('reason', '화면 이동')} 재실행")
            self._update_buttons()
            return True
        except Exception:
            self._update_buttons()
            return False

    def undo_page(self) -> bool:
        owner = self.owner
        if owner is None:
            return False
        self._cancel_runtime()
        try:
            owner.ensure_page_undo_state()
            page_idx = int(getattr(owner, "idx", 0) or 0)
            stack = self.manager.page_undo_stack(page_idx, create=True)
            if not stack:
                self._update_buttons()
                return False

            rec = stack.pop()
            if not self._validate_record(rec, "page", "undo_page"):
                stack.append(rec)
                self._update_buttons()
                return False

            if owner.is_view_history_record(rec):
                redo_rec = owner.make_view_history_record_for_state(rec, owner.capture_view_state())
                if not owner.restore_page_view_history_record(rec):
                    stack.append(rec)
                    self._update_buttons()
                    return False
                owner.append_page_redo_record(redo_rec, page_idx=page_idx)
                self._log(f"↩️ {rec.get('reason', '화면 이동')} 되돌림")
                self._update_buttons()
                return True

            if rec.get("paint_history"):
                try:
                    paint_lengths = owner.undo_paint_stack_lengths(getattr(owner, "view", None))
                    if hasattr(owner, "audit_boundary_event"):
                        owner.audit_boundary_event(
                            "PAINT_UNDO_ATTEMPT",
                            reason=str(rec.get("reason") or "페인팅"),
                            viewer_history_len=paint_lengths.get("paint_undo", 0),
                            throttle_ms=100,
                        )
                except Exception:
                    pass

                try:
                    paint_stack = self.manager.paint_history_stack(getattr(owner, "view", None), create=True)
                except Exception:
                    paint_stack = getattr(getattr(owner, "view", None), "history", [])

                if paint_stack and getattr(owner, "view", None) is not None and owner.view.undo():
                    redo_rec = {
                        "reason": rec.get("reason", "페인팅"),
                        "page_idx": page_idx,
                        "mode": int(getattr(owner, "last_mode", 0) or 0),
                        "paint_history": True,
                        "_undo_scope": "page",
                    }
                    owner.append_page_redo_record(redo_rec, page_idx=page_idx)
                    try:
                        owner.undo_commit_paint_layer(
                            "mask" if int(getattr(owner, "last_mode", 0) or 0) in (2, 3) else "final_paint",
                            delay_ms=1200,
                        )
                    except Exception:
                        pass
                    self._update_buttons()
                    return True

                try:
                    if hasattr(owner, "audit_boundary_event"):
                        owner.audit_boundary_event("PAINT_UNDO_BLOCKED_NO_VIEW_HISTORY", reason=str(rec.get("reason") or "페인팅"), throttle_ms=100)
                except Exception:
                    pass
                stack.append(rec)
                self._update_buttons()
                return False

            redo_rec = owner.make_current_undo_record_like(rec)
            if not owner.restore_project_history_record(rec):
                self._update_buttons()
                return False
            if not redo_rec.get("redo_unavailable"):
                owner.append_page_redo_record(redo_rec, page_idx=page_idx)
            self._log(f"↩️ {rec.get('reason', '작업')} 되돌림")
            self._update_buttons()
            return True
        except Exception:
            self._update_buttons()
            return False

    def redo_page(self) -> bool:
        owner = self.owner
        if owner is None:
            return False
        self._cancel_runtime()
        try:
            owner.ensure_page_undo_state()
            page_idx = int(getattr(owner, "idx", 0) or 0)
            stack = self.manager.page_redo_stack(page_idx, create=True)
            if not stack:
                self._update_buttons()
                return False

            rec = stack.pop()
            if not self._validate_record(rec, "page", "redo_page"):
                stack.append(rec)
                self._update_buttons()
                return False

            if owner.is_view_history_record(rec):
                undo_rec = owner.make_view_history_record_for_state(rec, owner.capture_view_state())
                if not owner.restore_page_view_history_record(rec):
                    stack.append(rec)
                    self._update_buttons()
                    return False
                owner.append_page_undo_record(undo_rec, page_idx=page_idx, clear_redo=False)
                self._log(f"↷ {rec.get('reason', '화면 이동')} 재실행")
                self._update_buttons()
                return True

            if rec.get("paint_history"):
                try:
                    paint_redo_stack = self.manager.paint_redo_history_stack(getattr(owner, "view", None), create=True)
                except Exception:
                    paint_redo_stack = getattr(getattr(owner, "view", None), "redo_history", [])

                if paint_redo_stack and getattr(owner, "view", None) is not None and owner.view.redo():
                    undo_rec = {
                        "reason": rec.get("reason", "페인팅"),
                        "page_idx": page_idx,
                        "mode": int(getattr(owner, "last_mode", 0) or 0),
                        "paint_history": True,
                        "_undo_scope": "page",
                    }
                    owner.append_page_undo_record(undo_rec, page_idx=page_idx, clear_redo=False)
                    try:
                        owner.undo_commit_paint_layer(
                            "mask" if int(getattr(owner, "last_mode", 0) or 0) in (2, 3) else "final_paint",
                            delay_ms=1200,
                        )
                    except Exception:
                        pass
                    self._update_buttons()
                    return True

                stack.append(rec)
                self._update_buttons()
                return False

            if rec.get("redo_unavailable"):
                self._update_buttons()
                return False

            undo_rec = owner.make_current_undo_record_like(rec)
            if not owner.restore_project_history_record(rec):
                self._update_buttons()
                return False
            owner.append_page_undo_record(undo_rec, page_idx=page_idx, clear_redo=False)
            self._log(f"↷ {rec.get('reason', '작업')} 재실행")
            self._update_buttons()
            return True
        except Exception:
            self._update_buttons()
            return False

    def undo_project(self) -> bool:
        owner = self.owner
        if owner is None:
            return False
        self._cancel_runtime()
        try:
            stack = self.manager.project_undo_stack_ref(create=True)
            if not stack:
                self._update_buttons()
                return False

            rec = stack.pop()
            if not self._validate_record(rec, "project", "undo_project"):
                stack.append(rec)
                self._update_buttons()
                return False
            redo_rec = owner.make_current_undo_record_like(rec)
            if not owner.restore_project_history_record(rec):
                self._update_buttons()
                return False

            owner.append_project_redo_record(redo_rec)
            self._log(f"↩️ {rec.get('reason', '작업')} 되돌림")
            self._update_buttons()
            return True
        except Exception:
            self._update_buttons()
            return False

    def redo_project(self) -> bool:
        owner = self.owner
        if owner is None:
            return False
        self._cancel_runtime()
        try:
            stack = self.manager.project_redo_stack_ref(create=True)
            if not stack:
                self._update_buttons()
                return False

            rec = stack.pop()
            if not self._validate_record(rec, "project", "redo_project"):
                stack.append(rec)
                self._update_buttons()
                return False
            undo_rec = owner.make_current_undo_record_like(rec)
            if not owner.restore_project_history_record(rec):
                self._update_buttons()
                return False

            owner.append_project_undo_record(undo_rec, clear_redo=False)
            self._log(f"↷ {rec.get('reason', '작업')} 재실행")
            self._update_buttons()
            return True
        except Exception:
            self._update_buttons()
            return False

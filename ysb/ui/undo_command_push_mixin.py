from ysb.ui.main_window_support import *


class UndoCommandPushMixin:

    def _text_data_list_for_page(self, page_idx=None):
        try:
            target_page = int(getattr(self, "idx", 0) if page_idx is None else page_idx)
        except Exception:
            target_page = int(getattr(self, "idx", 0) or 0)
        try:
            curr = self.data.get(target_page) or {}
            data_list = curr.get('data', []) if isinstance(curr, dict) else []
            return target_page, data_list if isinstance(data_list, list) else []
        except Exception:
            return target_page, []

    def _text_data_items_by_id(self, page_idx=None):
        page_idx, data_list = self._text_data_list_for_page(page_idx)
        out = {}
        try:
            for item in data_list or []:
                if isinstance(item, dict) and item.get('id') is not None:
                    out[str(item.get('id'))] = item
        except Exception:
            pass
        return page_idx, out

    def _snapshot_text_style_values(self, items=None, fields=None, page_idx=None, ids=None):
        """Capture only the selected text fields before a style burst changes data."""
        fields = [str(x) for x in (fields or []) if x]
        page_idx, by_id = self._text_data_items_by_id(page_idx)
        result = {}
        wanted_ids = [str(x) for x in (ids or []) if x is not None]
        if not wanted_ids:
            for item in list(items or []):
                try:
                    sid = getattr(item, "data", {}).get("id")
                    if sid is not None:
                        wanted_ids.append(str(sid))
                except Exception:
                    pass
        for sid in wanted_ids:
            source = by_id.get(str(sid))
            if source is None:
                for item in list(items or []):
                    try:
                        data = getattr(item, "data", {})
                        if str(data.get("id")) == str(sid):
                            source = data
                            break
                    except Exception:
                        pass
            if not isinstance(source, dict):
                continue
            result[str(sid)] = {}
            for field_name in fields:
                exists = field_name in source
                try:
                    value = copy.deepcopy(source.get(field_name))
                except Exception:
                    value = source.get(field_name)
                result[str(sid)][field_name] = {"exists": bool(exists), "value": value}
        return result

    def _make_text_style_command_from_session(self, session):
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return None
        if not isinstance(session, dict):
            return None
        try:
            page_idx = int(session.get("page_idx", getattr(self, "idx", 0) or 0))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        fields = [str(x) for x in sorted(session.get("fields") or []) if x]
        ids = [str(x) for x in (session.get("ids") or []) if x is not None]
        before_values = session.get("before_values") or {}
        if not fields or not ids or not isinstance(before_values, dict):
            return None
        _, by_id = self._text_data_items_by_id(page_idx)
        changes = []
        for sid in ids:
            target = by_id.get(str(sid))
            if not isinstance(target, dict):
                continue
            target_before = before_values.get(str(sid)) or {}
            for field_name in fields:
                before_info = target_before.get(field_name, {"exists": False, "value": None})
                before_exists = bool(before_info.get("exists"))
                before_value = before_info.get("value")
                after_exists = field_name in target
                try:
                    after_value = copy.deepcopy(target.get(field_name))
                except Exception:
                    after_value = target.get(field_name)
                changed = (before_exists != bool(after_exists))
                if not changed:
                    try:
                        changed = before_value != after_value
                    except Exception:
                        changed = True
                if not changed:
                    continue
                changes.append(FieldChange(
                    target_id=str(sid),
                    field=str(field_name),
                    before=before_value,
                    after=after_value,
                    component_type="text_style",
                    page_idx=page_idx,
                    meta={
                        "before_missing": not before_exists,
                        "after_missing": not bool(after_exists),
                    },
                ))
        if not changes:
            return None
        return UndoCommand(
            reason=str(session.get("reason") or "텍스트 스타일 변경"),
            page_idx=page_idx,
            component_type="text_style",
            target_ids=ids,
            changes=changes,
            merge_key=str(session.get("merge_key") or "text_style:" + ":".join(ids)),
            meta={"stage": "undo_command_diff_stage2", "fields": fields},
        )

    def flush_pending_live_text_style_undo_session(self):
        """Force-close a pending style burst before Undo/Redo or selection/page changes."""
        try:
            timer = getattr(self, "_live_text_style_timer", None)
            if timer is not None:
                timer.stop()
        except Exception:
            pass
        return self._finish_live_text_style_session()

    def _finish_live_text_style_session(self):
        """Close the current style burst and push one Command/Diff undo record."""
        session = getattr(self, "_live_text_style_session", None)
        if not isinstance(session, dict):
            self._live_text_style_session = None
            return False
        # Never close/push a style burst while a live text item is being dragged.
        # The timer can fire ~900ms after a color/font change, exactly while the
        # user has already started moving that item.  Pushing undo then clears redo
        # and may run audit/dirty callbacks while Qt still owns mouse grab state.
        if getattr(self, "_text_item_drag_active", False) or getattr(self, "_text_scene_mutation_lock", False):
            try:
                timer = getattr(self, "_live_text_style_timer", None)
                if timer is not None:
                    timer.start(260)
            except Exception:
                pass
            try:
                self.audit_boundary_event(
                    "UNDO_TEXT_STYLE_COMMAND_DEFERRED_DURING_TEXT_DRAG",
                    page_idx=session.get("page_idx", getattr(self, "idx", 0)),
                    selected_count=len(session.get("ids") or []),
                    text_drag=bool(getattr(self, "_text_item_drag_active", False)),
                    scene_mutation=bool(getattr(self, "_text_scene_mutation_lock", False)),
                    throttle_ms=120,
                )
            except Exception:
                pass
            return False
        self._live_text_style_session = None
        try:
            fields = sorted(session.get("fields") or [])
            ids = list(session.get("ids") or [])
            page_idx = int(session.get("page_idx", getattr(self, "idx", 0) or 0))
            if fields:
                try:
                    if hasattr(self, "text_engine") and self.text_engine is not None:
                        self.text_engine.mark_dirty(page_idx, ids, fields)
                except Exception:
                    pass
            command = self._make_text_style_command_from_session(session)
            if command is None:
                try:
                    self.audit_boundary_event("UNDO_TEXT_STYLE_COMMAND_SKIP_NOOP", page_idx=page_idx, selected_count=len(ids), fields=",".join(fields), throttle_ms=120)
                except Exception:
                    pass
                return False
            mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
            if mgr is not None and hasattr(mgr, "push_command"):
                ok = bool(mgr.push_command(command, clear_redo=True, source="text_style_burst"))
                try:
                    self.audit_boundary_event("UNDO_TEXT_STYLE_COMMAND_PUSH", page_idx=page_idx, selected_count=len(ids), change_count=command.change_count, fields=",".join(fields), ok=bool(ok), throttle_ms=80)
                except Exception:
                    pass
                return ok
        except Exception as e:
            try:
                self.audit_boundary_event("UNDO_TEXT_STYLE_COMMAND_FINISH_ERROR", error=repr(e), throttle_ms=120)
            except Exception:
                pass
        return False

    def _ensure_live_text_style_undo(self, items, fields=None, reason="텍스트 스타일 변경"):
        """Start or extend one Command/Diff undo session per continuous style burst."""
        if (
            getattr(self, "_text_undo_restore_lock", False)
            or getattr(self, "_project_undo_restore_lock", False)
            or getattr(self, "_command_undo_restore_lock", False)
        ):
            return False
        items = list(items or [])
        if not items:
            return False
        fields = [str(x) for x in (fields or []) if x]
        if not fields:
            return False
        key = self._live_text_style_selected_key(items)
        selected_ids = [getattr(item, "data", {}).get("id") for item in items if getattr(item, "data", {}).get("id") is not None]
        page_idx = key[0]

        session = getattr(self, "_live_text_style_session", None)
        if isinstance(session, dict) and session.get("key") != key:
            self.flush_pending_live_text_style_undo_session()
            session = None

        if not isinstance(session, dict):
            try:
                old_timer = getattr(self, "_live_text_style_timer", None)
                if old_timer is not None:
                    old_timer.stop()
            except Exception:
                pass
            session = {
                "key": key,
                "page_idx": page_idx,
                "ids": list(selected_ids),
                "fields": set(fields),
                "reason": str(reason or "텍스트 스타일 변경"),
                "merge_key": "text_style:" + str(page_idx) + ":" + ":".join([str(x) for x in sorted(selected_ids)]),
                "before_values": self._snapshot_text_style_values(items, fields, page_idx=page_idx, ids=selected_ids),
            }
            self._live_text_style_session = session
        else:
            try:
                old_fields = set(session.setdefault("fields", set()))
                new_fields = set(fields) - old_fields
                if new_fields:
                    before = session.setdefault("before_values", {})
                    snap = self._snapshot_text_style_values(items, new_fields, page_idx=page_idx, ids=selected_ids)
                    for sid, field_map in (snap or {}).items():
                        before.setdefault(str(sid), {}).update(field_map or {})
                    session.setdefault("fields", set()).update(new_fields)
            except Exception:
                pass

        try:
            timer = getattr(self, "_live_text_style_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._finish_live_text_style_session)
                self._live_text_style_timer = timer
            timer.start(900)
        except Exception:
            pass
        return True

    def _snapshot_text_field_values(self, data_item=None, fields=None):
        """Capture generic text data fields for Command/Diff undo records."""
        result = {}
        if not isinstance(data_item, dict):
            return result
        for field_name in [str(x) for x in (fields or []) if x]:
            exists = field_name in data_item
            try:
                value = copy.deepcopy(data_item.get(field_name))
            except Exception:
                value = data_item.get(field_name)
            result[field_name] = {"exists": bool(exists), "value": value}
        return result

    def push_text_geometry_command(self, data_item=None, before_values=None, after_values=None, *, reason="텍스트 이동", fields=None, page_idx=None, component_type="text_geometry", force_record=False, command_meta=None):
        """Push one field-level command for text position/geometry/transform changes.

        Stage 3 uses this for drag-move x_off/y_off and transform-move rect
        changes. Stage 4 reuses the same safe diff builder for rotation,
        char_width/char_height, skew, trapezoid, and arc transform fields.
        It is intentionally generic so later migrations can reuse it without
        taking a whole page/text snapshot.
        """
        if (
            getattr(self, "_text_undo_restore_lock", False)
            or getattr(self, "_project_undo_restore_lock", False)
            or getattr(self, "_command_undo_restore_lock", False)
        ):
            return False
        if not isinstance(data_item, dict):
            return False
        sid = data_item.get('id')
        if sid is None:
            return False
        try:
            target_page = int(getattr(self, "idx", 0) if page_idx is None else page_idx)
        except Exception:
            target_page = int(getattr(self, "idx", 0) or 0)
        field_names = [str(x) for x in (fields or []) if x]
        if not field_names:
            field_names = sorted(set((before_values or {}).keys()) | set((after_values or {}).keys()))
        if not field_names:
            return False
        before_values = before_values if isinstance(before_values, dict) else {}
        after_values = after_values if isinstance(after_values, dict) else self._snapshot_text_field_values(data_item, field_names)
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return False
        changes = []
        for field_name in field_names:
            before_info = before_values.get(field_name, {"exists": field_name in data_item, "value": data_item.get(field_name)})
            after_info = after_values.get(field_name, {"exists": field_name in data_item, "value": data_item.get(field_name)})
            before_exists = bool(before_info.get("exists"))
            after_exists = bool(after_info.get("exists"))
            before_value = before_info.get("value")
            after_value = after_info.get("value")
            changed = before_exists != after_exists
            if not changed:
                try:
                    changed = before_value != after_value
                except Exception:
                    changed = True
            if not changed:
                continue
            changes.append(FieldChange(
                target_id=str(sid),
                field=str(field_name),
                before=before_value,
                after=after_value,
                component_type=str(component_type or "text_geometry"),
                page_idx=target_page,
                meta={
                    "before_missing": not before_exists,
                    "after_missing": not after_exists,
                },
            ))
        meta = {"stage": "undo_command_diff_stage3", "fields": field_names}
        if isinstance(command_meta, dict):
            try:
                meta.update(copy.deepcopy(command_meta))
            except Exception:
                meta.update(command_meta)
        if force_record:
            meta["force_record"] = True
        if not changes and not force_record:
            try:
                self.audit_boundary_event(
                    "UNDO_TEXT_GEOMETRY_COMMAND_SKIP_NO_CHANGE",
                    page_idx=target_page,
                    target_id=str(sid),
                    reason=str(reason or ""),
                    component_type=str(component_type or "text_geometry"),
                    fields=",".join(field_names),
                    before_values=str(before_values)[:500],
                    after_values=str(after_values)[:500],
                    throttle_ms=80,
                )
            except Exception:
                pass
            return False
        command = UndoCommand(
            reason=str(reason or "텍스트 이동"),
            page_idx=target_page,
            component_type=str(component_type or "text_geometry"),
            target_ids=[str(sid)],
            changes=changes,
            merge_key=f"{component_type}:{target_page}:{sid}:{reason}",
            meta=meta,
        )
        mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
        if mgr is not None and hasattr(mgr, "push_command"):
            ok = bool(mgr.push_command(command, clear_redo=True, source=str(reason or "text_geometry")))
            try:
                self.audit_boundary_event(
                    "UNDO_TEXT_GEOMETRY_COMMAND_PUSH",
                    page_idx=target_page,
                    target_id=str(sid),
                    reason=str(reason or ""),
                    component_type=str(component_type or "text_geometry"),
                    change_count=command.change_count,
                    fields=",".join(field_names),
                    change_summary=command.change_summary(),
                    force_record=bool(force_record),
                    marker=str((meta or {}).get("marker") or ""),
                    ok=bool(ok),
                    throttle_ms=80,
                )
            except Exception:
                pass
            return ok
        return False

    def push_text_transform_command(self, data_item=None, before_values=None, after_values=None, *, reason="텍스트 변형", fields=None, page_idx=None):
        """Push Command/Diff undo for text transform fields.

        This is a thin semantic wrapper over push_text_geometry_command so the
        timeline can distinguish path-affecting transforms from pure position
        changes while keeping one diff-building implementation.
        """
        return self.push_text_geometry_command(
            data_item,
            before_values=before_values,
            after_values=after_values,
            reason=reason or "텍스트 변형",
            fields=fields,
            page_idx=page_idx,
            component_type="text_transform",
        )

    def _summarize_text_item_geometry_for_log(self, item):
        """Compact geometry summary for text lifecycle command logs."""
        if not isinstance(item, dict):
            return ""
        try:
            return (
                f"id={item.get('id')} "
                f"rect={item.get('rect')} "
                f"x_off={item.get('x_off')} "
                f"y_off={item.get('y_off')} "
                f"manual={item.get('manual_text_rect')} "
                f"anchor={item.get('text_anchor_mode')}"
            )[:500]
        except Exception:
            return ""

    def push_text_item_lifecycle_command(self, data_item=None, *, before_item=None, after_item=None, before_exists=True, after_exists=True, before_index=None, after_index=None, reason="텍스트 항목 변경", page_idx=None):
        """Push a Command/Diff record for adding/removing one text data item.

        Direct text creation changes the page data list itself, so it cannot be
        represented safely as only translated_text/rect field diffs.  This
        runtime command stores the whole affected text item for undo/redo while
        still staying in the canonical single timeline.
        """
        if (
            getattr(self, "_text_undo_restore_lock", False)
            or getattr(self, "_project_undo_restore_lock", False)
            or getattr(self, "_command_undo_restore_lock", False)
        ):
            return False
        item_src = data_item if isinstance(data_item, dict) else (after_item if isinstance(after_item, dict) else before_item)
        if not isinstance(item_src, dict):
            return False
        sid = item_src.get('id')
        if sid is None:
            return False
        try:
            target_page = int(getattr(self, "idx", 0) if page_idx is None else page_idx)
        except Exception:
            target_page = int(getattr(self, "idx", 0) or 0)
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return False
        try:
            before_value = copy.deepcopy(before_item) if before_exists and before_item is not None else None
        except Exception:
            before_value = before_item if before_exists else None
        try:
            after_value = copy.deepcopy(after_item) if after_exists and after_item is not None else None
        except Exception:
            after_value = after_item if after_exists else None
        change = FieldChange(
            target_id=str(sid),
            field="__text_item__",
            before=before_value,
            after=after_value,
            component_type="text_item_lifecycle",
            page_idx=target_page,
            meta={
                "before_missing": not bool(before_exists),
                "after_missing": not bool(after_exists),
                "before_index": before_index,
                "after_index": after_index,
            },
        )
        command = UndoCommand(
            reason=str(reason or "텍스트 항목 변경"),
            page_idx=target_page,
            component_type="text_item_lifecycle",
            target_ids=[str(sid)],
            changes=[change],
            merge_key=f"text_item_lifecycle:{target_page}:{sid}:{reason}",
            meta={"stage": "undo_command_diff_stage11_text_edit_fix"},
        )
        mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
        if mgr is not None and hasattr(mgr, "push_command"):
            ok = bool(mgr.push_command(command, clear_redo=True, source=str(reason or "text_item_lifecycle")))
            try:
                self.audit_boundary_event(
                    "UNDO_TEXT_ITEM_LIFECYCLE_COMMAND_PUSH",
                    page_idx=target_page,
                    target_id=str(sid),
                    reason=str(reason or ""),
                    command_id=str(getattr(command, "command_id", "") or ""),
                    change_summary=(command.change_summary(value_limit=120) if hasattr(command, "change_summary") else ""),
                    before_exists=bool(before_exists),
                    after_exists=bool(after_exists),
                    before_index=before_index,
                    after_index=after_index,
                    before_geometry=self._summarize_text_item_geometry_for_log(before_value),
                    after_geometry=self._summarize_text_item_geometry_for_log(after_value),
                    ok=bool(ok),
                    throttle_ms=80,
                )
            except Exception:
                pass
            return ok
        return False

    def _view_state_changes_for_command(self, before_state=None, after_state=None, *, page_idx=None, mode=None, component_type="view_state"):
        """Build FieldChange list for page-local view transform/scroll state.

        Stage 5 treats zoom/pan as a UI/View component.  The command stores only
        JSON-safe view fields, not page/text snapshots.
        """
        try:
            from ysb.core.command_undo import FieldChange
        except Exception:
            return []
        before_state = copy.deepcopy(before_state or {}) if isinstance(before_state, dict) else {}
        after_state = copy.deepcopy(after_state or {}) if isinstance(after_state, dict) else {}
        try:
            target_page = int(getattr(self, "idx", 0) if page_idx is None else page_idx)
        except Exception:
            target_page = int(getattr(self, "idx", 0) or 0)
        try:
            mode_idx = int(self.current_mode_index_safe() if mode is None else mode)
        except Exception:
            mode_idx = int(getattr(self, "last_mode", 0) or 0)
        target_id = f"view:{target_page}:{mode_idx}"
        changes = []
        for field_name in ("transform", "h_scroll", "v_scroll"):
            before_exists = field_name in before_state
            after_exists = field_name in after_state
            before_value = copy.deepcopy(before_state.get(field_name))
            after_value = copy.deepcopy(after_state.get(field_name))
            changed = before_exists != after_exists
            if not changed:
                try:
                    changed = before_value != after_value
                except Exception:
                    changed = True
            if not changed:
                continue
            changes.append(FieldChange(
                target_id=target_id,
                field=field_name,
                before=before_value,
                after=after_value,
                component_type=str(component_type or "view_state"),
                page_idx=target_page,
                meta={
                    "mode": mode_idx,
                    "before_missing": not before_exists,
                    "after_missing": not after_exists,
                },
            ))
        return changes

    def push_view_state_command_from_record(self, rec=None, page_idx=None):
        """Push zoom/pan/view-state history as a Command-Diff entry.

        Replaces the legacy page_view stack path for Stage 5.  The old restore
        path remains as fallback for older records.
        """
        if (
            getattr(self, "_project_undo_restore_lock", False)
            or getattr(self, "_command_undo_restore_lock", False)
            or getattr(self, "is_loading_project", False)
            or getattr(self, "is_page_loading", False)
        ):
            return False
        if not isinstance(rec, dict):
            return False
        try:
            target_page = int(page_idx if page_idx is not None else rec.get("page_idx", getattr(self, "idx", 0)))
        except Exception:
            target_page = int(getattr(self, "idx", 0) or 0)
        try:
            mode_idx = int(rec.get("mode", self.current_mode_index_safe()))
        except Exception:
            mode_idx = int(getattr(self, "last_mode", 0) or 0)
        before_state = copy.deepcopy(rec.get("view_state") or {})
        after_state = copy.deepcopy(rec.get("view_new_state") or {})
        if not before_state or not after_state:
            return False
        changes = self._view_state_changes_for_command(before_state, after_state, page_idx=target_page, mode=mode_idx, component_type="view_state")
        if not changes:
            return False
        try:
            from ysb.core.command_undo import UndoCommand
        except Exception:
            return False
        reason = str(rec.get("reason") or "화면 이동")
        command = UndoCommand(
            reason=reason,
            page_idx=target_page,
            component_type="view_state",
            target_ids=[f"view:{target_page}:{mode_idx}"],
            changes=changes,
            merge_key=f"view_state:{target_page}:{mode_idx}:{reason}",
            meta={
                "stage": "undo_command_diff_stage5",
                "mode": mode_idx,
                "before_state": before_state,
                "after_state": after_state,
            },
        )
        mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
        if mgr is not None and hasattr(mgr, "push_command"):
            ok = bool(mgr.push_command(command, clear_redo=True, source=str(reason or "view_state")))
            try:
                self.audit_boundary_event(
                    "UNDO_VIEW_STATE_COMMAND_PUSH",
                    page_idx=target_page,
                    mode=mode_idx,
                    reason=reason,
                    change_count=command.change_count,
                    ok=bool(ok),
                    throttle_ms=80,
                )
            except Exception:
                pass
            return ok
        return False

    def push_work_tab_command_from_record(self, rec=None, page_idx=None):
        """Push work-tab changes as one UI/View Command-Diff entry."""
        if (
            getattr(self, "_project_undo_restore_lock", False)
            or getattr(self, "_command_undo_restore_lock", False)
            or getattr(self, "is_loading_project", False)
            or getattr(self, "is_page_loading", False)
            or getattr(self, "is_batch_running", False)
        ):
            return False
        if not isinstance(rec, dict):
            return False
        try:
            old_mode = int(rec.get("mode", getattr(self, "last_mode", 0)) or 0)
            new_mode = int(rec.get("new_mode", self.current_mode_index_safe()) or 0)
        except Exception:
            return False
        if old_mode == new_mode:
            return False
        try:
            target_page = int(page_idx if page_idx is not None else rec.get("page_idx", getattr(self, "idx", 0)))
        except Exception:
            target_page = int(getattr(self, "idx", 0) or 0)
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return False
        before_view_state = copy.deepcopy(rec.get("view_state") or {})
        command = UndoCommand(
            reason=str(rec.get("reason") or "작업 탭 변경"),
            page_idx=target_page,
            component_type="work_tab",
            target_ids=["work_tab"],
            changes=[FieldChange(
                target_id="work_tab",
                field="current_index",
                before=old_mode,
                after=new_mode,
                component_type="work_tab",
                page_idx=target_page,
                meta={"before_view_state": before_view_state},
            )],
            merge_key=f"work_tab:{target_page}:{old_mode}->{new_mode}",
            meta={
                "stage": "undo_command_diff_stage5",
                "old_mode": old_mode,
                "new_mode": new_mode,
                "before_view_state": before_view_state,
            },
        )
        mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
        if mgr is not None and hasattr(mgr, "push_command"):
            ok = bool(mgr.push_command(command, clear_redo=True, source="work_tab_change"))
            try:
                self.audit_boundary_event(
                    "UNDO_WORK_TAB_COMMAND_PUSH",
                    page_idx=target_page,
                    old_mode=old_mode,
                    new_mode=new_mode,
                    ok=bool(ok),
                    throttle_ms=80,
                )
            except Exception:
                pass
            return ok
        return False

    def _normalize_page_index_list_for_command(self, page_indices=None):
        """Normalize page index lists for region/page-data commands."""
        out = []
        seen = set()
        raw_values = page_indices if page_indices is not None else []
        for raw in raw_values or []:
            try:
                i = int(raw)
            except Exception:
                continue
            try:
                max_len = len(getattr(self, "paths", []) or [])
            except Exception:
                max_len = 0
            if max_len and not (0 <= i < max_len):
                continue
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    def push_ocr_analysis_region_command(self, before_by_page=None, after_by_page=None, *, reason="OCR 분석 범위 지정", page_indices=None):
        """Push OCR analysis-region list changes as one Command/Diff entry.

        Stage 6 treats the saved OCR analysis regions as a page data component.
        Each affected page stores one field diff for ``ocr_analysis_regions``.
        Temporary drawing undo remains local to the selection tool; this command
        is only for committed save/clear changes.
        """
        if (
            getattr(self, "_project_undo_restore_lock", False)
            or getattr(self, "_command_undo_restore_lock", False)
            or getattr(self, "is_loading_project", False)
            or getattr(self, "is_page_loading", False)
            or getattr(self, "is_batch_running", False)
        ):
            return False
        if not isinstance(before_by_page, dict):
            before_by_page = {}
        if not isinstance(after_by_page, dict):
            after_by_page = {}
        pages = set()
        for src in (before_by_page, after_by_page):
            for raw in src.keys():
                try:
                    pages.add(int(raw))
                except Exception:
                    continue
        for i in self._normalize_page_index_list_for_command(page_indices):
            pages.add(int(i))
        if not pages:
            try:
                pages.add(int(getattr(self, "idx", 0) or 0))
            except Exception:
                pages.add(0)
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return False
        changes = []
        target_ids = []
        for page_idx in sorted(pages):
            curr = self.data.get(page_idx) if hasattr(self, "data") else None
            if not isinstance(curr, dict):
                continue
            before_exists = page_idx in before_by_page or str(page_idx) in before_by_page
            after_exists = page_idx in after_by_page or str(page_idx) in after_by_page
            before_value = copy.deepcopy(before_by_page.get(page_idx, before_by_page.get(str(page_idx), curr.get('ocr_analysis_regions', []) or [])))
            after_value = copy.deepcopy(after_by_page.get(page_idx, after_by_page.get(str(page_idx), curr.get('ocr_analysis_regions', []) or [])))
            changed = before_exists != after_exists
            if not changed:
                try:
                    changed = before_value != after_value
                except Exception:
                    changed = True
            if not changed:
                continue
            target_id = f"ocr_analysis_regions:{page_idx}"
            target_ids.append(target_id)
            changes.append(FieldChange(
                target_id=target_id,
                field="ocr_analysis_regions",
                before=before_value,
                after=after_value,
                component_type="ocr_analysis_regions",
                page_idx=page_idx,
                meta={
                    "target_page_idx": page_idx,
                    "before_missing": not before_exists,
                    "after_missing": not after_exists,
                },
            ))
        if not changes:
            return False
        try:
            owner_page = int(getattr(self, "idx", 0) or 0)
        except Exception:
            owner_page = 0
        command = UndoCommand(
            reason=str(reason or "OCR 분석 범위 지정"),
            page_idx=owner_page,
            component_type="ocr_analysis_regions",
            target_ids=target_ids,
            changes=changes,
            merge_key=f"ocr_analysis_regions:{','.join(str(x) for x in sorted(pages))}:{reason}",
            meta={"stage": "undo_command_diff_stage6", "page_indices": sorted(pages)},
        )
        mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
        if mgr is not None and hasattr(mgr, "push_command"):
            ok = bool(mgr.push_command(command, clear_redo=True, source=str(reason or "ocr_analysis_regions")))
            try:
                self.audit_boundary_event(
                    "UNDO_OCR_REGION_COMMAND_PUSH",
                    page_idx=owner_page,
                    affected=','.join(str(x) for x in sorted(pages)),
                    change_count=command.change_count,
                    reason=str(reason or ""),
                    ok=bool(ok),
                    throttle_ms=80,
                )
            except Exception:
                pass
            return ok
        return False

    def push_text_region_reset_command(self, items=None, before_by_id=None, after_by_id=None, *, reason="현재 텍스트 기준 영역 재설정", page_idx=None):
        """Push text-area reset changes as one Command/Diff entry.

        This covers rect/x_off/y_off/manual_text_rect/text_anchor_mode changes
        made by reset_text_rects_current().  It intentionally uses a separate
        component_type from drag-move geometry because applying it must rerender
        the affected text items/guide boxes, not merely call setPos().
        """
        if (
            getattr(self, "_text_undo_restore_lock", False)
            or getattr(self, "_project_undo_restore_lock", False)
            or getattr(self, "_command_undo_restore_lock", False)
        ):
            return False
        items = [d for d in (items or []) if isinstance(d, dict) and d.get('id') is not None]
        if not items:
            return False
        before_by_id = before_by_id if isinstance(before_by_id, dict) else {}
        after_by_id = after_by_id if isinstance(after_by_id, dict) else {}
        fields = ['rect', 'x_off', 'y_off', 'manual_text_rect', 'text_anchor_mode']
        try:
            target_page = int(getattr(self, "idx", 0) if page_idx is None else page_idx)
        except Exception:
            target_page = int(getattr(self, "idx", 0) or 0)
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return False
        changes = []
        target_ids = []
        for data_item in items:
            sid = str(data_item.get('id'))
            target_ids.append(sid)
            before_map = before_by_id.get(sid, before_by_id.get(data_item.get('id'), {})) or {}
            after_map = after_by_id.get(sid, after_by_id.get(data_item.get('id'), {})) or self._snapshot_text_field_values(data_item, fields)
            for field_name in fields:
                before_info = before_map.get(field_name, {"exists": field_name in data_item, "value": data_item.get(field_name)})
                after_info = after_map.get(field_name, {"exists": field_name in data_item, "value": data_item.get(field_name)})
                before_exists = bool(before_info.get("exists"))
                after_exists = bool(after_info.get("exists"))
                before_value = before_info.get("value")
                after_value = after_info.get("value")
                changed = before_exists != after_exists
                if not changed:
                    try:
                        changed = before_value != after_value
                    except Exception:
                        changed = True
                if not changed:
                    continue
                changes.append(FieldChange(
                    target_id=sid,
                    field=field_name,
                    before=before_value,
                    after=after_value,
                    component_type="text_region_reset",
                    page_idx=target_page,
                    meta={
                        "before_missing": not before_exists,
                        "after_missing": not after_exists,
                    },
                ))
        if not changes:
            return False
        command = UndoCommand(
            reason=str(reason or "현재 텍스트 기준 영역 재설정"),
            page_idx=target_page,
            component_type="text_region_reset",
            target_ids=target_ids,
            changes=changes,
            merge_key=f"text_region_reset:{target_page}:{len(target_ids)}",
            meta={"stage": "undo_command_diff_stage6", "fields": fields},
        )
        mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
        if mgr is not None and hasattr(mgr, "push_command"):
            ok = bool(mgr.push_command(command, clear_redo=True, source=str(reason or "text_region_reset")))
            try:
                self.audit_boundary_event(
                    "UNDO_TEXT_REGION_RESET_COMMAND_PUSH",
                    page_idx=target_page,
                    selected_count=len(target_ids),
                    change_count=command.change_count,
                    ok=bool(ok),
                    throttle_ms=80,
                )
            except Exception:
                pass
            return ok
        return False

    def _snapshot_project_structure_state(self, reason="프로젝트 구조 변경"):
        """Capture the runtime project/page structure for Command-Diff undo.

        Stage 8 keeps save formats unchanged.  This snapshot is runtime-only and
        is used for page add/delete/reorder commands that cannot be represented
        as a tiny scalar field diff.  It deliberately stores structure state in
        one command so these actions no longer need the legacy project stack.
        """
        try:
            paths = [str(p) for p in (getattr(self, "paths", []) or [])]
        except Exception:
            paths = []
        data = {}
        try:
            source_data = getattr(self, "data", {}) or {}
            for k, v in source_data.items():
                try:
                    kk = int(k)
                except Exception:
                    kk = k
                if isinstance(v, dict):
                    try:
                        data[kk] = self.copy_undo_page_data(v)
                    except Exception:
                        data[kk] = copy.deepcopy(v)
                else:
                    data[kk] = copy.deepcopy(v)
        except Exception:
            data = copy.deepcopy(getattr(self, "data", {}) or {})
        try:
            view_states = copy.deepcopy(getattr(self, "project_ui_view_states", {}) or {})
        except Exception:
            view_states = {}
        try:
            idx = int(getattr(self, "idx", 0) or 0)
        except Exception:
            idx = 0
        try:
            mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else int(getattr(self, "last_mode", 0) or 0)
        except Exception:
            mode = int(getattr(self, "last_mode", 0) or 0)
        return {
            "paths": paths,
            "data": data,
            "project_ui_view_states": view_states,
            "idx": idx,
            "mode": mode,
            "reason": str(reason or "프로젝트 구조 변경"),
        }

    def push_project_structure_command(self, before_state=None, after_state=None, *, reason="프로젝트 구조 변경", action="structure"):
        """Push page add/delete/reorder as one project_structure command.

        This is the Stage 8 migration target for large structure operations.
        It still captures a full structure state because page list changes move
        indices and page-owned data together, but it is now owned by the single
        command timeline instead of the project legacy stack.
        """
        if (
            getattr(self, "_project_undo_restore_lock", False)
            or getattr(self, "_command_undo_restore_lock", False)
            or getattr(self, "macro_running", False)
            or getattr(self, "_suppress_project_undo", False)
        ):
            return False
        if not isinstance(before_state, dict) or not isinstance(after_state, dict):
            return False
        try:
            if before_state == after_state:
                return False
        except Exception:
            pass
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return False
        try:
            page_idx = int(after_state.get("idx", getattr(self, "idx", 0)) or 0)
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        command = UndoCommand(
            reason=str(reason or "프로젝트 구조 변경"),
            page_idx=page_idx,
            component_type="project_structure",
            target_ids=["project"],
            changes=[FieldChange(
                target_id="project",
                field=str(action or "structure_state"),
                before=before_state,
                after=after_state,
                component_type="project_structure",
                page_idx=page_idx,
                meta={
                    "action": str(action or "structure"),
                    "before_count": len(before_state.get("paths") or []),
                    "after_count": len(after_state.get("paths") or []),
                    "stage": "undo_command_diff_stage8",
                },
            )],
            merge_key=f"project_structure:{action}:{page_idx}:{reason}",
            meta={
                "action": str(action or "structure"),
                "before_count": len(before_state.get("paths") or []),
                "after_count": len(after_state.get("paths") or []),
                "stage": "undo_command_diff_stage8",
            },
        )
        mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
        if mgr is not None and hasattr(mgr, "push_command"):
            ok = bool(mgr.push_command(command, clear_redo=True, source="project_structure"))
            try:
                self.audit_boundary_event(
                    "UNDO_PROJECT_STRUCTURE_COMMAND_PUSH",
                    page_idx=page_idx,
                    reason=str(reason or ""),
                    action=str(action or ""),
                    before_count=len(before_state.get("paths") or []),
                    after_count=len(after_state.get("paths") or []),
                    ok=bool(ok),
                    throttle_ms=100,
                )
            except Exception:
                pass
            return ok
        return False

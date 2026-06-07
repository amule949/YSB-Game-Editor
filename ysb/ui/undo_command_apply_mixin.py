from ysb.ui.main_window_support import *


class UndoCommandApplyMixin:

    def _scene_text_items_by_id(self):
        out = {}
        scene = self._safe_graphics_scene()
        if scene is None:
            return out
        try:
            for item in scene.items():
                if isinstance(item, TypesettingItem):
                    sid = getattr(item, "data", {}).get("id")
                    if sid is not None:
                        out[str(sid)] = item
        except RuntimeError:
            return {}
        except Exception:
            return out
        return out

    def _remove_inline_text_editor_from_scene(self):
        """Best-effort cleanup for temporary inline editor artifacts before text layer rebuild."""
        editor = getattr(self, "inline_text_editor", None)
        if editor is None:
            return
        try:
            editor._closing = True
        except Exception:
            pass
        try:
            sc = editor.scene()
            if sc is not None:
                sc.removeItem(editor)
        except Exception:
            pass
        try:
            self.inline_text_editor = None
            self.inline_text_target = None
        except Exception:
            pass

    def _remove_all_live_text_scene_items(self):
        """Remove every live TypesettingItem, even if an older item lost its layer tag."""
        scene = self._safe_graphics_scene()
        if scene is None:
            return 0
        removed = 0
        old_block = None
        try:
            old_block = scene.blockSignals(True)
        except Exception:
            old_block = None
        try:
            for obj in list(scene.items()):
                try:
                    if isinstance(obj, TypesettingItem):
                        try:
                            obj.setSelected(False)
                            obj.setCacheMode(QGraphicsItem.CacheMode.NoCache)
                            obj.setVisible(False)
                        except Exception:
                            pass
                        scene.removeItem(obj)
                        removed += 1
                except RuntimeError:
                    continue
                except Exception:
                    continue
        finally:
            try:
                if old_block is not None:
                    scene.blockSignals(old_block)
            except Exception:
                pass
        return removed

    def _sync_text_table_rows_for_ids(self, ids=None, page_idx=None):
        """Update visible text table cells after command undo/redo without taking a snapshot."""
        try:
            target_page = int(getattr(self, "idx", 0) if page_idx is None else page_idx)
        except Exception:
            target_page = int(getattr(self, "idx", 0) or 0)
        if target_page != int(getattr(self, "idx", 0) or 0):
            return False
        curr = self.data.get(target_page) if isinstance(getattr(self, "data", None), dict) else None
        if not isinstance(curr, dict):
            return False
        data_by_id = {}
        try:
            for d in curr.get('data', []) or []:
                if isinstance(d, dict) and d.get('id') is not None:
                    data_by_id[str(d.get('id'))] = d
        except Exception:
            return False
        wanted = {str(x) for x in (ids or []) if x is not None}
        if not wanted:
            wanted = set(data_by_id.keys())
        try:
            self.tab.blockSignals(True)
        except Exception:
            pass
        changed = False
        try:
            for row in range(1, self.tab.rowCount()):
                id_item = self.tab.item(row, 0)
                sid = id_item.text().strip() if id_item is not None else ""
                if not sid or sid not in wanted:
                    continue
                d = data_by_id.get(sid)
                if not isinstance(d, dict):
                    continue
                try:
                    maker_mode = bool(hasattr(self, '_is_current_maker_page') and self._is_current_maker_page())
                    trans_col = self._table_translation_column() if hasattr(self, '_table_translation_column') else 3
                    self.tab.setItem(row, trans_col, QTableWidgetItem(str(d.get('translated_text', '') or '')))
                    if maker_mode:
                        status_col = QTableWidgetItem(str(d.get('maker_status') or (self.tr_ui('번역완료') if str(d.get('translated_text') or '').strip() else self.tr_ui('미번역'))))
                        status_col.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.tab.setItem(row, 1, status_col)
                    changed = True
                except Exception:
                    pass
        finally:
            try:
                self.tab.blockSignals(False)
            except Exception:
                pass
        return changed

    def _apply_text_item_lifecycle_command(self, command, *, redo=False):
        """Apply add/remove text-item commands without falling back to page snapshots."""
        try:
            page_idx = int(getattr(command, "page_idx", getattr(self, "idx", 0) or 0))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        curr = self.data.get(page_idx) if isinstance(getattr(self, "data", None), dict) else None
        if not isinstance(curr, dict):
            return False
        data_list = curr.setdefault('data', [])
        if not isinstance(data_list, list):
            data_list = []
            curr['data'] = data_list
        changed_ids = []
        old_text_lock = getattr(self, "_text_undo_restore_lock", False)
        old_project_lock = getattr(self, "_project_undo_restore_lock", False)
        old_command_lock = getattr(self, "_command_undo_restore_lock", False)
        self._text_undo_restore_lock = True
        self._project_undo_restore_lock = True
        self._command_undo_restore_lock = True
        try:
            for change in list(getattr(command, "changes", []) or []):
                try:
                    sid = str(getattr(change, "target_id", "") or "")
                    if not sid:
                        continue
                    meta = getattr(change, "meta", {}) or {}
                    missing_key = "after_missing" if redo else "before_missing"
                    desired_missing = bool(meta.get(missing_key, False))
                    desired_value = getattr(change, "after" if redo else "before")
                    idx_existing = None
                    for i, d in enumerate(list(data_list)):
                        if isinstance(d, dict) and str(d.get('id')) == sid:
                            idx_existing = i
                            break
                    if desired_missing:
                        if idx_existing is not None:
                            data_list.pop(idx_existing)
                        changed_ids.append(sid)
                        continue
                    if not isinstance(desired_value, dict):
                        continue
                    try:
                        item_copy = copy.deepcopy(desired_value)
                    except Exception:
                        item_copy = dict(desired_value)
                    if idx_existing is not None:
                        data_list[idx_existing] = item_copy
                    else:
                        index_key = "after_index" if redo else "before_index"
                        insert_at = meta.get(index_key, None)
                        try:
                            insert_at = int(insert_at)
                        except Exception:
                            insert_at = len(data_list)
                        insert_at = max(0, min(len(data_list), insert_at))
                        data_list.insert(insert_at, item_copy)
                    changed_ids.append(sid)
                except Exception:
                    continue
            if not changed_ids:
                return True
            if page_idx == int(getattr(self, "idx", 0) or 0):
                try:
                    self.ref_tab()
                except Exception:
                    pass
                try:
                    self.force_rebuild_final_text_layer_from_data(changed_ids)
                except Exception:
                    try:
                        self.schedule_final_text_scene_refresh(40)
                    except Exception:
                        pass
                try:
                    # If the command state contains the item, reselect it. If it removed the item, clear stale selection.
                    existing_ids = {str(d.get('id')) for d in data_list if isinstance(d, dict) and d.get('id') is not None}
                    keep_ids = [sid for sid in changed_ids if str(sid) in existing_ids]
                    if keep_ids:
                        self.reselect_text_items(keep_ids)
                    else:
                        sc = self._safe_graphics_scene()
                        if sc is not None:
                            sc.clearSelection()
                except Exception:
                    pass
            try:
                if hasattr(self, "text_engine") and self.text_engine is not None:
                    self.text_engine.mark_dirty(page_idx, changed_ids, ['data', 'translated_text', 'rect'])
            except Exception:
                pass
            try:
                if page_idx == int(getattr(self, "idx", 0) or 0):
                    self.mark_active_page_dirty("text")
                elif hasattr(self, "project_engine") and self.project_engine is not None:
                    self.project_engine.mark_page_dirty(page_idx, "text")
            except Exception:
                pass
            try:
                self.audit_boundary_event(
                    "UNDO_TEXT_ITEM_LIFECYCLE_COMMAND_APPLY",
                    page_idx=page_idx,
                    redo=bool(redo),
                    selected_count=len(changed_ids),
                    command_id=str(getattr(command, "command_id", "") or ""),
                    reason=str(getattr(command, "reason", "") or ""),
                    change_summary=(command.change_summary(value_limit=120) if hasattr(command, "change_summary") else ""),
                    target_ids=",".join([str(x) for x in changed_ids[:8]]),
                    throttle_ms=80,
                )
            except Exception:
                pass
            try:
                self.schedule_deferred_auto_save_project(900)
            except Exception:
                pass
            return True
        finally:
            self._text_undo_restore_lock = old_text_lock
            self._project_undo_restore_lock = old_project_lock
            self._command_undo_restore_lock = old_command_lock

    def _position_text_scene_item_from_data(self, item=None, data_item=None):
        """Reposition a live TypesettingItem from rect/x_off/y_off without full rerender."""
        if item is None or not isinstance(data_item, dict):
            return False
        try:
            rect = list(data_item.get('rect') or [0, 0, 1, 1])
            while len(rect) < 4:
                rect.append(1)
            rect_x = float(rect[0])
            rect_y = float(rect[1])
            rect_w = max(1.0, float(rect[2]))
            rect_h = max(1.0, float(rect[3]))
            x_off = float(data_item.get('x_off', 0) or 0)
            y_off = float(data_item.get('y_off', 0) or 0)
            if bool(data_item.get('rasterized_text')) or bool(getattr(item, '_is_rasterized_text', False)):
                pos_x = rect_x + x_off
                pos_y = rect_y + y_off
            else:
                align = (data_item.get('align') or 'center').lower()
                path_rect = getattr(item, '_text_path_rect', None)
                if path_rect is None:
                    try:
                        path_rect = item.path().boundingRect()
                    except Exception:
                        path_rect = item.boundingRect()
                final_x = rect_x + x_off
                final_y = rect_y + y_off
                if align == 'left':
                    pos_x = final_x - float(path_rect.left())
                elif align == 'right':
                    pos_x = final_x + rect_w - float(path_rect.right())
                else:
                    pos_x = final_x + rect_w / 2.0 - float(path_rect.center().x())
                pos_y = final_y + rect_h / 2.0 - float(path_rect.center().y())
            try:
                item.prepareGeometryChange()
            except Exception:
                pass
            try:
                item.data = data_item
            except Exception:
                pass
            item.setPos(float(pos_x), float(pos_y))
            try:
                if hasattr(item, 'transform_rect'):
                    item.setTransformOriginPoint(item.transform_rect().center())
                item.setRotation(float(data_item.get('rotation', 0) or 0))
            except Exception:
                pass
            try:
                item.update()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _apply_text_geometry_command(self, command, *, redo=False):
        """Apply text position/geometry Command-Diff without rebuilding the whole text layer."""
        try:
            page_idx = int(getattr(command, "page_idx", getattr(self, "idx", 0) or 0))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        _, by_id = self._text_data_items_by_id(page_idx)
        if not by_id:
            return False
        changed_ids = []
        changed_fields = set()
        for change in list(getattr(command, "changes", []) or []):
            try:
                sid = str(getattr(change, "target_id", "") or "")
                field_name = str(getattr(change, "field", "") or "")
                if not sid or not field_name:
                    continue
                target = by_id.get(sid)
                if not isinstance(target, dict):
                    continue
                meta = getattr(change, "meta", {}) or {}
                missing_key = "after_missing" if redo else "before_missing"
                target_missing = bool(meta.get(missing_key, False))
                value = getattr(change, "after" if redo else "before")
                current_exists = field_name in target
                current_value = target.get(field_name)
                if target_missing:
                    if current_exists:
                        target.pop(field_name, None)
                    else:
                        continue
                else:
                    try:
                        if current_exists and current_value == value:
                            continue
                    except Exception:
                        pass
                    try:
                        target[field_name] = copy.deepcopy(value)
                    except Exception:
                        target[field_name] = value
                if sid not in changed_ids:
                    changed_ids.append(sid)
                changed_fields.add(field_name)
            except Exception:
                continue
        if not changed_ids:
            try:
                meta = dict(getattr(command, "meta", {}) or {})
            except Exception:
                meta = {}
            # Timeline marker commands, such as a new-text creation-position
            # anchor, intentionally carry no field changes.  They still consume
            # one Ctrl+Z/Ctrl+Y slot but must not mutate text data or delete the
            # item.
            if bool(meta.get("force_record")):
                try:
                    self.audit_boundary_event(
                        "UNDO_TEXT_GEOMETRY_COMMAND_MARKER_APPLY",
                        page_idx=page_idx,
                        redo=bool(redo),
                        reason=str(getattr(command, "reason", "") or ""),
                        marker=str(meta.get("marker") or ""),
                        command_id=str(getattr(command, "command_id", "") or ""),
                        target_ids=",".join([str(x) for x in (getattr(command, "target_ids", []) or [])][:8]),
                        throttle_ms=80,
                    )
                except Exception:
                    pass
                return True
            return True

        old_text_lock = getattr(self, "_text_undo_restore_lock", False)
        old_project_lock = getattr(self, "_project_undo_restore_lock", False)
        old_command_lock = getattr(self, "_command_undo_restore_lock", False)
        old_scene_sync_lock = getattr(self, "_text_scene_sync_lock", False)
        self._text_undo_restore_lock = True
        self._project_undo_restore_lock = True
        self._command_undo_restore_lock = True
        self._text_scene_sync_lock = True
        try:
            if page_idx == int(getattr(self, "idx", 0) or 0):
                scene_items = self._scene_text_items_by_id()
                positioned = False
                for sid in changed_ids:
                    item = scene_items.get(str(sid))
                    data_item = by_id.get(str(sid))
                    if item is not None and isinstance(data_item, dict):
                        if self._position_text_scene_item_from_data(item, data_item):
                            positioned = True
                if not positioned:
                    refreshed = False
                    try:
                        refreshed = bool(self.rebuild_current_page_text_layer_from_data(changed_ids, clear_selection=False))
                    except Exception:
                        refreshed = False
                    # 텍스트 위치/영역 Undo는 구조 변경이 아니므로 mode_chg 기반 전체 재구성을 타지 않는다.
                    # QGraphicsItem이 잠시 없으면 다음 이벤트 루프에서 부분 refresh만 예약한다.
                    if not refreshed:
                        try:
                            self.schedule_final_text_scene_refresh(80)
                        except Exception:
                            pass
                else:
                    try:
                        self.view.scene.update()
                    except Exception:
                        pass
                try:
                    self.reselect_text_items(changed_ids)
                except Exception:
                    pass
            try:
                if hasattr(self, "text_engine") and self.text_engine is not None:
                    self.text_engine.mark_dirty(page_idx, changed_ids, sorted(changed_fields))
            except Exception:
                pass
            try:
                if page_idx == int(getattr(self, "idx", 0) or 0):
                    self.mark_active_page_dirty("text")
                elif hasattr(self, "project_engine") and self.project_engine is not None:
                    self.project_engine.mark_page_dirty(page_idx, "text")
            except Exception:
                pass
            try:
                self.audit_boundary_event(
                    "UNDO_TEXT_GEOMETRY_COMMAND_APPLY",
                    page_idx=page_idx,
                    redo=bool(redo),
                    selected_count=len(changed_ids),
                    fields=",".join(sorted(changed_fields)),
                    command_id=str(getattr(command, "command_id", "") or ""),
                    component_type=str(getattr(command, "component_type", "") or ""),
                    reason=str(getattr(command, "reason", "") or ""),
                    change_summary=(command.change_summary() if hasattr(command, "change_summary") else ""),
                    target_ids=",".join([str(x) for x in changed_ids[:8]]),
                    throttle_ms=80,
                )
            except Exception:
                pass
            try:
                self.schedule_deferred_auto_save_project(900)
            except Exception:
                pass
            return True
        finally:
            self._text_undo_restore_lock = old_text_lock
            self._project_undo_restore_lock = old_project_lock
            self._command_undo_restore_lock = old_command_lock
            self._text_scene_sync_lock = old_scene_sync_lock

    def _apply_text_style_command(self, command, *, redo=False):
        """Apply a text_style UndoCommand using field-level before/after values."""
        try:
            page_idx = int(getattr(command, "page_idx", getattr(self, "idx", 0) or 0))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        _, by_id = self._text_data_items_by_id(page_idx)
        if not by_id:
            return False
        changed_ids = []
        changed_fields = set()
        for change in list(getattr(command, "changes", []) or []):
            try:
                sid = str(getattr(change, "target_id", "") or "")
                field_name = str(getattr(change, "field", "") or "")
                if not sid or not field_name:
                    continue
                target = by_id.get(sid)
                if not isinstance(target, dict):
                    continue
                meta = getattr(change, "meta", {}) or {}
                missing_key = "after_missing" if redo else "before_missing"
                target_missing = bool(meta.get(missing_key, False))
                value = getattr(change, "after" if redo else "before")
                current_exists = field_name in target
                current_value = target.get(field_name)
                if target_missing:
                    if current_exists:
                        target.pop(field_name, None)
                    else:
                        continue
                else:
                    try:
                        if current_exists and current_value == value:
                            continue
                    except Exception:
                        pass
                    try:
                        target[field_name] = copy.deepcopy(value)
                    except Exception:
                        target[field_name] = value
                if sid not in changed_ids:
                    changed_ids.append(sid)
                changed_fields.add(field_name)
            except Exception:
                continue
        if not changed_ids:
            return True

        old_text_lock = getattr(self, "_text_undo_restore_lock", False)
        old_project_lock = getattr(self, "_project_undo_restore_lock", False)
        old_command_lock = getattr(self, "_command_undo_restore_lock", False)
        self._text_undo_restore_lock = True
        self._project_undo_restore_lock = True
        self._command_undo_restore_lock = True
        try:
            if page_idx == int(getattr(self, "idx", 0) or 0):
                component_type = str(getattr(command, "component_type", "") or "")
                content_like = component_type in ("text_content", "text_direct_edit") or "translated_text" in changed_fields
                refreshed = False
                # 직접 텍스트 수정 Undo/Redo는 2.4.1의 안정 경로처럼 기존 TypesettingItem을 살려두고
                # 해당 item만 갱신한다.  여기서 force_rebuild_final_text_layer_from_data()를 타면
                # mode_chg(4)로 scene item을 갈아끼우게 되어 Qt/C++ access violation 위험이 커진다.
                scene_items = self._scene_text_items_by_id()
                live_items = []
                for sid in changed_ids:
                    item = scene_items.get(str(sid))
                    data_item = by_id.get(str(sid))
                    if item is not None and isinstance(data_item, dict):
                        try:
                            item.data = data_item
                        except Exception:
                            pass
                        try:
                            item.setVisible(True)
                        except Exception:
                            pass
                        live_items.append(item)
                if live_items:
                    try:
                        refreshed = bool(self.refresh_text_items_live_in_place(live_items, keep_selection=True))
                    except Exception:
                        refreshed = False
                if not refreshed:
                    try:
                        refreshed = bool(self.rebuild_current_page_text_layer_from_data(changed_ids, clear_selection=False))
                    except Exception:
                        refreshed = False
                # text_style/text_content Command는 item 수/ID가 바뀌는 구조 변경이 아니다.
                # 실패 시에도 전체 mode_chg rebuild 대신 짧은 지연 부분 refresh만 예약한다.
                if not refreshed:
                    try:
                        self.schedule_final_text_scene_refresh(80)
                    except Exception:
                        pass
                try:
                    self.audit_boundary_event(
                        "UNDO_TEXT_STYLE_REFRESH_IN_PLACE",
                        page_idx=page_idx,
                        redo=bool(redo),
                        content_like=bool(content_like),
                        refreshed=bool(refreshed),
                        target_ids=",".join([str(x) for x in changed_ids[:8]]),
                        throttle_ms=80,
                    )
                except Exception:
                    pass
                if "translated_text" in changed_fields:
                    try:
                        self._sync_text_table_rows_for_ids(changed_ids, page_idx=page_idx)
                    except Exception:
                        pass
                try:
                    self.reselect_text_items(changed_ids)
                except Exception:
                    pass
                try:
                    self.update_item_preset_combo_for_selected_texts()
                except Exception:
                    pass
            try:
                if hasattr(self, "text_engine") and self.text_engine is not None:
                    self.text_engine.mark_dirty(page_idx, changed_ids, sorted(changed_fields))
            except Exception:
                pass
            try:
                if page_idx == int(getattr(self, "idx", 0) or 0):
                    self.mark_active_page_dirty("text")
                elif hasattr(self, "project_engine") and self.project_engine is not None:
                    self.project_engine.mark_page_dirty(page_idx, "text")
            except Exception:
                pass
            try:
                self.audit_boundary_event("UNDO_TEXT_STYLE_COMMAND_APPLY", page_idx=page_idx, redo=bool(redo), selected_count=len(changed_ids), fields=",".join(sorted(changed_fields)), throttle_ms=80)
            except Exception:
                pass
            try:
                self.schedule_deferred_auto_save_project(900)
            except Exception:
                pass
            return True
        finally:
            self._text_undo_restore_lock = old_text_lock
            self._project_undo_restore_lock = old_project_lock
            self._command_undo_restore_lock = old_command_lock

    def _apply_ocr_analysis_region_command(self, command, *, redo=False):
        """Apply committed OCR analysis-region list changes page-by-page."""
        touched_pages = []
        for change in list(getattr(command, "changes", []) or []):
            try:
                if str(getattr(change, "field", "") or "") != "ocr_analysis_regions":
                    continue
                meta = getattr(change, "meta", {}) or {}
                page_idx = meta.get("target_page_idx", getattr(change, "page_idx", None))
                if page_idx is None:
                    tid = str(getattr(change, "target_id", "") or "")
                    if ":" in tid:
                        page_idx = tid.rsplit(":", 1)[-1]
                page_idx = int(page_idx)
            except Exception:
                continue
            curr = self.data.get(page_idx) if hasattr(self, "data") else None
            if not isinstance(curr, dict):
                continue
            value = getattr(change, "after" if redo else "before")
            try:
                curr['ocr_analysis_regions'] = copy.deepcopy(value or [])
            except Exception:
                curr['ocr_analysis_regions'] = list(value or []) if isinstance(value, (list, tuple)) else []
            if page_idx not in touched_pages:
                touched_pages.append(page_idx)
        if not touched_pages:
            return True
        old_project_lock = getattr(self, "_project_undo_restore_lock", False)
        old_command_lock = getattr(self, "_command_undo_restore_lock", False)
        self._project_undo_restore_lock = True
        self._command_undo_restore_lock = True
        try:
            current_page = int(getattr(self, "idx", 0) or 0)
            for page_idx in touched_pages:
                try:
                    if page_idx == current_page:
                        self.mark_active_page_dirty("ocr_analysis_regions")
                    elif hasattr(self, "project_engine") and self.project_engine is not None:
                        self.project_engine.mark_page_dirty(page_idx, "ocr_analysis_regions")
                except Exception:
                    pass
            try:
                self.refresh_ocr_region_overlay()
            except Exception:
                pass
            try:
                self.schedule_deferred_auto_save_project(900)
            except Exception:
                try:
                    self.auto_save_project()
                except Exception:
                    pass
            try:
                self.audit_boundary_event(
                    "UNDO_OCR_REGION_COMMAND_APPLY",
                    redo=bool(redo),
                    affected=','.join(str(x) for x in touched_pages),
                    throttle_ms=80,
                )
            except Exception:
                pass
            return True
        finally:
            self._project_undo_restore_lock = old_project_lock
            self._command_undo_restore_lock = old_command_lock

    def _apply_view_state_command(self, command, *, redo=False):
        """Apply zoom/pan command using the lightweight view state path."""
        try:
            page_idx = int(getattr(command, "page_idx", getattr(self, "idx", 0) or 0))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        if page_idx != int(getattr(self, "idx", 0) or 0):
            return False
        try:
            mode_idx = int((getattr(command, "meta", {}) or {}).get("mode", self.current_mode_index_safe()))
        except Exception:
            mode_idx = int(getattr(self, "last_mode", 0) or 0)
        # Use current state as base so commands that only changed scroll or zoom
        # do not need to store duplicate unchanged fields.
        try:
            state = copy.deepcopy(self.capture_view_state() or {})
        except Exception:
            state = {}
        changed_fields = set()
        for change in list(getattr(command, "changes", []) or []):
            try:
                field_name = str(getattr(change, "field", "") or "")
                if not field_name:
                    continue
                meta = getattr(change, "meta", {}) or {}
                missing_key = "after_missing" if redo else "before_missing"
                target_missing = bool(meta.get(missing_key, False))
                value = getattr(change, "after" if redo else "before")
                if target_missing:
                    state.pop(field_name, None)
                else:
                    try:
                        state[field_name] = copy.deepcopy(value)
                    except Exception:
                        state[field_name] = value
                changed_fields.add(field_name)
            except Exception:
                continue
        if not changed_fields:
            return True
        old_project_lock = getattr(self, "_project_undo_restore_lock", False)
        old_command_lock = getattr(self, "_command_undo_restore_lock", False)
        old_suppress_view_dirty = getattr(self, "_suppress_view_dirty_during_programmatic_view_change", False)
        self._project_undo_restore_lock = True
        self._command_undo_restore_lock = True
        self._suppress_view_dirty_during_programmatic_view_change = True
        try:
            ok = bool(self.apply_view_state(state))
            if ok:
                try:
                    self.project_ui_view_states[self.view_state_key(page_idx, mode_idx)] = copy.deepcopy(state)
                except Exception:
                    pass
                try:
                    if hasattr(self, "view_engine") and self.view_engine is not None:
                        self.view_engine.remember(page_idx, mode_idx, state)
                except Exception:
                    pass
                try:
                    self.audit_boundary_event(
                        "UNDO_VIEW_STATE_COMMAND_APPLY",
                        page_idx=page_idx,
                        mode=mode_idx,
                        redo=bool(redo),
                        fields=",".join(sorted(changed_fields)),
                        throttle_ms=80,
                    )
                except Exception:
                    pass
            return bool(ok)
        finally:
            self._project_undo_restore_lock = old_project_lock
            self._command_undo_restore_lock = old_command_lock
            self._suppress_view_dirty_during_programmatic_view_change = old_suppress_view_dirty

    def _apply_work_tab_command(self, command, *, redo=False):
        """Apply work-tab current_index command through mode_chg without recording another Undo."""
        try:
            page_idx = int(getattr(command, "page_idx", getattr(self, "idx", 0) or 0))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        if page_idx != int(getattr(self, "idx", 0) or 0):
            return False
        target_mode = None
        target_view_state = None
        for change in list(getattr(command, "changes", []) or []):
            try:
                if str(getattr(change, "field", "") or "") != "current_index":
                    continue
                target_mode = int(getattr(change, "after" if redo else "before"))
                if not redo:
                    target_view_state = copy.deepcopy((getattr(change, "meta", {}) or {}).get("before_view_state") or {})
                break
            except Exception:
                continue
        if target_mode is None:
            meta = getattr(command, "meta", {}) or {}
            try:
                target_mode = int(meta.get("new_mode" if redo else "old_mode"))
            except Exception:
                return False
            if not redo:
                target_view_state = copy.deepcopy(meta.get("before_view_state") or {})
        try:
            if hasattr(self, "cb_mode") and (target_mode < 0 or target_mode >= self.cb_mode.count()):
                return False
        except Exception:
            pass
        old_project_lock = getattr(self, "_project_undo_restore_lock", False)
        old_command_lock = getattr(self, "_command_undo_restore_lock", False)
        old_mode_suppress = getattr(self, "_suppress_mode_undo", False)
        old_skip_mask_commit = getattr(self, "_skip_mode_mask_commit", False)
        self._project_undo_restore_lock = True
        self._command_undo_restore_lock = True
        self._suppress_mode_undo = True
        self._skip_mode_mask_commit = True
        try:
            if hasattr(self, "cb_mode"):
                try:
                    self.cb_mode.blockSignals(True)
                    self.cb_mode.setCurrentIndex(int(target_mode))
                finally:
                    self.cb_mode.blockSignals(False)
            try:
                self.mode_chg(int(target_mode))
            except TypeError:
                self.mode_chg(target_mode)
            try:
                # Safety UX rule: after tab changes, tools reset to move mode.
                if getattr(self.view, "draw_mode", None):
                    self.set_tool(None)
            except Exception:
                pass
            if isinstance(target_view_state, dict) and target_view_state:
                try:
                    self.apply_view_state(target_view_state)
                    self.project_ui_view_states[self.view_state_key(page_idx, target_mode)] = copy.deepcopy(target_view_state)
                except Exception:
                    pass
            try:
                if hasattr(self, "layer_engine") and self.layer_engine is not None:
                    state = self.capture_view_state() if hasattr(self, "capture_view_state") else {}
                    self.layer_engine.remember_mode_state(page_idx, int(target_mode), state)
            except Exception:
                pass
            try:
                self.audit_boundary_event(
                    "UNDO_WORK_TAB_COMMAND_APPLY",
                    page_idx=page_idx,
                    target_mode=int(target_mode),
                    redo=bool(redo),
                    throttle_ms=80,
                )
            except Exception:
                pass
            return True
        finally:
            self._project_undo_restore_lock = old_project_lock
            self._command_undo_restore_lock = old_command_lock
            self._suppress_mode_undo = old_mode_suppress
            self._skip_mode_mask_commit = old_skip_mask_commit

    def _paint_patch_target_item_for_layer_id(self, layer_id=None, kind=None):
        """Resolve a runtime paint/mask command target layer on the active viewer."""
        try:
            view = getattr(self, "view", None)
            if view is None:
                return None
            lid = str(layer_id or "").lower()
            k = str(kind or "").lower()
            if lid.endswith("final_paint_above"):
                return getattr(view, "final_paint_above_item", None)
            if lid.endswith("final_paint") or k == "final_paint":
                # Preserve the exact layer recorded by the command when possible;
                # default to the normal final paint layer for older commands.
                if lid.endswith("final_paint_above"):
                    return getattr(view, "final_paint_above_item", None)
                return getattr(view, "final_paint_item", None)
            if lid.endswith("mask") or k == "mask":
                return getattr(view, "user_mask_item", None)
        except Exception:
            return None
        return None

    def _refresh_paint_patch_target_cache(self, target_item=None, kind=None, layer_id=None):
        """Keep viewer cached QImage references in sync after a patch command."""
        try:
            view = getattr(self, "view", None)
            if view is None or target_item is None:
                return
            pix = target_item.pixmap()
            if target_item is getattr(view, "final_paint_above_item", None):
                view.final_paint_above_img = pix.toImage()
            elif target_item is getattr(view, "final_paint_item", None):
                view.final_paint_img = pix.toImage()
            elif target_item is getattr(view, "user_mask_item", None):
                view.user_mask_img = pix.toImage()
        except Exception:
            pass


    def _mask_state_nonzero_count(self, mask):
        try:
            import numpy as _np
            if isinstance(mask, _np.ndarray):
                return int(_np.count_nonzero(mask))
        except Exception:
            pass
        return -1

    def _apply_full_mask_state_from_command(self, mask_state, *, mode=None, page_idx=None, redo=False, command=None):
        """Apply a full editable mask state captured with a paint/mask command.

        Patch drawing is not enough for loaded OCR/page masks because the visible
        overlay and the persisted active mask can diverge.  This path treats the
        current mask tab's editable mask as the source of truth, writes it back to
        page data, rebuilds the overlay, and updates the viewport immediately.
        """
        try:
            import numpy as _np
        except Exception:
            _np = None
        if _np is None or not isinstance(mask_state, _np.ndarray):
            return False
        view = getattr(self, "view", None)
        if view is None:
            return False
        try:
            mode_i = int(mode if mode is not None else (self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else getattr(self, "last_mode", 2)))
        except Exception:
            mode_i = 2
        try:
            page_i = int(page_idx if page_idx is not None else getattr(self, "idx", 0) or 0)
        except Exception:
            page_i = int(getattr(self, "idx", 0) or 0)
        if page_i != int(getattr(self, "idx", 0) or 0):
            return False
        try:
            mask = mask_state.copy().astype(_np.uint8)
        except Exception:
            mask = mask_state
        try:
            color = QColor(0, 0, 255, 150) if mode_i == 3 else QColor(168, 93, 102, 140)
            if getattr(view, "user_mask_item", None) is None:
                if hasattr(view, "set_mask_overlay_layer"):
                    view.set_mask_overlay_layer(mask, color)
            if hasattr(view, "set_user_mask_np"):
                view.set_user_mask_np(mask, color)
        except Exception:
            try:
                if hasattr(view, "set_mask_overlay_layer"):
                    view.set_mask_overlay_layer(mask, QColor(0, 0, 255, 150) if mode_i == 3 else QColor(168, 93, 102, 140))
            except Exception:
                return False
        try:
            curr = self.data.get(page_i) if hasattr(self, "data") else None
            if isinstance(curr, dict):
                if hasattr(self, "set_active_mask"):
                    self.set_active_mask(curr, mask, mode_i)
                curr["mask_toggle_enabled"] = bool(getattr(self, "mask_toggle_enabled", curr.get("mask_toggle_enabled", True)))
        except Exception:
            pass
        try:
            if hasattr(view, "scene"):
                view.scene.update()
            if hasattr(view, "viewport"):
                view.viewport().update()
        except Exception:
            pass
        try:
            self.audit_boundary_event(
                "UNDO_MASK_STATE_APPLY",
                page_idx=page_i,
                redo=bool(redo),
                mode=mode_i,
                nonzero=self._mask_state_nonzero_count(mask),
                command_id=str(getattr(command, "command_id", "") or "")[:12] if command is not None else "",
                throttle_ms=60,
            )
        except Exception:
            pass
        return True

    def _apply_paint_mask_patch_command(self, command, *, redo=False):
        """Apply paint/mask bbox patches stored directly in a runtime UndoCommand.

        Stage 7 keeps mask/paint data lossless.  It only changes the undo record
        granularity: before/after QPixmap patches inside dirty QRect bboxes are
        applied to the live layer, while full layer snapshots remain fallback-only.
        """
        try:
            page_idx = int(getattr(command, "page_idx", getattr(self, "idx", 0) or 0))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        try:
            if page_idx != int(getattr(self, "idx", 0) or 0):
                return False
        except Exception:
            return False
        old_project_lock = getattr(self, "_project_undo_restore_lock", False)
        old_command_lock = getattr(self, "_command_undo_restore_lock", False)
        self._project_undo_restore_lock = True
        self._command_undo_restore_lock = True
        touched_kinds = set()
        try:
            changed = False
            dirty_scene_rect = None
            mask_state_applied = False
            # Prefer full editable mask state for mask commands.  This fixes
            # Undo on masks that were loaded from page data instead of newly
            # painted in the current overlay.
            for change in list(getattr(command, "changes", []) or []):
                try:
                    if str(getattr(change, "field", "") or "") != "mask_state":
                        continue
                    meta = getattr(change, "meta", {}) or {}
                    mode_i = int(meta.get("mode", getattr(self, "last_mode", 2)) or 2)
                    mask_state = getattr(change, "after" if redo else "before", None)
                    if self._apply_full_mask_state_from_command(mask_state, mode=mode_i, page_idx=page_idx, redo=bool(redo), command=command):
                        mask_state_applied = True
                        changed = True
                        touched_kinds.add("mask")
                except Exception:
                    continue
            for change in list(getattr(command, "changes", []) or []):
                try:
                    if str(getattr(change, "field", "") or "") != "patches":
                        continue
                    meta = getattr(change, "meta", {}) or {}
                    layer_id = str(meta.get("layer_id") or getattr(change, "target_id", "") or "")
                    kind = str(meta.get("kind") or ("mask" if layer_id.endswith(":mask") else "final_paint"))
                    if mask_state_applied and (kind == "mask" or layer_id.endswith(":mask")):
                        continue
                    target_item = self._paint_patch_target_item_for_layer_id(layer_id, kind)
                    if target_item is None:
                        return False
                    pix = target_item.pixmap()
                    if pix.isNull():
                        return False
                    patches = getattr(change, "after" if redo else "before") or []
                    if not patches:
                        continue
                    painter = QPainter(pix)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                    try:
                        for patch in list(patches or []):
                            if not isinstance(patch, dict):
                                continue
                            rect = patch.get("rect")
                            patch_pix = patch.get("pixmap") or patch.get("patch")
                            if rect is None or patch_pix is None:
                                continue
                            painter.drawPixmap(rect.topLeft(), patch_pix)
                            try:
                                qrf = QRectF(rect)
                                dirty_scene = target_item.mapRectToScene(qrf)
                            except Exception:
                                dirty_scene = QRectF(rect)
                            dirty_scene_rect = QRectF(dirty_scene) if dirty_scene_rect is None else dirty_scene_rect.united(dirty_scene)
                            changed = True
                    finally:
                        painter.end()
                    if changed:
                        target_item.setPixmap(pix)
                        try:
                            if dirty_scene_rect is not None:
                                target_item.update(target_item.mapFromScene(dirty_scene_rect).boundingRect())
                            else:
                                target_item.update()
                        except Exception:
                            try:
                                target_item.update()
                            except Exception:
                                pass
                        self._refresh_paint_patch_target_cache(target_item, kind=kind, layer_id=layer_id)
                        touched_kinds.add("mask" if kind == "mask" or layer_id.endswith(":mask") else "final_paint")
                except Exception:
                    return False
            if not changed:
                return True
            try:
                view = getattr(self, "view", None)
                if view is not None:
                    if dirty_scene_rect is not None:
                        view.viewport().update(view.mapFromScene(dirty_scene_rect).boundingRect().adjusted(-6, -6, 6, 6))
                    else:
                        view.viewport().update()
            except Exception:
                pass
            try:
                self._sync_live_paint_mask_after_patch(touched_kinds, dirty_scene_rect=dirty_scene_rect)
            except Exception:
                pass
            for kind in sorted(touched_kinds):
                try:
                    if hasattr(self, "schedule_deferred_view_layer_commit"):
                        self.schedule_deferred_view_layer_commit(kind, delay_ms=1200)
                except Exception:
                    pass
            try:
                self.audit_boundary_event(
                    "UNDO_PAINT_MASK_PATCH_COMMAND_APPLY",
                    page_idx=page_idx,
                    redo=bool(redo),
                    kinds=','.join(sorted(touched_kinds)),
                    change_count=int(getattr(command, "change_count", 0) or 0),
                    mask_state_applied=bool(mask_state_applied),
                    command_id=str(getattr(command, "command_id", "") or "")[:12],
                    change_summary=str(command.change_summary(limit=3, value_limit=40)) if hasattr(command, "change_summary") else "",
                    throttle_ms=80,
                )
            except Exception:
                pass
            return True
        finally:
            self._project_undo_restore_lock = old_project_lock
            self._command_undo_restore_lock = old_command_lock


    def _sync_live_paint_mask_after_patch(self, touched_kinds=None, *, dirty_scene_rect=None):
        """Immediately refresh visible paint/mask layers after a patch Undo/Redo.

        Deferred commit is good for saving, but the canvas must reflect Undo/Redo
        right away.  Mask tabs in particular show a colored overlay whose alpha
        is the real mask; after patching the overlay pixmap, sync the data mask
        and rebuild the current overlay so the user sees the restored mask without
        leaving and re-entering the tab.
        """
        touched = set(touched_kinds or [])
        view = getattr(self, "view", None)
        if view is None:
            return
        try:
            mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else int(getattr(self, "last_mode", 0) or 0)
        except Exception:
            mode = int(getattr(self, "last_mode", 0) or 0)
        try:
            if "mask" in touched and mode in (2, 3):
                curr = self.data.get(self.idx) if hasattr(self, "data") else None
                mask_np = None
                try:
                    mask_np = view.get_mask_np()
                except Exception:
                    mask_np = None
                if mask_np is not None and isinstance(curr, dict):
                    try:
                        self.set_active_mask(curr, mask_np, mode)
                        curr["mask_toggle_enabled"] = getattr(self, "mask_toggle_enabled", curr.get("mask_toggle_enabled", True))
                    except Exception:
                        pass
                    try:
                        color = QColor(0, 0, 255, 100) if mode == 3 else QColor(255, 0, 0, 100)
                        if hasattr(view, "set_mask_overlay_layer"):
                            view.set_mask_overlay_layer(self.get_active_mask(curr, mode), color)
                    except Exception:
                        pass
            if "final_paint" in touched:
                try:
                    curr = self.data.get(self.idx) if hasattr(self, "data") else None
                    if isinstance(curr, dict) and hasattr(view, "get_final_paint_png_bytes"):
                        curr["final_paint"] = view.get_final_paint_png_bytes()
                        if hasattr(view, "get_final_paint_above_png_bytes"):
                            curr["final_paint_above"] = view.get_final_paint_above_png_bytes()
                except Exception:
                    pass
            try:
                if dirty_scene_rect is not None:
                    view.scene.update(dirty_scene_rect)
                    view.viewport().update(view.mapFromScene(dirty_scene_rect).boundingRect().adjusted(-10, -10, 10, 10))
                else:
                    view.scene.update()
                    view.viewport().update()
            except Exception:
                try:
                    view.viewport().update()
                except Exception:
                    pass
            try:
                self.audit_boundary_event(
                    "UNDO_PAINT_MASK_LIVE_REFRESH",
                    kinds=','.join(sorted(touched)),
                    mode=mode,
                    has_dirty_rect=dirty_scene_rect is not None,
                    mask_nonzero=self._mask_state_nonzero_count(mask_np) if 'mask_np' in locals() else -1,
                    throttle_ms=80,
                )
            except Exception:
                pass
        except Exception:
            pass

    def _apply_project_structure_command(self, command, *, redo=False):
        """Apply a Stage 8 project/page structure command.

        Page add/delete/reorder changes are large enough that restoring one
        scalar field is not sufficient.  The command owns the before/after
        project structure state and applies it through the normal load/refresh
        path, while avoiding new Undo records during restore.
        """
        target_state = None
        try:
            for change in list(getattr(command, "changes", []) or []):
                if str(getattr(change, "target_id", "") or "") == "project":
                    target_state = getattr(change, "after" if redo else "before", None)
                    break
        except Exception:
            target_state = None
        if not isinstance(target_state, dict):
            return False

        old_project_lock = getattr(self, "_project_undo_restore_lock", False)
        old_text_lock = getattr(self, "_text_undo_restore_lock", False)
        old_command_lock = getattr(self, "_command_undo_restore_lock", False)
        old_suppress = getattr(self, "_suppress_project_undo", False)
        self._project_undo_restore_lock = True
        self._text_undo_restore_lock = True
        self._command_undo_restore_lock = True
        self._suppress_project_undo = True
        try:
            try:
                self.paths = [str(p) for p in (target_state.get("paths") or [])]
            except Exception:
                self.paths = []

            restored_data = {}
            try:
                for k, v in (target_state.get("data") or {}).items():
                    try:
                        kk = int(k)
                    except Exception:
                        kk = k
                    restored_data[kk] = self.copy_undo_page_data(v) if isinstance(v, dict) else copy.deepcopy(v)
            except Exception:
                restored_data = copy.deepcopy(target_state.get("data") or {})
            self.data = restored_data

            try:
                self.project_ui_view_states = copy.deepcopy(target_state.get("project_ui_view_states") or {})
            except Exception:
                self.project_ui_view_states = {}

            try:
                idx = int(target_state.get("idx", 0) or 0)
            except Exception:
                idx = 0
            if self.paths:
                idx = max(0, min(idx, len(self.paths) - 1))
            else:
                idx = 0
            self.idx = idx

            try:
                mode = int(target_state.get("mode", getattr(self, "last_mode", 0)) or 0)
            except Exception:
                mode = int(getattr(self, "last_mode", 0) or 0)
            try:
                self.set_work_mode_without_undo(mode)
            except Exception:
                pass

            try:
                self.refresh_page_tabs()
            except Exception:
                pass
            try:
                if self.paths:
                    bar = getattr(self, "page_tab_bar", None)
                    if bar is not None and hasattr(bar, "setSelectedIndices"):
                        bar.setSelectedIndices([self.idx])
            except Exception:
                pass

            prev_loading = getattr(self, "is_page_loading", False)
            self.is_page_loading = True
            try:
                if self.paths:
                    self.load()
                else:
                    try:
                        scene = self._safe_graphics_scene()
                        if scene is not None:
                            scene.clear()
                    except Exception:
                        pass
            finally:
                self.is_page_loading = prev_loading

            try:
                self.restore_current_view_state_later()
            except Exception:
                pass
            try:
                self.update_page_tab_scroll_buttons()
            except Exception:
                pass
            try:
                self.schedule_deferred_auto_save_project(600)
            except Exception:
                try:
                    self.auto_save_project()
                except Exception:
                    pass
            try:
                self.audit_boundary_event(
                    "UNDO_PROJECT_STRUCTURE_COMMAND_APPLY",
                    redo=bool(redo),
                    page_idx=int(self.idx),
                    count=len(self.paths or []),
                    action=str((getattr(command, "meta", {}) or {}).get("action") or ""),
                    throttle_ms=100,
                )
            except Exception:
                pass
            return True
        finally:
            self._suppress_project_undo = old_suppress
            self._command_undo_restore_lock = old_command_lock
            self._text_undo_restore_lock = old_text_lock
            self._project_undo_restore_lock = old_project_lock

    def apply_undo_command(self, command, *, redo=False):
        component_type = str(getattr(command, "component_type", "") or "")
        if component_type in ("text_item_lifecycle", "text_item_add", "text_item_remove"):
            return self._apply_text_item_lifecycle_command(command, redo=bool(redo))
        if component_type in ("text_style", "text_item_style", "text_content", "text_direct_edit"):
            return self._apply_text_style_command(command, redo=bool(redo))
        if component_type in ("text_geometry", "text_position", "text_move", "text_rect"):
            return self._apply_text_geometry_command(command, redo=bool(redo))
        if component_type in ("text_transform", "text_deform", "text_shape"):
            # Transform fields change the text path/guide box, so use the live
            # in-place rerender path rather than the position-only setPos path.
            return self._apply_text_style_command(command, redo=bool(redo))
        if component_type in ("view_state", "view_zoom", "view_pan", "view_fit"):
            return self._apply_view_state_command(command, redo=bool(redo))
        if component_type in ("work_tab", "work_tab_change", "work_mode"):
            return self._apply_work_tab_command(command, redo=bool(redo))
        if component_type in ("ocr_analysis_regions", "ocr_region", "analysis_region"):
            return self._apply_ocr_analysis_region_command(command, redo=bool(redo))
        if component_type in ("text_region_reset", "text_area_reset"):
            return self._apply_text_style_command(command, redo=bool(redo))
        if component_type in ("paint_mask_patch", "paint_patch", "mask_patch", "paint_layer_patch"):
            return self._apply_paint_mask_patch_command(command, redo=bool(redo))
        if component_type in ("project_structure", "page_structure", "page_add_delete", "page_reorder"):
            return self._apply_project_structure_command(command, redo=bool(redo))
        if component_type in ("ocr_region_temp", "ocr_region_runtime"):
            return self._apply_ocr_region_temp_command(command, redo=bool(redo))
        if component_type in ("magic_wand_runtime", "magic_wand_selection"):
            return self._apply_magic_wand_runtime_command(command, redo=bool(redo))
        # Backward compatible generic text command dispatch: pure geometry fields go
        # to the lightweight position path; transform/style fields use live rerender.
        if component_type == "text":
            fields = {str(getattr(c, "field", "") or "") for c in list(getattr(command, "changes", []) or [])}
            if fields and fields.issubset({"rect", "x_off", "y_off", "manual_text_rect", "text_anchor_mode"}):
                return self._apply_text_geometry_command(command, redo=bool(redo))
            return self._apply_text_style_command(command, redo=bool(redo))
        try:
            self.audit_boundary_event("UNDO_COMMAND_UNHANDLED_COMPONENT", component_type=component_type, redo=bool(redo), throttle_ms=120)
        except Exception:
            pass
        return False

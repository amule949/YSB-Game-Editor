from ysb.ui.main_window_support import *


class MainWindowHistoryMixin:

    def ensure_page_project_engines(self):
        try:
            ready = (
                hasattr(self, "project_engine") and self.project_engine is not None and
                hasattr(self, "page_engine") and self.page_engine is not None and
                hasattr(self, "undo_manager") and self.undo_manager is not None and
                hasattr(self, "view_engine") and self.view_engine is not None and
                hasattr(self, "layer_engine") and self.layer_engine is not None and
                hasattr(self, "storage_engine") and self.storage_engine is not None
            )
            now = __import__("time").time()
            last = float(getattr(self, "_last_ensure_page_project_engines_ts", 0.0) or 0.0)
            if ready and (now - last) < 1.0:
                return True
            self._last_ensure_page_project_engines_ts = now
            self.audit_boundary_event("ENSURE_ENGINES", throttle_ms=1800)
        except Exception:
            pass
        """Ensure the new page/project engine split exists.

        This is kept in the mixin so older saved windows or partial imports still
        work even if MainWindow.__init__ was created before the refactor.
        """
        try:
            from ysb.core.page_engine import YSBPageEngine
            from ysb.core.project_engine import YSBProjectEngine
            from ysb.core.view_engine import YSBViewEngine
            from ysb.core.layer_engine import YSBLayerEngine
            from ysb.core.storage_engine import YSBStorageEngine
            from ysb.core.undo_manager import YSBUndoManager
            if not hasattr(self, "project_engine") or self.project_engine is None:
                self.project_engine = YSBProjectEngine()
            if not hasattr(self, "page_engine") or self.page_engine is None:
                self.page_engine = YSBPageEngine(on_dirty=lambda page_idx, kind: self.project_engine.mark_page_dirty(page_idx, kind))
            if not hasattr(self, "undo_manager") or self.undo_manager is None:
                self.undo_manager = YSBUndoManager(self)
            else:
                try:
                    self.undo_manager.bind(self)
                except Exception:
                    pass
            if not hasattr(self, "view_engine") or self.view_engine is None:
                self.view_engine = YSBViewEngine(
                    capture_state=lambda: self.capture_view_state(),
                    apply_state=lambda state: self.apply_view_state(state),
                    on_push_undo=lambda rec, page_idx: self.push_view_state_command_from_record(rec, page_idx=page_idx),
                )
            if not hasattr(self, "layer_engine") or self.layer_engine is None:
                self.layer_engine = YSBLayerEngine(on_push_undo=lambda rec, page_idx: self.push_work_tab_command_from_record(rec, page_idx=page_idx))
            if not hasattr(self, "storage_engine") or self.storage_engine is None:
                self.storage_engine = YSBStorageEngine(project_engine=self.project_engine, page_engine=self.page_engine)
            else:
                try:
                    self.storage_engine.bind(project_engine=self.project_engine, page_engine=self.page_engine)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def get_undo_manager(self):
        """Return the central UndoManager, creating/binding it if needed.

        New feature code should prefer this manager instead of touching
        page_undo_stacks/project_undo_stack or append_*_undo_record directly.
        Stage 1 still delegates to the existing HistoryMixin implementation.
        """
        try:
            if not hasattr(self, "undo_manager") or self.undo_manager is None:
                from ysb.core.undo_manager import YSBUndoManager
                self.undo_manager = YSBUndoManager(self)
            try:
                self.undo_manager.bind(self)
            except Exception:
                pass
            try:
                self.undo_manager.ensure_stack_state()
            except Exception:
                pass
            return self.undo_manager
        except Exception:
            return None

    def get_undo_record_factory(self):
        """Return the central UndoRecordFactory, creating/binding it if needed.

        Stage 2 keeps stack storage in this mixin but moves record construction
        into ysb.core.undo_records so new feature work shares one record shape.
        """
        try:
            if not hasattr(self, "undo_record_factory") or self.undo_record_factory is None:
                from ysb.core.undo_records import UndoRecordFactory
                self.undo_record_factory = UndoRecordFactory(self)
            else:
                try:
                    self.undo_record_factory.owner = self
                except Exception:
                    pass
            return self.undo_record_factory
        except Exception:
            return None

    def maker_global_undo_disabled(self):
        return bool(getattr(self, "maker_text_input_only_undo", True))

    def undo_push_page(self, rec, page_idx=None, clear_redo=True, reason=None):
        if self.maker_global_undo_disabled():
            return False
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.push_page(rec, page_idx=page_idx, clear_redo=clear_redo, reason=reason)
        return self.append_page_undo_record(rec, page_idx=page_idx, clear_redo=clear_redo)

    def undo_push_project(self, rec, clear_redo=True, reason=None):
        if self.maker_global_undo_disabled():
            return False
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.push_project(rec, clear_redo=clear_redo, reason=reason)
        return self.append_project_undo_record(rec, clear_redo=clear_redo)

    def undo_push_view(self, rec, page_idx=None, clear_redo=True, reason=None):
        if self.maker_global_undo_disabled():
            return False
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.push_view(rec, page_idx=page_idx, clear_redo=clear_redo, reason=reason)
        return self.append_page_undo_record(rec, page_idx=page_idx, clear_redo=clear_redo)

    def undo_break_boundary(self, kind="action", name=""):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.apply_boundary(kind=kind, name=name)
        return self.break_undo_chain(kind, name)

    def undo_apply_boundary(self, kind="action", name="", page_idx=None, selected_page_indices=None):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.apply_boundary(kind=kind, name=name, page_idx=page_idx, selected_page_indices=selected_page_indices)
        return self.break_undo_chain(kind, name)

    def undo_clear_current_page(self, reason="page boundary"):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.clear_page(reason=reason)
        return self.clear_current_page_undo_stack(reason)

    def undo_clear_all_pages(self, reason="page boundary"):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.clear_all_pages(reason=reason)
        return self.clear_all_page_undo_stacks(reason)

    def undo_clear_page_redo(self, page_idx=None, reason="redo boundary"):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.clear_page_redo(page_idx=page_idx, reason=reason)
        try:
            target_page = int(page_idx if page_idx is not None else getattr(self, "idx", 0) or 0)
            self.page_redo_stacks[target_page] = []
            if hasattr(self, "page_view_redo_stacks"):
                self.page_view_redo_stacks[target_page] = []
            self.update_undo_redo_buttons()
            return True
        except Exception:
            return False

    def undo_clear_project(self, reason="project boundary"):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.clear_project(reason=reason)
        try:
            self.project_undo_stack = []
            self.project_redo_stack = []
            self.update_undo_redo_buttons()
            return True
        except Exception:
            return False

    def undo_text_checkpoint(self, reason="텍스트 작업"):
        if self.maker_global_undo_disabled():
            return False
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.push_text_checkpoint(reason=reason)
        return self.push_page_text_undo(reason)

    def undo_push_text_line(self, reason="텍스트 라인 변경", page_idx=None, include_masks=False, clear_redo=True):
        if self.maker_global_undo_disabled():
            return False
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.push_text_line(reason=reason, page_idx=page_idx, include_masks=include_masks, clear_redo=clear_redo)
        return self.push_text_line_undo(reason, page_idx=page_idx, include_masks=include_masks)

    def undo_push_ui_state(self, reason="화면 작업", page_idx=None, mode=None, view_state=None, clear_redo=True):
        if self.maker_global_undo_disabled():
            return False
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.push_ui_state(reason=reason, page_idx=page_idx, mode=mode, view_state=view_state, clear_redo=clear_redo)
        rec = self.make_ui_undo_record(reason, page_idx=page_idx, mode=mode)
        if view_state is not None:
            rec["view_state"] = copy.deepcopy(view_state or {})
        return self.append_page_undo_record(rec, page_idx=page_idx, clear_redo=clear_redo)

    def undo_push_paint_marker(self, kind=None, reason=None, page_idx=None, mode=None, clear_redo=True):
        if self.maker_global_undo_disabled():
            return False
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.push_paint_marker(kind=kind, reason=reason, page_idx=page_idx, mode=mode, clear_redo=clear_redo)
        target_page = int(page_idx if page_idx is not None else getattr(self, "idx", 0) or 0)
        rec = {
            "reason": str(reason or ("최종 페인팅" if str(kind or "").lower() == "final_paint" else "마스크 브러시")),
            "page_idx": target_page,
            "mode": int(mode if mode is not None else self.current_mode_index_safe()),
            "paint_history": True,
            "_undo_scope": "page",
        }
        return self.append_page_undo_record(rec, page_idx=target_page, clear_redo=clear_redo)

    def undo_push_paint_record(self, viewer, record, kind=None, reason=None, max_history=80, page_idx=None, mode=None):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.push_paint_view_record(viewer, record, kind=kind, reason=reason, max_history=max_history, page_idx=page_idx, mode=mode)
        try:
            if viewer is None or record is None:
                return False
            viewer.history.append(record)
            while len(viewer.history) > int(max_history or 80):
                viewer.history.pop(0)
            if hasattr(viewer, "redo_history"):
                viewer.redo_history.clear()
            return self.undo_push_paint_marker(kind=kind, reason=reason, page_idx=page_idx, mode=mode)
        except Exception:
            return False

    def undo_clear_paint_redo(self, viewer=None, page_idx=None, reason="paint redo boundary"):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.clear_paint_redo(viewer=viewer, page_idx=page_idx, reason=reason)
        try:
            if viewer is not None and hasattr(viewer, "redo_history"):
                viewer.redo_history.clear()
                return True
        except Exception:
            pass
        return False

    def undo_bind_paint_viewer(self, viewer=None, clear=False):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.bind_paint_viewer(viewer=viewer, clear=bool(clear))
        return False

    def undo_clear_paint_history(self, viewer=None, undo=True, redo=True, reason="paint history clear"):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.clear_paint_history(viewer=viewer, undo=undo, redo=redo, reason=reason)
        try:
            if viewer is not None:
                if undo and hasattr(viewer, "history"):
                    viewer.history.clear()
                if redo and hasattr(viewer, "redo_history"):
                    viewer.redo_history.clear()
                return True
        except Exception:
            pass
        return False

    def undo_paint_stack_lengths(self, viewer=None):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.paint_stack_lengths(viewer=viewer)
        return {
            "paint_undo": len(getattr(viewer, "history", []) or []) if viewer is not None else 0,
            "paint_redo": len(getattr(viewer, "redo_history", []) or []) if viewer is not None else 0,
        }

    def undo_commit_paint_layer(self, kind=None, delay_ms=1200):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.commit_paint_layer(kind=kind, delay_ms=delay_ms)
        return self.schedule_deferred_view_layer_commit("final_paint" if str(kind or "").lower() == "final_paint" else "mask", delay_ms=delay_ms)

    def current_mode_index_safe(self):
        # 쯔꾸르붕이에서는 YSB식 작업탭을 쓰지 않고 프리뷰/최종 모드(4)로 고정한다.
        try:
            return int(getattr(self, "last_mode", 4) or 4)
        except Exception:
            return 4

    def ensure_active_page_session(self):
        """Return the current page workbench.

        Compatibility note: old code used ActivePageSession. The new object is
        PageWorkbench, but it exposes the same dirty fields/reset/mark_dirty API.
        """
        if not self.ensure_page_project_engines():
            return None
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
            mode_idx = self.current_mode_index_safe()
            session = self.page_engine.activate(page_idx, mode_idx, clear_undo_on_page_change=False)
            self.active_page_session = session
            return session
        except Exception:
            return None

    def activate_page_workbench(self, page_idx=None, mode_idx=None, *, clear_undo_on_page_change=True):
        if not self.ensure_page_project_engines():
            return None
        try:
            if page_idx is None:
                page_idx = int(getattr(self, "idx", 0) or 0)
            if mode_idx is None:
                mode_idx = self.current_mode_index_safe()
            session = self.page_engine.activate(int(page_idx), int(mode_idx), clear_undo_on_page_change=clear_undo_on_page_change)
            self.active_page_session = session
            # 기존 스택 이름은 UI의 버튼 상태/핫키와 호환을 위해 남긴다.
            try:
                mgr = self.get_undo_manager()
                if mgr is not None:
                    session.undo_stack = mgr.page_undo_stack(int(page_idx), create=True)
                    session.redo_stack = mgr.page_redo_stack(int(page_idx), create=True)
                else:
                    if hasattr(self, "page_undo_stacks"):
                        session.undo_stack = self.page_undo_stacks.setdefault(int(page_idx), session.undo_stack)
                    if hasattr(self, "page_redo_stacks"):
                        session.redo_stack = self.page_redo_stacks.setdefault(int(page_idx), session.redo_stack)
            except Exception:
                pass
            return session
        except Exception:
            return None

    def mark_active_page_dirty(self, kind):
        kind = str(kind or "")
        if getattr(self, "_suppress_work_cache_dirty", False) or getattr(self, "is_loading_project", False):
            return
        # 보기 상태(줌/스크롤/팬)는 작업 데이터가 아니다.
        # ViewUndo에는 남길 수 있지만 project/page dirty, 체크포인트, 창 제목 갱신으로 번지면
        # 텍스트 드래그/줌 조작마다 저장 루트와 화면 재구성이 깨어난다.
        if kind == "view" or kind.startswith("view"):
            try:
                if hasattr(self, "remember_current_view_state"):
                    self.remember_current_view_state()
                self.audit_boundary_event("PAGE_VIEW_STATE_ONLY", kind=kind, throttle_ms=500)
            except Exception:
                pass
            return
        try:
            self.audit_boundary_event("PAGE_DIRTY", kind=kind, throttle_ms=250, stack=True)
        except Exception:
            pass
        self.ensure_page_project_engines()
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
            if hasattr(self, "page_engine") and self.page_engine is not None:
                self.page_engine.mark_dirty(page_idx, kind)
            elif hasattr(self, "active_page_session") and self.active_page_session is not None:
                self.active_page_session.mark_dirty(kind)
        except Exception:
            pass
        try:
            self.has_unsaved_changes = True
            self.update_window_title()
        except Exception:
            pass

    def mark_project_structure_dirty(self, reason="structure"):
        if getattr(self, "_suppress_work_cache_dirty", False) or getattr(self, "is_loading_project", False):
            return
        self.ensure_page_project_engines()
        try:
            self.project_engine.mark_structure_dirty(reason)
        except Exception:
            pass
        try:
            self.has_unsaved_changes = True
            self.update_window_title()
        except Exception:
            pass

    def begin_page_view_undo(self, reason="화면 이동"):
        session = self.ensure_active_page_session()
        if session is None:
            return None
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
            mode_idx = self.current_mode_index_safe()
            if not hasattr(self, "view_engine") or self.view_engine is None:
                self.ensure_page_project_engines()
            if hasattr(self, "view_engine") and self.view_engine is not None:
                return self.view_engine.begin(page_idx, mode_idx, reason)
        except Exception:
            return None
        return None

    def finish_page_view_undo(self, force=False):
        session = self.ensure_active_page_session()
        if session is None:
            return False
        try:
            if hasattr(self, "view_engine") and self.view_engine is not None:
                suppress_view_dirty = bool(
                    getattr(self, "is_page_loading", False)
                    or getattr(self, "_suppress_view_dirty_during_programmatic_view_change", False)
                    or getattr(self, "_suppress_view_dirty_until", 0) > __import__("time").time()
                )
                now = __import__("time").time()
                last = float(getattr(self, "_last_view_undo_finish_ts", 0.0) or 0.0)
                if (not force) and (now - last) < 0.9:
                    try:
                        if hasattr(self, "remember_current_view_state"):
                            self.remember_current_view_state()
                    except Exception:
                        pass
                    return False
                ok = self.view_engine.finish(force=force)
                if ok:
                    self._last_view_undo_finish_ts = now
                    # ViewUndo는 page-local undo 스택에만 남긴다. project/page dirty는 만들지 않는다.
                    try:
                        if hasattr(self, "remember_current_view_state"):
                            self.remember_current_view_state()
                        self.audit_boundary_event("PAGE_VIEW_UNDO_RECORDED_UI_ONLY", throttle_ms=1200)
                    except Exception:
                        pass
                return bool(ok)
        except Exception:
            return False
        return False

    def flush_pending_page_view_undo_session(self):
        """Force-close pending zoom/pan Command-Diff before Undo/Redo.

        View actions are coalesced by a timer.  If the user presses Ctrl+Z
        before the timer fires, the latest zoom/pan must enter the single
        timeline first; otherwise Undo would skip the visible last action.
        """
        try:
            timer = getattr(self, "_view_undo_coalesce_timer", None)
            if timer is not None:
                timer.stop()
        except Exception:
            pass
        try:
            return bool(self.finish_page_view_undo(force=True))
        except Exception:
            return False

    def begin_coalesced_view_undo(self, reason="화면 이동", delay_ms=450):
        session = self.ensure_active_page_session()
        if session is None:
            return
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
            mode_idx = self.current_mode_index_safe()
            if not hasattr(self, "view_engine") or self.view_engine is None:
                self.ensure_page_project_engines()
            if hasattr(self, "view_engine") and self.view_engine is not None:
                self.view_engine.ensure_pending(page_idx, mode_idx, reason)
            timer = getattr(self, "_view_undo_coalesce_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(lambda: self.finish_page_view_undo(force=False))
                self._view_undo_coalesce_timer = timer
            timer.stop()
            timer.start(max(80, int(delay_ms or 450)))
        except Exception:
            pass

    def on_final_paint_opacity_changed(self, value):
        self.final_paint_opacity = max(1, min(100, int(value)))
        self.log(f"🖌️ 최종 브러시 불투명도: {self.final_paint_opacity}%")

    def set_brush_size(self, value, silent=False):
        """공통 브러시/지우개 두께를 1px 단위로 조절한다."""
        try:
            size = max(1, min(500, int(value)))
        except Exception:
            size = 25
        try:
            if hasattr(self, "view") and self.view is not None:
                self.view.brush_size = size
        except Exception:
            pass
        if hasattr(self, "sb_brush_size"):
            self.sb_brush_size.blockSignals(True)
            try:
                self.sb_brush_size.setValue(size)
            finally:
                self.sb_brush_size.blockSignals(False)
        try:
            self.app_options["brush_size"] = int(size)
            self.save_app_options_cache()
        except Exception:
            pass
        if not silent:
            try:
                self.log(f"🖌️ 브러시 크기: {size}px")
            except Exception:
                pass
        return size

    def on_brush_size_changed(self, value):
        self.set_brush_size(value, silent=False)

    def adjust_brush_size(self, delta):
        current = int(getattr(getattr(self, "view", None), "brush_size", 25) or 25)
        return self.set_brush_size(current + int(delta), silent=False)

    def update_final_paint_option_bar_visibility(self):
        # 최종 브러시 옵션도 상단 공유 옵션바에 편입한다.
        if hasattr(self, "final_paint_option_bar"):
            self.final_paint_option_bar.hide()
        if hasattr(self, "sb_final_paint_opacity"):
            self.sb_final_paint_opacity.blockSignals(True)
            try:
                self.sb_final_paint_opacity.setValue(int(self.final_paint_opacity))
            finally:
                self.sb_final_paint_opacity.blockSignals(False)
        try:
            if hasattr(self, "refresh_shared_option_bar"):
                self.refresh_shared_option_bar()
        except Exception:
            pass

    def update_final_paint_z_order(self):
        """최종 페인팅 레이어는 항상 아래/위 두 장으로 고정한다."""
        below = getattr(self.view, "final_paint_item", None)
        above = getattr(self.view, "final_paint_above_item", None)
        if below is not None:
            below.setZValue(8)
        if above is not None:
            above.setZValue(80)

    def on_final_paint_above_text_toggled(self, checked):
        # 기존에 그린 레이어의 위치는 바꾸지 않는다.
        # 이 토글은 이후 새로 그리는 브러시가 들어갈 레이어만 선택한다.
        old_state = bool(getattr(self, "_last_final_paint_above_text", getattr(self, "final_paint_above_text", False)))
        new_state = bool(checked)
        if (
            old_state != new_state
            and not getattr(self, "_project_undo_restore_lock", False)
            and not getattr(self, "is_loading_project", False)
            and not getattr(self, "is_page_loading", False)
            and not getattr(self, "is_batch_running", False)
        ):
            try:
                rec = self.make_project_undo_record("텍스트 위 페인팅 ON/OFF")
                rec.setdefault("ui_state", self.current_project_ui_state())
                rec["ui_state"]["final_paint_above_text"] = old_state
                self.undo_push_project(rec)
            except Exception:
                pass
        self.final_paint_above_text = new_state
        self._last_final_paint_above_text = new_state
        if hasattr(self, "act_final_paint_above_text"):
            self.act_final_paint_above_text.setText("T↑" if self.final_paint_above_text else "T↓")
        state = "ON" if checked else "OFF"
        self.log(f"🎚️ 새 브러시를 텍스트 위에 그리기: {state}")
        self.auto_save_project()

    def toggle_final_paint_above_text(self):
        if hasattr(self, "act_final_paint_above_text"):
            self.act_final_paint_above_text.toggle()
        else:
            self.on_final_paint_above_text_toggled(not self.final_paint_above_text)

    def adjust_final_paint_opacity(self, delta):
        value = max(1, min(100, int(self.final_paint_opacity) + int(delta)))
        self.final_paint_opacity = value
        if hasattr(self, "sb_final_paint_opacity"):
            self.sb_final_paint_opacity.blockSignals(True)
            try:
                self.sb_final_paint_opacity.setValue(value)
            finally:
                self.sb_final_paint_opacity.blockSignals(False)
        self.log(f"🖌️ 최종 브러시 불투명도: {value}%")

    def final_paint_rgba_from_value(self, value):
        if value is None:
            return None
        try:
            if isinstance(value, (bytes, bytearray)):
                arr = np.frombuffer(value, np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
            elif isinstance(value, np.ndarray):
                img = value.copy()
            else:
                return None

            if img is None:
                return None
            if img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGBA)
            elif img.ndim == 3 and img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
            elif img.ndim == 3 and img.shape[2] == 4:
                # cv2 imdecode는 BGRA이므로 RGBA로 변환
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
            return img
        except Exception:
            return None

    def compose_final_paint_on_bgr(self, base_bgr, paint_value):
        if base_bgr is None:
            return None
        base = base_bgr.copy()
        paint = self.final_paint_rgba_from_value(paint_value)
        if paint is None:
            return base
        h, w = base.shape[:2]
        if paint.shape[0] != h or paint.shape[1] != w:
            paint = cv2.resize(paint, (w, h), interpolation=cv2.INTER_LINEAR)
        alpha = paint[:, :, 3:4].astype(np.float32) / 255.0
        rgb = paint[:, :, :3].astype(np.float32)
        bgr = rgb[:, :, ::-1]
        out = base.astype(np.float32) * (1.0 - alpha) + bgr * alpha
        return np.clip(out, 0, 255).astype(np.uint8)

    def final_paint_layer_bytes_for_current_view(self):
        """현재 최종결과 뷰의 아래/위 페인팅 레이어 PNG bytes를 안전하게 가져온다."""
        try:
            if hasattr(self, "flush_pending_view_layer_commit"):
                self.flush_pending_view_layer_commit(save_after=False)
        except Exception:
            pass

        paint_bytes = None
        paint_above_bytes = None
        try:
            if hasattr(self, "view") and hasattr(self.view, "get_final_paint_png_bytes"):
                paint_bytes = self.view.get_final_paint_png_bytes()
        except Exception:
            paint_bytes = None
        try:
            if hasattr(self, "view") and hasattr(self.view, "get_final_paint_above_png_bytes"):
                paint_above_bytes = self.view.get_final_paint_above_png_bytes()
        except Exception:
            paint_above_bytes = None
        return paint_bytes, paint_above_bytes

    def compose_current_final_background_for_source(self, curr=None, page_idx=None, use_view_layers=True):
        """
        최종결과 탭의 '배경'으로 볼 이미지를 작업용 원본에 쓸 수 있는 BGR 이미지로 만든다.

        - bg_clean이 있으면 인페인팅/클린본 배경을 기준으로 쓴다.
        - 최종 페인팅 레이어가 있으면 배경에 먼저 합친 뒤 쓴다.
        - 텍스트 레이어는 배경으로 굽지 않는다.
        - page_idx를 받으면 현재 페이지가 아니어도 data에 저장된 배경/페인팅으로 처리한다.
        """
        if page_idx is None:
            page_idx = int(getattr(self, "idx", 0) or 0)
        if curr is None:
            curr = self.data.get(page_idx)
        if not curr:
            return None, False, False

        paint_bytes = curr.get('final_paint')
        paint_above_bytes = curr.get('final_paint_above')
        try:
            is_current_page = int(page_idx) == int(getattr(self, "idx", -1) or -1)
        except Exception:
            is_current_page = False
        if use_view_layers and is_current_page:
            view_paint_bytes, view_paint_above_bytes = self.final_paint_layer_bytes_for_current_view()
            if view_paint_bytes is not None:
                paint_bytes = view_paint_bytes
            if view_paint_above_bytes is not None:
                paint_above_bytes = view_paint_above_bytes

        has_paint = paint_bytes is not None or paint_above_bytes is not None
        has_clean_bg = curr.get('bg_clean') is not None

        # 클린본/인페인팅/최종 페인팅 중 하나라도 있어야 '배경을 원본으로 쓰기'의 의미가 있다.
        if not has_clean_bg and not has_paint:
            return None, False, False

        base = self.final_base_image_for_page(page_idx)
        if base is None:
            return None, has_paint, has_clean_bg

        merged = base.copy() if isinstance(base, np.ndarray) else base
        if has_paint:
            merged = self.compose_final_paint_on_bgr(merged, paint_bytes)
            merged = self.compose_final_paint_on_bgr(merged, paint_above_bytes)
        if merged is None:
            return None, has_paint, has_clean_bg
        try:
            merged = self.normalize_image_to_original_size(page_idx, merged)
        except Exception:
            pass
        return merged, has_paint, has_clean_bg

    def make_batch_page_data_undo_record(self, reason="일괄 작업", page_indices=None, page_idx=None):
        factory = self.get_undo_record_factory()
        if factory is not None:
            return factory.make_batch_page_data_undo_record(reason, page_indices=page_indices, page_idx=page_idx)
        return {"reason": str(reason or "일괄 작업"), "page_idx": int(page_idx if page_idx is not None else getattr(self, "idx", 0) or 0), "batch_page_data": {}, "batch_page_indices": [], "_undo_scope": "project"}

    def apply_final_background_as_source_to_page(self, page_idx):
        """한 페이지의 최종결과 배경을 작업용 원본으로 반영한다."""
        curr = self.data.get(page_idx)
        if not curr:
            return "skipped", "페이지 데이터 없음"

        merged, has_paint, has_clean_bg = self.compose_current_final_background_for_source(
            curr, page_idx=page_idx, use_view_layers=(page_idx == int(getattr(self, "idx", -1) or -1))
        )
        if merged is None:
            if not has_paint and not has_clean_bg:
                return "skipped", "원본으로 쓸 최종결과 배경 없음"
            return "failed", "반영할 배경 이미지 생성 실패"

        encoded = self.encode_np_image_to_png_bytes(merged)
        curr['bg_clean'] = encoded if encoded is not None else merged

        # 실제 원본 파일은 건드리지 않고, OCR/인페인팅 기준으로 쓰는 프로젝트 내부 작업용 원본만 갱신한다.
        self.set_working_source_image(curr, merged, page_idx=page_idx)

        if has_paint:
            curr['final_paint'] = None
            curr['final_paint_above'] = None
            try:
                if page_idx == int(getattr(self, "idx", -1) or -1) and hasattr(self.view, "clear_final_paint_layers"):
                    self.view.clear_final_paint_layers()
            except Exception:
                pass
        try:
            if hasattr(self, "mark_page_data_dirty_explicit"):
                self.mark_page_data_dirty_explicit(page_idx, "use_background_as_source")
        except Exception:
            pass
        return "done", "작업용 원본 반영"

    def use_final_background_as_source(self):
        """최종결과 배경(인페인팅/클린본/최종 페인팅 합성본)을 작업용 원본으로 사용한다."""
        if getattr(self, "is_batch_running", False):
            QMessageBox.information(self, self.tr_ui("일괄 작업 중"), self.tr_msg("이미 일괄 작업이 진행 중입니다.\n현재 작업이 끝난 뒤 다시 실행해 주세요."))
            return
        if not getattr(self, "paths", None):
            self.log("⚠️ " + self.tr_ui("작업할 페이지가 없습니다."))
            return

        title = "배경을 원본으로 쓰기"
        selected_indices, selected_label = self.choose_batch_page_indices_for_context(title, "use_background_as_source")
        if selected_indices is None:
            self.log("↩️ " + self.tr_ui("배경을 원본으로 쓰기") + " " + self.tr_ui("취소"))
            return

        try:
            self.commit_current_page_ui_to_data()
        except Exception:
            pass

        current_idx = int(getattr(self, "idx", 0) or 0)
        try:
            current_mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else -1
        except Exception:
            current_mode = -1
        single_current = len(selected_indices or []) == 1 and int(selected_indices[0]) == current_idx

        # 이미지 대량 작업은 Undo 스냅샷/작업 캐시 저장/전체 화면 복귀를 끊는다.
        undo_rec = self.make_batch_page_data_undo_record(title, selected_indices) if single_current else None
        changed = False

        def process_page(page_idx):
            nonlocal changed
            status, message = self.apply_final_background_as_source_to_page(page_idx)
            if str(status).lower() == "done":
                changed = True
            return status, message

        result = self.run_page_queue_batch(
            title,
            "use_background_as_source",
            selected_indices,
            selected_label,
            process_page,
            visual=False,
            cancellable=True,
            restore_page=False,
            save_work_cache=bool(single_current),
        )

        if changed:
            if single_current and undo_rec is not None:
                try:
                    self.undo_push_project(undo_rec)
                except Exception:
                    pass
            else:
                try:
                    self.undo_apply_boundary("use_background_as_source", title, selected_page_indices=selected_indices)
                except Exception:
                    pass
            try:
                self.has_unsaved_changes = True
                self.update_window_title()
            except Exception:
                pass
            try:
                __import__("gc").collect()
            except Exception:
                pass
        # 다중/전체 이미지 작업은 여기서 일반 작업 캐시 저장을 예약하지 않는다.
        # 정식 반영은 사용자가 [프로젝트 저장]을 눌렀을 때 처리한다.
        try:
            if single_current:
                self.mode_chg(current_mode if current_mode >= 0 else self.cb_mode.currentIndex())
            elif current_idx in set(int(i) for i in (selected_indices or [])):
                self.log("ℹ️ 배경을 원본으로 쓰기 완료: 대량 이미지 작업 후 화면 전체 갱신은 생략했습니다. 탭/페이지를 다시 열면 반영됩니다.")
        except Exception:
            pass
        self.log("📌 " + self.tr_ui("최종결과 배경을 원본 탭의 작업용 기준 이미지로 반영했습니다."))

    def apply_final_paint_to_background(self):
        """구버전 액션 호환: Alt+P는 이제 '배경을 원본으로 쓰기'로 동작한다."""
        return self.use_final_background_as_source()

    def final_base_image_for_page(self, page_idx):
        curr = self.data.get(page_idx)
        if not curr:
            return None
        # 쯔꾸르붕이 맵 프리뷰는 생성된 맵 PNG가 최종 표시 기준이다.
        # DB 모드/식질 잔재 정리 과정에서 bg_clean에 오래된 디버그 그리드가 남으면
        # 타일 렌더 PNG가 있어도 final 탭이 그 오래된 bg_clean을 우선 표시할 수 있다.
        # Maker 페이지는 원본 프리뷰 PNG를 우선 사용해서 타일 렌더를 보존한다.
        try:
            meta = curr.get("maker_page") or {}
            if isinstance(meta, dict) and str(meta.get("page_type") or "map") in {"", "map", "common_event"}:
                img = self.get_source_display_image(page_idx)
                if img is not None:
                    return img
        except Exception:
            pass
        if curr.get('bg_clean') is None and curr.get('clean_path'):
            try:
                self.ensure_page_runtime_loaded(page_idx, include_ori=False, include_heavy=True, include_masks=False)
            except Exception:
                pass
        base = self.bg_clean_to_np_image(curr.get('bg_clean'))
        if base is not None:
            return base
        return self.get_source_display_image(page_idx)

    def commit_final_paint_view_to_data(self, log=False):
        if self.is_page_loading or self.is_batch_running:
            return False
        curr = self.data.get(self.idx)
        if not curr or not hasattr(self, "view"):
            return False
        if not hasattr(self.view, "get_final_paint_png_bytes"):
            return False
        curr['final_paint'] = self.view.get_final_paint_png_bytes()
        if hasattr(self.view, "get_final_paint_above_png_bytes"):
            curr['final_paint_above'] = self.view.get_final_paint_above_png_bytes()
        if log:
            self.log("💾 최종 페인팅 저장 반영")
        return True

    def commit_view_mask_to_data(self, log=False):
        if self.is_page_loading or self.is_batch_running:
            return False
        curr = self.data.get(self.idx)
        if not curr or not hasattr(self, "view"):
            return False
        m = self.view.get_mask_np()
        if m is None:
            return False
        mode = self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else -1
        if mode in (2, 3):
            self.set_active_mask(curr, m, mode)
            curr['mask_toggle_enabled'] = self.mask_toggle_enabled
            if log:
                self.log("💾 마스크 저장 반영")
            return True
        return False

    def schedule_deferred_view_layer_commit(self, kind=None, delay_ms=1200):
        """브러시/마스크 레이어 변경을 즉시 PNG/numpy로 인코딩하지 않고 묶어서 저장한다.

        Ctrl+Z/Ctrl+Y나 브러시 release 순간에 on_final_paint_edited()/on_view_mask_edited()를
        바로 호출하면 큰 레이어 전체 PNG 인코딩과 자동저장이 같이 실행되어 매우 느려진다.
        여기서는 dirty 표시와 타이머만 걸고, 실제 data 반영은 잠깐 뒤 또는 저장 직전에 수행한다.
        """
        if (
            getattr(self, "_suppress_work_cache_dirty", False)
            or getattr(self, "is_loading_project", False)
            or not getattr(self, "project_dir", None)
            or not getattr(self, "paths", None)
        ):
            return
        kind = str(kind or "").strip()
        if not kind:
            return
        try:
            pending = getattr(self, "_pending_view_layer_commit_kinds", None)
            if not isinstance(pending, set):
                pending = set()
            pending.add(kind)
            self._pending_view_layer_commit_kinds = pending
            self.has_unsaved_changes = True
            try:
                dirty_kind = "mask" if kind == "mask" else "paint"
                self.mark_active_page_dirty(dirty_kind)
                try:
                    page_idx = int(getattr(self, "idx", 0) or 0)
                    pages = getattr(self, "_checkpoint_dirty_pages", None)
                    if pages is None:
                        pages = set()
                        self._checkpoint_dirty_pages = pages
                    pages.add(page_idx)
                    kinds = getattr(self, "_checkpoint_dirty_kinds", None)
                    if kinds is None:
                        kinds = {}
                        self._checkpoint_dirty_kinds = kinds
                    kinds.setdefault(page_idx, set()).add(dirty_kind)
                except Exception:
                    pass
            except Exception:
                pass
            self.update_window_title()
        except Exception:
            pass
        try:
            timer = getattr(self, "_deferred_view_layer_commit_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(lambda: self.flush_pending_view_layer_commit(save_after=True))
                self._deferred_view_layer_commit_timer = timer
            timer.stop()
            timer.start(max(100, int(delay_ms or 1200)))
        except Exception:
            pass

    def flush_pending_view_layer_commit(self, save_after=False):
        pending = getattr(self, "_pending_view_layer_commit_kinds", set())
        if not pending:
            return False
        try:
            timer = getattr(self, "_deferred_view_layer_commit_timer", None)
            if timer is not None:
                timer.stop()
        except Exception:
            pass
        self._pending_view_layer_commit_kinds = set()
        changed = False
        try:
            if "final_paint" in pending and hasattr(self, "cb_mode") and self.cb_mode.currentIndex() == 4:
                changed = self.commit_final_paint_view_to_data(log=False) or changed
            if "mask" in pending and hasattr(self, "cb_mode") and self.cb_mode.currentIndex() in (2, 3):
                changed = self.commit_view_mask_to_data(log=False) or changed
        except Exception:
            pass
        if changed and save_after:
            try:
                self.schedule_deferred_auto_save_project(200)
            except Exception:
                try:
                    self.auto_save_project()
                except Exception:
                    pass
        return changed

    def on_final_paint_edited(self):
        # 호환용 진입점. 실제 인코딩/저장은 지연 커밋으로 묶는다.
        self.undo_commit_paint_layer("final_paint", delay_ms=1200)


    def create_final_text_at(self, x, y, centered=True):
        """Create a pending manual text box on the Final tab.

        Restores the pre-refactor right-click/text-tool flow. The actual line is
        committed by finish_inline_text_edit(), so normal text-add Undo is kept
        at the point where the user confirms the text.
        """
        try:
            if self.cb_mode.currentIndex() != 4:
                return
        except Exception:
            return
        curr = self.data.get(self.idx)
        if not curr:
            return

        data_list = curr.setdefault('data', [])
        max_id = 0
        for item in data_list:
            try:
                max_id = max(max_id, int(item.get('id', 0)))
            except Exception:
                pass
        new_id = max_id + 1

        w, h = 260, 80
        try:
            font_family = self.cb_font.currentFont().family()
        except Exception:
            font_family = ''
        try:
            font_size = int(self.sb_font_size.value())
        except Exception:
            font_size = 24
        try:
            stroke_width = int(self.sb_strk.value())
        except Exception:
            stroke_width = 2

        temp_data = {
            'id': new_id,
            'text': '',
            'translated_text': '',
            'rect': [int(x - w / 2), int(y - h / 2), w, h] if centered else [int(x), int(y), w, h],
            'use_inpaint': True,
            'font_family': font_family,
            'font_size': font_size,
            'stroke_width': stroke_width,
            'text_color': str(getattr(self, 'default_text_color', None) or '#000000'),
            'stroke_color': str(getattr(self, 'default_stroke_color', None) or '#FFFFFF'),
            'align': getattr(self, 'default_align', 'center'),
            'x_off': 0,
            'y_off': 0,
            'manual_text_rect': True,
            'text_anchor_mode': 'text',
            'force_show': True,
            'pending_new_text': True,
        }

        item = TypesettingItem(
            temp_data,
            font_family,
            font_size,
            stroke_width,
            getattr(self, 'on_text_item_moved', None),
            text_color=temp_data['text_color'],
            stroke_color=temp_data['stroke_color'],
            align=temp_data['align'],
        )
        item.main_window = self
        try:
            self.view.scene.addItem(item)
            item.setZValue(30)
            item.setSelected(True)
        except Exception:
            return
        try:
            self.start_inline_text_edit(item)
        except Exception:
            pass
        try:
            self.log(f"➕ 새 텍스트 영역 생성 대기 (ID: {new_id})")
        except Exception:
            pass

    def on_view_mask_edited(self):
        # 호환용 진입점. 실제 numpy 변환/저장은 지연 커밋으로 묶는다.
        self.undo_commit_paint_layer("mask", delay_ms=1200)


    def flush_pending_log_messages(self):
        pending = list(getattr(self, "_pending_log_messages", []) or [])
        if not pending or not hasattr(self, "log_w") or self.log_w is None:
            return
        self._pending_log_messages = []
        for msg in pending:
            try:
                self.log_w.append(str(msg))
            except Exception:
                pass
        try:
            self.log_w.verticalScrollBar().setValue(self.log_w.verticalScrollBar().maximum())
        except Exception:
            pass

    def log(self, m):
        try:
            m = self.tr_msg(m)
        except Exception:
            pass
        try:
            if not bool(getattr(self, "show_paths_in_log", False)):
                m = hide_paths_in_log_text(m, self.tr_ui("경로 숨김"))
        except Exception:
            pass
        if not hasattr(self, "log_w") or self.log_w is None:
            try:
                self._pending_log_messages.append(str(m))
            except Exception:
                self._pending_log_messages = [str(m)]
            try:
                print(str(m))
            except Exception:
                pass
            return
        try:
            self.log_w.append(str(m))
            self.log_w.verticalScrollBar().setValue(self.log_w.verticalScrollBar().maximum())
        except Exception:
            try:
                print(str(m))
            except Exception:
                pass

    def get_special_shortcuts(self):
        symbol_map = {}
        for key, (_label, symbol) in TEXT_SYMBOLS.items():
            symbol_map[symbol] = self.shortcut_settings.seq("text_" + key)
        return symbol_map

    def get_linebreak_shortcut(self):
        return self.shortcut_settings.seq("text_linebreak")


    def _ocr_language_options_for_provider(self, provider=None):
        provider = str(provider or getattr(getattr(self, "api_settings", None), "selected_ocr_provider", "clova") or "clova")
        if provider == "google_vision":
            return [("영어", "en"), ("일본어", "ja"), ("중국어", "zh"), ("한국어", "ko")]
        if provider == "local_paddle_ocr":
            return [("일본어", "ja"), ("영어", "en"), ("한국어", "ko"), ("중국어", "zh")]
        if provider == "local_manga_ocr":
            return [("일본어", "ja")]
        # CLOVA 기본
        return [("일본어", "ja"), ("중국어", "zh"), ("한국어", "ko")]

    def _current_ocr_language_value(self):
        settings = getattr(self, "api_settings", None)
        provider = str(getattr(settings, "selected_ocr_provider", "clova") or "clova")
        if provider == "google_vision":
            return str(getattr(settings, "google_vision_ocr_language", "en") or "en")
        if provider == "local_paddle_ocr":
            return str(getattr(settings, "local_paddle_ocr_language", "ja") or "ja")
        if provider == "local_manga_ocr":
            return "ja"
        return str(getattr(settings, "clova_ocr_language", "ja") or "ja")

    def refresh_ocr_language_combo(self, save=False):
        combo = getattr(self, "cb_ocr_language", None)
        if combo is None:
            return
        provider = str(getattr(getattr(self, "api_settings", None), "selected_ocr_provider", "clova") or "clova")
        current = self._current_ocr_language_value()
        combo.blockSignals(True)
        try:
            combo.clear()
            for label, value in self._ocr_language_options_for_provider(provider):
                combo.addItem(self.tr_ui(label) if hasattr(self, "tr_ui") else label, value)
            if not self.set_combo_current_data(combo, current):
                combo.setCurrentIndex(0 if combo.count() else -1)
        finally:
            combo.blockSignals(False)

    def on_ocr_language_toolbar_changed(self, *_args):
        combo = getattr(self, "cb_ocr_language", None)
        if combo is None or not hasattr(self, "api_settings"):
            return
        value = str(combo.currentData() or combo.currentText() or "").strip()
        if not value:
            return
        provider = str(getattr(self.api_settings, "selected_ocr_provider", "clova") or "clova")
        if provider == "google_vision":
            self.api_settings.google_vision_ocr_language = value
        elif provider == "local_paddle_ocr":
            self.api_settings.local_paddle_ocr_language = value
        elif provider == "local_manga_ocr":
            value = "ja"
        else:
            self.api_settings.clova_ocr_language = value
        try:
            ApiSettingsStore.save(self.api_settings)
            apply_settings_to_config(self.api_settings)
        except Exception:
            pass

    def _chunk_attr_for_provider(self, provider):
        return {
            "openai": "openai_chunk_size",
            "deepseek": "deepseek_chunk_size",
            "google": "google_translate_chunk_size",
            "gemini": "gemini_chunk_size",
            "gemini_deferred": "gemini_delayed_chunk_size",
            "custom": "custom_translation_chunk_size",
            "lm_studio": "lm_studio_chunk_size",
        }.get(str(provider or "openai"), "openai_chunk_size")

    def on_translation_provider_changed(self, save=True):
        provider = self.cb_trans_provider.currentData() or "openai"
        if save and hasattr(self, "api_settings"):
            try:
                self.api_settings.selected_translation_provider = str(provider)
                ApiSettingsStore.save(self.api_settings)
                apply_settings_to_config(self.api_settings)
            except Exception:
                pass

    def on_translation_chunk_changed(self, value):
        # v2.1.0 이후 상단 툴바 묶음 입력은 제거되었다.
        # 구버전/호환 위젯이 남아 있을 경우만 캐시에 반영한다.
        provider = self.cb_trans_provider.currentData() or "openai"
        self.trans_chunk_sizes[provider] = int(value)

    def get_current_translation_chunk_size(self):
        provider = self.cb_trans_provider.currentData() or "openai"
        attr = self._chunk_attr_for_provider(provider)
        try:
            value = int(getattr(self.api_settings, attr, 0) or 0)
        except Exception:
            value = 0
        if value <= 0:
            value = int(self.trans_chunk_sizes.get(provider, 50))
        return max(1, min(value, 100))

    def open_text_number_width_dialog(self):
        """분석도 노란 텍스트 번호 박스 너비를 즉시 조정한다."""
        dlg = QDialog(self)
        dlg.setWindowTitle("텍스트 넘버 크기 변경")
        dlg.resize(360, 120)

        layout = QVBoxLayout(dlg)
        info = QLabel("분석도에 표시되는 노란 텍스트 번호 박스의 너비값을 조정합니다.")
        info.setWordWrap(True)
        layout.addWidget(info)

        line = QHBoxLayout()
        line.addWidget(QLabel("너비값"))
        spin = QSpinBox()
        spin.setRange(20, 300)
        spin.setValue(int(getattr(self, "analysis_number_box_width", 40)))
        spin.setSuffix(" px")
        spin.setKeyboardTracking(True)
        spin.selectAll()
        line.addWidget(spin, 1)
        layout.addLayout(line)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        old_value = int(getattr(self, "analysis_number_box_width", 40))

        def apply_value(value):
            self.analysis_number_box_width = int(value)
            self.save_app_options_cache()
            if self.cb_mode.currentIndex() == 1:
                self.mode_chg(1)

        spin.valueChanged.connect(apply_value)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        spin.setFocus()
        spin.selectAll()

        result = dlg.exec()
        if result != QDialog.DialogCode.Accepted:
            self.analysis_number_box_width = old_value
            self.save_app_options_cache()
            if self.cb_mode.currentIndex() == 1:
                self.mode_chg(1)
        else:
            apply_value(spin.value())
            self.log(f"🔢 텍스트 넘버 박스 너비 변경: {spin.value()}px")

    def open_shortcut_settings_dialog(self):
        dlg = ShortcutSettingsDialog(self.shortcut_settings, self, show_cache_path=bool(getattr(self, "show_cache_paths_in_settings", False)))
        if not dlg.exec():
            return
        new_settings = dlg.get_settings()
        # 단축키 창에서 비활성화된 기존 단축키 상태를 유지하면서 매크로도 보존한다.
        if not hasattr(new_settings, "macros"):
            new_settings.macros = getattr(self.shortcut_settings, "macros", [])
        self.apply_pending_item_preset_disables_for_shortcut_settings(getattr(dlg, "_pending_disabled_item_presets", set()), new_settings)
        if not self.resolve_item_preset_conflicts_for_new_shortcut_settings(new_settings, parent=self, source_label="단축키"):
            self.log("↩️ 단축키 설정 저장 취소: 개별 글꼴 프리셋 단축키 충돌")
            return
        self.shortcut_settings = new_settings
        ShortcutSettingsStore.save(self.shortcut_settings)
        self.apply_shortcuts()
        self.log("⌨️ 단축키 설정 캐시 저장 완료")

    def open_macro_settings_dialog(self):
        dlg = MacroSettingsDialog(self.shortcut_settings, self)
        if not dlg.exec():
            return
        new_settings = dlg.get_settings()
        self.apply_pending_item_preset_disables_for_shortcut_settings(getattr(dlg, "_pending_disabled_item_presets", set()), new_settings)
        if not self.resolve_item_preset_conflicts_for_new_shortcut_settings(new_settings, parent=self, source_label="매크로"):
            self.log("↩️ 매크로 설정 저장 취소: 개별 글꼴 프리셋 단축키 충돌")
            return
        self.shortcut_settings = new_settings
        ShortcutSettingsStore.save(self.shortcut_settings)
        self.apply_shortcuts()
        self.log("🧩 매크로 설정 캐시 저장 완료")

    def macro_action_requires_undo_boundary(self, key):
        """매크로 전체 Undo를 끊어야 하는 단계인지 판단한다.

        일반 매크로는 실행 전 상태를 1개의 Undo 스냅샷으로 저장해서
        Ctrl+Z 한 번으로 되돌릴 수 있어야 한다. 다만 일괄 작업은 여러
        페이지를 순차 처리하는 확정 작업이므로 매크로 Undo 스냅샷에 넣지
        않고 실행 후 Undo/Redo 체인을 끊는다.
        """
        key = str(key or "")
        return key.startswith("batch_")

    def macro_actions_require_undo_boundary(self, actions):
        return any(self.macro_action_requires_undo_boundary(k) for k in (actions or []))

    def macro_wait_kind_for_key(self, key):
        """매크로에서 다음 단계로 넘어가기 전에 완료 신호를 기다려야 하는 기능."""
        if key in ("work_analyze", "paint_reanalyze"):
            return "analysis"
        if key == "work_inpaint":
            return "inpaint"
        if key.startswith("batch_"):
            return "batch"
        return ""

    def macro_batch_key_for_mode(self, mode):
        if bool(getattr(self, "tktool_phase2_enabled", False)):
            return {"translate": "batch_translate"}.get(str(mode or ""), "")
        return {
            "analyze": "batch_analyze",
            "reanalyze": "batch_reanalyze",
            "translate": "batch_translate",
            "inpaint": "batch_inpaint",
            "export": "batch_export",
        }.get(str(mode or ""), "")

    def macro_collect_batch_result(self, result):
        """매크로 안에서 실행된 일괄 작업 결과를 마지막 요약창용으로 누적한다."""
        if not isinstance(result, dict):
            return False
        if not getattr(self, "macro_running", False):
            return False
        if not bool(getattr(self, "_macro_suppress_batch_summary", False)):
            return False
        try:
            copied = copy.deepcopy(result)
        except Exception:
            copied = dict(result)
        results = getattr(self, "_macro_batch_results", None)
        if not isinstance(results, list):
            results = []
            self._macro_batch_results = results
        results.append(copied)
        try:
            self.log(f"🧩 [Macro] 일괄 결과 누적: {copied.get('title', '일괄 작업')}")
        except Exception:
            pass
        return True

    def macro_batch_summary_text(self, name=None):
        """매크로 안의 여러 일괄 작업 결과를 하나의 요약 문구로 만든다."""
        results = getattr(self, "_macro_batch_results", []) or []
        title = str(name or getattr(self, "macro_current_name", "") or "매크로")
        lines = [f"매크로 완료: {title}", ""]
        if not results:
            lines.append("일괄 작업 결과가 없습니다.")
            return "\n".join(lines)

        total_done = total_skipped = total_failed = total_pending = 0
        for idx, result in enumerate(results, 1):
            rtitle = str(result.get("title") or f"일괄 작업 {idx}")
            total = int(result.get("total") or 0)
            done = len(result.get("done") or [])
            skipped = len(result.get("skipped") or [])
            failed = len(result.get("failed") or [])
            pending = len(result.get("pending") or [])
            cancelled = bool(result.get("cancelled"))
            total_done += done
            total_skipped += skipped
            total_failed += failed
            total_pending += pending
            state = "취소됨" if cancelled else ("완료" if failed <= 0 else "완료(일부 실패)")
            lines.extend([
                f"[{idx}] {rtitle} {state}",
                f"- 대상 {total} / 완료 {done} / 건너뜀 {skipped} / 실패 {failed} / 미처리 {pending}",
            ])
            failed_items = result.get("failed") or []
            if failed_items:
                for item in failed_items[:4]:
                    msg = item.get("message") or "오류"
                    lines.append(f"  - 실패: {item.get('label')}: {msg}")
                if len(failed_items) > 4:
                    lines.append(f"  - 실패 외 {len(failed_items) - 4}개")
            skipped_items = result.get("skipped") or []
            if skipped_items:
                for item in skipped_items[:3]:
                    msg = item.get("message") or "조건 없음"
                    lines.append(f"  - 건너뜀: {item.get('label')}: {msg}")
                if len(skipped_items) > 3:
                    lines.append(f"  - 건너뜀 외 {len(skipped_items) - 3}개")
            lines.append("")

        lines.extend([
            "전체 합계",
            f"- 완료 {total_done} / 건너뜀 {total_skipped} / 실패 {total_failed} / 미처리 {total_pending}",
            "",
            "자세한 내용은 로그에서 확인할 수 있습니다.",
        ])
        return "\n".join(lines)

    def show_macro_batch_summary_if_needed(self, name=None):
        results = getattr(self, "_macro_batch_results", []) or []
        if not results:
            return
        text = self.macro_batch_summary_text(name=name)
        has_failed = any((r.get("failed") or []) for r in results if isinstance(r, dict))
        try:
            if has_failed:
                QMessageBox.warning(self, self.tr_ui("매크로 결과"), self.tr_msg(text))
            else:
                QMessageBox.information(self, self.tr_ui("매크로 결과"), self.tr_msg(text))
        except Exception:
            pass

    def run_macro(self, macro):
        name = str(macro.get("name", "매크로"))
        raw_actions = list(macro.get("actions", []) or [])
        actions = list(raw_actions)
        if bool(getattr(self, "tktool_phase2_enabled", False)) and hasattr(self, "is_tktool_phase2_macro_action_allowed"):
            actions = [k for k in actions if self.is_tktool_phase2_macro_action_allowed(k)]
            removed_count = len(raw_actions) - len(actions)
            if removed_count > 0:
                try:
                    self.log(f"🧩 매크로에서 쯔꾸르붕이 미지원 기능 {removed_count}개를 건너뜀: {name}")
                except Exception:
                    pass
        if not actions:
            self.log(f"⚠️ 매크로 '{name}'에 등록된 기능이 없습니다.")
            return

        if self.macro_running:
            QMessageBox.information(self, self.tr_ui("매크로 실행 중"), self.tr_msg("이미 실행 중인 매크로가 있습니다. 현재 매크로가 끝난 뒤 다시 실행해주세요."))
            return

        has_batch = any(str(k).startswith("batch_") for k in actions)
        macro_batch_page_indices = None
        macro_batch_page_label = ""

        if has_batch:
            if not self.macro_preflight_batch_actions(name, actions):
                self.log(f"↩️ 매크로 취소: {name}")
                return
            try:
                first_ctx = self.macro_batch_preflight_context_for_key(next((str(k) for k in actions if str(k).startswith("batch_")), ""))
                macro_batch_page_indices = list((first_ctx or {}).get("indices") or [])
                macro_batch_page_label = str((first_ctx or {}).get("label") or "")
            except Exception:
                macro_batch_page_indices = None
                macro_batch_page_label = ""

        has_undo_boundary = self.macro_actions_require_undo_boundary(actions)
        macro_undo_record = None
        if not has_undo_boundary:
            # 일반 편집 매크로는 내부 단계별 Undo를 쌓지 않고,
            # 매크로 실행 직전 상태 1개만 저장해서 Ctrl+Z 한 번으로 되돌린다.
            # 이 경로는 일괄 작업이 없는 일반 매크로에서만 사용된다.
            # 페이지 하나 단위의 가벼운 Undo 스냅샷으로 묶어 Ctrl+Z 1회 복원을 지원한다.
            macro_undo_record = self.make_project_undo_record(f"매크로 실행: {name}", full_project=False)

        self.macro_running = True
        self.macro_queue = list(actions)
        self.macro_current = None
        self.macro_waiting_key = None
        self.macro_waiting_kind = None
        self.macro_current_name = name
        self.macro_executed_any = False
        self.macro_has_undo_boundary = has_undo_boundary
        self.macro_undo_record = macro_undo_record
        self._macro_batch_page_indices = list(macro_batch_page_indices or []) if has_batch else None
        self._macro_batch_page_label = str(macro_batch_page_label or "") if has_batch else ""
        self._macro_batch_results = []
        self._macro_suppress_batch_summary = bool(has_batch)
        self._macro_preflight_active = bool(has_batch)
        if has_batch and not isinstance(getattr(self, "_macro_batch_preflight_by_key", None), dict):
            self._macro_batch_preflight_by_key = {}

        self.log(f"🧩 매크로 실행: {name} / {len(self.macro_queue)}단계")
        QTimer.singleShot(0, self.run_next_macro_step)

    def macro_batch_is_busy(self):
        """Return True while any batch worker/state is still active.

        Macro batch steps must be strictly serialized.  Older workers keep an
        ``is_running`` flag for cancel checks, but that flag can remain True
        after the QThread has already emitted ``finished_all``.  Treat the Qt
        thread state as authoritative for QThread based workers; otherwise a
        completed first batch step can make the macro wait forever and never
        start the next registered batch action.
        """
        try:
            if bool(getattr(self, "is_batch_running", False)):
                return True
            if getattr(self, "current_batch_mode", None):
                return True
            for attr in ("bw", "_active_task_worker"):
                worker = getattr(self, attr, None)
                if worker is None:
                    continue
                try:
                    if hasattr(worker, "isRunning"):
                        return bool(worker.isRunning())
                except Exception:
                    return True
                try:
                    if bool(getattr(worker, "is_running", False)):
                        return True
                except Exception:
                    pass
        except Exception:
            return True
        return False

    def macro_continue_after_batch_idle(self, delay_ms=220):
        if not getattr(self, "macro_running", False):
            return
        if self.macro_batch_is_busy():
            QTimer.singleShot(int(delay_ms), lambda: self.macro_continue_after_batch_idle(delay_ms))
            return
        QTimer.singleShot(int(delay_ms), self.run_next_macro_step)

    def run_next_macro_step(self):
        if not self.macro_running:
            return

        if self.macro_batch_is_busy():
            QTimer.singleShot(220, self.run_next_macro_step)
            return

        if not self.macro_queue:
            name = self.macro_current_name or "매크로"
            executed_any = bool(getattr(self, "macro_executed_any", False))
            has_boundary = bool(getattr(self, "macro_has_undo_boundary", False))
            macro_undo_record = getattr(self, "macro_undo_record", None)
            self.log(f"✅ 매크로 완료: {name}")
            try:
                self.show_macro_batch_summary_if_needed(name)
            except Exception as e:
                try:
                    self.log(f"⚠️ 매크로 일괄 결과 요약 표시 실패: {e}")
                except Exception:
                    pass
            self.macro_running = False
            self.macro_current = None
            self.macro_waiting_key = None
            self.macro_waiting_kind = None
            self.macro_current_name = ""
            self.macro_executed_any = False
            self.macro_has_undo_boundary = False
            self.macro_undo_record = None
            self._macro_batch_page_indices = None
            self._macro_batch_page_label = ""
            self._macro_batch_results = []
            self._macro_suppress_batch_summary = False
            self._macro_batch_preflight_by_key = {}
            self.macro_clear_preflight_state()
            if executed_any:
                if has_boundary:
                    self.undo_break_boundary("macro", name)
                elif macro_undo_record:
                    old_allow = getattr(self, "_macro_allow_undo_append", False)
                    self._macro_allow_undo_append = True
                    try:
                        self.undo_push_project(macro_undo_record)
                    finally:
                        self._macro_allow_undo_append = old_allow
                    self.update_undo_redo_buttons()
                    self.log(
                        f"↶ Macro undo snapshot saved: {name}"
                        if getattr(self, "ui_language", LANG_KO) == LANG_EN else
                        f"↶ 매크로 Undo 기록 생성: {name}"
                    )
            return

        key = self.macro_queue.pop(0)
        self.macro_current = key
        action = self.actions.get(key)

        if action is None:
            self.log(f"⚠️ [{self.macro_current_name}] 매크로 기능 없음: {key}")
            QTimer.singleShot(0, self.run_next_macro_step)
            return

        if not action.isEnabled():
            self.log(f"⚠️ [{self.macro_current_name}] 비활성 기능 건너뜀: {action.text()}")
            QTimer.singleShot(0, self.run_next_macro_step)
            return

        wait_kind = self.macro_wait_kind_for_key(key)
        self.macro_waiting_key = key if wait_kind else None
        self.macro_waiting_kind = wait_kind or None

        self.log(f"🧩 [{self.macro_current_name}] 단계 실행: {action.text()}")

        try:
            self.macro_executed_any = True
            action.trigger()
            QApplication.processEvents()
        except Exception as e:
            self.log(f"❌ [{self.macro_current_name}] 매크로 중단: {key} / {e}")
            self.stop_macro_queue()
            return

        if wait_kind:
            # 비동기 작업은 워커가 실제로 시작됐는지 잠깐 뒤 확인한다.
            # 시작되지 않은 경우(취소/데이터 없음/키 없음 등)는 매크로가 무한 대기하지 않도록 다음 단계로 넘긴다.
            QTimer.singleShot(250, lambda k=key, wk=wait_kind: self.verify_macro_wait_started(k, wk))
        else:
            # 동기 작업은 함수가 끝난 뒤 바로 다음 단계.
            QTimer.singleShot(0, self.run_next_macro_step)

    def verify_macro_wait_started(self, key, wait_kind):
        if not self.macro_running or self.macro_waiting_key != key:
            return

        running = False
        try:
            if wait_kind == "analysis":
                running = hasattr(self, "w") and self.w is not None and self.w.isRunning()
            elif wait_kind == "inpaint":
                running = hasattr(self, "iw") and self.iw is not None and self.iw.isRunning()
            elif wait_kind == "batch":
                running = self.macro_batch_is_busy()
        except Exception:
            running = False

        if not running:
            self.log(f"↪️ [{self.macro_current_name}] 단계 대기 생략: 작업이 시작되지 않음 ({key})")
            self.macro_mark_current_step_done(key)

    def macro_mark_current_step_done(self, key=None):
        if not self.macro_running:
            return

        if key and self.macro_waiting_key and key != self.macro_waiting_key:
            return

        if self.macro_waiting_key:
            self.log(f"✅ [{self.macro_current_name}] 단계 완료: {self.macro_waiting_key}")

        wait_kind = self.macro_waiting_kind
        self.macro_waiting_key = None
        self.macro_waiting_kind = None
        self.macro_current = None
        if wait_kind == "batch":
            self.macro_continue_after_batch_idle()
        else:
            QTimer.singleShot(0, self.run_next_macro_step)

    def stop_macro_queue(self):
        self.macro_running = False
        self.macro_queue = []
        self.macro_current = None
        self.macro_waiting_key = None
        self.macro_waiting_kind = None
        self.macro_current_name = ""
        self.macro_has_undo_boundary = False
        self.macro_undo_record = None
        self._macro_batch_page_indices = None
        self._macro_batch_page_label = ""
        self._macro_batch_results = []
        self._macro_suppress_batch_summary = False
        self._macro_batch_preflight_by_key = {}
        self.macro_clear_preflight_state()

    def macro_clear_preflight_state(self):
        for name in (
            "_macro_preflight_active",
            "_macro_preflight_ocr_regions_confirmed",
            "_macro_preflight_inpaint_resize_checked",
            "_macro_preflight_inpaint_resize_policy",
            "_macro_preflight_export_options_confirmed",
            "_macro_batch_preflight_by_key",
        ):
            try:
                if hasattr(self, name):
                    delattr(self, name)
            except Exception:
                try:
                    setattr(self, name, None)
                except Exception:
                    pass

    def macro_batch_mode_for_key(self, key):
        if bool(getattr(self, "tktool_phase2_enabled", False)):
            return {"batch_translate": "translate"}.get(str(key or ""), "")
        return {
            "batch_analyze": "analyze",
            "batch_reanalyze": "reanalyze",
            "batch_translate": "translate",
            "batch_inpaint": "inpaint",
            "batch_export": "export",
            "batch_refresh": "refresh",
        }.get(str(key or ""), "")

    def macro_batch_title_for_key(self, key):
        if bool(getattr(self, "tktool_phase2_enabled", False)):
            return {"batch_translate": "일괄 번역"}.get(str(key or ""), str(key or "일괄 작업"))
        return {
            "batch_analyze": "일괄 분석",
            "batch_reanalyze": "일괄 재분석",
            "batch_translate": "일괄 번역",
            "batch_inpaint": "일괄 인페인팅",
            "batch_export": "일괄 출력",
            "batch_refresh": "일괄 텍스트 갱신",
        }.get(str(key or ""), str(key or "일괄 작업"))

    def macro_batch_preflight_context_for_key(self, key):
        table = getattr(self, "_macro_batch_preflight_by_key", None)
        if not isinstance(table, dict):
            return {}
        ctx = table.get(str(key or ""))
        return ctx if isinstance(ctx, dict) else {}

    def macro_batch_preflight_context_for_mode(self, mode):
        key = str(getattr(self, "macro_current", "") or "")
        if not key.startswith("batch_"):
            key = self.macro_batch_key_for_mode(mode)
        return self.macro_batch_preflight_context_for_key(key)

    def macro_preflight_batch_actions(self, macro_name, actions, page_indices=None, page_label=None):
        """매크로 안의 일괄 작업 확인창을 실제 실행 전에 모두 처리한다.

        원칙:
        1) 매크로 안에 일괄 단계가 여러 개 있어도 페이지 선택은 가장 처음 1회만 받는다.
        2) 그 1회 선택한 페이지 범위를 모든 일괄 단계가 공유한다.
        3) 페이지 범위 확정 뒤 단계별 추가 확인(OCR 영역/인페인팅 리사이즈/출력 옵션)을 받는다.
        4) 실행 중에는 미리 확정한 값을 재사용해서 확인창이 다시 뜨지 않는다.
        5) 매크로 큐는 등록 순서대로 "작업 단위"로 전체 페이지를 한 바퀴씩 돈다.
        """
        keys = [str(k or "") for k in (actions or []) if str(k or "").startswith("batch_")]
        if bool(getattr(self, "tktool_phase2_enabled", False)) and hasattr(self, "is_tktool_phase2_macro_action_allowed"):
            keys = [k for k in keys if self.is_tktool_phase2_macro_action_allowed(k)]
        self.macro_clear_preflight_state()
        self._macro_preflight_active = True
        self._macro_preflight_ocr_regions_confirmed = False
        self._macro_preflight_inpaint_resize_checked = False
        self._macro_preflight_inpaint_resize_policy = None
        self._macro_preflight_export_options_confirmed = False
        self._macro_batch_preflight_by_key = {}

        if not keys:
            return True

        try:
            self.log(f"🧩 매크로 사전 확인 시작: {macro_name} / {len(keys)}개 일괄 단계")
        except Exception:
            pass

        # 등록 순서는 유지하되, 같은 종류가 여러 번 들어간 경우 사전 확인은 1회만 한다.
        seen = set()
        ordered_keys = []
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            ordered_keys.append(key)

        # 페이지 선택은 매크로 전체에서 가장 먼저 1회만 받는다.
        # 사용자가 처음 지정한 페이지 조건을 모든 일괄 단계가 공유해야 한다.
        try:
            if page_indices is not None:
                shared_indices = list(page_indices or [])
                shared_label = str(page_label or self.tr_ui("전체 페이지"))
            else:
                shared_indices, shared_label = self.choose_batch_page_indices(
                    f"매크로 일괄 페이지 선택 - {macro_name}",
                    "macro",
                )
        except Exception as e:
            try:
                self.log(f"⚠️ 매크로 페이지 선택 실패: {e}")
            except Exception:
                pass
            return False
        if shared_indices is None:
            return False

        valid_shared = []
        seen_idx = set()
        for raw in shared_indices or []:
            try:
                i = int(raw)
            except Exception:
                continue
            if 0 <= i < len(getattr(self, "paths", []) or []) and i not in seen_idx:
                valid_shared.append(i)
                seen_idx.add(i)
        if not valid_shared:
            try:
                self.log("⚠️ 매크로 일괄 페이지 선택 실패: 작업할 페이지가 없습니다.")
            except Exception:
                pass
            return False

        shared_label = str(shared_label or self.tr_ui("전체 페이지"))
        self._macro_batch_page_indices = list(valid_shared)
        self._macro_batch_page_label = shared_label
        try:
            self.log(f"🧩 매크로 공통 페이지 선택: {shared_label} / {len(valid_shared)}페이지")
        except Exception:
            pass

        for key in ordered_keys:
            mode = self.macro_batch_mode_for_key(key)
            title = self.macro_batch_title_for_key(key)
            ctx = {
                "key": key,
                "mode": mode,
                "title": title,
                "indices": list(valid_shared),
                "label": shared_label,
                "shared_page_selection": True,
            }
            self._macro_batch_preflight_by_key[key] = ctx
            try:
                self.log(f"🧩 매크로 단계 페이지 공유: {title} / {shared_label} / {len(valid_shared)}페이지")
            except Exception:
                pass

            if key in ("batch_analyze", "batch_reanalyze"):
                try:
                    if not self.confirm_ocr_analysis_regions_before_run(valid_shared):
                        return False
                    ctx["ocr_regions_confirmed"] = True
                    self._macro_preflight_ocr_regions_confirmed = True
                except Exception as e:
                    try:
                        self.log(f"⚠️ 매크로 OCR 분석 영역 확인 실패: {e}")
                    except Exception:
                        pass
                    return False

            if key == "batch_inpaint":
                try:
                    old_policy = getattr(self, "_batch_inpaint_resize_policy", None)
                    self._batch_inpaint_resize_policy = None
                    if not self._ask_batch_inpaint_resize(valid_shared):
                        self._batch_inpaint_resize_policy = old_policy
                        return False
                    policy = getattr(self, "_batch_inpaint_resize_policy", None)
                    ctx["inpaint_resize_checked"] = True
                    ctx["inpaint_resize_policy"] = copy.deepcopy(policy) if isinstance(policy, dict) else None
                    self._macro_preflight_inpaint_resize_policy = copy.deepcopy(ctx["inpaint_resize_policy"]) if isinstance(ctx.get("inpaint_resize_policy"), dict) else None
                    self._macro_preflight_inpaint_resize_checked = True
                    self._batch_inpaint_resize_policy = old_policy
                    try:
                        self.log("🧩 매크로 인페인팅 리사이즈 정책 사전 확정")
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        self.log(f"⚠️ 매크로 인페인팅 리사이즈 확인 실패: {e}")
                    except Exception:
                        pass
                    return False

            if key == "batch_export":
                try:
                    if not self.open_output_options_dialog():
                        return False
                    ctx["export_options_confirmed"] = True
                    self._macro_preflight_export_options_confirmed = True
                    try:
                        self.log("🧩 매크로 출력 옵션 사전 확정")
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        self.log(f"⚠️ 매크로 출력 옵션 확인 실패: {e}")
                    except Exception:
                        pass
                    return False

        try:
            self.log(f"✅ 매크로 사전 확인 완료: {macro_name}")
        except Exception:
            pass
        return True

    def text_transform_runtime_keys(self):
        return ("_transform_mode", "_skew_mode", "_trapezoid_mode", "_arc_mode")

    def strip_text_transform_runtime_flags(self, data_item):
        """텍스트 변형 모드 플래그는 저장/Undo 대상이 아닌 런타임 UI 상태다."""
        if isinstance(data_item, dict):
            for key in self.text_transform_runtime_keys():
                data_item.pop(key, None)
        return data_item

    def strip_text_transform_runtime_flags_from_snapshot(self, state):
        if isinstance(state, dict):
            data_list = state.get("data")
            if isinstance(data_list, list):
                for item in data_list:
                    self.strip_text_transform_runtime_flags(item)
        return state

    def force_update_final_scene_region(self, rect=None):
        """변형/Undo 뒤 Qt viewport에 남는 이전 bounding rect 잔상을 강제로 무효화한다."""
        scene = None
        try:
            scene = self._safe_graphics_scene()
        except Exception:
            scene = None
        if scene is None:
            return
        try:
            if rect is None or rect.isNull():
                scene.update()
            else:
                scene.update(QRectF(rect).adjusted(-24, -24, 24, 24))
        except Exception:
            pass
        try:
            view = getattr(self, "view", None)
            if view is not None and view.viewport() is not None:
                view.viewport().update()
        except Exception:
            pass

    def current_transform_data_item(self):
        curr = self.data.get(self.idx)
        if not curr:
            return None
        for d in curr.get('data', []) or []:
            if d.get('_transform_mode', False) or d.get('_skew_mode', False) or d.get('_trapezoid_mode', False) or d.get('_arc_mode', False):
                return d
        return None

    def is_text_transform_active(self):
        return self.current_transform_data_item() is not None

    def view_state_key(self, page_idx=None, mode=None):
        if page_idx is None:
            page_idx = getattr(self, "idx", 0)
        if mode is None:
            try:
                mode = self.cb_mode.currentIndex()
            except Exception:
                mode = getattr(self, "last_mode", 0)
        return f"{int(page_idx)}:{int(mode)}"

    def capture_view_state(self):
        """현재 뷰의 확대율/이동 위치를 JSON 저장 가능한 값으로 캡처한다."""
        try:
            tr = self.view.transform()
            return {
                "transform": [
                    float(tr.m11()), float(tr.m12()), float(tr.m13()),
                    float(tr.m21()), float(tr.m22()), float(tr.m23()),
                    float(tr.m31()), float(tr.m32()), float(tr.m33()),
                ],
                "h_scroll": int(self.view.horizontalScrollBar().value()),
                "v_scroll": int(self.view.verticalScrollBar().value()),
            }
        except Exception:
            return {}

    def apply_view_state(self, state):
        if getattr(self, "_app_is_closing", False):
            return False
        if not isinstance(state, dict) or not state:
            return False
        vals = state.get("transform") or []
        ve = getattr(self, "view_engine", None)
        old_suppress = getattr(ve, "suppress", False) if ve is not None else False
        if ve is not None:
            ve.suppress = True
        try:
            if len(vals) == 9:
                self.view.setTransform(QTransform(*[float(x) for x in vals]))
            if "h_scroll" in state:
                self.view.horizontalScrollBar().setValue(int(state.get("h_scroll") or 0))
            if "v_scroll" in state:
                self.view.verticalScrollBar().setValue(int(state.get("v_scroll") or 0))
            try:
                if ve is not None:
                    ve.remember(int(getattr(self, "idx", 0) or 0), self.current_mode_index_safe(), state)
            except Exception:
                pass
            return True
        except Exception:
            return False
        finally:
            if ve is not None:
                ve.suppress = old_suppress

    def restore_current_view_state_later(self, page_idx=None, mode=None):
        try:
            key = self.view_state_key(self.idx if page_idx is None else page_idx, self.cb_mode.currentIndex() if mode is None else mode)
            state = copy.deepcopy((getattr(self, "project_ui_view_states", {}) or {}).get(key) or {})
            if not state:
                return False
            self.apply_view_state(state)
            QTimer.singleShot(0, lambda st=copy.deepcopy(state): self.apply_view_state(st))
            QTimer.singleShot(30, lambda st=copy.deepcopy(state): self.apply_view_state(st))
            QTimer.singleShot(80, lambda st=copy.deepcopy(state): self.apply_view_state(st))
            return True
        except Exception:
            return False

    def remember_current_view_state(self):
        if not hasattr(self, "view") or not hasattr(self, "cb_mode"):
            return
        try:
            key = self.view_state_key(self.idx, self.cb_mode.currentIndex())
            state = self.capture_view_state()
            self.project_ui_view_states[key] = state
            try:
                if hasattr(self, "view_engine") and self.view_engine is not None:
                    self.view_engine.remember(int(self.idx), int(self.cb_mode.currentIndex()), state)
            except Exception:
                pass
        except Exception:
            pass

    def restore_project_ui_state(self, ui_state, refresh=False):
        if not isinstance(ui_state, dict):
            return False
        old_restore = getattr(self, "_project_undo_restore_lock", False)
        self._project_undo_restore_lock = True
        try:
            if hasattr(self, "cb_show_final_text") and "show_final_text" in ui_state:
                self.cb_show_final_text.blockSignals(True)
                try:
                    self.cb_show_final_text.setChecked(bool(ui_state.get("show_final_text")))
                    self._last_show_final_text_checked = bool(ui_state.get("show_final_text"))
                finally:
                    self.cb_show_final_text.blockSignals(False)
            if hasattr(self, "act_final_paint_above_text") and "final_paint_above_text" in ui_state:
                val = bool(ui_state.get("final_paint_above_text"))
                self.final_paint_above_text = val
                self.act_final_paint_above_text.blockSignals(True)
                try:
                    self.act_final_paint_above_text.setChecked(val)
                    self.act_final_paint_above_text.setText("T↑" if val else "T↓")
                    self._last_final_paint_above_text = val
                finally:
                    self.act_final_paint_above_text.blockSignals(False)
            if isinstance(ui_state.get("view_states"), dict):
                self.project_ui_view_states = copy.deepcopy(ui_state.get("view_states") or {})
            try:
                pending = ui_state.get("maker_pending_writeback_pages", [])
                self._maker_game_writeback_dirty_pages = {int(x) for x in list(pending or [])}
                reasons = ui_state.get("maker_pending_writeback_reasons", [])
                self._maker_game_writeback_dirty_reasons = {str(x) for x in list(reasons or [])}
                if hasattr(self, "sync_maker_writeback_ui_state"):
                    self.sync_maker_writeback_ui_state()
            except Exception:
                pass
            if refresh and hasattr(self, "cb_mode") and self.cb_mode.currentIndex() == 4:
                old_suppress = getattr(self, "_suppress_mode_undo", False)
                self._suppress_mode_undo = True
                try:
                    self.mode_chg(4)
                finally:
                    self._suppress_mode_undo = old_suppress
            return True
        finally:
            self._project_undo_restore_lock = old_restore

    def current_project_ui_state(self):
        self.remember_current_view_state()
        try:
            mode = int(self.cb_mode.currentIndex())
        except Exception:
            mode = int(getattr(self, "last_mode", 0) or 0)
        state = {
            "current_mode": mode,
            "view_states": copy.deepcopy(getattr(self, "project_ui_view_states", {}) or {}),
            "show_final_text": bool(self.cb_show_final_text.isChecked()) if hasattr(self, "cb_show_final_text") else True,
            "final_paint_above_text": bool(getattr(self, "final_paint_above_text", False)),
            "maker_pending_writeback_pages": sorted(int(x) for x in (getattr(self, "_maker_game_writeback_dirty_pages", set()) or set())),
            "maker_pending_writeback_reasons": sorted(str(x) for x in (getattr(self, "_maker_game_writeback_dirty_reasons", set()) or set())),
        }
        # Preserve Maker-project metadata that was loaded from project.json.
        # current_project_ui_state() is called on normal saves; without this,
        # project_kind/maker_import/maker_preview_settings would disappear after
        # the first save even though the pages still exist.
        try:
            old_state = getattr(getattr(self, "project_store", None), "ui_state", {}) or {}
            if isinstance(old_state, dict):
                for key in ("project_kind", "maker_import", "maker_preview_settings"):
                    if key in old_state and key not in state:
                        state[key] = copy.deepcopy(old_state.get(key))
        except Exception:
            pass
        return state

    def save_project_store(self, store, paths=None, data=None, idx=None, force_full=None):
        try:
            self.audit_boundary_event(
                "PROJECT_STORE_SAVE_ENTER",
                explicit_save_depth=getattr(getattr(self, "project_engine", None), "explicit_save_depth", None),
                paths_override=paths is not None,
                data_override=data is not None,
                store_is_project=store is getattr(self, "project_store", None),
                stack=True,
            )
        except Exception:
            pass
        """ProjectStore.save() 호출 전에 UI 상태와 저장 계획을 같이 넣는 공통 저장 함수.

        F단계 저장 엔진 정리:
        - 프로젝트 구조가 바뀌지 않은 저장은 dirty page만 다시 빌드한다.
        - clean page는 기존 project.json page entry를 그대로 재사용한다.
        - 저장 계획은 ProjectEngine/PageEngine dirty 상태만 본다.
        - PageEngine 내부 편집 도중에는 이 함수가 호출되지 않는 것이 원칙이고,
          명시 저장/자동저장 flush에서만 ProjectStore.save()까지 내려온다.
        """
        if store is None:
            return False
        self.ensure_page_project_engines()
        try:
            store.ui_state = self.current_project_ui_state()
        except Exception:
            store.ui_state = getattr(store, "ui_state", {}) or {}
        try:
            store.clean_image_format = self.current_clean_image_format() if hasattr(self, "current_clean_image_format") else getattr(self, "clean_image_format", "png")
            store.clean_image_quality = self.current_clean_image_quality() if hasattr(self, "current_clean_image_quality") else getattr(self, "clean_image_quality", 95)
        except Exception:
            try:
                store.clean_image_format = getattr(self, "clean_image_format", "png")
                store.clean_image_quality = getattr(self, "clean_image_quality", 95)
            except Exception:
                pass

        plan = None
        applied_plan = False
        try:
            se = getattr(self, "storage_engine", None)
            pe = getattr(self, "project_engine", None)
            target_paths = paths if paths is not None else self.paths
            target_data = data if data is not None else self.data
            # Save As/new explicit overrides still need a full-safe save.
            # Work cache after it has been created can use the same dirty-page plan as the main project.
            # This prevents image-heavy batch jobs such as clean-background import from rebuilding
            # every page at each recovery-cache checkpoint.
            if force_full is None:
                force_full_save = bool(paths is not None or data is not None)
            else:
                force_full_save = bool(force_full)
            if se is not None:
                plan = se.make_plan(force_full=force_full_save, reason="save_project_store")
                # If no page is dirty and only current_index/ui_state changed, reuse all page entries.
                se.apply_plan_to_store(store, plan)
                applied_plan = True
        except Exception:
            plan = None
            applied_plan = False

        old_save_yield_callback = getattr(store, "_save_yield_callback", None)
        old_cleanup_duplicate_masks_on_save = getattr(store, "_cleanup_duplicate_masks_on_save", None)

        # v2.4.0 안정화: ProjectStore.save()는 자동저장/작업 캐시/일괄 작업 후처리에서도
        # 공통으로 호출된다. 여기서 진행창을 페이지 단위로 갱신하면 일괄 분석/번역 중에도
        # "1~끝페이지 저장 진행"이 매번 노출되어 기본 작업 흐름이 오염된다.
        # 따라서 store.save() 내부 진행률 노출은 기본적으로 끄고, 사용자가 직접 호출한
        # YSBG 패키징 단계(package_project)의 진행창만 화면에 보이게 둔다.
        enable_store_save_progress = False
        enable_mask_cleanup_on_store_save = False

        def _store_save_yield(phase, current, total):
            try:
                total_pages = int(total or len((paths if paths is not None else self.paths) or []) or 0)
                current_page = int(current or 0)
                phase_text = str(phase or "")
                if "reuse" in phase_text:
                    work_text = f"기존 페이지 항목 재사용 중: {current_page}/{total_pages}페이지"
                elif "page_done" in phase_text:
                    work_text = f"변경/페이지 데이터 저장 중: {current_page}/{total_pages}페이지"
                elif "pages_done" in phase_text:
                    work_text = f"페이지 데이터 저장 완료: {current_page}/{total_pages}페이지"
                elif "project_json" in phase_text:
                    work_text = "프로젝트 JSON을 쓰는 중입니다..."
                elif "manifest" in phase_text:
                    work_text = "프로젝트 manifest를 쓰는 중입니다..."
                else:
                    work_text = "작업 폴더 저장을 준비하는 중입니다..."
                overlay = getattr(self, "_task_progress_overlay", None)
                if overlay is not None and overlay.isVisible():
                    try:
                        self.update_task_progress_overlay(
                            current=min(max(current_page, 0), total_pages),
                            total=max(total_pages, 1),
                            detail=f"""전체 페이지: {total_pages}개
저장 진행: {min(max(current_page, 0), total_pages)}/{total_pages}
현재 작업: {work_text}""",
                        )
                    except Exception:
                        pass
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            except Exception:
                try:
                    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                except Exception:
                    pass

        try:
            try:
                if enable_store_save_progress:
                    store._save_yield_callback = _store_save_yield
                elif hasattr(store, "_save_yield_callback"):
                    # 이전 디버그/진단 패치가 남긴 콜백이 자동저장/일괄 작업에 끼어들지 않게 방어한다.
                    delattr(store, "_save_yield_callback")
            except Exception:
                pass
            try:
                store._cleanup_duplicate_masks_on_save = bool(enable_mask_cleanup_on_store_save)
            except Exception:
                pass
            store.save(paths if paths is not None else self.paths, data if data is not None else self.data, self.idx if idx is None else idx)
            return True
        finally:
            try:
                if old_save_yield_callback is not None:
                    store._save_yield_callback = old_save_yield_callback
                elif hasattr(store, "_save_yield_callback"):
                    delattr(store, "_save_yield_callback")
            except Exception:
                pass
            try:
                if old_cleanup_duplicate_masks_on_save is not None:
                    store._cleanup_duplicate_masks_on_save = old_cleanup_duplicate_masks_on_save
                elif hasattr(store, "_cleanup_duplicate_masks_on_save"):
                    delattr(store, "_cleanup_duplicate_masks_on_save")
            except Exception:
                pass
            try:
                if applied_plan and hasattr(self, "storage_engine") and self.storage_engine is not None:
                    self.storage_engine.clear_plan_on_store(store)
            except Exception:
                pass

    def undo_boundary_log_text(self, event, kind, name=""):
        """Undo 경계 생성/차단 로그 문구를 현재 UI 언어에 맞춰 돌려준다."""
        kind = str(kind or "action")
        name = str(name or "").strip()
        is_en = getattr(self, "ui_language", LANG_KO) == LANG_EN

        boundary_labels = {
            "macro": ("매크로", "macro"),
            "font_preset": ("글꼴 프리셋", "font preset"),
            "analysis": ("분석 결과", "analysis results"),
            "reanalyze": ("텍스트 마스크 재분석 결과", "text mask re-analysis results"),
            "translation": ("번역 결과", "translation results"),
            "inpaint": ("인페인팅 결과", "inpainting results"),
            "batch_analysis": ("일괄 분석 결과", "batch analysis results"),
            "batch_reanalysis": ("일괄 재분석 결과", "batch re-analysis results"),
            "batch_translation": ("일괄 번역 결과", "batch translation results"),
            "batch_inpaint": ("일괄 인페인팅 결과", "batch inpainting results"),
        }
        ko_label, en_label = boundary_labels.get(kind, ("작업", "action"))
        ko_name = name or ko_label
        en_name = name or en_label

        if kind == "macro":
            if event == "set":
                return (
                    f"🧱 Undo boundary set: macro '{en_name}' was executed, so previous undo history was cleared."
                    if is_en else
                    f"🧱 Undo 경계 생성: 매크로 '{ko_name}' 실행으로 이전 되돌리기 내역을 끊었습니다."
                )
            return (
                f"⛔ Cannot undo: macro '{en_name}' created an undo boundary. To prevent state conflicts, actions before that point cannot be restored."
                if is_en else
                f"⛔ 되돌릴 수 없습니다: 매크로 '{ko_name}' 실행 이후 Undo 경계가 생겼습니다. 상태 꼬임 방지를 위해 그 이전으로는 돌아가지 않습니다."
            )

        api_boundary_kinds = {
            "analysis", "reanalyze", "translation", "inpaint",
            "batch_analysis", "batch_reanalysis", "batch_translation", "batch_inpaint",
        }
        if kind in api_boundary_kinds:
            if event == "set":
                return (
                    f"🧱 Undo boundary set: {en_label} were applied, so previous undo history was cleared."
                    if is_en else
                    f"🧱 Undo 경계 생성: {ko_label} 반영으로 이전 되돌리기 내역을 끊었습니다."
                )
            return (
                f"⛔ Cannot undo: {en_label} created an undo boundary. To prevent state conflicts, actions before that point cannot be restored."
                if is_en else
                f"⛔ 되돌릴 수 없습니다: {ko_label} 반영 이후 Undo 경계가 생겼습니다. 상태 꼬임 방지를 위해 그 이전으로는 돌아가지 않습니다."
            )

        if event == "set":
            return (
                "🧱 Undo boundary set: previous undo history was cleared to prevent state conflicts."
                if is_en else
                "🧱 Undo 경계 생성: 상태 꼬임 방지를 위해 이전 되돌리기 내역을 끊었습니다."
            )
        return (
            "⛔ Cannot undo: an undo boundary was created. To prevent state conflicts, actions before that point cannot be restored."
            if is_en else
            "⛔ 되돌릴 수 없습니다: Undo 경계가 생겼습니다. 상태 꼬임 방지를 위해 그 이전으로는 돌아가지 않습니다."
        )

    def break_undo_chain(self, kind="action", name=""):
        """분석/번역/인페인팅 같은 확정 작업 뒤에 과거 Undo/Redo를 모두 차단한다."""
        self.undo_boundary = {"kind": str(kind or "action"), "name": str(name or "")}
        mgr = self.get_undo_manager()
        try:
            if mgr is not None:
                mgr.clear_project_storage(undo=True, redo=True, update=False)
            else:
                self.project_undo_stack = []
                self.project_redo_stack = []
        except Exception:
            try:
                self.project_undo_stack.clear()
                self.project_redo_stack.clear()
            except Exception:
                pass
        try:
            self.clear_all_page_undo_stacks(reason=f"undo boundary: {kind}")
        except Exception:
            try:
                if mgr is not None:
                    mgr.clear_all_page_storage(update=False)
                else:
                    self.page_undo_stacks.clear()
                    self.page_redo_stacks.clear()
                    self.page_text_undo_stacks = self.page_undo_stacks
            except Exception:
                pass
            try:
                if getattr(self, "view", None) is not None:
                    if hasattr(self.view, "history"):
                        self.view.history.clear()
                    if hasattr(self.view, "redo_history"):
                        self.view.redo_history.clear()
            except Exception:
                pass
        self._deferred_undo_records = {}
        self.log(self.undo_boundary_log_text("set", kind, name))
        self.update_undo_redo_buttons()
        return True

    def log_undo_boundary_blocked(self):
        boundary = getattr(self, "undo_boundary", None)
        if not boundary:
            return False
        self.log(self.undo_boundary_log_text("blocked", boundary.get("kind"), boundary.get("name")))
        return True

    def set_work_mode_without_undo(self, mode):
        try:
            mode = int(mode)
        except Exception:
            mode = 0
        if not hasattr(self, "cb_mode") or self.cb_mode.count() <= 0:
            self.last_mode = mode
            self._current_work_mode = mode
            return
        mode = max(0, min(mode, self.cb_mode.count() - 1))
        self.cb_mode.blockSignals(True)
        try:
            self.cb_mode.setCurrentIndex(mode)
        finally:
            self.cb_mode.blockSignals(False)
        self.last_mode = mode
        self._current_work_mode = mode

    def copy_page_data_for_undo(self, page_idx=None):
        if page_idx is None:
            page_idx = self.idx
        curr = self.data.get(page_idx)
        if not isinstance(curr, dict):
            return None
        out = {}
        for k, v in curr.items():
            if k == 'ori':
                out[k] = v
            elif isinstance(v, np.ndarray):
                out[k] = v.copy()
            else:
                out[k] = copy.deepcopy(v)
        return out

    def copy_project_data_for_undo(self):
        """일괄 텍스트 작업용 전체 프로젝트 스냅샷.

        번역문 일괄 불러오기/일괄 지우기/텍스트 정리처럼 여러 페이지를 한 번에
        바꾸는 작업은 현재 페이지만 저장하면 Ctrl+Z 복원이 깨진다.
        이 경우 변경 전 self.data 전체를 저장해 하나의 Undo 단계로 되돌린다.
        """
        out = {}
        try:
            keys = list((self.data or {}).keys())
        except Exception:
            keys = []
        for page_idx in keys:
            page_data = self.copy_page_data_for_undo(page_idx)
            if page_data is not None:
                out[page_idx] = page_data
        return out

    def ensure_page_undo_state(self):
        mgr = self.get_undo_manager()
        if mgr is not None:
            return mgr.ensure_stack_state()
        if not hasattr(self, "page_undo_stacks") or self.page_undo_stacks is None:
            self.page_undo_stacks = {}
        if not hasattr(self, "page_redo_stacks") or self.page_redo_stacks is None:
            self.page_redo_stacks = {}
        if not hasattr(self, "page_view_undo_stacks") or self.page_view_undo_stacks is None:
            self.page_view_undo_stacks = {}
        if not hasattr(self, "page_view_redo_stacks") or self.page_view_redo_stacks is None:
            self.page_view_redo_stacks = {}
        self.page_text_undo_stacks = self.page_undo_stacks
        if not hasattr(self, "project_undo_stack") or self.project_undo_stack is None:
            self.project_undo_stack = []
        if not hasattr(self, "project_redo_stack") or self.project_redo_stack is None:
            self.project_redo_stack = []
        return True

    def _cancel_pending_view_undo_boundary(self):
        """페이지 경계에서 아직 확정되지 않은 스크롤/확대 Undo를 끊는다.

        스크롤/확대 Undo 자체는 유지하지만, 페이지를 넘는 순간에는 체인을
        닫아야 한다. 타이머가 살아 있다가 새 페이지에서 finish되면 이전
        페이지 기록에 새 페이지 view_state가 섞일 수 있으므로 반드시 취소한다.
        """
        try:
            timer = getattr(self, "_view_undo_coalesce_timer", None)
            if timer is not None:
                timer.stop()
        except Exception:
            pass
        try:
            ve = getattr(self, "view_engine", None)
            if ve is not None and hasattr(ve, "cancel"):
                ve.cancel()
        except Exception:
            pass
        try:
            if getattr(self, "view", None) is not None:
                self.view._scrollbar_view_undo_active = False
                self.view._view_pan_undo_key = None
                self.view._view_pan_start_state = None
        except Exception:
            pass

    def _cancel_pending_view_layer_commit_timer(self):
        """페이지 경계에서 지연 레이어 커밋 타이머가 다음 페이지에 실행되지 않게 막는다."""
        try:
            timer = getattr(self, "_deferred_view_layer_commit_timer", None)
            if timer is not None:
                timer.stop()
        except Exception:
            pass

    def prepare_current_page_boundary(self, reason="page boundary"):
        """현재 페이지를 떠나기 직전 호출하는 단일 경계 처리.

        원칙: 페이지는 독립 프로젝트처럼 닫힌다.
        - 화면 위 텍스트/마스크/최종 페인팅 변경분은 현재 idx 기준 data에 먼저 고정한다.
        - 스크롤/확대 Undo pending은 취소한다.
        - 이후 현재 페이지 Undo/Redo 체인을 끊는다.
        """
        try:
            self._cancel_pending_view_layer_commit_timer()
            if hasattr(self, "flush_pending_view_layer_commit"):
                self.flush_pending_view_layer_commit(save_after=False)
        except Exception:
            pass
        try:
            if hasattr(self, "commit_current_page_ui_to_data"):
                self.commit_current_page_ui_to_data()
        except Exception:
            pass
        try:
            if hasattr(self, "remember_current_view_state"):
                self.remember_current_view_state()
        except Exception:
            pass
        self._cancel_pending_view_undo_boundary()
        self.clear_current_page_undo_stack(reason)

    def _clear_view_runtime_undo(self):
        """현재 화면의 픽셀/마스크/선택계 임시 Undo/Redo를 안전하게 비운다."""
        self._cancel_pending_view_undo_boundary()
        try:
            if getattr(self, "view", None) is not None:
                if hasattr(self.view, "history"):
                    self.view.history.clear()
                if hasattr(self.view, "redo_history"):
                    self.view.redo_history.clear()
        except Exception:
            pass
        # 페이지를 넘어가면 요술봉/분석영역 임시 선택도 이전 페이지 작업으로 본다.
        for attr, empty in (
            ("magic_wand_history", []),
            ("magic_wand_redo_history", []),
            ("ocr_region_temp_history", []),
        ):
            try:
                if hasattr(self, attr):
                    setattr(self, attr, list(empty))
            except Exception:
                pass

    def clear_current_page_undo_stack(self, reason="page boundary"):
        """페이지를 벗어날 때 현재 페이지 작업실의 Undo/Redo만 끊는다."""
        mgr = self.get_undo_manager()
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
        except Exception:
            page_idx = 0
        if mgr is not None:
            mgr.clear_page_storage(page_idx=page_idx, undo=True, redo=True, view=True, update=False)
        else:
            self.ensure_page_undo_state()
            try:
                self.page_undo_stacks.pop(page_idx, None)
                self.page_redo_stacks.pop(page_idx, None)
                self.page_view_undo_stacks.pop(page_idx, None)
                self.page_view_redo_stacks.pop(page_idx, None)
                self.page_text_undo_stacks = self.page_undo_stacks
            except Exception:
                pass
        self._clear_view_runtime_undo()
        self.log(f"🧱 현재 페이지 Undo/Redo 스택 정리: {reason}")
        self.update_undo_redo_buttons()
        return True

    def clear_all_page_undo_stacks(self, reason="page boundary"):
        """모든 페이지 작업실의 Undo/Redo를 끊는다."""
        mgr = self.get_undo_manager()
        if mgr is not None:
            mgr.clear_all_page_storage(update=False)
        else:
            self.ensure_page_undo_state()
            self.page_undo_stacks = {}
            self.page_redo_stacks = {}
            self.page_view_undo_stacks = {}
            self.page_view_redo_stacks = {}
            self.page_text_undo_stacks = self.page_undo_stacks
        self._clear_view_runtime_undo()
        self.log(f"🧱 전체 페이지 Undo/Redo 스택 정리: {reason}")
        self.update_undo_redo_buttons()
        return True

    def paint_history_undo_reasons(self):
        return {"최종 페인팅", "영역 페인팅", "마스크 브러시", "영역 마스킹", "요술봉 영역 칠하기"}

    def is_paint_history_undo_reason(self, reason):
        return str(reason or "") in self.paint_history_undo_reasons()

    def is_mask_light_undo_reason(self, reason):
        text = str(reason or "")
        return text in {"마스크 랩핑", "마스크 커팅", "요술봉 마스킹 칠하기", "마스크 ON/OFF", "텍스트 위 페인팅 ON/OFF"}

    def is_view_history_record(self, rec):
        """스크롤/확대 같은 보기 전용 Undo인지 판정한다.

        E단계부터 보기 기록도 현재 페이지의 일반 Undo 스택에 시간순으로 들어간다.
        이 함수는 restore 분기 판정용으로만 사용한다.
        """
        if not isinstance(rec, dict):
            return False
        if bool(rec.get("view_only")):
            return True
        reason = str(rec.get("reason") or "")
        return reason in {"화면 이동", "화면 확대/축소"}

    def append_page_view_undo_record(self, rec, page_idx=None, clear_redo=True):
        if not rec:
            return False
        if getattr(self, "_project_undo_restore_lock", False):
            return False
        self.ensure_page_undo_state()
        mgr = self.get_undo_manager()
        try:
            page_idx = int(page_idx if page_idx is not None else rec.get("page_idx", getattr(self, "idx", 0)))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        rec = copy.deepcopy(rec)
        rec["page_idx"] = page_idx
        rec["view_only"] = True
        rec["ui_only"] = True
        rec["_undo_scope"] = "page_view"
        stack = mgr.page_view_undo_stack(page_idx, create=True) if mgr is not None else self.page_view_undo_stacks.setdefault(page_idx, [])
        stack.append(rec)
        if len(stack) > 80:
            del stack[0:len(stack) - 80]
        if mgr is not None:
            mgr.register_undo_record(rec, stack="view", clear_redo=clear_redo, source="append_page_view_undo_record")
        if clear_redo:
            if mgr is not None:
                mgr.page_view_redo_stack(page_idx, create=True).clear()
                mgr.page_redo_stack(page_idx, create=True).clear()
            else:
                self.page_view_redo_stacks[page_idx] = []
                self.page_redo_stacks[page_idx] = []
            try:
                if hasattr(self, "page_engine") and self.page_engine is not None:
                    self.page_engine.get(page_idx).redo_stack.clear()
            except Exception:
                pass
        self.update_undo_redo_buttons()
        return True

    def append_page_view_redo_record(self, rec, page_idx=None):
        if not rec:
            return False
        self.ensure_page_undo_state()
        mgr = self.get_undo_manager()
        try:
            page_idx = int(page_idx if page_idx is not None else rec.get("page_idx", getattr(self, "idx", 0)))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        rec = copy.deepcopy(rec)
        rec["page_idx"] = page_idx
        rec["view_only"] = True
        rec["ui_only"] = True
        rec["_undo_scope"] = "page_view"
        stack = mgr.page_view_redo_stack(page_idx, create=True) if mgr is not None else self.page_view_redo_stacks.setdefault(page_idx, [])
        stack.append(rec)
        if len(stack) > 80:
            del stack[0:len(stack) - 80]
        if mgr is not None:
            mgr.register_redo_record(rec, stack="view", source="append_page_view_redo_record")
        self.update_undo_redo_buttons()
        return True

    def make_view_history_record_for_state(self, source_rec, target_state):
        try:
            page_idx = int((source_rec or {}).get("page_idx", getattr(self, "idx", 0)) or 0)
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        try:
            mode = int((source_rec or {}).get("mode", self.current_mode_index_safe()) or 0)
        except Exception:
            mode = int(getattr(self, "last_mode", 0) or 0)
        return {
            "reason": str((source_rec or {}).get("reason") or "화면 이동"),
            "page_idx": page_idx,
            "mode": mode,
            "view_state": copy.deepcopy(target_state or {}),
            "view_only": True,
            "ui_only": True,
            "_undo_scope": "page_view",
        }

    def restore_page_view_history_record(self, rec):
        if not isinstance(rec, dict):
            return False
        try:
            page_idx = int(rec.get("page_idx", getattr(self, "idx", 0)) or 0)
            if page_idx != int(getattr(self, "idx", 0) or 0):
                return False
        except Exception:
            return False
        state = copy.deepcopy(rec.get("view_state") or {})
        if not state:
            return False
        try:
            ve = getattr(self, "view_engine", None)
            if ve is not None and hasattr(ve, "apply"):
                ok = ve.apply(state)
            else:
                ok = self.apply_view_state(state)
        except Exception:
            ok = False
        if not ok:
            try:
                ok = bool(self.apply_view_state(state))
            except Exception:
                ok = False
        try:
            if ok and hasattr(self, "remember_current_view_state"):
                self.remember_current_view_state()
        except Exception:
            pass
        return bool(ok)

    def undo_current_page_view_action(self):
        mgr = self.get_undo_manager()
        if mgr is not None and hasattr(mgr, "undo_current_page_view"):
            return mgr.undo_current_page_view()
        self.update_undo_redo_buttons()
        return False

    def redo_current_page_view_action(self):
        mgr = self.get_undo_manager()
        if mgr is not None and hasattr(mgr, "redo_current_page_view"):
            return mgr.redo_current_page_view()
        self.update_undo_redo_buttons()
        return False

    def append_page_undo_record(self, rec, page_idx=None, clear_redo=True):
        if not rec:
            return False
        if getattr(self, "_project_undo_restore_lock", False):
            return False
        self.ensure_page_undo_state()
        mgr = self.get_undo_manager()
        try:
            page_idx = int(page_idx if page_idx is not None else rec.get("page_idx", getattr(self, "idx", 0)))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        rec = copy.deepcopy(rec)
        rec["page_idx"] = page_idx
        if self.is_view_history_record(rec):
            rec["view_only"] = True
            rec["ui_only"] = True
        rec["_undo_scope"] = "page"
        if clear_redo:
            try:
                if mgr is not None:
                    mgr.page_view_redo_stack(page_idx, create=True).clear()
                else:
                    self.page_view_redo_stacks[page_idx] = []
            except Exception:
                pass

        try:
            if hasattr(self, "page_engine") and self.page_engine is not None:
                ok = self.page_engine.push_undo(rec, page_idx=page_idx, clear_redo=clear_redo)
                wb = self.page_engine.get(page_idx)
                if mgr is not None:
                    mgr._page_stack_map("page_undo_stacks", create=True)[page_idx] = wb.undo_stack
                    if clear_redo:
                        mgr._page_stack_map("page_redo_stacks", create=True)[page_idx] = wb.redo_stack
                else:
                    self.page_undo_stacks[page_idx] = wb.undo_stack
                    if clear_redo:
                        self.page_redo_stacks[page_idx] = wb.redo_stack
                self.undo_boundary = None
                if mgr is not None and ok:
                    mgr.register_undo_record(rec, stack="page", clear_redo=clear_redo, source="append_page_undo_record")
                self.update_undo_redo_buttons()
                return bool(ok)
        except Exception:
            pass

        stack = mgr.page_undo_stack(page_idx, create=True) if mgr is not None else self.page_undo_stacks.setdefault(page_idx, [])
        stack.append(rec)
        if len(stack) > 40:
            stack.pop(0)
        if clear_redo:
            if mgr is not None:
                mgr.page_redo_stack(page_idx, create=True).clear()
            else:
                self.page_redo_stacks[page_idx] = []
        if mgr is not None:
            mgr.register_undo_record(rec, stack="page", clear_redo=clear_redo, source="append_page_undo_record")
        self.undo_boundary = None
        self.update_undo_redo_buttons()
        return True

    def append_page_redo_record(self, rec, page_idx=None):
        if not rec:
            return False
        self.ensure_page_undo_state()
        mgr = self.get_undo_manager()
        try:
            page_idx = int(page_idx if page_idx is not None else rec.get("page_idx", getattr(self, "idx", 0)))
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        rec = copy.deepcopy(rec)
        rec["page_idx"] = page_idx
        if self.is_view_history_record(rec):
            rec["view_only"] = True
            rec["ui_only"] = True
        rec["_undo_scope"] = "page"
        try:
            if hasattr(self, "page_engine") and self.page_engine is not None:
                ok = self.page_engine.push_redo(rec, page_idx=page_idx)
                wb = self.page_engine.get(page_idx)
                if mgr is not None:
                    mgr._page_stack_map("page_redo_stacks", create=True)[page_idx] = wb.redo_stack
                else:
                    self.page_redo_stacks[page_idx] = wb.redo_stack
                if mgr is not None and ok:
                    mgr.register_redo_record(rec, stack="page", source="append_page_redo_record")
                self.update_undo_redo_buttons()
                return bool(ok)
        except Exception:
            pass
        stack = mgr.page_redo_stack(page_idx, create=True) if mgr is not None else self.page_redo_stacks.setdefault(page_idx, [])
        stack.append(rec)
        if len(stack) > 40:
            stack.pop(0)
        if mgr is not None:
            mgr.register_redo_record(rec, stack="page", source="append_page_redo_record")
        self.update_undo_redo_buttons()
        return True

    def append_project_undo_record(self, rec, clear_redo=True):
        if not rec:
            return False
        if getattr(self, "_project_undo_restore_lock", False):
            return False
        if getattr(self, "macro_running", False) and not getattr(self, "_macro_allow_undo_append", False):
            return False
        reason = str((rec or {}).get("reason") or "작업")
        if (rec or {}).get("_undo_scope") == "page" or (not (rec or {}).get("batch_page_data") and not self.is_project_structure_undo_reason(reason, full_project=bool((rec or {}).get("project_data")))):
            if "text_line_state" not in rec and isinstance((rec or {}).get("page_data"), dict):
                page_data = rec.pop("page_data")
                rec["text_line_state"] = {
                    "data": copy.deepcopy(page_data.get("data", []) or []),
                    "ocr_analysis_regions": copy.deepcopy(page_data.get("ocr_analysis_regions", []) or []),
                }
            rec["_undo_scope"] = "page"
            return self.append_page_undo_record(rec, page_idx=rec.get("page_idx"), clear_redo=clear_redo)
        mgr = self.get_undo_manager()
        stack = mgr.project_undo_stack_ref(create=True) if mgr is not None else getattr(self, "project_undo_stack", None)
        if not isinstance(stack, list):
            self.project_undo_stack = []
            stack = self.project_undo_stack
        rec["_undo_scope"] = rec.get("_undo_scope") or "project"
        try:
            if hasattr(self, "project_engine") and self.project_engine is not None:
                self.project_engine.mark_structure_dirty(rec.get("reason", "project undo"))
        except Exception:
            pass
        stack.append(rec)
        if len(stack) > 20:
            stack.pop(0)
        if mgr is not None:
            mgr.register_undo_record(rec, stack="project", clear_redo=clear_redo, source="append_project_undo_record")
        if clear_redo:
            if mgr is not None:
                mgr.project_redo_stack_ref(create=True).clear()
            else:
                self.project_redo_stack = []
        self.update_undo_redo_buttons()
        return True

    def append_project_redo_record(self, rec):
        if not rec:
            return False
        mgr = self.get_undo_manager()
        stack = mgr.project_redo_stack_ref(create=True) if mgr is not None else getattr(self, "project_redo_stack", None)
        if not isinstance(stack, list):
            self.project_redo_stack = []
            stack = self.project_redo_stack
        stack.append(rec)
        if len(stack) > 20:
            stack.pop(0)
        if mgr is not None:
            mgr.register_redo_record(rec, stack="project", source="append_project_redo_record")
        self.update_undo_redo_buttons()
        return True

    def make_project_undo_record(self, reason="작업", page_idx=None, full_project=False):
        factory = self.get_undo_record_factory()
        if factory is not None:
            return factory.make_project_undo_record(reason, page_idx=page_idx, full_project=full_project)
        return {"reason": str(reason or "작업"), "page_idx": int(page_idx if page_idx is not None else getattr(self, "idx", 0) or 0), "_undo_scope": "project" if full_project else "page"}

    def make_ui_undo_record(self, reason="화면 작업", page_idx=None, mode=None):
        factory = self.get_undo_record_factory()
        if factory is not None:
            return factory.make_ui_undo_record(reason, page_idx=page_idx, mode=mode)
        return {"reason": str(reason or "화면 작업"), "page_idx": int(page_idx if page_idx is not None else getattr(self, "idx", 0) or 0), "mode": int(mode if mode is not None else getattr(self, "last_mode", 0) or 0), "ui_only": True}

    def is_ui_only_undo_reason(self, reason):
        text = str(reason or "")
        if text in ("작업 탭 변경", "페이지 이동", "화면 이동", "화면 확대/축소", "화면맞춤"):
            return True
        try:
            from ysb.core.undo_policies import KIND_UI, KIND_VIEW, policy_for
            return policy_for(text).kind in (KIND_UI, KIND_VIEW)
        except Exception:
            return False

    def push_project_undo(self, reason="작업", page_idx=None, full_project=False):
        if getattr(self, "_project_undo_restore_lock", False):
            return False
        if getattr(self, "macro_running", False) or getattr(self, "_suppress_project_undo", False):
            return False
        if getattr(self, "is_loading_project", False) or getattr(self, "is_page_loading", False) or getattr(self, "is_batch_running", False):
            return False
        if not self.paths or page_idx is None and self.idx not in self.data:
            return False
        target_page = self.idx if page_idx is None else page_idx

        # 브러시/페인팅은 QPixmap 레이어 히스토리가 담당한다. project/page data 복사 금지.
        if self.is_paint_history_undo_reason(reason):
            return self.undo_push_page({
                "reason": str(reason or "페인팅"),
                "page_idx": int(target_page),
                "mode": int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else int(getattr(self, "last_mode", 0) or 0),
                "paint_history": True,
            }, page_idx=target_page)

        if self.is_project_structure_undo_reason(reason, full_project=full_project):
            rec = self.make_project_undo_record(reason, target_page, full_project=full_project)
            rec["_undo_scope"] = "project"
            return self.undo_push_project(rec)

        if self.is_ui_only_undo_reason(reason):
            return self.undo_push_ui_state(reason, page_idx=target_page)

        if self.is_mask_light_undo_reason(reason):
            rec = self.make_text_line_undo_record(reason, target_page, include_masks=True)
            rec["_undo_scope"] = "page"
            rec["mask_light_state"] = True
            return self.undo_push_page(rec, page_idx=target_page)

        # 기본값: 현재 페이지 data 리스트 중심의 가벼운 Undo.
        rec = self.make_text_line_undo_record(reason, target_page, include_masks=False)
        rec["_undo_scope"] = "page"
        return self.undo_push_page(rec, page_idx=target_page)

    def begin_deferred_project_undo(self, key, reason="작업"):
        if not key:
            return None
        if getattr(self, "macro_running", False) or getattr(self, "_suppress_project_undo", False):
            return None
        if getattr(self, "_project_undo_restore_lock", False) or getattr(self, "is_page_loading", False) or getattr(self, "is_batch_running", False):
            return None
        page_idx = int(getattr(self, "idx", 0) or 0)
        if self.is_paint_history_undo_reason(reason):
            rec = {
                "reason": str(reason or "페인팅"),
                "page_idx": page_idx,
                "mode": int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else int(getattr(self, "last_mode", 0) or 0),
                "paint_history": True,
                "_undo_scope": "page",
            }
        elif self.is_project_structure_undo_reason(reason):
            rec = self.make_project_undo_record(reason, page_idx, full_project=False)
            rec["_undo_scope"] = "project"
        elif self.is_ui_only_undo_reason(reason):
            rec = self.make_ui_undo_record(reason, page_idx)
            rec["_undo_scope"] = "page"
        elif self.is_mask_light_undo_reason(reason):
            rec = self.make_text_line_undo_record(reason, page_idx, include_masks=True)
            rec["_undo_scope"] = "page"
            rec["mask_light_state"] = True
        else:
            rec = self.make_text_line_undo_record(reason, page_idx, include_masks=False)
            rec["_undo_scope"] = "page"
        self._deferred_undo_records[str(key)] = rec
        return rec

    def finish_deferred_project_undo(self, key, force=False, changed=None, autosave=True):
        rec = self._deferred_undo_records.pop(str(key), None)
        if getattr(self, "macro_running", False) or getattr(self, "_suppress_project_undo", False):
            if autosave:
                try:
                    self.schedule_deferred_auto_save_project(600)
                except Exception:
                    self.auto_save_project()
            return False
        if not rec:
            return False
        if changed is None:
            changed = True
        if not force and not changed:
            return False
        if rec.get("_undo_scope") == "project":
            ok = self.undo_push_project(rec)
        else:
            ok = self.undo_push_page(rec, page_idx=rec.get("page_idx"))
        if autosave:
            try:
                self.schedule_deferred_auto_save_project(600)
            except Exception:
                self.auto_save_project()
        return ok

    def copy_text_line_state_for_undo(self, page_idx=None, include_masks=False):
        factory = self.get_undo_record_factory()
        if factory is not None:
            return factory.copy_text_line_state_for_undo(page_idx=page_idx, include_masks=include_masks)
        return None

    def make_text_line_undo_record(self, reason="텍스트 라인 변경", page_idx=None, include_masks=False):
        factory = self.get_undo_record_factory()
        if factory is not None:
            return factory.make_text_line_undo_record(reason, page_idx=page_idx, include_masks=include_masks)
        return {"reason": str(reason or "텍스트 라인 변경"), "page_idx": int(page_idx if page_idx is not None else getattr(self, "idx", 0) or 0), "text_line_state": None, "_undo_scope": "page"}

    def push_text_line_undo(self, reason="텍스트 라인 변경", page_idx=None, include_masks=False):
        if getattr(self, "_project_undo_restore_lock", False):
            return False
        if getattr(self, "macro_running", False) or getattr(self, "_suppress_project_undo", False):
            return False
        if getattr(self, "is_loading_project", False) or getattr(self, "is_page_loading", False) or getattr(self, "is_batch_running", False):
            return False
        if not self.paths or (page_idx is None and self.idx not in self.data):
            return False
        target_page = self.idx if page_idx is None else page_idx
        mgr = self.get_undo_manager()
        if mgr is not None:
            ok = mgr.push_text_line(reason=reason, page_idx=target_page, include_masks=include_masks)
        else:
            rec = self.make_text_line_undo_record(reason, target_page, include_masks=include_masks)
            rec["_undo_scope"] = "page"
            ok = self.undo_push_page(rec, page_idx=target_page)
        try:
            self.audit_boundary_event(
                "TEXT_UNDO_PUSH",
                reason=str(reason or "텍스트 작업"),
                page_idx=int(target_page),
                ok=bool(ok),
                undo_len=len((self.page_undo_stacks or {}).get(int(target_page), []) or []),
                throttle_ms=80,
            )
        except Exception:
            pass
        return ok

    def unique_history_rename_target(self, target_path):
        """Undo/Redo 중 목표 파일명이 이미 있을 때 자동 대체 이름을 만든다."""
        try:
            target = Path(str(target_path))
            folder = target.parent
            ext = target.suffix or ".png"
            base = safe_page_file_stem(target.stem, fallback="image")
            for n in range(1, 10000):
                cand = folder / f"{base}({n}){ext}"
                if not cand.exists():
                    return str(cand)
            return str(folder / f"{base}({uuid.uuid4().hex[:8]}){ext}")
        except Exception:
            return str(target_path)

    def confirm_history_rename_conflict(self, target_path, auto_path, reason="원본 파일명 변경"):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(self.tr_ui("파일명 중복"))
        msg.setText(self.tr_ui("되돌리려는 원본 이미지 파일명이 이미 있습니다."))
        msg.setInformativeText(
            f"{self.tr_ui('기존 이름')} : {os.path.basename(str(target_path))}\n"
            f"{self.tr_ui('자동 이름')} : {os.path.basename(str(auto_path))}"
        )
        btn_auto = msg.addButton(self.tr_ui("이름 바꾸고 계속"), QMessageBox.ButtonRole.AcceptRole)
        btn_cancel = msg.addButton(self.tr_ui("되돌리지 않기"), QMessageBox.ButtonRole.RejectRole)
        for _btn in (btn_auto, btn_cancel):
            try:
                _btn.setMinimumWidth(148)
            except Exception:
                pass
        msg.setDefaultButton(btn_auto)
        msg.setEscapeButton(btn_cancel)
        try:
            msg.setStyleSheet(
                self.message_box_style()
                + "\nQMessageBox QPushButton { min-width:148px; padding:6px 14px; }"
            )
        except Exception:
            pass
        force_message_box_front(msg)
        msg.exec()
        return msg.clickedButton() is btn_auto

    def update_history_record_paths_after_rename(self, rec, page_idx, expected_to, actual_to):
        """충돌 때문에 Undo/Redo 목표명이 바뀐 경우 스냅샷도 실제 파일명에 맞춘다."""
        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = None
        expected_to = str(expected_to)
        actual_to = str(actual_to)
        if expected_to == actual_to:
            return
        try:
            paths = rec.get("project_paths")
            if isinstance(paths, list):
                for i, p in enumerate(paths):
                    try:
                        if str(Path(str(p)).resolve()).lower() == str(Path(expected_to).resolve()).lower():
                            paths[i] = actual_to
                    except Exception:
                        if str(p) == expected_to:
                            paths[i] = actual_to
                if page_idx is not None and 0 <= page_idx < len(paths):
                    paths[page_idx] = actual_to
        except Exception:
            pass
        try:
            pdata = rec.get("project_data")
            if isinstance(pdata, dict) and page_idx is not None:
                curr = pdata.get(page_idx)
                if curr is None:
                    curr = pdata.get(str(page_idx))
                if isinstance(curr, dict):
                    curr["original_name"] = os.path.basename(actual_to)
        except Exception:
            pass
        try:
            page_data = rec.get("page_data")
            if isinstance(page_data, dict):
                page_data["original_name"] = os.path.basename(actual_to)
        except Exception:
            pass

    def apply_file_rename_ops_for_history(self, rec):
        """Undo/Redo 기록에 포함된 실제 파일명 변경을 먼저 적용한다."""
        ops = (rec or {}).get("file_rename_ops")
        if not isinstance(ops, list) or not ops:
            return True

        for op in ops:
            if not isinstance(op, dict):
                continue
            src = str(op.get("from_path") or "")
            dst = str(op.get("to_path") or "")
            if not src or not dst:
                continue
            try:
                src_path = Path(src)
                dst_path = Path(dst)
                page_idx = op.get("page_idx")

                if not src_path.exists():
                    # 이미 목표 상태에 가깝거나 파일이 정리된 경우는 데이터 복원으로 이어간다.
                    continue

                actual_dst = dst_path
                try:
                    same_path = str(src_path.resolve()).lower() == str(dst_path.resolve()).lower()
                except Exception:
                    same_path = str(src_path).lower() == str(dst_path).lower()

                if dst_path.exists() and not same_path:
                    auto_path = Path(self.unique_history_rename_target(dst_path))
                    if not self.confirm_history_rename_conflict(dst_path, auto_path, op.get("reason", "원본 파일명 변경")):
                        return False
                    actual_dst = auto_path

                actual_dst.parent.mkdir(parents=True, exist_ok=True)

                if same_path and str(src_path) != str(actual_dst):
                    tmp = src_path.with_name(f".__ysb_history_rename_{uuid.uuid4().hex}{src_path.suffix}")
                    os.rename(str(src_path), str(tmp))
                    os.rename(str(tmp), str(actual_dst))
                elif str(src_path) != str(actual_dst):
                    os.rename(str(src_path), str(actual_dst))

                self.update_history_record_paths_after_rename(rec, page_idx, dst_path, actual_dst)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    self.tr_ui("파일명 변경 Undo 실패"),
                    f"{self.tr_ui('원본 이미지 파일명을 되돌리지 못했습니다.')}\n{e}",
                )
                return False
        return True

    def invert_file_rename_ops(self, ops):
        out = []
        for op in ops or []:
            if not isinstance(op, dict):
                continue
            out.append({
                "page_idx": op.get("page_idx"),
                "from_path": op.get("to_path"),
                "to_path": op.get("from_path"),
                "reason": op.get("reason", "원본 파일명 변경"),
            })
        return out

    def make_current_undo_record_like(self, rec):
        factory = self.get_undo_record_factory()
        if factory is not None:
            return factory.make_current_undo_record_like(rec)
        return self.make_project_undo_record(str((rec or {}).get("reason") or "작업"), page_idx=(rec or {}).get("page_idx"), full_project=bool((rec or {}).get("project_data")))

    def restore_project_history_record(self, rec):
        """Undo/Redo 기록 1개를 실제 작업 상태로 복원한다."""
        page_idx = int(rec.get("page_idx", self.idx) or 0)
        rec_paths = rec.get("project_paths")
        path_count = len(rec_paths) if isinstance(rec_paths, list) else len(self.paths)
        if path_count <= 0:
            page_idx = 0
        elif page_idx < 0 or page_idx >= path_count:
            page_idx = max(0, min(page_idx, path_count - 1))

        if not self.apply_file_rename_ops_for_history(rec):
            return False

        self._project_undo_restore_lock = True
        self._text_undo_restore_lock = True
        try:
            structure_applied = False
            try:
                from ysb.core.project_structure_undo import apply_structure_diff
                structure_applied = bool(apply_structure_diff(self, rec))
            except Exception:
                structure_applied = False

            text_diff_state = rec.get("text_diff_state")
            text_diff_changed_ids = []
            if isinstance(text_diff_state, dict):
                curr = self.data.get(page_idx)
                if isinstance(curr, dict):
                    data_list = curr.get("data", [])
                    if isinstance(data_list, list):
                        try:
                            text_diff_changed_ids = self.text_engine.apply_snapshot(data_list, text_diff_state.get("items") or [])
                        except Exception:
                            text_diff_changed_ids = []
            text_line_state = rec.get("text_line_state")
            restored_mask_state = False
            text_line_structure_changed = False
            if isinstance(text_line_state, dict):
                curr = self.data.get(page_idx)
                if isinstance(curr, dict):
                    try:
                        before_ids = [str(x.get("id")) for x in (curr.get("data", []) or []) if isinstance(x, dict)]
                        after_ids = [str(x.get("id")) for x in (text_line_state.get("data", []) or []) if isinstance(x, dict)]
                        text_line_structure_changed = before_ids != after_ids
                    except Exception:
                        text_line_structure_changed = True
                    curr["data"] = copy.deepcopy(text_line_state.get("data", []) or [])
                    if "ocr_analysis_regions" in text_line_state:
                        curr["ocr_analysis_regions"] = copy.deepcopy(text_line_state.get("ocr_analysis_regions", []) or [])
                    for key in ("mask_merge", "mask_inpaint", "mask_merge_off", "mask_inpaint_off"):
                        if key in text_line_state:
                            value = text_line_state.get(key)
                            curr[key] = value.copy() if isinstance(value, np.ndarray) else copy.deepcopy(value)
                            restored_mask_state = True
                    if "mask_toggle_enabled" in text_line_state:
                        curr["mask_toggle_enabled"] = bool(text_line_state.get("mask_toggle_enabled"))
                        restored_mask_state = True
            elif not structure_applied and not isinstance(text_diff_state, dict) and not rec.get("ui_only"):
                rec_paths = rec.get("project_paths")
                if isinstance(rec_paths, list):
                    self.paths = list(rec_paths)
                batch_page_data = rec.get("batch_page_data")
                if isinstance(batch_page_data, dict):
                    for k, v in batch_page_data.items():
                        try:
                            kk = int(k)
                        except Exception:
                            continue
                        if isinstance(v, dict):
                            self.data[kk] = self.copy_undo_page_data(v)
                            try:
                                self.touch_page_image_cache(kk)
                            except Exception:
                                pass
                else:
                    project_data = rec.get("project_data")
                    if isinstance(project_data, dict):
                        restored = {}
                        for k, v in project_data.items():
                            try:
                                kk = int(k)
                            except Exception:
                                kk = k
                            restored[kk] = self.copy_undo_page_data(v) if isinstance(v, dict) else copy.deepcopy(v)
                        self.data = restored
                    else:
                        page_data = rec.get("page_data")
                        if isinstance(page_data, dict):
                            self.data[page_idx] = self.copy_undo_page_data(page_data)

            if self.paths:
                page_idx = max(0, min(page_idx, len(self.paths) - 1))
            else:
                page_idx = 0
            mode = int(rec.get("mode", 0) or 0)

            # 텍스트 라인/스타일/이동 Undo는 현재 페이지의 data 리스트만 되돌리면 된다.
            # 여기서 self.load()를 호출하면 페이지 이미지/마스크/scene 전체가 다시 로드되어
            # Ctrl+Z 한 번에도 대용량 페이지 작업실이 통째로 움직인다.
            try:
                current_page_idx = int(getattr(self, "idx", -1))
            except Exception:
                current_page_idx = -1
            same_current_page = page_idx == current_page_idx
            fast_text_diff_restore = isinstance(text_diff_state, dict) and same_current_page
            fast_text_restore = (isinstance(text_line_state, dict) or fast_text_diff_restore) and same_current_page
            fast_ui_restore = bool(rec.get("ui_only")) and same_current_page
            fast_view_restore = bool(rec.get("view_only")) and same_current_page
            fast_mode_restore = bool(rec.get("layer_only")) or str(rec.get("reason") or "") == "작업 탭 변경"
            if fast_text_restore or fast_ui_restore:
                old_suppress_option = getattr(self, "_suppress_shared_option_refresh", False)
                old_rebuilding_text = getattr(self, "_is_rebuilding_text_layer", False)
                self._suppress_shared_option_refresh = True
                try:
                    if fast_text_restore:
                        # 현재 페이지 텍스트/뷰 Undo는 절대 load()/mode_chg()를 타지 않는다.
                        # page data를 snapshot으로 갈아끼우고, 현재 페이지 text layer만 다시 만든다.
                        self.set_work_mode_without_undo(mode)
                    elif fast_mode_restore:
                        # 작업탭 변경 Undo는 콤보박스 값만 바꾸면 탭 이름만 바뀌고 화면 레이어는 그대로 남는다.
                        # Undo 기록/마스크 자동커밋/저장 부작용은 막고, mode_chg를 직접 한 번 태워 실제 화면도 복원한다.
                        old_suppress_mode = getattr(self, "_suppress_mode_undo", False)
                        old_skip_mask = getattr(self, "_skip_mode_mask_commit", False)
                        old_batch = getattr(self, "is_batch_running", False)
                        try:
                            self._suppress_mode_undo = True
                            self._skip_mode_mask_commit = True
                            self.is_batch_running = True
                            self.set_work_mode_without_undo(mode)
                            try:
                                self.mode_chg(mode)
                            except Exception:
                                pass
                            self.restore_project_ui_state(rec.get("ui_state"), refresh=False)
                        finally:
                            self.is_batch_running = old_batch
                            self._skip_mode_mask_commit = old_skip_mask
                            self._suppress_mode_undo = old_suppress_mode
                    elif not fast_view_restore:
                        self.set_work_mode_without_undo(mode)
                        self.restore_project_ui_state(rec.get("ui_state"), refresh=False)
                    if fast_text_restore:
                        try:
                            if isinstance(text_line_state, dict) and text_line_structure_changed:
                                try:
                                    self.ref_tab()
                                except Exception:
                                    pass
                            if mode == 4:
                                sel = rec.get("selected_ids") or text_diff_changed_ids or []
                                self._is_rebuilding_text_layer = True
                                try:
                                    rebuilt = False
                                    if (not text_line_structure_changed) and hasattr(self, 'rebuild_current_page_text_layer_from_data'):
                                        rebuilt = bool(self.rebuild_current_page_text_layer_from_data(sel))
                                    if not rebuilt:
                                        # 삭제/붙여넣기/행 순서 변경 Undo처럼 scene item 수나 ID 구성이 달라지는 경우는
                                        # 부분 재빌드로는 복원 불가. refresh_final_text_scene_preserving_selection()는
                                        # 선택된 기존 아이템만 in-place 갱신하고 끝날 수 있으므로 강제 전체 재구성을 직접 호출한다.
                                        if hasattr(self, 'force_rebuild_final_text_layer_from_data'):
                                            self.force_rebuild_final_text_layer_from_data(sel)
                                        else:
                                            old_suppress_mode = getattr(self, "_suppress_mode_undo", False)
                                            self._suppress_mode_undo = True
                                            try:
                                                self.mode_chg(4)
                                                if sel:
                                                    self.reselect_text_items(sel)
                                            finally:
                                                self._suppress_mode_undo = old_suppress_mode
                                finally:
                                    self._is_rebuilding_text_layer = old_rebuilding_text
                            elif mode in (1, 2, 3):
                                self.refresh_boxes_only()
                                # 마스크 랩핑/커팅/ON-OFF Undo는 현재 페이지 data의 마스크 슬롯을
                                # 복원한 뒤, 화면의 user_mask_item도 즉시 같은 값으로 되돌려야 한다.
                                # 이전에는 data만 바뀌고 뷰 레이어가 남아 있어 Ctrl+Z가 안 먹는 것처럼 보였다.
                                if mode in (2, 3) and restored_mask_state:
                                    try:
                                        curr = self.data.get(page_idx) or {}
                                        if "mask_toggle_enabled" in text_line_state:
                                            self.set_mask_toggle_safely(bool(text_line_state.get("mask_toggle_enabled")))
                                        restored_mask = self.get_active_mask(curr, mode_idx=mode)
                                        if restored_mask is not None and getattr(self, "view", None) is not None:
                                            color = QColor(0, 0, 255, 150) if mode == 3 else QColor(255, 0, 0, 150)
                                            self.view.set_user_mask_np(restored_mask, color)
                                            try:
                                                self.view.viewport().update()
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                        except Exception:
                            self._is_rebuilding_text_layer = old_rebuilding_text
                    state = copy.deepcopy(rec.get("view_state") or {})
                    if state:
                        try:
                            self.apply_view_state(state)
                        except Exception:
                            pass
                    try:
                        self.restore_magic_wand_state(rec.get("magic_wand_state"))
                    except Exception:
                        pass
                    # Undo/Redo는 저장 작업이 아니다. 여기서 ProjectStore/복구 캐시 저장을 깨우지 않는다.
                    try:
                        if fast_text_restore:
                            try:
                                self.finalize_text_change(ids=[], fields=['undo_restore'], reason='텍스트 Undo/Redo 복원', delay_ms=1800, refresh_scene=False)
                            except Exception:
                                self.mark_active_page_dirty('text')
                            # Object <-> text undo can correctly rebuild the canvas while the
                            # right-side text table still holds its display-only "[객체]" prefix.
                            # Refresh the table after the scene/data resync so the table mirrors
                            # the current rasterized_text state and sanitized real text.
                            try:
                                sel_ids = rec.get("selected_ids") or text_diff_changed_ids or []
                                self.schedule_text_table_refresh_after_structure_change(
                                    sel_ids,
                                    delay_ms=80,
                                    reason='텍스트 Undo/Redo 표 갱신',
                                )
                            except Exception:
                                try:
                                    self.ref_tab()
                                except Exception:
                                    pass
                        elif fast_view_restore and hasattr(self, "active_page_session") and self.active_page_session is not None:
                            self.active_page_session.mark_dirty("view")
                    except Exception:
                        pass
                finally:
                    self._is_rebuilding_text_layer = old_rebuilding_text
                    self._suppress_shared_option_refresh = old_suppress_option
                try:
                    if mode == 4 and fast_text_restore and hasattr(self, "refresh_shared_option_bar"):
                        self.refresh_shared_option_bar()
                except Exception:
                    pass
            else:
                self.idx = page_idx
                self.set_work_mode_without_undo(mode)
                self.restore_project_ui_state(rec.get("ui_state"), refresh=False)

                prev_loading = self.is_page_loading
                self.is_page_loading = True
                try:
                    self.load()
                finally:
                    self.is_page_loading = prev_loading

                self.restore_project_ui_state(rec.get("ui_state"), refresh=(mode == 4))

                state = copy.deepcopy(rec.get("view_state") or {})
                if state:
                    self.apply_view_state(state)
                    QTimer.singleShot(0, lambda st=state: self.apply_view_state(st))
                    QTimer.singleShot(30, lambda st=state: self.apply_view_state(st))
                    QTimer.singleShot(80, lambda st=state: self.apply_view_state(st))

                try:
                    self.restore_magic_wand_state(rec.get("magic_wand_state"))
                except Exception:
                    pass
                try:
                    self.schedule_deferred_auto_save_project(600)
                except Exception:
                    self.auto_save_project()
        finally:
            self._text_undo_restore_lock = False
            self._project_undo_restore_lock = False
        return True

    def undo_current_page_action(self):
        mgr = self.get_undo_manager()
        if mgr is not None and hasattr(mgr, "undo_current_page"):
            return mgr.undo_current_page()
        self.update_undo_redo_buttons()
        return False

    def redo_current_page_action(self):
        mgr = self.get_undo_manager()
        if mgr is not None and hasattr(mgr, "redo_current_page"):
            return mgr.redo_current_page()
        self.update_undo_redo_buttons()
        return False

    def undo_project_action(self):
        mgr = self.get_undo_manager()
        if mgr is not None and hasattr(mgr, "undo_project"):
            return mgr.undo_project()
        self.update_undo_redo_buttons()
        return False

    def redo_project_action(self):
        mgr = self.get_undo_manager()
        if mgr is not None and hasattr(mgr, "redo_project"):
            return mgr.redo_project()
        self.update_undo_redo_buttons()
        return False

    def copy_undo_page_data(self, page_data):
        out = {}
        for k, v in (page_data or {}).items():
            if k == 'ori':
                out[k] = v
            elif isinstance(v, np.ndarray):
                out[k] = v.copy()
            else:
                out[k] = copy.deepcopy(v)
        try:
            data_list = out.get('data')
            if isinstance(data_list, list):
                for item in data_list:
                    self.strip_text_transform_runtime_flags(item)
        except Exception:
            pass
        return out

    def push_page_text_undo(self, reason="텍스트 작업"):
        # 텍스트 이동/수정/스타일 변경은 현재 페이지 data 리스트만 있으면 복구 가능하다.
        # 전체 page_data를 복사하면 bg_clean/mask/기타 큰 데이터까지 같이 붙어 작업 1회마다
        # 대용량 프로젝트가 끌려다니므로 텍스트 전용 Undo로 제한한다.
        return self.undo_push_text_line(reason, include_masks=False)

    def cancel_live_text_transform_runtime(self):
        """Undo/Redo 전 최종결과 scene에 남은 변형 드래그 런타임 상태와 캐시를 정리한다."""
        scene = None
        try:
            scene = self._safe_graphics_scene()
        except Exception:
            scene = None
        if scene is None:
            return False
        changed = False
        dirty_rect = QRectF()
        try:
            active = self.current_transform_data_item()
            if isinstance(active, dict):
                self.strip_text_transform_runtime_flags(active)
                changed = True
        except Exception:
            pass
        try:
            for item in list(scene.items()):
                if not isinstance(item, TypesettingItem):
                    continue
                try:
                    rect = item.sceneBoundingRect().adjusted(-32, -32, 32, 32)
                    dirty_rect = rect if dirty_rect.isNull() else dirty_rect.united(rect)
                except Exception:
                    pass
                if hasattr(item, 'cancel_live_transform_preview'):
                    item.cancel_live_transform_preview()
                    changed = True
        except RuntimeError:
            return changed
        except Exception:
            return changed
        try:
            self.force_update_final_scene_region(dirty_rect)
        except Exception:
            try:
                scene.update()
            except Exception:
                pass
        return changed

    def undo_page_text(self):
        # 구버전 호출 호환용. 실제 Ctrl+Z는 handle_general_undo()에서
        # undo_project_action()을 먼저 사용한다.
        return self.undo_project_action()

    def end_active_text_transform(self, refresh=True, quiet=False, mark_dirty=False, clear_selection=False):
        active = self.current_transform_data_item()
        if active is None:
            return False
        was_skew = bool(active.get('_skew_mode', False))
        was_trapezoid = bool(active.get('_trapezoid_mode', False))
        was_arc = bool(active.get('_arc_mode', False))
        selected_id = active.get('id')

        # 변형 모드 플래그는 저장 데이터가 아니라 런타임 UI 상태다.
        # 종료/ESC/Undo 전 정리 시 dirty/cache 저장을 깨우지 않는다.
        self.strip_text_transform_runtime_flags(active)

        old_suppress = getattr(self, "_suppress_shared_option_refresh", False)
        self._suppress_shared_option_refresh = True
        try:
            if refresh and self.cb_mode.currentIndex() == 4:
                if selected_id is not None and hasattr(self, 'refresh_final_text_items_by_ids'):
                    if not self.refresh_final_text_items_by_ids([selected_id]):
                        self.schedule_final_text_scene_refresh(30)
                    if not clear_selection and not quiet:
                        self.reselect_text_items([selected_id])
                else:
                    self.schedule_final_text_scene_refresh(30)
            if clear_selection:
                try:
                    if getattr(self, "view", None) is not None and getattr(self.view, "scene", None) is not None:
                        self.view.scene.clearSelection()
                except Exception:
                    pass
        finally:
            self._suppress_shared_option_refresh = old_suppress

        try:
            self.force_update_final_scene_region()
        except Exception:
            pass

        # 실제 변형값이 바뀐 경우는 각 drag/수치 입력 경로에서 dirty/save를 처리한다.
        # ESC로 모드만 빠져나오는 것은 dirty 작업이 아니다.
        if mark_dirty:
            try:
                self.finalize_text_change(ids=[selected_id] if selected_id is not None else [], fields=['transform_mode'], reason='텍스트 변형 모드 종료', delay_ms=1800, refresh_scene=False)
            except Exception:
                pass

        if not quiet:
            if was_arc:
                self.log("🔷 부채꼴 변형 종료")
            elif was_trapezoid:
                self.log("🔷 사다리꼴 변형 종료")
            elif was_skew:
                self.log("🔷 평행사변형 변형 종료")
            else:
                self.log("🔷 텍스트 변형 모드 종료")
        return True

    def undo_last_arc_transform_point(self):
        active = self.current_transform_data_item() if hasattr(self, 'current_transform_data_item') else None
        if not isinstance(active, dict) or not active.get('_arc_mode'):
            return False
        handles = active.get('arc_handles')
        if not isinstance(handles, list) or not handles:
            return False
        handles.pop()
        active['arc_handles'] = handles
        try:
            active['arc_active_index'] = len(handles) - 1 if handles else -1
        except Exception:
            pass
        selected_id = active.get('id')
        if self.cb_mode.currentIndex() == 4:
            if selected_id is not None and hasattr(self, 'refresh_final_text_items_by_ids'):
                if not self.refresh_final_text_items_by_ids([selected_id]):
                    self.schedule_final_text_scene_refresh(30)
                self.reselect_text_items([selected_id])
            else:
                self.schedule_final_text_scene_refresh(30)
        try:
            self.finalize_text_change(ids=[selected_id] if selected_id is not None else [], fields=['arc_handles', 'arc_active_index'], reason='부채꼴 제어점 제거', delay_ms=1800)
        except Exception:
            try:
                self.mark_active_page_dirty('text')
                self.schedule_deferred_auto_save_project(1800)
            except Exception:
                pass
        self.log(f"↩️ 부채꼴 제어점 제거: 남은 점 {len(handles)}개")
        self.update_undo_redo_buttons()
        return True

    def can_general_undo(self):
        if self.maker_global_undo_disabled():
            return False
        try:
            self.ensure_page_undo_state()
            mgr = self.get_undo_manager()
            page_idx = int(getattr(self, "idx", 0) or 0)
            # Stage 9: 버튼 활성 판단도 single timeline을 먼저 본다.
            # 임시/선택 전용 history는 구버전 fallback으로만 남긴다.
            if mgr is not None:
                if mgr.can_undo_timeline():
                    return True
                lengths = mgr.page_stack_lengths(page_idx)
                if lengths.get("page_undo") or lengths.get("project_undo") or lengths.get("view_undo"):
                    return True
            else:
                if self.page_undo_stacks.get(page_idx):
                    return True
                if getattr(self, "project_undo_stack", None):
                    return True
                if self.page_view_undo_stacks.get(page_idx):
                    return True
            try:
                paint_lengths = self.undo_paint_stack_lengths(getattr(self, "view", None))
                if paint_lengths.get("paint_undo"):
                    return True
            except Exception:
                if getattr(getattr(self, "view", None), "history", None):
                    return True
            active = self.current_transform_data_item() if hasattr(self, 'current_transform_data_item') else None
            if isinstance(active, dict) and active.get('_arc_mode') and isinstance(active.get('arc_handles'), list) and active.get('arc_handles'):
                return True
            if getattr(getattr(self, "view", None), "draw_mode", None) == 'ocr_region_select' and getattr(self, 'ocr_region_temp_history', None):
                return True
            if getattr(getattr(self, "view", None), "draw_mode", None) == 'magic_wand' and getattr(self, 'magic_wand_history', None):
                return True
        except Exception:
            pass
        return False

    def can_general_redo(self):
        if self.maker_global_undo_disabled():
            return False
        try:
            self.ensure_page_undo_state()
            mgr = self.get_undo_manager()
            page_idx = int(getattr(self, "idx", 0) or 0)
            if mgr is not None:
                if mgr.can_redo_timeline():
                    return True
                lengths = mgr.page_stack_lengths(page_idx)
                if lengths.get("page_redo") or lengths.get("project_redo") or lengths.get("view_redo"):
                    return True
            else:
                if self.page_redo_stacks.get(page_idx):
                    return True
                if getattr(self, "project_redo_stack", None):
                    return True
                if self.page_view_redo_stacks.get(page_idx):
                    return True
            try:
                paint_lengths = self.undo_paint_stack_lengths(getattr(self, "view", None))
                if paint_lengths.get("paint_redo"):
                    return True
            except Exception:
                if getattr(getattr(self, "view", None), "redo_history", None):
                    return True
            if getattr(getattr(self, "view", None), "draw_mode", None) == 'magic_wand' and getattr(self, 'magic_wand_redo_history', None):
                return True
        except Exception:
            pass
        return False

    def set_history_button_tooltips(self):
        """Keep quick undo/redo on the unified delayed tooltip system only."""
        def shortcut_text(key, fallback=""):
            try:
                seq = self.shortcut_settings.seq(key)
                txt = seq.toString(QKeySequence.SequenceFormat.NativeText)
                return txt or fallback
            except Exception:
                return fallback

        def set_delayed(widget, title, shortcut, desc):
            if widget is None:
                return
            try:
                widget.setToolTip("")
                action = widget.defaultAction() if hasattr(widget, "defaultAction") else None
                if action is not None:
                    action.setToolTip("")
                    action.setStatusTip("")
                    action.setWhatsThis("")
            except Exception:
                pass
            try:
                if hasattr(self, "register_delayed_tooltip"):
                    self.register_delayed_tooltip(widget, title, shortcut, desc)
                    return
            except Exception:
                pass
            try:
                widget.setProperty("delayed_tooltip_title", title)
                widget.setProperty("delayed_tooltip_shortcut", shortcut)
                widget.setProperty("delayed_tooltip_description", desc)
                if hasattr(self, "_tooltip_rich_text"):
                    widget.setProperty("delayed_tooltip_html", self._tooltip_rich_text(title, shortcut, desc))
                widget.installEventFilter(self)
            except Exception:
                pass

        if hasattr(self, "btn_quick_undo"):
            set_delayed(
                self.btn_quick_undo,
                self.tr_ui("뒤로가기"),
                shortcut_text("paint_undo", "Ctrl+Z"),
                self.tr_msg("최근 작업을 되돌립니다."),
            )
        if hasattr(self, "btn_quick_redo"):
            set_delayed(
                self.btn_quick_redo,
                self.tr_ui("앞으로 가기"),
                shortcut_text("paint_redo", "Ctrl+Y"),
                self.tr_msg("되돌린 작업을 다시 실행합니다."),
            )
    def history_button_style(self, enabled):
        if enabled:
            return "background:#3b465a;color:#ffffff;border:1px solid #7f8ba3;font-weight:bold;"
        return "background:#2a2d34;color:#777b84;border:1px solid #444852;font-weight:bold;"

    def update_undo_redo_buttons(self):
        # 쯔꾸르붕이 Undo 정책: 전역 작업 Undo/Redo 버튼은 사용하지 않는다.
        # Ctrl+Z/Ctrl+Y는 현재 텍스트 입력칸의 기본 Undo/Redo로만 처리한다.
        try:
            if hasattr(self, "btn_quick_undo"):
                self.btn_quick_undo.setEnabled(False)
                self.btn_quick_undo.hide()
            if hasattr(self, "btn_quick_redo"):
                self.btn_quick_redo.setEnabled(False)
                self.btn_quick_redo.hide()
        except Exception:
            pass

    def handle_general_undo(self):
        # 전역 프로젝트/페이지/뷰/페인트 Undo는 쯔꾸르붕이에서 금지한다.
        if hasattr(self, "handle_local_text_input_undo_redo"):
            self.handle_local_text_input_undo_redo(redo=False)
        self.update_undo_redo_buttons()
        return True

    def handle_general_redo(self):
        # 전역 프로젝트/페이지/뷰/페인트 Redo는 쯔꾸르붕이에서 금지한다.
        if hasattr(self, "handle_local_text_input_undo_redo"):
            self.handle_local_text_input_undo_redo(redo=True)
        self.update_undo_redo_buttons()
        return True

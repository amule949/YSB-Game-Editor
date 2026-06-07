from ysb.ui.main_window_support import *
from ysb.core.project_store import PackageProjectCancelled, WORKSPACE_STATE_FILENAME, read_workspace_state, write_workspace_state, relpath, json_safe
from ysb.tools.maker_project import (
    strip_maker_control_codes,
    compose_maker_inline_speaker_writeback,
    extract_database_text_units,
    load_maker_preview_settings,
    _ysb_text_item_from_unit,
    _virtual_page_placeholder_image,
    _MAKER_CONTROL_CODE_RE,
)


class MainWindowProjectPagesMixin:

    def _remove_live_text_scene_items_by_identity_or_id(self, data_ref_ids=None, text_ids=None, reason=""):
        """Remove specific live TypesettingItem objects from the current scene.

        Text line deletion changes curr['data'] first and then renumbers ids.  If the
        old scene item remains alive, undo rebuild creates a second item while the old
        one becomes an unlinked ghost.  Match by original data object identity before
        renumber, and by original id as a fallback.
        """
        scene = self._safe_graphics_scene() if hasattr(self, "_safe_graphics_scene") else getattr(getattr(self, "view", None), "scene", None)
        if scene is None:
            return 0
        data_ref_ids = {int(x) for x in (data_ref_ids or set()) if x is not None}
        text_ids = {str(x) for x in (text_ids or set()) if x is not None}
        removed = 0
        old_block = None
        try:
            old_block = scene.blockSignals(True)
        except Exception:
            old_block = None
        try:
            for obj in list(scene.items()):
                try:
                    if not isinstance(obj, TypesettingItem):
                        continue
                    data = getattr(obj, "data", None)
                    sid = None
                    try:
                        sid = data.get("id") if isinstance(data, dict) else None
                    except Exception:
                        sid = None
                    match_identity = bool(isinstance(data, dict) and id(data) in data_ref_ids)
                    match_id = bool(sid is not None and str(sid) in text_ids)
                    if not (match_identity or match_id):
                        continue
                    try:
                        obj.setSelected(False)
                        obj.setCacheMode(QGraphicsItem.CacheMode.NoCache)
                        obj.setVisible(False)
                    except Exception:
                        pass
                    try:
                        scene.removeItem(obj)
                    except RuntimeError:
                        continue
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
        try:
            if removed:
                self.audit_boundary_event(
                    "TEXT_SCENE_ITEMS_REMOVED_BY_IDENTITY",
                    reason=str(reason or ""),
                    count=removed,
                    ids=sorted(text_ids),
                    throttle_ms=100,
                )
        except Exception:
            pass
        return removed

    def _purge_orphan_text_scene_items(self, reason=""):
        """Remove TypesettingItems whose data dict is no longer present on this page.

        This is a safety net for text delete/undo/redo after the undo refactor.  A
        scene item can survive after its backing row was removed from curr['data']; if
        undo later recreates the row, the orphan remains as a duplicate unselectable
        text object.  Keep items only when their data object or id exists in page data.
        """
        scene = self._safe_graphics_scene() if hasattr(self, "_safe_graphics_scene") else getattr(getattr(self, "view", None), "scene", None)
        curr = self.data.get(self.idx) if isinstance(getattr(self, "data", None), dict) else None
        if scene is None or not isinstance(curr, dict):
            return 0
        data_list = curr.get("data", []) or []
        live_ref_ids = {id(d) for d in data_list if isinstance(d, dict)}
        live_ids = {str(d.get("id")) for d in data_list if isinstance(d, dict) and d.get("id") is not None}
        removed = 0
        old_block = None
        try:
            old_block = scene.blockSignals(True)
        except Exception:
            old_block = None
        try:
            for obj in list(scene.items()):
                try:
                    if not isinstance(obj, TypesettingItem):
                        continue
                    data = getattr(obj, "data", None)
                    sid = None
                    try:
                        sid = data.get("id") if isinstance(data, dict) else None
                    except Exception:
                        sid = None
                    is_live_ref = isinstance(data, dict) and id(data) in live_ref_ids
                    is_live_id = sid is not None and str(sid) in live_ids
                    if is_live_ref or is_live_id:
                        continue
                    try:
                        obj.setSelected(False)
                        obj.setCacheMode(QGraphicsItem.CacheMode.NoCache)
                        obj.setVisible(False)
                    except Exception:
                        pass
                    try:
                        scene.removeItem(obj)
                    except RuntimeError:
                        continue
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
        try:
            if removed:
                self.audit_boundary_event(
                    "TEXT_ORPHAN_SCENE_ITEMS_PURGED",
                    reason=str(reason or ""),
                    count=removed,
                    data_count=len(data_list),
                    throttle_ms=100,
                )
        except Exception:
            pass
        return removed

    def _enter_text_scene_mutation_timer_guard(self, reason="text_scene_mutation"):
        """Block view/clone fast-path timers while text scene items are replaced.

        Qt access violations were observed when source-compare/view fast-path timer
        callbacks restored render hints while finish_inline_text_edit() was removing
        and recreating TypesettingItem objects.  Treat text-layer mutation as a
        short critical section: stop/coalesce timers first, then let the caller
        mutate the scene, and resume clone sync after the event loop turns.
        """
        try:
            depth = int(getattr(self, "_text_scene_mutation_guard_depth", 0) or 0) + 1
        except Exception:
            depth = 1
        self._text_scene_mutation_guard_depth = depth
        self._text_scene_mutation_lock = True
        try:
            self.audit_boundary_event(
                "TEXT_SCENE_MUTATION_TIMER_GUARD_ENTER",
                reason=str(reason or ""),
                depth=depth,
                throttle_ms=100,
            )
        except Exception:
            pass
        # Stop periodic/queued clone sync.  Already queued singleShot callbacks also
        # check _text_scene_mutation_lock before doing work.
        try:
            timer = getattr(self, "_source_compare_sync_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
                self._source_compare_sync_resume_after_text_mutation = True
        except Exception:
            pass
        try:
            timer = getattr(self, "_source_compare_fast_path_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
        except Exception:
            pass
        # Do NOT execute fast-path finish callbacks inside the mutation guard.
        # Finishing restores render hints/cache modes and may touch QGraphicsView
        # while text items are about to be removed/recreated.  Just mark them as
        # pending; _release_text_scene_mutation_timer_guard() restores them after
        # the scene mutation finishes and the event loop turns.
        try:
            state = getattr(self, "_source_compare_fast_path_state", None)
            if isinstance(state, dict) and state.get("active"):
                self._source_compare_fast_path_finish_pending = True
        except Exception:
            pass
        try:
            view = getattr(self, "view", None)
            if view is not None and getattr(view, "_view_interaction_fast_path_active", False):
                view._view_interaction_fast_path_finish_pending = True
        except Exception:
            pass
        try:
            timer = getattr(getattr(self, "view", None), "_view_interaction_fast_path_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
        except Exception:
            pass

    def _release_text_scene_mutation_timer_guard(self, reason="text_scene_mutation"):
        try:
            depth = int(getattr(self, "_text_scene_mutation_guard_depth", 0) or 0) - 1
        except Exception:
            depth = 0
        if depth > 0:
            self._text_scene_mutation_guard_depth = depth
            try:
                self.audit_boundary_event(
                    "TEXT_SCENE_MUTATION_TIMER_GUARD_HOLD",
                    reason=str(reason or ""),
                    depth=depth,
                    throttle_ms=100,
                )
            except Exception:
                pass
            return
        self._text_scene_mutation_guard_depth = 0
        self._text_scene_mutation_lock = False
        try:
            self.audit_boundary_event(
                "TEXT_SCENE_MUTATION_TIMER_GUARD_RELEASE",
                reason=str(reason or ""),
                throttle_ms=100,
            )
        except Exception:
            pass

        def _resume_after_text_mutation():
            try:
                if getattr(self, "_text_scene_mutation_lock", False):
                    return
                try:
                    view = getattr(self, "view", None)
                    if view is not None and getattr(view, "_view_interaction_fast_path_finish_pending", False):
                        view._view_interaction_fast_path_finish_pending = False
                        if hasattr(view, "_finish_view_interaction_fast_path"):
                            view._finish_view_interaction_fast_path(force=True)
                except Exception:
                    pass
                try:
                    if getattr(self, "_source_compare_fast_path_finish_pending", False):
                        self._source_compare_fast_path_finish_pending = False
                        if hasattr(self, "_finish_source_compare_clone_fast_path"):
                            self._finish_source_compare_clone_fast_path(force=True)
                except Exception:
                    pass
                try:
                    if getattr(self, "_source_compare_sync_resume_after_text_mutation", False):
                        self._source_compare_sync_resume_after_text_mutation = False
                        if hasattr(self, "start_source_compare_sync_timer"):
                            self.start_source_compare_sync_timer()
                        if hasattr(self, "schedule_source_compare_sync"):
                            self.schedule_source_compare_sync(30)
                except Exception:
                    pass
            except Exception:
                pass

        try:
            QTimer.singleShot(30, _resume_after_text_mutation)
        except Exception:
            _resume_after_text_mutation()


    def _is_renderable_text_data_item(self, data_item):
        """Return True only for text rows that should create a TypesettingItem in final mode.

        curr['data'] can contain OCR rows that are unchecked, empty, or otherwise table-only.
        Comparing the scene item count against the raw table length makes normal pages look
        broken (for example scene_count=4/data_count=12) and triggers unnecessary full
        resync after text effects.  The final scene is drawn with the same predicate as
        MuleImageViewer.draw_movable_texts(), so all sanity checks must use that predicate.
        """
        if not isinstance(data_item, dict):
            return False
        try:
            # 쯔꾸르붕이 행은 우측 표/게임식 대사창 프리뷰 전용이다.
            # YSB 식질용 TypesettingItem으로 캔버스에 만들지 않는다.
            if isinstance(data_item.get('maker_text_unit'), dict):
                return False
            if not bool(data_item.get('use_inpaint', True)):
                return False
        except Exception:
            return False
        try:
            if not str(data_item.get('translated_text', '') or '').strip() and not data_item.get('force_show'):
                return False
        except Exception:
            return False
        try:
            return data_item.get('id') is not None
        except Exception:
            return False

    def _safe_text_scene_current_ids(self):
        """Return (scene_ids, renderable_data_ids, selected_ids) for final text layer checks."""
        scene_ids, data_ids, selected_ids = set(), set(), []
        try:
            scene = self._safe_graphics_scene() if hasattr(self, "_safe_graphics_scene") else getattr(getattr(self, "view", None), "scene", None)
        except Exception:
            scene = None
        if scene is not None:
            try:
                for obj in list(scene.items()):
                    try:
                        if not isinstance(obj, TypesettingItem):
                            continue
                        data = getattr(obj, "data", {}) or {}
                        sid = data.get("id") if isinstance(data, dict) else None
                        if sid is None:
                            continue
                        # Hidden TypesettingItems do not participate in the visible final layer.
                        # They can temporarily exist during refresh, but treating them as a real
                        # scene/data mismatch causes needless resync loops.
                        try:
                            if not obj.isVisible():
                                continue
                        except Exception:
                            pass
                        scene_ids.add(str(sid))
                        if obj.isSelected():
                            selected_ids.append(sid)
                    except RuntimeError:
                        continue
                    except Exception:
                        continue
            except Exception:
                pass
        try:
            curr = self.data.get(self.idx) if isinstance(getattr(self, "data", None), dict) else None
            for d in (curr.get("data", []) if isinstance(curr, dict) else []):
                if self._is_renderable_text_data_item(d):
                    data_ids.add(str(d.get("id")))
        except Exception:
            pass
        return scene_ids, data_ids, selected_ids

    def schedule_safe_text_scene_resync(self, reason="text_scene_resync", selected_ids=None, delay_ms=40, table_refresh=False):
        """Queue a single safe text scene/data resync on the next event loop turn.

        Text delete/paste/undo can temporarily leave live TypesettingItem objects out of
        sync with curr['data'].  Calling mode_chg(4) immediately from the same key/mouse
        event can crash Qt because stale selected QGraphicsItems may still be referenced.
        This barrier stores only text IDs, lets the current event unwind, then rebuilds
        the text layer from data in one guarded pass.
        """
        try:
            if int(self.cb_mode.currentIndex()) != 4:
                return False
        except Exception:
            return False
        ids = []
        try:
            ids.extend([x for x in (selected_ids or []) if x is not None])
        except Exception:
            pass
        try:
            _, _, live_selected = self._safe_text_scene_current_ids()
            ids.extend([x for x in live_selected if x is not None])
        except Exception:
            pass
        # De-duplicate while preserving order.
        seen = set()
        normalized = []
        for x in ids:
            key = str(x)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(x)

        try:
            pending = list(getattr(self, "_pending_safe_text_scene_resync_selected_ids", []) or [])
        except Exception:
            pending = []
        for x in normalized:
            if str(x) not in {str(y) for y in pending}:
                pending.append(x)
        self._pending_safe_text_scene_resync_selected_ids = pending
        self._pending_safe_text_scene_resync_reason = str(reason or "text_scene_resync")
        self._pending_safe_text_scene_resync_table_refresh = bool(
            getattr(self, "_pending_safe_text_scene_resync_table_refresh", False) or table_refresh
        )

        try:
            self.audit_boundary_event(
                "TEXT_SCENE_RESYNC_BARRIER_QUEUED",
                reason=self._pending_safe_text_scene_resync_reason,
                selected_count=len(pending),
                delay_ms=int(delay_ms or 0),
                throttle_ms=100,
            )
        except Exception:
            pass

        try:
            if getattr(self, "_text_item_drag_active", False):
                delay_ms = max(int(delay_ms or 0), 180)
                try:
                    self.audit_boundary_event(
                        "TEXT_SCENE_RESYNC_DEFERRED_DURING_TEXT_DRAG",
                        reason=self._pending_safe_text_scene_resync_reason,
                        selected_count=len(pending),
                        delay_ms=int(delay_ms or 0),
                        throttle_ms=120,
                    )
                except Exception:
                    pass
        except Exception:
            pass
        try:
            timer = getattr(self, "_safe_text_scene_resync_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._run_safe_text_scene_resync)
                self._safe_text_scene_resync_timer = timer
            timer.stop()
            timer.start(max(0, int(delay_ms or 0)))
            return True
        except Exception:
            try:
                QTimer.singleShot(max(0, int(delay_ms or 0)), self._run_safe_text_scene_resync)
                return True
            except Exception:
                return False

    def _run_safe_text_scene_resync(self):
        """Safely rebuild final text scene from curr['data'] after event handlers unwind."""
        if getattr(self, "_safe_text_scene_resync_active", False):
            try:
                self.schedule_safe_text_scene_resync("resync_reentrant", delay_ms=60)
            except Exception:
                pass
            return
        try:
            if int(self.cb_mode.currentIndex()) != 4:
                return
        except Exception:
            return
        if getattr(self, "_text_item_drag_active", False):
            try:
                self.audit_boundary_event(
                    "TEXT_SCENE_RESYNC_RUN_DEFERRED_DURING_TEXT_DRAG",
                    reason=str(getattr(self, "_pending_safe_text_scene_resync_reason", "text_scene_resync") or "text_scene_resync"),
                    throttle_ms=120,
                )
            except Exception:
                pass
            try:
                self.schedule_safe_text_scene_resync("resync_deferred_text_drag", delay_ms=180)
            except Exception:
                pass
            return
        if getattr(self, "is_page_loading", False) or getattr(self, "is_batch_running", False):
            try:
                self.schedule_safe_text_scene_resync("resync_deferred_loading", delay_ms=80)
            except Exception:
                pass
            return

        selected_ids = list(getattr(self, "_pending_safe_text_scene_resync_selected_ids", []) or [])
        reason = str(getattr(self, "_pending_safe_text_scene_resync_reason", "text_scene_resync") or "text_scene_resync")
        table_refresh = bool(getattr(self, "_pending_safe_text_scene_resync_table_refresh", False))
        self._pending_safe_text_scene_resync_selected_ids = []
        self._pending_safe_text_scene_resync_table_refresh = False

        self._safe_text_scene_resync_active = True
        old_suppress = getattr(self, "_suppress_mode_undo", False)
        old_rebuild = getattr(self, "_is_rebuilding_text_layer", False)
        try:
            try:
                self.audit_boundary_event("TEXT_SCENE_RESYNC_BARRIER_ENTER", reason=reason, selected_count=len(selected_ids), throttle_ms=100)
            except Exception:
                pass
            try:
                self._enter_text_scene_mutation_timer_guard(reason="safe_text_scene_resync")
            except Exception:
                pass
            try:
                timer = getattr(self, "_final_text_light_refresh_timer", None)
                if timer is not None and timer.isActive():
                    timer.stop()
            except Exception:
                pass
            try:
                if hasattr(self, "_remove_inline_text_editor_from_scene"):
                    self._remove_inline_text_editor_from_scene()
            except Exception:
                pass
            scene = None
            try:
                scene = self._safe_graphics_scene() if hasattr(self, "_safe_graphics_scene") else getattr(getattr(self, "view", None), "scene", None)
            except Exception:
                scene = None
            removed = 0
            old_block = None
            if scene is not None:
                try:
                    old_block = scene.blockSignals(True)
                except Exception:
                    old_block = None
                try:
                    try:
                        scene.clearSelection()
                    except Exception:
                        pass
                    for obj in list(scene.items()):
                        try:
                            if not isinstance(obj, TypesettingItem):
                                continue
                            obj.setSelected(False)
                            obj.setCacheMode(QGraphicsItem.CacheMode.NoCache)
                            obj.setVisible(False)
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
            try:
                self.audit_boundary_event("TEXT_SCENE_RESYNC_BARRIER_PURGE", reason=reason, removed=removed, throttle_ms=100)
            except Exception:
                pass
            self._suppress_mode_undo = True
            self._is_rebuilding_text_layer = True
            try:
                self.mode_chg(4)
            except Exception:
                pass
            try:
                if table_refresh:
                    self.ref_tab()
                    try:
                        self.audit_boundary_event(
                            "TEXT_TABLE_REFRESH_AFTER_RASTER_MODE_RESYNC",
                            reason=reason,
                            ids=','.join(str(x) for x in selected_ids),
                            throttle_ms=100,
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            if selected_ids:
                try:
                    self.reselect_text_items(selected_ids)
                except Exception:
                    pass
            try:
                self.force_update_final_scene_region()
            except Exception:
                try:
                    scene = self._safe_graphics_scene()
                    if scene is not None:
                        scene.update()
                except Exception:
                    pass
            try:
                scene_ids, data_ids, _ = self._safe_text_scene_current_ids()
                still_mismatch = set(scene_ids) != set(data_ids)
                self.audit_boundary_event(
                    "TEXT_SCENE_RESYNC_BARRIER_DONE",
                    reason=reason,
                    scene_count=len(scene_ids),
                    data_count=len(data_ids),
                    selected_count=len(selected_ids),
                    still_mismatch=bool(still_mismatch),
                    throttle_ms=100,
                )
                if still_mismatch:
                    self.audit_boundary_event(
                        "TEXT_SCENE_RESYNC_BARRIER_STILL_MISMATCH",
                        reason=reason,
                        scene_ids=sorted(scene_ids),
                        data_ids=sorted(data_ids),
                        throttle_ms=500,
                    )
            except Exception:
                pass
        finally:
            self._is_rebuilding_text_layer = old_rebuild
            self._suppress_mode_undo = old_suppress
            self._safe_text_scene_resync_active = False
            try:
                self._release_text_scene_mutation_timer_guard(reason="safe_text_scene_resync")
            except Exception:
                pass

    def _prepare_text_scene_mutation_safety(self, reason="text_scene_mutation", selected_ids=None):
        """Quiesce view/scene state before replacing live text items.

        Inline text commit can remove/recreate QGraphicsItems while the viewport,
        clone view fast path, selectionChanged signal, or item cache is still in
        flight.  Native Qt access violations happen in that tiny window, so keep
        this helper deliberately conservative and best-effort.
        """
        try:
            self.audit_boundary_event(
                "TEXT_SCENE_MUTATION_SAFETY_ENTER",
                reason=str(reason or ""),
                selected_ids=list(selected_ids or []),
                throttle_ms=100,
            )
        except Exception:
            pass
        try:
            self._enter_text_scene_mutation_timer_guard(reason=reason)
        except Exception:
            pass
        # Do not run view/source-compare fast-path finish callbacks here.  They
        # restore QGraphicsView render state and can re-enter painting while text
        # scene items are being replaced.  _enter_text_scene_mutation_timer_guard()
        # only marks pending restores; release resumes them after mutation.
        try:
            view = getattr(self, "view", None)
            if view is not None and getattr(view, "_view_interaction_fast_path_active", False):
                view._view_interaction_fast_path_finish_pending = True
        except Exception:
            pass
        try:
            state = getattr(self, "_source_compare_fast_path_state", None)
            if isinstance(state, dict) and state.get("active"):
                self._source_compare_fast_path_finish_pending = True
        except Exception:
            pass
        scene = None
        try:
            scene = self._safe_graphics_scene() if hasattr(self, "_safe_graphics_scene") else getattr(getattr(self, "view", None), "scene", None)
        except Exception:
            scene = None
        old_block = None
        if scene is not None:
            try:
                old_block = scene.blockSignals(True)
            except Exception:
                old_block = None
            try:
                scene.clearSelection()
            except Exception:
                pass
            try:
                for obj in list(scene.items()):
                    try:
                        if isinstance(obj, TypesettingItem):
                            obj.setSelected(False)
                            obj.setCacheMode(QGraphicsItem.CacheMode.NoCache)
                    except RuntimeError:
                        continue
                    except Exception:
                        continue
            except Exception:
                pass
            try:
                if old_block is not None:
                    scene.blockSignals(old_block)
            except Exception:
                pass
        try:
            editor = getattr(self, "inline_text_editor", None)
            if editor is not None:
                editor._closing = True
                try:
                    editor.clearFocus()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.audit_boundary_event("TEXT_SCENE_MUTATION_SAFETY_DONE", reason=str(reason or ""), throttle_ms=100)
        except Exception:
            pass

    def _file_dialog_log(self, event, **fields):
        try:
            self.audit_boundary_event(event, **fields)
        except Exception:
            pass

    def file_dialog_last_dirs_path(self):
        try:
            return get_cache_file("file_dialog_last_dirs.json")
        except Exception:
            return Path(os.path.join(str(get_cache_dir()), "file_dialog_last_dirs.json"))

    def load_file_dialog_last_dirs(self):
        try:
            p = self.file_dialog_last_dirs_path()
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def save_file_dialog_last_dirs(self, data):
        try:
            p = self.file_dialog_last_dirs_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data if isinstance(data, dict) else {}, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def file_dialog_reason_key(self, reason):
        reason = str(reason or "default")
        # 같은 성격의 열기는 같은 마지막 위치를 공유한다.
        mapping = {
            "open_project_ysbt": "open_project",
            "open_project_json": "open_project_json",
            "import_images_action": "import_images",
            "new_project_from_images": "import_images",
            "import_clean_background": "import_clean_background",
            "import_translation_txt": "import_translation_txt",
            "import_page_preset": "import_page_preset",
            "import_item_preset": "import_item_preset",
        }
        return mapping.get(reason, reason)

    def resolve_file_dialog_start_dir(self, reason, fallback_dir):
        key = self.file_dialog_reason_key(reason)
        data = self.load_file_dialog_last_dirs()
        saved = str(data.get(key) or "").strip()
        if saved and os.path.isdir(saved):
            self._file_dialog_log("FILE_DIALOG_LAST_DIR_USED", reason=str(reason), key=key, directory=saved, source="last")
            return saved
        fallback = str(fallback_dir or "").strip()
        if fallback and os.path.isdir(fallback):
            self._file_dialog_log("FILE_DIALOG_LAST_DIR_USED", reason=str(reason), key=key, directory=fallback, source="fallback")
            return fallback
        self._file_dialog_log("FILE_DIALOG_LAST_DIR_USED", reason=str(reason), key=key, directory=fallback, source="empty")
        return fallback

    def update_file_dialog_last_dir(self, reason, selected):
        if not selected:
            return False
        try:
            first = selected[0] if isinstance(selected, (list, tuple)) else selected
            path = str(first or "").strip()
            if not path:
                return False
            directory = path if os.path.isdir(path) else os.path.dirname(path)
            if not directory or not os.path.isdir(directory):
                return False
            key = self.file_dialog_reason_key(reason)
            data = self.load_file_dialog_last_dirs()
            old = data.get(key)
            data[key] = directory
            ok = self.save_file_dialog_last_dirs(data)
            self._file_dialog_log("FILE_DIALOG_LAST_DIR_SAVED", reason=str(reason), key=key, directory=directory, changed=(old != directory), ok=bool(ok))
            return ok
        except Exception as e:
            self._file_dialog_log("FILE_DIALOG_LAST_DIR_SAVE_ERROR", reason=str(reason), error=str(e))
            return False

    def file_dialog_options_for_current_setting(self):
        try:
            if bool(getattr(self, "use_light_file_dialog", True)):
                return QFileDialog.Option.DontUseNativeDialog
        except Exception:
            pass
        try:
            return QFileDialog.Option(0)
        except Exception:
            return QFileDialog.Option()

    def _use_light_qt_file_dialog(self):
        try:
            return bool(getattr(self, "use_light_file_dialog", True))
        except Exception:
            return True

    def _file_dialog_tr(self, ko_text, en_text=None):
        try:
            if str(getattr(self, "ui_language", LANG_KO)).lower().startswith("en"):
                return str(en_text if en_text is not None else ko_text)
        except Exception:
            pass
        return str(ko_text)

    def _file_dialog_sidebar_urls(self):
        urls = []
        seen = set()

        def add_path(path):
            try:
                path = str(path or "").strip()
                if not path or not os.path.isdir(path):
                    return
                norm = os.path.normcase(os.path.abspath(path))
                if norm in seen:
                    return
                seen.add(norm)
                urls.append(QUrl.fromLocalFile(path))
            except Exception:
                pass

        try:
            # 사용자가 바로 접근하는 위치를 먼저 둔다.
            add_path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation))
            add_path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation))
            add_path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation))
            add_path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation))
        except Exception:
            pass
        try:
            # 현재 작업 폴더도 있으면 편의 위치로 추가한다.
            add_path(str(default_package_dir()))
        except Exception:
            pass
        return urls

    def _configure_light_file_dialog(self, dialog, *, accept_mode="open", directory_mode=False):
        try:
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        except Exception:
            pass
        try:
            dialog.setLabelText(QFileDialog.DialogLabel.LookIn, self._file_dialog_tr("위치:", "Look in:"))
            dialog.setLabelText(QFileDialog.DialogLabel.FileName, self._file_dialog_tr("파일 이름:", "File name:"))
            dialog.setLabelText(QFileDialog.DialogLabel.FileType, self._file_dialog_tr("파일 형식:", "Files of type:"))
            dialog.setLabelText(QFileDialog.DialogLabel.Accept, self._file_dialog_tr("열기" if accept_mode == "open" else "선택", "Open" if accept_mode == "open" else "Select"))
            dialog.setLabelText(QFileDialog.DialogLabel.Reject, self._file_dialog_tr("취소", "Cancel"))
        except Exception:
            pass
        try:
            sidebar = self._file_dialog_sidebar_urls()
            if sidebar:
                dialog.setSidebarUrls(sidebar)
        except Exception:
            pass
        try:
            if directory_mode:
                dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        except Exception:
            pass
        return dialog

    def _get_open_file_name_light(self, parent, caption, directory, filter_text):
        dlg = QFileDialog(parent, caption, directory, filter_text)
        self._configure_light_file_dialog(dlg, accept_mode="open")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
        try:
            if filter_text:
                dlg.selectNameFilter(str(filter_text).split(";;")[0])
        except Exception:
            pass
        if dlg.exec():
            files = dlg.selectedFiles()
            return (files[0] if files else ""), dlg.selectedNameFilter()
        return "", dlg.selectedNameFilter()

    def _get_open_file_names_light(self, parent, caption, directory, filter_text):
        dlg = QFileDialog(parent, caption, directory, filter_text)
        self._configure_light_file_dialog(dlg, accept_mode="open")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
        try:
            if filter_text:
                dlg.selectNameFilter(str(filter_text).split(";;")[0])
        except Exception:
            pass
        if dlg.exec():
            return dlg.selectedFiles(), dlg.selectedNameFilter()
        return [], dlg.selectedNameFilter()

    def _get_existing_directory_light(self, parent, caption, directory):
        dlg = QFileDialog(parent, caption, directory)
        self._configure_light_file_dialog(dlg, accept_mode="select", directory_mode=True)
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dlg.setFileMode(QFileDialog.FileMode.Directory)
        if dlg.exec():
            files = dlg.selectedFiles()
            return files[0] if files else ""
        return ""

    def _file_dialog_process_events_logged(self, dialog_id, reason):
        try:
            t = time.time()
            self._file_dialog_log("FILE_DIALOG_PROCESS_EVENTS_ENTER", dialog_id=dialog_id, reason=str(reason))
            try:
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            except Exception:
                QApplication.processEvents()
            self._file_dialog_log("FILE_DIALOG_PROCESS_EVENTS_DONE", dialog_id=dialog_id, reason=str(reason), elapsed_ms=int((time.time() - t) * 1000))
        except Exception:
            pass

    def get_open_file_name_logged(self, reason, parent, caption, directory, filter_text):
        dialog_id = f"{reason}_{int(time.time() * 1000)}"
        t0 = time.time()
        directory = self.resolve_file_dialog_start_dir(reason, directory)
        options = self.file_dialog_options_for_current_setting()
        self._file_dialog_log("FILE_DIALOG_OPEN_ENTER", dialog_id=dialog_id, reason=str(reason), caption=str(caption), directory=str(directory), light_dialog=bool(getattr(self, "use_light_file_dialog", True)))
        self._file_dialog_process_events_logged(dialog_id, reason)
        try:
            self._file_dialog_log("FILE_DIALOG_NATIVE_CALL_ENTER", dialog_id=dialog_id, reason=str(reason))
            call_t = time.time()
            if self._use_light_qt_file_dialog():
                path, selected_filter = self._get_open_file_name_light(parent, caption, directory, filter_text)
            else:
                path, selected_filter = QFileDialog.getOpenFileName(parent, caption, directory, filter_text, "", options)
            self._file_dialog_log("FILE_DIALOG_NATIVE_CALL_RETURN", dialog_id=dialog_id, reason=str(reason), elapsed_ms=int((time.time() - call_t) * 1000), selected=bool(path))
            if path:
                self.update_file_dialog_last_dir(reason, path)
            elapsed = int((time.time() - t0) * 1000)
            self._file_dialog_log("FILE_DIALOG_OPEN_DONE", dialog_id=dialog_id, reason=str(reason), elapsed_ms=elapsed, selected=bool(path), path_ext=os.path.splitext(str(path or ""))[1])
            return path, selected_filter
        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            self._file_dialog_log("FILE_DIALOG_OPEN_ERROR", dialog_id=dialog_id, reason=str(reason), elapsed_ms=elapsed, error=str(e))
            raise

    def get_open_file_names_logged(self, reason, parent, caption, directory, filter_text):
        dialog_id = f"{reason}_{int(time.time() * 1000)}"
        t0 = time.time()
        directory = self.resolve_file_dialog_start_dir(reason, directory)
        options = self.file_dialog_options_for_current_setting()
        self._file_dialog_log("FILE_DIALOG_OPEN_ENTER", dialog_id=dialog_id, reason=str(reason), caption=str(caption), directory=str(directory), multi=True, light_dialog=bool(getattr(self, "use_light_file_dialog", True)))
        self._file_dialog_process_events_logged(dialog_id, reason)
        try:
            self._file_dialog_log("FILE_DIALOG_NATIVE_CALL_ENTER", dialog_id=dialog_id, reason=str(reason), multi=True)
            call_t = time.time()
            if self._use_light_qt_file_dialog():
                paths, selected_filter = self._get_open_file_names_light(parent, caption, directory, filter_text)
            else:
                paths, selected_filter = QFileDialog.getOpenFileNames(parent, caption, directory, filter_text, "", options)
            self._file_dialog_log("FILE_DIALOG_NATIVE_CALL_RETURN", dialog_id=dialog_id, reason=str(reason), elapsed_ms=int((time.time() - call_t) * 1000), selected=bool(paths), count=len(paths or []), multi=True)
            if paths:
                self.update_file_dialog_last_dir(reason, paths)
            elapsed = int((time.time() - t0) * 1000)
            self._file_dialog_log("FILE_DIALOG_OPEN_DONE", dialog_id=dialog_id, reason=str(reason), elapsed_ms=elapsed, selected=bool(paths), count=len(paths or []))
            return paths, selected_filter
        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            self._file_dialog_log("FILE_DIALOG_OPEN_ERROR", dialog_id=dialog_id, reason=str(reason), elapsed_ms=elapsed, error=str(e))
            raise

    def get_existing_directory_logged(self, reason, parent, caption, directory):
        dialog_id = f"{reason}_{int(time.time() * 1000)}"
        t0 = time.time()
        directory = self.resolve_file_dialog_start_dir(reason, directory)
        options = self.file_dialog_options_for_current_setting()
        self._file_dialog_log("FILE_DIALOG_OPEN_ENTER", dialog_id=dialog_id, reason=str(reason), caption=str(caption), directory=str(directory), directory_mode=True, light_dialog=bool(getattr(self, "use_light_file_dialog", True)))
        self._file_dialog_process_events_logged(dialog_id, reason)
        try:
            self._file_dialog_log("FILE_DIALOG_NATIVE_CALL_ENTER", dialog_id=dialog_id, reason=str(reason), directory_mode=True)
            call_t = time.time()
            if self._use_light_qt_file_dialog():
                path = self._get_existing_directory_light(parent, caption, directory)
            else:
                path = QFileDialog.getExistingDirectory(parent, caption, directory, options)
            self._file_dialog_log("FILE_DIALOG_NATIVE_CALL_RETURN", dialog_id=dialog_id, reason=str(reason), elapsed_ms=int((time.time() - call_t) * 1000), selected=bool(path), directory_mode=True)
            if path:
                self.update_file_dialog_last_dir(reason, path)
            elapsed = int((time.time() - t0) * 1000)
            self._file_dialog_log("FILE_DIALOG_OPEN_DONE", dialog_id=dialog_id, reason=str(reason), elapsed_ms=elapsed, selected=bool(path), directory_mode=True)
            return path
        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            self._file_dialog_log("FILE_DIALOG_OPEN_ERROR", dialog_id=dialog_id, reason=str(reason), elapsed_ms=elapsed, error=str(e), directory_mode=True)
            raise

    def selected_text_items(self):
        if getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
            return []
        scene = self._safe_graphics_scene()
        if scene is None:
            return []
        try:
            return [item for item in scene.selectedItems() if isinstance(item, TypesettingItem)]
        except RuntimeError:
            return []
        except Exception:
            return []

    def _set_widget_value_blocked(self, widget, value):
        """프로그램이 UI 값을 채울 때 valueChanged 재발동/포커스 튐을 막는다."""
        if widget is None:
            return
        blocker = None
        try:
            blocker = QSignalBlocker(widget)
        except Exception:
            blocker = None
        try:
            widget.setValue(value)
        except Exception:
            pass
        finally:
            try:
                del blocker
            except Exception:
                pass

    def _set_widget_checked_blocked(self, widget, checked):
        if widget is None:
            return
        blocker = None
        try:
            blocker = QSignalBlocker(widget)
        except Exception:
            blocker = None
        try:
            widget.setChecked(bool(checked))
        except Exception:
            pass
        finally:
            try:
                del blocker
            except Exception:
                pass

    def _live_text_content_scene_rect_for_data(self, data_item):
        """Return the currently visible TypesettingItem text bounds for this data row.

        The reset-text-rect action is explicitly based on the *current visible text*.
        After the undo/timeline refactor, some final-tab items can have live preview
        geometry that is newer than the pure data-based estimator.  Prefer the live
        TypesettingItem when it is available, and fall back to the 2.4.1 estimator for
        unloaded pages / batch work.
        """
        if not isinstance(data_item, dict):
            return None
        try:
            if int(self.cb_mode.currentIndex()) != 4:
                return None
        except Exception:
            return None
        # Live scene items only represent the currently loaded page.  During batch
        # processing other pages can reuse the same text ids, so never bind a
        # non-current page data row to the current scene item just because the id
        # matches.
        try:
            curr = self.data.get(self.idx) if hasattr(self, 'data') else None
            curr_items = curr.get('data', []) if isinstance(curr, dict) else []
            if all(data_item is not x for x in (curr_items or [])):
                return None
        except Exception:
            return None
        scene = self._safe_graphics_scene() if hasattr(self, "_safe_graphics_scene") else getattr(getattr(self, "view", None), "scene", None)
        if scene is None:
            return None
        target_id = data_item.get('id')
        candidates = []
        try:
            for item in list(scene.items()):
                try:
                    if not isinstance(item, TypesettingItem):
                        continue
                    item_data = getattr(item, 'data', None)
                    if item_data is data_item:
                        candidates.insert(0, item)
                        continue
                    if target_id is not None and isinstance(item_data, dict) and str(item_data.get('id')) == str(target_id):
                        candidates.append(item)
                except RuntimeError:
                    continue
                except Exception:
                    continue
        except Exception:
            candidates = []
        for item in candidates:
            try:
                if hasattr(item, 'text_content_scene_rect'):
                    rect = item.text_content_scene_rect()
                else:
                    rect = item.mapToScene(item.path().boundingRect()).boundingRect()
                if rect is not None and (not rect.isNull()) and rect.width() > 0 and rect.height() > 0:
                    return rect
            except RuntimeError:
                continue
            except Exception:
                continue
        return None

    def calculate_tight_text_scene_rect(self, data_item):
        """data_item의 현재 번역문/스타일이 실제로 차지하는 scene rect를 계산한다.

        OCR 원본 박스는 처음 배치용으로 유지하되, 사용자가 텍스트를 한 번 수정하면
        그 이후의 선택/변형 박스는 실제 텍스트 크기에 맞게 축소되어야 한다.
        Qt 문서 boundingRect 대신 TypesettingItem과 같은 QPainterPath 기준을 사용한다.
        """
        if not isinstance(data_item, dict):
            return None
        text = str(data_item.get('translated_text', '') or '')
        lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        if not lines:
            lines = ['']

        try:
            fallback_family = self.cb_font.currentFont().family() if hasattr(self, 'cb_font') else 'Arial'
        except Exception:
            fallback_family = 'Arial'
        try:
            fallback_size = int(self.sb_font_size.value()) if hasattr(self, 'sb_font_size') else 24
        except Exception:
            fallback_size = 24

        font = QFont(str(data_item.get('font_family') or fallback_family))
        try:
            font.setPixelSize(int(data_item.get('font_size', fallback_size) or fallback_size))
        except Exception:
            font.setPixelSize(fallback_size)
        try:
            font.setBold(bool(data_item.get('bold', False)))
            font.setItalic(bool(data_item.get('italic', False)))
            letter_spacing = int(data_item.get('letter_spacing', 0) or 0)
        except Exception:
            pass

        try:
            line_spacing_pct = max(50, min(300, int(data_item.get('line_spacing', 100) or 100)))
        except Exception:
            line_spacing_pct = 100
        try:
            char_width_pct = max(10, min(300, int(data_item.get('char_width', 100) or 100)))
        except Exception:
            char_width_pct = 100
        try:
            char_height_pct = max(10, min(300, int(data_item.get('char_height', 100) or 100)))
        except Exception:
            char_height_pct = 100

        align = (data_item.get('align') or getattr(self, 'default_align', 'center') or 'center').lower()
        if align not in ('left', 'center', 'right'):
            align = 'center'

        fm = QFontMetrics(font)
        line_height = max(1, int(fm.lineSpacing() * (line_spacing_pct / 100.0)))
        path, _line_rects = build_typesetting_text_path(lines, font, align, line_height, letter_spacing)

        if char_width_pct != 100 or char_height_pct != 100:
            tr = QTransform()
            tr.scale(char_width_pct / 100.0, char_height_pct / 100.0)
            path = tr.map(path)

        path_rect = path.boundingRect()
        if path_rect.isNull() or path_rect.width() <= 0 or path_rect.height() <= 0:
            path_rect = QRectF(0, 0, 1, max(1, fm.height()))

        rect = list(data_item.get('rect') or [0, 0, 1, 1])
        while len(rect) < 4:
            rect.append(1)
        x_off = float(data_item.get('x_off', 0) or 0)
        y_off = float(data_item.get('y_off', 0) or 0)
        rect_x = float(rect[0])
        rect_y = float(rect[1])
        rect_w = max(1.0, float(rect[2]))
        rect_h = max(1.0, float(rect[3]))
        text_w = max(1.0, float(path_rect.width()))
        text_h = max(1.0, float(path_rect.height()))

        if align == 'left':
            anchor_x = rect_x + x_off
            left = anchor_x
        elif align == 'right':
            anchor_x = rect_x + x_off + rect_w
            left = anchor_x - text_w
        else:
            anchor_x = rect_x + x_off + rect_w / 2.0
            left = anchor_x - text_w / 2.0

        # v1.6.3+: 텍스트는 영역의 세로 중심에 배치된다.
        anchor_y = rect_y + y_off + rect_h / 2.0
        top = anchor_y - text_h / 2.0

        return QRectF(left, top, text_w, text_h)

    def shrink_text_rect_to_content(self, data_item):
        """텍스트 수정 후 작업/변형 박스를 실제 텍스트 크기로 줄인다."""
        return self.ensure_text_anchor_rect(data_item, record_undo=False)

    def ensure_text_anchor_rect(self, data_item, record_undo=False, reason="텍스트 영역 자동 재생성"):
        """현재 보이는 실제 텍스트 bounds를 새 텍스트 영역으로 확정한다.

        초기 OCR 영역은 최초 배치용 기준일 뿐이다. 텍스트 직접 수정 또는
        텍스트 변형 모드 진입 시점에는 현재 화면에 보이는 실제 글자 영역을
        기준으로 rect를 다시 만들고, 이후 선택/변형 박스가 이 영역을 보게 한다.
        """
        if not isinstance(data_item, dict):
            return False
        # Prefer the live final-tab item because this action means "reset to the
        # currently visible text".  For batch/unloaded pages, fall back to the
        # data-based 2.4.1 estimator.
        rect = None
        try:
            rect = self._live_text_content_scene_rect_for_data(data_item)
        except Exception:
            rect = None
        if rect is None:
            rect = self.calculate_tight_text_scene_rect(data_item)
        if rect is None:
            return False

        new_rect = [
            int(round(rect.x())),
            int(round(rect.y())),
            max(1, int(round(rect.width()))),
            max(1, int(round(rect.height()))),
        ]
        old_rect = list(data_item.get('rect') or [])
        while len(old_rect) < 4:
            old_rect.append(0)
        try:
            old_rect4 = [int(round(float(v))) for v in old_rect[:4]]
        except Exception:
            old_rect4 = old_rect[:4]
        old_x = int(round(float(data_item.get('x_off', 0) or 0)))
        old_y = int(round(float(data_item.get('y_off', 0) or 0)))
        already_text_anchor = bool(data_item.get('manual_text_rect')) or str(data_item.get('text_anchor_mode') or '').lower() == 'text'
        changed = (
            old_rect4 != new_rect
            or old_x != 0
            or old_y != 0
            or not already_text_anchor
        )
        if not changed:
            return False

        if record_undo:
            try:
                self.push_page_text_undo(reason)
            except Exception:
                pass

        data_item['rect'] = new_rect
        data_item['x_off'] = 0
        data_item['y_off'] = 0
        data_item['manual_text_rect'] = True
        data_item['text_anchor_mode'] = 'text'
        return True

    def reset_text_rects_current(self):
        """현재 페이지의 모든 텍스트 영역을 현재 보이는 텍스트 bounds 기준으로 재생성한다."""
        if not self.paths or self.idx not in self.data:
            self.log("⚠️ 영역을 재설정할 현재 페이지가 없습니다.")
            return

        # 최종화면에서 드래그 이동한 좌표가 아직 data에 완전히 박히기 전일 수 있으므로
        # 먼저 현재 UI 상태를 data에 동기화한 뒤, 그 상태를 Undo 기준으로 저장한다.
        try:
            self.commit_current_page_ui_to_data(include_mask=False)
        except Exception:
            pass

        curr = self.data.get(self.idx) or {}
        items = [d for d in (curr.get('data', []) or []) if isinstance(d, dict)]
        if not items:
            self.log("⚠️ 영역을 재설정할 텍스트가 없습니다.")
            return

        selected_ids = []
        try:
            scene = self._safe_graphics_scene() if hasattr(self, "_safe_graphics_scene") else getattr(getattr(self, "view", None), "scene", None)
            if scene is not None:
                selected_ids = [getattr(x, 'data', {}).get('id') for x in scene.selectedItems() if isinstance(x, TypesettingItem)]
                selected_ids = [x for x in selected_ids if x is not None]
        except Exception:
            selected_ids = []

        # 2.4.1 안정 경로 유지: 영역 재설정은 page snapshot undo로 처리한다.
        # 화면 반영은 full rebuild/purge가 아니라 기존 TypesettingItem의 in-place refresh만 사용한다.
        # 이 작업은 텍스트 개수 변경이 아니라 rect/x_off/y_off 기준 변경이므로 scene item을 지우면 안 된다.
        undo_rec = self.make_project_undo_record("현재 텍스트 기준 영역 재설정")
        changed = 0
        changed_ids = []
        for d in items:
            try:
                if self.ensure_text_anchor_rect(d, record_undo=False, reason="현재 텍스트 기준 영역 재설정"):
                    changed += 1
                    sid = d.get('id')
                    if sid is not None:
                        changed_ids.append(sid)
            except Exception:
                continue

        if changed <= 0:
            self.log("↩️ 현재 텍스트 기준 영역 재설정: 변경된 영역이 없습니다.")
            return

        self.append_project_undo_record(undo_rec)
        try:
            self.mark_active_page_dirty('text')
        except Exception:
            try:
                if hasattr(self, 'project_engine') and self.project_engine is not None:
                    self.project_engine.mark_page_dirty(int(self.idx), 'text')
            except Exception:
                pass
        try:
            if hasattr(self, '_checkpoint_dirty_pages'):
                self._checkpoint_dirty_pages.add(int(self.idx))
            else:
                self._checkpoint_dirty_pages = {int(self.idx)}
            if not hasattr(self, '_checkpoint_dirty_kinds') or self._checkpoint_dirty_kinds is None:
                self._checkpoint_dirty_kinds = {}
            self._checkpoint_dirty_kinds.setdefault(int(self.idx), set()).add('text')
        except Exception:
            pass

        try:
            self.audit_boundary_event(
                "TEXT_REGION_RESET_APPLIED",
                changed=changed,
                changed_ids=','.join(str(x) for x in changed_ids),
                selected_count=len(selected_ids),
                page_idx=int(self.idx),
                refresh_path='in_place',
                throttle_ms=100,
            )
        except Exception:
            pass

        self.auto_save_project()
        self.ref_tab()
        if self.cb_mode.currentIndex() == 4:
            refreshed = False
            try:
                if changed_ids and hasattr(self, 'refresh_final_text_items_by_ids'):
                    refreshed = bool(self.refresh_final_text_items_by_ids(changed_ids))
            except Exception:
                refreshed = False
            try:
                if selected_ids:
                    self.reselect_text_items(selected_ids)
            except Exception:
                pass
            if not refreshed:
                try:
                    if hasattr(self, 'schedule_final_text_scene_refresh'):
                        self.schedule_final_text_scene_refresh(80)
                    else:
                        self.mode_chg(4)
                except Exception:
                    pass
        self.log(f"📐 현재 텍스트 기준 영역 재설정 완료: {changed}개")

    def reset_text_rects_batch(self):
        """선택한 페이지의 모든 텍스트 영역을 현재 텍스트 bounds 기준으로 일괄 재생성한다."""
        if not self.paths or not self.data:
            self.log("⚠️ 영역을 재설정할 프로젝트가 없습니다.")
            return

        title = "일괄 현재 텍스트 기준으로 영역 재설정"
        selected_indices, selected_label = self.choose_batch_page_indices_for_context(title, "reset_text_rects")
        if selected_indices is None:
            self.log("↩️ 일괄 텍스트 기준 영역 재설정 취소")
            return

        try:
            self.commit_current_page_ui_to_data(include_mask=False)
        except Exception:
            pass

        # 일괄 작업도 2.4.1처럼 각 페이지 data를 직접 수정하고, run_page_queue_batch의
        # 일괄 경계/워크캐시 흐름에 맡긴다. text_region_reset Command-Diff는 사용하지 않는다.
        current_page_changed_ids = []
        def process_page(page_idx):
            page_data = self.data.get(page_idx)
            if not isinstance(page_data, dict):
                return "skipped", "페이지 데이터 없음"
            items = [d for d in (page_data.get('data', []) or []) if isinstance(d, dict)]
            if not items:
                return "skipped", "텍스트 없음"
            page_changed = 0
            for d in items:
                try:
                    if self.ensure_text_anchor_rect(d, record_undo=False, reason=title):
                        page_changed += 1
                        try:
                            if int(page_idx) == int(self.idx) and d.get('id') is not None:
                                current_page_changed_ids.append(d.get('id'))
                        except Exception:
                            pass
                except Exception:
                    continue
            if page_changed <= 0:
                return "skipped", "변경된 영역 없음"
            try:
                if hasattr(self, 'project_engine') and self.project_engine is not None:
                    self.project_engine.mark_page_dirty(int(page_idx), 'text')
                pages = getattr(self, "_checkpoint_dirty_pages", None)
                if pages is None:
                    pages = set()
                    self._checkpoint_dirty_pages = pages
                pages.add(int(page_idx))
                kinds = getattr(self, "_checkpoint_dirty_kinds", None)
                if kinds is None:
                    kinds = {}
                    self._checkpoint_dirty_kinds = kinds
                kinds.setdefault(int(page_idx), set()).add("text")
            except Exception:
                pass
            return "done", f"{page_changed}개 재설정"

        result = self.run_page_queue_batch(title, "reset_text_rects", selected_indices, selected_label, process_page, visual=False, cancellable=True)
        try:
            self.ref_tab()
            if self.cb_mode.currentIndex() == 4 and current_page_changed_ids:
                refreshed = False
                try:
                    if hasattr(self, 'refresh_final_text_items_by_ids'):
                        refreshed = bool(self.refresh_final_text_items_by_ids(current_page_changed_ids))
                except Exception:
                    refreshed = False
                if not refreshed:
                    try:
                        if hasattr(self, 'schedule_final_text_scene_refresh'):
                            self.schedule_final_text_scene_refresh(80)
                        else:
                            self.mode_chg(4)
                    except Exception:
                        pass
        except Exception:
            pass


    def start_inline_text_edit(self, text_item, select_all=False):
        """최종 화면 텍스트를 더블클릭/F2 했을 때 그 자리에서 직접 편집한다."""
        if self.cb_mode.currentIndex() != 4:
            return

        if self.inline_text_editor is not None:
            self.finish_inline_text_edit(commit=True, refresh=False)

        if text_item is None:
            return
        if bool(getattr(text_item, 'data', {}).get('rasterized_text')):
            self.log("⚠️ " + self.tr_ui("객체로 변환된 텍스트는 내용을 직접 수정할 수 없습니다."))
            return

        self.inline_text_target = text_item
        text_item.setSelected(True)

        # 마지막 식자 단계의 직접 수정이므로, 기존 OCR 박스가 아니라 현재 실제 텍스트를 기준으로 편집을 시작한다.
        if hasattr(text_item, 'text_content_scene_rect'):
            scene_rect = text_item.text_content_scene_rect()
        else:
            local_rect = text_item.text_area_rect()
            scene_rect = text_item.mapToScene(local_rect).boundingRect()

        editor = InlineTextEditItem(self, text_item, scene_rect)
        self.inline_text_editor = editor

        text_item.setVisible(False)
        self.view.scene.addItem(editor)
        editor.setFocus(Qt.FocusReason.MouseFocusReason)

        cursor = editor.textCursor()
        cursor.clearSelection()
        if select_all:
            cursor.select(QTextCursor.SelectionType.Document)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)

        self.log(f"✏️ 텍스트 직접 편집 시작 (ID: {text_item.data.get('id')})")

    def finish_inline_text_edit(self, commit=True, refresh=True):
        editor = self.inline_text_editor
        target = self.inline_text_target
        if editor is None:
            return

        is_closing = bool(getattr(self, "_app_is_closing", False))
        try:
            editor._closing = True
        except Exception:
            pass

        # Qt 종료/탭 재구성 타이밍에 QGraphicsTextItem의 C++ 객체가 먼저 삭제될 수 있다.
        # 이 상태에서 toPlainText()/scene()/removeItem() 등을 호출하면
        # "wrapped C/C++ object ... has been deleted"가 나므로 조용히 포인터만 정리한다.
        try:
            _ = editor.toPlainText()
        except RuntimeError:
            self.inline_text_editor = None
            self.inline_text_target = None
            return
        except Exception:
            pass

        selected_id = target.data.get('id') if target is not None else None
        pending_new = bool(target is not None and target.data.get('pending_new_text'))

        changed = False
        added_new = False
        canceled_new = False

        if commit and target is not None:
            try:
                new_text = editor.toPlainText()
            except RuntimeError:
                self.inline_text_editor = None
                self.inline_text_target = None
                return
            changed = (new_text != getattr(editor, 'original_text', ''))

            if pending_new and not str(new_text or '').strip():
                canceled_new = True
                changed = False
                self.log(f"↩️ 새 텍스트 입력 취소 (ID: {target.data.get('id')})")
            elif changed or pending_new:
                command_fields = ['translated_text', 'rect', 'x_off', 'y_off', 'manual_text_rect', 'text_anchor_mode', 'force_show', 'pending_new_text']
                before_direct_values = None
                before_item_copy = None
                before_index = None
                try:
                    before_direct_values = self._snapshot_text_field_values(target.data, command_fields)
                except Exception:
                    before_direct_values = None
                try:
                    before_item_copy = copy.deepcopy(target.data)
                except Exception:
                    try:
                        before_item_copy = dict(target.data)
                    except Exception:
                        before_item_copy = None
                if not pending_new:
                    try:
                        curr_before = self.data.get(self.idx) or {}
                        for i, d in enumerate(curr_before.get('data', []) or []):
                            if isinstance(d, dict) and str(d.get('id')) == str(target.data.get('id')):
                                before_index = i
                                break
                    except Exception:
                        before_index = None
                # 2.4.1 안정 경로 복원:
                # 직접 텍스트 수정은 Command/Diff가 실패하거나 no-op 처리되면 Ctrl+Z 자체가
                # 사라지는 문제가 생겼다. 텍스트 내용/영역 직접 수정은 작은 필드 변경처럼
                # 보여도 편집기 focusOut/표 갱신/rect 재계산이 함께 얽히므로 2.4.1처럼
                # 수정 전 텍스트 라인 스냅샷을 먼저 남긴다.
                # 새 텍스트 추가만 lifecycle command를 유지한다.
                use_command_undo = False
                if pending_new:
                    use_command_undo = bool(hasattr(self, 'push_text_geometry_command') and hasattr(self, 'push_text_item_lifecycle_command'))
                if not use_command_undo:
                    try:
                        self.push_page_text_undo('텍스트 직접 수정' if not pending_new else '새 텍스트 추가')
                    except Exception:
                        try:
                            self.undo_text_checkpoint('텍스트 직접 수정' if not pending_new else '새 텍스트 추가')
                        except Exception:
                            pass

                target.data['translated_text'] = new_text
                target.data.pop('force_show', None)
                target.data.pop('pending_new_text', None)

                # 직접 수정한 경우에는 기존 OCR 박스가 아니라 현재 편집 텍스트 자체를 기준으로
                # 텍스트 영역을 다시 잡는다. 이 영역 변경도 같은 Command 안에 기록해야
                # Ctrl+Z 때 내용과 박스가 함께 원복된다.
                try:
                    edit_rect = editor.adjusted_scene_rect()
                    if edit_rect.width() > 1 and edit_rect.height() > 1:
                        target.data['rect'] = [
                            int(round(edit_rect.x())),
                            int(round(edit_rect.y())),
                            max(1, int(round(edit_rect.width()))),
                            max(1, int(round(edit_rect.height()))),
                        ]
                        target.data['x_off'] = 0
                        target.data['y_off'] = 0
                        target.data['manual_text_rect'] = True
                        target.data['text_anchor_mode'] = 'text'
                    else:
                        self.shrink_text_rect_to_content(target.data)
                except Exception:
                    try:
                        self.shrink_text_rect_to_content(target.data)
                    except Exception:
                        pass

                if pending_new:
                    curr = self.data.get(self.idx)
                    after_index = None
                    if curr is not None and target.data not in curr.setdefault('data', []):
                        after_index = len(curr.setdefault('data', []))
                        curr['data'].append(target.data)
                        added_new = True
                    changed = True
                    if use_command_undo:
                        try:
                            self.push_text_item_lifecycle_command(
                                target.data,
                                before_item=None,
                                after_item=target.data,
                                before_exists=False,
                                after_exists=True,
                                before_index=None,
                                after_index=after_index,
                                reason='새 텍스트 추가',
                                page_idx=self.idx,
                            )
                        except Exception:
                            pass
                        # 새 텍스트의 최초 위치/영역은 lifecycle command의 after_item에 이미 저장한다.
                        # 별도 text_position marker를 만들면 사용자가 실제로 이동하지 않았는데도
                        # Ctrl+Z 한 칸이 더 생겨 혼란스럽다. 위치 command는 실제 이동이
                        # 발생했을 때만 mousePress -> mouseRelease diff로 생성한다.
                    # 새 텍스트는 data 리스트 구조가 바뀌므로 텍스트 라인 표를 즉시 다시 만든다.
                    try:
                        self.ref_tab()
                        self.select_table_rows_by_ids([target.data.get('id')])
                    except Exception:
                        pass
                else:
                    if use_command_undo:
                        try:
                            after_direct_values = self._snapshot_text_field_values(target.data, command_fields)
                            self.push_text_geometry_command(
                                target.data,
                                before_values=before_direct_values,
                                after_values=after_direct_values,
                                reason='텍스트 직접 수정',
                                fields=command_fields,
                                page_idx=self.idx,
                                component_type='text_content',
                            )
                        except Exception:
                            pass
                    target_id = str(target.data.get('id'))
                    self.tab.blockSignals(True)
                    try:
                        trans_col = self._table_translation_column() if hasattr(self, '_table_translation_column') else 3
                        for row in range(1, self.tab.rowCount()):
                            id_item = self.tab.item(row, 0)
                            if id_item and id_item.text().strip() == target_id:
                                item = QTableWidgetItem(new_text)
                                item.setData(Qt.ItemDataRole.UserRole, new_text)
                                self.tab.setItem(row, trans_col, item)
                                break
                    finally:
                        self.tab.blockSignals(False)

            if changed:
                # E단계: 화면 반영 전에 작업 캐시 저장을 끼우면 직접 편집 확정 체감이 늦어진다.
                # 표/화면은 먼저 갱신하고, 저장 표시는 아래에서 지연 처리한다.
                try:
                    self.tab.resizeRowsToContents()
                except Exception:
                    pass
                if added_new:
                    self.log(f"✅ 새 텍스트 추가 완료 (ID: {target.data.get('id')})")
                else:
                    self.log(f"✅ 텍스트 직접 수정 완료 (ID: {target.data.get('id')})")
            elif not canceled_new:
                self.log(f"↩️ 텍스트 직접 수정 변화 없음 (ID: {target.data.get('id')})")
        elif target is not None:
            if pending_new:
                canceled_new = True
                self.log(f"↩️ 새 텍스트 입력 취소 (ID: {target.data.get('id')})")
            else:
                self.log(f"↩️ 텍스트 직접 수정 취소 (ID: {target.data.get('id')})")

        try:
            if editor.scene() is not None:
                editor.scene().removeItem(editor)
        except Exception:
            pass

        if target is not None:
            try:
                if canceled_new and target.scene() is not None:
                    target.scene().removeItem(target)
                else:
                    target.setVisible(True)
            except Exception:
                pass

        self.inline_text_editor = None
        self.inline_text_target = None

        # 인라인 텍스트 편집 확정은 2.4.1의 안정 경로처럼
        # 기존 TypesettingItem을 살려둔 채 해당 텍스트만 갱신한다.
        # 직접 수정 직후 QGraphicsScene의 텍스트 레이어를 제거/재생성하면
        # Qt/C++ access violation이 날 수 있으므로 force rebuild는 금지한다.
        if (not is_closing) and commit and (changed or added_new) and self.cb_mode.currentIndex() == 4:
            try:
                if selected_id is not None:
                    if not self.refresh_final_text_items_by_ids([selected_id]):
                        self.schedule_final_text_scene_refresh(80)
                elif refresh:
                    self.schedule_final_text_scene_refresh(80)
            except Exception:
                try:
                    self.schedule_final_text_scene_refresh(80)
                except Exception:
                    pass
            if selected_id is not None and not canceled_new:
                self.reselect_text_items([selected_id])
        elif (not is_closing) and selected_id is not None and not canceled_new:
            self.reselect_text_items([selected_id])

        if (not is_closing) and commit and (changed or added_new):
            try:
                self.finalize_text_change(ids=[selected_id] if selected_id is not None else [], fields=['translated_text'], reason='인라인 텍스트 직접 수정', delay_ms=1800)
            except Exception:
                try:
                    self.mark_active_page_dirty('text')
                    self.schedule_deferred_auto_save_project(1800)
                except Exception:
                    pass
    def on_scene_selection_changed(self):
        # 프로그램 종료/씬 재생성 중 selectionChanged가 뒤늦게 들어오면
        # 삭제된 QGraphicsScene에 접근하지 않고 조용히 무시한다.
        if getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
            return
        if self._safe_graphics_scene() is None:
            return
        try:
            # 쯔꾸르붕이의 좌측은 편집 가능한 텍스트 객체가 아니라 게임 프리뷰다.
            # 기존 식질툴의 scene -> table 선택 동기화가 살아 있으면,
            # 우측 표에서 셀을 드래그하는 순간 scene selectionChanged가 되돌아와
            # 표 선택을 행 선택/빈 선택으로 덮어써 버린다.
            # Maker 대사표에서는 표가 주 편집기이므로 scene selection은 표를 절대 건드리지 않는다.
            if self._is_current_maker_page():
                return
        except Exception:
            pass

        active_transform = self.current_transform_data_item()
        if active_transform is not None:
            active_id = active_transform.get('id')
            items = self.selected_text_items()
            if not any(item.data.get('id') == active_id for item in items):
                self.reselect_text_items([active_id])
                items = self.selected_text_items()
        else:
            items = self.selected_text_items()
        ids = [item.data.get('id') for item in items]
        self.select_table_rows_by_ids(ids)
        if hasattr(self, 'final_edit_bar'):
            self.final_edit_bar.hide()
        self.update_text_style_control_state(items)
        try:
            if hasattr(self, "refresh_shared_option_bar"):
                self.refresh_shared_option_bar()
        except Exception:
            pass

        if not items or self._style_signal_lock:
            return
        # 쯔꾸르붕이에서는 오른쪽 식질 스타일 UI를 생성하지 않는다.
        # 그래픽 텍스트 객체가 실수로 선택되어도 UI 동기화 경로로 들어가지 않는다.
        if not hasattr(self, 'cb_font'):
            return

        d = items[0].data
        self._style_signal_lock = True
        try:
            self.cb_font.setCurrentFont(QFont(d.get('font_family') or self.cb_font.currentFont().family()))
            self._set_widget_value_blocked(self.sb_font_size, int(d.get('font_size', self.sb_font_size.value()) or self.sb_font_size.value()))
            self._set_widget_value_blocked(self.sb_strk, int(d.get('stroke_width', self.sb_strk.value()) or 0))
            if hasattr(self, 'final_item_font'):
                self.final_item_font.setCurrentFont(QFont(d.get('font_family') or self.final_item_font.currentFont().family()))
            if hasattr(self, 'final_item_size'):
                self._set_widget_value_blocked(self.final_item_size, int(d.get('font_size', self.sb_font_size.value()) or self.sb_font_size.value()))
            if hasattr(self, 'final_item_stroke'):
                self._set_widget_value_blocked(self.final_item_stroke, int(d.get('stroke_width', self.sb_strk.value()) or 0))
            self.default_text_color = d.get('text_color') or self.default_text_color
            self.default_stroke_color = d.get('stroke_color') or self.default_stroke_color
            self.default_align = d.get('align') or self.default_align
            if hasattr(self, "sb_line_spacing"):
                self._set_widget_value_blocked(self.sb_line_spacing, int(d.get('line_spacing', self.default_line_spacing) or self.default_line_spacing))
            if hasattr(self, "sb_letter_spacing"):
                self._set_widget_value_blocked(self.sb_letter_spacing, int(d.get('letter_spacing', self.default_letter_spacing) or self.default_letter_spacing))
            if hasattr(self, "sb_char_width"):
                self._set_widget_value_blocked(self.sb_char_width, int(d.get('char_width', self.default_char_width) or self.default_char_width))
            if hasattr(self, "sb_char_height"):
                self._set_widget_value_blocked(self.sb_char_height, int(d.get('char_height', self.default_char_height) or self.default_char_height))
            if hasattr(self, "btn_bold"):
                self._set_widget_checked_blocked(self.btn_bold, bool(d.get('bold', False)))
            if hasattr(self, "btn_italic"):
                self._set_widget_checked_blocked(self.btn_italic, bool(d.get('italic', False)))
            if hasattr(self, "btn_strike"):
                self._set_widget_checked_blocked(self.btn_strike, bool(d.get('strike', False)))
            if hasattr(self, "sb_text_opacity"):
                self._set_widget_value_blocked(self.sb_text_opacity, int(d.get('opacity', 100) or 100))
            self.update_color_button_styles()
            self.update_item_preset_combo_for_selected_texts()
            self.update_text_style_control_state(items)
        finally:
            self._style_signal_lock = False

    def apply_text_style_button_styles(self):
        if self.is_light_theme():
            base = (
                "QPushButton { background:#ffffff; color:#111827; border:1px solid #D1C9CE; border-radius:0px; }"
                "QPushButton:hover { background:#FBF5F6; border-color:#9bbce8; }"
                "QPushButton:checked { background:#F5E8EA; color:#141416; border:1px solid #A85D66; font-weight:700; }"
                "QPushButton:disabled { background:#F2EDEF; color:#A39BA1; border:1px solid #d9dee8; }"
            )
        else:
            base = (
                "QPushButton { background:#2f3540; color:#F4EEF2; border:1px solid #625A61; border-radius:0px; }"
                "QPushButton:hover { background:#374151; }"
                "QPushButton:checked { background:#8A4A52; color:#ffffff; border:1px solid #C78A90; font-weight:700; }"
                "QPushButton:disabled { background:#211F23; color:#736A71; border:1px solid #373136; }"
            )
        for btn in (getattr(self, 'btn_align_left', None), getattr(self, 'btn_align_center', None), getattr(self, 'btn_align_right', None)):
            if btn is not None:
                btn.setStyleSheet(base)
        bold = base.replace("QPushButton {", "QPushButton { font-weight:bold;")
        italic = base.replace("QPushButton {", "QPushButton { font-style:italic;")
        strike = base.replace("QPushButton {", "QPushButton { text-decoration: line-through;")
        if hasattr(self, 'btn_bold'):
            self.btn_bold.setStyleSheet(bold)
        if hasattr(self, 'btn_italic'):
            self.btn_italic.setStyleSheet(italic)
        if hasattr(self, 'btn_strike'):
            self.btn_strike.setStyleSheet(strike)

    def set_widget_interlock_visual(self, widget, enabled, disabled_opacity=0.42):
        if widget is None:
            return
        try:
            widget.setEnabled(bool(enabled))
        except Exception:
            pass
        try:
            eff = widget.graphicsEffect()
            if not isinstance(eff, QGraphicsOpacityEffect):
                eff = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(eff)
            eff.setOpacity(1.0 if enabled else float(disabled_opacity))
        except Exception:
            pass

    def update_page_presence_interlocks(self):
        has_pages = bool(getattr(self, 'paths', []))
        for widget in getattr(self, 'page_required_widgets', []):
            self.set_widget_interlock_visual(widget, has_pages)
        for key in getattr(self, 'page_required_action_keys', []):
            action = self.actions.get(key) if hasattr(self, 'actions') else None
            if action is not None:
                try:
                    action.setEnabled(has_pages)
                except Exception:
                    pass
        # 로컬 라벨 변수까지 일일이 저장하지 않아도, 페이지 의존 문구는 같이 흐리게 만든다.
        label_texts = {
            "폰트", "크기", "획", "행간", "자간", "너비", "높이", "번역AI", "묶음",
            "Font", "Size", "Stroke", "Line", "Letter", "Width", "Height", "Translation AI", "Chunk",
        }
        try:
            for label in self.findChildren(QLabel):
                try:
                    if label.text().strip() in label_texts:
                        self.set_widget_interlock_visual(label, has_pages, disabled_opacity=0.35)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, 'page_tab_bar'):
                self.page_tab_bar.setEnabled(has_pages)
            if hasattr(self, 'btn_page_tab_menu'):
                self.set_widget_interlock_visual(self.btn_page_tab_menu, has_pages)
            for _btn in (getattr(self, 'btn_page_scroll_left', None), getattr(self, 'btn_page_scroll_right', None)):
                if _btn is not None:
                    self.set_widget_interlock_visual(_btn, has_pages)
            if hasattr(self, 'btn_page_add'):
                self.set_widget_interlock_visual(self.btn_page_add, bool(self.has_open_project()))
        except Exception:
            pass
        if not has_pages:
            self.update_text_style_control_state([])

    def update_text_style_control_state(self, selected_items=None):
        if getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
            return
        try:
            items = list(selected_items) if selected_items is not None else self.selected_text_items()
        except Exception:
            items = []
        enabled = bool(items) and hasattr(self, 'cb_mode') and self.cb_mode.currentIndex() == 4
        for widget in getattr(self, 'text_style_control_widgets', []):
            self.set_widget_interlock_visual(widget, enabled, disabled_opacity=0.35)
        self._style_signal_lock = True
        try:
            if not enabled:
                for btn in (getattr(self, 'btn_align_left', None), getattr(self, 'btn_align_center', None), getattr(self, 'btn_align_right', None), getattr(self, 'btn_bold', None), getattr(self, 'btn_italic', None), getattr(self, 'btn_strike', None)):
                    if btn is not None:
                        self._set_widget_checked_blocked(btn, False)
                if hasattr(self, 'sb_text_opacity'):
                    self._set_widget_value_blocked(self.sb_text_opacity, 100)
                return
            d = getattr(items[0], 'data', {}) or {}
            align = str(d.get('align') or getattr(self, 'default_align', 'center') or 'center').lower()
            if align not in ('left', 'center', 'right'):
                align = 'center'
            if hasattr(self, 'btn_align_left'):
                self._set_widget_checked_blocked(self.btn_align_left, align == 'left')
                self._set_widget_checked_blocked(self.btn_align_center, align == 'center')
                self._set_widget_checked_blocked(self.btn_align_right, align == 'right')
            if hasattr(self, 'btn_bold'):
                self._set_widget_checked_blocked(self.btn_bold, bool(d.get('bold', False)))
            if hasattr(self, 'btn_italic'):
                self._set_widget_checked_blocked(self.btn_italic, bool(d.get('italic', False)))
            if hasattr(self, 'btn_strike'):
                self._set_widget_checked_blocked(self.btn_strike, bool(d.get('strike', False)))
            if hasattr(self, 'sb_text_opacity'):
                self._set_widget_value_blocked(self.sb_text_opacity, int(d.get('opacity', 100) or 100))
        finally:
            self._style_signal_lock = False

    def _style_patch_from_sender(self, sender=None):
        """우측 텍스트 인터페이스의 사용자 조작을 field 단위 패치로 변환한다.

        AB단계: 여러 텍스트를 선택한 상태에서 한 컨트롤을 조작했을 때,
        대표 텍스트의 전체 스타일을 덮어쓰지 않고 사용자가 건드린 field만 전체 선택 항목에 적용한다.
        """
        try:
            sender = sender or self.sender()
        except Exception:
            sender = None
        try:
            if sender is getattr(self, 'cb_font', None):
                return {'font_family': self.cb_font.currentFont().family()}
            if sender is getattr(self, 'sb_font_size', None):
                return {'font_size': int(self.sb_font_size.value())}
            if sender is getattr(self, 'sb_strk', None):
                return {'stroke_width': int(self.sb_strk.value())}
            if sender is getattr(self, 'sb_line_spacing', None):
                return {'line_spacing': int(self.sb_line_spacing.value())}
            if sender is getattr(self, 'sb_letter_spacing', None):
                return {'letter_spacing': int(self.sb_letter_spacing.value())}
            if sender is getattr(self, 'sb_char_width', None):
                return {'char_width': int(self.sb_char_width.value())}
            if sender is getattr(self, 'sb_char_height', None):
                return {'char_height': int(self.sb_char_height.value())}
            if sender is getattr(self, 'btn_bold', None):
                return {'bold': bool(self.btn_bold.isChecked())}
            if sender is getattr(self, 'btn_italic', None):
                return {'italic': bool(self.btn_italic.isChecked())}
            if sender is getattr(self, 'btn_strike', None):
                return {'strike': bool(self.btn_strike.isChecked())}
        except Exception:
            pass
        return {}

    def _final_item_style_patch_from_sender(self, sender=None):
        try:
            sender = sender or self.sender()
        except Exception:
            sender = None
        try:
            if sender is getattr(self, 'final_item_font', None):
                return {'font_family': self.final_item_font.currentFont().family()}
            if sender is getattr(self, 'final_item_size', None):
                return {'font_size': int(self.final_item_size.value())}
            if sender is getattr(self, 'final_item_stroke', None):
                return {'stroke_width': int(self.final_item_stroke.value())}
        except Exception:
            pass
        return {}

    def on_final_item_style_changed(self, *args):
        if self._style_signal_lock:
            return
        if not self.selected_text_items():
            return
        patch = self._final_item_style_patch_from_sender()
        if not patch:
            return
        self.apply_style_to_selected(**patch)


    def on_text_opacity_changed(self, value):
        if getattr(self, '_style_signal_lock', False):
            return
        if not self.selected_text_items() or self.cb_mode.currentIndex() != 4:
            return
        self.apply_style_to_selected(opacity=max(0, min(100, int(value))))

    def selected_first_text_data_item(self):
        try:
            items = self.selected_text_items()
            if items:
                return items[0].data
        except Exception:
            pass
        try:
            rows = self.selected_text_data_items()
            if rows:
                return rows[0]
        except Exception:
            pass
        return None

    def open_selected_text_gradient_dialog(self):
        try:
            self.open_text_advanced_effect_dialog(self.selected_text_data_items())
        except Exception:
            pass

    def toggle_selected_text_transform_quick(self):
        d = self.selected_first_text_data_item()
        if d is not None:
            self.toggle_text_transform_mode(d)

    def toggle_selected_text_skew_quick(self):
        d = self.selected_first_text_data_item()
        if d is not None:
            self.toggle_text_skew_mode(d)

    def toggle_selected_text_trapezoid_quick(self):
        d = self.selected_first_text_data_item()
        if d is not None:
            self.toggle_text_trapezoid_mode(d)

    def toggle_selected_text_arc_quick(self):
        d = self.selected_first_text_data_item()
        if d is not None:
            self.toggle_text_arc_mode(d)

    def rasterize_selected_text_quick(self):
        try:
            self.convert_text_data_items_to_raster_objects(self.selected_text_data_items())
        except Exception:
            pass

    def rebuild_current_page_text_layer_from_data(self, selected_ids=None, clear_selection=False):
        """현재 최종결과 scene의 텍스트 아이템만 제자리에서 다시 그린다.

        예전 안정화 패치에서는 크래시 회피를 위해 mode_chg(4) 전체 재구성으로 우회했지만,
        텍스트 이동/수정/줌 때마다 배경과 텍스트 레이어 전체가 다시 만들어져 조작감이 크게 느려졌다.
        여기서는 기존 QGraphicsItem을 제거하지 않고 TypesettingItem 내부 path/style만 재계산한다.
        """
        if getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
            return False
        try:
            if self.cb_mode.currentIndex() != 4:
                return False
        except Exception:
            return False
        scene = self._safe_graphics_scene()
        if scene is None:
            return False

        ids = [x for x in (selected_ids or []) if x is not None]
        if not ids and not clear_selection:
            try:
                ids = [getattr(x, 'data', {}).get('id') for x in scene.selectedItems() if isinstance(x, TypesettingItem)]
                ids = [x for x in ids if x is not None]
            except Exception:
                ids = []
        idset = {str(x) for x in ids if x is not None}

        # Undo/Redo에서 curr["data"] 리스트를 통째로 교체하면 scene 위 TypesettingItem.data는
        # 이전 dict 객체를 계속 바라볼 수 있다. 이 상태로 path만 다시 그리면 화면은 그대로라
        # "텍스트 Undo가 안 먹는" 것처럼 보인다. 현재 page data의 dict로 반드시 재결합한다.
        curr = self.data.get(self.idx)
        data_list = curr.get("data", []) if isinstance(curr, dict) else []
        data_by_id = {}
        try:
            for d in data_list:
                if isinstance(d, dict) and d.get("id") is not None:
                    data_by_id[str(d.get("id"))] = d
        except Exception:
            data_by_id = {}

        # scene/data의 ID 구성이 달라진 경우(붙여넣기 Undo, 삭제 Undo 등)는 in-place 갱신만으로는
        # 아이템 추가/삭제가 맞지 않는다. 단, 비교 대상은 전체 curr['data']가 아니라
        # 실제 최종화면에 그려질 renderable text id여야 한다.
        try:
            scene_ids = {
                str(getattr(obj, 'data', {}).get('id'))
                for obj in list(scene.items())
                if isinstance(obj, TypesettingItem)
                and getattr(obj, 'data', {}).get('id') is not None
                and (not hasattr(obj, 'isVisible') or obj.isVisible())
            }
            renderable_ids = {
                str(d.get('id'))
                for d in data_list
                if isinstance(d, dict) and self._is_renderable_text_data_item(d)
            }
            if scene_ids != renderable_ids:
                missing_ids = sorted(list(renderable_ids - scene_ids), key=lambda x: str(x))
                extra_ids = sorted(list(scene_ids - renderable_ids), key=lambda x: str(x))
                # 붙여넣기처럼 data 쪽에만 새 텍스트가 추가된 경우는 전체 mode_chg(4)를 태우지 말고
                # 누락된 live TypesettingItem만 추가한다. 전체 scene 재구성은 Qt crash 위험이 크다.
                if missing_ids and not extra_ids and hasattr(self, '_add_live_text_items_for_ids'):
                    try:
                        if self._add_live_text_items_for_ids(missing_ids, selected=bool(idset), reason='scene_data_mismatch_add_only'):
                            return True
                    except Exception:
                        pass
                try:
                    self.audit_boundary_event(
                        "TEXT_LAYER_REBUILD_NEEDS_FULL_REFRESH",
                        scene_count=len(scene_ids),
                        data_count=len(renderable_ids),
                        raw_data_count=len(data_by_id),
                        selected_count=len(idset),
                        missing_count=len(missing_ids),
                        extra_count=len(extra_ids),
                        throttle_ms=200,
                    )
                except Exception:
                    pass
                try:
                    self.schedule_safe_text_scene_resync(
                        reason="scene_data_mismatch",
                        selected_ids=ids,
                        delay_ms=80,
                    )
                    return True
                except Exception:
                    return False
        except Exception:
            pass

        old_rebuild = getattr(self, "_is_rebuilding_text_layer", False)
        self._is_rebuilding_text_layer = True
        changed = False
        rebound = 0
        raster_mode_mismatch = False
        try:
            for obj in list(scene.items()):
                if not isinstance(obj, TypesettingItem):
                    continue
                sid = str(getattr(obj, 'data', {}).get('id'))
                if idset and sid not in idset:
                    continue
                try:
                    bound_data = data_by_id.get(sid)
                    if isinstance(bound_data, dict) and getattr(obj, "data", None) is not bound_data:
                        obj.data = bound_data
                        rebound += 1
                        try:
                            obj.main_window = self
                        except Exception:
                            pass
                    item_raster = bool(getattr(obj, "_is_rasterized_text", False))
                    data_raster = bool((getattr(obj, "data", {}) or {}).get("rasterized_text"))
                    if item_raster != data_raster:
                        # Text-object conversion changes the runtime item class behavior.
                        # In-place refresh cannot safely turn a rasterized item back into editable text,
                        # so queue a full text-layer rebuild after the current event unwinds.
                        raster_mode_mismatch = True
                        continue
                    if data_raster:
                        if hasattr(obj, "_init_rasterized_text_item"):
                            obj.prepareGeometryChange()
                            obj._init_rasterized_text_item()
                        else:
                            obj.update()
                    elif hasattr(obj, 'rebuild_text_render_for_live_preview'):
                        obj.rebuild_text_render_for_live_preview(force=True)
                    obj.update()
                    changed = True
                except RuntimeError:
                    return False
                except Exception:
                    pass
            if raster_mode_mismatch:
                try:
                    self.audit_boundary_event("TEXT_LAYER_REBUILD_RASTER_MODE_MISMATCH", selected_count=len(idset), throttle_ms=120)
                except Exception:
                    pass
                try:
                    self.schedule_safe_text_scene_resync(
                        reason="raster_mode_mismatch",
                        selected_ids=ids,
                        delay_ms=30,
                        table_refresh=True,
                    )
                    return True
                except Exception:
                    return False
            try:
                if rebound:
                    self.audit_boundary_event("TEXT_LAYER_REBOUND_DATA", rebound=rebound, changed=changed, throttle_ms=200)
            except Exception:
                pass
            if clear_selection:
                try:
                    scene.clearSelection()
                except Exception:
                    pass
            elif idset:
                try:
                    for obj in list(scene.items()):
                        if isinstance(obj, TypesettingItem) and str(getattr(obj, 'data', {}).get('id')) in idset:
                            obj.setSelected(True)
                except Exception:
                    pass
            try:
                self.force_update_final_scene_region()
            except Exception:
                try:
                    scene.update()
                except Exception:
                    pass
            return bool(changed)
        finally:
            self._is_rebuilding_text_layer = old_rebuild

    def refresh_selected_text_items_in_place(self, selected_items=None):
        ids = []
        for item in list(selected_items or self.selected_text_items() or []):
            try:
                sid = item.data.get('id')
                if sid is not None:
                    ids.append(sid)
            except Exception:
                pass
        return self.rebuild_current_page_text_layer_from_data(ids)

    def refresh_final_text_items_by_ids(self, text_ids):
        return self.rebuild_current_page_text_layer_from_data(text_ids)

    def force_rebuild_final_text_layer_from_data(self, selected_ids=None):
        """Queue a safe full text-scene resync from page data.

        This used to purge live TypesettingItems and call mode_chg(4) immediately.
        After the undo refactor that became unsafe because delete/paste/undo can call
        this while Qt still holds stale selected item references.  Route all full
        text-layer rebuild requests through the safe resync barrier instead.
        """
        try:
            if self.cb_mode.currentIndex() != 4:
                return False
        except Exception:
            return False
        try:
            ids = [x for x in (selected_ids or []) if x is not None]
        except Exception:
            ids = []
        try:
            return bool(self.schedule_safe_text_scene_resync(
                reason="force_rebuild_final_text_layer_from_data",
                selected_ids=ids,
                delay_ms=40,
            ))
        except Exception:
            return False

    def apply_style_to_selected(self, keep_selection=True, preset_name=None, record_undo=True, **style):
        if getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
            return
        items = self.selected_text_items()
        if not items:
            return
        try:
            self.flush_text_scene_geometry_to_data([getattr(item, 'data', {}) for item in items], mark_dirty=False, reason="before style apply")
        except Exception:
            pass
        selected_ids = [item.data.get('id') for item in items]
        page_idx = int(getattr(self, "idx", 0) or 0)
        mode_idx = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 4

        if record_undo:
            try:
                self._ensure_live_text_style_undo(
                    items,
                    fields=list(dict.fromkeys(list(style.keys()) + ["item_text_preset_name"])),
                    reason='텍스트 스타일 변경',
                )
            except Exception:
                try:
                    before = self.text_engine.snapshot_from_scene_items(items)
                    rec = self.text_engine.make_diff_record(
                        page_idx=page_idx,
                        mode=mode_idx,
                        reason='텍스트 스타일 변경',
                        before_items=before,
                        selected_ids=selected_ids,
                        fields=list(dict.fromkeys(list(style.keys()) + ["item_text_preset_name"])),
                    )
                    self.undo_push_page(rec, page_idx=page_idx)
                except Exception:
                    self.undo_text_checkpoint('텍스트 스타일 변경')

        for item in items:
            for key, value in style.items():
                item.data[key] = value
            if preset_name:
                item.data['item_text_preset_name'] = str(preset_name)
            else:
                item.data.pop('item_text_preset_name', None)
            # 이미 직접 수정된 텍스트는 OCR 박스를 버린 상태이므로,
            # 스타일 변경 후에도 실제 글자 bounds를 기준으로 텍스트 영역을 다시 만든다.
            try:
                if bool(item.data.get('manual_text_rect')) or str(item.data.get('text_anchor_mode') or '').lower() == 'text':
                    self.shrink_text_rect_to_content(item.data)
            except Exception:
                pass

        # 스타일/수치 변경은 즉시 화면에 보여야 한다.
        # 살아 있는 선택 item은 직접 path/style만 재계산해 렉을 줄이고,
        # 실패할 때만 전체 텍스트 레이어 재구성으로 폴백한다.
        if self.cb_mode.currentIndex() == 4:
            refreshed = False
            try:
                refreshed = bool(self.refresh_text_items_live_in_place(items, keep_selection=keep_selection))
            except Exception:
                refreshed = False
            if not refreshed:
                try:
                    refreshed = bool(self.rebuild_current_page_text_layer_from_data(selected_ids if keep_selection else None, clear_selection=not keep_selection))
                except Exception:
                    refreshed = False
            if not refreshed:
                try:
                    refreshed = bool(self.force_rebuild_final_text_layer_from_data(selected_ids if keep_selection else None))
                    try:
                        self.audit_boundary_event("TEXT_STYLE_REFRESH_FORCE_REBUILD", selected_count=len(selected_ids), fields=",".join([str(k) for k in style.keys()]), ok=bool(refreshed), throttle_ms=120)
                    except Exception:
                        pass
                except Exception:
                    refreshed = False
            if not refreshed:
                try:
                    self.schedule_final_text_scene_refresh(40)
                except Exception:
                    pass
            try:
                if keep_selection and selected_ids:
                    self.reselect_text_items(selected_ids)
            except Exception:
                pass
            try:
                self.update_item_preset_combo_for_selected_texts()
            except Exception:
                pass
        try:
            if hasattr(self, "text_engine") and self.text_engine is not None:
                self.text_engine.mark_dirty(page_idx, selected_ids, list(style.keys()))
            self.mark_active_page_dirty("text")
        except Exception:
            pass
        try:
            self.schedule_deferred_auto_save_project(900)
        except Exception:
            self.auto_save_project()

    def reselect_text_items(self, selected_ids):
        ids = set(selected_ids or [])
        if not ids or getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
            return
        scene = self._safe_graphics_scene()
        if scene is None:
            return
        try:
            for item in scene.items():
                if isinstance(item, TypesettingItem) and item.data.get('id') in ids:
                    item.setSelected(True)
        except RuntimeError:
            return
        except Exception:
            return

    def select_table_rows_by_ids(self, selected_ids):
        if not hasattr(self, 'tab') or self._syncing_selection:
            return
        ids = {str(x) for x in (selected_ids or []) if x is not None}
        self._syncing_selection = True
        try:
            model = self.tab.model()
            sm = self.tab.selectionModel()
            if not sm:
                return
            sm.clearSelection()
            first_row = None
            for row in range(1, self.tab.rowCount()):
                id_item = self.tab.item(row, 0)
                if id_item and id_item.text().strip() in ids:
                    top = model.index(row, 0)
                    bottom = model.index(row, self.tab.columnCount() - 1)
                    sel = QItemSelection(top, bottom)
                    sm.select(sel, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
                    if first_row is None:
                        first_row = row
            if first_row is not None:
                # setCurrentCell()은 환경에 따라 선택을 마지막 한 줄로 줄일 수 있어서 사용하지 않는다.
                # 현재 인덱스만 조용히 옮기고 다중 선택 상태는 유지한다.
                sm.setCurrentIndex(model.index(first_row, 0), QItemSelectionModel.SelectionFlag.NoUpdate)
        finally:
            self._syncing_selection = False


    def _is_current_maker_page(self):
        try:
            curr = self.data.get(self.idx) if isinstance(getattr(self, "data", None), dict) else None
            return bool(isinstance(curr, dict) and isinstance(curr.get("maker_page"), dict) and curr.get("maker_page"))
        except Exception:
            return False

    def _maker_current_selected_row_item(self):
        """Return the first selected Maker text row data dict on the current page."""
        try:
            if not self._is_current_maker_page():
                return None
            curr = self.data.get(self.idx) if isinstance(getattr(self, "data", None), dict) else None
            if not isinstance(curr, dict):
                return None
            ids = self.selected_table_text_ids()
            if not ids:
                return None
            first_id = str(ids[0])
            for row in curr.get("data") or []:
                if isinstance(row, dict) and str(row.get("id")) == first_id and isinstance(row.get("maker_text_unit"), dict):
                    return row
        except Exception:
            return None
        return None

    def _append_maker_preview_diagnostic(self, event, payload=None):
        try:
            project_dir = str(getattr(self, "project_dir", "") or "").strip()
            if not project_dir:
                return
            from ysb.tools.maker_project import append_maker_preview_diagnostic
            append_maker_preview_diagnostic(project_dir, str(event or "ui_event"), payload or {})
        except Exception:
            return

    def _maker_preview_new_lifecycle_token(self, reason=""):
        """Advance the Maker preview lifecycle generation.

        Project close/open paths can leave delayed QTimer refresh callbacks alive.
        Every close/open boundary gets a new token so stale callbacks cannot redraw
        an old project's preview after the view has been cleared.
        """
        try:
            token = int(getattr(self, "_maker_preview_lifecycle_token", 0) or 0) + 1
        except Exception:
            token = 1
        self._maker_preview_lifecycle_token = token
        try:
            self.audit_boundary_event("MAKER_PREVIEW_LIFECYCLE_TOKEN", token=token, reason=str(reason or ""))
        except Exception:
            pass
        return token

    def _clear_maker_preview_display_state(self, *, reason="project_close"):
        """Clear every visual/cache bit owned by the Maker preview area.

        This is intentionally stronger than clearing selection overlays.  The
        project lifecycle rule is simple: leaving/closing a project must leave an
        empty preview; opening/creating a project must build a fresh preview from
        that project's current page.
        """
        try:
            self._maker_preview_overlay_items = []
            self._maker_scene_preview_items = []
            self._maker_scene_preview_picture_items = []
            self._maker_scene_preview_text_items = []
            self._maker_scene_preview_message_items = []
            self._maker_scene_preview_event_items = []
            self._maker_scene_preview_current_row_id = None
            self._maker_scene_preview_current_payload = None
            self._maker_scene_preview_rebuild_key = None
            self._maker_local_map_preview_last_key = None
            self._maker_last_selected_text_id = None
            self._maker_table_current_marker_row = -1
        except Exception:
            pass
        try:
            self._project_runtime_cache_scope = ""
            self._maker_active_preview_project_scope = ""
            self._maker_current_preview_cache_key = None
            self._maker_current_preview_project_scope = None
        except Exception:
            pass
        # 프로젝트 생명주기 경계에서는 메모리 캐시를 전부 버린다.
        # 폰트/Window/DB JSON/뷰어 base pixmap 캐시가 프로젝트를 넘나들면
        # 같은 page:0/final 키로 이전 프로젝트 프리뷰가 새 프로젝트에 붙을 수 있다.
        for attr in (
            "_maker_preview_window_pixmap_cache",
            "_maker_preview_window_text_color_cache",
            "_maker_db_window_text_color_cache",
            "_maker_database_json_cache",
            "_maker_database_preview_raw_pixmap",
            "_last_maker_preview_font_deps_diag",
            "_last_maker_preview_font_conversion_diag",
            "_last_maker_preview_font_load_diag",
            "_last_maker_preview_font_diag",
        ):
            try:
                if attr.endswith("_cache"):
                    setattr(self, attr, {})
                else:
                    setattr(self, attr, None)
            except Exception:
                pass
        try:
            from PyQt6.QtGui import QPixmapCache
            QPixmapCache.clear()
        except Exception:
            pass
        try:
            self.maker_database_mode_enabled = False
            self.maker_database_idx = 0
            self.maker_database_tabs = []
            self._maker_database_preview_raw_pixmap = None
            self._maker_database_preview_fit_mode = True
            self._maker_database_preview_zoom = 1.0
        except Exception:
            pass
        # DB 프리뷰 패널은 일반 맵 프리뷰와 같은 자리를 차지한다.
        # 프로젝트를 닫거나 전환할 때 이 패널을 숨기지 않으면, 새 프로젝트가
        # 정상 로드되어도 왼쪽에 이전 DB 프리뷰 캔버스만 남는다.
        # 따라서 프로젝트 생명주기 경계에서는 표시 위젯 자체를 일반 맵 프리뷰로
        # 강제 복귀시킨다.
        try:
            panel = getattr(self, "maker_database_preview_panel", None)
            if panel is not None:
                panel.hide()
        except Exception:
            pass
        try:
            split = getattr(self, "source_compare_splitter", None)
            if split is not None:
                split.show()
                split.setVisible(True)
        except Exception:
            pass
        try:
            canvas = getattr(self, "lbl_maker_database_preview_canvas", None)
            if canvas is not None:
                canvas.clear()
                try:
                    canvas.setText(self.tr_ui("데이터베이스 프리뷰"))
                except Exception:
                    canvas.setText("데이터베이스 프리뷰")
                try:
                    canvas.setFixedSize(max(320, canvas.minimumWidth()), max(240, canvas.minimumHeight()))
                except Exception:
                    pass
        except Exception:
            pass
        try:
            label = getattr(self, "maker_database_preview_label", None)
            if label is not None:
                label.clear()
                try:
                    label.setText(self.tr_ui("데이터베이스 프리뷰"))
                except Exception:
                    label.setText("데이터베이스 프리뷰")
        except Exception:
            pass
        try:
            view = getattr(self, "view", None)
            if view is not None:
                try:
                    if hasattr(view, "hard_clear_runtime_cache"):
                        view.hard_clear_runtime_cache(reason=reason)
                    else:
                        view.set_image(None)
                except Exception:
                    try:
                        if getattr(view, "scene", None) is not None:
                            view.scene.clear()
                    except Exception:
                        pass
                try:
                    view.resetTransform()
                except Exception:
                    pass
                try:
                    if getattr(view, "scene", None) is not None:
                        view.scene.setSceneRect(0, 0, 1, 1)
                except Exception:
                    pass
                try:
                    view.resetCachedContent()
                except Exception:
                    pass
                try:
                    view.viewport().update()
                    view.viewport().repaint()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            sc = getattr(self, "source_compare_scene", None)
            if sc is not None:
                sc.clear()
                sc.setSceneRect(0, 0, 1, 1)
            scv = getattr(self, "source_compare_view", None)
            if scv is not None:
                try:
                    scv.resetTransform()
                    scv.resetCachedContent()
                    scv.viewport().update()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.audit_boundary_event("MAKER_PREVIEW_CLEARED", reason=str(reason or "project_close"))
        except Exception:
            pass

    def _force_maker_preview_rebuild_for_current_project(self, *, reason="project_open", token=None):
        """Build the current page preview from the currently loaded project only.

        This is the lifecycle counterpart to _clear_maker_preview_display_state().
        It does not depend on entering/leaving DB mode.  If a delayed refresh from
        an old project fires after a new project was opened, the lifecycle token
        check drops it.
        """
        try:
            current_token = int(getattr(self, "_maker_preview_lifecycle_token", 0) or 0)
            if token is not None and int(token) != current_token:
                return False
        except Exception:
            pass
        try:
            if getattr(self, "is_loading_project", False):
                return False
            if not getattr(self, "paths", None):
                return False
            self.maker_database_mode_enabled = False
            # 새 프로젝트의 일반 맵 프리뷰를 세울 때는 DB 프리뷰 패널을 반드시 닫는다.
            # saved ui_state/current_mode가 4여도 이것은 최종결과 탭이지 DB 모드가 아니다.
            try:
                self.set_maker_database_preview_visible(False)
            except Exception:
                try:
                    panel = getattr(self, "maker_database_preview_panel", None)
                    if panel is not None:
                        panel.hide()
                    split = getattr(self, "source_compare_splitter", None)
                    if split is not None:
                        split.show()
                        split.setVisible(True)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            import time
            paths = list(getattr(self, "paths", []) or [])
            if not paths:
                return False
            idx = int(getattr(self, "idx", 0) or 0)
            if idx < 0 or idx >= len(paths):
                idx = 0
            # In normal mode, never let a saved DB virtual-page index drive the
            # first preview.  Find the first real map/common page instead.
            try:
                pg = self._page_data_for_index_safe(idx) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(idx, {})
                if self._maker_page_is_database_page(pg):
                    for pi in range(len(paths)):
                        cand = self._page_data_for_index_safe(pi) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(pi, {})
                        if not self._maker_page_is_database_page(cand):
                            idx = pi
                            break
            except Exception:
                pass
            self.idx = idx
            page = (getattr(self, "data", {}) or {}).get(idx, {})
            try:
                self.ensure_page_runtime_loaded(idx, include_ori=True, include_heavy=True, include_masks=False)
            except Exception:
                pass
            # Directly seed the graphics view once.  mode_chg/ref_tab can then
            # add normal overlays, but the preview is no longer blank while
            # waiting for a DB-mode rebuild or a later user click.
            img = None
            try:
                img = self.final_base_image_for_page(idx)
            except Exception:
                img = None
            if img is None:
                try:
                    img = self.get_source_display_image(idx)
                except Exception:
                    img = None
            if img is not None and hasattr(self, "view") and self.view is not None:
                try:
                    self.view.set_image(img, fit=True)
                except Exception:
                    try:
                        key = self._work_mode_base_key(idx, "project_open_preview", page) if hasattr(self, "_work_mode_base_key") else f"project_open_preview:{idx}"
                        self.view.set_layer_base_image(img, key=key, fit=True, clear_paint_history=False)
                        self.view.clear_mode_layers(clear_boxes=True, clear_text=True, clear_mask=True, clear_final_paint=True)
                    except Exception:
                        pass
            try:
                self.ref_tab()
            except Exception:
                pass
            try:
                mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 4
            except Exception:
                mode = 4
            try:
                self.mode_chg(mode)
            except Exception:
                pass
            try:
                if hasattr(self, "update_maker_preview_selection_from_table"):
                    self.update_maker_preview_selection_from_table()
            except Exception:
                pass
            try:
                if hasattr(self, "view") and self.view is not None and self.view.viewport() is not None:
                    self.view.viewport().update()
            except Exception:
                pass
            try:
                self.audit_boundary_event("MAKER_PREVIEW_REBUILT", reason=str(reason or "project_open"), page_idx=idx, token=getattr(self, "_maker_preview_lifecycle_token", None), has_image=bool(img is not None))
            except Exception:
                pass
            return bool(img is not None)
        except Exception as e:
            try:
                self.audit_boundary_event("MAKER_PREVIEW_REBUILD_FAILED", reason=str(reason or "project_open"), error=f"{type(e).__name__}: {e}")
            except Exception:
                pass
            return False

    def force_refresh_maker_preview_action(self):
        """User-facing hard refresh for the current Maker map preview.

        This is intentionally manual and cache-hostile.  Automatic preview rebuilds
        may be skipped by lifecycle guards, lazy render flags, or viewer fast-path
        keys.  When the user presses [프리뷰 갱신], the current page preview PNG is
        regenerated from the current project/game clone and the left viewer is
        rebuilt immediately.
        """
        return self.force_refresh_maker_preview_current_page(reason="manual_preview_refresh", show_message=True)

    def force_refresh_maker_preview_current_page(self, *, reason="manual_preview_refresh", show_message=False):
        progress = None

        def _progress(step, total, label):
            nonlocal progress
            try:
                if not show_message:
                    return
                if progress is None:
                    progress = QProgressDialog(self)
                    progress.setWindowTitle(self.tr_ui("프리뷰 갱신"))
                    progress.setMinimumDuration(0)
                    progress.setAutoClose(False)
                    progress.setAutoReset(False)
                    progress.setCancelButton(None)
                    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
                    try:
                        apply_progress_dialog_theme(progress, bool(self.is_light_theme()))
                    except Exception:
                        pass
                total_i = max(1, int(total or 1))
                step_i = max(0, min(int(step or 0), total_i))
                progress.setRange(0, total_i)
                progress.setValue(step_i)
                progress.setLabelText(self.tr_ui(str(label or "프리뷰 이미지를 다시 만드는 중입니다...")))
                progress.show()
                QApplication.processEvents()
            except Exception:
                pass

        def _close_progress():
            nonlocal progress
            try:
                if progress is not None:
                    progress.setValue(progress.maximum())
                    QApplication.processEvents()
                    progress.close()
            except Exception:
                pass
            progress = None

        try:
            import os
            import time
            from pathlib import Path

            paths = list(getattr(self, "paths", []) or [])
            data = getattr(self, "data", {}) or {}
            if not paths or not isinstance(data, dict):
                if show_message:
                    QMessageBox.information(self, self.tr_ui("프리뷰 갱신"), self.tr_ui("열린 프로젝트가 없습니다."))
                return False
            idx = int(getattr(self, "idx", 0) or 0)
            if idx < 0 or idx >= len(paths):
                idx = 0
            curr = data.get(idx)
            if not isinstance(curr, dict):
                if show_message:
                    QMessageBox.warning(self, self.tr_ui("프리뷰 갱신 실패"), self.tr_ui("현재 맵 데이터를 찾을 수 없습니다."))
                return False
            meta = curr.get("maker_page") if isinstance(curr.get("maker_page"), dict) else {}
            if not isinstance(meta, dict) or not meta:
                if show_message:
                    QMessageBox.information(self, self.tr_ui("프리뷰 갱신"), self.tr_ui("쯔꾸르 맵 페이지에서만 사용할 수 있습니다."))
                return False
            page_type = str(meta.get("page_type") or "map")
            image_path = str(paths[idx] or "")
            if not image_path:
                if show_message:
                    QMessageBox.warning(self, self.tr_ui("프리뷰 갱신 실패"), self.tr_ui("현재 맵 이미지 경로를 찾을 수 없습니다."))
                return False

            try:
                self.audit_boundary_event("MAKER_PREVIEW_MANUAL_REFRESH_ENTER", reason=str(reason or "manual_preview_refresh"), page_idx=idx, page_type=page_type)
            except Exception:
                pass

            _progress(0, 5, "프리뷰 갱신 준비 중...")

            settings = dict(curr.get("maker_preview_settings") or {})
            try:
                settings["project_root"] = str(getattr(self, "project_dir", "") or "")
                settings["maker_project_root"] = str(getattr(self, "project_dir", "") or "")
            except Exception:
                pass
            # Manual refresh means: ignore lazy/deferred state, ignore disk cache,
            # and rebuild the tile-backed preview PNG even if the image path already exists.
            settings["defer_tile_render"] = False
            settings["force_maker_preview_rebuild"] = True
            settings["force_preview_rebuild"] = True
            settings["manual_preview_refresh_nonce"] = int(time.time_ns())
            if page_type in {"", "map"}:
                settings["show_tile_map_preview"] = True

            try:
                meta["preview_render_deferred"] = False
                meta["preview_rendered_on_demand"] = False
                meta["preview_manual_refresh_running"] = True
                meta["preview_cache_hit"] = False
                meta.pop("preview_cache_path", None)
            except Exception:
                pass

            # Clear in-memory image state before rendering so the following load cannot
            # reuse the previous placeholder/tile PNG just because curr['ori'] exists.
            try:
                curr["ori"] = None
            except Exception:
                pass
            try:
                self.touch_page_image_cache(idx)
                self.trim_page_image_cache(keep_indices=[idx])
            except Exception:
                pass
            try:
                self._clear_maker_preview_selection_overlay()
            except Exception:
                pass
            try:
                view = getattr(self, "view", None)
                if view is not None and hasattr(view, "hard_clear_runtime_cache"):
                    view.hard_clear_runtime_cache(str(reason or "manual_preview_refresh"))
            except Exception:
                pass

            _progress(1, 5, "기존 프리뷰 캐시를 무시하고 타일 프리뷰를 다시 만드는 중...")

            ok = False
            before_stat = None
            try:
                try:
                    before_stat = Path(image_path).stat()
                except Exception:
                    before_stat = None
                from ysb.tools.maker_project import regenerate_maker_placeholder_for_page
                ok = bool(regenerate_maker_placeholder_for_page(image_path, curr, settings=settings))
            except Exception as e:
                ok = False
                try:
                    self.log(self.tr_ui("⚠️ 프리뷰 갱신 실패: {error}", error=f"{type(e).__name__}: {e}"))
                except Exception:
                    pass
            if not ok:
                try:
                    meta["preview_manual_refresh_running"] = False
                except Exception:
                    pass
                _close_progress()
                if show_message:
                    QMessageBox.warning(self, self.tr_ui("프리뷰 갱신 실패"), self.tr_ui("현재 맵 프리뷰를 다시 만들지 못했습니다."))
                return False

            try:
                after_stat = Path(image_path).stat()
                self.audit_boundary_event(
                    "MAKER_PREVIEW_MANUAL_REFRESH_RENDERED",
                    reason=str(reason or "manual_preview_refresh"),
                    page_idx=idx,
                    page_type=page_type,
                    image_path=str(image_path),
                    before_mtime=getattr(before_stat, "st_mtime_ns", None) if before_stat is not None else None,
                    after_mtime=getattr(after_stat, "st_mtime_ns", None),
                    after_size=getattr(after_stat, "st_size", None),
                    force_rebuild=True,
                )
            except Exception:
                pass

            try:
                meta["preview_render_deferred"] = False
                meta["preview_rendered_on_demand"] = True
                meta["preview_manual_refreshed"] = True
                meta["preview_manual_refresh_running"] = False
                meta["preview_cache_hit"] = False
            except Exception:
                pass
            try:
                curr["maker_preview_settings"] = dict(curr.get("maker_preview_settings") or {})
            except Exception:
                pass
            try:
                curr["ori"] = None
            except Exception:
                pass
            try:
                self.touch_page_image_cache(idx)
                self.trim_page_image_cache(keep_indices=[idx])
            except Exception:
                pass

            _progress(3, 5, "새 프리뷰 이미지를 화면에 다시 불러오는 중...")

            try:
                self.ensure_page_runtime_loaded(idx, include_ori=True, include_heavy=True, include_masks=False)
            except Exception:
                pass

            img = None
            try:
                img = self.final_base_image_for_page(idx)
            except Exception:
                img = None
            if img is None:
                try:
                    img = self.get_source_display_image(idx)
                except Exception:
                    img = None

            if img is not None:
                try:
                    self.idx = idx
                    if hasattr(self, "view") and self.view is not None:
                        unique_key = f"manual_preview_refresh:{idx}:{time.time_ns()}:{os.path.getmtime(image_path) if os.path.exists(image_path) else 0}"
                        if hasattr(self.view, "set_layer_base_image"):
                            self.view.set_layer_base_image(img, key=unique_key, fit=True, clear_paint_history=False)
                            self.view.clear_mode_layers(clear_boxes=True, clear_text=True, clear_mask=True, clear_final_paint=True)
                        else:
                            self.view.set_image(img, fit=True)
                except Exception:
                    pass

            _progress(4, 5, "대사 선택 프리뷰를 다시 그리는 중...")

            try:
                self.ref_tab()
            except Exception:
                pass
            try:
                mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 4
            except Exception:
                mode = 4
            try:
                self.mode_chg(mode)
            except Exception:
                pass
            try:
                if hasattr(self, "update_maker_preview_selection_from_table"):
                    self.update_maker_preview_selection_from_table()
            except Exception:
                pass
            try:
                if getattr(self, "view", None) is not None:
                    self.view.resetCachedContent()
                    self.view.viewport().update()
                    self.view.viewport().repaint()
            except Exception:
                pass
            try:
                self.mark_project_structure_dirty("maker_preview_manual_refresh")
            except Exception:
                pass
            try:
                self.schedule_workspace_checkpoint(delay_ms=900, reason="maker_preview_manual_refresh")
            except Exception:
                pass
            try:
                self.audit_boundary_event("MAKER_PREVIEW_MANUAL_REFRESH_DONE", reason=str(reason or "manual_preview_refresh"), page_idx=idx, page_type=page_type, has_image=bool(img is not None))
            except Exception:
                pass
            try:
                self.log(self.tr_ui("🔄 프리뷰 갱신 완료: 현재 맵 이미지를 다시 만들었습니다."))
            except Exception:
                pass
            _progress(5, 5, "프리뷰 갱신 완료")
            _close_progress()
            return True
        except Exception as e:
            _close_progress()
            try:
                self.audit_boundary_event("MAKER_PREVIEW_MANUAL_REFRESH_FAILED", reason=str(reason or "manual_preview_refresh"), error=f"{type(e).__name__}: {e}")
            except Exception:
                pass
            try:
                self.log(self.tr_ui("⚠️ 프리뷰 갱신 실패: {error}", error=f"{type(e).__name__}: {e}"))
            except Exception:
                pass
            if show_message:
                try:
                    QMessageBox.warning(self, self.tr_ui("프리뷰 갱신 실패"), str(e))
                except Exception:
                    pass
            return False

    def _clear_maker_preview_selection_overlay(self):
        scene = self._safe_graphics_scene() if hasattr(self, "_safe_graphics_scene") else getattr(getattr(self, "view", None), "scene", None)
        items = list(getattr(self, "_maker_preview_overlay_items", []) or [])
        self._maker_preview_overlay_items = []
        if scene is None:
            return
        # Older preview builds did not always keep every dynamic overlay item in
        # _maker_preview_overlay_items.  Clear the whole high-z Maker preview layer
        # so each row selection reconstructs a fresh in-game screen instead of
        # stacking old standing pictures/message text on top of the new one.
        try:
            tracked = set(id(x) for x in items)
        except Exception:
            tracked = set()
        try:
            for item in list(scene.items()):
                try:
                    z = float(item.zValue())
                except Exception:
                    z = 0.0
                try:
                    marked = bool(item.data(0) == "maker_preview_overlay")
                except Exception:
                    marked = False
                if id(item) in tracked or marked or z >= 99000.0:
                    try:
                        item.setVisible(False)
                        scene.removeItem(item)
                    except RuntimeError:
                        continue
                    except Exception:
                        continue
        except RuntimeError:
            pass
        except Exception:
            # Fallback to the tracked list if a scene-wide scan fails.
            for item in items:
                try:
                    item.setVisible(False)
                    scene.removeItem(item)
                except Exception:
                    continue
        try:
            scene.update()
        except Exception:
            pass

    def _maker_page_canvas_geometry(self, page=None):
        # Maker preview uses a fixed game-screen coordinate system.  The left
        # viewer may scale this image as a whole, but message wrapping and window
        # layout must never depend on the current UI panel size.
        try:
            from ysb.tools.maker_project import normalize_maker_preview_settings
            page = page if isinstance(page, dict) else self.data.get(self.idx)
            st = normalize_maker_preview_settings((page or {}).get("maker_preview_settings") or {})
            canvas_w = int(st.get("screen_width") or 816)
            canvas_h = int(st.get("screen_height") or 624)
            meta = (page or {}).get("maker_page") or {}
            mw = int(meta.get("width") or 17)
            mh = int(meta.get("height") or 13)
        except Exception:
            canvas_w, canvas_h, mw, mh = 816, 624, 17, 13
        step_x = max(12, (canvas_w - 80) // max(1, min(int(mw or 17), 60)))
        step_y = max(12, (canvas_h - 140) // max(1, min(int(mh or 13), 45)))
        return canvas_w, canvas_h, step_x, step_y

    def _maker_event_xy_for_row(self, row, page=None):
        meta = row.get("maker_text_unit") if isinstance(row, dict) else None
        if not isinstance(meta, dict):
            return None
        try:
            if meta.get("event_x") is not None and meta.get("event_y") is not None:
                return int(meta.get("event_x") or 0), int(meta.get("event_y") or 0)
        except Exception:
            pass
        try:
            event_id = int(meta.get("event_id") or 0)
        except Exception:
            event_id = 0
        try:
            page = page if isinstance(page, dict) else self.data.get(self.idx)
            for ev in ((page or {}).get("maker_page") or {}).get("events") or []:
                if not isinstance(ev, dict):
                    continue
                if int(ev.get("id") or 0) == event_id:
                    return int(ev.get("x") or 0), int(ev.get("y") or 0)
        except Exception:
            pass
        # Backward-compatible fallback for projects imported before v0.4.
        # New projects persist event positions in maker_text_unit/maker_page, but old
        # pages can still read the cloned MapXXX.json once to find the event.
        try:
            project_dir = Path(str(getattr(self, "project_dir", "") or ""))
            map_file = str(meta.get("map_file") or "")
            candidates = [
                project_dir / "maker_game" / "data" / map_file,
                project_dir / "maker_game" / "www" / "data" / map_file,
            ]
            for path in candidates:
                if not path.is_file():
                    continue
                with path.open("r", encoding="utf-8-sig") as f:
                    map_data = json.load(f)
                for ev in (map_data.get("events") or []):
                    if isinstance(ev, dict) and int(ev.get("id") or 0) == event_id:
                        return int(ev.get("x") or 0), int(ev.get("y") or 0)
        except Exception:
            pass
        return None

    def _maker_local_map_crop_geometry(self, page=None):
        """Return the current local map preview geometry if stage-1 crop is active."""
        try:
            page = page if isinstance(page, dict) else self.data.get(self.idx)
            crop = ((page or {}).get("maker_page") or {}).get("preview_crop")
            if not isinstance(crop, dict) or not crop.get("enabled"):
                return None
            return {
                "x0": int(crop.get("x0") or 0),
                "y0": int(crop.get("y0") or 0),
                "x1": int(crop.get("x1") or 0),
                "y1": int(crop.get("y1") or 0),
                "cols": int(crop.get("cols") or 0),
                "rows": int(crop.get("rows") or 0),
                "tile_size": int(crop.get("tile_size") or 0),
                "origin_x": int(crop.get("origin_x") or 0),
                "origin_y": int(crop.get("origin_y") or 0),
                "focus_event_id": int(crop.get("focus_event_id") or 0),
            }
        except Exception:
            return None

    def _maker_event_scene_position_for_row(self, row, page=None):
        pos = self._maker_event_xy_for_row(row, page=page)
        if pos is None:
            return None
        ex, ey = pos
        crop = self._maker_local_map_crop_geometry(page)
        if crop:
            try:
                if ex < crop["x0"] or ex >= crop["x1"] or ey < crop["y0"] or ey >= crop["y1"]:
                    return None
                tile = max(1, int(crop["tile_size"]))
                return (
                    float(int(crop["origin_x"]) + (int(ex) - int(crop["x0"]) + 0.5) * tile),
                    float(int(crop["origin_y"]) + (int(ey) - int(crop["y0"]) + 0.5) * tile),
                )
            except Exception:
                pass
        _cw, _ch, step_x, step_y = self._maker_page_canvas_geometry(page)
        return float(40 + (ex + 0.5) * step_x), float(120 + (ey + 0.5) * step_y)

    def _refresh_maker_local_map_preview_background(self, row, page=None, settings=None):
        """Regenerate the current Maker map placeholder around the selected event.

        Stage 1 map preview is a generated background, not an editable text layer.
        It is safe to redraw because it only touches the project preview PNG, not
        maker_game JSON.
        """
        try:
            page = page if isinstance(page, dict) else self.data.get(self.idx)
            if not isinstance(page, dict) or not isinstance((page.get("maker_page") or {}), dict):
                return False
            meta = page.get("maker_page") or {}
            if str(meta.get("page_type") or "map") not in {"", "map"}:
                return False
            if not (0 <= int(getattr(self, "idx", -1)) < len(getattr(self, "paths", []) or [])):
                return False
            try:
                from ysb.tools.maker_project import normalize_maker_preview_settings, regenerate_maker_placeholder_for_selected_row
                st = normalize_maker_preview_settings(settings or page.get("maker_preview_settings") or {})
            except Exception:
                st = settings or page.get("maker_preview_settings") or {}
                from ysb.tools.maker_project import regenerate_maker_placeholder_for_selected_row
            if not bool((st or {}).get("show_local_map_preview", True)):
                return False
            image_path = Path(self.paths[int(self.idx)])
            ok = regenerate_maker_placeholder_for_selected_row(image_path, page, row, settings=st)
            if not ok:
                return False
            img = cv2.imdecode(np.fromfile(str(image_path), np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return False
            # 프리뷰 PNG를 다시 만든 뒤에는 원본/최종 표시 캐시를 모두 최신 PNG로 맞춘다.
            # bg_clean이 예전 디버그 그리드로 남아 있으면 final 모드가 타일 PNG 대신 그리드를 보여준다.
            page["ori"] = img.copy()
            page["bg_clean"] = img.copy()
            page["working_source"] = None
            try:
                page["bg_clean_path"] = str(image_path)
            except Exception:
                pass
            focus = ((page.get("maker_page") or {}).get("preview_crop") or {})
            try:
                stat = image_path.stat()
                file_marker = f":{int(stat.st_mtime_ns)}:{int(stat.st_size)}"
            except Exception:
                file_marker = ""
            key = f"page:{int(self.idx)}:maker_local:{focus.get('focus_event_id', 0)}:{focus.get('x0', 0)}:{focus.get('y0', 0)}:{focus.get('cols', 0)}:{focus.get('rows', 0)}{file_marker}"
            try:
                mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 4
            except Exception:
                mode = 4
            # Maker scene preview is rendered on the final/result tab.  If the
            # user is on analysis/mask tabs, only refresh the cached page image
            # and avoid clearing their current mode overlays.
            if mode == 4 and hasattr(self, "view") and hasattr(self.view, "set_layer_base_image"):
                self.view.set_layer_base_image(img, key=key, fit=False, clear_paint_history=False)
                self.view.clear_mode_layers(clear_boxes=True, clear_text=True, clear_mask=True, clear_final_paint=True)
                try:
                    self.view.set_final_paint_overlay(page.get('final_paint'), page.get('final_paint_above'), fit=False)
                    self.update_final_paint_z_order()
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _maker_preview_color(self, value, fallback="#FFFFFF"):
        try:
            text = str(value or fallback).strip()
            c = QColor(text)
            if c.isValid():
                return c
        except Exception:
            pass
        return QColor(str(fallback or "#FFFFFF"))

    def _maker_preview_project_root(self):
        """Return the active workspace root used for Maker runtime assets."""
        try:
            pd = str(getattr(self, "project_dir", "") or "").strip()
            if pd:
                return Path(pd).resolve()
        except Exception:
            pass
        try:
            pf = str(getattr(self, "project_json_path", "") or "").strip()
            if pf:
                return Path(pf).resolve().parent
        except Exception:
            pass
        return None

    def _maker_preview_read_system_json(self):
        root = self._maker_preview_project_root()
        checked = []
        if root is None:
            return {}, {"checked": checked, "found": False, "error": "project_root_missing"}
        candidates = [
            root / "maker_game" / "data" / "System.json",
            root / "maker_game" / "www" / "data" / "System.json",
        ]
        for c in candidates:
            try:
                checked.append(str(c))
                if c.is_file():
                    with c.open("r", encoding="utf-8-sig") as f:
                        return json.load(f), {"checked": checked, "found": True, "path": str(c)}
            except Exception as e:
                return {}, {"checked": checked, "found": False, "error": str(e), "error_type": type(e).__name__}
        return {}, {"checked": checked, "found": False, "error": "system_json_missing"}

    def _maker_preview_encryption_context(self):
        system, sdiag = self._maker_preview_read_system_json()
        key = ""
        has_images = False
        has_audio = False
        try:
            key = str((system or {}).get("encryptionKey") or "").strip()
            has_images = bool((system or {}).get("hasEncryptedImages"))
            has_audio = bool((system or {}).get("hasEncryptedAudio"))
        except Exception:
            pass
        return {
            "has_encrypted_images": has_images,
            "has_encrypted_audio": has_audio,
            "encryption_key": key,
            "system_json": sdiag,
        }

    def _maker_preview_is_encrypted_image_path(self, path):
        try:
            name = Path(path).name.lower()
            return name.endswith(".png_") or name.endswith(".jpg_") or name.endswith(".jpeg_") or name.endswith(".webp_") or name.endswith(".bmp_") or name.endswith(".rpgmvp") or name.endswith(".rpgmvp_")
        except Exception:
            return False

    def _maker_preview_cache_image_extension(self, path):
        name = Path(path).name.lower()
        for ext in (".png_", ".jpg_", ".jpeg_", ".webp_", ".bmp_"):
            if name.endswith(ext):
                return ext[:-1]
        if name.endswith(".rpgmvp") or name.endswith(".rpgmvp_"):
            return ".png"
        try:
            suf = Path(path).suffix.lower()
            return suf if suf in {".png", ".jpg", ".jpeg", ".webp", ".bmp"} else ".png"
        except Exception:
            return ".png"

    def _maker_preview_decrypt_image_asset(self, source_path, *, category="images"):
        """Decrypt RPG Maker MV/MZ encrypted image assets into a local cache.

        This is a preview-only cache.  The original game file is never modified.
        MZ encrypted images are commonly stored as .png_; MV may use .rpgmvp.
        Both use the RPGMV 16-byte header and XOR the first 16 body bytes with
        System.json encryptionKey, matching rmmz_core.js Utils.decryptArrayBuffer.
        """
        import hashlib
        diag = {"encrypted": True, "source_path": str(source_path), "category": str(category or "images"), "decrypt_attempted": False, "decrypt_success": False}
        try:
            src = Path(source_path)
            root = self._maker_preview_project_root()
            if root is None:
                diag["error"] = "project_root_missing"
                return None, diag
            if not src.is_file():
                diag["error"] = "source_missing"
                return None, diag
            ctx = self._maker_preview_encryption_context()
            key = str(ctx.get("encryption_key") or "").strip()
            diag["encryption_context"] = {k: v for k, v in ctx.items() if k != "encryption_key"}
            diag["key_present"] = bool(key)
            if len(key) < 32:
                diag["error"] = "encryption_key_missing_or_short"
                return None, diag
            ext = self._maker_preview_cache_image_extension(src)
            rel_for_hash = str(src)
            try:
                rel_for_hash = str(src.resolve().relative_to(root.resolve()))
            except Exception:
                pass
            digest = hashlib.sha1((rel_for_hash + "|" + str(src.stat().st_mtime_ns) + "|" + str(src.stat().st_size)).encode("utf-8", "ignore")).hexdigest()[:16]
            safe_stem = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in src.stem.replace(".png", "").replace(".jpg", "").replace(".jpeg", "").replace(".webp", "").replace(".bmp", ""))[:80] or "asset"
            cache_dir = root / "maker_meta" / "asset_cache" / str(category or "images")
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / f"{safe_stem}_{digest}{ext}"
            diag["cache_path"] = str(cache_path)
            if cache_path.is_file() and cache_path.stat().st_size > 8:
                diag.update({"decrypt_success": True, "cached": True, "output_path": str(cache_path)})
                return cache_path, diag
            data = src.read_bytes()
            diag["source_size"] = len(data)
            diag["decrypt_attempted"] = True
            # Accept RPGMV/RPGMZ/variant RPGM* headers.  MV/MZ decryption is the
            # same at this layer: drop the 16-byte header and XOR the first 16
            # body bytes with System.json encryptionKey.
            if len(data) >= 8 and data[:8] == b'\x89PNG\r\n\x1a\n':
                diag["plain_image_with_encrypted_extension"] = True
                cache_path.write_bytes(data)
                diag.update({"decrypt_success": True, "cached": False, "output_path": str(cache_path), "output_size": cache_path.stat().st_size})
                return cache_path, diag
            if len(data) < 16 or data[:4] != b'RPGM':
                diag["error"] = "encrypted_header_mismatch"
                diag["header_hex"] = data[:16].hex(",") if data else ""
                return None, diag
            diag["header_ascii"] = data[:8].decode("ascii", "replace")
            body = bytearray(data[16:])
            key_bytes = bytes(int(key[i:i+2], 16) for i in range(0, min(32, len(key)), 2))
            if len(key_bytes) < 16:
                diag["error"] = "encryption_key_parse_failed"
                return None, diag
            for i in range(min(16, len(body))):
                body[i] ^= key_bytes[i]
            cache_path.write_bytes(bytes(body))
            diag.update({"decrypt_success": True, "cached": False, "output_path": str(cache_path), "output_size": cache_path.stat().st_size})
            return cache_path, diag
        except Exception as e:
            diag["error"] = str(e)
            diag["error_type"] = type(e).__name__
            return None, diag

    def _maker_preview_prepare_image_asset(self, path, *, category="images"):
        diag = {"source_path": str(path) if path else "", "encrypted": False}
        if path is None:
            diag["error"] = "path_missing"
            return None, diag
        try:
            p = Path(path)
            if self._maker_preview_is_encrypted_image_path(p):
                cache_path, ddiag = self._maker_preview_decrypt_image_asset(p, category=category)
                diag.update(ddiag or {})
                if cache_path is not None and Path(cache_path).is_file():
                    return Path(cache_path), diag
                return None, diag
            if p.is_file():
                return p, diag
            diag["error"] = "source_missing"
            return None, diag
        except Exception as e:
            diag["error"] = str(e)
            diag["error_type"] = type(e).__name__
            return None, diag

    def _maker_preview_find_font_source_path(self, font_path, settings=None):
        """Resolve Maker font paths robustly from project-relative values.

        MZ stores values like maker_game/fonts/mplus-1m-regular.woff in the
        preview settings.  If the current working directory differs from the
        project workspace, directly resolving that string fails and the renderer
        silently falls back to Verdana.  Search the active workspace first, then
        maker_game/fonts by filename, case-insensitively.
        """
        settings = settings or {}
        root = self._maker_preview_project_root()
        raw = str(font_path or "").strip()
        filename_hints = []
        try:
            if raw:
                filename_hints.append(Path(raw).name)
        except Exception:
            pass
        for k in ("main_font_filename", "number_font_filename"):
            try:
                v = str(settings.get(k) or "").strip()
                if v:
                    filename_hints.append(Path(v).name)
            except Exception:
                pass
        candidates = []
        try:
            if raw:
                p0 = Path(raw)
                candidates.append(p0)
                if root is not None and not p0.is_absolute():
                    candidates.append(root / p0)
        except Exception:
            pass
        if root is not None:
            for name in filename_hints:
                if not name:
                    continue
                for base in (root / "maker_game" / "fonts", root / "maker_game" / "www" / "fonts", root / "fonts"):
                    candidates.append(base / name)
        checked = []
        for c in candidates:
            try:
                cp = Path(c).expanduser()
                if not cp.is_absolute() and root is not None:
                    cp = root / cp
                cp = cp.resolve()
                checked.append(str(cp))
                if cp.is_file():
                    return cp, {"raw": raw, "resolved": str(cp), "checked": checked, "found_by": "direct_or_project_relative"}
            except Exception:
                continue
        # Case-insensitive fallback for unpacked game folders copied from other OSes.
        if root is not None:
            wanted = {str(x).lower() for x in filename_hints if x}
            for base in (root / "maker_game" / "fonts", root / "maker_game" / "www" / "fonts", root / "fonts"):
                try:
                    if not base.is_dir():
                        continue
                    for f in base.iterdir():
                        if f.is_file() and f.name.lower() in wanted:
                            checked.append(str(f.resolve()))
                            return f.resolve(), {"raw": raw, "resolved": str(f.resolve()), "checked": checked, "found_by": "case_insensitive_fonts_scan"}
                except Exception:
                    pass
        return None, {"raw": raw, "resolved": "", "checked": checked, "found_by": "not_found"}

    def _maker_preview_font_runtime_deps_available(self):
        """Return availability of WOFF conversion dependencies.

        RPG Maker MZ often stores the real game font as WOFF/WOFF2.  Qt does not
        reliably load those files directly, so the preview converts them through
        fontTools/brotli.  This helper is intentionally kept in the UI layer so
        missing dependencies can be diagnosed from the same preview log the user
        sends back.
        """
        out = {"fonttools_available": False, "brotli_available": False}
        try:
            import importlib.util as _importlib_util
            out["fonttools_available"] = _importlib_util.find_spec("fontTools") is not None
            out["brotli_available"] = _importlib_util.find_spec("brotli") is not None
        except Exception as e:
            out["check_error"] = str(e)
        return out

    def _maker_preview_try_install_font_runtime_deps(self):
        """Best-effort source-mode install for WOFF conversion dependencies.

        This is only attempted when running from source/venv.  For frozen EXE
        builds, dependencies must be bundled at build time; the diagnostics will
        say so instead of silently falling back to a different font.
        """
        import sys
        import subprocess
        diag = dict(self._maker_preview_font_runtime_deps_available())
        diag["attempted"] = False
        diag["success"] = bool(diag.get("fonttools_available") and diag.get("brotli_available"))
        diag["python"] = sys.executable
        diag["frozen"] = bool(getattr(sys, "frozen", False))
        if diag["success"]:
            self._append_maker_preview_diagnostic("ui_font_runtime_deps_present", diag)
            return diag
        if diag.get("frozen"):
            diag["error"] = "frozen_build_missing_fonttools_or_brotli"
            self._append_maker_preview_diagnostic("ui_font_runtime_deps_missing", diag)
            self._last_maker_preview_font_deps_diag = dict(diag)
            return diag
        # Avoid repeatedly invoking pip during one session.
        if bool(getattr(self, "_maker_preview_font_deps_install_attempted", False)):
            diag["error"] = "install_already_attempted_this_session"
            self._append_maker_preview_diagnostic("ui_font_runtime_deps_missing", diag)
            self._last_maker_preview_font_deps_diag = dict(diag)
            return diag
        self._maker_preview_font_deps_install_attempted = True
        diag["attempted"] = True
        cmd = [sys.executable, "-m", "pip", "install", "fonttools", "brotli"]
        diag["cmd"] = cmd
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            diag["returncode"] = int(proc.returncode)
            diag["stdout_tail"] = (proc.stdout or "")[-4000:]
            diag["stderr_tail"] = (proc.stderr or "")[-4000:]
        except Exception as e:
            diag["error"] = f"pip_install_exception: {e}"
            self._append_maker_preview_diagnostic("ui_font_runtime_deps_install_failed", diag)
            self._last_maker_preview_font_deps_diag = dict(diag)
            return diag
        after = self._maker_preview_font_runtime_deps_available()
        diag.update({
            "fonttools_available_after": after.get("fonttools_available"),
            "brotli_available_after": after.get("brotli_available"),
        })
        diag["success"] = bool(after.get("fonttools_available") and after.get("brotli_available") and diag.get("returncode") == 0)
        self._append_maker_preview_diagnostic(
            "ui_font_runtime_deps_install_success" if diag["success"] else "ui_font_runtime_deps_install_failed",
            diag,
        )
        self._last_maker_preview_font_deps_diag = dict(diag)
        return diag

    def _maker_preview_qt_compatible_font_path(self, path):
        """Return a Qt-loadable cached path for the selected Maker font.

        Qt keeps application fonts cached inside the running process.  When the
        user replaces a font file at the same path, loading that same path may
        still show the old font until restart.  To make font changes apply while
        the editor is open, every supported font file is loaded from a fingerprint
        cache path under maker_meta/font_cache.  TTF/OTF/TTC are copied as-is;
        WOFF/WOFF2 are converted to TTF when possible.
        """
        diag = {
            "input_path": str(path or ""),
            "output_path": str(path or ""),
            "converted": False,
            "copied": False,
            "format": "",
            "error": "",
            "fonttools_available": False,
            "brotli_available": False,
            "source_exists": False,
            "source_size": 0,
        }
        try:
            src = Path(str(path or ""))
            if not src.is_absolute():
                root = self._maker_preview_project_root()
                if root is not None:
                    src = root / src
            src = src.resolve()
            diag["input_path"] = str(src)
            suffix = src.suffix.lower()
            diag["format"] = suffix.lstrip(".")
            diag["source_exists"] = bool(src.is_file())
            try:
                diag["source_size"] = int(src.stat().st_size) if src.is_file() else 0
            except Exception:
                pass
            if suffix not in {".ttf", ".otf", ".ttc", ".woff", ".woff2"}:
                self._append_maker_preview_diagnostic("ui_font_cache_not_supported", diag)
                self._last_maker_preview_font_conversion_diag = dict(diag)
                return src, ""
            if not src.is_file():
                diag["error"] = "source_missing"
                self._append_maker_preview_diagnostic("ui_font_cache_prepare_failed", diag)
                self._last_maker_preview_font_conversion_diag = dict(diag)
                return src, "source_missing"
            root = self._maker_preview_project_root()
            if root is None:
                diag["error"] = "project_root_missing"
                self._append_maker_preview_diagnostic("ui_font_cache_prepare_failed", diag)
                self._last_maker_preview_font_conversion_diag = dict(diag)
                return src, "project_root_missing"
            cache_dir = root / "maker_meta" / "font_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            try:
                (cache_dir / ".ysb_keep").write_text("keep\n", encoding="utf-8")
            except Exception:
                pass
            import hashlib
            stat = src.stat()
            mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
            digest_src = f"{src}|{stat.st_size}|{mtime_ns}"
            digest = hashlib.sha1(digest_src.encode("utf-8", errors="ignore")).hexdigest()[:12]

            if suffix in {".ttf", ".otf", ".ttc"}:
                target = cache_dir / f"{src.stem}_{digest}{suffix}"
                diag["output_path"] = str(target)
                self._append_maker_preview_diagnostic("ui_font_cache_copy_start", diag)
                if not target.is_file() or target.stat().st_size <= 0:
                    import shutil
                    shutil.copy2(str(src), str(target))
                diag["output_path"] = str(target.resolve())
                diag["copied"] = True
                try:
                    diag["target_size"] = int(target.stat().st_size)
                except Exception:
                    pass
                self._append_maker_preview_diagnostic("ui_font_cache_copy_success", diag)
                self._last_maker_preview_font_conversion_diag = dict(diag)
                return target.resolve(), ""

            dep_diag = self._maker_preview_font_runtime_deps_available()
            diag.update(dep_diag)
            if not (diag.get("fonttools_available") and diag.get("brotli_available")):
                dep_install = self._maker_preview_try_install_font_runtime_deps()
                diag["dependency_install"] = dep_install
                diag["fonttools_available"] = bool(dep_install.get("fonttools_available_after") or dep_install.get("fonttools_available"))
                diag["brotli_available"] = bool(dep_install.get("brotli_available_after") or dep_install.get("brotli_available"))
            self._append_maker_preview_diagnostic("ui_font_cache_convert_start", diag)
            target = cache_dir / f"{src.stem}_{digest}.ttf"
            diag["output_path"] = str(target)
            if not target.is_file() or target.stat().st_size <= 0:
                try:
                    from fontTools.ttLib import TTFont  # type: ignore
                    font = TTFont(str(src))
                    font.flavor = None
                    font.save(str(target))
                except Exception as e:
                    diag["error"] = f"fonttools_convert_failed: {e}"
                    self._append_maker_preview_diagnostic("ui_font_cache_prepare_failed", diag)
                    self._last_maker_preview_font_conversion_diag = dict(diag)
                    return src, diag["error"]
            diag["output_path"] = str(target.resolve())
            diag["converted"] = True
            try:
                diag["target_size"] = int(target.stat().st_size)
            except Exception:
                pass
            self._append_maker_preview_diagnostic("ui_font_cache_convert_success", diag)
            self._last_maker_preview_font_conversion_diag = dict(diag)
            return target.resolve(), ""
        except Exception as e:
            diag["error"] = f"unexpected: {e}"
            self._append_maker_preview_diagnostic("ui_font_cache_prepare_failed", diag)
            self._last_maker_preview_font_conversion_diag = dict(diag)
            try:
                return Path(str(path or "")).resolve(), diag["error"]
            except Exception:
                return Path(str(path or "")), diag["error"]

    def _maker_preview_resolve_font_family(self, settings):
        st = settings or {}
        family = str(st.get("font_family") or "맑은 고딕").strip() or "맑은 고딕"
        requested_family_raw = family
        try:
            if "," in family:
                family = family.split(",", 1)[0].strip().strip("'\"") or family
        except Exception:
            pass
        font_path = str(st.get("font_path") or "").strip()
        loaded_from_file = False
        diag = {
            "requested_family_raw": requested_family_raw,
            "requested_family_initial": family,
            "font_path": font_path,
            "fallback_fonts": str(st.get("fallback_fonts") or ""),
            "load_attempted": bool(font_path),
            "load_success": False,
            "fallback_used": False,
            "convert_error": "",
            "source_path": "",
            "source_exists": False,
            "source_resolution": {},
            "qt_path": "",
            "qt_path_exists": False,
            "font_id": None,
            "families": [],
            "selected_family": family,
        }
        if font_path:
            try:
                source, source_diag = self._maker_preview_find_font_source_path(font_path, st)
                diag["source_resolution"] = source_diag
                if source is not None:
                    diag["source_path"] = str(source)
                    diag["source_exists"] = bool(source.is_file())
                else:
                    diag["source_path"] = ""
                    diag["source_exists"] = False
                candidate = source if source is not None else Path(font_path)
                if not candidate.is_absolute():
                    root = self._maker_preview_project_root()
                    if root is not None:
                        candidate = root / candidate
                candidate = candidate.resolve()
                loaded = getattr(self, "_maker_preview_loaded_font_paths", set())
                if not isinstance(loaded, set):
                    loaded = set()
                loaded_map = getattr(self, "_maker_preview_loaded_font_families", {})
                if not isinstance(loaded_map, dict):
                    loaded_map = {}
                convert_error = ""
                qt_candidate, convert_error = self._maker_preview_qt_compatible_font_path(candidate)
                # If conversion failed, still try direct Qt loading once.  Some Qt
                # builds can load WOFF; when they cannot, the diagnostics will say so.
                if convert_error and not qt_candidate.is_file() and candidate.is_file():
                    qt_candidate = candidate
                key = str(qt_candidate.resolve()) if qt_candidate else str(candidate)
                diag["qt_path"] = key
                diag["qt_path_exists"] = bool(Path(key).is_file())
                diag["convert_error"] = str(convert_error or "")
                conv_diag = dict(getattr(self, "_last_maker_preview_font_conversion_diag", {}) or {})
                if conv_diag:
                    diag["conversion"] = conv_diag
                if Path(key).is_file():
                    if key not in loaded:
                        font_id = QFontDatabase.addApplicationFont(key)
                        diag["font_id"] = int(font_id)
                        if int(font_id) >= 0:
                            loaded.add(key)
                            families = [str(x) for x in QFontDatabase.applicationFontFamilies(int(font_id))]
                            diag["families"] = families
                            if families:
                                family = families[0]
                                loaded_map[key] = family
                                loaded_from_file = True
                                diag["load_success"] = True
                                diag["selected_family_from_file"] = family
                                diag["selected_family"] = family
                            self._maker_preview_loaded_font_paths = loaded
                            self._maker_preview_loaded_font_families = loaded_map
                            self._append_maker_preview_diagnostic("ui_font_database_load_success", {
                                "requested_path": str(font_path),
                                "source_path": diag.get("source_path"),
                                "qt_path": key,
                                "font_id": int(font_id),
                                "families": families,
                                "selected_family": family,
                                "convert_error": convert_error,
                            })
                        else:
                            self._append_maker_preview_diagnostic("ui_font_database_load_failed", {
                                "requested_path": str(font_path),
                                "source_path": diag.get("source_path"),
                                "qt_path": key,
                                "font_id": int(font_id),
                                "convert_error": convert_error,
                                "candidate_exists": bool(Path(key).is_file()),
                            })
                    else:
                        saved_family = str(loaded_map.get(key) or "").strip()
                        if saved_family:
                            family = saved_family
                        loaded_from_file = True
                        diag["load_success"] = True
                        diag["selected_family_from_file"] = family
                        diag["selected_family"] = family
                        diag["qt_path"] = key
                        self._append_maker_preview_diagnostic("ui_font_database_cached_family", {"qt_path": key, "selected_family": family})
            except Exception as e:
                diag["exception"] = str(e)
                diag["exception_type"] = type(e).__name__
                self._append_maker_preview_diagnostic("ui_font_resolution_failed", diag)
        if not loaded_from_file:
            # Keep the game-requested family as the requested family so QFontInfo
            # can expose the mismatch.  Do not silently request Verdana unless the
            # game did not provide any family at all.
            if not family or family in {"맑은 고딕", "Malgun Gothic"}:
                try:
                    fallback = str(st.get("fallback_fonts") or "").strip()
                    if fallback:
                        cand = fallback.split(",", 1)[0].strip().strip("'\"")
                        if cand and cand.lower() not in {"sans-serif", "serif", "monospace"}:
                            family = cand
                            diag["fallback_used"] = True
                            diag["selected_family"] = family
                except Exception:
                    pass
        diag["selected_family"] = family
        diag["load_success"] = bool(loaded_from_file)
        self._last_maker_preview_font_load_diag = dict(diag)
        self._append_maker_preview_diagnostic("ui_font_resolution", diag)
        return family

    def _maker_preview_font(self, settings, *, text_type="text", bold=False, size_override=None):
        st = settings or {}
        family = self._maker_preview_resolve_font_family(st)
        try:
            if size_override is not None:
                size = int(size_override)
            elif str(text_type or "").startswith("choice"):
                size = int(st.get("choice_font_size") or st.get("font_size") or 26)
            else:
                size = int(st.get("font_size") or 28)
        except Exception:
            size = 28
        font = QFont(family)
        try:
            # RPG Maker preview settings are in screen pixels, not typographic
            # points.  Pixel size keeps the line metric stable across displays.
            font.setPixelSize(max(6, min(160, int(size))))
        except Exception:
            font.setPointSize(max(6, min(96, int(size))))
        try:
            font.setBold(bool(bold))
        except Exception:
            pass
        try:
            font.setStretch(max(10, min(300, int(st.get("char_width") or 100))))
        except Exception:
            pass
        try:
            letter = int(st.get("letter_spacing") or 0)
            if letter:
                font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(letter))
        except Exception:
            pass
        try:
            info = QFontInfo(font)
            self._last_maker_preview_font_diag = {
                "requested_family": family,
                "actual_family": str(info.family()),
                "exact_match": bool(info.exactMatch()),
                "pixel_size": int(font.pixelSize()),
                "point_size": int(font.pointSize()),
                "bold": bool(font.bold()),
                "stretch": int(font.stretch()),
                "text_type": str(text_type or "text"),
            }
        except Exception:
            self._last_maker_preview_font_diag = {"requested_family": family, "text_type": str(text_type or "text")}
        return font

    def _maker_preview_resolve_asset_path(self, rel_path, *, profile=None, subdirs=()):
        """Resolve a Maker asset path and return a renderable local path.

        Normal images are returned directly.  Encrypted MV/MZ images such as
        Window.png_ or *.rpgmvp are decrypted into maker_meta/asset_cache first
        so QPixmap can render them without modifying the original game files.
        """
        root = self._maker_preview_project_root()
        raw = str(rel_path or "").strip().replace("\\", "/")
        checked = []
        encrypted_checked = []
        if not raw:
            return None, {"raw": raw, "checked": checked, "found_by": "empty"}
        candidates = []
        try:
            p = Path(raw)
            candidates.append(p)
            if root is not None and not p.is_absolute():
                candidates.append(root / p)
        except Exception:
            pass
        if root is not None:
            for sub in subdirs or ():
                try:
                    clean_sub = str(sub).strip("/\\")
                    candidates.append(root / "maker_game" / clean_sub / raw)
                    candidates.append(root / "maker_game" / "www" / clean_sub / raw)
                except Exception:
                    pass

        def encrypted_variants(cp):
            out = []
            try:
                cp = Path(cp)
                name = cp.name
                lower = name.lower()
                if lower.endswith(".png") or lower.endswith(".jpg") or lower.endswith(".jpeg") or lower.endswith(".webp") or lower.endswith(".bmp"):
                    out.append(Path(str(cp) + "_"))
                if lower.endswith(".png"):
                    out.append(cp.with_suffix(".rpgmvp"))
                    out.append(cp.with_suffix(".rpgmvp_"))
            except Exception:
                pass
            return out

        last_diag = {"raw": raw, "checked": checked, "encrypted_checked": encrypted_checked, "found_by": "not_found"}
        for c in candidates:
            try:
                cp = Path(c).expanduser()
                if not cp.is_absolute() and root is not None:
                    cp = root / cp
                cp = cp.resolve()
                checked.append(str(cp))
                if cp.is_file():
                    rpath, rdiag = self._maker_preview_prepare_image_asset(cp, category="system" if "img/system" in str(cp).replace("\\", "/") else "images")
                    diag = {"raw": raw, "resolved": str(rpath) if rpath else "", "source_resolved": str(cp), "checked": checked, "encrypted_checked": encrypted_checked, "found_by": "direct", "asset": rdiag}
                    return rpath, diag
                for ep in encrypted_variants(cp):
                    try:
                        ep = ep.resolve()
                        encrypted_checked.append(str(ep))
                        if ep.is_file():
                            rpath, rdiag = self._maker_preview_prepare_image_asset(ep, category="system" if "img/system" in str(ep).replace("\\", "/") else "images")
                            diag = {"raw": raw, "resolved": str(rpath) if rpath else "", "source_resolved": str(ep), "checked": checked, "encrypted_checked": encrypted_checked, "found_by": "encrypted_variant", "asset": rdiag}
                            return rpath, diag
                    except Exception:
                        pass
            except Exception:
                continue
        return last_diag.get("resolved_path"), last_diag

    def _maker_preview_window_skin_path(self, profile=None):
        profile = profile if isinstance(profile, dict) else {}
        win = profile.get("window") if isinstance(profile.get("window"), dict) else {}
        skin = str(win.get("skin") or "").strip()
        if skin:
            path, diag = self._maker_preview_resolve_asset_path(skin, profile=profile)
            if path is not None:
                return path, diag
        # Stable RPG Maker default location.
        path, diag = self._maker_preview_resolve_asset_path("maker_game/img/system/Window.png", profile=profile)
        if path is not None:
            return path, diag
        path, diag = self._maker_preview_resolve_asset_path("maker_game/www/img/system/Window.png", profile=profile)
        if path is not None:
            return path, diag
        return None, diag

    def _maker_preview_build_window_pixmap(self, width, height, *, opacity=205, profile=None):
        """Build an MZ/MV-style Window.png based window pixmap.

        RPG Maker windows are not plain rectangles.  For MZ/MV Window.png the
        0,0,96,96 block is the tiled/filled back and 96,0,96,96 is the frame.
        This approximation is intentionally engine-safe: it only uses the window
        skin if present and otherwise falls back to the old rectangle renderer.
        """
        diag = {"loaded": False, "source_path": "", "width": int(width or 0), "height": int(height or 0)}
        try:
            w = max(1, int(width))
            h = max(1, int(height))
            op = max(0, min(255, int(opacity)))
        except Exception:
            return None, {**diag, "error": "invalid_size"}
        try:
            path, path_diag = self._maker_preview_window_skin_path(profile=profile)
            diag["path_resolution"] = path_diag
            if path is None:
                diag["error"] = "window_skin_missing"
                return None, diag
            src = QPixmap(str(path))
            diag["source_path"] = str(path)
            diag["source_width"] = int(src.width())
            diag["source_height"] = int(src.height())
            if src.isNull() or src.width() < 192 or src.height() < 96:
                diag["error"] = "window_skin_invalid_or_too_small"
                return None, diag
            key = (str(path), w, h, op, int(src.width()), int(src.height()))
            cache = getattr(self, "_maker_preview_window_pixmap_cache", {}) or {}
            if key in cache:
                diag.update({"loaded": True, "cached": True})
                return cache[key], diag
            pm = QPixmap(w, h)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            try:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
                # Back layer. MZ tiles internally, but a scaled 96x96 back is a
                # close and stable preview approximation; opacity follows
                # System.json advanced.windowOpacity.
                back = src.copy(0, 0, 96, 96)
                painter.setOpacity(float(op) / 255.0)
                painter.drawPixmap(QRect(0, 0, w, h), back, QRect(0, 0, 96, 96))
                painter.setOpacity(1.0)
                # Frame 9-slice from the 96x96 frame block.
                frame = src.copy(96, 0, 96, 96)
                b = 24
                # corners
                pieces = [
                    (QRect(0, 0, b, b), QRect(0, 0, b, b)),
                    (QRect(96-b, 0, b, b), QRect(w-b, 0, b, b)),
                    (QRect(0, 96-b, b, b), QRect(0, h-b, b, b)),
                    (QRect(96-b, 96-b, b, b), QRect(w-b, h-b, b, b)),
                    # edges
                    (QRect(b, 0, 96-2*b, b), QRect(b, 0, max(1, w-2*b), b)),
                    (QRect(b, 96-b, 96-2*b, b), QRect(b, h-b, max(1, w-2*b), b)),
                    (QRect(0, b, b, 96-2*b), QRect(0, b, b, max(1, h-2*b))),
                    (QRect(96-b, b, b, 96-2*b), QRect(w-b, b, b, max(1, h-2*b))),
                ]
                for src_rect, dst_rect in pieces:
                    painter.drawPixmap(dst_rect, frame, src_rect)
            finally:
                painter.end()
            cache[key] = pm
            self._maker_preview_window_pixmap_cache = cache
            diag.update({"loaded": True, "cached": False, "slice_border": 24})
            return pm, diag
        except Exception as e:
            diag["error"] = str(e)
            diag["error_type"] = type(e).__name__
            return None, diag

    def _maker_preview_add_window_item(self, scene, x, y, width, height, *, z=100000, opacity=205, profile=None, fallback_pen=None, fallback_brush=None):
        pm, diag = self._maker_preview_build_window_pixmap(width, height, opacity=opacity, profile=profile)
        if pm is not None and not pm.isNull():
            item = QGraphicsPixmapItem(pm)
            item.setPos(float(x), float(y))
            item.setZValue(float(z))
            scene.addItem(item)
            return item, diag
        rect = QGraphicsRectItem(QRectF(float(x), float(y), float(width), float(height)))
        rect.setPen(fallback_pen or QPen(QColor(150, 185, 255, 230), 3))
        rect.setBrush(fallback_brush or QBrush(QColor(8, 10, 12, max(0, min(255, int(opacity or 205))))))
        rect.setZValue(float(z))
        scene.addItem(rect)
        return rect, diag

    def _maker_preview_picture_asset_path(self, name):
        root = self._maker_preview_project_root()
        raw = str(name or "").strip().replace("\\", "/")
        if not raw:
            return None, {"raw": raw, "checked": [], "found_by": "empty"}
        checked = []
        try:
            from urllib.parse import unquote
            raw_variants = [raw, unquote(raw)]
        except Exception:
            raw_variants = [raw]
        # RPG Maker picture command omits extension.  Keep the exact filename
        # first, then try common image extensions.  Some deployed titles may keep
        # encrypted .rpgmvp files; we still report those clearly even though Qt
        # cannot render them without game-side decryption.
        exts = (".png", ".PNG", ".png_", ".PNG_", ".jpg", ".jpg_", ".jpeg", ".jpeg_", ".webp", ".webp_", ".bmp", ".bmp_", ".rpgmvp", ".rpgmvp_")
        base_names = []
        for rv in raw_variants:
            rv = str(rv or "").strip().replace("\\", "/")
            if not rv:
                continue
            base_names.append(rv)
            if Path(rv).suffix == "":
                base_names.extend([rv + ext for ext in exts])
        # de-duplicate while preserving order
        seen_names = set()
        base_names = [x for x in base_names if not (x.lower() in seen_names or seen_names.add(x.lower()))]
        if root is not None:
            direct_dirs = (
                root / "maker_game" / "img" / "pictures",
                root / "maker_game" / "www" / "img" / "pictures",
            )
            for base in direct_dirs:
                for bn in base_names:
                    try:
                        p = (base / bn).resolve()
                        checked.append(str(p))
                        if p.is_file():
                            rpath, rdiag = self._maker_preview_prepare_image_asset(p, category="pictures")
                            return rpath, {"raw": raw, "resolved": str(rpath) if rpath else "", "source_resolved": str(p), "checked": checked, "found_by": "pictures_dir", "asset": rdiag}
                    except Exception:
                        pass
                # Case-insensitive direct scan.
                try:
                    if base.is_dir():
                        want = {Path(x).name.lower() for x in base_names}
                        for f in base.iterdir():
                            if f.is_file() and f.name.lower() in want:
                                rpath, rdiag = self._maker_preview_prepare_image_asset(f.resolve(), category="pictures")
                                return rpath, {"raw": raw, "resolved": str(rpath) if rpath else "", "source_resolved": str(f.resolve()), "checked": checked, "found_by": "case_insensitive_pictures_scan", "asset": rdiag}
                except Exception:
                    pass
            # Last-resort recursive scan under img.  This catches projects that
            # put pictures in subfolders or copy assets with different casing.
            try:
                wanted_stems = {Path(x).stem.lower() for x in base_names}
                wanted_names = {Path(x).name.lower() for x in base_names}
                allowed_exts = {e.lower() for e in exts}
                for img_root in (root / "maker_game" / "img", root / "maker_game" / "www" / "img"):
                    if not img_root.is_dir():
                        continue
                    # keep scans bounded; picture folders are normally small enough.
                    for f in img_root.rglob("*"):
                        try:
                            if not f.is_file():
                                continue
                            lname = f.name.lower()
                            if lname in wanted_names or (f.stem.lower() in wanted_stems and f.suffix.lower() in allowed_exts):
                                rpath, rdiag = self._maker_preview_prepare_image_asset(f.resolve(), category="pictures")
                                return rpath, {"raw": raw, "resolved": str(rpath) if rpath else "", "source_resolved": str(f.resolve()), "checked": checked, "found_by": "recursive_img_scan", "asset": rdiag}
                        except Exception:
                            continue
            except Exception as e:
                checked.append(f"recursive_scan_error:{e}")
        return None, {"raw": raw, "checked": checked, "found_by": "not_found"}

    def _maker_preview_collect_picture_state_for_row(self, row, page=None):
        """Return Show Picture state at the selected text command.

        MZ visual-novel style scenes often stack multiple pictures (body layer,
        face layer, effects) before a Show Text command.  Simulate picture slots
        from the beginning of the event page up to the selected command index.
        """
        diag = {"enabled": False, "reason": "not_available", "pictures": []}
        try:
            meta = (row or {}).get("maker_text_unit") or {}
            map_file = str(meta.get("map_file") or "").strip()
            event_id = int(meta.get("event_id") or 0)
            page_index = int(meta.get("page_index") or 0)
            command_index = int(meta.get("command_index") or 0)
            if not map_file or event_id <= 0:
                diag["reason"] = "missing_map_or_event"
                return [], diag
            project_dir = self._maker_preview_project_root()
            if project_dir is None:
                diag["reason"] = "project_root_missing"
                return [], diag

            source_kind = str(meta.get("source_kind") or "").strip().lower()
            is_common_event = source_kind == "common_event" or map_file.lower() == "commonevents.json"
            candidates = [
                project_dir / "maker_game" / "data" / map_file,
                project_dir / "maker_game" / "www" / "data" / map_file,
            ]
            map_path = next((p for p in candidates if p.is_file()), None)
            if map_path is None:
                diag.update({"reason": "source_file_missing", "checked": [str(p) for p in candidates], "source_kind": source_kind})
                return [], diag
            with map_path.open("r", encoding="utf-8-sig") as f:
                obj = json.load(f)

            if is_common_event:
                ce = None
                if isinstance(obj, list):
                    for e in obj:
                        if isinstance(e, dict) and int(e.get("id") or 0) == event_id:
                            ce = e
                            break
                    if ce is None and 0 <= event_id < len(obj) and isinstance(obj[event_id], dict):
                        ce = obj[event_id]
                if not isinstance(ce, dict):
                    diag.update({"reason": "common_event_not_found", "source_kind": source_kind, "common_event_id": event_id})
                    return [], diag
                commands = ce.get("list") or []
                diag.update({"source_kind": "common_event", "common_event_id": event_id, "common_event_name": str(ce.get("name") or "")})
            else:
                ev = None
                for e in obj.get("events") or []:
                    if isinstance(e, dict) and int(e.get("id") or 0) == event_id:
                        ev = e
                        break
                if not isinstance(ev, dict):
                    diag["reason"] = "event_not_found"
                    return [], diag
                pages = ev.get("pages") or []
                if page_index < 0 or page_index >= len(pages):
                    diag["reason"] = "page_index_out_of_range"
                    return [], diag
                commands = (pages[page_index] or {}).get("list") or []
            slots = {}
            for idx, cmd in enumerate(commands):
                if idx > command_index:
                    break
                if not isinstance(cmd, dict):
                    continue
                code = int(cmd.get("code") or 0)
                params = cmd.get("parameters") or []
                if code == 231 and len(params) >= 9:  # Show Picture
                    try:
                        pic_id = int(params[0])
                        name = str(params[1] or "")
                        origin = int(params[2] or 0)
                        # MV stores an extra "direct/variable coordinate" flag at
                        # parameters[3].  If we read it as X, scaleX becomes Y and
                        # the standing picture flips vertically.  MZ/older profiles
                        # may omit that flag, so support both layouts.
                        if len(params) >= 10 and str(params[3]) in {"0", "1", "True", "False", "true", "false"}:
                            direct = params[3]
                            x = float(params[4] or 0)
                            y = float(params[5] or 0)
                            sx = float(params[6] if params[6] is not None else 100)
                            sy = float(params[7] if params[7] is not None else 100)
                            opacity = float(params[8] if params[8] is not None else 255)
                            blend = int(params[9] or 0)
                            layout = "mv_direct_flag"
                        else:
                            direct = 0
                            x = float(params[3] or 0)
                            y = float(params[4] or 0)
                            sx = float(params[5] if params[5] is not None else 100)
                            sy = float(params[6] if params[6] is not None else 100)
                            opacity = float(params[7] if params[7] is not None else 255)
                            blend = int(params[8] or 0)
                            layout = "mz_or_legacy"
                        path, pdiag = self._maker_preview_picture_asset_path(name)
                        slots[pic_id] = {
                            "id": pic_id, "name": name, "origin": origin, "x": x, "y": y,
                            "scale_x": sx, "scale_y": sy, "opacity": opacity, "blend_mode": blend,
                            "direct_flag": direct, "parameter_layout": layout,
                            "path": str(path) if path else "", "path_diag": pdiag, "command_index": idx,
                        }
                    except Exception:
                        continue
                elif code == 232 and len(params) >= 9:  # Move Picture
                    try:
                        pic_id = int(params[0])
                        if pic_id in slots:
                            if len(params) >= 11 and str(params[2]) in {"0", "1", "True", "False", "true", "false"}:
                                origin = int(params[1] or slots[pic_id].get("origin") or 0)
                                direct = params[2]
                                x = float(params[3] or 0)
                                y = float(params[4] or 0)
                                sx = float(params[5] if params[5] is not None else 100)
                                sy = float(params[6] if params[6] is not None else 100)
                                opacity = float(params[7] if params[7] is not None else 255)
                                blend = int(params[8] or 0)
                                layout = "mv_direct_flag"
                            else:
                                origin = int(params[1] or slots[pic_id].get("origin") or 0)
                                direct = 0
                                x = float(params[2] or 0)
                                y = float(params[3] or 0)
                                sx = float(params[4] if params[4] is not None else 100)
                                sy = float(params[5] if params[5] is not None else 100)
                                opacity = float(params[6] if params[6] is not None else 255)
                                blend = int(params[7] or 0)
                                layout = "mz_or_legacy"
                            slots[pic_id].update({
                                "origin": origin,
                                "x": x, "y": y,
                                "scale_x": sx,
                                "scale_y": sy,
                                "opacity": opacity,
                                "blend_mode": blend,
                                "direct_flag": direct,
                                "parameter_layout": layout,
                                "move_command_index": idx,
                            })
                    except Exception:
                        continue
                elif code == 235 and params:  # Erase Picture
                    try:
                        slots.pop(int(params[0]), None)
                    except Exception:
                        pass
            pictures = [slots[k] for k in sorted(slots.keys())]
            diag.update({"enabled": True, "reason": "ok", "map_file": map_file, "event_id": event_id, "page_index": page_index, "command_index": command_index, "pictures": pictures})
            return pictures, diag
        except Exception as e:
            diag.update({"reason": "error", "error": str(e), "error_type": type(e).__name__})
            return [], diag

    def _maker_preview_add_picture_layers(self, scene, pictures, *, z_base=99900, settings=None):
        items = []
        rendered = []
        settings = settings if isinstance(settings, dict) else {}
        # Translator-first default: show picture/standing layers fully opaque.
        # If the user enables the option, follow RPG Maker picture opacity.
        follow_picture_opacity = bool(settings.get("show_picture_opacity"))
        for pic in pictures or []:
            try:
                path = str((pic or {}).get("path") or "")
                if not path:
                    rendered.append({**dict(pic), "rendered": False, "error": "path_missing"})
                    continue
                pm = QPixmap(path)
                if pm.isNull():
                    rendered.append({**dict(pic), "rendered": False, "error": "pixmap_null"})
                    continue
                sx = float((pic or {}).get("scale_x") or 100) / 100.0
                sy = float((pic or {}).get("scale_y") or 100) / 100.0
                x = float((pic or {}).get("x") or 0)
                y = float((pic or {}).get("y") or 0)
                if int((pic or {}).get("origin") or 0) == 1:
                    x -= (pm.width() * sx) / 2.0
                    y -= (pm.height() * sy) / 2.0
                item = QGraphicsPixmapItem(pm)
                item.setPos(x, y)
                tr = QTransform()
                tr.scale(sx, sy)
                item.setTransform(tr, False)
                try:
                    if follow_picture_opacity:
                        item.setOpacity(max(0.0, min(1.0, float((pic or {}).get("opacity") or 255) / 255.0)))
                    else:
                        item.setOpacity(1.0)
                except Exception:
                    pass
                item.setZValue(float(z_base + int((pic or {}).get("id") or 0)))
                scene.addItem(item)
                items.append(item)
                rendered.append({**dict(pic), "rendered": True, "pixmap_width": pm.width(), "pixmap_height": pm.height(), "draw_x": x, "draw_y": y, "preview_follow_opacity": follow_picture_opacity})
            except Exception as e:
                try:
                    rendered.append({**dict(pic), "rendered": False, "error": str(e), "error_type": type(e).__name__})
                except Exception:
                    pass
        return items, rendered

    def _maker_preview_text_color_index(self, color_index, *, profile=None, fallback="#ffffff"):
        r"""Sample RPG Maker Window.png text color for \C[n]."""
        try:
            idx = int(color_index or 0)
            cache = getattr(self, "_maker_preview_window_text_color_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                self._maker_preview_window_text_color_cache = cache
            path, _diag = self._maker_preview_window_skin_path(profile=profile) if hasattr(self, "_maker_preview_window_skin_path") else (None, {})
            key = (str(path or ""), idx)
            if key in cache:
                return cache[key]
            if path:
                pm = QPixmap(str(path))
                if not pm.isNull() and pm.width() >= 192 and pm.height() >= 180:
                    x = 96 + (idx % 8) * 12 + 6
                    y = 144 + (idx // 8) * 12 + 6
                    if 0 <= x < pm.width() and 0 <= y < pm.height():
                        c = pm.toImage().pixelColor(int(x), int(y))
                        if c.isValid():
                            cache[key] = c.name(QColor.NameFormat.HexRgb)
                            return cache[key]
        except Exception:
            pass
        return str(fallback or "#ffffff")

    def _maker_preview_control_code_arg(self, code):
        try:
            import re
            m = re.match(r"(?:\\|¥)([A-Za-z가-힣_]+)(?:\[([^\]]*)\])?", str(code or ""))
            if not m:
                return "", ""
            return str(m.group(1) or "").upper(), str(m.group(2) or "")
        except Exception:
            return "", ""

    def _maker_preview_font_for_state(self, settings, *, base_font=None, size=None, bold=False, italic=False, text_type="text"):
        try:
            font = QFont(base_font) if base_font is not None else self._maker_preview_font(settings, text_type=text_type, bold=bold, size_override=size)
        except Exception:
            font = self._maker_preview_font(settings, text_type=text_type, bold=bold, size_override=size)
        try:
            if size is not None:
                font.setPixelSize(max(6, min(160, int(float(size)))))
        except Exception:
            pass
        try:
            font.setBold(bool(bold))
        except Exception:
            pass
        try:
            font.setItalic(bool(italic))
        except Exception:
            pass
        return font

    def _maker_add_control_text_items(self, scene, text, x, y, *, settings, base_font, width, max_lines=4, line_height=36, z=100000, profile=None, height_scale=1.0):
        r"""Render MV/MZ message text while applying common control codes.

        This is a static preview renderer.  It intentionally ignores animation-only
        codes such as \AT[n], but applies visible layout/style codes such as \C[n],
        \FS[n], \MX[n], \MY[n], \PX[n], \PY[n], \FB, \FI, \OC, and \OW.
        """
        items = []
        raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        st = settings if isinstance(settings, dict) else {}
        try:
            base_size = int(base_font.pixelSize() if base_font is not None and base_font.pixelSize() > 0 else st.get("font_size") or 28)
        except Exception:
            base_size = int(st.get("font_size") or 28)
        try:
            base_line_h = max(12, int(line_height or st.get("line_height") or 36))
        except Exception:
            base_line_h = 36
        try:
            # RPG Maker MV/MZ advances a text line by maxFontSize + runtime extra.
            # MV's default 28px font / 36px line height gives +8.  Derive this
            # from the loaded game settings instead of applying editor-side spacing.
            runtime_line_extra = int(base_line_h) - int(base_size)
        except Exception:
            runtime_line_extra = 8
        if runtime_line_extra <= 0:
            runtime_line_extra = 8
        max_lines = max(1, int(max_lines or 4))
        cur_size = base_size
        cur_bold = False
        cur_italic = False
        cur_color = self._maker_preview_color(st.get("text_color"), "#FFFFFF")
        cur_outline = self._maker_preview_color(st.get("outline_color"), "#202020")
        cur_outline_w = self._maker_preview_effective_outline_width(st, st.get("outline_width") or 0)
        cx = float(x)
        cy = float(y)
        line_no = 0
        overflow = False
        width_overflow = False
        line_clipped = False
        run = ""
        run_x = cx
        run_y = cy
        run_font = self._maker_preview_font_for_state(st, base_font=base_font, size=cur_size, bold=cur_bold, italic=cur_italic)
        run_color = QColor(cur_color)
        run_outline = QColor(cur_outline)
        run_outline_w = cur_outline_w
        plain_parts = []

        def calc_runtime_line_height(start_pos, current_font_size):
            """Approximate RPG Maker calcTextHeight for the current raw line.

            MV computes the next y step from the current line's maximum font size.
            MPP_MessageEX adds \\FS[n] support, so a line ending in \\FS[22] can
            make following body lines use 22 + 8px instead of a fixed 36px.
            """
            try:
                temp_size = max(6, min(160, int(float(current_font_size or base_size))))
            except Exception:
                temp_size = int(base_size or 28)
            max_font_size = temp_size
            try:
                end_pos = raw.find("\n", int(start_pos))
                if end_pos < 0:
                    segment = raw[int(start_pos):]
                else:
                    segment = raw[int(start_pos):end_pos]
            except Exception:
                segment = ""
            try:
                for cm in _MAKER_CONTROL_CODE_RE.finditer(segment):
                    token = str(cm.group(0) or "")
                    cmd2, arg2 = self._maker_preview_control_code_arg(token)
                    if cmd2 == "FS":
                        try:
                            temp_size = max(6, min(160, int(float(arg2))))
                        except Exception:
                            pass
                    elif token in {"\\{", "¥{"}:
                        temp_size = min(160, temp_size + 12)
                    elif token in {"\\}", "¥}"}:
                        temp_size = max(6, temp_size - 12)
                    if temp_size > max_font_size:
                        max_font_size = temp_size
            except Exception:
                pass
            try:
                return max(12, int(round(float(max_font_size) + float(runtime_line_extra))))
            except Exception:
                return max(12, int(base_line_h or 36))

        current_line_h = calc_runtime_line_height(0, cur_size)

        def flush():
            nonlocal run, run_x, run_y, run_font, run_color, run_outline, run_outline_w, items
            if not run:
                return
            try:
                made = self._maker_add_outlined_text_items(
                    scene,
                    run,
                    run_x,
                    run_y,
                    font=run_font,
                    text_color=run_color,
                    outline_color=run_outline,
                    outline_width=run_outline_w,
                    width=None,
                    z=z,
                    height_scale=height_scale,
                )
                items.extend(made)
            except Exception:
                pass
            run = ""

        def reset_run_style():
            nonlocal run_x, run_y, run_font, run_color, run_outline, run_outline_w
            run_x = cx
            run_y = cy
            run_font = self._maker_preview_font_for_state(st, base_font=base_font, size=cur_size, bold=cur_bold, italic=cur_italic)
            run_color = QColor(cur_color)
            run_outline = QColor(cur_outline)
            run_outline_w = cur_outline_w

        pos = 0
        matches = list(_MAKER_CONTROL_CODE_RE.finditer(raw))
        mi = 0
        try:
            right = float(x) + max(40.0, float(width or 0))
        except Exception:
            right = float(x) + 720.0
        while pos < len(raw):
            if line_no >= max_lines:
                overflow = True
            m = matches[mi] if mi < len(matches) else None
            if m is not None and m.start() == pos:
                flush()
                cmd, arg = self._maker_preview_control_code_arg(m.group(0))
                if cmd == "C":
                    try:
                        cur_color = self._maker_preview_color(self._maker_preview_text_color_index(int(arg or 0), profile=profile), "#FFFFFF")
                    except Exception:
                        cur_color = self._maker_preview_color(st.get("text_color"), "#FFFFFF")
                elif cmd == "FS":
                    try:
                        cur_size = max(6, min(160, int(float(arg))))
                    except Exception:
                        pass
                elif cmd == "MX":
                    try:
                        cx += float(arg or 0)
                    except Exception:
                        pass
                elif cmd == "MY":
                    try:
                        cy += float(arg or 0)
                    except Exception:
                        pass
                elif cmd == "PX":
                    try:
                        cx = float(x) + float(arg or 0)
                    except Exception:
                        pass
                elif cmd == "PY":
                    try:
                        cy = float(y) + float(arg or 0)
                    except Exception:
                        pass
                elif cmd == "FB":
                    cur_bold = False if str(arg).strip() in {"0", "false", "False"} else (not cur_bold if arg == "" else True)
                elif cmd == "FI":
                    cur_italic = False if str(arg).strip() in {"0", "false", "False"} else (not cur_italic if arg == "" else True)
                elif cmd == "OC":
                    a = str(arg or "").strip()
                    if "," in a:
                        try:
                            parts = [int(float(x.strip())) for x in a.split(",")[:3]]
                            cur_outline = QColor(parts[0], parts[1], parts[2])
                        except Exception:
                            pass
                    elif a:
                        cur_outline = self._maker_preview_color(a if a.startswith("#") else ("#" + a), st.get("outline_color", "#202020"))
                elif cmd == "OW":
                    try:
                        cur_outline_w = self._maker_preview_effective_outline_width(st, int(float(arg or 0)))
                    except Exception:
                        pass
                elif str(m.group(0)) in {"\\{", "¥{"}:
                    cur_size = min(160, cur_size + 12)
                elif str(m.group(0)) in {"\\}", "¥}"}:
                    cur_size = max(6, cur_size - 12)
                # \AT[n] and other effect/input codes are animation/runtime only in
                # this static preview, so they are deliberately ignored.
                reset_run_style()
                pos = m.end()
                mi += 1
                continue
            if m is not None and m.start() < pos:
                mi += 1
                continue
            ch = raw[pos]
            if ch == "\n":
                flush()
                plain_parts.append("\n")
                cx = float(x)
                cy += current_line_h
                line_no += 1
                line_clipped = False
                pos += 1
                current_line_h = calc_runtime_line_height(pos, cur_size)
                reset_run_style()
                continue
            font = self._maker_preview_font_for_state(st, base_font=base_font, size=cur_size, bold=cur_bold, italic=cur_italic)
            try:
                fm = QFontMetrics(font)
                cw = max(1, int(fm.horizontalAdvance(ch)))
            except Exception:
                cw = max(1, int(cur_size * (1.0 if ord(ch) > 255 else 0.6)))
            plain_parts.append(ch)
            if line_clipped:
                # Do not auto-wrap preview text, but also do not draw outside the
                # message window.  The hidden tail remains in diagnostics/table so
                # the user can add real line breaks and verify the result.
                overflow = True
                width_overflow = True
                pos += 1
                continue
            if cx > float(x) and cx + cw > right:
                overflow = True
                width_overflow = True
                line_clipped = True
                flush()
                pos += 1
                continue
            if not run:
                run_x = cx
                run_y = cy
                run_font = font
                run_color = QColor(cur_color)
                run_outline = QColor(cur_outline)
                run_outline_w = cur_outline_w
            run += ch
            cx += cw
            pos += 1
        flush()
        # Count actual used lines from plain text and auto-wrap overflow.
        plain = "".join(plain_parts)
        line_count = max(1, line_no + 1)
        if pos < len(raw):
            overflow = True
        return items, {
            "raw_text": raw,
            "plain_text": plain,
            "line_count": int(line_count),
            "max_lines": int(max_lines),
            "overflow": bool(overflow),
            "width_overflow": bool(width_overflow),
            "runtime_line_extra": int(runtime_line_extra),
            "base_line_height": int(base_line_h),
            "last_line_height": int(current_line_h),
        }

    def _maker_add_text_item(self, scene, text, x, y, *, font=None, color=None, width=None, z=100000, height_scale=1.0):
        item = QGraphicsTextItem(str(text or ""))
        try:
            # QTextDocument has a default margin (usually 4px). RPG Maker text
            # drawing starts at the calculated contents rect directly, so remove
            # the Qt document margin for Maker scene preview items.
            item.document().setDocumentMargin(0)
        except Exception:
            pass
        if font is not None:
            item.setFont(font)
        if color is not None:
            item.setDefaultTextColor(color)
        if width is not None:
            try:
                item.setTextWidth(float(width))
            except Exception:
                pass
        item.setPos(float(x), float(y))
        item.setZValue(float(z))
        try:
            if abs(float(height_scale) - 1.0) > 0.001:
                tr = QTransform()
                tr.scale(1.0, float(height_scale))
                item.setTransform(tr, False)
        except Exception:
            pass
        try:
            item.setData(0, "maker_preview_overlay")
        except Exception:
            pass
        scene.addItem(item)
        return item

    def _maker_add_vector_text_item(self, scene, text, x, y, *, font=None, text_color=None, outline_color=None, outline_width=0, z=100000, height_scale=1.0):
        """Add Maker preview text as vector path items without darkening the fill.

        A single QGraphicsPathItem with a thick pen and a fill brush draws the
        outline stroke over the fill.  With Japanese glyphs and MV-sized text that
        can cover most of the white fill, making the text look almost black.  Use
        two path items instead: an outline item behind, and a clean fill item on
        top.  This keeps the anti-ghosting vector renderer while preserving the
        actual RPG Maker text color.
        """
        raw = str(text or "")
        if not raw:
            return None
        try:
            f = QFont(font) if font is not None else QFont()
            fm = QFontMetricsF(f)
            path = QPainterPath()
            # QPainterPath.addText uses a baseline position.  QGraphicsTextItem
            # callers pass a top-left y, so add the font ascent.
            path.addText(0.0, float(fm.ascent()), f, raw)
            try:
                ow = max(0.0, min(8.0, float(outline_width or 0)))
            except Exception:
                ow = 0.0
            made = []
            tx = QColor(text_color) if text_color is not None else QColor(255, 255, 255)
            ox = QColor(outline_color) if outline_color is not None else QColor(32, 32, 32)

            transform = None
            try:
                if abs(float(height_scale) - 1.0) > 0.001:
                    transform = QTransform()
                    transform.scale(1.0, float(height_scale))
            except Exception:
                transform = None

            if ow > 0 and outline_color is not None:
                outline_item = QGraphicsPathItem(path)
                pen = QPen(ox, ow * 2.0)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                outline_item.setPen(pen)
                # Fill the outline item with the outline color too, then draw the
                # true fill item above it. This prevents transparent counters/joins
                # from showing through while the top item restores the text color.
                outline_item.setBrush(QBrush(ox))
                outline_item.setPos(float(x), float(y))
                outline_item.setZValue(float(z))
                try:
                    outline_item.setData(0, "maker_preview_overlay")
                except Exception:
                    pass
                if transform is not None:
                    try:
                        outline_item.setTransform(transform, False)
                    except Exception:
                        pass
                scene.addItem(outline_item)
                made.append(outline_item)

            fill_item = QGraphicsPathItem(path)
            fill_item.setPen(QPen(Qt.PenStyle.NoPen))
            fill_item.setBrush(QBrush(tx))
            fill_item.setPos(float(x), float(y))
            fill_item.setZValue(float(z) + 0.5)
            try:
                fill_item.setData(0, "maker_preview_overlay")
            except Exception:
                pass
            if transform is not None:
                try:
                    fill_item.setTransform(transform, False)
                except Exception:
                    pass
            scene.addItem(fill_item)
            made.append(fill_item)
            return made
        except Exception:
            return None

    def _maker_preview_effective_outline_width(self, settings, raw_width):
        """Return the RPG Maker runtime outline width as-is for scene preview.

        쯔꾸르붕이의 게임 화면 프리뷰는 보정용 축소/확대값을 끼우지 않는다.
        MV/MZ 런타임에서 읽은 outlineWidth 값을 그대로 사용해야 행간/글자 크기처럼
        실제 게임 재현 기준이 흔들리지 않는다.
        """
        try:
            raw = float(raw_width or 0)
        except Exception:
            raw = 0.0
        if raw <= 0:
            return 0
        return max(0, min(20, int(round(raw))))

    def _maker_add_outlined_text_items(self, scene, text, x, y, *, font, text_color, outline_color, outline_width=0, width=None, z=100000, height_scale=1.0):
        made = []
        # For Maker scene previews, prefer a single stroked vector text item.
        # It removes the visible ghost/afterimage caused by stacked offset text
        # items while preserving the RPG Maker-style dark outline.
        try:
            if width is None:
                vector = self._maker_add_vector_text_item(
                    scene,
                    text,
                    x,
                    y,
                    font=font,
                    text_color=text_color,
                    outline_color=outline_color,
                    outline_width=outline_width,
                    z=z,
                    height_scale=height_scale,
                )
                if vector is not None:
                    if isinstance(vector, (list, tuple)):
                        return [v for v in vector if v is not None]
                    return [vector]
        except Exception:
            pass
        try:
            ow = max(0, min(3, int(round(float(outline_width or 0)))))
        except Exception:
            ow = 0
        if ow > 0:
            # Fallback only: use a restrained 4-direction outline so it does not
            # look like stacked old text.
            offsets = [(-ow, 0), (ow, 0), (0, -ow), (0, ow)]
            for dx, dy in offsets:
                item = self._maker_add_text_item(scene, text, x + dx, y + dy, font=font, color=outline_color, width=width, z=z, height_scale=height_scale)
                try:
                    item.setData(0, "maker_preview_overlay")
                except Exception:
                    pass
                made.append(item)
        item = self._maker_add_text_item(scene, text, x, y, font=font, color=text_color, width=width, z=z + 1, height_scale=height_scale)
        try:
            item.setData(0, "maker_preview_overlay")
        except Exception:
            pass
        made.append(item)
        return made

    def _maker_preview_text_type_is_choice(self, text_type):
        t = str(text_type or "").strip()
        return t.startswith("choice[") or t.startswith("common_choice[")

    def _maker_preview_choice_index_from_text_type(self, text_type):
        try:
            import re
            m = re.search(r"choice\[(\d+)\]", str(text_type or ""))
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 0

    def _maker_preview_display_text_for_row(self, row):
        translated = str((row or {}).get("translated_text") or "")
        original = str((row or {}).get("text") or "")
        raw = translated if translated.strip() else original
        try:
            raw = strip_maker_control_codes(raw)
        except Exception:
            pass
        return str(raw or "")

    def _maker_preview_choice_group_for_row(self, row, page=None):
        """Collect all choices belonging to the same Show Choices command.

        A selected choice is not a normal dialogue line.  It belongs to a single
        RPG Maker 102 command and must be previewed as a choice window while its
        102/402 write-back stays tied to each choice row.
        """
        try:
            meta = (row or {}).get("maker_text_unit") or {}
            text_type = str(meta.get("text_type") or "")
            if not self._maker_preview_text_type_is_choice(text_type):
                return {"enabled": False, "reason": "not_choice", "choices": [], "selected_index": 0}
            page = page if isinstance(page, dict) else (self.data.get(self.idx) if isinstance(getattr(self, "data", None), dict) else None)
            rows = list((page or {}).get("data") or [])
            key_fields = ("source_file", "map_file", "event_id", "page_index", "command_index", "source_kind")
            key = tuple(str(meta.get(k) or "") for k in key_fields)
            selected_index = self._maker_preview_choice_index_from_text_type(text_type)
            choices = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                m = r.get("maker_text_unit") or {}
                tt = str(m.get("text_type") or "")
                if not self._maker_preview_text_type_is_choice(tt):
                    continue
                rkey = tuple(str(m.get(k) or "") for k in key_fields)
                if rkey != key:
                    continue
                idx = self._maker_preview_choice_index_from_text_type(tt)
                choices.append({
                    "index": idx,
                    "row_id": r.get("id"),
                    "text": self._maker_preview_display_text_for_row(r),
                    "translated": str(r.get("translated_text") or ""),
                    "original": str(r.get("text") or ""),
                })
            choices.sort(key=lambda x: int(x.get("index") or 0))
            return {"enabled": bool(choices), "reason": "ok" if choices else "empty", "choices": choices, "selected_index": selected_index, "key": key}
        except Exception as e:
            return {"enabled": False, "reason": "error", "error": str(e), "error_type": type(e).__name__, "choices": [], "selected_index": 0}

    def _maker_preview_previous_message_for_choice(self, row, page=None):
        """Return the nearest previous message/narration row for a choice.

        RPG Maker usually displays choices after a message.  When the user
        selects a choice row, keep that previous message in the message window
        and render the choices as a separate choice box.
        """
        try:
            meta = (row or {}).get("maker_text_unit") or {}
            if not self._maker_preview_text_type_is_choice(meta.get("text_type")):
                return None
            page = page if isinstance(page, dict) else (self.data.get(self.idx) if isinstance(getattr(self, "data", None), dict) else None)
            rows = list((page or {}).get("data") or [])
            try:
                command_index = int(meta.get("command_index") or 0)
            except Exception:
                command_index = 0
            same = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                m = r.get("maker_text_unit") or {}
                if self._maker_preview_text_type_is_choice(m.get("text_type")):
                    continue
                try:
                    ci = int(m.get("command_index") or -1)
                except Exception:
                    ci = -1
                if ci < 0 or ci >= command_index:
                    continue
                if str(m.get("source_file") or m.get("map_file") or "") != str(meta.get("source_file") or meta.get("map_file") or ""):
                    continue
                if str(m.get("event_id") or "") != str(meta.get("event_id") or ""):
                    continue
                if str(m.get("page_index") or "") != str(meta.get("page_index") or ""):
                    continue
                if str(m.get("source_kind") or "") != str(meta.get("source_kind") or ""):
                    continue
                tt = str(m.get("text_type") or "")
                if tt.startswith("database:"):
                    continue
                same.append((ci, r))
            if not same:
                return None
            same.sort(key=lambda x: x[0], reverse=True)
            return same[0][1]
        except Exception:
            return None

    def _maker_preview_add_choice_window(self, scene, choice_group, *, settings, canvas_w, canvas_h, message_box=None, profile=None):
        """Draw an RPG Maker style Show Choices box.

        The selected choice row is highlighted with a cursor marker, but every
        sibling choice from the same 102 command is displayed together so the
        translator can judge the actual UI block instead of a single loose line.
        """
        overlay = []
        diag = {"enabled": False, "reason": "not_rendered", "choice_count": 0}
        try:
            choices = list((choice_group or {}).get("choices") or [])
            if not choices:
                diag["reason"] = "empty"
                return overlay, diag
            selected_index = int((choice_group or {}).get("selected_index") or 0)
            st = settings if isinstance(settings, dict) else {}
            try:
                padding = max(8, int(st.get("choice_padding") or st.get("message_padding") or 18))
            except Exception:
                padding = 18
            font = self._maker_preview_font(st, text_type="choice", bold=False, size_override=st.get("choice_font_size") or st.get("font_size") or 26)
            try:
                fm = QFontMetrics(font)
                base_line_h = max(12, int(fm.lineSpacing()))
            except Exception:
                fm = None
                base_line_h = max(12, int(st.get("choice_font_size") or st.get("font_size") or 26) + 8)
            height_scale = 1.0
            try:
                runtime_line_h = int(st.get("line_height") or 0)
            except Exception:
                runtime_line_h = 0
            line_h = max(16, int(runtime_line_h or base_line_h))
            display = []
            max_w = 0
            for ch in choices:
                idx = int(ch.get("index") or 0)
                txt = str(ch.get("text") or "").replace("\r\n", " ").replace("\r", " ").replace("\n", " ").strip()
                prefix = "▶ " if idx == selected_index else "  "
                label = prefix + (txt if txt else " ")
                display.append({**dict(ch), "label": label})
                try:
                    max_w = max(max_w, int(fm.horizontalAdvance(label)) if fm is not None else len(label) * 18)
                except Exception:
                    max_w = max(max_w, len(label) * 18)
            choice_w = max(180, min(int(canvas_w * 0.70), max_w + padding * 2))
            choice_h = max(56, padding * 2 + line_h * len(display))
            if message_box:
                try:
                    _mx, box_y, _mw, _mh = message_box
                    choice_y = max(18, int(box_y - choice_h - 14))
                except Exception:
                    choice_y = max(18, int(canvas_h * 0.50 - choice_h / 2))
            else:
                choice_y = max(18, int(canvas_h * 0.50 - choice_h / 2))
            # RPG Maker choices are commonly right-aligned.  Use a stable
            # right-side default so message text and choice text do not overlap.
            choice_x = max(18, int(canvas_w - choice_w - 24))
            try:
                win_opacity = max(0, min(255, int(st.get("window_opacity") or 205)))
            except Exception:
                win_opacity = 205
            box, skin_diag = self._maker_preview_add_window_item(
                scene,
                choice_x,
                choice_y,
                choice_w,
                choice_h,
                z=100010,
                opacity=win_opacity,
                profile=profile,
                fallback_pen=QPen(QColor(150, 185, 255, 230), 3),
                fallback_brush=QBrush(QColor(8, 10, 12, win_opacity)),
            )
            overlay.append(box)
            text_color = self._maker_preview_color(st.get("text_color"), "#FFFFFF")
            outline_color = self._maker_preview_color(st.get("outline_color"), "#202020")
            outline_width = self._maker_preview_effective_outline_width(st, st.get("outline_width") or 0)
            for n, ch in enumerate(display):
                y = choice_y + padding + n * line_h
                try:
                    if int(ch.get("index") or 0) == selected_index:
                        hi = QGraphicsRectItem(QRectF(choice_x + 8, y - 2, max(20, choice_w - 16), max(14, line_h)))
                        hi.setPen(QPen(QColor(255, 255, 255, 40), 1))
                        hi.setBrush(QBrush(QColor(255, 255, 255, 36)))
                        hi.setZValue(100011)
                        scene.addItem(hi)
                        overlay.append(hi)
                except Exception:
                    pass
                items = self._maker_add_outlined_text_items(
                    scene,
                    str(ch.get("label") or ""),
                    choice_x + padding,
                    y,
                    font=font,
                    text_color=text_color,
                    outline_color=outline_color,
                    outline_width=outline_width,
                    width=max(40, choice_w - padding * 2),
                    z=100012,
                    height_scale=height_scale,
                )
                overlay.extend(items)
            diag = {
                "enabled": True,
                "reason": "ok",
                "choice_count": len(display),
                "selected_index": selected_index,
                "x": choice_x,
                "y": choice_y,
                "width": choice_w,
                "height": choice_h,
                "skin": skin_diag,
                "choices": [{"index": int(c.get("index") or 0), "text": str(c.get("text") or "")} for c in choices],
            }
            return overlay, diag
        except Exception as e:
            diag.update({"reason": "error", "error": str(e), "error_type": type(e).__name__})
            return overlay, diag

    def _maker_preview_message_body_for_row(self, row):
        meta = row.get("maker_text_unit") if isinstance(row, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        translated = str((row or {}).get("translated_text") or "")
        original = str((row or {}).get("text") or "")
        body = translated if translated.strip() else original
        source_label = self.tr_ui("번역문") if translated.strip() else self.tr_ui("원문")
        if bool(meta.get("inline_speaker")):
            # The table speaker is plain, but the preview must reconstruct the
            # original inline-name code shell for this selected row only.
            try:
                body = compose_maker_inline_speaker_writeback(row or {}, body)
            except Exception:
                speaker = str((row or {}).get("maker_speaker") or meta.get("speaker_plain") or "").strip()
                prefix = str(meta.get("body_prefix_codes") or "")
                if prefix and body.strip() and not body.lstrip().startswith(prefix):
                    body = prefix + body
                if speaker:
                    body = speaker + "\n" + body
        return body, source_label

    def _maker_preview_payload_for_row(self, row, page=None):
        """Return a normalized preview payload for a Maker text row.

        Older projects and newly imported projects may not carry the same
        metadata keys.  The preview renderer should not depend on the table cell
        text itself; it should use a stable payload synthesized from
        maker_text_unit, row fields, and page metadata.  If the original command
        anchor is partially missing, keep whatever is available and let the
        message-window fallback still render the selected text.
        """
        row = row if isinstance(row, dict) else {}
        meta = row.get("maker_text_unit") if isinstance(row.get("maker_text_unit"), dict) else {}
        payload = meta.get("preview_payload") if isinstance(meta.get("preview_payload"), dict) else {}
        payload = dict(payload or {})
        page_meta = (page or {}).get("maker_page") if isinstance(page, dict) else {}
        if not isinstance(page_meta, dict):
            page_meta = {}

        def first_non_empty(*values, default=""):
            for value in values:
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    return value
            return default

        translated = str(row.get("translated_text") or "")
        body_raw = first_non_empty(
            payload.get("body_raw_with_codes"),
            meta.get("body_raw_with_codes"),
            row.get("text"),
            default="",
        )
        body_for_preview = translated if translated.strip() else str(body_raw or "")
        if bool(meta.get("inline_speaker") or payload.get("inline_speaker")):
            try:
                body_for_preview = compose_maker_inline_speaker_writeback(row, body_for_preview)
            except Exception:
                prefix = str(meta.get("body_prefix_codes") or payload.get("body_prefix_codes") or "")
                speaker = str(row.get("maker_speaker") or row.get("maker_speaker_plain") or meta.get("speaker_plain") or payload.get("speaker_plain") or "").strip()
                if prefix and body_for_preview.strip() and not body_for_preview.lstrip().startswith(prefix):
                    body_for_preview = prefix + body_for_preview
                if speaker:
                    body_for_preview = speaker + "\n" + body_for_preview

        def as_int(value, fallback=None):
            try:
                if value is None or value == "":
                    return fallback
                return int(value)
            except Exception:
                return fallback

        payload.update({
            "map_id": as_int(first_non_empty(payload.get("map_id"), meta.get("map_id"), page_meta.get("map_id"), default=""), None),
            "map_file": str(first_non_empty(payload.get("map_file"), meta.get("map_file"), page_meta.get("map_file"), default="") or ""),
            "map_name": str(first_non_empty(payload.get("map_name"), meta.get("map_name"), page_meta.get("map_name"), page_meta.get("display_name"), default="") or ""),
            "event_id": as_int(first_non_empty(payload.get("event_id"), meta.get("event_id"), default=""), None),
            "event_name": str(first_non_empty(payload.get("event_name"), meta.get("event_name"), default="") or ""),
            "event_x": as_int(first_non_empty(payload.get("event_x"), meta.get("event_x"), default=""), None),
            "event_y": as_int(first_non_empty(payload.get("event_y"), meta.get("event_y"), default=""), None),
            "page_index": as_int(first_non_empty(payload.get("page_index"), meta.get("page_index"), default=""), None),
            "command_index": as_int(first_non_empty(payload.get("command_index"), meta.get("command_index"), default=""), None),
            "command_code": as_int(first_non_empty(payload.get("command_code"), meta.get("code"), default=""), None),
            "text_type": str(first_non_empty(payload.get("text_type"), meta.get("text_type"), row.get("type"), default="dialogue") or "dialogue"),
            "source_kind": str(first_non_empty(payload.get("source_kind"), meta.get("source_kind"), default="map") or "map"),
            "source_file": str(first_non_empty(payload.get("source_file"), meta.get("source_file"), meta.get("map_file"), default="") or ""),
            "speaker_plain": str(first_non_empty(payload.get("speaker_plain"), meta.get("speaker_plain"), row.get("maker_speaker_plain"), strip_maker_control_codes(row.get("maker_speaker") or ""), default="") or ""),
            "speaker_raw_with_codes": str(first_non_empty(payload.get("speaker_raw_with_codes"), meta.get("speaker_raw_visible"), default="") or ""),
            "body_raw_with_codes": str(body_raw or ""),
            "body_for_preview": str(body_for_preview or ""),
            "body_plain": strip_maker_control_codes(body_raw or ""),
            "inline_speaker": bool(payload.get("inline_speaker") or meta.get("inline_speaker")),
            "body_prefix_codes": str(first_non_empty(payload.get("body_prefix_codes"), meta.get("body_prefix_codes"), default="") or ""),
            "body_line_reserved": bool(payload.get("body_line_reserved") or meta.get("body_line_reserved")),
        })
        return payload

    def _maker_preview_add_minimal_message_fallback(self, scene, row, page, settings, *, canvas_w=816, canvas_h=624, profile=None, reason="fallback"):
        """Draw at least the selected message when full scene reconstruction fails.

        This prevents a row click from appearing as if the dialogue is
        "unsupported".  Standing-picture reconstruction may fail for plugin
        commands, but the selected text must still be visible for checking.
        """
        overlay = []
        diag = {"enabled": False, "reason": reason}
        if scene is None:
            diag["reason"] = "scene_missing"
            return overlay, diag
        try:
            st = settings if isinstance(settings, dict) else {}
            payload = self._maker_preview_payload_for_row(row, page)
            body = str(payload.get("body_for_preview") or payload.get("body_raw_with_codes") or (row or {}).get("text") or "")
            if not body.strip():
                body = str((row or {}).get("translated_text") or "")
            if not body.strip():
                diag["reason"] = "empty_body"
                return overlay, diag
            try:
                margin = max(0, int(st.get("message_margin") or 0))
            except Exception:
                margin = 0
            try:
                message_w = int(st.get("message_width") or (canvas_w - margin * 2))
            except Exception:
                message_w = int(canvas_w - margin * 2)
            message_w = max(120, min(int(canvas_w), int(message_w)))
            try:
                padding = max(0, int(st.get("message_padding") or 18))
            except Exception:
                padding = 18
            try:
                max_lines = max(1, min(12, int(st.get("message_lines") or 4)))
            except Exception:
                max_lines = 4
            try:
                font = self._maker_preview_font(st, text_type=str(payload.get("text_type") or "dialogue"), bold=False)
            except Exception:
                font = QFont("Arial", int(st.get("font_size") or 28))
            try:
                fm = QFontMetrics(font)
                line_h = max(12, int(st.get("line_height") or fm.lineSpacing()))
            except Exception:
                line_h = max(12, int(st.get("line_height") or 36))
            warning_h = 0
            box_h = max(72, padding * 2 + line_h * max_lines + warning_h)
            box_h = min(max(72, box_h), max(72, int(canvas_h * 0.70)))
            box_x = max(0, int((canvas_w - message_w) / 2)) if int(st.get("message_x") or 0) < 0 else max(0, min(int(canvas_w - message_w), int(st.get("message_x") or 0)))
            try:
                raw_y = int(st.get("message_y") if st.get("message_y") is not None else -1)
            except Exception:
                raw_y = -1
            box_y = max(0, int(canvas_h - box_h - margin)) if raw_y < 0 else max(0, min(int(canvas_h - box_h), raw_y))
            try:
                win_opacity = max(0, min(255, int(st.get("window_opacity") or 205)))
            except Exception:
                win_opacity = 205
            box, skin_diag = self._maker_preview_add_window_item(
                scene, box_x, box_y, message_w, box_h,
                z=100000, opacity=win_opacity, profile=profile,
                fallback_pen=QPen(QColor(150, 185, 255, 230), 3),
                fallback_brush=QBrush(QColor(8, 10, 12, win_opacity)),
            )
            overlay.append(box)
            body_items, text_diag = self._maker_add_control_text_items(
                scene, body, box_x + padding, box_y + padding,
                settings=st, base_font=font, width=max(40, message_w - padding * 2),
                max_lines=max_lines, line_height=line_h, z=100004, profile=profile,
                height_scale=1.0,
            )
            overlay.extend(body_items)
            try:
                for it in overlay:
                    it.setData(0, "maker_preview_overlay")
            except Exception:
                pass
            diag.update({
                "enabled": True,
                "reason": reason,
                "payload": payload,
                "message_window": {"x": box_x, "y": box_y, "width": message_w, "height": box_h},
                "window_skin": skin_diag,
                "control_text": text_diag,
            })
            return overlay, diag
        except Exception as e:
            diag.update({"enabled": False, "reason": "error", "error": str(e), "error_type": type(e).__name__})
            return overlay, diag

    def _maker_wrap_text_with_font_metrics(self, text, font, max_width, max_lines=4):
        """Measure preview text without auto-wrapping.

        쯔꾸르붕이 프리뷰는 실제 JSON/번역문에 들어간 줄바꿈만 믿는다.
        자동 줄내림으로 보기 좋게 감추면 사용자가 넘침을 검수할 수 없으므로,
        긴 한 줄은 대사창을 넘어가더라도 그대로 직진 표시하고 overflow만 표시한다.
        """
        raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        try:
            fm = QFontMetrics(font)
        except Exception:
            fm = None
        width = max(40, int(max_width or 40))
        lines = raw.split("\n") if raw != "" else [""]
        try:
            max_lines = max(1, min(12, int(max_lines or 4)))
        except Exception:
            max_lines = 4
        width_overflow = False
        for line in lines:
            try:
                adv = fm.horizontalAdvance(str(line)) if fm is not None else len(str(line)) * 18
            except Exception:
                adv = len(str(line)) * 18
            if adv > width:
                width_overflow = True
                break
        overflow = bool(len(lines) > max_lines or width_overflow)
        return {
            "lines": lines,
            "visible_lines": lines[:max_lines],
            "visible_text": "\n".join(lines[:max_lines]),
            "line_count": len(lines),
            "max_lines": max_lines,
            "overflow": overflow,
            "overflow_count": max(0, len(lines) - max_lines),
            "width_overflow": bool(width_overflow),
        }

    def update_maker_preview_selection_from_table(self):
        """Render the selected RPG Maker text as a fixed game-screen preview.

        The left pane is not a direct-edit canvas here.  It is a generated RPG
        Maker scene preview: message wrapping is calculated in the game's screen
        coordinate system, then the viewer may scale the whole image.  The right
        table is the editor; the left pane is the result preview.
        """
        if not self._is_current_maker_page():
            self._clear_maker_preview_selection_overlay()
            return False
        scene = self._safe_graphics_scene() if hasattr(self, "_safe_graphics_scene") else getattr(getattr(self, "view", None), "scene", None)
        if scene is None:
            return False
        row = self._maker_current_selected_row_item()
        self._clear_maker_preview_selection_overlay()
        if not isinstance(row, dict):
            return False
        curr = self.data.get(self.idx) if isinstance(getattr(self, "data", None), dict) else None
        overlay = []
        profile = {}
        window_skin_diag = {}
        picture_state_diag = {}
        rendered_picture_diag = []
        choice_preview_diag = {}
        name_text_rect_diag = {}
        message_text_rect_diag = {}
        try:
            from ysb.tools.maker_project import (
                normalize_maker_preview_settings,
                load_maker_runtime_profile,
                build_maker_runtime_profile,
                maker_preview_settings_from_runtime_profile,
                detect_maker_engine,
            )
            meta = row.get("maker_text_unit") or {}
            if not isinstance(meta, dict):
                meta = {}
            preview_payload = self._maker_preview_payload_for_row(row, curr)
            try:
                project_dir_p = Path(str(getattr(self, "project_dir", "") or ""))
                profile = load_maker_runtime_profile(project_dir_p) if project_dir_p else {}
                msg_prof = profile.get("message_window") if isinstance(profile.get("message_window"), dict) else {}
                needs_rebuild = (not profile) or (str(profile.get("engine") or "").lower() == "mz" and "box_margin" not in msg_prof)
                game_dir = project_dir_p / "maker_game" if project_dir_p else None
                if needs_rebuild and game_dir is not None and game_dir.exists():
                    try:
                        profile = build_maker_runtime_profile(project_dir_p, game_dir, detect_maker_engine(game_dir))
                        self._append_maker_preview_diagnostic("runtime_profile_auto_rebuilt_for_preview", {"reason": "missing_box_margin_or_profile", "profile_engine": profile.get("engine")})
                    except Exception as _rebuild_e:
                        self._append_maker_preview_diagnostic("runtime_profile_auto_rebuild_failed", {"error": str(_rebuild_e), "error_type": type(_rebuild_e).__name__})
                raw_preview_settings = (curr or {}).get("maker_preview_settings") or {}
                if profile:
                    st = maker_preview_settings_from_runtime_profile(profile, raw_preview_settings)
                else:
                    st = normalize_maker_preview_settings(raw_preview_settings)
            except Exception:
                st = normalize_maker_preview_settings((curr or {}).get("maker_preview_settings") or {})
            try:
                canvas_w, canvas_h, _sx, _sy = self._maker_page_canvas_geometry(curr)
            except Exception:
                canvas_w, canvas_h = 816, 624

            # Stage-1 map preview: before drawing the message/choice UI overlay,
            # redraw the base placeholder around the selected event.
            # This only changes the generated preview PNG and never edits Maker JSON.
            page_type = str(((curr or {}).get("maker_page") or {}).get("page_type") or "map")
            if page_type in {"", "map"}:
                # Do not rebuild/replace the base map image on every row click.
                # MV tile maps can render correctly when the map tab is opened, but
                # regenerating a selected local placeholder here can wipe that base
                # and leave only standing pictures/message overlays.  Keep the map
                # layer stable; row changes update only event halo, pictures, and UI.
                try:
                    if not bool(st.get("show_tile_map_preview", True)) and bool(st.get("show_local_map_preview", True)):
                        self._refresh_maker_local_map_preview_background(row, page=curr, settings=st)
                except Exception:
                    pass

            # Keep a small event highlight for map pages only.  This is not a
            # camera operation: do not center/zoom the viewer when the row changes.
            pos = self._maker_event_scene_position_for_row(row, page=curr) if page_type in {"", "map"} else None
            if pos is not None:
                px, py = pos
                halo = QGraphicsEllipseItem(QRectF(px - 18, py - 18, 36, 36))
                halo.setPen(QPen(QColor(255, 210, 80), 3))
                halo.setBrush(QBrush(QColor(255, 210, 80, 44)))
                halo.setZValue(100000)
                scene.addItem(halo)
                overlay.append(halo)
                center = QGraphicsEllipseItem(QRectF(px - 5, py - 5, 10, 10))
                center.setPen(QPen(QColor(255, 255, 255), 2))
                center.setBrush(QBrush(QColor(255, 80, 80, 230)))
                center.setZValue(100001)
                scene.addItem(center)
                overlay.append(center)

            # MZ/MV Show Picture state at the selected command.  This turns the
            # left pane from a debug grid into a scene preview for VN-style Maker
            # games that layer standing illustrations via picture slots.
            try:
                pictures, picture_state_diag = self._maker_preview_collect_picture_state_for_row(row, page=curr)
                picture_items, rendered_picture_diag = self._maker_preview_add_picture_layers(scene, pictures, z_base=99000, settings=st)
                overlay.extend(picture_items)
            except Exception as _pic_e:
                picture_state_diag = {"enabled": False, "reason": "error", "error": str(_pic_e), "error_type": type(_pic_e).__name__}
                rendered_picture_diag = []

            # Fixed game-screen message window.  It intentionally ignores the
            # current QWidget/view width so right panel resizing never changes
            # preview line breaks.
            try:
                margin = max(0, int(st.get("message_margin") or 0))
            except Exception:
                margin = 0
            try:
                message_w = int(st.get("message_width") or (canvas_w - margin * 2))
            except Exception:
                message_w = canvas_w - margin * 2
            message_w = max(120, min(int(canvas_w), int(message_w)))
            try:
                raw_x = int(st.get("message_x") if st.get("message_x") is not None else 0)
            except Exception:
                raw_x = 0
            if raw_x < 0:
                box_x = int((canvas_w - message_w) / 2)
            else:
                box_x = max(0, min(int(canvas_w - message_w), raw_x))
            try:
                padding = max(0, int(st.get("message_padding") or 18))
            except Exception:
                padding = 18
            try:
                max_lines = max(1, min(12, int(st.get("message_lines") or 4)))
            except Exception:
                max_lines = 4
            # MV/MZ scene preview must follow the game runtime values only.
            # Do not apply YSB text-object correction values such as char_height
            # or line_spacing here; those are editor text-object controls, not
            # RPG Maker Window_Message metrics.
            height_scale = 1.0
            line_scale = 1.0

            text_type = str(preview_payload.get("text_type") or meta.get("text_type") or "text")
            choice_group = {"enabled": False, "reason": "not_choice", "choices": [], "selected_index": 0}
            if self._maker_preview_text_type_is_choice(text_type):
                choice_group = self._maker_preview_choice_group_for_row(row, curr)
                previous_message_row = self._maker_preview_previous_message_for_choice(row, curr)
                if isinstance(previous_message_row, dict):
                    body, source_label = self._maker_preview_message_body_for_row(previous_message_row)
                    source_label = self.tr_ui("선택지 이전 대사")
                else:
                    body, source_label = "", self.tr_ui("선택지")
            else:
                body = str(preview_payload.get("body_for_preview") or "")
                source_label = self.tr_ui("번역문") if str((row or {}).get("translated_text") or "").strip() else self.tr_ui("원문")
                if not body.strip():
                    body, source_label = self._maker_preview_message_body_for_row(row)
            try:
                # Overflow warnings are translation-review annotations.  Original
                # text can be shown as a fallback preview, but it should not ask the
                # user to insert line breaks into an untranslated row.
                has_translation_for_warning = bool(str((row or {}).get("translated_text") or "").strip())
                if self._maker_preview_text_type_is_choice(text_type) and isinstance(previous_message_row, dict):
                    has_translation_for_warning = bool(str(previous_message_row.get("translated_text") or "").strip())
            except Exception:
                has_translation_for_warning = bool(str((row or {}).get("translated_text") or "").strip())
            body_font = self._maker_preview_font(st, text_type=text_type, bold=False)
            body_font_load_diag_snapshot = dict(getattr(self, "_last_maker_preview_font_load_diag", {}) or {})
            try:
                fm = QFontMetrics(body_font)
            except Exception:
                fm = None
            try:
                configured_line_h = int(st.get("line_height") or 0)
            except Exception:
                configured_line_h = 0
            if configured_line_h > 0:
                base_line_h = configured_line_h
            else:
                try:
                    base_line_h = max(12, int(fm.lineSpacing())) if fm is not None else max(12, int(st.get("font_size") or 28) + 8)
                except Exception:
                    base_line_h = max(12, int(st.get("font_size") or 28) + 8)
            line_h = max(12, int(base_line_h))
            body_width = max(40, message_w - padding * 2)
            try:
                wrap_source = strip_maker_control_codes(body)
            except Exception:
                wrap_source = body
            wrapped = self._maker_wrap_text_with_font_metrics(wrap_source, body_font, body_width, max_lines=max_lines)
            # Keep the raw control-coded message for the scene renderer.  The
            # renderer applies \C/\FS/\MX etc.; API translation still receives
            # the plain text through prepare_maker_translation_payload().
            body_text = str(body or "")
            line_count = int(wrapped.get("line_count") or 1)
            # Keep the message window geometry identical to RPG Maker.  Width
            # overflow is a review diagnostic only and must not increase box_h.
            overflow = bool(line_count > max_lines)
            warning_h = 0
            try:
                configured_h = int(st.get("message_height") or 0)
            except Exception:
                configured_h = 0
            natural_h = int(padding * 2 + line_h * max_lines + warning_h)
            box_h = configured_h if configured_h > 0 else natural_h
            box_h = max(max(72, natural_h if configured_h <= 0 else 72), min(int(canvas_h * 0.70), box_h))
            try:
                raw_y = int(st.get("message_y") if st.get("message_y") is not None else -1)
            except Exception:
                raw_y = -1
            if raw_y < 0:
                box_y = max(0, int(canvas_h - box_h - margin))
            else:
                box_y = max(0, min(int(canvas_h - box_h), raw_y))

            # Message window body: closer to RPG Maker black translucent window,
            # without the old editor status header that distorted line placement.
            try:
                win_opacity = max(0, min(255, int(st.get("window_opacity") or 205)))
            except Exception:
                win_opacity = 205
            box, window_skin_diag = self._maker_preview_add_window_item(
                scene,
                box_x,
                box_y,
                message_w,
                box_h,
                z=100000,
                opacity=win_opacity,
                profile=profile,
                fallback_pen=QPen(QColor(150, 185, 255, 230), 3),
                fallback_brush=QBrush(QColor(8, 10, 12, win_opacity)),
            )
            overlay.append(box)

            # Name window.  Only render when we actually have a speaker; Unknown
            # narration should not create a broken name tag.
            if hasattr(self, "_maker_row_speaker_text"):
                speaker = str(self._maker_row_speaker_text(row) or "").strip()
            else:
                try:
                    speaker = strip_maker_control_codes((row or {}).get("maker_speaker_plain") or (row or {}).get("maker_speaker") or meta.get("speaker_plain") or meta.get("speaker") or "").strip()
                except Exception:
                    speaker = str((row or {}).get("maker_speaker_plain") or (row or {}).get("maker_speaker") or meta.get("speaker_plain") or meta.get("speaker") or "").strip()
            if bool(meta.get("inline_speaker")):
                # First-line speaker patterns are drawn inside the message body;
                # rendering a separate RPG Maker namebox would shift the preview.
                speaker = ""
            if speaker.lower() == "unknown":
                speaker = ""
            if speaker:
                name_font = self._maker_preview_font(st, text_type="name", bold=False, size_override=st.get("name_font_size") or 24)
                try:
                    nfm = QFontMetrics(name_font)
                    name_text_w = int(nfm.horizontalAdvance(speaker))
                    name_text_h = int(nfm.height())
                except Exception:
                    nfm = None
                    name_text_w = max(48, len(speaker) * 24)
                    name_text_h = int(st.get("name_font_size") or 28) + 10
                try:
                    maker_item_padding = max(0, int(st.get("item_padding") or 8))
                    maker_win_padding = max(0, int(st.get("message_padding") or 12))
                    name_pad_x = max(0, int(st.get("name_padding_x") or (maker_win_padding + maker_item_padding)))
                    name_pad_y = max(0, int(st.get("name_padding_y") or maker_win_padding))
                    name_min_w = max(32, int(st.get("name_min_width") or 96))
                    name_min_h = max(24, int(st.get("name_min_height") or (base_line_h + maker_win_padding * 2)))
                    name_overlap = int(st.get("name_overlap") or 0)
                except Exception:
                    name_pad_x, name_pad_y, name_min_w, name_min_h, name_overlap = 20, 12, 96, 60, 0
                name_h = max(name_min_h, name_text_h + name_pad_y * 2)
                name_w = min(max(name_min_w, name_text_w + name_pad_x * 2), max(name_min_w, int(message_w * 0.62)))
                name_x = box_x + 0
                name_y = max(0, box_y - name_h + name_overlap)
                name_box, name_window_skin_diag = self._maker_preview_add_window_item(
                    scene,
                    name_x,
                    name_y,
                    name_w,
                    name_h,
                    z=100001,
                    opacity=win_opacity,
                    profile=profile,
                    fallback_pen=QPen(QColor(150, 185, 255, 230), 3),
                    fallback_brush=QBrush(QColor(8, 10, 12, 218)),
                )
                overlay.append(name_box)
                try:
                    # Qt text items use top-left glyph bounds; MZ Window_NameBox
                    # draws inside the contents rect.  Use padding as the primary
                    # y-origin instead of visual centering so it tracks Window_Base.
                    name_text_x = name_x + name_pad_x
                    name_text_y = name_y + name_pad_y
                    name_text_rect_diag = {
                        "x": name_text_x,
                        "y": name_text_y,
                        "width": max(0, name_w - name_pad_x * 2),
                        "height": max(0, name_h - name_pad_y * 2),
                        "text_width": name_text_w,
                        "text_height": name_text_h,
                        "skin": name_window_skin_diag,
                        "font_weight": int(name_font.weight()),
                        "bold": bool(name_font.bold()),
                        "outline_effective_width": self._maker_preview_effective_outline_width(st, st.get("outline_width") or 0),
                    }
                except Exception:
                    name_text_x = name_x + name_pad_x
                    name_text_y = name_y + max(0, int((name_h - name_text_h) / 2))
                name_items = self._maker_add_outlined_text_items(
                    scene,
                    speaker,
                    name_text_x,
                    name_text_y,
                    font=name_font,
                    text_color=self._maker_preview_color(st.get("text_color"), "#FFFFFF"),
                    outline_color=self._maker_preview_color(st.get("outline_color"), "#202020"),
                    outline_width=self._maker_preview_effective_outline_width(st, st.get("outline_width") or 0),
                    # RPG Maker name windows are single-line.  Do not give
                    # QGraphicsTextItem a wrapping width here; if the name is
                    # wider, the window width calculation above must grow.
                    width=None,
                    z=100003,
                    height_scale=height_scale,
                )
                overlay.extend(name_items)

            # Main message text.
            text_color = self._maker_preview_color(st.get("text_color"), "#FFFFFF")
            outline_color = self._maker_preview_color(st.get("outline_color"), "#202020")
            outline_width = self._maker_preview_effective_outline_width(st, st.get("outline_width") or 0)
            # Window_Message textState starts inside the contents rect.  For
            # no-face messages the first line begins at x=0 relative to contents;
            # item padding is mostly for selectable items/name width, so keep the
            # body origin at the window padding but log it explicitly for tuning.
            body_x = box_x + padding
            body_y = box_y + padding
            message_text_rect_diag = {
                "x": body_x,
                "y": body_y,
                "width": body_width,
                "height": max(0, box_h - padding * 2),
                "first_line_x": body_x,
                "first_line_y": body_y,
                "line_height": line_h,
                "outline_effective_width": outline_width,
            }
            try:
                body_items, control_text_diag = self._maker_add_control_text_items(
                    scene,
                    body_text,
                    body_x,
                    body_y,
                    settings=st,
                    base_font=body_font,
                    width=body_width,
                    max_lines=max_lines,
                    line_height=line_h,
                    z=100004,
                    profile=profile,
                    height_scale=height_scale,
                )
            except Exception as _text_e:
                # Never let a plugin/control-code parsing edge case make the
                # selected dialogue look unsupported.  Fall back to plain text
                # while logging the renderer error.
                plain_fallback = strip_maker_control_codes(body_text) or str(body_text or "")
                body_items = self._maker_add_outlined_text_items(
                    scene,
                    plain_fallback,
                    body_x,
                    body_y,
                    font=body_font,
                    text_color=text_color,
                    outline_color=outline_color,
                    outline_width=outline_width,
                    width=None,
                    z=100004,
                    height_scale=height_scale,
                )
                control_text_diag = {
                    "raw_text": str(body_text or ""),
                    "plain_text": plain_fallback,
                    "line_count": line_count,
                    "max_lines": max_lines,
                    "overflow": bool(overflow),
                    "fallback": "plain_text",
                    "error": str(_text_e),
                    "error_type": type(_text_e).__name__,
                }
            overlay.extend(body_items)
            try:
                renderer_width_overflow = bool((control_text_diag or {}).get("width_overflow"))
                renderer_line_overflow = bool((control_text_diag or {}).get("line_count", line_count) and int((control_text_diag or {}).get("line_count") or line_count) > max_lines)
                overflow = bool(renderer_line_overflow or renderer_width_overflow)
                line_count = max(line_count, int((control_text_diag or {}).get("line_count") or line_count))
            except Exception:
                control_text_diag = {}
                renderer_width_overflow = False
                overflow = bool(line_count > max_lines)

            # Show Choices is a separate in-game UI block, not a loose dialogue
            # line.  Render all sibling choices from the same 102 command
            # together so selection text can be checked as an actual choice box.
            try:
                if bool((choice_group or {}).get("enabled")):
                    choice_items, choice_preview_diag = self._maker_preview_add_choice_window(
                        scene,
                        choice_group,
                        settings=st,
                        canvas_w=canvas_w,
                        canvas_h=canvas_h,
                        message_box=(box_x, box_y, message_w, box_h),
                        profile=profile,
                    )
                    overlay.extend(choice_items)
                else:
                    choice_preview_diag = dict(choice_group or {})
            except Exception as _choice_e:
                choice_preview_diag = {"enabled": False, "reason": "error", "error": str(_choice_e), "error_type": type(_choice_e).__name__}

            # Small page indicator triangle, like an RPG Maker message continue
            # mark.  It helps users visually judge the bottom margin.
            try:
                tri_w, tri_h = 16, 10
                cx = box_x + message_w / 2
                by = box_y + box_h - 14
                poly = QPolygonF([
                    QPointF(cx - tri_w / 2, by),
                    QPointF(cx + tri_w / 2, by),
                    QPointF(cx, by + tri_h),
                ])
                tri = QGraphicsPolygonItem(poly)
                tri.setPen(QPen(QColor(255, 255, 255, 210), 1))
                tri.setBrush(QBrush(QColor(255, 255, 255, 220)))
                tri.setZValue(100005)
                scene.addItem(tri)
                overlay.append(tri)
            except Exception:
                pass

            if bool(has_translation_for_warning) and overflow:
                try:
                    width_overflow = bool((control_text_diag or {}).get("width_overflow"))
                except Exception:
                    width_overflow = False
                if width_overflow:
                    warn = self.tr_ui("⚠ 가로 넘침: 실제 줄바꿈을 넣어 주세요")
                else:
                    warn = self.tr_ui("⚠ 줄넘침 가능: {line_count}줄 / 표시 {max_lines}줄", line_count=line_count, max_lines=max_lines)
                warn_item = QGraphicsTextItem(warn)
                warn_item.setDefaultTextColor(QColor(255, 218, 150))
                warn_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                warn_item.setTextWidth(max(80, message_w - padding * 2))
                # Warning is a translator overlay, not part of Window_Message.
                # Place it without changing the game window height.
                warn_y = box_y + box_h + 2
                if warn_y + 18 > canvas_h:
                    warn_y = max(0, box_y - 20)
                warn_item.setPos(box_x + padding, warn_y)
                warn_item.setZValue(100006)
                scene.addItem(warn_item)
                overlay.append(warn_item)

            try:
                font_info = QFontInfo(body_font)
                body_font_diag = dict(body_font_load_diag_snapshot or getattr(self, "_last_maker_preview_font_load_diag", {}) or {})
                body_font_diag.update({
                    "requested_family": str(body_font.family()),
                    "actual_family": str(font_info.family()),
                    "exact_match": bool(font_info.exactMatch()),
                    "pixel_size": int(body_font.pixelSize()),
                    "point_size": int(body_font.pointSize()),
                    "stretch": int(body_font.stretch()),
                    "fallback_mismatch": bool(str(font_info.family()) != str(body_font.family()) and not body_font_diag.get("load_success")),
                })
            except Exception:
                body_font_diag = dict(body_font_load_diag_snapshot or getattr(self, "_last_maker_preview_font_load_diag", {}) or getattr(self, "_last_maker_preview_font_diag", {}) or {})
            try:
                self._append_maker_preview_diagnostic("scene_preview_render", {
                    "page_index": int(getattr(self, "idx", -1)),
                    "page_type": page_type,
                    "row_id": (row or {}).get("id"),
                    "speaker": speaker,
                    "text_type": text_type,
                    "source_label": source_label,
                    "preview_payload": preview_payload,
                    "screen": {"width": canvas_w, "height": canvas_h},
                    "message_window": {
                        "x": box_x, "y": box_y, "width": message_w, "height": box_h,
                        "margin": margin, "padding": padding, "max_lines": max_lines,
                        "body_width": body_width, "configured_height": configured_h, "natural_height": natural_h,
                        "window_opacity": win_opacity,
                    },
                    "name_window": {
                        "enabled": bool(speaker),
                        "x": locals().get("name_x", None), "y": locals().get("name_y", None),
                        "width": locals().get("name_w", None), "height": locals().get("name_h", None),
                        "pad_x": locals().get("name_pad_x", None), "pad_y": locals().get("name_pad_y", None),
                    },
                    "window_skin": window_skin_diag,
                    "picture_state": picture_state_diag,
                    "picture_layers": rendered_picture_diag,
                    "choice_preview": choice_preview_diag,
                    "name_text_rect": name_text_rect_diag,
                    "message_text_rect": message_text_rect_diag,
                    "font": body_font_diag,
                    "metrics": {"line_height": line_h, "base_line_height": base_line_h, "line_count": line_count, "overflow": overflow},
                    "wrap": {"visible_text": strip_maker_control_codes(body_text), "raw_text": body, "raw_length": len(str(body or "")), "control_text": locals().get("control_text_diag", {})},
                    "settings_snapshot": {
                        k: st.get(k) for k in (
                            "font_family", "font_path", "fallback_fonts", "main_font_filename",
                            "font_size", "name_font_size", "char_width", "char_height",
                            "line_spacing", "line_height", "item_padding", "box_margin", "letter_spacing", "outline_width",
                            "screen_width", "screen_height", "ui_area_width", "ui_area_height", "message_x", "message_y",
                            "message_width", "message_height", "message_padding", "message_lines", "message_margin",
                            "window_opacity", "debug_overlay", "show_picture_opacity"
                        )
                    },
                })
            except Exception:
                pass

            try:
                for _ov in overlay:
                    try:
                        _ov.setData(0, "maker_preview_overlay")
                    except Exception:
                        pass
            except Exception:
                pass
            self._maker_preview_overlay_items = overlay
            try:
                scene.update()
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                self.log(self.tr_ui("⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}", error=e))
            except Exception:
                pass
            # Last-resort fallback: keep the already-rendered map base, but draw
            # the selected row's message box so users can still inspect the text.
            try:
                fallback_items, fallback_diag = self._maker_preview_add_minimal_message_fallback(
                    scene, row, curr, locals().get("st", {}) or {},
                    canvas_w=locals().get("canvas_w", 816),
                    canvas_h=locals().get("canvas_h", 624),
                    profile=locals().get("profile", {}) or {},
                    reason=f"full_preview_failed:{type(e).__name__}",
                )
                if fallback_items:
                    self._maker_preview_overlay_items = list(fallback_items)
                    try:
                        self._append_maker_preview_diagnostic("scene_preview_render_fallback", fallback_diag)
                    except Exception:
                        pass
                    try:
                        scene.update()
                    except Exception:
                        pass
                    return True
            except Exception:
                pass
            self._clear_maker_preview_selection_overlay()
            return False

    def selected_table_text_ids(self):
        if not hasattr(self, 'tab'):
            return []
        rows = sorted({idx.row() for idx in self.tab.selectedIndexes() if idx.row() > 0})
        ids = []
        for row in rows:
            item = self.tab.item(row, 0)
            if item:
                ids.append(item.text().strip())
        return ids

    def on_table_selection_changed(self):
        if self._syncing_selection:
            return
        if getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
            return
        try:
            if hasattr(self, "is_maker_database_mode") and self.is_maker_database_mode():
                try:
                    self.refresh_maker_table_current_row_marker()
                except Exception:
                    pass
                self.refresh_maker_database_preview_from_selection()
                return
        except Exception:
            pass
        try:
            if self._is_current_maker_page():
                # Keep the table Excel-like: the selected cell/range remains real
                # selection, while the current row is only repainted as a marker.
                try:
                    self.refresh_maker_table_current_row_marker()
                except Exception:
                    pass
                self.update_maker_preview_selection_from_table()
                try:
                    if str(getattr(self, "maker_control_code_display_mode", "hidden") or "hidden") == "current":
                        if not bool(getattr(self, "_maker_control_selection_refresh_lock", False)):
                            self._maker_control_selection_refresh_lock = True
                            try:
                                if hasattr(self, "refresh_maker_control_code_source_cells"):
                                    self.refresh_maker_control_code_source_cells()
                            finally:
                                self._maker_control_selection_refresh_lock = False
                except Exception:
                    try:
                        self._maker_control_selection_refresh_lock = False
                    except Exception:
                        pass
                # Maker 표 선택은 좌측 scene에 역동기화하지 않는다.
                # 이 return이 없으면 drag range가 select_table_rows_by_ids()/scene sync에 의해 즉시 깨진다.
                return
        except Exception:
            pass
        if self.cb_mode.currentIndex() != 4:
            return
        scene = self._safe_graphics_scene()
        if scene is None:
            return
        active_transform = self.current_transform_data_item()
        if active_transform is not None:
            self.reselect_text_items([active_transform.get('id')])
            return
        ids = set(self.selected_table_text_ids())
        self._syncing_selection = True
        try:
            scene.blockSignals(True)
            try:
                for item in scene.items():
                    if isinstance(item, TypesettingItem):
                        item.setSelected(str(item.data.get('id')) in ids)
            finally:
                scene.blockSignals(False)
        except RuntimeError:
            pass
        except Exception:
            pass
        finally:
            self._syncing_selection = False
        # 우측 스타일 칸은 첫 선택 항목 기준으로 맞춘다.
        self.on_scene_selection_changed()

    def configure_live_text_numeric_inputs(self):
        """텍스트 스타일 숫자 입력은 조작 즉시 화면에 반영한다.

        전체 숫자 입력칸은 안정성을 위해 keyboardTracking=False를 쓰지만,
        텍스트 스타일 컨트롤은 작업자가 수치를 움직이며 결과를 봐야 하므로
        별도로 실시간 추적을 켠다. Undo는 아래 live style session이 묶어서 기록한다.
        """
        for attr in (
            "sb_font_size", "sb_strk", "sb_line_spacing", "sb_letter_spacing", "sb_char_width", "sb_char_height",
            "final_item_size", "final_item_stroke", "sb_text_opacity",
        ):
            try:
                spin = getattr(self, attr, None)
                if spin is None:
                    continue
                spin.setKeyboardTracking(True)
                spin.setProperty("ysb_live_text_style_spin", True)
            except Exception:
                pass

    def _live_text_style_selected_key(self, items=None):
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
        except Exception:
            page_idx = 0
        ids = []
        for item in list(items or self.selected_text_items() or []):
            try:
                sid = getattr(item, "data", {}).get("id")
                if sid is not None:
                    ids.append(str(sid))
            except Exception:
                pass
        return (page_idx, tuple(sorted(ids)))







































    def on_global_text_style_changed(self, *args):
        if self._style_signal_lock:
            return
        if getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
            return
        selected = self.selected_text_items()
        if not selected or self.cb_mode.currentIndex() != 4:
            self.update_text_style_control_state([])
            return
        patch = self._style_patch_from_sender()
        if not patch:
            return
        self.set_preset_combo_to_last()
        self.set_item_preset_combo_custom()
        self.schedule_last_text_preset_save("__last__")
        self.apply_style_to_selected(**patch)

    def set_global_align(self, align):
        if getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
            return
        selected = self.selected_text_items()
        if not selected or self.cb_mode.currentIndex() != 4:
            self.update_text_style_control_state([])
            return
        self.default_align = align
        self.set_preset_combo_to_last()
        self.set_item_preset_combo_custom()
        self.schedule_last_text_preset_save("__last__")
        self.apply_style_to_selected(align=align)
        self.update_text_style_control_state(selected)

    def pick_color(self, target):
        if target in ("global_text", "global_stroke") and (not self.selected_text_items() or self.cb_mode.currentIndex() != 4):
            self.update_text_style_control_state([])
            return
        if target == "final_paint":
            current = self.final_paint_color
        else:
            current = self.default_text_color if "text" in target else self.default_stroke_color
        color = ysb_get_color_with_hex_focus(QColor(current), self, "색상 선택")
        if not color.isValid():
            return
        hex_color = color.name(QColor.NameFormat.HexRgb).upper()
        if target == "global_text":
            self.default_text_color = hex_color
            self.update_color_button_styles()
            if self.cb_mode.currentIndex() == 4 and self.selected_text_items():
                self.set_preset_combo_to_last()
                self.set_item_preset_combo_custom()
                self.schedule_last_text_preset_save("__last__")
                self.apply_style_to_selected(text_color=hex_color)
        elif target == "global_stroke":
            self.default_stroke_color = hex_color
            self.update_color_button_styles()
            if self.cb_mode.currentIndex() == 4 and self.selected_text_items():
                self.set_preset_combo_to_last()
                self.set_item_preset_combo_custom()
                self.schedule_last_text_preset_save("__last__")
                self.apply_style_to_selected(stroke_color=hex_color)
        elif target == "item_text":
            self.apply_style_to_selected(text_color=hex_color)
        elif target == "item_stroke":
            self.apply_style_to_selected(stroke_color=hex_color)
        elif target == "final_paint":
            self.final_paint_color = hex_color
            self.update_color_button_styles()
            self.log(f"🎨 최종 페인팅 색상: {hex_color}")

    def on_show_final_text_toggled(self, checked):
        old_state = bool(getattr(self, "_last_show_final_text_checked", not bool(checked)))
        new_state = bool(checked)
        if (
            old_state != new_state
            and not getattr(self, "_project_undo_restore_lock", False)
            and not getattr(self, "is_loading_project", False)
            and not getattr(self, "is_page_loading", False)
            and not getattr(self, "is_batch_running", False)
        ):
            try:
                rec = self.make_project_undo_record("텍스트 표시 ON/OFF")
                rec.setdefault("ui_state", self.current_project_ui_state())
                rec["ui_state"]["show_final_text"] = old_state
                self.undo_push_project(rec)
            except Exception:
                pass
        self._last_show_final_text_checked = new_state
        if self.cb_mode.currentIndex() == 4:
            old_suppress = getattr(self, "_suppress_mode_undo", False)
            self._suppress_mode_undo = True
            try:
                self.mode_chg(4)
            finally:
                self._suppress_mode_undo = old_suppress
        self.auto_save_project()

    def active_mask_key(self, mode_idx=None):
        mode_idx = self.cb_mode.currentIndex() if mode_idx is None else mode_idx
        if hasattr(self, "mask_engine") and self.mask_engine is not None:
            try:
                return self.mask_engine.active_key(mode_idx, bool(getattr(self, "mask_toggle_enabled", False)))
            except Exception:
                pass
        # Fallback for older startup states.
        if mode_idx == 2:
            return 'mask_merge'
        if mode_idx == 3:
            return 'mask_inpaint' if self.mask_toggle_enabled else 'mask_inpaint_off'
        return None

    def get_active_mask(self, curr, mode_idx=None):
        if hasattr(self, "mask_engine") and self.mask_engine is not None:
            try:
                mode_idx = self.cb_mode.currentIndex() if mode_idx is None else mode_idx
                return self.mask_engine.get_mask(curr, mode_idx=mode_idx, mask_toggle_enabled=bool(getattr(self, "mask_toggle_enabled", False)))
            except Exception:
                pass
        key = self.active_mask_key(mode_idx)
        if not key or not curr:
            return None
        return curr.get(key)

    def set_active_mask(self, curr, mask, mode_idx=None):
        mode_idx = self.cb_mode.currentIndex() if mode_idx is None else mode_idx
        if hasattr(self, "mask_engine") and self.mask_engine is not None:
            try:
                return self.mask_engine.set_mask(curr, mask, page_idx=int(getattr(self, "idx", 0) or 0), mode_idx=mode_idx, mask_toggle_enabled=bool(getattr(self, "mask_toggle_enabled", False)))
            except Exception:
                pass
        key = self.active_mask_key(mode_idx)
        if key and curr is not None:
            curr[key] = mask.copy() if isinstance(mask, np.ndarray) else mask
            curr[f"{key}_dirty"] = True
            try:
                self.mark_active_page_dirty("mask")
            except Exception:
                pass
        return key

    def on_mask_toggle_changed(self, checked):
        curr = self.data.get(self.idx)
        old_state = self.mask_toggle_enabled
        mode = self.cb_mode.currentIndex()
        if (
            mode == 3
            and not getattr(self, "_project_undo_restore_lock", False)
            and not getattr(self, "is_page_loading", False)
            and not getattr(self, "is_batch_running", False)
        ):
            try:
                self.commit_current_page_ui_to_data(include_mask=True)
                self.push_project_undo("마스크 ON/OFF")
            except Exception:
                pass

        # 토글은 페인팅 마스크 전용이다.
        # 텍스트 마스크에서는 분석 마스크(mask_merge)만 쓰므로 ON/OFF 분리 저장을 하지 않는다.
        if curr is not None and mode == 3:
            # 토글을 바꾸기 직전, 화면에 떠 있는 현재 페인팅 마스크를 이전 토글 슬롯에 먼저 저장한다.
            m = self.view.get_mask_np()
            if m is not None:
                curr['mask_inpaint' if old_state else 'mask_inpaint_off'] = m.copy()

        self.mask_toggle_enabled = bool(checked)
        if hasattr(self, "act_mask_toggle"):
            self.act_mask_toggle.setText("☑" if checked else "☐")
        if curr is not None:
            curr['mask_toggle_enabled'] = self.mask_toggle_enabled
        state = "ON" if checked else "OFF"
        self.log(f"🎚️ 페인팅 마스크 토글: {state}")

        if mode == 3:
            # 토글은 탭 이동이 아니라 같은 페인팅 마스크 탭 안에서
            # mask_inpaint / mask_inpaint_off 슬롯만 바꾸는 작업이다.
            # 따라서 mode_chg(3)로 화면을 다시 그릴 때:
            # 1) 탭 변경 Undo를 만들지 않고
            # 2) 이전 화면 마스크를 새 토글 슬롯에 덮어쓰지 않도록 막는다.
            old_suppress_mode_undo = getattr(self, "_suppress_mode_undo", False)
            old_skip_mode_mask_commit = getattr(self, "_skip_mode_mask_commit", False)
            old_mask_toggle_refreshing = getattr(self, "_mask_toggle_refreshing", False)
            self._suppress_mode_undo = True
            self._skip_mode_mask_commit = True
            self._mask_toggle_refreshing = True
            try:
                self.mode_chg(3)
            finally:
                self._suppress_mode_undo = old_suppress_mode_undo
                self._skip_mode_mask_commit = old_skip_mode_mask_commit
                self._mask_toggle_refreshing = old_mask_toggle_refreshing
        self.auto_save_project()

    def set_mask_toggle_safely(self, checked):
        self.mask_toggle_enabled = bool(checked)
        if hasattr(self, 'cb_mask_toggle'):
            self.cb_mask_toggle.blockSignals(True)
            try:
                self.cb_mask_toggle.setChecked(bool(checked))
                if hasattr(self, "act_mask_toggle"):
                    self.act_mask_toggle.setText("☑" if checked else "☐")
            finally:
                self.cb_mask_toggle.blockSignals(False)

    def get_page_stem(self, page_idx):
        """
        TXT 추출/번역문 불러오기용 파일명 기준.

        이제 기준은 실제 프로젝트의 뿌리 이름인 original_name이다.
        원본 파일명 변경 기능이 original_name과 images 경로를 함께 갱신하므로,
        TXT 출력/일괄 불러오기도 같은 이름을 따라가야 한다.
        """
        try:
            curr = self.data.get(page_idx, {}) if isinstance(self.data, dict) else {}
            name = curr.get('original_name') if isinstance(curr, dict) else ""
            if name:
                return safe_page_file_stem(Path(str(name)).stem, fallback=f"page{int(page_idx) + 1:03d}")
        except Exception:
            pass
        try:
            return safe_page_file_stem(Path(os.path.basename(self.paths[page_idx])).stem, fallback=f"page{int(page_idx) + 1:03d}")
        except Exception:
            return f"page{int(page_idx) + 1:03d}"

    def get_output_root(self):
        if self.project_dir:
            return self.project_dir
        if self.paths:
            return os.path.dirname(os.path.abspath(self.paths[self.idx]))
        return os.getcwd()

    def ensure_subdir(self, name):
        root = self.get_output_root()
        path = os.path.join(root, name)
        os.makedirs(path, exist_ok=True)
        return path

    def output_cleanup_targets(self):
        """현재 프로젝트에서 삭제 가능한 출력물 목록을 모은다."""
        root = Path(self.get_output_root())
        targets = {
            "result": [],
            "script": [],
            "txt": [],
        }

        for result_dir in (root / "result", root / "Result"):
            if result_dir.exists():
                try:
                    targets["result"].extend([p for p in result_dir.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp")])
                except Exception:
                    pass

        scripts_dir = root / "scripts"
        if scripts_dir.exists():
            try:
                targets["script"].extend([p for p in scripts_dir.iterdir() if p.is_file() and p.suffix.lower() in (".jsx", ".js", ".txt")])
            except Exception:
                pass

        for txt_dir in (root / "txt", root / "Txt"):
            if txt_dir.exists():
                try:
                    targets["txt"].extend([p for p in txt_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
                except Exception:
                    pass

        return targets

    def open_output_cleanup_dialog(self):
        """옵션: 현재 프로젝트 산출물 삭제."""
        if not self.project_dir:
            QMessageBox.information(self, self.tr_ui("출력물 삭제"), self.tr_ui("먼저 프로젝트를 열어주세요."))
            return False

        targets = self.output_cleanup_targets()
        counts = {k: len(v) for k, v in targets.items()}
        if not any(counts.values()):
            QMessageBox.information(self, self.tr_ui("출력물 삭제"), self.tr_ui("삭제할 출력물이 없습니다."))
            return False

        dlg = OutputCleanupDialog(counts, self)
        try:
            dlg.setStyleSheet(self.message_box_style())
        except Exception:
            pass
        if not dlg.exec():
            return False

        selected = dlg.selected()
        files = []
        labels = []
        if selected.get("result"):
            files.extend(targets.get("result", []))
            labels.append(f"{self.tr_ui('최종결과 이미지')} {len(targets.get('result', []))}개")
        if selected.get("script"):
            files.extend(targets.get("script", []))
            labels.append(f"{self.tr_ui('포토샵 스크립트')} {len(targets.get('script', []))}개")
        if selected.get("txt"):
            files.extend(targets.get("txt", []))
            labels.append(f"{self.tr_ui('TXT 지문')} {len(targets.get('txt', []))}개")

        if not files:
            return False

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(self.tr_ui("출력물 삭제 확인"))
        msg.setText(self.tr_ui("선택한 출력물을 삭제할까요?"))
        msg.setInformativeText("\n".join(labels))
        btn_delete = msg.addButton(self.tr_ui("삭제"), QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg.addButton(self.tr_ui("취소"), QMessageBox.ButtonRole.RejectRole)
        for _btn in (btn_delete, btn_cancel):
            try:
                _btn.setMinimumWidth(96)
            except Exception:
                pass
        msg.setDefaultButton(btn_cancel)
        msg.setEscapeButton(btn_cancel)
        try:
            msg.setStyleSheet(self.message_box_style())
        except Exception:
            pass
        force_message_box_front(msg)
        msg.exec()
        if msg.clickedButton() is not btn_delete:
            self.log("↩️ 출력물 삭제 취소")
            return False

        deleted = 0
        failed = 0
        for p in files:
            try:
                p = Path(p)
                if p.exists() and p.is_file():
                    p.unlink()
                    deleted += 1
            except Exception:
                failed += 1

        self.log(f"🧹 출력물 삭제 완료: {deleted}개 삭제 / 실패 {failed}개")
        if failed:
            QMessageBox.warning(self, self.tr_ui("출력물 삭제"), f"{self.tr_ui('일부 파일을 삭제하지 못했습니다.')} 실패: {failed}개")
        return True

    def choose_text_extract_mode(self):
        ko_items = ["원문만", "번역문만", "원문+번역문"]
        display_items = [self.tr_ui(x) for x in ko_items]
        value, ok = QInputDialog.getItem(
            self,
            self.tr_ui("원문/번역문 내보내기"),
            self.tr_ui("추출할 내용:"),
            display_items,
            0,
            False
        )
        if not ok:
            return None
        try:
            idx = display_items.index(value)
            return ko_items[idx]
        except ValueError:
            return value

    def build_text_export_content(self, page_idx, mode):
        curr = self.data.get(page_idx, {})
        blocks = []
        for i, item in enumerate(curr.get('data', []), 1):
            text_id = str(item.get('id', i))
            original = str(item.get('text', '') or '')
            try:
                if isinstance(item, dict) and isinstance(item.get('maker_text_unit'), dict):
                    original = strip_maker_control_codes(original)
            except Exception:
                pass
            translated = str(item.get('translated_text', '') or '')
            marker = f"[{text_id}]"
            if mode == "원문만":
                blocks.append(f"{marker}\n\n{original}")
            elif mode == "번역문만":
                blocks.append(f"{marker}\n\n{translated}")
            else:
                blocks.append(f"{marker}\n\n{original}\n\n{translated}")
        return "\n\n".join(blocks).rstrip() + "\n"

    def extract_text_current(self):
        if not self.paths:
            return
        self.commit_current_page_ui_to_data()
        mode = self.choose_text_extract_mode()
        if not mode:
            return
        page_label = self.get_page_stem(self.idx)
        if not self.ask_yes_no_shortcut(
            "원문/번역문 내보내기",
            "현재 페이지의 원문/번역문 TXT를 내보냅니다. 계속할까요?",
            yes_text="내보내기",
            no_text="취소",
            default_yes=False,
            icon=QMessageBox.Icon.Warning,
            parent=self,
        ):
            self.log("↩️ Source/translation export canceled" if self.ui_language == LANG_EN else "↩️ 원문/번역문 내보내기 취소")
            return
        txt_dir = self.ensure_subdir("txt")
        out_path = os.path.join(txt_dir, f"{page_label}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(self.build_text_export_content(self.idx, mode))
        self.log((f"📄 Source/translation export complete: {out_path}" if self.ui_language == LANG_EN else f"📄 원문/번역문 내보내기 완료: {out_path}"))
        try:
            QMessageBox.information(
                self,
                self.tr_ui("원문/번역문 내보내기 완료"),
                f"{self.tr_ui('현재 페이지의 원문/번역문 TXT 내보내기가 완료되었습니다.')}\n{out_path}",
            )
        except Exception:
            pass
        self.auto_save_project()

    def extract_text_batch(self):
        if not self.paths:
            return
        title = "일괄 원문/번역문 내보내기"
        selected_indices, selected_label = self.choose_batch_page_indices_for_context(title, "extract_text")
        if selected_indices is None:
            self.log("↩️ Batch source/translation export canceled" if self.ui_language == LANG_EN else "↩️ 일괄 원문/번역문 내보내기 취소")
            return
        self.commit_current_page_ui_to_data()
        mode = self.choose_text_extract_mode()
        if not mode:
            return
        if not self.ask_yes_no_shortcut(
            "일괄 원문/번역문 내보내기",
            "선택한 페이지들의 원문/번역문 TXT를 내보냅니다. 계속할까요?",
            yes_text="내보내기",
            no_text="취소",
            default_yes=False,
            icon=QMessageBox.Icon.Warning,
            parent=self,
        ):
            self.log("↩️ Batch source/translation export canceled" if self.ui_language == LANG_EN else "↩️ 일괄 원문/번역문 내보내기 취소")
            return
        txt_dir = self.ensure_subdir("txt")

        def process_page(i):
            if i not in self.data or not self.data[i].get('data'):
                return "skipped", "텍스트 데이터 없음"
            out_path = os.path.join(txt_dir, f"{self.get_page_stem(i)}.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(self.build_text_export_content(i, mode))
            return "done", os.path.basename(out_path)

        self.run_page_queue_batch(title, "extract_text", selected_indices, selected_label, process_page, visual=False, cancellable=True)



    def parse_translation_txt(self, path, valid_ids):
        valid = {str(x) for x in valid_ids}

        def marker_to_id(token):
            token = str(token or "").strip()
            if len(token) >= 3 and token.startswith("[") and token.endswith("]"):
                inner = token[1:-1].strip()
                if inner.isdigit() and inner in valid:
                    return inner
            return None

        with open(path, "r", encoding="utf-8-sig") as f:
            lines = f.read().splitlines()

        result = {}
        i = 0
        while i < len(lines):
            text_id = marker_to_id(lines[i])
            if text_id:
                i += 1
                buf = []
                while i < len(lines):
                    # 다음 번호는 [1]처럼 대괄호 안의 숫자이고,
                    # 현재 페이지에 실제 존재하는 텍스트 번호일 때만 인정한다.
                    # 그래서 1131313, 421 같은 숫자 번역문은 안전하게 본문으로 들어간다.
                    if marker_to_id(lines[i]):
                        break
                    if lines[i].strip():
                        buf.append(lines[i].rstrip())
                    i += 1

                if buf:
                    result[text_id] = "\n".join(buf).strip()
                continue

            i += 1

        return result

    def apply_translation_map_to_page(self, page_idx, trans_map):
        curr = self.data.get(page_idx)
        if not curr:
            return 0
        count = 0
        for i, item in enumerate(curr.get('data', []), 1):
            text_id = str(item.get('id', i))
            if text_id in trans_map:
                new_text = str(trans_map[text_id] or '')
                old_text = str(item.get('translated_text', '') or '')
                if new_text != old_text:
                    item['translated_text'] = new_text
                    try:
                        self.shrink_text_rect_to_content(item)
                    except Exception:
                        pass
                    count += 1
        return count

    def filename_match_aliases(self, value):
        """클린본/TXT 일괄 불러오기에서 쓸 파일명 stem 별칭 후보를 만든다.

        원본 stem을 1순위로 유지하되, 페이지탭/출력명에 붙을 수 있는
        1p_, page001_, clean_, result_ 같은 접두어/번호형을 양방향으로 보정한다.
        """
        seen = set()
        result = []

        def norm(v):
            try:
                stem = safe_page_file_stem(Path(str(v)).stem, fallback="")
                return str(stem or "").strip()
            except Exception:
                return ""

        def add(v):
            s = norm(v)
            if not s:
                return
            key = s.casefold()
            if key not in seen:
                seen.add(key)
                result.append(s)

        base = norm(value)
        if not base:
            return result

        queue = [base]
        known_prefixes = (
            "clean", "cleaned", "clear", "cleared", "clean본", "cleanbon",
            "클린", "클린본", "result", "results", "output", "out", "final",
            "최종", "결과", "bg", "background", "inpaint", "inpainted",
            "no_text", "notext", "textless", "remove_text", "removed_text",
        )
        known_suffixes = known_prefixes

        steps = 0
        while queue and steps < 128:
            steps += 1
            current = queue.pop(0)
            before_len = len(result)
            add(current)

            variants = set()
            s = current.strip()

            # 1p_제목, 01p-제목, page001_제목, page0001_제목, p001_제목, 001_제목 같은 페이지 접두어 제거
            for pattern in (
                r"^\s*\d{1,4}\s*p\s*[_\-\s]+(.+)$",
                r"^\s*p\s*\d{1,4}\s*[_\-\s]+(.+)$",
                r"^\s*page\s*\d{1,4}\s*[_\-\s]+(.+)$",
                r"^\s*페이지\s*\d{1,4}\s*[_\-\s]+(.+)$",
                r"^\s*\d{1,4}\s*[_\-\s]+(.+)$",
            ):
                m = re.match(pattern, s, flags=re.IGNORECASE)
                if m:
                    variants.add(m.group(1).strip())

            # clean_제목 / result-제목 / 최종 제목 같은 작업명 접두어 제거
            for prefix in known_prefixes:
                m = re.match(rf"^\s*{re.escape(prefix)}\s*[_\-\s]+(.+)$", s, flags=re.IGNORECASE)
                if m:
                    variants.add(m.group(1).strip())

            # 제목_clean / 제목-result 같은 작업명 접미어 제거
            for suffix in known_suffixes:
                m = re.match(rf"^(.+?)\s*[_\-\s]+{re.escape(suffix)}\s*$", s, flags=re.IGNORECASE)
                if m:
                    variants.add(m.group(1).strip())

            # 기본 stem에 대해 흔한 외부 작업물 파일명도 후보로 추가
            # 예: 제목 ↔ clean_제목 / result_제목 / 1p_제목
            already_page_prefixed = re.match(r"^\s*(?:\d{1,4}\s*p|page\s*\d{1,4}|p\s*\d{1,4}|페이지\s*\d{1,4}|\d{1,4})\s*[_\-\s]+", s, flags=re.IGNORECASE)
            already_work_prefixed = any(
                re.match(rf"^\s*{re.escape(prefix)}\s*[_\-\s]+", s, flags=re.IGNORECASE)
                for prefix in known_prefixes
            )
            if not already_page_prefixed and not already_work_prefixed:
                for prefix in ("clean", "cleaned", "clean본", "클린본", "result", "output", "final", "최종", "결과", "inpainted"):
                    variants.add(f"{prefix}_{s}")

            for v in variants:
                nv = norm(v)
                if nv and nv.casefold() not in seen:
                    queue.append(nv)

            # 무한 변형 방지. 이번 라운드에서 추가가 없고 새 큐도 없으면 종료.
            if len(result) == before_len and not queue:
                break

        return result

    def add_page_number_name_candidates(self, candidates, seen, page_idx):
        """page001처럼 제목 없이 페이지 번호만 있는 파일명 후보를 강제로 추가한다."""
        try:
            page_no = int(page_idx) + 1
        except Exception:
            return

        def add_raw(value):
            try:
                stem = safe_page_file_stem(Path(str(value)).stem, fallback="")
                key = str(stem or "").casefold()
                if stem and key not in seen:
                    seen.add(key)
                    candidates.append(stem)
            except Exception:
                pass

        for stem in (
            f"page{page_no:03d}",
            f"page{page_no:04d}",
            f"p{page_no:03d}",
            f"p{page_no:04d}",
            f"{page_no:03d}",
            f"{page_no:04d}",
        ):
            add_raw(stem)

    def translation_txt_name_candidates(self, page_idx):
        """번역문 다중 불러오기에서 허용할 TXT 파일명 후보.

        원본 이미지 stem을 기본으로 하되, 페이지탭/출력명이 1p_원본명, page001,
        page0001, clean_원본명, result_원본명처럼 달라져도 같은 페이지로 매칭한다.
        """
        candidates = []
        seen = set()

        def add(value):
            for stem in self.filename_match_aliases(value):
                key = str(stem or "").casefold()
                if stem and key not in seen:
                    seen.add(key)
                    candidates.append(stem)

        add(self.get_page_stem(page_idx))
        try:
            add(self.page_display_name(page_idx, mode=PAGE_DISPLAY_MODE_ORIGINAL, include_ext=False))
            add(self.page_display_name(page_idx, mode=PAGE_DISPLAY_MODE_PAGE_ORIGINAL, include_ext=False))
            add(self.page_display_name(page_idx, mode=PAGE_DISPLAY_MODE_PAGE_NUMBER, include_ext=False))
            add(self.output_display_stem(page_idx))
        except Exception:
            pass
        self.add_page_number_name_candidates(candidates, seen, page_idx)
        return candidates

    def find_translation_txt_in_folder(self, folder, page_stem=None, page_idx=None):
        """번역문 불러오기용 TXT 탐색.

        원본명.txt를 기본으로 찾고, 1p_원본명.txt / page001.txt / 출력 표시명.txt도 후보로 인정한다.
        선택한 폴더 바로 아래를 먼저 찾은 뒤 없으면 하위 폴더까지 한 번 더 찾는다.
        """
        if not folder:
            return None
        root = Path(folder)
        if not root.exists() or not root.is_dir():
            return None

        candidates = []
        if page_idx is not None:
            candidates.extend(self.translation_txt_name_candidates(page_idx))
        if page_stem:
            seen = {str(x or "").casefold() for x in candidates}
            for stem in self.filename_match_aliases(page_stem):
                key = str(stem or "").casefold()
                if stem and key not in seen:
                    seen.add(key)
                    candidates.append(stem)
        if not candidates:
            return None

        targets = {f"{stem}.txt".casefold() for stem in candidates}

        try:
            for child in root.iterdir():
                if child.is_file() and child.name.casefold() in targets:
                    return str(child)
        except Exception:
            pass

        try:
            for child in root.rglob("*.txt"):
                if child.is_file() and child.name.casefold() in targets:
                    return str(child)
        except Exception:
            pass
        return None

    def match_translation_txt_paths_to_pages(self, paths):
        """여러 TXT 파일을 파일명 stem 기준으로 프로젝트 페이지에 매칭한다."""
        by_stem = {}
        exact_items = []
        for path in paths or []:
            try:
                stem = safe_page_file_stem(Path(str(path)).stem, fallback="")
                key = str(stem or "").casefold()
                if key:
                    exact_items.append((path, stem))
                    if key not in by_stem:
                        by_stem[key] = path
            except Exception:
                pass

        # 정확한 파일명 매칭을 먼저 등록한 뒤, 별칭 매칭은 빈 키에만 채운다.
        # title.txt와 clean_title.txt가 동시에 있을 때 title.txt가 우선된다.
        for path, stem in exact_items:
            for alias in self.filename_match_aliases(stem):
                key = str(alias or "").casefold()
                if key and key not in by_stem:
                    by_stem[key] = path

        matched = {}
        for page_idx in range(len(getattr(self, "paths", []) or [])):
            for cand in self.translation_txt_name_candidates(page_idx):
                key = str(cand or "").casefold()
                if key in by_stem:
                    matched[page_idx] = by_stem[key]
                    break
        return matched

    def clean_image_name_candidates(self, page_idx):
        """클린본 불러오기용 이미지 파일명 후보."""
        candidates = []
        seen = set()

        def add(value):
            for stem in self.filename_match_aliases(value):
                key = str(stem or "").casefold()
                if stem and key not in seen:
                    seen.add(key)
                    candidates.append(stem)

        add(self.get_page_stem(page_idx))
        try:
            add(self.page_display_name(page_idx, mode=PAGE_DISPLAY_MODE_ORIGINAL, include_ext=False))
            add(self.page_display_name(page_idx, mode=PAGE_DISPLAY_MODE_PAGE_ORIGINAL, include_ext=False))
            add(self.page_display_name(page_idx, mode=PAGE_DISPLAY_MODE_PAGE_NUMBER, include_ext=False))
            add(self.output_display_stem(page_idx))
        except Exception:
            pass
        self.add_page_number_name_candidates(candidates, seen, page_idx)
        return candidates

    def read_clean_image_file(self, path, page_idx):
        try:
            img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return None
            return self.normalize_image_to_original_size(page_idx, img)
        except Exception:
            return None

    def pending_clean_import_root(self, base_dir=None):
        """클린본 불러오기 전용 경량 복구 캐시 폴더."""
        try:
            root = str(base_dir or getattr(self, "work_project_dir", None) or getattr(self, "project_dir", None) or "")
            if not root:
                return None
            return os.path.join(root, "pending_clean_import")
        except Exception:
            return None

    def pending_clean_import_manifest_path(self, base_dir=None):
        root = self.pending_clean_import_root(base_dir)
        return os.path.join(root, "pending_clean_import_map.json") if root else None

    def load_pending_clean_import_manifest(self, base_dir=None):
        path = self.pending_clean_import_manifest_path(base_dir)
        if not path or not os.path.exists(path):
            return {"version": 1, "type": "pending_clean_import", "pages": {}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        data.setdefault("version", 1)
        data.setdefault("type", "pending_clean_import")
        if not isinstance(data.get("pages"), dict):
            data["pages"] = {}
        return data

    def save_pending_clean_import_manifest(self, manifest, base_dir=None):
        path = self.pending_clean_import_manifest_path(base_dir)
        if not path:
            return False
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(manifest or {}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 클린본 복구 맵 내보내기 실패: {e}")
            except Exception:
                pass
            return False

    def ensure_pending_clean_import_cache(self):
        """무거운 ProjectStore.save() 없이 클린본 복구용 pending 폴더만 준비한다."""
        try:
            if not getattr(self, "work_project_dir", None):
                # 일반 프로젝트 열기 직후에는 작업 캐시가 이미 있다.
                # 예외적으로 없으면 현재 상태 기준 캐시를 한 번만 만든다.
                self.start_work_cache_from_current(mark_dirty=True)
            root = self.pending_clean_import_root(getattr(self, "work_project_dir", None))
            if not root:
                return None
            os.makedirs(os.path.join(root, "files"), exist_ok=True)
            self.record_recovery_project_dir(getattr(self, "work_project_dir", None))
            return root
        except Exception as e:
            try:
                self.log(f"⚠️ 클린본 pending 캐시 준비 실패: {e}")
            except Exception:
                pass
            return None

    def record_pending_clean_import_page(self, page_idx, source_path):
        """page_idx에 적용한 클린본 파일을 가벼운 pending 복구 캐시에 기록한다.

        ProjectStore.save() 전체를 돌리지 않고, 원본 클린본 파일 복사본과 작은 JSON만 남긴다.
        """
        root = self.ensure_pending_clean_import_cache()
        if not root:
            return False
        try:
            page_idx = int(page_idx)
            src = Path(str(source_path))
            ext = src.suffix.lower()
            if ext not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                ext = ".png"
            files_dir = os.path.join(root, "files")
            os.makedirs(files_dir, exist_ok=True)
            stem = f"page{page_idx + 1:04d}"
            # 같은 페이지에 다시 적용하면 이전 확장자 파일은 남기지 않는다.
            try:
                for old in Path(files_dir).glob(stem + ".*"):
                    try:
                        old.unlink()
                    except Exception:
                        pass
            except Exception:
                pass
            dst = os.path.join(files_dir, stem + ext)
            shutil.copy2(str(src), dst)

            manifest = self.load_pending_clean_import_manifest(getattr(self, "work_project_dir", None))
            pages = manifest.setdefault("pages", {})
            try:
                rel = os.path.relpath(dst, str(getattr(self, "work_project_dir", None)))
            except Exception:
                rel = dst
            pages[str(page_idx)] = {
                "cache": rel.replace("\\", "/"),
                "source": str(source_path),
                "name": os.path.basename(str(source_path)),
            }
            try:
                manifest["project_dir"] = str(getattr(self, "project_dir", "") or "")
                manifest["work_project_dir"] = str(getattr(self, "work_project_dir", "") or "")
                manifest["updated_at"] = __import__("time").time()
            except Exception:
                pass
            ok = self.save_pending_clean_import_manifest(manifest, getattr(self, "work_project_dir", None))
            if ok:
                pending_base = str(getattr(self, "work_project_dir", "") or "")
                try:
                    # 폴더 mtime을 갱신해서 복구 후보 정렬에서도 최신 작업으로 잡히게 한다.
                    os.utime(pending_base, None)
                except Exception:
                    pass
                try:
                    # project.json 후보와 별도로, pending 클린본 복구 후보도 명시 기록한다.
                    self.app_options["last_pending_clean_import_dir"] = pending_base
                    save_app_options(self.app_options)
                except Exception:
                    pass
            return ok
        except Exception as e:
            try:
                self.log(f"⚠️ 클린본 pending 기록 실패: {e}")
            except Exception:
                pass
            return False

    def clear_pending_clean_import_cache(self, base_dir=None):
        try:
            root = self.pending_clean_import_root(base_dir or getattr(self, "work_project_dir", None) or getattr(self, "project_dir", None))
            if root and os.path.exists(root):
                shutil.rmtree(root, ignore_errors=True)
                return True
        except Exception:
            pass
        return False

    def is_recovery_work_project_dir(self, project_dir=None):
        try:
            p = Path(str(project_dir or getattr(self, "project_dir", "") or "")).resolve()
            roots = [self.project_cache_root(), temp_dir()]
            for root in roots:
                try:
                    r = Path(root).resolve()
                    if str(p).lower().startswith(str(r).lower()):
                        return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def apply_pending_clean_import_if_available(self, base_dir=None):
        """복구용 pending 클린본 기록이 있으면 현재 data에 다시 반영한다."""
        base_dir = base_dir or getattr(self, "project_dir", None)
        manifest = self.load_pending_clean_import_manifest(base_dir)
        pages = manifest.get("pages") if isinstance(manifest, dict) else None
        if not isinstance(pages, dict) or not pages:
            return 0
        restored = 0
        for key, entry in list(pages.items()):
            try:
                page_idx = int(key)
            except Exception:
                continue
            if page_idx < 0 or page_idx >= len(getattr(self, "paths", []) or []):
                continue
            rel = ""
            if isinstance(entry, dict):
                rel = str(entry.get("cache") or "")
            if not rel:
                continue
            try:
                path = rel if os.path.isabs(rel) else os.path.join(str(base_dir), rel.replace("/", os.sep))
            except Exception:
                path = rel
            if not path or not os.path.exists(path):
                continue
            status, _message = self.apply_clean_image_to_page(page_idx, path)
            if str(status or "").lower() == "done":
                restored += 1
        if restored:
            try:
                self.undo_break_boundary("clean_import_recovered", "클린본 pending 복구")
            except Exception:
                pass
            try:
                self.has_unsaved_changes = True
                self.update_window_title()
            except Exception:
                pass
            try:
                self.log(f"🧯 클린본 pending 복구 적용: {restored}페이지")
            except Exception:
                pass
        return restored

    def mark_page_data_dirty_explicit(self, page_idx, kind="data"):
        """현재 화면 페이지가 아니어도 특정 page_idx를 dirty로 표시한다."""
        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        try:
            if hasattr(self, "project_engine") and self.project_engine is not None:
                self.project_engine.mark_page_dirty(page_idx, str(kind or "data"))
        except Exception:
            pass
        try:
            if hasattr(self, "page_engine") and self.page_engine is not None:
                self.page_engine.mark_dirty(page_idx, str(kind or "data"))
        except Exception:
            pass
        try:
            self.has_unsaved_changes = True
            self.update_window_title()
        except Exception:
            pass

    def release_clean_background_payload_for_replace(self, page_idx, curr=None):
        """클린본 교체 전 기존 큰 이미지 참조를 먼저 끊는다.

        새 클린본을 읽고 PNG bytes로 인코딩한 뒤 기존 bg_clean에 덮어쓰면,
        교체 순간에 기존 클린본 + 새 디코딩 배열 + 새 인코딩 bytes가 같이 살아 메모리 피크가 커진다.
        그래서 교체 모드에서는 새 이미지를 읽기 전에 기존 클린본/최종 페인트 계열을 먼저 비운다.
        """
        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        if curr is None:
            curr = (getattr(self, "data", {}) or {}).get(page_idx)
        if not isinstance(curr, dict):
            return False
        had_existing = False
        for key in ("bg_clean", "final_paint", "final_paint_above", "working_source"):
            try:
                if curr.get(key) is not None:
                    had_existing = True
                curr[key] = None
            except Exception:
                pass
        try:
            self._page_image_cache_order.pop(page_idx, None)
        except Exception:
            pass
        try:
            if page_idx == int(getattr(self, "idx", -1) or -1) and hasattr(self, "view") and hasattr(self.view, "clear_final_paint_layers"):
                self.view.clear_final_paint_layers()
        except Exception:
            pass
        if had_existing:
            try:
                QPixmapCache.clear()
            except Exception:
                pass
        return had_existing

    def apply_clean_image_to_page(self, page_idx, path, *, replace_mode=False):
        curr = self.data.get(page_idx)
        if curr is None:
            try:
                curr = self.make_page_data_for_image(self.paths[page_idx])
                self.data[page_idx] = curr
            except Exception:
                return "failed", "페이지 데이터 생성 실패"

        # 기존 클린본이 있는 교체 상황에서는 새 파일을 읽기 전에 먼저 기존 payload를 끊는다.
        # 실패 시 기존 클린본은 이미 비워질 수 있지만, 대량 교체 안정성과 메모리 피크 감소를 우선한다.
        had_existing = False
        try:
            had_existing = bool(curr.get('bg_clean') is not None or curr.get('final_paint') is not None or curr.get('final_paint_above') is not None)
        except Exception:
            had_existing = False
        if replace_mode or had_existing:
            self.release_clean_background_payload_for_replace(page_idx, curr)
            try:
                __import__("gc").collect()
            except Exception:
                pass

        img = self.read_clean_image_file(path, page_idx)
        if img is None:
            self.mark_page_data_dirty_explicit(page_idx, "clean_background")
            return "failed", "이미지 읽기 실패"
        encoded = None
        try:
            encoded = self.encode_np_image_to_png_bytes(img)
            curr['bg_clean'] = encoded if encoded is not None else img
            curr['final_paint'] = None
            curr['final_paint_above'] = None
            curr['working_source'] = None
            self.mark_page_data_dirty_explicit(page_idx, "clean_background")
        finally:
            # img는 원본 디코딩 배열이라 대량 클린본 불러오기에서 바로 끊어주는 게 안전하다.
            # encoded는 curr['bg_clean']에 들어간 bytes 참조만 남기고 지역 참조는 제거한다.
            try:
                if encoded is not None:
                    img = None
            except Exception:
                pass
        try:
            if page_idx == int(getattr(self, "idx", -1) or -1) and hasattr(self.view, "clear_final_paint_layers"):
                self.view.clear_final_paint_layers()
        except Exception:
            pass
        try:
            # 클린본 자체는 bg_clean bytes로 들고 있으므로 원본 ori 캐시를 이 페이지에 유지할 필요가 없다.
            # keep_indices=[]로 두어 이미지 대량 교체 중 ori 캐시가 같이 쌓이지 않게 한다.
            self.trim_page_image_cache(keep_indices=[])
        except Exception:
            pass
        return "done", os.path.basename(str(path))

    def match_clean_image_paths_to_pages(self, paths):
        by_stem = {}
        exact_items = []
        for path in paths or []:
            try:
                stem = safe_page_file_stem(Path(str(path)).stem, fallback="")
                key = str(stem or "").casefold()
                if key:
                    exact_items.append((path, stem))
                    if key not in by_stem:
                        by_stem[key] = path
            except Exception:
                pass

        # 정확한 파일명 매칭을 먼저 등록한 뒤, 별칭 매칭은 빈 키에만 채운다.
        # 이렇게 해야 title.png와 clean_title.png가 동시에 있을 때 title.png가 우선된다.
        for path, stem in exact_items:
            for alias in self.filename_match_aliases(stem):
                key = str(alias or "").casefold()
                if key and key not in by_stem:
                    by_stem[key] = path

        matched = {}
        for page_idx in range(len(getattr(self, "paths", []) or [])):
            for cand in self.clean_image_name_candidates(page_idx):
                key = str(cand or "").casefold()
                if key in by_stem:
                    matched[page_idx] = by_stem[key]
                    break
        return matched

    def import_clean_background(self):
        """클린본 이미지를 최종결과 배경(bg_clean)으로 불러온다.

        1개 선택: 현재 페이지에 적용.
        여러 개 선택: 파일명과 페이지명을 매칭해 각 페이지에 적용.
        """
        if getattr(self, "is_batch_running", False):
            QMessageBox.information(self, self.tr_ui("일괄 작업 중"), self.tr_msg("이미 일괄 작업이 진행 중입니다.\n현재 작업이 끝난 뒤 다시 실행해 주세요."))
            return
        if not self.paths or self.idx not in self.data:
            return
        start_dir = self.ensure_subdir("clean")
        files, _ = self.get_open_file_names_logged(
            "import_clean_background",
            self,
            self.tr_ui("클린본 이미지 불러오기"),
            start_dir,
            self.tr_ui("이미지 파일") + " (*.png *.jpg *.jpeg *.webp *.bmp);;" + self.tr_ui("모든 파일") + " (*.*)",
        )
        if not files:
            return
        try:
            self.commit_current_page_ui_to_data()
        except Exception:
            pass

        # 클린본 불러오기는 이미지-heavy 작업이다.
        # 최종결과 탭(mode 4)에서 원본 탭으로 강제 이동하면 mode_chg()/ref_tab() 재렌더가 무겁게 걸릴 수 있다.
        # 따라서 실제 탭 전환은 하지 않고, 작업 중/완료 후 화면 갱신만 생략한다.
        try:
            current_mode_before_clean = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else -1
        except Exception:
            current_mode_before_clean = -1
        clean_started_from_final_mode = (current_mode_before_clean == 4)
        if clean_started_from_final_mode:
            try:
                self.log("🧼 클린본 불러오기: 최종결과 탭 전환 없이 데이터만 적용합니다.")
            except Exception:
                pass

        title = "클린본 불러오기"
        if len(files) == 1:
            target_map = {int(getattr(self, "idx", 0) or 0): files[0]}
            selected_label = self.tr_ui("현재 페이지")
        else:
            target_map = self.match_clean_image_paths_to_pages(files)
            selected_label = self.tr_ui("파일명 매칭")
            if not target_map:
                QMessageBox.warning(self, self.tr_ui("클린본 불러오기"), self.tr_ui("선택한 클린본 파일명과 일치하는 페이지를 찾지 못했습니다."))
                return

        selected_indices = list(target_map.keys())
        replace_indices = []
        for page_idx in selected_indices:
            try:
                curr = (getattr(self, "data", {}) or {}).get(int(page_idx))
                if isinstance(curr, dict) and (
                    curr.get('bg_clean') is not None
                    or curr.get('final_paint') is not None
                    or curr.get('final_paint_above') is not None
                ):
                    replace_indices.append(int(page_idx))
            except Exception:
                pass
        replace_mode = bool(replace_indices)
        if replace_mode:
            try:
                self.log(f"🧼 클린본 교체 모드: 기존 클린본 {len(replace_indices)}페이지를 먼저 해제하며 적용합니다.")
            except Exception:
                pass

        # 클린본은 이미지 대량 교체 작업이라 Undo에 올리지 않는다.
        # Undo 스냅샷 자체가 기존/신규 클린본 이미지를 모두 물고 메모리를 크게 잡아먹기 때문이다.
        changed = False

        def process_page(page_idx):
            nonlocal changed
            path = target_map.get(page_idx)
            if not path:
                return "skipped", "매칭 파일 없음"
            status, message = self.apply_clean_image_to_page(page_idx, path, replace_mode=replace_mode)
            if str(status).lower() == "done":
                changed = True
                # 무거운 ProjectStore 저장 대신, 복구에 필요한 최소 파일/맵만 즉시 기록한다.
                self.record_pending_clean_import_page(page_idx, path)
            return status, message

        result = self.run_page_queue_batch(
            title,
            "import_clean_background",
            selected_indices,
            selected_label,
            process_page,
            visual=False,
            cancellable=True,
            restore_page=False,
            save_work_cache=False,
        )
        if changed:
            try:
                self.undo_break_boundary("clean_import", "클린본 불러오기")
            except Exception:
                try:
                    self.undo_clear_all_pages("clean import")
                    self.undo_clear_project("project stack reset")
                except Exception:
                    pass
            try:
                __import__("gc").collect()
            except Exception:
                pass
        try:
            self.has_unsaved_changes = True
            self.update_window_title()
        except Exception:
            pass
        try:
            current_idx = int(getattr(self, "idx", 0) or 0)
            current_mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else -1
            # 대량 클린본 불러오기 직후에는 load()/ref_tab()/mode_chg() 전체 재구성을 하지 않는다.
            # 최종결과 탭에서 시작한 경우도 실제 탭 전환/자동 새로고침 없이 데이터만 바꾼다.
            if clean_started_from_final_mode:
                self.log("ℹ️ 클린본 불러오기 완료: 최종결과 탭 자동 새로고침은 생략했습니다. 확인이 필요하면 탭/페이지를 다시 열어 주세요.")
            elif current_idx in selected_indices and len(selected_indices) == 1 and current_mode == 4:
                # 안전상 mode_chg(4) 직접 호출은 하지 않는다. 단일 적용도 다음 표시 시 반영한다.
                self.log("ℹ️ 클린본 불러오기 완료: 최종결과 탭 즉시 새로고침은 생략했습니다. 탭/페이지를 다시 열면 반영됩니다.")
            elif current_idx in selected_indices:
                self.log("ℹ️ 클린본 불러오기 완료: 대량 작업 후 화면 전체 갱신은 생략했습니다. 탭/페이지를 다시 열면 반영됩니다.")
        except Exception:
            pass
        # 클린본 불러오기는 pending_clean_import 캐시를 별도로 남긴다.
        # 여기서 일반 작업 캐시 자동 저장을 예약하면 대량 이미지 저장이 다시 걸릴 수 있으므로 하지 않는다.

    def import_translation_current(self):
        """TXT 번역문을 불러온다.

        1개 선택: 현재 페이지에 적용.
        여러 개 선택: 파일명과 페이지명을 매칭해 각 페이지에 적용.
        """
        if not self.paths:
            return
        if self.idx not in self.data:
            return

        start_path = os.path.join(self.ensure_subdir("txt"), f"{self.get_page_stem(self.idx)}.txt")
        legacy_txt = os.path.join(self.get_output_root(), "Txt", f"{self.get_page_stem(self.idx)}.txt")
        if (not os.path.exists(start_path)) and os.path.exists(legacy_txt):
            start_path = legacy_txt

        files, _ = self.get_open_file_names_logged(
            "import_translation_txt",
            self,
            self.tr_ui("번역문 TXT 불러오기"),
            start_path,
            self.tr_ui("TXT 파일") + " (*.txt);;" + self.tr_ui("모든 파일") + " (*.*)",
        )
        if not files:
            return

        try:
            self.commit_current_page_ui_to_data()
        except Exception:
            pass

        title = "번역문 불러오기"
        if len(files) == 1:
            target_map = {int(getattr(self, "idx", 0) or 0): files[0]}
            selected_label = self.tr_ui("현재 페이지")
        else:
            target_map = self.match_translation_txt_paths_to_pages(files)
            selected_label = self.tr_ui("파일명 매칭")
            if not target_map:
                QMessageBox.warning(self, self.tr_ui("번역문 불러오기"), self.tr_ui("선택한 번역문 파일명과 일치하는 페이지를 찾지 못했습니다."))
                return

        selected_indices = list(target_map.keys())
        undo_rec = self.make_batch_page_data_undo_record(title, selected_indices)
        changed = False
        total_count = 0

        def process_page(page_idx):
            nonlocal changed, total_count
            curr = self.data.get(page_idx)
            if not curr or not curr.get('data'):
                return "skipped", "텍스트 데이터 없음"
            path = target_map.get(page_idx)
            if not path:
                return "skipped", "매칭 파일 없음"
            valid_ids = [str(x.get('id', n + 1)) for n, x in enumerate(curr.get('data', []))]
            if not valid_ids:
                return "skipped", "불러올 텍스트 번호 없음"
            trans_map = self.parse_translation_txt(path, valid_ids)
            if not trans_map:
                return "skipped", "맞는 텍스트 번호 없음"
            count = self.apply_translation_map_to_page(page_idx, trans_map)
            if count <= 0:
                return "skipped", "변경된 번역문 없음"
            changed = True
            total_count += count
            return "done", f"{count}개 적용"

        result = self.run_page_queue_batch(title, "import_translation", selected_indices, selected_label, process_page, visual=False, cancellable=True)

        if changed:
            try:
                self.undo_push_project(undo_rec)
            except Exception:
                pass
        try:
            self.ref_tab()
            if self.cb_mode.currentIndex() == 4:
                self.mode_chg(4)
        except Exception:
            pass
        try:
            self.schedule_deferred_auto_save_project(200)
        except Exception:
            self.auto_save_project()
        self.log(f"📥 번역문 불러오기 완료: {total_count}개")

    def import_translation_batch(self):
        """구버전 호환용 래퍼.

        별도 '일괄 번역문 불러오기' 메뉴는 제거되었고,
        이제 '번역문 불러오기'의 다중 파일 선택으로 같은 작업을 처리한다.
        """
        return self.import_translation_current()


    def clear_translation_current(self):
        """현재 페이지의 번역문 칸을 모두 비운다."""
        if not self.paths or self.idx not in self.data:
            return

        self.commit_current_page_ui_to_data()
        curr = self.data.get(self.idx)
        if not curr or not curr.get('data'):
            self.log("⚠️ 지울 번역문이 없습니다.")
            return

        undo_rec = self.make_project_undo_record("번역문 내용 지우기")
        count = 0
        for item in curr.get('data', []):
            if str(item.get('translated_text', '') or ''):
                item['translated_text'] = ''
                try:
                    self.shrink_text_rect_to_content(item)
                except Exception:
                    pass
                count += 1

        if count:
            self.undo_push_project(undo_rec)
        self.ref_tab()
        if self.cb_mode.currentIndex() == 4:
            self.mode_chg(4)
        self.auto_save_project()
        self.log(f"🧹 번역문 내용 지우기 완료: {count}개")

    def clear_translation_batch(self):
        """선택한 페이지의 번역문 칸을 모두 비운다."""
        if not self.paths:
            return

        title = "선택 맵 번역문 지우기"
        selected_indices, selected_label = self.choose_batch_page_indices_for_context(title, "clear_translation")
        if selected_indices is None:
            self.log("↩️ 선택 맵 번역문 지우기 취소")
            return

        self.commit_current_page_ui_to_data()

        def process_page(page_idx):
            curr = self.data.get(page_idx)
            if not curr or not curr.get('data'):
                return "skipped", "텍스트 데이터 없음"
            page_count = 0
            for item in curr.get('data', []):
                if str(item.get('translated_text', '') or ''):
                    item['translated_text'] = ''
                    try:
                        self.shrink_text_rect_to_content(item)
                    except Exception:
                        pass
                    page_count += 1
            if page_count <= 0:
                return "skipped", "지울 번역문 없음"
            return "done", f"{page_count}개 삭제"

        result = self.run_page_queue_batch(title, "clear_translation", selected_indices, selected_label, process_page, visual=False, cancellable=True)
        try:
            self.ref_tab()
            if self.cb_mode.currentIndex() == 4:
                self.mode_chg(4)
        except Exception:
            pass



    def clear_masks_for_removed_items(self, curr, removed_items):
        if not curr or not removed_items:
            return
        mask_keys = ['mask_merge', 'mask_inpaint', 'mask_merge_off', 'mask_inpaint_off']
        for item in removed_items:
            try:
                x, y, w, h = [int(v) for v in item.get('rect', [0, 0, 0, 0])]
            except Exception:
                continue
            for key in mask_keys:
                m = curr.get(key)
                if not isinstance(m, np.ndarray):
                    continue
                yy1 = max(0, y)
                yy2 = min(m.shape[0], y + h)
                xx1 = max(0, x)
                xx2 = min(m.shape[1], x + w)
                if yy2 > yy1 and xx2 > xx1:
                    m[yy1:yy2, xx1:xx2] = 0

    def clean_text_for_page(self, page_idx):
        curr = self.data.get(page_idx)
        if not curr or 'data' not in curr:
            return 0
        old_items = list(curr.get('data', []))
        removed = [x for x in old_items if not x.get('use_inpaint', True)]
        kept = [x for x in old_items if x.get('use_inpaint', True)]
        if not removed:
            return 0

        self.clear_masks_for_removed_items(curr, removed)
        for n, item in enumerate(kept, 1):
            item['id'] = n
        curr['data'] = kept
        return len(removed)

    def clean_text_current(self):
        if not self.paths or self.idx not in self.data:
            return
        self.commit_current_page_ui_to_data()
        removed_count = sum(1 for x in self.data[self.idx].get('data', []) if not x.get('use_inpaint', True))
        if removed_count <= 0:
            self.log("🧹 There are no unchecked items to delete." if self.ui_language == LANG_EN else "🧹 삭제할 체크 해제 항목이 없습니다.")
            return
        if self.ui_language == LANG_EN:
            msg = f"Delete {removed_count} unchecked text item(s) and reorder IDs?\nThe masks for those text areas will also be cleared."
        else:
            msg = f"체크 해제된 텍스트 {removed_count}개를 삭제하고 번호를 재정렬할까요?\n해당 텍스트 영역의 마스크도 함께 지워집니다."
        ans = QMessageBox.question(
            self,
            self.tr_ui("텍스트 정리"),
            msg,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        undo_rec = self.make_project_undo_record("텍스트 정리")
        removed = self.clean_text_for_page(self.idx)
        if removed:
            self.undo_push_project(undo_rec)
        self.ref_tab()
        self.mode_chg(self.cb_mode.currentIndex())
        self.log((f"🧹 Clean text complete: {removed} items deleted / IDs reordered" if self.ui_language == LANG_EN else f"🧹 텍스트 정리 완료: {removed}개 삭제 / 번호 재정렬"))
        self.auto_save_project()

    def clean_text_batch(self):
        if not self.paths:
            return
        title = "일괄 텍스트 정리"
        selected_indices, selected_label = self.choose_batch_page_indices_for_context(title, "clean_text")
        if selected_indices is None:
            self.log("↩️ 일괄 텍스트 정리 취소")
            return
        self.commit_current_page_ui_to_data()
        total_candidates = 0
        for i in selected_indices:
            curr = self.data.get(i)
            if curr:
                total_candidates += sum(1 for x in curr.get('data', []) if not x.get('use_inpaint', True))
        if total_candidates <= 0:
            self.log("🧹 There are no unchecked items to clean in selected pages." if self.ui_language == LANG_EN else "🧹 선택한 페이지에 일괄 정리할 체크 해제 항목이 없습니다.")
            return
        if self.ui_language == LANG_EN:
            msg = f"Delete {total_candidates} unchecked text item(s) in selected pages and reorder IDs?\nThe masks for those text areas will also be cleared."
        else:
            msg = f"선택한 페이지에서 체크 해제된 텍스트 {total_candidates}개를 삭제하고 번호를 재정렬할까요?\n해당 텍스트 영역의 마스크도 함께 지워집니다."
        ans = QMessageBox.question(self, self.tr_ui(title), msg)
        if ans != QMessageBox.StandardButton.Yes:
            return

        def process_page(i):
            removed = self.clean_text_for_page(i)
            if removed <= 0:
                return "skipped", "삭제할 체크 해제 항목 없음"
            return "done", f"{removed}개 삭제"

        result = self.run_page_queue_batch(title, "clean_text", selected_indices, selected_label, process_page, visual=False, cancellable=True)
        try:
            self.ref_tab()
            self.mode_chg(self.cb_mode.currentIndex())
        except Exception:
            pass



    def bg_clean_to_np_image(self, bg):
        """bg_clean 값을 화면/마스크 작업용 OpenCV 이미지(BGR np.ndarray)로 변환한다."""
        if bg is None:
            return None

        try:
            if isinstance(bg, np.ndarray):
                return bg.copy()

            if isinstance(bg, (bytes, bytearray)):
                arr = np.frombuffer(bg, np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                return img.copy() if img is not None else None

            if isinstance(bg, str) and os.path.exists(bg):
                arr = np.fromfile(bg, np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                return img.copy() if img is not None else None
        except Exception:
            return None

        return None

    def get_real_original_image(self, page_idx):
        """프로젝트 images 폴더에 있는 실제 원본 파일을 다시 읽는다."""
        if page_idx < 0 or page_idx >= len(self.paths):
            return None
        try:
            return cv2.imdecode(np.fromfile(self.paths[page_idx], np.uint8), 1)
        except Exception:
            return None

    def normalize_image_to_original_size(self, page_idx, img):
        """
        인페인팅 결과 이미지를 프로젝트 원본 해상도에 맞춘다.

        일부 인페인팅 API는 결과 해상도를 바꿔서 반환할 수 있다.
        이 상태로 다시 인페인팅하면 기존 마스크/텍스트 좌표와 크기가 어긋날 수 있으므로
        툴 내부 기준 이미지는 항상 원본 해상도에 맞춘다.
        """
        if img is None:
            return None

        ref = self.get_real_original_image(page_idx)
        if ref is None:
            return img

        rh, rw = ref.shape[:2]
        h, w = img.shape[:2]
        if (h, w) == (rh, rw):
            return img

        try:
            resized = cv2.resize(img, (rw, rh), interpolation=cv2.INTER_CUBIC)
            self.log(f"↔️ 인페인팅 결과 해상도 보정: {w}x{h} → {rw}x{rh}")
            return resized
        except Exception:
            return img

    def encode_np_image_to_png_bytes(self, img):
        if img is None:
            return None
        try:
            ok, buf = cv2.imencode(".png", img)
            if ok:
                return buf.tobytes()
        except Exception:
            pass
        return None

    def set_working_source_image(self, curr, img, page_idx=None):
        """인페인팅/최종 브러시/클린본 반영 후 '원본 탭 기준 이미지'로 쓸 작업중 소스를 저장한다."""
        if curr is None or img is None:
            return
        encoded = self.encode_np_image_to_png_bytes(img)
        curr['working_source'] = encoded if encoded is not None else img
        curr['use_inpainted_as_source'] = True
        curr['ori'] = img.copy() if isinstance(img, np.ndarray) else img
        try:
            if page_idx is None:
                page_idx = self.idx if hasattr(self, 'idx') else None
            if page_idx is not None:
                self.touch_page_image_cache(int(page_idx))
                self.trim_page_image_cache(keep_indices=[int(page_idx)])
        except Exception:
            pass

    def write_np_image_as_inpaint_source(self, page_idx, img):
        """현재 기준 이미지를 인페인팅 입력 파일로 저장한다. Windows 한글 경로 안전 처리."""
        if img is None:
            return None

        clean_dir = self.ensure_subdir("clean")
        out_path = os.path.join(clean_dir, f"inpaint_source_{page_idx + 1:04d}.png")

        try:
            ok, buf = cv2.imencode(".png", img)
            if not ok:
                self.log("⚠️ 인페인팅 기준 이미지 인코딩 실패")
                return None

            # cv2.imwrite는 Windows 한글 경로에서 실패할 수 있어 np.tofile로 저장한다.
            buf.tofile(out_path)

            if not os.path.exists(out_path) or os.path.getsize(out_path) <= 0:
                self.log("⚠️ 인페인팅 기준 이미지 파일 내보내기 실패")
                return None

            return out_path
        except Exception as e:
            self.log(f"⚠️ 인페인팅 기준 이미지 저장 오류: {e}")
            return None

    def normalize_inpaint_mask_to_input_image(self, input_path, mask):
        """인페인팅 입력 이미지와 마스크 크기가 다르면 마스크를 입력 이미지 크기에 맞춘다."""
        if mask is None:
            return None

        try:
            img = cv2.imdecode(np.fromfile(input_path, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return mask

            ih, iw = img.shape[:2]
            mh, mw = mask.shape[:2]
            if (mh, mw) == (ih, iw):
                return mask

            fixed = cv2.resize(mask, (iw, ih), interpolation=cv2.INTER_NEAREST)
            self.log((f"↔️ Inpaint mask size normalized: {mw}x{mh} → {iw}x{ih}" if self.ui_language == LANG_EN else f"↔️ 인페인팅 마스크 해상도 보정: {mw}x{mh} → {iw}x{ih}"))
            return fixed
        except Exception:
            return mask

    def get_source_display_image(self, page_idx):
        """
        원본/분석/마스크 탭에서 실제로 보여줄 기준 이미지.

        use_inpainted_as_source=True면 프로젝트 내부의 작업중 원본(working_source)을 우선 사용한다.
        working_source는 "인페인팅을 원본으로"와 "최종 브러시를 원본으로"가 공유하는 최신 기준 파일이다.
        """
        curr = self.data.get(page_idx, {})

        if curr.get('use_inpainted_as_source'):
            if curr.get('working_source') is None and (curr.get('working_source_path') or curr.get('clean_path')):
                try:
                    self.ensure_page_runtime_loaded(page_idx, include_ori=False, include_heavy=True, include_masks=False)
                except Exception:
                    pass
            img = self.bg_clean_to_np_image(curr.get('working_source'))
            if img is not None:
                img = self.normalize_image_to_original_size(page_idx, img)
                curr['ori'] = img.copy()
                try:
                    self.touch_page_image_cache(page_idx)
                    self.trim_page_image_cache(keep_indices=[page_idx])
                except Exception:
                    pass
                return curr['ori']

            img = self.bg_clean_to_np_image(curr.get('bg_clean'))
            if img is not None:
                img = self.normalize_image_to_original_size(page_idx, img)
                self.set_working_source_image(curr, img, page_idx=page_idx)
                try:
                    self.touch_page_image_cache(page_idx)
                    self.trim_page_image_cache(keep_indices=[page_idx])
                except Exception:
                    pass
                return curr['ori']

        img = curr.get('ori')
        if img is None:
            img = self.get_real_original_image(page_idx)
            if img is not None:
                curr['ori'] = img
                try:
                    self.touch_page_image_cache(page_idx)
                    self.trim_page_image_cache(keep_indices=[page_idx])
                except Exception:
                    pass
        return img

    def get_inpainting_input_path(self, page_idx):
        curr = self.data.get(page_idx, {})
        if curr.get('use_inpainted_as_source'):
            # 덧칠 모드에서는 현재 원본 탭에 표시되는 이미지(curr['ori'])를 그대로 입력으로 쓴다.
            # bg_clean을 다시 직접 쓰면, 최신 결과와 표시 기준이 엇갈릴 수 있다.
            img = self.get_source_display_image(page_idx)
            src = self.write_np_image_as_inpaint_source(page_idx, img)
            if src:
                return src
            self.log("⚠️ Failed to save the inpaint source image. Using the real original image instead." if self.ui_language == LANG_EN else "⚠️ 인페인팅 기준 이미지 내보내기 실패. 실제 원본 이미지로 진행합니다.")
        return self.paths[page_idx]

    def use_inpainted_as_source(self):
        """구버전 메뉴/단축키 호환: 인페인팅 결과뿐 아니라 현재 최종결과 배경을 작업용 원본으로 쓴다."""
        if hasattr(self, "use_final_background_as_source"):
            return self.use_final_background_as_source()

        curr = self.data.get(self.idx)
        if not curr:
            return
        if not curr.get('bg_clean'):
            QMessageBox.warning(self, self.tr_ui("인페인팅 결과 없음"), self.tr_ui("먼저 인페인팅된 이미지가 있어야 원본으로 가져올 수 있습니다."))
            return

        img = self.bg_clean_to_np_image(curr.get('bg_clean'))
        if img is None:
            QMessageBox.warning(self, self.tr_ui("이미지 변환 실패"), self.tr_ui("인페인팅 결과 이미지를 원본 탭에 표시할 수 없습니다."))
            return

        # 실제 원본 파일은 건드리지 않고, 프로젝트 내부 작업중 원본(working_source)에 저장한다.
        img = self.normalize_image_to_original_size(self.idx, img)
        self.set_working_source_image(curr, img, page_idx=self.idx)
        self.log("🔁 Inpaint result has been imported as the working source image for the Original tab." if self.ui_language == LANG_EN else "🔁 인페인팅 결과를 원본 탭의 작업중 기준 이미지로 가져왔습니다.")
        self.auto_save_project()
        self.mode_chg(self.cb_mode.currentIndex())

    def restore_original_source_to_page(self, page_idx):
        """한 페이지의 작업용 원본을 실제 원본 이미지로 되돌린다."""
        curr = self.data.get(page_idx)
        if not curr:
            return "skipped", "페이지 데이터 없음"
        if not curr.get('use_inpainted_as_source') and curr.get('working_source') is None:
            return "skipped", "이미 실제 원본 상태"
        curr['use_inpainted_as_source'] = False
        curr['working_source'] = None
        real_ori = self.get_real_original_image(page_idx)
        if real_ori is not None:
            curr['ori'] = real_ori
            try:
                self.touch_page_image_cache(page_idx)
                self.trim_page_image_cache(keep_indices=[page_idx])
            except Exception:
                pass
        try:
            self.mark_page_data_dirty_explicit(page_idx, "restore_original_source")
        except Exception:
            pass
        return "done", "실제 원본으로 복구"

    def restore_original_source(self):
        if getattr(self, "is_batch_running", False):
            QMessageBox.information(self, self.tr_ui("일괄 작업 중"), self.tr_msg("이미 일괄 작업이 진행 중입니다.\n현재 작업이 끝난 뒤 다시 실행해 주세요."))
            return
        if not getattr(self, "paths", None):
            return

        title = "원본으로 돌아가기"
        selected_indices, selected_label = self.choose_batch_page_indices_for_context(title, "restore_original_source")
        if selected_indices is None:
            self.log("↩️ " + self.tr_ui("원본으로 돌아가기") + " " + self.tr_ui("취소"))
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

        # 이미지/원본 기준 대량 변경은 Undo 스냅샷과 작업 캐시 저장을 끊어 메모리 폭증을 막는다.
        undo_rec = self.make_batch_page_data_undo_record(title, selected_indices) if single_current else None
        changed = False

        def process_page(page_idx):
            nonlocal changed
            status, message = self.restore_original_source_to_page(page_idx)
            if str(status).lower() == "done":
                changed = True
            return status, message

        result = self.run_page_queue_batch(
            title,
            "restore_original_source",
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
                    self.undo_apply_boundary("restore_original_source", title, selected_page_indices=selected_indices)
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
        # 정식 반영은 사용자가 [프로젝트 내보내기]을 눌렀을 때 처리한다.
        try:
            if single_current:
                self.mode_chg(current_mode if current_mode >= 0 else self.cb_mode.currentIndex())
            elif current_idx in set(int(i) for i in (selected_indices or [])):
                self.log("ℹ️ 원본으로 돌아가기 완료: 대량 이미지 작업 후 화면 전체 갱신은 생략했습니다. 탭/페이지를 다시 열면 반영됩니다.")
        except Exception:
            pass
        self.log("↩️ " + ("The Original tab base image has been restored to the real original image." if self.ui_language == LANG_EN else "원본 탭의 기준 이미지를 실제 원본으로 되돌렸습니다."))

    def restart_engine(self, show_error=True):
        apply_settings_to_config(self.api_settings)

        try:
            self.engine = MangaProcessEngine()
            if show_error and hasattr(self, "log_w"):
                self.log("🔧 Engine restarted" if self.ui_language == LANG_EN else "🔧 엔진 재시동 완료")
            return True
        except Exception as e:
            self.engine = None
            print(f"Engine Init Error: {e}")
            if show_error:
                QMessageBox.warning(
                    self,
                    self.tr_ui("엔진 초기화 실패"),
                    self.tr_msg("API 설정이 비어 있거나 잘못되어 엔진을 시작하지 못했습니다.\n"
                    "[옵션 > API 관리]에서 키를 저장한 뒤 다시 시도해주세요.\n\n") + f"{self.tr_ui('오류')}: {e}"
                )
            return False

    def ensure_engine_ready(self):
        if self.engine is not None:
            return True

        QMessageBox.warning(
            self,
            self.tr_ui("API 설정 필요"),
            self.tr_msg("엔진이 아직 준비되지 않았습니다.\n[옵션 > API 관리]에서 키를 저장해주세요.")
        )
        return False

    def bring_to_front(self):
        """두 번째 실행 요청이 들어왔을 때 현재 창을 앞으로 가져온다."""
        self.force_app_focus(reason="single-instance")

    def force_app_focus(self, reason="external-open", log_once=False):
        """
        .ysbg 더블클릭 / 드래그 앤 드롭 / 외부 열기 후 창 포커스를 YSB로 되돌린다.
        Windows는 다른 프로세스가 만든 포커스 변경을 막는 경우가 있어 Qt 포커스와 Win32 포커스를 여러 번 같이 시도한다.
        """
        delays = (0, 80, 220, 450)
        for delay in delays:
            QTimer.singleShot(delay, lambda r=reason: self._force_app_focus_once(r))
        if log_once:
            try:
                if self.ui_language == LANG_EN:
                    self.log(f"🪟 Focus requested: {reason}")
                else:
                    self.log(f"🪟 창 포커스 요청: {reason}")
            except Exception:
                pass

    def _force_app_focus_once(self, reason="external-open"):
        try:
            if self.isMinimized():
                self.showNormal()
            else:
                self.show()

            try:
                self.setWindowState((self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
            except Exception:
                pass

            # Qt 기본 포커스 요청
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

            # Windows에서는 파일 더블클릭/두 번째 프로세스 전달 뒤 포커스가 탐색기나 cmd에 남는 경우가 있다.
            if sys.platform.startswith("win"):
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    hwnd = int(self.winId())
                    SW_RESTORE = 9
                    HWND_TOPMOST = -1
                    HWND_NOTOPMOST = -2
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_SHOWWINDOW = 0x0040
                    ASFW_ANY = -1
                    try:
                        user32.AllowSetForegroundWindow(ASFW_ANY)
                    except Exception:
                        pass
                    try:
                        user32.ShowWindow(hwnd, SW_RESTORE)
                    except Exception:
                        pass
                    # 포커스 제한이 걸린 환경에서도 앞으로 나오도록 topmost를 아주 짧게 토글한다.
                    try:
                        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    except Exception:
                        pass
                    try:
                        user32.BringWindowToTop(hwnd)
                    except Exception:
                        pass
                    try:
                        user32.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                    try:
                        user32.SetFocus(hwnd)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

    def has_open_project(self):
        return bool(self.project_dir or self.paths)


    def ensure_task_progress_overlay(self):
        try:
            overlay = getattr(self, "_task_progress_overlay", None)
            if overlay is None:
                overlay = CenterTaskProgressOverlay(self)
                overlay.cancelRequested.connect(self.request_current_long_task_cancel)
                self._task_progress_overlay = overlay
            return overlay
        except Exception:
            return None

    def ensure_task_alert_overlay(self):
        try:
            overlay = getattr(self, "_task_alert_overlay", None)
            if overlay is None:
                overlay = CenterTaskAlertOverlay(self)
                self._task_alert_overlay = overlay
            return overlay
        except Exception:
            return None

    def pause_task_progress_overlay_for_alert(self, detail=None):
        try:
            overlay = getattr(self, "_task_progress_overlay", None)
            if overlay is not None and overlay.isVisible():
                overlay.set_paused(True, detail=detail)
        except Exception:
            pass

    def show_task_alert_overlay(self, title="작업 알림", detail=""):
        try:
            self.pause_task_progress_overlay_for_alert(detail=detail)
            overlay = self.ensure_task_alert_overlay()
            if overlay is not None:
                overlay.show_alert(title, detail)
        except Exception:
            pass

    def _is_long_task_alert_message(self, message):
        text = str(message or "")
        if not text.strip():
            return False
        markers = ("❌", "⚠️", "오류", "에러", "실패", "Error", "ERROR", "Exception", "Traceback")
        return any(m in text for m in markers)

    def handle_long_task_message(self, message, *, current=None, total=None):
        text = str(message or "")
        try:
            self.log(text)
        except Exception:
            pass
        # 일괄 작업 중 worker 로그/진행 메시지가 들어와도 진행창 자체를 새 문구 크기로
        # 갈아엎지 않는다. 선택 페이지 큐 형식의 고정 레이아웃을 유지하고, 상세 줄만 갱신한다.
        try:
            if bool(getattr(self, "is_batch_running", False)) and hasattr(self, "batch_progress_detail"):
                cur = int(current if current is not None else (getattr(self, "_batch_progress_done", 0) or 0))
                tot = int(total if total is not None else (getattr(self, "_batch_total", 0) or 0))
                page_idx = getattr(self, "_batch_current_page_idx", None)
                if tot > 0:
                    detail = self.batch_progress_detail(getattr(self, "current_batch_mode", None), cur, tot, page_idx, text)
                    self.update_task_progress_overlay(current=cur, total=tot, detail=detail)
                    if self._is_long_task_alert_message(text):
                        self.show_task_alert_overlay("작업 알림", text)
                    return
        except Exception:
            pass
        if self._is_long_task_alert_message(text):
            self.update_task_progress_overlay(current=current, total=total, detail=text)
            self.show_task_alert_overlay("작업 알림", text)
            return
        self.update_task_progress_overlay(current=current, total=total, detail=text)

    def prepare_task_progress_overlay(self, title, detail="", total=0, cancellable=True):
        """Prepare the center progress overlay without showing it yet.

        The overlay should not appear while pre-flight validation dialogs are still
        possible.  It is displayed lazily on the first worker progress/log signal,
        which means a missing key / confirmation / early alert does not leave a
        fake progress panel on screen.
        """
        try:
            self._pending_task_progress_overlay = {
                "title": str(title or "작업 중"),
                "detail": str(detail or ""),
                "total": int(total or 0) if str(total or "").strip() else 0,
                "cancellable": bool(cancellable),
            }
            self.ensure_task_progress_overlay()
        except Exception:
            self._pending_task_progress_overlay = None

    def show_task_progress_overlay(self, title, detail="", total=0, cancellable=True):
        try:
            self._pending_task_progress_overlay = None
            overlay = self.ensure_task_progress_overlay()
            if overlay is None:
                return
            # 진행 중인 창이 이미 있으면 새로 show/reset하지 않고 같은 창에서 내용만 바꾼다.
            if overlay.isVisible():
                overlay.update_task(current=None, total=total, detail=detail)
                try:
                    overlay.title_label.setText(str(title or "작업 중"))
                    overlay.cancel_btn.setVisible(bool(cancellable))
                    overlay.note_label.setVisible(bool(cancellable))
                except Exception:
                    pass
            else:
                overlay.show_task(title, detail, total=total, cancellable=cancellable)
        except Exception:
            pass

    def update_task_progress_overlay(self, current=None, total=None, detail=None):
        try:
            overlay = getattr(self, "_task_progress_overlay", None)
            pending = getattr(self, "_pending_task_progress_overlay", None)
            if (overlay is None or not overlay.isVisible()) and pending:
                overlay = self.ensure_task_progress_overlay()
                if overlay is not None:
                    show_detail = str(detail if detail is not None else pending.get("detail", ""))
                    show_total = total if total is not None else pending.get("total", 0)
                    overlay.show_task(
                        pending.get("title", "작업 중"),
                        show_detail,
                        total=show_total,
                        cancellable=pending.get("cancellable", True),
                    )
                    self._pending_task_progress_overlay = None
            if overlay is not None and overlay.isVisible():
                overlay.update_task(current=current, total=total, detail=detail)
        except Exception:
            pass

    def hide_task_progress_overlay(self):
        try:
            self._pending_task_progress_overlay = None
            overlay = getattr(self, "_task_progress_overlay", None)
            if overlay is not None:
                overlay.hide()
            alert = getattr(self, "_task_alert_overlay", None)
            if alert is not None:
                alert.hide()
        except Exception:
            pass

    def request_current_long_task_cancel(self):
        """Cancel button handler for the center progress overlay.

        Long OCR/API/local-model calls cannot always be interrupted in the middle of
        the current request.  Workers stop before the next page/chunk/step.
        """
        self._long_task_cancel_requested = True
        worker = None
        for name in ("translation_worker", "bw", "iw", "w"):
            try:
                candidate = getattr(self, name, None)
            except Exception:
                candidate = None
            if candidate is not None and hasattr(candidate, "stop"):
                worker = candidate
                try:
                    candidate.stop()
                except Exception:
                    pass
        try:
            if getattr(self, "_active_long_task_kind", "") == "save":
                detail = "취소 요청됨. 현재 저장 항목이 끝난 뒤 중단됩니다."
                log_text = "⏹️ 내보내기 취소 요청됨: 현재 저장 항목이 끝난 뒤 중단됩니다."
            elif getattr(self, "_active_long_task_kind", "") == "open_extract":
                detail = "취소 요청됨. 현재 압축 해제 항목이 끝난 뒤 중단됩니다."
                log_text = "⏹️ YSBG 열기 취소 요청됨: 현재 압축 해제 항목이 끝난 뒤 중단됩니다."
            else:
                detail = "취소 요청됨. 현재 페이지 작업이 끝난 뒤 중단됩니다."
                log_text = "⏹️ 취소 요청됨. 현재 페이지 작업이 끝난 뒤 중단됩니다."
        except Exception:
            detail = "취소 요청됨. 현재 페이지 작업이 끝난 뒤 중단됩니다."
            log_text = "⏹️ 취소 요청됨: 현재 페이지 작업이 끝난 뒤 중단됩니다."
        self.update_task_progress_overlay(detail=detail)
        try:
            self.log(log_text)
        except Exception:
            pass

    def busy_reason_text(self, reason=""):
        reason = str(reason or "").strip()
        if reason:
            return reason
        return "Working..." if getattr(self, "ui_language", LANG_KO) == LANG_EN else "작업 중"

    def begin_busy_state(self, reason="작업 중"):
        """긴 내부 작업 중에는 Wait Cursor와 UI 잠금을 걸어 중복 클릭을 막는다."""
        try:
            if not hasattr(self, "_busy_counter"):
                self._busy_counter = 0
            if not hasattr(self, "_busy_reason_stack"):
                self._busy_reason_stack = []
            self._busy_counter += 1
            self._busy_reason_stack.append(self.busy_reason_text(reason))
            if self._busy_counter > 1:
                QApplication.processEvents()
                return

            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            except Exception:
                pass

            widgets = []
            try:
                cw = self.centralWidget()
                if cw is not None:
                    widgets.append(cw)
            except Exception:
                pass
            try:
                mb = self.menuBar()
                if mb is not None:
                    widgets.append(mb)
            except Exception:
                pass
            try:
                for tb in self.findChildren(QToolBar):
                    widgets.append(tb)
            except Exception:
                pass

            self._busy_widgets = []
            for w in widgets:
                try:
                    self._busy_widgets.append((w, bool(w.isEnabled())))
                    w.setEnabled(False)
                except Exception:
                    pass

            try:
                self.setCursor(Qt.CursorShape.WaitCursor)
            except Exception:
                pass

            text = self._busy_reason_stack[-1] if self._busy_reason_stack else self.busy_reason_text(reason)
            self.log(
                f"⏳ Busy: {text} / UI locked"
                if getattr(self, "ui_language", LANG_KO) == LANG_EN else
                f"⏳ 작업 중: {text} / UI 잠금"
            )
            QApplication.processEvents()
        except Exception:
            pass

    def end_busy_state(self, reason=""):
        """begin_busy_state()로 잠근 UI와 커서를 복구한다."""
        try:
            if not hasattr(self, "_busy_counter"):
                self._busy_counter = 0
            if self._busy_counter <= 0:
                self._busy_counter = 0
                return

            self._busy_counter -= 1
            try:
                if getattr(self, "_busy_reason_stack", None):
                    self._busy_reason_stack.pop()
            except Exception:
                pass

            if self._busy_counter > 0:
                QApplication.processEvents()
                return

            for w, enabled in reversed(getattr(self, "_busy_widgets", []) or []):
                try:
                    w.setEnabled(enabled)
                except Exception:
                    pass
            self._busy_widgets = []

            try:
                self.unsetCursor()
            except Exception:
                pass
            try:
                while QApplication.overrideCursor() is not None:
                    QApplication.restoreOverrideCursor()
            except Exception:
                pass

            text = self.busy_reason_text(reason)
            self.hide_task_progress_overlay()
            self.log(
                f"✅ Busy finished: {text} / UI unlocked"
                if getattr(self, "ui_language", LANG_KO) == LANG_EN else
                f"✅ 작업 완료: {text} / UI 잠금 해제"
            )
            QApplication.processEvents()
        except Exception:
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

    def guard_project_action(self, action_name="프로젝트 작업"):
        """일괄 작업 중에는 프로젝트 열기/저장/위치 변경 같은 구조 변경 동작을 막는다."""
        if getattr(self, "is_batch_running", False):
            QMessageBox.information(
                self,
                self.tr_ui("일괄 작업 중"),
                self.tr_msg(f"현재 일괄 작업이 진행 중입니다.\n{action_name}은(는) 일괄 작업이 끝난 뒤 다시 시도해 주세요."),
            )
            self.log(f"⛔ 일괄 작업 중 차단됨: {action_name}")
            return False
        return True

    def set_project_action_interlock(self, locked):
        """일괄 작업 중 사용하면 위험한 프로젝트 관련 메뉴를 비활성화한다."""
        for key in (
            "project_new",
            "project_open",
            "project_open_json",
            "project_save",
            "project_save_as",
            "option_workspace_location",
            "option_workspace_reset_default",
        ):
            action = self.actions.get(key) if hasattr(self, "actions") else None
            if action is not None:
                action.setEnabled(not locked)

    def close_current_project_state_for_switch(self):
        """새 프로젝트를 열기 전 현재 프로젝트의 화면/프리뷰 상태까지 정리한다."""
        try:
            if hasattr(self, "stop_progressive_page_loader"):
                self.stop_progressive_page_loader()
        except Exception:
            pass
        try:
            if hasattr(self, "_maker_preview_new_lifecycle_token"):
                self._maker_preview_new_lifecycle_token("project_switch")
        except Exception:
            pass
        try:
            if hasattr(self, "_clear_maker_preview_display_state"):
                self._clear_maker_preview_display_state(reason="project_switch")
        except Exception:
            pass
        try:
            self.cleanup_work_cache()
        except Exception:
            pass
        try:
            self.delete_temp_project_if_needed()
        except Exception:
            pass
        self.has_unsaved_changes = False

    def confirm_close_current_project_for_open(self, source_text=""):
        """외부 .ysbg 열기 요청이 들어왔을 때 현재 프로젝트를 닫을지 확인한다."""
        if not self.has_open_project():
            return True
        title = self.tr_ui("프로젝트 열기")
        message = self.tr_msg(
            "현재 열려있는 프로젝트를 닫고 새 프로젝트를 열까요?\n\n"
            "[예] 기존 프로젝트를 닫고 새 프로젝트를 엽니다.\n"
            "[아니오] 열기를 취소합니다."
        )
        if source_text:
            message += f"\n\n{self.tr_ui('열려고 하는 파일:')}\n{source_text}"
        ans = styled_question(
            self,
            title,
            message,
            default_yes=False,
        )
        if ans != QMessageBox.StandardButton.Yes:
            self.log("↩️ 외부 프로젝트 열기 취소")
            return False

        # 쯔꾸르붕이에는 별도 저장 확인 단계가 없다.
        # 전환 전 현재 화면만 작업 데이터에 반영하고 바로 닫는다.
        self.confirm_unsaved_before_switch()
        self.close_current_project_state_for_switch()
        return True

    def setup_external_open_queue_monitor(self):
        """YSB Launcher가 기록한 .ysbg 열기 요청 큐를 감시한다."""
        try:
            self.write_external_open_runtime_info()
        except Exception:
            pass

        self._external_open_queue_timer = QTimer(self)
        self._external_open_queue_timer.setInterval(350)
        self._external_open_queue_timer.timeout.connect(self.process_external_open_queue)
        self._external_open_queue_timer.start()

        self._external_runtime_timer = QTimer(self)
        self._external_runtime_timer.setInterval(5000)
        self._external_runtime_timer.timeout.connect(self.write_external_open_runtime_info)
        self._external_runtime_timer.start()

        QTimer.singleShot(700, self.process_external_open_queue)

    def write_external_open_runtime_info(self):
        """경량 런처가 메인 앱 실행 여부를 빠르게 판단할 수 있게 pid 정보를 남긴다."""
        try:
            path = ysb_main_runtime_info_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "pid": os.getpid(),
                "exe": str(Path(sys.executable).resolve()),
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "queue": str(ysb_open_queue_path()),
            }
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception:
            pass

    def cleanup_external_open_runtime_info(self):
        """정상 종료 시 런처용 pid 정보를 정리한다. 실패해도 종료는 막지 않는다."""
        try:
            path = ysb_main_runtime_info_path()
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if int(data.get("pid") or -1) != os.getpid():
                        return
                except Exception:
                    pass
                path.unlink()
        except Exception:
            pass

    def is_fresh_external_open_payload(self, payload, max_age_sec=600):
        """오래 전에 남은 열기 큐가 재실행 때 이전 프로젝트를 다시 여는 일을 막는다."""
        try:
            t = payload.get("time_epoch")
            if t is None:
                return False
            age = time.time() - float(t)
            return 0 <= age <= float(max_age_sec)
        except Exception:
            return False

    def process_external_open_queue(self):
        """open_queue.jsonl에 쌓인 .ysbg 열기 요청을 기존 창에서 처리한다."""
        queue_path = ysb_open_queue_path()
        if not queue_path.exists():
            return
        try:
            processing_path = queue_path.with_suffix(f".processing.{os.getpid()}.{int(time.time() * 1000)}")
            try:
                queue_path.replace(processing_path)
            except FileNotFoundError:
                return
            except Exception:
                # 다른 프로세스가 쓰는 순간이면 다음 타이머에서 다시 처리한다.
                return

            try:
                raw = processing_path.read_text(encoding="utf-8", errors="replace")
            finally:
                try:
                    processing_path.unlink()
                except Exception:
                    pass

            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                if not self.is_fresh_external_open_payload(payload):
                    try:
                        self.log("🧹 오래된 외부 열기 큐 무시")
                    except Exception:
                        pass
                    continue
                command = str(payload.get("command") or "activate")
                if command == "activate":
                    self.handle_single_instance_payload({"command": "activate", "source": "launcher-queue"})
                    continue
                if command != "open":
                    continue
                path = str(payload.get("path") or "")
                if not path:
                    continue
                if not (path.lower().endswith(YSB_EXTENSION) or os.path.basename(path).lower() == PROJECT_FILENAME):
                    continue
                self.handle_single_instance_payload({"command": "open", "path": path, "source": "launcher-queue"})
        except Exception as e:
            try:
                self.log(f"⚠️ 외부 열기 큐 처리 실패: {e}")
            except Exception:
                pass

    def handle_single_instance_payload(self, payload):
        """두 번째 실행 프로세스에서 넘어온 메시지를 현재 창에서 처리한다."""
        self.force_app_focus(reason="external request")
        payload = payload or {}
        command = str(payload.get("command", "activate") or "activate")
        if command != "open":
            return
        path = str(payload.get("path", "") or "")
        if not path:
            return
        if not self.guard_project_action("외부 YSBG 파일 열기"):
            return
        if not self.confirm_close_current_project_for_open(path):
            return
        self.open_project_path(path, external_request=True)
        self.force_app_focus(reason="external file open")

    def is_supported_image_path(self, path):
        try:
            return bool(path) and Path(str(path)).suffix.lower() in IMAGE_DROP_EXTS and os.path.isfile(str(path))
        except Exception:
            return False

    def normalize_image_drop_paths(self, paths):
        out = []
        seen = set()
        for path in paths or []:
            try:
                p = os.path.abspath(str(path))
            except Exception:
                continue
            if p.lower() in seen:
                continue
            if self.is_supported_image_path(p):
                out.append(p)
                seen.add(p.lower())
        return out

    def page_original_name(self, page_idx):
        try:
            curr = self.data.get(int(page_idx), {}) if isinstance(self.data, dict) else {}
            name = curr.get("original_name") if isinstance(curr, dict) else ""
            if name:
                return str(name)
            return os.path.basename(str(self.paths[int(page_idx)]))
        except Exception:
            return f"Map{int(page_idx) + 1:03d}"

    def maker_map_tab_name_from_original(self, original, page_idx=0, include_ext=False):
        """쯔꾸르붕이 맵 탭 표시명.

        탭 앞의 1p_/2p_ 같은 작업순서 접두사는 없애되,
        RPG Maker 원본 파일명 접두사(Map001_)는 지명 식별에 필요하므로 유지한다.
        맵 순서는 하단 번호가 담당하고, 탭은 Map 파일명+지명을 담당한다.
        """
        fallback = f"Map{int(page_idx) + 1:03d}"
        raw = str(original or fallback)
        stem = safe_page_file_stem(raw, fallback=fallback)
        ext = Path(raw).suffix if include_ext else ""

        # 구버전 탭 표시명 흔적: 1p_Map001_街 -> Map001_街
        stem = re.sub(r"^\d+p_", "", stem, flags=re.IGNORECASE).strip()

        return f"{stem or fallback}{ext}"

    def page_display_name(self, page_idx, mode=None, include_ext=False):
        # 쯔꾸르붕이에서는 페이지 번호 접두사를 탭에 붙이지 않는다.
        # mode 인자는 구버전 호출 호환용으로만 받는다.
        original = self.page_original_name(page_idx)
        return self.maker_map_tab_name_from_original(original, page_idx=page_idx, include_ext=include_ext)

    def output_display_stem(self, page_idx):
        return self.page_display_name(page_idx, mode=getattr(self, "output_display_name_mode", DEFAULT_PAGE_DISPLAY_MODE), include_ext=False)

    def path_for_output_display(self, page_idx):
        """구버전 호환용 표시명 경로. 실제 출력은 output_display_stem을 별도로 넘긴다."""
        try:
            src = str(self.paths[int(page_idx)])
            ext = Path(src).suffix or ".png"
            return os.path.join(os.path.dirname(os.path.abspath(src)), self.output_display_stem(page_idx) + ext)
        except Exception:
            return os.path.join(self.get_output_root(), self.output_display_stem(page_idx) + ".png")

    def output_format_label_pairs(self):
        return [
            ("png", "PNG"),
            ("jpg", "JPG"),
            ("webp", "WebP"),
        ]

    def output_text_render_quality_label_pairs(self):
        return [
            ("normal", self.tr_ui("기본 렌더 (1x)")),
            ("2x", self.tr_ui("고품질 렌더 (2x)")),
            ("3x", self.tr_ui("최고품질 렌더 (3x)")),
            ("4x", self.tr_ui("실험적 렌더 (4x)")),
        ]

    def current_output_text_render_quality(self):
        return normalize_output_text_render_quality(getattr(self, "output_text_render_quality", DEFAULT_OUTPUT_TEXT_RENDER_QUALITY))

    def current_output_text_render_scale(self):
        return output_text_render_scale(self.current_output_text_render_quality())

    def current_output_image_format(self):
        return normalize_output_image_format(getattr(self, "output_image_format", DEFAULT_OUTPUT_IMAGE_FORMAT))

    def current_clean_image_format(self):
        return normalize_output_image_format(getattr(self, "clean_image_format", DEFAULT_OUTPUT_IMAGE_FORMAT))

    def current_output_image_quality(self):
        return normalize_output_image_quality(getattr(self, "output_image_quality", DEFAULT_OUTPUT_IMAGE_QUALITY))

    def current_clean_image_quality(self):
        return normalize_output_image_quality(getattr(self, "clean_image_quality", DEFAULT_OUTPUT_IMAGE_QUALITY))

    def output_result_file_path(self, output_stem):
        ext = output_image_extension(self.current_output_image_format())
        return os.path.join(self.get_output_root(), "result", f"Result_{safe_page_file_stem(output_stem, 'output')}{ext}")

    def output_clean_file_path(self, clean_stem):
        ext = output_image_extension(self.current_clean_image_format())
        return os.path.join(self.get_output_root(), "clean", f"{safe_page_file_stem(clean_stem, 'clean')}{ext}")

    def remove_output_format_variants(self, directory, stem, prefix=""):
        """출력 형식이 바뀌었을 때 같은 stem의 기존 PNG/JPG/WebP를 중복으로 남기지 않는다."""
        try:
            folder = Path(str(directory))
            if not folder.exists():
                return
            safe_stem = safe_page_file_stem(stem, "output")
            current_exts = {".png", ".jpg", ".jpeg", ".webp"}
            for ext in current_exts:
                for name in (f"{prefix}{safe_stem}{ext}",):
                    p = folder / name
                    try:
                        if p.exists() and p.is_file():
                            p.unlink()
                    except Exception:
                        pass
        except Exception:
            pass

    def ensure_page_source_path(self, page_idx):
        """원본 파일명 변경/저장 후 self.paths가 낡았을 때 images/original_name 기준으로 복구한다."""
        try:
            page_idx = int(page_idx)
        except Exception:
            return False
        if page_idx < 0 or page_idx >= len(getattr(self, "paths", []) or []):
            return False

        try:
            current = Path(str(self.paths[page_idx]))
            if current.exists():
                return True
        except Exception:
            current = None

        curr = self.data.get(page_idx, {}) if isinstance(self.data, dict) else {}
        original = curr.get("original_name") if isinstance(curr, dict) else ""
        images_dirs = []
        try:
            if self.project_dir:
                images_dirs.append(Path(str(self.project_dir)) / "images")
        except Exception:
            pass
        try:
            active = self.active_page_storage_dir()
            if active:
                images_dirs.append(Path(str(active)) / "images")
        except Exception:
            pass

        candidates = []
        if original:
            for d in images_dirs:
                candidates.append(d / str(original))

        original_stem = Path(str(original)).stem.lower() if original else ""
        for d in images_dirs:
            try:
                if not d.exists():
                    continue
                if original_stem:
                    for p in d.iterdir():
                        if p.is_file() and p.stem.lower() == original_stem:
                            candidates.append(p)
                if current is not None:
                    old_stem = current.stem.lower()
                    for p in d.iterdir():
                        if p.is_file() and p.stem.lower() == old_stem:
                            candidates.append(p)
            except Exception:
                pass

        for cand in candidates:
            try:
                if cand.exists() and cand.is_file():
                    self.paths[page_idx] = str(cand)
                    if isinstance(curr, dict):
                        curr["original_name"] = cand.name
                        self.data[page_idx] = curr
                    try:
                        self.save_project_store(self.project_store)
                    except Exception:
                        pass
                    return True
            except Exception:
                pass

        return False

    def collect_used_source_stems_for_rename(self, except_index=None):
        used = set()
        try:
            except_index = None if except_index is None else int(except_index)
        except Exception:
            except_index = None
        for i, p in enumerate(getattr(self, "paths", []) or []):
            if except_index is not None and i == except_index:
                continue
            try:
                used.add(Path(str(p)).stem.lower())
            except Exception:
                pass
            try:
                curr = self.data.get(i, {}) if isinstance(self.data, dict) else {}
                original = curr.get("original_name") if isinstance(curr, dict) else ""
                if original:
                    used.add(Path(str(original)).stem.lower())
            except Exception:
                pass
        return used

    def unique_source_rename_target(self, current_path, requested_stem, page_index):
        current = Path(str(current_path))
        folder = current.parent
        ext = current.suffix or ".png"
        base = safe_page_file_stem(requested_stem, fallback=current.stem or "image")
        used = self.collect_used_source_stems_for_rename(except_index=page_index)

        def candidate(n=None):
            stem = base if n is None else f"{base}({n})"
            return stem, folder / f"{stem}{ext}"

        stem, path = candidate(None)
        if stem.lower() not in used and (not path.exists() or str(path.resolve()).lower() == str(current.resolve()).lower()):
            return str(path), False

        for n in range(1, 10000):
            stem, path = candidate(n)
            if stem.lower() not in used and not path.exists():
                return str(path), True

        stem = f"{base}({uuid.uuid4().hex[:8]})"
        return str(folder / f"{stem}{ext}"), True

    def rename_page_source_from_tab(self, page_idx):
        return self.rename_page_source_file(page_idx)

    def rename_current_page_source_file(self):
        return self.rename_page_source_file(getattr(self, "idx", 0))

    def rename_page_source_file(self, page_idx):
        """프로젝트 내부 images 원본 파일명을 변경하고 관련 기준 이름을 갱신한다."""
        if not getattr(self, "paths", None):
            return False
        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        if page_idx < 0 or page_idx >= len(self.paths):
            return False
        if not self.guard_project_action("맵 탭 이름 변경"):
            return False

        current_path = Path(str(self.paths[page_idx]))
        if not current_path.exists():
            QMessageBox.warning(
                self,
                self.tr_ui("파일 없음"),
                f"{self.tr_ui('현재 맵의 원본 이미지를 찾을 수 없습니다.')}\n{current_path}",
            )
            return False

        current_stem = current_path.stem
        while True:
            new_stem, ok = QInputDialog.getText(
                self,
                self.tr_ui("맵 탭 이름 변경"),
                self.tr_msg("새 원본 파일명을 입력하세요.\n확장자는 현재 파일의 확장자를 유지합니다."),
                QLineEdit.EchoMode.Normal,
                current_stem,
            )
            if not ok:
                return False
            new_stem = safe_page_file_stem(Path(str(new_stem or "")).stem, fallback=current_stem)
            if not new_stem:
                continue
            if new_stem == current_stem:
                return False

            target_path, has_conflict = self.unique_source_rename_target(current_path, new_stem, page_idx)
            if has_conflict:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle(self.tr_ui("파일명 중복"))
                msg.setText(self.tr_ui("같은 이름의 원본 이미지 파일명이 이미 있습니다."))
                msg.setInformativeText(
                    f"{self.tr_ui('입력한 이름')} : {new_stem}{current_path.suffix}\n"
                    f"{self.tr_ui('자동 이름')} : {os.path.basename(target_path)}"
                )
                btn_auto = msg.addButton(self.tr_ui("자동 이름 사용"), QMessageBox.ButtonRole.AcceptRole)
                btn_retry = msg.addButton(self.tr_ui("다시 입력"), QMessageBox.ButtonRole.ActionRole)
                btn_cancel = msg.addButton(self.tr_ui("취소"), QMessageBox.ButtonRole.RejectRole)
                for _btn in (btn_auto, btn_retry, btn_cancel):
                    try:
                        _btn.setMinimumWidth(128)
                    except Exception:
                        pass
                msg.setDefaultButton(btn_retry)
                msg.setEscapeButton(btn_cancel)
                try:
                    msg.setStyleSheet(
                        self.message_box_style()
                        + "\nQMessageBox QPushButton { min-width:128px; padding:6px 14px; }"
                    )
                except Exception:
                    pass
                force_message_box_front(msg)
                msg.exec()
                clicked = msg.clickedButton()
                if clicked is btn_cancel:
                    return False
                if clicked is btn_retry:
                    current_stem = new_stem
                    continue
                # 자동 이름 사용은 target_path 그대로 진행
            break

        try:
            self.commit_current_page_ui_to_data()
            self.remember_current_view_state()
        except Exception:
            pass

        undo_rec = None
        if not getattr(self, "_project_undo_restore_lock", False):
            try:
                from ysb.core.project_structure_undo import make_rename_record
                old_name = str((self.data.get(page_idx) or {}).get("original_name") or os.path.basename(str(current_path))) if isinstance(self.data, dict) else os.path.basename(str(current_path))
                undo_rec = make_rename_record(page_idx, str(current_path), old_name, reason="원본 파일명 변경")
            except Exception:
                undo_rec = None

        new_path = Path(target_path)
        try:
            if str(current_path.resolve()).lower() == str(new_path.resolve()).lower() and str(current_path) != str(new_path):
                temp_path = current_path.with_name(f".__ysb_rename_tmp_{uuid.uuid4().hex}{current_path.suffix}")
                os.rename(str(current_path), str(temp_path))
                os.rename(str(temp_path), str(new_path))
            else:
                os.rename(str(current_path), str(new_path))
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr_ui("파일명 변경 실패"),
                f"{self.tr_ui('원본 이미지 파일명을 변경하지 못했습니다.')}\n{e}",
            )
            return False

        self.paths[page_idx] = str(new_path)
        if not isinstance(self.data, dict):
            self.data = {}
        curr = self.data.get(page_idx) or {}
        curr["original_name"] = os.path.basename(str(new_path))
        self.data[page_idx] = curr

        if undo_rec is not None:
            try:
                undo_rec["file_rename_ops"] = [{
                    "page_idx": int(page_idx),
                    "from_path": str(new_path),
                    "to_path": str(current_path),
                    "reason": "원본 파일명 변경",
                }]
                self.undo_push_project(undo_rec)
            except Exception:
                pass

        try:
            if hasattr(self, "page_tab_bar"):
                self.page_tab_bar.setTabText(page_idx, self.page_display_name(page_idx))
                self.page_tab_bar.setTabToolTip(page_idx, f"{self.tr_ui('맵')} {page_idx + 1} / {len(self.paths)}\n{self.page_original_name(page_idx)}")
        except Exception:
            pass
        try:
            if page_idx == self.idx:
                self.update_page_position_label_for_current_tab_layer()
                self.sync_page_tab_current_only()
        except Exception:
            pass
        try:
            self.schedule_deferred_auto_save_project()
        except Exception:
            self.auto_save_project()
        self.log(f"✏️ 원본 파일명 변경: {current_path.name} → {new_path.name}")
        return True

    def apply_page_tab_style(self):
        if not hasattr(self, "page_tab_container") or not hasattr(self, "page_tab_bar"):
            return
        if self.is_light_theme():
            self.page_tab_container.setStyleSheet("background:#F1ECEF; border:1px solid #DED8DC; border-radius:0px;")
            self.page_tab_bar.setStyleSheet(
                "QTabBar::tab { background:#ffffff; color:#555056; padding:6px 28px 6px 10px; border:1px solid #D1C9CE; border-bottom:1px solid #D1C9CE; border-radius:0px; min-width:82px; }"
                "QTabBar::tab:selected { background:#F5E8EA; color:#111827; font-weight:700; border-color:#C78A90; }"
                "QTabBar::tab:hover { background:#FBF5F6; color:#111827; }"
                "QTabBar::scroller { width:0px; }"
                "QTabBar QToolButton { width:0px; height:0px; max-width:0px; max-height:0px; border:0px; padding:0px; margin:0px; background:transparent; color:transparent; }"
            )
            if hasattr(self, "btn_page_tab_menu"):
                self.btn_page_tab_menu.setStyleSheet(
                    "QToolButton { background:#ffffff; color:#28262B; border:1px solid #D1C9CE; border-radius:0px; font-size:16px; font-weight:700; }"
                    "QToolButton:hover { background:#FBF5F6; border-color:#C78A90; }"
                    "QToolButton:disabled { background:#F1ECEF; color:#A39BA1; border:1px solid #D3CCD1; }"
                )
            for _btn in (getattr(self, "btn_page_scroll_left", None), getattr(self, "btn_page_scroll_right", None)):
                if _btn is not None:
                    _btn.setStyleSheet(
                        "QToolButton { background:#ffffff; color:#111827; border:1px solid #D1C9CE; border-radius:0px; font-size:14px; font-weight:900; padding:0px; }"
                        "QToolButton:hover { background:#FBF5F6; border-color:#C78A90; }"
                        "QToolButton:disabled { background:#F1ECEF; color:#A39BA1; border:1px solid #D3CCD1; }"
                    )
            if hasattr(self, "btn_page_add"):
                self.btn_page_add.setStyleSheet(
                    "QToolButton { background:#ffffff; color:#28262B; border:1px solid #D1C9CE; border-radius:0px; font-size:17px; font-weight:700; }"
                    "QToolButton:hover { background:#FBF5F6; border-color:#C78A90; }"
                    "QToolButton:disabled { background:#F1ECEF; color:#A39BA1; border:1px solid #D3CCD1; }"
                )
            try:
                self.page_tab_bar.apply_theme(True)
            except Exception:
                pass
            self.update_page_tab_scroll_buttons()
        else:
            self.page_tab_container.setStyleSheet("background:#211F23; border:1px solid #3A363B; border-radius:0px;")
            self.page_tab_bar.setStyleSheet(
                "QTabBar::tab { background:#2B282D; color:#BDB6BB; padding:6px 28px 6px 10px; border:1px solid #3A363B; border-bottom:1px solid #3A363B; border-radius:0px; min-width:82px; }"
                "QTabBar::tab:selected { background:#5B3136; color:#ffffff; font-weight:700; border-color:#C78A90; }"
                "QTabBar::tab:hover { background:#3A343A; color:#ffffff; }"
                "QTabBar::scroller { width:0px; }"
                "QTabBar QToolButton { width:0px; height:0px; max-width:0px; max-height:0px; border:0px; padding:0px; margin:0px; background:transparent; color:transparent; }"
            )
            if hasattr(self, "btn_page_tab_menu"):
                self.btn_page_tab_menu.setStyleSheet(
                    "QToolButton { background:#2B282D; color:#ffffff; border:1px solid #3A363B; border-radius:0px; font-size:16px; font-weight:700; }"
                    "QToolButton:hover { background:#3A343A; border-color:#C78A90; }"
                    "QToolButton:disabled { background:#211F23; color:#736A71; border:1px solid #373136; }"
                )
            for _btn in (getattr(self, "btn_page_scroll_left", None), getattr(self, "btn_page_scroll_right", None)):
                if _btn is not None:
                    _btn.setStyleSheet(
                        "QToolButton { background:#2B282D; color:#ffffff; border:1px solid #3A363B; border-radius:0px; font-size:14px; font-weight:900; padding:0px; }"
                        "QToolButton:hover { background:#3A343A; border-color:#C78A90; }"
                        "QToolButton:disabled { background:#211F23; color:#736A71; border:1px solid #373136; }"
                    )
            if hasattr(self, "btn_page_add"):
                self.btn_page_add.setStyleSheet(
                    "QToolButton { background:#2B282D; color:#ffffff; border:1px solid #3A363B; border-radius:0px; font-size:17px; font-weight:700; }"
                    "QToolButton:hover { background:#3A343A; border-color:#C78A90; }"
                    "QToolButton:disabled { background:#211F23; color:#736A71; border:1px solid #373136; }"
                )
            try:
                self.page_tab_bar.apply_theme(False)
            except Exception:
                pass
            self.update_page_tab_scroll_buttons()

    def scroll_page_tabs_left(self):
        self.page_tab_scroll_generation = int(getattr(self, "page_tab_scroll_generation", 0) or 0) + 1
        bar = getattr(self, "page_tab_bar", None)
        if bar is not None and hasattr(bar, "scroll_step"):
            return bar.scroll_step(-1)
        return False

    def scroll_page_tabs_right(self):
        self.page_tab_scroll_generation = int(getattr(self, "page_tab_scroll_generation", 0) or 0) + 1
        bar = getattr(self, "page_tab_bar", None)
        if bar is not None and hasattr(bar, "scroll_step"):
            return bar.scroll_step(+1)
        return False

    def update_page_tab_scroll_buttons(self):
        """커스텀 탭바에서는 내부 스크롤 버튼 보정이 필요 없다."""
        try:
            bar = getattr(self, "page_tab_bar", None)
            if bar is not None and hasattr(bar, "apply_theme"):
                bar.apply_theme(self.is_light_theme())
        except Exception:
            pass

    def schedule_current_page_tab_visible(self, center=False):
        scheduled_generation = int(getattr(self, "page_tab_scroll_generation", 0) or 0)
        def _run():
            if scheduled_generation != int(getattr(self, "page_tab_scroll_generation", 0) or 0):
                return
            self.ensure_current_page_tab_visible(center=center)
        QTimer.singleShot(0, _run)

    def ensure_current_page_tab_visible(self, center=False):
        """현재 페이지 탭이 페이지탭 박스 안에 완전히 보이도록 스크롤한다."""
        try:
            bar = getattr(self, "page_tab_bar", None)
            if bar is None or not hasattr(bar, "scroll") or not hasattr(bar, "_tabs"):
                return False
            idx = int(getattr(self, "idx", 0) or 0)
            if idx < 0 or idx >= len(bar._tabs):
                return False

            sb = bar.scroll.horizontalScrollBar()
            viewport_w = bar.scroll.viewport().width()
            tab = bar._tabs[idx]
            left = int(tab.x())
            right = int(tab.x() + tab.width())
            cur = int(sb.value())
            view_left = cur
            view_right = cur + max(1, viewport_w)

            if center:
                target = left - max(0, (viewport_w - tab.width()) // 2)
            elif left < view_left:
                target = left
            elif right > view_right:
                target = right - viewport_w
            else:
                return True

            target = max(sb.minimum(), min(sb.maximum(), int(target)))
            sb.setValue(target)
            return True
        except Exception:
            return False

    def show_current_page_full_name(self):
        """Alt+V: 현재 맵 탭 전체 이름을 누르고 있는 동안만 보여준다."""
        if not getattr(self, "paths", None):
            self.log("⚠️ 표시할 맵이 없습니다.")
            return False
        try:
            page_idx = max(0, min(int(self.idx), len(self.paths) - 1))
        except Exception:
            page_idx = 0
        text = self.page_display_name(page_idx, include_ext=True)
        try:
            bar = getattr(self, "page_tab_bar", None)
            if bar is not None and 0 <= page_idx < bar.count():
                rect = bar.tabRect(page_idx)
                anchor = bar.mapToGlobal(rect.bottomLeft()) + QPoint(0, 8)
            else:
                anchor = QCursor.pos() + QPoint(12, 12)

            html = self.native_tooltip_html("현재 맵 이름", "Alt+V", text)
            popup = getattr(self, "_page_full_name_popup", None)
            if popup is None:
                popup = QLabel(self)
                popup.setObjectName("pageFullNameOverlay")
                popup.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                popup.setTextFormat(Qt.TextFormat.RichText)
                popup.hide()
                self._page_full_name_popup = popup
            popup.setText(html)
            if self.is_light_theme():
                popup.setStyleSheet("QLabel#pageFullNameOverlay { background:#ffffff; color:#111827; border:1px solid #D1C9CE; border-radius:0px; padding:5px; }")
            else:
                popup.setStyleSheet("QLabel#pageFullNameOverlay { background:#242329; color:#ffffff; border:1px solid #555056; border-radius:0px; padding:5px; }")
            popup.adjustSize()
            local = self.mapFromGlobal(anchor)
            x = max(4, min(local.x(), max(4, self.width() - popup.width() - 4)))
            y = max(4, min(local.y(), max(4, self.height() - popup.height() - 4)))
            popup.move(x, y)
            popup.show()
            popup.raise_()
            try:
                self.audit_top_level_widgets("page_full_name_popup", throttle_ms=1000)
            except Exception:
                pass
            self._page_full_name_popup_hold_by_shortcut = True
        except Exception:
            try:
                QMessageBox.information(self, self.tr_ui("현재 맵 이름"), text)
            except Exception:
                pass
        self.log(f"🗺️ 현재 맵 이름: {text}")
        return True

    def hide_current_page_full_name(self):
        try:
            QToolTip.hideText()
        except Exception:
            pass
        try:
            popup = getattr(self, "_page_full_name_popup", None)
            if popup is not None:
                popup.hide()
        except Exception:
            pass
        self._page_full_name_popup_hold_by_shortcut = False

    def hide_page_tab_menu(self):
        try:
            old_popup = getattr(self, "_page_list_popup", None)
            if old_popup is not None and old_popup.isVisible():
                old_popup.close()
        except Exception:
            pass
        self._page_list_popup = None
        self._page_list_popup_hold_by_shortcut = False

    def show_page_tab_menu(self, hold_by_shortcut=False):
        """좌측 3선 버튼/단축키에서 현재 프로젝트의 맵 목록을 포커스 가능한 세로 목록으로 보여준다."""
        try:
            old_popup = getattr(self, "_page_list_popup", None)
            if old_popup is not None and old_popup.isVisible():
                if hold_by_shortcut:
                    self._page_list_popup_hold_by_shortcut = True
                    return
                old_popup.close()
                return
        except Exception:
            pass
        self._page_list_popup_hold_by_shortcut = bool(hold_by_shortcut)

        btn = getattr(self, "btn_page_tab_menu", None)
        anchor = btn if btn is not None else self

        popup = QFrame(self, Qt.WindowType.Popup)
        self._page_list_popup = popup
        popup.setObjectName("PageListPopup")
        popup.setMinimumWidth(260)
        try:
            if self.is_light_theme():
                popup.setStyleSheet(
                    "QFrame#PageListPopup { background:#ffffff; color:#111827; border:1px solid #D1C9CE; }"
                    "QLabel { color:#111827; font-weight:700; padding:6px 8px 2px 8px; }"
                    "QListWidget { background:#ffffff; color:#111827; border:0px; outline:0px; }"
                    "QListWidget::item { padding:6px 10px; min-height:22px; }"
                    "QListWidget::item:selected { background:#F5E8EA; color:#111827; }"
                    "QListWidget::item:hover { background:#FBF5F6; }"
                )
            else:
                popup.setStyleSheet(
                    "QFrame#PageListPopup { background:#252328; color:#ffffff; border:1px solid #3A363B; }"
                    "QLabel { color:#ffffff; font-weight:700; padding:6px 8px 2px 8px; }"
                    "QListWidget { background:#252328; color:#ffffff; border:0px; outline:0px; }"
                    "QListWidget::item { padding:6px 10px; min-height:22px; }"
                    "QListWidget::item:selected { background:#5B3136; color:#ffffff; }"
                    "QListWidget::item:hover { background:#3A343A; }"
                )
        except Exception:
            pass

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        db_mode = bool(self.is_maker_database_mode()) if hasattr(self, "is_maker_database_mode") else False
        visible_pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else list(range(len(getattr(self, "paths", []) or [])))
        title = QLabel(self.tr_ui("데이터베이스 목록" if db_mode else "맵 목록"), popup)
        layout.addWidget(title)

        page_list = QListWidget(popup)
        page_list.setUniformItemSizes(True)
        page_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        page_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        page_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        popup.page_list_widget = page_list
        layout.addWidget(page_list)

        current_page_item = None
        current_row_in_list = -1
        if not visible_pages:
            item = QListWidgetItem(self.tr_ui("데이터베이스 항목 없음" if db_mode else "맵 없음"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            page_list.addItem(item)
        else:
            try:
                current_actual = int(getattr(self, "maker_database_idx", 0) if db_mode else getattr(self, "idx", 0))
            except Exception:
                current_actual = 0
            for display_row, i in enumerate(visible_pages):
                try:
                    i = int(i)
                except Exception:
                    continue
                label = self._database_tab_label_for_page(i) if db_mode and hasattr(self, "_database_tab_label_for_page") else self.page_display_name(i, include_ext=False)
                is_current = (i == current_actual)
                prefix = "▶ " if is_current else "   "
                item = QListWidgetItem(prefix + label)
                item.setData(Qt.ItemDataRole.UserRole, i)
                item.setData(Qt.ItemDataRole.UserRole + 1, is_current)
                try:
                    if db_mode and hasattr(self, "_page_data_for_index_safe"):
                        page = self._page_data_for_index_safe(i) or {}
                        meta = page.get("maker_page") or {} if isinstance(page, dict) else {}
                        original = str(meta.get("source_file") or meta.get("page_type") or label)
                        item.setToolTip(f"{self.tr_ui('데이터베이스 탭')} {display_row + 1} / {len(visible_pages)}\n{original}")
                    else:
                        item.setToolTip(self.page_display_name(i, include_ext=True))
                except Exception:
                    pass
                if is_current:
                    current_page_item = item
                    current_row_in_list = display_row
                    try:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                        if self.is_light_theme():
                            item.setBackground(QBrush(QColor("#fff7ed")))
                            item.setForeground(QBrush(QColor("#111827")))
                        else:
                            item.setBackground(QBrush(QColor("#303846")))
                            item.setForeground(QBrush(QColor("#ffffff")))
                    except Exception:
                        pass
                page_list.addItem(item)
            if current_row_in_list >= 0 and current_row_in_list < page_list.count():
                page_list.setCurrentRow(current_row_in_list)
                try:
                    page_list.setCurrentItem(page_list.item(current_row_in_list), QItemSelectionModel.SelectionFlag.ClearAndSelect)
                except Exception:
                    pass
            elif page_list.count() > 0:
                page_list.setCurrentRow(0)

        def _activate_item(item=None):
            try:
                item = item or page_list.currentItem()
                if item is None:
                    return
                page = item.data(Qt.ItemDataRole.UserRole)
                if page is None:
                    return
                popup.close()
                self.jump_to_page_from_menu(int(page))
            except Exception:
                pass

        page_list.itemActivated.connect(_activate_item)
        page_list.itemClicked.connect(_activate_item)

        row_height = 30
        try:
            max_popup_height = max(180, self.height() // 2)
        except Exception:
            max_popup_height = 300
        visible_rows = max(1, min(page_list.count() or 1, max(1, (max_popup_height - 34) // row_height)))
        popup_height = min(max_popup_height, 34 + max(1, page_list.count()) * row_height)
        try:
            popup_width = max(360, min(760, self.width() // 2))
        except Exception:
            popup_width = 520
        popup.resize(popup_width, popup_height)
        page_list.setMinimumHeight(min(visible_rows * row_height, max_popup_height - 34))
        page_list.setMaximumHeight(max_popup_height - 34)

        try:
            pos = anchor.mapToGlobal(QPoint(0, anchor.height()))
        except Exception:
            pos = self.mapToGlobal(QPoint(40, 80))
        popup.move(pos)
        popup.show()
        popup.raise_()
        popup.activateWindow()
        try:
            if current_page_item is not None:
                page_list.scrollToItem(current_page_item, QAbstractItemView.ScrollHint.PositionAtCenter)
                page_list.setCurrentItem(current_page_item, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            elif page_list.currentItem() is not None:
                page_list.scrollToItem(page_list.currentItem(), QAbstractItemView.ScrollHint.PositionAtCenter)
        except Exception:
            pass
        page_list.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def jump_to_page_from_menu(self, page_idx):
        try:
            page_idx = int(page_idx)
        except Exception:
            return
        if page_idx < 0 or page_idx >= len(getattr(self, "paths", []) or []):
            return
        db_mode = bool(self.is_maker_database_mode()) if hasattr(self, "is_maker_database_mode") else False
        visible_pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else list(range(len(getattr(self, "paths", []) or [])))
        if page_idx not in visible_pages:
            return
        display_idx = visible_pages.index(page_idx)
        if db_mode:
            try:
                if not bool(getattr(self, "_maker_database_batch_translate_active", False)):
                    self.commit_current_database_ui_to_layer()
            except Exception:
                pass
            self.maker_database_idx = page_idx
            try:
                bar = getattr(self, "page_tab_bar", None)
                if bar is not None and bar.currentIndex() != display_idx:
                    old = getattr(self, "_refreshing_page_tabs", False)
                    self._refreshing_page_tabs = True
                    try:
                        bar.blockSignals(True)
                        bar.setCurrentIndex(display_idx)
                    finally:
                        try:
                            bar.blockSignals(False)
                        except Exception:
                            pass
                        self._refreshing_page_tabs = old
            except Exception:
                pass
            try:
                self.refresh_maker_database_view()
            except Exception:
                pass
            try:
                self.refresh_maker_database_preview_from_selection()
            except Exception:
                pass
            try:
                self.update_page_position_label_for_current_tab_layer()
            except Exception:
                pass
            return
        if hasattr(self, "page_tab_bar"):
            try:
                self.page_tab_bar.setCurrentIndex(display_idx)
                return
            except Exception:
                pass
        self.on_page_tab_changed(display_idx)

    def is_maker_database_mode(self):
        return bool(getattr(self, "maker_database_mode_enabled", False))

    def _ensure_maker_database_layer_storage(self):
        """DB 번역 레이어 저장소를 보장한다.

        DB 레이어는 맵 레이어(self.paths/self.data)에 절대 섞지 않는다.
        self.maker_database_tabs에는 각 DB 탭의 표시명/원본 파일/행 데이터만 둔다.
        """
        if not isinstance(getattr(self, "maker_database_tabs", None), list):
            self.maker_database_tabs = []
        if not isinstance(getattr(self, "maker_database_idx", None), int):
            try:
                self.maker_database_idx = int(getattr(self, "maker_database_idx", 0) or 0)
            except Exception:
                self.maker_database_idx = 0
        return self.maker_database_tabs

    def _maker_page_is_database_page(self, page):
        """통합 레이어에서 DB성 페이지를 판정한다.

        이 함수는 일반 맵 프리뷰 레이어에 DB 페이지가 섞이는 것을 막기 위한
        분류 전용 판정이다. 맵/공통이벤트는 일반 번역 레이어에 남긴다.
        """
        try:
            if not isinstance(page, dict):
                return False
            meta = page.get("maker_page") or {}
            if str(meta.get("page_type") or "").strip().lower() == "database":
                return True
            for row in (page.get("data") or []):
                if not isinstance(row, dict):
                    continue
                unit = row.get("maker_text_unit") or {}
                if isinstance(unit, dict) and str(unit.get("source_kind") or "").strip().lower() == "database":
                    return True
        except Exception:
            pass
        return False

    def _database_tab_from_unified_page(self, page, source_path="", fallback="DB"):
        page = page if isinstance(page, dict) else {}
        label = self._database_tab_label_from_page_data(page, fallback=fallback) if hasattr(self, "_database_tab_label_from_page_data") else f"DB_{fallback}"
        source_file = ""
        try:
            meta = page.get("maker_page") or {}
            source_file = str(meta.get("source_file") or "").strip()
            if not source_file:
                for row in (page.get("data") or []):
                    if not isinstance(row, dict):
                        continue
                    unit = row.get("maker_text_unit") or {}
                    if isinstance(unit, dict):
                        source_file = str(unit.get("source_file") or "").strip()
                        if source_file:
                            break
        except Exception:
            pass
        return {
            "label": label,
            "source_file": source_file,
            "path": str(source_path or source_file or label),
            "page": page,
        }

    def rebuild_maker_layers_from_unified_import(self, maker_summary=None, *, reason="maker layer rebuild", save_project=False):
        """통합 레이어를 일반 맵 레이어와 DB 레이어로 분류한다.

        게임 가져오기/프로젝트 열기 직후에는 build_maker_pages가 만든 통합 목록을
        기준으로 한 번만 분류한다. 분류가 끝나면 self.paths/self.data에는 맵·대사류만
        남기고, DB성 항목은 self.maker_database_tabs로 이동한다.
        """
        try:
            paths = list(getattr(self, "paths", []) or [])
            data = getattr(self, "data", {}) or {}
            if not isinstance(data, dict):
                data = {}
            summary = maker_summary if isinstance(maker_summary, dict) else {}
            db_indices = set()
            for item in (summary.get("database_pages") or []):
                if isinstance(item, dict):
                    try:
                        db_indices.add(int(item.get("page_index")))
                    except Exception:
                        pass
            for old_idx in range(len(paths)):
                page = self._page_data_for_index_safe(old_idx) if hasattr(self, "_page_data_for_index_safe") else data.get(old_idx, {})
                if self._maker_page_is_database_page(page):
                    db_indices.add(int(old_idx))

            if not db_indices:
                self.maker_database_tabs = []
                self.maker_database_idx = 0
                return {"normal": len(paths), "database": 0, "moved": 0}

            new_paths = []
            new_data = {}
            tabs = []
            old_to_new = {}
            seen = set()
            for old_idx, raw_path in enumerate(paths):
                page = self._page_data_for_index_safe(old_idx) if hasattr(self, "_page_data_for_index_safe") else data.get(old_idx, {})
                if int(old_idx) in db_indices or self._maker_page_is_database_page(page):
                    tab = self._database_tab_from_unified_page(page, raw_path, fallback=f"{old_idx+1:03d}")
                    key = str(tab.get("source_file") or tab.get("label") or raw_path)
                    if key not in seen:
                        tabs.append(tab)
                        seen.add(key)
                    continue
                new_idx = len(new_paths)
                old_to_new[int(old_idx)] = new_idx
                new_paths.append(raw_path)
                new_data[new_idx] = page

            self.paths = new_paths
            self.data = new_data
            self.maker_database_tabs = tabs
            self.maker_database_idx = 0
            try:
                self.idx = old_to_new.get(int(getattr(self, "idx", 0) or 0), 0)
            except Exception:
                self.idx = 0
            try:
                if tabs:
                    self.log(f"🧱 통합 레이어 분류 완료: 일반 {len(new_paths)}개 / DB {len(tabs)}개 ({reason})")
            except Exception:
                pass
            if save_project:
                try:
                    self.save_project_store(force_full=True)
                except TypeError:
                    try:
                        self.save_project_store()
                    except Exception:
                        pass
                except Exception:
                    pass
            return {"normal": len(new_paths), "database": len(tabs), "moved": len(tabs)}
        except Exception as e:
            try:
                self.log(f"⚠️ 통합 레이어 분류 실패: {e}")
            except Exception:
                pass
            return {"normal": len(getattr(self, "paths", []) or []), "database": 0, "moved": 0}

    def rebuild_maker_database_layer_from_game_data(self, *, reason="database layer rebuild"):
        """maker_game/data에서 DB 레이어만 직접 재구축한다.

        이 함수는 self.paths/self.data를 건드리지 않는다. DB 모드에서 탭이 비었을 때만
        안전하게 DB 레이어를 복구하는 보조 루틴이다.
        """
        try:
            data_dir = self._maker_project_data_dir_for_database_pages()
            if data_dir is None:
                return 0
            db_pages = extract_database_text_units(Path(data_dir))
            tabs = []
            try:
                preview_settings = load_maker_preview_settings(Path(str(getattr(self, "project_dir", "") or "")))
            except Exception:
                preview_settings = {}
            for file_name, units in db_pages.items():
                if not units:
                    continue
                text_items = [_ysb_text_item_from_unit(unit, i, preview_settings=preview_settings) for i, unit in enumerate(units)]
                name = Path(str(file_name)).stem
                page_title = f"Database - {name}"
                page = {
                    "ori": None,
                    "data": text_items,
                    "original_name": f"DB_{name}",
                    "maker_preview_settings": dict(preview_settings or {}),
                    "maker_runtime_profile": {},
                    "maker_page": {
                        "page_type": "database",
                        "page_title": page_title,
                        "source_file": str(file_name),
                        "map_id": 0,
                        "map_name": page_title,
                        "map_file": str(file_name),
                        "width": 20,
                        "height": 11,
                        "event_count": 0,
                        "text_unit_count": len(units),
                        "events": [],
                    },
                }
                tabs.append({
                    "label": f"DB_{name}",
                    "source_file": str(file_name),
                    "path": str(Path(data_dir) / str(file_name)),
                    "page": page,
                })
            self.maker_database_tabs = tabs
            self.maker_database_idx = 0
            try:
                if tabs:
                    self.log(f"🧱 DB 레이어 재구축: {len(tabs)}개 ({reason})")
            except Exception:
                pass
            return len(tabs)
        except Exception as e:
            try:
                self.log(f"⚠️ DB 레이어 재구축 실패: {e}")
            except Exception:
                pass
            return 0

    def _page_data_for_index_safe(self, page_idx):
        try:
            data = getattr(self, "data", {}) or {}
            if not isinstance(data, dict):
                return {}
            idx = int(page_idx)
            page = data.get(idx)
            if isinstance(page, dict):
                return page
            page = data.get(str(idx))
            if isinstance(page, dict):
                return page
            page = data.get(str(idx + 1))
            if isinstance(page, dict):
                return page
        except Exception:
            pass
        return {}

    def _is_database_page_index(self, page_idx):
        """구버전/직전 패치에서 self.paths에 섞인 DB 가상 페이지를 판정한다.

        새 구조에서는 DB 페이지를 self.paths에 남기지 않지만, 기존 작업 폴더나
        직전 패치 결과를 열 때 분리해내기 위해 판정 함수는 유지한다.
        """
        try:
            page = self._page_data_for_index_safe(page_idx)
            meta = page.get("maker_page") or {}
            if str(meta.get("page_type") or "") == "database":
                return True
            for row in (page.get("data") or []):
                if isinstance(row, dict):
                    m = row.get("maker_text_unit") or {}
                    if isinstance(m, dict) and str(m.get("source_kind") or "") == "database":
                        return True
            try:
                paths = getattr(self, "paths", []) or []
                raw_path = str(paths[int(page_idx)] if 0 <= int(page_idx) < len(paths) else "")
                if Path(raw_path).name.lower().startswith("db_"):
                    return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    def _database_tab_label_from_page_data(self, page, fallback="DB"):
        try:
            page = page if isinstance(page, dict) else {}
            meta = page.get("maker_page") or {}
            raw = str(meta.get("source_file") or meta.get("title") or meta.get("page_title") or "").strip()
            name = Path(raw).stem if raw else ""
            if not name:
                for row in (page.get("data") or []):
                    if not isinstance(row, dict):
                        continue
                    m = row.get("maker_text_unit") or {}
                    if isinstance(m, dict):
                        name = str(m.get("db_kind") or m.get("source_file") or "").strip()
                        if name:
                            name = Path(name).stem
                            break
            if not name:
                name = str(fallback or "DB")
            if name.lower().startswith("db_"):
                return name
            return f"DB_{name}"
        except Exception:
            return f"DB_{fallback or 'Item'}"

    def _database_tab_label_for_page(self, page_idx):
        try:
            page = self._page_data_for_index_safe(int(page_idx)) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(int(page_idx), {})
            label = self._database_tab_label_from_page_data(page, fallback=f"{int(page_idx) + 1:03d}")
            return str(label or f"DB_{int(page_idx) + 1:03d}")
        except Exception:
            try:
                return f"DB_{int(page_idx) + 1:03d}"
            except Exception:
                return "DB"

    def _maker_project_data_dir_for_database_pages(self):
        try:
            root = Path(str(getattr(self, "project_dir", "") or ""))
            if not root:
                return None

            # MV exported games normally live under maker_game/www/data, while
            # MZ projects usually use maker_game/data.  The previous generic
            # ordering checked maker_game/data first even for MV projects, so a
            # stale/partial data folder could hide Troops.json and keep the
            # Troops DB tab from being rebuilt.
            engine = ""
            try:
                engine = str(self._maker_database_engine_key() or "").lower()
            except Exception:
                engine = ""
            mv_candidates = [
                root / "maker_game" / "www" / "data",
                root / "www" / "data",
                root / "maker_game" / "data",
                root / "data",
            ]
            mz_candidates = [
                root / "maker_game" / "data",
                root / "data",
                root / "maker_game" / "www" / "data",
                root / "www" / "data",
            ]
            candidates = mv_candidates if engine == "mv" else mz_candidates

            # Prefer a folder with System.json, then fall back to any JSON folder.
            json_candidates = []
            for cand in candidates:
                try:
                    if cand.is_dir() and any(cand.glob("*.json")):
                        if (cand / "System.json").is_file():
                            return cand
                        json_candidates.append(cand)
                except Exception:
                    continue
            if json_candidates:
                return json_candidates[0]
        except Exception:
            pass
        return None

    def _maker_database_tab_from_page(self, page, source_path=""):
        page = page if isinstance(page, dict) else {}
        meta = page.get("maker_page") or {}
        source_file = str(meta.get("source_file") or "").strip()
        if not source_file:
            for row in (page.get("data") or []):
                if not isinstance(row, dict):
                    continue
                m = row.get("maker_text_unit") or {}
                if isinstance(m, dict):
                    source_file = str(m.get("source_file") or "").strip()
                    if source_file:
                        break
        label = self._database_tab_label_from_page_data(page, fallback=Path(source_file or str(source_path or "DB")).stem)
        return {
            "label": label,
            "source_file": source_file,
            "path": str(source_path or source_file or label),
            "page": page,
        }

    def split_maker_database_pages_from_normal_layer(self, *, save_project=False, reason="split database layer"):
        """구버전/직전 패치의 혼합 페이지를 3층 분류 규칙으로 다시 분리한다."""
        before = len(self._ensure_maker_database_layer_storage())
        result = self.rebuild_maker_layers_from_unified_import(None, reason=reason, save_project=save_project)
        after = len(self._ensure_maker_database_layer_storage())
        return max(0, after - before) if after else int(result.get("moved") or 0)

    def _repair_maker_database_missing_name_rows(self, *, reason="database name row repair", save_project=False):
        """Add missing player-facing DB name rows created by an older over-broad filter.

        Earlier DB extraction could leave Skills/Items/Weapons/Armors/etc. without
        their name rows, because internal editor-name exclusions were too broad.
        This repair is intentionally narrow: it only inserts missing ``name`` rows
        into existing DB virtual pages and preserves existing translations/memos.
        """
        try:
            data_dir = self._maker_project_data_dir_for_database_pages()
            if data_dir is None:
                return 0
            db_pages = extract_database_text_units(Path(data_dir))
            if not db_pages:
                return 0
            changed = 0
            paths = list(getattr(self, "paths", []) or [])
            data = getattr(self, "data", {}) or {}
            if not isinstance(data, dict):
                return 0
            try:
                preview_settings = load_maker_preview_settings(Path(str(getattr(self, "project_dir", "") or "")))
            except Exception:
                preview_settings = {}

            def _source_file_for_page(page):
                try:
                    meta = page.get("maker_page") if isinstance(page, dict) else {}
                    sf = str((meta or {}).get("source_file") or "").strip()
                    if sf:
                        return Path(sf).name
                    for row in (page.get("data") or []):
                        unit = (row or {}).get("maker_text_unit") if isinstance(row, dict) else {}
                        if isinstance(unit, dict):
                            sf = str(unit.get("source_file") or "").strip()
                            if sf:
                                return Path(sf).name
                except Exception:
                    pass
                return ""

            for page_idx in range(len(paths)):
                page = self._page_data_for_index_safe(page_idx) if hasattr(self, "_page_data_for_index_safe") else data.get(page_idx, {})
                if not self._maker_page_is_database_page(page):
                    continue
                source_file = _source_file_for_page(page)
                if not source_file or source_file not in db_pages:
                    continue
                wanted_units = [u for u in (db_pages.get(source_file) or []) if str(getattr(u, "db_field", "") or "") == "name"]
                if not wanted_units:
                    continue
                rows = list((page or {}).get("data") or [])
                existing_paths = set()
                existing_name_by_id = set()
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    unit = row.get("maker_text_unit") or {}
                    if not isinstance(unit, dict):
                        continue
                    jp = str(unit.get("json_path") or row.get("maker_json_path") or "").strip()
                    if jp:
                        existing_paths.add(jp)
                    db_field = str(unit.get("db_field") or "").strip()
                    db_id = unit.get("db_id")
                    if db_field == "name":
                        existing_name_by_id.add(str(db_id))
                inserts = []
                for unit in wanted_units:
                    jp = str(getattr(unit, "json_path", "") or "").strip()
                    db_id = getattr(unit, "db_id", None)
                    if jp and jp in existing_paths:
                        continue
                    if str(db_id) in existing_name_by_id:
                        continue
                    try:
                        item = _ysb_text_item_from_unit(unit, len(rows) + len(inserts), preview_settings=preview_settings)
                    except Exception:
                        continue
                    inserts.append((db_id, item))
                    if jp:
                        existing_paths.add(jp)
                    existing_name_by_id.add(str(db_id))
                if not inserts:
                    continue
                # Insert each missing name before the first row of the same DB id so
                # the page order becomes: name -> description/message... where possible.
                for db_id, item in reversed(inserts):
                    insert_at = None
                    for i, row in enumerate(rows):
                        unit = row.get("maker_text_unit") if isinstance(row, dict) else {}
                        if isinstance(unit, dict) and str(unit.get("db_id")) == str(db_id):
                            insert_at = i
                            break
                    if insert_at is None:
                        rows.append(item)
                    else:
                        rows.insert(insert_at, item)
                    changed += 1
                page["data"] = rows
                try:
                    meta = page.setdefault("maker_page", {})
                    if isinstance(meta, dict):
                        meta["text_unit_count"] = len(rows)
                except Exception:
                    pass
                try:
                    self.data[int(page_idx)] = page
                except Exception:
                    pass
            if changed:
                try:
                    self.log(f"🧩 DB 이름 행 복구: {changed}개 ({reason})")
                except Exception:
                    pass
                try:
                    self.mark_project_structure_dirty("maker_database_name_rows_repaired")
                except Exception:
                    pass
                if save_project:
                    try:
                        self.save_workspace_project_json_light(reason="maker_database_name_rows_repaired")
                    except Exception:
                        pass
            return changed
        except Exception as e:
            try:
                self.log(f"⚠️ DB 이름 행 복구 실패: {type(e).__name__}: {e}")
            except Exception:
                pass
            return 0

    def _repair_maker_database_missing_virtual_pages(self, *, reason="database page repair", save_project=False):
        """Add missing DB virtual pages such as Troops from the current game data.

        Some older projects were opened after an over-broad DB exclusion pass, so
        an entire DB tab can be absent even though the imported maker_game/data
        still contains player-facing text.  Troops is the important case: troop
        names are internal, but battle-event Show Text/Choices/Scrolling Text must
        remain translatable.  This repair adds only missing source-file pages and
        leaves existing rows/translations untouched.
        """
        try:
            data_dir = self._maker_project_data_dir_for_database_pages()
            if data_dir is None:
                return 0
            db_pages = extract_database_text_units(Path(data_dir))
            if not db_pages:
                return 0
            paths = list(getattr(self, "paths", []) or [])
            data = getattr(self, "data", {}) or {}
            if not isinstance(data, dict):
                data = {}
            existing = set()

            def _source_file_for_page(page):
                try:
                    meta = page.get("maker_page") if isinstance(page, dict) else {}
                    sf = str((meta or {}).get("source_file") or "").strip()
                    if sf:
                        return Path(sf).name
                    for row in (page.get("data") or []):
                        unit = (row or {}).get("maker_text_unit") if isinstance(row, dict) else {}
                        if isinstance(unit, dict):
                            sf = str(unit.get("source_file") or "").strip()
                            if sf:
                                return Path(sf).name
                except Exception:
                    pass
                return ""

            for i in range(len(paths)):
                page = self._page_data_for_index_safe(i) if hasattr(self, "_page_data_for_index_safe") else data.get(i, {})
                if self._maker_page_is_database_page(page):
                    sf = _source_file_for_page(page)
                    if sf:
                        existing.add(sf.lower())
            # Do not trust maker_database_tabs here.  It is a view/cache list and
            # can be stale after switching projects or after entering/exiting DB
            # mode.  Only actual self.data pages count as existing DB pages;
            # otherwise missing files such as Troops.json can be falsely skipped.

            try:
                preview_settings = load_maker_preview_settings(Path(str(getattr(self, "project_dir", "") or "")))
            except Exception:
                preview_settings = {}

            added = 0
            for file_name, units in (db_pages or {}).items():
                if not units:
                    continue
                if Path(str(file_name)).name.lower() in existing:
                    continue
                text_items = []
                for i, unit in enumerate(units):
                    try:
                        text_items.append(_ysb_text_item_from_unit(unit, i, preview_settings=preview_settings))
                    except Exception:
                        continue
                if not text_items:
                    continue
                name = Path(str(file_name)).stem
                page_title = f"Database - {name}"
                page = {
                    "ori": None,
                    "data": text_items,
                    "original_name": f"DB_{name}",
                    "maker_preview_settings": dict(preview_settings or {}),
                    "maker_runtime_profile": {},
                    "maker_page": {
                        "page_type": "database",
                        "page_title": page_title,
                        "source_file": str(file_name),
                        "map_id": 0,
                        "map_name": page_title,
                        "map_file": str(file_name),
                        "width": 20,
                        "height": 11,
                        "event_count": 0,
                        "text_unit_count": len(text_items),
                        "events": [],
                    },
                }
                new_idx = len(paths)
                paths.append(str(Path(data_dir) / str(file_name)))
                data[int(new_idx)] = page
                existing.add(Path(str(file_name)).name.lower())
                added += 1

            if added:
                self.paths = paths
                self.data = data
                try:
                    self.log(f"🧩 누락 DB 탭 복구: {added}개 ({reason})")
                except Exception:
                    pass
                try:
                    self.mark_project_structure_dirty("maker_database_missing_pages_repaired")
                except Exception:
                    pass
                if save_project:
                    try:
                        self.save_workspace_project_json_light(reason="maker_database_missing_pages_repaired")
                    except Exception:
                        pass
            return added
        except Exception as e:
            try:
                self.log(f"⚠️ 누락 DB 탭 복구 실패: {type(e).__name__}: {e}")
            except Exception:
                pass
            return 0

    def ensure_maker_database_pages(self, *, save_project=True, reason="database mode"):
        """게임 가져오기 때 이미 생성된 page_type=database 페이지 수를 반환한다.

        정식 경로에서는 DB를 별도로 재생성하지 않는다. DB 페이지는 build_maker_pages가
        self.paths/self.data 안에 만들어 둔 가상 페이지이며, 모드 전환은 이 목록을
        필터링해서 보여주는 방식으로만 동작한다.
        """
        try:
            try:
                self._repair_maker_database_missing_virtual_pages(reason=reason, save_project=bool(save_project))
            except Exception:
                pass
            paths = getattr(self, "paths", []) or []
            count = 0
            for i in range(len(paths)):
                try:
                    page = self._page_data_for_index_safe(i) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(i, {})
                    if self._maker_page_is_database_page(page):
                        count += 1
                except Exception:
                    continue
            try:
                if count > 0:
                    # 구버전 프로젝트에서 DB 이름(name) 행이 빠진 경우를 좁게 보수한다.
                    # 스킬명/아이템명/장비명은 실제 게임 화면에 노출되므로 번역 대상이다.
                    self._repair_maker_database_missing_name_rows(reason=reason, save_project=bool(save_project))
            except Exception:
                pass
            try:
                self.audit_maker_database_mode_event("DB_PAGE_COUNT_FROM_PROJECT", reason=reason, count=count, total_pages=len(paths))
            except Exception:
                pass
            return int(count or 0)
        except Exception as e:
            try:
                self.log(f"⚠️ 데이터베이스 페이지 확인 실패: {e}")
            except Exception:
                pass
            return 0

    def diagnose_maker_database_scan_action(self):
        """수동 재현용: DB 탭 생성 전에 data 폴더와 추출 결과만 확인한다."""
        lines = []
        try:
            try:
                project_dir = Path(str(getattr(self, "project_dir", "") or ""))
            except Exception:
                project_dir = Path("")
            lines.append(f"project_dir: {project_dir if str(project_dir) else 'NOT SET'}")
            try:
                candidates = [
                    project_dir / "maker_game" / "data",
                    project_dir / "maker_game" / "www" / "data",
                    project_dir / "data",
                ]
                for cand in candidates:
                    try:
                        json_count = len(list(cand.glob("*.json"))) if cand.is_dir() else 0
                        lines.append(f"candidate: {cand} exists={cand.is_dir()} json={json_count}")
                    except Exception as _ce:
                        lines.append(f"candidate: {cand} ERROR {type(_ce).__name__}: {_ce}")
            except Exception as _ce:
                lines.append(f"candidate_scan_error: {type(_ce).__name__}: {_ce}")
            data_dir = self._maker_project_data_dir_for_database_pages()
            lines.append(f"selected_data_dir: {data_dir if data_dir else 'NOT FOUND'}")
            if data_dir is None:
                msg = "데이터 폴더를 찾지 못했습니다. 프로젝트 안에 maker_game/data 또는 maker_game/www/data가 있는지 확인해 주세요."
                lines.append(msg)
                try:
                    self.log("🧪 DB_SCAN_DIAG | " + " | ".join(lines))
                except Exception:
                    pass
                QMessageBox.information(self, self.tr_ui("DB 스캔 진단"), "\n".join(lines))
                return False
            data_dir = Path(data_dir)
            json_files = sorted([p for p in data_dir.glob("*.json")], key=lambda p: p.name.lower())
            lines.append(f"json_files: {len(json_files)}")
            try:
                sample_names = [p.name for p in json_files[:30]]
                lines.append("json_sample: " + (", ".join(sample_names) if sample_names else "NONE"))
            except Exception:
                pass
            excluded = []
            try:
                import re
                for p in json_files:
                    n = p.name
                    if re.match(r"Map\d+\.json$", n, re.I) or n in {"MapInfos.json", "CommonEvents.json"}:
                        excluded.append(n)
            except Exception:
                pass
            if excluded:
                lines.append(f"excluded_map_like: {len(excluded)}")
            try:
                db_pages = extract_database_text_units(data_dir)
            except Exception as e:
                db_pages = {}
                lines.append(f"extract_error: {type(e).__name__}: {e}")
            total = 0
            if isinstance(db_pages, dict):
                for file_name, units in sorted(db_pages.items(), key=lambda kv: str(kv[0]).lower()):
                    cnt = len(units or [])
                    total += cnt
                    lines.append(f"{file_name}: {cnt}")
            lines.append(f"db_total_units: {total}")
            lines.append(f"current_database_pages: {self.ensure_maker_database_pages(save_project=False, reason='diagnostic')}")
            try:
                self.log("🧪 DB_SCAN_DIAG | " + " | ".join(lines))
            except Exception:
                pass
            QMessageBox.information(self, self.tr_ui("DB 스캔 진단"), "\n".join(lines[:80]))
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ DB_SCAN_DIAG_FAIL | {type(e).__name__}: {e}")
            except Exception:
                pass
            QMessageBox.warning(self, self.tr_ui("DB 스캔 진단"), f"DB 스캔 진단 실패:\n{e}")
            return False

    def rebuild_maker_database_layer_manual_action(self):
        """수동 재현용: 게임 가져오기 때 생성된 DB 페이지를 확인한다."""
        try:
            pages = []
            for i in range(len(getattr(self, "paths", []) or [])):
                page = self._page_data_for_index_safe(i) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(i, {})
                if self._maker_page_is_database_page(page):
                    pages.append(i)
            msg = f"DB 페이지 확인 결과\n현재 DB 페이지: {len(pages)}\n반환값: {len(pages)}"
            if pages:
                msg += "\n\n" + "\n".join([f"{i}: {self._database_tab_label_for_page(i)}" for i in pages[:60]])
            try:
                self.log(f"🧪 DB_PAGE_CHECK_MANUAL | count={len(pages)} pages={pages[:30]}")
            except Exception:
                pass
            try:
                if self.is_maker_database_mode():
                    self.force_rebuild_page_tabs_for_current_layer(reason="manual db page check")
                    self.refresh_maker_database_view()
            except Exception:
                pass
            QMessageBox.information(self, self.tr_ui("DB 페이지 확인"), msg)
            return bool(pages)
        except Exception as e:
            try:
                self.log(f"⚠️ DB_PAGE_CHECK_MANUAL_FAIL | {type(e).__name__}: {e}")
            except Exception:
                pass
            QMessageBox.warning(self, self.tr_ui("DB 페이지 확인"), f"DB 페이지 확인 실패:\n{e}")
            return False

    def diagnose_maker_tile_preview_action(self):
        """수동 재현용: 현재 맵 타일 프리뷰가 왜 그리드로 떨어지는지 진단한다."""
        lines = []
        try:
            if not getattr(self, "paths", None):
                QMessageBox.information(self, self.tr_ui("타일 프리뷰 진단"), self.tr_ui("열린 맵이 없습니다."))
                return False
            try:
                page_idx = int(getattr(self, "idx", 0) or 0)
            except Exception:
                page_idx = 0
            page = self._page_data_for_index_safe(page_idx) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(page_idx, {})
            if not isinstance(page, dict):
                page = {}
            meta = page.get("maker_page") or {}
            project_root = None
            try:
                project_root = Path(str(self._maker_preview_project_root()))
            except Exception:
                try:
                    project_root = Path(str(getattr(self, "project_dir", "") or ""))
                except Exception:
                    project_root = None
            lines.append(f"project_dir: {project_root if project_root else 'NOT FOUND'}")
            lines.append(f"page_idx: {page_idx}")
            lines.append(f"map_file: {meta.get('map_file') or 'NONE'}")
            lines.append(f"map_id: {meta.get('map_id')}")
            lines.append(f"map_name: {meta.get('map_name') or meta.get('page_title') or ''}")
            lines.append(f"preview_crop: {'YES' if meta.get('preview_crop') else 'NO'}")
            def _image_value_diag(label, value, path_hint=None):
                try:
                    if value is None:
                        lines.append(f"{label}: NONE")
                        return
                    if isinstance(value, (str, Path)):
                        raw = str(value or "")
                        if raw:
                            pp = Path(raw)
                            lines.append(f"{label}: PATH {raw}")
                            lines.append(f"{label}_exists: {pp.exists()} size={pp.stat().st_size if pp.exists() else 0}")
                        else:
                            lines.append(f"{label}: EMPTY_PATH")
                        return
                    try:
                        shape = getattr(value, "shape", None)
                        dtype = getattr(value, "dtype", None)
                        lines.append(f"{label}: ARRAY shape={shape} dtype={dtype}")
                    except Exception:
                        lines.append(f"{label}: OBJECT {type(value).__name__}")
                    if path_hint:
                        try:
                            pp = Path(str(path_hint))
                            lines.append(f"{label}_path_hint: {pp} exists={pp.exists()} size={pp.stat().st_size if pp.exists() else 0}")
                        except Exception as _he:
                            lines.append(f"{label}_path_hint: ERROR {type(_he).__name__}: {_he}")
                except Exception as _e:
                    lines.append(f"{label}: ERROR {type(_e).__name__}: {_e}")
            _image_value_diag("ori", page.get("ori"), self.paths[page_idx] if 0 <= page_idx < len(getattr(self, "paths", []) or []) else None)
            _image_value_diag("bg_clean", page.get("bg_clean"), page.get("bg_clean_path") or page.get("clean_path"))
            _image_value_diag("working_source", page.get("working_source"), page.get("working_source_path"))

            data_dir = None
            try:
                data_dir = self._maker_project_data_dir_for_database_pages()
            except Exception:
                data_dir = None
            lines.append(f"data_dir: {data_dir if data_dir else 'NOT FOUND'}")
            map_file = str(meta.get("map_file") or "").strip()
            if data_dir and map_file:
                map_json = Path(data_dir) / map_file
                lines.append(f"map_json_exists: {map_json.exists()} ({map_json})")
                try:
                    import json
                    mj = json.loads(map_json.read_text(encoding="utf-8-sig")) if map_json.exists() else {}
                    tileset_id = int(mj.get("tilesetId") or 0) if isinstance(mj, dict) else 0
                    lines.append(f"tilesetId: {tileset_id}")
                    tilesets_json = Path(data_dir) / "Tilesets.json"
                    lines.append(f"Tilesets.json_exists: {tilesets_json.exists()}")
                    if tilesets_json.exists():
                        tilesets = json.loads(tilesets_json.read_text(encoding="utf-8-sig"))
                        entry = None
                        if isinstance(tilesets, list) and 0 <= tileset_id < len(tilesets):
                            entry = tilesets[tileset_id]
                        if isinstance(entry, dict):
                            names = [str(x or "") for x in (entry.get("tilesetNames") or [])]
                            lines.append(f"tileset_name: {entry.get('name') or ''}")
                            lines.append("tilesetNames: " + ", ".join([n for n in names if n][:12]))
                            root = Path(str(project_root or ""))
                            image_roots = [
                                root / "maker_game" / "img" / "tilesets",
                                root / "maker_game" / "www" / "img" / "tilesets",
                                root / "img" / "tilesets",
                            ]
                            for n in names:
                                if not n:
                                    continue
                                found = []
                                checked = []
                                prepared_lines = []
                                for ir in image_roots:
                                    for ext in (".png", ".PNG", ".png_", ".PNG_", ".rpgmvp", ".rpgmvp_", ".webp", ".webp_"):
                                        cand = ir / (n + ext)
                                        checked.append(str(cand))
                                        if cand.exists():
                                            found.append(str(cand))
                                            try:
                                                prepared, pdiag = self._maker_preview_prepare_image_asset(cand, category="tilesets")
                                                ok = bool(prepared and Path(prepared).is_file())
                                                if pdiag:
                                                    err = str(pdiag.get("error") or "")
                                                    dec = str(pdiag.get("decrypt_success") if pdiag.get("encrypted") else "plain")
                                                    prepared_lines.append(f"    prepare: {cand.name} -> {'OK' if ok else 'FAIL'} decrypt={dec}" + (f" error={err}" if err else ""))
                                                else:
                                                    prepared_lines.append(f"    prepare: {cand.name} -> {'OK' if ok else 'FAIL'}")
                                            except Exception as _pe:
                                                prepared_lines.append(f"    prepare: {cand.name} -> ERROR {type(_pe).__name__}: {_pe}")
                                if found:
                                    lines.append(f"tileset_asset[{n}]: FOUND -> {found[0]}")
                                    lines.extend(prepared_lines[:4])
                                else:
                                    lines.append(f"tileset_asset[{n}]: MISSING checked={len(checked)}")
                        else:
                            lines.append("tileset_entry: NOT FOUND")
                except Exception as _e:
                    lines.append(f"map/tileset_parse_error: {type(_e).__name__}: {_e}")

            # 강제 검수 덤프: 현재 선택 행 기준으로 타일 렌더러를 한 번 돌리고 summary를 읽는다.
            try:
                row_idx = 1
                table = getattr(self, "tab", None)
                if table is not None and int(table.currentRow()) >= 1:
                    row_idx = int(table.currentRow())
                row_data = (page.get("data") or [None] * (row_idx + 1))[row_idx] if isinstance(page.get("data"), list) and row_idx < len(page.get("data")) else None
                st = dict((page.get("maker_preview_settings") or {}) if isinstance(page, dict) else {})
                st.update({
                    "show_local_map_preview": True,
                    "show_tile_map_preview": True,
                    "show_advanced_map_preview": True,
                    "enable_tile_validation_dump": True,
                })
                ok = self._refresh_maker_local_map_preview_background(row_data, page=page, settings=st)
                lines.append(f"forced_preview_refresh: {ok}")
                dump_dir = Path(str(project_root or "")) / "maker_meta" / "maker_map_preview_validate_last"
                summary_path = dump_dir / "summary.json"
                lines.append(f"validation_dump: {summary_path} exists={summary_path.exists()}")
                if summary_path.exists():
                    import json
                    sm = json.loads(summary_path.read_text(encoding="utf-8"))
                    for key in ("rendered_any", "tile_validation_enabled", "map_file", "tileset_id", "tileset_name", "rendered_tiles", "missing_assets", "errors", "wrote_scene_raw", "wrote_scene_with_star"):
                        if key in sm:
                            lines.append(f"summary.{key}: {sm.get(key)}")
                try:
                    self.load()
                except Exception:
                    pass
            except Exception as _e:
                lines.append(f"forced_preview_refresh_error: {type(_e).__name__}: {_e}")

            try:
                self.log("🧪 TILE_PREVIEW_DIAG | " + " | ".join(lines[:80]))
            except Exception:
                pass
            QMessageBox.information(self, self.tr_ui("타일 프리뷰 진단"), "\n".join(lines[:120]))
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ TILE_PREVIEW_DIAG_FAIL | {type(e).__name__}: {e}")
            except Exception:
                pass
            QMessageBox.warning(self, self.tr_ui("타일 프리뷰 진단"), f"타일 프리뷰 진단 실패:\n{e}")
            return False

    def current_tab_page_indices(self):
        """현재 모드에서 탭바가 표시해야 하는 실제 self.paths 인덱스 목록.

        일반 모드: page_type != database
        DB 모드: page_type == database
        두 경우 모두 원본은 게임 가져오기 때 만들어진 self.paths/self.data다.
        """
        try:
            total = len(getattr(self, "paths", []) or [])
            db_mode = bool(self.is_maker_database_mode()) if hasattr(self, "is_maker_database_mode") else False
            out = []
            for i in range(total):
                page = self._page_data_for_index_safe(i) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(i, {})
                is_db = bool(self._maker_page_is_database_page(page))
                if db_mode and is_db:
                    out.append(i)
                elif (not db_mode) and (not is_db):
                    out.append(i)
            return out
        except Exception:
            return []

    def current_tab_display_index_for_page(self, page_idx=None):
        try:
            pages = self.current_tab_page_indices()
            if self.is_maker_database_mode():
                actual = int(getattr(self, "maker_database_idx", 0) if page_idx is None else page_idx)
            else:
                actual = int(self.idx if page_idx is None else page_idx)
            return pages.index(actual) if actual in pages else -1
        except Exception:
            return -1

    def update_page_position_label_for_current_tab_layer(self):
        try:
            pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else list(range(len(getattr(self, "paths", []) or [])))
            if self.is_maker_database_mode():
                current = int(getattr(self, "maker_database_idx", 0) or 0)
            else:
                current = int(getattr(self, "idx", 0) or 0)
            total = len(pages)
            try:
                pos = pages.index(current)
            except Exception:
                pos = 0
            text = "0 / 0" if total <= 0 else f"{pos + 1} / {total}"
            btn = getattr(self, "btn_page", None)
            if btn is not None:
                btn.setText(text)
        except Exception:
            pass

    def set_maker_database_preview_visible(self, enabled):
        """DB 모드 전용 좌측 프리뷰와 일반 맵 프리뷰를 전환한다."""
        enabled = bool(enabled)
        try:
            panel = getattr(self, "maker_database_preview_panel", None)
            if panel is not None:
                panel.setVisible(enabled)
        except Exception:
            pass
        try:
            split = getattr(self, "source_compare_splitter", None)
            if split is not None:
                split.setVisible(not enabled)
        except Exception:
            pass
        try:
            if enabled:
                if hasattr(self, "_apply_maker_database_preview_fixed_ratio"):
                    self._apply_maker_database_preview_fixed_ratio()
                self.refresh_maker_database_preview_from_selection()
        except Exception:
            pass

    def _current_database_preview_row_data(self):
        """현재 DB 표에서 프리뷰에 표시할 row_data를 가져온다."""
        try:
            actual_idx = int(getattr(self, "maker_database_idx", 0) or 0)
        except Exception:
            actual_idx = 0
        page = self._page_data_for_index_safe(actual_idx) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(actual_idx, {})
        filtered = self._maker_database_filtered_rows_for_page(page) if hasattr(self, "_maker_database_filtered_rows_for_page") else list(enumerate((page or {}).get("data") or []))
        if not filtered:
            return page, None, -1
        table_row = 1
        try:
            tab = getattr(self, "tab", None)
            if tab is not None and int(tab.currentRow()) > 0:
                table_row = int(tab.currentRow())
        except Exception:
            table_row = 1
        try:
            tab = getattr(self, "tab", None)
            if tab is not None and table_row > 0:
                id_item = tab.item(table_row, 0)
                if id_item is not None:
                    v = id_item.data(Qt.ItemDataRole.UserRole)
                    if v is not None and str(v).strip() != "":
                        data_index = int(v)
                        rows = (page or {}).get("data") or []
                        if 0 <= data_index < len(rows):
                            return page, rows[data_index], data_index
        except Exception:
            pass
        visible_index = max(0, min(len(filtered) - 1, table_row - 1))
        data_index, row = filtered[visible_index]
        return page, row, data_index


    def _db_preview_escape(self, value):
        try:
            s = str(value if value is not None else "")
        except Exception:
            s = ""
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("\n", "<br>"))

    def _maker_database_data_dir_runtime(self):
        try:
            if hasattr(self, "_maker_project_data_dir_for_database_pages"):
                cand = self._maker_project_data_dir_for_database_pages()
                if cand is not None:
                    return Path(cand)
        except Exception:
            pass
        try:
            root = Path(str(getattr(self, "project_dir", "") or ""))
            for cand in (
                root / "maker_game" / "data",
                root / "maker_game" / "www" / "data",
                root / "data",
            ):
                try:
                    if cand.is_dir() and any(cand.glob("*.json")):
                        return cand
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _load_maker_database_json_runtime(self, file_name):
        try:
            name = str(file_name or "").strip()
            if not name:
                return None
            if not name.lower().endswith(".json"):
                name += ".json"
            data_dir = self._maker_database_data_dir_runtime()
            if data_dir is None:
                return None
            p = Path(data_dir) / name
            if not p.is_file():
                # Case-insensitive fallback for packaged games.
                lname = name.lower()
                for f in data_dir.glob("*.json"):
                    if f.name.lower() == lname:
                        p = f
                        break
            if not p.is_file():
                return None
            cache = getattr(self, "_maker_database_json_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                self._maker_database_json_cache = cache
            key = str(p.resolve())
            try:
                st = p.stat()
                sig = (st.st_mtime_ns, st.st_size)
            except Exception:
                sig = None
            cached = cache.get(key)
            if isinstance(cached, dict) and cached.get("sig") == sig:
                return cached.get("data")
            with open(p, "r", encoding="utf-8-sig") as fp:
                data = json.load(fp)
            cache[key] = {"sig": sig, "data": data}
            return data
        except Exception:
            return None

    def _maker_database_record_from_path(self, file_name, json_path):
        """Actors.json/1/name 같은 경로에서 원본 DB 레코드를 찾는다."""
        try:
            file_name = str(file_name or "").strip()
            path = str(json_path or "").strip()
            if not file_name and path:
                file_name = path.split("/", 1)[0]
            data = self._load_maker_database_json_runtime(file_name)
            if data is None:
                return None, None, ""
            parts = [x for x in path.split("/") if x]
            # Drop leading file name.
            if parts and parts[0].lower().endswith(".json"):
                parts = parts[1:]
            rec_id = None
            field = ""
            cur = data
            if parts:
                try:
                    rec_id = int(parts[0])
                    if isinstance(cur, list) and 0 <= rec_id < len(cur):
                        cur = cur[rec_id]
                    elif isinstance(cur, dict):
                        cur = cur.get(str(rec_id)) or cur.get(rec_id)
                    parts = parts[1:]
                except Exception:
                    rec_id = None
            if parts:
                field = str(parts[-1])
            return cur, rec_id, field
        except Exception:
            return None, None, ""

    def _maker_database_page_rows_for_current(self):
        try:
            actual_idx = int(getattr(self, "maker_database_idx", 0) or 0)
        except Exception:
            actual_idx = 0
        page = self._page_data_for_index_safe(actual_idx) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(actual_idx, {})
        rows = (page or {}).get("data") or []
        return page, rows

    def _is_maker_database_row_translatable(self, row_data):
        """DB 표/번역 대상에서 코드성/내부 설정 항목을 제외한다.

        과거 버전으로 생성된 프로젝트에는 System.advanced, switches/variables,
        BGM 파일명, Skills.damage.formula 같은 행이 이미 들어 있을 수 있으므로,
        추출기뿐 아니라 UI 표시 단계에서도 한 번 더 막는다.
        """
        try:
            row_data = row_data if isinstance(row_data, dict) else {}
            unit = row_data.get("maker_text_unit") or {}
            unit = unit if isinstance(unit, dict) else {}
            field = str(unit.get("db_field") or unit.get("text_type") or "").lower()
            path = str(unit.get("json_path") or unit.get("db_path") or "").lower()
            value = str(row_data.get("text") or row_data.get("source_text") or "")
            source_file = str(unit.get("source_file") or unit.get("map_file") or "").lower()
            source_kind = str(unit.get("source_kind") or "").strip().lower()
            banned = {
                "formula", "script", "code", "note", "meta", "damage", "traits", "effects",
                "params", "parameters", "condition", "conditions", "advanced", "switches",
                "variables", "sounds", "testbattlers", "battletest", "filename", "file",
                "src", "url", "path", "folder", "facename", "charactername", "battlername",
                "svbattlername", "battleback1name", "battleback2name", "parallaxname",
            }
            parts = [x for x in re.split(r"[./\\]+", field + "/" + path) if x]
            if any(part in banned for part in parts):
                return False
            # DB object names are player-facing in RPG Maker menus/battle logs.
            # Keep them even while excluding internal resource/script fields.
            if source_file in {"actors.json", "classes.json", "skills.json", "items.json", "weapons.json", "armors.json", "enemies.json", "states.json"}:
                if field.endswith(".name") or field == "name" or path.endswith("/name") or path.endswith(".name"):
                    return True
            if source_file == "troops.json" and source_kind != "troop_event":
                return False
            if source_file in {"animations.json", "tilesets.json", "mapinfos.json", "commonevents.json"}:
                return False
            if source_file == "system.json":
                allowed_roots = {"gametitle", "currencyunit", "elements", "skilltypes", "weapontypes", "armortypes", "equiptypes", "terms"}
                roots = [p for p in parts if p and not p.endswith("json")]
                if roots:
                    first = roots[0]
                    if first == "system":
                        roots = roots[1:]
                    first = roots[0] if roots else ""
                    if first and first not in allowed_roots:
                        return False
                if any(part.endswith(("bgm", "bgs", "me", "se", "audio")) for part in parts):
                    return False
            if any(part.endswith(("bgm", "bgs", "me", "se", "audio")) for part in parts):
                return False
            if re.search(r"\b[ab]\.(atk|def|mat|mdf|agi|luk|hp|mp|tp)\b", value, flags=re.I):
                return False
            if re.fullmatch(r"[A-Za-z0-9_./\\:-]+", value.strip()) and not any(ord(ch) > 127 for ch in value):
                return False
            return True
        except Exception:
            return True

    def _maker_database_filtered_rows_for_page(self, page):
        rows = (page or {}).get("data") or []
        out = []
        for i, row in enumerate(rows):
            if self._is_maker_database_row_translatable(row):
                out.append((i, row))
        return out

    def _maker_database_runtime_profile(self):
        """Return the persisted MV/MZ runtime profile for DB preview rendering."""
        try:
            import json as _json
            root = Path(str(getattr(self, "project_dir", "") or ""))
            path = root / "maker_meta" / "maker_runtime_profile.json"
            if path.is_file():
                with path.open("r", encoding="utf-8") as f:
                    data = _json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _maker_database_engine_key(self):
        """Detect whether the imported game is MZ or MV for DB preview layout."""
        try:
            profile = self._maker_database_runtime_profile()
            eng = str((profile or {}).get("engine") or "").lower().strip()
            if "mz" in eng:
                return "mz"
            if "mv" in eng:
                return "mv"
        except Exception:
            pass
        try:
            system = self._load_maker_database_json_runtime("System.json") or {}
            if isinstance(system.get("advanced"), dict) and system.get("advanced"):
                return "mz"
        except Exception:
            pass
        return "mv"

    def _maker_database_screen_metrics(self):
        """Read exact game screen/ui metrics from the imported game.

        MZ and MV do not share the same default status/menu proportions.  DB
        preview must render in the original game's screen size first, then be
        scaled by the viewer.  Do not collapse MZ into the old 816x624 MV-like
        canvas.
        """
        engine = self._maker_database_engine_key()
        system = self._load_maker_database_json_runtime("System.json") or {}
        adv = system.get("advanced") if isinstance(system.get("advanced"), dict) else {}
        profile = self._maker_database_runtime_profile()
        screen = profile.get("screen") if isinstance(profile.get("screen"), dict) else {}

        def pick_int(default, *vals):
            for val in vals:
                try:
                    if isinstance(val, tuple):
                        obj, key = val
                        val = obj.get(key) if isinstance(obj, dict) else None
                    if val is not None and str(val).strip() != "":
                        iv = int(round(float(val)))
                        if iv > 0:
                            return iv
                except Exception:
                    continue
            return int(default)

        if engine == "mz":
            w = pick_int(1280, (adv, "screenWidth"), (adv, "uiAreaWidth"), (screen, "width"), (screen, "ui_area_width"))
            h = pick_int(720, (adv, "screenHeight"), (adv, "uiAreaHeight"), (screen, "height"), (screen, "ui_area_height"))
        else:
            w = pick_int(816, (screen, "width"), (adv, "screenWidth"), (adv, "uiAreaWidth"))
            h = pick_int(624, (screen, "height"), (adv, "screenHeight"), (adv, "uiAreaHeight"))
        return {
            "engine": engine,
            "screen_width": max(320, min(4096, int(w))),
            "screen_height": max(240, min(2160, int(h))),
            "font_size": pick_int(26 if engine == "mz" else 28, (adv, "fontSize"), ((profile.get("font") if isinstance(profile.get("font"), dict) else {}), "size")),
            "window_opacity": pick_int(192 if engine == "mz" else 205, (adv, "windowOpacity"), ((profile.get("window") if isinstance(profile.get("window"), dict) else {}), "opacity")),
        }

    def _maker_database_preview_geometry(self):
        """DB preview base canvas size.  MZ uses the game's real screen size."""
        try:
            m = self._maker_database_screen_metrics()
            return int(m.get("screen_width") or 1280), int(m.get("screen_height") or 720)
        except Exception:
            return 1280, 720

    def _apply_maker_database_preview_fixed_ratio(self):
        try:
            lbl = getattr(self, "lbl_maker_database_preview_canvas", None)
            if lbl is None:
                return
            # DB 프리뷰도 일반 맵 프리뷰처럼 이미지로 취급한다.
            # 기본은 화면 맞춤이고, 사용자가 Ctrl+휠을 쓰면 고정 배율 모드로 전환한다.
            if not isinstance(getattr(self, "_maker_database_preview_zoom", None), (int, float)):
                self._maker_database_preview_zoom = 1.0
            if not hasattr(self, "_maker_database_preview_fit_mode"):
                self._maker_database_preview_fit_mode = True
            lbl.setMinimumSize(320, 240)
            lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            if hasattr(self, "_update_maker_database_preview_canvas_scaled"):
                self._update_maker_database_preview_canvas_scaled()
        except Exception:
            pass

    def _maker_database_effective_value(self, db_kind, rec_id, field, fallback=""):
        """현재 DB 페이지의 번역문을 우선 적용한 표시값을 반환한다."""
        try:
            db_kind = str(db_kind or "").replace(".json", "")
            field = str(field or "")
            target_file = db_kind + ".json"
            _, rows = self._maker_database_page_rows_for_current()
            for r in rows:
                if not isinstance(r, dict):
                    continue
                unit = r.get("maker_text_unit") or {}
                if not isinstance(unit, dict):
                    continue
                source_file = str(unit.get("source_file") or "")
                if source_file and source_file.lower() != target_file.lower():
                    continue
                jp = str(unit.get("json_path") or unit.get("db_path") or "")
                if rec_id is not None and f"/{int(rec_id)}/" not in jp:
                    continue
                if field and not jp.endswith("/" + field) and str(unit.get("db_field") or unit.get("text_type") or "") != field:
                    continue
                dst = str(r.get("translated_text") or "").strip()
                if dst:
                    return dst
                src = str(r.get("text") or r.get("source_text") or "").strip()
                if src:
                    return src
        except Exception:
            pass
        return str(fallback if fallback is not None else "")

    def _maker_find_image_asset_for_db_preview(self, folder_name, base_name, *, category="images"):
        try:
            base_name = str(base_name or "").strip()
            if not base_name:
                return None
            root = Path(str(getattr(self, "project_dir", "") or ""))
            candidates = []
            for game_root in (root / "maker_game", root / "maker_game" / "www", root):
                for img_root in (game_root / "img" / folder_name,):
                    for ext in (".png", ".PNG", ".png_", ".PNG_", ".rpgmvp", ".rpgmvp_", ".webp", ".webp_", ".jpg", ".jpg_", ".jpeg", ".jpeg_"):
                        candidates.append(img_root / (base_name + ext))
                    try:
                        if img_root.is_dir():
                            wanted = base_name.lower()
                            for f in img_root.iterdir():
                                stem = f.name
                                for suf in (".png_", ".PNG_", ".rpgmvp_", ".rpgmvp", ".png", ".PNG", ".webp_", ".webp", ".jpg_", ".jpg", ".jpeg_", ".jpeg"):
                                    if stem.lower().endswith(suf.lower()):
                                        stem = stem[: -len(suf)]
                                        break
                                if stem.lower() == wanted:
                                    candidates.append(f)
                    except Exception:
                        pass
            for cand in candidates:
                try:
                    if cand.is_file():
                        if hasattr(self, "_maker_preview_prepare_image_asset"):
                            prepared, _diag = self._maker_preview_prepare_image_asset(cand, category=category)
                            if prepared and Path(prepared).is_file():
                                return Path(prepared)
                        return cand
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _maker_set_database_preview_pixmap(self, pixmap=None, text=""):
        try:
            lbl = getattr(self, "lbl_maker_database_preview_image", None)
            if lbl is None:
                return
            if pixmap is not None and not pixmap.isNull():
                lbl.setPixmap(pixmap.scaled(lbl.width(), lbl.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                lbl.setText("")
            else:
                lbl.clear()
                lbl.setText(str(text or "DB"))
        except Exception:
            pass

    def _maker_database_preview_face_pixmap(self, face_name, face_index=0):
        try:
            path = self._maker_find_image_asset_for_db_preview("faces", face_name, category="faces")
            if not path:
                return None
            pix = QPixmap(str(path))
            if pix.isNull():
                return None
            idx = max(0, int(face_index or 0))

            # RPG Maker MV/MZ default face graphics are 4 columns x 2 rows,
            # with each cell exactly 144x144.  Some games, however, use custom
            # one-image faces or non-standard face resolutions.  Dividing every
            # image by 4x2 can then crop only the top-left corner of a single
            # portrait, which is the distortion/cut-off case seen in MV DB
            # previews.
            if pix.width() >= 576 and pix.height() >= 288:
                cell_w = 144
                cell_h = 144
                x = (idx % 4) * cell_w
                y = (idx // 4) * cell_h
                if x + cell_w <= pix.width() and y + cell_h <= pix.height():
                    return pix.copy(x, y, cell_w, cell_h)

            # Non-standard but clearly sheet-like custom face graphics.  Only use
            # the 4x2 division when the derived cell is reasonably square; this
            # avoids treating a single large portrait as a sheet.
            if idx > 0 and pix.width() >= 4 and pix.height() >= 2:
                cell_w = max(1, pix.width() // 4)
                cell_h = max(1, pix.height() // 2)
                ratio = cell_w / max(1, cell_h)
                if 0.75 <= ratio <= 1.33:
                    x = (idx % 4) * cell_w
                    y = (idx // 4) * cell_h
                    if x + cell_w <= pix.width() and y + cell_h <= pix.height():
                        return pix.copy(x, y, cell_w, cell_h)

            # Custom single-face image.  Normalize to a 144x144 face source by
            # scaling with aspect ratio and center-cropping.  The status renderer
            # can then draw it into the usual face rectangle without stretching.
            target = 144
            out = QPixmap(target, target)
            out.fill(Qt.GlobalColor.transparent)
            painter = QPainter(out)
            try:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                scale = max(target / max(1, pix.width()), target / max(1, pix.height()))
                sw = max(1, int(round(pix.width() * scale)))
                sh = max(1, int(round(pix.height() * scale)))
                scaled = pix.scaled(sw, sh, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                dx = int((target - scaled.width()) / 2)
                dy = int((target - scaled.height()) / 2)
                painter.drawPixmap(dx, dy, scaled)
            finally:
                painter.end()
            return out
        except Exception:
            return None

    def _maker_database_preview_icon_pixmap(self, icon_index=0):
        try:
            icon_index = int(icon_index or 0)
            path = self._maker_find_image_asset_for_db_preview("system", "IconSet", category="system")
            if not path:
                return None
            pix = QPixmap(str(path))
            if pix.isNull():
                return None
            size = 32
            cols = max(1, pix.width() // size)
            x = (icon_index % cols) * size
            y = (icon_index // cols) * size
            if x + size > pix.width() or y + size > pix.height():
                return None
            return pix.copy(x, y, size, size)
        except Exception:
            return None

    def _db_preview_qcolor(self, value, fallback="#ffffff"):
        try:
            return QColor(str(value or fallback))
        except Exception:
            return QColor(str(fallback))

    def _maker_database_preview_set_canvas_pixmap(self, pixmap):
        try:
            self._maker_database_preview_raw_pixmap = pixmap
            # 새 DB 항목을 선택하면 우선 원본게임 화면 전체가 보이도록 맞춤 표시한다.
            # Ctrl+휠을 사용하면 _maker_database_preview_fit_mode가 False가 되어 배율 고정으로 전환된다.
            if not isinstance(getattr(self, "_maker_database_preview_zoom", None), (int, float)):
                self._maker_database_preview_zoom = 1.0
            if not hasattr(self, "_maker_database_preview_fit_mode"):
                self._maker_database_preview_fit_mode = True
            self._update_maker_database_preview_canvas_scaled()
        except Exception:
            pass

    def _maker_database_preview_viewport_size(self):
        try:
            scroll = getattr(self, "maker_database_preview_scroll", None)
            if scroll is not None and scroll.viewport() is not None:
                return scroll.viewport().size()
        except Exception:
            pass
        try:
            lbl = getattr(self, "lbl_maker_database_preview_canvas", None)
            return lbl.parentWidget().size() if lbl is not None and lbl.parentWidget() is not None else lbl.size()
        except Exception:
            return QSize(816, 624)

    def _maker_database_preview_fit_scale(self, pix=None):
        try:
            pix = pix or getattr(self, "_maker_database_preview_raw_pixmap", None)
            if pix is None or pix.isNull():
                return 1.0
            size = self._maker_database_preview_viewport_size()
            vw = max(1, int(size.width()) - 8)
            vh = max(1, int(size.height()) - 8)
            return max(0.05, min(float(vw) / max(1, pix.width()), float(vh) / max(1, pix.height())))
        except Exception:
            return 1.0

    def _maker_database_preview_zoom_by(self, wheel_delta):
        """DB 프리뷰 캔버스 Ctrl+휠 확대/축소."""
        try:
            pix = getattr(self, "_maker_database_preview_raw_pixmap", None)
            if pix is None or pix.isNull():
                return False
            current = float(getattr(self, "_maker_database_preview_zoom", 1.0) or 1.0)
            if bool(getattr(self, "_maker_database_preview_fit_mode", True)):
                current = self._maker_database_preview_fit_scale(pix)
            factor = 1.12 if int(wheel_delta or 0) > 0 else (1.0 / 1.12)
            self._maker_database_preview_zoom = max(0.10, min(6.0, current * factor))
            self._maker_database_preview_fit_mode = False
            self._update_maker_database_preview_canvas_scaled()
            return True
        except Exception:
            return False

    def reset_maker_database_preview_zoom_to_fit(self):
        try:
            self._maker_database_preview_fit_mode = True
            self._maker_database_preview_zoom = 1.0
            self._update_maker_database_preview_canvas_scaled()
            return True
        except Exception:
            return False

    def _update_maker_database_preview_canvas_scaled(self):
        try:
            lbl = getattr(self, "lbl_maker_database_preview_canvas", None)
            pix = getattr(self, "_maker_database_preview_raw_pixmap", None)
            if lbl is None:
                return
            if pix is None or pix.isNull():
                lbl.clear()
                lbl.setText(self.tr_ui("데이터베이스 프리뷰"))
                lbl.setFixedSize(max(320, lbl.minimumWidth()), max(240, lbl.minimumHeight()))
                return
            fit_mode = bool(getattr(self, "_maker_database_preview_fit_mode", True))
            if fit_mode:
                scale = self._maker_database_preview_fit_scale(pix)
            else:
                scale = float(getattr(self, "_maker_database_preview_zoom", 1.0) or 1.0)
            tw = max(1, int(round(pix.width() * scale)))
            th = max(1, int(round(pix.height() * scale)))
            scaled = pix.scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl.setFixedSize(scaled.size())
            lbl.setPixmap(scaled)
            lbl.setText("")
        except Exception:
            pass

    def _maker_database_new_canvas(self):
        w, h = self._maker_database_preview_geometry()
        pix = QPixmap(int(w), int(h))
        pix.fill(QColor(4, 5, 8))
        return pix

    def _maker_db_runtime_preview_settings(self):
        """Return DB-preview font/window settings derived from the real game profile.

        Database preview must use the RPG Maker game resources, not the editor UI
        language/font.  MZ games often declare a WOFF/WOFF2 main font; the normal
        Maker preview path already converts that into maker_meta/font_cache/*.ttf,
        so DB preview deliberately reuses the same resolver/cache.
        """
        st = {}
        try:
            st.update(self.current_maker_preview_settings() if hasattr(self, "current_maker_preview_settings") else {})
        except Exception:
            pass
        try:
            profile = self._maker_database_runtime_profile()
            font = profile.get("font") if isinstance(profile.get("font"), dict) else {}
            if font.get("family"):
                st["font_family"] = str(font.get("family") or "")
            # Prefer the already converted Qt-compatible path when present.
            # If the profile still points to WOFF, _maker_preview_resolve_font_family()
            # will convert/load maker_meta/font_cache/*.ttf just like message preview.
            for key in ("path", "source_font_path"):
                if font.get(key):
                    st["font_path"] = str(font.get(key) or "")
                    break
            for src, dst in (("main_font_filename", "main_font_filename"), ("number_font_filename", "number_font_filename"), ("fallback_fonts", "fallback_fonts")):
                if font.get(src):
                    st[dst] = str(font.get(src) or "")
            if font.get("size"):
                st["font_size"] = int(font.get("size") or 28)
        except Exception:
            pass
        return st

    def _maker_db_font(self, size=24, bold=False):
        family = "Malgun Gothic"
        try:
            st = self._maker_db_runtime_preview_settings()
            if hasattr(self, "_maker_preview_resolve_font_family"):
                family = self._maker_preview_resolve_font_family(st) or family
            else:
                family = str((st or {}).get("font_family") or family)
        except Exception:
            try:
                profile = self._maker_database_runtime_profile()
                font = profile.get("font") if isinstance(profile.get("font"), dict) else {}
                family = str(font.get("family") or family)
            except Exception:
                pass
        f = QFont(family)
        try:
            f.setPixelSize(max(6, min(160, int(size))))
        except Exception:
            f.setPointSize(max(8, int(size)))
        try:
            f.setBold(bool(bold))
        except Exception:
            pass
        return f

    def _maker_db_draw_text(self, painter, rect, text, size=24, color="#ffffff", bold=False, align=None, shadow=True, *, wrap=False, outline=False, outline_width=None):
        try:
            if align is None:
                align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            # DB preview must not auto-wrap text to the preview rectangle.
            # Show game/database values as-is: explicit newlines may render, but
            # long one-line fields should continue straight instead of being
            # visually wrapped by Qt.
            if wrap:
                align = align | Qt.TextFlag.TextWordWrap
            rect = QRectF(rect)
            font = self._maker_db_font(size, bold)
            painter.setFont(font)
            text = str(text or "")
            if outline:
                ow = outline_width
                if ow is None:
                    try:
                        profile = self._maker_database_runtime_profile()
                        ff = profile.get("font") if isinstance(profile.get("font"), dict) else {}
                        ow = int(ff.get("outline_width") or 3)
                    except Exception:
                        ow = 3
                ow = max(1, min(8, int(ow)))
                painter.setPen(QColor(0, 0, 0, 170))
                # QPainter does not expose the Canvas strokeText path directly, so
                # approximate MZ's outline by drawing the same glyph around the
                # target position.  This is closer to Bitmap.drawText than a single
                # drop shadow and keeps game fonts readable on Window.png.
                for dx in range(-ow, ow + 1):
                    for dy in range(-ow, ow + 1):
                        if dx == 0 and dy == 0:
                            continue
                        if dx * dx + dy * dy > ow * ow + 1:
                            continue
                        painter.drawText(rect.translated(dx, dy), int(align), text)
            elif shadow:
                painter.setPen(QColor(0, 0, 0, 210))
                painter.drawText(rect.adjusted(2, 2, 2, 2), int(align), text)
            painter.setPen(self._db_preview_qcolor(color))
            painter.drawText(rect, int(align), text)
        except Exception:
            pass

    def _maker_db_window_opacity(self):
        try:
            profile = self._maker_database_runtime_profile()
            win = profile.get("window") if isinstance(profile.get("window"), dict) else {}
            return max(0, min(255, int(win.get("opacity") or 205)))
        except Exception:
            return 205

    def _maker_db_draw_window(self, painter, rect, fill=None, border="#75a9ff", width=3, *, profile=None):
        try:
            r = QRectF(rect)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            pm = None
            if hasattr(self, "_maker_preview_build_window_pixmap"):
                try:
                    prof = profile if isinstance(profile, dict) else self._maker_database_runtime_profile()
                    pm, _diag = self._maker_preview_build_window_pixmap(int(round(r.width())), int(round(r.height())), opacity=self._maker_db_window_opacity(), profile=prof)
                except Exception:
                    pm = None
            if pm is not None and not pm.isNull():
                painter.drawPixmap(r.toRect(), pm)
                painter.restore()
                return
            if fill is None:
                fill = QColor(18, 20, 22, 222)
            painter.fillRect(r, fill)
            pen = QPen(self._db_preview_qcolor(border), int(width))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r.adjusted(1, 1, -2, -2))
            painter.setPen(QPen(QColor(190, 220, 255, 140), 1))
            painter.drawRect(r.adjusted(5, 5, -6, -6))
            painter.restore()
        except Exception:
            pass

    def _maker_db_draw_pattern_bg(self, painter, rect):
        try:
            r = QRectF(rect)
            grad = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
            grad.setColorAt(0.0, QColor(22, 24, 28))
            grad.setColorAt(1.0, QColor(5, 6, 8))
            painter.fillRect(r, grad)
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
            step = 6
            x = int(r.left()) - int(r.height())
            while x < r.right():
                painter.drawLine(QPointF(x, r.bottom()), QPointF(x + r.height(), r.top()))
                x += step
        except Exception:
            pass

    def _maker_db_draw_gauge(self, painter, x, y, w, h, ratio, color):
        try:
            painter.fillRect(QRectF(x, y, w, h), QColor(40, 40, 46, 230))
            painter.fillRect(QRectF(x, y, max(0, min(w, int(w * float(ratio)))), h), self._db_preview_qcolor(color))
            painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
            painter.drawRect(QRectF(x, y, w, h))
        except Exception:
            pass

    def _maker_db_canvas_finalize(self, painter):
        try:
            painter.end()
        except Exception:
            pass

    def _maker_db_effective_json_path_value(self, source_file, json_path, fallback=""):
        """Return translated/source row text for an exact Maker JSON path."""
        try:
            target_file = str(source_file or "").strip()
            if target_file and not target_file.lower().endswith(".json"):
                target_file += ".json"
            wanted = "/" + "/".join([x for x in str(json_path or "").strip().split("/") if x])
            _, rows = self._maker_database_page_rows_for_current()
            for r in rows:
                if not isinstance(r, dict):
                    continue
                unit = r.get("maker_text_unit") or {}
                if not isinstance(unit, dict):
                    continue
                sf = str(unit.get("source_file") or "")
                if target_file and sf.lower() != target_file.lower():
                    continue
                jp = str(unit.get("json_path") or unit.get("db_path") or "")
                jp_norm = "/" + "/".join([x for x in jp.split("/") if x and not x.lower().endswith(".json")])
                if jp_norm != wanted and not jp_norm.endswith(wanted):
                    continue
                dst = str(r.get("translated_text") or "").strip()
                if dst:
                    return dst
                src = str(r.get("text") or r.get("source_text") or "").strip()
                if src:
                    return src
        except Exception:
            pass
        return str(fallback if fallback is not None else "")

    def _maker_db_mz_text_color(self, color_index, fallback="#ffffff"):
        """Sample MZ ColorManager.textColor(n) from the game's Window.png."""
        try:
            idx = int(color_index or 0)
            cache = getattr(self, "_maker_db_window_text_color_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                self._maker_db_window_text_color_cache = cache
            profile = self._maker_database_runtime_profile()
            path, _diag = self._maker_preview_window_skin_path(profile=profile) if hasattr(self, "_maker_preview_window_skin_path") else (None, {})
            key = (str(path or ""), idx)
            if key in cache:
                return cache[key]
            if path:
                pm = QPixmap(str(path))
                if not pm.isNull() and pm.width() >= 192 and pm.height() >= 180:
                    # rmmz_core ColorManager.textColor: px = 96 + (n % 8) * 12 + 6,
                    # py = 144 + Math.floor(n / 8) * 12 + 6
                    x = 96 + (idx % 8) * 12 + 6
                    y = 144 + (idx // 8) * 12 + 6
                    if 0 <= x < pm.width() and 0 <= y < pm.height():
                        c = pm.toImage().pixelColor(int(x), int(y))
                        if c.isValid():
                            cache[key] = c.name(QColor.NameFormat.HexRgb)
                            return cache[key]
        except Exception:
            pass
        return str(fallback or "#ffffff")

    def _maker_db_mz_basic_term(self, system, index, fallback=""):
        try:
            arr = ((system.get("terms") or {}).get("basic") or []) if isinstance(system, dict) else []
            value = arr[int(index)] if int(index) < len(arr) else fallback
            return self._maker_db_effective_json_path_value("System.json", f"/terms/basic/{int(index)}", value)
        except Exception:
            return str(fallback or "")

    def _maker_db_mz_command_term(self, system, index, fallback=""):
        try:
            arr = ((system.get("terms") or {}).get("commands") or []) if isinstance(system, dict) else []
            idx = int(index)
            value = arr[idx] if 0 <= idx < len(arr) and arr[idx] not in (None, "") else fallback
            return self._maker_db_effective_json_path_value("System.json", f"/terms/commands/{idx}", value)
        except Exception:
            return str(fallback or "")

    def _maker_db_mz_skill_type_name(self, system, stype_id, fallback=""):
        try:
            arr = system.get("skillTypes") if isinstance(system, dict) else []
            idx = int(stype_id or 0)
            value = arr[idx] if isinstance(arr, list) and 0 <= idx < len(arr) and arr[idx] not in (None, "") else fallback
            return self._maker_db_effective_json_path_value("System.json", f"/skillTypes/{idx}", value)
        except Exception:
            return str(fallback or "")

    def _maker_db_mz_item_category_name(self, system, key):
        # RPG Maker MZ TextManager command indices used by Window_ItemCategory.
        # Fallbacks are engine-like labels, but real projects should supply these
        # through System.json terms/commands and translation rows.
        mapping = {
            "item": (4, "Item"),
            "weapon": (12, "Weapon"),
            "armor": (13, "Armor"),
            "keyItem": (14, "Key Item"),
            "skill": (5, "Skill"),
        }
        try:
            idx, fallback = mapping.get(str(key or ""), (None, str(key or "")))
            if idx is None:
                return fallback
            return self._maker_db_mz_command_term(system, idx, fallback)
        except Exception:
            return str(key or "")

    def _maker_db_mz_param_term(self, system, index, fallback=""):
        try:
            arr = ((system.get("terms") or {}).get("params") or []) if isinstance(system, dict) else []
            value = arr[int(index)] if int(index) < len(arr) else fallback
            return self._maker_db_effective_json_path_value("System.json", f"/terms/params/{int(index)}", value)
        except Exception:
            return str(fallback or "")

    def _maker_db_mz_message_term(self, system, key, fallback=""):
        try:
            msgs = ((system.get("terms") or {}).get("messages") or {}) if isinstance(system, dict) else {}
            value = msgs.get(str(key)) if isinstance(msgs, dict) else None
            if value in (None, ""):
                value = fallback
            return self._maker_db_effective_json_path_value("System.json", f"/terms/messages/{key}", value)
        except Exception:
            return str(fallback or "")

    def _maker_db_mz_format_term(self, template, value):
        try:
            t = str(template or "")
            if "%1" in t:
                return t.replace("%1", str(value or ""))
            return t.format(value)
        except Exception:
            return str(template or "")

    def _maker_db_mz_equip_type_name(self, system, equip_type_id, fallback=""):
        try:
            arr = system.get("equipTypes") if isinstance(system, dict) else []
            idx = int(equip_type_id or 0)
            value = arr[idx] if isinstance(arr, list) and 0 <= idx < len(arr) else fallback
            return self._maker_db_effective_json_path_value("System.json", f"/equipTypes/{idx}", value)
        except Exception:
            return str(fallback or "")

    def _maker_db_actor_param_values_with_equips(self, record, classes, weapons, armors, level):
        vals = [0] * 8
        try:
            cid = int((record or {}).get("classId") or 0)
            if 0 <= cid < len(classes) and classes[cid]:
                ptable = (classes[cid] or {}).get("params") or []
                for i in range(min(8, len(ptable))):
                    row = ptable[i]
                    if isinstance(row, list) and row:
                        vals[i] = int(row[min(max(1, int(level or 1)), len(row) - 1)] or 0)
        except Exception:
            pass
        try:
            for pos, eid in enumerate((record or {}).get("equips") or []):
                eid = int(eid or 0)
                if eid <= 0:
                    continue
                src_list = weapons if pos == 0 else armors
                if 0 <= eid < len(src_list) and src_list[eid]:
                    params = (src_list[eid] or {}).get("params") or []
                    for i in range(min(8, len(params))):
                        vals[i] += int(params[i] or 0)
        except Exception:
            pass
        return vals

    def _maker_db_draw_gauge_gradient(self, painter, x, y, w, h, ratio, color1, color2=None, back_color=None):
        try:
            x, y, w, h = int(x), int(y), int(w), int(h)
            if back_color is None:
                back_color = self._maker_db_mz_text_color(19, "#202040")
            painter.fillRect(QRectF(x, y, w, h), self._db_preview_qcolor(back_color))
            fill_w = max(0, min(w, int(round(w * float(ratio)))))
            if fill_w > 0:
                grad = QLinearGradient(x, y, x + fill_w, y)
                grad.setColorAt(0.0, self._db_preview_qcolor(color1))
                grad.setColorAt(1.0, self._db_preview_qcolor(color2 or color1))
                painter.fillRect(QRectF(x, y, fill_w, h), grad)
        except Exception:
            self._maker_db_draw_gauge(painter, x, y, w, h, ratio, color1)

    def _maker_db_draw_icon_item_name_mz(self, painter, item, x, y, width, size, normal_color, *, sx=1.0, sy=1.0):
        try:
            item = item if isinstance(item, dict) else None
            if not item:
                return
            icon_index = int(item.get("iconIndex") or 0)
            name = str(item.get("_preview_name") or item.get("name") or "")
            icon = self._maker_database_preview_icon_pixmap(icon_index)
            ix, iy = int(x), int(y + max(0, (36 * sy - 32 * sy) / 2))
            if icon and not icon.isNull():
                painter.drawPixmap(QRectF(ix, iy, 32 * sx, 32 * sy).toRect(), icon)
                tx = x + 36 * sx
                tw = max(1, width - 36 * sx)
            else:
                tx = x
                tw = width
            self._maker_db_draw_text(painter, QRectF(tx, y, tw, 36 * sy), name, size, normal_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        except Exception:
            pass

    def _maker_db_record_list(self, filename):
        data = self._load_maker_database_json_runtime(filename) or []
        return data if isinstance(data, list) else []

    def _maker_db_selected_index_from_record(self, record, fallback=1):
        try:
            if isinstance(record, dict):
                rid = record.get("id")
                if rid not in (None, ""):
                    return int(rid)
        except Exception:
            pass
        try:
            return int(fallback or 1)
        except Exception:
            return 1

    def _maker_db_mz_rect(self, x, y, w, h, sx=1.0, sy=1.0):
        return QRectF(float(x) * sx, float(y) * sy, float(w) * sx, float(h) * sy)

    def _maker_db_draw_mz_button(self, painter, rect, text):
        try:
            r = QRectF(rect)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            grad = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
            grad.setColorAt(0.0, QColor(46, 47, 48, 235))
            grad.setColorAt(1.0, QColor(4, 4, 4, 235))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(r, 10, 10)
            self._maker_db_draw_text(painter, r.adjusted(0, 3, 0, 0), text, 30, "#ffffff", True, Qt.AlignmentFlag.AlignCenter, True)
            painter.restore()
        except Exception:
            pass

    def _maker_render_actor_database_canvas_mz(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        """Render the Actor status preview by porting RPG Maker MZ's status scene.

        The DB preview is a game-screen reconstruction: labels come from
        System.json terms, actor/class/equipment data comes from the game DB, the
        font is resolved through the WOFF->TTF cache, and windows/colors are taken
        from Window.png whenever available.
        """
        pix = self._maker_database_new_canvas()
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = pix.width(), pix.height()
        sx, sy = w / 1280.0, h / 720.0
        ss = min(sx, sy)
        profile = self._maker_database_runtime_profile()
        win = profile.get("window") if isinstance(profile.get("window"), dict) else {}
        font_prof = profile.get("font") if isinstance(profile.get("font"), dict) else {}
        try:
            padding = int(win.get("padding") or 12)
        except Exception:
            padding = 12
        try:
            line_h = int((profile.get("message_window") if isinstance(profile.get("message_window"), dict) else {}).get("line_height") or 36)
        except Exception:
            line_h = 36
        try:
            font_size = int(font_prof.get("size") or 28)
        except Exception:
            font_size = 28
        try:
            box_margin = int((profile.get("message_window") if isinstance(profile.get("message_window"), dict) else {}).get("box_margin") or 4)
        except Exception:
            box_margin = 4

        record = record if isinstance(record, dict) else {}
        system = self._load_maker_database_json_runtime("System.json") or {}
        classes = self._maker_db_record_list("Classes.json")
        weapons = self._maker_db_record_list("Weapons.json")
        armors = self._maker_db_record_list("Armors.json")

        # Background: the actual Scene_Status blurs the current scene.  In DB mode
        # there is no live scene stack, so use the same darkened canvas base and
        # keep all foreground coordinates as real MZ screen pixels.
        self._maker_db_draw_pattern_bg(painter, QRectF(0, 0, w, h))

        # MZ Scene_Status layout.  This follows the engine relationship rather
        # than hand-tuned panel coordinates:
        # profile = calcWindowHeight(2), params/equip = calcWindowHeight(6),
        # status window fills from mainAreaTop to the params row.
        def calc_window_height(num_lines):
            return int(line_h * int(num_lines) + padding * 2)

        show_touch_buttons = bool(system.get("optTouchUI", True))
        button_area_h = 52 if show_touch_buttons else 0
        status_y = box_margin + button_area_h
        profile_h = calc_window_height(2)
        params_h = calc_window_height(6)
        profile_y = max(status_y + 120, h - box_margin - profile_h)
        params_y = max(status_y + 120, profile_y - box_margin - params_h)
        status_h = max(96, params_y - box_margin - status_y)
        wx = box_margin
        ww = max(1, w - box_margin * 2)
        params_w = int(round(300 * sx))
        top_rect = QRectF(wx, status_y, ww, status_h)
        param_rect = QRectF(wx, params_y, params_w, params_h)
        equip_rect = QRectF(wx + params_w + box_margin, params_y, max(1, ww - params_w - box_margin), params_h)
        profile_rect = QRectF(wx, profile_y, ww, profile_h)

        if show_touch_buttons:
            self._maker_db_draw_mz_button(painter, QRectF(box_margin + 8, box_margin + 2, 50 * sx, 48 * sy), "<")
            self._maker_db_draw_mz_button(painter, QRectF(box_margin + 66, box_margin + 2, 50 * sx, 48 * sy), ">")
            self._maker_db_draw_mz_button(painter, QRectF(w - box_margin - 62 * sx, box_margin + 2, 54 * sx, 48 * sy), "↩")

        for r in (top_rect, param_rect, equip_rect, profile_rect):
            self._maker_db_draw_window(painter, r, width=max(2, int(3 * ss)), profile=profile)

        normal = self._maker_db_mz_text_color(0, "#ffffff")
        system_color = self._maker_db_mz_text_color(16, "#80aaff")
        hp1 = self._maker_db_mz_text_color(20, "#e08040")
        hp2 = self._maker_db_mz_text_color(21, "#f0c040")
        mp1 = self._maker_db_mz_text_color(22, "#4080c0")
        mp2 = self._maker_db_mz_text_color(23, "#40c0f0")
        tp1 = self._maker_db_mz_text_color(28, "#8060c0")
        tp2 = self._maker_db_mz_text_color(29, "#c060ff")
        text_size = max(12, int(font_size * ss))
        small_size = max(11, int((font_size - 4) * ss))

        name = self._maker_database_effective_value("Actors", rec_id, "name", record.get("name") or shown)
        nickname = self._maker_database_effective_value("Actors", rec_id, "nickname", record.get("nickname") or "")
        profile_text = self._maker_database_effective_value("Actors", rec_id, "profile", record.get("profile") or "")
        level = int(record.get("initialLevel") or 1)
        class_name = ""
        try:
            cid = int(record.get("classId") or 0)
            if 0 <= cid < len(classes) and classes[cid]:
                class_name = self._maker_database_effective_value("Classes", cid, "name", (classes[cid] or {}).get("name") or "")
        except Exception:
            pass
        vals = self._maker_db_actor_param_values_with_equips(record, classes, weapons, armors, level)

        # Content origins are Window_Base.innerRect origins: window x/y + padding.
        cx = top_rect.x() + padding * sx
        cy = top_rect.y() + padding * sy
        lh = line_h * sy
        pad_x = padding * sx

        # Window_Status.drawBlock1() equivalent.
        y1 = cy
        self._maker_db_draw_text(painter, QRectF(cx + 6 * sx, y1, 168 * sx, lh), name, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(cx + 192 * sx, y1, 168 * sx, lh), class_name, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(cx + 432 * sx, y1, 270 * sx, lh), nickname, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        # Window_Status.drawBlock2(): face, basic info, exp info.
        block2_y = cy + line_h * 2 * sy
        face = self._maker_database_preview_face_pixmap(record.get("faceName"), record.get("faceIndex"))
        if face and not face.isNull():
            # Face graphics must stay square.  Custom MV/MZ screen sizes can make
            # sx and sy differ, so use the uniform status scale for image assets.
            face_size = 144 * ss
            painter.drawPixmap(QRectF(cx + 12 * sx, block2_y, face_size, face_size).toRect(), face)

        basic_x = cx + 204 * sx
        exp_x = cx + 456 * sx
        level_a = self._maker_db_mz_basic_term(system, 1, "Lv") or "Lv"
        hp_a = self._maker_db_mz_basic_term(system, 3, "HP") or "HP"
        mp_a = self._maker_db_mz_basic_term(system, 5, "MP") or "MP"
        tp_a = self._maker_db_mz_basic_term(system, 7, "TP") or "TP"
        exp_name = self._maker_db_mz_basic_term(system, 8, "EXP") or "EXP"
        level_name = self._maker_db_mz_basic_term(system, 0, "Level") or "Level"
        exp_total_t = self._maker_db_mz_message_term(system, "expTotal", "現在の%1")
        exp_next_t = self._maker_db_mz_message_term(system, "expNext", "次の%1まで")
        exp_total = self._maker_db_mz_format_term(exp_total_t, exp_name)
        exp_next = self._maker_db_mz_format_term(exp_next_t, level_name)

        self._maker_db_draw_text(painter, QRectF(basic_x, block2_y, 48 * sx, lh), level_a, text_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(basic_x + 84 * sx, block2_y, 48 * sx, lh), str(level), text_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        gauge_x = basic_x
        gauge_w = 128 * sx
        gauge_h = max(6, int(12 * sy))
        for row_i, (label, value, c1, c2, ratio) in enumerate((
            (hp_a, vals[0], hp1, hp2, 1.0),
            (mp_a, vals[1], mp1, mp2, 1.0),
            (tp_a, "", tp1, tp2, 0.0),
        )):
            gy = block2_y + (2 + row_i) * lh
            self._maker_db_draw_text(painter, QRectF(gauge_x, gy, 44 * sx, lh), label, small_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
            self._maker_db_draw_gauge_gradient(painter, gauge_x + 34 * sx, gy + 20 * sy, gauge_w, gauge_h, ratio, c1, c2)
            if value != "":
                self._maker_db_draw_text(painter, QRectF(gauge_x + 34 * sx, gy - 1 * sy, gauge_w, lh), str(value), small_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        self._maker_db_draw_text(painter, QRectF(exp_x, block2_y, 270 * sx, lh), exp_total, text_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(exp_x, block2_y + lh, 270 * sx, lh), "-------", text_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(exp_x, block2_y + lh * 2, 270 * sx, lh), exp_next, text_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(exp_x, block2_y + lh * 3, 270 * sx, lh), "-------", text_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        # Window_StatusParams.drawItem(): six params from ATK to LUK, including
        # equipment bonuses so the preview matches the game's status screen.
        pcx = param_rect.x() + padding * sx
        pcy = param_rect.y() + padding * sy
        for row_i, idx in enumerate([2, 3, 4, 5, 6, 7]):
            y = pcy + row_i * lh
            label = self._maker_db_mz_param_term(system, idx, str(idx))
            self._maker_db_draw_text(painter, QRectF(pcx + 8 * sx, y, 150 * sx, lh), label, text_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
            self._maker_db_draw_text(painter, QRectF(pcx + 160 * sx, y, 92 * sx, lh), str(vals[idx] or ""), text_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        # Window_StatusEquip.drawItem().  Slot labels use System.json equipTypes;
        # item names/icons use Weapons/Armors records, with translated DB rows if present.
        ecx = equip_rect.x() + padding * sx
        ecy = equip_rect.y() + padding * sy
        equip_types = system.get("equipTypes") if isinstance(system.get("equipTypes"), list) else []
        equips = []
        try:
            for pos, eid in enumerate(record.get("equips") or []):
                eid = int(eid or 0)
                if eid <= 0:
                    item = None
                else:
                    src_list = weapons if pos == 0 else armors
                    item = dict(src_list[eid]) if 0 <= eid < len(src_list) and src_list[eid] else None
                    if item is not None:
                        k = "Weapons" if pos == 0 else "Armors"
                        item["_preview_name"] = self._maker_database_effective_value(k, eid, "name", item.get("name") or "")
                etype_id = 1
                try:
                    if item is not None and int(item.get("etypeId") or 0) > 0:
                        etype_id = int(item.get("etypeId") or 0)
                    elif pos + 1 < len(equip_types):
                        etype_id = pos + 1
                except Exception:
                    etype_id = pos + 1
                slot = self._maker_db_mz_equip_type_name(system, etype_id, f"Equip {pos + 1}")
                equips.append((slot, item))
        except Exception:
            pass
        slot_w = 138 * sx
        for i, (slot, item) in enumerate(equips[:6]):
            y = ecy + i * lh
            self._maker_db_draw_text(painter, QRectF(ecx + 8 * sx, y, slot_w, lh), slot, text_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
            if item:
                self._maker_db_draw_icon_item_name_mz(painter, item, ecx + 8 * sx + slot_w, y, max(1, equip_rect.width() - padding * 2 * sx - 8 * sx - slot_w), text_size, normal, sx=sx, sy=sy)

        # Profile window.  MZ drawTextEx handles wrapping through escape processing;
        # here we keep the game text and use the game font inside the real profile
        # window rectangle.
        prx = profile_rect.x() + padding * sx
        pry = profile_rect.y() + padding * sy
        self._maker_db_draw_text(painter, QRectF(prx + 8 * sx, pry, profile_rect.width() - padding * 2 * sx - 16 * sx, profile_rect.height() - padding * 2 * sy), profile_text, max(12, text_size), normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, False, wrap=False, outline=True)
        self._maker_db_canvas_finalize(painter)
        return pix


    def _maker_render_actor_database_canvas_mv(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        """Render the Actor status preview by porting RPG Maker MV Window_Status.

        MV and MZ are intentionally kept separate here.  MV's database/status
        screen is a single Window_Status with drawBlock1~4 and 816x624 default
        coordinates; it must not reuse the MZ split-window layout.
        """
        pix = self._maker_database_new_canvas()
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = pix.width(), pix.height()
        sx, sy = w / 816.0, h / 624.0
        ss = min(sx, sy)
        profile = self._maker_database_runtime_profile()
        win = profile.get("window") if isinstance(profile.get("window"), dict) else {}
        font_prof = profile.get("font") if isinstance(profile.get("font"), dict) else {}
        msg = profile.get("message_window") if isinstance(profile.get("message_window"), dict) else {}
        try:
            padding = int(win.get("padding") or 18)
        except Exception:
            padding = 18
        try:
            line_h0 = int(msg.get("line_height") or 36)
        except Exception:
            line_h0 = 36
        try:
            font_size0 = int(font_prof.get("size") or 28)
        except Exception:
            font_size0 = 28
        pad_x, pad_y = padding * sx, padding * sy
        line_h = line_h0 * sy
        text_size = max(12, int(font_size0 * ss))
        small_size = max(11, int((font_size0 - 4) * ss))

        record = record if isinstance(record, dict) else {}
        system = self._load_maker_database_json_runtime("System.json") or {}
        classes = self._maker_db_record_list("Classes.json")
        weapons = self._maker_db_record_list("Weapons.json")
        armors = self._maker_db_record_list("Armors.json")

        # Scene_Status has no game map background; it displays the status window
        # over a dark scene background.  Keep one real Window_Status rectangle.
        self._maker_db_draw_pattern_bg(painter, QRectF(0, 0, w, h))
        full_rect = QRectF(0, 0, w, h)
        self._maker_db_draw_window(painter, full_rect, width=max(1, int(2 * ss)), profile=profile)

        normal = self._maker_db_mz_text_color(0, "#ffffff")
        system_color = self._maker_db_mz_text_color(16, "#80aaff")
        hp1 = self._maker_db_mz_text_color(20, "#e08040")
        hp2 = self._maker_db_mz_text_color(21, "#f0c040")
        mp1 = self._maker_db_mz_text_color(22, "#4080c0")
        mp2 = self._maker_db_mz_text_color(23, "#40c0f0")

        name = self._maker_database_effective_value("Actors", rec_id, "name", record.get("name") or shown)
        nickname = self._maker_database_effective_value("Actors", rec_id, "nickname", record.get("nickname") or "")
        profile_text = self._maker_database_effective_value("Actors", rec_id, "profile", record.get("profile") or "")
        level = int(record.get("initialLevel") or 1)
        class_name = ""
        try:
            cid = int(record.get("classId") or 0)
            if 0 <= cid < len(classes) and classes[cid]:
                class_name = self._maker_database_effective_value("Classes", cid, "name", (classes[cid] or {}).get("name") or "")
        except Exception:
            pass
        vals = self._maker_db_actor_param_values_with_equips(record, classes, weapons, armors, level)

        def rx(v):
            return pad_x + float(v) * sx
        def ry(v):
            return pad_y + float(v) * sy
        def rw(v):
            return float(v) * sx
        def rh(v):
            return float(v) * sy

        def draw_horz_line(y_base):
            try:
                y = ry(y_base) + line_h / 2 - 1
                x1 = rx(0)
                x2 = w - pad_x
                painter.save()
                c = self._db_preview_qcolor(normal)
                c.setAlpha(70)
                painter.setPen(QPen(c, max(1, int(2 * ss))))
                painter.drawLine(QPointF(x1, y), QPointF(x2, y))
                painter.restore()
            except Exception:
                pass

        # Window_Status.drawBlock1(y=0)
        y0 = 0
        self._maker_db_draw_text(painter, QRectF(rx(6), ry(y0), rw(168), line_h), name, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(rx(192), ry(y0), rw(168), line_h), class_name, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(rx(432), ry(y0), rw(270), line_h), nickname, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        draw_horz_line(line_h0)

        # Window_Status.drawBlock2(y=lineHeight*2)
        block2_y = line_h0 * 2
        face = self._maker_database_preview_face_pixmap(record.get("faceName"), record.get("faceIndex"))
        if face and not face.isNull():
            # Keep the actor face aspect ratio exactly like RPG Maker's 144x144
            # face blit.  The status window coordinates may stretch with the
            # project screen, but the face itself must not be non-uniformly scaled.
            face_size = 144 * ss
            painter.drawPixmap(QRectF(rx(12), ry(block2_y), face_size, face_size).toRect(), face)

        basic_x = 204
        exp_x = 456
        level_a = self._maker_db_mz_basic_term(system, 1, "Lv") or "Lv"
        hp_a = self._maker_db_mz_basic_term(system, 3, "HP") or "HP"
        mp_a = self._maker_db_mz_basic_term(system, 5, "MP") or "MP"
        exp_name = self._maker_db_mz_basic_term(system, 8, "EXP") or "EXP"
        level_name = self._maker_db_mz_basic_term(system, 0, "Level") or "Level"
        exp_total = self._maker_db_mz_format_term(self._maker_db_mz_message_term(system, "expTotal", "Current %1"), exp_name)
        exp_next = self._maker_db_mz_format_term(self._maker_db_mz_message_term(system, "expNext", "To Next %1"), level_name)

        # drawActorLevel
        self._maker_db_draw_text(painter, QRectF(rx(basic_x), ry(block2_y), rw(48), line_h), level_a, text_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(rx(basic_x + 84), ry(block2_y), rw(48), line_h), str(level), text_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        def draw_param_gauge(label, value, y_row, c1, c2):
            gy = ry(y_row)
            gx = rx(basic_x)
            gw = rw(186)
            self._maker_db_draw_text(painter, QRectF(gx, gy, rw(44), line_h), label, small_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
            self._maker_db_draw_gauge_gradient(painter, gx + rw(44), gy + line_h - rh(8), gw - rw(44), max(6, int(6 * sy)), 1.0, c1, c2)
            self._maker_db_draw_text(painter, QRectF(gx + rw(44), gy, gw - rw(44), line_h), str(value), small_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        # MV default status shows HP/MP here.  TP is not inserted unless plugins do it.
        draw_param_gauge(hp_a, vals[0], block2_y + line_h0 * 2, hp1, hp2)
        draw_param_gauge(mp_a, vals[1], block2_y + line_h0 * 3, mp1, mp2)

        self._maker_db_draw_text(painter, QRectF(rx(exp_x), ry(block2_y), rw(270), line_h), exp_total, text_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(rx(exp_x), ry(block2_y + line_h0), rw(270), line_h), "-------", text_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(rx(exp_x), ry(block2_y + line_h0 * 2), rw(270), line_h), exp_next, text_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        self._maker_db_draw_text(painter, QRectF(rx(exp_x), ry(block2_y + line_h0 * 3), rw(270), line_h), "-------", text_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        draw_horz_line(line_h0 * 6)

        # Window_Status.drawBlock3(y=lineHeight*7)
        block3_y = line_h0 * 7
        for i, idx in enumerate([2, 3, 4, 5, 6, 7]):
            y = block3_y + line_h0 * i
            label = self._maker_db_mz_param_term(system, idx, str(idx))
            self._maker_db_draw_text(painter, QRectF(rx(48), ry(y), rw(160), line_h), label, text_size, system_color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
            self._maker_db_draw_text(painter, QRectF(rx(208), ry(y), rw(60), line_h), str(vals[idx] or ""), text_size, normal, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        equip_items = []
        try:
            for pos, eid in enumerate(record.get("equips") or []):
                eid = int(eid or 0)
                src_list = weapons if pos == 0 else armors
                item = None
                if eid > 0 and 0 <= eid < len(src_list) and src_list[eid]:
                    item = dict(src_list[eid] or {})
                    k = "Weapons" if pos == 0 else "Armors"
                    item["_preview_name"] = self._maker_database_effective_value(k, eid, "name", item.get("name") or "")
                equip_items.append(item)
        except Exception:
            pass
        for i, item in enumerate(equip_items[:6]):
            y = block3_y + line_h0 * i
            if item:
                self._maker_db_draw_icon_item_name_mz(painter, item, rx(432), ry(y), rw(300), text_size, normal, sx=sx, sy=sy)
        draw_horz_line(line_h0 * 13)

        # Window_Status.drawBlock4(y=lineHeight*14)
        block4_y = line_h0 * 14
        self._maker_db_draw_text(painter, QRectF(rx(6), ry(block4_y), w - pad_x * 2 - rw(12), h - ry(block4_y) - pad_y), profile_text, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, False, wrap=False, outline=True)
        self._maker_db_canvas_finalize(painter)
        return pix

    def _maker_render_actor_database_canvas(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        engine = self._maker_database_engine_key()
        if engine == "mz":
            return self._maker_render_actor_database_canvas_mz(row_data, unit, db_kind, rec_id, field, record, src, shown)
        if engine == "mv":
            return self._maker_render_actor_database_canvas_mv(row_data, unit, db_kind, rec_id, field, record, src, shown)
        return self._maker_render_actor_database_canvas_mv(row_data, unit, db_kind, rec_id, field, record, src, shown)


    def _maker_render_item_like_database_canvas_mv(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        """Render item/skill/equipment DB rows using RPG Maker MV scene geometry."""
        pix = self._maker_database_new_canvas()
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = pix.width(), pix.height()
        sx, sy = w / 816.0, h / 624.0
        ss = min(sx, sy)
        profile = self._maker_database_runtime_profile()
        win = profile.get("window") if isinstance(profile.get("window"), dict) else {}
        font_prof = profile.get("font") if isinstance(profile.get("font"), dict) else {}
        msg = profile.get("message_window") if isinstance(profile.get("message_window"), dict) else {}
        try:
            padding = int(win.get("padding") or 18)
        except Exception:
            padding = 18
        try:
            line_h0 = int(msg.get("line_height") or 36)
        except Exception:
            line_h0 = 36
        try:
            font_size0 = int(font_prof.get("size") or 28)
        except Exception:
            font_size0 = 28
        line_h = line_h0 * sy
        text_size = max(12, int(font_size0 * ss))
        small_size = max(11, int((font_size0 - 4) * ss))
        kind = str(db_kind or "")
        system = self._load_maker_database_json_runtime("System.json") or {}
        record = record if isinstance(record, dict) else {}
        db_file = {"Items": "Items.json", "Weapons": "Weapons.json", "Armors": "Armors.json", "Skills": "Skills.json"}.get(kind, str(kind) + ".json")
        records = self._maker_db_record_list(db_file)
        cur_id = rec_id if rec_id is not None else self._maker_db_selected_index_from_record(record, 1)

        normal = self._maker_db_mz_text_color(0, "#ffffff")
        system_color = self._maker_db_mz_text_color(16, "#80aaff")
        crisis_color = self._maker_db_mz_text_color(17, "#ff8080")
        mp_color = self._maker_db_mz_text_color(23, "#40c0f0")
        tp_color = self._maker_db_mz_text_color(29, "#c060ff")

        self._maker_db_draw_pattern_bg(painter, QRectF(0, 0, w, h))
        help_h = int((line_h0 * 2 + padding * 2) * sy)
        command_h = int((line_h0 + padding * 2) * sy)
        if kind == "Skills":
            type_w = int(240 * sx)
            help_rect = QRectF(0, 0, w, help_h)
            type_rect = QRectF(0, help_h, type_w, h - help_h)
            list_rect = QRectF(type_w, help_h, w - type_w, h - help_h)
            draw_rects = (help_rect, type_rect, list_rect)
        else:
            help_rect = QRectF(0, 0, w, help_h)
            category_rect = QRectF(0, help_h, w, command_h)
            list_rect = QRectF(0, help_h + command_h, w, h - help_h - command_h)
            draw_rects = (help_rect, category_rect, list_rect)
        for r in draw_rects:
            self._maker_db_draw_window(painter, r, width=max(1, int(2 * ss)), profile=profile)

        cur_name = self._maker_database_effective_value(kind, cur_id, "name", record.get("name") or shown)
        cur_desc = self._maker_database_effective_value(kind, cur_id, "description", record.get("description") or "")
        self._maker_db_draw_text(painter, QRectF(padding * sx, padding * sy, w - padding * 2 * sx, help_h - padding * 2 * sy), cur_desc, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, False, wrap=False, outline=True)

        def item_kind_matches(r):
            r = r if isinstance(r, dict) else {}
            try:
                if kind == "Items":
                    return int(r.get("itypeId") or 1) == int(record.get("itypeId") or 1)
                if kind in ("Weapons", "Armors"):
                    return True
                if kind == "Skills":
                    return int(r.get("stypeId") or 0) == int(record.get("stypeId") or 0)
            except Exception:
                return True
            return True

        entries = []
        try:
            for r in records:
                if not r or not item_kind_matches(r):
                    continue
                rid = int((r or {}).get("id") or 0)
                name = self._maker_database_effective_value(kind, rid, "name", (r or {}).get("name") or "")
                entries.append((rid, name, int((r or {}).get("iconIndex") or 0), r if isinstance(r, dict) else {}))
        except Exception:
            pass
        if not entries and cur_name:
            entries = [(int(cur_id or 1), cur_name, int(record.get("iconIndex") or 0), record)]

        if kind == "Skills":
            stypes = []
            try:
                for idx, val in enumerate(system.get("skillTypes") or []):
                    if idx <= 0 or not str(val or "").strip():
                        continue
                    stypes.append((idx, self._maker_db_mz_skill_type_name(system, idx, str(val or ""))))
            except Exception:
                pass
            cur_stype = int(record.get("stypeId") or 0)
            if not stypes and cur_stype:
                stypes = [(cur_stype, self._maker_db_mz_skill_type_name(system, cur_stype, self._maker_db_mz_item_category_name(system, "skill")))]
            tx = type_rect.x() + padding * sx
            ty = type_rect.y() + padding * sy
            tw = type_rect.width() - padding * 2 * sx
            for i, (sid, label) in enumerate(stypes[:max(1, int((type_rect.height() - padding * 2 * sy) // max(1, line_h)))]):
                y = ty + i * line_h
                if sid == cur_stype:
                    painter.fillRect(QRectF(tx + 4 * sx, y + 2 * sy, tw - 8 * sx, line_h - 4 * sy), QColor(255, 255, 255, 35))
                self._maker_db_draw_text(painter, QRectF(tx + 6 * sx, y, tw - 12 * sx, line_h), label, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        else:
            categories = [
                ("Items", 1, self._maker_db_mz_item_category_name(system, "item")),
                ("Weapons", None, self._maker_db_mz_item_category_name(system, "weapon")),
                ("Armors", None, self._maker_db_mz_item_category_name(system, "armor")),
                ("Items", 2, self._maker_db_mz_item_category_name(system, "keyItem")),
            ]
            cx = category_rect.x() + padding * sx
            cy = category_rect.y() + padding * sy
            cw = max(1, (category_rect.width() - padding * 2 * sx) / max(1, len(categories)))
            for i, (cat_kind, itype, label) in enumerate(categories):
                active = False
                try:
                    if kind in ("Weapons", "Armors"):
                        active = cat_kind == kind
                    elif kind == "Items":
                        active = cat_kind == "Items" and int(itype or 0) == int(record.get("itypeId") or 1)
                except Exception:
                    active = cat_kind == kind
                x = cx + i * cw
                if active:
                    painter.fillRect(QRectF(x + 4 * sx, cy + 2 * sy, cw - 8 * sx, line_h - 4 * sy), QColor(255, 255, 255, 35))
                self._maker_db_draw_text(painter, QRectF(x + 8 * sx, cy, cw - 16 * sx, line_h), label, text_size, normal, False, Qt.AlignmentFlag.AlignCenter, False, wrap=False, outline=True)

        list_x = list_rect.x() + padding * sx
        list_y = list_rect.y() + padding * sy
        list_w = list_rect.width() - padding * 2 * sx
        list_h = list_rect.height() - padding * 2 * sy
        cols = 1 if kind == "Skills" else 2
        col_w = max(1, list_w / cols)
        visible_rows = max(1, int(list_h // max(1, line_h)))
        max_entries = visible_rows * cols
        start = 0
        try:
            for i, (rid, _name, _icon, _rec) in enumerate(entries):
                if int(rid) == int(cur_id or 0):
                    start = max(0, i - cols * 2)
                    break
        except Exception:
            start = 0
        for idx, (rid, name, icon_idx, item_rec) in enumerate(entries[start:start + max_entries]):
            col = idx % cols
            row = idx // cols
            x = list_x + col * col_w
            y = list_y + row * line_h
            active = False
            try:
                active = int(rid) == int(cur_id or 0)
            except Exception:
                active = False
            if active:
                painter.fillRect(QRectF(x + 4 * sx, y + 2 * sy, col_w - 8 * sx, line_h - 4 * sy), QColor(255, 255, 255, 35))
            icon = self._maker_database_preview_icon_pixmap(icon_idx)
            ix = x + 8 * sx
            if icon and not icon.isNull():
                painter.drawPixmap(QRectF(ix, y + max(0, (line_h - 32 * sy) / 2), 32 * sx, 32 * sy).toRect(), icon)
                tx = ix + 36 * sx
            else:
                tx = ix
            cost_w = 0
            cost = ""
            cost_color = normal
            if kind == "Skills":
                try:
                    tp_cost = int(item_rec.get("tpCost") or 0)
                    mp_cost = int(item_rec.get("mpCost") or 0)
                    if tp_cost > 0:
                        cost = str(tp_cost)
                        cost_color = tp_color
                    elif mp_cost > 0:
                        cost = str(mp_cost)
                        cost_color = mp_color
                    if cost:
                        cost_w = 72 * sx
                except Exception:
                    cost = ""
            self._maker_db_draw_text(painter, QRectF(tx, y, max(1, col_w - (tx - x) - cost_w - 12 * sx), line_h), name, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
            if cost:
                self._maker_db_draw_text(painter, QRectF(x + col_w - cost_w - 12 * sx, y, cost_w, line_h), cost, small_size, cost_color, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        self._maker_db_canvas_finalize(painter)
        return pix

    def _maker_render_item_like_database_canvas(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        """Render item/skill/equipment DB rows as a reconstructed MZ menu screen.

        This is intentionally not a custom database card.  It ports the visible
        MZ menu relationship: Help window + category/skill-type window + item
        list.  Labels, fonts, windows and icons are all taken from the game data
        and resource profile.  DB types that do not have a stable in-game screen
        should return no canvas instead of inventing a fake one.
        """
        engine = self._maker_database_engine_key()
        if engine == "mv":
            return self._maker_render_item_like_database_canvas_mv(row_data, unit, db_kind, rec_id, field, record, src, shown)
        if engine != "mz":
            return None
        pix = self._maker_database_new_canvas()
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = pix.width(), pix.height()
        sx, sy = w / 1280.0, h / 720.0
        ss = min(sx, sy)
        profile = self._maker_database_runtime_profile()
        win = profile.get("window") if isinstance(profile.get("window"), dict) else {}
        font_prof = profile.get("font") if isinstance(profile.get("font"), dict) else {}
        try:
            padding = int(win.get("padding") or 12)
        except Exception:
            padding = 12
        try:
            line_h = int((profile.get("message_window") if isinstance(profile.get("message_window"), dict) else {}).get("line_height") or 36)
        except Exception:
            line_h = 36
        try:
            font_size = int(font_prof.get("size") or 28)
        except Exception:
            font_size = 28
        try:
            box_margin = int((profile.get("message_window") if isinstance(profile.get("message_window"), dict) else {}).get("box_margin") or 4)
        except Exception:
            box_margin = 4

        kind = str(db_kind or "")
        system = self._load_maker_database_json_runtime("System.json") or {}
        record = record if isinstance(record, dict) else {}
        db_file = {"Items": "Items.json", "Weapons": "Weapons.json", "Armors": "Armors.json", "Skills": "Skills.json"}.get(kind, str(kind) + ".json")
        records = self._maker_db_record_list(db_file)
        cur_id = rec_id if rec_id is not None else self._maker_db_selected_index_from_record(record, 1)
        normal = self._maker_db_mz_text_color(0, "#ffffff")
        system_color = self._maker_db_mz_text_color(16, "#80aaff")
        disabled_color = self._maker_db_mz_text_color(8, "#888888")
        crisis_color = self._maker_db_mz_text_color(17, "#ff8080")
        text_size = max(12, int(font_size * ss))
        small_size = max(11, int((font_size - 4) * ss))
        lh = line_h * sy
        margin = box_margin

        self._maker_db_draw_pattern_bg(painter, QRectF(0, 0, w, h))

        def calc_window_height(num_lines):
            return int(line_h * int(num_lines) + padding * 2)

        show_touch_buttons = bool(system.get("optTouchUI", True))
        button_area_h = 52 if show_touch_buttons else 0
        main_y = margin + button_area_h
        help_h = calc_window_height(2)
        category_h = calc_window_height(1)
        wx = margin
        ww = max(1, w - margin * 2)

        if show_touch_buttons:
            self._maker_db_draw_mz_button(painter, QRectF(w - margin - 62 * sx, margin + 2, 54 * sx, 48 * sy), "↩")

        help_rect = QRectF(wx, main_y, ww, help_h)
        y_after_help = help_rect.bottom() + margin
        category_rect = QRectF(wx, y_after_help, ww, category_h)
        list_y = category_rect.bottom() + margin
        list_rect = QRectF(wx, list_y, ww, max(1, h - list_y - margin))
        status_rect = None
        command_rect = category_rect

        if kind == "Skills":
            # Scene_Skill has a status window above the command/item area.  There is
            # no active actor in DB mode, so only the structural window is drawn and
            # the selected skill-type command is reconstructed from System.skillTypes.
            status_h = calc_window_height(4)
            status_rect = QRectF(wx, y_after_help, ww, status_h)
            command_w = max(240 * sx, min(360 * sx, ww * 0.33))
            command_rect = QRectF(wx, status_rect.bottom() + margin, command_w, h - status_rect.bottom() - margin * 2)
            list_rect = QRectF(command_rect.right() + margin, command_rect.y(), max(1, ww - command_w - margin), command_rect.height())
            category_rect = command_rect

        for r in ([help_rect, status_rect, command_rect if kind == "Skills" else category_rect, list_rect]):
            if r is not None:
                self._maker_db_draw_window(painter, r, width=max(2, int(3 * ss)), profile=profile)

        cur_name = self._maker_database_effective_value(kind, cur_id, "name", record.get("name") or shown)
        cur_desc = self._maker_database_effective_value(kind, cur_id, "description", record.get("description") or src)
        self._maker_db_draw_text(
            painter,
            QRectF(help_rect.x() + padding * sx + 8 * sx, help_rect.y() + padding * sy, help_rect.width() - padding * 2 * sx - 16 * sx, help_rect.height() - padding * 2 * sy),
            cur_desc or shown or src,
            text_size,
            normal,
            False,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            False,
            wrap=False,
            outline=True,
        )

        def item_kind_matches(r):
            try:
                if not isinstance(r, dict) or not r.get("name"):
                    return False
                if kind == "Items":
                    return int(r.get("itypeId") or 0) == int(record.get("itypeId") or 1 or 1)
                if kind in ("Weapons", "Armors"):
                    return True
                if kind == "Skills":
                    return int(r.get("stypeId") or 0) == int(record.get("stypeId") or 0)
            except Exception:
                return True
            return True

        entries = []
        try:
            for r in records:
                if not item_kind_matches(r):
                    continue
                rid = int((r or {}).get("id") or 0)
                name = self._maker_database_effective_value(kind, rid, "name", (r or {}).get("name") or "")
                entries.append((rid, name, int((r or {}).get("iconIndex") or 0), r if isinstance(r, dict) else {}))
        except Exception:
            pass
        if not entries and cur_name:
            entries = [(int(cur_id or 1), cur_name, int(record.get("iconIndex") or 0), record)]

        if kind == "Skills":
            stypes = []
            try:
                for idx, val in enumerate(system.get("skillTypes") or []):
                    if idx <= 0 or not str(val or "").strip():
                        continue
                    stypes.append((idx, self._maker_db_mz_skill_type_name(system, idx, str(val or ""))))
            except Exception:
                pass
            if not stypes:
                sid = int(record.get("stypeId") or 0)
                stypes = [(sid, self._maker_db_mz_skill_type_name(system, sid, self._maker_db_mz_item_category_name(system, "skill")))] if sid else []
            cur_stype = int(record.get("stypeId") or 0)
            cx = command_rect.x() + padding * sx
            cy = command_rect.y() + padding * sy
            command_w = command_rect.width() - padding * 2 * sx
            for i, (sid, label) in enumerate(stypes[:max(1, int(command_rect.height() // max(1, lh)))]):
                y = cy + i * lh
                if sid == cur_stype:
                    painter.fillRect(QRectF(cx + 4 * sx, y + 2 * sy, command_w - 8 * sx, lh - 4 * sy), QColor(255, 255, 255, 35))
                self._maker_db_draw_text(painter, QRectF(cx + 8 * sx, y, command_w - 16 * sx, lh), label, text_size, normal, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
        else:
            categories = [
                ("Items", 1, self._maker_db_mz_item_category_name(system, "item")),
                ("Weapons", None, self._maker_db_mz_item_category_name(system, "weapon")),
                ("Armors", None, self._maker_db_mz_item_category_name(system, "armor")),
                ("Items", 2, self._maker_db_mz_item_category_name(system, "keyItem")),
            ]
            cx = category_rect.x() + padding * sx
            cy = category_rect.y() + padding * sy
            cat_w = max(1, (category_rect.width() - padding * 2 * sx) / max(1, len(categories)))
            for i, (cat_kind, itype, label) in enumerate(categories):
                active = False
                try:
                    if kind in ("Weapons", "Armors"):
                        active = (cat_kind == kind)
                    elif kind == "Items":
                        active = (cat_kind == "Items" and int(itype or 0) == int(record.get("itypeId") or 1))
                except Exception:
                    active = (cat_kind == kind)
                x = cx + i * cat_w
                if active:
                    painter.fillRect(QRectF(x + 4 * sx, cy + 2 * sy, cat_w - 8 * sx, lh - 4 * sy), QColor(255, 255, 255, 35))
                self._maker_db_draw_text(painter, QRectF(x + 8 * sx, cy, cat_w - 16 * sx, lh), label, text_size, normal, False, Qt.AlignmentFlag.AlignCenter, False, wrap=False, outline=True)

        # Window_ItemList / Window_SkillList: two columns for items, one/flexible for skills.
        list_x = list_rect.x() + padding * sx
        list_y = list_rect.y() + padding * sy
        list_w = list_rect.width() - padding * 2 * sx
        list_h = list_rect.height() - padding * 2 * sy
        cols = 1 if kind == "Skills" else 2
        col_w = max(1, list_w / cols)
        row_h = lh
        visible_rows = max(1, int(list_h // max(1, row_h)))
        max_entries = visible_rows * cols
        start = 0
        try:
            for i, (rid, _name, _icon, _rec) in enumerate(entries):
                if int(rid) == int(cur_id or 0):
                    start = max(0, i - cols * 2)
                    break
        except Exception:
            start = 0
        for idx, (rid, name, icon_idx, item_rec) in enumerate(entries[start:start + max_entries]):
            col = idx % cols
            row = idx // cols
            x = list_x + col * col_w
            y = list_y + row * row_h
            active = False
            try:
                active = int(rid) == int(cur_id or 0)
            except Exception:
                active = False
            if active:
                painter.fillRect(QRectF(x + 4 * sx, y + 2 * sy, col_w - 8 * sx, row_h - 4 * sy), QColor(255, 255, 255, 35))
            icon = self._maker_database_preview_icon_pixmap(icon_idx)
            ix = x + 8 * sx
            if icon and not icon.isNull():
                painter.drawPixmap(QRectF(ix, y + max(0, (row_h - 32 * sy) / 2), 32 * sx, 32 * sy).toRect(), icon)
                tx = ix + 36 * sx
            else:
                tx = ix
            cost_w = 96 * sx if kind == "Skills" else 0
            color = normal
            try:
                if kind == "Skills" and (int(item_rec.get("mpCost") or 0) > 0 or int(item_rec.get("tpCost") or 0) > 0):
                    cost_w = 116 * sx
            except Exception:
                pass
            self._maker_db_draw_text(painter, QRectF(tx, y, max(1, col_w - (tx - x) - cost_w - 12 * sx), row_h), name, text_size, color, False, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)
            if kind == "Skills":
                cost = ""
                cost_color = normal
                try:
                    tp_cost = int(item_rec.get("tpCost") or 0)
                    mp_cost = int(item_rec.get("mpCost") or 0)
                    if tp_cost > 0:
                        cost = str(tp_cost)
                        cost_color = self._maker_db_mz_text_color(29, crisis_color)
                    elif mp_cost > 0:
                        cost = str(mp_cost)
                        cost_color = self._maker_db_mz_text_color(23, system_color)
                except Exception:
                    cost = ""
                if cost:
                    self._maker_db_draw_text(painter, QRectF(x + col_w - cost_w - 12 * sx, y, cost_w, row_h), cost, text_size, cost_color, False, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, False, wrap=False, outline=True)

        self._maker_db_canvas_finalize(painter)
        return pix
    def _maker_render_unsupported_database_canvas(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        # Some database files do not have a single stable MZ runtime screen
        # (System terms, Classes, CommonEvents, Troops, etc.).  For those, do not
        # invent a fake database card.  The caller will clear the preview canvas.
        return None

    def _maker_render_system_database_canvas(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        return self._maker_render_unsupported_database_canvas(row_data, unit, db_kind, rec_id, field, record, src, shown)

    def _maker_render_generic_database_canvas(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        return self._maker_render_unsupported_database_canvas(row_data, unit, db_kind, rec_id, field, record, src, shown)
    def _maker_db_terms_value(self, system_data, key, default=""):
        try:
            if not isinstance(system_data, dict):
                return default
            terms = system_data.get("terms") or {}
            cur = terms
            for part in str(key or "").split("/"):
                if not part:
                    continue
                if isinstance(cur, dict):
                    cur = cur.get(part)
                elif isinstance(cur, list):
                    cur = cur[int(part)]
                else:
                    return default
            if cur is None:
                return default
            return str(cur)
        except Exception:
            return default

    def _maker_render_actor_database_preview(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        record = record if isinstance(record, dict) else {}
        classes = self._load_maker_database_json_runtime("Classes.json") or []
        weapons = self._load_maker_database_json_runtime("Weapons.json") or []
        armors = self._load_maker_database_json_runtime("Armors.json") or []
        system = self._load_maker_database_json_runtime("System.json") or {}
        name = self._maker_database_effective_value("Actors", rec_id, "name", record.get("name") or shown)
        nickname = self._maker_database_effective_value("Actors", rec_id, "nickname", record.get("nickname") or "")
        profile = self._maker_database_effective_value("Actors", rec_id, "profile", record.get("profile") or "")
        class_name = ""
        try:
            cid = int(record.get("classId") or 0)
            if isinstance(classes, list) and 0 <= cid < len(classes) and classes[cid]:
                class_name = str((classes[cid] or {}).get("name") or "")
        except Exception:
            pass
        level = record.get("initialLevel") or ""
        params = []
        try:
            cid = int(record.get("classId") or 0)
            lv = int(level or 1)
            if isinstance(classes, list) and 0 <= cid < len(classes) and classes[cid]:
                c = classes[cid] or {}
                ptable = c.get("params") or []
                names = ((system.get("terms") or {}).get("params") or ["MaxHP", "MaxMP", "ATK", "DEF", "MAT", "MDF", "AGI", "LUK"])
                for i, pname in enumerate(names[:8]):
                    val = ""
                    try:
                        row = ptable[i]
                        val = row[min(max(1, lv), len(row) - 1)] if isinstance(row, list) and row else ""
                    except Exception:
                        val = ""
                    params.append((str(pname or i), val))
        except Exception:
            pass
        equips = []
        try:
            for pos, eid in enumerate(record.get("equips") or []):
                eid = int(eid or 0)
                if eid <= 0:
                    continue
                src_list = weapons if pos == 0 else armors
                if isinstance(src_list, list) and 0 <= eid < len(src_list) and src_list[eid]:
                    equips.append(str((src_list[eid] or {}).get("name") or ""))
        except Exception:
            pass
        face = self._maker_database_preview_face_pixmap(record.get("faceName"), record.get("faceIndex"))
        self._maker_set_database_preview_pixmap(face, "Actor")
        esc = self._db_preview_escape
        stat_html = " ".join([f"<span style='color:#84a8ff'>{esc(k)}</span> {esc(v)}" for k, v in params[:4]])
        equip_html = " / ".join(esc(x) for x in equips) if equips else "-"
        return {
            "subtitle": "Actors.json을 읽어 상태창 형태로 재구성했습니다. 번역문이 있으면 표시값에 우선 반영됩니다.",
            "kind": f"<div style='font-size:20px; font-weight:800;'>{esc(name)}</div><div style='font-size:14px; color:#cfc7cf;'>{esc(nickname)} · {esc(class_name)} · Lv {esc(level)}</div><div style='margin-top:10px;'>{stat_html}</div>",
            "source": f"<b>장비</b><br>{equip_html}<br><br><b>프로필</b><br>{esc(profile)}",
            "translation": f"<div style='font-size:15px; color:#a8c6ff;'>선택 항목: {esc(field)}</div><div style='margin-top:4px;'>원문: {esc(src)}</div><div style='color:#8fd19e;'>표시값: {esc(shown)}</div>",
            "hint": "MZ/MV 공통 Actors.json 구조를 기준으로 읽습니다. MZ 전용 advanced 값이 없어도 동작합니다.",
        }

    def _maker_render_item_like_database_preview(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        record = record if isinstance(record, dict) else {}
        system = self._load_maker_database_json_runtime("System.json") or {}
        kind = str(db_kind or "")
        name = self._maker_database_effective_value(kind, rec_id, "name", record.get("name") or shown)
        desc = self._maker_database_effective_value(kind, rec_id, "description", record.get("description") or "")
        price = record.get("price", "")
        icon = self._maker_database_preview_icon_pixmap(record.get("iconIndex") or 0)
        self._maker_set_database_preview_pixmap(icon, "Icon")
        esc = self._db_preview_escape
        category = {"Items": "아이템", "Weapons": "무기", "Armors": "방어구", "Skills": "스킬"}.get(kind, kind)
        extra = []
        try:
            if kind in ("Weapons", "Armors"):
                terms = ((system.get("terms") or {}).get("params") or ["MaxHP", "MaxMP", "ATK", "DEF", "MAT", "MDF", "AGI", "LUK"])
                vals = record.get("params") or []
                pairs = []
                for i, val in enumerate(vals[:8]):
                    try:
                        if int(val or 0) != 0:
                            pairs.append(f"{esc(terms[i] if i < len(terms) else i)} {esc(val)}")
                    except Exception:
                        pass
                if pairs:
                    extra.append("능력치: " + " / ".join(pairs))
            if kind == "Skills":
                if record.get("mpCost"):
                    extra.append(f"MP {record.get('mpCost')}")
                if record.get("tpCost"):
                    extra.append(f"TP {record.get('tpCost')}")
                if record.get("message1"):
                    extra.append(str(record.get("message1")))
            if price not in (None, ""):
                extra.append(f"가격 {price}")
        except Exception:
            pass
        return {
            "subtitle": f"{kind}.json을 읽어 게임 목록/설명창 형태로 재구성했습니다.",
            "kind": f"<div style='font-size:18px; font-weight:800;'>{esc(category)}  |  {esc(name)}</div><div style='color:#cfc7cf;'>ID {esc(rec_id if rec_id is not None else '')} · {esc(field)}</div>",
            "source": f"<b>설명</b><br>{esc(desc)}" + (f"<br><br><b>정보</b><br>{esc(' / '.join(extra))}" if extra else ""),
            "translation": f"<div style='font-size:15px; color:#a8c6ff;'>선택 항목: {esc(field)}</div><div style='margin-top:4px;'>원문: {esc(src)}</div><div style='color:#8fd19e;'>표시값: {esc(shown)}</div>",
            "hint": "아이콘은 img/system/IconSet을 참조합니다. 암호화 이미지(.png_, .rpgmvp)도 기존 프리뷰 복호화 경로를 사용합니다.",
        }

    def _maker_render_system_database_preview(self, row_data, unit, db_kind, rec_id, field, record, src, shown):
        system = self._load_maker_database_json_runtime("System.json") or {}
        self._maker_set_database_preview_pixmap(None, "System")
        esc = self._db_preview_escape
        terms = system.get("terms") or {}
        basic = terms.get("basic") or []
        params = terms.get("params") or []
        commands = terms.get("commands") or []
        menu = system.get("menuCommands") or []
        rows = []
        for title, arr in (("기본 용어", basic), ("능력치", params), ("명령", commands)):
            vals = [str(x) for x in (arr or []) if str(x or "").strip()]
            if vals:
                rows.append(f"<b>{esc(title)}</b><br>{esc(' / '.join(vals[:16]))}")
        if menu:
            rows.append(f"<b>메뉴 표시</b><br>{esc(' / '.join(str(x) for x in menu[:12]))}")
        return {
            "subtitle": "System.json terms/menuCommands를 읽어 시스템 UI 용어 형태로 재구성했습니다.",
            "kind": f"<div style='font-size:18px; font-weight:800;'>System Terms</div><div style='color:#cfc7cf;'>{esc(field or 'terms')}</div>",
            "source": "<br><br>".join(rows) if rows else esc(src),
            "translation": f"<div style='font-size:15px; color:#a8c6ff;'>선택 항목: {esc(field)}</div><div style='margin-top:4px;'>원문: {esc(src)}</div><div style='color:#8fd19e;'>표시값: {esc(shown)}</div>",
            "hint": "MV/MZ 모두 System.json의 terms 계열을 우선 참조합니다. MZ advanced 항목은 있으면 보조 정보로만 사용합니다.",
        }

    def _maker_build_database_preview_canvas(self, page, row_data, data_index):
        row_data = row_data if isinstance(row_data, dict) else {}
        unit = row_data.get("maker_text_unit") or {}
        unit = unit if isinstance(unit, dict) else {}
        meta_page = (page or {}).get("maker_page") or {}
        source_file = str(unit.get("source_file") or meta_page.get("source_file") or "")
        db_kind = str(unit.get("db_kind") or Path(source_file).stem or meta_page.get("page_title") or "DB")
        field = str(unit.get("db_field") or unit.get("text_type") or "")
        path = str(unit.get("json_path") or unit.get("db_path") or source_file or "")
        src = str(row_data.get("text") or row_data.get("source_text") or "")
        dst = str(row_data.get("translated_text") or "")
        shown = dst if dst.strip() else src
        record, rec_id, path_field = self._maker_database_record_from_path(source_file, path)
        if not field:
            field = path_field
        low = source_file.lower()
        if db_kind in ("System", "System_Terms") or low == "system.json":
            return self._maker_render_system_database_canvas(row_data, unit, db_kind, rec_id, field, record, src, shown)
        if db_kind == "Actors" or low == "actors.json":
            return self._maker_render_actor_database_canvas(row_data, unit, "Actors", rec_id, field, record, src, shown)
        if db_kind in ("Items", "Weapons", "Armors", "Skills") or low in ("items.json", "weapons.json", "armors.json", "skills.json"):
            return self._maker_render_item_like_database_canvas(row_data, unit, db_kind, rec_id, field, record, src, shown)
        return self._maker_render_unsupported_database_canvas(row_data, unit, db_kind, rec_id, field, record, src, shown)

    def _maker_build_database_preview_payload(self, page, row_data, data_index):
        row_data = row_data if isinstance(row_data, dict) else {}
        unit = row_data.get("maker_text_unit") or {}
        unit = unit if isinstance(unit, dict) else {}
        meta_page = (page or {}).get("maker_page") or {}
        source_file = str(unit.get("source_file") or meta_page.get("source_file") or "")
        db_kind = str(unit.get("db_kind") or Path(source_file).stem or meta_page.get("page_title") or "DB")
        field = str(unit.get("db_field") or unit.get("text_type") or "")
        path = str(unit.get("json_path") or unit.get("db_path") or source_file or "")
        src = str(row_data.get("text") or row_data.get("source_text") or "")
        dst = str(row_data.get("translated_text") or "")
        shown = dst if dst.strip() else src
        record, rec_id, path_field = self._maker_database_record_from_path(source_file, path)
        if not field:
            field = path_field
        if db_kind == "System" or db_kind == "System_Terms" or source_file.lower() == "system.json":
            esc = self._db_preview_escape
            self._maker_set_database_preview_pixmap(None, "")
            return {
                "subtitle": self.tr_ui("System.json은 여러 화면의 용어 원천이라 단일 MZ 게임 화면으로 억지 재구성하지 않습니다."),
                "kind": f"{esc(db_kind)}" + (f" · {esc(field)}" if field else ""),
                "source": "",
                "translation": "",
                "hint": "",
            }
        if db_kind == "Actors" or source_file.lower() == "actors.json":
            return self._maker_render_actor_database_preview(row_data, unit, "Actors", rec_id, field, record, src, shown)
        if db_kind in ("Items", "Weapons", "Armors", "Skills") or source_file.lower() in ("items.json", "weapons.json", "armors.json", "skills.json"):
            return self._maker_render_item_like_database_preview(row_data, unit, db_kind, rec_id, field, record, src, shown)
        esc = self._db_preview_escape
        self._maker_set_database_preview_pixmap(None, "")
        return {
            "subtitle": self.tr_ui("이 DB 항목은 MZ 게임 화면에 직접 대응하는 프리뷰가 없어 화면을 비워둡니다."),
            "kind": f"{esc(db_kind)}" + (f" · {esc(field)}" if field else "") + (f" · #{data_index + 1}" if data_index >= 0 else ""),
            "source": "",
            "translation": "",
            "hint": "",
        }

    def refresh_maker_database_preview_from_selection(self):
        """오른쪽 DB 표 선택 행을 왼쪽 DB 프리뷰 패널에 반영한다."""
        if not (hasattr(self, "is_maker_database_mode") and self.is_maker_database_mode()):
            return False
        try:
            page, row_data, data_index = self._current_database_preview_row_data()
            meta_page = (page or {}).get("maker_page") or {}
            label = self._database_tab_label_for_page(int(getattr(self, "maker_database_idx", 0) or 0)) if hasattr(self, "_database_tab_label_for_page") else str(meta_page.get("page_title") or "DB")
            title = getattr(self, "lbl_maker_database_preview_title", None)
            subtitle = getattr(self, "lbl_maker_database_preview_subtitle", None)
            kind_lbl = getattr(self, "lbl_maker_database_preview_kind", None)
            src_lbl = getattr(self, "lbl_maker_database_preview_source", None)
            trans_lbl = getattr(self, "lbl_maker_database_preview_translation", None)
            hint_lbl = getattr(self, "lbl_maker_database_preview_hint", None)
            if title is not None:
                title.setText(self.tr_ui("데이터베이스 프리뷰") + f"  |  {label}")
            if row_data is None:
                self._maker_set_database_preview_pixmap(None, "DB")
                try:
                    pix = self._maker_render_generic_database_canvas({}, {}, label, None, "", {}, "", self.tr_ui("이 DB 탭에는 표시할 텍스트가 없습니다."))
                    self._maker_database_preview_set_canvas_pixmap(pix)
                except Exception:
                    pass
                if subtitle is not None:
                    subtitle.setText(self.tr_ui("이 DB 탭에는 표시할 텍스트가 없습니다."))
                if kind_lbl is not None: kind_lbl.setText("")
                if src_lbl is not None: src_lbl.setText("")
                if trans_lbl is not None: trans_lbl.setText("")
                if hint_lbl is not None: hint_lbl.setText("")
                return True
            # 3차 DB 프리뷰: 실제 게임창 비율의 이미지 캔버스를 다시 렌더링해서
            # 일반 맵 프리뷰처럼 축소/확대 가능한 화면으로 표시한다.
            try:
                canvas = self._maker_build_database_preview_canvas(page, row_data, data_index)
                self._maker_database_preview_set_canvas_pixmap(canvas)
            except Exception as ce:
                try:
                    self.log(f"⚠️ DB 캔버스 프리뷰 렌더 실패: {type(ce).__name__}: {ce}")
                except Exception:
                    pass
            payload = self._maker_build_database_preview_payload(page, row_data, data_index)
            if subtitle is not None:
                subtitle.setText(str(payload.get("subtitle") or ""))
            if kind_lbl is not None:
                kind_lbl.setText(str(payload.get("kind") or ""))
            if src_lbl is not None:
                src_lbl.setText(str(payload.get("source") or ""))
            if trans_lbl is not None:
                trans_lbl.setText(str(payload.get("translation") or ""))
            if hint_lbl is not None:
                hint_lbl.setText(str(payload.get("hint") or ""))
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ DB 프리뷰 갱신 실패: {type(e).__name__}: {e}")
            except Exception:
                pass
            return False

    def update_maker_database_mode_bar(self):
        enabled = self.is_maker_database_mode()
        try:
            bar = getattr(self, "maker_database_mode_bar", None)
            if bar is not None:
                bar.setVisible(enabled)
        except Exception:
            pass
        try:
            label = getattr(self, "lbl_maker_database_mode_detail", None)
            if label is not None:
                current = self._database_tab_label_for_page(int(getattr(self, "maker_database_idx", 0) or 0)) if enabled else ""
                label.setText(self.tr_ui("현재 탭의 DB 항목만 번역합니다.") + (f"  |  {current}" if current else ""))
        except Exception:
            pass
        try:
            act = (getattr(self, "actions", {}) or {}).get("option_maker_database_translation")
            if act is not None and hasattr(act, "setChecked"):
                old = act.blockSignals(True)
                try:
                    act.setChecked(enabled)
                finally:
                    act.blockSignals(old)
        except Exception:
            pass
        try:
            btn = getattr(self, "btn_page_add", None)
            if btn is not None:
                btn.setVisible(not enabled)
                btn.setEnabled((not enabled) and bool(self.has_open_project()))
        except Exception:
            pass
        try:
            self.update_page_position_label_for_current_tab_layer()
        except Exception:
            pass

    def refresh_maker_database_view(self):
        """현재 DB 페이지의 행을 일반 맵 대사표와 같은 편집 표로 펼친다."""
        pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else []
        if not pages:
            return False
        try:
            actual_idx = int(getattr(self, "maker_database_idx", pages[0]) or pages[0])
        except Exception:
            actual_idx = pages[0]
        if actual_idx not in pages:
            actual_idx = pages[0]
        self.maker_database_idx = int(actual_idx)
        page = self._page_data_for_index_safe(actual_idx) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(actual_idx, {})
        rows = (page or {}).get("data") or []
        tab = getattr(self, "tab", None)
        if tab is None:
            return False
        old_block = False
        try:
            old_block = tab.blockSignals(True)
        except Exception:
            old_block = False
        try:
            filtered = self._maker_database_filtered_rows_for_page(page) if hasattr(self, "_maker_database_filtered_rows_for_page") else list(enumerate(rows))
            visible_rows = [r for _idx, r in filtered]
            # DB mode deliberately uses the same right-table shape as the normal
            # Maker/map text mode: ID / status / speaker / type / event / source /
            # translation / memo.  Only the data source is different.
            if tab.columnCount() != 8:
                tab.setColumnCount(8)
            try:
                tab.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
                tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
                tab.setDragEnabled(False)
                tab.setAcceptDrops(False)
                tab.viewport().setAcceptDrops(False)
                tab.setDropIndicatorShown(False)
                tab.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
                tab.setDragDropOverwriteMode(False)
                tab.setProperty("ysb_excel_like_text_table", True)
                tab.setProperty("ysb_copy_blank_line_between_rows", True)
                # DB table instances are reused by normal Maker/map pages.
                # Keep the source DB page stamped on the widget so a stale table
                # can never be committed into the wrong DB page during batch UI refresh.
                tab.setProperty("maker_database_page_idx", int(actual_idx))
                tab.setProperty("maker_database_table", True)
                tab.setWordWrap(True)
                tab.setTextElideMode(Qt.TextElideMode.ElideNone)
                tab.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            except Exception:
                pass
            tab.clear()
            tab.setColumnCount(8)
            tab.setHorizontalHeaderLabels([
                "ID",
                self.tr_ui("상태"),
                self.tr_ui("화자"),
                self.tr_ui("타입"),
                self.tr_ui("이벤트"),
                self.tr_ui("원문"),
                self.tr_ui("번역문"),
                self.tr_ui("메모"),
            ])
            tab.setRowCount(len(filtered) + 1)
            try:
                tab.setItemDelegateForColumn(6, MultilineDelegate(
                    tab,
                    shortcut_getter=self.get_special_shortcuts,
                    linebreak_getter=self.get_linebreak_shortcut,
                    enter_commit_callback=self._advance_table_editor_after_enter,
                ))
            except Exception:
                pass

            translated = sum(1 for r in visible_rows if str((r or {}).get("translated_text") or "").strip())
            tab.setItem(0, 0, self._make_table_item("ALL", editable=False, center=True))
            tab.setItem(0, 1, self._make_table_item(self.tr_ui("전체"), editable=False, center=True))
            tab.setItem(0, 2, self._make_table_item("", editable=False))
            tab.setItem(0, 3, self._make_table_item("", editable=False))
            tab.setItem(0, 4, self._make_table_item("", editable=False))
            tab.setItem(0, 5, self._make_table_item(self.tr_ui("현재 DB 텍스트") + f" · {len(filtered)}", editable=False))
            tab.setItem(0, 6, self._make_table_item(f"{self.tr_ui('번역완료')} {translated} / {self.tr_ui('미번역')} {max(0, len(visible_rows)-translated)}", editable=False))
            tab.setItem(0, 7, self._make_table_item("", editable=False))
            try:
                self.paint_all_row_header()
            except Exception:
                pass
            for c in range(tab.columnCount()):
                item = tab.item(0, c)
                if item:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)

            for i, (source_index, row_data) in enumerate(filtered, start=1):
                row_data = row_data if isinstance(row_data, dict) else {}
                meta = row_data.get("maker_text_unit") or {}
                if not isinstance(meta, dict):
                    meta = {}
                src = str(row_data.get("text") or row_data.get("source_text") or "")
                dst = str(row_data.get("translated_text") or "")
                status_text = str(row_data.get("maker_status") or (self.tr_ui("번역완료") if dst.strip() else self.tr_ui("미번역")))
                if hasattr(self, "_maker_row_speaker_text"):
                    speaker_text = self._maker_row_speaker_text(row_data)
                else:
                    try:
                        speaker_text = strip_maker_control_codes(row_data.get("maker_speaker_plain") or row_data.get("maker_speaker") or "").strip()
                    except Exception:
                        speaker_text = str(row_data.get("maker_speaker_plain") or row_data.get("maker_speaker") or "")
                db_kind = str(meta.get("db_kind") or meta.get("source_file") or "")
                db_field = str(meta.get("db_field") or meta.get("text_type") or "")
                db_id = meta.get("db_id")
                source_file = str(meta.get("source_file") or "")
                event_bits = []
                if source_file:
                    event_bits.append(source_file)
                if db_id not in (None, ""):
                    event_bits.append(f"#{db_id}")
                event_text = " · ".join(event_bits)
                memo_text = str(row_data.get("maker_memo") or "")

                id_text = str(row_data.get("id", i))
                id_item = self._make_table_item(id_text, editable=False, center=True, user_value=source_index)
                id_item.setData(Qt.ItemDataRole.UserRole, source_index)
                tab.setItem(i, 0, id_item)
                tab.setItem(i, 1, self._make_table_item(status_text, editable=True, center=True, user_value=status_text))
                tab.setItem(i, 2, self._make_table_item(speaker_text, editable=True, user_value=speaker_text))
                tab.setItem(i, 3, self._make_table_item(db_field or db_kind, editable=False, center=True, user_value=db_field or db_kind))
                tab.setItem(i, 4, self._make_table_item(event_text, editable=False, user_value=event_text))
                # DB source/original text is project input data.  The visible DB table
                # may be rebuilt while batch translation is running, so never allow
                # routine UI commits to rewrite the source column.  Only translated_text
                # is the normal editable target.
                original_item = self._make_table_item(src, editable=False, user_value=src)
                try:
                    original_item.setToolTip(str(meta.get("json_path") or meta.get("db_path") or ""))
                except Exception:
                    pass
                tab.setItem(i, 5, original_item)
                tab.setItem(i, 6, self._make_table_item(dst, editable=True, user_value=dst))
                tab.setItem(i, 7, self._make_table_item(memo_text, editable=True, user_value=memo_text))
                try:
                    self.set_table_row_visual(i, True)
                except Exception:
                    pass

            try:
                header = tab.horizontalHeader()
                if header is not None:
                    header.setStretchLastSection(False)
                    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
                    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
                    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
                    header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
                    header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
                    header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
                    header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
                    header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
                    tab.setColumnWidth(0, 46)
                    tab.setColumnWidth(1, 78)
                    tab.setColumnWidth(2, 92)
                    tab.setColumnWidth(3, 92)
                    tab.setColumnWidth(4, 150)
                    tab.setColumnWidth(7, 120)
                    try:
                        tab.resizeRowsToContents()
                    except Exception:
                        pass
            except Exception:
                pass
        finally:
            try:
                tab.blockSignals(old_block)
            except Exception:
                pass
        try:
            self._maker_table_current_marker_row = -1
            self.refresh_maker_table_current_row_marker()
        except Exception:
            pass
        try:
            self.update_page_position_label_for_current_tab_layer()
            self.update_maker_database_mode_bar()
        except Exception:
            pass
        try:
            if len(rows) > 0 and tab.currentRow() < 1:
                tab.setCurrentCell(1, 6 if tab.columnCount() > 6 else 0)
        except Exception:
            pass
        try:
            self.refresh_maker_database_preview_from_selection()
        except Exception:
            pass
        try:
            self.audit_maker_database_mode_event("DB_VIEW_REFRESHED", page_idx=actual_idx, rows=len(rows), label=self._database_tab_label_for_page(actual_idx))
        except Exception:
            pass
        return True

    def commit_current_database_ui_to_layer(self):
        """현재 DB 표의 편집값을 실제 self.data의 DB 페이지에 반영한다."""
        # Batch DB translation changes pages rapidly for progress display.  During
        # that window, only the worker payload is authoritative.  A visible/stale
        # QTableWidget must not be committed back into self.data, because that can
        # overwrite DB source rows with a previously displayed map/dialogue table.
        try:
            if bool(getattr(self, "_suppress_database_ui_commit", False)):
                return False
            if (
                bool(getattr(self, "_maker_database_batch_translate_active", False))
                and bool(getattr(self, "is_batch_running", False))
                and str(getattr(self, "current_batch_mode", "") or "") == "translate"
            ):
                return False
        except Exception:
            pass
        try:
            actual_idx = int(getattr(self, "maker_database_idx", 0) or 0)
        except Exception:
            return False
        page = self._page_data_for_index_safe(actual_idx) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(actual_idx, {})
        if not isinstance(page, dict):
            return False
        rows = page.get("data") or []
        tab = getattr(self, "tab", None)
        if tab is None:
            return False
        try:
            table_page_idx = tab.property("maker_database_page_idx")
            if table_page_idx is None or int(table_page_idx) != int(actual_idx):
                try:
                    self.audit_maker_database_mode_event("DB_COMMIT_SKIP_STALE_TABLE", actual_idx=actual_idx, table_page_idx=table_page_idx)
                except Exception:
                    pass
                return False
        except Exception:
            return False
        changed = False
        for table_row in range(1, tab.rowCount()):
            data_index = table_row - 1
            try:
                id_item = tab.item(table_row, 0)
                if id_item is not None:
                    v = id_item.data(Qt.ItemDataRole.UserRole)
                    if v is not None and str(v).strip() != "":
                        data_index = int(v)
            except Exception:
                data_index = table_row - 1
            if data_index < 0 or data_index >= len(rows):
                continue
            row_data = rows[data_index]
            if not isinstance(row_data, dict):
                continue
            status_item = tab.item(table_row, 1)
            speaker_item = tab.item(table_row, 2)
            orig_item = tab.item(table_row, 5)
            trans_item = tab.item(table_row, 6)
            memo_item = tab.item(table_row, 7)
            new_status = status_item.text() if status_item is not None else str(row_data.get("maker_status") or "")
            new_speaker = speaker_item.text() if speaker_item is not None else str(row_data.get("maker_speaker") or "")
            new_src = orig_item.text() if orig_item is not None else str(row_data.get("text") or row_data.get("source_text") or "")
            new_trans = trans_item.text() if trans_item is not None else ""
            new_memo = memo_item.text() if memo_item is not None else ""
            if str(row_data.get("maker_status") or "") != str(new_status):
                row_data["maker_status"] = str(new_status)
                changed = True
            if str(row_data.get("maker_speaker") or "") != str(new_speaker):
                row_data["maker_speaker"] = str(new_speaker)
                row_data["maker_speaker_plain"] = str(new_speaker)
                try:
                    meta = row_data.setdefault("maker_text_unit", {})
                    if isinstance(meta, dict):
                        meta["speaker"] = str(new_speaker)
                        meta["speaker_plain"] = str(new_speaker)
                except Exception:
                    pass
                changed = True
            # Do not commit the DB source/original column from the visible table.
            # Source text is imported game data and must remain stable; normal DB
            # editing, batch translation, and preview refreshes may only change the
            # translation/memo/status side unless a future explicit source-edit mode
            # is introduced.
            _ = new_src
            if str(row_data.get("translated_text") or "") != str(new_trans):
                row_data["translated_text"] = str(new_trans)
                changed = True
            if str(row_data.get("maker_memo") or "") != str(new_memo):
                row_data["maker_memo"] = str(new_memo)
                changed = True
        if changed:
            try:
                self.data[int(actual_idx)] = page
            except Exception:
                pass
            try:
                self.has_unsaved_changes = True
                self.mark_project_structure_dirty("maker_database_page_edit")
            except Exception:
                pass
            try:
                self.apply_maker_writeback_to_clone(mark_dirty=False, log_result=False, backup=False, page_indices=[actual_idx])
            except Exception as e:
                try:
                    self.log(f"⚠️ DB 텍스트 JSON 실시간 반영 실패: {e}")
                except Exception:
                    pass
        return changed

    def audit_maker_database_mode_event(self, event, **fields):
        """DB 모드 전환/탭바 치환 상태를 로그에 남긴다."""
        try:
            if hasattr(self, "audit_boundary_event"):
                self.audit_boundary_event(event, **fields)
        except Exception:
            pass
        try:
            bits = [f"{k}={v!r}" for k, v in (fields or {}).items()]
            self.log("🧪 " + str(event) + (" | " + " | ".join(bits) if bits else ""))
        except Exception:
            pass

    def force_rebuild_page_tabs_for_current_layer(self, *, reason="layer switch"):
        """현재 모드 필터 기준으로 탭바를 강제 갱신한다."""
        try:
            self.refresh_page_tabs()
            pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else []
            self.audit_maker_database_mode_event(
                "DB_MODE_TABBAR_REBUILT",
                reason=reason,
                db_mode=bool(self.is_maker_database_mode()) if hasattr(self, "is_maker_database_mode") else False,
                tabbar_count=(getattr(self, "page_tab_bar", None).count() if getattr(self, "page_tab_bar", None) is not None else None),
                layer_count=len(pages),
                first=(self._database_tab_label_for_page(pages[0]) if pages and self.is_maker_database_mode() else (self.page_display_name(pages[0]) if pages and hasattr(self, "page_display_name") else "")),
            )
            return len(pages)
        except Exception as e:
            try:
                self.audit_maker_database_mode_event("DB_MODE_TABBAR_REBUILD_FAIL", reason=reason, error=f"{type(e).__name__}: {e}")
            except Exception:
                pass
            return 0

    def enter_maker_database_mode(self):
        count = self.ensure_maker_database_pages(save_project=False, reason="enter database mode")
        self.audit_maker_database_mode_event(
            "DB_MODE_TOGGLE_REQUEST",
            target="enter",
            current_enabled=bool(getattr(self, "maker_database_mode_enabled", False)),
            existing_pages=count,
        )
        if count <= 0:
            try:
                self.show_warn_notice("데이터베이스 모드", "데이터베이스 번역 탭이 없습니다. 먼저 게임을 가져와 주세요.")
            except Exception:
                QMessageBox.information(self, self.tr_ui("데이터베이스 모드"), self.tr_ui("데이터베이스 번역 탭이 없습니다. 먼저 게임을 가져와 주세요."))
            self.update_maker_database_mode_bar()
            return False
        if not self.is_maker_database_mode():
            try:
                self._maker_normal_mode_last_page_idx = int(getattr(self, "idx", 0) or 0)
            except Exception:
                self._maker_normal_mode_last_page_idx = 0
        self.maker_database_mode_enabled = True
        pages = self.current_tab_page_indices()
        try:
            current = int(getattr(self, "maker_database_idx", pages[0] if pages else 0) or (pages[0] if pages else 0))
        except Exception:
            current = pages[0] if pages else 0
        if current not in pages and pages:
            current = pages[0]
        self.maker_database_idx = int(current)
        rebuilt = self.force_rebuild_page_tabs_for_current_layer(reason="enter database mode")
        ok = False
        try:
            ok = bool(self.refresh_maker_database_view())
        except Exception as e:
            self.audit_maker_database_mode_event("DB_MODE_VIEW_REFRESH_FAIL", error=f"{type(e).__name__}: {e}")
            ok = False
        try:
            self.update_maker_database_mode_bar()
        except Exception:
            pass
        try:
            self.set_maker_database_preview_visible(True)
        except Exception:
            pass
        self.audit_maker_database_mode_event("DB_MODE_ENTER_DONE", rebuilt=rebuilt, view_refreshed=ok, current_page=self.maker_database_idx)
        return True

    def exit_maker_database_mode(self):
        self.audit_maker_database_mode_event(
            "DB_MODE_TOGGLE_REQUEST",
            target="exit",
            current_enabled=bool(getattr(self, "maker_database_mode_enabled", False)),
            existing_pages=self.ensure_maker_database_pages(save_project=False, reason="exit database mode"),
        )
        if not self.is_maker_database_mode():
            self.update_maker_database_mode_bar()
            return False
        try:
            if not bool(getattr(self, "_maker_database_batch_translate_active", False)):
                self.commit_current_database_ui_to_layer()
        except Exception:
            pass
        self.maker_database_mode_enabled = False
        try:
            self.set_maker_database_preview_visible(False)
        except Exception:
            pass
        try:
            restore = int(getattr(self, "_maker_normal_mode_last_page_idx", 0) or 0)
        except Exception:
            restore = 0
        normal_pages = self.current_tab_page_indices()
        if restore not in normal_pages and normal_pages:
            restore = normal_pages[0]
        if normal_pages:
            self.idx = int(restore)
        rebuilt = self.force_rebuild_page_tabs_for_current_layer(reason="exit database mode")
        try:
            self.load()
        except Exception as e:
            self.audit_maker_database_mode_event("DB_MODE_EXIT_LOAD_FAIL", error=f"{type(e).__name__}: {e}")
        try:
            self.log("↩️ 데이터베이스 모드 나가기")
        except Exception:
            pass
        self.audit_maker_database_mode_event("DB_MODE_EXIT_DONE", rebuilt=rebuilt, restored=self.idx)
        return True

    def toggle_maker_database_mode(self):
        if self.is_maker_database_mode():
            return self.exit_maker_database_mode()
        return self.enter_maker_database_mode()

    def refresh_page_tabs(self):
        if not hasattr(self, "page_tab_bar"):
            return
        bar = self.page_tab_bar
        visible_pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else list(range(len(getattr(self, "paths", []) or [])))
        has_pages = bool(visible_pages)
        try:
            if hasattr(self, "btn_page_tab_menu"):
                self.btn_page_tab_menu.setEnabled(has_pages)
        except Exception:
            pass
        try:
            bar.setEnabled(has_pages)
        except Exception:
            pass
        self._refreshing_page_tabs = True
        try:
            bar.blockSignals(True)
            if not has_pages:
                while bar.count() > 0:
                    bar.removeTab(0)
                bar.setTabsClosable(False)
                bar.setMovable(False)
                try:
                    self.update_maker_database_mode_bar()
                except Exception:
                    pass
                return

            db_mode = self.is_maker_database_mode() if hasattr(self, "is_maker_database_mode") else False
            bar.setTabsClosable(False if db_mode else True)
            bar.setMovable(False if db_mode else True)

            desired_count = len(visible_pages)
            need_rebuild = (bar.count() != desired_count)
            if need_rebuild:
                while bar.count() > 0:
                    bar.removeTab(0)
                for tab_i, page_i in enumerate(visible_pages):
                    label = self._database_tab_label_for_page(page_i) if db_mode else self.page_display_name(page_i)
                    bar.addTab(label)
                    try:
                        if db_mode:
                            tabs = self._ensure_maker_database_layer_storage()
                            info = tabs[page_i] if 0 <= int(page_i) < len(tabs) else {}
                            original = str(info.get("source_file") or info.get("path") or info.get("label") or "") if isinstance(info, dict) else ""
                            tooltip = f"{self.tr_ui('데이터베이스 탭')} {tab_i + 1} / {desired_count}\n{original}"
                        else:
                            original = self.page_original_name(page_i)
                            tooltip = f"{self.tr_ui('맵')} {tab_i + 1} / {desired_count}\n{original}"
                        bar.setTabToolTip(tab_i, tooltip)
                    except Exception:
                        pass
            else:
                for tab_i, page_i in enumerate(visible_pages):
                    try:
                        label = self._database_tab_label_for_page(page_i) if db_mode else self.page_display_name(page_i)
                        try:
                            if db_mode:
                                tabs = self._ensure_maker_database_layer_storage()
                                info = tabs[page_i] if 0 <= int(page_i) < len(tabs) else {}
                                original = str(info.get("source_file") or info.get("path") or info.get("label") or "") if isinstance(info, dict) else ""
                                tooltip = f"{self.tr_ui('데이터베이스 탭')} {tab_i + 1} / {desired_count}\n{original}"
                            else:
                                original = self.page_original_name(page_i)
                                tooltip = f"{self.tr_ui('맵')} {tab_i + 1} / {desired_count}\n{original}"
                        except Exception:
                            tooltip = ""
                        if bar.tabText(tab_i) != label:
                            bar.setTabText(tab_i, label)
                        try:
                            old_tip = bar.tabToolTip(tab_i)
                        except Exception:
                            old_tip = None
                        if old_tip != tooltip:
                            try:
                                bar.setTabToolTip(tab_i, tooltip)
                            except Exception:
                                pass
                    except Exception:
                        pass

            if db_mode:
                try:
                    if int(getattr(self, "maker_database_idx", 0) or 0) not in visible_pages:
                        self.maker_database_idx = visible_pages[0]
                except Exception:
                    self.maker_database_idx = 0
                display_idx = self.current_tab_display_index_for_page(getattr(self, "maker_database_idx", 0)) if hasattr(self, "current_tab_display_index_for_page") else int(getattr(self, "maker_database_idx", 0) or 0)
            else:
                if int(getattr(self, "idx", 0) or 0) not in visible_pages:
                    try:
                        self.idx = visible_pages[0]
                    except Exception:
                        self.idx = 0
                display_idx = self.current_tab_display_index_for_page(self.idx) if hasattr(self, "current_tab_display_index_for_page") else int(getattr(self, "idx", 0) or 0)
            if display_idx < 0:
                display_idx = 0
            if bar.currentIndex() != display_idx:
                bar.setCurrentIndex(display_idx)
            try:
                self.update_maker_database_mode_bar()
            except Exception:
                pass
        finally:
            try:
                bar.blockSignals(False)
            except Exception:
                pass
            self._refreshing_page_tabs = False
            try:
                self.update_page_tab_scroll_buttons()
            except Exception:
                pass

    def sync_page_tab_current_only(self):
        """페이지 이동 때 탭바 전체를 다시 만들지 않고 현재 선택만 맞춘다.

        대용량 프로젝트에서는 load()가 호출될 때마다 모든 페이지 탭 이름/툴팁을
        재계산하는 것만으로도 렉이 난다. 페이지 수나 구조가 바뀐 경우만
        refresh_page_tabs()를 쓰고, 단순 페이지 이동은 이 경량 동기화만 사용한다.
        """
        bar = getattr(self, "page_tab_bar", None)
        if bar is None:
            return False
        try:
            visible_pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else list(range(len(getattr(self, "paths", []) or [])))
            if not visible_pages:
                return False
            if bar.count() != len(visible_pages):
                return False
            if hasattr(self, "is_maker_database_mode") and self.is_maker_database_mode():
                idx = self.current_tab_display_index_for_page(getattr(self, "maker_database_idx", 0)) if hasattr(self, "current_tab_display_index_for_page") else max(0, min(int(getattr(self, "maker_database_idx", 0) or 0), len(visible_pages) - 1))
            else:
                idx = self.current_tab_display_index_for_page(getattr(self, "idx", 0)) if hasattr(self, "current_tab_display_index_for_page") else max(0, min(int(getattr(self, "idx", 0) or 0), len(self.paths) - 1))
            if idx < 0:
                return False
            if bar.currentIndex() != idx:
                old = getattr(self, "_refreshing_page_tabs", False)
                self._refreshing_page_tabs = True
                try:
                    bar.blockSignals(True)
                    bar.setCurrentIndex(idx)
                finally:
                    try:
                        bar.blockSignals(False)
                    except Exception:
                        pass
                    self._refreshing_page_tabs = old
            try:
                self.update_page_tab_scroll_buttons()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def remap_indexed_dict_by_order(self, src, order):
        out = {}
        src = src or {}
        for new_idx, old_idx in enumerate(order or []):
            if old_idx in src:
                out[new_idx] = src.get(old_idx)
        return out

    def remap_view_states_by_order(self, order):
        states = getattr(self, "project_ui_view_states", {}) or {}
        if not isinstance(states, dict) or not order:
            self.project_ui_view_states = {} if not order else states
            return
        old_to_new = {int(old): int(new) for new, old in enumerate(order)}
        new_states = {}
        for key, state in states.items():
            try:
                page_s, mode_s = str(key).split(":", 1)
                old_page = int(page_s)
                if old_page in old_to_new:
                    new_states[f"{old_to_new[old_page]}:{int(mode_s)}"] = copy.deepcopy(state)
            except Exception:
                pass
        self.project_ui_view_states = new_states

    def on_page_tab_changed(self, index):
        if getattr(self, "_refreshing_page_tabs", False):
            return
        visible_pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else list(range(len(getattr(self, "paths", []) or [])))
        if index < 0 or index >= len(visible_pages):
            return
        actual_index = int(visible_pages[int(index)])
        if hasattr(self, "is_maker_database_mode") and self.is_maker_database_mode():
            if actual_index == int(getattr(self, "maker_database_idx", 0) or 0):
                return
            try:
                if not bool(getattr(self, "_maker_database_batch_translate_active", False)):
                    self.commit_current_database_ui_to_layer()
            except Exception:
                pass
            self.maker_database_idx = actual_index
            try:
                self.refresh_maker_database_view()
            except Exception:
                pass
            try:
                self.update_page_position_label_for_current_tab_layer()
            except Exception:
                pass
            return
        if actual_index == self.idx:
            return

        preserve_scroll = None
        target_was_visible = False
        try:
            bar = getattr(self, "page_tab_bar", None)
            if bar is not None and hasattr(bar, "scroll") and hasattr(bar, "_tabs"):
                sb = bar.scroll.horizontalScrollBar()
                preserve_scroll = int(sb.value())
                if 0 <= int(index) < len(bar._tabs):
                    tab = bar._tabs[int(index)]
                    left = int(tab.x())
                    right = int(tab.x() + tab.width())
                    view_left = preserve_scroll
                    view_right = preserve_scroll + max(1, int(bar.scroll.viewport().width()))
                    target_was_visible = (left >= view_left and right <= view_right)
        except Exception:
            preserve_scroll = None
            target_was_visible = False

        # 페이지 전환은 현재 페이지 작업실의 Undo 경계다.
        # 다른 페이지로 넘어가면 이전 페이지 내부 Ctrl+Z 흐름은 끊는다.
        # 단, 페이지를 닫기 전에 현재 화면 변경분과 view_state는 현재 idx 기준으로 먼저 고정한다.
        try:
            self.prepare_current_page_boundary("page change")
        except Exception:
            try:
                self.undo_clear_current_page("page change")
            except Exception:
                pass
            self.commit_current_page_ui_to_data()
            self.remember_current_view_state()
        # 페이지 전환은 구조 변경이 아니라 탐색 동작이다.
        # 이미 보이는 탭을 클릭했다면 탭바 시점은 보존하고,
        # 보이지 않거나 절반만 보일 때만 현재 순간 기준으로 한 번 보정한다.
        self.idx = int(actual_index)
        self.load()
        self.restore_current_view_state_later()

        scheduled_generation = int(getattr(self, "page_tab_scroll_generation", 0) or 0)

        def _restore_or_ensure_tab_position():
            # 예약 후 사용자가 좌우 화살표로 탭바를 수동 이동했다면,
            # 오래된 자동 보정은 실행하지 않는다.
            if scheduled_generation != int(getattr(self, "page_tab_scroll_generation", 0) or 0):
                return
            try:
                bar = getattr(self, "page_tab_bar", None)
                if target_was_visible and preserve_scroll is not None and bar is not None and hasattr(bar, "scroll"):
                    sb = bar.scroll.horizontalScrollBar()
                    sb.setValue(max(sb.minimum(), min(sb.maximum(), int(preserve_scroll))))
                    return
            except Exception:
                pass
            self.ensure_current_page_tab_visible()

        QTimer.singleShot(0, _restore_or_ensure_tab_position)

    def selected_page_tab_indices(self):
        """페이지 탭바에서 Ctrl/Shift로 선택된 페이지 인덱스를 가져온다."""
        bar = getattr(self, "page_tab_bar", None)
        if bar is not None and hasattr(bar, "selectedIndices"):
            try:
                selected = [int(i) for i in bar.selectedIndices()]
                visible_pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else list(range(len(getattr(self, "paths", []) or [])))
                return [visible_pages[i] for i in selected if 0 <= i < len(visible_pages)]
            except Exception:
                pass
        try:
            return [int(self.idx)] if self.paths else []
        except Exception:
            return []

    def confirm_and_delete_pages(self, indices, title="일괄 맵 탭 삭제"):
        clean = []
        seen = set()
        for raw in indices or []:
            try:
                i = int(raw)
            except Exception:
                continue
            if 0 <= i < len(self.paths) and i not in seen:
                clean.append(i)
                seen.add(i)
        if not clean:
            self.log("⚠️ 삭제할 이미지탭이 없습니다.")
            return False

        names = [self.page_display_name(i, include_ext=True) for i in clean[:8]]
        info = "\n".join(str(x) for x in names)
        if len(clean) > 8:
            info += f"\n... 외 {len(clean) - 8}개"
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(self.tr_ui(title))
        msg.setText(self.tr_ui(f"선택한 {len(clean)}개의 페이지탭을 삭제할까요?"))
        msg.setInformativeText(info)
        btn_delete = msg.addButton(self.tr_ui("삭제"), QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg.addButton(self.tr_ui("취소"), QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_cancel)
        try:
            msg.setStyleSheet(self.message_box_style())
        except Exception:
            pass
        force_message_box_front(msg)
        msg.exec()
        if msg.clickedButton() is not btn_delete:
            self.log("↩️ 페이지탭 삭제 취소")
            return False
        return self.delete_pages_at(clean, reason=title)

    def close_page_from_tab(self, index):
        if index < 0 or index >= len(self.paths):
            return
        selected = self.selected_page_tab_indices()
        if len(selected) > 1 and index in selected:
            self.confirm_and_delete_pages(selected, title="일괄 맵 탭 삭제")
            return
        self.confirm_and_delete_pages([index], title="맵 삭제")


    def delete_pages_at(self, indices, reason="맵 삭제"):
        clean = []
        seen = set()
        for raw in indices or []:
            try:
                i = int(raw)
            except Exception:
                continue
            if 0 <= i < len(self.paths) and i not in seen:
                clean.append(i)
                seen.add(i)
        if not clean:
            return False

        remove_set = set(clean)
        self.commit_current_page_ui_to_data()
        self.remember_current_view_state()
        before_structure_state = self._snapshot_project_structure_state(reason)
        old_count = len(self.paths)
        old_idx = int(getattr(self, "idx", 0) or 0)
        order = [i for i in range(old_count) if i not in remove_set]
        removed_names = [self.page_display_name(i, include_ext=True) for i in clean]

        self.paths = [self.paths[i] for i in order]
        self.data = self.remap_indexed_dict_by_order(self.data, order)
        self.remap_view_states_by_order(order)

        if self.paths:
            removed_before = sum(1 for i in remove_set if i < old_idx)
            if old_idx in remove_set:
                self.idx = min(max(0, old_idx - removed_before), len(self.paths) - 1)
            else:
                self.idx = min(max(0, old_idx - removed_before), len(self.paths) - 1)
        else:
            self.idx = 0
            self.project_ui_view_states = {}

        after_structure_state = self._snapshot_project_structure_state(reason)
        self.undo_clear_all_pages("page delete")
        self.push_project_structure_command(before_structure_state, after_structure_state, reason=reason, action="page_delete")
        self.load()
        try:
            bar = getattr(self, "page_tab_bar", None)
            if bar is not None and hasattr(bar, "setSelectedIndices") and self.paths:
                bar.setSelectedIndices([self.idx])
        except Exception:
            pass
        self.auto_save_project()
        if len(clean) == 1:
            self.log(f"🗑️ 맵 삭제: {removed_names[0]}")
        else:
            self.log(f"🗑️ {reason}: {len(clean)}개")
        return True

    def delete_page_at(self, index):
        return self.delete_pages_at([index], reason="맵 삭제")


    def delete_current_page_shortcut(self):
        """Ctrl+Q: 현재 열려 있거나 탭바에서 선택된 이미지 탭을 삭제한다."""
        if not getattr(self, "paths", None):
            self.log("⚠️ 삭제할 이미지탭이 없습니다.")
            return False
        selected = self.selected_page_tab_indices()
        if len(selected) > 1:
            return self.confirm_and_delete_pages(selected, title="일괄 맵 탭 삭제")
        try:
            index = max(0, min(int(self.idx), len(self.paths) - 1))
        except Exception:
            index = 0
        self.close_page_from_tab(index)
        return True


    def delete_all_pages_shortcut(self):
        """Ctrl+Shift+Q: 선택한 범위의 페이지탭을 일괄 삭제한다."""
        if not getattr(self, "paths", None):
            self.log("⚠️ 삭제할 이미지탭이 없습니다.")
            return False

        selected = self.selected_page_tab_indices()
        if len(selected) <= 1:
            selected, label = self.choose_batch_page_indices("일괄 맵 탭 삭제", "delete_pages")
            if selected is None:
                self.log("↩️ 일괄 맵 탭 삭제 취소")
                return False
        else:
            label = f"선택 {len(selected)}개"

        result = self.confirm_and_delete_pages(selected, title="일괄 맵 탭 삭제")
        if result:
            self.log(f"🗑️ 일괄 맵 탭 삭제 완료: {len(selected)}개 ({label})")
        return result


    def on_page_tab_moved(self, from_index, to_index):
        if getattr(self, "_refreshing_page_tabs", False):
            return
        if from_index == to_index:
            return
        try:
            self.undo_clear_all_pages()
        except Exception:
            pass
        if from_index < 0 or to_index < 0 or from_index >= len(self.paths) or to_index >= len(self.paths):
            self.refresh_page_tabs()
            return

        bar = getattr(self, "page_tab_bar", None)
        try:
            visible_index = int(bar.currentIndex()) if bar is not None else int(self.idx)
        except Exception:
            visible_index = int(self.idx) if self.paths else 0
        try:
            tab_scroll_value = int(bar.scroll.horizontalScrollBar().value()) if bar is not None and hasattr(bar, "scroll") else None
        except Exception:
            tab_scroll_value = None

        self.commit_current_page_ui_to_data()
        self.remember_current_view_state()
        before_structure_state = self._snapshot_project_structure_state("페이지 순서 변경")

        n = len(self.paths)
        order = list(range(n))
        moved_old = order.pop(from_index)
        order.insert(to_index, moved_old)

        old_paths = list(self.paths)
        self.paths = [old_paths[old_i] for old_i in order]
        self.data = self.remap_indexed_dict_by_order(self.data, order)
        self.remap_view_states_by_order(order)

        # QTabBar가 이미 화면상으로 탭을 이동시켰으므로, 여기서 전체 탭을 다시 만들지 않는다.
        # 다시 만들면 드래그 직후 잡고 있던 탭/선택 위치가 한 번 더 튀어 보일 수 있다.
        self.idx = max(0, min(visible_index, len(self.paths) - 1)) if self.paths else 0
        after_structure_state = self._snapshot_project_structure_state("페이지 순서 변경")
        self.undo_clear_all_pages("page reorder")
        self.push_project_structure_command(before_structure_state, after_structure_state, reason="페이지 순서 변경", action="page_reorder")

        try:
            if bar is not None:
                bar.blockSignals(True)
                try:
                    for i in range(min(bar.count(), len(self.paths))):
                        bar.setTabText(i, self.page_display_name(i))
                        bar.setTabToolTip(i, "")
                    # 커스텀 탭바는 드래그 시 이미 시각적 이동을 끝낸 상태다.
                    # 여기서 currentIndex를 다시 강제로 바꾸면 탭 위치가 또 확인되는 느낌이 생기므로,
                    # 내부 idx와 표시 상태만 조용히 맞춘다.
                    try:
                        bar._current = self.idx
                        bar.apply_theme(self.is_light_theme())
                    except Exception:
                        pass
                finally:
                    bar.blockSignals(False)
        except Exception:
            pass

        # 순서 변경은 프로젝트 구조 작업이지만, 화면 전체를 즉시 다시 조립할 필요는 없다.
        # 현재 보이는 페이지는 그대로 두고 탭/목록 메타만 동기화한다. 실제 저장은 지연 저장으로 보낸다.
        try:
            self.sync_page_tab_current_only()
        except Exception:
            pass
        try:
            if tab_scroll_value is not None and bar is not None and hasattr(bar, "scroll"):
                QTimer.singleShot(0, lambda v=tab_scroll_value, b=bar: b.scroll.horizontalScrollBar().setValue(
                    max(b.scroll.horizontalScrollBar().minimum(), min(b.scroll.horizontalScrollBar().maximum(), int(v)))
                ))
        except Exception:
            pass
        self.update_page_tab_scroll_buttons()
        try:
            self.schedule_deferred_auto_save_project(800)
        except Exception:
            self.auto_save_project()
        self.log(f"↔️ 페이지 순서 변경: {from_index + 1} → {to_index + 1}")

    def active_page_storage_dir(self):
        """새로 삽입하는 이미지는 항상 현재 workspace/images에 바로 넣는다.

        예전 work_sessions 캐시 구조에서는 자동저장 OFF일 때 별도 작업 캐시에 먼저 넣었지만,
        지금은 workspaces 폴더 자체가 작업대이자 복구본이다. 따라서 이미지 추가는 즉시
        project_dir/images로 복사되어야 하고, work_sessions full copy를 만들면 안 된다.
        """
        return str(self.project_dir or "")

    def workspace_page_entry_light(self, page_idx, old_page=None):
        """큰 이미지 payload를 건드리지 않고 project.json page entry만 만든다.

        이미지 추가/구조 변경 직후에는 이미 workspace/images에 파일이 복사되어 있다.
        여기서는 파일 재저장/재인코딩 없이 경로와 텍스트 JSON만 갱신한다.
        """
        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = 0
        curr = (getattr(self, "data", {}) or {}).get(page_idx)
        if not isinstance(curr, dict):
            curr = {}
        page = copy.deepcopy(old_page) if isinstance(old_page, dict) else {}
        try:
            image_path = str((getattr(self, "paths", []) or [])[page_idx])
        except Exception:
            image_path = ""
        if image_path:
            try:
                page["image"] = relpath(image_path, self.project_dir)
            except Exception:
                page["image"] = image_path.replace("\\", "/")
        page["original_name"] = str(curr.get("original_name") or os.path.basename(str(image_path)) or f"page{page_idx + 1:03d}.png")
        page["data"] = json_safe(curr.get("data", []))
        page["ocr_analysis_regions"] = json_safe(curr.get("ocr_analysis_regions", []))
        page["mask_toggle_enabled"] = bool(curr.get("mask_toggle_enabled", False))
        page["use_inpainted_as_source"] = bool(curr.get("use_inpainted_as_source", False))
        if isinstance(curr.get("maker_page"), dict):
            page["maker_page"] = json_safe(curr.get("maker_page"))
        if isinstance(curr.get("maker_preview_settings"), dict):
            page["maker_preview_settings"] = json_safe(curr.get("maker_preview_settings"))

        path_fields = {
            "clean": "clean_path",
            "working_source": "working_source_path",
            "final_paint": "final_paint_path",
            "final_paint_above": "final_paint_above_path",
            "mask_merge": "mask_merge_path",
            "mask_inpaint": "mask_inpaint_path",
            "mask_merge_off": "mask_merge_off_path",
            "mask_inpaint_off": "mask_inpaint_off_path",
        }
        for json_key, data_key in path_fields.items():
            p = curr.get(data_key)
            if p and os.path.exists(str(p)):
                try:
                    page[json_key] = relpath(str(p), self.project_dir)
                except Exception:
                    page[json_key] = str(p).replace("\\", "/")
            elif json_key in page:
                # 기존 페이지에 남은 경로가 아직 workspace 안에 존재하면 보존한다.
                try:
                    old_abs = os.path.join(str(self.project_dir), str(page.get(json_key)).replace("/", os.sep))
                    if not page.get(json_key) or not os.path.exists(old_abs):
                        page.pop(json_key, None)
                except Exception:
                    pass
        return page

    def save_workspace_project_json_light(self, *, reason="structure_light"):
        """workspace/project.json만 가볍게 갱신한다.

        ProjectStore.save(force_full=True)는 전체 페이지를 순회하며 이미지/클린본/마스크 저장 루트를
        확인하므로 이미지 추가 직후 10초 이상 UI를 막을 수 있다. 구조 변경 직후에는 이미 파일이
        workspace/images에 있으므로 project.json만 갱신하면 된다.
        """
        if not getattr(self, "project_dir", None) or not getattr(self, "paths", None):
            return False
        project_file = os.path.join(str(self.project_dir), PROJECT_FILENAME)
        old_payload = {}
        try:
            if os.path.exists(project_file):
                with open(project_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    old_payload = loaded
        except Exception:
            old_payload = {}
        old_pages = old_payload.get("pages", []) if isinstance(old_payload.get("pages"), list) else []
        pages = []
        for i in range(len(self.paths)):
            old_page = old_pages[i] if i < len(old_pages) and isinstance(old_pages[i], dict) else {}
            pages.append(self.workspace_page_entry_light(i, old_page=old_page))
        ui_state = {}
        try:
            ui_state = self.current_project_ui_state()
        except Exception:
            ui_state = old_payload.get("ui_state", {}) if isinstance(old_payload.get("ui_state"), dict) else {}
        payload = {
            "version": old_payload.get("version", 1) if isinstance(old_payload, dict) else 1,
            "current_index": int(getattr(self, "idx", 0) or 0),
            "pages": pages,
            "ui_state": json_safe(ui_state if isinstance(ui_state, dict) else {}),
        }
        try:
            if getattr(self, "project_store", None) is not None:
                self.project_store.write_manifest()
        except Exception:
            pass
        tmp = project_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, project_file)
        return True

    def flush_workspace_structure_after_image_insert(self, *, reason="image_insert"):
        """페이지 삽입/삭제/순서 변경처럼 구조가 바뀐 작업을 workspace project.json에 즉시 반영한다."""
        if not getattr(self, "project_dir", None) or not getattr(self, "project_store", None):
            return False
        try:
            if hasattr(self, "mark_project_structure_dirty"):
                self.mark_project_structure_dirty(str(reason or "image_insert"))
        except Exception:
            pass
        try:
            self.audit_boundary_event("WORKSPACE_STRUCTURE_LIGHT_SAVE_ENTER", reason=str(reason or "image_insert"), stack=True)
        except Exception:
            pass
        ok = False
        try:
            ok = bool(self.save_workspace_project_json_light(reason=reason))
        except Exception as e:
            try:
                self.log(f"⚠️ 이미지 추가 workspace 구조 내보내기 실패: {e}")
            except Exception:
                pass
            ok = False
        try:
            self.record_recovery_project_dir(self.project_dir)
        except Exception:
            pass
        try:
            self.audit_boundary_event("WORKSPACE_STRUCTURE_LIGHT_SAVE_DONE", reason=str(reason or "image_insert"), ok=bool(ok))
        except Exception:
            pass
        try:
            self.has_unsaved_changes = True
            self.update_window_title()
        except Exception:
            pass
        return ok

    def unique_insert_image_path(self, src_path):
        storage_root = self.active_page_storage_dir() or str(self.project_dir)
        images_dir = os.path.join(storage_root, "images")
        os.makedirs(images_dir, exist_ok=True)
        src = Path(src_path)
        ext = src.suffix.lower() if src.suffix.lower() in IMAGE_DROP_EXTS else ".png"
        base = safe_page_file_stem(src.stem, fallback="inserted")

        # 원본 파일명을 최대한 보존하되, 확장자가 달라도 표시 stem이 겹치면 회피한다.
        # 예: 0007.jpg가 있으면 0007.png는 0007(1).png로 저장.
        existing_stems = set()
        try:
            for p in Path(images_dir).iterdir():
                if p.is_file():
                    existing_stems.add(p.stem.lower())
        except Exception:
            pass

        candidate_stem = base
        candidate = os.path.join(images_dir, f"{candidate_stem}{ext}")
        if candidate_stem.lower() not in existing_stems and not os.path.exists(candidate):
            return candidate

        for n in range(1, 10000):
            candidate_stem = f"{base}({n})"
            candidate = os.path.join(images_dir, f"{candidate_stem}{ext}")
            if candidate_stem.lower() not in existing_stems and not os.path.exists(candidate):
                return candidate

        return os.path.join(images_dir, f"{base}({uuid.uuid4().hex[:8]}){ext}")

    def unique_initial_image_target_path(self, src_path, images_dir, used_stems=None, current_path=None):
        """새 프로젝트 생성 직후 원본 파일명 보존용 대상 경로를 만든다.

        ProjectStore 경로가 0001/0002 같은 번호명을 만들었더라도 여기서 최종적으로
        원본명 기반 파일명으로 다시 정리한다.
        """
        used_stems = used_stems if used_stems is not None else set()
        src = Path(str(src_path))
        ext = src.suffix.lower() if src.suffix.lower() in IMAGE_DROP_EXTS else ".png"
        base = safe_page_file_stem(src.stem, fallback="image")
        current_resolved = ""
        try:
            current_resolved = str(Path(str(current_path)).resolve()).lower() if current_path else ""
        except Exception:
            current_resolved = ""

        existing_stems = set(used_stems)
        try:
            for p in Path(images_dir).iterdir():
                if not p.is_file():
                    continue
                try:
                    if current_resolved and str(p.resolve()).lower() == current_resolved:
                        continue
                except Exception:
                    pass
                existing_stems.add(p.stem.lower())
        except Exception:
            pass

        def make_candidate(n=None):
            stem = base if n is None else f"{base}({n})"
            return stem, Path(images_dir) / f"{stem}{ext}"

        stem, target = make_candidate(None)
        if stem.lower() not in existing_stems and (not target.exists() or str(target.resolve()).lower() == current_resolved):
            used_stems.add(stem.lower())
            return str(target)

        for n in range(1, 10000):
            stem, target = make_candidate(n)
            if stem.lower() not in existing_stems and not target.exists():
                used_stems.add(stem.lower())
                return str(target)

        stem = f"{base}({uuid.uuid4().hex[:8]})"
        used_stems.add(stem.lower())
        return str(Path(images_dir) / f"{stem}{ext}")

    def enforce_initial_project_image_names(self, source_paths):
        """새 프로젝트 생성 후 images 폴더의 실제 파일명을 원본명 기반으로 정리한다."""
        if not getattr(self, "project_dir", None) or not getattr(self, "paths", None):
            return False
        images_dir = os.path.join(str(self.project_dir), "images")
        os.makedirs(images_dir, exist_ok=True)
        changed = False
        used_stems = set()
        limit = min(len(self.paths), len(source_paths or []))
        for i in range(limit):
            try:
                src = source_paths[i]
                old_path = Path(str(self.paths[i]))
                if not old_path.exists():
                    continue
                target_path = Path(self.unique_initial_image_target_path(src, images_dir, used_stems, current_path=old_path))
                if str(old_path.resolve()).lower() != str(target_path.resolve()).lower():
                    if str(old_path.resolve()).lower() == str(target_path.resolve()).lower() and str(old_path) != str(target_path):
                        tmp = old_path.with_name(f".__ysb_init_rename_{uuid.uuid4().hex}{old_path.suffix}")
                        os.rename(str(old_path), str(tmp))
                        os.rename(str(tmp), str(target_path))
                    else:
                        os.rename(str(old_path), str(target_path))
                    self.paths[i] = str(target_path)
                    changed = True
                else:
                    self.paths[i] = str(target_path)
                if not isinstance(self.data, dict):
                    self.data = {}
                curr = self.data.get(i) or {}
                curr["original_name"] = os.path.basename(str(target_path))
                self.data[i] = curr
            except Exception as e:
                try:
                    self.log(f"⚠️ 원본 파일명 보존 실패({i + 1}p): {e}")
                except Exception:
                    pass
        if changed:
            try:
                self.save_project_store(self.project_store)
            except Exception:
                try:
                    self.project_store.save(self.paths, self.data, current_index=getattr(self, "idx", 0))
                except Exception:
                    pass
        return changed

    def _ensure_page_payload_cache_state(self):
        if not hasattr(self, "_page_payload_cache_order") or self._page_payload_cache_order is None:
            self._page_payload_cache_order = OrderedDict()
        try:
            limit = int(getattr(self, "page_payload_cache_limit", 3) or 3)
        except Exception:
            limit = 3
        self.page_payload_cache_limit = max(1, limit)

    def touch_page_payload_cache(self, page_idx):
        self._ensure_page_payload_cache_state()
        try:
            page_idx = int(page_idx)
        except Exception:
            return
        self._page_payload_cache_order.pop(page_idx, None)
        self._page_payload_cache_order[page_idx] = True

    def trim_page_payload_cache(self, keep_indices=None):
        self._ensure_page_payload_cache_state()
        keep = set()
        try:
            keep.add(int(getattr(self, "idx", -1)))
        except Exception:
            pass
        for raw in list(keep_indices or []):
            try:
                keep.add(int(raw))
            except Exception:
                pass
        payload_keys = ("bg_clean", "working_source", "final_paint", "final_paint_above")
        loaded = []
        for page_idx, curr in list((getattr(self, "data", {}) or {}).items()):
            if isinstance(curr, dict) and any(curr.get(k) is not None for k in payload_keys):
                loaded.append(int(page_idx))
                if page_idx not in self._page_payload_cache_order:
                    self._page_payload_cache_order[page_idx] = True
        while len(loaded) > self.page_payload_cache_limit:
            victim = None
            for candidate in list(self._page_payload_cache_order.keys()):
                if candidate in keep:
                    continue
                curr = (getattr(self, "data", {}) or {}).get(candidate)
                if isinstance(curr, dict) and any(curr.get(k) is not None for k in payload_keys):
                    victim = candidate
                    break
                self._page_payload_cache_order.pop(candidate, None)
            if victim is None:
                break
            curr = self.data.get(victim)
            if isinstance(curr, dict):
                for key in payload_keys:
                    curr[key] = None
            self._page_payload_cache_order.pop(victim, None)
            loaded = [idx for idx in loaded if idx != victim]

    def _read_binary_asset_bytes(self, path_value):
        path = self.resolve_project_asset_path(path_value) if hasattr(self, "resolve_project_asset_path") else path_value
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            return None

    def note_ui_interaction_activity(self, pause_ms=900):
        """사용자 드래그/줌/편집 직후에는 백그라운드 페이지 로더를 잠깐 쉬게 한다."""
        try:
            now = __import__("time").time()
            until = now + max(0.1, float(pause_ms or 900) / 1000.0)
            old_until = float(getattr(self, "_progressive_page_load_pause_until", 0.0) or 0.0)
            self._progressive_page_load_pause_until = max(old_until, until)
        except Exception:
            pass

    def mark_current_page_for_recovery_checkpoint(self, kind="checkpoint_text"):
        """YSBG 내보내기용 dirty와 workspace checkpoint용 dirty를 분리한다.

        project_engine/page_engine dirty는 명시 저장 전까지 유지되어야 하고,
        checkpoint dirty는 journal 저장이 끝나면 바로 비워져야 한다.
        """
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
        except Exception:
            page_idx = 0
        kind_s = str(kind or "checkpoint_text")
        try:
            if hasattr(self, "project_engine") and self.project_engine is not None:
                self.project_engine.mark_page_dirty(page_idx, kind_s)
        except Exception:
            pass
        try:
            if hasattr(self, "page_engine") and self.page_engine is not None:
                self.page_engine.mark_dirty(page_idx, kind_s)
        except Exception:
            pass
        try:
            pages = getattr(self, "_checkpoint_dirty_pages", None)
            if pages is None:
                pages = set()
                self._checkpoint_dirty_pages = pages
            pages.add(int(page_idx))
            kinds = getattr(self, "_checkpoint_dirty_kinds", None)
            if kinds is None:
                kinds = {}
                self._checkpoint_dirty_kinds = kinds
            kinds.setdefault(int(page_idx), set()).add(kind_s)
        except Exception:
            pass
        try:
            self.has_unsaved_changes = True
            self.update_window_title()
        except Exception:
            pass

    def schedule_workspace_checkpoint(self, delay_ms=1600, reason=""):
        """YSBG는 건드리지 않고, 현재 workspace/project.json에 page delta만 지연 반영한다."""
        if (
            getattr(self, "_suppress_work_cache_dirty", False)
            or getattr(self, "is_loading_project", False)
            or getattr(self, "is_autosaving", False)
            or not getattr(self, "project_dir", None)
            or not getattr(self, "paths", None)
        ):
            return
        try:
            self.note_ui_interaction_activity(int(delay_ms or 800) + 300)
        except Exception:
            pass
        try:
            self._last_workspace_checkpoint_reason = str(reason or "workspace_checkpoint")
        except Exception:
            pass
        try:
            timer = getattr(self, "_deferred_work_cache_save_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._run_deferred_workspace_checkpoint)
                self._deferred_work_cache_save_timer = timer
            timer.stop()
            timer.start(max(1200, int(delay_ms or 1600)))
        except Exception:
            try:
                self.auto_save_project()
            except Exception:
                pass

    def _run_deferred_workspace_checkpoint(self):
        if getattr(self, "_text_item_drag_active", False) or getattr(self, "_text_scene_mutation_lock", False):
            try:
                self.audit_boundary_event(
                    "WORK_CACHE_SAVE_DEFERRED_DURING_TEXT_DRAG",
                    text_drag=bool(getattr(self, "_text_item_drag_active", False)),
                    scene_mutation=bool(getattr(self, "_text_scene_mutation_lock", False)),
                    throttle_ms=120,
                )
            except Exception:
                pass
            try:
                timer = getattr(self, "_deferred_work_cache_save_timer", None)
                if timer is not None:
                    timer.start(650)
                    return
            except Exception:
                pass
        try:
            self.auto_save_project()
        except Exception:
            pass

    def _ensure_maker_lazy_map_preview_rendered_for_page(self, page_idx):
        """Render a deferred Maker map placeholder only when the map page is opened.

        Importing large MV projects should not tile-render every map up front.
        Map pages are first imported with a light placeholder; this method turns
        the current page into the real cached tile preview on demand.
        """
        try:
            page_idx = int(page_idx)
        except Exception:
            return False
        try:
            curr = (getattr(self, "data", {}) or {}).get(page_idx)
            if not isinstance(curr, dict):
                return False
            meta = curr.get("maker_page") if isinstance(curr.get("maker_page"), dict) else {}
            if not isinstance(meta, dict) or not meta:
                return False
            page_type = str(meta.get("page_type") or "map")
            if page_type not in {"", "map"}:
                return False
            # Render only maps that were intentionally imported in deferred mode.
            # Old projects without the marker keep their existing image as-is.
            if not bool(meta.get("preview_render_deferred", False)):
                return False
            paths = getattr(self, "paths", []) or []
            if page_idx < 0 or page_idx >= len(paths):
                return False
            image_path = paths[page_idx]
            st = dict(curr.get("maker_preview_settings") or {})
            st["defer_tile_render"] = False
            try:
                from ysb.tools.maker_project import regenerate_maker_placeholder_for_page
                ok = regenerate_maker_placeholder_for_page(image_path, curr, settings=st)
            except Exception as _e:
                ok = False
                try:
                    self.log(f"⚠️ MAKER_LAZY_MAP_RENDER_FAIL | page={page_idx+1} | {type(_e).__name__}: {_e}")
                except Exception:
                    pass
            if ok:
                try:
                    meta["preview_render_deferred"] = False
                    meta["preview_rendered_on_demand"] = True
                except Exception:
                    pass
                try:
                    curr["ori"] = None
                except Exception:
                    pass
                try:
                    self.log(f"🗺️ MAKER_LAZY_MAP_RENDER | page={page_idx+1} | cached/on-demand preview ready")
                except Exception:
                    pass
                return True
        except Exception:
            return False
        return False

    def ensure_page_runtime_loaded(self, page_idx, *, include_ori=True, include_heavy=False, include_masks=False):
        try:
            page_idx = int(page_idx)
        except Exception:
            return
        if page_idx < 0 or page_idx >= len(getattr(self, "paths", []) or []):
            return
        curr = (getattr(self, "data", {}) or {}).get(page_idx)
        if not isinstance(curr, dict):
            return
        if include_ori and not curr.get('use_inpainted_as_source'):
            # Maker 맵 페이지는 가져오기 직후 가벼운 placeholder PNG로 먼저 들어오고,
            # 실제 타일 프리뷰는 현재 페이지를 열 때 지연 렌더링한다.
            # 기존에는 curr['ori']가 placeholder로 한 번이라도 채워지면 lazy render가
            # 다시 돌지 않아, "기존 프로젝트 닫기 → 새 프로젝트 생성 → 게임 가져오기"
            # 직후에는 타일 프리뷰가 빈/placeholder 상태로 남고 재실행 후에야 보였다.
            # deferred 플래그가 살아 있으면 ori 존재 여부와 무관하게 먼저 타일 렌더를 확정한다.
            try:
                if int(page_idx) == int(getattr(self, "idx", -999)):
                    meta = curr.get("maker_page") if isinstance(curr.get("maker_page"), dict) else {}
                    if isinstance(meta, dict) and bool(meta.get("preview_render_deferred", False)):
                        if self._ensure_maker_lazy_map_preview_rendered_for_page(page_idx):
                            curr['ori'] = None
            except Exception:
                pass
        if include_ori and curr.get('ori') is None and not curr.get('use_inpainted_as_source'):
            try:
                curr['ori'] = cv2.imdecode(np.fromfile(self.paths[page_idx], np.uint8), 1)
            except Exception:
                curr['ori'] = None
            try:
                self.touch_page_image_cache(page_idx)
                self.trim_page_image_cache(keep_indices=[page_idx])
            except Exception:
                pass
        if include_heavy:
            loaded_any = False
            for field, path_key in (
                ('working_source', 'working_source_path'),
                ('bg_clean', 'clean_path'),
                ('final_paint', 'final_paint_path'),
                ('final_paint_above', 'final_paint_above_path'),
            ):
                if curr.get(field) is None and curr.get(path_key):
                    payload = self._read_binary_asset_bytes(curr.get(path_key))
                    if payload is not None:
                        curr[field] = payload
                        loaded_any = True
            if loaded_any:
                try:
                    self.touch_page_payload_cache(page_idx)
                    self.trim_page_payload_cache(keep_indices=[page_idx])
                except Exception:
                    pass
        if include_masks:
            try:
                self.ensure_page_masks_loaded(page_idx)
                self.touch_page_mask_cache(page_idx)
                self.trim_page_mask_cache(keep_indices=[page_idx])
            except Exception:
                pass

    def page_runtime_fully_loaded(self, page_idx):
        try:
            page_idx = int(page_idx)
        except Exception:
            return False
        curr = (getattr(self, "data", {}) or {}).get(page_idx) if getattr(self, "data", None) else None
        if not isinstance(curr, dict):
            return False
        # 백그라운드 순차 로더는 UI 렉 방지를 위해 원본 디코딩 정도만 선로딩한다.
        # clean/final_paint/working_source 같은 heavy payload는 실제로 해당 페이지를 열 때만 읽는다.
        if curr.get('ori') is None and not curr.get('use_inpainted_as_source'):
            return False
        return True

    def _ensure_progressive_page_loader(self):
        if not hasattr(self, '_progressive_page_load_queue') or self._progressive_page_load_queue is None:
            self._progressive_page_load_queue = []
        if not hasattr(self, '_progressive_page_load_timer') or self._progressive_page_load_timer is None:
            timer = QTimer(self)
            timer.setSingleShot(False)
            timer.setInterval(120)
            timer.timeout.connect(self._progressive_page_load_tick)
            self._progressive_page_load_timer = timer

    def stop_progressive_page_loader(self):
        try:
            timer = getattr(self, '_progressive_page_load_timer', None)
            if timer is not None:
                timer.stop()
        except Exception:
            pass
        self._progressive_page_load_queue = []

    def schedule_progressive_page_load(self, priority_index=None):
        self._ensure_progressive_page_loader()
        total = len(getattr(self, 'paths', []) or [])
        if total <= 1:
            return
        try:
            priority = int(self.idx if priority_index is None else priority_index)
        except Exception:
            priority = int(getattr(self, 'idx', 0) or 0)
        priority = max(0, min(priority, total - 1))
        ordered = list(range(priority, total)) + list(range(0, priority))
        queue = []
        seen = set()
        for i in ordered:
            if i == priority or i in seen:
                continue
            seen.add(i)
            if not self.page_runtime_fully_loaded(i):
                queue.append(i)
        self._progressive_page_load_queue = queue
        try:
            timer = getattr(self, '_progressive_page_load_timer', None)
            if timer is not None and queue:
                timer.start()
            elif timer is not None:
                timer.stop()
        except Exception:
            pass

    def _progressive_page_load_tick(self):
        if getattr(self, '_app_is_closing', False) or getattr(self, 'is_loading_project', False):
            return
        try:
            pause_until = float(getattr(self, "_progressive_page_load_pause_until", 0.0) or 0.0)
            if pause_until > __import__("time").time():
                return
        except Exception:
            pass
        queue = list(getattr(self, '_progressive_page_load_queue', []) or [])
        if not queue:
            try:
                timer = getattr(self, '_progressive_page_load_timer', None)
                if timer is not None:
                    timer.stop()
            except Exception:
                pass
            return
        page_idx = queue.pop(0)
        self._progressive_page_load_queue = queue
        try:
            self.ensure_page_runtime_loaded(page_idx, include_ori=True, include_heavy=False, include_masks=False)
        except Exception:
            pass
        if not self._progressive_page_load_queue:
            try:
                timer = getattr(self, '_progressive_page_load_timer', None)
                if timer is not None:
                    timer.stop()
            except Exception:
                pass

    def _ensure_page_image_cache_state(self):
        if not hasattr(self, "_page_image_cache_order") or self._page_image_cache_order is None:
            self._page_image_cache_order = OrderedDict()
        try:
            limit = int(getattr(self, "page_image_cache_limit", 3) or 3)
        except Exception:
            limit = 3
        self.page_image_cache_limit = max(1, limit)

    def touch_page_image_cache(self, page_idx):
        self._ensure_page_image_cache_state()
        try:
            page_idx = int(page_idx)
        except Exception:
            return
        self._page_image_cache_order.pop(page_idx, None)
        self._page_image_cache_order[page_idx] = True

    def trim_page_image_cache(self, keep_indices=None):
        self._ensure_page_image_cache_state()
        keep = set()
        try:
            keep.add(int(getattr(self, "idx", -1)))
        except Exception:
            pass
        for raw in list(keep_indices or []):
            try:
                keep.add(int(raw))
            except Exception:
                pass

        # 현재 메모리에 원본 이미지를 들고 있는 페이지들만 대상으로 LRU 정리
        loaded = []
        for page_idx, curr in list((getattr(self, "data", {}) or {}).items()):
            if isinstance(curr, dict) and isinstance(curr.get('ori'), np.ndarray):
                loaded.append(int(page_idx))
                if page_idx not in self._page_image_cache_order:
                    self._page_image_cache_order[page_idx] = True

        while len(loaded) > self.page_image_cache_limit:
            victim = None
            for candidate in list(self._page_image_cache_order.keys()):
                if candidate in keep:
                    continue
                curr = (getattr(self, "data", {}) or {}).get(candidate)
                if isinstance(curr, dict) and isinstance(curr.get('ori'), np.ndarray):
                    victim = candidate
                    break
                self._page_image_cache_order.pop(candidate, None)
            if victim is None:
                break
            curr = self.data.get(victim)
            if isinstance(curr, dict):
                curr['ori'] = None
            self._page_image_cache_order.pop(victim, None)
            loaded = [idx for idx in loaded if idx != victim]

    def _ensure_page_mask_cache_state(self):
        if not hasattr(self, "_page_mask_cache_order") or self._page_mask_cache_order is None:
            self._page_mask_cache_order = OrderedDict()
        try:
            limit = int(getattr(self, "page_mask_cache_limit", 3) or 3)
        except Exception:
            limit = 3
        self.page_mask_cache_limit = max(1, limit)

    def touch_page_mask_cache(self, page_idx):
        self._ensure_page_mask_cache_state()
        try:
            page_idx = int(page_idx)
        except Exception:
            return
        self._page_mask_cache_order.pop(page_idx, None)
        self._page_mask_cache_order[page_idx] = True

    def resolve_project_asset_path(self, path_value):
        if not path_value:
            return None
        try:
            p = str(path_value)
            if os.path.isabs(p):
                return p
            root = str(getattr(self, "project_dir", "") or "")
            if root:
                return os.path.join(root, p.replace("/", os.sep))
        except Exception:
            return None
        return None

    def load_mask_array_from_path(self, path_value):
        path = self.resolve_project_asset_path(path_value)
        if not path or not os.path.exists(path):
            return None
        try:
            return np.load(path).copy()
        except Exception as e:
            try:
                self.log(f"⚠️ 마스크 지연 로딩 실패: {e}")
            except Exception:
                pass
            return None

    def ensure_page_masks_loaded(self, page_idx, keys=None):
        if page_idx < 0 or page_idx >= len(getattr(self, "paths", []) or []):
            return
        curr = (getattr(self, "data", {}) or {}).get(page_idx)
        if not isinstance(curr, dict):
            return
        keys = keys or ("mask_merge", "mask_inpaint", "mask_merge_off", "mask_inpaint_off")
        loaded = []
        if hasattr(self, "mask_engine") and self.mask_engine is not None:
            try:
                loaded = self.mask_engine.load_missing_masks(curr, keys=keys, loader=self.load_mask_array_from_path)
            except Exception:
                loaded = []
        if not loaded:
            loaded_any = False
            for key in keys:
                if curr.get(key) is not None:
                    continue
                path_key = f"{key}_path"
                mask = self.load_mask_array_from_path(curr.get(path_key))
                if mask is not None:
                    curr[key] = mask
                    loaded_any = True
            if loaded_any:
                loaded = list(keys)
        if loaded:
            self.touch_page_mask_cache(page_idx)

    def trim_page_mask_cache(self, keep_indices=None):
        self._ensure_page_mask_cache_state()
        keep = set()
        try:
            keep.add(int(getattr(self, "idx", -1)))
        except Exception:
            pass
        for raw in list(keep_indices or []):
            try:
                keep.add(int(raw))
            except Exception:
                pass

        mask_keys = ("mask_merge", "mask_inpaint", "mask_merge_off", "mask_inpaint_off")
        loaded = []
        for page_idx, curr in list((getattr(self, "data", {}) or {}).items()):
            if isinstance(curr, dict) and any(isinstance(curr.get(k), np.ndarray) for k in mask_keys):
                loaded.append(int(page_idx))
                if page_idx not in self._page_mask_cache_order:
                    self._page_mask_cache_order[page_idx] = True

        while len(loaded) > self.page_mask_cache_limit:
            victim = None
            for candidate in list(self._page_mask_cache_order.keys()):
                if candidate in keep:
                    continue
                curr = (getattr(self, "data", {}) or {}).get(candidate)
                if isinstance(curr, dict) and any(isinstance(curr.get(k), np.ndarray) for k in mask_keys):
                    victim = candidate
                    break
                self._page_mask_cache_order.pop(candidate, None)
            if victim is None:
                break
            curr = self.data.get(victim)
            if isinstance(curr, dict):
                if hasattr(self, "mask_engine") and self.mask_engine is not None:
                    try:
                        self.mask_engine.unload_saved_masks(curr, keys=mask_keys)
                    except Exception:
                        pass
                else:
                    for k in mask_keys:
                        # path가 있는 저장된 마스크만 메모리에서 내린다.
                        if curr.get(f"{k}_path") and not curr.get(f"{k}_dirty"):
                            curr[k] = None
            self._page_mask_cache_order.pop(victim, None)
            loaded = [idx for idx in loaded if idx != victim]

    def write_page_mask_to_disk(self, page_idx, key, mask):
        if mask is None or not getattr(self, "project_dir", None):
            return None
        subdirs = {
            "mask_merge": ("masks", "text_mask", f"mask_merge_{page_idx + 1:04d}.npy"),
            "mask_inpaint": ("masks", "paint_mask", f"mask_inpaint_{page_idx + 1:04d}.npy"),
            "mask_merge_off": ("masks", "text_mask_off", f"mask_merge_off_{page_idx + 1:04d}.npy"),
            "mask_inpaint_off": ("masks", "paint_mask_off", f"mask_inpaint_off_{page_idx + 1:04d}.npy"),
        }
        parts = subdirs.get(key)
        if not parts:
            return None
        try:
            out_dir = os.path.join(str(self.project_dir), *parts[:-1])
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, parts[-1])
            np.save(out_path, np.array(mask, dtype=np.uint8).copy())
            return out_path
        except Exception as e:
            try:
                self.log(f"⚠️ 마스크 디스크 내보내기 실패({page_idx + 1}p/{key}): {e}")
            except Exception:
                pass
            return None

    def spill_payload_masks_to_disk(self, page_idx, curr, payload):
        if not isinstance(curr, dict) or not isinstance(payload, dict):
            return
        for key in ("mask_merge", "mask_inpaint"):
            value = payload.get(key)
            if not isinstance(value, np.ndarray):
                continue
            out_path = self.write_page_mask_to_disk(page_idx, key, value)
            if out_path:
                curr[f"{key}_path"] = out_path
                curr[f"{key}_dirty"] = False
                payload[f"{key}_path"] = out_path
                payload[key] = None

    def make_page_data_for_image(self, image_path, original_name=None):
        return {
            'ori': None,
            'data': [],
            'mask_merge': None,
            'mask_inpaint': None,
            'mask_merge_off': None,
            'mask_inpaint_off': None,
            'mask_merge_path': None,
            'mask_inpaint_path': None,
            'mask_merge_off_path': None,
            'mask_inpaint_off_path': None,
            'mask_toggle_enabled': False,
            'use_inpainted_as_source': False,
            'bg_clean': None,
            'working_source': None,
            'final_paint': None,
            'final_paint_above': None,
            'ocr_analysis_regions': [],
            'original_name': original_name or os.path.basename(image_path),
        }

    def insert_images_at_position(self, source_paths, insert_at=0, source_label="이미지 삽입"):
        source_paths = self.normalize_image_drop_paths(source_paths)
        if not source_paths:
            return False
        if not self.project_dir:
            return self.create_new_project_from_image_paths(source_paths, source_label=source_label)
        if not self.guard_project_action("이미지 삽입"):
            return False
        self.commit_current_page_ui_to_data()
        self.remember_current_view_state()
        before_structure_state = self._snapshot_project_structure_state("이미지 삽입")
        insert_at = max(0, min(int(insert_at), len(self.paths)))
        copied_paths = []
        copied_data = []
        for src in source_paths:
            dst = self.unique_insert_image_path(src)
            shutil.copy2(src, dst)
            copied_paths.append(dst)
            copied_data.append(self.make_page_data_for_image(dst, original_name=os.path.basename(dst)))

        old_paths = list(self.paths)
        old_data = dict(self.data or {})
        self.paths = old_paths[:insert_at] + copied_paths + old_paths[insert_at:]
        new_data = {}
        for new_i in range(len(self.paths)):
            if new_i < insert_at:
                if new_i in old_data:
                    new_data[new_i] = old_data[new_i]
            elif new_i < insert_at + len(copied_data):
                new_data[new_i] = copied_data[new_i - insert_at]
            else:
                old_i = new_i - len(copied_data)
                if old_i in old_data:
                    new_data[new_i] = old_data[old_i]
        self.data = new_data

        states = getattr(self, "project_ui_view_states", {}) or {}
        shifted_states = {}
        for key, state in states.items():
            try:
                page_s, mode_s = str(key).split(":", 1)
                old_page = int(page_s)
                new_page = old_page + len(copied_data) if old_page >= insert_at else old_page
                shifted_states[f"{new_page}:{int(mode_s)}"] = copy.deepcopy(state)
            except Exception:
                pass
        self.project_ui_view_states = shifted_states
        self.idx = insert_at
        after_structure_state = self._snapshot_project_structure_state("이미지 삽입")
        self.undo_clear_all_pages("image insert")
        self.push_project_structure_command(before_structure_state, after_structure_state, reason="이미지 삽입", action="page_insert")
        # 이미지 추가는 구조 변경이다. 원본 파일은 이미 workspace/images에 복사되어 있으므로,
        # project.json도 즉시 저장해 JSON 열기/복구가 바로 같은 맵 목록을 보게 한다.
        self.flush_workspace_structure_after_image_insert(reason="image_insert")
        self.load()
        self.log(f"🖼️ 이미지 {len(copied_paths)}장 삽입: {insert_at + 1}페이지부터")
        return True

    def insert_images_after_current(self, source_paths):
        insert_at = (self.idx + 1) if self.paths else 0
        return self.insert_images_at_position(source_paths, insert_at=insert_at, source_label="드래그 앤 드롭")

    def import_images_at_end_action(self):
        # 이전 버전 호환용: + 탭도 일반 게임 가져오기와 같은 동작을 사용한다.
        return self.import_images_action()

    def _dragged_local_files(self, event):
        try:
            mime = event.mimeData()
            if not mime or not mime.hasUrls():
                return []
            out = []
            for url in mime.urls():
                path = url.toLocalFile()
                if path:
                    out.append(os.path.abspath(path))
            return out
        except Exception:
            return []

    def _dragged_image_paths(self, event):
        return self.normalize_image_drop_paths(self._dragged_local_files(event))

    def _dragged_supported_files(self, event):
        files = self._dragged_local_files(event)
        images = self.normalize_image_drop_paths(files)
        ysb = ""
        for path in files:
            if path and str(path).lower().endswith(YSB_EXTENSION):
                ysb = os.path.abspath(path)
                break
        return images, ysb

    def handle_supported_file_drop(self, event):
        images, ysb_path = self._dragged_supported_files(event)
        if images:
            if self.project_dir:
                return self.insert_images_after_current(images)
            return self.create_new_project_from_image_paths(images, source_label="드래그 앤 드롭")
        if ysb_path:
            if not self.guard_project_action("YSBG 파일 드래그 열기"):
                return False
            if not self.confirm_close_current_project_for_open(ysb_path):
                return False
            self.open_project_path(ysb_path, external_request=True)
            self.force_app_focus(reason="drag and drop open")
            return True
        return False

    def _dragged_ysbt_path(self, event):
        _images, ysb = self._dragged_supported_files(event)
        return ysb

    def dragEnterEvent(self, event):
        images, ysb = self._dragged_supported_files(event)
        if images or ysb:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        images, ysb = self._dragged_supported_files(event)
        if images or ysb:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        images, ysb = self._dragged_supported_files(event)
        if not images and not ysb:
            event.ignore()
            return
        event.acceptProposedAction()
        self.handle_supported_file_drop(event)

    def change_workspace_location(self):
        """옵션 메뉴에서 작업 폴더 설정 창을 다시 연다.

        첫 실행 설정창과 같은 UI를 쓰되, 닫기를 눌러도 프로그램은 종료하지 않는다.
        위치가 바뀐 경우에는 다음 실행 시 이동되도록 예약한다.
        """
        if not self.guard_project_action("작업 폴더 위치 변경"):
            return
        dlg = WorkspaceSetupDialog(self, first_run=False)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.workspace_root = str(get_workspace_root())
            self.log("📁 작업 폴더 설정 확인")
        else:
            self.log("📁 작업 폴더 설정 변경 취소")

    def reset_workspace_location_to_default(self, parent=None):
        """작업 폴더 위치를 Windows 실제 문서 폴더 기준 기본값으로 되돌린 뒤 재기동한다."""
        if not self.guard_project_action("작업 폴더 위치 기본값으로 변경"):
            return
        parent = parent or self
        target = default_workspace_root()
        try:
            current = Path(load_workspace_config().get("workspace_root") or get_workspace_root()).resolve()
            target_resolved = target.resolve()
        except Exception:
            current = Path(str(get_workspace_root()))
            target_resolved = target

        if current == target_resolved:
            set_workspace_root(target)
            QMessageBox.information(
                parent,
                self.tr_ui("설정 완료"),
                f"{self.tr_ui('작업 폴더 위치가 이미 기본값입니다.')}\n\n{target}",
            )
            self.log(f"📁 작업 폴더 기본값 확인: {target}")
            return

        if not workspace_restart_confirmation(parent, current, target, self.ui_language):
            self.log("📁 작업 폴더 기본값 변경 취소")
            return

        try:
            schedule_workspace_root_change(target)
            self.log(f"📁 작업 폴더 기본값 변경 예약 및 재기동: {target}")
            restart_application_detached()
        except Exception as e:
            QMessageBox.critical(
                parent,
                self.tr_ui("내보내기 실패"),
                f"{self.tr_ui('작업 폴더 위치를 기본값으로 변경하지 못했습니다.')}\n{e}",
            )

    def register_ysb_file_association(self):
        if not is_windows():
            QMessageBox.information(self, self.tr_ui("지원 안내"), self.tr_msg(".ysbg 확장자 연결 등록은 Windows에서만 지원합니다."))
            return
        if is_ysbt_file_association_registered():
            QMessageBox.information(self, self.tr_ui("이미 등록됨"), self.tr_msg(".ysbg 확장자가 현재 실행 중인 쯔꾸르붕이에 이미 연결되어 있습니다."))
            return

        if is_ysbt_file_association_registered_to_other_ysb():
            registered = get_registered_ysbt_file_association_command() or "알 수 없음"
            message = (
                ".ysbg 확장자가 다른 위치의 쯔꾸르붕이에 연결되어 있습니다.\n"
                "현재 실행 중인 프로그램으로 연결을 갱신할까요?\n\n"
                f"현재 등록된 실행 명령:\n{registered}\n\n"
                "이 작업은 Windows의 확장자 연결 정보만 현재 프로그램으로 덮어씁니다. 기존 .ysbg 프로젝트 파일은 변경되지 않습니다."
            )
        else:
            message = (
                "현재 사용자 계정에 .ysbg 확장자 연결을 등록합니다.\n"
                "등록 후 .ysbg 파일을 더블클릭하면 쯔꾸르붕이로 열립니다. 계속할까요?"
            )

        ans = QMessageBox.question(
            self,
            self.tr_ui(".ysbg 확장자 연결 등록"),
            self.tr_msg(message),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            register_ysbt_file_association_raw()
            QMessageBox.information(self, self.tr_ui("등록 완료"), self.tr_ui(".ysbg 확장자 연결을 현재 실행 중인 쯔꾸르붕이로 등록했습니다.\n아이콘 표시는 Windows 아이콘 캐시 때문에 조금 늦게 갱신될 수 있습니다."))
            self.log("🔗 .ysbg 확장자 연결 등록/갱신 완료")
        except Exception as e:
            QMessageBox.critical(self, self.tr_ui("등록 실패"), f"{self.tr_ui('.ysbg 확장자 연결 등록에 실패했습니다.')}\n{e}")

    def unregister_ysbt_file_association(self):
        """현재 사용자 계정에 등록된 .ysbg 연결을 제거한다.

        이전 테스트 버전에서 이 프로그램이 등록한 .ysb 연결도 함께 정리한다.
        단, 다른 프로그램에 연결된 .ysb는 변경하지 않는다.
        """
        if not is_windows():
            QMessageBox.information(self, self.tr_ui("지원 안내"), self.tr_ui("확장자 연결 해제는 Windows에서만 지원합니다."))
            return
        ans = QMessageBox.question(
            self,
            self.tr_ui("확장자 연결 해제"),
            self.tr_ui("현재 사용자 계정의 .ysbg 연결을 해제합니다.\n이전 테스트 버전에서 이 프로그램이 등록한 .ysb 연결도 함께 정리합니다.\n다른 프로그램에 연결된 .ysb는 변경하지 않습니다.\n\n계속할까요?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            removed = unregister_ysbt_file_association_raw(include_legacy=True)
            msg = self.tr_ui("확장자 연결 해제를 완료했습니다.")
            if removed:
                msg += "\n\n" + self.tr_ui("제거 항목") + ":\n- " + "\n- ".join(removed)
            else:
                msg += "\n\n" + self.tr_ui("제거할 연결 항목이 없었습니다.")
            QMessageBox.information(self, self.tr_ui("해제 완료"), msg)
            self.log("🔗 확장자 연결 해제 완료: " + (", ".join(removed) if removed else "제거 항목 없음"))
        except Exception as e:
            QMessageBox.critical(self, self.tr_ui("해제 실패"), f"{self.tr_ui('확장자 연결 해제에 실패했습니다.')}\n{e}")

    def workspace_temp_project_dir(self, project_name="unsaved_project"):
        """새 프로젝트용 임시 작업 폴더를 만든다.

        v1.8 런처 이후에는 사용자가 작업 폴더를 문서/YSB_Translator로 잡아두었는지
        바로 확인할 수 있어야 하므로, 새 프로젝트의 임시 작업도 workspaces 아래에 만든다.
        아직 .ysbg로 저장되지 않은 상태라는 의미는 is_temp_project 플래그로 관리한다.
        """
        safe = safe_project_name(project_name)
        return unique_dir(workspaces_dir(), f"unsaved_{safe}_{uuid.uuid4().hex[:8]}")

    def workspace_project_dir(self, project_name="ysb_project", code=None, *, append_code=True):
        safe = clean_workspace_name(project_name)
        return unique_dir_with_code_suffix(workspaces_dir(), safe, code, append_code=append_code)

    def normalize_ysb_path(self, path):
        if not path:
            return path
        return path if path.lower().endswith(YSB_EXTENSION) else path + YSB_EXTENSION

    def current_package_default_path(self):
        base = getattr(self, "suggested_project_name", None) or (Path(self.project_dir).name if self.project_dir else "ysb_project")
        base = clean_workspace_name(base)
        try:
            package_dir = Path(getattr(self, "suggested_package_dir", None) or default_package_dir())
        except Exception:
            package_dir = default_package_dir()
        return str(package_dir / f"{safe_project_name(base)}{YSB_EXTENSION}")

    def delete_temp_project_if_needed(self):
        """저장되지 않은 임시 프로젝트 폴더를 안전하게 삭제한다.

        예전에는 임시 프로젝트가 temp 아래에만 있었지만, v1.8 런처 이후 새 프로젝트는
        사용자가 지정한 작업 폴더의 workspaces 아래에 unsaved_* 형태로 보이게 만든다.
        따라서 is_temp_project=True이고 아직 .ysbg 패키지에 연결되지 않은 경우에는
        temp/workspaces 내부의 unsaved_* 폴더를 정리한다.
        """
        if self.is_temp_project and self.project_dir and os.path.exists(self.project_dir):
            try:
                proj = os.path.abspath(self.project_dir)
                roots = [os.path.abspath(str(temp_dir()))]
                name = os.path.basename(proj)
                can_delete = (not getattr(self, "ysbg_package_path", None)) and name.startswith("unsaved_")
                if can_delete and any(proj.startswith(root) for root in roots):
                    shutil.rmtree(self.project_dir, ignore_errors=True)
                    self.log(f"🧹 임시 프로젝트 삭제: {self.project_dir}")
                elif can_delete:
                    self.log(f"🧷 workspaces 임시 프로젝트 자동 삭제 생략: {self.project_dir}")
            except Exception:
                pass
        self.is_temp_project = False

    def promote_temp_project_to_workspace(self, project_name=None):
        if not self.is_temp_project:
            return True
        if not self.project_dir or not os.path.exists(self.project_dir):
            return False

        name = clean_workspace_name(project_name or Path(self.project_dir).name)
        dst = self.workspace_project_dir(name)
        old_dir = self.project_dir
        try:
            # 현재 temp 프로젝트 내보내기 후, 새 폴더를 만들지 않고 temp 폴더 자체를 정식 작업 폴더로 승격한다.
            self.save_project_store(self.project_store)
            if os.path.abspath(old_dir) != os.path.abspath(dst):
                shutil.move(old_dir, dst)
            self.project_dir = dst
            self.project_store = ProjectStore(dst)
            # UUID는 manifest 내부에 유지하고, 폴더명/프로젝트명은 깔끔한 이름으로 갱신한다.
            self.project_store.write_manifest(project_name=name)
            self.is_temp_project = False

            # 혹시 이전 버전에서 workspaces 안에 unsaved_* 찌꺼기가 생겼다면,
            # 현재 승격한 폴더와 다른 빈/동일 임시 폴더만 안전하게 제거한다.
            try:
                ws_root = os.path.abspath(str(workspaces_dir()))
                old_abs = os.path.abspath(old_dir)
                dst_abs = os.path.abspath(dst)
                if old_abs.startswith(ws_root) and os.path.basename(old_abs).startswith("unsaved_") and old_abs != dst_abs and os.path.exists(old_abs):
                    # workspaces는 복구 기준 작업 공간이므로 자동 삭제하지 않는다.
                    pass
            except Exception:
                pass

            self.reload_saved_project_from_disk(refresh_view=False)
            self.log(f"📦 임시 프로젝트를 작업 폴더로 승격: {dst}")
            return True
        except Exception as e:
            msg_text = self.tr_ui("임시 프로젝트를 작업 폴더로 옮기지 못했습니다.")
            QMessageBox.critical(self, self.tr_ui("프로젝트 이동 실패"), f"{msg_text}\n{e}")
            return False

    def workspace_state_path_for_project_dir(self, project_dir):
        try:
            project_dir = os.path.abspath(str(project_dir or ""))
            if not project_dir:
                return None
            return os.path.join(project_dir, WORKSPACE_STATE_FILENAME)
        except Exception:
            return None

    def write_workspace_state_for_project(self, project_dir, *, is_dirty=True):
        """복구용 별도 캐시를 만들지 않고, workspace 자체에 작은 상태표만 붙인다."""
        try:
            if not project_dir:
                return
            project_dir = os.path.abspath(str(project_dir))
            if not os.path.exists(os.path.join(project_dir, PROJECT_FILENAME)):
                return

            dirty_pages = []
            dirty_summary = {}
            dirty_by_kind = {}
            try:
                if hasattr(self, "project_engine") and self.project_engine is not None:
                    dirty_pages = sorted(int(x) for x in self.project_engine.dirty_page_indices())
                    try:
                        dirty_summary = self.project_engine.dirty_summary()
                    except Exception:
                        dirty_summary = {}
            except Exception:
                dirty_pages = []
                dirty_summary = {}
            try:
                raw_dirty = dirty_summary.get("dirty_pages", {}) if isinstance(dirty_summary, dict) else {}
                if isinstance(raw_dirty, dict):
                    for page_key, kinds in raw_dirty.items():
                        try:
                            page_i = int(page_key)
                        except Exception:
                            continue
                        for kind in list(kinds or []):
                            kind_s = str(kind or "data")
                            dirty_by_kind.setdefault(kind_s, []).append(page_i)
                    dirty_by_kind = {k: sorted(set(v)) for k, v in dirty_by_kind.items()}
            except Exception:
                dirty_by_kind = {}

            write_workspace_state(
                project_dir,
                source_ysbg_path=str(getattr(self, "ysbg_package_path", "") or ""),
                project_name=str(getattr(self, "suggested_project_name", "") or Path(project_dir).name),
                is_dirty=bool(is_dirty),
                is_recovery=bool(is_dirty),
                dirty_pages=dirty_pages,
                dirty_by_kind=dirty_by_kind,
                text_dirty_pages=sorted(set(dirty_by_kind.get("text", []) + dirty_by_kind.get("checkpoint_text", []) + dirty_by_kind.get("checkpoint_fallback", []))),
                clean_dirty_pages=sorted(set(dirty_by_kind.get("clean_background", []) + dirty_by_kind.get("clean_import", []) + dirty_by_kind.get("final_paint", []))),
                mask_dirty_pages=sorted(set(dirty_by_kind.get("mask", []) + dirty_by_kind.get("mask_merge", []) + dirty_by_kind.get("mask_inpaint", []))),
                last_page_index=int(getattr(self, "idx", 0) or 0),
                last_mode=int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 0,
            )
        except Exception:
            pass

    def mark_workspace_state_saved(self, project_dir):
        try:
            if not project_dir:
                return
            self.write_workspace_state_for_project(project_dir, is_dirty=False)
        except Exception:
            pass

    def is_path_under_root(self, path, root):
        try:
            p = Path(str(path)).resolve()
            r = Path(str(root)).resolve()
            return str(p).lower() == str(r).lower() or str(p).lower().startswith(str(r).lower() + os.sep)
        except Exception:
            return False

    def is_workspace_project_dir_path(self, path):
        try:
            if not path:
                return False
            p = Path(str(path)).resolve()
            return self.is_path_under_root(p, workspaces_dir()) and (p / PROJECT_FILENAME).exists()
        except Exception:
            return False

    def record_recovery_project_dir(self, project_dir):
        """마지막 작업 폴더를 기록한다. 복구 데이터 본체는 이 workspace 자체다."""
        try:
            if not project_dir:
                return
            project_dir = os.path.abspath(str(project_dir))
            if not os.path.exists(os.path.join(project_dir, PROJECT_FILENAME)):
                return
            self.app_options["last_recovery_project_dir"] = project_dir
            save_app_options(self.app_options)
            self.write_workspace_state_for_project(project_dir, is_dirty=True)
        except Exception:
            pass

    def recovery_candidate_roots(self):
        # 새 구조에서는 workspaces가 실제 작업대이자 복구본이다.
        # workspaces는 위의 상태표 스캔에서 dirty/(복구) 폴더만 골라 보고,
        # 여기서는 temp와 구버전 work_sessions 호환 후보만 전체 검색한다.
        return [temp_dir(), self.project_cache_root()]

    def find_recovery_candidates(self):
        """work_sessions/temp 안에서 project.json 또는 pending 클린본 복구 후보를 최신순으로 찾는다."""
        candidates = []
        seen = set()

        def candidate_key(project_dir, pending_dir=None):
            try:
                return (str(Path(str(project_dir)).resolve()), str(Path(str(pending_dir)).resolve()) if pending_dir else "")
            except Exception:
                return (str(project_dir), str(pending_dir or ""))

        def add_candidate(path, pending_dir=None, mtime_hint=None):
            try:
                p = Path(path)
                project_file = p / PROJECT_FILENAME
                if not project_file.exists():
                    return
                key = candidate_key(str(p), pending_dir)
                if key in seen:
                    return
                seen.add(key)
                try:
                    mtime = max(project_file.stat().st_mtime, p.stat().st_mtime)
                except Exception:
                    mtime = p.stat().st_mtime if p.exists() else 0
                if mtime_hint:
                    try:
                        mtime = max(float(mtime), float(mtime_hint))
                    except Exception:
                        pass
                # 4번째 값은 pending 클린본 복구 폴더다. 구 후보는 None.
                candidates.append((mtime, str(p), str(project_file), str(pending_dir) if pending_dir else None))
            except Exception:
                pass

        def add_pending_candidate(pending_base):
            """pending_clean_import_map.json만 있는 후보도 원본 프로젝트와 엮어 복구 후보로 등록한다."""
            try:
                if not pending_base:
                    return
                pending_base = os.path.abspath(str(pending_base))
                manifest_path = self.pending_clean_import_manifest_path(pending_base)
                if not manifest_path or not os.path.exists(manifest_path):
                    return
                manifest = self.load_pending_clean_import_manifest(pending_base)
                pages = manifest.get("pages") if isinstance(manifest, dict) else None
                if not isinstance(pages, dict) or not pages:
                    return
                mtime_hint = None
                try:
                    mtime_hint = os.path.getmtime(manifest_path)
                except Exception:
                    pass

                # 가장 안전한 순서:
                # 1) pending_base 자체에 project.json이 있으면 그 폴더를 복구
                # 2) manifest에 기록된 원래 project_dir/work_project_dir의 project.json을 복구
                roots = [pending_base]
                for key in ("project_dir", "work_project_dir"):
                    value = str(manifest.get(key) or "").strip()
                    if value:
                        roots.append(value)
                for root in roots:
                    try:
                        root = os.path.abspath(str(root))
                    except Exception:
                        continue
                    if os.path.exists(os.path.join(root, PROJECT_FILENAME)):
                        add_candidate(root, pending_dir=pending_base, mtime_hint=mtime_hint)
                        return
            except Exception:
                pass

        # 1순위: 마지막 작업 캐시로 명시 기록한 폴더
        last_dir = str((self.app_options or {}).get("last_recovery_project_dir") or "").strip()
        if last_dir:
            add_candidate(last_dir)
            add_pending_candidate(last_dir)

        # 1.5순위: 클린본 pending 복구 후보로 명시 기록한 폴더
        last_pending_dir = str((self.app_options or {}).get("last_pending_clean_import_dir") or "").strip()
        if last_pending_dir:
            add_pending_candidate(last_pending_dir)

        # 2순위: workspaces의 상태표 검색
        try:
            ws_root = Path(workspaces_dir())
            if ws_root.exists():
                for child in ws_root.iterdir():
                    if not child.is_dir():
                        continue
                    state_path = child / WORKSPACE_STATE_FILENAME
                    state = {}
                    try:
                        if state_path.exists():
                            with open(state_path, "r", encoding="utf-8") as f:
                                loaded = json.load(f)
                            state = loaded if isinstance(loaded, dict) else {}
                    except Exception:
                        state = {}
                    is_dirty = bool(state.get("is_dirty", False)) or "(복구)" in child.name
                    if is_dirty:
                        mtime_hint = None
                        try:
                            mtime_hint = max(state_path.stat().st_mtime, child.stat().st_mtime) if state_path.exists() else child.stat().st_mtime
                        except Exception:
                            pass
                        add_candidate(child, mtime_hint=mtime_hint)
        except Exception:
            pass

        # 2.5순위: 구버전 work_sessions marker 호환 검색
        try:
            marker_root = self.project_cache_root()
            for marker in marker_root.glob("recovery_marker_*.json"):
                try:
                    with open(marker, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    project_dir = str(payload.get("project_dir") or "").strip()
                    if project_dir:
                        add_candidate(project_dir, mtime_hint=os.path.getmtime(marker))
                except Exception:
                    pass
        except Exception:
            pass

        # 3순위: workspaces / temp / 구 work cache 폴더 전체 검색
        for root in self.recovery_candidate_roots():
            try:
                root = Path(root)
                if not root.exists():
                    continue
                for child in root.iterdir():
                    if child.is_dir():
                        add_candidate(child)
                        add_pending_candidate(child)
            except Exception:
                pass

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates

    def recover_last_work_project(self):
        """마지막 작업 캐시/임시 프로젝트를 열어 복구한다."""
        if not self.guard_project_action("마지막 작업 복구"):
            return
        candidates = self.find_recovery_candidates()
        if not candidates:
            QMessageBox.information(
                self,
                self.tr_ui("복구할 작업 없음"),
                self.tr_ui("복구할 수 있는 임시 작업 파일을 찾지 못했습니다."),
            )
            self.log("⚠️ 복구할 임시 작업 파일 없음")
            return

        first = candidates[0]
        if len(first) >= 4:
            _mtime, project_dir, project_file, pending_clean_dir = first[:4]
        else:
            _mtime, project_dir, project_file = first[:3]
            pending_clean_dir = None
        msg = (
            f"{self.tr_ui('마지막 작업 폴더를 복구할까요?')}\n\n"
            f"{project_dir}\n\n"
            f"{self.tr_ui('복구한 작업은 아직 정식 YSBG 파일이 아닐 수 있습니다. 필요한 경우 [프로젝트 내보내기]으로 다시 저장해 주세요.')}"
        )
        ans = QMessageBox.question(
            self,
            self.tr_ui("마지막 작업 복구"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            self.log("↩️ 마지막 작업 복구 취소")
            return

        if not self.confirm_unsaved_before_switch():
            return

        shown_overlay = False
        old_load_progress = getattr(self, "_project_load_progress_callback", None)
        old_loading_recovery = bool(getattr(self, "_loading_recovery_project", False))
        self._long_task_cancel_requested = False
        self._active_long_task_kind = "recover"

        def _recover_progress(current=0, total=100, detail="복구 준비 중..."):
            try:
                show_total = max(1, int(total or 100))
                show_current = max(0, min(show_total, int(current or 0)))
                folder_name = os.path.basename(str(project_dir))
                formatted = (
                    f"{self.tr_ui('복구 폴더')}: {folder_name}\n"
                    f"{str(detail or '')}"
                )
                self.update_task_progress_overlay(current=show_current, total=show_total, detail=formatted)
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            except Exception:
                pass

        try:
            self.begin_busy_state("마지막 작업 복구")
            self.show_task_progress_overlay(
                "마지막 작업 복구",
                f"{self.tr_ui('복구 폴더')}: {os.path.basename(str(project_dir))}\n복구 준비 중...",
                total=100,
                cancellable=False,
            )
            shown_overlay = True
            try:
                overlay = getattr(self, "_task_progress_overlay", None)
                if overlay is not None:
                    overlay.note_label.setText("복구 중에는 프로젝트 데이터를 읽고 화면을 다시 구성합니다.")
            except Exception:
                pass
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

            self._loading_recovery_project = True
            self._project_load_progress_callback = _recover_progress

            _recover_progress(8, 100, "복구 프로젝트 파일을 읽는 중...")
            # 복구는 별도 캐시를 여는 것이 아니라, 남아 있는 workspace 작업대를 직접 여는 것이다.
            # 상태표에 원본 .ysbg가 있으면 그대로 연결해 [프로젝트 내보내기]으로 확정할 수 있게 한다.
            workspace_state = {}
            try:
                workspace_state = read_workspace_state(project_dir)
            except Exception:
                workspace_state = {}
            source_package = str(workspace_state.get("source_ysbg_path") or workspace_state.get("package_path") or "").strip() if isinstance(workspace_state, dict) else ""
            if source_package and not os.path.exists(source_package):
                source_package = ""
            self.load_project_json(project_file, package_path=source_package or None, temp_project=False)

            if pending_clean_dir:
                try:
                    _recover_progress(86, 100, "pending 클린본 복구를 적용하는 중...")
                    restored = self.apply_pending_clean_import_if_available(pending_clean_dir)
                    if restored:
                        self.log(f"🧯 pending 클린본 복구 추가 적용: {restored}페이지")
                except Exception as e:
                    self.log(f"⚠️ pending 클린본 복구 추가 적용 실패: {e}")

            _recover_progress(94, 100, "복구 상태를 정리하는 중...")
            if source_package:
                self.ysbg_package_path = source_package
                self.is_temp_project = False
            else:
                self.is_temp_project = True
            self.has_unsaved_changes = True
            self.record_recovery_project_dir(project_dir)
            try:
                if pending_clean_dir:
                    self.app_options["last_pending_clean_import_dir"] = str(pending_clean_dir)
                    save_app_options(self.app_options)
            except Exception:
                pass
            self.update_window_title()
            self.log(f"🧯 마지막 작업 복구 완료: {project_dir}")
            self.log("💾 복구한 작업은 [내보내기]으로 YSBG 파일에 확정하세요.")
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr_ui("복구 실패"),
                f"{self.tr_ui('마지막 작업을 복구하지 못했습니다.')}\n{project_dir}\n\n{e}",
            )
            self.log(f"❌ 마지막 작업 복구 실패: {e}")
        finally:
            try:
                self._project_load_progress_callback = old_load_progress
            except Exception:
                pass
            try:
                self._loading_recovery_project = old_loading_recovery
            except Exception:
                pass
            try:
                self._active_long_task_kind = ""
                self._long_task_cancel_requested = False
            except Exception:
                pass
            try:
                if shown_overlay:
                    self.hide_task_progress_overlay()
            except Exception:
                pass
            try:
                self.end_busy_state()
            except Exception:
                pass

    def temp_path_created_timestamp(self, path):
        """폴더 생성 시각을 우선 사용하고, 불가능하면 수정 시각을 사용한다."""
        try:
            return Path(path).stat().st_ctime
        except Exception:
            try:
                return Path(path).stat().st_mtime
            except Exception:
                return 0

    def temp_cleanup_category_roots(self):
        return [
            ("temp", self.tr_ui("임시 프로젝트"), temp_dir()),
            ("work_sessions", self.tr_ui("작업 캐시"), self.project_cache_root()),
        ]

    def empty_temp_cleanup_summary(self):
        return {
            "temp": {"label": self.tr_ui("임시 프로젝트"), "count": 0, "size": 0},
            "work_sessions": {"label": self.tr_ui("작업 캐시"), "count": 0, "size": 0},
        }

    def format_size_mb(self, size_bytes):
        try:
            return f"{float(size_bytes or 0) / (1024 * 1024):.1f} MB"
        except Exception:
            return "0.0 MB"

    def collect_temp_cleanup_targets(self, *, older_than_days=None, skip_current=True, exclude_recovery=False):
        """temp/work_sessions에서 삭제 가능한 임시 작업 폴더를 분류별로 모은다."""
        skip_dirs = set()
        if skip_current:
            for p in (getattr(self, "project_dir", None), getattr(self, "work_project_dir", None)):
                if p:
                    try:
                        skip_dirs.add(str(Path(p).resolve()))
                    except Exception:
                        pass

        if exclude_recovery:
            try:
                last_dir = str((self.app_options or {}).get("last_recovery_project_dir") or "").strip()
                if last_dir:
                    skip_dirs.add(str(Path(last_dir).resolve()))
            except Exception:
                pass

        now_ts = time.time()
        max_age_seconds = None
        if older_than_days is not None:
            try:
                max_age_seconds = max(0, int(older_than_days)) * 24 * 60 * 60
            except Exception:
                max_age_seconds = None

        targets = []
        total_size = 0
        summary = self.empty_temp_cleanup_summary()

        for key, label, root in self.temp_cleanup_category_roots():
            try:
                root = Path(root)
                if not root.exists():
                    continue
                for child in root.iterdir():
                    if not child.is_dir():
                        continue
                    try:
                        resolved = str(child.resolve())
                    except Exception:
                        resolved = str(child)
                    if resolved in skip_dirs:
                        continue

                    if max_age_seconds is not None:
                        created_ts = self.temp_path_created_timestamp(child)
                        if created_ts and (now_ts - created_ts) < max_age_seconds:
                            continue

                    folder_size = 0
                    try:
                        for file in child.rglob("*"):
                            if file.is_file():
                                folder_size += file.stat().st_size
                    except Exception:
                        pass

                    targets.append(child)
                    total_size += folder_size
                    summary.setdefault(key, {"label": label, "count": 0, "size": 0})
                    summary[key]["label"] = label
                    summary[key]["count"] += 1
                    summary[key]["size"] += folder_size
            except Exception:
                pass

        return targets, total_size, summary

    def temp_cleanup_summary_text(self, summary, total_count=None, total_size=None):
        summary = summary or self.empty_temp_cleanup_summary()
        temp_info = summary.get("temp", {})
        work_info = summary.get("work_sessions", {})
        if total_count is None:
            total_count = int(temp_info.get("count", 0) or 0) + int(work_info.get("count", 0) or 0)
        if total_size is None:
            total_size = int(temp_info.get("size", 0) or 0) + int(work_info.get("size", 0) or 0)
        return (
            f"{self.tr_ui('임시 프로젝트')}: {int(temp_info.get('count', 0) or 0)} / {self.format_size_mb(temp_info.get('size', 0))}\n"
            f"{self.tr_ui('작업 캐시')}: {int(work_info.get('count', 0) or 0)} / {self.format_size_mb(work_info.get('size', 0))}\n"
            f"{self.tr_ui('총합')}: {int(total_count or 0)} / {self.format_size_mb(total_size)}"
        )

    def temp_cleanup_period_options(self):
        return [
            (7, "일주일"),
            (30, "한달"),
            (90, "3개월"),
            (180, "6개월"),
            (365, "12개월"),
        ]

    def get_temp_auto_cleanup_days(self):
        try:
            days = int((self.app_options or {}).get("temp_auto_cleanup_days", 7) or 7)
        except Exception:
            days = 7
        if days not in (7, 30, 90, 180, 365):
            days = 7
        return days

    def is_temp_auto_cleanup_enabled(self):
        return bool((self.app_options or {}).get("temp_auto_cleanup_enabled", True))

    def set_temp_cleanup_options(self, enabled=None, days=None):
        try:
            if enabled is not None:
                self.app_options["temp_auto_cleanup_enabled"] = bool(enabled)
            if days is not None:
                days = int(days)
                if days not in (7, 30, 90, 180, 365):
                    days = 7
                self.app_options["temp_auto_cleanup_days"] = days
            save_app_options(self.app_options)
        except Exception:
            pass

    def auto_cleanup_temp_files_if_needed(self):
        """설정된 주기마다, 설정된 기간 이상 지난 임시 작업 폴더를 자동 삭제한다."""
        try:
            if not self.is_temp_auto_cleanup_enabled():
                self.log(
                    "🧹 Auto temp cleanup is disabled."
                    if getattr(self, "ui_language", LANG_KO) == LANG_EN else
                    "🧹 자동 임시 파일 정리: 꺼짐"
                )
                return

            period_days = self.get_temp_auto_cleanup_days()
            max_age_days = period_days
            now_ts = time.time()
            last_ts = float((self.app_options or {}).get("last_temp_auto_cleanup_at", 0) or 0)
            if last_ts and (now_ts - last_ts) < period_days * 24 * 60 * 60:
                return

            # 자동 정리는 AppData 실행 캐시 + 오래된 임시 작업/복구 캐시를 대상으로 한다.
            # 최근 프로젝트/설정/개인정보와 실제 작업 폴더(workspaces)는 절대 자동 삭제하지 않는다.
            targets, total_size, summary = self.collect_auto_cache_cleanup_targets(older_than_days=max_age_days)
            temp_targets, temp_size, temp_summary = self.collect_temp_cleanup_targets(
                older_than_days=max_age_days,
                skip_current=True,
                exclude_recovery=False,
            )
            targets.extend(temp_targets)
            total_size += int(temp_size or 0)
            for key, info in (temp_summary or {}).items():
                if int((info or {}).get("count", 0) or 0) <= 0 and int((info or {}).get("size", 0) or 0) <= 0:
                    continue
                dst = summary.setdefault(key, {"label": (info or {}).get("label") or key, "count": 0, "size": 0})
                dst["label"] = (info or {}).get("label") or dst.get("label") or key
                dst["count"] += int((info or {}).get("count", 0) or 0)
                dst["size"] += int((info or {}).get("size", 0) or 0)

            deleted, failed = self.cleanup_delete_paths(targets)

            try:
                last_dir = str((self.app_options or {}).get("last_recovery_project_dir") or "")
                if last_dir and not os.path.exists(last_dir):
                    self.app_options.pop("last_recovery_project_dir", None)
            except Exception:
                pass

            self.app_options["last_temp_auto_cleanup_at"] = now_ts
            self.app_options["temp_auto_cleanup_enabled"] = True
            self.app_options["temp_auto_cleanup_days"] = period_days
            save_app_options(self.app_options)

            if deleted or failed:
                size_mb = total_size / (1024 * 1024)
                self.log(
                    f"🧹 Auto cache cleanup: deleted {deleted}, failed {failed}, approx. {size_mb:.1f} MB / period {period_days} days"
                    if getattr(self, "ui_language", LANG_KO) == LANG_EN else
                    f"🧹 자동 캐시 정리: 삭제 {deleted}개 / 실패 {failed}개 / 약 {size_mb:.1f} MB / 주기 {period_days}일"
                )
            else:
                self.log(
                    "🧹 Auto cache cleanup: no old cache files."
                    if getattr(self, "ui_language", LANG_KO) == LANG_EN else
                    "🧹 자동 캐시 정리: 오래된 캐시 없음"
                )
        except Exception as e:
            try:
                self.log(
                    f"⚠️ Auto temp cleanup failed: {e}"
                    if getattr(self, "ui_language", LANG_KO) == LANG_EN else
                    f"⚠️ 자동 임시 파일 정리 실패: {e}"
                )
                _save_ui_diag("MESSAGEBOX_DONE_CLOSED")
            except Exception as e:
                _save_ui_diag("MESSAGEBOX_DONE_EXCEPTION", error=repr(e))
                pass

    def delete_temp_files_now(self, parent=None):
        """현재 작업과 연결되지 않은 temp/work_sessions 임시 파일을 즉시 삭제한다."""
        targets, total_size, summary = self.collect_temp_cleanup_targets(
            older_than_days=None,
            skip_current=True,
            exclude_recovery=False,
        )

        if not targets:
            QMessageBox.information(
                parent or self,
                self.tr_ui("삭제할 임시 파일 없음"),
                self.tr_ui("삭제할 수 있는 임시 작업 파일이 없습니다."),
            )
            self.log("🧹 삭제할 임시 작업 파일 없음")
            return False

        msg = (
            f"{self.tr_ui('현재 열려 있는 작업을 제외한 임시 작업 폴더를 삭제합니다.')}\n\n"
            f"{self.temp_cleanup_summary_text(summary, len(targets), total_size)}\n\n"
            f"{self.tr_ui('삭제 후에는 해당 임시 작업을 복구할 수 없습니다. 계속할까요?')}"
        )
        ans = QMessageBox.question(
            parent or self,
            self.tr_ui("임시 파일 삭제"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            self.log("↩️ 임시 파일 삭제 취소")
            return False

        deleted = 0
        failed = 0
        for path in targets:
            try:
                shutil.rmtree(path, ignore_errors=False)
                deleted += 1
            except Exception:
                failed += 1

        # 삭제한 폴더가 마지막 복구 기록이면 기록도 비운다.
        try:
            last_dir = str((self.app_options or {}).get("last_recovery_project_dir") or "")
            if last_dir and not os.path.exists(last_dir):
                self.app_options.pop("last_recovery_project_dir", None)
                save_app_options(self.app_options)
        except Exception:
            pass

        self.log(f"🧹 임시 파일 삭제 완료: {deleted}개 삭제 / {failed}개 실패")
        QMessageBox.information(
            parent or self,
            self.tr_ui("임시 파일 삭제 완료"),
            self.tr_ui(f"임시 파일 삭제가 완료되었습니다.\n삭제: {deleted}개\n실패: {failed}개"),
        )
        return True

    def cleanup_entry_size(self, path):
        """삭제 후보 1개의 파일/폴더 수와 용량을 계산한다."""
        try:
            path = Path(path)
        except Exception:
            return 0, 0, 0
        if not path.exists():
            return 0, 0, 0
        file_count = 0
        dir_count = 0
        total_size = 0
        try:
            if path.is_file():
                return 1, 0, int(path.stat().st_size)
            if path.is_dir():
                dir_count += 1
                for child in path.rglob("*"):
                    try:
                        if child.is_file():
                            file_count += 1
                            total_size += int(child.stat().st_size)
                        elif child.is_dir():
                            dir_count += 1
                    except Exception:
                        pass
        except Exception:
            pass
        return file_count, dir_count, total_size

    def cleanup_open_folder(self, path):
        """사용자 데이터/캐시 폴더를 OS 파일 탐색기로 연다."""
        try:
            path = Path(path)
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            QMessageBox.warning(self, self.tr_ui("폴더 열기 실패"), f"{self.tr_ui('폴더를 열지 못했습니다.')}\n{path}\n\n{e}")

    def cleanup_delete_path(self, path):
        try:
            path = Path(path)
            if not path.exists():
                return True
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=False)
            else:
                path.unlink()
            return True
        except Exception:
            return False

    def collect_user_data_cleanup_entries(self):
        """사용자에게 보여줄 정리 항목을 대분류로만 만든다.

        내부 파일 종류를 그대로 노출하지 않는다.
        temp/work_sessions 임시 작업 캐시는 용량이 커질 수 있으므로 이 창에서 먼저 보여준다.
        실제 작업 폴더(workspaces)는 별도의 [작업 폴더 용량 관리] 창에서 확인 후 삭제한다.
        """
        entries = []
        try:
            app_root = Path(app_config_dir())
        except Exception:
            app_root = Path.home() / ".YSB_Translator"
        try:
            workspace_root = Path(get_workspace_root())
        except Exception:
            workspace_root = Path(getattr(self, "workspace_root", "") or default_workspace_root())
        cache_root = workspace_root / "cache"

        def temp_work_session_cleanup_paths():
            try:
                targets, _total_size, _summary = self.collect_temp_cleanup_targets(
                    older_than_days=None,
                    skip_current=True,
                    exclude_recovery=False,
                )
                return list(targets or [])
            except Exception:
                return []

        def existing_paths(paths):
            out = []
            for item in paths or []:
                try:
                    pp = Path(item)
                    if pp.exists():
                        out.append(pp)
                except Exception:
                    pass
            return out

        def entry_size(paths):
            file_count = 0
            dir_count = 0
            total_size = 0
            for pp in existing_paths(paths):
                fc, dc, sz = self.cleanup_entry_size(pp)
                file_count += fc
                dir_count += dc
                total_size += sz
            return file_count, dir_count, total_size

        def add_group(key, label, desc, paths, *, manual_only=False, sensitive=False, open_path=None):
            paths = existing_paths(paths)
            files, dirs, size = entry_size(paths)
            entries.append({
                "key": key,
                "label": self.tr_ui(label),
                "desc": self.tr_ui(desc),
                "paths": paths,
                "files": files,
                "dirs": dirs,
                "size": size,
                "manual_only": bool(manual_only),
                "sensitive": bool(sensitive),
                "open_path": Path(open_path) if open_path else None,
            })

        # 1. 임시 작업/복구 캐시: temp + cache/work_sessions. 실제로 용량을 가장 많이 먹을 수 있으므로 최상단에 보여준다.
        add_group(
            "temp_work_sessions",
            "임시 작업/복구 캐시 삭제",
            "자동 정리 대상이지만 용량이 클 수 있어 직접 삭제할 수도 있습니다. 현재 열려 있는 작업은 제외됩니다.",
            temp_work_session_cleanup_paths(),
            manual_only=False,
            open_path=app_root,
        )

        # 2. AppData 캐시: PC별 런처/로그/런타임 상태. 작업 폴더 위치 설정은 설정 정보로 분리한다.
        add_group(
            "appdata_cache",
            "AppData 캐시 삭제",
            "실행 로그, 런처 상태, 앱 실행 중 생긴 임시 데이터입니다.",
            [
                app_root / "runtime",
                app_root / "logs",
                app_root / "restart_logs",
                app_root / "ysb_launcher.log",
                app_root / "open_queue.jsonl",
                app_root / "launcher_launch_stats.json",
                app_root / "association_preflight.json",
            ],
            manual_only=False,
            open_path=app_root,
        )

        # 3. 최근 프로젝트 정보: 자동 삭제 금지. 사용자가 직접 누를 때만 삭제한다.
        add_group(
            "recent_projects",
            "최근 프로젝트 정보 삭제",
            "최근 열었던 프로젝트 목록과 홈 화면 썸네일 정보입니다. 프로젝트 파일 자체는 삭제하지 않습니다.",
            [
                cache_root / "recent_projects.json",
                cache_root / "recent_thumbnails",
            ],
            manual_only=True,
        )

        # 4. 설정 정보: 자동 삭제 금지. 초기화 성격이므로 수동 삭제 전용.
        add_group(
            "settings_info",
            "설정 정보 삭제",
            "언어, 테마, 단축키, 프리셋, 작업 폴더 위치 같은 사용자 설정입니다.",
            [
                app_root / "workspace_config.json",
                cache_root / "app_options.json",
                cache_root / "shortcut_cache.json",
                cache_root / "text_preset",
                cache_root / "item_text_preset",
                cache_root / "macro_settings.json",
            ],
            manual_only=True,
        )

        # 5. 개인정보: API 키. 자동 삭제 금지.
        add_group(
            "privacy_info",
            "개인정보 삭제",
            "API 키 같은 민감 정보입니다.",
            [
                cache_root / "api_cache.json",
            ],
            manual_only=True,
            sensitive=True,
        )

        return entries, app_root, workspace_root

    def collect_auto_cache_cleanup_targets(self, older_than_days=None):
        """자동 정리 대상 중 AppData 실행 캐시를 모은다.

        temp/work_sessions 임시 작업/복구 캐시는 auto_cleanup_temp_files_if_needed()에서
        별도로 collect_temp_cleanup_targets()를 통해 함께 정리한다.
        workspaces 아래의 실제 작업 폴더는 실사용 데이터이므로 자동 삭제 대상에 넣지 않는다.
        """
        entries, _app_root, _workspace_root = self.collect_user_data_cleanup_entries()
        auto_entries = [e for e in entries if e.get("key") in ("appdata_cache",)]
        now_ts = time.time()
        max_age_seconds = None
        if older_than_days is not None:
            try:
                max_age_seconds = max(0, int(older_than_days)) * 24 * 60 * 60
            except Exception:
                max_age_seconds = None

        targets = []
        total_size = 0
        summary = {}

        def add_target(path, group_key, label):
            nonlocal total_size
            try:
                pp = Path(path)
            except Exception:
                return
            if not pp.exists():
                return
            if max_age_seconds is not None:
                try:
                    ts = self.temp_path_created_timestamp(pp)
                    if ts and (now_ts - ts) < max_age_seconds:
                        return
                except Exception:
                    pass
            fc, dc, sz = self.cleanup_entry_size(pp)
            targets.append(pp)
            total_size += int(sz or 0)
            info = summary.setdefault(group_key, {"label": label, "count": 0, "size": 0})
            info["count"] += 1
            info["size"] += int(sz or 0)

        for e in auto_entries:
            label = e.get("label") or e.get("key")
            key = e.get("key") or label
            for pp in e.get("paths") or []:
                add_target(pp, key, label)
        return targets, total_size, summary

    def cleanup_delete_paths(self, paths):
        deleted = 0
        failed = 0
        for pp in paths or []:
            if self.cleanup_delete_path(pp):
                deleted += 1
            else:
                failed += 1
        try:
            changed_options = False
            last_dir = str((self.app_options or {}).get("last_recovery_project_dir") or "")
            if last_dir and not os.path.exists(last_dir):
                self.app_options.pop("last_recovery_project_dir", None)
                changed_options = True
            last_pending = str((self.app_options or {}).get("last_pending_clean_import_dir") or "")
            if last_pending and not os.path.exists(last_pending):
                self.app_options.pop("last_pending_clean_import_dir", None)
                changed_options = True
            if changed_options:
                save_app_options(self.app_options)
        except Exception:
            pass
        return deleted, failed


    def collect_workspace_folder_entries(self):
        """workspaces 아래의 실제 작업 폴더들을 날짜순으로 수집한다."""
        try:
            root = Path(workspaces_dir())
        except Exception:
            root = Path(get_workspace_root()) / "workspaces"
        entries = []
        current_project_dir = None
        current_work_dir = None
        try:
            current_project_dir = Path(str(getattr(self, "project_dir", "") or "")).resolve()
        except Exception:
            current_project_dir = None
        try:
            current_work_dir = Path(str(getattr(self, "work_project_dir", "") or "")).resolve()
        except Exception:
            current_work_dir = None

        if not root.exists():
            return entries, root
        try:
            children = [p for p in root.iterdir() if p.is_dir()]
        except Exception:
            children = []

        for folder in children:
            try:
                resolved = folder.resolve()
            except Exception:
                resolved = folder
            is_current = False
            for cur in (current_project_dir, current_work_dir):
                if cur is None:
                    continue
                try:
                    if resolved == cur or cur.is_relative_to(resolved) or resolved.is_relative_to(cur):
                        is_current = True
                        break
                except Exception:
                    try:
                        if os.path.abspath(str(resolved)) == os.path.abspath(str(cur)):
                            is_current = True
                            break
                    except Exception:
                        pass
            fc, dc, size = self.cleanup_entry_size(folder)
            try:
                mtime = folder.stat().st_mtime
            except Exception:
                mtime = 0
            project_json = folder / PROJECT_FILENAME
            status = "현재 열림" if is_current else ("프로젝트 폴더" if project_json.exists() else "작업 폴더")
            display_name = folder.name
            try:
                if project_json.exists():
                    with open(project_json, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    display_name = str(meta.get("project_name") or meta.get("name") or display_name)
            except Exception:
                pass
            entries.append({
                "path": folder,
                "name": display_name,
                "folder_name": folder.name,
                "mtime": mtime,
                "size": int(size or 0),
                "files": fc,
                "dirs": dc,
                "current": is_current,
                "status": status,
            })
        entries.sort(key=lambda e: (float(e.get("mtime") or 0), str(e.get("folder_name") or "")), reverse=True)
        return entries, root

    def open_workspace_folder_size_manager_dialog(self):
        """작업 폴더별 용량을 보고 사용자가 직접 삭제하는 관리창."""
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("작업 폴더 용량 관리"))
        dlg.setModal(True)
        dlg.resize(980, 660)
        try:
            dlg.setStyleSheet(self.settings_dialog_style())
        except Exception:
            pass

        root_layout = QVBoxLayout(dlg)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        title = QLabel(self.tr_ui("작업 폴더 용량 관리"), dlg)
        title.setObjectName("SettingsTitle")
        root_layout.addWidget(title)

        desc = QLabel(self.tr_ui("작업 폴더는 .ysbg 파일을 열어 작업할 때 생성되는 작업 공간입니다. 삭제해도 .ysbg 파일 자체는 삭제되지 않지만, 저장되지 않은 작업 내용은 사라질 수 있습니다. 현재 열려 있는 작업 폴더는 삭제할 수 없습니다."), dlg)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        root_layout.addWidget(desc)

        path_box = QFrame(dlg)
        path_box.setObjectName("SettingsBlock")
        path_layout = QHBoxLayout(path_box)
        path_layout.setContentsMargins(12, 10, 12, 10)
        path_layout.setSpacing(10)
        path_title = QLabel(self.tr_ui("작업 폴더 위치"), path_box)
        path_title.setObjectName("SettingsItemTitle")
        path_label = QLabel("", path_box)
        path_label.setObjectName("SettingsPath")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_label.setWordWrap(True)
        btn_open_root = QPushButton(self.tr_ui("전체 폴더 열기"), path_box)
        path_layout.addWidget(path_title)
        path_layout.addWidget(path_label, 1)
        path_layout.addWidget(btn_open_root)
        root_layout.addWidget(path_box)

        scroll = QScrollArea(dlg)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        rows_widget = QWidget(scroll)
        rows_layout = QVBoxLayout(rows_widget)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(8)
        scroll.setWidget(rows_widget)
        root_layout.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_rescan = QPushButton(self.tr_ui("다시 스캔"), dlg)
        total_label = QLabel("", dlg)
        total_label.setObjectName("SettingsDescription")
        btn_close = QPushButton(self.tr_ui("닫기"), dlg)
        btn_row.addWidget(btn_rescan)
        btn_row.addWidget(total_label, 1)
        btn_row.addWidget(btn_close)
        root_layout.addLayout(btn_row)

        state = {"root": None, "entries": []}

        def clear_layout(layout):
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                child_layout = item.layout()
                if w is not None:
                    w.deleteLater()
                elif child_layout is not None:
                    clear_layout(child_layout)

        def format_mtime(ts):
            try:
                if not ts:
                    return "-"
                return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
            except Exception:
                return "-"

        def delete_entry(entry):
            if not entry:
                return
            if entry.get("current"):
                QMessageBox.information(dlg, self.tr_ui("삭제할 수 없음"), self.tr_ui("현재 열려 있는 작업 폴더는 삭제할 수 없습니다."))
                return
            path = Path(entry.get("path"))
            msg = (
                f"{self.tr_ui('이 작업 폴더를 삭제합니다. 이 작업은 되돌릴 수 없습니다.')}\n\n"
                f"{entry.get('name') or path.name}\n"
                f"{path}\n"
                f"{self.tr_ui('용량')}: {self.format_size_mb(entry.get('size', 0))}\n\n"
                f"{self.tr_ui('계속할까요?')}"
            )
            ans = QMessageBox.question(
                dlg,
                self.tr_ui("작업 폴더 삭제 확인"),
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
            ok = self.cleanup_delete_path(path)
            if ok:
                self.log(f"🧹 작업 폴더 삭제: {path}")
            else:
                QMessageBox.warning(dlg, self.tr_ui("삭제 실패"), f"{self.tr_ui('작업 폴더를 삭제하지 못했습니다.')}\n{path}")
            refresh()

        def make_row(entry):
            row = QFrame(rows_widget)
            row.setObjectName("SettingsItem")
            lay = QHBoxLayout(row)
            lay.setContentsMargins(12, 10, 12, 10)
            lay.setSpacing(12)

            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)
            name = QLabel(str(entry.get("name") or entry.get("folder_name") or ""), row)
            name.setObjectName("SettingsItemTitle")
            detail = QLabel(
                f"{entry.get('folder_name') or ''}  ·  {self.tr_ui('수정')}: {format_mtime(entry.get('mtime'))}  ·  {entry.get('status') or ''}",
                row,
            )
            detail.setObjectName("SettingsDescription")
            detail.setWordWrap(True)
            text_box.addWidget(name)
            text_box.addWidget(detail)
            lay.addLayout(text_box, 1)

            size_label = QLabel(self.format_size_mb(entry.get("size", 0)), row)
            size_label.setMinimumWidth(100)
            size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(size_label)

            btn_open = QPushButton(self.tr_ui("폴더 열기"), row)
            btn_open.setMinimumWidth(88)
            btn_open.clicked.connect(lambda _=False, p=entry.get("path"): self.cleanup_open_folder(p))
            lay.addWidget(btn_open)

            btn_delete = QPushButton(self.tr_ui("삭제"), row)
            btn_delete.setMinimumWidth(88)
            btn_delete.setEnabled(not bool(entry.get("current")))
            btn_delete.clicked.connect(lambda _=False, e=entry: delete_entry(e))
            lay.addWidget(btn_delete)
            return row

        def refresh():
            entries, root = self.collect_workspace_folder_entries()
            state["entries"] = entries
            state["root"] = root
            path_label.setText(str(root))
            clear_layout(rows_layout)
            total = sum(int(e.get("size") or 0) for e in entries)
            total_label.setText(f"{self.tr_ui('총')} {len(entries)}{self.tr_ui('개')} / {self.tr_ui('용량')}: {self.format_size_mb(total)}")
            if not entries:
                empty = QLabel(self.tr_ui("표시할 작업 폴더가 없습니다."), rows_widget)
                empty.setObjectName("SettingsDescription")
                rows_layout.addWidget(empty)
            for entry in entries:
                rows_layout.addWidget(make_row(entry))
            rows_layout.addStretch(1)

        btn_open_root.clicked.connect(lambda: self.cleanup_open_folder(state.get("root") or workspaces_dir()))
        btn_rescan.clicked.connect(refresh)
        btn_close.clicked.connect(dlg.reject)
        refresh()
        dlg.exec()

    def cleanup_temp_files_dialog(self):
        """5개 대분류만 보여주는 사용자 데이터/임시파일 정리 창."""
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("사용자 데이터 및 임시파일 정리"))
        dlg.setModal(True)
        dlg.resize(860, 560)
        try:
            dlg.setStyleSheet(self.settings_dialog_style())
        except Exception:
            pass

        root = QVBoxLayout(dlg)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title = QLabel(self.tr_ui("사용자 데이터 및 임시파일 정리"), dlg)
        title.setObjectName("SettingsTitle")
        root.addWidget(title)

        desc = QLabel(self.tr_ui("임시 작업/복구 캐시는 자동 정리되지만 용량이 크게 커질 수 있어 최상단에 표시합니다. 현재 열려 있는 작업은 삭제 대상에서 제외됩니다. 실제 작업 폴더 용량은 별도의 작업 폴더 용량 관리에서 확인합니다."), dlg)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        root.addWidget(desc)

        path_box = QFrame(dlg)
        path_box.setObjectName("SettingsBlock")
        path_layout = QGridLayout(path_box)
        path_layout.setContentsMargins(12, 12, 12, 12)
        path_layout.setHorizontalSpacing(10)
        path_layout.setVerticalSpacing(8)
        app_path_label = QLabel("", path_box)
        app_path_label.setObjectName("SettingsPath")
        app_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        app_path_label.setWordWrap(True)
        btn_open_app = QPushButton(self.tr_ui("AppData 폴더 열기"), path_box)
        path_layout.addWidget(QLabel(self.tr_ui("AppData"), path_box), 0, 0)
        path_layout.addWidget(app_path_label, 0, 1)
        path_layout.addWidget(btn_open_app, 0, 2)
        root.addWidget(path_box)

        auto_box = QFrame(dlg)
        auto_box.setObjectName("SettingsItem")
        auto_layout = QHBoxLayout(auto_box)
        auto_layout.setContentsMargins(12, 10, 12, 10)
        auto_layout.setSpacing(10)
        auto_text = QVBoxLayout()
        auto_title = QLabel(self.tr_ui("오래된 캐시 자동 정리"), auto_box)
        auto_title.setObjectName("SettingsItemTitle")
        auto_desc = QLabel(self.tr_ui("자동 정리 대상은 AppData 실행 캐시와 오래된 임시 작업/복구 캐시입니다. 실제 작업 폴더는 사용자가 직접 확인하고 삭제합니다."), auto_box)
        auto_desc.setObjectName("SettingsDescription")
        auto_desc.setWordWrap(True)
        auto_text.addWidget(auto_title)
        auto_text.addWidget(auto_desc)
        cb_auto = QCheckBox(self.tr_ui("자동정리"), auto_box)
        combo_days = QComboBox(auto_box)
        current_days = self.get_temp_auto_cleanup_days()
        for days, label in self.temp_cleanup_period_options():
            combo_days.addItem(self.tr_ui(label), days)
            if days == current_days:
                combo_days.setCurrentIndex(combo_days.count() - 1)
        cb_auto.setChecked(self.is_temp_auto_cleanup_enabled())
        combo_days.setEnabled(cb_auto.isChecked())
        auto_layout.addLayout(auto_text, 1)
        auto_layout.addWidget(cb_auto)
        auto_layout.addWidget(combo_days)
        root.addWidget(auto_box)

        rows_area = QScrollArea(dlg)
        rows_area.setWidgetResizable(True)
        rows_area.setFrameShape(QFrame.Shape.NoFrame)
        rows_widget = QWidget(rows_area)
        rows_layout = QVBoxLayout(rows_widget)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(8)
        rows_area.setWidget(rows_widget)
        root.addWidget(rows_area, 1)

        btn_row = QHBoxLayout()
        btn_rescan = QPushButton(self.tr_ui("다시 스캔"), dlg)
        btn_close = QPushButton(self.tr_ui("닫기"), dlg)
        btn_row.addWidget(btn_rescan)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

        state = {"entries": [], "app_root": None, "workspace_root": None}

        def save_options():
            days = combo_days.currentData()
            self.set_temp_cleanup_options(cb_auto.isChecked(), days)
            combo_days.setEnabled(cb_auto.isChecked())
            self.log(f"🧹 캐시 자동 정리 설정: {'ON' if cb_auto.isChecked() else 'OFF'} / {int(days)}일")

        def confirm_and_delete(entry):
            if not entry or not entry.get("paths"):
                QMessageBox.information(dlg, self.tr_ui("삭제할 항목 없음"), self.tr_ui("삭제할 수 있는 항목이 없습니다."))
                return
            label = entry.get("label") or ""
            size = self.format_size_mb(entry.get("size", 0))
            warning = self.tr_ui("이 항목을 삭제합니다. 이 작업은 되돌릴 수 없습니다.")
            if entry.get("manual_only"):
                warning += "\n" + self.tr_ui("이 항목은 자동 정리 대상이 아니며, 사용자가 직접 누를 때만 삭제됩니다.")
            if entry.get("key") == "temp_work_sessions":
                warning += "\n" + self.tr_ui("현재 열려 있는 작업은 제외되지만, 다른 저장되지 않은 복구 작업은 사라질 수 있습니다.")
            if entry.get("sensitive"):
                warning += "\n" + self.tr_ui("삭제 후 API 키를 다시 설정해야 할 수 있습니다.")
            msg = f"{warning}\n\n{label}\n{self.tr_ui('용량')}: {size}\n\n{self.tr_ui('계속할까요?')}"
            ans = QMessageBox.question(
                dlg,
                self.tr_ui("삭제 확인"),
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                self.log(f"↩️ {label} 삭제 취소")
                return
            deleted, failed = self.cleanup_delete_paths(entry.get("paths") or [])
            self.log(f"🧹 {label}: 삭제 {deleted}개 / 실패 {failed}개")
            QMessageBox.information(
                dlg,
                self.tr_ui("삭제 완료"),
                f"{label}\n{self.tr_ui('삭제')}: {deleted}{self.tr_ui('개')}\n{self.tr_ui('실패')}: {failed}{self.tr_ui('개')}",
            )
            refresh_rows()

        def clear_layout(layout):
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                child_layout = item.layout()
                if w is not None:
                    w.deleteLater()
                elif child_layout is not None:
                    clear_layout(child_layout)

        def make_row(entry):
            row = QFrame(rows_widget)
            row.setObjectName("SettingsItem")
            lay = QHBoxLayout(row)
            lay.setContentsMargins(12, 10, 12, 10)
            lay.setSpacing(12)

            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)
            name = QLabel(str(entry.get("label") or ""), row)
            name.setObjectName("SettingsItemTitle")
            desc_label = QLabel(str(entry.get("desc") or ""), row)
            desc_label.setObjectName("SettingsDescription")
            desc_label.setWordWrap(True)
            text_box.addWidget(name)
            text_box.addWidget(desc_label)
            lay.addLayout(text_box, 1)

            size_label = QLabel(self.format_size_mb(entry.get("size", 0)), row)
            size_label.setMinimumWidth(90)
            size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(size_label)

            open_path = entry.get("open_path")
            if open_path:
                btn_open = QPushButton(self.tr_ui("폴더 열기"), row)
                btn_open.setMinimumWidth(88)
                btn_open.clicked.connect(lambda _=False, p=open_path: self.cleanup_open_folder(p))
                lay.addWidget(btn_open)
            else:
                spacer = QWidget(row)
                spacer.setFixedWidth(88)
                lay.addWidget(spacer)

            btn_delete = QPushButton(self.tr_ui("삭제"), row)
            btn_delete.setMinimumWidth(88)
            btn_delete.setEnabled(bool(entry.get("paths")))
            btn_delete.clicked.connect(lambda _=False, e=entry: confirm_and_delete(e))
            lay.addWidget(btn_delete)
            return row

        def refresh_rows():
            entries, app_root, workspace_root = self.collect_user_data_cleanup_entries()
            state["entries"] = entries
            state["app_root"] = app_root
            state["workspace_root"] = workspace_root
            app_path_label.setText(str(app_root))
            clear_layout(rows_layout)
            for entry in entries:
                rows_layout.addWidget(make_row(entry))
            rows_layout.addStretch(1)

        cb_auto.toggled.connect(lambda _checked: save_options())
        combo_days.currentIndexChanged.connect(lambda _idx: save_options())
        btn_rescan.clicked.connect(refresh_rows)
        btn_close.clicked.connect(dlg.reject)
        btn_open_app.clicked.connect(lambda: self.cleanup_open_folder(state.get("app_root") or app_config_dir()))

        refresh_rows()
        dlg.exec()

    def _schedule_project_open_view_refresh(self, *, reason="project_open"):
        """Force a light post-open redraw after the editor widget is laid out.

        When a different project is opened after closing the previous one, Qt can
        finish tab/widget layout after the first load() call.  In that narrow case
        the table exists but the left maker preview remains blank until another
        mode switch/DB toggle emits a refresh.  Schedule a few safe redraw passes
        without changing data.
        """
        try:
            refresh_token = int(getattr(self, "_maker_preview_lifecycle_token", 0) or 0)
        except Exception:
            refresh_token = None
        force_load_done = {"done": False}

        def _refresh_once():
            try:
                try:
                    if refresh_token is not None and int(refresh_token) != int(getattr(self, "_maker_preview_lifecycle_token", 0) or 0):
                        return
                except Exception:
                    pass
                if getattr(self, "is_loading_project", False):
                    QTimer.singleShot(80, _refresh_once)
                    return
                if not getattr(self, "paths", None):
                    return
                try:
                    self.maker_database_mode_enabled = False
                    try:
                        self.set_maker_database_preview_visible(False)
                    except Exception:
                        try:
                            panel = getattr(self, "maker_database_preview_panel", None)
                            if panel is not None:
                                panel.hide()
                            split = getattr(self, "source_compare_splitter", None)
                            if split is not None:
                                split.show()
                                split.setVisible(True)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    paths = list(getattr(self, "paths", []) or [])
                    if int(getattr(self, "idx", 0) or 0) < 0:
                        self.idx = 0
                    if int(getattr(self, "idx", 0) or 0) >= len(paths):
                        self.idx = max(0, len(paths) - 1)
                    # If a saved/restored index points at a DB virtual page while
                    # normal mode is active, the left preview can remain blank
                    # until DB mode rebuilds the tabbar.  Move to the first real
                    # map page before the first post-open render.
                    try:
                        curr_page = self._page_data_for_index_safe(int(self.idx)) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(int(self.idx), {})
                        if self._maker_page_is_database_page(curr_page):
                            for pi in range(len(paths)):
                                pg = self._page_data_for_index_safe(pi) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(pi, {})
                                if not self._maker_page_is_database_page(pg):
                                    self.idx = pi
                                    break
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    current_mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else int(getattr(self, "last_mode", 0) or 0)
                except Exception:
                    current_mode = 0
                try:
                    self.ensure_page_runtime_loaded(
                        int(getattr(self, "idx", 0) or 0),
                        include_ori=True,
                        include_heavy=bool(current_mode == 4),
                        include_masks=False,
                    )
                except Exception:
                    pass
                # A plain ref_tab/mode_chg is not enough on every close->open
                # path because the graphics scene may have been cleared by
                # clear_current_project_runtime_state().  Run one real load() after
                # layout is visible, then use light redraws for the later timers.
                if not force_load_done["done"]:
                    force_load_done["done"] = True
                    try:
                        self.load()
                    except Exception:
                        pass
                try:
                    self.ref_tab()
                except Exception:
                    pass
                try:
                    self.mode_chg(current_mode)
                except Exception:
                    pass
                try:
                    if hasattr(self, "update_maker_preview_selection_from_table"):
                        self.update_maker_preview_selection_from_table()
                except Exception:
                    pass
                try:
                    if hasattr(self, "_force_maker_preview_rebuild_for_current_project"):
                        self._force_maker_preview_rebuild_for_current_project(reason=str(reason or "project_open_refresh"), token=refresh_token)
                except Exception:
                    pass
                try:
                    if hasattr(self, "view") and self.view is not None and self.view.viewport() is not None:
                        self.view.viewport().update()
                except Exception:
                    pass
                try:
                    self.audit_boundary_event("PROJECT_OPEN_VIEW_REFRESH", reason=str(reason or "project_open"), page_idx=getattr(self, "idx", None), mode=current_mode, token=refresh_token)
                except Exception:
                    pass
            except Exception:
                pass
        try:
            QTimer.singleShot(0, _refresh_once)
            QTimer.singleShot(120, _refresh_once)
            QTimer.singleShot(360, _refresh_once)
        except Exception:
            pass

    def open_project_path(self, path, external_request=False, skip_guard=False):
        """파일 연결/명령행 인자로 받은 .ysbg 또는 project.json을 연다.

        project.json 직접 열기는 .ysbg 압축 해제와 달리 이미 존재하는 작업 폴더를
        그대로 여는 흐름이다.  최근 프로젝트 경계 하드 리셋 이후, 기존 프로젝트를
        먼저 닫아 버린 뒤에야 선택 파일을 검증하면 잘못된 JSON 선택/로드 실패 시
        현재 작업만 닫히고 새 프로젝트는 열리지 않는 상태가 될 수 있다.
        그래서 project.json은 먼저 경로를 확정/검증하고, 그 다음에 이전 세션을
        정리한 뒤, 같은 호출 흐름 안에서 load_project_json()을 확정 실행한다.
        """
        if not path:
            return False
        guard_reason = "open_project_json"
        try:
            ext = os.path.splitext(str(path))[1].lower()
            if ext == str(YSB_EXTENSION).lower():
                guard_reason = "open_project_ysbt"
        except Exception:
            pass
        if not skip_guard:
            self._file_dialog_log("FILE_DIALOG_GUARD_ENTER", reason=guard_reason)
            if not self.guard_project_action("프로젝트 열기"):
                self._file_dialog_log("FILE_DIALOG_GUARD_BLOCKED", reason=guard_reason)
                return False
            self._file_dialog_log("FILE_DIALOG_GUARD_DONE", reason=guard_reason)
        path = os.path.abspath(str(path))

        if path.lower().endswith(str(YSB_EXTENSION).lower()):
            return self.open_ysbt_from_home(path, external_request=external_request)

        if os.path.isdir(path):
            project_file = os.path.join(path, PROJECT_FILENAME)
        else:
            project_file = path
        project_file = os.path.abspath(str(project_file))

        # 현재 프로젝트를 닫기 전에 먼저 선택 파일을 검증한다.
        if os.path.basename(project_file) != PROJECT_FILENAME or not os.path.exists(project_file):
            msg_text = self.tr_ui("열 수 있는 프로젝트 파일이 아닙니다.")
            QMessageBox.warning(self, self.tr_ui("프로젝트 없음"), f"{msg_text}\n{path}")
            return False

        had_open_project = bool(self.has_open_project())
        try:
            current_project_file = ""
            if getattr(self, "project_dir", None):
                current_project_file = os.path.abspath(os.path.join(str(self.project_dir), PROJECT_FILENAME))
            same_project = bool(current_project_file and current_project_file.lower() == project_file.lower())
        except Exception:
            same_project = False

        if had_open_project:
            if (not external_request) or bool(getattr(self, "has_unsaved_changes", False)):
                if not self.confirm_unsaved_before_switch():
                    return False
            # project.json으로 다른 프로젝트를 바로 열 때도 이전 화면/테이블/탭을 먼저 닫는다.
            # 단, 같은 project.json 재열기에서는 불필요한 세션 파괴를 피한다.
            if not same_project:
                try:
                    self.clear_current_project_runtime_state()
                    self._show_launcher_screen_only()
                    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                except Exception:
                    pass
        else:
            # 런처 화면에는 열린 프로젝트가 없으므로 남은 dirty 플래그/타이머는 이전 세션 찌꺼기다.
            try:
                self.clear_pending_work_cache_save_state("open_project_without_project")
            except Exception:
                pass
            self.has_unsaved_changes = False

        try:
            self.load_project_json(project_file)
            if external_request:
                self.force_app_focus(reason="external project open")
            return True
        except Exception as e:
            try:
                self.audit_boundary_event("PROJECT_JSON_OPEN_FAILED", path=str(project_file), error=str(e))
            except Exception:
                pass
            try:
                self._show_launcher_screen_only()
            except Exception:
                pass
            QMessageBox.critical(
                self,
                self.tr_ui("프로젝트 열기 실패"),
                f"{self.tr_ui('project.json 프로젝트를 열지 못했습니다.')}\n{project_file}\n\n{e}",
            )
            return False

    def open_ysbt_from_home(self, path, external_request=False):
        """YSBG 열기는 항상 홈화면 위에서 진행창을 띄운 뒤 시작한다."""
        path = os.path.abspath(str(path))
        if not os.path.exists(path):
            QMessageBox.warning(self, self.tr_ui("파일을 찾을 수 없음"), f"{self.tr_ui('파일을 찾을 수 없습니다.')}\n{path}")
            return False

        if self.has_open_project():
            if not external_request:
                if not self.confirm_unsaved_before_switch():
                    return False
            elif getattr(self, "has_unsaved_changes", False):
                # 외부 열기 루트는 보통 handle_single_instance_payload()에서 이미 확인을 거치지만,
                # 직접 호출되는 예외 상황을 방어한다.
                if not self.confirm_unsaved_before_switch():
                    return False
            self.clear_current_project_runtime_state()
        else:
            try:
                self.clear_pending_work_cache_save_state("open_ysbt_from_home_without_project")
            except Exception:
                pass
            self.has_unsaved_changes = False

        try:
            self._show_launcher_screen_only()
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        except Exception:
            pass

        def _start_open():
            try:
                self.open_ysb_package(path)
                if external_request:
                    self.force_app_focus(reason="external project open")
            except Exception as e:
                QMessageBox.critical(self, self.tr_ui("YSBG 열기 실패"), f"{self.tr_ui('YSBG 프로젝트를 열지 못했습니다.')}\n{path}\n\n{e}")

        # 홈화면 전환/갱신은 즉시 반영하되, 실제 YSBG 열기 본체는 같은 호출 흐름에서 확정 실행한다.
        # 프로젝트 경계 하드 리셋 이후 QTimer 지연 콜백에 맡기면 열기 요청이 묻히거나
        # 이전 세션 정리 타이밍과 엇갈릴 수 있다.
        try:
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        except Exception:
            pass
        _start_open()
        return True

    def load_project_json(self, project_file, package_path=None, temp_project=False):
        self.is_loading_project = True
        try:
            if hasattr(self, "_maker_preview_new_lifecycle_token"):
                self._maker_preview_new_lifecycle_token("project_open")
        except Exception:
            pass
        try:
            if hasattr(self, "_clear_maker_preview_display_state"):
                self._clear_maker_preview_display_state(reason="project_open_prepare")
        except Exception:
            pass
        load_progress = getattr(self, "_project_load_progress_callback", None)
        project_file = os.path.abspath(str(project_file))
        progress_overlay_owned = False
        progress_busy_owned = False

        if not callable(load_progress):
            try:
                overlay = getattr(self, "_task_progress_overlay", None)
                overlay_visible = bool(overlay is not None and overlay.isVisible())
            except Exception:
                overlay_visible = False
            try:
                project_label = os.path.basename(os.path.dirname(project_file)) or os.path.basename(str(project_file))
            except Exception:
                project_label = os.path.basename(str(project_file))

            if not overlay_visible:
                try:
                    self.begin_busy_state("프로젝트 열기")
                    progress_busy_owned = True
                except Exception:
                    progress_busy_owned = False
                try:
                    self.show_task_progress_overlay(
                        "프로젝트 열기",
                        f"프로젝트: {project_label}\n프로젝트 열기 준비 중...",
                        total=100,
                        cancellable=False,
                    )
                    progress_overlay_owned = True
                except Exception:
                    progress_overlay_owned = False

            def _default_load_progress(current=0, total=100, detail="프로젝트 로딩 중..."):
                try:
                    show_total = max(1, int(total or 100))
                    show_current = max(0, min(show_total, int(current or 0)))
                    formatted = (
                        f"프로젝트: {project_label}\n"
                        f"{str(detail or '')}"
                    )
                    self.update_task_progress_overlay(current=show_current, total=show_total, detail=formatted)
                    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                except Exception:
                    pass

            load_progress = _default_load_progress

        def _emit_load_progress(current, total, detail):
            if callable(load_progress):
                try:
                    load_progress(current, total, detail)
                except Exception:
                    pass

        def _store_load_progress(current=None, total=None, detail=None):
            try:
                show_total = max(1, int(total or 1))
                show_current = max(0, min(show_total, int(current or 0)))
                mapped = 22
                if show_total > 0:
                    mapped = 22 + int((show_current / show_total) * 12)
                mapped = max(22, min(34, mapped))
                _emit_load_progress(mapped, 100, str(detail or "프로젝트 페이지 메타데이터를 순차 로딩하는 중..."))
            except Exception:
                _emit_load_progress(24, 100, str(detail or "프로젝트 페이지 메타데이터를 순차 로딩하는 중..."))

        try:
            _emit_load_progress(12, 100, "현재 화면 상태를 정리하는 중...")
            self.commit_current_page_ui_to_data()
            _emit_load_progress(22, 100, "프로젝트 데이터를 읽는 중...")
            self.project_store = ProjectStore()
            # 프로젝트 재열기는 모든 페이지 이미지를 즉시 읽지 않는다.
            # project.json의 페이지 메타데이터만 순차로 훑고, 실제 이미지/마스크/클린본은
            # 현재 페이지를 열 때 ensure_page_runtime_loaded()가 필요분만 로딩한다.
            self.paths, self.data, self.idx = self.project_store.load(project_file, lazy_assets=True, progress_callback=_store_load_progress)
            _emit_load_progress(35, 100, "Undo/화면 상태를 초기화하는 중...")
            self.undo_clear_all_pages("project load")
            self.undo_clear_project("project stack reset")
            self.undo_boundary = None
            self.update_undo_redo_buttons()
            ui_state = getattr(self.project_store, "ui_state", {}) or {}
            self.project_ui_view_states = copy.deepcopy(ui_state.get("view_states") or {})
            self.restore_project_ui_state(ui_state, refresh=False)
            self.project_dir = self.project_store.project_dir
            try:
                uuid_value = ""
                try:
                    uuid_value = str(self.project_store.project_uuid() or "").strip()
                except Exception:
                    uuid_value = ""
                if uuid_value:
                    self._project_runtime_cache_scope = f"uuid:{uuid_value}"
                else:
                    base = os.path.abspath(str(self.project_dir or project_file or ""))
                    self._project_runtime_cache_scope = "path:" + hashlib.sha1(base.encode("utf-8", "ignore")).hexdigest()[:16]
                self._maker_active_preview_project_scope = self._project_runtime_cache_scope
                try:
                    self.audit_boundary_event("PROJECT_CACHE_SCOPE_SET", scope=self._project_runtime_cache_scope, project_dir=str(self.project_dir or ""))
                except Exception:
                    pass
            except Exception:
                self._project_runtime_cache_scope = ""
            try:
                # DB 페이지는 build_maker_pages/create_from_maker_game가 이미 self.paths/self.data에
                # page_type=database 가상 페이지로 만들어 둔다. 여기서 별도 레이어로 빼지 않는다.
                # 일반 모드/DB 모드 전환은 탭 표시 필터만 바꾸는 방식으로 처리한다.
                # 프로젝트를 새로 열 때는 저장된 작업 탭이 4(최종결과)여도 DB 모드가 아니다.
                # 이전 프로젝트에서 DB 프리뷰 패널이 켜져 있었던 상태를 무조건 끊고
                # 왼쪽을 일반 맵 프리뷰 위젯으로 돌린다.
                self.maker_database_mode_enabled = False
                try:
                    self.set_maker_database_preview_visible(False)
                except Exception:
                    try:
                        panel = getattr(self, "maker_database_preview_panel", None)
                        if panel is not None:
                            panel.hide()
                        split = getattr(self, "source_compare_splitter", None)
                        if split is not None:
                            split.show()
                            split.setVisible(True)
                    except Exception:
                        pass
            except Exception:
                pass
            self.ysbg_package_path = package_path
            self.suggested_project_name = self.split_uuid_suffix_from_name(Path(package_path).stem)[0] if package_path else None
            self.is_temp_project = bool(temp_project)
            self.update_window_title()
            self.mark_saved_state()
            self.log(f"📂 프로젝트 열림: {self.project_dir}")
            if package_path:
                self.log(f"📦 연결된 YSBG 파일: {package_path}")

            # 쯔꾸르붕이: project.json을 열 때마다 작업 폴더 안의 maker_game을 다시 확인해
            # System.json/fonts/Window.png/MV·MZ 런타임 값을 maker_runtime_profile 캐시로 재구성한다.
            # .ysbg는 운반용 패키지이고 평소 작업 본체는 폴더/project.json이므로,
            # 프로젝트 열기 시점에 표시 환경 캐시를 맞춰 두는 것이 가장 안전하다.
            try:
                if hasattr(self, "refresh_maker_display_environment"):
                    refreshed = self.refresh_maker_display_environment(reason="project_open", refresh_view=False, silent=True)
                    if refreshed:
                        _emit_load_progress(42, 100, "쯔꾸르 표시 환경을 읽는 중...")
            except Exception as e:
                try:
                    self.log(f"⚠️ 쯔꾸르 표시 환경 자동 갱신 실패: {e}")
                except Exception:
                    pass

            # 새 프로젝트/복구 프로젝트는 원본 탭으로 시작한다.
            # 특히 복구 직후 mode 4(최종결과)를 바로 복원하면 대량 클린본/이미지 상태에서 첫 렌더가 매우 무거워질 수 있다.
            if temp_project or bool(getattr(self, "_loading_recovery_project", False)):
                mode_to_load = 0
            else:
                mode_to_load = int(ui_state.get("current_mode", 0) or 0)
            _emit_load_progress(45, 100, "첫 페이지 화면을 구성하는 중...\n이미지가 많은 프로젝트는 이 단계에서 시간이 걸릴 수 있습니다.")
            self.set_work_mode_without_undo(mode_to_load)
            self.show_editor()
            self.load()
            try:
                if hasattr(self, "_force_maker_preview_rebuild_for_current_project"):
                    self._force_maker_preview_rebuild_for_current_project(reason="project_open_initial")
            except Exception:
                pass
            try:
                self.schedule_progressive_page_load(self.idx)
            except Exception:
                pass
            _emit_load_progress(75, 100, "첫 페이지 화면 구성 완료")
            self.record_current_project_recent()
            state = self.project_ui_view_states.get(self.view_state_key(self.idx, mode_to_load))
            if state:
                self.apply_view_state(state)
                QTimer.singleShot(0, lambda st=copy.deepcopy(state): self.apply_view_state(st))
                QTimer.singleShot(30, lambda st=copy.deepcopy(state): self.apply_view_state(st))
                QTimer.singleShot(80, lambda st=copy.deepcopy(state): self.apply_view_state(st))

            pending_clean_restored = 0
            try:
                pending_clean_restored = self.apply_pending_clean_import_if_available(self.project_dir)
            except Exception as e:
                pending_clean_restored = 0
                try:
                    self.log(f"⚠️ 클린본 pending 복구 실패: {e}")
                except Exception:
                    pass

            # 열기 직후에는 작업 캐시 full snapshot을 만들지 않는다.
            # YSBG를 풀어 둔 project_dir 자체를 현재 작업 기준 폴더로 사용하고,
            # 실제 변경이 생긴 페이지부터 save_pages_delta()로만 반영한다.
            try:
                self.work_project_dir = self.project_dir
                self.work_project_store = self.project_store
                if pending_clean_restored:
                    self.record_recovery_project_dir(self.project_dir)
                    self.has_unsaved_changes = True
            except Exception:
                pass
            try:
                self._schedule_project_open_view_refresh(reason="project_json_loaded")
            except Exception:
                pass
            _emit_load_progress(100, 100, "프로젝트 로드 완료")
        finally:
            self.is_loading_project = False
            try:
                if progress_overlay_owned:
                    self.hide_task_progress_overlay()
            except Exception:
                pass
            try:
                if progress_busy_owned:
                    self.end_busy_state()
            except Exception:
                pass

    def open_ysb_package(self, package_path):
        self._long_task_cancel_requested = False
        self._active_long_task_kind = "open_extract"
        shown_overlay = False

        def _open_progress(current=None, total=None, detail=None):
            try:
                show_total = int(total or 0)
                show_current = int(current or 0)
                raw_detail = str(detail or "압축 해제 중...")
                file_name = os.path.basename(str(package_path))
                formatted = (
                    f"{self.tr_ui('파일')}: {file_name}\n"
                    f"{raw_detail}"
                )
                self.update_task_progress_overlay(current=show_current, total=show_total, detail=formatted)
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            except Exception:
                pass

        def _open_cancel_requested():
            return bool(getattr(self, "_long_task_cancel_requested", False))

        try:
            self.begin_busy_state("YSBG 열기")
            self.show_task_progress_overlay(
                "YSBG 열기",
                f"{self.tr_ui('파일')}: {os.path.basename(str(package_path))}\n압축 해제 준비 중...",
                total=0,
                cancellable=True,
            )
            shown_overlay = True
            try:
                overlay = getattr(self, "_task_progress_overlay", None)
                if overlay is not None:
                    overlay.note_label.setText("취소 시 압축 해제를 중단하고 부분 작업 폴더를 삭제합니다.")
                    overlay.cancel_btn.setVisible(True)
                    overlay.cancel_btn.setEnabled(True)
            except Exception:
                pass
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

            # .ysbg는 항상 본체다.
            # 기존 workspaces 해제본은 옛 작업 공간이므로 재사용하지 않고,
            # 같은 이름/uuid 작업 폴더를 비운 뒤 현재 .ysbg를 다시 압축 해제해서 연다.
            target_dir, manifest, reused = extract_ysb_package(
                package_path,
                workspaces_dir(),
                reuse_existing=False,
                progress_callback=_open_progress,
                cancel_checker=_open_cancel_requested,
            )

            self.update_task_progress_overlay(
                current=1,
                total=1,
                detail=f"{self.tr_ui('파일')}: {os.path.basename(str(package_path))}\n프로젝트 데이터를 불러오는 중..."
            )
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            self.load_project_json(os.path.join(target_dir, PROJECT_FILENAME), package_path=package_path, temp_project=False)
        except PackageProjectCancelled:
            try:
                self.log("⏹️ YSBG 열기 취소됨")
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, self.tr_ui("YSBG 열기 실패"), f"{self.tr_ui('YSBG 프로젝트를 열지 못했습니다.')}\n{package_path}\n\n{e}")
        finally:
            try:
                self._active_long_task_kind = ""
            except Exception:
                pass
            try:
                self._long_task_cancel_requested = False
            except Exception:
                pass
            try:
                if shown_overlay:
                    self.hide_task_progress_overlay()
            except Exception:
                pass
            try:
                self.end_busy_state()
            except Exception:
                pass

    def project_cache_root(self):
        root = get_cache_dir() / "work_sessions"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def clear_pending_work_cache_save_state(self, reason=""):
        """저장/닫기/프로젝트 전환 뒤에 남은 지연 커밋 예약을 정리한다.

        v2.4 QA20:
        복구용 작업 캐시 저장 QTimer는 제거되었다. 여기서는 최종 페인트/마스크
        뷰 레이어 지연 커밋만 끊어, 화면 전환 뒤 이전 프로젝트의 예약 작업이
        새 프로젝트 상태를 건드리지 못하게 한다.
        """
        for attr in ("_deferred_view_layer_commit_timer", "_deferred_work_cache_save_timer"):
            try:
                timer = getattr(self, attr, None)
                if timer is not None:
                    timer.stop()
            except Exception:
                pass
        try:
            self._pending_view_layer_commit_kinds = set()
        except Exception:
            pass

    def forget_recovery_project_dir(self, project_dir=None):
        """내보내기 완료 등으로 복구 후보가 더 필요 없을 때 마지막 복구 기록만 지운다."""
        try:
            target = os.path.abspath(str(project_dir or getattr(self, "work_project_dir", "") or ""))
            if not target:
                return
            changed = False
            last_dir = str((self.app_options or {}).get("last_recovery_project_dir") or "")
            try:
                if last_dir and os.path.abspath(last_dir).lower() == target.lower():
                    self.app_options.pop("last_recovery_project_dir", None)
                    changed = True
            except Exception:
                pass
            last_pending = str((self.app_options or {}).get("last_pending_clean_import_dir") or "")
            try:
                if last_pending and os.path.abspath(last_pending).lower().startswith(target.lower()):
                    self.app_options.pop("last_pending_clean_import_dir", None)
                    changed = True
            except Exception:
                pass
            try:
                self.mark_workspace_state_saved(target)
            except Exception:
                pass
            # 구버전 work_sessions recovery_marker 파일은 best-effort로 정리한다.
            try:
                marker = self.project_cache_root() / f"recovery_marker_{Path(target).name}_{uuid.uuid5(uuid.NAMESPACE_URL, target).hex[:12]}.json"
                if marker.exists():
                    marker.unlink()
            except Exception:
                pass
            if changed:
                save_app_options(self.app_options)
        except Exception:
            pass

    def cleanup_work_cache(self):
        try:
            self.clear_pending_work_cache_save_state("cleanup_work_cache")
        except Exception:
            pass
        old_cache = self.work_project_dir
        try:
            self.forget_recovery_project_dir(old_cache)
        except Exception:
            pass
        if old_cache and os.path.exists(old_cache):
            try:
                old_abs = os.path.abspath(str(old_cache))
                project_abs = os.path.abspath(str(getattr(self, "project_dir", "") or ""))
                if old_abs == project_abs or self.is_workspace_project_dir_path(old_abs):
                    # workspaces는 실제 작업 공간이자 복구 기준이므로 자동 삭제하지 않는다.
                    try:
                        self.log(f"🧷 작업 폴더 자동 삭제 생략: {old_cache}")
                    except Exception:
                        pass
                else:
                    shutil.rmtree(old_cache, ignore_errors=True)
            except Exception:
                pass
        self.work_project_dir = None
        self.work_project_store = None
        self.page_tab_scroll_generation = 0

    def make_work_cache_dir(self):
        if self.project_dir:
            base = Path(self.project_dir).name
        else:
            base = "unsaved_project"
        safe_base = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in base)
        return str(self.project_cache_root() / f"{safe_base}_{uuid.uuid4().hex[:10]}")

    def start_work_cache_from_current(self, mark_dirty=False):
        """현재 메모리 상태를 기준으로 새 작업 캐시를 만든다."""
        if not self.project_dir:
            return
        old_cache = self.work_project_dir
        cache_dir = self.make_work_cache_dir()

        store = ProjectStore(cache_dir)
        old_suppress = bool(getattr(self, "_suppress_work_cache_dirty", False))
        self._suppress_work_cache_dirty = True
        try:
            self.save_project_store(store, force_full=True)
        finally:
            self._suppress_work_cache_dirty = old_suppress

        # store.save()가 paths를 cache 내부 이미지 경로로 고정할 수 있으므로 이후 작업은 캐시 기준으로 돌아간다.
        self.work_project_store = store
        self.work_project_dir = cache_dir
        self.record_recovery_project_dir(cache_dir)
        self.has_unsaved_changes = bool(mark_dirty)

        if old_cache and old_cache != cache_dir and os.path.exists(old_cache):
            try:
                if self.is_workspace_project_dir_path(old_cache):
                    self.log(f"🧷 기존 workspaces 작업 폴더 자동 삭제 생략: {old_cache}")
                else:
                    shutil.rmtree(old_cache, ignore_errors=True)
            except Exception:
                pass

        self.log(f"🧪 작업 캐시 시작: {cache_dir}")

    def flush_workspace_image_pages(self, page_indices, *, reason="image_heavy", release_non_current=True):
        """이미지-heavy 페이지를 즉시 workspace delta로 저장한다.

        인페인팅/클린본/배경 교체처럼 큰 이미지 payload가 생기는 작업은
        page journal이 아니라 save_pages_delta()로 바로 파일 flush 해야 한다.
        일괄 작업에서는 페이지 하나를 저장한 뒤 메모리 payload를 끊어 다음
        페이지로 넘어가도록 이 helper를 쓴다.
        """
        if (
            getattr(self, "_suppress_work_cache_dirty", False)
            or getattr(self, "is_loading_project", False)
            or not getattr(self, "project_dir", None)
            or not getattr(self, "paths", None)
        ):
            return False
        indices = []
        seen = set()
        for raw in list(page_indices or []):
            try:
                i = int(raw)
            except Exception:
                continue
            if 0 <= i < len(getattr(self, 'paths', []) or []) and i not in seen:
                indices.append(i)
                seen.add(i)
        if not indices:
            return False
        if self.work_project_store is None or not self.work_project_dir:
            self.work_project_store = getattr(self, 'project_store', None)
            self.work_project_dir = getattr(self, 'project_dir', None)
        if self.work_project_store is None or not self.work_project_dir:
            return False
        try:
            self.work_project_store.ui_state = self.current_project_ui_state()
        except Exception:
            self.work_project_store.ui_state = getattr(self.work_project_store, 'ui_state', {}) or {}
        self.work_project_store.clean_image_format = self.current_clean_image_format() if hasattr(self, 'current_clean_image_format') else getattr(self, 'clean_image_format', 'png')
        self.work_project_store.clean_image_quality = self.current_clean_image_quality() if hasattr(self, 'current_clean_image_quality') else getattr(self, 'clean_image_quality', 95)
        try:
            self.audit_boundary_event(
                'WORK_CACHE_IMAGE_DELTA_SAVE_ENTER',
                dirty_pages=sorted(int(x) for x in indices),
                reason=str(reason or 'image_heavy'),
                stack=True,
            )
        except Exception:
            pass
        self.work_project_store.save_pages_delta(self.paths, self.data, set(indices), current_index=getattr(self, 'idx', 0))
        try:
            self.record_recovery_project_dir(self.work_project_dir)
        except Exception:
            pass
        try:
            self.audit_boundary_event(
                'WORK_CACHE_IMAGE_DELTA_SAVE_DONE',
                dirty_pages=sorted(int(x) for x in indices),
                reason=str(reason or 'image_heavy'),
            )
        except Exception:
            pass
        if release_non_current:
            try:
                current_idx = int(getattr(self, 'idx', -1) or -1)
            except Exception:
                current_idx = -1
            for i in indices:
                if i == current_idx:
                    continue
                try:
                    curr = (getattr(self, 'data', {}) or {}).get(int(i))
                    if not isinstance(curr, dict):
                        continue
                    if curr.get('clean_path'):
                        curr['bg_clean'] = None
                    if curr.get('working_source_path'):
                        curr['working_source'] = None
                    if curr.get('final_paint_path'):
                        curr['final_paint'] = None
                    if curr.get('final_paint_above_path'):
                        curr['final_paint_above'] = None
                    curr['ori'] = None
                except Exception:
                    pass
            try:
                if hasattr(self, 'trim_page_image_cache'):
                    keep = [current_idx] if current_idx >= 0 else []
                    self.trim_page_image_cache(keep_indices=keep)
            except Exception:
                pass
            try:
                if hasattr(self, 'trim_page_mask_cache'):
                    keep = [current_idx] if current_idx >= 0 else []
                    self.trim_page_mask_cache(keep_indices=keep)
            except Exception:
                pass
            try:
                __import__('gc').collect()
            except Exception:
                pass
        return True

    def save_to_work_cache(self):
        if (
            getattr(self, "_suppress_work_cache_dirty", False)
            or getattr(self, "is_loading_project", False)
            or not self.project_dir
            or not getattr(self, "paths", None)
        ):
            return
        if self.work_project_store is None or not self.work_project_dir:
            # 더 이상 첫 변경 시 별도 work_sessions full copy를 만들지 않는다.
            # 현재 열려 있는 project_dir에 dirty page만 delta 저장한다.
            self.work_project_store = getattr(self, "project_store", None)
            self.work_project_dir = getattr(self, "project_dir", None)
        if self.work_project_store is None or not self.work_project_dir:
            return
        checkpoint_pages = set()
        try:
            checkpoint_pages = {int(x) for x in (getattr(self, "_checkpoint_dirty_pages", set()) or set())}
        except Exception:
            checkpoint_pages = set()

        dirty_pages = set()
        try:
            if hasattr(self, "storage_engine") and self.storage_engine is not None:
                plan = self.storage_engine.make_plan(force_full=False, reason="work_cache_page_delta")
                dirty_pages = set(getattr(plan, "dirty_pages", set()) or set())
        except Exception:
            dirty_pages = set()
        try:
            if not dirty_pages and hasattr(self, "project_engine") and self.project_engine is not None:
                dirty_pages = set(self.project_engine.dirty_page_indices())
        except Exception:
            pass
        try:
            if not dirty_pages and hasattr(self, "page_engine") and self.page_engine is not None:
                dirty_pages = set(self.page_engine.dirty_pages())
        except Exception:
            pass

        dirty_kinds_by_page = {}
        try:
            pe = getattr(self, "project_engine", None)
            summary = pe.dirty_summary() if pe is not None and hasattr(pe, "dirty_summary") else {}
            raw_dirty = summary.get("dirty_pages", {}) if isinstance(summary, dict) else {}
            if isinstance(raw_dirty, dict):
                for k, v in raw_dirty.items():
                    try:
                        dirty_kinds_by_page[int(k)] = {str(x or "data") for x in list(v or [])}
                    except Exception:
                        pass
        except Exception:
            dirty_kinds_by_page = {}

        text_json_only_kinds = {"text", "checkpoint_text", "checkpoint_fallback", "data", "translation", "translated_text", "text_effect_preview"}

        checkpoint_kinds = {}
        try:
            checkpoint_kinds = getattr(self, "_checkpoint_dirty_kinds", {}) or {}
        except Exception:
            checkpoint_kinds = {}
        checkpoint_text_only = bool(checkpoint_pages)
        if checkpoint_text_only:
            try:
                for pidx in checkpoint_pages:
                    # checkpoint kind와 project/page dirty kind를 합쳐서 판단한다.
                    # 이전에는 checkpoint_text만 남아 있고 실제 dirty에는 paint가 있어도 journal로 빠졌다.
                    kinds = {str(x or "") for x in list(checkpoint_kinds.get(int(pidx), set()) or set())}
                    kinds |= {str(x or "") for x in list(dirty_kinds_by_page.get(int(pidx), set()) or set())}
                    if not kinds or not set(kinds).issubset(text_json_only_kinds):
                        checkpoint_text_only = False
                        break
            except Exception:
                checkpoint_text_only = False

        if checkpoint_pages and checkpoint_text_only and hasattr(self.work_project_store, "save_page_data_delta"):
            journal_pages = set(checkpoint_pages)
            try:
                self.work_project_store.ui_state = self.current_project_ui_state()
            except Exception:
                self.work_project_store.ui_state = getattr(self.work_project_store, "ui_state", {}) or {}
            try:
                self.audit_boundary_event(
                    "WORK_CACHE_PAGE_JOURNAL_SAVE_ENTER",
                    dirty_pages=sorted(int(x) for x in journal_pages),
                    stack=True,
                )
            except Exception:
                pass
            self.work_project_store.save_page_data_delta(self.data, journal_pages, current_index=getattr(self, "idx", 0))
            try:
                self.audit_boundary_event(
                    "WORK_CACHE_PAGE_JOURNAL_SAVE_DONE",
                    dirty_pages=sorted(int(x) for x in journal_pages),
                )
            except Exception:
                pass
            try:
                self._checkpoint_dirty_pages.difference_update(journal_pages)
                for pidx in list(journal_pages):
                    try:
                        self._checkpoint_dirty_kinds.pop(int(pidx), None)
                    except Exception:
                        pass
            except Exception:
                pass
            dirty_pages = journal_pages

        elif checkpoint_pages and hasattr(self.work_project_store, "save_pages_delta"):
            image_pages = set(checkpoint_pages)
            try:
                self.audit_boundary_event(
                    "WORK_CACHE_PAGE_CHECKPOINT_IMAGE_DELTA_ENTER",
                    dirty_pages=sorted(int(x) for x in image_pages),
                    kinds={int(k): sorted(list(v)) for k, v in (checkpoint_kinds or {}).items() if int(k) in image_pages},
                    stack=True,
                )
            except Exception:
                pass
            try:
                self.flush_workspace_image_pages(image_pages, reason="checkpoint_image_dirty", release_non_current=True)
            except Exception:
                try:
                    self.work_project_store.save_pages_delta(self.paths, self.data, image_pages, current_index=getattr(self, "idx", 0))
                except Exception:
                    pass
            try:
                self._checkpoint_dirty_pages.difference_update(image_pages)
                for pidx in list(image_pages):
                    try:
                        self._checkpoint_dirty_kinds.pop(int(pidx), None)
                    except Exception:
                        pass
            except Exception:
                pass
            dirty_pages = image_pages

        elif not dirty_pages:
            # view/UI 상태만 바뀐 상황에서 work cache 전체 저장으로 빠지면 다시 프로젝트 단위 저장이 된다.
            # 개별 페이지 dirty가 없으면 복구 후보 기록만 갱신하고 끝낸다.
            try:
                self.audit_boundary_event("WORK_CACHE_PAGE_DELTA_SKIP_NO_DIRTY_PAGE")
            except Exception:
                pass

        else:
            text_only_project_dirty = bool(dirty_pages) and bool(dirty_kinds_by_page)
            if text_only_project_dirty:
                try:
                    for page_i in dirty_pages:
                        kinds = dirty_kinds_by_page.get(int(page_i), set())
                        if not kinds or not set(kinds).issubset(text_json_only_kinds):
                            text_only_project_dirty = False
                            break
                except Exception:
                    text_only_project_dirty = False

            if text_only_project_dirty:
                # 이미 journal에 반영된 텍스트 dirty는 YSBG 내보내기용 dirty로만 남긴다.
                # checkpoint_dirty가 없는데 project_dirty 전체를 다시 journal로 쓰면 매번 [1,2,...]가 반복 저장된다.
                try:
                    self.audit_boundary_event(
                        "WORK_CACHE_PAGE_JOURNAL_SKIP_NO_CHECKPOINT_DIRTY",
                        dirty_pages=sorted(int(x) for x in dirty_pages),
                        throttle_ms=1200,
                    )
                except Exception:
                    pass

            elif hasattr(self.work_project_store, "save_pages_delta"):
                try:
                    self.work_project_store.ui_state = self.current_project_ui_state()
                except Exception:
                    self.work_project_store.ui_state = getattr(self.work_project_store, "ui_state", {}) or {}
                self.work_project_store.clean_image_format = self.current_clean_image_format() if hasattr(self, "current_clean_image_format") else getattr(self, "clean_image_format", "png")
                self.work_project_store.clean_image_quality = self.current_clean_image_quality() if hasattr(self, "current_clean_image_quality") else getattr(self, "clean_image_quality", 95)
                try:
                    self.audit_boundary_event(
                        "WORK_CACHE_PAGE_DELTA_SAVE_ENTER",
                        dirty_pages=sorted(int(x) for x in dirty_pages),
                        stack=True,
                    )
                except Exception:
                    pass
                self.work_project_store.save_pages_delta(self.paths, self.data, dirty_pages, current_index=getattr(self, "idx", 0))
                try:
                    self.audit_boundary_event(
                        "WORK_CACHE_PAGE_DELTA_SAVE_DONE",
                        dirty_pages=sorted(int(x) for x in dirty_pages),
                    )
                except Exception:
                    pass
            else:
                # 구버전 객체 호환용 최후 폴백. 새 ProjectStore에는 save_pages_delta가 있어야 한다.
                try:
                    self.audit_boundary_event("WORK_CACHE_PAGE_DELTA_FALLBACK_FULL_STORE", dirty_pages=sorted(int(x) for x in dirty_pages), stack=True)
                except Exception:
                    pass
                self.save_project_store(self.work_project_store, force_full=False)
        # 쯔꾸르붕이에서는 작업 폴더가 본체이므로 텍스트 변경을 maker_game JSON에도
        # 가능한 한 바로 반영한다. .ysbg는 이 작업 폴더를 내보내는 운반 상자일 뿐이다.
        if dirty_pages:
            try:
                self.apply_maker_writeback_to_clone(mark_dirty=False, log_result=False, backup=False, page_indices=dirty_pages)
            except Exception as e:
                try:
                    self.log(f"⚠️ 쯔꾸르 JSON 실시간 반영 실패: {e}")
                except Exception:
                    pass
        self.record_recovery_project_dir(self.work_project_dir)
        if dirty_pages:
            self.has_unsaved_changes = True

    def mark_saved_state(self):
        try:
            self.clear_pending_work_cache_save_state("mark_saved_state")
        except Exception:
            pass
        self.has_unsaved_changes = False
        try:
            if hasattr(self, "project_engine") and self.project_engine is not None:
                self.project_engine.mark_saved()
            if hasattr(self, "page_engine") and self.page_engine is not None:
                self.page_engine.clear_dirty()
        except Exception:
            pass

    def save_app_options_cache(self):
        # v2.4 QA6: 실시간 자동저장은 폐지. 예전 캐시가 남아도 항상 OFF로 저장한다.
        self.auto_save_enabled = False
        self.app_options["auto_save_enabled"] = False
        self.app_options[UI_THEME_KEY] = str(getattr(self, "ui_theme", THEME_DARK) or THEME_DARK)
        self.app_options[UI_LANGUAGE_KEY] = normalize_ui_language(getattr(self, "ui_language", LANG_KO))
        self.app_options["analysis_number_box_width"] = int(getattr(self, "analysis_number_box_width", 40))
        try:
            self.app_options["brush_size"] = max(1, min(500, int(getattr(getattr(self, "view", None), "brush_size", 25) or 25)))
        except Exception:
            self.app_options["brush_size"] = int(self.app_options.get("brush_size", 25) or 25)
        self.app_options[PAGE_TAB_DISPLAY_MODE_KEY] = normalize_page_display_mode(getattr(self, "page_tab_display_name_mode", DEFAULT_PAGE_DISPLAY_MODE))
        self.app_options[OUTPUT_DISPLAY_MODE_KEY] = normalize_page_display_mode(getattr(self, "output_display_name_mode", DEFAULT_PAGE_DISPLAY_MODE))
        self.app_options[OUTPUT_IMAGE_FORMAT_KEY] = normalize_output_image_format(getattr(self, "output_image_format", DEFAULT_OUTPUT_IMAGE_FORMAT))
        self.app_options[CLEAN_IMAGE_FORMAT_KEY] = normalize_output_image_format(getattr(self, "clean_image_format", DEFAULT_OUTPUT_IMAGE_FORMAT))
        self.app_options[OUTPUT_IMAGE_QUALITY_KEY] = normalize_output_image_quality(getattr(self, "output_image_quality", DEFAULT_OUTPUT_IMAGE_QUALITY))
        self.app_options[CLEAN_IMAGE_QUALITY_KEY] = normalize_output_image_quality(getattr(self, "clean_image_quality", DEFAULT_OUTPUT_IMAGE_QUALITY))
        self.app_options[OUTPUT_TEXT_RENDER_QUALITY_KEY] = normalize_output_text_render_quality(getattr(self, "output_text_render_quality", DEFAULT_OUTPUT_TEXT_RENDER_QUALITY))
        self.app_options[LOG_PANEL_COLLAPSED_KEY] = bool(getattr(self, "log_panel_collapsed", DEFAULT_LOG_PANEL_COLLAPSED))
        self.app_options[SHOW_PATHS_IN_LOG_KEY] = bool(getattr(self, "show_paths_in_log", False))
        self.app_options[SHOW_CACHE_PATHS_IN_SETTINGS_KEY] = bool(getattr(self, "show_cache_paths_in_settings", False))
        self.app_options["interface_tooltips_enabled"] = bool(getattr(self, "interface_tooltips_enabled", True))
        self.app_options["use_light_file_dialog"] = bool(getattr(self, "use_light_file_dialog", True))
        self.app_options["temp_auto_cleanup_enabled"] = bool(self.app_options.get("temp_auto_cleanup_enabled", True))
        cleanup_days = int(self.app_options.get("temp_auto_cleanup_days", 7) or 7)
        if cleanup_days not in (7, 30, 90, 180, 365):
            cleanup_days = 7
        self.app_options["temp_auto_cleanup_days"] = cleanup_days
        self.app_options[ANALYSIS_TEXT_MASK_EXPAND_RATIO_KEY] = clamp_analysis_mask_ratio(
            self.app_options.get(ANALYSIS_TEXT_MASK_EXPAND_RATIO_KEY, getattr(Config, "MERGE_RATIO", DEFAULT_ANALYSIS_TEXT_MASK_EXPAND_RATIO)),
            DEFAULT_ANALYSIS_TEXT_MASK_EXPAND_RATIO,
        )
        self.app_options[ANALYSIS_PAINT_MASK_EXPAND_RATIO_KEY] = clamp_analysis_mask_ratio(
            self.app_options.get(ANALYSIS_PAINT_MASK_EXPAND_RATIO_KEY, getattr(Config, "INPAINT_RATIO", DEFAULT_ANALYSIS_PAINT_MASK_EXPAND_RATIO)),
            DEFAULT_ANALYSIS_PAINT_MASK_EXPAND_RATIO,
        )
        self.app_options[ANALYSIS_TEXT_MASK_MIN_EXPAND_PX_KEY] = clamp_analysis_mask_min_px(
            self.app_options.get(ANALYSIS_TEXT_MASK_MIN_EXPAND_PX_KEY, getattr(Config, "MERGE_MIN_STROKE_PX", DEFAULT_ANALYSIS_TEXT_MASK_MIN_EXPAND_PX)),
            DEFAULT_ANALYSIS_TEXT_MASK_MIN_EXPAND_PX,
        )
        self.app_options[ANALYSIS_PAINT_MASK_MIN_EXPAND_PX_KEY] = clamp_analysis_mask_min_px(
            self.app_options.get(ANALYSIS_PAINT_MASK_MIN_EXPAND_PX_KEY, getattr(Config, "MIN_STROKE_PX", DEFAULT_ANALYSIS_PAINT_MASK_MIN_EXPAND_PX)),
            DEFAULT_ANALYSIS_PAINT_MASK_MIN_EXPAND_PX,
        )
        self.sync_analysis_mask_options_to_config()
        self.app_options.setdefault(TRANSLATION_PROMPT_KEY, "")
        self.app_options.setdefault(TRANSLATION_GLOSSARY_TEXT_KEY, "")
        self.app_options.setdefault(TRANSLATION_GLOSSARY_PATH_KEY, "")
        save_app_options(self.app_options)

    def page_name_mode_label_pairs(self):
        return [
            (PAGE_DISPLAY_MODE_ORIGINAL, "원본 파일명"),
            (PAGE_DISPLAY_MODE_PAGE_ORIGINAL, "1p_원본 파일명"),
            (PAGE_DISPLAY_MODE_PAGE_NUMBER, "page001"),
        ]

    def ask_page_name_mode(self, title, current_mode):
        pairs = self.page_name_mode_label_pairs()
        current_mode = normalize_page_display_mode(current_mode)
        labels = [label for _mode, label in pairs]
        current_index = 0
        for i, (mode, _label) in enumerate(pairs):
            if mode == current_mode:
                current_index = i
                break
        value, ok = QInputDialog.getItem(
            self,
            self.tr_ui(title),
            self.tr_ui("표시명 형식:"),
            [self.tr_ui(label) for label in labels],
            current_index,
            False,
        )
        if not ok:
            return None
        try:
            selected_index = [self.tr_ui(label) for label in labels].index(value)
        except ValueError:
            selected_index = current_index
        return pairs[selected_index][0]

    def open_page_tab_display_name_dialog(self):
        old_mode = normalize_page_display_mode(getattr(self, "page_tab_display_name_mode", DEFAULT_PAGE_DISPLAY_MODE))
        new_mode = self.ask_page_name_mode("페이지 탭 표시명 설정", old_mode)
        if not new_mode or new_mode == old_mode:
            return False
        self.page_tab_display_name_mode = normalize_page_display_mode(new_mode)
        self.save_app_options_cache()
        self.refresh_page_tabs()
        self.log(f"📑 페이지 탭 표시명 설정: {self.page_tab_display_name_mode}")
        return True

    def open_output_display_name_dialog(self):
        old_mode = normalize_page_display_mode(getattr(self, "output_display_name_mode", DEFAULT_PAGE_DISPLAY_MODE))
        new_mode = self.ask_page_name_mode("출력 표시명 설정", old_mode)
        if not new_mode or new_mode == old_mode:
            return False
        self.output_display_name_mode = normalize_page_display_mode(new_mode)
        self.save_app_options_cache()
        self.log(f"📤 출력 표시명 설정: {self.output_display_name_mode}")
        return True

    def sync_translation_option_cache_to_config(self):
        """옵션 캐시에 저장된 번역 프롬프트/단어장을 번역 엔진 Config에 반영한다."""
        try:
            Config.TRANSLATION_PROMPT = str(self.app_options.get(TRANSLATION_PROMPT_KEY, "") or "")
            Config.TRANSLATION_GLOSSARY_TEXT = str(self.app_options.get(TRANSLATION_GLOSSARY_TEXT_KEY, "") or "")
        except Exception:
            pass

    def sync_analysis_mask_options_to_config(self):
        """옵션 캐시의 분석 마스크 확장 설정을 엔진 Config에 반영한다."""
        try:
            text_ratio = clamp_analysis_mask_ratio(
                self.app_options.get(ANALYSIS_TEXT_MASK_EXPAND_RATIO_KEY, DEFAULT_ANALYSIS_TEXT_MASK_EXPAND_RATIO),
                DEFAULT_ANALYSIS_TEXT_MASK_EXPAND_RATIO,
            )
            paint_ratio = clamp_analysis_mask_ratio(
                self.app_options.get(ANALYSIS_PAINT_MASK_EXPAND_RATIO_KEY, DEFAULT_ANALYSIS_PAINT_MASK_EXPAND_RATIO),
                DEFAULT_ANALYSIS_PAINT_MASK_EXPAND_RATIO,
            )
            text_min_px = clamp_analysis_mask_min_px(
                self.app_options.get(ANALYSIS_TEXT_MASK_MIN_EXPAND_PX_KEY, DEFAULT_ANALYSIS_TEXT_MASK_MIN_EXPAND_PX),
                DEFAULT_ANALYSIS_TEXT_MASK_MIN_EXPAND_PX,
            )
            paint_min_px = clamp_analysis_mask_min_px(
                self.app_options.get(ANALYSIS_PAINT_MASK_MIN_EXPAND_PX_KEY, DEFAULT_ANALYSIS_PAINT_MASK_MIN_EXPAND_PX),
                DEFAULT_ANALYSIS_PAINT_MASK_MIN_EXPAND_PX,
            )
            self.app_options[ANALYSIS_TEXT_MASK_EXPAND_RATIO_KEY] = text_ratio
            self.app_options[ANALYSIS_PAINT_MASK_EXPAND_RATIO_KEY] = paint_ratio
            self.app_options[ANALYSIS_TEXT_MASK_MIN_EXPAND_PX_KEY] = text_min_px
            self.app_options[ANALYSIS_PAINT_MASK_MIN_EXPAND_PX_KEY] = paint_min_px
            Config.MERGE_RATIO = text_ratio
            Config.INPAINT_RATIO = paint_ratio
            Config.MERGE_MIN_STROKE_PX = text_min_px
            Config.MIN_STROKE_PX = paint_min_px
        except Exception:
            pass

    def reload_saved_project_from_disk(self, refresh_view=True):
        """실제 프로젝트 내보내기본을 다시 로드해서 paths를 프로젝트 폴더 기준으로 되돌린다."""
        if not self.project_dir:
            return False
        project_file = os.path.join(self.project_dir, PROJECT_FILENAME)
        if not os.path.exists(project_file):
            return False

        self.is_loading_project = True
        try:
            store = ProjectStore()
            self.paths, self.data, self.idx = store.load(project_file)
            self.project_store = store
            self.project_dir = store.project_dir
            ui_state = getattr(store, "ui_state", {}) or {}
            self.project_ui_view_states = copy.deepcopy(ui_state.get("view_states") or getattr(self, "project_ui_view_states", {}) or {})
            self.restore_project_ui_state(ui_state, refresh=False)
            if refresh_view:
                mode_to_load = int(ui_state.get("current_mode", self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 0) or 0)
                self.set_work_mode_without_undo(mode_to_load)
                self.load()
                state = self.project_ui_view_states.get(self.view_state_key(self.idx, mode_to_load))
                if state:
                    self.apply_view_state(state)
                    QTimer.singleShot(0, lambda st=copy.deepcopy(state): self.apply_view_state(st))
                    QTimer.singleShot(30, lambda st=copy.deepcopy(state): self.apply_view_state(st))
                    QTimer.singleShot(80, lambda st=copy.deepcopy(state): self.apply_view_state(st))
            return True
        finally:
            self.is_loading_project = False

    def commit_to_real_project_only(self):
        """작업 캐시 상태를 실제 프로젝트에 저장하되, 새 작업 캐시는 만들지 않는다."""
        if not self.project_dir:
            return False
        self.commit_current_page_ui_to_data()
        self.save_project_store(self.project_store)
        self.mark_saved_state()
        try:
            self.clear_pending_clean_import_cache(getattr(self, "work_project_dir", None))
            self.clear_pending_clean_import_cache(getattr(self, "project_dir", None))
        except Exception:
            pass
        return True

    def toggle_auto_save_mode(self, checked=False):
        """Deprecated: 실시간 자동저장 모드는 YSBG 패키지 구조 이후 폐지되었다.

        일반 편집 변경분은 복구용 작업 캐시에 저장되고, 실제 .ysbg 반영은
        [내보내기]에서만 확정한다.
        """
        self.auto_save_enabled = False
        try:
            self.app_options["auto_save_enabled"] = False
            self.save_app_options_cache()
        except Exception:
            pass
        try:
            action = getattr(self, "act_auto_save_mode", None)
            if action is not None:
                action.blockSignals(True)
                action.setChecked(False)
                action.setEnabled(False)
                action.setVisible(False)
                action.blockSignals(False)
        except Exception:
            pass
        try:
            self.log("🧪 자동저장 모드는 폐지되었습니다. 변경 사항은 작업 캐시에 보관되고, 프로젝트 내보내기 시 YSBG에 확정됩니다.")
        except Exception:
            pass

    def confirm_unsaved_before_switch(self):
        """쯔꾸르붕이에서는 종료/전환 시 저장 확인창을 띄우지 않는다.

        작업 폴더는 실시간 작업 공간이고, 정식 산출물 확정은 [내보내기]만 담당한다.
        따라서 텍스트 수정/AI 번역/설정 변경으로 has_unsaved_changes가 켜져 있어도
        프로젝트 전환·홈화면 이동·종료 전에 "저장할까요?"를 묻지 않는다.
        """
        try:
            if not self.has_open_project():
                self.clear_pending_work_cache_save_state("confirm_without_project")
                self.has_unsaved_changes = False
                return True
        except Exception:
            pass
        try:
            if getattr(self, "project_dir", None) and getattr(self, "paths", None):
                self.commit_current_page_ui_to_data()
        except Exception as e:
            try:
                self.log(f"⚠️ 프로젝트 전환 전 현재 화면 반영 실패: {e}")
            except Exception:
                pass
        return True

    def closeEvent(self, event):
        """프로그램 종료 처리.

        쯔꾸르붕이는 별도 저장 기능을 두지 않고 [내보내기]로만 산출물을 확정한다.
        따라서 종료 시 저장 확인창을 띄우지 않는다. 현재 편집 중인 셀/텍스트만
        안전하게 확정하고, 복구/런타임 캐시를 정리한 뒤 바로 종료한다.
        """
        try:
            if getattr(self, "is_batch_running", False):
                _save_ui_diag("MESSAGEBOX_DONE_BEGIN")
                QMessageBox.information(
                    self,
                    self.tr_ui("일괄 작업 중"),
                    self.tr_ui("일괄 작업 중에는 프로그램을 종료할 수 없습니다.\n작업이 끝난 뒤 다시 종료해 주세요."),
                )
                event.ignore()
                return

            if getattr(self, "_closing_confirmed", False):
                self.cleanup_external_open_runtime_info()
                event.accept()
                return

            self._app_is_closing = True

            try:
                if getattr(self, "inline_text_editor", None) is not None:
                    self.finish_inline_text_edit(commit=True, refresh=False)
            except Exception as e:
                try:
                    self.log(f"⚠️ 종료 전 텍스트 편집 확정 실패: {e}")
                except Exception:
                    pass

            try:
                if getattr(self, "tab", None) is not None:
                    editor = self.tab.focusWidget()
                    if editor is not None:
                        self.tab.closePersistentEditor(editor)
            except Exception:
                pass

            try:
                if getattr(self, "project_dir", None) and getattr(self, "paths", None):
                    self.commit_current_page_ui_to_data()
            except Exception as e:
                try:
                    self.log(f"⚠️ 종료 전 현재 화면 상태 반영 실패: {e}")
                except Exception:
                    pass

            try:
                self.cleanup_work_cache()
            except Exception as e:
                try:
                    self.log(f"⚠️ 작업 캐시 정리 실패: {e}")
                except Exception:
                    pass
            try:
                self.delete_temp_project_if_needed()
            except Exception as e:
                try:
                    self.log(f"⚠️ 임시 프로젝트 정리 실패: {e}")
                except Exception:
                    pass

            self.has_unsaved_changes = False
            self.cleanup_external_open_runtime_info()
            self._closing_confirmed = True
            event.accept()
        except Exception as e:
            self._app_is_closing = False
            try:
                import traceback
                detail = traceback.format_exc()
                self.log(f"❌ 종료 처리 중 오류: {e}")
                QMessageBox.critical(
                    self,
                    self.tr_ui("종료 오류"),
                    self.tr_ui("프로그램 종료 처리 중 오류가 발생했습니다.\n작업 보호를 위해 종료를 취소합니다.") + f"\n\n{detail}",
                )
            except Exception:
                pass
            event.ignore()


    def default_empty_project_name(self):
        """빈 프로젝트 생성 기본 이름을 만든다."""
        try:
            return self.tr_ui("새 프로젝트")
        except Exception:
            return "새 프로젝트"

    def project_creation_preview_path(self, parent_dir, project_name):
        """새 빈 프로젝트가 생성될 작업 폴더/project.json 경로를 미리 보여준다."""
        try:
            parent = Path(str(parent_dir or workspaces_dir())).expanduser()
        except Exception:
            parent = workspaces_dir()
        name = clean_workspace_name(project_name or self.default_empty_project_name())
        return str(parent / safe_project_name(name) / PROJECT_FILENAME)

    def remember_last_project_create_dir(self, directory):
        try:
            directory = str(directory or "").strip()
            if not directory:
                return
            self.app_options[LAST_PROJECT_CREATE_DIR_KEY] = directory
            save_app_options(self.app_options)
        except Exception:
            pass

    def resolve_initial_project_create_dir(self):
        fallback = str(workspaces_dir())
        saved = str((self.app_options or {}).get(LAST_PROJECT_CREATE_DIR_KEY, "") or "").strip()
        if saved and os.path.isdir(saved):
            return saved
        if saved and not os.path.isdir(saved):
            QMessageBox.warning(
                self,
                self.tr_ui("프로젝트 생성 위치 확인"),
                self.tr_ui("마지막 프로젝트 생성 위치를 찾지 못했습니다.\n새 위치를 선택해 주세요."),
            )
            chosen = QFileDialog.getExistingDirectory(self, self.tr_ui("프로젝트 생성 위치 선택"), fallback)
            if chosen:
                self.remember_last_project_create_dir(chosen)
                return chosen
        return fallback

    def build_create_project_ysbt_path(self, parent_dir, project_name):
        """새 프로젝트 만들기에서 사용할 작업 폴더 경로를 만든다.

        YSB Game Editor는 평소 작업 본체를 project.json이 있는 폴더로 본다.
        .ysbg는 이 작업 폴더를 옮기거나 백업할 때 쓰는 내보내기 패키지다.
        """
        parent = Path(str(parent_dir or workspaces_dir())).expanduser()
        parent.mkdir(parents=True, exist_ok=True)
        safe_name = safe_project_name(clean_workspace_name(project_name or self.default_empty_project_name()))
        return str(parent / safe_name)

    def build_unique_create_project_ysbt_path(self, parent_dir, project_name):
        return self.build_create_project_ysbt_path(parent_dir, project_name)

    def new_empty_project_action(self):
        """이미지 없이 빈 프로젝트를 먼저 생성한다."""
        if not self.guard_project_action("새 프로젝트 만들기"):
            return False

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("새 프로젝트 만들기"))
        dlg.setModal(True)
        dlg.resize(560, 220)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        name_label = QLabel(self.tr_ui("프로젝트 이름"), dlg)
        name_edit = QLineEdit(dlg)
        name_edit.setText(self.default_empty_project_name())
        name_edit.selectAll()
        layout.addWidget(name_label)
        layout.addWidget(name_edit)

        location_label = QLabel(self.tr_ui("생성 위치"), dlg)
        location_row = QHBoxLayout()
        location_edit = QLineEdit(dlg)
        try:
            location_edit.setText(self.resolve_initial_project_create_dir())
        except Exception:
            location_edit.setText(str(workspaces_dir()))
        browse_btn = QToolButton(dlg)
        browse_btn.setText("⋯")
        browse_btn.setFixedWidth(34)
        location_row.addWidget(location_edit, 1)
        location_row.addWidget(browse_btn, 0)
        layout.addWidget(location_label)
        layout.addLayout(location_row)

        preview_label = QLabel(dlg)
        preview_label.setWordWrap(True)
        preview_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        preview_label.setObjectName("ProjectCreatePathPreview")
        try:
            preview_label.setStyleSheet("QLabel#ProjectCreatePathPreview { color:#9fb7d8; padding:6px 0px; }")
        except Exception:
            pass
        layout.addWidget(preview_label)

        info_label = QLabel(self.tr_ui("프로젝트 이름과 생성 위치를 먼저 확정하고, 게임 클론을 넣을 빈 프로젝트(.ysbg)를 만듭니다. 이후 [게임 가져오기]로 맵 페이지를 생성합니다."), dlg)
        info_label.setWordWrap(True)
        try:
            info_label.setStyleSheet("color:#A39BA1;")
        except Exception:
            pass
        layout.addWidget(info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        try:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("만들기"))
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("취소"))
        except Exception:
            pass
        layout.addWidget(buttons)

        def update_preview():
            try:
                preview = self.project_creation_preview_path(location_edit.text(), name_edit.text())
                preview_label.setText(f"{self.tr_ui('생성 경로')}: {preview}")
            except Exception:
                pass

        def browse_location():
            start = location_edit.text().strip() or str(workspaces_dir())
            folder = QFileDialog.getExistingDirectory(dlg, self.tr_ui("프로젝트 생성 위치 선택"), start)
            if folder:
                location_edit.setText(folder)
                update_preview()

        overwrite_choice = {"value": False}

        def accept_with_duplicate_check():
            project_name_now = clean_workspace_name(name_edit.text() or self.default_empty_project_name())
            parent_dir_now = location_edit.text().strip() or str(workspaces_dir())
            try:
                candidate_path = self.build_create_project_ysbt_path(parent_dir_now, project_name_now)
            except Exception:
                candidate_path = self.project_creation_preview_path(parent_dir_now, project_name_now)

            if candidate_path and os.path.exists(candidate_path):
                msg = QMessageBox(dlg)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle(self.tr_ui("이름 중복"))
                msg.setText(self.tr_ui("같은 이름의 YSBG 프로젝트가 이미 있습니다."))
                msg.setInformativeText(str(candidate_path))
                btn_rename = msg.addButton(self.tr_ui("이름 바꾸기"), QMessageBox.ButtonRole.AcceptRole)
                btn_overwrite = msg.addButton(self.tr_ui("덮어쓰기"), QMessageBox.ButtonRole.DestructiveRole)
                btn_cancel = msg.addButton(self.tr_ui("취소"), QMessageBox.ButtonRole.RejectRole)
                msg.setDefaultButton(btn_rename)
                msg.setEscapeButton(btn_cancel)
                try:
                    msg.setStyleSheet(self.message_box_style())
                except Exception:
                    pass
                force_message_box_front(msg)
                msg.exec()
                clicked = msg.clickedButton()

                if clicked is btn_rename:
                    overwrite_choice["value"] = False
                    name_edit.setFocus(Qt.FocusReason.OtherFocusReason)
                    name_edit.selectAll()
                    return
                if clicked is btn_overwrite:
                    overwrite_choice["value"] = True
                    dlg.accept()
                    return
                return

            overwrite_choice["value"] = False
            dlg.accept()

        browse_btn.clicked.connect(browse_location)
        name_edit.textChanged.connect(update_preview)
        location_edit.textChanged.connect(update_preview)
        buttons.accepted.connect(accept_with_duplicate_check)
        buttons.rejected.connect(dlg.reject)
        update_preview()

        name_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False

        project_name = clean_workspace_name(name_edit.text() or self.default_empty_project_name())
        parent_dir = location_edit.text().strip() or str(workspaces_dir())
        return self.create_empty_project(project_name=project_name, parent_dir=parent_dir, overwrite_existing=bool(overwrite_choice.get("value")))

    def create_empty_project(self, project_name="새 프로젝트", parent_dir=None, overwrite_existing=False):
        """이미지 없는 빈 작업 폴더를 만들고 project.json을 생성한 뒤 에디터로 진입한다.

        .ysbg 패키지는 여기서 만들지 않는다. 평소 작업 본체는 이 폴더와
        project.json이고, 메뉴의 [내보내기]가 현재 작업 폴더를 .ysbg로 패키징한다.
        """
        if not self.guard_project_action("새 프로젝트 만들기"):
            return False
        if not self.confirm_unsaved_before_switch():
            return False

        project_name = clean_workspace_name(project_name or self.default_empty_project_name())
        try:
            parent = Path(str(parent_dir or workspaces_dir())).expanduser()
            parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr_ui("프로젝트 생성 실패"),
                f"{self.tr_ui('프로젝트 생성 위치를 만들 수 없습니다.')}\n{parent_dir}\n\n{e}",
            )
            return False

        display_project_name = clean_workspace_name(project_name)
        project_uuid = uuid.uuid4().hex
        project_dir = os.path.abspath(str(parent / safe_project_name(display_project_name)))
        if os.path.exists(project_dir):
            if not overwrite_existing:
                QMessageBox.warning(
                    self,
                    self.tr_ui("이름 중복"),
                    f"{self.tr_ui('같은 이름의 작업 폴더가 이미 있습니다.')}\n{project_dir}",
                )
                return False
            try:
                shutil.rmtree(project_dir, ignore_errors=True)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    self.tr_ui("프로젝트 생성 실패"),
                    f"{self.tr_ui('기존 작업 폴더를 지우지 못했습니다.')}\n{project_dir}\n\n{e}",
                )
                return False

        try:
            self.commit_current_page_ui_to_data()
        except Exception:
            pass

        try:
            store = ProjectStore(project_dir)
            store.init_dirs()
            store.ui_state = {
                "current_mode": 0,
                "view_states": {},
                "show_final_text": True,
                "project_kind": "ysb_game_editor",
                "package_extension": YSB_EXTENSION,
            }
            store.save([], {}, current_index=0)
            store.write_manifest(package_source="", project_name=display_project_name, project_uuid=project_uuid)
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr_ui("프로젝트 생성 실패"),
                f"{self.tr_ui('빈 작업 폴더를 만들지 못했습니다.')}\n{project_dir}\n\n{e}",
            )
            return False

        self.close_current_project_state_for_switch()
        self.project_store = store
        self.project_dir = project_dir
        self.paths = []
        self.data = {}
        self.idx = 0
        self.undo_clear_all_pages("project reset")
        self.undo_clear_project("project reset")
        self.undo_boundary = None
        self.project_ui_view_states = {}
        self.ysbg_package_path = None
        self.is_temp_project = False
        self.suggested_project_name = display_project_name
        self.suggested_package_dir = str(parent)
        self.work_project_dir = self.project_dir
        self.work_project_store = self.project_store
        self.is_loading_project = False
        self.record_recovery_project_dir(project_dir)
        self.remember_last_project_create_dir(parent)
        self.mark_saved_state()
        self.update_window_title()
        self.update_undo_redo_buttons()
        self.reset_mode_to_original()
        self.show_editor()
        self.load()
        try:
            if hasattr(self, "_force_maker_preview_rebuild_for_current_project"):
                self._force_maker_preview_rebuild_for_current_project(reason="empty_project_created")
        except Exception:
            pass
        self.record_current_project_recent()
        self.log(f"📁 빈 작업 폴더 생성: {project_dir}")
        self.log("📄 평소에는 project.json으로 열고, 필요할 때 [내보내기]로 .ysbg 패키지를 만듭니다.")
        self.log("🎮 아직 가져온 게임이 없습니다. [게임 가져오기]로 RPG Maker MV/MZ 프로젝트 폴더를 클론해 주세요.")
        try:
            self.sync_maker_project_action_states()
        except Exception:
            pass
        return True

    def create_new_project_from_image_paths(self, source_paths, source_label="이미지 드롭"):
        source_paths = self.normalize_image_drop_paths(source_paths)
        if not source_paths:
            self.log("⚠️ 불러올 이미지 파일이 없습니다.")
            return False
        if not self.guard_project_action("새 프로젝트 만들기"):
            return False
        if not self.confirm_unsaved_before_switch():
            return False

        # 프로젝트 이름은 첫 생성 때 묻지 않는다.
        # 실제 이름은 .ysbg로 저장할 때 파일명 기준으로 확정된다.
        self.suggested_project_name = safe_project_name(Path(source_paths[0]).stem + "_project")
        self.suggested_package_dir = None
        project_dir = self.workspace_temp_project_dir(self.suggested_project_name)

        try:
            self.commit_current_page_ui_to_data()
        except Exception:
            pass
        try:
            self.close_current_project_state_for_switch()
        except Exception:
            pass

        self.project_store = ProjectStore(project_dir)
        self.paths, self.data = self.project_store.create_from_images(project_dir, source_paths)
        self.undo_clear_all_pages("project reset")
        self.undo_clear_project("project reset")
        self.undo_boundary = None
        self.update_undo_redo_buttons()
        self.project_ui_view_states = {}
        self.project_store.write_manifest(project_name="unsaved_project")
        self.project_dir = project_dir
        self.enforce_initial_project_image_names(source_paths)
        self.record_recovery_project_dir(project_dir)
        self.ysbg_package_path = None
        self.is_temp_project = True
        self.update_window_title()
        self.idx = 0
        self.is_loading_project = False
        self.log(f"📁 새 임시 프로젝트 작업 폴더 생성: {project_dir}")
        self.log("💾 아직 YSBG 파일로 저장되지 않았습니다. [내보내기]을 눌러 .ysbg로 저장하세요.")
        self.log(f"🖼️ 이미지 {len(source_paths)}장으로 새 프로젝트 생성: {source_label}")
        self.has_unsaved_changes = True
        if not self.auto_save_enabled:
            self.start_work_cache_from_current(mark_dirty=True)
            self.enforce_initial_project_image_names(source_paths)
        self.reset_mode_to_original()
        self.show_editor()
        self.load()
        try:
            if hasattr(self, "_force_maker_preview_rebuild_for_current_project"):
                self._force_maker_preview_rebuild_for_current_project(reason="image_project_created")
        except Exception:
            pass
        return True


    def _maker_import_progress_dialog(self, label_text=None):
        """게임 가져오기 중 사용자에게 멈춘 것이 아님을 보여주는 진행창을 만든다.

        MV/MZ 프로젝트는 복사·맵 JSON 분석·DB 텍스트 추출이 오래 걸릴 수 있으므로
        작업 단계와 가능한 경우 현재/전체 개수를 같이 표시한다.
        """
        try:
            dlg = QProgressDialog(self)
            dlg.setWindowTitle(self.tr_ui("게임 가져오기"))
            dlg.setLabelText(self.tr_ui(label_text or "게임을 가져오는 중입니다..."))
            dlg.setRange(0, 0)
            dlg.setMinimumDuration(0)
            dlg.setAutoClose(False)
            dlg.setAutoReset(False)
            dlg.setCancelButton(None)
            dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            try:
                apply_progress_dialog_theme(dlg, bool(self.is_light_theme()))
            except Exception:
                pass
            dlg.show()
            QApplication.processEvents()
            return dlg
        except Exception:
            return None

    def _maker_import_progress_update(self, dlg, label_text, current=None, total=None):
        try:
            if dlg is not None:
                if total is not None:
                    try:
                        total_i = int(total or 0)
                        current_i = int(current or 0)
                        if total_i > 0:
                            dlg.setRange(0, total_i)
                            dlg.setValue(max(0, min(current_i, total_i)))
                        else:
                            dlg.setRange(0, 0)
                    except Exception:
                        dlg.setRange(0, 0)
                dlg.setLabelText(self.tr_ui(str(label_text or "게임을 가져오는 중입니다...")))
                dlg.show()
                QApplication.processEvents()
        except Exception:
            pass

    def _maker_import_progress_callback(self, dlg):
        def _callback(current=None, total=None, detail=None):
            try:
                self._maker_import_progress_update(dlg, detail or "게임을 가져오는 중입니다...", current=current, total=total)
            except Exception:
                pass
        return _callback

    def _maker_import_progress_close(self, dlg):
        try:
            if dlg is not None:
                dlg.close()
                dlg.deleteLater()
                QApplication.processEvents()
        except Exception:
            pass

    def _log_maker_import_layer_summary(self, maker_summary, *, phase=""):
        try:
            summary = maker_summary if isinstance(maker_summary, dict) else {}
            maps = len(summary.get("maps") or [])
            common = len(summary.get("common_events") or [])
            db = len(summary.get("database_pages") or [])
            virtual = len(summary.get("virtual_pages") or [])
            total = int(summary.get("total_text_units") or 0)
            files = []
            for item in (summary.get("database_pages") or []):
                if isinstance(item, dict):
                    files.append(f"{item.get('source_file')}:{item.get('text_unit_count')}")
            detail = ", ".join(files[:20]) if files else "none"
            self.log(f"🧪 IMPORT_LAYER_SUMMARY({phase}) | maps={maps} common={common} database={db} virtual={virtual} total_text={total} db_files={detail}")
        except Exception:
            pass

    def create_new_project_from_game_dir(self, game_dir, source_label="게임 가져오기"):
        """RPG Maker 게임 폴더를 새 임시 프로젝트로 가져온다.

        YSB Maker 흐름에서는 이미지 목록 대신 게임 폴더가 원본이 된다. 게임은
        프로젝트 작업 폴더 안의 maker_game/으로 통째로 복사되고, MapXXX.json은
        각각 페이지 탭으로 재조립된다.
        """
        if not game_dir:
            return False
        if not self.guard_project_action("새 프로젝트 만들기"):
            return False
        if not self.confirm_unsaved_before_switch():
            return False

        game_name = safe_project_name(Path(str(game_dir)).name or "maker_game")
        self.suggested_project_name = safe_project_name(game_name + "_maker_project")
        self.suggested_package_dir = None
        project_dir = self.workspace_temp_project_dir(self.suggested_project_name)

        progress = self._maker_import_progress_dialog("게임 폴더를 가져오는 중입니다...\n잠시만 기다려 주세요.")
        try:
            self.commit_current_page_ui_to_data()
        except Exception:
            pass
        try:
            self.close_current_project_state_for_switch()
        except Exception:
            pass

        try:
            self._maker_import_progress_update(progress, "작업 폴더를 준비하는 중입니다...")
            self.project_store = ProjectStore(project_dir)
            # DB 레이어 생성은 project_dir 기준으로 data 폴더를 찾으므로,
            # 게임 가져오기 중에도 먼저 현재 작업 폴더를 지정해 둔다.
            self.project_dir = project_dir
            self._maker_import_progress_update(progress, "게임 파일을 복사하고 맵 데이터를 분석하는 중입니다...\n게임 크기에 따라 시간이 걸릴 수 있습니다.")
            maker_progress = self._maker_import_progress_callback(progress)
            self.paths, self.data, maker_summary = self.project_store.create_from_maker_game(project_dir, game_dir, progress_callback=maker_progress)
            self._log_maker_import_layer_summary(maker_summary, phase="new_project_after_build")
            # DB 페이지는 가져오기 시점에 이미 self.paths/self.data 안에 page_type=database로 생성된다.
            # 여기서 제거/분리하지 않고, 모드별 탭 필터링으로만 보여준다.
            try:
                self.maker_database_mode_enabled = False
                self.maker_database_idx = 0
            except Exception:
                pass
            self._maker_import_progress_update(progress, "맵과 대사표를 준비하는 중입니다...")
            try:
                self._prebuild_maker_preview_cache_for_current_project(progress, reason="maker_game_import")
            except Exception as _preview_build_error:
                try:
                    self.audit_boundary_event("MAKER_PREVIEW_PREBUILD_FAILED", reason="maker_game_import", error=f"{type(_preview_build_error).__name__}: {_preview_build_error}")
                except Exception:
                    pass
                try:
                    self.log(self.tr_ui("⚠️ 프리뷰 선생성 실패: {error}", error=f"{type(_preview_build_error).__name__}: {_preview_build_error}"))
                except Exception:
                    pass
        except Exception as e:
            self._maker_import_progress_close(progress)
            QMessageBox.critical(
                self,
                self.tr_ui("게임 가져오기 실패"),
                f"{self.tr_ui('쯔꾸르 게임을 가져오지 못했습니다.')}\n{game_dir}\n\n{e}",
            )
            return False

        self.undo_clear_all_pages("project reset")
        self.undo_clear_project("project reset")
        self.undo_boundary = None
        self.update_undo_redo_buttons()
        self.project_ui_view_states = {}
        try:
            self.project_store.write_manifest(project_name="unsaved_maker_project")
        except Exception:
            pass
        self.project_dir = project_dir
        self.record_recovery_project_dir(project_dir)
        self.ysbg_package_path = None
        self.is_temp_project = True
        self.update_window_title()
        self.idx = 0
        self.is_loading_project = False
        total_maps = len((maker_summary or {}).get("maps") or []) if isinstance(maker_summary, dict) else len(self.paths)
        total_text = int((maker_summary or {}).get("total_text_units") or 0) if isinstance(maker_summary, dict) else 0
        engine = (maker_summary or {}).get("engine") if isinstance(maker_summary, dict) else {}
        engine_label = str((engine or {}).get("engine_label") or "RPG Maker MV/MZ")
        engine_conf = (engine or {}).get("confidence")
        self.log(f"📁 새 임시 쯔꾸르 작업 폴더 생성: {project_dir}")
        self.log("💾 아직 YSBG 파일로 저장되지 않았습니다. [내보내기]을 눌러 .ysbg로 저장하세요.")
        self.log(f"🧭 {self.tr_ui('엔진 자동 감지')}: {engine_label} / {self.tr_ui('신뢰도')} {engine_conf}")
        for warning in (engine or {}).get("warnings") or []:
            self.log(f"⚠️ {self.tr_ui('엔진 감지 참고')}: {warning}")
        self.log(f"🎮 게임 가져오기 완료: 맵 {total_maps}개 / 텍스트 {total_text}개 - {source_label}")
        self.has_unsaved_changes = True
        if not self.auto_save_enabled:
            self.start_work_cache_from_current(mark_dirty=True)
        self.reset_mode_to_original()
        try:
            self._maker_import_progress_update(progress, "프리뷰와 대사표를 여는 중입니다...")
            self.show_editor()
            self.load()
        except Exception as e:
            self._maker_import_progress_close(progress)
            QMessageBox.critical(
                self,
                self.tr_ui("게임 가져오기 실패"),
                f"{self.tr_ui('쯔꾸르 게임을 가져오지 못했습니다.')}\n{game_dir}\n\n{e}",
            )
            return False
        try:
            if hasattr(self, "_force_maker_preview_rebuild_for_current_project"):
                self._force_maker_preview_rebuild_for_current_project(reason="maker_game_project_created")
        except Exception:
            pass
        try:
            self.schedule_progressive_page_load(self.idx)
        except Exception:
            pass
        try:
            self.record_current_project_recent()
        except Exception:
            pass
        try:
            self.sync_maker_project_action_states()
        except Exception:
            pass
        self._maker_import_progress_close(progress)
        return True

    def _prebuild_maker_preview_cache_for_current_project(self, progress=None, *, reason="maker_game_import"):
        """Pre-render preview images for every non-database Maker page.

        On first RPG Maker import we want all page preview images to exist on disk
        already, so reopening the project mostly becomes image loading instead of
        JSON/tile re-rendering. Map pages create full tile-backed preview caches;
        Common Events create their lightweight virtual-page placeholders.
        """
        try:
            from ysb.tools.maker_project import regenerate_maker_placeholder_for_page
        except Exception as e:
            try:
                self.log(self.tr_ui("⚠️ 프리뷰 선생성 준비 실패: {error}", error=f"{type(e).__name__}: {e}"))
            except Exception:
                pass
            return {"total": 0, "ok": 0, "failed": [f"import:{type(e).__name__}: {e}"]}

        paths = list(getattr(self, "paths", []) or [])
        data = getattr(self, "data", {}) or {}
        targets = []
        for idx, image_path in enumerate(paths):
            try:
                page = data.get(idx)
            except Exception:
                page = None
            if not isinstance(page, dict):
                continue
            meta = page.get("maker_page") if isinstance(page.get("maker_page"), dict) else {}
            if not isinstance(meta, dict) or not meta:
                continue
            page_type = str(meta.get("page_type") or "map").strip().lower()
            if page_type == "database":
                continue
            image_path = str(image_path or "").strip()
            if not image_path:
                continue
            targets.append((idx, image_path, page, meta, page_type))

        total = len(targets)
        try:
            self.audit_boundary_event("MAKER_PREVIEW_PREBUILD_ENTER", reason=str(reason or "maker_game_import"), total=total)
        except Exception:
            pass
        if total <= 0:
            try:
                self.audit_boundary_event("MAKER_PREVIEW_PREBUILD_DONE", reason=str(reason or "maker_game_import"), total=0, ok=0, failed=0)
            except Exception:
                pass
            return {"total": 0, "ok": 0, "failed": []}

        ok_count = 0
        failed = []
        for order, (idx, image_path, page, meta, page_type) in enumerate(targets, start=1):
            title = str(meta.get("page_title") or meta.get("map_name") or meta.get("name") or Path(image_path).stem or f"page_{idx}")
            label = f"프리뷰 캐시 생성 중... ({order}/{total})\n{title}"
            try:
                self._maker_import_progress_update(progress, label, current=order - 1, total=total)
            except Exception:
                pass

            # Import-time prebuild is a hard-build path.  It must not depend on
            # an existing preview PNG, curr['ori'], viewer cache, deferred flags,
            # or a previously saved force flag.  Use a fresh one-shot render
            # settings dict and never persist runtime force flags to the project.
            base_settings = dict(page.get("maker_preview_settings") or {})
            settings = dict(base_settings)
            root_for_render = str(getattr(self, "project_dir", "") or "")
            settings["project_root"] = root_for_render
            settings["maker_project_root"] = root_for_render
            settings["preview_project_root"] = root_for_render
            settings["defer_tile_render"] = False
            settings["force_maker_preview_rebuild"] = True
            settings["force_preview_rebuild"] = True
            settings["preview_import_hard_build"] = True
            settings["preview_prebuild_reason"] = str(reason or "maker_game_import")
            if page_type in {"", "map"}:
                settings["show_tile_map_preview"] = True
            try:
                # Keep saved settings clean.  Reopen should load caches, not inherit
                # force-rebuild runtime flags from the import pass.
                page["maker_preview_settings"] = dict(base_settings)
            except Exception:
                pass
            try:
                meta["preview_render_deferred"] = False
                meta["preview_rendered_on_demand"] = False
                meta["preview_cache_hit"] = False
            except Exception:
                pass
            try:
                page["ori"] = None
            except Exception:
                pass

            ok = False
            try:
                self.audit_boundary_event("MAKER_PREVIEW_PREBUILD_PAGE_ENTER", reason=str(reason or "maker_game_import"), page_idx=idx, order=order, total=total, page_type=page_type, title=title)
            except Exception:
                pass
            try:
                ok = bool(regenerate_maker_placeholder_for_page(image_path, page, settings=settings))
            except Exception as e:
                ok = False
                failed.append(f"{idx}:{type(e).__name__}: {e}")
            if ok:
                ok_count += 1
            else:
                if len(failed) < 50:
                    failed.append(f"{idx}:{title}")
            try:
                self.audit_boundary_event("MAKER_PREVIEW_PREBUILD_PAGE_DONE", reason=str(reason or "maker_game_import"), page_idx=idx, order=order, total=total, page_type=page_type, ok=bool(ok))
            except Exception:
                pass
            try:
                meta["preview_prebuilt"] = bool(ok)
                meta["preview_prebuilt_reason"] = str(reason or "maker_game_import")
            except Exception:
                pass

        try:
            self._maker_import_progress_update(progress, f"프리뷰 캐시 생성 완료\n{ok_count}/{total}개 준비됨", current=total, total=total)
        except Exception:
            pass
        try:
            self.audit_boundary_event("MAKER_PREVIEW_PREBUILD_DONE", reason=str(reason or "maker_game_import"), total=total, ok=ok_count, failed=len(failed))
        except Exception:
            pass
        return {"total": total, "ok": ok_count, "failed": failed}

    def import_game_into_current_project(self, game_dir):
        """현재 열린 빈자리/프로젝트 안으로 RPG Maker 게임을 클론하고 페이지를 재구성한다."""
        if not game_dir:
            return False
        if not self.has_open_project():
            return self.create_new_project_from_game_dir(game_dir)
        if not self.guard_project_action("게임 가져오기"):
            return False

        has_pages = bool(getattr(self, "paths", None))
        if has_pages:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(self.tr_ui("게임 다시 가져오기"))
            box.setText(self.tr_ui("현재 프로젝트의 페이지 구성을 새 게임 분석 결과로 교체할까요?"))
            box.setInformativeText(self.tr_ui("기존 페이지/텍스트 작업은 새 맵 페이지로 바뀝니다. 원본 게임은 프로젝트 안에 다시 클론됩니다."))
            btn_replace = box.addButton(self.tr_ui("교체"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(self.tr_ui("취소"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not btn_replace:
                self.log("↩️ 게임 가져오기 취소")
                return False

        progress = self._maker_import_progress_dialog("게임 폴더를 가져오는 중입니다...\n잠시만 기다려 주세요.")
        try:
            self.commit_current_page_ui_to_data()
        except Exception:
            pass

        try:
            try:
                if hasattr(self, "_maker_preview_new_lifecycle_token"):
                    self._maker_preview_new_lifecycle_token("maker_game_reimport")
                if hasattr(self, "_clear_maker_preview_display_state"):
                    self._clear_maker_preview_display_state(reason="maker_game_reimport")
            except Exception:
                pass
            if not getattr(self, "project_dir", None):
                project_name = safe_project_name(Path(str(game_dir)).name + "_maker_project")
                self.project_dir = self.workspace_temp_project_dir(project_name)
            self._maker_import_progress_update(progress, "작업 폴더를 준비하는 중입니다...")
            self.project_store = ProjectStore(self.project_dir)
            self._maker_import_progress_update(progress, "게임 파일을 복사하고 맵 데이터를 분석하는 중입니다...\n게임 크기에 따라 시간이 걸릴 수 있습니다.")
            maker_progress = self._maker_import_progress_callback(progress)
            self.paths, self.data, maker_summary = self.project_store.create_from_maker_game(self.project_dir, game_dir, progress_callback=maker_progress)
            self._log_maker_import_layer_summary(maker_summary, phase="import_into_project_after_build")
            # DB 페이지는 가져오기 시점에 이미 self.paths/self.data 안에 page_type=database로 생성된다.
            # 여기서 제거/분리하지 않고, 모드별 탭 필터링으로만 보여준다.
            try:
                self.maker_database_mode_enabled = False
                self.maker_database_idx = 0
            except Exception:
                pass
            self._maker_import_progress_update(progress, "맵과 대사표를 준비하는 중입니다...")
            try:
                self._prebuild_maker_preview_cache_for_current_project(progress, reason="maker_game_reimport")
            except Exception as _preview_build_error:
                try:
                    self.audit_boundary_event("MAKER_PREVIEW_PREBUILD_FAILED", reason="maker_game_reimport", error=f"{type(_preview_build_error).__name__}: {_preview_build_error}")
                except Exception:
                    pass
                try:
                    self.log(self.tr_ui("⚠️ 프리뷰 선생성 실패: {error}", error=f"{type(_preview_build_error).__name__}: {_preview_build_error}"))
                except Exception:
                    pass
        except Exception as e:
            self._maker_import_progress_close(progress)
            QMessageBox.critical(
                self,
                self.tr_ui("게임 가져오기 실패"),
                f"{self.tr_ui('쯔꾸르 게임을 가져오지 못했습니다.')}\n{game_dir}\n\n{e}",
            )
            return False

        self.idx = 0
        self.project_ui_view_states = {}
        self.undo_clear_all_pages("maker import")
        self.undo_clear_project("maker import")
        self.undo_boundary = None
        self.update_undo_redo_buttons()
        self.record_recovery_project_dir(self.project_dir)
        self.has_unsaved_changes = True
        try:
            self.mark_project_structure_dirty("maker_game_import")
        except Exception:
            pass
        if not self.auto_save_enabled:
            self.start_work_cache_from_current(mark_dirty=True)
        self.reset_mode_to_original()
        try:
            self._maker_import_progress_update(progress, "프리뷰와 대사표를 여는 중입니다...")
            self.show_editor()
            self.load()
            try:
                if hasattr(self, "_force_maker_preview_rebuild_for_current_project"):
                    self._force_maker_preview_rebuild_for_current_project(reason="maker_game_reimport_loaded")
            except Exception:
                pass
            try:
                self.schedule_progressive_page_load(self.idx)
            except Exception:
                pass
        except Exception as e:
            self._maker_import_progress_close(progress)
            QMessageBox.critical(
                self,
                self.tr_ui("게임 가져오기 실패"),
                f"{self.tr_ui('쯔꾸르 게임을 가져오지 못했습니다.')}\n{game_dir}\n\n{e}",
            )
            return False
        total_maps = len((maker_summary or {}).get("maps") or []) if isinstance(maker_summary, dict) else len(self.paths)
        total_text = int((maker_summary or {}).get("total_text_units") or 0) if isinstance(maker_summary, dict) else 0
        engine = (maker_summary or {}).get("engine") if isinstance(maker_summary, dict) else {}
        engine_label = str((engine or {}).get("engine_label") or "RPG Maker MV/MZ")
        engine_conf = (engine or {}).get("confidence")
        self.log(f"🧭 {self.tr_ui('엔진 자동 감지')}: {engine_label} / {self.tr_ui('신뢰도')} {engine_conf}")
        for warning in (engine or {}).get("warnings") or []:
            self.log(f"⚠️ {self.tr_ui('엔진 감지 참고')}: {warning}")
        self.log(f"🎮 게임 가져오기 완료: 맵 {total_maps}개 / 텍스트 {total_text}개")
        self.log(f"🧩 {self.tr_ui('OCR 대신 MapXXX.json을 분석해 맵 탭과 텍스트 행을 만들었습니다.')}")
        self._maker_import_progress_close(progress)
        return True

    def import_maker_game_action(self):
        """쯔꾸르붕이 기준명: RPG Maker 게임 폴더를 가져온다."""
        return self.import_images_action()

    def import_images_action(self):
        """YSB Maker 분기: 이미지 불러오기 대신 RPG Maker 게임 폴더를 가져온다.

        2단계 메뉴 규칙: 게임 가져오기는 새 프로젝트 작업 폴더가 열린 뒤,
        아직 maker_game이 들어오지 않은 상태에서만 허용한다.
        """
        try:
            self._file_dialog_log("FILE_DIALOG_ACTION_TRIGGER", reason="import_game_action", has_open_project=bool(self.has_open_project()), stack_widget=str(type(self.main_stack.currentWidget()).__name__) if hasattr(self, "main_stack") else "")
        except Exception:
            pass
        try:
            can_import = self._maker_can_import_game_into_current_project()
        except Exception:
            can_import = False
        if not can_import:
            try:
                if not bool(self.has_open_project()):
                    QMessageBox.information(self, self.tr_ui("프로젝트 없음"), self.tr_ui("먼저 새 프로젝트를 만든 뒤 게임을 가져와 주세요."))
                else:
                    QMessageBox.information(self, self.tr_ui("게임 가져오기"), self.tr_ui("이 프로젝트에는 이미 게임이 들어와 있습니다. 새 프로젝트에서 다시 가져와 주세요."))
            except Exception:
                try:
                    self.log("⚠️ 게임 가져오기는 새 프로젝트에서, 아직 게임이 없을 때만 사용할 수 있습니다.")
                except Exception:
                    pass
            return False
        start_dir = ""
        try:
            start_dir = str((self.app_options or {}).get("last_maker_game_import_dir", "") or "")
        except Exception:
            start_dir = ""
        if not start_dir or not os.path.isdir(start_dir):
            start_dir = str(Path.home())
        game_dir = QFileDialog.getExistingDirectory(
            self,
            self.tr_ui("가져올 RPG Maker MV/MZ 게임 폴더 선택"),
            start_dir,
        )
        if not game_dir:
            return False
        try:
            self.app_options["last_maker_game_import_dir"] = str(game_dir)
            save_app_options(self.app_options)
        except Exception:
            pass
        try:
            in_editor = (
                hasattr(self, "main_stack")
                and hasattr(self, "editor_widget")
                and self.main_stack.currentWidget() is self.editor_widget
            )
        except Exception:
            in_editor = False
        if in_editor and self.has_open_project():
            return self.import_game_into_current_project(game_dir)
        try:
            QMessageBox.information(self, self.tr_ui("프로젝트 없음"), self.tr_ui("먼저 새 프로젝트를 만든 뒤 게임을 가져와 주세요."))
        except Exception:
            pass
        return False

    def new_project_from_images(self):
        try:
            self._file_dialog_log("FILE_DIALOG_ACTION_TRIGGER", reason="new_project_from_images")
        except Exception:
            pass
        source_paths, _ = self.get_open_file_names_logged(
            "new_project_from_images",
            self,
            self.tr_ui("프로젝트에 넣을 이미지 선택"),
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)"
        )
        if not source_paths:
            return
        self.create_new_project_from_image_paths(source_paths, source_label="파일 선택")

    def open_project(self):
        try:
            self._file_dialog_log("FILE_DIALOG_ACTION_TRIGGER", reason="open_project")
        except Exception:
            pass
        """운반용 .ysbg 패키지를 연다."""
        if not self.guard_project_action("YSBG 열기"):
            return

        path, _ = self.get_open_file_name_logged(
            "open_project",
            self,
            self.tr_ui("YSBG 열기"),
            str(default_package_dir()),
            ("YSBG Package (*.ysbg);;All Files (*.*)" if str(getattr(self, "ui_language", LANG_KO)).lower().startswith("en") else "YSBG 패키지 (*.ysbg);;모든 파일 (*.*)")
        )
        if not path:
            return

        self.open_project_path(path)

    def open_project_json(self):
        """구버전/디버그용 project.json 직접 열기. 기본 열기와 분리한다."""
        try:
            self._file_dialog_log("FILE_DIALOG_ACTION_TRIGGER", reason="open_project_json")
        except Exception:
            pass
        self._file_dialog_log("FILE_DIALOG_GUARD_ENTER", reason="open_project_json")
        if not self.guard_project_action("프로젝트 열기"):
            self._file_dialog_log("FILE_DIALOG_GUARD_BLOCKED", reason="open_project_json")
            return
        self._file_dialog_log("FILE_DIALOG_GUARD_DONE", reason="open_project_json")

        path, _ = self.get_open_file_name_logged(
            "open_project_json",
            self,
            self.tr_ui("프로젝트 열기"),
            str(workspaces_dir()),
            "Project JSON (project.json);;JSON (*.json);;All Files (*.*)"
        )
        if not path:
            return

        self.open_project_path(path, skip_guard=True)

    def apply_maker_writeback_to_clone(self, *, mark_dirty=True, log_result=True, backup=False, page_indices=None):
        """Apply current table text to the cloned RPG Maker JSON files.

        쯔꾸르붕이는 maker_game/ 클론 자체가 현재 완성본이다.
        수동 수정은 즉시, AI 번역은 결과 확정 후 한 번에 이 함수를 통해
        클론 JSON에 반영한다.  원본 JSON 기준점은 maker_backup/original_json/에
        별도 보관하므로 live writeback 기본값은 추가 timestamp 백업을 만들지 않는다.
        """
        project_dir = str(getattr(self, "project_dir", "") or "").strip()
        if not project_dir:
            return {"written_units": 0, "skipped_empty": 0, "touched_maps": []}
        try:
            from ysb.tools.maker_project import apply_maker_translations_to_game, is_maker_project_dir
        except Exception:
            return {"written_units": 0, "skipped_empty": 0, "touched_maps": []}
        try:
            has_maker_page = any(
                isinstance(page, dict) and (
                    isinstance(page.get("maker_page"), dict)
                    or any(isinstance(row, dict) and isinstance(row.get("maker_text_unit"), dict) for row in (page.get("data") or []))
                )
                for page in (getattr(self, "data", {}) or {}).values()
            )
        except Exception:
            has_maker_page = False
        if not has_maker_page and not is_maker_project_dir(project_dir):
            return {"written_units": 0, "skipped_empty": 0, "touched_maps": []}
        summary = apply_maker_translations_to_game(project_dir, getattr(self, "data", None), page_indices=page_indices, backup=backup)
        try:
            written = int((summary or {}).get("written_units") or 0)
        except Exception:
            written = 0
        if written > 0:
            if mark_dirty:
                try:
                    page_idx = int(getattr(self, "idx", 0) or 0)
                    pe = getattr(self, "project_engine", None)
                    if pe is not None and hasattr(pe, "mark_page_dirty"):
                        pe.mark_page_dirty(page_idx, "maker_writeback")
                    pg = getattr(self, "page_engine", None)
                    if pg is not None and hasattr(pg, "mark_dirty"):
                        pg.mark_dirty(page_idx, "maker_writeback")
                except Exception:
                    pass
            if log_result:
                try:
                    touched = len((summary or {}).get("touched_maps") or [])
                    backup_dir = str((summary or {}).get("backup_dir") or "")
                    msg = f"🎮 쯔꾸르 JSON 실시간 반영: 텍스트 {written}개 / 맵 {touched}개"
                    if backup_dir:
                        msg += f" / 백업 {backup_dir}"
                    self.log(msg)
                except Exception:
                    pass
        return summary or {"written_units": 0, "skipped_empty": 0, "touched_maps": []}


    def save_project(self):
        def _save_ui_diag(event: str, **fields):
            try:
                root = os.environ.get("LOCALAPPDATA")
                if not root:
                    root = os.path.join(str(Path.home()), "AppData", "Local")
                log_dir = os.path.join(root, "YSBGameEditor", "logs")
                os.makedirs(log_dir, exist_ok=True)
                path = os.path.join(log_dir, "save_package_diag.log")
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                parts = [f"[{ts}]", f"UI_{event}"]
                for k, v in fields.items():
                    try:
                        sv = repr(v)
                    except Exception:
                        sv = "<unrepr>"
                    parts.append(f"{k}={sv}")
                with open(path, "a", encoding="utf-8") as f:
                    f.write(" | ".join(parts) + "\n")
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
            except Exception:
                pass

        _save_ui_diag("SAVE_PROJECT_ENTER", page_idx=getattr(self, "idx", None), ysbt=getattr(self, "ysbg_package_path", None), project_dir=getattr(self, "project_dir", None))
        try:
            self.audit_boundary_event("SAVE_PROJECT_ENTER", stack=True)
        except Exception:
            pass
        if not self.guard_project_action("프로젝트 내보내기"):
            return
        if not self.project_dir:
            self.log("⚠️ 프로젝트가 없습니다. 새 프로젝트를 먼저 만들어주세요.")
            return
        if not self.ysbg_package_path:
            # 새 프로젝트/구버전 폴더 프로젝트는 첫 저장 때 .ysbg 위치를 정한다.
            self.save_project_as()
            return

        total_pages = len(getattr(self, "paths", []) or [])
        self._long_task_cancel_requested = False
        self._active_long_task_kind = "save"
        save_cancelled = False
        dirty_count = 0
        structure_dirty = True
        save_mode_text = "YSBG 내보내기"

        self.begin_busy_state("프로젝트 내보내기")
        try:
            self.show_task_progress_overlay(
                "프로젝트 내보내기",
                f"""전체 페이지: {total_pages}개
변경 페이지: 계산 중
내보내기 진행: 0/{total_pages}
잠시 후 내보내기를 시작합니다.""",
                total=total_pages,
                cancellable=True,
            )
            try:
                overlay = getattr(self, "_task_progress_overlay", None)
                if overlay is not None:
                    overlay.note_label.setText("취소 시 현재 저장 항목이 끝난 뒤 중단됩니다.")
            except Exception:
                pass
            try:
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                QThread.msleep(300)
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            except Exception:
                pass
            if bool(getattr(self, "_long_task_cancel_requested", False)):
                raise PackageProjectCancelled("내보내기 시작 전 취소되었습니다.")

            try:
                if hasattr(self, "project_engine") and self.project_engine is not None:
                    self.project_engine.begin_explicit_save()
            except Exception:
                pass
            try:
                self.flush_pending_view_layer_commit(save_after=False)
            except Exception:
                pass
            self.update_task_progress_overlay(current=0, total=total_pages, detail=f"""전체 페이지: {total_pages}개
변경 페이지: 계산 중
내보내기 진행: 0/{total_pages}
현재 작업: 현재 화면 상태를 내보내기 데이터에 반영하는 중입니다...""")
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            _save_ui_diag("COMMIT_CURRENT_PAGE_UI_BEGIN", total_pages=total_pages)
            self.commit_current_page_ui_to_data()
            _save_ui_diag("COMMIT_CURRENT_PAGE_UI_DONE", total_pages=total_pages)
            try:
                # 리팩토링 중 일부 구형 편집 경로가 dirty flag를 못 찍는 경우를 방어한다.
                pe = getattr(self, "project_engine", None)
                if bool(getattr(self, "has_unsaved_changes", False)) and pe is not None and not pe.has_dirty():
                    page_idx = int(getattr(self, "idx", 0) or 0)
                    pe.mark_page_dirty(page_idx, "save_fallback")
                    if hasattr(self, "page_engine") and self.page_engine is not None:
                        self.page_engine.mark_dirty(page_idx, "save_fallback")
            except Exception:
                pass

            try:
                pe = getattr(self, "project_engine", None)
                page_dirty = False
                try:
                    page_dirty = bool(getattr(self, "page_engine", None) and self.page_engine.dirty_pages())
                except Exception:
                    page_dirty = False
                project_dirty = bool(pe.has_dirty()) if pe is not None else False
                if (
                    not bool(getattr(self, "has_unsaved_changes", False))
                    and not project_dirty
                    and not page_dirty
                    and not bool(getattr(self, "is_temp_project", False))
                ):
                    _save_ui_diag("SAVE_SKIPPED_NO_CHANGES")
                    try:
                        self.audit_boundary_event("SAVE_PROJECT_SKIPPED_NO_CHANGES")
                    except Exception:
                        pass
                    try:
                        self.log("💾 내보낼 변경 사항이 없습니다.")
                    except Exception:
                        pass
                    self.mark_saved_state()
                    try:
                        self.mark_workspace_state_saved(getattr(self, "project_dir", None))
                    except Exception:
                        pass
                    self.record_current_project_recent()
                    self.hide_task_progress_overlay()
                    return
            except Exception:
                pass


            try:
                self._maker_last_writeback_summary = self.apply_maker_writeback_to_clone()
            except Exception as e:
                _save_ui_diag("MAKER_WRITEBACK_EXCEPTION", error=repr(e))
                self.has_unsaved_changes = True
                self.hide_task_progress_overlay()
                QMessageBox.critical(
                    self,
                    self.tr_ui("쯔꾸르 JSON 실시간 반영 실패"),
                    f"{self.tr_ui('번역문을 쯔꾸르 게임 파일에 반영하지 못했습니다.')}\n\n{e}",
                )
                return

            self.update_task_progress_overlay(current=0, total=total_pages, detail=f"""전체 페이지: {total_pages}개
변경 페이지: 계산 중
내보내기 진행: 0/{total_pages}
현재 작업: 변경된 페이지를 확인하는 중입니다...""")
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            _save_ui_diag("SAVE_PROJECT_STORE_BEGIN")
            self.save_project_store(self.project_store)
            _save_ui_diag("SAVE_PROJECT_STORE_DONE")
            if bool(getattr(self, "_long_task_cancel_requested", False)):
                raise PackageProjectCancelled("YSBG 반영 전 저장이 취소되었습니다.")

            try:
                plan = getattr(getattr(self, "storage_engine", None), "last_plan", None)
                dirty_pages = set(getattr(plan, "dirty_pages", set()) or set()) if plan is not None else set()
                dirty_count = len(dirty_pages)
                structure_dirty = bool(plan.needs_full_save()) if plan is not None else True
                force_full_package = bool(getattr(self, "is_temp_project", False))
                if force_full_package:
                    structure_dirty = True
                    save_mode_text = "전체 YSBG 재패키징"
                    self.log("💾 [Export] 임시/복구 프로젝트 내보내기: 전체 YSBG 재패키징")
                elif structure_dirty:
                    save_mode_text = "전체 YSBG 재패키징"
                    self.log("💾 [Export] 프로젝트 구조 변경 감지: 전체 YSBG 재패키징")
                else:
                    save_mode_text = "증분 YSBG 내보내기"
                    self.log(f"💾 [Export] 변경 페이지 {dirty_count} / 전체 {total_pages}: 증분 YSBG 내보내기")
                self.update_task_progress_overlay(current=0, total=total_pages, detail=f"""전체 페이지: {total_pages}개
변경 페이지: {dirty_count}개
내보내기 진행: 0/{total_pages}
현재 작업: YSBG 반영을 준비하는 중입니다...""")
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

                def _save_progress(current=None, total=None, detail=None):
                    try:
                        show_total = int(total or total_pages or 0)
                        show_current = int(current or 0)
                        raw_detail = str(detail or "내보내는 중...")
                        if "최종 반영" in raw_detail:
                            overlay = getattr(self, "_task_progress_overlay", None)
                            if overlay is not None:
                                try:
                                    overlay.cancel_btn.setEnabled(False)
                                    overlay.note_label.setText("최종 반영 중입니다. 이 짧은 단계에서는 취소할 수 없습니다.")
                                except Exception:
                                    pass
                        formatted_detail = (
                            f"전체 페이지: {total_pages}개\n"
                            f"변경 페이지: {dirty_count}개\n"
                            f"내보내기 진행: {show_current}/{show_total}\n"
                            f"현재 작업: {raw_detail}"
                        )
                        self.update_task_progress_overlay(current=show_current, total=show_total, detail=formatted_detail)
                        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                    except Exception:
                        pass

                def _save_cancel_requested():
                    return bool(getattr(self, "_long_task_cancel_requested", False))

                text_json_only_kinds = {"text", "checkpoint_text", "checkpoint_fallback", "data", "translation", "translated_text", "text_effect_preview"}
                json_fast_save = False
                dirty_kinds_for_save = {}
                try:
                    pe = getattr(self, "project_engine", None)
                    summary = pe.dirty_summary() if pe is not None and hasattr(pe, "dirty_summary") else {}
                    raw_dirty = summary.get("dirty_pages", {}) if isinstance(summary, dict) else {}
                    if isinstance(raw_dirty, dict):
                        for k, v in raw_dirty.items():
                            try:
                                dirty_kinds_for_save[int(k)] = {str(x or "data") for x in list(v or [])}
                            except Exception:
                                pass
                    if (
                        bool(dirty_pages)
                        and not bool(structure_dirty)
                        and not bool(getattr(self, "is_temp_project", False))
                        and os.path.exists(str(getattr(self, "ysbg_package_path", "") or ""))
                    ):
                        json_fast_save = True
                        for page_i in set(int(x) for x in dirty_pages):
                            kinds = dirty_kinds_for_save.get(int(page_i), set())
                            if not kinds or not set(kinds).issubset(text_json_only_kinds):
                                json_fast_save = False
                                break
                except Exception:
                    json_fast_save = False

                try:
                    plan_dirty_pages = sorted(int(x) for x in dirty_pages)
                except Exception:
                    plan_dirty_pages = []
                try:
                    all_dirty_kinds = sorted({str(kind) for kinds in dirty_kinds_for_save.values() for kind in (kinds or set())})
                except Exception:
                    all_dirty_kinds = []
                try:
                    json_fast_reject_reason = ""
                    if not json_fast_save:
                        if bool(structure_dirty):
                            json_fast_reject_reason = "structure_dirty"
                        elif not bool(dirty_pages):
                            json_fast_reject_reason = "no_dirty_pages"
                        elif bool(getattr(self, "is_temp_project", False)):
                            json_fast_reject_reason = "temp_project"
                        elif not os.path.exists(str(getattr(self, "ysbg_package_path", "") or "")):
                            json_fast_reject_reason = "missing_ysbt"
                        else:
                            json_fast_reject_reason = "non_text_dirty_kind_or_missing_kind"
                except Exception:
                    json_fast_reject_reason = "diagnostic_error"
                _save_ui_diag(
                    "PACKAGE_PROJECT_BEGIN",
                    save_mode=save_mode_text,
                    dirty_count=dirty_count,
                    structure_dirty=structure_dirty,
                    json_fast_save=json_fast_save,
                    dirty_pages=plan_dirty_pages,
                    dirty_kind_names=all_dirty_kinds,
                    json_fast_reject_reason=json_fast_reject_reason,
                    dirty_kinds=dirty_kinds_for_save,
                )
                try:
                    self.audit_boundary_event(
                        "SAVE_DIRTY_DIAG",
                        save_mode=save_mode_text,
                        dirty_count=dirty_count,
                        structure_dirty=structure_dirty,
                        json_fast_save=json_fast_save,
                        dirty_pages=plan_dirty_pages,
                        dirty_kind_names=all_dirty_kinds,
                        json_fast_reject_reason=json_fast_reject_reason,
                        throttle_ms=100,
                    )
                except Exception:
                    pass
                if json_fast_save:
                    try:
                        self.log(f"💾 [Export] 텍스트/번역 JSON 변경 {dirty_count}페이지: YSBG 빠른 저장")
                    except Exception:
                        pass
                    try:
                        append_project_json_to_package(
                            self.project_dir,
                            self.ysbg_package_path,
                            progress_callback=_save_progress,
                            cancel_checker=_save_cancel_requested,
                        )
                    except PackageProjectCancelled:
                        raise
                    except Exception as fast_e:
                        _save_ui_diag("JSON_FAST_SAVE_FALLBACK_PACKAGE", error=repr(fast_e))
                        try:
                            self.log(f"💾 [Export] 빠른 저장 불가 → 일반 증분 저장으로 전환: {fast_e}")
                        except Exception:
                            pass
                        package_project(
                            self.project_dir,
                            self.ysbg_package_path,
                            dirty_pages=dirty_pages,
                            structure_dirty=structure_dirty,
                            incremental=not structure_dirty,
                            progress_callback=_save_progress,
                            cancel_checker=_save_cancel_requested,
                        )
                else:
                    package_project(
                        self.project_dir,
                        self.ysbg_package_path,
                        dirty_pages=dirty_pages,
                        structure_dirty=structure_dirty,
                        incremental=not structure_dirty,
                        progress_callback=_save_progress,
                        cancel_checker=_save_cancel_requested,
                    )
                _save_ui_diag("PACKAGE_PROJECT_DONE", save_mode=save_mode_text, json_fast_save=json_fast_save)
            except PackageProjectCancelled:
                _save_ui_diag("PACKAGE_PROJECT_CANCELLED")
                save_cancelled = True
                self.has_unsaved_changes = True
                try:
                    self.log("⏹️ [Export] 프로젝트 내보내기 취소됨: 원본 YSBG는 변경되지 않았습니다.")
                except Exception:
                    pass
                self.hide_task_progress_overlay()
                QMessageBox.warning(
                    self,
                    self.tr_ui("프로젝트 내보내기 취소"),
                    """프로젝트 내보내기이 취소되었습니다.

원본 YSBG 파일은 변경되지 않았습니다.
현재 작업 내용은 프로그램과 복구용 작업 캐시에 남아 있습니다.
다시 내보내면 YSBG에 반영할 수 있습니다.""",
                )
                return
            except Exception as e:
                _save_ui_diag("PACKAGE_PROJECT_EXCEPTION", error=repr(e))
                msg_text = self.tr_ui("프로젝트는 작업 폴더에 저장했지만, YSBG 파일 저장에 실패했습니다.")
                self.hide_task_progress_overlay()
                QMessageBox.critical(self, self.tr_ui("YSBG 내보내기 실패"), f"""{msg_text}

{e}""")
                self.has_unsaved_changes = True
                return

            _save_ui_diag("MARK_SAVED_BEGIN")
            self.mark_saved_state()
            try:
                self.clear_pending_clean_import_cache(getattr(self, "work_project_dir", None))
                self.clear_pending_clean_import_cache(getattr(self, "project_dir", None))
            except Exception:
                pass
            _save_ui_diag("MARK_SAVED_DONE")
            self.update_window_title()
            self.log(f"💾 프로젝트 내보내기 완료: {self.ysbg_package_path}")
            self.record_current_project_recent()
            _save_ui_diag("HIDE_OVERLAY_BEGIN")
            self.hide_task_progress_overlay()
            _save_ui_diag("HIDE_OVERLAY_DONE")
            try:
                QMessageBox.information(
                    self,
                    self.tr_ui("프로젝트 내보내기 완료"),
                    f"""프로젝트 내보내기이 완료되었습니다.

전체 페이지: {total_pages}개
변경 페이지: {dirty_count}개""",
                )
            except Exception:
                pass

            # 내보내기 완료 후에는 화면을 다시 로드하지 않고, 작업 캐시도 다시 만들지 않는다.
            # 저장된 시점의 본체는 YSBG 파일이므로 복구용 work cache를 매번 full save로 재생성할 필요가 없다.
            # 닫기 중 저장이면 어차피 나갈 것이므로 기존 작업 캐시를 삭제하고,
            # 일반 저장이면 마지막 복구 후보 기록만 지워 저장 직후 "복구할 작업"으로 보이지 않게 한다.
            if getattr(self, "_app_is_closing", False) or getattr(self, "_closing_confirmed", False):
                try:
                    _save_ui_diag("CLEANUP_WORK_CACHE_AFTER_SAVE_BEGIN", reason="closing")
                    self.cleanup_work_cache()
                    _save_ui_diag("CLEANUP_WORK_CACHE_AFTER_SAVE_DONE", reason="closing")
                except Exception as e:
                    _save_ui_diag("CLEANUP_WORK_CACHE_AFTER_SAVE_FAILED", reason="closing", error=repr(e))
            else:
                try:
                    _save_ui_diag("SKIP_WORK_CACHE_REBUILD_AFTER_SAVE")
                    self.forget_recovery_project_dir(getattr(self, "work_project_dir", None))
                except Exception:
                    pass
        except PackageProjectCancelled:
            self.has_unsaved_changes = True
            self.hide_task_progress_overlay()
            try:
                self.log("⏹️ [Export] 프로젝트 내보내기 취소됨: 원본 YSBG는 변경되지 않았습니다.")
            except Exception:
                pass
            QMessageBox.warning(
                self,
                self.tr_ui("프로젝트 내보내기 취소"),
                """프로젝트 내보내기이 취소되었습니다.

원본 YSBG 파일은 변경되지 않았습니다.
현재 작업 내용은 프로그램과 복구용 작업 캐시에 남아 있습니다.""",
            )
            return
        finally:
            _save_ui_diag("SAVE_PROJECT_FINALLY_BEGIN", save_cancelled=save_cancelled)
            try:
                if hasattr(self, "project_engine") and self.project_engine is not None:
                    self.project_engine.end_explicit_save()
            except Exception:
                pass
            try:
                self._active_long_task_kind = ""
            except Exception:
                pass
            if not save_cancelled:
                try:
                    # 정상 완료/실패 모두에서 남은 진행창을 정리한다. 취소 분기는 위에서 이미 정리한다.
                    if getattr(self, "_task_progress_overlay", None) is not None and self._task_progress_overlay.isVisible():
                        self.hide_task_progress_overlay()
                except Exception:
                    pass
            self.end_busy_state("프로젝트 내보내기")
            _save_ui_diag("SAVE_PROJECT_FINALLY_DONE")

    def ensure_save_as_output_parent(self, path_abs: str):
        """다른 이름으로 내보내기 대상 폴더가 없을 때 먼저 만든다."""
        parent = os.path.dirname(os.path.abspath(str(path_abs or "")))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)

    def _write_image_for_save_as_fallback(self, img, dst_path: str) -> bool:
        """원본 이미지 경로가 사라진 경우 메모리 이미지/작업 이미지를 새 저장용 파일로 복구한다."""
        if img is None:
            return False
        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            ext = Path(dst_path).suffix.lower()
            if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"):
                ext = ".png"
                dst_path = str(Path(dst_path).with_suffix(ext))

            if isinstance(img, (bytes, bytearray)):
                with open(dst_path, "wb") as f:
                    f.write(img)
                return os.path.exists(dst_path) and os.path.getsize(dst_path) > 0

            if isinstance(img, np.ndarray):
                encode_ext = ".jpg" if ext == ".jpeg" else ext
                ok, buf = cv2.imencode(encode_ext, img)
                if ok:
                    buf.tofile(dst_path)
                    return os.path.exists(dst_path) and os.path.getsize(dst_path) > 0
        except Exception:
            return False
        return False

    def prepare_save_as_paths_for_store(self, target_project_dir: str):
        """Save As용 이미지 경로 목록을 만든다.

        ProjectStore.save()는 원본 이미지 파일이 실제 디스크에 있어야 새 프로젝트 폴더로 복사할 수 있다.
        그런데 작업 폴더 이동/임시 캐시 정리/구버전 경로 문제로 self.paths의 일부가 사라진 경우
        다른 이름으로 내보내기이 [WinError 3]로 실패할 수 있다.

        이 함수는 저장 전에 각 이미지 경로를 확인하고,
        경로가 없으면 현재 프로젝트 images 폴더나 메모리의 ori/working_source로 복구한다.
        """
        prepared = list(self.paths or [])
        image_dir = os.path.join(str(target_project_dir), "images")
        os.makedirs(image_dir, exist_ok=True)

        project_images_dir = os.path.join(str(self.project_dir or ""), "images")
        known_exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")

        for i, src in enumerate(prepared):
            src_text = str(src or "")
            if src_text and os.path.exists(src_text):
                continue

            candidates = []
            if src_text:
                candidates.append(src_text)
                if self.project_dir and not os.path.isabs(src_text):
                    candidates.append(os.path.join(str(self.project_dir), src_text))
                if self.project_dir:
                    candidates.append(os.path.join(str(self.project_dir), "images", os.path.basename(src_text)))

            if os.path.isdir(project_images_dir):
                try:
                    for ext in known_exts:
                        candidates.append(os.path.join(project_images_dir, f"{i + 1:04d}{ext}"))
                except Exception:
                    pass

            found = None
            for cand in candidates:
                try:
                    if cand and os.path.exists(cand):
                        found = os.path.abspath(cand)
                        break
                except Exception:
                    pass

            if found:
                prepared[i] = found
                continue

            curr = self.data.get(i, {}) if isinstance(self.data, dict) else {}
            ext = Path(src_text).suffix.lower() if src_text else ".png"
            if ext not in known_exts:
                ext = ".png"
            original_hint = curr.get("original_name") if isinstance(curr, dict) else ""
            base = safe_page_file_stem(Path(str(original_hint or src_text or f"page{i + 1:03d}")).stem, fallback=f"page{i + 1:03d}")
            candidate = os.path.join(image_dir, f"{base}{ext}")
            if os.path.exists(candidate):
                for n in range(1, 10000):
                    candidate = os.path.join(image_dir, f"{base}({n}){ext}")
                    if not os.path.exists(candidate):
                        break
            dst = candidate

            recovered = False
            img = curr.get("ori") if isinstance(curr, dict) else None
            if img is not None:
                recovered = self._write_image_for_save_as_fallback(img, dst)

            if not recovered and isinstance(curr, dict):
                working_source = curr.get("working_source")
                if working_source is not None:
                    recovered = self._write_image_for_save_as_fallback(working_source, dst)

            if not recovered:
                raise FileNotFoundError(
                    "내보낼 원본 이미지 경로를 찾지 못했습니다.\n"
                    f"페이지: {i + 1}\n"
                    f"기존 경로: {src_text or '(비어 있음)'}"
                )

            prepared[i] = dst

        return prepared

    def save_project_as(self):
        """현재 작업 폴더를 .ysbg 패키지로 내보낸다.

        쯔꾸르붕이에서는 작업 폴더/project.json이 본체다.
        이 함수는 Save As처럼 새 작업 폴더로 갈아타지 않고, 현재 폴더 전체를
        운반/백업용 .ysbg 파일로 묶어 내보내기만 한다.
        """
        if not self.guard_project_action("내보내기"):
            return
        if not self.project_dir:
            self.log("⚠️ 내보낼 프로젝트가 없습니다.")
            return

        default_path = self.ysbg_package_path or self.current_package_default_path()
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr_ui("YSBG로 내보내기"),
            default_path,
            "YSBG Project (*.ysbg)"
        )
        if not path:
            return
        path_abs, display_project_name, new_uuid = self.make_ysbt_path_with_uuid_suffix(path)

        total_pages = len(getattr(self, "paths", []) or [])
        self._long_task_cancel_requested = False
        self._active_long_task_kind = "export"

        self.begin_busy_state("내보내기")
        shown_overlay = False
        try:
            self.show_task_progress_overlay(
                "내보내기",
                f"전체 맵: {total_pages}개\n현재 작업: 내보내기 준비 중...",
                total=total_pages,
                cancellable=True,
            )
            shown_overlay = True
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

            def _cancel_requested():
                return bool(getattr(self, "_long_task_cancel_requested", False))

            if _cancel_requested():
                raise PackageProjectCancelled("내보내기 시작 전 취소되었습니다.")

            try:
                if hasattr(self, "project_engine") and self.project_engine is not None:
                    self.project_engine.begin_explicit_save()
            except Exception:
                pass
            try:
                self.flush_pending_view_layer_commit(save_after=False)
            except Exception:
                pass
            self.commit_current_page_ui_to_data()

            try:
                self._maker_last_writeback_summary = self.apply_maker_writeback_to_clone()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    self.tr_ui("쯔꾸르 JSON 실시간 반영 실패"),
                    f"{self.tr_ui('번역문을 쯔꾸르 게임 파일에 반영하지 못했습니다.')}\n\n{e}",
                )
                return

            self.ensure_save_as_output_parent(path_abs)
            self.project_store.ui_state = self.current_project_ui_state()
            self.save_project_store(self.project_store)
            try:
                self.project_store.write_manifest(package_source=path_abs, project_name=display_project_name, project_uuid=new_uuid)
            except Exception:
                pass

            def _progress(current=None, total=None, detail=None):
                try:
                    show_total = int(total or total_pages or 0)
                    show_current = int(current or 0)
                    raw_detail = str(detail or "YSBG 패키지를 만드는 중...")
                    formatted = (
                        f"전체 페이지: {total_pages}개\n"
                        f"내보내기 진행: {show_current}/{show_total}\n"
                        f"현재 작업: {raw_detail}"
                    )
                    self.update_task_progress_overlay(current=show_current, total=show_total, detail=formatted)
                    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                except Exception:
                    pass

            package_project(
                self.project_dir,
                path_abs,
                project_name=display_project_name,
                project_uuid=new_uuid,
                progress_callback=_progress,
                cancel_checker=_cancel_requested,
            )
            self.ysbg_package_path = path_abs
            self.suggested_project_name = display_project_name
            self.suggested_package_dir = os.path.dirname(path_abs)
            self.is_temp_project = False
            try:
                self.mark_workspace_state_saved(getattr(self, "project_dir", None))
            except Exception:
                pass
            self.mark_saved_state()
            self.update_window_title()
            self.record_current_project_recent()
            self.log(f"📦 YSBG 내보내기 완료: {path_abs}")
            try:
                self.show_ok_notice(
                    "내보내기 완료",
                    f"YSBG 패키지로 내보냈습니다.\n{path_abs}",
                )
            except Exception:
                pass
        except PackageProjectCancelled:
            self.log("⏹️ YSBG 내보내기 취소")
            QMessageBox.warning(
                self,
                self.tr_ui("내보내기 취소"),
                self.tr_ui("YSBG 내보내기가 취소되었습니다. 현재 작업 폴더는 변경되지 않았습니다."),
            )
        except Exception as e:
            self.has_unsaved_changes = True
            QMessageBox.critical(
                self,
                self.tr_ui("YSBG 내보내기 실패"),
                f"{self.tr_ui('YSBG 파일을 내보내지 못했습니다.')}\n{path_abs}\n\n{e}",
            )
        finally:
            try:
                if hasattr(self, "project_engine") and self.project_engine is not None:
                    self.project_engine.end_explicit_save()
            except Exception:
                pass
            self._active_long_task_kind = None
            self._long_task_cancel_requested = False
            if shown_overlay:
                self.hide_task_progress_overlay()
            self.end_busy_state("내보내기")

    def auto_save_project(self):
        """복구용 작업 캐시 저장 진입점.

        이름은 기존 호출부 호환을 위해 유지하지만, v2.4 QA6부터는 실제 프로젝트나
        .ysbg 패키지를 자동 갱신하지 않는다. 일반 편집 변경분은 작업 캐시에만 저장하고,
        실제 YSBG 반영은 명시적인 프로젝트 내보내기에서만 수행한다.
        """
        if getattr(self, "is_batch_running", False) and getattr(self, "current_batch_mode", None) in ("analyze", "reanalyze"):
            try:
                self.audit_boundary_event("AUTO_SAVE_SKIPPED_DURING_BATCH_MACRO", mode=getattr(self, "current_batch_mode", None))
            except Exception:
                pass
            self.has_unsaved_changes = True
            return
        try:
            checkpoint_pages = set(getattr(self, "_checkpoint_dirty_pages", set()) or set())
            if not checkpoint_pages:
                pe = getattr(self, "project_engine", None)
                summary = pe.dirty_summary() if pe is not None and hasattr(pe, "dirty_summary") else {}
                raw_dirty = summary.get("dirty_pages", {}) if isinstance(summary, dict) else {}
                text_only = bool(raw_dirty)
                for _p, _kinds in (raw_dirty or {}).items():
                    _set = {str(x or "") for x in list(_kinds or [])}
                    if not _set or not _set.issubset({"text", "checkpoint_text", "checkpoint_fallback", "data", "translation", "translated_text", "text_effect_preview"}):
                        text_only = False
                        break
                if text_only:
                    try:
                        self.audit_boundary_event("WORK_CACHE_SAVE_SKIPPED_NO_CHECKPOINT_DIRTY", throttle_ms=2000)
                    except Exception:
                        pass
                    return
        except Exception:
            pass
        try:
            self.audit_boundary_event("WORK_CACHE_SAVE_ENTER", stack=True, throttle_ms=900)
        except Exception:
            pass
        try:
            self.note_ui_interaction_activity(600)
        except Exception:
            pass
        if (
            getattr(self, "_suppress_work_cache_dirty", False)
            or self.is_loading_project
            or self.is_autosaving
            or not self.project_dir
            or not getattr(self, "paths", None)
        ):
            return
        if getattr(self, "_text_transform_runtime_active", False):
            try:
                self.has_unsaved_changes = True
                self.update_window_title()
            except Exception:
                pass
            return
        self.auto_save_enabled = False
        self.is_autosaving = True
        try:
            try:
                self.flush_pending_view_layer_commit(save_after=False)
            except Exception:
                pass
            try:
                self.commit_current_page_ui_to_data(include_mask=False)
            except TypeError:
                self.commit_current_page_ui_to_data()
            try:
                pe = getattr(self, "project_engine", None)
                if bool(getattr(self, "has_unsaved_changes", False)) and pe is not None and not pe.has_dirty():
                    self.mark_current_page_for_recovery_checkpoint("checkpoint_fallback")
            except Exception:
                pass
            self.save_to_work_cache()
            self.update_window_title()
        finally:
            self.is_autosaving = False

    def flush_text_scene_geometry_to_data(self, data_items=None, *, mark_dirty=False, reason="scene geometry flush"):
        """현재 최종화면 텍스트 item 위치를 page data에 즉시 반영한다.

        텍스트를 드래그한 직후 변형/고급옵션/스타일 변경을 열면 data 기준으로
        레이어가 다시 만들어질 수 있다. 이때 이동 전 좌표를 쓰지 않도록
        진입 전에 scene -> data flush를 명시적으로 수행한다.
        """
        try:
            changed = bool(self.sync_final_text_scene_to_data())
        except Exception:
            changed = False

        # selected data_items가 scene item과 같은 dict가 아닐 가능성까지 보강한다.
        try:
            ids = {str(d.get('id')) for d in (data_items or []) if isinstance(d, dict) and d.get('id') is not None}
            if ids:
                curr = self.data.get(self.idx) or {}
                by_id = {str(d.get('id')): d for d in (curr.get('data', []) or []) if isinstance(d, dict) and d.get('id') is not None}
                for d in data_items or []:
                    if not isinstance(d, dict):
                        continue
                    sid = str(d.get('id'))
                    target = by_id.get(sid)
                    if target is not None and target is not d:
                        for k in ('rect', 'x_off', 'y_off', 'manual_text_rect', 'text_anchor_mode', 'rotation', 'char_width', 'char_height', 'skew_x', 'skew_y', 'trap_left', 'trap_right', 'trap_top', 'trap_bottom', 'arc_top', 'arc_bottom', 'arc_left', 'arc_right', 'arc_handles', 'arc_active_index'):
                            if k in target:
                                d[k] = copy.deepcopy(target.get(k))
        except Exception:
            pass

        if changed and mark_dirty:
            try:
                self.mark_active_page_dirty("text")
            except Exception:
                pass
            try:
                if hasattr(self, "text_engine") and self.text_engine is not None:
                    ids = [d.get('id') for d in (data_items or []) if isinstance(d, dict) and d.get('id') is not None]
                    self.text_engine.mark_dirty(int(getattr(self, "idx", 0) or 0), ids, ['rect', 'x_off', 'y_off'])
            except Exception:
                pass

        try:
            self.audit_boundary_event("TEXT_SCENE_GEOMETRY_FLUSH", reason=str(reason or ""), changed=bool(changed), mark_dirty=bool(mark_dirty), throttle_ms=120)
        except Exception:
            pass
        return changed

    def refresh_text_items_live_in_place(self, items=None, *, keep_selection=True):
        """선택 텍스트만 현재 data 기준으로 즉시 다시 그린다.

        전체 Final 텍스트 레이어 rebuild는 scene/data 개수가 어긋났을 때 안전하지만,
        스타일 수치를 휠로 바꿀 때마다 쓰면 렉이 커진다. 살아 있는 선택 item은
        item 내부 path/style만 재생성해서 가볍게 미리보기한다.
        """
        items = list(items or self.selected_text_items() or [])
        if not items:
            return False
        ok = False
        selected_ids = []
        for item in items:
            try:
                sid = getattr(item, 'data', {}).get('id')
                if sid is not None:
                    selected_ids.append(sid)
                if hasattr(item, 'rebuild_text_render_for_live_preview'):
                    item.rebuild_text_render_for_live_preview(force=True)
                else:
                    try:
                        item.prepareGeometryChange()
                    except Exception:
                        pass
                    item.update()
                ok = True
            except RuntimeError:
                continue
            except Exception:
                try:
                    item.update()
                    ok = True
                except Exception:
                    pass
        if ok:
            try:
                self.view.scene.update()
            except Exception:
                pass
            if keep_selection and selected_ids:
                try:
                    self.reselect_text_items(selected_ids)
                except Exception:
                    pass
            try:
                self.audit_boundary_event("TEXT_STYLE_REFRESH_IN_PLACE", selected_count=len(selected_ids), throttle_ms=120)
            except Exception:
                pass
        return bool(ok)

    def sync_final_text_scene_to_data(self):
        """최종화면의 실제 텍스트 아이템 위치를 현재 페이지 data에 동기화한다.

        일반 드래그/변형 드래그는 대부분 해당 이벤트에서 data를 갱신하지만,
        자동저장/페이지 이동/닫기처럼 이벤트 타이밍이 섞이는 경우를 위해
        저장 직전 화면에 남아 있는 TypesettingItem의 좌표를 한 번 더 확정한다.
        """
        if getattr(self, "_text_scene_sync_lock", False) or getattr(self, "_text_undo_restore_lock", False):
            return False
        scene = self._safe_graphics_scene()
        if scene is None:
            return False
        curr = self.data.get(self.idx)
        if not curr:
            return False

        self._text_scene_sync_lock = True
        changed = False
        try:
            data_list = curr.get('data', []) or []
            by_id = {str(d.get('id')): d for d in data_list if isinstance(d, dict)}
            try:
                scene_items = list(scene.items())
            except RuntimeError:
                return False
            except Exception:
                return False
            for item in scene_items:
                if not isinstance(item, TypesettingItem):
                    continue
                d = getattr(item, 'data', None)
                if not isinstance(d, dict):
                    continue
                if d.get('pending_new_text'):
                    continue
                item_id = str(d.get('id'))
                target = by_id.get(item_id)
                if target is None:
                    continue

                rect = list(target.get('rect') or [0, 0, 1, 1])
                while len(rect) < 4:
                    rect.append(1)
                try:
                    align = (target.get('align') or 'center').lower()
                    if align == 'left':
                        anchor_x = float(rect[0])
                    elif align == 'right':
                        anchor_x = float(rect[0]) + float(rect[2])
                    else:
                        anchor_x = float(rect[0]) + float(rect[2]) / 2.0

                    path_rect = getattr(item, '_text_path_rect', item.boundingRect())
                    item_pos = item.pos()
                    rect_x = float(rect[0])
                    rect_y = float(rect[1])
                    rect_w = max(1.0, float(rect[2]))
                    rect_h = max(1.0, float(rect[3]))
                    if bool(target.get('rasterized_text')) or bool(getattr(item, '_is_rasterized_text', False)):
                        # 객체화된 텍스트는 rect가 래스터 이미지의 좌상단 기준이다.
                        # 일반 텍스트처럼 center/align 보정을 넣으면 이동 후 저장 시 위치가 다시 밀린다.
                        new_x_off = int(round(float(item_pos.x()) - rect_x))
                        new_y_off = int(round(float(item_pos.y()) - rect_y))
                    elif align == 'left':
                        new_x_off = int(round(float(item_pos.x()) + float(path_rect.left()) - rect_x))
                        new_y_off = int(round(float(item_pos.y()) + float(path_rect.center().y()) - (rect_y + rect_h / 2.0)))
                    elif align == 'right':
                        new_x_off = int(round(float(item_pos.x()) + float(path_rect.right()) - (rect_x + rect_w)))
                        new_y_off = int(round(float(item_pos.y()) + float(path_rect.center().y()) - (rect_y + rect_h / 2.0)))
                    else:
                        new_x_off = int(round(float(item_pos.x()) + float(path_rect.center().x()) - (rect_x + rect_w / 2.0)))
                        new_y_off = int(round(float(item_pos.y()) + float(path_rect.center().y()) - (rect_y + rect_h / 2.0)))
                except Exception:
                    continue

                old_x_off = int(target.get('x_off', 0) or 0)
                old_y_off = int(target.get('y_off', 0) or 0)
                if new_x_off != old_x_off or new_y_off != old_y_off:
                    target['x_off'] = new_x_off
                    target['y_off'] = new_y_off
                    changed = True
            return changed
        finally:
            self._text_scene_sync_lock = False

    def commit_current_page_ui_to_data(self, include_mask=True):
        if hasattr(self, "is_maker_database_mode") and self.is_maker_database_mode():
            try:
                if not bool(getattr(self, "_maker_database_batch_translate_active", False)):
                    self.commit_current_database_ui_to_layer()
            except Exception:
                pass
            return
        curr = self.data.get(self.idx)
        if not curr:
            return

        # 최종화면 탭에서는 화면 위 텍스트 아이템의 현재 위치를 저장 데이터에 먼저 고정한다.
        self.sync_final_text_scene_to_data()

        # 표 상태 반영
        maker_mode = False
        try:
            maker_mode = bool(hasattr(self, "_is_current_maker_page") and self._is_current_maker_page())
        except Exception:
            maker_mode = False
        for row in range(1, self.tab.rowCount()):
            data_index = row - 1
            if data_index < 0 or data_index >= len(curr.get('data', [])):
                continue

            data_item = curr['data'][data_index]
            # Maker rows are translation/write-back records, not canvas typesetting objects.
            data_item['use_inpaint'] = False if maker_mode else self.get_table_check_state(row)

            # 객체화된 텍스트는 우측 표에 [객체] 표시용 문자열을 보여주지만,
            # 그 문자열이 원본 translated_text에 다시 저장되면 [객체] 접두사가 누적된다.
            # 래스터 텍스트 객체는 이동/삭제/부분 지우기만 허용하고 내용 편집 값은 유지한다.
            if data_item.get('rasterized_text'):
                continue

            if maker_mode:
                status_item = self.tab.item(row, 1)
                speaker_item = self.tab.item(row, 2)
                trans_item = self.tab.item(row, 6)
                memo_item = self.tab.item(row, 7)
                if status_item is not None:
                    data_item['maker_status'] = status_item.text()
                if speaker_item is not None:
                    speaker_text = speaker_item.text()
                    data_item['maker_speaker'] = speaker_text
                    data_item['maker_speaker_plain'] = speaker_text
                    data_item['maker_speaker_source'] = 'manual'
                    data_item['maker_speaker_confidence'] = 1.0 if str(speaker_text or '').strip() else 0.0
                    try:
                        meta = data_item.setdefault('maker_text_unit', {})
                        if isinstance(meta, dict):
                            meta['speaker'] = speaker_text
                            meta['speaker_plain'] = speaker_text
                            meta['speaker_source'] = 'manual'
                            meta['speaker_confidence'] = 1.0 if str(speaker_text or '').strip() else 0.0
                    except Exception:
                        pass
                data_item['translated_text'] = trans_item.text() if trans_item else ""
                if memo_item is not None:
                    data_item['maker_memo'] = memo_item.text()
            else:
                orig_item = self.tab.item(row, 2)
                if orig_item is not None:
                    data_item['text'] = orig_item.text()

                trans_item = self.tab.item(row, 3)
                data_item['translated_text'] = trans_item.text() if trans_item else ""

        # 화면 마스크 자동 저장은 평상시 현재 페이지에서만 허용.
        # 페이지 로딩/일괄 작업 중에는 이전 화면의 마스크가 다른 페이지에 섞일 수 있으므로 차단한다.
        if (not include_mask) or self.is_page_loading or self.is_batch_running:
            return

        if self.cb_mode.currentIndex() in [2, 3]:
            m = self.view.get_mask_np()
            if m is not None:
                self.set_active_mask(curr, m, self.cb_mode.currentIndex())
                curr['mask_toggle_enabled'] = self.mask_toggle_enabled


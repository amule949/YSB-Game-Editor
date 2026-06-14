import gc
import time
import uuid
import urllib.request
import urllib.error
from ysb.ui.main_window_support import *
from ysb.utils.runtime_logger import append_log, memory_text, numpy_shape_text
from ysb.ui.gemini_delayed_translation import (
    GeminiDelayedTranslationController,
    GeminiDelayedTranslationDialog,
)
from ysb.tools.maker_project import (
    load_maker_character_prompts,
    load_maker_translation_settings,
    normalize_maker_database_translation_result,
    prepare_maker_translation_payload,
    restore_maker_translation_text,
    restore_maker_translation_text_checked,
    analyze_maker_control_codes,
    strip_maker_control_codes,
    apply_maker_edge_control_codes,
    collect_maker_database_glossary,
    save_maker_database_glossary,
)


class MainWindowOperationsMixin:

    def open_api_settings_dialog(self):
        dlg = ApiSettingsDialog(self.api_settings, self, show_cache_path=bool(getattr(self, "show_cache_paths_in_settings", False)))
        if not dlg.exec():
            return

        self.api_settings = dlg.get_settings()
        ApiSettingsStore.save(self.api_settings)
        apply_settings_to_config(self.api_settings)
        self.sync_translation_option_cache_to_config()
        self.trans_chunk_sizes = {
            "openai": int(getattr(self.api_settings, "openai_chunk_size", 50) or 50),
            "deepseek": int(getattr(self.api_settings, "deepseek_chunk_size", 50) or 50),
            "google": int(getattr(self.api_settings, "google_translate_chunk_size", 50) or 50),
            "gemini": int(getattr(self.api_settings, "gemini_chunk_size", 50) or 50),
            "gemini_deferred": int(getattr(self.api_settings, "gemini_delayed_chunk_size", 50) or 50),
            "custom": int(getattr(self.api_settings, "custom_translation_chunk_size", 50) or 50),
        }
        if hasattr(self, "cb_trans_provider"):
            self.cb_trans_provider.blockSignals(True)
            try:
                self.set_combo_current_data(self.cb_trans_provider, getattr(self.api_settings, "selected_translation_provider", "openai"))
                self.on_translation_provider_changed(save=False)
            finally:
                self.cb_trans_provider.blockSignals(False)
        if hasattr(self, "refresh_ocr_language_combo"):
            self.refresh_ocr_language_combo(save=False)
        self.restart_engine(show_error=True)
        self.log("🔑 API settings cache saved" if self.ui_language == LANG_EN else "🔑 API 설정 캐시 저장 완료")

    def open_translation_prompt_dialog(self):
        """Legacy entry point: all prompt management now opens one manager."""
        return self.open_maker_character_prompts_dialog()

    def open_glossary_dialog(self):
        try:
            # Always refresh the current project's database glossary first.
            if hasattr(self, "refresh_maker_database_auto_glossary"):
                self.refresh_maker_database_auto_glossary(show_log=False)
        except Exception:
            pass

        auto_entries = normalize_glossary_entry_dict(
            self.app_options.get(TRANSLATION_AUTO_DB_GLOSSARY_ENTRIES_KEY, {})
        )
        user_entries = normalize_glossary_entry_dict(
            self.app_options.get(TRANSLATION_USER_GLOSSARY_ENTRIES_KEY, {})
        )
        user_notes = str(self.app_options.get(TRANSLATION_USER_GLOSSARY_NOTES_KEY, "") or "")

        # One-time migration from the former mixed TXT cache.  Nothing is discarded:
        # recognized pairs become structured dictionaries and the remaining lines
        # stay as user notes/rules.
        legacy_text = str(self.app_options.get(TRANSLATION_GLOSSARY_TEXT_KEY, "") or "")
        if legacy_text and (not auto_entries or not user_entries or not user_notes):
            migrated_auto, migrated_user, migrated_notes = split_legacy_glossary_cache(legacy_text)
            if not auto_entries:
                auto_entries = migrated_auto
            if not user_entries:
                user_entries = migrated_user
            if not user_notes:
                user_notes = migrated_notes

        dlg = GlossaryDialog(auto_entries, user_entries, user_notes, self)
        if not dlg.exec():
            self.log(self.tr_ui("↩️ 단어장 저장 취소"))
            return

        _auto_snapshot, new_user_entries, new_user_notes = dlg.get_glossary_state()
        self.app_options[TRANSLATION_USER_GLOSSARY_ENTRIES_KEY] = dict(new_user_entries)
        self.app_options[TRANSLATION_USER_GLOSSARY_NOTES_KEY] = str(new_user_notes or "")
        # The old mixed text key now keeps only free-form notes for compatibility.
        self.app_options[TRANSLATION_GLOSSARY_TEXT_KEY] = str(new_user_notes or "")
        self.app_options[TRANSLATION_GLOSSARY_PATH_KEY] = ""
        self.save_app_options_cache()
        self.sync_translation_option_cache_to_config()
        saved_message = self.tr_ui("📚 사용자 단어장 저장 완료: {count}개").format(count=f"{len(new_user_entries):,}")
        if new_user_notes:
            saved_message += self.tr_ui(" / 메모 {count}자").format(count=f"{len(new_user_notes):,}")
        self.log(saved_message)


    def capture_magic_wand_state(self):
        """요술봉 미리보기 상태를 Page-local MaskEngine에서 캡처한다."""
        try:
            active = bool(getattr(getattr(self, 'view', None), 'draw_mode', None) == 'magic_wand')
        except Exception:
            active = False
        page_idx = int(getattr(self, "idx", 0) or 0)
        if hasattr(self, "mask_engine") and self.mask_engine is not None:
            try:
                runtime = self.mask_engine.magic(page_idx)
                # Keep legacy attributes mirrored into the engine before capture.
                runtime.mask = self.magic_wand_mask.copy() if isinstance(getattr(self, 'magic_wand_mask', None), np.ndarray) else getattr(self, 'magic_wand_mask', None)
                runtime.seed = tuple(self.magic_wand_seed) if getattr(self, 'magic_wand_seed', None) else None
                runtime.seeds = [tuple(x) for x in (getattr(self, 'magic_wand_seeds', []) or [])]
                return self.mask_engine.capture_magic(page_idx, active=active)
            except Exception:
                pass
        return {
            "active": active,
            "mask": self.magic_wand_mask.copy() if isinstance(getattr(self, 'magic_wand_mask', None), np.ndarray) else None,
            "seed": tuple(self.magic_wand_seed) if getattr(self, 'magic_wand_seed', None) else None,
            "seeds": [tuple(x) for x in (getattr(self, 'magic_wand_seeds', []) or [])],
            "history": list(getattr(self, 'magic_wand_history', []) or []),
        }

    def restore_magic_wand_state(self, state):
        """Undo 복원 후 요술봉 선택/확장 상태를 화면에 다시 그린다."""
        page_idx = int(getattr(self, "idx", 0) or 0)
        if hasattr(self, "mask_engine") and self.mask_engine is not None:
            try:
                runtime = self.mask_engine.restore_magic(page_idx, state if isinstance(state, dict) else None)
                self.magic_wand_mask = runtime.mask.copy() if isinstance(runtime.mask, np.ndarray) else runtime.mask
                self.magic_wand_seeds = [tuple(x) for x in (runtime.seeds or [])]
                self.magic_wand_seed = tuple(runtime.seed) if runtime.seed else (self.magic_wand_seeds[-1] if self.magic_wand_seeds else None)
                self.magic_wand_history = runtime.history
            except Exception:
                self.magic_wand_mask = None
                self.magic_wand_seed = None
                self.magic_wand_seeds = []
        elif isinstance(state, dict):
            mask = state.get('mask')
            self.magic_wand_mask = mask.copy() if isinstance(mask, np.ndarray) else None
            self.magic_wand_seeds = [tuple(x) for x in (state.get('seeds') or [])]
            self.magic_wand_seed = tuple(state.get('seed')) if state.get('seed') else (self.magic_wand_seeds[-1] if self.magic_wand_seeds else None)
            self.magic_wand_history = list(state.get('history') or []) if isinstance(state, dict) else []
        else:
            self.clear_magic_wand_selection()
            return False
        active_state = bool(isinstance(state, dict) and state.get('active') and self.magic_wand_mask is not None)
        try:
            self._set_magic_wand_tool_restore_state(active_state)
        except Exception:
            pass
        if self.magic_wand_mask is not None:
            try:
                self.view.draw_magic_wand_preview(self.magic_wand_mask)
            except Exception:
                pass
        else:
            try:
                self.view.clear_magic_wand_preview()
            except Exception:
                pass
        return True

    def _copy_magic_state_light(self):
        """요술봉 현재 상태만 얕게 캡처한다. history 재귀 복사는 피한다."""
        try:
            return {
                "active": bool(getattr(getattr(self, "view", None), "draw_mode", None) == "magic_wand"),
                "mask": self.magic_wand_mask.copy() if isinstance(getattr(self, "magic_wand_mask", None), np.ndarray) else None,
                "seed": tuple(self.magic_wand_seed) if getattr(self, "magic_wand_seed", None) else None,
                "seeds": [tuple(x) for x in (getattr(self, "magic_wand_seeds", []) or [])],
            }
        except Exception:
            return {"active": False, "mask": None, "seed": None, "seeds": []}

    def _magic_wand_runtime(self):
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
            if hasattr(self, "mask_engine") and self.mask_engine is not None:
                return self.mask_engine.magic(page_idx)
        except Exception:
            pass
        return None

    def _sync_magic_wand_runtime_from_legacy(self):
        try:
            runtime = self._magic_wand_runtime()
            if runtime is not None:
                runtime.mask = self.magic_wand_mask.copy() if isinstance(getattr(self, 'magic_wand_mask', None), np.ndarray) else getattr(self, 'magic_wand_mask', None)
                runtime.seed = tuple(self.magic_wand_seed) if getattr(self, 'magic_wand_seed', None) else None
                runtime.seeds = [tuple(x) for x in (getattr(self, 'magic_wand_seeds', []) or [])]
                self.magic_wand_history = runtime.history
                return runtime
        except Exception:
            pass
        return None



    def _set_magic_wand_tool_restore_state(self, active):
        """Restore only the Magic Wand tool UI state without clearing command history."""
        try:
            active = bool(active)
            view = getattr(self, "view", None)
            if view is None:
                return False
            if active:
                mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 2
                if mode in (2, 3, 4):
                    view.draw_mode = "magic_wand"
                    view.setDragMode(QGraphicsView.DragMode.NoDrag)
                    try:
                        self.update_left_tool_action_states("magic_wand")
                    except Exception:
                        pass
                    try:
                        self.update_final_paint_option_bar_visibility()
                    except Exception:
                        pass
                    try:
                        self.refresh_shared_option_bar()
                    except Exception:
                        pass
                    return True
            if getattr(view, "draw_mode", None) == "magic_wand":
                view.draw_mode = None
                view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                try:
                    self.update_left_tool_action_states(None)
                except Exception:
                    pass
                try:
                    self.update_final_paint_option_bar_visibility()
                except Exception:
                    pass
                try:
                    self.refresh_shared_option_bar()
                except Exception:
                    pass
                return True
        except Exception:
            return False
        return True

    def _push_runtime_command(self, component_type, target_id, field_name, before_value, after_value, *, reason="작업", meta=None):
        """Push a small runtime/UI command into the canonical single timeline."""
        if (
            getattr(self, "_text_undo_restore_lock", False)
            or getattr(self, "_project_undo_restore_lock", False)
            or getattr(self, "_command_undo_restore_lock", False)
        ):
            return False
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return False
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
        except Exception:
            page_idx = 0
        try:
            changed = before_value != after_value
        except Exception:
            changed = True
        if not changed:
            return False
        change = FieldChange(
            target_id=str(target_id or f"{component_type}:{page_idx}"),
            field=str(field_name or "state"),
            before=copy.deepcopy(before_value),
            after=copy.deepcopy(after_value),
            component_type=str(component_type or "runtime_state"),
            page_idx=page_idx,
            meta=dict(meta or {}),
        )
        command = UndoCommand(
            reason=str(reason or "작업"),
            page_idx=page_idx,
            component_type=str(component_type or "runtime_state"),
            target_ids=[str(target_id or f"{component_type}:{page_idx}")],
            changes=[change],
            merge_key=f"{component_type}:{page_idx}:{reason}",
            meta=dict(meta or {}),
        )
        mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
        if mgr is not None and hasattr(mgr, "push_command"):
            return bool(mgr.push_command(command, clear_redo=True, source=str(component_type or reason or "runtime_command")))
        return False

    def _begin_magic_wand_runtime_command(self):
        try:
            self._pending_magic_wand_runtime_before = self._copy_magic_state_light()
        except Exception:
            self._pending_magic_wand_runtime_before = None

    def _magic_state_equal(self, left, right):
        """Compare magic-wand runtime states without numpy truth-value errors."""
        try:
            if left is right:
                return True
            if not isinstance(left, dict) or not isinstance(right, dict):
                return False
            if set(left.keys()) != set(right.keys()):
                return False
            for key in left.keys():
                a = left.get(key)
                b = right.get(key)
                if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
                    if not (isinstance(a, np.ndarray) and isinstance(b, np.ndarray)):
                        return False
                    if not np.array_equal(a, b):
                        return False
                else:
                    if a != b:
                        return False
            return True
        except Exception:
            return False

    def push_magic_wand_runtime_command(self, before_state=None, after_state=None, *, reason="요술봉 선택", extra_changes=None, meta=None):
        """Record one Magic Wand preview/fill step in the single Undo timeline."""
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
        except Exception:
            page_idx = 0
        try:
            from ysb.core.command_undo import FieldChange, UndoCommand
        except Exception:
            return False
        before_state = copy.deepcopy(before_state if isinstance(before_state, dict) else self._copy_magic_state_light())
        after_state = copy.deepcopy(after_state if isinstance(after_state, dict) else self._copy_magic_state_light())
        changes = []
        try:
            state_changed = not self._magic_state_equal(before_state, after_state)
        except Exception:
            state_changed = True
        if state_changed:
            changes.append(FieldChange(
                target_id=f"magic_wand:{page_idx}",
                field="state",
                before=before_state,
                after=after_state,
                component_type="magic_wand_runtime",
                page_idx=page_idx,
                meta=dict(meta or {}),
            ))
        for ch in list(extra_changes or []):
            try:
                changes.append(FieldChange.from_mapping(ch))
            except Exception:
                pass
        if not changes:
            return False
        command = UndoCommand(
            reason=str(reason or "요술봉 선택"),
            page_idx=page_idx,
            component_type="magic_wand_runtime",
            target_ids=[f"magic_wand:{page_idx}"],
            changes=changes,
            merge_key=f"magic_wand_runtime:{page_idx}:{reason}",
            meta=dict(meta or {}),
        )
        mgr = self.get_undo_manager() if hasattr(self, "get_undo_manager") else None
        if mgr is not None and hasattr(mgr, "push_command"):
            ok = bool(mgr.push_command(command, clear_redo=True, source="magic_wand_runtime"))
            try:
                self.audit_boundary_event(
                    "UNDO_MAGIC_WAND_COMMAND_PUSH",
                    page_idx=page_idx,
                    reason=str(reason or ""),
                    changes=len(changes),
                    before_active=bool(before_state.get("active")) if isinstance(before_state, dict) else False,
                    after_active=bool(after_state.get("active")) if isinstance(after_state, dict) else False,
                    before_has_mask=bool(isinstance(before_state.get("mask"), np.ndarray) and before_state.get("mask").size > 0) if isinstance(before_state, dict) else False,
                    after_has_mask=bool(isinstance(after_state.get("mask"), np.ndarray) and after_state.get("mask").size > 0) if isinstance(after_state, dict) else False,
                    throttle_ms=120,
                )
            except Exception:
                pass
            return ok
        return False

    def _finish_magic_wand_runtime_command(self, *, reason="요술봉 선택"):
        before = getattr(self, "_pending_magic_wand_runtime_before", None)
        self._pending_magic_wand_runtime_before = None
        if not isinstance(before, dict):
            return False
        try:
            after = self._copy_magic_state_light()
        except Exception:
            return False
        return self.push_magic_wand_runtime_command(before, after, reason=reason)

    def _apply_magic_wand_runtime_command(self, command, *, redo=False):
        changes = list(getattr(command, "changes", []) or [])
        if not changes:
            return False
        state_value = None
        mask_changes = []
        fail_reasons = []
        for change in changes:
            field_name = str(getattr(change, "field", "") or "")
            value = copy.deepcopy(getattr(change, "after", None) if redo else getattr(change, "before", None))
            if field_name == "state":
                state_value = value
            elif field_name in ("mask", "mask_state", "filled_mask"):
                mask_changes.append((change, value))
        ok = True
        # 실제 마스크 칠하기가 포함된 경우 먼저 픽셀 마스크를 되돌리고, 그 다음 preview/tool 상태를 복원한다.
        for change, value in mask_changes:
            try:
                meta = dict(getattr(change, "meta", {}) or {})
                mode = int(meta.get("mode", self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 2) or 2)
                mask_ok = bool(self._apply_magic_fill_mask_state(value, mode))
                if not mask_ok:
                    fail_reasons.append("mask_state_apply_failed")
                ok = mask_ok and ok
            except Exception as e:
                fail_reasons.append(f"mask_state_exception:{type(e).__name__}")
                ok = False
        if isinstance(state_value, dict):
            try:
                state_ok = bool(self._restore_magic_state_light(state_value))
                if not state_ok:
                    fail_reasons.append("state_restore_failed")
                ok = state_ok and ok
            except Exception as e:
                fail_reasons.append(f"state_exception:{type(e).__name__}")
                ok = False
        else:
            fail_reasons.append("missing_state")
            ok = False
        try:
            self.update_undo_redo_buttons()
            self.audit_boundary_event(
                "UNDO_MAGIC_WAND_COMMAND_APPLY",
                redo=bool(redo),
                ok=bool(ok),
                fail_reason=",".join(fail_reasons),
                has_state=isinstance(state_value, dict),
                has_mask_change=bool(mask_changes),
                state_active=bool(state_value.get("active")) if isinstance(state_value, dict) else False,
                state_has_mask=bool(isinstance(state_value, dict) and isinstance(state_value.get("mask"), np.ndarray) and state_value.get("mask").size > 0),
                draw_mode=str(getattr(getattr(self, "view", None), "draw_mode", None)),
                throttle_ms=120,
            )
        except Exception:
            pass
        return bool(ok)

    def push_magic_wand_history(self, action=None):
        # Paint/magic wand history uses the legacy lightweight runtime stack; do not push Command-Diff entries here.
        """요술봉 내부 작업 스택에 현재 상태 또는 특수 action을 넣는다.

        마스크 탭 요술봉은 픽셀 편집 전에 세심하게 선택/확장/칠하기를 반복하므로
        일반 page undo가 아니라 이 전용 runtime stack에서 한 단계씩 되돌린다.
        """
        page_idx = int(getattr(self, "idx", 0) or 0)
        try:
            # 새 요술봉 조작이 들어오면 redo 갈래는 끊는다.
            self.magic_wand_redo_history = []
        except Exception:
            pass

        runtime = self._sync_magic_wand_runtime_from_legacy()
        if runtime is not None:
            try:
                if isinstance(action, dict):
                    item = dict(action)
                    # numpy payload는 직접 copy해서 보존한다.
                    for key in ("before_mask", "after_mask"):
                        if isinstance(item.get(key), np.ndarray):
                            item[key] = item[key].copy()
                    runtime.history.append(item)
                else:
                    runtime.push_history(30)
                if len(runtime.history) > 30:
                    del runtime.history[0:len(runtime.history) - 30]
                self.magic_wand_history = runtime.history
                try:
                    self.audit_boundary_event("MAGIC_WAND_HISTORY_PUSH", action=str((action or {}).get("action") if isinstance(action, dict) else "state"), history_len=len(runtime.history), page_idx=page_idx, throttle_ms=100)
                except Exception:
                    pass
                return
            except Exception:
                pass

        if isinstance(action, dict):
            item = dict(action)
            for key in ("before_mask", "after_mask"):
                if isinstance(item.get(key), np.ndarray):
                    item[key] = item[key].copy()
            self.magic_wand_history.append(item)
        else:
            mask = self.magic_wand_mask.copy() if isinstance(self.magic_wand_mask, np.ndarray) else None
            seeds = list(getattr(self, "magic_wand_seeds", []) or [])
            self.magic_wand_history.append({"active": True, "mask": mask, "seed": self.magic_wand_seed, "seeds": seeds})
        if len(self.magic_wand_history) > 30:
            self.magic_wand_history.pop(0)

    def _apply_magic_fill_mask_state(self, mask, mode):
        """요술봉 fill_mask undo/redo용 마스크 적용."""
        if mask is None:
            return False
        try:
            mode = int(mode)
        except Exception:
            mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 2
        try:
            applied = mask.copy() if isinstance(mask, np.ndarray) else mask
            color = QColor(0, 0, 255, 150) if mode == 3 else QColor(168, 93, 102, 140)
            self.view.set_user_mask_np(applied, color)
            curr = self.data.get(self.idx)
            if isinstance(curr, dict):
                self.set_active_mask(curr, applied, mode)
            try:
                self.on_view_mask_edited()
            except Exception:
                try:
                    self.schedule_deferred_view_layer_commit("mask", delay_ms=1200)
                except Exception:
                    pass
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 요술봉 마스크 상태 복원 실패: {e}")
            except Exception:
                pass
            return False

    def _restore_magic_state_light(self, state, *, preserve_history=None):
        if not isinstance(state, dict):
            state = {"active": False, "mask": None, "seed": None, "seeds": []}
        try:
            if isinstance(preserve_history, list):
                state = dict(state)
                state["history"] = preserve_history
            self.restore_magic_wand_state(state)
        except Exception:
            try:
                mask = state.get("mask")
                self.magic_wand_mask = mask.copy() if isinstance(mask, np.ndarray) else None
                self.magic_wand_seeds = [tuple(x) for x in (state.get("seeds") or [])]
                self.magic_wand_seed = tuple(state.get("seed")) if state.get("seed") else (self.magic_wand_seeds[-1] if self.magic_wand_seeds else None)
                if self.magic_wand_mask is not None:
                    self.view.draw_magic_wand_preview(self.magic_wand_mask)
                else:
                    self.view.clear_magic_wand_preview()
            except Exception:
                pass

    def undo_magic_wand_selection(self):
        page_idx = int(getattr(self, "idx", 0) or 0)
        runtime = self._magic_wand_runtime()
        history = runtime.history if runtime is not None else getattr(self, "magic_wand_history", [])
        if not history:
            self.log("⚠️ 되돌릴 요술봉 선택이 없습니다.")
            return False

        try:
            current_state = self._copy_magic_state_light()
            item = history.pop()
            redo_item = item
            if isinstance(item, dict) and item.get("action") == "fill_mask":
                before_mask = item.get("before_mask")
                mode = int(item.get("mode", self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 2) or 2)
                if not self._apply_magic_fill_mask_state(before_mask, mode):
                    history.append(item)
                    return False
                before_magic = item.get("before_magic_state") or {}
                self._restore_magic_state_light(before_magic, preserve_history=history)
                self.magic_wand_redo_history.append(redo_item)
                self.log("↩️ 요술봉 마스크 칠하기 되돌림")
            else:
                # 일반 선택/허용범위/확장 단계는 이전 preview 상태로 되돌린다.
                self.magic_wand_redo_history.append(current_state)
                self._restore_magic_state_light(item, preserve_history=history)
                self.log("↩️ 요술봉 선택 되돌림")

            try:
                if runtime is not None:
                    self.magic_wand_history = runtime.history
                self.update_undo_redo_buttons()
                self.audit_boundary_event("MAGIC_WAND_UNDO", action=str(item.get("action") if isinstance(item, dict) else "state"), history_len=len(getattr(self, "magic_wand_history", []) or []), redo_len=len(getattr(self, "magic_wand_redo_history", []) or []), page_idx=page_idx, throttle_ms=100)
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 요술봉 되돌리기 실패: {e}")
            except Exception:
                pass
            return False

    def redo_magic_wand_selection(self):
        page_idx = int(getattr(self, "idx", 0) or 0)
        redo = getattr(self, "magic_wand_redo_history", []) or []
        if not redo:
            self.log("⚠️ 다시 실행할 요술봉 작업이 없습니다.")
            return False
        runtime = self._sync_magic_wand_runtime_from_legacy()
        history = runtime.history if runtime is not None else getattr(self, "magic_wand_history", [])
        try:
            item = redo.pop()
            if isinstance(item, dict) and item.get("action") == "fill_mask":
                after_mask = item.get("after_mask")
                mode = int(item.get("mode", self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 2) or 2)
                if not self._apply_magic_fill_mask_state(after_mask, mode):
                    redo.append(item)
                    return False
                # 다시 칠한 뒤에는 선택 preview가 사라진 상태를 유지하되, undo용 action은 history에 남긴다.
                self.clear_magic_wand_selection(clear_history=False)
                history.append(item)
                self.log("↷ 요술봉 마스크 칠하기 다시 실행")
            else:
                current_state = self._copy_magic_state_light()
                history.append(current_state)
                self._restore_magic_state_light(item, preserve_history=history)
                self.log("↷ 요술봉 선택 다시 실행")
            if len(history) > 30:
                del history[0:len(history) - 30]
            if runtime is not None:
                self.magic_wand_history = runtime.history
            else:
                self.magic_wand_history = history
            try:
                self.update_undo_redo_buttons()
                self.audit_boundary_event("MAGIC_WAND_REDO", action=str(item.get("action") if isinstance(item, dict) else "state"), history_len=len(getattr(self, "magic_wand_history", []) or []), redo_len=len(getattr(self, "magic_wand_redo_history", []) or []), page_idx=page_idx, throttle_ms=100)
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 요술봉 다시 실행 실패: {e}")
            except Exception:
                pass
            return False

    def clear_magic_wand_selection(self, clear_history=True):
        page_idx = int(getattr(self, "idx", 0) or 0)
        if hasattr(self, "mask_engine") and self.mask_engine is not None:
            try:
                self.mask_engine.clear_magic(page_idx, clear_history=bool(clear_history))
            except Exception:
                pass
        self.magic_wand_mask = None
        self.magic_wand_seed = None
        self.magic_wand_seeds = []
        if clear_history:
            self.magic_wand_history = []
            self.magic_wand_redo_history = []
        else:
            try:
                runtime = self._magic_wand_runtime()
                self.magic_wand_history = runtime.history if runtime is not None else getattr(self, "magic_wand_history", [])
            except Exception:
                pass
        if hasattr(self, "view") and hasattr(self.view, "clear_magic_wand_preview"):
            self.view.clear_magic_wand_preview()

    def current_magic_source_image(self):
        # 최종결과 탭의 요술봉은 실제 최종 화면 기준으로 영역을 판정한다.
        try:
            if hasattr(self, "cb_mode") and self.cb_mode.currentIndex() == 4:
                rendered = self.render_final_scene_for_magic_wand()
                if rendered is not None:
                    return rendered
        except Exception:
            pass
        return self.get_source_display_image(self.idx)

    def render_final_scene_for_magic_wand(self):
        """현재 최종결과 scene을 요술봉 판정용 RGB 이미지로 렌더링한다."""
        try:
            scene = getattr(getattr(self, "view", None), "scene", None)
            if scene is None:
                return None
            rect = scene.sceneRect()
            w = max(1, int(round(rect.width())))
            h = max(1, int(round(rect.height())))
            qimg = QImage(w, h, QImage.Format.Format_ARGB32)
            qimg.fill(Qt.GlobalColor.transparent)
            painter = QPainter(qimg)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            # 미리보기 overlay가 있다면 판정에 섞이지 않도록 잠시 숨긴다.
            hidden = []
            try:
                for item in list(getattr(self.view, "magic_preview_items", []) or []):
                    if item is not None and item.isVisible():
                        item.setVisible(False)
                        hidden.append(item)
            except Exception:
                hidden = []
            try:
                scene.render(painter, QRectF(0, 0, w, h), rect)
            finally:
                painter.end()
                for item in hidden:
                    try:
                        item.setVisible(True)
                    except Exception:
                        pass
            qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
            ptr = qimg.bits()
            ptr.setsize(qimg.sizeInBytes())
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, qimg.bytesPerLine() // 4, 4))[:, :w, :4].copy()
            # 투명 영역은 흰 배경처럼 처리한다. 최종결과 배경이 깔린 경우엔 보통 alpha가 이미 255다.
            alpha = arr[:, :, 3:4].astype(np.float32) / 255.0
            rgb = arr[:, :, :3].astype(np.float32)
            bg = np.full_like(rgb, 255.0)
            comp = (rgb * alpha + bg * (1.0 - alpha)).astype(np.uint8)
            return comp
        except Exception:
            return None

    def set_mask_wrap_shape(self, shape, silent=False):
        shape = "free" if str(shape) == "free" else "rect"
        try:
            self.view.mask_wrap_shape = shape
            self.view.clear_mask_wrap_preview()
        except Exception:
            pass
        for btn, active in ((getattr(self, "btn_mask_wrap_rect", None), shape == "rect"), (getattr(self, "btn_mask_wrap_free", None), shape == "free")):
            if btn is None:
                continue
            try:
                btn.blockSignals(True)
                btn.setChecked(active)
                btn.blockSignals(False)
                if active:
                    btn.setStyleSheet("font-weight:bold; background:#8A4A52; color:white;")
                else:
                    btn.setStyleSheet("opacity:0.7;")
            except Exception:
                pass
        if not silent:
            if shape == "rect":
                self.log("🩹 마스크 랩핑 모드: 사각형")
            else:
                self.log("🩹 마스크 랩핑 모드: 자유형")

    def set_mask_cut_shape(self, shape, silent=False):
        shape = "free" if str(shape) == "free" else "rect"
        try:
            self.view.mask_cut_shape = shape
            self.view.clear_mask_cut_preview()
        except Exception:
            pass
        for btn, active in ((getattr(self, "btn_mask_cut_rect", None), shape == "rect"), (getattr(self, "btn_mask_cut_free", None), shape == "free")):
            if btn is None:
                continue
            try:
                btn.blockSignals(True)
                btn.setChecked(active)
                btn.blockSignals(False)
                if active:
                    btn.setStyleSheet("font-weight:bold; background:#c2410c; color:white;")
                else:
                    btn.setStyleSheet("opacity:0.7;")
            except Exception:
                pass
        if not silent:
            if shape == "rect":
                self.log(self.tr_ui("🔪 마스크 커팅 모드: 사각형"))
            else:
                self.log(self.tr_ui("🔪 마스크 커팅 모드: 자유형"))

    def set_area_paint_shape(self, shape, silent=False):
        shape = "free" if str(shape) == "free" else "rect"
        try:
            self.view.area_paint_shape = shape
            self.view.clear_area_paint_preview()
        except Exception:
            pass
        for btn, active in ((getattr(self, "btn_area_paint_rect", None), shape == "rect"), (getattr(self, "btn_area_paint_free", None), shape == "free")):
            if btn is None:
                continue
            try:
                btn.blockSignals(True)
                btn.setChecked(active)
                btn.blockSignals(False)
                if active:
                    btn.setStyleSheet("font-weight:bold; background:#7c3aed; color:white;")
                else:
                    btn.setStyleSheet("opacity:0.7;")
            except Exception:
                pass
        if not silent:
            if shape == "rect":
                self.log(self.tr_ui("▦ 영역 페인팅 모드: 사각형"))
            else:
                self.log(self.tr_ui("▦ 영역 페인팅 모드: 자유형"))

    def apply_mask_wrapping(self, region_mask):
        """선택한 영역 안의 분리된 마스크 덩어리들을 하나의 채움 영역으로 감싸준다."""
        try:
            mode = int(self.cb_mode.currentIndex())
        except Exception:
            mode = -1
        if mode not in (2, 3):
            self.log("⚠️ 마스크 랩핑은 텍스트 마스크/페인팅 마스크 탭에서 사용하세요.")
            self.update_left_tool_action_states()
            return
        if region_mask is None:
            self.log("⚠️ 마스크 랩핑 영역이 비어 있습니다.")
            return
        before = self.view.get_mask_np()
        if before is None:
            self.log(self.tr_ui("⚠️ 현재 탭에 마스크 레이어가 없습니다."))
            return

        try:
            mask = (before > 0).astype(np.uint8) * 255
            region = (region_mask > 0).astype(np.uint8) * 255
            if mask.shape[:2] != region.shape[:2]:
                region = cv2.resize(region, (mask.shape[1], mask.shape[0]), interpolation=cv2.INTER_NEAREST)

            # 선택 영역 안에 실제로 들어온 마스크 조각만 대상으로 삼는다.
            inside = cv2.bitwise_and(mask, region)
            num, labels, stats, _ = cv2.connectedComponentsWithStats(inside, 8)
            comps = [i for i in range(1, num) if int(stats[i, cv2.CC_STAT_AREA]) > 0]
            if len(comps) < 2:
                self.log("⚠️ 선택한 영역 안에 랩핑할 마스크가 2개 이상 필요합니다.")
                return

            ys, xs = np.where(inside > 0)
            if len(xs) == 0 or len(ys) == 0:
                self.log("⚠️ 마스크 랩핑 영역 안에서 마스크를 찾지 못했습니다.")
                return

            try:
                self.commit_current_page_ui_to_data(include_mask=True)
                self.push_project_undo("마스크 랩핑")
            except Exception:
                pass

            x1, x2 = int(xs.min()), int(xs.max())
            y1, y2 = int(ys.min()), int(ys.max())
            fill = np.zeros_like(mask, dtype=np.uint8)
            cv2.rectangle(fill, (x1, y1), (x2, y2), 255, thickness=-1)
            # 사용자가 잡은 영역 밖은 절대 건드리지 않는다.
            fill = cv2.bitwise_and(fill, region)
            wrapped = cv2.bitwise_or(mask, fill)

            if np.array_equal(wrapped, mask):
                self.log("⚠️ 마스크 랩핑으로 추가될 영역이 없습니다.")
                return

            color = QColor(0, 0, 255, 150) if mode == 3 else QColor(168, 93, 102, 140)
            self.view.set_user_mask_np(wrapped, color)
            self.on_view_mask_edited()
            self.log(f"🩹 마스크 랩핑 완료: {len(comps)}개 마스크 덩어리를 1개 영역으로 감쌈")
        except Exception as e:
            self.log(f"⚠️ 마스크 랩핑 실패: {e}")

    def apply_mask_cutting(self, region_mask):
        """선택 영역 내부는 보존하고, 선택 영역 바깥 경계 주변의 마스크를 지정 px만큼 잘라낸다."""
        try:
            mode = int(self.cb_mode.currentIndex())
        except Exception:
            mode = -1
        if mode not in (2, 3):
            self.log(self.tr_ui("⚠️ 마스크 커팅은 텍스트 마스크/페인팅 마스크 탭에서 사용하세요."))
            self.update_left_tool_action_states()
            return
        if region_mask is None:
            self.log(self.tr_ui("⚠️ 마스크 커팅 영역이 비어 있습니다."))
            return

        before = self.view.get_mask_np()
        if before is None:
            self.log(self.tr_ui("⚠️ 현재 탭에 마스크 레이어가 없습니다."))
            return

        try:
            cut_px = int(getattr(self, "sb_mask_cut_px", None).value()) if hasattr(self, "sb_mask_cut_px") else 8
        except Exception:
            cut_px = 8
        cut_px = max(1, min(200, int(cut_px)))

        try:
            mask = (before > 0).astype(np.uint8) * 255
            region = (region_mask > 0).astype(np.uint8) * 255
            if mask.shape[:2] != region.shape[:2]:
                region = cv2.resize(region, (mask.shape[1], mask.shape[0]), interpolation=cv2.INTER_NEAREST)

            kernel_size = cut_px * 2 + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            expanded = cv2.dilate(region, kernel, iterations=1)
            cut_band = cv2.bitwise_and(expanded, cv2.bitwise_not(region))

            if np.count_nonzero(cut_band) <= 0:
                self.log(self.tr_ui("⚠️ 마스크 커팅으로 제거할 외곽 영역이 없습니다."))
                return

            target_pixels = cv2.bitwise_and(mask, cut_band)
            removed = int(np.count_nonzero(target_pixels))
            if removed <= 0:
                self.log(self.tr_ui("⚠️ 지정한 커팅 영역에 제거할 마스크가 없습니다."))
                return

            try:
                self.commit_current_page_ui_to_data(include_mask=True)
                self.push_project_undo("마스크 커팅")
            except Exception:
                pass

            cut = mask.copy()
            cut[cut_band > 0] = 0

            if np.array_equal(cut, mask):
                self.log(self.tr_ui("⚠️ 마스크 커팅으로 변경된 영역이 없습니다."))
                return

            color = QColor(0, 0, 255, 150) if mode == 3 else QColor(168, 93, 102, 140)
            self.view.set_user_mask_np(cut, color)
            self.on_view_mask_edited()
            lang = normalize_ui_language(getattr(self, "ui_language", None) or current_ui_language())
            if lang == LANG_EN:
                self.log(f"🔪 Mask cutting complete: outer {cut_px}px / {removed} px removed")
            else:
                self.log(f"🔪 마스크 커팅 완료: 외곽 {cut_px}px / {removed} px 제거")
        except Exception as e:
            lang = normalize_ui_language(getattr(self, "ui_language", None) or current_ui_language())
            if lang == LANG_EN:
                self.log(f"⚠️ Mask cutting failed: {e}")
            else:
                self.log(f"⚠️ 마스크 커팅 실패: {e}")

    def magic_wand_pick(self, x, y):
        if self.cb_mode.currentIndex() not in [2, 3, 4]:
            self.log("⚠️ 요술봉은 마스크 탭 또는 최종결과 탭에서만 사용할 수 있습니다.")
            return

        img = self.current_magic_source_image()
        if img is None:
            self.log("⚠️ 요술봉 기준 이미지가 없습니다.")
            return

        h, w = img.shape[:2]
        if x < 0 or y < 0 or x >= w or y >= h:
            return

        tol = int(self.sb_magic_tolerance.value()) if hasattr(self, "sb_magic_tolerance") else 20
        # 요술봉 선택은 프로젝트 편집이 아니라 현재 페이지의 임시 선택 상태다.
        # ProjectUndo에 넣지 않고 MaskEngine의 magic-wand history로만 관리한다.
        self.push_magic_wand_history()
        self.magic_wand_seed = (int(x), int(y))
        if not hasattr(self, "magic_wand_seeds"):
            self.magic_wand_seeds = []
        self.magic_wand_seeds.append(self.magic_wand_seed)

        new_mask = self.build_magic_wand_mask(img, self.magic_wand_seed, tol)
        if self.magic_wand_mask is None:
            self.magic_wand_mask = new_mask
        else:
            self.magic_wand_mask = cv2.bitwise_or(self.magic_wand_mask.astype(np.uint8), new_mask.astype(np.uint8))

        try:
            if hasattr(self, "mask_engine") and self.mask_engine is not None:
                self.mask_engine.set_magic_mask(int(getattr(self, "idx", 0) or 0), self.magic_wand_mask, seeds=self.magic_wand_seeds, seed=self.magic_wand_seed)
        except Exception:
            pass
        self.view.draw_magic_wand_preview(self.magic_wand_mask)
        try:
            self._finish_magic_wand_runtime_command(reason="요술봉 선택 추가")
        except Exception:
            pass
        try:
            self.update_undo_redo_buttons()
        except Exception:
            pass
        self.log(f"요술봉 선택 추가: x={x}, y={y}, 허용범위={tol}, 누적={len(self.magic_wand_seeds)}")

    def build_magic_wand_mask(self, img, seed, tolerance):
        """
        Photoshop 요술봉에 가까운 기본 동작:
        클릭 픽셀과 RGB/BGR 값이 비슷하고, 서로 연결된 영역만 flood fill로 선택한다.
        """
        h, w = img.shape[:2]
        work_img = img.copy()
        flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
        tol = max(0, min(255, int(tolerance)))
        diff = (tol, tol, tol)
        flags = 8 | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)

        try:
            cv2.floodFill(work_img, flood_mask, tuple(seed), (0, 255, 255), diff, diff, flags)
        except Exception as e:
            self.log(f"⚠️ 요술봉 선택 실패: {e}")
            return np.zeros((h, w), dtype=np.uint8)

        raw = flood_mask[1:h + 1, 1:w + 1].copy()
        return self.fill_magic_wand_outer_region(raw)

    def fill_magic_wand_outer_region(self, mask):
        """요술봉 공통 후처리: 외부 외곽선을 기준으로 내부 구멍까지 채운다.

        도넛처럼 내부가 비어 있는 선택도 바깥 contour를 기준으로 하나의 면으로 칠한다.
        마스크 탭과 최종결과 탭이 같은 판정 결과를 공유한다.
        """
        try:
            if mask is None:
                return mask
            m = (mask.astype(np.uint8) > 0).astype(np.uint8) * 255
            contours, _hier = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return m
            out = np.zeros_like(m, dtype=np.uint8)
            cv2.drawContours(out, contours, -1, 255, thickness=-1)
            return out
        except Exception:
            try:
                return mask.astype(np.uint8)
            except Exception:
                return mask

    def on_magic_wand_tolerance_changed(self, value):
        # 허용범위를 바꾸면 누적 클릭 지점 전체를 기준으로 미리보기를 다시 계산한다.
        # 단, 영역확장 후 허용범위를 바꾸면 확장 상태는 재계산된다.
        if self.view.draw_mode != 'magic_wand':
            return
        seeds = list(getattr(self, "magic_wand_seeds", []) or [])
        if not seeds:
            return
        # 요술봉 허용범위 변경은 실제 프로젝트/마스크 편집이 아니라
        # 현재 요술봉 미리보기 안의 단계다. 전체 PageUndo가 아니라
        # MagicWandRuntime history에만 쌓아 Ctrl+Z가 순차적으로 되돌아가게 한다.
        self.push_magic_wand_history()
        img = self.current_magic_source_image()
        if img is None:
            return

        merged = None
        for seed in seeds:
            part = self.build_magic_wand_mask(img, seed, int(value))
            merged = part if merged is None else cv2.bitwise_or(merged.astype(np.uint8), part.astype(np.uint8))

        self.magic_wand_mask = merged
        try:
            if hasattr(self, "mask_engine") and self.mask_engine is not None:
                self.mask_engine.set_magic_mask(int(getattr(self, "idx", 0) or 0), self.magic_wand_mask, seeds=self.magic_wand_seeds, seed=self.magic_wand_seed)
        except Exception:
            pass
        self.view.draw_magic_wand_preview(self.magic_wand_mask)
        try:
            self._finish_magic_wand_runtime_command(reason="요술봉 허용범위 변경")
        except Exception:
            pass
        try:
            self.update_undo_redo_buttons()
        except Exception:
            pass

    def expand_magic_wand_selection(self):
        if self.magic_wand_mask is None:
            self.log("⚠️ 먼저 요술봉으로 영역을 선택하세요.")
            return

        amount = int(self.sb_magic_expand.value()) if hasattr(self, "sb_magic_expand") else 3
        if amount <= 0:
            self.view.draw_magic_wand_preview(self.magic_wand_mask)
            return

        # 영역 확장도 요술봉 내부 미리보기 단계다. Project/Page undo에 넣으면
        # Ctrl+Z 순서가 꼬여 선택 전체가 한 번에 사라질 수 있으므로
        # 요술봉 내부 history에만 직전 상태를 저장한다.
        self.push_magic_wand_history()
        kernel_size = amount * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        self.magic_wand_mask = cv2.dilate(self.magic_wand_mask, kernel, iterations=1)
        try:
            if hasattr(self, "mask_engine") and self.mask_engine is not None:
                self.mask_engine.set_magic_mask(int(getattr(self, "idx", 0) or 0), self.magic_wand_mask, seeds=self.magic_wand_seeds, seed=self.magic_wand_seed)
        except Exception:
            pass
        self.view.draw_magic_wand_preview(self.magic_wand_mask)
        try:
            self._finish_magic_wand_runtime_command(reason="요술봉 영역확장")
        except Exception:
            pass
        try:
            self.update_undo_redo_buttons()
        except Exception:
            pass
        self.log(f"요술봉 영역확장: {amount}px")

    def fill_magic_wand_mask(self):
        if self.magic_wand_mask is None:
            self.log("⚠️ 먼저 요술봉으로 영역을 선택하세요.")
            return

        mode = self.cb_mode.currentIndex()
        if mode == 4:
            return self.fill_magic_wand_final_paint()

        if mode not in [2, 3]:
            self.log("⚠️ 마스킹 칠하기는 마스크 탭에서만 가능합니다.")
            return

        if self.view.user_mask_item is None:
            self.log(self.tr_ui("⚠️ 현재 탭에 마스크 레이어가 없습니다."))
            return

        try:
            self.commit_current_page_ui_to_data(include_mask=True)
        except Exception:
            pass

        before = self.view.get_mask_np()
        if before is None:
            before = np.zeros_like(self.magic_wand_mask, dtype=np.uint8)
        before = before.copy() if isinstance(before, np.ndarray) else before
        before_magic_state = self.capture_magic_wand_state()

        mask = self.fill_magic_wand_outer_region(self.magic_wand_mask).astype(np.uint8)
        combined = cv2.bitwise_or(before.astype(np.uint8), mask)
        color = QColor(0, 0, 255, 150) if mode == 3 else QColor(168, 93, 102, 140)
        self.view.set_user_mask_np(combined, color)
        try:
            curr = self.data.get(self.idx)
            if isinstance(curr, dict):
                self.set_active_mask(curr, combined, mode)
        except Exception:
            pass

        self.push_magic_wand_history({
            "action": "fill_mask",
            "mode": int(mode),
            "before_mask": before.copy() if isinstance(before, np.ndarray) else before,
            "after_mask": combined.copy() if isinstance(combined, np.ndarray) else combined,
            "before_magic_state": before_magic_state,
        })
        # 칠한 뒤 preview는 지우되, 요술봉 내부 history는 유지한다.
        self.clear_magic_wand_selection(clear_history=False)
        self.on_view_mask_edited()
        self.log("요술봉 선택 영역을 현재 마스크에 칠했습니다.")

    def fill_magic_wand_final_paint(self):
        if self.magic_wand_mask is None:
            self.log("⚠️ 먼저 요술봉으로 영역을 선택하세요.")
            return False
        if self.cb_mode.currentIndex() != 4:
            return False
        if not hasattr(self, "view") or not hasattr(self.view, "apply_magic_wand_final_paint"):
            return False
        try:
            self.commit_current_page_ui_to_data(include_mask=False)
        except Exception:
            pass
        # 실제 Undo는 viewer.apply_magic_wand_final_paint()가 만든 QPixmap patch history로 처리한다.
        ok = False
        try:
            mask = self.fill_magic_wand_outer_region(self.magic_wand_mask).astype(np.uint8)
            ok = bool(self.view.apply_magic_wand_final_paint(mask))
        except Exception as e:
            self.log(f"⚠️ 요술봉 영역 칠하기 실패: {e}")
            ok = False
        if ok:
            self.clear_magic_wand_selection()
            try:
                if hasattr(self, "schedule_deferred_view_layer_commit"):
                    self.schedule_deferred_view_layer_commit("final_paint", delay_ms=1200)
                elif hasattr(self, "on_final_paint_edited"):
                    self.on_final_paint_edited()
            except Exception:
                pass
            self.log("요술봉 선택 영역을 현재 팔레트 색상으로 칠했습니다.")
        return ok


    def _sample_color_from_scene(self, scene, x, y):
        """Render a 1x1 scene pixel so eyedropper follows the visible result."""
        if scene is None:
            return None
        try:
            scene_rect = scene.sceneRect()
            if not scene_rect.contains(float(x), float(y)):
                return None
            qimg = QImage(1, 1, QImage.Format.Format_ARGB32)
            qimg.fill(Qt.GlobalColor.transparent)
            painter = QPainter(qimg)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            scene.render(painter, QRectF(0, 0, 1, 1), QRectF(float(x), float(y), 1, 1))
            painter.end()
            color = QColor(qimg.pixel(0, 0))
            if not color.isValid():
                return None
            return color
        except Exception:
            try:
                painter.end()
            except Exception:
                pass
            return None

    def _apply_final_paint_eyedropper_color(self, color, *, source_label="", global_pos=None):
        if color is None or not color.isValid():
            self.log(self.tr_ui("⚠️ 스포이드로 색상을 가져오지 못했습니다."))
            return False
        hex_color = color.name(QColor.NameFormat.HexRgb).upper()
        self.final_paint_color = hex_color
        try:
            QApplication.clipboard().setText(hex_color)
        except Exception:
            pass
        try:
            self.update_color_button_styles()
        except Exception:
            pass
        self._show_eyedropper_color_feedback(hex_color, source_label=source_label, global_pos=global_pos)
        self.log(f"🎯 {self.tr_ui('스포이드 색상 적용')}: {hex_color} ({self.tr_ui('클립보드에 복사됨')})")
        return True

    def pick_final_paint_color_from_scene(self, x, y, global_pos=None):
        color = self._sample_color_from_scene(getattr(getattr(self, "view", None), "scene", None), x, y)
        return self._apply_final_paint_eyedropper_color(color, source_label=self.tr_ui("최종화면"), global_pos=global_pos)

    def pick_final_paint_color_from_source_scene(self, x, y, global_pos=None):
        color = self._sample_color_from_scene(getattr(self, "source_compare_scene", None), x, y)
        return self._apply_final_paint_eyedropper_color(color, source_label=self.tr_ui("원본 비교창"), global_pos=global_pos)

    def _show_eyedropper_color_feedback(self, hex_color, *, source_label="", global_pos=None):
        try:
            QToolTip.hideText()
        except Exception:
            pass
        try:
            popup = getattr(self, "_eyedropper_color_popup", None)
            if popup is None:
                popup = QLabel(None)
                popup.setObjectName("ysbEyedropperColorPopup")
                popup.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
                popup.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                popup.setTextFormat(Qt.TextFormat.RichText)
                popup.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._eyedropper_color_popup = popup
            safe_hex = str(hex_color or "#000000").upper()
            c = QColor(safe_hex)
            text_fg = "#111111" if c.isValid() and c.lightness() > 170 else "#ffffff"
            popup.setText(
                "<div style='white-space:nowrap;'>"
                f"<span style='display:inline-block; width:30px; height:20px; "
                f"background:{safe_hex}; border:1px solid #111111; vertical-align:middle;'></span> "
                f"<b>{safe_hex}</b>"
                "</div>"
            )
            popup.setStyleSheet(
                "QLabel#ysbEyedropperColorPopup { "
                f"background:{safe_hex}; color:{text_fg}; border:1px solid #111111; "
                "border-radius:0px; padding:4px 7px; font-weight:700; }"
            )
            popup.adjustSize()
            pos = global_pos if global_pos is not None else QCursor.pos()
            try:
                pos = QPoint(pos)
            except Exception:
                pos = QCursor.pos()
            # 커서 위에 색상칩+HEX만 표시한다. 작업 지점은 가리지 않도록 살짝 띄운다.
            popup.move(pos + QPoint(10, -popup.height() - 12))
            popup.show()
            popup.raise_()
        except Exception:
            pass

    def _hide_eyedropper_color_feedback(self):
        try:
            QToolTip.hideText()
        except Exception:
            pass
        try:
            popup = getattr(self, "_eyedropper_color_popup", None)
            if popup is not None:
                popup.hide()
        except Exception:
            pass

    def adjust_magic_tolerance(self, delta):
        if not hasattr(self, "sb_magic_tolerance"):
            return
        self.sb_magic_tolerance.setValue(max(0, min(255, self.sb_magic_tolerance.value() + int(delta))))

    def adjust_magic_expand_range(self, delta):
        if not hasattr(self, "sb_magic_expand"):
            return
        self.sb_magic_expand.setValue(max(0, min(200, self.sb_magic_expand.value() + int(delta))))

    def _detach_source_compare_controls(self):
        try:
            controls = getattr(self, "source_compare_controls", None)
            if controls is None:
                return
            parent = controls.parentWidget()
            if parent is not None and parent.layout() is not None:
                try:
                    parent.layout().removeWidget(controls)
                except Exception:
                    pass
            try:
                controls.hide()
            except Exception:
                pass
            controls.setParent(None)
        except Exception:
            pass

    def _add_source_compare_controls_to_layout(self, layout):
        if bool(getattr(self, "maker_ui_cleanup_enabled", False)) or bool(getattr(self, "tktool_phase1_enabled", False)):
            try:
                controls = getattr(self, "source_compare_controls", None)
                if controls is not None:
                    controls.hide()
                    controls.setVisible(False)
            except Exception:
                pass
            return False
        if layout is None or not hasattr(self, "source_compare_controls"):
            return False
        try:
            self._detach_source_compare_controls()
            # stretch 뒤에 붙여 같은 줄의 오른쪽 끝에 놓는다.
            layout.addWidget(self.source_compare_controls)
            self.source_compare_controls.show()
            return True
        except Exception:
            return False

    def place_source_compare_controls(self):
        """원본 비교 컨트롤은 공유 옵션바의 우측 고정 영역에만 배치한다."""
        if bool(getattr(self, "maker_ui_cleanup_enabled", False)) or bool(getattr(self, "tktool_phase1_enabled", False)):
            for _name in ("cb_text_effect_preview", "source_compare_controls", "source_compare_bar", "shared_option_bar"):
                try:
                    _w = getattr(self, _name, None)
                    if _w is not None:
                        _w.hide()
                        _w.setVisible(False)
                        if _name == "shared_option_bar":
                            try:
                                _w.setFixedHeight(0)
                                _w.setMaximumHeight(0)
                            except Exception:
                                pass
                except Exception:
                    pass
            return
        try:
            right_layout = getattr(self, "shared_option_right_layout", None)
            controls = getattr(self, "source_compare_controls", None)
            effect_cb = getattr(self, "cb_text_effect_preview", None)
            if right_layout is None:
                return
            # 우측 고정 영역은 항상 [텍스트 이펙트 미리보기]를 맨 오른쪽 계열에 둔다.
            # 원본 비교창이 켜지면 체크박스 오른쪽에 비교창 컨트롤을 붙여 자연스럽게 왼쪽으로 밀린다.
            while right_layout.count():
                item = right_layout.takeAt(0)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    try:
                        widget.hide()
                    except Exception:
                        pass
                    widget.setParent(None)
            if effect_cb is not None:
                try:
                    right_layout.addWidget(effect_cb)
                    effect_cb.show()
                except Exception:
                    pass
            visible = self.source_compare_is_visible() if hasattr(self, "source_compare_is_visible") else False
            if visible and controls is not None:
                right_layout.addWidget(controls)
                controls.show()
            elif controls is not None:
                controls.hide()
            if hasattr(self, "source_compare_bar"):
                self.source_compare_bar.hide()
            if hasattr(self, "shared_option_bar"):
                self.shared_option_bar.show()
        except Exception:
            pass

    def _hide_legacy_option_bars(self):
        for bar_name in (
            "area_paint_bar", "magic_wand_bar", "mask_wrap_bar", "mask_cut_bar",
            "ocr_region_bar", "final_paint_option_bar", "final_edit_bar",
            "source_compare_bar",
        ):
            try:
                bar = getattr(self, bar_name, None)
                if bar is not None:
                    bar.hide()
            except Exception:
                pass

    def _clear_shared_option_left(self):
        layout = getattr(self, "shared_option_left_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                # 출력/탭 전환 중 레이아웃에서 빠진 버튼이 부모 없는 독립 위젯으로
                # 좌상단에 떠버리는 것을 막기 위해 먼저 숨긴 뒤 분리한다.
                try:
                    widget.hide()
                except Exception:
                    pass
                widget.setParent(None)

    def _shared_add_label(self, text):
        try:
            label = QLabel(str(text))
            self.shared_option_left_layout.addWidget(label)
            return label
        except Exception:
            return None

    def refresh_shared_option_bar(self):
        """항상 보이는 한 줄 공유 옵션바의 왼쪽 도구 영역을 현재 상태에 맞게 재구성한다."""
        if bool(getattr(self, "maker_ui_cleanup_enabled", False)) or bool(getattr(self, "tktool_phase1_enabled", False)):
            try:
                self._hide_legacy_option_bars()
            except Exception:
                pass
            try:
                self._clear_shared_option_left()
            except Exception:
                pass
            for _name in ("cb_text_effect_preview", "source_compare_controls", "source_compare_bar", "shared_option_bar"):
                try:
                    _w = getattr(self, _name, None)
                    if _w is not None:
                        _w.hide()
                        _w.setVisible(False)
                        if _name == "shared_option_bar":
                            try:
                                _w.setFixedHeight(0)
                                _w.setMaximumHeight(0)
                            except Exception:
                                pass
                except Exception:
                    pass
            return
        if getattr(self, "_export_rendering_guard", False):
            # 출력 렌더링은 사용자 조작이 아니므로 텍스트 선택용 옵션 위젯을
            # 새로 붙이지 않는다. 이미 붙어 있던 위젯도 숨겨 좌상단 탈출을 막는다.
            try:
                self._hide_legacy_option_bars()
                self._clear_shared_option_left()
                if hasattr(self, "shared_option_bar"):
                    self.shared_option_bar.show()
                if hasattr(self, "place_source_compare_controls"):
                    self.place_source_compare_controls()
            except Exception:
                pass
            return
        if getattr(self, "_suppress_shared_option_refresh", False):
            return
        if not hasattr(self, "shared_option_bar") or not hasattr(self, "shared_option_left_layout"):
            return
        self._hide_legacy_option_bars()
        self._clear_shared_option_left()
        try:
            self.shared_option_bar.show()
        except Exception:
            pass

        mode = self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 0
        draw_mode = getattr(getattr(self, "view", None), "draw_mode", None)

        def add_widget(widget):
            try:
                if widget is not None:
                    self.shared_option_left_layout.addWidget(widget)
                    widget.show()
            except Exception:
                pass

        try:
            selected_text = self.selected_text_items() if hasattr(self, "selected_text_items") else []
        except Exception:
            selected_text = []

        populated = False
        try:
            if mode == 4 and draw_mode is None and selected_text:
                self._shared_add_label("불투명도")
                add_widget(getattr(self, "sb_text_opacity", None))
                add_widget(getattr(self, "btn_text_effect_gradient", None))
                add_widget(getattr(self, "btn_text_effect_transform", None))
                add_widget(getattr(self, "btn_text_effect_skew", None))
                add_widget(getattr(self, "btn_text_effect_trapezoid", None))
                add_widget(getattr(self, "btn_text_effect_arc", None))
                populated = True
            elif mode in (2, 3, 4) and draw_mode in ("draw", "erase"):
                self._shared_add_label(self.tr_ui("브러시"))
                self._shared_add_label(self.tr_ui("크기"))
                add_widget(getattr(self, "sb_brush_size", None))
                if mode == 4:
                    self._shared_add_label(self.tr_ui("불투명도"))
                    add_widget(getattr(self, "sb_final_paint_opacity", None))
                populated = True
            elif mode in (2, 3, 4) and draw_mode == "area_paint":
                self._shared_add_label(self.tr_ui("영역 마스킹") if mode in (2, 3) else self.tr_ui("영역 페인팅"))
                add_widget(getattr(self, "btn_area_paint_rect", None))
                add_widget(getattr(self, "btn_area_paint_free", None))
                self._shared_add_label(
                    self.tr_ui("선택한 영역을 현재 마스크에 채웁니다.")
                    if mode in (2, 3)
                    else self.tr_ui("선택한 영역을 현재 최종 페인팅 색상으로 채웁니다.")
                )
                populated = True
            elif mode in (2, 3, 4) and draw_mode == "magic_wand":
                self._shared_add_label("요술봉")
                self._shared_add_label("RGB 허용범위")
                add_widget(getattr(self, "sb_magic_tolerance", None))
                add_widget(getattr(self, "btn_magic_expand", None))
                self._shared_add_label("확장 범위")
                add_widget(getattr(self, "sb_magic_expand", None))
                try:
                    if getattr(self, "btn_magic_fill", None) is not None:
                        self.btn_magic_fill.setText(self.tr_ui("영역 칠하기") if mode == 4 else self.tr_ui("마스킹 칠하기"))
                except Exception:
                    pass
                add_widget(getattr(self, "btn_magic_fill", None))
                populated = True
            elif mode in (2, 3) and draw_mode == "mask_wrap":
                self._shared_add_label(self.tr_ui("마스크 랩핑"))
                add_widget(getattr(self, "btn_mask_wrap_rect", None))
                add_widget(getattr(self, "btn_mask_wrap_free", None))
                self._shared_add_label(self.tr_ui("선택한 영역 안의 떨어진 마스크들을 하나의 채움 영역으로 감싸줍니다."))
                populated = True
            elif mode in (2, 3) and draw_mode == "mask_cut":
                self._shared_add_label(self.tr_ui("마스크 커팅"))
                add_widget(getattr(self, "btn_mask_cut_rect", None))
                add_widget(getattr(self, "btn_mask_cut_free", None))
                self._shared_add_label(self.tr_ui("커팅 폭"))
                add_widget(getattr(self, "sb_mask_cut_px", None))
                populated = True
            elif draw_mode == "ocr_region_select":
                self._shared_add_label(self.tr_ui("OCR 분석 영역"))
                add_widget(getattr(self, "btn_ocr_region_rect", None))
                add_widget(getattr(self, "btn_ocr_region_free", None))
                self._shared_add_label(self.tr_ui("OCR이 읽을 범위를 드래그로 지정합니다."))
                add_widget(getattr(self, "btn_ocr_region_finish", None))
                populated = True
        except Exception:
            pass

        # 빈 상태여도 바 높이는 유지한다.
        try:
            self.shared_option_left_layout.addStretch(1)
        except Exception:
            pass
        try:
            self.place_source_compare_controls()
        except Exception:
            pass


    def _source_compare_sync_blocked(self):
        try:
            if getattr(self, "_text_scene_mutation_lock", False):
                return True
            if getattr(self, "_source_compare_splitter_adjusting", False):
                return True
            until = float(getattr(self, "_source_compare_sync_block_until", 0.0) or 0.0)
            if until and time.monotonic() < until:
                return True
        except Exception:
            pass
        return False

    def _block_source_compare_sync_temporarily(self, ms=180):
        try:
            self._source_compare_sync_block_until = max(
                float(getattr(self, "_source_compare_sync_block_until", 0.0) or 0.0),
                time.monotonic() + max(0, int(ms)) / 1000.0,
            )
            self._source_compare_sync_pending = False
            self._source_compare_reverse_sync_pending = False
        except Exception:
            pass

    def _source_compare_fast_path_log(self, event_name, **payload):
        try:
            if hasattr(self, "audit_boundary_event"):
                self.audit_boundary_event(event_name, **payload)
        except Exception:
            pass

    def _begin_source_compare_clone_fast_path(self, reason="sync", delay_ms=180):
        """Temporarily lower render cost for the source-compare clone view.

        The clone window mirrors the main view, so high-resolution pages can be
        repainted twice while zooming/panning.  During active synchronization we
        use a cheap render path for the clone, then restore the original render
        hints after movement stops.
        """
        try:
            if getattr(self, "_text_scene_mutation_lock", False) or getattr(self, "_text_item_drag_active", False):
                self._source_compare_fast_path_finish_pending = True
                self._source_compare_fast_path_log(
                    "TEXT_SCENE_MUTATION_TIMER_GUARD_BLOCKED_SOURCE_COMPARE",
                    action="begin",
                    reason=str(reason or "sync"),
                    text_drag=bool(getattr(self, "_text_item_drag_active", False)),
                    throttle_ms=100,
                )
                return
            view = getattr(self, "source_compare_view", None)
            if view is None or not view.isVisible():
                return
            try:
                delay_ms = int(delay_ms or 180)
            except Exception:
                delay_ms = 180
            delay_ms = max(80, min(delay_ms, 800))

            state = getattr(self, "_source_compare_fast_path_state", None)
            if not isinstance(state, dict):
                state = {"active": False}
                self._source_compare_fast_path_state = state

            if not state.get("active"):
                state.clear()
                state["active"] = True
                state["reason"] = str(reason or "sync")
                try:
                    state["hints"] = view.renderHints()
                except Exception:
                    state["hints"] = None
                try:
                    state["viewport_mode"] = view.viewportUpdateMode()
                except Exception:
                    state["viewport_mode"] = None
                try:
                    state["cache_mode"] = view.cacheMode()
                except Exception:
                    state["cache_mode"] = None
                try:
                    pix_item = getattr(self, "source_compare_pixmap_item", None)
                    if pix_item is not None:
                        state["pixmap_transform_mode"] = pix_item.transformationMode()
                        pix_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
                except Exception:
                    state["pixmap_transform_mode"] = None

                try:
                    view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
                    view.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                    view.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
                except Exception:
                    pass
                try:
                    view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
                except Exception:
                    pass
                try:
                    view.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
                except Exception:
                    pass
                self._source_compare_fast_path_log(
                    "SOURCE_COMPARE_FAST_PATH_BEGIN",
                    reason=str(reason or "sync"),
                    delay_ms=delay_ms,
                    smooth_pixmap=False,
                    antialiasing=False,
                    viewport="BoundingRectViewportUpdate",
                    cache="CacheBackground",
                )
            else:
                state["reason"] = str(reason or state.get("reason") or "sync")

            timer = getattr(self, "_source_compare_fast_path_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._finish_source_compare_clone_fast_path)
                self._source_compare_fast_path_timer = timer
            timer.start(delay_ms)
        except Exception:
            pass

    def _finish_source_compare_clone_fast_path(self, force=False):
        try:
            state = getattr(self, "_source_compare_fast_path_state", None)
            if not isinstance(state, dict) or not state.get("active"):
                return
            if getattr(self, "_text_scene_mutation_lock", False) or getattr(self, "_text_item_drag_active", False):
                self._source_compare_fast_path_finish_pending = True
                try:
                    timer = getattr(self, "_source_compare_fast_path_timer", None)
                    if timer is not None and timer.isActive():
                        timer.stop()
                except Exception:
                    pass
                self._source_compare_fast_path_log(
                    "TEXT_SCENE_MUTATION_TIMER_GUARD_BLOCKED_SOURCE_COMPARE",
                    action="finish",
                    reason=str(state.get("reason") or "sync"),
                    throttle_ms=100,
                )
                return
            view = getattr(self, "source_compare_view", None)
            reason = str(state.get("reason") or "sync")
            if view is not None:
                try:
                    old_hints = state.get("hints")
                    if old_hints is not None:
                        view.setRenderHints(old_hints)
                    else:
                        view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                except Exception:
                    pass
                try:
                    old_mode = state.get("viewport_mode")
                    if old_mode is not None:
                        view.setViewportUpdateMode(old_mode)
                except Exception:
                    pass
                try:
                    old_cache = state.get("cache_mode")
                    if old_cache is not None:
                        view.setCacheMode(old_cache)
                    else:
                        view.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
                except Exception:
                    pass
                try:
                    pix_item = getattr(self, "source_compare_pixmap_item", None)
                    old_transform = state.get("pixmap_transform_mode")
                    if pix_item is not None and old_transform is not None:
                        pix_item.setTransformationMode(old_transform)
                except Exception:
                    pass
                try:
                    view.viewport().update()
                except Exception:
                    pass
            self._source_compare_fast_path_state = {"active": False}
            self._source_compare_fast_path_finish_pending = False
            self._source_compare_fast_path_log("SOURCE_COMPARE_FAST_PATH_END", reason=reason)
        except Exception:
            try:
                self._source_compare_fast_path_state = {"active": False}
                self._source_compare_fast_path_finish_pending = False
            except Exception:
                pass

    def _capture_compare_view_state(self, view):
        try:
            if view is None:
                return None
            return {
                "transform": view.transform(),
                "h": view.horizontalScrollBar().value(),
                "v": view.verticalScrollBar().value(),
            }
        except Exception:
            return None

    def _restore_compare_view_state(self, view, state):
        try:
            if view is None or not state:
                return
            if state.get("transform") is not None:
                view.setTransform(state.get("transform"))
            if state.get("h") is not None:
                view.horizontalScrollBar().setValue(int(state.get("h")))
            if state.get("v") is not None:
                view.verticalScrollBar().setValue(int(state.get("v")))
            try:
                view.viewport().update()
            except Exception:
                pass
        except Exception:
            pass

    def _capture_source_compare_splitter_states(self):
        return {
            "main": self._capture_compare_view_state(getattr(self, "view", None)),
            "clone": self._capture_compare_view_state(getattr(self, "source_compare_view", None)),
        }

    def _restore_source_compare_splitter_states(self, states=None):
        try:
            if states is None:
                states = getattr(self, "_source_compare_splitter_view_states", None)
            if not states:
                return
            old_sync = getattr(self, "_source_compare_syncing", False)
            self._source_compare_syncing = True
            try:
                self._restore_compare_view_state(getattr(self, "view", None), states.get("main"))
                self._restore_compare_view_state(getattr(self, "source_compare_view", None), states.get("clone"))
            finally:
                self._source_compare_syncing = old_sync
        except Exception:
            pass

    def _capture_main_view_state_for_compare_splitter(self):
        try:
            states = self._capture_source_compare_splitter_states()
            return states.get("main")
        except Exception:
            return None

    def _restore_main_view_state_for_compare_splitter(self, state=None):
        try:
            if state is None:
                state = getattr(self, "_source_compare_splitter_main_view_state", None)
            old_sync = getattr(self, "_source_compare_syncing", False)
            self._source_compare_syncing = True
            try:
                self._restore_compare_view_state(getattr(self, "view", None), state)
            finally:
                self._source_compare_syncing = old_sync
        except Exception:
            pass

    def reset_source_compare_splitter_half(self):
        """원본 비교창과 작업창을 현재 사용 가능 너비 기준 정확히 반반으로 맞춘다."""
        try:
            keep_states = self._capture_source_compare_splitter_states()
            split = getattr(self, 'source_compare_splitter', None)
            if split is None or split.count() < 2:
                return
            total = max(0, int(split.width()) - max(0, (split.count() - 1) * int(split.handleWidth())))
            if total <= 0:
                total = sum(max(0, int(v)) for v in split.sizes())
            if total <= 0:
                return
            left = total // 2
            right = total - left
            self._source_compare_splitter_adjusting = True
            self._block_source_compare_sync_temporarily(260)
            try:
                split.setSizes([left, right])
                self._restore_source_compare_splitter_states(keep_states)
                QTimer.singleShot(0, lambda s=keep_states: self._restore_source_compare_splitter_states(s))
                QTimer.singleShot(80, lambda s=keep_states: self._restore_source_compare_splitter_states(s))
            finally:
                QTimer.singleShot(180, lambda: setattr(self, '_source_compare_splitter_adjusting', False))
            self.log('🖼️ 원본 비교창/작업창 너비를 1:1로 정렬했습니다.')
        except Exception as e:
            try:
                self.log(f'⚠️ 원본 비교창 정렬 실패: {e}')
            except Exception:
                pass

    def open_source_compare_view(self):
        """왼쪽에 현재 페이지의 원본 탭 이미지를 복제해 비교 보기로 띄운다.
        이미 열려 있으면 같은 버튼/단축키로 닫는다.
        """
        if bool(getattr(self, "maker_ui_cleanup_enabled", False)) or bool(getattr(self, "tktool_phase1_enabled", False)):
            try:
                self.close_source_compare_view()
            except Exception:
                pass
            try:
                self.log(self.tr_ui("ℹ️ 쯔꾸르붕이에서는 원본 비교창/상단 공유 옵션바를 사용하지 않습니다."))
            except Exception:
                pass
            return
        if not getattr(self, "paths", None):
            try:
                self.log(self.tr_ui("⚠️ 원본 비교창을 열 프로젝트가 없습니다."))
            except Exception:
                pass
            return
        try:
            if self.source_compare_is_visible():
                self.close_source_compare_view()
                return
            if hasattr(self, "source_compare_view"):
                self.source_compare_view.show()
            if hasattr(self, "source_compare_controls"):
                self.source_compare_controls.show()
            if hasattr(self, "source_compare_splitter"):
                sizes = self.source_compare_splitter.sizes()
                total = sum(sizes) if sizes else 0
                if total <= 0:
                    total = max(900, self.source_compare_splitter.width())
                left = max(40, int(total * 0.35))
                right = max(240, total - left)
                self.source_compare_splitter.setSizes([left, right])
            self.refresh_source_compare_view(fit=True)
            if hasattr(self, "sync_source_compare_from_main"):
                self.place_source_compare_controls()
                self.schedule_source_compare_sync(0)
                self.start_source_compare_sync_timer()
                QTimer.singleShot(60, lambda: self.schedule_source_compare_sync(0))
                QTimer.singleShot(160, lambda: self.schedule_source_compare_sync(0))
                QTimer.singleShot(300, lambda: self.schedule_source_compare_sync(0))
            self.log(self.tr_ui("🖼️ 원본 비교창을 열었습니다."))
        except Exception as e:
            try:
                self.log(self.tr_ui(f"⚠️ 원본 비교창 열기 실패: {e}"))
            except Exception:
                pass

    def close_source_compare_view(self):
        try:
            # Closing the clone view must not change the user's current work view.
            try:
                keep_transform = self.view.transform()
                keep_center = self.view.mapToScene(self.view.viewport().rect().center())
            except Exception:
                keep_transform = None
                keep_center = None

            self.stop_source_compare_sync_timer()
            if hasattr(self, "source_compare_view"):
                self.source_compare_view.hide()
            if hasattr(self, "source_compare_controls"):
                self.source_compare_controls.hide()
            if hasattr(self, "source_compare_bar"):
                self.source_compare_bar.hide()
            if hasattr(self, "source_compare_splitter"):
                self.source_compare_splitter.setSizes([0, max(400, self.source_compare_splitter.width())])

            def restore_main_view():
                try:
                    if keep_transform is not None:
                        self.view.setTransform(keep_transform)
                    if keep_center is not None:
                        self.view.centerOn(keep_center)
                except Exception:
                    pass
                try:
                    self.place_source_compare_controls()
                except Exception:
                    pass

            QTimer.singleShot(0, restore_main_view)
            QTimer.singleShot(80, restore_main_view)
            self.log(self.tr_ui("🖼️ 원본 비교창을 닫았습니다."))
        except Exception:
            pass

    def get_page_text_effect_preview_enabled(self, page_idx=None):
        """Return the page-local text effect preview setting.

        Heavy text effects are preview-only editor UI.  The setting is stored per
        page because a single project can contain both light pages and very heavy
        glow/shadow pages.  Missing value means ON.
        """
        try:
            pidx = int(page_idx if page_idx is not None else getattr(self, "idx", 0) or 0)
        except Exception:
            pidx = int(getattr(self, "idx", 0) or 0) if hasattr(self, "idx") else 0
        try:
            curr = (getattr(self, "data", {}) or {}).get(pidx)
            if isinstance(curr, dict) and "text_effect_preview_enabled" in curr:
                return bool(curr.get("text_effect_preview_enabled"))
        except Exception:
            pass
        return True

    def sync_text_effect_preview_checkbox_for_current_page(self):
        """Apply the current page-local effect-preview value to runtime/UI."""
        enabled = bool(self.get_page_text_effect_preview_enabled())
        try:
            self.text_effect_preview_enabled = enabled
        except Exception:
            pass
        cb = getattr(self, "cb_text_effect_preview", None)
        if cb is not None:
            try:
                old = cb.blockSignals(True)
                try:
                    cb.setChecked(enabled)
                finally:
                    cb.blockSignals(old)
            except Exception:
                try:
                    cb.setChecked(enabled)
                except Exception:
                    pass
        return enabled

    def on_text_effect_preview_toggled(self, checked):
        """Toggle heavy text effects for the current page editor preview only.

        This does not change export rendering.  It only skips expensive
        preview-only effects for the active page while editing/navigation is laggy.
        """
        enabled = bool(checked)
        changed = False
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
        except Exception:
            page_idx = 0
        try:
            curr = (getattr(self, "data", {}) or {}).get(page_idx)
            if isinstance(curr, dict):
                old = bool(curr.get("text_effect_preview_enabled", True))
                if old != enabled or "text_effect_preview_enabled" not in curr:
                    curr["text_effect_preview_enabled"] = enabled
                    changed = True
        except Exception:
            pass
        try:
            self.text_effect_preview_enabled = enabled
        except Exception:
            pass
        if changed:
            try:
                self.mark_current_page_for_recovery_checkpoint("text_effect_preview")
            except Exception:
                try:
                    self.mark_active_page_dirty("text_effect_preview")
                except Exception:
                    pass
            try:
                self.schedule_workspace_checkpoint(900, reason="text_effect_preview_toggle")
            except Exception:
                try:
                    self.schedule_deferred_auto_save_project(900)
                except Exception:
                    pass
        try:
            scene = getattr(getattr(self, "view", None), "scene", None)
            if scene is not None:
                for item in list(scene.items()):
                    if isinstance(item, TypesettingItem):
                        try:
                            item.update()
                        except Exception:
                            pass
        except Exception:
            pass
        try:
            view = getattr(self, "view", None)
            if view is not None and view.viewport() is not None:
                view.viewport().update()
        except Exception:
            pass
        try:
            msg = "텍스트 이펙트 미리보기 켜짐" if enabled else "텍스트 이펙트 미리보기 꺼짐 - 최종 출력에는 영향 없음"
            self.log(self.tr_ui(msg))
        except Exception:
            pass

    def on_source_compare_sync_toggled(self, checked):
        if checked:
            self.schedule_source_compare_sync(0)
            self.start_source_compare_sync_timer()
        else:
            self.stop_source_compare_sync_timer()
            try:
                self._source_compare_sync_pending = False
            except Exception:
                pass

    def source_compare_is_visible(self):
        try:
            return bool(hasattr(self, "source_compare_view") and self.source_compare_view.isVisible())
        except Exception:
            return False

    def ensure_source_compare_sync_timer(self):
        """Create a lightweight polling timer for clone sync."""
        try:
            timer = getattr(self, "_source_compare_sync_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setInterval(80)
                timer.timeout.connect(lambda: self.sync_source_compare_from_main())
                self._source_compare_sync_timer = timer
            return timer
        except Exception:
            return None

    def start_source_compare_sync_timer(self):
        try:
            if self._source_compare_sync_blocked():
                return
            if not self.source_compare_is_visible():
                return
            if hasattr(self, "cb_source_compare_sync") and not self.cb_source_compare_sync.isChecked():
                return
            timer = self.ensure_source_compare_sync_timer()
            if timer is not None and not timer.isActive():
                timer.start()
        except Exception:
            pass

    def stop_source_compare_sync_timer(self):
        try:
            timer = getattr(self, "_source_compare_sync_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
        except Exception:
            pass

    def schedule_source_compare_sync(self, delay=16):
        """Coalesce source-compare clone sync requests.

        Safe zoom-performance rule:
        - Do not change text item cache modes here. That made large text pages much slower.
        - During wheel/scroll fast path, postpone clone sync until the view settles.
        - Keep the existing one-shot/pending structure so this remains low-risk.
        """
        try:
            if getattr(self, "_text_scene_mutation_lock", False) or getattr(self, "_text_item_drag_active", False):
                self._source_compare_sync_resume_after_text_mutation = True
                self._source_compare_fast_path_log(
                    "TEXT_SCENE_MUTATION_TIMER_GUARD_BLOCKED_SOURCE_COMPARE",
                    action="schedule_sync",
                    text_drag=bool(getattr(self, "_text_item_drag_active", False)),
                    throttle_ms=100,
                )
                return
            if self._source_compare_sync_blocked() or getattr(self, "_source_compare_syncing", False) or getattr(self, "_source_compare_user_driving", False):
                return
            if not self.source_compare_is_visible():
                return
            if hasattr(self, "cb_source_compare_sync") and not self.cb_source_compare_sync.isChecked():
                return
            if getattr(self, "_source_compare_sync_pending", False):
                return
            self._source_compare_sync_pending = True
            def _run():
                try:
                    self._source_compare_sync_pending = False
                    if getattr(self, "_text_scene_mutation_lock", False) or getattr(self, "_text_item_drag_active", False):
                        self._source_compare_sync_resume_after_text_mutation = True
                        self._source_compare_fast_path_log(
                            "TEXT_SCENE_MUTATION_TIMER_GUARD_BLOCKED_SOURCE_COMPARE",
                            action="run_sync",
                            text_drag=bool(getattr(self, "_text_item_drag_active", False)),
                            throttle_ms=100,
                        )
                        return
                    view = getattr(self, "view", None)
                    if view is not None and getattr(view, "_view_interaction_fast_path_active", False):
                        # A wheel burst is still repainting the work view.  Syncing the
                        # clone now causes two views to repaint mid-gesture.  Push once.
                        self.schedule_source_compare_sync(180)
                        return
                    if self._source_compare_sync_blocked() or getattr(self, "_source_compare_user_driving", False):
                        return
                    self.sync_source_compare_from_main()
                except Exception:
                    self._source_compare_sync_pending = False
            try:
                effective_delay = max(16, int(delay or 0))
            except Exception:
                effective_delay = 16
            QTimer.singleShot(effective_delay, _run)
        except Exception:
            try:
                self._source_compare_sync_pending = False
            except Exception:
                pass

    def refresh_source_compare_view(self, fit=False):
        if not self.source_compare_is_visible():
            return
        try:
            # 원본 비교창은 작업용 원본(working_source)이 아니라, 처음 불러온 순수 원본을 유지한다.
            # Alt+P '배경을 원본으로 쓰기'는 분석/인페인팅 기준만 바꾸고 비교용 순수 원본은 건드리지 않는다.
            img = self.get_real_original_image(self.idx) if hasattr(self, "get_real_original_image") else None
            if img is None:
                img = self.get_source_display_image(self.idx)
            scene = self.source_compare_scene
            scene.clear()
            pix = self.qt_pixmap_from_image_source(img)
            if pix is None or pix.isNull():
                return
            item = scene.addPixmap(pix)
            self.source_compare_pixmap_item = item
            try:
                item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            except Exception:
                pass
            scene.setSceneRect(QRectF(pix.rect()))
            if fit and not (hasattr(self, "cb_source_compare_sync") and self.cb_source_compare_sync.isChecked()):
                self.source_compare_view.fitInView(scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            if hasattr(self, "cb_source_compare_sync") and self.cb_source_compare_sync.isChecked():
                self.schedule_source_compare_sync(0)
        except Exception as e:
            try:
                self.log(self.tr_ui(f"⚠️ 원본 비교창 갱신 실패: {e}"))
            except Exception:
                pass

    def sync_source_compare_from_main(self):
        if getattr(self, "_text_scene_mutation_lock", False) or getattr(self, "_text_item_drag_active", False):
            self._source_compare_sync_resume_after_text_mutation = True
            self._source_compare_fast_path_log(
                "TEXT_SCENE_MUTATION_TIMER_GUARD_BLOCKED_SOURCE_COMPARE",
                action="sync_from_main",
                text_drag=bool(getattr(self, "_text_item_drag_active", False)),
                throttle_ms=100,
            )
            return
        if self._source_compare_sync_blocked():
            return
        if getattr(self, "_source_compare_syncing", False) or getattr(self, "_source_compare_user_driving", False):
            return
        if not self.source_compare_is_visible():
            return
        if hasattr(self, "cb_source_compare_sync") and not self.cb_source_compare_sync.isChecked():
            return
        self._source_compare_syncing = True
        try:
            self._begin_source_compare_clone_fast_path("main_to_clone_sync", delay_ms=180)
            center = self.view.mapToScene(self.view.viewport().rect().center())
            self.source_compare_view.setTransform(self.view.transform())
            self.source_compare_view.centerOn(center)
            try:
                self.source_compare_view.viewport().update()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self._source_compare_syncing = False

    def schedule_main_sync_from_source_compare(self, delay=0):
        try:
            if getattr(self, "_text_scene_mutation_lock", False) or getattr(self, "_text_item_drag_active", False):
                self._source_compare_sync_resume_after_text_mutation = True
                self._source_compare_fast_path_log(
                    "TEXT_SCENE_MUTATION_TIMER_GUARD_BLOCKED_SOURCE_COMPARE",
                    action="schedule_reverse_sync",
                    text_drag=bool(getattr(self, "_text_item_drag_active", False)),
                    throttle_ms=100,
                )
                return
            if self._source_compare_sync_blocked() or getattr(self, "_source_compare_syncing", False):
                return
            if not self.source_compare_is_visible():
                return
            if hasattr(self, "cb_source_compare_sync") and not self.cb_source_compare_sync.isChecked():
                return
            if getattr(self, "_source_compare_reverse_sync_pending", False):
                return
            self._source_compare_reverse_sync_pending = True
            def _run():
                try:
                    self._source_compare_reverse_sync_pending = False
                    sc_view = getattr(self, "source_compare_view", None)
                    if sc_view is not None and getattr(sc_view, "_view_interaction_fast_path_active", False):
                        self.schedule_main_sync_from_source_compare(180)
                        return
                    if self._source_compare_sync_blocked():
                        return
                    self.sync_main_from_source_compare()
                except Exception:
                    self._source_compare_reverse_sync_pending = False
            try:
                effective_delay = max(16, int(delay or 0))
            except Exception:
                effective_delay = 16
            QTimer.singleShot(effective_delay, _run)
        except Exception:
            try:
                self._source_compare_reverse_sync_pending = False
            except Exception:
                pass

    def sync_main_from_source_compare(self):
        if self._source_compare_sync_blocked():
            return
        if getattr(self, "_source_compare_syncing", False):
            return
        if not self.source_compare_is_visible():
            return
        if hasattr(self, "cb_source_compare_sync") and not self.cb_source_compare_sync.isChecked():
            return
        self._source_compare_syncing = True
        try:
            self._begin_source_compare_clone_fast_path("clone_to_main_sync", delay_ms=180)
            try:
                if hasattr(self.view, "_begin_view_interaction_fast_path"):
                    self.view._begin_view_interaction_fast_path("source_compare_reverse_sync", delay_ms=180)
            except Exception:
                pass
            center = self.source_compare_view.mapToScene(self.source_compare_view.viewport().rect().center())
            self.view.setTransform(self.source_compare_view.transform())
            self.view.centerOn(center)
            try:
                self.view.viewport().update()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self._source_compare_syncing = False

    def _on_main_view_scroll_changed_for_source_compare(self, *_args):
        try:
            if self._source_compare_sync_blocked() or getattr(self, "_source_compare_syncing", False):
                return
            try:
                self._begin_source_compare_clone_fast_path("main_scroll_sync", delay_ms=180)
            except Exception:
                pass
            self.schedule_source_compare_sync(16)
        except Exception:
            pass

    def _on_source_compare_scroll_changed_for_main(self, *_args):
        try:
            if self._source_compare_sync_blocked() or getattr(self, "_source_compare_syncing", False):
                return
            sc_view = getattr(self, "source_compare_view", None)
            # Resize/layout changes also move scrollbars. Treat reverse sync as user intent
            # only when the clone view itself is being interacted with.
            user_driving = bool(getattr(self, "_source_compare_user_driving", False))
            try:
                user_driving = user_driving or bool(sc_view is not None and (sc_view.underMouse() or sc_view.viewport().underMouse()))
            except Exception:
                pass
            if not user_driving:
                return
            try:
                self._begin_source_compare_clone_fast_path("clone_scroll_reverse_sync", delay_ms=180)
            except Exception:
                pass
            self.schedule_main_sync_from_source_compare(16)
        except Exception:
            pass

    def update_left_tool_action_states(self, tool=None):
        """Reflect the active canvas tool on the left toolbar buttons.

        The source of truth is view.draw_mode.  This method is called both after
        mouse-click toolbar actions and after keyboard shortcuts, so the visual
        state is consistent regardless of how the tool was selected.
        """
        try:
            if tool is None and getattr(self, "view", None) is not None:
                tool = getattr(self.view, "draw_mode", None)
        except Exception:
            tool = None
        active_key = str(tool) if tool is not None else ""
        actions = getattr(self, "left_tool_actions", {}) or {}
        buttons = getattr(self, "left_tool_buttons", {}) or {}
        for key, action in list(actions.items()):
            active = str(key) == active_key
            if action is not None:
                try:
                    action.blockSignals(True)
                    action.setChecked(active)
                except Exception:
                    pass
                finally:
                    try:
                        action.blockSignals(False)
                    except Exception:
                        pass
            btn = buttons.get(key)
            if btn is None:
                try:
                    btn = self.tb.widgetForAction(action) if hasattr(self, "tb") and self.tb is not None and action is not None else None
                    if btn is not None:
                        buttons[key] = btn
                except Exception:
                    btn = None
            if btn is not None:
                try:
                    btn.setCheckable(True)
                    btn.blockSignals(True)
                    btn.setChecked(active)
                    btn.setProperty("ysb_active_tool", bool(active))
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    btn.update()
                except Exception:
                    pass
                finally:
                    try:
                        btn.blockSignals(False)
                    except Exception:
                        pass
        try:
            self.left_tool_buttons = buttons
        except Exception:
            pass
        try:
            if hasattr(self, "tb") and self.tb is not None:
                self.tb.update()
        except Exception:
            pass

    def set_tool(self, m):
        mode = self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 0

        if m == 'magic_wand' and mode not in [2, 3, 4]:
            self.log("⚠️ 요술봉은 마스크 탭 또는 최종결과 탭에서 사용하세요.")
            self.update_left_tool_action_states()
            return
        if m == 'mask_wrap' and mode not in [2, 3]:
            self.log("⚠️ 마스크 랩핑은 텍스트 마스크/페인팅 마스크 탭에서 사용하세요.")
            return
        if m == 'mask_cut' and mode not in [2, 3]:
            self.log(self.tr_ui("⚠️ 마스크 커팅은 텍스트 마스크/페인팅 마스크 탭에서 사용하세요."))
            return
        if m == 'final_text' and mode != 4:
            self.log("⚠️ 텍스트 도구는 최종화면에서만 사용할 수 있습니다.")
            self.update_left_tool_action_states()
            return
        if m == 'area_paint' and mode not in [2, 3, 4]:
            self.log("⚠️ 영역 페인팅/마스킹은 마스크 탭 또는 최종화면에서만 사용할 수 있습니다.")
            self.update_left_tool_action_states()
            return
        if m == 'paste_text' and mode != 4:
            self.log("⚠️ 텍스트 붙여넣기는 최종화면에서만 사용할 수 있습니다.")
            self.update_left_tool_action_states()
            return
        if m == 'raster_erase' and mode != 4:
            self.log("⚠️ " + self.tr_ui("객체 일부 지우기는 최종화면에서만 사용할 수 있습니다."))
            self.update_left_tool_action_states()
            return
        if m in ('draw', 'erase') and mode not in [2, 3, 4]:
            self.log("⚠️ 브러시/지우개는 마스크 탭 또는 최종화면에서만 사용할 수 있습니다.")
            self.update_left_tool_action_states()
            return

        if m != 'paste_text':
            self.text_paste_pending = False
            try:
                self.view.clear_paste_preview()
            except Exception:
                pass

        self.view.draw_mode = m
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag if m else QGraphicsView.DragMode.ScrollHandDrag)
        self.update_left_tool_action_states(m)
        self._hide_legacy_option_bars()
        if m != 'magic_wand':
            self.clear_magic_wand_selection()
        if m != 'mask_wrap' and hasattr(self.view, "clear_mask_wrap_preview"):
            self.view.clear_mask_wrap_preview()
        if m != 'mask_cut' and hasattr(self.view, "clear_mask_cut_preview"):
            self.view.clear_mask_cut_preview()
        if m != 'ocr_region_select' and hasattr(self.view, "clear_ocr_region_preview"):
            self.view.clear_ocr_region_preview()
        if m != 'quick_ocr' and hasattr(self.view, "clear_quick_ocr_preview"):
            self.view.clear_quick_ocr_preview()
        if m != 'area_paint' and hasattr(self.view, "clear_area_paint_preview"):
            self.view.clear_area_paint_preview()
        if m != 'area_paint' and hasattr(self.view, "area_paint_points"):
            self.view.area_paint_points = []
        if m != 'raster_erase' and hasattr(self.view, "clear_raster_erase_preview"):
            self.view.clear_raster_erase_preview()

        self.update_final_paint_option_bar_visibility()
        try:
            self.refresh_shared_option_bar()
        except Exception:
            pass

        if m == 'final_text':
            self.log("🔤 도구: 텍스트")
        elif m == 'paste_text':
            self.log("📋 도구: 텍스트 붙여넣기 위치 지정")
        elif m == 'area_paint':
            if mode in (2, 3):
                self.log("▦ 도구: 영역 마스킹")
            else:
                self.log("▦ 도구: 영역 페인팅")
        elif m == 'raster_erase':
            self.log("🧽 " + self.tr_ui("도구: 텍스트 객체 일부 지우기"))
        elif m == 'draw':
            self.log("🖌️ 도구: 브러시")
        elif m == 'erase':
            self.log("🧼 도구: 지우개")
        elif m == 'mask_wrap':
            self.log("🩹 도구: 마스크 랩핑")
        elif m == 'mask_cut':
            self.log(self.tr_ui("🔪 도구: 마스크 커팅"))
        elif m == 'ocr_region_select':
            self.log("🔎 도구: OCR 분석 영역 지정")
        elif m == 'quick_ocr':
            self.log("🔎 도구: 빠른 OCR 영역 선택")
        elif m is None:
            self.log("✋ 도구: 이동")

    def _ocr_region_indices_label(self, indices):
        if not indices:
            return self.tr_ui("선택 맵 없음")
        if len(indices) == len(getattr(self, "paths", []) or []):
            return self.tr_ui("전체 맵")
        return ", ".join(str(i + 1) for i in indices[:12]) + ("..." if len(indices) > 12 else "")

    def ocr_analysis_regions_hidden(self):
        return bool((getattr(self, "app_options", {}) or {}).get("ocr_analysis_regions_hidden", False))

    def set_ocr_analysis_regions_hidden(self, hidden):
        self.app_options["ocr_analysis_regions_hidden"] = bool(hidden)
        self.save_app_options_cache()
        self.refresh_ocr_region_overlay()

    def current_ocr_regions_for_view(self):
        if self.ocr_analysis_regions_hidden():
            return []
        temp = getattr(self, "ocr_region_temp_by_page", None)
        if isinstance(temp, dict) and self.idx in temp:
            return copy.deepcopy(temp.get(self.idx) or [])
        curr = self.data.get(self.idx) if hasattr(self, "data") else None
        if not curr:
            return []
        return copy.deepcopy(curr.get('ocr_analysis_regions', []) or [])

    def refresh_ocr_region_overlay(self):
        try:
            if not hasattr(self, "view"):
                return
            if self.ocr_analysis_regions_hidden():
                self.view.clear_ocr_region_overlay()
                return
            mode = self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 0
            if mode in (0, 1, 2, 3):
                self.view.draw_ocr_analysis_regions(self.current_ocr_regions_for_view())
            else:
                self.view.clear_ocr_region_overlay()
        except Exception:
            pass

    def set_ocr_region_shape(self, shape, silent=False):
        shape = "free" if str(shape) == "free" else "rect"
        try:
            self.view.ocr_region_shape = shape
            self.view.clear_ocr_region_preview()
        except Exception:
            pass
        for btn, active in ((getattr(self, "btn_ocr_region_rect", None), shape == "rect"), (getattr(self, "btn_ocr_region_free", None), shape == "free")):
            if btn is None:
                continue
            try:
                btn.blockSignals(True)
                btn.setChecked(active)
                btn.blockSignals(False)
                if active:
                    btn.setStyleSheet("font-weight:bold; background:#8A4A52; color:white;")
                else:
                    btn.setStyleSheet("opacity:0.7;")
            except Exception:
                pass
        if not silent:
            self.log("🔎 OCR 분석 영역: 사각형" if shape == "rect" else "🔎 OCR 분석 영역: 자유형")

    def open_ocr_analysis_region_dialog(self):
        if not getattr(self, "paths", None):
            QMessageBox.information(self, self.tr_ui("이미지 없음"), self.tr_ui("먼저 프로젝트에 이미지를 불러와 주세요."))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("OCR 분석 범위 지정"))
        dlg.setModal(True)
        dlg.resize(720, 430)
        try:
            dlg.setStyleSheet(self.settings_dialog_style())
        except Exception:
            pass

        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(self.tr_ui("OCR 분석 범위 지정"), dlg)
        title.setObjectName("SettingsTitle")
        root.addWidget(title)

        desc = QLabel(self.tr_ui("OCR이 읽을 영역을 페이지별로 제한합니다. 지정된 영역이 없으면 전체 화면을 분석합니다."), dlg)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        root.addWidget(desc)

        form_box = QFrame(dlg)
        form_box.setObjectName("SettingsItem")
        form_layout = QVBoxLayout(form_box)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(12)

        def add_setting_row(title_text, description_text, button_text, handler):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)

            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)

            item_title = QLabel(self.tr_ui(title_text), dlg)
            item_title.setObjectName("SettingsItemTitle")
            item_desc = QLabel(self.tr_ui(description_text), dlg)
            item_desc.setObjectName("SettingsDescription")
            item_desc.setWordWrap(True)

            text_box.addWidget(item_title)
            text_box.addWidget(item_desc)
            row.addLayout(text_box, 1)

            btn = QPushButton(self.tr_ui(button_text), dlg)
            btn.setMinimumWidth(112)
            btn.clicked.connect(lambda checked=False, _h=handler: (dlg.accept(), _h()))
            row.addWidget(btn, 0)
            form_layout.addLayout(row)

        add_setting_row(
            "현재 페이지의 OCR 분석 범위 지정",
            "현재 보고 있는 페이지만 OCR 분석 영역을 지정합니다.",
            "지정하기",
            lambda: self.start_ocr_analysis_region_selection([self.idx], "현재 맵"),
        )
        add_setting_row(
            "전체 맵의 OCR 분석 범위 지정",
            "모든 페이지에 같은 OCR 분석 영역을 지정합니다.",
            "지정하기",
            lambda: self.start_ocr_analysis_region_selection(list(range(len(self.paths))), "전체 맵"),
        )

        def selected_pages_handler():
            indices, label = self.choose_batch_page_indices(self.tr_ui("OCR 분석 범위 지정"), "analyze")
            if indices is None:
                self.log("↩️ OCR 분석 범위 지정 취소")
                return
            self.start_ocr_analysis_region_selection(indices, label)

        add_setting_row(
            "선택 페이지의 OCR 분석 범위 지정",
            "1-3, 1~3, 1,2,3 형식으로 지정한 페이지에 같은 영역을 적용합니다.",
            "지정하기",
            selected_pages_handler,
        )

        line = QFrame(dlg)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        form_layout.addWidget(line)

        add_setting_row(
            "현재 페이지 범위지정 해제",
            "현재 보고 있는 페이지만 OCR 분석 영역을 지우고, 다른 페이지의 영역은 유지합니다.",
            "현재 페이지만 해제",
            self.clear_current_ocr_analysis_regions,
        )

        add_setting_row(
            "전체 범위지정 해제",
            "저장된 OCR 분석 영역을 모든 페이지에서 지우고, 다시 전체 화면 분석 상태로 되돌립니다.",
            "전체 해제",
            self.clear_all_ocr_analysis_regions,
        )

        hide_box = QFrame(dlg)
        hide_box.setObjectName("SettingsItem")
        hide_layout = QVBoxLayout(hide_box)
        hide_layout.setContentsMargins(12, 12, 12, 12)
        hide_layout.setSpacing(6)
        cb_hide_regions = QCheckBox(self.tr_ui("OCR 분석 영역 숨기기"), dlg)
        cb_hide_regions.setChecked(self.ocr_analysis_regions_hidden())
        cb_hide_desc = QLabel(self.tr_ui("체크하면 저장된 OCR 분석 영역은 유지하되, 모든 탭에서 영역 표시만 숨깁니다."), dlg)
        cb_hide_desc.setObjectName("SettingsDescription")
        cb_hide_desc.setWordWrap(True)
        hide_layout.addWidget(cb_hide_regions)
        hide_layout.addWidget(cb_hide_desc)
        cb_hide_regions.toggled.connect(lambda checked: self.set_ocr_analysis_regions_hidden(bool(checked)))

        root.addWidget(form_box)
        root.addWidget(hide_box)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dlg)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.tr_ui("닫기"))
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)
        dlg.exec()


    def _copy_ocr_region_temp_state(self):
        try:
            temp = getattr(self, "ocr_region_temp_by_page", None)
            return {
                "temp_by_page": copy.deepcopy(temp) if isinstance(temp, dict) else None,
                "history": copy.deepcopy(getattr(self, "ocr_region_temp_history", []) or []),
                "target_indices": [int(x) for x in (getattr(self, "ocr_region_target_indices", []) or [])],
                "target_label": str(getattr(self, "ocr_region_target_label", "") or ""),
            }
        except Exception:
            return {"temp_by_page": None, "history": [], "target_indices": [], "target_label": ""}

    def push_ocr_region_temp_command(self, before_state=None, after_state=None, *, reason="OCR 분석 영역 임시 추가"):
        before_state = before_state if isinstance(before_state, dict) else self._copy_ocr_region_temp_state()
        after_state = after_state if isinstance(after_state, dict) else self._copy_ocr_region_temp_state()
        try:
            page_idx = int(getattr(self, "idx", 0) or 0)
        except Exception:
            page_idx = 0
        return self._push_runtime_command(
            "ocr_region_temp",
            f"ocr_region_temp:{page_idx}",
            "state",
            before_state,
            after_state,
            reason=reason,
            meta={"stage": "undo_exception_cleanup", "runtime_only": True},
        )

    def _apply_ocr_region_temp_command(self, command, *, redo=False):
        changes = list(getattr(command, "changes", []) or [])
        if not changes:
            return False
        value = None
        for change in changes:
            if str(getattr(change, "field", "") or "") == "state":
                value = copy.deepcopy(getattr(change, "after", None) if redo else getattr(change, "before", None))
                break
        if not isinstance(value, dict):
            return False
        try:
            temp = value.get("temp_by_page")
            self.ocr_region_temp_by_page = copy.deepcopy(temp) if isinstance(temp, dict) else temp
            self.ocr_region_temp_history = copy.deepcopy(value.get("history") or [])
            self.ocr_region_target_indices = [int(x) for x in (value.get("target_indices") or [])]
            self.ocr_region_target_label = str(value.get("target_label") or "")
            self.refresh_ocr_region_overlay()
            self.update_undo_redo_buttons()
            self.audit_boundary_event("UNDO_OCR_REGION_TEMP_COMMAND_APPLY", redo=bool(redo), hist_len=len(self.ocr_region_temp_history or []), throttle_ms=120)
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ OCR 임시 영역 복원 실패: {e}")
            except Exception:
                pass
            return False

    def start_ocr_analysis_region_selection(self, indices, label=""):
        if not indices:
            self.log("⚠️ OCR 분석 영역을 지정할 페이지가 없습니다.")
            return
        clean = []
        seen = set()
        for raw in indices:
            try:
                i = int(raw)
            except Exception:
                continue
            if 0 <= i < len(self.paths) and i not in seen:
                clean.append(i); seen.add(i)
        if not clean:
            self.log("⚠️ OCR 분석 영역을 지정할 페이지가 없습니다.")
            return
        self.ocr_region_target_indices = clean
        self.ocr_region_target_label = str(label or self._ocr_region_indices_label(clean))
        self.ocr_region_temp_history = []
        self.ocr_region_temp_by_page = {i: copy.deepcopy(self.data.get(i, {}).get('ocr_analysis_regions', []) or []) for i in clean}
        if self.idx not in self.ocr_region_temp_by_page:
            self.ocr_region_temp_by_page[self.idx] = copy.deepcopy(self.data.get(self.idx, {}).get('ocr_analysis_regions', []) or [])
        self.set_ocr_region_shape("rect", silent=True)
        self.set_tool('ocr_region_select')
        self.refresh_ocr_region_overlay()
        self.log(f"🔎 OCR 분석 영역 지정 시작: {self.ocr_region_target_label}")

    def add_ocr_analysis_region_payload(self, payload):
        if not isinstance(payload, dict):
            return
        before_temp_state = self._copy_ocr_region_temp_state() if hasattr(self, "_copy_ocr_region_temp_state") else None
        temp = getattr(self, "ocr_region_temp_by_page", None)
        targets = list(getattr(self, "ocr_region_target_indices", []) or [])
        if not isinstance(temp, dict) or not targets:
            targets = [self.idx]
            self.ocr_region_target_indices = targets
            self.ocr_region_target_label = self.tr_ui("현재 맵")
            self.ocr_region_temp_by_page = {self.idx: copy.deepcopy(self.data.get(self.idx, {}).get('ocr_analysis_regions', []) or [])}
            temp = self.ocr_region_temp_by_page
        affected = []
        for i in targets:
            temp.setdefault(i, copy.deepcopy(self.data.get(i, {}).get('ocr_analysis_regions', []) or []))
            temp[i].append(copy.deepcopy(payload))
            affected.append(i)
        if self.idx not in temp:
            temp[self.idx] = copy.deepcopy(self.data.get(self.idx, {}).get('ocr_analysis_regions', []) or [])
            temp[self.idx].append(copy.deepcopy(payload))
            affected.append(self.idx)
        hist = getattr(self, "ocr_region_temp_history", None)
        if not isinstance(hist, list):
            self.ocr_region_temp_history = []
            hist = self.ocr_region_temp_history
        hist.append(affected)
        try:
            self.push_ocr_region_temp_command(before_temp_state, self._copy_ocr_region_temp_state(), reason="OCR 분석 영역 임시 추가")
        except Exception:
            pass
        self.refresh_ocr_region_overlay()
        self.update_undo_redo_buttons()
        self.log(f"➕ OCR 분석 영역 추가: {self._ocr_region_indices_label(targets)}")

    def finish_ocr_analysis_region_selection(self):
        targets = list(getattr(self, "ocr_region_target_indices", []) or [])
        temp = getattr(self, "ocr_region_temp_by_page", None)
        if not isinstance(temp, dict):
            self.set_tool(None)
            return

        box = QMessageBox(self)
        box.setWindowTitle(self.tr_ui("OCR 분석 영역 지정 종료"))
        box.setText(self.tr_ui("OCR 분석 영역 지정을 종료할까요?"))
        box.setInformativeText(self.tr_ui("아직 저장하지 않은 변경사항이 있을 수 있습니다. 종료하면 저장 여부를 한 번 더 선택할 수 있습니다."))
        exit_btn = box.addButton(self.tr_ui("종료하기"), QMessageBox.ButtonRole.AcceptRole)
        keep_btn = box.addButton(self.tr_ui("계속 지정하기"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(keep_btn)
        box.exec()
        if box.clickedButton() is not exit_btn:
            return

        save_box = QMessageBox(self)
        save_box.setWindowTitle(self.tr_ui("OCR 분석 영역 저장"))
        save_box.setText(self.tr_ui("변경한 OCR 분석 영역을 저장할까요?"))
        save_box.setInformativeText(self.tr_ui("저장하지 않고 종료하면 이번에 지정한 OCR 분석 영역은 적용되지 않습니다."))
        save_btn = save_box.addButton(self.tr_ui("저장하고 종료"), QMessageBox.ButtonRole.AcceptRole)
        discard_btn = save_box.addButton(self.tr_ui("저장하지 않고 종료"), QMessageBox.ButtonRole.DestructiveRole)
        save_box.setDefaultButton(save_btn)
        save_box.exec()

        if save_box.clickedButton() is save_btn:
            try:
                self.commit_current_page_ui_to_data(include_mask=False)
            except Exception:
                pass
            before_regions = {}
            after_regions = {}
            for i in targets:
                if i in self.data:
                    before_regions[i] = copy.deepcopy(self.data.get(i, {}).get('ocr_analysis_regions', []) or [])
                    after_regions[i] = copy.deepcopy(temp.get(i, []) or [])
                    self.data[i]['ocr_analysis_regions'] = copy.deepcopy(after_regions[i])
            try:
                self.push_ocr_analysis_region_command(
                    before_regions,
                    after_regions,
                    reason="OCR 분석 범위 지정",
                    page_indices=targets,
                )
            except Exception:
                pass
            self.auto_save_project()
            self.log(f"💾 OCR 분석 영역 저장: {self._ocr_region_indices_label(targets)}")
        else:
            self.log("↩️ OCR 분석 영역 변경사항 폐기")

        self.ocr_region_temp_by_page = None
        self.ocr_region_temp_history = []
        self.ocr_region_target_indices = []
        self.ocr_region_target_label = ""
        self.set_tool(None)
        self.refresh_ocr_region_overlay()

    def clear_current_ocr_analysis_regions(self):
        if not getattr(self, "paths", None):
            return
        msg = self.tr_ui("현재 페이지의 OCR 분석 영역만 지울까요?\n\n다른 페이지의 OCR 분석 영역은 유지됩니다.")
        if QMessageBox.question(self, self.tr_ui("현재 페이지 OCR 분석 범위 해제"), msg) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.commit_current_page_ui_to_data(include_mask=False)
        except Exception:
            pass
        curr = self.data.get(self.idx)
        before_regions = {self.idx: copy.deepcopy(curr.get('ocr_analysis_regions', []) or [])} if isinstance(curr, dict) else {}
        after_regions = {self.idx: []} if isinstance(curr, dict) else {}
        if isinstance(curr, dict):
            curr['ocr_analysis_regions'] = []
            try:
                self.push_ocr_analysis_region_command(
                    before_regions,
                    after_regions,
                    reason="현재 페이지 OCR 분석 범위 해제",
                    page_indices=[self.idx],
                )
            except Exception:
                pass
        temp = getattr(self, "ocr_region_temp_by_page", None)
        if isinstance(temp, dict):
            temp[self.idx] = []
            self.ocr_region_temp_history = []
        self.auto_save_project()
        self.refresh_ocr_region_overlay()
        try:
            QApplication.processEvents()
        except Exception:
            pass
        self.log("🧹 현재 페이지 OCR 분석 범위를 해제했습니다. 다른 페이지의 영역은 유지됩니다.")

    def clear_all_ocr_analysis_regions(self):
        if not getattr(self, "paths", None):
            return
        msg = self.tr_ui("모든 페이지의 OCR 분석 영역을 지울까요?\n\n지우면 OCR은 다시 전체 화면을 분석합니다.")
        if QMessageBox.question(self, self.tr_ui("OCR 분석 범위 해제"), msg) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.commit_current_page_ui_to_data(include_mask=False)
        except Exception:
            pass
        before_regions = {}
        after_regions = {}
        for page_idx, curr in list(self.data.items()):
            if isinstance(curr, dict):
                before_regions[page_idx] = copy.deepcopy(curr.get('ocr_analysis_regions', []) or [])
                after_regions[page_idx] = []
                curr['ocr_analysis_regions'] = []
        try:
            self.push_ocr_analysis_region_command(
                before_regions,
                after_regions,
                reason="OCR 분석 범위 해제",
                page_indices=list(before_regions.keys()),
            )
        except Exception:
            pass
        temp = getattr(self, "ocr_region_temp_by_page", None)
        if isinstance(temp, dict):
            for key in list(temp.keys()):
                temp[key] = []
            self.ocr_region_temp_history = []
        self.auto_save_project()
        try:
            self.view.clear_ocr_region_overlay()
        except Exception:
            pass
        self.refresh_ocr_region_overlay()
        try:
            QApplication.processEvents()
        except Exception:
            pass
        self.log("🧹 OCR 분석 범위를 해제했습니다. 이제 전체 화면을 분석합니다.")

    def undo_last_ocr_analysis_region_temp(self):
        temp = getattr(self, "ocr_region_temp_by_page", None)
        hist = getattr(self, "ocr_region_temp_history", None)
        if not isinstance(temp, dict) or not hist:
            return False
        affected = hist.pop()
        changed = False
        for i in affected or []:
            try:
                if i in temp and temp[i]:
                    temp[i].pop()
                    changed = True
            except Exception:
                pass
        if changed:
            self.refresh_ocr_region_overlay()
            self.update_undo_redo_buttons()
            self.log("↩️ OCR 분석 영역 1개 취소")
        return changed

    def _indices_have_ocr_analysis_regions(self, indices):
        for i in indices or []:
            try:
                curr = self.data.get(int(i), {}) if hasattr(self, "data") else {}
                if isinstance(curr, dict) and curr.get('ocr_analysis_regions'):
                    return True
            except Exception:
                continue
        return False

    def confirm_ocr_analysis_regions_before_run(self, indices):
        if not self._indices_have_ocr_analysis_regions(indices):
            return True
        msg = self.tr_ui("지정된 OCR 분석 영역이 있습니다. 지정된 영역만 분석할까요?")
        detail = self.tr_ui("아니오를 누르면 분석을 취소합니다. 전체 화면을 분석하려면 먼저 OCR 분석 범위 지정을 해제해 주세요.")
        box = QMessageBox(self)
        box.setWindowTitle(self.tr_ui("OCR 분석 영역 확인"))
        box.setText(msg)
        box.setInformativeText(detail)
        yes_btn = box.addButton(self.tr_ui("실행하기"), QMessageBox.ButtonRole.AcceptRole)
        no_btn = box.addButton(self.tr_ui("취소"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(yes_btn)
        box.exec()
        return box.clickedButton() is yes_btn

    def _rect_edges_from_item(self, item):
        try:
            x, y, w, h = [float(v) for v in (item.get('rect') or [0, 0, 0, 0])[:4]]
            return x, y, x + max(0.0, w), y + max(0.0, h)
        except Exception:
            return 0.0, 0.0, 0.0, 0.0

    def _rect_overlap_area_for_items(self, a, b):
        ax1, ay1, ax2, ay2 = self._rect_edges_from_item(a)
        bx1, by1, bx2, by2 = self._rect_edges_from_item(b)
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0
        return (ix2 - ix1) * (iy2 - iy1)

    def _rect_center_inside_mask(self, item, mask):
        if mask is None:
            return False
        try:
            h, w = mask.shape[:2]
            x1, y1, x2, y2 = self._rect_edges_from_item(item)
            cx = max(0, min(w - 1, int(round((x1 + x2) / 2))))
            cy = max(0, min(h - 1, int(round((y1 + y2) / 2))))
            if mask[cy, cx] > 0:
                return True
            rx1 = max(0, min(w - 1, int(round(x1))))
            ry1 = max(0, min(h - 1, int(round(y1))))
            rx2 = max(0, min(w, int(round(x2))))
            ry2 = max(0, min(h, int(round(y2))))
            if rx2 <= rx1 or ry2 <= ry1:
                return False
            crop = mask[ry1:ry2, rx1:rx2]
            return bool(crop.size and cv2.countNonZero(crop) > 0)
        except Exception:
            return False

    def _merge_mask_by_ocr_regions(self, old_mask, new_mask, region_mask):
        if region_mask is None:
            return new_mask
        if isinstance(new_mask, np.ndarray):
            base_shape = new_mask.shape[:2]
        elif isinstance(old_mask, np.ndarray):
            base_shape = old_mask.shape[:2]
        else:
            return new_mask
        if not isinstance(old_mask, np.ndarray):
            old = np.zeros_like(new_mask) if isinstance(new_mask, np.ndarray) else np.zeros(base_shape, dtype=np.uint8)
        else:
            old = old_mask.copy()
        if old.shape[:2] != base_shape:
            old = cv2.resize(old, (base_shape[1], base_shape[0]), interpolation=cv2.INTER_NEAREST)
        if not isinstance(new_mask, np.ndarray):
            new = np.zeros_like(old)
        else:
            new = new_mask.copy()
            if new.shape[:2] != base_shape:
                new = cv2.resize(new, (base_shape[1], base_shape[0]), interpolation=cv2.INTER_NEAREST)
        rm = region_mask
        if rm.shape[:2] != base_shape:
            rm = cv2.resize(rm, (base_shape[1], base_shape[0]), interpolation=cv2.INTER_NEAREST)
        out = old.copy()
        sel = rm > 0
        out[sel] = new[sel]
        return out

    def merge_ocr_analysis_region_results(self, page_idx, new_data, new_mask_merge, new_mask_inpaint, ori_img=None):
        curr = self.data.get(page_idx, {}) if hasattr(self, "data") else {}
        regions = copy.deepcopy(curr.get('ocr_analysis_regions', []) or []) if isinstance(curr, dict) else []
        old_data = copy.deepcopy(curr.get('data', []) or []) if isinstance(curr, dict) else []
        if not regions or not old_data:
            return new_data, new_mask_merge, new_mask_inpaint
        try:
            if isinstance(ori_img, np.ndarray):
                h, w = ori_img.shape[:2]
            elif isinstance(new_mask_merge, np.ndarray):
                h, w = new_mask_merge.shape[:2]
            elif isinstance(curr.get('ori'), np.ndarray):
                h, w = curr.get('ori').shape[:2]
            else:
                return new_data, new_mask_merge, new_mask_inpaint
            region_mask = self.engine._ocr_regions_to_mask(regions, w, h)
        except Exception:
            region_mask = None
        if region_mask is None:
            return new_data, new_mask_merge, new_mask_inpaint

        new_items = copy.deepcopy(new_data or [])
        old_in_region = [idx for idx, item in enumerate(old_data) if self._rect_center_inside_mask(item, region_mask)]
        new_in_region = [idx for idx, item in enumerate(new_items) if self._rect_center_inside_mask(item, region_mask)]
        if not old_in_region:
            # 기존 번호가 없는 새 영역이면 새 OCR 결과를 뒤에 붙인다.
            merged = copy.deepcopy(old_data)
            max_id = 0
            for item in merged:
                try:
                    max_id = max(max_id, int(item.get('id') or 0))
                except Exception:
                    pass
            for ni in new_in_region:
                max_id += 1
                item = copy.deepcopy(new_items[ni])
                item['id'] = max_id
                merged.append(item)
            mm = self._merge_mask_by_ocr_regions(curr.get('mask_merge'), new_mask_merge, region_mask)
            mi = self._merge_mask_by_ocr_regions(curr.get('mask_inpaint'), new_mask_inpaint, region_mask)
            return merged, mm, mi

        used_new = set()
        merged = []
        for idx, old_item in enumerate(old_data):
            if idx not in old_in_region:
                merged.append(copy.deepcopy(old_item))
                continue
            best_idx = None
            best_score = 0.0
            for ni in new_in_region:
                if ni in used_new:
                    continue
                ni_item = new_items[ni]
                ov = self._rect_overlap_area_for_items(old_item, ni_item)
                ax1, ay1, ax2, ay2 = self._rect_edges_from_item(old_item)
                bx1, by1, bx2, by2 = self._rect_edges_from_item(ni_item)
                old_area = max(1.0, (ax2 - ax1) * (ay2 - ay1))
                new_area = max(1.0, (bx2 - bx1) * (by2 - by1))
                score = ov / max(1.0, min(old_area, new_area))
                if score > best_score:
                    best_score = score
                    best_idx = ni
            if best_idx is not None and best_score >= 0.08:
                used_new.add(best_idx)
                updated = copy.deepcopy(old_item)
                old_id = old_item.get('id')
                old_trans = old_item.get('translated_text')
                for k, v in copy.deepcopy(new_items[best_idx]).items():
                    if k in ('id', 'translated_text'):
                        continue
                    updated[k] = v
                updated['id'] = old_id
                if old_trans is not None:
                    updated['translated_text'] = old_trans
                merged.append(updated)
            else:
                # 재OCR 결과가 없더라도 기존 번호/라인은 삭제하지 않는다.
                merged.append(copy.deepcopy(old_item))

        max_id = 0
        for item in merged:
            try:
                max_id = max(max_id, int(item.get('id') or 0))
            except Exception:
                pass
        for ni in new_in_region:
            if ni in used_new:
                continue
            max_id += 1
            item = copy.deepcopy(new_items[ni])
            item['id'] = max_id
            merged.append(item)

        mm = self._merge_mask_by_ocr_regions(curr.get('mask_merge'), new_mask_merge, region_mask)
        mi = self._merge_mask_by_ocr_regions(curr.get('mask_inpaint'), new_mask_inpaint, region_mask)
        self.log("🔁 지정 영역 OCR 결과를 기존 분석 데이터에 병합했습니다.")
        return merged, mm, mi

    def _ocr_provider_options(self):
        """Return the same OCR providers that are available in API Settings.

        Lite and Local share this dialog, so Local-only OCR providers must not
        appear in Lite Quick OCR.
        """
        options = [
            ("CLOVA OCR", "clova"),
            ("Google Vision OCR", "google_vision"),
        ]
        try:
            from ysb.editions.current import is_local_edition
            if is_local_edition():
                options.extend([
                    ("LOCAL Paddle OCR", "local_paddle_ocr"),
                    ("LOCAL Manga OCR", "local_manga_ocr"),
                ])
        except Exception:
            pass
        return options

    def _quick_ocr_provider_values(self):
        return [value for _label, value in self._ocr_provider_options()]

    def _ocr_language_options_for_quick(self, provider):
        provider = str(provider or "clova")
        if provider == "google_vision":
            return [("영어", "en"), ("일본어", "ja"), ("중국어", "zh"), ("한국어", "ko")]
        if provider == "local_paddle_ocr":
            return [("일본어", "ja"), ("영어", "en"), ("한국어", "ko"), ("중국어", "zh")]
        if provider == "local_manga_ocr":
            return [("일본어", "ja")]
        return [("일본어", "ja"), ("중국어", "zh"), ("한국어", "ko")]

    def _quick_ocr_provider_from_options(self):
        candidates = [
            str((getattr(self, "app_options", {}) or {}).get("quick_ocr_provider") or ""),
            str(getattr(self.api_settings, "selected_ocr_provider", "clova") or "clova"),
            "clova",
        ]
        allowed = set(self._quick_ocr_provider_values())
        for provider in candidates:
            if provider in allowed:
                return provider
        values = self._quick_ocr_provider_values()
        return values[0] if values else "clova"

    def _quick_ocr_language_from_options(self):
        return str((getattr(self, "app_options", {}) or {}).get("quick_ocr_language") or (self._current_ocr_language_value() if hasattr(self, "_current_ocr_language_value") else "ja") or "ja")

    def _quick_ocr_shortcut_conflict_label(self, seq_text):
        seq_text = str(seq_text or "").strip()
        if not seq_text:
            return ""
        try:
            target_seq = key_sequence_from_text(seq_text)
        except Exception:
            return ""
        for key, value in list(getattr(self.shortcut_settings, "shortcuts", {}).items()):
            if key == "quick_ocr_execute":
                continue
            if not getattr(self.shortcut_settings, "enabled", {}).get(key, True):
                continue
            try:
                other_seq = key_sequence_from_text(str(value or ""))
                if other_seq and not other_seq.isEmpty() and other_seq.matches(target_seq) == QKeySequence.SequenceMatch.ExactMatch:
                    return self.standard_shortcut_label(key) if hasattr(self, "standard_shortcut_label") else str(key)
            except Exception:
                continue
        for macro in getattr(self.shortcut_settings, "macros", []) or []:
            if not macro.get("enabled", True):
                continue
            try:
                other_seq = key_sequence_from_text(str(macro.get("shortcut", "") or ""))
                if other_seq and not other_seq.isEmpty() and other_seq.matches(target_seq) == QKeySequence.SequenceMatch.ExactMatch:
                    return str(macro.get("name") or "매크로")
            except Exception:
                continue
        return ""

    def request_open_quick_ocr_dialog(self):
        """Open Quick OCR settings after the active menu has fully closed."""
        if bool(getattr(self, "tktool_phase2_enabled", False)):
            try:
                self.log("⛔ 쯔꾸르붕이에서는 빠른 OCR 설정을 사용하지 않습니다.")
            except Exception:
                pass
            return
        try:
            self.audit_boundary_event("QUICK_OCR_DIALOG_REQUEST", page_idx=getattr(self, "idx", None), mode=(self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else None), throttle_ms=50)
        except Exception:
            pass
        try:
            timer = getattr(self, "_tooltip_timer", None)
            if timer is not None:
                timer.stop()
            self._tooltip_target = None
            self._tooltip_html = ""
            self._tooltip_visible_target = None
            # Do not call QToolTip.hideText() here.  On Windows, doing so while a
            # QMenu action is closing can crash inside Qt.  Only hide our custom
            # tooltip label, then open the dialog after a short defer.
            popup = getattr(self, "_tooltip_popup", None)
            if popup is not None:
                popup.hide()
        except Exception:
            pass

        def _open():
            try:
                self.open_quick_ocr_dialog()
            except Exception as e:
                try:
                    self.audit_boundary_event("QUICK_OCR_DIALOG_OPEN_ERROR", error=str(e), throttle_ms=50)
                except Exception:
                    pass
                try:
                    QMessageBox.warning(self, self.tr_ui("빠른 OCR 오류"), self.tr_ui("빠른 OCR 설정창을 여는 중 오류가 발생했습니다.") + f"\n\n{e}")
                except Exception:
                    pass

        try:
            QTimer.singleShot(80, _open)
        except Exception:
            _open()

    def open_quick_ocr_dialog(self):
        try:
            self.audit_boundary_event("QUICK_OCR_DIALOG_OPEN_ENTER", page_idx=getattr(self, "idx", None), mode=(self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else None), memory=memory_text(), throttle_ms=50)
        except Exception:
            pass
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("빠른 OCR"))
        dlg.resize(660, 430)
        try:
            dlg.setStyleSheet(self.settings_dialog_style())
        except Exception:
            pass

        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(self.tr_ui("빠른 OCR"), dlg)
        title.setObjectName("SettingsTitle")
        root.addWidget(title)

        desc = QLabel(self.tr_ui("빠른 OCR은 지정된 단축키를 사용할 때만 동작합니다. Ctrl+J는 이 설정창을 여는 단축키입니다."), dlg)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        root.addWidget(desc)

        form_box = QFrame(dlg)
        form_box.setObjectName("SettingsItem")
        form_layout = QVBoxLayout(form_box)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(12)

        def add_setting_row(title_text, description_text, editor):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)
            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)
            item_title = QLabel(self.tr_ui(title_text), dlg)
            item_title.setObjectName("SettingsItemTitle")
            item_desc = QLabel(self.tr_ui(description_text), dlg)
            item_desc.setObjectName("SettingsDescription")
            item_desc.setWordWrap(True)
            text_box.addWidget(item_title)
            text_box.addWidget(item_desc)
            row.addLayout(text_box, 1)
            row.addWidget(editor, 0)
            form_layout.addLayout(row)

        cb_provider = QComboBox(dlg)
        for label, value in self._ocr_provider_options():
            cb_provider.addItem(self.tr_ui(label), value)
        self.set_combo_current_data(cb_provider, self._quick_ocr_provider_from_options())

        cb_lang = QComboBox(dlg)

        def reload_langs():
            provider = cb_provider.currentData() or "clova"
            old = cb_lang.currentData()
            cb_lang.blockSignals(True)
            cb_lang.clear()
            for label, value in self._ocr_language_options_for_quick(provider):
                cb_lang.addItem(self.tr_ui(label), value)
            self.set_combo_current_data(cb_lang, old or self._quick_ocr_language_from_options())
            cb_lang.blockSignals(False)

        cb_provider.currentIndexChanged.connect(lambda *_: reload_langs())
        reload_langs()

        add_setting_row(
            "OCR 모델",
            "빠른 OCR 실행에 사용할 OCR 모델을 선택합니다.",
            cb_provider,
        )
        add_setting_row(
            "언어",
            "빠른 OCR 실행에 사용할 인식 언어를 선택합니다.",
            cb_lang,
        )

        seq_widget = QWidget(dlg)
        seq_row = QHBoxLayout(seq_widget)
        seq_row.setContentsMargins(0, 0, 0, 0)
        seq_row.setSpacing(8)
        seq_edit = ConfirmingKeySequenceEdit(dlg)
        seq_edit.setMinimumWidth(170)
        try:
            seq_edit.setKeySequence(self.shortcut_settings.seq("quick_ocr_execute"))
        except Exception:
            seq_edit.setKeySequence(QKeySequence(""))
        btn_clear = QPushButton(self.tr_ui("비우기"), dlg)
        btn_clear.clicked.connect(seq_edit.clear)
        seq_row.addWidget(seq_edit, 1)
        seq_row.addWidget(btn_clear, 0)
        add_setting_row(
            "빠른 OCR 실행 단축키",
            "이 단축키를 누르면 바로 드래그 선택 모드로 들어갑니다. 빠른 OCR은 이 단축키로만 실제 실행됩니다.",
            seq_widget,
        )

        shortcut_row = QHBoxLayout()
        opener_seq = self.shortcut_settings.seq("work_quick_ocr").toString(QKeySequence.SequenceFormat.NativeText)
        shortcut_row.addWidget(QLabel(f"{self.tr_ui('설정창 단축키')}: {opener_seq or '-'}", dlg))
        shortcut_row.addStretch(1)
        shortcut_btn = QPushButton(self.tr_ui("단축키 관리 열기"), dlg)
        shortcut_btn.clicked.connect(lambda checked=False: self.open_shortcut_settings_dialog())
        shortcut_row.addWidget(shortcut_btn)
        form_layout.addLayout(shortcut_row)

        root.addWidget(form_box)
        root.addStretch(1)

        def apply_quick_ocr_settings():
            try:
                clean_seq = sequence_without_confirm_keys(seq_edit.keySequence())
                clean_text = key_sequence_to_portable(clean_seq).strip()
                current_text = key_sequence_to_portable(seq_edit.keySequence()).strip()
                if clean_text != current_text:
                    seq_edit.blockSignals(True)
                    try:
                        seq_edit.setKeySequence(clean_seq)
                    finally:
                        seq_edit.blockSignals(False)
                seq_text = clean_text
            except Exception:
                seq_text = key_sequence_to_portable(seq_edit.keySequence()).strip()
            conflict = self._quick_ocr_shortcut_conflict_label(seq_text)
            if conflict:
                QMessageBox.warning(
                    dlg,
                    self.tr_ui("단축키 충돌"),
                    self.tr_ui("이미 사용 중인 단축키입니다.") + f"\n\n{conflict}: {seq_text}",
                )
                return False

            self.app_options["quick_ocr_provider"] = cb_provider.currentData() or "clova"
            self.app_options["quick_ocr_language"] = cb_lang.currentData() or "ja"
            self.save_app_options_cache()

            try:
                self.shortcut_settings.enabled["quick_ocr_execute"] = bool(seq_text)
                self.shortcut_settings.shortcuts["quick_ocr_execute"] = seq_text
                ShortcutSettingsStore.save(self.shortcut_settings)
                self.shortcut_label_map = shortcut_label_map()
                self.apply_shortcuts()
            except Exception as e:
                QMessageBox.warning(dlg, self.tr_ui("단축키 저장 오류"), str(e))
                return False

            self.log(f"🔎 빠른 OCR 설정 저장: {cb_provider.currentText()} / {cb_lang.currentText()} / {seq_text or '단축키 없음'}")
            return True

        def on_ok():
            if apply_quick_ocr_settings():
                dlg.accept()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("닫기"))
        buttons.accepted.connect(on_ok)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)

        try:
            result = dlg.exec()
        finally:
            try:
                self.audit_boundary_event("QUICK_OCR_DIALOG_CLOSED", throttle_ms=50)
            except Exception:
                pass
        if result == QDialog.DialogCode.Accepted:
            self.show_ok_notice("빠른 OCR 설정 저장 완료", "빠른 OCR 설정이 저장되었습니다.")

    def _quick_ocr_popup_style(self):
        if str(getattr(self, "ui_theme", "dark") or "dark").lower() == "light":
            return (
                "QLabel { background:#ffffff; color:#111827; "
                "border:1px solid #D1C9CE; border-radius:0px; "
                "padding:6px 8px; font-size:12px; }"
            )
        return (
            "QLabel { background:#242329; color:#ffffff; "
            "border:1px solid #555056; border-radius:0px; "
            "padding:6px 8px; font-size:12px; }"
        )

    def show_quick_ocr_result_popup(self, text):
        text = str(text or "").strip()
        if not text:
            return
        try:
            popup = getattr(self, "quick_ocr_result_popup", None)
            if popup is None:
                popup = QLabel(self)
                popup.setObjectName("quickOcrResultPopup")
                popup.setWordWrap(True)
                popup.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                popup.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
                popup.hide()
                self.quick_ocr_result_popup = popup
            popup.setStyleSheet(self._quick_ocr_popup_style())
            popup.setText(text)
            popup.setMaximumWidth(520)
            popup.adjustSize()
            local = self.mapFromGlobal(QCursor.pos() + QPoint(16, 18))
            x = max(4, min(local.x(), max(4, self.width() - popup.width() - 4)))
            y = max(4, min(local.y(), max(4, self.height() - popup.height() - 4)))
            popup.move(x, y)
            popup.show()
            popup.raise_()
            try:
                self.audit_top_level_widgets("quick_ocr_popup", throttle_ms=1000)
            except Exception:
                pass
        except Exception:
            # 빠른 OCR 결과 표시는 보조 UI라서 실패해도 OCR 자체는 막지 않는다.
            pass

    def hide_quick_ocr_result_popup(self):
        try:
            popup = getattr(self, "quick_ocr_result_popup", None)
            if popup is not None:
                popup.hide()
        except Exception:
            pass

    def start_quick_ocr_selection(self):
        if bool(getattr(self, "tktool_phase2_enabled", False)):
            try:
                self.log("⛔ 쯔꾸르붕이에서는 빠른 OCR을 사용하지 않습니다.")
            except Exception:
                pass
            return
        if not getattr(self, "paths", None):
            QMessageBox.information(self, self.tr_ui("이미지 없음"), self.tr_ui("먼저 프로젝트에 이미지를 불러와 주세요."))
            return
        if not self.ensure_engine_ready():
            return
        self.quick_ocr_provider = self._quick_ocr_provider_from_options()
        self.quick_ocr_language = self._quick_ocr_language_from_options()
        self.quick_ocr_latest_text = ""
        self.quick_ocr_drag_active = False
        self.set_tool('quick_ocr')
        self.log("🔎 빠른 OCR: 마우스를 누른 채 영역을 고정하면 OCR을 실행합니다.")

    def begin_quick_ocr_drag(self):
        self.quick_ocr_drag_active = True
        self.quick_ocr_latest_text = ""
        self.quick_ocr_worker_busy = False
        self.quick_ocr_active_request_id = None
        self.hide_quick_ocr_result_popup()

    def run_quick_ocr_region_live(self, rect_norm, request_id=None, image_path=None, source="main"):
        if bool(getattr(self, "tktool_phase2_enabled", False)):
            try:
                self.log("⛔ 쯔꾸르붕이에서는 빠른 OCR을 사용하지 않습니다.")
            except Exception:
                pass
            return
        if not rect_norm or not getattr(self, "quick_ocr_drag_active", False):
            return
        if getattr(self, "quick_ocr_worker_busy", False):
            return
        target_idx = self.idx
        provider = getattr(self, "quick_ocr_provider", None) or self._quick_ocr_provider_from_options()
        language = getattr(self, "quick_ocr_language", None) or self._quick_ocr_language_from_options()
        self.quick_ocr_worker_busy = True
        self.quick_ocr_active_request_id = request_id
        self.quick_ocr_active_source = source or "main"
        self.log("🔎 빠른 OCR 실행 중...")
        input_path = image_path or self.get_inpainting_input_path(target_idx)
        self.quick_ocr_worker = QuickOCRWorker(
            self.engine,
            input_path,
            copy.deepcopy(rect_norm),
            provider=provider,
            language=language,
        )
        self.quick_ocr_worker.log.connect(self.log)
        self.quick_ocr_worker.finished.connect(lambda text, error=None, rid=request_id, src=source: self.on_quick_ocr_finished(text, error, rid, src))
        self.quick_ocr_worker.start()

    def run_quick_ocr_region(self, rect_norm):
        # 구버전 호출 호환용. 빠른 OCR은 이제 마우스를 누른 상태에서만 실행된다.
        self.run_quick_ocr_region_live(rect_norm, request_id=None)

    def on_quick_ocr_finished(self, text, error=None, request_id=None, source="main"):
        self.quick_ocr_worker_busy = False
        if error:
            if getattr(self, "quick_ocr_drag_active", False):
                QMessageBox.warning(self, self.tr_ui("빠른 OCR 오류"), str(error))
            return
        # 사용자가 아직 마우스를 누르고 있고, OCR 요청 이후 영역이 바뀌지 않은 경우에만 표시한다.
        try:
            if not getattr(self, "quick_ocr_drag_active", False):
                return
            if str(source or "main") == "source_compare":
                current_revision = getattr(self, "source_compare_quick_ocr_revision", None)
                current_rect = copy.deepcopy(getattr(self, "source_compare_quick_ocr_current_rect_norm", None))
            else:
                current_revision = getattr(self.view, "quick_ocr_revision", None)
                current_rect = copy.deepcopy(getattr(self.view, "quick_ocr_current_rect_norm", None))
            if request_id is not None and current_revision != request_id:
                # OCR 중에 사용자가 영역을 다시 움직였으면 오래된 결과는 버리고,
                # 현재 유지 중인 영역으로 한 번 더 실행을 시도한다.
                if current_rect:
                    QTimer.singleShot(0, lambda rn=current_rect, rid=current_revision, src=source: self.run_quick_ocr_region_live(rn, request_id=rid, source=src))
                return
        except Exception:
            return
        text = str(text or "").strip()
        self.quick_ocr_latest_text = text
        if text:
            # QToolTip은 시간이 지나면 자동으로 사라지므로 사용하지 않는다.
            # 빠른 OCR 결과는 마우스를 떼기 전까지 유지되는 전용 팝업으로 표시한다.
            self.show_quick_ocr_result_popup(text)
            self.log(f"🔎 빠른 OCR 결과: {text}")
        else:
            self.show_quick_ocr_result_popup(self.tr_ui("인식된 텍스트가 없습니다."))
            self.log("⚠️ 빠른 OCR에서 인식된 텍스트가 없습니다.")

    def finish_quick_ocr_drag(self):
        text = str(getattr(self, "quick_ocr_latest_text", "") or "").strip()
        self.quick_ocr_drag_active = False
        self.quick_ocr_active_request_id = None
        if text:
            QApplication.clipboard().setText(text)
            self.log(f"📋 빠른 OCR 결과를 클립보드에 복사했습니다: {text}")
        self.hide_quick_ocr_result_popup()
        try:
            QToolTip.hideText()
        except Exception:
            pass
        self.set_tool(None)

    def clear_source_compare_quick_ocr_preview(self):
        try:
            item = getattr(self, "source_compare_quick_ocr_preview_item", None)
            if item is not None and hasattr(self, "source_compare_scene"):
                self.source_compare_scene.removeItem(item)
        except Exception:
            pass
        self.source_compare_quick_ocr_preview_item = None

    def _source_compare_norm_rect_from_scene(self, rect):
        try:
            scene_rect = self.source_compare_scene.sceneRect()
            w = float(scene_rect.width())
            h = float(scene_rect.height())
            if w <= 0 or h <= 0:
                return None
            left = float(scene_rect.left())
            top = float(scene_rect.top())
            x1 = max(left, min(left + w, float(rect.left())))
            y1 = max(top, min(top + h, float(rect.top())))
            x2 = max(left, min(left + w, float(rect.right())))
            y2 = max(top, min(top + h, float(rect.bottom())))
            if x2 <= x1 or y2 <= y1:
                return None
            return [(x1 - left) / w, (y1 - top) / h, (x2 - left) / w, (y2 - top) / h]
        except Exception:
            return None

    def source_compare_quick_ocr_rect_payload(self, end_pos):
        if getattr(self, "source_compare_quick_ocr_start", None) is None:
            return None
        try:
            rect = QRectF(self.source_compare_quick_ocr_start, end_pos).normalized()
            return self._source_compare_norm_rect_from_scene(rect)
        except Exception:
            return None

    def draw_source_compare_quick_ocr_preview(self, end_pos):
        self.clear_source_compare_quick_ocr_preview()
        try:
            start = getattr(self, "source_compare_quick_ocr_start", None)
            if start is None or not hasattr(self, "source_compare_scene"):
                return
            rect = QRectF(start, end_pos).normalized()
            if rect.width() < 2 or rect.height() < 2:
                return
            pen = QPen(QColor(70, 135, 220, 220), 2)
            brush = QBrush(QColor(80, 160, 255, 70))
            item = self.source_compare_scene.addRect(rect, pen, brush)
            item.setZValue(87)
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.source_compare_quick_ocr_preview_item = item
        except Exception:
            pass

    def _schedule_source_compare_quick_ocr_hold_check(self, end_pos):
        rect_norm = self.source_compare_quick_ocr_rect_payload(end_pos)
        old_rect = copy.deepcopy(getattr(self, "source_compare_quick_ocr_current_rect_norm", None))
        if not rect_norm:
            if old_rect is not None:
                self.source_compare_quick_ocr_current_rect_norm = None
                self.source_compare_quick_ocr_revision = int(getattr(self, "source_compare_quick_ocr_revision", 0) or 0) + 1
            return
        changed = True
        try:
            changed = self.view._quick_ocr_rect_changed_significantly(old_rect, rect_norm)
        except Exception:
            changed = old_rect != rect_norm
        if old_rect is not None and not changed:
            return
        self.source_compare_quick_ocr_current_rect_norm = copy.deepcopy(rect_norm)
        self.source_compare_quick_ocr_revision = int(getattr(self, "source_compare_quick_ocr_revision", 0) or 0) + 1
        try:
            latest = str(getattr(self, "quick_ocr_latest_text", "") or "").strip()
            if latest:
                self.show_quick_ocr_result_popup(latest)
        except Exception:
            pass
        try:
            timer = getattr(self, "source_compare_quick_ocr_hold_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._trigger_source_compare_quick_ocr_if_still_holding)
                self.source_compare_quick_ocr_hold_timer = timer
            timer.start(200)
        except Exception:
            pass

    def _trigger_source_compare_quick_ocr_if_still_holding(self):
        if getattr(getattr(self, "view", None), "draw_mode", None) != "quick_ocr":
            return
        if not getattr(self, "source_compare_quick_ocr_drawing", False):
            return
        rect_norm = copy.deepcopy(getattr(self, "source_compare_quick_ocr_current_rect_norm", None))
        if not rect_norm:
            return
        revision = int(getattr(self, "source_compare_quick_ocr_revision", 0) or 0)
        if revision == int(getattr(self, "source_compare_quick_ocr_last_requested_revision", -1) or -1):
            return
        self.source_compare_quick_ocr_last_requested_revision = revision
        self.run_quick_ocr_region_live(rect_norm, request_id=revision, source="source_compare")

    def handle_source_compare_quick_ocr_event(self, event):
        try:
            if getattr(getattr(self, "view", None), "draw_mode", None) != "quick_ocr":
                return False
            if not self.source_compare_is_visible():
                return False
            et = event.type()
            if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.source_compare_quick_ocr_drawing = True
                self.source_compare_quick_ocr_start = self.source_compare_view.mapToScene(event.pos())
                self.source_compare_quick_ocr_current_rect_norm = None
                self.source_compare_quick_ocr_revision = int(getattr(self, "source_compare_quick_ocr_revision", 0) or 0) + 1
                self.source_compare_quick_ocr_last_requested_revision = -1
                try:
                    timer = getattr(self, "source_compare_quick_ocr_hold_timer", None)
                    if timer is not None:
                        timer.stop()
                except Exception:
                    pass
                self.quick_ocr_active_source = "source_compare"
                self.begin_quick_ocr_drag()
                self.draw_source_compare_quick_ocr_preview(self.source_compare_quick_ocr_start)
                return True
            if et == QEvent.Type.MouseMove and getattr(self, "source_compare_quick_ocr_drawing", False):
                now = self.source_compare_view.mapToScene(event.pos())
                self.draw_source_compare_quick_ocr_preview(now)
                self._schedule_source_compare_quick_ocr_hold_check(now)
                return True
            if et == QEvent.Type.MouseButtonRelease and getattr(self, "source_compare_quick_ocr_drawing", False):
                self.source_compare_quick_ocr_drawing = False
                self.source_compare_quick_ocr_start = None
                self.source_compare_quick_ocr_current_rect_norm = None
                try:
                    timer = getattr(self, "source_compare_quick_ocr_hold_timer", None)
                    if timer is not None:
                        timer.stop()
                except Exception:
                    pass
                self.clear_source_compare_quick_ocr_preview()
                self.finish_quick_ocr_drag()
                return True
        except Exception:
            return False
        return False

    def reset_mode_to_original(self):
        """
        새 프로젝트/프로젝트 열기 시 이전 작업 탭 상태가 섞이지 않도록
        기본 작업 탭으로 강제 이동한다.
        """
        if bool(getattr(self, "tktool_phase1_enabled", False)):
            # 쯔꾸르붕이에서는 원본/분석/마스크 탭을 노출하지 않고 최종결과 기준만 사용한다.
            self.last_mode = 4
            self.cb_mode.blockSignals(True)
            try:
                if self.cb_mode.count() >= 5:
                    self.cb_mode.setCurrentIndex(4)
                elif self.cb_mode.count() > 0:
                    self.cb_mode.setCurrentIndex(self.cb_mode.count() - 1)
            finally:
                self.cb_mode.blockSignals(False)
            return

        self.last_mode = 0
        self.cb_mode.blockSignals(True)
        try:
            self.cb_mode.setCurrentIndex(0)
        finally:
            self.cb_mode.blockSignals(False)

    def cycle_work_tab(self):
        """쯔꾸르붕이에서는 YSB식 작업탭 전환을 사용하지 않는다.

        호환 호출이 들어오면 대사표 다음 항목 이동으로만 처리한다.
        """
        if hasattr(self, "navigate_tktool_dialogue_by_tab"):
            self.navigate_tktool_dialogue_by_tab(backwards=False)
        return

    def load(self):
        try:
            self.audit_boundary_event("LOAD_ENTER", stack=True)
        except Exception:
            pass
        # load/ref_tab/mode_chg 직후 delayed view undo가 실제 편집처럼 dirty를 찍는 것을 막는다.
        try:
            self._suppress_view_dirty_until = __import__("time").time() + 0.9
        except Exception:
            pass
        if not self.paths:
            self.idx = 0
            if hasattr(self, "btn_page"):
                self.btn_page.setText("0 / 0")
            self.refresh_page_tabs()
            try:
                if hasattr(self, "view") and self.view is not None:
                    self.view.set_image(None)
            except Exception:
                pass
            try:
                self.ref_tab()
            except Exception:
                pass
            self.update_page_presence_interlocks()
            self.update_undo_redo_buttons()
            return

        if self.idx < 0:
            self.idx = 0
        if self.idx >= len(self.paths):
            self.idx = len(self.paths) - 1
        try:
            if hasattr(self, "activate_page_workbench"):
                self.activate_page_workbench(self.idx, None, clear_undo_on_page_change=True)
        except Exception:
            pass
        try:
            if not self.sync_page_tab_current_only():
                self.refresh_page_tabs()
        except Exception:
            self.refresh_page_tabs()
        self.update_page_presence_interlocks()
        p = self.paths[self.idx]
        try:
            self.update_page_position_label_for_current_tab_layer()
        except Exception:
            self.btn_page.setText(f"{self.idx + 1} / {len(self.paths)}")

        if self.idx not in self.data:
            self.data[self.idx] = {
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
                'clean_path': None,
                'working_source': None,
                'working_source_path': None,
                'final_paint': None,
                'final_paint_path': None,
                'final_paint_above': None,
                'final_paint_above_path': None,
                'ocr_analysis_regions': [],
            }
        curr_page = self.data[self.idx]
        try:
            self.sync_text_effect_preview_checkbox_for_current_page()
        except Exception:
            try:
                self.text_effect_preview_enabled = True
            except Exception:
                pass
        try:
            current_mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else -1
        except Exception:
            current_mode = -1

        # 일반 대사 프리뷰가 꺼져 있으면 현재 페이지 이미지/마스크/프리뷰 캐시를
        # 읽지 않는다. 오른쪽 표만 구성하고 왼쪽은 검은 화면으로 유지한다.
        maker_preview_suppressed = False
        try:
            maker_preview_suppressed = bool(
                hasattr(self, "_is_current_maker_page")
                and self._is_current_maker_page()
                and hasattr(self, "is_maker_preview_enabled")
                and not self.is_maker_preview_enabled()
            )
        except Exception:
            maker_preview_suppressed = False
        if maker_preview_suppressed:
            try:
                self.ref_tab()
            except Exception:
                pass
            try:
                self._clear_maker_normal_preview_to_black(reason="page_load_preview_disabled")
            except Exception:
                pass
            try:
                self.update_maker_database_mode_bar()
            except Exception:
                pass
            return

        try:
            self.ensure_page_runtime_loaded(
                self.idx,
                include_ori=True,
                include_heavy=bool(current_mode == 4 or curr_page.get('use_inpainted_as_source') or curr_page.get('clean_path') or curr_page.get('working_source_path') or curr_page.get('final_paint_path') or curr_page.get('final_paint_above_path')),
                include_masks=bool(current_mode in (2, 3)),
            )
        except Exception:
            if curr_page.get('ori') is None and not curr_page.get('use_inpainted_as_source'):
                curr_page['ori'] = cv2.imdecode(np.fromfile(p, np.uint8), 1)
            try:
                self.touch_page_image_cache(self.idx)
                self.trim_page_image_cache(keep_indices=[self.idx])
            except Exception:
                pass
            if current_mode in (2, 3):
                try:
                    self.ensure_page_masks_loaded(self.idx)
                    self.touch_page_mask_cache(self.idx)
                    self.trim_page_mask_cache(keep_indices=[self.idx])
                except Exception:
                    pass

        self.set_mask_toggle_safely(bool(self.data[self.idx].get('mask_toggle_enabled', self.mask_toggle_enabled)))

        # load() 중 mode_chg()가 실행되면 뷰어에 이전 맵 마스크가 남아 있을 수 있다.
        # 이때 자동 저장이 끼면 다른 페이지 마스크가 덮이므로 로딩 플래그로 차단한다.
        prev_loading = self.is_page_loading
        self.is_page_loading = True
        try:
            self.ref_tab()
            self.mode_chg(self.cb_mode.currentIndex())
        finally:
            self.is_page_loading = prev_loading
        try:
            self.schedule_progressive_page_load(self.idx)
        except Exception:
            pass

    def is_light_theme(self):
        return str(getattr(self, "ui_theme", THEME_DARK) or THEME_DARK).lower() == THEME_LIGHT

    def table_row_color(self, checked):
        # 우측 텍스트 표 행 색상은 테마에 따라 따로 관리한다.
        # 체크 해제 행은 작업 제외/비활성 표시이므로, 파란 음영 대신 Warm Graphite + 아주 약한 와인 톤으로 둔다.
        if self.is_light_theme():
            return QColor("#ffffff") if checked else QColor("#FBF5F6")
        return QColor("#171719") if checked else QColor("#211B1F")

    def table_text_color(self, checked=True):
        if self.is_light_theme():
            return QColor("#202124") if checked else QColor("#6F666D")
        return QColor("#E8E1E6") if checked else QColor("#A99FA5")

    def table_current_row_color(self):
        # Maker row highlight is visual only.  The real table selection remains
        # cell/range based, but every row touched by selected cells is filled so
        # the user can read each row as one dialogue object.
        return QColor("#F5E8EA") if self.is_light_theme() else QColor("#5B3136")

    def table_current_row_text_color(self):
        return QColor("#202124") if self.is_light_theme() else QColor("#FFFFFF")

    def _paint_maker_table_row_marker_state(self, row, marked=False):
        """Paint one Maker table row as selected/current or normal.

        Qt still selects cells.  This helper only paints the full row touched by
        those cells, and ESC/invalid selection restores it to its normal color.
        """
        try:
            table = getattr(self, "tab", None)
            if table is None:
                return False
            row = int(row)
            if row < 0 or row >= table.rowCount():
                return False
            if row == 0:
                self.paint_all_row_header()
                return True
            if marked:
                bg = self.table_current_row_color()
                fg = self.table_current_row_text_color()
                for c in range(table.columnCount()):
                    cell = table.item(row, c)
                    if cell:
                        cell.setBackground(bg)
                        cell.setForeground(fg)
                widget = table.cellWidget(row, 1)
                if widget:
                    widget.setStyleSheet(self.table_check_widget_style(bg))
            else:
                self.set_table_row_visual(row, True if self._is_maker_text_table_mode() else self.get_table_check_state(row))
            return True
        except Exception:
            return False

    def _maker_table_selected_marker_rows(self):
        """Return Maker table rows touched by the current real cell selection.

        Large drag/range selections can expose thousands of selected indexes.
        For Maker tables we only need row numbers, so prefer selectedRanges()
        and expand rows once.  This keeps multi-select as a light text-table
        operation instead of making selectionChanged walk every selected cell.
        """
        rows = set()
        try:
            table = getattr(self, "tab", None)
            if table is None:
                return rows
            try:
                ranges = list(table.selectedRanges() or [])
            except Exception:
                ranges = []
            if ranges:
                row_count = int(table.rowCount())
                for rg in ranges:
                    try:
                        top = max(1, int(rg.topRow()))
                        bottom = min(row_count - 1, int(rg.bottomRow()))
                    except Exception:
                        continue
                    if bottom >= top:
                        rows.update(range(top, bottom + 1))
                return rows
            for idx in table.selectedIndexes() or []:
                try:
                    row = int(idx.row())
                except Exception:
                    continue
                if row > 0:
                    rows.add(row)
        except Exception:
            pass
        return rows

    def refresh_maker_table_current_row_marker(self):
        """Update Maker row-marker state without touching cell/widget data.

        Selection is a text-table operation.  Store only the selected row ids and
        ask the viewport to repaint its lightweight overlay.  No item background,
        foreground, checkbox stylesheet, preview, cache, or scene work belongs here.
        """
        try:
            if not self._is_maker_text_table_mode():
                return False
            table = getattr(self, "tab", None)
            if table is None:
                return False
            current_rows = set(self._maker_table_selected_marker_rows() or set())
            self._maker_table_current_marker_rows = current_rows
            self._maker_table_current_marker_row = min(current_rows) if current_rows else -1
            try:
                table._ysb_selected_marker_rows = set(current_rows)
            except Exception:
                pass
            try:
                table.viewport().update()
            except Exception:
                pass
            return True
        except Exception:
            return False


    def table_header_color(self):
        return QColor("#F0EAED") if self.is_light_theme() else QColor("#141416")

    def table_header_text_color(self):
        return QColor("#202124") if self.is_light_theme() else QColor("#CBC4C9")

    def table_check_widget_style(self, color):
        if self.is_light_theme():
            return f"QWidget {{ background:{color.name()}; border:none; }} QCheckBox {{ background:transparent; padding:0px; margin:0px; }}"
        return f"QWidget {{ background:{color.name()}; border:none; }} QCheckBox {{ background:transparent; padding:0px; margin:0px; }}"

    def repaint_text_table_theme(self):
        """테마 전환 직후 기존 우측 텍스트 표의 배경/글자색을 다시 칠한다."""
        if not hasattr(self, "tab") or self.tab is None:
            return
        self._table_check_lock = True
        self.tab.blockSignals(True)
        try:
            if self.tab.rowCount() > 0:
                self.clear_native_table_check_item(0)
                self.paint_all_row_header()
            for row in range(1, self.tab.rowCount()):
                self.clear_native_table_check_item(row)
                self.set_table_row_visual(row, True if self._is_maker_text_table_mode() else self.get_table_check_state(row))
            try:
                self._maker_table_current_marker_row = -1
                self._maker_table_current_marker_rows = set()
                if self._is_maker_text_table_mode():
                    self.refresh_maker_table_current_row_marker()
            except Exception:
                pass
        finally:
            self.tab.blockSignals(False)
            self._table_check_lock = False

    def get_table_checkbox(self, row):
        widget = self.tab.cellWidget(row, 1)
        if widget:
            return widget.findChild(QCheckBox)
        return None

    def get_table_check_state(self, row):
        cb = self.get_table_checkbox(row)
        if cb is not None:
            return cb.isChecked()
        item = self.tab.item(row, 1)
        return item is not None and item.checkState() == Qt.CheckState.Checked

    def clear_native_table_check_item(self, row):
        """체크 표시는 cellWidget(QCheckBox) 하나만 사용한다.
        QTableWidgetItem의 CheckStateRole이 남아 있으면 테마 전환 후 기본 체크박스가
        같이 그려져 체크박스가 2개처럼 보일 수 있으므로 항상 제거한다.
        """
        try:
            item = self.tab.item(row, 1)
            if item is None:
                return
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setData(Qt.ItemDataRole.CheckStateRole, None)
        except Exception:
            pass

    def set_table_check_state(self, row, checked):
        cb = self.get_table_checkbox(row)
        if cb is not None:
            cb.blockSignals(True)
            try:
                cb.setChecked(bool(checked))
            finally:
                cb.blockSignals(False)
        self.clear_native_table_check_item(row)

    def make_center_check_widget(self, row, checked):
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        cb = QCheckBox()
        cb.setFixedSize(18, 18)
        cb.setStyleSheet("QCheckBox { background:transparent; padding:0px; margin:0px; } QCheckBox::indicator { width:14px; height:14px; border:1px solid #3A363B; background:#141416; } QCheckBox::indicator:checked { background:#8A4A52; border:1px solid #A85D66; }")
        cb.setChecked(bool(checked))
        cb.stateChanged.connect(lambda state, r=row: self.on_table_check_widget_changed(r, state))
        lay.addStretch()
        lay.addWidget(cb, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch()
        return wrap

    def set_table_row_visual(self, row, checked):
        self.clear_native_table_check_item(row)
        color = self.table_row_color(checked)
        for c in range(self.tab.columnCount()):
            cell = self.tab.item(row, c)
            if cell:
                cell.setBackground(color)
                cell.setForeground(self.table_text_color(checked))
        widget = self.tab.cellWidget(row, 1)
        if widget:
            widget.setStyleSheet(self.table_check_widget_style(color))

    def paint_all_row_header(self):
        self.clear_native_table_check_item(0)
        bg = self.table_header_color()
        fg = self.table_header_text_color()
        for c in range(self.tab.columnCount()):
            cell = self.tab.item(0, c)
            if cell:
                cell.setBackground(bg)
                cell.setForeground(fg)
        widget = self.tab.cellWidget(0, 1)
        if widget:
            widget.setStyleSheet(self.table_check_widget_style(bg))

    def on_table_check_widget_changed(self, row, state):
        if self._table_check_lock:
            return
        self.apply_table_check_state(row, state in (Qt.CheckState.Checked, Qt.CheckState.Checked.value, 2))

    def apply_table_check_state(self, row, is_checked):
        if self.idx not in self.data:
            return

        curr_data = self.data.get(self.idx)
        if not curr_data or 'data' not in curr_data:
            return

        # 체크/상태 변경은 전역 Undo 대상이 아니다.
        # 변경은 즉시 데이터에 반영하고, 되돌림은 명시적 재수정으로 처리한다.

        self._table_check_lock = True
        self.tab.blockSignals(True)
        try:
            if row == 0:
                for i, data_item in enumerate(curr_data['data']):
                    table_row = i + 1
                    data_item['use_inpaint'] = is_checked
                    self.set_table_check_state(table_row, is_checked)
                    self.set_table_row_visual(table_row, is_checked)
                self.set_table_check_state(0, is_checked)
                self.paint_all_row_header()
            else:
                data_index = row - 1
                if data_index < 0 or data_index >= len(curr_data['data']):
                    return
                curr_data['data'][data_index]['use_inpaint'] = is_checked
                self.set_table_check_state(row, is_checked)
                self.set_table_row_visual(row, is_checked)

                all_checked = len(curr_data['data']) > 0 and all(x.get('use_inpaint', True) for x in curr_data['data'])
                self.set_table_check_state(0, all_checked)
                self.paint_all_row_header()
            try:
                self.refresh_maker_translation_summary_header()
            except Exception:
                pass
        finally:
            self.tab.blockSignals(False)
            self._table_check_lock = False

        if self.cb_mode.currentIndex() in [1, 2, 3]:
            self.refresh_boxes_only()
        elif self.cb_mode.currentIndex() == 4:
            self.sync_final_text_visibility_only()

        if row == 0:
            self.log((f"🔄 All check states auto-refreshed: {'ON' if is_checked else 'OFF'}" if self.ui_language == LANG_EN else f"🔄 전체 체크 상태 자동 갱신: {'ON' if is_checked else 'OFF'}"))
        else:
            data_index = row - 1
            if 0 <= data_index < len(curr_data['data']):
                self.log((f"🔄 Check state auto-refreshed: ID {curr_data['data'][data_index].get('id')} = {'ON' if is_checked else 'OFF'}" if self.ui_language == LANG_EN else f"🔄 체크 상태 자동 갱신: ID {curr_data['data'][data_index].get('id')} = {'ON' if is_checked else 'OFF'}"))
        try:
            self.schedule_deferred_auto_save_project()
        except Exception:
            self.auto_save_project()


    def _is_maker_text_table_mode(self):
        """Return True when the right text table should use the Maker/Game columns."""
        try:
            if hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode():
                return True
            return bool(hasattr(self, "_is_current_maker_page") and self._is_current_maker_page())
        except Exception:
            return False

    def _table_text_column(self):
        return 5 if self._is_maker_text_table_mode() else 2

    def _table_translation_column(self):
        return 6 if self._is_maker_text_table_mode() else 3

    def restore_maker_text_table_focus_marker(self, *, focus=True, reason=""):
        """Keep the Maker text table as the keyboard anchor.

        The left pane is now a generated RPG Maker preview, not a text-object
        editing canvas.  After the preview is redrawn Qt may leave focus on the
        graphics view; then Space/Enter/Ctrl+Enter stop reaching the table and the
        selected row no longer shows the expected wine-red bar.  This helper
        reasserts the current row selection without opening an editor.
        """
        try:
            if not self._is_maker_text_table_mode():
                return False
            table = getattr(self, "tab", None)
            if table is None or table.rowCount() <= 1:
                return False
            if bool(getattr(self, "_maker_table_focus_marker_lock", False)):
                return False
            self._maker_table_focus_marker_lock = True
            try:
                row = int(table.currentRow())
                if row < 1:
                    row = 1
                if row >= table.rowCount():
                    row = table.rowCount() - 1
                col = int(table.currentColumn())
                if col < 0 or col >= table.columnCount():
                    col = self._table_translation_column()
                try:
                    table.setCurrentCell(row, col)
                except Exception:
                    pass
                try:
                    # Do not select or fill the row.  The current-cell/focus
                    # outline alone is the Maker single-line translation marker.
                    table.clearSelection()
                except Exception:
                    pass
                try:
                    item = table.item(row, col) or table.item(row, self._table_translation_column())
                    if item is not None:
                        table.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)
                except Exception:
                    pass
                if focus:
                    try:
                        fw = QApplication.focusWidget()
                    except Exception:
                        fw = None
                    # Do not steal focus from an open cell editor or any text input.
                    try:
                        if fw is not None and self.is_text_input_widget(fw):
                            return True
                    except Exception:
                        pass
                    try:
                        table.setFocus(Qt.FocusReason.OtherFocusReason)
                    except Exception:
                        pass
                return True
            finally:
                self._maker_table_focus_marker_lock = False
        except Exception:
            try:
                self._maker_table_focus_marker_lock = False
            except Exception:
                pass
            return False

    def _maker_clean_page_indices(self, page_indices=None):
        cleaned = []
        try:
            if page_indices is None:
                return None
            for x in page_indices:
                try:
                    cleaned.append(int(x))
                except Exception:
                    pass
        except Exception:
            return None
        seen = set()
        out = []
        for x in cleaned:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    def maker_recovery_dir(self):
        try:
            project_dir = getattr(self, "project_dir", None)
            if not project_dir:
                return None
            path = Path(str(project_dir)) / ".recovery"
            path.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            return None

    def append_maker_recovery_event(self, payload):
        """Append a tiny JSONL recovery record for crash recovery without saving the full project."""
        try:
            if not isinstance(payload, dict):
                return False
            root = self.maker_recovery_dir()
            if root is None:
                return False
            session = str(getattr(self, "_maker_recovery_session_id", "") or "session")
            path = root / f"maker_recovery_{session}.jsonl"
            rec = dict(payload)
            rec.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
            rec.setdefault("page_idx", int(getattr(self, "idx", 0) or 0))
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            return True
        except Exception:
            return False

    def clear_maker_recovery_events(self):
        try:
            root = self.maker_recovery_dir()
            if root is None or not root.exists():
                return
            for p in root.glob("maker_recovery_*.jsonl"):
                try:
                    p.unlink()
                except Exception:
                    pass
        except Exception:
            pass

    def has_maker_writeback_dirty(self):
        try:
            return bool(getattr(self, "_maker_game_writeback_dirty_pages", set()) or getattr(self, "_maker_game_writeback_dirty_reasons", set()))
        except Exception:
            return False

    def mark_maker_writeback_dirty(self, page_indices=None, reason="maker_edit", schedule_save=False):
        """Mark edited pages as waiting for manual Ctrl+S project save/game writeback."""
        try:
            if page_indices is None:
                page_indices = [int(getattr(self, "idx", 0) or 0)]
        except Exception:
            page_indices = None
        pages = self._maker_clean_page_indices(page_indices) if hasattr(self, "_maker_clean_page_indices") else None
        try:
            if not hasattr(self, "_maker_game_writeback_dirty_pages"):
                self._maker_game_writeback_dirty_pages = set()
            if not hasattr(self, "_maker_game_writeback_dirty_reasons"):
                self._maker_game_writeback_dirty_reasons = set()
            if pages:
                self._maker_game_writeback_dirty_pages.update(int(x) for x in pages)
            else:
                # page_indices=None은 전체 반영 대기 의미로 남긴다.
                self._maker_game_writeback_dirty_reasons.add("ALL")
            if reason:
                self._maker_game_writeback_dirty_reasons.add(str(reason))
        except Exception:
            pass
        try:
            self.has_unsaved_changes = True
        except Exception:
            pass
        try:
            self.append_maker_recovery_event({
                "type": "maker_dirty",
                "pages": sorted(int(x) for x in (pages or [])),
                "reason": str(reason or "maker_edit"),
            })
        except Exception:
            pass
        try:
            if hasattr(self, "audit_boundary_event"):
                self.audit_boundary_event(
                    "MAKER_WRITEBACK_DIRTY_MARK",
                    dirty_pages=sorted(int(x) for x in getattr(self, "_maker_game_writeback_dirty_pages", set()) or set()),
                    reason=str(reason or ""),
                )
        except Exception:
            pass
        try:
            self.sync_maker_writeback_ui_state()
        except Exception:
            pass
        if schedule_save:
            try:
                self.schedule_deferred_auto_save_project(1200)
            except Exception:
                pass

    def clear_maker_writeback_dirty(self, page_indices=None, *, save_state=True):
        try:
            pages = self._maker_clean_page_indices(page_indices) if page_indices is not None else None
            if not hasattr(self, "_maker_game_writeback_dirty_pages"):
                self._maker_game_writeback_dirty_pages = set()
            if pages is None:
                self._maker_game_writeback_dirty_pages.clear()
                self._maker_game_writeback_dirty_reasons = set()
            else:
                for pidx in pages:
                    self._maker_game_writeback_dirty_pages.discard(int(pidx))
                if not self._maker_game_writeback_dirty_pages:
                    self._maker_game_writeback_dirty_reasons = set()
        except Exception:
            pass
        try:
            self.sync_maker_writeback_ui_state()
        except Exception:
            pass
        if save_state:
            try:
                self.schedule_deferred_auto_save_project(800)
            except Exception:
                pass

    def sync_maker_writeback_ui_state(self):
        dirty = bool(self.has_maker_writeback_dirty()) if hasattr(self, "has_maker_writeback_dirty") else False
        running = getattr(self, "_maker_writeback_worker", None) is not None
        try:
            has_project = bool(self._maker_project_has_imported_game()) if hasattr(self, "_maker_project_has_imported_game") else bool(getattr(self, "project_dir", None))
        except Exception:
            has_project = bool(getattr(self, "project_dir", None))
        enabled = bool(has_project and not running)
        label = self.tr_ui("프로젝트 저장") if hasattr(self, "tr_ui") else "프로젝트 저장"
        if dirty:
            label = label + " *"
        tip = self.tr_ui("현재 작업 폴더와 작업용 게임 JSON을 저장합니다. 단축키: Ctrl+S") if hasattr(self, "tr_ui") else "현재 작업 폴더와 작업용 게임 JSON을 저장합니다. 단축키: Ctrl+S"
        if running:
            tip = self.tr_ui("프로젝트 저장 작업이 진행 중입니다.") if hasattr(self, "tr_ui") else "프로젝트 저장 작업이 진행 중입니다."
        try:
            action = (getattr(self, "actions", {}) or {}).get("project_save")
            if action is not None:
                action.setText(label)
                action.setToolTip(tip)
                action.setStatusTip(tip)
                action.setWhatsThis(tip)
                action.setEnabled(enabled)
        except Exception:
            pass
        try:
            action = (getattr(self, "actions", {}) or {}).get("work_apply_maker_game_json")
            if action is not None:
                action.setEnabled(False)
                action.setVisible(False)
        except Exception:
            pass
        try:
            btn = getattr(self, "btn_maker_apply_game", None)
            if btn is not None:
                btn.setVisible(False)
                btn.setEnabled(False)
        except Exception:
            pass

    def _maker_pending_writeback_page_indices(self):
        try:
            pages = sorted(int(x) for x in (getattr(self, "_maker_game_writeback_dirty_pages", set()) or set()))
            if pages:
                return pages
        except Exception:
            pass
        return None

    def _apply_maker_live_writeback_now(self, *, page_indices=None, reason="live_edit", log_result=False):
        """Compatibility shim: live writeback is intentionally disabled.

        Editing now only marks Maker pages as pending.  Actual working game JSON
        files are updated only by Ctrl+S / [프로젝트 저장].  Keeping this shim lets
        older edit routes call the old name without accidentally saving JSON or
        causing recursive project-store writes during table editing.
        """
        try:
            self.mark_maker_writeback_dirty(page_indices=page_indices, reason=reason)
        except Exception:
            pass
        return None

    def apply_maker_writeback_to_game_action(self):
        # 구버전 액션 호환: 게임 반영은 프로젝트 저장(Ctrl+S)으로 통합되었다.
        try:
            self.save_project()
        except Exception as e:
            try:
                QMessageBox.warning(self, self.tr_ui("프로젝트 저장 실패"), str(e))
            except Exception:
                pass

    def apply_maker_writeback_to_game_async(self, *, page_indices=None, reason="manual_apply", after_done=None):
        """Apply pending Maker edits to game JSON in a QThread with progress dialog."""
        try:
            if getattr(self, "_maker_writeback_worker", None) is not None:
                return False
            project_dir = getattr(self, "project_dir", None)
            if not project_dir:
                return False
            pages = self._maker_clean_page_indices(page_indices)
            if pages is None:
                pages = self._maker_pending_writeback_page_indices()
            # Deep-copy data before the worker starts so the UI thread can continue editing safely.
            data_snapshot = copy.deepcopy(getattr(self, "data", {}) or {})
            progress = QProgressDialog(self.tr_ui("작업용 게임 JSON을 저장하는 중..."), "", 0, 0, self)
            progress.setWindowTitle(self.tr_ui("프로젝트 저장"))
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setMinimumDuration(0)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            try:
                progress.setCancelButton(None)
            except Exception:
                pass
            progress.show()
            worker = MakerWritebackWorker(project_dir, data_snapshot, page_indices=pages, backup=False)
            self._maker_writeback_worker = worker
            self._maker_writeback_progress = progress
            self._maker_writeback_after_done = after_done
            self.sync_maker_writeback_ui_state()
            try:
                self.audit_boundary_event("MAKER_WRITEBACK_ASYNC_START", dirty_pages=pages, reason=str(reason or ""))
            except Exception:
                pass

            def _finish_ok(summary):
                try:
                    if getattr(self, "_maker_writeback_progress", None) is not None:
                        self._maker_writeback_progress.close()
                except Exception:
                    pass
                self._maker_writeback_progress = None
                self._maker_writeback_worker = None
                try:
                    self.clear_maker_writeback_dirty(page_indices=pages, save_state=False)
                except Exception:
                    pass
                try:
                    written = summary.get("written_units", summary.get("written", summary.get("translated", summary.get("updated", "?")))) if isinstance(summary, dict) else "?"
                    touched_maps = summary.get("touched_maps", []) if isinstance(summary, dict) else []
                    touched = len(touched_maps) if isinstance(touched_maps, (list, tuple, set)) else summary.get("touched_files", summary.get("files", summary.get("pages", "?")))
                    self.log(f"🎮 게임 반영 완료: 텍스트 {written}개 / 맵 {touched}개")
                except Exception:
                    pass
                try:
                    self.schedule_deferred_auto_save_project(200)
                except Exception:
                    pass
                try:
                    self.sync_maker_writeback_ui_state()
                except Exception:
                    pass
                cb = getattr(self, "_maker_writeback_after_done", None)
                self._maker_writeback_after_done = None
                if callable(cb):
                    try:
                        cb(True)
                    except Exception:
                        pass

            def _finish_error(message):
                try:
                    if getattr(self, "_maker_writeback_progress", None) is not None:
                        self._maker_writeback_progress.close()
                except Exception:
                    pass
                self._maker_writeback_progress = None
                self._maker_writeback_worker = None
                try:
                    self.sync_maker_writeback_ui_state()
                except Exception:
                    pass
                try:
                    QMessageBox.warning(self, self.tr_ui("프로젝트 저장 실패"), str(message or ""))
                except Exception:
                    pass
                cb = getattr(self, "_maker_writeback_after_done", None)
                self._maker_writeback_after_done = None
                if callable(cb):
                    try:
                        cb(False)
                    except Exception:
                        pass

            try:
                worker.progress.connect(lambda msg: progress.setLabelText(str(msg or "")))
                worker.finished.connect(_finish_ok)
                worker.error.connect(_finish_error)
                worker.start()
            except Exception:
                self._maker_writeback_worker = None
                self._maker_writeback_progress = None
                raise
            return True
        except Exception as e:
            try:
                self.log(f"❌ 게임 JSON 반영 시작 실패: {e}")
            except Exception:
                pass
            try:
                self.sync_maker_writeback_ui_state()
            except Exception:
                pass
            return False

    def prompt_maker_writeback_before_leave(self, title=None):
        """Return 'apply', 'discard', or 'cancel' for pending project save/writeback."""
        try:
            if not self.has_maker_writeback_dirty():
                return "discard"
        except Exception:
            return "discard"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title or self.tr_ui("프로젝트 저장 확인"))
        message = self.tr_ui("저장하지 않은 변경사항이 있습니다.\n저장할까요?")
        box.setText(message)
        apply_btn = box.addButton(self.tr_ui("저장"), QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton(self.tr_ui("저장 안 함"), QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(self.tr_ui("취소"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(apply_btn)
        try:
            fm = QFontMetrics(box.font())
            text_w = max(fm.horizontalAdvance(line) for line in str(message).splitlines() if line)
            button_w = 0
            for btn in (apply_btn, discard_btn, cancel_btn):
                bw = max(86, fm.horizontalAdvance(btn.text()) + 36)
                btn.setMinimumWidth(bw)
                button_w += bw
            # QMessageBox sometimes keeps a too-small native width after custom styling.
            # Reserve room for icon, margins, and button spacing so Korean labels are not clipped.
            box.setMinimumWidth(max(420, text_w + 150, button_w + 110))
        except Exception:
            box.setMinimumWidth(420)
        box.exec()
        clicked = box.clickedButton()
        if clicked is apply_btn:
            return "apply"
        if clicked is discard_btn:
            return "discard"
        return "cancel"

    def _advance_table_editor_after_enter(self, row=None, col=None, stay_current=False):
        """After committing a table QTextEdit with Enter, move to the same cell below.

        Shift+Enter remains a line break through MultilineDelegate.  Plain Enter is
        optimized for translation work: commit current cell, select the next text row,
        and immediately reopen the editor when that cell is editable.
        """
        try:
            table = getattr(self, "tab", None)
            if table is None:
                return
            row = int(row if row is not None else table.currentRow())
            col = int(col if col is not None else table.currentColumn())
            if row < 1:
                row = max(1, row)
            next_row = row + 1
            if bool(stay_current):
                next_row = row
            elif next_row >= table.rowCount():
                next_row = row
            if next_row < 1 or next_row >= table.rowCount():
                return
            db_mode = bool(hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
            if db_mode:
                # DB mode now mirrors the normal Maker/map text table.
                editable_cols = {6, 7, 5, 2, 1}
                if col not in editable_cols:
                    col = self._table_translation_column()
            else:
                editable_cols = {6, 7, 2, 1} if self._is_maker_text_table_mode() else {2, 3}
                if col not in editable_cols:
                    col = self._table_translation_column()
            item = table.item(next_row, col)
            if item is None:
                item = QTableWidgetItem("")
                table.setItem(next_row, col, item)
            table.setCurrentCell(next_row, col)
            table.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
            if bool(stay_current):
                try:
                    if bool(hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode()):
                        self.commit_current_database_ui_to_layer()
                    else:
                        self.apply_current_maker_row_without_move()
                except Exception:
                    pass
                return
            try:
                table.editItem(item)
            except Exception:
                pass
        except Exception:
            pass


    def begin_maker_translation_edit_current_row(self):
        try:
            table = getattr(self, "tab", None)
            if table is None or not self._is_maker_text_table_mode():
                return False
            row = int(table.currentRow())
            if row < 1:
                row = 1
            col = self._table_translation_column()
            item = table.item(row, col)
            if item is None:
                item = QTableWidgetItem("")
                table.setItem(row, col, item)
            table.setCurrentCell(row, col)
            table.setFocus(Qt.FocusReason.ShortcutFocusReason)
            table.editItem(item)
            return True
        except Exception:
            return False

    def apply_current_maker_row_without_move(self):
        """Ctrl+Enter 검수용: 현재 줄을 유지한 채 클론 JSON/프리뷰만 갱신한다."""
        try:
            table = getattr(self, "tab", None)
            if table is None or not self._is_maker_text_table_mode():
                return False
            row_no = int(table.currentRow())
            if row_no < 1:
                return False
            data_index = row_no - 1
            page_idx = int(getattr(self, "idx", 0) or 0)
            page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
            rows = page.get("data") or []
            if data_index < 0 or data_index >= len(rows):
                return False
            trans_col = self._table_translation_column()
            item = table.item(row_no, trans_col)
            new_text = str(item.text() if item is not None else "")
            row = rows[data_index]
            if not isinstance(row, dict):
                return False
            row["translated_text"] = new_text
            row["maker_status"] = self.tr_ui("번역완료") if new_text.strip() else self.tr_ui("미번역")
            if new_text.strip():
                row["maker_translation_origin"] = "manual_edit"
            else:
                row.pop("maker_translation_origin", None)
            try:
                status_item = table.item(row_no, 1)
                if status_item is not None:
                    status_item.setText(str(row.get("maker_status") or ""))
            except Exception:
                pass
            self._apply_maker_live_writeback_now(page_indices=[page_idx], reason="ctrl_enter_stay", log_result=False)
            try:
                table.setCurrentCell(row_no, trans_col)
                table.scrollToItem(table.item(row_no, trans_col), QAbstractItemView.ScrollHint.PositionAtCenter)
            except Exception:
                pass
            try:
                self.finalize_maker_text_data_change([row.get("id")], fields=["translated_text"], page_idx=page_idx, reason="Ctrl+Enter 현재 줄 반영")
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 현재 줄 반영 실패: {e}")
            except Exception:
                pass
            return False

    def parse_maker_single_column_clipboard_blocks(self, text):
        """Parse clipboard text as one-column Excel-like Maker translation cells.

        Blank/whitespace-only lines separate cells.  Newlines inside each
        non-blank block are preserved, so a multi-line RPG Maker dialogue stays
        one translation cell instead of being split line-by-line.
        """
        try:
            text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        except Exception:
            text = ""
        blocks = []
        current = []
        for raw_line in text.split("\n"):
            line = str(raw_line or "").strip()
            if not line:
                if current:
                    blocks.append("\n".join(current).strip())
                    current = []
                continue
            current.append(line)
        if current:
            blocks.append("\n".join(current).strip())
        return [b for b in blocks if str(b or "").strip()]

    def _select_maker_translation_paste_range(self, start_row, end_row, trans_col):
        """Show the pasted target cells after table refresh/writeback work.

        This is visual feedback only.  Keep selection signals and preview rebuilds
        blocked so bulk paste remains a text-to-text operation.
        """
        try:
            table = getattr(self, "tab", None)
            if table is None:
                return False
            start_row = max(0, int(start_row))
            end_row = min(int(end_row), int(table.rowCount()) - 1)
            trans_col = int(trans_col)
            if end_row < start_row or trans_col < 0 or trans_col >= int(table.columnCount()):
                return False
            old_bulk = bool(getattr(self, "_maker_bulk_text_editing", False))
            old_block = table.blockSignals(True)
            old_updates = True
            viewport = None
            viewport_updates = True
            try:
                self._maker_bulk_text_editing = True
                try:
                    old_updates = bool(table.updatesEnabled())
                    table.setUpdatesEnabled(False)
                except Exception:
                    pass
                try:
                    viewport = table.viewport()
                    if viewport is not None:
                        viewport_updates = bool(viewport.updatesEnabled())
                        viewport.setUpdatesEnabled(False)
                except Exception:
                    viewport = None
                table.clearSelection()
                table.setRangeSelected(QTableWidgetSelectionRange(start_row, trans_col, end_row, trans_col), True)
                table.setCurrentCell(start_row, trans_col)
                try:
                    self.refresh_maker_table_current_row_marker()
                except Exception:
                    pass
                try:
                    item0 = table.item(start_row, trans_col)
                    if item0 is not None:
                        table.scrollToItem(item0, QAbstractItemView.ScrollHint.PositionAtCenter)
                except Exception:
                    pass
                try:
                    table.setFocus(Qt.FocusReason.OtherFocusReason)
                except Exception:
                    pass
            finally:
                try:
                    if viewport is not None:
                        viewport.setUpdatesEnabled(viewport_updates)
                except Exception:
                    pass
                try:
                    table.setUpdatesEnabled(old_updates)
                except Exception:
                    pass
                try:
                    table.blockSignals(old_block)
                except Exception:
                    pass
                try:
                    self._maker_bulk_text_editing = old_bulk
                except Exception:
                    pass
                try:
                    if viewport is not None:
                        viewport.update()
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _maker_preview_commit_epoch_value(self):
        try:
            return int(getattr(self, "_maker_preview_commit_epoch", 0) or 0)
        except Exception:
            return 0

    def _invalidate_maker_preview_commits(self, reason="maker_text_mutation"):
        """Invalidate already queued table-preview commits without redrawing anything."""
        try:
            epoch = self._maker_preview_commit_epoch_value() + 1
            self._maker_preview_commit_epoch = int(epoch)
            try:
                self.audit_boundary_event(
                    "MAKER_PREVIEW_COMMIT_INVALIDATED",
                    epoch=int(epoch),
                    reason=str(reason or "maker_text_mutation"),
                )
            except Exception:
                pass
            return int(epoch)
        except Exception:
            return 0

    def _begin_maker_text_mutation(self, reason="maker_text_mutation"):
        """Enter a text-data-only mutation scope.

        While this scope is active, Maker preview entry points must refuse work.
        The epoch bump also invalidates callbacks queued before the mutation.
        """
        try:
            depth = int(getattr(self, "_maker_text_mutation_depth", 0) or 0)
        except Exception:
            depth = 0
        if depth <= 0:
            self._invalidate_maker_preview_commits(reason)
        self._maker_text_mutation_depth = depth + 1
        self._maker_text_mutation_reason = str(reason or "maker_text_mutation")
        try:
            self.audit_boundary_event(
                "MAKER_TEXT_MUTATION_BEGIN",
                depth=int(self._maker_text_mutation_depth),
                reason=str(reason or "maker_text_mutation"),
            )
        except Exception:
            pass
        return int(self._maker_preview_commit_epoch_value())

    def _end_maker_text_mutation(self, reason="maker_text_mutation"):
        try:
            depth = max(0, int(getattr(self, "_maker_text_mutation_depth", 0) or 0) - 1)
        except Exception:
            depth = 0
        self._maker_text_mutation_depth = int(depth)
        if depth <= 0:
            self._maker_text_mutation_reason = ""
        try:
            self.audit_boundary_event(
                "MAKER_TEXT_MUTATION_END",
                depth=int(depth),
                reason=str(reason or "maker_text_mutation"),
                preview_refresh=False,
            )
        except Exception:
            pass
        return depth

    def _is_maker_text_mutation_active(self):
        try:
            return int(getattr(self, "_maker_text_mutation_depth", 0) or 0) > 0
        except Exception:
            return False

    def finalize_maker_text_data_change(self, ids=None, *, fields=None, page_idx=None, reason="메이커 텍스트 변경"):
        """Finalize Maker text data without any preview/table reconstruction path.

        This is the only common finalizer for bulk paste/delete/translation/
        control-code text mutations.  It records dirty/recovery state only.
        """
        try:
            page_idx = int(getattr(self, "idx", 0) if page_idx is None else page_idx)
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        clean_ids = [x for x in (ids or []) if x is not None]
        field_list = [str(x or "") for x in (fields or ["translated_text"])]
        self._invalidate_maker_preview_commits(reason)
        try:
            te = getattr(self, "text_engine", None)
            if te is not None:
                te.mark_dirty(page_idx, clean_ids, field_list)
        except Exception:
            pass
        try:
            if page_idx == int(getattr(self, "idx", 0) or 0):
                self.mark_active_page_dirty("text")
            else:
                pe = getattr(self, "project_engine", None)
                if pe is not None and hasattr(pe, "mark_page_dirty"):
                    pe.mark_page_dirty(page_idx, "text")
        except Exception:
            pass
        try:
            self.has_unsaved_changes = True
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
            kinds.setdefault(int(page_idx), set()).add("text")
        except Exception:
            pass
        try:
            if hasattr(self, "append_maker_recovery_event"):
                self.append_maker_recovery_event({
                    "type": "maker_text_data_change",
                    "page_idx": int(page_idx),
                    "ids": list(clean_ids),
                    "fields": list(field_list),
                    "reason": str(reason or "메이커 텍스트 변경"),
                    "preview_refresh": False,
                })
        except Exception:
            pass
        try:
            self.audit_boundary_event(
                "MAKER_TEXT_DATA_FINALIZED",
                page_idx=int(page_idx),
                ids_count=len(clean_ids),
                fields=",".join(field_list),
                reason=str(reason or "메이커 텍스트 변경"),
                preview_refresh=False,
                table_rebuild=False,
            )
        except Exception:
            pass
        return clean_ids

    def _maker_table_pending_refresh_key(self, page_idx=None, *, db_mode=False):
        """Return a project/page scoped key for deferred table-row refresh state."""
        try:
            if page_idx is None:
                page_idx = getattr(self, "maker_database_idx", 0) if db_mode else getattr(self, "idx", 0)
            page_idx = int(page_idx or 0)
        except Exception:
            page_idx = 0
        try:
            data_scope = id(getattr(self, "data", None))
        except Exception:
            data_scope = 0
        return (int(data_scope), "db" if bool(db_mode) else "page", int(page_idx))

    def _maker_table_pending_refresh_rows(self, page_idx=None, *, db_mode=False):
        try:
            store = getattr(self, "_maker_table_pending_refresh_by_page", None)
            if not isinstance(store, dict):
                return set()
            key = self._maker_table_pending_refresh_key(page_idx, db_mode=db_mode)
            return set(store.get(key) or set())
        except Exception:
            return set()

    def _maker_table_page_has_pending_refresh(self, page_idx=None, *, db_mode=False):
        return bool(self._maker_table_pending_refresh_rows(page_idx, db_mode=db_mode))

    def _sync_maker_table_rows_text_only(self, table_rows, *, page_idx=None, db_mode=False, reason="bulk_text_data_change"):
        """Show current translated text/status immediately without resizing rows.

        Bulk Maker text operations must remain data-first, but the user still needs
        immediate visual confirmation that text was pasted, deleted, translated,
        restored, or undone.  This path updates only the existing table item text
        and status while signals, painting, and automatic row-height calculation
        are suspended.  The row remains pending so a later plain single-row click
        can run resizeRowToContents() for that row only.
        """
        if bool(db_mode):
            return 0
        table = getattr(self, "tab", None)
        if table is None:
            return 0
        try:
            if page_idx is None:
                page_idx = int(getattr(self, "idx", 0) or 0)
            page_idx = int(page_idx or 0)
            if page_idx != int(getattr(self, "idx", 0) or 0):
                return 0
            if not self._is_maker_text_table_mode():
                return 0
        except Exception:
            return 0

        clean_rows = []
        for raw in table_rows or []:
            try:
                row = int(raw)
            except Exception:
                continue
            if row > 0 and row < int(table.rowCount()):
                clean_rows.append(row)
        clean_rows = sorted(set(clean_rows))
        if not clean_rows:
            return 0

        page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
        data_rows = page.get("data") or []
        if not isinstance(data_rows, list):
            return 0

        # ResizeToContents is the expensive part of bulk setText().  Maker map
        # tables use manually sized rows: ref_tab() sizes all rows once on load,
        # and a later plain single-row click sizes only that row.
        try:
            table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        except Exception:
            pass

        old_block = False
        old_updates = True
        viewport = table.viewport()
        old_view_updates = True
        updated = 0
        trans_col = int(self._table_translation_column())
        try:
            old_block = table.blockSignals(True)
            old_updates = bool(table.updatesEnabled())
            old_view_updates = bool(viewport.updatesEnabled()) if viewport is not None else True
            table.setUpdatesEnabled(False)
            if viewport is not None:
                viewport.setUpdatesEnabled(False)
            for table_row in clean_rows:
                data_index = self._maker_data_index_for_table_row(table_row, db_mode=False)
                if data_index < 0 or data_index >= len(data_rows):
                    continue
                row_data = data_rows[data_index]
                if not isinstance(row_data, dict):
                    continue
                text = str(row_data.get("translated_text") or "")
                status = str(row_data.get("maker_status") or (self.tr_ui("번역완료") if text.strip() else self.tr_ui("미번역")))

                item = table.item(table_row, trans_col)
                if item is None:
                    item = self._make_table_item("", editable=True, user_value="")
                    table.setItem(table_row, trans_col, item)
                if str(item.text() or "") != text:
                    item.setText(text)
                if item.data(Qt.ItemDataRole.UserRole) != text:
                    item.setData(Qt.ItemDataRole.UserRole, text)

                status_item = table.item(table_row, 1)
                if status_item is None:
                    status_item = self._make_table_item(status, editable=True, center=True, user_value=status)
                    table.setItem(table_row, 1, status_item)
                else:
                    if str(status_item.text() or "") != status:
                        status_item.setText(status)
                    if status_item.data(Qt.ItemDataRole.UserRole) != status:
                        status_item.setData(Qt.ItemDataRole.UserRole, status)
                updated += 1
        finally:
            try:
                if viewport is not None:
                    viewport.setUpdatesEnabled(old_view_updates)
            except Exception:
                pass
            try:
                table.setUpdatesEnabled(old_updates)
            except Exception:
                pass
            try:
                table.blockSignals(old_block)
            except Exception:
                pass

        try:
            if viewport is not None:
                viewport.update()
        except Exception:
            pass
        try:
            self.refresh_maker_translation_summary_header()
        except Exception:
            pass
        try:
            self.audit_boundary_event(
                "MAKER_TABLE_BULK_TEXT_VISIBLE_SYNCED",
                page_idx=int(page_idx),
                rows_count=int(updated),
                resized=False,
                reason=str(reason or "bulk_text_data_change"),
            )
        except Exception:
            pass
        return int(updated)

    def _mark_maker_table_rows_pending_refresh(self, table_rows, *, page_idx=None, db_mode=False, reason="bulk_text_data_change"):
        """Mark rows whose height still needs a later single-row refresh.

        Bulk text operations update the visible translated text/status immediately
        through a no-resize path, but never calculate row height.  A plain
        single-row click later resizes only that row and clears this pending mark.
        """
        clean = set()
        for raw in table_rows or []:
            try:
                row = int(raw)
            except Exception:
                continue
            if row > 0:
                clean.add(row)
        if not clean:
            return 0
        try:
            store = getattr(self, "_maker_table_pending_refresh_by_page", None)
            if not isinstance(store, dict):
                store = {}
                self._maker_table_pending_refresh_by_page = store
            key = self._maker_table_pending_refresh_key(page_idx, db_mode=db_mode)
            store.setdefault(key, set()).update(clean)
        except Exception:
            return 0
        try:
            self.audit_boundary_event(
                "MAKER_TABLE_BULK_UI_DEFERRED",
                page_idx=int(getattr(self, "idx", 0) if page_idx is None else page_idx),
                rows_count=len(clean),
                db_mode=bool(db_mode),
                reason=str(reason or "bulk_text_data_change"),
            )
        except Exception:
            pass
        try:
            self._sync_maker_table_rows_text_only(
                clean,
                page_idx=page_idx,
                db_mode=bool(db_mode),
                reason=reason,
            )
        except Exception:
            pass
        return len(clean)

    def _clear_maker_table_pending_refresh(self, page_idx=None, *, db_mode=False, table_rows=None):
        try:
            store = getattr(self, "_maker_table_pending_refresh_by_page", None)
            if not isinstance(store, dict):
                return 0
            key = self._maker_table_pending_refresh_key(page_idx, db_mode=db_mode)
            current = set(store.get(key) or set())
            if table_rows is None:
                removed = len(current)
                store.pop(key, None)
                return removed
            remove_rows = set()
            for raw in table_rows or []:
                try:
                    row = int(raw)
                except Exception:
                    continue
                if row > 0:
                    remove_rows.add(row)
            before = len(current)
            current.difference_update(remove_rows)
            if current:
                store[key] = current
            else:
                store.pop(key, None)
            return max(0, before - len(current))
        except Exception:
            return 0

    def sync_maker_table_row_from_data(self, table_row, *, page_idx=None, db_mode=None, resize=True, force=False):
        """Synchronize one visible Maker row from model data and resize only it.

        This is the sole UI synchronization path for rows changed by bulk operations.
        It is called from an explicit plain single-row activation, never from paste,
        Delete, translation, restore, or Undo loops.
        """
        table = getattr(self, "tab", None)
        if table is None:
            return False
        try:
            table_row = int(table_row)
        except Exception:
            return False
        if table_row <= 0 or table_row >= int(table.rowCount()):
            return False
        if db_mode is None:
            try:
                db_mode = bool(hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
            except Exception:
                db_mode = False
        try:
            if page_idx is None:
                page_idx = getattr(self, "maker_database_idx", 0) if db_mode else getattr(self, "idx", 0)
            page_idx = int(page_idx or 0)
        except Exception:
            page_idx = 0
        pending = self._maker_table_pending_refresh_rows(page_idx, db_mode=bool(db_mode))
        needs_data_sync = bool(force or table_row in pending)
        page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
        rows = page.get("data") or []
        data_index = self._maker_data_index_for_table_row(table_row, db_mode=bool(db_mode))
        if data_index < 0 or data_index >= len(rows):
            return False
        row_data = rows[data_index]
        if not isinstance(row_data, dict):
            return False

        old_block = False
        old_updates = True
        try:
            old_block = table.blockSignals(True)
            old_updates = bool(table.updatesEnabled())
            table.setUpdatesEnabled(False)
            if needs_data_sync:
                trans_col = int(self._table_translation_column())
                text = str(row_data.get("translated_text") or "")
                status = str(row_data.get("maker_status") or (self.tr_ui("번역완료") if text.strip() else self.tr_ui("미번역")))
                item = table.item(table_row, trans_col)
                if item is None:
                    item = self._make_table_item("", editable=True, user_value="")
                    table.setItem(table_row, trans_col, item)
                if str(item.text() or "") != text:
                    item.setText(text)
                if item.data(Qt.ItemDataRole.UserRole) != text:
                    item.setData(Qt.ItemDataRole.UserRole, text)
                status_item = table.item(table_row, 1)
                if status_item is None:
                    status_item = self._make_table_item(status, editable=True, center=True, user_value=status)
                    table.setItem(table_row, 1, status_item)
                else:
                    if str(status_item.text() or "") != status:
                        status_item.setText(status)
                    if status_item.data(Qt.ItemDataRole.UserRole) != status:
                        status_item.setData(Qt.ItemDataRole.UserRole, status)
        finally:
            try:
                table.setUpdatesEnabled(old_updates)
            except Exception:
                pass
            try:
                table.blockSignals(old_block)
            except Exception:
                pass

        self._clear_maker_table_pending_refresh(page_idx, db_mode=bool(db_mode), table_rows=[table_row])
        if resize:
            try:
                table.resizeRowToContents(table_row)
            except Exception:
                pass
        try:
            table.viewport().update()
        except Exception:
            pass
        try:
            if not db_mode:
                self.refresh_maker_translation_summary_header()
        except Exception:
            pass
        try:
            self.audit_boundary_event(
                "MAKER_TABLE_SINGLE_ROW_SYNCED",
                page_idx=int(page_idx),
                table_row=int(table_row),
                data_index=int(data_index),
                data_synced=bool(needs_data_sync),
                resized=bool(resize),
            )
        except Exception:
            pass
        return True

    def _maker_translation_selected_table_rows(self, trans_col=None):
        """Return table rows whose translation cells are selected/current."""
        try:
            table = getattr(self, "tab", None)
            if table is None:
                return []
            trans_col = self._table_translation_column() if trans_col is None else int(trans_col)
            rows = set()
            try:
                for idx in table.selectedIndexes() or []:
                    if int(idx.column()) == int(trans_col) and int(idx.row()) > 0:
                        rows.add(int(idx.row()))
            except Exception:
                pass
            if not rows:
                try:
                    r = int(table.currentRow())
                    c = int(table.currentColumn())
                    if r > 0 and c == int(trans_col):
                        rows.add(r)
                except Exception:
                    pass
            return sorted(rows)
        except Exception:
            return []

    def _maker_data_index_for_table_row(self, table_row, *, db_mode=False):
        try:
            table_row = int(table_row)
            if bool(db_mode):
                table = getattr(self, "tab", None)
                if table is not None:
                    try:
                        id_item = table.item(table_row, 0)
                        if id_item is not None:
                            v = id_item.data(Qt.ItemDataRole.UserRole)
                            if v is not None and str(v).strip() != "":
                                return int(v)
                    except Exception:
                        pass
            return int(table_row) - 1
        except Exception:
            return int(table_row) - 1

    def push_maker_table_edit_undo(self, reason, page_idx, changes, *, db_mode=False):
        """Small Maker-table undo stack for spreadsheet-like paste/delete edits.

        쯔꾸르붕이는 전역 Undo를 텍스트 입력칸 로컬 Undo로 제한하고 있어서
        기존 project/page undo는 의도적으로 막힐 수 있다. 하지만 표 셀 붙여넣기/Del은
        일반 편집 동작이므로 별도 소형 스택에 이전 값을 저장한다.
        """
        try:
            clean = []
            for ch in changes or []:
                if not isinstance(ch, dict):
                    continue
                clean.append({
                    "table_row": int(ch.get("table_row", 0) or 0),
                    "data_index": int(ch.get("data_index", -1) or -1),
                    "old_text": str(ch.get("old_text", "") or ""),
                    "new_text": str(ch.get("new_text", "") or ""),
                    "old_status": str(ch.get("old_status", "") or ""),
                    "new_status": str(ch.get("new_status", "") or ""),
                    "old_origin": str(ch.get("old_origin", "") or ""),
                    "new_origin": str(ch.get("new_origin", "") or ""),
                    "id": ch.get("id"),
                })
            if not clean:
                return False
            stack = getattr(self, "_maker_table_edit_undo_stack", None)
            if not isinstance(stack, list):
                stack = []
                self._maker_table_edit_undo_stack = stack
            stack.append({
                "reason": str(reason or "표 셀 편집"),
                "page_idx": int(page_idx),
                "db_mode": bool(db_mode),
                "changes": clean,
            })
            if len(stack) > 80:
                del stack[:-80]
            try:
                self._maker_table_edit_redo_stack = []
            except Exception:
                pass
            try:
                self.update_undo_redo_buttons()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def undo_maker_table_edit_once(self):
        reason = "표 셀 편집 Undo"
        self._begin_maker_text_mutation(reason)
        try:
            stack = getattr(self, "_maker_table_edit_undo_stack", None)
            if not isinstance(stack, list) or not stack:
                return False
            rec = stack.pop()
            page_idx = int(rec.get("page_idx", getattr(self, "idx", 0)) or 0)
            page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
            rows = page.get("data") or []
            if not isinstance(rows, list):
                return False
            changes = list(rec.get("changes") or [])
            changed_ids = []
            changed_table_rows = []
            table = getattr(self, "tab", None)
            db_mode = bool(rec.get("db_mode", False))
            trans_col = self._table_translation_column()
            status_col = 1
            old_block = False
            old_updates = True
            try:
                if db_mode and table is not None:
                    old_block = table.blockSignals(True)
                    old_updates = bool(table.updatesEnabled())
                    table.setUpdatesEnabled(False)
                for ch in changes:
                    data_index = int(ch.get("data_index", -1) or -1)
                    if data_index < 0 or data_index >= len(rows):
                        continue
                    row_data = rows[data_index]
                    if not isinstance(row_data, dict):
                        continue
                    old_text = str(ch.get("old_text", "") or "")
                    old_status = str(ch.get("old_status", "") or "")
                    row_data["translated_text"] = old_text
                    row_data["maker_status"] = old_status or (self.tr_ui("번역완료") if old_text.strip() else self.tr_ui("미번역"))
                    old_origin = str(ch.get("old_origin", "") or "")
                    if old_origin:
                        row_data["maker_translation_origin"] = old_origin
                    else:
                        row_data.pop("maker_translation_origin", None)
                    changed_ids.append(row_data.get("id"))
                    table_row = int(ch.get("table_row", data_index + 1) or data_index + 1)
                    changed_table_rows.append(table_row)
                    if db_mode and table is not None and 0 <= table_row < table.rowCount():
                        item = table.item(table_row, trans_col)
                        if item is None:
                            item = QTableWidgetItem("")
                            table.setItem(table_row, trans_col, item)
                        item.setText(old_text)
                        item.setData(Qt.ItemDataRole.UserRole, old_text)
                        st_item = table.item(table_row, status_col)
                        if st_item is not None:
                            status_text = str(row_data.get("maker_status") or "")
                            st_item.setText(status_text)
                            st_item.setData(Qt.ItemDataRole.UserRole, status_text)
            finally:
                if db_mode and table is not None:
                    try:
                        table.setUpdatesEnabled(old_updates)
                        table.blockSignals(old_block)
                        table.viewport().update()
                    except Exception:
                        pass
            if not db_mode:
                self._mark_maker_table_rows_pending_refresh(
                    changed_table_rows, page_idx=page_idx, db_mode=False, reason="maker_table_cell_undo"
                )
            if db_mode:
                try:
                    self.data[int(page_idx)] = page
                    self.commit_current_database_ui_to_layer()
                    self._finalize_maker_database_page_change(
                        page_idx,
                        changed_ids=changed_ids,
                        fields=["translated_text"],
                        reason="maker_table_cell_undo",
                        refresh_preview=False,
                        writeback=True,
                    )
                except Exception:
                    self.finalize_maker_text_data_change(changed_ids, fields=["translated_text"], page_idx=page_idx, reason=reason)
            else:
                try:
                    self.mark_maker_writeback_dirty(page_indices=[page_idx], reason="maker_table_cell_undo")
                except Exception:
                    pass
                self.finalize_maker_text_data_change(changed_ids, fields=["translated_text"], page_idx=page_idx, reason=reason)
            try:
                self.log(f"↩️ {rec.get('reason') or '표 셀 편집'} 되돌림: {len(changes)}개")
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 표 셀 Undo 실패: {e}")
            except Exception:
                pass
            return False
        finally:
            self._end_maker_text_mutation(reason)

    def clear_maker_translation_cells_for_selection(self, *, reason="Delete 번역문 셀 비우기"):
        """Clear selected Maker translation cells as a data-only mutation."""
        self._begin_maker_text_mutation(reason)
        try:
            table = getattr(self, "tab", None)
            if table is None or not self._is_maker_text_table_mode():
                return False
            db_mode = bool(hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
            page_idx = int((getattr(self, "maker_database_idx", 0) if db_mode else getattr(self, "idx", 0)) or 0)
            page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
            rows = page.get("data") or []
            if not isinstance(rows, list) or not rows:
                return False
            trans_col = self._table_translation_column()
            table_rows = self._maker_translation_selected_table_rows(trans_col)
            if not table_rows:
                return False

            status_col = 1
            changes = []
            changed_ids = []
            lazy_table_ui = not db_mode
            old_bulk = bool(getattr(self, "_maker_bulk_text_editing", False))
            old_block = table.blockSignals(True) if not lazy_table_ui else False
            old_updates = bool(table.updatesEnabled())
            viewport = table.viewport()
            try:
                self._maker_bulk_text_editing = True
                if not lazy_table_ui:
                    table.setUpdatesEnabled(False)
                    if viewport is not None:
                        viewport.setUpdatesEnabled(False)
                for table_row in table_rows:
                    data_index = self._maker_data_index_for_table_row(table_row, db_mode=db_mode)
                    if data_index < 0 or data_index >= len(rows):
                        continue
                    row_data = rows[data_index]
                    if not isinstance(row_data, dict):
                        continue
                    old_text = str(row_data.get("translated_text") or "")
                    old_status = str(row_data.get("maker_status") or "")
                    old_origin = str(row_data.get("maker_translation_origin") or "")
                    if old_text == "":
                        continue
                    row_data["translated_text"] = ""
                    row_data["maker_status"] = self.tr_ui("미번역")
                    row_data.pop("maker_translation_origin", None)
                    changes.append({
                        "table_row": int(table_row),
                        "data_index": int(data_index),
                        "old_text": old_text,
                        "new_text": "",
                        "old_status": old_status,
                        "new_status": str(row_data.get("maker_status") or ""),
                        "old_origin": old_origin,
                        "new_origin": "",
                        "id": row_data.get("id"),
                    })
                    changed_ids.append(row_data.get("id"))
                    if not lazy_table_ui:
                        item = table.item(table_row, trans_col)
                        if item is None:
                            item = QTableWidgetItem("")
                            table.setItem(table_row, trans_col, item)
                        item.setText("")
                        item.setData(Qt.ItemDataRole.UserRole, "")
                        st_item = table.item(table_row, status_col)
                        if st_item is not None:
                            status_text = str(row_data.get("maker_status") or "")
                            st_item.setText(status_text)
                            st_item.setData(Qt.ItemDataRole.UserRole, status_text)
                selected_set = {int(x) for x in table_rows if int(x) > 0}
                self._maker_table_current_marker_rows = set(selected_set)
                self._maker_last_selected_translate_rows = set(selected_set)
            finally:
                if not lazy_table_ui:
                    try:
                        if viewport is not None:
                            viewport.setUpdatesEnabled(True)
                    except Exception:
                        pass
                    try:
                        table.setUpdatesEnabled(old_updates)
                        table.blockSignals(old_block)
                        table.viewport().update()
                    except Exception:
                        pass
                self._maker_bulk_text_editing = old_bulk

            if not changes:
                return False
            self.push_maker_table_edit_undo(reason, page_idx, changes, db_mode=db_mode)
            if lazy_table_ui:
                self._mark_maker_table_rows_pending_refresh(
                    [ch.get("table_row") for ch in changes],
                    page_idx=page_idx,
                    db_mode=False,
                    reason="translation_cells_delete",
                )
            if db_mode:
                try:
                    self.data[int(page_idx)] = page
                    self.commit_current_database_ui_to_layer()
                except Exception:
                    pass
                glossary_touched = any(
                    0 <= int(ch.get("data_index", -1)) < len(rows)
                    and self._is_maker_database_name_row(rows[int(ch.get("data_index", -1))])
                    for ch in changes
                )
                self._finalize_maker_database_page_change(
                    page_idx,
                    changed_ids=changed_ids,
                    fields=["translated_text"],
                    reason="translation_cells_delete",
                    refresh_preview=False,
                    writeback=True,
                    glossary_touched=glossary_touched,
                    show_glossary_log=False,
                )
            else:
                try:
                    self.mark_maker_writeback_dirty(page_indices=[page_idx], reason="translation_cells_delete")
                except Exception:
                    pass
                self.finalize_maker_text_data_change(
                    changed_ids,
                    fields=["translated_text"],
                    page_idx=page_idx,
                    reason=reason,
                )
            try:
                self.audit_boundary_event(
                    "MAKER_TRANSLATION_DELETE_TEXT_ONLY",
                    page_idx=int(page_idx),
                    rows_count=len(table_rows),
                    changed_count=len(changes),
                    selection_preserved=True,
                    preview_refresh=False,
                )
            except Exception:
                pass
            try:
                self.log(f"🧹 번역문 셀 비우기 완료: {len(changes)}개")
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 번역문 셀 비우기 실패: {e}")
            except Exception:
                pass
            return False
        finally:
            self._end_maker_text_mutation(reason)

    def paste_maker_translation_blocks_from_clipboard(self):
        """Paste clipboard blocks as translated_text data only.

        Selection, preview, dialogue overlay, scene, and cache state are never
        recommitted by this operation.  The user sees the new preview only after
        explicitly clicking one dialogue row later.
        """
        reason = "번역문 문단 붙여넣기"
        self._begin_maker_text_mutation(reason)
        try:
            table = getattr(self, "tab", None)
            if table is None or not self._is_maker_text_table_mode():
                return False
            try:
                clipboard_text = QApplication.clipboard().text()
            except Exception:
                clipboard_text = ""
            blocks = self.parse_maker_single_column_clipboard_blocks(clipboard_text)
            if not blocks:
                return False
            db_mode = bool(hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
            page_idx = int((getattr(self, "maker_database_idx", 0) if db_mode else getattr(self, "idx", 0)) or 0)
            page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
            rows = page.get("data") or []
            if not isinstance(rows, list) or not rows:
                return False
            start_row = max(1, int(table.currentRow()))
            trans_col = self._table_translation_column()
            try:
                selected_columns = {int(idx.column()) for idx in table.selectedIndexes()}
            except Exception:
                selected_columns = set()
            try:
                current_col = int(table.currentColumn())
            except Exception:
                current_col = -1
            if current_col != trans_col and trans_col not in selected_columns:
                return False

            changed_ids = []
            undo_changes = []
            applied = 0
            lazy_table_ui = not db_mode
            old_bulk = bool(getattr(self, "_maker_bulk_text_editing", False))
            old_block = table.blockSignals(True) if not lazy_table_ui else False
            old_updates = bool(table.updatesEnabled())
            viewport = table.viewport()
            try:
                self._maker_bulk_text_editing = True
                if not lazy_table_ui:
                    table.setUpdatesEnabled(False)
                    if viewport is not None:
                        viewport.setUpdatesEnabled(False)
                for offset, new_text in enumerate(blocks):
                    table_row = start_row + offset
                    if table_row >= table.rowCount():
                        break
                    data_index = self._maker_data_index_for_table_row(table_row, db_mode=db_mode)
                    if data_index < 0 or data_index >= len(rows):
                        continue
                    row_data = rows[data_index]
                    if not isinstance(row_data, dict):
                        continue
                    new_text = str(new_text or "")
                    old_text = str(row_data.get("translated_text") or "")
                    old_status = str(row_data.get("maker_status") or "")
                    old_origin = str(row_data.get("maker_translation_origin") or "")
                    row_data["translated_text"] = new_text
                    row_data["maker_status"] = self.tr_ui("번역완료") if new_text.strip() else self.tr_ui("미번역")
                    if new_text.strip():
                        row_data["maker_translation_origin"] = "manual_paste"
                    else:
                        row_data.pop("maker_translation_origin", None)
                    undo_changes.append({
                        "table_row": int(table_row),
                        "data_index": int(data_index),
                        "old_text": old_text,
                        "new_text": new_text,
                        "old_status": old_status,
                        "new_status": str(row_data.get("maker_status") or ""),
                        "old_origin": old_origin,
                        "new_origin": str(row_data.get("maker_translation_origin") or ""),
                        "id": row_data.get("id"),
                    })
                    if not lazy_table_ui:
                        item = table.item(table_row, trans_col)
                        if item is None:
                            item = QTableWidgetItem("")
                            table.setItem(table_row, trans_col, item)
                        item.setText(new_text)
                        item.setData(Qt.ItemDataRole.UserRole, new_text)
                        st_item = table.item(table_row, 1)
                        if st_item is None:
                            st_item = QTableWidgetItem("")
                            table.setItem(table_row, 1, st_item)
                        status_text = str(row_data.get("maker_status") or "")
                        st_item.setText(status_text)
                        st_item.setData(Qt.ItemDataRole.UserRole, status_text)
                    if row_data.get("id") is not None:
                        changed_ids.append(row_data.get("id"))
                    applied += 1
            finally:
                if not lazy_table_ui:
                    try:
                        if viewport is not None:
                            viewport.setUpdatesEnabled(True)
                    except Exception:
                        pass
                    try:
                        table.setUpdatesEnabled(old_updates)
                        table.blockSignals(old_block)
                        table.viewport().update()
                    except Exception:
                        pass
                self._maker_bulk_text_editing = old_bulk

            if applied <= 0:
                return False
            self.push_maker_table_edit_undo(reason, page_idx, undo_changes, db_mode=db_mode)
            if lazy_table_ui:
                self._mark_maker_table_rows_pending_refresh(
                    [ch.get("table_row") for ch in undo_changes],
                    page_idx=page_idx,
                    db_mode=False,
                    reason="translation_blocks_paste",
                )
            if db_mode:
                try:
                    self.data[int(page_idx)] = page
                    self.commit_current_database_ui_to_layer()
                except Exception:
                    pass
                glossary_touched = any(
                    0 <= int(ch.get("data_index", -1)) < len(rows)
                    and self._is_maker_database_name_row(rows[int(ch.get("data_index", -1))])
                    for ch in undo_changes
                )
                self._finalize_maker_database_page_change(
                    page_idx,
                    changed_ids=changed_ids,
                    fields=["translated_text"],
                    reason="translation_blocks_paste",
                    refresh_preview=False,
                    writeback=True,
                    glossary_touched=glossary_touched,
                    show_glossary_log=False,
                )
            else:
                try:
                    self.mark_maker_writeback_dirty(page_indices=[page_idx], reason="translation_blocks_paste")
                except Exception:
                    pass
                self.finalize_maker_text_data_change(
                    changed_ids,
                    fields=["translated_text"],
                    page_idx=page_idx,
                    reason=reason,
                )
            try:
                self.audit_boundary_event(
                    "MAKER_TRANSLATION_PASTE_TEXT_ONLY",
                    page_idx=int(page_idx),
                    changed_count=int(applied),
                    selection_preserved=True,
                    preview_refresh=False,
                    translation_origin="manual_paste",
                    line_count_review=False,
                )
            except Exception:
                pass
            try:
                skipped = len(blocks) - applied
                msg = f"📋 번역문 붙여넣기 완료: {applied}개"
                if skipped > 0:
                    msg += f" / 범위 초과 {skipped}개 건너뜀"
                self.log(msg)
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 번역문 붙여넣기 실패: {e}")
            except Exception:
                pass
            return False
        finally:
            self._end_maker_text_mutation(reason)

    def _finalize_maker_database_page_change(self, page_idx=None, *, changed_ids=None, fields=None, reason="maker_database_page_edit", refresh_preview=False, writeback=True, glossary_touched=False, show_glossary_log=False):
        """Persist database page edits to program data and maker_game immediately.

        Database pages are normal Maker project pages.  During normal editing the
        program data is the master, so a DB edit must not stop at the visible
        table: it must update self.data, write the clone JSON, mark the project
        dirty, and save the project store/recovery checkpoint just like dialogue
        edits do.
        """
        try:
            if page_idx is None:
                page_idx = int(getattr(self, "maker_database_idx", getattr(self, "idx", 0)) or 0)
            page_idx = int(page_idx)
        except Exception:
            page_idx = int(getattr(self, "maker_database_idx", 0) or 0)
        changed_ids = [x for x in (changed_ids or []) if x is not None]
        field_list = list(fields or ["translated_text"])
        speaker_layer = False
        try:
            speaker_page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
            speaker_layer = bool(hasattr(self, "_maker_page_is_speaker_page") and self._maker_page_is_speaker_page(speaker_page))
        except Exception:
            speaker_layer = False
        if speaker_layer:
            writeback = False
            glossary_touched = True
            try:
                self.apply_maker_speaker_layer_to_dialogues(page_idx, reason=str(reason or "speaker page edit"))
            except Exception:
                pass
        try:
            page = (getattr(self, "data", {}) or {}).get(page_idx)
            if isinstance(page, dict):
                self.data[page_idx] = page
        except Exception:
            pass
        try:
            self.has_unsaved_changes = True
            self.mark_project_structure_dirty(str(reason or "maker_database_page_edit"))
        except Exception:
            pass
        if writeback:
            try:
                self.mark_maker_writeback_dirty(page_indices=[page_idx], reason="maker_database_page_edit")
            except Exception as e:
                try:
                    self.log(f"⚠️ DB 텍스트 JSON 반영 대기 처리 실패: {e}")
                except Exception:
                    pass
        if glossary_touched:
            try:
                self.refresh_maker_database_auto_glossary_after_name_change(show_log=show_glossary_log, reason=reason)
            except Exception:
                pass
        try:
            # finalize_text_change is also the central project-store persistence
            # path.  It marks the DB page dirty, saves the project store, and
            # schedules the recovery checkpoint.  update_table/refresh_scene are
            # disabled because DB mode has its own table/preview refresh.
            self.finalize_maker_text_data_change(
                changed_ids,
                fields=field_list,
                page_idx=page_idx,
                reason=str(reason or "데이터베이스 변경"),
            )
        except Exception:
            try:
                pe = getattr(self, "project_engine", None)
                if pe is not None and hasattr(pe, "mark_page_dirty"):
                    pe.mark_page_dirty(page_idx, "text")
            except Exception:
                pass
            try:
                pages = getattr(self, "_checkpoint_dirty_pages", None)
                if pages is None:
                    pages = set()
                    self._checkpoint_dirty_pages = pages
                pages.add(page_idx)
                kinds = getattr(self, "_checkpoint_dirty_kinds", None)
                if kinds is None:
                    kinds = {}
                    self._checkpoint_dirty_kinds = kinds
                kinds.setdefault(page_idx, set()).add("text")
            except Exception:
                pass
            try:
                store = getattr(self, "project_store", None)
                if store is not None:
                    self.save_project_store(store, force_full=False)
            except Exception:
                pass
            try:
                self.schedule_deferred_auto_save_project(700)
            except Exception:
                pass
        # DB 편집은 일반 대사와 달리 현재 화면 idx가 DB 페이지와 다를 수 있다.
        # finalize_text_change의 조건부 저장만 믿지 말고 프로젝트 본체에도 한 번 더 즉시 저장한다.
        try:
            store = getattr(self, "project_store", None)
            if store is not None:
                self.save_project_store(store, force_full=False)
        except Exception:
            pass
        try:
            self.schedule_deferred_auto_save_project(700)
        except Exception:
            pass
        return True

    def refresh_maker_database_auto_glossary(self, *, show_log=True):
        """Collect translated database and speaker names into the read-only automatic glossary."""
        try:
            project_dir = getattr(self, "project_dir", None)
            if not project_dir:
                self.app_options[TRANSLATION_AUTO_DB_GLOSSARY_ENTRIES_KEY] = {}
                self.sync_translation_option_cache_to_config()
                return 0
            entries = collect_maker_database_glossary(getattr(self, "data", {}) or {})
            save_maker_database_glossary(project_dir, entries)
            auto_dict = {}
            for entry in entries:
                source = str(entry.get("source") or "").strip()
                target = str(entry.get("target") or "").strip()
                if source and target and source != target:
                    auto_dict[source] = target
            self.app_options[TRANSLATION_AUTO_DB_GLOSSARY_ENTRIES_KEY] = auto_dict
            self.save_app_options_cache()
            self.sync_translation_option_cache_to_config()
            if show_log:
                self.log(self.tr_ui("📚 자동 단어장 갱신: {count}개 / DB name·화자 name 자동 반영 / 현재 번역 청크에 등장한 항목만 사용").format(count=f"{len(auto_dict):,}"))
            return len(auto_dict)
        except Exception as e:
            try:
                self.log(self.tr_ui("⚠️ 자동 단어장 갱신 실패: {error}").format(error=e))
            except Exception:
                pass
            return 0

    def _is_maker_database_name_row(self, row_data):
        """Return True when a row is a Maker database visible name field."""
        try:
            if not isinstance(row_data, dict):
                return False
            meta = row_data.get("maker_text_unit") if isinstance(row_data.get("maker_text_unit"), dict) else {}
            db_field = str((meta or {}).get("db_field") or "").strip().lower()
            db_path_keys = (meta or {}).get("db_path_keys") or []
            try:
                db_last_path = str(list(db_path_keys)[-1]).strip().lower() if db_path_keys else ""
            except Exception:
                db_last_path = ""
            return db_field == "name" or db_field.endswith(".name") or db_last_path == "name"
        except Exception:
            return False

    def refresh_maker_database_auto_glossary_after_name_change(self, *, show_log=False, reason="db_name_changed"):
        """Refresh the automatic name glossary after a database or speaker name changes.

        Database ``name`` fields and the independent speaker layer both feed the
        same read-only automatic glossary so names remain consistent everywhere.
        """
        try:
            count = self.refresh_maker_database_auto_glossary(show_log=show_log)
            try:
                if show_log:
                    self.log(f"📚 name 변경 감지 → 자동 단어장 갱신: {count}개 ({reason})")
            except Exception:
                pass
            return count
        except Exception as e:
            try:
                self.log(f"⚠️ name 자동 단어장 갱신 실패: {e}")
            except Exception:
                pass
            return 0

    def maker_database_page_indices(self):
        """Return actual self.data page indices for database pages.

        DB pages are created during game import by build_maker_pages. They stay in
        self.paths/self.data and are only filtered by UI mode; they are not a separate
        regenerated layer.
        """
        try:
            if hasattr(self, "current_tab_page_indices") and hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode():
                pages = list(self.current_tab_page_indices() or [])
                if pages:
                    return pages
        except Exception:
            pass
        out = []
        try:
            data = getattr(self, "data", {}) or {}
            items = data.items() if hasattr(data, "items") else []
            for k, page in items:
                try:
                    idx = int(k)
                except Exception:
                    continue
                meta = (page or {}).get("maker_page") or {} if isinstance(page, dict) else {}
                if str(meta.get("page_type") or "").strip().lower() == "database":
                    out.append(idx)
                    continue
                for row in ((page or {}).get("data") or []) if isinstance(page, dict) else []:
                    unit = (row or {}).get("maker_text_unit") or {} if isinstance(row, dict) else {}
                    if isinstance(unit, dict) and str(unit.get("source_kind") or "").strip().lower() == "database":
                        out.append(idx)
                        break
        except Exception:
            pass
        return sorted(set(out))

    def run_maker_database_batch_translate(self):
        plugin_mode = bool(hasattr(self, "is_maker_plugin_mode") and self.is_maker_plugin_mode())
        speaker_mode = bool(hasattr(self, "is_maker_speaker_mode") and self.is_maker_speaker_mode())
        layer_title = "플러그인 번역" if plugin_mode else ("화자 번역" if speaker_mode else "데이터베이스 번역")
        layer_item = "플러그인" if plugin_mode else ("화자" if speaker_mode else "데이터베이스")
        pages = self.maker_database_page_indices()
        if not pages:
            empty_msg = "플러그인 번역 페이지가 없습니다." if plugin_mode else ("화자 번역 페이지가 없습니다." if speaker_mode else "데이터베이스 번역 페이지가 없습니다.")
            self.show_warn_notice(layer_title, empty_msg)
            return
        if getattr(self, "is_batch_running", False):
            QMessageBox.information(self, self.tr_ui("일괄 작업 중"), self.tr_ui("이미 일괄 작업이 진행 중입니다."))
            return
        if not self.ensure_engine_ready():
            return
        if not self.check_translation_api_key_or_alert(self.cb_trans_provider.currentData()):
            return
        if plugin_mode:
            confirm_template = "플러그인 페이지 {count}개를 AI 번역할까요?\n번역 완료 후 원래 플러그인 데이터 위치에 바로 반영됩니다."
        elif speaker_mode:
            confirm_template = "화자명 {count}개를 AI 번역할까요?\n번역 결과는 연결된 실제 대사의 화자명에 반영됩니다."
        else:
            confirm_template = "데이터베이스 페이지 {count}개만 먼저 AI 번역할까요?\n번역 완료 후 클론 게임 JSON에 바로 반영됩니다."
        confirm_count = len(pages)
        if speaker_mode:
            try:
                confirm_count = sum(
                    len(self._maker_database_filtered_rows_for_page((getattr(self, "data", {}) or {}).get(int(page_idx), {}) or {}))
                    for page_idx in pages
                )
            except Exception:
                confirm_count = len(pages)
        confirm_message = self.tr_ui(confirm_template, count=confirm_count)
        if not self.ask_yes_no_shortcut(
            layer_title,
            confirm_message,
            yes_text="번역 시작", no_text="취소", default_yes=True, icon=QMessageBox.Icon.Question, parent=self,
        ):
            return
        self.commit_current_page_ui_to_data(include_mask=False)
        self.auto_save_project()
        self.is_batch_running = True
        self.current_batch_mode = "translate"
        self._maker_database_batch_translate_active = True
        self._batch_progress_done = 0
        self._batch_total = len(pages)
        self._long_task_cancel_requested = False
        self._batch_return_page_idx = int(getattr(self, "idx", 0) or 0)
        self._batch_return_mode_idx = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 0
        self.begin_busy_state(layer_title)
        self.set_project_action_interlock(True)
        self.batch_prepare_progress(layer_title, pages, layer_item, cancellable=True)
        if plugin_mode:
            self.log(self.tr_ui("🧩 플러그인 번역 시작: {count}페이지", count=len(pages)))
        elif speaker_mode:
            self.log(self.tr_ui("👤 화자 번역 시작: {count}페이지", count=len(pages)))
        else:
            self.log(f"🗃️ 데이터베이스 번역 시작: {len(pages)}페이지")
        self.start_universal_batch_worker("translate", pages)

    def _text_find_field_options(self):
        return [
            ("text", self.tr_ui("원문")),
            ("translated_text", self.tr_ui("번역문")),
            ("maker_memo", self.tr_ui("메모")),
        ]

    def _text_find_field_to_column(self, field):
        maker = self._is_maker_text_table_mode()
        if field == "text":
            return 5 if maker else 2
        if field == "translated_text":
            return 6 if maker else 3
        if field == "maker_memo":
            return 7 if maker else 3
        return self._table_translation_column()

    def _text_find_page_indices(self, scope):
        if scope == "all":
            try:
                return sorted(int(k) for k in (getattr(self, "data", {}) or {}).keys())
            except Exception:
                return list(range(len(getattr(self, "paths", []) or [])))
        try:
            if hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode():
                return [int(getattr(self, "maker_database_idx", 0) or 0)]
        except Exception:
            pass
        return [int(getattr(self, "idx", 0) or 0)]

    def _text_find_match(self, text, query, *, case_sensitive=False, whole=False, regex=False):
        text = str(text or "")
        query = str(query or "")
        if not query:
            return False
        if regex:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                if whole:
                    return re.fullmatch(query, text, flags=flags) is not None
                return re.search(query, text, flags=flags) is not None
            except Exception:
                return False
        a = text if case_sensitive else text.casefold()
        b = query if case_sensitive else query.casefold()
        return a == b if whole else b in a

    def _text_find_collect_matches(self, query, *, scope="current", fields=None, case_sensitive=False, whole=False, regex=False, start_after_current=False):
        fields = list(fields or ["text", "translated_text"])
        matches = []
        for page_idx in self._text_find_page_indices(scope):
            page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
            rows = page.get("data") or []
            for data_index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                for field in fields:
                    if field == "maker_memo" and not self._is_current_or_page_maker(page):
                        continue
                    value = row.get(field, "")
                    if self._text_find_match(value, query, case_sensitive=case_sensitive, whole=whole, regex=regex):
                        matches.append((page_idx, data_index, field))
        if start_after_current and matches:
            cur_page = int(getattr(self, "idx", 0) or 0)
            cur_row = max(0, int(getattr(getattr(self, "tab", None), "currentRow", lambda: 1)() or 1) - 1)
            cur_col = int(getattr(getattr(self, "tab", None), "currentColumn", lambda: 0)() or 0)
            def order_key(m):
                page_idx, data_index, field = m
                col = self._text_find_field_to_column(field)
                after = (page_idx, data_index, col) > (cur_page, cur_row, cur_col)
                return (0 if after else 1, page_idx, data_index, col)
            matches.sort(key=order_key)
        return matches

    def _is_current_or_page_maker(self, page):
        try:
            if isinstance(page, dict) and isinstance(page.get("maker_page"), dict):
                return True
            return any(isinstance(r, dict) and isinstance(r.get("maker_text_unit"), dict) for r in (page.get("data") or []))
        except Exception:
            return False

    def _select_text_find_match(self, match):
        if not match:
            return
        page_idx, data_index, field = match
        def _select_now():
            try:
                row = int(data_index) + 1
                col = self._text_find_field_to_column(field)
                item = self.tab.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    self.tab.setItem(row, col, item)
                self.tab.setCurrentCell(row, col)
                self.tab.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                self.tab.setFocus(Qt.FocusReason.ShortcutFocusReason)
            except Exception:
                pass
        try:
            if int(page_idx) != int(getattr(self, "idx", 0) or 0):
                self.jump_to_page_from_menu(int(page_idx))
                QTimer.singleShot(120, _select_now)
            else:
                _select_now()
        except Exception:
            _select_now()

    def open_text_find_dialog(self):
        self.open_text_find_replace_dialog(replace_mode=False)

    def open_text_replace_dialog(self):
        self.open_text_find_replace_dialog(replace_mode=True)

    def open_text_find_replace_dialog(self, replace_mode=False):
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("텍스트 찾기/교체") if replace_mode else self.tr_ui("텍스트 찾기"))
        dlg.resize(520, 360 if replace_mode else 300)
        root = QVBoxLayout(dlg)
        form = QFormLayout()
        find_edit = QLineEdit(dlg)
        find_edit.setText(str(getattr(self, "_last_text_find_query", "") or ""))
        replace_edit = QLineEdit(dlg)
        replace_edit.setText(str(getattr(self, "_last_text_replace_value", "") or ""))
        form.addRow(self.tr_ui("찾을 내용"), find_edit)
        if replace_mode:
            form.addRow(self.tr_ui("바꿀 내용"), replace_edit)
        root.addLayout(form)

        scope_box = QComboBox(dlg)
        scope_box.addItem(self.tr_ui("현재 맵"), "current")
        scope_box.addItem(self.tr_ui("전체 맵"), "all")
        try:
            scope_box.setCurrentIndex(1 if getattr(self, "_last_text_find_scope", "current") == "all" else 0)
        except Exception:
            pass
        root.addWidget(QLabel(self.tr_ui("검색 범위"), dlg))
        root.addWidget(scope_box)

        field_group = QGroupBox(self.tr_ui("검색 대상"), dlg)
        field_layout = QHBoxLayout(field_group)
        cb_fields = {}
        last_fields = set(getattr(self, "_last_text_find_fields", None) or ["text", "translated_text"])
        for key, label in self._text_find_field_options():
            cb = QCheckBox(label, field_group)
            cb.setChecked(key in last_fields)
            cb_fields[key] = cb
            field_layout.addWidget(cb)
        field_layout.addStretch(1)
        root.addWidget(field_group)

        opt_group = QGroupBox(self.tr_ui("고급 옵션"), dlg)
        opt_layout = QHBoxLayout(opt_group)
        cb_whole = QCheckBox(self.tr_ui("전체가 같은 것만"), opt_group)
        cb_case = QCheckBox(self.tr_ui("대소문자 구분"), opt_group)
        cb_regex = QCheckBox(self.tr_ui("정규식"), opt_group)
        opt_layout.addWidget(cb_whole)
        opt_layout.addWidget(cb_case)
        opt_layout.addWidget(cb_regex)
        opt_layout.addStretch(1)
        root.addWidget(opt_group)

        result_label = QLabel("", dlg)
        result_label.setWordWrap(True)
        root.addWidget(result_label)

        btn_row = QHBoxLayout()
        btn_find = QPushButton(self.tr_ui("다음 찾기"), dlg)
        btn_replace = QPushButton(self.tr_ui("현재 항목 교체"), dlg) if replace_mode else None
        btn_replace_all = QPushButton(self.tr_ui("모두 교체"), dlg) if replace_mode else None
        btn_close = QPushButton(self.tr_ui("닫기"), dlg)
        btn_row.addWidget(btn_find)
        if replace_mode:
            btn_row.addWidget(btn_replace)
            btn_row.addWidget(btn_replace_all)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

        def options():
            fields = [k for k, cb in cb_fields.items() if cb.isChecked()]
            if not fields:
                fields = ["text", "translated_text"]
            self._last_text_find_query = find_edit.text()
            self._last_text_replace_value = replace_edit.text()
            self._last_text_find_scope = scope_box.currentData()
            self._last_text_find_fields = fields
            return {
                "query": find_edit.text(),
                "replace": replace_edit.text(),
                "scope": scope_box.currentData(),
                "fields": fields,
                "case_sensitive": cb_case.isChecked(),
                "whole": cb_whole.isChecked(),
                "regex": cb_regex.isChecked(),
            }

        def do_find_next():
            opt = options()
            matches = self._text_find_collect_matches(opt["query"], scope=opt["scope"], fields=opt["fields"], case_sensitive=opt["case_sensitive"], whole=opt["whole"], regex=opt["regex"], start_after_current=True)
            if not matches:
                result_label.setText(self.tr_ui("검색 결과가 없습니다."))
                return
            self._select_text_find_match(matches[0])
            result_label.setText(self.tr_ui("검색 결과") + f": {len(matches)}개")

        def do_replace_current():
            opt = options()
            page_idx = int(getattr(self, "idx", 0) or 0)
            row = max(1, self.tab.currentRow()) - 1
            col = self.tab.currentColumn()
            field = None
            for f in opt["fields"]:
                if self._text_find_field_to_column(f) == col:
                    field = f
                    break
            if field is None:
                field = "translated_text"
            page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
            rows = page.get("data") or []
            if row < 0 or row >= len(rows):
                result_label.setText(self.tr_ui("교체할 현재 항목이 없습니다."))
                return
            if not self._text_find_match(rows[row].get(field, ""), opt["query"], case_sensitive=opt["case_sensitive"], whole=opt["whole"], regex=opt["regex"]):
                result_label.setText(self.tr_ui("현재 셀이 검색 조건과 일치하지 않습니다."))
                return
            self._replace_text_cell(page_idx, row, field, opt["replace"])
            result_label.setText(self.tr_ui("현재 항목을 교체했습니다."))
            do_find_next()

        def do_replace_all():
            opt = options()
            matches = self._text_find_collect_matches(opt["query"], scope=opt["scope"], fields=opt["fields"], case_sensitive=opt["case_sensitive"], whole=opt["whole"], regex=opt["regex"], start_after_current=False)
            count = 0
            for page_idx, data_index, field in matches:
                if self._replace_text_cell(page_idx, data_index, field, opt["replace"]):
                    count += 1
            try:
                self.fill_table()
            except Exception:
                pass
            try:
                self.schedule_deferred_auto_save_project(300)
            except Exception:
                pass
            result_label.setText(self.tr_ui("교체 완료") + f": {count}개")
            self.log(f"🔎 텍스트 일괄 교체: {count}개")

        btn_find.clicked.connect(do_find_next)
        if replace_mode and btn_replace is not None:
            btn_replace.clicked.connect(do_replace_current)
        if replace_mode and btn_replace_all is not None:
            btn_replace_all.clicked.connect(do_replace_all)
        btn_close.clicked.connect(dlg.close)
        find_edit.returnPressed.connect(do_find_next)
        dlg.exec()

    def _replace_text_cell(self, page_idx, data_index, field, new_text):
        try:
            page = (getattr(self, "data", {}) or {}).get(int(page_idx)) or {}
            rows = page.get("data") or []
            if data_index < 0 or data_index >= len(rows):
                return False
            row = rows[data_index]
            if not isinstance(row, dict):
                return False
            old = str(row.get(field, "") or "")
            new_text = str(new_text or "")
            if old == new_text:
                return False
            row[field] = new_text
            if field == "translated_text" and self._is_current_or_page_maker(page):
                row["maker_status"] = self.tr_ui("번역완료") if new_text.strip() else self.tr_ui("미번역")
            if int(page_idx) == int(getattr(self, "idx", 0) or 0):
                table_row = int(data_index) + 1
                col = self._text_find_field_to_column(field)
                old_block = self.tab.blockSignals(True)
                try:
                    item = self.tab.item(table_row, col)
                    if item is None:
                        item = QTableWidgetItem("")
                        self.tab.setItem(table_row, col, item)
                    item.setText(new_text)
                    item.setData(Qt.ItemDataRole.UserRole, new_text)
                    if field == "translated_text" and self._is_maker_text_table_mode():
                        status_item = self.tab.item(table_row, 1)
                        if status_item is not None:
                            status_text = row.get("maker_status") or ""
                            status_item.setText(status_text)
                            status_item.setData(Qt.ItemDataRole.UserRole, status_text)
                finally:
                    self.tab.blockSignals(old_block)
            try:
                if field == "translated_text" and self._is_current_or_page_maker(page):
                    self._apply_maker_live_writeback_now(page_indices=[int(page_idx)], reason="replace_text_cell", log_result=False)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _translation_unify_visible_source_key(self, text):
        """Return a conservative visible-source key for translation unification.

        This key is intentionally independent from the API prompt/newline
        settings.  The menu command named "번역 통일" means "if the user sees
        the same source sentence in the table, reuse the first translation".
        Therefore hidden RPG Maker control codes, CR/LF differences, stored 401
        line splits, zero-width characters, and CJK-only whitespace must not split
        the identity group.
        """
        raw = str(text or "")
        if not raw:
            return ""
        try:
            raw = strip_maker_control_codes(raw)
        except Exception:
            pass
        try:
            import unicodedata
            raw = unicodedata.normalize("NFKC", raw)
            cleaned = []
            for ch in raw.replace("\r\n", "\n").replace("\r", "\n"):
                cat = unicodedata.category(ch)
                if cat in {"Cf", "Cc"} and ch not in {"\n", "\t"}:
                    continue
                cleaned.append(ch)
            raw = "".join(cleaned)
        except Exception:
            raw = raw.replace("\r\n", "\n").replace("\r", "\n")

        def has_cjk(value):
            for ch in value:
                code = ord(ch)
                if (
                    0x3040 <= code <= 0x30FF
                    or 0x3400 <= code <= 0x9FFF
                    or 0xAC00 <= code <= 0xD7AF
                    or 0x1100 <= code <= 0x11FF
                    or 0xFF00 <= code <= 0xFFEF
                ):
                    return True
            return False

        if has_cjk(raw):
            # RPG Maker often stores one visible Japanese/Korean sentence as
            # multiple command lines.  For CJK text, those spaces/newlines are
            # normally storage artifacts, not word identity.
            return "".join(str(raw).split()).strip()
        try:
            import re
            return re.sub(r"\s+", " ", raw).strip()
        except Exception:
            return raw.strip()

    def _translation_unify_key_for_row(self, row, page=None, maker_translation_settings=None):
        """Return the source identity used by translation-unify.

        The unification command is a table/data cleanup command, not a
        translation-request command.  It must group rows by the visible source
        sentence the user is checking, then copy the earliest translation in
        page/row order.
        """
        if not isinstance(row, dict):
            return ""
        raw = str(row.get("text") or "")
        if not raw:
            return ""
        maker = False
        try:
            maker = isinstance(row.get("maker_text_unit"), dict) or self._is_current_or_page_maker(page or {})
        except Exception:
            maker = isinstance(row.get("maker_text_unit"), dict)
        if maker:
            # First priority: what the user actually sees as the source text.
            # This fixes identical-looking repeated RPG Maker sentences that
            # failed to unify because API/newline settings produced different
            # internal keys.
            visible_key = self._translation_unify_visible_source_key(raw)
            if visible_key:
                return visible_key
            try:
                unify_settings = {}
                if isinstance(maker_translation_settings, dict):
                    unify_settings.update(maker_translation_settings)
                unify_settings["normalize_source_newlines"] = True
                unify_settings["newline_join_mode"] = "auto"
                payload = prepare_maker_translation_payload(row, None, unify_settings)
                key = str(payload.get("normalized_text") or payload.get("plain_text") or payload.get("text") or raw)
            except Exception:
                try:
                    key = strip_maker_control_codes(raw)
                except Exception:
                    key = raw
            return self._translation_unify_visible_source_key(key)
        return self._translation_unify_visible_source_key(raw)

    def _translation_unify_current_visible_page_index(self):
        try:
            if hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode():
                return int(getattr(self, "maker_database_idx", 0) or 0)
        except Exception:
            pass
        try:
            return int(getattr(self, "idx", 0) or 0)
        except Exception:
            return 0

    def _translation_unify_table_cell_text(self, table_row, col):
        try:
            item = self.tab.item(int(table_row), int(col))
            if item is None:
                return ""
            text = str(item.text() if item.text() is not None else "")
            # For visible-table unification the displayed value is the primary
            # truth.  UserRole is only a fallback for legacy cells that do not
            # expose their text yet.
            if text != "":
                return text
            role = item.data(Qt.ItemDataRole.UserRole)
            return str(role if role is not None else "")
        except Exception:
            return ""

    def _translation_unify_is_current_visible_page(self, page_idx):
        try:
            return int(page_idx) == int(self._translation_unify_current_visible_page_index())
        except Exception:
            return False

    def _translation_unify_collect_entries_for_page(self, page_idx, page, *, maker_translation_settings=None):
        """Collect source/translation rows in the exact order used by 번역 통일.

        The current visible page is read from the table first, because the user
        command is deliberately a table-cleanup command: the topmost visible
        translation for the same visible source sentence must win.  Non-visible
        pages are read from self.data in page/data order so multi-map unification
        still propagates the first selected map's earliest translation to later
        maps.
        """
        entries = []
        page = page if isinstance(page, dict) else {}
        rows = page.get("data") or []
        maker = False
        try:
            maker = self._is_current_or_page_maker(page)
        except Exception:
            maker = False

        visible = False
        try:
            visible = bool(self._translation_unify_is_current_visible_page(page_idx) and getattr(self, "tab", None) is not None)
        except Exception:
            visible = False

        if visible and maker:
            # Maker table cells may intentionally be stale after a bulk data-only
            # operation.  Direct cell edits already update self.data immediately, so
            # unification must always read Maker translations from model data.
            visible = False

        if visible:
            try:
                text_col = self._table_text_column()
                trans_col = self._table_translation_column()
                db_mode = bool(hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
                row_count = int(self.tab.rowCount())
                for table_row in range(1, row_count):
                    try:
                        if maker:
                            data_index = self._maker_data_index_for_table_row(table_row, db_mode=db_mode)
                        else:
                            data_index = int(table_row) - 1
                    except Exception:
                        data_index = int(table_row) - 1
                    if data_index < 0 or data_index >= len(rows):
                        continue
                    row_data = rows[data_index]
                    if not isinstance(row_data, dict):
                        continue
                    source_display = self._translation_unify_table_cell_text(table_row, text_col)
                    if not source_display:
                        try:
                            source_display = self._maker_display_original_text(row_data, data_index=data_index) if maker else str(row_data.get("text") or "")
                        except Exception:
                            source_display = str(row_data.get("text") or "")
                    key = self._translation_unify_visible_source_key(source_display)
                    if not key:
                        continue
                    trans_display = self._translation_unify_table_cell_text(table_row, trans_col)
                    entries.append({
                        "page_idx": int(page_idx),
                        "data_index": int(data_index),
                        "table_row": int(table_row),
                        "key": key,
                        "translation": str(trans_display or ""),
                        "row": row_data,
                        "maker": bool(maker),
                        "visible": True,
                    })
                if entries:
                    return entries
            except Exception:
                # Fall through to data-based collection if the table is not in a
                # safe/readable state.
                entries = []

        for data_index, row_data in enumerate(rows):
            if not isinstance(row_data, dict):
                continue
            if maker:
                try:
                    source_display = self._maker_display_original_text(row_data, data_index=data_index)
                except Exception:
                    source_display = str(row_data.get("text") or "")
                key = self._translation_unify_visible_source_key(source_display)
                if not key:
                    key = self._translation_unify_key_for_row(row_data, page, maker_translation_settings)
            else:
                source_display = str(row_data.get("text") or "")
                key = self._translation_unify_visible_source_key(source_display)
            if not key:
                continue
            entries.append({
                "page_idx": int(page_idx),
                "data_index": int(data_index),
                "table_row": int(data_index) + 1,
                "key": key,
                "translation": str(row_data.get("translated_text") or ""),
                "row": row_data,
                "maker": bool(maker),
                "visible": False,
            })
        return entries

    def _translation_unify_set_entry_translation(self, entry, canon):
        try:
            row = entry.get("row") if isinstance(entry, dict) else None
            if not isinstance(row, dict):
                return False
            canon = str(canon or "")
            old = str(row.get("translated_text") or "")
            changed = old != canon
            if changed:
                row["translated_text"] = canon
                if bool(entry.get("maker")):
                    row["maker_status"] = self.tr_ui("번역완료") if canon.strip() else self.tr_ui("미번역")
            if bool(entry.get("maker")) and changed:
                try:
                    self._mark_maker_table_rows_pending_refresh(
                        [int(entry.get("table_row") or (int(entry.get("data_index", -1)) + 1))],
                        page_idx=int(entry.get("page_idx", getattr(self, "idx", 0)) or 0),
                        db_mode=False,
                        reason="unified_translation_memory",
                    )
                except Exception:
                    pass
            elif bool(entry.get("visible")):
                try:
                    trans_col = self._table_translation_column()
                    status_col = 1
                    table_row = int(entry.get("table_row") or 0)
                    old_block = self.tab.blockSignals(True)
                    try:
                        item = self.tab.item(table_row, trans_col)
                        if item is None:
                            item = QTableWidgetItem("")
                            self.tab.setItem(table_row, trans_col, item)
                        if str(item.text() or "") != canon:
                            item.setText(canon)
                        item.setData(Qt.ItemDataRole.UserRole, canon)
                        status_text = row.get("maker_status") or ""
                        st_item = self.tab.item(table_row, status_col)
                        if st_item is not None:
                            st_item.setText(status_text)
                            st_item.setData(Qt.ItemDataRole.UserRole, status_text)
                    finally:
                        self.tab.blockSignals(old_block)
                except Exception:
                    pass
            return changed
        except Exception:
            return False

    def apply_unified_translation_memory(self, *, scope="all", show_message=True, auto=False, page_indices=None, page_label=None):
        """Make identical visible source strings share the earliest translation.

        번역 통일의 기준은 내부 API payload가 아니라 사용자가 표에서 보는 원문이다.
        선택된 페이지를 앞에서부터 훑고, 각 페이지 안에서는 위 행부터 훑는다.  같은
        원문 키가 처음 등장했을 때의 번역문이 기준 번역문이 되고, 뒤쪽 페이지/행의
        같은 원문은 그 기준 번역문으로 교체된다.
        """
        try:
            # Maker cell edits update self.data immediately, while bulk operations
            # intentionally leave visible cells stale until a single-row click.
            # Never commit a stale Maker table back over the model here.
            is_maker_page = bool(hasattr(self, "_is_current_maker_page") and self._is_current_maker_page())
            if (not is_maker_page) and hasattr(self, "commit_current_page_ui_to_data"):
                self.commit_current_page_ui_to_data(include_mask=False)
        except Exception:
            pass

        if page_indices is not None:
            pages = []
            seen = set()
            total_pages = len(getattr(self, "paths", []) or [])
            for raw in page_indices or []:
                try:
                    idx = int(raw)
                except Exception:
                    continue
                if idx < 0 or idx >= total_pages or idx in seen:
                    continue
                pages.append(idx)
                seen.add(idx)
        else:
            pages = self._text_find_page_indices("all" if scope == "all" else "current")

        page_kind = {}
        for page_idx in pages:
            page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
            is_db = False
            try:
                is_db = bool(self._maker_page_is_database_page(page))
            except Exception:
                meta = page.get("maker_page") if isinstance(page, dict) else {}
                is_db = isinstance(meta, dict) and str(meta.get("page_type") or "").lower() == "database"
            page_kind[int(page_idx)] = bool(is_db)

        # Keep DB and normal map/common-event text in separate pools.  If the
        # selection accidentally contains both, retain the current behavior: only
        # normal map/common-event pages are unified unless the user is in DB-only
        # selection mode.
        if pages and any(page_kind.values()) and not all(page_kind.values()):
            pages = [idx for idx in pages if not page_kind.get(int(idx), False)]

        if not pages:
            if show_message:
                self.show_warn_notice("번역 통일", "번역 통일을 적용할 항목이 없습니다.")
            return 0

        try:
            maker_translation_settings = load_maker_translation_settings(getattr(self, "project_dir", None))
        except Exception:
            maker_translation_settings = None

        entries = []
        for page_idx in pages:
            page = (getattr(self, "data", {}) or {}).get(page_idx) or {}
            entries.extend(self._translation_unify_collect_entries_for_page(
                page_idx,
                page,
                maker_translation_settings=maker_translation_settings,
            ))

        if not entries:
            if show_message:
                label = str(page_label or (self.tr_ui("전체 맵") if scope == "all" else self.tr_ui("현재 맵")))
                self.show_ok_notice("번역 통일", f"{label} 기준으로 동일 원문 번역문 0개를 통일했습니다.")
            return 0

        memory = {}
        # First pass: earliest non-empty translation wins.  The order of entries
        # is selected page order -> row order, so all pages can inherit the first
        # selected map's first translated line.
        for entry in entries:
            key = str(entry.get("key") or "")
            if not key or key in memory:
                continue
            trans = str(entry.get("translation") or "")
            if trans.strip():
                memory[key] = trans

        changed = 0
        changed_pages = set()
        if memory and not auto:
            try:
                self.push_project_undo("번역 통일", full_project=True)
            except Exception:
                try:
                    self.undo_push_text_line("번역 통일")
                except Exception:
                    pass

        for entry in entries:
            key = str(entry.get("key") or "")
            if not key or key not in memory:
                continue
            canon = memory[key]
            if self._translation_unify_set_entry_translation(entry, canon):
                changed += 1
                try:
                    changed_pages.add(int(entry.get("page_idx")))
                except Exception:
                    pass

        if changed:
            # Current visible table cells were already updated directly.  Use a
            # full refill only as a safety refresh for non-visible pages and row
            # summaries; the direct table write above is the source of truth for
            # the command feedback the user sees immediately.
            try:
                self.fill_table()
            except Exception:
                try:
                    self.tab.resizeRowsToContents()
                except Exception:
                    pass
            for page_idx in sorted(changed_pages):
                try:
                    if hasattr(self, "mark_page_data_dirty_explicit"):
                        self.mark_page_data_dirty_explicit(page_idx, "text")
                    elif hasattr(self, "project_engine") and self.project_engine is not None:
                        self.project_engine.mark_page_dirty(page_idx, "text")
                except Exception:
                    pass
            try:
                self.schedule_deferred_auto_save_project(500)
            except Exception:
                pass
            try:
                if any(self._is_current_or_page_maker((getattr(self, "data", {}) or {}).get(i) or {}) for i in pages):
                    self.mark_maker_writeback_dirty(page_indices=sorted(changed_pages or set(pages)), reason="translation_memory_apply")
            except Exception:
                pass
        try:
            self.log(f"🧩 번역 통일 표 기준 적용: 대상 {len(entries)}행 / 기준 {len(memory)}개 / 변경 {changed}개")
        except Exception:
            pass
        if show_message:
            label = str(page_label or (self.tr_ui("전체 맵") if scope == "all" else self.tr_ui("현재 맵")))
            self.show_ok_notice("번역 통일", f"{label} 기준으로 동일 원문 번역문 {changed}개를 통일했습니다.")
        elif changed and not auto:
            self.log(f"🧩 통일 번역 적용: {changed}개")
        return changed

    def apply_unified_translation_memory_action(self):
        title = "번역 통일"
        selected_indices, selected_label = self.choose_batch_page_indices_for_context(title, "unify_translations")
        if selected_indices is None:
            try:
                self.log("↩️ 번역 통일 취소")
            except Exception:
                pass
            return
        self.apply_unified_translation_memory(scope="selected", show_message=True, page_indices=selected_indices, page_label=selected_label)

    def _maker_control_info_for_row(self, row):
        try:
            raw = str((row or {}).get("text") or "")
            return analyze_maker_control_codes(raw)
        except Exception:
            raw = str((row or {}).get("text") or "") if isinstance(row, dict) else ""
            return {
                "raw_text": raw,
                "plain_text": raw,
                "has_control_codes": False,
                "placement": "none",
                "prefix_codes": "",
                "suffix_codes": "",
                "middle_codes": [],
                "control_codes": [],
                "auto_restorable": False,
            }

    def _maker_display_original_text(self, row, *, data_index=None):
        info = self._maker_control_info_for_row(row)
        raw = str(info.get("raw_text") or "")
        # 쯔꾸르붕이 원문 표는 제어코드를 숨기지 않는다. 번역/API에는
        # plain_text만 보내지만, 사용자는 원본에 어떤 코드가 박혀 있는지
        # 항상 볼 수 있어야 한다.
        return raw

    def _maker_control_status_label(self, info):
        try:
            if not info.get("has_control_codes"):
                return self.tr_ui("없음")
            if info.get("placement") == "edge" and info.get("auto_restorable"):
                return self.tr_ui("자동복원 가능")
            return self.tr_ui("수동처리 필요")
        except Exception:
            return self.tr_ui("수동처리 필요")

    def _maker_control_cell_tooltip(self, row):
        info = self._maker_control_info_for_row(row)
        if not info.get("has_control_codes"):
            return ""
        raw = str(info.get("raw_text") or "")
        plain = str(info.get("plain_text") or "")
        return (
            f"{self.tr_ui('번역/API에는 제어코드를 제거한 원문만 사용합니다.')}\n"
            f"{self.tr_ui('상태')}: {self._maker_control_status_label(info)}\n\n"
            f"{self.tr_ui('정리 원문')}:\n{plain}\n\n"
            f"{self.tr_ui('제어코드 포함 원문')}:\n{raw}"
        )

    def _maker_selected_data_indexes(self):
        indexes = []
        try:
            rows = sorted({idx.row() for idx in self.tab.selectedIndexes() if idx.row() > 0})
        except Exception:
            rows = []
        if not rows:
            try:
                r = int(self.tab.currentRow())
                if r > 0:
                    rows = [r]
            except Exception:
                rows = []
        for r in rows:
            indexes.append(r - 1)
        return indexes

    def _refresh_maker_control_code_buttons(self):
        mode = str(getattr(self, "maker_control_code_display_mode", "hidden") or "hidden")
        try:
            if hasattr(self, "btn_maker_ctrl_show_all"):
                self.btn_maker_ctrl_show_all.blockSignals(True)
                self.btn_maker_ctrl_show_all.setChecked(mode == "all")
                self.btn_maker_ctrl_show_all.blockSignals(False)
            if hasattr(self, "btn_maker_ctrl_show_current"):
                self.btn_maker_ctrl_show_current.blockSignals(True)
                self.btn_maker_ctrl_show_current.setChecked(mode == "current")
                self.btn_maker_ctrl_show_current.blockSignals(False)
        except Exception:
            pass

    def refresh_maker_control_code_source_cells(self, rows=None, resize=True):
        if not hasattr(self, "tab") or not self._is_maker_text_table_mode():
            return
        curr = self.data.get(self.idx) or {}
        data = curr.get("data") or []
        try:
            if rows is None:
                mode = str(getattr(self, "maker_control_code_display_mode", "hidden") or "hidden")
                if mode == "current":
                    cur = int(self.tab.currentRow()) if self.tab is not None else -1
                    prev = int(getattr(self, "_maker_control_previous_current_row", -1) or -1)
                    rows = [prev, cur]
                    self._maker_control_previous_current_row = cur
                else:
                    rows = list(range(1, len(data) + 1))
            row_list = []
            seen = set()
            for r in rows or []:
                try:
                    r = int(r)
                except Exception:
                    continue
                if r <= 0 or r in seen:
                    continue
                seen.add(r)
                row_list.append(r)
        except Exception:
            row_list = list(range(1, len(data) + 1))
        old_block = False
        try:
            old_block = self.tab.blockSignals(True)
        except Exception:
            old_block = False
        try:
            for row in row_list:
                i = row - 1
                if i < 0 or i >= len(data):
                    continue
                row_data = data[i]
                if row >= self.tab.rowCount() or self.tab.columnCount() <= 5:
                    continue
                item = self.tab.item(row, 5)
                if item is None:
                    item = self._make_table_item("", editable=False)
                    self.tab.setItem(row, 5, item)
                display = self._maker_display_original_text(row_data, data_index=i)
                item.setText(display)
                item.setData(Qt.ItemDataRole.UserRole, str(row_data.get("text", "") or ""))
                try:
                    tip = self._maker_control_cell_tooltip(row_data)
                    item.setToolTip(tip or "")
                    info = self._maker_control_info_for_row(row_data)
                    if info.get("has_control_codes"):
                        if info.get("placement") == "edge" and info.get("auto_restorable"):
                            item.setForeground(QBrush(QColor("#D9C38A")))
                        else:
                            item.setForeground(QBrush(QColor("#D7A3A9")))
                    else:
                        item.setForeground(QBrush())
                except Exception:
                    pass
        finally:
            try:
                self.tab.blockSignals(old_block)
            except Exception:
                pass
        if resize:
            try:
                if row_list and len(row_list) <= 4:
                    for row in row_list:
                        try:
                            self.tab.resizeRowToContents(int(row))
                        except Exception:
                            pass
                else:
                    self.tab.resizeRowsToContents()
            except Exception:
                pass

    def set_maker_control_code_display_mode(self, mode):
        mode = str(mode or "hidden")
        if mode not in ("hidden", "current", "all"):
            mode = "hidden"
        self.maker_control_code_display_mode = mode
        self._refresh_maker_control_code_buttons()
        try:
            self.refresh_maker_control_code_source_cells()
        except Exception:
            try:
                self.ref_tab()
            except Exception:
                pass

    def toggle_maker_control_code_all(self, checked=False):
        self.set_maker_control_code_display_mode("all" if checked else "hidden")

    def toggle_maker_control_code_current(self, checked=False):
        self.set_maker_control_code_display_mode("current" if checked else "hidden")

    def is_maker_control_code_auto_apply_enabled(self):
        return bool(getattr(self, "maker_control_code_auto_apply_enabled", True))

    def set_maker_control_code_auto_apply_enabled(self, enabled, *, save=True, show_log=True):
        enabled = bool(enabled)
        self.maker_control_code_auto_apply_enabled = enabled
        try:
            cb = getattr(self, "cb_maker_control_code_auto_apply", None)
            if cb is not None:
                old = cb.blockSignals(True)
                try:
                    cb.setChecked(enabled)
                finally:
                    cb.blockSignals(old)
        except Exception:
            pass
        try:
            action = (getattr(self, "actions", {}) or {}).get("work_toggle_maker_control_code_auto_apply")
            if action is not None:
                old = action.blockSignals(True)
                try:
                    action.setChecked(enabled)
                finally:
                    action.blockSignals(old)
        except Exception:
            pass
        if save:
            try:
                self.app_options["maker_control_code_auto_apply_enabled"] = enabled
                self.save_app_options_cache()
            except Exception:
                pass
        if show_log:
            try:
                self.log(self.tr_ui("🧩 번역 시 제어코드 자동 반영: ON" if enabled else "🧩 번역 시 제어코드 자동 반영: OFF"))
            except Exception:
                pass
        return enabled

    def on_maker_control_code_auto_apply_toggled(self, checked):
        return self.set_maker_control_code_auto_apply_enabled(bool(checked), save=True, show_log=True)

    def toggle_maker_control_code_auto_apply(self):
        return self.set_maker_control_code_auto_apply_enabled(
            not self.is_maker_control_code_auto_apply_enabled(),
            save=True,
            show_log=True,
        )

    def restore_edge_control_codes_current(self):
        if not self._is_maker_text_table_mode():
            try:
                self.log("ℹ️ 제어코드 복원은 쯔꾸르 대사 페이지에서만 사용할 수 있습니다.")
            except Exception:
                pass
            return
        curr = self.data.get(self.idx) or {}
        data = curr.get("data") or []
        indexes = list(range(len(data)))
        if not indexes:
            try:
                self.log("⚠️ 현재 맵에 복원할 대사 행이 없습니다.")
            except Exception:
                pass
            return
        self._restore_edge_control_codes_for_indexes(indexes, reason="제어코드 현재 맵 복원", current_only=False, scope_label="현재 맵", show_progress=True)

    def restore_edge_control_codes_all(self):
        if not self._is_maker_text_table_mode():
            try:
                self.log("ℹ️ 제어코드 복원은 쯔꾸르 대사 페이지에서만 사용할 수 있습니다.")
            except Exception:
                pass
            return
        self._restore_edge_control_codes_for_all_maps(reason="제어코드 일괄 맵 복원")

    def _maker_control_code_restore_candidate_pages(self, selected_indices=None):
        if not isinstance(getattr(self, "data", None), dict):
            return []
        if selected_indices is None:
            raw_indices = list((self.data or {}).keys())
        else:
            raw_indices = list(selected_indices or [])
        result = []
        seen = set()
        for raw in raw_indices:
            try:
                page_idx = int(raw)
            except Exception:
                continue
            if page_idx in seen:
                continue
            seen.add(page_idx)
            page = (self.data or {}).get(page_idx) or {}
            if not isinstance(page, dict):
                continue
            meta = page.get("maker_page") or {}
            if not isinstance(meta, dict) or not meta:
                continue
            page_type = str(meta.get("page_type") or "map")
            # 여기서 "맵"은 실제 MapXXX 대사 페이지다. DB/공통 이벤트 가상 페이지는 타일 맵이 없으므로 일괄 맵 복원 대상에서 제외한다.
            if page_type not in ("", "map"):
                continue
            if not (page.get("data") or []):
                continue
            result.append(page_idx)
        return result

    def _restore_edge_control_codes_for_all_maps(self, *, reason="제어코드 일괄 맵 복원"):
        if not isinstance(getattr(self, "data", None), dict):
            return
        title = "일괄 맵 제어코드 복원"
        selected_indices, selected_label = self.choose_batch_page_indices_for_context(title, "restore_edge_control_codes")
        if selected_indices is None:
            try:
                self.log("↩️ 일괄 맵 제어코드 복원 취소")
            except Exception:
                pass
            return
        page_indices = self._maker_control_code_restore_candidate_pages(selected_indices)
        if not page_indices:
            try:
                self.log("⚠️ 일괄 맵 제어코드 복원 대상이 없습니다.")
            except Exception:
                pass
            return

        progress = None
        page_plans = {}
        total = {"applied": 0, "already": 0, "manual": 0, "empty": 0, "none": 0}
        try:
            progress = QProgressDialog(self)
            progress.setWindowTitle(self.tr_ui("일괄 맵 제어코드 복원"))
            progress.setLabelText(self.tr_ui("복원 대상 대사 수를 계산하는 중입니다..."))
            progress.setRange(0, max(1, len(page_indices)))
            progress.setValue(0)
            progress.setMinimumDuration(0)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            progress.setCancelButton(None)
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            try:
                apply_progress_dialog_theme(progress, bool(self.is_light_theme()))
            except Exception:
                pass
            progress.show()
            QApplication.processEvents()
        except Exception:
            progress = None

        # 1단계: 실제로 반영될 대사 수를 먼저 계산한다.
        # 이 단계는 데이터만 훑고 화면/프리뷰는 절대 재구성하지 않는다.
        for order, page_idx in enumerate(page_indices, start=1):
            page = (self.data or {}).get(page_idx) or {}
            data = page.get("data") or []
            try:
                meta = page.get("maker_page") or {}
                map_name = str(meta.get("map_name") or meta.get("page_title") or f"Map {int(page_idx)+1}")
                if progress is not None:
                    progress.setLabelText(self.tr_ui(f"복원 대상 대사 수를 계산하는 중입니다... ({order}/{len(page_indices)})\n{map_name}"))
                    progress.setValue(order - 1)
                    QApplication.processEvents()
            except Exception:
                pass
            stats, candidates = self._restore_edge_control_codes_scan_candidates(data, range(len(data)))
            page_plans[int(page_idx)] = candidates
            for key, value in (stats or {}).items():
                total[key] = int(total.get(key, 0) or 0) + int(value or 0)
        try:
            if progress is not None:
                progress.setValue(len(page_indices))
                QApplication.processEvents()
        except Exception:
            pass

        total_apply = int(total.get("applied", 0) or 0)
        self._audit_translate_event(
            "TRANSLATE_CONTROL_CODE_MANUAL_RESTORE_COUNTED",
            scope="batch_maps",
            label=str(selected_label),
            pages=len(page_indices),
            apply_total=total_apply,
            already=int(total.get("already", 0)),
            manual=int(total.get("manual", 0)),
            empty=int(total.get("empty", 0)),
            none=int(total.get("none", 0)),
        )
        if total_apply <= 0:
            try:
                if progress is not None:
                    progress.close()
                    progress.deleteLater()
            except Exception:
                pass
            self.log(f"ℹ️ 제어코드 일괄 맵 제어코드 복원({selected_label}): 적용 없음 / 이미 적용 {total['already']}개 / 수동필요 {total['manual']}개 / 빈 번역 {total['empty']}개 / 제어코드 없음 {total['none']}개")
            return

        try:
            if progress is not None:
                progress.setWindowTitle(self.tr_ui("일괄 맵 제어코드 복원"))
                progress.setLabelText(self.tr_ui("복원 전 되돌리기 지점을 만드는 중입니다...\n잠시만 기다려 주세요."))
                progress.setRange(0, 0)
                QApplication.processEvents()
        except Exception:
            pass
        self._audit_translate_event("TRANSLATE_CONTROL_CODE_MANUAL_RESTORE_UNDO_BEGIN", scope="batch_maps", apply_total=total_apply)
        try:
            self.push_project_undo(reason, full_project=True)
        except Exception:
            try:
                self.undo_push_text_line(reason)
            except Exception:
                pass
        self._audit_translate_event("TRANSLATE_CONTROL_CODE_MANUAL_RESTORE_UNDO_DONE", scope="batch_maps", apply_total=total_apply)

        # 2단계: 계산된 적용 후보만 데이터에 반영한다.
        # 여기서도 ref_tab()/프리뷰 전체 재구성은 금지한다.
        changed_pages = []
        changed_by_page = {}
        changed_ids_by_page = {}
        counter = {"value": 0}
        try:
            current_idx_for_progress = int(getattr(self, "idx", 0) or 0)
        except Exception:
            current_idx_for_progress = -1
        progress_total_units = max(1, total_apply + 2)
        try:
            if progress is not None:
                progress.setWindowTitle(self.tr_ui("일괄 맵 제어코드 복원"))
                progress.setLabelText(self.tr_ui(f"제어코드 데이터 반영 중입니다... (0/{total_apply})"))
                progress.setRange(0, progress_total_units)
                progress.setValue(0)
                QApplication.processEvents()
        except Exception:
            pass
        for page_idx in page_indices:
            candidates = list(page_plans.get(int(page_idx)) or [])
            if not candidates:
                continue
            page = (self.data or {}).get(page_idx) or {}
            data = page.get("data") or []
            changed_ids, changed_indices = self._restore_edge_control_codes_apply_candidates(
                int(page_idx),
                data,
                candidates,
                progress=progress,
                counter=counter,
                total=total_apply,
                label=str(selected_label),
                progress_base=0,
                progress_total=progress_total_units,
            )
            if changed_indices:
                changed_pages.append(int(page_idx))
                changed_by_page[int(page_idx)] = list(changed_indices)
                changed_ids_by_page[int(page_idx)] = list(changed_ids or [])
        try:
            if progress is not None:
                progress.setValue(min(total_apply, progress_total_units))
                QApplication.processEvents()
        except Exception:
            pass

        # 표 셀과 행 높이는 건드리지 않는다. 각 페이지의 변경 행을 지연
        # 갱신 대상으로 표시하고, 사용자가 해당 행을 단일 클릭할 때만 반영한다.
        try:
            for changed_page_idx, data_indices in changed_by_page.items():
                self._mark_maker_table_rows_pending_refresh(
                    [int(i) + 1 for i in (data_indices or [])],
                    page_idx=int(changed_page_idx),
                    db_mode=False,
                    reason="control_code_restore_batch_maps",
                )
        except Exception:
            pass
        try:
            for page_idx in changed_pages:
                if hasattr(self, "project_engine") and self.project_engine is not None:
                    self.project_engine.mark_page_dirty(int(page_idx), "text")
        except Exception:
            pass
        try:
            if progress is not None:
                progress.setLabelText(self.tr_ui("변경 사항을 작업 데이터에 반영하는 중입니다..."))
                progress.setValue(max(0, progress_total_units - 1))
                QApplication.processEvents()
        except Exception:
            pass
        try:
            if changed_pages:
                for changed_page_idx in changed_pages:
                    self.finalize_maker_text_data_change(
                        changed_ids_by_page.get(int(changed_page_idx)) or [],
                        fields=["translated_text"],
                        page_idx=int(changed_page_idx),
                        reason="control_code_restore_batch_maps",
                    )
                self.mark_maker_writeback_dirty(page_indices=changed_pages, reason="control_code_restore_batch_maps")
        except Exception:
            pass
        try:
            if progress is not None:
                progress.setValue(progress_total_units)
                QApplication.processEvents()
                progress.close()
                progress.deleteLater()
        except Exception:
            pass
        self.log(f"🧩 제어코드 일괄 맵 제어코드 복원 완료({selected_label}): 적용 {total['applied']}개 / 이미 적용 {total['already']}개 / 수동필요 {total['manual']}개 / 빈 번역 {total['empty']}개 / 제어코드 없음 {total['none']}개")
        self._audit_translate_event(
            "TRANSLATE_CONTROL_CODE_MANUAL_RESTORE_APPLIED",
            scope="batch_maps",
            label=str(selected_label),
            applied=int(total.get('applied', 0)),
            already=int(total.get('already', 0)),
            manual=int(total.get('manual', 0)),
            empty=int(total.get('empty', 0)),
            none=int(total.get('none', 0)),
            changed_pages=len(changed_pages),
        )

    def _restore_edge_control_codes_scan_candidates(self, data, indexes):
        stats = {"applied": 0, "already": 0, "manual": 0, "empty": 0, "none": 0}
        candidates = []
        data = data or []
        for raw_i in list(indexes or []):
            try:
                i = int(raw_i)
            except Exception:
                continue
            if i < 0 or i >= len(data):
                continue
            item = data[i]
            if not isinstance(item, dict):
                continue
            try:
                new_text, status = apply_maker_edge_control_codes(item.get("translated_text", ""), item.get("text", ""))
            except Exception:
                new_text, status = str(item.get("translated_text", "") or ""), "none"
            if status == "applied":
                candidates.append({
                    "data_index": int(i),
                    "new_text": str(new_text or ""),
                    "id": item.get("id"),
                })
                stats["applied"] += 1
            elif status == "already":
                stats["already"] += 1
            elif status == "manual":
                stats["manual"] += 1
            elif status == "empty":
                stats["empty"] += 1
            else:
                stats["none"] += 1
        return stats, candidates

    def _restore_edge_control_codes_apply_candidates(self, page_idx, data, candidates, *, progress=None, counter=None, total=0, label="", progress_base=0, progress_total=None):
        changed_ids = []
        changed_indices = []
        data = data or []
        total = int(total or len(candidates or []) or 0)
        progress_base = int(progress_base or 0)
        progress_total = int(progress_total or total or 1)
        update_every = 1 if total <= 500 else 10
        for cand in list(candidates or []):
            try:
                i = int(cand.get("data_index"))
            except Exception:
                continue
            if i < 0 or i >= len(data):
                continue
            item = data[i]
            if not isinstance(item, dict):
                continue
            new_text = str(cand.get("new_text") or "")
            if str(item.get("translated_text") or "") == new_text:
                continue
            item["translated_text"] = new_text
            item["maker_status"] = self.tr_ui("번역완료") if new_text.strip() else self.tr_ui("미번역")
            changed_ids.append(item.get("id"))
            changed_indices.append(int(i))
            try:
                if counter is not None:
                    counter["value"] = int(counter.get("value", 0) or 0) + 1
                    current = int(counter.get("value", 0) or 0)
                else:
                    current = len(changed_indices)
                if progress is not None and (current == total or current <= 3 or current % update_every == 0):
                    progress.setLabelText(self.tr_ui(f"제어코드 데이터 반영 중입니다... ({current}/{total})\n{label}"))
                    progress.setValue(min(progress_base + current, max(1, progress_total)))
                    QApplication.processEvents()
            except Exception:
                pass
        return changed_ids, changed_indices

    def _restore_edge_control_codes_on_page(self, page_idx, data, indexes):
        stats, candidates = self._restore_edge_control_codes_scan_candidates(data, indexes)
        changed_ids, changed_indices = self._restore_edge_control_codes_apply_candidates(page_idx, data, candidates)
        return stats, changed_ids, changed_indices

    def _refresh_maker_restored_translation_table_rows(self, data, data_indices, *, progress=None, progress_base=0, progress_total=None, label=""):
        table = getattr(self, "tab", None)
        if table is None or not data_indices:
            return 0
        try:
            trans_col = int(self._table_translation_column())
        except Exception:
            trans_col = 6
        changed = 0
        rows = list(data_indices or [])
        row_total = len(rows)
        progress_base = int(progress_base or 0)
        progress_total = int(progress_total or (progress_base + row_total) or 1)
        update_every = 1 if row_total <= 500 else 10
        try:
            old_block = table.blockSignals(True)
        except Exception:
            old_block = False
        try:
            try:
                old_updates = table.updatesEnabled()
                table.setUpdatesEnabled(False)
            except Exception:
                old_updates = True
            for step, raw_i in enumerate(rows, start=1):
                try:
                    data_index = int(raw_i)
                except Exception:
                    continue
                if data_index < 0 or data_index >= len(data or []):
                    continue
                table_row = data_index + 1
                if table_row <= 0 or table_row >= table.rowCount():
                    continue
                row_data = data[data_index]
                if not isinstance(row_data, dict):
                    continue
                text = str(row_data.get("translated_text") or "")
                item = table.item(table_row, trans_col)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(table_row, trans_col, item)
                if str(item.text() or "") != text:
                    item.setText(text)
                item.setData(Qt.ItemDataRole.UserRole, text)
                try:
                    status_text = str(row_data.get("maker_status") or "")
                    st_item = table.item(table_row, 1)
                    if st_item is not None:
                        st_item.setText(status_text)
                        st_item.setData(Qt.ItemDataRole.UserRole, status_text)
                except Exception:
                    pass
                changed += 1
                try:
                    if progress is not None and (step == row_total or step <= 3 or step % update_every == 0):
                        progress.setLabelText(self.tr_ui(f"현재 표 셀 반영 중입니다... ({step}/{row_total})\n{label}"))
                        progress.setValue(min(progress_base + step, max(1, progress_total)))
                        QApplication.processEvents()
                except Exception:
                    pass
            try:
                table.setUpdatesEnabled(old_updates)
                table.viewport().update()
            except Exception:
                pass
        finally:
            try:
                table.blockSignals(old_block)
            except Exception:
                pass
        return changed

    def _restore_edge_control_codes_for_indexes(self, indexes, *, reason="제어코드 자동복원", current_only=True, scope_label=None, show_progress=False):
        curr = self.data.get(self.idx) or {}
        data = curr.get("data") or []
        if not data:
            return
        targets = [i for i in indexes if 0 <= int(i) < len(data)]
        if not targets:
            return

        progress = None
        if show_progress:
            try:
                progress = QProgressDialog(self)
                progress.setWindowTitle(self.tr_ui("현재 맵 복원"))
                progress.setLabelText(self.tr_ui("복원 대상 대사 수를 계산하는 중입니다..."))
                progress.setRange(0, 1)
                progress.setValue(0)
                progress.setMinimumDuration(0)
                progress.setAutoClose(False)
                progress.setAutoReset(False)
                progress.setCancelButton(None)
                progress.setWindowModality(Qt.WindowModality.ApplicationModal)
                try:
                    apply_progress_dialog_theme(progress, bool(self.is_light_theme()))
                except Exception:
                    pass
                progress.show()
                QApplication.processEvents()
            except Exception:
                progress = None

        stats, candidates = self._restore_edge_control_codes_scan_candidates(data, targets)
        applied = int(stats.get("applied", 0) or 0)
        already = int(stats.get("already", 0) or 0)
        manual = int(stats.get("manual", 0) or 0)
        empty = int(stats.get("empty", 0) or 0)
        none = int(stats.get("none", 0) or 0)
        self._audit_translate_event(
            "TRANSLATE_CONTROL_CODE_MANUAL_RESTORE_COUNTED",
            scope=str(scope_label or ("선택 대사" if current_only else "현재 맵")),
            apply_total=applied,
            already=already,
            manual=manual,
            empty=empty,
            none=none,
        )
        if applied <= 0:
            try:
                if progress is not None:
                    progress.close()
                    progress.deleteLater()
            except Exception:
                pass
            label = str(scope_label or ("선택 대사" if current_only else "현재 맵"))
            self.log(f"ℹ️ 제어코드 {label} 복원: 적용 없음 / 이미 적용 {already}개 / 수동필요 {manual}개 / 빈 번역 {empty}개 / 제어코드 없음 {none}개")
            self._audit_translate_event(
                "TRANSLATE_CONTROL_CODE_MANUAL_RESTORE_APPLIED",
                scope=str(label),
                applied=0,
                already=already,
                manual=manual,
                empty=empty,
                none=none,
            )
            return

        label = str(scope_label or ("선택 대사" if current_only else "현재 맵"))
        try:
            if progress is not None:
                progress.setWindowTitle(self.tr_ui("현재 맵 복원"))
                progress.setLabelText(self.tr_ui("복원 전 되돌리기 지점을 만드는 중입니다...\n잠시만 기다려 주세요."))
                progress.setRange(0, 0)
                QApplication.processEvents()
        except Exception:
            pass
        self._audit_translate_event("TRANSLATE_CONTROL_CODE_MANUAL_RESTORE_UNDO_BEGIN", scope=str(label), apply_total=applied)
        try:
            self.undo_push_text_line(reason)
        except Exception:
            pass
        self._audit_translate_event("TRANSLATE_CONTROL_CODE_MANUAL_RESTORE_UNDO_DONE", scope=str(label), apply_total=applied)
        progress_total_units = max(1, applied + applied + 2)
        try:
            if progress is not None:
                progress.setWindowTitle(self.tr_ui("현재 맵 복원"))
                progress.setLabelText(self.tr_ui(f"제어코드 데이터 반영 중입니다... (0/{applied})\n{label}"))
                progress.setRange(0, progress_total_units)
                progress.setValue(0)
                QApplication.processEvents()
        except Exception:
            pass

        counter = {"value": 0}
        changed_ids, changed_indices = self._restore_edge_control_codes_apply_candidates(
            int(getattr(self, "idx", 0) or 0),
            data,
            candidates,
            progress=progress,
            counter=counter,
            total=applied,
            label=str(label),
            progress_base=0,
            progress_total=progress_total_units,
        )
        try:
            if progress is not None:
                progress.setValue(min(applied, progress_total_units))
                QApplication.processEvents()
        except Exception:
            pass

        # 표 셀/행 높이 갱신은 지연한다. 단일 행을 실제 클릭할 때만
        # 해당 번역문과 상태를 데이터에서 읽어와 한 행 높이를 다시 계산한다.
        try:
            self._mark_maker_table_rows_pending_refresh(
                [int(i) + 1 for i in (changed_indices or [])],
                page_idx=int(getattr(self, "idx", 0) or 0),
                db_mode=False,
                reason="control_code_restore",
            )
        except Exception:
            pass
        try:
            if changed_ids and self.cb_mode.currentIndex() == 4:
                # 프리뷰 전체 재구성 금지. 현재 선택 행이 바뀐 경우에도 사용자가 행을 다시 누를 때 갱신되도록 둔다.
                pass
        except Exception:
            pass
        try:
            if progress is not None:
                progress.setLabelText(self.tr_ui("변경 사항을 작업 데이터에 반영하는 중입니다..."))
                progress.setValue(max(0, progress_total_units - 1))
                QApplication.processEvents()
        except Exception:
            pass
        try:
            if applied:
                current_page_idx = int(getattr(self, "idx", 0) or 0)
                self.finalize_maker_text_data_change(
                    changed_ids,
                    fields=["translated_text"],
                    page_idx=current_page_idx,
                    reason="control_code_restore",
                )
                self.mark_maker_writeback_dirty(page_indices=[current_page_idx], reason="control_code_restore")
        except Exception:
            pass
        try:
            if progress is not None:
                progress.setValue(progress_total_units)
                QApplication.processEvents()
                progress.close()
                progress.deleteLater()
        except Exception:
            pass
        self.log(f"🧩 제어코드 {label} 복원 완료: 적용 {applied}개 / 이미 적용 {already}개 / 수동필요 {manual}개 / 빈 번역 {empty}개 / 제어코드 없음 {none}개")
        self._audit_translate_event(
            "TRANSLATE_CONTROL_CODE_MANUAL_RESTORE_APPLIED",
            scope=str(label),
            applied=int(applied),
            already=int(already),
            manual=int(manual),
            empty=int(empty),
            none=int(none),
            table_partial_update=0,
            table_lazy_rows=int(len(changed_indices or [])),
        )

    def _maker_text_type_label(self, text_type):
        raw = str(text_type or "").strip()
        mapping = {
            "text": self.tr_ui("대사"),
            "dialogue": self.tr_ui("대사"),
            "show_text": self.tr_ui("대사"),
            "choice": self.tr_ui("선택지"),
            "scroll": self.tr_ui("스크롤문"),
            "scrolling_text": self.tr_ui("스크롤문"),
            "common_dialogue": self.tr_ui("공통 대사"),
            "common_scrolling_text": self.tr_ui("공통 스크롤문"),
            "common_event": self.tr_ui("공통 이벤트"),
            "database": self.tr_ui("데이터베이스"),
            "plugin": self.tr_ui("플러그인"),
        }
        if raw.startswith("choice["):
            return self.tr_ui("선택지")
        if raw.startswith("common_choice["):
            return self.tr_ui("공통 선택지")
        if raw.startswith("database:"):
            try:
                tail = raw.split(":", 1)[1]
                if "." in tail:
                    group, field = tail.split(".", 1)
                    return f"{self.tr_ui('DB')} · {group}.{field}"
            except Exception:
                pass
            return self.tr_ui("데이터베이스")
        return mapping.get(raw, raw or self.tr_ui("대사"))

    def _maker_row_status_text(self, row):
        try:
            # In Maker mode the visible status must follow the translation cell first.
            # A stale explicit maker_status="미번역" can remain after game refresh or
            # older project saves; if translated_text has content, treat it as done.
            translated = str((row or {}).get("translated_text") or "").strip()
            if translated:
                return self.tr_ui("번역완료")
            explicit = str((row or {}).get("maker_status") or "").strip()
            if explicit and explicit not in (self.tr_ui("번역완료"), "Translated", "Done"):
                return explicit
            return self.tr_ui("미번역")
        except Exception:
            return self.tr_ui("미번역")

    def _maker_row_speaker_text(self, row):
        """Return the plain speaker label for the right-side table.

        Inline MV/MZ message speakers can carry control codes in the original
        line, but the main editing table must stay readable.  Control-coded
        speaker shells are reviewed from the separate Speaker Translation dialog;
        this helper always returns a control-code-stripped name.
        """
        meta = (row or {}).get("maker_text_unit") if isinstance(row, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        try:
            source = str((row or {}).get("maker_speaker_source") or meta.get("speaker_source") or "").strip()
        except Exception:
            source = ""
        # PATCH: event names are context, not speakers.  Do not display an
        # event-name fallback in the speaker column/namebox.  The event column
        # already carries that data.
        if source == "event_name":
            return ""
        candidates = [
            (row or {}).get("maker_speaker_plain") if isinstance(row, dict) else "",
            meta.get("speaker_plain"),
            (row or {}).get("maker_speaker") if isinstance(row, dict) else "",
            (row or {}).get("speaker") if isinstance(row, dict) else "",
            meta.get("speaker"),
            meta.get("face_name"),
        ]
        for value in candidates:
            try:
                text = strip_maker_control_codes(value).strip()
            except Exception:
                text = str(value or "").strip()
            if text:
                return text
        return ""

    def _maker_row_speaker_tooltip(self, row):
        meta = (row or {}).get("maker_text_unit") if isinstance(row, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        try:
            source = str((row or {}).get("maker_speaker_source") or meta.get("speaker_source") or "unknown").strip() or "unknown"
        except Exception:
            source = "unknown"
        try:
            confidence = float((row or {}).get("maker_speaker_confidence", meta.get("speaker_confidence", 0.0)) or 0.0)
        except Exception:
            confidence = 0.0
        labels = {
            "manual": self.tr_ui("사용자 지정"),
            "name_window": self.tr_ui("이름창"),
            "actor_escape": self.tr_ui("\\N[n] 배우 참조"),
            "actor_face": self.tr_ui("배우 얼굴칩"),
            "face_name": self.tr_ui("얼굴칩 파일명"),
            "event_name": self.tr_ui("이벤트 이름"),
            "unknown": self.tr_ui("미확정"),
        }
        source_label = labels.get(source, source)
        percent = int(round(max(0.0, min(1.0, confidence)) * 100))
        return self.tr_ui("화자 출처: {source} / 신뢰도 {confidence}%").format(source=source_label, confidence=percent)

    def _maker_row_event_text(self, row):
        meta = (row or {}).get("maker_text_unit") if isinstance(row, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        try:
            source_kind = str(meta.get("source_kind") or "map").strip()
            if source_kind == "database":
                db_kind = str(meta.get("db_kind") or "DB").strip()
                db_id = meta.get("db_id")
                db_field = str(meta.get("db_field") or "").strip()
                base = db_kind
                if db_id is not None:
                    base += f" #{db_id}"
                if db_field:
                    base += f" · {db_field}"
                return base
            if source_kind == "common_event":
                ev_id = str(meta.get("event_id") or "").strip()
                ev_name = str(meta.get("event_name") or "").strip()
                base = f"CE {ev_id}" if ev_id else "CE ?"
                if ev_name:
                    base += f" · {ev_name}"
                return base
            if source_kind == "troop_event":
                ev_id = str(meta.get("event_id") or meta.get("db_id") or "").strip()
                ev_name = str(meta.get("event_name") or "").strip()
                page_index = meta.get("page_index")
                base = f"Troop {ev_id}" if ev_id else "Troop ?"
                if ev_name:
                    base += f" · {ev_name}"
                if page_index is not None:
                    try:
                        base += f" · P{int(page_index) + 1}"
                    except Exception:
                        pass
                return base
            ev_id = str(meta.get("event_id") or "").strip()
            ev_name = str(meta.get("event_name") or "").strip()
            page_index = meta.get("page_index")
            base = f"EV {ev_id}" if ev_id else "EV ?"
            if ev_name:
                base += f" · {ev_name}"
            if page_index is not None:
                base += f" · P{int(page_index) + 1}"
            return base
        except Exception:
            return str(meta.get("event_name") or meta.get("db_field") or "")

    def _configure_text_table_columns_for_current_page(self):
        """Switch the right-side table between image/OCR columns and Maker columns."""
        if not hasattr(self, "tab"):
            return
        maker = self._is_maker_text_table_mode()
        old_block = False
        try:
            old_block = self.tab.blockSignals(True)
        except Exception:
            old_block = False
        try:
            if maker:
                try:
                    self.tab.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
                    self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
                    self.tab.setDragEnabled(False)
                    self.tab.setAcceptDrops(False)
                    self.tab.viewport().setAcceptDrops(False)
                    self.tab.setDropIndicatorShown(False)
                    self.tab.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
                    self.tab.setDragDropOverwriteMode(False)
                    self.tab.setProperty("ysb_excel_like_text_table", True)
                    self.tab.setProperty("ysb_copy_blank_line_between_rows", True)
                    # Map/event text rows are sized once on load and then only
                    # the explicitly clicked row is auto-sized.  Keeping the
                    # header in Interactive mode prevents bulk setText() from
                    # recalculating every row height.
                    self.tab.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
                except Exception:
                    pass
                if self.tab.columnCount() != 8:
                    self.tab.setColumnCount(8)
                self.tab.setHorizontalHeaderLabels([
                    "ID",
                    self.tr_ui("상태"),
                    self.tr_ui("화자"),
                    self.tr_ui("타입"),
                    self.tr_ui("이벤트"),
                    self.tr_ui("원문"),
                    self.tr_ui("번역문"),
                    self.tr_ui("메모"),
                ])
                try:
                    self.tab.setItemDelegateForColumn(6, MultilineDelegate(
                        self.tab,
                        shortcut_getter=self.get_special_shortcuts,
                        linebreak_getter=self.get_linebreak_shortcut,
                        enter_commit_callback=self._advance_table_editor_after_enter,
                    ))
                except Exception:
                    pass
                try:
                    header = self.tab.horizontalHeader()
                    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
                    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
                    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
                    header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
                    header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
                    header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
                    header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
                    header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
                    self.tab.setColumnWidth(0, 46)
                    self.tab.setColumnWidth(1, 78)
                    self.tab.setColumnWidth(2, 92)
                    self.tab.setColumnWidth(3, 78)
                    self.tab.setColumnWidth(4, 130)
                    self.tab.setColumnWidth(7, 120)
                except Exception:
                    pass
            else:
                try:
                    self.tab.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
                    self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
                    self.tab.setProperty("ysb_excel_like_text_table", False)
                    self.tab.setProperty("ysb_copy_blank_line_between_rows", False)
                except Exception:
                    pass
                if self.tab.columnCount() != 4:
                    self.tab.setColumnCount(4)
                self.tab.setHorizontalHeaderLabels(["ID", "X", self.tr_ui("원문"), self.tr_ui("번역")])
                try:
                    self.tab.setItemDelegateForColumn(3, MultilineDelegate(
                        self.tab,
                        shortcut_getter=self.get_special_shortcuts,
                        linebreak_getter=self.get_linebreak_shortcut,
                        enter_commit_callback=self._advance_table_editor_after_enter,
                    ))
                except Exception:
                    pass
                try:
                    self.tab.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
                    self.tab.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
                    self.tab.setColumnWidth(0, 46)
                    self.tab.setColumnWidth(1, 28)
                except Exception:
                    pass
        finally:
            try:
                self.tab.blockSignals(old_block)
            except Exception:
                pass

    def _make_table_item(self, text="", *, editable=True, center=False, user_value=None):
        item = QTableWidgetItem(str(text or ""))
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        if center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole, str(user_value if user_value is not None else text or ""))
        return item

    def refresh_maker_translation_summary_header(self):
        """Refresh the ALL/header row translation counts without rebuilding the table.

        Maker map/DB tables use row 0 as a live summary row.  Individual cell
        edits update the row status immediately, so the summary must move at the
        same time.  Do not call ref_tab() here: that would rebuild the whole
        table and make simple text edits feel heavy again.
        """
        tab = getattr(self, "tab", None)
        if tab is None:
            return False
        try:
            if tab.rowCount() <= 0 or tab.columnCount() < 7:
                return False
        except Exception:
            return False

        try:
            db_mode = bool(hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
        except Exception:
            db_mode = False

        rows = []
        label = self.tr_ui("현재 맵 텍스트")
        if db_mode:
            try:
                actual_idx = int(getattr(self, "maker_database_idx", getattr(self, "idx", 0)) or 0)
            except Exception:
                actual_idx = int(getattr(self, "idx", 0) or 0)
            page = self.data.get(actual_idx) if isinstance(getattr(self, "data", None), dict) else None
            if not isinstance(page, dict):
                return False
            try:
                filtered = self._maker_database_filtered_rows_for_page(page) if hasattr(self, "_maker_database_filtered_rows_for_page") else list(enumerate(page.get("data") or []))
                rows = [r for _idx, r in filtered]
            except Exception:
                rows = list(page.get("data") or [])
            label = self.tr_ui("현재 DB 텍스트")
        else:
            try:
                if not self._is_maker_text_table_mode():
                    return False
            except Exception:
                return False
            page = self.data.get(self.idx) if isinstance(getattr(self, "data", None), dict) else None
            if not isinstance(page, dict):
                return False
            rows = list(page.get("data") or [])

        try:
            translated = sum(1 for r in rows if str((r or {}).get("translated_text") or "").strip())
            total = len(rows)
            summary = f"{self.tr_ui('번역완료')} {translated} / {self.tr_ui('미번역')} {max(0, total - translated)}"
            left = f"{label} · {total}"

            old_block = tab.blockSignals(True)
            try:
                for col, text in ((5, left), (6, summary)):
                    item = tab.item(0, col)
                    if item is None:
                        item = self._make_table_item(text, editable=False)
                        tab.setItem(0, col, item)
                    else:
                        item.setText(text)
                        item.setData(Qt.ItemDataRole.UserRole, text)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
            finally:
                tab.blockSignals(old_block)
            return True
        except Exception:
            return False

    def ref_tab(self):
        try:
            self.audit_boundary_event("REF_TAB_ENTER", throttle_ms=250, stack=True)
        except Exception:
            pass
        try:
            self._configure_text_table_columns_for_current_page()
        except Exception:
            pass
        curr = self.data.get(self.idx)
        maker_mode = self._is_maker_text_table_mode()
        if not curr:
            self._table_check_lock = True
            self.tab.blockSignals(True)
            try:
                self._configure_text_table_columns_for_current_page()
                self.tab.clearContents()
                self.tab.setRowCount(1)

                all_id_item = self._make_table_item("ALL", editable=False, center=True)
                self.tab.setItem(0, 0, all_id_item)

                if maker_mode:
                    self.tab.setItem(0, 1, self._make_table_item(self.tr_ui("전체"), editable=False, center=True))
                    self.tab.setItem(0, 2, self._make_table_item("", editable=False))
                    self.tab.setItem(0, 3, self._make_table_item("", editable=False))
                    self.tab.setItem(0, 4, self._make_table_item("", editable=False))
                    self.tab.setItem(0, 5, self._make_table_item(self.tr_ui("현재 맵 텍스트"), editable=False))
                    self.tab.setItem(0, 6, self._make_table_item("", editable=False))
                    self.tab.setItem(0, 7, self._make_table_item("", editable=False))
                else:
                    all_check_item = QTableWidgetItem("")
                    all_check_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    self.tab.setItem(0, 1, all_check_item)
                    self.tab.setCellWidget(0, 1, self.make_center_check_widget(0, False))
                    self.tab.setItem(0, 2, QTableWidgetItem(self.tr_ui("전체 선택")))
                    self.tab.setItem(0, 3, QTableWidgetItem(""))

                self.paint_all_row_header()
                for c in range(self.tab.columnCount()):
                    item = self.tab.item(0, c)
                    if item:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
            finally:
                self.tab.blockSignals(False)
                self._table_check_lock = False

            self.tab.resizeRowsToContents()
            return

        d = curr.get('data', [])

        self._table_check_lock = True
        self.tab.blockSignals(True)
        try:
            self._configure_text_table_columns_for_current_page()
            self.tab.clearContents()
            self.tab.setRowCount(len(d) + 1)
            try:
                for row in range(self.tab.rowCount()):
                    for col in range(self.tab.columnCount()):
                        if self.tab.cellWidget(row, col):
                            self.tab.removeCellWidget(row, col)
            except Exception:
                pass

            all_checked = len(d) > 0 and all(x.get('use_inpaint', True) for x in d)

            all_id_item = self._make_table_item("ALL", editable=False, center=True)
            self.tab.setItem(0, 0, all_id_item)

            if maker_mode:
                untranslated_count = 0
                translated_count = 0
                for x in d:
                    if str((x or {}).get('translated_text') or '').strip():
                        translated_count += 1
                    else:
                        untranslated_count += 1
                self.tab.setItem(0, 1, self._make_table_item(self.tr_ui("전체"), editable=False, center=True))
                self.tab.setItem(0, 2, self._make_table_item("", editable=False))
                self.tab.setItem(0, 3, self._make_table_item("", editable=False))
                self.tab.setItem(0, 4, self._make_table_item("", editable=False))
                summary = self.tr_ui("현재 맵 텍스트") + f" · {len(d)}"
                self.tab.setItem(0, 5, self._make_table_item(summary, editable=False))
                self.tab.setItem(0, 6, self._make_table_item(f"{self.tr_ui('번역완료')} {translated_count} / {self.tr_ui('미번역')} {untranslated_count}", editable=False))
                self.tab.setItem(0, 7, self._make_table_item("", editable=False))
            else:
                all_check_item = QTableWidgetItem("")
                all_check_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.tab.setItem(0, 1, all_check_item)
                self.tab.setCellWidget(0, 1, self.make_center_check_widget(0, all_checked))
                self.tab.setItem(0, 2, QTableWidgetItem(self.tr_ui("전체 선택")))
                self.tab.setItem(0, 3, QTableWidgetItem(""))

            self.paint_all_row_header()
            for c in range(self.tab.columnCount()):
                item = self.tab.item(0, c)
                if item:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)

            for i, x in enumerate(d):
                try:
                    self.sanitize_text_data_object_prefixes(x)
                except Exception:
                    pass
                row = i + 1
                is_checked = bool(x.get('use_inpaint', True))

                id_item = self._make_table_item(str(x.get('id', i + 1)), editable=False, center=True)
                self.tab.setItem(row, 0, id_item)

                if maker_mode:
                    meta = x.get('maker_text_unit') if isinstance(x, dict) else {}
                    if not isinstance(meta, dict):
                        meta = {}
                    status_text = self._maker_row_status_text(x)
                    speaker_text = self._maker_row_speaker_text(x)
                    type_text = self._maker_text_type_label(meta.get('text_type'))
                    event_text = self._maker_row_event_text(x)
                    original_text = self._maker_display_original_text(x, data_index=i)
                    translated_text = str(x.get('translated_text', '') or '')
                    memo_text = str(x.get('maker_memo', '') or '')
                    control_info = self._maker_control_info_for_row(x)

                    self.tab.setItem(row, 1, self._make_table_item(status_text, editable=True, center=True, user_value=status_text))
                    speaker_item = self._make_table_item(speaker_text, editable=True, user_value=speaker_text)
                    try:
                        speaker_item.setToolTip(self._maker_row_speaker_tooltip(x))
                    except Exception:
                        pass
                    self.tab.setItem(row, 2, speaker_item)
                    self.tab.setItem(row, 3, self._make_table_item(type_text, editable=False, center=True, user_value=type_text))
                    self.tab.setItem(row, 4, self._make_table_item(event_text, editable=False, user_value=event_text))
                    original_item = self._make_table_item(original_text, editable=True, user_value=str(x.get('text', '') or ''))
                    try:
                        tip = self._maker_control_cell_tooltip(x)
                        if tip:
                            original_item.setToolTip(tip)
                            if control_info.get("placement") == "edge" and control_info.get("auto_restorable"):
                                original_item.setForeground(QBrush(QColor("#D9C38A")))
                            else:
                                original_item.setForeground(QBrush(QColor("#D7A3A9")))
                    except Exception:
                        pass
                    self.tab.setItem(row, 5, original_item)
                    self.tab.setItem(row, 6, self._make_table_item(translated_text, editable=True, user_value=translated_text))
                    self.tab.setItem(row, 7, self._make_table_item(memo_text, editable=True, user_value=memo_text))
                else:
                    check_item = QTableWidgetItem("")
                    check_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    self.tab.setItem(row, 1, check_item)
                    self.tab.setCellWidget(row, 1, self.make_center_check_widget(row, is_checked))

                    if x.get('rasterized_text'):
                        display_text = str(x.get('text', '') or '')
                        display_trans = str(x.get('translated_text', '') or x.get('object_source_text', '') or '')
                        text_item = QTableWidgetItem(display_text)
                        trans_item = QTableWidgetItem("[객체] " + display_trans)
                        text_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                        trans_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    else:
                        text_item = QTableWidgetItem(x.get('text', ''))
                        trans_item = QTableWidgetItem(x.get('translated_text', ''))
                    text_item.setData(Qt.ItemDataRole.UserRole, str(x.get('text', '') or ''))
                    trans_item.setData(Qt.ItemDataRole.UserRole, str(x.get('translated_text', '') or ''))
                    self.tab.setItem(row, 2, text_item)
                    self.tab.setItem(row, 3, trans_item)

                self.set_table_row_visual(row, True if maker_mode else is_checked)
        finally:
            self.tab.blockSignals(False)
            self._table_check_lock = False

        self.tab.resizeRowsToContents()
        try:
            if maker_mode:
                self._clear_maker_table_pending_refresh(
                    page_idx=int(getattr(self, "idx", 0) or 0), db_mode=False
                )
                self._maker_table_current_marker_row = -1
                self.refresh_maker_table_current_row_marker()
        except Exception:
            pass

    def scan_maker_game_action(self):
        """쯔꾸르붕이 기준명: 게임/맵 데이터를 다시 스캔한다. 현재는 기존 분석 루틴으로 연결한다."""
        return self.anal()

    def anal(self):
        if bool(getattr(self, "tktool_phase2_enabled", False)):
            try:
                self.log("ℹ️ 쯔꾸르붕이의 게임 텍스트 분석은 [게임 가져오기] 때 자동으로 수행됩니다.")
            except Exception:
                pass
            return
        if not self.ensure_engine_ready():
            return
        if not self.paths:
            self.log("⚠️ 이미지가 없습니다. 먼저 프로젝트에 이미지를 불러와 주세요.")
            return
        if not self.check_ocr_api_or_alert():
            return
        if not self.confirm_ocr_analysis_regions_before_run([self.idx]):
            self.log("↩️ OCR 분석 취소")
            return

        self.commit_current_page_ui_to_data(include_mask=False)

        target_idx = self.idx
        self.prepare_text_mask_slots_for_fresh_analysis(target_idx)
        self._long_task_cancel_requested = False
        self.prepare_task_progress_overlay("분석", "OCR/API 분석을 진행 중입니다.", total=0, cancellable=True)
        self.begin_busy_state("분석")
        self.w = AnalysisWorker(
            self.engine,
            self.get_inpainting_input_path(target_idx),
            analysis_regions=copy.deepcopy(self.data.get(target_idx, {}).get('ocr_analysis_regions', []) or []),
        )
        self._active_task_worker = self.w
        self.w.log.connect(lambda msg: self.handle_long_task_message(msg))
        self.w.finished.connect(
            lambda o, d, mm, mi, page_idx=target_idx:
                self.anal_end_for_page(page_idx, o, d, mm, mi, preserve_text_mask=False)
        )
        self.w.start()

    def reanalyze_mask(self):
        if bool(getattr(self, "tktool_phase2_enabled", False)):
            try:
                self.log("⛔ 쯔꾸르붕이에서는 OCR 재분석을 사용하지 않습니다.")
            except Exception:
                pass
            return
        mode_idx = self.cb_mode.currentIndex()

        if mode_idx not in [2, 3]:
            return

        m = self.view.get_mask_np()
        if m is None:
            return

        target_idx = self.idx
        curr = self.data[target_idx]

        if mode_idx == 2:
            # 텍스트 마스크는 현재 토글 상태의 저장 슬롯에 저장
            self.set_active_mask(curr, m, mode_idx)
            curr['mask_toggle_enabled'] = self.mask_toggle_enabled

            # 워커에 넘길 기존 데이터는 복사본으로 넘긴다.
            # 그래야 재분석 중 기존 페이지 데이터가 직접 흔들리지 않는다.
            existing_data = copy.deepcopy(curr.get('data', []))

            if not self.check_ocr_api_or_alert():
                return

            self.begin_busy_state("텍스트 마스크 재분석")
            self.w = AnalysisWorker(
                self.engine,
                self.get_inpainting_input_path(target_idx),
                m.copy(),
                existing_data
            )
            self.w.log.connect(self.log)
            self.w.finished.connect(
                lambda o, d, mm, mi, page_idx=target_idx:
                    self.anal_end_for_page(page_idx, o, d, mm, mi, preserve_text_mask=True)
            )
            self.w.start()

        elif mode_idx == 3:
            # 페인팅 마스크는 재분석이 아니라 현재 페이지 저장만
            self.set_active_mask(curr, m, mode_idx)
            curr['mask_toggle_enabled'] = self.mask_toggle_enabled
            self.log((f"💾 Painting mask saved for page {target_idx + 1}" if self.ui_language == LANG_EN else f"💾 {target_idx + 1}페이지 페인팅 마스크 저장됨"))
            self.auto_save_project()

    def prepare_text_mask_slots_for_fresh_analysis(self, page_idx):
        """
        일반 [분석]은 기존 텍스트 마스크를 기준으로 누적하지 않는다.
        재분석은 사용자가 칠한 마스크를 기준으로 보존해야 하지만,
        일반 분석은 OCR 결과로 mask_merge / mask_inpaint를 새로 만들기 때문에
        이전 텍스트 마스크가 화면/저장 슬롯에 남지 않도록 먼저 비운다.
        """
        curr = self.data.get(page_idx)
        if not curr:
            return
        try:
            curr['mask_merge'] = None
            curr['mask_inpaint'] = None
            curr['mask_merge_path'] = None
            curr['mask_inpaint_path'] = None
            # 텍스트 마스크는 ON/OFF 슬롯을 사용하지 않지만, 예전 버전/작업 캐시에서
            # 남아 있을 수 있는 보조 슬롯까지 같이 지워야 전체 분석이 항상 새 상태가 된다.
            curr['mask_merge_off'] = None
            curr['mask_merge_off_path'] = None
            # 일반 분석은 초기화에 가까운 작업이므로 기존 수동/자동 마스킹 슬롯을 모두 비운다.
            curr['mask_inpaint_off'] = None
            curr['mask_inpaint_off_path'] = None
            curr['mask_toggle_enabled'] = True
            if page_idx == getattr(self, 'idx', -1) and self.cb_mode.currentIndex() == 2:
                try:
                    self.view.set_user_mask_np(None)
                except Exception:
                    pass
        except Exception:
            pass

    def anal_end_for_page(self, page_idx, o, d, mm, mi, preserve_text_mask=False):
        """
        분석/재분석 결과를 시작 당시의 page_idx에만 반영한다.
        self.idx를 직접 쓰면 작업 도중 페이지 이동 시 다른 페이지를 덮어쓸 수 있다.

        preserve_text_mask=False: 일반 분석. 기존 텍스트 마스크 슬롯을 버리고 새 OCR 마스크로 교체한다.
        preserve_text_mask=True: 텍스트 마스크 재분석. 사용자가 칠한 재분석 마스크를 보존한다.
        """
        if page_idx < 0 or page_idx >= len(self.paths):
            self.end_busy_state("분석")
            return

        if page_idx not in self.data:
            self.data[page_idx] = {
                'ori': o,
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
                'clean_path': None,
                'working_source': None,
                'working_source_path': None,
                'final_paint': None,
                'final_paint_path': None,
                'final_paint_above': None,
                'final_paint_above_path': None,
                'ocr_analysis_regions': [],
            }

        old_inpaint_off = self.data[page_idx].get('mask_inpaint_off')
        if not preserve_text_mask:
            old_inpaint_off = None

        if preserve_text_mask:
            # 재분석은 사용자가 칠한 텍스트 마스크를 기준으로 OCR을 다시 거는 작업이다.
            # 따라서 워커가 반환한 mm(=재분석에 사용한 마스크)을 그대로 유지한다.
            self.data[page_idx].update({
                'ori': o,
                'data': d,
                'mask_merge': mm,
                'mask_inpaint': mi,
                'mask_toggle_enabled': True,
            })
            if self.data[page_idx].get('mask_merge_off') is None:
                self.data[page_idx]['mask_merge_off'] = None
            if self.data[page_idx].get('mask_inpaint_off') is None:
                self.data[page_idx]['mask_inpaint_off'] = old_inpaint_off
            self.log((
                f"✅ Text mask re-analysis applied to page {page_idx + 1} (manual mask preserved)"
                if self.ui_language == LANG_EN
                else f"✅ {page_idx + 1}페이지 텍스트 마스크 재분석 반영 완료 (재분석 마스크 보존)"
            ))
        else:
            # 일반 분석은 새 OCR 결과를 기준으로 텍스트 마스크를 다시 만드는 작업이다.
            # 단, OCR 분석 영역이 지정되어 있고 기존 분석 데이터가 있다면 전체 결과를 버리지 않고
            # 지정 영역 안의 기존 번호/라인만 새 OCR 결과로 업데이트한다.
            if self.data[page_idx].get('ocr_analysis_regions') and self.data[page_idx].get('data'):
                d, mm, mi = self.merge_ocr_analysis_region_results(page_idx, d, mm, mi, ori_img=o)
            # 이전 mask_merge/mask_inpaint가 남으면 분석을 반복해도 이전 상태가 섞여 보일 수 있으므로
            # 텍스트 마스크 계열은 명시적으로 새 결과로 교체한다.
            self.data[page_idx].update({
                'ori': o,
                'data': d,
                'mask_merge': mm.copy() if isinstance(mm, np.ndarray) else mm,
                'mask_inpaint': mi.copy() if isinstance(mi, np.ndarray) else mi,
                'mask_merge_off': None,
                # 일반 분석은 기존 마스킹 자료를 무시하고 새로 따는 작업이므로 OFF 마스크도 초기화한다.
                'mask_inpaint_off': None,
                'mask_toggle_enabled': True,
            })
            self.log((
                f"✅ Analysis applied to page {page_idx + 1} (text mask rebuilt)"
                if self.ui_language == LANG_EN
                else f"✅ {page_idx + 1}페이지 분석 결과 반영 완료 (텍스트 마스크 새로 생성)"
            ))

        # 현재 보고 있는 페이지가 작업 완료된 페이지일 때만 화면 갱신
        if page_idx == self.idx:
            self.ref_tab()

            # 분석/재분석 결과 반영 직후 분석도 탭으로 이동할 때,
            # 직전 텍스트/페인팅 마스크 화면에 남아 있던 구 마스크가 mode_chg에서
            # 새 분석 결과를 덮어쓰지 않도록 마스크 자동 커밋을 잠시 막는다.
            old_skip_mode_mask_commit = getattr(self, "_skip_mode_mask_commit", False)
            self._skip_mode_mask_commit = True
            try:
                if self.cb_mode.currentIndex() != 1:
                    self.cb_mode.setCurrentIndex(1)
                else:
                    self.mode_chg(1)
            finally:
                self._skip_mode_mask_commit = old_skip_mode_mask_commit

            # ON 강제 조건 1/2: 일반 분석 또는 텍스트 마스크 재분석 완료 직후에만 켠다.
            self.set_mask_toggle_safely(True)

        # ON 강제 조건 1/2: 분석 결과가 들어온 페이지는 분석 마스크 사용 상태로 저장한다.
        # 사용자가 이후 직접 OFF로 바꾸면 다시 임의로 ON시키지 않는다.
        self.data[page_idx]['mask_toggle_enabled'] = True

        self.auto_save_project()

        # 분석/재분석은 OCR/API 결과가 반영되는 작업 경계다.
        # 결과 반영 이후에는 이전 편집 Undo로 돌아가면 마스크/텍스트 상태가 꼬일 수 있으므로
        # 성공적으로 데이터에 적용된 뒤 Undo 체인을 끊는다.
        self.undo_break_boundary("reanalyze" if preserve_text_mask else "analysis")
        self._active_task_worker = None
        self.end_busy_state("텍스트 마스크 재분석" if preserve_text_mask else "분석")
        self.macro_mark_current_step_done("work_analyze")

    def _show_api_missing_and_open_settings(self, category, provider_name, detail_ko=None, detail_en=None):
        """API 설정 누락을 사용자에게 알리고 바로 API 관리창을 연다."""
        lang_en = getattr(self, "ui_language", LANG_KO) == LANG_EN
        category_map = {
            "ocr": ("OCR API", "OCR API"),
            "inpaint": ("인페인팅 API", "Inpainting API"),
            "translation": ("번역 API", "Translation API"),
        }
        category_ko, category_en = category_map.get(category, ("API", "API"))
        if lang_en:
            title = "API Settings Required"
            detail = detail_en or "Required API settings are missing."
            msg = (
                f"The selected {category_en} ({provider_name}) is not configured or its key is missing.\n"
                f"Please check the selected provider and fill in the required settings in [Options > API Settings].\n\n"
                f"Details: {detail}"
            )
            self.log(f"❌ {category_en} missing or invalid: {provider_name}")
        else:
            title = "API 설정 필요"
            detail = detail_ko or "필요한 API 설정이 비어 있습니다."
            msg = (
                f"선택된 {category_ko} ({provider_name}) 설정이 비어 있거나 키가 없습니다.\n"
                f"[옵션 > API 관리]에서 선택된 API와 필수 설정을 확인해 주세요.\n\n"
                f"상세: {detail}"
            )
            self.log(f"❌ {category_ko} 설정 누락: {provider_name}")
        QMessageBox.critical(self, title, msg)
        try:
            self.open_api_settings_dialog()
        except Exception as e:
            self.log((f"⚠️ Failed to open API Settings: {e}" if lang_en else f"⚠️ API 관리창 열기 실패: {e}"))
        return False

    def check_ocr_api_or_alert(self):
        """쯔꾸르붕이 5단계: OCR 기능은 제거되었으므로 직접 호출도 방어적으로 차단한다."""
        self.log("ℹ️ 쯔꾸르붕이에서는 이미지 OCR 기능을 사용하지 않습니다.")
        return False

    def check_inpaint_api_or_alert(self):
        """쯔꾸르붕이 5단계: 인페인팅 기능은 제거되었으므로 직접 호출도 방어적으로 차단한다."""
        self.log("ℹ️ 쯔꾸르붕이에서는 인페인팅 기능을 사용하지 않습니다.")
        return False

    def _lm_studio_models_url_from_base(self, base_url):
        """LM Studio Base URL에서 /models 점검 주소를 만든다."""
        base = str(base_url or "").strip().rstrip("/")
        if not base:
            return ""
        if base.lower().endswith("/v1"):
            return base + "/models"
        return base + "/v1/models"

    def _check_lm_studio_server_or_alert(self, settings):
        """LM Studio Local Server가 실제로 켜져 있는지 번역 시작 전에 차단 확인한다."""
        base_url = str(getattr(settings, "lm_studio_base_url", "") or "").strip().rstrip("/")
        model_name = str(getattr(settings, "lm_studio_model", "") or "").strip()
        models_url = self._lm_studio_models_url_from_base(base_url)
        if not models_url:
            return True
        lang_en = bool(getattr(self, "ui_language", "") == LANG_EN)
        try:
            req = urllib.request.Request(models_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                status = int(getattr(resp, "status", 200) or 200)
                body = resp.read(1024 * 256).decode("utf-8", errors="replace")
            if status < 200 or status >= 300:
                raise RuntimeError(f"HTTP {status}")
            try:
                payload = json.loads(body or "{}")
            except Exception:
                payload = {}
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list) and not data:
                title = "LM Studio Connection Failed" if lang_en else "LM Studio 연결 실패"
                msg = (
                    "The LM Studio server is running, but no model is loaded.\n\n"
                    "Load a model in LM Studio, then try again.\n\n"
                    f"Model: {model_name or '-'}\nBase URL: {base_url}"
                    if lang_en else
                    "LM Studio 서버는 켜져 있지만 로드된 모델이 없습니다.\n\n"
                    "LM Studio에서 모델을 로드한 뒤 다시 시도해 주세요.\n\n"
                    f"모델: {model_name or '-'}\nBase URL: {base_url}"
                )
                QMessageBox.critical(self, title, msg)
                self.log(("❌ LM Studio server has no loaded model." if lang_en else "❌ LM Studio 서버에 로드된 모델이 없습니다."))
                return False
            return True
        except Exception as e:
            detail = str(e) or e.__class__.__name__
            title = "LM Studio Connection Failed" if lang_en else "LM Studio 연결 실패"
            msg = (
                "Cannot connect to the LM Studio Local Server.\n\n"
                "Start the server in LM Studio > Developer > Local Server, then try again.\n\n"
                f"Base URL: {base_url}\nCheck URL: {models_url}\nDetails: {detail}"
                if lang_en else
                "LM Studio Local Server에 연결할 수 없습니다.\n\n"
                "LM Studio > Developer > Local Server에서 서버를 켠 뒤 다시 시도해 주세요.\n\n"
                f"Base URL: {base_url}\n확인 주소: {models_url}\n상세: {detail}"
            )
            QMessageBox.critical(self, title, msg)
            self.log((f"❌ LM Studio connection failed: {detail}" if lang_en else f"❌ LM Studio 연결 실패: {detail}"))
            return False

    def check_translation_api_key_or_alert(self, provider=None):
        """번역 API 키가 없을 때 원문 반환으로 조용히 넘어가지 않게 UI에서 먼저 막는다."""
        settings = getattr(self, "api_settings", None) or ApiSettingsStore.load()
        provider = (provider or getattr(settings, "selected_translation_provider", "openai") or self.cb_trans_provider.currentData() or "openai").lower()

        def _provider_display_name(code: str) -> str:
            mapping = {
                "openai": "OpenAI",
                "deepseek": "DeepSeek",
                "google": "Google Translate",
                "gemini": "Gemini",
                "gemini_deferred": "Gemini Flex / Batch",
                "custom": "Custom / OpenAI-Compatible",
                "lm_studio": "LM Studio / Local OpenAI-Compatible",
            }
            return mapping.get((code or "").lower(), str(code or "OpenAI"))

        if provider in ("local_argos", "local_hf_jako", "local_hf_enko", "local_nllb"):
            # Legacy local translation providers are no longer supported.
            provider = "openai"

        provider_name = _provider_display_name(provider)

        if provider == "deepseek":
            if not str(getattr(settings, "deepseek_api_key", "") or "").strip():
                return self._show_api_missing_and_open_settings("translation", provider_name, "DeepSeek API Key가 비어있습니다.", "DeepSeek API Key is empty.")
        elif provider == "google":
            if not str(getattr(settings, "google_translate_api_key", "") or "").strip():
                return self._show_api_missing_and_open_settings("translation", provider_name, "Google Translate API Key가 비어있습니다.", "Google Translate API Key is empty.")
        elif provider == "gemini":
            if not str(getattr(settings, "gemini_api_key", "") or "").strip():
                return self._show_api_missing_and_open_settings("translation", provider_name, "Gemini API Key가 비어있습니다.", "Gemini API Key is empty.")
        elif provider == "gemini_deferred":
            missing = []
            if not str(getattr(settings, "gemini_delayed_api_key", "") or "").strip():
                missing.append("API Key")
            if not str(getattr(settings, "gemini_delayed_model", "") or "").strip():
                missing.append("Model")
            if missing:
                return self._show_api_missing_and_open_settings(
                    "translation",
                    provider_name,
                    "Gemini Flex / Batch " + ", ".join(missing) + " 설정이 비어있습니다.",
                    "Gemini Flex / Batch " + ", ".join(missing) + " setting(s) are empty.",
                )
        elif provider == "custom":
            missing = []
            if not str(getattr(settings, "custom_translation_base_url", "") or "").strip():
                missing.append("Base URL")
            if not str(getattr(settings, "custom_translation_model", "") or "").strip():
                missing.append("Model")
            if not str(getattr(settings, "custom_translation_api_key", "") or "").strip():
                missing.append("API Key")
            if missing:
                return self._show_api_missing_and_open_settings(
                    "translation",
                    provider_name,
                    "Custom 번역 API " + ", ".join(missing) + " 설정이 비어있습니다.",
                    "Custom translation API " + ", ".join(missing) + " setting(s) are empty.",
                )
        elif provider == "lm_studio":
            missing = []
            if not str(getattr(settings, "lm_studio_base_url", "") or "").strip():
                missing.append("Base URL")
            if not str(getattr(settings, "lm_studio_model", "") or "").strip():
                missing.append("Model")
            if missing:
                return self._show_api_missing_and_open_settings(
                    "translation",
                    provider_name,
                    "LM Studio " + ", ".join(missing) + " 설정이 비어있습니다. LM Studio에서 모델을 로드하고 서버를 켠 뒤 입력해 주세요.",
                    "LM Studio " + ", ".join(missing) + " setting(s) are empty. Load a model and start the server in LM Studio first.",
                )
            if not self._check_lm_studio_server_or_alert(settings):
                return False
        else:
            if not str(getattr(settings, "openai_api_key", "") or "").strip():
                return self._show_api_missing_and_open_settings("translation", provider_name, "OpenAI API Key가 비어있습니다.", "OpenAI API Key is empty.")

        return True

    def _selected_table_cells_for_translation(self, curr=None, *, db_mode=False):
        """Return translation targets from an explicit Qt table selection only.

        This is intentionally narrower than the visual red-row marker.  The red row
        is a display aid, but using old marker/background state as a translate
        trigger can swallow the normal whole-map translation path.  The translate
        button decides selected-row translation only from the table selection model
        (selectedIndexes/selectedRanges).
        """
        selected_cell_count = 0
        valid_cell_count = 0
        targets_by_row = {}
        try:
            table = getattr(self, "tab", None)
            if table is None:
                return [], 0, 0
            selected_rows = {}
            seen_cells = set()

            def add_row_cell(row, col=None, *, counted=True):
                nonlocal selected_cell_count
                try:
                    row = int(row)
                except Exception:
                    return
                if row <= 0:
                    return
                if col is None:
                    try:
                        cols = range(0, max(1, int(table.columnCount() or 1)))
                    except Exception:
                        cols = [0]
                else:
                    try:
                        cols = [int(col)]
                    except Exception:
                        cols = [0]
                for c in cols:
                    if c < 0:
                        continue
                    key = (row, int(c))
                    if key in seen_cells:
                        continue
                    seen_cells.add(key)
                    selected_rows.setdefault(row, set()).add(int(c))
                    if counted:
                        selected_cell_count += 1

            # Explicit live Qt cell selection.
            for idx in table.selectedIndexes() or []:
                try:
                    add_row_cell(idx.row(), idx.column())
                except Exception:
                    continue

            # Explicit range selection fallback.
            try:
                for rg in table.selectedRanges() or []:
                    for row in range(int(rg.topRow()), int(rg.bottomRow()) + 1):
                        if row <= 0:
                            continue
                        for col in range(int(rg.leftColumn()), int(rg.rightColumn()) + 1):
                            add_row_cell(row, col)
            except Exception:
                pass

            if selected_cell_count <= 0:
                return [], 0, 0

            data = list((curr or {}).get("data") or []) if isinstance(curr, dict) else []
            for row in sorted(selected_rows):
                data_index = self._maker_data_index_for_table_row(row, db_mode=db_mode)
                if data_index < 0 or data_index >= len(data):
                    continue
                try:
                    if db_mode and hasattr(self, "_is_maker_database_row_translatable") and not self._is_maker_database_row_translatable(data[data_index]):
                        continue
                except Exception:
                    pass
                source_text = str((data[data_index] or {}).get("text") or "")
                if not source_text.strip():
                    continue
                cols = set(selected_rows.get(row) or set())
                valid_cell_count += max(1, len(cols))
                targets_by_row[row] = {
                    "row": int(row),
                    "data_index": int(data_index),
                    "selected_columns": set(int(c) for c in cols),
                    "selected_cell_count": int(len(cols) or 1),
                }
        except Exception:
            return [], int(selected_cell_count or 0), int(valid_cell_count or 0)

        targets = []
        for row in sorted(targets_by_row):
            target = dict(targets_by_row[row])
            try:
                target["selected_columns"] = sorted(int(c) for c in (target.get("selected_columns") or []))
            except Exception:
                target["selected_columns"] = []
            targets.append(target)
        return targets, int(selected_cell_count or 0), int(valid_cell_count or 0)

    def _selected_table_rows_for_translation(self, curr=None, *, db_mode=False):
        """Compatibility wrapper: return rows touched by translatable selected cells."""
        try:
            targets, _selected_cell_count, _valid_cell_count = self._selected_table_cells_for_translation(curr, db_mode=db_mode)
            return [int(t.get("row")) for t in targets if isinstance(t, dict)]
        except Exception:
            return []

    def _maker_data_index_for_table_row(self, row, *, db_mode=False):
        try:
            row = int(row)
        except Exception:
            return -1
        if row <= 0:
            return -1
        data_index = row - 1
        if db_mode:
            try:
                id_item = self.tab.item(row, 0)
                v = id_item.data(Qt.ItemDataRole.UserRole) if id_item is not None else None
                if v is not None:
                    data_index = int(v)
            except Exception:
                data_index = row - 1
        return data_index

    def _line_bounds_for_text(self, text):
        """Return (line_index, start, end_without_newline, end_with_newline) bounds."""
        src = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        if src == "":
            return [(0, 0, 0, 0)]
        bounds = []
        start = 0
        parts = src.split("\n")
        for i, part in enumerate(parts):
            end = start + len(part)
            end_with_newline = end + (1 if i < len(parts) - 1 else 0)
            bounds.append((i, start, end, end_with_newline))
            start = end_with_newline
        return bounds

    def _selected_line_range_from_offsets(self, text, start, end):
        try:
            start = int(start)
            end = int(end)
        except Exception:
            return None
        if end < start:
            start, end = end, start
        if end <= start:
            return None
        text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        bounds = self._line_bounds_for_text(text)
        # If the selection ends exactly at the start of a following line because the
        # newline was included, keep that following line out of the target range.
        effective_end = max(start, end - 1)
        selected = []
        for line_idx, line_start, line_end, line_end_with_newline in bounds:
            if start <= line_end_with_newline and effective_end >= line_start:
                # Ignore pure newline-only overlap with an empty trailing area.
                if effective_end < line_start or start > line_end_with_newline:
                    continue
                selected.append(line_idx)
        if not selected:
            return None
        return min(selected), max(selected)

    def _line_text_slice(self, text, line_start, line_end):
        lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if not lines:
            lines = [""]
        try:
            line_start = max(0, int(line_start))
            line_end = max(line_start, int(line_end))
        except Exception:
            return ""
        if line_start >= len(lines):
            return ""
        line_end = min(line_end, len(lines) - 1)
        return "\n".join(lines[line_start:line_end + 1])

    def _selected_text_segments_for_translation(self, curr=None, *, db_mode=False):
        """Return selected in-cell line segments for Maker selected-line translation.

        This catches the QTextEdit delegate selection that can disappear visually when
        the translate button is clicked.  The delegate stores the last explicit text
        selection on the main window, and this function validates it against the
        current table/data before using it.
        """
        cache = getattr(self, "_ysb_table_text_selection_for_translation", None)
        if not isinstance(cache, dict):
            return []
        try:
            # Keep the selection short-lived to avoid stale accidental partial
            # translation after the user moves on to another row.
            if time.time() - float(cache.get("timestamp") or 0.0) > 30.0:
                return []
        except Exception:
            return []
        try:
            row = int(cache.get("row"))
            col = int(cache.get("col"))
        except Exception:
            return []
        if row <= 0:
            return []
        try:
            valid_cols = {int(self._table_text_column()), int(self._table_translation_column())}
            if col not in valid_cols:
                return []
        except Exception:
            pass
        data = list((curr or {}).get("data") or []) if isinstance(curr, dict) else []
        data_index = self._maker_data_index_for_table_row(row, db_mode=db_mode)
        if data_index < 0 or data_index >= len(data):
            return []
        try:
            if db_mode and hasattr(self, "_is_maker_database_row_translatable") and not self._is_maker_database_row_translatable(data[data_index]):
                return []
        except Exception:
            pass
        full_text = str(cache.get("full_text") or "")
        rng = self._selected_line_range_from_offsets(full_text, cache.get("selection_start"), cache.get("selection_end"))
        if rng is None:
            return []
        line_start, line_end = rng
        # Translation source must come from the original/source text, not from the
        # edited display cache.  Line numbers are mapped against the source text.
        source_text = str(data[data_index].get("text") or "")
        source_piece = self._line_text_slice(source_text, line_start, line_end)
        if not source_piece.strip():
            return []
        return [{
            "row": row,
            "data_index": data_index,
            "line_start": line_start,
            "line_end": line_end,
            "source_text": source_piece,
            "source_full_text": source_text,
        }]

    def _format_ui_text(self, template, **kwargs):
        """Translate a UI text and safely apply format placeholders.

        MainWindow.tr_ui() does not accept **kwargs, so confirmation dialogs must
        translate first and then format.  Passing kwargs directly to self.tr_ui()
        raises TypeError and made selected-translation confirmation return False
        before the dialog was shown.
        """
        try:
            text = self.tr_ui(template)
        except Exception:
            text = str(template or "")
        try:
            return str(text).format(**kwargs)
        except Exception:
            return str(text)

    def _exec_translate_confirm_dialog(self, title, text, **fields):
        """Show a real modal confirmation dialog for selected translation."""
        try:
            self._audit_translate_event("TRANSLATE_CONFIRM_DIALOG_SHOW", title=str(title or ""), **fields)
        except Exception:
            pass
        try:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setWindowTitle(str(title or ""))
            msg.setText(str(text or ""))
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            msg.setEscapeButton(QMessageBox.StandardButton.No)
            try:
                msg.setWindowModality(Qt.WindowModality.ApplicationModal)
            except Exception:
                pass
            try:
                msg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass
            try:
                apply_message_box_palette(msg, False)
            except Exception:
                pass
            try:
                QTimer.singleShot(0, msg.raise_)
                QTimer.singleShot(0, msg.activateWindow)
            except Exception:
                pass
            result = msg.exec()
            clicked = msg.clickedButton()
            accepted = False
            try:
                accepted = msg.standardButton(clicked) == QMessageBox.StandardButton.Yes
            except Exception:
                accepted = False
            try:
                if not accepted and int(result) == int(QMessageBox.StandardButton.Yes):
                    accepted = True
            except Exception:
                pass
            try:
                self._audit_translate_event(
                    "TRANSLATE_CONFIRM_DIALOG_RESULT",
                    accepted=bool(accepted),
                    result=int(result) if result is not None else -1,
                    clicked_text=clicked.text() if clicked is not None and hasattr(clicked, "text") else "",
                    **fields,
                )
            except Exception:
                pass
            return bool(accepted)
        except Exception as e:
            try:
                self._audit_translate_event("TRANSLATE_CONFIRM_DIALOG_ERROR", error=f"{type(e).__name__}: {e}", **fields)
            except Exception:
                pass
            try:
                self.log(f"⚠️ 선택 번역 확인창 표시 실패: {type(e).__name__}: {e}")
            except Exception:
                pass
            return False

    def _confirm_translate_selected_targets(self, count, *, partial=False):
        """Ask before translating only selected rows/segments."""
        try:
            count = int(count or 0)
        except Exception:
            count = 0
        if count <= 0:
            return False
        title = self.tr_ui("선택한 줄만 번역")
        if partial:
            text = self._format_ui_text(
                "현재 오른쪽 텍스트 칸에서 일부 줄이 선택되어 있습니다. 전체 대사가 아니라 선택한 줄만 번역합니다.\n\n대상: {count}줄\n\n진행할까요?",
                count=count,
            )
        else:
            text = self._format_ui_text(
                "현재 오른쪽 텍스트 표에서 줄이 선택되어 있습니다. 전체 대상이 아니라 선택한 줄만 번역합니다.\n\n대상: {count}줄\n\n진행할까요?",
                count=count,
            )
        return self._exec_translate_confirm_dialog(title, text, target_count=count, partial=bool(partial))

    def _replace_lines_in_text(self, base_text, line_start, line_end, replacement):
        lines = str(base_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if not lines:
            lines = [""]
        try:
            line_start = max(0, int(line_start))
            line_end = max(line_start, int(line_end))
        except Exception:
            return str(replacement or "")
        while len(lines) <= line_end:
            lines.append("")
        repl_lines = str(replacement or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        lines[line_start:line_end + 1] = repl_lines
        return "\n".join(lines)

    def _start_translation_job(self):
        job_id = uuid.uuid4().hex
        self._active_translation_job_id = job_id
        try:
            canceled = getattr(self, "_canceled_translation_job_ids", None)
            if not isinstance(canceled, set):
                canceled = set()
            self._canceled_translation_job_ids = canceled
        except Exception:
            self._canceled_translation_job_ids = set()
        return job_id

    def _is_active_translation_job(self, job_id):
        if not job_id:
            return True
        try:
            if job_id in (getattr(self, "_canceled_translation_job_ids", set()) or set()):
                return False
        except Exception:
            pass
        return str(getattr(self, "_active_translation_job_id", "") or "") == str(job_id)

    def _clear_translation_runtime_state(self):
        self._translation_target_rows = []
        self._translation_target_texts = []
        self._translation_maker_token_maps = []
        self._translation_maker_contexts = None
        self._translation_target_segments = []
        self._chunked_translation_apply_state = None
        self._translation_database_mode = False
        self._translation_speaker_mode = False
        self._translation_database_idx = None

    def _cancel_active_translation_job(self, reason="user_cancel"):
        job_id = str(getattr(self, "_active_translation_job_id", "") or "")
        if job_id:
            try:
                canceled = getattr(self, "_canceled_translation_job_ids", None)
                if not isinstance(canceled, set):
                    canceled = set()
                canceled.add(job_id)
                self._canceled_translation_job_ids = canceled
            except Exception:
                pass
        self._active_translation_job_id = None
        self._long_task_cancel_requested = True
        try:
            worker = getattr(self, "translation_worker", None)
            if worker is not None and hasattr(worker, "stop"):
                worker.stop()
        except Exception:
            pass
        self._clear_translation_runtime_state()
        try:
            self.handle_long_task_message(
                self.tr_ui("번역 취소됨. 완료된 청크는 유지하고, 현재 응답과 이후 청크는 반영하지 않습니다.")
            )
        except Exception:
            pass
        try:
            self.hide_task_progress_overlay()
        except Exception:
            pass
        try:
            self.end_busy_state("번역")
        except Exception:
            pass
        try:
            self.log(self.tr_ui("⏹️ 번역 취소: 완료된 청크는 유지하고 현재 응답과 이후 청크는 버립니다."))
        except Exception:
            pass

    def _confirm_translate_selected_table_cells(self, targets, *, selected_cell_count=0, valid_cell_count=0):
        """Ask before translating only the selected table cells/rows."""
        try:
            target_count = len(targets or [])
        except Exception:
            target_count = 0
        try:
            selected_cell_count = int(selected_cell_count or 0)
        except Exception:
            selected_cell_count = 0
        try:
            valid_cell_count = int(valid_cell_count or 0)
        except Exception:
            valid_cell_count = 0
        if target_count <= 0:
            return False
        title = self.tr_ui("선택한 셀만 번역")
        cell_count = selected_cell_count or valid_cell_count or target_count
        text = self._format_ui_text(
            "현재 오른쪽 텍스트 표에서 셀이 선택되어 있습니다. 전체 대상이 아니라 선택한 셀에 해당하는 줄만 번역합니다.\n\n선택 셀: {cell_count}개 / 번역 대상: {target_count}줄\n\n진행할까요?",
            cell_count=cell_count,
            target_count=target_count,
        )
        return self._exec_translate_confirm_dialog(
            title,
            text,
            target_count=target_count,
            selected_cell_count=selected_cell_count,
            valid_cell_count=valid_cell_count,
        )

    def _confirm_translate_selected_table_rows(self, rows):
        """Ask before translating only selected table rows."""
        return self._confirm_translate_selected_targets(len(rows or []), partial=False)

    def _audit_translate_event(self, event_name, **fields):
        """Write high-signal translate decision logs to engine_boundary."""
        try:
            if hasattr(self, "audit_boundary_event"):
                self.audit_boundary_event(str(event_name), **fields)
        except Exception:
            pass

    def on_translate_button_clicked(self, *args, **kwargs):
        """Translate button/action entry point.

        This method is intentionally separate from trans().  It decides whether the
        current Maker table selection means "selected rows only" or "whole current
        map/page".  trans() itself must stay the execution body and must not inspect
        red rows / selectedIndexes() again, otherwise the normal whole-map route can
        be swallowed by stale table selection state.
        """
        self._audit_translate_event("TRANSLATE_BUTTON_CLICK")
        try:
            db_mode = bool(hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
        except Exception:
            db_mode = False
        try:
            maker_mode = True if db_mode else bool(self._is_maker_text_table_mode())
        except Exception:
            maker_mode = False

        curr = None
        try:
            if db_mode:
                db_idx = int(getattr(self, "maker_database_idx", 0) or 0)
                curr = self.data.get(db_idx) if isinstance(getattr(self, "data", None), dict) else None
            else:
                curr = self.data.get(self.idx) if isinstance(getattr(self, "data", None), dict) else None
        except Exception:
            curr = None

        selected_targets = []
        selected_cell_count = 0
        valid_cell_count = 0
        if maker_mode and isinstance(curr, dict) and curr.get("data"):
            try:
                selected_targets, selected_cell_count, valid_cell_count = self._selected_table_cells_for_translation(curr, db_mode=db_mode)
            except Exception as e:
                selected_targets, selected_cell_count, valid_cell_count = [], 0, 0
                self._audit_translate_event("TRANSLATE_DECISION_SELECTION_ERROR", error=f"{type(e).__name__}: {e}")
            self._audit_translate_event(
                "TRANSLATE_DECISION_SELECTION_SCAN",
                targets_count=len(selected_targets or []),
                selected_cell_count=int(selected_cell_count or 0),
                valid_cell_count=int(valid_cell_count or 0),
                explicit_only=True,
            )

        if selected_targets:
            rows = []
            for t in selected_targets:
                try:
                    row = int(t.get("row")) if isinstance(t, dict) else -1
                except Exception:
                    row = -1
                if row > 0 and row not in rows:
                    rows.append(row)
            self._audit_translate_event(
                "TRANSLATE_DECISION_SELECTED_ROWS",
                rows_count=len(rows),
                selected_cell_count=int(selected_cell_count or 0),
                valid_cell_count=int(valid_cell_count or 0),
                rows=",".join(str(x) for x in rows[:80]),
            )
            if rows:
                if not self._confirm_translate_selected_table_cells(
                    selected_targets,
                    selected_cell_count=selected_cell_count,
                    valid_cell_count=valid_cell_count,
                ):
                    self._audit_translate_event("TRANSLATE_DECISION_SELECTED_CANCEL", rows_count=len(rows))
                    try:
                        self.log("⏹️ 선택 셀 번역을 취소했습니다.")
                    except Exception:
                        pass
                    return
                self._audit_translate_event("TRANSLATE_DECISION_SELECTED_CONFIRMED", rows_count=len(rows), rows=",".join(str(x) for x in rows[:80]))
                return self.trans(selected_rows=rows, translate_origin="button_selected")

        if selected_cell_count > 0:
            self._audit_translate_event(
                "TRANSLATE_DECISION_SELECTION_NO_VALID_TARGETS_FALLBACK_FULL",
                selected_cell_count=int(selected_cell_count or 0),
                valid_cell_count=int(valid_cell_count or 0),
            )
            try:
                self.log("ℹ️ 선택 표시가 있지만 번역 가능한 선택 행이 없어 현재 맵/페이지 전체 번역으로 진행합니다.")
            except Exception:
                pass
        self._audit_translate_event("TRANSLATE_DECISION_FULL_MAP")
        return self.trans(selected_rows=None, translate_origin="button_full")

    def trans(self, selected_rows=None, *, translate_origin="direct", selected_segments=None):
        if isinstance(selected_rows, bool):
            # Defensive: old Qt signal paths may pass the clicked(bool) payload.
            selected_rows = None
        if not self.ensure_engine_ready():
            self._audit_translate_event("TRANSLATE_CORE_ABORT_ENGINE_NOT_READY", origin=str(translate_origin or ""))
            return
        db_mode = bool(hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
        speaker_mode = bool(hasattr(self, "is_maker_speaker_mode") and self.is_maker_speaker_mode())
        self._translation_database_mode = bool(db_mode)
        self._translation_speaker_mode = bool(speaker_mode)
        self._translation_database_idx = int(getattr(self, "maker_database_idx", 0) or 0) if db_mode else None
        if db_mode:
            db_idx = int(getattr(self, "maker_database_idx", 0) or 0)
            curr = self.data.get(db_idx) if isinstance(getattr(self, "data", None), dict) else None
            if not isinstance(curr, dict):
                self._audit_translate_event("TRANSLATE_CORE_ABORT_NO_DB_TAB", origin=str(translate_origin or ""))
                self.log("⚠️ 번역할 데이터베이스 탭이 없습니다.")
                return
        else:
            if not self.paths:
                self._audit_translate_event("TRANSLATE_CORE_ABORT_NO_IMAGE", origin=str(translate_origin or ""))
                self.log("⚠️ 이미지가 없습니다. 먼저 프로젝트에 이미지를 불러와 주세요.")
                return
            if self.idx not in self.data:
                self._audit_translate_event("TRANSLATE_CORE_ABORT_NO_DATA", origin=str(translate_origin or ""), page_idx=getattr(self, "idx", None))
                self.log("⚠️ 번역할 데이터가 없습니다.")
                return
            curr = self.data.get(self.idx)
        if not curr or not curr.get('data'):
            self._audit_translate_event("TRANSLATE_CORE_ABORT_NO_TEXT_BOX", origin=str(translate_origin or ""))
            self.log("⚠️ 텍스트 박스가 없어서 번역할 게 없습니다.")
            return

        try:
            texts = []
            target_rows = []
            maker_contexts = []
            maker_token_maps = []
            maker_mode = True if db_mode else self._is_maker_text_table_mode()
            maker_prompts = None
            maker_translation_settings = None
            control_code_auto_enabled = bool(
                maker_mode
                and not db_mode
                and getattr(self, "maker_control_code_auto_apply_enabled", True)
            )
            if maker_mode:
                try:
                    maker_prompts = load_maker_character_prompts(getattr(self, "project_dir", None))
                except Exception:
                    maker_prompts = None
                try:
                    maker_translation_settings = load_maker_translation_settings(getattr(self, "project_dir", None))
                except Exception:
                    maker_translation_settings = None
            source_col = self._table_text_column()
            selected_translate_rows = []
            try:
                if selected_rows:
                    seen = set()
                    for row in selected_rows:
                        try:
                            row_i = int(row)
                        except Exception:
                            continue
                        if row_i > 0 and row_i not in seen:
                            selected_translate_rows.append(row_i)
                            seen.add(row_i)
            except Exception:
                selected_translate_rows = []
            selected_translate_segments = list(selected_segments or [])
            self._audit_translate_event(
                "TRANSLATE_CORE_ENTER",
                origin=str(translate_origin or ""),
                maker_mode=bool(maker_mode),
                db_mode=bool(db_mode),
                selected_rows_count=len(selected_translate_rows),
                selected_segments_count=len(selected_translate_segments),
                table_rows=int(self.tab.rowCount() or 0) if hasattr(self, "tab") else -1,
            )
            if selected_translate_segments:
                for seg in selected_translate_segments:
                    row = int(seg.get("row"))
                    data_index = int(seg.get("data_index"))
                    if data_index < 0 or data_index >= len(curr['data']):
                        continue
                    item_copy = dict(curr['data'][data_index] or {})
                    item_copy['text'] = str(seg.get("source_text") or "")
                    payload = prepare_maker_translation_payload(
                        item_copy,
                        maker_prompts,
                        maker_translation_settings,
                        auto_restore_control_codes=control_code_auto_enabled,
                    )
                    texts.append(payload.get("text", ""))
                    maker_contexts.append(payload.get("context", ""))
                    maker_token_maps.append(payload.get("control_map", []))
                    target_rows.append(row)
            else:
                row_iter = selected_translate_rows if selected_translate_rows else range(1, self.tab.rowCount())
                for row in row_iter:
                    data_index = self._maker_data_index_for_table_row(row, db_mode=db_mode)
                    if data_index < 0 or data_index >= len(curr['data']):
                        continue
                    try:
                        if db_mode and hasattr(self, "_is_maker_database_row_translatable") and not self._is_maker_database_row_translatable(curr['data'][data_index]):
                            continue
                    except Exception:
                        pass
                    is_checked = True if maker_mode else self.get_table_check_state(row)
                    curr['data'][data_index]['use_inpaint'] = is_checked
                    if not is_checked:
                        continue
                    if maker_mode:
                        payload = prepare_maker_translation_payload(
                            curr['data'][data_index],
                            maker_prompts,
                            maker_translation_settings,
                            auto_restore_control_codes=control_code_auto_enabled,
                        )
                        texts.append(payload.get("text", ""))
                        maker_contexts.append(payload.get("context", ""))
                        maker_token_maps.append(payload.get("control_map", []))
                    else:
                        item = self.tab.item(row, source_col)
                        texts.append(item.text() if item else "")
                    target_rows.append(row)

            if not texts:
                self._audit_translate_event(
                    "TRANSLATE_NO_TARGETS",
                    origin=str(translate_origin or ""),
                    selected_rows_count=len(selected_translate_rows),
                    selected_segments_count=len(selected_translate_segments),
                )
                self.log("⚠️ 체크된 번역 대상이 없습니다.")
                return

            provider = self.cb_trans_provider.currentData()
            if not self.check_translation_api_key_or_alert(provider):
                self._audit_translate_event("TRANSLATE_CORE_ABORT_API_CHECK", origin=str(translate_origin or ""), provider=str(provider or ""), targets=len(texts))
                return
            chunk_size = self.get_current_translation_chunk_size()
            self.log(
                f"🌐 번역 엔진: {self.cb_trans_provider.currentText()} / "
                f"대상 {len(texts)}개 / 묶음 {chunk_size}개"
            )
            if maker_mode:
                if control_code_auto_enabled:
                    self.log("🎮 쯔꾸르 AI 번역: 제어코드를 안전 토큰으로 분리하고 번역 의미에 맞춰 자동 반영합니다.")
                else:
                    self.log("🎮 쯔꾸르 AI 번역: 캐릭터/시스템 프롬프트, 제어문자 제거, 치환 코드 유지, 원문 줄내림 정규화를 적용합니다.")
            # The active translation locks project editing.  Reuse these lists
            # instead of cloning the full job several times; only per-chunk
            # slices are created when a result is actually applied.
            self._translation_target_rows = target_rows
            self._translation_target_texts = texts
            self._translation_maker_token_maps = maker_token_maps if maker_mode else []
            self._translation_maker_contexts = maker_contexts if maker_mode else None
            self._translation_control_code_auto_enabled = bool(control_code_auto_enabled)
            self._translation_target_segments = selected_translate_segments or []
            self._long_task_cancel_requested = False
            self._active_long_task_kind = "translation"
            translation_job_id = self._start_translation_job()
            self._audit_translate_event(
                "TRANSLATE_WORKER_START",
                origin=str(translate_origin or ""),
                job_id=str(translation_job_id or ""),
                provider=str(provider or ""),
                targets=len(texts),
                selected_rows_count=len(selected_translate_rows),
                full_map=not bool(selected_translate_rows or selected_translate_segments),
                chunk_size=int(chunk_size or 0),
            )
            if str(provider or "") == "gemini_deferred":
                self._audit_translate_event(
                    "TRANSLATE_GEMINI_DELAYED_DIALOG_START",
                    origin=str(translate_origin or ""),
                    job_id=str(translation_job_id or ""),
                    targets=len(texts),
                    chunk_size=int(chunk_size or 0),
                    delayed_mode=str(getattr(self.api_settings, "gemini_delayed_mode", "flex") or "flex"),
                )
                self._run_gemini_delayed_translation(
                    texts=texts,
                    contexts=(maker_contexts if maker_mode else None),
                    chunk_size=chunk_size,
                    job_id=translation_job_id,
                    translate_origin=translate_origin,
                )
                return

            self._chunked_translation_apply_state = {
                "affected_ids": set(),
                "pending_rows": set(),
                "db_pages": set(),
                "db_name_glossary_touched": False,
                "maker_mode": bool(maker_mode),
                "db_mode": bool(getattr(self, "_translation_database_mode", False)),
                "speaker_mode": bool(getattr(self, "_translation_speaker_mode", False)),
                "session_kind": "standard",
            }

            self.prepare_task_progress_overlay(
                "번역",
                f"번역 준비 중... 대상 {len(texts)}개 / 묶음 {chunk_size}개",
                total=len(texts),
                cancellable=True,
            )
            self.begin_busy_state("번역")
            self.translation_worker = TranslationWorker(
                self.engine,
                texts,
                provider=provider,
                chunk_size=chunk_size,
                contexts=(maker_contexts if maker_mode else None),
                apply_error_message=self.tr_ui("번역 청크 결과 적용에 실패했습니다."),
            )
            try:
                self.translation_worker._ysb_job_id = translation_job_id
            except Exception:
                pass
            self._active_task_worker = self.translation_worker
            self.translation_worker.progress.connect(self.on_translation_worker_progress)
            self.translation_worker.chunk_ready.connect(self.on_translation_worker_chunk_ready)
            self.translation_worker.finished.connect(self.on_translation_worker_finished)
            self.translation_worker.canceled.connect(self.on_translation_worker_canceled)
            self.translation_worker.error.connect(self.on_translation_worker_error)
            self.translation_worker.start()
            return

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._audit_translate_event("TRANSLATE_CORE_EXCEPTION", origin=str(translate_origin or ""), error=f"{type(e).__name__}: {e}")
            self.log(f"❌ 번역 중 에러 발생: {e}")
            msg_text = self.tr_ui("에러가 발생했습니다:")
            QMessageBox.critical(self, self.tr_ui("번역 오류"), f"{msg_text}\n{e}")
        finally:
            try:
                tw = getattr(self, "translation_worker", None)
                if tw is None or not tw.isRunning():
                    self.end_busy_state("번역")
            except Exception:
                self.end_busy_state("번역")


    def _run_gemini_delayed_translation(self, *, texts, contexts, chunk_size, job_id, translate_origin="direct"):
        settings = getattr(self, "api_settings", None) or ApiSettingsStore.load()
        mode = str(getattr(settings, "gemini_delayed_mode", "flex") or "flex").strip().lower()
        mode = "batch" if mode == "batch" else "flex"
        api_key = str(getattr(settings, "gemini_delayed_api_key", "") or "").strip()
        model = str(getattr(settings, "gemini_delayed_model", "gemini-2.5-flash-lite") or "gemini-2.5-flash-lite").strip()
        chunk_size = max(1, min(int(chunk_size or 50), 100))

        chunks = []
        for start in range(0, len(texts), chunk_size):
            end = min(len(texts), start + chunk_size)
            chunks.append({
                "start": start,
                "end": end,
            })

        self._chunked_translation_apply_state = {
            "affected_ids": set(),
            "pending_rows": set(),
            "db_pages": set(),
            "db_name_glossary_touched": False,
            "maker_mode": bool(getattr(self, "_translation_maker_token_maps", None)),
            "db_mode": bool(getattr(self, "_translation_database_mode", False)),
            "speaker_mode": bool(getattr(self, "_translation_speaker_mode", False)),
            "session_kind": "gemini_delayed",
        }
        self._gemini_delayed_translation_active = True
        self._active_long_task_kind = "gemini_delayed_translation"

        controller = GeminiDelayedTranslationController(
            self.engine,
            chunks,
            mode=mode,
            api_key=api_key,
            model=model,
            source_texts=texts,
            source_contexts=contexts,
            language=getattr(self, "ui_language", LANG_KO),
            parent=self,
        )
        self._gemini_delayed_controller = controller

        def apply_chunk(row_index, results):
            if not self._is_active_translation_job(job_id):
                return False
            if not (0 <= int(row_index) < len(controller.rows)):
                return False
            chunk = controller.rows[int(row_index)]
            start = int(chunk.get("start", 0) or 0)
            end = int(chunk.get("end", start) or start)
            # Slice only the active chunk.  Wrapping the full job in list(...)
            # here would duplicate every target on each completed chunk and can
            # explode memory on very large translation runs.
            rows = (getattr(self, "_translation_target_rows", []) or [])[start:end]
            source_texts = (getattr(self, "_translation_target_texts", []) or [])[start:end]
            segments = (getattr(self, "_translation_target_segments", []) or [])[start:end]
            token_maps = (getattr(self, "_translation_maker_token_maps", []) or [])[start:end]
            ok = self._apply_translation_results_to_current_page(
                results or [],
                target_rows_override=rows,
                texts_override=source_texts,
                target_segments_override=segments,
                token_maps_override=token_maps,
                partial_chunk=True,
            )
            if ok:
                try:
                    self.log(
                        self.tr_ui("✅ 지연 번역 청크 {chunk} 완료 및 즉시 반영").format(chunk=int(row_index) + 1)
                    )
                except Exception:
                    pass
            return bool(ok)

        dialog = GeminiDelayedTranslationDialog(
            controller,
            apply_chunk=apply_chunk,
            language=getattr(self, "ui_language", LANG_KO),
            parent=self,
        )
        self._gemini_delayed_dialog = dialog
        result = QDialog.DialogCode.Rejected
        try:
            result = dialog.exec()
        finally:
            if result != QDialog.DialogCode.Accepted:
                try:
                    canceled = getattr(self, "_canceled_translation_job_ids", None)
                    if not isinstance(canceled, set):
                        canceled = set()
                    canceled.add(job_id)
                    self._canceled_translation_job_ids = canceled
                except Exception:
                    pass
            try:
                self._finalize_chunked_translation_session()
            except Exception as exc:
                try:
                    self.log(self.tr_ui("⚠️ 지연 번역 마무리 처리 실패: {error}").format(error=exc))
                except Exception:
                    pass
            completed = sum(1 for row in controller.rows if row.get("status") == "completed")
            failed = sum(1 for row in controller.rows if row.get("status") == "failed")
            total = len(controller.rows)
            try:
                if result == QDialog.DialogCode.Accepted:
                    self.log(self.tr_ui("✅ Gemini 지연 번역 완료: 전체 {total}개 청크").format(total=total))
                else:
                    self.log(
                        self.tr_ui("⏹️ Gemini 지연 번역 취소: 완료 {completed}개 / 실패 {failed}개 / 전체 {total}개").format(
                            completed=completed,
                            failed=failed,
                            total=total,
                        )
                    )
            except Exception:
                pass
            self._audit_translate_event(
                "TRANSLATE_GEMINI_DELAYED_DIALOG_END",
                origin=str(translate_origin or ""),
                job_id=str(job_id or ""),
                accepted=bool(result == QDialog.DialogCode.Accepted),
                completed=int(completed),
                failed=int(failed),
                total=int(total),
                delayed_mode=mode,
            )
            self._gemini_delayed_translation_active = False
            self._gemini_delayed_controller = None
            self._gemini_delayed_dialog = None
            self._chunked_translation_apply_state = None
            self._active_translation_job_id = None
            self._active_long_task_kind = ""
            self._clear_translation_runtime_state()
            try:
                controller.deleteLater()
                dialog.deleteLater()
            except Exception:
                pass
            self.macro_mark_current_step_done("work_translate")

    def _finalize_chunked_translation_session(self):
        state = getattr(self, "_chunked_translation_apply_state", None)
        if not isinstance(state, dict):
            return False
        affected_ids = list(state.get("affected_ids") or [])
        if not affected_ids:
            return False
        maker_mode = bool(state.get("maker_mode"))
        db_mode = bool(state.get("db_mode"))
        speaker_mode = bool(state.get("speaker_mode"))
        pending_rows = sorted(int(x) for x in (state.get("pending_rows") or set()))
        db_pages = sorted(int(x) for x in (state.get("db_pages") or set()))
        session_kind = str(state.get("session_kind") or "standard")
        is_delayed = session_kind == "gemini_delayed"
        reason_prefix = "gemini_delayed" if is_delayed else "translation_stream"
        human_reason = "Gemini 지연 번역 결과 반영" if is_delayed else "번역 결과 반영"

        try:
            if maker_mode:
                if db_mode:
                    pages = db_pages or [int(getattr(self, "_translation_database_idx", getattr(self, "maker_database_idx", 0)) or 0)]
                    changed_unified = self.apply_unified_translation_memory(
                        scope="selected",
                        show_message=False,
                        auto=True,
                        page_indices=pages,
                        page_label="화자" if speaker_mode else "데이터베이스",
                    )
                else:
                    changed_unified = self.apply_unified_translation_memory(scope="all", show_message=False, auto=True)
                if changed_unified:
                    self.log(f"🧩 통일 번역 자동 적용: 동일 원문 {changed_unified}개 정리")
        except Exception:
            pass

        if maker_mode and db_mode:
            pages = db_pages or [int(getattr(self, "_translation_database_idx", getattr(self, "maker_database_idx", 0)) or 0)]
            if speaker_mode:
                try:
                    self.apply_maker_speaker_layer_to_dialogues(pages[0], reason=f"{reason_prefix}_speaker_translation_finished")
                except Exception:
                    pass
            else:
                try:
                    self.mark_maker_writeback_dirty(page_indices=pages, reason=f"{reason_prefix}_database_translation_finished")
                except Exception:
                    pass
                if bool(state.get("db_name_glossary_touched")):
                    try:
                        self.refresh_maker_database_auto_glossary_after_name_change(show_log=True, reason="gemini_delayed_db_translation_result")
                    except Exception:
                        pass
            try:
                self._finalize_maker_database_page_change(
                    pages[0],
                    changed_ids=affected_ids,
                    fields=["translated_text"],
                    reason=f"{reason_prefix}_speaker_translation_result" if speaker_mode else f"{reason_prefix}_db_translation_result",
                    refresh_preview=False,
                    writeback=False,
                    glossary_touched=False,
                    show_glossary_log=False,
                )
            except Exception:
                try:
                    store = getattr(self, "project_store", None)
                    if store is not None:
                        self.save_project_store(store, force_full=False)
                except Exception:
                    pass
            try:
                self.refresh_maker_database_view()
            except Exception:
                pass
        elif maker_mode:
            page_idx = int(getattr(self, "idx", 0) or 0)
            try:
                self.mark_maker_writeback_dirty(page_indices=[page_idx], reason=f"{reason_prefix}_translation_finished")
            except Exception:
                pass
            try:
                self._mark_maker_table_rows_pending_refresh(
                    pending_rows,
                    page_idx=page_idx,
                    db_mode=False,
                    reason=f"{reason_prefix}_translation_finished",
                )
            except Exception:
                pass
            try:
                self.finalize_maker_text_data_change(
                    affected_ids,
                    fields=["translated_text"],
                    page_idx=page_idx,
                    reason=human_reason,
                )
            except Exception:
                try:
                    if hasattr(self, "text_engine") and self.text_engine is not None:
                        self.text_engine.mark_dirty(page_idx, affected_ids, ["translated_text"])
                    self.mark_active_page_dirty("text")
                    self.schedule_deferred_auto_save_project(1200)
                except Exception:
                    pass
        else:
            # The inherited editor can also run outside Maker mode. Keep the
            # delayed provider safe there instead of touching Maker-only APIs.
            page_idx = int(getattr(self, "idx", 0) or 0)
            try:
                if hasattr(self, "text_engine") and self.text_engine is not None:
                    self.text_engine.mark_dirty(page_idx, affected_ids, ["translated_text"])
            except Exception:
                pass
            try:
                self.mark_active_page_dirty("text")
            except Exception:
                pass
            try:
                self.schedule_deferred_auto_save_project(1200)
            except Exception:
                pass
            try:
                self.ref_tab()
            except Exception:
                pass
        self.undo_break_boundary("translation")
        return True

    def on_translation_worker_progress(self, detail, current, total):
        sender = self.sender()
        job_id = getattr(sender, "_ysb_job_id", None)
        if not self._is_active_translation_job(job_id):
            return
        self.handle_long_task_message(str(detail), current=current, total=total)

    def _maker_prefer_split_positions(self, text, targets):
        """Choose stable split positions near target character offsets."""
        import re
        s = str(text or "")
        if not s:
            return []
        candidates = set()
        # After natural sentence/quote boundaries.
        for m in re.finditer(r"[」』\]\)）〉》〕】\"'.!?。！？…]+", s):
            pos = int(m.end())
            if 0 < pos < len(s):
                candidates.add(pos)
        # Before Korean quote-reporting tails such as "라고" when they follow a quote.
        for m in re.finditer(r"(?<=[」』\"'])\s*(?=라고|라며|라 쓰|라 적|라고 쓰|라고 적)", s):
            pos = int(m.start())
            if 0 < pos < len(s):
                candidates.add(pos)
        # Whitespace boundaries are safe in Latin/Korean mixed text.
        for m in re.finditer(r"\s+", s):
            pos = int(m.end())
            if 0 < pos < len(s):
                candidates.add(pos)
        out = []
        last = 0
        for target in targets:
            target = max(last + 1, min(len(s) - 1, int(target)))
            valid = [p for p in candidates if last < p < len(s) and p not in out]
            if valid:
                pos = min(valid, key=lambda p: (abs(p - target), p))
            else:
                pos = target
            if pos <= last:
                pos = min(len(s) - 1, last + 1)
            out.append(pos)
            last = pos
        return out

    def _maker_force_translation_line_count(self, translated_text, raw_text):
        """Keep translated Maker text visually line-compatible with the source.

        The prompt asks the model to keep the same line count, but local models can
        still merge lines into a single natural Korean sentence.  RPG Maker lines
        are restoration/display units, so when the count differs we do a minimal
        deterministic split/join instead of leaving the row visually mismatched.
        """
        try:
            translated = str(translated_text or "").replace("\r\n", "\n").replace("\r", "\n")
            raw = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
            info = analyze_maker_control_codes(raw)
            plain = str(info.get("plain_text") or strip_maker_control_codes(raw) or raw).replace("\r\n", "\n").replace("\r", "\n")
            src_lines = plain.split("\n")
            if len(src_lines) <= 1:
                return translated
            dst_lines = translated.split("\n")
            if len(dst_lines) == len(src_lines):
                return translated
            # Too many lines: preserve early lines and merge the surplus into the
            # last visual source line.  This keeps the required line count.
            if len(dst_lines) > len(src_lines):
                head = dst_lines[:len(src_lines) - 1]
                tail = " ".join(x.strip() for x in dst_lines[len(src_lines) - 1:] if str(x).strip())
                return "\n".join(head + [tail])
            # Too few lines, especially one merged sentence: split near source
            # proportions but prefer punctuation/quote boundaries.
            compact = " ".join(x.strip() for x in dst_lines if str(x).strip())
            if not compact:
                return translated
            weights = [max(1, len(x.strip())) for x in src_lines]
            total = float(sum(weights) or len(src_lines))
            targets = []
            acc = 0.0
            for w in weights[:-1]:
                acc += float(w)
                targets.append(round(len(compact) * acc / total))
            splits = self._maker_prefer_split_positions(compact, targets)
            if not splits:
                return translated
            out = []
            start = 0
            for pos in splits:
                out.append(compact[start:pos].strip())
                start = pos
            out.append(compact[start:].strip())
            # Pad defensively if pathological input produced too few segments.
            while len(out) < len(src_lines):
                out.append("")
            return "\n".join(out[:len(src_lines)])
        except Exception:
            return str(translated_text or "")

    def _apply_translation_results_to_current_page(
        self,
        res,
        *,
        target_rows_override=None,
        texts_override=None,
        target_segments_override=None,
        token_maps_override=None,
        partial_chunk=False,
    ):
        db_mode = bool(getattr(self, "_translation_database_mode", False))
        speaker_mode = bool(getattr(self, "_translation_speaker_mode", False))
        if db_mode:
            try:
                db_idx = int(getattr(self, "_translation_database_idx", getattr(self, "maker_database_idx", 0)) or 0)
            except Exception:
                db_idx = 0
            curr = self.data.get(db_idx) if isinstance(getattr(self, "data", None), dict) else None
        else:
            curr = self.data.get(self.idx)
        if not curr or not curr.get('data'):
            return False
        target_rows = list(target_rows_override if target_rows_override is not None else (getattr(self, "_translation_target_rows", []) or []))
        texts = list(texts_override if texts_override is not None else (getattr(self, "_translation_target_texts", []) or []))
        target_segments = list(target_segments_override if target_segments_override is not None else (getattr(self, "_translation_target_segments", []) or []))
        if len(res) != len(target_rows):
            QMessageBox.warning(
                self,
                self.tr_ui("번역 개수 불일치"),
                self.tr_msg(f"요청 {len(target_rows)}개 / 응답 {len(res)}개\n\n밀림 방지를 위해 결과 반영을 중단했습니다."),
            )
            return False

        affected_ids = []
        db_name_glossary_touched = False
        db_touched_page_indices = set()
        control_code_auto_restore_skipped = 0
        control_code_auto_stats = {
            "applied": 0,
            "applied_raw": 0,
            "fallback_edge": 0,
            "failed_plain": 0,
        }
        # 번역 결과 반영은 분석/인페인팅과 같은 확정 작업 경계다.
        # 이전 편집 상태로 Ctrl+Z 되는 것을 막기 위해 별도 Undo 기록을 만들지 않는다.
        maker_mode = True if db_mode else self._is_maker_text_table_mode()
        # DB mode uses the same Maker table shape as map/event pages:
        # ID / status / speaker / type / event / source / translation / memo.
        # A previous hardcoded DB column wrote translation results into the source
        # column, and the later DB UI commit could overwrite self.data with the old
        # translation column value.  Always ask the table layout helper instead.
        trans_col = self._table_translation_column()
        pending_translation_rows = []
        self.tab.blockSignals(True)
        try:
            token_maps = list(token_maps_override if token_maps_override is not None else (getattr(self, "_translation_maker_token_maps", []) or []))
            for result_index, (row, t) in enumerate(zip(target_rows, res)):
                seg = target_segments[result_index] if result_index < len(target_segments) else None
                if isinstance(seg, dict):
                    try:
                        row = int(seg.get("row", row))
                        data_index = int(seg.get("data_index", row - 1))
                    except Exception:
                        data_index = self._maker_data_index_for_table_row(row, db_mode=db_mode)
                else:
                    data_index = self._maker_data_index_for_table_row(row, db_mode=db_mode)
                if data_index < 0 or data_index >= len(curr['data']):
                    continue
                safe_text = str(t) if t is not None else ""
                if maker_mode:
                    token_map = token_maps[result_index] if result_index < len(token_maps) else []
                    raw_for_restore = str(seg.get("source_text") or "") if isinstance(seg, dict) else str(curr['data'][data_index].get('text', ''))
                    has_auto_spec = bool(token_map)
                    if has_auto_spec:
                        safe_text, control_status, _control_detail = restore_maker_translation_text_checked(
                            safe_text,
                            token_map,
                            raw_for_restore,
                        )
                        if control_status in control_code_auto_stats:
                            control_code_auto_stats[control_status] += 1
                        curr['data'][data_index]['maker_control_code_auto_status'] = control_status
                        if control_status == "failed_plain":
                            # 토큰이 누락되거나 순서가 바뀌면 잘못된 코드를 억지로
                            # 붙이지 않는다. 순수 번역문의 물리 줄 수만 안전하게 맞춘다.
                            try:
                                safe_text = self._maker_force_translation_line_count(safe_text, raw_for_restore)
                            except Exception:
                                pass
                    else:
                        safe_text = restore_maker_translation_text(safe_text, token_map)
                        curr['data'][data_index].pop('maker_control_code_auto_status', None)
                        try:
                            safe_text = self._maker_force_translation_line_count(safe_text, raw_for_restore)
                        except Exception:
                            pass
                        # 자동 반영 OFF에서는 기존처럼 순수 번역문을 유지하고
                        # [현재 맵 복원] / [일괄 맵 복원]을 수동 후처리로 사용한다.
                        try:
                            info_for_restore = analyze_maker_control_codes(raw_for_restore)
                            if isinstance(info_for_restore, dict) and info_for_restore.get("has_control_codes"):
                                control_code_auto_restore_skipped += 1
                        except Exception:
                            pass
                    if db_mode and not speaker_mode:
                        safe_text = normalize_maker_database_translation_result(safe_text, raw_for_restore)
                old_translated_text = str(curr['data'][data_index].get('translated_text') or '')
                if isinstance(seg, dict):
                    try:
                        base_text = old_translated_text if old_translated_text else str(curr['data'][data_index].get('text') or '')
                        safe_text = self._replace_lines_in_text(base_text, seg.get("line_start", 0), seg.get("line_end", 0), safe_text)
                    except Exception:
                        pass
                curr['data'][data_index]['translated_text'] = safe_text
                if safe_text.strip():
                    curr['data'][data_index]['maker_translation_origin'] = "api_translation"
                else:
                    curr['data'][data_index].pop('maker_translation_origin', None)
                if db_mode:
                    try:
                        db_touched_page_indices.add(int(getattr(self, "_translation_database_idx", getattr(self, "maker_database_idx", 0)) or 0))
                    except Exception:
                        pass
                    try:
                        if safe_text != old_translated_text and self._is_maker_database_name_row(curr['data'][data_index]):
                            db_name_glossary_touched = True
                    except Exception:
                        pass
                if maker_mode:
                    curr['data'][data_index]['maker_status'] = self.tr_ui("번역완료") if safe_text.strip() else self.tr_ui("미번역")
                affected_ids.append(curr['data'][data_index].get('id'))
                pending_translation_rows.append(int(row))
                if db_mode:
                    table_item = QTableWidgetItem(safe_text)
                    table_item.setData(Qt.ItemDataRole.UserRole, safe_text)
                    self.tab.setItem(row, trans_col, table_item)
                    status_item = QTableWidgetItem(curr['data'][data_index].get('maker_status', ''))
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    status_item.setData(Qt.ItemDataRole.UserRole, status_item.text())
                    self.tab.setItem(row, 1, status_item)
            if db_mode:
                self.paint_all_row_header()
            if control_code_auto_restore_skipped:
                self._audit_translate_event(
                    "TRANSLATE_CONTROL_CODE_AUTO_RESTORE_SKIPPED",
                    count=int(control_code_auto_restore_skipped),
                    reason="manual_restore_button_required",
                )
            if any(control_code_auto_stats.values()):
                self._audit_translate_event(
                    "TRANSLATE_CONTROL_CODE_AUTO_APPLY",
                    **{key: int(value) for key, value in control_code_auto_stats.items()},
                )
                if control_code_auto_stats["failed_plain"]:
                    self.log(
                        self.tr_ui(
                            "⚠️ 제어코드 자동 반영에 실패한 {count}개 대사는 안전을 위해 순수 번역문으로 유지했습니다."
                        ).format(count=int(control_code_auto_stats["failed_plain"]))
                    )
                if control_code_auto_stats["fallback_edge"]:
                    self.log(
                        self.tr_ui(
                            "ℹ️ AI 토큰 검증에 실패한 {count}개 대사는 안전한 앞/뒤 제어코드만 자동 복원했습니다."
                        ).format(count=int(control_code_auto_stats["fallback_edge"]))
                    )
        finally:
            self.tab.blockSignals(False)

        if partial_chunk:
            try:
                state = getattr(self, "_chunked_translation_apply_state", None)
                if not isinstance(state, dict):
                    state = {
                        "affected_ids": set(),
                        "pending_rows": set(),
                        "db_pages": set(),
                        "db_name_glossary_touched": False,
                        "maker_mode": bool(maker_mode),
                        "db_mode": bool(db_mode),
                        "speaker_mode": bool(speaker_mode),
                    }
                    self._chunked_translation_apply_state = state
                state.setdefault("affected_ids", set()).update(x for x in affected_ids if x is not None)
                state.setdefault("pending_rows", set()).update(int(x) for x in pending_translation_rows)
                state.setdefault("db_pages", set()).update(int(x) for x in db_touched_page_indices)
                state["db_name_glossary_touched"] = bool(state.get("db_name_glossary_touched")) or bool(db_name_glossary_touched)
                state["maker_mode"] = bool(maker_mode)
                state["db_mode"] = bool(db_mode)
                state["speaker_mode"] = bool(speaker_mode)
                state.setdefault("session_kind", "standard")
            except Exception:
                pass

            try:
                self.has_unsaved_changes = True
                self.update_window_title()
            except Exception:
                pass
            try:
                session_kind = str((getattr(self, "_chunked_translation_apply_state", None) or {}).get("session_kind") or "standard")
                reason_prefix = "gemini_delayed" if session_kind == "gemini_delayed" else "translation_stream"
                if maker_mode and not db_mode:
                    page_idx = int(getattr(self, "idx", 0) or 0)
                    self.mark_maker_writeback_dirty(page_indices=[page_idx], reason=f"{reason_prefix}_chunk_applied")
                    self._mark_maker_table_rows_pending_refresh(
                        pending_translation_rows,
                        page_idx=page_idx,
                        db_mode=False,
                        reason=f"{reason_prefix}_chunk_applied",
                    )
                elif db_mode:
                    pages = sorted(int(x) for x in db_touched_page_indices) if db_touched_page_indices else [int(getattr(self, "_translation_database_idx", getattr(self, "maker_database_idx", 0)) or 0)]
                    if speaker_mode:
                        self.apply_maker_speaker_layer_to_dialogues(pages[0], reason=f"{reason_prefix}_speaker_chunk_applied")
                    else:
                        self.mark_maker_writeback_dirty(page_indices=pages, reason=f"{reason_prefix}_database_chunk_applied")
                    for row in pending_translation_rows:
                        self.tab.resizeRowToContents(int(row))
            except Exception:
                pass
            try:
                page_idx = int(getattr(self, "_translation_database_idx", getattr(self, "idx", 0)) or 0) if db_mode else int(getattr(self, "idx", 0) or 0)
                if hasattr(self, "text_engine") and self.text_engine is not None:
                    self.text_engine.mark_dirty(page_idx, affected_ids, ["translated_text"])
                self.mark_active_page_dirty("text")
                self.schedule_deferred_auto_save_project(1200)
            except Exception:
                pass
            return True

        try:
            if maker_mode:
                if db_mode:
                    try:
                        auto_unify_pages = sorted(int(x) for x in (db_touched_page_indices or {int(getattr(self, "_translation_database_idx", getattr(self, "maker_database_idx", 0)) or 0)}))
                    except Exception:
                        auto_unify_pages = [int(getattr(self, "_translation_database_idx", getattr(self, "maker_database_idx", 0)) or 0)]
                    changed_unified = self.apply_unified_translation_memory(
                        scope="selected",
                        show_message=False,
                        auto=True,
                        page_indices=auto_unify_pages,
                        page_label="화자" if speaker_mode else "데이터베이스",
                    )
                else:
                    changed_unified = self.apply_unified_translation_memory(scope="all", show_message=False, auto=True)
                if changed_unified:
                    self.log(f"🧩 통일 번역 자동 적용: 동일 원문 {changed_unified}개 정리")
        except Exception:
            pass

        try:
            if maker_mode and not db_mode:
                self.mark_maker_writeback_dirty(page_indices=[int(getattr(self, "idx", 0) or 0)], reason="translation_finished")
        except Exception:
            pass

        # 맵 번역 결과는 데이터만 반영한다. 표 셀과 자동 행 높이는
        # 각 행을 단일 클릭했을 때 한 행씩 최신화한다.
        if maker_mode and not db_mode:
            try:
                self._mark_maker_table_rows_pending_refresh(
                    pending_translation_rows,
                    page_idx=int(getattr(self, "idx", 0) or 0),
                    db_mode=False,
                    reason="translation_finished",
                )
            except Exception:
                pass
        elif db_mode:
            try:
                for row in pending_translation_rows:
                    self.tab.resizeRowToContents(int(row))
            except Exception:
                pass
        try:
            if db_mode:
                try:
                    self.has_unsaved_changes = True
                except Exception:
                    pass
                pages = sorted(int(x) for x in db_touched_page_indices) if db_touched_page_indices else [int(getattr(self, "_translation_database_idx", getattr(self, "maker_database_idx", 0)) or 0)]
                if speaker_mode:
                    try:
                        self.apply_maker_speaker_layer_to_dialogues(pages[0], reason="speaker translation finished")
                    except Exception:
                        pass
                else:
                    try:
                        self.mark_maker_writeback_dirty(page_indices=pages, reason="database_translation_finished")
                    except Exception as e:
                        try:
                            self.log(f"⚠️ DB 번역 결과 JSON 반영 대기 처리 실패: {e}")
                        except Exception:
                            pass
                if db_name_glossary_touched and not speaker_mode:
                    try:
                        self.refresh_maker_database_auto_glossary_after_name_change(show_log=True, reason="db_translation_result")
                    except Exception:
                        pass
                try:
                    self._finalize_maker_database_page_change(
                        pages[0] if pages else getattr(self, "_translation_database_idx", getattr(self, "maker_database_idx", 0)),
                        changed_ids=affected_ids,
                        fields=["translated_text"],
                        reason="speaker_translation_result" if speaker_mode else "db_translation_result",
                        refresh_preview=False,
                        writeback=False,
                        glossary_touched=False,
                        show_glossary_log=False,
                    )
                except Exception:
                    try:
                        store = getattr(self, "project_store", None)
                        if store is not None:
                            self.save_project_store(store, force_full=False)
                    except Exception:
                        pass
                try:
                    self.refresh_maker_database_view()
                except Exception:
                    pass
                return True
            self.finalize_maker_text_data_change(affected_ids, fields=['translated_text'], page_idx=int(getattr(self, 'idx', 0) or 0), reason='번역 결과 반영')
        except Exception:
            try:
                if hasattr(self, 'text_engine') and self.text_engine is not None:
                    self.text_engine.mark_dirty(int(getattr(self, 'idx', 0) or 0), affected_ids, ['translated_text'])
                self.mark_active_page_dirty('text')
                self.schedule_deferred_auto_save_project(1800)
            except Exception:
                pass
        self.undo_break_boundary("translation")
        return True

    def on_translation_worker_chunk_ready(self, start, res):
        """Apply exactly one normal-translation chunk, then release the worker."""
        sender = self.sender()
        job_id = getattr(sender, "_ysb_job_id", None)
        if not self._is_active_translation_job(job_id):
            try:
                sender.mark_chunk_applied(start, False, self.tr_ui("취소된 번역 작업입니다."))
            except Exception:
                pass
            return

        ok = False
        error = ""
        try:
            start = max(0, int(start or 0))
            results = res if isinstance(res, list) else list(res or [])
            end = start + len(results)
            target_rows = (getattr(self, "_translation_target_rows", []) or [])[start:end]
            source_texts = (getattr(self, "_translation_target_texts", []) or [])[start:end]
            target_segments = (getattr(self, "_translation_target_segments", []) or [])[start:end]
            token_maps = (getattr(self, "_translation_maker_token_maps", []) or [])[start:end]
            ok = bool(
                self._apply_translation_results_to_current_page(
                    results,
                    target_rows_override=target_rows,
                    texts_override=source_texts,
                    target_segments_override=target_segments,
                    token_maps_override=token_maps,
                    partial_chunk=True,
                )
            )
            if not ok:
                error = self.tr_ui("번역 청크 결과를 프로젝트에 적용하지 못했습니다.")
        except Exception as exc:
            error = str(exc)
            ok = False
        finally:
            try:
                sender.mark_chunk_applied(start, ok, error)
            except Exception:
                pass

    def on_translation_worker_finished(self, res):
        sender = self.sender()
        job_id = getattr(sender, "_ysb_job_id", None)
        if not self._is_active_translation_job(job_id):
            try:
                self.log("🗑️ 취소된 번역 응답 폐기: 결과를 반영하지 않았습니다.")
            except Exception:
                pass
            if sender is getattr(self, "translation_worker", None):
                self._active_task_worker = None
                self.translation_worker = None
            return
        try:
            if isinstance(res, dict) and res.get("streamed"):
                self._finalize_chunked_translation_session()
                self.log(
                    self.tr_ui("✅ 번역 완료: {applied}개 항목을 청크 순서대로 반영했습니다.").format(
                        applied=int(res.get("applied", 0) or 0)
                    )
                )
            elif self._apply_translation_results_to_current_page(list(res or [])):
                # Backward-compatible fallback for an older worker object.
                self.log("✅ 번역 완료")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log(f"❌ 번역 결과 반영 중 오류: {e}")
            QMessageBox.critical(self, self.tr_ui("번역 오류"), f"{self.tr_ui('에러가 발생했습니다:')}\n{e}")
        finally:
            self._active_task_worker = None
            self.translation_worker = None
            self._clear_translation_runtime_state()
            self._active_translation_job_id = None
            self._active_long_task_kind = ""
            self.end_busy_state("번역")
            self.macro_mark_current_step_done("work_translate")

    def on_translation_worker_canceled(self, partial):
        sender = self.sender()
        job_id = getattr(sender, "_ysb_job_id", None)
        if not self._is_active_translation_job(job_id):
            if sender is getattr(self, "translation_worker", None):
                self._active_task_worker = None
                self.translation_worker = None
            return
        try:
            self._finalize_chunked_translation_session()
            applied = int((partial or {}).get("applied", 0) or 0) if isinstance(partial, dict) else 0
            self.log(
                self.tr_ui("⏹️ 번역 취소됨: 이미 반영된 {applied}개 결과는 유지하고 이후 청크는 중단했습니다.").format(
                    applied=applied
                )
            )
        finally:
            self._active_task_worker = None
            self.translation_worker = None
            self._clear_translation_runtime_state()
            self._active_translation_job_id = None
            self._active_long_task_kind = ""
            self.end_busy_state("번역")

    def on_translation_worker_error(self, message):
        sender = self.sender()
        job_id = getattr(sender, "_ysb_job_id", None)
        if not self._is_active_translation_job(job_id):
            try:
                self.log("🗑️ 취소된 번역 오류 응답 폐기")
            except Exception:
                pass
            if sender is getattr(self, "translation_worker", None):
                self._active_task_worker = None
                self.translation_worker = None
            return
        try:
            msg = f"❌ 번역 중 에러 발생: {message}"
            self.handle_long_task_message(msg)
            self._finalize_chunked_translation_session()
        finally:
            self._active_task_worker = None
            self.translation_worker = None
            self._clear_translation_runtime_state()
            self._active_translation_job_id = None
            self._active_long_task_kind = ""
            self.end_busy_state("번역")

    def clip_mask_to_checked_text_boxes(self, mask, data):
        """
        페인팅 마스크 토글 ON 전용:
        분석 기반 페인팅 마스크는 체크된 텍스트 박스 영역 안에서만 지우도록 제한한다.
        사용자가 ON 상태에서 박스 밖을 칠해도 실제 인페인팅 마스크에는 들어가지 않는다.
        """
        if mask is None:
            return None

        if mask.ndim == 3:
            gray = cv2.cvtColor(mask, cv2.COLOR_RGB2GRAY)
        else:
            gray = mask.copy()

        h, w = gray.shape[:2]
        allowed = np.zeros((h, w), dtype=np.uint8)

        for item in data or []:
            if not item.get('use_inpaint', True):
                continue
            rect = item.get('rect')
            if not rect or len(rect) < 4:
                continue
            try:
                rx, ry, rw, rh = [int(v) for v in rect[:4]]
            except Exception:
                continue

            x1 = max(0, rx)
            y1 = max(0, ry)
            x2 = min(w, rx + max(0, rw))
            y2 = min(h, ry + max(0, rh))
            if x2 > x1 and y2 > y1:
                allowed[y1:y2, x1:x2] = 255

        return cv2.bitwise_and(gray, allowed)

    def build_inpainting_payload_for_current_toggle(self, curr):
        """
        인페인팅 입력 분기:
        - 토글 ON: 분석 기반 페인팅 마스크를 체크된 텍스트 박스 안으로 제한한다.
        - 토글 OFF: 텍스트 박스/체크 상태를 무시하고 OFF 페인팅 마스크를 그대로 사용한다.
        """
        data = curr.get('data', [])
        if self.mask_toggle_enabled:
            mask = curr.get('mask_inpaint')
            if mask is not None:
                mask = self.clip_mask_to_checked_text_boxes(mask, data)
            return data, mask

        # OFF 상태는 분석 없이 직접 칠한 마스크로만 인페인팅한다.
        # engine.execute_inpainting()이 data의 체크박스 영역을 추가로 건드리지 않도록 data를 비워 넘긴다.
        return [], curr.get('mask_inpaint_off')

    def _get_inpaint_resize_limits(self, provider=None):
        provider = str(provider or "replicate_lama").strip().lower()
        if provider == "local_lama":
            return {
                "provider": provider,
                "provider_label": "LOCAL LaMa",
                "warn_max_side": 3000,
                "warn_max_pixels": 9_000_000,
                "target_max_side": 2800,
                "target_max_pixels": 7_500_000,
            }
        if provider == "replicate_lama":
            return {
                "provider": provider,
                "provider_label": "Replicate LaMa",
                "warn_max_side": 2800,
                "warn_max_pixels": 6_000_000,
                "target_max_side": 2200,
                "target_max_pixels": 4_000_000,
            }
        return None

    def _get_current_inpaint_provider(self):
        try:
            from ysb.engine.manga_engine import Config
            return str(getattr(Config, "INPAINT_PROVIDER", "replicate_lama") or "replicate_lama").strip().lower()
        except Exception:
            return "replicate_lama"

    def _inspect_inpaint_resize_plan(self, input_path, provider=None):
        limits = self._get_inpaint_resize_limits(provider or self._get_current_inpaint_provider())
        if not limits or not input_path or not os.path.exists(str(input_path)):
            return None
        try:
            img = cv2.imdecode(np.fromfile(str(input_path), np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return None
            h, w = img.shape[:2]
        except Exception:
            return None

        max_side = max(int(w or 0), int(h or 0))
        total_pixels = int(max(0, w) * max(0, h))
        warn_max_side = int(limits.get("warn_max_side", 0) or 0)
        warn_max_pixels = int(limits.get("warn_max_pixels", 0) or 0)
        if (warn_max_side <= 0 or max_side <= warn_max_side) and (warn_max_pixels <= 0 or total_pixels <= warn_max_pixels):
            return None

        scale = 1.0
        target_max_side = int(limits.get("target_max_side", warn_max_side) or warn_max_side or 0)
        target_max_pixels = int(limits.get("target_max_pixels", warn_max_pixels) or warn_max_pixels or 0)
        if target_max_side > 0 and max_side > target_max_side:
            scale = min(scale, float(target_max_side) / float(max_side))
        if target_max_pixels > 0 and total_pixels > target_max_pixels:
            scale = min(scale, float(target_max_pixels / float(total_pixels)) ** 0.5)
        if scale >= 0.9999:
            return None

        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        return {
            "provider": limits.get("provider", provider),
            "provider_label": limits.get("provider_label", provider or "LaMa"),
            "source_path": str(input_path),
            "orig_width": int(w),
            "orig_height": int(h),
            "orig_megapixels": float(total_pixels) / 1_000_000.0,
            "target_width": int(new_w),
            "target_height": int(new_h),
            "target_megapixels": float(new_w * new_h) / 1_000_000.0,
            "warn_max_side": warn_max_side,
            "warn_max_pixels": warn_max_pixels,
            "target_max_side": target_max_side,
            "target_max_pixels": target_max_pixels,
        }

    def _write_resized_inpaint_request(self, page_idx, input_path, inpaint_mask, plan):
        if not isinstance(plan, dict):
            return input_path, inpaint_mask
        try:
            src_img = cv2.imdecode(np.fromfile(str(input_path), np.uint8), cv2.IMREAD_COLOR)
            if src_img is None:
                return input_path, inpaint_mask
            tw = int(plan.get("target_width", 0) or 0)
            th = int(plan.get("target_height", 0) or 0)
            if tw <= 0 or th <= 0:
                return input_path, inpaint_mask
            interp = cv2.INTER_AREA if tw < src_img.shape[1] or th < src_img.shape[0] else cv2.INTER_CUBIC
            resized = cv2.resize(src_img, (tw, th), interpolation=interp)
            base_dir = getattr(self, "project_dir", None) or os.path.dirname(str(input_path)) or os.getcwd()
            out_dir = os.path.join(base_dir, "_inpaint_resize_cache")
            os.makedirs(out_dir, exist_ok=True)
            provider = str(plan.get("provider") or "").strip().lower()
            # Replicate 업로드는 픽셀 수뿐 아니라 입력 파일 용량도 실패 요인이 될 수 있다.
            # 축소본을 PNG로 저장하면 원본 JPG보다 더 커질 수 있어 Replicate LaMa에는 JPG 임시 입력을 쓴다.
            ext = ".jpg" if provider == "replicate_lama" else ".png"
            out_path = os.path.join(out_dir, f"page_{int(page_idx)+1:04d}_{tw}x{th}{ext}")
            if ext == ".jpg":
                ok, buf = cv2.imencode(ext, resized, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            else:
                ok, buf = cv2.imencode(ext, resized, [int(cv2.IMWRITE_PNG_COMPRESSION), 6])
            if not ok:
                return input_path, inpaint_mask
            buf.tofile(out_path)
            resized_mask = inpaint_mask
            if inpaint_mask is not None:
                try:
                    resized_mask = cv2.resize(inpaint_mask, (tw, th), interpolation=cv2.INTER_NEAREST)
                except Exception:
                    resized_mask = inpaint_mask
            try:
                self.log(f"↘️ 인페인팅 입력 축소: {plan.get('orig_width')}x{plan.get('orig_height')} → {tw}x{th}")
            except Exception:
                pass
            return out_path, resized_mask
        except Exception:
            return input_path, inpaint_mask

    def _ask_single_inpaint_resize(self, page_idx, plan):
        if not isinstance(plan, dict):
            return "keep"
        title = self.tr_ui("인페인팅 해상도 확인")
        provider_label = str(plan.get("provider_label") or "LaMa")
        current_size = f"{int(plan.get('orig_width', 0))} x {int(plan.get('orig_height', 0))} ({float(plan.get('orig_megapixels', 0.0)):.1f}MP)"
        target_size = f"{int(plan.get('target_width', 0))} x {int(plan.get('target_height', 0))} ({float(plan.get('target_megapixels', 0.0)):.1f}MP)"
        warn_text = f"장변 {int(plan.get('warn_max_side', 0)):,}px / {float(int(plan.get('warn_max_pixels', 0))/1_000_000.0):.1f}MP"
        body = self.tr_ui("현재 이미지가 LaMa 권장 해상도를 넘을 수 있습니다.")
        detail = (
            f"{self.tr_ui('페이지')}: {int(page_idx) + 1}\n"
            f"{self.tr_ui('현재 이미지')}: {current_size}\n"
            f"{self.tr_ui('권장 기준')}: {provider_label} · {warn_text}\n"
            f"{self.tr_ui('인페인팅용 축소 예상')}: {target_size}"
        )
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(body)
        msg.setInformativeText(detail)
        resize_btn = msg.addButton(self.tr_ui("리사이즈 후 진행"), QMessageBox.ButtonRole.AcceptRole)
        keep_btn = msg.addButton(self.tr_ui("그대로 진행"), QMessageBox.ButtonRole.ActionRole)
        cancel_btn = msg.addButton(self.tr_ui("취소"), QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(resize_btn)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == resize_btn:
            return "resize"
        if clicked == keep_btn:
            return "keep"
        return "cancel"

    def _prepare_single_inpaint_request_with_resize_prompt(self, page_idx, input_path, inpaint_mask):
        plan = self._inspect_inpaint_resize_plan(input_path, self._get_current_inpaint_provider())
        if not plan:
            return input_path, inpaint_mask, True
        decision = self._ask_single_inpaint_resize(page_idx, plan)
        if decision == "cancel":
            self.log("↩️ 인페인팅 리사이즈 취소")
            return input_path, inpaint_mask, False
        if decision != "resize":
            self.log("ℹ️ 인페인팅은 원본 해상도로 그대로 진행합니다.")
            return input_path, inpaint_mask, True
        new_path, new_mask = self._write_resized_inpaint_request(page_idx, input_path, inpaint_mask, plan)
        return new_path, new_mask, True

    def _ask_batch_inpaint_resize(self, selected_page_indices):
        provider = self._get_current_inpaint_provider()
        limits = self._get_inpaint_resize_limits(provider)
        self._batch_inpaint_resize_policy = None
        if not limits:
            return True

        overs = []
        for page_idx in list(selected_page_indices or []):
            try:
                input_path = self.get_inpainting_input_path(int(page_idx))
            except Exception:
                input_path = None
            plan = self._inspect_inpaint_resize_plan(input_path, provider)
            if plan:
                plan["page_idx"] = int(page_idx)
                overs.append(plan)

        if not overs:
            return True

        preview_lines = []
        for plan in overs[:6]:
            preview_lines.append(
                f"- {int(plan.get('page_idx', 0)) + 1}{self.tr_ui('페이지')}: "
                f"{int(plan.get('orig_width', 0))}x{int(plan.get('orig_height', 0))} → "
                f"{int(plan.get('target_width', 0))}x{int(plan.get('target_height', 0))}"
            )
        if len(overs) > 6:
            preview_lines.append(self.tr_ui("외 추가 페이지가 있습니다.").format(count=len(overs) - 6))

        provider_label = str(limits.get("provider_label") or "LaMa")
        warn_text = f"장변 {int(limits.get('warn_max_side', 0)):,}px / {float(int(limits.get('warn_max_pixels', 0))/1_000_000.0):.1f}MP"
        detail = (
            f"{self.tr_ui('기준 초과 페이지')}: {len(overs)}\n"
            f"{self.tr_ui('권장 기준')}: {provider_label} · {warn_text}\n\n"
            + "\n".join(preview_lines)
        )

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(self.tr_ui("일괄 인페인팅 해상도 확인"))
        msg.setText(self.tr_ui("선택한 맵 중 일부가 LaMa 권장 해상도를 넘습니다."))
        msg.setInformativeText(detail)
        cb = QCheckBox(self.tr_ui("선택한 전체 맵에 같은 기준으로 적용"), msg)
        cb.setChecked(True)
        msg.setCheckBox(cb)
        resize_btn = msg.addButton(self.tr_ui("리사이즈 후 진행"), QMessageBox.ButtonRole.AcceptRole)
        keep_btn = msg.addButton(self.tr_ui("그대로 진행"), QMessageBox.ButtonRole.ActionRole)
        cancel_btn = msg.addButton(self.tr_ui("취소"), QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(resize_btn)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == cancel_btn:
            self.log("↩️ 인페인팅 리사이즈 취소")
            return False
        if clicked == keep_btn:
            self.log("ℹ️ 일괄 인페인팅은 원본 해상도로 그대로 진행합니다.")
            return True

        if cb.isChecked():
            apply_indices = [int(i) for i in selected_page_indices or []]
        else:
            apply_indices = [int(plan.get("page_idx", -1)) for plan in overs]
        self._batch_inpaint_resize_policy = {
            "enabled": True,
            "provider": provider,
            "target_max_side": int(limits.get("target_max_side", 0) or 0),
            "target_max_pixels": int(limits.get("target_max_pixels", 0) or 0),
            "warn_max_side": int(limits.get("warn_max_side", 0) or 0),
            "warn_max_pixels": int(limits.get("warn_max_pixels", 0) or 0),
            "page_indices": [int(i) for i in apply_indices if int(i) >= 0],
        }
        self.log(f"↘️ 일괄 인페인팅 리사이즈 적용 예정: {len(overs)}페이지 감지")
        return True

    def run_inpainting(self):
        if bool(getattr(self, "tktool_phase2_enabled", False)):
            try:
                self.log("⛔ 쯔꾸르붕이에서는 인페인팅을 사용하지 않습니다.")
            except Exception:
                pass
            return
        if not self.ensure_engine_ready():
            return
        if not self.paths:
            self.log("⚠️ 이미지가 없습니다. 먼저 프로젝트에 이미지를 불러와 주세요.")
            return
        if not self.check_inpaint_api_or_alert():
            return

        page_idx = int(getattr(self, "idx", 0) or 0)
        curr = self.data.get(page_idx)
        if not curr:
            return

        # 인페인팅은 현재 작업 페이지를 고정해서 시작한다.
        # 작업 중 사용자가 다른 페이지로 이동해도 완료 결과는 page_idx에만 반영한다.
        self.commit_current_page_ui_to_data()
        try:
            self.ensure_page_masks_loaded(page_idx, keys=("mask_inpaint", "mask_inpaint_off"))
            self.touch_page_mask_cache(page_idx)
            self.trim_page_mask_cache(keep_indices=[page_idx])
        except Exception:
            pass

        input_path = self.get_inpainting_input_path(page_idx)
        if not input_path or not os.path.exists(input_path):
            self.log("⚠️ 인페인팅 입력 이미지 파일을 만들지 못했습니다.")
            return

        mask_toggle_enabled = bool(getattr(self, "mask_toggle_enabled", False))
        data = curr.get('data', [])
        if mask_toggle_enabled:
            inpaint_mask = curr.get('mask_inpaint')
            if inpaint_mask is not None:
                inpaint_mask = self.clip_mask_to_checked_text_boxes(inpaint_mask, data)
            inpaint_data = data
        else:
            inpaint_data = []
            inpaint_mask = curr.get('mask_inpaint_off')

        inpaint_mask = self.normalize_inpaint_mask_to_input_image(input_path, inpaint_mask)

        original_input_path = str(input_path)
        input_path, inpaint_mask, proceed_inpaint = self._prepare_single_inpaint_request_with_resize_prompt(page_idx, input_path, inpaint_mask)
        if not proceed_inpaint:
            return
        cleanup_input_path = str(input_path) if str(input_path) != original_input_path else None

        if not mask_toggle_enabled and inpaint_mask is None:
            self.log("⚠️ OFF 페인팅 마스크가 없습니다. 마스크 OFF 상태에서는 직접 칠한 마스크가 필요합니다.")
            return

        if inpaint_mask is not None and int(np.count_nonzero(inpaint_mask)) == 0:
            self.log("⚠️ 인페인팅 마스크가 비어 있습니다.")
            return

        self.log(f"🧾 인페인팅 입력: {input_path}")
        self._long_task_cancel_requested = False
        self._inpaint_target_page_idx = page_idx
        self.prepare_task_progress_overlay("인페인팅", f"{page_idx + 1}페이지 인페인팅 요청을 처리하는 중입니다.", total=0, cancellable=True)
        self.begin_busy_state("인페인팅")
        self.iw = InpaintWorker(self.engine, input_path, inpaint_data, inpaint_mask, page_idx=page_idx, cleanup_path=cleanup_input_path)
        self._active_task_worker = self.iw
        self.iw.log.connect(lambda msg: self.handle_long_task_message(msg))
        self.iw.finished.connect(self.inpaint_end)
        self.iw.start()

    def save_changed_page_without_ui_commit(self, page_idx):
        """worker 결과를 저장하되 현재 화면의 다른 페이지 UI를 target page에 덮지 않는다."""
        if not getattr(self, "project_dir", None):
            return
        try:
            if hasattr(self, 'flush_workspace_image_pages'):
                saved = self.flush_workspace_image_pages([page_idx], reason='inpaint_result', release_non_current=True)
                if saved:
                    self.has_unsaved_changes = True
                    return
        except Exception as e:
            try:
                self.log(f"⚠️ 인페인팅 이미지 즉시 저장 실패({page_idx + 1}p): {e}")
            except Exception:
                pass
        if getattr(self, "auto_save_enabled", False):
            try:
                self.save_project_store(self.project_store)
                if getattr(self, "ysbg_package_path", None) and not getattr(self, "is_temp_project", False):
                    try:
                        package_project(self.project_dir, self.ysbg_package_path)
                    except Exception as e:
                        self.has_unsaved_changes = True
                        self.log(f"⚠️ 인페인팅 결과 패키지 저장 실패({page_idx + 1}p): {e}")
                        return
                self.has_unsaved_changes = bool(getattr(self, "is_temp_project", False) or not getattr(self, "ysbg_package_path", None))
            except Exception as e:
                self.has_unsaved_changes = True
                self.log(f"⚠️ 인페인팅 결과 저장 실패({page_idx + 1}p): {e}")
        else:
            try:
                self.save_to_work_cache()
            except Exception as e:
                self.has_unsaved_changes = True
                self.log(f"⚠️ 인페인팅 작업 캐시 저장 실패({page_idx + 1}p): {e}")

    def inpaint_end(self, page_idx, bg):
        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = int(getattr(self, "_inpaint_target_page_idx", getattr(self, "idx", 0)) or 0)

        if not bg:
            self.log("⚠️ 식질 실패: 결과물이 비어있습니다.")
            self._active_task_worker = None
            self.end_busy_state("인페인팅")
            self.macro_mark_current_step_done("work_inpaint")
            return

        if page_idx < 0 or page_idx >= len(getattr(self, "paths", []) or []):
            self.log("⚠️ 인페인팅 결과를 반영할 페이지를 찾지 못했습니다.")
            self._active_task_worker = None
            self.end_busy_state("인페인팅")
            return

        curr = self.data.get(page_idx)
        if curr is None:
            curr = self.make_page_data_for_image(self.paths[page_idx])
            self.data[page_idx] = curr

        img = self.bg_clean_to_np_image(bg)
        if img is not None:
            img = self.normalize_image_to_original_size(page_idx, img)
            encoded = self.encode_np_image_to_png_bytes(img)
            curr['bg_clean'] = encoded if encoded is not None else bg

            # 인페인팅을 원본으로 쓰는 상태라면, 새 결과를 작업중 원본으로 갱신한다.
            if curr.get('use_inpainted_as_source'):
                self.set_working_source_image(curr, img, page_idx=page_idx)
        else:
            curr['bg_clean'] = bg

        curr['final_paint'] = None
        curr['final_paint_above'] = None
        try:
            if hasattr(self, 'mark_page_data_dirty_explicit'):
                self.mark_page_data_dirty_explicit(page_idx, 'clean_background')
        except Exception:
            pass

        same_page = (page_idx == int(getattr(self, "idx", -1) or -1))
        try:
            if hasattr(self, 'flush_workspace_image_pages'):
                self.flush_workspace_image_pages([page_idx], reason='inpaint_result', release_non_current=not same_page)
            else:
                self.save_changed_page_without_ui_commit(page_idx)
        except Exception as e:
            try:
                self.log(f"⚠️ 인페인팅 결과 workspace 저장 실패({page_idx + 1}p): {e}")
            except Exception:
                pass
            try:
                self.schedule_deferred_auto_save_project(300)
            except Exception:
                self.auto_save_project()

        if same_page:
            # 인페인팅 완료 후 현재 작업 탭을 강제로 최종결과로 넘기지 않는다.
            # 마스크 탭에서 실행했다면 마스크가 그대로 보여야 하고, 최종결과 탭이면 텍스트만 갱신한다.
            try:
                current_mode = int(self.cb_mode.currentIndex())
            except Exception:
                current_mode = 4
            old_suppress = getattr(self, "_suppress_mode_undo", False)
            old_skip_commit = getattr(self, "_skip_mode_mask_commit", False)
            self._suppress_mode_undo = True
            self._skip_mode_mask_commit = True
            try:
                if current_mode == 4:
                    self.refresh_final_text_scene_preserving_selection()
                elif current_mode in (2, 3):
                    try:
                        self.ensure_page_masks_loaded(page_idx, keys=("mask_merge", "mask_inpaint", "mask_merge_off", "mask_inpaint_off"))
                    except Exception:
                        pass
                    self.mode_chg(current_mode)
                elif current_mode == 1:
                    self.refresh_boxes_only()
                else:
                    # 원본 탭 등은 화면을 굳이 다시 만들 필요가 없다.
                    pass
            finally:
                self._suppress_mode_undo = old_suppress
                self._skip_mode_mask_commit = old_skip_commit
            self.log(f"✅ {page_idx + 1}페이지 인페인팅 완료 (클린본 즉시 저장)")
        else:
            self.log(f"✅ {page_idx + 1}페이지 인페인팅 결과 저장 완료: 현재 작업 페이지는 건드리지 않았습니다.")

        # 인페인팅은 배경 이미지와 최종 페인팅 레이어 기준을 바꾸는 작업 경계다.
        self.undo_break_boundary("inpaint")
        self._active_task_worker = None
        self.end_busy_state("인페인팅")
        self.macro_mark_current_step_done("work_inpaint")

    def toggle_check_from_box(self, data_item):
        # 분석도 화면에서만 박스 클릭 토글 허용
        # 0: 원본 / 1: 분석도 / 2: 텍스트 마스크 / 3: 페인팅 마스크 / 4: 최종결과
        if self.cb_mode.currentIndex() != 1:
            return

        curr = self.data.get(self.idx)
        if not curr or 'data' not in curr:
            return

        try:
            data_index = curr['data'].index(data_item)
        except ValueError:
            return

        new_state = not data_item.get('use_inpaint', True)
        table_row = data_index + 1
        self.apply_table_check_state(table_row, new_state)
        self.log((f"🔄 Box click toggle: ID {data_item.get('id')} = {'ON' if new_state else 'OFF'}" if self.ui_language == LANG_EN else f"🔄 박스 클릭 토글: ID {data_item.get('id')} = {'ON' if new_state else 'OFF'}"))

    def refresh_boxes_only(self):
        curr = self.data.get(self.idx)
        if not curr:
            return
        for item in list(self.view.scene.items()):
            if item.zValue() >= 20:
                self.view.scene.removeItem(item)
        self.view.draw_static_boxes(curr.get('data', []))
        self.refresh_ocr_region_overlay()

    def refresh_after_text_line_change(self, autosave=True):
        """텍스트 라인/ID/체크 상태가 바뀐 뒤 현재 탭 표시를 즉시 갱신한다.

        분석도/텍스트 마스크/페인팅 마스크 탭은 왼쪽 번호 박스가 scene에
        따로 그려져 있으므로 data의 id만 바꿔서는 화면 번호가 갱신되지 않는다.
        최종결과 탭은 TypesettingItem을 다시 만들어야 선택/변형 영역까지 맞는다.
        """
        try:
            mode = int(self.cb_mode.currentIndex())
        except Exception:
            mode = 0

        if mode in (1, 2, 3):
            self.refresh_boxes_only()
        elif mode == 4:
            try:
                if hasattr(self, 'schedule_safe_text_scene_resync'):
                    self.schedule_safe_text_scene_resync(
                        reason='refresh_after_text_line_change',
                        delay_ms=40,
                        table_refresh=False,
                    )
                else:
                    old_suppress = getattr(self, "_suppress_mode_undo", False)
                    self._suppress_mode_undo = True
                    try:
                        self.mode_chg(4)
                    finally:
                        self._suppress_mode_undo = old_suppress
            except Exception:
                pass

        if autosave:
            self.auto_save_project()

    def refresh_text_only(self):
        curr = self.data.get(self.idx)
        if not curr:
            self.log("⚠️ 데이터가 없습니다.")
            return
        if not curr.get('bg_clean'):
            self.log("⚠️ 인페인팅을 먼저 해주세요.")
            return

        self.commit_current_page_ui_to_data()
        self.cb_mode.setCurrentIndex(4)
        self.mode_chg(4)
        self.log("✨ 텍스트 갱신 완료")
        self.auto_save_project()

    def on_text_item_moved(self, message):
        self.log(message)
        # 텍스트 이동 fast path에서는 TypesettingItem이 release 시점에 x_off/y_off를
        # page data에 직접 확정한다. 이 경우 scene 전체를 다시 훑는 flush는 중복이고,
        # 고해상도 확대 상태에서 놓는 순간 렉을 만든다.
        direct_flushed = False
        try:
            direct_flushed = bool(getattr(self, '_text_move_direct_data_flushed', False))
        except Exception:
            direct_flushed = False

        if direct_flushed:
            try:
                self.audit_boundary_event(
                    'TEXT_MOVE_DIRTY_FAST_PATH',
                    ids=','.join(sorted(getattr(self, '_text_move_direct_data_flushed_ids', set()) or [])),
                    flush_skipped=True,
                )
            except Exception:
                pass
        else:
            # 텍스트 이동은 scene item 위치와 data[x_off/y_off]를 즉시 맞춘다.
            # 이후 변형/고급옵션/스타일 변경이 data 기준으로 다시 그려도 이동 전 위치로 돌아가지 않게 한다.
            try:
                if hasattr(self, "flush_text_scene_geometry_to_data"):
                    changed = self.flush_text_scene_geometry_to_data(self.selected_text_data_items() if hasattr(self, "selected_text_data_items") else None, mark_dirty=True, reason="text item moved")
                    if not changed:
                        try:
                            self.audit_boundary_event('TEXT_MOVE_DIRTY_SKIPPED_NO_CHANGE', reason='flush returned false')
                        except Exception:
                            pass
            except Exception:
                pass

        try:
            if hasattr(self, 'note_ui_interaction_activity'):
                self.note_ui_interaction_activity(1200)
        except Exception:
            pass
        try:
            if hasattr(self, 'mark_current_page_for_recovery_checkpoint'):
                self.mark_current_page_for_recovery_checkpoint('text')
        except Exception:
            pass
        try:
            self.mark_active_page_dirty('text')
        except Exception:
            pass
        try:
            self.schedule_deferred_auto_save_project()
        except Exception:
            self.auto_save_project()
        finally:
            try:
                self._text_move_direct_data_flushed = False
                self._text_move_direct_data_flushed_ids = set()
            except Exception:
                pass

    def sync_final_text_visibility_only(self):
        """최종결과 탭에서 체크 ON/OFF만 반영할 때 scene 전체를 다시 만들지 않는다."""
        if not hasattr(self, "view") or getattr(self, "view", None) is None:
            return False
        if not hasattr(self.view, "scene") or self.view.scene is None:
            return False
        try:
            show_text = bool(self._safe_show_final_text_checked())
        except Exception:
            show_text = True
        try:
            if self._is_maker_text_table_mode():
                # 쯔꾸르붕이는 식질 툴이 아니므로 YSB 텍스트 객체를 캔버스에 표시하지 않는다.
                # 대사는 별도 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시한다.
                show_text = False
        except Exception:
            pass
        changed = False
        try:
            for obj in list(self.view.scene.items()):
                if not isinstance(obj, TypesettingItem):
                    continue
                data = getattr(obj, 'data', None) or {}
                visible = bool(show_text and data.get('use_inpaint', True) and (str(data.get('translated_text', '') or '').strip() or data.get('force_show')))
                if obj.isVisible() != visible:
                    obj.setVisible(visible)
                    changed = True
        except Exception:
            return False
        return changed

    def _current_project_cache_scope(self):
        """Stable project/session prefix for viewer base pixmap caches.

        Page index + mode alone is unsafe: after closing one project and opening
        another, both can have page 0/final keys.  The viewer cache must include
        the current project identity so an old project's first/last preview cannot
        be reused by a newly opened project.
        """
        try:
            scope = str(getattr(self, "_project_runtime_cache_scope", "") or "").strip()
            if scope:
                return scope
        except Exception:
            pass
        try:
            store = getattr(self, "project_store", None)
            if store is not None and getattr(store, "project_dir", None):
                try:
                    uuid = str(store.project_uuid() or "").strip()
                except Exception:
                    uuid = ""
                if uuid:
                    self._project_runtime_cache_scope = f"uuid:{uuid}"
                    return self._project_runtime_cache_scope
        except Exception:
            pass
        try:
            import hashlib, os
            base = os.path.abspath(str(getattr(self, "project_dir", "") or getattr(getattr(self, "project_store", None), "project_dir", "") or "no_project"))
            scope = hashlib.sha1(base.encode("utf-8", "ignore")).hexdigest()[:16]
            self._project_runtime_cache_scope = f"path:{scope}"
            return self._project_runtime_cache_scope
        except Exception:
            return "no_project"

    def _work_mode_base_key(self, page_idx, kind, curr=None):
        """Cheap scene base key for same-page tab switching.

        The key is intentionally page/kind based so Original/Analysis/Mask tabs
        can reuse the same base pixmap without a full scene rebuild.  Content
        changing operations still clear/reload the page or call the full image
        path elsewhere.
        """
        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = int(getattr(self, "idx", 0) or 0)
        kind = str(kind or "source")
        curr = curr if isinstance(curr, dict) else (self.data.get(page_idx) or {})
        project_scope = self._current_project_cache_scope() if hasattr(self, "_current_project_cache_scope") else str(getattr(self, "_project_runtime_cache_scope", "") or "no_project")
        try:
            if kind == "final":
                marker = curr.get("clean_path") or curr.get("bg_clean_path") or ""
                # 쯔꾸르붕이 맵/공통이벤트 페이지의 final 탭은 bg_clean이 아니라
                # 원본 맵 프리뷰 PNG를 최종 표시 기준으로 사용한다.
                # 따라서 clean_path가 비어 있는 상태에서 빈 프로젝트의 final 키와
                # 게임 가져오기 후 맵 final 키가 같아지면 viewer fast-path가 기존 빈
                # base item을 재사용해 타일 프리뷰가 안 뜰 수 있다.
                try:
                    meta = curr.get("maker_page") if isinstance(curr.get("maker_page"), dict) else {}
                    page_type = str((meta or {}).get("page_type") or "map")
                    if page_type in {"", "map", "common_event"}:
                        paths = getattr(self, "paths", []) or []
                        if 0 <= page_idx < len(paths):
                            src = str(paths[page_idx] or "")
                            marker = src
                            try:
                                import os as _ysb_os
                                if src and _ysb_os.path.exists(src):
                                    st = _ysb_os.stat(src)
                                    marker = f"{src}:mtime{int(st.st_mtime_ns)}:size{int(st.st_size)}"
                            except Exception:
                                pass
                except Exception:
                    pass
                blob = curr.get("bg_clean")
                if isinstance(blob, (bytes, bytearray)):
                    marker = f"{marker}:bg{len(blob)}"
                return f"project:{project_scope}:page:{page_idx}:final:{marker}"
            marker = self.paths[page_idx] if 0 <= page_idx < len(getattr(self, "paths", []) or []) else ""
            if curr.get("use_inpainted_as_source"):
                blob = curr.get("working_source") or curr.get("bg_clean")
                if isinstance(blob, (bytes, bytearray)):
                    marker = f"{marker}:work{len(blob)}"
                marker = f"{marker}:use_work"
            return f"project:{project_scope}:page:{page_idx}:source:{marker}"
        except Exception:
            return f"project:{project_scope}:page:{page_idx}:{kind}"

    def schedule_final_text_scene_refresh(self, delay_ms=120):
        """최종 텍스트 갱신을 가볍게 예약한다.

        가능한 경우 기존 TypesettingItem을 제자리에서 다시 그리며, 전체 mode_chg(4)는 폴백으로만 쓴다.
        """
        try:
            if self.cb_mode.currentIndex() != 4:
                return
        except Exception:
            return
        if getattr(self, "_text_transform_runtime_active", False):
            self._pending_final_text_scene_refresh = True
            return
        try:
            timer = getattr(self, '_final_text_light_refresh_timer', None)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self.refresh_final_text_scene_preserving_selection)
                self._final_text_light_refresh_timer = timer
            timer.stop()
            timer.start(max(10, int(delay_ms or 120)))
        except Exception:
            self.refresh_final_text_scene_preserving_selection()

    def refresh_final_text_scene_preserving_selection(self):
        if self.cb_mode.currentIndex() != 4:
            return
        selected_ids = []
        try:
            selected_ids = [getattr(x, 'data', {}).get('id') for x in self.view.scene.selectedItems() if isinstance(x, TypesettingItem)]
            selected_ids = [x for x in selected_ids if x is not None]
        except Exception:
            selected_ids = []
        try:
            if hasattr(self, 'rebuild_current_page_text_layer_from_data') and self.rebuild_current_page_text_layer_from_data(selected_ids or None):
                return
        except Exception:
            pass
        # Scene/data mismatch or stale item references must not be fixed by immediate
        # mode_chg(4).  Queue a safe resync barrier so the current key/mouse/undo
        # event unwinds before live TypesettingItems are removed/recreated.
        try:
            if hasattr(self, 'schedule_safe_text_scene_resync'):
                self.schedule_safe_text_scene_resync(
                    reason='refresh_final_text_scene_preserving_selection',
                    selected_ids=selected_ids,
                    delay_ms=40,
                )
                return
        except Exception:
            pass
        # Last-ditch fallback only.
        old_suppress = getattr(self, "_suppress_mode_undo", False)
        self._suppress_mode_undo = True
        try:
            self.mode_chg(4)
            if selected_ids:
                self.reselect_text_items(selected_ids)
        finally:
            self._suppress_mode_undo = old_suppress

    def on_table_item_changed(self, item):
        # 쯔꾸르붕이 표 편집은 텍스트 값만 바꾸는 작업이다.
        # 셀 수정마다 행 높이를 다시 계산하면 긴 대사/델리게이트 때문에 체감 렉이 커진다.
        if hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode():
            try:
                row = int(item.row()); col = int(item.column())
                # DB 표는 ID/상태/화자/타입/이벤트/원문/번역문/메모 = 0..7 구조다.
                # 실제 게임 반영 대상인 번역문은 6번 열이다.  이전 코드가 5번 열을
                # 번역문으로 보면서 System.json gameTitle 같은 DB 항목이 메모로만
                # 들어가고 maker_game JSON에 즉시 반영되지 않는 문제가 있었다.
                editable_columns = {
                    1: "maker_status",
                    2: "maker_speaker",
                    5: "text",
                    6: "translated_text",
                    7: "maker_memo",
                }
                if row <= 0 or col not in editable_columns:
                    return
                idx = int(getattr(self, "maker_database_idx", 0) or 0)
                page = self._page_data_for_index_safe(idx) if hasattr(self, "_page_data_for_index_safe") else (getattr(self, "data", {}) or {}).get(idx, {})
                rows = (page or {}).get("data") or []
                data_index = row - 1
                try:
                    id_item = self.tab.item(row, 0)
                    if id_item is not None:
                        v = id_item.data(Qt.ItemDataRole.UserRole)
                        if v is not None:
                            data_index = int(v)
                except Exception:
                    data_index = row - 1
                if data_index < 0 or data_index >= len(rows):
                    return
                key = editable_columns.get(col, "")
                new_text = item.text() if item is not None else ""
                row_data = rows[data_index]
                old_text = str(row_data.get(key) or "") if isinstance(row_data, dict) else ""
                changed = False
                if isinstance(row_data, dict) and new_text != old_text:
                    row_data[key] = new_text
                    if key == "text":
                        row_data["source_text"] = new_text
                    elif key == "maker_speaker":
                        row_data["maker_speaker_plain"] = new_text
                        try:
                            meta = row_data.setdefault("maker_text_unit", {})
                            if isinstance(meta, dict):
                                meta["speaker"] = new_text
                                meta["speaker_plain"] = new_text
                        except Exception:
                            pass
                    elif key == "translated_text":
                        status_text = self.tr_ui("번역완료") if str(new_text or "").strip() else self.tr_ui("미번역")
                        row_data["maker_status"] = status_text
                        if str(new_text or "").strip():
                            row_data["maker_translation_origin"] = "manual_edit"
                        else:
                            row_data.pop("maker_translation_origin", None)
                        try:
                            status_item = self.tab.item(row, 1)
                            if status_item is not None:
                                old_block = self.tab.blockSignals(True)
                                try:
                                    status_item.setText(status_text)
                                    status_item.setData(Qt.ItemDataRole.UserRole, status_text)
                                finally:
                                    self.tab.blockSignals(old_block)
                        except Exception:
                            pass
                    item.setData(Qt.ItemDataRole.UserRole, new_text)
                    changed = True
                    try:
                        self.data[int(idx)] = page
                    except Exception:
                        pass
                    glossary_touched = False
                    if key in ("text", "translated_text"):
                        try:
                            glossary_touched = bool(self._is_maker_database_name_row(row_data))
                        except Exception:
                            glossary_touched = False
                    try:
                        self._finalize_maker_database_page_change(
                            idx,
                            changed_ids=[row_data.get("id")],
                            fields=[key],
                            reason="table_edit",
                            refresh_preview=False,
                            writeback=key in ("text", "translated_text", "maker_speaker"),
                            glossary_touched=glossary_touched,
                            show_glossary_log=False,
                        )
                    except Exception:
                        try:
                            self.has_unsaved_changes = True
                            self.mark_project_structure_dirty("maker_database_page_edit")
                            if key in ("text", "translated_text", "maker_speaker"):
                                self.mark_maker_writeback_dirty(page_indices=[idx], reason="maker_database_table_edit")
                            if glossary_touched:
                                self.refresh_maker_database_auto_glossary_after_name_change(show_log=False, reason="table_edit")
                        except Exception:
                            pass
                elif isinstance(row_data, dict):
                    pass
            except Exception:
                pass
            return
        if self.idx not in self.data:
            return
        curr_data = self.data.get(self.idx)
        if not curr_data or 'data' not in curr_data:
            return

        row = item.row()
        col = item.column()

        # 텍스트 라인/쯔꾸르 메타 수정은 현재 페이지 data 리스트만 저장하는 경량 Undo로 처리한다.
        # 비교 기준은 curr_data가 아니라 셀 생성 시 UserRole에 넣어둔 직전 텍스트다.
        # 이렇게 해야 표 편집/동기화 순서가 꼬여도 수정 전 상태를 안정적으로 잡을 수 있다.
        maker_mode = self._is_maker_text_table_mode()
        if maker_mode:
            editable_columns = {
                1: ("maker_status", "상태 수정"),
                2: ("maker_speaker", "화자 수정"),
                6: ("translated_text", "번역문 텍스트 수정"),
                7: ("maker_memo", "메모 수정"),
            }
        else:
            editable_columns = {
                2: ("text", "원문 텍스트 수정"),
                3: ("translated_text", "번역문 텍스트 수정"),
            }

        if maker_mode and row > 0 and col == 5:
            # 원문 칸은 더블클릭 복사/선택용으로만 편집기를 열어준다.
            # 사용자가 실수로 값을 바꿔도 원본 데이터나 클론 JSON에는 절대 반영하지 않는다.
            try:
                data_index = row - 1
                if 0 <= data_index < len(curr_data.get('data', [])):
                    row_data = curr_data['data'][data_index]
                    display = self._maker_display_original_text(row_data, data_index=data_index)
                    old_block = self.tab.blockSignals(True)
                    try:
                        item.setText(display)
                        item.setData(Qt.ItemDataRole.UserRole, str(row_data.get('text', '') or ''))
                    finally:
                        self.tab.blockSignals(old_block)
            except Exception:
                pass
            return

        if row > 0 and col in editable_columns:
            data_index = row - 1
            if 0 <= data_index < len(curr_data['data']):
                key, reason = editable_columns[col]
                new_text = self.strip_object_display_prefix_for_data(item.text() or '')
                role_old = item.data(Qt.ItemDataRole.UserRole)
                old_text = str(role_old if role_old is not None else curr_data['data'][data_index].get(key, '') or '')
                if new_text != str(item.text() or ''):
                    try:
                        item.setText(new_text)
                    except Exception:
                        pass
                if new_text != old_text:
                    target_id = curr_data['data'][data_index].get('id')
                    # 쯔꾸르붕이 Undo 정책:
                    # 표 편집이 셀에 확정된 뒤에는 전역 Undo 스택에 넣지 않는다.
                    # Ctrl+Z는 열린 텍스트 편집기 내부에서만 Qt 기본 Undo로 동작한다.
                    curr_data['data'][data_index][key] = new_text
                    if maker_mode and key == "maker_speaker":
                        try:
                            row_data = curr_data['data'][data_index]
                            row_data["maker_speaker_source"] = "manual"
                            row_data["maker_speaker_confidence"] = 1.0 if new_text.strip() else 0.0
                            row_data["maker_speaker_plain"] = new_text
                            meta = row_data.setdefault("maker_text_unit", {})
                            if isinstance(meta, dict):
                                meta["speaker"] = new_text
                                meta["speaker_plain"] = new_text
                                meta["speaker_source"] = "manual"
                                meta["speaker_confidence"] = 1.0 if new_text.strip() else 0.0
                            try:
                                item.setToolTip(self._maker_row_speaker_tooltip(row_data))
                            except Exception:
                                pass
                        except Exception:
                            pass
                    item.setData(Qt.ItemDataRole.UserRole, new_text)
                    if key == 'translated_text':
                        try:
                            if maker_mode:
                                if new_text.strip():
                                    curr_data['data'][data_index]['maker_translation_origin'] = "manual_edit"
                                else:
                                    curr_data['data'][data_index].pop('maker_translation_origin', None)
                                # 번역문 유무와 상태/상단 요약은 1대1로 즉시 움직여야 한다.
                                # 기존에는 현재 상태가 미번역일 때만 상태 셀을 바꿔서,
                                # 번역문을 지우거나 다시 채울 때 ALL 헤더 카운트가 stale로 남았다.
                                status_text = self.tr_ui("번역완료") if new_text.strip() else self.tr_ui("미번역")
                                curr_data['data'][data_index]['maker_status'] = status_text
                                status_col = self.tab.item(row, 1)
                                old_block = self.tab.blockSignals(True)
                                try:
                                    if status_col is None:
                                        status_col = self._make_table_item(status_text, editable=True, center=True)
                                        self.tab.setItem(row, 1, status_col)
                                    else:
                                        status_col.setText(status_text)
                                        status_col.setData(Qt.ItemDataRole.UserRole, status_text)
                                finally:
                                    self.tab.blockSignals(old_block)
                                try:
                                    self.refresh_maker_translation_summary_header()
                                except Exception:
                                    pass
                            else:
                                self.shrink_text_rect_to_content(curr_data['data'][data_index])
                        except Exception:
                            pass
                    try:
                        if maker_mode:
                            self.append_maker_recovery_event({
                                "type": "edit_cell",
                                "row": int(row),
                                "data_index": int(data_index),
                                "key": str(key),
                                "old": str(old_text),
                                "new": str(new_text),
                                "text_id": target_id,
                            })
                    except Exception:
                        pass
                    try:
                        if maker_mode and key in ('translated_text', 'maker_speaker', 'maker_memo', 'maker_status'):
                            # 수정 중에는 게임 JSON을 쓰지 않는다. Ctrl+S / 프로젝트 저장 때만
                            # project.json과 작업용 게임 JSON을 함께 저장한다.
                            self.mark_maker_writeback_dirty(page_indices=[int(getattr(self, 'idx', 0) or 0)], reason='manual_table_edit')
                    except Exception:
                        pass
                    if (not maker_mode) and self.cb_mode.currentIndex() == 4:
                        try:
                            if target_id is not None:
                                if not self.refresh_final_text_items_by_ids([target_id]):
                                    self.schedule_final_text_scene_refresh(60)
                            else:
                                self.schedule_final_text_scene_refresh(60)
                        except Exception:
                            self.schedule_final_text_scene_refresh(60)
                    try:
                        self.finalize_maker_text_data_change([target_id], fields=[key], page_idx=int(getattr(self, 'idx', 0) or 0), reason='표 텍스트 수정')
                    except Exception:
                        try:
                            if hasattr(self, 'text_engine') and self.text_engine is not None:
                                self.text_engine.mark_dirty(int(getattr(self, 'idx', 0) or 0), [target_id], [key])
                            self.mark_active_page_dirty('text')
                            self.schedule_deferred_auto_save_project(1800)
                        except Exception:
                            pass
            return

        if col != 1:
            return

        # 체크박스는 현재 중앙 정렬용 QWidget으로 표시되지만,
        # 구버전 프로젝트/예외 상황에서 QTableWidgetItem 신호가 들어오면 같은 처리 함수로 넘긴다.
        try:
            is_checked = item.checkState() == Qt.CheckState.Checked
        except Exception:
            is_checked = self.get_table_check_state(row)
        self.apply_table_check_state(row, is_checked)

    def upd_map(self):
        curr_data = self.data[self.idx]
        active_count = 0
        self._table_check_lock = True
        self.tab.blockSignals(True)
        try:
            for row in range(1, self.tab.rowCount()):
                data_index = row - 1
                if data_index < 0 or data_index >= len(curr_data['data']):
                    continue
                is_checked = self.get_table_check_state(row)
                curr_data['data'][data_index]['use_inpaint'] = is_checked
                if is_checked:
                    active_count += 1
                self.set_table_row_visual(row, is_checked)

            all_checked = active_count == len(curr_data['data']) and len(curr_data['data']) > 0
            self.set_table_check_state(0, all_checked)
            self.paint_all_row_header()
        finally:
            self.tab.blockSignals(False)
            self._table_check_lock = False

        if self.cb_mode.currentIndex() in [1, 2, 3]:
            self.refresh_boxes_only()
        self.log(f"🔄 갱신 완료 (활성: {active_count}개) - 비활성 행은 붉게 표시됨")
        try:
            self.schedule_deferred_auto_save_project()
        except Exception:
            self.auto_save_project()

    def schedule_deferred_auto_save_project(self, delay_ms=1800):
        """YSBG는 건드리지 않고 workspace 복구 체크포인트만 지연 저장한다.

        텍스트 드래그/줌/스타일 조정 중 매 프레임 저장하면 렉이 생긴다.
        그래서 호출부 호환 이름은 유지하되, 실제 동작은:
        - dirty/미저장 표시
        - 현재 페이지를 복구 체크포인트 대상으로 표시
        - delay_ms 뒤 workspace/project.json에 page delta 반영
        이 세 가지로 제한한다.
        """
        if (
            getattr(self, "_suppress_work_cache_dirty", False)
            or getattr(self, "is_loading_project", False)
            or not getattr(self, "project_dir", None)
            or not getattr(self, "paths", None)
        ):
            return
        try:
            self.auto_save_enabled = False
        except Exception:
            pass
        try:
            self.mark_current_page_for_recovery_checkpoint("checkpoint_text")
        except Exception:
            try:
                self.has_unsaved_changes = True
                self.update_window_title()
            except Exception:
                pass
        try:
            self.schedule_workspace_checkpoint(delay_ms, reason="deferred_auto_save")
        except Exception:
            try:
                self.auto_save_project()
            except Exception:
                pass

    def _safe_text_font_family(self):
        """쯔꾸르붕이에서 식질 글꼴 UI가 제거된 뒤 남은 레거시 렌더 경로용 기본 글꼴."""
        try:
            w = getattr(self, "cb_font", None)
            if w is not None:
                return str(w.currentFont().family() or getattr(self, "default_font_family", "Arial") or "Arial")
        except Exception:
            pass
        return str(getattr(self, "default_font_family", "Arial") or "Arial")

    def _safe_text_font_size(self):
        try:
            w = getattr(self, "sb_font_size", None)
            if w is not None:
                return int(w.value())
        except Exception:
            pass
        return int(getattr(self, "default_font_size", 35) or 35)

    def _safe_text_stroke_width(self):
        try:
            w = getattr(self, "sb_strk", None)
            if w is not None:
                return int(w.value())
        except Exception:
            pass
        return int(getattr(self, "default_stroke_width", 3) or 3)

    def _safe_show_final_text_checked(self):
        try:
            w = getattr(self, "cb_show_final_text", None)
            if w is not None:
                return bool(w.isChecked())
        except Exception:
            pass
        return False if self._is_maker_text_table_mode() else True

    def mode_chg(self, i):
        try:
            self.audit_boundary_event("MODE_CHG_ENTER", new_mode=i, old_mode=getattr(self, "_current_work_mode", getattr(self, "last_mode", None)), stack=True)
        except Exception:
            pass
        try:
            self._suppress_view_dirty_until = __import__("time").time() + 0.7
        except Exception:
            pass
        # cb_mode.currentIndexChanged는 콤보박스 값이 이미 바뀐 뒤 들어오므로,
        # 직전 탭은 cb_mode가 아니라 별도 추적값(_current_work_mode)을 기준으로 잡는다.
        old_mode_for_undo = int(getattr(self, "_current_work_mode", getattr(self, "last_mode", 0)) or 0)
        new_mode_for_undo = int(i)
        # 마스크 토글처럼 "같은 탭을 새 마스크 슬롯으로 다시 그리기" 위한 내부 갱신은
        # 사용자가 탭을 이동한 작업이 아니므로 Undo 스택에 탭 변경으로 기록하면 안 된다.
        suppress_mode_undo = bool(
            getattr(self, "_suppress_mode_undo", False)
            or getattr(self, "_mask_toggle_refreshing", False)
        )
        track_mode_change = (
            old_mode_for_undo != new_mode_for_undo
            and not suppress_mode_undo
            and not getattr(self, "is_loading_project", False)
            and not getattr(self, "is_page_loading", False)
            and not getattr(self, "is_batch_running", False)
            and not getattr(self, "_project_undo_restore_lock", False)
            and bool(getattr(self, "paths", []))
        )
        if track_mode_change:
            try:
                old_view_state = self.capture_view_state()
                self.project_ui_view_states[self.view_state_key(self.idx, old_mode_for_undo)] = old_view_state
                if hasattr(self, "layer_engine") and self.layer_engine is not None:
                    self.layer_engine.push_mode_undo(self, self.idx, old_mode_for_undo, new_mode_for_undo, old_view_state)
                    self.layer_engine.remember_mode_state(self.idx, old_mode_for_undo, old_view_state)
                else:
                    rec = self.make_ui_undo_record("작업 탭 변경", self.idx, mode=old_mode_for_undo)
                    rec["view_state"] = copy.deepcopy(old_view_state or {})
                    rec["view_only"] = True
                    rec["ui_only"] = True
                    rec["_undo_scope"] = "page"
                    self.undo_push_page(rec, page_idx=self.idx)
            except Exception:
                pass

        try:
            if hasattr(self, "layer_engine") and self.layer_engine is not None:
                self.layer_engine.begin_switch(self.idx, old_mode_for_undo, new_mode_for_undo)
        except Exception:
            pass

        if getattr(self, "inline_text_editor", None) is not None:
            self.finish_inline_text_edit(commit=True, refresh=False)

        # 이전 마스크 탭에서 벗어나기 전에 자동 반영.
        # 단, 페이지 로딩/일괄 작업 중에는 절대 화면 마스크를 저장하지 않는다.
        should_commit_mask_on_leave = True
        try:
            if hasattr(self, "layer_engine") and self.layer_engine is not None:
                should_commit_mask_on_leave = self.layer_engine.should_commit_mask_before_leave(self, self.idx, self.last_mode)
        except Exception:
            should_commit_mask_on_leave = True
        if (
            should_commit_mask_on_leave
            and not self.is_page_loading
            and not self.is_batch_running
            and not getattr(self, "_skip_mode_mask_commit", False)
            and self.last_mode in [2, 3]
        ):
            curr = self.data.get(self.idx)
            m = self.view.get_mask_np()
            if curr is not None and m is not None:
                self.set_active_mask(curr, m, self.last_mode)
                curr['mask_toggle_enabled'] = self.mask_toggle_enabled
                self.schedule_deferred_auto_save_project()

        should_commit_paint_on_leave = True
        try:
            if hasattr(self, "layer_engine") and self.layer_engine is not None:
                should_commit_paint_on_leave = self.layer_engine.should_commit_paint_before_leave(self, self.idx, self.last_mode)
        except Exception:
            should_commit_paint_on_leave = True
        if (
            should_commit_paint_on_leave
            and not self.is_page_loading
            and not self.is_batch_running
            and self.last_mode == 4
        ):
            curr = self.data.get(self.idx)
            if curr is not None and hasattr(self.view, "get_final_paint_png_bytes"):
                curr['final_paint'] = self.view.get_final_paint_png_bytes()
                if hasattr(self.view, "get_final_paint_above_png_bytes"):
                    curr['final_paint_above'] = self.view.get_final_paint_above_png_bytes()
                self.schedule_deferred_auto_save_project()

        # 사용자가 작업 탭을 바꾸면 브러시/지우개/요술봉/텍스트 입력 같은 도구는
        # 새 탭에서 그대로 이어지면 오작동하기 쉽다. 탭 이동은 항상 이동 모드로 정리한다.
        auto_move_on_tab_change = (
            old_mode_for_undo != new_mode_for_undo
            and not suppress_mode_undo
            and not getattr(self, "is_loading_project", False)
            and not getattr(self, "is_page_loading", False)
            and not getattr(self, "is_batch_running", False)
            and not getattr(self, "_project_undo_restore_lock", False)
        )
        if auto_move_on_tab_change and getattr(self.view, "draw_mode", None):
            self.set_tool(None)

        preserve_view_state = (not self.is_page_loading) and bool(self.view.scene.items())
        saved_transform = self.view.transform() if preserve_view_state else None
        saved_h_scroll = self.view.horizontalScrollBar().value() if preserve_view_state else None
        saved_v_scroll = self.view.verticalScrollBar().value() if preserve_view_state else None

        def restore_view_state_later():
            if not preserve_view_state or saved_transform is None:
                return

            def _restore():
                try:
                    self.view.setTransform(saved_transform)
                    if saved_h_scroll is not None:
                        self.view.horizontalScrollBar().setValue(saved_h_scroll)
                    if saved_v_scroll is not None:
                        self.view.verticalScrollBar().setValue(saved_v_scroll)
                except Exception:
                    pass

            # centerOn은 스크롤바 정수 반올림 때문에 반복 탭 이동 시 좌우로 누적 오차가 생길 수 있다.
            # 그래서 저장된 스크롤바 값을 직접 복원한다.
            QTimer.singleShot(0, _restore)
            QTimer.singleShot(60, _restore)

        self.last_mode = i
        self._current_work_mode = i
        self.update_paint_toolbar_visibility()

        curr = self.data.get(self.idx)
        if not curr:
            self.update_text_style_control_state([])
            self._hide_legacy_option_bars()
            try:
                self.refresh_shared_option_bar()
            except Exception:
                pass
            return

        if i != 4 and getattr(self.view, "draw_mode", None) == 'paste_text':
            self.set_tool(None)

        if i not in [2, 3, 4] and getattr(self.view, "draw_mode", None) == 'magic_wand':
            self.set_tool(None)
        if i not in [2, 3] and getattr(self.view, "draw_mode", None) in ('mask_wrap', 'mask_cut'):
            self.set_tool(None)
        if i not in [1, 2, 3] and getattr(self.view, "draw_mode", None) == 'ocr_region_select':
            self.set_tool(None)
        if i not in [2, 3, 4] and getattr(self.view, "draw_mode", None) == 'area_paint':
            self.set_tool(None)
        self._hide_legacy_option_bars()
        self.update_final_paint_option_bar_visibility()
        try:
            self.refresh_shared_option_bar()
        except Exception:
            pass

        source_img = self.get_source_display_image(self.idx)
        if i in (2, 3):
            try:
                self.ensure_page_masks_loaded(self.idx)
                self.touch_page_mask_cache(self.idx)
                self.trim_page_mask_cache(keep_indices=[self.idx])
            except Exception:
                pass

        # 3-5 후속 안정화: 같은 페이지 안의 작업탭 이동은 base image를 재사용한다.
        # 이전 set_image()/set_overlay() 전체 rebuild 경로는 큰 이미지에서 탭 전환 렉과
        # 불필요한 paint history clear를 만들었다.
        try:
            if i in (0, 1, 2, 3):
                self.view.set_layer_base_image(source_img, key=self._work_mode_base_key(self.idx, "source", curr), fit=not preserve_view_state, clear_paint_history=False)
                self.view.clear_mode_layers(clear_boxes=True, clear_text=True, clear_mask=True, clear_final_paint=True)
                if i == 1:
                    self.view.draw_static_boxes(curr['data'])
                elif i in (2, 3):
                    color = QColor(0, 0, 255, 100) if i == 3 else QColor(255, 0, 0, 100)
                    if hasattr(self.view, "set_mask_overlay_layer"):
                        self.view.set_mask_overlay_layer(self.get_active_mask(curr, i), color)
                    else:
                        self.view.set_overlay(source_img, self.get_active_mask(curr, i), color, fit=not preserve_view_state)
                    self.view.draw_static_boxes(curr['data'])
                self.refresh_ocr_region_overlay()
            elif i == 4:
                self.ensure_item_style_defaults_for_page(self.idx)
                final_base = self.final_base_image_for_page(self.idx)
                self.view.set_layer_base_image(final_base, key=self._work_mode_base_key(self.idx, "final", curr), fit=not preserve_view_state, clear_paint_history=False)
                self.view.clear_mode_layers(clear_boxes=True, clear_text=True, clear_mask=True, clear_final_paint=True)
                self.view.set_final_paint_overlay(curr.get('final_paint'), curr.get('final_paint_above'), fit=False)
                self.update_final_paint_z_order()
                self.view.draw_movable_texts(
                    curr['data'],
                    self._safe_text_font_family(),
                    self._safe_text_font_size(),
                    self._safe_text_stroke_width(),
                    show_text=(False if self._is_maker_text_table_mode() else self._safe_show_final_text_checked()),
                    text_color=self.default_text_color,
                    stroke_color=self.default_stroke_color,
                    align=self.default_align,
                )
        except Exception:
            # 안전 폴백: 가벼운 레이어 갱신에 실패하면 기존 전체 rebuild 경로로 복구한다.
            if i == 0:
                self.view.set_image(source_img, fit=not preserve_view_state)
                self.refresh_ocr_region_overlay()
            elif i == 1:
                self.view.set_image(source_img, fit=not preserve_view_state)
                self.view.draw_static_boxes(curr['data'])
                self.refresh_ocr_region_overlay()
            elif i == 2:
                self.view.set_overlay(source_img, self.get_active_mask(curr, 2), QColor(255, 0, 0, 100), fit=not preserve_view_state)
                self.view.draw_static_boxes(curr['data'])
                self.refresh_ocr_region_overlay()
            elif i == 3:
                self.view.set_overlay(source_img, self.get_active_mask(curr, 3), QColor(0, 0, 255, 100), fit=not preserve_view_state)
                self.view.draw_static_boxes(curr['data'])
                self.refresh_ocr_region_overlay()
            elif i == 4:
                self.ensure_item_style_defaults_for_page(self.idx)
                final_base = self.final_base_image_for_page(self.idx)
                self.view.set_image(final_base, fit=not preserve_view_state)
                self.view.set_final_paint_overlay(curr.get('final_paint'), curr.get('final_paint_above'), fit=False)
                self.update_final_paint_z_order()
                self.view.draw_movable_texts(
                    curr['data'],
                    self._safe_text_font_family(),
                    self._safe_text_font_size(),
                    self._safe_text_stroke_width(),
                    show_text=(False if self._is_maker_text_table_mode() else self._safe_show_final_text_checked()),
                    text_color=self.default_text_color,
                    stroke_color=self.default_stroke_color,
                    align=self.default_align,
                )

        restore_view_state_later()
        try:
            if hasattr(self, "layer_engine") and self.layer_engine is not None:
                self.layer_engine.end_switch(self.idx, i)
        except Exception:
            pass
        try:
            self.refresh_source_compare_view(fit=False)
            QTimer.singleShot(80, lambda: self.schedule_source_compare_sync(120))
        except Exception:
            pass

        if track_mode_change:
            try:
                self.remember_current_view_state()
                # 탭 변경은 현재 페이지 내부 보기 동작이다. 저장 dirty/project save를 깨우지 않는다.
                if hasattr(self, "layer_engine") and self.layer_engine is not None:
                    self.layer_engine.remember_mode_state(self.idx, i, self.capture_view_state())
            except Exception:
                pass

    def prev(self):
        if not self.paths:
            return

        try:
            self.prepare_current_page_boundary("page change")
        except Exception:
            try:
                self.undo_clear_current_page("page change")
            except Exception:
                pass
            self.commit_current_page_ui_to_data()
            self.remember_current_view_state()
        self.idx = (self.idx - 1) % len(self.paths)
        self.load()
        self.restore_current_view_state_later()
        self.schedule_current_page_tab_visible()

    def next(self):
        if not self.paths:
            return

        try:
            self.prepare_current_page_boundary("page change")
        except Exception:
            try:
                self.undo_clear_current_page("page change")
            except Exception:
                pass
            self.commit_current_page_ui_to_data()
            self.remember_current_view_state()
        self.idx = (self.idx + 1) % len(self.paths)
        self.load()
        self.restore_current_view_state_later()
        self.schedule_current_page_tab_visible()

    def jump_page(self):
        if not self.paths:
            return
        num, ok = QInputDialog.getInt(
            self,
            self.tr_ui("맵 이동"),
            self.tr_msg(f"맵 (1~{len(self.paths)}):"),
            self.idx + 1,
            1,
            len(self.paths),
        )
        if ok:
            if num - 1 == self.idx:
                return
            try:
                self.prepare_current_page_boundary("page change")
            except Exception:
                try:
                    self.undo_clear_current_page("page change")
                except Exception:
                    pass
                self.commit_current_page_ui_to_data()
                self.remember_current_view_state()
            self.idx = num - 1
            self.load()
            self.restore_current_view_state_later()
            self.schedule_current_page_tab_visible(center=True)

    def qt_pixmap_from_image_source(self, img):
        """출력용 Qt 렌더에 사용할 QPixmap을 만든다.
        viewer._np2pix와 같은 기준으로 BGR(OpenCV) 이미지를 Qt 화면 색상에 맞춘다.
        """
        try:
            if img is None:
                return QPixmap()

            if isinstance(img, (bytes, bytearray)):
                qimg = QImage.fromData(bytes(img))
                if not qimg.isNull():
                    return QPixmap.fromImage(qimg)
                return QPixmap()

            if isinstance(img, str):
                qimg = QImage(img)
                if not qimg.isNull():
                    return QPixmap.fromImage(qimg)
                # 한글/특수 경로 방어: cv2로 읽어서 다시 넘긴다.
                try:
                    arr = np.fromfile(img, np.uint8)
                    decoded = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
                    if decoded is not None:
                        return self.qt_pixmap_from_image_source(decoded)
                except Exception:
                    pass
                return QPixmap()

            if isinstance(img, QImage):
                return QPixmap.fromImage(img)

            if isinstance(img, QPixmap):
                return img

            if isinstance(img, np.ndarray):
                if img.ndim == 2:
                    h, w = img.shape[:2]
                    qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
                    return QPixmap.fromImage(qimg)

                if img.ndim == 3:
                    h, w, c = img.shape
                    if c == 3:
                        # OpenCV BGR → Qt RGB. viewer._np2pix와 동일한 처리.
                        qimg = QImage(img.data, w, h, c * w, QImage.Format.Format_RGB888).rgbSwapped().copy()
                        return QPixmap.fromImage(qimg)
                    if c == 4:
                        # RGBA 계열 페인트 레이어 등은 viewer 기준과 맞춰 그대로 처리한다.
                        qimg = QImage(img.data, w, h, c * w, QImage.Format.Format_RGBA8888).copy()
                        return QPixmap.fromImage(qimg)
        except Exception:
            pass
        return QPixmap()

    def save_qimage_for_output(self, qimg, path, image_format=None, quality=None):
        """QImage를 출력 옵션 형식(PNG/JPG/WebP)으로 저장한다.
        Qt 플러그인이 특정 형식을 지원하지 않는 경우 PIL로 한 번 더 시도한다.
        """
        fmt = normalize_output_image_format(image_format or self.current_output_image_format())
        quality = normalize_output_image_quality(quality if quality is not None else self.current_output_image_quality())
        try:
            os.makedirs(os.path.dirname(str(path)), exist_ok=True)
        except Exception:
            pass
        qfmt = qt_image_format_name(fmt)
        try:
            if qimg.save(str(path), qfmt, quality):
                return True
        except Exception:
            pass
        try:
            from PIL import Image
            img = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
            w, h = img.width(), img.height()
            ptr = img.bits()
            ptr.setsize(img.sizeInBytes())
            arr = np.array(ptr, dtype=np.uint8).reshape((h, w, 4)).copy()
            pil = Image.fromarray(arr, "RGBA")
            params = {}
            pil_fmt = pil_image_format_name(fmt)
            if fmt == "jpg":
                bg = Image.new("RGB", pil.size, (255, 255, 255))
                try:
                    bg.paste(pil, mask=pil.getchannel("A"))
                except Exception:
                    bg.paste(pil.convert("RGB"))
                pil = bg
                params.update({"quality": quality, "subsampling": 0, "optimize": True})
            elif fmt == "webp":
                params.update({"quality": quality, "method": 6})
            elif fmt == "png":
                params.update({"optimize": True})
            pil.save(str(path), pil_fmt, **params)
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 출력 이미지 저장 실패({fmt}): {e}")
            except Exception:
                pass
            return False

    def save_bgr_image_for_output(self, bgr_image, path, image_format=None, quality=None):
        fmt = normalize_output_image_format(image_format or self.current_output_image_format())
        quality = normalize_output_image_quality(quality if quality is not None else self.current_output_image_quality())
        try:
            os.makedirs(os.path.dirname(str(path)), exist_ok=True)
        except Exception:
            pass
        ext = output_image_extension(fmt)
        params = []
        try:
            if fmt == "jpg":
                params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
            elif fmt == "webp" and hasattr(cv2, "IMWRITE_WEBP_QUALITY"):
                params = [int(cv2.IMWRITE_WEBP_QUALITY), int(quality)]
            elif fmt == "png":
                params = [int(cv2.IMWRITE_PNG_COMPRESSION), 6]
            ok, buf = cv2.imencode(ext, bgr_image, params)
            if ok:
                buf.tofile(str(path))
                return True
        except Exception:
            pass
        try:
            from PIL import Image
            rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            pil_fmt = pil_image_format_name(fmt)
            params = {}
            if fmt == "jpg":
                params.update({"quality": quality, "subsampling": 0, "optimize": True})
            elif fmt == "webp":
                params.update({"quality": quality, "method": 6})
            elif fmt == "png":
                params.update({"optimize": True})
            pil.save(str(path), pil_fmt, **params)
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 출력 이미지 저장 실패({fmt}): {e}")
            except Exception:
                pass
            return False

    def effective_output_text_render_scale(self, base_w, base_h):
        """Return export text render supersampling scale with a memory safety cap."""
        try:
            scale = float(self.current_output_text_render_scale())
        except Exception:
            scale = 1.0
        if scale < 1.0:
            scale = 1.0
        # A very large 3x/4x render can allocate multiple huge QImages.
        # Keep the cap conservative; final output still succeeds, only the render scale is reduced.
        try:
            pixels = max(1, int(base_w) * int(base_h))
            max_pixels = int(getattr(self, "output_text_render_max_pixels", 120_000_000) or 120_000_000)
            while scale > 1.0 and pixels * scale * scale > max_pixels:
                if scale >= 4.0:
                    scale = 3.0
                elif scale >= 3.0:
                    scale = 2.0
                elif scale >= 2.0:
                    scale = 1.0
                else:
                    scale = 1.0
                    break
        except Exception:
            pass
        return max(1.0, float(scale))

    def render_current_final_scene_to_image_qt(self, result_path):
        """현재 최종화면에 실제로 떠 있는 QGraphicsScene을 그대로 PNG로 저장한다.

        Result 출력은 화면에서 보이는 최종 결과와 같아야 한다.
        이전 방식은 data를 기준으로 TypesettingItem을 다시 만들어 렌더했기 때문에,
        텍스트 편집/영역 재설정/변형 직후의 화면 상태와 몇 픽셀 어긋날 수 있었다.
        최종화면 탭에서 출력할 때는 현재 scene 자체를 렌더해서 화면 기준을 최우선으로 맞춘다.
        """
        try:
            if not hasattr(self, 'cb_mode') or self.cb_mode.currentIndex() != 4:
                return False
            scene = self._safe_graphics_scene()
            if scene is None:
                return False

            rect = scene.sceneRect()
            if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
                rect = scene.itemsBoundingRect()
            if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
                return False

            w = max(1, int(round(rect.width())))
            h = max(1, int(round(rect.height())))

            # 출력 PNG에는 선택 박스/점선/변형 핸들이 찍히면 안 된다.
            # 현재 scene을 그대로 쓰되, 렌더 순간에만 보조 가이드를 숨긴다.
            text_items = []
            old_suppress = []
            old_export_mask = []
            try:
                for it in scene.items():
                    if isinstance(it, TypesettingItem):
                        text_items.append(it)
                        old_suppress.append(bool(getattr(it, 'suppress_guides', False)))
                        old_export_mask.append(bool(getattr(it, '_export_mask_stroke', False)))
                        it.suppress_guides = True
                        # Heavy mask-stroke rendering is output/preview-only.
                        # It is intentionally not used in the live editor because
                        # many thick glow/stroke texts make navigation sluggish.
                        it._export_mask_stroke = True
                        it.update()
            except RuntimeError:
                return False

            output_scale = self.effective_output_text_render_scale(w, h)
            if output_scale > 1.0:
                render_w = max(1, int(round(w * output_scale)))
                render_h = max(1, int(round(h * output_scale)))
                hi = QImage(render_w, render_h, QImage.Format.Format_ARGB32_Premultiplied)
                hi.fill(Qt.GlobalColor.white)
                painter = QPainter(hi)
                try:
                    try:
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    except Exception:
                        pass
                    scene.render(painter, QRectF(0, 0, render_w, render_h), rect)
                finally:
                    painter.end()
                out = hi.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_RGB32)
            else:
                out = QImage(w, h, QImage.Format.Format_RGB32)
                out.fill(Qt.GlobalColor.white)
                painter = QPainter(out)
                try:
                    try:
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    except Exception:
                        pass
                    scene.render(painter, QRectF(0, 0, w, h), rect)
                finally:
                    painter.end()

            for it, old, old_mask in zip(text_items, old_suppress, old_export_mask):
                try:
                    it.suppress_guides = old
                    it._export_mask_stroke = old_mask
                    it.update()
                except RuntimeError:
                    pass
                except Exception:
                    pass

            try:
                self.audit_boundary_event("EXPORT_CURRENT_SCENE_TEXT_RENDER", scale=output_scale, width=w, height=h, throttle_ms=100)
            except Exception:
                pass

            try:
                os.makedirs(os.path.dirname(result_path), exist_ok=True)
            except Exception:
                pass
            if self.save_qimage_for_output(out, result_path):
                return True

            try:
                tmp_path = os.path.join(os.path.dirname(result_path), '__ysb_current_scene_result_tmp' + output_image_extension(self.current_output_image_format()))
                if self.save_qimage_for_output(out, tmp_path):
                    shutil.move(tmp_path, result_path)
                    return True
            except Exception:
                pass
            return False
        except Exception as e:
            try:
                self.log(f"⚠️ 현재 최종화면 기준 출력 실패: {e}")
            except Exception:
                pass
            return False

    def render_final_tab_scene_for_export_qt(self, result_path):
        """최종 탭 화면을 실제로 한 번 그린 뒤 그 QGraphicsScene을 그대로 저장한다.

        출력 PNG는 사용자가 최종 탭에서 보는 화면과 일치해야 한다.
        현재 작업 탭이 최종결과가 아닐 때 기존 코드는 data만으로 별도 scene을 재구성했는데,
        자동 조판/텍스트 변형 직후에는 화면 렌더 경로와 재구성 렌더 경로가 갈라질 수 있었다.
        그래서 출력 시 잠깐 최종결과 탭을 그려 현재 프로그램 화면과 같은 경로로 렌더한다.
        """
        if not hasattr(self, 'cb_mode'):
            return False

        old_mode = int(self.cb_mode.currentIndex())
        old_suppress_mode_undo = bool(getattr(self, '_suppress_mode_undo', False))
        old_skip_mode_mask_commit = bool(getattr(self, '_skip_mode_mask_commit', False))
        old_batch_running = bool(getattr(self, 'is_batch_running', False))
        old_draw_mode = getattr(getattr(self, 'view', None), 'draw_mode', None)
        old_suppress_option = bool(getattr(self, '_suppress_shared_option_refresh', False))
        old_export_guard = bool(getattr(self, '_export_rendering_guard', False))

        try:
            # 탭 임시 이동은 사용자 작업이 아니므로 Undo/마스크 자동 반영/도구 전환 부작용을 막는다.
            # 또한 출력 렌더 중에는 상단 텍스트 선택 옵션 위젯이 갱신되면 안 된다.
            self._suppress_mode_undo = True
            self._skip_mode_mask_commit = True
            self.is_batch_running = True
            self._export_rendering_guard = True
            self._suppress_shared_option_refresh = True
            try:
                self._hide_legacy_option_bars()
                self._clear_shared_option_left()
            except Exception:
                pass

            if old_mode != 4:
                self.cb_mode.blockSignals(True)
                try:
                    self.cb_mode.setCurrentIndex(4)
                finally:
                    self.cb_mode.blockSignals(False)
                # blockSignals로 신호를 막았으므로 직접 최종 탭을 그린다.
                self.mode_chg(4)
            else:
                # 이미 최종 탭이어도 data 변경 직후일 수 있으므로 한 번 새로 그린다.
                self.mode_chg(4)

            try:
                QApplication.processEvents()
            except Exception:
                pass

            return self.render_current_final_scene_to_image_qt(result_path)
        except Exception as e:
            try:
                self.log(f"⚠️ 최종화면 동기화 출력 실패: {e}")
            except Exception:
                pass
            return False
        finally:
            try:
                self._suppress_mode_undo = old_suppress_mode_undo
                self._skip_mode_mask_commit = old_skip_mode_mask_commit
                self.is_batch_running = old_batch_running
                self._export_rendering_guard = old_export_guard
                self._suppress_shared_option_refresh = old_suppress_option
            except Exception:
                pass

            if old_mode != 4:
                try:
                    self.cb_mode.blockSignals(True)
                    self.cb_mode.setCurrentIndex(old_mode)
                    self.cb_mode.blockSignals(False)
                    self._suppress_mode_undo = True
                    self._skip_mode_mask_commit = True
                    self.is_batch_running = True
                    self._export_rendering_guard = True
                    self._suppress_shared_option_refresh = True
                    self.mode_chg(old_mode)
                except Exception:
                    pass
                finally:
                    try:
                        self._suppress_mode_undo = old_suppress_mode_undo
                        self._skip_mode_mask_commit = old_skip_mode_mask_commit
                        self.is_batch_running = old_batch_running
                        self._export_rendering_guard = old_export_guard
                        self._suppress_shared_option_refresh = old_suppress_option
                    except Exception:
                        pass

            try:
                if old_draw_mode and hasattr(self, 'view'):
                    self.view.draw_mode = old_draw_mode
            except Exception:
                pass

            # 단일 출력에서는 즉시 원래 옵션바를 복구한다.
            # 일괄 출력 중에는 페이지마다 옵션바를 다시 붙이지 않고 마지막에만 복구한다.
            try:
                if not bool(getattr(self, "_batch_export_streaming", False)) and hasattr(self, "refresh_shared_option_bar"):
                    self.refresh_shared_option_bar()
            except Exception:
                pass

    def render_final_result_image_qt(self, result_path, bg_image, paint_above_data=None):
        """최종 PNG를 Qt 최종화면과 같은 렌더러로 다시 저장한다.

        엔진의 PIL 렌더는 검수용으로 충분하지만, QGraphicsPath 기반 최종화면과
        폰트 메트릭/기준선이 달라 텍스트 좌표가 몇 픽셀씩 어긋날 수 있다.
        그래서 result/Result_XXXX.png는 실제 최종화면과 같은 TypesettingItem을
        오프스크린 QGraphicsScene에 올려 다시 렌더한다.
        """
        curr = self.data.get(self.idx)
        if not curr:
            return False

        bg_pix = self.qt_pixmap_from_image_source(bg_image)
        if bg_pix.isNull() or bg_pix.width() <= 0 or bg_pix.height() <= 0:
            return False

        scene = QGraphicsScene()
        bg_item = scene.addPixmap(bg_pix)
        bg_item.setZValue(0)
        scene.setSceneRect(QRectF(0, 0, bg_pix.width(), bg_pix.height()))

        visible_items = []
        for d in curr.get('data', []):
            if not d.get('use_inpaint', True):
                continue
            if not str(d.get('translated_text', '') or '').strip() and not d.get('force_show'):
                continue
            visible_items.append(d)

        total_items = len(visible_items)
        for order_idx, d in enumerate(visible_items):
            item = TypesettingItem(
                d,
                self._safe_text_font_family(),
                self._safe_text_font_size(),
                self._safe_text_stroke_width(),
                None,
                text_color=self.default_text_color,
                stroke_color=self.default_stroke_color,
                align=self.default_align,
            )
            # 출력 PNG에는 작업용 점선 박스/선택 박스/변형 핸들을 찍지 않는다.
            item.suppress_guides = True
            # Use the heavy Photoshop-like mask stroke only in export/output preview.
            item._export_mask_stroke = True
            item.setSelected(False)
            item.setZValue(30 + (total_items - order_idx))
            scene.addItem(item)

        if paint_above_data is not None and hasattr(self, "view") and hasattr(self.view, "_paint_qimage_from_data"):
            try:
                above_qimg = self.view._paint_qimage_from_data(paint_above_data, bg_pix.width(), bg_pix.height())
                if not above_qimg.isNull():
                    above_item = scene.addPixmap(QPixmap.fromImage(above_qimg))
                    above_item.setZValue(80)
            except Exception:
                pass

        # Output-only high quality text engine.  The editor preview stays light,
        # but exported files can spend a little more time supersampling text/effects.
        # The scale is selected in the output options dialog.
        try:
            base_w = int(bg_pix.width())
            base_h = int(bg_pix.height())
            output_scale = self.effective_output_text_render_scale(base_w, base_h)
        except Exception:
            base_w, base_h, output_scale = bg_pix.width(), bg_pix.height(), 1.0

        if output_scale > 1.0:
            render_w = max(1, int(round(base_w * output_scale)))
            render_h = max(1, int(round(base_h * output_scale)))
            hi = QImage(render_w, render_h, QImage.Format.Format_ARGB32_Premultiplied)
            hi.fill(Qt.GlobalColor.white)
            painter = QPainter(hi)
            try:
                try:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                except Exception:
                    pass
                scene.render(
                    painter,
                    QRectF(0, 0, render_w, render_h),
                    QRectF(0, 0, base_w, base_h),
                )
            finally:
                painter.end()
                scene.clear()
            out = hi.scaled(base_w, base_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_RGB32)
        else:
            out = QImage(base_w, base_h, QImage.Format.Format_RGB32)
            out.fill(Qt.GlobalColor.white)
            painter = QPainter(out)
            try:
                try:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                except Exception:
                    pass
                scene.render(
                    painter,
                    QRectF(0, 0, base_w, base_h),
                    QRectF(0, 0, base_w, base_h),
                )
            finally:
                painter.end()
                scene.clear()

        try:
            self.audit_boundary_event("EXPORT_QT_SUPERSAMPLE_RENDER", scale=output_scale, width=base_w, height=base_h, throttle_ms=100)
        except Exception:
            pass

        try:
            os.makedirs(os.path.dirname(result_path), exist_ok=True)
        except Exception:
            pass

        if self.save_qimage_for_output(out, result_path):
            return True

        # 일부 환경에서 한글 경로 저장이 실패할 때를 대비한 임시 파일 우회.
        try:
            tmp_path = os.path.join(os.path.dirname(result_path), "__ysb_qt_result_tmp" + output_image_extension(self.current_output_image_format()))
            if self.save_qimage_for_output(out, tmp_path):
                shutil.move(tmp_path, result_path)
                return True
        except Exception:
            pass
        return False

    def _load_output_preview_qimage(self, image_path):
        """Load the already-encoded export file back into a QImage for preview.

        This makes Export Preview show the same result the user would get after
        saving, including JPG/WebP quality loss.  Qt may not be able to read WebP
        on some systems, so Pillow is used as a fallback.
        """
        try:
            qimg = QImage(str(image_path))
            if not qimg.isNull():
                return qimg
        except Exception:
            pass
        try:
            from PIL import Image
            pil = Image.open(str(image_path)).convert("RGBA")
            w, h = pil.size
            arr = np.array(pil, dtype=np.uint8)
            return QImage(arr.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
        except Exception:
            return QImage()

    def show_output_preview(self):
        """Render and show the current page exactly as export will save it.

        Export Preview is not a separate approximate renderer.  It opens the same
        output options dialog, renders the current page through an offscreen export
        scene without changing the live editor tab/scene, writes the encoded image
        into a temporary result folder, reads that exact encoded file back, and
        displays it in the preview viewer.
        """
        curr = self.data.get(self.idx) if hasattr(self, 'data') else None
        if not curr:
            try:
                QMessageBox.information(self, self.tr_ui("출력 미리보기"), self.tr_msg("미리보기할 현재 페이지 데이터가 없습니다."))
            except Exception:
                pass
            return

        # Preview must use the same options as actual export.  If the user cancels
        # here, no preview is generated and no project data is touched.
        try:
            if not self.open_output_options_dialog():
                try:
                    self.log("↩️ 출력 미리보기 취소")
                except Exception:
                    pass
                return
        except Exception as e:
            try:
                QMessageBox.warning(self, self.tr_ui("출력 미리보기"), self.tr_msg(f"출력 옵션 창을 열지 못했습니다: {e}"))
            except Exception:
                pass
            return

        tmp_dir = None
        tmp_path = None
        old_batch_running = bool(getattr(self, 'is_batch_running', False))
        try:
            try:
                self.show_task_progress_overlay(
                    self.tr_ui("출력 미리보기"),
                    self.tr_ui("실제 출력과 동일한 옵션으로 미리보기를 생성하는 중입니다..."),
                    total=7,
                    cancellable=False,
                )
                QApplication.processEvents()
            except Exception:
                pass

            try:
                self.update_task_progress_overlay(current=1, total=7, detail=self.tr_ui("현재 페이지 데이터를 정리하는 중입니다."))
                QApplication.processEvents()
            except Exception:
                pass
            try:
                self.commit_current_page_ui_to_data()
            except Exception:
                pass
            try:
                if self.cb_mode.currentIndex() == 4 and hasattr(self.view, "get_final_paint_png_bytes"):
                    curr['final_paint'] = self.view.get_final_paint_png_bytes()
                    if hasattr(self.view, "get_final_paint_above_png_bytes"):
                        curr['final_paint_above'] = self.view.get_final_paint_above_png_bytes()
            except Exception:
                pass
            try:
                self.ensure_item_style_defaults_for_page(self.idx)
            except Exception:
                pass

            try:
                self.update_task_progress_overlay(current=2, total=7, detail=self.tr_ui("출력 배경과 페인팅 레이어를 준비하는 중입니다."))
                QApplication.processEvents()
            except Exception:
                pass
            export_bg = curr.get('bg_clean')
            if export_bg is None:
                export_bg = self.final_base_image_for_page(self.idx)
            if export_bg is None:
                export_bg = self.get_source_display_image(self.idx)
            if export_bg is None:
                self.ensure_page_source_path(self.idx)
                try:
                    export_bg = self.paths[self.idx]
                except Exception:
                    export_bg = None
            if curr.get('final_paint'):
                try:
                    base_img = self.bg_clean_to_np_image(export_bg)
                    export_img = self.compose_final_paint_on_bgr(base_img, curr.get('final_paint'))
                    export_bg = self.encode_np_image_to_png_bytes(export_img) or export_img
                except Exception:
                    pass

            tmp_dir = tempfile.mkdtemp(prefix="ysb_output_preview_exact_")
            output_stem = self.output_display_stem(self.idx)
            clean_stem = self.get_page_stem(self.idx)
            source_path_for_export = None
            try:
                source_path_for_export = self.paths[self.idx] if self.paths and self.idx < len(self.paths) else self.path_for_output_display(self.idx)
            except Exception:
                source_path_for_export = self.path_for_output_display(self.idx)
            try:
                result_ext = output_image_extension(self.current_output_image_format())
            except Exception:
                result_ext = ".png"
            tmp_path = os.path.join(tmp_dir, "result", f"Result_{safe_page_file_stem(output_stem, 'output')}{result_ext}")

            try:
                self.update_task_progress_overlay(current=3, total=7, detail=self.tr_ui("기본 출력 이미지를 생성하는 중입니다."))
                QApplication.processEvents()
            except Exception:
                pass
            self.engine.export_project_result(
                curr['data'],
                source_path_for_export,
                export_bg,
                self._safe_text_font_family(),
                self._safe_text_stroke_width(),
                self._safe_text_font_size(),
                output_root=tmp_dir,
                output_name_stem=output_stem,
                clean_name_stem=clean_stem,
                output_image_format=self.current_output_image_format(),
                clean_image_format=self.current_clean_image_format(),
                output_image_quality=self.current_output_image_quality(),
                clean_image_quality=self.current_clean_image_quality(),
            )

            try:
                self.update_task_progress_overlay(current=4, total=7, detail=self.tr_ui("오프스크린에서 최종 텍스트를 렌더링하는 중입니다."))
                QApplication.processEvents()
            except Exception:
                pass

            # 출력 미리보기는 절대 실제 최종결과 탭/scene을 건드리지 않는다.
            # render_final_tab_scene_for_export_qt()는 mode_chg/load/ref_tab을 거치며
            # Qt UI scene을 재구성하므로, 미리보기 중 Abort/access violation의 원인이 될 수 있다.
            # 대신 현재 페이지 데이터 snapshot + 배경만으로 오프스크린 QGraphicsScene을 만들어
            # 실제 출력 파일과 같은 포맷으로 저장한 뒤 그 파일을 다시 읽어 미리보기한다.
            old_preview_guard = bool(getattr(self, "_output_preview_offscreen_rendering", False))
            self._output_preview_offscreen_rendering = True
            try:
                qt_result_rendered = self.render_final_result_image_qt(tmp_path, export_bg, curr.get('final_paint_above'))
            finally:
                try:
                    self._output_preview_offscreen_rendering = old_preview_guard
                except Exception:
                    pass

            if not qt_result_rendered:
                raise RuntimeError(self.tr_msg("오프스크린 출력 렌더링에 실패했습니다."))

            if not os.path.exists(tmp_path):
                raise RuntimeError(self.tr_msg("출력 미리보기를 생성하지 못했습니다."))

            try:
                self.update_task_progress_overlay(current=7, total=7, detail=self.tr_ui("실제 출력 파일과 같은 포맷으로 미리보기를 확인하는 중입니다."))
                QApplication.processEvents()
            except Exception:
                pass
            img = self._load_output_preview_qimage(tmp_path)
            if img.isNull():
                raise RuntimeError(self.tr_msg("출력 미리보기 이미지를 읽지 못했습니다."))
            pix = QPixmap.fromImage(img)

            try:
                self.hide_task_progress_overlay()
            except Exception:
                pass

            self._show_output_preview_dialog(pix, tmp_dir=tmp_dir, tmp_result_path=tmp_path)
        except Exception as e:
            try:
                self.hide_task_progress_overlay()
            except Exception:
                pass
            try:
                QMessageBox.warning(self, self.tr_ui("출력 미리보기"), self.tr_msg(f"출력 미리보기 생성 실패: {e}"))
            except Exception:
                pass
            try:
                self.log(f"⚠️ 출력 미리보기 생성 실패: {e}")
            except Exception:
                pass
        finally:
            try:
                self.is_batch_running = old_batch_running
            except Exception:
                pass
            try:
                if tmp_dir and os.path.isdir(tmp_dir):
                    shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def _publish_output_preview_files(self, tmp_dir, tmp_result_path=None, parent=None):
        """Copy the already-rendered Export Preview result into the real output folders.

        Export Preview now creates the same encoded files as an actual export inside
        a temporary output root.  Pressing [Export] in the preview dialog should not
        render again; it should publish those exact files so the preview and saved
        result remain identical.
        """
        tmp_root = Path(str(tmp_dir or ""))
        if not tmp_root.exists():
            raise RuntimeError(self.tr_msg("미리보기 임시 출력 폴더를 찾지 못했습니다."))

        tmp_result = Path(str(tmp_result_path or "")) if tmp_result_path else None
        if tmp_result is not None and (not tmp_result.exists()):
            tmp_result = None
        if tmp_result is None:
            result_candidates = []
            try:
                result_candidates = sorted((tmp_root / "result").glob("Result_*"))
            except Exception:
                result_candidates = []
            tmp_result = result_candidates[0] if result_candidates else None
        if tmp_result is None or not tmp_result.exists():
            raise RuntimeError(self.tr_msg("미리보기 결과 파일이 없습니다."))

        out_root = Path(str(self.get_output_root()))
        result_dir = out_root / "result"
        clean_dir = out_root / "clean"
        scripts_dir = out_root / "scripts"
        for d in (result_dir, clean_dir, scripts_dir):
            d.mkdir(parents=True, exist_ok=True)

        output_stem = safe_page_file_stem(self.output_display_stem(self.idx), "output")
        clean_source_stem = safe_page_file_stem(self.get_page_stem(self.idx), "clean")
        clean_stem = clean_source_stem if clean_source_stem.lower().startswith("clean_") else f"clean_{clean_source_stem}"

        # Remove old variants for this page before copying the exact preview files.
        try:
            self.remove_output_format_variants(result_dir, output_stem, "Result_")
        except Exception:
            pass
        try:
            self.remove_output_format_variants(clean_dir, clean_stem, "")
            self.remove_output_format_variants(clean_dir, clean_source_stem, "")
            self.remove_output_format_variants(clean_dir, output_stem, "Clean_")
        except Exception:
            pass
        try:
            old_script = scripts_dir / f"Script_{output_stem}.jsx"
            if old_script.exists():
                old_script.unlink()
        except Exception:
            pass

        copied = []
        for sub in ("clean", "result", "scripts"):
            src_dir = tmp_root / sub
            dst_dir = out_root / sub
            if not src_dir.exists():
                continue
            try:
                for src in src_dir.iterdir():
                    if not src.is_file():
                        continue
                    dst = dst_dir / src.name
                    try:
                        shutil.copy2(str(src), str(dst))
                        copied.append(str(dst))
                    except Exception:
                        shutil.copy(str(src), str(dst))
                        copied.append(str(dst))
            except Exception as e:
                try:
                    self.log(f"⚠️ 미리보기 출력 파일 복사 실패({sub}): {e}")
                except Exception:
                    pass

        if not copied:
            raise RuntimeError(self.tr_msg("미리보기 출력 파일을 저장하지 못했습니다."))

        try:
            self.log("✅ 미리보기 결과를 실제 출력 폴더에 저장했습니다.")
            for path in copied:
                self.log(f"   - {path}")
        except Exception:
            pass
        return copied

    def _show_output_preview_dialog(self, pixmap, tmp_dir=None, tmp_result_path=None):
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("출력 미리보기"))
        try:
            dlg.setWindowIcon(QIcon(resource_path("ysb_icon.ico")))
        except Exception:
            pass
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)
        title = QLabel(self.tr_ui("출력 미리보기"))
        title.setStyleSheet("font-size:18px;font-weight:700;")
        layout.addWidget(title)
        info = QLabel(self.tr_ui("현재 페이지가 실제 출력에서 어떻게 보일지 렌더링한 미리보기입니다. 텍스트 이펙트 미리보기가 꺼져 있어도 출력 기준 이펙트는 모두 적용됩니다."))
        info.setWordWrap(True)
        layout.addWidget(info)

        class OutputPreviewView(QGraphicsView):
            def __init__(self, pix, parent=None):
                super().__init__(parent)
                self._scene = QGraphicsScene(self)
                self._item = self._scene.addPixmap(pix)
                self._scene.setSceneRect(QRectF(0, 0, pix.width(), pix.height()))
                self.setScene(self._scene)
                self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
                self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
                self._fit_on_show = True

            def fit_to_window(self):
                rect = self._scene.sceneRect()
                if not rect.isNull():
                    self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
                    self._fit_on_show = False

            def actual_size(self):
                self.resetTransform()
                self._fit_on_show = False

            def zoom_by(self, factor):
                try:
                    factor = float(factor)
                except Exception:
                    factor = 1.0
                if factor <= 0:
                    return
                self.scale(factor, factor)
                self._fit_on_show = False

            def wheelEvent(self, event):
                try:
                    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        delta = event.angleDelta().y()
                        self.zoom_by(1.25 if delta > 0 else 0.8)
                        event.accept()
                        return
                except Exception:
                    pass
                super().wheelEvent(event)

            def resizeEvent(self, event):
                super().resizeEvent(event)
                if self._fit_on_show:
                    QTimer.singleShot(0, self.fit_to_window)

        view = OutputPreviewView(pixmap, dlg)
        layout.addWidget(view, 1)

        bottom = QHBoxLayout()
        fit_btn = QPushButton(self.tr_ui("전체 보기"))
        fit_btn.clicked.connect(view.fit_to_window)
        bottom.addWidget(fit_btn)
        actual_btn = QPushButton(self.tr_ui("100%"))
        actual_btn.clicked.connect(view.actual_size)
        bottom.addWidget(actual_btn)
        zoom_out_btn = QPushButton(self.tr_ui("축소"))
        zoom_out_btn.clicked.connect(lambda: view.zoom_by(0.8))
        bottom.addWidget(zoom_out_btn)
        zoom_in_btn = QPushButton(self.tr_ui("확대"))
        zoom_in_btn.clicked.connect(lambda: view.zoom_by(1.25))
        bottom.addWidget(zoom_in_btn)
        bottom.addStretch(1)
        hint = QLabel(self.tr_ui("Ctrl+마우스휠로 확대/축소"))
        try:
            hint.setStyleSheet("color:#aaa;")
        except Exception:
            pass
        bottom.addWidget(hint)

        export_btn = QPushButton(self.tr_ui("출력"))
        export_btn.setToolTip(self.tr_ui("미리보기 이미지를 그대로 실제 출력 폴더에 저장하고 포토샵 스크립트도 함께 저장합니다."))

        def _export_preview_now():
            try:
                export_btn.setEnabled(False)
                export_btn.setText(self.tr_ui("출력 중..."))
                QApplication.processEvents()
                copied = self._publish_output_preview_files(tmp_dir, tmp_result_path, parent=dlg)
                export_btn.setText(self.tr_ui("출력 완료"))
                try:
                    QMessageBox.information(
                        dlg,
                        self.tr_ui("출력 미리보기"),
                        self.tr_msg("미리보기 결과를 실제 출력 폴더에 저장했습니다.")
                    )
                except Exception:
                    pass
            except Exception as e:
                try:
                    export_btn.setEnabled(True)
                    export_btn.setText(self.tr_ui("출력"))
                except Exception:
                    pass
                try:
                    QMessageBox.warning(
                        dlg,
                        self.tr_ui("출력 미리보기"),
                        self.tr_msg(f"미리보기 결과 출력 실패: {e}")
                    )
                except Exception:
                    pass
                try:
                    self.log(f"⚠️ 미리보기 결과 출력 실패: {e}")
                except Exception:
                    pass

        export_btn.clicked.connect(_export_preview_now)
        bottom.addWidget(export_btn)
        close_btn = QPushButton(self.tr_ui("닫기"))
        close_btn.clicked.connect(dlg.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        try:
            screen = QApplication.primaryScreen()
            geo = screen.availableGeometry() if screen else None
            max_w = int(geo.width() * 0.86) if geo else 1100
            max_h = int(geo.height() * 0.86) if geo else 820
        except Exception:
            max_w, max_h = 1100, 820
        try:
            dlg.resize(min(max_w, max(720, int(max_w))), min(max_h, max(560, int(max_h))))
        except Exception:
            dlg.resize(960, 720)
        QTimer.singleShot(0, view.fit_to_window)
        dlg.exec()

    def export_result(self, autosave=True, prompt_options=True):
        if prompt_options and not bool(getattr(self, "_suppress_export_options_dialog", False)):
            if not self.open_output_options_dialog():
                try:
                    self.log("↩️ 출력 취소")
                except Exception:
                    pass
                return
        curr = self.data.get(self.idx)
        if not curr:
            self.log("⚠️ 데이터 없음")
            return

        single_progress = not bool(getattr(self, "_batch_export_streaming", False))

        def _progress(current=None, total=6, detail=""):
            if not single_progress:
                return
            try:
                self.update_task_progress_overlay(current=current, total=total, detail=self.tr_ui(detail or "출력 진행 중..."))
                QApplication.processEvents()
            except Exception:
                pass

        if single_progress:
            try:
                self.show_task_progress_overlay(
                    self.tr_ui("개별 출력"),
                    self.tr_ui("출력 준비 중..."),
                    total=6,
                    cancellable=False,
                )
                QApplication.processEvents()
            except Exception:
                pass

        try:
            _progress(0, detail="현재 페이지 데이터를 정리하는 중입니다.")
            self.commit_current_page_ui_to_data()
            if self.cb_mode.currentIndex() == 4 and hasattr(self.view, "get_final_paint_png_bytes"):
                curr['final_paint'] = self.view.get_final_paint_png_bytes()
                if hasattr(self.view, "get_final_paint_above_png_bytes"):
                    curr['final_paint_above'] = self.view.get_final_paint_above_png_bytes()
            self.ensure_item_style_defaults_for_page(self.idx)
            export_bg = curr.get('bg_clean')
            if export_bg is None:
                export_bg = self.final_base_image_for_page(self.idx)
            if export_bg is None:
                export_bg = self.get_source_display_image(self.idx)
            if export_bg is None:
                self.ensure_page_source_path(self.idx)
                try:
                    export_bg = self.paths[self.idx]
                except Exception:
                    export_bg = None

            _progress(1, detail="출력 배경과 페인팅 레이어를 준비하는 중입니다.")
            if curr.get('final_paint'):
                base_img = self.bg_clean_to_np_image(export_bg)
                export_img = self.compose_final_paint_on_bgr(base_img, curr.get('final_paint'))
                export_bg = self.encode_np_image_to_png_bytes(export_img) or export_img
            self.ensure_page_source_path(self.idx)
            output_stem = self.output_display_stem(self.idx)
            source_path_for_export = self.paths[self.idx] if self.paths and self.idx < len(self.paths) else self.path_for_output_display(self.idx)

            _progress(2, detail="기본 출력 이미지를 생성하는 중입니다.")
            p = self.engine.export_project_result(
                curr['data'],
                source_path_for_export,
                export_bg,
                self._safe_text_font_family(),
                self._safe_text_stroke_width(),
                self._safe_text_font_size(),
                output_root=self.get_output_root(),
                output_name_stem=output_stem,
                clean_name_stem=self.get_page_stem(self.idx),
                output_image_format=self.current_output_image_format(),
                clean_image_format=self.current_clean_image_format(),
                output_image_quality=self.current_output_image_quality(),
                clean_image_quality=self.current_clean_image_quality(),
            )
            result_path = self.output_result_file_path(output_stem)

            # Result PNG는 포토샵 스크립트용 엔진 렌더(PIL)가 아니라 Qt 렌더로 다시 저장한다.
            # 최종화면 탭에서 출력하는 경우에는 data로 다시 조립하지 않고,
            # 현재 화면에 실제로 떠 있는 QGraphicsScene을 그대로 렌더한다.
            # 이렇게 해야 글꼴/영역 재설정/변형 직후의 화면과 출력 PNG가 1:1에 가깝게 맞는다.
            qt_result_rendered = False

            _progress(3, detail="최종화면 기준으로 텍스트를 렌더링하는 중입니다.")
            # Result PNG는 항상 최종결과 탭에서 보이는 화면과 같은 QGraphicsScene 렌더 경로를 사용한다.
            # 현재 탭이 최종결과가 아니어도 잠깐 최종 탭을 그린 뒤 저장하고 원래 탭으로 돌린다.
            qt_result_rendered = self.render_final_tab_scene_for_export_qt(result_path)
            if qt_result_rendered:
                self.log("🖼️ 최종화면 동기화 기준으로 최종 이미지 재저장")

            if not qt_result_rendered:
                _progress(4, detail="최종 이미지를 재구성 렌더링하는 중입니다.")
                qt_result_rendered = self.render_final_result_image_qt(result_path, export_bg, curr.get('final_paint_above'))
                if qt_result_rendered:
                    self.log("🖼️ 최종 이미지 Qt 재구성 렌더 기준으로 재저장")

            # 텍스트 위 페인팅 레이어는 텍스트 렌더링 이후 최종 PNG 위에 다시 합성한다.
            # 단, Qt 렌더가 성공한 경우에는 위 페인팅까지 함께 렌더했으므로 중복 합성하지 않는다.
            if curr.get('final_paint_above') and (not qt_result_rendered) and os.path.exists(result_path):
                _progress(5, detail="텍스트 위 페인팅을 합성하는 중입니다.")
                try:
                    result_img = cv2.imdecode(np.fromfile(result_path, np.uint8), cv2.IMREAD_COLOR)
                    if result_img is not None:
                        result_img = self.compose_final_paint_on_bgr(result_img, curr.get('final_paint_above'))
                        self.save_bgr_image_for_output(result_img, result_path)
                except Exception as e:
                    self.log(f"⚠️ 텍스트 위 페인팅 출력 합성 실패: {e}")

            _progress(6, detail="출력 완료")
            self.log(f"✅ 스크립트 저장: {p}")
            self.log(f"🖼️ 최종 이미지 저장: {result_path}")
            if autosave and not bool(getattr(self, "_batch_export_streaming", False)):
                self.auto_save_project()
        finally:
            if single_progress:
                try:
                    QTimer.singleShot(350, self.hide_task_progress_overlay)
                except Exception:
                    try:
                        self.hide_task_progress_overlay()
                    except Exception:
                        pass

    def macro_batch_page_selection(self):
        """매크로 실행 시작 시 1회 선택한 일괄 작업 페이지 범위를 반환한다."""
        if not getattr(self, "macro_running", False):
            return None, None
        indices = getattr(self, "_macro_batch_page_indices", None)
        if not isinstance(indices, (list, tuple)):
            return None, None
        valid = []
        seen = set()
        for raw in indices:
            try:
                i = int(raw)
            except Exception:
                continue
            if 0 <= i < len(self.paths) and i not in seen:
                valid.append(i)
                seen.add(i)
        if not valid:
            return None, None
        label = str(getattr(self, "_macro_batch_page_label", "") or self.tr_ui("전체 맵"))
        return valid, label

    def choose_batch_page_indices_for_context(self, title, mode, *, default_all=False):
        """일반 실행은 페이지 선택창을 먼저 띄우고, 매크로 실행 중에는 공통 사전 선택값을 재사용한다."""
        try:
            if getattr(self, "macro_running", False):
                ctx = self.macro_batch_preflight_context_for_mode(mode) if hasattr(self, "macro_batch_preflight_context_for_mode") else {}
                if isinstance(ctx, dict):
                    indices = ctx.get("indices")
                    if isinstance(indices, (list, tuple)):
                        valid = []
                        seen = set()
                        for raw in indices:
                            try:
                                i = int(raw)
                            except Exception:
                                continue
                            if 0 <= i < len(self.paths) and i not in seen:
                                valid.append(i)
                                seen.add(i)
                        if valid:
                            label = str(ctx.get("label") or self.tr_ui("전체 맵"))
                            self.log(f"🧩 [Macro] 일괄 맵 범위 재사용: {title} / {label} / {len(valid)}페이지")
                            return valid, label
        except Exception:
            pass
        macro_indices, macro_label = self.macro_batch_page_selection()
        if macro_indices is not None:
            self.log(f"🧩 [Macro] 일괄 맵 범위 재사용: {title} / {macro_label} / {len(macro_indices)}페이지")
            return macro_indices, macro_label
        if default_all:
            return list(range(len(self.paths))), self.tr_ui("전체 맵")
        return self.choose_batch_page_indices(title, mode)

    def confirm_batch_operation(self, title, detail=None):
        # 매크로 안에 포함된 일괄 작업은 run_macro()에서 최초 1회만 확인한다.
        # 중간 단계마다 확인창이 뜨면 자동화 흐름이 끊기므로 여기서는 통과시킨다.
        if getattr(self, "macro_running", False):
            return True

        message = detail or f"{title}을(를) 실행할까요?"
        return QMessageBox.question(
            self,
            self.tr_msg(title),
            self.tr_msg(message),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes


    # ------------------------------------------------------------------
    # Batch job UX/policy helpers (QA7)
    # ------------------------------------------------------------------
    def batch_start_preview_delay_ms(self):
        """일괄 작업 시작 전 대상 페이지 수를 확인할 수 있게 최소 표시 시간을 둔다."""
        return 750

    def batch_mode_title(self, mode):
        return {
            "analyze": "일괄 분석",
            "reanalyze": "일괄 재분석",
            "translate": "일괄 번역",
            "inpaint": "일괄 인페인팅",
            "export": "일괄 출력",
            "extract_text": "일괄 원문/번역문 내보내기",
            "import_translation": "번역문 불러오기",
            "clear_translation": "일괄 번역문 내용 지우기",
            "clean_text": "일괄 텍스트 정리",
            "auto_text_size": "일괄 자동 텍스트 크기 조정",
            "auto_linebreak": "일괄 자동 줄 내림",
            "reset_text_rects": "일괄 현재 텍스트 기준으로 영역 재설정",
            "refresh": "일괄 텍스트 갱신",
        }.get(str(mode or ""), "일괄 작업")

    def batch_page_display_label(self, page_idx):
        try:
            page_no = int(page_idx) + 1
        except Exception:
            page_no = 0
        name = ""
        try:
            if 0 <= int(page_idx) < len(self.paths):
                name = os.path.basename(str(self.paths[int(page_idx)] or ""))
        except Exception:
            name = ""
        try:
            if hasattr(self, "_is_database_page_index") and self._is_database_page_index(page_idx):
                return self._database_tab_label_for_page(page_idx) if hasattr(self, "_database_tab_label_for_page") else f"DB_{page_no:03d}"
        except Exception:
            pass
        if not name:
            name = f"Map{page_no:03d}"
        return f"{page_no} - {name}"

    def wait_for_batch_preview(self, delay_ms=None):
        try:
            QApplication.processEvents()
            loop = QEventLoop()
            QTimer.singleShot(int(delay_ms or self.batch_start_preview_delay_ms()), loop.quit)
            loop.exec()
            QApplication.processEvents()
        except Exception:
            pass

    def _batch_result_new(self, title, mode, page_indices, page_label=""):
        return {
            "title": str(title or self.batch_mode_title(mode)),
            "mode": str(mode or "batch"),
            "page_label": str(page_label or ""),
            "total": len(page_indices or []),
            "done": [],
            "skipped": [],
            "failed": [],
            "pending": list(page_indices or []),
            "cancelled": False,
            "messages": [],
        }

    def _batch_result_record(self, page_idx, status="done", message=""):
        result = getattr(self, "_batch_result", None)
        if not isinstance(result, dict):
            return
        try:
            if page_idx in result.get("pending", []):
                result["pending"] = [x for x in result.get("pending", []) if x != page_idx]
        except Exception:
            pass
        status = str(status or "done").lower()
        if status not in ("done", "skipped", "failed"):
            status = "done"
        entry = {"index": page_idx, "label": self.batch_page_display_label(page_idx), "message": str(message or "")}
        result.setdefault(status, []).append(entry)
        if message:
            result.setdefault("messages", []).append(entry)

    def _batch_summary_text(self, result=None):
        result = result if isinstance(result, dict) else getattr(self, "_batch_result", {}) or {}
        title = str(result.get("title") or "일괄 작업")
        total = int(result.get("total") or 0)
        done = len(result.get("done") or [])
        skipped = len(result.get("skipped") or [])
        failed = len(result.get("failed") or [])
        pending = len(result.get("pending") or [])
        cancelled = bool(result.get("cancelled"))
        state = "취소됨" if cancelled else ("완료" if failed <= 0 else "완료(일부 실패)")
        lines = [
            f"{title} {state}",
            "",
            f"대상 페이지: {total}개",
            f"완료: {done}개",
            f"건너뜀: {skipped}개",
            f"실패: {failed}개",
            f"미처리: {pending}개",
        ]
        failed_items = result.get("failed") or []
        skipped_items = result.get("skipped") or []
        if failed_items:
            lines.append("")
            lines.append("실패한 페이지:")
            for item in failed_items[:8]:
                msg = item.get("message") or "오류"
                lines.append(f"- {item.get('label')}: {msg}")
            if len(failed_items) > 8:
                lines.append(f"- 외 {len(failed_items) - 8}개")
        if skipped_items:
            lines.append("")
            lines.append("건너뛴 페이지:")
            for item in skipped_items[:6]:
                msg = item.get("message") or "조건 없음"
                lines.append(f"- {item.get('label')}: {msg}")
            if len(skipped_items) > 6:
                lines.append(f"- 외 {len(skipped_items) - 6}개")
        lines.append("")
        lines.append("자세한 내용은 로그에서 확인할 수 있습니다.")
        return "\n".join(lines)

    def show_batch_result_summary(self, result=None):
        result = result if isinstance(result, dict) else getattr(self, "_batch_result", None)
        if not isinstance(result, dict):
            return
        try:
            if getattr(self, "macro_running", False) and hasattr(self, "macro_collect_batch_result"):
                if self.macro_collect_batch_result(result):
                    return
        except Exception:
            pass
        title = str(result.get("title") or "일괄 작업")
        text = self._batch_summary_text(result)
        try:
            if result.get("failed"):
                QMessageBox.warning(self, self.tr_ui(title), self.tr_msg(text))
            else:
                QMessageBox.information(self, self.tr_ui(title), self.tr_msg(text))
        except Exception:
            pass

    def batch_log_undo_boundary(self, reason):
        try:
            self.log(f"🧱 [Batch] Undo/Redo 스택 정리: {reason}")
        except Exception:
            pass
        try:
            self.undo_apply_boundary(f"batch_{reason}", "일괄 작업")
        except Exception:
            try:
                self.undo_clear_all_pages(reason=f"batch: {reason}")
            except Exception:
                pass

    def batch_prepare_progress(self, title, page_indices, page_label="", cancellable=True, start_delay=True):
        total = len(page_indices or [])
        lines = [f"대상 페이지: {total}개"]
        if page_label:
            lines[0] += f" ({page_label})"
        lines.extend([
            f"선택 페이지 진행: 0/{total}",
            "현재 페이지: 대기 중",
            "완료 0 / 건너뜀 0 / 실패 0",
            "잠시 후 작업을 시작합니다." if start_delay else "작업을 바로 시작합니다.",
        ])
        detail = "\n".join(lines)
        self.show_task_progress_overlay(title, detail, total=total, cancellable=cancellable)
        self.update_task_progress_overlay(current=0, total=total, detail=detail)
        try:
            QApplication.processEvents()
        except Exception:
            pass

    def batch_progress_detail(self, prefix, current, total, page_idx=None, extra=""):
        lines = [f"선택 페이지 진행: {current}/{total}"]
        if page_idx is not None:
            lines.append(f"현재 페이지: {self.batch_page_display_label(page_idx)}")
        else:
            lines.append("현재 페이지: 대기 중")
        done = len((getattr(self, "_batch_result", {}) or {}).get("done") or [])
        skipped = len((getattr(self, "_batch_result", {}) or {}).get("skipped") or [])
        failed = len((getattr(self, "_batch_result", {}) or {}).get("failed") or [])
        lines.append(f"완료 {done} / 건너뜀 {skipped} / 실패 {failed}")
        if extra:
            lines.append(str(extra))
        return "\n".join(lines)

    def run_page_queue_batch(self, title, mode, page_indices, page_label, page_func, *, visual=False, cancellable=True, restore_page=True, save_work_cache=True):
        """빠른 일괄 데이터 작업을 공통 페이지 큐로 실행한다.

        page_func(page_idx)는 (status, message) 또는 status 문자열을 반환한다.
        status: done / skipped / failed
        """
        if getattr(self, "is_batch_running", False):
            QMessageBox.information(self, self.tr_ui("일괄 작업 중"), self.tr_msg("이미 일괄 작업이 진행 중입니다.\n현재 작업이 끝난 뒤 다시 실행해 주세요."))
            return None
        indices = []
        seen = set()
        for raw in page_indices or []:
            try:
                i = int(raw)
            except Exception:
                continue
            if 0 <= i < len(self.paths) and i not in seen:
                indices.append(i)
                seen.add(i)
        if not indices:
            self.log(f"⚠️ {title}: 작업할 페이지가 없습니다.")
            return None

        old_idx = int(getattr(self, "idx", 0) or 0)
        old_mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 0
        result = self._batch_result_new(title, mode, indices, page_label)
        self._batch_result = result
        self._long_task_cancel_requested = False
        self.is_batch_running = True
        self.current_batch_mode = mode
        self.begin_busy_state(title)
        self.set_project_action_interlock(True)
        self.batch_log_undo_boundary("start")
        # visual=True인 분석/번역/인페인팅/출력류는 사용자가 처리 화면을 확인할 수 있도록
        # 시작 전 짧은 미리보기 시간을 둔다. 번역문 불러오기/텍스트 정리/자동 줄내림처럼
        # 화면 확인이 필요 없는 데이터 일괄 작업은 이 대기 시간을 건너뛴다.
        self.batch_prepare_progress(title, indices, page_label, cancellable=cancellable, start_delay=bool(visual))
        self.log(f"▶️ [Batch] {title} 시작: 대상 {len(indices)}개 ({page_label})")
        if visual:
            self.wait_for_batch_preview()
        else:
            try:
                QApplication.processEvents()
            except Exception:
                pass
        total = len(indices)
        completed = 0
        data_only = not bool(visual)
        # O단계: 데이터형 일괄 작업은 화면 없는 순차 처리로 유지한다.
        # 페이지를 실제로 넘기지 않고 data만 한 페이지씩 수정하며,
        # Undo는 일괄 작업 시작/종료 경계에서만 끊는다. 매 페이지마다
        # work cache 저장/Undo 경계/진행창 강제 갱신을 반복하면 300+장
        # 프로젝트에서 체감 속도가 크게 떨어진다.
        data_progress_interval = 5
        heavy_data_modes = {"import_clean_background", "use_background_as_source", "restore_original_source"}
        data_checkpoint_interval = None if str(mode or "") in heavy_data_modes else 25
        heavy_cleanup_interval = 3 if str(mode or "") == "import_clean_background" else 10
        data_changed_since_checkpoint = False
        try:
            for order, page_idx in enumerate(indices, 1):
                if bool(getattr(self, "_long_task_cancel_requested", False)):
                    result["cancelled"] = True
                    break
                try:
                    if (not data_only) or order == 1 or (order - 1) % data_progress_interval == 0:
                        self.update_task_progress_overlay(current=completed, total=total, detail=self.batch_progress_detail(title, completed, total, page_idx, "페이지 작업 중..."))
                    if visual:
                        self.show_batch_page_progress(page_idx, mode=mode, finished=False)
                    self.log(f"[Batch] 처리 시작: {order}/{total} - {self.batch_page_display_label(page_idx)}")
                    ret = page_func(page_idx)
                    if isinstance(ret, tuple):
                        status = ret[0] if len(ret) > 0 else "done"
                        message = ret[1] if len(ret) > 1 else ""
                    else:
                        status = ret or "done"
                        message = ""
                    self._batch_result_record(page_idx, status=status, message=message)
                    if str(status or "").lower() == "done":
                        data_changed_since_checkpoint = True
                    self.log(f"[Batch] 처리 {status}: {order}/{total} - {self.batch_page_display_label(page_idx)} {message or ''}".rstrip())
                except Exception as e:
                    self._batch_result_record(page_idx, status="failed", message=str(e))
                    self.log(f"[Batch] 처리 실패: {order}/{total} - {self.batch_page_display_label(page_idx)} - {e}")
                completed += 1

                if data_only:
                    # 데이터 작업은 페이지마다 디스크 저장하지 않고, 일정 단위로만 체크포인트 저장한다.
                    # 단, 클린본 불러오기처럼 이미지가 큰 작업은 일반 ProjectStore 저장 대신
                    # pending clean import 캐시를 쓰므로 여기서는 작업 캐시 저장을 건너뛴다.
                    if (
                        save_work_cache
                        and data_checkpoint_interval
                        and data_changed_since_checkpoint
                        and (completed % data_checkpoint_interval == 0 or completed >= total)
                    ):
                        try:
                            self.save_to_work_cache()
                            self.has_unsaved_changes = True
                            data_changed_since_checkpoint = False
                        except Exception as e:
                            self.log(f"⚠️ [Batch] 작업 캐시 체크포인트 저장 실패: {e}")
                else:
                    if save_work_cache:
                        try:
                            self.save_to_work_cache()
                            self.has_unsaved_changes = True
                        except Exception as e:
                            self.log(f"⚠️ [Batch] 작업 캐시 저장 실패: {e}")

                # 이미지 대량 데이터 작업은 페이지 처리 후 지역/Qt 캐시를 주기적으로 비운다.
                # 클린본 교체는 기존/신규 이미지가 겹치는 순간이 생길 수 있어 더 짧은 주기로 비운다.
                if data_only and str(mode or "") in heavy_data_modes and (completed % heavy_cleanup_interval == 0 or completed >= total):
                    try:
                        QPixmapCache.clear()
                    except Exception:
                        pass
                    try:
                        __import__("gc").collect()
                    except Exception:
                        pass

                # 일괄 작업은 작업 단위 자체가 Undo 경계다. 매 페이지마다 Undo를 다시 끊지 않는다.
                if (not data_only) or completed == total or completed % data_progress_interval == 0:
                    self.update_task_progress_overlay(current=completed, total=total, detail=self.batch_progress_detail(title, completed, total, page_idx, "페이지 작업 완료"))
                # 진행 UI는 QTimer 지연 갱신으로 처리한다.
                # 여기서 processEvents()를 호출하면 queued batch 신호가 현재 스택으로 재진입할 수 있다.
        finally:
            if data_only and save_work_cache and data_changed_since_checkpoint:
                try:
                    self.save_to_work_cache()
                    self.has_unsaved_changes = True
                except Exception as e:
                    self.log(f"⚠️ [Batch] 최종 작업 캐시 저장 실패: {e}")
            if restore_page and self.paths:
                try:
                    self.idx = max(0, min(old_idx, len(self.paths) - 1))
                    self.load()
                    if hasattr(self, "cb_mode") and 0 <= old_mode < self.cb_mode.count():
                        if self.cb_mode.currentIndex() != old_mode:
                            self.cb_mode.setCurrentIndex(old_mode)
                        else:
                            self.mode_chg(old_mode)
                except Exception:
                    pass
            self.batch_log_undo_boundary("finish")
            self.is_batch_running = False
            self.current_batch_mode = None
            self._active_task_worker = None
            self._batch_total = None
            self._batch_current_page_idx = None
            self.set_project_action_interlock(False)
            self.end_busy_state(title)
            try:
                self.hide_task_progress_overlay()
            except Exception:
                pass
            summary = self._batch_summary_text(result)
            self.log(summary.replace("\n", " | "))
            self.show_batch_result_summary(result)
        return result

    def release_batch_export_page_memory(self, page_index=None):
        """대용량 일괄 출력용 페이지 단위 메모리 정리.

        일괄 출력은 현재 화면과 같은 Qt 렌더 경로를 사용하므로, 한 페이지를 출력할 때마다
        QGraphicsScene/QImage/QPixmap/PIL/NumPy 참조가 여러 단계로 생길 수 있다.
        저장이 끝난 페이지는 즉시 화면 씬과 임시 레이어 참조를 비우고 Qt pixmap cache와
        Python GC를 돌려 다음 맵가 이전 맵 객체를 끌고 가지 않게 한다.
        """
        try:
            if not bool(getattr(self, "_batch_export_streaming", False)):
                return

            # 예약된 원본 비교창 동기화가 resize/paint 이후 늦게 실행되며 이미지를 다시 잡는 것을 막는다.
            try:
                self._source_compare_sync_pending = False
                self._source_compare_reverse_sync_pending = False
                if hasattr(self, "_block_source_compare_sync_temporarily"):
                    self._block_source_compare_sync_temporarily(180)
            except Exception:
                pass

            view = getattr(self, "view", None)
            try:
                if view is not None:
                    # 출력 직후 다음 맵를 다시 load()할 것이므로 현재 작업 씬은 비워도 된다.
                    scene = getattr(view, "scene", None)
                    if scene is not None:
                        try:
                            scene.clear()
                        except Exception:
                            pass
                    for attr in (
                        "final_paint_item", "final_paint_above_item",
                        "final_paint_img", "final_paint_above_img",
                        "user_mask_item", "user_mask_img",
                        "paste_preview_item", "magic_wand_preview_item",
                        "mask_wrap_preview_item", "mask_cut_preview_item",
                        "ocr_region_preview_item", "quick_ocr_preview_item",
                    ):
                        try:
                            setattr(view, attr, None)
                        except Exception:
                            pass
            except Exception:
                pass

            # 클론창은 열린 상태를 유지하되, 일괄 출력 중 불필요하게 되살아나는 sync 예약만 비운다.
            try:
                if hasattr(self, "source_compare_quick_ocr_preview_item"):
                    self.source_compare_quick_ocr_preview_item = None
            except Exception:
                pass

            try:
                QPixmapCache.clear()
            except Exception:
                pass
            # 여기서 processEvents()를 돌리면 scene.clear()가 먼저 화면에 반영되어
            # 일괄 출력 진행창 뒤로 검은 화면이 번쩍이는 문제가 생긴다.
            # 캐시는 비우되 실제 화면 갱신은 다음 맵 load()/진행창 update 타이밍에 맡긴다.
            gc.collect()
        except Exception as e:
            try:
                self.log(f"⚠️ 일괄 출력 페이지 메모리 정리 실패: {e}")
            except Exception:
                pass

    def run_batch_export_preview_sync(self, title="일괄 출력", page_indices=None, page_label=None):
        """일괄 출력도 개별 출력과 같은 최종화면(QGraphicsScene) 렌더 경로를 사용한다.

        기존 UniversalBatchWorker의 export 모드는 워커 스레드에서 engine.export_project_result()만 호출했다.
        그 경로는 data/PIL 기준 재구성 렌더라서, 최종결과 탭에 실제로 보이는 Qt 조판 화면과
        줄바꿈/기준선/변형 위치가 어긋날 수 있다. Qt 위젯/scene 렌더는 메인 스레드에서만 안전하므로
        일괄 출력만 메인 스레드 루프로 처리한다.
        """
        if not self.paths:
            self.log("⚠️ 파일 없음")
            return

        selected_indices = []
        seen = set()
        source_indices = page_indices if page_indices is not None else range(len(self.paths))
        for raw in source_indices:
            try:
                i = int(raw)
            except Exception:
                continue
            if 0 <= i < len(self.paths) and i not in seen:
                selected_indices.append(i)
                seen.add(i)
        if not selected_indices:
            self.log("⚠️ 출력할 페이지가 없습니다.")
            return

        old_idx = int(getattr(self, "idx", 0) or 0)
        old_mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 0
        old_batch_mode = getattr(self, "current_batch_mode", None)
        old_streaming = bool(getattr(self, "_batch_export_streaming", False))
        total = len(selected_indices)
        ok_count = 0
        fail_count = 0
        self._batch_result = self._batch_result_new(title, "export", selected_indices, page_label or self.tr_ui('전체 맵'))
        self._long_task_cancel_requested = False

        try:
            self.commit_current_page_ui_to_data()
        except Exception:
            pass

        export_ctx = self.macro_batch_preflight_context_for_mode("export") if hasattr(self, "macro_batch_preflight_context_for_mode") else {}
        if getattr(self, "macro_running", False) and (
            bool((export_ctx or {}).get("export_options_confirmed"))
            or bool(getattr(self, "_macro_preflight_export_options_confirmed", False))
        ):
            try:
                self.log("🧩 [Macro] 출력 옵션 재사용")
            except Exception:
                pass
        else:
            if not self.open_output_options_dialog():
                try:
                    self.log("↩️ 일괄 출력 취소")
                except Exception:
                    pass
                return

        self.is_batch_running = True
        self._batch_export_streaming = True
        self.current_batch_mode = "export"
        self.begin_busy_state(title)
        self.set_project_action_interlock(True)
        self.batch_log_undo_boundary("start")
        self.batch_prepare_progress(title, selected_indices, page_label or self.tr_ui('전체 맵'), cancellable=True)
        self.log(f"📦 [Batch] 대용량 일괄 출력 모드: {total}/{len(self.paths)}페이지 ({page_label or self.tr_ui('전체 맵')})")

        def _keep_export_progress_on_top():
            try:
                overlay = getattr(self, "_task_progress_overlay", None)
                if overlay is not None and overlay.isVisible():
                    overlay.raise_()
            except Exception:
                pass

        # 일괄 출력은 실제 최종결과 탭 렌더를 사용하지만, 매 페이지마다
        # 작업 탭 ↔ 최종결과 탭을 왕복하면 진행창 뒤 화면이 계속 번쩍인다.
        # 시작 시 한 번 최종결과 탭으로 고정하고, 끝날 때 원래 탭으로 복귀한다.
        try:
            if hasattr(self, "cb_mode") and self.cb_mode.currentIndex() != 4:
                self.cb_mode.blockSignals(True)
                try:
                    self.cb_mode.setCurrentIndex(4)
                finally:
                    self.cb_mode.blockSignals(False)
        except Exception:
            pass

        self.wait_for_batch_preview()
        _keep_export_progress_on_top()

        try:
            for seq_no, i in enumerate(selected_indices):
                if bool(getattr(self, "_long_task_cancel_requested", False)):
                    try:
                        self._batch_result["cancelled"] = True
                    except Exception:
                        pass
                    self.log("⏹️ 일괄 출력 취소 요청으로 중단")
                    break
                if i >= len(self.paths):
                    continue
                path = self.paths[i]
                base_name = os.path.basename(str(path or f"page{i + 1:03d}.png"))
                prefix = f"[{seq_no + 1}/{total} | {i + 1}p]"
                try:
                    self._batch_total = total
                    self._batch_progress_done = seq_no
                    self._batch_current_page_idx = i
                    self.update_task_progress_overlay(current=seq_no, total=total, detail=self.batch_progress_detail(title, seq_no, total, i, f"출력 중: {base_name}"))
                    _keep_export_progress_on_top()
                    self.log(f"{prefix} 출력: {base_name}")
                    self.idx = i
                    self.ensure_page_source_path(i)
                    # 진행 중에는 최종결과 탭을 유지한다. load() 직후 진행창을 다시 올려
                    # 씬 재구성/검은 빈 화면이 진행창을 덮는 것처럼 보이지 않게 한다.
                    try:
                        if hasattr(self, "cb_mode") and self.cb_mode.currentIndex() != 4:
                            self.cb_mode.blockSignals(True)
                            self.cb_mode.setCurrentIndex(4)
                            self.cb_mode.blockSignals(False)
                    except Exception:
                        pass
                    self.load()
                    _keep_export_progress_on_top()
                    QApplication.processEvents()
                    _keep_export_progress_on_top()

                    # export_result() 내부에서 최종결과 탭을 실제로 그린 뒤 그 scene을 저장한다.
                    # 이 경로를 타야 개별 출력과 일괄 출력의 결과가 같은 렌더러를 사용한다.
                    # 일괄 출력에서는 800MB+ YSBG가 매 페이지마다 통째로 자동저장되지 않게 막고,
                    # 페이지 저장 직후 씬/이미지 캐시를 해제한다.
                    self.export_result(autosave=False, prompt_options=False)
                    ok_count += 1
                    self._batch_result_record(i, status="done", message="출력 완료")
                    self._batch_progress_done = seq_no + 1
                    self.update_task_progress_overlay(current=seq_no + 1, total=total, detail=self.batch_progress_detail(title, seq_no + 1, total, i, "출력 완료"))
                    _keep_export_progress_on_top()
                    QApplication.processEvents()
                    _keep_export_progress_on_top()
                except Exception as e:
                    fail_count += 1
                    self._batch_result_record(i, status="failed", message=str(e))
                    self.log(f"{prefix} ❌ 출력 에러: {e}")
                finally:
                    self.release_batch_export_page_memory(i)
                    _keep_export_progress_on_top()

            if fail_count:
                self.log(f"✅ 일괄 출력 완료: 성공 {ok_count}개 / 실패 {fail_count}개")
            else:
                self.log(f"✅ 일괄 출력 완료! ({ok_count}/{total})")
        finally:
            # 원래 보던 페이지/작업 탭으로 복귀한다. 복귀 과정은 사용자 편집이 아니므로
            # mode_chg()의 Undo/마스크 커밋 부작용을 막는다.
            try:
                if self.paths:
                    self.idx = max(0, min(old_idx, len(self.paths) - 1))
                    self.cb_mode.blockSignals(True)
                    try:
                        self.cb_mode.setCurrentIndex(max(0, min(old_mode, self.cb_mode.count() - 1)))
                    finally:
                        self.cb_mode.blockSignals(False)
                    old_suppress = bool(getattr(self, '_suppress_mode_undo', False))
                    old_skip = bool(getattr(self, '_skip_mode_mask_commit', False))
                    try:
                        self._suppress_mode_undo = True
                        self._skip_mode_mask_commit = True
                        self.load()
                    finally:
                        self._suppress_mode_undo = old_suppress
                        self._skip_mode_mask_commit = old_skip
            except Exception:
                pass

            try:
                gc.collect()
                QPixmapCache.clear()
            except Exception:
                pass
            try:
                self.save_to_work_cache()
                self.has_unsaved_changes = True
            except Exception:
                pass
            self.batch_log_undo_boundary("finish")
            self.is_batch_running = False
            self._batch_export_streaming = old_streaming
            self.current_batch_mode = old_batch_mode
            self._batch_total = None
            self._batch_progress_done = 0
            self._batch_current_page_idx = None
            self.set_project_action_interlock(False)
            self.end_busy_state(title)
            try:
                self.hide_task_progress_overlay()
            except Exception:
                pass
            try:
                self._export_rendering_guard = False
                self._suppress_shared_option_refresh = False
                if hasattr(self, "refresh_shared_option_bar"):
                    self.refresh_shared_option_bar()
            except Exception:
                pass
            try:
                result = getattr(self, "_batch_result", None)
                if isinstance(result, dict):
                    summary = self._batch_summary_text(result)
                    self.log(summary.replace("\n", " | "))
                    self.show_batch_result_summary(result)
            except Exception:
                pass
            self.macro_mark_current_step_done(self.macro_batch_key_for_mode("export"))

    def parse_batch_page_selection_text(self, text, total_pages):
        """사용자 입력(1-3, 1~3, 1,2,3)을 0-base 맵 인덱스 목록으로 변환한다."""
        raw = str(text or "").strip()
        if not raw:
            raise ValueError(self.tr_msg("맵 선택 값을 입력해 주세요."))
        if total_pages <= 0:
            raise ValueError(self.tr_msg("작업할 맵이 없습니다."))

        # 1 - 3 / 1 ~ 3처럼 공백이 들어간 범위도 허용한다.
        normalized = raw.replace("，", ",").replace("、", ",").replace("～", "~")
        normalized = re.sub(r"\s*([-~])\s*", r"\1", normalized)
        tokens = [t for t in re.split(r"[,\s]+", normalized) if t]
        if not tokens:
            raise ValueError(self.tr_msg("맵 선택 값을 입력해 주세요."))

        selected = set()
        for token in tokens:
            range_match = re.fullmatch(r"(\d+)([-~])(\d+)", token)
            single_match = re.fullmatch(r"\d+", token)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(3))
                if start > end:
                    start, end = end, start
                if start < 1 or end > total_pages:
                    raise ValueError(self.tr_msg("맵 범위가 프로젝트 맵 수를 벗어났습니다."))
                for page_no in range(start, end + 1):
                    selected.add(page_no - 1)
            elif single_match:
                page_no = int(token)
                if page_no < 1 or page_no > total_pages:
                    raise ValueError(self.tr_msg("맵 범위가 프로젝트 맵 수를 벗어났습니다."))
                selected.add(page_no - 1)
            else:
                raise ValueError(self.tr_msg("맵 선택 형식을 확인해 주세요."))

        if not selected:
            raise ValueError(self.tr_msg("작업할 맵이 없습니다."))
        return sorted(selected)

    def choose_batch_page_indices(self, title, mode):
        """일괄 작업 실행 전에 전체/지정 페이지 범위를 고른다.

        쯔꾸르붕이에서는 일반 모드와 데이터베이스 모드가 서로 다른 탭 집합을 쓴다.
        DB 모드에서 일괄 번역을 실행하면 실제 self.paths 전체가 아니라 현재 표시 중인
        DB 탭 목록(current_tab_page_indices)을 기준으로 선택 번호를 해석한다.
        """
        db_select_mode = False
        visible_indices = []
        try:
            db_select_mode = (
                str(mode or "") in {"translate", "unify_translations"}
                and hasattr(self, "is_maker_special_table_mode")
                and bool(self.is_maker_special_table_mode())
            )
        except Exception:
            db_select_mode = False
        if db_select_mode:
            plugin_select_mode = bool(hasattr(self, "is_maker_plugin_mode") and self.is_maker_plugin_mode())
            speaker_select_mode = bool(hasattr(self, "is_maker_speaker_mode") and self.is_maker_speaker_mode())
            try:
                visible_indices = list(self.current_tab_page_indices() or []) if hasattr(self, "current_tab_page_indices") else []
            except Exception:
                visible_indices = []
            if not visible_indices:
                try:
                    visible_indices = list(self.maker_database_page_indices() or []) if hasattr(self, "maker_database_page_indices") else []
                except Exception:
                    visible_indices = []
            visible_indices = [int(x) for x in visible_indices if 0 <= int(x) < len(self.paths)]
            total_pages = len(visible_indices)
            if plugin_select_mode:
                item_word = self.tr_ui("플러그인 페이지")
                all_label_text = self.tr_ui("전체 플러그인 페이지")
                selected_label_text = self.tr_ui("플러그인 페이지 선택")
                desc_text = self.tr_ui("작업할 플러그인 페이지 범위를 선택하세요.")
                note_text = self.tr_ui("쉼표와 범위를 섞어서 입력할 수 있습니다. 번호는 현재 플러그인 탭 순서 기준입니다.")
            elif speaker_select_mode:
                item_word = self.tr_ui("화자 페이지")
                all_label_text = self.tr_ui("전체 화자 페이지")
                selected_label_text = self.tr_ui("화자 페이지 선택")
                desc_text = self.tr_ui("작업할 화자 페이지 범위를 선택하세요.")
                note_text = self.tr_ui("쉼표와 범위를 섞어서 입력할 수 있습니다. 번호는 현재 화자 탭 순서 기준입니다.")
            else:
                item_word = self.tr_ui("DB 페이지")
                all_label_text = self.tr_ui("전체 DB 페이지")
                selected_label_text = self.tr_ui("DB 페이지 선택")
                desc_text = self.tr_ui("작업할 DB 페이지 범위를 선택하세요.")
                note_text = self.tr_ui("쉼표와 범위를 섞어서 입력할 수 있습니다. 번호는 현재 DB 탭 순서 기준입니다.")
            placeholder_text = self.tr_ui("예: 1-3, 1~3, 1,2,3")
        else:
            visible_indices = list(range(len(self.paths)))
            total_pages = len(visible_indices)
            item_word = self.tr_ui("맵")
            all_label_text = self.tr_ui("전체 맵")
            selected_label_text = self.tr_ui("맵 선택")
            desc_text = self.tr_ui("작업할 맵 범위를 선택하세요.")
            note_text = self.tr_ui("쉼표와 범위를 섞어서 입력할 수 있습니다.")
            placeholder_text = self.tr_ui("예: 1-3, 1~3, 1,2,3")
        if total_pages <= 0:
            return None, None

        include_current_page = (not db_select_mode) and str(mode or "") in {"use_background_as_source", "restore_original_source"}
        try:
            current_idx = int(getattr(self, "idx", 0) or 0)
        except Exception:
            current_idx = 0
        if current_idx < 0 or current_idx >= len(self.paths):
            current_idx = 0

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr_ui(title))
        dialog.setModal(True)
        dialog.resize(480, 220 if include_current_page else 190)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        desc = QLabel(desc_text, dialog)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        rb_current = QRadioButton(self.tr_ui("현재 맵"), dialog) if include_current_page else None
        rb_all = QRadioButton(all_label_text, dialog)
        rb_selected = QRadioButton(selected_label_text, dialog)
        if rb_current is not None:
            rb_current.setChecked(True)
        else:
            rb_all.setChecked(True)

        edit_pages = QLineEdit(dialog)
        edit_pages.setPlaceholderText(placeholder_text)
        edit_pages.setEnabled(False)

        selected_row = QHBoxLayout()
        selected_row.setContentsMargins(0, 0, 0, 0)
        selected_row.setSpacing(8)
        selected_row.addWidget(rb_selected)
        selected_row.addWidget(edit_pages, 1)

        if rb_current is not None:
            layout.addWidget(rb_current)
        layout.addWidget(rb_all)
        layout.addLayout(selected_row)

        note = QLabel(note_text, dialog)
        note.setWordWrap(True)
        note.setStyleSheet("color: #8ea0b8;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        try:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("취소"))
        except Exception:
            pass
        layout.addWidget(buttons)

        def sync_enabled():
            edit_pages.setEnabled(rb_selected.isChecked())
            if rb_selected.isChecked():
                edit_pages.setFocus()

        rb_selected.toggled.connect(sync_enabled)
        rb_all.toggled.connect(sync_enabled)
        if rb_current is not None:
            rb_current.toggled.connect(sync_enabled)

        if rb_current is not None:
            result = {"accepted": False, "indices": [current_idx], "label": self.tr_ui("현재 맵")}
        else:
            result = {"accepted": False, "indices": list(visible_indices), "label": all_label_text}

        def map_relative_indices(relative_indices):
            mapped = []
            seen = set()
            for raw in relative_indices:
                try:
                    pos = int(raw)
                    actual = int(visible_indices[pos])
                except Exception:
                    continue
                if actual not in seen:
                    mapped.append(actual)
                    seen.add(actual)
            return mapped

        def on_accept():
            try:
                if rb_current is not None and rb_current.isChecked():
                    result["indices"] = [current_idx]
                    result["label"] = self.tr_ui("현재 맵")
                elif rb_selected.isChecked():
                    rel_indices = self.parse_batch_page_selection_text(edit_pages.text(), total_pages)
                    indices = map_relative_indices(rel_indices)
                    if not indices:
                        raise ValueError(self.tr_msg(f"작업할 {item_word}이 없습니다."))
                    result["indices"] = indices
                    result["label"] = edit_pages.text().strip()
                else:
                    result["indices"] = list(visible_indices)
                    result["label"] = all_label_text
                result["accepted"] = True
                dialog.accept()
            except Exception as e:
                QMessageBox.warning(dialog, self.tr_ui("페이지 선택 오류" if db_select_mode else "맵 선택 오류"), str(e))

        buttons.accepted.connect(on_accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() != QDialog.DialogCode.Accepted or not result.get("accepted"):
            return None, None
        return result["indices"], result["label"]

    def run_batch(self, mode):
        if bool(getattr(self, "tktool_phase2_enabled", False)) and str(mode or "") != "translate":
            try:
                self.log(f"⛔ 쯔꾸르붕이에서는 지원하지 않는 일괄 작업입니다: {mode}")
            except Exception:
                pass
            return
        if getattr(self, "is_batch_running", False):
            QMessageBox.information(self, self.tr_ui("일괄 작업 중"), self.tr_msg("이미 일괄 작업이 진행 중입니다.\n현재 작업이 끝난 뒤 다시 실행해 주세요."))
            return
        if not self.ensure_engine_ready():
            return
        if not self.paths:
            self.log("⚠️ 파일 없음")
            return

        mode_names = {
            "analyze": "일괄 분석",
            "reanalyze": "일괄 재분석",
            "translate": "일괄 번역",
            "inpaint": "일괄 인페인팅",
            "refresh": "일괄 텍스트 갱신",
            "export": "일괄 출력",
        }
        title = mode_names.get(mode, "일괄 작업")

        if mode in ("analyze", "reanalyze"):
            if not self.check_ocr_api_or_alert():
                return
        if mode == "inpaint":
            if not self.check_inpaint_api_or_alert():
                return
        if mode == "translate":
            if not self.check_translation_api_key_or_alert(self.cb_trans_provider.currentData()):
                return
        selected_page_indices = list(range(len(self.paths)))
        selected_page_label = self.tr_ui("전체 맵")
        maker_db_batch = False
        try:
            maker_db_batch = bool(mode == "translate" and hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
        except Exception:
            maker_db_batch = False
        if mode in ("analyze", "reanalyze", "translate", "inpaint", "export", "refresh"):
            selected_page_indices, selected_page_label = self.choose_batch_page_indices_for_context(title, mode)
            if selected_page_indices is None:
                self.log(f"↩️ {title} 취소")
                return
            if mode == "translate" and maker_db_batch and not selected_page_indices:
                plugin_mode = bool(hasattr(self, "is_maker_plugin_mode") and self.is_maker_plugin_mode())
                speaker_mode = bool(hasattr(self, "is_maker_speaker_mode") and self.is_maker_speaker_mode())
                if plugin_mode:
                    empty_message = "플러그인 번역 모드에서 번역할 플러그인 페이지가 없습니다."
                elif speaker_mode:
                    empty_message = "화자 번역 모드에서 번역할 화자 페이지가 없습니다."
                else:
                    empty_message = "데이터베이스 모드에서 번역할 DB 페이지가 없습니다."
                self.show_warn_notice("일괄 번역", empty_message)
                return
            if mode == "analyze":
                analyze_ctx = self.macro_batch_preflight_context_for_mode(mode) if hasattr(self, "macro_batch_preflight_context_for_mode") else {}
                if getattr(self, "macro_running", False) and (
                    bool((analyze_ctx or {}).get("ocr_regions_confirmed"))
                    or bool(getattr(self, "_macro_preflight_ocr_regions_confirmed", False))
                ):
                    try:
                        self.log("🧩 [Macro] OCR 분석 영역 확인값 재사용")
                    except Exception:
                        pass
                elif not self.confirm_ocr_analysis_regions_before_run(selected_page_indices):
                    self.log(f"↩️ {title} 취소")
                    return
        else:
            if getattr(self, "ui_language", LANG_KO) == LANG_EN:
                batch_message = f"Run {self.tr_ui(title)} on total {len(self.paths)} page(s)?"
            else:
                batch_message = f"{title}을(를) 총 {len(self.paths)}페이지에 실행합니다."
            if not self.confirm_batch_operation(title, batch_message):
                self.log(f"↩️ {title} 취소")
                return

        # 일괄 시작 전 현재 페이지의 UI 상태를 한 번만 확정한다.
        # 일괄 분석은 일반 분석과 동일하게 기존 마스크를 무시하고 새로 따야 하므로
        # 현재 화면 마스크를 데이터에 다시 저장하지 않는다.
        # 일괄 재분석은 현재 텍스트 마스크를 기준으로 하므로 반드시 마스크를 확정한다.
        self.commit_current_page_ui_to_data(include_mask=(mode != "analyze"))
        self.auto_save_project()

        self._batch_inpaint_resize_policy = None
        if mode == "inpaint":
            inpaint_ctx = self.macro_batch_preflight_context_for_mode(mode) if hasattr(self, "macro_batch_preflight_context_for_mode") else {}
            if getattr(self, "macro_running", False) and (
                bool((inpaint_ctx or {}).get("inpaint_resize_checked"))
                or bool(getattr(self, "_macro_preflight_inpaint_resize_checked", False))
            ):
                policy = (inpaint_ctx or {}).get("inpaint_resize_policy", None)
                if not isinstance(policy, dict):
                    policy = getattr(self, "_macro_preflight_inpaint_resize_policy", None)
                self._batch_inpaint_resize_policy = copy.deepcopy(policy) if isinstance(policy, dict) else None
                try:
                    self.log("🧩 [Macro] 인페인팅 리사이즈 정책 재사용")
                except Exception:
                    pass
            else:
                if not self._ask_batch_inpaint_resize(selected_page_indices):
                    self.log(f"↩️ {title} 취소")
                    return
        try:
            self._batch_return_page_idx = int(self.idx)
            self._batch_return_mode_idx = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else 0
            self._batch_return_database_idx = int(getattr(self, "maker_database_idx", self.idx) or self.idx)
        except Exception:
            self._batch_return_page_idx = int(getattr(self, "idx", 0) or 0)
            self._batch_return_mode_idx = 0
            self._batch_return_database_idx = int(getattr(self, "maker_database_idx", getattr(self, "idx", 0)) or 0)

        if mode == "export":
            self.run_batch_export_preview_sync(title, page_indices=selected_page_indices, page_label=selected_page_label)
            return

        try:
            self._maker_database_batch_translate_active = bool(mode == "translate" and maker_db_batch)
        except Exception:
            self._maker_database_batch_translate_active = False
        self.is_batch_running = True
        self.current_batch_mode = mode
        self._batch_progress_done = 0
        self._batch_total = len(selected_page_indices)
        self._long_task_cancel_requested = False
        self._batch_result = self._batch_result_new(title, mode, selected_page_indices, selected_page_label)
        self.begin_busy_state(title)
        self.set_project_action_interlock(True)
        self.batch_log_undo_boundary("start")
        self.batch_prepare_progress(title, selected_page_indices, selected_page_label, cancellable=True)

        self.log(f"▶️ [Batch] {title} 시작: {len(selected_page_indices)}/{len(self.paths)}페이지 ({selected_page_label})")
        self.wait_for_batch_preview()
        if bool(getattr(self, "_long_task_cancel_requested", False)):
            try:
                self._batch_result["cancelled"] = True
            except Exception:
                pass
            self.on_batch_finished(mode)
            return
        self.start_universal_batch_worker(mode, selected_page_indices)

    def _start_batch_job(self, mode=""):
        job_id = uuid.uuid4().hex
        self._active_batch_job_id = job_id
        self._active_batch_mode = str(mode or "")
        try:
            canceled = getattr(self, "_canceled_batch_job_ids", None)
            if not isinstance(canceled, set):
                canceled = set()
            self._canceled_batch_job_ids = canceled
        except Exception:
            self._canceled_batch_job_ids = set()
        return job_id

    def _is_active_batch_job(self, job_id):
        if not job_id:
            return True
        # 취소된 현재 batch도 finished_all은 UI 정리를 위해 받아야 한다.
        # 따라서 여기서는 "현재 batch id와 같은가"만 본다.  취소 여부에
        # 따른 payload 폐기는 on_batch_item_finished의 cancel guard가 맡고,
        # 새 batch가 시작된 뒤 늦게 도착한 이전 신호만 여기서 차단한다.
        return str(getattr(self, "_active_batch_job_id", "") or "") == str(job_id)

    def _cancel_active_batch_job(self, reason="user_cancel"):
        job_id = str(getattr(self, "_active_batch_job_id", "") or "")
        if job_id:
            try:
                canceled = getattr(self, "_canceled_batch_job_ids", None)
                if not isinstance(canceled, set):
                    canceled = set()
                canceled.add(job_id)
                self._canceled_batch_job_ids = canceled
            except Exception:
                pass
        try:
            worker = getattr(self, "bw", None)
            if worker is not None and hasattr(worker, "stop"):
                worker.stop()
        except Exception:
            pass
        try:
            append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "UI BATCH JOB CANCELED", job_id=job_id, reason=str(reason or ""), memory=memory_text())
        except Exception:
            pass

    def _handle_batch_progress_for_job(self, job_id, msg):
        if not self._is_active_batch_job(job_id):
            return
        self.handle_long_task_message(msg)

    def _on_batch_item_started_for_job(self, job_id, i, mode=None):
        if not self._is_active_batch_job(job_id):
            try:
                append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "STALE BATCH ITEM START IGNORED", job_id=str(job_id or ""), index=i, mode=mode, memory=memory_text())
            except Exception:
                pass
            return
        return self.on_batch_item_started(i, mode)

    def _on_batch_item_finished_for_job(self, job_id, i, payload=None):
        if not self._is_active_batch_job(job_id):
            try:
                append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "STALE BATCH ITEM FINISH IGNORED", job_id=str(job_id or ""), index=i, memory=memory_text())
            except Exception:
                pass
            try:
                sender = self.sender()
                if sender is not None and hasattr(sender, "mark_item_applied"):
                    sender.mark_item_applied(i)
            except Exception:
                pass
            return
        return self.on_batch_item_finished(i, payload)

    def _on_batch_finished_for_job(self, job_id, mode):
        if not self._is_active_batch_job(job_id):
            try:
                append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "STALE BATCH FINISH IGNORED", job_id=str(job_id or ""), mode=mode, memory=memory_text())
            except Exception:
                pass
            return
        return self.on_batch_finished(mode)

    def start_universal_batch_worker(self, mode, selected_page_indices):
        batch_job_id = self._start_batch_job(mode)
        self.bw = UniversalBatchWorker(self, mode, page_indices=selected_page_indices)
        try:
            self.bw._ysb_batch_job_id = batch_job_id
        except Exception:
            pass
        self._active_task_worker = self.bw
        self.bw.progress.connect(lambda msg, job_id=batch_job_id: self._handle_batch_progress_for_job(job_id, msg))
        if hasattr(self.bw, "active_item"):
            self.bw.active_item.connect(lambda i, m, job_id=batch_job_id: self._on_batch_item_started_for_job(job_id, i, m))
        self.bw.finished_item.connect(lambda i, payload, job_id=batch_job_id: self._on_batch_item_finished_for_job(job_id, i, payload))
        self.bw.finished_all.connect(lambda job_id=batch_job_id, m=mode: self._on_batch_finished_for_job(job_id, m))
        self.bw.start()

    def batch_visual_mode_for(self, mode):
        return {
            "analyze": 1,
            "reanalyze": 1,
            "translate": 4,
            "inpaint": 4,
        }.get(str(mode or ""), self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 0)

    def show_batch_page_progress(self, page_index, mode=None, finished=False):
        """일괄 작업 화면 갱신을 즉시 실행하지 않고 한 번만 예약한다.

        worker finished/started 신호가 몰릴 때 이 함수 안에서 load()/processEvents()를
        즉시 실행하면, 대기 중인 batch 신호가 현재 call stack 안으로 다시 들어와
        show_batch_page_progress -> on_batch_item_finished -> show_batch_page_progress 형태의
        재진입이 발생할 수 있다. 따라서 최신 상태만 저장하고 실제 화면 갱신은
        다음 이벤트 루프로 미룬다.
        """
        try:
            page_index = int(page_index)
        except Exception:
            return
        if page_index < 0 or page_index >= len(getattr(self, "paths", []) or []):
            return
        self._pending_batch_page_progress = (page_index, mode, bool(finished))
        self._schedule_batch_page_progress_flush()

    def _schedule_batch_page_progress_flush(self, delay_ms=0):
        try:
            if bool(getattr(self, "_batch_page_progress_flush_scheduled", False)):
                return
            self._batch_page_progress_flush_scheduled = True
            QTimer.singleShot(int(delay_ms or 0), self._flush_batch_page_progress)
        except Exception:
            try:
                self._batch_page_progress_flush_scheduled = False
            except Exception:
                pass

    def _flush_batch_page_progress(self):
        """예약된 일괄 작업 화면 갱신을 1회 처리한다.

        이 함수 안에서는 QApplication.processEvents()를 절대 호출하지 않는다.
        processEvents()는 queued signal을 현재 stack 안으로 끌고 들어와 batch progress
        재귀/stack overflow를 만들 수 있다.
        """
        if bool(getattr(self, "_batch_page_progress_flush_active", False)):
            # load()/mode_chg 중 다시 들어오면 현재 flush가 끝난 뒤 한 번만 재시도한다.
            self._batch_page_progress_flush_scheduled = False
            self._schedule_batch_page_progress_flush(delay_ms=30)
            return

        pending = getattr(self, "_pending_batch_page_progress", None)
        self._pending_batch_page_progress = None
        self._batch_page_progress_flush_scheduled = False
        if not pending:
            return

        try:
            page_index, mode, finished = pending
        except Exception:
            return
        try:
            page_index = int(page_index)
        except Exception:
            return
        if page_index < 0 or page_index >= len(getattr(self, "paths", []) or []):
            return

        self._batch_page_progress_flush_active = True
        try:
            append_log(
                getattr(getattr(self, "bw", None), "batch_log_path", None),
                "UI SHOW PAGE FLUSH BEGIN",
                index=page_index,
                mode=mode,
                finished=finished,
                memory=memory_text(),
            )
            db_batch_progress = False
            try:
                db_batch_progress = (
                    str(mode or "") == "translate"
                    and bool(getattr(self, "_maker_database_batch_translate_active", False))
                    and hasattr(self, "_is_database_page_index")
                    and self._is_database_page_index(int(page_index))
                )
            except Exception:
                db_batch_progress = False
            if db_batch_progress:
                # DB batch progress must not use the normal load() path.  load() can
                # rebuild the shared table as a normal map/Maker table and then a
                # later DB UI commit may write those stale source cells into DB rows.
                # Show the DB page through the DB-view refresh path, with UI commit
                # suppressed; the worker payload remains the only data source.
                self.idx = int(page_index)
                self.maker_database_idx = int(page_index)
                target_mode = self.batch_visual_mode_for(mode)
                if hasattr(self, "cb_mode") and 0 <= target_mode < self.cb_mode.count():
                    if self.cb_mode.currentIndex() != target_mode:
                        self.cb_mode.setCurrentIndex(target_mode)
                old_suppress = bool(getattr(self, "_suppress_database_ui_commit", False))
                self._suppress_database_ui_commit = True
                try:
                    try:
                        pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else []
                        bar = getattr(self, "page_tab_bar", None)
                        if pages and int(page_index) in pages and bar is not None:
                            display_idx = pages.index(int(page_index))
                            old_refresh = bool(getattr(self, "_refreshing_page_tabs", False))
                            self._refreshing_page_tabs = True
                            try:
                                old_block = bar.blockSignals(True)
                                try:
                                    if bar.currentIndex() != display_idx:
                                        bar.setCurrentIndex(display_idx)
                                finally:
                                    bar.blockSignals(old_block)
                            finally:
                                self._refreshing_page_tabs = old_refresh
                    except Exception:
                        pass
                    if hasattr(self, "refresh_maker_database_view"):
                        self.refresh_maker_database_view()
                    if hasattr(self, "update_page_position_label_for_current_tab_layer"):
                        self.update_page_position_label_for_current_tab_layer()
                finally:
                    self._suppress_database_ui_commit = old_suppress
            else:
                self.idx = int(page_index)
                target_mode = self.batch_visual_mode_for(mode)
                if hasattr(self, "cb_mode") and 0 <= target_mode < self.cb_mode.count():
                    if self.cb_mode.currentIndex() != target_mode:
                        self.cb_mode.setCurrentIndex(target_mode)
                self.load()
            append_log(
                getattr(getattr(self, "bw", None), "batch_log_path", None),
                "UI SHOW PAGE FLUSH DONE",
                index=page_index,
                mode=mode,
                finished=finished,
                memory=memory_text(),
            )
        except Exception as e:
            append_log(
                getattr(getattr(self, "bw", None), "batch_log_path", None),
                "UI SHOW PAGE FLUSH EXCEPTION",
                index=page_index,
                mode=mode,
                finished=finished,
                error=repr(e),
                memory=memory_text(),
            )
            try:
                self.log(f"⚠️ 일괄 작업 화면 갱신 실패: {e}")
            except Exception:
                pass
        finally:
            self._batch_page_progress_flush_active = False
            # 처리 중 더 최신 페이지가 예약되었으면 다음 이벤트 루프에서 한 번만 이어 처리한다.
            if getattr(self, "_pending_batch_page_progress", None) is not None:
                self._schedule_batch_page_progress_flush(delay_ms=0)

    def on_batch_item_started(self, i, mode=None):
        append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "UI BATCH ITEM STARTED", index=i, mode=mode, memory=memory_text())
        try:
            self._batch_current_page_idx = int(i)
            done = int(getattr(self, "_batch_progress_done", 0) or 0)
            total = int(getattr(self, "_batch_total", len(self.paths)) or len(self.paths))
            self.update_task_progress_overlay(
                current=done,
                total=total,
                detail=self.batch_progress_detail(mode, done, total, i, "페이지 작업 중..."),
            )
        except Exception:
            pass
        self.show_batch_page_progress(i, mode=mode, finished=False)

    def on_batch_item_finished(self, i, payload=None):
        append_log(
            getattr(getattr(self, "bw", None), "batch_log_path", None),
            "UI BATCH ITEM FINISHED ENTER",
            index=i,
            payload_keys=list((payload or {}).keys()) if isinstance(payload, dict) else type(payload).__name__,
            memory=memory_text(),
        )
        payload_status = "done"
        payload_message = ""
        try:
            if isinstance(payload, dict):
                payload_status = str(payload.pop('_batch_status', 'done') or 'done')
                payload_message = str(payload.pop('_batch_message', '') or '')
        except Exception:
            payload_status = "done"
            payload_message = ""
        # 취소 확인 후 현재 맵의 API 응답이 늦게 돌아온 경우에는 UI/data에 반영하지 않는다.
        # 이미 이 함수에서 처리 완료되어 _batch_result.done에 기록된 이전 맵만 유지한다.
        try:
            if (
                str(getattr(self, "current_batch_mode", "") or "") == "translate"
                and bool(getattr(self, "_long_task_cancel_requested", False))
            ):
                try:
                    self.log(f"🗑️ 취소된 일괄 번역 응답 폐기: {self.batch_page_display_label(i)}")
                except Exception:
                    pass
                try:
                    if hasattr(getattr(self, "bw", None), "mark_item_applied"):
                        self.bw.mark_item_applied(i)
                except Exception:
                    pass
                return
        except Exception:
            pass

        # workers.py가 payload를 넘기는 새 구조와, main.data를 직접 갱신하는 구 구조를 모두 지원한다.
        # 일괄 중에는 self.load()를 호출하지 않는다. 화면에 남은 마스크가 다른 페이지에 저장될 수 있기 때문.
        if i < 0 or i >= len(self.paths):
            try:
                if hasattr(getattr(self, "bw", None), "mark_item_applied"):
                    self.bw.mark_item_applied(i)
            except Exception:
                pass
            return

        if i not in self.data:
            self.data[i] = {
                'ori': None,
                'data': [],
                'mask_merge': None,
                'mask_inpaint': None,
                'mask_merge_off': None,
                'mask_inpaint_off': None,
                'mask_toggle_enabled': False,
                'use_inpainted_as_source': False,
                'bg_clean': None,
                'clean_path': None,
                'working_source': None,
                'working_source_path': None,
                'final_paint': None,
                'final_paint_path': None,
                'final_paint_above': None,
                'final_paint_above_path': None,
                'ocr_analysis_regions': [],
            }

        if payload:
            curr = self.data[i]
            append_log(
                getattr(getattr(self, "bw", None), "batch_log_path", None),
                "UI PAYLOAD APPLY BEGIN",
                index=i,
                payload_keys=list(payload.keys()),
                ori=numpy_shape_text(payload.get('ori')),
                mask_merge=numpy_shape_text(payload.get('mask_merge')),
                mask_inpaint=numpy_shape_text(payload.get('mask_inpaint')),
                data_count=len(payload.get('data') or []) if isinstance(payload.get('data'), list) else 0,
                memory=memory_text(),
            )
            if getattr(self, "current_batch_mode", None) == "analyze" and curr.get('ocr_analysis_regions') and curr.get('data'):
                try:
                    md, mm, mi = self.merge_ocr_analysis_region_results(i, payload.get('data', []), payload.get('mask_merge'), payload.get('mask_inpaint'), ori_img=payload.get('ori'))
                    payload['data'] = md
                    payload['mask_merge'] = mm
                    payload['mask_inpaint'] = mi
                except Exception as e:
                    self.log(f"⚠️ 지정 영역 OCR 병합 실패: {e}")
            if getattr(self, "current_batch_mode", None) in ("analyze", "reanalyze"):
                try:
                    self.spill_payload_masks_to_disk(i, curr, payload)
                    append_log(
                        getattr(getattr(self, "bw", None), "batch_log_path", None),
                        "UI PAYLOAD MASK SPILL DONE",
                        index=i,
                        mask_merge_path=curr.get('mask_merge_path'),
                        mask_inpaint_path=curr.get('mask_inpaint_path'),
                        memory=memory_text(),
                    )
                except Exception as e:
                    self.log(f"⚠️ 일괄 분석 마스크 디스크 저장 실패: {e}")

            db_translate_payload = False
            try:
                db_translate_payload = (
                    getattr(self, "current_batch_mode", None) == "translate"
                    and (hasattr(self, "_is_database_page_index") and self._is_database_page_index(i))
                    and isinstance(payload.get("data"), list)
                )
            except Exception:
                db_translate_payload = False

            for key, value in payload.items():
                if key == 'ori' or str(key).startswith('_batch_'):
                    continue
                if key == 'data' and db_translate_payload:
                    # DB batch translation must never replace the entire row objects
                    # from a worker snapshot.  The worker is only allowed to bring
                    # back translation-side fields; source text/source_text and DB
                    # metadata remain owned by the current project data.
                    old_rows = curr.get('data') if isinstance(curr.get('data'), list) else []
                    new_rows = value if isinstance(value, list) else []
                    id_to_old = {}
                    try:
                        for old_row in old_rows:
                            if isinstance(old_row, dict):
                                oid = old_row.get('id')
                                if oid is not None and oid not in id_to_old:
                                    id_to_old[oid] = old_row
                    except Exception:
                        id_to_old = {}
                    for pos, new_row in enumerate(new_rows):
                        if not isinstance(new_row, dict):
                            continue
                        target_row = None
                        try:
                            nid = new_row.get('id')
                            if nid is not None:
                                target_row = id_to_old.get(nid)
                        except Exception:
                            target_row = None
                        if target_row is None and 0 <= pos < len(old_rows) and isinstance(old_rows[pos], dict):
                            target_row = old_rows[pos]
                        if not isinstance(target_row, dict):
                            continue
                        for safe_key in ('translated_text', 'maker_status', 'maker_memo', 'memo'):
                            if safe_key in new_row:
                                target_row[safe_key] = copy.deepcopy(new_row.get(safe_key))
                    curr['data'] = old_rows
                    continue
                if isinstance(value, np.ndarray):
                    curr[key] = value.copy()
                else:
                    curr[key] = value

            # 일괄 인페인팅으로 bg_clean이 새로 들어오면,
            # 원본으로 반영하지 않은 최종 페인팅 레이어는 새 결과 기준으로 초기화한다.
            append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "UI PAYLOAD APPLY DONE", index=i, memory=memory_text())

            # Maker DB 페이지 일괄 번역도 직접 수정/개별 번역과 같은 확정 경로를 탄다.
            # 즉, 프로그램 data 반영 → maker_game JSON writeback → 프로젝트 저장 → name 단어장 갱신.
            try:
                if (
                    getattr(self, "current_batch_mode", None) == "translate"
                    and (hasattr(self, "_is_database_page_index") and self._is_database_page_index(i))
                    and isinstance(payload.get("data"), list)
                ):
                    changed_ids = []
                    glossary_touched = False
                    for row_data in (curr.get("data") or []):
                        if not isinstance(row_data, dict):
                            continue
                        changed_ids.append(row_data.get("id"))
                        try:
                            if self._is_maker_database_name_row(row_data) and str(row_data.get("translated_text") or "").strip():
                                glossary_touched = True
                        except Exception:
                            pass
                    try:
                        self._finalize_maker_database_page_change(
                            i,
                            changed_ids=[x for x in changed_ids if x is not None],
                            fields=["translated_text"],
                            reason="batch_database_translation",
                            refresh_preview=False,
                            writeback=True,
                            glossary_touched=glossary_touched,
                            show_glossary_log=False,
                        )
                    except Exception as e:
                        try:
                            self.log(f"⚠️ DB 일괄 번역 저장/반영 실패: {e}")
                        except Exception:
                            pass
            except Exception:
                pass

            if getattr(self, "current_batch_mode", None) == "inpaint" and "bg_clean" in payload:
                img = self.bg_clean_to_np_image(curr.get('bg_clean'))
                if img is not None:
                    img = self.normalize_image_to_original_size(i, img)
                    encoded = self.encode_np_image_to_png_bytes(img)
                    if encoded is not None:
                        curr['bg_clean'] = encoded
                    if curr.get('use_inpainted_as_source'):
                        self.set_working_source_image(curr, img, page_idx=i)
                curr['final_paint'] = None
                curr['final_paint_above'] = None
                try:
                    self.mark_page_data_dirty_explicit(i, 'clean_background')
                except Exception:
                    pass

        # ON 강제 조건 3: 일괄 분석/재분석으로 결과가 들어온 페이지는 분석 마스크 사용 상태로 저장한다.
        if getattr(self, "current_batch_mode", None) in ("analyze", "reanalyze"):
            if getattr(self, "current_batch_mode", None) == "analyze":
                # 일반 일괄 분석도 개별 분석과 동일하게 이전 텍스트 마스크를 누적하지 않는다.
                # worker payload의 mask_merge / mask_inpaint가 새 기준이며, 이전 보조 텍스트 마스크는 비운다.
                self.data[i]['mask_merge_off'] = None
                self.data[i]['mask_inpaint_off'] = None
            self.data[i]['mask_toggle_enabled'] = True

        if getattr(self, "current_batch_mode", None) in ("analyze", "reanalyze", "translate", "inpaint"):
            self.show_batch_page_progress(i, mode=getattr(self, "current_batch_mode", None), finished=True)
        try:
            self._batch_result_record(i, status=payload_status, message=payload_message)
            self._batch_progress_done = int(getattr(self, "_batch_progress_done", 0) or 0) + 1
            batch_total = int(getattr(self, "_batch_total", len(self.paths)) or len(self.paths))
            self.update_task_progress_overlay(
                current=self._batch_progress_done,
                total=batch_total,
                detail=self.batch_progress_detail(getattr(self, "current_batch_mode", None), self._batch_progress_done, batch_total, i, payload_message or "페이지 작업 완료"),
            )
            # 이미지-heavy 일괄 인페인팅은 페이지 하나를 처리할 때마다 clean 파일을 즉시 flush하고
            # 메모리를 털어야 다음 맵에서 피크가 누적되지 않는다.
            if getattr(self, "current_batch_mode", None) == "inpaint":
                try:
                    self.mark_page_data_dirty_explicit(i, 'clean_background')
                except Exception:
                    pass
                try:
                    if hasattr(self, 'flush_workspace_image_pages'):
                        self.flush_workspace_image_pages([i], reason='batch_inpaint_item', release_non_current=True)
                    else:
                        self.save_to_work_cache()
                except Exception as e:
                    self.log(f"⚠️ [Batch] 인페인팅 페이지 즉시 저장 실패: {e}")
            elif getattr(self, "current_batch_mode", None) not in ("analyze", "reanalyze"):
                self.save_to_work_cache()
            else:
                append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "UI BATCH ITEM CACHE SAVE SKIPPED", index=i, mode=getattr(self, "current_batch_mode", None), memory=memory_text())
            self.has_unsaved_changes = True
            # O단계: 일괄 작업은 시작/종료가 Undo 경계다.
            # 페이지마다 Undo를 다시 끊으면 불필요한 스택 정리와 로그가 반복되어 느려진다.
        except Exception as e:
            try:
                self.log(f"⚠️ [Batch] 페이지 완료 처리 실패: {e}")
            except Exception:
                pass
        try:
            if hasattr(getattr(self, "bw", None), "mark_item_applied"):
                self.bw.mark_item_applied(i)
        except Exception:
            pass
        append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "UI BATCH ITEM FINISHED DONE", index=i, status=payload_status, payload_message=payload_message, memory=memory_text())

    def save_batch_results_without_ui_commit(self):
        """일괄 결과를 복구용 작업 캐시에 저장한다.

        자동저장 기능은 폐지되었으므로, 일괄 작업 결과도 실제 YSBG 패키지에
        즉시 반영하지 않는다. 튕김 복구용 작업 캐시에만 저장하고, 실제 YSBG 확정은
        사용자가 프로젝트 저장/다른 이름으로 저장을 눌렀을 때 수행한다.
        """
        if not getattr(self, "project_dir", None):
            return
        try:
            self.save_to_work_cache()
            self.has_unsaved_changes = True
            self.log("💾 [Batch] 작업 캐시에 일괄 작업 결과 저장")
        except Exception as e:
            self.has_unsaved_changes = True
            self.log(f"⚠️ [Batch] 작업 캐시 저장 실패: {e}")

    def on_batch_finished(self, mode):
        append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "UI BATCH FINISHED ENTER", mode=mode, memory=memory_text())
        try:
            if getattr(getattr(self, "bw", None), "is_running", True) is False or bool(getattr(self, "_long_task_cancel_requested", False)):
                if isinstance(getattr(self, "_batch_result", None), dict):
                    self._batch_result["cancelled"] = True
        except Exception:
            pass
        self.is_batch_running = False
        self.set_project_action_interlock(False)
        self._batch_inpaint_resize_policy = None

        # ON 강제 조건 3: 일괄 분석 완료 직후 현재 페이지 체크박스도 ON으로 맞춘다.
        if mode in ("analyze", "reanalyze"):
            if self.idx in self.data:
                self.data[self.idx]['mask_toggle_enabled'] = True
            self.set_mask_toggle_safely(True)

        # 일괄 분석/재분석은 페이지 작업을 이어 붙인 매크로다.
        # 프로젝트/작업캐시 저장은 사용자가 명시 저장할 때만 수행한다.
        if mode == "translate":
            try:
                result = getattr(self, "_batch_result", None)
                cancelled = bool((result or {}).get("cancelled")) if isinstance(result, dict) else False
                done_entries = list((result or {}).get("done") or []) if isinstance(result, dict) else []
                done_indices = []
                seen_done = set()
                for entry in done_entries:
                    try:
                        idx_done = int(entry.get("index") if isinstance(entry, dict) else entry)
                    except Exception:
                        continue
                    if 0 <= idx_done < len(getattr(self, "paths", []) or []) and idx_done not in seen_done:
                        done_indices.append(idx_done)
                        seen_done.add(idx_done)
                if done_indices and not cancelled:
                    changed_unified = self.apply_unified_translation_memory(
                        scope="selected",
                        show_message=False,
                        auto=True,
                        page_indices=done_indices,
                        page_label=(result or {}).get("page_label") if isinstance(result, dict) else "",
                    )
                    if changed_unified:
                        self.log(f"🧩 일괄 번역 후 통일 번역 자동 적용: 동일 원문 {changed_unified}개 정리")
            except Exception as e:
                try:
                    self.log(f"⚠️ 일괄 번역 후 통일 번역 자동 적용 실패: {e}")
                except Exception:
                    pass

        if mode in ("analyze", "reanalyze"):
            self.has_unsaved_changes = True
            append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "UI BATCH FINISH CACHE SAVE SKIPPED", mode=mode, memory=memory_text())
            try:
                self.log("ℹ️ 일괄 분석/재분석 결과는 현재 프로젝트에만 반영했습니다. 필요하면 [프로젝트 저장]으로 확정하세요.")
            except Exception:
                pass
        else:
            self.save_batch_results_without_ui_commit()

        if self.paths:
            try:
                return_idx = int(getattr(self, "_batch_return_page_idx", self.idx) or 0)
            except Exception:
                return_idx = self.idx
            db_batch_finish = bool(mode == "translate" and getattr(self, "_maker_database_batch_translate_active", False) and hasattr(self, "is_maker_special_table_mode") and self.is_maker_special_table_mode())
            if db_batch_finish:
                try:
                    db_return_idx = int(getattr(self, "_batch_return_database_idx", getattr(self, "maker_database_idx", return_idx)) or getattr(self, "maker_database_idx", return_idx))
                except Exception:
                    db_return_idx = int(getattr(self, "maker_database_idx", return_idx) or return_idx)
                try:
                    if hasattr(self, "_is_database_page_index") and not self._is_database_page_index(db_return_idx):
                        pages = self.current_tab_page_indices() if hasattr(self, "current_tab_page_indices") else []
                        db_return_idx = int(pages[0]) if pages else int(return_idx)
                except Exception:
                    pass
                self.idx = max(0, min(db_return_idx, len(self.paths) - 1))
                self.maker_database_idx = self.idx
                old_suppress = bool(getattr(self, "_suppress_database_ui_commit", False))
                self._suppress_database_ui_commit = True
                try:
                    if hasattr(self, "refresh_maker_database_view"):
                        self.refresh_maker_database_view()
                finally:
                    self._suppress_database_ui_commit = old_suppress
            else:
                self.idx = max(0, min(return_idx, len(self.paths) - 1))
                self.load()

        if mode in ("analyze", "reanalyze"):
            # 일괄 분석/재분석 완료 후 원래 작업 페이지의 분석도로 복귀
            if self.cb_mode.currentIndex() != 1:
                self.cb_mode.setCurrentIndex(1)
            else:
                self.mode_chg(1)

        elif mode == "inpaint":
            # 일괄 인페인팅 완료 후 원래 작업 페이지의 최종결과 화면으로 복귀
            if self.cb_mode.currentIndex() != 4:
                self.cb_mode.setCurrentIndex(4)
            else:
                self.mode_chg(4)

        if mode == "translate" and bool(getattr(self, "_maker_database_batch_translate_active", False)):
            try:
                if hasattr(self, "is_maker_database_mode") and self.is_maker_database_mode():
                    self.refresh_maker_database_auto_glossary(show_log=True)
            finally:
                self._maker_database_batch_translate_active = False

        # 일괄 분석/번역/인페인팅은 여러 페이지에 외부/API 결과를 반영하는 작업 경계다.
        # 성공적으로 전체 흐름이 끝난 뒤 이전 Undo 스택을 끊는다.
        batch_boundary_kind = {
            "analyze": "batch_analysis",
            "reanalyze": "batch_reanalysis",
            "translate": "batch_translation",
            "inpaint": "batch_inpaint",
            "export": "batch_export",
        }.get(mode, "batch_finish")
        self.batch_log_undo_boundary("finish")

        append_log(getattr(getattr(self, "bw", None), "batch_log_path", None), "UI BATCH FINISHED DONE", mode=mode, memory=memory_text())
        self.current_batch_mode = None
        self._active_task_worker = None
        try:
            self._active_batch_job_id = None
        except Exception:
            pass
        # 완료된 UniversalBatchWorker 객체가 self.bw에 남아 있으면
        # macro_batch_is_busy()가 이전 worker 상태를 보고 다음 매크로 일괄 단계로
        # 넘어가지 못할 수 있다. 완료 콜백에서 UI 반영을 끝낸 뒤 참조를 비운다.
        try:
            self.bw = None
        except Exception:
            pass
        self._batch_total = None
        self._batch_current_page_idx = None
        self.end_busy_state({
            "analyze": "일괄 분석",
            "reanalyze": "일괄 재분석",
            "translate": "일괄 번역",
            "inpaint": "일괄 인페인팅",
            "export": "일괄 출력",
        }.get(mode, "일괄 작업"))
        try:
            self.hide_task_progress_overlay()
        except Exception:
            pass
        try:
            result = getattr(self, "_batch_result", None)
            if isinstance(result, dict):
                summary = self._batch_summary_text(result)
                self.log(summary.replace("\n", " | "))
                self.show_batch_result_summary(result)
        except Exception:
            pass
        self.macro_mark_current_step_done(self.macro_batch_key_for_mode(mode))

    def _event_matches_shortcut(self, event, key_name):
        seq = self.shortcut_settings.seq(key_name)
        if not seq or seq.isEmpty():
            return False
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return False
        try:
            mods_value = event.modifiers().value
        except AttributeError:
            mods_value = int(event.modifiers())
        pressed = QKeySequence(mods_value | key)
        return pressed.matches(seq) == QKeySequence.SequenceMatch.ExactMatch

    def keyReleaseEvent(self, event):
        try:
            if getattr(self, "_page_full_name_popup_hold_by_shortcut", False) and not event.isAutoRepeat():
                self.hide_current_page_full_name()
                event.accept()
                return
            if getattr(self, "_page_list_popup_hold_by_shortcut", False) and not event.isAutoRepeat():
                self.hide_page_tab_menu()
                event.accept()
                return
        except Exception:
            pass
        super().keyReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.is_text_transform_active() and (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.end_active_text_transform(refresh=True)
            event.accept()
            return

        key = event.key()

        if key == Qt.Key.Key_Escape:
            handled_escape = False
            try:
                if getattr(self, "inline_text_editor", None) is not None:
                    self.finish_inline_text_edit(commit=False, refresh=True)
                    handled_escape = True
            except Exception:
                handled_escape = True
            if not handled_escape:
                try:
                    if self.is_text_transform_active():
                        self.end_active_text_transform(refresh=True, quiet=False, clear_selection=True)
                        handled_escape = True
                except Exception:
                    try:
                        self.clear_text_transform_modes()
                        handled_escape = True
                    except Exception:
                        pass
            if handled_escape:
                old_suppress = getattr(self, "_suppress_shared_option_refresh", False)
                self._suppress_shared_option_refresh = True
                try:
                    if getattr(self, "view", None) is not None and getattr(self.view, "scene", None) is not None:
                        self.view.scene.clearSelection()
                except Exception:
                    pass
                finally:
                    self._suppress_shared_option_refresh = old_suppress
                try:
                    self.refresh_shared_option_bar()
                except Exception:
                    pass
                try:
                    fw = QApplication.focusWidget()
                    if fw is not None:
                        fw.clearFocus()
                    if getattr(self, "view", None) is not None:
                        self.view.setFocus(Qt.FocusReason.OtherFocusReason)
                except Exception:
                    pass
                event.accept()
                return

        # F2: 현재 편집 가능한 텍스트/이름 칸은 전체 선택.
        # 선택된 텍스트 영역/우측 텍스트 행이면 번역문 수정으로 바로 진입.
        if key == Qt.Key.Key_F2:
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit):
                fw.setFocus()
                fw.selectAll()
                event.accept()
                return
            if isinstance(fw, (QTextEdit, QPlainTextEdit)):
                cur = fw.textCursor()
                cur.select(QTextCursor.SelectionType.Document)
                fw.setTextCursor(cur)
                event.accept()
                return
            if self.edit_selected_translation_text_f2():
                event.accept()
                return

        # 텍스트/숫자 입력 중에는 Backspace/숫자/방향키 등이 전역 단축키로 새지 않게 한다.
        # 특히 QSpinBox가 포커스를 가진 상태에서 valueChanged/UI 갱신이 얽히면
        # OCR 언어 콤보박스로 포커스가 튀는 문제가 생길 수 있다.
        fw = QApplication.focusWidget()
        input_target = None
        try:
            input_target = self.current_single_line_input_widget(fw)
        except Exception:
            input_target = None
        if isinstance(fw, (QTextEdit, QLineEdit, QPlainTextEdit)) or isinstance(input_target, (QAbstractSpinBox, QComboBox, QFontComboBox, QKeySequenceEdit)):
            mods_for_edit = event.modifiers()
            # 단일 수치/콤보/라인 입력칸에서는 Enter/Esc가 포커스 탈출로 동작해야 한다.
            # 그냥 super()로 넘기면 Qt의 focus traversal 때문에 OCR 언어 콤보박스로 포커스가 이동할 수 있다.
            if input_target is not None and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                if key == Qt.Key.Key_Escape:
                    if self.escape_single_line_input_focus_first(input_target):
                        event.accept()
                        return
                elif not (mods_for_edit & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier)):
                    if self.finish_single_line_input_by_enter(input_target):
                        event.accept()
                        return
            # 쯔꾸르붕이: Ctrl+Z/Y는 현재 텍스트 입력칸 내부의 Qt 기본 Undo/Redo만 실행한다.
            # 프로젝트/페이지/AI번역/설정 변경을 전역 Undo로 되돌리지 않는다.
            if isinstance(fw, (QTextEdit, QPlainTextEdit, QLineEdit)):
                if (mods_for_edit & Qt.KeyboardModifier.ControlModifier) and key == Qt.Key.Key_Z:
                    if hasattr(self, "handle_local_text_input_undo_redo"):
                        self.handle_local_text_input_undo_redo(redo=False)
                    event.accept()
                    return
                if (mods_for_edit & Qt.KeyboardModifier.ControlModifier) and key == Qt.Key.Key_Y:
                    if hasattr(self, "handle_local_text_input_undo_redo"):
                        self.handle_local_text_input_undo_redo(redo=True)
                    event.accept()
                    return
            super().keyPressEvent(event)
            return

        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)

        # 맵 목록 단축키는 누르고 있는 동안만 표시하고, 키를 떼면 즉시 닫는다.
        if self._event_matches_shortcut(event, "work_page_list"):
            if not event.isAutoRepeat():
                try:
                    self._page_list_popup_hold_by_shortcut = True
                    self.show_page_tab_menu(hold_by_shortcut=True)
                except TypeError:
                    self.show_page_tab_menu()
            event.accept()
            return

        # 현재 페이지 이름 팝업도 누르고 있는 동안만 표시한다.
        if self._event_matches_shortcut(event, "work_page_full_name"):
            if not event.isAutoRepeat():
                try:
                    self._page_full_name_popup_hold_by_shortcut = True
                    self.show_current_page_full_name()
                except Exception:
                    pass
            event.accept()
            return

        # Alt+숫자: 작업탭 직접 이동
        if alt and key in (
            Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5
        ):
            tab_index = {
                Qt.Key.Key_1: 0,
                Qt.Key.Key_2: 1,
                Qt.Key.Key_3: 2,
                Qt.Key.Key_4: 3,
                Qt.Key.Key_5: 4,
            }.get(key)
            if tab_index is not None and tab_index < self.cb_mode.count():
                self.cb_mode.setCurrentIndex(tab_index)
                return

        if key == Qt.Key.Key_Delete:
            try:
                table = getattr(self, "tab", None)
                fw = QApplication.focusWidget()
                table_context = bool(table is not None and (fw is table or table.isAncestorOf(fw) or table.hasFocus()))
                if table_context and hasattr(self, "clear_maker_translation_cells_for_selection"):
                    if self.clear_maker_translation_cells_for_selection(reason="Delete 번역문 셀 비우기"):
                        event.accept()
                        return
                    # 표에 포커스가 있을 때 Delete는 번역문 열 비우기 전용이다.
                    # 원문/화자/이벤트 열 선택에서 Delete가 텍스트 객체 삭제로 새면 위험하다.
                    event.accept()
                    return
            except Exception:
                pass
            if self.cb_mode.currentIndex() == 4 and self.selected_text_data_items():
                self.delete_text_data_items(ask=True)
                event.accept()
                return

        if self.cb_mode.currentIndex() == 4 and key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            # 방향키는 선택 텍스트를 1px 이동한다. Shift+방향키는 빠른 10px 이동.
            # Ctrl/Alt 조합은 다른 단축키와 충돌할 수 있으므로 여기서는 잡지 않는다.
            if not ctrl and not alt and self.selected_text_data_items():
                step = 10 if shift else 1
                dx = -step if key == Qt.Key.Key_Left else (step if key == Qt.Key.Key_Right else 0)
                dy = -step if key == Qt.Key.Key_Up else (step if key == Qt.Key.Key_Down else 0)
                if self.nudge_selected_text_items(dx, dy):
                    event.accept()
                    return

        if ctrl and key == Qt.Key.Key_C:
            if self.cb_mode.currentIndex() == 4 and self.selected_text_data_items():
                self.copy_text_data_items()
                return

        if self.cb_mode.currentIndex() == 4 and self._event_matches_shortcut(event, "text_paste_same_position"):
            self.paste_text_clipboard_same_position()
            return

        if ctrl and key == Qt.Key.Key_V:
            if self.cb_mode.currentIndex() == 4:
                if self.enter_text_paste_mode():
                    return

        if self.cb_mode.currentIndex() == 4:
            if self._event_matches_shortcut(event, "text_font_size"):
                self.set_text_detail_focus("sb_font_size")
                return
            if self._event_matches_shortcut(event, "text_stroke_size"):
                self.set_text_detail_focus("sb_strk")
                return
            if self._event_matches_shortcut(event, "text_line_spacing"):
                self.set_text_detail_focus("sb_line_spacing")
                return
            if self._event_matches_shortcut(event, "text_letter_spacing"):
                self.set_text_detail_focus("sb_letter_spacing")
                return
            if self._event_matches_shortcut(event, "text_char_width"):
                self.set_text_detail_focus("sb_char_width")
                return
            if self._event_matches_shortcut(event, "text_char_height"):
                self.set_text_detail_focus("sb_char_height")
                return
            if self._event_matches_shortcut(event, "text_bold_toggle"):
                self.toggle_bold()
                return
            if self._event_matches_shortcut(event, "text_italic_toggle"):
                self.toggle_italic()
                return
            if self._event_matches_shortcut(event, "text_strike_toggle"):
                self.toggle_strike()
                return

        # ESC 동작:
        # - 그림판/요술봉 도구 사용 중이면 무조건 이동 모드로 복귀
        # - 최종 화면에서 텍스트가 선택되어 있으면 전체 선택 해제
        if key == Qt.Key.Key_Escape:
            if getattr(self.view, "draw_mode", None):
                self.set_tool(None)
                try:
                    fw = QApplication.focusWidget()
                    if fw is not None:
                        fw.clearFocus()
                    self.view.setFocus(Qt.FocusReason.OtherFocusReason)
                except Exception:
                    pass
                self.log("↔️ 이동 모드")
                return
            if self.cb_mode.currentIndex() == 4:
                self.view.scene.clearSelection()
                try:
                    if getattr(self, "tab", None) is not None:
                        self.tab.clearSelection()
                except Exception:
                    pass
                self.on_scene_selection_changed()
                try:
                    fw = QApplication.focusWidget()
                    if fw is not None:
                        fw.clearFocus()
                    self.view.setFocus(Qt.FocusReason.OtherFocusReason)
                except Exception:
                    pass
                self.log("선택 해제")
                return

        # 그림판/마스크/최종 페인팅 도구 단축키는 관련 탭에서만 사용한다.
        paint_keys = [
            "paint_magic_select", "paint_magic_expand",
            "paint_magic_tolerance_inc", "paint_magic_tolerance_dec",
            "paint_magic_expand_inc", "paint_magic_expand_dec",
            "paint_mask_cut", "paint_area_fill",
            "paint_brush", "paint_erase", "paint_move",
            "paint_zoom_out", "paint_zoom_in", "paint_reanalyze", "paint_undo", "paint_redo",
            "final_paint_color", "paint_area_fill", "final_paint_to_background", "final_text_tool",
            "final_paint_above_toggle", "final_paint_opacity_inc", "final_paint_opacity_dec",
        ]
        if self.cb_mode.currentIndex() not in (2, 3, 4):
            for paint_key in paint_keys:
                if self._event_matches_shortcut(event, paint_key):
                    return

        # 요술봉 전용 단축키
        if self._event_matches_shortcut(event, "paint_magic_select"):
            self.set_tool('magic_wand')
            return
        if self._event_matches_shortcut(event, "paint_magic_expand"):
            self.expand_magic_wand_selection()
            return
        if self._event_matches_shortcut(event, "paint_magic_fill"):
            self.fill_magic_wand_mask()
            return
        if self._event_matches_shortcut(event, "paint_magic_tolerance_inc"):
            self.adjust_magic_tolerance(+1)
            return
        if self._event_matches_shortcut(event, "paint_magic_tolerance_dec"):
            self.adjust_magic_tolerance(-1)
            return
        if self._event_matches_shortcut(event, "paint_magic_expand_inc"):
            self.adjust_magic_expand_range(+1)
            return
        if self._event_matches_shortcut(event, "paint_magic_expand_dec"):
            self.adjust_magic_expand_range(-1)
            return
        if self._event_matches_shortcut(event, "paint_mask_wrap"):
            self.set_tool('mask_wrap')
            return
        if self._event_matches_shortcut(event, "paint_mask_cut"):
            self.set_tool('mask_cut')
            return
        if self.cb_mode.currentIndex() in (2, 3) and self._event_matches_shortcut(event, "paint_area_fill"):
            self.set_tool("area_paint")
            return
        if self._event_matches_shortcut(event, "work_quick_ocr"):
            self.open_quick_ocr_dialog()
            return
        if self._event_matches_shortcut(event, "quick_ocr_execute"):
            self.start_quick_ocr_selection()
            return
        if getattr(self.view, "draw_mode", None) == 'ocr_region_select':
            if self._event_matches_shortcut(event, "paint_mask_wrap_rect"):
                self.set_ocr_region_shape('rect')
                return
            if self._event_matches_shortcut(event, "paint_mask_wrap_free"):
                self.set_ocr_region_shape('free')
                return
        if getattr(self.view, "draw_mode", None) in ('mask_wrap', 'mask_cut', 'area_paint'):
            if self._event_matches_shortcut(event, "paint_mask_wrap_rect"):
                if getattr(self.view, "draw_mode", None) == 'mask_cut':
                    self.set_mask_cut_shape('rect')
                elif getattr(self.view, "draw_mode", None) == 'area_paint':
                    self.set_area_paint_shape('rect')
                else:
                    self.set_mask_wrap_shape('rect')
                return
            if self._event_matches_shortcut(event, "paint_mask_wrap_free"):
                if getattr(self.view, "draw_mode", None) == 'mask_cut':
                    self.set_mask_cut_shape('free')
                elif getattr(self.view, "draw_mode", None) == 'area_paint':
                    self.set_area_paint_shape('free')
                else:
                    self.set_mask_wrap_shape('free')
                return

        if self._event_matches_shortcut(event, "work_page_prev"):
            self.prev()
            return
        if self._event_matches_shortcut(event, "work_page_next"):
            self.next()
            return

        # 최종 화면에서는 F1/글꼴 선택 단축키로 전용 글꼴 선택창을 연다.
        # 텍스트가 선택되어 있으면 선택 텍스트에 적용하고, 없으면 기본 글꼴을 바꾼다.
        if self.cb_mode.currentIndex() == 4 and self._event_matches_shortcut(event, "item_font_select"):
            self.open_font_select_dialog()
            return

        # 최종 화면에서 텍스트를 선택한 상태일 때만 작동하는 개별 텍스트 단축키
        if self.cb_mode.currentIndex() == 4 and self.selected_text_items():
            if self._event_matches_shortcut(event, "text_transform_toggle"):
                self.toggle_selected_text_transform_quick()
                return
            if self._event_matches_shortcut(event, "text_effect_gradient"):
                self.open_selected_text_gradient_dialog()
                return
            if self._event_matches_shortcut(event, "text_skew_toggle"):
                self.toggle_selected_text_skew_quick()
                return
            if self._event_matches_shortcut(event, "text_trapezoid_toggle"):
                self.toggle_selected_text_trapezoid_quick()
                return
            if self._event_matches_shortcut(event, "text_arc_toggle"):
                self.toggle_selected_text_arc_quick()
                return
            if self._event_matches_shortcut(event, "text_rasterize"):
                self.rasterize_selected_text_quick()
                return
            if self._event_matches_shortcut(event, "item_font_select"):
                self.open_font_select_dialog()
                return
            if self._event_matches_shortcut(event, "item_font_inc"):
                items = self.selected_text_items()
                if items:
                    # TextEngine 2차: 선택 텍스트만 즉시 갱신하고 scene 전체/mode_chg는 깨우지 않는다.
                    current = int(items[0].data.get('font_size', self._safe_text_font_size()) or self._safe_text_font_size())
                    self.apply_style_to_selected(font_size=current + 1)
                return
            if self._event_matches_shortcut(event, "item_font_dec"):
                items = self.selected_text_items()
                if items:
                    current = int(items[0].data.get('font_size', self._safe_text_font_size()) or self._safe_text_font_size())
                    self.apply_style_to_selected(font_size=max(1, current - 1))
                return
            if self._event_matches_shortcut(event, "item_align_left"):
                self.apply_style_to_selected(align="left")
                return
            if self._event_matches_shortcut(event, "item_align_center"):
                self.apply_style_to_selected(align="center")
                return
            if self._event_matches_shortcut(event, "item_align_right"):
                self.apply_style_to_selected(align="right")
                return
            if self._event_matches_shortcut(event, "item_stroke_inc"):
                items = self.selected_text_items()
                if items:
                    current = int(items[0].data.get('stroke_width', self._safe_text_stroke_width()) or 0)
                    self.apply_style_to_selected(stroke_width=current + 1)
                return
            if self._event_matches_shortcut(event, "item_stroke_dec"):
                items = self.selected_text_items()
                if items:
                    current = int(items[0].data.get('stroke_width', self._safe_text_stroke_width()) or 0)
                    self.apply_style_to_selected(stroke_width=max(0, current - 1))
                return
            if self._event_matches_shortcut(event, "item_text_color"):
                self.pick_color("item_text")
                return
            if self._event_matches_shortcut(event, "item_stroke_color"):
                self.pick_color("item_stroke")
                return

        if self.cb_mode.currentIndex() == 4:
            if self._event_matches_shortcut(event, "text_transform_toggle"):
                active = self.current_transform_data_item() if hasattr(self, "current_transform_data_item") else None
                if active is not None:
                    self.toggle_text_transform_mode(active)
                    return
            if self._event_matches_shortcut(event, "final_paint_color"):
                self.pick_color("final_paint")
                return
            if self._event_matches_shortcut(event, "paint_area_fill"):
                self.set_tool("area_paint")
                return
            if self._event_matches_shortcut(event, "final_paint_to_background"):
                self.use_final_background_as_source()
                return
            if self._event_matches_shortcut(event, "final_text_tool"):
                self.set_tool("final_text")
                return
            if self._event_matches_shortcut(event, "final_paint_above_toggle"):
                self.toggle_final_paint_above_text()
                return
            if self._event_matches_shortcut(event, "final_paint_opacity_inc"):
                self.adjust_final_paint_opacity(+5)
                return
            if self._event_matches_shortcut(event, "final_paint_opacity_dec"):
                self.adjust_final_paint_opacity(-5)
                return

        if self._event_matches_shortcut(event, "paint_brush"):
            self.set_tool('draw')
            return
        if self._event_matches_shortcut(event, "paint_erase"):
            self.set_tool('erase')
            return
        if self._event_matches_shortcut(event, "paint_move"):
            self.set_tool(None)
            return
        if self._event_matches_shortcut(event, "paint_zoom_out"):
            self.adjust_brush_size(-1)
            return
        if self._event_matches_shortcut(event, "paint_zoom_in"):
            self.adjust_brush_size(+1)
            return
        if self._event_matches_shortcut(event, "paint_reanalyze"):
            self.reanalyze_mask()
            return
        if self._event_matches_shortcut(event, "paint_undo"):
            self.handle_general_undo()
            return
        if self._event_matches_shortcut(event, "paint_redo"):
            self.handle_general_redo()
            return

        super().keyPressEvent(event)


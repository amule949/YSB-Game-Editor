from ysb.ui.main_window_support import *


class MainWindowInteractionMixin:

    def maker_legacy_action_aliases(self):
        """쯔꾸르붕이 정식 액션명과 이전 YSB/식질툴 계열 액션명의 호환표."""
        return {
            "project_import_images": "project_import_maker_game",
            "paint_undo": "edit_undo",
            "paint_redo": "edit_redo",
            "work_analyze": "work_scan_maker_game",
        }

    def _maker_expand_action_keys(self, keys):
        expanded = set(keys or set())
        aliases = self.maker_legacy_action_aliases()
        for legacy_key, maker_key in aliases.items():
            if maker_key in expanded:
                expanded.add(legacy_key)
        return expanded

    def maker_allowed_action_keys(self):
        """쯔꾸르붕이에서 사용자 호출을 허용할 QAction key 목록."""
        canonical = {
            "project_new", "project_import_maker_game", "project_maker_character_profiles", "project_open", "project_open_json",
            "project_show_launcher", "project_exit", "project_save", "project_recover_last_work",
            "option_settings_overview", "option_theme_settings", "option_language_settings", "setting_page_tab_display_name",
            "setting_interface_tooltips", "option_api_settings", "option_shortcut_settings", "option_macro_settings",
            "option_maker_character_prompts", "option_maker_translation_settings",
            "option_maker_preview_display_settings", "option_maker_game_settings", "option_maker_game_refresh",
            "option_maker_database_translation", "db_maker_character_name_translation", "db_maker_plugin_translation",
            "option_glossary", "option_workspace_location",
            "option_cleanup_temp_files", "option_workspace_size_manager",
            "option_register_ysb", "option_unregister_ysbt", "setting_file_path_visibility",
            "help_program_manual", "help_open_website", "help_report_bug", "help_about",
            "work_open_current_project_folder", "work_translate", "work_text_find",
            "work_text_replace", "work_unify_translations", "work_extract_text", "work_import_translation",
            "work_clear_translation", "work_page_prev", "work_page_next", "work_page_list", "work_page_full_name",
            "work_restore_edge_control_codes_current",
            "batch_restore_edge_control_codes",
            "batch_translate", "batch_extract_text", "batch_clear_translation", "edit_undo", "edit_redo",
        }
        return self._maker_expand_action_keys(canonical)

    def maker_macro_action_keys(self):
        """매크로 안에서 허용할 기능. 이미지/식질 기능은 여기서 차단한다."""
        canonical = {
            "work_translate", "batch_translate", "work_text_find", "work_text_replace",
            "work_unify_translations", "work_extract_text", "work_import_translation", "work_clear_translation",
            "work_restore_edge_control_codes_current", "batch_restore_edge_control_codes", "batch_extract_text", "project_save",
        }
        return self._maker_expand_action_keys(canonical)

    def is_maker_action_allowed(self, key):
        if not bool(getattr(self, "maker_action_cleanup_enabled", getattr(self, "tktool_phase2_enabled", False))):
            return True
        return str(key or "") in self.maker_allowed_action_keys()

    def is_maker_macro_action_allowed(self, key):
        if not bool(getattr(self, "maker_action_cleanup_enabled", getattr(self, "tktool_phase2_enabled", False))):
            return True
        return str(key or "") in self.maker_macro_action_keys()

    def apply_maker_action_cleanup(self):
        """숨긴 식질/이미지 기능이 단축키/매크로/QAction으로 다시 실행되지 않도록 잠근다."""
        if not bool(getattr(self, "maker_action_cleanup_enabled", getattr(self, "tktool_phase2_enabled", False))):
            return
        allowed = self.maker_allowed_action_keys()
        for key, action in list((getattr(self, "actions", {}) or {}).items()):
            if key in allowed:
                continue
            try:
                action.setShortcut(QKeySequence())
            except Exception:
                pass
            try:
                action.setEnabled(False)
                action.setVisible(False)
            except Exception:
                pass

    # 구버전 호출 호환 래퍼. 내부 기준명은 maker_*를 사용한다.
    def tktool_phase2_allowed_action_keys(self):
        return self.maker_allowed_action_keys()

    def tktool_phase2_macro_action_keys(self):
        return self.maker_macro_action_keys()

    def is_tktool_phase2_action_allowed(self, key):
        return self.is_maker_action_allowed(key)

    def is_tktool_phase2_macro_action_allowed(self, key):
        return self.is_maker_macro_action_allowed(key)

    def apply_tktool_phase2_action_cleanup(self):
        return self.apply_maker_action_cleanup()

    def setup_actions(self):
        self.maker_action_cleanup_enabled = True
        self.tktool_phase2_enabled = True  # legacy flag compatibility

        def make_action(key, text, slot):
            action = QAction(text, self)
            action.triggered.connect(lambda *args, _slot=slot: _slot())
            self.actions[key] = action
            self.addAction(action)
            return action

        def alias_action(alias_key, target_key):
            action = self.actions.get(target_key)
            if action is not None:
                self.actions[alias_key] = action
            return action

        # 프로젝트
        make_action("project_new", "새 프로젝트", self.new_empty_project_action)
        make_action("project_import_maker_game", "게임 가져오기", self.import_maker_game_action)
        alias_action("project_import_images", "project_import_maker_game")
        make_action("project_open", "YSBG 열기", self.open_project)
        make_action("project_open_json", "프로젝트 열기", self.open_project_json)
        make_action("project_show_launcher", "홈화면으로 가기", self.show_launcher)
        make_action("project_exit", "프로젝트 나가기", self.show_launcher)
        make_action("project_save", "내보내기", self.save_project)
        make_action("project_save_as", "다른 이름으로 내보내기(호환)", self.save_project_as)
        make_action("project_recover_last_work", "복구하기", self.recover_last_work_project)

        # 개별 작업
        make_action("work_source_compare", "원본 비교창 열기/끄기", self.open_source_compare_view)
        make_action("work_page_prev", "이전 맵", self.prev)
        make_action("work_page_next", "다음 맵", self.next)
        make_action("work_page_list", "맵 목록", self.show_page_tab_menu)
        make_action("work_page_full_name", "현재 맵 이름 보기", self.show_current_page_full_name)
        make_action("work_page_rename_source", "맵 탭 이름 변경", self.rename_current_page_source_file)
        make_action("work_page_delete_current", "현재 맵 탭 삭제", self.delete_current_page_shortcut)
        make_action("work_page_delete_all", "일괄 페이지탭 삭제", self.delete_all_pages_shortcut)
        make_action("work_open_current_project_folder", "현재 프로젝트의 작업 폴더로 이동하기", self.open_current_project_work_folder)
        make_action("work_scan_maker_game", "게임 분석", self.scan_maker_game_action)
        alias_action("work_analyze", "work_scan_maker_game")
        make_action("paint_reanalyze", "재분석", self.reanalyze_mask)
        try:
            _reanalyze_tip = "현재 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만들고, 기존 마스크는 재사용합니다."
            self.actions["paint_reanalyze"].setToolTip(self.tr_msg(_reanalyze_tip))
            self.actions["paint_reanalyze"].setStatusTip(self.tr_msg(_reanalyze_tip))
            self.actions["paint_reanalyze"].setWhatsThis(self.tr_msg(_reanalyze_tip))
        except Exception:
            pass
        make_action("work_quick_ocr", "빠른 OCR 설정", self.request_open_quick_ocr_dialog)
        make_action("quick_ocr_execute", "빠른 OCR 실행", self.start_quick_ocr_selection)
        # 빠른 OCR 설정은 프로그램 바탕/포커스 외부에 툴팁이 뜨면 거슬리므로
        # 단축키만 유지하고 일반 툴팁은 비워 둔다.
        try:
            self.actions["work_quick_ocr"].setToolTip("")
            self.actions["work_quick_ocr"].setStatusTip("")
            self.actions["work_quick_ocr"].setWhatsThis("")
            for prop in (
                "delayed_tooltip_title",
                "delayed_tooltip_shortcut",
                "delayed_tooltip_description",
                "delayed_tooltip_force_white_in_light",
                "delayed_tooltip_force_outline",
                "delayed_tooltip_html",
            ):
                self.setProperty(prop, None)
        except Exception:
            pass
        make_action("work_text_number_width", "텍스트 넘버 크기 변경", self.open_text_number_width_dialog)
        make_action("work_translate", "번역", self.trans)
        make_action("work_restore_edge_control_codes_current", "맵 제어코드 복원", self.restore_edge_control_codes_current)
        try:
            tips = {
                "work_translate": "현재 맵의 텍스트를 번역합니다",
                "work_restore_edge_control_codes_current": "현재 맵의 텍스트의 맨앞과 맨 뒤에 있는 제어코드를 자동복원 합니다.",
                "batch_restore_edge_control_codes": "전체 맵의 텍스트의 맨앞과 맨 뒤에 있는 제어코드를 자동복원합니다.",
            }
            for _key, _tip in tips.items():
                act = self.actions.get(_key) if hasattr(self, "actions") else None
                if act is not None:
                    act.setToolTip(self.tr_msg(_tip))
                    act.setStatusTip(self.tr_msg(_tip))
                    act.setWhatsThis(self.tr_msg(_tip))
        except Exception:
            pass
        make_action("work_refresh_maker_preview", "프리뷰 갱신", self.force_refresh_maker_preview_action)
        make_action("work_inpaint", "인페인팅", self.run_inpainting)
        make_action("work_import_clean_background", "클린본 불러오기", self.import_clean_background)
        make_action("work_inpaint_source", "배경을 원본으로 쓰기", self.use_inpainted_as_source)
        make_action("work_restore_original_source", "원본으로 돌아가기", self.restore_original_source)
        make_action("work_extract_text", "원문/번역문 내보내기", self.extract_text_current)
        make_action("work_import_translation", "번역문 불러오기", self.import_translation_current)
        make_action("work_clear_translation", "번역문 내용 지우기", self.clear_translation_current)
        make_action("work_clean_text", "텍스트 정리", self.clean_text_current)
        make_action("work_text_find", "텍스트 찾기", self.open_text_find_dialog)
        make_action("work_text_replace", "텍스트 교체", self.open_text_replace_dialog)
        make_action("work_unify_translations", "번역 통일", self.apply_unified_translation_memory_action)
        make_action("work_reset_text_rects", "현재 텍스트 기준으로 영역 재설정", self.reset_text_rects_current)
        make_action("work_export", "출력", self.export_result)
        make_action("work_output_preview", "출력 미리보기", self.show_output_preview)

        # 자동화 작업
        make_action("auto_text_size_current", "자동 텍스트 크기 조정", self.auto_text_size_current)
        make_action("auto_text_size_batch", "일괄 자동 텍스트 크기 조정", self.auto_text_size_batch)
        make_action("auto_linebreak_current", "자동 줄 내림", self.auto_linebreak_current)
        make_action("auto_linebreak_batch", "일괄 자동 줄 내림", self.auto_linebreak_batch)

        # 일괄 작업
        make_action("batch_analyze", "일괄 게임 분석", lambda: self.run_batch('analyze'))
        make_action("batch_reanalyze", "일괄 재분석", lambda: self.run_batch('reanalyze'))
        try:
            _batch_reanalyze_tip = "선택한 맵마다 현재 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만들고, 기존 마스크는 재사용합니다."
            self.actions["batch_reanalyze"].setToolTip(self.tr_msg(_batch_reanalyze_tip))
            self.actions["batch_reanalyze"].setStatusTip(self.tr_msg(_batch_reanalyze_tip))
            self.actions["batch_reanalyze"].setWhatsThis(self.tr_msg(_batch_reanalyze_tip))
        except Exception:
            pass
        make_action("batch_translate", "일괄 번역", lambda: self.run_batch('translate'))
        make_action("batch_restore_edge_control_codes", "일괄 맵 제어코드 복원", self.restore_edge_control_codes_all)
        try:
            _tip = "전체 맵의 텍스트의 맨앞과 맨 뒤에 있는 제어코드를 자동복원합니다."
            self.actions["batch_restore_edge_control_codes"].setToolTip(self.tr_msg(_tip))
            self.actions["batch_restore_edge_control_codes"].setStatusTip(self.tr_msg(_tip))
            self.actions["batch_restore_edge_control_codes"].setWhatsThis(self.tr_msg(_tip))
        except Exception:
            pass
        make_action("batch_inpaint", "일괄 인페인팅", lambda: self.run_batch('inpaint'))
        make_action("batch_extract_text", "일괄 원문/번역문 내보내기", self.extract_text_batch)
        make_action("batch_clear_translation", "선택 맵 번역문 지우기", self.clear_translation_batch)
        make_action("batch_clean_text", "일괄 텍스트 정리", self.clean_text_batch)
        make_action("batch_reset_text_rects", "일괄 현재 텍스트 기준으로 영역 재설정", self.reset_text_rects_batch)
        make_action("batch_export", "일괄 출력", lambda: self.run_batch('export'))

        # 설정 / 옵션
        make_action("option_settings_overview", "설정 / 옵션", self.open_settings_overview_dialog)
        # v2.4 QA6: 자동저장 모드는 폐지.
        # 예전 단축키/매크로 캐시가 참조해도 오류가 나지 않도록 비활성 액션만 보존한다.
        self.act_auto_save_mode = make_action("option_auto_save_mode", "자동저장 모드(폐지됨)", self.toggle_auto_save_mode)
        self.act_auto_save_mode.setEnabled(False)
        self.act_auto_save_mode.setVisible(False)
        make_action("option_theme_settings", "테마 설정", self.open_theme_settings_dialog)
        make_action("option_language_settings", "언어 설정", self.open_language_settings_dialog)
        make_action("setting_page_tab_display_name", "맵 탭 표시명 설정", self.open_page_tab_display_name_dialog)
        make_action("setting_output_display_name", "출력 표시명 설정", self.open_output_display_name_dialog)
        make_action("setting_output_options", "출력 옵션", self.open_output_options_dialog)
        act_tooltips = make_action("setting_interface_tooltips", "인터페이스 툴팁 표시", self.toggle_interface_tooltips_enabled)
        try:
            act_tooltips.setCheckable(True)
            act_tooltips.setChecked(self.is_interface_tooltips_enabled())
        except Exception:
            pass
        make_action("setting_file_path_visibility", "파일 경로 표시", self.open_file_path_visibility_dialog)
        make_action("option_api_settings", "API 관리", self.open_api_settings_dialog)
        make_action("option_translation_prompt", "공통 번역 프롬프트", self.open_translation_prompt_dialog)
        make_action("option_maker_character_prompts", "게임 프롬프트 관리", self.open_maker_character_prompts_dialog)
        make_action("option_maker_translation_settings", "줄내림 옵션", self.open_maker_translation_settings_dialog)
        make_action("option_maker_refresh_runtime_profile", "쯔꾸르 표시 환경 갱신", self.refresh_maker_display_environment_action)
        make_action("option_maker_game_font_settings", "실제 게임 폰트 설정", self.open_maker_game_font_settings_dialog)
        make_action("option_maker_preview_display_settings", "게임 프리뷰 옵션", self.open_maker_preview_display_settings_dialog)
        make_action("option_maker_game_settings", "게임 설정", self.open_maker_game_settings_dialog)
        make_action("option_maker_game_refresh", "게임 갱신", self.refresh_maker_game_dialogue_action)
        make_action("option_maker_title_settings", "타이틀명 변경", self.open_maker_title_settings_dialog)
        make_action("option_maker_terms_translation", "시스템 번역", self.open_maker_terms_translation_dialog)
        act_db_mode = make_action("option_maker_database_translation", "데이터베이스 모드", self.toggle_maker_database_mode)
        try:
            act_db_mode.setCheckable(True)
            act_db_mode.setChecked(False)
        except Exception:
            pass
        make_action("db_maker_character_name_translation", "화자 번역", self.open_maker_character_name_translation_dialog)
        make_action("db_maker_plugin_translation", "플러그인 번역", self.open_maker_plugin_translation_dialog)
        make_action("debug_maker_database_scan", "DB 스캔 진단", self.diagnose_maker_database_scan_action)
        make_action("debug_maker_database_layer_rebuild", "DB 페이지 확인", self.rebuild_maker_database_layer_manual_action)
        make_action("debug_maker_tile_preview_diagnose", "타일 프리뷰 진단", self.diagnose_maker_tile_preview_action)
        make_action("option_maker_preview_font_settings", "실제 게임 폰트 설정", self.open_maker_game_font_settings_dialog)
        make_action("project_maker_character_profiles", "캐릭터 프로필 보기", self.open_maker_character_profiles_dialog)
        make_action("option_glossary", "단어장", self.open_glossary_dialog)
        make_action("option_analysis_mask_settings", "분석 마스크 확장 비율", self.open_analysis_mask_settings_dialog)
        make_action("option_ocr_analysis_regions", "OCR 분석 범위 지정", self.open_ocr_analysis_region_dialog)
        make_action("option_cleanup_outputs", "출력물 삭제", self.open_output_cleanup_dialog)
        make_action("option_workspace_location", "작업 폴더 위치 변경", self.change_workspace_location)
        make_action("option_workspace_reset_default", "작업 폴더 위치 기본값으로 변경", self.reset_workspace_location_to_default)
        make_action("option_cleanup_temp_files", "사용자 데이터 및 임시파일 정리", self.cleanup_temp_files_dialog)
        make_action("option_workspace_size_manager", "작업 폴더 용량 관리", self.open_workspace_folder_size_manager_dialog)
        make_action("option_register_ysb", ".ysbg 확장자 연결 등록", self.register_ysb_file_association)
        make_action("option_unregister_ysbt", ".ysbg 확장자 연결 해제", self.unregister_ysbt_file_association)
        make_action("option_shortcut_settings", "단축키 통합 관리", self.open_shortcut_settings_dialog)
        make_action("option_macro_settings", "매크로 관리", self.open_macro_settings_dialog)
        make_action("option_text_preset_settings", "페이지 글꼴 프리셋 관리", self.open_text_preset_dialog)
        make_action("option_item_text_preset_settings", "개별 글꼴 프리셋 관리", self.open_item_text_preset_dialog)

        # 도움말
        make_action("help_program_manual", "프로그램 메뉴얼", self.open_program_manual_url)
        make_action("help_open_website", "YSB Game Editor 사이트로 가기", self.open_ysb_tool_site_url)
        make_action("help_report_bug", "버그제보 / 문의하기", self.open_bug_report_url)
        make_action("help_about", "프로그램 정보", self.open_about_dialog)


        # 토글/보조 작업
        make_action("edit_undo", "텍스트 입력 취소", self.handle_global_undo_shortcut)
        alias_action("paint_undo", "edit_undo")
        make_action("edit_redo", "텍스트 입력 재실행", self.handle_general_redo)
        alias_action("paint_redo", "edit_redo")
        make_action("paint_magic_fill", "마스킹 칠하기", self.fill_magic_wand_mask)
        make_action("paint_area_fill", "영역 페인팅", lambda *args: self.set_tool("area_paint"))
        make_action("paint_mask_cut", "마스크 커팅", lambda *args: self.set_tool("mask_cut"))
        make_action("paint_mask_toggle", "마스크 ON/OFF", self.toggle_mask_toggle)
        make_action("view_text_toggle", "텍스트 표시 ON/OFF", self.toggle_show_final_text)
        make_action("final_paint_color", "최종 페인팅 색상", lambda *args: self.pick_color("final_paint"))
        make_action("final_paint_to_background", "배경을 원본으로 쓰기", self.use_final_background_as_source)
        make_action("final_text_tool", "최종 텍스트 도구", lambda *args: self.set_tool("final_text"))
        make_action("final_paint_above_toggle", "텍스트 위 페인팅 ON/OFF", self.toggle_final_paint_above_text)
        make_action("final_paint_opacity_inc", "브러시 불투명도 증가", lambda *args: self.adjust_final_paint_opacity(+5))
        make_action("final_paint_opacity_dec", "브러시 불투명도 감소", lambda *args: self.adjust_final_paint_opacity(-5))

        self.apply_maker_action_cleanup()

    def open_external_url(self, url):
        """도움말 메뉴에서 외부 웹페이지를 기본 브라우저로 연다."""
        try:
            ok = QDesktopServices.openUrl(QUrl(str(url)))
            if not ok:
                raise RuntimeError(self.tr_ui("웹 브라우저로 링크를 열 수 없습니다."))
        except Exception as e:
            try:
                webbrowser.open(str(url))
                return
            except Exception:
                pass
            QMessageBox.warning(self, self.tr_ui("링크 열기 실패"), str(e))

    def open_program_manual_url(self):
        self.open_external_url(YSB_TOOL_MANUAL_URL)

    def open_ysb_tool_site_url(self):
        self.open_external_url(YSB_TOOL_SITE_URL)

    def open_bug_report_url(self):
        # 프로그램에서는 공식 지원 페이지를 경유하고,
        # 사이트 안의 문의/버그제보 버튼이 GitHub Issues 작성 화면으로 이동한다.
        self.open_external_url(YSB_TOOL_SUPPORT_URL)

    def start_auto_version_check(self):
        """Check latest version in the background after startup.

        The app must stay usable without internet, so failures are intentionally
        silent. Only a newer version shows a small dialog.
        """
        try:
            if getattr(self, "_auto_version_check_started", False):
                return
            self._auto_version_check_started = True
            worker = VersionCheckThread(APP_VERSION, timeout=5, parent=self)
            self._auto_version_check_thread = worker
            worker.version_info_ready.connect(self._on_auto_version_info_ready)
            worker.version_check_failed.connect(self._on_auto_version_check_failed)
            worker.finished.connect(worker.deleteLater)
            worker.finished.connect(lambda: setattr(self, "_auto_version_check_thread", None))
            worker.start()
        except Exception:
            pass

    def _on_auto_version_check_failed(self, message):
        # 인터넷이 없거나 사이트가 잠시 안 열려도 프로그램 사용은 막지 않는다.
        try:
            self._auto_version_check_error = str(message)
        except Exception:
            pass

    def _on_auto_version_info_ready(self, info):
        try:
            if getattr(self, "_app_is_closing", False):
                return
            latest_version = str((info or {}).get("latest_version") or "").strip()
            if not latest_version:
                return
            if _ysb_version_tuple(APP_VERSION) >= _ysb_version_tuple(latest_version):
                return

            options = load_app_options()
            ignored = str(options.get(UPDATE_IGNORED_VERSION_KEY, "") or "").strip()
            if ignored == latest_version:
                return

            dialog = UpdateAvailableDialog(self, current_version=APP_VERSION, version_info=info)
            dialog.exec()

            if dialog.ignore_this_version():
                options[UPDATE_IGNORED_VERSION_KEY] = latest_version
                save_app_options(options)
                try:
                    self.app_options = dict(options)
                except Exception:
                    pass

            if getattr(dialog, "open_download_requested", False):
                self.open_external_url(str(info.get("download_page_url") or YSB_TOOL_DOWNLOAD_PAGE_URL))
        except Exception:
            pass

    def apply_shortcuts(self):
        maker_legacy_aliases = {}
        try:
            maker_legacy_aliases = self.maker_legacy_action_aliases()
        except Exception:
            maker_legacy_aliases = {}
        for key, action in self.actions.items():
            # 같은 QAction을 새 maker_* 키와 옛 YSB 키가 함께 가리킬 때는
            # 새 기준 키의 단축키를 우선한다. 여기서 legacy 키를 다시 세팅하면
            # 같은 QAction의 단축키가 옛 캐시값으로 덮일 수 있다.
            if key in maker_legacy_aliases and maker_legacy_aliases.get(key) in self.actions:
                continue
            # Alt+V 현재 페이지 이름은 keyPress/keyRelease에서 직접 처리한다.
            # QAction 단축키와 동시에 살아 있으면 팝업이 두 번 떠서 깜빡인다.
            if key == "work_page_full_name":
                action.setShortcut(QKeySequence())
                action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
                continue
            seq = self.shortcut_settings.seq(key)
            action.setShortcut(seq)
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            if bool(getattr(self, "maker_action_cleanup_enabled", getattr(self, "tktool_phase2_enabled", False))) and not self.is_maker_action_allowed(key):
                try:
                    action.setShortcut(QKeySequence())
                    action.setEnabled(False)
                    action.setVisible(False)
                except Exception:
                    pass

        # 기존 매크로 액션 제거 후 현재 설정 기준으로 다시 등록한다.
        for action in getattr(self, "macro_actions", []):
            try:
                self.removeAction(action)
            except Exception:
                pass
        self.macro_actions = []

        for macro in getattr(self.shortcut_settings, "macros", []) or []:
            if not macro.get("enabled", True):
                continue
            shortcut = str(macro.get("shortcut", "") or "").strip()
            actions = list(macro.get("actions", []) or [])
            if bool(getattr(self, "maker_action_cleanup_enabled", getattr(self, "tktool_phase2_enabled", False))):
                actions = [k for k in actions if self.is_maker_macro_action_allowed(k)]
            if not shortcut or not actions:
                continue
            action = QAction(str(macro.get("name", "매크로")), self)
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.triggered.connect(lambda checked=False, m=dict(macro): self.run_macro(m))
            self.addAction(action)
            self.macro_actions.append(action)

        for action in getattr(self, "item_preset_actions", []):
            try:
                self.removeAction(action)
            except Exception:
                pass
        self.item_preset_actions = []
        if not bool(getattr(self, "tktool_phase2_enabled", False)):
            for name, preset in sorted(getattr(self, "item_text_presets", {}).items()):
                if not preset.get("enabled", True):
                    continue
                shortcut = str(preset.get("shortcut", "") or "").strip()
                if not shortcut:
                    continue
                action = QAction(f"개별 글꼴 프리셋: {name}", self)
                action.setShortcut(QKeySequence(shortcut))
                action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
                # 개별 글꼴 프리셋 "단축키" 적용은 Ctrl+Z 기록에서 제외한다.
                # 일반 텍스트 조정/콤보 적용은 기존처럼 Undo 대상이다.
                action.triggered.connect(lambda checked=False, n=name: self.apply_item_text_preset_by_name(n, record_undo=True))
                self.addAction(action)
                self.item_preset_actions.append(action)

        if hasattr(self, "cb_show_final_text"):
            self.configure_ui_tooltips()

        try:
            if hasattr(self, "btn_project_exit"):
                seq = self.shortcut_settings.seq("project_exit").toString(QKeySequence.SequenceFormat.NativeText)
                self.btn_project_exit.setToolTip(self.native_tooltip_html("프로젝트 나가기", seq))
            if hasattr(self, "btn_page_tab_menu"):
                seq = self.shortcut_settings.seq("work_page_list").toString(QKeySequence.SequenceFormat.NativeText)
                self.btn_page_tab_menu.setToolTip(self.native_tooltip_html("맵 목록", seq))
            if hasattr(self, "btn_page_add"):
                seq = self.shortcut_settings.seq("project_import_maker_game").toString(QKeySequence.SequenceFormat.NativeText)
                self.btn_page_add.setToolTip(self.native_tooltip_html("게임 가져오기", seq, "현재 프로젝트에 RPG Maker MV/MZ 게임 폴더를 클론하고 맵 페이지를 재구성합니다."))
        except Exception:
            pass

    def update_paint_toolbar_visibility(self):
        """작업 탭별로 사용할 수 없는 좌측 도구 아이콘은 숨긴다."""
        if bool(getattr(self, "tktool_phase1_enabled", False)):
            # 쯔꾸르붕이 1단계에서는 이미지 편집 툴바 전체를 UI에서 제거한다.
            for attr in (
                "act_brush", "act_erase", "act_magic", "act_mask_wrap", "act_mask_cut",
                "act_mask_toggle", "act_final_area_paint", "act_final_paint_color",
                "act_final_text_tool", "act_final_paint_to_bg", "act_final_paint_above_text",
            ):
                try:
                    a = getattr(self, attr, None)
                    if a is not None:
                        a.setVisible(False)
                        a.setEnabled(False)
                except Exception:
                    pass
            try:
                if hasattr(self, "mask_toggle_wrap") and self.mask_toggle_wrap:
                    self.mask_toggle_wrap.setVisible(False)
            except Exception:
                pass
            try:
                if hasattr(self, "btn_reanalyze"):
                    self.btn_reanalyze.setVisible(False)
            except Exception:
                pass
            for _name in ("shared_option_bar", "cb_text_effect_preview", "source_compare_controls", "source_compare_bar"):
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
            try:
                if hasattr(self, "tb"):
                    self.tb.setVisible(False)
                    self.tb.setEnabled(False)
                    self.tb.setFixedWidth(0)
            except Exception:
                pass
            return

        mode = self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 0

        mask_tabs = mode in (2, 3)
        final_tab = mode == 4
        drawing_tabs = mask_tabs or final_tab
        paint_only = mode == 3

        # 브러시/지우개는 마스크 탭 + 최종화면에서 사용.
        for attr in ("act_brush", "act_erase"):
            if hasattr(self, attr):
                getattr(self, attr).setVisible(drawing_tabs)

        # 요술봉은 마스크 탭 + 최종결과 탭에서 사용한다.
        # 랩핑/커팅은 마스크 탭 전용이다.
        if hasattr(self, "act_magic"):
            self.act_magic.setVisible(mask_tabs or final_tab)
        if hasattr(self, "act_mask_wrap"):
            self.act_mask_wrap.setVisible(mask_tabs)
        if hasattr(self, "act_mask_cut"):
            self.act_mask_cut.setVisible(mask_tabs)
        # 마스크 ON/OFF는 페인팅 마스크 탭 전용.
        if hasattr(self, "act_mask_toggle"):
            self.act_mask_toggle.setVisible(paint_only)
        if hasattr(self, "mask_toggle_wrap") and self.mask_toggle_wrap:
            self.mask_toggle_wrap.setVisible(paint_only)

        # 영역 페인팅 버튼은 마스크 탭에서는 영역 마스킹, 최종결과 탭에서는 영역 칠하기로 쓴다.
        if hasattr(self, "act_final_area_paint"):
            self.act_final_area_paint.setVisible(mask_tabs or final_tab)

        # 나머지 최종화면 전용 도구.
        for attr in ("act_final_paint_color", "act_final_text_tool", "act_final_paint_to_bg", "act_final_paint_above_text"):
            if hasattr(self, attr):
                getattr(self, attr).setVisible(final_tab)

        # 텍스트 마스크 탭에서만 기존 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만든다.
        if hasattr(self, "btn_reanalyze"):
            self.btn_reanalyze.setVisible(mode == 2)

        if hasattr(self, "tb"):
            self.tb.setEnabled(drawing_tabs)

    def toggle_mask_toggle(self):
        # 마스크 ON/OFF는 페인팅 마스크 탭 전용이다.
        # 텍스트 마스크 탭에서는 관련 동작을 하지 않는다.
        if self.cb_mode.currentIndex() != 3:
            return
        if hasattr(self, "cb_mask_toggle") and self.cb_mask_toggle is not None:
            self.cb_mask_toggle.toggle()

    def toggle_show_final_text(self):
        if hasattr(self, "cb_show_final_text") and self.cb_show_final_text is not None:
            self.cb_show_final_text.toggle()

    def native_tooltip_html(self, title, shortcut_text="", description=""):
        return self._tooltip_rich_text(title, shortcut_text, description)

    def _tooltip_rich_text(self, title, shortcut_text="", description="", force_white_in_light=False, force_outline=False):
        title = str(title or "")
        shortcut_text = str(shortcut_text or "").strip()
        description = str(description or "").strip()

        color_tooltip = bool(force_outline)
        is_light = self.is_light_theme()
        if color_tooltip:
            fg = "#111827" if is_light else "#ffffff"
            sub = "#374151" if is_light else "#E7E2E5"
            line = "#D1C9CE" if is_light else "#555056"
        elif is_light and force_white_in_light:
            fg = "#ffffff"
            sub = "#ffffff"
            line = "#ffffff"
        elif is_light:
            fg = "#111827"
            sub = "#374151"
            line = "#D1C9CE"
        else:
            fg = "#ffffff"
            sub = "#E7E2E5"
            line = "#555056"

        base = (
            f'color:{fg};'
            'font-size:12px;'
            'line-height:1.25;'
            'padding:1px 4px;'
            'white-space:normal;'
        )
        rows = [f'<div style="color:{fg}; font-size:12px; line-height:1.25;"><b>{title}</b></div>']
        if shortcut_text:
            rows.append(f'<div style="margin-top:1px;color:{sub}; font-size:11px; line-height:1.22;">{shortcut_text}</div>')
        if description:
            rows.append(f'<div style="margin-top:3px;color:{sub}; border-top:1px solid {line}; padding-top:3px; font-size:11px; line-height:1.25;">{description}</div>')
        return f'<div style="{base}">' + ''.join(rows) + '</div>'

    def is_text_input_widget(self, widget):
        """키 입력을 글자 편집으로 소비해야 하는 입력 위젯인지 확인한다."""
        try:
            if widget is None:
                return False
            if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
                return True
            # QComboBox 내부의 QLineEdit처럼 직접 타입이 아닌 자식 편집기도 잡는다.
            p = widget
            while p is not None:
                if isinstance(p, (QLineEdit, QTextEdit, QPlainTextEdit)):
                    return True
                p = p.parent()
        except Exception:
            pass
        return False

    def is_editing_table_text_cell(self):
        """우측 텍스트 테이블의 원문/번역 셀을 편집 중인지 확인한다."""
        try:
            fw = QApplication.focusWidget()
            if fw is None or not hasattr(self, "tab") or self.tab is None:
                return False
            if not (fw is self.tab or self.tab.isAncestorOf(fw)):
                return False
            if not self.is_text_input_widget(fw):
                return False
            # 현재 편집기가 열린 셀 좌표를 확인한다. 원문/번역 칸이면 Delete는 행 삭제가 아니라 글자 삭제여야 한다.
            idx = self.tab.currentIndex()
            if idx.isValid() and idx.column() in (2, 3):
                return True
            return True
        except Exception:
            return False

    def install_global_input_filter(self):
        """메인 윈도우 키 입력을 안전하게 정리한다.

        우측 표의 텍스트 셀 편집 중 Delete는 글자 삭제로만 사용하고,
        행 삭제 단축키로 전파하지 않는다.
        """
        if getattr(self, "_global_event_filter_installed", False):
            return
        app = QApplication.instance()
        if app is None:
            return
        try:
            app.installEventFilter(self)
            self._global_event_filter_installed = True
        except Exception:
            pass

    def _is_own_window_object(self, obj):
        try:
            if obj is self:
                return True
            w = obj if isinstance(obj, QWidget) else None
            if w is None:
                return False
            return w.window() is self
        except Exception:
            return False

    def _find_parent_widget_of_type(self, obj, cls):
        try:
            p = obj
            for _ in range(8):
                if p is None or not hasattr(p, "parent"):
                    return None
                p = p.parent()
                if isinstance(p, cls):
                    return p
        except Exception:
            return None
        return None

    def _dialog_key_interlock_is_text_focus(self, widget):
        """Return True when Enter/Esc must not close the parent dialog."""
        try:
            if widget is None:
                return False
            text_types = (QLineEdit, QTextEdit, QPlainTextEdit, QKeySequenceEdit, QAbstractSpinBox)
            if isinstance(widget, text_types):
                return True
            name = type(widget).__name__.lower()
            if "keysequence" in name or "lineedit" in name or "textedit" in name:
                return True
            p = widget
            for _ in range(8):
                if p is None or not hasattr(p, "parent"):
                    break
                p = p.parent()
                if isinstance(p, text_types):
                    return True
                pname = type(p).__name__.lower()
                if "keysequence" in pname or "lineedit" in pname or "textedit" in pname:
                    return True
        except Exception:
            pass
        return False

    def _dialog_key_interlock_positive_button(self, dialog):
        """Find an OK/Apply/Save/Yes button. Never return Cancel/Close."""
        try:
            boxes = dialog.findChildren(QDialogButtonBox)
        except Exception:
            boxes = []
        positive_roles = (
            QDialogButtonBox.ButtonRole.AcceptRole,
            QDialogButtonBox.ButtonRole.ApplyRole,
            QDialogButtonBox.ButtonRole.YesRole,
        )
        for box in boxes or []:
            try:
                for btn in box.buttons():
                    try:
                        role = box.buttonRole(btn)
                    except Exception:
                        role = None
                    if role in positive_roles and btn.isVisible() and btn.isEnabled():
                        return btn
            except Exception:
                pass
            for standard in (
                QDialogButtonBox.StandardButton.Ok,
                QDialogButtonBox.StandardButton.Apply,
                QDialogButtonBox.StandardButton.Save,
                QDialogButtonBox.StandardButton.Yes,
            ):
                try:
                    btn = box.button(standard)
                    if btn is not None and btn.isVisible() and btn.isEnabled():
                        return btn
                except Exception:
                    pass
        try:
            for btn in dialog.findChildren(QPushButton):
                try:
                    if not btn.isVisible() or not btn.isEnabled():
                        continue
                    label = str(btn.text() or "").replace("&", "").strip().lower()
                    if label in {"취소", "cancel", "닫기", "close", "아니오", "no"}:
                        continue
                    if label in {"확인", "적용", "저장", "ok", "apply", "save", "yes", "예"}:
                        return btn
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def _table_cell_editor_from_focus(self, obj=None):
        """Return (table, editor) when focus is inside a QAbstractItemView cell editor."""
        try:
            fw = QApplication.focusWidget()
        except Exception:
            fw = None
        candidates = []
        if isinstance(obj, QWidget):
            candidates.append(obj)
        if isinstance(fw, QWidget) and fw not in candidates:
            candidates.append(fw)
        for target in candidates:
            try:
                # Only active text editors inside item views are handled here.
                if not isinstance(target, (QLineEdit, QTextEdit, QPlainTextEdit)):
                    continue
                p = target
                for _ in range(12):
                    if p is None or not hasattr(p, "parent"):
                        break
                    p = p.parent()
                    if isinstance(p, QAbstractItemView):
                        return p, target
            except Exception:
                pass
        return None, None

    def _handle_table_cell_editor_enter_escape(self, obj, event):
        """Commit/cancel an active table-cell editor before global dialog keys.

        Enter commits the editor.  Esc cancels/reverts it.  This prevents table
        cell edits from leaking to dialog OK/Cancel buttons while keeping normal
        spreadsheet-like editing behavior.
        """
        try:
            if event.type() not in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
                return False
            key = event.key()
            if key not in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                return False
            mods = event.modifiers()
            if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier):
                return False
            table, editor = self._table_cell_editor_from_focus(obj)
            if table is None or editor is None:
                return False
            if event.type() == QEvent.Type.ShortcutOverride:
                event.accept()
                return True
            try:
                if key == Qt.Key.Key_Escape:
                    table.closeEditor(editor, QAbstractItemDelegate.EndEditHint.RevertModelCache)
                else:
                    try:
                        table.commitData(editor)
                    except Exception:
                        pass
                    table.closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)
            except Exception:
                try:
                    editor.clearFocus()
                except Exception:
                    pass
            try:
                table.setFocus(Qt.FocusReason.OtherFocusReason)
            except Exception:
                pass
            event.accept()
            return True
        except Exception:
            return False

    def _dialog_key_interlock_handle(self, obj, event):
        """Global dialog Enter/Esc safety rule.

        - Text/shortcut/spin fields keep dialogs from closing; first Return/Esc clears focus.
        - With no text focus, Return triggers only OK/Apply/Save/Yes, never Cancel.
        - Esc keeps normal cancel behavior only after focus has already escaped input fields.
        """
        try:
            if event.type() not in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
                return False
            key = event.key()
            if key not in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                return False
            try:
                mods = event.modifiers()
                if mods not in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeypadModifier):
                    return False
            except Exception:
                pass
            widget = obj if isinstance(obj, QWidget) else QApplication.focusWidget()
            dialog = None
            try:
                if isinstance(widget, QDialog):
                    dialog = widget
                elif isinstance(widget, QWidget) and isinstance(widget.window(), QDialog):
                    dialog = widget.window()
            except Exception:
                dialog = None
            if dialog is None:
                return False
            try:
                if type(dialog).__name__ in {"QFileDialog", "QColorDialog", "QFontDialog", "QPrintDialog"}:
                    return False
            except Exception:
                pass
            fw = QApplication.focusWidget()
            if fw is not None and self._dialog_key_interlock_is_text_focus(fw):
                if event.type() == QEvent.Type.ShortcutOverride:
                    event.accept()
                    return True
                try:
                    fw.clearFocus()
                except Exception:
                    pass
                try:
                    dialog.setFocus(Qt.FocusReason.OtherFocusReason)
                except Exception:
                    pass
                event.accept()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.type() == QEvent.Type.ShortcutOverride:
                    event.accept()
                    return True
                btn = self._dialog_key_interlock_positive_button(dialog)
                if btn is not None:
                    try:
                        btn.click()
                        event.accept()
                        return True
                    except Exception:
                        pass
        except Exception:
            return False
        return False

    def current_font_focus_widget(self, obj=None):
        """메인/프리셋의 글꼴 선택 콤보박스에 포커스가 있는지 확인한다."""
        try:
            fw = QApplication.focusWidget()
        except Exception:
            fw = None
        candidates = [obj, fw]
        for w in candidates:
            if w is None:
                continue
            try:
                if isinstance(w, QFontComboBox):
                    return w
                parent_font_combo = self._find_parent_widget_of_type(w, QFontComboBox)
                if parent_font_combo is not None:
                    return parent_font_combo
            except Exception:
                pass
        return None

    def escape_font_focus_first(self, obj=None):
        """ESC는 글꼴 선택 콤보박스의 포커스를 먼저 빼고, 다른 작업은 하지 않는다."""
        combo = self.current_font_focus_widget(obj)
        if combo is None:
            return False
        try:
            combo.hidePopup()
        except Exception:
            pass
        try:
            combo.clearFocus()
        except Exception:
            pass
        try:
            line = combo.lineEdit()
            if line is not None:
                line.clearFocus()
        except Exception:
            pass
        try:
            if getattr(self, "view", None) is not None:
                self.view.setFocus(Qt.FocusReason.OtherFocusReason)
            else:
                self.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception:
            pass
        return True

    def current_single_line_input_widget(self, obj=None):
        """ESC/Enter 포커스 탈출 대상이 되는 단일 입력 위젯을 찾는다."""
        try:
            fw = QApplication.focusWidget()
        except Exception:
            fw = None

        for target in (obj, fw):
            if target is None:
                continue
            try:
                if isinstance(target, (QLineEdit, QAbstractSpinBox, QKeySequenceEdit)):
                    return target
                # QSpinBox/QComboBox 내부 lineEdit이나 popup child에서 올라가기
                p = target
                for _ in range(8):
                    if p is None or not hasattr(p, "parent"):
                        break
                    p = p.parent()
                    if isinstance(p, (QAbstractSpinBox, QKeySequenceEdit)):
                        return p
            except Exception:
                pass
        return None

    def escape_single_line_input_focus_first(self, obj=None):
        """ESC는 단일 입력칸 포커스를 먼저 빼고, 다른 작업은 하지 않는다."""
        target = self.current_single_line_input_widget(obj)
        if target is None:
            return False

        # 멀티라인 텍스트 편집은 ESC 포커스 탈출 대상에서 제외한다.
        if isinstance(target, (QTextEdit, QPlainTextEdit)):
            return False

        try:
            if isinstance(target, QComboBox):
                target.hidePopup()
        except Exception:
            pass

        try:
            if isinstance(target, QAbstractSpinBox):
                target.interpretText()
        except Exception:
            pass

        try:
            if isinstance(target, QKeySequenceEdit):
                target.clear()
        except Exception:
            pass

        # 내부 lineEdit까지 같이 포커스 제거
        try:
            line = target.lineEdit()
            if line is not None:
                try:
                    line.deselect()
                except Exception:
                    pass
                line.clearFocus()
        except Exception:
            pass

        try:
            if hasattr(target, "deselect"):
                target.deselect()
            target.clearFocus()
        except Exception:
            pass

        def move_focus():
            try:
                if getattr(self, "view", None) is not None:
                    self.view.setFocus(Qt.FocusReason.OtherFocusReason)
                else:
                    self.setFocus(Qt.FocusReason.OtherFocusReason)
            except Exception:
                pass

        move_focus()
        # 일부 입력 위젯이 ESC 처리 뒤 포커스를 다시 잡는 경우 대비.
        try:
            QTimer.singleShot(0, move_focus)
            QTimer.singleShot(30, move_focus)
        except Exception:
            pass
        return True

    def finish_single_line_input_by_enter(self, obj=None):
        """단일 입력칸에서 Enter를 누르면 값을 확정하고 포커스를 작업 화면으로 돌린다.
        QSpinBox/QDoubleSpinBox는 내부 QLineEdit이 Enter를 삼키거나 다시 포커스를 잡는 경우가 있어
        즉시 clearFocus + 지연 clearFocus를 같이 수행한다.
        """
        try:
            fw = QApplication.focusWidget()
        except Exception:
            fw = None

        def is_input_like(w):
            if w is None:
                return False
            try:
                if isinstance(w, (QLineEdit, QAbstractSpinBox)):
                    return True
                p = w.parent() if hasattr(w, "parent") else None
                if isinstance(w, QLineEdit) and isinstance(p, QComboBox):
                    return True
                for _ in range(4):
                    p = p.parent() if p is not None and hasattr(p, "parent") else None
                    if isinstance(p, QAbstractSpinBox):
                        return True
            except Exception:
                pass
            return False

        # eventFilter로 들어온 obj가 내부 lineEdit일 수 있으므로 obj를 우선 본다.
        target = obj if is_input_like(obj) else fw
        if target is None or not is_input_like(target):
            return False

        spin = None
        line = None
        try:
            if isinstance(target, QAbstractSpinBox):
                spin = target
                line = target.lineEdit()
            else:
                if isinstance(target, QLineEdit):
                    line = target
                p = target
                for _ in range(5):
                    if p is None or not hasattr(p, "parent"):
                        break
                    p = p.parent()
                    if isinstance(p, QAbstractSpinBox):
                        spin = p
                        try:
                            line = p.lineEdit()
                        except Exception:
                            pass
                        break
        except Exception:
            spin = None

        try:
            if spin is not None:
                spin.interpretText()
        except Exception:
            pass

        # 우측 표 셀 편집기면 표 에디터를 닫아 itemChanged를 확정한다.
        try:
            table = getattr(self, "tab", None)
            if table is not None and (target is table or table.isAncestorOf(target)):
                try:
                    table.commitData(target)
                except Exception:
                    pass
                try:
                    table.closeEditor(target, QAbstractItemDelegate.EndEditHint.NoHint)
                except Exception:
                    pass
                table.setFocus(Qt.FocusReason.OtherFocusReason)
                return True
        except Exception:
            pass

        def ensure_focus_sink():
            sink = getattr(self, "_enter_focus_sink", None)
            try:
                if sink is None:
                    sink = QWidget(self)
                    sink.setObjectName("EnterFocusSink")
                    sink.setFixedSize(1, 1)
                    sink.move(-100, -100)
                    sink.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                    try:
                        sink.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    except Exception:
                        pass
                    sink.show()
                    self._enter_focus_sink = sink
                return sink
            except Exception:
                return None

        def clear_and_move_focus():
            # QSpinBox 내부 editor가 Enter 처리 뒤 다시 포커스를 잡는 경우가 있어 여러 대상을 같이 정리한다.
            for w in (line, target, spin):
                try:
                    if w is not None:
                        if hasattr(w, "deselect"):
                            w.deselect()
                        w.clearFocus()
                except Exception:
                    pass

            try:
                if getattr(self, "view", None) is not None:
                    try:
                        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                    except Exception:
                        pass
                    self.view.setFocus(Qt.FocusReason.OtherFocusReason)
                    return
            except Exception:
                pass

            sink = ensure_focus_sink()
            try:
                if sink is not None:
                    sink.setFocus(Qt.FocusReason.OtherFocusReason)
                    return
            except Exception:
                pass

            try:
                self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                self.setFocus(Qt.FocusReason.OtherFocusReason)
            except Exception:
                pass

        clear_and_move_focus()
        # Qt가 spinbox keyPressEvent/editingFinished 뒤에 포커스를 다시 잡는 경우 대비.
        QTimer.singleShot(0, clear_and_move_focus)
        QTimer.singleShot(30, clear_and_move_focus)
        return True

    def commit_active_text_editors_before_undo(self):
        """Undo 직전 열린 셀/인라인 텍스트 편집을 data에 먼저 확정한다."""
        try:
            if getattr(self, "inline_text_editor", None) is not None:
                self.finish_inline_text_edit(commit=True, refresh=False)
        except Exception:
            pass

        fw = QApplication.focusWidget()
        if fw is None:
            return

        # 우측 텍스트 표의 임시 편집기라면 닫아서 itemChanged를 먼저 발생시킨다.
        try:
            if getattr(self, "tab", None) is not None and (fw is self.tab or self.tab.isAncestorOf(fw)):
                try:
                    self.tab.commitData(fw)
                except Exception:
                    pass
                try:
                    self.tab.closeEditor(fw, QAbstractItemDelegate.EndEditHint.NoHint)
                except Exception:
                    try:
                        fw.clearFocus()
                        self.tab.setFocus()
                    except Exception:
                        pass
                QApplication.processEvents()
        except Exception:
            pass

    def handle_inline_text_editor_local_undo_redo(self, redo=False):
        """Legacy canvas-text local Undo hook.

        쯔꾸르붕이는 캔버스 텍스트를 편집하지 않으므로 전역 Undo 경로에서
        이 훅을 사용하지 않는다. 기존 호출 호환을 위해 no-op으로 둔다.
        """
        return False

    def _focused_text_input_for_local_undo(self):
        """Return the currently focused Qt text editor, if Ctrl+Z/Y may stay local.

        쯔꾸르붕이 Undo 정책:
        - 프로젝트/페이지/AI번역/설정 변경은 Undo 대상이 아니다.
        - 현재 포커스가 실제 텍스트 입력 위젯 안에 있을 때만 Qt 기본 Undo/Redo를 실행한다.
        """
        try:
            fw = QApplication.focusWidget()
        except Exception:
            fw = None
        if fw is None:
            return None
        try:
            if isinstance(fw, (QLineEdit, QTextEdit, QPlainTextEdit)):
                return fw
        except Exception:
            return None
        return None

    def handle_local_text_input_undo_redo(self, redo=False):
        editor = self._focused_text_input_for_local_undo()
        if editor is None:
            return False
        try:
            if redo:
                editor.redo()
            else:
                editor.undo()
            if hasattr(self, 'audit_boundary_event'):
                self.audit_boundary_event(
                    'MAKER_TEXT_INPUT_LOCAL_UNDO_REDO',
                    page_idx=getattr(self, 'idx', None),
                    redo=bool(redo),
                    throttle_ms=80,
                )
            return True
        except Exception:
            return False

    def handle_global_undo_shortcut(self):
        # 쯔꾸르붕이에서는 대규모 전역 Undo는 쓰지 않는다.
        # 다만 표 셀 붙여넣기/Del 비우기는 일반 편집 동작이므로
        # 별도 Maker 표 편집 Undo 스택을 먼저 확인한다.
        try:
            if hasattr(self, "undo_maker_table_edit_once") and self.undo_maker_table_edit_once():
                return True
        except Exception:
            pass
        # 현재 열린 텍스트 입력칸의 Qt 기본 Undo를 허용한다.
        self.handle_local_text_input_undo_redo(redo=False)
        return True

    def make_safe_slot(self, func, *call_args, **call_kwargs):
        """Qt 시그널 인자와 충돌하지 않게 고정 인자 슬롯을 만든다.

        lambda *args, w=widget 형태는 PyQt 환경/신호 종류에 따라
        keyword-only 인자 오류를 만들 수 있어서 텍스트 UI에서는 이 헬퍼로 통일한다.
        """
        def _slot(*signal_args):
            return func(*call_args, **call_kwargs)
        return _slot

    def make_safe_deferred_input_slot(self, widget, line_edit=None):
        """입력칸 포커스 확정용 지연 슬롯. w 키워드 캡처 람다를 완전히 제거한다."""
        target_widget = widget
        target_line = line_edit
        def _slot(*signal_args):
            try:
                if target_line is not None and QApplication.focusWidget() is not target_line:
                    return
            except Exception:
                pass
            QTimer.singleShot(0, lambda: self.finish_single_line_input_by_enter(target_widget))
        return _slot

    def make_safe_click_slot(self, widget):
        target_widget = widget
        def _slot(*signal_args):
            if target_widget is not None:
                return target_widget.click()
        return _slot

    def install_enter_escape_for_input(self, widget):
        """QSpinBox 내부 editor가 Enter를 삼키는 경우까지 대비해 직접 필터/시그널을 붙인다."""
        if widget is None:
            return
        # QComboBox/QFontComboBox는 클릭 자체가 팝업 열기 동작이라 일반 입력 안정화 필터를 붙이지 않는다.
        # 마우스 press/release 경로가 중복으로 지나가면 팝업이 두 번 열리는 것처럼 번쩍일 수 있다.
        if isinstance(widget, (QComboBox, QFontComboBox)):
            return
        try:
            if isinstance(widget, QAbstractSpinBox):
                # 숫자 입력 중 매 키마다 valueChanged가 발생하면 화면/우측 UI가 갱신되며
                # 포커스가 OCR 언어 콤보박스 등으로 튈 수 있다. 입력 확정 시점에만 반영한다.
                widget.setKeyboardTracking(False)
        except Exception:
            pass
        try:
            widget.installEventFilter(self)
        except Exception:
            pass

        def install_line():
            try:
                line = widget.lineEdit()
            except Exception:
                line = None
            if line is not None:
                try:
                    line.installEventFilter(self)
                except Exception:
                    pass
                try:
                    line.returnPressed.connect(self.make_safe_slot(self.finish_single_line_input_by_enter, widget))
                except Exception:
                    pass
                try:
                    line.editingFinished.connect(self.make_safe_deferred_input_slot(widget, line))
                except Exception:
                    pass

        install_line()
        QTimer.singleShot(0, install_line)

        try:
            if isinstance(widget, QLineEdit):
                widget.returnPressed.connect(self.make_safe_slot(self.finish_single_line_input_by_enter, widget))
        except Exception:
            pass

    def configure_stable_numeric_inputs(self):
        """메인 UI의 숫자 입력칸은 입력 중 포커스를 잃지 않도록 안정화한다."""
        try:
            widgets = list(self.findChildren(QAbstractSpinBox))
        except Exception:
            widgets = []
        for spin in widgets:
            try:
                spin.setKeyboardTracking(False)
            except Exception:
                pass
            try:
                self.install_enter_escape_for_input(spin)
            except Exception:
                pass

    def install_main_input_enter_escape_filters(self):
        """메인 상단 조작부 입력칸에서 Enter가 포커스 탈출로 동작하게 한다."""
        for widget in (
            getattr(self, "cb_font", None),
            getattr(self, "sb_font_size", None),
            getattr(self, "sb_strk", None),
            getattr(self, "sb_line_spacing", None),
            getattr(self, "sb_letter_spacing", None),
            getattr(self, "sb_char_width", None),
            getattr(self, "sb_char_height", None),
            getattr(self, "final_item_size", None),
            getattr(self, "final_item_stroke", None),
            getattr(self, "sb_text_opacity", None),
            getattr(self, "sb_trans_chunk", None),
            getattr(self, "sb_final_paint_opacity", None),
            getattr(self, "sb_magic_tolerance", None),
            getattr(self, "sb_magic_expand", None),
            getattr(self, "sb_mask_cut_px", None),
        ):
            self.install_enter_escape_for_input(widget)
        try:
            self.configure_stable_numeric_inputs()
        except Exception:
            pass

    def is_interface_tooltips_enabled(self):
        return bool(getattr(self, "interface_tooltips_enabled", True))

    def sync_interface_tooltips_action_state(self):
        try:
            action = getattr(self, "actions", {}).get("setting_interface_tooltips")
            if action is None:
                return
            enabled = self.is_interface_tooltips_enabled()
            action.setCheckable(True)
            action.setChecked(enabled)
            base_text = self.tr_ui("인터페이스 툴팁 표시") if hasattr(self, "tr_ui") else "인터페이스 툴팁 표시"
            # 메뉴에서 현재 상태를 바로 볼 수 있게 켜져 있을 때만 체크 표시를 텍스트 뒤에 붙인다.
            action.setText(f"{base_text} ✓" if enabled else base_text)
            action.setStatusTip("ON" if enabled else "OFF")
        except Exception:
            pass

    def set_interface_tooltips_enabled(self, enabled, *, persist=True, announce=True):
        enabled = bool(enabled)
        self.interface_tooltips_enabled = enabled
        try:
            self.app_options["interface_tooltips_enabled"] = enabled
        except Exception:
            pass
        if not enabled:
            try:
                self._tooltip_target = None
                self._tooltip_html = ""
                timer = getattr(self, "_tooltip_timer", None)
                if timer is not None:
                    timer.stop()
            except Exception:
                pass
            try:
                self._hide_delayed_tooltip_popup()
            except Exception:
                pass
        try:
            self.sync_interface_tooltips_action_state()
        except Exception:
            pass
        if persist:
            try:
                self.save_app_options_cache()
            except Exception:
                try:
                    from ysb.core.cache_utils import save_app_options
                    save_app_options(self.app_options)
                except Exception:
                    pass
        if announce:
            try:
                self.log("💬 인터페이스 툴팁: ON" if enabled else "💬 인터페이스 툴팁: OFF")
            except Exception:
                pass
        return enabled

    def toggle_interface_tooltips_enabled(self):
        return self.set_interface_tooltips_enabled(not self.is_interface_tooltips_enabled(), persist=True, announce=True)

    def register_delayed_tooltip(self, widget, title, shortcut_text="", description=""):
        if widget is None:
            return

        # 메인 윈도우 전체에 지연 툴팁이 붙으면 창 전체가 하나의 툴팁 영역처럼 동작한다.
        # 빠른 OCR 설정 툴팁이 바탕 어디서나 뜨던 원인이 이 케이스였으므로 방어한다.
        if widget is self:
            try:
                for prop in (
                    "delayed_tooltip_title",
                    "delayed_tooltip_shortcut",
                    "delayed_tooltip_description",
                    "delayed_tooltip_force_white_in_light",
                    "delayed_tooltip_force_outline",
                    "delayed_tooltip_html",
                ):
                    self.setProperty(prop, None)
            except Exception:
                pass
            return

        # QWidget 툴팁과 QAction 툴팁이 동시에 살아 있으면
        # 작은 기본 툴팁 + 지연 툴팁 + 상태 설명이 중복 표시될 수 있다.
        # 그래서 실제 표시는 이 지연 툴팁 하나로 통일한다.
        try:
            widget.setToolTip("")
            action = widget.defaultAction() if hasattr(widget, "defaultAction") else None
            if action is not None:
                action.setToolTip("")
                action.setStatusTip("")
                action.setWhatsThis("")
        except Exception:
            pass

        # QComboBox 계열은 팝업 클릭 경로가 예민하므로 기본적으로 지연 툴팁용 eventFilter를 붙이지 않는다.
        # 단, 글꼴 선택 콤보처럼 "처음 쓰는 사람이 반드시 봐야 하는" 핵심 컨트롤은
        # allow_delayed_tooltip_on_combo 속성을 켜서 내부 overlay 툴팁을 허용한다.
        allow_combo_delayed = False
        try:
            allow_combo_delayed = bool(widget.property("allow_delayed_tooltip_on_combo"))
        except Exception:
            allow_combo_delayed = False
        if isinstance(widget, (QComboBox, QFontComboBox)) and not allow_combo_delayed:
            try:
                widget.setToolTip(self.tr_msg(title))
            except Exception:
                pass
            return

        try:
            title = self.tr_msg(title)
            description = self.tr_msg(description)
        except Exception:
            pass
        force_white_in_light = False
        try:
            force_white_in_light = bool(widget.property("force_white_tooltip_in_light") or widget.property("force_dark_tooltip"))
        except Exception:
            force_white_in_light = False
        widget.setProperty("delayed_tooltip_title", title)
        widget.setProperty("delayed_tooltip_shortcut", shortcut_text)
        widget.setProperty("delayed_tooltip_description", description)
        force_outline = False
        try:
            force_outline = bool(widget.property("force_outlined_tooltip_text") or widget.property("force_color_tooltip_text"))
        except Exception:
            force_outline = False
        widget.setProperty("delayed_tooltip_force_white_in_light", force_white_in_light)
        widget.setProperty("delayed_tooltip_force_outline", force_outline)
        widget.setProperty("delayed_tooltip_html", self._tooltip_rich_text(title, shortcut_text, description, force_white_in_light=force_white_in_light, force_outline=force_outline))
        widget.installEventFilter(self)
        # QFontComboBox 같은 복합 위젯은 실제 hover가 내부 child로 들어갈 수 있다.
        # 허용된 combo에 한해서 child에도 같은 tooltip property/filter를 복사한다.
        try:
            if allow_combo_delayed and isinstance(widget, (QComboBox, QFontComboBox)):
                for child in widget.findChildren(QWidget):
                    try:
                        child.setToolTip("")
                        child.setProperty("delayed_tooltip_title", title)
                        child.setProperty("delayed_tooltip_shortcut", shortcut_text)
                        child.setProperty("delayed_tooltip_description", description)
                        child.setProperty("delayed_tooltip_force_white_in_light", force_white_in_light)
                        child.setProperty("delayed_tooltip_force_outline", force_outline)
                        child.setProperty("delayed_tooltip_html", self._tooltip_rich_text(title, shortcut_text, description, force_white_in_light=force_white_in_light, force_outline=force_outline))
                        child.installEventFilter(self)
                    except Exception:
                        pass
        except Exception:
            pass

    def _hide_delayed_tooltip_popup(self):
        try:
            QToolTip.hideText()
        except Exception:
            pass
        try:
            popup = getattr(self, "_tooltip_popup", None)
            if popup is not None:
                popup.hide()
        except Exception:
            pass
        try:
            self._tooltip_visible_target = None
        except Exception:
            pass

    def _cursor_inside_tooltip_target(self, widget, margin=3):
        try:
            if widget is None or not widget.isVisible():
                return False
            pos = QCursor.pos()
            top_left = widget.mapToGlobal(QPoint(0, 0))
            rect = QRect(top_left, widget.size()).adjusted(-margin, -margin, margin, margin)
            return rect.contains(pos)
        except Exception:
            return False

    def _validate_delayed_tooltip_hover(self):
        widget = getattr(self, "_tooltip_visible_target", None) or getattr(self, "_tooltip_target", None)
        popup = getattr(self, "_tooltip_popup", None)
        try:
            has_native = bool(QToolTip.isVisible())
        except Exception:
            has_native = False
        visible = bool((popup is not None and popup.isVisible()) or has_native)
        if not visible:
            return
        if not self._cursor_inside_tooltip_target(widget, margin=6):
            try:
                self._tooltip_timer.stop()
            except Exception:
                pass
            self._tooltip_target = None
            self._tooltip_html = ""
            self._hide_delayed_tooltip_popup()
            return
        try:
            QTimer.singleShot(250, self._validate_delayed_tooltip_hover)
        except Exception:
            pass

    def _tooltip_popup_position(self, widget, popup):
        """위젯 위치에 맞춰 툴팁을 버튼과 겹치지 않게 배치한다."""
        gap = 10
        try:
            top_left = widget.mapToGlobal(QPoint(0, 0))
            rect = QRect(top_left, widget.size())
        except Exception:
            return QCursor.pos() + QPoint(12, 12)

        try:
            main_tl = self.mapToGlobal(QPoint(0, 0))
            main_rect = QRect(main_tl, self.size())
        except Exception:
            main_rect = QRect()

        try:
            hint = str(widget.property("delayed_tooltip_position") or "")
        except Exception:
            hint = ""

        try:
            ox = int(widget.property("delayed_tooltip_offset_x") or 0)
            oy = int(widget.property("delayed_tooltip_offset_y") or 0)
        except Exception:
            ox, oy = 0, 0

        pw = max(1, popup.width())
        ph = max(1, popup.height())

        def pos_above():
            return QPoint(rect.center().x() - pw // 2, rect.top() - ph - gap)

        def pos_below(extra_y=0):
            return QPoint(rect.center().x() - pw // 2, rect.bottom() + gap + extra_y)

        def pos_right():
            return QPoint(rect.right() + gap, rect.center().y() - ph // 2)

        def pos_left():
            return QPoint(rect.left() - pw - gap, rect.center().y() - ph // 2)

        if hint == "right":
            pos = pos_right()
        elif hint == "left":
            pos = pos_left()
        elif hint == "above":
            pos = pos_above()
        elif hint == "below":
            pos = pos_below()
        elif hint == "below_low":
            pos = pos_below(34)
        else:
            # 기본 자동 배치:
            # - 왼쪽 도구바 버튼은 오른쪽
            # - 하단 버튼은 위
            # - 오른쪽 인터페이스 버튼은 조금 아래
            # - 나머지는 아래
            try:
                if main_rect.isValid():
                    if rect.center().x() <= main_rect.left() + 90:
                        pos = pos_right()
                    elif rect.center().y() >= main_rect.bottom() - 130:
                        pos = pos_above()
                    elif rect.center().x() >= main_rect.right() - 210:
                        pos = pos_below(12)
                    else:
                        pos = pos_below()
                else:
                    pos = pos_below()
            except Exception:
                pos = pos_below()

        pos += QPoint(ox, oy)

        # 화면 밖으로 너무 튀어나가지 않게 최소 보정한다.
        try:
            screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                x = max(avail.left() + 4, min(pos.x(), avail.right() - pw - 4))
                y = max(avail.top() + 4, min(pos.y(), avail.bottom() - ph - 4))
                pos = QPoint(x, y)
        except Exception:
            pass
        return pos

    def _show_delayed_tooltip(self):
        if not self.is_interface_tooltips_enabled():
            try:
                self._hide_delayed_tooltip_popup()
            except Exception:
                pass
            return
        widget = self._tooltip_target
        html = self._tooltip_html
        if widget is None or not html:
            return
        if not widget.isVisible():
            return
        try:
            raw_title = widget.property("delayed_tooltip_title")
            if raw_title:
                raw_shortcut = widget.property("delayed_tooltip_shortcut") or ""
                raw_desc = widget.property("delayed_tooltip_description") or ""
                force_white = bool(widget.property("delayed_tooltip_force_white_in_light"))
                force_outline = bool(widget.property("delayed_tooltip_force_outline"))
                html = self._tooltip_rich_text(raw_title, raw_shortcut, raw_desc, force_white_in_light=force_white, force_outline=force_outline)
                self._tooltip_html = html
        except Exception:
            pass
        try:
            self._tooltip_visible_target = widget
        except Exception:
            pass

        # v2.3.1 tooltip isolation:
        # 기본 QToolTip은 버튼을 가리고, parent 없는 ToolTip 창은 작업표시줄에 python 창으로 잡힐 수 있다.
        # 그래서 메인윈도우 내부 QLabel overlay만 사용한다.
        try:
            QToolTip.hideText()
        except Exception:
            pass
        try:
            popup = getattr(self, "_tooltip_popup", None)
            if popup is None:
                popup = QLabel(self)
                popup.setObjectName("ysbDelayedTooltipOverlay")
                popup.setTextFormat(Qt.TextFormat.RichText)
                popup.setWordWrap(True)
                popup.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                popup.hide()
                self._tooltip_popup = popup
            popup.setText(html)
            if self.is_light_theme():
                popup.setStyleSheet("QLabel#ysbDelayedTooltipOverlay { background:#ffffff; color:#111827; border:1px solid #D1C9CE; border-radius:0px; padding:7px 9px; }")
            else:
                popup.setStyleSheet("QLabel#ysbDelayedTooltipOverlay { background:#242329; color:#ffffff; border:1px solid #555056; border-radius:0px; padding:7px 9px; }")
            popup.setMaximumWidth(420)
            popup.adjustSize()
            global_pos = self._tooltip_popup_position(widget, popup)
            local_pos = self.mapFromGlobal(global_pos)
            x = max(4, min(local_pos.x(), max(4, self.width() - popup.width() - 4)))
            y = max(4, min(local_pos.y(), max(4, self.height() - popup.height() - 4)))
            popup.move(x, y)
            popup.show()
            popup.raise_()
            try:
                self.audit_top_level_widgets("delayed_tooltip_overlay", throttle_ms=1000)
            except Exception:
                pass
            self._tooltip_visible_target = widget
            QTimer.singleShot(250, self._validate_delayed_tooltip_hover)
        except Exception:
            pass


    def navigate_tktool_dialogue_by_tab(self, backwards=False):
        """쯔꾸르붕이 전용: 현재 대사표 안에서만 이전/다음 행으로 이동한다.

        This must be a light row-selection move.  Do not call next()/prev() here:
        page switching triggers load/ref_tab/mode_chg and makes normal dialogue
        navigation feel extremely heavy, especially on picture-heavy events.
        """
        table = getattr(self, "tab", None)
        if table is None:
            return False
        try:
            if not hasattr(table, "rowCount") or table.rowCount() <= 1:
                return False
        except Exception:
            return False

        try:
            fw = QApplication.focusWidget()
        except Exception:
            fw = None

        # 열린 셀 에디터가 있으면 먼저 번역문을 확정한다.
        try:
            if fw is not None and (fw is table or table.isAncestorOf(fw)):
                try:
                    table.commitData(fw)
                except Exception:
                    pass
                try:
                    table.closeEditor(fw, QAbstractItemDelegate.EndEditHint.NoHint)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            row_count = int(table.rowCount())
            row = int(table.currentRow())
            if row < 1:
                row = 1
            max_row = max(1, row_count - 1)
            target_row = row - 1 if backwards else row + 1
            target_row = max(1, min(max_row, int(target_row)))

            col = int(table.currentColumn())
            if col < 0 or col >= table.columnCount():
                col = 6 if table.columnCount() >= 7 else min(3, max(0, table.columnCount() - 1))

            table.setCurrentCell(int(target_row), int(col))
            item = table.item(int(target_row), int(col))
            if item is not None:
                table.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
            try:
                if hasattr(self, "refresh_maker_table_current_row_marker"):
                    self.refresh_maker_table_current_row_marker()
            except Exception:
                pass
            try:
                table.setFocus(Qt.FocusReason.TabFocusReason)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def eventFilter(self, obj, event):
        """Delayed tooltip + source compare sync event filter."""
        et = event.type()

        try:
            if self._handle_table_cell_editor_enter_escape(obj, event):
                return True
        except Exception:
            pass

        try:
            if self._dialog_key_interlock_handle(obj, event):
                return True
        except Exception:
            pass

        # DB 프리뷰는 일반 맵 프리뷰처럼 렌더된 이미지로 다룬다.
        # Ctrl+휠은 DB 캔버스 확대/축소, 리사이즈는 맞춤 표시 갱신에 사용한다.
        try:
            if hasattr(self, "is_maker_database_mode") and self.is_maker_database_mode():
                lbl = getattr(self, "lbl_maker_database_preview_canvas", None)
                scroll = getattr(self, "maker_database_preview_scroll", None)
                scroll_vp = None
                try:
                    scroll_vp = scroll.viewport() if scroll is not None else None
                except Exception:
                    scroll_vp = None
                if obj is lbl or obj is scroll or obj is scroll_vp:
                    if et == QEvent.Type.Wheel and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                        delta = 0
                        try:
                            delta = int(event.angleDelta().y())
                        except Exception:
                            delta = 0
                        if hasattr(self, "_maker_database_preview_zoom_by") and self._maker_database_preview_zoom_by(delta):
                            event.accept()
                            return True
                    if et == QEvent.Type.Resize and bool(getattr(self, "_maker_database_preview_fit_mode", True)):
                        try:
                            QTimer.singleShot(0, self._update_maker_database_preview_canvas_scaled)
                        except Exception:
                            pass
        except Exception:
            pass

        # 쯔꾸르붕이: 작업탭 순환 대신 키보드로 대사 행을 이동한다.
        # ShortcutOverride에서 이동까지 해버리면 Qt KeyPress와 겹쳐 Tab이 2칸 이동할 수 있으므로
        # 실제 이동은 KeyPress에서만 처리한다.
        try:
            if (
                bool(getattr(self, "tktool_phase1_enabled", False))
                and et in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress)
                and self._is_own_window_object(obj)
                and getattr(self, "main_stack", None) is not None
                and getattr(self, "editor_widget", None) is not None
                and self.main_stack.currentWidget() is self.editor_widget
            ):
                key = event.key()
                if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_F2, Qt.Key.Key_C, Qt.Key.Key_V):
                    mods = event.modifiers()
                    try:
                        fw = QApplication.focusWidget()
                    except Exception:
                        fw = None
                    table = getattr(self, "tab", None)
                    db_table_mode = bool(table is not None and hasattr(self, "is_maker_database_mode") and self.is_maker_database_mode())
                    maker_table_mode = bool(table is not None and (self._is_maker_text_table_mode() or db_table_mode))
                    try:
                        input_focused = bool(fw is not None and self.is_text_input_widget(fw))
                    except Exception:
                        input_focused = isinstance(fw, (QTextEdit, QPlainTextEdit, QLineEdit))
                    table_focused = bool(maker_table_mode and (fw is table or table.isAncestorOf(fw) or fw is None))
                    # 쯔꾸르붕이의 좌측 화면은 프리뷰일 뿐이다. 다만 모든 버튼/콤보 포커스까지
                    # 대사 이동으로 가로채면 안 되므로, table 또는 preview/view 쪽 포커스일 때만
                    # Space/Enter/Ctrl+Enter를 대사표 기준으로 처리한다.
                    try:
                        view = getattr(self, "view", None)
                        preview_focused = bool(view is not None and (fw is view or view.isAncestorOf(fw)))
                    except Exception:
                        preview_focused = False
                    try:
                        editor_focused = bool(fw is getattr(self, "editor_widget", None))
                    except Exception:
                        editor_focused = False
                    maker_table_keyboard_context = bool(maker_table_mode and not input_focused and (table_focused or preview_focused or editor_focused or fw is self))
                    if key == Qt.Key.Key_C and maker_table_keyboard_context and (mods & Qt.KeyboardModifier.ControlModifier):
                        if et == QEvent.Type.ShortcutOverride:
                            event.accept()
                            return True
                        elif et == QEvent.Type.KeyPress:
                            try:
                                if table is not None and hasattr(table, "copy_selection_to_clipboard") and table.copy_selection_to_clipboard():
                                    event.accept()
                                    return True
                            except Exception:
                                pass
                    if key == Qt.Key.Key_V and maker_table_keyboard_context and (mods & Qt.KeyboardModifier.ControlModifier):
                        # DB mode uses the same right-table layout as normal Maker/map mode,
                        # so cell-selection paste can share the same block paste logic.
                        if isinstance(fw, (QTextEdit, QPlainTextEdit, QLineEdit)):
                            pass
                        elif et == QEvent.Type.ShortcutOverride:
                            event.accept()
                            return True
                        elif et == QEvent.Type.KeyPress:
                            if self.paste_maker_translation_blocks_from_clipboard():
                                event.accept()
                                return True
                    if key == Qt.Key.Key_F2 and maker_table_keyboard_context and et == QEvent.Type.KeyPress:
                        if self.begin_maker_translation_edit_current_row():
                            event.accept()
                            return True
                    if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and maker_table_keyboard_context and (mods & Qt.KeyboardModifier.ControlModifier) and et == QEvent.Type.KeyPress:
                        if db_table_mode:
                            try:
                                self.commit_current_database_ui_to_layer()
                                self.refresh_maker_database_preview_from_selection()
                                event.accept()
                                return True
                            except Exception:
                                pass
                        elif self.apply_current_maker_row_without_move():
                            event.accept()
                            return True
                    if not (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                        # 편집기 안에서는 Enter/Space를 글자 입력으로 유지한다. Ctrl+Enter는 MultilineDelegate가 처리한다.
                        if isinstance(fw, (QTextEdit, QPlainTextEdit, QLineEdit)):
                            pass
                        elif key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                            if et == QEvent.Type.ShortcutOverride:
                                event.accept()
                                return True
                            backwards = bool(key == Qt.Key.Key_Backtab or (mods & Qt.KeyboardModifier.ShiftModifier))
                            if self.navigate_tktool_dialogue_by_tab(backwards=backwards):
                                event.accept()
                                return True
                        elif et == QEvent.Type.KeyPress and not (mods & Qt.KeyboardModifier.ShiftModifier):
                            try:
                                if maker_table_keyboard_context:
                                    if self.navigate_tktool_dialogue_by_tab(backwards=False):
                                        event.accept()
                                        return True
                            except Exception:
                                pass
        except Exception:
            pass

        # 설정/프리셋 다이얼로그 흰색 깜빡임 분석용 로그.
        try:
            if isinstance(obj, QDialog):
                dialog_key = ""
                try:
                    dialog_key = str(obj.property("dialog_timing_log_key") or "")
                except Exception:
                    dialog_key = ""
                if dialog_key:
                    now = time.time()
                    try:
                        created_at = float(obj.property("dialog_timing_created_at") or 0.0)
                    except Exception:
                        created_at = 0.0
                    try:
                        exec_at = float(obj.property("dialog_timing_exec_enter_at") or 0.0)
                    except Exception:
                        exec_at = 0.0
                    if et == QEvent.Type.Show:
                        self.audit_boundary_event(
                            "DIALOG_SHOW_EVENT",
                            dialog_key=dialog_key,
                            title=obj.windowTitle(),
                            since_create_ms=int((now - created_at) * 1000) if created_at else None,
                            since_exec_enter_ms=int((now - exec_at) * 1000) if exec_at else None,
                            size=f"{obj.width()}x{obj.height()}",
                            memory=memory_text(),
                            throttle_ms=20,
                        )
                    elif et == QEvent.Type.Paint:
                        if not bool(obj.property("dialog_first_paint_logged")):
                            obj.setProperty("dialog_first_paint_logged", True)
                            self.audit_boundary_event(
                                "DIALOG_FIRST_PAINT",
                                dialog_key=dialog_key,
                                title=obj.windowTitle(),
                                since_create_ms=int((now - created_at) * 1000) if created_at else None,
                                since_exec_enter_ms=int((now - exec_at) * 1000) if exec_at else None,
                                size=f"{obj.width()}x{obj.height()}",
                                memory=memory_text(),
                                throttle_ms=20,
                            )
                    elif et == QEvent.Type.Hide:
                        self.audit_boundary_event(
                            "DIALOG_HIDE_EVENT",
                            dialog_key=dialog_key,
                            title=obj.windowTitle(),
                            since_create_ms=int((now - created_at) * 1000) if created_at else None,
                            memory=memory_text(),
                            throttle_ms=20,
                        )
        except Exception:
            pass

        # 상단 메뉴바 반응 지연 분석용 로그.
        # 클릭 이벤트가 들어온 시점, aboutToShow 시점, QMenu Show 시점을 분리해서 본다.
        try:
            if isinstance(obj, QMenuBar):
                if et in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
                    try:
                        pos = event.position().toPoint()
                    except Exception:
                        try:
                            pos = event.pos()
                        except Exception:
                            pos = QPoint()
                    action_title = ""
                    action_text = ""
                    try:
                        act = obj.actionAt(pos)
                        if act is not None:
                            action_text = act.text()
                            action_title = action_text.replace("&", "")
                    except Exception:
                        pass
                    now = time.time()
                    if et == QEvent.Type.MouseButtonPress:
                        self._last_menu_bar_press_time = now
                        self._last_menu_bar_press_title = action_title
                        self.audit_boundary_event(
                            "MENU_BAR_MOUSE_PRESS",
                            action_title=action_title,
                            raw_text=action_text,
                            x=int(pos.x()),
                            y=int(pos.y()),
                            button=int(event.button().value) if hasattr(event.button(), "value") else str(event.button()),
                            memory=memory_text(),
                            throttle_ms=50,
                        )
                    else:
                        press_t = float(getattr(self, "_last_menu_bar_press_time", 0.0) or 0.0)
                        self.audit_boundary_event(
                            "MENU_BAR_MOUSE_RELEASE",
                            action_title=action_title,
                            raw_text=action_text,
                            elapsed_since_press_ms=int((now - press_t) * 1000) if press_t else None,
                            x=int(pos.x()),
                            y=int(pos.y()),
                            button=int(event.button().value) if hasattr(event.button(), "value") else str(event.button()),
                            memory=memory_text(),
                            throttle_ms=50,
                        )
                elif et == QEvent.Type.MouseMove:
                    # Hover 로그는 체감 조작감을 둔탁하게 만들 수 있어 기본적으로 끈다.
                    # 필요할 때만 self.menu_timing_verbose = True로 켠다.
                    if bool(getattr(self, "menu_timing_verbose", False)):
                        try:
                            pos = event.position().toPoint()
                        except Exception:
                            try:
                                pos = event.pos()
                            except Exception:
                                pos = QPoint()
                        try:
                            act = obj.actionAt(pos)
                            title = act.text().replace("&", "") if act is not None else ""
                        except Exception:
                            title = ""
                        self.audit_boundary_event("MENU_BAR_MOUSE_MOVE", action_title=title, x=int(pos.x()), y=int(pos.y()), throttle_ms=1500)
            elif isinstance(obj, QMenu):
                if et == QEvent.Type.Show:
                    try:
                        press_t = float(getattr(self, "_last_menu_bar_press_time", 0.0) or 0.0)
                    except Exception:
                        press_t = 0.0
                    self.audit_boundary_event(
                        "MENU_SHOW_EVENT",
                        menu_title=obj.title(),
                        obj_name=obj.objectName(),
                        action_count=len(obj.actions()),
                        since_press_ms=int((time.time() - press_t) * 1000) if press_t else None,
                        memory=memory_text(),
                        throttle_ms=50,
                    )
                elif et == QEvent.Type.Hide:
                    self.audit_boundary_event(
                        "MENU_HIDE_EVENT",
                        menu_title=obj.title(),
                        obj_name=obj.objectName(),
                        memory=memory_text(),
                        throttle_ms=50,
                    )
        except Exception:
            pass

        # registered delayed-tooltip widgets use our internal overlay only.
        # Block Qt native tooltips so they do not cover buttons or create odd colored popups.
        if et == QEvent.Type.ToolTip:
            # QMenu/QMenuBar native tooltip events are fragile on Windows when the
            # menu is being closed and a modal dialog is opened immediately after
            # an action click.  Do not call QToolTip.hideText() for menus; simply
            # consume the tooltip event.  This prevents access-violation crashes
            # observed when opening the Quick OCR settings from the Work menu.
            try:
                if isinstance(obj, (QMenu, QMenuBar)):
                    try:
                        if hasattr(event, "accept"):
                            event.accept()
                    except Exception:
                        pass
                    return True
            except Exception:
                pass
            try:
                if bool(obj.property("allow_native_tooltip")):
                    if self.is_interface_tooltips_enabled():
                        return False
                    try:
                        self.audit_boundary_event("NATIVE_TOOLTIP_BLOCKED_BY_SETTING", obj_type=type(obj).__name__, obj_name=getattr(obj, "objectName", lambda: "")(), throttle_ms=1000)
                    except Exception:
                        pass
                    try:
                        QToolTip.hideText()
                    except Exception:
                        pass
                    return True
            except Exception:
                pass
            try:
                self.audit_boundary_event("NATIVE_TOOLTIP_BLOCKED", obj_type=type(obj).__name__, obj_name=getattr(obj, "objectName", lambda: "")(), throttle_ms=1000)
            except Exception:
                pass
            try:
                QToolTip.hideText()
            except Exception:
                pass
            return True

        # Enter/Esc from right-side numeric/single-line inputs must commit/cancel the
        # edit and return focus to the image workspace.  Do this before global
        # shortcut handling or Qt focus traversal can move focus to the OCR language
        # combo box.
        try:
            if et in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
                key = event.key()
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                    target = self.current_single_line_input_widget(obj)
                    if target is not None:
                        # Do not steal Enter from multiline text editors.
                        if not isinstance(target, (QTextEdit, QPlainTextEdit)):
                            if key == Qt.Key.Key_Escape:
                                if self.escape_single_line_input_focus_first(target):
                                    event.accept()
                                    return True
                            else:
                                if not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier)):
                                    if self.finish_single_line_input_by_enter(target):
                                        event.accept()
                                        return True
        except Exception:
            pass

        # Source compare clone sync must be driven only by real view movement.
        # Resize/Paint/MouseMove are layout/UI events and can drag the image toward
        # the top-left when the compare splitter is moved, so they are intentionally ignored.
        try:
            view = getattr(self, "view", None)
            if view is not None and obj is view.viewport():
                if et in (QEvent.Type.Wheel, QEvent.Type.MouseButtonRelease):
                    try:
                        if hasattr(self, "_begin_source_compare_clone_fast_path"):
                            self._begin_source_compare_clone_fast_path("main_view_event", delay_ms=180)
                    except Exception:
                        pass
                    if hasattr(self, "schedule_source_compare_sync"):
                        self.schedule_source_compare_sync(220 if et == QEvent.Type.Wheel else 80)
        except Exception:
            pass

        # Source compare clone can now be controlled directly.
        # If scroll sync is ON, wheel/drag operations on the clone drive the main work view too.
        try:
            sc_view = getattr(self, "source_compare_view", None)
            if sc_view is not None and obj is sc_view.viewport():
                if et == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                    try:
                        if hasattr(self, '_hide_eyedropper_color_feedback'):
                            self._hide_eyedropper_color_feedback()
                    except Exception:
                        pass

                if (
                    et == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton
                    and (event.modifiers() & Qt.KeyboardModifier.AltModifier)
                    and getattr(self, "cb_mode", None) is not None
                    and self.cb_mode.currentIndex() == 4
                ):
                    try:
                        pt = sc_view.mapToScene(event.pos())
                        if hasattr(self, "pick_final_paint_color_from_source_scene"):
                            self.pick_final_paint_color_from_source_scene(int(pt.x()), int(pt.y()), global_pos=event.globalPosition().toPoint())
                            return True
                    except Exception:
                        pass

                if (
                    et == QEvent.Type.MouseMove
                    and event.buttons() & Qt.MouseButton.LeftButton
                    and (event.modifiers() & Qt.KeyboardModifier.AltModifier)
                    and getattr(self, "cb_mode", None) is not None
                    and self.cb_mode.currentIndex() == 4
                ):
                    try:
                        pt = sc_view.mapToScene(event.pos())
                        if hasattr(self, "pick_final_paint_color_from_source_scene"):
                            self.pick_final_paint_color_from_source_scene(int(pt.x()), int(pt.y()), global_pos=event.globalPosition().toPoint())
                            return True
                    except Exception:
                        pass

                if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                    try:
                        if hasattr(self, "_begin_source_compare_clone_fast_path"):
                            self._begin_source_compare_clone_fast_path("clone_mouse_press", delay_ms=220)
                    except Exception:
                        pass
                    try:
                        self._source_compare_user_driving = True
                    except Exception:
                        pass
                elif et == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                    try:
                        if hasattr(self, "_begin_source_compare_clone_fast_path"):
                            self._begin_source_compare_clone_fast_path("clone_mouse_release", delay_ms=180)
                    except Exception:
                        pass
                    try:
                        self._source_compare_user_driving = False
                    except Exception:
                        pass
                    if hasattr(self, "schedule_main_sync_from_source_compare"):
                        self.schedule_main_sync_from_source_compare(60)
                elif et == QEvent.Type.Wheel:
                    try:
                        if hasattr(self, "_begin_source_compare_clone_fast_path"):
                            self._begin_source_compare_clone_fast_path("clone_wheel", delay_ms=180)
                    except Exception:
                        pass
                    try:
                        self._source_compare_user_driving = True
                    except Exception:
                        pass
                    if hasattr(self, "schedule_main_sync_from_source_compare"):
                        self.schedule_main_sync_from_source_compare(220)
                    try:
                        QTimer.singleShot(260, lambda: setattr(self, '_source_compare_user_driving', False))
                    except Exception:
                        pass

                if et == QEvent.Type.MouseMove and getattr(self, "_source_compare_user_driving", False):
                    try:
                        if hasattr(self, "_begin_source_compare_clone_fast_path"):
                            self._begin_source_compare_clone_fast_path("clone_mouse_move", delay_ms=180)
                    except Exception:
                        pass

                if hasattr(self, "handle_source_compare_quick_ocr_event") and self.handle_source_compare_quick_ocr_event(event):
                    return True
        except Exception:
            pass

        try:
            view = getattr(self, "view", None)
            if view is not None and obj is view.viewport() and et == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if hasattr(self, '_hide_eyedropper_color_feedback'):
                    self._hide_eyedropper_color_feedback()
        except Exception:
            pass


        try:
            if obj is getattr(self, '_source_compare_splitter_handle', None):
                if et == QEvent.Type.MouseButtonPress:
                    self._source_compare_splitter_adjusting = True
                    if hasattr(self, '_block_source_compare_sync_temporarily'):
                        self._block_source_compare_sync_temporarily(320)
                    if hasattr(self, '_capture_source_compare_splitter_states'):
                        self._source_compare_splitter_view_states = self._capture_source_compare_splitter_states()
                elif et == QEvent.Type.MouseMove:
                    # splitter 이동은 레이아웃 변경만 해야 한다. 이미지 좌표/확대/스크롤은 저장값으로 유지한다.
                    if hasattr(self, '_block_source_compare_sync_temporarily'):
                        self._block_source_compare_sync_temporarily(220)
                    if hasattr(self, '_restore_source_compare_splitter_states'):
                        self._restore_source_compare_splitter_states()
                elif et == QEvent.Type.MouseButtonRelease:
                    states = getattr(self, '_source_compare_splitter_view_states', None)
                    if hasattr(self, '_block_source_compare_sync_temporarily'):
                        self._block_source_compare_sync_temporarily(320)
                    if hasattr(self, '_restore_source_compare_splitter_states'):
                        self._restore_source_compare_splitter_states(states)
                        QTimer.singleShot(0, lambda s=states: self._restore_source_compare_splitter_states(s))
                        QTimer.singleShot(80, lambda s=states: self._restore_source_compare_splitter_states(s))
                    self._source_compare_splitter_view_states = None
                    QTimer.singleShot(180, lambda: setattr(self, '_source_compare_splitter_adjusting', False))
                elif et == QEvent.Type.MouseButtonDblClick:
                    if hasattr(self, 'reset_source_compare_splitter_half'):
                        self.reset_source_compare_splitter_half()
                        event.accept()
                        return True
        except Exception:
            pass

        try:
            html = obj.property("delayed_tooltip_html") if obj is not None and hasattr(obj, "property") else None
        except Exception:
            html = None

        if html:
            if not self.is_interface_tooltips_enabled():
                try:
                    if getattr(self, "_tooltip_target", None) is obj or getattr(self, "_tooltip_visible_target", None) is obj:
                        self._tooltip_target = None
                        self._tooltip_html = ""
                        timer = getattr(self, "_tooltip_timer", None)
                        if timer is not None:
                            timer.stop()
                        self._hide_delayed_tooltip_popup()
                except Exception:
                    pass
                return False
            try:
                if et == QEvent.Type.Enter:
                    # New target: always clear any previous popup first.
                    if getattr(self, "_tooltip_visible_target", None) is not obj:
                        self._hide_delayed_tooltip_popup()
                    self._tooltip_target = obj
                    self._tooltip_html = str(html)
                    popup = getattr(self, "_tooltip_popup", None)
                    try:
                        self._tooltip_timer.stop()
                    except Exception:
                        pass
                    if popup is not None and popup.isVisible() and getattr(self, "_tooltip_visible_target", None) is obj:
                        return False
                    self._tooltip_timer.start(420)

                elif et == QEvent.Type.MouseMove:
                    if getattr(self, "_tooltip_target", None) is obj:
                        self._tooltip_html = str(html)

                elif et in (
                    QEvent.Type.Leave,
                    QEvent.Type.Hide,
                    QEvent.Type.Close,
                    QEvent.Type.Destroy,
                    QEvent.Type.FocusOut,
                    QEvent.Type.WindowDeactivate,
                    QEvent.Type.MouseButtonPress,
                    QEvent.Type.MouseButtonRelease,
                    QEvent.Type.Wheel,
                    QEvent.Type.KeyPress,
                ):
                    if getattr(self, "_tooltip_target", None) is obj or getattr(self, "_tooltip_visible_target", None) is obj:
                        try:
                            self._tooltip_timer.stop()
                        except Exception:
                            pass
                        self._tooltip_target = None
                        self._tooltip_html = ""
                        self._hide_delayed_tooltip_popup()
            except Exception:
                pass

        return super().eventFilter(obj, event)


    def configure_ui_tooltips(self):
        def seq_text(key):
            if key.startswith("RAW:"):
                return key[4:]
            try:
                return self.shortcut_settings.seq(key).toString(QKeySequence.SequenceFormat.NativeText)
            except Exception:
                return ""

        def tooltip_pos(widget, pos="", x=0, y=0):
            try:
                if widget is not None:
                    if pos:
                        widget.setProperty("delayed_tooltip_position", pos)
                    if x:
                        widget.setProperty("delayed_tooltip_offset_x", int(x))
                    if y:
                        widget.setProperty("delayed_tooltip_offset_y", int(y))
            except Exception:
                pass

        # 좌측 그림판/마스크 도구
        if hasattr(self, "tb") and self.tb is not None:
            action_info = []
            if hasattr(self, "act_brush"): action_info.append((self.act_brush, "브러시", seq_text("paint_brush")))
            if hasattr(self, "act_erase"): action_info.append((self.act_erase, "지우개", seq_text("paint_erase")))
            if hasattr(self, "act_redo"): action_info.append((self.act_redo, "텍스트 입력 재실행", seq_text("edit_redo")))
            if hasattr(self, "act_magic"): action_info.append((self.act_magic, "요술봉", seq_text("paint_magic_select"), "마스크 탭에서는 마스크 선택/채우기, 최종결과 탭에서는 팔레트 색상으로 영역 칠하기에 사용합니다."))
            if hasattr(self, "act_mask_wrap"): action_info.append((self.act_mask_wrap, "마스크 랩핑", seq_text("paint_mask_wrap"), "영역 안의 떨어진 마스크들을 하나의 채움 영역으로 감싸줍니다."))
            if hasattr(self, "act_mask_cut"): action_info.append((self.act_mask_cut, "마스크 커팅", seq_text("paint_mask_cut"), "선택 영역 밖 경계를 지정 픽셀만큼 잘라 붙어 있는 마스크를 분리합니다."))
            if hasattr(self, "act_final_area_paint"): action_info.append((self.act_final_area_paint, "영역 페인팅/마스킹", seq_text("paint_area_fill"), "마스크 탭에서는 영역 마스킹, 최종결과 탭에서는 현재 페인팅 색상으로 영역을 칠합니다."))
            if hasattr(self, "act_final_text_tool"): action_info.append((self.act_final_text_tool, "최종 텍스트 도구", seq_text("final_text_tool"), "최종화면을 클릭하면 텍스트 영역을 만듭니다. 내용 작성 후 Ctrl+Return을 누르거나 다른 곳을 클릭하면 작성이 완료됩니다."))
            if hasattr(self, "act_final_paint_to_bg"): action_info.append((self.act_final_paint_to_bg, "배경을 원본으로 쓰기", seq_text("final_paint_to_background"), "최종결과 배경을 이후 분석/인페인팅 기준이 되는 작업용 원본으로 반영합니다."))
            if hasattr(self, "act_final_paint_above_text"): action_info.append((self.act_final_paint_above_text, "텍스트 위에 페인팅", seq_text("final_paint_above_toggle"), "ON이면 이후 새로 칠하는 브러시가 텍스트보다 위 레이어에 그려집니다."))
            for info in action_info:
                try:
                    if len(info) >= 4:
                        act, title, sk, desc = info
                    else:
                        act, title, sk = info
                        desc = ""
                    _w = self.tb.widgetForAction(act)
                    if _w is not None:
                        _w.setToolTip("")
                        tooltip_pos(_w, "right")
                    self.register_delayed_tooltip(_w, title, sk, desc)
                except Exception:
                    pass

        if hasattr(self, "act_final_paint_color") and hasattr(self, "tb"):
            try:
                w = self.tb.widgetForAction(self.act_final_paint_color)
                if w is not None:
                    w.setProperty("force_outlined_tooltip_text", True)
                    w.setProperty("force_color_tooltip_text", True)
                    tooltip_pos(w, "right")
                self.register_delayed_tooltip(w, "최종 페인팅 색상", seq_text("final_paint_color"), "스포이드: Alt+마우스 좌클릭")
            except Exception:
                self.register_delayed_tooltip(self.tb.widgetForAction(self.act_final_paint_color), "최종 페인팅 색상", seq_text("final_paint_color"), "스포이드: Alt+마우스 좌클릭")
        if hasattr(self, "mask_toggle_wrap"):
            tooltip_pos(self.mask_toggle_wrap, "right")
            self.register_delayed_tooltip(
                self.mask_toggle_wrap,
                "페인팅 마스크 ON/OFF",
                seq_text("paint_mask_toggle"),
                "ON은 분석 기반, OFF는 직접 칠한 마스크를 사용합니다."
            )
        if hasattr(self, "sb_brush_size"):
            self.register_delayed_tooltip(self.sb_brush_size, "브러시 크기", f"{seq_text('paint_zoom_out')} / {seq_text('paint_zoom_in')}", "브러시와 지우개의 두께를 1px 단위로 조절합니다.")
        if hasattr(self, "final_paint_option_bar"):
            self.register_delayed_tooltip(self.sb_final_paint_opacity, "최종 브러시 불투명도", f"{seq_text('final_paint_opacity_dec')} / {seq_text('final_paint_opacity_inc')}", "최종화면 브러시 색상의 알파값을 조절합니다.")
        if hasattr(self, "magic_wand_bar"):
            self.register_delayed_tooltip(self.btn_magic_expand, "선택 영역 확장", seq_text("paint_magic_expand"))
            self.register_delayed_tooltip(self.btn_magic_fill, "마스킹/영역 칠하기", seq_text("paint_magic_fill"), "마스크 탭에서는 마스크를 채우고, 최종결과 탭에서는 현재 팔레트 색상으로 영역을 칠합니다.")
            self.register_delayed_tooltip(self.sb_magic_tolerance, "RGB 허용범위", f"{seq_text('paint_magic_tolerance_inc')} / {seq_text('paint_magic_tolerance_dec')}")
            self.register_delayed_tooltip(self.sb_magic_expand, "영역 확장 범위", f"{seq_text('paint_magic_expand_inc')} / {seq_text('paint_magic_expand_dec')}")
        if hasattr(self, "area_paint_bar"):
            self.register_delayed_tooltip(self.btn_area_paint_rect, "사각형 영역", seq_text("paint_mask_wrap_rect"), "마스크 탭에서는 영역 마스킹, 최종결과 탭에서는 현재 페인팅 색상으로 영역 칠하기를 수행합니다.")
            self.register_delayed_tooltip(self.btn_area_paint_free, "자유형 영역", seq_text("paint_mask_wrap_free"), "마스크 탭에서는 영역 마스킹, 최종결과 탭에서는 현재 페인팅 색상으로 영역 칠하기를 수행합니다.")
        if hasattr(self, "mask_wrap_bar"):
            self.register_delayed_tooltip(self.btn_mask_wrap_rect, "사각형으로 영역 그리기", seq_text("paint_mask_wrap_rect"), "윈도우 캡처처럼 사각형 범위를 잡고 그 안의 마스크들을 하나로 감싸 채웁니다.")
            self.register_delayed_tooltip(self.btn_mask_wrap_free, "자유형으로 영역 그리기", seq_text("paint_mask_wrap_free"), "드래그한 자유형 범위 안에서만 마스크들을 하나로 감싸 채웁니다.")
        if hasattr(self, "mask_cut_bar"):
            self.register_delayed_tooltip(self.btn_mask_cut_rect, "사각형으로 영역 그리기", seq_text("paint_mask_wrap_rect"), "사각형 보존 영역의 바깥 경계를 지정 픽셀만큼 잘라냅니다.")
            self.register_delayed_tooltip(self.btn_mask_cut_free, "자유형으로 영역 그리기", seq_text("paint_mask_wrap_free"), "자유형 보존 영역의 바깥 경계를 지정 픽셀만큼 잘라냅니다.")
            self.register_delayed_tooltip(self.sb_mask_cut_px, "커팅 폭", "", "선택 영역 밖으로 잘라낼 마스크 폭입니다.")
        if hasattr(self, "ocr_region_bar"):
            self.register_delayed_tooltip(self.btn_ocr_region_rect, "사각형 OCR 분석 영역", seq_text("paint_mask_wrap_rect"), "사각형으로 OCR이 읽을 영역을 지정합니다.")
            self.register_delayed_tooltip(self.btn_ocr_region_free, "자유형 OCR 분석 영역", seq_text("paint_mask_wrap_free"), "자유형으로 OCR이 읽을 영역을 지정합니다.")
            self.register_delayed_tooltip(self.btn_ocr_region_finish, "OCR 분석 영역 지정 종료", "", "지정한 영역을 저장하거나 폐기하고 영역 지정 모드를 종료합니다.")

        # 툴팁 글자색은 테마 기본값을 따른다.
        # 색상 버튼처럼 특수한 경우만 개별 QToolTip 스타일에서 처리한다.

        # 우측 상단 작업 버튼/옵션
        if hasattr(self, "sb_trans_chunk"):
            self.register_delayed_tooltip(self.sb_trans_chunk, "묶음 수", "", "한 번의 API 요청에 묶어서 보낼 텍스트 줄 수")
        if hasattr(self, "btn_reanalyze"):
            tooltip_pos(self.btn_reanalyze, "above")
            self.register_delayed_tooltip(self.btn_reanalyze, "재분석", seq_text("paint_reanalyze"), "텍스트 마스크를 유지한 채 현재 페이지를 다시 분석합니다.")
        if hasattr(self, "btn_analyze"):
            tooltip_pos(self.btn_analyze, "above")
            self.register_delayed_tooltip(self.btn_analyze, "분석", seq_text("work_scan_maker_game"), "현재 페이지를 분석합니다.")
            # 빠른 OCR 설정은 버튼이 아니라 단축키/메뉴로 여는 기능이다.
            # 메인 윈도우(self)에 지연 툴팁을 등록하면 창 전체가 툴팁 영역이 되어
            # 포커스가 없어도 마우스 진입 시 계속 툴팁이 뜬다.
            # 따라서 여기서는 별도 지연 툴팁을 등록하지 않는다.
        if hasattr(self, "btn_translate"):
            tooltip_pos(self.btn_translate, "below")
            self.register_delayed_tooltip(self.btn_translate, "번역", seq_text("work_translate"), "현재 맵의 텍스트를 번역합니다.")
            if hasattr(self, "btn_maker_ctrl_restore_current"):
                self.register_delayed_tooltip(self.btn_maker_ctrl_restore_current, "현재 맵 복원", seq_text("work_restore_edge_control_codes_current"), "현재 맵의 텍스트의 맨앞과 맨 뒤에 있는 제어코드를 자동복원 합니다.")
            if hasattr(self, "btn_maker_ctrl_restore_all"):
                self.register_delayed_tooltip(self.btn_maker_ctrl_restore_all, "일괄 맵 복원", seq_text("batch_restore_edge_control_codes"), "전체 맵의 텍스트의 맨앞과 맨 뒤에 있는 제어코드를 자동복원합니다.")
        if hasattr(self, "btn_maker_preview_refresh"):
            tooltip_pos(self.btn_maker_preview_refresh, "above")
            self.register_delayed_tooltip(self.btn_maker_preview_refresh, "프리뷰 갱신", seq_text("work_refresh_maker_preview"), "현재 맵의 프리뷰 이미지를 상태/캐시와 무관하게 다시 만듭니다.")
        if hasattr(self, "btn_inpaint"):
            tooltip_pos(self.btn_inpaint, "above")
            self.register_delayed_tooltip(self.btn_inpaint, "인페인팅", seq_text("work_inpaint"))
        if hasattr(self, "btn_text_cleanup"):
            tooltip_pos(self.btn_text_cleanup, "above")
            self.register_delayed_tooltip(self.btn_text_cleanup, "텍스트 정리", seq_text("work_clean_text"))
        if hasattr(self, "cb_show_final_text"):
            tooltip_pos(self.cb_show_final_text, "left", x=-6)
            self.register_delayed_tooltip(self.cb_show_final_text, "텍스트 표시 ON/OFF", seq_text("view_text_toggle"))
        if hasattr(self, "cb_font"):
            try:
                self.cb_font.setProperty("allow_delayed_tooltip_on_combo", True)
                tooltip_pos(self.cb_font, "below", y=4)
            except Exception:
                pass
            self.register_delayed_tooltip(
                self.cb_font,
                "글꼴 선택",
                seq_text("item_font_select"),
                "폰트 설정창을 엽니다.",
            )
        if hasattr(self, "sb_font_size"):
            self.register_delayed_tooltip(self.sb_font_size, "글꼴 크기", seq_text("text_font_size"), "현재 선택한 텍스트의 글자 크기를 조절합니다.")
        if hasattr(self, "sb_strk"):
            self.register_delayed_tooltip(self.sb_strk, "획 크기", seq_text("text_stroke_size"), "현재 선택한 텍스트의 외곽선 두께를 조절합니다.")
        if hasattr(self, "sb_line_spacing"):
            self.register_delayed_tooltip(self.sb_line_spacing, "행간", seq_text("text_line_spacing"), "줄과 줄 사이 간격을 조절합니다.")
        if hasattr(self, "sb_letter_spacing"):
            self.register_delayed_tooltip(self.sb_letter_spacing, "자간", seq_text("text_letter_spacing"), "글자와 글자 사이 간격을 조절합니다.")
        if hasattr(self, "sb_char_width"):
            self.register_delayed_tooltip(self.sb_char_width, "너비", seq_text("text_char_width"), "문자의 가로 비율을 조절합니다.")
        if hasattr(self, "sb_char_height"):
            self.register_delayed_tooltip(self.sb_char_height, "높이", seq_text("text_char_height"), "문자의 세로 비율을 조절합니다.")
        if hasattr(self, "btn_bold"):
            self.register_delayed_tooltip(self.btn_bold, "굵게", seq_text("text_bold_toggle"))
            self.register_delayed_tooltip(self.btn_italic, "기울이기", seq_text("text_italic_toggle"))
            self.register_delayed_tooltip(self.btn_strike, "취소선", seq_text("text_strike_toggle"))
        if hasattr(self, "btn_prev_page"):
            tooltip_pos(self.btn_prev_page, "above")
            self.register_delayed_tooltip(self.btn_prev_page, "이전 맵", seq_text("work_page_prev"))
        if hasattr(self, "btn_next_page"):
            tooltip_pos(self.btn_next_page, "above")
            self.register_delayed_tooltip(self.btn_next_page, "다음 맵", seq_text("work_page_next"))
        if hasattr(self, "btn_page_tab_menu"):
            tooltip_pos(self.btn_page_tab_menu, "above")
            self.register_delayed_tooltip(self.btn_page_tab_menu, "맵 목록", seq_text("work_page_list"))
        if hasattr(self, "btn_page_scroll_left"):
            tooltip_pos(self.btn_page_scroll_left, "above")
            self.register_delayed_tooltip(self.btn_page_scroll_left, "페이지 탭 왼쪽 이동", "")
        if hasattr(self, "btn_page_scroll_right"):
            tooltip_pos(self.btn_page_scroll_right, "above")
            self.register_delayed_tooltip(self.btn_page_scroll_right, "페이지 탭 오른쪽 이동", "")
        if hasattr(self, "btn_page_add"):
            tooltip_pos(self.btn_page_add, "above")
            self.register_delayed_tooltip(self.btn_page_add, "게임 가져오기", seq_text("project_import_maker_game"), "현재 프로젝트에 RPG Maker MV/MZ 게임 폴더를 클론하고 맵 페이지를 재구성합니다.")
        if hasattr(self, "btn_project_exit"):
            tooltip_pos(self.btn_project_exit, "below_low", y=10)
            self.register_delayed_tooltip(self.btn_project_exit, "프로젝트 나가기", seq_text("project_exit"), "현재 프로젝트를 닫고 시작 화면으로 돌아갑니다.")
        if hasattr(self, "btn_page"):
            # 페이지 번호/이름 영역은 메뉴 조작 동선과 겹쳐 툴팁이 방해되므로 끈다.
            try:
                self.btn_page.setToolTip("")
                for _name in ("delayed_tooltip_title", "delayed_tooltip_shortcut", "delayed_tooltip_description", "delayed_tooltip_html"):
                    self.btn_page.setProperty(_name, "")
            except Exception:
                pass
        if hasattr(self, "btn_quick_undo"):
            tooltip_pos(self.btn_quick_undo, "above")
            self.register_delayed_tooltip(self.btn_quick_undo, "텍스트 입력 취소", seq_text("edit_undo"), "현재 텍스트 입력칸의 글자 수정만 되돌립니다.")
        if hasattr(self, "btn_quick_redo"):
            tooltip_pos(self.btn_quick_redo, "above")
            self.register_delayed_tooltip(self.btn_quick_redo, "텍스트 입력 재실행", seq_text("edit_redo"), "현재 텍스트 입력칸의 글자 수정만 다시 실행합니다.")
        if hasattr(self, "cb_text_preset"):
            self.register_delayed_tooltip(self.cb_text_preset, "페이지 프리셋", "", "현재 페이지/전체 맵에 적용할 글꼴 프리셋을 선택합니다.")
        if hasattr(self, "btn_preset_save"):
            self.register_delayed_tooltip(self.btn_preset_save, "페이지 프리셋 저장", "", "현재 글꼴 설정을 페이지 프리셋으로 저장합니다.")
        if hasattr(self, "btn_preset_import"):
            self.register_delayed_tooltip(self.btn_preset_import, "페이지 프리셋 가져오기", "", "외부 프리셋 JSON을 가져옵니다.")
        if hasattr(self, "btn_preset_apply_page"):
            self.register_delayed_tooltip(self.btn_preset_apply_page, "현재 페이지 프리셋 적용", "", "선택한 맵 프리셋을 현재 페이지에 적용합니다.")
        if hasattr(self, "btn_preset_apply_all"):
            self.register_delayed_tooltip(self.btn_preset_apply_all, "전체 맵 프리셋 적용", "", "선택한 맵 프리셋을 전체 맵에 적용합니다.")
        if hasattr(self, "cb_item_text_preset"):
            try:
                self.cb_item_text_preset.setProperty("allow_delayed_tooltip_on_combo", True)
            except Exception:
                pass
            self.register_delayed_tooltip(self.cb_item_text_preset, "개별 글꼴 프리셋", "", "선택한 텍스트 객체에 적용할 개별 글꼴 프리셋을 선택합니다.")
        if hasattr(self, "btn_text_color"):
            try:
                self.btn_text_color.setProperty("force_outlined_tooltip_text", True)
                self.btn_text_color.setProperty("force_color_tooltip_text", True)
            except Exception:
                pass
            self.register_delayed_tooltip(self.btn_text_color, "문자 색상", seq_text("item_text_color"))
        if hasattr(self, "btn_stroke_color"):
            try:
                self.btn_stroke_color.setProperty("force_outlined_tooltip_text", True)
                self.btn_stroke_color.setProperty("force_color_tooltip_text", True)
            except Exception:
                pass
            self.register_delayed_tooltip(self.btn_stroke_color, "획 색상", seq_text("item_stroke_color"))
        if hasattr(self, "btn_item_text_color"):
            try:
                self.btn_item_text_color.setProperty("force_outlined_tooltip_text", True)
                self.btn_item_text_color.setProperty("force_color_tooltip_text", True)
            except Exception:
                pass
            self.register_delayed_tooltip(self.btn_item_text_color, "문자 색상", seq_text("item_text_color"))
        if hasattr(self, "btn_item_stroke_color"):
            try:
                self.btn_item_stroke_color.setProperty("force_outlined_tooltip_text", True)
                self.btn_item_stroke_color.setProperty("force_color_tooltip_text", True)
            except Exception:
                pass
            self.register_delayed_tooltip(self.btn_item_stroke_color, "획 색상", seq_text("item_stroke_color"))
        if hasattr(self, "sb_text_opacity"):
            self.register_delayed_tooltip(self.sb_text_opacity, "텍스트 불투명도", "", "선택한 텍스트의 불투명도를 조절합니다.")
        if hasattr(self, "btn_text_effect_gradient"):
            self.register_delayed_tooltip(self.btn_text_effect_gradient, "고급 텍스트/획 옵션", seq_text("text_effect_gradient"), "선택한 텍스트에 고급 텍스트/획 옵션 창을 엽니다.")
        if hasattr(self, "btn_text_effect_transform"):
            self.register_delayed_tooltip(self.btn_text_effect_transform, "텍스트 변형", seq_text("text_transform_toggle"), "선택한 텍스트의 기준 변형 모드를 켜거나 끕니다.")
        if hasattr(self, "btn_text_effect_skew"):
            self.register_delayed_tooltip(self.btn_text_effect_skew, "평행사변형 변형", seq_text("text_skew_toggle"), "선택한 텍스트를 평행사변형 형태로 기울입니다.")
        if hasattr(self, "btn_text_effect_trapezoid"):
            self.register_delayed_tooltip(self.btn_text_effect_trapezoid, "사다리꼴 변형", seq_text("text_trapezoid_toggle"), "선택한 텍스트에 좌우/상하 원근감을 적용합니다.")
        if hasattr(self, "btn_text_effect_arc"):
            self.register_delayed_tooltip(self.btn_text_effect_arc, "부채꼴 변형", seq_text("text_arc_toggle"), "선택한 텍스트를 부채꼴로 휘게 변형합니다.")
        if hasattr(self, "btn_align_left"):
            self.register_delayed_tooltip(self.btn_align_left, "왼쪽 정렬", seq_text("item_align_left"))
            self.register_delayed_tooltip(self.btn_align_center, "가운데 정렬", seq_text("item_align_center"))
            self.register_delayed_tooltip(self.btn_align_right, "오른쪽 정렬", seq_text("item_align_right"))

    def message_box_style(self):
        """확인/경고/질문창 공통 스타일. 홈 화면의 부드러운 카드 톤에 맞춘다."""
        if self.is_light_theme():
            return """
                QMessageBox, QMessageBox QWidget { background:#F5EFF3; color:#111827; }
                QMessageBox QLabel { background:#F5EFF3; color:#111827; line-height:1.35em; }
                QMessageBox QLabel, QMessageBox QFrame {
                    border:0px;
                }
                QMessageBox QTextEdit, QMessageBox QPlainTextEdit, QMessageBox QScrollArea {
                    background:#ffffff;
                    color:#111827;
                    border:1px solid #D1C9CE;
                    selection-background-color:#F5E8EA;
                    selection-color:#111827;
                }
                QMessageBox QPushButton {
                    background:#ffffff;
                    color:#111827;
                    border:1px solid #D1C9CE;
                    border-radius:0px;
                    padding:7px 18px;
                    min-width:72px;
                }
                QMessageBox QPushButton:hover { background:#FBF5F6; border-color:#D7A3A9; }
                QMessageBox QPushButton:pressed { background:#F5E8EA; }
                QMessageBox QToolTip { background-color:#ffffff; color:#111827; border:1px solid #D1C9CE; border-radius:0px; padding:5px; }
            """
        return """
            QMessageBox, QMessageBox QWidget { background:#252328; color:#F4EEF2; }
            QMessageBox QLabel { background:#252328; color:#F4EEF2; line-height:1.35em; }
            QMessageBox QLabel, QMessageBox QFrame {
                border:0px;
            }
            QMessageBox QTextEdit, QMessageBox QPlainTextEdit, QMessageBox QScrollArea {
                background:#211F23;
                color:#F4EEF2;
                border:1px solid #3A363B;
                selection-background-color:#5B3136;
                selection-color:#ffffff;
            }
            QMessageBox QPushButton {
                background:#373136;
                color:#F4EEF2;
                border:1px solid #615A60;
                border-radius:0px;
                padding:7px 18px;
                min-width:72px;
            }
            QMessageBox QPushButton:hover { background:#443A40; border-color:#7B7078; }
            QMessageBox QPushButton:pressed { background:#302C31; }
            QMessageBox QToolTip { background-color:#242329; color:#ffffff; border:1px solid #555056; border-radius:0px; padding:5px; }
        """

    def _message_button_with_shortcut(self, button, key_text):
        """QMessageBox 버튼에 문자 단축키를 붙인다. 예: Y/N."""
        try:
            button.setShortcut(QKeySequence(str(key_text)))
        except Exception:
            pass
        try:
            button.setAutoDefault(True)
        except Exception:
            pass
        return button

    def ask_yes_no_shortcut(self, title, message, yes_text="예", no_text="아니오", default_yes=True, icon=QMessageBox.Icon.Question, parent=None):
        """Enter/Y/N이 동작하는 단순 확인창. 버튼에는 반드시 (Y)/(N)을 표시한다."""
        msg = QMessageBox(parent or self)
        msg.setIcon(icon)
        msg.setWindowTitle(self.tr_ui(title))
        msg.setText(self.tr_ui(message))
        msg.setStyleSheet(self.message_box_style())
        btn_yes = msg.addButton(f"{self.tr_ui(yes_text)} (Y)", QMessageBox.ButtonRole.AcceptRole)
        btn_no = msg.addButton(f"{self.tr_ui(no_text)} (N)", QMessageBox.ButtonRole.RejectRole)
        self._message_button_with_shortcut(btn_yes, "Y")
        self._message_button_with_shortcut(btn_no, "N")
        try:
            msg.setDefaultButton(btn_yes if default_yes else btn_no)
        except Exception:
            pass
        try:
            msg.setEscapeButton(btn_no)
        except Exception:
            pass
        msg.exec()
        return msg.clickedButton() == btn_yes

    def show_ok_notice(self, title, message, parent=None):
        """확인 버튼 하나만 있는 알림창. Enter로 닫힌다."""
        msg = QMessageBox(parent or self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle(self.tr_ui(title))
        msg.setText(self.tr_ui(message))
        msg.setStyleSheet(self.message_box_style())
        btn_ok = msg.addButton(self.tr_ui("확인"), QMessageBox.ButtonRole.AcceptRole)
        try:
            msg.setDefaultButton(btn_ok)
        except Exception:
            pass
        force_message_box_front(msg)
        msg.exec()

    def _show_launcher_screen_only(self):
        """프로젝트 상태를 건드리지 않고 런처 화면만 표시한다. 내부 전용."""
        try:
            if hasattr(self, "launcher_widget"):
                self.launcher_widget.refresh()
            if hasattr(self, "main_stack") and hasattr(self, "launcher_widget"):
                self.main_stack.setCurrentWidget(self.launcher_widget)
            self.update_project_exit_button_visibility()
        except Exception:
            pass

    def clear_current_project_runtime_state(self):
        """런처로 돌아가기 위해 현재 프로젝트 세션을 완전히 닫는다."""
        try:
            if hasattr(self, "clear_pending_work_cache_save_state"):
                self.clear_pending_work_cache_save_state("clear_current_project_runtime_state")
        except Exception:
            pass
        try:
            if getattr(self, "inline_text_editor", None) is not None:
                try:
                    self.finish_inline_text_edit(commit=True, refresh=False)
                except Exception:
                    pass
            if getattr(self, "project_dir", None) and getattr(self, "paths", None):
                try:
                    self.commit_current_page_ui_to_data()
                except Exception:
                    pass
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

        try:
            if hasattr(self, "_maker_preview_new_lifecycle_token"):
                self._maker_preview_new_lifecycle_token("project_close")
        except Exception:
            pass
        try:
            if hasattr(self, "stop_progressive_page_loader"):
                self.stop_progressive_page_loader()
        except Exception:
            pass

        self.paths = []
        self.data = {}
        self.idx = 0
        self.project_store = ProjectStore()
        self.project_dir = None
        self.ysbg_package_path = None
        self.suggested_project_name = None
        self.is_temp_project = False
        self.work_project_store = None
        self.work_project_dir = None
        self.has_unsaved_changes = False
        self.undo_clear_all_pages("project close")
        self.undo_clear_project("project close")
        self.undo_boundary = None
        self.project_ui_view_states = {}
        self.magic_wand_mask = None
        self.magic_wand_seed = None
        self.magic_wand_seeds = []
        self.magic_wand_history = []
        self.text_clipboard = []
        self.text_clipboard_is_plain = False
        self.text_paste_pending = False
        # 쯔꾸르 DB/프리뷰 모드 상태도 프로젝트 생명주기에 묶어 초기화한다.
        # 프로젝트를 나가면 프리뷰는 반드시 비워져야 하며, 새 프로젝트 열기/생성 때만
        # 그 프로젝트 기준으로 다시 그린다.
        try:
            if hasattr(self, "_clear_maker_preview_display_state"):
                self._clear_maker_preview_display_state(reason="project_close")
        except Exception:
            pass

        try:
            if hasattr(self, "tab") and self.tab is not None:
                self.tab.blockSignals(True)
                self.tab.setRowCount(0)
                self.tab.blockSignals(False)
        except Exception:
            pass
        try:
            self.update_undo_redo_buttons()
        except Exception:
            pass
        try:
            self.update_window_title()
        except Exception:
            pass
        try:
            self.refresh_page_tabs()
        except Exception:
            pass
        try:
            self.update_project_exit_button_visibility()
        except Exception:
            pass

    def show_launcher(self):
        """홈화면으로 이동한다. 홈화면은 열린 프로젝트가 없는 상태여야 한다."""
        if getattr(self, "is_batch_running", False):
            QMessageBox.information(
                self,
                self.tr_ui("일괄 작업 중"),
                self.tr_ui("일괄 작업 중에는 홈화면으로 이동할 수 없습니다.\n작업이 끝난 뒤 다시 시도해 주세요."),
            )
            return

        if self.has_open_project():
            # 홈화면은 휴대폰 홈처럼 빈 상태여야 하므로, 현재 파일/프로젝트 세션을 먼저 닫는다.
            try:
                if getattr(self, "project_dir", None) and getattr(self, "paths", None):
                    self.commit_current_page_ui_to_data()
                    if getattr(self, "auto_save_enabled", False):
                        self.auto_save_project()
            except Exception as e:
                try:
                    self.log(f"⚠️ 홈화면 이동 전 현재 화면 반영 실패: {e}")
                except Exception:
                    pass

            if getattr(self, "has_unsaved_changes", False):
                if not self.confirm_unsaved_before_switch():
                    self.log("↩️ 홈화면 이동 취소")
                    return

            try:
                # 프로젝트를 나갈 때 최근 항목 썸네일을 마지막으로 보고 있던 맵 프리뷰로 갱신한다.
                self.record_current_project_recent()
            except Exception:
                pass
            self.clear_current_project_runtime_state()
            self.log("🏠 프로젝트를 닫고 홈화면으로 이동했습니다.")

        self._show_launcher_screen_only()

    def confirm_open_recent_project(self, path):
        """최근 프로젝트 카드는 바로 열지 않고 한 번 확인한다."""
        path = str(path or "")
        if not path or not os.path.exists(path):
            QMessageBox.warning(
                self,
                self.tr_ui("파일을 찾을 수 없음"),
                self.tr_msg("최근 프로젝트 파일을 찾을 수 없습니다.\n최근 목록에서 제거하거나 파일 위치를 확인해 주세요."),
            )
            return
        name = Path(path).name
        message = self.tr_msg("이 최근 프로젝트를 열까요?") + f"\n\n{name}"
        if not self.ask_yes_no_shortcut("최근 프로젝트 열기", message, yes_text="열기", no_text="취소", default_yes=True):
            self.log("↩️ 최근 프로젝트 열기 취소")
            return
        self.open_project_path(path)

    def show_editor(self):
        """런처에서 실제 작업 화면으로 전환한다."""
        try:
            if hasattr(self, "main_stack") and hasattr(self, "editor_widget"):
                self.main_stack.setCurrentWidget(self.editor_widget)
                # 에디터 화면이 실제 배치된 뒤 우측 작업 패널을 기본 폭으로 맞춘다.
                # 기본 폭은 사용자지정 콤보박스까지 잘리지 않는 상태를 기준으로 한다.
                try:
                    QTimer.singleShot(0, self.restore_editor_splitter_default_width)
                except Exception:
                    pass
            self.update_project_exit_button_visibility()
        except Exception:
            pass

    def restore_editor_splitter_default_width(self):
        """좌우 splitter를 우측 작업 패널 기준 기본 폭으로 복원한다."""
        try:
            split = getattr(self, "editor_splitter", None)
            if split is not None and hasattr(split, "reset_to_default_right_panel_width"):
                split.reset_to_default_right_panel_width()
        except Exception:
            pass

    def refresh_launcher(self):
        try:
            if hasattr(self, "launcher_widget"):
                self.launcher_widget.refresh()
        except Exception:
            pass

    def record_current_project_recent(self):
        """현재 열린 작업 폴더(project.json)를 최근 목록에 기록한다.

        쯔꾸르붕이는 평소 작업 본체를 .ysbg가 아니라 작업 폴더/project.json으로 본다.
        .ysbg는 [내보내기]에서 만드는 운반/백업용 패키지다.
        """
        try:
            project_dir = str(getattr(self, "project_dir", "") or "").strip()
            if not project_dir:
                return False
            project_file = os.path.join(project_dir, PROJECT_FILENAME)
            if not os.path.exists(project_file):
                return False
            store = getattr(self, "recent_project_store", None) or RecentProjectStore()
            self.recent_project_store = store
            title = self.display_project_name() or Path(project_dir).name
            paths_for_thumb = list(getattr(self, "paths", []) or [])
            try:
                cur_idx = int(getattr(self, "idx", 0) or 0)
                if 0 <= cur_idx < len(paths_for_thumb):
                    cur_path = paths_for_thumb[cur_idx]
                    paths_for_thumb = [cur_path] + [p for n, p in enumerate(paths_for_thumb) if n != cur_idx]
            except Exception:
                pass
            thumb = store.make_thumbnail(paths_for_thumb, project_file)
            store.add_project(
                project_file,
                title=title,
                page_count=len(getattr(self, "paths", []) or []),
                thumbnail_path=thumb,
                workspace_dir=project_dir,
            )
            self.refresh_launcher()
            return True
        except Exception as e:
            try:
                self.log(f"⚠️ 최근 프로젝트 기록 실패: {e}")
            except Exception:
                pass
            return False

    def remove_recent_project_from_launcher(self, path):
        try:
            if hasattr(self, "recent_project_store"):
                self.recent_project_store.remove_project(path)
            self.refresh_launcher()
        except Exception:
            pass

    def _find_recent_project_workspace_folder(self, package_path):
        """최근 프로젝트 카드의 .ysbg 경로에서 실제 작업 폴더를 찾는다.

        최근 프로젝트의 "폴더 위치 열기"는 .ysbg가 저장된 문서 폴더가 아니라
        workspaces 아래의 해당 프로젝트 작업 폴더를 우선 열어야 한다.
        """
        raw = str(package_path or "").strip().strip('"')
        if not raw:
            return None
        try:
            package_abs = os.path.abspath(os.path.expandvars(os.path.expanduser(raw)))
        except Exception:
            package_abs = raw

        # 현재 열려 있는 프로젝트라면 이미 알고 있는 project_dir이 가장 정확하다.
        try:
            current_dir = getattr(self, "project_dir", None)
            if current_dir and os.path.isdir(str(current_dir)):
                current_project_json = os.path.abspath(os.path.join(str(current_dir), PROJECT_FILENAME)).lower()
                if current_project_json == os.path.abspath(str(package_abs)).lower() or os.path.abspath(str(current_dir)).lower() == os.path.abspath(str(package_abs)).lower():
                    return os.path.abspath(str(current_dir))
        except Exception:
            pass


        try:
            if os.path.isdir(package_abs):
                if os.path.exists(os.path.join(package_abs, PROJECT_FILENAME)):
                    return package_abs
            if os.path.isfile(package_abs) and os.path.basename(package_abs) == PROJECT_FILENAME:
                return os.path.dirname(package_abs)
        except Exception:
            pass
        manifest = {}
        project_uuid = ""
        try:
            if os.path.isfile(package_abs):
                manifest = read_ysb_manifest(package_abs) or {}
                project_uuid = str(manifest.get("project_uuid") or "")
        except Exception:
            manifest = {}
            project_uuid = ""

        try:
            root = Path(str(workspaces_dir()))
            if not root.exists():
                return None

            package_key = os.path.abspath(str(package_abs)).lower()
            uuid_match = None
            for child in root.iterdir():
                try:
                    if not child.is_dir():
                        continue
                    if not (child / PROJECT_FILENAME).exists():
                        continue
                    manifest_path = child / "manifest.json"
                    if not manifest_path.exists():
                        continue
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        m = json.load(f)
                    if not isinstance(m, dict):
                        continue
                    src = str(m.get("package_source") or "")
                    src_key = os.path.abspath(src).lower() if src else ""
                    child_uuid = str(m.get("project_uuid") or "")

                    # 같은 .ysbg 경로가 기록된 폴더를 최우선으로 연다.
                    if src_key and src_key == package_key:
                        if (not project_uuid) or (child_uuid == project_uuid):
                            return str(child)
                    # 예전 기록처럼 package_source가 없거나 경로가 바뀐 경우 UUID로 보조 매칭한다.
                    if project_uuid and child_uuid == project_uuid and uuid_match is None:
                        uuid_match = str(child)
                except Exception:
                    continue
            if uuid_match:
                return uuid_match

            # 예상 폴더명도 한 번 더 확인한다.
            if project_uuid:
                expected = root / f"{clean_workspace_name(Path(package_abs).stem)}_{project_uuid[:8]}"
                if expected.exists() and expected.is_dir():
                    return str(expected)
        except Exception:
            pass
        return None

    def _open_path_location_in_file_manager(self, path, select_file=True):
        """파일/폴더 위치를 OS 파일 관리자에서 연다.

        Windows에서 QDesktopServices.openUrl(QUrl.fromLocalFile(folder))만 쓰면
        상대경로/현재 작업 디렉터리 상태에 따라 바탕화면이나 문서 폴더 같은
        엉뚱한 위치가 열릴 수 있어, Windows에서는 explorer.exe를 직접 호출한다.
        """
        raw = str(path or "").strip().strip('"')
        if not raw:
            raise FileNotFoundError(self.tr_ui("최근 프로젝트 파일을 찾을 수 없습니다.\n최근 목록에서 제거하거나 파일 위치를 확인해 주세요."))

        raw = os.path.expandvars(os.path.expanduser(raw))
        target = os.path.abspath(raw)

        if os.path.isfile(target):
            folder = os.path.dirname(target)
            if sys.platform.startswith("win") and select_file:
                # 파일 위치를 열면서 해당 .ysbg 파일을 선택한다.
                # 리스트 인자로 넘겨 공백/한글 경로를 안전하게 처리한다.
                subprocess.Popen(["explorer.exe", f"/select,{target}"])
                return target
        elif os.path.isdir(target):
            folder = target
        else:
            folder = os.path.dirname(target)
            if not folder or not os.path.isdir(folder):
                raise FileNotFoundError(target)

        folder = os.path.abspath(folder)
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer.exe", folder])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        return folder

    def reveal_recent_project_in_folder(self, path):
        """최근 프로젝트 카드의 [폴더 위치 열기].

        이 메뉴에서 말하는 위치는 내부 작업 폴더(workspaces)가 아니라
        사용자가 저장한 .ysbg 파일이 있는 폴더다.
        이전 패치에서 작업 폴더를 우선 열도록 바꾸면서 여러 최근 항목이
        모두 문서/YSB_Translator/workspaces 쪽으로 열리는 혼동이 생겼으므로
        여기서는 항상 recent_projects.json에 기록된 .ysbg_path 기준으로 연다.
        """
        try:
            self._open_path_location_in_file_manager(path, select_file=False)
        except Exception as e:
            QMessageBox.warning(self, self.tr_ui("폴더 열기 실패"), str(e))

    def open_current_project_work_folder(self):
        """현재 열려 있는 프로젝트의 실제 작업 폴더를 탐색기에서 연다."""
        project_dir = getattr(self, "project_dir", None)
        if not project_dir:
            QMessageBox.information(
                self,
                self.tr_ui("작업 폴더 열기"),
                self.tr_ui("현재 열린 프로젝트가 없습니다."),
            )
            return
        folder = os.path.abspath(str(project_dir))
        if not os.path.isdir(folder):
            QMessageBox.warning(
                self,
                self.tr_ui("작업 폴더 열기 실패"),
                f"{self.tr_ui('현재 프로젝트 작업 폴더를 찾을 수 없습니다.')}\n\n{folder}",
            )
            return
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
            self.log(f"📁 {self.tr_ui('현재 프로젝트 작업 폴더를 열었습니다.')}: {folder}")
        except Exception as e:
            QMessageBox.warning(self, self.tr_ui("작업 폴더 열기 실패"), str(e))


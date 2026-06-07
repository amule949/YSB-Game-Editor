from ysb.ui.main_window_support import *
from ysb.core.page_engine import YSBPageEngine
from ysb.core.project_engine import YSBProjectEngine
from ysb.core.view_engine import YSBViewEngine
from ysb.core.text_engine import YSBGextEngine
from ysb.core.mask_engine import YSBMaskEngine
from ysb.core.layer_engine import YSBLayerEngine
from ysb.core.undo_manager import YSBUndoManager
from ysb.core.engine_boundary_audit import YSBEngineBoundaryAudit
from ysb.ui.main_window_interaction_mixin import MainWindowInteractionMixin
from ysb.ui.main_window_settings_theme_mixin import MainWindowSettingsThemeMixin
from ysb.ui.main_window_text_layout_mixin import MainWindowTextLayoutMixin
from ysb.ui.main_window_project_pages_mixin import MainWindowProjectPagesMixin
from ysb.ui.undo_command_push_mixin import UndoCommandPushMixin
from ysb.ui.undo_command_apply_mixin import UndoCommandApplyMixin
from ysb.ui.main_window_history_mixin import MainWindowHistoryMixin
from ysb.ui.main_window_operations_mixin import MainWindowOperationsMixin
from ysb.utils.runtime_logger import append_log, install_faulthandler_log, log_dir, make_log_path, memory_text, write_fatal_exception_log
from ysb.ui.bug_report_dialog import maybe_prompt_previous_fatal_report
from ysb.core.crash_reporter import start_crash_session_marker, mark_crash_session_clean


class MainWindow(MainWindowInteractionMixin, MainWindowSettingsThemeMixin, MainWindowTextLayoutMixin, UndoCommandPushMixin, UndoCommandApplyMixin, MainWindowProjectPagesMixin, MainWindowHistoryMixin, MainWindowOperationsMixin, QMainWindow):

    def audit_boundary_event(self, event, **fields):
        """Best-effort audit for PageEngine/ProjectEngine boundary leaks."""
        try:
            audit = getattr(self, "engine_boundary_audit", None)
            if audit is None:
                return
            try:
                mode = int(self.cb_mode.currentIndex()) if hasattr(self, "cb_mode") else None
            except Exception:
                mode = None
            try:
                pe = getattr(self, "project_engine", None)
                dirty_summary = pe.dirty_summary() if pe is not None and hasattr(pe, "dirty_summary") else None
            except Exception:
                dirty_summary = None
            try:
                session = getattr(self, "active_page_session", None)
                page_dirty = sorted(getattr(session, "dirty_kinds", set()) or []) if session is not None else []
            except Exception:
                page_dirty = []
            audit.note(
                event,
                page_idx=getattr(self, "idx", None),
                mode=mode,
                is_page_loading=bool(getattr(self, "is_page_loading", False)),
                is_batch_running=bool(getattr(self, "is_batch_running", False)),
                is_autosaving=bool(getattr(self, "is_autosaving", False)),
                has_unsaved=bool(getattr(self, "has_unsaved_changes", False)),
                page_dirty=page_dirty,
                project_dirty=dirty_summary,
                **fields,
            )
        except Exception:
            pass

    def audit_top_level_widgets(self, reason="manual", *, throttle_ms=500):
        """Log currently visible top-level widgets to find stray python taskbar windows."""
        try:
            audit = getattr(self, "engine_boundary_audit", None)
            if audit is None:
                return
            widgets = QApplication.topLevelWidgets()
            summary = audit.widget_summary(widgets)
            suspects = [x for x in summary if "suspect=True" in x]
            audit.note(
                "TOP_LEVEL_WIDGETS",
                throttle_ms=throttle_ms,
                reason=reason,
                count=len(summary),
                suspect_count=len(suspects),
                suspects=" || ".join(suspects[:12]),
                widgets=" || ".join(summary[:20]),
            )
        except Exception:
            pass

    def __init__(self):
        super().__init__()
        # setup_ui() 도중 일부 도구 초기화가 log()를 호출할 수 있다.
        # 이 시점에는 아직 로그 위젯이 만들어지지 않았으므로 임시 버퍼에 보관한다.
        self._pending_log_messages = []
        self.engine_boundary_audit = None
        self.update_window_title()
        self.setWindowIcon(QIcon(resource_path("ysb_icon.ico")))
        self.resize(1740, 1040)
        self.setAcceptDrops(True)

        self.api_settings = ApiSettingsStore.load()
        apply_settings_to_config(self.api_settings)
        self.engine = None
        self.restart_engine(show_error=False)

        self.paths = []
        self.idx = 0
        self.data = {}
        # 엔진 분리 1차: ProjectEngine은 저장/페이지 구조만, PageEngine은 현재 페이지 작업실만 담당한다.
        # Undo 1차 리팩토링: 새 기능은 UndoManager 관문을 통해 들어오게 하고,
        # 내부 구현은 기존 HistoryMixin 스택으로 위임한다.
        self.undo_manager = YSBUndoManager(self)
        self.project_engine = YSBProjectEngine()
        self.page_engine = YSBPageEngine(on_dirty=lambda page_idx, kind: self.project_engine.mark_page_dirty(page_idx, kind))
        self.view_engine = YSBViewEngine(
            capture_state=lambda: self.capture_view_state(),
            apply_state=lambda state: self.apply_view_state(state),
            on_push_undo=lambda rec, page_idx: self.push_view_state_command_from_record(rec, page_idx=page_idx),
        )
        self.text_engine = YSBGextEngine(on_dirty=lambda page_idx, kind: self.page_engine.mark_dirty(page_idx, kind))
        self.mask_engine = YSBMaskEngine(on_dirty=lambda page_idx, kind: self.page_engine.mark_dirty(page_idx, kind))
        self.layer_engine = YSBLayerEngine(on_push_undo=lambda rec, page_idx: self.push_work_tab_command_from_record(rec, page_idx=page_idx))
        self.active_page_session = self.page_engine.current
        self.page_image_cache_limit = 3
        self.page_mask_cache_limit = 3
        self._page_image_cache_order = OrderedDict()
        self._page_mask_cache_order = OrderedDict()

        self.project_store = ProjectStore()
        self.project_dir = None
        self.workspace_root = str(get_workspace_root())
        self.ysbg_package_path = None
        self.suggested_project_name = None
        self.is_temp_project = False
        self.is_loading_project = False
        self.is_autosaving = False
        self._busy_counter = 0
        self._busy_reason_stack = []
        self._busy_widgets = []

        self.app_options = load_app_options()
        try:
            self.engine_boundary_audit = YSBEngineBoundaryAudit(enabled=bool(self.app_options.get("engine_boundary_audit_enabled", True)))
            self.audit_boundary_event("APP_INIT", phase="after_app_options")
        except Exception:
            self.engine_boundary_audit = None
        try:
            self.page_image_cache_limit = max(1, int(self.app_options.get("page_image_cache_limit", self.page_image_cache_limit) or self.page_image_cache_limit))
        except Exception:
            self.page_image_cache_limit = 3
        try:
            self.page_mask_cache_limit = max(1, int(self.app_options.get("page_mask_cache_limit", self.page_mask_cache_limit) or self.page_mask_cache_limit))
        except Exception:
            self.page_mask_cache_limit = 3
        self.sync_translation_option_cache_to_config()
        self.sync_analysis_mask_options_to_config()

        # 저장본/작업 캐시 분리
        # v2.4 QA6: YSBG 패키지 구조에서는 실시간 자동저장을 폐지한다.
        # 모든 일반 편집 변경은 복구용 작업 캐시에만 저장하고, 실제 .ysbg 반영은
        # 사용자가 [프로젝트 내보내기]/[다른 이름으로 내보내기]을 눌렀을 때만 확정한다.
        self.auto_save_enabled = False
        self.app_options["auto_save_enabled"] = False
        self.ui_theme = str(self.app_options.get(UI_THEME_KEY, THEME_DARK) or THEME_DARK).lower()
        if self.ui_theme not in (THEME_DARK, THEME_LIGHT):
            self.ui_theme = THEME_DARK
        self.ui_language = normalize_ui_language(self.app_options.get(UI_LANGUAGE_KEY, LANG_KO))
        self.analysis_number_box_width = int(self.app_options.get("analysis_number_box_width", 40) or 40)
        self.page_tab_display_name_mode = normalize_page_display_mode(self.app_options.get(PAGE_TAB_DISPLAY_MODE_KEY, DEFAULT_PAGE_DISPLAY_MODE))
        self.output_display_name_mode = normalize_page_display_mode(self.app_options.get(OUTPUT_DISPLAY_MODE_KEY, DEFAULT_PAGE_DISPLAY_MODE))
        self.output_image_format = normalize_output_image_format(self.app_options.get(OUTPUT_IMAGE_FORMAT_KEY, DEFAULT_OUTPUT_IMAGE_FORMAT))
        self.clean_image_format = normalize_output_image_format(self.app_options.get(CLEAN_IMAGE_FORMAT_KEY, DEFAULT_OUTPUT_IMAGE_FORMAT))
        self.output_image_quality = normalize_output_image_quality(self.app_options.get(OUTPUT_IMAGE_QUALITY_KEY, DEFAULT_OUTPUT_IMAGE_QUALITY))
        self.clean_image_quality = normalize_output_image_quality(self.app_options.get(CLEAN_IMAGE_QUALITY_KEY, DEFAULT_OUTPUT_IMAGE_QUALITY))
        self.output_text_render_quality = normalize_output_text_render_quality(self.app_options.get(OUTPUT_TEXT_RENDER_QUALITY_KEY, DEFAULT_OUTPUT_TEXT_RENDER_QUALITY))
        self.show_paths_in_log = bool(self.app_options.get(SHOW_PATHS_IN_LOG_KEY, False))
        self.show_cache_paths_in_settings = bool(self.app_options.get(SHOW_CACHE_PATHS_IN_SETTINGS_KEY, False))
        self.interface_tooltips_enabled = bool(self.app_options.get("interface_tooltips_enabled", True))
        # 텍스트 이펙트 미리보기는 페이지별 설정이다.
        # 기본값은 항상 ON이며, 후광/그림자/2중 획이 무거운 페이지에서만 사용자가 끈다.
        # 예전 전역 캐시값이 False로 남아 있더라도 새 페이지/기본값에는 영향을 주지 않게 한다.
        self.text_effect_preview_default_enabled = True
        self.text_effect_preview_enabled = True
        # 화면 이동/확대 Undo는 실작업에서 중요하므로 기본 ON이다. 연속 조작은 viewer/main에서 묶어 기록한다.
        self.view_navigation_undo_enabled = bool(self.app_options.get("view_navigation_undo_enabled", True))
        # Windows native QFileDialog가 느린 환경이 있어 기본은 경량 Qt 파일창을 사용한다.
        # 설정 / 옵션에서 끌 수 있다.
        self.use_light_file_dialog = bool(self.app_options.get("use_light_file_dialog", True))
        self.log_panel_collapsed = bool(self.app_options.get(LOG_PANEL_COLLAPSED_KEY, DEFAULT_LOG_PANEL_COLLAPSED))
        self.work_project_store = None
        self.work_project_dir = None
        self.has_unsaved_changes = False
        self._closing_confirmed = False
        # 종료 처리 중에는 focusOut/QTimer가 삭제된 QGraphicsScene에 접근하지 못하게 막는다.
        self._app_is_closing = False

        # 일괄 작업/페이지 로딩 중에는 화면에 남아 있는 마스크를
        # 현재 페이지 데이터에 자동 저장하면 안 된다.
        self.is_batch_running = False
        self.is_page_loading = False
        self.current_batch_mode = None

        self.inline_text_editor = None
        self.inline_text_target = None

        self.text_clipboard = []
        self.text_clipboard_is_plain = False
        self.text_paste_pending = False
        self.last_canvas_context_pos = None

        self.last_mode = 0
        self._current_work_mode = 0
        self._global_event_filter_installed = False

        # 번역 묶음 수: 한 번의 API 요청에 몇 줄을 묶어 보낼지.
        # v2.1.0: 상단 툴바에서는 숨기고 API 관리 > 번역 탭에서 제공자별로 관리한다.
        self.trans_chunk_sizes = {
            "openai": int(getattr(self.api_settings, "openai_chunk_size", 50) or 50),
            "deepseek": int(getattr(self.api_settings, "deepseek_chunk_size", 50) or 50),
            "google": int(getattr(self.api_settings, "google_translate_chunk_size", 50) or 50),
            "gemini": int(getattr(self.api_settings, "gemini_chunk_size", 50) or 50),
            "custom": int(getattr(self.api_settings, "custom_translation_chunk_size", 50) or 50),
        }

        self.default_text_color = "#000000"
        self.default_stroke_color = "#FFFFFF"
        self.default_line_spacing = 100
        self.default_letter_spacing = 0
        self.default_char_width = 100
        self.default_char_height = 100
        self.default_bold = False
        self.default_italic = False
        self.default_strike = False
        self.final_paint_color = "#FFFFFF"
        self.final_paint_above_text = False
        self.final_paint_opacity = 100
        self.default_align = "center"
        self.mask_toggle_enabled = False
        self.magic_wand_mask = None
        self.magic_wand_seed = None
        self.magic_wand_seeds = []
        self.magic_wand_history = []
        self._style_signal_lock = False
        self._preset_loading = False
        self._syncing_selection = False
        self._table_check_lock = False
        self.text_presets = {}

        self.shortcut_settings = ShortcutSettingsStore.load()
        self.actions = {}
        self.macro_actions = []
        self.item_preset_actions = []
        self.item_text_presets = {}
        self._item_preset_loading = False
        self._item_preset_signal_lock = False
        self.shortcut_label_map = shortcut_label_map()

        # 매크로 실행 큐
        # 비동기 작업(분석/인페인팅/일괄 작업)은 완료 콜백을 받아야 다음 단계로 넘어간다.
        self.macro_running = False
        self.macro_queue = []
        self.macro_current = None
        self.macro_waiting_key = None
        self.macro_waiting_kind = None
        self.macro_current_name = ""
        self._suppress_project_undo = False
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.timeout.connect(self._show_delayed_tooltip)
        self._tooltip_target = None
        self._tooltip_visible_target = None
        self._tooltip_html = ""
        self._tooltip_popup = None

        # 현재 페이지/프로젝트 Undo 스택.
        # 3단계-2부터 실제 컨테이너 소유권은 UndoManager가 가진다.
        # 아래 속성들은 구버전 코드 호환용 alias로만 유지한다.
        # 쯔꾸르붕이 Undo 정책:
        # 전역 작업 Undo/Redo는 끄고, 현재 텍스트 입력칸의 Qt 기본 Undo/Redo만 허용한다.
        self.maker_text_input_only_undo = True
        try:
            self.undo_manager.ensure_stack_state()
        except Exception:
            pass
        self.page_undo_stacks = self.undo_manager.page_undo_stacks
        self.page_redo_stacks = self.undo_manager.page_redo_stacks
        self.page_view_undo_stacks = self.undo_manager.page_view_undo_stacks
        self.page_view_redo_stacks = self.undo_manager.page_view_redo_stacks
        # 구버전 호환 이름: 일부 함수가 아직 page_text_undo_stacks를 참조한다.
        self.page_text_undo_stacks = self.page_undo_stacks
        # 표/화면 동기화 중에는 텍스트 undo 스냅샷을 만들지 않는다.
        self._text_undo_restore_lock = False
        # Command/Diff Undo 적용 중에는 새 command session을 만들지 않는다.
        self._command_undo_restore_lock = False
        # 자동저장 직전 화면의 텍스트 아이템 좌표를 data에 반영할 때 재진입을 막는다.
        self._text_scene_sync_lock = False

        # 프로젝트 구조 변경 전용 Undo 스택도 UndoManager가 소유하고,
        # MainWindow 쪽 이름은 alias로 남긴다.
        self.project_undo_stack = self.undo_manager.project_undo_stack
        self.project_redo_stack = self.undo_manager.project_redo_stack
        self._project_undo_restore_lock = False
        self._deferred_undo_records = {}
        # 매크로/글꼴 프리셋처럼 Undo 기록을 남기지 않는 작업은
        # 과거 Undo로 되돌아가면 상태가 꼬일 수 있으므로 Undo 경계를 세운다.
        self.undo_boundary = None
        self.macro_executed_any = False
        self.macro_has_undo_boundary = False
        self.macro_undo_record = None
        self._macro_allow_undo_append = False
        self.project_ui_view_states = {}
        self.suggested_package_dir = None

        self.setup_actions()
        self.setup_ui()
        self._last_show_final_text_checked = bool(self.cb_show_final_text.isChecked()) if hasattr(self, "cb_show_final_text") else True
        self._last_final_paint_above_text = bool(getattr(self, "final_paint_above_text", False))
        self.load_text_preset_cache()
        self.load_item_text_preset_cache()
        self.setup_menu()
        self.apply_theme(self.ui_theme)
        self.apply_shortcuts()
        self.apply_language(self.ui_language)
        self.install_global_input_filter()
        # 오래된 임시 작업 폴더는 한 달에 한 번 자동 정리한다.
        QTimer.singleShot(1500, self.auto_cleanup_temp_files_if_needed)

        # .ysbg 더블클릭 전용 경량 런처가 남긴 열기 요청을 감시한다.
        # 이미 켜진 앱에 파일 경로만 전달해 드래그앤드롭과 같은 빠른 열기를 구현한다.
        self.setup_external_open_queue_monitor()

        # 사이트 버전 확인은 시작 후 백그라운드에서 조용히 수행한다.
        # 인터넷이 없거나 실패해도 프로그램 사용에는 영향을 주지 않는다.
        QTimer.singleShot(2500, self.start_auto_version_check)

    def showEvent(self, event):
        try:
            super().showEvent(event)
        finally:
            self.schedule_native_title_bar_theme(self, dark=not self.is_light_theme())

    def changeEvent(self, event):
        try:
            super().changeEvent(event)
        finally:
            try:
                if event.type() in (
                    QEvent.Type.WindowStateChange,
                    QEvent.Type.PaletteChange,
                    QEvent.Type.StyleChange,
                ):
                    self.schedule_native_title_bar_theme(self, dark=not self.is_light_theme())
            except Exception:
                pass


def exception_hook(exctype, value, traceback):
    global _handling_fatal_exception
    import traceback as tb
    error_msg = "".join(tb.format_exception(exctype, value, traceback))
    fatal_log_path = write_fatal_exception_log(exctype, value, traceback, error_msg)
    print(error_msg)

    # 예외 표시 중 Qt 이벤트가 다시 들어와 같은 예외를 반복 발생시키면
    # CMD에 무한히 쌓이고 프로그램 종료가 늦어진다. 한 번만 다이얼로그를 띄운다.
    if _handling_fatal_exception:
        try:
            sys.__stderr__.write(error_msg + "\n")
        except Exception:
            pass
        sys.exit(1)

    _handling_fatal_exception = True
    try:
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("python")
        msg_box.setText("치명적인 오류 발생!")
        info = str(value)
        if fatal_log_path:
            info += f"\n\n로그 저장 위치: {fatal_log_path}"
        msg_box.setInformativeText(info)
        msg_box.setDetailedText(error_msg)
        apply_message_box_dark_palette(msg_box)
        force_message_box_front(msg_box)
        msg_box.exec()
    except Exception:
        pass
    sys.exit(1)


def _exec_app_with_clean_crash_session(app):
    """Run QApplication and mark the startup session clean only on normal exit."""
    try:
        ret = app.exec()
        try:
            mark_crash_session_clean()
        except Exception:
            pass
        sys.exit(ret)
    except SystemExit:
        # If app.exec() returned and sys.exit() raises, the session was already
        # marked clean above. If a SystemExit is raised earlier, leave marker state
        # as-is so abnormal startup exits can be diagnosed conservatively.
        raise


def _exit_clean_after_startup_cancel(code=0):
    try:
        mark_crash_session_clean()
    except Exception:
        pass
    sys.exit(code)


def _schedule_startup_external_open(window, open_arg, *, delay_ms=260):
    """Defer command-line/.ysbg startup open until the home screen has painted.

    When the app is launched by double-clicking a .ysbg file, opening the package
    synchronously during startup can hide the launcher/home screen and progress
    overlay until the extraction has already finished.  Always show the main
    window first, let Qt process at least one paint cycle, then enter the normal
    home-screen open path.
    """
    if not open_arg:
        return
    try:
        open_arg = str(open_arg)
    except Exception:
        return

    try:
        setattr(window, "_startup_external_open_pending", True)
    except Exception:
        pass

    def _run_open():
        try:
            try:
                setattr(window, "_startup_external_open_pending", False)
            except Exception:
                pass
            try:
                window.show()
                window.raise_()
                window.activateWindow()
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            except Exception:
                pass
            try:
                if hasattr(window, "audit_boundary_event"):
                    window.audit_boundary_event("STARTUP_EXTERNAL_OPEN_DEFERRED_RUN", path=open_arg)
            except Exception:
                pass
            window.open_project_path(open_arg, external_request=True)
        except Exception as e:
            try:
                QMessageBox.critical(window, window.tr_ui("YSBG 열기 실패"), f"{window.tr_ui('YSBG 프로젝트를 열지 못했습니다.')}\n{open_arg}\n\n{e}")
            except Exception:
                pass

    try:
        if hasattr(window, "audit_boundary_event"):
            window.audit_boundary_event("STARTUP_EXTERNAL_OPEN_DEFERRED", path=open_arg, delay_ms=delay_ms)
    except Exception:
        pass
    QTimer.singleShot(int(delay_ms), _run_open)


def run_app() -> None:
    sys.excepthook = exception_hook
    fault_log_path = install_faulthandler_log()
    runtime_log_path = make_log_path("ysb_runtime")
    append_log(
        runtime_log_path,
        "APP RUN START",
        edition=APP_EDITION,
        executable=getattr(sys, "executable", ""),
        frozen=getattr(sys, "frozen", False),
        log_dir=log_dir(),
        fault_log=fault_log_path or "",
        memory=memory_text(),
    )

    # Windows 작업표시줄이 PyQt 기본 아이콘 대신 앱 아이콘을 잡도록 지정한다.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"YSB.YeoksikBoongi.Tool.{APP_EDITION}")
    except Exception:
        pass

    app = QApplication(sys.argv)

    # Windows/Qt combo popups can appear to flash because menu/combo fade/animation
    # draws the popup frame and list in separate passes. Disable UI effects globally
    # so compact right-panel combo boxes open in a single, steadier step.
    try:
        for _effect in (
            Qt.UIEffect.UI_AnimateCombo,
            Qt.UIEffect.UI_FadeMenu,
            Qt.UIEffect.UI_AnimateMenu,
            Qt.UIEffect.UI_AnimateTooltip,
        ):
            try:
                QApplication.setEffectEnabled(_effect, False)
            except Exception:
                pass
    except Exception:
        pass

    close_pyinstaller_boot_splash()

    # 두 번째 실행이면 기존 프로세스에 열기 요청만 전달하고 종료한다.
    # 이 경로에서는 어떤 스플래시도 만들지 않는다.
    if notify_running_instance(sys.argv[1:]):
        sys.exit(0)

    single_instance_server = SingleInstanceServer()
    if not single_instance_server.start():
        QMessageBox.warning(None, "단일 실행 경고", "단일 실행 서버를 시작하지 못했습니다.\n프로그램은 계속 실행되지만 중복 실행 차단이 정상 동작하지 않을 수 있습니다.")

    try:
        start_crash_session_marker(runtime_log_path=runtime_log_path, faulthandler_log_path=fault_log_path)
    except Exception:
        pass
    try:
        app.aboutToQuit.connect(mark_crash_session_clean)
    except Exception:
        pass

    app.setWindowIcon(QIcon(resource_path("ysb_icon.ico")))

    launcher_owned = is_launcher_splash_owner()
    write_launcher_mode_debug("after_launcher_owned_check")
    if launcher_owned:
        # 런처가 55%에서 멈추지 않도록, 런처 모드 판정 직후 즉시 진행률을 남긴다.
        report_launcher_progress(56, translate_ui_text("메인 초기화 시작 중..."))

    # 런처가 시작한 경우:
    # - 메인 스플래시는 절대 만들지 않는다.
    # - 메인은 런처의 단일 스플래시에 진행률만 보고한다.
    if launcher_owned:
        write_main_startup_signal()
        write_launcher_mode_debug("after_startup_signal")
        report_launcher_progress(58, translate_ui_text("환경 준비 중..."))

        # 작업 폴더 설정창 같은 실제 입력창이 필요하면, 런처를 먼저 닫게 한다.
        try:
            needs_setup, _reason, _kind = workspace_root_needs_setup()
        except Exception:
            needs_setup = False
        if needs_setup:
            report_launcher_progress(100, translate_ui_text("설정 화면으로 전환 중..."), done=True)
            wait_for_launcher_closed_if_needed()
            if not run_initial_workspace_setup_if_needed():
                _exit_clean_after_startup_cancel(0)
        else:
            if not run_initial_workspace_setup_if_needed():
                _exit_clean_after_startup_cancel(0)

        # 런처가 확장자 사전 확인을 처리한 경우 메인은 중복 알림을 띄우지 않는다.
        report_launcher_progress(65, translate_ui_text("환경 준비 중..."))
        prompt_update_ysbt_file_association_if_needed(None)

        report_launcher_progress(78, translate_ui_text("인터페이스 로딩 중..."))
        w = MainWindow()
        single_instance_server.set_main_window(w)

        report_launcher_progress(92, translate_ui_text("화면 구성 마무리 중..."))
        w.setWindowIcon(QIcon(resource_path("ysb_icon.ico")))

        startup_open_arg = None
        try:
            if len(sys.argv) > 1:
                startup_open_arg = sys.argv[1]
        except Exception:
            startup_open_arg = None

        report_launcher_progress(100, translate_ui_text("시작 완료"), done=True)
        wait_for_launcher_closed_if_needed()
        w.show()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        if startup_open_arg:
            _schedule_startup_external_open(w, startup_open_arg, delay_ms=280)
        QTimer.singleShot(1200, lambda: maybe_prompt_previous_fatal_report(w))
        _exec_app_with_clean_crash_session(app)

    # 메인 EXE 직접 실행:
    # - 런처가 폴더에 있더라도 호출하지 않는다.
    # - 메인 스플래시만 표시한다.
    if not run_initial_workspace_setup_if_needed():
        _exit_clean_after_startup_cancel(0)

    prompt_update_ysbt_file_association_if_needed(None)

    splash = make_splash_screen()
    if splash is not None:
        splash.set_progress(45, translate_ui_text("환경 준비 중..."))

    if splash is not None:
        splash.set_progress(62, translate_ui_text("인터페이스 로딩 중..."))

    w = MainWindow()
    single_instance_server.set_main_window(w)

    if splash is not None:
        splash.set_progress(88, translate_ui_text("화면 구성 마무리 중..."))

    w.setWindowIcon(QIcon(resource_path("ysb_icon.ico")))
    w.show()

    startup_open_arg = None
    try:
        if len(sys.argv) > 1:
            startup_open_arg = sys.argv[1]
    except Exception:
        startup_open_arg = None

    if splash is not None:
        splash.set_progress(100, translate_ui_text("시작 완료"))
        splash.stop()
        QApplication.processEvents()
        QTimer.singleShot(120, lambda: splash.finish(w))

    # Command-line/file-association opens must be deferred until the main home
    # screen has actually painted.  Otherwise double-clicking a .ysbg while the
    # app is closed can appear to skip the home screen and extraction progress.
    if startup_open_arg:
        _schedule_startup_external_open(w, startup_open_arg, delay_ms=320)

    QTimer.singleShot(1200, lambda: maybe_prompt_previous_fatal_report(w))
    _exec_app_with_clean_crash_session(app)


if __name__ == "__main__":
    run_app()

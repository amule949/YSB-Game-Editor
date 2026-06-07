from ysb.ui.main_window_support import *

class _MakerFixedModeState:
    """쯔꾸르붕이 전용 고정 프리뷰 모드 상태.

    과거 YSB 작업탭(QComboBox)을 실제 UI에서 제거한 뒤에도,
    아직 남은 내부 렌더/Undo 코드가 currentIndex()/setCurrentIndex() 형태를
    호출할 수 있어서 위젯이 아닌 상태 객체로만 호환한다.
    """

    def __init__(self, owner, mode=4):
        self.owner = owner
        self._mode = int(mode)

    def currentIndex(self):
        try:
            return int(getattr(self.owner, "last_mode", self._mode) or self._mode)
        except Exception:
            return self._mode

    def setCurrentIndex(self, value):
        try:
            self._mode = int(value)
        except Exception:
            self._mode = 4
        try:
            self.owner.last_mode = self._mode
            self.owner._current_work_mode = self._mode
        except Exception:
            pass

    def count(self):
        return 5

    def blockSignals(self, blocked):
        return False

    def hide(self):
        return None

    def setVisible(self, visible):
        return None

    def setEnabled(self, enabled):
        return None

    def setItemText(self, index, text):
        return None



class MainWindowSettingsThemeMixin:

    def settings_dialog_style(self):
        """통합 설정/옵션 계열 창 전용 몽글 카드 스타일."""
        if self.is_light_theme():
            return """
                QDialog { background:#F5EFF3; color:#242329; }
                QScrollArea { background:transparent; border:0; }
                QLabel { color:#242329; }
                QFrame#SettingsBlock {
                    background:#ffffff;
                    border:1px solid #DED8DC;
                    border-radius:16px;
                }
                QFrame#SettingsItem {
                    background:#f9fbfe;
                    border:1px solid #E7E1E5;
                    border-radius:14px;
                }
                QLabel#SettingsItemTitle { font-size:13px; font-weight:700; color:#211F23; }
                QLabel#SettingsTitle, QLabel#SettingsDialogTitle { font-size:22px; font-weight:800; color:#211F23; }
                QLabel#SettingsSectionTitle { font-size:16px; font-weight:750; color:#211F23; }
                QLabel#SettingsDescription { color:#6F666D; line-height:140%; }
                QLabel#SettingsPath {
                    color:#6F666D;
                    background:#F2EDEF;
                    border:1px solid #E3DDE1;
                    border-radius:0px;
                    padding:3px 6px;
                }
                QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QFontComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {
                    background:#ffffff;
                    color:#242329;
                    border:1px solid #D1C9CE;
                    border-radius:0px;
                    padding:3px 6px;
                    selection-background-color:#F5E8EA;
                    selection-color:#111827;
                }
                QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QFontComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QKeySequenceEdit:focus {
                    border:1px solid #C78A90;
                    background:#ffffff;
                }
QCheckBox, QRadioButton { color:#242329; spacing:9px; }
                QCheckBox::indicator, QRadioButton::indicator {
                    width:15px; height:15px;
                    border:1px solid #aab4c3;
                    background:#ffffff;
                    border-radius:0px;
                }
                QRadioButton::indicator { border-radius:0px; }
                QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                    background:#A85D66;
                    border:1px solid #A85D66;
                }
                QPushButton {
                    background:#FAF5F7;
                    color:#242329;
                    border:1px solid #D1C9CE;
                    border-radius:0px;
                    padding:4px 10px;
                }
                QPushButton:hover { background:#FBF5F6; border-color:#D7A3A9; }
                QPushButton:pressed { background:#F5E8EA; }
                QPushButton:disabled { background:#F0EAED; color:#A29A9F; border-color:#E0DADF; }
                QTabWidget::pane { border:1px solid #DED8DC; border-radius:0px; background:#ffffff; }
                QTabBar::tab {
                    background:#EEEFF3;
                    color:#555056;
                    border:1px solid #DAD4D8;
                    border-bottom:none;
                    border-top-left-radius:10px;
                    border-top-right-radius:3px;
                    padding:4px 10px;
                }
                QTabBar::tab:selected { background:#ffffff; color:#211F23; font-weight:700; }
                QListWidget, QTableWidget, QTreeWidget {
                    background:#ffffff;
                    color:#242329;
                    border:1px solid #DED8DC;
                    border-radius:0px;
                    alternate-background-color:#F8F3F5;
                    selection-background-color:#F5E8EA;
                    selection-color:#111827;
                }
                QHeaderView::section {
                    background:#F2EDEF;
                    color:#374151;
                    border:0;
                    border-right:1px solid #DED8DC;
                    padding:7px;
                }
                QScrollBar:vertical { background:#F1ECEF; width:12px; margin:0; border:0; border-radius:0px; }
                QScrollBar::handle:vertical { background:#CBC4C9; min-height:30px; border-radius:0px; }
                QScrollBar::handle:vertical:hover { background:#b7c3d4; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
                QScrollBar:horizontal { background:#F1ECEF; height:12px; margin:0; border:0; border-radius:0px; }
                QScrollBar::handle:horizontal { background:#CBC4C9; min-width:30px; border-radius:0px; }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
            """
        return """
            QDialog { background:#101113; color:#E0DADF; }
            QScrollArea { background:transparent; border:0; }
            QLabel { color:#E0DADF; }
            QFrame#SettingsBlock {
                background:#18171A;
                border:1px solid #2E2A30;
                border-radius:16px;
            }
            QFrame#SettingsItem {
                background:#171719;
                border:1px solid #3A363B;
                border-radius:14px;
            }
            QLabel#SettingsItemTitle { font-size:13px; font-weight:700; color:#ffffff; }
            QLabel#SettingsTitle, QLabel#SettingsDialogTitle { font-size:22px; font-weight:800; color:#ffffff; }
            QLabel#SettingsSectionTitle { font-size:16px; font-weight:750; color:#ffffff; }
            QLabel#SettingsDescription { color:#9A9098; line-height:140%; }
            QLabel#SettingsPath {
                color:#c6ceda;
                background:#211F23;
                border:1px solid #2E2A30;
                border-radius:0px;
                padding:3px 6px;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QFontComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {
                background:#211F23;
                color:#F6F1F4;
                border:1px solid #3D383E;
                border-radius:0px;
                padding:3px 6px;
                selection-background-color:#8A4A52;
                selection-color:#ffffff;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QFontComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QKeySequenceEdit:focus {
                border:1px solid #A85D66;
                background:#111827;
            }
            QComboBox QAbstractItemView, QFontComboBox QAbstractItemView {
                background:#111827;
                color:#E8E1E6;
                border:1px solid #3D383E;
                outline:0;
                selection-background-color:#8A4A52;
                selection-color:#ffffff;
                padding:2px;
            }
            QComboBox QAbstractItemView::item, QFontComboBox QAbstractItemView::item {
                min-height:22px;
                padding:3px 8px;
            }
            QComboBox QAbstractItemView::item:hover, QFontComboBox QAbstractItemView::item:hover {
                background:#332B30;
                color:#ffffff;
            }
QCheckBox, QRadioButton { color:#E0DADF; spacing:9px; }
            QCheckBox::indicator, QRadioButton::indicator {
                width:15px; height:15px;
                border:1px solid #3A363B;
                background:#211F23;
                border-radius:0px;
            }
            QRadioButton::indicator { border-radius:0px; }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                background:#8A4A52;
                border:1px solid #A85D66;
            }
            QPushButton {
                background:#28262B;
                color:#E0DADF;
                border:1px solid #3A363B;
                border-radius:0px;
                padding:4px 10px;
            }
            QPushButton:hover { background:#332B30; border-color:#665A62; }
            QPushButton:pressed { background:#111827; }
            QPushButton:disabled { background:#171719; color:#746B72; border-color:#2E2A30; }
            QTabWidget::pane { border:1px solid #2E2A30; border-radius:0px; background:#171719; }
            QTabBar::tab {
                background:#171719;
                color:#9A9098;
                border:1px solid #2E2A30;
                border-bottom:none;
                border-top-left-radius:10px;
                border-top-right-radius:3px;
                padding:4px 10px;
            }
            QTabBar::tab:selected { background:#28262B; color:#ffffff; font-weight:700; }
            QListWidget, QTableWidget, QTreeWidget {
                background:#171719;
                color:#E0DADF;
                border:1px solid #2E2A30;
                border-radius:0px;
                alternate-background-color:#1D1B1F;
                selection-background-color:#8A4A52;
                selection-color:#ffffff;
            }
            QHeaderView::section {
                background:#141416;
                color:#CBC4C9;
                border:0;
                border-right:1px solid #2E2A30;
                padding:7px;
            }
            QScrollBar:vertical { background:#171719; width:12px; margin:0; border:0; border-radius:0px; }
            QScrollBar::handle:vertical { background:#3D383E; min-height:30px; border-radius:0px; }
            QScrollBar::handle:vertical:hover { background:#5C555B; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar:horizontal { background:#171719; height:12px; margin:0; border:0; border-radius:0px; }
            QScrollBar::handle:horizontal { background:#3D383E; min-width:30px; border-radius:0px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
        """

    def _settings_block(self, title, description=None):
        block = QFrame()
        block.setObjectName("SettingsBlock")
        layout = QVBoxLayout(block)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        title_label = QLabel(self.tr_ui(title))
        title_label.setObjectName("SettingsSectionTitle")
        layout.addWidget(title_label)
        if description:
            desc = QLabel(self.tr_ui(description))
            desc.setObjectName("SettingsDescription")
            desc.setWordWrap(True)
            layout.addWidget(desc)
        return block, layout

    def _settings_row(self, label_text, widget, description=None):
        row_wrap = QWidget()
        row = QHBoxLayout(row_wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        label = QLabel(self.tr_ui(label_text))
        label.setMinimumWidth(180)
        left.addWidget(label)
        if description:
            desc = QLabel(self.tr_ui(description))
            desc.setObjectName("SettingsDescription")
            desc.setWordWrap(True)
            left.addWidget(desc)
        row.addLayout(left, 1)
        row.addWidget(widget, 0)
        return row_wrap

    def _settings_button(self, text, slot):
        btn = QPushButton(self.tr_ui(text))
        btn.clicked.connect(slot)
        return btn

    def open_file_path_visibility_dialog(self):
        """로그/설정창의 실제 경로 표시 여부를 따로 조정하는 전용 설정창."""
        old_show_paths_in_log = bool(getattr(self, "show_paths_in_log", False))
        old_show_cache_paths_in_settings = bool(getattr(self, "show_cache_paths_in_settings", False))
        old_interface_tooltips_enabled = bool(getattr(self, "interface_tooltips_enabled", True))
        old_use_light_file_dialog = bool(getattr(self, "use_light_file_dialog", True))

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("파일 경로 표시"))
        dlg.setModal(True)
        dlg.resize(680, 360)
        dlg.setStyleSheet(self.settings_dialog_style())

        root = QVBoxLayout(dlg)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel(self.tr_ui("파일 경로 표시"), dlg)
        title.setObjectName("SettingsDialogTitle")
        root.addWidget(title)

        intro = QLabel(self.tr_ui("로그와 설정창에 실제 파일 경로를 표시할지 정합니다. 기본값은 꺼짐이며, 필요한 경우에만 켜는 고급 정보입니다."), dlg)
        intro.setObjectName("SettingsDescription")
        intro.setWordWrap(True)
        root.addWidget(intro)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)
        root.addLayout(body, 1)

        def add_toggle(title_text, description_text, checked=False):
            item = QFrame(dlg)
            item.setObjectName("SettingsItem")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(12, 10, 12, 10)
            item_layout.setSpacing(12)
            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)
            t = QLabel(self.tr_ui(title_text), item)
            t.setObjectName("SettingsItemTitle")
            text_box.addWidget(t)
            d = QLabel(self.tr_ui(description_text), item)
            d.setObjectName("SettingsDescription")
            d.setWordWrap(True)
            text_box.addWidget(d)
            item_layout.addLayout(text_box, 1)
            cb = QCheckBox(self.tr_ui("표시"), item)
            cb.setChecked(bool(checked))
            item_layout.addWidget(cb, 0)
            body.addWidget(item)
            return cb

        cb_show_paths_log = add_toggle(
            "로그창에 파일 위치 및 경로 표시",
            "로그에 저장 위치, 출력 위치, 작업 폴더 같은 실제 파일 경로를 함께 표시합니다. 끄면 완료/실패 같은 결과 문구만 표시합니다.",
            old_show_paths_in_log,
        )
        cb_show_cache_paths = add_toggle(
            "옵션 및 설정창에 캐시 위치 경로 표시",
            "API, 단축키 같은 옵션/설정 관리창에서 실제 캐시 파일 위치를 표시합니다. 끄면 캐시 경로는 숨깁니다.",
            old_show_cache_paths_in_settings,
        )
        body.addStretch(1)

        buttons = QDialogButtonBox(dlg)
        ok_btn = buttons.addButton(self.tr_ui("확인"), QDialogButtonBox.ButtonRole.AcceptRole)
        close_btn = buttons.addButton(self.tr_ui("닫기"), QDialogButtonBox.ButtonRole.RejectRole)
        root.addWidget(buttons)

        def apply_path_visibility_changes():
            new_show_paths_in_log = bool(cb_show_paths_log.isChecked())
            new_show_cache_paths_in_settings = bool(cb_show_cache_paths.isChecked())
            self.show_paths_in_log = new_show_paths_in_log
            self.show_cache_paths_in_settings = new_show_cache_paths_in_settings
            if new_show_paths_in_log != old_show_paths_in_log:
                self.log("🧾 로그 경로 표시: ON" if new_show_paths_in_log else "🧾 로그 경로 표시: OFF")
            if new_show_cache_paths_in_settings != old_show_cache_paths_in_settings:
                self.log("🧾 설정창 캐시 경로 표시: ON" if new_show_cache_paths_in_settings else "🧾 설정창 캐시 경로 표시: OFF")
            self.save_app_options_cache()
            self.log("⚙️ " + self.tr_ui("파일 경로 표시 설정 저장 완료"))
            dlg.accept()

        ok_btn.clicked.connect(apply_path_visibility_changes)
        close_btn.clicked.connect(dlg.reject)
        dlg.exec()

    def open_output_options_dialog(self):
        """출력 이미지/클린본 저장 형식을 설정한다.
        기본값은 PNG이고, 최종 출력과 클린본을 각각 독립적으로 고를 수 있다.
        """
        old_output_fmt = normalize_output_image_format(getattr(self, "output_image_format", DEFAULT_OUTPUT_IMAGE_FORMAT))
        old_clean_fmt = normalize_output_image_format(getattr(self, "clean_image_format", DEFAULT_OUTPUT_IMAGE_FORMAT))
        old_output_quality = normalize_output_image_quality(getattr(self, "output_image_quality", DEFAULT_OUTPUT_IMAGE_QUALITY))
        old_clean_quality = normalize_output_image_quality(getattr(self, "clean_image_quality", DEFAULT_OUTPUT_IMAGE_QUALITY))
        old_render_quality = normalize_output_text_render_quality(getattr(self, "output_text_render_quality", DEFAULT_OUTPUT_TEXT_RENDER_QUALITY))

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("출력 옵션"))
        dlg.resize(620, 420)
        try:
            dlg.setStyleSheet(self.settings_dialog_style())
        except Exception:
            pass

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        title = QLabel(self.tr_ui("출력 옵션"))
        title.setObjectName("SettingsDialogTitle")
        layout.addWidget(title)

        desc = QLabel(self.tr_ui("최종 출력 이미지와 클린본의 저장 형식, 그리고 출력할 때 사용할 텍스트 렌더 품질을 선택합니다. 형식을 바꿔 다시 출력하면 같은 이름의 기존 PNG/JPG/WebP 파일은 새 형식 파일로 교체됩니다."))
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        block = QFrame()
        block.setObjectName("SettingsBlock")
        block_lay = QGridLayout(block)
        block_lay.setContentsMargins(16, 14, 16, 14)
        block_lay.setHorizontalSpacing(12)
        block_lay.setVerticalSpacing(10)

        cb_output = QComboBox()
        cb_clean = QComboBox()
        for fmt, label in self.output_format_label_pairs():
            cb_output.addItem(label, fmt)
            cb_clean.addItem(label, fmt)
        try:
            cb_output.setCurrentIndex(max(0, cb_output.findData(old_output_fmt)))
            cb_clean.setCurrentIndex(max(0, cb_clean.findData(old_clean_fmt)))
        except Exception:
            pass

        sp_output_q = QSpinBox()
        sp_output_q.setRange(1, 100)
        sp_output_q.setValue(old_output_quality)
        sp_output_q.setSuffix(" %")
        sp_clean_q = QSpinBox()
        sp_clean_q.setRange(1, 100)
        sp_clean_q.setValue(old_clean_quality)
        sp_clean_q.setSuffix(" %")

        def add_row(row, title_text, desc_text, combo, quality_spin):
            name = QLabel(self.tr_ui(title_text))
            name.setObjectName("SettingsItemTitle")
            info = QLabel(self.tr_ui(desc_text))
            info.setObjectName("SettingsDescription")
            info.setWordWrap(True)
            block_lay.addWidget(name, row, 0)
            block_lay.addWidget(combo, row, 1)
            block_lay.addWidget(QLabel(self.tr_ui("품질")), row, 2)
            block_lay.addWidget(quality_spin, row, 3)
            block_lay.addWidget(info, row + 1, 0, 1, 4)

        add_row(0, "최종 출력 이미지", "result 폴더에 저장되는 식질 완료 이미지 형식입니다.", cb_output, sp_output_q)
        add_row(2, "클린본", "clean 폴더에 저장되는 글자 제거 배경 이미지 형식입니다. 파일명은 원본 파일명을 따릅니다.", cb_clean, sp_clean_q)

        cb_render = QComboBox()
        for value, label in self.output_text_render_quality_label_pairs():
            cb_render.addItem(label, value)
        try:
            cb_render.setCurrentIndex(max(0, cb_render.findData(old_render_quality)))
        except Exception:
            pass
        render_name = QLabel(self.tr_ui("텍스트 출력 렌더"))
        render_name.setObjectName("SettingsItemTitle")
        render_info = QLabel(self.tr_ui("출력 시 텍스트를 더 큰 임시 캔버스에 렌더링한 뒤 축소해 획과 후광 가장자리를 부드럽게 만듭니다. 작업 화면 속도에는 영향이 없고, 배율이 높을수록 출력 시간이 늘어날 수 있습니다."))
        render_info.setObjectName("SettingsDescription")
        render_info.setWordWrap(True)
        block_lay.addWidget(render_name, 4, 0)
        block_lay.addWidget(cb_render, 4, 1, 1, 3)
        block_lay.addWidget(render_info, 5, 0, 1, 4)

        def update_quality_enabled():
            cb_output_fmt = normalize_output_image_format(cb_output.currentData())
            cb_clean_fmt = normalize_output_image_format(cb_clean.currentData())
            sp_output_q.setEnabled(cb_output_fmt in ("jpg", "webp"))
            sp_clean_q.setEnabled(cb_clean_fmt in ("jpg", "webp"))
        cb_output.currentIndexChanged.connect(update_quality_enabled)
        cb_clean.currentIndexChanged.connect(update_quality_enabled)
        update_quality_enabled()

        layout.addWidget(block)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_ok = QPushButton(self.tr_ui("확인"))
        btn_cancel = QPushButton(self.tr_ui("닫기"))
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        def on_ok():
            new_output_fmt = normalize_output_image_format(cb_output.currentData())
            new_clean_fmt = normalize_output_image_format(cb_clean.currentData())
            new_output_quality = normalize_output_image_quality(sp_output_q.value())
            new_clean_quality = normalize_output_image_quality(sp_clean_q.value())
            new_render_quality = normalize_output_text_render_quality(cb_render.currentData())
            self.output_image_format = new_output_fmt
            self.clean_image_format = new_clean_fmt
            self.output_image_quality = new_output_quality
            self.clean_image_quality = new_clean_quality
            self.output_text_render_quality = new_render_quality
            self.app_options[OUTPUT_IMAGE_FORMAT_KEY] = new_output_fmt
            self.app_options[CLEAN_IMAGE_FORMAT_KEY] = new_clean_fmt
            self.app_options[OUTPUT_IMAGE_QUALITY_KEY] = new_output_quality
            self.app_options[CLEAN_IMAGE_QUALITY_KEY] = new_clean_quality
            self.app_options[OUTPUT_TEXT_RENDER_QUALITY_KEY] = new_render_quality
            self.save_app_options_cache()
            try:
                self.log(f"📤 출력 옵션 저장: 결과={new_output_fmt.upper()} / 클린본={new_clean_fmt.upper()} / 텍스트렌더={new_render_quality}")
            except Exception:
                pass
            dlg.accept()

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dlg.reject)
        return dlg.exec() == QDialog.DialogCode.Accepted

    def open_maker_plugin_translation_dialog(self):
        """DB번역 > 플러그인 번역.

        아직 별도 플러그인 번역 편집창은 연결 전이므로 메뉴 위치만 먼저 확정한다.
        """
        try:
            QMessageBox.information(
                self,
                self.tr_ui("플러그인 번역"),
                self.tr_ui("플러그인 번역 창은 다음 단계에서 연결합니다."),
            )
        except Exception:
            try:
                self.log("플러그인 번역 창은 다음 단계에서 연결합니다.")
            except Exception:
                pass

    def open_settings_overview_dialog(self):
        """설정과 옵션을 한 번에 보는 통합 창.
        - 확인: 이 창에서 직접 바꾼 설정을 저장하고 닫는다.
        - 닫기/X: 이 창에서 직접 바꾼 설정을 저장하지 않고 닫는다.
        - 복잡한 옵션은 각 전용 관리창의 확인/닫기 규칙을 따른다.
        """
        _dlg_t0 = time.time()
        try:
            self.audit_boundary_event("SETTINGS_DIALOG_BUILD_ENTER", dialog_key="settings_overview", memory=memory_text())
        except Exception:
            pass
        # 자동저장 모드는 v2.4 QA6에서 폐지되었다.
        self.auto_save_enabled = False
        old_theme = str(getattr(self, "ui_theme", THEME_DARK) or THEME_DARK)
        old_language = normalize_ui_language(getattr(self, "ui_language", LANG_KO))
        old_temp_enabled = self.is_temp_auto_cleanup_enabled()
        old_temp_days = self.get_temp_auto_cleanup_days()
        old_page_tab_display = normalize_page_display_mode(getattr(self, "page_tab_display_name_mode", DEFAULT_PAGE_DISPLAY_MODE))
        old_output_display = normalize_page_display_mode(getattr(self, "output_display_name_mode", DEFAULT_PAGE_DISPLAY_MODE))
        old_show_paths_in_log = bool(getattr(self, "show_paths_in_log", False))
        old_show_cache_paths_in_settings = bool(getattr(self, "show_cache_paths_in_settings", False))
        old_interface_tooltips_enabled = bool(getattr(self, "interface_tooltips_enabled", True))
        old_use_light_file_dialog = bool(getattr(self, "use_light_file_dialog", True))

        dlg = QDialog(self)
        dlg.setProperty("dialog_timing_log_key", "settings_overview")
        dlg.setProperty("dialog_timing_created_at", _dlg_t0)
        dlg.installEventFilter(self)
        dlg.setUpdatesEnabled(False)
        dlg.setWindowTitle(self.tr_ui("설정 / 옵션"))
        dlg.setModal(True)
        dlg.resize(820, 760)
        dlg.setStyleSheet(self.settings_dialog_style())

        root = QVBoxLayout(dlg)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel(self.tr_ui("설정 / 옵션"))
        title.setObjectName("SettingsDialogTitle")
        root.addWidget(title)

        intro = QLabel(self.tr_ui("확인을 누르면 이 창에서 바꾼 설정이 저장됩니다. 닫기나 X를 누르면 이 창에서 바꾼 설정은 저장하지 않습니다. 복잡한 항목은 오른쪽 버튼으로 전용 관리창을 엽니다."))
        intro.setObjectName("SettingsDescription")
        intro.setWordWrap(True)
        root.addWidget(intro)

        scroll = QScrollArea(dlg)
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        def make_action_button(text, slot):
            btn = QPushButton(self.tr_ui(text), dlg)
            btn.setMinimumWidth(150)
            btn.clicked.connect(slot)
            return btn

        def add_item(layout, title_text, description_text, control_widget=None, button_text=None, button_slot=None):
            item = QFrame(dlg)
            item.setObjectName("SettingsItem")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(12, 10, 12, 10)
            item_layout.setSpacing(12)
            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)
            t = QLabel(self.tr_ui(title_text), item)
            t.setObjectName("SettingsItemTitle")
            text_box.addWidget(t)
            d = QLabel(self.tr_ui(description_text), item)
            d.setObjectName("SettingsDescription")
            d.setWordWrap(True)
            text_box.addWidget(d)
            item_layout.addLayout(text_box, 1)
            if control_widget is not None:
                item_layout.addWidget(control_widget, 0)
            if button_text and button_slot:
                item_layout.addWidget(make_action_button(button_text, button_slot), 0)
            layout.addWidget(item)
            return item

        # 설정 섹션
        settings_block, settings_layout = self._settings_block(
            "설정",
            "프로그램의 기본 동작과 작업 환경을 정하는 항목입니다. 여기서 직접 바꾼 값은 확인을 눌러야 저장됩니다.",
        )

        cb_interface_tooltips = QCheckBox(self.tr_ui("표시"), dlg)
        cb_interface_tooltips.setChecked(old_interface_tooltips_enabled)
        add_item(
            settings_layout,
            "인터페이스 툴팁 표시",
            "버튼, 메뉴, 툴바에 뜨는 설명용 툴팁을 표시합니다. 스포이드 색상 표시 같은 작업용 안내는 이 설정과 별개로 유지됩니다.",
            cb_interface_tooltips,
        )

        combo_theme = QComboBox(dlg)
        combo_theme.addItem(self.tr_ui("다크 테마"), THEME_DARK)
        combo_theme.addItem(self.tr_ui("화이트 테마"), THEME_LIGHT)
        combo_theme.setCurrentIndex(1 if old_theme == THEME_LIGHT else 0)
        add_item(
            settings_layout,
            "테마 설정",
            "프로그램 전체의 밝기 테마를 정합니다. 확인을 누르면 선택한 테마가 적용됩니다.",
            combo_theme,
        )

        combo_lang = QComboBox(dlg)
        combo_lang.addItem(self.tr_ui("한국어"), LANG_KO)
        combo_lang.addItem("English", LANG_EN)
        combo_lang.setCurrentIndex(1 if old_language == LANG_EN else 0)
        add_item(
            settings_layout,
            "언어 설정",
            "메뉴와 안내 문구의 표시 언어를 정합니다. 확인을 누르면 선택한 언어가 적용됩니다.",
            combo_lang,
        )

        cb_show_paths_log = QCheckBox(self.tr_ui("표시"), dlg)
        cb_show_paths_log.setChecked(old_show_paths_in_log)
        add_item(
            settings_layout,
            "로그창에 파일 위치 및 경로 표시",
            "로그에 저장 위치, 출력 위치, 작업 폴더 같은 실제 파일 경로를 함께 표시합니다. 끄면 완료/실패 같은 결과 문구만 표시합니다.",
            cb_show_paths_log,
        )

        cb_show_cache_paths = QCheckBox(self.tr_ui("표시"), dlg)
        cb_show_cache_paths.setChecked(old_show_cache_paths_in_settings)
        add_item(
            settings_layout,
            "옵션 및 설정창에 캐시 위치 경로 표시",
            "API, 단축키 같은 옵션/설정 관리창에서 실제 캐시 파일 위치를 표시합니다. 끄면 캐시 경로는 숨깁니다.",
            cb_show_cache_paths,
        )

        cb_light_file_dialog = QCheckBox(self.tr_ui("사용"), dlg)
        cb_light_file_dialog.setChecked(old_use_light_file_dialog)
        add_item(
            settings_layout,
            "경량 파일 선택창 사용",
            "Windows 파일창이 느린 환경에서 Qt 경량 파일창을 사용합니다. 기본 파일 탐색기보다 덜 익숙할 수 있지만 열리는 시간이 줄어들 수 있습니다.",
            cb_light_file_dialog,
        )

        def fill_page_name_combo(combo, current_value):
            choices = [
                ("맵 이름", PAGE_DISPLAY_MODE_ORIGINAL),
                ("맵 이름", PAGE_DISPLAY_MODE_PAGE_ORIGINAL),
                ("맵 이름", PAGE_DISPLAY_MODE_PAGE_NUMBER),
            ]
            current_value = normalize_page_display_mode(current_value)
            for label, value in choices:
                combo.addItem(self.tr_ui(label), value)
                if value == current_value:
                    combo.setCurrentIndex(combo.count() - 1)

        combo_page_tab_name = QComboBox(dlg)
        fill_page_name_combo(combo_page_tab_name, old_page_tab_display)
        add_item(
            settings_layout,
            "맵 탭 표시명",
            "좌측 프리뷰 상단의 맵 탭에 표시할 이름 형식을 정합니다. 기본값은 맵 이름입니다.",
            combo_page_tab_name,
        )

        workspace_widget = QWidget(dlg)
        workspace_row = QHBoxLayout(workspace_widget)
        workspace_row.setContentsMargins(0, 0, 0, 0)
        workspace_row.setSpacing(8)
        try:
            old_workspace_root = Path(load_workspace_config().get("workspace_root") or get_workspace_root())
        except Exception:
            old_workspace_root = Path(str(get_workspace_root()))
        workspace_target = {"path": old_workspace_root}
        workspace_label = QLabel(str(old_workspace_root), workspace_widget)
        workspace_label.setObjectName("SettingsPath")
        workspace_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        workspace_row.addWidget(workspace_label, 1)
        def change_workspace_from_dialog():
            # 통합 설정창에서는 개별 작업 폴더 설정창을 다시 띄우지 않는다.
            # 여기서는 경로값만 바꾸고, 실제 저장/재기동 확인은 통합 설정창의 [확인]에서 처리한다.
            current = str(workspace_target.get("path") or old_workspace_root)
            selected = self.get_existing_directory_logged("workspace_location_select", dlg, self.tr_ui("작업 폴더 위치 선택"), current) if hasattr(self, "get_existing_directory_logged") else QFileDialog.getExistingDirectory(dlg, self.tr_ui("작업 폴더 위치 선택"), current)
            if selected:
                try:
                    target = normalize_workspace_root_from_user(selected)
                except Exception:
                    QMessageBox.warning(dlg, self.tr_ui("경로 오류"), self.tr_ui("작업 폴더 경로가 올바르지 않습니다."))
                    return
                workspace_target["path"] = target
                workspace_label.setText(str(target))
        btn_change_workspace = QPushButton(self.tr_ui("위치 변경"), workspace_widget)
        btn_change_workspace.clicked.connect(change_workspace_from_dialog)
        workspace_row.addWidget(btn_change_workspace)
        def reset_workspace_from_dialog():
            # 즉시 저장하지 않고 표시값만 기본값으로 되돌린다.
            # [확인]에서 재기동을 승인해야 실제 적용된다.
            target = default_workspace_root()
            workspace_target["path"] = target
            workspace_label.setText(str(target))
        btn_reset_workspace = QPushButton(self.tr_ui("기본값으로\n변경"), workspace_widget)
        btn_reset_workspace.setToolTip(self.tr_ui("Windows 실제 문서 폴더 아래 YSB_Translator로 되돌립니다."))
        btn_reset_workspace.clicked.connect(reset_workspace_from_dialog)
        workspace_row.addWidget(btn_reset_workspace)
        add_item(
            settings_layout,
            "작업 폴더 위치",
            "프로젝트 작업 폴더와 캐시가 저장되는 기준 위치입니다. 위치를 바꾸면 프로그램을 재기동해야 적용됩니다. 취소하면 이전 작업 폴더 위치값으로 원복됩니다. 기본값은 Windows 실제 문서 폴더 아래 YSB_Translator입니다.",
            workspace_widget,
        )

        temp_widget = QWidget(dlg)
        temp_row = QHBoxLayout(temp_widget)
        temp_row.setContentsMargins(0, 0, 0, 0)
        temp_row.setSpacing(8)
        cb_temp_auto = QCheckBox(self.tr_ui("자동삭제"), temp_widget)
        cb_temp_auto.setChecked(old_temp_enabled)
        combo_days = QComboBox(temp_widget)
        for days, label in self.temp_cleanup_period_options():
            combo_days.addItem(self.tr_ui(label), days)
            if days == old_temp_days:
                combo_days.setCurrentIndex(combo_days.count() - 1)
        combo_days.setEnabled(cb_temp_auto.isChecked())
        cb_temp_auto.toggled.connect(lambda checked: combo_days.setEnabled(bool(checked)))
        temp_row.addWidget(cb_temp_auto)
        temp_row.addWidget(combo_days)
        add_item(
            settings_layout,
            "사용자 데이터 및 임시파일 정리",
            "AppData 실행 캐시와 임시 데이터는 자동 정리 대상입니다. 최근 프로젝트 정보, 설정 정보, 개인정보는 사용자가 직접 누를 때만 삭제합니다.",
            temp_widget,
            "관리",
            self.cleanup_temp_files_dialog,
        )

        add_item(
            settings_layout,
            "작업 폴더 용량 관리",
            ".ysbg를 열어 작업할 때 생성되는 실제 작업 폴더들을 날짜순으로 보고, 폴더별 용량 확인/열기/삭제를 직접 관리합니다.",
            None,
            "관리",
            self.open_workspace_folder_size_manager_dialog,
        )

        add_item(
            settings_layout,
            "YSBG 파일 연결 등록",
            ".ysbg 파일을 더블클릭했을 때 현재 쯔꾸르붕이로 바로 열리게 Windows 연결을 등록합니다.",
            None,
            "등록",
            self.register_ysb_file_association,
        )
        add_item(
            settings_layout,
            "YSBG 파일 연결 해제",
            "현재 사용자 계정의 .ysbg 연결을 해제합니다. 이전 테스트용 .ysb 연결도 함께 정리합니다.",
            None,
            "해제",
            self.unregister_ysbt_file_association,
        )

        body_layout.addWidget(settings_block)

        # 옵션 섹션
        options_block, options_layout = self._settings_block(
            "옵션",
            "작업 기능을 관리하는 항목입니다. 이 창 안에 전부 펼치면 복잡해지므로, 각 항목의 버튼으로 기존 전용 관리창을 엽니다.",
        )
        option_items = [
            (
                "API 관리",
                "번역 API 주소, 키, 모델명 같은 외부 API 설정을 관리합니다. 유료 API 정보가 들어갈 수 있으니 저장 전 확인이 필요합니다.",
                "관리",
                self.open_api_settings_dialog,
            ),
            (
                "단축키 통합 관리",
                "상단 메뉴와 작업 기능에 연결된 단축키를 한곳에서 바꿉니다. 충돌 확인과 비활성화도 여기서 처리합니다.",
                "관리",
                self.open_shortcut_settings_dialog,
            ),
            (
                "매크로 관리",
                "여러 작업을 하나의 사용자 단축키로 묶어 실행하는 매크로를 관리합니다. 반복 작업을 줄이는 자동화용 기능입니다.",
                "관리",
                self.open_macro_settings_dialog,
            ),
            (
                "캐릭터 프로필 보기",
                "게임 대사에서 분석한 캐릭터/화자 정보를 확인하고 번역 말투 관리에 활용합니다.",
                "보기",
                self.open_maker_character_profiles_dialog,
            ),
            (
                "게임 프롬프트 관리",
                "공통 프롬프트, 캐릭터 말투, 시스템/데이터베이스 번역 지침을 프로젝트 단위로 관리합니다.",
                "관리",
                self.open_maker_character_prompts_dialog,
            ),
            (
                "단어장",
                "반복해서 나오는 이름, 고유명사, 말투 규칙, 번역 고정어를 관리합니다. 번역 품질을 일정하게 유지하는 데 쓰입니다.",
                "관리",
                self.open_glossary_dialog,
            ),
            (
                "줄내림 옵션",
                "AI 번역 요청에 넣는 쯔꾸르 원문을 정리합니다. 원본 데이터는 유지하고, 번역 품질을 위해 요청용 줄내림만 제거할 수 있습니다.",
                "설정",
                self.open_maker_translation_settings_dialog,
            ),
            (
                "게임 프리뷰 옵션",
                "맵 그리드/보조선, 이벤트 위치, 이벤트 이름 오버레이, 이미지 반투명 표시를 켜고 끕니다. 대사는 게임식 대사창/선택지 프리뷰로 표시합니다.",
                "설정",
                self.open_maker_preview_display_settings_dialog,
            ),
            (
                "게임 설정",
                "현재 프로젝트의 게임 제목, 해상도, 타일 크기, 대사창 기준값 같은 게임 기본 표시 정보를 확인하고 관리합니다.",
                "설정",
                self.open_maker_game_settings_dialog,
            ),
            (
                "게임 갱신",
                "현재 게임 JSON에서 대사를 다시 읽어 원문 기준과 번역문 칸을 갱신합니다. 기존 번역/메모는 가능한 한 보존합니다.",
                "갱신",
                self.refresh_maker_game_dialogue_action,
            ),
        ]
        for title_text, desc_text, btn_text, slot in option_items:
            add_item(options_layout, title_text, desc_text, None, btn_text, slot)

        body_layout.addWidget(options_block)
        body_layout.addStretch(1)

        save_applied = {"ok": False, "restart": False}

        def apply_settings_overview_changes():
            new_theme = str(combo_theme.currentData() or THEME_DARK)
            if new_theme not in (THEME_DARK, THEME_LIGHT):
                new_theme = THEME_DARK
            new_language = normalize_ui_language(combo_lang.currentData())
            new_temp_enabled = bool(cb_temp_auto.isChecked())
            new_temp_days = int(combo_days.currentData() or old_temp_days or 7)
            new_page_tab_display = normalize_page_display_mode(combo_page_tab_name.currentData())
            new_output_display = old_output_display
            new_show_paths_in_log = bool(cb_show_paths_log.isChecked())
            new_show_cache_paths_in_settings = bool(cb_show_cache_paths.isChecked())
            new_interface_tooltips_enabled = bool(cb_interface_tooltips.isChecked())
            new_use_light_file_dialog = bool(cb_light_file_dialog.isChecked())

            # 확인 → 저장 확인에서 예를 누른 뒤에만 실제 저장/적용한다.
            if new_theme != old_theme:
                self.ui_theme = new_theme
                self.apply_theme(new_theme)
            if new_language != old_language:
                self.ui_language = new_language
                self.apply_language(new_language)
            if new_temp_enabled != old_temp_enabled or new_temp_days != old_temp_days:
                self.set_temp_cleanup_options(new_temp_enabled, new_temp_days)
                self.log(f"🧹 임시 파일 자동삭제 설정: {'ON' if new_temp_enabled else 'OFF'} / {new_temp_days}일")
            display_changed = (new_page_tab_display != old_page_tab_display) or (new_output_display != old_output_display)
            self.page_tab_display_name_mode = new_page_tab_display
            self.output_display_name_mode = new_output_display
            if new_page_tab_display != old_page_tab_display:
                self.refresh_page_tabs()
                self.log(f"📑 맵 탭 표시명 설정: {new_page_tab_display}")
            if new_output_display != old_output_display:
                self.log(f"📤 출력 표시명 설정: {new_output_display}")
            path_visibility_changed = (new_show_paths_in_log != old_show_paths_in_log) or (new_show_cache_paths_in_settings != old_show_cache_paths_in_settings)
            self.show_paths_in_log = new_show_paths_in_log
            self.show_cache_paths_in_settings = new_show_cache_paths_in_settings
            if new_show_paths_in_log != old_show_paths_in_log:
                self.log("🧾 로그 경로 표시: ON" if new_show_paths_in_log else "🧾 로그 경로 표시: OFF")
            if new_show_cache_paths_in_settings != old_show_cache_paths_in_settings:
                self.log("🧾 설정창 캐시 경로 표시: ON" if new_show_cache_paths_in_settings else "🧾 설정창 캐시 경로 표시: OFF")
            if new_interface_tooltips_enabled != old_interface_tooltips_enabled:
                try:
                    self.set_interface_tooltips_enabled(new_interface_tooltips_enabled, persist=False, announce=True)
                except Exception:
                    self.interface_tooltips_enabled = new_interface_tooltips_enabled
            if new_use_light_file_dialog != old_use_light_file_dialog:
                self.use_light_file_dialog = new_use_light_file_dialog
                self.log("📂 경량 파일 선택창: ON" if new_use_light_file_dialog else "📂 경량 파일 선택창: OFF")
            else:
                self.use_light_file_dialog = new_use_light_file_dialog
            self.auto_save_enabled = False
            self.save_app_options_cache()
            self.log("⚙️ 설정 / 옵션 저장 완료")
            save_applied["ok"] = True

        def on_settings_overview_ok():
            # 설정창은 닫지 않은 상태에서 먼저 저장 여부를 묻는다.
            # 아니오(N)를 누르면 설정창으로 돌아가 다시 조작할 수 있다.
            if not self.ask_yes_no_shortcut(
                "설정 저장",
                "이 창에서 바꾼 설정을 저장할까요?",
                yes_text="저장",
                no_text="취소",
                default_yes=True,
                icon=QMessageBox.Icon.Question,
                parent=dlg,
            ):
                self.log("⚙️ 설정 / 옵션 저장 취소")
                return

            try:
                current_workspace = Path(old_workspace_root).resolve()
                target_workspace = Path(workspace_target.get("path") or old_workspace_root).resolve()
            except Exception:
                current_workspace = Path(str(old_workspace_root))
                target_workspace = Path(str(workspace_target.get("path") or old_workspace_root))

            workspace_changed = current_workspace != target_workspace
            if workspace_changed:
                if not workspace_restart_confirmation(dlg, current_workspace, target_workspace, self.ui_language):
                    # 재기동을 취소하면 설정창은 그대로 두고 작업 폴더 표시값만 이전값으로 원복한다.
                    workspace_target["path"] = old_workspace_root
                    workspace_label.setText(str(old_workspace_root))
                    self.log("📁 작업 폴더 위치 변경 취소")
                    return
                try:
                    apply_settings_overview_changes()
                    schedule_workspace_root_change(target_workspace)
                    save_applied["restart"] = True
                    self.log(f"📁 작업 폴더 위치 변경 예약 및 재기동: {target_workspace}")
                    dlg.accept()
                    restart_application_detached()
                    return
                except Exception as e:
                    QMessageBox.critical(dlg, self.tr_ui("내보내기 실패"), f"{self.tr_ui('작업 폴더 위치를 변경하지 못했습니다.')}\n{e}")
                    workspace_target["path"] = old_workspace_root
                    workspace_label.setText(str(old_workspace_root))
                    return

            apply_settings_overview_changes()
            dlg.accept()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("닫기"))
        btns.accepted.connect(on_settings_overview_ok)
        btns.rejected.connect(dlg.reject)
        root.addWidget(btns)

        try:
            self.audit_boundary_event("SETTINGS_DIALOG_BUILD_DONE", dialog_key="settings_overview", elapsed_ms=int((time.time() - _dlg_t0) * 1000), memory=memory_text())
        except Exception:
            pass
        try:
            dlg.setUpdatesEnabled(True)
            dlg.update()
        except Exception:
            pass
        try:
            dlg.setProperty("dialog_timing_exec_enter_at", time.time())
            self.audit_boundary_event("SETTINGS_DIALOG_EXEC_ENTER", dialog_key="settings_overview", memory=memory_text())
        except Exception:
            pass
        _settings_result = dlg.exec()
        try:
            self.audit_boundary_event("SETTINGS_DIALOG_EXEC_RETURN", dialog_key="settings_overview", result=int(_settings_result), elapsed_ms=int((time.time() - float(dlg.property("dialog_timing_exec_enter_at") or time.time())) * 1000), memory=memory_text())
        except Exception:
            pass
        if _settings_result != QDialog.DialogCode.Accepted:
            self.log("⚙️ 설정 / 옵션 변경 취소")
            return

        if save_applied.get("ok") and not save_applied.get("restart"):
            self.show_ok_notice("설정 저장 완료", "설정이 저장되었습니다.")

    def open_maker_translation_settings_dialog(self):
        """옵션 > 쯔꾸르 번역 설정.

        Project-level settings for AI translation input normalization. OK saves;
        Cancel/X discards. This does not change original project text.
        """
        try:
            from ysb.tools.maker_project import (
                DEFAULT_MAKER_TRANSLATION_SETTINGS,
                load_maker_translation_settings,
                normalize_maker_translation_settings,
                save_maker_translation_settings,
            )
        except Exception as e:
            QMessageBox.critical(self, self.tr_ui("설정 오류"), f"{self.tr_ui('쯔꾸르 번역 설정을 열 수 없습니다.')}\n{e}")
            return

        project_dir = str(getattr(self, "project_dir", "") or "").strip()
        if not project_dir:
            QMessageBox.information(self, self.tr_ui("프로젝트 없음"), self.tr_ui("쯔꾸르 번역 설정은 프로젝트를 연 뒤 사용할 수 있습니다."))
            return

        is_maker = False
        try:
            ui_state = getattr(getattr(self, "project_store", None), "ui_state", {}) or {}
            if str(ui_state.get("project_kind") or "").startswith("rpg_maker_"):
                is_maker = True
        except Exception:
            pass
        if not is_maker:
            try:
                is_maker = any(isinstance((page or {}).get("maker_page"), dict) and (page or {}).get("maker_page") for page in (getattr(self, "data", {}) or {}).values())
            except Exception:
                is_maker = False
        if not is_maker:
            QMessageBox.information(self, self.tr_ui("쯔꾸르 프로젝트 아님"), self.tr_ui("현재 프로젝트에는 쯔꾸르 페이지 정보가 없습니다. 게임 가져오기 후 사용해 주세요."))
            return

        old_settings = normalize_maker_translation_settings(load_maker_translation_settings(project_dir))

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("쯔꾸르 번역 설정"))
        dlg.resize(620, 360)
        dlg.setStyleSheet(self.settings_dialog_style())
        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(self.tr_ui("쯔꾸르 번역 설정"), dlg)
        title.setObjectName("SettingsTitle")
        root.addWidget(title)

        desc = QLabel(self.tr_ui("AI 번역 요청에 넣는 원문을 정리하는 프로젝트 단위 설정입니다. 원본 JSON과 오른쪽 원문 표시는 바꾸지 않고, AI에 보내는 텍스트만 정규화합니다."), dlg)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        root.addWidget(desc)

        box = QFrame(dlg)
        box.setObjectName("SettingsItem")
        form = QVBoxLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(12)

        cb_normalize = QCheckBox(self.tr_ui("AI 번역 시 원문 줄내림 제거"), box)
        cb_normalize.setChecked(bool(old_settings.get("normalize_source_newlines", True)))
        cb_desc = QLabel(self.tr_ui("RPG Maker 대사는 여러 401/405 줄로 나뉘어 저장될 수 있습니다. 이 옵션은 번역 품질을 위해 AI 요청용 원문만 한 문장처럼 합칩니다."), box)
        cb_desc.setObjectName("SettingsDescription")
        cb_desc.setWordWrap(True)
        form.addWidget(cb_normalize)
        form.addWidget(cb_desc)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        lab = QLabel(self.tr_ui("줄내림 제거 방식"), box)
        lab.setObjectName("SettingsItemTitle")
        combo = QComboBox(box)
        combo.addItem(self.tr_ui("자동 판단: CJK는 붙이고 영문/숫자 사이만 공백"), "auto")
        combo.addItem(self.tr_ui("항상 붙여쓰기: 일본어/한국어/중국어 중심"), "cjk_join")
        combo.addItem(self.tr_ui("항상 공백으로 합치기: 영어 중심"), "space")
        try:
            idx = combo.findData(str(old_settings.get("newline_join_mode") or "auto"))
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        except Exception:
            pass
        row.addWidget(lab, 1)
        row.addWidget(combo, 2)
        form.addLayout(row)

        mode_desc = QLabel(self.tr_ui("기본값은 자동 판단입니다. 원문/번역문 저장 데이터 자체는 변경하지 않으며, AI 요청 직전에만 적용됩니다."), box)
        mode_desc.setObjectName("SettingsDescription")
        mode_desc.setWordWrap(True)
        form.addWidget(mode_desc)

        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        btn_reset = QPushButton(self.tr_ui("기본값으로 돌아가기"), box)
        reset_row.addWidget(btn_reset)
        form.addLayout(reset_row)

        def reset_defaults():
            d = DEFAULT_MAKER_TRANSLATION_SETTINGS
            cb_normalize.setChecked(bool(d.get("normalize_source_newlines", True)))
            idx = combo.findData(str(d.get("newline_join_mode") or "auto"))
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        btn_reset.clicked.connect(reset_defaults)

        preview_row = QHBoxLayout()
        preview_row.setContentsMargins(0, 0, 0, 0)
        preview_row.setSpacing(10)
        preview_desc = QLabel(self.tr_ui("보조선, 이벤트 위치/이름, 이미지 반투명 표시 여부는 프리뷰 표시 옵션에서 관리합니다. 대사는 게임식 대사창/선택지 프리뷰로만 표시합니다."), box)
        preview_desc.setObjectName("SettingsDescription")
        preview_desc.setWordWrap(True)
        btn_preview_options = QPushButton(self.tr_ui("프리뷰 표시 옵션 열기"), box)
        btn_preview_options.clicked.connect(self.open_maker_preview_display_settings_dialog)
        preview_row.addWidget(preview_desc, 1)
        preview_row.addWidget(btn_preview_options, 0)
        form.addLayout(preview_row)

        root.addWidget(box, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        try:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("취소"))
        except Exception:
            pass
        root.addWidget(buttons)

        saved = {"ok": False}

        def collect_settings():
            return normalize_maker_translation_settings({
                "normalize_source_newlines": cb_normalize.isChecked(),
                "newline_join_mode": combo.currentData() or "auto",
            })

        def accept_and_save():
            settings = save_maker_translation_settings(project_dir, collect_settings())
            try:
                store = getattr(self, "project_store", None)
                if store is not None:
                    ui_state = getattr(store, "ui_state", {}) or {}
                    if not isinstance(ui_state, dict):
                        ui_state = {}
                    ui_state["maker_translation_settings"] = dict(settings)
                    store.ui_state = ui_state
            except Exception:
                pass
            try:
                if hasattr(self, "mark_project_structure_dirty"):
                    self.mark_project_structure_dirty("maker_translation_settings")
            except Exception:
                pass
            try:
                self.save_project_store(getattr(self, "project_store", None))
            except Exception:
                pass
            saved["ok"] = True
            try:
                self.log("⚙️ 쯔꾸르 번역 설정 저장: 원문 줄내림 제거 {state} / 방식 {mode}".format(
                    state="ON" if settings.get("normalize_source_newlines", True) else "OFF",
                    mode=settings.get("newline_join_mode") or "auto",
                ))
            except Exception:
                pass
            dlg.accept()

        buttons.accepted.connect(accept_and_save)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() == QDialog.DialogCode.Accepted and saved.get("ok"):
            self.show_ok_notice("쯔꾸르 번역 설정 저장 완료", "AI 번역용 원문 줄내림 정규화 설정이 저장되었습니다.")


    def refresh_maker_display_environment(self, *, reason="manual", refresh_view=True, silent=False):
        """Rebuild the Maker runtime display profile from the opened project folder.

        The working folder/project.json is the normal entry point for YSB Game
        Editor.  Therefore, when a project is opened or when the user presses the
        refresh button, rebuild maker_meta/maker_runtime_profile.json from the
        actual cloned game folder instead of relying on stale preview values.
        """
        try:
            project_dir = Path(str(getattr(self, "project_dir", "") or ""))
        except Exception:
            project_dir = Path("")
        if not project_dir or not project_dir.exists():
            if not silent:
                self.show_warn_notice("쯔꾸르 표시 환경 갱신", "프로젝트를 먼저 열어 주세요.")
            return False
        game_dir = project_dir / "maker_game"
        if not game_dir.exists():
            if not silent:
                self.show_warn_notice("쯔꾸르 표시 환경 갱신", "현재 프로젝트에 maker_game 폴더가 없습니다.")
            return False
        try:
            from ysb.tools.maker_project import (
                detect_maker_engine,
                build_maker_runtime_profile,
                maker_preview_settings_from_runtime_profile,
                load_maker_preview_settings,
                save_maker_preview_settings,
                apply_maker_preview_settings_to_data,
                regenerate_maker_placeholder_for_page,
                append_maker_preview_diagnostic,
            )
            engine_info = detect_maker_engine(game_dir)
            profile = build_maker_runtime_profile(project_dir, game_dir, engine_info)
            old_settings = load_maker_preview_settings(project_dir)
            settings = maker_preview_settings_from_runtime_profile(profile, old_settings)
            settings = save_maker_preview_settings(project_dir, settings)
            try:
                self._reset_maker_preview_font_runtime_cache(f"display_environment_refresh:{reason}")
            except Exception:
                pass
            changed = apply_maker_preview_settings_to_data(getattr(self, "data", {}) or {}, settings)
            regenerated = 0
            try:
                for i, path in enumerate(getattr(self, "paths", []) or []):
                    page = (getattr(self, "data", {}) or {}).get(i, {})
                    if not isinstance(page, dict) or not page.get("maker_page"):
                        continue
                    page["maker_preview_settings"] = dict(settings)
                    page["maker_runtime_profile"] = dict(profile)
                    try:
                        if regenerate_maker_placeholder_for_page(path, page, settings=settings):
                            regenerated += 1
                    except Exception as e:
                        try:
                            self.log(f"⚠️ 쯔꾸르 프리뷰 페이지 갱신 실패({i + 1}p): {e}")
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                store = getattr(self, "project_store", None)
                if store is not None:
                    ui_state = getattr(store, "ui_state", {}) or {}
                    if not isinstance(ui_state, dict):
                        ui_state = {}
                    ui_state["maker_preview_settings"] = dict(settings)
                    ui_state["maker_runtime_profile"] = dict(profile)
                    ui_state["maker_runtime_profile_refreshed_at"] = datetime.now().isoformat(timespec="seconds")
                    ui_state["maker_runtime_profile_refresh_reason"] = str(reason or "manual")
                    store.ui_state = ui_state
            except Exception:
                pass
            try:
                append_maker_preview_diagnostic(project_dir, "runtime_profile_refreshed", {
                    "reason": str(reason or "manual"),
                    "engine": profile.get("engine"),
                    "settings": settings,
                    "text_items_changed": changed,
                    "pages_regenerated": regenerated,
                })
            except Exception:
                pass
            try:
                if hasattr(self, "mark_project_structure_dirty"):
                    self.mark_project_structure_dirty(f"maker_runtime_profile_refresh:{reason}")
            except Exception:
                pass
            try:
                self.save_project_store(getattr(self, "project_store", None))
            except Exception:
                try:
                    self.save_workspace_project_json_light(reason="maker_runtime_profile_refresh")
                except Exception:
                    pass
            if refresh_view:
                try:
                    curr_mode = self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 0
                    self.mode_chg(curr_mode)
                except Exception:
                    pass
                try:
                    if hasattr(self, "refresh_page_tabs"):
                        self.refresh_page_tabs()
                except Exception:
                    pass
                try:
                    self.update_maker_preview_selection_from_table()
                except Exception:
                    pass
            try:
                font_info = profile.get("font") if isinstance(profile.get("font"), dict) else {}
                screen_info = profile.get("screen") if isinstance(profile.get("screen"), dict) else {}
                self.log(
                    "🔁 쯔꾸르 표시 환경 갱신: "
                    f"{profile.get('engine_label') or profile.get('engine') or 'RPG Maker'} / "
                    f"{screen_info.get('width')}x{screen_info.get('height')} / "
                    f"font={font_info.get('main_font_filename') or font_info.get('family') or settings.get('font_family')} / "
                    f"{settings.get('font_size')}px"
                )
            except Exception:
                pass
            return {
                "profile": profile,
                "settings": settings,
                "changed": changed,
                "regenerated": regenerated,
            }
        except Exception as e:
            try:
                self.log(f"⚠️ 쯔꾸르 표시 환경 갱신 실패: {e}")
            except Exception:
                pass
            if not silent:
                self.show_warn_notice("쯔꾸르 표시 환경 갱신 실패", str(e))
            return False

    def refresh_maker_display_environment_action(self, show_notice=True):
        if not getattr(self, "project_dir", None):
            self.show_warn_notice("쯔꾸르 표시 환경 갱신", "프로젝트를 먼저 열어 주세요.")
            return False
        if show_notice:
            ok = self.ask_yes_no_shortcut(
                "쯔꾸르 표시 환경 갱신",
                "현재 작업 폴더의 maker_game에서 System.json, fonts, Window.png, MV/MZ 런타임 값을 다시 읽어 프리뷰 설정을 갱신할까요?\n\n수동으로 조정한 일부 프리뷰 값은 게임값 기준으로 다시 맞춰질 수 있습니다.",
                yes_text="갱신",
                no_text="취소",
                default_yes=True,
                icon=QMessageBox.Icon.Question,
            )
            if not ok:
                try:
                    self.log("↩️ 쯔꾸르 표시 환경 갱신 취소")
                except Exception:
                    pass
                return False
        result = self.refresh_maker_display_environment(reason="manual", refresh_view=True, silent=False)
        if result and show_notice:
            try:
                settings = result.get("settings") if isinstance(result, dict) else {}
                self.show_ok_notice(
                    "쯔꾸르 표시 환경 갱신 완료",
                    f"게임 내부 표시 환경을 다시 읽었습니다.\n화면: {settings.get('screen_width')}x{settings.get('screen_height')}\n폰트: {settings.get('main_font_filename') or settings.get('font_family')} / {settings.get('font_size')}px"
                )
            except Exception:
                pass
        return result

    def open_maker_preview_font_settings_dialog(self):
        """옵션 > 쯔꾸르 프리뷰 폰트 설정.

        Project-level settings for Maker map/message preview.  OK saves and
        immediately refreshes the current page; Cancel/X discards changes.
        """
        try:
            from ysb.tools.maker_project import (
                DEFAULT_MAKER_PREVIEW_SETTINGS,
                apply_maker_preview_settings_to_data,
                load_maker_preview_settings,
                regenerate_maker_placeholder_for_page,
                save_maker_preview_settings,
                normalize_maker_preview_settings,
            )
        except Exception as e:
            QMessageBox.critical(self, self.tr_ui("설정 오류"), f"{self.tr_ui('쯔꾸르 프리뷰 폰트 설정을 열 수 없습니다.')}\n{e}")
            return

        project_dir = str(getattr(self, "project_dir", "") or "").strip()
        if not project_dir:
            QMessageBox.information(self, self.tr_ui("프로젝트 없음"), self.tr_ui("쯔꾸르 프리뷰 폰트 설정은 프로젝트를 연 뒤 사용할 수 있습니다."))
            return

        is_maker = False
        try:
            ui_state = getattr(getattr(self, "project_store", None), "ui_state", {}) or {}
            if str(ui_state.get("project_kind") or "").startswith("rpg_maker_"):
                is_maker = True
        except Exception:
            pass
        if not is_maker:
            try:
                is_maker = any(isinstance((page or {}).get("maker_page"), dict) and (page or {}).get("maker_page") for page in (getattr(self, "data", {}) or {}).values())
            except Exception:
                is_maker = False
        if not is_maker:
            QMessageBox.information(self, self.tr_ui("쯔꾸르 프로젝트 아님"), self.tr_ui("현재 프로젝트에는 쯔꾸르 맵 페이지 정보가 없습니다. 게임 가져오기 후 사용해 주세요."))
            return

        old_settings = normalize_maker_preview_settings(load_maker_preview_settings(project_dir))

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("쯔꾸르 프리뷰 폰트 설정"))
        dlg.resize(720, 680)
        dlg.setStyleSheet(self.settings_dialog_style())
        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(self.tr_ui("쯔꾸르 프리뷰 폰트 설정"), dlg)
        title.setObjectName("SettingsTitle")
        root.addWidget(title)

        desc = QLabel(self.tr_ui("맵/메시지 프리뷰와 쯔꾸르 텍스트 아이템에 적용할 프로젝트 단위 폰트 기준값입니다. 확인을 누르면 저장하고 현재 화면을 갱신합니다. 닫기나 X를 누르면 저장하지 않습니다."), dlg)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        root.addWidget(desc)

        box = QFrame(dlg)
        box.setObjectName("SettingsItem")
        form = QVBoxLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        def add_row(label_text, editor, description_text=""):
            row = QHBoxLayout()
            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(2)
            lab = QLabel(self.tr_ui(label_text), dlg)
            lab.setObjectName("SettingsItemTitle")
            text_box.addWidget(lab)
            if description_text:
                d = QLabel(self.tr_ui(description_text), dlg)
                d.setObjectName("SettingsDescription")
                d.setWordWrap(True)
                text_box.addWidget(d)
            row.addLayout(text_box, 1)
            row.addWidget(editor, 0)
            form.addLayout(row)
            return editor

        font_combo = QFontComboBox(dlg)
        try:
            font_combo.setCurrentFont(QFont(str(old_settings.get("font_family") or "")))
        except Exception:
            pass
        add_row("기본 폰트", font_combo, "프리뷰 메시지창과 가져온 쯔꾸르 텍스트 아이템에 적용할 기본 글꼴입니다.")

        file_widget = QWidget(dlg)
        file_row = QHBoxLayout(file_widget)
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.setSpacing(8)
        le_font_path = QLineEdit(str(old_settings.get("font_path") or ""), file_widget)
        le_font_path.setPlaceholderText(self.tr_ui("선택 안 함"))
        btn_font_file = QPushButton(self.tr_ui("찾기"), file_widget)
        file_row.addWidget(le_font_path, 1)
        file_row.addWidget(btn_font_file, 0)
        add_row("폰트 파일", file_widget, "게임 폴더나 별도 폰트 파일을 직접 지정할 때 사용합니다. 지정하면 Qt에 폰트를 등록하고 가능한 경우 폰트 이름을 자동으로 맞춥니다.")

        def browse_font_file():
            start_dir = str(Path(le_font_path.text()).parent) if le_font_path.text().strip() else project_dir
            selected, _ = QFileDialog.getOpenFileName(dlg, self.tr_ui("폰트 파일 선택"), start_dir, self.tr_ui("Font Files (*.ttf *.otf *.ttc);;All Files (*.*)"))
            if not selected:
                return
            le_font_path.setText(selected)
            try:
                font_id = QFontDatabase.addApplicationFont(selected)
                if int(font_id) >= 0:
                    families = list(QFontDatabase.applicationFontFamilies(int(font_id)))
                    if families:
                        font_combo.setCurrentFont(QFont(str(families[0])))
            except Exception:
                pass
        btn_font_file.clicked.connect(browse_font_file)

        def make_spin(value, lo, hi, suffix="", step=1):
            spin = QSpinBox(dlg)
            spin.setRange(int(lo), int(hi))
            spin.setSingleStep(int(step))
            spin.setValue(int(value))
            if suffix:
                spin.setSuffix(suffix)
            spin.setMinimumWidth(110)
            return spin

        sb_screen_w = make_spin(old_settings.get("screen_width", 816), 320, 4096, " px", step=16)
        add_row("게임 화면 너비", sb_screen_w, "왼쪽 프리뷰가 재현할 RPG Maker 게임 내부 화면 너비입니다. 오른쪽 패널 크기와 무관하게 이 값으로 줄내림을 계산합니다.")
        sb_screen_h = make_spin(old_settings.get("screen_height", 624), 240, 2160, " px", step=16)
        add_row("게임 화면 높이", sb_screen_h, "왼쪽 프리뷰가 재현할 RPG Maker 게임 내부 화면 높이입니다. MZ 커스텀 해상도 게임은 이 값이 특히 중요합니다.")
        sb_size = make_spin(old_settings.get("font_size", 28), 6, 96, " px")
        add_row("기본 글자 크기", sb_size, "대사 프리뷰의 기본 글자 크기입니다.")
        sb_name_size = make_spin(old_settings.get("name_font_size", 24), 6, 96, " px")
        add_row("이름창 글자 크기", sb_name_size, "이름창/화자 표시를 별도로 렌더링할 때 사용할 크기입니다. 이후 실제 이름창 프리뷰와 연결됩니다.")
        sb_choice_size = make_spin(old_settings.get("choice_font_size", 26), 6, 96, " px")
        add_row("선택지 글자 크기", sb_choice_size, "Show Choices 항목에 적용할 글자 크기입니다.")
        sb_width = make_spin(old_settings.get("char_width", 100), 10, 300, " %")
        add_row("폰트 너비", sb_width, "문자의 가로 비율입니다. 한글이 대사창에서 너무 넓거나 좁게 보일 때 조절합니다.")
        sb_height = make_spin(old_settings.get("char_height", 100), 10, 300, " %")
        add_row("폰트 높이", sb_height, "문자의 세로 비율입니다. 실제 메시지창 느낌에 맞게 조절합니다.")
        sb_line = make_spin(old_settings.get("line_spacing", 100), 50, 300, " %")
        add_row("행간", sb_line, "줄과 줄 사이 간격입니다.")
        sb_letter = make_spin(old_settings.get("letter_spacing", 0), -100, 200, " px")
        add_row("자간", sb_letter, "글자와 글자 사이 간격입니다.")
        sb_msg_w = make_spin(old_settings.get("message_width", 808), 120, 4096, " px", step=10)
        add_row("메시지창 기준 너비", sb_msg_w, "실제 게임 화면 안의 메시지창 폭입니다. 줄내림은 이 폭을 기준으로 고정 계산됩니다.")
        sb_msg_margin = make_spin(old_settings.get("message_margin", 4), 0, 120, " px")
        add_row("메시지창 바깥 여백", sb_msg_margin, "화면 가장자리와 메시지창 사이의 바깥 여백입니다.")
        sb_msg_lines = make_spin(old_settings.get("message_lines", 4), 1, 12, " 줄")
        add_row("메시지창 표시 줄 수", sb_msg_lines, "프리뷰 메시지창에 한 번에 표시할 줄 수입니다. 이 값을 넘으면 줄넘침 경고를 표시합니다.")
        sb_pad = make_spin(old_settings.get("message_padding", 18), 0, 120, " px")
        add_row("메시지창 안쪽 여백", sb_pad, "프리뷰 텍스트 박스 높이를 계산할 때 사용하는 안쪽 여백입니다.")
        sb_outline = make_spin(old_settings.get("outline_width", 3), 0, 20, " px")
        add_row("외곽선 두께", sb_outline, "메시지 텍스트 외곽선 두께입니다.")

        color_widget = QWidget(dlg)
        color_row = QHBoxLayout(color_widget)
        color_row.setContentsMargins(0, 0, 0, 0)
        color_row.setSpacing(8)
        le_text_color = QLineEdit(str(old_settings.get("text_color") or "#FFFFFF"), color_widget)
        le_outline_color = QLineEdit(str(old_settings.get("outline_color") or "#202020"), color_widget)
        color_row.addWidget(QLabel(self.tr_ui("글자"), color_widget))
        color_row.addWidget(le_text_color)
        color_row.addWidget(QLabel(self.tr_ui("외곽선"), color_widget))
        color_row.addWidget(le_outline_color)
        add_row("색상", color_widget, "#RRGGBB 형식으로 입력합니다. 색상 선택기는 이후 붙일 수 있게 입력칸으로 먼저 둡니다.")

        reset_row = QHBoxLayout()
        btn_refresh_runtime = QPushButton(self.tr_ui("게임 설정 다시 읽기"), dlg)
        btn_refresh_runtime.setToolTip(self.tr_ui("현재 작업 폴더의 maker_game에서 System.json, fonts, Window.png, MV/MZ 런타임 값을 다시 읽어 프리뷰 설정을 갱신합니다."))
        reset_row.addWidget(btn_refresh_runtime)
        reset_row.addStretch(1)
        btn_reset = QPushButton(self.tr_ui("기본값으로 돌아가기"), dlg)
        reset_row.addWidget(btn_reset)
        form.addLayout(reset_row)

        def reset_defaults():
            d = DEFAULT_MAKER_PREVIEW_SETTINGS
            try:
                font_combo.setCurrentFont(QFont(str(d.get("font_family") or "맑은 고딕")))
            except Exception:
                pass
            le_font_path.setText(str(d.get("font_path") or ""))
            sb_screen_w.setValue(int(d.get("screen_width") or 816))
            sb_screen_h.setValue(int(d.get("screen_height") or 624))
            sb_size.setValue(int(d.get("font_size") or 28))
            sb_name_size.setValue(int(d.get("name_font_size") or 24))
            sb_choice_size.setValue(int(d.get("choice_font_size") or 26))
            sb_width.setValue(int(d.get("char_width") or 100))
            sb_height.setValue(int(d.get("char_height") or 100))
            sb_line.setValue(int(d.get("line_spacing") or 100))
            sb_letter.setValue(int(d.get("letter_spacing") or 0))
            sb_msg_w.setValue(int(d.get("message_width") or 808))
            sb_msg_margin.setValue(int(d.get("message_margin") or 4))
            sb_msg_lines.setValue(int(d.get("message_lines") or 4))
            sb_pad.setValue(int(d.get("message_padding") or 18))
            sb_outline.setValue(int(d.get("outline_width") or 3))
            le_text_color.setText(str(d.get("text_color") or "#FFFFFF"))
            le_outline_color.setText(str(d.get("outline_color") or "#202020"))
        btn_reset.clicked.connect(reset_defaults)

        preview_row = QHBoxLayout()
        preview_row.setContentsMargins(0, 0, 0, 0)
        preview_row.setSpacing(10)
        preview_desc = QLabel(self.tr_ui("보조선, 이벤트 위치/이름, 이미지 반투명 표시 여부는 프리뷰 표시 옵션에서 관리합니다. 대사는 게임식 대사창/선택지 프리뷰로만 표시합니다."), box)
        preview_desc.setObjectName("SettingsDescription")
        preview_desc.setWordWrap(True)
        btn_preview_options = QPushButton(self.tr_ui("프리뷰 표시 옵션 열기"), box)
        btn_preview_options.clicked.connect(self.open_maker_preview_display_settings_dialog)
        preview_row.addWidget(preview_desc, 1)
        preview_row.addWidget(btn_preview_options, 0)
        form.addLayout(preview_row)

        root.addWidget(box, 1)

        save_applied = {"ok": False, "count": 0}

        def collect_settings():
            try:
                family = font_combo.currentFont().family()
            except Exception:
                family = str(old_settings.get("font_family") or "")
            # Preserve runtime-profile fields that are not yet exposed as direct
            # spin boxes.  The dialog edits the most common correction values, but
            # it must not throw away game-derived message/name-window metrics.
            merged = dict(old_settings or {})
            merged.update({
                "font_family": family,
                "font_path": le_font_path.text().strip(),
                "screen_width": sb_screen_w.value(),
                "screen_height": sb_screen_h.value(),
                "font_size": sb_size.value(),
                "name_font_size": sb_name_size.value(),
                "choice_font_size": sb_choice_size.value(),
                "char_width": sb_width.value(),
                "char_height": sb_height.value(),
                "line_spacing": sb_line.value(),
                "letter_spacing": sb_letter.value(),
                "message_width": sb_msg_w.value(),
                "message_margin": sb_msg_margin.value(),
                "message_lines": sb_msg_lines.value(),
                "message_padding": sb_pad.value(),
                "outline_width": sb_outline.value(),
                "text_color": le_text_color.text().strip(),
                "outline_color": le_outline_color.text().strip(),
            })
            return normalize_maker_preview_settings(merged)

        def apply_changes():
            try:
                self._reset_maker_preview_font_runtime_cache("preview_font_settings_apply")
            except Exception:
                pass
            settings = save_maker_preview_settings(project_dir, collect_settings())
            changed = apply_maker_preview_settings_to_data(getattr(self, "data", {}) or {}, settings)
            try:
                for i, path in enumerate(getattr(self, "paths", []) or []):
                    page = (getattr(self, "data", {}) or {}).get(i, {})
                    regenerate_maker_placeholder_for_page(path, page, settings=settings)
                    if isinstance(page, dict) and page.get("maker_page"):
                        page["maker_preview_settings"] = dict(settings)
            except Exception as e:
                try:
                    self.log(f"⚠️ 쯔꾸르 프리뷰 이미지 갱신 일부 실패: {e}")
                except Exception:
                    pass
            try:
                store = getattr(self, "project_store", None)
                if store is not None:
                    ui_state = getattr(store, "ui_state", {}) or {}
                    if not isinstance(ui_state, dict):
                        ui_state = {}
                    ui_state["maker_preview_settings"] = dict(settings)
                    store.ui_state = ui_state
            except Exception:
                pass
            try:
                if hasattr(self, "mark_project_structure_dirty"):
                    self.mark_project_structure_dirty("maker_preview_font_settings")
            except Exception:
                pass
            try:
                self.save_project_store(getattr(self, "project_store", None))
            except Exception:
                try:
                    self.auto_save_project()
                except Exception:
                    pass
            try:
                curr_mode = self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 0
                self.mode_chg(curr_mode)
            except Exception:
                pass
            try:
                if hasattr(self, "refresh_page_tabs"):
                    self.refresh_page_tabs()
            except Exception:
                pass
            save_applied["ok"] = True
            save_applied["count"] = int(changed)
            self.log(f"🔤 쯔꾸르 프리뷰 폰트 설정 저장: {settings.get('font_family')} / {settings.get('font_size')}px / 텍스트 {changed}개 갱신")

        def on_ok():
            if not self.ask_yes_no_shortcut(
                "쯔꾸르 프리뷰 폰트 설정 저장",
                "쯔꾸르 프리뷰 폰트 설정을 저장하고 현재 화면을 갱신할까요?",
                yes_text="저장",
                no_text="취소",
                default_yes=True,
                icon=QMessageBox.Icon.Question,
                parent=dlg,
            ):
                self.log("🔤 쯔꾸르 프리뷰 폰트 설정 저장 취소")
                return
            apply_changes()
            dlg.accept()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("닫기"))
        btns.accepted.connect(on_ok)
        btns.rejected.connect(dlg.reject)
        root.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted and save_applied.get("ok"):
            self.show_ok_notice("쯔꾸르 프리뷰 폰트 설정 저장 완료", f"{self.tr_ui('쯔꾸르 프리뷰 폰트 설정이 저장되었습니다.')}\n{self.tr_ui('갱신된 텍스트')}: {save_applied.get('count', 0)}")

    def _ensure_maker_project_for_settings(self, title="쯔꾸르 설정"):
        project_dir = str(getattr(self, "project_dir", "") or "").strip()
        if not project_dir:
            self.show_warn_notice(title, "프로젝트를 연 뒤 사용할 수 있습니다.")
            return ""
        try:
            is_maker = any(isinstance((page or {}).get("maker_page"), dict) for page in (getattr(self, "data", {}) or {}).values())
        except Exception:
            is_maker = False
        if not is_maker:
            self.show_warn_notice(title, "현재 프로젝트는 쯔꾸르 게임 프로젝트로 보이지 않습니다.")
            return ""
        return project_dir

    def _reset_maker_preview_font_runtime_cache(self, reason=""):
        """Forget per-session Qt font path/family cache before a Maker preview refresh.

        QFontDatabase itself is process-level, so the renderer loads changed font
        files through fingerprinted cache paths.  This method clears only our own
        fast path maps so the next preview rebuild resolves the current file state
        instead of reusing a family name selected before the user changed fonts.
        """
        try:
            self._maker_preview_loaded_font_paths = set()
            self._maker_preview_loaded_font_families = {}
            self._last_maker_preview_font_conversion_diag = {}
            self._last_maker_preview_font_load_diag = {}
            self._last_maker_preview_font_diag = {}
            if hasattr(self, "_append_maker_preview_diagnostic"):
                self._append_maker_preview_diagnostic("ui_font_runtime_cache_reset", {"reason": str(reason or "")})
        except Exception:
            pass

    def _refresh_maker_preview_after_settings(self, settings=None):
        try:
            self._reset_maker_preview_font_runtime_cache("maker_settings_refresh")
        except Exception:
            pass
        try:
            from ysb.tools.maker_project import apply_maker_preview_settings_to_data, regenerate_maker_placeholder_for_page, load_maker_preview_settings
            project_dir = str(getattr(self, "project_dir", "") or "")
            st = settings or load_maker_preview_settings(project_dir)
            apply_maker_preview_settings_to_data(getattr(self, "data", {}) or {}, st)
            for i, path in enumerate(getattr(self, "paths", []) or []):
                page = (getattr(self, "data", {}) or {}).get(i, {})
                if isinstance(page, dict) and page.get("maker_page"):
                    page["maker_preview_settings"] = dict(st)
                    if regenerate_maker_placeholder_for_page(path, page, settings=st):
                        try:
                            img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
                            if img is not None:
                                page["ori"] = img.copy()
                                page["bg_clean"] = img.copy()
                                page["working_source"] = None
                                page["bg_clean_path"] = str(path)
                        except Exception:
                            pass
            try:
                self.save_project_store(getattr(self, "project_store", None))
            except Exception:
                try:
                    self.auto_save_project()
                except Exception:
                    pass
            try:
                self.mode_chg(self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 4)
            except Exception:
                pass
        except Exception as e:
            try:
                self.log(f"⚠️ 쯔꾸르 프리뷰 갱신 실패: {e}")
            except Exception:
                pass

    def open_maker_prompt_verification_dialog(self, project_dir=None, prompts=None):
        """게임 프롬프트 관리 안에서 실제 번역 요청 프롬프트와 테스트 번역을 검증한다."""
        project_dir = project_dir or getattr(self, "project_dir", None)
        if not project_dir:
            self.show_warn_notice("입력 프롬프트 확인", "프로젝트를 연 뒤 사용할 수 있습니다.")
            return
        try:
            import json
            from ysb.tools.maker_project import (
                load_maker_character_prompts,
                normalize_maker_character_prompts,
                prepare_maker_translation_payload,
                maker_item_speaker,
            )
        except Exception as e:
            self.show_warn_notice("입력 프롬프트 확인", str(e)); return
        prompts = normalize_maker_character_prompts(prompts or load_maker_character_prompts(project_dir))

        def collect_rows(preview_kind="dialogue", max_per_speaker=2, max_total=30, current_first=True):
            """Collect representative rows for prompt verification.

            preview_kind:
            - dialogue: normal map/common/troop text prompt shape
            - database: database translation prompt shape, including DB-only system prompt
            """
            rows = []
            seen_counts = {}
            data = getattr(self, "data", {}) or {}
            page_order = []
            try:
                cur = int(getattr(self, "idx", 0) or 0)
                if current_first and cur in data:
                    page_order.append(cur)
            except Exception:
                pass
            for k in sorted(data.keys(), key=lambda x: int(x) if str(x).lstrip('-').isdigit() else 10**9):
                if k not in page_order:
                    page_order.append(k)
            want_database = str(preview_kind or "dialogue").lower() == "database"
            for page_idx in page_order:
                page = data.get(page_idx) or {}
                if not isinstance(page, dict):
                    continue
                maker_page = page.get("maker_page") if isinstance(page.get("maker_page"), dict) else {}
                for row_idx, item in enumerate(page.get("data") or []):
                    if not isinstance(item, dict):
                        continue
                    meta = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
                    source_kind = str((meta or {}).get("source_kind") or "map")
                    text_type = str((meta or {}).get("text_type") or "").lower()
                    is_database = source_kind == "database" or text_type.startswith("database")
                    if want_database:
                        if not is_database:
                            continue
                    else:
                        if is_database:
                            continue
                    speaker = str(maker_item_speaker(item) or "Unknown").strip() or "Unknown"
                    if not want_database:
                        if speaker == "Unknown":
                            continue
                        if int(seen_counts.get(speaker, 0)) >= int(max_per_speaker or 1):
                            continue
                    payload = prepare_maker_translation_payload(item, prompts)
                    text = str(payload.get("text") or "").strip()
                    if not text:
                        continue
                    db_kind = str((meta or {}).get("db_kind") or "")
                    db_field = str((meta or {}).get("db_field") or "")
                    db_id = str((meta or {}).get("db_id") if (meta or {}).get("db_id") is not None else "")
                    rows.append({
                        "page_idx": page_idx,
                        "row_idx": row_idx,
                        "speaker": speaker,
                        "map": str((meta or {}).get("map_name") or (maker_page or {}).get("map_name") or ""),
                        "event": str((meta or {}).get("event_name") or ""),
                        "db_kind": db_kind,
                        "db_field": db_field,
                        "db_id": db_id,
                        "text_type": str((meta or {}).get("text_type") or ""),
                        "source_kind": source_kind,
                        "text": text,
                        "context": str(payload.get("context") or ""),
                    })
                    if not want_database:
                        seen_counts[speaker] = int(seen_counts.get(speaker, 0)) + 1
                    if len(rows) >= int(max_total or 30):
                        return rows
            return rows

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("입력 프롬프트 확인"))
        dlg.resize(980, 720)
        dlg.setMinimumSize(760, 520)
        dlg.setSizeGripEnabled(True)
        try: dlg.setStyleSheet(self.settings_dialog_style())
        except Exception: pass
        root = QVBoxLayout(dlg); root.setContentsMargins(16,16,16,16); root.setSpacing(10)
        title = QLabel(self.tr_ui("입력 프롬프트 확인 / 번역 테스트"), dlg); title.setObjectName("SettingsTitle"); root.addWidget(title)
        desc = QLabel(self.tr_ui("실제 번역 API 요청에 들어가는 공용 프롬프트, 청크당 1회 적용 프롬프트, 줄별 화자 매칭을 확인합니다."), dlg); desc.setWordWrap(True); desc.setObjectName("SettingsDescription"); root.addWidget(desc)
        tabs = QTabWidget(dlg); root.addWidget(tabs, 1)

        tab_check = QWidget(tabs); check_layout = QVBoxLayout(tab_check); check_layout.setContentsMargins(8,8,8,8); check_layout.setSpacing(8)
        check_mode_row = QHBoxLayout(); check_mode_row.setSpacing(8)
        check_mode_row.addWidget(QLabel(self.tr_ui("확인할 번역 종류"), tab_check))
        cb_prompt_kind = QComboBox(tab_check)
        cb_prompt_kind.addItem(self.tr_ui("일반 대사 번역"), "dialogue")
        cb_prompt_kind.addItem(self.tr_ui("데이터베이스 번역"), "database")
        check_mode_row.addWidget(cb_prompt_kind)
        check_mode_row.addStretch(1)
        btn_refresh = QPushButton(self.tr_ui("현재 프롬프트 다시 확인"), tab_check); check_mode_row.addWidget(btn_refresh)
        check_layout.addLayout(check_mode_row)
        check_text = QPlainTextEdit(tab_check); check_text.setReadOnly(True); check_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap); check_layout.addWidget(check_text, 1)
        tabs.addTab(tab_check, self.tr_ui("프롬프트 확인"))

        tab_test = QWidget(tabs); test_layout = QVBoxLayout(tab_test); test_layout.setContentsMargins(8,8,8,8); test_layout.setSpacing(8)
        opt_row = QHBoxLayout(); opt_row.setSpacing(8)
        cb_test_kind = QComboBox(tab_test)
        cb_test_kind.addItem(self.tr_ui("일반 대사 번역"), "dialogue")
        cb_test_kind.addItem(self.tr_ui("데이터베이스 번역"), "database")
        sp_per = QSpinBox(tab_test); sp_per.setRange(1,5); sp_per.setValue(2)
        sp_total = QSpinBox(tab_test); sp_total.setRange(1,100); sp_total.setValue(30)
        opt_row.addWidget(QLabel(self.tr_ui("번역 종류"), tab_test)); opt_row.addWidget(cb_test_kind)
        opt_row.addWidget(QLabel(self.tr_ui("캐릭터별 대표 대사"), tab_test)); opt_row.addWidget(sp_per)
        opt_row.addWidget(QLabel(self.tr_ui("최대 줄 수"), tab_test)); opt_row.addWidget(sp_total)
        opt_row.addStretch(1)
        btn_test = QPushButton(self.tr_ui("대표 항목 번역 테스트"), tab_test); opt_row.addWidget(btn_test)
        test_layout.addLayout(opt_row)
        test_text = QPlainTextEdit(tab_test); test_text.setReadOnly(True); test_layout.addWidget(test_text, 1)
        tabs.addTab(tab_test, self.tr_ui("번역 테스트"))

        def ensure_engine_for_preview():
            if getattr(self, "engine", None) is None:
                try: self.restart_engine(show_error=False)
                except Exception: pass
            return getattr(self, "engine", None)

        def refresh_prompt_preview():
            preview_kind = str(cb_prompt_kind.currentData() or "dialogue")
            rows = collect_rows(preview_kind=preview_kind, max_per_speaker=2, max_total=50)
            if not rows:
                msg = "확인할 데이터베이스 번역 행을 찾지 못했습니다." if preview_kind == "database" else "확인할 대표 대사를 찾지 못했습니다."
                check_text.setPlainText(self.tr_ui(msg)); return
            engine = ensure_engine_for_preview()
            texts = [r["text"] for r in rows]
            contexts = [r["context"] for r in rows]
            try:
                preview = engine.preview_translation_request(texts, contexts=contexts, base_id=0) if engine is not None and hasattr(engine, "preview_translation_request") else {}
            except Exception as e:
                preview = {"error": f"{type(e).__name__}: {e}", "items": []}
            lines = []
            if preview_kind == "database":
                lines.append("[데이터베이스 번역 프롬프트 확인]")
                lines.append("이 미리보기는 데이터베이스 번역 청크 기준입니다. DB 전용 시스템 프롬프트가 이쪽에만 포함되어야 합니다.")
            else:
                lines.append("[일반 대사 번역 프롬프트 확인]")
                lines.append("이 미리보기는 일반 맵/이벤트 대사 번역 청크 기준입니다. DB 전용 시스템 프롬프트는 포함되면 안 됩니다.")
            lines.append("\n[청크당 1회 적용 프롬프트 묶음]")
            lines.append(str(preview.get("character_prompt_block") or "(없음)"))
            if preview_kind != "database" and str((prompts or {}).get("system_prompt") or "").strip():
                lines.append("\n[DB 전용 프롬프트 안내]")
                lines.append("DB 전용 프롬프트가 설정되어 있지만, 현재 일반 대사 미리보기에는 포함하지 않았습니다.")
            lines.append("\n[줄별 항목 매칭]")
            for i, r in enumerate(rows, 1):
                if preview_kind == "database":
                    matched = "Chunk prompt:" in str(r.get("context") or "")
                    loc = f"DB: {r.get('db_kind','')} / ID: {r.get('db_id','')} / Field: {r.get('db_field','')}"
                    lines.append(f"{i}. {loc} / DB Prompt: {'OK' if matched else '없음'}")
                else:
                    matched = "Character prompt:" in str(r.get("context") or "")
                    lines.append(f"{i}. Speaker: {r['speaker']} / Match: {'OK' if matched else '없음'} / {r.get('map','')} / {r.get('event','')}")
                lines.append(f"   Text: {r['text']}")
            lines.append("\n[실제 system prompt 미리보기]")
            lines.append(str(preview.get("system_prompt") or ""))
            lines.append("\n[실제 user payload 미리보기]")
            try:
                lines.append(json.dumps(preview.get("items") or [], ensure_ascii=False, indent=2))
            except Exception:
                lines.append(str(preview.get("items") or []))
            if preview.get("error"):
                lines.insert(0, "ERROR: " + str(preview.get("error")))
            check_text.setPlainText("\n".join(lines))

        def run_translation_test():
            test_kind = str(cb_test_kind.currentData() or "dialogue")
            rows = collect_rows(preview_kind=test_kind, max_per_speaker=sp_per.value(), max_total=sp_total.value())
            if not rows:
                msg = "테스트할 데이터베이스 번역 행을 찾지 못했습니다." if test_kind == "database" else "테스트할 대표 대사를 찾지 못했습니다."
                QMessageBox.information(dlg, self.tr_ui("번역 테스트"), self.tr_ui(msg)); return
            engine = ensure_engine_for_preview()
            if engine is None:
                QMessageBox.warning(dlg, self.tr_ui("번역 테스트"), self.tr_ui("번역 엔진을 초기화하지 못했습니다.")); return
            provider = self.cb_trans_provider.currentData() if hasattr(self, "cb_trans_provider") else "openai"
            texts = [r["text"] for r in rows]
            contexts = [r["context"] for r in rows]
            progress = QProgressDialog(dlg); progress.setWindowTitle(self.tr_ui("번역 테스트")); progress.setLabelText(self.tr_ui("대표 대사를 번역하는 중입니다...")); progress.setRange(0,0); progress.setCancelButton(None); progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            try: apply_progress_dialog_theme(progress, bool(self.is_light_theme()))
            except Exception: pass
            progress.show(); QApplication.processEvents()
            try:
                chunk_size = self.get_current_translation_chunk_size() if hasattr(self, "get_current_translation_chunk_size") else 50
                translated = engine.translate_text_batch(texts, provider=provider, chunk_size=chunk_size, contexts=contexts)
                out = []
                for i, (r, tr) in enumerate(zip(rows, translated or []), 1):
                    out.append(f"[{i}] {r['speaker']} / {r.get('map','')} / {r.get('event','')}")
                    out.append("원문: " + r["text"])
                    out.append("번역: " + str(tr or ""))
                    out.append("")
                test_text.setPlainText("\n".join(out).strip())
            except Exception as e:
                test_text.setPlainText(f"번역 테스트 실패: {type(e).__name__}: {e}")
            finally:
                try: progress.close(); progress.deleteLater(); QApplication.processEvents()
                except Exception: pass

        btn_refresh.clicked.connect(refresh_prompt_preview)
        try:
            cb_prompt_kind.currentIndexChanged.connect(lambda *_: refresh_prompt_preview())
        except Exception:
            pass
        btn_test.clicked.connect(run_translation_test)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dlg)
        try: buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.tr_ui("닫기"))
        except Exception: pass
        buttons.rejected.connect(dlg.reject); root.addWidget(buttons)
        refresh_prompt_preview()
        dlg.exec()

    def refresh_maker_game_dialogue_action(self):
        """Temporarily treat maker_game JSON as the master and import it.

        Normal editing is always program -> game.  This explicit action is the
        only reverse-sync boundary: current maker_game is read into the program,
        then the program immediately becomes the master again.
        """
        project_dir = self._ensure_maker_project_for_settings("게임 갱신")
        if not project_dir:
            return
        if not self.ask_yes_no_shortcut(
            "게임 갱신",
            "위험한 작업입니다. 현재 게임 JSON을 기준으로 프로그램의 대사/DB 구조와 번역문을 다시 가져옵니다.\n\n게임 쪽 값이 프로그램의 기존 번역문을 덮어쓸 수 있습니다. 계속할까요?",
            yes_text="갱신",
            no_text="취소",
            default_yes=False,
            icon=QMessageBox.Icon.Warning,
            parent=self,
        ):
            return
        try:
            from ysb.tools.maker_project import (
                build_maker_pages, detect_maker_engine, _maker_game_dir,
                _maker_original_json_backup_dir, backup_maker_original_json_snapshot,
            )
        except Exception as e:
            self.show_warn_notice("게임 갱신", str(e))
            return
        progress = None
        try:
            progress = self.show_maker_import_progress("게임 갱신", "현재 게임 JSON을 프로그램으로 가져오는 중입니다...") if hasattr(self, "show_maker_import_progress") else None
        except Exception:
            progress = None
        try:
            game_dir = _maker_game_dir(project_dir)
            if not game_dir.is_dir():
                raise RuntimeError("maker_game 폴더를 찾지 못했습니다.")
            backup_dir = _maker_original_json_backup_dir(project_dir)
            engine_info = detect_maker_engine(game_dir)

            try:
                if progress is not None:
                    self._maker_import_progress_update(progress, "현재 maker_game JSON을 읽는 중입니다...")
            except Exception:
                pass
            game_paths, game_data, _game_summary = build_maker_pages(project_dir, game_dir, engine_info)

            orig_data = {}
            if backup_dir.is_dir():
                try:
                    if progress is not None:
                        self._maker_import_progress_update(progress, "기존 원본 백업과 비교하는 중입니다...")
                except Exception:
                    pass
                try:
                    _orig_paths, orig_data, _orig_summary = build_maker_pages(project_dir, backup_dir, engine_info)
                except Exception:
                    orig_data = {}
            old_data = getattr(self, "data", {}) or {}

            def page_key(page):
                if not isinstance(page, dict):
                    return ""
                meta = page.get("maker_page") if isinstance(page.get("maker_page"), dict) else {}
                ptype = str(meta.get("page_type") or "map")
                src = str(meta.get("source_file") or meta.get("map_file") or meta.get("page_title") or meta.get("map_name") or "")
                return f"{ptype}::{src}"

            def row_key(row):
                if not isinstance(row, dict):
                    return ""
                meta = row.get("maker_text_unit") if isinstance(row.get("maker_text_unit"), dict) else {}
                src = str(meta.get("source_file") or meta.get("map_file") or "")
                path = str(meta.get("json_path") or "")
                if src or path:
                    return f"{src}::{path}"
                return str(row.get("id") or "")

            def _norm_text(v):
                return str(v or "").replace("\r\n", "\n").replace("\r", "\n")

            def _speaker_plain(row):
                if not isinstance(row, dict):
                    return ""
                meta = row.get("maker_text_unit") if isinstance(row.get("maker_text_unit"), dict) else {}
                return str(
                    row.get("maker_speaker_plain")
                    or row.get("maker_speaker")
                    or (meta.get("speaker_plain") if isinstance(meta, dict) else "")
                    or (meta.get("speaker") if isinstance(meta, dict) else "")
                    or ""
                ).strip()

            old_pages = {page_key(page): (idx, page) for idx, page in old_data.items() if isinstance(page, dict) and page_key(page)}
            orig_pages = {page_key(page): page for _idx, page in (orig_data or {}).items() if isinstance(page, dict) and page_key(page)}

            merged_data = {}
            touched_pages = []
            added_rows = 0
            updated_rows = 0
            translated_from_game = 0
            preserved_project_translations = 0
            new_pages = 0

            for gidx, game_page in (game_data or {}).items():
                if not isinstance(game_page, dict):
                    continue
                key = page_key(game_page)
                old_idx, old_page = old_pages.get(key, (None, None))
                orig_page = orig_pages.get(key) if isinstance(orig_pages, dict) else None
                old_rows = old_page.get("data") if isinstance(old_page, dict) else []
                orig_rows = orig_page.get("data") if isinstance(orig_page, dict) else []
                game_rows = game_page.get("data") or []
                old_by_key = {row_key(r): r for r in (old_rows or []) if row_key(r)}
                orig_by_key = {row_key(r): r for r in (orig_rows or []) if row_key(r)}

                merged_page = dict(game_page)
                merged_rows = []
                for gr in game_rows:
                    if not isinstance(gr, dict):
                        continue
                    nr = dict(gr)
                    ok = row_key(gr)
                    old_row = old_by_key.get(ok)
                    orig_row = orig_by_key.get(ok)
                    game_text = _norm_text(gr.get("text"))
                    original_text = _norm_text(orig_row.get("text")) if isinstance(orig_row, dict) else game_text
                    old_translation = _norm_text(old_row.get("translated_text")) if isinstance(old_row, dict) else ""

                    # Keep current maker_game command indexes/structure, but preserve
                    # the older source text when we have a known original-backup row.
                    nr["text"] = original_text

                    if isinstance(old_row, dict):
                        for keep in ("maker_memo", "maker_prompt_profile", "checked"):
                            if keep in old_row and old_row.get(keep) not in (None, ""):
                                nr[keep] = old_row.get(keep)
                        old_meta = old_row.get("maker_text_unit") if isinstance(old_row.get("maker_text_unit"), dict) else {}
                        new_meta = nr.get("maker_text_unit") if isinstance(nr.get("maker_text_unit"), dict) else {}
                        if isinstance(new_meta, dict) and isinstance(old_meta, dict):
                            for keep in ("prompt_profile",):
                                if keep in old_meta and old_meta.get(keep) not in (None, ""):
                                    new_meta[keep] = old_meta.get(keep)
                            nr["maker_text_unit"] = new_meta

                    if game_text and game_text != original_text:
                        nr["translated_text"] = game_text
                        translated_from_game += 1
                    elif old_translation:
                        nr["translated_text"] = old_translation
                        preserved_project_translations += 1
                    else:
                        nr["translated_text"] = ""
                    nr["maker_status"] = self.tr_ui("번역완료") if str(nr.get("translated_text") or "").strip() else self.tr_ui("미번역")

                    original_speaker = _speaker_plain(orig_row) if isinstance(orig_row, dict) else _speaker_plain(gr)
                    game_speaker = _speaker_plain(gr)
                    old_speaker = _speaker_plain(old_row) if isinstance(old_row, dict) else ""
                    chosen_speaker = ""
                    if old_speaker and old_speaker != original_speaker:
                        chosen_speaker = old_speaker
                    elif game_speaker and game_speaker != original_speaker:
                        chosen_speaker = game_speaker
                    if chosen_speaker:
                        nr["maker_speaker"] = chosen_speaker
                        nr["maker_speaker_plain"] = chosen_speaker
                        unit_meta = nr.get("maker_text_unit") if isinstance(nr.get("maker_text_unit"), dict) else {}
                        if isinstance(unit_meta, dict):
                            unit_meta["speaker"] = chosen_speaker
                            unit_meta["speaker_plain"] = chosen_speaker
                            unit_meta.setdefault("speaker_original", original_speaker)
                            unit_meta["speaker_source"] = "game_refresh" if chosen_speaker == game_speaker else "project_saved"
                            nr["maker_text_unit"] = unit_meta
                        nr.setdefault("maker_speaker_original", original_speaker)

                    if isinstance(old_row, dict):
                        updated_rows += 1
                    else:
                        added_rows += 1
                    merged_rows.append(nr)
                merged_page["data"] = merged_rows
                try:
                    meta = merged_page.get("maker_page") if isinstance(merged_page.get("maker_page"), dict) else {}
                    meta["text_unit_count"] = len(merged_rows)
                    meta["refresh_master"] = "maker_game"
                    meta["refresh_completed_at"] = datetime.now().isoformat(timespec="seconds")
                    merged_page["maker_page"] = meta
                except Exception:
                    pass
                try:
                    out_idx = int(gidx)
                except Exception:
                    out_idx = len(merged_data)
                merged_data[out_idx] = merged_page
                touched_pages.append(out_idx)
                if not isinstance(old_page, dict):
                    new_pages += 1

            try:
                self.paths = list(game_paths or [])
                self.data = merged_data
                if self.paths:
                    self.idx = max(0, min(int(getattr(self, "idx", 0) or 0), len(self.paths) - 1))
                else:
                    self.idx = 0
            except Exception:
                pass

            try:
                if progress is not None:
                    self._maker_import_progress_update(progress, "게임 갱신 기준 백업을 새로 고정하는 중입니다...")
            except Exception:
                pass
            try:
                backup_maker_original_json_snapshot(project_dir, game_dir, engine_info, overwrite=True)
            except Exception as e:
                try:
                    self.log(f"⚠️ 게임 갱신 기준 백업 재작성 실패: {e}")
                except Exception:
                    pass

            if touched_pages:
                try:
                    if hasattr(self, "mark_project_structure_dirty"):
                        self.mark_project_structure_dirty("maker_game_refresh_import_master")
                except Exception:
                    pass
                try:
                    for pidx in touched_pages:
                        if hasattr(self, "project_engine") and self.project_engine is not None:
                            self.project_engine.mark_page_dirty(int(pidx), "text")
                except Exception:
                    pass
                try:
                    self.has_unsaved_changes = True
                    self.save_project_store(getattr(self, "project_store", None), force_full=True)
                except Exception:
                    pass
                try:
                    # Boundary closes here: after refresh, program data is master again.
                    self.apply_maker_writeback_to_clone(mark_dirty=False, log_result=False, backup=False, page_indices=touched_pages)
                except Exception as e:
                    try:
                        self.log(f"⚠️ 게임 갱신 후 프로그램→게임 재고정 실패: {e}")
                    except Exception:
                        pass
                try:
                    self.ref_tab()
                    self.mode_chg(4)
                except Exception:
                    pass
            self.log(f"🔄 게임 갱신 완료: 페이지 {len(touched_pages)}개 / 새 페이지 {new_pages}개 / 기존 행 {updated_rows}개 / 새 행 {added_rows}개 / 게임 반영문 {translated_from_game}개 / 프로젝트 번역 보존 {preserved_project_translations}개")
            QMessageBox.information(self, self.tr_ui("게임 갱신"), self.tr_ui("게임 JSON 갱신이 완료되었습니다.\n이번 작업 동안만 maker_game을 마스터로 읽었고, 완료 후에는 다시 프로그램 데이터가 마스터입니다."))
        except Exception as e:
            self.show_warn_notice("게임 갱신 실패", str(e))
        finally:
            try:
                if progress is not None:
                    progress.close()
            except Exception:
                pass

    def _set_maker_title_in_program_data(self, title):
        """Set System.json gameTitle in the program table first.

        Title follows the same rule as dialogue: the program data is the master,
        and maker_game/System.json plus package/index sidecars are outputs.
        """
        touched_pages = []
        title = str(title or "")
        try:
            for page_idx, page in (getattr(self, "data", {}) or {}).items():
                if not isinstance(page, dict):
                    continue
                page_touched = False
                for row in page.get("data") or []:
                    if not isinstance(row, dict):
                        continue
                    meta = row.get("maker_text_unit") if isinstance(row.get("maker_text_unit"), dict) else {}
                    path_keys = meta.get("db_path_keys") if isinstance(meta, dict) else []
                    is_game_title = (
                        str(meta.get("source_file") or "") == "System.json"
                        and (
                            str(meta.get("db_field") or "") == "gameTitle"
                            or path_keys == ["gameTitle"]
                        )
                    )
                    if is_game_title:
                        row["translated_text"] = title
                        row["maker_status"] = self.tr_ui("번역완료") if title else self.tr_ui("미번역")
                        page_touched = True
                if page_touched:
                    try:
                        touched_pages.append(int(page_idx))
                    except Exception:
                        pass
        except Exception:
            pass
        return touched_pages

    def _show_maker_font_restart_notice(self):
        msg = self.tr_ui("프로그램을 껐다 켜면 변경한 폰트가 적용됩니다.")
        try:
            QMessageBox.information(self, self.tr_ui("폰트 변경 안내"), msg)
        except Exception:
            try:
                self.show_warn_notice("폰트 변경 안내", msg)
            except Exception:
                pass

    def open_maker_game_settings_dialog(self):
        project_dir = self._ensure_maker_project_for_settings("게임 설정")
        if not project_dir:
            return
        try:
            from ysb.tools.maker_project import (
                list_maker_game_fonts, maker_fonts_dir, load_maker_preview_settings,
                normalize_maker_preview_settings, apply_maker_game_font_settings,
                apply_maker_preview_settings_to_data, load_maker_game_title,
                _maker_project_engine_info, _engine_id_from_info,
            )
        except Exception as e:
            self.show_warn_notice("게임 설정", str(e)); return
        old = normalize_maker_preview_settings(load_maker_preview_settings(project_dir))
        try: game_title = load_maker_game_title(project_dir)
        except Exception: game_title = ""
        try:
            engine_info = _maker_project_engine_info(project_dir) or {}
            engine_id = _engine_id_from_info(engine_info)
        except Exception:
            engine_info = {}; engine_id = "unknown"

        dlg = QDialog(self); dlg.setWindowTitle(self.tr_ui("게임 설정")); dlg.resize(840, 620); dlg.setMinimumSize(720, 500); dlg.setSizeGripEnabled(True)
        try: dlg.setStyleSheet(self.settings_dialog_style())
        except Exception: pass
        root = QVBoxLayout(dlg); root.setContentsMargins(16,16,16,16); root.setSpacing(10)
        title = QLabel(self.tr_ui("게임 설정"), dlg); title.setObjectName("SettingsTitle"); root.addWidget(title)
        desc = QLabel(self.tr_ui("게임 타이틀과 실제 게임 폰트를 설정합니다. 폰트는 클론 게임 fonts 폴더에 들어 있는 파일만 선택할 수 있습니다."), dlg); desc.setWordWrap(True); desc.setObjectName("SettingsDescription"); root.addWidget(desc)
        font_dir_label = QLabel(str(maker_fonts_dir(project_dir)), dlg); font_dir_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); font_dir_label.setObjectName("SettingsPath"); root.addWidget(font_dir_label)
        title_row = QFormLayout(); le_title = QLineEdit(str(game_title or old.get("game_title") or ""), dlg); title_row.addRow(self.tr_ui("타이틀명"), le_title); root.addLayout(title_row)
        tabs = QTabWidget(dlg); root.addWidget(tabs, 1)

        def make_combo(parent):
            cb = QComboBox(parent)
            cb.addItem(self.tr_ui("선택 안 함"), "")
            for f in list_maker_game_fonts(project_dir):
                fn = str(f.get("filename") or "")
                if fn:
                    cb.addItem(fn, fn)
            return cb
        def set_combo(cb, value):
            idx = cb.findData(str(value or ""))
            if idx >= 0: cb.setCurrentIndex(idx)

        mv_tab = QWidget(tabs); mv_form = QFormLayout(mv_tab); mv_form.setContentsMargins(12,12,12,12); mv_form.setSpacing(10)
        mv_main = make_combo(mv_tab); set_combo(mv_main, old.get("main_font_filename"))
        mv_size = QSpinBox(mv_tab); mv_size.setRange(6,96); mv_size.setValue(int(old.get("font_size") or 28)); mv_size.setSuffix(" px")
        mv_line = QSpinBox(mv_tab); mv_line.setRange(12,160); mv_line.setValue(int(old.get("line_height") or 36)); mv_line.setSuffix(" px")
        mv_padding = QSpinBox(mv_tab); mv_padding.setRange(0,80); mv_padding.setValue(int(old.get("message_padding") or 18)); mv_padding.setSuffix(" px")
        mv_form.addRow(self.tr_ui("메인 폰트"), mv_main); mv_form.addRow(self.tr_ui("글자 크기"), mv_size); mv_form.addRow(self.tr_ui("라인 높이"), mv_line); mv_form.addRow(self.tr_ui("대사창 패딩"), mv_padding)
        tabs.addTab(mv_tab, self.tr_ui("MV 설정"))

        mz_tab = QWidget(tabs); mz_form = QFormLayout(mz_tab); mz_form.setContentsMargins(12,12,12,12); mz_form.setSpacing(10)
        mz_main = make_combo(mz_tab); set_combo(mz_main, old.get("main_font_filename"))
        mz_number = make_combo(mz_tab); set_combo(mz_number, old.get("number_font_filename") or old.get("main_font_filename"))
        mz_fallback = QLineEdit(str(old.get("fallback_fonts") or "Verdana, sans-serif"), mz_tab)
        mz_size = QSpinBox(mz_tab); mz_size.setRange(6,96); mz_size.setValue(int(old.get("font_size") or 26)); mz_size.setSuffix(" px")
        mz_opacity = QSpinBox(mz_tab); mz_opacity.setRange(0,255); mz_opacity.setValue(int(old.get("window_opacity") or 192))
        mz_form.addRow(self.tr_ui("메인 폰트"), mz_main); mz_form.addRow(self.tr_ui("숫자 폰트"), mz_number); mz_form.addRow(self.tr_ui("대체 폰트"), mz_fallback); mz_form.addRow(self.tr_ui("글자 크기"), mz_size); mz_form.addRow(self.tr_ui("창 투명도"), mz_opacity)
        tabs.addTab(mz_tab, self.tr_ui("MZ 설정"))
        tabs.setCurrentIndex(1 if engine_id == "mz" else 0)

        btn_row = QHBoxLayout(); btn_open = QPushButton(self.tr_ui("fonts 폴더 열기"), dlg); btn_row.addStretch(1); btn_row.addWidget(btn_open); root.addLayout(btn_row)
        btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(maker_fonts_dir(project_dir)))))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인")); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("취소")); root.addWidget(buttons)
        def on_ok():
            old_main_font = str(old.get("main_font_filename") or "")
            old_number_font = str(old.get("number_font_filename") or old.get("main_font_filename") or "")
            merged = dict(old); merged["game_title"] = le_title.text().strip()
            if tabs.currentIndex() == 1:
                merged.update({"main_font_filename": str(mz_main.currentData() or ""), "number_font_filename": str(mz_number.currentData() or ""), "fallback_fonts": mz_fallback.text().strip(), "font_size": mz_size.value(), "window_opacity": mz_opacity.value()})
            else:
                merged.update({"main_font_filename": str(mv_main.currentData() or ""), "number_font_filename": str(mv_main.currentData() or ""), "font_size": mv_size.value(), "line_height": mv_line.value(), "message_padding": mv_padding.value()})
            try:
                fixed = apply_maker_game_font_settings(project_dir, merged)
                touched_title_pages = self._set_maker_title_in_program_data(le_title.text().strip())
                apply_maker_preview_settings_to_data(getattr(self, "data", {}) or {}, fixed)
                if touched_title_pages:
                    self.apply_maker_writeback_to_clone(mark_dirty=False, log_result=False, backup=False, page_indices=touched_title_pages)
                    try:
                        self.mark_project_structure_dirty("maker_game_title")
                    except Exception:
                        pass
                    try:
                        self.save_workspace_project_json_light(reason="maker_game_title")
                    except Exception:
                        pass
                self._refresh_maker_preview_after_settings(fixed)
                self.log(f"🎮 게임 설정 저장: {le_title.text().strip() or '-'}")
                font_changed = (str(merged.get("main_font_filename") or "") != old_main_font) or (str(merged.get("number_font_filename") or "") != old_number_font)
                font_changed = font_changed or (str(fixed.get("main_font_fingerprint") or "") != str(old.get("main_font_fingerprint") or ""))
                dlg.accept()
                if font_changed:
                    self._show_maker_font_restart_notice()
            except Exception as e:
                self.show_warn_notice("게임 설정 실패", str(e))
        buttons.accepted.connect(on_ok); buttons.rejected.connect(dlg.reject); dlg.exec()

    def open_maker_game_font_settings_dialog(self):
        project_dir = self._ensure_maker_project_for_settings("실제 게임 폰트 설정")
        if not project_dir:
            return
        try:
            from ysb.tools.maker_project import (
                list_maker_game_fonts, maker_fonts_dir, load_maker_preview_settings,
                normalize_maker_preview_settings, apply_maker_game_font_settings,
                apply_maker_preview_settings_to_data,
            )
        except Exception as e:
            self.show_warn_notice("실제 게임 폰트 설정", str(e)); return
        old = normalize_maker_preview_settings(load_maker_preview_settings(project_dir))
        dlg = QDialog(self); dlg.setWindowTitle(self.tr_ui("실제 게임 폰트 설정")); dlg.resize(720, 560)
        try: dlg.setStyleSheet(self.settings_dialog_style())
        except Exception: pass
        root = QVBoxLayout(dlg); root.setContentsMargins(16,16,16,16); root.setSpacing(10)
        title = QLabel(self.tr_ui("실제 게임 폰트 설정"), dlg); title.setObjectName("SettingsDialogTitle"); root.addWidget(title)
        desc = QLabel(self.tr_ui("클론 게임의 fonts 폴더에 들어 있는 폰트만 선택할 수 있습니다. 저장하면 실제 클론 게임 JSON/CSS와 쯔꾸르붕이 프리뷰에 함께 반영됩니다."), dlg); desc.setWordWrap(True); desc.setObjectName("SettingsDescription"); root.addWidget(desc)
        fonts_dir_label = QLabel(str(maker_fonts_dir(project_dir)), dlg); fonts_dir_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); fonts_dir_label.setObjectName("SettingsPath"); root.addWidget(fonts_dir_label)
        row = QHBoxLayout(); combo = QComboBox(dlg); row.addWidget(combo,1)
        btn_refresh = QPushButton(self.tr_ui("목록 새로고침"), dlg); btn_open = QPushButton(self.tr_ui("fonts 폴더 열기"), dlg); row.addWidget(btn_refresh); row.addWidget(btn_open); root.addLayout(row)
        form = QFormLayout(); root.addLayout(form)
        def spin(v, lo, hi, suffix=""):
            sp=QSpinBox(dlg); sp.setRange(lo,hi); sp.setValue(int(v)); sp.setSuffix(suffix); return sp
        sb_size=spin(old.get("font_size",28),6,96," px"); sb_name=spin(old.get("name_font_size",28),6,96," px"); sb_choice=spin(old.get("choice_font_size",28),6,96," px")
        sb_width=spin(old.get("char_width",100),10,300," %"); sb_height=spin(old.get("char_height",100),10,300," %"); sb_line=spin(old.get("line_spacing",100),50,300," %"); sb_letter=spin(old.get("letter_spacing",0),-100,200," px")
        for lab,w in (("기본 글자 크기",sb_size),("이름창 글자 크기",sb_name),("선택지 글자 크기",sb_choice),("폰트 너비",sb_width),("폰트 높이",sb_height),("행간",sb_line),("자간",sb_letter)):
            form.addRow(self.tr_ui(lab), w)
        status = QLabel("", dlg); status.setObjectName("SettingsDescription"); status.setWordWrap(True); root.addWidget(status)
        font_items=[]
        def reload_fonts():
            nonlocal font_items
            combo.clear(); font_items=list_maker_game_fonts(project_dir)
            cur = str(old.get("main_font_filename") or "")
            if not font_items:
                combo.addItem(self.tr_ui("fonts 폴더에 폰트가 없습니다"), "")
                status.setText(self.tr_ui("사용할 폰트를 클론 게임의 fonts 폴더에 넣은 뒤 새로고침하세요."))
                return
            for f in font_items:
                combo.addItem(str(f.get("filename") or ""), str(f.get("filename") or ""))
            idx = combo.findData(cur)
            if idx >= 0: combo.setCurrentIndex(idx)
            status.setText(self.tr_ui("선택 가능한 폰트") + f": {len(font_items)}개")
        def open_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(maker_fonts_dir(project_dir))))
        btn_refresh.clicked.connect(reload_fonts); btn_open.clicked.connect(open_dir); reload_fonts()
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel, dlg); buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인")); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("취소")); root.addWidget(buttons)
        def on_ok():
            filename = str(combo.currentData() or "")
            if not filename:
                self.show_warn_notice("실제 게임 폰트 설정", "fonts 폴더에 폰트를 넣고 선택해야 합니다."); return
            old_filename = str(old.get("main_font_filename") or "")
            merged=dict(old); merged.update({"main_font_filename": filename, "number_font_filename": filename, "font_size": sb_size.value(), "name_font_size": sb_name.value(), "choice_font_size": sb_choice.value(), "char_width": sb_width.value(), "char_height": sb_height.value(), "line_spacing": sb_line.value(), "letter_spacing": sb_letter.value()})
            try:
                fixed=apply_maker_game_font_settings(project_dir, merged)
                apply_maker_preview_settings_to_data(getattr(self,"data",{}) or {}, fixed)
                self._refresh_maker_preview_after_settings(fixed)
                self.log(f"🔤 실제 게임 폰트 설정 저장: {filename}")
                font_changed = filename != old_filename
                font_changed = font_changed or (str(fixed.get("main_font_fingerprint") or "") != str(old.get("main_font_fingerprint") or ""))
                dlg.accept()
                if font_changed:
                    self._show_maker_font_restart_notice()
            except Exception as e:
                self.show_warn_notice("실제 게임 폰트 설정 실패", str(e))
        buttons.accepted.connect(on_ok); buttons.rejected.connect(dlg.reject); dlg.exec()

    def open_maker_preview_display_settings_dialog(self):
        project_dir = self._ensure_maker_project_for_settings("프리뷰 표시 옵션")
        if not project_dir: return
        try:
            from ysb.tools.maker_project import load_maker_preview_settings, save_maker_preview_settings, normalize_maker_preview_settings
        except Exception as e:
            self.show_warn_notice("프리뷰 표시 옵션", str(e)); return
        old=normalize_maker_preview_settings(load_maker_preview_settings(project_dir))
        dlg=QDialog(self); dlg.setWindowTitle(self.tr_ui("프리뷰 표시 옵션")); dlg.resize(560,430); dlg.setMinimumSize(460, 340); dlg.setSizeGripEnabled(True)
        try: dlg.setStyleSheet(self.settings_dialog_style())
        except Exception: pass
        root=QVBoxLayout(dlg); root.setContentsMargins(16,16,16,16); root.setSpacing(10)
        title=QLabel(self.tr_ui("프리뷰 표시 옵션"), dlg); title.setObjectName("SettingsDialogTitle"); root.addWidget(title)
        cb_local=QCheckBox(self.tr_ui("선택 대사 주변 간이 맵 프리뷰 표시"), dlg); cb_local.setChecked(bool(old.get("show_local_map_preview", True)))
        cb_local.setToolTip(self.tr_ui("현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다."))
        cb_tile=QCheckBox(self.tr_ui("타일셋 기반 맵 배경 프리뷰 사용 (2단계)"), dlg); cb_tile.setChecked(bool(old.get("show_tile_map_preview", True)))
        cb_tile.setToolTip(self.tr_ui("가능하면 Tilesets.json과 img/tilesets를 읽어 현재 이벤트 주변의 실제 타일 배경을 일부 보여줍니다. 실패하면 1단계 격자 프리뷰로 안전하게 돌아갑니다."))
        cb_adv=QCheckBox(self.tr_ui("고급 맵 재현 프리뷰 사용 (3단계)"), dlg); cb_adv.setChecked(bool(old.get("show_advanced_map_preview", True)))
        cb_adv.setToolTip(self.tr_ui("가능하면 오토타일을 대표 형태로 표시하고, 그림자/이벤트 그래픽/별표 우선순위 타일을 일부 반영합니다. 완전한 엔진 재현은 아니며, 실패 시 2단계 또는 1단계 프리뷰로 돌아갑니다."))
        cb_tile_validation=QCheckBox(self.tr_ui("타일 검수 로그/이미지 덤프 저장"), dlg); cb_tile_validation.setChecked(bool(old.get("enable_tile_validation_dump", False)))
        cb_tile_validation.setToolTip(self.tr_ui("디버깅할 때만 켜세요. 켜면 maker_meta 아래에 타일 trace JSON과 raw/post PNG 검증 덤프를 저장합니다. 대사 이동 시 렉이 생길 수 있으므로 평소에는 꺼두는 것을 권장합니다."))
        cb_grid=QCheckBox(self.tr_ui("맵 그리드/보조선 표시"), dlg); cb_grid.setChecked(bool(old.get("show_map_grid")))
        cb_event=QCheckBox(self.tr_ui("이벤트 위치 실선/점선 표시"), dlg); cb_event.setChecked(bool(old.get("show_event_positions")))
        cb_overlay=QCheckBox(self.tr_ui("이벤트 이름 오버레이 표시"), dlg); cb_overlay.setChecked(bool(old.get("show_event_text_overlay")))
        cb_picture_opacity=QCheckBox(self.tr_ui("게임 원래 반투명 연출 반영"), dlg); cb_picture_opacity.setChecked(bool(old.get("show_picture_opacity")))
        cb_picture_opacity.setToolTip(self.tr_ui("꺼두면 번역자가 보기 쉽도록 스탠딩/표시 이미지를 항상 불투명하게 보여줍니다. 켜면 게임 원래 opacity 값을 반영합니다. 실제 게임 JSON은 바꾸지 않습니다."))
        for cb in (cb_local, cb_tile, cb_adv, cb_tile_validation, cb_grid, cb_event, cb_overlay, cb_picture_opacity): root.addWidget(cb)
        note_text = self.tr_ui(
            "검수용 프리뷰 표시 옵션입니다.\n\n"
            "1단계: 선택된 대사의 이벤트 주변을 간이 맵/격자/이벤트 점으로 보여줍니다.\n\n"
            "2단계: 가능하면 Tilesets.json과 img/tilesets 이미지를 읽어 실제 타일 배경 분위기를 보여줍니다.\n\n"
            "3단계: 가능하면 오토타일 대표형, 그림자, 이벤트 그래픽, 별표 우선순위 타일까지 일부 반영합니다.\n\n"
            "실패 시 자동으로 2단계 또는 1단계 프리뷰로 돌아갑니다.\n\n"
            "타일 검수 로그/이미지 덤프는 디버깅용이므로 평소에는 꺼두세요.\n\n"
            "실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다."
        )
        note=QLabel(note_text, dlg); note.setWordWrap(True); note.setObjectName("SettingsDescription")
        note_scroll = QScrollArea(dlg); note_scroll.setWidgetResizable(True); note_scroll.setFrameShape(QFrame.Shape.NoFrame); note_scroll.setWidget(note); root.addWidget(note_scroll, 1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel, dlg); buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인")); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("취소")); root.addWidget(buttons)
        def on_ok():
            st=dict(old); st.update({"show_local_map_preview": cb_local.isChecked(), "show_tile_map_preview": cb_tile.isChecked(), "show_advanced_map_preview": cb_adv.isChecked(), "enable_tile_validation_dump": cb_tile_validation.isChecked(), "show_map_grid": cb_grid.isChecked(), "show_event_positions": cb_event.isChecked(), "show_event_text_overlay": cb_overlay.isChecked(), "show_canvas_text_overlay": False, "show_picture_opacity": cb_picture_opacity.isChecked()})
            fixed=save_maker_preview_settings(project_dir, st); self._refresh_maker_preview_after_settings(fixed); self.log("🧭 프리뷰 표시 옵션 저장"); dlg.accept()
        buttons.accepted.connect(on_ok); buttons.rejected.connect(dlg.reject); dlg.exec()

    def open_maker_title_settings_dialog(self):
        project_dir = self._ensure_maker_project_for_settings("타이틀명 변경")
        if not project_dir: return
        try:
            from ysb.tools.maker_project import load_maker_game_title, save_maker_game_title
        except Exception as e:
            self.show_warn_notice("타이틀명 변경", str(e)); return
        old=load_maker_game_title(project_dir)
        dlg=QDialog(self); dlg.setWindowTitle(self.tr_ui("타이틀명 변경")); dlg.resize(520,200)
        try: dlg.setStyleSheet(self.settings_dialog_style())
        except Exception: pass
        root=QVBoxLayout(dlg); root.setContentsMargins(16,16,16,16)
        root.addWidget(QLabel(self.tr_ui("클론 게임의 System.json gameTitle을 직접 변경합니다."), dlg))
        edit=QLineEdit(old, dlg); root.addWidget(edit)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel, dlg); buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인")); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("취소")); root.addWidget(buttons)
        def on_ok():
            title = edit.text().strip()
            touched_pages = self._set_maker_title_in_program_data(title)
            try:
                if touched_pages:
                    self.apply_maker_writeback_to_clone(mark_dirty=False, log_result=False, backup=False, page_indices=touched_pages)
                else:
                    # Very old projects may not have a System.json DB row in the
                    # program table.  Fall back to direct write, but keep the log clear.
                    title = save_maker_game_title(project_dir, title)
                    self.log("⚠️ 프로그램 데이터에서 gameTitle 행을 찾지 못해 직접 System.json에 반영했습니다.")
            except Exception as e:
                try: self.log(f"⚠️ 타이틀명 JSON 반영 실패: {e}")
                except Exception: pass
                self.show_warn_notice("타이틀명 변경 실패", str(e))
                return
            try:
                self.has_unsaved_changes = True
                if hasattr(self, "mark_project_structure_dirty"):
                    self.mark_project_structure_dirty("maker_game_title")
                if hasattr(self, "save_workspace_project_json_light"):
                    self.save_workspace_project_json_light(reason="maker_game_title")
            except Exception: pass
            try:
                if hasattr(self, "refresh_maker_database_view") and hasattr(self, "is_maker_database_mode") and self.is_maker_database_mode():
                    self.refresh_maker_database_view()
            except Exception: pass
            self.log(f"🏷️ 타이틀명 변경: {title}"); dlg.accept()
        buttons.accepted.connect(on_ok); buttons.rejected.connect(dlg.reject); dlg.exec()

    def open_maker_terms_translation_dialog(self):
        project_dir = self._ensure_maker_project_for_settings("인게임 용어 번역")
        if not project_dir: return
        try:
            from ysb.tools.maker_project import collect_maker_system_terms, apply_maker_system_terms
        except Exception as e:
            self.show_warn_notice("인게임 용어 번역", str(e)); return
        rows=collect_maker_system_terms(project_dir)
        dlg=QDialog(self); dlg.setWindowTitle(self.tr_ui("인게임 용어 번역")); dlg.resize(900,650)
        try: dlg.setStyleSheet(self.settings_dialog_style())
        except Exception: pass
        root=QVBoxLayout(dlg); root.setContentsMargins(14,14,14,14)
        root.addWidget(QLabel(self.tr_ui("HP/MP/공격/방어/장비 등 System.json terms를 별도로 번역합니다."), dlg))
        table=QTableWidget(dlg); table.setColumnCount(3); table.setHorizontalHeaderLabels([self.tr_ui("경로"), self.tr_ui("원문"), self.tr_ui("번역/적용값")]); table.horizontalHeader().setStretchLastSection(True); table.setRowCount(len(rows)); root.addWidget(table,1)
        for r,row in enumerate(rows):
            for c,key in enumerate(("key","source","translation")):
                it=QTableWidgetItem(str(row.get(key) or "")); it.setData(Qt.ItemDataRole.UserRole, row.get("path"))
                if c<2: it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r,c,it)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel, dlg); buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인")); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("취소")); root.addWidget(buttons)
        def on_ok():
            new_rows=[]
            for r in range(table.rowCount()):
                path=table.item(r,0).data(Qt.ItemDataRole.UserRole) if table.item(r,0) else None
                trans=table.item(r,2).text() if table.item(r,2) else ""
                new_rows.append({"path": path, "translation": trans})
            changed=apply_maker_system_terms(project_dir,new_rows)
            self.log(f"📘 인게임 용어 번역 저장: {changed}개 변경")
            dlg.accept()
        buttons.accepted.connect(on_ok); buttons.rejected.connect(dlg.reject); dlg.exec()


    def _maker_actor_name_translation_map(self):
        """Return Actors.json name translations only.

        Database translation is the master for actor display names.  Only
        database rows whose maker metadata points to Actors.name are allowed to
        feed the character-name translation table; item/skill/system/plugin text
        must not override speaker names.
        """
        mapping = {}
        try:
            data = getattr(self, "data", {}) or {}
            for _page_idx, curr in data.items():
                if not isinstance(curr, dict):
                    continue
                for row in curr.get("data", []) or []:
                    if not isinstance(row, dict):
                        continue
                    meta = row.get("maker_text_unit") if isinstance(row.get("maker_text_unit"), dict) else {}
                    if not meta:
                        meta = row.get("maker_meta") if isinstance(row.get("maker_meta"), dict) else {}
                    db_kind = str(meta.get("db_kind") or "").strip().lower()
                    db_field = str(meta.get("db_field") or "").strip().lower()
                    if db_kind not in ("actors", "actors.json") or db_field != "name":
                        continue
                    source = str(row.get("text") or "").strip()
                    target = str(row.get("translated_text") or "").strip()
                    if source and target:
                        mapping[source] = target
        except Exception:
            pass
        return mapping

    def _apply_maker_actor_name_master_to_speakers(self, actor_map=None, *, refresh=True, write_cache=True):
        """Push Actors.name translations into speaker/display names.

        Returns the number of speaker rows changed.  This is intentionally based
        only on Actors.name data so unrelated DB terms cannot corrupt character
        names.
        """
        if actor_map is None:
            actor_map = self._maker_actor_name_translation_map()
        if not actor_map:
            return 0
        changed = 0
        try:
            data = getattr(self, "data", {}) or {}
            for _page_idx, curr in data.items():
                if not isinstance(curr, dict):
                    continue
                # Database virtual pages are the source side, not targets for speaker sync.
                page_meta = curr.get("maker_page") if isinstance(curr.get("maker_page"), dict) else {}
                if str(page_meta.get("page_type") or "") == "database":
                    continue
                for row in curr.get("data", []) or []:
                    if not isinstance(row, dict):
                        continue
                    meta = row.get("maker_meta") if isinstance(row.get("maker_meta"), dict) else {}
                    current = str(row.get("maker_speaker") or meta.get("speaker") or row.get("speaker") or "").strip()
                    if not current or current.lower() == "unknown":
                        continue
                    original = str(row.get("maker_speaker_original") or meta.get("speaker_original") or current).strip()
                    if not original or original not in actor_map:
                        continue
                    new_name = str(actor_map.get(original) or original).strip() or original
                    if row.get("maker_speaker_original") is None:
                        row["maker_speaker_original"] = original
                    if isinstance(meta, dict) and meta.get("speaker_original") is None:
                        meta["speaker_original"] = original
                    before = str(row.get("maker_speaker") or meta.get("speaker") or "")
                    if before != new_name:
                        changed += 1
                    row["maker_speaker"] = new_name
                    row["maker_speaker_source"] = "actor_database"
                    row["maker_speaker_confidence"] = 1.0
                    row["maker_speaker_actor_master"] = True
                    if isinstance(meta, dict):
                        meta["speaker"] = new_name
                        meta["speaker_source"] = "actor_database"
                        meta["speaker_confidence"] = 1.0
                        meta["speaker_actor_master"] = True
                        row["maker_meta"] = meta
        except Exception:
            pass
        if changed and refresh:
            try:
                self.fill_table()
            except Exception:
                pass
            try:
                self.update_maker_preview_selection_from_table()
            except Exception:
                pass
        if changed and write_cache:
            try:
                self.mark_project_structure_dirty("maker_actor_name_master_sync")
            except Exception:
                pass
            try:
                self.start_work_cache_from_current(mark_dirty=True)
            except Exception:
                pass
        return changed

    def open_maker_database_translation_dialog(self):
        project_dir = self._ensure_maker_project_for_settings("데이터베이스 번역")
        if not project_dir: return
        try:
            from ysb.tools.maker_project import collect_maker_database_glossary, save_maker_database_glossary
        except Exception as e:
            self.show_warn_notice("데이터베이스 번역", str(e)); return
        db_pages=self.maker_database_page_indices() if hasattr(self,"maker_database_page_indices") else []
        dlg=QDialog(self); dlg.setWindowTitle(self.tr_ui("데이터베이스 번역")); dlg.resize(960,680)
        try: dlg.setStyleSheet(self.settings_dialog_style())
        except Exception: pass
        root=QVBoxLayout(dlg); root.setContentsMargins(14,14,14,14)
        desc=QLabel(self.tr_ui("아이템/스킬/장비/상태이상 등 데이터베이스 텍스트를 대사보다 먼저 번역합니다. 저장 시 클론 게임 JSON에 바로 반영됩니다."), dlg); desc.setWordWrap(True); root.addWidget(desc)
        table=QTableWidget(dlg); table.setColumnCount(5); table.setHorizontalHeaderLabels(["page","row",self.tr_ui("종류"),self.tr_ui("원문"),self.tr_ui("번역문")]); table.horizontalHeader().setStretchLastSection(True); table.setColumnHidden(0,True); table.setColumnHidden(1,True); root.addWidget(table,1)
        records=[]
        for page_idx in db_pages:
            page=(getattr(self,"data",{}) or {}).get(page_idx) or {}
            for data_i,row in enumerate(page.get("data") or []):
                meta=row.get("maker_text_unit") or {}
                records.append((page_idx,data_i,row,meta))
        table.setRowCount(len(records))
        for r,(page_idx,data_i,row,meta) in enumerate(records):
            vals=[str(page_idx),str(data_i), f"{meta.get('db_kind','')}.{meta.get('db_field','')}", str(row.get("text") or ""), str(row.get("translated_text") or "")]
            for c,val in enumerate(vals):
                it=QTableWidgetItem(val)
                if c<4: it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r,c,it)
        btn_row=QHBoxLayout(); btn_ai=QPushButton(self.tr_ui("DB 미번역 일괄 번역"), dlg); btn_gloss=QPushButton(self.tr_ui("번역된 DB를 단어장 후보로 저장"), dlg); btn_row.addWidget(btn_ai); btn_row.addWidget(btn_gloss); btn_row.addStretch(1); root.addLayout(btn_row)
        def save_table_to_data():
            touched=set(); changed=0
            for r in range(table.rowCount()):
                try: page_idx=int(table.item(r,0).text()); data_i=int(table.item(r,1).text())
                except Exception: continue
                trans=table.item(r,4).text() if table.item(r,4) else ""
                row=(getattr(self,"data",{}) or {}).get(page_idx,{}).get("data",[])[data_i]
                if str(row.get("translated_text") or "") != trans:
                    row["translated_text"]=trans; row["maker_status"]=self.tr_ui("번역완료") if trans.strip() else self.tr_ui("미번역"); touched.add(page_idx); changed+=1
            actor_sync_changed = 0
            if touched:
                self.apply_maker_writeback_to_clone(mark_dirty=False, log_result=False, backup=False, page_indices=sorted(touched))
                try:
                    if hasattr(self, "refresh_maker_database_auto_glossary"):
                        self.refresh_maker_database_auto_glossary(show_log=False)
                except Exception:
                    pass
                try:
                    actor_sync_changed = self._apply_maker_actor_name_master_to_speakers(refresh=False, write_cache=False)
                except Exception:
                    actor_sync_changed = 0
                try: self.fill_table()
                except Exception: pass
                try: self.update_maker_preview_selection_from_table()
                except Exception: pass
                if actor_sync_changed:
                    try:
                        self.mark_project_structure_dirty("maker_actor_name_master_sync")
                    except Exception:
                        pass
                    try:
                        self.start_work_cache_from_current(mark_dirty=True)
                    except Exception:
                        pass
            return changed
        def do_ai():
            dlg.accept(); self.run_maker_database_batch_translate()
        def do_gloss():
            save_table_to_data(); entries=collect_maker_database_glossary(getattr(self,"data",{}) or {}); path=save_maker_database_glossary(project_dir, entries)
            try:
                count = self.refresh_maker_database_auto_glossary(show_log=True) if hasattr(self, "refresh_maker_database_auto_glossary") else len(entries)
            except Exception:
                count = len(entries)
            self.show_ok_notice("DB 단어장 저장", f"DB name 단어장 후보 {count}개를 저장했습니다.\n{path}")
        btn_ai.clicked.connect(do_ai); btn_gloss.clicked.connect(do_gloss)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel, dlg); buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("저장")); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("닫기")); root.addWidget(buttons)
        def on_ok():
            changed=save_table_to_data(); self.log(f"🗃️ 데이터베이스 번역 저장: {changed}개 변경"); dlg.accept()
        buttons.accepted.connect(on_ok); buttons.rejected.connect(dlg.reject); dlg.exec()

    def open_analysis_mask_settings_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("분석 마스크 확장 비율"))
        dlg.resize(660, 500)
        dlg.setStyleSheet(self.settings_dialog_style())
        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(self.tr_ui("분석 마스크 확장 비율"), dlg)
        title.setObjectName("SettingsTitle")
        root.addWidget(title)

        desc = QLabel(self.tr_ui("OCR/분석 결과로 만들어지는 마스크의 여유 범위와 최소 확장 크기를 조절합니다. 최소 확장 크기를 0px로 두면 강제 최소 확장을 사용하지 않습니다."), dlg)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        root.addWidget(desc)

        form_box = QFrame(dlg)
        form_box.setObjectName("SettingsItem")
        form_layout = QVBoxLayout(form_box)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(12)

        old_text_ratio = clamp_analysis_mask_ratio(
            self.app_options.get(ANALYSIS_TEXT_MASK_EXPAND_RATIO_KEY, DEFAULT_ANALYSIS_TEXT_MASK_EXPAND_RATIO),
            DEFAULT_ANALYSIS_TEXT_MASK_EXPAND_RATIO,
        )
        old_paint_ratio = clamp_analysis_mask_ratio(
            self.app_options.get(ANALYSIS_PAINT_MASK_EXPAND_RATIO_KEY, DEFAULT_ANALYSIS_PAINT_MASK_EXPAND_RATIO),
            DEFAULT_ANALYSIS_PAINT_MASK_EXPAND_RATIO,
        )
        old_text_min_px = clamp_analysis_mask_min_px(
            self.app_options.get(ANALYSIS_TEXT_MASK_MIN_EXPAND_PX_KEY, DEFAULT_ANALYSIS_TEXT_MASK_MIN_EXPAND_PX),
            DEFAULT_ANALYSIS_TEXT_MASK_MIN_EXPAND_PX,
        )
        old_paint_min_px = clamp_analysis_mask_min_px(
            self.app_options.get(ANALYSIS_PAINT_MASK_MIN_EXPAND_PX_KEY, DEFAULT_ANALYSIS_PAINT_MASK_MIN_EXPAND_PX),
            DEFAULT_ANALYSIS_PAINT_MASK_MIN_EXPAND_PX,
        )

        def make_ratio_spin(value):
            spin = QDoubleSpinBox(dlg)
            spin.setRange(0.00, 2.00)
            spin.setDecimals(2)
            spin.setSingleStep(0.05)
            spin.setValue(float(value))
            spin.setSuffix(" x")
            spin.setMinimumWidth(120)
            return spin

        def make_px_spin(value):
            spin = QSpinBox(dlg)
            spin.setRange(0, 100)
            spin.setSingleStep(1)
            spin.setValue(int(value))
            spin.setSuffix(" px")
            spin.setMinimumWidth(120)
            return spin

        def add_setting_row(title_text, description_text, editor):
            row = QHBoxLayout()
            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
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

        spin_text = make_ratio_spin(old_text_ratio)
        add_setting_row(
            "텍스트 마스크 확장 비율",
            "분석 결과의 텍스트 마스크를 묶고 확장하는 비율입니다. 말풍선 글자 테두리가 덜 잡히면 이 값을 올리세요.",
            spin_text,
        )

        spin_text_min = make_px_spin(old_text_min_px)
        add_setting_row(
            "텍스트 마스크 최소 확장 크기",
            "텍스트 마스크를 만들 때 비율 계산값이 작아도 최소로 확장할 픽셀 크기입니다. 0px이면 최소 확장 강제를 사용하지 않습니다.",
            spin_text_min,
        )

        line = QFrame(dlg)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        form_layout.addWidget(line)

        spin_paint = make_ratio_spin(old_paint_ratio)
        add_setting_row(
            "페인트 마스크 확장 비율",
            "인페인팅/페인트 마스크를 만들 때 글자 주변을 얼마나 여유 있게 지울지 정합니다. 배경까지 너무 많이 잡히면 이 값을 낮추세요.",
            spin_paint,
        )

        spin_paint_min = make_px_spin(old_paint_min_px)
        add_setting_row(
            "페인트 마스크 최소 확장 크기",
            "페인트 마스크를 만들 때 비율 계산값이 작아도 최소로 확장할 픽셀 크기입니다. 0px이면 최소 확장 강제를 사용하지 않습니다.",
            spin_paint_min,
        )

        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        btn_reset = QPushButton(self.tr_ui("기본값으로 돌아가기"), dlg)
        reset_row.addWidget(btn_reset)
        form_layout.addLayout(reset_row)

        def reset_defaults():
            spin_text.setValue(DEFAULT_ANALYSIS_TEXT_MASK_EXPAND_RATIO)
            spin_text_min.setValue(DEFAULT_ANALYSIS_TEXT_MASK_MIN_EXPAND_PX)
            spin_paint.setValue(DEFAULT_ANALYSIS_PAINT_MASK_EXPAND_RATIO)
            spin_paint_min.setValue(DEFAULT_ANALYSIS_PAINT_MASK_MIN_EXPAND_PX)

        btn_reset.clicked.connect(reset_defaults)
        root.addWidget(form_box)
        root.addStretch(1)

        save_applied = {"ok": False, "restart": False}

        def apply_changes():
            text_ratio = clamp_analysis_mask_ratio(spin_text.value(), DEFAULT_ANALYSIS_TEXT_MASK_EXPAND_RATIO)
            paint_ratio = clamp_analysis_mask_ratio(spin_paint.value(), DEFAULT_ANALYSIS_PAINT_MASK_EXPAND_RATIO)
            text_min_px = clamp_analysis_mask_min_px(spin_text_min.value(), DEFAULT_ANALYSIS_TEXT_MASK_MIN_EXPAND_PX)
            paint_min_px = clamp_analysis_mask_min_px(spin_paint_min.value(), DEFAULT_ANALYSIS_PAINT_MASK_MIN_EXPAND_PX)
            self.app_options[ANALYSIS_TEXT_MASK_EXPAND_RATIO_KEY] = text_ratio
            self.app_options[ANALYSIS_PAINT_MASK_EXPAND_RATIO_KEY] = paint_ratio
            self.app_options[ANALYSIS_TEXT_MASK_MIN_EXPAND_PX_KEY] = text_min_px
            self.app_options[ANALYSIS_PAINT_MASK_MIN_EXPAND_PX_KEY] = paint_min_px
            self.sync_analysis_mask_options_to_config()
            self.save_app_options_cache()
            self.log(f"🎭 분석 마스크 확장 설정 저장: 텍스트 {text_ratio:.2f}/{text_min_px}px, 페인트 {paint_ratio:.2f}/{paint_min_px}px")
            save_applied["ok"] = True

        def on_ok():
            if not self.ask_yes_no_shortcut(
                "분석 마스크 설정 저장",
                "분석 마스크 확장 설정을 저장할까요?",
                yes_text="저장",
                no_text="취소",
                default_yes=True,
                icon=QMessageBox.Icon.Question,
                parent=dlg,
            ):
                self.log("🎭 분석 마스크 확장 설정 저장 취소")
                return
            apply_changes()
            dlg.accept()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("닫기"))
        btns.accepted.connect(on_ok)
        btns.rejected.connect(dlg.reject)
        root.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted and save_applied.get("ok"):
            self.show_ok_notice("분석 마스크 설정 저장 완료", "분석 마스크 확장 설정이 저장되었습니다.")

    def open_maker_character_name_translation_dialog(self):
        """화자명만 모아서 일괄 치환한다.

        Normal table cells show a plain speaker name.  If an MV inline-name line
        used control codes (for example \\MX...\\C[23]天子), this dialog shows that
        raw shell for review, but edits only the plain display/translation name.
        """
        try:
            from ysb.tools.maker_project import strip_maker_control_codes
        except Exception:
            def strip_maker_control_codes(value):
                return str(value or "")
        if not getattr(self, "data", None):
            QMessageBox.information(self, self.tr_ui("화자 번역"), self.tr_ui("불러온 맵 데이터가 없습니다."))
            return
        actor_master_map = self._maker_actor_name_translation_map()
        entries = {}
        for page_idx, curr in (getattr(self, "data", {}) or {}).items():
            if not isinstance(curr, dict):
                continue
            page_meta = curr.get("maker_page") if isinstance(curr.get("maker_page"), dict) else {}
            page_type = str((page_meta or {}).get("page_type") or "map").strip().lower()
            source_file = str((page_meta or {}).get("source_file") or (page_meta or {}).get("map_file") or "").strip()
            # 화자 번역은 실제 대사 맥락만 대상으로 한다. System/Troops/DB 가상 페이지는 말하는 인물이 아니므로 제외한다.
            if page_type not in ("", "map", "common_events") or source_file in ("System.json", "Troops.json") or source_file.startswith("DB_"):
                continue
            for row in curr.get("data", []) or []:
                if not isinstance(row, dict):
                    continue
                unit_meta = row.get("maker_text_unit") if isinstance(row.get("maker_text_unit"), dict) else {}
                legacy_meta = row.get("maker_meta") if isinstance(row.get("maker_meta"), dict) else {}
                row_source_file = str(unit_meta.get("source_file") or unit_meta.get("map_file") or legacy_meta.get("source_file") or "").strip()
                if row_source_file in ("System.json", "Troops.json") or row_source_file.startswith("DB_"):
                    continue
                plain_current = str(
                    row.get("maker_speaker_plain")
                    or unit_meta.get("speaker_plain")
                    or strip_maker_control_codes(row.get("maker_speaker") or "")
                    or strip_maker_control_codes(legacy_meta.get("speaker") or "")
                    or strip_maker_control_codes(row.get("speaker") or "")
                    or ""
                ).strip()
                if not plain_current or plain_current.lower() == "unknown":
                    continue
                original = str(
                    row.get("maker_speaker_original")
                    or unit_meta.get("speaker_original")
                    or unit_meta.get("speaker_plain")
                    or legacy_meta.get("speaker_original")
                    or plain_current
                ).strip()
                if not original or original.lower() == "unknown":
                    continue
                raw_visible = str(unit_meta.get("speaker_raw_visible") or "").strip()
                info = entries.setdefault(original, {"current": plain_current, "count": 0, "raw_samples": set()})
                info["current"] = str(actor_master_map.get(original) or plain_current)
                info["actor_master"] = bool(original in actor_master_map)
                info["count"] = int(info.get("count") or 0) + 1
                if raw_visible:
                    try:
                        info.setdefault("raw_samples", set()).add(raw_visible)
                    except Exception:
                        pass
        if not entries:
            QMessageBox.information(self, self.tr_ui("화자 번역"), self.tr_ui("화자 데이터가 없습니다."))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr_ui("화자 번역"))
        dialog.resize(780, 560)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        desc = QLabel(self.tr_ui("화자명만 따로 수정합니다. 일반 표의 화자 칸은 제어코드 없는 이름만 보여주고, 이 창에서 제어코드 포함 원본 화자 줄을 확인할 수 있습니다. Actors 데이터베이스의 이름 번역이 있는 항목은 DB를 마스터로 삼아 자동 반영됩니다."), dialog)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        table = TextTableWidget(len(entries), 4, dialog)
        table.setHorizontalHeaderLabels([self.tr_ui("원래 화자"), self.tr_ui("제어코드 포함 원본"), self.tr_ui("번역/표시 이름"), self.tr_ui("사용 수")])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        try:
            table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
            table.setProperty("ysb_excel_like_text_table", True)
            table.setProperty("ysb_copy_blank_line_between_rows", True)
        except Exception:
            pass
        try:
            table.horizontalHeader().setStretchLastSection(False)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        except Exception:
            pass
        originals = sorted(entries.keys(), key=lambda x: x.casefold())
        for r, original in enumerate(originals):
            info = entries[original]
            raw_samples = sorted(list(info.get("raw_samples") or []), key=lambda x: (len(x), x))
            raw_text = "\n".join(raw_samples[:3])
            if len(raw_samples) > 3:
                raw_text += f"\n… +{len(raw_samples)-3}"
            item_original = QTableWidgetItem(original)
            item_original.setFlags(item_original.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(r, 0, item_original)
            item_raw = QTableWidgetItem(raw_text)
            item_raw.setFlags(item_raw.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if raw_text:
                item_raw.setToolTip(raw_text)
            table.setItem(r, 1, item_raw)
            item_current = QTableWidgetItem(str(info.get("current") or original))
            if bool(info.get("actor_master")):
                item_current.setFlags(item_current.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item_current.setToolTip(self.tr_ui("Actors 데이터베이스 번역을 따르는 항목입니다."))
            table.setItem(r, 2, item_current)
            item_count = QTableWidgetItem(str(info.get("count") or 0))
            item_count.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_count.setFlags(item_count.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(r, 3, item_count)
        try:
            table.resizeRowsToContents()
        except Exception:
            pass
        layout.addWidget(table, 1)
        extra_row = QHBoxLayout()
        extra_row.addStretch(1)
        btn_translate_names = QPushButton(self.tr_ui("화자명 번역"), dialog)
        btn_translate_names.setToolTip(self.tr_ui("이 창의 화자명만 현재 선택한 번역 API로 번역합니다."))
        extra_row.addWidget(btn_translate_names)
        layout.addLayout(extra_row)

        def _speaker_table_copy_selected_cells():
            try:
                text = table.selected_text_for_clipboard() if hasattr(table, "selected_text_for_clipboard") else ""
                if text == "":
                    item = table.currentItem()
                    text = str(item.text() if item is not None else "")
                if text == "":
                    return False
                QApplication.clipboard().setText(text)
                return True
            except Exception:
                return False

        def _speaker_table_paste_translation_cells():
            try:
                try:
                    current_col = int(table.currentColumn())
                except Exception:
                    current_col = -1
                try:
                    selected_columns = {int(idx.column()) for idx in table.selectedIndexes()}
                except Exception:
                    selected_columns = set()
                # 붙여넣기는 사용자가 수정하는 번역/표시 이름 열에만 허용한다.
                if current_col != 2 and 2 not in selected_columns:
                    return False
                blocks = self.parse_maker_single_column_clipboard_blocks(QApplication.clipboard().text()) if hasattr(self, "parse_maker_single_column_clipboard_blocks") else []
                if not blocks:
                    return False
                try:
                    start_row = int(table.currentRow())
                except Exception:
                    start_row = 0
                if start_row < 0:
                    start_row = 0
                applied = 0
                for offset, value in enumerate(blocks):
                    row_no = start_row + offset
                    if row_no >= table.rowCount():
                        break
                    original = originals[row_no] if 0 <= row_no < len(originals) else ""
                    if original in actor_master_map:
                        continue
                    item = table.item(row_no, 2)
                    if item is None:
                        item = QTableWidgetItem("")
                        table.setItem(row_no, 2, item)
                    item.setText(str(value or ""))
                    applied += 1
                if applied:
                    try:
                        end_row = min(table.rowCount() - 1, start_row + max(0, applied) - 1)
                        table.clearSelection()
                        if end_row >= start_row:
                            table.setRangeSelected(QTableWidgetSelectionRange(start_row, 2, end_row, 2), True)
                        table.setCurrentCell(start_row, 2)
                        item0 = table.item(start_row, 2)
                        if item0 is not None:
                            table.scrollToItem(item0, QAbstractItemView.ScrollHint.PositionAtCenter)
                    except Exception:
                        pass
                return applied > 0
            except Exception:
                return False

        class _SpeakerTableClipboardFilter(QObject):
            def eventFilter(self, obj, event):
                try:
                    if event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
                        key = event.key()
                        mods = event.modifiers()
                        if mods & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_C:
                            if event.type() == QEvent.Type.ShortcutOverride:
                                event.accept(); return True
                            if _speaker_table_copy_selected_cells():
                                event.accept(); return True
                        if mods & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_V:
                            try:
                                fw = QApplication.focusWidget()
                            except Exception:
                                fw = None
                            # 셀 편집기 안에서는 일반 텍스트 붙여넣기를 우선한다.
                            if isinstance(fw, (QLineEdit, QTextEdit, QPlainTextEdit)):
                                return False
                            if event.type() == QEvent.Type.ShortcutOverride:
                                event.accept(); return True
                            if _speaker_table_paste_translation_cells():
                                event.accept(); return True
                except Exception:
                    pass
                return False

        speaker_table_filter = _SpeakerTableClipboardFilter(dialog)
        table.installEventFilter(speaker_table_filter)
        table.viewport().installEventFilter(speaker_table_filter)
        dialog._ysb_speaker_table_clipboard_filter = speaker_table_filter

        def translate_speaker_name_rows():
            try:
                if hasattr(self, "ensure_engine_ready") and not self.ensure_engine_ready():
                    return
                provider = self.cb_trans_provider.currentData() if hasattr(self, "cb_trans_provider") else "openai"
                if hasattr(self, "check_translation_api_key_or_alert") and not self.check_translation_api_key_or_alert(provider):
                    return
                rows = []
                texts = []
                contexts = []
                for r, original in enumerate(originals):
                    if original in actor_master_map:
                        continue
                    src = str(original or "").strip()
                    if not src:
                        continue
                    rows.append(r)
                    texts.append(src)
                    contexts.append("Translate only this RPG Maker speaker/character name into natural Korean. Return only the translated name, no explanation.")
                if not texts:
                    QMessageBox.information(dialog, self.tr_ui("화자 번역"), self.tr_ui("번역할 화자명이 없습니다."))
                    return
                progress = QProgressDialog(dialog)
                progress.setWindowTitle(self.tr_ui("화자명 번역"))
                progress.setLabelText(self.tr_ui("화자명을 번역하는 중입니다..."))
                progress.setRange(0, 0)
                progress.setCancelButton(None)
                progress.setWindowModality(Qt.WindowModality.ApplicationModal)
                try:
                    apply_progress_dialog_theme(progress, bool(self.is_light_theme()))
                except Exception:
                    pass
                progress.show(); QApplication.processEvents()
                chunk_size = self.get_current_translation_chunk_size() if hasattr(self, "get_current_translation_chunk_size") else 50
                translated = self.engine.translate_text_batch(texts, provider=provider, chunk_size=chunk_size, contexts=contexts)
                for r, val in zip(rows, translated or []):
                    item = table.item(r, 2)
                    if item is not None:
                        item.setText(str(val or "").strip() or texts[rows.index(r)])
                progress.close(); progress.deleteLater(); QApplication.processEvents()
                try:
                    self.log(f"👤 화자명 번역 완료: {len(rows)}개")
                except Exception:
                    pass
            except Exception as e:
                try:
                    progress.close()
                except Exception:
                    pass
                QMessageBox.warning(dialog, self.tr_ui("화자명 번역 실패"), str(e))

        btn_translate_names.clicked.connect(translate_speaker_name_rows)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        try:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("적용"))
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("취소"))
        except Exception:
            pass
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        mapping = {}
        for r, original in enumerate(originals):
            item = table.item(r, 2)
            value = str(item.text() if item is not None else "").strip()
            if original in actor_master_map:
                mapping[original] = str(actor_master_map.get(original) or original).strip() or original
            else:
                mapping[original] = value or original
        changed = 0
        touched_pages = set()
        try:
            self.commit_current_page_ui_to_data()
        except Exception:
            pass
        for page_idx, curr in (getattr(self, "data", {}) or {}).items():
            if not isinstance(curr, dict):
                continue
            page_meta = curr.get("maker_page") if isinstance(curr.get("maker_page"), dict) else {}
            page_type = str((page_meta or {}).get("page_type") or "map").strip().lower()
            source_file = str((page_meta or {}).get("source_file") or (page_meta or {}).get("map_file") or "").strip()
            if page_type not in ("", "map", "common_events") or source_file in ("System.json", "Troops.json") or source_file.startswith("DB_"):
                continue
            for row in curr.get("data", []) or []:
                if not isinstance(row, dict):
                    continue
                unit_meta = row.get("maker_text_unit") if isinstance(row.get("maker_text_unit"), dict) else {}
                legacy_meta = row.get("maker_meta") if isinstance(row.get("maker_meta"), dict) else {}
                row_source_file = str(unit_meta.get("source_file") or unit_meta.get("map_file") or legacy_meta.get("source_file") or "").strip()
                if row_source_file in ("System.json", "Troops.json") or row_source_file.startswith("DB_"):
                    continue
                current = str(row.get("maker_speaker_plain") or unit_meta.get("speaker_plain") or strip_maker_control_codes(row.get("maker_speaker") or "") or strip_maker_control_codes(legacy_meta.get("speaker") or "") or strip_maker_control_codes(row.get("speaker") or "") or "").strip()
                original = str(row.get("maker_speaker_original") or unit_meta.get("speaker_original") or unit_meta.get("speaker_plain") or legacy_meta.get("speaker_original") or current).strip()
                if not original or original not in mapping:
                    continue
                new_name = mapping.get(original) or original
                if row.get("maker_speaker_original") is None:
                    row["maker_speaker_original"] = original
                row["maker_speaker"] = new_name
                row["maker_speaker_plain"] = new_name
                row["maker_speaker_source"] = "speaker_translation"
                row["maker_speaker_confidence"] = 1.0
                if isinstance(unit_meta, dict):
                    if unit_meta.get("speaker_original") is None:
                        unit_meta["speaker_original"] = original
                    unit_meta["speaker"] = new_name
                    unit_meta["speaker_plain"] = new_name
                    unit_meta["speaker_source"] = "speaker_translation"
                    unit_meta["speaker_confidence"] = 1.0
                    row["maker_text_unit"] = unit_meta
                if isinstance(legacy_meta, dict):
                    if legacy_meta.get("speaker_original") is None:
                        legacy_meta["speaker_original"] = original
                    legacy_meta["speaker"] = new_name
                    legacy_meta["speaker_source"] = "speaker_translation"
                    legacy_meta["speaker_confidence"] = 1.0
                    row["maker_meta"] = legacy_meta
                changed += 1
                try:
                    touched_pages.add(int(page_idx))
                except Exception:
                    pass
        if touched_pages:
            try:
                # 화자 번역도 실제 게임 클론 JSON에 즉시 반영한다.
                # project.json에만 저장되면 표에는 보이지만 게임 적용 파일에는 빠질 수 있다.
                self.apply_maker_writeback_to_clone(
                    mark_dirty=False,
                    log_result=False,
                    backup=False,
                    page_indices=sorted(touched_pages),
                )
            except Exception as e:
                try:
                    self.log(f"⚠️ 화자 번역 게임 JSON 반영 실패: {e}")
                except Exception:
                    pass
        try:
            self.ref_tab()
            self.update_maker_preview_selection_from_table()
        except Exception:
            pass
        try:
            self.mark_project_structure_dirty("maker_speaker_translation")
        except Exception:
            pass
        try:
            # 화자 번역은 게임 JSON writeback만으로 끝내면 다음 열기 때 사라질 수 있다.
            # 작업 본체인 project.json에도 즉시 확정 저장한다.
            self.save_project_store(getattr(self, "project_store", None), force_full=True)
        except Exception:
            try:
                self.schedule_deferred_auto_save_project(300)
            except Exception:
                pass
        try:
            self.start_work_cache_from_current(mark_dirty=True)
        except Exception:
            pass
        try:
            page_count = len(touched_pages or [])
        except Exception:
            page_count = 0
        self.log(f"👤 화자 번역 적용: {changed}개 대사 갱신 / 게임 JSON 반영 맵 {page_count}개")

    def open_maker_character_prompts_dialog(self):
        """옵션 > 쯔꾸르 캐릭터 프롬프트 관리.

        Project-level character prompt profiles. OK saves into maker_meta and
        marks TextUnits with their prompt profile key. Cancel/X discards edits.
        """
        try:
            from ysb.tools.maker_project import (
                apply_maker_character_prompts_to_data,
                collect_maker_speakers_from_data,
                ensure_maker_character_prompt_profiles,
                load_maker_character_prompts,
                normalize_maker_character_prompt_profile,
                normalize_maker_character_prompts,
                save_maker_character_prompts,
                sync_maker_character_prompts_to_current_speakers,
            )
        except Exception as e:
            QMessageBox.critical(self, self.tr_ui("설정 오류"), f"{self.tr_ui('쯔꾸르 캐릭터 프롬프트 관리를 열 수 없습니다.')}\n{e}")
            return

        project_dir = str(getattr(self, "project_dir", "") or "").strip()
        if not project_dir:
            QMessageBox.information(self, self.tr_ui("프로젝트 없음"), self.tr_ui("쯔꾸르 캐릭터 프롬프트는 프로젝트를 연 뒤 사용할 수 있습니다."))
            return

        is_maker = False
        try:
            ui_state = getattr(getattr(self, "project_store", None), "ui_state", {}) or {}
            if str(ui_state.get("project_kind") or "").startswith("rpg_maker_"):
                is_maker = True
        except Exception:
            pass
        if not is_maker:
            try:
                is_maker = any(isinstance((page or {}).get("maker_page"), dict) and (page or {}).get("maker_page") for page in (getattr(self, "data", {}) or {}).values())
            except Exception:
                is_maker = False
        if not is_maker:
            QMessageBox.information(self, self.tr_ui("쯔꾸르 프로젝트 아님"), self.tr_ui("현재 프로젝트에는 쯔꾸르 맵 페이지 정보가 없습니다. 게임 가져오기 후 사용해 주세요."))
            return

        try:
            prompts = ensure_maker_character_prompt_profiles(project_dir, getattr(self, "data", {}) or {})
        except Exception:
            prompts = load_maker_character_prompts(project_dir)
        prompts = sync_maker_character_prompts_to_current_speakers(prompts, getattr(self, "data", {}) or {})
        speakers = collect_maker_speakers_from_data(getattr(self, "data", {}) or {})
        allowed_speaker_keys = [str(sp).strip() for sp in speakers if str(sp).strip()]
        allowed_speaker_set = set(allowed_speaker_keys)
        chars = prompts.setdefault("characters", {})

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("게임 프롬프트 관리"))
        dlg.resize(920, 620)
        dlg.setMinimumSize(760, 460)
        dlg.setSizeGripEnabled(True)
        dlg.setStyleSheet(self.settings_dialog_style())
        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(self.tr_ui("게임 프롬프트 관리"), dlg)
        title.setObjectName("SettingsTitle")
        root.addWidget(title)

        desc = QLabel(self.tr_ui("공통 프롬프트, 캐릭터 프롬프트, 데이터베이스 전용 프롬프트를 한곳에서 관리합니다. 확인을 누르면 저장되고, 닫기나 X를 누르면 저장하지 않습니다."), dlg)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        root.addWidget(desc)

        prompt_tabs = QTabWidget(dlg)
        root.addWidget(prompt_tabs, 1)

        PROMPT_PRESETS_KEY = "maker_prompt_presets"

        def _normalize_prompt_presets(raw):
            clean = []
            seen = set()
            if isinstance(raw, list):
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip()
                    text = str(item.get("text") or "")
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    clean.append({"name": name, "text": text})
            return clean

        def _prompt_presets_root():
            opts = getattr(self, "app_options", {})
            if not isinstance(opts, dict):
                self.app_options = {}
                opts = self.app_options
            root_presets = opts.get(PROMPT_PRESETS_KEY)
            if not isinstance(root_presets, dict):
                root_presets = {}
            root_presets["common"] = _normalize_prompt_presets(root_presets.get("common"))
            root_presets["database"] = _normalize_prompt_presets(root_presets.get("database"))
            opts[PROMPT_PRESETS_KEY] = root_presets
            return root_presets

        def _prompt_presets_for(kind):
            return list((_prompt_presets_root().get(kind) or []))

        def _save_prompt_presets_for(kind, presets):
            root_presets = _prompt_presets_root()
            root_presets[kind] = _normalize_prompt_presets(presets)
            self.app_options[PROMPT_PRESETS_KEY] = root_presets
            try:
                self.save_app_options_cache()
            except Exception:
                try:
                    from ysb.core.cache_utils import save_app_options
                    save_app_options(self.app_options)
                except Exception:
                    pass

        def _make_prompt_preset_box(parent, editor, kind, title_text):
            box = QFrame(parent)
            box.setObjectName("SettingsItem")
            lay = QHBoxLayout(box)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(8)
            lab = QLabel(self.tr_ui(title_text), box)
            lab.setObjectName("SettingsItemTitle")
            lay.addWidget(lab)
            combo = QComboBox(box)
            combo.setMinimumWidth(180)
            name_edit = QLineEdit(box)
            name_edit.setPlaceholderText(self.tr_ui("프리셋 이름"))
            btn_load = QPushButton(self.tr_ui("불러오기"), box)
            btn_save = QPushButton(self.tr_ui("현재 저장"), box)
            btn_delete = QPushButton(self.tr_ui("삭제"), box)
            lay.addWidget(combo, 1)
            lay.addWidget(name_edit, 1)
            lay.addWidget(btn_load)
            lay.addWidget(btn_save)
            lay.addWidget(btn_delete)

            def refresh(select_name=""):
                presets = _prompt_presets_for(kind)
                combo.blockSignals(True)
                try:
                    combo.clear()
                    combo.addItem(self.tr_ui("프리셋 선택"), "")
                    for preset in presets:
                        combo.addItem(str(preset.get("name") or ""), str(preset.get("name") or ""))
                    if select_name:
                        for idx in range(combo.count()):
                            if str(combo.itemData(idx) or "") == str(select_name):
                                combo.setCurrentIndex(idx)
                                break
                finally:
                    combo.blockSignals(False)
                if select_name:
                    name_edit.setText(str(select_name))

            def selected_preset():
                key = str(combo.currentData() or "").strip()
                if not key:
                    return None
                for preset in _prompt_presets_for(kind):
                    if str(preset.get("name") or "") == key:
                        return preset
                return None

            def on_combo_changed():
                preset = selected_preset()
                if preset:
                    name_edit.setText(str(preset.get("name") or ""))

            def load_preset():
                preset = selected_preset()
                if not preset:
                    return
                editor.setPlainText(str(preset.get("text") or ""))

            def save_preset():
                name = str(name_edit.text() or "").strip() or str(combo.currentData() or "").strip()
                if not name:
                    QMessageBox.information(dlg, self.tr_ui("프리셋 이름 필요"), self.tr_ui("저장할 프리셋 이름을 입력해 주세요."))
                    return
                text = editor.toPlainText()
                presets = _prompt_presets_for(kind)
                replaced = False
                for preset in presets:
                    if str(preset.get("name") or "") == name:
                        preset["text"] = text
                        replaced = True
                        break
                if not replaced:
                    presets.append({"name": name, "text": text})
                _save_prompt_presets_for(kind, presets)
                refresh(name)

            def delete_preset():
                key = str(combo.currentData() or "").strip()
                if not key:
                    return
                presets = [p for p in _prompt_presets_for(kind) if str(p.get("name") or "") != key]
                _save_prompt_presets_for(kind, presets)
                name_edit.clear()
                refresh("")

            combo.currentIndexChanged.connect(lambda *_: on_combo_changed())
            btn_load.clicked.connect(load_preset)
            btn_save.clicked.connect(save_preset)
            btn_delete.clicked.connect(delete_preset)
            refresh("")
            return box

        common_tab = QWidget(prompt_tabs)
        common_layout = QVBoxLayout(common_tab)
        common_layout.setContentsMargins(8, 8, 8, 8)
        common_layout.setSpacing(8)
        prompt_tabs.addTab(common_tab, self.tr_ui("공통 프롬프트"))

        character_tab = QWidget(prompt_tabs)
        character_layout = QVBoxLayout(character_tab)
        character_layout.setContentsMargins(8, 8, 8, 8)
        character_layout.setSpacing(8)
        prompt_tabs.addTab(character_tab, self.tr_ui("캐릭터 프롬프트"))

        system_tab = QWidget(prompt_tabs)
        system_layout = QVBoxLayout(system_tab)
        system_layout.setContentsMargins(8, 8, 8, 8)
        system_layout.setSpacing(8)
        prompt_tabs.addTab(system_tab, self.tr_ui("DB 전용 프롬프트"))

        default_box = QFrame(common_tab)
        default_box.setObjectName("SettingsItem")
        default_layout = QVBoxLayout(default_box)
        default_layout.setContentsMargins(12, 12, 12, 12)
        default_layout.setSpacing(6)
        default_title = QLabel(self.tr_ui("공통 번역 프롬프트"), default_box)
        default_title.setObjectName("SettingsItemTitle")
        default_layout.addWidget(default_title)
        default_desc = QLabel(self.tr_ui("API 번역이 기본적으로 참조하는 공통 지침입니다. 일반 맵 대사와 데이터베이스 번역 모두에 영향을 줍니다."), default_box)
        default_desc.setObjectName("SettingsDescription")
        default_desc.setWordWrap(True)
        default_layout.addWidget(default_desc)
        te_default = QPlainTextEdit(str((getattr(self, "app_options", {}) or {}).get(TRANSLATION_PROMPT_KEY) or prompts.get("default_prompt") or ""), default_box)
        te_default.setPlaceholderText(self.tr_ui("예: 일본어를 자연스러운 한국어로 번역하고, RPG Maker 제어문자와 치환 코드(%1, %2)는 절대 바꾸지 마세요."))
        te_default.setMinimumHeight(180)
        default_layout.addWidget(te_default)
        default_layout.addWidget(_make_prompt_preset_box(default_box, te_default, "common", "공통 프롬프트 프리셋"))
        common_layout.addWidget(default_box, 1)

        system_box = QFrame(system_tab)
        system_box.setObjectName("SettingsItem")
        system_box_layout = QVBoxLayout(system_box)
        system_box_layout.setContentsMargins(12, 12, 12, 12)
        system_box_layout.setSpacing(6)
        system_title = QLabel(self.tr_ui("데이터베이스 전용 번역 프롬프트"), system_box)
        system_title.setObjectName("SettingsItemTitle")
        system_box_layout.addWidget(system_title)
        system_desc = QLabel(self.tr_ui("System.json terms, States 메시지, 아이템/스킬 설명처럼 게임 UI와 전투 메시지를 번역할 때 붙는 전용 지침입니다. %1, %2 같은 치환 코드는 원문 그대로 API에 보내므로, 조사와 문장 길이 규칙을 여기 적어두면 안정적입니다. \\V[n] 같은 제어문자는 번역 요청에서 제외됩니다."), system_box)
        system_desc.setObjectName("SettingsDescription")
        system_desc.setWordWrap(True)
        system_box_layout.addWidget(system_desc)
        te_system = QPlainTextEdit(str(prompts.get("system_prompt") or ""), system_box)
        te_system.setPlaceholderText(self.tr_ui("예: DB 이름/설명/시스템 용어는 짧고 일관되게 번역합니다. %1, %2는 절대 변경하지 않고, 필요한 조사는 은(는)/이(가)/을(를) 형태로 붙입니다."))
        te_system.setMinimumHeight(220)
        system_box_layout.addWidget(te_system, 1)
        system_box_layout.addWidget(_make_prompt_preset_box(system_box, te_system, "database", "DB 전용 프롬프트 프리셋"))
        system_layout.addWidget(system_box, 1)

        prompt_test_tab = QWidget(prompt_tabs)
        prompt_test_layout = QVBoxLayout(prompt_test_tab)
        prompt_test_layout.setContentsMargins(8, 8, 8, 8)
        prompt_test_layout.setSpacing(8)
        prompt_tabs.addTab(prompt_test_tab, self.tr_ui("프롬프트 테스트"))

        prompt_test_desc = QLabel(self.tr_ui("화자와 문장을 직접 넣어 실제로 어떤 공통/캐릭터/DB/단어장 프롬프트가 적용되는지 역방향으로 확인합니다. API 호출 없이 조립 결과만 보여줍니다."), prompt_test_tab)
        prompt_test_desc.setObjectName("SettingsDescription")
        prompt_test_desc.setWordWrap(True)
        prompt_test_layout.addWidget(prompt_test_desc)

        prompt_test_form = QFrame(prompt_test_tab)
        prompt_test_form.setObjectName("SettingsItem")
        prompt_test_form_layout = QVBoxLayout(prompt_test_form)
        prompt_test_form_layout.setContentsMargins(12, 12, 12, 12)
        prompt_test_form_layout.setSpacing(8)
        prompt_test_layout.addWidget(prompt_test_form, 0)

        prompt_test_row1 = QHBoxLayout(); prompt_test_row1.setSpacing(8)
        prompt_test_row1.addWidget(QLabel(self.tr_ui("번역 종류"), prompt_test_form))
        cb_prompt_test_kind = QComboBox(prompt_test_form)
        cb_prompt_test_kind.addItem(self.tr_ui("일반 대사 번역"), "dialogue")
        cb_prompt_test_kind.addItem(self.tr_ui("데이터베이스 번역"), "database")
        prompt_test_row1.addWidget(cb_prompt_test_kind)
        prompt_test_row1.addWidget(QLabel(self.tr_ui("화자"), prompt_test_form))
        cb_prompt_test_speaker = QComboBox(prompt_test_form)
        cb_prompt_test_speaker.setEditable(True)
        try:
            cb_prompt_test_speaker.addItems(allowed_speaker_keys)
        except Exception:
            pass
        prompt_test_row1.addWidget(cb_prompt_test_speaker, 1)
        prompt_test_row1.addStretch(1)
        prompt_test_form_layout.addLayout(prompt_test_row1)

        prompt_test_row2 = QHBoxLayout(); prompt_test_row2.setSpacing(8)
        lab_prompt_test_map = QLabel(self.tr_ui("맵"), prompt_test_form)
        le_prompt_test_map = QLineEdit(prompt_test_form); le_prompt_test_map.setText("TEST")
        lab_prompt_test_event = QLabel(self.tr_ui("이벤트"), prompt_test_form)
        le_prompt_test_event = QLineEdit(prompt_test_form); le_prompt_test_event.setText("TEST")
        lab_prompt_test_db = QLabel(self.tr_ui("DB"), prompt_test_form)
        le_prompt_test_db = QLineEdit(prompt_test_form); le_prompt_test_db.setText("Items")
        lab_prompt_test_db_id = QLabel(self.tr_ui("DB ID"), prompt_test_form)
        le_prompt_test_db_id = QLineEdit(prompt_test_form); le_prompt_test_db_id.setText("1")
        lab_prompt_test_field = QLabel(self.tr_ui("필드"), prompt_test_form)
        le_prompt_test_field = QLineEdit(prompt_test_form); le_prompt_test_field.setText("name")
        for w in (lab_prompt_test_map, le_prompt_test_map, lab_prompt_test_event, le_prompt_test_event, lab_prompt_test_db, le_prompt_test_db, lab_prompt_test_db_id, le_prompt_test_db_id, lab_prompt_test_field, le_prompt_test_field):
            prompt_test_row2.addWidget(w)
        prompt_test_form_layout.addLayout(prompt_test_row2)

        prompt_test_text_label = QLabel(self.tr_ui("테스트 문장"), prompt_test_form)
        prompt_test_text_label.setObjectName("SettingsItemTitle")
        prompt_test_form_layout.addWidget(prompt_test_text_label)
        te_prompt_test_text = QPlainTextEdit(prompt_test_form)
        te_prompt_test_text.setPlaceholderText(self.tr_ui("예: リオラはポーションを手に入れた！"))
        te_prompt_test_text.setMinimumHeight(86)
        prompt_test_form_layout.addWidget(te_prompt_test_text)
        prompt_test_btn_row = QHBoxLayout(); prompt_test_btn_row.addStretch(1)
        btn_prompt_test_check = QPushButton(self.tr_ui("사용 프롬프트 확인"), prompt_test_form)
        prompt_test_btn_row.addWidget(btn_prompt_test_check)
        prompt_test_form_layout.addLayout(prompt_test_btn_row)

        prompt_test_result = QPlainTextEdit(prompt_test_tab)
        prompt_test_result.setReadOnly(True)
        prompt_test_result.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        prompt_test_layout.addWidget(prompt_test_result, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal, character_tab)
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)
        left_title = QLabel(self.tr_ui("화자 목록"), left)
        left_title.setToolTip(self.tr_ui("화자 번역과 동일한 기준으로 수집된 실제 화자만 표시합니다."))
        left_title.setObjectName("SettingsItemTitle")
        left_layout.addWidget(left_title)
        list_widget = QListWidget(left)
        left_layout.addWidget(list_widget, 1)
        left_btns = QHBoxLayout()
        btn_add = QPushButton(self.tr_ui("추가"), left)
        btn_remove = QPushButton(self.tr_ui("삭제"), left)
        btn_add.setToolTip(self.tr_ui("현재 프로젝트에서 실제 화자로 수집된 이름만 추가할 수 있습니다."))
        left_btns.addWidget(btn_add)
        left_btns.addWidget(btn_remove)
        left_layout.addLayout(left_btns)

        right_scroll = QScrollArea(splitter)
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right = QFrame(right_scroll)
        right.setObjectName("SettingsItem")
        right_scroll.setWidget(right)
        form = QVBoxLayout(right)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        current_key = {"value": None}

        cb_enabled = QCheckBox(self.tr_ui("이 캐릭터 프롬프트 사용"), right)
        form.addWidget(cb_enabled)
        le_display = QLineEdit(right)
        te_tone = QPlainTextEdit(right)
        te_personality = QPlainTextEdit(right)
        te_relationship = QPlainTextEdit(right)
        te_rules = QPlainTextEdit(right)
        te_forbidden = QPlainTextEdit(right)
        te_notes = QPlainTextEdit(right)
        for te in (te_tone, te_personality, te_relationship, te_rules, te_forbidden, te_notes):
            te.setMinimumHeight(76)
            te.setMaximumHeight(160)

        def add_field(label_text, editor, desc_text=""):
            lab = QLabel(self.tr_ui(label_text), right)
            lab.setObjectName("SettingsItemTitle")
            form.addWidget(lab)
            if desc_text:
                d = QLabel(self.tr_ui(desc_text), right)
                d.setObjectName("SettingsDescription")
                d.setWordWrap(True)
                form.addWidget(d)
            form.addWidget(editor)

        add_field("표시 이름", le_display, "프롬프트에 표시할 캐릭터 이름입니다. 비워두면 화자명을 그대로 사용합니다.")
        add_field("말투", te_tone, "반말/존댓말, 밝음/무뚝뚝함, 말끝 습관 같은 말투 지침입니다.")
        add_field("성격", te_personality, "캐릭터의 성격, 감정 표현 방식, 대사 리듬을 적습니다.")
        add_field("관계/상황", te_relationship, "주인공과의 관계나 번역에 영향을 주는 기본 문맥을 적습니다.")
        add_field("번역 규칙", te_rules, "이 캐릭터에게 적용할 번역 규칙입니다. 예: 짧게 말함, 이름은 원문 유지 등.")
        add_field("금지/주의 표현", te_forbidden, "피해야 할 단어, 어색한 말투, 쓰면 안 되는 표현을 적습니다.")
        add_field("메모", te_notes, "검수 메모나 나중에 참고할 내용을 적습니다.")
        form.addStretch(1)

        splitter.addWidget(left)
        splitter.addWidget(right_scroll)
        try:
            splitter.setSizes([250, 670])
        except Exception:
            pass
        character_layout.addWidget(splitter, 1)

        def sorted_keys():
            keys = [key for key in (prompts.get("characters") or {}).keys() if (not allowed_speaker_set) or key in allowed_speaker_set]
            return sorted(keys, key=lambda x: str(x).casefold())

        def save_current():
            key = current_key.get("value")
            if not key:
                return
            chars = prompts.setdefault("characters", {})
            chars[key] = normalize_maker_character_prompt_profile({
                "enabled": cb_enabled.isChecked(),
                "display_name": le_display.text().strip(),
                "tone": te_tone.toPlainText().strip(),
                "personality": te_personality.toPlainText().strip(),
                "relationship": te_relationship.toPlainText().strip(),
                "translation_rules": te_rules.toPlainText().strip(),
                "forbidden_words": te_forbidden.toPlainText().strip(),
                "notes": te_notes.toPlainText().strip(),
            }, speaker=key)

        def load_profile(key):
            current_key["value"] = key
            profile = normalize_maker_character_prompt_profile((prompts.get("characters") or {}).get(key) or {}, speaker=key)
            cb_enabled.setChecked(bool(profile.get("enabled", True)))
            le_display.setText(str(profile.get("display_name") or key))
            te_tone.setPlainText(str(profile.get("tone") or ""))
            te_personality.setPlainText(str(profile.get("personality") or ""))
            te_relationship.setPlainText(str(profile.get("relationship") or ""))
            te_rules.setPlainText(str(profile.get("translation_rules") or ""))
            te_forbidden.setPlainText(str(profile.get("forbidden_words") or ""))
            te_notes.setPlainText(str(profile.get("notes") or ""))

        def refresh_list(select_key=None):
            list_widget.blockSignals(True)
            try:
                list_widget.clear()
                for key in sorted_keys():
                    item = QListWidgetItem(str(key))
                    item.setData(Qt.ItemDataRole.UserRole, str(key))
                    profile = normalize_maker_character_prompt_profile((prompts.get("characters") or {}).get(key) or {}, speaker=key)
                    if not profile.get("enabled", True):
                        item.setText(f"{key}  ({self.tr_ui('사용 안 함')})")
                    list_widget.addItem(item)
                target = select_key or current_key.get("value") or (sorted_keys()[0] if sorted_keys() else None)
                if target:
                    for i in range(list_widget.count()):
                        it = list_widget.item(i)
                        if str(it.data(Qt.ItemDataRole.UserRole) or "") == str(target):
                            list_widget.setCurrentRow(i)
                            load_profile(str(target))
                            break
            finally:
                list_widget.blockSignals(False)

        def on_selection_changed():
            old = current_key.get("value")
            if old:
                save_current()
            item = list_widget.currentItem()
            key = str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""
            if key:
                load_profile(key)

        list_widget.currentItemChanged.connect(lambda _cur, _prev: on_selection_changed())

        def add_character():
            save_current()
            name, ok = QInputDialog.getText(dlg, self.tr_ui("화자 추가"), self.tr_ui("화자 이름:"))
            if not ok:
                return
            key = str(name or "").strip()
            if not key:
                return
            if allowed_speaker_set and key not in allowed_speaker_set:
                QMessageBox.information(
                    dlg,
                    self.tr_ui("추가 불가"),
                    self.tr_ui("캐릭터 프롬프트 목록에는 현재 프로젝트에서 실제 화자로 수집된 이름만 추가할 수 있습니다."),
                )
                return
            chars = prompts.setdefault("characters", {})
            if key not in chars:
                chars[key] = normalize_maker_character_prompt_profile({}, speaker=key)
            refresh_list(key)

        def remove_character():
            item = list_widget.currentItem()
            if item is None:
                return
            key = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if not key:
                return
            if not self.ask_yes_no_shortcut(
                "화자 프롬프트 삭제",
                f"'{key}' 캐릭터 프롬프트를 삭제할까요?\n현재 텍스트의 화자명은 지워지지 않고, 프롬프트 설정만 삭제됩니다.",
                yes_text="삭제",
                no_text="취소",
                default_yes=False,
                icon=QMessageBox.Icon.Warning,
                parent=dlg,
            ):
                return
            prompts.setdefault("characters", {}).pop(key, None)
            current_key["value"] = None
            refresh_list()

        btn_add.clicked.connect(add_character)
        btn_remove.clicked.connect(remove_character)
        refresh_list()

        def update_prompt_test_kind_fields():
            is_db = str(cb_prompt_test_kind.currentData() or "dialogue") == "database"
            for w in (lab_prompt_test_map, le_prompt_test_map, lab_prompt_test_event, le_prompt_test_event):
                try:
                    w.setVisible(not is_db)
                except Exception:
                    pass
            for w in (lab_prompt_test_db, le_prompt_test_db, lab_prompt_test_db_id, le_prompt_test_db_id, lab_prompt_test_field, le_prompt_test_field):
                try:
                    w.setVisible(is_db)
                except Exception:
                    pass

        def _current_prompt_test_prompts():
            save_current()
            import copy
            local_prompts = copy.deepcopy(prompts)
            local_prompts["default_prompt"] = te_default.toPlainText().strip()
            local_prompts["system_prompt"] = te_system.toPlainText().strip()
            return normalize_maker_character_prompts(local_prompts)

        def run_prompt_reverse_test():
            try:
                import json
                from ysb.engine.translation_engine import Config
                from ysb.tools.maker_project import prepare_maker_translation_payload
            except Exception as e:
                prompt_test_result.setPlainText(f"프롬프트 테스트 준비 실패: {type(e).__name__}: {e}")
                return
            local_prompts = _current_prompt_test_prompts()
            text = te_prompt_test_text.toPlainText().strip()
            if not text:
                prompt_test_result.setPlainText(self.tr_ui("테스트 문장을 입력해 주세요."))
                return
            speaker = str(cb_prompt_test_speaker.currentText() or "").strip() or "Unknown"
            kind = str(cb_prompt_test_kind.currentData() or "dialogue")
            if kind == "database":
                meta = {
                    "source_kind": "database",
                    "text_type": "database",
                    "db_kind": le_prompt_test_db.text().strip() or "Items",
                    "db_id": le_prompt_test_db_id.text().strip() or "1",
                    "db_field": le_prompt_test_field.text().strip() or "name",
                    "speaker_plain": speaker,
                    "speaker": speaker,
                    "map_name": "Database",
                    "event_name": str(le_prompt_test_db.text().strip() or "Items"),
                }
            else:
                meta = {
                    "source_kind": "map",
                    "text_type": "dialogue",
                    "speaker_plain": speaker,
                    "speaker": speaker,
                    "map_name": le_prompt_test_map.text().strip() or "TEST",
                    "event_name": le_prompt_test_event.text().strip() or "TEST",
                }
            item = {
                "text": text,
                "maker_speaker": speaker,
                "maker_speaker_plain": speaker,
                "maker_text_unit": meta,
            }
            payload = prepare_maker_translation_payload(item, local_prompts)
            engine = getattr(self, "engine", None)
            if engine is None:
                try:
                    self.restart_engine(show_error=False)
                    engine = getattr(self, "engine", None)
                except Exception:
                    engine = None
            if engine is None or not hasattr(engine, "preview_translation_request"):
                prompt_test_result.setPlainText(self.tr_ui("번역 엔진을 초기화하지 못했습니다."))
                return
            try:
                if hasattr(self, "sync_translation_option_cache_to_config"):
                    self.sync_translation_option_cache_to_config()
            except Exception:
                pass
            old_prompt = getattr(Config, "TRANSLATION_PROMPT", "")
            try:
                Config.TRANSLATION_PROMPT = str(local_prompts.get("default_prompt") or "")
                preview = engine.preview_translation_request([payload.get("text") or ""], contexts=[payload.get("context") or ""], base_id=0)
            except Exception as e:
                preview = {"error": f"{type(e).__name__}: {e}", "items": []}
            finally:
                try:
                    Config.TRANSLATION_PROMPT = old_prompt
                except Exception:
                    pass
            chunk_block = str(preview.get("character_prompt_block") or "").strip()
            matched_glossary = str(preview.get("matched_glossary_block") or "").strip()
            cleaned_contexts = preview.get("cleaned_contexts") or []
            cleaned_context = str(cleaned_contexts[0] if cleaned_contexts else "")
            has_character_prompt = "[Character:" in chunk_block
            has_db_prompt = "Database-only system prompt:" in chunk_block or "Database text is game UI/system text" in chunk_block
            lines = []
            lines.append("[프롬프트 역방향 테스트]")
            lines.append(f"번역 종류: {'데이터베이스 번역' if kind == 'database' else '일반 대사 번역'}")
            lines.append(f"화자: {speaker}")
            lines.append(f"API 입력 원문: {payload.get('text') or ''}")
            lines.append("")
            lines.append("[적용 판정]")
            if kind == "database":
                lines.append(f"DB 전용 프롬프트: {'포함' if has_db_prompt else '없음'}")
                lines.append("캐릭터 프롬프트: 데이터베이스 번역에는 적용하지 않음")
            else:
                lines.append("DB 전용 프롬프트: 일반 대사 번역에는 적용하지 않음")
                lines.append(f"캐릭터 프롬프트: {'포함' if has_character_prompt else '없음'}")
            lines.append(f"이번 문장 적용 단어장: {'있음' if matched_glossary else '없음'}")
            lines.append("")
            lines.append("[이번 문장 적용 단어장]")
            lines.append(matched_glossary or "(없음)")
            lines.append("")
            lines.append("[청크당 1회 적용 프롬프트 묶음]")
            lines.append(chunk_block or "(없음)")
            lines.append("")
            lines.append("[줄별 context]")
            lines.append(cleaned_context or "(없음)")
            lines.append("")
            lines.append("[실제 system prompt 미리보기]")
            lines.append(str(preview.get("system_prompt") or ""))
            lines.append("")
            lines.append("[실제 user payload 미리보기]")
            try:
                lines.append(json.dumps(preview.get("items") or [], ensure_ascii=False, indent=2))
            except Exception:
                lines.append(str(preview.get("items") or []))
            if preview.get("error"):
                lines.insert(0, "ERROR: " + str(preview.get("error")))
            prompt_test_result.setPlainText("\n".join(lines))

        try:
            cb_prompt_test_kind.currentIndexChanged.connect(lambda *_: update_prompt_test_kind_fields())
        except Exception:
            pass
        btn_prompt_test_check.clicked.connect(run_prompt_reverse_test)
        update_prompt_test_kind_fields()

        verify_row = QHBoxLayout()
        verify_row.addStretch(1)
        btn_verify_prompt = QPushButton(self.tr_ui("입력 프롬프트 확인 / 번역 테스트"), dlg)
        btn_verify_prompt.setToolTip(self.tr_ui("실제 API 요청에 들어가는 공용/캐릭터 프롬프트와 대표 대사 번역 결과를 확인합니다."))
        verify_row.addWidget(btn_verify_prompt)
        root.addLayout(verify_row)
        btn_verify_prompt.clicked.connect(lambda: (save_current(), self.open_maker_prompt_verification_dialog(project_dir, prompts)))

        save_applied = {"ok": False, "count": 0}

        def apply_changes():
            save_current()
            # NOTE: do not rebind the outer ``prompts`` name here.
            # Rebinding inside this nested function makes Python treat it as a
            # local variable, so the earlier ``prompts[...]`` reads crash with
            # UnboundLocalError when the OK button is pressed.  Build a fixed
            # copy instead, then save/apply that copy.
            prompts["default_prompt"] = te_default.toPlainText().strip()
            prompts["system_prompt"] = te_system.toPlainText().strip()
            try:
                self.app_options[TRANSLATION_PROMPT_KEY] = prompts["default_prompt"]
                self.save_app_options_cache()
                self.sync_translation_option_cache_to_config()
            except Exception:
                pass
            fixed_prompts = sync_maker_character_prompts_to_current_speakers(prompts, getattr(self, "data", {}) or {})
            fixed = save_maker_character_prompts(project_dir, fixed_prompts)
            changed = apply_maker_character_prompts_to_data(getattr(self, "data", {}) or {}, fixed)
            try:
                store = getattr(self, "project_store", None)
                if store is not None:
                    ui_state = getattr(store, "ui_state", {}) or {}
                    if not isinstance(ui_state, dict):
                        ui_state = {}
                    ui_state["maker_character_prompts"] = fixed
                    store.ui_state = ui_state
            except Exception:
                pass
            try:
                if hasattr(self, "mark_project_structure_dirty"):
                    self.mark_project_structure_dirty("maker_character_prompts")
            except Exception:
                pass
            try:
                self.save_project_store(getattr(self, "project_store", None))
            except Exception:
                try:
                    self.auto_save_project()
                except Exception:
                    pass
            try:
                self.fill_table()
            except Exception:
                pass
            save_applied["ok"] = True
            save_applied["count"] = int(changed)
            self.log(f"🎭 쯔꾸르 프롬프트 저장: 캐릭터 {len((fixed.get('characters') or {}))}명 / 텍스트 {changed}개 연결 / 시스템 프롬프트 {len(str(fixed.get('system_prompt') or '')):,}자")

        def on_ok():
            apply_changes()
            dlg.accept()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("닫기"))
        buttons.accepted.connect(on_ok)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted and save_applied.get("ok"):
            self.show_ok_notice("프롬프트 저장 완료", "쯔꾸르 프롬프트 설정이 저장되었습니다.")



    def open_maker_character_profiles_dialog(self):
        """현재 쯔꾸르 프로젝트의 등장인물/이미지 후보/대표 대사를 한곳에서 파악한다."""
        project_dir = getattr(self, "project_dir", None)
        if not project_dir:
            self.show_warn_notice("게임 캐릭터 프로필", "게임 캐릭터 프로필은 프로젝트를 연 뒤 사용할 수 있습니다.")
            return
        try:
            from ysb.tools.maker_project import (
                MAKER_CLONE_DIR,
                apply_maker_character_prompts_to_data,
                collect_maker_character_profiles,
                load_maker_character_prompts,
                normalize_maker_character_prompt_profile,
                save_maker_character_prompts,
            )
        except Exception as e:
            self.show_warn_notice("게임 캐릭터 프로필", f"게임 캐릭터 프로필 창을 열 수 없습니다.\n{e}")
            return

        try:
            payload = collect_maker_character_profiles(project_dir, getattr(self, "data", {}) or {})
        except Exception as e:
            self.show_warn_notice("게임 캐릭터 프로필", f"캐릭터 프로필을 분석하지 못했습니다.\n{e}")
            return
        characters = dict((payload or {}).get("characters") or {})
        if not characters:
            self.show_warn_notice("게임 캐릭터 프로필", "분석된 캐릭터가 없습니다. 먼저 게임 가져오기/텍스트 분석을 확인해 주세요.")
            return

        prompts = load_maker_character_prompts(project_dir)
        chars_prompt = prompts.setdefault("characters", {})
        for key in characters.keys():
            if key not in chars_prompt:
                chars_prompt[key] = normalize_maker_character_prompt_profile({}, speaker=key)

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr_ui("게임 캐릭터 프로필"))
        dlg.resize(1040, 720)
        dlg.setMinimumSize(820, 520)
        dlg.setSizeGripEnabled(True)
        try:
            dlg.setStyleSheet(self.settings_dialog_style())
        except Exception:
            pass

        root = QVBoxLayout(dlg)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        title = QLabel(self.tr_ui("게임 캐릭터 프로필"), dlg)
        title.setObjectName("SettingsDialogTitle")
        root.addWidget(title)
        desc = QLabel(self.tr_ui("현재 게임에서 발견한 캐릭터, 이미지 후보, 대표 대사, 등장 위치를 모아 보여줍니다. 자동 매칭은 근거와 신뢰도 기반 후보이며, 최종 말투/성격 프롬프트는 사용자가 확정합니다."), dlg)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        root.addWidget(desc)

        splitter = QSplitter(Qt.Orientation.Horizontal, dlg)
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)
        left_title = QLabel(self.tr_ui("캐릭터 목록"), left)
        left_title.setObjectName("SettingsItemTitle")
        left_layout.addWidget(left_title)
        list_widget = QListWidget(left)
        left_layout.addWidget(list_widget, 1)
        btn_rescan = QPushButton(self.tr_ui("프로필 재분석"), left)
        left_layout.addWidget(btn_rescan)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        header = QFrame(right)
        header.setObjectName("SettingsItem")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(12)
        image_label = QLabel(header)
        image_label.setFixedSize(180, 180)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setObjectName("SettingsPath")
        image_label.setText(self.tr_ui("이미지 없음"))
        header_layout.addWidget(image_label, 0)
        info_label = QLabel(header)
        info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_label.setWordWrap(True)
        info_label.setObjectName("SettingsDescription")
        header_layout.addWidget(info_label, 1)
        right_layout.addWidget(header)

        tabs = QTabWidget(right)
        right_layout.addWidget(tabs, 1)

        tab_profile = QWidget(tabs)
        profile_layout = QVBoxLayout(tab_profile)
        profile_layout.setContentsMargins(8, 8, 8, 8)
        profile_layout.setSpacing(8)
        image_table = QTableWidget(tab_profile)
        image_table.setColumnCount(5)
        image_table.setHorizontalHeaderLabels([self.tr_ui("종류"), self.tr_ui("파일"), self.tr_ui("신뢰도"), self.tr_ui("횟수"), self.tr_ui("근거")])
        image_table.horizontalHeader().setStretchLastSection(True)
        image_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        image_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        image_table.setIconSize(QSize(48, 48))
        profile_layout.addWidget(QLabel(self.tr_ui("이미지 후보"), tab_profile))
        profile_layout.addWidget(image_table, 1)
        appearance_table = QTableWidget(tab_profile)
        appearance_table.setColumnCount(4)
        appearance_table.setHorizontalHeaderLabels([self.tr_ui("맵/페이지"), self.tr_ui("이벤트"), self.tr_ui("파일"), self.tr_ui("횟수")])
        appearance_table.horizontalHeader().setStretchLastSection(True)
        appearance_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        profile_layout.addWidget(QLabel(self.tr_ui("등장 위치"), tab_profile))
        profile_layout.addWidget(appearance_table, 1)
        tabs.addTab(tab_profile, self.tr_ui("프로필"))

        tab_samples = QWidget(tabs)
        samples_layout = QVBoxLayout(tab_samples)
        samples_layout.setContentsMargins(8, 8, 8, 8)
        sample_text = QPlainTextEdit(tab_samples)
        sample_text.setReadOnly(True)
        samples_layout.addWidget(sample_text, 1)
        tabs.addTab(tab_samples, self.tr_ui("대표 대사"))

        tab_prompt = QWidget(tabs)
        tab_prompt_outer = QVBoxLayout(tab_prompt)
        tab_prompt_outer.setContentsMargins(0, 0, 0, 0)
        tab_prompt_scroll = QScrollArea(tab_prompt)
        tab_prompt_scroll.setWidgetResizable(True)
        tab_prompt_scroll.setFrameShape(QFrame.Shape.NoFrame)
        tab_prompt_body = QWidget(tab_prompt_scroll)
        tab_prompt_scroll.setWidget(tab_prompt_body)
        tab_prompt_outer.addWidget(tab_prompt_scroll, 1)
        prompt_layout = QVBoxLayout(tab_prompt_body)
        prompt_layout.setContentsMargins(8, 8, 8, 8)
        prompt_layout.setSpacing(8)
        cb_enabled = QCheckBox(self.tr_ui("이 캐릭터 프롬프트 사용"), tab_prompt_body)
        prompt_layout.addWidget(cb_enabled)
        le_display = QLineEdit(tab_prompt)
        te_tone = QPlainTextEdit(tab_prompt)
        te_personality = QPlainTextEdit(tab_prompt)
        te_relationship = QPlainTextEdit(tab_prompt)
        te_rules = QPlainTextEdit(tab_prompt)
        te_forbidden = QPlainTextEdit(tab_prompt)
        te_notes = QPlainTextEdit(tab_prompt)
        for te in (te_tone, te_personality, te_relationship, te_rules, te_forbidden, te_notes):
            te.setMinimumHeight(70)
            te.setMaximumHeight(150)
        def add_prompt_field(label, editor, desc_text=""):
            lab = QLabel(self.tr_ui(label), tab_prompt)
            lab.setObjectName("SettingsItemTitle")
            prompt_layout.addWidget(lab)
            if desc_text:
                d = QLabel(self.tr_ui(desc_text), tab_prompt)
                d.setObjectName("SettingsDescription")
                d.setWordWrap(True)
                prompt_layout.addWidget(d)
            prompt_layout.addWidget(editor)
        add_prompt_field("표시 이름", le_display)
        add_prompt_field("말투", te_tone)
        add_prompt_field("성격", te_personality)
        add_prompt_field("관계/상황", te_relationship)
        add_prompt_field("번역 규칙", te_rules)
        add_prompt_field("금지/주의 표현", te_forbidden)
        add_prompt_field("메모", te_notes)
        prompt_layout.addStretch(1)
        tabs.addTab(tab_prompt, self.tr_ui("번역 프롬프트"))

        splitter.addWidget(left)
        splitter.addWidget(right)
        try:
            splitter.setSizes([260, 860])
        except Exception:
            pass
        root.addWidget(splitter, 1)

        current_key = {"value": None}
        project_root = Path(project_dir)
        game_root = project_root / MAKER_CLONE_DIR

        def candidate_pixmap(candidate):
            try:
                rel = str((candidate or {}).get("rel_path") or "").strip().replace("\\", "/")
                if not rel:
                    return QPixmap()
                resolved = None
                diag = {}
                try:
                    # Use the same RPG Maker image resolver as the map preview.
                    # This supports deployed/encrypted assets such as *.png_ and *.rpgmvp
                    # by decrypting them into maker_meta/asset_cache for display only.
                    resolved, diag = self._maker_preview_resolve_asset_path(rel, subdirs=("",))
                except Exception:
                    resolved = None
                if resolved is None:
                    path = game_root / rel
                else:
                    path = Path(resolved)
                pix = QPixmap(str(path))
                if pix.isNull():
                    return pix
                crop_type = str((candidate or {}).get("crop_type") or "full")
                idx = int((candidate or {}).get("index") or 0)
                if crop_type == "face":
                    cols, rows = 4, 2
                    cw = max(1, pix.width() // cols)
                    ch = max(1, pix.height() // rows)
                    x = (idx % cols) * cw
                    y = (idx // cols) * ch
                    pix = pix.copy(x, y, cw, ch)
                elif crop_type == "character":
                    # RPG Maker character sheets are usually 4x2 character blocks,
                    # except files starting with '$', which contain one character.
                    name = Path(rel).name
                    if not name.startswith("$"):
                        cols, rows = 4, 2
                        cw = max(1, pix.width() // cols)
                        ch = max(1, pix.height() // rows)
                        x = (idx % cols) * cw
                        y = (idx // cols) * ch
                        pix = pix.copy(x, y, cw, ch)
                return pix
            except Exception:
                return QPixmap()

        def show_candidate(candidate):
            pix = candidate_pixmap(candidate or {})
            if pix.isNull():
                image_label.setPixmap(QPixmap())
                image_label.setText(self.tr_ui("이미지 없음"))
                return
            scaled = pix.scaled(image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image_label.setText("")
            image_label.setPixmap(scaled)

        def save_current_prompt():
            key = current_key.get("value")
            if not key:
                return
            chars_prompt[key] = normalize_maker_character_prompt_profile({
                "enabled": cb_enabled.isChecked(),
                "display_name": le_display.text().strip(),
                "tone": te_tone.toPlainText().strip(),
                "personality": te_personality.toPlainText().strip(),
                "relationship": te_relationship.toPlainText().strip(),
                "translation_rules": te_rules.toPlainText().strip(),
                "forbidden_words": te_forbidden.toPlainText().strip(),
                "notes": te_notes.toPlainText().strip(),
            }, speaker=key)

        def load_prompt_for(key):
            profile = normalize_maker_character_prompt_profile(chars_prompt.get(key) or {}, speaker=key)
            cb_enabled.setChecked(bool(profile.get("enabled", True)))
            le_display.setText(str(profile.get("display_name") or key))
            te_tone.setPlainText(str(profile.get("tone") or ""))
            te_personality.setPlainText(str(profile.get("personality") or ""))
            te_relationship.setPlainText(str(profile.get("relationship") or ""))
            te_rules.setPlainText(str(profile.get("translation_rules") or ""))
            te_forbidden.setPlainText(str(profile.get("forbidden_words") or ""))
            te_notes.setPlainText(str(profile.get("notes") or ""))

        def fill_image_table(profile):
            image_table.setRowCount(0)
            imgs = list((profile or {}).get("images") or [])
            for r, cand in enumerate(imgs):
                image_table.insertRow(r)
                vals = [
                    str(cand.get("label") or cand.get("kind") or ""),
                    str(cand.get("rel_path") or ""),
                    f"{float(cand.get('confidence') or 0.0) * 100:.0f}%",
                    str(cand.get("count") or 0),
                    " / ".join(str(x) for x in (cand.get("evidences") or [])[:2]),
                ]
                for c, val in enumerate(vals):
                    it = QTableWidgetItem(val)
                    if c == 0:
                        it.setData(Qt.ItemDataRole.UserRole, cand)
                        try:
                            pix = candidate_pixmap(cand)
                            if not pix.isNull():
                                it.setIcon(QIcon(pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
                                image_table.setRowHeight(r, 56)
                        except Exception:
                            pass
                    image_table.setItem(r, c, it)
            image_table.resizeColumnsToContents()
            if imgs:
                image_table.selectRow(0)
                show_candidate(imgs[0])
            else:
                show_candidate({})

        def fill_appearance_table(profile):
            appearance_table.setRowCount(0)
            apps = list((profile or {}).get("appearances") or [])[:30]
            for r, app in enumerate(apps):
                appearance_table.insertRow(r)
                vals = [str(app.get("map_name") or ""), str(app.get("event_name") or ""), str(app.get("source_file") or ""), str(app.get("count") or 0)]
                for c, val in enumerate(vals):
                    appearance_table.setItem(r, c, QTableWidgetItem(val))
            appearance_table.resizeColumnsToContents()

        def load_character(key):
            current_key["value"] = key
            profile = characters.get(key) or {}
            actor = profile.get("actor") or {}
            hints = ", ".join(str(x) for x in (profile.get("source_hints") or [])[:8])
            image_total = sum(int(x.get("count") or 0) for x in (profile.get("images") or []) if isinstance(x, dict))
            appearance_total = sum(int(x.get("count") or 0) for x in (profile.get("appearances") or []) if isinstance(x, dict))
            display_count = int(profile.get("text_count") or 0)
            info = [
                f"<b>{key}</b>",
                f"대사 출현 횟수: {display_count} / 이미지 후보: {len(profile.get('images') or [])} / 신뢰도: {float(profile.get('confidence') or 0.0) * 100:.0f}%",
                f"추론 근거: {hints or '-'}",
            ]
            if actor:
                info.append(f"Actor ID: {actor.get('id') or '-'} / 별칭: {actor.get('nickname') or '-'}")
                if actor.get("profile"):
                    info.append(f"기본 프로필: {actor.get('profile')}")
            info_label.setText("<br>".join(info))
            fill_image_table(profile)
            fill_appearance_table(profile)
            lines = []
            for i, sample in enumerate((profile.get("samples") or [])[:30], 1):
                head = " / ".join(x for x in [str(sample.get("map_name") or ""), str(sample.get("event_name") or ""), str(sample.get("text_type") or "")] if x)
                src_line = str(sample.get('text') or '').strip()
                tr_line = str(sample.get('translated_text') or '').strip()
                if tr_line:
                    lines.append(f"[{i}] {head}\n원문: {src_line}\n번역: {tr_line}")
                else:
                    lines.append(f"[{i}] {head}\n원문: {src_line}")
            sample_text.setPlainText("\n\n".join(lines))
            load_prompt_for(key)

        def refresh_list(select_key=None):
            list_widget.blockSignals(True)
            try:
                list_widget.clear()
                keys = sorted(characters.keys(), key=lambda x: x.casefold())
                for key in keys:
                    profile = characters.get(key) or {}
                    image_total = sum(int(x.get("count") or 0) for x in (profile.get("images") or []) if isinstance(x, dict))
                    appearance_total = sum(int(x.get("count") or 0) for x in (profile.get("appearances") or []) if isinstance(x, dict))
                    display_count = int(profile.get("text_count") or 0)
                    it = QListWidgetItem(f"{key}  ({display_count})")
                    it.setData(Qt.ItemDataRole.UserRole, key)
                    it.setToolTip(self.tr_ui("괄호 안 숫자는 실제 Show Text 대사에서 화자로 잡힌 출현 횟수입니다."))
                    list_widget.addItem(it)
                target = select_key or current_key.get("value") or (keys[0] if keys else None)
                if target:
                    for i in range(list_widget.count()):
                        it = list_widget.item(i)
                        if str(it.data(Qt.ItemDataRole.UserRole) or "") == str(target):
                            list_widget.setCurrentRow(i)
                            load_character(str(target))
                            break
            finally:
                list_widget.blockSignals(False)

        def on_select():
            old = current_key.get("value")
            if old:
                save_current_prompt()
            it = list_widget.currentItem()
            key = str(it.data(Qt.ItemDataRole.UserRole) or "") if it is not None else ""
            if key:
                load_character(key)

        def on_image_select():
            row = image_table.currentRow()
            it = image_table.item(row, 0) if row >= 0 else None
            cand = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
            if isinstance(cand, dict):
                show_candidate(cand)

        list_widget.currentItemChanged.connect(lambda _cur, _prev: on_select())
        image_table.itemSelectionChanged.connect(on_image_select)

        def rescan_profiles():
            nonlocal payload, characters
            save_current_prompt()
            try:
                payload = collect_maker_character_profiles(project_dir, getattr(self, "data", {}) or {})
                characters = dict((payload or {}).get("characters") or {})
                for key in characters.keys():
                    if key not in chars_prompt:
                        chars_prompt[key] = normalize_maker_character_prompt_profile({}, speaker=key)
                refresh_list(current_key.get("value"))
                self.log(f"👤 게임 캐릭터 프로필 재분석: {len(characters)}명")
            except Exception as e:
                self.show_warn_notice("캐릭터 프로필 재분석 실패", str(e))

        btn_rescan.clicked.connect(rescan_profiles)
        refresh_list()

        saved = {"ok": False}
        def apply_changes():
            save_current_prompt()
            prompts["characters"] = chars_prompt
            fixed = save_maker_character_prompts(project_dir, prompts)
            changed = apply_maker_character_prompts_to_data(getattr(self, "data", {}) or {}, fixed)
            try:
                self.save_project_store(getattr(self, "project_store", None))
            except Exception:
                try:
                    self.auto_save_project()
                except Exception:
                    pass
            try:
                self.fill_table()
            except Exception:
                pass
            saved["ok"] = True
            self.log(f"👤 게임 캐릭터 프로필 저장: 캐릭터 {len(chars_prompt)}명 / 텍스트 {changed}개 연결")

        def on_ok():
            apply_changes()
            dlg.accept()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("닫기"))
        buttons.accepted.connect(on_ok)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted and saved.get("ok"):
            self.show_ok_notice("캐릭터 프로필 저장 완료", "게임 캐릭터 프로필/프롬프트 설정이 저장되었습니다.")


    def open_launcher_options_menu(self):
        menu = QMenu(self)
        menu.addAction(self.actions["option_api_settings"])
        menu.addSeparator()
        menu.addAction(self.actions["option_shortcut_settings"])
        menu.addAction(self.actions["option_macro_settings"])
        menu.addSeparator()
        if "project_maker_character_profiles" in self.actions:
            menu.addAction(self.actions["project_maker_character_profiles"])
        if "option_maker_character_prompts" in self.actions:
            menu.addAction(self.actions["option_maker_character_prompts"])
        menu.addAction(self.actions["option_glossary"])
        menu.addSeparator()
        if "option_maker_translation_settings" in self.actions:
            menu.addAction(self.actions["option_maker_translation_settings"])
        if "option_maker_preview_display_settings" in self.actions:
            menu.addAction(self.actions["option_maker_preview_display_settings"])
        menu.exec(QCursor.pos())

    def open_launcher_help(self):
        QMessageBox.information(
            self,
            self.tr_ui("도움말 / 매뉴얼"),
            self.tr_ui("런처 화면에서는 새 프로젝트, 프로젝트 열기, 마지막 작업 복구, 최근 프로젝트 열기를 바로 사용할 수 있습니다."),
        )

    def open_about_dialog(self):
        """도움말 > 프로그램 정보."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr_ui("프로그램 정보"))
        dialog.resize(500, 280)

        layout = QVBoxLayout(dialog)

        title = QLabel(self.tr_ui("YSB Game Editor / 쯔꾸르붕이"))
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)

        try:
            version = str(APP_VERSION)
        except Exception:
            version = "unknown"

        info = QLabel(
            self.tr_ui("버전") + f" {version}\n"
            "© 2026 amule949\n"
            "Support Email: ysbtool.support@gmail.com\n\n"
            "GNU General Public License v3.0\n"
            + self.tr_ui("자세한 내용은 LICENSE 및 TRADEMARKS.md를 참고하세요.")
        )
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        try:
            dialog.setStyleSheet(self.settings_dialog_style())
        except Exception:
            try:
                dialog.setStyleSheet(self.message_box_style())
            except Exception:
                pass

        dialog.exec()

    def setup_project_exit_button(self, menubar):
        """작업 화면 우측 상단에 프로젝트를 닫고 홈으로 나가는 버튼을 둔다."""
        try:
            btn = QToolButton(self)
            self.btn_project_exit = btn
            btn.setText(self.tr_ui("프로젝트 나가기"))
            btn.setToolTip(self.tr_ui("프로젝트 나가기"))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setAutoRaise(False)
            btn.setFixedHeight(26)
            btn.setMinimumWidth(118)
            btn.clicked.connect(lambda: self.actions["project_exit"].trigger() if hasattr(self, "actions") and "project_exit" in self.actions else self.show_launcher())
            self.apply_project_exit_button_theme()
            menubar.setCornerWidget(btn, Qt.Corner.TopRightCorner)
            self.update_project_exit_button_visibility()
        except Exception:
            pass

    def apply_project_exit_button_theme(self):
        """프로젝트 나가기 버튼도 현재 테마 팔레트를 따라가게 한다."""
        try:
            btn = getattr(self, "btn_project_exit", None)
            if btn is None:
                return
            if self.is_light_theme():
                btn.setStyleSheet(
                    "QToolButton { "
                    "background:#FAF5F7; color:#242329; border:1px solid #D1C9CE; "
                    "border-radius:0px; padding:3px 10px; font-weight:700; "
                    "}"
                    "QToolButton:hover { background:#FBF5F6; border-color:#D7A3A9; color:#111827; }"
                    "QToolButton:pressed { background:#F5E8EA; border-color:#C78A90; }"
                    "QToolButton:disabled { background:#EEEFF3; color:#A29A9F; border-color:#DED8DC; }"
                )
            else:
                btn.setStyleSheet(
                    "QToolButton { "
                    "background:#28262B; color:#E0DADF; border:1px solid #3A363B; "
                    "border-radius:0px; padding:3px 10px; font-weight:700; "
                    "}"
                    "QToolButton:hover { background:#332B30; border-color:#665A62; color:#ffffff; }"
                    "QToolButton:pressed { background:#5B3136; border-color:#A85D66; }"
                    "QToolButton:disabled { background:#171719; color:#746B72; border-color:#2E2A30; }"
                )
            btn.update()
        except Exception:
            pass

    def update_project_exit_button_visibility(self):
        try:
            btn = getattr(self, "btn_project_exit", None)
            if btn is None:
                return
            in_editor = False
            try:
                in_editor = bool(
                    hasattr(self, "main_stack")
                    and hasattr(self, "editor_widget")
                    and self.main_stack.currentWidget() is self.editor_widget
                )
            except Exception:
                in_editor = False
            btn.setVisible(bool(in_editor and self.has_open_project()))
            btn.setEnabled(bool(in_editor and self.has_open_project()))
        except Exception:
            pass

    def install_menu_timing_logs(self):
        """상단 메뉴 지연 원인 분석용 timing 로그를 연결한다."""
        try:
            menubar = self.menuBar()
        except Exception:
            menubar = None
        try:
            if menubar is not None:
                menubar.setObjectName("MainMenuBar")
        except Exception:
            pass

        menu_specs = [
            ("project_menu", "project", "프로젝트"),
            ("work_menu", "work", "작업"),
            ("batch_menu", "batch", "일괄 작업"),
            ("db_menu", "db", "DB번역"),
            ("auto_menu", "auto", "자동화 작업"),
            ("option_menu", "option", "옵션"),
            ("settings_menu", "settings", "설정"),
            ("help_menu", "help", "도움말"),
        ]

        for attr, key, title in menu_specs:
            menu = getattr(self, attr, None)
            if menu is None:
                continue
            try:
                menu.setObjectName(f"TopMenu_{key}")
            except Exception:
                pass
            try:
                if bool(menu.property("menu_timing_log_connected")):
                    continue
            except Exception:
                pass
            try:
                menu.setProperty("menu_timing_log_connected", True)
            except Exception:
                pass

            def _on_about_to_show(_menu=menu, _key=key, _title=title):
                t0 = time.time()
                try:
                    press_t = float(getattr(self, "_last_menu_bar_press_time", 0.0) or 0.0)
                    since_press = int((t0 - press_t) * 1000) if press_t else None
                except Exception:
                    since_press = None
                try:
                    self.audit_boundary_event(
                        "MENU_ABOUT_TO_SHOW_ENTER",
                        menu_key=_key,
                        title=_menu.title(),
                        fallback_title=self.tr_ui(_title),
                        action_count=len(_menu.actions()),
                        since_press_ms=since_press,
                        memory=memory_text(),
                    )
                except Exception:
                    pass

                def _done():
                    try:
                        self.audit_boundary_event(
                            "MENU_ABOUT_TO_SHOW_DONE",
                            menu_key=_key,
                            title=_menu.title(),
                            elapsed_ms=int((time.time() - t0) * 1000),
                            action_count=len(_menu.actions()),
                            memory=memory_text(),
                        )
                    except Exception:
                        pass

                try:
                    QTimer.singleShot(0, _done)
                except Exception:
                    _done()

            try:
                menu.aboutToShow.connect(_on_about_to_show)
            except Exception as e:
                try:
                    self.audit_boundary_event("MENU_LOG_CONNECT_ERROR", menu_key=key, error=str(e))
                except Exception:
                    pass

    def setup_menu(self):
        menubar = self.menuBar()

        project_menu = menubar.addMenu(self.tr_ui("프로젝트")); self.project_menu = project_menu
        try:
            project_menu.aboutToShow.connect(lambda: self.sync_maker_project_action_states())
        except Exception:
            pass
        # 1. 새로 만들기 및 열기
        project_menu.addAction(self.actions["project_new"])
        project_menu.addAction(self.actions["project_import_maker_game"])
        project_menu.addAction(self.actions["project_open"])
        project_menu.addAction(self.actions["project_open_json"])
        project_menu.addSeparator()
        # 2. 내보내기
        project_menu.addAction(self.actions["project_save"])
        project_menu.addSeparator()
        # 3. 복구하기
        project_menu.addAction(self.actions["project_recover_last_work"])
        project_menu.addSeparator()
        # 4. 기타 옵션
        project_menu.addAction(self.actions["project_show_launcher"])
        project_menu.addAction(self.actions["project_exit"])
        project_menu.addAction(self.actions["option_settings_overview"])

        work_menu = menubar.addMenu(self.tr_ui("작업")); self.work_menu = work_menu
        work_menu.addSection(self.tr_ui("기본동작"))
        work_menu.addAction(self.actions["work_source_compare"])
        work_menu.addAction(self.actions["work_open_current_project_folder"])
        work_menu.addAction(self.actions["work_export"])
        work_menu.addSeparator()

        work_menu.addSection(self.tr_ui("페이지탭"))
        work_menu.addAction(self.actions["work_page_rename_source"])
        work_menu.addAction(self.actions["work_page_delete_current"])
        work_menu.addSeparator()

        work_menu.addSection(self.tr_ui("작업류"))
        work_menu.addAction(self.actions["work_scan_maker_game"])
        work_menu.addAction(self.actions["paint_reanalyze"])
        work_menu.addAction(self.actions["work_translate"])
        if "work_restore_edge_control_codes_current" in self.actions:
            work_menu.addAction(self.actions["work_restore_edge_control_codes_current"])
        work_menu.addAction(self.actions["work_inpaint"])
        work_menu.addSeparator()

        work_menu.addSection(self.tr_ui("텍스트 수정류"))
        work_menu.addAction(self.actions["work_extract_text"])
        work_menu.addAction(self.actions["work_import_translation"])
        work_menu.addAction(self.actions["work_clear_translation"])
        work_menu.addAction(self.actions["work_clean_text"])
        if "work_text_find" in self.actions:
            work_menu.addAction(self.actions["work_text_find"])
        if "work_text_replace" in self.actions:
            work_menu.addAction(self.actions["work_text_replace"])
        work_menu.addSeparator()

        work_menu.addSection(self.tr_ui("이미지 교체류"))
        if "work_import_clean_background" in self.actions:
            work_menu.addAction(self.actions["work_import_clean_background"])
        if "final_paint_to_background" in self.actions:
            work_menu.addAction(self.actions["final_paint_to_background"])
        work_menu.addAction(self.actions["work_restore_original_source"])
        work_menu.addSeparator()

        work_menu.addSection(self.tr_ui("기타 동작"))
        work_menu.addAction(self.actions["work_quick_ocr"])
        work_menu.addAction(self.actions["work_text_number_width"])
        work_menu.addAction(self.actions["work_reset_text_rects"])
        work_menu.addSeparator()
        work_menu.addAction(self.actions["work_output_preview"])

        batch_menu = menubar.addMenu(self.tr_ui("일괄 작업")); self.batch_menu = batch_menu
        batch_menu.addSection(self.tr_ui("기본 동작"))
        batch_menu.addAction(self.actions["batch_export"])
        batch_menu.addSeparator()

        batch_menu.addSection(self.tr_ui("일괄 작업류"))
        batch_menu.addAction(self.actions["batch_analyze"])
        batch_menu.addAction(self.actions["batch_reanalyze"])
        batch_menu.addAction(self.actions["batch_translate"])
        if "work_unify_translations" in self.actions:
            batch_menu.addAction(self.actions["work_unify_translations"])
        if "batch_restore_edge_control_codes" in self.actions:
            batch_menu.addAction(self.actions["batch_restore_edge_control_codes"])
        batch_menu.addAction(self.actions["batch_inpaint"])
        batch_menu.addSeparator()

        batch_menu.addSection(self.tr_ui("텍스트 수정류"))
        batch_menu.addAction(self.actions["batch_extract_text"])
        batch_menu.addAction(self.actions["batch_clear_translation"])
        batch_menu.addAction(self.actions["batch_clean_text"])
        batch_menu.addSeparator()

        batch_menu.addSection(self.tr_ui("기타 동작"))
        batch_menu.addAction(self.actions["batch_reset_text_rects"])
        if "work_page_delete_all" in self.actions:
            batch_menu.addAction(self.actions["work_page_delete_all"])

        db_menu = menubar.addMenu(self.tr_ui("DB번역")); self.db_menu = db_menu
        if "option_maker_database_translation" in self.actions:
            db_menu.addAction(self.actions["option_maker_database_translation"])
        if "db_maker_character_name_translation" in self.actions:
            db_menu.addAction(self.actions["db_maker_character_name_translation"])

        auto_menu = menubar.addMenu(self.tr_ui("자동화 작업")); self.auto_menu = auto_menu
        auto_menu.addAction(self.actions["auto_text_size_current"])
        auto_menu.addAction(self.actions["auto_text_size_batch"])
        auto_menu.addSeparator()
        auto_menu.addAction(self.actions["auto_linebreak_current"])
        auto_menu.addAction(self.actions["auto_linebreak_batch"])


        option_menu = menubar.addMenu(self.tr_ui("옵션")); self.option_menu = option_menu
        option_menu.addAction(self.actions["option_api_settings"])
        option_menu.addSeparator()
        option_menu.addAction(self.actions["option_shortcut_settings"])
        option_menu.addAction(self.actions["option_macro_settings"])
        option_menu.addSeparator()
        if "project_maker_character_profiles" in self.actions:
            option_menu.addAction(self.actions["project_maker_character_profiles"])
        if "option_maker_character_prompts" in self.actions:
            option_menu.addAction(self.actions["option_maker_character_prompts"])
        option_menu.addAction(self.actions["option_glossary"])
        option_menu.addSeparator()
        if "option_maker_translation_settings" in self.actions:
            option_menu.addAction(self.actions["option_maker_translation_settings"])
        if "option_maker_preview_display_settings" in self.actions:
            option_menu.addAction(self.actions["option_maker_preview_display_settings"])
        if "option_maker_game_settings" in self.actions:
            option_menu.addAction(self.actions["option_maker_game_settings"])
        if "option_maker_game_refresh" in self.actions:
            option_menu.addAction(self.actions["option_maker_game_refresh"])
        settings_menu = menubar.addMenu(self.tr_ui("설정")); self.settings_menu = settings_menu
        if "setting_interface_tooltips" in self.actions:
            settings_menu.addAction(self.actions["setting_interface_tooltips"])
        settings_menu.addSeparator()
        settings_menu.addAction(self.actions["option_theme_settings"])
        settings_menu.addAction(self.actions["option_language_settings"])
        settings_menu.addAction(self.actions["setting_page_tab_display_name"])
        settings_menu.addAction(self.actions["setting_output_display_name"])
        settings_menu.addSeparator()
        settings_menu.addAction(self.actions["option_workspace_location"])
        settings_menu.addAction(self.actions["option_cleanup_temp_files"])
        settings_menu.addAction(self.actions["option_register_ysb"])
        settings_menu.addAction(self.actions["option_unregister_ysbt"])
        settings_menu.addSeparator()
        settings_menu.addAction(self.actions["setting_file_path_visibility"])
        settings_menu.addAction(self.actions["option_workspace_size_manager"])
        settings_menu.addAction(self.actions["setting_output_options"])

        help_menu = menubar.addMenu(self.tr_ui("도움말")); self.help_menu = help_menu
        help_menu.addAction(self.actions["help_program_manual"])
        help_menu.addAction(self.actions["help_open_website"])
        help_menu.addAction(self.actions["help_report_bug"])
        help_menu.addSeparator()
        help_menu.addAction(self.actions["help_about"])

        try:
            self.sync_interface_tooltips_action_state()
        except Exception:
            pass

        self.apply_maker_legacy_menu_cleanup()
        self.apply_maker_menu_cleanup()
        self.setup_project_exit_button(menubar)
        try:
            self.install_menu_timing_logs()
        except Exception as e:
            try:
                self.audit_boundary_event("MENU_LOG_SETUP_ERROR", error=str(e))
            except Exception:
                pass

    def setup_ui(self):
        # 쯔꾸르붕이 1단계 정리: 아직 기능 파일은 삭제하지 않고,
        # 역식붕이 이미지 편집용 UI만 먼저 숨겨 실행 안정성을 확인한다.
        self.tktool_phase1_enabled = True
        self.tktool_phase2_enabled = True
        self.maker_control_code_display_mode = str(getattr(self, "maker_control_code_display_mode", "hidden") or "hidden")

        self.main_stack = QStackedWidget()
        self.setCentralWidget(self.main_stack)

        self.recent_project_store = RecentProjectStore()
        self.launcher_widget = LauncherWidget(
            self.recent_project_store,
            app_version=APP_VERSION,
            lang=getattr(self, "ui_language", LANG_KO),
            theme=getattr(self, "ui_theme", THEME_DARK),
            parent=self,
        )
        self.launcher_widget.newProjectRequested.connect(self.new_empty_project_action)
        self.launcher_widget.openProjectRequested.connect(self.open_project)
        self.launcher_widget.importImagesRequested.connect(self.import_maker_game_action)
        self.launcher_widget.recoverRequested.connect(self.recover_last_work_project)
        self.launcher_widget.optionsRequested.connect(self.open_settings_overview_dialog)
        self.launcher_widget.helpRequested.connect(self.open_launcher_help)
        self.launcher_widget.droppedProjectOpenRequested.connect(lambda path: self.open_project_path(path, external_request=True))
        self.launcher_widget.recentProjectOpenRequested.connect(self.confirm_open_recent_project)
        self.launcher_widget.recentProjectRemoveRequested.connect(self.remove_recent_project_from_launcher)
        self.launcher_widget.recentProjectRevealRequested.connect(self.reveal_recent_project_in_folder)
        self.main_stack.addWidget(self.launcher_widget)

        w = QWidget()
        w.setObjectName("EditorRoot")
        self.editor_widget = w
        self.main_stack.addWidget(w)
        self.main_stack.setCurrentWidget(self.launcher_widget)
        lay = QHBoxLayout(w)
        # 기본 우측 텍스트/번역 영역은 전체 작업창의 절반을 차지하게 한다.
        split = EditorSplitter(Qt.Orientation.Horizontal, default_right_width=0)
        self.editor_splitter = split
        split.setHandleWidth(8)
        lay.addWidget(split)

        # Left Panel
        lp = QWidget()
        lp.setObjectName("LeftPanel")
        lp.setMinimumWidth(0)
        lp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        ll = QHBoxLayout(lp)
        ll.setContentsMargins(0, 0, 0, 0)

        self.view = MuleImageViewer(self)
        self.view.setObjectName("MainCanvasView")
        try:
            self.view.brush_size = max(1, min(500, int(self.app_options.get("brush_size", getattr(self.view, "brush_size", 25)) or 25)))
        except Exception:
            self.view.brush_size = 25
        self.view.scene.selectionChanged.connect(self.on_scene_selection_changed)
        try:
            self.view.installEventFilter(self)
            self.view.viewport().installEventFilter(self)
            self.view.viewport().setMouseTracking(True)
        except Exception:
            pass

        tb = QToolBar(orientation=Qt.Orientation.Vertical)
        tb.setStyleSheet(
            "QToolBar { background:#171719; border:1px solid #2E2A30; border-radius:0px; padding:4px; }"
            "QToolButton:checked { background:#8A4A52; border:1px solid #A85D66; color:#ffffff; font-weight:700; }"
        )
        self.act_brush = QAction("🖌️", self, triggered=lambda *args: self.set_tool('draw'))
        self.act_brush.setCheckable(True)
        tb.addAction(self.act_brush)
        self.act_erase = QAction("🧼", self, triggered=lambda *args: self.set_tool('erase'))
        self.act_erase.setCheckable(True)
        tb.addAction(self.act_erase)

        # 재분석은 좌측 도구 툴바에서 제거하고, 작업 메뉴/단축키(F5)로만 제공한다.

        self.act_magic = QAction("⭐", self)
        self.act_magic.setCheckable(True)
        self.act_magic.triggered.connect(lambda *args: self.set_tool('magic_wand'))
        tb.addAction(self.act_magic)
        try:
            _magic_btn = tb.widgetForAction(self.act_magic)
            if _magic_btn is not None:
                _magic_btn.setStyleSheet(
                    "QToolButton { font-size:18px; color:#ffd43b; }"
                    "QToolButton:checked { background:#8A4A52; border:1px solid #A85D66; color:#ffffff; font-weight:700; }"
                )
        except Exception:
            pass

        self.act_mask_wrap = QAction("🩹", self)
        self.act_mask_wrap.setCheckable(True)
        self.act_mask_wrap.triggered.connect(lambda *args: self.set_tool('mask_wrap'))
        tb.addAction(self.act_mask_wrap)

        self.act_mask_cut = QAction("🔪", self)
        self.act_mask_cut.setCheckable(True)
        self.act_mask_cut.triggered.connect(lambda *args: self.set_tool('mask_cut'))
        tb.addAction(self.act_mask_cut)

        # QCheckBox를 QToolBar에 직접 넣으면 QToolBar 레이아웃 + QCheckBox indicator가 따로 놀아
        # 다른 도구 버튼들과 여백/정렬이 맞지 않는다.
        # 그래서 다른 그림판 도구와 동일하게 checkable QAction으로 통일한다.
        self.act_mask_toggle = QAction("☐", self)
        self.act_mask_toggle.setCheckable(True)
        # QAction 자체 툴팁은 QToolBar가 즉시 표시할 수 있으므로 비워둔다.
        # 실제 안내는 register_delayed_tooltip()의 지연 툴팁 하나로만 표시한다.
        self.act_mask_toggle.setToolTip("")
        self.act_mask_toggle.setStatusTip("")
        self.act_mask_toggle.setWhatsThis("")

        self.act_mask_toggle.toggled.connect(self.on_mask_toggle_changed)
        tb.addAction(self.act_mask_toggle)

        # 기존 코드 호환용 별칭: setChecked/toggle/blockSignals/setVisible 등을 QAction이 그대로 지원한다.
        self.cb_mask_toggle = self.act_mask_toggle
        self.mask_toggle_wrap = tb.widgetForAction(self.act_mask_toggle)
        if self.mask_toggle_wrap:
            self.mask_toggle_wrap.setToolTip("")
            self.mask_toggle_wrap.setStyleSheet("")

        self.act_final_paint_color = QAction("", self)
        self.act_final_paint_color.triggered.connect(lambda *args: self.pick_color("final_paint"))
        tb.addAction(self.act_final_paint_color)

        self.act_final_area_paint = QAction("▦", self)
        self.act_final_area_paint.setCheckable(True)
        self.act_final_area_paint.setToolTip("")
        self.act_final_area_paint.setStatusTip("")
        self.act_final_area_paint.setWhatsThis("")
        self.act_final_area_paint.triggered.connect(lambda *args: self.set_tool("area_paint"))
        tb.addAction(self.act_final_area_paint)
        try:
            _area_paint_widget = tb.widgetForAction(self.act_final_area_paint)
            if _area_paint_widget is not None:
                _area_paint_widget.setToolTip("")
                try:
                    _area_paint_widget.clicked.connect(lambda checked=False: self.set_tool("area_paint"))
                except Exception:
                    pass
        except Exception:
            pass

        self.act_final_text_tool = QAction("T", self)
        self.act_final_text_tool.setCheckable(True)
        self.act_final_text_tool.triggered.connect(lambda *args: self.set_tool("final_text"))
        tb.addAction(self.act_final_text_tool)

        # 좌측 도구 버튼은 클릭/단축키 어느 쪽으로 켜도 같은 선택 상태를 보여야 한다.
        # 즉시 실행 액션(색상 선택, 배경 반영 등)은 제외하고 draw_mode를 가진 도구만 묶는다.
        self.left_tool_actions = {
            'draw': self.act_brush,
            'erase': self.act_erase,
            'magic_wand': self.act_magic,
            'mask_wrap': self.act_mask_wrap,
            'mask_cut': self.act_mask_cut,
            'area_paint': self.act_final_area_paint,
            'final_text': self.act_final_text_tool,
        }
        self.left_tool_buttons = {}
        try:
            for _tool, _act in self.left_tool_actions.items():
                _btn = tb.widgetForAction(_act)
                if _btn is None:
                    continue
                self.left_tool_buttons[_tool] = _btn
                try:
                    _btn.setCheckable(True)
                except Exception:
                    pass
                try:
                    _btn.setProperty("ysb_left_tool_button", True)
                    _btn.setCursor(Qt.CursorShape.PointingHandCursor)
                except Exception:
                    pass
        except Exception:
            pass

        self.act_final_paint_to_bg = QAction("↧", self)
        self.act_final_paint_to_bg.triggered.connect(self.use_final_background_as_source)
        tb.addAction(self.act_final_paint_to_bg)

        self.act_final_paint_above_text = QAction("T↓", self)
        self.act_final_paint_above_text.setCheckable(True)
        self.act_final_paint_above_text.setChecked(False)
        self.act_final_paint_above_text.toggled.connect(self.on_final_paint_above_text_toggled)
        tb.addAction(self.act_final_paint_above_text)

        self.tb = tb
        self.tb.setFixedWidth(42)
        self.tb.setVisible(True)
        self.tb.setEnabled(False)
        ll.addWidget(tb)

        vc = QWidget()
        vc.setObjectName("CanvasPanel")
        vl = QVBoxLayout(vc)
        vl.setContentsMargins(0, 0, 0, 0)

        self.page_tab_container = QWidget()
        self.page_tab_container.setFixedHeight(36)
        page_tab_layout = QHBoxLayout(self.page_tab_container)
        page_tab_layout.setContentsMargins(4, 3, 4, 3)
        page_tab_layout.setSpacing(6)
        self.btn_page_tab_menu = QToolButton()
        self.btn_page_tab_menu.setText("☰")
        self.btn_page_tab_menu.setToolTip(self.tr_ui("맵 목록"))
        self.btn_page_tab_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_page_tab_menu.setFixedSize(32, 28)
        self.btn_page_tab_menu.clicked.connect(self.show_page_tab_menu)
        self.page_tab_bar = ScrollablePageTabBar(self)
        self.page_tab_bar.setExpanding(False)
        self.page_tab_bar.setDrawBase(False)
        self.page_tab_bar.setUsesScrollButtons(True)
        self.page_tab_bar.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.page_tab_bar.setMovable(True)
        self.page_tab_bar.setTabsClosable(True)
        self.page_tab_bar.currentChanged.connect(self.on_page_tab_changed)
        self.page_tab_bar.tabCloseRequested.connect(self.close_page_from_tab)
        try:
            self.page_tab_bar.tabRenameRequested.connect(self.rename_page_source_from_tab)
        except Exception:
            pass
        try:
            self.page_tab_bar.tabMoved.connect(self.on_page_tab_moved)
        except Exception:
            pass

        self.btn_page_scroll_left = QToolButton()
        self.btn_page_scroll_left.setText("◀")
        self.btn_page_scroll_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_page_scroll_left.setFixedSize(24, 28)
        self.btn_page_scroll_left.clicked.connect(self.scroll_page_tabs_left)

        self.btn_page_scroll_right = QToolButton()
        self.btn_page_scroll_right.setText("▶")
        self.btn_page_scroll_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_page_scroll_right.setFixedSize(24, 28)
        self.btn_page_scroll_right.clicked.connect(self.scroll_page_tabs_right)

        self.btn_page_add = QToolButton()
        self.btn_page_add.setText("+")
        self.btn_page_add.setToolTip(self.native_tooltip_html("게임 가져오기", self.shortcut_text_for_key("project_import_maker_game", "Alt+O"), "현재 프로젝트에 RPG Maker MV/MZ 게임 폴더를 클론하고 맵 페이지를 재구성합니다."))
        self.btn_page_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_page_add.setFixedSize(32, 28)
        self.btn_page_add.clicked.connect(self.import_maker_game_action)
        page_tab_layout.addWidget(self.btn_page_tab_menu, 0)
        page_tab_layout.addWidget(self.page_tab_bar, 1)
        page_tab_layout.addWidget(self.btn_page_scroll_left, 0)
        page_tab_layout.addWidget(self.btn_page_scroll_right, 0)
        page_tab_layout.addWidget(self.btn_page_add, 0)
        vl.addWidget(self.page_tab_container)

        self.maker_database_mode_bar = QFrame()
        self.maker_database_mode_bar.setObjectName("MakerDatabaseModeBar")
        self.maker_database_mode_bar.setFixedHeight(34)
        self.maker_database_mode_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        db_mode_lay = QHBoxLayout(self.maker_database_mode_bar)
        db_mode_lay.setContentsMargins(8, 2, 8, 2)
        db_mode_lay.setSpacing(8)
        self.lbl_maker_database_mode = QLabel(self.tr_ui("데이터베이스 모드"))
        self.lbl_maker_database_mode.setObjectName("MakerDatabaseModeLabel")
        self.lbl_maker_database_mode.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.lbl_maker_database_mode_detail = QLabel(self.tr_ui(""))
        self.lbl_maker_database_mode_detail.setObjectName("MakerDatabaseModeDetail")
        self.lbl_maker_database_mode_detail.hide()
        self.btn_exit_maker_database_mode = QPushButton(self.tr_ui("데이터베이스 모드 나가기"))
        self.btn_exit_maker_database_mode.setFixedHeight(26)
        self.btn_exit_maker_database_mode.clicked.connect(self.exit_maker_database_mode)
        db_mode_lay.addWidget(self.lbl_maker_database_mode, 0)
        db_mode_lay.addStretch(1)
        db_mode_lay.addWidget(self.btn_exit_maker_database_mode, 0)
        self.maker_database_mode_bar.hide()
        vl.addWidget(self.maker_database_mode_bar)

        self._refreshing_page_tabs = False
        self.apply_page_tab_style()
        self.refresh_page_tabs()

        # 쯔꾸르붕이에서는 상단 공유 옵션바를 사용자 UI에 노출하지 않는다.
        # 기존 내부 함수가 참조할 수 있으므로 호환 객체만 만들고 0px 숨김 상태로 둔다.
        self.shared_option_bar = QWidget()
        self.shared_option_bar.setObjectName("SharedOptionBar")
        self.shared_option_bar_layout = QHBoxLayout(self.shared_option_bar)
        self.shared_option_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.shared_option_bar_layout.setSpacing(0)
        self.shared_option_left = QWidget()
        self.shared_option_left_layout = QHBoxLayout(self.shared_option_left)
        self.shared_option_left_layout.setContentsMargins(0, 0, 0, 0)
        self.shared_option_left_layout.setSpacing(6)
        self.shared_option_right = QWidget()
        self.shared_option_right_layout = QHBoxLayout(self.shared_option_right)
        self.shared_option_right_layout.setContentsMargins(0, 0, 0, 0)
        self.shared_option_right_layout.setSpacing(6)
        self.shared_option_bar_layout.addWidget(self.shared_option_left, 0)
        self.shared_option_bar_layout.addStretch(1)
        self.shared_option_bar_layout.addWidget(self.shared_option_right, 0)
        try:
            self.shared_option_bar.setFixedHeight(0)
            self.shared_option_bar.setMaximumHeight(0)
            self.shared_option_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        self.shared_option_bar.hide()
        vl.addWidget(self.shared_option_bar)

        self.final_edit_bar = QWidget()
        final_bar = QHBoxLayout(self.final_edit_bar)
        final_bar.setContentsMargins(6, 1, 6, 1)
        final_bar.setSpacing(6)
        self.final_item_font = QFontComboBox()
        self.final_item_font.setMinimumWidth(180)
        self.final_item_size = QSpinBox()
        self.final_item_size.setRange(5, 500)
        self.final_item_size.setSuffix(" px")
        self.final_item_stroke = QSpinBox()
        self.final_item_stroke.setRange(0, 100)
        self.final_item_stroke.setSuffix(" px")
        self.btn_item_text_color = QPushButton("문자색")
        self.btn_item_stroke_color = QPushButton("획색")
        self.btn_item_align_left = QPushButton("≡◁")
        self.btn_item_align_center = QPushButton("≡◇")
        self.btn_item_align_right = QPushButton("▷≡")
        self.sb_text_opacity = QSpinBox()
        self.sb_text_opacity.setRange(0, 100)
        self.sb_text_opacity.setValue(100)
        self.sb_text_opacity.setSuffix(" %")
        self.sb_text_opacity.setFixedWidth(76)
        self.sb_text_opacity.setToolTip("")
        self.btn_text_effect_gradient = QPushButton("◩")
        self.btn_text_effect_transform = QPushButton("⤢")
        self.btn_text_effect_skew = QPushButton("▱")
        self.btn_text_effect_trapezoid = QPushButton("▰")
        self.btn_text_effect_arc = QPushButton("⌒")
        self.btn_text_effect_rasterize = QPushButton("▣")
        for _btn, _tip in (
            (self.btn_text_effect_gradient, "고급 텍스트/획 옵션"),
            (self.btn_text_effect_transform, "텍스트 변형"),
            (self.btn_text_effect_skew, "평행사변형 변형"),
            (self.btn_text_effect_trapezoid, "사다리꼴 변형"),
            (self.btn_text_effect_arc, "부채꼴 변형"),
            (self.btn_text_effect_rasterize, "텍스트를 객체로 변환"),
        ):
            _btn.setFixedSize(30, 26)
            _btn.setToolTip("")
        # 공유바에는 선택 텍스트용 빠른 옵션만 최소 구성으로 올린다.
        final_bar.addWidget(QLabel("불투명도"))
        final_bar.addWidget(self.sb_text_opacity)
        final_bar.addWidget(self.btn_text_effect_gradient)
        final_bar.addWidget(self.btn_text_effect_transform)
        final_bar.addWidget(self.btn_text_effect_skew)
        final_bar.addWidget(self.btn_text_effect_trapezoid)
        final_bar.addWidget(self.btn_text_effect_arc)
        final_bar.addStretch()
        self.final_edit_bar.hide()
        vl.addWidget(self.final_edit_bar)
        try:
            self.final_edit_bar.setFixedHeight(30)
            self.final_edit_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception:
            pass

        self.final_paint_option_bar = QWidget()
        final_paint_bar = QHBoxLayout(self.final_paint_option_bar)
        final_paint_bar.setContentsMargins(6, 1, 6, 1)
        final_paint_bar.setSpacing(6)
        self.sb_brush_size = QSpinBox()
        self.sb_brush_size.setRange(1, 500)
        self.sb_brush_size.setSingleStep(1)
        self.sb_brush_size.setValue(max(1, min(500, int(getattr(self.view, "brush_size", 25) or 25))))
        self.sb_brush_size.setSuffix(" px")
        self.sb_brush_size.setFixedWidth(84)
        self.sb_brush_size.setToolTip("")
        self.sb_brush_size.valueChanged.connect(self.on_brush_size_changed)
        self.sb_final_paint_opacity = QSpinBox()
        self.sb_final_paint_opacity.setRange(1, 100)
        self.sb_final_paint_opacity.setValue(100)
        self.sb_final_paint_opacity.setSuffix(" %")
        self.sb_final_paint_opacity.setFixedWidth(80)
        self.sb_final_paint_opacity.valueChanged.connect(self.on_final_paint_opacity_changed)
        final_paint_bar.addWidget(QLabel(self.tr_ui("브러시")))
        final_paint_bar.addWidget(QLabel(self.tr_ui("크기")))
        final_paint_bar.addWidget(self.sb_brush_size)
        final_paint_bar.addWidget(QLabel(self.tr_ui("불투명도")))
        final_paint_bar.addWidget(self.sb_final_paint_opacity)
        final_paint_bar.addStretch()
        self.final_paint_option_bar.hide()
        vl.addWidget(self.final_paint_option_bar)
        try:
            self.final_paint_option_bar.setFixedHeight(30)
            self.final_paint_option_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception:
            pass

        self.area_paint_bar = QWidget()
        area_paint_bar_lay = QHBoxLayout(self.area_paint_bar)
        area_paint_bar_lay.setContentsMargins(6, 1, 6, 1)
        area_paint_bar_lay.setSpacing(6)
        self.btn_area_paint_rect = QPushButton(self.tr_ui("▭ 사각형"))
        self.btn_area_paint_rect.setCheckable(True)
        self.btn_area_paint_rect.clicked.connect(lambda checked=False: self.set_area_paint_shape("rect"))
        self.btn_area_paint_free = QPushButton(self.tr_ui("✎ 자유형"))
        self.btn_area_paint_free.setCheckable(True)
        self.btn_area_paint_free.clicked.connect(lambda checked=False: self.set_area_paint_shape("free"))
        area_paint_bar_lay.addWidget(QLabel(self.tr_ui("영역 페인팅")))
        area_paint_bar_lay.addWidget(self.btn_area_paint_rect)
        area_paint_bar_lay.addWidget(self.btn_area_paint_free)
        area_paint_bar_lay.addWidget(QLabel(self.tr_ui("선택한 영역을 현재 최종 페인팅 색상으로 채웁니다.")))
        area_paint_bar_lay.addStretch()
        self.area_paint_bar.hide()
        vl.addWidget(self.area_paint_bar)
        try:
            self.area_paint_bar.setFixedHeight(30)
            self.area_paint_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        self.set_area_paint_shape("rect", silent=True)

        self.magic_wand_bar = QWidget()
        magic_bar = QHBoxLayout(self.magic_wand_bar)
        magic_bar.setContentsMargins(6, 1, 6, 1)
        magic_bar.setSpacing(6)
        self.sb_magic_tolerance = QSpinBox()
        self.sb_magic_tolerance.setRange(0, 255)
        self.sb_magic_tolerance.setValue(20)
        self.sb_magic_tolerance.setFixedWidth(70)
        self.sb_magic_tolerance.setToolTip("요술봉 RGB 허용범위")
        self.btn_magic_expand = QPushButton("영역확장")
        self.btn_magic_expand.clicked.connect(self.expand_magic_wand_selection)
        self.sb_magic_expand = QSpinBox()
        self.sb_magic_expand.setRange(0, 200)
        self.sb_magic_expand.setValue(3)
        self.sb_magic_expand.setSuffix(" px")
        self.sb_magic_expand.setFixedWidth(80)
        self.sb_magic_expand.setToolTip("요술봉 영역확장 범위")
        self.btn_magic_fill = QPushButton(self.tr_ui("마스킹 칠하기"))
        self.btn_magic_fill.clicked.connect(self.fill_magic_wand_mask)
        magic_bar.addWidget(QLabel("요술봉"))
        magic_bar.addWidget(QLabel("RGB 허용범위"))
        magic_bar.addWidget(self.sb_magic_tolerance)
        magic_bar.addWidget(self.btn_magic_expand)
        magic_bar.addWidget(QLabel("확장 범위"))
        magic_bar.addWidget(self.sb_magic_expand)
        magic_bar.addWidget(self.btn_magic_fill)
        magic_bar.addStretch()
        self.magic_wand_bar.hide()
        vl.addWidget(self.magic_wand_bar)
        try:
            self.magic_wand_bar.setFixedHeight(30)
            self.magic_wand_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        self.sb_magic_tolerance.valueChanged.connect(self.on_magic_wand_tolerance_changed)

        self.mask_wrap_bar = QWidget()
        mask_wrap_bar_lay = QHBoxLayout(self.mask_wrap_bar)
        mask_wrap_bar_lay.setContentsMargins(6, 1, 6, 1)
        mask_wrap_bar_lay.setSpacing(6)
        self.btn_mask_wrap_rect = QPushButton(self.tr_ui("▭ 사각형"))
        self.btn_mask_wrap_rect.setCheckable(True)
        self.btn_mask_wrap_rect.clicked.connect(lambda checked=False: self.set_mask_wrap_shape("rect"))
        self.btn_mask_wrap_free = QPushButton(self.tr_ui("✎ 자유형"))
        self.btn_mask_wrap_free.setCheckable(True)
        self.btn_mask_wrap_free.clicked.connect(lambda checked=False: self.set_mask_wrap_shape("free"))
        mask_wrap_bar_lay.addWidget(QLabel(self.tr_ui("마스크 랩핑")))
        mask_wrap_bar_lay.addWidget(self.btn_mask_wrap_rect)
        mask_wrap_bar_lay.addWidget(self.btn_mask_wrap_free)
        mask_wrap_bar_lay.addWidget(QLabel(self.tr_ui("선택한 영역 안의 떨어진 마스크들을 하나의 채움 영역으로 감싸줍니다.")))
        mask_wrap_bar_lay.addStretch()
        self.mask_wrap_bar.hide()
        vl.addWidget(self.mask_wrap_bar)
        try:
            self.mask_wrap_bar.setFixedHeight(30)
            self.mask_wrap_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        self.set_mask_wrap_shape("rect", silent=True)

        self.mask_cut_bar = QWidget()
        mask_cut_bar_lay = QHBoxLayout(self.mask_cut_bar)
        mask_cut_bar_lay.setContentsMargins(6, 1, 6, 1)
        mask_cut_bar_lay.setSpacing(6)
        self.btn_mask_cut_rect = QPushButton(self.tr_ui("▭ 사각형"))
        self.btn_mask_cut_rect.setCheckable(True)
        self.btn_mask_cut_rect.clicked.connect(lambda checked=False: self.set_mask_cut_shape("rect"))
        self.btn_mask_cut_free = QPushButton(self.tr_ui("✎ 자유형"))
        self.btn_mask_cut_free.setCheckable(True)
        self.btn_mask_cut_free.clicked.connect(lambda checked=False: self.set_mask_cut_shape("free"))
        self.sb_mask_cut_px = QSpinBox()
        self.sb_mask_cut_px.setRange(1, 200)
        self.sb_mask_cut_px.setValue(8)
        self.sb_mask_cut_px.setSuffix(" px")
        mask_cut_bar_lay.addWidget(QLabel(self.tr_ui("마스크 커팅")))
        mask_cut_bar_lay.addWidget(self.btn_mask_cut_rect)
        mask_cut_bar_lay.addWidget(self.btn_mask_cut_free)
        mask_cut_bar_lay.addWidget(QLabel(self.tr_ui("커팅 폭")))
        mask_cut_bar_lay.addWidget(self.sb_mask_cut_px)
        mask_cut_bar_lay.addWidget(QLabel(self.tr_ui("선택 영역 밖 경계를 지정 픽셀만큼 잘라 붙어 있는 마스크를 분리합니다.")))
        mask_cut_bar_lay.addStretch()
        self.mask_cut_bar.hide()
        vl.addWidget(self.mask_cut_bar)
        try:
            self.mask_cut_bar.setFixedHeight(30)
            self.mask_cut_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        self.set_mask_cut_shape("rect", silent=True)

        self.ocr_region_bar = QWidget()
        ocr_region_bar_lay = QHBoxLayout(self.ocr_region_bar)
        ocr_region_bar_lay.setContentsMargins(6, 1, 6, 1)
        ocr_region_bar_lay.setSpacing(6)
        self.btn_ocr_region_rect = QPushButton(self.tr_ui("▭ 사각형"))
        self.btn_ocr_region_rect.setCheckable(True)
        self.btn_ocr_region_rect.clicked.connect(lambda checked=False: self.set_ocr_region_shape("rect"))
        self.btn_ocr_region_free = QPushButton(self.tr_ui("✎ 자유형"))
        self.btn_ocr_region_free.setCheckable(True)
        self.btn_ocr_region_free.clicked.connect(lambda checked=False: self.set_ocr_region_shape("free"))
        self.btn_ocr_region_finish = QPushButton(self.tr_ui("분석 영역 지정 종료"))
        self.btn_ocr_region_finish.clicked.connect(self.finish_ocr_analysis_region_selection)
        ocr_region_bar_lay.addWidget(QLabel(self.tr_ui("OCR 분석 영역")))
        ocr_region_bar_lay.addWidget(self.btn_ocr_region_rect)
        ocr_region_bar_lay.addWidget(self.btn_ocr_region_free)
        ocr_region_bar_lay.addWidget(QLabel(self.tr_ui("OCR이 읽을 범위를 드래그로 지정합니다.")))
        ocr_region_bar_lay.addStretch()
        ocr_region_bar_lay.addWidget(self.btn_ocr_region_finish)
        self.ocr_region_bar.hide()
        vl.addWidget(self.ocr_region_bar)
        try:
            self.ocr_region_bar.setFixedHeight(30)
            self.ocr_region_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        self.set_ocr_region_shape("rect", silent=True)

        self.source_compare_bar = QWidget()
        source_compare_bar_lay = QHBoxLayout(self.source_compare_bar)
        source_compare_bar_lay.setContentsMargins(6, 1, 6, 1)
        source_compare_bar_lay.setSpacing(6)
        source_compare_bar_lay.addStretch()

        self.cb_text_effect_preview = QCheckBox(self.tr_ui("텍스트 이펙트 미리보기"))
        try:
            _effect_preview_checked = bool(self.get_page_text_effect_preview_enabled())
        except Exception:
            _effect_preview_checked = bool(getattr(self, "text_effect_preview_enabled", True))
        self.cb_text_effect_preview.setChecked(_effect_preview_checked)
        self.cb_text_effect_preview.setToolTip(self.tr_ui("후광, 그림자, 2중 획 같은 무거운 텍스트 효과를 현재 페이지 작업 화면에 표시합니다. 끄면 이 페이지의 화면 조작이 가벼워지며 최종 출력에는 영향을 주지 않습니다."))
        self.cb_text_effect_preview.toggled.connect(self.on_text_effect_preview_toggled)

        self.source_compare_controls = QWidget()
        source_compare_controls_lay = QHBoxLayout(self.source_compare_controls)
        source_compare_controls_lay.setContentsMargins(0, 0, 0, 0)
        source_compare_controls_lay.setSpacing(6)
        self.cb_source_compare_sync = QCheckBox(self.tr_ui("스크롤 동기화"))
        self.cb_source_compare_sync.setChecked(True)
        self.cb_source_compare_sync.toggled.connect(self.on_source_compare_sync_toggled)
        self.btn_source_compare_close = QPushButton(self.tr_ui("원본 비교창 끄기"))
        self.btn_source_compare_close.clicked.connect(self.close_source_compare_view)
        source_compare_controls_lay.addWidget(self.cb_source_compare_sync)
        source_compare_controls_lay.addWidget(self.btn_source_compare_close)
        # 쯔꾸르붕이에서는 텍스트 이펙트/원본 비교 공유 컨트롤을 상단 UI에 붙이지 않는다.
        # 객체는 호환용으로만 유지한다.
        self.cb_text_effect_preview.hide()
        self.source_compare_controls.hide()
        self.source_compare_bar.hide()
        vl.addWidget(self.source_compare_bar)
        try:
            self.source_compare_bar.setFixedHeight(30)
            self.source_compare_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        except Exception:
            pass

        self.source_compare_view = QGraphicsView()
        self.source_compare_view.setObjectName("SourceCompareView")
        self.source_compare_scene = QGraphicsScene(self.source_compare_view)
        self.source_compare_view.setScene(self.source_compare_scene)
        self.source_compare_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.source_compare_view.setBackgroundBrush(QBrush(QColor("#0B0C0E")))
        self.source_compare_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.source_compare_view.setMinimumWidth(0)
        try:
            self.source_compare_view.viewport().installEventFilter(self)
        except Exception:
            pass
        self.source_compare_view.hide()

        self.source_compare_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.source_compare_splitter.setHandleWidth(6)
        self.source_compare_splitter.addWidget(self.source_compare_view)
        self.source_compare_splitter.addWidget(self.view)
        self.source_compare_splitter.setChildrenCollapsible(True)
        self.source_compare_splitter.setCollapsible(0, True)
        self.source_compare_splitter.setCollapsible(1, False)
        self.source_compare_splitter.setStretchFactor(0, 1)
        self.source_compare_splitter.setStretchFactor(1, 2)
        self.source_compare_splitter.setSizes([0, 1200])
        vl.addWidget(self.source_compare_splitter)
        try:
            self.source_compare_splitter.handle(1).installEventFilter(self)
            self._source_compare_splitter_handle = self.source_compare_splitter.handle(1)
        except Exception:
            pass

        try:
            self.source_compare_splitter.splitterMoved.connect(lambda pos, index: None)
            self.view.horizontalScrollBar().valueChanged.connect(self._on_main_view_scroll_changed_for_source_compare)
            self.view.verticalScrollBar().valueChanged.connect(self._on_main_view_scroll_changed_for_source_compare)
            self.source_compare_view.horizontalScrollBar().valueChanged.connect(self._on_source_compare_scroll_changed_for_main)
            self.source_compare_view.verticalScrollBar().valueChanged.connect(self._on_source_compare_scroll_changed_for_main)
        except Exception:
            pass

        # 데이터베이스 모드 전용 좌측 프리뷰.
        # 일반 맵 프리뷰와 분리해서 DB 모드에서는 이 패널만 표시한다.
        self.maker_database_preview_panel = QFrame()
        self.maker_database_preview_panel.setObjectName("MakerDatabasePreviewPanel")
        self.maker_database_preview_panel.setMinimumHeight(260)
        self.maker_database_preview_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        db_preview_lay = QVBoxLayout(self.maker_database_preview_panel)
        db_preview_lay.setContentsMargins(12, 10, 12, 10)
        db_preview_lay.setSpacing(6)
        self.lbl_maker_database_preview_title = QLabel(self.tr_ui("데이터베이스 프리뷰"))
        self.lbl_maker_database_preview_title.setObjectName("MakerDatabasePreviewTitle")
        self.lbl_maker_database_preview_title.setWordWrap(True)
        self.lbl_maker_database_preview_title.hide()
        self.lbl_maker_database_preview_subtitle = QLabel(self.tr_ui("오른쪽 표에서 DB 항목을 선택하면 이곳에 표시됩니다."))
        self.lbl_maker_database_preview_subtitle.setObjectName("MakerDatabasePreviewSubtitle")
        self.lbl_maker_database_preview_subtitle.setWordWrap(True)
        self.lbl_maker_database_preview_subtitle.hide()
        # DB 프리뷰는 일반 맵 프리뷰처럼 "렌더된 이미지"로 다룬다.
        # QScrollArea + QLabel 조합으로 Ctrl+휠 확대/축소와 스크롤을 지원한다.
        self.maker_database_preview_scroll = QScrollArea()
        self.maker_database_preview_scroll.setObjectName("MakerDatabasePreviewScroll")
        self.maker_database_preview_scroll.setWidgetResizable(False)
        self.maker_database_preview_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.maker_database_preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.maker_database_preview_scroll.setStyleSheet("QScrollArea#MakerDatabasePreviewScroll { background:#050608; border:1px solid #24252b; }")
        self.lbl_maker_database_preview_canvas = QLabel("")
        self.lbl_maker_database_preview_canvas.setObjectName("MakerDatabasePreviewCanvas")
        self.lbl_maker_database_preview_canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_maker_database_preview_canvas.setMinimumSize(320, 240)
        self.lbl_maker_database_preview_canvas.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.lbl_maker_database_preview_canvas.setStyleSheet("background:#050608; color:#9b949a;")
        self.lbl_maker_database_preview_canvas.installEventFilter(self)
        try:
            self.maker_database_preview_scroll.viewport().installEventFilter(self)
        except Exception:
            pass
        self.maker_database_preview_scroll.setWidget(self.lbl_maker_database_preview_canvas)
        self._maker_database_preview_zoom = 1.0
        self._maker_database_preview_fit_mode = True

        # 구버전 호환용 라벨. 실제 DB 프리뷰는 캔버스 QLabel을 사용한다.
        self.maker_database_preview_card = QFrame()
        self.maker_database_preview_card.setObjectName("MakerDatabasePreviewCard")
        self.maker_database_preview_card.hide()
        self.lbl_maker_database_preview_image = QLabel("")
        self.lbl_maker_database_preview_kind = QLabel("")
        self.lbl_maker_database_preview_source = QLabel("")
        self.lbl_maker_database_preview_translation = QLabel("")
        self.lbl_maker_database_preview_hint = QLabel("")

        db_preview_lay.addWidget(self.lbl_maker_database_preview_title, 0)
        db_preview_lay.addWidget(self.lbl_maker_database_preview_subtitle, 0)
        db_preview_lay.addWidget(self.maker_database_preview_scroll, 1)
        self.maker_database_preview_panel.hide()
        vl.addWidget(self.maker_database_preview_panel)

        ll.addWidget(vc)

        cl = QHBoxLayout()
        self.btn_prev_page = QPushButton("◀")
        self.btn_prev_page.clicked.connect(self.prev)
        cl.addWidget(self.btn_prev_page)
        self.btn_page = QPushButton("0 / 0")
        self.btn_page.setToolTip("")
        self.btn_page.setStyleSheet("border:none; font-weight:bold; color:#CBC4C9;")
        self.btn_page.clicked.connect(self.jump_page)
        cl.addWidget(self.btn_page)
        self.btn_next_page = QPushButton("▶")
        self.btn_next_page.clicked.connect(self.next)
        cl.addWidget(self.btn_next_page)

        # 쯔꾸르붕이 4차 정리: 화면 작업탭 콤보는 완전 제거한다.
        # 내부 렌더/Undo 호환용으로만 고정 프리뷰 모드 상태 객체를 둔다.
        self.last_mode = 4
        self._current_work_mode = 4
        self.cb_mode = _MakerFixedModeState(self, 4)

        # 쯔꾸르붕이 Undo 정책: 전역 Undo/Redo 버튼은 두지 않는다.
        # Ctrl+Z/Ctrl+Y는 현재 텍스트 입력칸의 Qt 기본 Undo/Redo로만 처리한다.
        self.update_paint_toolbar_visibility()
        self.update_undo_redo_buttons()

        cl.addStretch()
        self.btn_reanalyze = QPushButton(self.tr_ui("↻ 재분석"), clicked=self.reanalyze_mask)
        self.btn_reanalyze.setStyleSheet("QPushButton { background:#28262B;color:#E0DADF;font-weight:700;border:1px solid #3A363B;border-radius:0px;padding:6px 10px; } QPushButton:hover { background:#332B30; border-color:#665A62; }")
        self.btn_reanalyze.setVisible(False)
        self.btn_reanalyze.hide()
        self.btn_analyze = QPushButton(self.tr_ui("⚡ 분석"), clicked=self.anal)
        self.btn_analyze.setStyleSheet("QPushButton { background:#8A4A52;color:#ffffff;font-weight:800;border:1px solid #A85D66;border-radius:0px;padding:6px 13px; } QPushButton:hover { background:#6F3940; border-color:#C78A90; } QPushButton:pressed { background:#5B3136; }")
        self.btn_analyze.hide()
        self.update_paint_toolbar_visibility()
        vl.addLayout(cl)
        split.addWidget(lp)

        # Right Panel
        rp = QWidget()
        rp.setObjectName("RightPanel")
        # 오른쪽 작업 패널은 기본 상태에서는 사용자지정 콤보박스까지 보이도록 충분한 폭을 잡는다.
        # 단, splitter를 끌면 왼쪽/오른쪽 모두 거의 끝까지 접을 수 있게 최소 폭은 낮게 둔다.
        rp.setMinimumWidth(0)
        rp.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        rl = QVBoxLayout(rp)
        rl.setContentsMargins(6, 6, 6, 6)
        rl.setSpacing(4)

        self.right_panel = rp
        self.right_scroll = QScrollArea()
        self.right_scroll.setObjectName("RightPanelScroll")
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.right_scroll.setMinimumWidth(0)
        self.right_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.right_scroll.setWidget(rp)
        split.addWidget(self.right_scroll)
        split.setChildrenCollapsible(True)
        split.setCollapsible(0, True)
        split.setCollapsible(1, True)
        # 쯔꾸르붕이는 텍스트 표가 작업의 절반이므로 좌/우 기본 비율을 1:1로 둔다.
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([900, 900])

        # 글꼴 프리셋은 옵션 메뉴의 "글꼴 프리셋 관리"에서 다룬다.
        # 캐시/자동저장 로직 호환을 위해 컨트롤 객체는 숨겨 둔다.
        self.cb_text_preset = QComboBox(self)
        self.cb_text_preset.hide()
        self.btn_preset_save = QPushButton("프리셋 저장", self)
        self.btn_preset_save.hide()
        self.btn_preset_import = QPushButton("JSON 가져오기", self)
        self.btn_preset_import.hide()
        self.btn_preset_apply_page = QPushButton("페이지 적용", self)
        self.btn_preset_apply_page.hide()
        self.btn_preset_apply_all = QPushButton("전체 적용", self)
        self.btn_preset_apply_all.hide()

        # 우측 인터페이스: 텍스트 / AI / 기타 3영역 압축 배치
        # 원칙: 기존 위젯/시그널은 유지하고, 큰 그룹박스 없이 작은 제목줄+촘촘한 행으로만 재배치한다.
        def _right_section_title(text):
            lbl = QLabel(self.tr_ui(text))
            lbl.setObjectName("RightSectionTitle")
            lbl.setFixedHeight(17)
            if self.is_light_theme():
                lbl.setStyleSheet("QLabel#RightSectionTitle { color:#555056; font-weight:700; padding:0px 0px 1px 0px; }")
            else:
                lbl.setStyleSheet("QLabel#RightSectionTitle { color:#b7c4d4; font-weight:700; padding:0px 0px 1px 0px; }")
            return lbl

        def _compact_row(spacing=3):
            lay = QHBoxLayout()
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(spacing)
            return lay

        def _short_label(text, width=None):
            lbl = QLabel(self.tr_ui(text))
            lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            if width is not None:
                lbl.setFixedWidth(width)
            return lbl

        def _fixed_combo(widget, width):
            widget.setFixedHeight(26)
            widget.setFixedWidth(width)
            widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            # 콤보 팝업은 Qt 기본 view를 유지한다.
            # 직접 QListView를 붙이면 일부 환경에서 팝업이 두 번 열리는 것처럼 번쩍일 수 있다.
            return widget

        def _fixed_button(widget, width=None):
            widget.setFixedHeight(26)
            if width is not None:
                widget.setFixedWidth(width)
            else:
                widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            return widget

        _right_control_line_width = 690

        def _row_widget(layout, object_name):
            box = QWidget()
            box.setObjectName(object_name)
            box.setFixedWidth(_right_control_line_width)
            box.setFixedHeight(26)
            box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            box.setLayout(layout)
            return box

        # === 텍스트 스타일 UI ===
        # 쯔꾸르붕이는 이미지 위 텍스트 오브젝트를 편집하지 않는다.
        # 이전 YSB 식질툴의 폰트/획/정렬/자간/행간/개별 프리셋 UI는 생성하지 않는다.
        self.text_style_control_widgets = []

        # === 번역 / 제어코드 ===
        self.right_ai_title = _right_section_title("번역")
        rl.addWidget(self.right_ai_title)
        ai_line = _compact_row(spacing=2)
        self.cb_ocr_language = StableComboBox()
        self.cb_ocr_language.setObjectName("ocr_language_combo")
        _fixed_combo(self.cb_ocr_language, 78)
        self.refresh_ocr_language_combo(save=False)
        self.cb_ocr_language.currentIndexChanged.connect(self.on_ocr_language_toolbar_changed)

        self.cb_trans_provider = StableComboBox()
        self.cb_trans_provider.setObjectName("trans_provider_combo")
        _fixed_combo(self.cb_trans_provider, 88)
        self.cb_trans_provider.addItem("OpenAI", "openai")
        self.cb_trans_provider.addItem("DeepSeek", "deepseek")
        self.cb_trans_provider.addItem("Google", "google")
        self.cb_trans_provider.addItem("Gemini", "gemini")
        self.cb_trans_provider.addItem("Custom", "custom")
        self.set_combo_current_data(self.cb_trans_provider, getattr(self.api_settings, "selected_translation_provider", "openai"))
        self.cb_trans_provider.currentIndexChanged.connect(self.on_translation_provider_changed)

        self.sb_trans_chunk = QSpinBox()
        self.sb_trans_chunk.setRange(1, 100)
        self.sb_trans_chunk.setValue(self.trans_chunk_sizes.get("openai", 50))
        self.sb_trans_chunk.setSuffix(" items" if getattr(self, "ui_language", LANG_KO) == LANG_EN else "개")
        self.sb_trans_chunk.setFixedHeight(26)
        self.sb_trans_chunk.setStatusTip(self.tr_msg("한 번의 API 요청에 묶어서 보낼 텍스트 줄 수"))
        self.sb_trans_chunk.valueChanged.connect(self.on_translation_chunk_changed)
        self.sb_trans_chunk.hide()

        self.cb_show_final_text = QCheckBox("텍스트 표시")
        self.cb_show_final_text.setChecked(True)
        self.cb_show_final_text.setFixedHeight(26)
        self.cb_show_final_text.setFixedWidth(104)
        self.cb_show_final_text.toggled.connect(self.on_show_final_text_toggled)

        self.btn_translate = QPushButton("🌐 번역", clicked=self.trans)
        _fixed_button(self.btn_translate, 82)
        self.btn_inpaint = QPushButton("🎨 인페인팅", clicked=self.run_inpainting, styleSheet="QPushButton { background:#2f5d4a;color:#ffffff;border:1px solid #5f8d70;border-radius:0px;padding:4px 8px;font-weight:700; } QPushButton:hover { background:#3b6e57; border-color:#7fa68d; } QPushButton:pressed { background:#254838; }")
        _fixed_button(self.btn_inpaint, 95)

        self.lbl_maker_ctrl_restore = _short_label(self.tr_ui("제어코드"), 58)
        self.lbl_maker_ctrl_restore.setToolTip(self.tr_ui("원문의 맨앞과 맨 뒤에 있는 제어코드를 자동복원합니다."))
        self.btn_maker_ctrl_restore_current = QPushButton(self.tr_ui("현재 맵 복원"))
        self.btn_maker_ctrl_restore_current.setToolTip(self.tr_ui("현재 맵의 텍스트의 맨앞과 맨 뒤에 있는 제어코드를 자동복원 합니다."))
        self.btn_maker_ctrl_restore_current.clicked.connect(self.restore_edge_control_codes_current)
        _fixed_button(self.btn_maker_ctrl_restore_current, 98)
        self.btn_maker_ctrl_restore_all = QPushButton(self.tr_ui("일괄 맵 복원"))
        self.btn_maker_ctrl_restore_all.setToolTip(self.tr_ui("전체 맵의 텍스트의 맨앞과 맨 뒤에 있는 제어코드를 자동복원합니다."))
        self.btn_maker_ctrl_restore_all.clicked.connect(self.restore_edge_control_codes_all)
        _fixed_button(self.btn_maker_ctrl_restore_all, 98)

        self.lbl_maker_preview_refresh = _short_label(self.tr_ui("프리뷰"), 46)
        self.lbl_maker_preview_refresh.setToolTip(self.tr_ui("현재 맵의 프리뷰 이미지를 상태/캐시와 무관하게 다시 만듭니다."))
        self.btn_maker_preview_refresh = QPushButton(self.tr_ui("프리뷰 갱신"))
        self.btn_maker_preview_refresh.setToolTip(self.tr_ui("현재 맵의 프리뷰 이미지를 상태/캐시와 무관하게 다시 만듭니다."))
        self.btn_maker_preview_refresh.clicked.connect(self.force_refresh_maker_preview_action)
        _fixed_button(self.btn_maker_preview_refresh, 94)

        ai_line.addWidget(_short_label("엔진", 32))
        ai_line.addWidget(self.cb_trans_provider)
        ai_line.addWidget(self.btn_translate)
        ai_line.addSpacing(8)
        ai_line.addWidget(self.lbl_maker_ctrl_restore)
        ai_line.addWidget(self.btn_maker_ctrl_restore_current)
        ai_line.addWidget(self.btn_maker_ctrl_restore_all)
        try:
            self.lbl_maker_preview_refresh.hide()
            self.btn_maker_preview_refresh.hide()
        except Exception:
            pass
        ai_line.addStretch(1)
        ai_line_widget = _row_widget(ai_line, "RightAiControlLine")
        self.right_ai_line_widget = ai_line_widget
        self.right_control_title = None
        self.right_control_line_widget = ai_line_widget
        rl.addWidget(ai_line_widget)
        try:
            self._refresh_maker_control_code_buttons()
        except Exception:
            pass

        # OCR/인페인팅 위젯은 구버전 코드 호환용으로만 생성하고, 쯔꾸르붕이 UI에서는 노출하지 않는다.
        try:
            self.cb_ocr_language.hide()
            self.btn_inpaint.hide()
        except Exception:
            pass

        # === 기타 ===
        self.right_misc_title = _right_section_title("기타")
        rl.addWidget(self.right_misc_title)
        misc_line = _compact_row()
        self.btn_export_result = QPushButton(self.tr_ui("📤 결과물 출력"), clicked=self.export_result, styleSheet="QPushButton { background:#8A4A52;color:#ffffff;font-weight:600;border:1px solid #A85D66;border-radius:0px;min-height:0px;max-height:26px;padding:0px 6px; } QPushButton:hover { background:#6F3940; border-color:#C78A90; } QPushButton:pressed { background:#5B3136; }")
        _fixed_button(self.btn_export_result, 124)
        self.btn_text_cleanup = QPushButton("🧹 텍스트 정리", clicked=self.clean_text_current)
        _fixed_button(self.btn_text_cleanup, 124)
        misc_line.addWidget(self.btn_export_result)
        misc_line.addWidget(self.btn_text_cleanup)
        misc_line.addWidget(self.cb_show_final_text)
        misc_line.addSpacing(60)
        misc_line.addStretch(1)
        self.right_misc_line_widget = _row_widget(misc_line, "RightMiscLine")
        rl.addWidget(self.right_misc_line_widget)
        self.apply_action_button_theme_styles()

        self.tab = TextTableWidget(0, 4)
        try:
            self.tab.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.tab.viewport().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.tab.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
            self.tab.setDragEnabled(False)
            self.tab.setAcceptDrops(False)
            self.tab.viewport().setAcceptDrops(False)
            self.tab.setDropIndicatorShown(False)
            self.tab.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
            self.tab.setDragDropOverwriteMode(False)
        except Exception:
            pass
        self.tab.setHorizontalHeaderLabels(["ID", "X", "원문", "번역"])
        self.tab.setItemDelegateForColumn(
            3,
            MultilineDelegate(
                self.tab,
                shortcut_getter=self.get_special_shortcuts,
                linebreak_getter=self.get_linebreak_shortcut,
                enter_commit_callback=self._advance_table_editor_after_enter,
            )
        )
        self.tab.itemChanged.connect(self.on_table_item_changed)
        self.tab.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.tab.rowsReordered.connect(self.on_text_table_rows_reordered)
        # Text table is Excel-like: dragging selects cells only.  It must never
        # move/copy rows or trigger fill-handle-like behavior.
        self.tab.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.tab.setDragDropOverwriteMode(False)
        self.tab.setDragEnabled(False)
        self.tab.setAcceptDrops(False)
        self.tab.viewport().setAcceptDrops(False)
        self.tab.setDropIndicatorShown(False)
        self.tab.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self.on_table_context_menu)
        self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.tab.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tab.setStyleSheet(
            "QTableWidget { background:#171719; color:#E8E1E6; gridline-color:#2C282D; border:1px solid #293241; border-radius:0px; }"
            "QTableWidget::item { padding:3px 4px; }"
            "QTableWidget::item:selected { background:#8A4A52; color:#ffffff; }"
            "QTableWidget QTableCornerButton::section { background:#141416; border:1px solid #293241; }"
        )
        rl.addWidget(self.tab, 1)

        self.tab.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tab.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tab.setColumnWidth(0, 46)
        self.tab.setColumnWidth(1, 28)
        self.tab.setWordWrap(True)
        self.tab.verticalHeader().setVisible(False)
        self.tab.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)


        # 작업 로그는 하단에 작은 조작 막대를 두고, 막대의 버튼으로 접고 펼친다.
        # 버튼을 큰 빈 로그 영역 안에 띄우지 않도록 로그 본문과 조작 막대를 분리한다.
        self.log_panel = QWidget()
        self.log_panel.setObjectName("LogPanel")
        self.log_panel_layout = QVBoxLayout(self.log_panel)
        self.log_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.log_panel_layout.setSpacing(0)

        self.log_w = QTextEdit(self.log_panel)
        self.log_w.setFixedHeight(96)
        self.log_w.setReadOnly(True)
        self.log_w.setStyleSheet("background:#222;color:#0f0;")
        self.log_panel_layout.addWidget(self.log_w)

        self.log_footer = QWidget(self.log_panel)
        self.log_footer.setObjectName("LogPanelFooter")
        self.log_footer.setFixedHeight(30)
        log_footer_layout = QHBoxLayout(self.log_footer)
        log_footer_layout.setContentsMargins(8, 2, 4, 2)
        log_footer_layout.setSpacing(6)
        self.lbl_log_title = QLabel(self.tr_ui("작업 로그"), self.log_footer)
        self.lbl_log_title.setObjectName("LogPanelTitle")
        self.btn_log_toggle = QPushButton(self.log_footer)
        self.btn_log_toggle.setObjectName("LogPanelToggleButton")
        self.btn_log_toggle.setFixedHeight(24)
        self.btn_log_toggle.setMinimumWidth(96)
        self.btn_log_toggle.clicked.connect(self.toggle_log_panel_collapsed)
        log_footer_layout.addWidget(self.lbl_log_title)
        # 로그 접기/열기 버튼은 로그 제목 바로 옆에 둔다.
        # 오른쪽 끝으로 밀면 실제 로그 조작 위치가 너무 멀어져 시선 이동이 커진다.
        log_footer_layout.addWidget(self.btn_log_toggle)
        log_footer_layout.addStretch(1)
        self.log_panel_layout.addWidget(self.log_footer)
        self.log_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        rl.addWidget(self.log_panel)
        self.refresh_log_panel_state(save=False)
        self.flush_pending_log_messages()
        split.setSizes([900, 900])

        self.cb_text_preset.currentIndexChanged.connect(self.on_text_preset_selected)
        self.btn_preset_save.clicked.connect(self.save_text_preset_named)
        self.btn_preset_import.clicked.connect(self.import_text_preset_json)
        self.btn_preset_apply_page.clicked.connect(self.apply_current_preset_to_current_page_safe)
        self.btn_preset_apply_all.clicked.connect(self.apply_current_preset_to_all_pages)

        # 텍스트 스타일 UI는 쯔꾸르붕이에서 생성하지 않으므로 연결할 시그널도 없다.

        if hasattr(self, "final_item_font") and self.final_item_font is not None:
            self.final_item_font.currentFontChanged.connect(self.on_final_item_style_changed)
        if hasattr(self, "final_item_size") and self.final_item_size is not None:
            self.final_item_size.valueChanged.connect(self.on_final_item_style_changed)
        if hasattr(self, "final_item_stroke") and self.final_item_stroke is not None:
            self.final_item_stroke.valueChanged.connect(self.on_final_item_style_changed)
        if hasattr(self, "btn_item_text_color") and self.btn_item_text_color is not None:
            self.btn_item_text_color.clicked.connect(self.make_safe_slot(self.pick_color, "item_text"))
        if hasattr(self, "btn_item_stroke_color") and self.btn_item_stroke_color is not None:
            self.btn_item_stroke_color.clicked.connect(self.make_safe_slot(self.pick_color, "item_stroke"))
        if hasattr(self, "btn_item_align_left") and self.btn_item_align_left is not None:
            self.btn_item_align_left.clicked.connect(self.make_safe_slot(self.apply_style_to_selected, align="left"))
        if hasattr(self, "btn_item_align_center") and self.btn_item_align_center is not None:
            self.btn_item_align_center.clicked.connect(self.make_safe_slot(self.apply_style_to_selected, align="center"))
        if hasattr(self, "btn_item_align_right") and self.btn_item_align_right is not None:
            self.btn_item_align_right.clicked.connect(self.make_safe_slot(self.apply_style_to_selected, align="right"))
        if hasattr(self, "sb_text_opacity") and self.sb_text_opacity is not None:
            self.sb_text_opacity.valueChanged.connect(self.on_text_opacity_changed)
        if hasattr(self, "btn_text_effect_gradient") and self.btn_text_effect_gradient is not None:
            self.btn_text_effect_gradient.clicked.connect(self.open_selected_text_gradient_dialog)
        if hasattr(self, "btn_text_effect_transform") and self.btn_text_effect_transform is not None:
            self.btn_text_effect_transform.clicked.connect(self.toggle_selected_text_transform_quick)
        if hasattr(self, "btn_text_effect_skew") and self.btn_text_effect_skew is not None:
            self.btn_text_effect_skew.clicked.connect(self.toggle_selected_text_skew_quick)
        if hasattr(self, "btn_text_effect_trapezoid") and self.btn_text_effect_trapezoid is not None:
            self.btn_text_effect_trapezoid.clicked.connect(self.toggle_selected_text_trapezoid_quick)
        if hasattr(self, "btn_text_effect_arc") and self.btn_text_effect_arc is not None:
            self.btn_text_effect_arc.clicked.connect(self.toggle_selected_text_arc_quick)
        if hasattr(self, "btn_text_effect_rasterize") and self.btn_text_effect_rasterize is not None:
            self.btn_text_effect_rasterize.clicked.connect(self.rasterize_selected_text_quick)

        # G단계: 툴바 버튼/작업 콤보는 클릭용 컨트롤이다.
        # 스타일 버튼을 누른 뒤 포커스가 OCR 언어 콤보로 튀면 휠/키 입력이
        # 엉뚱한 곳에 먹으므로, 작업 캔버스 포커스를 빼앗지 않게 한다.
        for _focus_widget in (
            getattr(self, 'btn_align_left', None), getattr(self, 'btn_align_center', None), getattr(self, 'btn_align_right', None),
            getattr(self, 'btn_bold', None), getattr(self, 'btn_italic', None), getattr(self, 'btn_strike', None),
            getattr(self, 'btn_text_color', None), getattr(self, 'btn_stroke_color', None),
            getattr(self, 'btn_translate', None), getattr(self, 'btn_maker_preview_refresh', None), getattr(self, 'btn_inpaint', None), getattr(self, 'btn_text_cleanup', None),
            getattr(self, 'cb_ocr_language', None), getattr(self, 'cb_trans_provider', None), getattr(self, 'cb_show_final_text', None),
            getattr(self, 'btn_item_text_color', None), getattr(self, 'btn_item_stroke_color', None),
            getattr(self, 'btn_item_align_left', None), getattr(self, 'btn_item_align_center', None), getattr(self, 'btn_item_align_right', None),
            getattr(self, 'btn_text_effect_gradient', None), getattr(self, 'btn_text_effect_transform', None),
            getattr(self, 'btn_text_effect_skew', None), getattr(self, 'btn_text_effect_trapezoid', None),
            getattr(self, 'btn_text_effect_arc', None), getattr(self, 'btn_text_effect_rasterize', None),
        ):
            try:
                if _focus_widget is not None:
                    _focus_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            except Exception:
                pass

        self.page_required_widgets = [
            getattr(self, 'view', None), getattr(self, 'btn_prev_page', None), getattr(self, 'btn_next_page', None),
            getattr(self, 'btn_page', None), getattr(self, 'cb_trans_provider', None), getattr(self, 'btn_translate', None),
            getattr(self, 'btn_maker_preview_refresh', None),
            getattr(self, 'tab', None), getattr(self, 'page_tab_bar', None), getattr(self, 'btn_page_tab_menu', None),
        ]
        self.page_required_action_keys = [
            'work_translate', 'work_refresh_maker_preview', 'work_text_find', 'work_text_replace', 'work_unify_translations',
            'batch_translate', 'work_page_prev', 'work_page_next', 'work_page_list', 'work_page_full_name',
        ]
        self.update_color_button_styles()
        self.update_text_style_control_state([])
        self.update_page_presence_interlocks()
        self.install_main_input_enter_escape_filters()
        self.apply_maker_preview_ui_cleanup()
        try:
            self.configure_stable_numeric_inputs()
        except Exception:
            pass
        try:
            self.configure_live_text_numeric_inputs()
        except Exception:
            pass

    def apply_maker_preview_ui_cleanup(self):
        """쯔꾸르붕이 프리뷰 전용 UI 정리.

        기능 파일과 내부 함수는 아직 보존하되, 이미지 편집/식질 전용 UI는 사용자 화면에서 제거한다.
        """
        self.maker_ui_cleanup_enabled = True
        self.tktool_phase1_enabled = True  # legacy flag compatibility
        self.tktool_phase2_enabled = True  # legacy flag compatibility

        # 작업 탭은 최종결과만 내부 기준으로 고정하고, 사용자 UI에서는 숨긴다.
        try:
            if hasattr(self, "cb_mode") and self.cb_mode is not None:
                self.cb_mode.blockSignals(True)
                try:
                    if self.cb_mode.count() >= 5:
                        self.cb_mode.setCurrentIndex(4)
                    elif self.cb_mode.count() > 0:
                        self.cb_mode.setCurrentIndex(self.cb_mode.count() - 1)
                finally:
                    self.cb_mode.blockSignals(False)
                self.cb_mode.hide()
        except Exception:
            pass

        # 좌측 이미지 편집 툴바와 보조 옵션바 제거.
        for name in (
            "tb", "shared_option_bar", "final_edit_bar", "final_paint_option_bar", "area_paint_bar",
            "magic_wand_bar", "mask_wrap_bar", "mask_cut_bar", "ocr_region_bar", "source_compare_bar",
            "source_compare_view", "source_compare_controls", "cb_text_effect_preview",
        ):
            try:
                w = getattr(self, name, None)
                if w is not None:
                    w.hide()
                    w.setVisible(False)
                    if name == "tb":
                        w.setEnabled(False)
                        w.setFixedWidth(0)
                    if name == "shared_option_bar":
                        try:
                            w.setFixedHeight(0)
                            w.setMaximumHeight(0)
                        except Exception:
                            pass
            except Exception:
                pass

        # 상단 이미지 작업 버튼 제거. 맵 이동/대사 표/번역만 남긴다.
        for name in (
            "btn_reanalyze", "btn_analyze", "btn_export_result", "btn_text_cleanup", "btn_inpaint",
            "cb_ocr_language", "cb_show_final_text",
        ):
            try:
                w = getattr(self, name, None)
                if w is not None:
                    w.hide()
                    w.setVisible(False)
                    w.setEnabled(False)
            except Exception:
                pass

        # 우측 식질 보조 버튼 제거. 번역 엔진/번역 버튼/대사표/로그만 남긴다.
        for name in (
            "right_misc_title", "right_misc_line_widget",
        ):
            try:
                w = getattr(self, name, None)
                if w is not None:
                    w.hide()
                    w.setVisible(False)
            except Exception:
                pass

        try:
            self.update_paint_toolbar_visibility()
        except Exception:
            pass

    def apply_tktool_phase1_ui_cleanup(self):
        return self.apply_maker_preview_ui_cleanup()

    def _maker_project_has_imported_game(self):
        """현재 작업 폴더에 이미 RPG Maker 게임이 들어왔는지 확인한다."""
        try:
            project_dir = Path(str(getattr(self, "project_dir", "") or ""))
        except Exception:
            project_dir = None
        try:
            if project_dir and str(project_dir) and (project_dir / "maker_game").exists():
                return True
        except Exception:
            pass
        try:
            if bool(getattr(self, "paths", []) or []):
                return True
        except Exception:
            pass
        try:
            data = getattr(self, "data", {}) or {}
            for page in data.values() if isinstance(data, dict) else []:
                if isinstance(page, dict) and isinstance(page.get("maker_page"), dict):
                    return True
        except Exception:
            pass
        return False

    def _maker_project_menu_can_show_game_import(self):
        """게임 가져오기 메뉴는 홈화면이 아니라 열린 프로젝트/에디터 화면에서만 보인다."""
        try:
            has_project = bool(self.has_open_project())
        except Exception:
            has_project = bool(getattr(self, "project_dir", "") or "")
        try:
            in_editor = (
                hasattr(self, "main_stack")
                and hasattr(self, "editor_widget")
                and self.main_stack.currentWidget() is self.editor_widget
            )
        except Exception:
            in_editor = False
        return bool(has_project and in_editor)

    def _maker_can_import_game_into_current_project(self):
        """게임 가져오기는 열린 프로젝트 안에서 아직 게임이 없을 때만 실행 가능하다."""
        return bool(
            self._maker_project_menu_can_show_game_import()
            and not self._maker_project_has_imported_game()
        )

    def sync_maker_project_action_states(self):
        """프로젝트 상태에 맞춰 게임 가져오기 노출/실행 가능 여부를 동기화한다.

        메뉴 항목은 '홈화면에서는 숨김 / 열린 프로젝트에서는 표시'가 기준이고,
        실제 실행 가능 여부만 '아직 게임을 가져오지 않았는가'로 제한한다.
        """
        can_show_import = self._maker_project_menu_can_show_game_import()
        can_execute_import = bool(can_show_import and not self._maker_project_has_imported_game())
        for key in ("project_import_maker_game", "project_import_images"):
            try:
                action = (getattr(self, "actions", {}) or {}).get(key)
                if action is not None:
                    action.setVisible(can_show_import)
                    action.setEnabled(can_execute_import)
            except Exception:
                pass
        try:
            btn = getattr(self, "btn_page_add", None)
            if btn is not None:
                btn.setVisible(can_execute_import)
                btn.setEnabled(can_execute_import)
        except Exception:
            pass
        return can_execute_import

    def _ensure_maker_db_menu(self):
        """DB번역 메뉴를 옵션 앞에 둔다. 기존 메뉴가 없으면 생성한다."""
        try:
            menubar = self.menuBar()
        except Exception:
            return getattr(self, "db_menu", None)
        db_menu = getattr(self, "db_menu", None)
        if db_menu is not None:
            try:
                db_menu.setTitle(self.tr_ui("DB번역"))
            except Exception:
                pass
            return db_menu
        try:
            option_menu = getattr(self, "option_menu", None)
            if option_menu is not None:
                db_menu = QMenu(self.tr_ui("DB번역"), self)
                menubar.insertMenu(option_menu.menuAction(), db_menu)
            else:
                db_menu = menubar.addMenu(self.tr_ui("DB번역"))
            self.db_menu = db_menu
            return db_menu
        except Exception:
            return None

    def rebuild_maker_top_menus(self):
        """쯔꾸르붕이 2단계 상단 메뉴 재배치."""
        try:
            self.sync_maker_project_action_states()
        except Exception:
            pass

        def add_if(menu, key):
            try:
                action = (getattr(self, "actions", {}) or {}).get(key)
                if action is not None:
                    menu.addAction(action)
            except Exception:
                pass

        def sep(menu):
            try:
                menu.addSeparator()
            except Exception:
                pass

        try:
            m = getattr(self, "project_menu", None)
            if m is not None:
                m.clear()
                add_if(m, "project_new")
                add_if(m, "project_import_maker_game")
                add_if(m, "project_open_json")
                add_if(m, "project_open")
                sep(m)
                add_if(m, "project_save")
                sep(m)
                add_if(m, "project_recover_last_work")
                sep(m)
                add_if(m, "project_show_launcher")
                add_if(m, "project_exit")
                sep(m)
                add_if(m, "option_settings_overview")
        except Exception:
            pass

        try:
            m = getattr(self, "work_menu", None)
            if m is not None:
                m.clear()
                add_if(m, "work_translate")
                add_if(m, "work_restore_edge_control_codes_current")
                sep(m)
                add_if(m, "work_text_find")
                add_if(m, "work_text_replace")
                sep(m)
                add_if(m, "work_extract_text")
                add_if(m, "work_import_translation")
                add_if(m, "work_clear_translation")
                sep(m)
                add_if(m, "work_open_current_project_folder")
        except Exception:
            pass

        try:
            m = getattr(self, "batch_menu", None)
            if m is not None:
                m.clear()
                add_if(m, "batch_translate")
                add_if(m, "work_unify_translations")
                add_if(m, "batch_restore_edge_control_codes")
                sep(m)
                add_if(m, "batch_extract_text")
        except Exception:
            pass

        try:
            m = self._ensure_maker_db_menu()
            if m is not None:
                m.clear()
                add_if(m, "option_maker_database_translation")
                add_if(m, "db_maker_character_name_translation")
        except Exception:
            pass

        for attr in ("auto_menu",):
            try:
                m = getattr(self, attr, None)
                if m is not None:
                    m.clear()
                    m.menuAction().setVisible(False)
                    m.menuAction().setEnabled(False)
            except Exception:
                pass

        try:
            m = getattr(self, "option_menu", None)
            if m is not None:
                m.clear()
                add_if(m, "option_api_settings")
                sep(m)
                add_if(m, "option_shortcut_settings")
                add_if(m, "option_macro_settings")
                sep(m)
                add_if(m, "project_maker_character_profiles")
                add_if(m, "option_maker_character_prompts")
                add_if(m, "option_glossary")
                sep(m)
                add_if(m, "option_maker_translation_settings")
                add_if(m, "option_maker_preview_display_settings")
                add_if(m, "option_maker_game_settings")
                add_if(m, "option_maker_game_refresh")
        except Exception:
            pass

        try:
            m = getattr(self, "settings_menu", None)
            if m is not None:
                m.clear()
                add_if(m, "setting_interface_tooltips")
                sep(m)
                add_if(m, "option_theme_settings")
                add_if(m, "option_language_settings")
                add_if(m, "setting_page_tab_display_name")
                sep(m)
                add_if(m, "option_workspace_location")
                # removed: option_workspace_reset_default
                add_if(m, "option_cleanup_temp_files")
                add_if(m, "option_workspace_size_manager")
                sep(m)
                add_if(m, "option_register_ysb")
                add_if(m, "option_unregister_ysbt")
                add_if(m, "setting_file_path_visibility")
        except Exception:
            pass

        try:
            m = getattr(self, "help_menu", None)
            if m is not None:
                m.clear()
                add_if(m, "help_program_manual")
                add_if(m, "help_open_website")
                add_if(m, "help_report_bug")
                sep(m)
                add_if(m, "help_about")
        except Exception:
            pass

        try:
            self.sync_maker_project_action_states()
        except Exception:
            pass

    def apply_maker_legacy_menu_cleanup(self):
        """구버전 이름 호환용. 실제 메뉴 구성은 rebuild_maker_top_menus가 담당한다."""
        return self.rebuild_maker_top_menus()

    def apply_maker_menu_cleanup(self):
        """쯔꾸르붕이 정식 메뉴 정리."""
        self.maker_action_cleanup_enabled = True
        self.tktool_phase2_enabled = True  # legacy flag compatibility
        try:
            if hasattr(self, "apply_maker_action_cleanup"):
                self.apply_maker_action_cleanup()
        except Exception:
            pass
        return self.rebuild_maker_top_menus()

    def apply_tktool_phase1_menu_cleanup(self):
        return self.apply_maker_legacy_menu_cleanup()

    def apply_tktool_phase2_menu_cleanup(self):
        return self.apply_maker_menu_cleanup()

    def toggle_log_panel_collapsed(self):
        self.set_log_panel_collapsed(not bool(getattr(self, "log_panel_collapsed", False)), save=True)

    def set_log_panel_collapsed(self, collapsed, save=True):
        self.log_panel_collapsed = bool(collapsed)
        self.refresh_log_panel_state(save=save)

    def refresh_log_panel_state(self, save=False):
        collapsed = bool(getattr(self, "log_panel_collapsed", False))
        try:
            if hasattr(self, "log_w") and self.log_w is not None:
                self.log_w.setVisible(not collapsed)
            if hasattr(self, "log_panel") and self.log_panel is not None:
                self.log_panel.setFixedHeight(30 if collapsed else 126)
        except Exception:
            pass
        try:
            if hasattr(self, "lbl_log_title") and self.lbl_log_title is not None:
                self.lbl_log_title.setText(self.tr_ui("작업 로그"))
            if hasattr(self, "btn_log_toggle") and self.btn_log_toggle is not None:
                if collapsed:
                    self.btn_log_toggle.setText("▲ " + self.tr_ui("로그 열기"))
                    self.btn_log_toggle.setToolTip(self.tr_ui("숨긴 작업 로그를 다시 엽니다."))
                else:
                    self.btn_log_toggle.setText("— " + self.tr_ui("로그 숨기기"))
                    self.btn_log_toggle.setToolTip(self.tr_ui("작업 로그를 아래 막대로 접습니다."))
        except Exception:
            pass
        try:
            self.apply_log_panel_theme()
        except Exception:
            pass
        if save:
            try:
                self.app_options[LOG_PANEL_COLLAPSED_KEY] = collapsed
                self.save_app_options_cache()
            except Exception:
                pass

    def apply_log_panel_theme(self):
        light = self.is_light_theme() if hasattr(self, "is_light_theme") else False
        if light:
            panel_style = "QWidget#LogPanel { background:#ffffff; border:1px solid #DED8DC; border-radius:0px; }"
            header_style = "QWidget#LogPanelFooter { background:#F1ECEF; border:0; border-top:1px solid #DED8DC; }"
            title_style = "color:#374151; font-weight:700;"
            button_style = (
                "QPushButton#LogPanelToggleButton { background:#FAF5F7; color:#374151; border:1px solid #D1C9CE; "
                "border-radius:0px; padding:2px 8px; font-weight:700; }"
                "QPushButton#LogPanelToggleButton:hover { background:#FBF5F6; border-color:#D7A3A9; }"
            )
            log_style = "background:#ffffff;color:#25704a;border:0;border-radius:0px;"
        else:
            panel_style = "QWidget#LogPanel { background:#101113; border:1px solid #2E2A30; border-radius:0px; }"
            header_style = "QWidget#LogPanelFooter { background:#171719; border:0; border-top:1px solid #2E2A30; }"
            title_style = "color:#CBC4C9; font-weight:700;"
            button_style = (
                "QPushButton#LogPanelToggleButton { background:#28262B; color:#E0DADF; border:1px solid #3A363B; "
                "border-radius:0px; padding:2px 8px; font-weight:700; }"
                "QPushButton#LogPanelToggleButton:hover { background:#332B30; border-color:#665A62; }"
            )
            log_style = "background:#101113;color:#8fd8a8;border:0;border-radius:0px;"
        try:
            if hasattr(self, "log_panel") and self.log_panel is not None:
                self.log_panel.setStyleSheet(panel_style)
            if hasattr(self, "log_footer") and self.log_footer is not None:
                self.log_footer.setStyleSheet(header_style)
            if hasattr(self, "log_header") and self.log_header is not None:
                self.log_header.setStyleSheet(header_style)
            if hasattr(self, "lbl_log_title") and self.lbl_log_title is not None:
                self.lbl_log_title.setStyleSheet(title_style)
            if hasattr(self, "btn_log_toggle") and self.btn_log_toggle is not None:
                self.btn_log_toggle.setStyleSheet(button_style)
            if hasattr(self, "log_w") and self.log_w is not None:
                self.log_w.setStyleSheet(log_style)
        except Exception:
            pass

    def shortcut_text_for_key(self, key, fallback=""):
        try:
            seq = self.shortcut_settings.seq(key)
            if seq and not seq.isEmpty():
                txt = seq.toString(QKeySequence.SequenceFormat.NativeText)
                return txt or fallback
        except Exception:
            pass
        return fallback

    def set_dialog_control_tooltip(self, widget, title, key="", desc=""):
        if widget is None:
            return
        shortcut = self.shortcut_text_for_key(key, "") if key else ""
        parts = [self.tr_ui(title)]
        if shortcut:
            parts.append(shortcut)
        if desc:
            parts.append(self.tr_msg(desc))
        text = "\n".join(parts)
        try:
            widget.setToolTip(text)
            # 메인윈도우는 QApplication 전역 eventFilter로 native tooltip을 막는다.
            # 프리셋/설정 대화상자 컨트롤은 native tooltip을 허용해야 창 위에서 바로 보인다.
            widget.setProperty("allow_native_tooltip", True)
            try:
                for child in widget.findChildren(QWidget):
                    child.setToolTip(text)
                    child.setProperty("allow_native_tooltip", True)
            except Exception:
                pass
        except Exception:
            pass

    def focus_dialog_control(self, widget):
        if widget is None:
            return
        try:
            widget.setFocus()
            if hasattr(widget, "selectAll"):
                widget.selectAll()
            elif hasattr(widget, "lineEdit") and widget.lineEdit() is not None:
                widget.lineEdit().selectAll()
        except Exception:
            pass

    def add_dialog_shortcut(self, dialog, key, callback):
        try:
            seq = self.shortcut_settings.seq(key)
        except Exception:
            seq = QKeySequence()
        if not seq or seq.isEmpty():
            return None
        sc = QShortcut(seq, dialog)
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.activated.connect(callback)
        if not hasattr(dialog, "_ysb_style_shortcuts"):
            dialog._ysb_style_shortcuts = []
        dialog._ysb_style_shortcuts.append(sc)
        return sc

    def apply_current_preset_to_current_page_safe(self, *signal_args):
        return self.apply_current_preset_to_page(self.idx, refresh=True)

    def install_style_editor_shortcuts(self, dialog, controls):
        """메인 인터페이스와 같은 글꼴 상세 단축키/툴팁을 프리셋 창에도 적용한다."""
        if not dialog or not controls:
            return

        if not hasattr(dialog, "_ysb_enter_commit_filter"):
            dialog._ysb_enter_commit_filter = EnterCommitFilter(parent_dialog=dialog, fallback_widget=dialog, parent=dialog)
        for _name, _widget in list(controls.items()):
            if _widget is None:
                continue
            try:
                _widget.installEventFilter(dialog._ysb_enter_commit_filter)
            except Exception:
                pass
            try:
                line = _widget.lineEdit()
                if line is not None:
                    line.installEventFilter(dialog._ysb_enter_commit_filter)
            except Exception:
                pass

        def open_font_selector():
            font_widget = controls.get("font")
            size_widget = controls.get("size")
            bold_widget = controls.get("bold")
            italic_widget = controls.get("italic")
            try:
                current_family = font_widget.currentFont().family()
            except Exception:
                current_family = ""
            try:
                current_size = int(size_widget.value())
            except Exception:
                current_size = 24
            dlg = FontSelectDialog(
                current_family=current_family,
                current_size=current_size,
                current_bold=bool(bold_widget.isChecked()) if bold_widget else False,
                current_italic=bool(italic_widget.isChecked()) if italic_widget else False,
                parent=self,
            )
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_font_family():
                if font_widget is not None:
                    font_widget.setCurrentFont(QFont(dlg.selected_font_family()))
                if bold_widget is not None:
                    bold_widget.setChecked(dlg.selected_is_bold())
                if italic_widget is not None:
                    italic_widget.setChecked(dlg.selected_is_italic())

        focus_map = {
            "text_font_size": ("size", "글꼴 크기", "현재 편집 중인 글자 크기 값을 선택합니다."),
            "text_stroke_size": ("stroke", "획 크기", "현재 편집 중인 외곽선 두께 값을 선택합니다."),
            "text_line_spacing": ("line_spacing", "행간", "줄과 줄 사이 간격 값을 선택합니다."),
            "text_letter_spacing": ("letter_spacing", "자간", "글자와 글자 사이 간격 값을 선택합니다."),
            "text_char_width": ("char_width", "너비", "문자의 가로 비율 값을 선택합니다."),
            "text_char_height": ("char_height", "높이", "문자의 세로 비율 값을 선택합니다."),
        }
        for key, (control_name, title, desc) in focus_map.items():
            widget = controls.get(control_name)
            self.set_dialog_control_tooltip(widget, title, key, desc)
            self.add_dialog_shortcut(dialog, key, self.make_safe_slot(self.focus_dialog_control, widget))

        toggle_map = {
            "text_bold_toggle": ("bold", "굵게"),
            "text_italic_toggle": ("italic", "기울이기"),
            "text_strike_toggle": ("strike", "취소선"),
        }
        for key, (control_name, title) in toggle_map.items():
            widget = controls.get(control_name)
            self.set_dialog_control_tooltip(widget, title, key, "")
            self.add_dialog_shortcut(dialog, key, self.make_safe_click_slot(widget))

        color_map = {
            "item_text_color": ("text_color", "문자 색상", "현재 편집 중인 문자 색상을 선택합니다."),
            "item_stroke_color": ("stroke_color", "획 색상", "현재 편집 중인 외곽선 색상을 선택합니다."),
        }
        for key, (control_name, title, desc) in color_map.items():
            widget = controls.get(control_name)
            self.set_dialog_control_tooltip(widget, title, key, desc)

        align_map = {
            "item_align_left": ("align_left", "왼쪽 정렬"),
            "item_align_center": ("align_center", "가운데 정렬"),
            "item_align_right": ("align_right", "오른쪽 정렬"),
        }
        for key, (control_name, title) in align_map.items():
            widget = controls.get(control_name)
            self.set_dialog_control_tooltip(widget, title, key, "")

        font_widget = controls.get("font")
        self.set_dialog_control_tooltip(font_widget, "글꼴 선택", "item_font_select", "전용 글꼴 선택창을 엽니다.")
        self.add_dialog_shortcut(dialog, "item_font_select", open_font_selector)

    def open_font_select_dialog(self):
        """전용 글꼴 선택 창을 열어 선택 텍스트 또는 기본 글꼴에 적용한다."""
        try:
            current_family = self.cb_font.currentFont().family()
        except Exception:
            current_family = ""
        try:
            current_size = int(self.sb_font_size.value())
        except Exception:
            current_size = 24
        try:
            current_bold = bool(self.btn_bold.isChecked())
            current_italic = bool(self.btn_italic.isChecked())
        except Exception:
            current_bold = False
            current_italic = False

        dlg = FontSelectDialog(
            current_family=current_family,
            current_size=current_size,
            current_bold=current_bold,
            current_italic=current_italic,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False

        family = dlg.selected_font_family()
        if not family:
            return False

        style_updates = {
            "font_family": family,
            "bold": dlg.selected_is_bold(),
            "italic": dlg.selected_is_italic(),
        }

        if self.cb_mode.currentIndex() == 4 and self.selected_text_items():
            self.apply_style_to_selected(**style_updates)
        else:
            self.cb_font.setCurrentFont(QFont(family))
            try:
                self.btn_bold.setChecked(bool(style_updates["bold"]))
                self.btn_italic.setChecked(bool(style_updates["italic"]))
            except Exception:
                pass
            self.on_global_text_style_changed()

        self.log((f"🔤 Font selected: {family} / {dlg.selected_font_style()}" if self.ui_language == LANG_EN else f"🔤 글꼴 선택: {family} / {dlg.selected_font_style()}"))
        return True

    def set_combo_current_data(self, combo, data):
        """QComboBox의 userData 값으로 현재 항목을 선택한다."""
        try:
            for i in range(combo.count()):
                if str(combo.itemData(i)) == str(data):
                    combo.setCurrentIndex(i)
                    return True
        except Exception:
            pass
        return False

    def tr_ui(self, text):
        return translate_ui_text(text, getattr(self, "ui_language", LANG_KO))

    def tr_msg(self, text):
        return translate_ui_dynamic_text(text, getattr(self, "ui_language", LANG_KO))

    def display_project_name(self):
        """창 제목에 표시할 현재 파일명.
        .ysbg 파일명은 사람이 보는 이름 그대로 두고, UUID는 내부 manifest/작업 폴더에서만 관리한다.
        구버전 이름_고유번호.ysbg 파일을 열었을 때만 표시용으로 뒤쪽 코드를 숨긴다.
        """
        name = ""
        try:
            if getattr(self, "ysbg_package_path", None):
                name = Path(self.ysbg_package_path).stem
            elif getattr(self, "suggested_project_name", None):
                name = str(self.suggested_project_name)
        except Exception:
            name = ""
        if not name:
            return ""
        name = re.sub(r"_[0-9a-fA-F]{8,12}$", "", name)
        return name

    def update_window_title(self):
        is_en = normalize_ui_language(getattr(self, "ui_language", current_ui_language())) == LANG_EN
        base_name = APP_NAME_EN if is_en else APP_NAME_KO
        base = f"{base_name} {APP_VERSION}"
        project_name = self.display_project_name()
        try:
            self.setWindowTitle(f"{base} - {project_name}" if project_name else base)
        except Exception:
            pass

    def split_uuid_suffix_from_name(self, name: str):
        stem = clean_workspace_name(name or "ysb_project")
        m = re.match(r"^(.*)_([0-9a-fA-F]{8,12})$", stem)
        if m:
            return clean_workspace_name(m.group(1) or stem), m.group(2).lower()
        return stem, None

    def make_ysbt_path_with_uuid_suffix(self, path: str, project_uuid: str | None = None):
        """사용자가 고른 .ysbg 경로를 확정한다.

        정책:
        - 파일명에는 UUID/YSBG 문구를 강제로 붙이지 않는다. 확장자만 .ysbg로 맞춘다.
        - 구형 이름_고유번호.ysbg를 저장할 때도 기존 ID를 누적/계승하지 않고 새 내부 UUID로 교체한다.
        - UUID는 패키지 manifest와 작업 폴더명에만 사용한다.
        """
        path = self.normalize_ysb_path(path)
        path_obj = Path(path)
        display_name, _existing_code = self.split_uuid_suffix_from_name(path_obj.stem)
        try:
            cleaned = re.sub(r"(?:[\s_-]+YSBG)$", "", str(display_name or ""), flags=re.IGNORECASE).strip(" _-. ")
            if cleaned:
                display_name = clean_workspace_name(cleaned)
        except Exception:
            pass
        final_uuid = str(project_uuid) if project_uuid else uuid.uuid4().hex
        clean_path = path_obj.with_name(safe_project_name(display_name or "ysb_project") + YSB_EXTENSION)
        return str(clean_path), display_name, final_uuid

    def translate_child_widgets(self, root_widget):
        """설정창/프리셋창처럼 나중에 생성되는 창의 고정 문구를 현재 언어로 바꾼다."""
        if root_widget is None:
            return
        try:
            for widget in root_widget.findChildren((QLabel, QPushButton, QCheckBox, QGroupBox, QRadioButton)):
                try:
                    txt = widget.text()
                except Exception:
                    continue
                if txt:
                    widget.setText(self.tr_msg(txt))
        except Exception:
            pass
        try:
            for combo in root_widget.findChildren(QComboBox):
                for i in range(combo.count()):
                    txt = combo.itemText(i)
                    if txt:
                        combo.setItemText(i, self.tr_msg(txt))
        except Exception:
            pass
        try:
            for spin in root_widget.findChildren(QSpinBox):
                if spin.specialValueText():
                    spin.setSpecialValueText(self.tr_ui(spin.specialValueText()))
        except Exception:
            pass
        try:
            for widget in root_widget.findChildren(QWidget):
                tip = widget.toolTip()
                if tip:
                    widget.setToolTip(self.tr_msg(tip))
        except Exception:
            pass

    def apply_language(self, language=None):
        """저장된 표시 언어를 메인 UI에 적용한다.
        사용자 원문/번역문 데이터는 건드리지 않고, 고정 UI 문구만 교체한다.
        """
        lang = normalize_ui_language(language or getattr(self, "ui_language", LANG_KO))
        self.ui_language = lang
        try:
            self.update_window_title()
        except Exception:
            pass

        # 메뉴 제목
        for attr, ko in (
            ("project_menu", "프로젝트"),
            ("work_menu", "작업"),
            ("batch_menu", "일괄 작업"),
            ("db_menu", "DB번역"),
            ("auto_menu", "자동화 작업"),
            ("settings_menu", "설정"),
            ("option_menu", "옵션"),
            ("help_menu", "도움말"),
        ):
            menu = getattr(self, attr, None)
            if menu is not None:
                try:
                    menu.setTitle(self.tr_ui(ko))
                except Exception:
                    pass

        action_ko = {
            "project_new": "새 프로젝트",
            "project_import_maker_game": "게임 가져오기",
            "project_import_images": "게임 가져오기(호환)",
            "project_maker_character_profiles": "캐릭터 프로필 보기",
            "project_open": "YSBG 열기",
            "project_open_json": "프로젝트 열기",
            "project_show_launcher": "홈화면으로 가기",
            "project_exit": "프로젝트 나가기",
            "project_save": "내보내기",
            "project_save_as": "다른 이름으로 내보내기(호환)",
            "project_recover_last_work": "복구하기",
            "option_settings_overview": "설정 / 옵션",
            "edit_undo": "텍스트 입력 취소",
            "edit_redo": "텍스트 입력 재실행",
            "paint_undo": "텍스트 입력 취소(호환)",
            "paint_redo": "텍스트 입력 재실행(호환)",
            "work_page_prev": "이전 맵",
            "work_page_next": "다음 맵",
            "work_page_list": "맵 목록",
            "work_page_full_name": "현재 맵 이름 보기",
            "work_page_rename_source": "맵 탭 이름 변경",
            "work_page_delete_current": "현재 페이지 탭 삭제",
            "work_page_delete_all": "일괄 페이지탭 삭제",
            "work_open_current_project_folder": "현재 프로젝트의 작업 폴더로 이동하기",
            "work_scan_maker_game": "게임 분석",
            "work_analyze": "분석(호환)",
            "paint_reanalyze": "재분석",
            "work_quick_ocr": "빠른 OCR 설정",
            "quick_ocr_execute": "빠른 OCR 실행",
            "work_text_number_width": "텍스트 넘버 크기 변경",
            "work_translate": "번역",
            "work_restore_edge_control_codes_current": "맵 제어코드 복원",
            "work_refresh_maker_preview": "프리뷰 갱신",
            "work_inpaint": "인페인팅",
            "work_import_clean_background": "클린본 불러오기",
            "work_inpaint_source": "배경을 원본으로 쓰기",
            "work_restore_original_source": "원본으로 돌아가기",
            "work_extract_text": "원문/번역문 내보내기",
            "work_import_translation": "번역문 불러오기",
            "work_clear_translation": "번역문 내용 지우기",
            "work_clean_text": "텍스트 정리",
            "work_text_find": "텍스트 찾기",
            "work_text_replace": "텍스트 교체",
            "work_unify_translations": "번역 통일",
            "work_reset_text_rects": "현재 텍스트 기준으로 영역 재설정",
            "work_export": "출력",
            "work_output_preview": "출력 미리보기",
            "batch_analyze": "일괄 분석",
            "batch_reanalyze": "일괄 재분석",
            "batch_translate": "일괄 번역",
            "batch_restore_edge_control_codes": "일괄 맵 제어코드 복원",
            "batch_inpaint": "일괄 인페인팅",
            "batch_extract_text": "일괄 원문/번역문 내보내기",
            "batch_clear_translation": "선택 맵 번역문 지우기",
            "batch_clean_text": "일괄 텍스트 정리",
            "batch_reset_text_rects": "일괄 현재 텍스트 기준으로 영역 재설정",
            "batch_export": "일괄 출력",
            "auto_text_size_current": "자동 텍스트 크기 조정",
            "auto_text_size_batch": "일괄 자동 텍스트 크기 조정",
            "auto_linebreak_current": "자동 줄 내림",
            "auto_linebreak_batch": "일괄 자동 줄 내림",
            "option_auto_save_mode": "자동저장 모드(폐지됨)",
            "option_theme_settings": "테마 설정",
            "option_language_settings": "언어 설정",
            "setting_page_tab_display_name": "맵 탭 표시명 설정",
            "setting_output_display_name": "출력 표시명 설정",
            "setting_output_options": "출력 옵션",
            "setting_interface_tooltips": "인터페이스 툴팁 표시",
            "setting_file_path_visibility": "파일 경로 표시",
            "option_api_settings": "API 관리",
            "option_translation_prompt": "공통 번역 프롬프트",
            "option_maker_character_prompts": "게임 프롬프트 관리",
            "option_maker_translation_settings": "줄내림 옵션",
            "option_maker_refresh_runtime_profile": "쯔꾸르 표시 환경 갱신",
            "option_glossary": "단어장",
            "option_analysis_mask_settings": "분석 마스크 확장 비율",
            "option_maker_preview_font_settings": "실제 게임 폰트 설정",
            "option_maker_game_font_settings": "실제 게임 폰트 설정",
            "option_maker_game_settings": "게임 설정",
            "option_maker_game_refresh": "게임 갱신",
            "option_maker_preview_display_settings": "게임 프리뷰 옵션",
            "option_maker_title_settings": "타이틀명 변경",
            "option_maker_terms_translation": "시스템 번역",
            "option_maker_database_translation": "데이터베이스 모드",
            "db_maker_character_name_translation": "화자 번역",
            "debug_maker_database_scan": "DB 스캔 진단",
            "debug_maker_database_layer_rebuild": "DB 레이어 생성 테스트",
            "debug_maker_tile_preview_diagnose": "타일 프리뷰 진단",
            "db_maker_plugin_translation": "플러그인 번역",
            "option_ocr_analysis_regions": "OCR 분석 범위 지정",
            "option_cleanup_outputs": "출력물 삭제",
            "option_workspace_location": "작업 폴더 위치 변경",
            "option_workspace_reset_default": "작업 폴더 위치 기본값으로 변경",
            "option_cleanup_temp_files": "사용자 데이터 및 임시파일 정리",
            "option_workspace_size_manager": "작업 폴더 용량 관리",
            "option_register_ysb": ".ysbg 확장자 연결 등록",
            "option_unregister_ysbt": ".ysbg 확장자 연결 해제",
            "option_shortcut_settings": "단축키 통합 관리",
            "option_macro_settings": "매크로 관리",
            "option_text_preset_settings": "페이지 글꼴 프리셋 관리",
            "option_item_text_preset_settings": "개별 글꼴 프리셋 관리",
            "help_program_manual": "프로그램 메뉴얼",
            "help_open_website": "YSB Game Editor 사이트로 가기",
            "help_report_bug": "버그제보 / 문의하기",
            "help_about": "프로그램 정보",
            "paint_magic_fill": "마스킹 칠하기",
            "paint_mask_wrap": "마스크 랩핑",
            "paint_mask_cut": "마스크 커팅",
            "paint_mask_wrap_rect": "마스크 선택 사각형",
            "paint_mask_wrap_free": "마스크 선택 자유형",
            "paint_mask_toggle": "마스크 ON/OFF",
            "view_text_toggle": "텍스트 표시 ON/OFF",
            "final_paint_color": "최종 페인팅 색상",
            "final_paint_to_background": "배경을 원본으로 쓰기",
            "final_text_tool": "최종 텍스트 도구",
            "final_paint_above_toggle": "텍스트 위 페인팅 ON/OFF",
            "final_paint_opacity_inc": "브러시 불투명도 증가",
            "final_paint_opacity_dec": "브러시 불투명도 감소",
        }
        for key, ko in action_ko.items():
            action = self.actions.get(key)
            if action is not None:
                try:
                    action.setText(self.tr_ui(ko))
                except Exception:
                    pass

        try:
            self.sync_interface_tooltips_action_state()
        except Exception:
            pass

        try:
            if hasattr(self, "launcher_widget"):
                self.launcher_widget.set_language(lang)
        except Exception:
            pass

        # 현재 생성된 고정 UI 위젯의 텍스트를 교체한다.
        widget_types = (QLabel, QPushButton, QCheckBox, QGroupBox, QRadioButton)
        for widget in self.findChildren(widget_types):
            try:
                txt = widget.text()
            except Exception:
                continue
            if txt:
                new_txt = self.tr_ui(txt)
                if new_txt != txt:
                    try:
                        widget.setText(new_txt)
                    except Exception:
                        pass

        # 우측 텍스트 표 헤더
        try:
            if hasattr(self, "tab"):
                maker_mode = bool(hasattr(self, "_is_current_maker_page") and self._is_current_maker_page())
                if maker_mode:
                    headers = [
                        "ID",
                        self.tr_ui("상태"),
                        self.tr_ui("화자"),
                        self.tr_ui("타입"),
                        self.tr_ui("이벤트"),
                        self.tr_ui("원문"),
                        self.tr_ui("번역문"),
                        self.tr_ui("메모"),
                    ]
                else:
                    headers = ["ID", "X", self.tr_ui("원문"), self.tr_ui("번역")]
                self.tab.setHorizontalHeaderLabels(headers)
                for row in (0,):
                    item = self.tab.item(row, 2 if not maker_mode else 5)
                    if item and item.text() in ("전체 선택", "Select All"):
                        item.setText(self.tr_ui("전체 선택"))
        except Exception:
            pass

        # 콤보박스 기본 항목
        try:
            if hasattr(self, "cb_text_preset"):
                for i in range(self.cb_text_preset.count()):
                    if self.cb_text_preset.itemData(i) == "__last__":
                        self.cb_text_preset.setItemText(i, self.tr_ui("마지막 설정"))
            if hasattr(self, "cb_item_text_preset"):
                for i in range(self.cb_item_text_preset.count()):
                    if self.cb_item_text_preset.itemData(i) == "__custom__":
                        self.cb_item_text_preset.setItemText(i, self.tr_ui("사용자지정"))
        except Exception:
            pass

        # 작업 탭/모드 콤보박스 항목
        try:
            if hasattr(self, "cb_mode"):
                mode_labels = ["1. 원본", "2. 분석도", "3. 텍스트 마스크", "4. 페인팅 마스크", "5. 최종결과"]
                cur = self.cb_mode.currentIndex()
                self.cb_mode.blockSignals(True)
                for i, ko in enumerate(mode_labels):
                    if i < self.cb_mode.count():
                        self.cb_mode.setItemText(i, self.tr_ui(ko))
                self.cb_mode.setCurrentIndex(cur)
                self.cb_mode.blockSignals(False)
        except Exception:
            try:
                self.cb_mode.blockSignals(False)
            except Exception:
                pass

        # 콤보박스 안의 기본 한국어 항목
        try:
            for combo in self.findChildren(QComboBox):
                for i in range(combo.count()):
                    txt = combo.itemText(i)
                    if txt:
                        new_txt = self.tr_ui(txt)
                        if new_txt != txt:
                            combo.setItemText(i, new_txt)
        except Exception:
            pass

        # 일부 위젯은 이모지/특수값 때문에 일반 순회 번역만으로는 바뀌지 않으므로 직접 보정한다.
        try:
            # 행간/자간은 수치 기반으로 표시한다. 행간 기본값은 100%, 자간 기본값은 0px.
            # QSpinBox specialValueText("자동")는 최솟값 전용이라 음수/기본값 UX와 충돌한다.
            if hasattr(self, "btn_analyze"):
                self.btn_analyze.setText(self.tr_ui("⚡ 분석"))
            if hasattr(self, "btn_mask_wrap_rect"):
                self.btn_mask_wrap_rect.setText(self.tr_ui("▭ 사각형"))
            if hasattr(self, "btn_mask_wrap_free"):
                self.btn_mask_wrap_free.setText(self.tr_ui("✎ 자유형"))
            if hasattr(self, "btn_mask_cut_rect"):
                self.btn_mask_cut_rect.setText(self.tr_ui("▭ 사각형"))
            if hasattr(self, "btn_mask_cut_free"):
                self.btn_mask_cut_free.setText(self.tr_ui("✎ 자유형"))
            if hasattr(self, "btn_area_paint_rect"):
                self.btn_area_paint_rect.setText(self.tr_ui("▭ 사각형"))
            if hasattr(self, "btn_area_paint_free"):
                self.btn_area_paint_free.setText(self.tr_ui("✎ 자유형"))
            if hasattr(self, "btn_magic_fill"):
                try:
                    mode = self.cb_mode.currentIndex() if hasattr(self, "cb_mode") else 2
                    self.btn_magic_fill.setText(self.tr_ui("영역 칠하기") if mode == 4 else self.tr_ui("마스킹 칠하기"))
                except Exception:
                    self.btn_magic_fill.setText(self.tr_ui("마스킹 칠하기"))
            if hasattr(self, "btn_translate"):
                self.btn_translate.setText(self.tr_ui("🌐 번역"))
            if hasattr(self, "lbl_maker_preview_refresh"):
                self.lbl_maker_preview_refresh.setText(self.tr_ui("프리뷰"))
            if hasattr(self, "btn_maker_preview_refresh"):
                self.btn_maker_preview_refresh.setText(self.tr_ui("프리뷰 갱신"))
            if hasattr(self, "btn_inpaint"):
                self.btn_inpaint.setText(self.tr_ui("🎨 인페인팅"))
            if hasattr(self, "btn_text_cleanup"):
                self.btn_text_cleanup.setText(self.tr_ui("🧹 텍스트 정리"))
            if hasattr(self, "btn_export_result"):
                self.btn_export_result.setText(self.tr_ui("📤 결과물 출력"))
            if hasattr(self, "sb_trans_chunk"):
                self.sb_trans_chunk.setSuffix(" items" if lang == LANG_EN else "개")
                self.sb_trans_chunk.setStatusTip(self.tr_msg("한 번의 API 요청에 묶어서 보낼 텍스트 줄 수"))
            if hasattr(self, "btn_project_exit"):
                self.btn_project_exit.setText(self.tr_ui("프로젝트 나가기"))
                seq = self.shortcut_settings.seq("project_exit").toString(QKeySequence.SequenceFormat.NativeText)
                self.btn_project_exit.setToolTip(self.native_tooltip_html("프로젝트 나가기", seq))
            if hasattr(self, "btn_page_tab_menu"):
                self.btn_page_tab_menu.setText("☰")
                seq = self.shortcut_settings.seq("work_page_list").toString(QKeySequence.SequenceFormat.NativeText)
                self.btn_page_tab_menu.setToolTip(self.native_tooltip_html("맵 목록", seq))
        except Exception:
            pass

        # 기본 툴팁 문구도 언어 설정에 맞춘다.
        try:
            for widget in self.findChildren(QWidget):
                tip = widget.toolTip()
                if tip:
                    new_tip = self.tr_ui(tip)
                    if new_tip != tip:
                        widget.setToolTip(new_tip)
        except Exception:
            pass

        try:
            self.refresh_log_panel_state(save=False)
        except Exception:
            pass

        try:
            self.configure_ui_tooltips()
        except Exception:
            pass

    def open_language_settings_dialog(self):
        """옵션 > 언어 설정."""
        old_language = normalize_ui_language(getattr(self, "ui_language", LANG_KO))

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr_ui("언어 설정"))
        dialog.resize(360, 160)
        layout = QVBoxLayout(dialog)

        label = QLabel(self.tr_ui("표시 언어를 선택하세요.\n확인을 누르면 즉시 적용되고, 닫기를 누르면 변경하지 않습니다."))
        label.setWordWrap(True)
        layout.addWidget(label)

        combo = QComboBox(dialog)
        combo.addItem(self.tr_ui("한국어"), LANG_KO)
        combo.addItem("English", LANG_EN)
        combo.setCurrentIndex(1 if old_language == LANG_EN else 0)
        layout.addWidget(combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("닫기"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setStyleSheet(self.settings_dialog_style())

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = normalize_ui_language(combo.currentData())
        self.ui_language = selected
        self.save_app_options_cache()
        self.apply_language(selected)
        self.log("🌐 Language changed: English" if selected == LANG_EN else "🌐 언어 변경: 한국어")

    def apply_theme(self, theme=None):
        """저장된 테마값에 따라 전체 UI 테마를 적용한다."""
        theme = str(theme or getattr(self, "ui_theme", THEME_DARK) or THEME_DARK).lower()
        if theme not in (THEME_DARK, THEME_LIGHT):
            theme = THEME_DARK
        self.ui_theme = theme
        if theme == THEME_LIGHT:
            self.apply_light_theme()
        else:
            self.apply_dark_theme()
        try:
            if hasattr(self, "launcher_widget"):
                self.launcher_widget.set_theme(theme)
        except Exception:
            pass
        self.force_theme_repaint_after_apply()

    def refresh_top_bars_for_theme(self):
        """Qt 내부 상단 영역만 현재 테마에 맞춘다.
        Windows 네이티브 제목 표시줄은 건드리지 않는다. 네이티브 프레임을 강제로
        다시 그리면 최소화/복원/전체화면 전환 뒤 포커스와 입력 상태가 꼬일 수 있다.
        """
        light = self.is_light_theme()
        try:
            mb = self.menuBar()
            if mb is not None:
                if light:
                    mb.setStyleSheet(
                        "QMenuBar { background-color:#ffffff; color:#242329; border-bottom:1px solid #E3DDE1; padding:2px 4px; }"
                        "QMenuBar::item { background:transparent; padding:6px 10px; border-radius:0px; }"
                        "QMenuBar::item:selected { background:#FBF5F6; color:#111827; }"
                    )
                else:
                    mb.setStyleSheet(
                        "QMenuBar { background-color:#101113; color:#E0DADF; border-bottom:1px solid #2E2A30; padding:2px 4px; }"
                        "QMenuBar::item { background:transparent; padding:6px 10px; border-radius:0px; }"
                        "QMenuBar::item:selected { background:#28262B; color:#ffffff; }"
                    )
                mb.update()
        except Exception:
            pass

        try:
            self.apply_project_exit_button_theme()
        except Exception:
            pass

        try:
            self.apply_log_panel_theme()
        except Exception:
            pass

    def force_theme_repaint_after_apply(self):
        # 안전 원칙: 테마 적용은 1회만 수행한다.
        # 지연 타이머, processEvents, activateWindow/raise_, 네이티브 프레임 Redraw는 사용하지 않는다.
        self.refresh_top_bars_for_theme()
        try:
            self.update()
        except Exception:
            pass

    def open_theme_settings_dialog(self):
        """옵션 > 테마 설정."""
        old_theme = str(getattr(self, "ui_theme", THEME_DARK) or THEME_DARK).lower()
        if old_theme not in (THEME_DARK, THEME_LIGHT):
            old_theme = THEME_DARK

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr_ui("테마 설정"))
        dialog.resize(360, 170)
        layout = QVBoxLayout(dialog)

        label = QLabel(self.tr_ui("화면에 적용할 테마를 선택하세요.\n확인을 누르면 즉시 적용되고, 닫기를 누르면 변경하지 않습니다."))
        label.setWordWrap(True)
        layout.addWidget(label)

        combo = QComboBox(dialog)
        combo.addItem(self.tr_ui("다크 테마"), THEME_DARK)
        combo.addItem(self.tr_ui("화이트 테마"), THEME_LIGHT)
        combo.setCurrentIndex(0 if old_theme == THEME_DARK else 1)
        layout.addWidget(combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_ui("확인"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_ui("닫기"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # 현재 테마에 맞춰 설정창도 어색하지 않게 표시한다.
        if old_theme == THEME_LIGHT:
            dialog.setStyleSheet("""
                QDialog { background:#f6f7f9; color:#202124; }
                QLabel { color:#202124; }
                QComboBox { background:#ffffff; color:#202124; border:1px solid #b9bec7; padding:4px; }
                QPushButton { background:#ffffff; color:#202124; border:1px solid #B2ABB0; padding:5px 14px; }
                QPushButton:hover { background:#e9eef7; }
            """)
        else:
            dialog.setStyleSheet("""
                QDialog { background:#1f1f22; color:#f2f2f2; }
                QLabel { color:#f2f2f2; }
                QComboBox { background:#2d2f34; color:#f5f5f5; border:1px solid #53565f; padding:4px; }
                QPushButton { background:#383238; color:#f2f2f2; border:1px solid #625C63; padding:5px 14px; }
                QPushButton:hover { background:#454047; }
            """)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = str(combo.currentData() or THEME_DARK)
        if selected not in (THEME_DARK, THEME_LIGHT):
            selected = THEME_DARK
        self.ui_theme = selected
        self.save_app_options_cache()
        self.apply_theme(selected)
        self.log(f"🎨 테마 변경: {'화이트 테마' if selected == THEME_LIGHT else '다크 테마'}")

    def themed_action_button_style(self, kind="primary"):
        light = self.is_light_theme() if hasattr(self, "is_light_theme") else False
        if light:
            if kind == "primary":
                return (
                    "QPushButton { background:#F5E8EA; color:#5B3136; border:1px solid #D7A3A9; border-radius:0px; padding:4px 10px; }"
                    "QPushButton:hover { background:#EEDBDE; border-color:#C78A90; }"
                    "QPushButton:pressed { background:#E6D0D4; border-color:#A85D66; }"
                    "QPushButton:disabled { background:#F2F3F5; color:#B3ACB2; border-color:#DED8DC; }"
                )
            return (
                "QPushButton { background:#FFFFFF; color:#374151; border:1px solid #DED8DC; border-radius:0px; padding:4px 10px; }"
                "QPushButton:hover { background:#FBF5F6; border-color:#D7A3A9; }"
                "QPushButton:pressed { background:#F5E8EA; border-color:#C78A90; }"
                "QPushButton:disabled { background:#F2F3F5; color:#B3ACB2; border-color:#DED8DC; }"
            )
        if kind == "primary":
            return (
                "QPushButton { background:#8A4A52; color:#FFFFFF; border:1px solid #A85D66; border-radius:0px; padding:4px 10px; }"
                "QPushButton:hover { background:#A85D66; border-color:#C78A90; }"
                "QPushButton:pressed { background:#6F3940; border-color:#C78A90; }"
                "QPushButton:disabled { background:#252328; color:#827A80; border-color:#555056; }"
            )
        return (
            "QPushButton { background:#211F23; color:#E0DADF; border:1px solid #555056; border-radius:0px; padding:4px 10px; }"
            "QPushButton:hover { background:#2A2E35; border-color:#8A4A52; }"
            "QPushButton:pressed { background:#171719; border-color:#A85D66; }"
            "QPushButton:disabled { background:#252328; color:#827A80; border-color:#555056; }"
        )

    def apply_action_button_theme_styles(self):
        try:
            # 특수색(파랑/초록)을 제거하고, 현재 테마의 공통 색 체계를 따른다.
            if hasattr(self, "btn_analyze") and self.btn_analyze:
                self.btn_analyze.setStyleSheet(self.themed_action_button_style("primary"))
            if hasattr(self, "btn_inpaint") and self.btn_inpaint:
                self.btn_inpaint.setStyleSheet(self.themed_action_button_style("primary"))
            if hasattr(self, "btn_export_result") and self.btn_export_result:
                self.btn_export_result.setStyleSheet(self.themed_action_button_style("primary"))
            if hasattr(self, "btn_reanalyze") and self.btn_reanalyze:
                self.btn_reanalyze.setStyleSheet(self.themed_action_button_style("secondary"))
            if hasattr(self, "btn_text_cleanup") and self.btn_text_cleanup:
                self.btn_text_cleanup.setStyleSheet(self.themed_action_button_style("secondary"))
        except Exception:
            pass

    def apply_native_title_bar_theme(self, widget=None, dark=None):
        """Windows 네이티브 제목 표시줄 테마 적용은 공개판에서 비활성화한다.

        DwmSetWindowAttribute/SetWindowPos/RedrawWindow 같은 비클라이언트 영역 갱신은
        Windows와 Qt의 포커스 이벤트를 계속 흔들 수 있다. 색상 일치보다 입력 안정성을
        우선하므로 제목 표시줄은 OS 기본 동작에 맡긴다.
        """
        return

    def schedule_native_title_bar_theme(self, widget=None, dark=None):
        """네이티브 제목 표시줄 지연 갱신 비활성화.
        최소화/복원/전체화면 전환 뒤 버벅임과 먹통을 막기 위해 아무 작업도 하지 않는다.
        """
        return

    def apply_tooltip_theme(self, light=None):
        """QToolTip은 OS/Qt 기본 팔레트 영향을 많이 받아 글자색이 흐려질 수 있다.
        테마 적용 시마다 팔레트와 앱 스타일시트를 같이 고정해 대비를 보장한다.
        """
        if light is None:
            light = self.is_light_theme() if hasattr(self, "is_light_theme") else False

        app = QApplication.instance()
        if light:
            bg = QColor("#ffffff")
            fg = QColor("#111827")
            border = "#D1C9CE"
        else:
            bg = QColor("#242329")
            fg = QColor("#ffffff")
            border = "#555056"

        pal = QPalette()
        pal.setColor(QPalette.ColorRole.ToolTipBase, bg)
        pal.setColor(QPalette.ColorRole.ToolTipText, fg)
        try:
            QToolTip.setPalette(pal)
        except Exception:
            pass

        if app:
            try:
                app.setStyleSheet(
                    "QToolTip { "
                    f"background-color:{bg.name()}; "
                    f"color:{fg.name()}; "
                    f"border:1px solid {border}; "
                    "border-radius:0px; "
                    "padding:5px; "
                    "}"
                )
            except Exception:
                pass

    def apply_light_theme(self):
        """화이트 테마를 부드러운 카드형 톤으로 적용한다."""
        app = QApplication.instance()
        if app:
            app.setStyleSheet("""
                QToolTip { background-color:#ffffff; color:#111827; border:1px solid #D1C9CE; border-radius:0px; padding:5px; }
            """)
            pal = QPalette()
            pal.setColor(QPalette.ColorRole.Window, QColor("#F5EFF3"))
            pal.setColor(QPalette.ColorRole.WindowText, QColor("#242329"))
            pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#F8F3F5"))
            pal.setColor(QPalette.ColorRole.Text, QColor("#242329"))
            pal.setColor(QPalette.ColorRole.Button, QColor("#FAF5F7"))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor("#242329"))
            pal.setColor(QPalette.ColorRole.Highlight, QColor("#F5E8EA"))
            pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#111827"))
            pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#111827"))
            app.setPalette(pal)
            self.apply_tooltip_theme(light=True)

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color:#F5EFF3; color:#242329; }
            QMenuBar {
                background-color:#ffffff;
                color:#242329;
                border-bottom:1px solid #E3DDE1;
                padding:2px 4px;
            }
            QMenuBar::item { background:transparent; padding:6px 10px; border-radius:0px; }
            QMenuBar::item:selected { background:#FBF5F6; }
            QMenu {
                background-color:#ffffff;
                color:#242329;
                border:1px solid #DED8DC;
                border-radius:0px;
                padding:6px;
            }
            QMenu::separator { height:1px; background:#e3e8f1; margin:6px 6px; }
            QMenu::item { padding:7px 28px 7px 12px; border-radius:0px; }
            QMenu::item:selected { background-color:#FBF5F6; color:#111827; }
            QMessageBox { background:#F5EFF3; color:#111827; }
            QMessageBox QLabel { color:#111827; }
            QMessageBox QPushButton { background:#ffffff; color:#111827; border:1px solid #D1C9CE; border-radius:0px; padding:4px 10px; min-width:56px; }
            QMessageBox QPushButton:hover { background:#FBF5F6; border-color:#D7A3A9; }
            QProgressDialog, QProgressDialog QWidget { background:#F5EFF3; color:#111827; }
            QProgressDialog QLabel { color:#111827; }
            QProgressBar { background:#E7E2E5; color:#111827; border:1px solid #D1C9CE; border-radius:0px; height:16px; text-align:center; }
            QProgressBar::chunk { background:#8A4A52; border-radius:0px; }
            QLabel, QCheckBox, QRadioButton, QGroupBox { color:#242329; }
            QGroupBox {
                border:1px solid #DED8DC;
                border-radius:0px;
                margin-top:12px;
                padding:10px;
                background:#ffffff;
            }
            QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; color:#374151; }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QFontComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {
                background-color:#ffffff;
                color:#242329;
                border:1px solid #D1C9CE;
                border-radius:0px;
                padding:3px 6px;
                selection-background-color:#F5E8EA;
                selection-color:#111827;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QFontComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QKeySequenceEdit:focus {
                border:1px solid #C78A90;
            }
            QAbstractItemView {
                background-color:#ffffff;
                color:#242329;
                border:1px solid #DED8DC;
                border-radius:0px;
                alternate-background-color:#F8F3F5;
                selection-background-color:#F5E8EA;
                selection-color:#111827;
                gridline-color:#E7E1E5;
            }
            QHeaderView::section {
                background-color:#F2EDEF;
                color:#374151;
                border:0;
                border-right:1px solid #DED8DC;
                padding:7px;
            }
            QPushButton {
                background-color:#FAF5F7;
                color:#242329;
                border:1px solid #D1C9CE;
                border-radius:0px;
                padding:4px 10px;
            }
            QPushButton:hover { background-color:#FBF5F6; border-color:#D7A3A9; }
            QPushButton:pressed { background-color:#F5E8EA; }
            QPushButton:disabled { background-color:#F0EAED; color:#A29A9F; border-color:#E0DADF; }
            QToolBar {
                background-color:#F1ECEF;
                border:1px solid #DED8DC;
                border-radius:0px;
                spacing:8px;
                padding:4px;
            }
            QToolButton {
                background-color:#FAF5F7;
                color:#242329;
                border:1px solid #D1C9CE;
                border-radius:0px;
                padding:5px;
            }
            QToolButton:hover { background-color:#FBF5F6; border-color:#D7A3A9; }
            QToolButton:checked { background-color:#F5E8EA; border-color:#C78A90; }
            QCheckBox::indicator, QRadioButton::indicator {
                width:15px; height:15px;
                border:1px solid #aab4c3;
                background:#ffffff;
                border-radius:0px;
            }
            QRadioButton::indicator { border-radius:0px; }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked { background:#A85D66; border:1px solid #A85D66; }
            QSplitter::handle { background:#DED8DC; }
            QTabWidget::pane { border:1px solid #DED8DC; border-radius:0px; background:#ffffff; }
            QTabBar::tab {
                background:#EEEFF3;
                color:#555056;
                padding:8px 12px;
                border:1px solid #DAD4D8;
                border-bottom:none;
                border-top-left-radius:10px;
                border-top-right-radius:3px;
            }
            QTabBar::tab:selected { background:#ffffff; color:#211F23; font-weight:bold; }
            QTabBar::tab:hover { background:#FBF5F6; }
            QScrollBar:vertical { background:#F1ECEF; width:12px; margin:0; border:0; border-radius:0px; }
            QScrollBar::handle:vertical { background:#CBC4C9; min-height:30px; border-radius:0px; }
            QScrollBar::handle:vertical:hover { background:#b7c3d4; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar:horizontal { background:#F1ECEF; height:12px; margin:0; border:0; border-radius:0px; }
            QScrollBar::handle:horizontal { background:#CBC4C9; min-width:30px; border-radius:0px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
            QToolTip { background-color:#ffffff; color:#111827; border:1px solid #D1C9CE; border-radius:0px; padding:5px; }
        """)
        if hasattr(self, 'tb') and self.tb:
            self.tb.setStyleSheet(
                "QToolBar { background:#F1ECEF; border:1px solid #DED8DC; border-radius:0px; padding:4px; }"
                "QToolButton { background:#FAF5F7; color:#242329; border:1px solid #D1C9CE; border-radius:0px; padding:5px; }"
                "QToolButton:hover { background:#FBF5F6; border-color:#D7A3A9; }"
                "QToolButton:checked { background:#F5E8EA; border:2px solid #C78A90; color:#111827; font-weight:700; }"
            )
            try:
                self.update_left_tool_action_states()
            except Exception:
                pass
        if hasattr(self, 'mask_toggle_wrap') and self.mask_toggle_wrap:
            self.mask_toggle_wrap.setStyleSheet("")
        if hasattr(self, 'btn_page') and self.btn_page:
            self.btn_page.setStyleSheet("border:none; font-weight:bold; color:#242329;")
        self.apply_page_tab_style()
        self.apply_text_style_button_styles()
        if hasattr(self, 'tab') and self.tab:
            self.tab.setStyleSheet(
                "QTableWidget { background:#ffffff; color:#242329; gridline-color:#E7E1E5; border:1px solid #DED8DC; border-radius:0px; }"
                "QTableWidget::item:selected { background:#F5E8EA; color:#111827; }"
                "QTableWidget QTableCornerButton::section { background:#F2EDEF; border:1px solid #DED8DC; }"
            )
            self.repaint_text_table_theme()
        self.apply_log_panel_theme()
        self.apply_action_button_theme_styles()
        self.update_color_button_styles()
        try:
            if getattr(self, "_task_progress_overlay", None) is not None:
                self._task_progress_overlay.apply_theme(True)
            if getattr(self, "_task_alert_overlay", None) is not None:
                self._task_alert_overlay.apply_theme(True)
        except Exception:
            pass
        self.schedule_native_title_bar_theme(self, dark=False)

    def apply_dark_theme(self):
        """다크 테마를 홈 화면과 맞는 부드러운 카드형 톤으로 적용한다."""
        app = QApplication.instance()
        if app:
            app.setStyleSheet("""
                QToolTip { background-color:#141416; color:#ffffff; border:1px solid #555056; border-radius:0px; padding:5px; }
            """)
            pal = QPalette()
            pal.setColor(QPalette.ColorRole.Window, QColor("#101113"))
            pal.setColor(QPalette.ColorRole.WindowText, QColor("#E0DADF"))
            pal.setColor(QPalette.ColorRole.Base, QColor("#171719"))
            pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#1D1B1F"))
            pal.setColor(QPalette.ColorRole.Text, QColor("#E0DADF"))
            pal.setColor(QPalette.ColorRole.Button, QColor("#28262B"))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor("#E0DADF"))
            pal.setColor(QPalette.ColorRole.Highlight, QColor("#8A4A52"))
            pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#141416"))
            pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#ffffff"))
            app.setPalette(pal)

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color:#101113; color:#E0DADF; }
            QWidget#EditorRoot { background-color:#0f1117; }
            QWidget#LeftPanel { background-color:#0f1117; }
            QWidget#CanvasPanel { background-color:#0B0C0E; }
            QWidget#RightPanel { background-color:#171719; }
            QScrollArea#RightPanelScroll { background:#171719; border:0; border-left:1px solid #2E2A30; }
            QScrollArea#RightPanelScroll > QWidget > QWidget { background:#171719; }
            QGraphicsView#MainCanvasView, QGraphicsView#SourceCompareView { background:#0B0C0E; border:1px solid #293241; }
            QFrame#MakerDatabasePreviewPanel { background:#0B0C0E; border:1px solid #293241; }
            QLabel#MakerDatabasePreviewTitle { color:#FFFFFF; font-size:18px; font-weight:800; }
            QLabel#MakerDatabasePreviewSubtitle { color:#C9C2C7; font-size:11px; }
            QFrame#MakerDatabasePreviewCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #171815, stop:1 #202218); border:2px solid #75A9FF; border-radius:4px; }
            QLabel#MakerDatabasePreviewKind { color:#A9C7FF; font-size:15px; font-weight:800; }
            QLabel#MakerDatabasePreviewSource { color:#FFFFFF; font-size:16px; font-weight:700; }
            QLabel#MakerDatabasePreviewTranslation { color:#F2EEF2; font-size:15px; font-weight:700; }
            QLabel#MakerDatabasePreviewHint { color:#AFA7AD; font-size:11px; }
            QMenuBar {
                background-color:#101113;
                color:#E0DADF;
                border-bottom:1px solid #2E2A30;
                padding:2px 4px;
            }
            QMenuBar::item { background:transparent; padding:6px 10px; border-radius:0px; }
            QMenuBar::item:selected { background:#28262B; }
            QMenu {
                background-color:#18171A;
                color:#E0DADF;
                border:1px solid #2E2A30;
                border-radius:0px;
                padding:6px;
            }
            QMenu::separator { height:1px; background:#2E2A30; margin:6px 6px; }
            QMenu::item { padding:7px 28px 7px 12px; border-radius:0px; }
            QMenu::item:selected { background-color:#28262B; color:#ffffff; }
            QMessageBox { background:#171719; color:#E0DADF; }
            QMessageBox QLabel { color:#E0DADF; }
            QMessageBox QPushButton { background:#28262B; color:#E0DADF; border:1px solid #3A363B; border-radius:0px; padding:4px 10px; min-width:56px; }
            QMessageBox QPushButton:hover { background:#332B30; border-color:#665A62; }
            QProgressDialog, QProgressDialog QWidget { background:#171719; color:#E0DADF; }
            QProgressDialog QLabel { color:#E0DADF; }
            QProgressBar { background:#111827; color:#ffffff; border:1px solid #555056; border-radius:0px; height:16px; text-align:center; }
            QProgressBar::chunk { background:#8A4A52; border-radius:0px; }
            QLabel, QCheckBox, QRadioButton, QGroupBox { color:#E0DADF; }
            QGroupBox {
                border:1px solid #2E2A30;
                border-radius:0px;
                margin-top:12px;
                padding:10px;
                background:#18171A;
            }
            QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; color:#CBC4C9; }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QFontComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {
                background-color:#211F23;
                color:#F6F1F4;
                border:1px solid #3D383E;
                border-radius:0px;
                padding:3px 6px;
                selection-background-color:#8A4A52;
                selection-color:#ffffff;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QFontComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QKeySequenceEdit:focus {
                border:1px solid #A85D66;
                background:#111827;
            }
            QAbstractItemView {
                background-color:#171719;
                color:#E0DADF;
                border:1px solid #2E2A30;
                border-radius:0px;
                alternate-background-color:#1D1B1F;
                selection-background-color:#8A4A52;
                selection-color:#ffffff;
                gridline-color:#2C282D;
            }
            QHeaderView::section {
                background-color:#141416;
                color:#CBC4C9;
                border:0;
                border-right:1px solid #2E2A30;
                padding:7px;
            }
            QPushButton {
                background-color:#28262B;
                color:#E0DADF;
                border:1px solid #3A363B;
                border-radius:0px;
                padding:4px 10px;
            }
            QPushButton:hover { background-color:#332B30; border-color:#665A62; }
            QPushButton:pressed { background-color:#111827; }
            QPushButton:disabled { background-color:#171719; color:#746B72; border-color:#2E2A30; }
            QToolBar {
                background-color:#171719;
                border:1px solid #2E2A30;
                border-radius:0px;
                spacing:8px;
                padding:4px;
            }
            QToolButton {
                background-color:#28262B;
                color:#E0DADF;
                border:1px solid #3A363B;
                border-radius:0px;
                padding:5px;
            }
            QToolButton:hover { background-color:#332B30; border-color:#665A62; }
            QToolButton:checked { background-color:#8A4A52; border-color:#A85D66; }
            QCheckBox::indicator, QRadioButton::indicator {
                width:15px; height:15px;
                border:1px solid #3A363B;
                background:#211F23;
                border-radius:0px;
            }
            QRadioButton::indicator { border-radius:0px; }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked { background:#8A4A52; border:1px solid #A85D66; }
            QSplitter::handle { background:#2E2A30; }
            QTabWidget::pane { border:1px solid #2E2A30; border-radius:0px; background:#171719; }
            QTabBar::tab {
                background:#171719;
                color:#9A9098;
                padding:8px 12px;
                border:1px solid #2E2A30;
                border-bottom:none;
                border-top-left-radius:10px;
                border-top-right-radius:3px;
            }
            QTabBar::tab:selected { background:#28262B; color:#ffffff; font-weight:bold; }
            QTabBar::tab:hover { background:#332B30; }
            QScrollBar:vertical { background:#171719; width:12px; margin:0; border:0; border-radius:0px; }
            QScrollBar::handle:vertical { background:#3D383E; min-height:30px; border-radius:0px; }
            QScrollBar::handle:vertical:hover { background:#5C555B; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar:horizontal { background:#171719; height:12px; margin:0; border:0; border-radius:0px; }
            QScrollBar::handle:horizontal { background:#3D383E; min-width:30px; border-radius:0px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
            QToolTip { background-color:#141416; color:#ffffff; border:1px solid #555056; border-radius:0px; padding:5px; }
        """)
        if hasattr(self, 'tb') and self.tb:
            self.tb.setStyleSheet(
                "QToolBar { background:#171719; border:1px solid #2E2A30; border-radius:0px; padding:4px; }"
                "QToolButton { background:#28262B; color:#E0DADF; border:1px solid #3A363B; border-radius:0px; padding:5px; }"
                "QToolButton:hover { background:#332B30; border-color:#665A62; }"
                "QToolButton:checked { background:#8A4A52; border:2px solid #A85D66; color:#ffffff; font-weight:700; }"
            )
            try:
                self.update_left_tool_action_states()
            except Exception:
                pass
        if hasattr(self, 'mask_toggle_wrap') and self.mask_toggle_wrap:
            self.mask_toggle_wrap.setStyleSheet("")
        if hasattr(self, 'btn_page') and self.btn_page:
            self.btn_page.setStyleSheet("border:none; font-weight:bold; color:#E0DADF;")
        self.apply_page_tab_style()
        self.apply_text_style_button_styles()
        if hasattr(self, 'tab') and self.tab:
            self.tab.setStyleSheet(
                "QTableWidget { background:#171719; color:#E0DADF; gridline-color:#2C282D; border:1px solid #2E2A30; border-radius:0px; }"
                "QTableWidget::item:selected { background:#8A4A52; color:#ffffff; }"
                "QTableWidget QTableCornerButton::section { background:#141416; border:1px solid #2E2A30; }"
            )
            self.repaint_text_table_theme()
        self.apply_log_panel_theme()
        self.apply_action_button_theme_styles()
        self.update_color_button_styles()
        try:
            if getattr(self, "_task_progress_overlay", None) is not None:
                self._task_progress_overlay.apply_theme(False)
            if getattr(self, "_task_alert_overlay", None) is not None:
                self._task_alert_overlay.apply_theme(False)
        except Exception:
            pass

    def make_color_icon(self, color_value):
        pix = QPixmap(22, 22)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        c = QColor(str(color_value or "#FFFFFF"))
        if not c.isValid():
            c = QColor("#FFFFFF")
        painter.setPen(QPen(QColor("#777777"), 1))
        painter.setBrush(QBrush(c))
        painter.drawRect(2, 2, 18, 18)
        painter.end()
        return QIcon(pix)

    def update_color_button_styles(self):
        pairs = [
            (getattr(self, "btn_text_color", None), self.default_text_color, "문자 색상"),
            (getattr(self, "btn_stroke_color", None), self.default_stroke_color, "획 색상"),
            (getattr(self, "btn_item_text_color", None), self.default_text_color, "문자 색상"),
            (getattr(self, "btn_item_stroke_color", None), self.default_stroke_color, "획 색상"),
        ]
        for btn, color, tooltip in pairs:
            if btn:
                btn.setText("")
                btn.setStatusTip(f"{tooltip}: {color}")
                try:
                    btn.setProperty("force_outlined_tooltip_text", True)
                    btn.setProperty("force_color_tooltip_text", True)
                except Exception:
                    pass
                btn.setFixedSize(26, 26)
                tip_bg = "#ffffff" if self.is_light_theme() else "#000000"
                tip_fg = "#111827" if self.is_light_theme() else "#ffffff"
                tip_border = "#D1C9CE" if self.is_light_theme() else "#555056"
                btn.setStyleSheet(
                    f"QPushButton {{ background:{color}; border:1px solid #3A363B; border-radius:0px; padding:0px; }}"
                    f"QPushButton:hover {{ border:1px solid #C78A90; }}"
                    f"QToolTip {{ background-color:{tip_bg}; color:{tip_fg}; border:1px solid {tip_border}; border-radius:0px; padding:5px; }}"
                )

        if hasattr(self, "act_final_paint_color"):
            self.act_final_paint_color.setIcon(self.make_color_icon(self.final_paint_color))
            self.act_final_paint_color.setText("")
            self.act_final_paint_color.setStatusTip(f"{self.tr_ui('최종 페인팅 색상')}: {self.final_paint_color} / {self.tr_ui('스포이드: Alt+마우스 좌클릭')}")
            self.act_final_paint_color.setToolTip(f"{self.tr_ui('최종 페인팅 색상')}: {self.final_paint_color}\n{self.tr_ui('스포이드: Alt+마우스 좌클릭')}")
            try:
                w = self.tb.widgetForAction(self.act_final_paint_color) if hasattr(self, "tb") else None
                if w is not None:
                    w.setProperty("force_outlined_tooltip_text", True)
                    w.setProperty("force_color_tooltip_text", True)
                    tip_bg = "#ffffff" if self.is_light_theme() else "#000000"
                    tip_fg = "#111827" if self.is_light_theme() else "#ffffff"
                    tip_border = "#D1C9CE" if self.is_light_theme() else "#555056"
                    w.setStyleSheet(
                        f"QToolButton {{ border:1px solid #2E2A30; border-radius:0px; padding:2px; }}"
                        f"QToolTip {{ background-color:{tip_bg}; color:{tip_fg}; border:1px solid {tip_border}; border-radius:0px; padding:5px; }}"
                    )
            except Exception:
                pass


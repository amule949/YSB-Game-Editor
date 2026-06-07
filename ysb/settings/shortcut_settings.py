import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QDialogButtonBox,
    QTabWidget, QWidget, QPushButton, QHBoxLayout, QMessageBox, QScrollArea,
    QCheckBox, QInputDialog, QLineEdit, QListWidget, QListWidgetItem,
    QAbstractItemView, QFrame, QSizePolicy
)
from PyQt6.QtGui import QKeySequence
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import QKeySequenceEdit

from ysb.core.cache_utils import get_cache_file

CACHE_FILE_NAME = "shortcut_cache.json"

# 쯔꾸르붕이: 이미지 편집/식질 호출 경로를 단축키·매크로 목록에서 제거한다.
# 옛 tktool_* 이름은 호환 래퍼로 남기고, 내부 기준은 maker_* 이름을 사용한다.
MAKER_SHORTCUT_MODE = True
TKTOOL_PHASE2_MODE = MAKER_SHORTCUT_MODE  # legacy compatibility
MAKER_LEGACY_SHORTCUT_ALIASES = {
    "project_import_images": "project_import_maker_game",
    "paint_undo": "edit_undo",
    "paint_redo": "edit_redo",
    "work_analyze": "work_scan_maker_game",
}
TKTOOL_PHASE2_SHORTCUT_KEYS = {
    "project_new", "project_import_maker_game", "project_import_images", "project_maker_character_profiles", "project_open", "project_open_json",
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
    "work_restore_edge_control_codes_current", "batch_restore_edge_control_codes",
    "batch_translate", "batch_extract_text", "edit_undo", "edit_redo", "paint_undo", "paint_redo", "text_linebreak",
}
TKTOOL_PHASE2_MACRO_ACTION_KEYS = {
    "work_translate", "batch_translate", "work_text_find", "work_text_replace",
    "work_unify_translations", "work_extract_text", "work_import_translation", "work_clear_translation", "work_restore_edge_control_codes_current",
    "batch_restore_edge_control_codes", "batch_extract_text", "project_save",
}

def maker_shortcut_allowed(key: str) -> bool:
    if not MAKER_SHORTCUT_MODE:
        return True
    return str(key or "") in TKTOOL_PHASE2_SHORTCUT_KEYS

def maker_macro_action_allowed(key: str) -> bool:
    if not MAKER_SHORTCUT_MODE:
        return True
    return str(key or "") in TKTOOL_PHASE2_MACRO_ACTION_KEYS

def maker_filter_shortcut_rows(rows):
    if not MAKER_SHORTCUT_MODE:
        return list(rows or [])
    return [(key, label) for key, label in (rows or []) if maker_shortcut_allowed(key)]

def maker_visible_shortcut_groups():
    result = []
    for group_title, rows in GROUPS:
        filtered = maker_filter_shortcut_rows(rows)
        if filtered:
            result.append((group_title, filtered))
    return result

# 구버전 호출 호환 래퍼.
def tktool_phase2_shortcut_allowed(key: str) -> bool:
    return maker_shortcut_allowed(key)

def tktool_phase2_macro_action_allowed(key: str) -> bool:
    return maker_macro_action_allowed(key)

def tktool_phase2_filter_rows(rows):
    return maker_filter_shortcut_rows(rows)

def tktool_phase2_visible_groups():
    return maker_visible_shortcut_groups()


def cache_file():
    return get_cache_file(CACHE_FILE_NAME)


_CONFIRM_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter)
_ESCAPE_KEYS = (Qt.Key.Key_Escape,)
_ENTER_KEY_NAMES = {"return", "enter", "numenter", "num+enter", "keypadenter"}
_COMMA_KEY_NAMES = {",", "comma"}
_PUNCT_KEY_NAMES = {
    ",": Qt.Key.Key_Comma,
    "comma": Qt.Key.Key_Comma,
    "<": Qt.Key.Key_Comma,
    "less": Qt.Key.Key_Comma,
    ".": Qt.Key.Key_Period,
    "period": Qt.Key.Key_Period,
    ">": Qt.Key.Key_Period,
    "greater": Qt.Key.Key_Period,
    "/": Qt.Key.Key_Slash,
    "slash": Qt.Key.Key_Slash,
    "?": Qt.Key.Key_Slash,
    "question": Qt.Key.Key_Slash,
}
_PUNCT_EVENT_ALIASES = {
    ",": (Qt.Key.Key_Comma, getattr(Qt.Key, "Key_Less", Qt.Key.Key_Comma)),
    ".": (Qt.Key.Key_Period, getattr(Qt.Key, "Key_Greater", Qt.Key.Key_Period)),
    "/": (Qt.Key.Key_Slash, getattr(Qt.Key, "Key_Question", Qt.Key.Key_Slash)),
}
_PUNCT_TEXT_ALIASES = {
    ",": {",", "<"},
    ".": {".", ">"},
    "/": {"/", "?"},
}
_MODIFIER_MASK = (
    Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.ShiftModifier
    | Qt.KeyboardModifier.MetaModifier
)


def _enum_int(value):
    try:
        return int(value.value)
    except Exception:
        try:
            return int(value)
        except Exception:
            return 0


def _split_sequence_parts_preserving_comma(text: str):
    """QKeySequence PortableText의 콤마 구분자를 나누되 Ctrl+, 같은 콤마 키는 보존한다."""
    s = str(text or "").strip()
    if not s:
        return []
    if s.lower() in _COMMA_KEY_NAMES:
        return [s]

    parts = []
    buf = []
    for i, ch in enumerate(s):
        if ch == ",":
            before = "".join(buf).rstrip()
            after = s[i + 1:].lstrip()
            prev = before[-1:]
            # Ctrl+, / Ctrl+Shift+, / bare , 는 실제 콤마 키이므로 분리하지 않는다.
            if prev == "+" or (not before and not after):
                buf.append(ch)
                continue
            # 일반 QKeySequence의 multi-stroke 구분자.
            part = before.strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def key_sequence_from_text(value) -> QKeySequence:
    """문자열을 QKeySequence로 변환한다. Qt가 헷갈려하는 Ctrl+, 계열은 수동 생성한다."""
    text = str(value or "").strip()
    if not text:
        return QKeySequence("")
    compact = text.replace(" ", "")
    tokens = [t for t in compact.split("+") if t != ""]
    key_token = tokens[-1].lower() if tokens else ""
    if key_token in _PUNCT_KEY_NAMES:
        mods = Qt.KeyboardModifier.NoModifier
        for token in tokens[:-1]:
            t = token.lower()
            if t in ("ctrl", "control"):
                mods |= Qt.KeyboardModifier.ControlModifier
            elif t == "alt":
                mods |= Qt.KeyboardModifier.AltModifier
            elif t == "shift":
                mods |= Qt.KeyboardModifier.ShiftModifier
            elif t in ("meta", "cmd", "command", "win"):
                mods |= Qt.KeyboardModifier.MetaModifier
        return QKeySequence(_enum_int(mods) | _enum_int(_PUNCT_KEY_NAMES[key_token]))
    return QKeySequence(text)


def key_sequence_to_portable(seq, fallback="") -> str:
    try:
        text = seq.toString(QKeySequence.SequenceFormat.PortableText)
    except Exception:
        text = ""
    if text:
        return text
    fallback = str(fallback or "").strip()
    if fallback and (fallback.lower() in _COMMA_KEY_NAMES or fallback.replace(" ", "").endswith("+,")):
        return fallback.replace(" ", "")
    return ""



def _reduced_modifiers(mods):
    try:
        return mods & _MODIFIER_MASK
    except Exception:
        return Qt.KeyboardModifier.NoModifier


def _parse_shortcut_part(text: str):
    compact = str(text or "").replace(" ", "").strip()
    if not compact:
        return Qt.KeyboardModifier.NoModifier, ""
    tokens = [t for t in compact.split("+") if t != ""]
    if not tokens:
        return Qt.KeyboardModifier.NoModifier, ""
    mods = Qt.KeyboardModifier.NoModifier
    for token in tokens[:-1]:
        t = token.lower()
        if t in ("ctrl", "control"):
            mods |= Qt.KeyboardModifier.ControlModifier
        elif t == "alt":
            mods |= Qt.KeyboardModifier.AltModifier
        elif t == "shift":
            mods |= Qt.KeyboardModifier.ShiftModifier
        elif t in ("meta", "cmd", "command", "win"):
            mods |= Qt.KeyboardModifier.MetaModifier
    return mods, tokens[-1].lower()


def _canonical_punct_token(token: str):
    t = str(token or "").lower()
    if t in (",", "comma", "<", "less"):
        return ","
    if t in (".", "period", ">", "greater"):
        return "."
    if t in ("/", "slash", "?", "question"):
        return "/"
    return ""


def key_event_matches_sequence(event, seq) -> bool:
    """Qt가 Shift+기호키를 Shift+<, Shift+>, Shift+?처럼 넘겨도 단축키로 인식한다."""
    if not seq or seq.isEmpty():
        return False
    try:
        key = event.key()
    except Exception:
        return False
    if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
        return False

    try:
        mods_value = _enum_int(_reduced_modifiers(event.modifiers()))
        pressed = QKeySequence(mods_value | _enum_int(key))
        if pressed.matches(seq) == QKeySequence.SequenceMatch.ExactMatch:
            return True
    except Exception:
        pass

    # Fallback: punctuation keys on many layouts are reported as the shifted glyph key.
    # Examples: Shift+, => Key_Less/text '<', Shift+. => Key_Greater/text '>', Shift+/ => Key_Question/text '?'.
    texts = []
    for fmt in (QKeySequence.SequenceFormat.PortableText, QKeySequence.SequenceFormat.NativeText):
        try:
            text = seq.toString(fmt)
        except Exception:
            text = ""
        if text and text not in texts:
            texts.append(text)

    try:
        event_mods = _reduced_modifiers(event.modifiers())
    except Exception:
        event_mods = Qt.KeyboardModifier.NoModifier
    try:
        event_text = event.text()
    except Exception:
        event_text = ""

    for text in texts:
        for part in _split_sequence_parts_preserving_comma(text):
            expected_mods, key_token = _parse_shortcut_part(part)
            canonical = _canonical_punct_token(key_token)
            if not canonical:
                continue
            if _enum_int(event_mods) != _enum_int(expected_mods):
                continue
            if key in _PUNCT_EVENT_ALIASES.get(canonical, ()):
                return True
            if event_text in _PUNCT_TEXT_ALIASES.get(canonical, set()):
                return True
    return False


def _sequence_part_has_enter(part: str) -> bool:
    tokens = [t.strip().lower() for t in str(part or "").replace(" ", "").split("+") if t.strip()]
    return any(t in _ENTER_KEY_NAMES for t in tokens)


def sequence_without_confirm_keys(seq) -> QKeySequence:
    """Return/Enter는 단축키 입력 확정키로만 사용하고 실제 단축키에서는 제거한다."""
    try:
        text = seq.toString(QKeySequence.SequenceFormat.PortableText)
    except Exception:
        text = str(seq or "")
    parts = _split_sequence_parts_preserving_comma(text)
    parts = [p for p in parts if not _sequence_part_has_enter(p)]
    return key_sequence_from_text(", ".join(parts))


class ConfirmingKeySequenceEdit(QKeySequenceEdit):
    """Enter/Esc를 단축키 일부가 아니라 입력 확정/포커스 해제로 처리하는 단축키 입력칸."""

    def _finish_shortcut_input(self):
        try:
            clean = sequence_without_confirm_keys(self.keySequence())
            if key_sequence_to_portable(clean) != key_sequence_to_portable(self.keySequence()):
                self.blockSignals(True)
                try:
                    self.setKeySequence(clean)
                finally:
                    self.blockSignals(False)
        except Exception:
            pass
        try:
            self.editingFinished.emit()
        except Exception:
            pass
        try:
            self.clearFocus()
        except Exception:
            pass
        try:
            parent = self.parentWidget()
            if parent is not None:
                parent.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception:
            pass

    def keyPressEvent(self, event):
        if event.key() in _CONFIRM_KEYS:
            event.accept()
            self._finish_shortcut_input()
            return
        if event.key() in _ESCAPE_KEYS:
            event.accept()
            self._finish_shortcut_input()
            return
        punct_key = None
        try:
            key = event.key()
            text = event.text()
        except Exception:
            key = None
            text = ""
        if key in _PUNCT_EVENT_ALIASES.get(",", ()) or text in _PUNCT_TEXT_ALIASES.get(",", set()):
            punct_key = ","
        elif key in _PUNCT_EVENT_ALIASES.get(".", ()) or text in _PUNCT_TEXT_ALIASES.get(".", set()):
            punct_key = "."
        elif key in _PUNCT_EVENT_ALIASES.get("/", ()) or text in _PUNCT_TEXT_ALIASES.get("/", set()):
            punct_key = "/"
        if punct_key:
            mods = event.modifiers()
            parts = []
            if mods & Qt.KeyboardModifier.ControlModifier:
                parts.append("Ctrl")
            if mods & Qt.KeyboardModifier.AltModifier:
                parts.append("Alt")
            if mods & Qt.KeyboardModifier.ShiftModifier:
                parts.append("Shift")
            if mods & Qt.KeyboardModifier.MetaModifier:
                parts.append("Meta")
            seq_text = "+".join(parts + [punct_key]) if parts else punct_key
            self.setKeySequence(key_sequence_from_text(seq_text))
            event.accept()
            return
        super().keyPressEvent(event)


THEME_DARK = "dark"
THEME_LIGHT = "light"
LANG_KO = "ko"
LANG_EN = "en"

# Independent dialog translation table is centralized in lang_text.py.
from ysb.i18n.lang_text import SHORTCUT_TR_KO_EN as TR_KO_EN

def resolve_ui_language(widget=None):
    cur = widget
    while cur is not None:
        lang = getattr(cur, "ui_language", None) or getattr(cur, "_ui_language", None)
        if lang:
            lang = str(lang).lower()
            if lang.startswith("en"):
                return LANG_EN
            return LANG_KO
        try:
            cur = cur.parent()
        except Exception:
            break
    return LANG_KO

def tr_text(text, lang=LANG_KO):
    text = str(text)
    if str(lang).lower().startswith("en"):
        return TR_KO_EN.get(text, text)
    return text


def resolve_ui_theme(widget=None):
    """부모 창에서 현재 UI 테마를 찾아온다."""
    cur = widget
    while cur is not None:
        theme = getattr(cur, "ui_theme", None) or getattr(cur, "_ui_theme", None)
        if theme:
            theme = str(theme).lower()
            if theme in (THEME_DARK, THEME_LIGHT):
                return theme
        try:
            cur = cur.parent()
        except Exception:
            break
    return THEME_DARK


def shortcut_dialog_qss(theme=THEME_DARK):
    """단축키/매크로/프리셋 계열 창 공통 카드형 스타일."""
    if str(theme).lower() == THEME_LIGHT:
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
            QFrame#SettingsItem[shortcutEnabled="false"] {
                background:#F0EAED;
                border:1px solid #d7dde8;
            }
            QLabel#SettingsItemTitle { font-size:13px; font-weight:700; color:#211F23; }
            QLabel#SettingsTitle, QLabel#SettingsDialogTitle { font-size:22px; font-weight:800; color:#211F23; }
            QLabel#SettingsSectionTitle { font-size:16px; font-weight:750; color:#211F23; }
            QLabel#SettingsDescription { color:#6F666D; line-height:140%; }
            QLineEdit, QTextEdit, QPlainTextEdit, QKeySequenceEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background:#ffffff;
                color:#242329;
                border:1px solid #D1C9CE;
                border-radius:0px;
                padding:3px 6px;
                selection-background-color:#F5E8EA;
                selection-color:#111827;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QKeySequenceEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
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
            QCheckBox::indicator:checked, QRadioButton::indicator:checked { background:#A85D66; border:1px solid #A85D66; }
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
            QTabWidget::pane { border:1px solid #DED8DC; border-radius:0px; background:#ffffff; top:-1px; }
            QTabBar::tab {
                background:#EEEFF3;
                color:#555056;
                border:1px solid #DAD4D8;
                border-bottom:none;
                border-top-left-radius:10px;
                border-top-right-radius:3px;
                padding:4px 10px;
                min-width:0px;
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
            QScrollBar:vertical { background:#F1ECEF; width:12px; margin:0; border:0; border-radius:0px; }
            QScrollBar::handle:vertical { background:#CBC4C9; min-height:30px; border-radius:0px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QToolTip { background:#ffffff; color:#111827; border:1px solid #D1C9CE; border-radius:0px; padding:5px; }
        """
    return """
        QDialog { background:#1E1D20; color:#F4EEF2; }
        QScrollArea { background:transparent; border:0; }
        QLabel { color:#F4EEF2; }
        QFrame#SettingsBlock {
            background:#2A282D;
            border:1px solid #3A363B;
            border-radius:16px;
        }
        QFrame#SettingsItem {
            background:#252328;
            border:1px solid #3A363B;
            border-radius:14px;
        }
        QFrame#SettingsItem[shortcutEnabled="false"] {
            background:#211F23;
            border:1px solid #323844;
        }
        QLabel#SettingsItemTitle { font-size:13px; font-weight:700; color:#ffffff; }
        QLabel#SettingsTitle, QLabel#SettingsDialogTitle { font-size:22px; font-weight:800; color:#ffffff; }
        QLabel#SettingsSectionTitle { font-size:16px; font-weight:750; color:#ffffff; }
        QLabel#SettingsDescription { color:#BDB6BB; line-height:140%; }
        QLineEdit, QTextEdit, QPlainTextEdit, QKeySequenceEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background:#211F23;
            color:#F6F1F4;
            border:1px solid #434a56;
            border-radius:0px;
            padding:3px 6px;
            selection-background-color:#8A4A52;
            selection-color:#ffffff;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QKeySequenceEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border:1px solid #C78A90;
            background:#242128;
        }
        QCheckBox, QRadioButton { color:#F4EEF2; spacing:9px; }
        QCheckBox::indicator, QRadioButton::indicator {
            width:15px; height:15px;
            border:1px solid #6f7786;
            background:#211F23;
            border-radius:0px;
        }
        QCheckBox::indicator:checked, QRadioButton::indicator:checked { background:#8A4A52; border:1px solid #8A4A52; }
        QPushButton {
            background:#373136;
            color:#F4EEF2;
            border:1px solid #5E565D;
            border-radius:0px;
            padding:4px 10px;
        }
        QPushButton:hover { background:#443A40; border-color:#8A4A52; }
        QPushButton:pressed { background:#302C31; }
        QPushButton:disabled { background:#2A282D; color:#8B8389; border-color:#3f4550; }
        QTabWidget::pane { border:1px solid #3A363B; border-radius:0px; background:#252328; top:-1px; }
        QTabBar::tab {
            background:#2B282D;
            color:#BDB6BB;
            border:1px solid #3A363B;
            border-bottom:none;
            border-top-left-radius:10px;
            border-top-right-radius:3px;
            padding:4px 10px;
            min-width:0px;
        }
        QTabBar::tab:selected { background:#373136; color:#ffffff; font-weight:700; }
        QListWidget, QTableWidget, QTreeWidget {
            background:#252328;
            color:#F4EEF2;
            border:1px solid #3A363B;
            border-radius:0px;
            alternate-background-color:#2A282D;
            selection-background-color:#5B3136;
            selection-color:#ffffff;
        }
        QScrollBar:vertical { background:#211F23; width:12px; margin:0; border:0; border-radius:0px; }
        QScrollBar::handle:vertical { background:#474147; min-height:30px; border-radius:0px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        QToolTip { background:#242329; color:#ffffff; border:1px solid #555056; border-radius:0px; padding:5px; }
    """


def disabled_key_edit_qss(theme=THEME_DARK):
    if str(theme).lower() == THEME_LIGHT:
        return "QKeySequenceEdit { background:#f4f1f1; color:#91888F; border:1px solid #dccaca; border-radius:0px; padding:3px 6px; }"
    return "QKeySequenceEdit { background:#342c2f; color:#B2ABB0; border:1px solid #5b464b; border-radius:0px; padding:3px 6px; }"


def disabled_line_edit_qss(theme=THEME_DARK):
    if str(theme).lower() == THEME_LIGHT:
        return "QLineEdit { background:#f4f1f1; color:#91888F; border:1px solid #dccaca; border-radius:0px; padding:3px 6px; }"
    return "QLineEdit { background:#342c2f; color:#B2ABB0; border:1px solid #5b464b; border-radius:0px; padding:3px 6px; }"


def disabled_button_qss(theme=THEME_DARK):
    if str(theme).lower() == THEME_LIGHT:
        return "QPushButton { background:#f4f1f1; color:#91888F; border:1px solid #dccaca; border-radius:0px; padding:4px 10px; }"
    return "QPushButton { background:#342c2f; color:#B2ABB0; border:1px solid #5b464b; border-radius:0px; padding:4px 10px; }"

TEXT_SYMBOLS = {
    "ellipsis": ("말줄임표(…)", "…"),
    "horizontal_dash": ("가로장음(―)", "―"),
    "vertical_dash": ("세로장음(│)", "│"),
    "single_corner": ("홑낫표(「」)", "「」"),
    "double_corner": ("겹낫표(『』)", "『』"),
    "white_heart": ("하얀하트(♡)", "♡"),
    "black_heart": ("검은하트(♥)", "♥"),
    "music_note": ("음표(♪)", "♪"),
    "black_circle": ("검은 동그라미(●)", "●"),
    "middle_dot": ("가운뎃점(·)", "·"),
}

DEFAULT_SHORTCUTS = {
    # 1. 그림판 옵션
    "paint_move": "M",
    "paint_brush": "B",
    "paint_erase": "E",
    "paint_zoom_in": "]",
    "paint_zoom_out": "[",
    "paint_reanalyze": "F5",
    "edit_undo": "Ctrl+Z",
    "edit_redo": "Ctrl+Y",
    "paint_undo": "Ctrl+Z",  # legacy alias
    "paint_redo": "Ctrl+Y",  # legacy alias
    "paint_magic_select": "Ctrl+D",
    "paint_magic_expand": "Ctrl+Shift+D",
    "paint_magic_tolerance_inc": "Ctrl+'",
    "paint_magic_tolerance_dec": "Ctrl+;",
    "paint_magic_expand_inc": "Ctrl+Shift+'",
    "paint_magic_expand_dec": "Ctrl+Shift+;",
    "paint_magic_fill": "Alt+Shift+D",
    "paint_area_fill": "J",
     "paint_mask_wrap": "W",
    "paint_mask_cut": "C",
    "paint_mask_wrap_rect": "Alt+D",
    "paint_mask_wrap_free": "Alt+F",
    "paint_mask_toggle": "Ctrl+M",
    "final_paint_color": "Ctrl+Shift+C",
    "final_paint_to_background": "Alt+P",
    "final_text_tool": "T",
    "final_paint_above_toggle": "X",
    "final_paint_opacity_inc": "Alt+S",
    "final_paint_opacity_dec": "Alt+A",

    # 1-2. 글꼴 상세 옵션
    "text_font_size": "Ctrl+Alt+A",
    "text_stroke_size": "Ctrl+Alt+S",
    "text_line_spacing": "Ctrl+Alt+Q",
    "text_letter_spacing": "Ctrl+Alt+W",
    "text_char_width": "Ctrl+Alt+E",
    "text_char_height": "Ctrl+Alt+R",
    "text_bold_toggle": "Ctrl+Alt+B",
    "text_italic_toggle": "Ctrl+Alt+M",
    "text_strike_toggle": "Ctrl+Alt+N",
    "text_transform_toggle": "Ctrl+T",
    "text_effect_gradient": "Shift+G",
    "text_skew_toggle": "Shift+H",
    "text_trapezoid_toggle": "Shift+J",
    "text_arc_toggle": "Shift+K",
    "text_rasterize": "Ctrl+Alt+K",
    "text_paste_same_position": "Ctrl+Shift+V",

    # 2. 텍스트 입력 옵션
    # 사용자가 'Shift'라고 적어준 항목은 실제 입력 충돌 방지를 위해 Shift+Enter로 처리
    "text_linebreak": "Shift+Return",
    "text_ellipsis": "Ctrl+1",
    "text_horizontal_dash": "Ctrl+2",
    "text_vertical_dash": "Ctrl+3",
    "text_single_corner": "Ctrl+4",
    "text_double_corner": "Ctrl+5",
    "text_white_heart": "Ctrl+6",
    "text_black_heart": "Ctrl+7",
    "text_music_note": "Ctrl+8",
    "text_black_circle": "Ctrl+9",
    "text_middle_dot": "Ctrl+0",

    # 3. 프로젝트 옵션
    "project_new": "Ctrl+N",
    "project_import_maker_game": "Alt+O",
    "project_import_images": "Alt+O",  # legacy alias
    "project_maker_character_profiles": "Ctrl+Alt+4",
    "project_open": "Ctrl+Alt+O",
    "project_open_json": "Ctrl+O",
    "project_show_launcher": "Ctrl+Alt+Home",
    "project_exit": "Alt+Q",
    "project_save": "Ctrl+E",
    "project_save_as": "",
    "project_recover_last_work": "Ctrl+Alt+Shift+B",

    # 3-2. 설정 / 옵션
    "option_settings_overview": "Ctrl+Alt+S",

    "option_theme_settings": "Ctrl+Alt+Shift+2",
    "option_language_settings": "Ctrl+Alt+Shift+3",
    "setting_page_tab_display_name": "Ctrl+Alt+Shift+4",
    "setting_output_display_name": "Ctrl+Alt+Shift+5",
    "setting_output_options": "Ctrl+Alt+Shift+=",
    "setting_interface_tooltips": "Ctrl+Alt+Shift+1",
    "option_api_settings": "Ctrl+Alt+1",
    "option_shortcut_settings": "Ctrl+Alt+2",
    "option_macro_settings": "Ctrl+Alt+3",
    "option_text_preset_settings": "Ctrl+Alt+6",
    "option_item_text_preset_settings": "Ctrl+Alt+7",
    "option_translation_prompt": "",
    "option_maker_character_prompts": "Ctrl+Alt+5",
    "option_maker_translation_settings": "Ctrl+Alt+7",
    "option_maker_preview_display_settings": "Ctrl+Alt+8",
    "option_maker_game_settings": "Ctrl+Alt+9",
    "option_maker_game_refresh": "Ctrl+Alt+0",
    "option_maker_database_translation": "Ctrl+D",
    "db_maker_character_name_translation": "Ctrl+G",
    "option_maker_refresh_runtime_profile": "",
    "option_glossary": "Ctrl+Alt+6",
    "option_analysis_mask_settings": "Ctrl+Alt+Shift+M",
    "option_ocr_analysis_regions": "Ctrl+Shift+Alt+A",
    "option_workspace_location": "Ctrl+Alt+Shift+6",
    "option_cleanup_temp_files": "Ctrl+Alt+Shift+7",
    "option_workspace_size_manager": "Ctrl+Alt+Shift+-",
    "option_cleanup_outputs": "Ctrl+Alt+Shift+Delete",
    "option_register_ysb": "Ctrl+Alt+Shift+8",
    "option_unregister_ysbt": "Ctrl+Alt+Shift+9",
    "setting_file_path_visibility": "Ctrl+Alt+Shift+0",
    "help_program_manual": "",
    "help_open_website": "",
    "help_report_bug": "",
    "help_about": "",


    # 4. 작업 옵션
    "work_source_compare": "Ctrl+Alt+Shift+V",
    "work_page_prev": "Alt+Left",
    "work_page_next": "Alt+Right",
    "work_page_list": "Ctrl+Alt+F",
    "work_page_full_name": "Alt+V",
    "work_page_rename_source": "Ctrl+F2",
    "work_page_delete_current": "Ctrl+Q",
    "work_page_delete_all": "Ctrl+Shift+Q",
    "work_open_current_project_folder": "Ctrl+Alt+Shift+F",
    "work_analyze": "Ctrl+F5",
    "work_quick_ocr": "Ctrl+J",
    "quick_ocr_execute": "",
    "work_text_number_width": "Ctrl+Shift+W",
    "work_translate": "Ctrl+F6",
    "work_restore_edge_control_codes_current": "Ctrl+B",
    "work_refresh_maker_preview": "Alt+F5",
    "work_inpaint": "Ctrl+F7",
    "work_import_clean_background": "Alt+C",
    "work_inpaint_source": "",
    "work_restore_original_source": "Ctrl+Shift+R",
    "work_extract_text": "Ctrl+L",
    "work_import_translation": "Ctrl+K",
    "work_clear_translation": "Ctrl+/",
    "work_clean_text": "Ctrl+Alt+Shift+C",
    "work_text_find": "Ctrl+F",
    "work_text_replace": "Ctrl+H",
    "work_unify_translations": "Ctrl+Shift+T",
    "work_reset_text_rects": "Ctrl+G",
    "work_export": "Ctrl+E",
    "work_output_preview": "Ctrl+P",
    "view_text_toggle": "Ctrl+Alt+V",

    # 5. 자동화 작업 옵션
    "auto_text_size_current": "",
    "auto_text_size_batch": "",
    "auto_linebreak_current": "Ctrl+,",
    "auto_linebreak_batch": "Ctrl+Shift+,",

    # 6. 일괄 작업 옵션
    "batch_analyze": "Ctrl+Shift+F5",
    "batch_reanalyze": "Ctrl+Alt+Shift+F5",
    "batch_translate": "Ctrl+Shift+F6",
    "batch_restore_edge_control_codes": "Ctrl+Shift+B",
    "batch_inpaint": "Ctrl+Shift+F7",
    "batch_extract_text": "Ctrl+Shift+L",
    "batch_clear_translation": "Ctrl+Shift+/",
    "batch_clean_text": "Ctrl+Shift+Y",
    "batch_reset_text_rects": "Ctrl+Shift+G",
    "batch_export": "Ctrl+Shift+E",

    # 6. 개별 텍스트 작업 옵션
    "item_font_select": "F1",
    "item_font_inc": "=",
    "item_font_dec": "-",
    "item_align_left": "Shift+,",
    "item_align_center": "Shift+.",
    "item_align_right": "Shift+/",
    "item_stroke_inc": "Ctrl+=",
    "item_stroke_dec": "Ctrl+-",
    "item_text_color": "F6",
    "item_stroke_color": "F7",
}


# These are system-reserved editing shortcuts. They are shown in the shortcut
# manager for discovery, but cannot be changed or disabled.
FIXED_SHORTCUT_KEYS = {"text_linebreak", "edit_undo", "edit_redo", "paint_undo", "paint_redo"}
SHIFT_SYMBOL_SHORTCUT_MIGRATION_KEY = "v2_4_shift_special_shortcuts_migrated"
CTRL_NUMBER_SYMBOL_SHORTCUT_MIGRATION_KEY = "v2_4_ctrl_number_special_shortcuts_migrated"

def fixed_shortcut_text(key: str, portable: bool = True) -> str:
    value = DEFAULT_SHORTCUTS.get(key, "")
    seq = key_sequence_from_text(value)
    fmt = QKeySequence.SequenceFormat.PortableText if portable else QKeySequence.SequenceFormat.NativeText
    try:
        return seq.toString(fmt) or str(value or "")
    except Exception:
        return str(value or "")

def enforce_fixed_shortcuts(settings):
    try:
        for _key in FIXED_SHORTCUT_KEYS:
            settings.shortcuts[_key] = DEFAULT_SHORTCUTS.get(_key, "")
            settings.enabled[_key] = True
    except Exception:
        pass
    return settings

GROUPS = [
    ("그림판", [
        ("paint_move", "이동"),
        ("paint_brush", "브러시"),
        ("paint_erase", "지우개"),
        ("paint_zoom_in", "브러시 확대"),
        ("paint_zoom_out", "브러시 축소"),
        ("paint_reanalyze", "재분석"),
        ("paint_magic_select", "요술봉 선택"),
        ("paint_magic_expand", "요술봉 영역 확장"),
        ("paint_magic_tolerance_inc", "요술봉 허용범위 증가"),
        ("paint_magic_tolerance_dec", "요술봉 허용범위 감소"),
        ("paint_magic_expand_inc", "요술봉 확장범위 증가"),
        ("paint_magic_expand_dec", "요술봉 확장범위 감소"),
        ("paint_magic_fill", "마스킹/영역 칠하기"),
        ("paint_area_fill", "영역 페인팅"),
        ("paint_mask_wrap", "마스크 랩핑"),
        ("paint_mask_cut", "마스크 커팅"),
        ("paint_mask_wrap_rect", "마스크 선택 사각형"),
        ("paint_mask_wrap_free", "마스크 선택 자유형"),
        ("paint_mask_toggle", "페인팅 마스크 ON/OFF"),
        ("final_paint_color", "최종 페인팅 색상"),
        ("final_text_tool", "최종 텍스트 도구"),
        ("final_paint_above_toggle", "텍스트 위 페인팅 ON/OFF"),
        ("final_paint_opacity_inc", "브러시 불투명도 증가"),
        ("final_paint_opacity_dec", "브러시 불투명도 감소"),
    ]),
    ("텍스트", [
        ("item_font_select", "폰트"),
        ("text_font_size", "문자 크기"),
        ("item_font_inc", "문자 확대"),
        ("item_font_dec", "문자 축소"),
        ("text_stroke_size", "획 크기"),
        ("item_stroke_inc", "획 확대"),
        ("item_stroke_dec", "획 축소"),
        ("text_line_spacing", "행간"),
        ("text_letter_spacing", "자간"),
        ("text_char_width", "문자 너비"),
        ("text_char_height", "문자 높이"),
        ("text_bold_toggle", "굵게하기"),
        ("text_italic_toggle", "기울이기"),
        ("text_strike_toggle", "취소선"),
        ("item_align_left", "왼쪽 정렬"),
        ("item_align_center", "중앙정렬"),
        ("item_align_right", "오른쪽 정렬"),
        ("item_text_color", "문자 색상 팔레트"),
        ("item_stroke_color", "획 색상 팔레트"),
        ("text_linebreak", "줄내림"),
        ("text_ellipsis", "말줄임표(…)"),
        ("text_horizontal_dash", "가로장음(―)"),
        ("text_vertical_dash", "세로장음(│)"),
        ("text_single_corner", "홑낫표(「」)"),
        ("text_double_corner", "겹낫표(『』)"),
        ("text_white_heart", "하얀하트(♡)"),
        ("text_black_heart", "검은하트(♥)"),
        ("text_music_note", "음표(♪)"),
        ("text_black_circle", "검은 동그라미(●)"),
        ("text_middle_dot", "가운뎃점(·)"),
    ]),
    ("텍스트 수정", [
        ("text_transform_toggle", "텍스트 변형"),
        ("text_effect_gradient", "고급 텍스트/획 옵션"),
        ("text_skew_toggle", "평행사변형 변형"),
        ("text_trapezoid_toggle", "사다리꼴 변형"),
        ("text_arc_toggle", "부채꼴 변형"),
        ("text_rasterize", "텍스트를 객체로 변환"),
        ("text_paste_same_position", "원위치 붙여넣기"),
    ]),
    ("프로젝트", [
        ("project_new", "새 프로젝트"),
        ("project_import_maker_game", "게임 가져오기"),
        ("project_maker_character_profiles", "캐릭터 프로필 보기"),
        ("project_open", "YSBG 열기"),
        ("project_open_json", "프로젝트 열기"),
        ("project_save", "내보내기"),
        ("project_recover_last_work", "복구하기"),
        ("project_show_launcher", "홈화면으로 가기"),
        ("project_exit", "프로젝트 나가기"),
    ]),
    ("작업", [
        ("work_source_compare", "원본 비교창 열기/끄기"),
        ("edit_undo", "텍스트 입력 취소"),
        ("edit_redo", "텍스트 입력 재실행"),
        ("work_page_prev", "이전 맵"),
        ("work_page_next", "다음 맵"),
        ("work_page_list", "맵 목록"),
        ("work_page_rename_source", "맵 탭 이름 변경"),
        ("work_page_delete_current", "현재 맵 탭 삭제"),
        ("work_open_current_project_folder", "현재 프로젝트의 작업 폴더로 이동하기"),
        ("work_scan_maker_game", "게임 분석"),
        ("paint_reanalyze", "재분석"),
        ("work_quick_ocr", "빠른 OCR 설정"),
        ("work_text_number_width", "텍스트 넘버 크기 변경"),
        ("work_translate", "번역"),
        ("work_restore_edge_control_codes_current", "맵 제어코드 복원"),
        ("work_inpaint", "인페인팅"),
        ("work_import_clean_background", "클린본 불러오기"),
        ("final_paint_to_background", "배경을 원본으로 쓰기"),
        ("work_restore_original_source", "원본으로 돌아가기"),
        ("work_extract_text", "원문/번역문 내보내기"),
        ("work_import_translation", "번역문 불러오기"),
        ("work_clear_translation", "번역문 내용 지우기"),
        ("work_clean_text", "텍스트 정리"),
        ("work_text_find", "텍스트 찾기"),
        ("work_text_replace", "텍스트 교체"),
        ("work_reset_text_rects", "현재 텍스트 기준으로 영역 재설정"),
        ("work_export", "출력"),
        ("work_output_preview", "출력 미리보기"),
        ("view_text_toggle", "텍스트 표시 ON/OFF"),
    ]),
    ("일괄 작업", [
        ("batch_analyze", "일괄 분석"),
        ("batch_reanalyze", "일괄 재분석"),
        ("batch_translate", "일괄 번역"),
        ("work_unify_translations", "번역 통일"),
        ("batch_restore_edge_control_codes", "일괄 맵 제어코드 복원"),
        ("batch_inpaint", "일괄 인페인팅"),
        ("batch_extract_text", "일괄 원문/번역문 내보내기"),
        ("batch_clear_translation", "일괄 번역문 내용 지우기"),
        ("batch_clean_text", "일괄 텍스트 정리"),
        ("batch_reset_text_rects", "일괄 현재 텍스트 기준으로 영역 재설정"),
        ("batch_export", "일괄 출력"),
        ("work_page_delete_all", "일괄 페이지탭 삭제"),
    ]),
    ("자동화 작업", [
        ("auto_text_size_current", "자동 텍스트 크기 조정"),
        ("auto_text_size_batch", "일괄 자동 텍스트 크기 조정"),
        ("auto_linebreak_current", "자동 줄 내림"),
        ("auto_linebreak_batch", "일괄 자동 줄 내림"),
    ]),
    ("DB번역", [
        ("option_maker_database_translation", "데이터베이스 모드"),
        ("db_maker_character_name_translation", "화자 번역"),
    ]),
    ("옵션", [
        ("option_api_settings", "API 관리"),
        ("option_shortcut_settings", "단축키 통합 관리"),
        ("option_macro_settings", "매크로 관리"),
        ("project_maker_character_profiles", "캐릭터 프로필 보기"),
        ("option_maker_character_prompts", "게임 프롬프트 관리"),
        ("option_glossary", "단어장"),
        ("option_maker_translation_settings", "줄내림 옵션"),
        ("option_maker_preview_display_settings", "게임 프리뷰 옵션"),
        ("option_maker_game_settings", "게임 설정"),
        ("option_maker_game_refresh", "게임 갱신"),
    ]),
    ("설정", [
        ("option_settings_overview", "설정 / 옵션"),
        ("option_theme_settings", "테마 설정"),
        ("option_language_settings", "언어 설정"),
        ("setting_page_tab_display_name", "맵 탭 표시명 설정"),
        ("setting_output_display_name", "출력 표시명 설정"),
        ("setting_output_options", "출력 옵션"),
        ("setting_interface_tooltips", "인터페이스 툴팁 표시"),
        ("setting_file_path_visibility", "파일 경로 표시"),
        ("option_shortcut_settings", "단축키 통합 관리"),
        ("option_macro_settings", "매크로 관리"),
        ("option_text_preset_settings", "페이지 글꼴 프리셋 관리"),
        ("option_item_text_preset_settings", "개별 글꼴 프리셋 관리"),
    ]),
    ("도움말", [
        ("help_program_manual", "프로그램 메뉴얼"),
        ("help_open_website", "YSB Tool 사이트로 가기"),
        ("help_report_bug", "버그제보 / 문의하기"),
        ("help_about", "프로그램 정보"),
    ]),
    ("기타", [
        ("quick_ocr_execute", "빠른 OCR 실행"),
    ]),
]



def shortcut_label_map() -> Dict[str, str]:
    result = {}
    for group_title, rows in tktool_phase2_visible_groups():
        for key, label in rows:
            result[key] = label
    return result


def shortcut_group_rows():
    rows = []
    for group_title, group_rows in tktool_phase2_visible_groups():
        for key, label in group_rows:
            rows.append((key, label, group_title))
    return rows


SHORTCUT_GROUP_SECTIONS = {
    "작업": [
        ("기본동작", ["work_source_compare", "edit_undo", "edit_redo", "work_open_current_project_folder", "work_export"]),
        ("페이지탭", ["work_page_prev", "work_page_next", "work_page_list", "work_page_full_name", "work_page_rename_source", "work_page_delete_current"]),
        ("작업류", ["work_scan_maker_game", "paint_reanalyze", "work_translate", "work_inpaint"]),
        ("텍스트 수정류", ["work_extract_text", "work_import_translation", "work_clear_translation", "work_clean_text", "work_text_find", "work_text_replace", "work_unify_translations"]),
        ("이미지 교체류", ["work_import_clean_background", "final_paint_to_background", "work_restore_original_source"]),
        ("기타 동작", ["work_quick_ocr", "work_text_number_width", "work_reset_text_rects", "work_output_preview"]),
    ],
    "일괄 작업": [
        ("기본 동작", ["batch_export"]),
        ("일괄 작업류", ["batch_analyze", "batch_reanalyze", "batch_translate", "batch_inpaint"]),
        ("텍스트 수정류", ["batch_extract_text", "batch_clear_translation", "batch_clean_text"]),
        ("기타 동작", ["batch_reset_text_rects", "work_page_delete_all"]),
    ],
}


def shortcut_section_rows(group_title: str, rows):
    rows = tktool_phase2_filter_rows(rows)
    row_map = {key: label for key, label in rows}
    used = set()
    sections = []
    predefined = SHORTCUT_GROUP_SECTIONS.get(group_title, [])
    for section_title, keys in predefined:
        section_rows = []
        for key in keys:
            if key in row_map:
                section_rows.append((key, row_map[key]))
                used.add(key)
        if section_rows:
            sections.append((section_title, section_rows))
    leftover = [(key, label) for key, label in rows if key not in used]
    if leftover:
        # 작업/일괄 작업처럼 별도 블록 구성을 가진 탭의 남은 항목만 기타 동작으로 보낸다.
        # 그 외 탭은 탭 이름 자체가 곧 큰 분류이므로 "그림판 관련 단축키"처럼 표시한다.
        sections.append(("기타 동작" if predefined else group_title, leftover))
    if not sections:
        sections.append((group_title, rows))
    return sections


@dataclass
class ShortcutSettings:
    shortcuts: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SHORTCUTS))
    enabled: Dict[str, bool] = field(default_factory=lambda: {k: True for k in DEFAULT_SHORTCUTS})
    macros: List[dict] = field(default_factory=list)
    migration_state: Dict[str, bool] = field(default_factory=dict)

    def is_enabled(self, key: str) -> bool:
        if not tktool_phase2_shortcut_allowed(key):
            return False
        if key in FIXED_SHORTCUT_KEYS:
            return True
        return bool(self.enabled.get(key, True))

    def seq(self, key: str) -> QKeySequence:
        if not tktool_phase2_shortcut_allowed(key):
            return QKeySequence("")
        if key in FIXED_SHORTCUT_KEYS:
            return key_sequence_from_text(DEFAULT_SHORTCUTS.get(key, ""))
        if not self.is_enabled(key):
            return QKeySequence("")
        return key_sequence_from_text(self.shortcuts.get(key, DEFAULT_SHORTCUTS.get(key, "")))

    def set_seq(self, key: str, seq: QKeySequence):
        if key in FIXED_SHORTCUT_KEYS:
            self.shortcuts[key] = DEFAULT_SHORTCUTS.get(key, "")
            return
        self.shortcuts[key] = key_sequence_to_portable(seq)

    def set_enabled(self, key: str, value: bool):
        if key in FIXED_SHORTCUT_KEYS:
            self.enabled[key] = True
            return
        self.enabled[key] = bool(value)


class ShortcutSettingsStore:
    @staticmethod
    def load() -> ShortcutSettings:
        p = cache_file()
        if not p.exists():
            return ShortcutSettings()
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            merged_shortcuts = dict(DEFAULT_SHORTCUTS)
            merged_enabled = {k: True for k in DEFAULT_SHORTCUTS}

            loaded_macros = []
            migration_state = {}
            migration_dirty = False

            if isinstance(data, dict):
                raw_shortcuts = data.get("shortcuts", data)
                raw_enabled = data.get("enabled", {})
                raw_macros = data.get("macros", [])
                raw_migration_state = data.get("migration_state", {})
                if isinstance(raw_macros, list):
                    loaded_macros = []
                    valid_keys = set(DEFAULT_SHORTCUTS.keys())
                    for m in raw_macros:
                        if not isinstance(m, dict):
                            continue
                        mm = dict(m)
                        mm["actions"] = [k for k in (mm.get("actions", []) or []) if k in valid_keys]
                        loaded_macros.append(mm)

                if isinstance(raw_shortcuts, dict):
                    merged_shortcuts.update({
                        k: str(v)
                        for k, v in raw_shortcuts.items()
                        if k in merged_shortcuts
                    })

                if isinstance(raw_enabled, dict):
                    merged_enabled.update({
                        k: bool(v)
                        for k, v in raw_enabled.items()
                        if k in merged_enabled
                    })

                if isinstance(raw_migration_state, dict):
                    migration_state.update({str(k): bool(v) for k, v in raw_migration_state.items()})

            # 기존 캐시에 남아 있는 + 계열 단축키는 새 기준인 = 계열로 자동 보정한다.
            if merged_shortcuts.get("item_font_inc") == "+":
                merged_shortcuts["item_font_inc"] = "="
            if merged_shortcuts.get("item_stroke_inc") == "Ctrl++":
                merged_shortcuts["item_stroke_inc"] = "Ctrl+="

            # 1.2 자동화 단축키가 Ctrl+B / Ctrl+Shift+B를 사용하므로,
            # 예전 기본값으로 남아 있던 번역문 불러오기 단축키는 비워 충돌을 피한다.
            if merged_shortcuts.get("work_import_translation") == "Ctrl+B":
                merged_shortcuts["work_import_translation"] = ""

            # v2.4 특수문자 입력 기본값을 새 표준으로 옮긴다.
            # 이 마이그레이션은 캐시당 1회만 실행한다. 이후 사용자가 일부러 예전 값을
            # 다시 지정해도 사용자 설정으로 보고 덮어쓰지 않는다.
            if not migration_state.get(SHIFT_SYMBOL_SHORTCUT_MIGRATION_KEY, False):
                symbol_shortcut_migration = {
                    "text_ellipsis": {"Ctrl+Q", "Ctrl+Alt+Q", "Ctrl+Alt+Shift+Q", "Alt+G"},
                    "text_horizontal_dash": {"Ctrl+W", "Ctrl+Alt+W", "Ctrl+Alt+Shift+W", "Alt+H"},
                    "text_vertical_dash": {"Ctrl+E", "Ctrl+Alt+E", "Ctrl+Alt+Shift+E", "Alt+J"},
                    "text_single_corner": {"Ctrl+R", "Ctrl+Alt+R", "Ctrl+Alt+Shift+R", "Alt+K"},
                    "text_double_corner": {"Ctrl+T", "Ctrl+Alt+T", "Ctrl+Alt+Shift+T", "Alt+L"},
                    "text_white_heart": {"Ctrl+Y", "Ctrl+Alt+Y", "Ctrl+Alt+Shift+Y", "Ctrl+Alt+Shift+H", "Alt+N"},
                    "text_black_heart": {"Ctrl+U", "Ctrl+Alt+U", "Ctrl+Alt+Shift+U", "Alt+M"},
                    "text_music_note": {"Ctrl+I", "Ctrl+Alt+I", "Ctrl+Alt+Shift+I", "Alt+,"},
                    "text_black_circle": {"Ctrl+O", "Ctrl+Alt+O", "Ctrl+Alt+Shift+O", "Alt+."},
                    "text_middle_dot": {"Ctrl+P", "Ctrl+Alt+P", "Ctrl+Alt+Shift+P", "Alt+/"},
                }
                for key, old_values in symbol_shortcut_migration.items():
                    current_value = str(merged_shortcuts.get(key) or "")
                    if current_value in old_values:
                        merged_shortcuts[key] = DEFAULT_SHORTCUTS.get(key, current_value)
                        migration_dirty = True
                migration_state[SHIFT_SYMBOL_SHORTCUT_MIGRATION_KEY] = True
                migration_dirty = True

            # v2.4 특수문자 입력을 Ctrl+숫자 계열로 재배치한다.
            # Shift 단독 계열은 한글 IME 조합과 충돌할 수 있으므로 텍스트 편집 중 특수문자에는 쓰지 않는다.
            # 이 마이그레이션도 캐시당 1회만 실행한다. 이후 사용자 수정값은 덮어쓰지 않는다.
            if not migration_state.get(CTRL_NUMBER_SYMBOL_SHORTCUT_MIGRATION_KEY, False):
                ctrl_number_shortcut_migration = {
                    # 기존 Shift 기본값 / 예전 Ctrl+Alt 기본값 / 방금 전 Ctrl+숫자 충돌값까지 새 기본값으로 이동
                    "text_ellipsis": {"Shift+G", "Alt+G", "Ctrl+Q", "Ctrl+Alt+Q", "Ctrl+Alt+Shift+Q"},
                    "text_horizontal_dash": {"Shift+H", "Alt+H", "Ctrl+W", "Ctrl+Alt+W", "Ctrl+Alt+Shift+W"},
                    "text_vertical_dash": {"Shift+J", "Alt+J", "Ctrl+E", "Ctrl+Alt+E", "Ctrl+Alt+Shift+E"},
                    "text_single_corner": {"Shift+K", "Alt+K", "Ctrl+R", "Ctrl+Alt+R", "Ctrl+Alt+Shift+R"},
                    "text_double_corner": {"Shift+L", "Alt+L", "Ctrl+T", "Ctrl+Alt+T", "Ctrl+Alt+Shift+T"},
                    "text_white_heart": {"Shift+N", "Alt+N", "Ctrl+Y", "Ctrl+Alt+Y", "Ctrl+Alt+Shift+Y", "Ctrl+Alt+Shift+H"},
                    "text_black_heart": {"Shift+M", "Alt+M", "Ctrl+U", "Ctrl+Alt+U", "Ctrl+Alt+Shift+U"},
                    "text_music_note": {"Shift+,", "Alt+,", "Ctrl+I", "Ctrl+Alt+I", "Ctrl+Alt+Shift+I"},
                    "text_black_circle": {"Shift+.", "Alt+.", "Ctrl+O", "Ctrl+Alt+O", "Ctrl+Alt+Shift+O"},
                    "text_middle_dot": {"Shift+/", "Alt+/", "Ctrl+P", "Ctrl+Alt+P", "Ctrl+Alt+Shift+P"},
                    "text_effect_gradient": {"Ctrl+1"},
                    "text_skew_toggle": {"Ctrl+2"},
                    "text_trapezoid_toggle": {"Ctrl+3"},
                    "text_arc_toggle": {"Ctrl+4"},
                    "item_align_left": {"Ctrl+5"},
                    "item_align_center": {"Ctrl+6"},
                    "item_align_right": {"Ctrl+7"},
                }
                for key, old_values in ctrl_number_shortcut_migration.items():
                    current_value = str(merged_shortcuts.get(key) or "")
                    if current_value in old_values:
                        merged_shortcuts[key] = DEFAULT_SHORTCUTS.get(key, current_value)
                        migration_dirty = True
                migration_state[CTRL_NUMBER_SYMBOL_SHORTCUT_MIGRATION_KEY] = True
                migration_dirty = True

            # 특수문자 새 기본 단축키와 겹치는 기존 기능은 자동 이동한다.
            if merged_shortcuts.get("option_theme_settings") in {"Ctrl+Alt+Shift+T", "Ctrl+Alt+T"}:
                merged_shortcuts["option_theme_settings"] = DEFAULT_SHORTCUTS.get("option_theme_settings", "Ctrl+Alt+Shift+2")
            if merged_shortcuts.get("work_clean_text") in {"Ctrl+Y", "Ctrl+Alt+Shift+Y"}:
                merged_shortcuts["work_clean_text"] = "Ctrl+Alt+Shift+C"

            # v1.8.1 마스크 커팅 도구 추가:
            # C는 마스크 커팅으로 이동하고, 기존 C였던 최종 페인팅 색상은 Ctrl+Shift+C로 이동한다.
            if merged_shortcuts.get("paint_mask_cut") in ("", None):
                merged_shortcuts["paint_mask_cut"] = DEFAULT_SHORTCUTS.get("paint_mask_cut", "C")
            if merged_shortcuts.get("final_paint_color") == "C":
                merged_shortcuts["final_paint_color"] = DEFAULT_SHORTCUTS.get("final_paint_color", "Ctrl+Shift+C")
            if merged_shortcuts.get("paint_mask_wrap_rect") == "R":
                merged_shortcuts["paint_mask_wrap_rect"] = DEFAULT_SHORTCUTS.get("paint_mask_wrap_rect", "Alt+Shift+R")
            if merged_shortcuts.get("paint_mask_wrap_free") == "F":
                merged_shortcuts["paint_mask_wrap_free"] = DEFAULT_SHORTCUTS.get("paint_mask_wrap_free", "Alt+F")

            # v2.0.1 맵 탭 단축키 보정:
            # Ctrl+Q는 현재 맵 탭 삭제, Ctrl+Shift+Q는 일괄 페이지탭 삭제,
            # 프로젝트 나가기는 Alt+Q로 이동한다.
            page_tab_shortcut_defaults = {
                "work_page_list": "Ctrl+Alt+F",
                "work_page_full_name": "Alt+V",
                "work_page_rename_source": "Ctrl+F2",
                "work_page_delete_current": "Ctrl+Q",
                "work_page_delete_all": "Ctrl+Shift+Q",
                "project_exit": "Alt+Q",
                "project_import_maker_game": "Alt+O",
    "project_import_images": "Alt+O",  # legacy alias
            }
            for _key, _fallback in page_tab_shortcut_defaults.items():
                if merged_shortcuts.get(_key) in ("", None):
                    merged_shortcuts[_key] = DEFAULT_SHORTCUTS.get(_key, _fallback)

            # 구버전에서 project_exit가 Ctrl+Q를 점유하고 있었으면 Alt+Q로 이동한다.
            if str(merged_shortcuts.get("project_exit") or "") == "Ctrl+Q":
                merged_shortcuts["project_exit"] = "Alt+Q"

            for _reserved_key, _reserved_value in page_tab_shortcut_defaults.items():
                if not str(_reserved_value or ""):
                    continue
                for _key, _value in list(merged_shortcuts.items()):
                    if _key != _reserved_key and str(_value) == _reserved_value:
                        merged_shortcuts[_key] = DEFAULT_SHORTCUTS.get(_key, "")
                        if str(merged_shortcuts.get(_key) or "") == _reserved_value:
                            merged_shortcuts[_key] = ""

            # v1.0.0 Game Editor: Ctrl+F는 텍스트 찾기로 사용한다.
            merged_shortcuts["work_page_list"] = "Ctrl+Alt+F"
            merged_shortcuts["work_text_find"] = "Ctrl+F"
            merged_shortcuts["work_text_replace"] = "Ctrl+H"
            merged_shortcuts["work_unify_translations"] = "Ctrl+Alt+U"
            merged_shortcuts["work_page_full_name"] = "Alt+V"
            merged_shortcuts["work_page_rename_source"] = "Ctrl+F2"
            merged_shortcuts["work_page_delete_current"] = "Ctrl+Q"
            merged_shortcuts["work_page_delete_all"] = "Ctrl+Shift+Q"
            merged_shortcuts["project_exit"] = "Alt+Q"
            merged_shortcuts["project_import_maker_game"] = "Alt+O"
            merged_shortcuts["project_import_images"] = "Alt+O"
            merged_shortcuts["project_save"] = "Ctrl+E"
            merged_shortcuts["project_save_as"] = ""
            merged_shortcuts["work_restore_edge_control_codes_current"] = "Ctrl+B"
            merged_shortcuts["batch_restore_edge_control_codes"] = "Ctrl+Shift+B"
            merged_shortcuts["work_unify_translations"] = "Ctrl+Shift+T"
            merged_shortcuts["option_maker_database_translation"] = "Ctrl+D"
            merged_shortcuts["db_maker_character_name_translation"] = "Ctrl+G"
            merged_shortcuts["option_api_settings"] = "Ctrl+Alt+1"
            merged_shortcuts["option_shortcut_settings"] = "Ctrl+Alt+2"
            merged_shortcuts["option_macro_settings"] = "Ctrl+Alt+3"
            merged_shortcuts["project_maker_character_profiles"] = "Ctrl+Alt+4"
            merged_shortcuts["option_maker_character_prompts"] = "Ctrl+Alt+5"
            merged_shortcuts["option_glossary"] = "Ctrl+Alt+6"
            merged_shortcuts["option_maker_translation_settings"] = "Ctrl+Alt+7"
            merged_shortcuts["option_maker_preview_display_settings"] = "Ctrl+Alt+8"
            merged_shortcuts["option_maker_game_settings"] = "Ctrl+Alt+9"
            merged_shortcuts["option_maker_game_refresh"] = "Ctrl+Alt+0"
            merged_shortcuts["option_translation_prompt"] = ""
            merged_shortcuts["debug_maker_tile_preview_diagnose"] = ""
            merged_shortcuts["debug_maker_database_scan"] = ""
            merged_shortcuts["debug_maker_database_layer_rebuild"] = ""
            merged_shortcuts["option_workspace_reset_default"] = ""
            merged_shortcuts["auto_text_size_current"] = ""
            merged_shortcuts["auto_text_size_batch"] = ""

            # v2.0.1 hotfix50: Options / Settings menu shortcut layout.
            # Options: main 7 items use Ctrl+Alt+1~7 in visible order.
            option_menu_shortcut_layout = {
                "option_api_settings": "Ctrl+Alt+1",
                "option_shortcut_settings": "Ctrl+Alt+2",
                "option_macro_settings": "Ctrl+Alt+3",
                "project_maker_character_profiles": "Ctrl+Alt+4",
                "option_maker_character_prompts": "Ctrl+Alt+5",
                "option_glossary": "Ctrl+Alt+6",
                "option_maker_translation_settings": "Ctrl+Alt+7",
                "option_maker_preview_display_settings": "Ctrl+Alt+8",
                "option_maker_game_settings": "Ctrl+Alt+9",
                "option_maker_game_refresh": "Ctrl+Alt+0",
                "option_translation_prompt": "",
                "debug_maker_tile_preview_diagnose": "",
                "debug_maker_database_scan": "",
                "debug_maker_database_layer_rebuild": "",
                "option_maker_refresh_runtime_profile": "",
                "option_maker_game_font_settings": "",
                "option_maker_title_settings": "",
                "option_text_preset_settings": "",
                "option_item_text_preset_settings": "",
                "option_analysis_mask_settings": "",
                "option_ocr_analysis_regions": "",
                "option_cleanup_outputs": "",
            }
                        # Settings: keep visible order and use Ctrl+Alt+Shift+1~9.
            settings_menu_shortcut_layout = {
                "option_theme_settings": "Ctrl+Alt+Shift+2",
                "option_language_settings": "Ctrl+Alt+Shift+3",
                "setting_page_tab_display_name": "Ctrl+Alt+Shift+4",
                "setting_output_display_name": "Ctrl+Alt+Shift+5",
                "option_workspace_location": "Ctrl+Alt+Shift+6",
                "option_cleanup_temp_files": "Ctrl+Alt+Shift+7",
                "option_workspace_size_manager": "Ctrl+Alt+Shift+-",
                "setting_output_options": "Ctrl+Alt+Shift+=",
                "setting_interface_tooltips": "Ctrl+Alt+Shift+1",
                "option_register_ysb": "Ctrl+Alt+Shift+8",
                "option_unregister_ysbt": "Ctrl+Alt+Shift+9",
                "setting_file_path_visibility": "Ctrl+Alt+Shift+0",
            }
            for _key, _value in {
                **option_menu_shortcut_layout,
                **settings_menu_shortcut_layout,
            }.items():
                if _key in merged_shortcuts:
                    merged_shortcuts[_key] = _value

            # v2.2.0 hotfix: 단축키 관리의 글꼴 탭 기본값을 새 표준으로 정리한다.
            font_shortcut_layout = {
                "item_font_select": "F1",
                "text_font_size": "Ctrl+Alt+A",
                "item_font_inc": "=",
                "item_font_dec": "-",
                "text_stroke_size": "Ctrl+Alt+S",
                "item_stroke_inc": "Ctrl+=",
                "item_stroke_dec": "Ctrl+-",
                "text_line_spacing": "Ctrl+Alt+Q",
                "text_letter_spacing": "Ctrl+Alt+W",
                "text_char_width": "Ctrl+Alt+E",
                "text_char_height": "Ctrl+Alt+R",
                "text_bold_toggle": "Ctrl+Alt+B",
                "text_italic_toggle": "Ctrl+Alt+M",
                "text_strike_toggle": "Ctrl+Alt+N",
                "text_transform_toggle": "Ctrl+T",
                "text_effect_gradient": "Shift+G",
                "text_skew_toggle": "Shift+H",
                "text_trapezoid_toggle": "Shift+J",
                "text_arc_toggle": "Shift+K",
                "text_rasterize": "Ctrl+Alt+K",
                "item_align_left": "Shift+,",
                "item_align_center": "Shift+.",
                "item_align_right": "Shift+/",
                "item_text_color": "F6",
                "item_stroke_color": "F7",
            }
            # 기존 구버전 보정값이다. v2.4에서 사용자가 새 단축키를 직접 바꿀 수 있도록
            # 텍스트 변형/정렬 7개는 위의 1회 마이그레이션 이후에는 강제 고정하지 않는다.
            _user_editable_v24_keys = {
                "text_effect_gradient", "text_skew_toggle", "text_trapezoid_toggle", "text_arc_toggle",
                "item_align_left", "item_align_center", "item_align_right",
            }
            for _key, _value in font_shortcut_layout.items():
                if _key in merged_shortcuts and _key not in _user_editable_v24_keys:
                    merged_shortcuts[_key] = _value

            # v2.2.0 작업 메뉴 재분류/신규 도구 단축키 표준값.
            # v2.4.x: 인페인팅/클린본/최종 페인팅 원본 반영은 Alt+P '배경을 원본으로 쓰기'로 통합한다.
            if "work_inpaint_source" in merged_shortcuts and str(merged_shortcuts.get("work_inpaint_source") or "") == "Ctrl+Alt+P":
                merged_shortcuts["work_inpaint_source"] = ""
            if "final_paint_to_background" in merged_shortcuts:
                merged_shortcuts["final_paint_to_background"] = "Alt+P"
            if "paint_area_fill" in merged_shortcuts and not str(merged_shortcuts.get("paint_area_fill") or ""):
                merged_shortcuts["paint_area_fill"] = "J"
            if "text_transform_toggle" in merged_shortcuts:
                merged_shortcuts["text_transform_toggle"] = "Ctrl+T"
            if "view_text_toggle" in merged_shortcuts and merged_shortcuts.get("view_text_toggle") in {"Ctrl+T", "", None}:
                merged_shortcuts["view_text_toggle"] = "Ctrl+Alt+V"

            # v1.8.1 마스크 커팅 단축키 보정:
            # Alt+D는 사각형 영역으로 이동하고, 기존 Alt+D였던 마스킹 칠하기는 Alt+Shift+D로 이동한다.
            if merged_shortcuts.get("paint_magic_fill") == "Alt+D":
                merged_shortcuts["paint_magic_fill"] = DEFAULT_SHORTCUTS.get("paint_magic_fill", "Alt+Shift+D")
            if merged_shortcuts.get("paint_mask_wrap_rect") in ("R", "Alt+Shift+R", "", None):
                merged_shortcuts["paint_mask_wrap_rect"] = DEFAULT_SHORTCUTS.get("paint_mask_wrap_rect", "Alt+D")

            # Fixed shortcuts are reserved by the editor itself. User cache values cannot override them.
            for _key in FIXED_SHORTCUT_KEYS:
                merged_shortcuts[_key] = DEFAULT_SHORTCUTS.get(_key, "")
                merged_enabled[_key] = True

            # 비활성화된 단축키는 입력칸/동작에서 빠진 상태로 유지한다.
            for key in list(merged_shortcuts.keys()):
                if key in FIXED_SHORTCUT_KEYS:
                    continue
                if not merged_enabled.get(key, True):
                    merged_shortcuts[key] = ""

            result = enforce_fixed_shortcuts(ShortcutSettings(merged_shortcuts, merged_enabled, loaded_macros, migration_state))
            if migration_dirty:
                try:
                    ShortcutSettingsStore.save(result)
                except Exception:
                    pass
            return result
        except Exception:
            return enforce_fixed_shortcuts(ShortcutSettings())

    @staticmethod
    def save(settings: ShortcutSettings):
        settings = enforce_fixed_shortcuts(settings)
        p = cache_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(asdict(settings), f, ensure_ascii=False, indent=2)

    @staticmethod
    def cache_path() -> str:
        return str(cache_file())



class MacroFunctionSelectDialog(QDialog):
    def __init__(self, current_actions=None, settings: ShortcutSettings = None, parent=None):
        super().__init__(parent)
        self._ui_language = resolve_ui_language(parent)
        self.setWindowTitle(tr_text("매크로 기능 선택", self._ui_language))
        self.resize(720, 720)
        self._ui_theme = resolve_ui_theme(parent)
        self.setStyleSheet(shortcut_dialog_qss(self._ui_theme))

        self.settings = settings or ShortcutSettings()
        self.label_map = shortcut_label_map()
        self.current_actions = list(current_actions or [])
        self.rows = shortcut_group_rows()
        self.shortcut_to_key = {}
        self._refreshing_search = False

        layout = QVBoxLayout(self)

        title = QLabel(tr_text("현재 매크로 기능", self._ui_language))
        title.setStyleSheet("font-weight:bold;")
        layout.addWidget(title)

        self.current_box = QScrollArea()
        self.current_box.setWidgetResizable(True)
        self.current_box.setMinimumHeight(92)
        self.current_inner = QWidget()
        self.current_grid = QGridLayout(self.current_inner)
        self.current_grid.setContentsMargins(6, 6, 6, 6)
        self.current_grid.setSpacing(6)
        self.current_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.current_box.setWidget(self.current_inner)
        layout.addWidget(self.current_box)

        help_label = QLabel(tr_text("기능은 더블클릭하거나 검색창/목록에 포커스를 둔 상태에서 실제 단축키를 눌러 추가합니다. Enter는 기능 추가가 아니라 확인으로 동작합니다. 확인을 누르면 현재 매크로 기능 목록을 저장하고, 닫기를 누르면 저장하지 않고 나갑니다. 단축키 OFF/없음은 단축키 상태 표시일 뿐, 매크로 실행에는 영향 없습니다.", self._ui_language))
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.search = QLineEdit()
        self.search.setPlaceholderText(tr_text("기능명 / 그룹 / 단축키 검색  예: 자동 줄 내림, Ctrl+B", self._ui_language))
        layout.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.list_widget, 1)

        btn_line = QHBoxLayout()
        self.btn_ok = QPushButton(tr_text("확인", self._ui_language))
        self.btn_close = QPushButton(tr_text("닫기", self._ui_language))
        btn_line.addStretch()
        btn_line.addWidget(self.btn_ok)
        btn_line.addWidget(self.btn_close)
        layout.addLayout(btn_line)

        self.btn_ok.setDefault(True)
        self.btn_ok.setAutoDefault(True)
        self.btn_close.setAutoDefault(False)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_close.clicked.connect(self.reject)
        self.search.textChanged.connect(self.refill)
        # Enter는 기능 추가가 아니라 확인으로 동작한다.
        self.search.returnPressed.connect(self.accept)
        self.list_widget.itemDoubleClicked.connect(lambda item: self.add_key(item.data(Qt.ItemDataRole.UserRole)))

        # 검색창에서 Ctrl+F5/F5/Alt+D처럼 실제 단축키를 누르면 즉시 기능으로 추가한다.
        # QLineEdit가 키를 문자로 처리하기 전에 잡아야 하므로 eventFilter를 붙인다.
        self.search.installEventFilter(self)
        self.list_widget.installEventFilter(self)

        self.build_shortcut_index()
        self.refill()
        self.refresh_current_actions()

    def collect_extra_shortcut_references(self):
        records = []
        seen = set()

        for idx, macro in enumerate(getattr(self.settings, "macros", []) or []):
            if not macro.get("enabled", True):
                continue
            shortcut = str(macro.get("shortcut", "") or "").strip()
            if not shortcut:
                continue
            try:
                seq = key_sequence_from_text(shortcut)
                display_shortcut = seq.toString(QKeySequence.SequenceFormat.NativeText) or shortcut
            except Exception:
                display_shortcut = shortcut
            name = str(macro.get("name") or "매크로").strip() or "매크로"
            key = f"__macro__:{idx}:{name}"
            records.append({
                "key": key,
                "label": f"매크로: {name}",
                "shortcut": display_shortcut,
                "description": "매크로 관리에서 등록한 사용자 매크로 단축키입니다.",
            })
            seen.add(key)

        parent = self.parent()
        item_presets = getattr(parent, "item_text_presets", {}) if parent is not None else {}
        if isinstance(item_presets, dict):
            for name, preset in sorted(item_presets.items(), key=lambda x: str(x[0])):
                if not isinstance(preset, dict):
                    continue
                if not preset.get("enabled", True):
                    continue
                shortcut = str(preset.get("shortcut", "") or "").strip()
                if not shortcut:
                    continue
                try:
                    seq = key_sequence_from_text(shortcut)
                    display_shortcut = seq.toString(QKeySequence.SequenceFormat.NativeText) or shortcut
                except Exception:
                    display_shortcut = shortcut
                label_name = str(name)
                key = f"__item_preset__:{label_name}"
                records.append({
                    "key": key,
                    "label": f"개별 글꼴 프리셋: {label_name}",
                    "shortcut": display_shortcut,
                    "description": "개별 글꼴 프리셋 관리에서 등록한 사용자 단축키입니다.",
                })
                seen.add(key)

        return records



    def normalize_shortcut_text(self, value):
        value = str(value or "").strip()
        if not value:
            return ""

        # QKeySequence가 구두점 단축키(Ctrl+, / Ctrl+; 등)를
        # 환경에 따라 빈 문자열/다른 표기로 바꾸는 경우가 있어 수동 정규화도 같이 한다.
        compact = (
            value.replace(" ", "")
            .replace("Control+", "Ctrl+")
            .replace("control+", "ctrl+")
            .replace("CTRL+", "Ctrl+")
        )
        try:
            converted = QKeySequence(compact).toString(QKeySequence.SequenceFormat.PortableText)
            if converted:
                compact = converted.replace(" ", "")
        except Exception:
            pass
        return compact.lower()

    def key_token_from_event(self, event):
        key_code = event.key()

        punct = {
            Qt.Key.Key_Comma: ",",
            Qt.Key.Key_Period: ".",
            Qt.Key.Key_Semicolon: ";",
            Qt.Key.Key_Apostrophe: "'",
            Qt.Key.Key_Slash: "/",
            Qt.Key.Key_Backslash: "\\",
            Qt.Key.Key_BracketLeft: "[",
            Qt.Key.Key_BracketRight: "]",
            Qt.Key.Key_Minus: "-",
            Qt.Key.Key_Equal: "=",
            Qt.Key.Key_Plus: "+",
            Qt.Key.Key_QuoteDbl: '"',
            Qt.Key.Key_Colon: ":",
        }
        if key_code in punct:
            return punct[key_code]

        # F1~F35
        try:
            key_int = int(key_code)
        except Exception:
            try:
                key_int = key_code.value
            except Exception:
                key_int = 0

        for n in range(1, 36):
            if key_code == getattr(Qt.Key, f"Key_F{n}", None):
                return f"F{n}"

        # 문자/숫자
        txt = event.text()
        if txt and len(txt) == 1 and txt.isprintable():
            return txt.upper()

        return QKeySequence(key_code).toString(QKeySequence.SequenceFormat.PortableText)

    def shortcut_candidates_from_event(self, event):
        key_code = event.key()
        if key_code in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_unknown,
        ):
            return set()

        try:
            mods_value = event.modifiers().value
        except AttributeError:
            mods_value = int(event.modifiers())

        candidates = set()

        # Qt 기본 변환 후보
        try:
            pressed = QKeySequence(mods_value | key_code)
            portable = pressed.toString(QKeySequence.SequenceFormat.PortableText)
            native = pressed.toString(QKeySequence.SequenceFormat.NativeText)
            if portable:
                candidates.add(self.normalize_shortcut_text(portable))
            if native:
                candidates.add(self.normalize_shortcut_text(native))
        except Exception:
            pass

        # 구두점/특수키 수동 변환 후보
        mods = event.modifiers()
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("Meta")

        token = self.key_token_from_event(event)
        if token:
            manual = "+".join(parts + [token]) if parts else token
            candidates.add(self.normalize_shortcut_text(manual))

        return {c for c in candidates if c}

    def is_shortcut_enabled_for_key(self, key):
        return bool(self.settings.enabled.get(key, True))

    def display_shortcut_for_key(self, key):
        if not self.is_shortcut_enabled_for_key(key):
            return ""
        seq = self.settings.seq(key)
        if not seq or seq.isEmpty():
            return ""
        return seq.toString(QKeySequence.SequenceFormat.NativeText)

    def portable_shortcut_for_key(self, key):
        if not self.is_shortcut_enabled_for_key(key):
            return ""
        seq = self.settings.seq(key)
        if not seq or seq.isEmpty():
            return ""
        return seq.toString(QKeySequence.SequenceFormat.PortableText)

    def status_text_for_key(self, key):
        # 이 상태는 "기능 실행 가능 여부"가 아니라 "단축키 등록 상태"만 의미한다.
        # 매크로는 기능 key를 직접 실행하므로 단축키 OFF여도 매크로 안에서는 실행된다.
        if not self.is_shortcut_enabled_for_key(key):
            return "단축키 OFF"
        if not self.display_shortcut_for_key(key):
            return "단축키 없음"
        return "단축키 ON"

    def build_shortcut_index(self):
        self.shortcut_to_key = {}
        for key, label, group_title in self.rows:
            portable = self.portable_shortcut_for_key(key)
            norm = self.normalize_shortcut_text(portable)
            if norm:
                self.shortcut_to_key[norm] = key

    def refresh_current_actions(self):
        while self.current_grid.count():
            item = self.current_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self.current_actions:
            lab = QLabel(tr_text("아직 추가된 기능이 없습니다.", self._ui_language))
            lab.setStyleSheet("color:#5f6673;" if self._ui_theme == THEME_LIGHT else "color:#bfc3cc;")
            self.current_grid.addWidget(lab, 0, 0)
            return

        max_cols = 3
        for i, key in enumerate(self.current_actions):
            label = tr_text(self.label_map.get(key, key), self._ui_language)
            sk = self.display_shortcut_for_key(key)
            status = self.status_text_for_key(key)
            extra = f" / {sk}" if sk else f" / {tr_text(status, self._ui_language)}"
            btn = QPushButton(f"{i + 1}. {label}{extra}  ×")
            btn.setToolTip(tr_text("클릭하면 이 기능을 매크로에서 제거합니다.", self._ui_language))

            if self._ui_theme == THEME_LIGHT:
                if status == "단축키 ON":
                    bg = "#FBF5F6"
                    border = "#D7A3A9"
                    hover = "#F5E8EA"
                    color = "#202124"
                elif status == "단축키 OFF":
                    bg = "#f7f2e4"
                    border = "#d1bd83"
                    hover = "#f3ead0"
                    color = "#5b4a12"
                else:
                    bg = "#F5EFF3"
                    border = "#D4CCD2"
                    hover = "#EEEFF3"
                    color = "#404651"
            elif status == "단축키 ON":
                bg = "#332B30"
                border = "#8A4A52"
                hover = "#5B3136"
                color = "#ffffff"
            elif status == "단축키 OFF":
                bg = "#37342c"
                border = "#756a4b"
                hover = "#474230"
                color = "#efe5bd"
            else:
                bg = "#322E34"
                border = "#5E565D"
                hover = "#443A40"
                color = "#d8d8d8"

            btn.setStyleSheet(
                "QPushButton {"
                f"background:{bg};"
                f"border:1px solid {border};"
                "border-radius:0px;"
                "padding:7px 11px;"
                f"color:{color};"
                "}"
                f"QPushButton:hover {{ background:{hover}; }}"
            )
            btn.clicked.connect(lambda checked=False, idx=i: self.remove_action_at(idx))
            self.current_grid.addWidget(btn, i // max_cols, i % max_cols)

    def remove_action_at(self, index):
        if 0 <= index < len(self.current_actions):
            removed = self.current_actions.pop(index)
            self.refresh_current_actions()

    def refill(self):
        query = self.search.text().strip().lower()
        self.list_widget.clear()

        for key, label, group_title in self.rows:
            native_shortcut = self.display_shortcut_for_key(key)
            portable_shortcut = self.portable_shortcut_for_key(key)
            status = self.status_text_for_key(key)
            d_label = tr_text(label, self._ui_language)
            d_group = tr_text(group_title, self._ui_language)
            d_status = tr_text(status, self._ui_language)
            hay = f"{label} {d_label} {key} {group_title} {d_group} {native_shortcut} {portable_shortcut} {status} {d_status}".lower()
            if query and query not in hay:
                continue

            shortcut_part = f" / {native_shortcut}" if native_shortcut else ""
            item = QListWidgetItem(f"[{d_status}] [{d_group}] {d_label}{shortcut_part}  ({key})")
            item.setData(Qt.ItemDataRole.UserRole, key)
            if status != "단축키 ON":
                item.setForeground(Qt.GlobalColor.gray)
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def key_from_key_event(self, event):
        candidates = self.shortcut_candidates_from_event(event)
        if not candidates:
            return None

        # 실제 현재 단축키 설정과 1:1로 비교한다.
        # Ctrl+, / Ctrl+; 같은 구두점 단축키는 Qt matches만으로 놓치는 경우가 있어
        # PortableText/NativeText/수동 후보를 모두 비교한다.
        for key, label, group_title in self.rows:
            if not self.settings.enabled.get(key, True):
                continue
            seq = self.settings.seq(key)
            if not seq or seq.isEmpty():
                continue

            try:
                pressed = QKeySequence(event.modifiers().value | event.key())
                if pressed.matches(seq) == QKeySequence.SequenceMatch.ExactMatch:
                    return key
            except Exception:
                pass

            seq_candidates = {
                self.normalize_shortcut_text(seq.toString(QKeySequence.SequenceFormat.PortableText)),
                self.normalize_shortcut_text(seq.toString(QKeySequence.SequenceFormat.NativeText)),
            }
            if candidates.intersection(seq_candidates):
                return key

        return None

    def handle_shortcut_key_event(self, event):
        key = self.key_from_key_event(event)
        if not key:
            return False
        self.add_key(key)
        self.search.clear()
        return True

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                event.accept()
                return True
            if self.key_from_key_event(event):
                event.accept()
                return True

        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.accept()
                return True
            if self.handle_shortcut_key_event(event):
                return True

        return super().eventFilter(obj, event)

    def add_exact_shortcut_from_search(self):
        # Enter는 "현재 선택된 첫 항목"을 멋대로 추가하지 않는다.
        # 검색어가 정확히 단축키로 인식될 때만 추가해서 이동 같은 엉뚱한 블록이 쌓이는 문제를 막는다.
        text = self.search.text().strip()
        norm = self.normalize_shortcut_text(text)
        key = self.shortcut_to_key.get(norm)
        if key:
            self.add_key(key)
            self.search.clear()
            return True

        QMessageBox.information(self, tr_text("기능 선택", self._ui_language), tr_text("정확히 일치하는 단축키가 없습니다. 기능명 검색 후 항목을 더블클릭하거나 실제 단축키를 눌러주세요.", self._ui_language))
        return False

    def add_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(self, tr_text("기능 선택", self._ui_language), tr_text("추가할 기능을 선택해주세요.", self._ui_language))
            return
        self.add_key(item.data(Qt.ItemDataRole.UserRole))

    def add_key(self, key):
        if not key:
            return
        self.current_actions.append(key)
        self.refresh_current_actions()

    def closeEvent(self, event):
        self.reject()
        event.accept()

    def get_actions(self):
        return list(self.current_actions)


class MacroSettingsDialog(QDialog):
    def __init__(self, settings: ShortcutSettings, parent=None):
        super().__init__(parent)
        self._ui_language = resolve_ui_language(parent)
        self.setWindowTitle(tr_text("매크로 관리", self._ui_language))
        self.resize(900, 560)
        self.settings = ShortcutSettings(
            dict(settings.shortcuts),
            {k: bool(settings.enabled.get(k, True)) for k in DEFAULT_SHORTCUTS},
            [dict(m) for m in getattr(settings, "macros", [])],
            dict(getattr(settings, "migration_state", {}) or {}),
        )
        self.label_map = shortcut_label_map()
        self.rows = []
        self._handling = False
        # 매크로 입력 중 개별 글꼴 프리셋과 충돌을 허용한 경우,
        # 실제 비활성화는 OK로 저장할 때 메인 창에서 적용한다.
        self._pending_disabled_item_presets = set()

        self._ui_theme = resolve_ui_theme(parent)
        self.setStyleSheet(shortcut_dialog_qss(self._ui_theme))

        root = QVBoxLayout(self)
        info = QLabel(tr_text(
            "매크로는 여러 기능을 추가한 순서대로 연속 실행합니다.\n"
            "매크로 단축키가 기존 단축키와 겹치면, 확인 후 기존 단축키를 비활성화합니다.",
            self._ui_language,
        ))
        info.setWordWrap(True)
        root.addWidget(info)

        add_btn = QPushButton(tr_text("매크로 추가", self._ui_language))
        add_btn.clicked.connect(self.add_macro)
        root.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.inner = QWidget()
        self.grid = QGridLayout(self.inner)
        self.grid.setColumnStretch(2, 1)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.inner)
        root.addWidget(self.scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr_text("닫기", self._ui_language))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.refill()

    def macro_label(self, actions):
        names = [tr_text(self.label_map.get(k, k), self._ui_language) for k in actions]
        return " + ".join(names) if names else tr_text("기능 없음", self._ui_language)

    def normalized_macros(self):
        result = []
        for row in self.rows:
            name = row["name"].text().strip() or tr_text("새 매크로", self._ui_language)
            enabled = bool(row["enabled"].isChecked())
            seq = row["seq"].keySequence().toString(QKeySequence.SequenceFormat.PortableText) if enabled else ""
            actions = [k for k in list(row.get("actions", [])) if tktool_phase2_macro_action_allowed(k)]
            result.append({
                "enabled": enabled,
                "name": name,
                "shortcut": seq,
                "actions": actions,
            })
        return result

    def refill(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.rows = []

        headers = ["사용", "이름", "기능", "단축키", ""]
        for c, h in enumerate(headers):
            lab = QLabel(tr_text(h, self._ui_language) if h else "")
            lab.setStyleSheet("font-weight:bold;")
            self.grid.addWidget(lab, 0, c)

        macros = getattr(self.settings, "macros", []) or []
        for macro in macros:
            self.add_macro_row(macro)

    def add_macro(self):
        name, ok = QInputDialog.getText(self, tr_text("매크로 추가", self._ui_language), tr_text("매크로 이름:", self._ui_language))
        if not ok:
            return
        name = name.strip() or tr_text("새 매크로", self._ui_language)
        self.add_macro_row({"enabled": True, "name": name, "shortcut": "", "actions": []})

    def apply_macro_row_enabled_state(self, row_data, enabled):
        for key in ("name", "function_btn", "seq"):
            w = row_data.get(key)
            if w:
                w.setEnabled(enabled)

        seq = row_data.get("seq")
        if seq:
            if enabled:
                seq.setStyleSheet("")
            else:
                seq.setStyleSheet(
                    "QKeySequenceEdit {"
                    "background:#4a2f2f;"
                    "color:#bdbdbd;"
                    "border:1px solid #8a5555;"
                    "}"
                )

        name = row_data.get("name")
        function_btn = row_data.get("function_btn")
        if name:
            name.setStyleSheet("" if enabled else "QLineEdit { background:#3b3030; color:#bdbdbd; border:1px solid #6a4a4a; }")
        if function_btn:
            function_btn.setStyleSheet("" if enabled else "QPushButton { background:#3b3030; color:#bdbdbd; border:1px solid #6a4a4a; }")

    def on_macro_enabled_toggled(self, row_data, checked):
        if self._handling:
            return

        seq_edit = row_data.get("seq")
        self._handling = True
        try:
            if checked:
                restore = row_data.get("backup_shortcut", "")
                if restore:
                    seq_edit.setKeySequence(key_sequence_from_text(restore))
            else:
                current = seq_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
                if current:
                    row_data["backup_shortcut"] = current
                seq_edit.clear()
                row_data["last_shortcut"] = ""
        finally:
            self._handling = False

        self.apply_macro_row_enabled_state(row_data, checked)

        if checked:
            # setKeySequence 직후 editingFinished가 한 번 더 들어올 수 있어서
            # 실제 충돌 검사는 on_macro_shortcut_edited의 last_shortcut 가드가 담당한다.
            self.on_macro_shortcut_edited(row_data)

    def eventFilter(self, obj, event):
        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_F2:
                obj.setFocus()
                obj.selectAll()
                return True
        return super().eventFilter(obj, event)

    def add_macro_row(self, macro):
        row_num = len(self.rows) + 1
        enabled = QCheckBox()
        enabled.setChecked(bool(macro.get("enabled", True)))

        name = QLineEdit(str(macro.get("name", tr_text("새 매크로", self._ui_language))))
        name.setPlaceholderText(tr_text("매크로 이름", self._ui_language))
        name.installEventFilter(self)

        actions = [k for k in list(macro.get("actions", []) or []) if tktool_phase2_macro_action_allowed(k)]
        function_btn = QPushButton(self.macro_label(actions))
        function_btn.setMinimumWidth(360)

        seq = ConfirmingKeySequenceEdit()
        seq.setKeySequence(key_sequence_from_text(str(macro.get("shortcut", ""))))

        delete_btn = QPushButton(tr_text("삭제", self._ui_language))

        initial_shortcut = key_sequence_to_portable(seq.keySequence()) if enabled.isChecked() else ""
        row_data = {
            "enabled": enabled,
            "name": name,
            "actions": actions,
            "function_btn": function_btn,
            "seq": seq,
            "delete_btn": delete_btn,
            "backup_shortcut": str(macro.get("shortcut", "") or ""),
            "last_shortcut": initial_shortcut,
            "_shortcut_checking": False,
        }
        if not enabled.isChecked():
            seq.clear()
        self.rows.append(row_data)

        function_btn.clicked.connect(lambda checked=False, r=row_data: self.add_function_to_macro(r))
        delete_btn.clicked.connect(lambda checked=False, r=row_data: self.delete_macro_row(r))
        seq.editingFinished.connect(lambda r=row_data: self.on_macro_shortcut_edited(r))
        enabled.toggled.connect(lambda checked, r=row_data: self.on_macro_enabled_toggled(r, checked))
        self.apply_macro_row_enabled_state(row_data, enabled.isChecked())

        self.grid.addWidget(enabled, row_num, 0)
        self.grid.addWidget(name, row_num, 1)
        self.grid.addWidget(function_btn, row_num, 2)
        self.grid.addWidget(seq, row_num, 3)
        self.grid.addWidget(delete_btn, row_num, 4)

    def add_function_to_macro(self, row_data):
        dlg = MacroFunctionSelectDialog(row_data.get("actions", []), self.settings, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        row_data["actions"] = dlg.get_actions()
        row_data["function_btn"].setText(self.macro_label(row_data["actions"]))

    def delete_macro_row(self, row_data):
        ans = QMessageBox.question(self, tr_text("매크로 삭제", self._ui_language), f"'{row_data['name'].text()}' {tr_text('매크로를 삭제할까요?', self._ui_language)}")
        if ans != QMessageBox.StandardButton.Yes:
            return
        if row_data in self.rows:
            self.rows.remove(row_data)
        self.settings.macros = self.normalized_macros()
        self.refill()

    def on_macro_shortcut_edited(self, row_data):
        # QKeySequenceEdit는 키 입력 완료/포커스 이동/메시지박스 표시 과정에서
        # editingFinished가 중복으로 들어올 수 있다.
        # 그래서 같은 단축키는 한 번만 검사하도록 last_shortcut으로 방어한다.
        if self._handling or row_data.get("_shortcut_checking"):
            return
        if not row_data["enabled"].isChecked():
            return

        try:
            clean_seq = sequence_without_confirm_keys(row_data["seq"].keySequence())
            clean_text = key_sequence_to_portable(clean_seq)
            current_text = key_sequence_to_portable(row_data["seq"].keySequence())
            if clean_text != current_text:
                row_data["seq"].blockSignals(True)
                try:
                    row_data["seq"].setKeySequence(clean_seq)
                finally:
                    row_data["seq"].blockSignals(False)
            seq_text = clean_text
        except Exception:
            seq_text = key_sequence_to_portable(row_data["seq"].keySequence())
        old_text = row_data.get("last_shortcut", "")

        if not seq_text:
            row_data["last_shortcut"] = ""
            return

        if seq_text == old_text:
            return

        row_data["_shortcut_checking"] = True

        def restore_previous_shortcut():
            self._handling = True
            try:
                if old_text:
                    row_data["seq"].setKeySequence(key_sequence_from_text(old_text))
                else:
                    row_data["seq"].clear()
                row_data["last_shortcut"] = old_text
            finally:
                self._handling = False

        try:
            # 다른 매크로 중복은 후입 우선으로 기존 매크로를 비활성화한다.
            for other in self.rows:
                if other is row_data:
                    continue
                if not other["enabled"].isChecked():
                    continue
                other_seq = key_sequence_to_portable(other["seq"].keySequence())
                if other_seq == seq_text:
                    ans = QMessageBox.question(
                        self,
                        "매크로 단축키 중복",
                        f"'{other['name'].text()}' 매크로가 같은 단축키를 사용 중입니다.\n"
                        f"기존 매크로를 비활성화하고 사용할까요?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if ans != QMessageBox.StandardButton.Yes:
                        restore_previous_shortcut()
                        return

                    self._handling = True
                    try:
                        other["backup_shortcut"] = other_seq
                        other["enabled"].setChecked(False)
                        other["seq"].clear()
                        other["last_shortcut"] = ""
                    finally:
                        self._handling = False
                    self.apply_macro_row_enabled_state(other, False)

            # 기존 일반 단축키와 충돌하면 일반 단축키를 토글 OFF 한다.
            for key, shortcut in list(self.settings.shortcuts.items()):
                if not self.settings.enabled.get(key, True):
                    continue
                if shortcut and key_sequence_to_portable(key_sequence_from_text(shortcut), shortcut) == seq_text:
                    label = self.label_map.get(key, key)
                    ans = QMessageBox.question(
                        self,
                        "기존 단축키 비활성화 확인",
                        f"'{label}' 기능이 같은 단축키를 사용 중입니다.\n\n"
                        f"기존 단축키를 비활성화하고 이 매크로에 지정할까요?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if ans != QMessageBox.StandardButton.Yes:
                        restore_previous_shortcut()
                        return
                    self.settings.enabled[key] = False
                    self.settings.shortcuts[key] = ""
                    break

            # 개별 글꼴 프리셋과 충돌하면 입력 시점에 확인한다.
            # 실제 비활성화는 이 창에서 OK를 눌렀을 때 메인 창이 최종 설정과 다시 대조한 뒤 적용한다.
            parent = self.parent()
            for preset_name, preset in list(getattr(parent, "item_text_presets", {}) .items() if parent is not None else []):
                if str(preset_name) in self._pending_disabled_item_presets:
                    continue
                if not preset.get("enabled", True):
                    continue
                item_seq = str(preset.get("shortcut", "") or "")
                if item_seq and key_sequence_to_portable(key_sequence_from_text(item_seq), item_seq) == seq_text:
                    ans = QMessageBox.question(
                        self,
                        tr_text("개별 프리셋 단축키 비활성화 확인", self._ui_language),
                        (
                            f"'{preset_name}' individual font preset is using the same shortcut.\n\n"
                            f"Disable the individual font preset shortcut and assign it to this macro?"
                            if self._ui_language == LANG_EN else
                            f"'{preset_name}' 개별 글꼴 프리셋이 같은 단축키를 사용 중입니다.\n\n"
                            f"개별 글꼴 프리셋 단축키를 비활성화하고 이 매크로에 지정할까요?"
                        ),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if ans != QMessageBox.StandardButton.Yes:
                        restore_previous_shortcut()
                        return
                    self._pending_disabled_item_presets.add(str(preset_name))
                    break

            row_data["last_shortcut"] = seq_text
            row_data["backup_shortcut"] = seq_text

        finally:
            row_data["_shortcut_checking"] = False

    def accept(self):
        self.settings.macros = self.normalized_macros()
        super().accept()

    def get_settings(self) -> ShortcutSettings:
        return self.settings




def shortcut_item_description(key: str, label: str, group_title: str, lang=LANG_KO) -> str:
    explicit = {
        "paint_move": "캔버스 이동 모드로 전환합니다.",
        "paint_brush": "브러시 도구로 직접 칠합니다.",
        "paint_erase": "브러시로 칠한 내용을 지웁니다.",
        "paint_zoom_in": "브러시 크기를 키웁니다.",
        "paint_zoom_out": "브러시 크기를 줄입니다.",
        "paint_reanalyze": "현재 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만들고, 기존 마스크는 재사용합니다.",
        "edit_undo": "현재 포커스된 텍스트 입력칸의 글자 수정만 되돌립니다. 프로젝트/AI 번역/설정 변경은 되돌리지 않습니다.",
        "edit_redo": "현재 포커스된 텍스트 입력칸의 글자 수정만 다시 실행합니다. 프로젝트/AI 번역/설정 변경은 다시 실행하지 않습니다.",
        "paint_undo": "현재 포커스된 텍스트 입력칸의 글자 수정만 되돌립니다. (호환 키)",
        "paint_redo": "현재 포커스된 텍스트 입력칸의 글자 수정만 다시 실행합니다. (호환 키)",
        "paint_magic_select": "요술봉 선택 모드를 켭니다.",
        "paint_magic_expand": "요술봉으로 선택한 영역을 확장합니다.",
        "paint_magic_tolerance_inc": "요술봉 색상 허용범위를 올립니다.",
        "paint_magic_tolerance_dec": "요술봉 색상 허용범위를 낮춥니다.",
        "paint_magic_expand_inc": "요술봉 선택 영역의 확장값을 올립니다.",
        "paint_magic_expand_dec": "요술봉 선택 영역의 확장값을 낮춥니다.",
        "paint_magic_fill": "선택한 영역을 현재 색상으로 채웁니다.",
        "paint_area_fill": "마스크 탭에서는 영역 마스킹, 최종결과 탭에서는 현재 페인팅 색상으로 영역 칠하기를 수행합니다.",
        "paint_mask_wrap": "마스크 랩핑은 지정한 영역의 마스크를 하나로 합치는 도구입니다.",
        "paint_mask_cut": "마스크 커팅은 지정한 영역과 겹치는 마스크를 잘라내는 도구입니다.",
        "paint_mask_wrap_rect": "마스크 선택 모양을 사각형으로 바꿉니다.",
        "paint_mask_wrap_free": "마스크 선택 모양을 자유형으로 바꿉니다.",
        "paint_mask_toggle": "분석 생성 마스크를 숨기고 사용자가 직접 마스크를 그릴 수 있는 기능입니다.",
        "final_paint_color": "최종 페인팅 색상을 선택합니다.",
        "final_paint_to_background": "최종결과 배경을 이후 분석/인페인팅 기준이 되는 작업용 원본으로 반영합니다.",
        "final_text_tool": "최종결과 탭의 텍스트 도구로 전환합니다.",
        "final_paint_above_toggle": "텍스트 위로 페인팅을 할지 텍스트 아래로 페인팅을 할지 선택합니다.",
        "final_paint_opacity_inc": "브러시 불투명도를 올립니다.",
        "final_paint_opacity_dec": "브러시 불투명도를 낮춥니다.",

        "text_linebreak": "선택한 텍스트에 줄내림을 넣습니다.",
        "text_ellipsis": "말줄임표 특수문자를 입력합니다.",
        "text_horizontal_dash": "가로장음 특수문자를 입력합니다.",
        "text_vertical_dash": "세로장음 특수문자를 입력합니다.",
        "text_single_corner": "홑낫표 특수문자를 입력합니다.",
        "text_double_corner": "겹낫표 특수문자를 입력합니다.",
        "text_white_heart": "하얀 하트 특수문자를 입력합니다.",
        "text_black_heart": "검은 하트 특수문자를 입력합니다.",
        "text_music_note": "음표 특수문자를 입력합니다.",
        "text_black_circle": "검은 동그라미 특수문자를 입력합니다.",
        "text_middle_dot": "가운뎃점 특수문자를 입력합니다.",

        "item_font_select": "폰트 설정창을 엽니다.",
        "text_font_size": "문자 크기 입력칸에 포커싱을 줍니다.",
        "item_font_inc": "선택한 텍스트의 문자 크기를 키웁니다.",
        "item_font_dec": "선택한 텍스트의 문자 크기를 줄입니다.",
        "text_stroke_size": "획 크기 입력칸에 포커싱을 줍니다.",
        "item_stroke_inc": "선택한 텍스트의 획을 굵게 합니다.",
        "item_stroke_dec": "선택한 텍스트의 획을 얇게 합니다.",
        "text_line_spacing": "행간 입력칸에 포커싱을 줍니다.",
        "text_letter_spacing": "자간 입력칸에 포커싱을 줍니다.",
        "text_char_width": "문자 너비 입력칸에 포커싱을 줍니다.",
        "text_char_height": "문자 높이 입력칸에 포커싱을 줍니다.",
        "text_bold_toggle": "문자를 굵게 합니다.",
        "text_italic_toggle": "문자를 기울입니다.",
        "text_strike_toggle": "문자에 취소선을 그립니다.",
        "text_transform_toggle": "선택한 텍스트의 변형 모드를 켜거나 끕니다.",
        "item_align_left": "텍스트를 왼쪽 정렬합니다.",
        "item_align_center": "텍스트를 가운데 정렬합니다.",
        "item_align_right": "텍스트를 오른쪽 정렬합니다.",
        "item_text_color": "문자 색상 팔레트를 엽니다.",
        "item_stroke_color": "획 색상 팔레트를 엽니다.",

        "project_new": "새 프로젝트 작업 폴더를 만듭니다.",
        "project_import_maker_game": "RPG Maker MV/MZ 게임 폴더를 불러와 쯔꾸르 번역 프로젝트를 시작합니다.",
        "project_import_images": "RPG Maker MV/MZ 게임 폴더를 불러옵니다. (호환 키)",
        "project_open": "YSBG 패키지를 엽니다.",
        "project_open_json": "작업 폴더의 project.json을 엽니다.",
        "project_save": "현재 프로젝트를 저장합니다.",
        "project_save_as": "현재 프로젝트를 다른 이름으로 저장합니다.",
        "project_recover_last_work": "이전 작업 상태를 복구합니다.",
        "project_show_launcher": "홈 화면으로 이동합니다.",
        "project_exit": "현재 프로젝트를 닫습니다.",

        "work_source_compare": "왼쪽에 원본 탭 복사 화면을 열어 현재 작업 화면과 비교합니다.",
        "work_page_prev": "이전 맵로 이동합니다.",
        "work_page_next": "다음 맵로 이동합니다.",
        "work_page_list": "맵 목록 창을 엽니다.",
        "work_page_full_name": "현재 맵의 전체 이름을 확인합니다.",
        "work_page_rename_source": "현재 맵 탭의 파일명을 바꿉니다.",
        "work_page_delete_current": "현재 맵 탭을 삭제합니다.",
        "work_page_delete_all": "선택한 맵 탭 또는 지정한 범위의 맵 탭을 일괄 삭제합니다.",
        "work_open_current_project_folder": "현재 프로젝트 작업 폴더를 엽니다.",
        "work_scan_maker_game": "쯔꾸르 게임/맵 데이터를 다시 분석합니다.",
        "work_analyze": "쯔꾸르 게임/맵 데이터를 다시 분석합니다. (호환 키)",
        "paint_reanalyze": "현재 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만들고, 기존 마스크는 재사용합니다.",
        "work_quick_ocr": "빠른 OCR 설정창을 엽니다.",
        "work_text_number_width": "텍스트 넘버 크기 설정을 엽니다.",
        "work_translate": "현재 페이지를 번역합니다.",
        "work_refresh_maker_preview": "현재 맵의 프리뷰 이미지를 상태/캐시와 무관하게 다시 만듭니다.",
        "work_inpaint": "현재 페이지를 인페인팅합니다.",
        "work_import_clean_background": "클린본 이미지를 최종결과 배경으로 불러옵니다. 1개를 선택하면 현재 페이지, 여러 개를 선택하면 파일명과 페이지명을 매칭합니다.",
        "work_inpaint_source": "구버전 호환용 동작입니다. 현재는 배경을 원본으로 쓰기와 같은 동작을 실행합니다.",
        "work_restore_original_source": "원본 이미지 상태로 되돌립니다.",
        "work_extract_text": "현재 페이지의 원문/번역문 TXT를 내보냅니다.",
        "work_import_translation": "현재 페이지의 번역문을 불러옵니다.",
        "work_clear_translation": "현재 페이지 번역문 내용을 비웁니다.",
        "work_clean_text": "현재 페이지에서 체크 해제된 텍스트 라인을 정리합니다.",
        "work_text_find": "텍스트 표에서 원문/번역문/메모를 검색합니다.",
        "work_text_replace": "텍스트 표에서 원문/번역문/메모를 찾고 교체합니다.",
        "work_unify_translations": "100% 동일한 원문은 가장 먼저 확보된 번역문으로 통일합니다.",
        "work_reset_text_rects": "현재 텍스트의 크기를 기준으로 텍스트 영역을 재설정합니다.",
        "work_export": "현재 페이지를 출력합니다.",
        "work_output_preview": "현재 페이지가 실제 출력에서 어떻게 보일지 미리보기로 확인합니다.",
        "view_text_toggle": "최종결과 탭에서 번역문의 텍스트가 보이지 않게 숨깁니다.",

        "batch_analyze": "여러 페이지를 한 번에 분석합니다.",
        "batch_reanalyze": "선택한 맵마다 현재 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만들고, 기존 마스크는 재사용합니다.",
        "batch_translate": "여러 페이지를 한 번에 번역합니다.",
        "batch_inpaint": "여러 페이지를 한 번에 인페인팅합니다.",
        "batch_extract_text": "선택한 맵들의 원문/번역문 TXT를 한 번에 내보냅니다.",
        "batch_clear_translation": "전체 맵 번역문 내용을 지웁니다.",
        "batch_clean_text": "전체 맵에서 체크 해제된 텍스트 라인을 정리합니다.",
        "batch_reset_text_rects": "현재 텍스트의 크기를 기준으로 전체 맵의 텍스트 영역을 재설정합니다.",
        "batch_export": "전체 맵를 한 번에 출력합니다.",

        "auto_text_size_current": "현재 페이지 텍스트 크기를 자동 조정합니다.",
        "auto_text_size_batch": "전체 맵 텍스트 크기를 자동 조정합니다.",
        "auto_linebreak_current": "현재 페이지 텍스트 줄내림을 자동 정리합니다.",
        "auto_linebreak_batch": "전체 맵 텍스트 줄내림을 자동 정리합니다.",

        
        "option_api_settings": "API 설정 관리창을 엽니다.",
        "option_translation_prompt": "번역 프롬프트 설정창을 엽니다.",
        "option_maker_character_prompts": "쯔꾸르 캐릭터별 번역 프롬프트 관리창을 엽니다.",
        "option_maker_translation_settings": "쯔꾸르 AI 번역용 원문 정규화 설정창을 엽니다.",
        "option_maker_refresh_runtime_profile": "현재 작업 폴더의 maker_game에서 표시 환경을 다시 읽고 프리뷰 캐시를 갱신합니다.",
        "option_maker_preview_display_settings": "게임 프리뷰 옵션창을 엽니다.",
        "option_maker_game_settings": "게임 기본 정보와 표시 환경 설정창을 엽니다.",
        "option_maker_game_refresh": "현재 게임 JSON에서 대사를 다시 읽어 프로젝트와 맞춥니다.",
        "project_maker_character_profiles": "쯔꾸르 캐릭터 프로필 창을 엽니다.",
        "option_glossary": "단어장 관리창을 엽니다.",
        "option_analysis_mask_settings": "분석/페인트 마스크 확장 비율을 설정합니다.",
        "option_ocr_analysis_regions": "OCR 분석 범위 지정 기능을 엽니다.",
        "option_cleanup_outputs": "출력물 정리 창을 엽니다.",
        "option_workspace_location": "작업 폴더 위치를 바꿉니다.",
        "option_cleanup_temp_files": "사용자 데이터 및 임시파일 정리 창을 엽니다.",
        "option_workspace_size_manager": "작업 폴더별 용량을 확인하고 직접 삭제하는 관리창을 엽니다.",
        "option_register_ysb": ".ysbg 확장자 연결을 등록합니다.",
        "option_unregister_ysbt": ".ysbg 확장자 연결을 해제합니다.",

        "option_settings_overview": "설정 / 옵션 통합창을 엽니다.",
        "option_theme_settings": "테마 설정창을 엽니다.",
        "option_language_settings": "언어 설정창을 엽니다.",
        "setting_page_tab_display_name": "맵 탭 표시명을 설정합니다.",
        "setting_output_display_name": "출력 파일 표시명을 설정합니다.",
        "setting_output_options": "최종 출력 이미지와 클린본의 저장 형식을 설정합니다.",
        "setting_interface_tooltips": "버튼과 메뉴의 설명용 인터페이스 툴팁 표시를 켜거나 끕니다.",
        "setting_file_path_visibility": "로그창 경로 표시를 켜거나 끕니다.",
        "option_shortcut_settings": "단축키 통합 관리창을 엽니다.",
        "option_macro_settings": "매크로 관리창을 엽니다.",
        "option_text_preset_settings": "페이지 글꼴 프리셋 관리창을 엽니다.",
        "option_item_text_preset_settings": "개별 글꼴 프리셋 관리창을 엽니다.",

        "help_program_manual": "프로그램 메뉴얼을 엽니다.",
        "help_open_website": "YSB Tool 사이트로 이동합니다.",
        "help_report_bug": "버그 제보 / 문의 페이지를 엽니다.",
        "help_about": "프로그램 정보를 엽니다.",

        "quick_ocr_execute": "지정한 단축키로 바로 빠른 OCR 드래그 모드를 시작합니다.",
    }
    text = explicit.get(key)
    if not text:
        text = f"{label} 기능을 실행합니다."
    if str(lang).lower().startswith("en"):
        # Keep English simple if a translation is missing.
        text = {
            "캔버스 이동 모드로 전환합니다.": "Switches to canvas move mode.",
        }.get(text, text)
    return tr_text(text, lang)


class ShortcutSettingsDialog(QDialog):
    def __init__(self, settings: ShortcutSettings, parent=None, show_cache_path=False):
        super().__init__(parent)
        self._show_cache_path = bool(show_cache_path)
        self._ui_language = resolve_ui_language(parent)
        self.setWindowTitle(tr_text("단축키 통합 관리", self._ui_language))
        self.resize(760, 760)
        self._ui_theme = resolve_ui_theme(parent)
        self.setStyleSheet(shortcut_dialog_qss(self._ui_theme))

        self.settings = enforce_fixed_shortcuts(ShortcutSettings(
            dict(settings.shortcuts),
            {k: bool(settings.enabled.get(k, True)) for k in DEFAULT_SHORTCUTS},
            [dict(m) for m in getattr(settings, "macros", [])],
            dict(getattr(settings, "migration_state", {}) or {}),
        ))
        self.edits = {}
        self.fixed_labels = {}
        self.checks = {}
        self.labels = {}
        self.desc_labels = {}
        self.item_frames = {}
        self.last_sequences = {}
        self.disabled_backup = {}
        self._handling_change = False
        self._shortcut_conflict_prompt_active = False
        # 기본 단축키 입력 중 개별 글꼴 프리셋과 충돌을 허용한 경우,
        # 실제 비활성화는 OK로 저장할 때 메인 창에서 최종 충돌 여부를 재확인한 뒤 적용한다.
        self._pending_disabled_item_presets = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel(tr_text("단축키 통합 관리", self._ui_language))
        title.setObjectName("SettingsDialogTitle")
        layout.addWidget(title)

        intro_lines = [
            tr_text("프로그램 전체 단축키를 한곳에서 관리합니다. 각 항목 설명을 보고 어떤 기능의 단축키를 바꾸는지 바로 확인할 수 있습니다.", self._ui_language),
            tr_text("체크를 끄면 해당 단축키는 사용하지 않으며 입력칸이 비워집니다. 같은 단축키를 지정하면 기존 항목과 서로 교체됩니다.", self._ui_language),
            tr_text("줄내림, 뒤로가기, 앞으로 가기는 작업 안정성을 위해 고정 단축키로 표시만 됩니다.", self._ui_language),
        ]
        if self._show_cache_path:
            intro_lines.append(tr_text("캐시 위치: ", self._ui_language) + ShortcutSettingsStore.cache_path())
        intro = QLabel("\n".join(intro_lines))
        intro.setObjectName("SettingsDescription")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr_text("기능 이름을 입력하고 Enter, 또는 이 칸에 포커스를 둔 상태에서 단축키를 눌러 검색", self._ui_language))
        self.search_edit.returnPressed.connect(self.apply_text_search)
        self.search_edit.installEventFilter(self)
        layout.addWidget(self.search_edit)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.tabs.setUsesScrollButtons(True)
        tab_bar = self.tabs.tabBar()
        tab_bar.setExpanding(False)
        tab_bar.setUsesScrollButtons(True)
        layout.addWidget(self.tabs, 1)

        self.tab_records = []
        self.section_records = []
        self.card_records = []
        self.extra_shortcut_text_by_key = {}

        for title_text, rows in tktool_phase2_visible_groups():
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(0)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setAlignment(Qt.AlignmentFlag.AlignTop)

            outer = QWidget()
            outer_layout = QVBoxLayout(outer)
            outer_layout.setContentsMargins(10, 10, 10, 10)
            outer_layout.setSpacing(10)
            outer_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            tab_record = {"title": title_text, "page": page, "sections": []}

            for section_name, section_rows in shortcut_section_rows(title_text, rows):
                block = QFrame()
                block.setObjectName("SettingsBlock")
                block_layout = QVBoxLayout(block)
                block_layout.setContentsMargins(12, 12, 12, 12)
                block_layout.setSpacing(10)

                section_title = QLabel(tr_text(section_name, self._ui_language))
                section_title.setObjectName("SettingsSectionTitle")
                block_layout.addWidget(section_title)

                section_desc = QLabel(tr_text(f"{section_name} 관련 단축키를 관리합니다.", self._ui_language))
                section_desc.setObjectName("SettingsDescription")
                section_desc.setWordWrap(True)
                block_layout.addWidget(section_desc)

                section_record = {"title": section_name, "block": block, "cards": [], "tab": tab_record}

                for key, label in section_rows:
                    item = QFrame()
                    item.setObjectName("SettingsItem")
                    item_layout = QHBoxLayout(item)
                    item_layout.setContentsMargins(12, 10, 12, 10)
                    item_layout.setSpacing(14)

                    toggle_wrap = QWidget()
                    toggle_wrap.setFixedWidth(32)
                    toggle_layout = QVBoxLayout(toggle_wrap)
                    toggle_layout.setContentsMargins(0, 0, 0, 0)
                    toggle_layout.setSpacing(0)
                    chk = QCheckBox()
                    chk.setChecked(True if key in FIXED_SHORTCUT_KEYS else self.settings.is_enabled(key))
                    if key in FIXED_SHORTCUT_KEYS:
                        chk.setEnabled(False)
                        chk.setToolTip(tr_text("고정 단축키라서 끌 수 없습니다.", self._ui_language))
                    toggle_layout.addStretch(1)
                    toggle_layout.addWidget(chk, 0, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
                    toggle_layout.addStretch(1)
                    item_layout.addWidget(toggle_wrap, 0, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

                    left_wrap = QWidget()
                    left_layout = QVBoxLayout(left_wrap)
                    left_layout.setContentsMargins(0, 0, 0, 0)
                    left_layout.setSpacing(4)

                    label_w = QLabel(tr_text(label, self._ui_language))
                    label_w.setObjectName("SettingsItemTitle")
                    left_layout.addWidget(label_w)

                    desc_w = QLabel(shortcut_item_description(key, label, title_text, self._ui_language))
                    desc_w.setObjectName("SettingsDescription")
                    desc_w.setWordWrap(True)
                    left_layout.addWidget(desc_w)

                    item_layout.addWidget(left_wrap, 1)

                    self.checks[key] = chk
                    self.labels[key] = label_w
                    self.desc_labels[key] = desc_w
                    self.item_frames[key] = item

                    if key in FIXED_SHORTCUT_KEYS:
                        fixed_text = fixed_shortcut_text(key, portable=False)
                        fixed_label = QLabel(f"{fixed_text}  ·  {tr_text('고정', self._ui_language)}")
                        fixed_label.setObjectName("SettingsItemTitle")
                        fixed_label.setMinimumWidth(220)
                        fixed_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        fixed_label.setToolTip(tr_text("고정 단축키라서 변경할 수 없습니다.", self._ui_language))
                        item_layout.addWidget(fixed_label, 0, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        self.fixed_labels[key] = fixed_label
                        self.last_sequences[key] = fixed_shortcut_text(key, portable=True)
                        item.setProperty("shortcutEnabled", True)
                    else:
                        edit = ConfirmingKeySequenceEdit()
                        edit.setKeySequence(self.settings.seq(key))
                        edit.setMinimumWidth(220)
                        item_layout.addWidget(edit, 0, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        self.edits[key] = edit
                        self.last_sequences[key] = key_sequence_to_portable(edit.keySequence())
                        chk.toggled.connect(lambda checked, k=key: self.on_enabled_toggled(k, checked))
                        edit.editingFinished.connect(lambda k=key: self.on_editing_finished(k))
                        self.apply_enabled_state(key, chk.isChecked())

                    block_layout.addWidget(item)

                    card_record = {
                        "key": key,
                        "label": label,
                        "group": title_text,
                        "section": section_name,
                        "item": item,
                        "section_record": section_record,
                        "tab_record": tab_record,
                        "readonly": key in FIXED_SHORTCUT_KEYS,
                    }
                    section_record["cards"].append(card_record)
                    self.card_records.append(card_record)

                outer_layout.addWidget(block)
                tab_record["sections"].append(section_record)
                self.section_records.append(section_record)

            if title_text == "기타":
                extra_refs = self.collect_extra_shortcut_references()
                if extra_refs:
                    block = QFrame()
                    block.setObjectName("SettingsBlock")
                    block_layout = QVBoxLayout(block)
                    block_layout.setContentsMargins(12, 12, 12, 12)
                    block_layout.setSpacing(10)

                    section_title = QLabel(tr_text("등록된 사용자 단축키", self._ui_language))
                    section_title.setObjectName("SettingsSectionTitle")
                    block_layout.addWidget(section_title)

                    section_desc = QLabel(tr_text("매크로와 개별 글꼴 프리셋에 등록된 단축키를 함께 확인합니다.", self._ui_language))
                    section_desc.setObjectName("SettingsDescription")
                    section_desc.setWordWrap(True)
                    block_layout.addWidget(section_desc)

                    section_record = {"title": "등록된 사용자 단축키", "block": block, "cards": [], "tab": tab_record}
                    for extra in extra_refs:
                        key = extra["key"]
                        label = extra["label"]
                        shortcut = extra["shortcut"]
                        desc = extra.get("description", "")

                        item = QFrame()
                        item.setObjectName("SettingsItem")
                        item_layout = QHBoxLayout(item)
                        item_layout.setContentsMargins(12, 10, 12, 10)
                        item_layout.setSpacing(14)

                        left_wrap = QWidget()
                        left_layout = QVBoxLayout(left_wrap)
                        left_layout.setContentsMargins(0, 0, 0, 0)
                        left_layout.setSpacing(4)

                        label_w = QLabel(tr_text(label, self._ui_language))
                        label_w.setObjectName("SettingsItemTitle")
                        left_layout.addWidget(label_w)

                        desc_w = QLabel(tr_text(desc, self._ui_language))
                        desc_w.setObjectName("SettingsDescription")
                        desc_w.setWordWrap(True)
                        left_layout.addWidget(desc_w)

                        item_layout.addWidget(left_wrap, 1)

                        shortcut_label = QLabel(shortcut)
                        shortcut_label.setObjectName("SettingsItemTitle")
                        shortcut_label.setMinimumWidth(180)
                        shortcut_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        item_layout.addWidget(shortcut_label, 0, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                        block_layout.addWidget(item)
                        self.extra_shortcut_text_by_key[key] = shortcut

                        card_record = {
                            "key": key,
                            "label": label,
                            "group": title_text,
                            "section": "등록된 사용자 단축키",
                            "item": item,
                            "section_record": section_record,
                            "tab_record": tab_record,
                            "readonly": True,
                            "shortcut": shortcut,
                            "description": desc,
                            "filter_visible": True,
                        }
                        section_record["cards"].append(card_record)
                        self.card_records.append(card_record)

                    outer_layout.addWidget(block)
                    tab_record["sections"].append(section_record)
                    self.section_records.append(section_record)

            outer_layout.addStretch(1)
            scroll.setWidget(outer)
            page_layout.addWidget(scroll)
            self.tabs.addTab(page, tr_text(title_text, self._ui_language))
            tab_record["index"] = self.tabs.indexOf(page)
            self.tab_records.append(tab_record)

        btn_line = QHBoxLayout()
        reset_btn = QPushButton(tr_text("기본값 복구", self._ui_language))
        reset_btn.clicked.connect(self.reset_defaults)
        btn_line.addWidget(reset_btn)
        btn_line.addStretch()
        layout.addLayout(btn_line)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr_text("닫기", self._ui_language))
        # 검색창에 포커스가 있을 때 Enter가 QDialog의 기본 OK 버튼으로 전달되어
        # 창이 바로 닫히는 것을 막는다. 검색은 eventFilter/keyPressEvent에서만 처리한다.
        for _btn in (buttons.button(QDialogButtonBox.StandardButton.Ok), buttons.button(QDialogButtonBox.StandardButton.Cancel)):
            if _btn is not None:
                _btn.setAutoDefault(False)
                _btn.setDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


    def collect_extra_shortcut_references(self):
        records = []
        seen = set()

        for idx, macro in enumerate(getattr(self.settings, "macros", []) or []):
            if not macro.get("enabled", True):
                continue
            shortcut = str(macro.get("shortcut", "") or "").strip()
            if not shortcut:
                continue
            try:
                seq = key_sequence_from_text(shortcut)
                display_shortcut = seq.toString(QKeySequence.SequenceFormat.NativeText) or shortcut
            except Exception:
                display_shortcut = shortcut
            name = str(macro.get("name") or "매크로").strip() or "매크로"
            key = f"__macro__:{idx}:{name}"
            records.append({
                "key": key,
                "label": f"매크로: {name}",
                "shortcut": display_shortcut,
                "description": "매크로 관리에서 등록한 사용자 매크로 단축키입니다.",
            })
            seen.add(key)

        parent = self.parent()
        item_presets = getattr(parent, "item_text_presets", {}) if parent is not None else {}
        if isinstance(item_presets, dict):
            for name, preset in sorted(item_presets.items(), key=lambda x: str(x[0])):
                if not isinstance(preset, dict):
                    continue
                if not preset.get("enabled", True):
                    continue
                shortcut = str(preset.get("shortcut", "") or "").strip()
                if not shortcut:
                    continue
                try:
                    seq = key_sequence_from_text(shortcut)
                    display_shortcut = seq.toString(QKeySequence.SequenceFormat.NativeText) or shortcut
                except Exception:
                    display_shortcut = shortcut
                label_name = str(name)
                key = f"__item_preset__:{label_name}"
                records.append({
                    "key": key,
                    "label": f"개별 글꼴 프리셋: {label_name}",
                    "shortcut": display_shortcut,
                    "description": "개별 글꼴 프리셋 관리에서 등록한 사용자 단축키입니다.",
                })
                seen.add(key)

        return records



    def normalize_shortcut_text(self, value):
        value = str(value or "").strip()
        if not value:
            return ""
        compact = (
            value.replace(" ", "")
            .replace("Control+", "Ctrl+")
            .replace("control+", "ctrl+")
            .replace("CTRL+", "Ctrl+")
        )
        try:
            converted = QKeySequence(compact).toString(QKeySequence.SequenceFormat.PortableText)
            if converted:
                compact = converted.replace(" ", "")
        except Exception:
            pass
        return compact.lower()

    def key_token_from_event(self, event):
        key_code = event.key()
        punct = {
            Qt.Key.Key_Comma: ",",
            Qt.Key.Key_Period: ".",
            Qt.Key.Key_Semicolon: ";",
            Qt.Key.Key_Apostrophe: "'",
            Qt.Key.Key_Slash: "/",
            Qt.Key.Key_Backslash: "\\",
            Qt.Key.Key_BracketLeft: "[",
            Qt.Key.Key_BracketRight: "]",
            Qt.Key.Key_Minus: "-",
            Qt.Key.Key_Equal: "=",
            Qt.Key.Key_Plus: "+",
            Qt.Key.Key_QuoteDbl: '"',
            Qt.Key.Key_Colon: ":",
        }
        if key_code in punct:
            return punct[key_code]
        for n in range(1, 36):
            if key_code == getattr(Qt.Key, f"Key_F{n}", None):
                return f"F{n}"
        txt = event.text()
        if txt and len(txt) == 1 and txt.isprintable():
            return txt.upper()
        return QKeySequence(key_code).toString(QKeySequence.SequenceFormat.PortableText)

    def shortcut_text_from_event(self, event):
        key_code = event.key()
        if key_code in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_unknown,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Escape,
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
        ):
            return ""
        mods = event.modifiers()
        # 검색어 입력 중 일반 문자 입력은 그대로 통과시킨다. 단축키 검색은 조합키 입력일 때만 실행한다.
        if not (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.MetaModifier)):
            return ""
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("Meta")
        token = self.key_token_from_event(event)
        if not token:
            return ""
        seq_text = "+".join(parts + [token]) if parts else token
        try:
            portable = key_sequence_to_portable(key_sequence_from_text(seq_text), seq_text)
            if portable:
                return portable
        except Exception:
            pass
        return seq_text

    def eventFilter(self, obj, event):
        if obj is getattr(self, "search_edit", None):
            if event.type() == QEvent.Type.ShortcutOverride:
                seq_text = self.shortcut_text_from_event(event)
                if seq_text:
                    event.accept()
                    return True
            if event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self.apply_text_search()
                    event.accept()
                    return True
                if event.key() == Qt.Key.Key_Escape:
                    self.clear_shortcut_search()
                    event.accept()
                    return True
                seq_text = self.shortcut_text_from_event(event)
                if seq_text:
                    self.apply_shortcut_search(seq_text)
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        # QDialog는 기본 버튼이 있으면 Enter를 accept로 처리할 수 있다.
        # 검색창에서는 Enter를 무조건 검색 확정으로만 사용하고, 창 닫기는 OK 버튼/Alt 계열 버튼으로만 한다.
        if getattr(self, "search_edit", None) is not None and self.focusWidget() is self.search_edit:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.apply_text_search()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Escape:
                self.clear_shortcut_search()
                event.accept()
                return
        super().keyPressEvent(event)

    def current_shortcut_text_for_key(self, key, portable=True):
        if hasattr(self, "extra_shortcut_text_by_key") and key in self.extra_shortcut_text_by_key:
            value = str(self.extra_shortcut_text_by_key.get(key) or "")
            try:
                seq = key_sequence_from_text(value)
                if seq and not seq.isEmpty():
                    fmt = QKeySequence.SequenceFormat.PortableText if portable else QKeySequence.SequenceFormat.NativeText
                    shown = seq.toString(fmt)
                    return shown or value
            except Exception:
                pass
            return value

        if key in FIXED_SHORTCUT_KEYS:
            return fixed_shortcut_text(key, portable=portable)

        edit = self.edits.get(key)
        if edit is not None:
            seq = edit.keySequence()
            if not seq or seq.isEmpty():
                return ""
            fmt = QKeySequence.SequenceFormat.PortableText if portable else QKeySequence.SequenceFormat.NativeText
            return seq.toString(fmt) or key_sequence_to_portable(seq)
        value = self.settings.shortcuts.get(key, DEFAULT_SHORTCUTS.get(key, ""))
        seq = key_sequence_from_text(value)
        fmt = QKeySequence.SequenceFormat.PortableText if portable else QKeySequence.SequenceFormat.NativeText
        return (seq.toString(fmt) or str(value or "")) if seq and not seq.isEmpty() else ""

    def clear_shortcut_search(self):
        if hasattr(self, "search_edit"):
            self.search_edit.clear()
        self.apply_filter(None)

    def apply_text_search(self):
        query = self.search_edit.text().strip().lower() if hasattr(self, "search_edit") else ""
        if not query:
            self.apply_filter(None)
            return
        matched = []
        for card in self.card_records:
            key = card["key"]
            label = str(card.get("label", ""))
            d_label = tr_text(label, self._ui_language)
            group = str(card.get("group", ""))
            section = str(card.get("section", ""))
            desc = str(card.get("description", ""))
            portable = self.current_shortcut_text_for_key(key, portable=True)
            native = self.current_shortcut_text_for_key(key, portable=False)
            hay = f"{label} {d_label} {group} {section} {desc} {portable} {native}".lower()
            if query in hay:
                matched.append(key)
        if not matched:
            QMessageBox.information(self, tr_text("검색 결과 없음", self._ui_language), tr_text("검색 결과가 없습니다.", self._ui_language))
            return
        self.apply_filter(set(matched))

    def apply_shortcut_search(self, seq_text):
        normalized = self.normalize_shortcut_text(seq_text)
        if not normalized:
            return
        matched = []
        for card in self.card_records:
            key = card["key"]
            chk = self.checks.get(key)
            if chk is not None and not chk.isChecked():
                continue
            candidates = {
                self.normalize_shortcut_text(self.current_shortcut_text_for_key(key, portable=True)),
                self.normalize_shortcut_text(self.current_shortcut_text_for_key(key, portable=False)),
            }
            if normalized in candidates:
                matched.append(key)
        if not matched:
            QMessageBox.information(self, tr_text("단축키 검색", self._ui_language), tr_text("해당 단축키는 없습니다.", self._ui_language))
            return
        # 검색창에는 사용자가 방금 누른 단축키를 표시해 현재 필터 상태를 알 수 있게 한다.
        self.search_edit.setText(key_sequence_from_text(seq_text).toString(QKeySequence.SequenceFormat.NativeText) or seq_text)
        self.apply_filter(set(matched))

    def apply_filter(self, matched_keys):
        # 검색 기준은 항상 전체 원본 카드 목록이다.
        # QWidget.isVisible()은 부모 탭이 숨겨지면 False가 되므로,
        # 재검색/검색해제 때 숨겨진 탭이 영원히 제외되지 않도록 논리 상태를 따로 쓴다.
        matched_keys = None if matched_keys is None else set(matched_keys)

        for card in self.card_records:
            visible = matched_keys is None or card["key"] in matched_keys
            card["filter_visible"] = visible
            card["item"].setVisible(visible)

        for section in self.section_records:
            visible = any(bool(card.get("filter_visible", True)) for card in section["cards"])
            section["block"].setVisible(visible)
            section["filter_visible"] = visible

        first_visible_index = None
        for tab in self.tab_records:
            tab_visible = any(bool(section.get("filter_visible", True)) for section in tab["sections"])
            idx = tab.get("index", -1)
            tab["filter_visible"] = tab_visible
            if idx >= 0:
                try:
                    self.tabs.setTabVisible(idx, tab_visible)
                except Exception:
                    self.tabs.setTabEnabled(idx, tab_visible)
            if tab_visible and first_visible_index is None:
                first_visible_index = idx

        if first_visible_index is not None and first_visible_index >= 0:
            current_idx = self.tabs.currentIndex()
            current_visible = True
            try:
                current_visible = self.tabs.isTabVisible(current_idx)
            except Exception:
                current_visible = self.tabs.isTabEnabled(current_idx)
            if not current_visible:
                self.tabs.setCurrentIndex(first_visible_index)



    def ask_shortcut_conflict_question(self, *args, **kwargs):
        # QKeySequenceEdit는 포커스 이동/메시지박스 표시 과정에서 editingFinished가
        # 중복으로 들어올 수 있다. 확인창이 떠 있는 동안 재진입을 차단해
        # 같은 충돌 알림이 2번 표시되는 것을 막는다.
        if getattr(self, "_shortcut_conflict_prompt_active", False):
            return QMessageBox.StandardButton.No
        self._shortcut_conflict_prompt_active = True
        try:
            return QMessageBox.question(*args, **kwargs)
        finally:
            self._shortcut_conflict_prompt_active = False

    def sequence_text(self, edit: QKeySequenceEdit) -> str:
        try:
            clean = sequence_without_confirm_keys(edit.keySequence())
            clean_text = key_sequence_to_portable(clean)
            current_text = key_sequence_to_portable(edit.keySequence())
            if clean_text != current_text:
                edit.blockSignals(True)
                try:
                    edit.setKeySequence(clean)
                finally:
                    edit.blockSignals(False)
            return clean_text
        except Exception:
            return edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)

    def apply_enabled_state(self, key: str, enabled: bool):
        if key in FIXED_SHORTCUT_KEYS:
            return
        edit = self.edits[key]
        label = self.labels.get(key)
        desc = self.desc_labels.get(key)
        item = self.item_frames.get(key)

        edit.setEnabled(enabled)

        if item is not None:
            item.setProperty("shortcutEnabled", enabled)
            style = item.style()
            style.unpolish(item)
            style.polish(item)
            item.update()

        if enabled:
            edit.setStyleSheet("")
            if label:
                label.setStyleSheet("")
            if desc:
                desc.setStyleSheet("")
        else:
            edit.setStyleSheet(disabled_key_edit_qss(self._ui_theme))
            if self._ui_theme == THEME_LIGHT:
                muted_title = "color:#8b95a7;"
                muted_desc = "color:#9aa3b2;"
            else:
                muted_title = "color:#8d97a6;"
                muted_desc = "color:#768091;"
            if label:
                label.setStyleSheet(muted_title)
            if desc:
                desc.setStyleSheet(muted_desc)

    def on_enabled_toggled(self, key: str, checked: bool):
        if key in FIXED_SHORTCUT_KEYS:
            return
        if self._handling_change or getattr(self, "_shortcut_conflict_prompt_active", False):
            return

        edit = self.edits[key]
        self._handling_change = True
        try:
            if checked:
                restore = self.disabled_backup.get(key) or DEFAULT_SHORTCUTS.get(key, "")
                edit.setKeySequence(key_sequence_from_text(restore))
                # 여기서 last_sequences를 바로 갱신하면 swap_if_conflict가
                # "변경 없음"으로 판단해서 매크로 단축키 충돌 검사를 건너뛴다.
                # 따라서 토글 ON 직후 충돌 검사는 swap_if_conflict가 담당하게 둔다.
            else:
                current = self.sequence_text(edit)
                if current:
                    self.disabled_backup[key] = current
                edit.clear()
                self.last_sequences[key] = ""
        finally:
            self._handling_change = False

        self.apply_enabled_state(key, checked)

        if checked:
            self.swap_if_conflict(key)

    def swap_if_conflict(self, key: str, notify=True):
        if key in FIXED_SHORTCUT_KEYS:
            return
        if self._handling_change or getattr(self, "_shortcut_conflict_prompt_active", False):
            return

        if not self.checks[key].isChecked():
            return

        edit = self.edits[key]
        new_text = self.sequence_text(edit)
        old_text = self.last_sequences.get(key, "")

        if not new_text:
            self.last_sequences[key] = ""
            return

        if new_text == old_text:
            return

        def restore_previous_shortcut():
            self._handling_change = True
            try:
                if old_text:
                    edit.setKeySequence(key_sequence_from_text(old_text))
                else:
                    edit.clear()
                self.last_sequences[key] = old_text
            finally:
                self._handling_change = False

        # 고정 단축키는 다른 기능과 교체하지 않는다. 같은 키 입력은 되돌린다.
        for fixed_key in FIXED_SHORTCUT_KEYS:
            fixed_text = fixed_shortcut_text(fixed_key, portable=True)
            if fixed_text and fixed_text == new_text:
                fixed_label = self.labels.get(fixed_key).text() if self.labels.get(fixed_key) else fixed_key
                label = self.labels.get(key).text() if self.labels.get(key) else key
                QMessageBox.warning(
                    self,
                    tr_text("고정 단축키 충돌", self._ui_language),
                    (
                        f"{fixed_label} is a fixed shortcut and cannot be changed.\n\n"
                        f"{label}: {new_text}"
                        if self._ui_language == LANG_EN else
                        f"'{fixed_label}'은 고정 단축키라서 변경할 수 없습니다.\n\n"
                        f"{label}: {new_text}"
                    ),
                )
                restore_previous_shortcut()
                return

        # 매크로 단축키와도 서로 감시한다.
        for macro in getattr(self.settings, "macros", []) or []:
            if not macro.get("enabled", True):
                continue
            macro_seq = str(macro.get("shortcut", "") or "")
            if not macro_seq:
                continue
            if key_sequence_to_portable(key_sequence_from_text(macro_seq), macro_seq) == new_text:
                label = self.labels.get(key).text() if self.labels.get(key) else key
                macro_name = str(macro.get("name", "매크로"))
                ans = self.ask_shortcut_conflict_question(
                    self,
                    "매크로 단축키 비활성화 확인",
                    f"'{macro_name}' 매크로가 같은 단축키를 사용 중입니다.\n\n"
                    f"매크로 단축키를 비활성화하고 '{label}'에 지정할까요?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if ans != QMessageBox.StandardButton.Yes:
                    restore_previous_shortcut()
                    return
                macro["enabled"] = False
                macro["shortcut"] = ""
                break

        # 개별 글꼴 프리셋 단축키와도 서로 감시한다.
        # 실제 프리셋 비활성화는 OK 저장 시 메인 창에서 최종 설정과 다시 대조한 뒤 적용한다.
        parent = self.parent()
        for preset_name, preset in list(getattr(parent, "item_text_presets", {}) .items() if parent is not None else []):
            if str(preset_name) in self._pending_disabled_item_presets:
                continue
            if not preset.get("enabled", True):
                continue
            item_seq = str(preset.get("shortcut", "") or "")
            if item_seq and key_sequence_to_portable(key_sequence_from_text(item_seq), item_seq) == new_text:
                label = self.labels.get(key).text() if self.labels.get(key) else key
                ans = self.ask_shortcut_conflict_question(
                    self,
                    tr_text("개별 프리셋 단축키 비활성화 확인", self._ui_language),
                    (
                        f"'{preset_name}' individual font preset is using the same shortcut.\n\n"
                        f"Disable the individual font preset shortcut and assign it to '{label}'?"
                        if self._ui_language == LANG_EN else
                        f"'{preset_name}' 개별 글꼴 프리셋이 같은 단축키를 사용 중입니다.\n\n"
                        f"개별 글꼴 프리셋 단축키를 비활성화하고 '{label}'에 지정할까요?"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if ans != QMessageBox.StandardButton.Yes:
                    restore_previous_shortcut()
                    return
                self._pending_disabled_item_presets.add(str(preset_name))
                break

        other_key = None
        for k, other_edit in self.edits.items():
            if k == key:
                continue
            if not self.checks[k].isChecked():
                continue
            if self.sequence_text(other_edit) == new_text:
                other_key = k
                break

        if other_key and notify:
            new_label = self.labels.get(key).text() if self.labels.get(key) else key
            old_label = self.labels.get(other_key).text() if self.labels.get(other_key) else other_key
            old_text_display = old_text if old_text else tr_text("비어 있음", self._ui_language)
            ans = self.ask_shortcut_conflict_question(
                self,
                "단축키 교체 확인",
                f"이미 사용 중인 단축키입니다.\n\n"
                f"{new_label}: {new_text}\n"
                f"{old_label}: {old_text_display}\n\n"
                f"{tr_text('서로 교체해서 사용할까요?', self._ui_language)}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                restore_previous_shortcut()
                return

        self._handling_change = True
        try:
            if other_key:
                other_edit = self.edits[other_key]
                if old_text:
                    other_edit.setKeySequence(key_sequence_from_text(old_text))
                else:
                    other_edit.clear()
                self.last_sequences[other_key] = old_text

            self.last_sequences[key] = new_text
        finally:
            self._handling_change = False

    def on_editing_finished(self, key: str):
        self.swap_if_conflict(key, notify=True)

    def reset_defaults(self):
        if QMessageBox.question(self, tr_text("기본값 복구", self._ui_language), tr_text("단축키를 전부 기본값으로 돌릴까요?", self._ui_language)) != QMessageBox.StandardButton.Yes:
            return

        self._handling_change = True
        try:
            self.disabled_backup.clear()
            for key, value in DEFAULT_SHORTCUTS.items():
                if key in self.checks:
                    self.checks[key].setChecked(True)
                if key in FIXED_SHORTCUT_KEYS:
                    self.settings.shortcuts[key] = DEFAULT_SHORTCUTS.get(key, "")
                    self.settings.enabled[key] = True
                    self.last_sequences[key] = fixed_shortcut_text(key, portable=True)
                    if key in getattr(self, "fixed_labels", {}):
                        self.fixed_labels[key].setText(f"{fixed_shortcut_text(key, portable=False)}  ·  {tr_text('고정', self._ui_language)}")
                    continue
                if key in self.edits:
                    self.edits[key].setKeySequence(key_sequence_from_text(value))
                    self.last_sequences[key] = key_sequence_to_portable(self.edits[key].keySequence())
                    self.apply_enabled_state(key, True)
        finally:
            self._handling_change = False

    def accept(self):
        for key, edit in self.edits.items():
            enabled = self.checks[key].isChecked()
            self.settings.set_enabled(key, enabled)
            if enabled:
                self.settings.set_seq(key, edit.keySequence())
            else:
                self.settings.shortcuts[key] = ""
        enforce_fixed_shortcuts(self.settings)
        super().accept()

    def get_settings(self) -> ShortcutSettings:
        return self.settings

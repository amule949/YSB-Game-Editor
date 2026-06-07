from PyQt6.QtWidgets import QStyledItemDelegate, QTextEdit
from PyQt6.QtGui import QTextCursor, QKeySequence
from PyQt6.QtCore import Qt, QEvent, QTimer

from ysb.settings.shortcut_settings import key_event_matches_sequence


class MultilineDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, shortcut_getter=None, linebreak_getter=None, enter_commit_callback=None):
        super().__init__(parent)
        self.shortcut_getter = shortcut_getter
        self.linebreak_getter = linebreak_getter
        self.enter_commit_callback = enter_commit_callback

    def createEditor(self, parent, option, index):
        editor = QTextEdit(parent)
        editor.setAcceptRichText(False)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor.installEventFilter(self)
        self._install_symbol_shortcuts(editor)
        return editor

    def _install_symbol_shortcuts(self, editor):
        # QTextEdit 위에 QShortcut을 직접 얹으면 Ctrl+Alt+Shift 계열에서
        # Windows/IME/AltGr 처리와 QTextEdit 기본 키 처리 순서가 엉켜,
        # 커서 앞 글자가 함께 딸려 들어오는 사례가 생길 수 있다.
        # 그래서 특수문자 입력은 eventFilter에서 실제 문자 키가 눌린 순간만
        # 정확히 매칭해서 직접 처리한다.
        editor._special_shortcut_map = {}
        if not self.shortcut_getter:
            return
        try:
            shortcut_map = self.shortcut_getter()
        except Exception:
            shortcut_map = {}
        for symbol, seq in shortcut_map.items():
            try:
                if seq and not seq.isEmpty():
                    editor._special_shortcut_map[symbol] = seq
            except Exception:
                pass

    def setEditorData(self, editor, index):
        editor.setText(index.model().data(index, Qt.ItemDataRole.EditRole) or "")
        try:
            editor._ysb_table_row = int(index.row())
            editor._ysb_table_col = int(index.column())
        except Exception:
            pass

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText(), Qt.ItemDataRole.EditRole)

    def _insert_symbol(self, editor, symbol):
        cursor = editor.textCursor()
        selected = cursor.selectedText()
        pair_map = {
            "「」": ("「", "」"),
            "『』": ("『", "』"),
        }
        if symbol in pair_map:
            left, right = pair_map[symbol]
            if selected:
                cursor.insertText(left + selected + right)
            else:
                cursor.insertText(left + right)
                cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, 1)
            editor.setTextCursor(cursor)
            return
        editor.insertPlainText(symbol)

    def _event_to_keysequence(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return QKeySequence()
        try:
            mods_value = event.modifiers().value
        except AttributeError:
            mods_value = int(event.modifiers())
        return QKeySequence(mods_value | key)

    def _is_alt_modifier_guard_event(self, event):
        # Ctrl+Shift를 누른 상태에서 Alt만 추가로 누르는 순간은
        # Windows 입력기/언어 전환(Alt+Shift) 및 AltGr(Ctrl+Alt) 계열과
        # 충돌하기 쉽다. 텍스트 편집 중에는 이 modifier-only Alt 이벤트를
        # QTextEdit 기본 처리로 넘기지 않아 커서/선택 상태 흔들림을 막는다.
        try:
            if event.key() != Qt.Key.Key_Alt:
                return False
            mods = event.modifiers()
            return bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
        except Exception:
            return False

    def _symbol_shortcut_matches(self, event, seq):
        try:
            return key_event_matches_sequence(event, seq)
        except Exception:
            return False

    def _handle_symbol_shortcut(self, editor, event):
        shortcut_map = getattr(editor, '_special_shortcut_map', {}) or {}
        for symbol, seq in shortcut_map.items():
            if self._symbol_shortcut_matches(event, seq):
                self._insert_symbol(editor, symbol)
                event.accept()
                return True
        return False

    def _linebreak_matches(self, event):
        # 기본 안전장치: Shift+Enter는 항상 줄내림으로 인정
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            return True
        if not self.linebreak_getter:
            return False
        seq = self.linebreak_getter()
        if not seq or seq.isEmpty():
            return False
        pressed = self._event_to_keysequence(event)
        return pressed.matches(seq) == QKeySequence.SequenceMatch.ExactMatch

    def eventFilter(self, editor, event):
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if self._is_alt_modifier_guard_event(event):
                event.accept()
                return True
        if event.type() == QEvent.Type.KeyPress:
            if self._handle_symbol_shortcut(editor, event):
                return True
            if self._linebreak_matches(event):
                editor.insertPlainText("\n")
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                row = getattr(editor, "_ysb_table_row", None)
                col = getattr(editor, "_ysb_table_col", None)
                stay_current = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                self.commitData.emit(editor)
                self.closeEditor.emit(editor)
                callback = getattr(self, "enter_commit_callback", None)
                if callable(callback):
                    QTimer.singleShot(0, lambda r=row, c=col, stay=stay_current: callback(r, c, stay_current=stay))
                return True
        return super().eventFilter(editor, event)

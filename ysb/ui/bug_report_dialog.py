# -*- coding: utf-8 -*-
"""User-consent bug report packaging dialog.

This module intentionally prepares mail/report files only. It never sends mail
or uploads logs by itself.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ysb.core.crash_reporter import (
    BUG_REPORT_OPTION_LAST_CREATED_AT,
    SUPPORT_EMAIL,
    build_bug_report_package,
    clear_pending_fatal_marker,
    collect_recent_log_files,
    load_pending_fatal_marker,
    open_eml_draft,
    open_mail_draft,
    reveal_path,
)
from ysb.ui.main_window_support import save_app_options, translate_ui_text


class FatalBugReportDialog(QDialog):
    def __init__(self, marker: dict | None = None, parent=None):
        super().__init__(parent)
        self.marker = marker or {}
        self.action = "later"
        self.setWindowTitle(translate_ui_text("치명적 오류 보고"))
        self.resize(720, 620)
        self._build_ui()

    def tr(self, text: str) -> str:  # noqa: D401 - small UI helper
        return translate_ui_text(text)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel(self.tr("이전 실행에서 치명적인 오류가 감지되었습니다."))
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        root.addWidget(title)

        body = QLabel(self.tr(
            "문제 해결을 위해 최근 로그를 묶어 개발자에게 보낼 수 있습니다. "
            "프로젝트 파일과 작업 이미지는 자동으로 포함하지 않습니다."
        ))
        body.setWordWrap(True)
        root.addWidget(body)

        meta_lines = []
        if self.marker.get("created_at"):
            meta_lines.append(f"{self.tr('오류 시각')}: {self.marker.get('created_at')}")
        if self.marker.get("exctype"):
            meta_lines.append(f"{self.tr('오류 종류')}: {self.marker.get('exctype')}")
        if self.marker.get("message"):
            msg = str(self.marker.get("message") or "")
            if len(msg) > 240:
                msg = msg[:237] + "..."
            meta_lines.append(f"{self.tr('오류 내용')}: {msg}")
        if meta_lines:
            meta = QLabel("\n".join(meta_lines))
            meta.setWordWrap(True)
            meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            meta.setStyleSheet("padding: 8px; border: 1px solid rgba(128,128,128,80); border-radius: 6px;")
            root.addWidget(meta)

        root.addWidget(QLabel(self.tr("메일 제목")))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(self.tr("예: 텍스트 이동 중 튕김"))
        root.addWidget(self.title_edit)

        root.addWidget(QLabel(self.tr("상세 설명")))
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText(self.tr("어떤 작업 중이었는지 적어주세요."))
        self.desc_edit.setMinimumHeight(90)
        root.addWidget(self.desc_edit)

        self.include_logs = QCheckBox(self.tr("최근 로그 포함"))
        self.include_logs.setChecked(True)
        root.addWidget(self.include_logs)

        self.sanitize_logs = QCheckBox(self.tr("사용자 경로를 가능한 한 가려서 포함"))
        self.sanitize_logs.setChecked(True)
        root.addWidget(self.sanitize_logs)

        root.addWidget(QLabel(self.tr("포함 예정 로그")))
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(110)
        for p in collect_recent_log_files():
            try:
                item = QListWidgetItem(str(Path(p).name))
                item.setToolTip(str(p))
                self.file_list.addItem(item)
            except Exception:
                pass
        if self.file_list.count() <= 0:
            self.file_list.addItem(self.tr("최근 로그를 찾지 못했습니다."))
        root.addWidget(self.file_list)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(line)

        note = QLabel(self.tr(
            "생성 후 제목별 버그 리포트 폴더를 만들고, 그 안에 작성 중 메일용 EML 초안/로그 ZIP/본문 TXT를 넣습니다. "
            "EML 초안이 작성창으로 열리면 보내기만 누르면 됩니다. 실제 전송은 사용자가 직접 확인한 뒤 진행합니다."
        ))
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.create_btn = QPushButton(self.tr("리포트 패키지 만들기"))
        self.later_btn = QPushButton(self.tr("다음에 다시 묻기"))
        self.never_btn = QPushButton(self.tr("이번 오류 다시 묻지 않기"))
        buttons.addWidget(self.create_btn)
        buttons.addWidget(self.later_btn)
        buttons.addWidget(self.never_btn)
        root.addLayout(buttons)

        self.create_btn.clicked.connect(self._accept_create)
        self.later_btn.clicked.connect(self._reject_later)
        self.never_btn.clicked.connect(self._reject_never)

    def _accept_create(self) -> None:
        self.action = "create"
        self.accept()

    def _reject_later(self) -> None:
        self.action = "later"
        self.reject()

    def _reject_never(self) -> None:
        self.action = "never"
        self.reject()

    def title_text(self) -> str:
        return str(self.title_edit.text() or "").strip()

    def description_text(self) -> str:
        return str(self.desc_edit.toPlainText() or "").strip()


def maybe_prompt_previous_fatal_report(parent=None) -> None:
    """Ask the user whether to package logs after a previous fatal crash."""
    try:
        marker = load_pending_fatal_marker()
        if not marker:
            return
        options = dict(getattr(parent, "app_options", {}) or {})
        dlg = FatalBugReportDialog(marker=marker, parent=parent)
        result = dlg.exec()
        if result == QDialog.DialogCode.Accepted and dlg.action == "create":
            package = build_bug_report_package(
                title=dlg.title_text(),
                description=dlg.description_text(),
                marker=marker,
                include_logs=bool(dlg.include_logs.isChecked()),
                sanitize_logs=bool(dlg.sanitize_logs.isChecked()),
            )
            try:
                QApplication.clipboard().setText(str(package.get("body") or ""))
            except Exception:
                pass
            try:
                # Prefer the generated X-Unsent EML draft because it can keep
                # To/Subject/body and the ZIP attachment together. Keep mailto
                # as a fallback for environments that cannot open draft EMLs.
                opened_eml = open_eml_draft(package.get("eml_path"))
                if not opened_eml:
                    open_mail_draft(subject=str(package.get("subject") or ""), body=str(package.get("body") or ""))
            except Exception:
                try:
                    open_mail_draft(subject=str(package.get("subject") or ""), body=str(package.get("body") or ""))
                except Exception:
                    pass
            try:
                reveal_path(package.get("zip_path"))
            except Exception:
                pass
            clear_pending_fatal_marker()
            try:
                options[BUG_REPORT_OPTION_LAST_CREATED_AT] = marker.get("created_at") or ""
                if parent is not None:
                    parent.app_options.update(options)
                    if hasattr(parent, "save_app_options_cache"):
                        parent.save_app_options_cache()
                    else:
                        save_app_options(parent.app_options)
                else:
                    save_app_options(options)
            except Exception:
                pass
            _show_report_created_message(parent, package)
            return

        if dlg.action == "never":
            # Dismiss only the currently detected crash. This is not a global
            # opt-out; a future new crash will create a new marker and ask again.
            clear_pending_fatal_marker()
            return
        # later: keep marker so the user can be asked again next startup.
    except Exception:
        pass


def _show_report_created_message(parent, package: dict) -> None:
    try:
        zip_path = package.get("zip_path")
        eml_path = package.get("eml_path")
        mail_body_path = package.get("mail_body_path")
        subject = package.get("subject")
        text = "\n".join([
            translate_ui_text("버그 리포트 패키지를 만들었습니다."),
            "",
            f"{translate_ui_text('받는 사람')}: {SUPPORT_EMAIL}",
            f"{translate_ui_text('제목')}: {subject}",
            f"ZIP: {zip_path}",
            f"EML: {eml_path}",
            f"TXT: {mail_body_path}",
            "",
            translate_ui_text("EML 초안이 작성창으로 열리면 내용을 확인한 뒤 보내기만 누르면 됩니다."),
            translate_ui_text("메일 작성창이 열리지 않으면 TXT 내용을 복사하고 ZIP을 첨부해서 보내주세요."),
            translate_ui_text("메일 본문은 클립보드에도 복사했습니다."),
        ])
        QMessageBox.information(parent, translate_ui_text("버그 리포트 생성 완료"), text)
    except Exception:
        pass

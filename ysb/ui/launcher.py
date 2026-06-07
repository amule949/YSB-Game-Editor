# -*- coding: utf-8 -*-
"""
YSB Game Editor launcher/start screen.

v1.8.0 방향:
- 프로그램 시작 시 바로 빈 에디터로 들어가지 않고, 시작 화면에서 새 프로젝트/열기/복구/최근 프로젝트를 고른다.
- 최근 프로젝트 목록과 썸네일은 작업환경 캐시로 관리한다.
"""

import hashlib
import json
import os
import time
import zipfile
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QPixmap, QPainter, QColor, QAction, QPixmapCache
from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QToolButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QScrollArea, QSizePolicy, QMenu
)

from ysb.core.cache_utils import get_cache_dir, get_cache_file
from ysb.i18n.lang_text import tr_ui, normalize_language, LANG_KO, LANG_EN


RECENT_PROJECTS_FILE = "recent_projects.json"
RECENT_THUMBNAIL_DIR = "recent_thumbnails"
MAX_RECENT_PROJECTS = 20
VISIBLE_RECENT_PROJECTS = 12


def _now_iso():
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


class RecentProjectStore:
    """최근 프로젝트 목록과 썸네일 캐시를 관리한다."""

    def __init__(self):
        self.path = get_cache_file(RECENT_PROJECTS_FILE)
        self.thumbnail_dir = get_cache_dir() / RECENT_THUMBNAIL_DIR
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

    def load(self):
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    items = data.get("recent_projects", [])
                elif isinstance(data, list):
                    items = data
                else:
                    items = []
            else:
                items = []
        except Exception:
            items = []

        out = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            p = str(item.get("project_path") or item.get("ysbg_path") or item.get("ysbt_path") or item.get("path") or "").strip()
            if not p:
                continue
            key = os.path.abspath(p).lower()
            if key in seen:
                continue
            seen.add(key)
            normalized = dict(item)
            normalized["project_path"] = os.path.abspath(p)
            normalized["ysbt_path"] = os.path.abspath(p)  # compatibility key used by old card code
            normalized["title"] = str(normalized.get("title") or Path(p).stem)
            normalized["page_count"] = _safe_int(normalized.get("page_count"), 0)
            normalized["last_opened_at"] = str(normalized.get("last_opened_at") or "")
            normalized["thumbnail_path"] = str(normalized.get("thumbnail_path") or "")
            normalized["workspace_dir"] = os.path.abspath(str(normalized.get("workspace_dir") or "")) if normalized.get("workspace_dir") else ""
            normalized["file_exists"] = os.path.exists(normalized["ysbt_path"])
            out.append(normalized)
        return out[:MAX_RECENT_PROJECTS]

    def save(self, items):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "recent_projects": list(items or [])[:MAX_RECENT_PROJECTS],
            }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def project_key(self, ysbt_path):
        raw = os.path.abspath(str(ysbt_path or "")).lower().encode("utf-8", errors="ignore")
        return hashlib.sha1(raw).hexdigest()[:16]

    def thumbnail_path_for(self, ysbt_path):
        return self.thumbnail_dir / f"{self.project_key(ysbt_path)}.jpg"

    def _save_thumbnail_pixmap(self, pixmap, ysbt_path, size=QSize(360, 250)):
        """QPixmap을 최근 프로젝트용 썸네일 캐시에 저장한다."""
        try:
            if not ysbt_path or pixmap is None or pixmap.isNull():
                return ""
            dest = self.thumbnail_path_for(ysbt_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            canvas = QPixmap(size)
            canvas.fill(QColor("#181a1f"))
            scaled = pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter = QPainter(canvas)
            try:
                x = int((size.width() - scaled.width()) / 2)
                y = int((size.height() - scaled.height()) / 2)
                painter.drawPixmap(x, y, scaled)
            finally:
                painter.end()
            # 같은 파일명으로 덮어쓴 뒤에도 화면에 이전 썸네일이 남지 않게 캐시를 비운다.
            try:
                QPixmapCache.remove(str(dest))
            except Exception:
                pass
            if canvas.save(str(dest), "JPG", 88):
                return str(dest)
        except Exception:
            pass

    def clear(self):
        """최근 프로젝트 목록을 비운다. 썸네일 캐시는 다음 기록/복구 때 다시 정리된다."""
        self.save([])
        return True
        return ""

    def make_thumbnail(self, image_paths, ysbt_path, size=QSize(360, 250)):
        """첫 페이지 이미지를 최근 프로젝트용 썸네일로 저장한다."""
        if not ysbt_path:
            return ""
        try:
            first = None
            for p in image_paths or []:
                if p and os.path.exists(str(p)):
                    first = str(p)
                    break
            if not first:
                return self.make_thumbnail_from_ysbt(ysbt_path, size=size, force=False)

            src = QPixmap(first)
            if src.isNull():
                return self.make_thumbnail_from_ysbt(ysbt_path, size=size, force=False)
            return self._save_thumbnail_pixmap(src, ysbt_path, size=size)
        except Exception:
            return self.make_thumbnail_from_ysbt(ysbt_path, size=size, force=False)

    def _normalize_zip_name(self, name):
        name = str(name or "").replace("\\", "/").lstrip("/")
        while name.startswith("./"):
            name = name[2:]
        return name

    def make_thumbnail_from_ysbt(self, ysbt_path, size=QSize(360, 250), force=True):
        """최근 썸네일이 사라졌을 때 project.json 또는 .ysbg 내부 첫 페이지 이미지에서 다시 만든다."""
        try:
            if not ysbt_path or not os.path.exists(str(ysbt_path)):
                return ""
            dest = self.thumbnail_path_for(ysbt_path)
            if (not force) and dest.exists() and dest.stat().st_size > 0:
                return str(dest)

            # 평소 최근 항목은 작업 폴더/project.json을 가리킨다.
            project_json_path = ""
            if os.path.isdir(str(ysbt_path)):
                project_json_path = os.path.join(str(ysbt_path), "project.json")
            elif os.path.basename(str(ysbt_path)) == "project.json":
                project_json_path = str(ysbt_path)
            if project_json_path and os.path.exists(project_json_path):
                try:
                    with open(project_json_path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    pages = payload.get("pages") if isinstance(payload, dict) else []
                    page = pages[0] if isinstance(pages, list) and pages and isinstance(pages[0], dict) else {}
                    base_dir = os.path.dirname(project_json_path)
                    for rel in (page.get("image"), page.get("working_source"), page.get("clean"), page.get("final_paint"), page.get("final_paint_above")):
                        if not rel:
                            continue
                        candidate = rel if os.path.isabs(str(rel)) else os.path.join(base_dir, str(rel))
                        if os.path.exists(candidate):
                            pix = QPixmap(candidate)
                            if not pix.isNull():
                                return self._save_thumbnail_pixmap(pix, ysbt_path, size=size)
                except Exception:
                    pass
                return ""

            with zipfile.ZipFile(str(ysbt_path), "r") as zf:
                try:
                    payload = json.loads(zf.read("project.json").decode("utf-8"))
                except Exception:
                    payload = {}
                pages = payload.get("pages") if isinstance(payload, dict) else []
                if not isinstance(pages, list) or not pages:
                    return ""

                # 기본은 원본 이미지. 없으면 작업본/클린본/최종본 순서로 보정한다.
                page = pages[0] if isinstance(pages[0], dict) else {}
                candidates = [
                    page.get("image"),
                    page.get("working_source"),
                    page.get("clean"),
                    page.get("final_paint"),
                    page.get("final_paint_above"),
                ]
                names = set(zf.namelist())
                image_bytes = None
                for rel in candidates:
                    rel = self._normalize_zip_name(rel)
                    if rel and rel in names:
                        try:
                            image_bytes = zf.read(rel)
                            break
                        except Exception:
                            image_bytes = None
                if not image_bytes:
                    return ""

            pix = QPixmap()
            if not pix.loadFromData(image_bytes):
                return ""
            return self._save_thumbnail_pixmap(pix, ysbt_path, size=size)
        except Exception:
            return ""

    def repair_recent_project_thumbnails(self, force=False):
        """최근 프로젝트의 썸네일 경로가 사라졌거나 갱신이 필요할 때 .ysbg에서 재생성한다."""
        changed = False
        repaired = 0
        items = self.load()
        for item in items:
            path = str(item.get("ysbt_path") or "")
            if not path or not os.path.exists(path):
                continue
            thumb = str(item.get("thumbnail_path") or "")
            missing = (not thumb) or (not os.path.exists(thumb)) or (os.path.exists(thumb) and os.path.getsize(thumb) <= 0)
            if force or missing:
                new_thumb = self.make_thumbnail_from_ysbt(path, force=True)
                if new_thumb:
                    if item.get("thumbnail_path") != new_thumb:
                        item["thumbnail_path"] = new_thumb
                        changed = True
                    repaired += 1
        if changed:
            self.save(items)
        return repaired

    def add_project(self, ysbt_path, title=None, page_count=0, thumbnail_path="", workspace_dir=""):
        if not ysbt_path:
            return False
        abs_path = os.path.abspath(str(ysbt_path))
        items = self.load()
        key = abs_path.lower()
        items = [i for i in items if str(i.get("ysbt_path", "")).lower() != key]
        if not thumbnail_path:
            thumbnail_path = self.make_thumbnail_from_ysbt(abs_path, force=False)
        items.insert(0, {
            "title": str(title or Path(abs_path).stem),
            "project_path": abs_path,
            "ysbt_path": abs_path,  # compatibility key used by old card code
            "thumbnail_path": str(thumbnail_path or ""),
            "workspace_dir": os.path.abspath(str(workspace_dir or "")) if workspace_dir else "",
            "last_opened_at": _now_iso(),
            "page_count": _safe_int(page_count, 0),
            "file_exists": os.path.exists(abs_path),
        })
        return self.save(items[:MAX_RECENT_PROJECTS])

    def remove_project(self, ysbt_path):
        if not ysbt_path:
            return False
        key = os.path.abspath(str(ysbt_path)).lower()
        items = [i for i in self.load() if str(i.get("ysbt_path", "")).lower() != key]
        return self.save(items)


class RecentProjectCard(QFrame):
    openRequested = pyqtSignal(str)
    removeRequested = pyqtSignal(str)
    revealRequested = pyqtSignal(str)

    def __init__(self, project, lang=LANG_KO, parent=None):
        super().__init__(parent)
        self.project = dict(project or {})
        self.lang = normalize_language(lang)
        self.setObjectName("RecentProjectCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(230)
        self.setMaximumWidth(310)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build()

    def t(self, text):
        return tr_ui(text, self.lang)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        thumb = QLabel()
        thumb.setObjectName("RecentProjectThumbnail")
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setFixedHeight(142)
        thumb.setMinimumWidth(210)
        thumb_path = str(self.project.get("thumbnail_path") or "")
        if thumb_path:
            try:
                # 같은 파일명으로 썸네일을 덮어쓸 때 Qt pixmap 캐시 때문에 이전 이미지가 보일 수 있어 제거한다.
                QPixmapCache.remove(thumb_path)
            except Exception:
                pass
        pix = QPixmap(thumb_path) if thumb_path and os.path.exists(thumb_path) else QPixmap()
        if not pix.isNull():
            thumb.setPixmap(pix.scaled(250, 142, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            thumb.setText(self.t("썸네일 없음"))
        layout.addWidget(thumb)

        title_row = QHBoxLayout()
        title = QLabel(str(self.project.get("title") or Path(str(self.project.get("ysbt_path") or "")).stem or self.t("제목 없음")))
        title.setObjectName("RecentProjectTitle")
        title.setWordWrap(True)
        self.more_button = QToolButton()
        self.more_button.setText("⋯")
        self.more_button.setFixedSize(28, 26)
        # QToolButton.clicked 는 checked(bool)를 넘긴다.
        # 이 bool 값이 QMenu.exec(pos) 의 pos 인자로 들어가면 PyQt6에서 크래시가 난다.
        self.more_button.clicked.connect(self._open_more_menu)
        title_row.addWidget(title, 1)
        title_row.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(title_row)

        last = QLabel(f"{self.t('마지막 열기')}: {self.project.get('last_opened_at') or '-'}")
        last.setObjectName("RecentProjectMeta")
        layout.addWidget(last)

        page_count = _safe_int(self.project.get("page_count"), 0)
        pages = f"{page_count}{self.t('페이지')}" if self.lang == LANG_KO else f"{page_count} page(s)"
        exists = bool(self.project.get("file_exists", True)) and os.path.exists(str(self.project.get("ysbt_path") or ""))
        status_text = self.t("로컬 있음") if exists else self.t("파일을 찾을 수 없음")
        status = QLabel(f"{pages} · {status_text}")
        status.setObjectName("RecentProjectStatusMissing" if not exists else "RecentProjectStatus")
        layout.addWidget(status)

        self.setToolTip(str(self.project.get("ysbt_path") or ""))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self.open_menu(event.globalPos())

    def _open(self):
        path = str(self.project.get("ysbt_path") or "")
        if path and os.path.exists(path):
            self.openRequested.emit(path)

    def _open_more_menu(self, checked=False):
        self.open_menu()

    def open_menu(self, pos=None):
        # contextMenuEvent에서는 QPoint가 들어오지만,
        # QToolButton.clicked 연결 실수/호출 방식에 따라 bool이 들어올 수 있으므로 방어한다.
        if isinstance(pos, bool):
            pos = None

        menu = QMenu(self)
        path = str(self.project.get("ysbt_path") or "")
        act_open = QAction(self.t("열기"), self)
        act_reveal = QAction(self.t("폴더 위치 열기"), self)
        act_remove = QAction(self.t("최근 목록에서 제거"), self)
        act_open.setEnabled(bool(path and os.path.exists(path)))
        act_reveal.setEnabled(bool(path and os.path.exists(path)))
        menu.addAction(act_open)
        menu.addAction(act_reveal)
        menu.addSeparator()
        menu.addAction(act_remove)
        if pos is None:
            anchor = getattr(self, "more_button", None)
            if anchor is not None:
                pos = anchor.mapToGlobal(anchor.rect().bottomRight())
            else:
                pos = self.mapToGlobal(self.rect().bottomRight())

        chosen = menu.exec(pos)
        if chosen == act_open:
            self._open()
        elif chosen == act_reveal:
            self.revealRequested.emit(path)
        elif chosen == act_remove:
            self.removeRequested.emit(path)


class LauncherWidget(QWidget):
    newProjectRequested = pyqtSignal()
    importImagesRequested = pyqtSignal()
    openProjectRequested = pyqtSignal()
    recoverRequested = pyqtSignal()
    optionsRequested = pyqtSignal()
    helpRequested = pyqtSignal()
    droppedProjectOpenRequested = pyqtSignal(str)
    recentProjectOpenRequested = pyqtSignal(str)
    recentProjectRemoveRequested = pyqtSignal(str)
    recentProjectRevealRequested = pyqtSignal(str)

    def __init__(self, recent_store, app_version="", lang=LANG_KO, theme="dark", parent=None):
        super().__init__(parent)
        self.store = recent_store
        self.app_version = app_version
        self.lang = normalize_language(lang)
        self.theme = str(theme or "dark").lower()
        self.setObjectName("LauncherWidget")
        self.setAcceptDrops(True)
        self._build()
        self.apply_style()
        self.refresh()

    def t(self, text):
        return tr_ui(text, self.lang)

    def set_language(self, lang):
        self.lang = normalize_language(lang)
        self.rebuild()

    def set_theme(self, theme):
        self.theme = str(theme or "dark").lower()
        self.apply_style()

    def rebuild(self):
        old = self.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            QWidget().setLayout(old)
        self._build()
        self.apply_style()
        self.refresh()

    def _side_button(self, text, slot, primary=False):
        btn = QPushButton(self.t(text))
        btn.setObjectName("LauncherPrimaryButton" if primary else "LauncherSideButton")
        btn.setMinimumHeight(42)
        btn.clicked.connect(slot)
        return btn

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(24)

        side = QFrame()
        side.setObjectName("LauncherSidePanel")
        side.setAcceptDrops(True)
        side.installEventFilter(self)
        side.setFixedWidth(310)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(22, 22, 22, 22)
        sl.setSpacing(12)

        title = QLabel(self.t("쯔꾸르붕이"))
        title.setObjectName("LauncherAppTitle")
        subtitle = QLabel(f"YSB Game Editor {self.app_version}")
        subtitle.setObjectName("LauncherSubtitle")
        sl.addWidget(title)
        sl.addWidget(subtitle)
        sl.addSpacing(12)

        desc = QLabel(self.t("작업 본체는 project.json이 있는 폴더이고, YSBG는 내보내기 패키지입니다."))
        desc.setWordWrap(True)
        desc.setObjectName("LauncherDescription")
        sl.addWidget(desc)
        sl.addSpacing(10)

        sl.addWidget(self._side_button("새 프로젝트", self.newProjectRequested.emit, primary=True))
        sl.addWidget(self._side_button("YSBG 열기", self.openProjectRequested.emit))
        sl.addWidget(self._side_button("마지막 작업 복구", self.recoverRequested.emit))
        sl.addSpacing(8)
        sl.addSpacing(8)
        sl.addWidget(self._side_button("옵션 / 설정", self.optionsRequested.emit))
        sl.addStretch()

        foot = QLabel(self.t("최근 프로젝트는 로컬 경로를 기본 화면에 직접 노출하지 않습니다."))
        foot.setWordWrap(True)
        foot.setObjectName("LauncherFootnote")
        sl.addWidget(foot)

        main = QFrame()
        main.setObjectName("LauncherMainPanel")
        main.setAcceptDrops(True)
        main.installEventFilter(self)
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(12)

        header = QHBoxLayout()
        htitle = QLabel(self.t("최근 프로젝트"))
        htitle.setObjectName("LauncherSectionTitle")
        self.btn_refresh = QPushButton(self.t("치우기"))
        self.btn_refresh.setObjectName("LauncherRefreshButton")
        self.btn_refresh.clicked.connect(self.clear_recent_projects)
        header.addWidget(htitle)
        header.addStretch()
        header.addWidget(self.btn_refresh)
        ml.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("LauncherRecentScroll")
        self.scroll.setAcceptDrops(True)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        try:
            self.scroll.viewport().setAcceptDrops(True)
            self.scroll.viewport().installEventFilter(self)
        except Exception:
            pass
        self.cards_container = QWidget()
        self.cards_container.setAcceptDrops(True)
        self.cards_container.installEventFilter(self)
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setHorizontalSpacing(14)
        self.cards_layout.setVerticalSpacing(14)
        self.scroll.setWidget(self.cards_container)
        ml.addWidget(self.scroll, 1)

        root.addWidget(side)
        root.addWidget(main, 1)

    def clear_recent_projects(self):
        """최근 프로젝트 목록을 홈화면에서 치운다."""
        try:
            self.store.clear()
        except Exception:
            try:
                self.store.save([])
            except Exception:
                pass
        self.refresh(force_thumbnail_repair=False)

    def force_refresh(self):
        """호환용: 외부 호출 시 썸네일 보정 갱신은 유지한다."""
        self.refresh(force_thumbnail_repair=True)

    def refresh(self, force_thumbnail_repair=False):
        if not hasattr(self, "cards_layout"):
            return
        try:
            # 작업 폴더 위치를 옮기면 기존 recent_thumbnails 경로가 사라질 수 있다.
            # 홈화면 표시 시에는 누락 썸네일을 자동 복구한다. 치우기 버튼은 최근 목록을 비운다.
            self.store.repair_recent_project_thumbnails(force=bool(force_thumbnail_repair))
        except Exception:
            pass
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        projects = self.store.load()[:VISIBLE_RECENT_PROJECTS]
        if not projects:
            empty = QLabel(self.t("아직 최근 프로젝트가 없습니다. 왼쪽에서 새 프로젝트를 만들거나 YSBG를 열어주세요."))
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setObjectName("LauncherEmptyText")
            self.cards_layout.addWidget(empty, 0, 0, 1, 3)
            return

        for i, project in enumerate(projects):
            card = RecentProjectCard(project, self.lang, self.cards_container)
            card.openRequested.connect(self.recentProjectOpenRequested.emit)
            card.removeRequested.connect(self.recentProjectRemoveRequested.emit)
            card.revealRequested.connect(self.recentProjectRevealRequested.emit)
            row = i // 3
            col = i % 3
            self.cards_layout.addWidget(card, row, col)
        self.cards_layout.setRowStretch((len(projects) + 2) // 3, 1)

    def _ysbt_path_from_mime(self, mime):
        try:
            if mime is None or not mime.hasUrls():
                return ""
            for url in mime.urls():
                try:
                    if not url.isLocalFile():
                        continue
                    path = os.path.abspath(str(url.toLocalFile() or ""))
                    if os.path.isfile(path) and (path.lower().endswith(".ysbg") or os.path.basename(path) == "project.json"):
                        return path
                    if os.path.isdir(path) and os.path.exists(os.path.join(path, "project.json")):
                        return os.path.join(path, "project.json")
                except Exception:
                    pass
        except Exception:
            pass
        return ""

    def _handle_ysbt_drag_enter(self, event):
        path = self._ysbt_path_from_mime(event.mimeData() if event is not None else None)
        if path:
            event.acceptProposedAction()
            return True
        return False

    def dragEnterEvent(self, event):
        if self._handle_ysbt_drag_enter(event):
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._handle_ysbt_drag_enter(event):
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        path = self._ysbt_path_from_mime(event.mimeData() if event is not None else None)
        if path:
            event.acceptProposedAction()
            self.droppedProjectOpenRequested.emit(path)
            return
        super().dropEvent(event)

    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.Type.DragEnter:
                if self._handle_ysbt_drag_enter(event):
                    return True
            if event.type() == QEvent.Type.DragMove:
                if self._handle_ysbt_drag_enter(event):
                    return True
            if event.type() == QEvent.Type.Drop:
                path = self._ysbt_path_from_mime(event.mimeData() if event is not None else None)
                if path:
                    event.acceptProposedAction()
                    self.droppedProjectOpenRequested.emit(path)
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def apply_style(self):
        if self.theme == "light":
            self.setStyleSheet("""
                #LauncherWidget { background:#F6F1F4; color:#202124; }
                #LauncherSidePanel { background:#ffffff; border:1px solid #DAD4D8; border-radius:16px; }
                #LauncherMainPanel { background:transparent; }
                #LauncherAppTitle { font-size:26px; font-weight:800; color:#141416; }
                #LauncherSubtitle, #LauncherDescription, #LauncherFootnote, #RecentProjectMeta { color:#625A61; }
                #LauncherDescription { font-size:13px; line-height:145%; }
                #LauncherSectionTitle { font-size:22px; font-weight:750; color:#141416; }
                #LauncherPrimaryButton { background:transparent; color:#8A4A52; border:0; border-left:3px solid #8A4A52; border-radius:0; font-weight:800; text-align:left; padding:8px 12px; }
                #LauncherSideButton { background:transparent; color:#202124; border:0; border-radius:0; text-align:left; padding:8px 12px; }
                #LauncherSideButton:hover, #LauncherPrimaryButton:hover { background:#FBF5F6; }
                #LauncherRefreshButton { background:#ffffff; color:#202124; border:1px solid #cbd2df; border-radius:10px; text-align:left; padding:8px 14px; }
                #LauncherRefreshButton:hover { background:#FBF5F6; }
                #LauncherRecentScroll { background:transparent; }
                #RecentProjectCard { background:#ffffff; border:1px solid #DAD4D8; border-radius:14px; }
                #RecentProjectCard:hover { border:1px solid #8bbcff; background:#fafdff; }
                #RecentProjectThumbnail { background:#F0EAED; border-radius:10px; color:#7a828f; }
                #RecentProjectTitle { font-size:15px; font-weight:700; color:#141416; }
                #RecentProjectStatus { color:#267344; font-size:12px; }
                #RecentProjectStatusMissing { color:#c43d3d; font-size:12px; }
                #LauncherEmptyText { color:#687284; font-size:15px; padding:40px; }
            """)
        else:
            self.setStyleSheet("""
                #LauncherWidget { background:#1f1f22; color:#f2f2f2; }
                #LauncherSidePanel { background:#272a30; border:1px solid #3f444d; border-radius:16px; }
                #LauncherMainPanel { background:transparent; }
                #LauncherAppTitle { font-size:26px; font-weight:800; color:#ffffff; }
                #LauncherSubtitle, #LauncherDescription, #LauncherFootnote, #RecentProjectMeta { color:#b6bdc9; }
                #LauncherDescription { font-size:13px; line-height:145%; }
                #LauncherSectionTitle { font-size:22px; font-weight:750; color:#ffffff; }
                #LauncherPrimaryButton { background:transparent; color:#C78A90; border:0; border-left:3px solid #8A4A52; border-radius:0; font-weight:800; text-align:left; padding:8px 12px; }
                #LauncherSideButton { background:transparent; color:#f2f2f2; border:0; border-radius:0; text-align:left; padding:8px 12px; }
                #LauncherSideButton:hover, #LauncherPrimaryButton:hover { background:#343842; }
                #LauncherRefreshButton { background:#383238; color:#f2f2f2; border:1px solid #625C63; border-radius:10px; text-align:left; padding:8px 14px; }
                #LauncherRefreshButton:hover { background:#454047; }
                #LauncherRecentScroll { background:transparent; }
                #RecentProjectCard { background:#292c33; border:1px solid #49434A; border-radius:14px; }
                #RecentProjectCard:hover { border:1px solid #6aa9ff; background:#322E34; }
                #RecentProjectThumbnail { background:#181a1f; border-radius:10px; color:#8d95a3; }
                #RecentProjectTitle { font-size:15px; font-weight:700; color:#ffffff; }
                #RecentProjectStatus { color:#75d68a; font-size:12px; }
                #RecentProjectStatusMissing { color:#ff7f7f; font-size:12px; }
                #LauncherEmptyText { color:#aab2c0; font-size:15px; padding:40px; }
            """)

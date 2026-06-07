
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QDialogButtonBox, QTextEdit
)
from PyQt6.QtCore import Qt

from ysb.core.cache_utils import get_cache_dir

try:
    from ysb.ui.main_window_support import translate_ui_text, translate_ui_dynamic_text
except Exception:
    def translate_ui_text(text, lang=None): return str(text)
    def translate_ui_dynamic_text(text, lang=None): return str(text)

APP_ROOT = Path(__file__).resolve().parents[2]
LEGACY_GLOSSARY_ROOT = APP_ROOT / "local_models" / "translate" / "glossary"

def _default_glossary_root() -> Path:
    """Return the workspace cache location used for local translation glossary files.

    로컬 번역 단어장은 사용자가 넣고 빼며 관리하는 작업 데이터에 가깝다.
    그래서 AppData가 아니라 Documents/YSB_Translator/cache 아래에 둔다.
    이 위치는 작업환경 캐시와 함께 관리하기 쉽고, 사용자가 폴더 열기로 확인할 수 있다.
    """
    return get_cache_dir() / "translate" / "glossary"

GLOSSARY_ROOT = _default_glossary_root()
IMPORTED_DIR = GLOSSARY_ROOT / "imported"
COMPILED_DIR = GLOSSARY_ROOT / "compiled"
MANIFEST_PATH = GLOSSARY_ROOT / "manifest.json"
COMPILED_PATH = COMPILED_DIR / "local_glossary.json"

_SKIP_PREFIXES = ("prefilter_", "postfilter_", "skiplayer_", "skip_layer_")

# H-dor / Ehnd includes several files that are not plain glossary dictionaries.
# UserDict_@Hdor#0#req.txt is an internal/filter helper dictionary and contains
# artificial markers such as 戰戰, 梦名, 乘名 and EasyTranslator control wrappers.
# It must not be treated as a normal local replacement glossary.
_SKIP_NAME_FRAGMENTS = ("#0#req", "0#req")

_HDOR_INTERNAL_MARKERS = (
    "戰", "梦", "乘", "ゎ形", "ゎ", "≪", "≫", "∬",
    "#m", "#n", "#v",
)


def _migrate_legacy_glossary_if_needed():
    """Best-effort migration from older glossary cache locations to the workspace cache."""
    try:
        if MANIFEST_PATH.exists() or any(IMPORTED_DIR.glob("*.txt")):
            return

        old_roots = [LEGACY_GLOSSARY_ROOT]
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            old_roots.append(Path(local_appdata) / "YSBGameEditor" / "local_models" / "translate" / "glossary")
        old_roots.append(Path.home() / "AppData" / "Local" / "YSBGameEditor" / "local_models" / "translate" / "glossary")

        for root in old_roots:
            try:
                if not root.exists() or root.resolve() == GLOSSARY_ROOT.resolve():
                    continue
                legacy_imported = root / "imported"
                legacy_manifest = root / "manifest.json"
                if legacy_imported.exists():
                    IMPORTED_DIR.mkdir(parents=True, exist_ok=True)
                    for src in legacy_imported.glob("*.txt"):
                        dst = IMPORTED_DIR / src.name
                        if not dst.exists():
                            shutil.copy2(src, dst)
                if legacy_manifest.exists() and not MANIFEST_PATH.exists():
                    try:
                        data = json.loads(legacy_manifest.read_text(encoding="utf-8"))
                        for item in data.get("files", []) if isinstance(data, dict) else []:
                            name = str(item.get("filename") or "")
                            if name:
                                item["imported_path"] = str(IMPORTED_DIR / name)
                        GLOSSARY_ROOT.mkdir(parents=True, exist_ok=True)
                        MANIFEST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                break
            except Exception:
                continue
    except Exception:
        pass

def ensure_dirs():
    IMPORTED_DIR.mkdir(parents=True, exist_ok=True)
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_glossary_if_needed()


def read_manifest():
    ensure_dirs()
    if not MANIFEST_PATH.exists():
        return {"files": []}
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"files": []}
        files = data.get("files")
        if not isinstance(files, list):
            data["files"] = []
        for item in data.get("files", []):
            if isinstance(item, dict):
                name = str(item.get("filename") or "")
                if name:
                    # Imported TXT copies now live in the YSBGameEditor cache area.
                    item["imported_path"] = str(IMPORTED_DIR / name)
        return data
    except Exception:
        return {"files": []}


def write_manifest(data):
    ensure_dirs()
    MANIFEST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_text_any(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp932", "cp949", "euc-kr", "utf-8"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


def _clean_term_value(value: str) -> str:
    value = str(value or "").strip()
    # Remove common EasyTranslator/H-dor wrapping marks if a row slips through.
    value = value.replace("<<", "").replace(">>", "")
    value = value.replace("≪", "").replace("≫", "")
    value = value.replace("∬&", "").replace("∬", "")
    # H-dor style suffix marks such as #N / #M / #N二 are not useful for simple local replacement.
    if "#" in value:
        value = value.split("#", 1)[0].strip()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _is_hdor_internal_row(source: str, target: str) -> bool:
    raw = f"{source}\t{target}".lower()
    # Internal helper rows are meant for EasyTranslator filter stages, not for simple replacement.
    if any(marker in raw for marker in _HDOR_INTERNAL_MARKERS):
        return True
    # Split Korean jamo patterns usually come from filter grammar fragments such as ㄱㅏㄴ/ㅎㅏㄴ.
    if re.search(r"[ㄱ-ㅎㅏ-ㅣ]", raw):
        return True
    return False


def should_parse_file(filename: str) -> bool:
    name = str(filename or "").strip().lower()
    if not name.endswith(".txt"):
        return False
    if name.startswith(_SKIP_PREFIXES):
        return False
    if any(fragment in name for fragment in _SKIP_NAME_FRAGMENTS):
        return False
    # H-dor dictionaries are UserDict_*.txt. Unknown txt files are allowed so users can bring a simple tab dictionary.
    return True


def parse_glossary_txt(path: Path):
    """Return (entries, ignored_lines). Only first two tab-separated fields are used."""
    path = Path(path)
    if not should_parse_file(path.name):
        return [], 0
    text = _read_text_any(path)
    entries = []
    ignored = 0
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        if raw.startswith("//") or raw.startswith(";"):
            continue
        # Filter commands are intentionally ignored for Local AI glossary v1.
        low = raw.lower()
        if low.startswith("_tgl") or low.startswith("pre") or low.startswith("post"):
            ignored += 1
            continue
        parts = raw.split("\t")
        if len(parts) < 2:
            ignored += 1
            continue
        raw_source = str(parts[0] or "").strip()
        raw_target = str(parts[1] or "").strip()
        if _is_hdor_internal_row(raw_source, raw_target):
            ignored += 1
            continue
        source = _clean_term_value(raw_source)
        target = _clean_term_value(raw_target)
        if not source or not target or source == target:
            ignored += 1
            continue
        if _is_hdor_internal_row(source, target):
            ignored += 1
            continue
        # Avoid destructive mega rules.
        if len(source) > 80 or len(target) > 120:
            ignored += 1
            continue
        entries.append({"source": source, "target": target})
    return entries, ignored


def _unique_dest_name(filename: str) -> str:
    ensure_dirs()
    base = Path(filename).name
    stem = Path(base).stem
    suffix = Path(base).suffix or ".txt"
    candidate = IMPORTED_DIR / base
    n = 2
    while candidate.exists():
        candidate = IMPORTED_DIR / f"{stem}_{n}{suffix}"
        n += 1
    return candidate.name


def add_text_files(paths):
    data = read_manifest()
    added = []
    for src in paths:
        src_path = Path(src)
        if not src_path.exists() or src_path.suffix.lower() != ".txt":
            continue
        dest_name = _unique_dest_name(src_path.name)
        dest = IMPORTED_DIR / dest_name
        shutil.copy2(src_path, dest)
        item = {
            "filename": dest_name,
            "source_path": str(src_path),
            "imported_path": str(dest),
            "enabled": True,
            "status": "pending",
            "count": 0,
            "ignored": 0,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        data.setdefault("files", []).append(item)
        added.append(item)
    write_manifest(data)
    compile_glossary()
    return added


def remove_files(filenames):
    data = read_manifest()
    names = set(filenames or [])
    kept = []
    removed = []
    for item in data.get("files", []):
        name = str(item.get("filename") or "")
        if name in names:
            try:
                p = Path(item.get("imported_path") or IMPORTED_DIR / name)
                if p.exists():
                    p.unlink()
            except Exception:
                pass
            removed.append(name)
        else:
            kept.append(item)
    data["files"] = kept
    write_manifest(data)
    compile_glossary()
    return removed


def refresh_files(selected_filenames=None):
    data = read_manifest()
    selected = set(selected_filenames or [])
    do_all = not selected
    for item in data.get("files", []):
        name = str(item.get("filename") or "")
        if not do_all and name not in selected:
            continue
        src = Path(str(item.get("source_path") or ""))
        dest = Path(str(item.get("imported_path") or IMPORTED_DIR / name))
        if src.exists():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                item["status"] = "refreshed"
            except Exception as e:
                item["status"] = f"refresh error: {e}"
        elif dest.exists():
            item["status"] = "source missing; using imported copy"
        else:
            item["status"] = "missing"
        item["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_manifest(data)
    return compile_glossary()


def compile_glossary():
    ensure_dirs()
    data = read_manifest()
    merged = {}
    total_raw = 0
    ignored_total = 0
    used_files = 0
    for item in data.get("files", []):
        name = str(item.get("filename") or "")
        if not item.get("enabled", True):
            item["status"] = "disabled"
            continue
        path = Path(str(item.get("imported_path") or IMPORTED_DIR / name))
        if not path.exists():
            item["status"] = "missing"
            item["count"] = 0
            continue
        if not should_parse_file(name):
            item["status"] = "ignored"
            item["count"] = 0
            continue
        try:
            entries, ignored = parse_glossary_txt(path)
        except Exception as e:
            item["status"] = f"parse error: {e}"
            item["count"] = 0
            continue
        for entry in entries:
            merged[entry["source"]] = entry["target"]
        item["count"] = len(entries)
        item["ignored"] = ignored
        item["status"] = "used" if entries else "empty"
        used_files += 1 if entries else 0
        total_raw += len(entries)
        ignored_total += ignored
    compiled = [{"source": s, "target": t} for s, t in sorted(merged.items(), key=lambda kv: (-len(kv[0]), kv[0]))]
    COMPILED_PATH.write_text(json.dumps(compiled, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "files": len(data.get("files", [])),
        "used_files": used_files,
        "raw_entries": total_raw,
        "compiled_entries": len(compiled),
        "duplicates": max(0, total_raw - len(compiled)),
        "ignored_lines": ignored_total,
        "compiled_path": str(COMPILED_PATH),
    }
    data["last_compile"] = {**summary, "updated_at": datetime.now().isoformat(timespec="seconds")}
    write_manifest(data)
    return summary


def load_compiled_glossary():
    if not COMPILED_PATH.exists():
        return []
    try:
        data = json.loads(COMPILED_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            out = []
            for item in data:
                if isinstance(item, dict):
                    s = str(item.get("source") or "").strip()
                    t = str(item.get("target") or "").strip()
                    if s and t:
                        out.append({"source": s, "target": t})
            return out
    except Exception:
        return []
    return []


class LocalTranslationGlossaryDialog(QDialog):
    """Local translator glossary file manager.

    Users manage TXT files only. The program compiles them into a simple source -> target JSON.
    """
    def __init__(self, parent=None, show_cache_path=False):
        super().__init__(parent)
        self._ui_language = str(getattr(parent, "ui_language", "ko") or "ko")
        self._show_cache_path = bool(show_cache_path)
        self.setWindowTitle(self.tr_ui("로컬 번역 단어장"))
        self.resize(780, 520)
        try:
            if parent is not None and hasattr(parent, "settings_dialog_style"):
                self.setStyleSheet(parent.settings_dialog_style())
        except Exception:
            pass

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(self.tr_ui("로컬 번역 단어장"), self)
        title.setObjectName("SettingsDialogTitle")
        layout.addWidget(title)

        desc = QLabel(self.tr_msg(
            "Local Ja-Ko / Local NLLB 같은 로컬 번역기에 쓰는 단순 치환 단어장입니다.\n"
            "여러 TXT 파일을 불러오면 첫 번째 탭 칸을 원문, 두 번째 탭 칸을 치환어로 읽습니다. "
            "PreFilter/PostFilter/SkipLayer 계열은 기본적으로 무시합니다."
        ), self)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.status = QLabel(self)
        self.status.setObjectName("SettingsDescription")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setFixedHeight(128)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        self.btn_load = QPushButton(self.tr_ui("텍스트 불러오기"), self)
        self.btn_remove = QPushButton(self.tr_ui("제거"), self)
        self.btn_refresh = QPushButton(self.tr_ui("갱신"), self)
        self.btn_refresh_all = QPushButton(self.tr_ui("전체 갱신"), self)
        self.btn_open_folder = QPushButton(self.tr_ui("폴더 열기"), self)
        for b in (self.btn_load, self.btn_remove, self.btn_refresh, self.btn_refresh_all, self.btn_open_folder):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.preview_label = QLabel(self.tr_ui("미리보기: 텍스트 파일을 더블클릭하면 해당 파일의 파싱 결과를 표시합니다."), self)
        self.preview_label.setObjectName("SettingsDescription")
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label)

        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(160)
        layout.addWidget(self.preview, 1)

        buttons = QDialogButtonBox(self)
        buttons.addButton(self.tr_ui("닫기"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.btn_load.clicked.connect(self.load_files)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_refresh.clicked.connect(self.refresh_selected)
        self.btn_refresh_all.clicked.connect(self.refresh_all)
        self.btn_open_folder.clicked.connect(self.open_folder)
        self.list_widget.itemDoubleClicked.connect(self.preview_file_item)
        self.reload_view()

    def tr_ui(self, text):
        return translate_ui_text(text, self._ui_language)

    def tr_msg(self, text):
        return translate_ui_dynamic_text(text, self._ui_language)

    def selected_filenames(self):
        return [str(i.data(Qt.ItemDataRole.UserRole) or "") for i in self.list_widget.selectedItems()]


    def display_path(self, path_value):
        if self._show_cache_path:
            return str(path_value)
        return self.tr_ui("경로 숨김")

    def _manifest_item_by_filename(self, filename):
        data = read_manifest()
        for item in data.get("files", []):
            if str(item.get("filename") or "") == str(filename or ""):
                return item
        return None

    def preview_file_item(self, item):
        filename = str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""
        if not filename:
            return
        manifest_item = self._manifest_item_by_filename(filename)
        if not manifest_item:
            self.preview_label.setText(self.tr_ui("미리보기: 파일 정보를 찾지 못했습니다."))
            self.preview.clear()
            return
        path = Path(str(manifest_item.get("imported_path") or IMPORTED_DIR / filename))
        try:
            entries, ignored = parse_glossary_txt(path)
        except Exception as e:
            self.preview_label.setText(f"{self.tr_ui('미리보기')}: {filename} / {self.tr_ui('오류')}: {e}")
            self.preview.clear()
            return
        self.preview_label.setText(
            f"{self.tr_ui('미리보기')}: {filename} / "
            f"{self.tr_ui('단어 수')}: {len(entries):,} / "
            f"{self.tr_ui('무시된 줄')}: {ignored:,}"
        )
        lines = []
        for idx, x in enumerate(entries, start=1):
            lines.append(f"{idx:>5}. {x['source']}  ->  {x['target']}")
        self.preview.setPlainText("\n".join(lines))

    def reload_view(self):
        data = read_manifest()
        try:
            summary = compile_glossary()
            data = read_manifest()
        except Exception:
            summary = data.get("last_compile") or {}
        self.list_widget.clear()
        for item in data.get("files", []):
            name = str(item.get("filename") or "")
            count = int(item.get("count") or 0)
            status = str(item.get("status") or "pending")
            src = str(item.get("source_path") or "")
            label = f"{name}    | {status} | {count:,} terms"
            lw = QListWidgetItem(label)
            lw.setData(Qt.ItemDataRole.UserRole, name)
            lw.setToolTip(src)
            self.list_widget.addItem(lw)
        last = (read_manifest().get("last_compile") or summary or {})
        self.status.setText(
            f"{self.tr_ui('등록 파일')}: {last.get('files', 0)} / "
            f"{self.tr_ui('사용 파일')}: {last.get('used_files', 0)} / "
            f"{self.tr_ui('단어 수')}: {last.get('compiled_entries', 0)} / "
            f"{self.tr_ui('중복')}: {last.get('duplicates', 0)}\n"
            f"{self.tr_ui('캐시')}: {self.display_path(last.get('compiled_path', str(COMPILED_PATH)))}"
        )
        self.preview_label.setText(self.tr_ui("미리보기: 텍스트 파일을 더블클릭하면 해당 파일의 파싱 결과를 표시합니다."))
        self.preview.setPlainText(self.tr_ui("위 목록의 TXT 파일을 더블클릭하면 이 영역에 번호가 붙은 파싱 결과가 표시됩니다."))

    def load_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, self.tr_ui("로컬 번역 단어장 TXT 불러오기"), "", "Text Files (*.txt);;All Files (*)"
        )
        if not paths:
            return
        added = add_text_files(paths)
        self.reload_view()
        QMessageBox.information(self, self.tr_ui("불러오기 완료"), self.tr_ui("선택한 TXT 파일을 로컬 번역 단어장에 등록했습니다."))

    def remove_selected(self):
        names = self.selected_filenames()
        if not names:
            QMessageBox.information(self, self.tr_ui("선택 없음"), self.tr_ui("제거할 TXT 파일을 선택해주세요."))
            return
        if QMessageBox.question(self, self.tr_ui("제거 확인"), self.tr_ui("선택한 TXT 파일을 로컬 단어장 목록에서 제거할까요? 원본 파일은 삭제하지 않습니다.")) != QMessageBox.StandardButton.Yes:
            return
        remove_files(names)
        self.reload_view()

    def refresh_selected(self):
        names = self.selected_filenames()
        if not names:
            QMessageBox.information(self, self.tr_ui("선택 없음"), self.tr_ui("갱신할 TXT 파일을 선택해주세요."))
            return
        refresh_files(names)
        self.reload_view()
        QMessageBox.information(self, self.tr_ui("갱신 완료"), self.tr_ui("선택한 TXT 파일을 다시 읽어 로컬 단어장 캐시를 갱신했습니다."))

    def refresh_all(self):
        refresh_files()
        self.reload_view()
        QMessageBox.information(self, self.tr_ui("전체 갱신 완료"), self.tr_ui("등록된 모든 TXT 파일을 다시 읽어 로컬 단어장 캐시를 갱신했습니다."))

    def open_folder(self):
        ensure_dirs()
        try:
            os.startfile(str(GLOSSARY_ROOT))
        except Exception as e:
            QMessageBox.warning(self, self.tr_ui("폴더 열기 실패"), str(e))

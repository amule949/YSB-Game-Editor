import os
import re
import json
import shutil
import zipfile
import uuid
import copy
import warnings
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, List, Tuple, Any

from ysb.core.cache_utils import get_cache_dir
from ysb.tools.maker_project import (
    copy_game_to_project,
    build_maker_pages,
    load_maker_preview_settings,
    ensure_maker_project_layout,
)

import cv2
import numpy as np


PROJECT_VERSION = 1
PROJECT_FILENAME = "project.json"
MANIFEST_FILENAME = "manifest.json"
WORKSPACE_STATE_FILENAME = ".ysb_workspace_state.json"
PAGE_JOURNAL_DIRNAME = ".ysb_page_journal"
YSB_EXTENSION = ".ysbg"
YSBG_SIGNATURE = b"YSBG-PROJECT\x00\r\n\x1a\n"
SIGNATURE_FILENAME = ".ysbg_signature"



def page_journal_dir(project_dir: str | Path) -> str:
    return os.path.join(str(project_dir), PAGE_JOURNAL_DIRNAME)


def page_journal_path(project_dir: str | Path, page_idx: int) -> str:
    return os.path.join(page_journal_dir(project_dir), f"page_{int(page_idx) + 1:04d}.json")


def _read_page_journal(project_dir: str | Path, page_idx: int) -> dict:
    try:
        p = page_journal_path(project_dir, page_idx)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def apply_page_journals_to_payload(project_dir: str | Path, payload: dict) -> dict:
    """workspace 복구용 page journal을 project.json payload에 겹쳐 적용한다."""
    if not isinstance(payload, dict):
        return payload
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return payload
    journal_root = page_journal_dir(project_dir)
    if not os.path.isdir(journal_root):
        return payload
    for i in range(len(pages)):
        journal = _read_page_journal(project_dir, i)
        if not journal:
            continue
        page_patch = journal.get("page")
        if not isinstance(page_patch, dict):
            page_patch = journal
        if not isinstance(page_patch, dict):
            continue
        page = copy.deepcopy(pages[i]) if isinstance(pages[i], dict) else {}
        for key in ("data", "ocr_analysis_regions", "mask_toggle_enabled", "use_inpainted_as_source"):
            if key in page_patch:
                page[key] = page_patch.get(key)
        pages[i] = page
        try:
            if "current_index" in journal:
                payload["current_index"] = int(journal.get("current_index"))
        except Exception:
            pass
        if isinstance(journal.get("ui_state"), dict):
            old_ui = payload.get("ui_state") if isinstance(payload.get("ui_state"), dict) else {}
            old_ui.update(journal.get("ui_state") or {})
            payload["ui_state"] = old_ui
    return payload


def flush_page_journals_to_project_json(project_dir: str | Path) -> bool:
    """page journal을 project.json에 병합한다. 명시 저장/패키징 때만 쓰는 비교적 무거운 루트."""
    project_file = os.path.join(str(project_dir), PROJECT_FILENAME)
    if not os.path.exists(project_file) or not os.path.isdir(page_journal_dir(project_dir)):
        return False
    try:
        with open(project_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
        payload = apply_page_journals_to_payload(project_dir, payload)
        tmp = project_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, project_file)
        clear_page_journals(project_dir)
        return True
    except Exception:
        return False


def clear_page_journals(project_dir: str | Path, page_indices=None):
    try:
        root = page_journal_dir(project_dir)
        if not os.path.isdir(root):
            return
        if page_indices is None:
            shutil.rmtree(root, ignore_errors=True)
            return
        for raw in list(page_indices or []):
            try:
                p = page_journal_path(project_dir, int(raw))
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        try:
            if os.path.isdir(root) and not any(Path(root).iterdir()):
                os.rmdir(root)
        except Exception:
            pass
    except Exception:
        pass

class PackageProjectCancelled(Exception):
    """Raised when the user cancels YSBG packaging before the final replace."""


def _package_cancel_requested(cancel_checker) -> bool:
    if cancel_checker is None:
        return False
    try:
        return bool(cancel_checker())
    except Exception:
        return False


def _check_package_cancel(cancel_checker):
    if _package_cancel_requested(cancel_checker):
        raise PackageProjectCancelled("YSBG 내보내기가 취소되었습니다.")


def _emit_package_progress(progress_callback, current=None, total=None, detail=None):
    if progress_callback is None:
        return
    try:
        progress_callback(current, total, detail)
    except TypeError:
        try:
            progress_callback(current=current, total=total, detail=detail)
        except Exception:
            pass
    except Exception:
        pass


def _emit_store_progress(progress_callback, current=None, total=None, detail=None):
    if progress_callback is None:
        return
    try:
        progress_callback(current, total, detail)
    except TypeError:
        try:
            progress_callback(current=current, total=total, detail=detail)
        except Exception:
            pass
    except Exception:
        pass


def _save_diag_log(event: str, **fields):
    """Append-only save/package diagnostic log.

    This logger is intentionally independent from the UI audit logger so that
    a crash during final YSBG packaging leaves a breadcrumb right before the
    failing step. Each line is flushed with fsync where possible.
    """
    try:
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            root = os.path.join(str(Path.home()), "AppData", "Local")
        log_dir = os.path.join(root, "YSBGameEditor", "logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "save_package_diag.log")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        parts = [f"[{ts}]", str(event)]
        for k, v in fields.items():
            try:
                sv = repr(v)
            except Exception:
                sv = "<unrepr>"
            parts.append(f"{k}={sv}")
        line = " | ".join(parts) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
    except Exception:
        pass


def imread_unicode(path: str):
    arr = np.fromfile(path, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def imwrite_unicode(path: str, image) -> bool:
    """cv2.imwrite 대신 np.tofile을 사용해 일본어/한글 경로에서도 안전하게 저장한다."""
    try:
        ext = Path(str(path)).suffix or ".png"
        ok, buf = cv2.imencode(ext, image)
        if not ok:
            return False
        buf.tofile(str(path))
        return True
    except Exception:
        return False


def normalize_output_image_format(value: str) -> str:
    v = str(value or "png").strip().lower().lstrip(".")
    if v in ("jpeg", "jpe"):
        v = "jpg"
    if v in ("wep", "wbp"):
        v = "webp"
    return v if v in ("png", "jpg", "webp") else "png"


def output_image_extension(value: str) -> str:
    fmt = normalize_output_image_format(value)
    if fmt == "jpg":
        return ".jpg"
    if fmt == "webp":
        return ".webp"
    return ".png"


def normalize_output_image_quality(value) -> int:
    try:
        q = int(value)
    except Exception:
        q = 95
    return max(1, min(100, q))


def remove_same_stem_image_variants(folder: str, stem: str):
    stem = str(stem or "").strip()
    if not stem:
        return
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        path = os.path.join(folder, stem + ext)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


def save_image_payload_for_output(path: str, payload, image_format: str = "png", quality: int = 95) -> bool:
    """bytes/ndarray 이미지 payload를 지정 출력 형식으로 저장한다.

    bg_clean은 API나 이전 프로젝트에서 PNG bytes로 들어올 수 있으므로,
    단순 write가 아니라 decode 후 선택한 clean 형식으로 재인코딩한다.
    """
    fmt = normalize_output_image_format(image_format)
    q = normalize_output_image_quality(quality)
    img = None
    try:
        if isinstance(payload, (bytes, bytearray)):
            arr = np.frombuffer(payload, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        elif isinstance(payload, np.ndarray):
            img = payload
        elif isinstance(payload, str) and os.path.exists(payload):
            img = imread_unicode(payload)
    except Exception:
        img = None

    if img is None:
        if fmt == "png" and isinstance(payload, (bytes, bytearray)):
            try:
                with open(path, "wb") as f:
                    f.write(payload)
                return True
            except Exception:
                return False
        return False

    try:
        ext = output_image_extension(fmt)
        encode_img = img
        params = []
        if fmt == "jpg":
            # JPEG에는 alpha가 없으므로 흰 배경으로 합성한다.
            try:
                if len(encode_img.shape) == 3 and encode_img.shape[2] == 4:
                    bgr = encode_img[:, :, :3].astype(np.float32)
                    alpha = (encode_img[:, :, 3:4].astype(np.float32) / 255.0)
                    white = np.full_like(bgr, 255, dtype=np.float32)
                    encode_img = (bgr * alpha + white * (1.0 - alpha)).astype(np.uint8)
            except Exception:
                pass
            params = [int(cv2.IMWRITE_JPEG_QUALITY), q]
        elif fmt == "webp":
            params = [int(cv2.IMWRITE_WEBP_QUALITY), q]
        else:
            params = [int(cv2.IMWRITE_PNG_COMPRESSION), 9]
        ok, buf = cv2.imencode(ext, encode_img, params)
        if not ok:
            return False
        buf.tofile(str(path))
        return True
    except Exception:
        return False


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)



def safe_image_file_stem(name: str, fallback: str = "image") -> str:
    """Windows 파일명으로 쓸 수 있게 최소 보정하되, 원본 이름은 최대한 보존한다."""
    s = str(name or "").strip()
    for ch in '<>:"/\\|?*':
        s = s.replace(ch, "_")
    s = s.rstrip(" .")
    return s or fallback


def unique_image_copy_name(src_path: Path, images_dir: str, used_stems: set[str] | None = None) -> str:
    """원본 파일명 기반으로 복사 파일명을 만든다.

    확장자가 달라도 표시명 stem이 겹치면 name(1), name(2) 형식으로 회피한다.
    예: 0007.jpg가 있으면 0007.png는 0007(1).png로 저장.
    """
    used_stems = used_stems if used_stems is not None else set()
    ext = src_path.suffix.lower() or ".png"
    base = safe_image_file_stem(src_path.stem, fallback="image")
    existing_stems = set(used_stems)
    try:
        for p in Path(images_dir).iterdir():
            if p.is_file():
                existing_stems.add(p.stem.lower())
    except Exception:
        pass

    def candidate_name(n: int | None):
        stem = base if n is None else f"{base}({n})"
        return stem, f"{stem}{ext}"

    stem, name = candidate_name(None)
    if stem.lower() not in existing_stems and not os.path.exists(os.path.join(images_dir, name)):
        used_stems.add(stem.lower())
        return name

    for n in range(1, 10000):
        stem, name = candidate_name(n)
        if stem.lower() not in existing_stems and not os.path.exists(os.path.join(images_dir, name)):
            used_stems.add(stem.lower())
            return name

    fallback_stem = f"{base}({uuid.uuid4().hex[:8]})"
    used_stems.add(fallback_stem.lower())
    return f"{fallback_stem}{ext}"


def relpath(path: str, root: str) -> str:
    return os.path.relpath(path, root).replace("\\", "/")


def abs_from_rel(root: str, rel: str) -> str:
    rel_text = str(rel or "")
    # 구버전/버그 프로젝트에 Windows 절대 경로가 page entry로 남아 있을 수 있다.
    # 이 값은 project_dir에 붙이면 안 되고, 그대로 외부 파일 경로로 취급한다.
    try:
        if os.path.isabs(rel_text) or PureWindowsPath(rel_text).is_absolute() or PurePosixPath(rel_text).is_absolute():
            return rel_text
    except Exception:
        pass
    return os.path.join(root, rel_text.replace("/", os.sep))


def json_safe(value: Any):
    """numpy 값이 섞여도 project.json에 들어갈 수 있게 변환."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


class ProjectStore:
    """
    프로젝트 폴더 저장/불러오기 담당.

    폴더 구조:
    project_dir/
      project.json
      manifest.json
      images/
      masks/text_mask/
      masks/paint_mask/
      clean/
      working_source/
      final_paint/
      final_paint_above/
      scripts/
      Result/
      Txt/
    """

    def __init__(self, project_dir: str | None = None):
        self.project_dir = project_dir
        self.ui_state = {}

    @property
    def project_file(self) -> str | None:
        if not self.project_dir:
            return None
        return os.path.join(self.project_dir, PROJECT_FILENAME)

    def init_dirs(self):
        if not self.project_dir:
            raise ValueError("project_dir이 비어 있습니다.")
        ensure_dir(self.project_dir)
        ensure_dir(os.path.join(self.project_dir, "images"))
        ensure_dir(os.path.join(self.project_dir, "masks"))
        ensure_dir(os.path.join(self.project_dir, "masks", "text_mask"))
        ensure_dir(os.path.join(self.project_dir, "masks", "paint_mask"))
        ensure_dir(os.path.join(self.project_dir, "masks", "text_mask_off"))
        ensure_dir(os.path.join(self.project_dir, "masks", "paint_mask_off"))
        ensure_dir(os.path.join(self.project_dir, "clean"))
        ensure_dir(os.path.join(self.project_dir, "working_source"))
        ensure_dir(os.path.join(self.project_dir, "final_paint"))
        ensure_dir(os.path.join(self.project_dir, "final_paint_above"))
        ensure_dir(os.path.join(self.project_dir, "scripts"))
        ensure_dir(os.path.join(self.project_dir, "result"))
        ensure_dir(os.path.join(self.project_dir, "txt"))

    def create_from_images(self, project_dir: str, source_paths: List[str]) -> Tuple[List[str], Dict[int, dict]]:
        self.project_dir = project_dir
        self.init_dirs()

        paths: List[str] = []
        data: Dict[int, dict] = {}

        images_dir = os.path.join(self.project_dir, "images")
        used_stems: set[str] = set()
        for i, src in enumerate(source_paths):
            src_path = Path(src)
            dst_name = unique_image_copy_name(src_path, images_dir, used_stems)
            dst = os.path.join(images_dir, dst_name)
            shutil.copy2(src, dst)

            paths.append(dst)
            data[i] = {
                "ori": None,
                "data": [],
                "mask_merge": None,
                "mask_inpaint": None,
                "mask_merge_off": None,
                "mask_inpaint_off": None,
                "mask_merge_path": None,
                "mask_inpaint_path": None,
                "mask_merge_off_path": None,
                "mask_inpaint_off_path": None,
                "mask_toggle_enabled": False,
                "use_inpainted_as_source": False,
                "bg_clean": None,
                "working_source": None,
                "final_paint": None,
                "final_paint_above": None,
                "original_name": dst_name,
                "ocr_analysis_regions": [],
            }

        self.ui_state = {"current_mode": 0, "view_states": {}}
        self.save(paths, data, current_index=0)
        return paths, data

    def create_from_maker_game(self, project_dir: str, source_game_dir: str, progress_callback=None) -> Tuple[List[str], Dict[int, dict], dict]:
        """Create YSB pages from a RPG Maker MV/MZ game/project folder.

        Conceptually this replaces image import for the Maker editor branch:
        the whole game folder is cloned into the project, then MapXXX.json files
        become page tabs and extracted event texts become right-panel text rows.
        """
        self.project_dir = project_dir
        self.init_dirs()
        _emit_store_progress(progress_callback, 0, 0, "작업 폴더 구조를 준비하는 중...")
        ensure_maker_project_layout(self.project_dir)
        game_clone, engine_info = copy_game_to_project(source_game_dir, self.project_dir, progress_callback=progress_callback)
        paths, data, summary = build_maker_pages(self.project_dir, game_clone, engine_info, progress_callback=progress_callback)
        engine_kind = "rpg_maker_" + str((summary.get("engine") or {}).get("engine") or "mv_mz")
        self.ui_state = {
            "current_mode": 0,
            "view_states": {},
            "show_final_text": True,
            "project_kind": engine_kind,
            "maker_import": summary,
            "maker_preview_settings": load_maker_preview_settings(self.project_dir),
        }
        _emit_store_progress(progress_callback, 0, 0, "프로젝트 파일을 저장하는 중...")
        self.save(paths, data, current_index=0)
        _emit_store_progress(progress_callback, 1, 1, "프로젝트 가져오기 완료")
        return paths, data, summary


    def project_uuid(self) -> str:
        if not self.project_dir:
            return uuid.uuid4().hex
        manifest_path = os.path.join(self.project_dir, MANIFEST_FILENAME)
        try:
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("project_uuid"):
                    return str(data["project_uuid"])
        except Exception:
            pass
        return uuid.uuid4().hex

    def write_manifest(self, package_source: str | None = None, project_name: str | None = None, project_uuid: str | None = None):
        if not self.project_dir:
            return
        manifest_path = os.path.join(self.project_dir, MANIFEST_FILENAME)
        old = {}
        try:
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    old = loaded
        except Exception:
            old = {}
        now = datetime.now().isoformat(timespec="seconds")

        folder_name = clean_workspace_name(Path(self.project_dir).name)
        old_name = str(old.get("project_name") or "")
        if project_name:
            final_name = clean_workspace_name(project_name)
        elif old_name.startswith("unsaved_") or not old_name:
            final_name = folder_name
        else:
            final_name = clean_workspace_name(old_name)

        final_uuid = str(project_uuid or old.get("project_uuid") or uuid.uuid4().hex)
        payload = {
            "format": "YSBG_PROJECT",
            "signature": "YSBG-PROJECT",
            "format_version": "1.0",
            "project_uuid": final_uuid,
            "project_name": final_name,
            "project_version": PROJECT_VERSION,
            "created_at": old.get("created_at") or now,
            "last_saved_at": now,
        }
        if package_source:
            payload["package_source"] = package_source
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def save(self, paths: List[str], data: Dict[int, dict], current_index: int = 0):
        if not self.project_dir:
            return

        self.init_dirs()

        old_pages = []
        old_page_images: Dict[int, str] = {}
        try:
            if self.project_file and os.path.exists(self.project_file):
                with open(self.project_file, "r", encoding="utf-8") as f:
                    old_payload_for_images = json.load(f)
                old_pages = old_payload_for_images.get("pages", []) if isinstance(old_payload_for_images, dict) else []
                if not isinstance(old_pages, list):
                    old_pages = []
                for _i, _page in enumerate(old_pages):
                    if isinstance(_page, dict) and _page.get("image"):
                        old_page_images[_i] = os.path.abspath(abs_from_rel(self.project_dir, _page.get("image")))
        except Exception:
            old_pages = []
            old_page_images = {}

        incremental_allowed = bool(getattr(self, "_save_incremental_allowed", False))
        structure_dirty = bool(getattr(self, "_save_structure_dirty", True))
        dirty_pages_raw = getattr(self, "_save_dirty_pages", None)
        dirty_pages = set()
        if dirty_pages_raw is not None:
            try:
                dirty_pages = {int(x) for x in dirty_pages_raw}
            except Exception:
                dirty_pages = set()
        can_reuse_old_pages = (
            incremental_allowed
            and not structure_dirty
            and dirty_pages_raw is not None
            and len(old_pages) == len(paths)
        )

        save_yield_callback = getattr(self, "_save_yield_callback", None)

        def _yield_save_progress(phase: str, current: int = 0, total: int | None = None):
            if not callable(save_yield_callback):
                return
            try:
                save_yield_callback(str(phase or "store_save"), int(current or 0), int(total if total is not None else len(paths)))
            except Exception:
                pass

        _yield_save_progress("store_save_prepare", 0, len(paths))

        pages = []
        # 저장/작업 캐시 반영은 "새 이미지 추가"가 아니라 현재 페이지 목록을 저장하는 작업이다.
        # 따라서 폴더에 같은 이름이 있다는 이유만으로 (1) 파일을 새로 만들면 안 된다.
        # 현재 저장되는 페이지 목록 안에서만 이름 충돌을 피하고, 기존 파일은 덮어쓰기/재사용한다.
        used_save_stems: set[str] = set()
        for i, image_path in enumerate(paths):
            curr = data.get(i, {})

            # Incremental save: if the page is clean and the project structure did
            # not change, reuse the previous project.json entry verbatim. This
            # avoids image copying, mask np.save, PNG writes and per-page path
            # normalization for hundreds of untouched pages.
            if can_reuse_old_pages and i not in dirty_pages:
                old_page = old_pages[i] if i < len(old_pages) else None
                try:
                    old_image_abs = old_page_images.get(i)
                    curr_image_abs = os.path.abspath(image_path)
                    same_page_file = bool(old_image_abs and curr_image_abs and os.path.abspath(old_image_abs) == curr_image_abs)
                except Exception:
                    same_page_file = False
                # 페이지 순서 변경/삽입/삭제가 mark_structure_dirty를 타지 못했더라도
                # 현재 index의 기준 이미지가 달라졌다면 old page entry를 재사용하면 안 된다.
                if isinstance(old_page, dict) and same_page_file:
                    pages.append(copy.deepcopy(old_page))
                    _yield_save_progress("store_save_reuse_page", i + 1, len(paths))
                    continue

            images_dir = os.path.join(self.project_dir, "images")
            ensure_dir(images_dir)
            abs_image = os.path.abspath(image_path)
            project_abs = os.path.abspath(self.project_dir)

            ext = Path(image_path).suffix.lower() or ".png"
            original_hint = curr.get("original_name") or os.path.basename(image_path)
            hint = Path(str(original_hint))
            base = safe_image_file_stem(hint.stem or Path(image_path).stem or f"page{i + 1:03d}", fallback=f"page{i + 1:03d}")
            if hint.suffix:
                # 실제 인코딩 변환은 하지 않으므로 확장자는 image_path 기준을 우선한다.
                ext = Path(image_path).suffix.lower() or hint.suffix.lower() or ".png"

            target_stem = base
            if target_stem.lower() in used_save_stems:
                for n in range(1, 10000):
                    candidate_stem = f"{base}({n})"
                    if candidate_stem.lower() not in used_save_stems:
                        target_stem = candidate_stem
                        break
            used_save_stems.add(target_stem.lower())
            desired_dst = os.path.join(images_dir, f"{target_stem}{ext}")

            # 프로젝트 밖 이미지 또는 프로젝트 내부라도 원하는 기준 이름과 다른 경우만 복사/이동한다.
            # save()는 저장 작업이므로 기존 desired_dst가 있으면 충돌로 보지 않고 덮어쓴다.
            if os.path.abspath(image_path) != os.path.abspath(desired_dst):
                try:
                    if os.path.exists(image_path):
                        shutil.copy2(image_path, desired_dst)
                    else:
                        desired_dst = image_path
                except Exception:
                    # 기존 저장 동작과 동일하게 상위에서 파일 없음/쓰기 실패를 알 수 있게 다시 던진다.
                    raise
                image_path = desired_dst
                paths[i] = desired_dst
            else:
                image_path = desired_dst
                paths[i] = desired_dst

            curr["original_name"] = os.path.basename(image_path)

            page = {
                "image": relpath(image_path, self.project_dir),
                "original_name": curr.get("original_name", os.path.basename(image_path)),
                "data": json_safe(curr.get("data", [])),
                "ocr_analysis_regions": json_safe(curr.get("ocr_analysis_regions", [])),
            }
            # YSB Maker branch: keep page-level RPG Maker map metadata in project.json.
            if isinstance(curr.get("maker_page"), dict):
                page["maker_page"] = json_safe(curr.get("maker_page"))
            if isinstance(curr.get("maker_preview_settings"), dict):
                page["maker_preview_settings"] = json_safe(curr.get("maker_preview_settings"))

            def _existing_mask_path(path_value, file_key: str):
                if not path_value:
                    return None
                p = str(path_value)
                try:
                    if not (os.path.isabs(p) or PureWindowsPath(p).is_absolute() or PurePosixPath(p).is_absolute()):
                        p = abs_from_rel(self.project_dir, p)
                except Exception:
                    p = abs_from_rel(self.project_dir, p)
                if not os.path.exists(p):
                    # 구버전/중복 파일 정리 뒤 path가 mask_merge_0001(3).npy 등을 가리키면
                    # canonical 이름(mask_merge_0001.npy)으로 폴백한다.
                    if file_key in MASK_PAGE_KEYS:
                        canonical = _mask_canonical_path(self.project_dir, file_key, i)
                        return canonical if canonical and os.path.exists(canonical) else None
                    return None
                # Save As처럼 새 project_dir로 분기하는 저장에서는 curr 내부의 mask path가
                # 기존 작업 폴더 A를 가리킬 수 있다. 이때 relpath(old, new)를 project.json에
                # 남기지 말고 파일을 새 작업 폴더 B 안으로 복사해 내부 상대경로로 고정한다.
                try:
                    if not _is_path_inside(p, self.project_dir):
                        fixed_rel = _copy_external_page_file_into_project(self.project_dir, file_key, p, i)
                        if fixed_rel:
                            fixed_abs = abs_from_rel(self.project_dir, fixed_rel)
                            return fixed_abs if os.path.exists(fixed_abs) else None
                except Exception:
                    pass
                if file_key in MASK_PAGE_KEYS:
                    return _canonicalize_mask_file(self.project_dir, file_key, p, i)
                return p if os.path.exists(p) else None

            mask_merge = curr.get("mask_merge")
            mask_path = _existing_mask_path(curr.get("mask_merge_path"), "mask_merge")
            if mask_merge is not None and (bool(curr.get("mask_merge_dirty", False)) or not mask_path):
                mask_path = _mask_canonical_path(self.project_dir, "mask_merge", i)
                _atomic_save_mask_array(mask_path, mask_merge)
                curr["mask_merge_path"] = mask_path
                curr["mask_merge_dirty"] = False
                page["mask_merge"] = relpath(mask_path, self.project_dir)
            elif mask_path:
                curr["mask_merge_path"] = mask_path
                page["mask_merge"] = relpath(mask_path, self.project_dir)

            mask_inpaint = curr.get("mask_inpaint")
            mask_path = _existing_mask_path(curr.get("mask_inpaint_path"), "mask_inpaint")
            if mask_inpaint is not None and (bool(curr.get("mask_inpaint_dirty", False)) or not mask_path):
                mask_path = _mask_canonical_path(self.project_dir, "mask_inpaint", i)
                _atomic_save_mask_array(mask_path, mask_inpaint)
                curr["mask_inpaint_path"] = mask_path
                curr["mask_inpaint_dirty"] = False
                page["mask_inpaint"] = relpath(mask_path, self.project_dir)
            elif mask_path:
                curr["mask_inpaint_path"] = mask_path
                page["mask_inpaint"] = relpath(mask_path, self.project_dir)

            mask_merge_off = curr.get("mask_merge_off")
            mask_path = _existing_mask_path(curr.get("mask_merge_off_path"), "mask_merge_off")
            if mask_merge_off is not None and (bool(curr.get("mask_merge_off_dirty", False)) or not mask_path):
                mask_path = _mask_canonical_path(self.project_dir, "mask_merge_off", i)
                _atomic_save_mask_array(mask_path, mask_merge_off)
                curr["mask_merge_off_path"] = mask_path
                curr["mask_merge_off_dirty"] = False
                page["mask_merge_off"] = relpath(mask_path, self.project_dir)
            elif mask_path:
                curr["mask_merge_off_path"] = mask_path
                page["mask_merge_off"] = relpath(mask_path, self.project_dir)

            mask_inpaint_off = curr.get("mask_inpaint_off")
            mask_path = _existing_mask_path(curr.get("mask_inpaint_off_path"), "mask_inpaint_off")
            if mask_inpaint_off is not None and (bool(curr.get("mask_inpaint_off_dirty", False)) or not mask_path):
                mask_path = _mask_canonical_path(self.project_dir, "mask_inpaint_off", i)
                _atomic_save_mask_array(mask_path, mask_inpaint_off)
                curr["mask_inpaint_off_path"] = mask_path
                curr["mask_inpaint_off_dirty"] = False
                page["mask_inpaint_off"] = relpath(mask_path, self.project_dir)
            elif mask_path:
                curr["mask_inpaint_off_path"] = mask_path
                page["mask_inpaint_off"] = relpath(mask_path, self.project_dir)

            page["mask_toggle_enabled"] = bool(curr.get("mask_toggle_enabled", False))
            page["use_inpainted_as_source"] = bool(curr.get("use_inpainted_as_source", False))

            working_source = curr.get("working_source")
            if working_source is not None:
                source_path = os.path.join(self.project_dir, "working_source", f"working_source_{i + 1:04d}.png")
                if isinstance(working_source, (bytes, bytearray)):
                    with open(source_path, "wb") as f:
                        f.write(working_source)
                    page["working_source"] = relpath(source_path, self.project_dir)
                elif isinstance(working_source, np.ndarray):
                    imwrite_unicode(source_path, working_source)
                    page["working_source"] = relpath(source_path, self.project_dir)

            bg_clean = curr.get("bg_clean")
            if bg_clean is not None:
                clean_fmt = normalize_output_image_format(getattr(self, "clean_image_format", "png"))
                clean_quality = normalize_output_image_quality(getattr(self, "clean_image_quality", 95))
                original_name = ""
                try:
                    original_name = str(curr.get("original_name") or "").strip()
                except Exception:
                    original_name = ""
                if not original_name:
                    try:
                        original_name = os.path.basename(str(image_path or f"page{i + 1:03d}.png"))
                    except Exception:
                        original_name = f"page{i + 1:03d}.png"
                original_stem = safe_image_file_stem(Path(str(original_name)).stem, fallback=f"page{i + 1:03d}")
                clean_stem = original_stem if original_stem.lower().startswith("clean_") else f"clean_{original_stem}"
                clean_path = os.path.join(self.project_dir, "clean", clean_stem + output_image_extension(clean_fmt))

                # 형식/이름 규칙이 바뀌어 다시 저장되면 같은 클린본의 옛 확장자는 중복으로 남기지 않는다.
                remove_same_stem_image_variants(os.path.join(self.project_dir, "clean"), clean_stem)
                # 직전 버전에서 생긴 접두사 없는 원본명 클린본도 정리한다.
                remove_same_stem_image_variants(os.path.join(self.project_dir, "clean"), original_stem)
                # 더 오래된 page index 기반 clean_0001.png 계열은 원본 stem과 다를 때만 정리한다.
                legacy_stem = f"clean_{i + 1:04d}"
                if legacy_stem != clean_stem:
                    remove_same_stem_image_variants(os.path.join(self.project_dir, "clean"), legacy_stem)

                if save_image_payload_for_output(clean_path, bg_clean, clean_fmt, clean_quality):
                    curr["clean_path"] = clean_path
                    page["clean"] = relpath(clean_path, self.project_dir)

            final_paint = curr.get("final_paint")
            if final_paint is not None:
                paint_path = os.path.join(self.project_dir, "final_paint", f"final_paint_{i + 1:04d}.png")
                if isinstance(final_paint, (bytes, bytearray)):
                    with open(paint_path, "wb") as f:
                        f.write(final_paint)
                    page["final_paint"] = relpath(paint_path, self.project_dir)
                elif isinstance(final_paint, np.ndarray):
                    imwrite_unicode(paint_path, final_paint)
                    page["final_paint"] = relpath(paint_path, self.project_dir)

            final_paint_above = curr.get("final_paint_above")
            if final_paint_above is not None:
                paint_path = os.path.join(self.project_dir, "final_paint_above", f"final_paint_above_{i + 1:04d}.png")
                if isinstance(final_paint_above, (bytes, bytearray)):
                    with open(paint_path, "wb") as f:
                        f.write(final_paint_above)
                    page["final_paint_above"] = relpath(paint_path, self.project_dir)
                elif isinstance(final_paint_above, np.ndarray):
                    imwrite_unicode(paint_path, final_paint_above)
                    page["final_paint_above"] = relpath(paint_path, self.project_dir)

            # Lazy-load 상태에서 실제 payload(bytes/ndarray)를 아직 읽지 않았더라도,
            # 기존 파일 경로 참조는 project.json에 유지한다.
            for _page_key, _path_key in (
                ("working_source", "working_source_path"),
                ("clean", "clean_path"),
                ("final_paint", "final_paint_path"),
                ("final_paint_above", "final_paint_above_path"),
            ):
                if _page_key not in page:
                    _asset_path = curr.get(_path_key)
                    if _asset_path and os.path.exists(_asset_path):
                        page[_page_key] = relpath(_asset_path, self.project_dir)

            pages.append(page)
            _yield_save_progress("store_save_page_done", i + 1, len(paths))

        _yield_save_progress("store_save_pages_done", len(paths), len(paths))
        # 자동저장/작업 캐시/일괄 작업 후 저장에서는 전체 masks 폴더 스윕을 돌리지 않는다.
        # 마스크 파일은 저장 시 canonical 이름으로 원자 교체하고, 중복 파일 전체 정리는
        # 명시 저장의 YSBG 패키징 직전(_sanitize_project_json_file/package_project)에서만 조용히 수행한다.
        if bool(getattr(self, "_cleanup_duplicate_masks_on_save", False)):
            cleanup_duplicate_mask_files(self.project_dir)
            pages = normalize_mask_page_refs(self.project_dir, pages)

        # 같은 페이지의 원본 이미지명이 바뀌었을 때, 예전 파일이 images 폴더에 남으면
        # '구버전 이름'과 '새 이름'이 같이 보인다. 저장 완료 전 안전하게 정리한다.
        # 단, 현재 pages가 참조하는 파일이거나 images 폴더 밖 파일은 삭제하지 않는다.
        try:
            current_image_abs = set()
            for _page in pages:
                if isinstance(_page, dict) and _page.get("image"):
                    current_image_abs.add(os.path.abspath(abs_from_rel(self.project_dir, _page.get("image"))))
            images_dir_abs = os.path.abspath(os.path.join(self.project_dir, "images"))
            for _i, _old_abs in list(old_page_images.items()):
                if not _old_abs:
                    continue
                if _old_abs in current_image_abs:
                    continue
                try:
                    if os.path.commonpath([images_dir_abs, os.path.abspath(_old_abs)]) != images_dir_abs:
                        continue
                except Exception:
                    continue
                if os.path.exists(_old_abs):
                    try:
                        os.remove(_old_abs)
                    except Exception:
                        pass
        except Exception:
            pass

        _yield_save_progress("store_save_cleanup_done", len(paths), len(paths))

        ui_state = getattr(self, "ui_state", None)
        if ui_state is None:
            ui_state = {}
        if not isinstance(ui_state, dict):
            ui_state = {}
        if not ui_state:
            try:
                if self.project_file and os.path.exists(self.project_file):
                    with open(self.project_file, "r", encoding="utf-8") as f:
                        old_payload = json.load(f)
                    if isinstance(old_payload, dict) and isinstance(old_payload.get("ui_state"), dict):
                        ui_state = old_payload.get("ui_state") or {}
            except Exception:
                ui_state = {}

        # Save As/작업 폴더 분기 중 예전 작업 폴더의 절대 경로가 page entry에 남으면
        # .ysbg 내부 zip member가 C:/Users/... 형태가 되어 다음 열기 때 안전 검사에서 막힌다.
        # project.json에는 항상 현재 project_dir 기준의 패키지 내부 상대 경로만 남긴다.
        pages = _sanitize_page_file_refs_for_project(self.project_dir, pages)

        payload = {
            "version": PROJECT_VERSION,
            "current_index": int(current_index),
            "pages": pages,
            "ui_state": json_safe(ui_state),
        }
        payload = apply_page_journals_to_payload(self.project_dir, payload)

        _yield_save_progress("store_save_write_manifest_begin", len(paths), len(paths))
        self.write_manifest()
        _yield_save_progress("store_save_write_project_json_begin", len(paths), len(paths))
        with open(self.project_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        clear_page_journals(self.project_dir)
        _yield_save_progress("store_save_done", len(paths), len(paths))

    def save_page_data_delta(self, data: Dict[int, dict], page_indices, current_index: int = 0):
        """텍스트/번역문/좌표 복구용 page journal 저장.

        project.json 전체를 다시 쓰지 않고 workspace/.ysb_page_journal/page_0001.json 같은
        작은 저널 파일만 쓴다. 복구/열기/명시 저장 시점에 project.json 위로 겹쳐 적용한다.
        """
        if not self.project_dir:
            return False
        try:
            indices = sorted({int(i) for i in (page_indices or []) if int(i) >= 0})
        except Exception:
            indices = []
        if not indices:
            return False

        root = page_journal_dir(self.project_dir)
        os.makedirs(root, exist_ok=True)
        ui_state = getattr(self, "ui_state", None)
        changed = False
        for i in indices:
            curr = data.get(i, {}) if isinstance(data, dict) else {}
            if not isinstance(curr, dict):
                continue
            page_patch = {
                "data": json_safe(curr.get("data", [])),
                "ocr_analysis_regions": json_safe(curr.get("ocr_analysis_regions", [])),
                "mask_toggle_enabled": bool(curr.get("mask_toggle_enabled", False)),
                "use_inpainted_as_source": bool(curr.get("use_inpainted_as_source", False)),
            }
            payload = {
                "version": 1,
                "page_index": int(i),
                "current_index": int(current_index),
                "page": page_patch,
                "updated_at": datetime.now().timestamp(),
            }
            if isinstance(ui_state, dict):
                payload["ui_state"] = json_safe(ui_state or {})
            out_path = page_journal_path(self.project_dir, i)
            tmp_path = out_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, out_path)
            changed = True
        return changed
    def save_pages_delta(self, paths: List[str], data: Dict[int, dict], page_indices, current_index: int = 0):
        """작업 캐시 전용 dirty-page 저장.

        ProjectStore.save()는 전체 paths를 순회하며 clean page 재사용을 하더라도 함수 진입 자체가
        프로젝트 내보내기 단위다. 단일 분석/페이지 편집 후 work cache에 저장할 때는 dirty page만
        디스크에 반영하고 project.json의 해당 page entry만 교체한다.
        """
        if not self.project_dir:
            return False
        self.init_dirs()

        try:
            indices = sorted({int(i) for i in (page_indices or []) if 0 <= int(i) < len(paths)})
        except Exception:
            indices = []
        if not indices:
            return False

        payload = {}
        old_pages = []
        if self.project_file and os.path.exists(self.project_file):
            try:
                with open(self.project_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    payload = loaded
                    old_pages = loaded.get("pages", []) if isinstance(loaded.get("pages"), list) else []
            except Exception:
                payload = {}
                old_pages = []

        if not isinstance(payload, dict):
            payload = {}
        if not isinstance(old_pages, list):
            old_pages = []

        pages = [copy.deepcopy(p) if isinstance(p, dict) else {} for p in old_pages]
        while len(pages) < len(paths):
            pages.append({})

        used_save_stems: set[str] = set()
        for _page in pages:
            try:
                if isinstance(_page, dict) and _page.get("image"):
                    used_save_stems.add(Path(str(_page.get("image"))).stem.lower())
            except Exception:
                pass

        def _existing_mask_path(path_value, file_key: str, page_idx: int):
            if not path_value:
                return None
            p = str(path_value)
            try:
                if not (os.path.isabs(p) or PureWindowsPath(p).is_absolute() or PurePosixPath(p).is_absolute()):
                    p = abs_from_rel(self.project_dir, p)
            except Exception:
                p = abs_from_rel(self.project_dir, p)
            if not os.path.exists(p):
                if file_key in MASK_PAGE_KEYS:
                    canonical = _mask_canonical_path(self.project_dir, file_key, page_idx)
                    return canonical if canonical and os.path.exists(canonical) else None
                return None
            try:
                if not _is_path_inside(p, self.project_dir):
                    fixed_rel = _copy_external_page_file_into_project(self.project_dir, file_key, p, page_idx)
                    if fixed_rel:
                        fixed_abs = abs_from_rel(self.project_dir, fixed_rel)
                        return fixed_abs if os.path.exists(fixed_abs) else None
            except Exception:
                pass
            if file_key in MASK_PAGE_KEYS:
                return _canonicalize_mask_file(self.project_dir, file_key, p, page_idx)
            return p if os.path.exists(p) else None

        for i in indices:
            curr = data.get(i, {})
            if not isinstance(curr, dict):
                curr = {}

            image_path = paths[i]
            images_dir = os.path.join(self.project_dir, "images")
            ensure_dir(images_dir)
            ext = Path(str(image_path)).suffix.lower() or ".png"
            original_hint = curr.get("original_name") or os.path.basename(str(image_path))
            hint = Path(str(original_hint))
            base = safe_image_file_stem(hint.stem or Path(str(image_path)).stem or f"page{i + 1:03d}", fallback=f"page{i + 1:03d}")
            if hint.suffix:
                ext = Path(str(image_path)).suffix.lower() or hint.suffix.lower() or ".png"

            target_stem = base
            old_page = pages[i] if i < len(pages) else {}
            try:
                old_stem = Path(str(old_page.get("image") or "")).stem.lower() if isinstance(old_page, dict) else ""
            except Exception:
                old_stem = ""
            if target_stem.lower() in used_save_stems and target_stem.lower() != old_stem:
                for n in range(1, 10000):
                    candidate_stem = f"{base}({n})"
                    if candidate_stem.lower() not in used_save_stems:
                        target_stem = candidate_stem
                        break
            used_save_stems.add(target_stem.lower())
            desired_dst = os.path.join(images_dir, f"{target_stem}{ext}")

            try:
                if os.path.abspath(str(image_path)) != os.path.abspath(desired_dst):
                    if os.path.exists(str(image_path)):
                        shutil.copy2(str(image_path), desired_dst)
                        image_path = desired_dst
                        paths[i] = desired_dst
                else:
                    image_path = desired_dst
                    paths[i] = desired_dst
            except Exception:
                raise

            curr["original_name"] = os.path.basename(str(image_path))
            page = {
                "image": relpath(str(image_path), self.project_dir),
                "original_name": curr.get("original_name", os.path.basename(str(image_path))),
                "data": json_safe(curr.get("data", [])),
                "ocr_analysis_regions": json_safe(curr.get("ocr_analysis_regions", [])),
            }

            for file_key in ("mask_merge", "mask_inpaint", "mask_merge_off", "mask_inpaint_off"):
                arr_value = curr.get(file_key)
                path_key = f"{file_key}_path"
                dirty_key = f"{file_key}_dirty"
                mask_path = _existing_mask_path(curr.get(path_key), file_key, i)
                if arr_value is not None and (bool(curr.get(dirty_key, False)) or not mask_path):
                    mask_path = _mask_canonical_path(self.project_dir, file_key, i)
                    _atomic_save_mask_array(mask_path, arr_value)
                    curr[path_key] = mask_path
                    curr[dirty_key] = False
                    page[file_key] = relpath(mask_path, self.project_dir)
                elif mask_path:
                    curr[path_key] = mask_path
                    page[file_key] = relpath(mask_path, self.project_dir)

            page["mask_toggle_enabled"] = bool(curr.get("mask_toggle_enabled", False))
            page["use_inpainted_as_source"] = bool(curr.get("use_inpainted_as_source", False))

            working_source = curr.get("working_source")
            if working_source is not None:
                ensure_dir(os.path.join(self.project_dir, "working_source"))
                source_path = os.path.join(self.project_dir, "working_source", f"working_source_{i + 1:04d}.png")
                if isinstance(working_source, (bytes, bytearray)):
                    with open(source_path, "wb") as f:
                        f.write(working_source)
                    page["working_source"] = relpath(source_path, self.project_dir)
                elif isinstance(working_source, np.ndarray):
                    imwrite_unicode(source_path, working_source)
                    page["working_source"] = relpath(source_path, self.project_dir)

            bg_clean = curr.get("bg_clean")
            if bg_clean is not None:
                ensure_dir(os.path.join(self.project_dir, "clean"))
                clean_fmt = normalize_output_image_format(getattr(self, "clean_image_format", "png"))
                clean_quality = normalize_output_image_quality(getattr(self, "clean_image_quality", 95))
                original_name = str(curr.get("original_name") or "").strip() or os.path.basename(str(image_path or f"page{i + 1:03d}.png"))
                original_stem = safe_image_file_stem(Path(str(original_name)).stem, fallback=f"page{i + 1:03d}")
                clean_stem = original_stem if original_stem.lower().startswith("clean_") else f"clean_{original_stem}"
                clean_path = os.path.join(self.project_dir, "clean", clean_stem + output_image_extension(clean_fmt))
                remove_same_stem_image_variants(os.path.join(self.project_dir, "clean"), clean_stem)
                remove_same_stem_image_variants(os.path.join(self.project_dir, "clean"), original_stem)
                legacy_stem = f"clean_{i + 1:04d}"
                if legacy_stem != clean_stem:
                    remove_same_stem_image_variants(os.path.join(self.project_dir, "clean"), legacy_stem)
                if save_image_payload_for_output(clean_path, bg_clean, clean_fmt, clean_quality):
                    curr["clean_path"] = clean_path
                    page["clean"] = relpath(clean_path, self.project_dir)
            else:
                existing_clean = curr.get("clean_path")
                if existing_clean and os.path.exists(existing_clean):
                    page["clean"] = relpath(existing_clean, self.project_dir)
                else:
                    try:
                        old_clean = old_page.get("clean") if isinstance(old_page, dict) else ""
                        if old_clean:
                            old_clean_abs = abs_from_rel(self.project_dir, old_clean)
                            if os.path.exists(old_clean_abs):
                                os.remove(old_clean_abs)
                    except Exception:
                        pass

            final_paint = curr.get("final_paint")
            if final_paint is not None:
                ensure_dir(os.path.join(self.project_dir, "final_paint"))
                paint_path = os.path.join(self.project_dir, "final_paint", f"final_paint_{i + 1:04d}.png")
                if isinstance(final_paint, (bytes, bytearray)):
                    with open(paint_path, "wb") as f:
                        f.write(final_paint)
                    page["final_paint"] = relpath(paint_path, self.project_dir)
                elif isinstance(final_paint, np.ndarray):
                    imwrite_unicode(paint_path, final_paint)
                    page["final_paint"] = relpath(paint_path, self.project_dir)

            final_paint_above = curr.get("final_paint_above")
            if final_paint_above is not None:
                ensure_dir(os.path.join(self.project_dir, "final_paint_above"))
                paint_path = os.path.join(self.project_dir, "final_paint_above", f"final_paint_above_{i + 1:04d}.png")
                if isinstance(final_paint_above, (bytes, bytearray)):
                    with open(paint_path, "wb") as f:
                        f.write(final_paint_above)
                    page["final_paint_above"] = relpath(paint_path, self.project_dir)
                elif isinstance(final_paint_above, np.ndarray):
                    imwrite_unicode(paint_path, final_paint_above)
                    page["final_paint_above"] = relpath(paint_path, self.project_dir)

            # Lazy-load 상태에서 실제 payload(bytes/ndarray)를 아직 읽지 않았더라도,
            # 기존 파일 경로 참조는 project.json에 유지한다.
            for _page_key, _path_key in (
                ("working_source", "working_source_path"),
                ("clean", "clean_path"),
                ("final_paint", "final_paint_path"),
                ("final_paint_above", "final_paint_above_path"),
            ):
                if _page_key not in page:
                    _asset_path = curr.get(_path_key)
                    if _asset_path and os.path.exists(_asset_path):
                        page[_page_key] = relpath(_asset_path, self.project_dir)

            pages[i] = _sanitize_page_file_refs_for_project(self.project_dir, [page])[0]

        ui_state = getattr(self, "ui_state", None)
        if not isinstance(ui_state, dict):
            ui_state = payload.get("ui_state", {}) if isinstance(payload.get("ui_state"), dict) else {}

        payload = {
            "version": PROJECT_VERSION,
            "current_index": int(current_index),
            "pages": pages[:len(paths)],
            "ui_state": json_safe(ui_state or {}),
        }

        self.write_manifest()
        tmp_path = self.project_file + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.project_file)
        try:
            clear_page_journals(self.project_dir, indices)
        except Exception:
            pass
        return True

    def load(self, project_json_path: str, lazy_assets: bool = False, progress_callback=None) -> Tuple[List[str], Dict[int, dict], int]:
        project_json_path = os.path.abspath(project_json_path)
        self.project_dir = os.path.dirname(project_json_path)

        _emit_store_progress(progress_callback, 0, 0, "project.json을 읽는 중...")
        with open(project_json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        _emit_store_progress(progress_callback, 0, 0, "페이지 저널을 적용하는 중...")
        payload = apply_page_journals_to_payload(self.project_dir, payload)

        self.ui_state = payload.get("ui_state") if isinstance(payload.get("ui_state"), dict) else {}

        paths: List[str] = []
        data: Dict[int, dict] = {}
        pages = payload.get("pages", [])
        if not isinstance(pages, list):
            pages = []
        total_pages = len(pages)

        for i, page in enumerate(pages):
            if i == 0 or (i + 1) == total_pages or (i + 1) % 25 == 0:
                try:
                    page_name = str((page or {}).get("original_name") or os.path.basename(str((page or {}).get("image") or "")) or f"page {i + 1}")
                except Exception:
                    page_name = f"page {i + 1}"
                _emit_store_progress(progress_callback, i + 1, max(1, total_pages), f"페이지 메타데이터 로딩 중... {i + 1} / {total_pages}\n{page_name}")
            image_path = abs_from_rel(self.project_dir, page["image"])
            paths.append(image_path)

            ori = None

            mask_merge = None
            mask_merge_path = None
            if page.get("mask_merge"):
                p = abs_from_rel(self.project_dir, page["mask_merge"])
                if os.path.exists(p):
                    mask_merge_path = p

            mask_inpaint = None
            mask_inpaint_path = None
            if page.get("mask_inpaint"):
                p = abs_from_rel(self.project_dir, page["mask_inpaint"])
                if os.path.exists(p):
                    mask_inpaint_path = p

            mask_merge_off = None
            mask_merge_off_path = None
            if page.get("mask_merge_off"):
                p = abs_from_rel(self.project_dir, page["mask_merge_off"])
                if os.path.exists(p):
                    mask_merge_off_path = p

            mask_inpaint_off = None
            mask_inpaint_off_path = None
            if page.get("mask_inpaint_off"):
                p = abs_from_rel(self.project_dir, page["mask_inpaint_off"])
                if os.path.exists(p):
                    mask_inpaint_off_path = p

            working_source = None
            working_source_path = None
            if page.get("working_source"):
                p = abs_from_rel(self.project_dir, page["working_source"])
                if os.path.exists(p):
                    working_source_path = p
                    if not lazy_assets:
                        with open(p, "rb") as f:
                            working_source = f.read()

            bg_clean = None
            clean_path = None
            if page.get("clean"):
                p = abs_from_rel(self.project_dir, page["clean"])
                if os.path.exists(p):
                    clean_path = p
                    if not lazy_assets:
                        with open(p, "rb") as f:
                            bg_clean = f.read()

            final_paint = None
            final_paint_path = None
            if page.get("final_paint"):
                p = abs_from_rel(self.project_dir, page["final_paint"])
                if os.path.exists(p):
                    final_paint_path = p
                    if not lazy_assets:
                        with open(p, "rb") as f:
                            final_paint = f.read()

            final_paint_above = None
            final_paint_above_path = None
            if page.get("final_paint_above"):
                p = abs_from_rel(self.project_dir, page["final_paint_above"])
                if os.path.exists(p):
                    final_paint_above_path = p
                    if not lazy_assets:
                        with open(p, "rb") as f:
                            final_paint_above = f.read()

            data[i] = {
                "ori": ori,
                "data": page.get("data", []),
                "mask_merge": mask_merge,
                "mask_inpaint": mask_inpaint,
                "mask_merge_off": mask_merge_off,
                "mask_inpaint_off": mask_inpaint_off,
                "mask_merge_path": mask_merge_path,
                "mask_inpaint_path": mask_inpaint_path,
                "mask_merge_off_path": mask_merge_off_path,
                "mask_inpaint_off_path": mask_inpaint_off_path,
                "mask_toggle_enabled": bool(page.get("mask_toggle_enabled", False)),
                "use_inpainted_as_source": bool(page.get("use_inpainted_as_source", False)),
                "bg_clean": bg_clean,
                "clean_path": clean_path,
                "working_source": working_source,
                "working_source_path": working_source_path,
                "final_paint": final_paint,
                "final_paint_path": final_paint_path,
                "final_paint_above": final_paint_above,
                "final_paint_above_path": final_paint_above_path,
                "original_name": page.get("original_name", os.path.basename(image_path)),
                "ocr_analysis_regions": page.get("ocr_analysis_regions", []) if isinstance(page.get("ocr_analysis_regions", []), list) else [],
                "maker_page": page.get("maker_page", {}) if isinstance(page.get("maker_page", {}), dict) else {},
                "maker_preview_settings": page.get("maker_preview_settings", {}) if isinstance(page.get("maker_preview_settings", {}), dict) else {},
            }

        _emit_store_progress(progress_callback, max(1, total_pages), max(1, total_pages), "페이지 메타데이터 로딩 완료")

        current_index = int(payload.get("current_index", 0))
        if paths:
            current_index = max(0, min(current_index, len(paths) - 1))
        else:
            current_index = 0

        return paths, data, current_index



def has_ysbt_signature(path: str) -> bool:
    """YSBG 전용 파일인지 파일 앞쪽 고유 바이트로 확인한다."""
    try:
        with open(path, "rb") as f:
            return f.read(len(YSBG_SIGNATURE)) == YSBG_SIGNATURE
    except Exception:
        return False


def assert_ysbt_signature(path: str):
    """확장자만 바꾼 일반 ZIP/다른 파일을 잘못 여는 것을 막는다."""
    if not has_ysbt_signature(path):
        raise ValueError("YSBG 전용 시그니처가 없습니다. 올바른 .ysbg 프로젝트 파일이 아닙니다.")


def read_ysb_manifest(ysb_path: str) -> dict:
    """.ysbg 패키지의 manifest.json을 읽는다.

    파일 앞쪽의 YSBG_SIGNATURE를 먼저 확인해, 확장자만 바뀐 ZIP/다른 파일을
    프로젝트로 잘못 여는 것을 막는다.
    """
    assert_ysbt_signature(ysb_path)
    with zipfile.ZipFile(ysb_path, "r") as zf:
        with zf.open(MANIFEST_FILENAME) as f:
            data = json.loads(f.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("manifest.json 형식이 올바르지 않습니다.")
        if data.get("format") != "YSBG_PROJECT" and data.get("signature") != "YSBG-PROJECT":
            raise ValueError("YSBG 프로젝트 manifest가 아닙니다.")
        return data

def safe_project_name(name: str) -> str:
    bad = '<>:"/\\|?*'
    out = "".join("_" if ch in bad else ch for ch in str(name or "ysb_project")).strip()
    return out or "ysb_project"


def clean_workspace_name(name: str) -> str:
    """임시 프로젝트명/패키지명에서 사람이 읽을 기본 이름을 정리한다.

    .ysbg 파일명에는 UUID를 붙이지 않는다.
    UUID는 manifest.json 내부에 저장하고, 작업 폴더를 만들 때만 이름 뒤에 짧게 붙인다.
    예: unsaved_리우1_5c03f97b -> 리우1
    """
    safe = safe_project_name(name or "ysb_project")
    if safe.startswith("unsaved_"):
        rest = safe[len("unsaved_"):]
        parts = rest.rsplit("_", 1)
        if len(parts) == 2 and len(parts[1]) >= 6 and all(ch in "0123456789abcdefABCDEF" for ch in parts[1]):
            safe = parts[0] or "ysb_project"
        else:
            safe = rest or "ysb_project"
    return safe_project_name(safe)


def _read_manifest_from_dir(project_dir: str | Path) -> dict:
    try:
        manifest_path = Path(project_dir) / MANIFEST_FILENAME
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def unique_dir(parent: str | Path, base_name: str) -> str:
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    safe = safe_project_name(base_name)
    cand = parent / safe
    if not cand.exists():
        return str(cand)
    for n in range(2, 10000):
        cand = parent / f"{safe}_{n}"
        if not cand.exists():
            return str(cand)
    return str(parent / f"{safe}_{uuid.uuid4().hex[:8]}")


def unique_dir_with_code_suffix(parent: str | Path, base_name: str, code: str | None = None, *, append_code: bool = True) -> str:
    """base_name 뒤에 고유 코드를 붙여 충돌 없는 작업 폴더를 만든다.

    v2.4 workspace 정책:
    - append_code=True이면 기존 _8~12자리 ID를 제거한 뒤 새 ID 하나만 붙인다.
    - 충돌 시 _2를 누적하지 않고 새 ID를 다시 뽑는다.
    - append_code=False는 이미 확정된 이름을 그대로 쓰는 구형 호환 경로다.
    """
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    if append_code:
        return unique_dir_with_replaced_code_suffix(parent, base_name, code)[0]
    safe = safe_project_name(base_name)
    first = parent / safe
    if not first.exists():
        return str(first)
    for n in range(2, 10000):
        cand = parent / f"{first.name}_{n}"
        if not cand.exists():
            return str(cand)
    return str(parent / f"{first.name}_{uuid.uuid4().hex[:8]}")



PAGE_FILE_KEYS = (
    "image",
    "mask_merge",
    "mask_inpaint",
    "mask_merge_off",
    "mask_inpaint_off",
    "working_source",
    "clean",
    "final_paint",
    "final_paint_above",
)


PAGE_FILE_DESTS = {
    "image": ("images", "page"),
    "mask_merge": ("masks/text_mask", "mask_merge"),
    "mask_inpaint": ("masks/paint_mask", "mask_inpaint"),
    "mask_merge_off": ("masks/text_mask_off", "mask_merge_off"),
    "mask_inpaint_off": ("masks/paint_mask_off", "mask_inpaint_off"),
    "working_source": ("working_source", "working_source"),
    "clean": ("clean", "clean"),
    "final_paint": ("final_paint", "final_paint"),
    "final_paint_above": ("final_paint_above", "final_paint_above"),
}


MASK_PAGE_KEYS = {"mask_merge", "mask_inpaint", "mask_merge_off", "mask_inpaint_off"}


def _mask_canonical_path(project_dir: str, key: str, page_index: int) -> str | None:
    if key not in MASK_PAGE_KEYS:
        return None
    folder, prefix = PAGE_FILE_DESTS.get(key, ("masks", key))
    dst_dir = os.path.join(project_dir, *folder.split("/"))
    ensure_dir(dst_dir)
    return os.path.join(dst_dir, f"{prefix}_{page_index + 1:04d}.npy")


def _remove_numbered_mask_variants(canonical_path: str | None):
    if not canonical_path:
        return 0
    try:
        canonical = Path(canonical_path)
        folder = canonical.parent
        stem = canonical.stem
        suffix = canonical.suffix or ".npy"
        removed = 0
        pattern = re.compile(rf"^{re.escape(stem)}\(\d+\){re.escape(suffix)}$", re.IGNORECASE)
        for p in folder.iterdir():
            if not p.is_file():
                continue
            if pattern.match(p.name):
                try:
                    p.unlink()
                    removed += 1
                except Exception:
                    pass
        return removed
    except Exception:
        return 0


def _atomic_save_mask_array(path: str, mask_value):
    ensure_dir(os.path.dirname(path))
    tmp = str(path) + ".tmp.npy"
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass
    np.save(tmp, np.array(mask_value, dtype=np.uint8).copy())
    os.replace(tmp, path)
    _remove_numbered_mask_variants(path)


def _canonicalize_mask_file(project_dir: str, key: str, src_path: str | None, page_index: int) -> str | None:
    canonical = _mask_canonical_path(project_dir, key, page_index)
    if not canonical:
        return None
    src = str(src_path or "")
    if src:
        try:
            if not (os.path.isabs(src) or PureWindowsPath(src).is_absolute() or PurePosixPath(src).is_absolute()):
                src = abs_from_rel(project_dir, src)
        except Exception:
            src = abs_from_rel(project_dir, src)
    try:
        if src and os.path.isfile(src) and os.path.abspath(src) != os.path.abspath(canonical):
            ensure_dir(os.path.dirname(canonical))
            shutil.copy2(src, canonical)
        elif (not os.path.isfile(canonical)) and src and os.path.isfile(src):
            shutil.copy2(src, canonical)
        if os.path.isfile(canonical):
            _remove_numbered_mask_variants(canonical)
            return canonical
    except Exception:
        pass
    return canonical if os.path.isfile(canonical) else None


def cleanup_duplicate_mask_files(project_dir: str) -> dict:
    """Keep one canonical mask file per page/type and remove mask_0001(1).npy style duplicates.

    If duplicate variants are newer than the canonical file, the newest file is promoted to
    the canonical name first. Masks are core project data, so this never compresses or
    transforms content; it only normalizes filenames.
    """
    stats = {"groups": 0, "promoted": 0, "removed": 0}
    try:
        for key in sorted(MASK_PAGE_KEYS):
            folder, prefix = PAGE_FILE_DESTS.get(key, ("masks", key))
            dst_dir = Path(project_dir).joinpath(*folder.split("/"))
            if not dst_dir.exists():
                continue
            pat = re.compile(rf"^{re.escape(prefix)}_(\d{{4}})(?:\((\d+)\))?\.npy$", re.IGNORECASE)
            groups = {}
            for p in dst_dir.iterdir():
                if not p.is_file():
                    continue
                m = pat.match(p.name)
                if not m:
                    continue
                groups.setdefault(m.group(1), []).append(p)
            for page_no, files in groups.items():
                if len(files) <= 1 and files[0].name == f"{prefix}_{page_no}.npy":
                    continue
                stats["groups"] += 1
                canonical = dst_dir / f"{prefix}_{page_no}.npy"
                try:
                    best = max(files, key=lambda x: x.stat().st_mtime)
                except Exception:
                    best = files[-1]
                try:
                    if best.resolve() != canonical.resolve():
                        shutil.copy2(best, canonical)
                        stats["promoted"] += 1
                except Exception:
                    pass
                for p in files:
                    try:
                        if p.resolve() == canonical.resolve():
                            continue
                    except Exception:
                        if str(p) == str(canonical):
                            continue
                    try:
                        p.unlink()
                        stats["removed"] += 1
                    except Exception:
                        pass
    except Exception as e:
        try:
            _save_diag_log("MASK_DUP_CLEANUP_EXCEPTION", error=repr(e))
        except Exception:
            pass
    if stats.get("groups") or stats.get("removed"):
        try:
            _save_diag_log("MASK_DUP_CLEANUP_DONE", **stats)
        except Exception:
            pass
    return stats


def normalize_mask_page_refs(project_dir: str, pages: list[dict]) -> list[dict]:
    if not isinstance(pages, list):
        return pages
    for i, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        for key in MASK_PAGE_KEYS:
            canonical = _mask_canonical_path(project_dir, key, i)
            if canonical and os.path.exists(canonical):
                page[key] = relpath(canonical, project_dir)
    return pages


def _normalize_zip_name(name: str) -> str:
    return str(name or "").replace("\\", "/").lstrip("/")


def _zip_ref_is_safe(rel: str) -> bool:
    """YSBG 패키지 내부에 들어가도 되는 상대 경로인지 검사한다.

    Save As 중 구 작업 폴더의 Windows 절대 경로가 project.json에 남으면
    zip member로 들어가고, 다음 열기 때 안전 검사에서 막힌다.
    여기서는 절대경로/상위폴더 탈출/드라이브 경로를 모두 패키지 외부 참조로 본다.
    """
    text = str(rel or "").strip().replace("\\", "/")
    if not text:
        return False
    try:
        if PureWindowsPath(text).is_absolute() or PurePosixPath(text).is_absolute() or os.path.isabs(text):
            return False
    except Exception:
        pass
    parts = [p for p in text.split("/") if p]
    if not parts:
        return False
    if any(p == ".." for p in parts):
        return False
    # C:/Users/... 같은 드라이브 표기를 lstrip('/') 뒤에도 막는다.
    if parts and len(parts[0]) >= 2 and parts[0][1] == ":":
        return False
    return True


def _is_path_inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except Exception:
        return False


def _copy_external_page_file_into_project(project_dir: str, key: str, value: str, page_index: int) -> str | None:
    """절대/외부 page file 참조를 현재 project_dir 내부 파일로 복사하고 상대 경로를 돌려준다."""
    raw = str(value or "").strip()
    if not raw:
        return None

    src = raw
    try:
        if not (os.path.isabs(src) or PureWindowsPath(src).is_absolute() or PurePosixPath(src).is_absolute()):
            src = abs_from_rel(project_dir, src)
    except Exception:
        src = abs_from_rel(project_dir, src)

    try:
        if not os.path.isfile(src):
            return None
        folder, prefix = PAGE_FILE_DESTS.get(key, ("assets", key or "file"))
        dst_dir = os.path.join(project_dir, *folder.split("/"))
        ensure_dir(dst_dir)
        ext = Path(src).suffix or ".bin"
        if key == "image":
            stem = safe_image_file_stem(Path(src).stem, fallback=f"page{page_index + 1:04d}")
            dst = os.path.join(dst_dir, f"{stem}{ext}")
            if os.path.exists(dst) and os.path.abspath(dst) != os.path.abspath(src):
                for n in range(1, 10000):
                    cand = os.path.join(dst_dir, f"{stem}({n}){ext}")
                    if not os.path.exists(cand):
                        dst = cand
                        break
            if os.path.abspath(dst) != os.path.abspath(src):
                shutil.copy2(src, dst)
            return relpath(dst, project_dir)

        if key in MASK_PAGE_KEYS:
            dst = _mask_canonical_path(project_dir, key, page_index)
            if not dst:
                return None
            if os.path.abspath(dst) != os.path.abspath(src):
                shutil.copy2(src, dst)
            _remove_numbered_mask_variants(dst)
            return relpath(dst, project_dir)

        stem = f"{prefix}_{page_index + 1:04d}"
        dst = os.path.join(dst_dir, f"{stem}{ext}")
        if os.path.abspath(dst) != os.path.abspath(src):
            shutil.copy2(src, dst)
        return relpath(dst, project_dir)
    except Exception:
        return None


def _sanitize_page_file_refs_for_project(project_dir: str, pages: list[dict]) -> list[dict]:
    """project.json page 파일 참조를 패키지 안전 상대 경로로 정규화한다."""
    if not isinstance(pages, list):
        return pages
    for i, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        for key in PAGE_FILE_KEYS:
            value = page.get(key)
            if not value:
                continue
            rel = _normalize_zip_name(str(value))
            if _zip_ref_is_safe(rel):
                page[key] = rel
                continue
            fixed = _copy_external_page_file_into_project(project_dir, key, str(value), i)
            if fixed and _zip_ref_is_safe(fixed):
                page[key] = _normalize_zip_name(fixed)
            else:
                # 안전하지 않은 경로를 project.json/패키지에 남기지 않는다.
                page.pop(key, None)
    return pages


def _page_entry_members(page: dict) -> set[str]:
    """project.json의 한 페이지가 참조하는 패키지 내부 파일 목록."""
    out: set[str] = set()
    if not isinstance(page, dict):
        return out
    for key in PAGE_FILE_KEYS:
        value = page.get(key)
        if not value:
            continue
        name = _normalize_zip_name(str(value))
        if name and _zip_ref_is_safe(name):
            out.add(name)
    return out


def _read_project_payload_from_ysbt(ysb_path: str) -> dict:
    assert_ysbt_signature(ysb_path)
    with zipfile.ZipFile(ysb_path, "r") as zf:
        with zf.open(PROJECT_FILENAME) as f:
            payload = json.loads(f.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("YSBG project.json 형식이 올바르지 않습니다.")
    return payload


def _sanitize_project_json_file(project_dir: str) -> dict:
    """project.json의 page 파일 참조를 현재 작업 폴더 기준 안전 상대경로로 고정한다.

    특히 Save As 직후에는 구 작업 폴더의 절대경로/../ 경로가 project.json에 남으면
    새 .ysbg가 다시 열리지 않는다. 패키징 직전에 한 번 더 정규화해 안전하지 않은
    참조를 새 작업 폴더 안으로 복사하거나 제거한다.
    """
    project_path = os.path.join(project_dir, PROJECT_FILENAME)
    with open(project_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("현재 project.json 형식이 올바르지 않습니다.")
    pages = payload.get("pages", [])
    if isinstance(pages, list):
        cleanup_duplicate_mask_files(project_dir)
        payload["pages"] = normalize_mask_page_refs(project_dir, _sanitize_page_file_refs_for_project(project_dir, pages))
        with open(project_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def _iter_package_files(project_dir: str):
    """패키지에 넣을 수 있는 현재 작업 폴더 파일을 rel 경로로 순회."""
    skip_dirs = {"__pycache__", ".git", ".venv", "venv", "build", "dist"}
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for file in files:
            if file.endswith((".pyc", ".pyo")):
                continue
            abs_path = os.path.join(root, file)
            rel = os.path.relpath(abs_path, project_dir).replace("\\", "/")
            yield rel, abs_path


def _write_current_file_to_zip(zf: zipfile.ZipFile, project_dir: str, rel: str) -> bool:
    rel = _normalize_zip_name(rel)
    if not rel or rel in {PROJECT_FILENAME, MANIFEST_FILENAME, SIGNATURE_FILENAME}:
        return False
    # .ysbg 내부 member는 반드시 project_dir 기준의 안전한 상대경로만 허용한다.
    # Save As 중 C:/Users/... 또는 ../old_workspace/...가 rel로 흘러 들어오면
    # 열기 단계의 안전 검사에서 막히므로, 패키징 단계에서 먼저 차단한다.
    if not _zip_ref_is_safe(rel):
        return False
    abs_path = os.path.abspath(os.path.join(project_dir, rel.replace("/", os.sep)))
    project_abs = os.path.abspath(project_dir)
    try:
        if os.path.commonpath([project_abs, abs_path]) != project_abs:
            return False
    except Exception:
        return False
    if not os.path.isfile(abs_path):
        return False
    zf.write(abs_path, rel)
    return True


def _package_project_incremental(project_dir: str, ysb_path: str, dirty_pages: set[int], *, progress_callback=None, cancel_checker=None) -> str:
    _save_diag_log("INCREMENTAL_ENTER", project_dir=project_dir, ysb_path=ysb_path, dirty_pages=sorted(list(dirty_pages or set())))
    """기존 YSBG를 기반으로 dirty page만 새 파일로 교체해 다시 쓴다.

    ZIP은 내부 파일을 안정적으로 제자리 수정하기 어렵다. 그래서 실제 구현은
    temp YSBG를 새로 만들되, clean page 파일은 기존 YSBG에서 그대로 복사하고
    dirty page 파일과 project.json/manifest/global 파일만 현재 작업 폴더에서 쓴다.

    v2.4 QA9: 저장도 페이지 큐처럼 보이도록 진행 콜백/취소 콜백을 지원한다.
    원본 .ysbg는 temp 패키지 작성과 검증이 끝난 뒤 마지막 os.replace에서만 교체된다.
    취소되면 temp 파일만 삭제하고 원본 .ysbg는 그대로 둔다.
    """
    project_dir = os.path.abspath(project_dir)
    try:
        flush_page_journals_to_project_json(project_dir)
    except Exception:
        pass
    ysb_path = os.path.abspath(ysb_path)
    if not os.path.exists(ysb_path):
        raise FileNotFoundError(ysb_path)
    _save_diag_log("INCREMENTAL_ASSERT_SIGNATURE_BEGIN", ysb_path=ysb_path)
    assert_ysbt_signature(ysb_path)
    _save_diag_log("INCREMENTAL_ASSERT_SIGNATURE_DONE", ysb_path=ysb_path)

    current_project_path = os.path.join(project_dir, PROJECT_FILENAME)
    _save_diag_log("PACKAGE_SANITIZE_JSON_BEGIN", project_json=current_project_path)
    current_payload = _sanitize_project_json_file(project_dir)
    _save_diag_log("PACKAGE_SANITIZE_JSON_DONE", project_json=current_project_path)
    current_pages = current_payload.get("pages", [])
    if not isinstance(current_pages, list):
        current_pages = []

    _save_diag_log("INCREMENTAL_READ_CURRENT_JSON_DONE", page_count=len(current_pages))
    cleanup_duplicate_mask_files(project_dir)
    _save_diag_log("INCREMENTAL_READ_OLD_PAYLOAD_BEGIN", ysb_path=ysb_path)
    old_payload = _read_project_payload_from_ysbt(ysb_path)
    _save_diag_log("INCREMENTAL_READ_OLD_PAYLOAD_DONE")
    old_pages = old_payload.get("pages", []) if isinstance(old_payload, dict) else []
    if not isinstance(old_pages, list):
        old_pages = []
    if len(old_pages) != len(current_pages):
        raise ValueError("페이지 수가 바뀌어 전체 재패키징이 필요합니다.")

    # 같은 페이지 순서/이미지 기준에서만 page-index dirty를 신뢰한다.
    old_images = [_normalize_zip_name(p.get("image", "")) if isinstance(p, dict) else "" for p in old_pages]
    current_images = [_normalize_zip_name(p.get("image", "")) if isinstance(p, dict) else "" for p in current_pages]
    if old_images != current_images:
        raise ValueError("페이지 순서 또는 기준 이미지가 바뀌어 전체 재패키징이 필요합니다.")

    dirty_pages = {int(i) for i in (dirty_pages or set()) if 0 <= int(i) < len(current_pages)}

    old_page_members_by_index = [_page_entry_members(p) for p in old_pages]
    current_page_members_by_index = [_page_entry_members(p) for p in current_pages]
    old_page_members_all = set().union(*old_page_members_by_index) if old_page_members_by_index else set()
    current_page_members_all = set().union(*current_page_members_by_index) if current_page_members_by_index else set()

    # 현재 작업 폴더의 비페이지 파일은 최신 상태가 맞다. 예: scripts, txt, result, 설정성 파일 등.
    _save_diag_log("PACKAGE_PAGE_MEMBERS_DONE", page_count=len(current_pages), page_member_total=sum(len(x) for x in current_page_members_by_index))
    current_global_members: set[str] = set()
    for rel, abs_path in _iter_package_files(project_dir):
        rel = _normalize_zip_name(rel)
        if rel in {PROJECT_FILENAME, MANIFEST_FILENAME, SIGNATURE_FILENAME}:
            continue
        if not _zip_ref_is_safe(rel):
            continue
        if rel not in current_page_members_all:
            current_global_members.add(rel)

    total_pages = len(current_pages)
    tmp_path = ysb_path + ".tmp"
    if os.path.exists(tmp_path):
        _save_diag_log("INCREMENTAL_REMOVE_OLD_TMP_BEGIN", tmp_path=tmp_path)
        os.remove(tmp_path)
        _save_diag_log("INCREMENTAL_REMOVE_OLD_TMP_DONE", tmp_path=tmp_path)

    _save_diag_log("INCREMENTAL_READ_BYTES_BEGIN", project_json=current_project_path)
    with open(current_project_path, "rb") as f:
        project_json_bytes = f.read()
    manifest_path = os.path.join(project_dir, MANIFEST_FILENAME)
    with open(manifest_path, "rb") as f:
        manifest_bytes = f.read()
    _save_diag_log("INCREMENTAL_READ_BYTES_DONE", project_json_bytes=len(project_json_bytes), manifest_bytes=len(manifest_bytes), total_pages=total_pages, dirty_count=len(dirty_pages))

    _emit_package_progress(progress_callback, 0, total_pages, f"저장 준비 중... 전체 페이지 {total_pages}개 / 변경 페이지 {len(dirty_pages)}개")

    try:
        _save_diag_log("INCREMENTAL_TMP_OPEN_BEGIN", tmp_path=tmp_path)
        with open(tmp_path, "wb") as raw:
            raw.write(YSBG_SIGNATURE)
            _save_diag_log("INCREMENTAL_SIGNATURE_WRITTEN", tmp_path=tmp_path)
            with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out_zf:
                out_zf.writestr(SIGNATURE_FILENAME, "YSBG-PROJECT\n")
                out_zf.writestr(PROJECT_FILENAME, project_json_bytes)
                out_zf.writestr(MANIFEST_FILENAME, manifest_bytes)

                written = {SIGNATURE_FILENAME, PROJECT_FILENAME, MANIFEST_FILENAME}
                _save_diag_log("INCREMENTAL_BASE_ENTRIES_WRITTEN", written_count=len(written))
                with zipfile.ZipFile(ysb_path, "r") as old_zf:
                    for i in range(total_pages):
                        _check_package_cancel(cancel_checker)
                        is_dirty = i in dirty_pages
                        verb = "변경 페이지 저장" if is_dirty else "기존 페이지 복사"
                        if i == 0 or (i + 1) == total_pages or (i + 1) % 25 == 0:
                            _save_diag_log("INCREMENTAL_PAGE_BEGIN", index=i, page=i + 1, total=total_pages, is_dirty=is_dirty, written_count=len(written))
                        _emit_package_progress(progress_callback, i, total_pages, f"{verb}: {i + 1}/{total_pages}페이지")
                        members = current_page_members_by_index[i] if is_dirty else old_page_members_by_index[i]
                        for rel in sorted(members):
                            rel = _normalize_zip_name(rel)
                            if not rel or rel in written:
                                continue
                            if is_dirty:
                                if _write_current_file_to_zip(out_zf, project_dir, rel):
                                    written.add(rel)
                            else:
                                try:
                                    data = old_zf.read(rel)
                                except KeyError:
                                    # 기존 패키지에 파일이 누락된 경우에는 현재 작업 폴더에서 복구 시도한다.
                                    if _write_current_file_to_zip(out_zf, project_dir, rel):
                                        written.add(rel)
                                    continue
                                out_zf.writestr(rel, data)
                                written.add(rel)
                        _emit_package_progress(progress_callback, i + 1, total_pages, f"{verb} 완료: {i + 1}/{total_pages}페이지")
                        if i == 0 or (i + 1) == total_pages or (i + 1) % 25 == 0:
                            _save_diag_log("INCREMENTAL_PAGE_DONE", index=i, page=i + 1, total=total_pages, is_dirty=is_dirty, written_count=len(written))

                _save_diag_log("INCREMENTAL_GLOBAL_BEGIN", global_count=len(current_global_members), written_count=len(written))
                # 비페이지/global 파일은 현재 작업 폴더 기준으로 다시 쓴다.
                global_items = sorted(current_global_members)
                for _gidx, rel in enumerate(global_items):
                    _check_package_cancel(cancel_checker)
                    rel = _normalize_zip_name(rel)
                    if not rel or rel in written:
                        continue
                    if _write_current_file_to_zip(out_zf, project_dir, rel):
                        written.add(rel)
                    if (_gidx + 1) == len(global_items) or (_gidx + 1) % 25 == 0:
                        _emit_package_progress(progress_callback, total_pages, total_pages, f"비페이지 파일 반영 중: {_gidx + 1}/{len(global_items)}개")
                _save_diag_log("INCREMENTAL_GLOBAL_DONE", written_count=len(written))

        try:
            tmp_size = os.path.getsize(tmp_path)
        except Exception:
            tmp_size = -1
        _save_diag_log("INCREMENTAL_TMP_CLOSED", tmp_path=tmp_path, tmp_size=tmp_size)
        _check_package_cancel(cancel_checker)
        _emit_package_progress(progress_callback, total_pages, total_pages, "최종 반영 중입니다. 잠시만 기다려주세요...")
        _save_diag_log("INCREMENTAL_REPLACE_BEGIN", tmp_path=tmp_path, ysb_path=ysb_path, tmp_size=tmp_size)
        os.replace(tmp_path, ysb_path)
        _save_diag_log("INCREMENTAL_REPLACE_DONE", ysb_path=ysb_path)
        _emit_package_progress(progress_callback, total_pages, total_pages, "YSBG 내보내기 완료")
        _save_diag_log("INCREMENTAL_DONE", ysb_path=ysb_path)
        return ysb_path
    except PackageProjectCancelled as e:
        _save_diag_log("INCREMENTAL_CANCELLED", error=str(e), tmp_exists=os.path.exists(tmp_path))
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise
    except Exception as e:
        _save_diag_log("INCREMENTAL_EXCEPTION", error=repr(e), tmp_exists=os.path.exists(tmp_path))
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise



def append_project_json_to_package(project_dir: str, ysb_path: str, project_name: str | None = None, project_uuid: str | None = None, *, progress_callback=None, cancel_checker=None, max_duplicate_project_json: int = 24) -> str:
    """Fast path for text/translation-only saves.

    Normal ZIP packaging cannot update an entry in place, so the existing
    incremental path rewrites the whole .ysbg and recompresses/copies every clean
    page asset.  For text-only edits the page assets do not change; only
    project.json/manifest.json need to be refreshed.  ZIP readers, including
    Python's zipfile, resolve duplicate names to the last central-directory entry,
    so appending a fresh project.json is a safe and very fast journal-style update.

    To avoid unbounded package growth, after too many appended project.json
    entries this function raises and the caller falls back to the compact/full
    packaging path.
    """
    project_dir = os.path.abspath(project_dir)
    ysb_path = os.path.abspath(ysb_path)
    if not ysb_path.lower().endswith(YSB_EXTENSION):
        ysb_path += YSB_EXTENSION
    _save_diag_log("JSON_FAST_UPDATE_ENTER", project_dir=project_dir, ysb_path=ysb_path)
    _check_package_cancel(cancel_checker)
    if not os.path.exists(ysb_path):
        raise FileNotFoundError(ysb_path)
    if not os.path.exists(os.path.join(project_dir, PROJECT_FILENAME)):
        raise FileNotFoundError(f"{PROJECT_FILENAME}이 없는 프로젝트 폴더입니다: {project_dir}")
    assert_ysbt_signature(ysb_path)

    try:
        with zipfile.ZipFile(ysb_path, "r") as zf:
            project_json_count = sum(1 for info in zf.infolist() if _normalize_zip_name(info.filename) == PROJECT_FILENAME)
            manifest_count = sum(1 for info in zf.infolist() if _normalize_zip_name(info.filename) == MANIFEST_FILENAME)
    except Exception:
        project_json_count = 1
        manifest_count = 1
    if project_json_count >= int(max_duplicate_project_json or 24):
        raise ValueError(f"project.json 빠른 저장 누적 {project_json_count}회로 전체 재패키징이 필요합니다.")

    store = ProjectStore(project_dir)
    store.init_dirs()
    store.write_manifest(package_source=ysb_path, project_name=project_name, project_uuid=project_uuid)
    try:
        flush_page_journals_to_project_json(project_dir)
    except Exception:
        pass
    _sanitize_project_json_file(project_dir)

    project_path = os.path.join(project_dir, PROJECT_FILENAME)
    manifest_path = os.path.join(project_dir, MANIFEST_FILENAME)
    with open(project_path, "rb") as f:
        project_json_bytes = f.read()
    with open(manifest_path, "rb") as f:
        manifest_bytes = f.read()

    _emit_package_progress(progress_callback, 0, 1, "텍스트/JSON 빠른 저장 준비 중...")
    _check_package_cancel(cancel_checker)
    _save_diag_log(
        "JSON_FAST_UPDATE_APPEND_BEGIN",
        project_json_bytes=len(project_json_bytes),
        manifest_bytes=len(manifest_bytes),
        project_json_count=project_json_count,
        manifest_count=manifest_count,
    )
    # Duplicate-name warnings are expected here.  The last project.json is the
    # active one when the package is opened again.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(ysb_path, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.writestr(PROJECT_FILENAME, project_json_bytes)
            zf.writestr(MANIFEST_FILENAME, manifest_bytes)
    _check_package_cancel(cancel_checker)
    _emit_package_progress(progress_callback, 1, 1, "텍스트/JSON 빠른 저장 완료")
    try:
        size = os.path.getsize(ysb_path)
    except Exception:
        size = -1
    _save_diag_log("JSON_FAST_UPDATE_APPEND_DONE", ysb_path=ysb_path, size=size)
    return ysb_path

def package_project(project_dir: str, ysb_path: str, project_name: str | None = None, project_uuid: str | None = None, *, dirty_pages: set[int] | None = None, structure_dirty: bool = True, incremental: bool | None = None, progress_callback=None, cancel_checker=None) -> str:
    _save_diag_log("PACKAGE_ENTER", project_dir=project_dir, ysb_path=ysb_path, dirty_pages=sorted(list(dirty_pages or set())), structure_dirty=structure_dirty, incremental=incremental)
    """프로젝트 폴더를 .ysbg 전용 패키지 파일로 묶는다.

    v2.4 QA9: 저장 진행률/취소를 지원한다. 원본 .ysbg는 temp 파일 작성이 끝난 뒤
    마지막 os.replace에서만 교체한다. 취소 시 temp 파일을 삭제하고 원본은 유지한다.
    """
    project_dir = os.path.abspath(project_dir)
    ysb_path = os.path.abspath(ysb_path)
    if not ysb_path.lower().endswith(YSB_EXTENSION):
        ysb_path += YSB_EXTENSION
    if not os.path.exists(os.path.join(project_dir, PROJECT_FILENAME)):
        raise FileNotFoundError(f"{PROJECT_FILENAME}이 없는 프로젝트 폴더입니다: {project_dir}")

    _save_diag_log("PACKAGE_VALIDATE_DONE", project_dir=project_dir, ysb_path=ysb_path)
    store = ProjectStore(project_dir)
    store.init_dirs()
    _save_diag_log("PACKAGE_INIT_DIRS_DONE", project_dir=project_dir)
    store.write_manifest(package_source=ysb_path, project_name=project_name, project_uuid=project_uuid)
    _save_diag_log("PACKAGE_WRITE_MANIFEST_DONE", project_dir=project_dir)

    use_incremental = bool(incremental) if incremental is not None else (dirty_pages is not None and not bool(structure_dirty))
    if use_incremental and not bool(structure_dirty) and os.path.exists(ysb_path):
        try:
            _save_diag_log("PACKAGE_INCREMENTAL_ATTEMPT", ysb_path=ysb_path)
            result = _package_project_incremental(
                project_dir,
                ysb_path,
                set(dirty_pages or set()),
                progress_callback=progress_callback,
                cancel_checker=cancel_checker,
            )
            _save_diag_log("PACKAGE_INCREMENTAL_SUCCESS", result=result)
            return result
        except PackageProjectCancelled:
            _save_diag_log("PACKAGE_INCREMENTAL_CANCELLED")
            raise
        except Exception as e:
            # 안전을 우선한다. 증분 패키징이 불가능한 구조 변경/구버전 패키지는 전체 재패키징으로 자동 전환한다.
            _save_diag_log("PACKAGE_INCREMENTAL_FALLBACK_FULL", error=repr(e))
            pass

    _save_diag_log("PACKAGE_FULL_BEGIN")
    try:
        flush_page_journals_to_project_json(project_dir)
    except Exception:
        pass
    current_project_path = os.path.join(project_dir, PROJECT_FILENAME)
    current_payload = _sanitize_project_json_file(project_dir)
    current_pages = current_payload.get("pages", []) if isinstance(current_payload, dict) else []
    if not isinstance(current_pages, list):
        current_pages = []
    cleanup_duplicate_mask_files(project_dir)
    current_page_members_by_index = [_page_entry_members(p) for p in current_pages]
    current_page_members_all = set().union(*current_page_members_by_index) if current_page_members_by_index else set()

    current_global_members: set[str] = set()
    for rel, abs_path in _iter_package_files(project_dir):
        rel = _normalize_zip_name(rel)
        if rel in {PROJECT_FILENAME, MANIFEST_FILENAME, SIGNATURE_FILENAME}:
            continue
        if not _zip_ref_is_safe(rel):
            continue
        if rel not in current_page_members_all:
            current_global_members.add(rel)
    _save_diag_log("PACKAGE_GLOBAL_MEMBERS_DONE", global_count=len(current_global_members))

    os.makedirs(os.path.dirname(ysb_path), exist_ok=True)
    tmp_path = ysb_path + ".tmp"
    if os.path.exists(tmp_path):
        _save_diag_log("PACKAGE_REMOVE_OLD_TMP_BEGIN", tmp_path=tmp_path)
        os.remove(tmp_path)
        _save_diag_log("PACKAGE_REMOVE_OLD_TMP_DONE", tmp_path=tmp_path)

    total_pages = len(current_pages)
    _save_diag_log("PACKAGE_READ_BYTES_BEGIN", project_json=current_project_path)
    with open(current_project_path, "rb") as f:
        project_json_bytes = f.read()
    manifest_path = os.path.join(project_dir, MANIFEST_FILENAME)
    with open(manifest_path, "rb") as f:
        manifest_bytes = f.read()
    _save_diag_log("PACKAGE_READ_BYTES_DONE", project_json_bytes=len(project_json_bytes), manifest_bytes=len(manifest_bytes), total_pages=total_pages)

    _emit_package_progress(progress_callback, 0, total_pages, f"전체 YSBG 재패키징 준비 중... 전체 페이지 {total_pages}개")

    try:
        _save_diag_log("PACKAGE_TMP_OPEN_BEGIN", tmp_path=tmp_path)
        with open(tmp_path, "wb") as raw:
            # ZIP 앞에 전용 고유 바이트를 남긴다. Python zipfile은 앞쪽에 데이터가
            # 붙은 ZIP도 읽을 수 있으므로, 일반 ZIP과 구분하는 안전장치로 사용한다.
            raw.write(YSBG_SIGNATURE)
            _save_diag_log("PACKAGE_SIGNATURE_WRITTEN", tmp_path=tmp_path)
            with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                zf.writestr(SIGNATURE_FILENAME, "YSBG-PROJECT\n")
                zf.writestr(PROJECT_FILENAME, project_json_bytes)
                zf.writestr(MANIFEST_FILENAME, manifest_bytes)
                written = {SIGNATURE_FILENAME, PROJECT_FILENAME, MANIFEST_FILENAME}
                _save_diag_log("PACKAGE_BASE_ENTRIES_WRITTEN", written_count=len(written))

                for i, members in enumerate(current_page_members_by_index):
                    _check_package_cancel(cancel_checker)
                    if i == 0 or (i + 1) == total_pages or (i + 1) % 25 == 0:
                        _save_diag_log("PACKAGE_PAGE_BEGIN", index=i, page=i + 1, total=total_pages, member_count=len(members), written_count=len(written))
                    _emit_package_progress(progress_callback, i, total_pages, f"페이지 저장 중: {i + 1}/{total_pages}페이지")
                    for rel in sorted(members):
                        rel = _normalize_zip_name(rel)
                        if not rel or rel in written:
                            continue
                        if _write_current_file_to_zip(zf, project_dir, rel):
                            written.add(rel)
                    _emit_package_progress(progress_callback, i + 1, total_pages, f"페이지 저장 완료: {i + 1}/{total_pages}페이지")
                    if i == 0 or (i + 1) == total_pages or (i + 1) % 25 == 0:
                        _save_diag_log("PACKAGE_PAGE_DONE", index=i, page=i + 1, total=total_pages, written_count=len(written))

                _save_diag_log("PACKAGE_GLOBAL_BEGIN", global_count=len(current_global_members), written_count=len(written))
                global_items = sorted(current_global_members)
                for _gidx, rel in enumerate(global_items):
                    _check_package_cancel(cancel_checker)
                    rel = _normalize_zip_name(rel)
                    if not rel or rel in written:
                        continue
                    if _write_current_file_to_zip(zf, project_dir, rel):
                        written.add(rel)
                    if (_gidx + 1) == len(global_items) or (_gidx + 1) % 25 == 0:
                        _emit_package_progress(progress_callback, total_pages, total_pages, f"비페이지 파일 반영 중: {_gidx + 1}/{len(global_items)}개")
                _save_diag_log("PACKAGE_GLOBAL_DONE", written_count=len(written))

        try:
            tmp_size = os.path.getsize(tmp_path)
        except Exception:
            tmp_size = -1
        _save_diag_log("PACKAGE_TMP_CLOSED", tmp_path=tmp_path, tmp_size=tmp_size)
        _check_package_cancel(cancel_checker)
        _emit_package_progress(progress_callback, total_pages, total_pages, "최종 반영 중입니다. 잠시만 기다려주세요...")
        _save_diag_log("PACKAGE_REPLACE_BEGIN", tmp_path=tmp_path, ysb_path=ysb_path, tmp_size=tmp_size)
        os.replace(tmp_path, ysb_path)
        _save_diag_log("PACKAGE_REPLACE_DONE", ysb_path=ysb_path)
        _emit_package_progress(progress_callback, total_pages, total_pages, "YSBG 내보내기 완료")
        _save_diag_log("PACKAGE_DONE", ysb_path=ysb_path)
        return ysb_path
    except PackageProjectCancelled as e:
        _save_diag_log("PACKAGE_CANCELLED", error=str(e), tmp_exists=os.path.exists(tmp_path))
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise
    except Exception as e:
        _save_diag_log("PACKAGE_EXCEPTION", error=repr(e), tmp_exists=os.path.exists(tmp_path))
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise


# YSBG를 다시 열 때 작업 폴더 전체를 밀어버리면 result/txt/scripts처럼
# 사용자가 기대하는 산출물이 같이 사라질 수 있다.
# 아래 목록은 패키지 본문과 강하게 동기화되어야 하는 내부 작업 데이터만 대상으로 한다.
_YSBG_EXTRACT_MANAGED_REPLACE_DIRS = {
    "images",
    "masks",
    "clean",
    "working_source",
    "final_paint",
    "final_paint_above",
    # YSB Maker branch: these are not user export folders. They are the
    # package-synchronized imported game clone and Maker editor sidecars.
    "maker_game",
    "maker_meta",
    "maker_backup",
    "maker_diff",
}
_YSBG_EXTRACT_PRESERVE_DIRS = {
    "result",
    "txt",
    "scripts",
}


def _validate_zip_members_for_extract(zf: zipfile.ZipFile, target_dir: str):
    target_abs = os.path.abspath(target_dir)
    members = zf.infolist()
    for member in members:
        name = member.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError(f"안전하지 않은 패키지 경로입니다: {member.filename}")
        dest = os.path.abspath(os.path.join(target_dir, name))
        try:
            common = os.path.commonpath([target_abs, dest])
        except Exception:
            common = ""
        if common != target_abs:
            raise ValueError(f"패키지 경로가 작업 폴더 밖을 가리킵니다: {member.filename}")
    return members


def _prepare_workspace_for_package_overlay(zf: zipfile.ZipFile, target_dir: str, members=None, *, progress_callback=None, cancel_checker=None):
    """YSBG 재열기 전 기존 작업 폴더를 보존형으로 정리한다.

    예전 방식처럼 target_dir 전체를 삭제하지 않는다. 대신 패키지 내부에 포함된
    핵심 작업 데이터 폴더만 갱신하고, result/txt/scripts 및 사용자 임의 파일은 보존한다.
    같은 상대경로가 직접 충돌하는 파일은 zip 추출이 실패하지 않도록 정리한다.
    """
    target_abs = os.path.abspath(target_dir)
    members = members if members is not None else _validate_zip_members_for_extract(zf, target_dir)
    if not os.path.isdir(target_abs):
        return

    top_dirs_in_package: set[str] = set()
    for member in members:
        name = _normalize_zip_name(member.filename.replace("\\", "/"))
        if not name:
            continue
        first = name.split("/", 1)[0].strip()
        if first:
            top_dirs_in_package.add(first)

    # 이미지/마스크/클린본 등 project.json과 직접 연결되는 내부 작업 데이터는
    # 현재 YSBG의 내용이 기준이므로 폴더 단위로 새로 맞춘다.
    managed_to_reset = sorted((top_dirs_in_package & _YSBG_EXTRACT_MANAGED_REPLACE_DIRS) - _YSBG_EXTRACT_PRESERVE_DIRS)
    if managed_to_reset and callable(progress_callback):
        try:
            progress_callback(0, len(members), "기존 작업 폴더의 내부 데이터 정리 중...\n" + ", ".join(managed_to_reset))
        except Exception:
            pass
    for root_name in managed_to_reset:
        _check_package_cancel(cancel_checker)
        target_path = os.path.abspath(os.path.join(target_abs, root_name))
        try:
            if os.path.commonpath([target_abs, target_path]) != target_abs:
                continue
        except Exception:
            continue
        if os.path.isdir(target_path):
            shutil.rmtree(target_path, ignore_errors=True)
        elif os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass

    # project.json/manifest/.signature처럼 루트의 패키지 메타 파일은 현재 YSBG로 교체한다.
    for root_file in (PROJECT_FILENAME, MANIFEST_FILENAME, SIGNATURE_FILENAME, WORKSPACE_STATE_FILENAME):
        if root_file in top_dirs_in_package:
            p = os.path.join(target_abs, root_file)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    # 보존 폴더나 사용자 폴더는 통삭제하지 않는다. 다만 같은 rel 경로가
    # 파일/폴더 타입 충돌을 일으키면 그 충돌 지점만 정리한다.
    for member in members:
        _check_package_cancel(cancel_checker)
        name = _normalize_zip_name(member.filename.replace("\\", "/"))
        if not name:
            continue
        dest = os.path.abspath(os.path.join(target_abs, name))
        try:
            if os.path.commonpath([target_abs, dest]) != target_abs:
                continue
        except Exception:
            continue
        is_dir_member = member.is_dir() or name.endswith("/")
        if is_dir_member:
            if os.path.isfile(dest) or os.path.islink(dest):
                try:
                    os.remove(dest)
                except Exception:
                    pass
        else:
            if os.path.isdir(dest):
                shutil.rmtree(dest, ignore_errors=True)


def _safe_extract_zip(zf: zipfile.ZipFile, target_dir: str, *, progress_callback=None, cancel_checker=None):
    target_abs = os.path.abspath(target_dir)
    members = _validate_zip_members_for_extract(zf, target_dir)
    total = len(members)

    if callable(progress_callback):
        try:
            progress_callback(0, total, "압축 해제 준비 중...")
        except Exception:
            pass

    for idx, member in enumerate(members, start=1):
        _check_package_cancel(cancel_checker)
        name = member.filename.replace("\\", "/")
        if callable(progress_callback):
            try:
                progress_callback(idx - 1, total, f"압축 해제 중: {idx}/{total}\n{name}")
            except Exception:
                pass
        zf.extract(member, target_dir)
        if callable(progress_callback) and (idx == total or idx % 10 == 0):
            try:
                progress_callback(idx, total, f"압축 해제 중: {idx}/{total}\n{name}")
            except Exception:
                pass

    if callable(progress_callback):
        try:
            progress_callback(total, total, "압축 해제 완료")
        except Exception:
            pass


def _same_package_source(a: str | None, b: str | None) -> bool:
    try:
        if not a or not b:
            return False
        return os.path.abspath(str(a)).lower() == os.path.abspath(str(b)).lower()
    except Exception:
        return False


def strip_runtime_code_suffix_from_name(name: str, fallback: str = "ysb_project") -> str:
    """작업 폴더/구형 파일명 끝의 _8~12자리 ID와 강제 YSBG 꼬리를 제거한다."""
    stem = clean_workspace_name(name or fallback)
    try:
        cleaned = re.sub(r"(?:[\s_-]+YSBG)$", "", stem, flags=re.IGNORECASE).strip(" _-. ")
        if cleaned:
            stem = clean_workspace_name(cleaned)
    except Exception:
        pass
    m = re.match(r"^(.*)_([0-9a-fA-F]{8,12})$", stem)
    if m:
        base = clean_workspace_name(m.group(1) or fallback)
        return base or fallback
    return stem or fallback


def unique_dir_with_replaced_code_suffix(parent: str | Path, base_name: str, code: str | None = None) -> tuple[str, str]:
    """base_name의 기존 ID는 제거하고 새 code 하나만 붙인 폴더를 만든다."""
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    base = safe_project_name(strip_runtime_code_suffix_from_name(base_name))
    for _ in range(10000):
        next_code = str(code or uuid.uuid4().hex)[:12]
        cand = parent / f"{base}_{next_code}"
        if not cand.exists():
            return str(cand), next_code
        code = uuid.uuid4().hex
    next_code = uuid.uuid4().hex[:12]
    return str(parent / f"{base}_{next_code}"), next_code


def unique_recovery_dir_for_workspace(path: str | Path) -> str:
    """기존 workspace를 삭제하지 않고 같은 위치에 '(복구)' 이름으로 밀어낸다."""
    src = Path(path)
    parent = src.parent
    base = src.name
    first = parent / f"{base}(복구)"
    if not first.exists():
        return str(first)
    for n in range(2, 10000):
        cand = parent / f"{base}(복구{n})"
        if not cand.exists():
            return str(cand)
    return str(parent / f"{base}(복구_{uuid.uuid4().hex[:8]})")


def _find_existing_workspace_by_uuid_and_source(workspaces_root: str | Path, project_uuid: str, package_source: str) -> str | None:
    """workspaces 안에서 같은 project_uuid + 같은 .ysbg 경로를 가진 작업 폴더를 찾는다.

    .ysbg 파일명이 기준이고, UUID는 내부 manifest/meta에만 저장된다.
    이미 같은 YSBG를 가져온 상태라면 사용자에게 다시 물어보지 않고 해당 폴더를 조용히 재사용한다.
    """
    try:
        root = Path(workspaces_root)
        if not root.exists():
            return None
        package_source_abs = os.path.abspath(str(package_source)).lower()
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if not (child / PROJECT_FILENAME).exists():
                continue
            m = _read_manifest_from_dir(child)
            if str(m.get("project_uuid") or "") != str(project_uuid):
                continue
            src = str(m.get("package_source") or "")
            if src and os.path.abspath(src).lower() == package_source_abs:
                return str(child)
    except Exception:
        pass
    return None


def _find_existing_workspace_by_uuid(workspaces_root: str | Path, project_uuid: str) -> str | None:
    """workspaces 안에서 같은 project_uuid를 가진 작업 폴더를 찾는다.

    같은 이름+ID 폴더가 없는데 같은 UUID를 가진 다른 폴더가 있으면,
    사용자가 .ysbg 파일명을 바꿔 새 이름으로 연 상황일 수 있다.
    이때는 기존 작업 인스턴스와 연결을 끊기 위해 새 UUID를 부여한다.
    """
    try:
        root = Path(workspaces_root)
        if not root.exists():
            return None
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if not (child / PROJECT_FILENAME).exists():
                continue
            m = _read_manifest_from_dir(child)
            if str(m.get("project_uuid") or "") == str(project_uuid):
                return str(child)
    except Exception:
        pass
    return None


def workspace_state_path(project_dir: str | Path) -> str:
    return os.path.join(str(project_dir), WORKSPACE_STATE_FILENAME)


def read_workspace_state(project_dir: str | Path) -> dict:
    try:
        p = workspace_state_path(project_dir)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def write_workspace_state(project_dir: str | Path, **updates) -> dict:
    """workspace 자체에 붙는 작은 상태표.

    큰 데이터는 전부 workspace/project.json과 images/clean/masks에 있고,
    이 파일은 이 작업대가 미저장 상태인지, 어느 .ysbg에서 왔는지 정도만 기록한다.
    """
    project_dir = os.path.abspath(str(project_dir))
    state = read_workspace_state(project_dir)
    if not isinstance(state, dict):
        state = {}
    state.update({k: v for k, v in updates.items() if v is not None})
    state.setdefault("type", "ysb_workspace_state")
    state["project_dir"] = project_dir
    state["project_file"] = os.path.join(project_dir, PROJECT_FILENAME)
    state["updated_at"] = datetime.now().timestamp()
    try:
        m = _read_manifest_from_dir(project_dir)
        if m:
            state.setdefault("project_uuid", str(m.get("project_uuid") or ""))
            state.setdefault("project_name", str(m.get("project_name") or os.path.basename(project_dir)))
            if m.get("package_source"):
                state.setdefault("source_ysbg_path", str(m.get("package_source") or ""))
    except Exception:
        pass
    try:
        tmp = workspace_state_path(project_dir) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, workspace_state_path(project_dir))
    except Exception:
        pass
    return state


def workspace_is_dirty(project_dir: str | Path) -> bool:
    """기존 workspace를 덮어써도 되는지 판단한다.

    상태 파일이 없으면 구버전/저장된 해제본으로 보고 덮어써도 된다.
    상태 파일에서 is_dirty=True거나 폴더명 끝이 '(복구)'면 미저장 작업대로 본다.
    """
    try:
        name = os.path.basename(os.path.abspath(str(project_dir)))
        if name.endswith("(복구)") or "(복구)" in name:
            return True
    except Exception:
        pass
    state = read_workspace_state(project_dir)
    try:
        return bool(state.get("is_dirty", False))
    except Exception:
        return False


def rebase_workspace_state_project_dir(old_project_dir: str | Path, new_project_dir: str | Path):
    """workspace를 '(복구)'로 밀어낼 때 상태 파일도 새 위치를 가리키게 갱신한다."""
    try:
        old_state = read_workspace_state(old_project_dir)
        old_abs = os.path.abspath(str(old_project_dir))
        new_abs = os.path.abspath(str(new_project_dir))
        payload = old_state if isinstance(old_state, dict) else {}
        payload.update({
            "type": "ysb_workspace_state",
            "project_dir": new_abs,
            "project_file": os.path.join(new_abs, PROJECT_FILENAME),
            "is_dirty": True,
            "is_recovery": True,
            "recovery_renamed_from": old_abs,
            "updated_at": datetime.now().timestamp(),
        })
        tmp = workspace_state_path(new_abs) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, workspace_state_path(new_abs))
    except Exception:
        pass

def extract_ysb_package(ysb_path: str, workspaces_root: str, reuse_existing: bool = False, *, progress_callback=None, cancel_checker=None) -> tuple[str, dict, bool]:
    """.ysbg를 workspaces_root 안의 작업 폴더로 푼다.

    반환: (project_dir, manifest, reused_existing)

    v2.4 안정화:
    - .ysbg는 항상 본체로 취급한다.
    - 일반 열기에서는 같은 이름/uuid 작업 폴더를 재사용하되, 폴더 전체를 삭제하지 않는다.
      현재 .ysbg에 포함된 내부 작업 데이터만 갱신하고 result/txt/scripts/사용자 파일은 보존한다.
    - 저장되지 않은 작업 복구는 이 함수가 아니라 work_sessions/temp 복구 루트에서 별도 처리한다.
    """
    ysb_path = os.path.abspath(ysb_path)
    manifest = read_ysb_manifest(ysb_path)
    raw_file_title = clean_workspace_name(Path(ysb_path).stem)
    file_title = strip_runtime_code_suffix_from_name(raw_file_title)
    project_uuid = str(manifest.get("project_uuid") or uuid.uuid4().hex)
    code = project_uuid[:8]

    # 예외적 구버전 호환 옵션. 일반 UI에서는 reuse_existing=False로 호출한다.
    if reuse_existing:
        existing = _find_existing_workspace_by_uuid_and_source(workspaces_root, project_uuid, ysb_path)
        if existing:
            return existing, manifest, True

    # 사용자가 직접 보는 .ysbg 파일명은 깔끔하게 유지하고,
    # 내부 관리용 작업 폴더에만 uuid 짧은값을 뒤에 붙인다.
    base_title = safe_project_name(strip_runtime_code_suffix_from_name(file_title))
    target = os.path.join(str(workspaces_root), f"{base_title}_{code}")

    # 일반 열기는 .ysbg 본체를 기준으로 해야 한다.
    # 다만 새 ID는 아무 때나 발급하지 않는다.
    # A) 같은 이름+ID workspace가 있고 dirty 상태가 아니면 같은 YSBG 재열기이므로 기존 폴더를 비우고 재사용한다.
    # B) 같은 이름+ID workspace가 dirty/(복구) 상태면 기존 폴더를 '(복구)'로 보존하고 새 ID로 연다.
    # C) 같은 이름+ID workspace는 없지만 같은 UUID의 다른 workspace가 있으면 파일명 변경 진입으로 보고 새 ID로 연다.
    if not reuse_existing:
        root_abs = os.path.abspath(str(workspaces_root))
        target_abs = os.path.abspath(str(target))
        try:
            common = os.path.commonpath([root_abs, target_abs])
        except Exception:
            common = ""
        if common != root_abs or target_abs == root_abs:
            raise RuntimeError(f"안전하지 않은 작업 폴더 경로입니다: {target}")

        if os.path.exists(target_abs):
            has_recovery = workspace_is_dirty(target_abs)
            if has_recovery and (os.path.exists(os.path.join(target_abs, PROJECT_FILENAME)) or os.listdir(target_abs)):
                recovery_target = unique_recovery_dir_for_workspace(target_abs)
                os.replace(target_abs, recovery_target)
                rebase_workspace_state_project_dir(target_abs, recovery_target)
                old_uuid = project_uuid
                project_uuid = uuid.uuid4().hex
                code = project_uuid[:8]
                target, _used_code = unique_dir_with_replaced_code_suffix(workspaces_root, file_title, code)
                target_abs = os.path.abspath(str(target))
                manifest["project_uuid"] = project_uuid
                manifest["workspace_rebased_from_project_uuid"] = old_uuid
                manifest["workspace_recovery_preserved_dir"] = recovery_target
                os.makedirs(target_abs, exist_ok=True)
            else:
                # 복구 이력이 없는 같은 이름+ID workspace는 정상 재열기다.
                # 작업 폴더 전체를 삭제하지 않고 현재 YSBG 내용만 overlay로 갱신한다.
                # result/txt/scripts 및 사용자가 별도로 둔 비충돌 파일은 보존한다. ID 유지.
                os.makedirs(target_abs, exist_ok=True)
        else:
            existing_same_uuid = _find_existing_workspace_by_uuid(workspaces_root, project_uuid)
            if existing_same_uuid:
                # 파일명 변경 등으로 이름+ID 조합이 달라진 새 진입.
                # 기존 작업 인스턴스와 연결을 끊기 위해 새 ID를 부여한다.
                old_uuid = project_uuid
                project_uuid = uuid.uuid4().hex
                code = project_uuid[:8]
                target, _used_code = unique_dir_with_replaced_code_suffix(workspaces_root, file_title, code)
                target_abs = os.path.abspath(str(target))
                manifest["project_uuid"] = project_uuid
                manifest["workspace_rebased_from_project_uuid"] = old_uuid
                manifest["workspace_rebased_reason"] = "renamed_package_or_new_title"
            os.makedirs(target_abs, exist_ok=True)
    else:
        if os.path.exists(os.path.join(target, PROJECT_FILENAME)):
            existing_manifest = _read_manifest_from_dir(target)
            existing_uuid = str(existing_manifest.get("project_uuid") or "")
            existing_source = str(existing_manifest.get("package_source") or "")
            if reuse_existing and existing_uuid and existing_uuid == project_uuid and _same_package_source(existing_source, ysb_path):
                return target, manifest, True
            target, _used_code = unique_dir_with_replaced_code_suffix(workspaces_root, file_title, uuid.uuid4().hex[:8])
        else:
            os.makedirs(target, exist_ok=True)
        os.makedirs(target, exist_ok=True)

    try:
        with zipfile.ZipFile(ysb_path, "r") as zf:
            members = _validate_zip_members_for_extract(zf, target)
            if not reuse_existing:
                _prepare_workspace_for_package_overlay(
                    zf,
                    target,
                    members,
                    progress_callback=progress_callback,
                    cancel_checker=cancel_checker,
                )
            _safe_extract_zip(zf, target, progress_callback=progress_callback, cancel_checker=cancel_checker)
    except PackageProjectCancelled:
        # 일반 열기에서는 기존 해제본을 비우고 새로 푸는 중이므로,
        # 취소 시 부분 압축 해제 폴더가 남지 않게 정리한다.
        if not reuse_existing:
            try:
                shutil.rmtree(target, ignore_errors=True)
            except Exception:
                pass
        raise
    except Exception:
        if not reuse_existing and not os.path.exists(os.path.join(target, PROJECT_FILENAME)):
            try:
                shutil.rmtree(target, ignore_errors=True)
            except Exception:
                pass
        raise

    if not os.path.exists(os.path.join(target, PROJECT_FILENAME)):
        raise FileNotFoundError(f"패키지 안에 {PROJECT_FILENAME}이 없습니다: {ysb_path}")

    # 압축 해제 후 작업 폴더 manifest에는 실제 패키지 경로와 사람이 읽을 프로젝트명을 기록한다.
    try:
        ProjectStore(target).write_manifest(package_source=ysb_path, project_name=file_title, project_uuid=project_uuid)
    except Exception:
        pass
    try:
        write_workspace_state(
            target,
            source_ysbg_path=ysb_path,
            project_uuid=project_uuid,
            project_name=file_title,
            is_dirty=False,
            is_recovery=False,
            opened_at=datetime.now().timestamp(),
        )
    except Exception:
        pass
    return target, manifest, False

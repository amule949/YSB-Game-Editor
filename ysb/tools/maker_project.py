from __future__ import annotations

import json
import ast
import math
import os
import re
import shutil
import hashlib
import html
import unicodedata
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import cv2
import numpy as np

from ysb.tools.maker_engines import get_engine_adapter, engine_module_metadata, normalize_engine
from ysb.settings.translation_prompt_presets import (
    PROMPT_BLOCK_BEGIN,
    PROMPT_BLOCK_END,
    get_runtime_prompt_templates,
    render_prompt_template,
)


RPG_MAKER_DATA_DIR = "data"
MAKER_CLONE_DIR = "maker_game"
MAKER_META_DIR = "maker_meta"
MAKER_BACKUP_DIR = "maker_backup"
MAKER_ORIGINAL_JSON_BACKUP_DIR = "original_json"
MAKER_DIFF_DIR = "maker_diff"
MAKER_IMPORT_SUMMARY_FILE = "maker_import_summary.json"
MAKER_PROJECT_LAYOUT_FILE = "maker_project_layout.json"
MAKER_PREVIEW_SETTINGS_FILE = "maker_preview_settings.json"
MAKER_WRITEBACK_SUMMARY_FILE = "maker_writeback_summary.json"
MAKER_SPEAKER_SUMMARY_FILE = "maker_speaker_summary.json"
MAKER_CHARACTER_PROMPTS_FILE = "maker_character_prompts.json"
MAKER_DATABASE_SUMMARY_FILE = "maker_database_summary.json"
MAKER_PLUGIN_SUMMARY_FILE = "maker_plugin_summary.json"
MAKER_CHARACTER_PROFILES_FILE = "maker_character_profiles.json"
MAKER_TRANSLATION_SETTINGS_FILE = "maker_translation_settings.json"
MAKER_RUNTIME_PROFILE_FILE = "maker_runtime_profile.json"
MAKER_PREVIEW_DIAGNOSTICS_FILE = "maker_preview_diagnostics.jsonl"
MAKER_PREVIEW_DIAGNOSTICS_LAST_FILE = "maker_preview_diagnostics_last.json"
MAKER_FONT_CACHE_DIR = "font_cache"
MAKER_KEEP_FILE = ".ysb_keep"


DEFAULT_MAKER_TRANSLATION_SETTINGS: Dict[str, Any] = {
    "normalize_source_newlines": False,
    "newline_join_mode": "auto",  # auto / cjk_join / space
}


DEFAULT_MAKER_PREVIEW_SETTINGS: Dict[str, Any] = {
    "font_family": "맑은 고딕",
    "font_path": "",
    "fallback_fonts": "",
    "main_font_filename": "",
    "number_font_filename": "",
    "font_size": 28,
    "name_font_size": 28,
    "choice_font_size": 28,
    "char_width": 100,
    "char_height": 100,
    "line_spacing": 100,
    "letter_spacing": 0,
    # RPG Maker scene preview is rendered in a fixed game-screen coordinate
    # system first, then scaled as a whole in the left viewer.  The UI size must
    # never change message wrapping.
    "screen_width": 816,
    "screen_height": 624,
    "ui_area_width": 816,
    "ui_area_height": 624,
    "message_x": 0,
    "message_y": -1,  # -1 means bottom by message_height/message_margin.
    "message_width": 816,
    "message_height": 180,
    "message_margin": 0,
    "message_lines": 4,
    "message_padding": 18,
    "line_height": 36,
    "item_padding": 8,
    "box_margin": 0,
    "name_padding_x": 18,
    "name_padding_y": 8,
    "name_min_width": 96,
    "name_min_height": 54,
    "name_overlap": 0,
    "outline_width": 3,
    # Scene preview uses runtime values directly.  Kept only for old settings compatibility.
    "outline_qt_scale": 100,
    "text_color": "#FFFFFF",
    "outline_color": "#202020",
    "window_opacity": 205,
    # Explicit game settings saved by the user from the Game Settings dialog.
    # Project-open runtime refresh must not overwrite these choices with stale
    # auto-detected/default game values.
    "game_settings_user_saved": False,
    "game_settings_saved_at": "",
    "debug_overlay": False,
    "show_map_grid": False,
    "show_event_positions": False,
    "show_event_text_overlay": False,
    # 1단계 맵 프리뷰: 선택된 대사의 이벤트 주변만 잘라 보여준다.
    # 실제 타일 렌더러가 붙기 전까지는 격자/이벤트 표시만 사용한다.
    "show_local_map_preview": True,
    "show_tile_map_preview": True,
    "show_advanced_map_preview": True,
    # Debug-only.  When enabled, the map preview writes tile trace JSON and
    # raw/post PNG dumps under maker_meta for tile verification.  It is heavy
    # and must stay off during normal translation work.
    "enable_tile_validation_dump": False,
    # Import/open speed: when True, map pages first create a light placeholder
    # and render tile-heavy MV/MZ previews only when that map page is actually opened.
    "defer_tile_render": False,
    "local_map_cols": 15,
    "local_map_rows": 10,
    "show_canvas_text_overlay": False,
    # Translation/editor default: show standing/picture images fully opaque so
    # translators can read character visuals clearly.  When True, the preview
    # follows RPG Maker picture opacity commands.
    "show_picture_opacity": False,
}


@dataclass
class MakerEngineInfo:
    engine: str
    engine_label: str
    confidence: float
    project_root: str
    data_dir: str
    js_dir: str
    indicators: List[str]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_label": self.engine_label,
            "confidence": self.confidence,
            "project_root": self.project_root,
            "data_dir": self.data_dir,
            "js_dir": self.js_dir,
            "indicators": list(self.indicators),
            "warnings": list(self.warnings),
        }


def _engine_id_from_info(engine_info: MakerEngineInfo | Dict[str, Any] | None) -> str:
    try:
        if isinstance(engine_info, MakerEngineInfo):
            return normalize_engine(engine_info.engine)
        if isinstance(engine_info, dict):
            return normalize_engine(str(engine_info.get("engine") or ""))
    except Exception:
        pass
    return "unknown"


def _rel_or_name(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except Exception:
        return path.name


def _candidate_content_roots(root: Path) -> List[Path]:
    """Return likely RPG Maker MV/MZ content roots under a selected folder.

    During development the project usually has data/ and js/ directly under the
    selected folder. Deployed games can hide the same content root one or more
    levels deeper depending on platform/build style: www/, resources/app.nw/,
    resources/app/, package.nw/, or macOS .app/Contents/Resources/app.nw/.

    The editor still clones the selected game folder as-is; this function only
    finds where the Maker data actually lives inside that clone.  The scan stays
    shallow and bounded so choosing a high-level folder never turns into a whole
    drive crawl.
    """
    candidates: List[Path] = [root]

    explicit_rel_roots = (
        "www",
        "game",
        "Game",
        "app",
        "app.nw",
        "package.nw",
        "resources/app",
        "resources/app.nw",
        "Resources/app",
        "Resources/app.nw",
        "Contents/Resources/app",
        "Contents/Resources/app.nw",
    )
    for rel in explicit_rel_roots:
        p = root / rel
        if p.is_dir():
            candidates.append(p)

    # Bounded compatibility search.  This catches structures such as
    # Game.app/Contents/Resources/app.nw/data without guessing every possible
    # executable wrapper folder name.
    max_depth = 6
    max_dirs = 2500
    skip_names = {
        "node_modules", ".git", ".hg", ".svn", "__pycache__",
        "locales", "swiftshader", "shadercache", "GPUCache",
        "maker_meta", "maker_backup", "maker_diff",
    }
    try:
        stack: List[Tuple[Path, int]] = [(root, 0)]
        visited = 0
        while stack and visited < max_dirs:
            current, depth = stack.pop(0)
            visited += 1
            data_marker = current / RPG_MAKER_DATA_DIR / "MapInfos.json"
            if data_marker.is_file():
                candidates.append(current)
            if depth >= max_depth:
                continue
            try:
                children = sorted([c for c in current.iterdir() if c.is_dir()], key=lambda x: x.name.lower())
            except Exception:
                continue
            for child in children:
                if child.name in skip_names or child.name.startswith("."):
                    continue
                stack.append((child, depth + 1))
    except Exception:
        pass

    out: List[Path] = []
    seen = set()
    for c in candidates:
        try:
            key = str(c.resolve()) if c.exists() else str(c)
        except Exception:
            key = str(c)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _detect_legacy_maker_layout(root: Path) -> Tuple[str, List[str]] | None:
    """Detect older non-JSON RPG Maker layouts for clearer compatibility errors.

    쯔꾸르붕이의 현재 번역/저장 파이프라인은 MV/MZ JSON(data/MapInfos.json)
    구조를 기준으로 한다.  VX Ace/VX/XP/2000/2003 계열은 파일 형식이 달라서
    같은 루틴으로 열면 안 되므로, 최소한 사용자가 선택한 폴더가 어떤 계열로
    보이는지 알려준다.
    """
    if not root.exists() or not root.is_dir():
        return None
    markers: List[str] = []

    def note(path: Path) -> None:
        try:
            markers.append(_rel_or_name(path, root))
        except Exception:
            markers.append(str(path))

    try:
        base_candidates: List[Path] = [root, root / "Data", root / "data"]
        try:
            for child in sorted([c for c in root.iterdir() if c.is_dir()], key=lambda x: x.name.lower()):
                base_candidates.extend([child, child / "Data", child / "data"])
        except Exception:
            pass
        seen_bases = set()
        for base in base_candidates:
            try:
                base_key = str(base.resolve()) if base.exists() else str(base)
            except Exception:
                base_key = str(base)
            if base_key in seen_bases:
                continue
            seen_bases.add(base_key)
            if not base.exists():
                continue
            if list(base.glob("*.rvdata2")):
                first = sorted(base.glob("*.rvdata2"))[0]
                note(first)
                return "RPG Maker VX Ace(RGSS3 / .rvdata2)", markers
            if list(base.glob("*.rvdata")):
                first = sorted(base.glob("*.rvdata"))[0]
                note(first)
                return "RPG Maker VX(RGSS2 / .rvdata)", markers
            if list(base.glob("*.rxdata")):
                first = sorted(base.glob("*.rxdata"))[0]
                note(first)
                return "RPG Maker XP(RGSS / .rxdata)", markers
        for name in ("RPG_RT.ldb", "RPG_RT.lmt"):
            p = root / name
            if p.is_file():
                note(p)
                return "RPG Maker 2000/2003(RPG_RT)", markers
        for pattern in ("*.ldb", "*.lmt", "*.lmu"):
            found = sorted(root.glob(pattern))
            if found:
                note(found[0])
                return "RPG Maker 2000/2003(RPG_RT)", markers
        game_ini = root / "Game.ini"
        if game_ini.is_file():
            try:
                raw = game_ini.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                raw = ""
            if "RGSS" in raw or "RTP" in raw:
                note(game_ini)
                return "RPG Maker RGSS 계열(XP/VX/VX Ace 추정)", markers
    except Exception:
        return None
    return None


def _score_engine_for_root(content_root: Path, selected_root: Path) -> Tuple[str, str, float, List[str], List[str]]:
    indicators: List[str] = []
    warnings: List[str] = []
    js_dir = content_root / "js"
    data_dir = content_root / RPG_MAKER_DATA_DIR

    mv_score = 0
    mz_score = 0

    def has(rel: str) -> bool:
        return (content_root / rel).is_file()

    # The most reliable low-cost distinction in MV/MZ projects is the runtime JS
    # naming convention: MV uses rpg_*.js, MZ uses rmmz_*.js.
    for rel in (
        "js/rmmz_core.js",
        "js/rmmz_managers.js",
        "js/rmmz_objects.js",
        "js/rmmz_scenes.js",
        "js/rmmz_sprites.js",
        "js/rmmz_windows.js",
    ):
        if has(rel):
            mz_score += 3
            indicators.append(_rel_or_name(content_root / rel, selected_root))
    for rel in (
        "js/rpg_core.js",
        "js/rpg_managers.js",
        "js/rpg_objects.js",
        "js/rpg_scenes.js",
        "js/rpg_sprites.js",
        "js/rpg_windows.js",
    ):
        if has(rel):
            mv_score += 3
            indicators.append(_rel_or_name(content_root / rel, selected_root))

    # System.json exists in both, but MZ often carries an "advanced" block and
    # an editMapId/autosave-ish project structure. Treat these as weak hints only.
    system_path = data_dir / "System.json"
    if system_path.is_file():
        indicators.append(_rel_or_name(system_path, selected_root))
        try:
            system = _read_json(system_path)
            if isinstance(system, dict):
                if isinstance(system.get("advanced"), dict):
                    mz_score += 1
                    indicators.append("System.json:advanced")
                if "editMapId" in system:
                    mz_score += 1
                    indicators.append("System.json:editMapId")
                if "battleSystem" in system:
                    mz_score += 1
                    indicators.append("System.json:battleSystem")
        except Exception as e:
            warnings.append(f"System.json 판독 실패: {e}")

    if mz_score > mv_score:
        confidence = min(0.99, 0.55 + 0.06 * (mz_score - mv_score) + 0.03 * mz_score)
        return "mz", "RPG Maker MZ", round(confidence, 2), indicators, warnings
    if mv_score > mz_score:
        confidence = min(0.99, 0.55 + 0.06 * (mv_score - mz_score) + 0.03 * mv_score)
        return "mv", "RPG Maker MV", round(confidence, 2), indicators, warnings

    if (data_dir / "MapInfos.json").is_file():
        warnings.append("MV/MZ 공통 JSON 구조는 확인했지만, js/rpg_*.js 또는 js/rmmz_*.js 런타임 파일을 찾지 못해 엔진을 확정하지 못했습니다.")
        return "unknown_mv_mz", "RPG Maker MV/MZ 호환 구조(엔진 미확정)", 0.45, indicators, warnings

    return "unknown", "알 수 없음", 0.0, indicators, warnings


def detect_maker_engine(folder: str | os.PathLike[str]) -> MakerEngineInfo:
    """Auto-detect RPG Maker MV/MZ and the actual content root.

    Returns data/js paths relative to the selected folder so the cloned game can
    preserve its original layout while the parser still knows where to read.
    """
    selected_root = Path(folder).expanduser().resolve()
    if not selected_root.exists() or not selected_root.is_dir():
        raise MakerProjectError("선택한 게임 폴더를 찾을 수 없습니다.")

    best: MakerEngineInfo | None = None
    for content_root in _candidate_content_roots(selected_root):
        data_dir = content_root / RPG_MAKER_DATA_DIR
        if not (data_dir / "MapInfos.json").is_file():
            continue
        engine, label, confidence, indicators, warnings = _score_engine_for_root(content_root, selected_root)
        info = MakerEngineInfo(
            engine=engine,
            engine_label=label,
            confidence=confidence,
            project_root=_rel_or_name(content_root, selected_root),
            data_dir=_rel_or_name(data_dir, selected_root),
            js_dir=_rel_or_name(content_root / "js", selected_root),
            indicators=indicators,
            warnings=warnings,
        )
        if best is None or info.confidence > best.confidence:
            best = info

    if best is None:
        legacy = _detect_legacy_maker_layout(selected_root)
        if legacy is not None:
            legacy_label, legacy_markers = legacy
            marker_text = ", ".join(legacy_markers[:3]) if legacy_markers else "구버전 데이터 파일"
            raise MakerProjectError(
                f"{legacy_label} 구조로 보입니다. 감지 파일: {marker_text}. "
                "현재 쯔꾸르붕이는 RPG Maker MV/MZ의 JSON 구조(data/MapInfos.json)를 기준으로 가져옵니다. "
                "VX Ace/VX/XP/2000/2003 계열은 별도 변환/전용 지원이 필요합니다."
            )
        raise MakerProjectError(
            "RPG Maker MV/MZ 프로젝트로 보이지 않습니다. "
            "data/MapInfos.json, www/data/MapInfos.json, resources/app.nw/data/MapInfos.json, "
            "또는 macOS .app/Contents/Resources/app.nw/data/MapInfos.json이 있는 폴더를 선택해 주세요."
        )
    return best


def _data_dir_from_engine_info(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Path:
    root = Path(game_root)
    if isinstance(engine_info, MakerEngineInfo):
        rel = engine_info.data_dir
    elif isinstance(engine_info, dict):
        rel = str(engine_info.get("data_dir") or RPG_MAKER_DATA_DIR)
    else:
        rel = detect_maker_engine(root).data_dir
    return root / rel





def _maker_system_json_from_game(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Dict[str, Any]:
    try:
        data_dir = _data_dir_from_engine_info(game_root, engine_info)
        path = data_dir / "System.json"
        if path.is_file():
            obj = _read_json(path)
            if isinstance(obj, dict):
                return obj
    except Exception:
        pass
    return {}



def _content_root_from_engine_info(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Path:
    root = Path(game_root)
    rel = "."
    try:
        if isinstance(engine_info, MakerEngineInfo):
            rel = engine_info.project_root or "."
        elif isinstance(engine_info, dict):
            rel = str(engine_info.get("project_root") or ".")
        else:
            rel = detect_maker_engine(root).project_root or "."
    except Exception:
        rel = "."
    if rel in {"", "."}:
        return root
    return root / rel


def _js_dir_from_engine_info(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Path:
    root = Path(game_root)
    rel = "js"
    try:
        if isinstance(engine_info, MakerEngineInfo):
            rel = engine_info.js_dir or "js"
        elif isinstance(engine_info, dict):
            rel = str(engine_info.get("js_dir") or "js")
        else:
            rel = detect_maker_engine(root).js_dir or "js"
    except Exception:
        rel = "js"
    return root / rel


def _project_rel_path(path: Path, project_dir: Path | None = None) -> str:
    try:
        if project_dir is not None:
            return str(path.resolve().relative_to(project_dir.resolve())).replace("\\", "/")
    except Exception:
        pass
    return str(path).replace("\\", "/")

def _maker_font_cache_dir(project_dir: Path | None) -> Path | None:
    try:
        if project_dir is None:
            return None
        d = Path(project_dir) / MAKER_META_DIR / MAKER_FONT_CACHE_DIR
        d.mkdir(parents=True, exist_ok=True)
        try:
            (d / MAKER_KEEP_FILE).write_text("keep\n", encoding="utf-8")
        except Exception:
            pass
        return d
    except Exception:
        return None


def _json_diag_safe(value: Any) -> Any:
    try:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(k): _json_diag_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_diag_safe(v) for v in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)
    except Exception:
        return str(value)


def append_maker_preview_diagnostic(project_dir: str | os.PathLike[str] | Path | None, event: str, payload: Dict[str, Any] | None = None) -> None:
    """Append Maker preview/runtime diagnostics without ever breaking editing.

    The left preview is now a game-screen renderer, so when a game does not look
    like the real RPG Maker window we need to know the exact data used to build
    it: runtime profile, font conversion result, QFont load result, message window
    geometry and wrapping metrics.  This writes both an append-only jsonl log and
    a last-snapshot json for quick inspection.
    """
    try:
        if not project_dir:
            return
        base = Path(project_dir)
        meta_dir = base / MAKER_META_DIR
        meta_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "event": str(event or "unknown"),
            "payload": _json_diag_safe(payload or {}),
        }
        log_path = meta_dir / MAKER_PREVIEW_DIAGNOSTICS_FILE
        try:
            if log_path.exists() and log_path.stat().st_size > 2_000_000:
                old_path = meta_dir / (MAKER_PREVIEW_DIAGNOSTICS_FILE + ".old")
                try:
                    if old_path.exists():
                        old_path.unlink()
                except Exception:
                    pass
                try:
                    log_path.replace(old_path)
                except Exception:
                    pass
        except Exception:
            pass
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        try:
            with (meta_dir / MAKER_PREVIEW_DIAGNOSTICS_LAST_FILE).open("w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass
    except Exception:
        return


def _maker_qt_compatible_font_path(font_path: Path, project_dir: Path | None = None) -> Dict[str, Any]:
    """Return a Qt-loadable font path, caching by file fingerprint.

    Qt/PyQt keeps application fonts in process-level caches.  If a user replaces
    a game font file while the editor is open, loading the same path again can
    keep using the old face until restart.  Therefore all project fonts are
    loaded through maker_meta/font_cache with a size/mtime fingerprint in the
    file name.  TTF/OTF/TTC are copied as-is; WOFF/WOFF2 are converted to SFNT
    when possible.  The original game font is never modified.
    """
    out: Dict[str, Any] = {
        "input_path": str(font_path or ""),
        "output_path": str(font_path or ""),
        "converted": False,
        "copied": False,
        "format": "",
        "error": "",
    }
    try:
        src = Path(font_path)
        suffix = src.suffix.lower()
        out["format"] = suffix.lstrip(".")
        if suffix not in {".ttf", ".otf", ".ttc", ".woff", ".woff2"}:
            append_maker_preview_diagnostic(project_dir, "font_cache_not_supported", out)
            return out
        if not src.is_file():
            out["error"] = "source_missing"
            append_maker_preview_diagnostic(project_dir, "font_cache_prepare_failed", out)
            return out
        cache_dir = _maker_font_cache_dir(project_dir)
        if cache_dir is None:
            out["error"] = "cache_dir_unavailable"
            append_maker_preview_diagnostic(project_dir, "font_cache_prepare_failed", out)
            return out
        try:
            stat = src.stat()
            mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
            digest_src = f"{src.resolve()}|{stat.st_size}|{mtime_ns}"
        except Exception:
            digest_src = str(src.resolve())
        digest = hashlib.sha1(digest_src.encode("utf-8", errors="ignore")).hexdigest()[:12]

        if suffix in {".ttf", ".otf", ".ttc"}:
            target = cache_dir / f"{src.stem}_{digest}{suffix}"
            out["output_path"] = str(target)
            try:
                append_maker_preview_diagnostic(project_dir, "font_cache_copy_start", out)
                if not target.is_file() or target.stat().st_size <= 0:
                    shutil.copy2(str(src), str(target))
                out["output_path"] = str(target.resolve())
                out["copied"] = True
                append_maker_preview_diagnostic(project_dir, "font_cache_copy_success", out)
            except Exception as e:
                out["error"] = f"font_cache_copy_failed: {e}"
                append_maker_preview_diagnostic(project_dir, "font_cache_prepare_failed", out)
                return out
            return out

        append_maker_preview_diagnostic(project_dir, "font_cache_convert_start", out)
        target = cache_dir / f"{src.stem}_{digest}.ttf"
        out["output_path"] = str(target)
        if not target.is_file() or target.stat().st_size <= 0:
            try:
                import importlib.util as _importlib_util
                out["fonttools_available"] = _importlib_util.find_spec("fontTools") is not None
                out["brotli_available"] = _importlib_util.find_spec("brotli") is not None
            except Exception:
                out["fonttools_available"] = False
                out["brotli_available"] = False
            try:
                from fontTools.ttLib import TTFont  # type: ignore
                font = TTFont(str(src))
                font.flavor = None
                font.save(str(target))
            except Exception as e:
                out["error"] = f"fonttools_convert_failed: {e}"
                append_maker_preview_diagnostic(project_dir, "font_cache_prepare_failed", out)
                return out
        out["output_path"] = str(target.resolve())
        out["converted"] = True
        append_maker_preview_diagnostic(project_dir, "font_cache_convert_success", out)
        return out
    except Exception as e:
        out["error"] = f"unexpected: {e}"
        append_maker_preview_diagnostic(project_dir, "font_cache_prepare_failed", out)
        return out


def _parse_css_first_font_face(css_path: Path) -> Dict[str, Any]:
    """Read a Maker gamefont.css and return the first @font-face hint.

    RPG Maker MV/MZ commonly ships a fonts/gamefont.css file.  The editor should
    not invent a font when the game already declares one.  This parser is small
    on purpose: it extracts font-family and the first url(...) source without
    trying to become a full CSS engine.
    """
    out: Dict[str, Any] = {}
    try:
        css = css_path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return out
    try:
        fam_m = re.search(r"font-family\s*:\s*['\"]?([^;'\"}]+)", css, re.I)
        if fam_m:
            out["font_family"] = fam_m.group(1).strip()
    except Exception:
        pass
    try:
        url_m = re.search(r"url\((['\"]?)([^)'\"]+)\1\)", css, re.I)
        if url_m:
            raw = url_m.group(2).strip()
            raw = raw.replace("%20", " ")
            out["font_src"] = raw
            font_path = (css_path.parent / raw).resolve()
            if font_path.is_file():
                out["font_path"] = str(font_path)
    except Exception:
        pass
    return out


def _maker_font_search_dirs(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> List[Path]:
    """Return likely content/font roots for MV/MZ projects and deployments."""
    root = Path(game_root)
    try:
        content_root = _content_root_from_engine_info(root, engine_info)
    except Exception:
        content_root = root
    dirs: List[Path] = []
    for base in (content_root, root, root / "www"):
        if not isinstance(base, Path):
            continue
        for rel in ("fonts", "Fonts", "."):
            d = base / rel
            if d not in dirs:
                dirs.append(d)
    return dirs


def _find_maker_font_file(game_root: str | os.PathLike[str], filename: str, engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Path | None:
    """Find a specific font file named by System.json advanced.*FontFilename."""
    name = str(filename or "").strip().strip("/\\")
    if not name:
        return None
    # Guard against odd paths while still allowing subfolders under fonts.
    name = name.replace("\\", "/")
    for d in _maker_font_search_dirs(game_root, engine_info):
        try:
            p = (d / name).resolve()
            if p.is_file():
                return p
        except Exception:
            pass
        try:
            p = (d / Path(name).name).resolve()
            if p.is_file():
                return p
        except Exception:
            pass
    return None


def _collect_maker_font_files(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> List[Path]:
    exts = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}
    seen: set[str] = set()
    out: List[Path] = []
    for d in _maker_font_search_dirs(game_root, engine_info):
        try:
            if d.is_dir():
                for p in sorted(d.iterdir()):
                    if p.is_file() and p.suffix.lower() in exts:
                        key = str(p.resolve())
                        if key not in seen:
                            seen.add(key)
                            out.append(p)
        except Exception:
            pass
    return out


def _detect_maker_font_profile(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None, project_dir: str | os.PathLike[str] | None = None, system: Dict[str, Any] | None = None) -> Dict[str, Any]:
    root = Path(game_root)
    content_root = _content_root_from_engine_info(root, engine_info)
    candidates: List[Path] = []
    for base in (content_root, root, root / "www"):
        if not isinstance(base, Path):
            continue
        for rel in ("fonts/gamefont.css", "Fonts/gamefont.css", "gamefont.css"):
            p = base / rel
            if p.is_file() and p not in candidates:
                candidates.append(p)
    profile: Dict[str, Any] = {
        "source": "default",
        "font_family": "",
        "font_path": "",
        "css_path": "",
        "candidates": [],
        "main_font_filename": "",
        "number_font_filename": "",
        "fallback_fonts": "",
    }
    project_root = Path(project_dir) if project_dir else None
    engine_id = _engine_id_from_info(engine_info)
    adapter = get_engine_adapter(engine_id)
    profile["engine"] = adapter.engine
    profile["runtime_module"] = adapter.runtime_module
    profile["font_priority"] = adapter.font_priority

    # MZ stores the actual runtime font filenames in data/System.json > advanced.
    # These values must win over the older MV-style gamefont.css heuristic.
    # MV must remain CSS-first because many MV titles use fonts/gamefont.css.
    sys_obj = system if isinstance(system, dict) else _maker_system_json_from_game(root, engine_info)
    adv = sys_obj.get("advanced") if isinstance(sys_obj.get("advanced"), dict) else {}
    main_font_filename = str((adv or {}).get("mainFontFilename") or "").strip()
    number_font_filename = str((adv or {}).get("numberFontFilename") or "").strip()
    fallback_fonts = str((adv or {}).get("fallbackFonts") or "").strip()
    if engine_id == "mz" and main_font_filename:
        main_font_file = _find_maker_font_file(root, main_font_filename, engine_info)
        profile["source"] = "System.json advanced.mainFontFilename" if main_font_file else "System.json advanced.mainFontFilename_missing"
        profile["main_font_filename"] = main_font_filename
        profile["number_font_filename"] = number_font_filename
        profile["fallback_fonts"] = fallback_fonts
        profile["font_family"] = Path(main_font_filename).stem
        if main_font_file is not None:
            qt_font = _maker_qt_compatible_font_path(main_font_file, project_root)
            qt_path = Path(str(qt_font.get("output_path") or main_font_file))
            profile["source_font_path"] = _project_rel_path(main_font_file, project_root)
            profile["font_path"] = _project_rel_path(qt_path, project_root)
            profile["font_format"] = str(qt_font.get("format") or main_font_file.suffix.lstrip("."))
            profile["font_converted_for_qt"] = bool(qt_font.get("converted"))
            if qt_font.get("error"):
                profile["font_conversion_error"] = str(qt_font.get("error") or "")
        # Attach CSS hints as auxiliary data only; do not let CSS override the MZ
        # explicit System.json font filename.
        for css_path in candidates:
            hint = _parse_css_first_font_face(css_path)
            if hint:
                profile["css_path"] = _project_rel_path(css_path, project_root)
                profile["css_font_family"] = str(hint.get("font_family") or "").strip()
                profile["raw_src"] = str(hint.get("font_src") or "")
                break
        font_files = _collect_maker_font_files(root, engine_info)
        if font_files:
            profile["candidates"] = [_project_rel_path(p, project_root) for p in font_files[:30]]
        return profile

    for css_path in candidates:
        hint = _parse_css_first_font_face(css_path)
        if hint:
            profile["source"] = "gamefont.css"
            profile["css_path"] = _project_rel_path(css_path, project_root)
            profile["font_family"] = str(hint.get("font_family") or "").strip()
            font_path = str(hint.get("font_path") or "").strip()
            if font_path:
                src_font = Path(font_path)
                qt_font = _maker_qt_compatible_font_path(src_font, project_root)
                qt_path = Path(str(qt_font.get("output_path") or src_font))
                profile["source_font_path"] = _project_rel_path(src_font, project_root)
                profile["font_path"] = _project_rel_path(qt_path, project_root)
                profile["font_format"] = str(qt_font.get("format") or src_font.suffix.lstrip("."))
                profile["font_converted_for_qt"] = bool(qt_font.get("converted"))
                if qt_font.get("error"):
                    profile["font_conversion_error"] = str(qt_font.get("error") or "")
            profile["raw_src"] = str(hint.get("font_src") or "")
            return profile
    # No CSS, so collect font files as a fallback candidate list.
    font_files = _collect_maker_font_files(root, engine_info)
    if font_files:
        first = font_files[0]
        profile["source"] = "fonts_folder"
        profile["font_family"] = first.stem
        qt_font = _maker_qt_compatible_font_path(first, project_root)
        qt_path = Path(str(qt_font.get("output_path") or first))
        profile["source_font_path"] = _project_rel_path(first, project_root)
        profile["font_path"] = _project_rel_path(qt_path, project_root)
        profile["font_format"] = str(qt_font.get("format") or first.suffix.lstrip("."))
        profile["font_converted_for_qt"] = bool(qt_font.get("converted"))
        if qt_font.get("error"):
            profile["font_conversion_error"] = str(qt_font.get("error") or "")
        profile["candidates"] = [_project_rel_path(p, project_root) for p in font_files[:20]]
    return profile


def _read_text_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""



def _dict_items(value: Any):
    return value.items() if isinstance(value, dict) else ()

def _detect_engine_window_defaults(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return engine-specific message-window defaults and JS-derived hints.

    MV and MZ intentionally go through separate adapters.  Do not let MZ
    Window_NameBox/font formulas bleed into MV; MV often depends on plugins for
    names, while MZ has native name-window data in Show Text parameter[4].
    """
    engine = _engine_id_from_info(engine_info)
    adapter = get_engine_adapter(engine)
    defaults: Dict[str, Any] = dict(adapter.runtime_defaults())
    defaults["engine"] = adapter.engine
    defaults["runtime_module"] = adapter.runtime_module
    defaults["engine_module"] = adapter.metadata()
    try:
        js_dir = _js_dir_from_engine_info(game_root, engine_info)
        windows_js = js_dir / adapter.windows_js_name
        text = _read_text_file_safe(windows_js)
        # Literal lineHeight() { return 36; } / standardFontSize() { return 28; }
        m = re.search(r"lineHeight\s*\([^)]*\)\s*\{[^{}]*return\s+(\d+)", text)
        if m:
            defaults["line_height"] = int(m.group(1))
        m = re.search(r"standardFontSize\s*\([^)]*\)\s*\{[^{}]*return\s+(\d+)", text)
        if m:
            defaults["font_size"] = defaults["name_font_size"] = defaults["choice_font_size"] = int(m.group(1))
        m = re.search(r"standardPadding\s*\([^)]*\)\s*\{[^{}]*return\s+(\d+)", text)
        if m:
            defaults["window_padding"] = int(m.group(1))
        defaults["windows_js"] = _rel_or_name(windows_js, Path(game_root))
    except Exception as e:
        defaults["windows_js_error"] = str(e)
    return defaults


def maker_runtime_profile_path(project_dir: str | os.PathLike[str]) -> Path:
    return Path(project_dir) / MAKER_META_DIR / MAKER_RUNTIME_PROFILE_FILE


def load_maker_runtime_profile(project_dir: str | os.PathLike[str] | None) -> Dict[str, Any]:
    if not project_dir:
        return {}
    path = maker_runtime_profile_path(project_dir)
    try:
        if path.exists():
            obj = _read_json(path)
            return dict(obj) if isinstance(obj, dict) else {}
    except Exception:
        pass
    return {}


def save_maker_runtime_profile(project_dir: str | os.PathLike[str], profile: Dict[str, Any]) -> Dict[str, Any]:
    fixed = dict(profile or {})
    path = maker_runtime_profile_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)
    return fixed




def _detect_mv_plugin_screen_metrics(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Dict[str, int]:
    """Read MV screen size from enabled plugins.js when possible.

    MV projects often keep the default 816x624, but many deployed games change it
    through Community_Basic or compatible plugins.  MZ has System.json advanced;
    MV usually needs this plugins.js pass.
    """
    out: Dict[str, int] = {}
    try:
        root = Path(game_root)
        content_root = _content_root_from_engine_info(root, engine_info)
        plugins_path = content_root / "js" / "plugins.js"
        if not plugins_path.is_file():
            plugins_path = root / "js" / "plugins.js"
        if not plugins_path.is_file():
            return out
        text = _read_text_file_safe(plugins_path)
        m = re.search(r"var\s+\$plugins\s*=\s*(\[.*?\])\s*;", text, re.S)
        if not m:
            return out
        arr = json.loads(m.group(1))
        if not isinstance(arr, list):
            return out
        for plug in arr:
            if not isinstance(plug, dict) or not plug.get("status", False):
                continue
            name = str(plug.get("name") or "").strip().lower()
            params = plug.get("parameters") if isinstance(plug.get("parameters"), dict) else {}
            if name in {"community_basic", "communitybasic"} or any(str(k).lower() in {"screenwidth", "screenheight"} for k in params.keys()):
                for key, dst in (("screenWidth", "width"), ("screenHeight", "height"), ("screen width", "width"), ("screen height", "height")):
                    for pk, pv in params.items():
                        if str(pk).strip().lower() == key.lower():
                            try:
                                iv = int(float(str(pv).strip()))
                                if iv > 0:
                                    out[dst] = iv
                            except Exception:
                                pass
                if out:
                    return out
    except Exception:
        return out
    return out

def build_maker_runtime_profile(project_dir: str | os.PathLike[str], game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Create the game-derived display profile used by Maker scene preview.

    The editor should not freely invent message-window metrics.  This profile
    gathers values from the game's JSON, resource files, and MV/MZ runtime
    defaults first; user settings can then override the profile later.
    """
    project_dir_p = Path(project_dir)
    root = Path(game_root)
    if engine_info is None:
        try:
            engine_info = detect_maker_engine(root)
        except Exception:
            engine_info = None
    engine_dict = engine_info.to_dict() if isinstance(engine_info, MakerEngineInfo) else dict(engine_info or {})
    engine = normalize_engine(str(engine_dict.get("engine") or "unknown"))
    adapter = get_engine_adapter(engine)
    system = _maker_system_json_from_game(root, engine_info)
    adv = system.get("advanced") if isinstance(system.get("advanced"), dict) else {}

    def pick_int(default: int, *keys) -> int:
        for key in keys:
            try:
                if isinstance(key, tuple):
                    obj, name = key
                    val = obj.get(name) if isinstance(obj, dict) else None
                else:
                    val = system.get(key) if isinstance(system, dict) else None
                if val is not None and str(val).strip() != "":
                    iv = int(round(float(val)))
                    if iv > 0:
                        return iv
            except Exception:
                continue
        return int(default)

    default_sw = 816
    default_sh = 624
    mv_plugin_screen = _detect_mv_plugin_screen_metrics(root, engine_info) if engine == "mv" else {}
    sw = pick_int(default_sw, (adv, "screenWidth"), (adv, "uiAreaWidth"), "screenWidth", "uiAreaWidth", (mv_plugin_screen, "width"))
    sh = pick_int(default_sh, (adv, "screenHeight"), (adv, "uiAreaHeight"), "screenHeight", "uiAreaHeight", (mv_plugin_screen, "height"))
    uiw = pick_int(sw, (adv, "uiAreaWidth"), "uiAreaWidth", (adv, "screenWidth"), "screenWidth", (mv_plugin_screen, "width"))
    uih = pick_int(sh, (adv, "uiAreaHeight"), "uiAreaHeight", (adv, "screenHeight"), "screenHeight", (mv_plugin_screen, "height"))
    runtime_defaults = _detect_engine_window_defaults(root, engine_info)
    font_profile = _detect_maker_font_profile(root, engine_info, project_dir=project_dir_p, system=system)
    font_size = pick_int(int(runtime_defaults.get("font_size") or 28), (adv, "fontSize"), "fontSize")
    window_opacity = pick_int(int(runtime_defaults.get("window_opacity") or 205), (adv, "windowOpacity"), "windowOpacity")
    line_h = int(runtime_defaults.get("line_height") or 36)
    padding = int(runtime_defaults.get("window_padding") or 18)
    rows = int(runtime_defaults.get("message_lines") or 4)
    message_h = max(80, int(line_h * rows + padding * 2 + int(runtime_defaults.get("message_height_extra") or 0)))
    box_margin = int(runtime_defaults.get("box_margin") or 0)
    # Use MZ/MV Graphics.boxWidth-like width when a runtime box margin exists.
    message_w = int(max(120, (uiw or sw) - box_margin * 2))
    window_skin = ""
    try:
        content_root = _content_root_from_engine_info(root, engine_info)
        p = content_root / "img" / "system" / "Window.png"
        if not p.is_file():
            p = root / "img" / "system" / "Window.png"
        if p.is_file():
            window_skin = _project_rel_path(p, project_dir_p)
    except Exception:
        pass
    profile: Dict[str, Any] = {
        "version": 1,
        "source": "game_data_and_runtime_defaults",
        "engine": engine,
        "engine_label": engine_dict.get("engine_label") or adapter.engine_label or "RPG Maker",
        "runtime_module": adapter.runtime_module,
        "engine_module": adapter.metadata(),
        "screen": {
            "width": max(320, min(4096, int(sw))),
            "height": max(240, min(2160, int(sh))),
            "ui_area_width": max(320, min(4096, int(uiw))),
            "ui_area_height": max(240, min(2160, int(uih))),
            "source": "System.json advanced" if isinstance(adv, dict) and adv else ("MV plugins.js" if mv_plugin_screen else "engine_default"),
        },
        "font": {
            "family": font_profile.get("font_family") or adapter.default_font_family,
            "path": font_profile.get("font_path") or "",
            "source_font_path": font_profile.get("source_font_path") or "",
            "format": font_profile.get("font_format") or "",
            "converted_for_qt": bool(font_profile.get("font_converted_for_qt")),
            "conversion_error": font_profile.get("font_conversion_error") or "",
            "source": font_profile.get("source") or "default",
            "css_path": font_profile.get("css_path") or "",
            "css_font_family": font_profile.get("css_font_family") or "",
            "candidates": font_profile.get("candidates") or [],
            "main_font_filename": font_profile.get("main_font_filename") or str((adv or {}).get("mainFontFilename") or ""),
            "number_font_filename": font_profile.get("number_font_filename") or str((adv or {}).get("numberFontFilename") or ""),
            "fallback_fonts": font_profile.get("fallback_fonts") or str((adv or {}).get("fallbackFonts") or ""),
            "size": int(font_size),
            "outline_width": int(runtime_defaults.get("outline_width") or 3),
        },
        "window": {
            "skin": window_skin,
            "padding": int(padding),
            "item_padding": int(runtime_defaults.get("item_padding") or 8),
            "text_padding": int(runtime_defaults.get("text_padding") or 6),
            "opacity": int(window_opacity),
            "source": ("System.json advanced.windowOpacity" if isinstance(adv, dict) and adv.get("windowOpacity") is not None else (runtime_defaults.get("source") or "engine_defaults")),
        },
        "message_window": {
            "x": int(runtime_defaults.get("message_x") or 0),
            "y": -1,
            "width": int(message_w),
            "height": int(message_h),
            "rows": int(rows),
            "line_height": int(line_h),
            "margin": int(runtime_defaults.get("message_margin") or 0),
            "box_margin": int(runtime_defaults.get("box_margin") or 0),
        },
        "name_window": {
            "padding_x": int(runtime_defaults.get("name_padding_x") or 18),
            "padding_y": int(runtime_defaults.get("name_padding_y") or 8),
            "min_width": int(runtime_defaults.get("name_min_width") or 96),
            "min_height": int(runtime_defaults.get("name_min_height") or 54),
            "overlap": int(runtime_defaults.get("name_overlap") or 0),
        },
        "notes": [
            "Values are read from System.json advanced, MV plugins.js, fonts/gamefont.css, img/system/Window.png when available, then filled with MV/MZ runtime defaults.",
            "Scene preview should follow runtime profile values directly; editor correction values are ignored for Window_Message reproduction.",
        ],
    }
    saved_profile = save_maker_runtime_profile(project_dir_p, profile)
    try:
        append_maker_preview_diagnostic(project_dir_p, "runtime_profile_built", {
            "engine": engine,
            "system_advanced": adv if isinstance(adv, dict) else {},
            "font_profile": font_profile,
            "runtime_defaults": runtime_defaults,
            "engine_module": adapter.metadata(),
            "saved_profile": saved_profile,
        })
    except Exception:
        pass
    return saved_profile


def maker_preview_settings_from_runtime_profile(profile: Dict[str, Any], base_settings: Dict[str, Any] | None = None, *, preserve_user_game_settings: bool = True) -> Dict[str, Any]:
    """Convert runtime profile to existing preview settings schema.

    Runtime profile refresh is useful for first import and manual re-detection,
    but after the user changes Game Settings the saved font choices become the
    editor's source of truth.  Otherwise project-open refresh can read an older
    System.json/CSS/default profile and overwrite the saved combo values, making
    the font appear reset after restart.
    """
    base_settings = dict(base_settings or {})
    st = dict(base_settings)
    profile = dict(profile or {})
    screen = profile.get("screen") if isinstance(profile.get("screen"), dict) else {}
    font = profile.get("font") if isinstance(profile.get("font"), dict) else {}
    win = profile.get("window") if isinstance(profile.get("window"), dict) else {}
    msg = profile.get("message_window") if isinstance(profile.get("message_window"), dict) else {}
    name = profile.get("name_window") if isinstance(profile.get("name_window"), dict) else {}
    for dst, src, default in (
        ("screen_width", "width", 816),
        ("screen_height", "height", 624),
        ("ui_area_width", "ui_area_width", None),
        ("ui_area_height", "ui_area_height", None),
    ):
        val = screen.get(src)
        if val is None:
            val = default
        if val is not None:
            st[dst] = val
    if font.get("family"):
        st["font_family"] = str(font.get("family"))
    if font.get("path"):
        st["font_path"] = str(font.get("path"))
    if font.get("fallback_fonts"):
        st["fallback_fonts"] = str(font.get("fallback_fonts"))
    if font.get("main_font_filename"):
        st["main_font_filename"] = str(font.get("main_font_filename"))
    if font.get("number_font_filename"):
        st["number_font_filename"] = str(font.get("number_font_filename"))
    if font.get("size"):
        st["font_size"] = int(font.get("size") or 28)
        st["name_font_size"] = int(font.get("size") or 28)
        st["choice_font_size"] = int(font.get("size") or 28)
    if font.get("outline_width") is not None:
        st["outline_width"] = int(font.get("outline_width") or 0)
    if win.get("padding") is not None:
        st["message_padding"] = int(win.get("padding") or 0)
    if win.get("item_padding") is not None:
        st["item_padding"] = int(win.get("item_padding") or 0)
    if win.get("opacity") is not None:
        st["window_opacity"] = int(win.get("opacity") or 205)
    for dst, src in (("message_x", "x"), ("message_y", "y"), ("message_width", "width"), ("message_height", "height"), ("message_lines", "rows"), ("message_margin", "margin"), ("box_margin", "box_margin"), ("line_height", "line_height")):
        if msg.get(src) is not None:
            st[dst] = int(msg.get(src) or 0)
    for dst, src in (("name_padding_x", "padding_x"), ("name_padding_y", "padding_y"), ("name_min_width", "min_width"), ("name_min_height", "min_height"), ("name_overlap", "overlap")):
        if name.get(src) is not None:
            st[dst] = int(name.get(src) or 0)

    if preserve_user_game_settings and bool(base_settings.get("game_settings_user_saved")):
        for key in (
            "main_font_filename",
            "number_font_filename",
            "fallback_fonts",
            "font_family",
            "font_path",
            "main_font_fingerprint",
            "number_font_fingerprint",
            "font_size",
            "line_height",
            "message_padding",
            "window_opacity",
            "game_settings_user_saved",
            "game_settings_saved_at",
        ):
            if key in base_settings:
                st[key] = base_settings.get(key)
    return normalize_maker_preview_settings(st)

def detect_maker_screen_preview_settings(game_root: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None, base_settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Merge game-derived runtime display values into preview settings.

    Kept for backward compatibility.  New imports call build_maker_runtime_profile
    from build_maker_pages so the profile is also persisted to maker_meta.
    """
    try:
        # If no project dir is available, build a transient profile in memory.
        tmp_project = Path(game_root)
        profile = build_maker_runtime_profile(tmp_project, game_root, engine_info)
        return maker_preview_settings_from_runtime_profile(profile, base_settings)
    except Exception:
        st = normalize_maker_preview_settings(base_settings)
        system = _maker_system_json_from_game(game_root, engine_info)
        adv = system.get("advanced") if isinstance(system.get("advanced"), dict) else {}
        def pick_int(*keys, default=0):
            for key in keys:
                try:
                    if isinstance(key, tuple):
                        obj, name = key
                        val = obj.get(name) if isinstance(obj, dict) else None
                    else:
                        val = system.get(key) if isinstance(system, dict) else None
                    if val is not None and str(val).strip() != "":
                        iv = int(round(float(val)))
                        if iv > 0:
                            return iv
                except Exception:
                    continue
            return int(default or 0)
        sw = pick_int((adv, "screenWidth"), (adv, "uiAreaWidth"), "screenWidth", "uiAreaWidth", default=0)
        sh = pick_int((adv, "screenHeight"), (adv, "uiAreaHeight"), "screenHeight", "uiAreaHeight", default=0)
        if sw >= 320 and sh >= 240:
            st["screen_width"] = max(320, min(4096, int(sw)))
            st["screen_height"] = max(240, min(2160, int(sh)))
            st["message_width"] = int(st["screen_width"])
            st["message_x"] = 0
            st["message_y"] = -1
        return normalize_maker_preview_settings(st)

def _clamp_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        v = int(round(float(value)))
    except Exception:
        v = int(default)
    return max(int(lo), min(int(hi), v))


def _clean_hex_color(value: Any, default: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
        return text.upper()
    return str(default)



def normalize_maker_translation_settings(settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return safe project-level RPG Maker AI translation settings."""
    raw = dict(settings or {}) if isinstance(settings, dict) else {}
    out = dict(DEFAULT_MAKER_TRANSLATION_SETTINGS)
    out["normalize_source_newlines"] = bool(raw.get("normalize_source_newlines", out["normalize_source_newlines"]))
    mode = str(raw.get("newline_join_mode") or out["newline_join_mode"]).strip().lower()
    if mode not in {"auto", "cjk_join", "space"}:
        mode = "auto"
    out["newline_join_mode"] = mode
    return out


def maker_translation_settings_path(project_dir: str | os.PathLike[str]) -> Path:
    return Path(project_dir) / MAKER_META_DIR / MAKER_TRANSLATION_SETTINGS_FILE


def load_maker_translation_settings(project_dir: str | os.PathLike[str] | None) -> Dict[str, Any]:
    if not project_dir:
        return normalize_maker_translation_settings()
    path = maker_translation_settings_path(project_dir)
    try:
        if path.exists():
            return normalize_maker_translation_settings(_read_json(path))
    except Exception:
        pass
    return normalize_maker_translation_settings()


def save_maker_translation_settings(project_dir: str | os.PathLike[str], settings: Dict[str, Any]) -> Dict[str, Any]:
    fixed = normalize_maker_translation_settings(settings)
    path = maker_translation_settings_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)
    return fixed


def _maker_is_cjk_char(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (
        0x3040 <= code <= 0x30FF  # Hiragana/Katakana
        or 0x3400 <= code <= 0x9FFF  # CJK ideographs
        or 0xAC00 <= code <= 0xD7AF  # Hangul syllables
        or 0x1100 <= code <= 0x11FF  # Hangul jamo
        or 0xFF00 <= code <= 0xFFEF  # full-width forms
    )


def _maker_needs_join_space(left: str, right: str, mode: str) -> bool:
    if not left or not right:
        return False
    if mode == "cjk_join":
        return False
    if mode == "space":
        return True
    # auto: CJK-to-CJK should be joined directly; Latin/numeric word fragments
    # need a space so English and code-like text do not merge into one token.
    if _maker_is_cjk_char(left) and _maker_is_cjk_char(right):
        return False
    if left in "([{「『（【《〈“‘\"'" or right in ")]},.!?:;」』）】》〉”’\"'、。！？…":
        return False
    if left.isspace() or right.isspace():
        return False
    try:
        left_word = left.isascii() and (left.isalnum() or left == "_")
        right_word = right.isascii() and (right.isalnum() or right == "_")
    except Exception:
        left_word = right_word = False
    return bool(left_word and right_word)


def normalize_maker_translation_source_text(text: Any, settings: Dict[str, Any] | None = None) -> str:
    """Normalize text only for AI translation input, without changing project data.

    RPG Maker dialogue is often stored as multiple 401/405 command lines. Sending
    those raw line breaks to AI translation can reduce quality, so this function
    joins ordinary line breaks while keeping paragraph blanks readable. The
    original item text, preview text, and write-back data are not modified.
    """
    src = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    st = normalize_maker_translation_settings(settings)
    if not st.get("normalize_source_newlines", False):
        return src
    mode = str(st.get("newline_join_mode") or "auto")
    lines = src.split("\n")
    out = ""
    previous_blank = False
    for raw_line in lines:
        line = raw_line.strip()
        if line == "":
            # Preserve a paragraph break in a compact form; most RPG Maker dialogue
            # lines do not intentionally use blank paragraphs, but if they do, keep
            # a visible separation for the translator.
            if out and not previous_blank:
                out = out.rstrip() + "\n"
            previous_blank = True
            continue
        if not out or out.endswith("\n"):
            out += line
        else:
            left = out[-1]
            right = line[0]
            out += (" " if _maker_needs_join_space(left, right, mode) else "") + line
        previous_blank = False
    return out.strip()


def normalize_maker_preview_settings(settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return safe project-level RPG Maker preview font settings."""
    raw = dict(settings or {}) if isinstance(settings, dict) else {}
    base = dict(DEFAULT_MAKER_PREVIEW_SETTINGS)
    base.update(raw)
    out = dict(DEFAULT_MAKER_PREVIEW_SETTINGS)
    out["font_family"] = str(base.get("font_family") or DEFAULT_MAKER_PREVIEW_SETTINGS["font_family"]).strip() or DEFAULT_MAKER_PREVIEW_SETTINGS["font_family"]
    out["font_path"] = str(base.get("font_path") or "").strip()
    out["fallback_fonts"] = str(base.get("fallback_fonts") or "").strip()
    out["main_font_filename"] = str(base.get("main_font_filename") or "").strip()
    out["number_font_filename"] = str(base.get("number_font_filename") or "").strip()
    out["font_size"] = _clamp_int(base.get("font_size"), 28, 6, 96)
    out["name_font_size"] = _clamp_int(base.get("name_font_size"), 24, 6, 96)
    out["choice_font_size"] = _clamp_int(base.get("choice_font_size"), 26, 6, 96)
    out["char_width"] = _clamp_int(base.get("char_width"), 100, 10, 300)
    out["char_height"] = _clamp_int(base.get("char_height"), 100, 10, 300)
    out["line_spacing"] = _clamp_int(base.get("line_spacing"), 100, 50, 300)
    out["letter_spacing"] = _clamp_int(base.get("letter_spacing"), 0, -100, 200)
    out["screen_width"] = _clamp_int(base.get("screen_width"), DEFAULT_MAKER_PREVIEW_SETTINGS["screen_width"], 320, 4096)
    out["screen_height"] = _clamp_int(base.get("screen_height"), DEFAULT_MAKER_PREVIEW_SETTINGS["screen_height"], 240, 2160)
    out["ui_area_width"] = _clamp_int(base.get("ui_area_width"), out["screen_width"], 320, 4096)
    out["ui_area_height"] = _clamp_int(base.get("ui_area_height"), out["screen_height"], 240, 2160)
    auto_message_width = max(120, int(out["ui_area_width"]))
    out["message_x"] = _clamp_int(base.get("message_x"), DEFAULT_MAKER_PREVIEW_SETTINGS["message_x"], -4096, 4096)
    out["message_y"] = _clamp_int(base.get("message_y"), DEFAULT_MAKER_PREVIEW_SETTINGS["message_y"], -4096, 4096)
    out["message_width"] = _clamp_int(base.get("message_width"), auto_message_width, 120, 4096)
    out["message_width"] = min(int(out["message_width"]), max(120, int(out["screen_width"])))
    out["message_height"] = _clamp_int(base.get("message_height"), DEFAULT_MAKER_PREVIEW_SETTINGS["message_height"], 48, 1200)
    out["message_margin"] = _clamp_int(base.get("message_margin"), DEFAULT_MAKER_PREVIEW_SETTINGS["message_margin"], 0, 120)
    out["message_lines"] = _clamp_int(base.get("message_lines"), 4, 1, 12)
    out["message_padding"] = _clamp_int(base.get("message_padding"), 18, 0, 120)
    out["line_height"] = _clamp_int(base.get("line_height"), DEFAULT_MAKER_PREVIEW_SETTINGS["line_height"], 12, 120)
    out["item_padding"] = _clamp_int(base.get("item_padding"), DEFAULT_MAKER_PREVIEW_SETTINGS["item_padding"], 0, 80)
    out["box_margin"] = _clamp_int(base.get("box_margin"), DEFAULT_MAKER_PREVIEW_SETTINGS["box_margin"], 0, 120)
    out["name_padding_x"] = _clamp_int(base.get("name_padding_x"), DEFAULT_MAKER_PREVIEW_SETTINGS["name_padding_x"], 0, 120)
    out["name_padding_y"] = _clamp_int(base.get("name_padding_y"), DEFAULT_MAKER_PREVIEW_SETTINGS["name_padding_y"], 0, 120)
    out["name_min_width"] = _clamp_int(base.get("name_min_width"), DEFAULT_MAKER_PREVIEW_SETTINGS["name_min_width"], 32, 800)
    out["name_min_height"] = _clamp_int(base.get("name_min_height"), DEFAULT_MAKER_PREVIEW_SETTINGS["name_min_height"], 24, 300)
    out["name_overlap"] = _clamp_int(base.get("name_overlap"), DEFAULT_MAKER_PREVIEW_SETTINGS["name_overlap"], -120, 120)
    out["outline_width"] = _clamp_int(base.get("outline_width"), 3, 0, 20)
    out["outline_qt_scale"] = _clamp_int(base.get("outline_qt_scale"), DEFAULT_MAKER_PREVIEW_SETTINGS["outline_qt_scale"], 25, 125)
    out["window_opacity"] = _clamp_int(base.get("window_opacity"), DEFAULT_MAKER_PREVIEW_SETTINGS["window_opacity"], 0, 255)
    out["game_settings_user_saved"] = bool(base.get("game_settings_user_saved", DEFAULT_MAKER_PREVIEW_SETTINGS.get("game_settings_user_saved", False)))
    out["game_settings_saved_at"] = str(base.get("game_settings_saved_at") or DEFAULT_MAKER_PREVIEW_SETTINGS.get("game_settings_saved_at") or "")
    out["debug_overlay"] = bool(base.get("debug_overlay", DEFAULT_MAKER_PREVIEW_SETTINGS["debug_overlay"]))
    out["show_map_grid"] = bool(base.get("show_map_grid", DEFAULT_MAKER_PREVIEW_SETTINGS.get("show_map_grid", False)))
    out["show_event_positions"] = bool(base.get("show_event_positions", DEFAULT_MAKER_PREVIEW_SETTINGS.get("show_event_positions", False)))
    out["show_event_text_overlay"] = bool(base.get("show_event_text_overlay", DEFAULT_MAKER_PREVIEW_SETTINGS.get("show_event_text_overlay", False)))
    out["show_local_map_preview"] = bool(base.get("show_local_map_preview", DEFAULT_MAKER_PREVIEW_SETTINGS.get("show_local_map_preview", True)))
    out["show_tile_map_preview"] = bool(base.get("show_tile_map_preview", DEFAULT_MAKER_PREVIEW_SETTINGS.get("show_tile_map_preview", True)))
    out["show_advanced_map_preview"] = bool(base.get("show_advanced_map_preview", DEFAULT_MAKER_PREVIEW_SETTINGS.get("show_advanced_map_preview", True)))
    out["enable_tile_validation_dump"] = bool(base.get("enable_tile_validation_dump", DEFAULT_MAKER_PREVIEW_SETTINGS.get("enable_tile_validation_dump", False)))
    out["defer_tile_render"] = bool(base.get("defer_tile_render", DEFAULT_MAKER_PREVIEW_SETTINGS.get("defer_tile_render", False)))
    # Runtime-only flags must survive normalization.  Manual preview refresh uses
    # these to bypass placeholder/tile caches; dropping them makes the renderer
    # think an existing cached preview is still valid.
    out["force_maker_preview_rebuild"] = bool(base.get("force_maker_preview_rebuild", False))
    out["force_preview_rebuild"] = bool(base.get("force_preview_rebuild", False))
    out["local_map_cols"] = _clamp_int(base.get("local_map_cols"), DEFAULT_MAKER_PREVIEW_SETTINGS.get("local_map_cols", 15), 5, 40)
    out["local_map_rows"] = _clamp_int(base.get("local_map_rows"), DEFAULT_MAKER_PREVIEW_SETTINGS.get("local_map_rows", 10), 4, 30)
    # 쯔꾸르붕이에서는 YSB 식질용 텍스트 객체를 맵 캔버스 위에 만들지 않는다.
    # 대사는 게임식 대사창/선택지창 프리뷰와 우측 표에서만 다룬다.
    # 기존 설정 파일에 show_canvas_text_overlay=True가 남아 있어도 안전하게 무시한다.
    out["show_canvas_text_overlay"] = False
    out["show_picture_opacity"] = bool(base.get("show_picture_opacity", DEFAULT_MAKER_PREVIEW_SETTINGS.get("show_picture_opacity", False)))
    out["text_color"] = _clean_hex_color(base.get("text_color"), DEFAULT_MAKER_PREVIEW_SETTINGS["text_color"])
    out["outline_color"] = _clean_hex_color(base.get("outline_color"), DEFAULT_MAKER_PREVIEW_SETTINGS["outline_color"])
    return out


def _maker_preview_char_units(ch: str) -> float:
    """Approximate visual width units for RPG Maker preview wrapping."""
    if not ch:
        return 0.0
    if ch == "\t":
        return 2.0
    if ch.isspace():
        return 0.45
    try:
        east = unicodedata.east_asian_width(ch)
    except Exception:
        east = "N"
    if east in {"F", "W"}:
        return 1.0
    if east == "A":
        return 0.85
    if ch in "|!ilI.,:;`\'\"":
        return 0.35
    if ch in "()[]{}<>/\\-_=+":
        return 0.55
    return 0.62


def wrap_maker_preview_text(text: str, settings: Dict[str, Any] | None = None, *, text_type: str = "text", max_text_width: int | None = None) -> Dict[str, Any]:
    """Measure message preview text without auto-wrapping.

    The editor preview must show the actual saved line breaks.  If a translated
    line is too long, keep it as one long line and report overflow instead of
    wrapping it visually.  This prevents the preview from hiding lines that need
    manual review.
    """
    st = normalize_maker_preview_settings(settings)
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if str(text_type or "").startswith("choice"):
        size = int(st.get("choice_font_size") or st.get("font_size") or 26)
    else:
        size = int(st.get("font_size") or 28)
    padding = int(st.get("message_padding") or 0)
    width = int(max_text_width or st.get("message_width") or 760)
    usable = max(40, width - padding * 2)
    # Do not apply editor text-object correction values (char_width/letter_spacing)
    # to RPG Maker scene preview diagnostics.
    unit_px = max(2.0, float(size) * 0.92)
    max_units = max(4.0, float(usable) / unit_px)
    lines: List[str] = raw.split("\n") if raw != "" else [""]
    max_lines = int(st.get("message_lines") or 4)
    max_lines = max(1, min(12, max_lines))
    width_overflow = False
    for line in lines:
        units = sum(_maker_preview_char_units(ch) for ch in str(line or ""))
        if units > max_units:
            width_overflow = True
            break
    overflow = bool(len(lines) > max_lines or width_overflow)
    visible = lines[:max_lines]
    return {
        "lines": lines,
        "visible_lines": visible,
        "visible_text": "\n".join(visible),
        "line_count": len(lines),
        "max_lines": max_lines,
        "overflow": bool(overflow),
        "overflow_count": max(0, len(lines) - max_lines),
        "width_overflow": bool(width_overflow),
        "usable_width": int(usable),
        "estimated_units_per_line": float(max_units),
    }




def _write_keep_file(folder: Path, text: str = "") -> None:
    """Keep intentional empty Maker sidecar folders visible in YSBG packages."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        keep = folder / MAKER_KEEP_FILE
        if not keep.exists():
            keep.write_text(text or "YSB Maker project sidecar folder.\n", encoding="utf-8")
    except Exception:
        pass


def maker_project_layout(project_dir: str | os.PathLike[str]) -> Dict[str, Any]:
    """Return the canonical RPG Maker branch folder layout for one YSB project."""
    root = Path(project_dir)
    return {
        "layout_version": 1,
        "project_kind": "rpg_maker_mv_mz",
        "clone_dir": MAKER_CLONE_DIR,
        "meta_dir": MAKER_META_DIR,
        "backup_dir": MAKER_BACKUP_DIR,
        "original_json_backup_dir": f"{MAKER_BACKUP_DIR}/{MAKER_ORIGINAL_JSON_BACKUP_DIR}",
        "diff_dir": MAKER_DIFF_DIR,
        "page_image_dir": "images",
        "project_file": "project.json",
        "roles": {
            MAKER_CLONE_DIR: "Imported game clone edited by this project. The original selected game folder is not modified.",
            MAKER_META_DIR: "Import summary, engine detection, preview settings, character prompts, and structural metadata.",
            MAKER_BACKUP_DIR: "Original JSON baseline and manual write-back backups stored outside the cloned game.",
            MAKER_DIFF_DIR: "Reserved for future version/update comparison snapshots and reports.",
            "images": "YSB page preview images. For Maker projects, each image is a map/page placeholder or renderer output.",
            "project.json": "YSB page list and editable TextUnit data.",
        },
        "paths": {
            "root": ".",
            "clone": MAKER_CLONE_DIR,
            "meta": MAKER_META_DIR,
            "backup": MAKER_BACKUP_DIR,
            "original_json_backup": f"{MAKER_BACKUP_DIR}/{MAKER_ORIGINAL_JSON_BACKUP_DIR}",
            "diff": MAKER_DIFF_DIR,
            "images": "images",
        },
    }


def maker_project_layout_path(project_dir: str | os.PathLike[str]) -> Path:
    return Path(project_dir) / MAKER_META_DIR / MAKER_PROJECT_LAYOUT_FILE


def ensure_maker_project_layout(project_dir: str | os.PathLike[str]) -> Dict[str, Any]:
    """Create the canonical Maker sidecar folders and persist a layout manifest."""
    root = Path(project_dir)
    for name in (MAKER_CLONE_DIR, MAKER_META_DIR, MAKER_BACKUP_DIR, MAKER_DIFF_DIR, "images"):
        (root / name).mkdir(parents=True, exist_ok=True)
    # maker_game and images usually contain real files. backup/diff can be empty
    # at first, so keep markers make the intended structure survive packaging.
    _write_keep_file(root / MAKER_BACKUP_DIR, "YSB Maker original JSON backups and optional write-back backups.\n")
    _write_keep_file(root / MAKER_BACKUP_DIR / MAKER_ORIGINAL_JSON_BACKUP_DIR, "Original JSON baseline copied from the imported game before live clone editing.\n")
    _write_keep_file(root / MAKER_DIFF_DIR, "YSB Maker update/diff workspace. Reserved for future version comparison.\n")
    layout = maker_project_layout(root)
    try:
        path = maker_project_layout_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(layout, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return layout


def load_maker_project_layout(project_dir: str | os.PathLike[str] | None) -> Dict[str, Any]:
    if not project_dir:
        return {}
    try:
        path = maker_project_layout_path(project_dir)
        if path.is_file():
            data = _read_json(path)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    try:
        return maker_project_layout(project_dir)
    except Exception:
        return {}

def maker_preview_settings_path(project_dir: str | os.PathLike[str]) -> Path:
    return Path(project_dir) / MAKER_META_DIR / MAKER_PREVIEW_SETTINGS_FILE


def load_maker_preview_settings(project_dir: str | os.PathLike[str] | None) -> Dict[str, Any]:
    if not project_dir:
        return normalize_maker_preview_settings()
    path = maker_preview_settings_path(project_dir)
    try:
        if path.is_file():
            return normalize_maker_preview_settings(_read_json(path))
    except Exception:
        pass
    return normalize_maker_preview_settings()


def save_maker_preview_settings(project_dir: str | os.PathLike[str], settings: Dict[str, Any]) -> Dict[str, Any]:
    fixed = normalize_maker_preview_settings(settings)
    path = maker_preview_settings_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)
    return fixed

DEFAULT_MAKER_CHARACTER_PROMPT_PROFILE: Dict[str, Any] = {
    "enabled": True,
    "display_name": "",
    "tone": "",
    "personality": "",
    "relationship": "",
    "translation_rules": "",
    "forbidden_words": "",
    "notes": "",
}


DEFAULT_MAKER_CHARACTER_PROMPTS: Dict[str, Any] = {
    "schema_version": 2,
    "default_prompt": "",
    "system_prompt": "",
    "characters": {},
}


def maker_character_prompts_path(project_dir: str | os.PathLike[str]) -> Path:
    return Path(project_dir) / MAKER_META_DIR / MAKER_CHARACTER_PROMPTS_FILE


def _normal_character_key(name: Any) -> str:
    text = str(name or "").strip()
    if not text or text.lower() == "unknown":
        return "Unknown"
    return text


def normalize_maker_character_prompt_profile(profile: Dict[str, Any] | None, *, speaker: str = "") -> Dict[str, Any]:
    data = dict(DEFAULT_MAKER_CHARACTER_PROMPT_PROFILE)
    if isinstance(profile, dict):
        for key in data.keys():
            if key in profile:
                data[key] = profile.get(key)
    data["enabled"] = bool(data.get("enabled", True))
    for key in ("display_name", "tone", "personality", "relationship", "translation_rules", "forbidden_words", "notes"):
        data[key] = str(data.get(key) or "")
    if speaker and not data.get("display_name"):
        data["display_name"] = speaker
    return data


def normalize_maker_character_prompts(raw: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base = {
        "schema_version": 2,
        "default_prompt": "",
        "system_prompt": "",
        "characters": {},
    }
    if isinstance(raw, dict):
        try:
            base["schema_version"] = max(2, int(raw.get("schema_version") or 1))
        except Exception:
            base["schema_version"] = 2
        base["default_prompt"] = str(raw.get("default_prompt") or "")
        # v1 파일을 그대로 읽어도 깨지지 않게 system_prompt는 없으면 빈 값으로 둔다.
        base["system_prompt"] = str(raw.get("system_prompt") or "")
        chars = raw.get("characters") or {}
        if isinstance(chars, dict):
            for name, profile in chars.items():
                key = _normal_character_key(name)
                base["characters"][key] = normalize_maker_character_prompt_profile(profile if isinstance(profile, dict) else {}, speaker=key)
    return base


def load_maker_character_prompts(project_dir: str | os.PathLike[str] | None) -> Dict[str, Any]:
    if not project_dir:
        return normalize_maker_character_prompts()
    path = maker_character_prompts_path(project_dir)
    try:
        if path.is_file():
            return normalize_maker_character_prompts(_read_json(path))
    except Exception:
        pass
    return normalize_maker_character_prompts()


def save_maker_character_prompts(project_dir: str | os.PathLike[str], prompts: Dict[str, Any]) -> Dict[str, Any]:
    fixed = normalize_maker_character_prompts(prompts)
    ensure_maker_project_layout(project_dir)
    path = maker_character_prompts_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)
    return fixed


def _maker_prompt_row_is_real_speaker(item: Dict[str, Any] | None, page_meta: Dict[str, Any] | None = None) -> bool:
    if not isinstance(item, dict):
        return False
    meta = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
    pm = page_meta if isinstance(page_meta, dict) else {}
    page_type = str(pm.get("page_type") or "map").strip().lower()
    source_file = str((meta or {}).get("source_file") or (meta or {}).get("map_file") or pm.get("source_file") or pm.get("map_file") or "").strip()
    if page_type not in ("", "map", "common_events"):
        return False
    if source_file in ("System.json", "Troops.json") or source_file.startswith("DB_"):
        return False
    text_type = str((meta or {}).get("text_type") or item.get("text_type") or "").strip().lower()
    return text_type in ("dialogue", "common_dialogue", "show_text", "text")


def _maker_prompt_row_speaker(item: Dict[str, Any] | None) -> str:
    if not isinstance(item, dict):
        return ""
    meta = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
    candidates = [
        meta.get("speaker_plain") if isinstance(meta, dict) else "",
        item.get("maker_speaker_plain"),
        strip_maker_control_codes(item.get("maker_speaker") or ""),
        meta.get("speaker") if isinstance(meta, dict) else "",
        strip_maker_control_codes(item.get("speaker") or ""),
    ]
    for cand in candidates:
        key = _normal_character_key(cand)
        if key and key.lower() != "unknown":
            return key
    return ""


def _maker_row_is_dialogue_for_profile(item: Dict[str, Any] | None, page_meta: Dict[str, Any] | None = None) -> bool:
    """True only for real dialogue rows used as speaker/profile evidence."""
    if not isinstance(item, dict):
        return False
    meta = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    pm = page_meta if isinstance(page_meta, dict) else {}
    page_type = str(pm.get("page_type") or "map").strip().lower()
    source_file = str(meta.get("source_file") or meta.get("map_file") or pm.get("source_file") or pm.get("map_file") or "").strip()
    if page_type not in ("", "map", "common_events"):
        return False
    if source_file in ("System.json", "Troops.json") or source_file.startswith("DB_"):
        return False
    text_type = str(meta.get("text_type") or item.get("text_type") or "").strip().lower()
    return text_type in ("dialogue", "common_dialogue", "show_text", "text")


def _maker_row_speaker_for_profile(item: Dict[str, Any] | None) -> str:
    """Return the explicit current speaker name used for prompts/profiles.

    Face names and event names are only hints; they must not become character
    prompt/profile keys by themselves.
    """
    if not isinstance(item, dict):
        return ""
    meta = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    candidates = [
        item.get("maker_speaker_plain"),
        meta.get("speaker_plain"),
        strip_maker_control_codes(item.get("maker_speaker") or ""),
        strip_maker_control_codes(meta.get("speaker") or ""),
        strip_maker_control_codes(item.get("speaker") or ""),
    ]
    for cand in candidates:
        key = _normal_character_key(cand)
        if key and key.lower() != "unknown":
            return key
    return ""


def _maker_speaker_alias_map_from_data(data: Dict[int, dict] | None) -> Dict[str, str]:
    """Map original speaker names to current translated/display speaker names."""
    aliases: Dict[str, str] = {}
    for _idx, page in _dict_items(data):
        if not isinstance(page, dict):
            continue
        page_meta = page.get("maker_page") if isinstance(page.get("maker_page"), dict) else {}
        for item in page.get("data") or []:
            if not _maker_row_is_dialogue_for_profile(item, page_meta):
                continue
            current = _maker_row_speaker_for_profile(item)
            if not current:
                continue
            meta = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
            legacy = item.get("maker_meta") if isinstance(item.get("maker_meta"), dict) else {}
            original_candidates = [
                item.get("maker_speaker_original"),
                meta.get("speaker_original") if isinstance(meta, dict) else "",
                legacy.get("speaker_original") if isinstance(legacy, dict) else "",
                meta.get("speaker_plain") if isinstance(meta, dict) else "",
                meta.get("speaker") if isinstance(meta, dict) else "",
            ]
            for raw in original_candidates:
                original = _normal_character_key(strip_maker_control_codes(raw or ""))
                if original and original.lower() != "unknown" and original != current:
                    aliases[original] = current
    return aliases


def _maker_profile_key(name: Any, aliases: Dict[str, str] | None = None) -> str:
    key = _normal_character_key(name)
    if aliases and key in aliases:
        return _normal_character_key(aliases.get(key) or key)
    return key



def collect_maker_speakers_from_data(data: Dict[int, dict] | None) -> List[str]:
    speakers: List[str] = []
    seen = set()
    for _idx, page in _dict_items(data):
        if not isinstance(page, dict):
            continue
        page_meta = page.get("maker_page") if isinstance(page.get("maker_page"), dict) else {}
        for item in page.get("data") or []:
            if not _maker_row_is_dialogue_for_profile(item, page_meta):
                continue
            key = _maker_row_speaker_for_profile(item)
            if key and key not in seen:
                seen.add(key)
                speakers.append(key)
    speakers.sort(key=lambda x: x.casefold())
    return speakers


def _maker_prompt_profile_has_user_text(profile: Dict[str, Any] | None) -> bool:
    if not isinstance(profile, dict):
        return False
    for key in ("tone", "personality", "relationship", "translation_rules", "forbidden_words", "notes"):
        if str(profile.get(key) or "").strip():
            return True
    return False


def _merge_maker_character_prompt_profile(target: Dict[str, Any] | None, source: Dict[str, Any] | None, *, speaker: str) -> Dict[str, Any]:
    """Merge old prompt data into a current speaker key without destroying edits.

    The current speaker key wins.  Old/original-name profiles only fill empty
    fields.  This is used when 화자 번역 changes リオラ -> 리오라.
    """
    merged = normalize_maker_character_prompt_profile(target if isinstance(target, dict) else {}, speaker=speaker)
    src = normalize_maker_character_prompt_profile(source if isinstance(source, dict) else {}, speaker=speaker)
    if not _maker_prompt_profile_has_user_text(merged):
        merged["enabled"] = bool(src.get("enabled", merged.get("enabled", True)))
    for key in ("display_name", "tone", "personality", "relationship", "translation_rules", "forbidden_words", "notes"):
        if not str(merged.get(key) or "").strip() and str(src.get(key) or "").strip():
            merged[key] = str(src.get(key) or "")
    if not str(merged.get("display_name") or "").strip():
        merged["display_name"] = speaker
    return merged


def sync_maker_character_prompts_to_current_speakers(prompts: Dict[str, Any] | None, data: Dict[int, dict] | None = None) -> Dict[str, Any]:
    """Keep prompt data only for real current speakers, preserving valid text.

    - default_prompt/system_prompt are always preserved.
    - Current real speakers from dialogue rows are the only character prompt keys.
    - If a speaker was renamed, the old-name prompt is merged into the new key
      by filling empty fields only.
    - Fake/stale keys from DB/System/Troops/image-only candidates are removed.
    """
    fixed = normalize_maker_character_prompts(prompts)
    old_chars = dict(fixed.get("characters") or {})
    speakers = [_normal_character_key(sp) for sp in collect_maker_speakers_from_data(data) if _normal_character_key(sp).lower() != "unknown"]
    seen = set()
    ordered_speakers: List[str] = []
    for sp in speakers:
        if sp and sp not in seen:
            seen.add(sp)
            ordered_speakers.append(sp)
    aliases = _maker_speaker_alias_map_from_data(data or {})
    new_chars: Dict[str, Any] = {}
    for sp in ordered_speakers:
        base = old_chars.get(sp)
        merged = normalize_maker_character_prompt_profile(base if isinstance(base, dict) else {}, speaker=sp)
        # Merge prompts written under original names into the current translated speaker key.
        for old_key, current_key in aliases.items():
            if _normal_character_key(current_key) != sp:
                continue
            if old_key == sp:
                continue
            old_profile = old_chars.get(old_key)
            if isinstance(old_profile, dict):
                merged = _merge_maker_character_prompt_profile(merged, old_profile, speaker=sp)
        new_chars[sp] = merged
    fixed["characters"] = new_chars
    return normalize_maker_character_prompts(fixed)


def ensure_maker_character_prompt_profiles(project_dir: str | os.PathLike[str], data: Dict[int, dict] | None = None) -> Dict[str, Any]:
    prompts = load_maker_character_prompts(project_dir)
    fixed = sync_maker_character_prompts_to_current_speakers(prompts, data)
    return save_maker_character_prompts(project_dir, fixed)


def maker_character_prompt_for_speaker(prompts: Dict[str, Any] | None, speaker: Any) -> Dict[str, Any]:
    fixed = normalize_maker_character_prompts(prompts)
    key = _normal_character_key(speaker)
    profile = fixed.get("characters", {}).get(key) or {}
    return normalize_maker_character_prompt_profile(profile, speaker=key)


def build_maker_character_prompt_text(prompts: Dict[str, Any] | None, speaker: Any, *, include_default: bool = True) -> str:
    fixed = normalize_maker_character_prompts(prompts)
    key = _normal_character_key(speaker)
    profile = maker_character_prompt_for_speaker(fixed, key)
    templates = get_runtime_prompt_templates()
    parts: List[str] = []
    if include_default and str(fixed.get("default_prompt") or "").strip():
        parts.append(str(fixed.get("default_prompt") or "").strip())
    if profile.get("enabled"):
        label = str(profile.get("display_name") or key).strip() or key
        field_lines: List[str] = []
        field_specs = (
            ("tone", "character_profile_tone", "TONE"),
            ("personality", "character_profile_personality", "PERSONALITY"),
            ("relationship", "character_profile_relationship", "RELATIONSHIP"),
            ("translation_rules", "character_profile_translation_rules", "TRANSLATION_RULES"),
            ("forbidden_words", "character_profile_forbidden_words", "FORBIDDEN_WORDS"),
            ("notes", "character_profile_notes", "NOTES"),
        )
        for profile_key, template_key, placeholder in field_specs:
            value = str(profile.get(profile_key) or "").strip()
            if not value:
                continue
            line = render_prompt_template(templates.get(template_key, ""), **{placeholder: value})
            if line:
                field_lines.append(line)
        if field_lines:
            character_lines: List[str] = []
            header = render_prompt_template(templates.get("character_profile_header", ""), DISPLAY_NAME=label)
            if header:
                character_lines.append(header)
            character_lines.extend(field_lines)
            parts.append("\n".join(character_lines))
    return "\n\n".join(part for part in parts if str(part or "").strip())


def build_maker_common_prompt_text(prompts: Dict[str, Any] | None) -> str:
    fixed = normalize_maker_character_prompts(prompts)
    return str(fixed.get("default_prompt") or "").strip()


def build_maker_system_prompt_text(prompts: Dict[str, Any] | None) -> str:
    fixed = normalize_maker_character_prompts(prompts)
    return str(fixed.get("system_prompt") or "").strip()


def apply_maker_character_prompts_to_data(data: Dict[int, dict] | None, prompts: Dict[str, Any] | None) -> int:
    fixed = normalize_maker_character_prompts(prompts)
    changed = 0
    chars = fixed.get("characters") or {}
    for _idx, page in _dict_items(data):
        if not isinstance(page, dict):
            continue
        page["maker_character_prompts"] = fixed
        for item in page.get("data") or []:
            if not isinstance(item, dict) or not isinstance(item.get("maker_text_unit"), dict):
                continue
            meta = item.get("maker_text_unit") or {}
            speaker = _normal_character_key(item.get("maker_speaker") or meta.get("speaker"))
            if speaker in chars:
                item["maker_prompt_profile"] = speaker
                meta["prompt_profile"] = speaker
                changed += 1
    return changed



def maker_character_profiles_path(project_dir: str | os.PathLike[str]) -> Path:
    return Path(project_dir) / MAKER_META_DIR / MAKER_CHARACTER_PROFILES_FILE


def _safe_profile_key(name: Any) -> str:
    key = _normal_character_key(name)
    return key or "Unknown"


def _profile_blank(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "display_name": name,
        "source_hints": [],
        "text_count": 0,
        "source_counts": {},
        "images": [],
        "samples": [],
        "appearances": [],
        "actor": {},
        "profile_prompt": {},
        "confidence": 0.0,
    }


def _profile_entry(profiles: Dict[str, Any], name: Any) -> Dict[str, Any]:
    key = _safe_profile_key(name)
    if key not in profiles:
        profiles[key] = _profile_blank(key)
    return profiles[key]


def _add_profile_hint(profile: Dict[str, Any], hint: str) -> None:
    hint = str(hint or "").strip()
    if not hint:
        return
    hints = profile.setdefault("source_hints", [])
    if hint not in hints:
        hints.append(hint)


def _maker_content_paths_for_project(project_dir: str | os.PathLike[str]) -> Tuple[Path, Path, Path, Dict[str, Any]]:
    """Resolve the actual MV/MZ content root inside maker_game.

    Imported games keep the folder selected by the user intact.  Therefore the
    real data/js/img folders may live below an arbitrary wrapper directory such
    as ``maker_game/게임데이터`` or a deployed ``resources/app.nw`` tree.
    Prefer the import summary, but validate it and re-detect the clone when an
    old/stale project summary still points at maker_game/data.
    """
    project_root = Path(project_dir)
    game_root = project_root / MAKER_CLONE_DIR
    summary = _read_maker_import_summary(project_root)
    engine_info = summary.get("engine") if isinstance(summary, dict) else None
    engine_dict = dict(engine_info) if isinstance(engine_info, dict) else {}

    def resolve(info: Dict[str, Any] | None):
        data = _data_dir_from_engine_info(game_root, info)
        content = _content_root_from_engine_info(game_root, info)
        return data, content

    try:
        data_dir, content_root = resolve(engine_dict or None)
    except Exception:
        data_dir, content_root = game_root / RPG_MAKER_DATA_DIR, game_root

    # Old projects or manually moved clones can have a valid maker_game folder
    # but an invalid/stale engine path in maker_import_summary.json.  Re-detect
    # from the clone instead of silently falling back to maker_game/data.
    marker_ok = (Path(data_dir) / "MapInfos.json").is_file()
    try:
        content_matches_data = Path(content_root).resolve() == Path(data_dir).parent.resolve()
    except Exception:
        content_matches_data = Path(content_root) == Path(data_dir).parent
    if not marker_ok or not content_matches_data or not engine_dict.get("data_dir") or not engine_dict.get("project_root"):
        detected = detect_maker_engine(game_root)
        engine_dict = detected.to_dict()
        data_dir, content_root = resolve(engine_dict)

    return game_root, Path(data_dir), Path(content_root), engine_dict


def maker_project_paths(project_dir: str | os.PathLike[str]) -> Dict[str, Any]:
    """Return one canonical path set for all Maker readers and previews.

    UI code must use this resolver instead of guessing maker_game/data,
    maker_game/www/data, and similar layouts independently.
    """
    project_root = Path(project_dir)
    game_root, data_dir, content_root, engine_info = _maker_content_paths_for_project(project_root)
    js_dir = _js_dir_from_engine_info(game_root, engine_info)
    if not Path(js_dir).is_dir():
        js_dir = Path(content_root) / "js"
    return {
        "project_root": project_root,
        "game_root": Path(game_root),
        "content_root": Path(content_root),
        "data_dir": Path(data_dir),
        "js_dir": Path(js_dir),
        "img_dir": Path(content_root) / "img",
        "fonts_dir": Path(content_root) / "fonts",
        "engine": dict(engine_info or {}),
    }


def _rel_from_game_root(game_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(game_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _image_rel_candidate(game_root: Path, content_root: Path, folder: str, name: Any) -> str:
    base = str(name or "").strip()
    if not base:
        return ""
    base = base.replace("\\", "/").split("/")[-1]
    candidates = [base] if re.search(r"\.(png|jpg|jpeg|webp)$", base, flags=re.I) else [base + ext for ext in (".png", ".webp", ".jpg", ".jpeg")]
    for candidate in candidates:
        p = content_root / "img" / folder / candidate
        if p.is_file():
            return _rel_from_game_root(game_root, p)
    if not re.search(r"\.(png|jpg|jpeg|webp)$", base, flags=re.I):
        base = base + ".png"
    return _rel_from_game_root(game_root, content_root / "img" / folder / base)


def _candidate_key(candidate: Dict[str, Any]) -> Tuple[Any, ...]:
    layers = candidate.get("layers") if isinstance(candidate, dict) else None
    layer_key: Tuple[Any, ...] = tuple(
        (
            str(layer.get("role") or ""),
            str(layer.get("rel_path") or ""),
            int(layer.get("x") or 0),
            int(layer.get("y") or 0),
        )
        for layer in (layers or [])
        if isinstance(layer, dict)
    )
    return (
        str(candidate.get("kind") or ""),
        str(candidate.get("rel_path") or ""),
        int(candidate.get("index") or 0),
        layer_key,
        str(candidate.get("plugin_name") or ""),
        str(candidate.get("actor_key") or ""),
        str(candidate.get("pose") or ""),
        str(candidate.get("expression") or ""),
    )


def _add_image_candidate(profile: Dict[str, Any], candidate: Dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        return
    if not candidate.get("rel_path"):
        layers = candidate.get("layers") if isinstance(candidate.get("layers"), list) else []
        first_layer = next((x for x in layers if isinstance(x, dict) and x.get("rel_path")), None)
        if first_layer:
            candidate = dict(candidate)
            candidate["rel_path"] = str(first_layer.get("rel_path") or "")
    if not candidate.get("rel_path"):
        return
    images = profile.setdefault("images", [])
    key = _candidate_key(candidate)
    for old in images:
        if _candidate_key(old) == key:
            old["count"] = int(old.get("count") or 0) + int(candidate.get("count") or 1)
            try:
                old["confidence"] = max(float(old.get("confidence") or 0.0), float(candidate.get("confidence") or 0.0))
            except Exception:
                pass
            ev = str(candidate.get("evidence") or "").strip()
            if ev:
                evidences = old.setdefault("evidences", [])
                if ev not in evidences:
                    evidences.append(ev)
            return
    cand = dict(candidate)
    cand.setdefault("count", 1)
    ev = str(cand.pop("evidence", "") or "").strip()
    cand.setdefault("evidences", [ev] if ev else [])
    images.append(cand)


def _add_profile_sample(profile: Dict[str, Any], text: Any, *, translated_text: Any = "", map_name: str = "", event_name: str = "", text_type: str = "", source_file: str = "") -> None:
    src = str(text or "").strip()
    if not src:
        return
    samples = profile.setdefault("samples", [])
    if any(str(x.get("text") or "") == src for x in samples):
        return
    # 캐릭터 말투 파악용이므로 너무 적게 자르지 않는다.
    # 실제 프롬프트에는 이 전체 샘플을 자동 투입하지 않고, 프로필 작성 참고용으로만 보여준다.
    if len(samples) >= 30:
        return
    samples.append({
        "text": src,
        "translated_text": str(translated_text or "").strip(),
        "map_name": str(map_name or ""),
        "event_name": str(event_name or ""),
        "text_type": str(text_type or ""),
        "source_file": str(source_file or ""),
    })


def _add_profile_appearance(profile: Dict[str, Any], *, map_name: str = "", event_name: str = "", source_file: str = "", count: int = 1) -> None:
    key = (str(map_name or ""), str(event_name or ""), str(source_file or ""))
    apps = profile.setdefault("appearances", [])
    for app in apps:
        if (str(app.get("map_name") or ""), str(app.get("event_name") or ""), str(app.get("source_file") or "")) == key:
            app["count"] = int(app.get("count") or 0) + int(count or 1)
            return
    if len(apps) < 50:
        apps.append({"map_name": key[0], "event_name": key[1], "source_file": key[2], "count": int(count or 1)})


def _name_similarity_hint(name: str, file_name: str) -> bool:
    def norm(x: str) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣ぁ-んァ-ヶ一-龥]+", "", str(x or "")).casefold()
    n = norm(name)
    f = norm(Path(str(file_name or "")).stem)
    return bool(n and f and (n in f or f in n))


def _maker_plugin_parameters_by_name(
    game_root: Path,
    engine_info: MakerEngineInfo | Dict[str, Any] | None,
    plugin_name: str,
) -> Dict[str, Any]:
    """Return one enabled plugin's parameter dictionary from generated plugins.js."""
    try:
        content_root = _content_root_from_engine_info(Path(game_root), engine_info)
    except Exception:
        content_root = Path(game_root)
    path = Path(content_root) / "js" / "plugins.js"
    if not path.is_file():
        return {}
    try:
        payload, _prefix, _suffix = _read_maker_plugins_js_array(path)
    except Exception:
        return {}
    target = str(plugin_name or "").strip().casefold()
    for plugin in payload:
        if not isinstance(plugin, dict) or not bool(plugin.get("status", True)):
            continue
        if str(plugin.get("name") or "").strip().casefold() != target:
            continue
        params = plugin.get("parameters")
        return dict(params) if isinstance(params, dict) else {}
    return {}


def load_maker_trp_skit_actor_config(
    game_root: Path,
    engine_info: MakerEngineInfo | Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Parse TRP_SkitMZ actor aliases/poses for both preview and profile analysis."""
    params = _maker_plugin_parameters_by_name(Path(game_root), engine_info, "TRP_SkitMZ_Config")
    raw_list = params.get("SkitActorSettings") or "[]"
    try:
        arr = json.loads(raw_list) if isinstance(raw_list, str) else raw_list
    except Exception:
        arr = []
    actors: Dict[str, Dict[str, Any]] = {}
    if not isinstance(arr, list):
        return actors
    for raw in arr:
        try:
            obj = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(obj, dict):
                continue
            file_name = str(obj.get("fileName") or "").strip()
            input_name = str(obj.get("inputName") or "").strip()
            display_name = str(obj.get("name") or "").strip()
            aliases: List[str] = []
            for alias in (input_name, display_name, file_name):
                if alias and alias not in aliases:
                    aliases.append(alias)
            if not aliases:
                continue
            poses: List[str] = []
            pose_info: Dict[str, Dict[str, Any]] = {}
            pose_raw = obj.get("pose") or "[]"
            try:
                pose_arr = json.loads(pose_raw) if isinstance(pose_raw, str) else pose_raw
            except Exception:
                pose_arr = []
            for pr in pose_arr if isinstance(pose_arr, list) else []:
                try:
                    po = json.loads(pr) if isinstance(pr, str) else pr
                except Exception:
                    po = None
                if not isinstance(po, dict):
                    continue
                pose_name = str(po.get("name") or "").strip()
                if pose_name:
                    poses.append(pose_name)
                    pose_info[pose_name.casefold()] = po
            default_pose = poses[0] if poses else "normal"
            default_position = str(
                obj.get("defaultPosition")
                or obj.get("position")
                or obj.get("positionName")
                or "center"
            ).strip()
            canonical = input_name or display_name or file_name
            data = {
                "configKey": canonical.casefold(),
                "inputName": input_name,
                "name": display_name,
                "fileName": file_name,
                "aliases": aliases,
                "defaultPose": default_pose,
                "defaultPosition": default_position,
                "poses": poses,
                "poseInfo": pose_info,
                "raw": obj,
            }
            for alias in aliases:
                cleaned = str(alias or "").replace("\\PX[160]", "").strip().casefold()
                if cleaned:
                    actors[cleaned] = data
        except Exception:
            continue
    return actors


def load_maker_trp_skit_display_config(
    game_root: Path,
    engine_info: MakerEngineInfo | Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    params = _maker_plugin_parameters_by_name(Path(game_root), engine_info, "TRP_SkitMZ_Config")

    def to_float(value: Any, default: float = 0.0) -> float:
        try:
            text = str(value).strip()
            return float(text) if text else float(default)
        except Exception:
            return float(default)

    positions: Dict[str, float] = {}
    raw_positions = params.get("xPosition") or "[]"
    try:
        arr = json.loads(raw_positions) if isinstance(raw_positions, str) else raw_positions
    except Exception:
        arr = []
    for raw in arr if isinstance(arr, list) else []:
        try:
            obj = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            obj = None
        if not isinstance(obj, dict):
            continue
        name = str(obj.get("name") or "").strip().casefold()
        if name:
            positions[name] = to_float(obj.get("position"), 5.0) / 10.0
    return {
        "busts_scale": max(1.0, min(400.0, to_float(params.get("bustsScale"), 100.0))),
        "base_offset_y": to_float(params.get("baseOffsetY"), 0.0),
        "positions": positions,
    }


def maker_trp_position_ratio(position: Any, *, positions: Dict[str, Any] | None = None) -> float | None:
    pos = str(position or "").strip().casefold()
    position_map = positions if isinstance(positions, dict) else {}
    if pos in position_map:
        try:
            return max(0.0, min(1.0, float(position_map[pos])))
        except Exception:
            pass
    aliases = {
        "left": 0.22, "l": 0.22,
        "center": 0.50, "centre": 0.50, "c": 0.50, "def": 0.50, "d": 0.50,
        "right": 0.78, "r": 0.78,
    }
    if pos in aliases:
        return aliases[pos]
    try:
        value = float(pos)
        if 0.0 <= value <= 1.0:
            return value
        if 0.0 <= value <= 10.0:
            return value / 10.0
    except Exception:
        pass
    return None


def parse_maker_trp_skit_command(
    line: Any,
    actors_cfg: Dict[str, Any] | None,
    positions: Dict[str, Any] | None,
) -> Dict[str, Any]:
    try:
        import shlex
        parts = shlex.split(str(line or ""), posix=False)
    except Exception:
        parts = str(line or "").split()
    clean = [str(x or "").strip().strip(",;") for x in parts if str(x or "").strip()]
    result = {"parts": clean, "op": "", "actor": "", "actor_index": -1, "position": "", "explicit_position": False}
    if len(clean) < 2 or clean[0].casefold() != "skit":
        return result
    result["op"] = clean[1].casefold()
    actor_map = actors_cfg if isinstance(actors_cfg, dict) else {}
    for idx in range(2, len(clean)):
        token = clean[idx]
        key = token.replace("\\PX[160]", "").strip().casefold()
        if key in actor_map:
            result["actor"] = token
            result["actor_index"] = idx
            break
    if not result["actor"] and len(clean) >= 3:
        result["actor"] = clean[2]
        result["actor_index"] = 2
    position_map = positions if isinstance(positions, dict) else {}
    for idx in range(max(2, int(result["actor_index"]) + 1), len(clean)):
        token = clean[idx]
        low = token.casefold()
        is_named = low in position_map or low in {"left", "l", "center", "centre", "c", "def", "d", "right", "r"}
        try:
            value = float(low)
            is_numeric = 0.0 <= value <= 10.0
        except Exception:
            is_numeric = False
        if is_named or is_numeric:
            result["position"] = token
            result["explicit_position"] = True
    return result


def maker_trp_skit_layer_spec(
    actor_key: Any,
    pose: Any = None,
    expression: Any = None,
    *,
    actors_cfg: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    actors = actors_cfg if isinstance(actors_cfg, dict) else {}
    lookup_key = str(actor_key or "").replace("\\PX[160]", "").strip().casefold()
    cfg = actors.get(lookup_key) or {}
    file_name = str(cfg.get("fileName") or actor_key or "").strip()
    resolved_pose = str(pose or cfg.get("defaultPose") or "normal").strip()
    requested_expression = str(expression or "default").strip()
    pose_info = (cfg.get("poseInfo") or {}).get(resolved_pose.casefold()) if isinstance(cfg.get("poseInfo"), dict) else {}
    pose_info = pose_info if isinstance(pose_info, dict) else {}
    numeric_expression_token = ""
    normalized_expression = requested_expression
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", requested_expression):
        numeric_expression_token = requested_expression
        normalized_expression = str(
            pose_info.get("defaultExpression")
            or pose_info.get("defaultExp")
            or "default"
        ).strip() or "default"
    default_expression = str(
        pose_info.get("defaultExpression")
        or pose_info.get("defaultExp")
        or "default"
    ).strip() or "default"
    base_candidates = [f"busts/{file_name}/{resolved_pose}"] if file_name and resolved_pose else []
    overlay_candidates = [f"busts/{file_name}/{resolved_pose}_{normalized_expression}"] if file_name and resolved_pose and normalized_expression else []
    fallback_candidates: List[str] = []
    if file_name and normalized_expression:
        fallback_candidates.append(f"busts/{file_name}/{normalized_expression}")
    if file_name and resolved_pose and normalized_expression:
        fallback_candidates.append(f"busts/{file_name}/{resolved_pose}_{normalized_expression}")
    return {
        "actor_key": actor_key,
        "config": cfg,
        "file_name": file_name,
        "pose": resolved_pose,
        "requested_expression": requested_expression,
        "normalized_expression": normalized_expression,
        "numeric_expression_token": numeric_expression_token,
        "default_expression": default_expression,
        "pose_info": pose_info,
        "base_candidates": base_candidates,
        "overlay_candidates": overlay_candidates,
        "fallback_candidates": fallback_candidates,
    }


def _maker_trp_asset_rel_from_candidate(game_root: Path, content_root: Path, candidate: str) -> str:
    raw = str(candidate or "").strip().replace("\\", "/").lstrip("/")
    if not raw:
        return ""
    suffixes = (".png", ".PNG", ".png_", ".PNG_", ".jpg", ".jpg_", ".jpeg", ".jpeg_", ".webp", ".webp_", ".bmp", ".bmp_", ".rpgmvp", ".rpgmvp_")
    names = [raw]
    if Path(raw).suffix == "":
        names.extend(raw + ext for ext in suffixes)
    bases = (
        Path(content_root) / "img" / "pictures",
        Path(content_root) / "pictures",
        Path(game_root) / "img" / "pictures",
        Path(game_root) / "pictures",
    )
    seen = set()
    for base in bases:
        for name in names:
            path = base / name
            key = str(path).casefold()
            if key in seen:
                continue
            seen.add(key)
            if path.is_file():
                return _rel_from_game_root(Path(game_root), path)
    return ""


def resolve_maker_trp_skit_layer_paths(
    game_root: Path,
    content_root: Path,
    actor_key: Any,
    pose: Any = None,
    expression: Any = None,
    *,
    actors_cfg: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    spec = maker_trp_skit_layer_spec(actor_key, pose, expression, actors_cfg=actors_cfg)
    base_rel = next((rel for rel in (_maker_trp_asset_rel_from_candidate(game_root, content_root, x) for x in spec.get("base_candidates") or []) if rel), "")
    overlay_rel = next((rel for rel in (_maker_trp_asset_rel_from_candidate(game_root, content_root, x) for x in spec.get("overlay_candidates") or []) if rel), "")
    resolved_expression = str(spec.get("normalized_expression") or "default")
    fallback = None
    if base_rel and not overlay_rel:
        default_expr = str(spec.get("default_expression") or "default")
        token = str(spec.get("normalized_expression") or "")
        if default_expr and token.casefold() != default_expr.casefold():
            default_candidate = f"busts/{spec.get('file_name')}/{spec.get('pose')}_{default_expr}"
            default_rel = _maker_trp_asset_rel_from_candidate(game_root, content_root, default_candidate)
            if default_rel:
                overlay_rel = default_rel
                resolved_expression = default_expr
                fallback = {"from": token, "to": default_expr, "candidate": default_candidate}
    if not base_rel and not overlay_rel:
        merged_rel = next((rel for rel in (_maker_trp_asset_rel_from_candidate(game_root, content_root, x) for x in spec.get("fallback_candidates") or []) if rel), "")
        if merged_rel:
            base_rel = merged_rel
    return {
        **spec,
        "base_rel_path": base_rel,
        "overlay_rel_path": overlay_rel,
        "resolved_expression": resolved_expression,
        "expression_fallback": fallback,
        "composition": "base_plus_expression_overlay" if base_rel and overlay_rel else ("base_only" if base_rel else "missing"),
    }


def iter_maker_trp_skit_dialogue_compositions(
    commands: List[Any],
    *,
    actors_cfg: Dict[str, Any] | None,
    positions: Dict[str, Any] | None = None,
    event_name: str = "",
    actor_lookup: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Return TRP actor pose/expression snapshots at each Show Text command."""
    actors = actors_cfg if isinstance(actors_cfg, dict) else {}
    if not actors:
        return []
    position_map = positions if isinstance(positions, dict) else {}
    states: Dict[str, Dict[str, Any]] = {}
    out: List[Dict[str, Any]] = []
    show_sequence = 0

    def clean_name(value: Any) -> str:
        text = str(value or "").replace("\\PX[160]", "").strip()
        text = re.sub(r"(?:\\|¥)[A-Za-z_]+(?:\[[^\]]*\])?", "", text)
        return text.strip()

    def get_state(name: Any) -> Dict[str, Any]:
        cleaned = clean_name(name)
        lookup = cleaned.casefold()
        cfg = actors.get(lookup) or {"fileName": cleaned, "defaultPose": "normal", "defaultPosition": "center", "configKey": lookup}
        config_key = str(cfg.get("configKey") or lookup).casefold()
        state = next((x for x in states.values() if str(x.get("config_key") or "").casefold() == config_key), None)
        if state is None:
            state = {
                "key": lookup,
                "config_key": config_key,
                "actor": cleaned,
                "pose": cfg.get("defaultPose") or "normal",
                "expression": "default",
                "visible": False,
                "position": cfg.get("defaultPosition") or "center",
                "show_sequence": -1,
                "source_command_index": -1,
            }
            states[lookup] = state
        return state

    def occupy_position(actor_state: Dict[str, Any], *, explicit: bool) -> None:
        ratio = maker_trp_position_ratio(actor_state.get("position"), positions=position_map)
        if ratio is None or not explicit:
            return
        for other in states.values():
            if other is actor_state or not other.get("visible"):
                continue
            other_ratio = maker_trp_position_ratio(other.get("position"), positions=position_map)
            if other_ratio is not None and abs(float(other_ratio) - float(ratio)) < 0.001:
                other["visible"] = False

    i = 0
    while i < len(commands):
        cmd = commands[i] if isinstance(commands[i], dict) else {}
        try:
            code = int(cmd.get("code") or 0)
        except Exception:
            code = 0
        params = cmd.get("parameters") if isinstance(cmd.get("parameters"), list) else []
        if code in (355, 655):
            for raw_line in params:
                line = str(raw_line or "").strip()
                if not line.casefold().startswith("skit"):
                    continue
                parsed = parse_maker_trp_skit_command(line, actors, position_map)
                parts = parsed.get("parts") or []
                op = str(parsed.get("op") or "").casefold()
                actor = str(parsed.get("actor") or "").strip()
                actor_idx = int(parsed.get("actor_index") or -1)
                if op in ("start", ""):
                    continue
                if op in ("end", "clear"):
                    states.clear()
                    continue
                if not actor:
                    continue
                state = get_state(actor)
                state["source_command_index"] = i
                if op in ("hide", "fadeout"):
                    state["visible"] = False
                elif op == "pose":
                    cfg = actors.get(clean_name(actor).casefold()) or {}
                    pose_names = {str(x).casefold(): str(x) for x in (cfg.get("poses") or [])}
                    tail = parts[actor_idx + 1:] if actor_idx >= 0 else []
                    pose_token = next((pose_names[str(x).casefold()] for x in tail if str(x).casefold() in pose_names), "")
                    if not pose_token and tail:
                        pose_token = str(tail[-1])
                    if pose_token:
                        state["pose"] = pose_token
                    candidate_tokens = []
                    for raw_token in tail:
                        token = str(raw_token or "").strip()
                        if not token or (pose_token and token.casefold() == str(pose_token).casefold()):
                            continue
                        if maker_trp_position_ratio(token, positions=position_map) is not None:
                            continue
                        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", token):
                            continue
                        if token.casefold() in {"true", "false", "wait", "nowait", "linear", "easein", "easeout", "easeinout"}:
                            continue
                        candidate_tokens.append(token)
                    if candidate_tokens:
                        state["expression"] = candidate_tokens[-1]
                elif op in ("exp", "expression"):
                    tail = parts[actor_idx + 1:] if actor_idx >= 0 else []
                    if tail:
                        state["expression"] = str(tail[-1])
                elif op in ("fadein", "show"):
                    show_sequence += 1
                    if parsed.get("explicit_position"):
                        state["position"] = parsed.get("position")
                    occupy_position(state, explicit=bool(parsed.get("explicit_position")))
                    state["visible"] = True
                    state["show_sequence"] = show_sequence
                elif op == "move" and parsed.get("explicit_position"):
                    state["position"] = parsed.get("position")
                    occupy_position(state, explicit=True)
            i += 1
            continue
        if code == 101:
            lines: List[str] = []
            j = i + 1
            while j < len(commands):
                nxt = commands[j] if isinstance(commands[j], dict) else {}
                try:
                    nxt_code = int(nxt.get("code") or 0)
                except Exception:
                    nxt_code = 0
                if nxt_code != 401:
                    break
                nxt_params = nxt.get("parameters") if isinstance(nxt.get("parameters"), list) else []
                if nxt_params:
                    lines.append(str(nxt_params[0] or ""))
                j += 1
            info = infer_maker_speaker(params=params, event_name=event_name, text="\n".join(lines), actor_lookup=actor_lookup)
            speaker = clean_name(info.get("speaker") or (params[4] if len(params) >= 5 else ""))
            cfg = actors.get(speaker.casefold()) if speaker else None
            if isinstance(cfg, dict):
                state = get_state(speaker)
                joined = " ".join([*(str(x or "") for x in params), *lines])
                for match in re.finditer(r"(?:\\|¥)SE\[([^\]]+)\]", joined, re.I):
                    expr = str(match.group(1) or "").strip()
                    if expr:
                        state["expression"] = expr
                out.append({
                    "command_index": i,
                    "speaker": speaker,
                    "speaker_source": str(info.get("speaker_source") or ""),
                    "speaker_confidence": float(info.get("speaker_confidence") or 0.0),
                    "actor_key": state.get("actor") or speaker,
                    "config_key": state.get("config_key") or cfg.get("configKey") or speaker.casefold(),
                    "pose": state.get("pose") or cfg.get("defaultPose") or "normal",
                    "expression": state.get("expression") or "default",
                    "visible": bool(state.get("visible")),
                    "position": state.get("position") or cfg.get("defaultPosition") or "center",
                    "source_command_index": int(state.get("source_command_index") or -1),
                    "show_sequence": int(state.get("show_sequence") or -1),
                })
            i = j
            continue
        i += 1
    return out


def _collect_picture_candidates_from_commands(
    profiles: Dict[str, Any],
    commands: List[Any],
    *,
    event_name: str,
    map_name: str,
    source_file: str,
    game_root: Path,
    content_root: Path,
    actor_lookup: Dict[str, Any] | None = None,
    speaker_aliases: Dict[str, str] | None = None,
) -> None:
    recent: List[Tuple[int, str]] = []
    i = 0
    while i < len(commands):
        cmd = commands[i] if isinstance(commands[i], dict) else {}
        try:
            code = int(cmd.get("code") or 0)
        except Exception:
            code = 0
        params = cmd.get("parameters") if isinstance(cmd.get("parameters"), list) else []
        if code == 231:
            try:
                pic_name = str(params[1] or "").strip() if len(params) > 1 else ""
            except Exception:
                pic_name = ""
            if pic_name:
                recent.append((i, pic_name))
                recent = recent[-8:]
        elif code == 101:
            lines: List[str] = []
            j = i + 1
            while j < len(commands):
                c = commands[j] if isinstance(commands[j], dict) else {}
                try:
                    ccode = int(c.get("code") or 0)
                except Exception:
                    ccode = 0
                if ccode != 401:
                    break
                cparams = c.get("parameters") if isinstance(c.get("parameters"), list) else []
                if cparams:
                    lines.append(str(cparams[0] or ""))
                j += 1
            info = infer_maker_speaker(params=params, event_name=event_name, text="\n".join(lines), actor_lookup=actor_lookup)
            speaker = _maker_profile_key(info.get("speaker") or "Unknown", speaker_aliases)
            if speaker and speaker != "Unknown":
                profile = _profile_entry(profiles, speaker)
                for pic_idx, pic_name in recent:
                    if i - pic_idx > 10:
                        continue
                    rel = _image_rel_candidate(game_root, content_root, "pictures", pic_name)
                    similar = _name_similarity_hint(speaker, pic_name)
                    _add_image_candidate(profile, {
                        "kind": "standing",
                        "label": "스탠딩/표시 이미지 후보",
                        "rel_path": rel,
                        "index": 0,
                        "crop_type": "full",
                        "confidence": 0.84 if similar else 0.64,
                        "count": 1,
                        "evidence": f"Show Picture '{pic_name}'가 {speaker} 대사 직전 {i - pic_idx}명령 이내 등장",
                    })
        i += 1


def collect_maker_character_profiles(project_dir: str | os.PathLike[str], data: Dict[int, dict] | None = None) -> Dict[str, Any]:
    """Build character overview profiles for the current RPG Maker project.

    The profile is evidence-based, not absolute. Actor DB links are treated as
    high-confidence, repeated dialogue faces as medium/high-confidence, and Show
    Picture candidates as contextual hints the user can confirm in the UI.
    """
    project_root = Path(project_dir)
    game_root, data_dir, content_root, engine_info = _maker_content_paths_for_project(project_root)
    profiles: Dict[str, Any] = {}
    speaker_aliases = _maker_speaker_alias_map_from_data(data or {})

    actors_path = data_dir / "Actors.json"
    try:
        actors = _read_json(actors_path)
    except Exception:
        actors = []
    if isinstance(actors, list):
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            name = str(actor.get("name") or "").strip()
            if not name:
                continue
            profile_key = _maker_profile_key(name, speaker_aliases)
            if not profile_key:
                continue
            profile = _profile_entry(profiles, profile_key)
            if profile_key != name:
                aliases = profile.setdefault("aliases", [])
                if name not in aliases:
                    aliases.append(name)
            _add_profile_hint(profile, "Actors.json")
            try:
                actor_id = int(actor.get("id") or 0)
            except Exception:
                actor_id = 0
            face_name = str(actor.get("faceName") or "").strip()
            char_name = str(actor.get("characterName") or "").strip()
            battler_name = str(actor.get("battlerName") or "").strip()
            try:
                face_index = int(actor.get("faceIndex") or 0)
            except Exception:
                face_index = 0
            try:
                character_index = int(actor.get("characterIndex") or 0)
            except Exception:
                character_index = 0
            profile["actor"] = {
                "id": actor_id,
                "name": name,
                "nickname": str(actor.get("nickname") or ""),
                "profile": str(actor.get("profile") or ""),
                "faceName": face_name,
                "faceIndex": face_index,
                "characterName": char_name,
                "characterIndex": character_index,
                "battlerName": battler_name,
            }
            if face_name:
                _add_image_candidate(profile, {"kind": "face", "label": "Actors.json 얼굴칩", "rel_path": _image_rel_candidate(game_root, content_root, "faces", face_name), "index": face_index, "crop_type": "face", "confidence": 0.98, "count": 1, "evidence": f"Actors.json actor #{actor_id} faceName/faceIndex"})
            if char_name:
                _add_image_candidate(profile, {"kind": "character", "label": "Actors.json 캐릭터칩", "rel_path": _image_rel_candidate(game_root, content_root, "characters", char_name), "index": character_index, "crop_type": "character", "confidence": 0.96, "count": 1, "evidence": f"Actors.json actor #{actor_id} characterName/characterIndex"})
            if battler_name:
                _add_image_candidate(profile, {"kind": "battler", "label": "Actors.json 전투 스프라이트", "rel_path": _image_rel_candidate(game_root, content_root, "sv_actors", battler_name), "index": 0, "crop_type": "full", "confidence": 0.94, "count": 1, "evidence": f"Actors.json actor #{actor_id} battlerName"})

    for _page_idx, page in (data or {}).items():
        if not isinstance(page, dict):
            continue
        maker_page = page.get("maker_page") or {}
        page_type = str((maker_page or {}).get("page_type") or "map").strip().lower() if isinstance(maker_page, dict) else "map"
        source_file = str((maker_page or {}).get("source_file") or (maker_page or {}).get("map_file") or "").strip() if isinstance(maker_page, dict) else ""
        # Character profile inference should only use actual dialogue contexts.
        # Database/System/Troops rows are terms/battle data and must not become speakers.
        if page_type not in ("", "map", "common_events") or source_file in ("System.json", "Troops.json") or source_file.startswith("DB_"):
            continue
        for item in page.get("data") or []:
            if not isinstance(item, dict):
                continue
            meta = item.get("maker_text_unit") or {}
            if not isinstance(meta, dict):
                continue
            if not _maker_row_is_dialogue_for_profile(item, maker_page):
                continue
            speaker = _maker_row_speaker_for_profile(item)
            if not speaker:
                continue
            profile = _profile_entry(profiles, speaker)
            # Preserve original name as an alias when 화자 번역 changed it.
            orig = _normal_character_key(strip_maker_control_codes((item.get("maker_speaker_original") or meta.get("speaker_original") or "") if isinstance(meta, dict) else item.get("maker_speaker_original") or ""))
            if orig and orig != speaker:
                aliases = profile.setdefault("aliases", [])
                if orig not in aliases:
                    aliases.append(orig)
            profile["text_count"] = int(profile.get("text_count") or 0) + 1
            src = str(item.get("maker_speaker_source") or meta.get("speaker_source") or "unknown")
            counts = profile.setdefault("source_counts", {})
            counts[src] = int(counts.get(src) or 0) + 1
            _add_profile_hint(profile, src)
            _add_profile_sample(profile, item.get("text") or item.get("source_text") or "", translated_text=item.get("translated_text") or "", map_name=str(meta.get("map_name") or maker_page.get("map_name") or ""), event_name=str(meta.get("event_name") or ""), text_type=str(meta.get("text_type") or ""), source_file=str(meta.get("source_file") or meta.get("map_file") or ""))
            _add_profile_appearance(profile, map_name=str(meta.get("map_name") or maker_page.get("map_name") or ""), event_name=str(meta.get("event_name") or ""), source_file=str(meta.get("source_file") or meta.get("map_file") or ""))
            face_name = str(meta.get("face_name") or "").strip()
            if face_name:
                try:
                    face_index = int(meta.get("face_index") or 0)
                except Exception:
                    face_index = 0
                conf = float(meta.get("speaker_confidence") or item.get("maker_speaker_confidence") or 0.76)
                _add_image_candidate(profile, {"kind": "face", "label": "대사 얼굴칩 후보", "rel_path": _image_rel_candidate(game_root, content_root, "faces", face_name), "index": face_index, "crop_type": "face", "confidence": max(0.70, min(0.95, conf)), "count": 1, "evidence": f"대사 TextUnit faceName={face_name} faceIndex={face_index}"})

    actor_lookup = load_maker_actor_lookup(game_root, engine_info)
    trp_actors = load_maker_trp_skit_actor_config(game_root, engine_info)
    trp_display = load_maker_trp_skit_display_config(game_root, engine_info) if trp_actors else {}
    trp_layer_cache: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    try:
        for _map_id, map_name, map_path, map_data in iter_existing_maps(game_root, engine_info):
            events = map_data.get("events") if isinstance(map_data, dict) else []
            if not isinstance(events, list):
                continue
            for event in events:
                if not isinstance(event, dict):
                    continue
                ev_name = _event_name(event)
                pages = event.get("pages")
                if not isinstance(pages, list):
                    continue
                for page in pages:
                    commands = page.get("list") if isinstance(page, dict) else []
                    if isinstance(commands, list):
                        _collect_picture_candidates_from_commands(profiles, commands, event_name=ev_name, map_name=map_name, source_file=map_path.name, game_root=game_root, content_root=content_root, actor_lookup=actor_lookup, speaker_aliases=speaker_aliases)
                        if trp_actors:
                            snapshots = iter_maker_trp_skit_dialogue_compositions(
                                commands,
                                actors_cfg=trp_actors,
                                positions=(trp_display.get("positions") or {}) if isinstance(trp_display, dict) else {},
                                event_name=ev_name,
                                actor_lookup=actor_lookup,
                            )
                            for snapshot in snapshots:
                                speaker = _maker_profile_key(snapshot.get("speaker") or "Unknown", speaker_aliases)
                                if not speaker or speaker == "Unknown":
                                    continue
                                profile = _profile_entry(profiles, speaker)
                                layer_key = (
                                    str(snapshot.get("config_key") or snapshot.get("actor_key") or speaker).casefold(),
                                    str(snapshot.get("pose") or "normal").casefold(),
                                    str(snapshot.get("expression") or "default").casefold(),
                                )
                                layer_info = trp_layer_cache.get(layer_key)
                                if not isinstance(layer_info, dict):
                                    layer_info = resolve_maker_trp_skit_layer_paths(
                                        game_root,
                                        content_root,
                                        snapshot.get("actor_key") or speaker,
                                        snapshot.get("pose"),
                                        snapshot.get("expression"),
                                        actors_cfg=trp_actors,
                                    )
                                    trp_layer_cache[layer_key] = layer_info
                                layers = []
                                if layer_info.get("base_rel_path"):
                                    layers.append({"role": "base_pose", "rel_path": str(layer_info.get("base_rel_path") or ""), "x": 0, "y": 0})
                                if layer_info.get("overlay_rel_path"):
                                    layers.append({"role": "expression_overlay", "rel_path": str(layer_info.get("overlay_rel_path") or ""), "x": 0, "y": 0})
                                if not layers:
                                    continue
                                visible = bool(snapshot.get("visible"))
                                confidence = 0.97 if visible else 0.89
                                resolved_expression = str(layer_info.get("resolved_expression") or snapshot.get("expression") or "default")
                                _add_profile_hint(profile, "TRP_SkitMZ")
                                _add_image_candidate(profile, {
                                    "kind": "plugin_composite",
                                    "label": "플러그인 조합 스탠딩",
                                    "rel_path": str(layers[0].get("rel_path") or ""),
                                    "layers": layers,
                                    "index": 0,
                                    "crop_type": "composite",
                                    "confidence": confidence,
                                    "count": 1,
                                    "plugin_name": "TRP_SkitMZ",
                                    "actor_key": str(snapshot.get("actor_key") or speaker),
                                    "pose": str(layer_info.get("pose") or snapshot.get("pose") or "normal"),
                                    "expression": resolved_expression,
                                    "visible_at_dialogue": visible,
                                    "evidence": (
                                        f"TRP_SkitMZ | map={map_name} | event={ev_name} | "
                                        f"actor={snapshot.get('actor_key') or speaker} | "
                                        f"pose={layer_info.get('pose') or snapshot.get('pose') or 'normal'} | "
                                        f"expression={resolved_expression} | visible={str(visible).lower()}"
                                    ),
                                })
    except Exception:
        pass

    prompts = load_maker_character_prompts(project_root)
    chars = prompts.get("characters") or {}
    for name, profile in profiles.items():
        profile["profile_prompt"] = normalize_maker_character_prompt_profile(chars.get(name) if isinstance(chars, dict) else {}, speaker=name)
        images = profile.get("images") or []
        images.sort(key=lambda x: (float(x.get("confidence") or 0.0), int(x.get("count") or 0)), reverse=True)
        profile["images"] = images[:24]
        apps = profile.get("appearances") or []
        apps.sort(key=lambda x: int(x.get("count") or 0), reverse=True)
        profile["appearances"] = apps[:30]
        try:
            best_img = max([float(x.get("confidence") or 0.0) for x in images] or [0.0])
        except Exception:
            best_img = 0.0
        try:
            image_count = sum(int(x.get("count") or 0) for x in images if isinstance(x, dict))
        except Exception:
            image_count = 0
        try:
            appearance_count = sum(int(x.get("count") or 0) for x in apps if isinstance(x, dict))
        except Exception:
            appearance_count = 0
        profile["image_count"] = int(image_count)
        profile["appearance_count"] = int(appearance_count)
        profile["profile_count"] = int(profile.get("text_count") or 0)
        text_boost = min(0.15, int(profile.get("text_count") or 0) / 100.0)
        actor_boost = 0.10 if profile.get("actor") else 0.0
        profile["confidence"] = round(min(1.0, best_img + text_boost + actor_boost), 3)

    # Only actual dialogue speakers remain as profile list items.  Actor/image
    # candidates with no dialogue are evidence, not characters to show here.
    profiles = {k: v for k, v in profiles.items() if int((v or {}).get("text_count") or 0) > 0}
    out = {"schema_version": 1, "generated_at": datetime.now().isoformat(timespec="seconds"), "project_kind": "ysb_game_editor", "engine": engine_info, "character_count": len(profiles), "characters": {k: profiles[k] for k in sorted(profiles.keys(), key=lambda x: x.casefold())}}
    try:
        path = maker_character_profiles_path(project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return out


_MAKER_CONTROL_CODE_RE = re.compile(
    r"(?:\\|¥)(?:[A-Za-z가-힣_]+(?:\[[^\]\r\n]*\])?|[!\.\|\^><{}$#])"
)

# 전투/시스템 메시지에 쓰이는 RPG Maker 치환 변수. 예: %1, %2, %3.
# 이 값은 실제 게임 런타임에서 이름/수치로 치환되는 표시 코드이므로
# 번역 API에는 원문 그대로 보낸다. 가짜 보호 토큰으로 치환하지 않는다.
_MAKER_MESSAGE_PLACEHOLDER_RE = re.compile(r"%(?:\d+)")

# AI 자동 제어코드 반영용 불투명 토큰. 실제 RPG Maker 제어코드는 API 입력에서
# 제거하고, 의미 위치만 이 토큰으로 표시한다. 모델 응답이 토큰을 정확히 보존했을
# 때만 원래 코드를 되돌리므로 코드 인수 변형/누락을 프로그램 쪽에서 막을 수 있다.
_MAKER_AI_CONTROL_TOKEN_RE = re.compile(r"⟦YSB_CC_(\d{4})⟧", re.IGNORECASE)
_MAKER_AI_CONTROL_TOKEN_FUZZY_RE = re.compile(
    r"(?:⟦|\[\[)\s*YSB[ _-]*CC[ _-]*(\d{4})\s*(?:⟧|\]\])",
    re.IGNORECASE,
)


def _canonicalize_maker_ai_control_tokens(text: Any) -> str:
    raw = str(text or "")
    return _MAKER_AI_CONTROL_TOKEN_FUZZY_RE.sub(
        lambda m: f"⟦YSB_CC_{int(m.group(1)):04d}⟧",
        raw,
    )


def _maker_control_code_requires_line_edge(code: Any) -> bool:
    """Return True only for controls whose edge position is structurally important.

    Semantic/range controls such as ``\\C[n]`` are deliberately movable: the AI may
    place them around the corresponding translated phrase. Layout/font-position and
    timing controls that start or finish a physical message line stay anchored.
    """
    raw = str(code or "")
    body = raw[1:] if raw.startswith(("\\", "¥")) else raw
    name_match = re.match(r"([A-Za-z가-힣_]+)", body)
    name = (name_match.group(1) if name_match else body[:1]).upper()
    if name in {"FS", "PX", "PY", "SE"}:
        return True
    return body[:1] in {"!", ".", "|", "^"}


def _maker_ai_control_token_line_layout(
    text: Any,
    mapping: Iterable[Tuple[str, str]] | None = None,
) -> List[Dict[str, Any]]:
    """Return per-line token order and structurally anchored edge tokens.

    All tokens must remain on their source physical line and keep their order.
    Only controls with a line-level role are required to stay at an edge. Semantic
    controls (for example a color pair) may move with their translated phrase.
    """
    normalized = _canonicalize_maker_ai_control_tokens(text).replace("\r\n", "\n").replace("\r", "\n")
    token_to_code = {
        _canonicalize_maker_ai_control_tokens(token): str(code or "")
        for token, code in (mapping or [])
    }
    layout: List[Dict[str, Any]] = []
    for line in normalized.split("\n"):
        matches = list(_MAKER_AI_CONTROL_TOKEN_RE.finditer(line))
        tokens = [m.group(0) for m in matches]

        edge_prefix_tokens: List[str] = []
        cursor = 0
        for m in matches:
            between = line[cursor:m.start()]
            if between.strip():
                break
            edge_prefix_tokens.append(m.group(0))
            cursor = m.end()

        edge_suffix_tokens_rev: List[str] = []
        cursor = len(line)
        for m in reversed(matches):
            between = line[m.end():cursor]
            if between.strip():
                break
            edge_suffix_tokens_rev.append(m.group(0))
            cursor = m.start()
        edge_suffix_tokens = list(reversed(edge_suffix_tokens_rev))

        if token_to_code:
            prefix_tokens = [
                token for token in edge_prefix_tokens
                if _maker_control_code_requires_line_edge(token_to_code.get(token, ""))
            ]
            suffix_tokens = [
                token for token in edge_suffix_tokens
                if _maker_control_code_requires_line_edge(token_to_code.get(token, ""))
            ]
        else:
            # Compatibility fallback for a spec created without token/code metadata.
            prefix_tokens = edge_prefix_tokens
            suffix_tokens = edge_suffix_tokens

        layout.append({
            "tokens": tokens,
            "prefix_tokens": prefix_tokens,
            "suffix_tokens": suffix_tokens,
        })
    return layout


def _maker_raw_control_code_lines(text: Any) -> List[List[str]]:
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return [[m.group(0) for m in _MAKER_CONTROL_CODE_RE.finditer(line)] for line in raw.split("\n")]


def protect_maker_control_codes_for_ai(text: Any) -> Tuple[str, List[Tuple[str, str]]]:
    r"""Replace every Maker control code with a stable opaque AI token.

    The model never needs to reproduce ``\C[26]`` or another real command. It only
    moves exact opaque tokens with the translated phrase. The original command text
    stays in ``mapping`` and is restored only after strict validation.
    """
    raw = str(text or "")
    mapping: List[Tuple[str, str]] = []

    def repl(match):
        token = f"⟦YSB_CC_{len(mapping) + 1:04d}⟧"
        mapping.append((token, match.group(0)))
        return token

    return _MAKER_CONTROL_CODE_RE.sub(repl, raw), mapping


def build_maker_control_code_auto_context(raw_text: Any, tokenized_text: Any, mapping: Iterable[Tuple[str, str]] | None) -> str:
    pairs = [(str(token), str(code)) for token, code in (mapping or [])]
    if not pairs:
        return ""
    templates = get_runtime_prompt_templates()
    entry_template = templates.get("control_code_mapping_entry", "")
    mapping_lines = "\n".join(
        render_prompt_template(entry_template, TOKEN=token, CODE=code)
        for token, code in pairs
    )
    return render_prompt_template(
        templates.get("control_code_item_context", ""),
        RAW_TEXT=str(raw_text or ""),
        TOKENIZED_TEXT=str(tokenized_text or ""),
        TOKEN_MAPPING=mapping_lines,
    )


def _maker_control_spec_parts(control_map: Any) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
    if isinstance(control_map, dict):
        raw_mapping = control_map.get("mapping") or []
        meta = dict(control_map)
    else:
        raw_mapping = control_map or []
        meta = {}
    pairs: List[Tuple[str, str]] = []
    for pair in raw_mapping:
        try:
            token, code = pair
        except Exception:
            continue
        token = str(token or "")
        code = str(code or "")
        if token and code:
            pairs.append((token, code))
    return pairs, meta


def restore_maker_translation_text_checked(
    text: Any,
    control_map: Any = None,
    raw_text: Any = "",
) -> Tuple[str, str, Dict[str, Any]]:
    """Validate AI tokens, restore exact codes, or fall back safely.

    Status values:
    - ``none``: automatic placement was not requested for this item.
    - ``applied``: every opaque token was valid and restored.
    - ``applied_raw``: the model returned the exact original raw codes instead.
    - ``fallback_edge``: token validation failed, but deterministic edge restore was safe.
    - ``failed_plain``: middle/range placement could not be trusted; plain translation is kept.
    """
    translated = _canonicalize_maker_ai_control_tokens(text)
    mapping, meta = _maker_control_spec_parts(control_map)
    if not mapping:
        return translated, "none", {}

    expected_tokens = [token for token, _code in mapping]
    expected_codes = [code for _token, code in mapping]
    seen_tokens = [m.group(0) for m in _MAKER_AI_CONTROL_TOKEN_RE.finditer(translated)]
    normalized_expected = [_canonicalize_maker_ai_control_tokens(x) for x in expected_tokens]
    expected_line_count = int(meta.get("expected_line_count") or 0) if isinstance(meta, dict) else 0
    line_count_ok = not expected_line_count or translated.count("\n") + 1 == expected_line_count
    raw_codes_in_output = [m.group(0) for m in _MAKER_CONTROL_CODE_RE.finditer(translated)]

    expected_layout = meta.get("expected_token_line_layout") if isinstance(meta, dict) else None
    if not isinstance(expected_layout, list):
        expected_layout = _maker_ai_control_token_line_layout(meta.get("normalized_source") or "", mapping)
    seen_layout = _maker_ai_control_token_line_layout(translated, mapping)

    def _layout_matches(expected: Any, seen: Any) -> bool:
        if not isinstance(expected, list) or not isinstance(seen, list) or len(expected) != len(seen):
            return False
        for expected_line, seen_line in zip(expected, seen):
            if not isinstance(expected_line, dict) or not isinstance(seen_line, dict):
                return False
            expected_line_tokens = [
                _canonicalize_maker_ai_control_tokens(token)
                for token in (expected_line.get("tokens") or [])
            ]
            expected_prefix = [
                _canonicalize_maker_ai_control_tokens(token)
                for token in (expected_line.get("prefix_tokens") or [])
            ]
            expected_suffix = [
                _canonicalize_maker_ai_control_tokens(token)
                for token in (expected_line.get("suffix_tokens") or [])
            ]
            seen_line_tokens = list(seen_line.get("tokens") or [])
            seen_prefix = list(seen_line.get("prefix_tokens") or [])
            seen_suffix = list(seen_line.get("suffix_tokens") or [])
            # A token may move with its translated phrase inside the same physical
            # line, but no token may cross a line. Codes that originally preceded
            # all visible text must remain at the beginning. The same rule applies
            # to trailing edge codes. Extra inline/range tokens are allowed at an
            # edge when their translated phrase itself moved to that edge.
            if seen_line_tokens != expected_line_tokens:
                return False
            if expected_prefix and seen_prefix[:len(expected_prefix)] != expected_prefix:
                return False
            if expected_suffix and seen_suffix[-len(expected_suffix):] != expected_suffix:
                return False
        return True

    line_layout_ok = _layout_matches(expected_layout, seen_layout)
    valid_tokens = (
        seen_tokens == normalized_expected
        and len(seen_tokens) == len(set(seen_tokens))
        and not raw_codes_in_output
        and line_count_ok
        and line_layout_ok
    )
    if valid_tokens:
        restored = translated
        for token, code in zip(normalized_expected, expected_codes):
            restored = restored.replace(token, code, 1)
        restored_codes = [m.group(0) for m in _MAKER_CONTROL_CODE_RE.finditer(restored)]
        restored_code_lines = _maker_raw_control_code_lines(restored)
        expected_code_lines = meta.get("expected_raw_code_lines") if isinstance(meta, dict) else None
        if not isinstance(expected_code_lines, list):
            expected_code_lines = _maker_raw_control_code_lines(meta.get("raw_text") or raw_text or "")
        if restored_codes == expected_codes and restored_code_lines == expected_code_lines:
            return restored, "applied", {
                "count": len(mapping),
                "line_count_ok": True,
                "line_layout_ok": True,
            }

    # Some models ignore the opaque-token instruction and emit the exact original
    # commands. Accept only an exact per-line ordered match with the original edge
    # placement. Any changed argument, line move, or displaced edge code is rejected.
    raw_layout_ok = False
    expected_code_lines = meta.get("expected_raw_code_lines") if isinstance(meta, dict) else None
    if not isinstance(expected_code_lines, list):
        expected_code_lines = _maker_raw_control_code_lines(meta.get("raw_text") or raw_text or "")
    if not seen_tokens and raw_codes_in_output == expected_codes and line_count_ok:
        token_index = 0

        def _raw_to_token(match):
            nonlocal token_index
            if token_index >= len(normalized_expected):
                return match.group(0)
            token = normalized_expected[token_index]
            token_index += 1
            return token

        raw_as_tokens = _MAKER_CONTROL_CODE_RE.sub(_raw_to_token, translated)
        raw_layout_ok = (
            token_index == len(normalized_expected)
            and _maker_raw_control_code_lines(translated) == expected_code_lines
            and _layout_matches(expected_layout, _maker_ai_control_token_line_layout(raw_as_tokens, mapping))
        )
        if raw_layout_ok:
            return translated, "applied_raw", {
                "count": len(mapping),
                "line_count_ok": True,
                "line_layout_ok": True,
            }

    # Never leave malformed or invented tokens/codes in the user's translation.
    plain = _MAKER_AI_CONTROL_TOKEN_RE.sub("", translated)
    plain = _MAKER_AI_CONTROL_TOKEN_FUZZY_RE.sub("", plain)
    plain = strip_maker_control_codes(plain)
    source_raw = str(raw_text or meta.get("raw_text") or "")
    if source_raw:
        fallback, edge_status = apply_maker_edge_control_codes(plain, source_raw)
        if edge_status in {"applied", "already"}:
            return fallback, "fallback_edge", {
                "expected_tokens": normalized_expected,
                "seen_tokens": seen_tokens,
                "line_count_ok": line_count_ok,
                "line_layout_ok": line_layout_ok,
                "raw_layout_ok": raw_layout_ok,
            }
    return plain, "failed_plain", {
        "expected_tokens": normalized_expected,
        "seen_tokens": seen_tokens,
        "raw_codes": raw_codes_in_output,
        "line_count_ok": line_count_ok,
        "line_layout_ok": line_layout_ok,
        "raw_layout_ok": raw_layout_ok,
    }


def strip_maker_control_codes(text: Any) -> str:
    """Return the human-readable text with RPG Maker control codes removed.

    This is used as the translation/export display layer.  The original raw text
    is still kept in the project row so the user can manually restore effects.
    """
    return _MAKER_CONTROL_CODE_RE.sub("", str(text or ""))


def _analyze_maker_control_codes_flat(raw_text: Any) -> Dict[str, Any]:
    """Classify control-code placement for one physical line."""
    raw = str(raw_text or "")
    matches = list(_MAKER_CONTROL_CODE_RE.finditer(raw))
    plain = strip_maker_control_codes(raw)
    if not matches:
        return {
            "raw_text": raw,
            "plain_text": plain,
            "has_control_codes": False,
            "placement": "none",
            "prefix_codes": "",
            "suffix_codes": "",
            "middle_codes": [],
            "control_codes": [],
            "auto_restorable": False,
        }

    segments: List[Tuple[str, str]] = []
    pos = 0
    for m in matches:
        if m.start() > pos:
            segments.append(("text", raw[pos:m.start()]))
        segments.append(("code", m.group(0)))
        pos = m.end()
    if pos < len(raw):
        segments.append(("text", raw[pos:]))

    text_indexes = [i for i, (kind, value) in enumerate(segments) if kind == "text" and str(value or "").strip()]
    if not text_indexes:
        prefix = "".join(value for kind, value in segments if kind == "code")
        return {
            "raw_text": raw,
            "plain_text": plain,
            "has_control_codes": True,
            "placement": "edge",
            "prefix_codes": prefix,
            "suffix_codes": "",
            "middle_codes": [],
            "control_codes": [m.group(0) for m in matches],
            "auto_restorable": bool(prefix),
        }

    first_text = min(text_indexes)
    last_text = max(text_indexes)
    prefix_codes = "".join(value for i, (kind, value) in enumerate(segments) if kind == "code" and i < first_text)
    suffix_codes = "".join(value for i, (kind, value) in enumerate(segments) if kind == "code" and i > last_text)
    middle_codes = [value for i, (kind, value) in enumerate(segments) if kind == "code" and first_text < i < last_text]
    placement = "middle" if middle_codes else "edge"
    return {
        "raw_text": raw,
        "plain_text": plain,
        "has_control_codes": True,
        "placement": placement,
        "prefix_codes": prefix_codes,
        "suffix_codes": suffix_codes,
        "middle_codes": middle_codes,
        "control_codes": [m.group(0) for m in matches],
        "auto_restorable": placement == "edge" and bool(prefix_codes or suffix_codes),
    }


def _analyze_maker_control_codes_multiline(raw_text: Any) -> Dict[str, Any] | None:
    """Treat each source line as an independent restoration unit.

    RPG Maker dialogue is often stored as multiple visible lines.  A code at the
    beginning of line 2 must not be treated as a dangerous middle code for the
    whole paragraph.  If every non-empty line is edge-only, the row is safe for
    line-wise auto-restore.
    """
    raw = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    if "\n" not in raw:
        return None
    if not _MAKER_CONTROL_CODE_RE.search(raw):
        return None
    lines = raw.split("\n")
    units: List[Dict[str, Any]] = []
    control_codes: List[str] = []
    middle_codes: List[str] = []
    has_codes = False
    any_restorable = False
    plain_lines: List[str] = []
    for line_no, line in enumerate(lines):
        info = _analyze_maker_control_codes_flat(line)
        plain = str(info.get("plain_text") or "")
        plain_lines.append(plain)
        line_has_codes = bool(info.get("has_control_codes"))
        has_codes = has_codes or line_has_codes
        control_codes.extend(list(info.get("control_codes") or []))
        if str(line or "").strip() == "" and not line_has_codes:
            units.append({
                "line_index": line_no,
                "raw_text": line,
                "plain_text": plain,
                "prefix_codes": "",
                "suffix_codes": "",
                "placement": "none",
                "auto_restorable": False,
                "has_control_codes": False,
            })
            continue
        if info.get("placement") == "middle":
            middle_codes.extend(list(info.get("middle_codes") or []))
        if info.get("auto_restorable"):
            any_restorable = True
        units.append({
            "line_index": line_no,
            "raw_text": line,
            "plain_text": plain,
            "prefix_codes": str(info.get("prefix_codes") or ""),
            "suffix_codes": str(info.get("suffix_codes") or ""),
            "placement": str(info.get("placement") or "none"),
            "auto_restorable": bool(info.get("auto_restorable")),
            "has_control_codes": line_has_codes,
        })
    if not has_codes:
        return None
    linewise_safe = not middle_codes and any_restorable
    return {
        "raw_text": raw,
        "plain_text": "\n".join(plain_lines),
        "has_control_codes": True,
        "placement": "edge" if linewise_safe else "middle",
        "prefix_codes": "",
        "suffix_codes": "",
        "middle_codes": middle_codes,
        "control_codes": control_codes,
        "auto_restorable": bool(linewise_safe),
        "linewise_restore": bool(linewise_safe),
        "line_units": units,
    }


def analyze_maker_control_codes(text: Any) -> Dict[str, Any]:
    """Classify RPG Maker control-code placement for UI assistance.

    placement:
    - none: no control code
    - edge: all control codes are before/after the meaningful text.  For
      multi-line dialogue, each physical line is judged independently.
    - middle: at least one control code appears between meaningful text segments
      within the same line and requires manual handling.
    """
    raw = str(text or "")
    info = _analyze_maker_control_codes_multiline(raw)
    if info is not None:
        return info
    return _analyze_maker_control_codes_flat(raw)



_MAKER_SENTENCE_END_CHARS = set("。.!！?？…♪♥♡★☆、,，;；:：")
_MAKER_BODY_RESET_CODE_RE = re.compile(r"^(?:\\|¥)(?:C\[0\]|FS\[[^\]]+\]|AT\[[^\]]+\]|FB\[?0?\]?|FI\[?0?\]?|OC\[[^\]]+\]|OW\[[^\]]+\])$", re.IGNORECASE)


def _maker_control_segments(text: Any) -> List[Tuple[str, str]]:
    """Split text into ('code'|'text', value) segments without hiding codes."""
    raw = str(text or "")
    out: List[Tuple[str, str]] = []
    pos = 0
    for m in _MAKER_CONTROL_CODE_RE.finditer(raw):
        if m.start() > pos:
            out.append(("text", raw[pos:m.start()]))
        out.append(("code", m.group(0)))
        pos = m.end()
    if pos < len(raw):
        out.append(("text", raw[pos:]))
    return out


def _maker_split_edge_codes(line: Any) -> Dict[str, str]:
    """Return leading codes/text/trailing codes for one visual line.

    Spaces between adjacent leading control codes stay with the leading-code block
    because MV/MZ plugins often write them for readability, not as displayed text.
    """
    raw = str(line or "")
    segs = _maker_control_segments(raw)
    first = None
    last = None
    for i, (kind, value) in enumerate(segs):
        if kind == "text" and str(value or "").strip():
            first = i if first is None else first
            last = i
    if first is None:
        return {"leading_codes": raw, "text": "", "trailing_codes": "", "plain": ""}
    leading_parts: List[str] = []
    for kind, value in segs[:first]:
        leading_parts.append(value)
    text_parts: List[str] = []
    for kind, value in segs[first:last + 1]:
        text_parts.append(value)
    trailing_parts: List[str] = []
    for kind, value in segs[last + 1:]:
        trailing_parts.append(value)
    text_raw = "".join(text_parts)
    return {
        "leading_codes": "".join(leading_parts),
        "text": text_raw,
        "trailing_codes": "".join(trailing_parts),
        "plain": strip_maker_control_codes(text_raw).strip(),
    }


def _maker_name_like_plain_text(text: Any) -> bool:
    plain = str(text or "").strip()
    if not plain:
        return False
    if "\n" in plain or "\r" in plain:
        return False
    if len(plain) > 24:
        return False
    if any(ch in _MAKER_SENTENCE_END_CHARS for ch in plain):
        return False
    # Names normally do not contain long whitespace-separated phrases.
    if len([x for x in re.split(r"\s+", plain) if x]) > 3:
        return False
    return True


def split_maker_inline_speaker_text(text: Any) -> Dict[str, Any]:
    """Detect the MV/plugin pattern where the first message line is an inline name.

    The user-facing rule is:
    - control codes stay visible in the editor;
    - API translation sees plain text only;
    - first-line name codes stay in the speaker cell;
    - trailing reset/body codes after the name move to the body text front.
    """
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    if len(lines) < 2:
        return {"enabled": False, "raw_text": raw, "body_text": raw}
    first = lines[0]
    rest = "\n".join(lines[1:])
    if not rest.strip():
        return {"enabled": False, "raw_text": raw, "body_text": raw}
    split = _maker_split_edge_codes(first)
    plain = str(split.get("plain") or "").strip()
    if not _maker_name_like_plain_text(plain):
        return {"enabled": False, "raw_text": raw, "body_text": raw, "speaker_plain": plain}
    leading = str(split.get("leading_codes") or "")
    visible_text = str(split.get("text") or "").strip()
    trailing = str(split.get("trailing_codes") or "")
    # If a name line ends with reset/body-prep codes, treat them as the first
    # codes for the dialogue body.  This preserves the visible code structure
    # while avoiding a hidden suffix stuck to the speaker name.
    speaker_raw = (leading + visible_text).strip()
    body_prefix = trailing
    body_text = (body_prefix + rest) if body_prefix else rest
    return {
        "enabled": True,
        "raw_text": raw,
        "speaker_plain": plain,
        "speaker_raw_visible": speaker_raw or plain,
        "speaker_prefix_codes": leading,
        "body_prefix_codes": body_prefix,
        "body_text": body_text,
        "body_plain": strip_maker_control_codes(body_text),
        "body_line_reserved": True,
        "original_first_line": first,
        "original_body_text": rest,
    }


def maker_item_plain_speaker(item: Dict[str, Any] | None) -> str:
    if not isinstance(item, dict):
        return "Unknown"
    meta = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
    for value in (
        meta.get("speaker_plain") if isinstance(meta, dict) else "",
        item.get("maker_speaker_plain"),
        strip_maker_control_codes(item.get("maker_speaker") or ""),
    ):
        key = _normal_character_key(value)
        if key:
            return key
    return maker_item_speaker(item)


def _maker_rebuild_inline_speaker_from_template(raw_template: Any, speaker_text: Any) -> str:
    """Insert a plain speaker name back into the original inline-name code shell."""
    speaker = str(speaker_text or "").strip()
    raw = str(raw_template or "")
    if not raw:
        return speaker
    try:
        split = _maker_split_edge_codes(raw)
        leading = str(split.get("leading_codes") or "")
        trailing = str(split.get("trailing_codes") or "")
        old_text = str(split.get("text") or "")
        # Preserve the user's explicit code shell, but replace only the visible
        # name segment.  If the template parser cannot find a text segment, fall
        # back to appending the speaker after the leading code block.
        if old_text.strip():
            return f"{leading}{speaker}{trailing}"
        return f"{leading}{speaker}{trailing}"
    except Exception:
        plain = strip_maker_control_codes(raw).strip()
        if plain and plain in raw:
            return raw.replace(plain, speaker, 1)
        return raw + speaker




def _maker_speaker_has_visible_codes(value: Any) -> bool:
    """True when a speaker/name-window value contains Maker control codes.

    MV inline names and MZ name-window plugins can both style the displayed
    speaker name with codes.  The normal table must show the plain name, while
    the speaker-translation dialog keeps this raw shell visible for review and
    write-back.
    """
    try:
        return bool(analyze_maker_control_codes(value).get("has_control_codes"))
    except Exception:
        return bool(_MAKER_CONTROL_CODE_RE.search(str(value or "")))


def _maker_rebuild_speaker_shell(raw_template: Any, speaker_text: Any) -> str:
    """Put a plain speaker name back into a control-code speaker shell.

    Shared by MV inline-name rows and MZ name-window rows.  It preserves the
    codes around the visible name and replaces only the human-readable segment.
    """
    return _maker_rebuild_inline_speaker_from_template(raw_template, speaker_text)


def _apply_plain_speaker_to_show_text_header(cmd: Dict[str, Any], item: Dict[str, Any]) -> None:
    """Update an MZ Show Text name-window parameter from the plain speaker field.

    MV does not have a native params[4] name window, but MZ does.  Keep this
    function harmless for MV by requiring an existing 5th parameter.  Inline
    first-line speakers are handled by compose_maker_inline_speaker_writeback(),
    so they must not also overwrite params[4].
    """
    if not isinstance(cmd, dict) or not isinstance(item, dict):
        return
    meta = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
    if bool(meta.get("inline_speaker")):
        return
    params = cmd.get("parameters")
    if not isinstance(params, list) or len(params) < 5:
        return
    current = str(params[4] or "")
    # Only touch real name-window slots.  Do not invent one for MV-style rows.
    if not current and str(meta.get("speaker_source") or "") != "name_window":
        return
    plain = str(
        item.get("maker_speaker")
        or item.get("maker_speaker_plain")
        or meta.get("speaker_plain")
        or meta.get("speaker")
        or ""
    ).strip()
    if not plain or plain.lower() in {"unknown", "none", "null"}:
        return
    raw_template = str(meta.get("speaker_raw_visible") or current or "")
    if raw_template and _maker_speaker_has_visible_codes(raw_template):
        params[4] = _maker_rebuild_speaker_shell(raw_template, plain)
    else:
        params[4] = plain

def compose_maker_inline_speaker_writeback(item: Dict[str, Any], body_text: str) -> str:
    """Rebuild a first-line speaker message while keeping visible control codes.

    The editor's speaker column is intentionally plain.  The original control-code
    shell lives in maker_text_unit.speaker_raw_visible so users can inspect it in
    the speaker-translation dialog without polluting the normal table.  Write-back
    puts the translated/plain speaker name back into that shell, then joins the
    body prefix codes and translated body.
    """
    meta = item.get("maker_text_unit") if isinstance(item, dict) else None
    if not isinstance(meta, dict) or not bool(meta.get("inline_speaker")):
        return str(body_text or "")
    speaker_plain = str(item.get("maker_speaker") or item.get("speaker") or meta.get("speaker_plain") or "").strip()
    if not speaker_plain:
        speaker_plain = str(meta.get("speaker_plain") or "").strip()
    raw_template = str(meta.get("speaker_raw_visible") or "")
    speaker_line = _maker_rebuild_inline_speaker_from_template(raw_template, speaker_plain) if raw_template else speaker_plain

    body = str(body_text or "")
    prefix = str(meta.get("body_prefix_codes") or "")
    if prefix and body.strip() and not body.lstrip().startswith(prefix):
        body = prefix + body
    if speaker_line and body:
        return speaker_line + "\n" + body
    if speaker_line:
        return speaker_line
    return body

def _apply_line_edge_control_codes(translated: str, info: Dict[str, Any]) -> Tuple[str, str]:
    """Apply line-wise edge codes when the source had explicit newlines."""
    if not str(translated or "").strip():
        return translated, "empty"
    units = list(info.get("line_units") or [])
    if not units:
        return translated, "manual"
    translated_norm = str(translated or "").replace("\r\n", "\n").replace("\r", "\n")
    trans_lines = translated_norm.split("\n")
    if len(trans_lines) != len(units):
        # Do not guess line mapping.  The user's rule is that each source line is
        # one restoration unit, so mismatched translation lines need manual review.
        return translated_norm, "manual"
    changed = False
    out_lines: List[str] = []
    for t_line, unit in zip(trans_lines, units):
        line = str(t_line or "")
        prefix = str(unit.get("prefix_codes") or "")
        suffix = str(unit.get("suffix_codes") or "")
        if unit.get("placement") == "middle":
            return translated_norm, "manual"
        if not (prefix or suffix):
            out_lines.append(line)
            continue
        if prefix and not line.startswith(prefix):
            line = prefix + line
            changed = True
        if suffix and not line.endswith(suffix):
            line = line + suffix
            changed = True
        out_lines.append(line)
    new_text = "\n".join(out_lines)
    return new_text, "applied" if changed else "already"


def apply_maker_edge_control_codes(translated_text: Any, raw_text: Any) -> Tuple[str, str]:
    """Apply edge-only control codes from raw_text to translated_text.

    Returns (new_text, status):
    - applied: translated text changed
    - already: translated text already had the same edge codes
    - empty: no translated text to update
    - none: no control codes
    - manual: middle control codes require manual handling

    Multi-line source text is handled line by line.  For example:
    [C1]line one\n[C1]line two[C0]
    restores each line's leading/trailing codes independently.
    """
    translated = str(translated_text or "")
    if not translated.strip():
        return translated, "empty"
    info = analyze_maker_control_codes(raw_text)
    if not info.get("has_control_codes"):
        return translated, "none"
    if info.get("linewise_restore"):
        return _apply_line_edge_control_codes(translated, info)
    if info.get("placement") != "edge" or not info.get("auto_restorable"):
        return translated, "manual"
    prefix = str(info.get("prefix_codes") or "")
    suffix = str(info.get("suffix_codes") or "")
    if prefix and translated.startswith(prefix) and (not suffix or translated.endswith(suffix)):
        return translated, "already"
    if suffix and translated.endswith(suffix) and (not prefix or translated.startswith(prefix)):
        return translated, "already"
    new_text = f"{prefix}{translated}{suffix}"
    return new_text, "applied"


def is_maker_text_item(item: Dict[str, Any] | None) -> bool:
    return isinstance(item, dict) and isinstance(item.get("maker_text_unit"), dict)


def protect_maker_control_codes(text: Any) -> Tuple[str, List[Tuple[str, str]]]:
    r"""Return Maker translation text without artificial placeholder tokens.

    쯔꾸르 제어문자(\N[1], \V[3], \C[2] 등)는 strip/analyze 단계에서
    번역용 plain_text에서 제거한다. 전투/시스템 메시지 치환 변수(%1, %2 등)는
    게임 원본 코드이므로 번역 API에 그대로 보낸다.

    과거처럼 ⟦YSB_TAG_000⟧ 같은 가짜 보호 토큰으로 치환하지 않는다.
    모델이 가짜 토큰 자체를 번역하거나 변형할 위험이 %1을 직접 보내는 것보다
    작지 않기 때문이다.
    """
    return str(text or ""), []


def restore_maker_control_codes(text: Any, mapping: Iterable[Tuple[str, str]] | None = None) -> str:
    """Compatibility no-op for older translation flow hooks."""
    return str(text or "")


def maker_item_speaker(item: Dict[str, Any] | None) -> str:
    if not isinstance(item, dict):
        return "Unknown"
    meta = item.get("maker_text_unit") or {}
    if not isinstance(meta, dict):
        meta = {}
    # Internal prompt/profile identity should use the clean speaker name.  The
    # visible table cell may include RPG Maker control codes for inline speakers.
    for value in (
        meta.get("speaker_plain"),
        item.get("maker_speaker_plain"),
        strip_maker_control_codes(item.get("maker_speaker") or ""),
        meta.get("speaker"),
        meta.get("face_name"),
        meta.get("event_name"),
    ):
        key = _normal_character_key(value)
        if key:
            return key
    return "Unknown"


def build_maker_translation_context(item: Dict[str, Any] | None, prompts: Dict[str, Any] | None = None) -> str:
    """Build concise per-text RPG Maker context for AI translation."""
    if not is_maker_text_item(item):
        return ""
    meta = item.get("maker_text_unit") or {}
    if not isinstance(meta, dict):
        meta = {}
    speaker = maker_item_speaker(item)
    parts: List[str] = []
    source_kind = str(meta.get("source_kind") or "map")

    # Row context is sent once per JSON item, so keep it extremely small.
    # Global RPG Maker/API rules are already in the system prompt.
    if source_kind == "speaker":
        parts.append("Page: Speaker Translation")
    elif source_kind == "database":
        if meta.get("map_name"):
            parts.append(f"Page: {meta.get('map_name')}")
        if meta.get("db_kind"):
            parts.append(f"DB: {meta.get('db_kind')}")
        if meta.get("db_id") is not None:
            parts.append(f"DB ID: {meta.get('db_id')}")
        if meta.get("db_field"):
            parts.append(f"Field: {meta.get('db_field')}")
    elif source_kind == "troop_event":
        parts.append("Page: Battle Troops")
        if meta.get("event_name"):
            parts.append(f"Troop: {meta.get('event_name')}")
        if meta.get("page_index") is not None:
            try:
                parts.append(f"Battle page: {int(meta.get('page_index')) + 1}")
            except Exception:
                pass
    elif source_kind == "common_event":
        parts.append("Page: Common Events")
        if meta.get("event_name"):
            parts.append(f"Common event: {meta.get('event_name')}")
    else:
        if meta.get("map_name"):
            parts.append(f"Map: {meta.get('map_name')}")
        if meta.get("event_name"):
            parts.append(f"Event: {meta.get('event_name')}")

    if meta.get("text_type"):
        parts.append(f"Type: {meta.get('text_type')}")
    if speaker and source_kind != "speaker":
        parts.append(f"Speaker: {speaker}")
    if meta.get("face_name"):
        parts.append(f"Face: {meta.get('face_name')}")

    # Prompt text must be lifted into the system prompt once per API chunk.
    # Never repeat the full common prompt inside every row context.
    templates = get_runtime_prompt_templates()
    if source_kind == "speaker":
        speaker_prompt = str(templates.get("speaker_name_prompt") or "").strip()
        if speaker_prompt:
            parts.append(f"{PROMPT_BLOCK_BEGIN}\n{speaker_prompt}\n{PROMPT_BLOCK_END}")
    elif source_kind == "database":
        # Project-specific DB instructions remain data, while the entire wrapper
        # and built-in wording are controlled by the active editable preset.
        system_prompt = build_maker_system_prompt_text(prompts)
        database_prompt = render_prompt_template(
            templates.get("database_prompt", ""),
            PROJECT_DB_PROMPT=system_prompt,
        )
        if database_prompt:
            parts.append(f"{PROMPT_BLOCK_BEGIN}\n{database_prompt}\n{PROMPT_BLOCK_END}")
    elif source_kind == "troop_event":
        battle_prompt = str(templates.get("battle_event_prompt") or "").strip()
        if battle_prompt:
            parts.append(f"{PROMPT_BLOCK_BEGIN}\n{battle_prompt}\n{PROMPT_BLOCK_END}")
    else:
        # Character prompt must contain only the speaker-specific profile.
        # The common/default prompt is sent through the engine system prompt once.
        char_prompt = build_maker_character_prompt_text(prompts, speaker, include_default=False)
        if char_prompt:
            parts.append(f"{PROMPT_BLOCK_BEGIN}\n{char_prompt}\n{PROMPT_BLOCK_END}")

    return "\n".join(str(x) for x in parts if str(x or "").strip())

def prepare_maker_translation_payload(
    item: Dict[str, Any] | None,
    prompts: Dict[str, Any] | None = None,
    translation_settings: Dict[str, Any] | None = None,
    *,
    auto_restore_control_codes: bool = False,
) -> Dict[str, Any]:
    original = ""
    meta: Dict[str, Any] = {}
    if isinstance(item, dict):
        original = str(item.get("text") or "")
        raw_meta = item.get("maker_text_unit")
        if isinstance(raw_meta, dict):
            meta = raw_meta

    raw_info = analyze_maker_control_codes(original)
    plain_source = str(raw_info.get("plain_text") or "")
    source_kind = str(meta.get("source_kind") or "map").strip().lower()
    # DB/플러그인/화자 레이어는 순수 데이터 번역이다. 자동 제어코드 배치는
    # 일반 맵/공통 이벤트/전투 이벤트 대사에서만 작동한다.
    auto_allowed = source_kind not in {"database", "speaker"} and not source_kind.startswith("plugin")
    auto_enabled = bool(auto_restore_control_codes and auto_allowed and raw_info.get("has_control_codes"))

    control_spec: Any = []
    context = build_maker_translation_context(item, prompts)
    if auto_enabled:
        tokenized_source, mapping = protect_maker_control_codes_for_ai(original)
        # 줄 시작 제어코드는 실제 물리 줄에 묶여 있다. 자동 반영 경로에서는
        # 원문 줄내림 제거 옵션보다 코드 위치 안전을 우선해 줄 구조를 유지한다.
        auto_settings = dict(translation_settings or {}) if isinstance(translation_settings, dict) else {}
        auto_settings["normalize_source_newlines"] = False
        normalized = normalize_maker_translation_source_text(tokenized_source, auto_settings)
        control_spec = {
            "mapping": mapping,
            "raw_text": original,
            "tokenized_source": tokenized_source,
            "normalized_source": normalized,
            "expected_line_count": normalized.count("\n") + 1,
            "expected_token_line_layout": _maker_ai_control_token_line_layout(normalized, mapping),
            "expected_raw_code_lines": _maker_raw_control_code_lines(original),
        }
        auto_context = build_maker_control_code_auto_context(original, tokenized_source, mapping)
        if auto_context:
            context = (context + "\n\n" + auto_context).strip()
        protected = normalized
    else:
        # 기본 경로: API에는 제어코드가 완전히 제거된 원문만 보낸다.
        normalized = normalize_maker_translation_source_text(plain_source, translation_settings)
        protected, _unused_mapping = protect_maker_control_codes(normalized)

    return {
        "text": protected,
        "raw_text": original,
        "plain_text": plain_source,
        "normalized_text": normalized,
        "context": context,
        "control_map": control_spec,
        "control_info": raw_info,
        "control_auto_enabled": auto_enabled,
        "speaker": maker_item_speaker(item),
        "source_newlines_removed": normalized != (tokenized_source if auto_enabled else plain_source),
    }


def restore_maker_translation_text(text: Any, control_map: Any = None) -> str:
    restored, _status, _detail = restore_maker_translation_text_checked(text, control_map)
    return restored


def normalize_maker_database_translation_result(text: Any, source_text: Any = "") -> str:
    """Normalize newline characters without removing translator-provided breaks.

    Line-break policy must be controlled by the user's common/DB prompts.
    The program should not silently collapse database translation newlines,
    because that can override an explicit prompt that asks the model to break
    long text naturally.
    """
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def apply_maker_preview_settings_to_item(item: Dict[str, Any], settings: Dict[str, Any]) -> bool:
    """Apply project preview font settings to one Maker text row.

    Returns True when the item looked like a Maker text unit and was changed.
    """
    if not isinstance(item, dict) or not isinstance(item.get("maker_text_unit"), dict):
        return False
    st = normalize_maker_preview_settings(settings)
    text_type = str((item.get("maker_text_unit") or {}).get("text_type") or "")
    size = int(st["font_size"])
    if text_type.startswith("choice"):
        size = int(st["choice_font_size"])
    item["font_family"] = st["font_family"]
    item["font_size"] = size
    item["stroke_width"] = int(st["outline_width"])
    item["text_color"] = st["text_color"]
    item["stroke_color"] = st["outline_color"]
    item["line_spacing"] = int(st["line_spacing"])
    item["letter_spacing"] = int(st["letter_spacing"])
    item["char_width"] = int(st["char_width"])
    item["char_height"] = int(st["char_height"])
    try:
        rect = list(item.get("rect") or [48, 116, 260, 64])
        while len(rect) < 4:
            rect.append(0)
        rect[2] = max(120, int(st["message_width"]))
        lines = str(item.get("translated_text") or item.get("text") or "").splitlines() or [""]
        line_count = max(1, len(lines))
        line_h = max(8, int(st.get("line_height") or size * 1.25))
        rect[3] = max(40, int(line_h * line_count + int(st["message_padding"]) * 2))
        item["rect"] = [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]
    except Exception:
        pass
    return True


def apply_maker_preview_settings_to_data(data: Dict[int, dict], settings: Dict[str, Any]) -> int:
    changed = 0
    st = normalize_maker_preview_settings(settings)
    for _idx, page in _dict_items(data):
        if not isinstance(page, dict):
            continue
        page["maker_preview_settings"] = dict(st)
        for item in page.get("data") or []:
            if apply_maker_preview_settings_to_item(item, st):
                changed += 1
    return changed


def regenerate_maker_placeholder_for_page(image_path: str | os.PathLike[str], page: Dict[str, Any], *, settings: Dict[str, Any] | None = None) -> bool:
    """Regenerate the lightweight map placeholder for one Maker page."""
    if not isinstance(page, dict) or not isinstance(page.get("maker_page"), dict):
        return False
    meta = page.get("maker_page") or {}
    try:
        map_id = int(meta.get("map_id") or 0)
        map_name = str(meta.get("map_name") or f"Map{map_id:03d}")
        mw = int(meta.get("width") or 17)
        mh = int(meta.get("height") or 13)
        event_count = int(meta.get("event_count") or 0)
        text_count = int(meta.get("text_unit_count") or len(page.get("data") or []))
        engine_label = str(meta.get("engine_label") or "RPG Maker")
        page_type = str(meta.get("page_type") or "map")
        if page_type in {"common_events", "database"}:
            _virtual_page_placeholder_image(
                Path(image_path),
                title=str(meta.get("page_title") or map_name),
                subtitle=str(meta.get("source_file") or meta.get("map_file") or ""),
                text_count=text_count,
                engine_label=engine_label,
                preview_settings=settings,
            )
        else:
            events = meta.get("events") if isinstance(meta.get("events"), list) else []
            # 설정 변경 등으로 placeholder를 다시 만들 때도 기존에 저장된 이벤트 목록을 유지한다.
            # 이벤트 목록이 없으면 1단계 간이 맵 프리뷰가 빈 화면처럼 보일 수 있다.
            _placeholder_image(Path(image_path), map_id=map_id, map_name=map_name, width=mw, height=mh, events=events, text_count=text_count, engine_label=engine_label, preview_settings=settings, page_meta=meta)
            # Keep preview_crop. The UI uses it to map event tile coordinates to
            # scene coordinates after lazy/cached map rendering.
        meta["event_count"] = event_count
        return True
    except Exception:
        return False


def _maker_focus_event_from_row(row: Dict[str, Any] | None, page: Dict[str, Any] | None) -> Dict[str, Any] | None:
    """Return the event anchor for a selected Maker text row.

    The 1-step map preview is centered on the event that owns the currently
    selected dialogue/choice command.  New imports persist event_x/event_y in
    maker_text_unit; older projects can still fall back to maker_page.events.
    """
    if not isinstance(row, dict):
        return None
    meta = row.get("maker_text_unit") if isinstance(row.get("maker_text_unit"), dict) else {}
    if not isinstance(meta, dict):
        return None
    try:
        event_id = int(meta.get("event_id") or 0)
    except Exception:
        event_id = 0
    event_name = str(meta.get("event_name") or "").strip()
    try:
        if meta.get("event_x") is not None and meta.get("event_y") is not None:
            return {
                "id": event_id,
                "name": event_name,
                "x": int(meta.get("event_x") or 0),
                "y": int(meta.get("event_y") or 0),
            }
    except Exception:
        pass
    try:
        for ev in (((page or {}).get("maker_page") or {}).get("events") or []):
            if not isinstance(ev, dict):
                continue
            if int(ev.get("id") or 0) == event_id:
                return {
                    "id": int(ev.get("id") or 0),
                    "name": str(ev.get("name") or event_name or "").strip(),
                    "x": int(ev.get("x") or 0),
                    "y": int(ev.get("y") or 0),
                }
    except Exception:
        pass
    return None


def regenerate_maker_placeholder_for_selected_row(image_path: str | os.PathLike[str], page: Dict[str, Any], row: Dict[str, Any] | None, *, settings: Dict[str, Any] | None = None) -> bool:
    """Regenerate the map placeholder centered on the selected text row.

    This is stage 1 of the map preview: no game JSON is modified, only the
    generated preview image is redrawn.  If no valid selected event exists, it
    falls back to the normal page placeholder.
    """
    if not isinstance(page, dict) or not isinstance(page.get("maker_page"), dict):
        return False
    meta = page.get("maker_page") or {}
    try:
        page_type = str(meta.get("page_type") or "map")
        if page_type not in {"", "map"}:
            return regenerate_maker_placeholder_for_page(image_path, page, settings=settings)
        map_id = int(meta.get("map_id") or 0)
        map_name = str(meta.get("map_name") or f"Map{map_id:03d}")
        mw = int(meta.get("width") or 17)
        mh = int(meta.get("height") or 13)
        text_count = int(meta.get("text_unit_count") or len(page.get("data") or []))
        engine_label = str(meta.get("engine_label") or "RPG Maker")
        events = meta.get("events") if isinstance(meta.get("events"), list) else []
        focus_event = _maker_focus_event_from_row(row, page)
        _placeholder_image(
            Path(image_path),
            map_id=map_id,
            map_name=map_name,
            width=mw,
            height=mh,
            events=events,
            text_count=text_count,
            engine_label=engine_label,
            preview_settings=settings,
            focus_event=focus_event,
            page_meta=meta,
        )
        return True
    except Exception:
        return False

class MakerProjectError(RuntimeError):
    """RPG Maker/MV-MZ project import error."""


class MakerWriteBackError(MakerProjectError):
    """Raised when writing edited Maker translations back to maker_game fails."""


def _maker_meta_path(project_dir: str | os.PathLike[str], filename: str) -> Path:
    return Path(project_dir) / MAKER_META_DIR / filename


def _read_maker_import_summary(project_dir: str | os.PathLike[str]) -> Dict[str, Any]:
    try:
        path = _maker_meta_path(project_dir, MAKER_IMPORT_SUMMARY_FILE)
        if path.is_file():
            data = _read_json(path)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _maker_game_dir(project_dir: str | os.PathLike[str]) -> Path:
    return Path(project_dir) / MAKER_CLONE_DIR


def _maker_original_json_backup_dir(project_dir: str | os.PathLike[str]) -> Path:
    return Path(project_dir) / MAKER_BACKUP_DIR / MAKER_ORIGINAL_JSON_BACKUP_DIR


def backup_maker_original_json_snapshot(
    project_dir: str | os.PathLike[str],
    game_clone_dir: str | os.PathLike[str] | None = None,
    engine_info: MakerEngineInfo | Dict[str, Any] | None = None,
    *,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """Copy the imported game's original JSON files outside maker_game/.

    쯔꾸르붕이의 기본 작업 방식은 maker_game/ 클론을 즉시 완성본으로
    갱신하는 것이다.  그래서 원본 JSON 기준점은 클론 내부가 아니라
    작업 폴더의 maker_backup/original_json/ 아래에 별도 보관한다.
    """
    project_dir = Path(project_dir)
    game_root = Path(game_clone_dir) if game_clone_dir is not None else _maker_game_dir(project_dir)
    summary: Dict[str, Any] = {
        "source_type": "rpg_maker_mv_mz_original_json_snapshot",
        "backup_dir": f"{MAKER_BACKUP_DIR}/{MAKER_ORIGINAL_JSON_BACKUP_DIR}",
        "files": [],
        "file_count": 0,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "warnings": [],
    }
    try:
        if not game_root.is_dir():
            summary["warnings"].append(f"clone_missing: {game_root}")
            return summary
        if engine_info is None:
            try:
                engine_info = detect_maker_engine(game_root)
            except Exception:
                engine_info = None
        data_dir = _data_dir_from_engine_info(game_root, engine_info)
        if not data_dir.is_dir():
            summary["warnings"].append(f"data_dir_missing: {data_dir}")
            return summary
        backup_root = _maker_original_json_backup_dir(project_dir)
        if overwrite and backup_root.exists():
            shutil.rmtree(backup_root, ignore_errors=True)
        backup_root.mkdir(parents=True, exist_ok=True)
        for src in sorted(data_dir.rglob("*.json")):
            if not src.is_file():
                continue
            try:
                rel_from_game = src.relative_to(game_root)
            except Exception:
                rel_from_game = Path(src.name)
            dst = backup_root / rel_from_game
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            summary["files"].append(str(rel_from_game).replace("\\", "/"))

        # Plugin parameters are stored outside data/ in generated js/plugins.js.
        # Keep the same immutable baseline rule as RPG Maker JSON files so repeated
        # write-back never accumulates escaping or loses another plugin row.
        try:
            content_root = _content_root_from_engine_info(game_root, engine_info)
            plugins_src = Path(content_root) / "js" / "plugins.js"
            if plugins_src.is_file():
                try:
                    rel_plugins = plugins_src.relative_to(game_root)
                except Exception:
                    rel_plugins = Path("js") / "plugins.js"
                plugins_dst = backup_root / rel_plugins
                plugins_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(plugins_src, plugins_dst)
                summary["files"].append(str(rel_plugins).replace("\\", "/"))
        except Exception as plugin_backup_error:
            summary["warnings"].append(f"plugins.js 원본 백업 실패: {plugin_backup_error}")
        summary["file_count"] = len(summary["files"])
        manifest = backup_root / "original_json_manifest.json"
        with manifest.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    except Exception as e:
        summary.setdefault("warnings", []).append(str(e))
    return summary


def _is_maker_project_data(data: Dict[int, dict] | None) -> bool:
    if not isinstance(data, dict):
        return False
    for page in data.values():
        if isinstance(page, dict) and isinstance(page.get("maker_page"), dict):
            return True
        if isinstance(page, dict):
            for item in page.get("data") or []:
                if isinstance(item, dict) and isinstance(item.get("maker_text_unit"), dict):
                    return True
    return False


def is_maker_project_dir(project_dir: str | os.PathLike[str] | None) -> bool:
    if not project_dir:
        return False
    try:
        if (_maker_game_dir(project_dir)).is_dir():
            return True
        summary = _read_maker_import_summary(project_dir)
        return bool(summary.get("source_type") == "rpg_maker_mv_mz")
    except Exception:
        return False


def copy_maker_sidecar_dirs(source_project_dir: str | os.PathLike[str] | None, target_project_dir: str | os.PathLike[str] | None) -> List[str]:
    """Copy Maker-specific non-page folders when Save As branches a project.

    ProjectStore.save() naturally copies page images/masks, but Maker projects also
    need the cloned game and metadata sidecars.  Keep this copy shallow at the
    directory level so package_project can include maker_game/ in the final YSBG.
    """
    if not source_project_dir or not target_project_dir:
        return []
    src_root = Path(source_project_dir)
    dst_root = Path(target_project_dir)
    copied: List[str] = []
    for name in (MAKER_CLONE_DIR, MAKER_META_DIR, MAKER_BACKUP_DIR, MAKER_DIFF_DIR):
        src = src_root / name
        if not src.exists():
            continue
        dst = dst_root / name
        try:
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
            copied.append(name)
        except Exception as e:
            raise MakerWriteBackError(f"쯔꾸르 프로젝트 보조 폴더 복사 실패: {name} / {e}") from e
    return copied


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        # RPG Maker MV/MZ JSON is usually compact.  Compact output keeps files
        # closer to the original runtime style while still preserving Unicode.
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    # Validate before replacing the live JSON file.
    _ = _read_json(tmp)
    os.replace(tmp, path)
    # Validate once more after replace so a bad write is caught immediately.
    _ = _read_json(path)


def _cmd_code(cmd: Any) -> int | None:
    if not isinstance(cmd, dict):
        return None
    try:
        return int(cmd.get("code"))
    except Exception:
        return None


def _maker_normalize_writeback_newlines(text: Any) -> str:
    """Normalize editor/import newline markers before writing RPG Maker JSON.

    The table editor stores real line breaks as ``\n``.  Some imported TXT/API
    results may instead contain the two-character marker ``\\n``.  RPG Maker
    dialogue must be written as separate continuation commands, so both forms are
    normalized here before the command block is rebuilt.  Uppercase/lowercase
    actor-name escape codes such as ``\\N[1]`` / ``\\n[1]`` are intentionally
    preserved.
    """
    s = str(text or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\u2028", "\n").replace("\u2029", "\n")
    # Convert literal backslash newline markers from TXT/API import.  Do not
    # touch \\N[1] / \\n[1] style actor-name escape codes.
    s = re.sub(r"\\r\\n", "\n", s)
    s = re.sub(r"\\n(?!\[)", "\n", s)
    return s


def _split_maker_text_lines(text: str) -> List[str]:
    normalized = _maker_normalize_writeback_newlines(text)
    lines = normalized.split("\n")
    # RPG Maker continuation commands can contain blank lines.  Keep intentional
    # blank middle lines, but avoid creating a final empty command from a trailing
    # newline typed by accident.
    while len(lines) > 1 and lines[-1] == "":
        lines.pop()
    return lines if lines else [""]


def _find_event_by_id(events: List[Any], event_id: int | None) -> Dict[str, Any] | None:
    if event_id is None:
        return None
    try:
        if 0 <= int(event_id) < len(events):
            candidate = events[int(event_id)]
            if isinstance(candidate, dict) and int(candidate.get("id") or -1) == int(event_id):
                return candidate
    except Exception:
        pass
    for event in events:
        try:
            if isinstance(event, dict) and int(event.get("id") or -1) == int(event_id):
                return event
        except Exception:
            continue
    return None


def _command_list_for_unit(map_data: Dict[str, Any], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    events = map_data.get("events")
    if not isinstance(events, list):
        raise MakerWriteBackError("Map JSON에 events 목록이 없습니다.")
    event_id = meta.get("event_id")
    page_index = meta.get("page_index")
    try:
        event_id_i = int(event_id)
        page_index_i = int(page_index)
    except Exception as e:
        raise MakerWriteBackError(f"이벤트/페이지 위치가 올바르지 않습니다: event={event_id}, page={page_index}") from e
    event = _find_event_by_id(events, event_id_i)
    if not isinstance(event, dict):
        raise MakerWriteBackError(f"이벤트를 찾지 못했습니다: event_id={event_id_i}")
    pages = event.get("pages")
    if not isinstance(pages, list) or not (0 <= page_index_i < len(pages)):
        raise MakerWriteBackError(f"이벤트 페이지를 찾지 못했습니다: event_id={event_id_i}, page={page_index_i}")
    page = pages[page_index_i]
    if not isinstance(page, dict) or not isinstance(page.get("list"), list):
        raise MakerWriteBackError(f"이벤트 명령 목록을 찾지 못했습니다: event_id={event_id_i}, page={page_index_i}")
    return page["list"]


def _make_continuation_command(template: Dict[str, Any] | None, code: int, indent: int, line: str) -> Dict[str, Any]:
    cmd = dict(template or {})
    cmd["code"] = int(code)
    cmd["indent"] = int(cmd.get("indent", indent) if isinstance(cmd, dict) else indent)
    cmd["parameters"] = [str(line or "")]
    return cmd


def _replace_continuation_block(commands: List[Dict[str, Any]], header_index: int, continuation_code: int, text: str) -> int:
    if not (0 <= header_index < len(commands)):
        raise MakerWriteBackError(f"명령 위치가 범위를 벗어났습니다: list[{header_index}]")
    header = commands[header_index]
    if not isinstance(header, dict):
        raise MakerWriteBackError(f"명령 위치가 올바르지 않습니다: list[{header_index}]")
    j = header_index + 1
    while j < len(commands) and _cmd_code(commands[j]) == int(continuation_code):
        j += 1
    old_count = max(0, j - (header_index + 1))
    try:
        indent = int(header.get("indent") or 0)
    except Exception:
        indent = 0
    template = commands[header_index + 1] if old_count > 0 and isinstance(commands[header_index + 1], dict) else None
    new_lines = _split_maker_text_lines(text)
    new_cmds = [_make_continuation_command(template, continuation_code, indent, line) for line in new_lines]
    commands[header_index + 1:j] = new_cmds
    return len(new_cmds)


def _maker_item_writeback_text(item: Dict[str, Any]) -> str:
    """Return the text that should occupy the live clone JSON slot.

    translated_text wins.  If it is empty, write the original raw source text back
    so clearing a translation immediately restores the cloned game to the source
    wording instead of leaving a stale previous translation in maker_game/.
    """
    translated = str((item or {}).get("translated_text") or "")
    body = translated if translated.strip() else str((item or {}).get("text") or "")
    body = _maker_normalize_writeback_newlines(body)
    meta = item.get("maker_text_unit") if isinstance(item, dict) else {}
    if isinstance(meta, dict) and bool(meta.get("inline_speaker")):
        return _maker_normalize_writeback_newlines(compose_maker_inline_speaker_writeback(item, body))
    return body


def _apply_translation_to_map_data(map_data: Dict[str, Any], item: Dict[str, Any]) -> bool:
    meta = item.get("maker_text_unit") if isinstance(item, dict) else None
    if not isinstance(meta, dict):
        return False
    translated = _maker_item_writeback_text(item)
    if not translated and not str((item or {}).get("text") or ""):
        return False
    try:
        command_index = int(meta.get("command_index"))
    except Exception as e:
        raise MakerWriteBackError(f"명령 위치가 없습니다: {meta.get('json_path')}") from e
    commands = _command_list_for_unit(map_data, meta)
    if not (0 <= command_index < len(commands)):
        raise MakerWriteBackError(f"명령 위치가 범위를 벗어났습니다: {meta.get('json_path')}")
    text_type = str(meta.get("text_type") or "")
    expected_code = meta.get("code")
    try:
        expected_code_i = int(expected_code)
    except Exception:
        expected_code_i = None
    live_code = _cmd_code(commands[command_index])
    if expected_code_i is not None and live_code != expected_code_i:
        raise MakerWriteBackError(f"명령 코드가 달라졌습니다: {meta.get('json_path')} / expected={expected_code_i}, actual={live_code}")

    if text_type == "dialogue" and live_code == 101:
        _apply_plain_speaker_to_show_text_header(commands[command_index], item)
        _replace_continuation_block(commands, command_index, 401, translated)
        return True
    if text_type == "scrolling_text" and live_code == 105:
        _replace_continuation_block(commands, command_index, 405, translated)
        return True
    if text_type.startswith("choice") and live_code == 102:
        m = re.match(r"choice\[(\d+)\]", text_type)
        if not m:
            raise MakerWriteBackError(f"선택지 번호를 읽지 못했습니다: {text_type}")
        choice_index = int(m.group(1))
        cmd = commands[command_index]
        params = cmd.get("parameters") if isinstance(cmd, dict) else None
        if not isinstance(params, list) or not params or not isinstance(params[0], list):
            raise MakerWriteBackError(f"선택지 parameters 구조가 올바르지 않습니다: {meta.get('json_path')}")
        choices = params[0]
        if not (0 <= choice_index < len(choices)):
            raise MakerWriteBackError(f"선택지 번호가 범위를 벗어났습니다: {meta.get('json_path')} / choice={choice_index}")
        choice_text = _maker_normalize_writeback_newlines(translated)
        if "\n" in choice_text:
            # RPG Maker choice labels are a single string.  Collapse accidental
            # multi-line translations instead of creating invalid UI surprises.
            choice_text = " ".join(part.strip() for part in choice_text.split("\n") if part.strip())
        choices[choice_index] = choice_text
        # Keep the editor/runtime branch labels in sync with the displayed
        # choice list.  RPG Maker stores branch labels as code 402 commands
        # after the Show Choices command.
        j = command_index + 1
        while j < len(commands):
            ccode = _cmd_code(commands[j])
            if ccode == 404:  # End choices
                break
            if ccode == 402 and isinstance(commands[j], dict):
                branch_params = commands[j].get("parameters")
                if isinstance(branch_params, list) and len(branch_params) >= 2:
                    try:
                        if int(branch_params[0]) == int(choice_index):
                            branch_params[1] = choice_text
                    except Exception:
                        pass
            # Stop scanning at a new top-level command that is clearly not part
            # of the choice branch block.  Indented branch contents are allowed.
            if j > command_index + 1 and ccode not in (402, 403) and isinstance(commands[j], dict):
                try:
                    if int(commands[j].get("indent") or 0) <= int((commands[command_index] or {}).get("indent") or 0):
                        break
                except Exception:
                    pass
            j += 1
        return True
    raise MakerWriteBackError(f"아직 저장 반영을 지원하지 않는 쯔꾸르 텍스트 타입입니다: {text_type} / code={live_code}")



def _command_list_for_common_event(common_events_data: List[Any], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    event_id = meta.get("event_id") or meta.get("common_event_id")
    try:
        event_id_i = int(event_id)
    except Exception as e:
        raise MakerWriteBackError(f"공통 이벤트 ID가 올바르지 않습니다: {event_id}") from e
    target = None
    try:
        if 0 <= event_id_i < len(common_events_data):
            candidate = common_events_data[event_id_i]
            if isinstance(candidate, dict) and int(candidate.get("id") or -1) == event_id_i:
                target = candidate
    except Exception:
        target = None
    if target is None:
        for item in common_events_data:
            try:
                if isinstance(item, dict) and int(item.get("id") or -1) == event_id_i:
                    target = item
                    break
            except Exception:
                continue
    if not isinstance(target, dict) or not isinstance(target.get("list"), list):
        raise MakerWriteBackError(f"공통 이벤트 명령 목록을 찾지 못했습니다: id={event_id_i}")
    return target["list"]


def _apply_translation_to_command_item(commands: List[Dict[str, Any]], item: Dict[str, Any], *, common: bool = False) -> bool:
    meta = item.get("maker_text_unit") if isinstance(item, dict) else None
    if not isinstance(meta, dict):
        return False
    translated = _maker_item_writeback_text(item)
    if not translated and not str((item or {}).get("text") or ""):
        return False
    try:
        command_index = int(meta.get("command_index"))
    except Exception as e:
        raise MakerWriteBackError(f"명령 위치가 없습니다: {meta.get('json_path')}") from e
    if not (0 <= command_index < len(commands)):
        raise MakerWriteBackError(f"명령 위치가 범위를 벗어났습니다: {meta.get('json_path')}")
    text_type = str(meta.get("text_type") or "")
    expected_code = meta.get("code")
    try:
        expected_code_i = int(expected_code)
    except Exception:
        expected_code_i = None
    live_code = _cmd_code(commands[command_index])
    if expected_code_i is not None and live_code != expected_code_i:
        raise MakerWriteBackError(f"명령 코드가 달라졌습니다: {meta.get('json_path')} / expected={expected_code_i}, actual={live_code}")

    is_dialogue = text_type in {"dialogue", "common_dialogue", "troop_dialogue"}
    is_scroll = text_type in {"scrolling_text", "common_scrolling_text", "troop_scrolling_text"}
    is_choice = text_type.startswith("choice") or text_type.startswith("common_choice") or text_type.startswith("troop_choice")
    if is_dialogue and live_code == 101:
        _apply_plain_speaker_to_show_text_header(commands[command_index], item)
        _replace_continuation_block(commands, command_index, 401, translated)
        return True
    if is_scroll and live_code == 105:
        _replace_continuation_block(commands, command_index, 405, translated)
        return True
    if is_choice and live_code == 102:
        m = re.search(r"choice\[(\d+)\]", text_type)
        if not m:
            raise MakerWriteBackError(f"선택지 번호를 읽지 못했습니다: {text_type}")
        choice_index = int(m.group(1))
        cmd = commands[command_index]
        params = cmd.get("parameters") if isinstance(cmd, dict) else None
        if not isinstance(params, list) or not params or not isinstance(params[0], list):
            raise MakerWriteBackError(f"선택지 parameters 구조가 올바르지 않습니다: {meta.get('json_path')}")
        choices = params[0]
        if not (0 <= choice_index < len(choices)):
            raise MakerWriteBackError(f"선택지 번호가 범위를 벗어났습니다: {meta.get('json_path')} / choice={choice_index}")
        choice_text = _maker_normalize_writeback_newlines(translated)
        if "\n" in choice_text:
            choice_text = " ".join(part.strip() for part in choice_text.split("\n") if part.strip())
        choices[choice_index] = choice_text
        j = command_index + 1
        while j < len(commands):
            ccode = _cmd_code(commands[j])
            if ccode == 404:
                break
            if ccode == 402 and isinstance(commands[j], dict):
                branch_params = commands[j].get("parameters")
                if isinstance(branch_params, list) and len(branch_params) >= 2:
                    try:
                        if int(branch_params[0]) == int(choice_index):
                            branch_params[1] = choice_text
                    except Exception:
                        pass
            if j > command_index + 1 and ccode not in (402, 403) and isinstance(commands[j], dict):
                try:
                    if int(commands[j].get("indent") or 0) <= int((commands[command_index] or {}).get("indent") or 0):
                        break
                except Exception:
                    pass
            j += 1
        return True
    raise MakerWriteBackError(f"아직 저장 반영을 지원하지 않는 쯔꾸르 텍스트 타입입니다: {text_type} / code={live_code}")


def _apply_translation_to_common_event_data(common_events_data: List[Any], item: Dict[str, Any]) -> bool:
    meta = item.get("maker_text_unit") if isinstance(item, dict) else None
    if not isinstance(meta, dict):
        return False
    commands = _command_list_for_common_event(common_events_data, meta)
    return _apply_translation_to_command_item(commands, item, common=True)



def _find_troop_by_id(troops_data: List[Any], troop_id: int) -> Dict[str, Any] | None:
    try:
        if 0 <= int(troop_id) < len(troops_data):
            candidate = troops_data[int(troop_id)]
            if isinstance(candidate, dict) and int(candidate.get("id") or -1) == int(troop_id):
                return candidate
    except Exception:
        pass
    for troop in troops_data:
        try:
            if isinstance(troop, dict) and int(troop.get("id") or -1) == int(troop_id):
                return troop
        except Exception:
            continue
    return None


def _command_list_for_troop_event(troops_data: List[Any], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    troop_id = meta.get("event_id") or meta.get("db_id")
    page_index = meta.get("page_index")
    try:
        troop_id_i = int(troop_id)
        page_index_i = int(page_index)
    except Exception as e:
        raise MakerWriteBackError(f"전투 그룹/페이지 위치가 올바르지 않습니다: troop={troop_id}, page={page_index}") from e
    troop = _find_troop_by_id(troops_data, troop_id_i)
    if not isinstance(troop, dict):
        raise MakerWriteBackError(f"전투 그룹을 찾지 못했습니다: troop_id={troop_id_i}")
    pages = troop.get("pages")
    if not isinstance(pages, list) or not (0 <= page_index_i < len(pages)):
        raise MakerWriteBackError(f"전투 이벤트 페이지를 찾지 못했습니다: troop_id={troop_id_i}, page={page_index_i}")
    page = pages[page_index_i]
    if not isinstance(page, dict) or not isinstance(page.get("list"), list):
        raise MakerWriteBackError(f"전투 이벤트 명령 목록을 찾지 못했습니다: troop_id={troop_id_i}, page={page_index_i}")
    return page["list"]


def _apply_translation_to_troop_data(troops_data: List[Any], item: Dict[str, Any]) -> bool:
    meta = item.get("maker_text_unit") if isinstance(item, dict) else None
    if not isinstance(meta, dict):
        return False
    commands = _command_list_for_troop_event(troops_data, meta)
    return _apply_translation_to_command_item(commands, item, common=True)

def _set_nested_value(payload: Any, path_keys: List[Any], value: str) -> None:
    if not path_keys:
        raise MakerWriteBackError("데이터베이스 경로가 비어 있습니다.")
    cur = payload
    for key in path_keys[:-1]:
        if isinstance(cur, list):
            try:
                idx = int(key)
            except Exception as e:
                raise MakerWriteBackError(f"목록 경로가 올바르지 않습니다: {path_keys}") from e
            if not (0 <= idx < len(cur)):
                raise MakerWriteBackError(f"목록 경로가 범위를 벗어났습니다: {path_keys}")
            cur = cur[idx]
        elif isinstance(cur, dict):
            if key not in cur:
                raise MakerWriteBackError(f"딕셔너리 경로를 찾지 못했습니다: {path_keys}")
            cur = cur[key]
        else:
            raise MakerWriteBackError(f"데이터베이스 경로 중간값이 올바르지 않습니다: {path_keys}")
    last = path_keys[-1]
    if isinstance(cur, list):
        idx = int(last)
        if not (0 <= idx < len(cur)):
            raise MakerWriteBackError(f"목록 최종 경로가 범위를 벗어났습니다: {path_keys}")
        cur[idx] = _maker_normalize_writeback_newlines(value)
    elif isinstance(cur, dict):
        cur[last] = _maker_normalize_writeback_newlines(value)
    else:
        raise MakerWriteBackError(f"데이터베이스 최종 경로가 올바르지 않습니다: {path_keys}")


def _apply_translation_to_database_data(payload: Any, item: Dict[str, Any]) -> bool:
    meta = item.get("maker_text_unit") if isinstance(item, dict) else None
    if not isinstance(meta, dict):
        return False
    translated = _maker_item_writeback_text(item)
    if not translated and not str((item or {}).get("text") or ""):
        return False
    path_keys = meta.get("db_path_keys")
    if not isinstance(path_keys, list) or not path_keys:
        raise MakerWriteBackError(f"데이터베이스 경로가 없습니다: {meta.get('json_path')}")
    _set_nested_value(payload, path_keys, translated)
    return True

def collect_maker_writeback_items(data: Dict[int, dict] | None, page_indices: Iterable[int] | None = None) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    allowed = None
    if page_indices is not None:
        try:
            allowed = {int(x) for x in page_indices}
        except Exception:
            allowed = None
    items: List[Dict[str, Any]] = []
    for page_idx, page in _dict_items(data):
        try:
            page_i = int(page_idx)
        except Exception:
            page_i = -1
        if allowed is not None and page_i not in allowed:
            continue
        if not isinstance(page, dict):
            continue
        for row in page.get("data") or []:
            if not isinstance(row, dict) or not isinstance(row.get("maker_text_unit"), dict):
                continue
            meta = row.get("maker_text_unit") or {}
            item = dict(row)
            item["_page_index"] = page_i
            item["_sort_command_index"] = int(meta.get("command_index") or 0) if str(meta.get("command_index") or "").lstrip("-").isdigit() else 0
            items.append(item)
    return items


def _maker_writeback_baseline_path(project_dir: Path, game_root: Path, live_data_dir: Path, source_file: str) -> Path | None:
    """Return the immutable JSON baseline used for normal program -> game writes.

    Normal editing must never treat maker_game/data as the master, because line
    insertions/removals can shift RPG Maker command indexes after the first save.
    The stable baseline is maker_backup/original_json.  Game refresh may rebuild
    that baseline deliberately, but ordinary writeback only reads from it.
    """
    backup_root = _maker_original_json_backup_dir(project_dir)
    source_file = str(source_file or "").strip().replace("\\", "/").lstrip("/")
    if not source_file:
        return None
    candidates: List[Path] = []
    try:
        rel_data_dir = live_data_dir.relative_to(game_root)
        candidates.append(backup_root / rel_data_dir / source_file)
    except Exception:
        pass
    candidates.extend([
        backup_root / "data" / source_file,
        backup_root / "www" / "data" / source_file,
        backup_root / source_file,
    ])
    seen: set[str] = set()
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        if cand.is_file():
            return cand
    return None


def _maker_source_file_from_item(item: Dict[str, Any]) -> str:
    meta = item.get("maker_text_unit") if isinstance(item, dict) else {}
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("source_file") or meta.get("map_file") or "").strip()


def apply_maker_translations_to_game(project_dir: str | os.PathLike[str], data: Dict[int, dict] | None, *, page_indices: Iterable[int] | None = None, backup: bool = False) -> Dict[str, Any]:
    """Write the current program table state into the cloned RPG Maker JSON files.

    Normal editing is strictly one-way: program data is the master and maker_game
    JSON is only an output.  Each touched JSON file is rebuilt from the stable
    maker_backup/original_json baseline, then the current program rows are applied
    onto it.  This keeps RPG Maker command indexes stable even when a translation
    adds or removes dialogue lines.

    The only feature allowed to reverse this direction is the explicit Game
    Refresh action, which imports maker_game into program data and then makes that
    imported project data the new master again.
    """
    project_dir = Path(project_dir)
    summary: Dict[str, Any] = {
        "source_type": "rpg_maker_mv_mz_writeback",
        "master": "program_data",
        "writeback_basis": "maker_backup/original_json",
        "live_clone_editing": True,
        "written_units": 0,
        "skipped_empty": 0,
        "touched_maps": [],
        "touched_files": [],
        "touched_sidecars": [],
        "touched_plugins": [],
        "backup_dir": "",
        "warnings": [],
        "errors": [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if not _is_maker_project_data(data):
        return summary

    game_root = _maker_game_dir(project_dir)
    if not game_root.is_dir():
        raise MakerWriteBackError(f"쯔꾸르 게임 클론 폴더를 찾지 못했습니다: {game_root}")
    import_summary = _read_maker_import_summary(project_dir)
    engine_info = import_summary.get("engine") if isinstance(import_summary.get("engine"), dict) else None
    if engine_info is None:
        try:
            engine_info = detect_maker_engine(game_root).to_dict()
        except Exception:
            engine_info = None
    data_dir = _data_dir_from_engine_info(game_root, engine_info)
    if not data_dir.is_dir():
        raise MakerWriteBackError(f"쯔꾸르 data 폴더를 찾지 못했습니다: {data_dir}")

    for page in (data or {}).values():
        if isinstance(page, dict):
            for row in page.get("data") or []:
                if isinstance(row, dict) and isinstance(row.get("maker_text_unit"), dict):
                    if not str(row.get("translated_text") or "").strip():
                        summary["skipped_empty"] += 1

    page_indices_list = None
    if page_indices is not None:
        try:
            page_indices_list = [int(x) for x in page_indices]
        except Exception:
            page_indices_list = list(page_indices) if not isinstance(page_indices, (str, bytes)) else [page_indices]
    requested_items = collect_maker_writeback_items(data, page_indices=page_indices_list)
    if page_indices_list is not None and requested_items:
        # A single edited page can share the same JSON file with other pages/rows
        # (System.json DB rows, common events, etc.).  Because writeback rebuilds a
        # whole file from the immutable baseline, apply every program row belonging
        # to any touched file so previous translations are not reverted.
        touched_sources = {_maker_source_file_from_item(item) for item in requested_items}
        touched_sources.discard("")
        all_items = collect_maker_writeback_items(data, page_indices=None)
        items = [item for item in all_items if _maker_source_file_from_item(item) in touched_sources]
        try:
            summary["requested_page_indices"] = sorted({int(x) for x in (page_indices_list or [])})
        except Exception:
            summary["requested_page_indices"] = []
    else:
        items = requested_items

    plugin_parameter_items = [
        item for item in items
        if str(((item.get("maker_text_unit") or {}) if isinstance(item, dict) else {}).get("source_kind") or "") == "plugin_parameter"
    ]
    items = [
        item for item in items
        if str(((item.get("maker_text_unit") or {}) if isinstance(item, dict) else {}).get("source_kind") or "") != "plugin_parameter"
    ]
    if plugin_parameter_items:
        written_plugins = apply_plugin_parameter_translations_to_game(project_dir, plugin_parameter_items)
        if written_plugins:
            summary["written_units"] += int(written_plugins)
            summary.setdefault("touched_files", []).append("js/plugins.js")
            summary.setdefault("touched_plugins", []).extend(sorted({
                str(((item.get("maker_text_unit") or {}) if isinstance(item, dict) else {}).get("plugin_name") or "")
                for item in plugin_parameter_items
                if str(((item.get("maker_text_unit") or {}) if isinstance(item, dict) else {}).get("plugin_name") or "").strip()
            }))

    if not items:
        _maker_meta_path(project_dir, MAKER_WRITEBACK_SUMMARY_FILE).parent.mkdir(parents=True, exist_ok=True)
        with _maker_meta_path(project_dir, MAKER_WRITEBACK_SUMMARY_FILE).open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        return summary

    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        source_file = _maker_source_file_from_item(item)
        if not source_file:
            summary["warnings"].append("source_file이 없는 TextUnit은 건너뜀")
            continue
        by_file.setdefault(source_file, []).append(item)

    changed_payloads: Dict[Path, Any] = {}
    payload_source_files: Dict[Path, str] = {}
    for source_file, file_items in by_file.items():
        live_path = data_dir / source_file
        if not live_path.is_file():
            raise MakerWriteBackError(f"쯔꾸르 data 파일을 찾지 못했습니다: {live_path}")
        baseline_path = _maker_writeback_baseline_path(project_dir, game_root, data_dir, source_file)
        if baseline_path is None:
            # Old projects made before the original-json snapshot existed can still
            # be opened.  Warn loudly, but keep them editable instead of failing.
            baseline_path = live_path
            summary["warnings"].append(f"원본 백업 기준 JSON을 찾지 못해 현재 게임 JSON을 임시 기준으로 사용함: {source_file}")
            summary["writeback_basis"] = "maker_game_fallback_no_original_backup"
        payload = _read_json(baseline_path)
        source_kind = str(((file_items[0].get("maker_text_unit") or {}).get("source_kind") or "map")).strip()
        file_items_sorted = sorted(
            file_items,
            key=lambda row: (
                int((row.get("maker_text_unit") or {}).get("event_id") or 0),
                int((row.get("maker_text_unit") or {}).get("page_index") or 0) if (row.get("maker_text_unit") or {}).get("page_index") is not None else -1,
                int((row.get("maker_text_unit") or {}).get("command_index") or 0) if (row.get("maker_text_unit") or {}).get("command_index") is not None else -1,
                str((row.get("maker_text_unit") or {}).get("text_type") or ""),
            ),
            reverse=True,
        )
        written_here = 0
        for item in file_items_sorted:
            meta = item.get("maker_text_unit") or {}
            kind = str(meta.get("source_kind") or source_kind or "map")
            if kind in {"plugin_json", "plugin_script_literal", "plugin_note"}:
                if _apply_translation_to_plugin_json_data(payload, item):
                    written_here += 1
            elif kind == "common_event":
                if not isinstance(payload, list):
                    raise MakerWriteBackError(f"CommonEvents.json 구조가 올바르지 않습니다: {live_path}")
                if _apply_translation_to_common_event_data(payload, item):
                    written_here += 1
            elif kind == "troop_event":
                if not isinstance(payload, list):
                    raise MakerWriteBackError(f"Troops.json 구조가 올바르지 않습니다: {live_path}")
                if _apply_translation_to_troop_data(payload, item):
                    written_here += 1
            elif kind == "database":
                if _apply_translation_to_database_data(payload, item):
                    written_here += 1
            else:
                if not isinstance(payload, dict):
                    raise MakerWriteBackError(f"맵 JSON 구조가 올바르지 않습니다: {live_path}")
                if _apply_translation_to_map_data(payload, item):
                    written_here += 1
        if written_here:
            changed_payloads[live_path] = payload
            payload_source_files[live_path] = source_file
            summary["written_units"] += written_here
            summary.setdefault("touched_files", []).append(source_file)
            if re.fullmatch(r"Map\d{3,}\.json", source_file):
                summary["touched_maps"].append(source_file)

    if not changed_payloads:
        with _maker_meta_path(project_dir, MAKER_WRITEBACK_SUMMARY_FILE).open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        return summary

    backup_dir = None
    backups: Dict[Path, Path] = {}
    try:
        if backup:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = project_dir / MAKER_BACKUP_DIR / stamp
            base_backup_dir = backup_dir
            suffix = 1
            while backup_dir.exists():
                backup_dir = Path(str(base_backup_dir) + f"_{suffix}")
                suffix += 1
            backup_dir.mkdir(parents=True, exist_ok=True)
            for src in sorted(changed_payloads.keys()):
                dst = backup_dir / src.name
                shutil.copy2(src, dst)
                backups[src] = dst
            summary["backup_dir"] = str(backup_dir.relative_to(project_dir)).replace("\\", "/")

        for path, payload in changed_payloads.items():
            _atomic_write_json(path, payload)

        # System.json > gameTitle is the program-side title master.  Keep NW.js
        # package/index sidecars synchronized whenever System.json is rebuilt.
        for path, payload in changed_payloads.items():
            if payload_source_files.get(path) == "System.json" and isinstance(payload, dict):
                try:
                    sidecars = _apply_maker_game_title_sidecars(project_dir, str(payload.get("gameTitle") or ""))
                    summary.setdefault("touched_sidecars", []).extend(sidecars)
                except Exception as side_e:
                    summary["warnings"].append(f"타이틀 부가 파일 동기화 실패: {side_e}")

        for path in changed_payloads.keys():
            _ = _read_json(path)

    except Exception as e:
        summary["errors"].append(str(e))
        for src, bak in backups.items():
            try:
                if bak.is_file():
                    shutil.copy2(bak, src)
            except Exception as restore_e:
                summary["errors"].append(f"복구 실패: {src.name} / {restore_e}")
        try:
            _maker_meta_path(project_dir, MAKER_WRITEBACK_SUMMARY_FILE).parent.mkdir(parents=True, exist_ok=True)
            with _maker_meta_path(project_dir, MAKER_WRITEBACK_SUMMARY_FILE).open("w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        raise MakerWriteBackError(f"쯔꾸르 JSON 저장 반영 실패: {e}") from e

    try:
        summary["touched_files"] = sorted(set(summary.get("touched_files") or []))
        summary["touched_maps"] = sorted(set(summary.get("touched_maps") or []))
        summary["touched_sidecars"] = sorted(set(summary.get("touched_sidecars") or []))
        summary["touched_plugins"] = sorted(set(summary.get("touched_plugins") or []))
    except Exception:
        pass
    _maker_meta_path(project_dir, MAKER_WRITEBACK_SUMMARY_FILE).parent.mkdir(parents=True, exist_ok=True)
    with _maker_meta_path(project_dir, MAKER_WRITEBACK_SUMMARY_FILE).open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


@dataclass
class MakerTextUnit:
    map_id: int
    map_file: str
    map_name: str
    event_id: int | None
    event_name: str
    event_x: int | None
    event_y: int | None
    page_index: int | None
    command_index: int | None
    code: int | None
    text_type: str
    text: str
    speaker: str
    face_name: str
    json_path: str
    face_index: int = 0
    speaker_source: str = "unknown"
    speaker_confidence: float = 0.0
    source_kind: str = "map"
    source_file: str = ""
    db_kind: str = ""
    db_id: int | None = None
    db_field: str = ""
    db_path_keys: List[Any] | None = None
    # Plugin translation metadata.  Plugin pages deliberately reuse the normal
    # Maker text-row pipeline, but write-back needs the exact source container.
    plugin_name: str = ""
    plugin_kind: str = ""
    plugin_root_path: List[Any] | None = None
    plugin_access_steps: List[Dict[str, Any]] | None = None
    plugin_note_tag: str = ""
    plugin_note_occurrence: int = 0
    # Inline-speaker message pattern used by many MV projects/plugins:
    # first displayed line is a name drawn inside the message window with control
    # codes, not a real RPG Maker namebox.  The editor shows the codes, but API
    # translation uses the plain text only and write-back re-composes the line.
    inline_speaker: bool = False
    speaker_plain: str = ""
    speaker_raw_visible: str = ""
    body_prefix_codes: str = ""
    body_line_reserved: bool = False


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _emit_maker_progress(progress_callback, current=None, total=None, detail=None):
    """Best-effort progress emitter for heavy Maker import/build steps.

    The UI side accepts either positional or keyword-style callbacks.  Keep this
    helper in the tools layer so map/database extraction can report real steps
    without depending on PyQt.
    """
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


def _copy_game_tree_with_progress(src: Path, dst: Path, progress_callback=None) -> None:
    """Copy a RPG Maker game tree while reporting per-file progress.

    shutil.copytree is fast but opaque for large MV/MZ projects.  This keeps the
    same clone semantics while giving the UI a live step counter.
    """
    src = Path(src)
    dst = Path(dst)
    _emit_maker_progress(progress_callback, 0, 0, "게임 파일 목록 확인 중...")
    file_entries: List[Tuple[Path, Path]] = []
    dir_entries: List[Path] = []
    scanned = 0
    for root, dirs, files in os.walk(src):
        root_p = Path(root)
        try:
            rel_root = root_p.relative_to(src)
        except Exception:
            rel_root = Path()
        dir_entries.append(dst / rel_root)
        for name in dirs:
            dir_entries.append(dst / rel_root / name)
        for name in files:
            file_entries.append((root_p / name, dst / rel_root / name))
        scanned += len(files)
        if scanned and scanned % 500 == 0:
            _emit_maker_progress(progress_callback, 0, 0, f"게임 파일 목록 확인 중... {scanned}개")
    for d in dir_entries:
        d.mkdir(parents=True, exist_ok=True)
    total = len(file_entries)
    if total <= 0:
        _emit_maker_progress(progress_callback, 0, 1, "복사할 게임 파일이 없습니다.")
        return
    step = 1 if total < 80 else max(10, total // 100)
    _emit_maker_progress(progress_callback, 0, total, f"게임 파일 복사 중... 0/{total}")
    for idx, (src_file, dst_file) in enumerate(file_entries, start=1):
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        if idx == total or idx % step == 0:
            try:
                rel = str(src_file.relative_to(src)).replace('\\', '/')
            except Exception:
                rel = src_file.name
            _emit_maker_progress(progress_callback, idx, total, f"게임 파일 복사 중... {idx}/{total}\n{rel}")


def is_rpg_maker_mv_mz_project(folder: str | os.PathLike[str]) -> bool:
    try:
        info = detect_maker_engine(folder)
        return info.engine in {"mv", "mz", "unknown_mv_mz"}
    except Exception:
        return False


def assert_rpg_maker_project(folder: str | os.PathLike[str]) -> Path:
    root = Path(folder).expanduser().resolve()
    detect_maker_engine(root)
    return root


def copy_game_to_project(source_game_dir: str | os.PathLike[str], project_dir: str | os.PathLike[str], progress_callback=None) -> Tuple[Path, MakerEngineInfo]:
    """Copy the whole game/project folder into the YSB work project.

    This is intentionally a clone operation. The editor works on the copied game
    so the user's original folder remains untouched until a later explicit export
    or sync feature is implemented.
    """
    src = assert_rpg_maker_project(source_game_dir)
    src_info = detect_maker_engine(src)
    ensure_maker_project_layout(project_dir)
    dst = Path(project_dir) / MAKER_CLONE_DIR
    if dst.exists():
        _emit_maker_progress(progress_callback, 0, 0, "이전 게임 클론을 정리하는 중...")
        shutil.rmtree(dst, ignore_errors=True)
    _copy_game_tree_with_progress(src, dst, progress_callback=progress_callback)
    _emit_maker_progress(progress_callback, 0, 0, "복사된 게임 구조를 확인하는 중...")
    # Re-detect after cloning so project_root/data_dir are relative to maker_game/.
    dst_info = detect_maker_engine(dst)
    # Preserve the original confidence/engine decision if the clone layout is the same,
    # but prefer clone-relative paths for parser use.
    dst_info.engine = src_info.engine
    dst_info.engine_label = src_info.engine_label
    dst_info.confidence = src_info.confidence
    dst_info.indicators = list(src_info.indicators)
    dst_info.warnings = list(src_info.warnings)
    # Live Clone Editing: the cloned game is edited directly from now on.
    # Keep the original JSON baseline outside maker_game/ for comparison/restore.
    _emit_maker_progress(progress_callback, 0, 0, "원본 JSON 기준점을 백업하는 중...")
    backup_maker_original_json_snapshot(project_dir, dst, dst_info, overwrite=True)
    _emit_maker_progress(progress_callback, 1, 1, "게임 파일 복사 완료")
    return dst, dst_info


def load_map_infos(game_clone_dir: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Dict[int, Dict[str, Any]]:
    data_dir = _data_dir_from_engine_info(game_clone_dir, engine_info)
    raw = _read_json(data_dir / "MapInfos.json")
    result: Dict[int, Dict[str, Any]] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                mid = int(item.get("id") or 0)
            except Exception:
                mid = 0
            if mid > 0:
                result[mid] = item
    return result


def _safe_map_name(name: Any, fallback: str) -> str:
    value = str(name or "").strip() or fallback
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:80] or fallback


def _map_file_name(map_id: int) -> str:
    return f"Map{int(map_id):03d}.json"


def iter_existing_maps(game_clone_dir: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Iterable[Tuple[int, str, Path, Dict[str, Any]]]:
    data_dir = _data_dir_from_engine_info(game_clone_dir, engine_info)
    infos = load_map_infos(game_clone_dir, engine_info)
    for path in sorted(data_dir.glob("Map*.json")):
        m = re.fullmatch(r"Map(\d{3,})\.json", path.name)
        if not m:
            continue
        map_id = int(m.group(1))
        info = infos.get(map_id, {})
        map_name = _safe_map_name(info.get("name"), f"Map{map_id:03d}")
        try:
            data = _read_json(path)
        except Exception:
            data = {}
        if isinstance(data, dict):
            yield map_id, map_name, path, data


def _event_name(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("name") or "").strip()
    return ""


def load_maker_actor_lookup(game_clone_dir: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Load actor-name hints used by the first-pass speaker inference.

    MV/MZ stores actor data in data/Actors.json.  We keep the structure small and
    defensive because many games partially customize or strip these fields.
    """
    lookup: Dict[str, Any] = {"by_id": {}, "by_face_index": {}, "by_face": {}, "names": set()}
    try:
        data_dir = _data_dir_from_engine_info(game_clone_dir, engine_info)
        actors = _read_json(data_dir / "Actors.json")
    except Exception:
        return lookup
    if not isinstance(actors, list):
        return lookup
    for actor in actors:
        if not isinstance(actor, dict):
            continue
        try:
            actor_id = int(actor.get("id") or 0)
        except Exception:
            actor_id = 0
        name = str(actor.get("name") or "").strip()
        face_name = str(actor.get("faceName") or "").strip()
        try:
            face_index = int(actor.get("faceIndex") or 0)
        except Exception:
            face_index = 0
        if actor_id > 0 and name:
            lookup["by_id"][actor_id] = name
            lookup["names"].add(name)
        if face_name and name:
            lookup["by_face_index"][(face_name, face_index)] = name
            lookup["by_face"].setdefault(face_name, name)
    return lookup


def _is_generic_event_name(name: str) -> bool:
    value = str(name or "").strip()
    if not value:
        return True
    if re.fullmatch(r"(?i)(ev|event)[ _\-]*\d+", value):
        return True
    if re.fullmatch(r"(イベント|ＥＶ|EV)[ _\-]*\d+", value):
        return True
    if value in {"EV", "Event", "イベント", "이벤트"}:
        return True
    return False


def _clean_speaker_name(name: Any) -> str:
    value = str(name or "").strip()
    value = re.sub(r"\s+", " ", value)
    if not value or value.lower() in {"none", "null", "unknown"}:
        return ""
    return value


def _actor_name_from_text(text: str, actor_lookup: Dict[str, Any] | None = None) -> str:
    actor_lookup = actor_lookup or {}
    by_id = actor_lookup.get("by_id") if isinstance(actor_lookup, dict) else {}
    if not isinstance(by_id, dict):
        by_id = {}
    for m in re.finditer(r"\\[Nn]\[(\d+)\]", str(text or "")):
        try:
            actor_id = int(m.group(1))
        except Exception:
            continue
        name = _clean_speaker_name(by_id.get(actor_id))
        if name:
            return name
    return ""


def infer_maker_speaker(
    *,
    params: List[Any] | None = None,
    event_name: str = "",
    text: str = "",
    actor_lookup: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Infer a speaker candidate from RPG Maker context.

    This is intentionally conservative.  It fills the editable speaker column with
    the best hint we have, but stores source/confidence so later UI can distinguish
    auto guesses from manual speaker fixes.
    """
    params = params if isinstance(params, list) else []
    actor_lookup = actor_lookup or {}
    face_name = ""
    face_index = 0
    try:
        face_name = _clean_speaker_name(params[0]) if len(params) > 0 else ""
    except Exception:
        face_name = ""
    try:
        face_index = int(params[1] or 0) if len(params) > 1 else 0
    except Exception:
        face_index = 0

    # MZ Show Text can carry a speaker/name-window value at parameters[4].
    try:
        name_window = _clean_speaker_name(params[4]) if len(params) > 4 else ""
    except Exception:
        name_window = ""
    if name_window:
        return {
            "speaker": name_window,
            "face_name": face_name,
            "face_index": face_index,
            "source": "name_window",
            "confidence": 0.98,
        }

    actor_name = _actor_name_from_text(text, actor_lookup)
    if actor_name:
        return {
            "speaker": actor_name,
            "face_name": face_name,
            "face_index": face_index,
            "source": "actor_escape",
            "confidence": 0.95,
        }

    if face_name:
        by_face_index = actor_lookup.get("by_face_index") if isinstance(actor_lookup, dict) else {}
        by_face = actor_lookup.get("by_face") if isinstance(actor_lookup, dict) else {}
        actor_from_face = ""
        try:
            actor_from_face = _clean_speaker_name(by_face_index.get((face_name, face_index))) if isinstance(by_face_index, dict) else ""
        except Exception:
            actor_from_face = ""
        if not actor_from_face:
            try:
                actor_from_face = _clean_speaker_name(by_face.get(face_name)) if isinstance(by_face, dict) else ""
            except Exception:
                actor_from_face = ""
        if actor_from_face:
            return {
                "speaker": actor_from_face,
                "face_name": face_name,
                "face_index": face_index,
                "source": "actor_face",
                "confidence": 0.9,
            }
        return {
            "speaker": face_name,
            "face_name": face_name,
            "face_index": face_index,
            "source": "face_name",
            "confidence": 0.76,
        }

    # PATCH: UI scene reconstruction from game data.
    # Event names are map/editor context, not RPG Maker speaker data.  Do not
    # promote them into the editable speaker column or the preview name window.
    # A speaker is accepted only when it comes from an actual Show Text name
    # window, actor escape code, face/actor DB lookup, or a later explicit user
    # edit.  The event name remains available in maker_text_unit.event_name.
    return {
        "speaker": "Unknown",
        "face_name": face_name,
        "face_index": face_index,
        "source": "unknown",
        "confidence": 0.0,
    }


def _show_text_speaker(params: List[Any], event_name: str, text: str = "", actor_lookup: Dict[str, Any] | None = None) -> Tuple[str, str, int, str, float]:
    info = infer_maker_speaker(params=params, event_name=event_name, text=text, actor_lookup=actor_lookup)
    try:
        face_index = int(info.get("face_index") or 0)
    except Exception:
        face_index = 0
    return (
        str(info.get("speaker") or "Unknown"),
        str(info.get("face_name") or ""),
        face_index,
        str(info.get("source") or "unknown"),
        float(info.get("confidence") or 0.0),
    )


def _append_text_unit(
    units: List[MakerTextUnit],
    *,
    map_id: int,
    map_file: str,
    map_name: str,
    event_id: int | None,
    event_name: str,
    page_index: int | None,
    command_index: int | None,
    code: int | None,
    text_type: str,
    text: str,
    event_x: int | None = None,
    event_y: int | None = None,
    speaker: str = "",
    face_name: str = "",
    face_index: int = 0,
    speaker_source: str = "unknown",
    speaker_confidence: float = 0.0,
    source_kind: str = "map",
    source_file: str = "",
    json_path: str | None = None,
    db_kind: str = "",
    db_id: int | None = None,
    db_field: str = "",
    db_path_keys: List[Any] | None = None,
    plugin_name: str = "",
    plugin_kind: str = "",
    plugin_root_path: List[Any] | None = None,
    plugin_access_steps: List[Dict[str, Any]] | None = None,
    plugin_note_tag: str = "",
    plugin_note_occurrence: int = 0,
    inline_speaker: bool = False,
    speaker_plain: str = "",
    speaker_raw_visible: str = "",
    body_prefix_codes: str = "",
    body_line_reserved: bool = False,
):
    text = str(text or "")
    if not text.strip():
        return
    if json_path is None:
        if event_id is None:
            json_path = f"{map_file}"
        else:
            json_path = f"{map_file}/events[{event_id}]/pages[{page_index}]/list[{command_index}]"
    raw_speaker_value = str(speaker or "")
    resolved_speaker_plain = str(speaker_plain or strip_maker_control_codes(raw_speaker_value) or "").strip()
    if not resolved_speaker_plain:
        resolved_speaker_plain = raw_speaker_value.strip() or "Unknown"
    resolved_speaker_raw_visible = str(speaker_raw_visible or "")
    if not resolved_speaker_raw_visible and _maker_speaker_has_visible_codes(raw_speaker_value):
        resolved_speaker_raw_visible = raw_speaker_value

    units.append(
        MakerTextUnit(
            map_id=map_id,
            map_file=map_file,
            map_name=map_name,
            event_id=event_id,
            event_name=event_name,
            event_x=event_x,
            event_y=event_y,
            page_index=page_index,
            command_index=command_index,
            code=code,
            text_type=text_type,
            text=text,
            speaker=resolved_speaker_plain or "Unknown",
            face_name=face_name,
            json_path=json_path,
            face_index=int(face_index or 0),
            speaker_source=speaker_source or "unknown",
            speaker_confidence=float(speaker_confidence or 0.0),
            source_kind=source_kind or "map",
            source_file=source_file or map_file,
            db_kind=db_kind or "",
            db_id=db_id,
            db_field=db_field or "",
            db_path_keys=list(db_path_keys or []),
            plugin_name=plugin_name or "",
            plugin_kind=plugin_kind or "",
            plugin_root_path=list(plugin_root_path or []),
            plugin_access_steps=[dict(x) for x in (plugin_access_steps or []) if isinstance(x, dict)],
            plugin_note_tag=plugin_note_tag or "",
            plugin_note_occurrence=int(plugin_note_occurrence or 0),
            inline_speaker=bool(inline_speaker),
            speaker_plain=resolved_speaker_plain,
            speaker_raw_visible=resolved_speaker_raw_visible,
            body_prefix_codes=body_prefix_codes or "",
            body_line_reserved=bool(body_line_reserved),
        )
    )


def extract_map_text_units(map_id: int, map_name: str, map_path: Path, map_data: Dict[str, Any], *, actor_lookup: Dict[str, Any] | None = None) -> List[MakerTextUnit]:
    """Extract MVP text units from a RPG Maker MV/MZ MapXXX.json.

    First pass targets the most important event-command texts:
    - 101 + 401: Show Text lines grouped as one dialogue unit
    - 102: Show Choices entries
    - 105 + 405: Scrolling text grouped as one unit
    This keeps the import useful immediately while leaving plugin/script cases for
    later pattern-based growth.
    """
    units: List[MakerTextUnit] = []
    map_file = map_path.name
    events = map_data.get("events")
    if not isinstance(events, list):
        return units

    for event in events:
        if not isinstance(event, dict):
            continue
        try:
            event_id = int(event.get("id") or 0)
        except Exception:
            event_id = None
        event_name = _event_name(event)
        try:
            event_x = int(event.get("x") or 0)
            event_y = int(event.get("y") or 0)
        except Exception:
            event_x = None
            event_y = None
        pages = event.get("pages")
        if not isinstance(pages, list):
            continue
        for page_idx, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            commands = page.get("list")
            if not isinstance(commands, list):
                continue
            i = 0
            while i < len(commands):
                cmd = commands[i] if isinstance(commands[i], dict) else {}
                try:
                    code = int(cmd.get("code"))
                except Exception:
                    code = None
                params = cmd.get("parameters") if isinstance(cmd.get("parameters"), list) else []

                if code == 101:  # Show Text header, followed by 401 continuation lines.
                    lines: List[str] = []
                    j = i + 1
                    while j < len(commands):
                        c = commands[j] if isinstance(commands[j], dict) else {}
                        try:
                            ccode = int(c.get("code"))
                        except Exception:
                            ccode = None
                        if ccode != 401:
                            break
                        cparams = c.get("parameters") if isinstance(c.get("parameters"), list) else []
                        if cparams:
                            lines.append(str(cparams[0] or ""))
                        j += 1
                    raw_block = "\n".join(lines)
                    inline_info = split_maker_inline_speaker_text(raw_block)
                    speaker, face_name, face_index, speaker_source, speaker_confidence = _show_text_speaker(params, event_name, raw_block, actor_lookup)
                    text_for_row = raw_block
                    speaker_plain = strip_maker_control_codes(speaker)
                    inline_enabled = bool(inline_info.get("enabled")) and (not speaker or speaker == "Unknown" or str(speaker_source or "") in {"unknown", "event_name"})
                    if inline_enabled:
                        text_for_row = str(inline_info.get("body_text") or raw_block)
                        # The table speaker column must stay plain.  Control-code
                        # styling for inline names is kept in maker_text_unit.speaker_raw_visible
                        # and shown from the speaker-translation dialog only.
                        speaker_plain = str(inline_info.get("speaker_plain") or strip_maker_control_codes(inline_info.get("speaker_raw_visible") or ""))
                        speaker = speaker_plain or "Unknown"
                        speaker_source = "inline_first_line"
                        speaker_confidence = max(float(speaker_confidence or 0.0), 0.86)
                    _append_text_unit(
                        units,
                        map_id=map_id,
                        map_file=map_file,
                        map_name=map_name,
                        event_id=event_id,
                        event_name=event_name,
                        event_x=event_x,
                        event_y=event_y,
                        page_index=page_idx,
                        command_index=i,
                        code=code,
                        text_type="dialogue",
                        text=text_for_row,
                        speaker=speaker,
                        face_name=face_name,
                        face_index=face_index,
                        speaker_source=speaker_source,
                        speaker_confidence=speaker_confidence,
                        inline_speaker=inline_enabled,
                        speaker_plain=speaker_plain,
                        speaker_raw_visible=str(inline_info.get("speaker_raw_visible") or ""),
                        body_prefix_codes=str(inline_info.get("body_prefix_codes") or ""),
                        body_line_reserved=bool(inline_info.get("body_line_reserved")),
                    )
                    i = max(j, i + 1)
                    continue

                if code == 102:  # Show Choices
                    choices = []
                    try:
                        if params and isinstance(params[0], list):
                            choices = [str(x or "") for x in params[0]]
                    except Exception:
                        choices = []
                    base_speaker_info = infer_maker_speaker(event_name=event_name, text="\n".join(choices), actor_lookup=actor_lookup)
                    for choice_idx, choice in enumerate(choices):
                        _append_text_unit(
                            units,
                            map_id=map_id,
                            map_file=map_file,
                            map_name=map_name,
                            event_id=event_id,
                            event_name=event_name,
                            event_x=event_x,
                            event_y=event_y,
                            page_index=page_idx,
                            command_index=i,
                            code=code,
                            text_type=f"choice[{choice_idx}]",
                            text=choice,
                            speaker=str(base_speaker_info.get("speaker") or "Unknown"),
                            face_name=str(base_speaker_info.get("face_name") or ""),
                            face_index=int(base_speaker_info.get("face_index") or 0),
                            speaker_source=str(base_speaker_info.get("source") or "unknown"),
                            speaker_confidence=float(base_speaker_info.get("confidence") or 0.0),
                        )
                    i += 1
                    continue

                if code == 105:  # Show Scrolling Text, followed by 405 continuation lines.
                    lines: List[str] = []
                    j = i + 1
                    while j < len(commands):
                        c = commands[j] if isinstance(commands[j], dict) else {}
                        try:
                            ccode = int(c.get("code"))
                        except Exception:
                            ccode = None
                        if ccode != 405:
                            break
                        cparams = c.get("parameters") if isinstance(c.get("parameters"), list) else []
                        if cparams:
                            lines.append(str(cparams[0] or ""))
                        j += 1
                    scroll_speaker_info = infer_maker_speaker(event_name=event_name, text="\n".join(lines), actor_lookup=actor_lookup)
                    _append_text_unit(
                        units,
                        map_id=map_id,
                        map_file=map_file,
                        map_name=map_name,
                        event_id=event_id,
                        event_name=event_name,
                        event_x=event_x,
                        event_y=event_y,
                        page_index=page_idx,
                        command_index=i,
                        code=code,
                        text_type="scrolling_text",
                        text="\n".join(lines),
                        speaker=str(scroll_speaker_info.get("speaker") or "Unknown"),
                        face_name=str(scroll_speaker_info.get("face_name") or ""),
                        face_index=int(scroll_speaker_info.get("face_index") or 0),
                        speaker_source=str(scroll_speaker_info.get("source") or "unknown"),
                        speaker_confidence=float(scroll_speaker_info.get("confidence") or 0.0),
                    )
                    i = max(j, i + 1)
                    continue

                i += 1

    return units


def _common_event_name(common_event: Any) -> str:
    if isinstance(common_event, dict):
        return str(common_event.get("name") or "").strip()
    return ""


def _extract_command_text_units(
    *,
    units: List[MakerTextUnit],
    commands: List[Any],
    map_id: int,
    map_file: str,
    map_name: str,
    event_id: int | None,
    event_name: str,
    page_index: int | None,
    event_x: int | None,
    event_y: int | None,
    actor_lookup: Dict[str, Any] | None,
    source_kind: str,
    source_file: str,
    json_prefix: str,
):
    """Shared extractor for Map event lists and CommonEvents command lists."""
    i = 0
    while i < len(commands):
        cmd = commands[i] if isinstance(commands[i], dict) else {}
        try:
            code = int(cmd.get("code"))
        except Exception:
            code = None
        params = cmd.get("parameters") if isinstance(cmd.get("parameters"), list) else []

        if code == 101:
            lines: List[str] = []
            j = i + 1
            while j < len(commands):
                c = commands[j] if isinstance(commands[j], dict) else {}
                try:
                    ccode = int(c.get("code"))
                except Exception:
                    ccode = None
                if ccode != 401:
                    break
                cparams = c.get("parameters") if isinstance(c.get("parameters"), list) else []
                if cparams:
                    lines.append(str(cparams[0] or ""))
                j += 1
            raw_block = "\n".join(lines)
            inline_info = split_maker_inline_speaker_text(raw_block)
            speaker, face_name, face_index, speaker_source, speaker_confidence = _show_text_speaker(params, event_name, raw_block, actor_lookup)
            text_for_row = raw_block
            speaker_plain = strip_maker_control_codes(speaker)
            inline_enabled = bool(inline_info.get("enabled")) and (not speaker or speaker == "Unknown" or str(speaker_source or "") in {"unknown", "event_name"})
            if inline_enabled:
                text_for_row = str(inline_info.get("body_text") or raw_block)
                # The table speaker column must stay plain.  Control-code styling
                # is retained separately for write-back and speaker-translation review.
                speaker_plain = str(inline_info.get("speaker_plain") or strip_maker_control_codes(inline_info.get("speaker_raw_visible") or ""))
                speaker = speaker_plain or "Unknown"
                speaker_source = "inline_first_line"
                speaker_confidence = max(float(speaker_confidence or 0.0), 0.86)
            _append_text_unit(
                units,
                map_id=map_id,
                map_file=map_file,
                map_name=map_name,
                event_id=event_id,
                event_name=event_name,
                event_x=event_x,
                event_y=event_y,
                page_index=page_index,
                command_index=i,
                code=code,
                text_type="dialogue" if source_kind == "map" else "common_dialogue",
                text=text_for_row,
                speaker=speaker,
                face_name=face_name,
                face_index=face_index,
                speaker_source=speaker_source,
                speaker_confidence=speaker_confidence,
                source_kind=source_kind,
                source_file=source_file,
                json_path=f"{json_prefix}/list[{i}]",
                inline_speaker=inline_enabled,
                speaker_plain=speaker_plain,
                speaker_raw_visible=str(inline_info.get("speaker_raw_visible") or ""),
                body_prefix_codes=str(inline_info.get("body_prefix_codes") or ""),
                body_line_reserved=bool(inline_info.get("body_line_reserved")),
            )
            i = max(j, i + 1)
            continue

        if code == 102:
            choices = []
            try:
                if params and isinstance(params[0], list):
                    choices = [str(x or "") for x in params[0]]
            except Exception:
                choices = []
            base_speaker_info = infer_maker_speaker(event_name=event_name, text="\n".join(choices), actor_lookup=actor_lookup)
            for choice_idx, choice in enumerate(choices):
                _append_text_unit(
                    units,
                    map_id=map_id,
                    map_file=map_file,
                    map_name=map_name,
                    event_id=event_id,
                    event_name=event_name,
                    event_x=event_x,
                    event_y=event_y,
                    page_index=page_index,
                    command_index=i,
                    code=code,
                    text_type=f"choice[{choice_idx}]" if source_kind == "map" else f"common_choice[{choice_idx}]",
                    text=choice,
                    speaker=str(base_speaker_info.get("speaker") or "Unknown"),
                    face_name=str(base_speaker_info.get("face_name") or ""),
                    speaker_source=str(base_speaker_info.get("source") or "unknown"),
                    face_index=int(base_speaker_info.get("face_index") or 0),
                    speaker_confidence=float(base_speaker_info.get("confidence") or 0.0),
                    source_kind=source_kind,
                    source_file=source_file,
                    json_path=f"{json_prefix}/list[{i}]/choice[{choice_idx}]",
                )
            i += 1
            continue

        if code == 105:
            lines: List[str] = []
            j = i + 1
            while j < len(commands):
                c = commands[j] if isinstance(commands[j], dict) else {}
                try:
                    ccode = int(c.get("code"))
                except Exception:
                    ccode = None
                if ccode != 405:
                    break
                cparams = c.get("parameters") if isinstance(c.get("parameters"), list) else []
                if cparams:
                    lines.append(str(cparams[0] or ""))
                j += 1
            scroll_speaker_info = infer_maker_speaker(event_name=event_name, text="\n".join(lines), actor_lookup=actor_lookup)
            _append_text_unit(
                units,
                map_id=map_id,
                map_file=map_file,
                map_name=map_name,
                event_id=event_id,
                event_name=event_name,
                event_x=event_x,
                event_y=event_y,
                page_index=page_index,
                command_index=i,
                code=code,
                text_type="scrolling_text" if source_kind == "map" else "common_scrolling_text",
                text="\n".join(lines),
                speaker=str(scroll_speaker_info.get("speaker") or "Unknown"),
                face_name=str(scroll_speaker_info.get("face_name") or ""),
                speaker_source=str(scroll_speaker_info.get("source") or "unknown"),
                face_index=int(scroll_speaker_info.get("face_index") or 0),
                speaker_confidence=float(scroll_speaker_info.get("confidence") or 0.0),
                source_kind=source_kind,
                source_file=source_file,
                json_path=f"{json_prefix}/list[{i}]",
            )
            i = max(j, i + 1)
            continue

        i += 1


def extract_common_event_text_units(common_events_path: Path, common_events_data: Any, *, actor_lookup: Dict[str, Any] | None = None) -> List[MakerTextUnit]:
    """Extract Show Text/Choices/Scrolling Text from data/CommonEvents.json."""
    units: List[MakerTextUnit] = []
    if not isinstance(common_events_data, list):
        return units
    for idx, common_event in enumerate(common_events_data):
        if not isinstance(common_event, dict):
            continue
        try:
            common_id = int(common_event.get("id") or idx)
        except Exception:
            common_id = idx
        name = _common_event_name(common_event) or f"CommonEvent{common_id:03d}"
        commands = common_event.get("list")
        if not isinstance(commands, list):
            continue
        _extract_command_text_units(
            units=units,
            commands=commands,
            map_id=0,
            map_file=common_events_path.name,
            map_name="Common Events",
            event_id=common_id,
            event_name=name,
            page_index=0,
            event_x=None,
            event_y=None,
            actor_lookup=actor_lookup,
            source_kind="common_event",
            source_file=common_events_path.name,
            json_prefix=f"{common_events_path.name}[{common_id}]",
        )
    return units


_DATABASE_LIST_TEXT_FIELDS: Dict[str, Tuple[str, ...]] = {
    "Actors.json": ("name", "nickname", "profile"),
    "Classes.json": ("name",),
    "Skills.json": ("name", "description", "message1", "message2"),
    "Items.json": ("name", "description"),
    "Weapons.json": ("name", "description"),
    "Armors.json": ("name", "description"),
    "Enemies.json": ("name",),
    "States.json": ("name", "message1", "message2", "message3", "message4"),
}


def _database_label_from_filename(file_name: str) -> str:
    stem = str(file_name or "").replace(".json", "")
    labels = {
        "Actors": "Database - Actors",
        "Classes": "Database - Classes",
        "Skills": "Database - Skills",
        "Items": "Database - Items",
        "Weapons": "Database - Weapons",
        "Armors": "Database - Armors",
        "Enemies": "Database - Enemies",
        "States": "Database - States",
        "Troops": "Database - Troops",
        "System": "Database - System/Terms",
    }
    return labels.get(stem, f"Database - {stem or file_name}")


def _append_database_unit(
    units: List[MakerTextUnit],
    *,
    file_name: str,
    page_name: str,
    text: Any,
    db_kind: str,
    db_id: int | None,
    db_field: str,
    db_path_keys: List[Any],
    event_name: str = "",
):
    value = str(text or "")
    if not value.strip():
        return
    label = event_name or (f"{db_kind} {db_id}" if db_id is not None else db_kind)
    _append_text_unit(
        units,
        map_id=0,
        map_file=file_name,
        map_name=page_name,
        event_id=db_id,
        event_name=label,
        event_x=None,
        event_y=None,
        page_index=None,
        command_index=None,
        code=None,
        text_type=f"database:{db_kind}.{db_field}",
        text=value,
        speaker="System",
        face_name="",
        speaker_source="database",
        speaker_confidence=0.7,
        source_kind="database",
        source_file=file_name,
        json_path=f"{file_name}/" + "/".join(str(x) for x in db_path_keys),
        db_kind=db_kind,
        db_id=db_id,
        db_field=db_field,
        db_path_keys=db_path_keys,
    )


def _walk_database_system_terms(units: List[MakerTextUnit], file_name: str, page_name: str, root: Any, path_keys: List[Any] | None = None):
    path_keys = list(path_keys or [])
    if isinstance(root, str):
        field = ".".join(str(x) for x in path_keys) or "text"
        _append_database_unit(
            units,
            file_name=file_name,
            page_name=page_name,
            text=root,
            db_kind="System",
            db_id=None,
            db_field=field,
            db_path_keys=path_keys,
            event_name="System/Terms",
        )
        return
    if isinstance(root, list):
        for i, value in enumerate(root):
            # System arrays often have index 0 empty by design.  The empty guard
            # in _append_database_unit keeps those out.
            if isinstance(value, (str, list, dict)):
                _walk_database_system_terms(units, file_name, page_name, value, path_keys + [i])
        return
    if isinstance(root, dict):
        for key, value in _dict_items(root):
            if isinstance(value, (str, list, dict)):
                _walk_database_system_terms(units, file_name, page_name, value, path_keys + [str(key)])


def _database_should_skip_json_file(file_name: str) -> bool:
    name = str(file_name or "")
    if re.match(r"^Map\d+\.json$", name, flags=re.I):
        return True
    # CommonEvents/Map은 일반 맵 대사 레이어에서 처리한다.
    # Troops.json은 전투 이벤트 안의 Show Text/Choices/Scrolling Text가
    # 실제 플레이어에게 보일 수 있으므로 파일 자체는 살리고, troop name 같은
    # 내부 관리명은 전용 추출기에서 제외한다.
    # Animations/Tilesets/MapInfos의 name류는 대부분 내부 관리명이라 제외한다.
    return name in {"MapInfos.json", "CommonEvents.json", "Animations.json", "Tilesets.json"}


def _database_should_skip_string_path(file_name: str, path_keys: List[Any], value: str) -> bool:
    """Keep database-mode extraction to player-facing text only.

    DB 번역은 사용자에게 보이는 이름/설명/메시지만 대상으로 한다.
    파일명, BGM/SE 참조, 폰트 설정, 스위치/변수 내부명, damage.formula,
    script, note, meta 같은 코드/리소스/계산식은 번역하면 게임 동작이 깨질 수
    있으므로 정식 추출과 동적 fallback 양쪽에서 제외한다.
    """
    v = str(value or "").strip()
    if not v:
        return True
    file_l = str(file_name or "").lower()
    lowered = [str(k).lower() for k in (path_keys or [])]
    last = lowered[-1] if lowered else ""
    first = lowered[0] if lowered else ""

    # Player-facing DB object names must stay translatable.  A previous
    # over-broad internal-name filter could hide Skills/Items/Weapons/Armors
    # names and leave only descriptions/messages in DB mode.
    player_facing_name_files = {
        "actors.json", "classes.json", "skills.json", "items.json",
        "weapons.json", "armors.json", "enemies.json", "states.json",
    }
    if file_l in player_facing_name_files and last == "name":
        if not any(k in {
            "facename", "charactername", "battlername", "svbattlername",
            "battleback1name", "battleback2name", "parallaxname",
            "filename", "file", "src", "url", "path", "folder",
        } for k in lowered):
            return False

    if file_l == "system.json":
        # System.json은 광범위한 설정 파일이므로 허용 필드를 화이트리스트로 둔다.
        # 플레이어에게 보이는 Terms/타입명/화폐/게임 제목만 번역 대상으로 본다.
        allowed_roots = {"gametitle", "currencyunit", "elements", "skilltypes", "weapontypes", "armortypes", "equiptypes", "terms"}
        if first not in allowed_roots:
            return True
        if first == "terms":
            allowed_terms = {"basic", "params", "commands", "messages"}
            if len(lowered) >= 2 and lowered[1] not in allowed_terms:
                return True
        if any(k in {"advanced", "switches", "variables", "testbattlers", "sounds", "battletest"} for k in lowered):
            return True
        if last == "name" and any(k.endswith(("bgm", "bgs", "me", "se")) for k in lowered[:-1]):
            return True

    skip_exact = {
        "charactername", "facename", "battlername", "svbattlername",
        "battleback1name", "battleback2name", "parallaxname", "tilesetname",
        "panorama", "filename", "file", "src", "url", "path", "folder",
        # 코드/메타/계산식 계열: 번역 금지
        "formula", "script", "code", "note", "meta", "condition", "conditions",
        "params", "parameters", "traits", "effects", "damage", "speed",
    }
    if last in skip_exact:
        return True
    if any(k in {"damage", "formula", "meta", "traits", "effects", "condition", "conditions", "advanced", "switches", "variables"} for k in lowered):
        return True
    if last == "name" and any(k.endswith(("bgm", "bgs", "me", "se", "audio")) or k in {"bgm", "bgs", "me", "se", "audio"} for k in lowered[:-1]):
        return True
    # RPG Maker damage formulas and plugin expressions are usually ASCII code.
    if re.search(r"\b[ab]\.(atk|def|mat|mdf|agi|luk|hp|mp|tp)\b", v, flags=re.I):
        return True
    if re.search(r"[+\-*/=<>]", v) and re.search(r"\b(if|else|return|this|Math|game|actor|enemy|target|subject|value|[ab]\.)\b", v, flags=re.I):
        return True
    # Pure internal identifiers are usually not user-facing text.
    if re.fullmatch(r"[A-Za-z0-9_./\\:-]+", v) and not any(ord(ch) > 127 for ch in v):
        return True
    return False


def _walk_database_strings_dynamic(
    units: List[MakerTextUnit],
    *,
    file_name: str,
    page_name: str,
    root: Any,
    db_kind: str,
    db_id: int | None = None,
    event_name: str = "",
    path_keys: List[Any] | None = None,
    emitted_paths: set[Tuple[Any, ...]] | None = None,
):
    path_keys = list(path_keys or [])
    emitted_paths = emitted_paths if emitted_paths is not None else set()
    if isinstance(root, str):
        key_tuple = tuple(path_keys)
        if key_tuple in emitted_paths:
            return
        if _database_should_skip_string_path(file_name, path_keys, root):
            return
        emitted_paths.add(key_tuple)
        field = ".".join(str(x) for x in path_keys) or "text"
        _append_database_unit(
            units,
            file_name=file_name,
            page_name=page_name,
            text=root,
            db_kind=db_kind,
            db_id=db_id,
            db_field=field,
            db_path_keys=path_keys,
            event_name=event_name or (f"{db_kind} {db_id}" if db_id is not None else db_kind),
        )
        return
    if isinstance(root, list):
        for i, value in enumerate(root):
            if value is None:
                continue
            item_db_id = db_id
            item_event = event_name
            if isinstance(value, dict):
                try:
                    item_db_id = int(value.get("id") or i)
                except Exception:
                    item_db_id = i
                item_name = str(value.get("name") or "").strip()
                if item_name:
                    item_event = f"{item_db_id}: {item_name}"
            if isinstance(value, (str, list, dict)):
                _walk_database_strings_dynamic(
                    units,
                    file_name=file_name,
                    page_name=page_name,
                    root=value,
                    db_kind=db_kind,
                    db_id=item_db_id,
                    event_name=item_event,
                    path_keys=path_keys + [i],
                    emitted_paths=emitted_paths,
                )
        return
    if isinstance(root, dict):
        for key, value in _dict_items(root):
            if isinstance(value, (str, list, dict)):
                _walk_database_strings_dynamic(
                    units,
                    file_name=file_name,
                    page_name=page_name,
                    root=value,
                    db_kind=db_kind,
                    db_id=db_id,
                    event_name=event_name,
                    path_keys=path_keys + [str(key)],
                    emitted_paths=emitted_paths,
                )



def _extract_troop_event_text_units(file_name: str, page_name: str, payload: Any, *, actor_lookup: Dict[str, Any] | None = None) -> List[MakerTextUnit]:
    """Extract player-facing battle-event text from data/Troops.json.

    Troop names themselves are editor/internal labels in many RPG Maker projects, so
    they are intentionally not extracted here.  Only event-command text that can be
    displayed during battle is included: Show Text(101/401), Show Choices(102), and
    Scrolling Text(105/405).
    """
    units: List[MakerTextUnit] = []
    if not isinstance(payload, list):
        return units
    for troop_idx, troop in enumerate(payload):
        if not isinstance(troop, dict):
            continue
        try:
            troop_id = int(troop.get("id") or troop_idx)
        except Exception:
            troop_id = troop_idx
        troop_name = str(troop.get("name") or f"Troop {troop_id}").strip()
        pages = troop.get("pages")
        if not isinstance(pages, list):
            continue
        for page_idx, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            commands = page.get("list")
            if not isinstance(commands, list):
                continue
            event_name = f"Troop {troop_id}"
            if troop_name:
                event_name += f": {troop_name}"
            event_name += f" / Battle Page {page_idx + 1}"
            before = len(units)
            _extract_command_text_units(
                units=units,
                commands=commands,
                map_id=0,
                map_file=file_name,
                map_name=page_name,
                event_id=troop_id,
                event_name=event_name,
                page_index=page_idx,
                event_x=None,
                event_y=None,
                actor_lookup=actor_lookup,
                source_kind="troop_event",
                source_file=file_name,
                json_prefix=f"{file_name}[{troop_id}]/pages[{page_idx}]",
            )
            # Convert the shared command text types to troop-specific labels so the
            # right table and write-back diagnostics do not describe them as CommonEvents.
            for unit in units[before:]:
                if unit.text_type == "common_dialogue":
                    unit.text_type = "troop_dialogue"
                elif unit.text_type == "common_scrolling_text":
                    unit.text_type = "troop_scrolling_text"
                elif unit.text_type.startswith("common_choice"):
                    unit.text_type = unit.text_type.replace("common_choice", "troop_choice", 1)
                unit.db_kind = "Troops"
                unit.db_id = troop_id
                unit.db_field = unit.text_type
                unit.db_path_keys = []
    return units

def extract_database_text_units(data_dir: Path) -> Dict[str, List[MakerTextUnit]]:
    """Extract editable database/system strings into virtual page units.

    DB 탭은 고정 목록이 아니라 실제 data 폴더에 존재하는 JSON 항목을 기준으로
    만든다. MapXXX/CommonEvents처럼 일반 대사 레이어로 다룰 파일은 제외하고,
    나머지 DB성 JSON은 정식 필드 + 동적 문자열 fallback으로 추출한다.
    """
    pages: Dict[str, List[MakerTextUnit]] = {}
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return pages
    json_files = sorted([p for p in data_dir.glob("*.json") if not _database_should_skip_json_file(p.name)], key=lambda p: p.name.lower())
    preferred_order = [
        "Actors.json", "Classes.json", "Skills.json", "Items.json", "Weapons.json", "Armors.json",
        "Enemies.json", "States.json", "Troops.json", "System.json",
    ]
    order = {name: i for i, name in enumerate(preferred_order)}
    json_files.sort(key=lambda p: (order.get(p.name, 999), p.name.lower()))

    for path in json_files:
        file_name = path.name
        try:
            payload = _read_json(path)
        except Exception:
            continue
        page_name = _database_label_from_filename(file_name)
        units: List[MakerTextUnit] = []
        emitted_paths: set[Tuple[Any, ...]] = set()
        db_kind = file_name.replace(".json", "")

        if file_name == "Troops.json":
            units.extend(_extract_troop_event_text_units(file_name, page_name, payload, actor_lookup=None))
        elif file_name == "System.json" and isinstance(payload, dict):
            for key in ("gameTitle", "currencyUnit"):
                if isinstance(payload.get(key), str):
                    _append_database_unit(
                        units,
                        file_name=file_name,
                        page_name=page_name,
                        text=payload.get(key),
                        db_kind="System",
                        db_id=None,
                        db_field=key,
                        db_path_keys=[key],
                        event_name="System",
                    )
                    emitted_paths.add((key,))
            for key in ("elements", "skillTypes", "weaponTypes", "armorTypes", "equipTypes"):
                if isinstance(payload.get(key), list):
                    before = len(units)
                    _walk_database_system_terms(units, file_name, page_name, payload.get(key), [key])
                    # _walk_system_terms does not expose paths; fallback duplicate filtering handles most cases.
            if isinstance(payload.get("terms"), dict):
                _walk_database_system_terms(units, file_name, page_name, payload.get("terms"), ["terms"])
            _walk_database_strings_dynamic(
                units,
                file_name=file_name,
                page_name=page_name,
                root=payload,
                db_kind="System",
                db_id=None,
                event_name="System",
                path_keys=[],
                emitted_paths=emitted_paths,
            )
        elif isinstance(payload, list):
            fields = _DATABASE_LIST_TEXT_FIELDS.get(file_name, None)
            for idx, entry in enumerate(payload):
                if not isinstance(entry, dict):
                    continue
                try:
                    entry_id = int(entry.get("id") or idx)
                except Exception:
                    entry_id = idx
                entry_name = str(entry.get("name") or f"{db_kind} {entry_id}").strip()
                if fields:
                    for field in fields:
                        if field in entry and isinstance(entry.get(field), str):
                            _append_database_unit(
                                units,
                                file_name=file_name,
                                page_name=page_name,
                                text=entry.get(field),
                                db_kind=db_kind,
                                db_id=entry_id,
                                db_field=field,
                                db_path_keys=[idx, field],
                                event_name=f"{entry_id}: {entry_name}" if entry_name else str(entry_id),
                            )
                            emitted_paths.add((idx, field))
                _walk_database_strings_dynamic(
                    units,
                    file_name=file_name,
                    page_name=page_name,
                    root=entry,
                    db_kind=db_kind,
                    db_id=entry_id,
                    event_name=f"{entry_id}: {entry_name}" if entry_name else str(entry_id),
                    path_keys=[idx],
                    emitted_paths=emitted_paths,
                )
        elif isinstance(payload, dict):
            _walk_database_strings_dynamic(
                units,
                file_name=file_name,
                page_name=page_name,
                root=payload,
                db_kind=db_kind,
                db_id=None,
                event_name=db_kind,
                path_keys=[],
                emitted_paths=emitted_paths,
            )
        if units:
            # Deduplicate identical JSON paths generated by System special handling + fallback.
            deduped: List[MakerTextUnit] = []
            seen = set()
            for unit in units:
                key = tuple(unit.db_path_keys or []) if unit.db_path_keys else ("json_path", str(unit.json_path or ""), str(unit.text_type or ""))
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(unit)
            pages[file_name] = deduped
    return pages


# ---------------------------------------------------------------------------
# Plugin translation extraction/write-back helpers
# ---------------------------------------------------------------------------

_PLUGIN_TEXT_KEY_HINTS = (
    "text", "name", "label", "title", "caption", "message", "help", "description",
    "command", "category", "confirm", "format", "display", "term", "word", "prompt",
)
_PLUGIN_INTERNAL_KEY_HINTS = (
    "file", "image", "picture", "icon", "path", "folder", "script", "eval", "formula",
    "code", "class", "symbol", "variable", "switch", "fontface", "windowskin", "audio",
    "bgm", "bgs", "se", "me", "color", "width", "height", "offset", "scale", "origin",
    "opacity", "rotation", "rate", "speed", "duration", "id", "index", "x", "y",
)


def _maker_contains_translatable_chars(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    # Japanese/CJK/Hangul and normal sentence punctuation are the primary target.
    if re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]", text):
        return True
    # Latin-only strings are included only when they look like actual prose.
    return bool(re.search(r"[A-Za-z]", text) and re.search(r"\s", text) and len(text) >= 8)


def _maker_plugin_string_is_translatable(value: Any, key_hint: str = "") -> bool:
    text = str(value or "").strip()
    if not text or not _maker_contains_translatable_chars(text):
        return False
    key = str(key_hint or "").strip().lower().replace("_", " ")
    compact_key = re.sub(r"[^a-z0-9]", "", key)
    if compact_key:
        if any(h in compact_key for h in _PLUGIN_INTERNAL_KEY_HINTS):
            # Strongly visible labels such as ImageHelpText are still allowed only
            # when the key explicitly contains a display-text hint.
            if not any(h in compact_key for h in _PLUGIN_TEXT_KEY_HINTS):
                return False
    # Resource identifiers / expressions / pure control-code containers are unsafe.
    if re.fullmatch(r"[A-Za-z0-9_./\\:-]+", text):
        return False
    if text.lower() in {"true", "false", "null", "none", "undefined"}:
        return False
    if re.search(r"\b(this|window|scene|return|function|math|gamevariables|gameswitches)\b", text, re.I):
        return False
    if ("=>" in text or "${" in text or ";" in text) and not any(h in compact_key for h in ("text", "message", "help", "description")):
        return False
    if compact_key and any(h in compact_key for h in _PLUGIN_TEXT_KEY_HINTS):
        return True
    # Unknown keys are accepted only for unmistakable CJK prose, not short IDs.
    return bool(len(text) >= 2 and re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]", text))


def _read_maker_plugins_js_array(path: Path) -> Tuple[List[Any], str, str]:
    """Parse RPG Maker's generated ``var $plugins = [...]`` file.

    Returns the array plus untouched prefix/suffix so write-back changes only the
    JSON payload and keeps generated comments/assignment syntax valid.
    """
    text = Path(path).read_text(encoding="utf-8-sig")
    marker = text.find("$plugins")
    start = text.find("[", marker if marker >= 0 else 0)
    if start < 0:
        raise MakerProjectError(f"plugins.js 배열을 찾지 못했습니다: {path}")
    payload, consumed = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(payload, list):
        raise MakerProjectError(f"plugins.js 구조가 배열이 아닙니다: {path}")
    return payload, text[:start], text[start + consumed:]


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".ysb_tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)


def _set_plugin_access_value(current: Any, steps: List[Dict[str, Any]], value: str) -> Any:
    """Apply a translation through nested JSON strings used by plugin parameters."""
    if not steps:
        return _maker_normalize_writeback_newlines(value)
    step = steps[0] if isinstance(steps[0], dict) else {}
    op = str(step.get("op") or "")
    rest = steps[1:]
    if op == "json":
        if not isinstance(current, str):
            raise MakerWriteBackError("플러그인 중첩 JSON 문자열 구조가 변경되었습니다.")
        try:
            decoded = json.loads(current)
        except Exception as e:
            raise MakerWriteBackError("플러그인 중첩 JSON을 다시 읽지 못했습니다.") from e
        updated = _set_plugin_access_value(decoded, rest, value)
        return json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
    if op == "key":
        if not isinstance(current, dict):
            raise MakerWriteBackError("플러그인 파라미터 딕셔너리 구조가 변경되었습니다.")
        key = step.get("value")
        if key not in current:
            raise MakerWriteBackError(f"플러그인 파라미터 키를 찾지 못했습니다: {key}")
        current[key] = _set_plugin_access_value(current[key], rest, value)
        return current
    if op == "index":
        if not isinstance(current, list):
            raise MakerWriteBackError("플러그인 파라미터 목록 구조가 변경되었습니다.")
        idx = int(step.get("value") or 0)
        if not (0 <= idx < len(current)):
            raise MakerWriteBackError(f"플러그인 파라미터 목록 위치가 범위를 벗어났습니다: {idx}")
        current[idx] = _set_plugin_access_value(current[idx], rest, value)
        return current
    raise MakerWriteBackError(f"알 수 없는 플러그인 접근 단계입니다: {op}")


def _walk_plugin_parameter_value(
    units: List[MakerTextUnit],
    *,
    plugin_name: str,
    root_path: List[Any],
    value: Any,
    key_hint: str,
    access_steps: List[Dict[str, Any]] | None = None,
    depth: int = 0,
):
    if depth > 16:
        return
    steps = list(access_steps or [])
    if isinstance(value, str):
        raw = value.strip()
        if raw[:1] in {"[", "{"}:
            try:
                decoded = json.loads(value)
            except Exception:
                decoded = None
            if isinstance(decoded, (list, dict)):
                _walk_plugin_parameter_value(
                    units,
                    plugin_name=plugin_name,
                    root_path=root_path,
                    value=decoded,
                    key_hint=key_hint,
                    access_steps=steps + [{"op": "json"}],
                    depth=depth + 1,
                )
                return
        if _maker_plugin_string_is_translatable(value, key_hint):
            display_path = "/".join(str(x.get("value")) for x in steps if x.get("op") in {"key", "index"})
            _append_text_unit(
                units,
                map_id=0,
                map_file="js/plugins.js",
                map_name=f"Plugin - {plugin_name}",
                event_id=None,
                event_name=plugin_name,
                page_index=None,
                command_index=None,
                code=None,
                text_type="plugin_parameter",
                text=value,
                speaker="System",
                speaker_source="plugin_parameter",
                speaker_confidence=1.0,
                source_kind="plugin_parameter",
                source_file="js/plugins.js",
                json_path=f"js/plugins.js/{plugin_name}/" + "/".join(str(x) for x in root_path + ([display_path] if display_path else [])),
                db_kind=plugin_name,
                db_field=str(key_hint or "parameter"),
                db_path_keys=[],
                plugin_name=plugin_name,
                plugin_kind="parameter",
                plugin_root_path=root_path,
                plugin_access_steps=steps,
            )
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _walk_plugin_parameter_value(
                units,
                plugin_name=plugin_name,
                root_path=root_path,
                value=child,
                key_hint=str(key),
                access_steps=steps + [{"op": "key", "value": key}],
                depth=depth + 1,
            )
        return
    if isinstance(value, list):
        for idx, child in enumerate(value):
            _walk_plugin_parameter_value(
                units,
                plugin_name=plugin_name,
                root_path=root_path,
                value=child,
                key_hint=key_hint,
                access_steps=steps + [{"op": "index", "value": idx}],
                depth=depth + 1,
            )


def extract_plugin_parameter_text_units(game_root: Path, engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Dict[str, List[MakerTextUnit]]:
    pages: Dict[str, List[MakerTextUnit]] = {}
    try:
        content_root = _content_root_from_engine_info(game_root, engine_info)
    except Exception:
        content_root = Path(game_root)
    plugins_path = Path(content_root) / "js" / "plugins.js"
    if not plugins_path.is_file():
        return pages
    try:
        payload, _prefix, _suffix = _read_maker_plugins_js_array(plugins_path)
    except Exception:
        return pages
    for plugin_index, plugin in enumerate(payload):
        if not isinstance(plugin, dict) or not bool(plugin.get("status", True)):
            continue
        plugin_name = str(plugin.get("name") or f"Plugin{plugin_index}").strip() or f"Plugin{plugin_index}"
        params = plugin.get("parameters")
        if not isinstance(params, dict):
            continue
        units: List[MakerTextUnit] = []
        for param_key, raw_value in params.items():
            _walk_plugin_parameter_value(
                units,
                plugin_name=plugin_name,
                root_path=[plugin_index, "parameters", str(param_key)],
                value=raw_value,
                key_hint=str(param_key),
                access_steps=[],
            )
        if units:
            pages[f"plugin:{plugin_name}"] = units
    return pages


def _decode_js_string_literal(value: Any) -> str | None:
    raw = str(value or "").strip()
    if len(raw) < 2 or raw[0] not in {"'", '"'} or raw[-1] != raw[0]:
        return None
    try:
        parsed = ast.literal_eval(raw)
        return str(parsed) if isinstance(parsed, str) else None
    except Exception:
        if raw[0] == '"':
            try:
                parsed = json.loads(raw)
                return str(parsed) if isinstance(parsed, str) else None
            except Exception:
                return None
    return None


def _append_plugin_command_text_unit(
    units: List[MakerTextUnit], *, source_file: str, page_name: str,
    plugin_name: str, command_name: str, text: str, key_hint: str,
    root_path: List[Any], access_steps: List[Dict[str, Any]] | None,
    event_id: int | None, event_name: str, page_index: int | None,
    command_index: int,
):
    display_parts = [str(x.get("value")) for x in (access_steps or []) if isinstance(x, dict) and x.get("op") in {"key", "index"}]
    display_suffix = ("/" + "/".join(display_parts)) if display_parts else ""
    _append_text_unit(
        units,
        map_id=0,
        map_file=source_file,
        map_name=page_name,
        event_id=event_id,
        event_name=event_name,
        page_index=page_index,
        command_index=command_index,
        code=357,
        text_type="plugin_command_argument",
        text=text,
        speaker="System",
        speaker_source="plugin_command",
        speaker_confidence=1.0,
        source_kind="plugin_json",
        source_file=source_file,
        json_path=f"{source_file}/" + "/".join(str(x) for x in root_path) + display_suffix,
        db_kind=plugin_name,
        db_field=key_hint,
        db_path_keys=root_path,
        plugin_name=plugin_name,
        plugin_kind="command_argument",
        plugin_root_path=root_path,
        plugin_access_steps=list(access_steps or []),
    )


def _walk_plugin_command_nested_json(
    units: List[MakerTextUnit], *, source_file: str, page_name: str,
    plugin_name: str, command_name: str, value: Any, root_path: List[Any],
    access_steps: List[Dict[str, Any]], event_id: int | None, event_name: str,
    page_index: int | None, command_index: int, depth: int = 0,
):
    if depth > 16:
        return
    if isinstance(value, str):
        raw = value.strip()
        if raw[:1] in {"[", "{"}:
            try:
                decoded = json.loads(value)
            except Exception:
                decoded = None
            if isinstance(decoded, (list, dict)):
                _walk_plugin_command_nested_json(
                    units, source_file=source_file, page_name=page_name,
                    plugin_name=plugin_name, command_name=command_name, value=decoded,
                    root_path=root_path, access_steps=access_steps + [{"op": "json"}],
                    event_id=event_id, event_name=event_name, page_index=page_index,
                    command_index=command_index, depth=depth + 1,
                )
                return
        key_hint = str(access_steps[-1].get("value")) if access_steps and isinstance(access_steps[-1], dict) else command_name
        if _maker_plugin_string_is_translatable(value, key_hint):
            _append_plugin_command_text_unit(
                units, source_file=source_file, page_name=page_name,
                plugin_name=plugin_name, command_name=command_name, text=value,
                key_hint=key_hint, root_path=root_path, access_steps=access_steps,
                event_id=event_id, event_name=event_name, page_index=page_index,
                command_index=command_index,
            )
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _walk_plugin_command_nested_json(
                units, source_file=source_file, page_name=page_name,
                plugin_name=plugin_name, command_name=command_name, value=child,
                root_path=root_path, access_steps=access_steps + [{"op": "key", "value": key}],
                event_id=event_id, event_name=event_name, page_index=page_index,
                command_index=command_index, depth=depth + 1,
            )
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            _walk_plugin_command_nested_json(
                units, source_file=source_file, page_name=page_name,
                plugin_name=plugin_name, command_name=command_name, value=child,
                root_path=root_path, access_steps=access_steps + [{"op": "index", "value": idx}],
                event_id=event_id, event_name=event_name, page_index=page_index,
                command_index=command_index, depth=depth + 1,
            )


def _walk_plugin_command_argument_strings(
    units: List[MakerTextUnit],
    *, source_file: str, page_name: str, command_path: List[Any], plugin_name: str,
    command_name: str, value: Any, path: List[Any], event_id: int | None,
    event_name: str, page_index: int | None, command_index: int,
):
    if isinstance(value, str):
        full_path = command_path + path
        raw = value.strip()
        if raw[:1] in {"[", "{"}:
            try:
                decoded = json.loads(value)
            except Exception:
                decoded = None
            if isinstance(decoded, (list, dict)):
                _walk_plugin_command_nested_json(
                    units, source_file=source_file, page_name=page_name,
                    plugin_name=plugin_name, command_name=command_name, value=decoded,
                    root_path=full_path, access_steps=[{"op": "json"}],
                    event_id=event_id, event_name=event_name, page_index=page_index,
                    command_index=command_index,
                )
                return
        key_hint = str(path[-1]) if path else command_name
        if _maker_plugin_string_is_translatable(value, key_hint):
            _append_plugin_command_text_unit(
                units, source_file=source_file, page_name=page_name,
                plugin_name=plugin_name, command_name=command_name, text=value,
                key_hint=key_hint, root_path=full_path, access_steps=[],
                event_id=event_id, event_name=event_name, page_index=page_index,
                command_index=command_index,
            )
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _walk_plugin_command_argument_strings(
                units, source_file=source_file, page_name=page_name, command_path=command_path,
                plugin_name=plugin_name, command_name=command_name, value=child, path=path + [key],
                event_id=event_id, event_name=event_name, page_index=page_index, command_index=command_index,
            )
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            _walk_plugin_command_argument_strings(
                units, source_file=source_file, page_name=page_name, command_path=command_path,
                plugin_name=plugin_name, command_name=command_name, value=child, path=path + [idx],
                event_id=event_id, event_name=event_name, page_index=page_index, command_index=command_index,
            )


def _extract_plugin_units_from_command_list(
    units: List[MakerTextUnit], *, source_file: str, page_name: str, commands: Any,
    command_list_path: List[Any], event_id: int | None, event_name: str, page_index: int | None,
):
    if not isinstance(commands, list):
        return
    for command_index, command in enumerate(commands):
        if not isinstance(command, dict):
            continue
        try:
            code = int(command.get("code") or 0)
        except Exception:
            code = 0
        params = command.get("parameters")
        command_path = list(command_list_path) + [command_index, "parameters"]
        # Control Variables: script operand containing a quoted string literal.
        if code == 122 and isinstance(params, list) and len(params) >= 5:
            try:
                operand_type = int(params[3])
            except Exception:
                operand_type = -1
            decoded = _decode_js_string_literal(params[4]) if operand_type == 4 else None
            if decoded is not None and _maker_contains_translatable_chars(decoded):
                variable_from = params[0] if len(params) > 0 else ""
                variable_to = params[1] if len(params) > 1 else variable_from
                _append_text_unit(
                    units,
                    map_id=0,
                    map_file=source_file,
                    map_name=page_name,
                    event_id=event_id,
                    event_name=event_name,
                    page_index=page_index,
                    command_index=command_index,
                    code=122,
                    text_type="plugin_variable_string",
                    text=decoded,
                    speaker="System",
                    speaker_source="plugin_variable",
                    speaker_confidence=1.0,
                    source_kind="plugin_script_literal",
                    source_file=source_file,
                    json_path=f"{source_file}/" + "/".join(str(x) for x in command_path + [4]),
                    db_kind="Variables",
                    db_field=f"Variable {variable_from}" if variable_from == variable_to else f"Variables {variable_from}-{variable_to}",
                    db_path_keys=command_path + [4],
                    plugin_name="Game Variables",
                    plugin_kind="variable_string",
                )
        # RPG Maker MZ plugin command arguments.
        if code == 357 and isinstance(params, list) and len(params) >= 4 and isinstance(params[3], dict):
            plugin_name = str(params[0] or "Plugin")
            command_name = str(params[1] or params[2] or "Command")
            _walk_plugin_command_argument_strings(
                units,
                source_file=source_file,
                page_name=page_name,
                command_path=command_path + [3],
                plugin_name=plugin_name,
                command_name=command_name,
                value=params[3],
                path=[],
                event_id=event_id,
                event_name=event_name,
                page_index=page_index,
                command_index=command_index,
            )


def extract_plugin_event_text_units(data_dir: Path) -> Dict[str, List[MakerTextUnit]]:
    pages: Dict[str, List[MakerTextUnit]] = {}
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return pages
    files = sorted(list(data_dir.glob("Map*.json")) + [data_dir / "CommonEvents.json", data_dir / "Troops.json"], key=lambda p: p.name.lower())
    for path in files:
        if not path.is_file():
            continue
        try:
            payload = _read_json(path)
        except Exception:
            continue
        units: List[MakerTextUnit] = []
        if re.fullmatch(r"Map\d+\.json", path.name, re.I) and isinstance(payload, dict):
            for ev_idx, event in enumerate(payload.get("events") or []):
                if not isinstance(event, dict):
                    continue
                event_id = int(event.get("id") or ev_idx)
                event_name = str(event.get("name") or f"Event {event_id}")
                for page_idx, page in enumerate(event.get("pages") or []):
                    if not isinstance(page, dict):
                        continue
                    _extract_plugin_units_from_command_list(
                        units, source_file=path.name, page_name=path.stem,
                        commands=page.get("list"), command_list_path=["events", event_id, "pages", page_idx, "list"],
                        event_id=event_id, event_name=event_name, page_index=page_idx,
                    )
        elif path.name == "CommonEvents.json" and isinstance(payload, list):
            for ce_idx, event in enumerate(payload):
                if not isinstance(event, dict):
                    continue
                event_id = int(event.get("id") or ce_idx)
                event_name = str(event.get("name") or f"Common Event {event_id}")
                _extract_plugin_units_from_command_list(
                    units, source_file=path.name, page_name="Common Events",
                    commands=event.get("list"), command_list_path=[event_id, "list"],
                    event_id=event_id, event_name=event_name, page_index=0,
                )
        elif path.name == "Troops.json" and isinstance(payload, list):
            for troop_idx, troop in enumerate(payload):
                if not isinstance(troop, dict):
                    continue
                troop_id = int(troop.get("id") or troop_idx)
                troop_name = str(troop.get("name") or f"Troop {troop_id}")
                for page_idx, page in enumerate(troop.get("pages") or []):
                    if not isinstance(page, dict):
                        continue
                    _extract_plugin_units_from_command_list(
                        units, source_file=path.name, page_name="Troop Events",
                        commands=page.get("list"), command_list_path=[troop_id, "pages", page_idx, "list"],
                        event_id=troop_id, event_name=troop_name, page_index=page_idx,
                    )
        if units:
            pages[f"event:{path.name}"] = units
    return pages


def _iter_note_tag_values(note: str):
    """Yield RPG Maker note-tag values while preserving tag name/occurrence."""
    text = str(note or "")
    pattern = re.compile(r"<([^<>:\r\n]+):([\s\S]*?)>", re.M)
    counts: Dict[str, int] = {}
    for match in pattern.finditer(text):
        tag = str(match.group(1) or "").strip()
        value = str(match.group(2) or "")
        idx = counts.get(tag, 0)
        counts[tag] = idx + 1
        yield tag, idx, value


def extract_plugin_note_text_units(data_dir: Path) -> Dict[str, List[MakerTextUnit]]:
    pages: Dict[str, List[MakerTextUnit]] = {}
    data_dir = Path(data_dir)
    for path in sorted(data_dir.glob("*.json"), key=lambda p: p.name.lower()):
        if re.fullmatch(r"Map\d+\.json", path.name, re.I) or path.name in {"CommonEvents.json", "Troops.json", "System.json"}:
            continue
        try:
            payload = _read_json(path)
        except Exception:
            continue
        if not isinstance(payload, list):
            continue
        units: List[MakerTextUnit] = []
        for row_idx, record in enumerate(payload):
            if not isinstance(record, dict) or not isinstance(record.get("note"), str):
                continue
            rec_id = int(record.get("id") or row_idx)
            rec_name = str(record.get("name") or f"{path.stem} {rec_id}")
            note = record.get("note") or ""
            for tag, occurrence, value in _iter_note_tag_values(note):
                key_compact = re.sub(r"[^a-z0-9\u3040-\u30ff\u3400-\u9fff]", "", tag.lower())
                # Numeric/layout/resource tags stay untouched; descriptions,
                # categories and other unmistakable visible values are editable.
                if any(x in key_compact for x in ("picture", "image", "icon", "x", "y", "scale", "rate", "order", "id", "switch", "variable")):
                    continue
                if not _maker_plugin_string_is_translatable(value, tag):
                    continue
                _append_text_unit(
                    units,
                    map_id=0,
                    map_file=path.name,
                    map_name=f"Plugin Notes - {path.stem}",
                    event_id=rec_id,
                    event_name=rec_name,
                    page_index=None,
                    command_index=None,
                    code=None,
                    text_type="plugin_note_tag",
                    text=value,
                    speaker="System",
                    speaker_source="plugin_note",
                    speaker_confidence=1.0,
                    source_kind="plugin_note",
                    source_file=path.name,
                    json_path=f"{path.name}/{row_idx}/note/{tag}[{occurrence}]",
                    db_kind=path.stem,
                    db_id=rec_id,
                    db_field=tag,
                    db_path_keys=[row_idx, "note"],
                    plugin_name=path.stem,
                    plugin_kind="note_tag",
                    plugin_note_tag=tag,
                    plugin_note_occurrence=occurrence,
                )
        if units:
            pages[f"note:{path.name}"] = units
    return pages


def extract_plugin_text_units(game_root: Path, data_dir: Path, engine_info: MakerEngineInfo | Dict[str, Any] | None = None) -> Dict[str, List[MakerTextUnit]]:
    """Collect safe plugin-facing strings into isolated virtual pages."""
    pages: Dict[str, List[MakerTextUnit]] = {}
    for source in (
        extract_plugin_parameter_text_units(game_root, engine_info),
        extract_plugin_event_text_units(data_dir),
        extract_plugin_note_text_units(data_dir),
    ):
        for key, units in (source or {}).items():
            if units:
                pages[key] = units
    return pages


def _replace_note_tag_occurrence(note: str, tag: str, occurrence: int, value: str) -> str:
    text = str(note or "")
    pattern = re.compile(r"<(" + re.escape(str(tag)) + r"):([\s\S]*?)>", re.M)
    seen = -1
    def repl(match):
        nonlocal seen
        seen += 1
        if seen != int(occurrence or 0):
            return match.group(0)
        return "<" + match.group(1) + ":" + _maker_normalize_writeback_newlines(value) + ">"
    updated = pattern.sub(repl, text)
    if seen < int(occurrence or 0):
        raise MakerWriteBackError(f"플러그인 메모 태그를 찾지 못했습니다: {tag}[{occurrence}]")
    return updated


def _apply_translation_to_plugin_json_data(payload: Any, item: Dict[str, Any]) -> bool:
    meta = item.get("maker_text_unit") if isinstance(item, dict) else None
    if not isinstance(meta, dict):
        return False
    translated = _maker_item_writeback_text(item)
    kind = str(meta.get("source_kind") or "")
    path_keys = list(meta.get("db_path_keys") or [])
    if kind == "plugin_script_literal":
        # Store as a valid JS string expression; RPG Maker evaluates this operand.
        _set_nested_value(payload, path_keys, json.dumps(_maker_normalize_writeback_newlines(translated), ensure_ascii=False))
        return True
    if kind == "plugin_json" and list(meta.get("plugin_access_steps") or []):
        old_value = _get_by_path(payload, path_keys, None)
        if old_value is None:
            raise MakerWriteBackError(f"플러그인 명령 인수 경로를 찾지 못했습니다: {path_keys}")
        updated = _set_plugin_access_value(old_value, list(meta.get("plugin_access_steps") or []), translated)
        _set_nested_value(payload, path_keys, updated)
        return True
    if kind == "plugin_note":
        old_note = _get_by_path(payload, path_keys, None)
        if not isinstance(old_note, str):
            raise MakerWriteBackError(f"플러그인 메모 경로를 찾지 못했습니다: {path_keys}")
        new_note = _replace_note_tag_occurrence(
            old_note,
            str(meta.get("plugin_note_tag") or ""),
            int(meta.get("plugin_note_occurrence") or 0),
            translated,
        )
        _set_nested_value(payload, path_keys, new_note)
        return True
    _set_nested_value(payload, path_keys, translated)
    return True


def apply_plugin_parameter_translations_to_game(project_dir: Path, items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0
    game_root = _maker_game_dir(project_dir)
    import_summary = _read_maker_import_summary(project_dir)
    engine_info = import_summary.get("engine") if isinstance(import_summary.get("engine"), dict) else None
    try:
        content_root = _content_root_from_engine_info(game_root, engine_info)
    except Exception:
        content_root = game_root
    path = Path(content_root) / "js" / "plugins.js"
    if not path.is_file():
        raise MakerWriteBackError(f"plugins.js를 찾지 못했습니다: {path}")
    try:
        rel_plugins = path.relative_to(game_root)
    except Exception:
        rel_plugins = Path("js") / "plugins.js"
    baseline_path = _maker_original_json_backup_dir(project_dir) / rel_plugins
    source_path = baseline_path if baseline_path.is_file() else path
    payload, prefix, suffix = _read_maker_plugins_js_array(source_path)
    changed = 0
    for item in items:
        meta = item.get("maker_text_unit") if isinstance(item, dict) else {}
        root_path = list((meta or {}).get("plugin_root_path") or [])
        steps = [dict(x) for x in ((meta or {}).get("plugin_access_steps") or []) if isinstance(x, dict)]
        translated = _maker_item_writeback_text(item)
        if not root_path:
            continue
        old = _get_by_path(payload, root_path, None)
        if old is None:
            raise MakerWriteBackError(f"플러그인 파라미터 경로를 찾지 못했습니다: {root_path}")
        new = _set_plugin_access_value(old, steps, translated)
        if new != old:
            _set_by_path(payload, root_path, new)
            changed += 1
    if changed:
        rendered = prefix + json.dumps(payload, ensure_ascii=False, indent=4, separators=(",", ":")) + suffix
        # Validate the exact text before replacing the live file.
        tmp_payload, _p, _s = _read_maker_plugins_js_array_from_text(rendered)
        if not isinstance(tmp_payload, list):
            raise MakerWriteBackError("plugins.js 저장 검증에 실패했습니다.")
        _atomic_write_text(path, rendered, encoding="utf-8")
    return changed


def _read_maker_plugins_js_array_from_text(text: str) -> Tuple[List[Any], str, str]:
    marker = text.find("$plugins")
    start = text.find("[", marker if marker >= 0 else 0)
    if start < 0:
        raise MakerProjectError("plugins.js 배열을 찾지 못했습니다.")
    payload, consumed = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(payload, list):
        raise MakerProjectError("plugins.js 구조가 배열이 아닙니다.")
    return payload, text[:start], text[start + consumed:]


def _virtual_page_placeholder_image(
    path: Path,
    *,
    title: str,
    subtitle: str,
    text_count: int,
    engine_label: str = "RPG Maker",
    preview_settings: Dict[str, Any] | None = None,
):
    st = normalize_maker_preview_settings(preview_settings)
    canvas_w = int(st.get("screen_width") or 816)
    canvas_h = int(st.get("screen_height") or 624)
    img = np.full((canvas_h, canvas_w, 3), 36, dtype=np.uint8)
    cv2.rectangle(img, (24, 24), (canvas_w - 24, 104), (54, 54, 58), -1)
    cv2.rectangle(img, (24, 24), (canvas_w - 24, 104), (112, 112, 122), 2)
    cv2.putText(img, str(title)[:70], (46, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (235, 235, 235), 2, cv2.LINE_AA)
    cv2.putText(img, str(subtitle)[:100], (46, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (196, 216, 236), 1, cv2.LINE_AA)
    cv2.rectangle(img, (60, 150), (canvas_w - 60, canvas_h - 96), (45, 45, 50), -1)
    cv2.rectangle(img, (60, 150), (canvas_w - 60, canvas_h - 96), (98, 98, 110), 2)
    cv2.putText(img, f"{engine_label} virtual text page", (92, 206), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (220, 220, 220), 2, cv2.LINE_AA)
    cv2.putText(img, f"text units: {int(text_count or 0)}", (92, 248), cv2.FONT_HERSHEY_SIMPLEX, 0.66, (210, 226, 190), 1, cv2.LINE_AA)
    cv2.putText(img, f"preview font: {st.get('font_family')} / {st.get('font_size')}px / {canvas_w}x{canvas_h}", (92, 288), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (220, 205, 185), 1, cv2.LINE_AA)
    cv2.putText(img, "Select a row on the right to preview/edit text.", (92, 338), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (185, 205, 230), 1, cv2.LINE_AA)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise MakerProjectError("가상 페이지 이미지를 만들지 못했습니다.")
    buf.tofile(str(path))


def _calc_local_map_crop(width: int, height: int, focus_x: int, focus_y: int, cols: int, rows: int) -> Dict[str, int]:
    """Calculate a safe map crop around one event tile."""
    mw = max(1, int(width or 1))
    mh = max(1, int(height or 1))
    cols = max(1, min(int(cols or 15), mw))
    rows = max(1, min(int(rows or 10), mh))
    fx = max(0, min(mw - 1, int(focus_x or 0)))
    fy = max(0, min(mh - 1, int(focus_y or 0)))
    x0 = fx - cols // 2
    y0 = fy - rows // 2
    x0 = max(0, min(x0, max(0, mw - cols)))
    y0 = max(0, min(y0, max(0, mh - rows)))
    return {"x0": int(x0), "y0": int(y0), "cols": int(cols), "rows": int(rows), "x1": int(x0 + cols), "y1": int(y0 + rows), "focus_x": int(fx), "focus_y": int(fy)}


def _draw_text_safe(img, text: str, org: tuple[int, int], scale: float, color: tuple[int, int, int], thickness: int = 1):
    try:
        cv2.putText(img, str(text), org, cv2.FONT_HERSHEY_SIMPLEX, float(scale), color, int(thickness), cv2.LINE_AA)
    except Exception:
        pass




_MAKER_PREVIEW_JSON_CACHE: Dict[str, Any] = {}
_MAKER_PREVIEW_IMAGE_CACHE: Dict[str, Any] = {}


def _maker_find_project_root_from_preview_path(path: Path | str | os.PathLike[str]) -> Path | None:
    try:
        p = Path(path).resolve()
    except Exception:
        try:
            p = Path(path)
        except Exception:
            return None
    for base in [p.parent] + list(p.parents):
        try:
            if (base / MAKER_META_DIR).is_dir() and (base / MAKER_CLONE_DIR).is_dir():
                return base
        except Exception:
            continue
    return None


def _maker_project_root_from_settings(settings: Dict[str, Any] | None) -> Path | None:
    """Return an explicit project root supplied by UI/import hard-build paths.

    Preview image paths can point at work-cache/page files, so the renderer must
    not rely only on walking upward from the PNG.  Import-time hard builds pass
    the project root through preview settings and this helper validates it.
    """
    try:
        if not isinstance(settings, dict):
            return None
        for key in ("project_root", "maker_project_root", "preview_project_root"):
            value = str(settings.get(key) or "").strip()
            if not value:
                continue
            root = Path(value).resolve()
            # Explicit import-time roots are trusted as the source root.  Do not
            # require maker_meta to already exist; the hard build itself creates
            # cache folders under maker_meta.  Requiring an existing cache/meta
            # directory reintroduces the dependency we are trying to avoid.
            if (root / MAKER_CLONE_DIR).is_dir():
                return root
    except Exception:
        return None
    return None


def _maker_resolve_project_root_for_preview(path: Path | str | os.PathLike[str], settings: Dict[str, Any] | None = None) -> Path | None:
    return _maker_project_root_from_settings(settings) or _maker_find_project_root_from_preview_path(path)


def _maker_preview_read_json_cached(path: Path) -> Dict[str, Any] | List[Any] | None:
    try:
        st = path.stat()
        key = f"{path}|{st.st_mtime_ns}|{st.st_size}"
        cached = _MAKER_PREVIEW_JSON_CACHE.get(key)
        if cached is not None:
            return cached
        with path.open('r', encoding='utf-8-sig') as f:
            payload = json.load(f)
        _MAKER_PREVIEW_JSON_CACHE.clear() if len(_MAKER_PREVIEW_JSON_CACHE) > 64 else None
        _MAKER_PREVIEW_JSON_CACHE[key] = payload
        return payload
    except Exception:
        return None


def _maker_preview_read_system_json_for_root(project_root: Path) -> Dict[str, Any]:
    try:
        _game_root, data_dir, _content_root, _engine_info = _maker_content_paths_for_project(project_root)
        p = Path(data_dir) / 'System.json'
        data = _maker_preview_read_json_cached(p)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _maker_preview_encryption_context_for_root(project_root: Path) -> Dict[str, Any]:
    system = _maker_preview_read_system_json_for_root(project_root)
    try:
        return {
            'has_encrypted_images': bool((system or {}).get('hasEncryptedImages')),
            'has_encrypted_audio': bool((system or {}).get('hasEncryptedAudio')),
            'encryption_key': str((system or {}).get('encryptionKey') or '').strip(),
        }
    except Exception:
        return {'has_encrypted_images': False, 'has_encrypted_audio': False, 'encryption_key': ''}


def _maker_preview_is_encrypted_image_path(path: Path | str | os.PathLike[str]) -> bool:
    try:
        name = Path(path).name.lower()
        return name.endswith('.png_') or name.endswith('.jpg_') or name.endswith('.jpeg_') or name.endswith('.webp_') or name.endswith('.bmp_') or name.endswith('.rpgmvp') or name.endswith('.rpgmvp_')
    except Exception:
        return False


def _maker_preview_cache_image_extension(path: Path | str | os.PathLike[str]) -> str:
    try:
        name = Path(path).name.lower()
        for ext in ('.png_', '.jpg_', '.jpeg_', '.webp_', '.bmp_'):
            if name.endswith(ext):
                return ext[:-1]
        if name.endswith('.rpgmvp') or name.endswith('.rpgmvp_'):
            return '.png'
        suf = Path(path).suffix.lower()
        return suf if suf in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'} else '.png'
    except Exception:
        return '.png'


def _maker_preview_decrypt_image_asset_for_root(project_root: Path, source_path: Path | str | os.PathLike[str], *, category: str = 'images') -> Path | None:
    try:
        src = Path(source_path)
        if not src.is_file():
            return None
        ctx = _maker_preview_encryption_context_for_root(project_root)
        key = str(ctx.get('encryption_key') or '').strip()
        if len(key) < 32:
            return None
        ext = _maker_preview_cache_image_extension(src)
        try:
            rel_for_hash = str(src.resolve().relative_to(project_root.resolve()))
        except Exception:
            rel_for_hash = str(src)
        digest = hashlib.sha1((rel_for_hash + '|' + str(src.stat().st_mtime_ns) + '|' + str(src.stat().st_size)).encode('utf-8', 'ignore')).hexdigest()[:16]
        safe_stem = ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in src.stem.replace('.png', '').replace('.jpg', '').replace('.jpeg', '').replace('.webp', '').replace('.bmp', ''))[:80] or 'asset'
        cache_dir = project_root / MAKER_META_DIR / 'asset_cache' / str(category or 'images')
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f'{safe_stem}_{digest}{ext}'
        if cache_path.is_file() and cache_path.stat().st_size > 8:
            return cache_path
        data = src.read_bytes()
        # RPG Maker MV/MZ encrypted image assets normally have a 16-byte
        # RPGM* header, then the real image data with the first 16 bytes
        # XORed by System.json encryptionKey. Accept RPGMV/RPGMZ/variant
        # RPGM* headers instead of one exact byte sequence.
        if len(data) >= 8 and data[:8] == b'\x89PNG\r\n\x1a\n':
            # Some deployed projects keep a trailing encrypted extension even
            # when the file body is already a plain PNG. Cache it normally.
            cache_path.write_bytes(data)
            return cache_path if cache_path.is_file() else None
        if len(data) < 16 or data[:4] != b'RPGM':
            return None
        body = bytearray(data[16:])
        key_bytes = bytes(int(key[i:i+2], 16) for i in range(0, min(32, len(key)), 2))
        if len(key_bytes) < 16:
            return None
        for i in range(min(16, len(body))):
            body[i] ^= key_bytes[i]
        cache_path.write_bytes(bytes(body))
        return cache_path if cache_path.is_file() else None
    except Exception:
        return None


def _maker_preview_prepare_image_asset_for_root(project_root: Path, path: Path | str | os.PathLike[str], *, category: str = 'images') -> Path | None:
    try:
        p = Path(path)
        if _maker_preview_is_encrypted_image_path(p):
            return _maker_preview_decrypt_image_asset_for_root(project_root, p, category=category)
        return p if p.is_file() else None
    except Exception:
        return None


def _maker_cv2_read_image_cached(path: Path | str | os.PathLike[str], flags: int = cv2.IMREAD_COLOR):
    try:
        p = Path(path)
        st = p.stat()
        key = f"{p}|{st.st_mtime_ns}|{st.st_size}|{int(flags)}"
        cached = _MAKER_PREVIEW_IMAGE_CACHE.get(key)
        if cached is not None:
            return cached.copy()
        arr = np.fromfile(str(p), np.uint8)
        img = cv2.imdecode(arr, int(flags))
        if img is None:
            return None
        if len(_MAKER_PREVIEW_IMAGE_CACHE) > 48:
            _MAKER_PREVIEW_IMAGE_CACHE.clear()
        _MAKER_PREVIEW_IMAGE_CACHE[key] = img
        return img.copy()
    except Exception:
        return None



def _maker_map_placeholder_cache_path(
    preview_path: Path | str | os.PathLike[str],
    map_file: str,
    crop_info: Dict[str, Any] | None,
    settings: Dict[str, Any] | None,
    *,
    mode: str = "full",
) -> Path | None:
    """Return the disk cache path for a rendered Maker map preview image.

    The cache stores the complete placeholder PNG for a map/crop, not just the
    raw tile layer.  This keeps project opening light: import can create a cheap
    placeholder first, and the first real render for each map is reused later.
    """
    try:
        pp = Path(preview_path)
        project_root = _maker_resolve_project_root_for_preview(pp, settings)
        if project_root is None:
            return None
        _game_root, data_dir, _content_root, engine_info = _maker_content_paths_for_project(project_root)
        map_path = Path(data_dir) / str(map_file or "")
        tilesets_path = Path(data_dir) / "Tilesets.json"
        parts = [
            "maker_map_placeholder_v2",
            str((engine_info or {}).get("engine") or ""),
            str(mode or "full"),
            str(map_file or ""),
        ]
        for dep in (map_path, tilesets_path):
            try:
                st_dep = dep.stat()
                parts.append(str(dep))
                parts.append(str(st_dep.st_mtime_ns))
                parts.append(str(st_dep.st_size))
            except Exception:
                parts.append(str(dep))
                parts.append("missing")
        crop = crop_info if isinstance(crop_info, dict) else {}
        for key in ("x0", "y0", "x1", "y1", "cols", "rows", "tile_size", "focus_event_id"):
            parts.append(f"{key}={crop.get(key)}")
        st = normalize_maker_preview_settings(settings or {})
        for key in ("screen_width", "screen_height", "show_map_grid", "show_event_positions", "show_event_text_overlay", "show_advanced_map_preview"):
            parts.append(f"{key}={st.get(key)}")
        digest = hashlib.sha1("|".join(parts).encode("utf-8", "ignore")).hexdigest()[:20]
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(str(map_file or "map")).stem)[:80] or "map"
        cache_dir = project_root / MAKER_META_DIR / "map_preview_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{stem}_{digest}.png"
    except Exception:
        return None


def _maker_read_map_placeholder_cache(cache_path: Path | None, expected_w: int, expected_h: int):
    try:
        if cache_path is None or not Path(cache_path).is_file():
            return None
        img = _maker_cv2_read_image_cached(cache_path, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        if int(w) != int(expected_w) or int(h) != int(expected_h):
            return None
        return img
    except Exception:
        return None


def _maker_write_map_placeholder_cache(cache_path: Path | None, img) -> bool:
    try:
        if cache_path is None or img is None:
            return False
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        ok, buf = cv2.imencode(".png", img)
        if not ok:
            return False
        buf.tofile(str(cache_path))
        return bool(cache_path.is_file() and cache_path.stat().st_size > 8)
    except Exception:
        return False

def _maker_asset_search_dirs(project_root: Path, content_root: Path, category: str) -> List[Path]:
    """Return compatible RPG Maker asset folders for one image category.

    Normal MV/MZ projects store images under img/<category>.  Some extracted or
    partial resource packs, however, are distributed as the *contents* of the
    img folder, so users may end up with tilesets/, characters/, system/ directly
    beside data/ and js/.  Treat those direct category folders as read-only
    compatibility fallbacks for preview rendering.
    """
    cat = str(category or '').strip().replace('\\', '/').strip('/')
    if not cat:
        return []
    roots = [
        Path(content_root),
        Path(project_root) / MAKER_CLONE_DIR,
        Path(project_root) / MAKER_CLONE_DIR / 'www',
    ]
    dirs: List[Path] = []
    seen = set()
    for root in roots:
        for folder in (root / 'img' / cat, root / cat):
            try:
                key = str(folder.resolve()) if folder.exists() else str(folder)
            except Exception:
                key = str(folder)
            if key in seen:
                continue
            seen.add(key)
            dirs.append(folder)
    return dirs


def _maker_resolve_image_asset_path(project_root: Path, content_root: Path, category: str, name: str) -> Path | None:
    base = str(name or '').strip()
    if not base:
        return None
    # RPG Maker database values normally contain a bare asset name.  If a plugin
    # or hand-edited project passes a path-like value, keep only the filename to
    # avoid escaping the intended asset category.
    base = base.replace('\\', '/').split('/')[-1]
    if not base:
        return None
    exts = ('.png', '.PNG', '.png_', '.PNG_', '.rpgmvp', '.rpgmvp_', '.webp', '.webp_', '.jpg', '.jpg_', '.jpeg', '.jpeg_', '.bmp', '.bmp_')
    has_ext = bool(re.search(r'\.(png|png_|rpgmvp|rpgmvp_|webp|webp_|jpg|jpg_|jpeg|jpeg_|bmp|bmp_)$', base, flags=re.I))
    names = [base] if has_ext else [f'{base}{ext}' for ext in exts]
    for folder in _maker_asset_search_dirs(project_root, content_root, category):
        for filename in names:
            c = folder / filename
            try:
                if c.is_file():
                    return c
            except Exception:
                continue
    # Case-insensitive fallback for deployed games copied between platforms.
    # Also catches encrypted MZ assets like TileA1.PNG_ / tilea1.png_.
    wanted = {str(filename).lower() for filename in names}
    for folder in _maker_asset_search_dirs(project_root, content_root, category):
        try:
            if not folder.is_dir():
                continue
            for child in folder.iterdir():
                if child.is_file() and child.name.lower() in wanted:
                    return child
        except Exception:
            continue
    return None


def _maker_resolve_tileset_image_path(project_root: Path, content_root: Path, name: str) -> Path | None:
    return _maker_resolve_image_asset_path(project_root, content_root, 'tilesets', name)


def _maker_map_get_tile(data: List[Any], mw: int, mh: int, x: int, y: int, z: int) -> int:
    try:
        idx = (int(z) * int(mh) + int(y)) * int(mw) + int(x)
        if idx < 0 or idx >= len(data):
            return 0
        return int(data[idx] or 0)
    except Exception:
        return 0


def _maker_tile_crop_from_sheet(sheet_img, local_index: int):
    try:
        tile_w = tile_h = 48
        h, w = sheet_img.shape[:2]
        cols = max(1, int(w // tile_w))
        rows = max(1, int(h // tile_h))
        cap = cols * rows
        li = int(local_index)
        if li < 0 or li >= cap:
            return None
        sx = (li % cols) * tile_w
        sy = (li // cols) * tile_h
        tile = sheet_img[sy:sy+tile_h, sx:sx+tile_w]
        if tile is None or tile.size == 0:
            return None
        return tile.copy()
    except Exception:
        return None


def _maker_normal_tile_source_rect(tile_id: int) -> Tuple[int, int, int, int]:
    """Return RPG Maker MZ normal-tile source rect for B/C/D/E/A5.

    MZ does not use simple 16-column row-major local_index cropping here.
    The engine formula is:
      sx = ((floor(tileId / 128) % 2) * 8 + (tileId % 8)) * 48
      sy = (floor((tileId % 256) / 8) % 16) * 48
    """
    try:
        tid = int(tile_id or 0)
        tile_w = tile_h = 48
        sx = (((tid // 128) % 2) * 8 + (tid % 8)) * tile_w
        sy = (((tid % 256) // 8) % 16) * tile_h
        return int(sx), int(sy), tile_w, tile_h
    except Exception:
        return 0, 0, 48, 48


def _maker_tile_crop_from_source_rect(sheet_img, sx: int, sy: int, sw: int = 48, sh: int = 48):
    try:
        h, w = sheet_img.shape[:2]
        sx = int(sx); sy = int(sy); sw = int(sw); sh = int(sh)
        if sx < 0 or sy < 0 or sx + sw > w or sy + sh > h:
            return None
        tile = sheet_img[sy:sy+sh, sx:sx+sw]
        if tile is None or tile.size == 0:
            return None
        return tile.copy()
    except Exception:
        return None


def _maker_normal_tile_image(tile_id: int, tileset_images: Dict[str, Any]):
    try:
        tid = int(tile_id or 0)
    except Exception:
        return None
    sheet = _maker_tile_sheet_name(tid) if "_maker_tile_sheet_name" in globals() else ""
    if not sheet:
        if 0 <= tid < 256:
            sheet = "B"
        elif 256 <= tid < 512:
            sheet = "C"
        elif 512 <= tid < 768:
            sheet = "D"
        elif 768 <= tid < 1024:
            sheet = "E"
        elif 1536 <= tid < 2048:
            sheet = "A5"
    if sheet not in {"A5", "B", "C", "D", "E"}:
        return None
    img = tileset_images.get(sheet)
    if img is None:
        return None
    sx, sy, sw, sh = _maker_normal_tile_source_rect(tid)
    tile = _maker_tile_crop_from_source_rect(img, sx, sy, sw, sh)
    # A5 has only an 8-column sheet in many projects.  If a theoretically valid
    # tileId points outside the actual image, keep a conservative fallback for
    # preview robustness instead of killing the whole render.
    if tile is None and sheet == "A5":
        tile = _maker_tile_crop_from_sheet(img, tid - 1536)
    return tile


def _maker_simple_tile_image(tile_id: int, tileset_images: Dict[str, Any]):
    try:
        tid = int(tile_id or 0)
    except Exception:
        return None
    # B/C/D/E/A5 normal tiles must use the RPG Maker source-rect formula, not
    # simple 16-column row-major cropping.  Row-major cropping makes roofs,
    # walls, pillars and decorations appear as the wrong pieces.
    if 0 <= tid < 1024 or 1536 <= tid < 2048:
        return _maker_normal_tile_image(tid, tileset_images)
    return None



MAKER_TILE_ID_A5 = 1536
MAKER_TILE_ID_A1 = 2048
MAKER_TILE_ID_A2 = 2816
MAKER_TILE_ID_A3 = 4352
MAKER_TILE_ID_A4 = 5888
MAKER_TILE_ID_MAX = 8192

# Official RPG Maker autotile assembly tables adapted for preview rendering.
MAKER_FLOOR_AUTOTILE_TABLE = [
    [[2, 4], [1, 4], [2, 3], [1, 3]],
    [[2, 0], [1, 4], [2, 3], [1, 3]],
    [[2, 4], [3, 0], [2, 3], [1, 3]],
    [[2, 0], [3, 0], [2, 3], [1, 3]],
    [[2, 4], [1, 4], [2, 3], [3, 1]],
    [[2, 0], [1, 4], [2, 3], [3, 1]],
    [[2, 4], [3, 0], [2, 3], [3, 1]],
    [[2, 0], [3, 0], [2, 3], [3, 1]],
    [[2, 4], [1, 4], [2, 1], [1, 3]],
    [[2, 0], [1, 4], [2, 1], [1, 3]],
    [[2, 4], [3, 0], [2, 1], [1, 3]],
    [[2, 0], [3, 0], [2, 1], [1, 3]],
    [[2, 4], [1, 4], [2, 1], [3, 1]],
    [[2, 0], [1, 4], [2, 1], [3, 1]],
    [[2, 4], [3, 0], [2, 1], [3, 1]],
    [[2, 0], [3, 0], [2, 1], [3, 1]],
    [[0, 4], [1, 4], [0, 3], [1, 3]],
    [[0, 4], [3, 0], [0, 3], [1, 3]],
    [[0, 4], [1, 4], [0, 3], [3, 1]],
    [[0, 4], [3, 0], [0, 3], [3, 1]],
    [[2, 2], [1, 2], [2, 3], [1, 3]],
    [[2, 2], [1, 2], [2, 3], [3, 1]],
    [[2, 2], [1, 2], [2, 1], [1, 3]],
    [[2, 2], [1, 2], [2, 1], [3, 1]],
    [[2, 4], [3, 4], [2, 3], [3, 3]],
    [[2, 4], [3, 4], [2, 1], [3, 3]],
    [[2, 0], [3, 4], [2, 3], [3, 3]],
    [[2, 0], [3, 4], [2, 1], [3, 3]],
    [[2, 4], [1, 4], [2, 5], [1, 5]],
    [[2, 0], [1, 4], [2, 5], [1, 5]],
    [[2, 4], [3, 0], [2, 5], [1, 5]],
    [[2, 0], [3, 0], [2, 5], [1, 5]],
    [[0, 4], [3, 4], [0, 3], [3, 3]],
    [[2, 2], [1, 2], [2, 5], [1, 5]],
    [[0, 2], [1, 2], [0, 3], [1, 3]],
    [[0, 2], [1, 2], [0, 3], [3, 1]],
    [[2, 2], [3, 2], [2, 3], [3, 3]],
    [[2, 2], [3, 2], [2, 1], [3, 3]],
    [[2, 4], [3, 4], [2, 5], [3, 5]],
    [[2, 0], [3, 4], [2, 5], [3, 5]],
    [[0, 4], [1, 4], [0, 5], [1, 5]],
    [[0, 4], [3, 0], [0, 5], [1, 5]],
    [[0, 2], [3, 2], [0, 3], [3, 3]],
    [[0, 2], [1, 2], [0, 5], [1, 5]],
    [[0, 4], [3, 4], [0, 5], [3, 5]],
    [[2, 2], [3, 2], [2, 5], [3, 5]],
    [[0, 2], [3, 2], [0, 5], [3, 5]],
    [[0, 0], [1, 0], [0, 1], [1, 1]],
]

MAKER_WALL_AUTOTILE_TABLE = [
    [[2, 2], [1, 2], [2, 1], [1, 1]],
    [[0, 2], [1, 2], [0, 1], [1, 1]],
    [[2, 0], [1, 0], [2, 1], [1, 1]],
    [[0, 0], [1, 0], [0, 1], [1, 1]],
    [[2, 2], [3, 2], [2, 1], [3, 1]],
    [[0, 2], [3, 2], [0, 1], [3, 1]],
    [[2, 0], [3, 0], [2, 1], [3, 1]],
    [[0, 0], [3, 0], [0, 1], [3, 1]],
    [[2, 2], [1, 2], [2, 3], [1, 3]],
    [[0, 2], [1, 2], [0, 3], [1, 3]],
    [[2, 0], [1, 0], [2, 3], [1, 3]],
    [[0, 0], [1, 0], [0, 3], [1, 3]],
    [[2, 2], [3, 2], [2, 3], [3, 3]],
    [[0, 2], [3, 2], [0, 3], [3, 3]],
    [[2, 0], [3, 0], [2, 3], [3, 3]],
    [[0, 0], [3, 0], [0, 3], [3, 3]],
]

MAKER_WATERFALL_AUTOTILE_TABLE = [
    [[2, 0], [1, 0], [2, 1], [1, 1]],
    [[0, 0], [1, 0], [0, 1], [1, 1]],
    [[2, 0], [3, 0], [2, 1], [3, 1]],
    [[0, 0], [3, 0], [0, 1], [3, 1]],
]


def _maker_is_tile_a1(tile_id: int) -> bool:
    return MAKER_TILE_ID_A1 <= int(tile_id or 0) < MAKER_TILE_ID_A2


def _maker_is_tile_a2(tile_id: int) -> bool:
    return MAKER_TILE_ID_A2 <= int(tile_id or 0) < MAKER_TILE_ID_A3


def _maker_is_tile_a3(tile_id: int) -> bool:
    return MAKER_TILE_ID_A3 <= int(tile_id or 0) < MAKER_TILE_ID_A4


def _maker_is_tile_a4(tile_id: int) -> bool:
    return MAKER_TILE_ID_A4 <= int(tile_id or 0) < MAKER_TILE_ID_MAX


def _maker_get_autotile_kind(tile_id: int) -> int:
    return max(0, (int(tile_id or 0) - MAKER_TILE_ID_A1) // 48)


def _maker_get_autotile_shape(tile_id: int) -> int:
    return max(0, (int(tile_id or 0) - MAKER_TILE_ID_A1) % 48)


def _maker_to_bgra(img):
    try:
        if img is None:
            return None
        if len(img.shape) == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        if img.shape[2] == 4:
            return img.copy()
        if img.shape[2] == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    except Exception:
        return None
    return None


def _maker_alpha_blit_bgra(dst, src, x: int, y: int):
    try:
        if dst is None or src is None:
            return False
        sh, sw = src.shape[:2]
        dh, dw = dst.shape[:2]
        x0 = max(0, int(x)); y0 = max(0, int(y))
        x1 = min(dw, int(x) + sw); y1 = min(dh, int(y) + sh)
        if x0 >= x1 or y0 >= y1:
            return False
        sx0 = x0 - int(x); sy0 = y0 - int(y)
        sx1 = sx0 + (x1 - x0); sy1 = sy0 + (y1 - y0)
        patch = _maker_to_bgra(src[sy0:sy1, sx0:sx1])
        base = _maker_to_bgra(dst[y0:y1, x0:x1])
        if patch is None or base is None:
            return False
        alpha = patch[:, :, 3:4].astype(np.float32) / 255.0
        out_rgb = patch[:, :, :3].astype(np.float32) * alpha + base[:, :, :3].astype(np.float32) * (1.0 - alpha)
        out_a = np.maximum(base[:, :, 3:4], patch[:, :, 3:4])
        out = np.concatenate([out_rgb.astype(np.uint8), out_a.astype(np.uint8)], axis=2)
        dst[y0:y1, x0:x1] = out
        return True
    except Exception:
        return False


def _maker_crop_image_patch(img, sx: int, sy: int, sw: int, sh: int):
    try:
        src = _maker_to_bgra(img)
        if src is None:
            return None
        h, w = src.shape[:2]
        if sx < 0 or sy < 0 or sx >= w or sy >= h:
            return None
        patch = src[sy:min(h, sy+sh), sx:min(w, sx+sw)]
        if patch is None or patch.size == 0:
            return None
        if patch.shape[0] != sh or patch.shape[1] != sw:
            canvas = np.zeros((sh, sw, 4), dtype=np.uint8)
            _maker_alpha_blit_bgra(canvas, patch, 0, 0)
            return canvas
        return patch.copy()
    except Exception:
        return None


def _maker_is_table_tile(tile_id: int, flags: List[int] | None) -> bool:
    try:
        tid = int(tile_id or 0)
        return _maker_is_tile_a2(tid) and isinstance(flags, list) and 0 <= tid < len(flags) and bool(int(flags[tid]) & 0x80)
    except Exception:
        return False


def _maker_build_autotile_image(tile_id: int, tileset_images: Dict[str, Any], flags: List[int] | None = None):
    try:
        tid = int(tile_id or 0)
    except Exception:
        return None
    if tid < MAKER_TILE_ID_A1:
        return None
    kind = _maker_get_autotile_kind(tid)
    shape = _maker_get_autotile_shape(tid)
    tx = kind % 8
    ty = kind // 8
    bx = 0
    by = 0
    source_img = None
    table = MAKER_FLOOR_AUTOTILE_TABLE
    is_table = False
    water_surface_index = 0
    waterfall_frame = 0
    if _maker_is_tile_a1(tid):
        source_img = tileset_images.get('A1')
        if source_img is None:
            return None
        if kind == 0:
            bx = water_surface_index * 2
            by = 0
        elif kind == 1:
            bx = water_surface_index * 2
            by = 3
        elif kind == 2:
            bx = 6
            by = 0
        elif kind == 3:
            bx = 6
            by = 3
        else:
            bx = (tx // 4) * 8
            by = ty * 6 + ((tx // 2) % 2) * 3
            if kind % 2 == 0:
                bx += water_surface_index * 2
            else:
                bx += 6
                table = MAKER_WATERFALL_AUTOTILE_TABLE
                by += waterfall_frame
    elif _maker_is_tile_a2(tid):
        source_img = tileset_images.get('A2')
        if source_img is None:
            return None
        bx = tx * 2
        by = (ty - 2) * 3
        table = MAKER_FLOOR_AUTOTILE_TABLE
        is_table = _maker_is_table_tile(tid, flags)
    elif _maker_is_tile_a3(tid):
        source_img = tileset_images.get('A3')
        if source_img is None:
            return None
        bx = tx * 2
        by = (ty - 6) * 2
        table = MAKER_WALL_AUTOTILE_TABLE
    elif _maker_is_tile_a4(tid):
        source_img = tileset_images.get('A4')
        if source_img is None:
            return None
        bx = tx * 2
        by = int(math.floor((ty - 10) * 2.5 + (0.5 if (ty % 2 == 1) else 0.0)))
        table = MAKER_WALL_AUTOTILE_TABLE if (ty % 2 == 1) else MAKER_FLOOR_AUTOTILE_TABLE
    else:
        return None

    src = _maker_to_bgra(source_img)
    if src is None:
        return None
    table_entry = table[shape % len(table)]
    tile = np.zeros((48, 48, 4), dtype=np.uint8)
    w1 = h1 = 24
    for i in range(4):
        qsx, qsy = table_entry[i]
        sx1 = int((bx * 2 + qsx) * w1)
        sy1 = int((by * 2 + qsy) * h1)
        dx1 = int((i % 2) * w1)
        dy1 = int((i // 2) * h1)
        if is_table and qsy in (1, 5):
            qsx2 = ((4 - qsx) % 4) if qsy == 1 else qsx
            qsy2 = 3
            sx2 = int((bx * 2 + qsx2) * w1)
            sy2 = int((by * 2 + qsy2) * h1)
            patch2 = _maker_crop_image_patch(src, sx2, sy2, w1, h1)
            if patch2 is not None:
                _maker_alpha_blit_bgra(tile, patch2, dx1, dy1)
            patch1 = _maker_crop_image_patch(src, sx1, sy1, w1, h1 // 2)
            if patch1 is not None:
                _maker_alpha_blit_bgra(tile, patch1, dx1, dy1 + h1 // 2)
        else:
            patch = _maker_crop_image_patch(src, sx1, sy1, w1, h1)
            if patch is not None:
                _maker_alpha_blit_bgra(tile, patch, dx1, dy1)
    return tile


def _maker_any_tile_image(tile_id: int, tileset_images: Dict[str, Any], *, advanced: bool = False, flags: List[int] | None = None):
    tile = _maker_simple_tile_image(tile_id, tileset_images)
    if tile is not None:
        return tile
    if advanced:
        return _maker_build_autotile_image(tile_id, tileset_images, flags=flags)
    return None


def _maker_tileset_flags(tileset_entry: Dict[str, Any]) -> List[int]:
    try:
        flags = tileset_entry.get('flags') if isinstance(tileset_entry, dict) else None
        if isinstance(flags, list):
            return [int(v or 0) for v in flags]
    except Exception:
        pass
    return []


def _maker_tile_has_star(tile_id: int, flags: List[int]) -> bool:
    try:
        tid = int(tile_id or 0)
        if tid < 0 or tid >= len(flags):
            return False
        return bool(int(flags[tid]) & 0x10)
    except Exception:
        return False


def _maker_alpha_blit(dst, src, x: int, y: int):
    try:
        if src is None or dst is None:
            return False
        sh, sw = src.shape[:2]
        dh, dw = dst.shape[:2]
        x0 = max(0, int(x)); y0 = max(0, int(y))
        x1 = min(dw, int(x) + sw); y1 = min(dh, int(y) + sh)
        if x0 >= x1 or y0 >= y1:
            return False
        sx0 = x0 - int(x); sy0 = y0 - int(y)
        sx1 = sx0 + (x1 - x0); sy1 = sy0 + (y1 - y0)
        patch = src[sy0:sy1, sx0:sx1]
        if patch.shape[2] >= 4:
            alpha = patch[:, :, 3:4].astype(np.float32) / 255.0
            dst[y0:y1, x0:x1] = (patch[:, :, :3].astype(np.float32) * alpha + dst[y0:y1, x0:x1].astype(np.float32) * (1.0 - alpha)).astype(np.uint8)
        else:
            dst[y0:y1, x0:x1] = patch[:, :, :3]
        return True
    except Exception:
        return False


def _maker_resolve_character_image_path(project_root: Path, content_root: Path, name: str) -> Path | None:
    return _maker_resolve_image_asset_path(project_root, content_root, 'characters', name)


def _maker_select_event_preview_page(event: Dict[str, Any], preferred_index: int | None = None) -> Dict[str, Any] | None:
    try:
        pages = event.get('pages') if isinstance(event, dict) else None
        if not isinstance(pages, list) or not pages:
            return None
        if preferred_index is not None and 0 <= int(preferred_index) < len(pages):
            page = pages[int(preferred_index)]
            if isinstance(page, dict):
                return page
        # Fall back to the last page with some visible image data, otherwise the last page.
        for page in reversed(pages):
            if not isinstance(page, dict):
                continue
            image = page.get('image') if isinstance(page.get('image'), dict) else {}
            if int(image.get('tileId') or 0) > 0 or str(image.get('characterName') or '').strip():
                return page
        page = pages[-1]
        return page if isinstance(page, dict) else None
    except Exception:
        return None


def _maker_extract_character_frame(sheet_img, character_name: str, character_index: int, direction: int, pattern: int):
    try:
        img = sheet_img
        if img is None:
            return None
        h, w = img.shape[:2]
        big = str(character_name or '').startswith('$')
        if big:
            pw = max(1, w // 3)
            ph = max(1, h // 4)
            bx = 0
            by = 0
        else:
            pw = max(1, w // 12)
            ph = max(1, h // 8)
            idx = max(0, int(character_index or 0))
            bx = (idx % 4) * 3 * pw
            by = (idx // 4) * 4 * ph
        dir_map = {2: 0, 4: 1, 6: 2, 8: 3}
        row = dir_map.get(int(direction or 2), 0)
        col = max(0, min(2, int(pattern or 1)))
        x0 = bx + col * pw
        y0 = by + row * ph
        frame = img[y0:y0+ph, x0:x0+pw]
        if frame is None or frame.size == 0:
            return None
        return frame.copy()
    except Exception:
        return None


def _maker_log_preview_tile_issue(map_ctx: Dict[str, Any] | None, payload: Dict[str, Any]) -> None:
    """Append lightweight diagnostics for map preview tile render failures.

    This log is preview-only and never changes game JSON.  It is intentionally
    best-effort because the renderer must never crash the editor just to report
    a bad tile.
    """
    try:
        if not isinstance(map_ctx, dict):
            return
        project_root = map_ctx.get('project_root')
        if project_root is None:
            return
        root = Path(project_root)
        log_dir = root / MAKER_META_DIR
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "maker_map_preview_tile_failures.jsonl"
        payload = dict(payload or {})
        payload.setdefault("kind", "map_preview_tile_failure")
        payload.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass




def _maker_tile_sheet_name(tile_id: int) -> str:
    try:
        tid = int(tile_id or 0)
    except Exception:
        return ""
    if 0 <= tid < 256:
        return "B"
    if 256 <= tid < 512:
        return "C"
    if 512 <= tid < 768:
        return "D"
    if 768 <= tid < 1024:
        return "E"
    if MAKER_TILE_ID_A5 <= tid < MAKER_TILE_ID_A1:
        return "A5"
    if _maker_is_tile_a1(tid):
        return "A1"
    if _maker_is_tile_a2(tid):
        return "A2"
    if _maker_is_tile_a3(tid):
        return "A3"
    if _maker_is_tile_a4(tid):
        return "A4"
    return ""


def _maker_is_overlay_sheet_tile(tile_id: int) -> bool:
    return _maker_tile_sheet_name(tile_id) in {"B", "C", "D", "E"}


def _maker_sheet_image_debug_info(tileset_images: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        for key, img in sorted((tileset_images or {}).items()):
            try:
                shape = getattr(img, "shape", None)
                if shape is None:
                    out[str(key)] = {"loaded": False}
                    continue
                channels = int(shape[2]) if len(shape) >= 3 else 1
                out[str(key)] = {
                    "loaded": True,
                    "width": int(shape[1]),
                    "height": int(shape[0]),
                    "channels": channels,
                    "has_alpha": bool(channels >= 4),
                }
            except Exception as e:
                out[str(key)] = {"loaded": False, "error": str(e)}
    except Exception:
        pass
    return out


def _maker_infer_alpha_for_overlay_tile(tile, tile_id: int, z: int | None = None, flags: List[int] | None = None):
    """Infer missing transparency for B/C/D/E overlay tiles.

    Safe version after normal-tile source mapping fix:
    - never use arbitrary border_color keying
    - allow only obvious white / black / magenta key colors
    - additionally remove obvious WHITE/MAGENTA regions connected to the tile
      border even when the four corners are not key-colored
    """
    info: Dict[str, Any] = {"alpha_inferred": False}
    try:
        if tile is None:
            return tile, info
        if len(tile.shape) != 3:
            return tile, info
        if tile.shape[2] >= 4:
            info["has_alpha_original"] = True
            return tile, info

        tid = int(tile_id or 0)
        sheet = _maker_tile_sheet_name(tid)
        info["sheet"] = sheet
        if sheet not in {"B", "C", "D", "E"}:
            return tile, info

        z_int = int(z or 0)
        is_star = _maker_tile_has_star(tid, flags or [])
        info["z"] = z_int
        info["is_star_for_alpha"] = bool(is_star)

        # Keep lower/base B/C/D/E tiles opaque unless star.  Lower structure
        # tiles are often intentionally solid.
        if not is_star and z_int < 2:
            info["skip_reason"] = "lower_layer_non_star"
            return tile, info

        bgr = tile[:, :, :3].copy()
        h, w = bgr.shape[:2]
        if h <= 0 or w <= 0:
            return tile, info

        def _connected_to_border(mask_bool):
            try:
                mask_u8 = (mask_bool.astype(np.uint8) * 255)
                n, labels = cv2.connectedComponents(mask_u8, connectivity=8)
                if n <= 1:
                    return mask_bool & False
                border_labels = set()
                border_labels.update(int(v) for v in labels[0, :].ravel() if int(v) != 0)
                border_labels.update(int(v) for v in labels[h - 1, :].ravel() if int(v) != 0)
                border_labels.update(int(v) for v in labels[:, 0].ravel() if int(v) != 0)
                border_labels.update(int(v) for v in labels[:, w - 1].ravel() if int(v) != 0)
                if not border_labels:
                    return mask_bool & False
                out = np.isin(labels, list(border_labels))
                return out
            except Exception:
                return mask_bool & False

        # New safe supplement: obvious white/magenta connected to the outer edge.
        # This catches roof/window/stall tiles where the transparent key area is
        # on the right/bottom edge but not exactly in the four corners.
        white_mask = np.all(bgr.astype(np.int16) >= 238, axis=2)
        magenta_mask = (bgr[:, :, 0] >= 180) & (bgr[:, :, 1] <= 70) & (bgr[:, :, 2] >= 180)
        black_mask = np.all(bgr.astype(np.int16) <= 24, axis=2)
        connected_white = _connected_to_border(white_mask)
        connected_magenta = _connected_to_border(magenta_mask)
        connected_black = _connected_to_border(black_mask)
        connected_key_mask = connected_white | connected_magenta
        connected_ratio = float(connected_key_mask.mean())
        connected_black_ratio = float(connected_black.mean())
        info["border_connected_white_ratio"] = float(connected_white.mean())
        info["border_connected_magenta_ratio"] = float(connected_magenta.mean())
        info["border_connected_black_ratio"] = connected_black_ratio

        primary_threshold = 0.015 if (is_star or z_int >= 3) else 0.035
        if connected_ratio >= primary_threshold:
            bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
            bgra[:, :, 3][connected_key_mask] = 0
            info["alpha_inferred"] = True
            info["key_kind"] = "border_connected_white" if float(connected_white.mean()) >= float(connected_magenta.mean()) else "border_connected_magenta"
            info["key_ratio"] = connected_ratio
            info["key_threshold"] = primary_threshold
            return bgra, info

        # Supplemental black-key path for high overlay / star tiles.
        # Some roof / awning / wall-edge B tiles encode transparency as a pure
        # black wedge without white corner keys.  Keep this conservative.
        if is_star or z_int >= 3:
            black_only_threshold = 0.012
            black_only_max = 0.34
            if black_only_threshold <= connected_black_ratio <= black_only_max:
                bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
                bgra[:, :, 3][connected_black] = 0
                info["alpha_inferred"] = True
                info["key_kind"] = "border_connected_black"
                info["key_ratio"] = connected_black_ratio
                info["key_threshold"] = black_only_threshold
                info["key_threshold_max"] = black_only_max
                return bgra, info

        # Original safe corner-key path.
        corners = np.array([bgr[0, 0], bgr[0, w - 1], bgr[h - 1, 0], bgr[h - 1, w - 1]], dtype=np.int16)
        rounded = (corners // 8) * 8
        buckets: Dict[Tuple[int, int, int], int] = {}
        for c in rounded:
            key = (int(c[0]), int(c[1]), int(c[2]))
            buckets[key] = buckets.get(key, 0) + 1
        key_color = np.array(max(buckets.items(), key=lambda kv: kv[1])[0], dtype=np.int16)
        corner_spread = int(np.max(corners.max(axis=0) - corners.min(axis=0)))

        try:
            border_width = 2 if min(h, w) >= 16 else 1
            border = np.concatenate([
                bgr[:border_width, :, :].reshape(-1, 3),
                bgr[h-border_width:, :, :].reshape(-1, 3),
                bgr[:, :border_width, :].reshape(-1, 3),
                bgr[:, w-border_width:, :].reshape(-1, 3),
            ], axis=0).astype(np.int16)
            rounded_border = (border // 8) * 8
            border_buckets: Dict[Tuple[int, int, int], int] = {}
            for c in rounded_border:
                bkey = (int(c[0]), int(c[1]), int(c[2]))
                border_buckets[bkey] = border_buckets.get(bkey, 0) + 1
            border_share = float(max(border_buckets.values()) / max(1, len(border)))
        except Exception:
            border_share = 0.0

        obvious_white = bool(np.all(key_color >= 232))
        obvious_black = bool(np.all(key_color <= 24))
        obvious_magenta = bool(key_color[0] >= 180 and key_color[1] <= 60 and key_color[2] >= 180)

        info["corner_key_bgr"] = [int(v) for v in key_color]
        info["corner_spread"] = corner_spread
        info["border_share"] = border_share
        info["relaxed_candidate"] = False

        if not (obvious_white or obvious_black or obvious_magenta):
            info["skip_reason"] = "corner_key_not_obvious"
            info["rollback_note"] = "border_color_disabled"
            return tile, info

        tol = 12
        ratio_threshold = 0.05 if (is_star or z_int >= 3) else 0.08
        key_kind = "white" if obvious_white else ("black" if obvious_black else "magenta")

        diff = np.abs(bgr.astype(np.int16) - key_color.reshape(1, 1, 3))
        mask = np.all(diff <= tol, axis=2)
        ratio = float(mask.mean())

        info["key_ratio"] = ratio
        info["key_tol"] = int(tol)
        info["key_threshold"] = float(ratio_threshold)

        if ratio < ratio_threshold:
            info["skip_reason"] = "key_ratio_low"
            return tile, info

        bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        alpha = bgra[:, :, 3]
        alpha[mask] = 0

        try:
            kernel = np.ones((2, 2), np.uint8)
            transparent = (alpha == 0).astype(np.uint8) * 255
            transparent = cv2.morphologyEx(transparent, cv2.MORPH_OPEN, kernel)
            alpha[transparent > 0] = 0
            bgra[:, :, 3] = alpha
        except Exception:
            pass

        info["alpha_inferred"] = True
        info["key_kind"] = key_kind
        return bgra, info
    except Exception as e:
        info["alpha_infer_error"] = str(e)
        return tile, info


def _maker_infer_alpha_for_a2_autotile_tile(tile, tile_id: int, z: int | None = None, flags: List[int] | None = None):
    """Infer missing transparency for selected A2 autotile overlay results.

    Some RPG Maker projects have A2 autotile source images loaded as RGB.  The
    assembled autotile becomes BGRA, but the alpha is fully opaque, so leftover
    white/black key areas from cliff/grass edge pieces remain visible.  Only
    apply this to A2 overlay-ish layers (z>=1), and only to obvious white plus
    border-connected black/white key regions.
    """
    info: Dict[str, Any] = {"a2_alpha_inferred": False}
    try:
        if tile is None:
            return tile, info
        tid = int(tile_id or 0)
        if not _maker_is_tile_a2(tid):
            return tile, info
        z_int = int(z or 0)
        info["a2_z"] = z_int
        if z_int < 1:
            info["a2_skip_reason"] = "base_layer"
            return tile, info
        if len(tile.shape) != 3:
            return tile, info

        if tile.shape[2] >= 4:
            bgra = tile.copy()
        else:
            bgra = cv2.cvtColor(tile[:, :, :3], cv2.COLOR_BGR2BGRA)
        bgr = bgra[:, :, :3]
        h, w = bgr.shape[:2]
        if h <= 0 or w <= 0:
            return tile, info

        def _connected_to_border(mask_bool):
            try:
                mask_u8 = (mask_bool.astype(np.uint8) * 255)
                n, labels = cv2.connectedComponents(mask_u8, connectivity=8)
                if n <= 1:
                    return mask_bool & False
                border_labels = set()
                border_labels.update(int(v) for v in labels[0, :].ravel() if int(v) != 0)
                border_labels.update(int(v) for v in labels[h - 1, :].ravel() if int(v) != 0)
                border_labels.update(int(v) for v in labels[:, 0].ravel() if int(v) != 0)
                border_labels.update(int(v) for v in labels[:, w - 1].ravel() if int(v) != 0)
                if not border_labels:
                    return mask_bool & False
                return np.isin(labels, list(border_labels))
            except Exception:
                return mask_bool & False

        bgr_i = bgr.astype(np.int16)
        white_mask = np.all(bgr_i >= 238, axis=2)
        # Use strict black/dark detection.  This is intentionally not a general
        # dark-color keyer; it targets the lost transparent black background in
        # A2 edge autotiles.
        black_mask = np.all(bgr_i <= 24, axis=2)

        connected_white = _connected_to_border(white_mask)
        connected_black = _connected_to_border(black_mask)
        white_ratio = float(connected_white.mean())
        black_ratio = float(connected_black.mean())

        info["a2_border_connected_white_ratio"] = white_ratio
        info["a2_border_connected_black_ratio"] = black_ratio
        info["a2_kind"] = _maker_get_autotile_kind(tid)
        info["a2_shape"] = _maker_get_autotile_shape(tid)

        key_mask = np.zeros((h, w), dtype=bool)
        # White fringe is the safest signal.
        if white_ratio >= 0.003:
            key_mask |= connected_white
            # Remove neighboring lost black background only when there is a
            # clear white key fringe in the same tile.  This avoids punching
            # legitimate dark A2 texture/shadow tiles.
            if 0.006 <= black_ratio <= 0.42:
                key_mask |= connected_black
        else:
            # Black-only cleanup is risky.  Allow it only for a small-to-medium
            # border-connected pure black region, not for mostly dark tiles.
            if 0.035 <= black_ratio <= 0.28:
                key_mask |= connected_black

        key_ratio = float(key_mask.mean())
        info["a2_key_ratio"] = key_ratio
        if key_ratio <= 0.0:
            info["a2_skip_reason"] = "no_border_key"
            return tile, info
        if key_ratio > 0.50:
            info["a2_skip_reason"] = "key_ratio_too_high"
            return tile, info

        bgra[:, :, 3][key_mask] = 0
        info["a2_alpha_inferred"] = True
        info["a2_key_kind"] = "border_connected_white_black" if (white_ratio >= 0.003 and black_ratio >= 0.006) else ("border_connected_white" if white_ratio >= 0.003 else "border_connected_black")
        return bgra, info
    except Exception as e:
        info["a2_alpha_infer_error"] = str(e)
        return tile, info


def _maker_tile_trace_entry(tile_id: int, *, x: int | None = None, y: int | None = None, z: int | None = None, flags: List[int] | None = None, result: str = "") -> Dict[str, Any]:
    """Return a compact debug entry for one map tile.

    This is used only for preview diagnostics.  It helps identify which tile_id
    produced a visually wrong wall/pillar/roof/etc.
    """
    try:
        tid = int(tile_id or 0)
    except Exception:
        tid = 0
    entry: Dict[str, Any] = {
        "x": x,
        "y": y,
        "z": z,
        "tile_id": tid,
        "result": str(result or ""),
    }
    try:
        if tid <= 0:
            entry["type"] = "empty"
        elif tid < 256:
            entry.update({"type": "normal", "sheet": "B", "local_index": tid % 256})
        elif tid < 512:
            entry.update({"type": "normal", "sheet": "C", "local_index": tid % 256})
        elif tid < 768:
            entry.update({"type": "normal", "sheet": "D", "local_index": tid % 256})
        elif tid < 1024:
            entry.update({"type": "normal", "sheet": "E", "local_index": tid % 256})
        elif MAKER_TILE_ID_A5 <= tid < MAKER_TILE_ID_A1:
            entry.update({"type": "normal", "sheet": "A5", "local_index": tid - MAKER_TILE_ID_A5})
        if entry.get("type") == "normal":
            sx, sy, sw, sh = _maker_normal_tile_source_rect(tid)
            entry.update({"source_sx": sx, "source_sy": sy, "source_w": sw, "source_h": sh})
        elif _maker_is_tile_a1(tid):
            entry.update({"type": "autotile", "sheet": "A1", "kind": _maker_get_autotile_kind(tid), "shape": _maker_get_autotile_shape(tid)})
        elif _maker_is_tile_a2(tid):
            entry.update({"type": "autotile", "sheet": "A2", "kind": _maker_get_autotile_kind(tid), "shape": _maker_get_autotile_shape(tid), "is_table": _maker_is_table_tile(tid, flags)})
        elif _maker_is_tile_a3(tid):
            entry.update({"type": "autotile", "sheet": "A3", "kind": _maker_get_autotile_kind(tid), "shape": _maker_get_autotile_shape(tid)})
        elif _maker_is_tile_a4(tid):
            entry.update({"type": "autotile", "sheet": "A4", "kind": _maker_get_autotile_kind(tid), "shape": _maker_get_autotile_shape(tid)})
        else:
            entry["type"] = "unknown"
        entry["is_star"] = bool(_maker_tile_has_star(tid, flags or [])) if tid > 0 else False
    except Exception:
        entry["type"] = "trace_error"
    return entry


def _maker_log_preview_tile_trace(map_ctx: Dict[str, Any] | None, payload: Dict[str, Any]) -> None:
    """Write a detailed tile trace for the most recent map preview render.

    Outputs:
    - maker_meta/maker_map_preview_tile_trace_last.json  (full latest trace)
    - maker_meta/maker_map_preview_tile_trace.jsonl      (small rolling summary)
    """
    try:
        if not isinstance(map_ctx, dict):
            return
        project_root = map_ctx.get('project_root')
        if project_root is None:
            return
        root = Path(project_root)
        log_dir = root / MAKER_META_DIR
        log_dir.mkdir(parents=True, exist_ok=True)

        payload = dict(payload or {})
        payload.setdefault("kind", "map_preview_tile_trace")
        payload.setdefault("ts", datetime.now().isoformat(timespec="seconds"))

        last_path = log_dir / "maker_map_preview_tile_trace_last.json"
        with last_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

        summary = {
            "kind": payload.get("kind"),
            "ts": payload.get("ts"),
            "map_file": payload.get("map_file"),
            "map_id": payload.get("map_id"),
            "tileset_id": payload.get("tileset_id"),
            "crop": payload.get("crop"),
            "advanced": payload.get("advanced"),
            "tile_count": len(payload.get("tiles") or []),
            "failure_count": len(payload.get("failures") or []),
            "trace_last": str(last_path),
        }
        summary_path = log_dir / "maker_map_preview_tile_trace.jsonl"
        with summary_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _maker_blit_tile_to_bgr_canvas(canvas, tile, x: int, y: int) -> bool:
    """Draw a tile on a BGR scene canvas while preserving tile alpha."""
    try:
        if tile is None or canvas is None:
            return False
        if len(tile.shape) == 3 and tile.shape[2] >= 4:
            return bool(_maker_alpha_blit(canvas, tile, x, y))
        # 3-channel tiles are still direct-copy.  This is fine for A5/base tiles
        # and for fully opaque autotile output.
        th, tw = tile.shape[:2]
        canvas[y:y+th, x:x+tw] = tile[:, :, :3]
        return True
    except Exception:
        return False


def _maker_write_debug_image(path: Path, img) -> bool:
    """Write debug PNG/JPG safely even when the project path contains Korean.

    OpenCV cv2.imwrite() can silently fail on Windows Unicode paths.  imencode()
    + ndarray.tofile() avoids that path-encoding problem.
    """
    try:
        if img is None:
            return False
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix.lower() or ".png"
        if ext not in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
            ext = ".png"
        ok, buf = cv2.imencode(ext, img)
        if not ok or buf is None:
            return False
        buf.tofile(str(path))
        return bool(path.is_file() and path.stat().st_size > 0)
    except Exception:
        return False


def _maker_validation_tile_basename(entry: Dict[str, Any]) -> str:
    try:
        x = int(entry.get("x") or 0)
        y = int(entry.get("y") or 0)
        z = int(entry.get("z") or 0)
        tid = int(entry.get("tile_id") or 0)
        sheet = str(entry.get("sheet") or "UNK")
        result = str(entry.get("result") or "")
        return f"x{x:03d}_y{y:03d}_z{z}_id{tid:04d}_{sheet}_{result}"
    except Exception:
        return "tile"


def _maker_dump_preview_validation(map_ctx: Dict[str, Any] | None, payload: Dict[str, Any]) -> None:
    """Dump the latest map-preview validation artifacts.

    Purpose:
    - show which tile image was cut/built for each x/y/z
    - show the image before alpha inference and after alpha inference
    - save the composite scene before and after deferred star overlays
    This is a verification tool, not a final user feature.
    """
    try:
        if not isinstance(map_ctx, dict):
            return
        project_root = map_ctx.get("project_root")
        if project_root is None:
            return
        root = Path(project_root)
        dump_dir = root / MAKER_META_DIR / "maker_map_preview_validate_last"
        if dump_dir.exists():
            shutil.rmtree(dump_dir, ignore_errors=True)
        dump_dir.mkdir(parents=True, exist_ok=True)

        summary = dict(payload or {})
        tile_samples = summary.pop("tile_samples", []) if isinstance(summary, dict) else []
        scene_raw = summary.pop("scene_raw", None) if isinstance(summary, dict) else None
        scene_with_star = summary.pop("scene_with_star", None) if isinstance(summary, dict) else None

        # Save composite images first.  Record actual write results because
        # OpenCV path issues can otherwise leave JSON saying a file exists when
        # the PNG was not created.
        wrote_scene_raw = _maker_write_debug_image(dump_dir / "scene_raw.png", scene_raw) if scene_raw is not None else False
        wrote_scene_with_star = _maker_write_debug_image(dump_dir / "scene_with_star.png", scene_with_star) if scene_with_star is not None else False

        summary["scene_raw_file"] = "scene_raw.png" if wrote_scene_raw else ""
        summary["scene_raw_written"] = bool(wrote_scene_raw)
        summary["scene_with_star_file"] = "scene_with_star.png" if wrote_scene_with_star else ""
        summary["scene_with_star_written"] = bool(wrote_scene_with_star)

        saved_tiles = []
        tiles_dir = dump_dir / "tiles"
        for item in (tile_samples or []):
            try:
                if not isinstance(item, dict):
                    continue
                entry = dict(item.get("entry") or {})
                base = _maker_validation_tile_basename(entry)
                raw_img = item.get("raw")
                post_img = item.get("post")
                raw_name = f"{base}__raw.png"
                post_name = f"{base}__post.png"
                wrote_raw = _maker_write_debug_image(tiles_dir / raw_name, raw_img)
                wrote_post = _maker_write_debug_image(tiles_dir / post_name, post_img)
                meta = dict(entry)
                raw_path = tiles_dir / raw_name
                post_path = tiles_dir / post_name
                meta["raw_file"] = f"tiles/{raw_name}" if wrote_raw else ""
                meta["raw_written"] = bool(wrote_raw)
                meta["raw_file_size"] = int(raw_path.stat().st_size) if wrote_raw and raw_path.is_file() else 0
                meta["post_file"] = f"tiles/{post_name}" if wrote_post else ""
                meta["post_written"] = bool(wrote_post)
                meta["post_file_size"] = int(post_path.stat().st_size) if wrote_post and post_path.is_file() else 0
                saved_tiles.append(meta)
            except Exception:
                continue

        summary["saved_tile_count"] = len(saved_tiles)
        summary["written_raw_tile_count"] = sum(1 for t in saved_tiles if t.get("raw_written"))
        summary["written_post_tile_count"] = sum(1 for t in saved_tiles if t.get("post_written"))
        summary["tiles"] = saved_tiles

        with (dump_dir / "summary.json").open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass


def _maker_render_local_map_scene(crop_info: Dict[str, Any], map_ctx: Dict[str, Any], *, advanced: bool = False, tile_validation: bool = False) -> Dict[str, Any]:
    scene = {'rendered_any': False, 'image': None, 'star_tiles': [], 'failures': [], 'tile_trace': []}
    tile_validation = bool(tile_validation)
    debug_tile_samples: List[Dict[str, Any]] = []
    try:
        map_data = map_ctx.get('map_data') if isinstance(map_ctx, dict) else None
        if not isinstance(map_data, dict):
            return scene
        layers = map_data.get('data') if isinstance(map_data.get('data'), list) else []
        if not isinstance(layers, list) or not layers:
            return scene
        mw = int(map_data.get('width') or 0)
        mh = int(map_data.get('height') or 0)
        if mw <= 0 or mh <= 0:
            return scene
        tileset_images = map_ctx.get('tileset_images') if isinstance(map_ctx.get('tileset_images'), dict) else {}
        if not isinstance(tileset_images, dict) or not tileset_images:
            return scene

        flags = _maker_tileset_flags(map_ctx.get('tileset_entry') if isinstance(map_ctx.get('tileset_entry'), dict) else {})
        x0 = int(crop_info.get('x0') or 0)
        y0 = int(crop_info.get('y0') or 0)
        cols = int(crop_info.get('cols') or 0)
        rows = int(crop_info.get('rows') or 0)
        tile_px = int(crop_info.get('tile_size') or 0)
        if cols <= 0 or rows <= 0 or tile_px <= 0:
            return scene

        scene_img = np.full((rows * tile_px, cols * tile_px, 3), 42, dtype=np.uint8)
        star_tiles = []
        shadow_items = []
        failures = []
        trace_tiles = []
        rendered_any = False

        for ry in range(rows):
            for rx in range(cols):
                mx = x0 + rx
                my = y0 + ry
                if mx < 0 or my < 0 or mx >= mw or my >= mh:
                    continue
                px0 = rx * tile_px
                py0 = ry * tile_px

                try:
                    shadow_bits = _maker_map_get_tile(layers, mw, mh, mx, my, 4) if advanced else 0
                    if shadow_bits:
                        shadow_items.append((px0, py0, int(shadow_bits)))
                        if tile_validation:
                            trace_tiles.append({
                                "x": int(mx), "y": int(my), "z": 4,
                                "tile_id": int(shadow_bits),
                                "type": "shadow",
                                "sheet": "shadow",
                                "result": "shadow_queued",
                            })
                except Exception as e:
                    if tile_validation and len(failures) < 80:
                        failures.append({"phase": "shadow", "x": mx, "y": my, "error": str(e), "error_type": type(e).__name__})

                for z in range(4):
                    try:
                        tid = _maker_map_get_tile(layers, mw, mh, mx, my, z)
                        if tid <= 0:
                            continue
                        entry = _maker_tile_trace_entry(tid, x=int(mx), y=int(my), z=int(z), flags=flags, result="start") if tile_validation else None
                        tile = _maker_any_tile_image(tid, tileset_images, advanced=advanced, flags=flags)
                        if tile is None:
                            if tile_validation and entry is not None:
                                entry["result"] = "tile_none_skipped"
                                trace_tiles.append(entry)
                                if len(failures) < 80 and advanced and tid >= MAKER_TILE_ID_A1:
                                    failures.append({"phase": "tile_none", "x": mx, "y": my, "z": z, "tile_id": int(tid), "kind": _maker_get_autotile_kind(tid), "shape": _maker_get_autotile_shape(tid)})
                            continue

                        raw_tile_debug = tile.copy() if tile_validation else None
                        if tile_validation and entry is not None:
                            entry["raw_tile_w"] = int(tile.shape[1]) if getattr(tile, "shape", None) is not None and len(tile.shape) >= 2 else None
                            entry["raw_tile_h"] = int(tile.shape[0]) if getattr(tile, "shape", None) is not None and len(tile.shape) >= 2 else None
                            entry["has_alpha_original"] = bool(len(tile.shape) == 3 and tile.shape[2] >= 4)

                        alpha_info = {"alpha_inferred": False, "skip_reason": "validation_off"}
                        a2_alpha_info = {"a2_alpha_inferred": False, "a2_skip_reason": "validation_off"}
                        # Color-key transparency fallback is now validation/debug only.
                        # Normal preview should follow RPG Maker more closely:
                        # preserve source alpha, and do not guess transparency from
                        # white/black fill colors during everyday translation work.
                        if tile_validation:
                            tile, alpha_info = _maker_infer_alpha_for_overlay_tile(tile, tid, z=z, flags=flags)
                            tile, a2_alpha_info = _maker_infer_alpha_for_a2_autotile_tile(tile, tid, z=z, flags=flags)
                        if tile_validation and entry is not None:
                            if isinstance(alpha_info, dict):
                                entry.update({k: v for k, v in alpha_info.items() if k not in {"sheet"}})
                            if isinstance(a2_alpha_info, dict):
                                entry.update(a2_alpha_info)
                            entry["has_alpha"] = bool(len(tile.shape) == 3 and tile.shape[2] >= 4)

                        if tile_px != 48:
                            tile = cv2.resize(tile, (tile_px, tile_px), interpolation=cv2.INTER_AREA if tile_px < 48 else cv2.INTER_NEAREST)
                            if tile_validation and entry is not None:
                                entry["scaled_tile_px"] = int(tile_px)

                        if advanced and _maker_tile_has_star(tid, flags):
                            star_tiles.append((px0, py0, tile))
                            if tile_validation and entry is not None:
                                entry["result"] = "star_deferred"
                            rendered_any = True
                        else:
                            if _maker_blit_tile_to_bgr_canvas(scene_img, tile, px0, py0):
                                if tile_validation and entry is not None:
                                    entry["result"] = "rendered_alpha" if entry.get("has_alpha") else "rendered_copy"
                                rendered_any = True
                            else:
                                if tile_validation and entry is not None:
                                    entry["result"] = "blit_failed"
                                if tile_validation and len(failures) < 80:
                                    failures.append({"phase": "blit_failed", "x": mx, "y": my, "z": z, "tile_id": int(tid)})

                        if tile_validation and entry is not None:
                            trace_tiles.append(entry)
                            try:
                                debug_tile_samples.append({
                                    "entry": dict(entry),
                                    "raw": raw_tile_debug,
                                    "post": tile.copy() if tile is not None else None,
                                })
                            except Exception:
                                pass
                    except Exception as e:
                        if tile_validation and len(failures) < 80:
                            try:
                                tid_for_log = _maker_map_get_tile(layers, mw, mh, mx, my, z)
                            except Exception:
                                tid_for_log = 0
                            failure = {
                                "phase": "tile_render",
                                "x": int(mx),
                                "y": int(my),
                                "z": int(z),
                                "tile_id": int(tid_for_log or 0),
                                "kind": _maker_get_autotile_kind(tid_for_log) if int(tid_for_log or 0) >= MAKER_TILE_ID_A1 else None,
                                "shape": _maker_get_autotile_shape(tid_for_log) if int(tid_for_log or 0) >= MAKER_TILE_ID_A1 else None,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            }
                            failures.append(failure)
                            trace_tiles.append(dict(failure, result="exception_skipped"))
                        continue

        if advanced and shadow_items and rendered_any:
            for px0, py0, bits in shadow_items:
                try:
                    overlay = scene_img[py0:py0+tile_px, px0:px0+tile_px].copy()
                    half = max(1, tile_px // 2)
                    quads = [((0, 0), 1), ((half, 0), 2), ((0, half), 4), ((half, half), 8)]
                    for (ox, oy), bit in quads:
                        if bits & bit:
                            cv2.rectangle(overlay, (ox, oy), (min(tile_px, ox + half), min(tile_px, oy + half)), (0, 0, 0), -1)
                    scene_img[py0:py0+tile_px, px0:px0+tile_px] = cv2.addWeighted(overlay, 0.35, scene_img[py0:py0+tile_px, px0:px0+tile_px], 0.65, 0)
                except Exception as e:
                    if tile_validation and len(failures) < 80:
                        failures.append({"phase": "shadow_blend", "px": int(px0), "py": int(py0), "error": str(e), "error_type": type(e).__name__})
                    continue

        scene['rendered_any'] = bool(rendered_any or star_tiles)
        scene['image'] = scene_img if scene['rendered_any'] else None
        scene['star_tiles'] = star_tiles
        scene['failures'] = failures if tile_validation else []
        scene['tile_trace'] = trace_tiles if tile_validation else []

        if tile_validation:
            try:
                scene_with_star = scene_img.copy()
                for sx, sy, st in star_tiles:
                    _maker_blit_tile_to_bgr_canvas(scene_with_star, st, sx, sy)
                tileset_entry = map_ctx.get('tileset_entry') if isinstance(map_ctx.get('tileset_entry'), dict) else {}
                _maker_dump_preview_validation(map_ctx, {
                    "map_file": str(map_ctx.get("map_file") or map_data.get("map_file") or ""),
                    "map_id": map_data.get("id"),
                    "map_width": mw,
                    "map_height": mh,
                    "tileset_id": map_ctx.get("tileset_id"),
                    "tileset_name": str(tileset_entry.get("name") or ""),
                    "loaded_sheets": sorted([str(k) for k in (tileset_images or {}).keys()]),
                    "sheet_images": _maker_sheet_image_debug_info(tileset_images),
                    "crop": dict(crop_info or {}),
                    "advanced": bool(advanced),
                    "rendered_any": bool(scene['rendered_any']),
                    "tile_trace_count": len(trace_tiles),
                    "failures": failures,
                    "tile_samples": debug_tile_samples,
                    "scene_raw": scene_img if scene['rendered_any'] else None,
                    "scene_with_star": scene_with_star if scene['rendered_any'] else None,
                })
            except Exception:
                pass

            if trace_tiles or failures:
                try:
                    tileset_entry = map_ctx.get('tileset_entry') if isinstance(map_ctx.get('tileset_entry'), dict) else {}
                    _maker_log_preview_tile_trace(map_ctx, {
                        "map_file": str(map_ctx.get("map_file") or map_data.get("map_file") or ""),
                        "map_id": map_data.get("id"),
                        "map_width": mw,
                        "map_height": mh,
                        "tileset_id": map_ctx.get("tileset_id"),
                        "tileset_name": str(tileset_entry.get("name") or ""),
                        "loaded_sheets": sorted([str(k) for k in (tileset_images or {}).keys()]),
                        "sheet_images": _maker_sheet_image_debug_info(tileset_images),
                        "crop": dict(crop_info or {}),
                        "advanced": bool(advanced),
                        "rendered_any": bool(scene['rendered_any']),
                        "tiles": trace_tiles,
                        "failures": failures,
                    })
                except Exception:
                    pass

            if failures:
                try:
                    _maker_log_preview_tile_issue(map_ctx, {
                        "phase": "scene_render",
                        "map_id": map_data.get("id"),
                        "map_width": mw,
                        "map_height": mh,
                        "crop": dict(crop_info or {}),
                        "advanced": bool(advanced),
                        "failure_count": len(failures),
                        "failures": failures[:20],
                    })
                except Exception:
                    pass
        return scene
    except Exception as e:
        scene['rendered_any'] = False
        scene['image'] = None
        scene['failures'] = [{"phase": "scene_fatal", "error": str(e), "error_type": type(e).__name__}] if tile_validation else []
        if tile_validation:
            try:
                _maker_log_preview_tile_issue(map_ctx, scene['failures'][0])
                _maker_log_preview_tile_trace(map_ctx, {"rendered_any": False, "tiles": [], "failures": scene['failures']})
            except Exception:
                pass
        return scene

def _maker_draw_event_graphics(img, crop_info: Dict[str, Any], map_ctx: Dict[str, Any], focus_event_id: int = 0) -> bool:
    rendered = False
    try:
        map_data = map_ctx.get('map_data') if isinstance(map_ctx, dict) else None
        project_root = map_ctx.get('project_root') if isinstance(map_ctx, dict) else None
        content_root = map_ctx.get('content_root') if isinstance(map_ctx, dict) else None
        tileset_images = map_ctx.get('tileset_images') if isinstance(map_ctx, dict) else None
        if not isinstance(map_data, dict) or project_root is None or content_root is None:
            return False
        events = map_data.get('events') if isinstance(map_data.get('events'), list) else []
        x0 = int(crop_info.get('x0') or 0); y0 = int(crop_info.get('y0') or 0)
        cols = int(crop_info.get('cols') or 0); rows = int(crop_info.get('rows') or 0)
        tile_px = int(crop_info.get('tile_size') or 0)
        origin_x = int(crop_info.get('origin_x') or 0); origin_y = int(crop_info.get('origin_y') or 0)
        for ev in events:
            if not isinstance(ev, dict):
                continue
            try:
                ex = int(ev.get('x') or 0); ey = int(ev.get('y') or 0); eid = int(ev.get('id') or 0)
            except Exception:
                continue
            if ex < x0 or ex >= x0 + cols or ey < y0 or ey >= y0 + rows:
                continue
            preferred_page = None if focus_event_id != eid else None
            page = _maker_select_event_preview_page(ev, preferred_page)
            if not isinstance(page, dict):
                continue
            image = page.get('image') if isinstance(page.get('image'), dict) else {}
            tile_id = int(image.get('tileId') or 0)
            px = int(origin_x + (ex - x0) * tile_px)
            py = int(origin_y + (ey - y0) * tile_px)
            if tile_id > 0 and isinstance(tileset_images, dict):
                event_flags = _maker_tileset_flags(map_ctx.get('tileset_entry') if isinstance(map_ctx.get('tileset_entry'), dict) else {})
                tile = _maker_any_tile_image(tile_id, tileset_images, advanced=True, flags=event_flags)
                if tile is not None:
                    tile, _alpha_info = _maker_infer_alpha_for_overlay_tile(tile, tile_id, z=3, flags=event_flags)
                    if tile_px != 48:
                        tile = cv2.resize(tile, (tile_px, tile_px), interpolation=cv2.INTER_AREA if tile_px < 48 else cv2.INTER_NEAREST)
                    if tile.ndim == 3 and tile.shape[2] >= 4:
                        _maker_alpha_blit(img, tile, px, py)
                    else:
                        img[py:py+tile_px, px:px+tile_px] = tile[:, :, :3]
                    rendered = True
                continue
            cname = str(image.get('characterName') or '').strip()
            if not cname:
                continue
            cidx = int(image.get('characterIndex') or 0)
            direction = int(image.get('direction') or 2)
            pattern = int(image.get('pattern') or 1)
            src = _maker_resolve_character_image_path(project_root, content_root, cname)
            if src is None:
                continue
            prepared = _maker_preview_prepare_image_asset_for_root(project_root, src, category='characters')
            if prepared is None:
                continue
            sheet = _maker_cv2_read_image_cached(prepared, cv2.IMREAD_UNCHANGED)
            frame = _maker_extract_character_frame(sheet, cname, cidx, direction, pattern)
            if frame is None:
                continue
            fh, fw = frame.shape[:2]
            if fh <= 0 or fw <= 0:
                continue
            # Scale character to roughly 1.2 tiles high while preserving aspect.
            target_h = max(tile_px, int(tile_px * 1.2))
            scale = target_h / max(1, fh)
            target_w = max(1, int(round(fw * scale)))
            frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_NEAREST)
            draw_x = int(px + tile_px / 2 - target_w / 2)
            draw_y = int(py + tile_px - target_h)
            _maker_alpha_blit(img, frame, draw_x, draw_y)
            rendered = True
    except Exception:
        return rendered
    return rendered

def _maker_load_local_map_tile_preview_context(preview_path: Path, map_file: str, settings: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    try:
        project_root = _maker_resolve_project_root_for_preview(preview_path, settings)
        if project_root is None:
            return None
        game_root, data_dir, content_root, _engine_info = _maker_content_paths_for_project(project_root)
        map_path = Path(data_dir) / str(map_file or '')
        if not map_path.is_file():
            return None
        map_data = _maker_preview_read_json_cached(map_path)
        if not isinstance(map_data, dict):
            return None
        tilesets_path = Path(data_dir) / 'Tilesets.json'
        tilesets = _maker_preview_read_json_cached(tilesets_path)
        if not isinstance(tilesets, list):
            return None
        tileset_id = int(map_data.get('tilesetId') or 0)
        tileset_entry = None
        for entry in tilesets:
            if isinstance(entry, dict) and int(entry.get('id') or 0) == tileset_id:
                tileset_entry = entry
                break
        if not isinstance(tileset_entry, dict):
            return None
        names = tileset_entry.get('tilesetNames') if isinstance(tileset_entry.get('tilesetNames'), list) else []
        named_images = {}
        keys = ['A1', 'A2', 'A3', 'A4', 'A5', 'B', 'C', 'D', 'E']
        for idx, key in enumerate(keys):
            try:
                name = str(names[idx] or '').strip()
            except Exception:
                name = ''
            if not name:
                continue
            src = _maker_resolve_tileset_image_path(project_root, content_root, name)
            if src is None:
                continue
            prepared = _maker_preview_prepare_image_asset_for_root(project_root, src, category='tilesets')
            if prepared is None:
                continue
            # Tileset preview must preserve the source PNG alpha channel.
            # RPG Maker itself does not guess transparency from white/black key
            # colors here; it relies on the image alpha plus tilemap rules.
            img = _maker_cv2_read_image_cached(prepared, cv2.IMREAD_UNCHANGED)
            if img is not None:
                named_images[key] = img
        return {
            'project_root': project_root,
            'game_root': game_root,
            'data_dir': data_dir,
            'content_root': content_root,
            'map_file': str(map_file or ''),
            'map_data': map_data,
            'tileset_id': tileset_id,
            'tileset_entry': tileset_entry,
            'tileset_images': named_images,
        }
    except Exception:
        return None


def _draw_local_map_tiles(img, crop_info: Dict[str, Any], map_ctx: Dict[str, Any]) -> bool:
    try:
        map_data = map_ctx.get('map_data') if isinstance(map_ctx, dict) else None
        if not isinstance(map_data, dict):
            return False
        layers = map_data.get('data') if isinstance(map_data.get('data'), list) else []
        if not isinstance(layers, list) or not layers:
            return False
        mw = int(map_data.get('width') or 0)
        mh = int(map_data.get('height') or 0)
        if mw <= 0 or mh <= 0:
            return False
        tileset_images = map_ctx.get('tileset_images') if isinstance(map_ctx.get('tileset_images'), dict) else {}
        if not isinstance(tileset_images, dict) or not tileset_images:
            return False
        x0 = int(crop_info.get('x0') or 0)
        y0 = int(crop_info.get('y0') or 0)
        cols = int(crop_info.get('cols') or 0)
        rows = int(crop_info.get('rows') or 0)
        tile_px = int(crop_info.get('tile_size') or 0)
        map_left = int(crop_info.get('origin_x') or 0)
        map_top = int(crop_info.get('origin_y') or 0)
        rendered_any = False
        for ry in range(rows):
            for rx in range(cols):
                mx = x0 + rx
                my = y0 + ry
                px0 = map_left + rx * tile_px
                py0 = map_top + ry * tile_px
                if mx < 0 or my < 0 or mx >= mw or my >= mh:
                    continue
                # draw lower->upper tile layers. Ignore shadow/region layers.
                for z in range(4):
                    tid = _maker_map_get_tile(layers, mw, mh, mx, my, z)
                    if tid <= 0:
                        continue
                    tile = _maker_simple_tile_image(tid, tileset_images)
                    if tile is None:
                        continue
                    if tile_px != 48:
                        tile = cv2.resize(tile, (tile_px, tile_px), interpolation=cv2.INTER_AREA if tile_px < 48 else cv2.INTER_NEAREST)
                    img[py0:py0+tile_px, px0:px0+tile_px] = tile
                    rendered_any = True
        return rendered_any
    except Exception:
        return False

def _placeholder_image(
    path: Path,
    *,
    map_id: int,
    map_name: str,
    width: int,
    height: int,
    events: List[Dict[str, Any]],
    text_count: int,
    engine_label: str = "RPG Maker",
    preview_settings: Dict[str, Any] | None = None,
    focus_event: Dict[str, Any] | None = None,
    page_meta: Dict[str, Any] | None = None,
):
    """Create a lightweight map-page placeholder.

    Stage 1 map preview focuses on the selected dialogue event and shows a
    cropped grid around it.  This is intentionally not a full RPG Maker tile
    renderer; it is a safe context preview that never edits cloned game JSON.
    """
    st = normalize_maker_preview_settings(preview_settings)
    defer_tile_render = bool(st.get("defer_tile_render", False))
    force_preview_rebuild = bool(st.get("force_maker_preview_rebuild", False) or st.get("force_preview_rebuild", False))
    placeholder_cache_path = None
    placeholder_cache_hit = False
    placeholder_cache_should_write = False
    canvas_w = int(st.get("screen_width") or 816)
    canvas_h = int(st.get("screen_height") or 624)
    img = np.full((canvas_h, canvas_w, 3), 28, dtype=np.uint8)

    mw = max(1, int(width or 1))
    mh = max(1, int(height or 1))
    event_list = [ev for ev in (events or []) if isinstance(ev, dict)]
    local_enabled = bool(st.get("show_local_map_preview", True)) and isinstance(focus_event, dict)

    crop_info: Dict[str, Any] | None = None
    map_left = 40
    map_top = 120
    step_x = max(12, (canvas_w - 80) // max(1, min(mw, 60)))
    step_y = max(12, (canvas_h - 140) // max(1, min(mh, 45)))

    if local_enabled:
        try:
            fx = int(focus_event.get("x") or 0)
            fy = int(focus_event.get("y") or 0)
            cols = int(st.get("local_map_cols") or 15)
            rows = int(st.get("local_map_rows") or 10)
            crop = _calc_local_map_crop(mw, mh, fx, fy, cols, rows)
            tile = max(12, min(48, (canvas_w - 72) // max(1, crop["cols"]), (canvas_h - 96) // max(1, crop["rows"])))
            map_w_px = int(crop["cols"] * tile)
            map_h_px = int(crop["rows"] * tile)
            map_left = int((canvas_w - map_w_px) // 2)
            map_top = int((canvas_h - map_h_px) // 2)
            step_x = step_y = int(tile)
            crop_info = {
                "enabled": True,
                "x0": int(crop["x0"]),
                "y0": int(crop["y0"]),
                "x1": int(crop["x1"]),
                "y1": int(crop["y1"]),
                "cols": int(crop["cols"]),
                "rows": int(crop["rows"]),
                "tile_size": int(tile),
                "origin_x": int(map_left),
                "origin_y": int(map_top),
                "focus_x": int(crop["focus_x"]),
                "focus_y": int(crop["focus_y"]),
                "focus_event_id": int(focus_event.get("id") or 0),
                "focus_event_name": str(focus_event.get("name") or ""),
            }
        except Exception:
            local_enabled = False
            crop_info = None

    if page_meta is not None:
        try:
            if crop_info:
                page_meta["preview_crop"] = dict(crop_info)
            else:
                page_meta.pop("preview_crop", None)
        except Exception:
            pass

    if local_enabled and crop_info:
        try:
            map_file_for_cache = str((page_meta or {}).get('map_file') or '').strip() if isinstance(page_meta, dict) else ''
            if map_file_for_cache and bool(st.get("show_tile_map_preview", True)) and not bool(st.get("debug_overlay")) and not bool(st.get("enable_tile_validation_dump", False)):
                placeholder_cache_path = _maker_map_placeholder_cache_path(path, map_file_for_cache, crop_info, st, mode="local")
                cached_img = None if force_preview_rebuild else _maker_read_map_placeholder_cache(placeholder_cache_path, canvas_w, canvas_h)
                if cached_img is not None:
                    ok, buf = cv2.imencode(".png", cached_img)
                    if ok:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        buf.tofile(str(path))
                        try:
                            if page_meta is not None:
                                page_meta["preview_render_deferred"] = False
                                page_meta["preview_cache_hit"] = True
                        except Exception:
                            pass
                        return
                placeholder_cache_should_write = bool(placeholder_cache_path is not None and not defer_tile_render)
        except Exception:
            placeholder_cache_path = None
            placeholder_cache_should_write = False
        x0 = int(crop_info["x0"])
        y0 = int(crop_info["y0"])
        cols = int(crop_info["cols"])
        rows = int(crop_info["rows"])
        tile = int(crop_info["tile_size"])
        map_w_px = cols * tile
        map_h_px = rows * tile

        cv2.rectangle(img, (map_left - 8, map_top - 8), (map_left + map_w_px + 8, map_top + map_h_px + 8), (18, 18, 20), -1)
        cv2.rectangle(img, (map_left, map_top), (map_left + map_w_px, map_top + map_h_px), (42, 42, 46), -1)
        tile_rendered = False
        tile_render_state = None
        map_ctx = None
        advanced_map = bool(st.get("show_advanced_map_preview", True))
        if (not defer_tile_render) and bool(st.get("show_tile_map_preview", True)) and isinstance(page_meta, dict):
            try:
                map_file = str(page_meta.get('map_file') or '').strip()
                if map_file:
                    map_ctx = _maker_load_local_map_tile_preview_context(path, map_file, st)
                    if isinstance(map_ctx, dict):
                        tile_render_state = _maker_render_local_map_scene(crop_info, map_ctx, advanced=advanced_map, tile_validation=bool(st.get("enable_tile_validation_dump", False)))
                        if isinstance(tile_render_state, dict) and tile_render_state.get('rendered_any') and tile_render_state.get('image') is not None:
                            scene_img = tile_render_state.get('image')
                            sh, sw = scene_img.shape[:2]
                            img[map_top:map_top+sh, map_left:map_left+sw] = scene_img[:, :, :3]
                            tile_rendered = True
            except Exception:
                tile_rendered = False
                tile_render_state = None
                map_ctx = None
        line_color = (66, 66, 72) if bool(st.get("show_map_grid")) else (52, 52, 58)
        if (not tile_rendered) or bool(st.get("show_map_grid")):
            for i in range(cols + 1):
                x = map_left + i * tile
                cv2.line(img, (x, map_top), (x, map_top + map_h_px), line_color, 1)
            for j in range(rows + 1):
                y = map_top + j * tile
                cv2.line(img, (map_left, y), (map_left + map_w_px, y), line_color, 1)

        # A small context label.  OpenCV cannot draw Korean reliably, so keep it
        # numeric/ASCII.  The UI overlays handle Korean dialogue separately.
        label_mode = 'tiles' if tile_rendered else 'grid'
        label = f"Map {int(map_id):03d}  x{x0}-{x0 + cols - 1} / y{y0}-{y0 + rows - 1}  {label_mode}  events:{len(event_list)}  text:{int(text_count or 0)}"
        _draw_text_safe(img, label[:110], (max(12, map_left), max(24, map_top - 18)), 0.52, (210, 218, 226), 1)

        # Mini-map: show where the cropped area sits in the whole map.
        try:
            mini_w, mini_h = 132, 92
            mini_x, mini_y = canvas_w - mini_w - 18, 18
            cv2.rectangle(img, (mini_x - 6, mini_y - 6), (mini_x + mini_w + 6, mini_y + mini_h + 6), (16, 16, 18), -1)
            cv2.rectangle(img, (mini_x, mini_y), (mini_x + mini_w, mini_y + mini_h), (48, 48, 54), 1)
            rx0 = int(mini_x + (x0 / max(1, mw)) * mini_w)
            ry0 = int(mini_y + (y0 / max(1, mh)) * mini_h)
            rx1 = int(mini_x + ((x0 + cols) / max(1, mw)) * mini_w)
            ry1 = int(mini_y + ((y0 + rows) / max(1, mh)) * mini_h)
            cv2.rectangle(img, (rx0, ry0), (max(rx0 + 2, rx1), max(ry0 + 2, ry1)), (90, 170, 240), 1)
            fx = int(crop_info["focus_x"])
            fy = int(crop_info["focus_y"])
            fmx = int(mini_x + ((fx + 0.5) / max(1, mw)) * mini_w)
            fmy = int(mini_y + ((fy + 0.5) / max(1, mh)) * mini_h)
            cv2.circle(img, (fmx, fmy), 3, (80, 220, 255), -1)
        except Exception:
            pass

        focus_id = int(crop_info.get("focus_event_id") or 0)
        if advanced_map and tile_rendered and isinstance(map_ctx, dict):
            try:
                _maker_draw_event_graphics(img, crop_info, map_ctx, focus_event_id=focus_id)
                if isinstance(tile_render_state, dict):
                    for sx, sy, star_tile in (tile_render_state.get('star_tiles') or []):
                        tx = map_left + int(sx)
                        ty = map_top + int(sy)
                        if star_tile is None:
                            continue
                        _maker_alpha_blit(img, star_tile if star_tile.shape[2] == 4 else cv2.cvtColor(star_tile, cv2.COLOR_BGR2BGRA), tx, ty)
            except Exception:
                pass
        for ev in event_list:
            try:
                ex = int(ev.get("x") or 0)
                ey = int(ev.get("y") or 0)
                eid = int(ev.get("id") or 0)
            except Exception:
                continue
            if ex < x0 or ex >= x0 + cols or ey < y0 or ey >= y0 + rows:
                continue
            px = int(map_left + (ex - x0 + 0.5) * tile)
            py = int(map_top + (ey - y0 + 0.5) * tile)
            is_focus = bool(focus_id and eid == focus_id) or (ex == int(crop_info.get("focus_x") or -999) and ey == int(crop_info.get("focus_y") or -999))
            if is_focus:
                cv2.circle(img, (px, py), max(12, tile // 3), (50, 185, 255), 2)
                cv2.circle(img, (px, py), max(5, tile // 8), (60, 80, 255), -1)
                cv2.circle(img, (px, py), max(3, tile // 12), (245, 245, 245), -1)
            else:
                cv2.circle(img, (px, py), max(4, tile // 9), (90, 150, 230), -1)
            label_ev = str(eid)
            _draw_text_safe(img, label_ev, (px + max(6, tile // 8), py + 5), 0.42, (230, 230, 230), 1)
            name = str(ev.get("name") or "").strip()
            if name and (bool(st.get("show_event_text_overlay")) or is_focus):
                # Keep names short because OpenCV text is only a debug/context label.
                ascii_name = name.encode("ascii", "ignore").decode("ascii", "ignore").strip()
                if ascii_name:
                    _draw_text_safe(img, ascii_name[:20], (px + max(6, tile // 8), py + 22), 0.36, (210, 210, 210), 1)
    else:
        # Full-map/game-map preview.  This is the normal map-opening interface:
        # before a text row is selected we still render a real map overview
        # instead of leaving the viewer as an empty black canvas.  MV deployed
        # projects commonly live under www/, so this path must go through the
        # same content-root resolver used by the selected-row local preview.
        full_crop_info = None
        full_tile_rendered = False
        full_tile_state = None
        full_map_ctx = None
        try:
            margin_x = 32
            margin_top = 34
            margin_bottom = 28
            avail_w = max(96, int(canvas_w) - margin_x * 2)
            avail_h = max(96, int(canvas_h) - margin_top - margin_bottom)
            # RPG Maker MV/MZ tiles are 48px.  For a whole-map overview, allow
            # downscaling so normal mode can show large maps at once.
            fit_tile = int(min(48, max(4, min(avail_w / max(1, mw), avail_h / max(1, mh)))))
            if fit_tile < 4:
                fit_tile = 4
            cols = min(mw, max(1, avail_w // max(1, fit_tile)))
            rows = min(mh, max(1, avail_h // max(1, fit_tile)))
            x0 = 0
            y0 = 0
            map_w_px = int(cols * fit_tile)
            map_h_px = int(rows * fit_tile)
            map_left = int((canvas_w - map_w_px) // 2)
            map_top = int((canvas_h - map_h_px) // 2)
            full_crop_info = {
                "enabled": True,
                "mode": "full_map",
                "x0": int(x0),
                "y0": int(y0),
                "x1": int(x0 + cols),
                "y1": int(y0 + rows),
                "cols": int(cols),
                "rows": int(rows),
                "tile_size": int(fit_tile),
                "origin_x": int(map_left),
                "origin_y": int(map_top),
                "focus_x": -1,
                "focus_y": -1,
                "focus_event_id": 0,
                "focus_event_name": "",
            }
            if page_meta is not None:
                try:
                    page_meta["preview_crop"] = dict(full_crop_info)
                except Exception:
                    pass
        except Exception:
            full_crop_info = None

        if full_crop_info:
            try:
                map_file_for_cache = str((page_meta or {}).get('map_file') or '').strip() if isinstance(page_meta, dict) else ''
                if map_file_for_cache and bool(st.get("show_tile_map_preview", True)) and not bool(st.get("debug_overlay")) and not bool(st.get("enable_tile_validation_dump", False)):
                    placeholder_cache_path = _maker_map_placeholder_cache_path(path, map_file_for_cache, full_crop_info, st, mode="full")
                    cached_img = None if force_preview_rebuild else _maker_read_map_placeholder_cache(placeholder_cache_path, canvas_w, canvas_h)
                    if cached_img is not None:
                        ok, buf = cv2.imencode(".png", cached_img)
                        if ok:
                            path.parent.mkdir(parents=True, exist_ok=True)
                            buf.tofile(str(path))
                            try:
                                if page_meta is not None:
                                    page_meta["preview_render_deferred"] = False
                                    page_meta["preview_cache_hit"] = True
                            except Exception:
                                pass
                            return
                    placeholder_cache_should_write = bool(placeholder_cache_path is not None and not defer_tile_render)
            except Exception:
                placeholder_cache_path = None
                placeholder_cache_should_write = False
            try:
                x0 = int(full_crop_info["x0"])
                y0 = int(full_crop_info["y0"])
                cols = int(full_crop_info["cols"])
                rows = int(full_crop_info["rows"])
                tile = int(full_crop_info["tile_size"])
                map_left = int(full_crop_info["origin_x"])
                map_top = int(full_crop_info["origin_y"])
                map_w_px = int(cols * tile)
                map_h_px = int(rows * tile)
                cv2.rectangle(img, (map_left - 8, map_top - 8), (map_left + map_w_px + 8, map_top + map_h_px + 8), (18, 18, 20), -1)
                cv2.rectangle(img, (map_left, map_top), (map_left + map_w_px, map_top + map_h_px), (42, 42, 46), -1)

                if (not defer_tile_render) and bool(st.get("show_tile_map_preview", True)) and isinstance(page_meta, dict):
                    try:
                        map_file = str(page_meta.get('map_file') or '').strip()
                        if map_file:
                            full_map_ctx = _maker_load_local_map_tile_preview_context(path, map_file, st)
                            if isinstance(full_map_ctx, dict):
                                full_tile_state = _maker_render_local_map_scene(full_crop_info, full_map_ctx, advanced=bool(st.get("show_advanced_map_preview", True)), tile_validation=bool(st.get("enable_tile_validation_dump", False)))
                                if isinstance(full_tile_state, dict) and full_tile_state.get('rendered_any') and full_tile_state.get('image') is not None:
                                    scene_img = full_tile_state.get('image')
                                    sh, sw = scene_img.shape[:2]
                                    img[map_top:map_top+sh, map_left:map_left+sw] = scene_img[:, :, :3]
                                    full_tile_rendered = True
                    except Exception:
                        full_tile_rendered = False
                        full_tile_state = None
                        full_map_ctx = None

                line_color = (66, 66, 72) if bool(st.get("show_map_grid")) else (52, 52, 58)
                if (not full_tile_rendered) or bool(st.get("show_map_grid")):
                    for i in range(cols + 1):
                        x = map_left + i * tile
                        cv2.line(img, (x, map_top), (x, map_top + map_h_px), line_color, 1)
                    for j in range(rows + 1):
                        y = map_top + j * tile
                        cv2.line(img, (map_left, y), (map_left + map_w_px, y), line_color, 1)

                label_mode = 'tiles' if full_tile_rendered else 'grid'
                label = f"Map {int(map_id):03d}  {mw}x{mh}  {label_mode}  events:{len(event_list)}  text:{int(text_count or 0)}"
                _draw_text_safe(img, label[:110], (max(12, map_left), max(24, map_top - 18)), 0.52, (210, 218, 226), 1)

                if bool(st.get("show_advanced_map_preview", True)) and full_tile_rendered and isinstance(full_map_ctx, dict):
                    try:
                        _maker_draw_event_graphics(img, full_crop_info, full_map_ctx, focus_event_id=0)
                        if isinstance(full_tile_state, dict):
                            for sx, sy, star_tile in (full_tile_state.get('star_tiles') or []):
                                tx = map_left + int(sx)
                                ty = map_top + int(sy)
                                if star_tile is None:
                                    continue
                                _maker_alpha_blit(img, star_tile if star_tile.shape[2] == 4 else cv2.cvtColor(star_tile, cv2.COLOR_BGR2BGRA), tx, ty)
                    except Exception:
                        pass

                # Event markers stay visible even when the map has no tile assets.
                # This prevents MV imports with missing/external img folders from
                # appearing as a dead black screen.
                for ev in event_list:
                    try:
                        ex = int(ev.get("x") or 0)
                        ey = int(ev.get("y") or 0)
                        eid = int(ev.get("id") or 0)
                    except Exception:
                        continue
                    if ex < x0 or ex >= x0 + cols or ey < y0 or ey >= y0 + rows:
                        continue
                    px = int(map_left + (ex - x0 + 0.5) * tile)
                    py = int(map_top + (ey - y0 + 0.5) * tile)
                    cv2.circle(img, (px, py), max(4, tile // 5), (90, 150, 230), -1)
                    if tile >= 12:
                        _draw_text_safe(img, str(eid), (px + max(5, tile // 8), py + 5), 0.38, (230, 230, 230), 1)
                    if bool(st.get("show_event_text_overlay")):
                        name = str(ev.get("name") or "").strip()
                        if name:
                            ascii_name = name.encode("ascii", "ignore").decode("ascii", "ignore").strip()
                            if ascii_name:
                                _draw_text_safe(img, ascii_name[:24], (px + max(5, tile // 8), py + 20), 0.36, (210, 210, 210), 1)
            except Exception:
                pass

        # Last-resort legacy overlay.  It should rarely be used now, but keeps
        # old projects/debug settings readable if map geometry failed.
        if full_crop_info is None:
            if bool(st.get("show_map_grid")) or bool(st.get("debug_overlay")):
                for x in range(0, canvas_w, step_x):
                    cv2.line(img, (x, 0), (x, canvas_h), (54, 54, 54), 1)
                for y in range(0, canvas_h, step_y):
                    cv2.line(img, (0, y), (canvas_w, y), (54, 54, 54), 1)

            if bool(st.get("show_event_positions")) or bool(st.get("debug_overlay")):
                for ev in event_list:
                    try:
                        ex = int(ev.get("x") or 0)
                        ey = int(ev.get("y") or 0)
                        eid = int(ev.get("id") or 0)
                    except Exception:
                        continue
                    px = int(40 + (ex + 0.5) * step_x)
                    py = int(120 + (ey + 0.5) * step_y)
                    if px >= canvas_w - 30 or py >= canvas_h - 30:
                        continue
                    cv2.circle(img, (px, py), 8, (90, 150, 230), -1)
                    _draw_text_safe(img, str(eid), (px + 10, py + 5), 0.42, (220, 220, 220), 1)
                    if bool(st.get("show_event_text_overlay")):
                        name = str(ev.get("name") or "").strip()
                        if name:
                            ascii_name = name.encode("ascii", "ignore").decode("ascii", "ignore").strip()
                            if ascii_name:
                                _draw_text_safe(img, ascii_name[:24], (px + 10, py + 24), 0.42, (210, 210, 210), 1)

    if bool(st.get("debug_overlay")):
        cv2.rectangle(img, (20, 18), (canvas_w - 20, 94), (52, 52, 52), -1)
        cv2.rectangle(img, (20, 18), (canvas_w - 20, 94), (98, 98, 98), 2)
        title = f"{engine_label} Map {map_id:03d} / {map_name}"
        _draw_text_safe(img, title[:75], (40, 50), 0.8, (235, 235, 235), 2)
        _draw_text_safe(img, f"events: {len(event_list)}   text units: {text_count}", (40, 78), 0.62, (190, 210, 230), 1)
        font_line = f"preview font: {st.get('font_family')} / {st.get('font_size')}px / W{st.get('char_width')}% H{st.get('char_height')}% / {canvas_w}x{canvas_h}"
        _draw_text_safe(img, font_line[:100], (40, min(canvas_h - 24, 108)), 0.52, (220, 205, 185), 1)

    try:
        if bool(placeholder_cache_should_write) and placeholder_cache_path is not None and not bool(st.get("debug_overlay")) and not bool(st.get("enable_tile_validation_dump", False)):
            _maker_write_map_placeholder_cache(placeholder_cache_path, img)
            if page_meta is not None:
                try:
                    page_meta["preview_render_deferred"] = False
                    page_meta["preview_cache_hit"] = False
                    page_meta["preview_cache_path"] = str(placeholder_cache_path)
                except Exception:
                    pass
    except Exception:
        pass

    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise MakerProjectError("맵 페이지 이미지를 만들지 못했습니다.")
    buf.tofile(str(path))

def _ysb_text_item_from_unit(unit: MakerTextUnit, idx: int, *, page_w: int = 960, preview_settings: Dict[str, Any] | None = None, engine: str = "") -> Dict[str, Any]:
    row_h = 84
    top = 116 + (idx % 10) * row_h
    left = 48 + (idx // 10) * 300
    if left > page_w - 260:
        left = 48
    label = unit.text
    st = normalize_maker_preview_settings(preview_settings)
    speaker_display = str(unit.speaker_plain or strip_maker_control_codes(unit.speaker or "") or "Unknown").strip() or "Unknown"
    speaker_raw_visible = str(unit.speaker_raw_visible or "")
    if not speaker_raw_visible and _maker_speaker_has_visible_codes(unit.speaker):
        speaker_raw_visible = str(unit.speaker or "")
    font_size = int(st["choice_font_size"] if str(unit.text_type or "").startswith("choice") else st["font_size"])
    item = {
        "id": idx + 1,
        "text": label,
        "translated_text": "",
        # Normal table speaker is always plain; inline speaker control codes live
        # in maker_text_unit.speaker_raw_visible and the speaker-translation UI.
        "maker_speaker": speaker_display,
        "maker_speaker_plain": speaker_display,
        "maker_speaker_source": unit.speaker_source or "unknown",
        "maker_speaker_confidence": float(unit.speaker_confidence or 0.0),
        "rect": [int(left), int(top), 260, 64],
        "use_inpaint": False,
        "font_family": st["font_family"],
        "font_size": font_size,
        "stroke_width": int(st["outline_width"]),
        "text_color": st["text_color"],
        "stroke_color": st["outline_color"],
        "line_spacing": int(st["line_spacing"]),
        "letter_spacing": int(st["letter_spacing"]),
        "char_width": int(st["char_width"]),
        "char_height": int(st["char_height"]),
        "align": "center",
        "x_off": 0,
        "y_off": 0,
        "manual_text_rect": True,
        "text_anchor_mode": "text",
        "force_show": False,
        "maker_text_unit": {
            "map_id": unit.map_id,
            "map_file": unit.map_file,
            "map_name": unit.map_name,
            "event_id": unit.event_id,
            "event_name": unit.event_name,
            "event_x": unit.event_x,
            "event_y": unit.event_y,
            "page_index": unit.page_index,
            "command_index": unit.command_index,
            "code": unit.code,
            "text_type": unit.text_type,
            "speaker": speaker_display,
            "speaker_plain": speaker_display,
            "inline_speaker": bool(unit.inline_speaker),
            "speaker_raw_visible": speaker_raw_visible,
            "body_prefix_codes": unit.body_prefix_codes or "",
            "body_line_reserved": bool(unit.body_line_reserved),
            "face_name": unit.face_name,
            "face_index": int(unit.face_index or 0),
            "speaker_source": unit.speaker_source or "unknown",
            "speaker_confidence": float(unit.speaker_confidence or 0.0),
            "source_kind": unit.source_kind or "map",
            "source_file": unit.source_file or unit.map_file,
            "db_kind": unit.db_kind or "",
            "db_id": unit.db_id,
            "db_field": unit.db_field or "",
            "db_path_keys": list(unit.db_path_keys or []),
            "plugin_name": unit.plugin_name or "",
            "plugin_kind": unit.plugin_kind or "",
            "plugin_root_path": list(unit.plugin_root_path or []),
            "plugin_access_steps": [dict(x) for x in (unit.plugin_access_steps or []) if isinstance(x, dict)],
            "plugin_note_tag": unit.plugin_note_tag or "",
            "plugin_note_occurrence": int(unit.plugin_note_occurrence or 0),
            "json_path": unit.json_path,
            "preview_payload": {
                "engine": engine or "",
                "map_id": unit.map_id,
                "map_file": unit.map_file,
                "map_name": unit.map_name,
                "event_id": unit.event_id,
                "event_name": unit.event_name,
                "event_x": unit.event_x,
                "event_y": unit.event_y,
                "page_index": unit.page_index,
                "command_index": unit.command_index,
                "command_code": unit.code,
                "text_type": unit.text_type,
                "source_kind": unit.source_kind or "map",
                "source_file": unit.source_file or unit.map_file,
                "speaker_plain": speaker_display,
                "speaker_raw_with_codes": speaker_raw_visible,
                "body_raw_with_codes": unit.text,
                "body_plain": strip_maker_control_codes(unit.text or ""),
                "inline_speaker": bool(unit.inline_speaker),
                "body_prefix_codes": unit.body_prefix_codes or "",
                "body_line_reserved": bool(unit.body_line_reserved),
            },
        },
    }
    apply_maker_preview_settings_to_item(item, st)
    return item



MAKER_MAP_TEXT_SPLIT_LIMIT = 300

def _maker_unit_event_key(unit: MakerTextUnit) -> tuple:
    try:
        event_id = int(unit.event_id or 0)
    except Exception:
        event_id = 0
    try:
        page_index = int(unit.page_index or 0)
    except Exception:
        page_index = 0
    return (event_id, page_index)

def _split_maker_map_units_by_event(units: List[MakerTextUnit], *, limit: int = MAKER_MAP_TEXT_SPLIT_LIMIT) -> List[Dict[str, Any]]:
    """Split a large map text list into editor-only chunks.

    The RPG Maker MapXXX.json stays physically intact.  Only the YSB editor
    page/table is split so very large maps do not force a 1000+ row QTableWidget
    and preview sync loop.  The normal boundary is the RPG Maker event/page,
    because event commands, choices and picture state are naturally grouped there.
    If a single event itself exceeds the limit, that one event is chunked as a
    safety fallback rather than allowing one huge editor page.
    """
    try:
        limit = max(1, int(limit or MAKER_MAP_TEXT_SPLIT_LIMIT))
    except Exception:
        limit = MAKER_MAP_TEXT_SPLIT_LIMIT
    source = list(units or [])
    if len(source) <= limit:
        return [{
            "split_index": 1,
            "split_total": 1,
            "units": source,
            "event_ids": sorted({int(u.event_id or 0) for u in source if getattr(u, "event_id", None) is not None}),
            "split_within_event": False,
        }]

    groups: List[List[MakerTextUnit]] = []
    current_group: List[MakerTextUnit] = []
    current_key = None
    for unit in source:
        key = _maker_unit_event_key(unit)
        if current_group and key != current_key:
            groups.append(current_group)
            current_group = []
        current_key = key
        current_group.append(unit)
    if current_group:
        groups.append(current_group)

    chunks: List[Dict[str, Any]] = []
    current: List[MakerTextUnit] = []
    current_split_within = False

    def flush() -> None:
        nonlocal current, current_split_within
        if not current:
            return
        chunks.append({
            "split_index": len(chunks) + 1,
            "split_total": 0,
            "units": current,
            "event_ids": sorted({int(u.event_id or 0) for u in current if getattr(u, "event_id", None) is not None}),
            "split_within_event": bool(current_split_within),
        })
        current = []
        current_split_within = False

    for group in groups:
        if not group:
            continue
        if len(group) > limit:
            flush()
            for start in range(0, len(group), limit):
                part = group[start:start + limit]
                chunks.append({
                    "split_index": len(chunks) + 1,
                    "split_total": 0,
                    "units": part,
                    "event_ids": sorted({int(u.event_id or 0) for u in part if getattr(u, "event_id", None) is not None}),
                    "split_within_event": True,
                })
            continue
        if current and len(current) + len(group) > limit:
            flush()
        current.extend(group)
    flush()

    total = len(chunks) or 1
    for chunk in chunks:
        chunk["split_total"] = total
    return chunks or [{
        "split_index": 1,
        "split_total": 1,
        "units": source,
        "event_ids": sorted({int(u.event_id or 0) for u in source if getattr(u, "event_id", None) is not None}),
        "split_within_event": False,
    }]

def build_maker_pages(project_dir: str | os.PathLike[str], game_clone_dir: str | os.PathLike[str], engine_info: MakerEngineInfo | Dict[str, Any] | None = None, progress_callback=None) -> Tuple[List[str], Dict[int, dict], Dict[str, Any]]:
    project_dir = Path(project_dir)
    layout = ensure_maker_project_layout(project_dir)
    images_dir = project_dir / "images"
    meta_dir = project_dir / MAKER_META_DIR
    images_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)
    _emit_maker_progress(progress_callback, 0, 0, "엔진과 표시 환경을 확인하는 중...")

    if engine_info is None:
        engine_info = detect_maker_engine(game_clone_dir)
    if isinstance(engine_info, dict):
        engine_dict = dict(engine_info)
    else:
        engine_dict = engine_info.to_dict()

    runtime_profile = build_maker_runtime_profile(project_dir, game_clone_dir, engine_info)
    preview_settings = maker_preview_settings_from_runtime_profile(runtime_profile, load_maker_preview_settings(project_dir))
    _emit_maker_progress(progress_callback, 0, 0, "배우/화자 힌트를 읽는 중...")
    actor_lookup = load_maker_actor_lookup(game_clone_dir, engine_info)

    paths: List[str] = []
    data: Dict[int, dict] = {}
    summary = {
        "source_type": "rpg_maker_mv_mz",
        "layout": layout,
        "game_clone_dir": MAKER_CLONE_DIR,
        "maker_meta_dir": MAKER_META_DIR,
        "maker_backup_dir": MAKER_BACKUP_DIR,
        "maker_original_json_backup_dir": f"{MAKER_BACKUP_DIR}/{MAKER_ORIGINAL_JSON_BACKUP_DIR}",
        "maker_diff_dir": MAKER_DIFF_DIR,
        "engine": engine_dict,
        "maker_preview_settings": dict(preview_settings),
        "maker_runtime_profile": dict(runtime_profile),
        "speaker_inference": {
            "version": 1,
            "actor_count": len((actor_lookup or {}).get("by_id") or {}),
            "source_counts": {},
            "speaker_counts": {},
        },
        "maps": [],
        "common_events": [],
        "database_pages": [],
        "plugin_pages": [],
        "virtual_pages": [],
        "total_text_units": 0,
    }

    try:
        _map_data_dir = _data_dir_from_engine_info(game_clone_dir, engine_info)
        _map_total = len([p for p in _map_data_dir.glob("Map*.json") if re.fullmatch(r"Map(\d{3,})\.json", p.name)])
    except Exception:
        _map_total = 0
    _emit_maker_progress(progress_callback, 0, max(_map_total, 1), f"맵 목록을 분석하는 중... 0/{max(_map_total, 1)}")

    for map_pos, (map_id, map_name, map_path, map_data) in enumerate(iter_existing_maps(game_clone_dir, engine_info), start=1):
        units = extract_map_text_units(map_id, map_name, map_path, map_data, actor_lookup=actor_lookup)
        chunks = _split_maker_map_units_by_event(units, limit=MAKER_MAP_TEXT_SPLIT_LIMIT)
        split_total = max(1, len(chunks))
        split_note = f" / 분할 {split_total}개" if split_total > 1 else ""
        _emit_maker_progress(progress_callback, map_pos, max(_map_total, map_pos, 1), f"맵 대사 추출 중... {map_pos}/{max(_map_total, map_pos, 1)}\n{map_path.name} / 텍스트 {len(units)}개{split_note}")
        events = [e for e in (map_data.get("events") or []) if isinstance(e, dict)] if isinstance(map_data, dict) else []
        try:
            mw = int(map_data.get("width") or 17)
            mh = int(map_data.get("height") or 13)
        except Exception:
            mw, mh = 17, 13
        safe_name = _safe_map_name(map_name, f"Map{map_id:03d}")

        for chunk in chunks:
            chunk_units = list(chunk.get("units") or [])
            split_index = int(chunk.get("split_index") or 1)
            split_total = int(chunk.get("split_total") or len(chunks) or 1)
            page_idx = len(paths)
            suffix = f"-{split_index}" if split_total > 1 else ""
            image_name = f"Map{map_id:03d}{suffix}_{safe_name}.png"
            image_path = images_dir / image_name
            display_map_name = f"{map_name}-{split_index}" if split_total > 1 else map_name
            maker_page_meta = {
                "engine": engine_dict.get("engine"),
                "engine_label": engine_dict.get("engine_label"),
                "map_id": map_id,
                "map_name": map_name,
                "display_map_name": display_map_name,
                "map_file": map_path.name,
                "width": mw,
                "height": mh,
                "event_count": len(events),
                "text_unit_count": len(chunk_units),
                "physical_map_text_unit_count": len(units),
                "editor_split_enabled": bool(split_total > 1),
                "editor_split_index": split_index,
                "editor_split_total": split_total,
                "editor_split_limit": MAKER_MAP_TEXT_SPLIT_LIMIT,
                "editor_split_event_ids": list(chunk.get("event_ids") or []),
                "editor_split_within_event": bool(chunk.get("split_within_event", False)),
                "editor_split_canonical_image": f"Map{map_id:03d}-1_{safe_name}.png" if split_total > 1 else image_name,
                "events": [
                    {
                        "id": int(ev.get("id") or 0),
                        "name": _event_name(ev),
                        "x": int(ev.get("x") or 0),
                        "y": int(ev.get("y") or 0),
                    }
                    for ev in events
                    if isinstance(ev, dict)
                ],
            }
            initial_preview_settings = dict(preview_settings)
            initial_preview_settings["defer_tile_render"] = True
            maker_page_meta["preview_render_deferred"] = True
            _placeholder_image(image_path, map_id=map_id, map_name=display_map_name, width=mw, height=mh, events=events, text_count=len(chunk_units), engine_label=str(engine_dict.get("engine_label") or "RPG Maker"), preview_settings=initial_preview_settings, page_meta=maker_page_meta)
            text_items = [_ysb_text_item_from_unit(unit, i, preview_settings=preview_settings, engine=str(engine_dict.get("engine") or "")) for i, unit in enumerate(chunk_units)]
            try:
                source_counts = summary["speaker_inference"].setdefault("source_counts", {})
                speaker_counts = summary["speaker_inference"].setdefault("speaker_counts", {})
                for unit in chunk_units:
                    src_key = str(unit.speaker_source or "unknown")
                    source_counts[src_key] = int(source_counts.get(src_key, 0) or 0) + 1
                    sp_key = str(unit.speaker or "Unknown")
                    speaker_counts[sp_key] = int(speaker_counts.get(sp_key, 0) or 0) + 1
            except Exception:
                pass
            paths.append(str(image_path))
            data[page_idx] = {
                "ori": None,
                "data": text_items,
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
                "original_name": image_name,
                "ocr_analysis_regions": [],
                "maker_preview_settings": dict(preview_settings),
                "maker_runtime_profile": dict(runtime_profile),
                "maker_page": dict(maker_page_meta),
            }
            summary["maps"].append({
                "page_index": page_idx,
                "map_id": map_id,
                "map_name": map_name,
                "map_file": map_path.name,
                "text_unit_count": len(chunk_units),
                "physical_map_text_unit_count": len(units),
                "event_count": len(events),
                "editor_split_enabled": bool(split_total > 1),
                "editor_split_index": split_index,
                "editor_split_total": split_total,
                "editor_split_limit": MAKER_MAP_TEXT_SPLIT_LIMIT,
                "editor_split_event_ids": list(chunk.get("event_ids") or []),
                "editor_split_within_event": bool(chunk.get("split_within_event", False)),
            })
            summary["total_text_units"] += len(chunk_units)

    # Virtual pages: CommonEvents and Database/System text.  These do not have
    # a real map canvas, but they should still behave like Maker pages in the
    # right-side text table and AI translation/write-back pipeline.
    try:
        data_dir = _data_dir_from_engine_info(game_clone_dir, engine_info)
    except Exception:
        data_dir = None

    if isinstance(data_dir, Path) and data_dir.is_dir():
        _emit_maker_progress(progress_callback, 0, 1, "공통 이벤트를 확인하는 중...")
        common_path = data_dir / "CommonEvents.json"
        if common_path.is_file():
            try:
                common_payload = _read_json(common_path)
                common_units = extract_common_event_text_units(common_path, common_payload, actor_lookup=actor_lookup)
            except Exception:
                common_payload = []
                common_units = []
            if common_units:
                # CommonEvents.json is one physical RPG Maker file, but each
                # Common Event is a different scene/situation for translation.
                # Split the editor pages by CE id while keeping source_file/json_path
                # pointed at CommonEvents.json so write-back still updates the single
                # original file safely.
                ce_lookup: Dict[int, Dict[str, Any]] = {}
                if isinstance(common_payload, list):
                    for ce_idx, ce in enumerate(common_payload):
                        if not isinstance(ce, dict):
                            continue
                        try:
                            ce_id = int(ce.get("id") or ce_idx)
                        except Exception:
                            ce_id = ce_idx
                        if ce_id <= 0:
                            continue
                        ce_lookup[ce_id] = ce

                grouped_common_units: Dict[int, List[MakerTextUnit]] = {}
                for unit in common_units:
                    try:
                        ce_id = int(unit.event_id or 0)
                    except Exception:
                        ce_id = 0
                    if ce_id <= 0:
                        ce_id = 999999
                    grouped_common_units.setdefault(ce_id, []).append(unit)

                _common_keys_sorted = sorted(grouped_common_units.keys())
                for _ce_pos, ce_id in enumerate(_common_keys_sorted, start=1):
                    units_for_ce = grouped_common_units.get(ce_id) or []
                    _emit_maker_progress(progress_callback, _ce_pos, max(len(_common_keys_sorted), 1), f"공통 이벤트 페이지 구성 중... {_ce_pos}/{max(len(_common_keys_sorted), 1)}")
                    if not units_for_ce:
                        continue
                    ce_obj = ce_lookup.get(ce_id) or {}
                    ce_name = _common_event_name(ce_obj) or (units_for_ce[0].event_name if units_for_ce else "") or f"CommonEvent{ce_id:03d}"
                    page_title = f"CE{ce_id:03d}_{ce_name}"
                    safe_name = _safe_map_name(page_title, f"CE{ce_id:03d}")
                    image_name = f"{safe_name}.png"
                    image_path = images_dir / image_name
                    _virtual_page_placeholder_image(
                        image_path,
                        title=page_title,
                        subtitle="data/CommonEvents.json",
                        text_count=len(units_for_ce),
                        engine_label=str(engine_dict.get("engine_label") or "RPG Maker"),
                        preview_settings=preview_settings,
                    )
                    text_items = [_ysb_text_item_from_unit(unit, i, preview_settings=preview_settings, engine=str(engine_dict.get("engine") or "")) for i, unit in enumerate(units_for_ce)]
                    paths.append(str(image_path))
                    page_idx = len(paths) - 1
                    data[page_idx] = {
                        "ori": None,
                        "data": text_items,
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
                        "original_name": image_name,
                        "ocr_analysis_regions": [],
                        "maker_preview_settings": dict(preview_settings),
                        "maker_runtime_profile": dict(runtime_profile),
                        "maker_page": {
                            "engine": engine_dict.get("engine"),
                            "engine_label": engine_dict.get("engine_label"),
                            "page_type": "common_event",
                            "page_title": page_title,
                            "source_file": "CommonEvents.json",
                            "common_event_id": ce_id,
                            "common_event_name": ce_name,
                            "map_id": 0,
                            "map_name": page_title,
                            "map_file": "CommonEvents.json",
                            "width": 20,
                            "height": 11,
                            "event_count": 1,
                            "text_unit_count": len(units_for_ce),
                            "events": [],
                        },
                    }
                    summary["common_events"].append({
                        "page_index": page_idx,
                        "source_file": "CommonEvents.json",
                        "common_event_id": ce_id,
                        "common_event_name": ce_name,
                        "page_title": page_title,
                        "text_unit_count": len(units_for_ce),
                    })
                    summary["virtual_pages"].append({
                        "page_index": page_idx,
                        "page_type": "common_event",
                        "source_file": "CommonEvents.json",
                        "common_event_id": ce_id,
                        "common_event_name": ce_name,
                    })
                    summary["total_text_units"] += len(units_for_ce)
                    try:
                        source_counts = summary["speaker_inference"].setdefault("source_counts", {})
                        speaker_counts = summary["speaker_inference"].setdefault("speaker_counts", {})
                        for unit in units_for_ce:
                            src_key = str(unit.speaker_source or "unknown")
                            source_counts[src_key] = int(source_counts.get(src_key, 0) or 0) + 1
                            sp_key = str(unit.speaker or "Unknown")
                            speaker_counts[sp_key] = int(speaker_counts.get(sp_key, 0) or 0) + 1
                    except Exception:
                        pass

        try:
            db_pages = extract_database_text_units(data_dir)
        except Exception:
            db_pages = {}
        _db_items = list(db_pages.items()) if isinstance(db_pages, dict) else []
        for _db_pos, (file_name, units) in enumerate(_db_items, start=1):
            if not units:
                continue
            _emit_maker_progress(progress_callback, _db_pos, max(len(_db_items), 1), f"데이터베이스 텍스트 페이지 구성 중... {_db_pos}/{max(len(_db_items), 1)}\n{file_name} / 텍스트 {len(units)}개")
            page_idx = len(paths)
            page_title = _database_label_from_filename(file_name)
            safe_name = _safe_map_name(page_title, file_name.replace(".json", ""))
            image_name = f"{safe_name}.png"
            image_path = images_dir / image_name
            _virtual_page_placeholder_image(
                image_path,
                title=page_title,
                subtitle=f"data/{file_name}",
                text_count=len(units),
                engine_label=str(engine_dict.get("engine_label") or "RPG Maker"),
                preview_settings=preview_settings,
            )
            text_items = [_ysb_text_item_from_unit(unit, i, preview_settings=preview_settings, engine=str(engine_dict.get("engine") or "")) for i, unit in enumerate(units)]
            paths.append(str(image_path))
            data[page_idx] = {
                "ori": None,
                "data": text_items,
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
                "original_name": image_name,
                "ocr_analysis_regions": [],
                "maker_preview_settings": dict(preview_settings),
                "maker_runtime_profile": dict(runtime_profile),
                "maker_page": {
                    "engine": engine_dict.get("engine"),
                    "engine_label": engine_dict.get("engine_label"),
                    "page_type": "database",
                    "page_title": page_title,
                    "source_file": file_name,
                    "map_id": 0,
                    "map_name": page_title,
                    "map_file": file_name,
                    "width": 20,
                    "height": 11,
                    "event_count": 0,
                    "text_unit_count": len(units),
                    "events": [],
                },
            }
            summary["database_pages"].append({
                "page_index": page_idx,
                "source_file": file_name,
                "page_title": page_title,
                "text_unit_count": len(units),
            })
            summary["virtual_pages"].append({"page_index": page_idx, "page_type": "database", "source_file": file_name})
            summary["total_text_units"] += len(units)
            try:
                source_counts = summary["speaker_inference"].setdefault("source_counts", {})
                speaker_counts = summary["speaker_inference"].setdefault("speaker_counts", {})
                for unit in units:
                    src_key = str(unit.speaker_source or "unknown")
                    source_counts[src_key] = int(source_counts.get(src_key, 0) or 0) + 1
                    sp_key = str(unit.speaker or "Unknown")
                    speaker_counts[sp_key] = int(speaker_counts.get(sp_key, 0) or 0) + 1
            except Exception:
                pass

        # Plugin translation pages are a third editor layer.  They deliberately
        # stay separate from map dialogue and database rows because their source
        # containers and write-back rules are different.
        try:
            plugin_pages = extract_plugin_text_units(Path(game_clone_dir), Path(data_dir), engine_info)
        except Exception:
            plugin_pages = {}
        _plugin_items = list(plugin_pages.items()) if isinstance(plugin_pages, dict) else []
        for _plugin_pos, (plugin_key, units) in enumerate(_plugin_items, start=1):
            if not units:
                continue
            first = units[0]
            plugin_name = str(first.plugin_name or first.db_kind or plugin_key).strip()
            if str(plugin_key).startswith("plugin:"):
                page_title = f"Plugin - {plugin_name}"
            elif str(plugin_key).startswith("event:"):
                page_title = f"Plugin Events - {Path(str(first.source_file or plugin_key)).stem}"
            elif str(plugin_key).startswith("note:"):
                page_title = f"Plugin Notes - {Path(str(first.source_file or plugin_key)).stem}"
            else:
                page_title = f"Plugin - {plugin_name or plugin_key}"
            _emit_maker_progress(
                progress_callback, _plugin_pos, max(len(_plugin_items), 1),
                f"플러그인 텍스트 페이지 구성 중... {_plugin_pos}/{max(len(_plugin_items), 1)}\n{page_title} / 텍스트 {len(units)}개",
            )
            page_idx = len(paths)
            safe_name = _safe_map_name(page_title, f"Plugin{_plugin_pos:03d}")
            image_name = f"{safe_name}.png"
            image_path = images_dir / image_name
            _virtual_page_placeholder_image(
                image_path, title=page_title,
                subtitle=str(first.source_file or "plugin data"),
                text_count=len(units),
                engine_label=str(engine_dict.get("engine_label") or "RPG Maker"),
                preview_settings=preview_settings,
            )
            text_items = [_ysb_text_item_from_unit(unit, i, preview_settings=preview_settings, engine=str(engine_dict.get("engine") or "")) for i, unit in enumerate(units)]
            paths.append(str(image_path))
            data[page_idx] = {
                "ori": None, "data": text_items,
                "mask_merge": None, "mask_inpaint": None,
                "mask_merge_off": None, "mask_inpaint_off": None,
                "mask_merge_path": None, "mask_inpaint_path": None,
                "mask_merge_off_path": None, "mask_inpaint_off_path": None,
                "mask_toggle_enabled": False, "use_inpainted_as_source": False,
                "bg_clean": None, "working_source": None,
                "final_paint": None, "final_paint_above": None,
                "original_name": image_name, "ocr_analysis_regions": [],
                "maker_preview_settings": dict(preview_settings),
                "maker_runtime_profile": dict(runtime_profile),
                "maker_page": {
                    "engine": engine_dict.get("engine"),
                    "engine_label": engine_dict.get("engine_label"),
                    "page_type": "plugin",
                    "page_title": page_title,
                    "source_file": str(first.source_file or ""),
                    "plugin_key": str(plugin_key),
                    "plugin_name": plugin_name,
                    "map_id": 0, "map_name": page_title,
                    "map_file": str(first.source_file or ""),
                    "width": 20, "height": 11,
                    "event_count": 0, "text_unit_count": len(units),
                    "events": [],
                },
            }
            summary["plugin_pages"].append({
                "page_index": page_idx, "plugin_key": str(plugin_key),
                "plugin_name": plugin_name, "source_file": str(first.source_file or ""),
                "page_title": page_title, "text_unit_count": len(units),
            })
            summary["virtual_pages"].append({"page_index": page_idx, "page_type": "plugin", "source_file": str(first.source_file or "")})
            summary["total_text_units"] += len(units)

    if not paths:
        raise MakerProjectError("MapXXX.json을 찾지 못했습니다. MV/MZ 프로젝트의 data 폴더를 확인해 주세요.")

    _emit_maker_progress(progress_callback, 1, 1, "가져오기 요약과 표시 설정을 저장하는 중...")
    try:
        save_maker_preview_settings(project_dir, preview_settings)
    except Exception:
        pass
    meta_path = meta_dir / MAKER_IMPORT_SUMMARY_FILE
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    try:
        speaker_path = meta_dir / MAKER_SPEAKER_SUMMARY_FILE
        with speaker_path.open("w", encoding="utf-8") as f:
            json.dump(summary.get("speaker_inference") or {}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        database_path = meta_dir / MAKER_DATABASE_SUMMARY_FILE
        with database_path.open("w", encoding="utf-8") as f:
            json.dump({
                "common_events": summary.get("common_events") or [],
                "database_pages": summary.get("database_pages") or [],
                "plugin_pages": summary.get("plugin_pages") or [],
                "virtual_pages": summary.get("virtual_pages") or [],
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    _emit_maker_progress(progress_callback, 1, 1, "맵/DB 페이지 구성 완료")
    return paths, data, summary


# ---------------------------------------------------------------------------
# 쯔꾸르붕이 실전 설정/기본정보 헬퍼
# ---------------------------------------------------------------------------

def _maker_project_engine_info(project_dir: str | os.PathLike[str]) -> Dict[str, Any] | None:
    try:
        return dict(maker_project_paths(project_dir).get("engine") or {})
    except Exception:
        return None


def maker_content_root(project_dir: str | os.PathLike[str]) -> Path:
    try:
        return Path(maker_project_paths(project_dir).get("content_root"))
    except Exception:
        return _maker_game_dir(project_dir)


def maker_fonts_dir(project_dir: str | os.PathLike[str]) -> Path:
    root = maker_content_root(project_dir)
    for name in ("fonts", "Fonts", "font", "Font"):
        p = root / name
        if p.is_dir():
            return p
    p = root / "fonts"
    p.mkdir(parents=True, exist_ok=True)
    keep = p / MAKER_KEEP_FILE
    try:
        if not keep.exists():
            keep.write_text("Put RPG Maker game fonts here.\n", encoding="utf-8")
    except Exception:
        pass
    return p


def _maker_font_fingerprint(path: str | os.PathLike[str] | None) -> str:
    try:
        p = Path(path)
        st = p.stat()
        return f"{p.name}|{int(st.st_size)}|{int(getattr(st, 'st_mtime_ns', int(st.st_mtime * 1000000000)))}"
    except Exception:
        return ""


def list_maker_game_fonts(project_dir: str | os.PathLike[str]) -> List[Dict[str, Any]]:
    fonts = []
    fonts_dir = maker_fonts_dir(project_dir)
    exts = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}
    try:
        for p in sorted(fonts_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in exts:
                fp = _maker_font_fingerprint(p)
                fonts.append({"filename": p.name, "path": str(p), "family": p.stem, "suffix": p.suffix.lower(), "fingerprint": fp})
    except Exception:
        pass
    return fonts


def _maker_system_json_path(project_dir: str | os.PathLike[str]) -> Path:
    game_root = _maker_game_dir(project_dir)
    engine_info = _maker_project_engine_info(project_dir)
    data_dir = _data_dir_from_engine_info(game_root, engine_info)
    return data_dir / "System.json"


def _maker_gamefont_css_path(project_dir: str | os.PathLike[str]) -> Path:
    return maker_fonts_dir(project_dir) / "gamefont.css"


def _maker_unique_existing_roots(*roots: Path) -> List[Path]:
    out: List[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            p = Path(root)
            if not p.exists():
                continue
            key = str(p.resolve())
        except Exception:
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        out.append(Path(root))
    return out


def _update_maker_package_title(path: Path, title: str) -> bool:
    if not path.is_file():
        return False
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return False
    changed = False
    window = payload.get("window")
    if isinstance(window, dict):
        if str(window.get("title") or "") != str(title or ""):
            window["title"] = str(title or "")
            changed = True
    # Some exported NW.js packages use productName/title instead of window.title.
    for key in ("productName", "title"):
        if key in payload and str(payload.get(key) or "") != str(title or ""):
            payload[key] = str(title or "")
            changed = True
    if changed:
        _atomic_write_json(path, payload)
    return changed


def _update_maker_index_title(path: Path, title: str) -> bool:
    if not path.is_file():
        return False
    try:
        raw = path.read_text(encoding="utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8-sig")
        enc = "utf-8-sig"
    except Exception:
        return False
    safe_title = html.escape(str(title or ""), quote=False)
    if re.search(r"<title>.*?</title>", raw, flags=re.I | re.S):
        new_raw = re.sub(r"<title>.*?</title>", f"<title>{safe_title}</title>", raw, count=1, flags=re.I | re.S)
    else:
        new_raw = raw
    if new_raw != raw:
        path.write_text(new_raw, encoding=enc)
        return True
    return False


def _apply_maker_game_title_sidecars(project_dir: str | os.PathLike[str], title: str) -> List[str]:
    """Update runtime title sidecar files next to System.json.

    System.json controls the RPG Maker title screen text, but deployed MV/MZ
    builds can also show a title from NW.js package.json or index.html.  Keep
    those sidecars in sync so the change is visible when the cloned game is run.
    """
    project_dir_p = Path(project_dir)
    game_root = _maker_game_dir(project_dir_p)
    roots = [game_root]
    try:
        roots.extend(_candidate_content_roots(game_root))
    except Exception:
        pass
    touched: List[str] = []
    for root in _maker_unique_existing_roots(*roots):
        for rel in ("package.json", "www/package.json"):
            p = root / rel
            try:
                if _update_maker_package_title(p, str(title or "")):
                    touched.append(str(p.relative_to(game_root)).replace("\\", "/"))
            except Exception:
                pass
        for rel in ("index.html", "www/index.html"):
            p = root / rel
            try:
                if _update_maker_index_title(p, str(title or "")):
                    touched.append(str(p.relative_to(game_root)).replace("\\", "/"))
            except Exception:
                pass
    return sorted(set(touched))


def load_maker_game_title(project_dir: str | os.PathLike[str]) -> str:
    try:
        system = _read_json(_maker_system_json_path(project_dir))
        if isinstance(system, dict):
            return str(system.get("gameTitle") or "")
    except Exception:
        pass
    return ""


def save_maker_game_title(project_dir: str | os.PathLike[str], title: str) -> str:
    path = _maker_system_json_path(project_dir)
    system = _read_json(path)
    if not isinstance(system, dict):
        raise MakerWriteBackError("System.json 구조가 올바르지 않습니다.")
    system["gameTitle"] = str(title or "")
    _atomic_write_json(path, system)
    try:
        _apply_maker_game_title_sidecars(project_dir, str(title or ""))
    except Exception:
        pass
    return str(system.get("gameTitle") or "")


def apply_maker_game_font_settings(project_dir: str | os.PathLike[str], settings: Dict[str, Any]) -> Dict[str, Any]:
    """Apply engine-aware game title/font settings to the cloned RPG Maker game.

    MV primarily uses fonts/gamefont.css with a GameFont face.  MZ stores main
    and number font filenames in data/System.json > advanced.  Preview settings
    are saved alongside so 쯔꾸르붕이 renders with the same choices.
    """
    settings = normalize_maker_preview_settings(settings or {})
    project_dir_p = Path(project_dir)
    engine_info = _maker_project_engine_info(project_dir_p)
    engine_id = _engine_id_from_info(engine_info)
    fonts = list_maker_game_fonts(project_dir_p)
    available = {str(f.get("filename") or ""): f for f in fonts}

    main_font = str(settings.get("main_font_filename") or "").strip()
    number_font = str(settings.get("number_font_filename") or "").strip()
    if main_font and main_font not in available:
        raise MakerProjectError(f"fonts 폴더에서 폰트 파일을 찾지 못했습니다: {main_font}")
    if number_font and number_font not in available:
        raise MakerProjectError(f"fonts 폴더에서 숫자 폰트 파일을 찾지 못했습니다: {number_font}")
    if not main_font and fonts:
        main_font = str(fonts[0].get("filename") or "")
    if not number_font:
        number_font = main_font

    settings["main_font_filename"] = main_font
    settings["number_font_filename"] = number_font
    settings["engine_id"] = engine_id
    settings["game_settings_user_saved"] = True
    try:
        from datetime import datetime as _dt
        settings["game_settings_saved_at"] = _dt.now().isoformat(timespec="seconds")
    except Exception:
        settings["game_settings_saved_at"] = str(settings.get("game_settings_saved_at") or "")
    if main_font:
        settings["font_family"] = Path(main_font).stem
        main_font_path = Path(str(available.get(main_font, {}).get("path") or maker_fonts_dir(project_dir_p) / main_font))
        settings["font_path"] = str(main_font_path)
        settings["main_font_fingerprint"] = str(available.get(main_font, {}).get("fingerprint") or _maker_font_fingerprint(main_font_path))
    if number_font:
        number_font_path = Path(str(available.get(number_font, {}).get("path") or maker_fonts_dir(project_dir_p) / number_font))
        settings["number_font_fingerprint"] = str(available.get(number_font, {}).get("fingerprint") or _maker_font_fingerprint(number_font_path))

    system_path = _maker_system_json_path(project_dir_p)
    if system_path.is_file():
        try:
            system = _read_json(system_path)
            if isinstance(system, dict):
                title = str(settings.get("game_title") or "").strip()
                if title:
                    system["gameTitle"] = title
                if engine_id == "mz":
                    adv = system.get("advanced")
                    if not isinstance(adv, dict):
                        adv = {}
                    if main_font:
                        adv["mainFontFilename"] = main_font
                    if number_font:
                        adv["numberFontFilename"] = number_font
                    fallback = str(settings.get("fallback_fonts") or "").strip()
                    if fallback:
                        adv["fallbackFonts"] = fallback
                    try:
                        adv["fontSize"] = int(settings.get("font_size") or 26)
                    except Exception:
                        pass
                    try:
                        adv["windowOpacity"] = int(settings.get("window_opacity") or adv.get("windowOpacity") or 192)
                    except Exception:
                        pass
                    system["advanced"] = adv
                _atomic_write_json(system_path, system)
                try:
                    _apply_maker_game_title_sidecars(project_dir_p, str(system.get("gameTitle") or ""))
                except Exception:
                    pass
        except Exception as e:
            try:
                append_maker_preview_diagnostic(project_dir_p, "game_font_system_json_write_failed", {"error": str(e), "system_path": str(system_path)})
            except Exception:
                pass
            raise MakerProjectError(f"System.json에 게임 폰트 설정을 저장하지 못했습니다: {e}")

    if main_font:
        css_path = _maker_gamefont_css_path(project_dir_p)
        # MV expects the family name GameFont from fonts/gamefont.css.  MZ ignores
        # this for main runtime font but keeping the CSS harmlessly helps webview
        # previews and older projects.
        css = (
            "@font-face {\n"
            "    font-family: GameFont;\n"
            f"    src: url(\"{main_font}\");\n"
            "}\n"
        )
        try:
            css_path.parent.mkdir(parents=True, exist_ok=True)
            css_path.write_text(css, encoding="utf-8")
        except Exception:
            pass
    fixed = save_maker_preview_settings(project_dir_p, settings)
    return fixed

def _walk_system_terms(obj: Any, path: List[Any] | None = None):
    path = list(path or [])
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_system_terms(v, path + [i])
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_system_terms(v, path + [k])


def _get_by_path(obj: Any, path: List[Any], default: Any = "") -> Any:
    cur = obj
    try:
        for key in path:
            cur = cur[key]
        return cur
    except Exception:
        return default


def _set_by_path(obj: Any, path: List[Any], value: Any) -> bool:
    cur = obj
    try:
        for key in path[:-1]:
            cur = cur[key]
        cur[path[-1]] = value
        return True
    except Exception:
        return False


def collect_maker_system_terms(project_dir: str | os.PathLike[str]) -> List[Dict[str, Any]]:
    sys_path = _maker_system_json_path(project_dir)
    system = _read_json(sys_path) if sys_path.is_file() else {}
    if not isinstance(system, dict):
        return []
    terms = system.get("terms")
    original_terms = None
    try:
        game_root = _maker_game_dir(project_dir)
        rel = sys_path.relative_to(game_root)
        backup_path = _maker_original_json_backup_dir(project_dir) / rel
        original = _read_json(backup_path) if backup_path.is_file() else {}
        if isinstance(original, dict):
            original_terms = original.get("terms")
    except Exception:
        original_terms = None
    rows = []
    for path, value in _walk_system_terms(terms, ["terms"]):
        if not str(value or "").strip():
            continue
        rel_path = path[1:] if path and path[0] == "terms" else path
        source = _get_by_path(original_terms, rel_path, value) if original_terms is not None else value
        rows.append({"path": path, "key": "/".join(str(x) for x in path), "source": str(source or ""), "translation": str(value or "")})
    return rows


def apply_maker_system_terms(project_dir: str | os.PathLike[str], rows: Iterable[Dict[str, Any]]) -> int:
    sys_path = _maker_system_json_path(project_dir)
    system = _read_json(sys_path)
    if not isinstance(system, dict):
        raise MakerWriteBackError("System.json 구조가 올바르지 않습니다.")
    changed = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        path = row.get("path")
        if not isinstance(path, list) or not path:
            continue
        value = str(row.get("translation") or "")
        old = _get_by_path(system, path, None)
        if old != value and _set_by_path(system, path, value):
            changed += 1
    if changed:
        _atomic_write_json(sys_path, system)
    return changed


def _is_maker_database_name_field(meta: Dict[str, Any] | None) -> bool:
    """Return True only for database fields that represent visible item/name labels."""
    if not isinstance(meta, dict):
        return False
    field = str(meta.get("db_field") or "").strip().lower()
    path_keys = meta.get("db_path_keys") or []
    try:
        last_path = str(list(path_keys)[-1]).strip().lower() if path_keys else ""
    except Exception:
        last_path = ""
    # Normal RPG Maker DB records use db_field == "name".  Dynamic fallback
    # records may carry a dotted path such as "1.name" instead, so the last
    # path segment is also checked.  Other fields such as nickname/profile,
    # description, message*, gameTitle and System terms are intentionally kept
    # out of the automatic glossary because the glossary is a term/name list.
    return field == "name" or field.endswith(".name") or last_path == "name"


def collect_maker_database_glossary(data: Dict[int, dict] | None) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    entries: List[Dict[str, Any]] = []
    seen_sources: set[str] = set()
    for page_idx, page in _dict_items(data):
        if not isinstance(page, dict):
            continue
        page_type = str(((page.get("maker_page") or {}).get("page_type") or ""))
        for row_index, row in enumerate(page.get("data") or []):
            if not isinstance(row, dict):
                continue
            meta = row.get("maker_text_unit") or {}
            if not isinstance(meta, dict):
                meta = {}
            source_kind = str(meta.get("source_kind") or "").strip().lower()
            is_database_name = page_type == "database" or source_kind == "database"
            is_speaker_name = page_type == "speaker" or source_kind == "speaker"
            if not (is_database_name or is_speaker_name):
                continue
            if not _is_maker_database_name_field(meta):
                continue
            src = str(row.get("text") or "").strip()
            dst = str(row.get("translated_text") or "").strip()
            if not src or not dst:
                continue
            # 원문이 같은 DB name 항목은 처음 인식된 유효 번역문만 대표로 쓴다.
            # 이후 중복 항목은 서로 단어장을 덮어쓰지 않게 무시한다.
            if src in seen_sources:
                continue
            seen_sources.add(src)
            entries.append({
                "source": src,
                "target": dst,
                "source_file": str(meta.get("source_file") or ""),
                "db_kind": str(meta.get("db_kind") or ""),
                "db_field": str(meta.get("db_field") or ""),
                "db_id": meta.get("db_id"),
                "row_index": int(row_index),
                "page_index": int(page_idx) if str(page_idx).lstrip("-").isdigit() else page_idx,
            })
    return entries


def save_maker_database_glossary(project_dir: str | os.PathLike[str], entries: Iterable[Dict[str, Any]]) -> Path:
    path = Path(project_dir) / MAKER_META_DIR / "maker_database_glossary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = list(entries or [])
    path.write_text(json.dumps({"entries": data, "count": len(data), "updated_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_maker_database_glossary(project_dir: str | os.PathLike[str]) -> List[Dict[str, Any]]:
    path = Path(project_dir) / MAKER_META_DIR / "maker_database_glossary.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries") if isinstance(data, dict) else data
        if isinstance(entries, list):
            return [dict(e) for e in entries if isinstance(e, dict)]
    except Exception:
        pass
    return []

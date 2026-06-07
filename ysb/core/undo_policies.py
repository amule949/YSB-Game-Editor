# -*- coding: utf-8 -*-
"""Undo policy map for YSB Game Editor.

Stage 2-1 purpose:
- Keep real stack/restore logic in MainWindowHistoryMixin for now.
- Centralize the classification of actions so feature code does not re-decide
  whether an operation is page/project/view/boundary every time.
- Later stages can make UndoManager enforce these policies directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


SCOPE_PAGE = "page"
SCOPE_PROJECT = "project"
SCOPE_VIEW = "view"
SCOPE_BOUNDARY = "boundary"
SCOPE_RUNTIME = "runtime"

KIND_TEXT_LINE = "text_line"
KIND_TEXT_DIFF = "text_diff"
KIND_UI = "ui"
KIND_VIEW = "view"
KIND_PAINT = "paint"
KIND_MASK = "mask"
KIND_PROJECT_STRUCTURE = "project_structure"
KIND_EXTERNAL_COMMIT = "external_commit"
KIND_BATCH = "batch"
KIND_RUNTIME = "runtime"


@dataclass(frozen=True)
class UndoActionPolicy:
    action: str
    scope: str = SCOPE_PAGE
    kind: str = KIND_TEXT_LINE
    dirty_kinds: tuple[str, ...] = field(default_factory=tuple)
    redo: bool = True
    boundary_policy: str = "none"
    merge_key: str | None = None
    note: str = ""


def _p(action: str, scope: str, kind: str, dirty=(), *, redo=True, boundary="none", merge_key=None, note="") -> UndoActionPolicy:
    if isinstance(dirty, str):
        dirty = (dirty,)
    return UndoActionPolicy(
        action=str(action),
        scope=str(scope),
        kind=str(kind),
        dirty_kinds=tuple(str(x) for x in (dirty or ())),
        redo=bool(redo),
        boundary_policy=str(boundary or "none"),
        merge_key=merge_key,
        note=str(note or ""),
    )


DEFAULT_POLICY = _p("작업", SCOPE_PAGE, KIND_TEXT_LINE, dirty=("text",), note="Default light page text-line undo.")

# UI / view actions
UI_ACTIONS: dict[str, UndoActionPolicy] = {
    "작업 탭 변경": _p("작업 탭 변경", SCOPE_PAGE, KIND_UI, dirty=("view",), merge_key="work_tab"),
    "페이지 이동": _p("페이지 이동", SCOPE_PAGE, KIND_UI, dirty=("view",), merge_key="page_nav"),
    "화면 이동": _p("화면 이동", SCOPE_VIEW, KIND_VIEW, dirty=("view",), merge_key="view_pan"),
    "화면 확대/축소": _p("화면 확대/축소", SCOPE_VIEW, KIND_VIEW, dirty=("view",), merge_key="view_zoom"),
    "화면맞춤": _p("화면맞춤", SCOPE_VIEW, KIND_VIEW, dirty=("view",), merge_key="view_fit"),
    "텍스트 위 페인팅 ON/OFF": _p("텍스트 위 페인팅 ON/OFF", SCOPE_PROJECT, KIND_UI, dirty=("ui",)),
    "마스크 ON/OFF": _p("마스크 ON/OFF", SCOPE_PAGE, KIND_UI, dirty=("mask",)),
}

# Text actions
TEXT_ACTIONS: dict[str, UndoActionPolicy] = {
    "새 텍스트 추가": _p("새 텍스트 추가", SCOPE_PAGE, KIND_TEXT_LINE, dirty=("text",)),
    "텍스트 직접 수정": _p("텍스트 직접 수정", SCOPE_PAGE, KIND_TEXT_LINE, dirty=("text",)),
    "인라인 텍스트 직접 수정": _p("인라인 텍스트 직접 수정", SCOPE_PAGE, KIND_TEXT_LINE, dirty=("text",)),
    "텍스트 삭제": _p("텍스트 삭제", SCOPE_PAGE, KIND_TEXT_LINE, dirty=("text", "mask")),
    "텍스트 붙여넣기": _p("텍스트 붙여넣기", SCOPE_PAGE, KIND_TEXT_LINE, dirty=("text",)),
    "텍스트 원위치 붙여넣기": _p("텍스트 원위치 붙여넣기", SCOPE_PAGE, KIND_TEXT_LINE, dirty=("text",)),
    "텍스트 이동": _p("텍스트 이동", SCOPE_PAGE, KIND_TEXT_DIFF, dirty=("text",), merge_key="text_move"),
    "텍스트 스타일 변경": _p("텍스트 스타일 변경", SCOPE_PAGE, KIND_TEXT_DIFF, dirty=("text",), merge_key="text_style"),
    "고급 텍스트/획 옵션": _p("고급 텍스트/획 옵션", SCOPE_PAGE, KIND_TEXT_DIFF, dirty=("text",)),
    "평행사변형 변형": _p("평행사변형 변형", SCOPE_PAGE, KIND_TEXT_DIFF, dirty=("text",)),
    "사다리꼴 변형": _p("사다리꼴 변형", SCOPE_PAGE, KIND_TEXT_DIFF, dirty=("text",)),
    "부채꼴 변형": _p("부채꼴 변형", SCOPE_PAGE, KIND_TEXT_DIFF, dirty=("text",)),
}

# Paint/mask actions.  Stage 2 keeps viewer history as implementation detail.
PAINT_ACTIONS: dict[str, UndoActionPolicy] = {
    "브러시": _p("브러시", SCOPE_PAGE, KIND_PAINT, dirty=("mask", "final_paint"), merge_key="paint_stroke"),
    "지우개": _p("지우개", SCOPE_PAGE, KIND_PAINT, dirty=("mask", "final_paint"), merge_key="paint_stroke"),
    "페인팅": _p("페인팅", SCOPE_PAGE, KIND_PAINT, dirty=("mask", "final_paint"), merge_key="paint_stroke"),
    "최종 페인팅": _p("최종 페인팅", SCOPE_PAGE, KIND_PAINT, dirty=("final_paint",), merge_key="paint_stroke"),
    "영역 페인팅": _p("영역 페인팅", SCOPE_PAGE, KIND_PAINT, dirty=("final_paint",), merge_key="paint_area"),
    "요술봉 영역 칠하기": _p("요술봉 영역 칠하기", SCOPE_PAGE, KIND_PAINT, dirty=("final_paint",), merge_key="paint_magic"),
    "마스크 브러시": _p("마스크 브러시", SCOPE_PAGE, KIND_MASK, dirty=("mask",), merge_key="mask_stroke"),
    "영역 마스킹": _p("영역 마스킹", SCOPE_PAGE, KIND_MASK, dirty=("mask",), merge_key="mask_area"),
    "요술봉 마스킹 칠하기": _p("요술봉 마스킹 칠하기", SCOPE_PAGE, KIND_MASK, dirty=("mask",), merge_key="mask_magic"),
    "마스크 랩": _p("마스크 랩", SCOPE_PAGE, KIND_MASK, dirty=("mask",)),
    "마스크 컷": _p("마스크 컷", SCOPE_PAGE, KIND_MASK, dirty=("mask",)),
    "마스크 랩핑": _p("마스크 랩핑", SCOPE_PAGE, KIND_MASK, dirty=("mask",)),
    "마스크 커팅": _p("마스크 커팅", SCOPE_PAGE, KIND_MASK, dirty=("mask",)),
    "요술봉": _p("요술봉", SCOPE_PAGE, KIND_MASK, dirty=("mask",)),
    "마스크 초기화": _p("마스크 초기화", SCOPE_PAGE, KIND_MASK, dirty=("mask",)),
}

# Project structure and external commit actions.
PROJECT_ACTIONS: dict[str, UndoActionPolicy] = {
    "페이지 추가": _p("페이지 추가", SCOPE_PROJECT, KIND_PROJECT_STRUCTURE, dirty=("project_structure",)),
    "페이지 삭제": _p("페이지 삭제", SCOPE_PROJECT, KIND_PROJECT_STRUCTURE, dirty=("project_structure",)),
    "페이지 순서 변경": _p("페이지 순서 변경", SCOPE_PROJECT, KIND_PROJECT_STRUCTURE, dirty=("project_structure",)),
    "페이지 이름 변경": _p("페이지 이름 변경", SCOPE_PROJECT, KIND_PROJECT_STRUCTURE, dirty=("project_structure",)),
    "배경을 원본으로 쓰기": _p("배경을 원본으로 쓰기", SCOPE_PROJECT, KIND_EXTERNAL_COMMIT, dirty=("clean_background",), boundary="page_or_batch"),
}

BOUNDARY_ACTIONS: dict[str, UndoActionPolicy] = {
    # Single-page external commits
    "analyze": _p("analyze", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("text", "mask"), redo=False, boundary="clear_page"),
    "analysis": _p("analysis", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("text", "mask"), redo=False, boundary="clear_page"),
    "reanalyze": _p("reanalyze", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("mask",), redo=False, boundary="clear_page"),
    "translate": _p("translate", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("text",), redo=False, boundary="clear_page"),
    "translation": _p("translation", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("text",), redo=False, boundary="clear_page"),
    "inpaint": _p("inpaint", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("clean_background",), redo=False, boundary="clear_page"),

    # Batch / multi-page external commits
    "batch": _p("batch", SCOPE_BOUNDARY, KIND_BATCH, dirty=("project",), redo=False, boundary="clear_all_pages"),
    "batch_start": _p("batch_start", SCOPE_BOUNDARY, KIND_BATCH, dirty=("project",), redo=False, boundary="clear_all_pages"),
    "batch_finish": _p("batch_finish", SCOPE_BOUNDARY, KIND_BATCH, dirty=("project",), redo=False, boundary="clear_all_pages"),
    "batch_inpaint": _p("batch_inpaint", SCOPE_BOUNDARY, KIND_BATCH, dirty=("clean_background",), redo=False, boundary="clear_all_pages"),

    # Project/background external commits
    "clean_import": _p("clean_import", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("clean_background",), redo=False, boundary="clear_all_pages"),
    "clean_import_recovered": _p("clean_import_recovered", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("clean_background",), redo=False, boundary="clear_all_pages"),
    "restore_original_source": _p("restore_original_source", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("source_image",), redo=False, boundary="page_or_batch"),
    "use_background_as_source": _p("use_background_as_source", SCOPE_BOUNDARY, KIND_EXTERNAL_COMMIT, dirty=("source_image",), redo=False, boundary="page_or_batch"),

    # Macro/project lifecycle
    "macro": _p("macro", SCOPE_BOUNDARY, KIND_BATCH, dirty=("project",), redo=False, boundary="legacy_clear_all"),
    "project_open": _p("project_open", SCOPE_BOUNDARY, KIND_PROJECT_STRUCTURE, dirty=("project_structure",), redo=False, boundary="clear_all"),
}

POLICY_MAP: dict[str, UndoActionPolicy] = {}
for _group in (UI_ACTIONS, TEXT_ACTIONS, PAINT_ACTIONS, PROJECT_ACTIONS, BOUNDARY_ACTIONS):
    POLICY_MAP.update(_group)


def normalize_action_name(action: str | None) -> str:
    return str(action or "").strip()


def policy_for(action: str | None, *, default: UndoActionPolicy | None = None) -> UndoActionPolicy:
    name = normalize_action_name(action)
    if not name:
        return default or DEFAULT_POLICY
    return POLICY_MAP.get(name) or default or DEFAULT_POLICY


def is_scope(action: str | None, scope: str) -> bool:
    return policy_for(action).scope == str(scope)


def is_kind(action: str | None, kind: str) -> bool:
    return policy_for(action).kind == str(kind)


def action_names_for_scope(scope: str) -> tuple[str, ...]:
    scope = str(scope)
    return tuple(name for name, pol in POLICY_MAP.items() if pol.scope == scope)


def all_policies() -> tuple[UndoActionPolicy, ...]:
    return tuple(POLICY_MAP.values())

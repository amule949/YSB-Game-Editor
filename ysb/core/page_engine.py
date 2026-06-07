from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Callable
import copy


@dataclass
class PageDirtyState:
    """Dirty flags for one active page workbench.

    This class is runtime-only. It must not know project.json, package paths,
    or project-level save behavior.
    """
    text: bool = False
    mask: bool = False
    paint: bool = False
    view: bool = False
    data: bool = False
    kinds: Set[str] = field(default_factory=set)

    def mark(self, kind: str) -> None:
        kind = str(kind or "").strip()
        if not kind:
            return
        self.kinds.add(kind)
        if kind.startswith("text"):
            self.text = True
            self.data = True
        elif kind.startswith("mask"):
            self.mask = True
            self.data = True
        elif kind.startswith("paint") or kind in {"final_paint", "final-paint"}:
            self.paint = True
            self.data = True
        elif kind.startswith("view"):
            self.view = True
        else:
            self.data = True

    def clear(self) -> None:
        self.text = self.mask = self.paint = self.view = self.data = False
        self.kinds.clear()

    def any(self) -> bool:
        return bool(self.text or self.mask or self.paint or self.view or self.data or self.kinds)


@dataclass
class PageWorkbench:
    """Runtime workbench for exactly one page.

    Project-level concepts are intentionally absent. A PageWorkbench only knows
    its page index, mode, local dirty flags, local undo stacks, and temporary
    runtime caches. ProjectEngine decides when to save the project.
    """
    page_idx: int = -1
    mode_idx: int = 0
    dirty: PageDirtyState = field(default_factory=PageDirtyState)
    undo_stack: List[Dict[str, Any]] = field(default_factory=list)
    redo_stack: List[Dict[str, Any]] = field(default_factory=list)
    view_undo_pending: Optional[Dict[str, Any]] = None
    view_undo_reason: str = ""
    runtime: Dict[str, Any] = field(default_factory=dict)

    def reset_for_page(self, page_idx: int, mode_idx: int = 0, *, clear_undo: bool = True) -> None:
        self.page_idx = int(page_idx)
        self.mode_idx = int(mode_idx)
        self.dirty.clear()
        self.view_undo_pending = None
        self.view_undo_reason = ""
        self.runtime.clear()
        if clear_undo:
            self.undo_stack.clear()
            self.redo_stack.clear()

    def mark_dirty(self, kind: str) -> None:
        self.dirty.mark(kind)

    # Compatibility with older ActivePageSession callers.
    @property
    def text_dirty(self) -> bool:
        return self.dirty.text

    @text_dirty.setter
    def text_dirty(self, value: bool) -> None:
        self.dirty.text = bool(value)

    @property
    def mask_dirty(self) -> bool:
        return self.dirty.mask

    @mask_dirty.setter
    def mask_dirty(self, value: bool) -> None:
        self.dirty.mask = bool(value)

    @property
    def paint_dirty(self) -> bool:
        return self.dirty.paint

    @paint_dirty.setter
    def paint_dirty(self, value: bool) -> None:
        self.dirty.paint = bool(value)

    @property
    def view_dirty(self) -> bool:
        return self.dirty.view

    @view_dirty.setter
    def view_dirty(self, value: bool) -> None:
        self.dirty.view = bool(value)

    @property
    def dirty_kinds(self) -> Set[str]:
        return self.dirty.kinds

    def reset(self, page_idx: int, mode_idx: int = 0) -> None:
        self.reset_for_page(page_idx, mode_idx, clear_undo=True)


class YSBPageEngine:
    """Page-only runtime engine.

    The engine is deliberately small in this first refactor pass. It creates a
    hard conceptual boundary: page edits mark the current page workbench dirty;
    they do not save or package the project. Existing UI code can still use
    self.data/self.view, but should go through this engine for dirty/undo/view
    state from now on.
    """

    def __init__(self, *, on_dirty: Optional[Callable[[int, str], None]] = None, max_undo: int = 120):
        self.current = PageWorkbench()
        self.page_workbenches: Dict[int, PageWorkbench] = {}
        self.on_dirty = on_dirty
        self.max_undo = max(10, int(max_undo or 120))

    def activate(self, page_idx: int, mode_idx: int = 0, *, clear_undo_on_page_change: bool = True) -> PageWorkbench:
        page_idx = int(page_idx)
        mode_idx = int(mode_idx)
        if self.current.page_idx == page_idx:
            self.current.mode_idx = mode_idx
            self.page_workbenches[page_idx] = self.current
            return self.current
        if self.current.page_idx >= 0:
            self.page_workbenches[self.current.page_idx] = self.current
        wb = self.page_workbenches.get(page_idx)
        if wb is None:
            wb = PageWorkbench(page_idx=page_idx, mode_idx=mode_idx)
            self.page_workbenches[page_idx] = wb
        if clear_undo_on_page_change:
            wb.reset_for_page(page_idx, mode_idx, clear_undo=True)
        else:
            wb.page_idx = page_idx
            wb.mode_idx = mode_idx
        self.current = wb
        return wb

    def get(self, page_idx: Optional[int] = None) -> PageWorkbench:
        if page_idx is None:
            return self.current
        page_idx = int(page_idx)
        if page_idx == self.current.page_idx:
            return self.current
        wb = self.page_workbenches.get(page_idx)
        if wb is None:
            wb = PageWorkbench(page_idx=page_idx)
            self.page_workbenches[page_idx] = wb
        return wb

    def mark_dirty(self, page_idx: Optional[int], kind: str) -> None:
        wb = self.get(page_idx)
        wb.mark_dirty(kind)
        if callable(self.on_dirty):
            try:
                self.on_dirty(wb.page_idx, str(kind or "data"))
            except Exception:
                pass

    def clear_page_undo(self, page_idx: Optional[int] = None) -> None:
        wb = self.get(page_idx)
        wb.undo_stack.clear()
        wb.redo_stack.clear()
        wb.view_undo_pending = None

    def clear_all_undo(self) -> None:
        self.current.undo_stack.clear()
        self.current.redo_stack.clear()
        self.current.view_undo_pending = None
        for wb in self.page_workbenches.values():
            wb.undo_stack.clear()
            wb.redo_stack.clear()
            wb.view_undo_pending = None

    def push_undo(self, record: Dict[str, Any], page_idx: Optional[int] = None, *, clear_redo: bool = True) -> bool:
        if not isinstance(record, dict):
            return False
        wb = self.get(page_idx if page_idx is not None else record.get("page_idx", None))
        rec = copy.deepcopy(record)
        rec.setdefault("page_idx", wb.page_idx)
        rec["_engine_scope"] = "page"
        wb.undo_stack.append(rec)
        if len(wb.undo_stack) > self.max_undo:
            del wb.undo_stack[0:len(wb.undo_stack) - self.max_undo]
        if clear_redo:
            wb.redo_stack.clear()
        return True

    def pop_undo(self, page_idx: Optional[int] = None) -> Optional[Dict[str, Any]]:
        wb = self.get(page_idx)
        if not wb.undo_stack:
            return None
        return wb.undo_stack.pop()

    def push_redo(self, record: Dict[str, Any], page_idx: Optional[int] = None) -> bool:
        if not isinstance(record, dict):
            return False
        wb = self.get(page_idx if page_idx is not None else record.get("page_idx", None))
        rec = copy.deepcopy(record)
        rec.setdefault("page_idx", wb.page_idx)
        rec["_engine_scope"] = "page"
        wb.redo_stack.append(rec)
        if len(wb.redo_stack) > self.max_undo:
            del wb.redo_stack[0:len(wb.redo_stack) - self.max_undo]
        return True

    def pop_redo(self, page_idx: Optional[int] = None) -> Optional[Dict[str, Any]]:
        wb = self.get(page_idx)
        if not wb.redo_stack:
            return None
        return wb.redo_stack.pop()

    def dirty_pages(self) -> Set[int]:
        out: Set[int] = set()
        if self.current.page_idx >= 0 and self.current.dirty.any():
            out.add(self.current.page_idx)
        for idx, wb in self.page_workbenches.items():
            if wb.dirty.any():
                out.add(idx)
        return out

    def clear_dirty(self, page_idx: Optional[int] = None) -> None:
        if page_idx is None:
            for wb in self.page_workbenches.values():
                wb.dirty.clear()
            self.current.dirty.clear()
            return
        self.get(page_idx).dirty.clear()

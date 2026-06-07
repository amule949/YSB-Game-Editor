from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ActivePageSession:
    """Runtime-only workbench for the currently active page.

    This object intentionally stores only transient state. Project JSON/images/masks
    remain in ProjectStore/self.data and are flushed explicitly by save/commit code.
    """
    page_idx: int = -1
    mode_idx: int = 0
    text_dirty: bool = False
    mask_dirty: bool = False
    paint_dirty: bool = False
    view_dirty: bool = False
    dirty_kinds: Set[str] = field(default_factory=set)
    view_undo_pending: Optional[Dict[str, Any]] = None
    view_undo_reason: str = ""

    def reset(self, page_idx: int, mode_idx: int = 0) -> None:
        self.page_idx = int(page_idx)
        self.mode_idx = int(mode_idx)
        self.text_dirty = False
        self.mask_dirty = False
        self.paint_dirty = False
        self.view_dirty = False
        self.dirty_kinds.clear()
        self.view_undo_pending = None
        self.view_undo_reason = ""

    def mark_dirty(self, kind: str) -> None:
        kind = str(kind or "").strip()
        if not kind:
            return
        self.dirty_kinds.add(kind)
        if kind.startswith("text"):
            self.text_dirty = True
        elif kind.startswith("mask"):
            self.mask_dirty = True
        elif kind.startswith("paint") or kind == "final_paint":
            self.paint_dirty = True
        elif kind.startswith("view"):
            self.view_dirty = True

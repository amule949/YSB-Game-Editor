from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Any


@dataclass
class ProjectDirtyState:
    """Project-level dirty tracker.

    Page-level edits are tracked by page index/kind only. The project engine does
    not inspect or mutate QGraphicsScene/QPixmap/text widgets. It only knows
    which page or project structure needs flushing when an explicit save happens.
    """
    dirty_pages: Dict[int, Set[str]] = field(default_factory=dict)
    structure_dirty: bool = False
    structure_reasons: Set[str] = field(default_factory=set)
    metadata_dirty: bool = False

    def mark_page(self, page_idx: int, kind: str = "data") -> None:
        self.dirty_pages.setdefault(int(page_idx), set()).add(str(kind or "data"))

    def mark_structure(self, reason: str = "structure") -> None:
        self.structure_dirty = True
        self.structure_reasons.add(str(reason or "structure"))

    def any(self) -> bool:
        return bool(self.dirty_pages or self.structure_dirty or self.metadata_dirty)

    def clear(self) -> None:
        self.dirty_pages.clear()
        self.structure_dirty = False
        self.structure_reasons.clear()
        self.metadata_dirty = False


class YSBProjectEngine:
    """Project-only coordinator.

    This object owns project-level dirtiness and save boundaries. Page edit code
    should call mark_page_dirty(), not ProjectStore.save()/package_project().
    Explicit save actions may call begin_explicit_save()/end_explicit_save() to
    allow project-level persistence.
    """

    def __init__(self):
        self.dirty = ProjectDirtyState()
        self.explicit_save_depth = 0
        self.autosave_suspended_depth = 0

    def mark_page_dirty(self, page_idx: int, kind: str = "data") -> None:
        self.dirty.mark_page(page_idx, kind)

    def mark_structure_dirty(self, reason: str = "structure") -> None:
        self.dirty.mark_structure(reason)

    def mark_metadata_dirty(self) -> None:
        self.dirty.metadata_dirty = True

    def has_dirty(self) -> bool:
        return self.dirty.any()

    def is_project_save_allowed(self, *, auto_save_enabled: bool = False) -> bool:
        if self.explicit_save_depth > 0:
            return True
        if self.autosave_suspended_depth > 0:
            return False
        return bool(auto_save_enabled)

    def begin_explicit_save(self) -> None:
        self.explicit_save_depth += 1

    def end_explicit_save(self) -> None:
        self.explicit_save_depth = max(0, self.explicit_save_depth - 1)

    def suspend_autosave(self) -> None:
        self.autosave_suspended_depth += 1

    def resume_autosave(self) -> None:
        self.autosave_suspended_depth = max(0, self.autosave_suspended_depth - 1)

    def mark_saved(self) -> None:
        self.dirty.clear()

    def page_dirty_kinds(self, page_idx: int) -> Set[str]:
        return set(self.dirty.dirty_pages.get(int(page_idx), set()))

    def dirty_page_indices(self) -> Set[int]:
        return set(int(x) for x in self.dirty.dirty_pages.keys())

    def is_structure_dirty(self) -> bool:
        return bool(self.dirty.structure_dirty)

    def dirty_summary(self) -> Dict[str, Any]:
        return {
            "dirty_pages": {int(k): sorted(v) for k, v in self.dirty.dirty_pages.items()},
            "structure_dirty": bool(self.dirty.structure_dirty),
            "metadata_dirty": bool(self.dirty.metadata_dirty),
            "structure_reasons": sorted(self.dirty.structure_reasons),
        }

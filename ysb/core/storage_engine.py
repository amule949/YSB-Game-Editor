from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set, Dict, Any


@dataclass
class ProjectSavePlan:
    """A lightweight save plan owned by the project layer only.

    Page editors should only mark dirty pages. The storage layer decides whether
    ProjectStore.save() may reuse old page records or must rebuild the full
    project manifest.
    """
    incremental: bool = True
    dirty_pages: Set[int] = field(default_factory=set)
    structure_dirty: bool = False
    metadata_dirty: bool = False
    reason: str = ""

    def needs_full_save(self) -> bool:
        return bool(self.structure_dirty or not self.incremental)


class YSBStorageEngine:
    """Project-level save planner.

    This object does not inspect QGraphicsScene, QPixmap, text widgets, masks or
    page runtime buffers. It only combines ProjectEngine and PageEngine dirty
    information into a small save plan for ProjectStore.
    """

    def __init__(self, project_engine=None, page_engine=None):
        self.project_engine = project_engine
        self.page_engine = page_engine
        self.last_plan: Optional[ProjectSavePlan] = None

    def bind(self, *, project_engine=None, page_engine=None) -> None:
        if project_engine is not None:
            self.project_engine = project_engine
        if page_engine is not None:
            self.page_engine = page_engine

    def collect_dirty_pages(self) -> Set[int]:
        dirty: Set[int] = set()
        pe = self.project_engine
        pg = self.page_engine
        try:
            if pe is not None:
                dirty.update(int(x) for x in getattr(pe.dirty, 'dirty_pages', {}).keys())
        except Exception:
            pass
        try:
            if pg is not None:
                dirty.update(int(x) for x in pg.dirty_pages())
        except Exception:
            pass
        return dirty

    def make_plan(self, *, force_full: bool = False, reason: str = "") -> ProjectSavePlan:
        pe = self.project_engine
        structure_dirty = bool(force_full)
        metadata_dirty = False
        try:
            if pe is not None:
                structure_dirty = structure_dirty or bool(getattr(pe.dirty, 'structure_dirty', False))
                metadata_dirty = bool(getattr(pe.dirty, 'metadata_dirty', False))
        except Exception:
            pass
        plan = ProjectSavePlan(
            incremental=not bool(force_full),
            dirty_pages=self.collect_dirty_pages(),
            structure_dirty=structure_dirty,
            metadata_dirty=metadata_dirty,
            reason=str(reason or ''),
        )
        self.last_plan = plan
        return plan

    def apply_plan_to_store(self, store, plan: ProjectSavePlan) -> None:
        if store is None or plan is None:
            return
        try:
            store._save_incremental_allowed = bool(plan.incremental and not plan.needs_full_save())
            store._save_dirty_pages = set(int(x) for x in (plan.dirty_pages or set()))
            store._save_structure_dirty = bool(plan.structure_dirty)
            store._save_metadata_dirty = bool(plan.metadata_dirty)
            store._save_plan_reason = str(plan.reason or '')
        except Exception:
            pass

    def clear_plan_on_store(self, store) -> None:
        if store is None:
            return
        for name in (
            '_save_incremental_allowed', '_save_dirty_pages', '_save_structure_dirty',
            '_save_metadata_dirty', '_save_plan_reason'
        ):
            try:
                if hasattr(store, name):
                    delattr(store, name)
            except Exception:
                pass

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
import copy


@dataclass
class LayerModeState:
    """Runtime-only layer/mode state for one active page.

    The layer engine is intentionally page-local. It does not save project.json,
    does not package, and does not decide page order. It only guards mode/layer
    switching so tab changes do not wake project-level undo/save paths.
    """
    page_idx: int = -1
    mode_idx: int = 0
    last_mode_idx: int = 0
    layer_cache: Dict[str, Any] = field(default_factory=dict)


class YSBLayerEngine:
    """Page-local layer/mode engine.

    First pass goals:
    - keep tab/mode changes inside the current page undo stack;
    - prevent view-only mode changes from marking the project dirty;
    - avoid expensive mask/final-paint commits when the active page layer is not dirty;
    - centralize later layer show/hide refactors behind one boundary.
    """

    def __init__(self, *, on_push_undo: Optional[Callable[[Dict[str, Any], int], bool]] = None):
        self.states: Dict[int, LayerModeState] = {}
        self.current = LayerModeState()
        self.on_push_undo = on_push_undo
        self._switching = False

    def activate(self, page_idx: int, mode_idx: int = 0) -> LayerModeState:
        page_idx = int(page_idx)
        mode_idx = int(mode_idx)
        st = self.states.get(page_idx)
        if st is None:
            st = LayerModeState(page_idx=page_idx, mode_idx=mode_idx, last_mode_idx=mode_idx)
            self.states[page_idx] = st
        st.last_mode_idx = st.mode_idx
        st.mode_idx = mode_idx
        self.current = st
        return st

    def begin_switch(self, page_idx: int, old_mode: int, new_mode: int) -> LayerModeState:
        self._switching = True
        st = self.activate(page_idx, old_mode)
        st.last_mode_idx = int(old_mode)
        st.mode_idx = int(new_mode)
        return st

    def end_switch(self, page_idx: int, mode_idx: int) -> None:
        st = self.activate(page_idx, mode_idx)
        st.mode_idx = int(mode_idx)
        self._switching = False

    def switching(self) -> bool:
        return bool(self._switching)

    @staticmethod
    def _workbench_for(main: Any, page_idx: int):
        try:
            pe = getattr(main, "page_engine", None)
            if pe is not None:
                return pe.get(int(page_idx))
        except Exception:
            pass
        try:
            return getattr(main, "active_page_session", None)
        except Exception:
            return None

    @staticmethod
    def _dirty_kind(main: Any, page_idx: int, kind: str) -> bool:
        wb = YSBLayerEngine._workbench_for(main, page_idx)
        try:
            dirty = getattr(wb, "dirty", None)
            if dirty is not None:
                if kind == "mask":
                    return bool(getattr(dirty, "mask", False) or any(str(x).startswith("mask") for x in getattr(dirty, "kinds", set())))
                if kind == "paint":
                    return bool(getattr(dirty, "paint", False) or any(str(x).startswith("paint") or str(x) in {"final_paint", "final-paint"} for x in getattr(dirty, "kinds", set())))
                if kind == "text":
                    return bool(getattr(dirty, "text", False) or any(str(x).startswith("text") for x in getattr(dirty, "kinds", set())))
        except Exception:
            pass
        return False

    def should_commit_mask_before_leave(self, main: Any, page_idx: int, old_mode: int) -> bool:
        """Only flush mask layer on tab leave if the page actually has mask changes.

        Old mode 2/3 was flushing the QImage mask on every tab change. That is
        safe but expensive and wakes save/dirty paths even when the user merely
        visits the tab. The new rule: commit only when mask is dirty or a pending
        layer commit explicitly asks for mask flush.
        """
        try:
            if int(old_mode) not in (2, 3):
                return False
        except Exception:
            return False
        try:
            pending = getattr(main, "_pending_view_layer_commit_kinds", set()) or set()
            if "mask" in pending:
                return True
        except Exception:
            pass
        return self._dirty_kind(main, page_idx, "mask")

    def should_commit_paint_before_leave(self, main: Any, page_idx: int, old_mode: int) -> bool:
        try:
            if int(old_mode) != 4:
                return False
        except Exception:
            return False
        try:
            pending = getattr(main, "_pending_view_layer_commit_kinds", set()) or set()
            if "final_paint" in pending or "paint" in pending:
                return True
        except Exception:
            pass
        return self._dirty_kind(main, page_idx, "paint")

    def push_mode_undo(self, main: Any, page_idx: int, old_mode: int, new_mode: int, view_state: Optional[Dict[str, Any]] = None) -> bool:
        """Record ordinary work-tab changes on the single Undo timeline.

        Mask/paint history stays on the fast viewer.history patch path, but tab
        navigation is still a user-visible action and should be undoable.  This
        method only creates a light UI command containing the old/new tab index
        plus the previous view state; the command apply path suppresses nested
        mode undo and mask/paint commits so Ctrl+Z can step through tabs without
        waking the heavy paint history pipeline.
        """
        try:
            old_mode_i = int(old_mode)
            new_mode_i = int(new_mode)
            page_idx_i = int(page_idx)
        except Exception:
            return False
        if old_mode_i == new_mode_i:
            return False
        record = {
            "reason": "작업 탭 변경",
            "page_idx": page_idx_i,
            "mode": old_mode_i,
            "new_mode": new_mode_i,
            "view_state": copy.deepcopy(view_state or {}),
            "view_only": True,
            "ui_only": True,
            "_undo_scope": "command",
        }
        ok = False
        if callable(self.on_push_undo):
            try:
                ok = bool(self.on_push_undo(record, page_idx_i))
            except Exception as exc:
                ok = False
                try:
                    if main is not None and hasattr(main, "audit_boundary_event"):
                        main.audit_boundary_event(
                            "WORK_TAB_UNDO_PUSH_ERROR",
                            page_idx=page_idx_i, old_mode=old_mode_i, new_mode=new_mode_i, error=repr(exc), throttle_ms=100,
                        )
                except Exception:
                    pass
        try:
            if main is not None and hasattr(main, "audit_boundary_event"):
                main.audit_boundary_event(
                    "WORK_TAB_UNDO_RECORDED",
                    page_idx=page_idx_i, old_mode=old_mode_i, new_mode=new_mode_i, ok=bool(ok), throttle_ms=100,
                )
        except Exception:
            pass
        return bool(ok)

    def remember_mode_state(self, page_idx: int, mode_idx: int, state: Dict[str, Any]) -> None:
        st = self.activate(page_idx, mode_idx)
        st.layer_cache[f"view:{int(mode_idx)}"] = copy.deepcopy(state or {})

    def cached_mode_state(self, page_idx: int, mode_idx: int) -> Dict[str, Any]:
        try:
            return copy.deepcopy(self.states.get(int(page_idx), LayerModeState()).layer_cache.get(f"view:{int(mode_idx)}") or {})
        except Exception:
            return {}

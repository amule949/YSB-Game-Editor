from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple
import copy


@dataclass
class ViewAction:
    """One page-local view/navigation action.

    This is intentionally page-only. It stores only view state values and does
    not know project.json, images, masks, package paths, or page data.
    """
    page_idx: int
    mode_idx: int
    reason: str
    before: Dict[str, Any]
    after: Dict[str, Any] = field(default_factory=dict)


class YSBViewEngine:
    """Page-local View engine for scroll/zoom/pan history.

    View actions are small value snapshots. They are allowed to share Ctrl+Z
    with editing actions, but they must never use ProjectUndo or save paths.
    Page changes are boundaries: view undo lives only inside the active page.
    """

    def __init__(self, *, capture_state: Optional[Callable[[], Dict[str, Any]]] = None,
                 apply_state: Optional[Callable[[Dict[str, Any]], bool]] = None,
                 on_push_undo: Optional[Callable[[Dict[str, Any], int], bool]] = None):
        self.capture_state = capture_state
        self.apply_state = apply_state
        self.on_push_undo = on_push_undo
        self.pending: Optional[ViewAction] = None
        self.last_states: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self.suppress: bool = False

    def key(self, page_idx: int, mode_idx: int) -> Tuple[int, int]:
        return int(page_idx), int(mode_idx)

    def capture(self) -> Dict[str, Any]:
        if callable(self.capture_state):
            try:
                return copy.deepcopy(self.capture_state() or {})
            except Exception:
                return {}
        return {}

    def remember(self, page_idx: int, mode_idx: int, state: Optional[Dict[str, Any]] = None) -> None:
        self.last_states[self.key(page_idx, mode_idx)] = copy.deepcopy(state if state is not None else self.capture())

    def begin(self, page_idx: int, mode_idx: int, reason: str = "화면 이동") -> Optional[ViewAction]:
        if self.suppress:
            return None
        page_idx = int(page_idx)
        mode_idx = int(mode_idx)
        before = copy.deepcopy(self.last_states.get(self.key(page_idx, mode_idx)) or self.capture())
        self.pending = ViewAction(page_idx=page_idx, mode_idx=mode_idx, reason=str(reason or "화면 이동"), before=before)
        return self.pending

    def ensure_pending(self, page_idx: int, mode_idx: int, reason: str = "화면 이동") -> Optional[ViewAction]:
        if self.pending is None:
            return self.begin(page_idx, mode_idx, reason)
        if self.pending.page_idx != int(page_idx) or self.pending.mode_idx != int(mode_idx):
            # Page/mode changes are hard boundaries. Close the old pending action.
            self.pending = None
            return self.begin(page_idx, mode_idx, reason)
        return self.pending

    def finish(self, *, force: bool = False) -> bool:
        action = self.pending
        self.pending = None
        if action is None:
            return False
        after = self.capture()
        action.after = copy.deepcopy(after)
        self.remember(action.page_idx, action.mode_idx, after)
        if not force and self.states_equal(action.before, action.after):
            return False
        record = {
            "reason": action.reason,
            "page_idx": int(action.page_idx),
            "mode": int(action.mode_idx),
            "view_state": copy.deepcopy(action.before),
            "view_new_state": copy.deepcopy(action.after),
            "view_only": True,
            "ui_only": True,
            "_undo_scope": "page",
        }
        if callable(self.on_push_undo):
            try:
                return bool(self.on_push_undo(record, int(action.page_idx)))
            except Exception:
                return False
        return False

    def cancel(self) -> None:
        self.pending = None

    def apply(self, state: Dict[str, Any]) -> bool:
        if not isinstance(state, dict) or not state:
            return False
        if not callable(self.apply_state):
            return False
        old = self.suppress
        self.suppress = True
        try:
            return bool(self.apply_state(copy.deepcopy(state)))
        except Exception:
            return False
        finally:
            self.suppress = old

    @staticmethod
    def states_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        if not isinstance(a, dict) or not isinstance(b, dict):
            return False
        # Scrollbars can bounce by 0/1 pixel due to Qt layout. Treat tiny jitter as no-op.
        try:
            at = [round(float(x), 5) for x in (a.get("transform") or [])]
            bt = [round(float(x), 5) for x in (b.get("transform") or [])]
            if at != bt:
                return False
            if abs(int(a.get("h_scroll", 0) or 0) - int(b.get("h_scroll", 0) or 0)) > 1:
                return False
            if abs(int(a.get("v_scroll", 0) or 0) - int(b.get("v_scroll", 0) or 0)) > 1:
                return False
            return True
        except Exception:
            return a == b

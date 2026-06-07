from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
import copy
import os

import numpy as np


MASK_KEYS: Tuple[str, ...] = (
    "mask_merge",
    "mask_inpaint",
    "mask_merge_off",
    "mask_inpaint_off",
)


@dataclass
class MaskDirtyState:
    keys: set[str] = field(default_factory=set)
    toggle_dirty: bool = False

    def mark(self, key: str | None = None, *, toggle: bool = False) -> None:
        if key:
            self.keys.add(str(key))
        if toggle:
            self.toggle_dirty = True

    def clear(self) -> None:
        self.keys.clear()
        self.toggle_dirty = False

    def any(self) -> bool:
        return bool(self.keys or self.toggle_dirty)


@dataclass
class MagicWandRuntime:
    mask: Any = None
    seed: Optional[Tuple[int, int]] = None
    seeds: List[Tuple[int, int]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def _copy_history_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(state, dict):
            return {}
        out = {
            "active": bool(state.get("active", False)),
            "mask": state.get("mask").copy() if isinstance(state.get("mask"), np.ndarray) else None,
            "seed": tuple(state.get("seed")) if state.get("seed") else None,
            "seeds": [tuple(x) for x in (state.get("seeds") or [])],
        }
        return out

    def capture(self, *, active: bool = False, include_history: bool = False) -> Dict[str, Any]:
        state = {
            "active": bool(active),
            "mask": self.mask.copy() if isinstance(self.mask, np.ndarray) else None,
            "seed": tuple(self.seed) if self.seed else None,
            "seeds": [tuple(x) for x in (self.seeds or [])],
        }
        if include_history and self.history:
            # Page undo records need to restore the internal Magic Wand step stack
            # after undoing a real mask fill. Keep the stored history flat so
            # push_history() does not recursively copy older history arrays.
            state["history"] = [self._copy_history_state(item) for item in self.history if isinstance(item, dict)]
        return state

    def restore(self, state: Dict[str, Any] | None) -> None:
        if not isinstance(state, dict):
            self.clear(clear_history=False)
            return
        m = state.get("mask")
        self.mask = m.copy() if isinstance(m, np.ndarray) else None
        self.seeds = [tuple(x) for x in (state.get("seeds") or [])]
        if state.get("seed"):
            self.seed = tuple(state.get("seed"))
        else:
            self.seed = self.seeds[-1] if self.seeds else None
        if "history" in state:
            self.history = [self._copy_history_state(item) for item in (state.get("history") or []) if isinstance(item, dict)]

    def push_history(self, limit: int = 30) -> None:
        self.history.append(self.capture(active=True, include_history=False))
        if len(self.history) > max(1, int(limit or 30)):
            del self.history[0:len(self.history) - int(limit or 30)]

    def undo(self) -> bool:
        if not self.history:
            return False
        state = self.history.pop()
        self.restore(state)
        return True

    def clear(self, *, clear_history: bool = True) -> None:
        self.mask = None
        self.seed = None
        self.seeds = []
        if clear_history:
            self.history = []


class YSBMaskEngine:
    """Page-local mask/magic-wand engine.

    This engine owns current-page mask dirty state and magic-wand runtime state.
    It never saves project.json, never packages a project, and never decides page
    order. Disk I/O is delegated through callables provided by the UI layer.
    """

    def __init__(self, *, on_dirty: Optional[Callable[[int, str], None]] = None, max_magic_history: int = 30):
        self.on_dirty = on_dirty
        self.max_magic_history = max(1, int(max_magic_history or 30))
        self.dirty_by_page: Dict[int, MaskDirtyState] = {}
        self.magic_by_page: Dict[int, MagicWandRuntime] = {}

    @staticmethod
    def active_key(mode_idx: int, mask_toggle_enabled: bool = False) -> Optional[str]:
        try:
            mode_idx = int(mode_idx)
        except Exception:
            return None
        if mode_idx == 2:
            return "mask_merge"
        if mode_idx == 3:
            return "mask_inpaint" if bool(mask_toggle_enabled) else "mask_inpaint_off"
        return None

    def dirty_state(self, page_idx: int) -> MaskDirtyState:
        page_idx = int(page_idx)
        state = self.dirty_by_page.get(page_idx)
        if state is None:
            state = MaskDirtyState()
            self.dirty_by_page[page_idx] = state
        return state

    def mark_dirty(self, page_idx: int, key: str | None = None, *, toggle: bool = False) -> None:
        page_idx = int(page_idx)
        self.dirty_state(page_idx).mark(key, toggle=toggle)
        if callable(self.on_dirty):
            try:
                kind = f"mask:{key}" if key else "mask"
                if toggle:
                    kind = "mask:toggle"
                self.on_dirty(page_idx, kind)
            except Exception:
                pass

    def clear_dirty(self, page_idx: Optional[int] = None) -> None:
        if page_idx is None:
            self.dirty_by_page.clear()
        else:
            self.dirty_by_page.pop(int(page_idx), None)

    def get_mask(self, page_data: Dict[str, Any], *, mode_idx: int, mask_toggle_enabled: bool = False) -> Any:
        key = self.active_key(mode_idx, mask_toggle_enabled)
        if not key or not isinstance(page_data, dict):
            return None
        return page_data.get(key)

    def set_mask(self, page_data: Dict[str, Any], mask: Any, *, page_idx: int, mode_idx: int, mask_toggle_enabled: bool = False, key: str | None = None) -> Optional[str]:
        if not isinstance(page_data, dict):
            return None
        key = key or self.active_key(mode_idx, mask_toggle_enabled)
        if not key:
            return None
        page_data[key] = mask.copy() if isinstance(mask, np.ndarray) else mask
        page_data[f"{key}_dirty"] = True
        self.mark_dirty(page_idx, key)
        return key

    def set_mask_by_key(self, page_data: Dict[str, Any], key: str, mask: Any, *, page_idx: int) -> Optional[str]:
        if key not in MASK_KEYS or not isinstance(page_data, dict):
            return None
        page_data[key] = mask.copy() if isinstance(mask, np.ndarray) else mask
        page_data[f"{key}_dirty"] = True
        self.mark_dirty(page_idx, key)
        return key

    def load_missing_masks(self, page_data: Dict[str, Any], *, keys: Iterable[str] | None = None, loader: Optional[Callable[[Any], Any]] = None) -> List[str]:
        if not isinstance(page_data, dict) or not callable(loader):
            return []
        loaded: List[str] = []
        for key in tuple(keys or MASK_KEYS):
            if key not in MASK_KEYS:
                continue
            if page_data.get(key) is not None:
                continue
            path_key = f"{key}_path"
            mask = loader(page_data.get(path_key))
            if mask is not None:
                page_data[key] = mask
                loaded.append(key)
        return loaded

    def unload_saved_masks(self, page_data: Dict[str, Any], *, keys: Iterable[str] | None = None) -> List[str]:
        if not isinstance(page_data, dict):
            return []
        unloaded: List[str] = []
        for key in tuple(keys or MASK_KEYS):
            if key not in MASK_KEYS:
                continue
            # Only unload masks that have a saved backing file and are not dirty.
            if page_data.get(f"{key}_path") and not page_data.get(f"{key}_dirty"):
                if page_data.get(key) is not None:
                    page_data[key] = None
                    unloaded.append(key)
        return unloaded

    def capture_masks(self, page_data: Dict[str, Any], *, keys: Iterable[str] | None = None, include_toggle: bool = True) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if not isinstance(page_data, dict):
            return out
        for key in tuple(keys or MASK_KEYS):
            if key not in MASK_KEYS:
                continue
            value = page_data.get(key)
            out[key] = value.copy() if isinstance(value, np.ndarray) else value
            path_key = f"{key}_path"
            if page_data.get(path_key):
                out[path_key] = page_data.get(path_key)
        if include_toggle:
            out["mask_toggle_enabled"] = bool(page_data.get("mask_toggle_enabled", False))
        return out

    def restore_masks(self, page_data: Dict[str, Any], state: Dict[str, Any], *, page_idx: int) -> List[str]:
        if not isinstance(page_data, dict) or not isinstance(state, dict):
            return []
        changed: List[str] = []
        for key in MASK_KEYS:
            if key in state:
                value = state.get(key)
                page_data[key] = value.copy() if isinstance(value, np.ndarray) else value
                page_data[f"{key}_dirty"] = True
                changed.append(key)
            path_key = f"{key}_path"
            if path_key in state:
                page_data[path_key] = state.get(path_key)
        if "mask_toggle_enabled" in state:
            page_data["mask_toggle_enabled"] = bool(state.get("mask_toggle_enabled"))
            self.mark_dirty(page_idx, toggle=True)
        for key in changed:
            self.mark_dirty(page_idx, key)
        return changed

    def magic(self, page_idx: int) -> MagicWandRuntime:
        page_idx = int(page_idx)
        runtime = self.magic_by_page.get(page_idx)
        if runtime is None:
            runtime = MagicWandRuntime()
            self.magic_by_page[page_idx] = runtime
        return runtime

    def capture_magic(self, page_idx: int, *, active: bool = False, include_history: bool = True) -> Dict[str, Any]:
        return self.magic(page_idx).capture(active=active, include_history=include_history)

    def restore_magic(self, page_idx: int, state: Dict[str, Any] | None) -> MagicWandRuntime:
        runtime = self.magic(page_idx)
        runtime.restore(state)
        return runtime

    def push_magic_history(self, page_idx: int) -> None:
        self.magic(page_idx).push_history(self.max_magic_history)

    def undo_magic(self, page_idx: int) -> bool:
        return self.magic(page_idx).undo()

    def clear_magic(self, page_idx: int, *, clear_history: bool = True) -> None:
        self.magic(page_idx).clear(clear_history=clear_history)

    def set_magic_mask(self, page_idx: int, mask: Any, seeds: Optional[List[Tuple[int, int]]] = None, seed: Optional[Tuple[int, int]] = None) -> None:
        runtime = self.magic(page_idx)
        runtime.mask = mask.copy() if isinstance(mask, np.ndarray) else mask
        if seeds is not None:
            runtime.seeds = [tuple(x) for x in seeds]
        if seed is not None:
            runtime.seed = tuple(seed)
        elif runtime.seeds:
            runtime.seed = runtime.seeds[-1]

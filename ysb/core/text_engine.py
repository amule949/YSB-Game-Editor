from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Callable
import copy


RUNTIME_TRANSFORM_KEYS = ("_transform_mode", "_skew_mode", "_trapezoid_mode", "_arc_mode")

OBJECT_DISPLAY_PREFIXES = ("[객체] ", "[객체]", "[Object] ", "[Object]", "[OBJECT] ", "[OBJECT]")

def _strip_object_display_prefix(value: Any) -> str:
    text = str(value or "")
    changed = True
    while changed:
        changed = False
        left = text.lstrip()
        leading = text[:len(text) - len(left)]
        for prefix in OBJECT_DISPLAY_PREFIXES:
            if left.startswith(prefix):
                left = left[len(prefix):]
                text = leading + left
                changed = True
                break
    return text


def _strip_runtime_transform_keys(item: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(item) if isinstance(item, dict) else {}
    for key in RUNTIME_TRANSFORM_KEYS:
        out.pop(key, None)
    # [객체] is a table/display prefix only.  It must not enter real text data
    # through table editing, undo snapshots, or object->text restore.
    for text_key in ("text", "translated_text", "object_source_text"):
        if text_key in out:
            out[text_key] = _strip_object_display_prefix(out.get(text_key))
    return out

def _safe_id(value: Any) -> str:
    return str(value) if value is not None else ""


@dataclass
class TextDirtyState:
    ids: Set[str] = field(default_factory=set)
    fields: Set[str] = field(default_factory=set)

    def mark(self, ids: Iterable[Any] = (), fields: Iterable[str] = ()) -> None:
        for value in ids or []:
            sid = _safe_id(value)
            if sid:
                self.ids.add(sid)
        for field_name in fields or []:
            name = str(field_name or "").strip()
            if name:
                self.fields.add(name)

    def clear(self) -> None:
        self.ids.clear()
        self.fields.clear()


class YSBGextEngine:
    """Page-local text engine.

    This engine only handles text-line data for one page at a time. It never
    saves project.json, never touches package paths, and never loads images or
    masks. The UI can use it to create small diff-based undo records and to
    mutate the current page's text dictionaries without copying the whole page.
    """

    def __init__(self, *, on_dirty: Optional[Callable[[int, str], None]] = None):
        self.on_dirty = on_dirty
        self.dirty_by_page: Dict[int, TextDirtyState] = {}

    def dirty_state(self, page_idx: int) -> TextDirtyState:
        page_idx = int(page_idx)
        state = self.dirty_by_page.get(page_idx)
        if state is None:
            state = TextDirtyState()
            self.dirty_by_page[page_idx] = state
        return state

    def mark_dirty(self, page_idx: int, ids: Iterable[Any] = (), fields: Iterable[str] = ()) -> None:
        page_idx = int(page_idx)
        self.dirty_state(page_idx).mark(ids, fields)
        if callable(self.on_dirty):
            try:
                self.on_dirty(page_idx, "text")
            except Exception:
                pass

    def clear_dirty(self, page_idx: Optional[int] = None) -> None:
        if page_idx is None:
            self.dirty_by_page.clear()
            return
        self.dirty_by_page.pop(int(page_idx), None)

    @staticmethod
    def item_id(item: Dict[str, Any]) -> str:
        if not isinstance(item, dict):
            return ""
        return _safe_id(item.get("id"))

    @classmethod
    def snapshot_items(cls, data_list: List[Dict[str, Any]], ids: Optional[Iterable[Any]] = None, indexes: Optional[Iterable[int]] = None) -> List[Dict[str, Any]]:
        if not isinstance(data_list, list):
            return []
        id_set: Optional[Set[str]] = None
        if ids is not None:
            id_set = {_safe_id(x) for x in ids if _safe_id(x)}
        index_set: Optional[Set[int]] = None
        if indexes is not None:
            index_set = set()
            for raw in indexes:
                try:
                    index_set.add(int(raw))
                except Exception:
                    pass
        out: List[Dict[str, Any]] = []
        for idx, item in enumerate(data_list):
            if not isinstance(item, dict):
                continue
            if id_set is not None and cls.item_id(item) not in id_set:
                continue
            if index_set is not None and idx not in index_set:
                continue
            out.append(_strip_runtime_transform_keys(item))
        return out

    @classmethod
    def snapshot_from_scene_items(cls, scene_items: Iterable[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for obj in list(scene_items or []):
            data = getattr(obj, "data", None)
            if isinstance(data, dict):
                out.append(_strip_runtime_transform_keys(data))
        return out

    @classmethod
    def apply_snapshot(cls, data_list: List[Dict[str, Any]], snapshot: Iterable[Dict[str, Any]]) -> List[str]:
        if not isinstance(data_list, list):
            return []
        by_id = {cls.item_id(item): item for item in data_list if isinstance(item, dict) and cls.item_id(item)}
        changed: List[str] = []
        for saved in list(snapshot or []):
            if not isinstance(saved, dict):
                continue
            sid = cls.item_id(saved)
            if not sid:
                continue
            target = by_id.get(sid)
            if target is None:
                # If the line is gone, restore it to the end. This keeps undo
                # safe for deletion/reorder-ish text actions without touching masks.
                data_list.append(_strip_runtime_transform_keys(saved))
            else:
                target.clear()
                target.update(_strip_runtime_transform_keys(saved))
            changed.append(sid)
        return changed

    @classmethod
    def apply_fields(cls, data_list: List[Dict[str, Any]], ids: Iterable[Any], updates: Dict[str, Any]) -> List[str]:
        if not isinstance(data_list, list) or not isinstance(updates, dict):
            return []
        id_set = {_safe_id(x) for x in ids or [] if _safe_id(x)}
        changed: List[str] = []
        for item in data_list:
            if not isinstance(item, dict):
                continue
            sid = cls.item_id(item)
            if not sid or sid not in id_set:
                continue
            for key, value in updates.items():
                item[str(key)] = value
            changed.append(sid)
        return changed

    @classmethod
    def apply_field_by_index(cls, data_list: List[Dict[str, Any]], index: int, key: str, value: Any) -> Optional[str]:
        try:
            item = data_list[int(index)]
        except Exception:
            return None
        if not isinstance(item, dict):
            return None
        item[str(key)] = value
        return cls.item_id(item)


    @classmethod
    def ids_from_items(cls, items: Iterable[Dict[str, Any]]) -> List[str]:
        ids: List[str] = []
        for item in list(items or []):
            if not isinstance(item, dict):
                continue
            sid = cls.item_id(item)
            if sid:
                ids.append(sid)
        return ids

    def make_diff_record_for_items(self, *, data_list: List[Dict[str, Any]], page_idx: int, mode: int, reason: str, items: Iterable[Dict[str, Any]], fields: Iterable[str] = ()) -> Dict[str, Any]:
        ids = self.ids_from_items(items)
        before = self.snapshot_items(data_list, ids=ids)
        return self.make_diff_record(
            page_idx=page_idx,
            mode=mode,
            reason=reason,
            before_items=before,
            selected_ids=ids,
            fields=fields,
        )

    @classmethod
    def make_diff_record(cls, *, page_idx: int, mode: int, reason: str, before_items: Iterable[Dict[str, Any]], selected_ids: Iterable[Any] = (), fields: Iterable[str] = ()) -> Dict[str, Any]:
        ids = [_safe_id(x) for x in selected_ids or [] if _safe_id(x)]
        if not ids:
            ids = [cls.item_id(item) for item in before_items or [] if isinstance(item, dict) and cls.item_id(item)]
        return {
            "reason": str(reason or "텍스트 변경"),
            "page_idx": int(page_idx),
            "mode": int(mode),
            "text_diff_state": {
                "items": [_strip_runtime_transform_keys(x) for x in before_items or [] if isinstance(x, dict)],
                "ids": ids,
                "fields": [str(x) for x in fields or []],
            },
            "selected_ids": ids,
            "_undo_scope": "page",
        }

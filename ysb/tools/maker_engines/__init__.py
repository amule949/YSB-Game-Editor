from __future__ import annotations

from typing import Any, Dict

from .base import MakerEngineAdapter
from .mz import ADAPTER as MZ_ADAPTER
from .mv import ADAPTER as MV_ADAPTER


def normalize_engine(engine: str | None) -> str:
    value = str(engine or "").strip().lower()
    if value in {"mz", "rpg_maker_mz", "rpg maker mz"}:
        return "mz"
    if value in {"mv", "rpg_maker_mv", "rpg maker mv"}:
        return "mv"
    return "unknown_mv_mz" if "mv" in value or "mz" in value else "unknown"


def get_engine_adapter(engine: str | Dict[str, Any] | None) -> MakerEngineAdapter:
    if isinstance(engine, dict):
        engine = str(engine.get("engine") or "")
    value = normalize_engine(str(engine or ""))
    if value == "mz":
        return MZ_ADAPTER
    if value == "mv":
        return MV_ADAPTER
    # Unknown MV/MZ-compatible structures use MV's safer older defaults.  The
    # detector should normally resolve to MV or MZ before rendering.
    return MV_ADAPTER


def engine_module_metadata(engine: str | Dict[str, Any] | None) -> Dict[str, Any]:
    return get_engine_adapter(engine).metadata()


__all__ = [
    "MakerEngineAdapter",
    "normalize_engine",
    "get_engine_adapter",
    "engine_module_metadata",
]

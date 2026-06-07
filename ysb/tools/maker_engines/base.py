from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class MakerEngineAdapter:
    """Small engine-specific adapter for RPG Maker MV/MZ.

    UI/project code should not hard-code MV/MZ renderer rules in a single pile.
    The editor detects the engine once, stores the selected runtime module in
    maker_runtime_profile.json, then asks the adapter for engine-specific
    defaults and parsing hints.
    """

    engine: str
    engine_label: str
    runtime_module: str
    default_font_family: str
    windows_js_name: str
    has_builtin_name_window: bool
    show_text_name_parameter_index: int | None
    font_priority: str

    def runtime_defaults(self) -> Dict[str, Any]:
        raise NotImplementedError

    def metadata(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_label": self.engine_label,
            "runtime_module": self.runtime_module,
            "windows_js_name": self.windows_js_name,
            "default_font_family": self.default_font_family,
            "has_builtin_name_window": self.has_builtin_name_window,
            "show_text_name_parameter_index": self.show_text_name_parameter_index,
            "font_priority": self.font_priority,
        }

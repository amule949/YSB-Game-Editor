from __future__ import annotations

from typing import Any, Dict

from .base import MakerEngineAdapter


class MVEngineAdapter(MakerEngineAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine="mv",
            engine_label="RPG Maker MV",
            runtime_module="ysb.tools.maker_engines.mv",
            default_font_family="GameFont",
            windows_js_name="rpg_windows.js",
            has_builtin_name_window=False,
            show_text_name_parameter_index=None,
            font_priority="gamefont.css > fonts_folder > System.json fallback",
        )

    def runtime_defaults(self) -> Dict[str, Any]:
        # RPG Maker MV has no built-in name window in the same sense as MZ.
        # Name windows are commonly plugin-controlled, so keep the MV adapter
        # separate and avoid applying MZ formulas to it.
        return {
            "source": "rpg_windows.js defaults",
            "font_size": 28,
            "name_font_size": 28,
            "choice_font_size": 28,
            "line_height": 36,
            "message_lines": 4,
            "window_padding": 18,
            "item_padding": 6,
            "text_padding": 6,
            "outline_width": 4,
            "box_margin": 0,
            "message_margin": 0,
            "message_x": 0,
            "message_y": -1,
            "message_height_extra": 0,
            "name_padding_x": 18,
            "name_padding_y": 8,
            "name_min_width": 96,
            "name_min_height": 60,
            "name_overlap": 0,
            "window_opacity": 205,
            "has_builtin_name_window": False,
        }


ADAPTER = MVEngineAdapter()

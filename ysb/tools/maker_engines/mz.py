from __future__ import annotations

from typing import Any, Dict

from .base import MakerEngineAdapter


class MZEngineAdapter(MakerEngineAdapter):
    def __init__(self) -> None:
        super().__init__(
            engine="mz",
            engine_label="RPG Maker MZ",
            runtime_module="ysb.tools.maker_engines.mz",
            default_font_family="rmmz-mainfont",
            windows_js_name="rmmz_windows.js",
            has_builtin_name_window=True,
            show_text_name_parameter_index=4,
            font_priority="System.json advanced.mainFontFilename > gamefont.css > fonts_folder > fallbackFonts",
        )

    def runtime_defaults(self) -> Dict[str, Any]:
        # Mirrors stable RPG Maker MZ Window_Base/Window_Message/Window_NameBox
        # defaults.  Game/plugin values may override these later.
        return {
            "source": "rmmz_windows.js defaults",
            "font_size": 28,
            "name_font_size": 28,
            "choice_font_size": 28,
            "line_height": 36,
            "message_lines": 4,
            "window_padding": 12,
            "item_padding": 8,
            "text_padding": 6,
            "outline_width": 3,
            "box_margin": 4,
            "message_margin": 4,
            "message_x": 4,
            "message_y": -1,
            "message_height_extra": 8,
            "name_padding_x": 20,
            "name_padding_y": 12,
            "name_min_width": 96,
            "name_min_height": 60,
            "name_overlap": 0,
            "window_opacity": 205,
            "has_builtin_name_window": True,
        }


ADAPTER = MZEngineAdapter()

# -*- coding: utf-8 -*-
"""Current YSB Game Editor build-mode selector.

쯔꾸르붕이는 API 번역 단일판으로 배포한다.
예전 설정/환경변수에 lite/local 값이 남아 있어도 모두 현재 단일판(game)으로 정규화한다.
"""

from __future__ import annotations

from dataclasses import dataclass
import os

from ysb.version_info import (
    APP_VERSION,
    LITE_APP_NAME_EN,
    LITE_APP_NAME_KO,
    LITE_MAIN_EXE_NAME,
    UPDATE_IGNORE_KEY_LITE,
    VERSION_JSON_URL_LITE,
)


@dataclass(frozen=True)
class EditionInfo:
    key: str
    label: str
    app_version: str
    app_name_ko: str
    app_name_en: str
    main_exe_name: str
    version_json_url: str
    update_ignore_key: str
    onefile: bool


GAME_EDITION = EditionInfo(
    key="game",
    label="",
    app_version=APP_VERSION,
    app_name_ko=LITE_APP_NAME_KO,
    app_name_en=LITE_APP_NAME_EN,
    main_exe_name=LITE_MAIN_EXE_NAME,
    version_json_url=VERSION_JSON_URL_LITE,
    update_ignore_key=UPDATE_IGNORE_KEY_LITE,
    onefile=True,
)

_EDITION_TABLE: dict[str, EditionInfo] = {
    "game": GAME_EDITION,
    # Backward-compatible aliases. They all point to the single current app.
    "api": GAME_EDITION,
    "lite": GAME_EDITION,
    "local": GAME_EDITION,
}

_ENV_KEY = "YSB_TOOL_EDITION"
_CURRENT_EDITION: str | None = None


def normalize_edition(value: str | None) -> str:
    return "game"


def set_current_edition(value: str | None) -> EditionInfo:
    global _CURRENT_EDITION
    key = normalize_edition(value)
    _CURRENT_EDITION = key
    os.environ[_ENV_KEY] = key
    return _EDITION_TABLE[key]


def get_current_edition_key() -> str:
    if _CURRENT_EDITION:
        return _CURRENT_EDITION
    return normalize_edition(os.environ.get(_ENV_KEY))


def get_current_edition() -> EditionInfo:
    return _EDITION_TABLE[get_current_edition_key()]


def is_lite_edition() -> bool:
    # Compatibility name: old code uses this to mean "not Local/OCR".
    return True


def is_local_edition() -> bool:
    return False

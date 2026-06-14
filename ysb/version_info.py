# -*- coding: utf-8 -*-
"""Central version/brand metadata for YSB Game Editor.

Edit this file first when releasing a new version.
The app UI, edition metadata, launcher candidates, and PyInstaller build names
read from this single source of truth.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Release version
# ---------------------------------------------------------------------------
# Change these numbers only, then rebuild.
VERSION_MAJOR = 1
VERSION_MINOR = 1
VERSION_PATCH = 0
VERSION_BUILD = 0

VERSION_TEXT = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
APP_VERSION = f"v{VERSION_TEXT}"
WINDOWS_VERSION_STRING = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}.{VERSION_BUILD}"
WINDOWS_VERSION_TUPLE = (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH, VERSION_BUILD)

# ---------------------------------------------------------------------------
# Product / company metadata
# ---------------------------------------------------------------------------
COMPANY_NAME = "Zerostress8"
PRODUCT_NAME = "YSB Game Editor"
APP_FAMILY_ID = "ZEROSTRESS8_YSB_GAME_EDITOR"

APP_TITLE_KO = "쯔꾸르붕이"
APP_TITLE_EN = "YSB Game Editor"
APP_TITLE_FULL = "YSB Game Editor / 쯔꾸르붕이"

SUPPORT_EMAIL = "ysbtool.support@gmail.com"
COPYRIGHT_TEXT = "© 2026 amule949"

# ---------------------------------------------------------------------------
# Build / release names
# ---------------------------------------------------------------------------
# 쯔꾸르붕이는 이제 API 번역 단일판으로 배포한다.
# 예전 Lite/Local 분기와 호환되는 상수명은 남기되, 사용자에게 보이는 이름에는
# Lite/Local 문구를 붙이지 않는다.
LITE_EDITION_LABEL = ""
LOCAL_EDITION_LABEL = ""

LITE_APP_NAME_KO = APP_TITLE_KO
LOCAL_APP_NAME_KO = APP_TITLE_KO
LITE_APP_NAME_EN = APP_TITLE_EN
LOCAL_APP_NAME_EN = APP_TITLE_EN

LITE_MAIN_EXE_NAME = f"{APP_TITLE_KO} {APP_VERSION}"
LOCAL_MAIN_EXE_NAME = f"{APP_TITLE_KO} {APP_VERSION}"
LAUNCHER_EXE_NAME = "YSB_Game_Editor_Launcher"

# Build output folder. The build script leaves only this *_package folder in dist/.
LITE_PACKAGE_FOLDER_NAME = f"{LITE_MAIN_EXE_NAME}_package"
LOCAL_PACKAGE_FOLDER_NAME = LITE_PACKAGE_FOLDER_NAME

# Zip names are kept only for compatibility with old helpers. The current build
# tool creates a package folder, not a ZIP.
LITE_PACKAGE_ZIP_NAME = f"YSB_Game_Editor_{APP_VERSION}.zip"
LOCAL_PACKAGE_ZIP_NAME = LITE_PACKAGE_ZIP_NAME
BUILD_LOG_FILE_NAME = f"build_log_{APP_VERSION}.txt"

VERSION_JSON_URL_LITE = "https://ysb-tool.com/game_editor/version.json"
VERSION_JSON_URL_LOCAL = "https://ysb-tool.com/game_editor/version_local.json"

UPDATE_IGNORE_KEY_LITE = "ignored_update_version_lite"
UPDATE_IGNORE_KEY_LOCAL = "ignored_update_version_local"

YSB_ROLE_MAIN = "YSB_MAIN"
YSB_ROLE_LAUNCHER = "YSB_LAUNCHER"


def app_name_ko(edition: str) -> str:
    return LOCAL_APP_NAME_KO if str(edition).lower() == "local" else LITE_APP_NAME_KO


def app_name_en(edition: str) -> str:
    return LOCAL_APP_NAME_EN if str(edition).lower() == "local" else LITE_APP_NAME_EN


def main_exe_name(edition: str) -> str:
    return LOCAL_MAIN_EXE_NAME if str(edition).lower() == "local" else LITE_MAIN_EXE_NAME


def package_folder_name(edition: str) -> str:
    return LOCAL_PACKAGE_FOLDER_NAME if str(edition).lower() == "local" else LITE_PACKAGE_FOLDER_NAME


def package_zip_name(edition: str) -> str:
    return LOCAL_PACKAGE_ZIP_NAME if str(edition).lower() == "local" else LITE_PACKAGE_ZIP_NAME


def windows_original_filename(edition: str) -> str:
    return "YSB_Game_Editor.exe" if str(edition).lower() == "local" else "YSB_Game_Editor.exe"


def main_exe_candidates() -> list[str]:
    """Candidate main executable names for the shared launcher."""
    return [
        f"{LITE_MAIN_EXE_NAME}.exe",
        f"{LOCAL_MAIN_EXE_NAME}.exe",
        f"YSB_Tool_Lite_{APP_VERSION}.exe",
        f"YSB_Tool_Local_{APP_VERSION}.exe",
        "쯔꾸르붕이 v2.0.1.exe",
        "쯔꾸르붕이 v1.8.1.exe",
        "쯔꾸르붕이.exe",
        "YSB_Tool_v2.0.1.exe",
        "YSB_Tool_v1.8.1.exe",
        "YSB_Game_Editor.exe",
    ]

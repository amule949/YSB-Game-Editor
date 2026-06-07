# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main(argv: list[str]) -> int:
    target = argv[1].lower().strip() if len(argv) >= 2 else "game"
    if target != "game":
        raise ValueError("쯔꾸르붕이는 game 단일 빌드만 지원합니다. Usage: build_probe.py game")

    required = [
        PROJECT_ROOT / "main.py",
        PROJECT_ROOT / "ysb" / "__init__.py",
        PROJECT_ROOT / "ysb" / "ui" / "main_window.py",
        PROJECT_ROOT / "ysb" / "version_info.py",
        PROJECT_ROOT / "assets" / "ysb_splash.png",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Required file(s) missing:\n" + "\n".join(missing))

    from ysb.version_info import APP_VERSION, LITE_PACKAGE_FOLDER_NAME
    print(f"쯔꾸르붕이 {APP_VERSION} build probe OK")
    print(f"Package folder: {LITE_PACKAGE_FOLDER_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

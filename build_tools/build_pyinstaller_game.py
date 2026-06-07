# -*- coding: utf-8 -*-
from __future__ import annotations

from build_pyinstaller_core import build_package, log


if __name__ == "__main__":
    try:
        raise SystemExit(build_package())
    except Exception as exc:
        log("")
        log(f"ERROR: {exc}")
        raise SystemExit(1)

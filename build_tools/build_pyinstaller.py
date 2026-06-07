# -*- coding: utf-8 -*-
"""Deprecated direct build entry.

Use build_tools/build_game_exe.bat instead.
"""
from __future__ import annotations


def main() -> int:
    print("This direct build driver is deprecated.")
    print("Use this driver instead:")
    print("  build_tools\\build_game_exe.bat")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

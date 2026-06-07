#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight Undo policy guard for YSB Translator patches.

This script is intentionally conservative.  It does not fail on legacy calls
inside MainWindowHistoryMixin / UndoManager, but warns when feature files start
touching undo stacks or legacy append/boundary functions directly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_LEGACY_FILES = {
    Path("ysb/ui/main_window_history_mixin.py"),
    Path("ysb/core/undo_manager.py"),
    Path("ysb/core/undo_restore_engine.py"),
    Path("ysb/core/undo_record_validator.py"),
    Path("ysb/core/undo_records.py"),
    Path("ysb/core/undo_policies.py"),
    Path("ysb/ui/main_window.py"),  # stack field initialization only; stage 3 will move ownership.
    Path("tools/check_undo_policy.py"),
}

DANGEROUS_PATTERNS = [
    "append_page_undo_record(",
    "append_project_undo_record(",
    "append_page_redo_record(",
    "append_project_redo_record(",
    "break_undo_chain(",
    "clear_current_page_undo_stack(",
    "clear_all_page_undo_stacks(",
    "page_undo_stacks",
    "page_redo_stacks",
    "project_undo_stack",
    "project_redo_stack",
    "view.history.append",
    "view.redo_history.append",
    "restore_project_history_record(",
    "restore_page_view_history_record(",
]

PREFERRED_PATTERNS = [
    "undo_push_page(",
    "undo_push_project(",
    "undo_push_view(",
    "undo_break_boundary(",
    "undo_text_checkpoint(",
    "get_undo_manager(",
    "get_undo_record_factory(",
    "validate_record(",
    "UndoRecordValidator",
    "undo_restore_engine",
]


def iter_py_files(root: Path):
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if any(part in {"__pycache__", ".git", ".venv", "venv"} for part in rel.parts):
            continue
        yield path, rel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT), help="project root")
    parser.add_argument("--strict", action="store_true", help="return non-zero on warnings")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    warnings: list[str] = []
    preferred_hits = 0
    for path, rel in iter_py_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if rel not in ALLOWED_LEGACY_FILES:
            for pat in DANGEROUS_PATTERNS:
                if pat in text:
                    warnings.append(f"{rel}: direct undo access pattern found: {pat}")
        for pat in PREFERRED_PATTERNS:
            if pat in text:
                preferred_hits += text.count(pat)

    print("Undo policy check")
    print(f"- preferred UndoManager/factory hits: {preferred_hits}")
    if warnings:
        print(f"- warnings: {len(warnings)}")
        for msg in warnings:
            print("  WARN", msg)
    else:
        print("- warnings: 0")
    return 1 if warnings and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())

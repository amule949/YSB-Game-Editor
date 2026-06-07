# Core helpers for YSB Game Editor.
# Undo stage-2 keeps stack storage in MainWindowHistoryMixin but centralizes
# gateway, policy, and record construction in ysb.core.

# Undo restore execution engine is imported lazily by YSBUndoManager to avoid UI cycles.
# Undo record validation helpers live in ysb.core.undo_record_validator.

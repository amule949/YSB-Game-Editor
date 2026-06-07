"""YSB Tool edition support.

The existing ysb package remains the common code area.
Edition-specific behavior is selected by entry point/build script.
"""

from .current import (
    EditionInfo,
    get_current_edition,
    get_current_edition_key,
    set_current_edition,
    is_lite_edition,
    is_local_edition,
)

__all__ = [
    "EditionInfo",
    "get_current_edition",
    "get_current_edition_key",
    "set_current_edition",
    "is_lite_edition",
    "is_local_edition",
]

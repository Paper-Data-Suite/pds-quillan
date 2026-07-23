"""Cross-version filesystem path safety helpers."""

from __future__ import annotations

import os
from pathlib import Path
import stat


def is_link_like(path: Path) -> bool:
    """Return whether *path* is a symlink, junction, or Windows reparse point."""
    if path.is_symlink():
        return True

    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True

    if os.name != "nt":
        return False
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(attributes & reparse_point)


__all__ = ["is_link_like"]

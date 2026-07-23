"""Cross-version path-safety regression tests."""

from types import SimpleNamespace
from typing import Any, cast
import stat

import pytest

import quillan._path_safety as path_safety


class _LegacyWindowsPath:
    """Path-like test double for Python versions without Path.is_junction()."""

    def is_symlink(self) -> bool:
        return False


def test_windows_reparse_point_is_link_like_without_path_is_junction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("quillan._path_safety.os.name", "nt")
    monkeypatch.setattr(
        "quillan._path_safety.os.lstat",
        lambda _path: SimpleNamespace(
            st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
        ),
    )

    legacy_path = cast(Any, _LegacyWindowsPath())
    assert path_safety.is_link_like(legacy_path)

"""Visual evidence archive naming contract."""

from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from scripts.run_visual_acceptance import _write_visual_archive


def test_visual_archive_has_unique_extractable_member_paths(tmp_path: Path) -> None:
    sources: list[tuple[str, Path]] = []
    for name in (
        "contact-sheet.png",
        "one-student-one-page/page-01.png",
        "one-student-one-page/printable_response_pages.pdf",
        "several-students-one-page/page-01.png",
        "several-students-one-page/printable_response_pages.pdf",
    ):
        source = tmp_path / "sources" / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(name.encode())
        sources.append((name, source))
    archive_path = tmp_path / "visual.zip"
    result = _write_visual_archive(archive_path, sources)
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        extraction = tmp_path / "extracted"
        archive.extractall(extraction)
    assert names == [name for name, _ in sources]
    assert len(names) == len(set(names)) == result["unique_member_count"]
    assert all((extraction / name).read_bytes() == source.read_bytes() for name, source in sources)


def test_visual_archive_rejects_duplicate_member_names(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    with pytest.raises(ValueError, match="must be unique"):
        _write_visual_archive(
            tmp_path / "duplicate.zip",
            [("case/page-01.png", first), ("case/page-01.png", second)],
        )

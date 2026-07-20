"""Tests for safely opening generated Quillan outputs."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.generated_output_opening as opening
from quillan.generated_output_opening import (
    GeneratedOutputOpeningError,
    OpenedGeneratedOutput,
)


def _generated_pdf(workspace_root: Path) -> Path:
    output_path = (
        workspace_root
        / "classes"
        / "english10_p2"
        / "modules"
        / "quillan"
        / "work"
        / "essay_01"
        / "templates"
        / "printable_response_pages.pdf"
    )
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"%PDF synthetic")
    return output_path


def test_open_generated_output_file_opens_valid_file_inside_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = _generated_pdf(tmp_path)
    calls: list[Path] = []

    def open_local_path(path: str | Path) -> Path:
        calls.append(Path(path))
        return Path(path)

    monkeypatch.setattr(opening, "open_local_path", open_local_path)

    opened = opening.open_generated_output_file(tmp_path, output_path)

    assert calls == [output_path]
    assert opened == OpenedGeneratedOutput(
        path=output_path,
        relative_path=(
            "classes/english10_p2/modules/quillan/work/essay_01/templates/"
            "printable_response_pages.pdf"
        ),
    )


def test_open_generated_output_folder_opens_valid_containing_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = _generated_pdf(tmp_path)
    calls: list[Path] = []

    def open_local_path(path: str | Path) -> Path:
        calls.append(Path(path))
        return Path(path)

    monkeypatch.setattr(opening, "open_local_path", open_local_path)

    opened = opening.open_generated_output_folder(tmp_path, output_path)

    assert calls == [output_path.parent]
    assert opened == OpenedGeneratedOutput(
        path=output_path.parent,
        relative_path="classes/english10_p2/modules/quillan/work/essay_01/templates",
    )


def test_open_generated_output_accepts_workspace_relative_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = _generated_pdf(tmp_path)
    relative_path = output_path.relative_to(tmp_path)
    calls: list[Path] = []

    def open_local_path(path: str | Path) -> Path:
        calls.append(Path(path))
        return Path(path)

    monkeypatch.setattr(opening, "open_local_path", open_local_path)

    opened = opening.open_generated_output_file(tmp_path, relative_path)

    assert calls == [output_path]
    assert opened.path == output_path


def test_open_generated_output_file_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(GeneratedOutputOpeningError, match="does not exist"):
        opening.open_generated_output_file(tmp_path, "missing.pdf")


def test_open_generated_output_file_rejects_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "classes"
    output_path.mkdir()

    with pytest.raises(GeneratedOutputOpeningError, match="must identify a file"):
        opening.open_generated_output_file(tmp_path, output_path)


def test_open_generated_output_folder_rejects_missing_output(
    tmp_path: Path,
) -> None:
    with pytest.raises(GeneratedOutputOpeningError, match="does not exist"):
        opening.open_generated_output_folder(tmp_path, "missing.pdf")


def test_open_generated_output_rejects_outside_workspace(tmp_path: Path) -> None:
    outside_path = tmp_path.parent / "outside.pdf"
    outside_path.write_bytes(b"%PDF outside")

    with pytest.raises(GeneratedOutputOpeningError, match="inside"):
        opening.open_generated_output_file(tmp_path, outside_path)


@pytest.mark.parametrize(
    "output_path",
    [
        "http://example.test/packet.pdf",
        "https://example.test/packet.pdf",
        "file:///tmp/packet.pdf",
    ],
)
def test_open_generated_output_rejects_url_like_paths(
    tmp_path: Path,
    output_path: str,
) -> None:
    with pytest.raises(GeneratedOutputOpeningError, match="not a URL"):
        opening.open_generated_output_file(tmp_path, output_path)


def test_open_generated_output_rejects_parent_traversal_outside_workspace(
    tmp_path: Path,
) -> None:
    outside_path = tmp_path.parent / "outside.pdf"
    outside_path.write_bytes(b"%PDF outside")

    with pytest.raises(GeneratedOutputOpeningError, match="inside"):
        opening.open_generated_output_file(tmp_path, "../outside.pdf")

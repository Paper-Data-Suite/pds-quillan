"""Tests for removed legacy Review Materials menu surfaces."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from quillan.cli import main
from quillan.review_materials_menu import launch_review_materials_menu


def _menu_input(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str],
) -> None:
    response_iterator: Iterator[str] = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(response_iterator)
        except StopIteration as error:
            raise AssertionError(
                "Menu requested more input than the test provided."
            ) from error

    monkeypatch.setattr("builtins.input", fake_input)


def _file_tree(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
    entries: list[tuple[str, str, bytes | None]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            entries.append(("file", relative, path.read_bytes()))
        elif path.is_dir():
            entries.append(("dir", relative, None))
    return tuple(entries)


def test_main_menu_excludes_review_materials_and_exits_cleanly(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "2. Review Student Work" in output
    assert "4. Workspace Settings" in output
    assert "5. Help" in output
    assert "Q. Quit" in output
    assert "Review Materials" not in output
    assert "Goodbye." in output


def test_review_student_work_menu_excludes_review_materials(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["2", "3", "6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Review Student Work" in output
    assert "1. Assignment Review Actions" in output
    assert "2. Scan Intake / Route Paper Responses" in output
    assert "B. Back" in output
    assert "M. Main Menu" in output
    assert "Q. Quit" in output
    assert "Manage Review Materials" not in output
    assert "Comment Banks" not in output
    assert "Tag Banks" not in output
    assert "Rubrics / Scoring Profiles" not in output


def test_direct_review_materials_menu_is_disabled(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["x", "", "1"])

    assert launch_review_materials_menu() == 0

    output = capsys.readouterr().out
    assert "Review Materials" in output
    assert "Legacy generic comment-bank, tag-bank, and rubric workflows" in output
    assert "B. Back" in output
    assert "Comment Banks" not in output
    assert "Tag Banks" not in output
    assert "Starter Materials" not in output
    assert "Invalid selection. Please choose a listed option, B, M, or Q." in output


def test_review_materials_menu_has_no_workspace_side_effects(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classes = tmp_path / "classes"
    scans = tmp_path / "scans"
    scans_inbox = tmp_path / "scans_inbox"
    standards = tmp_path / "shared" / "standards"
    for folder in (classes, scans, scans_inbox, standards):
        folder.mkdir(parents=True)
        (folder / "existing.txt").write_text("keep", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    before = _file_tree(tmp_path)
    _menu_input(monkeypatch, ["1"])

    assert launch_review_materials_menu() == 0

    capsys.readouterr()
    assert _file_tree(tmp_path) == before
    assert not (tmp_path / "shared" / "comment_banks").exists()
    assert not (tmp_path / "shared" / "tag_banks").exists()
    assert not (tmp_path / "shared" / "rubrics").exists()
    assert not list(tmp_path.rglob("review.json"))
    assert not list(tmp_path.rglob("submission.json"))
    assert not list(tmp_path.rglob("exports"))

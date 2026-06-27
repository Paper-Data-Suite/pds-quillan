"""Tests for the teacher-facing Review Materials menu shell."""

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


def test_main_menu_includes_review_materials_and_exits_cleanly(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["9"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "5. Review Student Work" in output
    assert "6. Review Materials" in output
    assert "7. Workspace Settings" in output
    assert "8. Help" in output
    assert "9. Exit" in output
    assert "Goodbye." in output


def test_main_menu_invalid_selection_uses_new_range(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["bad", "", "9"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Invalid selection. Please enter a number from 1 to 9." in output


def test_review_materials_menu_navigation_returns_to_main_menu(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["6", "5", "9"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Review Materials" in output
    assert (
        "Reusable review materials help teachers prepare comments, tags, "
        "and scoring tools before reviewing student work."
    ) in output
    assert "1. Comment Banks" in output
    assert "2. Tag Banks" in output
    assert "3. Rubrics / Scoring Profiles" in output
    assert "4. Starter Materials" in output
    assert "5. Back" in output
    assert "Goodbye." in output


@pytest.mark.parametrize(
    ("choice", "header", "future_issue", "path_text"),
    [
        ("2", "Tag Banks", "#166", "shared/tag_banks/"),
        ("4", "Starter Materials", "#169", ""),
    ],
)
def test_review_materials_informational_screens_return_safely(
    choice: str,
    header: str,
    future_issue: str,
    path_text: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, [choice, "", "5"])

    assert launch_review_materials_menu() == 0

    output = capsys.readouterr().out
    assert header in output
    assert future_issue in output
    assert "No files were changed." in output
    if path_text:
        assert path_text in output


def test_review_materials_rubrics_opens_submenu(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["3", "7", "5"])

    assert launch_review_materials_menu() == 0

    output = capsys.readouterr().out
    assert "Rubrics / Scoring Profiles" in output
    assert "1. Create rubric / scoring profile" in output
    assert "6. Validate rubric / scoring profile" in output
    assert "7. Back" in output


def test_review_materials_comment_banks_opens_submenu(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["1", "7", "5"])

    assert launch_review_materials_menu() == 0

    output = capsys.readouterr().out
    assert "Comment banks store reusable teacher-authored feedback comments." in output
    assert "1. Create comment bank" in output
    assert "6. Validate comment bank" in output
    assert "7. Back" in output


def test_review_materials_invalid_selection_is_helpful(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["x", "", "5"])

    assert launch_review_materials_menu() == 0

    output = capsys.readouterr().out
    assert "Invalid selection. Please enter a number from 1 to 5." in output


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
    _menu_input(
        monkeypatch,
        ["6", "1", "7", "2", "", "3", "", "4", "", "5", "9"],
    )

    assert main(["menu"]) == 0

    capsys.readouterr()
    assert _file_tree(tmp_path) == before
    assert not (tmp_path / "shared" / "comment_banks").exists()
    assert not (tmp_path / "shared" / "tag_banks").exists()
    assert not (tmp_path / "shared" / "rubrics").exists()
    assert not list(tmp_path.rglob("review.json"))
    assert not list(tmp_path.rglob("submission.json"))
    assert not list(tmp_path.rglob("exports"))

"""Issue #383 menu integration tests for the deterministic review work queue."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.menu_navigation import QuitQuillan, ReturnToMainMenu
import quillan.review_menu as review_menu
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    SECOND_STUDENT_ID,
    _write_workspace,
)


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def _inputs(monkeypatch: pytest.MonkeyPatch, responses: tuple[str, ...]) -> None:
    iterator = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration as error:
            raise AssertionError("Menu requested more input than supplied.") from error

    monkeypatch.setattr("builtins.input", fake_input)


def test_queue_screen_is_roster_ordered_refreshable_and_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    before = _snapshot(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("r", "b"))

    review_menu._menu_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    output = capsys.readouterr().out
    assert output.count("Review Work Queue") == 2
    assert output.count("Active context") == 2
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID} - Synthetic Essay" in output
    assert "Complete: 0 / 2" in output
    assert "Needs work: 2" in output
    first = f"1. Avery Rivera ({STUDENT_ID}) — minimum requirements pending"
    second = f"2. Mina Patel ({SECOND_STUDENT_ID}) — no submission"
    assert first in output
    assert second in output
    assert output.index(first) < output.index(second)
    assert "R. Refresh" in output
    assert "Next student" not in output
    assert "Previous student" not in output
    assert "Continue Review" not in output
    assert _snapshot(tmp_path) == before


def test_student_picker_uses_same_queue_category_without_losing_submission_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    dashboard = review_menu._load_review_dashboard(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert dashboard is not None
    before = _snapshot(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("b",))

    selected = review_menu._prompt_student_id(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        dashboard,
    )

    assert selected is None
    output = capsys.readouterr().out
    assert (
        f"1. Avery Rivera ({STUDENT_ID}): "
        "unreviewed; manifest exists; evidence files=1; "
        "work=minimum requirements pending"
    ) in output
    assert (
        f"2. Mina Patel ({SECOND_STUDENT_ID}): "
        "no manifest; no routed evidence; work=no submission"
    ) in output
    assert _snapshot(tmp_path) == before


def test_assignment_review_actions_add_queue_without_renumbering_existing_actions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("7", "b", "b"))

    assert review_menu._launch_assignment_review_actions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ) == 0

    output = capsys.readouterr().out
    for expected in (
        "1. Select student/submission",
        "2. View submission status",
        "3. Review scan problems",
        "4. Export reports",
        "5. View full diagnostic dashboard",
        "6. Refresh",
        "7. View review work queue",
    ):
        assert expected in output
    assert "Review Work Queue" in output


def test_queue_screen_main_menu_uses_existing_navigation_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("m",))

    with pytest.raises(ReturnToMainMenu):
        review_menu._menu_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)


def test_queue_screen_quit_uses_existing_navigation_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("q",))

    with pytest.raises(QuitQuillan):
        review_menu._menu_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)

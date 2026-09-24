"""Focused Slice 1 tests for Quillan issue #386 compact review UX."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import quillan.review_menu as review_menu
from quillan.plain_paper_submission import create_plain_paper_submission
from quillan.review_student_navigation import (
    ReviewStudentNavigationError,
    build_review_student_navigation,
)
from tests.menu_screen_recorder import MenuScreenRecorder
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    SECOND_STUDENT_ID,
    STUDENT_ID,
    _write_workspace,
)


def _prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)


def _inputs(monkeypatch: pytest.MonkeyPatch, responses: tuple[str, ...]) -> None:
    iterator = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration as error:
            raise AssertionError("Menu requested more input than supplied.") from error

    monkeypatch.setattr("builtins.input", fake_input)


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def test_review_ready_root_prioritizes_compact_routine_actions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    for expected in (
        "Position: 1 of 2",
        "Work state: minimum requirements pending",
        "Students needing work: 2",
        "O. Open Evidence",
        "C. Continue Review — Review minimum requirements",
        "E. Export Feedback",
        f"N. Next Student — Mina Patel ({SECOND_STUDENT_ID})",
        "A. Advanced Actions",
        "P. Previous Student — none (first roster student)",
        f"W. Next Student Needing Review — Mina Patel ({SECOND_STUDENT_ID})",
        "B. Back",
        "M. Main Menu",
        "Q. Quit",
    ):
        assert expected in output

    for old_action in (
        "1. Open submission evidence",
        "2. View current review details",
        "3. Review minimum requirements",
        "4. Review units and Focus Standard observations",
        "5. Overall Focus Standard ratings",
        "6. Compose Focus Standard feedback",
        "7. Manage submission pages",
        "8. Add teacher note",
        "9. Update review workflow state",
        "10. Export student feedback",
        "11. Refresh summary",
    ):
        assert old_action not in output
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize(
    ("choice", "handler_name", "requires_pause"),
    (
        ("o", "_open_submission_evidence", True),
        ("e", "_menu_export_student_feedback", True),
        ("a", "_menu_advanced_review_actions", False),
    ),
)
def test_compact_primary_actions_route_existing_exact_student_workflows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    choice: str,
    handler_name: str,
    requires_pause: bool,
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    calls: list[tuple[str, str, str, str]] = []

    def record(
        _root: Path,
        class_id: str,
        assignment_id: str,
        student_id: str,
    ) -> None:
        calls.append((handler_name, class_id, assignment_id, student_id))

    monkeypatch.setattr(review_menu, handler_name, record)
    responses = (choice, "", "b") if requires_pause else (choice, "b")
    _inputs(monkeypatch, responses)

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0
    assert calls == [(handler_name, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)]
    assert _snapshot(tmp_path) == before


def test_compact_next_student_keeps_assignment_context_and_rebuilds_student_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    _inputs(monkeypatch, ("n", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert f"Student: Avery Rivera ({STUDENT_ID})" in output
    assert f"Student: Mina Patel ({SECOND_STUDENT_ID})" in output
    assert "Position: 1 of 2" in output
    assert "Position: 2 of 2" in output
    assert "C. Continue Review — Review minimum requirements" in output
    assert "C. Continue Review — unavailable (no reviewable submission)" in output
    assert _snapshot(tmp_path) == before


def test_advanced_actions_preserve_all_less_common_direct_workflows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    _inputs(monkeypatch, ("b",))

    review_menu._menu_advanced_review_actions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )

    output = capsys.readouterr().out
    assert "Advanced Review Actions" in output
    assert f"Student: Avery Rivera ({STUDENT_ID})" in output
    for expected in (
        "1. View current review details",
        "2. Review minimum requirements",
        "3. Review units and Focus Standard observations",
        "4. Overall Focus Standard ratings",
        "5. Compose Focus Standard feedback",
        "6. Manage submission pages",
        "7. Add teacher note",
        "8. Update review workflow state",
        "9. Refresh summary",
        "B. Back",
        "M. Main Menu",
        "Q. Quit",
    ):
        assert expected in output


@pytest.mark.parametrize(
    ("choice", "handler_name", "requires_pause"),
    (
        ("1", "_menu_view_current_review_details", True),
        ("2", "_menu_review_minimum_requirements", False),
        ("3", "_menu_review_unit_observations", False),
        ("4", "_menu_overall_focus_standard_ratings", False),
        ("5", "_menu_compose_focus_standard_feedback", False),
        ("6", "_menu_manage_submission_pages", True),
        ("7", "_menu_add_review_note", True),
        ("8", "_menu_update_review_workflow_state", True),
    ),
)
def test_advanced_action_dispatch_reuses_existing_exact_student_handler_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    choice: str,
    handler_name: str,
    requires_pause: bool,
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    calls: list[tuple[str, str, str]] = []

    def record(
        _root: Path,
        class_id: str,
        assignment_id: str,
        student_id: str,
    ) -> None:
        calls.append((class_id, assignment_id, student_id))

    monkeypatch.setattr(review_menu, handler_name, record)
    _inputs(monkeypatch, (choice, "") if requires_pause else (choice,))

    review_menu._menu_advanced_review_actions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )

    assert calls == [(CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)]
    assert _snapshot(tmp_path) == before


def test_no_submission_remains_explicit_recovery_screen_not_compact_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "No digital submission evidence has been found for this student." in output
    assert "Create plain-paper submission for this student" in output
    assert "C. Continue Review — unavailable (no reviewable submission)" in output
    assert "O. Open Evidence" not in output
    assert "E. Export Feedback" not in output
    assert "A. Advanced Actions" not in output


def test_compact_review_root_has_recorder_backed_task_hierarchy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    recorder = MenuScreenRecorder(["b"])
    recorder.install(monkeypatch)

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    screens = recorder.screens(output)
    roots = [screen.output for screen in screens if "Selected Student Review" in screen.output]
    assert len(roots) == 1
    root = roots[0]
    for expected in (
        "O. Open Evidence",
        "C. Continue Review — Review minimum requirements",
        "E. Export Feedback",
        f"N. Next Student — Mina Patel ({SECOND_STUDENT_ID})",
        "A. Advanced Actions",
        "P. Previous Student — none (first roster student)",
        f"W. Next Student Needing Review — Mina Patel ({SECOND_STUDENT_ID})",
        "B. Back",
        "M. Main Menu",
        "Q. Quit",
    ):
        assert expected in root
    for old_action in (
        "1. Open submission evidence",
        "2. View current review details",
        "3. Review minimum requirements",
        "4. Review units and Focus Standard observations",
        "5. Overall Focus Standard ratings",
        "6. Compose Focus Standard feedback",
        "7. Manage submission pages",
        "8. Add teacher note",
        "9. Update review workflow state",
        "10. Export student feedback",
        "11. Refresh summary",
    ):
        assert old_action not in root


def test_review_ready_navigation_failure_uses_explicit_unavailable_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation_from_read_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ReviewStudentNavigationError("synthetic canonical navigation failure")
        ),
    )
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "Class-set navigation unavailable:" in output
    assert "Position: unavailable" in output
    assert "Work state: unavailable" in output
    assert "Students needing work: unavailable" in output
    assert "C. Continue Review — unavailable" in output
    assert "N. Next Student — unavailable" in output
    assert "P. Previous Student — unavailable" in output
    assert "W. Next Student Needing Review — unavailable" in output
    assert "none (final roster student)" not in output
    assert "none (first roster student)" not in output
    assert _snapshot(tmp_path) == before


def test_attention_required_compact_root_surfaces_bounded_reason_and_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    navigation = build_review_student_navigation(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    attention = replace(
        navigation,
        current=replace(
            navigation.current,
            category="attention_required",
            reason_code="synthetic_attention_reason",
            warnings=("synthetic_attention_warning",),
        ),
    )
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation_from_read_context",
        lambda *_args, **_kwargs: attention,
    )
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "Work state: attention required" in output
    assert "Attention: synthetic_attention_reason" in output
    assert "Warning: synthetic_attention_warning" in output
    assert "C. Continue Review — unavailable (attention required)" in output
    assert "O. Open Evidence" in output
    assert "E. Export Feedback" in output
    assert "A. Advanced Actions" in output
    assert _snapshot(tmp_path) == before


def test_needs_assembly_remains_recovery_screen_not_compact_review_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    navigation = build_review_student_navigation(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    )
    needs_assembly = replace(
        navigation,
        current=replace(
            navigation.current,
            category="needs_assembly",
            reason_code="routed_evidence_needs_assembly",
        ),
    )
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation_from_read_context",
        lambda *_args, **_kwargs: needs_assembly,
    )
    monkeypatch.setattr(
        review_menu,
        "_load_submission_status",
        lambda *_args, **_kwargs: SimpleNamespace(
            student_statuses=(
                SimpleNamespace(
                    student_id=SECOND_STUDENT_ID,
                    manifest_path=None,
                ),
            )
        ),
    )
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "review-ready submission record has not been assembled yet" in output
    assert "1. Assemble this assignment now" in output
    assert "C. Continue Review — unavailable (submission needs assembly)" in output
    assert "O. Open Evidence" not in output
    assert "E. Export Feedback" not in output
    assert "A. Advanced Actions" not in output
    assert _snapshot(tmp_path) == before


def test_plain_paper_submission_is_review_ready_and_uses_compact_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    created = create_plain_paper_submission(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        SECOND_STUDENT_ID,
        created_at="2026-08-22T12:00:00+00:00",
    )
    assert created.submission_manifest_path.is_file()
    before = _snapshot(tmp_path)
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert f"Student: Mina Patel ({SECOND_STUDENT_ID})" in output
    assert "O. Open Evidence" in output
    assert "C. Continue Review — Review minimum requirements" in output
    assert "E. Export Feedback" in output
    assert "A. Advanced Actions" in output
    assert "No digital submission evidence has been found for this student." not in output
    assert "Create plain-paper submission for this student" not in output
    assert _snapshot(tmp_path) == before


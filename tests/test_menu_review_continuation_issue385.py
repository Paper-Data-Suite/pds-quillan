"""Issue #385 Slice 2 menu tests for deterministic Continue Review routing."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest

import quillan.review_menu as review_menu
from quillan.review_read_context import AssignmentReviewReadContext
from quillan.review_student_navigation import (
    ReviewStudentNavigation,
    ReviewStudentNavigationError,
    build_review_student_navigation,
    build_review_student_navigation_from_read_context,
)
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    SECOND_STUDENT_ID,
    STUDENT_ID,
    _write_workspace,
)


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


def _prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)


def _navigation_with_category(
    root: Path,
    student_id: str,
    category: str,
    *,
    reason_code: str | None = None,
) -> ReviewStudentNavigation:
    navigation = build_review_student_navigation(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        student_id,
    )
    return replace(
        navigation,
        current=replace(
            navigation.current,
            category=category,
            reason_code=(
                f"reason_{category}" if reason_code is None else reason_code
            ),
        ),
    )


def _record_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str, str, str]]:
    calls: list[tuple[str, str, str, str]] = []
    handler_names = (
        "_menu_review_minimum_requirements",
        "_menu_review_unit_observations",
        "_menu_overall_focus_standard_ratings",
        "_menu_compose_focus_standard_feedback",
        "_menu_export_student_feedback",
    )

    for handler_name in handler_names:
        def record(
            _root: Path,
            class_id: str,
            assignment_id: str,
            student_id: str,
            *,
            _handler_name: str = handler_name,
        ) -> None:
            calls.append((_handler_name, class_id, assignment_id, student_id))

        monkeypatch.setattr(review_menu, handler_name, record)
    return calls


@pytest.mark.parametrize(
    ("category", "label", "handler_name", "requires_pause"),
    (
        (
            "minimum_requirements_pending",
            "Review minimum requirements",
            "_menu_review_minimum_requirements",
            False,
        ),
        (
            "observations_pending",
            "Review units and Focus Standard observations",
            "_menu_review_unit_observations",
            False,
        ),
        (
            "ratings_pending",
            "Overall Focus Standard ratings",
            "_menu_overall_focus_standard_ratings",
            False,
        ),
        (
            "feedback_pending",
            "Compose Focus Standard feedback",
            "_menu_compose_focus_standard_feedback",
            False,
        ),
        (
            "export_pending",
            "Export student feedback",
            "_menu_export_student_feedback",
            True,
        ),
    ),
)
def test_continue_review_routes_each_available_stage_to_existing_child_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    category: str,
    label: str,
    handler_name: str,
    requires_pause: bool,
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    navigation = _navigation_with_category(tmp_path, STUDENT_ID, category)
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation_from_read_context",
        lambda *_args, **_kwargs: navigation,
    )
    calls = _record_handlers(monkeypatch)
    _inputs(monkeypatch, ("c", "", "b") if requires_pause else ("c", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert f"C. Continue Review — {label}" in output
    assert calls == [(handler_name, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)]
    assert _snapshot(tmp_path) == before


def test_continue_review_recalculates_after_each_child_returns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    categories = iter(
        (
            "minimum_requirements_pending",
            "ratings_pending",
            "ratings_pending",
        )
    )
    build_calls: list[str] = []

    def changing_builder(
        read_context: AssignmentReviewReadContext,
        student_id: str,
    ) -> ReviewStudentNavigation:
        build_calls.append(student_id)
        navigation = build_review_student_navigation_from_read_context(
            read_context,
            student_id,
        )
        category = next(categories)
        return replace(
            navigation,
            current=replace(
                navigation.current,
                category=category,
                reason_code=f"reason_{category}",
            ),
        )

    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation_from_read_context",
        changing_builder,
    )
    calls = _record_handlers(monkeypatch)
    _inputs(monkeypatch, ("c", "c", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert build_calls == [STUDENT_ID, STUDENT_ID, STUDENT_ID]
    assert calls == [
        (
            "_menu_review_minimum_requirements",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        ),
        (
            "_menu_overall_focus_standard_ratings",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        ),
    ]
    assert "C. Continue Review — Review minimum requirements" in output
    assert "C. Continue Review — Overall Focus Standard ratings" in output


@pytest.mark.parametrize(
    ("category", "label", "message"),
    (
        (
            "complete",
            "complete",
            "No incomplete review stage remains for this student.",
        ),
        (
            "attention_required",
            "unavailable (attention required)",
            "Continue Review is unavailable (attention required).",
        ),
    ),
)
def test_complete_and_attention_required_continue_review_are_no_write_states(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    category: str,
    label: str,
    message: str,
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    navigation = _navigation_with_category(tmp_path, STUDENT_ID, category)
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation_from_read_context",
        lambda *_args, **_kwargs: navigation,
    )
    calls = _record_handlers(monkeypatch)
    _inputs(monkeypatch, ("c", "", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert f"C. Continue Review — {label}" in output
    assert message in output
    assert calls == []
    assert _snapshot(tmp_path) == before


def test_no_submission_continue_review_does_not_create_plain_paper_or_change_student(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    monkeypatch.setattr(
        review_menu,
        "_create_plain_paper_submission_menu",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Continue Review must not create plain paper")
        ),
    )
    _inputs(monkeypatch, ("c", "", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "C. Continue Review — unavailable (no reviewable submission)" in output
    assert "Continue Review is unavailable (no reviewable submission)." in output
    assert f"Student: Mina Patel ({SECOND_STUDENT_ID})" in output
    assert output.count("Position: 2 of 2") == 2
    assert "Position: 1 of 2" not in output
    assert _snapshot(tmp_path) == before


def test_needs_assembly_continue_review_does_not_assemble_submission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    before = _snapshot(tmp_path)
    navigation = _navigation_with_category(
        tmp_path,
        SECOND_STUDENT_ID,
        "needs_assembly",
        reason_code="routed_evidence_needs_assembly",
    )
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation_from_read_context",
        lambda *_args, **_kwargs: navigation,
    )
    synthetic_status = SimpleNamespace(
        student_statuses=(
            SimpleNamespace(
                student_id=SECOND_STUDENT_ID,
                manifest_path=None,
            ),
        )
    )
    monkeypatch.setattr(
        review_menu,
        "_load_submission_status",
        lambda *_args, **_kwargs: synthetic_status,
    )
    monkeypatch.setattr(
        review_menu,
        "_assemble_assignment",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Continue Review must not assemble submissions")
        ),
    )
    _inputs(monkeypatch, ("c", "", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, SECOND_STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "C. Continue Review — unavailable (submission needs assembly)" in output
    assert "Continue Review is unavailable (submission needs assembly)." in output
    assert _snapshot(tmp_path) == before


def test_queue_navigation_failure_makes_continue_review_bounded_and_unavailable(
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
            ReviewStudentNavigationError("synthetic canonical queue failure")
        ),
    )
    calls = _record_handlers(monkeypatch)
    _inputs(monkeypatch, ("c", "", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert "Class-set navigation unavailable:" in output
    assert "C. Continue Review — unavailable" in output
    assert (
        "Continue Review is unavailable because canonical review work state "
        "could not be resolved."
    ) in output
    assert calls == []
    assert _snapshot(tmp_path) == before


def test_continue_review_remains_visible_on_compact_review_ready_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
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


def test_student_navigation_recalculates_continue_review_for_new_exact_student(
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
    assert "C. Continue Review — Review minimum requirements" in output
    assert "C. Continue Review — unavailable (no reviewable submission)" in output
    assert "Position: 1 of 2" in output
    assert "Position: 2 of 2" in output
    assert _snapshot(tmp_path) == before


def test_selected_student_identity_mismatch_fails_closed_before_routing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare(tmp_path, monkeypatch)
    navigation = build_review_student_navigation(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    mismatched = replace(
        navigation,
        current=replace(navigation.current, student_id=SECOND_STUDENT_ID),
    )

    continuation = review_menu._review_continuation_for_selected_student(
        mismatched,
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
    )

    assert continuation is None

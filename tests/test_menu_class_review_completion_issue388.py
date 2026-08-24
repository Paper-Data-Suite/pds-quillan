"""Issue #388 menu tests for focused class review completion."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.class_review_completion import (
    ClassReviewCompletionItem,
    ClassReviewCompletionView,
)
from quillan.cli import main
import quillan.review_menu as review_menu
from tests.menu_screen_recorder import (
    MenuScreenRecorder,
    assert_focused_child_screen,
)
from tests.test_menu_export_actions import (
    _enter_assignment_review_actions,
    _exit_assignment_review_actions_to_main,
)
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    SECOND_STUDENT_ID,
    STUDENT_ID,
    _write_workspace,
)


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): (
            path.read_bytes() if path.is_file() else None
        )
        for path in root.rglob("*")
    }


def _inputs(monkeypatch: pytest.MonkeyPatch, responses: tuple[str, ...]) -> None:
    iterator = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration as error:
            raise AssertionError(
                "Menu requested more input than supplied."
            ) from error

    monkeypatch.setattr("builtins.input", fake_input)


def _completion_view() -> ClassReviewCompletionView:
    items = (
        ClassReviewCompletionItem(
            student_id=STUDENT_ID,
            display_name="Avery Rivera",
            category="feedback_pending",
            reason_code="feedback_not_composed",
            feedback_pdf_status="missing",
            feedback_markdown_status="missing",
            warnings=(),
        ),
        ClassReviewCompletionItem(
            student_id=SECOND_STUDENT_ID,
            display_name="Mina Patel",
            category="complete",
            reason_code="current_feedback_export_present",
            feedback_pdf_status="present",
            feedback_markdown_status="missing",
            warnings=(),
        ),
    )
    return ClassReviewCompletionView(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        items=items,
        category_counts=(
            ("no_submission", 0),
            ("needs_assembly", 0),
            ("minimum_requirements_pending", 0),
            ("observations_pending", 0),
            ("ratings_pending", 0),
            ("feedback_pending", 1),
            ("export_pending", 0),
            ("complete", 1),
            ("attention_required", 0),
        ),
        feedback_pdf_counts=(
            ("present", 1),
            ("stale", 0),
            ("missing", 0),
            ("unknown", 0),
        ),
        feedback_markdown_counts=(
            ("present", 0),
            ("stale", 0),
            ("missing", 1),
            ("unknown", 0),
        ),
        unrostered_student_ids=(),
        warnings=(),
    )


def test_assignment_root_prioritizes_completion_and_routes_action_seven(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("7", "b", "b"))

    assert review_menu._launch_assignment_review_actions(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    ) == 0

    output = capsys.readouterr().out
    assert "Complete: 0 / 2" in output
    assert "Needs work: 2" in output
    assert "Export pending: 0" in output
    assert "Attention required: 0" in output
    assert "7. Review class progress" in output
    assert "F. Batch Feedback Export" in output
    assert "Class Review Progress" in output


def test_class_progress_filter_drills_into_exact_student_and_is_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    view = _completion_view()
    selected: list[str] = []

    monkeypatch.setattr(
        review_menu,
        "_load_class_review_completion_from_dashboard",
        lambda _root, _dashboard: (view, None),
    )

    def launch(
        _root: Path,
        _class_id: str,
        _assignment_id: str,
        student_id: str,
    ) -> int:
        selected.append(student_id)
        return 0

    monkeypatch.setattr(review_menu, "_launch_selected_student_review", launch)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("f", "4", "6", "1", "b"))

    review_menu._menu_class_review_progress(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    output = capsys.readouterr().out
    assert selected == [STUDENT_ID]
    assert output.count("Filter: Feedback pending") == 2
    assert output.count("Showing: 1 of 2") == 2
    assert f"Avery Rivera ({STUDENT_ID}) — feedback pending" in output
    assert "Filter: All students" in output


def test_class_progress_export_filter_uses_current_teacher_wording(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    view = _completion_view()
    monkeypatch.setattr(
        review_menu,
        "_load_class_review_completion_from_dashboard",
        lambda _root, _dashboard: (view, None),
    )
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("f", "5", "1", "b"))

    review_menu._menu_class_review_progress(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    output = capsys.readouterr().out
    assert "Only export-capable reviews are considered" in output
    assert "Filter: PDF current" in output
    assert "Showing: 1 of 2" in output
    assert (
        f"Mina Patel ({SECOND_STUDENT_ID}) — complete — "
        "PDF current; Markdown missing"
    ) in output


def test_roster_unavailable_progress_fails_closed_but_keeps_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr(
        review_menu,
        "_load_class_review_completion_from_dashboard",
        lambda _root, _dashboard: (
            None,
            "Canonical class roster is unavailable; review queue ordering "
            "cannot be derived safely.",
        ),
    )
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("b",))

    review_menu._menu_class_review_progress(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    output = capsys.readouterr().out
    assert "Review completion: unavailable" in output
    assert "Canonical class roster is unavailable" in output
    assert "D. Full diagnostic dashboard" in output
    assert "F. Filter" not in output


def test_progress_view_filter_and_refresh_are_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_workspace(tmp_path)
    before = _snapshot(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("f", "2", "r", "b"))

    review_menu._menu_class_review_progress(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    assert _snapshot(tmp_path) == before


def test_progress_full_diagnostic_route_reuses_existing_dashboard_formatter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    _inputs(monkeypatch, ("d", "", "b"))

    review_menu._menu_class_review_progress(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    output = capsys.readouterr().out
    assert "Full Assignment Diagnostic Dashboard" in output
    assert "Assignment Review Dashboard" in output

@pytest.mark.menu_density_workflow("class review progress")
def test_class_review_progress_density_uses_real_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    recorder = MenuScreenRecorder(
        _enter_assignment_review_actions()
        + [
            "7",  # Assignment Review Actions -> Class Review Progress.
            "f",  # Filter.
            "4",  # By review-work stage.
            "1",  # no_submission.
            "1",  # Exact first displayed roster row.
            "b",  # Return from Selected Student Review.
            "b",  # Return from Class Review Progress.
        ]
        + _exit_assignment_review_actions_to_main()
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert_focused_child_screen(
        screens,
        heading="Class Review Progress",
        required_text=(
            "Filter: No submission",
            "Showing: 1 of 2",
            f"Mina Patel ({SECOND_STUDENT_ID})",
        ),
        forbidden_parent_text="5. View full diagnostic dashboard",
        parent_heading="Assignment Review Actions",
        result_heading="Selected Student Review",
        unrelated_previous_text="F. Batch Feedback Export",
    )
    assert output.count("Filter: No submission") >= 2
    assert output.count("Showing: 1 of 2") >= 2
    assert all(
        prompt.prompt != "Select student/submission: "
        for prompt in recorder.prompts
    )

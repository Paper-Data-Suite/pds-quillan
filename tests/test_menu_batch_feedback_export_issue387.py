"""Issue #387 teacher-menu tests for assignment-level batch feedback export."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from quillan.batch_feedback_export import (
    BatchFeedbackExportPlan,
    BatchFeedbackExportResult,
    BatchFeedbackExportStudentPlan,
    BatchFeedbackExportStudentResult,
)
from quillan.cli import main
import quillan.review_menu as review_menu
from tests.menu_screen_recorder import MenuScreenRecorder, assert_focused_child_screen
from tests.test_menu_export_actions import (
    ASSIGNMENT_ID,
    CLASS_ID,
    _enter_assignment_review_actions,
    _exit_assignment_review_actions_to_main,
    _write_workspace,
)


def _menu_input(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> None:
    values: Iterator[str] = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(values)
        except StopIteration as error:
            raise AssertionError("Menu requested more input than supplied.") from error

    monkeypatch.setattr("builtins.input", fake_input)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _plan() -> BatchFeedbackExportPlan:
    return BatchFeedbackExportPlan(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        scope="completed",
        feedback_format="pdf",
        overwrite_policy="none",
        roster_count=2,
        excluded_incomplete_count=1,
        excluded_attention_count=0,
        items=(
            BatchFeedbackExportStudentPlan(
                student_id="stu_0001",
                display_name="Avery Rivera",
                category="export_pending",
                reason_code="feedback_export_missing",
                warnings=(),
                review_updated_at="2026-08-23T12:00:00+00:00",
                requested_export_statuses=(("feedback_pdf", "missing"),),
                action="create",
            ),
        ),
    )


def _result() -> BatchFeedbackExportResult:
    return BatchFeedbackExportResult(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        feedback_format="pdf",
        overwrite_policy="none",
        items=(
            BatchFeedbackExportStudentResult(
                student_id="stu_0001",
                display_name="Avery Rivera",
                outcome="created",
                message="verified current canonical feedback export",
                artifact_paths=(
                    "classes/english12_p3_synthetic/modules/quillan/work/"
                    "essay_01_synthetic/submissions/stu_0001/exports/feedback.pdf",
                ),
            ),
        ),
    )


def test_assignment_review_actions_exposes_batch_without_renumbering_existing_actions(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions() + _exit_assignment_review_actions_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "4. Export reports" in output
    assert "5. View full diagnostic dashboard" in output
    assert "7. Review class progress" in output
    assert "F. Batch Feedback Export" in output
    assert "G. Prepare Feedback for Printing / Sharing" in output


@pytest.mark.menu_density_workflow("batch feedback export")
def test_menu_completed_batch_previews_once_then_executes_once(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    planned = _plan()
    captured: dict[str, object] = {}
    executed: list[BatchFeedbackExportPlan] = []

    def build(*args: object, **kwargs: object) -> BatchFeedbackExportPlan:
        captured.update(kwargs)
        return planned

    def execute(
        _root: Path, plan: BatchFeedbackExportPlan
    ) -> BatchFeedbackExportResult:
        executed.append(plan)
        return _result()

    monkeypatch.setattr(review_menu, "build_batch_feedback_export_plan", build)
    monkeypatch.setattr(review_menu, "execute_batch_feedback_export", execute)
    recorder = MenuScreenRecorder(
        _enter_assignment_review_actions()
        + [
            "f",  # Assignment Review Actions -> batch feedback export.
            "1",  # All export-capable completed reviews.
            "1",  # PDF.
            "1",  # No overwrite.
            "yes",  # One confirmation for the whole batch.
            "",  # Result pause.
        ]
        + _exit_assignment_review_actions_to_main()
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert_focused_child_screen(
        screens,
        heading="Batch Feedback Export Preview",
        required_text=(
            "Scope: completed",
            "Writable students: 1",
            "action=create",
        ),
        forbidden_parent_text="5. View full diagnostic dashboard",
        parent_heading="Assignment Review Actions",
        result_heading="Batch Feedback Export Result",
        unrelated_previous_text="Assembly needed:",
    )
    assert captured == {
        "scope": "completed",
        "student_ids": (),
        "feedback_format": "pdf",
        "overwrite_policy": "none",
    }
    assert executed == [planned]
    assert output.count("Execute this batch?") == 0
    assert sum(
        prompt.prompt == "Execute this batch? (y/yes): "
        for prompt in recorder.prompts
    ) == 1
    assert all(
        prompt.prompt != "Select student/submission: " for prompt in recorder.prompts
    )
    assert "verified current canonical feedback export" in output


def test_menu_cancel_after_preview_starts_no_batch_write(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        review_menu,
        "build_batch_feedback_export_plan",
        lambda *args, **kwargs: _plan(),
    )
    monkeypatch.setattr(
        review_menu,
        "execute_batch_feedback_export",
        lambda *args, **kwargs: calls.append("execute"),
    )
    _menu_input(monkeypatch, ["1", "1", "1", "n"])

    review_menu._menu_batch_feedback_export(workspace, CLASS_ID, ASSIGNMENT_ID)

    output = capsys.readouterr().out
    assert "Batch Feedback Export Preview" in output
    assert "canceled; no batch write was started" in output
    assert calls == []


def test_menu_explicit_selection_passes_exact_ids_not_display_names(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def build(*args: object, **kwargs: object) -> BatchFeedbackExportPlan:
        captured.update(kwargs)
        return _plan()

    monkeypatch.setattr(review_menu, "build_batch_feedback_export_plan", build)
    _menu_input(monkeypatch, ["2", "2,1", "2", "3", "n"])

    review_menu._menu_batch_feedback_export(workspace, CLASS_ID, ASSIGNMENT_ID)

    assert captured["scope"] == "selected"
    assert captured["student_ids"] == ("stu_0002", "stu_0001")
    assert captured["feedback_format"] == "markdown"
    assert captured["overwrite_policy"] == "all"
    output = capsys.readouterr().out
    assert "Mina Patel (stu_0002)" in output
    assert "Avery Rivera (stu_0001)" in output

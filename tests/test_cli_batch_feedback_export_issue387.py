"""Issue #387 direct CLI tests for batch feedback export."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.batch_feedback_export import (
    BatchFeedbackExportPlan,
    BatchFeedbackExportResult,
    BatchFeedbackExportStudentPlan,
    BatchFeedbackExportStudentResult,
)
from quillan.cli import main
import quillan.cli_app.handlers.exports as cli_exports

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"


def _plan(*, action: str = "create") -> BatchFeedbackExportPlan:
    item = BatchFeedbackExportStudentPlan(
        student_id="001",
        display_name="Avery Rivera",
        category="export_pending",
        reason_code="feedback_export_missing",
        warnings=(),
        review_updated_at="2026-08-23T12:00:00+00:00",
        requested_export_statuses=(("feedback_pdf", "missing"),),
        action=action,  # type: ignore[arg-type]
    )
    return BatchFeedbackExportPlan(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        scope="completed",
        feedback_format="pdf",
        overwrite_policy="none",
        roster_count=1,
        excluded_incomplete_count=0,
        excluded_attention_count=0,
        items=(item,),
    )


def _result(outcome: str = "created") -> BatchFeedbackExportResult:
    return BatchFeedbackExportResult(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        feedback_format="pdf",
        overwrite_policy="none",
        items=(
            BatchFeedbackExportStudentResult(
                student_id="001",
                display_name="Avery Rivera",
                outcome=outcome,  # type: ignore[arg-type]
                message="synthetic result",
                artifact_paths=("classes/c/a/001/exports/feedback.pdf",),
            ),
        ),
    )


def test_cli_dry_run_prints_plan_and_never_executes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        cli_exports,
        "build_batch_feedback_export_plan",
        lambda *args, **kwargs: _plan(),
    )
    monkeypatch.setattr(
        cli_exports,
        "execute_batch_feedback_export",
        lambda *args, **kwargs: calls.append("execute"),
    )

    assert main(
        [
            "export-feedback-batch",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--completed",
            "--format",
            "pdf",
            "--dry-run",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "Batch Feedback Export Preview" in output
    assert "Scope: completed" in output
    assert "Writable students: 1" in output
    assert "action=create" in output
    assert calls == []


def test_cli_yes_executes_confirmed_plan_and_prints_verification_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    planned = _plan()
    calls: list[BatchFeedbackExportPlan] = []
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        cli_exports,
        "build_batch_feedback_export_plan",
        lambda *args, **kwargs: planned,
    )

    def execute(
        _root: Path, plan: BatchFeedbackExportPlan
    ) -> BatchFeedbackExportResult:
        calls.append(plan)
        return _result()

    monkeypatch.setattr(cli_exports, "execute_batch_feedback_export", execute)

    assert main(
        [
            "export-feedback-batch",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--completed",
            "--format",
            "pdf",
            "--overwrite-policy",
            "none",
            "--yes",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert calls == [planned]
    assert "Batch Feedback Export Result" in output
    assert "created: synthetic result" in output
    assert "artifact: classes/c/a/001/exports/feedback.pdf" in output


def test_cli_explicit_selection_passes_exact_ids_and_partial_failure_is_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)

    def build(*args: object, **kwargs: object) -> BatchFeedbackExportPlan:
        captured.update(kwargs)
        return _plan()

    monkeypatch.setattr(cli_exports, "build_batch_feedback_export_plan", build)
    monkeypatch.setattr(
        cli_exports,
        "execute_batch_feedback_export",
        lambda *args, **kwargs: _result("verification_failed"),
    )

    assert main(
        [
            "export-feedback-batch",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--student-id",
            "002",
            "--student-id",
            "001",
            "--format",
            "pdf",
            "--yes",
        ]
    ) == 1

    assert captured["scope"] == "selected"
    assert captured["student_ids"] == ("002", "001")
    assert "verification_failed: synthetic result" in capsys.readouterr().out


def test_cli_selected_ineligible_result_is_nonzero_but_policy_skip_is_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        cli_exports,
        "build_batch_feedback_export_plan",
        lambda *args, **kwargs: _plan(),
    )
    command = [
        "export-feedback-batch",
        CLASS_ID,
        ASSIGNMENT_ID,
        "--student-id",
        "001",
        "--format",
        "pdf",
        "--yes",
    ]

    monkeypatch.setattr(
        cli_exports,
        "execute_batch_feedback_export",
        lambda *args, **kwargs: _result("blocked_incomplete"),
    )
    assert main(command) == 1

    monkeypatch.setattr(
        cli_exports,
        "execute_batch_feedback_export",
        lambda *args, **kwargs: _result("skipped_by_policy"),
    )
    assert main(command) == 0

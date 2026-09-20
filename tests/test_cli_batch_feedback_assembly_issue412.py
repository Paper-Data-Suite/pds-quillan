"""Issue #412 direct CLI feedback-assembly coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.generated_output_opening as output_opening
from quillan.batch_feedback_assembly import (
    FeedbackAssemblyPlan,
    FeedbackAssemblyResult,
    FeedbackAssemblyStudentPlan,
)
from quillan.cli import main
import quillan.cli_app.handlers.exports as cli_exports

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"


def _plan(
    *,
    scope: str = "whole_class",
    output: str = "both",
    duplex_safe: bool = True,
) -> FeedbackAssemblyPlan:
    return FeedbackAssemblyPlan(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        scope=scope,  # type: ignore[arg-type]
        output=output,  # type: ignore[arg-type]
        duplex_safe=duplex_safe,
        roster_count=2,
        items=(
            FeedbackAssemblyStudentPlan(
                student_id="001",
                display_name="Avery Rivera",
                status="current",
                reason_code="current",
                source_relative_path="classes/c/a/001/exports/feedback.pdf",
                review_updated_at="2026-09-20T20:00:00+00:00",
                source_review_updated_at="2026-09-20T20:00:00+00:00",
                source_size=100,
                source_sha256="a" * 64,
                source_page_count=1,
            ),
            FeedbackAssemblyStudentPlan(
                student_id="002",
                display_name="Jordan Smith",
                status="missing",
                reason_code="feedback_pdf_missing",
                source_relative_path="classes/c/a/002/exports/feedback.pdf",
                review_updated_at=None,
                source_review_updated_at=None,
                source_size=None,
                source_sha256=None,
                source_page_count=None,
            ),
        ),
    )


def _result(
    *,
    scope: str = "whole_class",
    output: str = "both",
    duplex_safe: bool = True,
) -> FeedbackAssemblyResult:
    print_requested = output in {"print", "both"}
    bundle_requested = output in {"bundle", "both"}
    return FeedbackAssemblyResult(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        scope=scope,  # type: ignore[arg-type]
        output=output,  # type: ignore[arg-type]
        duplex_safe=duplex_safe,
        selected_count=2,
        included_student_ids=("001",),
        exclusions=(),
        print_packet_relative_path=(
            "classes/c/work/a/exports/feedback_batches/x/feedback_print_packet.pdf"
            if print_requested
            else None
        ),
        sharing_bundle_relative_path=(
            "classes/c/work/a/exports/feedback_batches/x/feedback_sharing_bundle.zip"
            if bundle_requested
            else None
        ),
        print_packet_page_count=1 if print_requested else None,
        sharing_bundle_pdf_count=1 if bundle_requested else None,
    )


def test_cli_dry_run_validates_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        cli_exports, "build_feedback_assembly_plan", lambda *a, **k: _plan()
    )
    monkeypatch.setattr(
        cli_exports,
        "execute_feedback_assembly",
        lambda *a, **k: calls.append("execute"),
    )

    assert main(
        [
            "assemble-feedback-batch",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--whole-class",
            "--output",
            "both",
            "--duplex-safe",
            "--dry-run",
        ]
    ) == 0

    assert calls == []
    assert not (tmp_path / "classes").exists()
    output = capsys.readouterr().out
    assert "Feedback Batch Assembly Preview" in output
    assert "Ready: 1" in output
    assert "feedback_pdf_missing: 1" in output


def test_cli_selected_ids_and_yes_execute_without_opening(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}
    executed: list[FeedbackAssemblyPlan] = []
    opened: list[str] = []
    bundle_plan = _plan(scope="selected", output="bundle", duplex_safe=False)
    bundle_result = _result(scope="selected", output="bundle", duplex_safe=False)
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        output_opening,
        "open_generated_output_folder",
        lambda *a, **k: opened.append("opened"),
    )

    def build(*args: object, **kwargs: object) -> FeedbackAssemblyPlan:
        captured.update(kwargs)
        return bundle_plan

    monkeypatch.setattr(cli_exports, "build_feedback_assembly_plan", build)
    def execute(root: Path, plan: FeedbackAssemblyPlan) -> FeedbackAssemblyResult:
        executed.append(plan)
        return bundle_result

    monkeypatch.setattr(cli_exports, "execute_feedback_assembly", execute)

    assert main(
        [
            "assemble-feedback-batch",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--student-id",
            "002",
            "--student-id",
            "001",
            "--output",
            "bundle",
            "--yes",
        ]
    ) == 0

    assert captured["scope"] == "selected"
    assert captured["student_ids"] == ("002", "001")
    assert captured["output"] == "bundle"
    assert executed == [bundle_plan]
    assert executed[0].output == "bundle"
    assert opened == []
    output = capsys.readouterr().out
    assert "Feedback Batch Result" in output
    assert "feedback_sharing_bundle.zip" in output
    assert "feedback_print_packet.pdf" not in output


def test_cli_rejects_duplex_safe_bundle_through_service_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "assemble-feedback-batch",
            CLASS_ID,
            ASSIGNMENT_ID,
            "--whole-class",
            "--output",
            "bundle",
            "--duplex-safe",
            "--dry-run",
        ]
    ) == 1
    assert "Duplex-safe separation" in capsys.readouterr().err

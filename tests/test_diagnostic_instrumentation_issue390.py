"""Issue #390 bounded instrumentation contracts for local diagnostics."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import quillan.assignment_copying as assignment_copying
import quillan.batch_feedback_export as batch_feedback_export
import quillan.diagnostic_events as diagnostics
import quillan.feedback_export as feedback_export
import quillan.intake_assembly as intake_assembly
import quillan.post_dispatch_review_resolution as post_dispatch_resolution
import quillan.review_record_paths as review_record_paths


@pytest.fixture(autouse=True)
def _fixed_core_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quillan.diagnostic_events._installed_core_version",
        lambda: "0.6.3",
    )


def test_try_emit_build_failure_never_raises_or_creates_state(
    tmp_path: Path,
) -> None:
    result = diagnostics.try_emit_diagnostic_event(
        tmp_path,
        component="not_a_component",
        workflow="copy_assignment",
        stage="preflight",
        outcome="failure",
        code="assignment_copy_stale",
    )

    assert result.recorded is False
    assert result.event_id is None
    assert result.warning_code == "diagnostic_instrumentation_failed"
    assert not (tmp_path / "shared").exists()


def test_try_emit_unexpected_storage_failure_is_non_interfering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_root: str | Path, _event: diagnostics.DiagnosticEvent) -> object:
        raise RuntimeError("PRIVATE-STORAGE-FAILURE-SENTINEL")

    monkeypatch.setattr(diagnostics, "record_diagnostic_event", fail)

    result = diagnostics.try_emit_diagnostic_event(
        tmp_path,
        component="assignment",
        workflow="copy_assignment",
        stage="verify_record",
        outcome="success",
        code="assignment_copy_created",
        class_id="class_a",
        assignment_id="assignment_a",
    )

    assert result.recorded is False
    assert result.warning_code == "diagnostic_instrumentation_failed"


def test_slice2a_owner_boundaries_use_the_non_throwing_helper() -> None:
    modules = (
        assignment_copying,
        intake_assembly,
        review_record_paths,
        feedback_export,
        batch_feedback_export,
        post_dispatch_resolution,
    )
    for module in modules:
        source = inspect.getsource(module)
        assert "try_emit_diagnostic_event" in source
        assert "record_diagnostic_event(" not in source
        assert "build_diagnostic_event(" not in source


def test_review_persistence_records_failures_not_teacher_judgment_success() -> None:
    create_source = inspect.getsource(
        review_record_paths.create_quillan_review_record
    )
    update_source = inspect.getsource(
        review_record_paths.update_quillan_review_record
    )
    combined = create_source + update_source

    assert "review_write_conflict" in combined
    assert "review_write_partial_success" in combined
    assert "review_record_unreadable" in combined
    assert 'outcome="success"' not in combined
    assert "rating" not in combined
    assert "feedback" not in combined
    assert "teacher" not in combined


def test_scan_instrumentation_has_no_student_or_source_identity_arguments() -> None:
    source = inspect.getsource(intake_assembly._record_scan_workflow_diagnostics)

    assert "partial_dispatch" in source
    assert "dispatch_failed" in source
    assert "assembly_succeeded" in source
    assert "student_id=" not in source
    assert "source_scan_id=" not in source
    assert "source_filename=" not in source


def test_batch_export_diagnostic_is_assignment_aggregate() -> None:
    source = inspect.getsource(
        batch_feedback_export.execute_batch_feedback_export
    )
    event_tail = source[source.index("result = BatchFeedbackExportResult(") :]

    assert "batch_export_partial_success" in event_tail
    assert "batch_export_verified" in event_tail
    assert "student_id=" not in event_tail


def test_verified_retry_is_recorded_only_after_resolution_write() -> None:
    source = inspect.getsource(
        post_dispatch_resolution.resolve_post_dispatch_after_successful_retry
    )

    write_at = source.index("persisted = _write_resolution(")
    event_at = source.index("try_emit_diagnostic_event(")
    return_at = source.index("return persisted")
    assert write_at < event_at < return_at
    assert 'outcome="recovered"' in source
    assert 'code="post_dispatch_recovered"' in source


def test_feedback_event_calls_do_not_pass_student_identity() -> None:
    markdown = inspect.getsource(feedback_export.export_student_feedback)
    pdf = inspect.getsource(feedback_export.export_student_feedback_pdf)

    for source in (markdown, pdf):
        event_calls = source.split("try_emit_diagnostic_event(")[1:]
        assert event_calls
        for call in event_calls:
            bounded = call.split(")", 1)[0]
            assert "student_id=" not in bounded
            assert "exception=str(" not in bounded

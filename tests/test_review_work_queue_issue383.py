"""Issue #383 tests for the deterministic assignment review work queue."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from quillan.review_dashboard import DashboardStudentStatus
from quillan.review_work_queue import (
    WORK_QUEUE_CATEGORIES,
    ReviewWorkQueueError,
    assignment_review_work_queue_to_dict,
    build_assignment_review_work_queue,
    classify_review_work_queue_item,
    format_assignment_review_work_queue,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import (
    _write_assignment,
    _write_records,
    _write_roster,
)


def _student(
    *,
    student_id: str = "00100",
    display_name: str = "Avery Rivera",
    needs_assembly: bool = False,
    submission_status: str = "valid",
    review_status: str = "valid",
    review_state: str | None = "not_started",
    minimum_status: str | None = "met",
    returned: bool = False,
    plain_paper: bool = False,
    pdf_status: str = "missing",
    markdown_status: str = "missing",
    warnings: tuple[str, ...] = (),
) -> DashboardStudentStatus:
    return DashboardStudentStatus(
        student_id=student_id,
        display_name=display_name,
        roster_status="rostered",
        routed_evidence_present=needs_assembly,
        needs_assembly=needs_assembly,
        submission_status=submission_status,
        submission_path=(
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
            f"submissions/{student_id}/submission.json"
        ),
        submission_state=None if submission_status != "valid" else "unreviewed",
        plain_paper=plain_paper,
        evidence_file_count=0,
        page_counts=(),
        review_status=review_status,
        review_path=(
            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
            f"submissions/{student_id}/review.json"
        ),
        review_state=review_state,
        minimum_requirement_status=minimum_status,
        returned_without_full_review=returned,
        feedback_pdf_status=pdf_status,
        feedback_markdown_status=markdown_status,
        warnings=warnings,
    )


def _category(
    student: DashboardStudentStatus,
    *,
    configured_requirement_count: int = 1,
) -> tuple[str, str, tuple[str, ...]]:
    item = classify_review_work_queue_item(
        CLASS_ID,
        ASSIGNMENT_ID,
        student,
        configured_requirement_count=configured_requirement_count,
    )
    return item.category, item.reason_code, item.warnings


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def test_submission_preparation_categories_are_distinct() -> None:
    no_submission = _student(
        submission_status="missing",
        review_status="unavailable",
        review_state=None,
        minimum_status=None,
    )
    needs_assembly = _student(
        needs_assembly=True,
        submission_status="missing",
        review_status="unavailable",
        review_state=None,
        minimum_status=None,
    )

    assert _category(no_submission)[:2] == (
        "no_submission",
        "submission_missing",
    )
    assert _category(needs_assembly)[:2] == (
        "needs_assembly",
        "routed_evidence_needs_assembly",
    )


def test_minimum_requirement_gate_precedes_later_workflow_state() -> None:
    student = _student(
        review_state="ratings_complete",
        minimum_status="not_checked",
    )

    category, reason, warnings = _category(student)

    assert category == "minimum_requirements_pending"
    assert reason == "minimum_requirement_outcome_not_checked"
    assert "workflow_state_ahead_of_minimum_requirements" in warnings


def test_assignment_without_minimum_requirements_skips_requirement_phase() -> None:
    student = _student(
        review_status="missing",
        review_state=None,
        minimum_status=None,
    )

    assert _category(student, configured_requirement_count=0)[:2] == (
        "observations_pending",
        "observations_not_complete",
    )


@pytest.mark.parametrize(
    ("state", "expected_category", "expected_reason"),
    (
        ("not_started", "observations_pending", "observations_not_complete"),
        (
            "requirements_checked",
            "observations_pending",
            "observations_not_complete",
        ),
        (
            "observations_in_progress",
            "observations_pending",
            "observations_not_complete",
        ),
        ("observations_complete", "ratings_pending", "ratings_not_complete"),
        ("ratings_complete", "feedback_pending", "feedback_not_composed"),
        ("feedback_composed", "export_pending", "feedback_export_missing"),
        ("ready_for_export", "export_pending", "feedback_export_missing"),
        ("exported", "export_pending", "feedback_export_missing"),
    ),
)
def test_explicit_review_state_drives_mechanical_stage(
    state: str,
    expected_category: str,
    expected_reason: str,
) -> None:
    student = _student(review_state=state, minimum_status="met")

    assert _category(student)[:2] == (expected_category, expected_reason)


def test_plain_paper_valid_submission_enters_normal_review_classification() -> None:
    student = _student(
        plain_paper=True,
        review_status="missing",
        review_state=None,
        minimum_status=None,
    )

    assert _category(student)[:2] == (
        "minimum_requirements_pending",
        "minimum_requirement_outcome_not_checked",
    )


def test_duplicate_display_names_preserve_exact_student_identity() -> None:
    first = classify_review_work_queue_item(
        CLASS_ID,
        ASSIGNMENT_ID,
        _student(student_id="00100", display_name="Alex Lee"),
        configured_requirement_count=1,
    )
    second = classify_review_work_queue_item(
        CLASS_ID,
        ASSIGNMENT_ID,
        _student(student_id="00200", display_name="Alex Lee"),
        configured_requirement_count=1,
    )

    assert first.display_name == second.display_name == "Alex Lee"
    assert first.student_id == "00100"
    assert second.student_id == "00200"
    assert first.student_id != second.student_id


def test_markdown_only_current_export_satisfies_export_gate() -> None:
    student = _student(
        review_state="exported",
        minimum_status="met",
        pdf_status="missing",
        markdown_status="present",
    )

    assert _category(student)[:2] == (
        "complete",
        "current_feedback_export_present",
    )


def test_current_supported_export_is_complete_even_if_companion_is_stale() -> None:
    student = _student(
        review_state="exported",
        minimum_status="met",
        pdf_status="present",
        markdown_status="stale",
        warnings=("feedback_markdown_stale",),
    )

    category, reason, warnings = _category(student)

    assert category == "complete"
    assert reason == "current_feedback_export_present"
    assert warnings == ("feedback_markdown_stale",)


@pytest.mark.parametrize(
    ("pdf_status", "markdown_status", "reason"),
    (
        ("stale", "missing", "feedback_export_stale"),
        ("unknown", "missing", "feedback_export_metadata_unknown"),
        ("missing", "missing", "feedback_export_missing"),
    ),
)
def test_export_pending_reason_uses_existing_freshness_state(
    pdf_status: str,
    markdown_status: str,
    reason: str,
) -> None:
    student = _student(
        review_state="exported",
        minimum_status="met",
        pdf_status=pdf_status,
        markdown_status=markdown_status,
    )

    assert _category(student)[:2] == ("export_pending", reason)


def test_returned_without_full_review_bypasses_non_applicable_review_stages() -> None:
    returned = _student(
        review_state="returned_without_full_review",
        minimum_status="returned_without_full_review",
        returned=True,
    )
    returned_exported = _student(
        review_state="returned_without_full_review",
        minimum_status="returned_without_full_review",
        returned=True,
        pdf_status="present",
    )

    assert _category(returned)[:2] == (
        "export_pending",
        "feedback_export_missing",
    )
    assert _category(returned_exported)[:2] == (
        "complete",
        "current_feedback_export_present",
    )


def test_inconsistent_returned_state_fails_closed() -> None:
    student = _student(
        review_state="returned_without_full_review",
        minimum_status="met",
        returned=False,
    )

    assert _category(student)[:2] == (
        "attention_required",
        "returned_state_inconsistent",
    )


@pytest.mark.parametrize(
    ("student", "reason"),
    (
        (_student(submission_status="invalid"), "invalid_submission"),
        (
            _student(submission_status="identity_mismatch"),
            "record_identity_mismatch",
        ),
        (_student(review_status="invalid"), "invalid_review"),
        (_student(review_status="orphaned"), "orphan_review"),
        (
            _student(review_status="identity_mismatch"),
            "record_identity_mismatch",
        ),
    ),
)
def test_invalid_or_unsafe_record_state_requires_attention(
    student: DashboardStudentStatus,
    reason: str,
) -> None:
    assert _category(student)[:2] == ("attention_required", reason)


def test_real_queue_uses_roster_order_fixed_counts_and_writes_nothing(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    before = _snapshot(tmp_path)

    queue = build_assignment_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    document = cast(dict[str, Any], assignment_review_work_queue_to_dict(queue))
    text = format_assignment_review_work_queue(queue)

    assert [item.student_id for item in queue.items] == ["00100", "00200", "00900"]
    assert [item.category for item in queue.items] == [
        "no_submission",
        "no_submission",
        "no_submission",
    ]
    counts = cast(dict[str, int], document["counts"])
    assert list(counts) == list(WORK_QUEUE_CATEGORIES)
    assert sum(counts.values()) == 3
    assert counts["no_submission"] == 3
    assert queue.complete_count == 0
    assert queue.needs_work_count == 3
    assert "Review Work Queue" in text
    assert "Avery Rivera (00100)" in text
    assert _snapshot(tmp_path) == before


def test_unrostered_records_are_excluded_from_roster_queue(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _write_records(tmp_path, "00300")

    queue = build_assignment_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert [item.student_id for item in queue.items] == ["00100", "00200", "00900"]
    assert queue.unrostered_student_ids == ("00300",)
    assert "unrostered_records_excluded" in queue.warnings
    assert sum(dict(queue.counts).values()) == 3


def test_roster_unavailable_fails_instead_of_using_directory_order(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path)
    _write_records(tmp_path, "00300")

    with pytest.raises(ReviewWorkQueueError, match="roster is unavailable"):
        build_assignment_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)


def test_repeated_queue_serialization_is_deterministic(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)

    first = assignment_review_work_queue_to_dict(
        build_assignment_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    second = assignment_review_work_queue_to_dict(
        build_assignment_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )

    assert first == second

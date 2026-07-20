"""Create review-ready submissions for work completed on plain paper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pds_core.classes import load_class_roster
from pds_core.identifiers import validate_identifier

from quillan.assignments import load_assignment_config
from quillan.review_record import build_empty_review_record, validate_review_record
from quillan.review_record_paths import (
    review_record_path,
    write_review_record,
)
from quillan.storage import assignment_config_path
from quillan.submission_manifest import validate_submission_manifest
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)
from quillan.work_paths import (
    initialize_student_submission_dir,
    quillan_work_ref,
)

PLAIN_PAPER_ENTRY_METHOD = "plain_paper_manual"
PLAIN_PAPER_PHYSICAL_EVIDENCE_STATUS = "teacher_has_external_plain_paper"
PLAIN_PAPER_WORKFLOW = "plain_paper_submission"


class PlainPaperSubmissionError(ValueError):
    """Raised when a plain-paper submission cannot be safely created."""


@dataclass(frozen=True, slots=True)
class CreatedPlainPaperSubmission:
    """Paths and identity for a newly created plain-paper submission."""

    class_id: str
    assignment_id: str
    student_id: str
    submission_manifest_path: Path
    submission_manifest_relative_path: str
    review_record_path: Path
    review_record_relative_path: str
    created_at: str


@dataclass(frozen=True, slots=True)
class PlainPaperSubmissionPlan:
    """Validated target paths for a plain-paper submission."""

    class_id: str
    assignment_id: str
    student_id: str
    submission_manifest_path: Path
    submission_manifest_relative_path: str
    review_record_path: Path
    review_record_relative_path: str


def plan_plain_paper_submission(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> PlainPaperSubmissionPlan:
    """Validate a plain-paper submission request without writing files."""
    root = Path(workspace_root).resolve(strict=False)
    for value, field in (
        (class_id, "class_id"),
        (assignment_id, "assignment_id"),
        (student_id, "student_id"),
    ):
        validate_identifier(value, field)

    assignment = load_assignment_config(
        assignment_config_path(root, class_id, assignment_id)
    )
    if assignment["assignment_id"] != assignment_id:
        raise PlainPaperSubmissionError(
            "The selected assignment ID does not match its assignment config."
        )
    if class_id not in assignment["class_ids"]:
        raise PlainPaperSubmissionError(
            f"Class {class_id!r} is not included in assignment {assignment_id!r}."
        )

    roster = load_class_roster(root, class_id)
    if not any(student.student_id == student_id for student in roster.students):
        raise PlainPaperSubmissionError(
            f"Student {student_id!r} is not in the roster for class {class_id!r}."
        )

    manifest_path = submission_manifest_path(root, class_id, assignment_id, student_id)
    review_path = review_record_path(root, class_id, assignment_id, student_id)
    if manifest_path.exists():
        raise PlainPaperSubmissionError(
            "A submission record already exists for this student. "
            "Plain-paper submission was not created."
        )
    if review_path.exists():
        raise PlainPaperSubmissionError(
            "A review record exists without a submission manifest. "
            "Plain-paper submission was not created. Repair this student "
            "submission before continuing."
        )

    return PlainPaperSubmissionPlan(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        submission_manifest_path=manifest_path,
        submission_manifest_relative_path=manifest_path.relative_to(root).as_posix(),
        review_record_path=review_path,
        review_record_relative_path=review_path.relative_to(root).as_posix(),
    )


def create_plain_paper_submission(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    created_at: datetime | str | None = None,
) -> CreatedPlainPaperSubmission:
    """Create an evidence-less manifest and empty v2 review record safely."""
    plan = plan_plain_paper_submission(
        workspace_root, class_id, assignment_id, student_id
    )

    timestamp = _timestamp(created_at)
    manifest: dict[str, Any] = {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
        "expected_pages": None,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "module_details": {
            "submission_entry_method": PLAIN_PAPER_ENTRY_METHOD,
            "physical_evidence_status": PLAIN_PAPER_PHYSICAL_EVIDENCE_STATUS,
            "created_by_workflow": PLAIN_PAPER_WORKFLOW,
        },
    }
    review = build_empty_review_record(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        created_at=timestamp,
    )
    review["module_details"] = {
        "review_entry_method": PLAIN_PAPER_ENTRY_METHOD,
        "created_by_workflow": PLAIN_PAPER_WORKFLOW,
    }
    validate_submission_manifest(manifest)
    validate_review_record(review)

    initialize_student_submission_dir(
        workspace_root,
        quillan_work_ref(class_id, assignment_id),
        student_id,
    )
    write_submission_manifest(plan.submission_manifest_path, manifest)
    try:
        write_review_record(plan.review_record_path, review)
    except Exception:
        # Restore the original no-record state if the paired write cannot finish.
        plan.submission_manifest_path.unlink(missing_ok=True)
        raise

    return CreatedPlainPaperSubmission(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        submission_manifest_path=plan.submission_manifest_path,
        submission_manifest_relative_path=plan.submission_manifest_relative_path,
        review_record_path=plan.review_record_path,
        review_record_relative_path=plan.review_record_relative_path,
        created_at=timestamp,
    )


def is_plain_paper_submission(manifest: dict[str, object]) -> bool:
    """Return whether a manifest carries the plain-paper entry marker."""
    details = manifest.get("module_details")
    return isinstance(details, dict) and details.get(
        "submission_entry_method"
    ) == PLAIN_PAPER_ENTRY_METHOD


def _timestamp(value: datetime | str | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise PlainPaperSubmissionError("created_at must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise PlainPaperSubmissionError("created_at must be a datetime or string.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise PlainPaperSubmissionError(
            "created_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PlainPaperSubmissionError("created_at must be timezone-aware.")
    return value

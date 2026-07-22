"""Create review-ready submissions for work completed on plain paper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from pds_core.classes import load_class_roster
from pds_core.identifiers import validate_identifier

from quillan.record_context import (
    QuillanRecordContextError,
    load_quillan_assignment_context,
    load_quillan_student_review_context,
    ReviewLoadingPolicy,
    student_record_paths,
)
from quillan.review_record import build_empty_review_record, validate_review_record
from quillan.review_record_paths import (
    create_quillan_review_record,
)
from quillan.submission_manifest import validate_submission_manifest
from quillan.submission_manifest_paths import (
    create_quillan_submission_manifest,
)
from quillan.work_paths import (
    quillan_work_ref,
)

PLAIN_PAPER_ENTRY_METHOD = "plain_paper_manual"
PLAIN_PAPER_PHYSICAL_EVIDENCE_STATUS = "teacher_has_external_plain_paper"
PLAIN_PAPER_WORKFLOW = "plain_paper_submission"


class PlainPaperSubmissionError(ValueError):
    """Raised when a plain-paper submission cannot be safely created."""


class PlainPaperSubmissionDurabilityError(PlainPaperSubmissionError):
    """A paired creation failed with exact possible durable destinations."""

    def __init__(
        self,
        message: str,
        *,
        possible_manifest_path: Path | None,
        possible_review_path: Path | None,
    ) -> None:
        super().__init__(message)
        self.possible_manifest_path = possible_manifest_path
        self.possible_review_path = possible_review_path


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
    return _plan_plain_paper_submission(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
        require_absent=True,
    )


def _plan_plain_paper_submission(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    require_absent: bool,
) -> PlainPaperSubmissionPlan:
    root = Path(os.path.abspath(Path(workspace_root)))
    for value, field in (
        (class_id, "class_id"),
        (assignment_id, "assignment_id"),
        (student_id, "student_id"),
    ):
        validate_identifier(value, field)

    work_ref = quillan_work_ref(class_id, assignment_id)
    try:
        load_quillan_assignment_context(root, work_ref)
        paths = student_record_paths(root, work_ref, student_id)
    except QuillanRecordContextError as error:
        raise PlainPaperSubmissionError(str(error)) from error

    roster = load_class_roster(root, class_id)
    if not any(student.student_id == student_id for student in roster.students):
        raise PlainPaperSubmissionError(
            f"Student {student_id!r} is not in the roster for class {class_id!r}."
        )

    manifest_path = paths.submission_manifest_path
    review_path = paths.review_record_path
    if require_absent and os.path.lexists(manifest_path):
        raise PlainPaperSubmissionError(
            "A submission record already exists for this student. "
            "Plain-paper submission was not created."
        )
    if require_absent and os.path.lexists(review_path):
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
        submission_manifest_relative_path=paths.submission_relative_path,
        review_record_path=review_path,
        review_record_relative_path=paths.review_relative_path,
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
    plan = _plan_plain_paper_submission(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
        require_absent=False,
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
    manifest_bytes = _manifest_bytes(manifest)
    review_bytes = _review_bytes(review)

    manifest_state = _record_state(plan.submission_manifest_path, manifest_bytes)
    review_state = _record_state(plan.review_record_path, review_bytes)
    if (manifest_state, review_state) != ("absent", "absent"):
        if (manifest_state, review_state) == ("installed", "installed"):
            detail = "The exact durable plain-paper pair already exists."
        elif manifest_state == "absent" and review_state != "absent":
            detail = "A review exists without a submission manifest."
        else:
            detail = (
                "Existing plain-paper destinations are incomplete or contradictory "
                f"(manifest={manifest_state}, review={review_state})."
            )
        raise PlainPaperSubmissionDurabilityError(
            f"Plain-paper submission already exists or requires repair. {detail}",
            possible_manifest_path=(
                plan.submission_manifest_path if manifest_state != "absent" else None
            ),
            possible_review_path=(
                plan.review_record_path if review_state != "absent" else None
            ),
        )

    work_ref = quillan_work_ref(class_id, assignment_id)
    assignment_context = load_quillan_assignment_context(workspace_root, work_ref)
    try:
        create_quillan_submission_manifest(
            assignment_context, student_id, manifest
        )
    except Exception as error:
        possible_manifest = getattr(error, "possibly_durable_path", None)
        raise PlainPaperSubmissionDurabilityError(
            f"Could not create plain-paper submission manifest: {error}",
            possible_manifest_path=possible_manifest,
            possible_review_path=None,
        ) from error

    try:
        review_context = load_quillan_student_review_context(
            workspace_root,
            work_ref,
            student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_MUST_BE_ABSENT,
        )
        create_quillan_review_record(review_context, review)
    except Exception as error:
        review_state = _record_state(plan.review_record_path, review_bytes)
        if review_state == "absent":
            compensation_error = _compensate_owned_manifest(
                plan.submission_manifest_path,
                manifest_bytes,
                plan.review_record_path,
            )
            if compensation_error is None:
                possible_manifest_path = None
                possible_review_path = None
            else:
                error.add_note(compensation_error)
                possible_manifest_path = (
                    plan.submission_manifest_path
                    if os.path.lexists(plan.submission_manifest_path)
                    else None
                )
                post_compensation_review_state = _record_state(
                    plan.review_record_path, review_bytes
                )
                possible_review_path = (
                    plan.review_record_path
                    if post_compensation_review_state != "absent"
                    else None
                )
        else:
            compensation_error = None
            possible_manifest_path = plan.submission_manifest_path
            possible_review_path = plan.review_record_path
        diagnostic = (
            f" Compensation diagnostic: {compensation_error}"
            if compensation_error is not None
            else ""
        )
        raise PlainPaperSubmissionDurabilityError(
            f"Could not create paired plain-paper records: {error}. "
            f"Review state: {review_state}.{diagnostic}",
            possible_manifest_path=possible_manifest_path,
            possible_review_path=possible_review_path,
        ) from error

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


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            manifest,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _review_bytes(review: dict[str, Any]) -> bytes:
    return (
        json.dumps(review, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")


def _record_state(path: Path, expected: bytes) -> str:
    """Classify one paired destination without treating uncertainty as absence."""
    try:
        is_junction = getattr(path, "is_junction", None)
        if not os.path.lexists(path):
            return "absent"
        if (
            path.is_symlink()
            or bool(is_junction is not None and is_junction())
            or not path.is_file()
        ):
            return "contradictory"
        return "installed" if path.read_bytes() == expected else "contradictory"
    except OSError:
        return "uncertain"


def _compensate_owned_manifest(
    manifest_path: Path,
    expected_manifest_bytes: bytes,
    review_path: Path,
) -> str | None:
    """Remove only this operation's manifest while holding the review create guard."""
    review_lock = review_path.parent / f".{review_path.name}.create.lock"
    token = b"quillan-plain-paper-compensation-v1\0" + os.urandom(32)
    try:
        with review_lock.open("xb") as lock_file:
            lock_file.write(token)
            lock_file.flush()
            os.fsync(lock_file.fileno())
    except OSError as error:
        return f"Could not acquire review compensation guard {review_lock}: {error}"

    diagnostic: str | None = None
    try:
        diagnostic = _compensate_manifest_under_guard(
            manifest_path,
            expected_manifest_bytes,
            review_path,
        )
    finally:
        primary_error = sys.exception()
        try:
            if review_lock.read_bytes() != token:
                raise OSError("review compensation guard ownership changed")
            review_lock.unlink()
        except OSError as error:
            lock_diagnostic = (
                f"Possible stale review compensation guard {review_lock}: {error}"
            )
            if primary_error is not None:
                primary_error.add_note(lock_diagnostic)
            else:
                diagnostic = (
                    lock_diagnostic
                    if diagnostic is None
                    else f"{diagnostic}; {lock_diagnostic}"
                )
    return diagnostic


def _compensate_manifest_under_guard(
    manifest_path: Path,
    expected_manifest_bytes: bytes,
    review_path: Path,
) -> str | None:
    displaced = manifest_path.parent / (
        f".{manifest_path.name}.plain-paper-compensation."
        f"{os.urandom(16).hex()}.displaced"
    )
    try:
        if _record_state(review_path, b"") != "absent":
            return f"Review destination is no longer definitely absent: {review_path}"
        if _record_state(manifest_path, expected_manifest_bytes) != "installed":
            return (
                "Manifest no longer contains the exact bytes installed by this "
                f"operation: {manifest_path}"
            )
        os.replace(manifest_path, displaced)
        if displaced.read_bytes() != expected_manifest_bytes:
            _restore_displaced_manifest(displaced, manifest_path)
            return f"Manifest changed during compensation and was preserved: {manifest_path}"
        if os.path.lexists(manifest_path):
            displaced.unlink()
            return (
                "A concurrent manifest now owns the canonical destination; only the "
                f"current operation's displaced bytes were removed: {manifest_path}"
            )
        displaced.unlink()
        if os.path.lexists(manifest_path):
            return f"A concurrent manifest was preserved after compensation: {manifest_path}"
        if _record_state(review_path, b"") != "absent":
            return f"Review appeared during guarded compensation: {review_path}"
        return None
    except OSError as error:
        if os.path.lexists(displaced):
            try:
                _restore_displaced_manifest(displaced, manifest_path)
            except OSError as restore_error:
                error.add_note(f"Manifest restore also failed: {restore_error}")
        return f"Manifest compensation failed: {error}"


def _restore_displaced_manifest(displaced: Path, target: Path) -> None:
    if os.path.lexists(target):
        return
    try:
        os.link(displaced, target)
    except FileExistsError:
        return
    displaced.unlink()

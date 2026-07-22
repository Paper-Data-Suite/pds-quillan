"""Shared assignment-local summary helpers for Quillan exports."""

from __future__ import annotations

import re
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from pds_core.classes import load_class_roster
from pds_core.rosters import RosterError, StudentRecord, student_display_name
from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.routing_models import ModuleWorkRef

from quillan.assignments import AssignmentConfigError
from quillan.record_context import (
    InvalidReviewError,
    InvalidSubmissionError,
    MissingSubmissionError,
    OrphanReviewError,
    QuillanRecordContextError,
    RecordIdentityMismatchError,
    ReviewLoadingPolicy,
    load_quillan_assignment_context,
    load_quillan_student_review_context,
    mutable_json_copy,
    student_record_paths,
)
from quillan.work_paths import (
    quillan_work_paths,
    quillan_work_ref,
    review_record_path as canonical_review_record_path,
    student_submission_dir,
    submission_manifest_path as canonical_submission_manifest_path,
)


@dataclass(frozen=True, slots=True)
class SummaryStudent:
    """One student row candidate for assignment-local summaries."""

    student_id: str
    display_name: str
    roster_status: str
    student_dir: Path
    workspace_root: Path
    work_ref: ModuleWorkRef


@dataclass(frozen=True, slots=True)
class LoadedStudentRecord:
    """Submission and review data loaded for one student row."""

    student: SummaryStudent
    submission_manifest_path: Path
    review_record_path: Path
    submission: dict[str, Any] | None
    review: dict[str, Any] | None
    submission_valid: str
    review_valid: str
    warnings: tuple[str, ...]


def assignment_path(workspace_root: Path, class_id: str, assignment_id: str) -> Path:
    return quillan_work_paths(workspace_root, class_id, assignment_id).assignment_path


def submissions_dir(workspace_root: Path, class_id: str, assignment_id: str) -> Path:
    return quillan_work_paths(workspace_root, class_id, assignment_id).submissions_dir


def load_assignment(workspace_root: Path, class_id: str, assignment_id: str) -> dict[str, Any]:
    try:
        context = load_quillan_assignment_context(
            workspace_root, quillan_work_ref(class_id, assignment_id)
        )
        assignment = mutable_json_copy(context.assignment)
    except (OSError, AssignmentConfigError, QuillanRecordContextError) as error:
        raise ValueError(f"Could not load assignment config: {error}") from error
    if class_id not in assignment["class_ids"]:
        raise ValueError(f"Assignment {assignment_id!r} is not configured for class {class_id!r}.")
    return assignment


def discover_students(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> tuple[SummaryStudent, ...]:
    base_submissions_dir = submissions_dir(workspace_root, class_id, assignment_id)
    submission_ids = _submission_ids(base_submissions_dir)
    roster_students = _roster_students(workspace_root, class_id)
    work_ref = quillan_work_ref(class_id, assignment_id)
    students: list[SummaryStudent] = []

    if roster_students is not None:
        roster_ids = set()
        for roster_student in roster_students:
            roster_ids.add(roster_student.student_id)
            students.append(
                SummaryStudent(
                    student_id=roster_student.student_id,
                    display_name=student_display_name(roster_student),
                    roster_status="rostered",
                    student_dir=student_submission_dir(
                        workspace_root, work_ref, roster_student.student_id
                    ),
                    workspace_root=workspace_root,
                    work_ref=work_ref,
                )
            )
        for student_id in sorted(submission_ids - roster_ids):
            students.append(
                SummaryStudent(
                    student_id=student_id,
                    display_name=student_id,
                    roster_status="unrostered_submission",
                    student_dir=student_submission_dir(
                        workspace_root, work_ref, student_id
                    ),
                    workspace_root=workspace_root,
                    work_ref=work_ref,
                )
            )
        return tuple(students)

    return tuple(
        SummaryStudent(
            student_id=student_id,
            display_name=student_id,
            roster_status="roster_unavailable",
            student_dir=student_submission_dir(workspace_root, work_ref, student_id),
            workspace_root=workspace_root,
            work_ref=work_ref,
        )
        for student_id in sorted(submission_ids)
    )


def load_student_record(
    student: SummaryStudent,
    class_id: str,
    assignment_id: str,
) -> LoadedStudentRecord:
    warnings: list[str] = []
    if student.roster_status == "unrostered_submission":
        warnings.append("unrostered_submission")

    try:
        paths = student_record_paths(
            student.workspace_root, student.work_ref, student.student_id
        )
    except QuillanRecordContextError:
        return LoadedStudentRecord(
            student,
            canonical_submission_manifest_path(
                student.workspace_root, student.work_ref, student.student_id
            ),
            canonical_review_record_path(
                student.workspace_root, student.work_ref, student.student_id
            ),
            None,
            None,
            "false",
            "false",
            tuple((*warnings, "unsafe_path")),
        )
    manifest_path = paths.submission_manifest_path
    review_path = paths.review_record_path
    submission: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    submission_valid = "false"
    review_valid = "false"

    try:
        context = load_quillan_student_review_context(
            student.workspace_root,
            student.work_ref,
            student.student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
        )
    except MissingSubmissionError:
        warnings.append("missing_submission")
    except OrphanReviewError:
        warnings.extend(("missing_submission", "invalid_review", "orphan_review"))
    except InvalidSubmissionError:
        warnings.append("invalid_submission")
    except InvalidReviewError as error:
        if error.submission_record is not None:
            submission = mutable_json_copy(error.submission_record.value)
            submission_valid = "true"
        warnings.append("invalid_review")
    except RecordIdentityMismatchError:
        warnings.append("identity_mismatch")
    except QuillanRecordContextError:
        warnings.append("unsafe_path")
    else:
        submission = mutable_json_copy(context.submission)
        submission_valid = "true"
        if context.review is None:
            warnings.append("missing_review")
        else:
            review = mutable_json_copy(context.review)
            review_valid = "true"

    return LoadedStudentRecord(
        student=student,
        submission_manifest_path=manifest_path,
        review_record_path=review_path,
        submission=submission if submission_valid == "true" else None,
        review=review if review_valid == "true" else None,
        submission_valid=submission_valid,
        review_valid=review_valid,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def standard_column_keys(standard_ids: list[str]) -> tuple[dict[str, str], tuple[str, ...]]:
    keys: dict[str, str] = {}
    warnings: list[str] = []
    used: dict[str, str] = {}
    for standard_id in standard_ids:
        base_key = re.sub(r"[^A-Za-z0-9_-]", "_", standard_id)
        key = base_key
        if key in used and used[key] != standard_id:
            warnings.append("standard_column_key_collision")
            suffix = 2
            while f"{base_key}_{suffix}" in used:
                suffix += 1
            key = f"{base_key}_{suffix}"
        used[key] = standard_id
        keys[standard_id] = key
    return keys, tuple(warnings)


def rating_labels(assignment: dict[str, Any]) -> dict[int, str]:
    return {
        int(level["value"]): str(level["label"])
        for level in assignment["rating_scale"]["levels"]
    }


def rating_values(assignment: dict[str, Any]) -> tuple[int, ...]:
    return tuple(int(level["value"]) for level in assignment["rating_scale"]["levels"])


def feedback_status(
    workspace_root: Path,
    review: dict[str, Any] | None,
    field: str,
    default_path: Path,
) -> tuple[str, str, str, tuple[str, ...]]:
    warnings: list[str] = []
    relative_path = relative_path_for(default_path, workspace_root)
    metadata = None if review is None else review["exports"].get(field)
    if isinstance(metadata, dict):
        relative_path = str(metadata["path"])
        file_path = workspace_root / relative_path
        if not file_path.is_file():
            warnings.append(f"{field}_file_missing")
            return relative_path, "missing", "false", tuple(warnings)
        if review is not None and metadata["source_review_updated_at"] != review["updated_at"]:
            warnings.append(f"{field}_stale")
            return relative_path, "stale", "true", tuple(warnings)
        return relative_path, "present", "false", tuple(warnings)

    if default_path.is_file():
        warnings.append(f"{field}_metadata_missing")
        return relative_path, "unknown", "unknown", tuple(warnings)
    return relative_path, "missing", "false", tuple(warnings)


def relative_path_for(path: Path, workspace_root: Path) -> str:
    return Path(os.path.abspath(path)).relative_to(workspace_root).as_posix()


def _submission_ids(path: Path) -> set[str]:
    try:
        if not os.path.lexists(path):
            return set()
        if _is_link_like(path) or not path.is_dir():
            raise ValueError("Submission collection is not an ordinary directory.")
        identifiers: set[str] = set()
        for entry in path.iterdir():
            if _is_link_like(entry) or not entry.is_dir():
                raise ValueError(
                    f"Invalid direct submission child: {entry.name}"
                )
            try:
                identifiers.add(validate_identifier(entry.name, "student_id"))
            except IdentifierValidationError as error:
                raise ValueError(
                    f"Invalid student submission child: {entry.name}"
                ) from error
        return identifiers
    except (FileNotFoundError, NotADirectoryError):
        return set()
    except OSError as error:
        raise ValueError(f"Could not discover student submission directories: {error}") from error


def _roster_students(workspace_root: Path, class_id: str) -> tuple[StudentRecord, ...] | None:
    try:
        return load_class_roster(workspace_root, class_id).students
    except (OSError, RosterError):
        return None


def _has_identity_mismatch(
    record: dict[str, Any],
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> bool:
    return any(
        record[field] != expected
        for field, expected in (
            ("class_id", class_id),
            ("assignment_id", assignment_id),
            ("student_id", student_id),
        )
    )


def _is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction is not None and is_junction())

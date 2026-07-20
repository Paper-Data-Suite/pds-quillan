"""Shared assignment-local summary helpers for Quillan exports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pds_core.classes import load_class_roster
from pds_core.rosters import RosterError, StudentRecord, student_display_name

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.review_record import ReviewRecordError, load_review_record
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.storage import assignment_config_path, assignment_submissions_dir


@dataclass(frozen=True, slots=True)
class SummaryStudent:
    """One student row candidate for assignment-local summaries."""

    student_id: str
    display_name: str
    roster_status: str
    student_dir: Path


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
    return assignment_config_path(workspace_root, class_id, assignment_id)


def submissions_dir(workspace_root: Path, class_id: str, assignment_id: str) -> Path:
    return assignment_submissions_dir(workspace_root, class_id, assignment_id)


def load_assignment(workspace_root: Path, class_id: str, assignment_id: str) -> dict[str, Any]:
    try:
        assignment = load_assignment_config(assignment_path(workspace_root, class_id, assignment_id))
    except (OSError, AssignmentConfigError) as error:
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
                    student_dir=base_submissions_dir / roster_student.student_id,
                )
            )
        for student_id in sorted(submission_ids - roster_ids):
            students.append(
                SummaryStudent(
                    student_id=student_id,
                    display_name=student_id,
                    roster_status="unrostered_submission",
                    student_dir=base_submissions_dir / student_id,
                )
            )
        return tuple(students)

    return tuple(
        SummaryStudent(
            student_id=student_id,
            display_name=student_id,
            roster_status="roster_unavailable",
            student_dir=base_submissions_dir / student_id,
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

    manifest_path = student.student_dir / "submission.json"
    review_path = student.student_dir / "review.json"
    submission: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    submission_valid = "false"
    review_valid = "false"

    if not manifest_path.is_file():
        warnings.append("missing_submission")
    else:
        try:
            submission = load_submission_manifest(manifest_path)
            submission_valid = "true"
        except (OSError, SubmissionManifestError):
            warnings.append("invalid_submission")
        if submission is not None and _has_identity_mismatch(
            submission, class_id, assignment_id, student.student_id
        ):
            warnings.append("identity_mismatch")
            submission_valid = "false"

    if submission_valid == "true":
        if not review_path.is_file():
            warnings.append("missing_review")
        else:
            try:
                review = load_review_record(review_path)
                review_valid = "true"
            except (OSError, ReviewRecordError):
                warnings.append("invalid_review")
            if review is not None and _has_identity_mismatch(
                review, class_id, assignment_id, student.student_id
            ):
                warnings.append("identity_mismatch")
                review_valid = "false"

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
    return path.resolve(strict=False).relative_to(workspace_root).as_posix()


def _submission_ids(path: Path) -> set[str]:
    try:
        return {entry.name for entry in path.iterdir() if entry.is_dir()}
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

"""Read-only context and constrained input validation for review units."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from quillan.record_context import (
    QuillanRecordContextError,
    QuillanStudentReviewContext,
    ReviewLoadingPolicy,
    load_quillan_student_review_context,
    mutable_json_copy,
)
from quillan.work_paths import quillan_work_ref

_ALLOWED_UNIT_FIELDS = frozenset({"sequence", "label", "page_number", "evidence_id"})


class ReviewUnitManagementError(ValueError):
    """Raised when review-unit context or input is invalid."""


@dataclass(frozen=True, slots=True)
class ReviewUnitDefinition:
    """One current canonical review unit and its observation count."""

    sequence: int
    unit_id: str
    label: str
    unit_type: str
    page_number: int | None
    evidence_id: str | None
    observation_count: int


@dataclass(frozen=True, slots=True)
class ReviewUnitContext:
    """Validated canonical assignment, submission, and optional review context."""

    workspace_root: Path
    class_id: str
    assignment_id: str
    student_id: str
    assignment_path: Path
    submission_manifest_path: Path
    review_record_path: Path
    assignment: dict[str, Any]
    manifest: dict[str, Any]
    review: dict[str, Any] | None
    record_context: QuillanStudentReviewContext

    @property
    def unit_type(self) -> str:
        return cast(str, self.assignment["review_unit"]["type"])

    @property
    def singular_label(self) -> str:
        return cast(str, self.assignment["review_unit"]["singular_label"])

    @property
    def plural_label(self) -> str:
        return cast(str, self.assignment["review_unit"]["plural_label"])

    @property
    def review_state(self) -> str:
        return cast(str, self.review["review_state"]) if self.review else "not_started"

    @property
    def submission_manifest_relative_path(self) -> str:
        return _relative(self.submission_manifest_path, self.workspace_root, "submission manifest")

    @property
    def review_record_relative_path(self) -> str:
        return _relative(self.review_record_path, self.workspace_root, "review record")

    @property
    def units(self) -> tuple[ReviewUnitDefinition, ...]:
        if self.review is None:
            return ()
        return tuple(
            ReviewUnitDefinition(
                sequence=unit["sequence"],
                unit_id=unit["unit_id"],
                label=unit["label"],
                unit_type=unit["unit_type"],
                page_number=unit.get("page_number"),
                evidence_id=unit.get("evidence_id"),
                observation_count=len(unit["standard_observations"]),
            )
            for unit in self.review["review_units"]
        )

    @property
    def observation_count(self) -> int:
        return sum(unit.observation_count for unit in self.units)


def load_review_unit_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> ReviewUnitContext:
    """Load canonical review-unit context without writing anything."""
    try:
        loaded = load_quillan_student_review_context(
            workspace_root,
            quillan_work_ref(class_id, assignment_id),
            student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
        )
    except (QuillanRecordContextError, OSError, RuntimeError, ValueError) as error:
        raise ReviewUnitManagementError(str(error)) from error

    root = loaded.paths.workspace_root
    assignment = mutable_json_copy(loaded.assignment_context.assignment)
    manifest = mutable_json_copy(loaded.submission)
    review = None if loaded.review is None else mutable_json_copy(loaded.review)

    return ReviewUnitContext(
        workspace_root=root,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        assignment_path=loaded.assignment_context.paths.assignment_path,
        submission_manifest_path=loaded.paths.submission_manifest_path,
        review_record_path=loaded.paths.review_record_path,
        assignment=assignment,
        manifest=manifest,
        review=review,
        record_context=loaded,
    )


def load_review_unit_definitions_file(path: str | Path) -> list[dict[str, Any]]:
    """Read a UTF-8 JSON unit-description file and validate its basic shape."""
    input_path = Path(path)
    try:
        with input_path.open("r", encoding="utf-8") as file:
            value = json.load(file)
    except FileNotFoundError as error:
        raise ReviewUnitManagementError(f"Review-unit input file not found: {input_path}") from error
    except json.JSONDecodeError as error:
        raise ReviewUnitManagementError(
            f"Review-unit input file is not valid JSON: {input_path}"
        ) from error
    except (OSError, UnicodeError) as error:
        raise ReviewUnitManagementError(
            f"Could not read review-unit input file {input_path}: {error}"
        ) from error
    if not isinstance(value, list):
        raise ReviewUnitManagementError("Review-unit input root must be a JSON array.")
    return cast(list[dict[str, Any]], value)


def validate_review_unit_definitions(
    units: list[Any], manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    """Validate constrained unit descriptions against manifest metadata."""
    if not units:
        raise ReviewUnitManagementError("Review-unit input array must not be empty.")
    pages = {page["page_number"]: page for page in manifest["pages"]}
    evidence_pages = {
        evidence["evidence_id"]: page["page_number"]
        for page in manifest["pages"]
        for evidence in page["evidence"]
    }
    normalized: list[dict[str, Any]] = []
    sequences: set[int] = set()
    for index, value in enumerate(units):
        context = f"units[{index}]"
        if not isinstance(value, dict):
            raise ReviewUnitManagementError(f"{context} must be an object.")
        unknown = sorted(set(value) - _ALLOWED_UNIT_FIELDS)
        if unknown:
            raise ReviewUnitManagementError(
                f"{context} contains prohibited or unknown field {unknown[0]!r}."
            )
        if "sequence" not in value:
            raise ReviewUnitManagementError(f"{context} is missing required field 'sequence'.")
        sequence = value["sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ReviewUnitManagementError(f"{context}.sequence must be a positive integer.")
        if sequence in sequences:
            raise ReviewUnitManagementError(f"Duplicate review-unit sequence: {sequence}.")
        sequences.add(sequence)
        item: dict[str, Any] = {"sequence": sequence}

        if "label" in value:
            label = value["label"]
            if not isinstance(label, str) or not label.strip():
                raise ReviewUnitManagementError(f"{context}.label must be a non-empty string.")
            item["label"] = label.strip()
        if "page_number" in value:
            page_number = value["page_number"]
            if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
                raise ReviewUnitManagementError(f"{context}.page_number must be a positive integer.")
            if page_number not in pages:
                raise ReviewUnitManagementError(
                    f"{context}.page_number {page_number} is not present in the submission manifest."
                )
            item["page_number"] = page_number
        if "evidence_id" in value:
            evidence_id = value["evidence_id"]
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                raise ReviewUnitManagementError(f"{context}.evidence_id must be a non-empty string.")
            evidence_id = evidence_id.strip()
            if evidence_id not in evidence_pages:
                raise ReviewUnitManagementError(
                    f"{context}.evidence_id {evidence_id!r} is not present in the submission manifest."
                )
            if "page_number" in item and evidence_pages[evidence_id] != item["page_number"]:
                raise ReviewUnitManagementError(
                    f"{context}.evidence_id {evidence_id!r} does not belong to page {item['page_number']}."
                )
            item["evidence_id"] = evidence_id
        normalized.append(item)
    return sorted(normalized, key=lambda item: cast(int, item["sequence"]))


def _validate_identity(
    record: dict[str, Any], name: str, class_id: str, assignment_id: str, student_id: str
) -> None:
    for field, expected in {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }.items():
        if record[field] != expected:
            raise ReviewUnitManagementError(
                f"{name} {field} is {record[field]!r}, expected {expected!r}."
            )


def _relative(path: Path, root: Path, name: str) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise ReviewUnitManagementError(
            f"Canonical {name} path is outside the workspace root."
        ) from error

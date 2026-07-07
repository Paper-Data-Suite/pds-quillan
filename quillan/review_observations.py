"""Review-unit and Focus Standard observation mutation helpers."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.review_record import (
    ReviewRecordError,
    build_empty_review_record,
    load_review_record,
    validate_review_record,
)
from quillan.review_record_paths import (
    ReviewRecordPathError,
    review_record_path,
    write_review_record,
)
from quillan.storage import assignment_config_path
from quillan.submission_guidance import missing_submission_guidance
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
)

_SEQUENTIAL_OBSERVATION_ID = re.compile(r"^observation_(\d{4})$")


class ReviewObservationError(Exception):
    """Raised when review-unit observations cannot be changed safely."""


@dataclass(frozen=True, slots=True)
class UpdatedReviewUnits:
    """Information about review units written to a review record."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    review_state: str
    unit_count: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class UpdatedReviewUnitObservation:
    """Information about one Focus Standard observation update."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    review_state: str
    unit_id: str
    unit_label: str
    standard_id: str
    observation_id: str
    applicable: bool
    evidence_present: bool | None
    include_in_feedback: bool
    was_created: bool
    updated_at: str


@dataclass(frozen=True, slots=True)
class CompletedReviewUnitObservations:
    """Information about an observations-complete review-state update."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    review_state: str
    unit_count: int
    observation_count: int
    missing_focus_standard_pairs: int
    updated_at: str


def set_review_units(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    units: list[dict[str, Any]],
    *,
    updated_at: datetime | str | None = None,
) -> UpdatedReviewUnits:
    """Create or replace review units for one assembled student submission."""
    normalized_updated_at = _normalize_timestamp(updated_at)
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    assignment = context["assignment"]
    review = _load_or_create_review(context, normalized_updated_at)
    _guard_returned_without_full_review(review)

    existing_by_id = {
        unit["unit_id"]: unit
        for unit in review["review_units"]
        if isinstance(unit, dict) and isinstance(unit.get("unit_id"), str)
    }
    canonical_units: list[dict[str, Any]] = []
    review_unit_config = assignment["review_unit"]
    unit_type = str(review_unit_config["type"]).strip()
    singular_label = str(review_unit_config["singular_label"]).strip()
    for index, unit in enumerate(units, start=1):
        sequence = _normalize_sequence(unit.get("sequence", index), index)
        unit_id = f"{unit_type}_{sequence}"
        label = _normalize_optional_string(unit.get("label"), "label")
        if label is None:
            label = f"{_display_label(singular_label)} {sequence}"
        canonical = {
            "unit_id": unit_id,
            "sequence": sequence,
            "label": label,
            "unit_type": unit_type,
            "standard_observations": copy.deepcopy(
                existing_by_id.get(unit_id, {}).get("standard_observations", [])
            ),
            "module_details": {},
        }
        page_number = unit.get("page_number")
        if page_number is not None:
            canonical["page_number"] = _normalize_positive_int(
                page_number, "page_number"
            )
        evidence_id = _normalize_optional_string(unit.get("evidence_id"), "evidence_id")
        if evidence_id is not None:
            canonical["evidence_id"] = evidence_id
        canonical_units.append(canonical)

    review["review_units"] = canonical_units
    _drop_stale_feedback_observation_references(review)
    review["review_state"] = _observations_in_progress_state(review["review_state"])
    review["updated_at"] = normalized_updated_at

    _write_review(context, review)
    return UpdatedReviewUnits(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        review_state=review["review_state"],
        unit_count=len(canonical_units),
        updated_at=normalized_updated_at,
    )


def set_review_unit_observation(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    unit_id: str,
    standard_id: str,
    applicable: bool,
    evidence_present: bool | None,
    rationale: str | None = None,
    include_in_feedback: bool | None = None,
    rating: int | None = None,
    updated_at: datetime | str | None = None,
) -> UpdatedReviewUnitObservation:
    """Create or update one review-unit Focus Standard observation."""
    if not isinstance(applicable, bool):
        raise ReviewObservationError("applicable must be a boolean.")
    normalized_unit_id = _normalize_required_string(unit_id, "unit_id")
    normalized_standard_id = _normalize_required_string(standard_id, "standard_id")
    normalized_rationale = _normalize_optional_string(rationale, "rationale")
    normalized_updated_at = _normalize_timestamp(updated_at)
    normalized_rating = _normalize_rating(rating)
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    assignment = context["assignment"]
    if normalized_standard_id not in assignment["focus_standard_ids"]:
        raise ReviewObservationError(
            f"standard_id {normalized_standard_id!r} is not a Focus Standard for this assignment."
        )

    review = _load_existing_review(context)
    _guard_returned_without_full_review(review)
    if not review["review_units"]:
        raise ReviewObservationError("Define review units before recording observations.")
    unit = next(
        (candidate for candidate in review["review_units"] if candidate["unit_id"] == normalized_unit_id),
        None,
    )
    if unit is None:
        raise ReviewObservationError(f"Review unit not found: {normalized_unit_id}")

    if applicable:
        if not isinstance(evidence_present, bool):
            raise ReviewObservationError(
                "evidence_present must be a boolean when applicable is true."
            )
        normalized_evidence_present: bool | None = evidence_present
        normalized_include = True if include_in_feedback is None else include_in_feedback
    else:
        normalized_evidence_present = None
        normalized_rating = None
        normalized_include = False if include_in_feedback is None else include_in_feedback
    if not isinstance(normalized_include, bool):
        raise ReviewObservationError("include_in_feedback must be a boolean.")

    observations = unit["standard_observations"]
    observation = next(
        (
            candidate
            for candidate in observations
            if candidate["standard_id"] == normalized_standard_id
        ),
        None,
    )
    was_created = observation is None
    if observation is None:
        observation_id = _next_observation_id(review)
        observation = {"observation_id": observation_id}
        observations.append(observation)
    else:
        observation_id = observation["observation_id"]

    observation.clear()
    observation.update(
        {
            "observation_id": observation_id,
            "standard_id": normalized_standard_id,
            "applicable": applicable,
            "evidence_present": normalized_evidence_present,
            "rating": normalized_rating,
            "rationale": normalized_rationale,
            "include_in_feedback": normalized_include,
            "updated_at": normalized_updated_at,
            "module_details": {},
        }
    )
    review["review_state"] = _observations_in_progress_state(review["review_state"])
    review["updated_at"] = normalized_updated_at

    _write_review(context, review)
    return UpdatedReviewUnitObservation(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        review_state=review["review_state"],
        unit_id=normalized_unit_id,
        unit_label=unit["label"],
        standard_id=normalized_standard_id,
        observation_id=observation_id,
        applicable=applicable,
        evidence_present=normalized_evidence_present,
        include_in_feedback=normalized_include,
        was_created=was_created,
        updated_at=normalized_updated_at,
    )


def mark_observations_complete(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    updated_at: datetime | str | None = None,
) -> CompletedReviewUnitObservations:
    """Explicitly mark review-unit observations complete."""
    normalized_updated_at = _normalize_timestamp(updated_at)
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    review = _load_existing_review(context)
    _guard_returned_without_full_review(review)
    if not review["review_units"]:
        raise ReviewObservationError("Define review units before marking observations complete.")

    review["review_state"] = "observations_complete"
    review["updated_at"] = normalized_updated_at
    _write_review(context, review)

    focus_count = len(context["assignment"]["focus_standard_ids"])
    observation_count = _count_observations(review)
    return CompletedReviewUnitObservations(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        review_state=review["review_state"],
        unit_count=len(review["review_units"]),
        observation_count=observation_count,
        missing_focus_standard_pairs=max(
            len(review["review_units"]) * focus_count - observation_count, 0
        ),
        updated_at=normalized_updated_at,
    )


def _load_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> dict[str, Any]:
    try:
        resolved_root = Path(workspace_root).resolve(strict=False)
        manifest_path = submission_manifest_path(
            resolved_root, class_id, assignment_id, student_id
        )
        record_path = review_record_path(
            resolved_root, class_id, assignment_id, student_id
        )
        assignment_path = assignment_config_path(resolved_root, class_id, assignment_id)
    except (
        OSError,
        RuntimeError,
        SubmissionManifestPathError,
        ReviewRecordPathError,
    ) as error:
        raise ReviewObservationError(str(error)) from error

    if not manifest_path.exists():
        raise ReviewObservationError(missing_submission_guidance())

    try:
        manifest = load_submission_manifest(manifest_path)
        assignment = load_assignment_config(assignment_path)
    except (OSError, SubmissionManifestError, AssignmentConfigError) as error:
        raise ReviewObservationError(str(error)) from error

    _validate_identity(
        manifest,
        record_name="Submission manifest",
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )
    if class_id not in assignment["class_ids"]:
        raise ReviewObservationError(
            f"Assignment config class_ids does not include {class_id!r}."
        )
    if assignment["assignment_id"] != assignment_id:
        raise ReviewObservationError(
            f"Assignment config assignment_id is {assignment['assignment_id']!r}, expected {assignment_id!r}."
        )

    return {
        "workspace_root": resolved_root,
        "manifest_path": manifest_path,
        "record_path": record_path,
        "assignment_path": assignment_path,
        "assignment": assignment,
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }


def _load_or_create_review(context: dict[str, Any], created_at: str) -> dict[str, Any]:
    record_path = context["record_path"]
    if record_path.exists():
        return _load_existing_review(context)
    return build_empty_review_record(
        class_id=context["class_id"],
        assignment_id=context["assignment_id"],
        student_id=context["student_id"],
        submission_manifest_path=_workspace_relative_path(
            context["manifest_path"], context["workspace_root"], "submission manifest"
        ),
        assignment_path=_workspace_relative_path(
            context["assignment_path"], context["workspace_root"], "assignment"
        ),
        created_at=created_at,
    )


def _load_existing_review(context: dict[str, Any]) -> dict[str, Any]:
    record_path = context["record_path"]
    if not record_path.exists():
        raise ReviewObservationError("Review units must be defined before recording observations.")
    try:
        review = load_review_record(record_path)
    except (OSError, ReviewRecordError) as error:
        raise ReviewObservationError(f"Could not load review record: {error}") from error
    _validate_identity(
        review,
        record_name="Review record",
        class_id=context["class_id"],
        assignment_id=context["assignment_id"],
        student_id=context["student_id"],
    )
    return copy.deepcopy(review)


def _write_review(context: dict[str, Any], review: dict[str, Any]) -> None:
    try:
        validate_review_record(review)
        write_review_record(
            context["record_path"],
            review,
            overwrite=context["record_path"].exists(),
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        ReviewRecordError,
        ReviewRecordPathError,
    ) as error:
        raise ReviewObservationError(f"Could not write review record: {error}") from error


def _guard_returned_without_full_review(review: dict[str, Any]) -> None:
    if review["review_state"] == "returned_without_full_review":
        raise ReviewObservationError(
            "This submission was returned without full standards review. "
            "Change the minimum-requirements outcome before continuing with observations."
        )


def _observations_in_progress_state(current_state: str) -> str:
    if current_state in {"not_started", "requirements_checked", "observations_complete"}:
        return "observations_in_progress"
    if current_state == "observations_in_progress":
        return current_state
    return current_state


def _drop_stale_feedback_observation_references(review: dict[str, Any]) -> None:
    valid_ids = {
        observation["observation_id"]
        for unit in review["review_units"]
        for observation in unit["standard_observations"]
    }
    for item in review["feedback"]["standard_feedback"]:
        item["included_observation_ids"] = [
            observation_id
            for observation_id in item["included_observation_ids"]
            if observation_id in valid_ids
        ]


def _next_observation_id(review: dict[str, Any]) -> str:
    existing_ids = {
        observation["observation_id"]
        for unit in review["review_units"]
        for observation in unit["standard_observations"]
    }
    highest = max(
        (
            int(match.group(1))
            for observation_id in existing_ids
            if (match := _SEQUENTIAL_OBSERVATION_ID.fullmatch(observation_id))
        ),
        default=0,
    )
    candidate_number = highest + 1
    while True:
        candidate = f"observation_{candidate_number:04d}"
        if candidate not in existing_ids:
            return candidate
        candidate_number += 1


def _count_observations(review: dict[str, Any]) -> int:
    return sum(len(unit["standard_observations"]) for unit in review["review_units"])


def _normalize_sequence(value: Any, index: int) -> int:
    if value is None:
        return index
    return _normalize_positive_int(value, "sequence")


def _normalize_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ReviewObservationError(f"{field} must be a positive integer.")
    return value


def _normalize_rating(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReviewObservationError("rating must be an integer or null.")
    return value


def _normalize_required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewObservationError(f"{field} must be a non-empty string.")
    return value.strip()


def _normalize_optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReviewObservationError(f"{field} must be a string or null.")
    if not value.strip():
        return None
    return value.strip()


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewObservationError("updated_at datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise ReviewObservationError(
            "updated_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewObservationError(
            "updated_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewObservationError(
            "updated_at must be a timezone-aware ISO 8601 string."
        )
    return value


def _validate_identity(
    record: dict[str, Any],
    *,
    record_name: str,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    for field, expected in {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }.items():
        actual = record[field]
        if actual != expected:
            raise ReviewObservationError(
                f"{record_name} {field} is {actual!r}, expected {expected!r}."
            )


def _workspace_relative_path(
    path: Path,
    workspace_root: Path,
    description: str,
) -> str:
    try:
        return path.resolve(strict=False).relative_to(workspace_root).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise ReviewObservationError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error


def _display_label(value: str) -> str:
    return value[:1].upper() + value[1:]

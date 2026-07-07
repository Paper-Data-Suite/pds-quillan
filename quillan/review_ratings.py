"""Overall Focus Standard rating helpers."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.review_record import ReviewRecordError, load_review_record, validate_review_record
from quillan.review_record_paths import (
    ReviewRecordPathError,
    review_record_path,
    write_review_record,
)
from quillan.storage import assignment_config_path
from quillan.submission_guidance import missing_submission_guidance
from quillan.submission_manifest import SubmissionManifestError, load_submission_manifest
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
)


class ReviewRatingError(Exception):
    """Raised when overall Focus Standard ratings cannot be changed safely."""


@dataclass(frozen=True, slots=True)
class FocusStandardObservationDetail:
    """One review-unit observation note for a Focus Standard summary."""

    unit_id: str
    unit_label: str
    observation_id: str
    applicable: bool
    evidence_present: bool | None
    include_in_feedback: bool
    rationale: str | None


@dataclass(frozen=True, slots=True)
class FocusStandardObservationSummary:
    """Teacher-facing evidence summary for one assignment Focus Standard."""

    standard_id: str
    total_review_units: int
    observation_count: int
    applicable_count: int
    not_applicable_count: int
    evidence_present_count: int
    evidence_missing_count: int
    included_for_feedback_count: int
    details: tuple[FocusStandardObservationDetail, ...]
    current_rating: int | None
    current_rationale: str | None
    current_include_in_feedback: bool | None
    rating_scale_levels: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class UpdatedOverallStandardRating:
    """Information about one overall Focus Standard rating update."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    review_state: str
    standard_id: str
    rating: int
    rating_label: str
    include_in_feedback: bool
    was_created: bool
    updated_at: str


@dataclass(frozen=True, slots=True)
class CompletedOverallStandardRatings:
    """Information about an explicit overall-ratings completion update."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    review_state: str
    focus_standard_count: int
    rating_count: int
    missing_rating_count: int
    updated_at: str


def summarize_focus_standard_observations(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> tuple[FocusStandardObservationSummary, ...]:
    """Summarize recorded observations by Focus Standard without scoring."""
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    review = _load_existing_review(context)
    assignment = context["assignment"]
    rating_scale_levels = tuple(
        copy.deepcopy(level) for level in assignment["rating_scale"]["levels"]
    )
    ratings_by_standard = {
        rating["standard_id"]: rating for rating in review["overall_standard_ratings"]
    }

    summaries: list[FocusStandardObservationSummary] = []
    for standard_id in assignment["focus_standard_ids"]:
        details: list[FocusStandardObservationDetail] = []
        applicable_count = 0
        not_applicable_count = 0
        evidence_present_count = 0
        evidence_missing_count = 0
        included_count = 0
        for unit in review["review_units"]:
            for observation in unit["standard_observations"]:
                if observation["standard_id"] != standard_id:
                    continue
                if observation["applicable"]:
                    applicable_count += 1
                    if observation["evidence_present"]:
                        evidence_present_count += 1
                    else:
                        evidence_missing_count += 1
                else:
                    not_applicable_count += 1
                if observation["include_in_feedback"]:
                    included_count += 1
                details.append(
                    FocusStandardObservationDetail(
                        unit_id=unit["unit_id"],
                        unit_label=unit["label"],
                        observation_id=observation["observation_id"],
                        applicable=observation["applicable"],
                        evidence_present=observation["evidence_present"],
                        include_in_feedback=observation["include_in_feedback"],
                        rationale=observation["rationale"],
                    )
                )
        current = ratings_by_standard.get(standard_id)
        summaries.append(
            FocusStandardObservationSummary(
                standard_id=standard_id,
                total_review_units=len(review["review_units"]),
                observation_count=len(details),
                applicable_count=applicable_count,
                not_applicable_count=not_applicable_count,
                evidence_present_count=evidence_present_count,
                evidence_missing_count=evidence_missing_count,
                included_for_feedback_count=included_count,
                details=tuple(details),
                current_rating=current["rating"] if current else None,
                current_rationale=current["rationale"] if current else None,
                current_include_in_feedback=(
                    current["include_in_feedback"] if current else None
                ),
                rating_scale_levels=rating_scale_levels,
            )
        )
    return tuple(summaries)


def set_overall_standard_rating(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    standard_id: str,
    rating: int,
    rationale: str | None = None,
    include_in_feedback: bool,
    updated_at: datetime | str | None = None,
) -> UpdatedOverallStandardRating:
    """Create or update one teacher-entered overall Focus Standard rating."""
    normalized_standard_id = _normalize_required_string(standard_id, "standard_id")
    normalized_rating = _normalize_rating(rating)
    normalized_rationale = _normalize_optional_string(rationale, "rationale")
    if not isinstance(include_in_feedback, bool):
        raise ReviewRatingError("include_in_feedback must be a boolean.")
    normalized_updated_at = _normalize_timestamp(updated_at)

    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    assignment = context["assignment"]
    if normalized_standard_id not in assignment["focus_standard_ids"]:
        raise ReviewRatingError(
            f"standard_id {normalized_standard_id!r} is not a Focus Standard for this assignment."
        )
    rating_labels = _rating_labels_by_value(assignment)
    if normalized_rating not in rating_labels:
        allowed = ", ".join(str(value) for value in sorted(rating_labels))
        raise ReviewRatingError(
            f"rating {normalized_rating!r} is not in the assignment rating scale. "
            f"Allowed values: {allowed}."
        )

    review = _load_existing_review(context)
    _guard_returned_without_full_review(review)
    existing = next(
        (
            candidate
            for candidate in review["overall_standard_ratings"]
            if candidate["standard_id"] == normalized_standard_id
        ),
        None,
    )
    was_created = existing is None
    if existing is None:
        existing = {"standard_id": normalized_standard_id}
        review["overall_standard_ratings"].append(existing)
    existing.clear()
    existing.update(
        {
            "standard_id": normalized_standard_id,
            "rating": normalized_rating,
            "rationale": normalized_rationale,
            "include_in_feedback": include_in_feedback,
            "updated_at": normalized_updated_at,
            "module_details": {},
        }
    )
    review["review_state"] = _rating_update_state(review["review_state"])
    review["updated_at"] = normalized_updated_at

    _write_review(context, review)
    return UpdatedOverallStandardRating(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        review_state=review["review_state"],
        standard_id=normalized_standard_id,
        rating=normalized_rating,
        rating_label=rating_labels[normalized_rating],
        include_in_feedback=include_in_feedback,
        was_created=was_created,
        updated_at=normalized_updated_at,
    )


def mark_overall_ratings_complete(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    updated_at: datetime | str | None = None,
) -> CompletedOverallStandardRatings:
    """Explicitly mark teacher-entered overall Focus Standard ratings complete."""
    normalized_updated_at = _normalize_timestamp(updated_at)
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    review = _load_existing_review(context)
    _guard_returned_without_full_review(review)

    focus_standard_ids = context["assignment"]["focus_standard_ids"]
    rated_focus_standards = {
        rating["standard_id"]
        for rating in review["overall_standard_ratings"]
        if rating["standard_id"] in focus_standard_ids
    }
    focus_count = len(focus_standard_ids)
    rating_count = len(rated_focus_standards)
    review["review_state"] = "ratings_complete"
    review["updated_at"] = normalized_updated_at
    _write_review(context, review)

    return CompletedOverallStandardRatings(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        review_state=review["review_state"],
        focus_standard_count=focus_count,
        rating_count=rating_count,
        missing_rating_count=max(focus_count - rating_count, 0),
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
        raise ReviewRatingError(str(error)) from error

    if not manifest_path.exists():
        raise ReviewRatingError(missing_submission_guidance())
    if not record_path.exists():
        raise ReviewRatingError("A review record must exist before recording ratings.")

    try:
        manifest = load_submission_manifest(manifest_path)
        assignment = load_assignment_config(assignment_path)
    except (OSError, SubmissionManifestError, AssignmentConfigError) as error:
        raise ReviewRatingError(str(error)) from error

    _validate_identity(
        manifest,
        record_name="Submission manifest",
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )
    if class_id not in assignment["class_ids"]:
        raise ReviewRatingError(
            f"Assignment config class_ids does not include {class_id!r}."
        )
    if assignment["assignment_id"] != assignment_id:
        raise ReviewRatingError(
            f"Assignment config assignment_id is {assignment['assignment_id']!r}, expected {assignment_id!r}."
        )
    return {
        "workspace_root": resolved_root,
        "manifest_path": manifest_path,
        "record_path": record_path,
        "assignment": assignment,
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }


def _load_existing_review(context: dict[str, Any]) -> dict[str, Any]:
    try:
        review = load_review_record(context["record_path"])
    except (OSError, ReviewRecordError) as error:
        raise ReviewRatingError(f"Could not load review record: {error}") from error
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
        write_review_record(context["record_path"], review, overwrite=True)
    except (
        OSError,
        RuntimeError,
        ValueError,
        ReviewRecordError,
        ReviewRecordPathError,
    ) as error:
        raise ReviewRatingError(f"Could not write review record: {error}") from error


def _guard_returned_without_full_review(review: dict[str, Any]) -> None:
    if review["review_state"] == "returned_without_full_review":
        raise ReviewRatingError(
            "This submission was returned without full standards review. "
            "Change the minimum-requirements outcome before continuing with ratings."
        )


def _rating_update_state(current_state: str) -> str:
    if current_state in {"not_started", "requirements_checked"}:
        return "observations_in_progress"
    if current_state in {"feedback_composed", "ready_for_export", "exported"}:
        return "ratings_complete"
    return current_state


def _rating_labels_by_value(assignment: dict[str, Any]) -> dict[int, str]:
    labels: dict[int, str] = {}
    for level in assignment["rating_scale"]["levels"]:
        labels[level["value"]] = level["label"]
    return labels


def _normalize_rating(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReviewRatingError("rating must be an integer.")
    return value


def _normalize_required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewRatingError(f"{field} must be a non-empty string.")
    return value.strip()


def _normalize_optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReviewRatingError(f"{field} must be a string or null.")
    if not value.strip():
        return None
    return value.strip()


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewRatingError("updated_at datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise ReviewRatingError(
            "updated_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewRatingError(
            "updated_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewRatingError(
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
            raise ReviewRatingError(
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
        raise ReviewRatingError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error

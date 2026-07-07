"""Focus Standard feedback composition helpers."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.focus_standard_comments import (
    FocusStandardCommentError,
    SavedReusableFocusStandardComment,
    append_saved_comment,
    focus_standard_comment_set_path,
    increment_usage,
    load_comment_set,
    lookup_comments,
)
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

_SEQUENTIAL_FEEDBACK_COMMENT_ID = re.compile(r"^feedback_comment_(\d{4})$")


class ReviewFeedbackError(Exception):
    """Raised when Focus Standard feedback cannot be composed safely."""


@dataclass(frozen=True, slots=True)
class UpdatedStandardFeedbackOptions:
    """Information about one Focus Standard feedback option update."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    review_state: str
    standard_id: str
    include_overall_rating: bool
    include_overall_rationale: bool
    included_observation_count: int
    was_created: bool
    updated_at: str


@dataclass(frozen=True, slots=True)
class AddedFeedbackComment:
    """Information about one custom feedback comment added to a review."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    review_state: str
    standard_id: str
    feedback_comment_id: str
    include_in_feedback: bool
    save_for_reuse: bool
    saved_reusable_comment: SavedReusableFocusStandardComment | None
    created_at: str


@dataclass(frozen=True, slots=True)
class SelectedReusableFeedbackComment:
    """Information about one reusable comment copied into a review."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    review_state: str
    standard_id: str
    feedback_comment_id: str
    comment_set_id: str
    reusable_comment_id: str
    include_in_feedback: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class CompletedFeedbackComposition:
    """Information about an explicit feedback-composed state update."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    review_state: str
    focus_standard_count: int
    standard_feedback_count: int
    missing_standard_feedback_count: int
    included_comment_count: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class StandardFeedbackSummary:
    """Compact feedback status for one Focus Standard."""

    standard_id: str
    has_overall_rating: bool
    has_feedback_record: bool
    comment_count: int
    included_comment_count: int


def summarize_standard_feedback(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> tuple[StandardFeedbackSummary, ...]:
    """Summarize feedback composition status by Focus Standard."""
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    review = _load_existing_review(context)
    ratings = {item["standard_id"] for item in review["overall_standard_ratings"]}
    feedback_by_standard = {
        item["standard_id"]: item for item in review["feedback"]["standard_feedback"]
    }
    summaries: list[StandardFeedbackSummary] = []
    for standard_id in context["assignment"]["focus_standard_ids"]:
        feedback = feedback_by_standard.get(standard_id)
        comments = feedback["comments"] if feedback is not None else []
        summaries.append(
            StandardFeedbackSummary(
                standard_id=standard_id,
                has_overall_rating=standard_id in ratings,
                has_feedback_record=feedback is not None,
                comment_count=len(comments),
                included_comment_count=sum(
                    1 for comment in comments if comment["include_in_feedback"]
                ),
            )
        )
    return tuple(summaries)


def set_standard_feedback_options(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    standard_id: str,
    include_overall_rating: bool,
    include_overall_rationale: bool,
    included_observation_ids: list[str],
    updated_at: datetime | str | None = None,
) -> UpdatedStandardFeedbackOptions:
    """Create or update feedback options for one Focus Standard."""
    normalized_standard_id = _normalize_required_string(standard_id, "standard_id")
    if not isinstance(include_overall_rating, bool):
        raise ReviewFeedbackError("include_overall_rating must be a boolean.")
    if not isinstance(include_overall_rationale, bool):
        raise ReviewFeedbackError("include_overall_rationale must be a boolean.")
    normalized_updated_at = _normalize_timestamp(updated_at)
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    _validate_focus_standard(context["assignment"], normalized_standard_id)
    review = _load_existing_review(context)
    _guard_returned_without_full_review(review)
    _validate_observation_ids_for_standard(
        review, normalized_standard_id, included_observation_ids
    )

    feedback = _standard_feedback_record(review, normalized_standard_id)
    was_created = feedback is None
    if feedback is None:
        feedback = _empty_standard_feedback(normalized_standard_id)
        review["feedback"]["standard_feedback"].append(feedback)
    feedback["include_overall_rating"] = include_overall_rating
    feedback["include_overall_rationale"] = include_overall_rationale
    feedback["included_observation_ids"] = list(included_observation_ids)
    review["feedback"]["include_review_unit_observations"] = any(
        item["included_observation_ids"] for item in review["feedback"]["standard_feedback"]
    )
    review["review_state"] = _feedback_edit_state(review["review_state"])
    review["updated_at"] = normalized_updated_at
    _write_review(context, review)
    return UpdatedStandardFeedbackOptions(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        review_state=review["review_state"],
        standard_id=normalized_standard_id,
        include_overall_rating=include_overall_rating,
        include_overall_rationale=include_overall_rationale,
        included_observation_count=len(included_observation_ids),
        was_created=was_created,
        updated_at=normalized_updated_at,
    )


def add_custom_feedback_comment(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    standard_id: str,
    text: str,
    include_in_feedback: bool,
    save_for_reuse: bool,
    created_at: datetime | str | None = None,
    comment_id: str | None = None,
    comment_set_id: str | None = None,
    reusable_label: str | None = None,
    reusable_text: str | None = None,
    purpose: str = "general",
    rating_values: list[int | float] | None = None,
) -> AddedFeedbackComment:
    """Add one teacher-authored feedback comment under a Focus Standard."""
    normalized_standard_id = _normalize_required_string(standard_id, "standard_id")
    normalized_text = _normalize_required_string(text, "text")
    if not isinstance(include_in_feedback, bool):
        raise ReviewFeedbackError("include_in_feedback must be a boolean.")
    if not isinstance(save_for_reuse, bool):
        raise ReviewFeedbackError("save_for_reuse must be a boolean.")
    normalized_created_at = _normalize_timestamp(created_at)
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    assignment = context["assignment"]
    _validate_focus_standard(assignment, normalized_standard_id)
    review = _load_existing_review(context)
    _guard_returned_without_full_review(review)
    feedback = _ensure_standard_feedback(review, normalized_standard_id)
    feedback_comment_id = (
        _normalize_required_string(comment_id, "comment_id")
        if comment_id is not None
        else _next_feedback_comment_id(review)
    )
    if _feedback_comment_id_exists(review, feedback_comment_id):
        raise ReviewFeedbackError(
            f"feedback_comment_id {feedback_comment_id!r} already exists."
        )

    saved_reusable: SavedReusableFocusStandardComment | None = None
    if save_for_reuse:
        reusable_label_text = _normalize_required_string(
            reusable_label, "reusable_label"
        )
        reusable_comment_text = _normalize_required_string(
            reusable_text if reusable_text is not None else normalized_text,
            "reusable_text",
        )
        rating_values_to_save = rating_values
        if rating_values_to_save is None:
            current_rating = _current_rating_value(review, normalized_standard_id)
            rating_values_to_save = [] if current_rating is None else [current_rating]
        saved_reusable = append_saved_comment(
            context["workspace_root"],
            standards_profile_id=assignment["standards_profile_id"],
            writing_type=assignment["writing_type"],
            standard_id=normalized_standard_id,
            label=reusable_label_text,
            text=reusable_comment_text,
            purpose=purpose,
            rating_values=rating_values_to_save,
            source=_saved_comment_source(
                context,
                feedback_comment_id=feedback_comment_id,
                saved_at=normalized_created_at,
            ),
            created_at=normalized_created_at,
            comment_set_id=comment_set_id,
        )

    feedback["comments"].append(
        {
            "feedback_comment_id": feedback_comment_id,
            "source": "custom",
            "text": normalized_text,
            "reusable_comment_id": None,
            "save_for_reuse": save_for_reuse,
            "include_in_feedback": include_in_feedback,
            "created_at": normalized_created_at,
            "module_details": {},
        }
    )
    review["review_state"] = _feedback_edit_state(review["review_state"])
    review["updated_at"] = normalized_created_at
    _write_review(context, review)
    return AddedFeedbackComment(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        review_state=review["review_state"],
        standard_id=normalized_standard_id,
        feedback_comment_id=feedback_comment_id,
        include_in_feedback=include_in_feedback,
        save_for_reuse=save_for_reuse,
        saved_reusable_comment=saved_reusable,
        created_at=normalized_created_at,
    )


def select_reusable_feedback_comment(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    standard_id: str,
    comment_set_id: str,
    comment_id: str,
    include_in_feedback: bool,
    created_at: datetime | str | None = None,
) -> SelectedReusableFeedbackComment:
    """Copy a reusable Focus Standard comment into the student review record."""
    normalized_standard_id = _normalize_required_string(standard_id, "standard_id")
    normalized_comment_set_id = _normalize_required_string(
        comment_set_id, "comment_set_id"
    )
    normalized_comment_id = _normalize_required_string(comment_id, "comment_id")
    if not isinstance(include_in_feedback, bool):
        raise ReviewFeedbackError("include_in_feedback must be a boolean.")
    normalized_created_at = _normalize_timestamp(created_at)
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    assignment = context["assignment"]
    _validate_focus_standard(assignment, normalized_standard_id)
    review = _load_existing_review(context)
    _guard_returned_without_full_review(review)
    rating_value = _current_rating_value(review, normalized_standard_id)
    try:
        comment_set = load_comment_set(
            focus_standard_comment_set_path(
                context["workspace_root"], normalized_comment_set_id
            )
        )
    except (OSError, FocusStandardCommentError) as error:
        raise ReviewFeedbackError(str(error)) from error
    matches = lookup_comments(
        context["workspace_root"],
        standards_profile_id=assignment["standards_profile_id"],
        writing_type=assignment["writing_type"],
        standard_id=normalized_standard_id,
        rating_value=rating_value,
        comment_set_id=normalized_comment_set_id,
    )
    match = next(
        (
            item
            for item in matches
            if item.comment_id == normalized_comment_id
            and item.comment_set_id == comment_set["comment_set_id"]
        ),
        None,
    )
    if match is None:
        raise ReviewFeedbackError(
            "Reusable Focus Standard comment is not compatible with this "
            "assignment, standard, and rating."
        )
    feedback = _ensure_standard_feedback(review, normalized_standard_id)
    feedback_comment_id = _next_feedback_comment_id(review)
    feedback["comments"].append(
        {
            "feedback_comment_id": feedback_comment_id,
            "source": "reusable_focus_standard_comment",
            "text": match.text,
            "reusable_comment_id": normalized_comment_id,
            "save_for_reuse": False,
            "include_in_feedback": include_in_feedback,
            "created_at": normalized_created_at,
            "module_details": {"comment_set_id": normalized_comment_set_id},
        }
    )
    review["review_state"] = _feedback_edit_state(review["review_state"])
    review["updated_at"] = normalized_created_at
    _write_review(context, review)
    try:
        increment_usage(
            context["workspace_root"],
            comment_set_id=normalized_comment_set_id,
            comment_id=normalized_comment_id,
            used_at=normalized_created_at,
        )
    except FocusStandardCommentError as error:
        raise ReviewFeedbackError(str(error)) from error
    return SelectedReusableFeedbackComment(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        review_state=review["review_state"],
        standard_id=normalized_standard_id,
        feedback_comment_id=feedback_comment_id,
        comment_set_id=normalized_comment_set_id,
        reusable_comment_id=normalized_comment_id,
        include_in_feedback=include_in_feedback,
        created_at=normalized_created_at,
    )


def mark_feedback_composed(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    updated_at: datetime | str | None = None,
) -> CompletedFeedbackComposition:
    """Explicitly mark Focus Standard feedback composition complete."""
    normalized_updated_at = _normalize_timestamp(updated_at)
    context = _load_context(workspace_root, class_id, assignment_id, student_id)
    review = _load_existing_review(context)
    _guard_returned_without_full_review(review)
    focus_standard_ids = set(context["assignment"]["focus_standard_ids"])
    standards_with_feedback = {
        item["standard_id"]
        for item in review["feedback"]["standard_feedback"]
        if item["standard_id"] in focus_standard_ids
    }
    included_comment_count = sum(
        1
        for item in review["feedback"]["standard_feedback"]
        for comment in item["comments"]
        if comment["include_in_feedback"]
    )
    review["review_state"] = "feedback_composed"
    review["updated_at"] = normalized_updated_at
    _write_review(context, review)
    return CompletedFeedbackComposition(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        review_state=review["review_state"],
        focus_standard_count=len(focus_standard_ids),
        standard_feedback_count=len(standards_with_feedback),
        missing_standard_feedback_count=max(
            len(focus_standard_ids) - len(standards_with_feedback), 0
        ),
        included_comment_count=included_comment_count,
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
        raise ReviewFeedbackError(str(error)) from error
    if not manifest_path.exists():
        raise ReviewFeedbackError(missing_submission_guidance())
    if not record_path.exists():
        raise ReviewFeedbackError(
            "A review record must exist before composing feedback."
        )
    try:
        manifest = load_submission_manifest(manifest_path)
        assignment = load_assignment_config(assignment_path)
    except (OSError, SubmissionManifestError, AssignmentConfigError) as error:
        raise ReviewFeedbackError(str(error)) from error
    _validate_identity(
        manifest,
        record_name="Submission manifest",
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )
    if class_id not in assignment["class_ids"]:
        raise ReviewFeedbackError(
            f"Assignment config class_ids does not include {class_id!r}."
        )
    if assignment["assignment_id"] != assignment_id:
        raise ReviewFeedbackError(
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
        raise ReviewFeedbackError(f"Could not load review record: {error}") from error
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
        raise ReviewFeedbackError(f"Could not write review record: {error}") from error


def _guard_returned_without_full_review(review: dict[str, Any]) -> None:
    if review["review_state"] == "returned_without_full_review":
        raise ReviewFeedbackError(
            "This submission was returned without full standards review. "
            "Change the minimum-requirements outcome before continuing with "
            "Focus Standard feedback."
        )


def _validate_focus_standard(assignment: dict[str, Any], standard_id: str) -> None:
    if standard_id not in assignment["focus_standard_ids"]:
        raise ReviewFeedbackError(
            f"standard_id {standard_id!r} is not a Focus Standard for this assignment."
        )


def _validate_observation_ids_for_standard(
    review: dict[str, Any], standard_id: str, observation_ids: list[str]
) -> None:
    if not isinstance(observation_ids, list):
        raise ReviewFeedbackError("included_observation_ids must be a list.")
    observations_by_id = {
        observation["observation_id"]: observation
        for unit in review["review_units"]
        for observation in unit["standard_observations"]
    }
    seen: set[str] = set()
    for observation_id in observation_ids:
        normalized_id = _normalize_required_string(observation_id, "observation_id")
        if normalized_id in seen:
            raise ReviewFeedbackError(
                f"included_observation_ids contains duplicate {normalized_id!r}."
            )
        seen.add(normalized_id)
        observation = observations_by_id.get(normalized_id)
        if observation is None:
            raise ReviewFeedbackError(
                f"included_observation_ids references unknown observation_id {normalized_id!r}."
            )
        if observation["standard_id"] != standard_id:
            raise ReviewFeedbackError(
                f"observation_id {normalized_id!r} does not belong to standard_id {standard_id!r}."
            )


def _ensure_standard_feedback(
    review: dict[str, Any], standard_id: str
) -> dict[str, Any]:
    feedback = _standard_feedback_record(review, standard_id)
    if feedback is None:
        feedback = _empty_standard_feedback(standard_id)
        review["feedback"]["standard_feedback"].append(feedback)
    return feedback


def _standard_feedback_record(
    review: dict[str, Any], standard_id: str
) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in review["feedback"]["standard_feedback"]
            if item["standard_id"] == standard_id
        ),
        None,
    )


def _empty_standard_feedback(standard_id: str) -> dict[str, Any]:
    return {
        "standard_id": standard_id,
        "include_overall_rating": True,
        "include_overall_rationale": True,
        "included_observation_ids": [],
        "comments": [],
        "module_details": {},
    }


def _next_feedback_comment_id(review: dict[str, Any]) -> str:
    existing_ids = {
        comment["feedback_comment_id"]
        for item in review["feedback"]["standard_feedback"]
        for comment in item["comments"]
    }
    highest = max(
        (
            int(match.group(1))
            for comment_id in existing_ids
            if (match := _SEQUENTIAL_FEEDBACK_COMMENT_ID.fullmatch(comment_id))
        ),
        default=0,
    )
    candidate_number = highest + 1
    while True:
        candidate = f"feedback_comment_{candidate_number:04d}"
        if candidate not in existing_ids:
            return candidate
        candidate_number += 1


def _feedback_comment_id_exists(review: dict[str, Any], comment_id: str) -> bool:
    return any(
        comment["feedback_comment_id"] == comment_id
        for item in review["feedback"]["standard_feedback"]
        for comment in item["comments"]
    )


def _current_rating_value(review: dict[str, Any], standard_id: str) -> int | None:
    rating = next(
        (
            item
            for item in review["overall_standard_ratings"]
            if item["standard_id"] == standard_id
        ),
        None,
    )
    return rating["rating"] if rating is not None else None


def _saved_comment_source(
    context: dict[str, Any], *, feedback_comment_id: str, saved_at: str
) -> dict[str, Any]:
    return {
        "type": "teacher_saved_from_feedback",
        "class_id": context["class_id"],
        "assignment_id": context["assignment_id"],
        "student_id": context["student_id"],
        "review_path": _workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        "feedback_comment_id": feedback_comment_id,
        "saved_at": saved_at,
    }


def _feedback_edit_state(current_state: str) -> str:
    if current_state in {"feedback_composed", "ready_for_export", "exported"}:
        return "ratings_complete"
    return current_state


def _normalize_required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewFeedbackError(f"{field} must be a non-empty string.")
    return value.strip()


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewFeedbackError("timestamp datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise ReviewFeedbackError(
            "timestamp must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewFeedbackError(
            "timestamp must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewFeedbackError(
            "timestamp must be a timezone-aware ISO 8601 string."
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
            raise ReviewFeedbackError(
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
        raise ReviewFeedbackError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error

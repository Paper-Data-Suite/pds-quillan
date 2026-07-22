"""Teacher-controlled review workflow state updates."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.minimum_requirement_review import (
    allows_return_without_full_review,
    configured_requirements,
)
from quillan.review_record import (
    ALLOWED_REVIEW_STATES,
    ReviewRecordError,
    build_empty_review_record,
    validate_review_record,
)
from quillan.review_record_paths import (
    ReviewRecordPathError,
    persist_quillan_review_record,
)
from quillan.review_unit_management import (
    ReviewUnitManagementError,
    load_review_unit_context,
)
REVIEW_WORKFLOW_STATES = (
    "not_started",
    "requirements_checked",
    "returned_without_full_review",
    "observations_in_progress",
    "observations_complete",
    "ratings_complete",
    "feedback_composed",
    "ready_for_export",
    "exported",
)

if frozenset(REVIEW_WORKFLOW_STATES) != ALLOWED_REVIEW_STATES:
    raise RuntimeError("Ordered review workflow states do not match the review schema.")


class ReviewWorkflowStateError(ValueError):
    """Raised when a review workflow state cannot be updated safely."""


@dataclass(frozen=True, slots=True)
class UpdatedReviewWorkflowState:
    """Immutable result of one canonical review workflow state update."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    previous_state: str | None
    new_state: str
    review_was_created: bool
    updated_at: str


def set_review_workflow_state(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    state: str,
    *,
    updated_at: datetime | str | None = None,
) -> UpdatedReviewWorkflowState:
    """Set only ``review_state`` and ``updated_at`` in one canonical review."""
    if state not in REVIEW_WORKFLOW_STATES:
        allowed = ", ".join(REVIEW_WORKFLOW_STATES)
        raise ReviewWorkflowStateError(
            f"Invalid review workflow state {state!r}. Allowed states: {allowed}."
        )

    try:
        context = load_review_unit_context(
            workspace_root, class_id, assignment_id, student_id
        )
    except ReviewUnitManagementError as error:
        raise ReviewWorkflowStateError(str(error)) from error

    normalized_updated_at = _normalize_timestamp(updated_at)
    review = context.review
    if state == "returned_without_full_review":
        if review is None or not _has_coherent_returned_outcome(
            review, context.assignment
        ):
            raise ReviewWorkflowStateError(
                "Returned-without-full-review status must be set through "
                "'requirements set-outcome --outcome returned_without_full_review' first."
            )
    elif review is not None and bool(
        review["minimum_requirement_outcome"]["returned_without_full_review"]
    ):
        raise ReviewWorkflowStateError(
            "Change the minimum-requirement outcome through 'requirements set-outcome' "
            "before leaving returned-without-full-review status."
        )

    if review is None:
        updated_review = build_empty_review_record(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            submission_manifest_path=context.submission_manifest_relative_path,
            assignment_path=_relative(context.assignment_path, context.workspace_root),
            created_at=normalized_updated_at,
        )
        previous_state = None
        review_was_created = True
    else:
        _ensure_not_before_created_at(normalized_updated_at, review["created_at"])
        updated_review = copy.deepcopy(review)
        previous_state = str(review["review_state"])
        review_was_created = False

    updated_review["review_state"] = state
    updated_review["updated_at"] = normalized_updated_at
    try:
        validate_review_record(updated_review)
        persist_quillan_review_record(context.record_context, updated_review)
    except (ReviewRecordError, ReviewRecordPathError, OSError, ValueError) as error:
        raise ReviewWorkflowStateError(f"Could not write review record: {error}") from error

    return UpdatedReviewWorkflowState(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context.review_record_path,
        review_record_relative_path=context.review_record_relative_path,
        previous_state=previous_state,
        new_state=state,
        review_was_created=review_was_created,
        updated_at=normalized_updated_at,
    )


def _has_coherent_returned_outcome(
    review: dict[str, Any], assignment: dict[str, Any]
) -> bool:
    outcome = review["minimum_requirement_outcome"]
    assert isinstance(outcome, dict)
    note = outcome["teacher_note"]
    configured_keys = {item.key for item in configured_requirements(assignment)}
    checks = review["minimum_requirement_checks"]
    assert isinstance(checks, list)
    has_configured_unmet_check = any(
        isinstance(check, dict)
        and check.get("requirement_key") in configured_keys
        and check.get("met") is False
        for check in checks
    )
    return (
        review["review_state"] == "returned_without_full_review"
        and outcome["status"] == "returned_without_full_review"
        and outcome["returned_without_full_review"] is True
        and isinstance(note, str)
        and bool(note.strip())
        and allows_return_without_full_review(assignment)
        and has_configured_unmet_check
    )


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
        normalized = value.isoformat()
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ReviewWorkflowStateError(
                "updated_at must be a timezone-aware ISO 8601 timestamp."
            ) from error
        normalized = value
    else:
        raise ReviewWorkflowStateError(
            "updated_at must be a timezone-aware datetime or ISO 8601 string."
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewWorkflowStateError("updated_at must be timezone-aware.")
    return normalized


def _ensure_not_before_created_at(updated_at: str, created_at: object) -> None:
    assert isinstance(created_at, str)
    if datetime.fromisoformat(updated_at) < datetime.fromisoformat(created_at):
        raise ReviewWorkflowStateError("updated_at must not precede created_at.")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise ReviewWorkflowStateError(
            f"Canonical path is outside the workspace: {path}"
        ) from error

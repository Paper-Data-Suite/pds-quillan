"""Teacher-facing display helpers for submission, review, and export status."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

OBSERVATIONS_COMPLETE_STATES = {
    "observations_complete",
    "ratings_complete",
    "feedback_composed",
    "ready_for_export",
    "exported",
}

RATINGS_COMPLETE_STATES = {
    "ratings_complete",
    "feedback_composed",
    "ready_for_export",
    "exported",
}

FEEDBACK_COMPOSED_STATES = {
    "feedback_composed",
    "ready_for_export",
    "exported",
}

REVIEW_STATE_LABELS = {
    "not_started": "not started",
    "requirements_checked": "requirements checked",
    "returned_without_full_review": "returned without full standards review",
    "observations_in_progress": "observations in progress",
    "observations_complete": "observations complete",
    "ratings_complete": "ratings complete",
    "feedback_composed": "feedback composed",
    "ready_for_export": "ready for export",
    "exported": "exported",
}


@dataclass(frozen=True, slots=True)
class ReviewProgressStatus:
    """Authoritative teacher-review progress derived from review_state."""

    review_state: str
    review_state_label: str
    is_returned_without_full_review: bool
    observations_complete: bool
    ratings_complete: bool
    feedback_composed: bool
    ready_for_export: bool
    exported: bool
    observations_status_label: str
    ratings_status_label: str
    feedback_status_label: str


def review_status_label(record: dict[str, Any] | None) -> str:
    """Return the teacher-facing review workflow label."""
    if record is None:
        return REVIEW_STATE_LABELS["not_started"]
    state = str(record.get("review_state", "not_started"))
    return REVIEW_STATE_LABELS.get(state, state.replace("_", " "))


def review_progress_status(record: dict[str, Any] | None) -> ReviewProgressStatus:
    """Return centralized review-phase completion status for menus and gates."""
    state = (
        "not_started"
        if record is None
        else str(record.get("review_state", "not_started"))
    )
    returned = state == "returned_without_full_review"
    observations_complete = state in OBSERVATIONS_COMPLETE_STATES
    ratings_complete = state in RATINGS_COMPLETE_STATES
    feedback_composed = state in FEEDBACK_COMPOSED_STATES
    exported = state == "exported" or _export_metadata_exists(record)

    if returned:
        observations_label = "not applicable - returned without full standards review"
        ratings_label = "not applicable - returned without full standards review"
        feedback_label = "not applicable - returned without full standards review"
    else:
        observations_label = "complete" if observations_complete else "incomplete"
        ratings_label = "complete" if ratings_complete else "incomplete"
        feedback_label = "composed" if feedback_composed else "not composed"

    return ReviewProgressStatus(
        review_state=state,
        review_state_label=review_status_label(record),
        is_returned_without_full_review=returned,
        observations_complete=observations_complete,
        ratings_complete=ratings_complete,
        feedback_composed=feedback_composed,
        ready_for_export=state in {"ready_for_export", "exported"} or exported,
        exported=exported,
        observations_status_label=observations_label,
        ratings_status_label=ratings_label,
        feedback_status_label=feedback_label,
    )


def _export_metadata_exists(record: dict[str, Any] | None) -> bool:
    if record is None:
        return False
    exports = record.get("exports")
    if not isinstance(exports, dict):
        return False
    return any(
        isinstance(exports.get(key), dict)
        for key in ("feedback_pdf", "feedback_markdown")
    )


def feedback_export_status(
    workspace_root: str | Path,
    record: dict[str, Any] | None,
) -> str:
    """Derive a teacher-facing export status from review export metadata."""
    if record is None:
        return "not exported"
    exports = record.get("exports")
    if not isinstance(exports, dict):
        return "not exported"

    present: list[tuple[str, str]] = []
    for key, label in (
        ("feedback_pdf", "PDF"),
        ("feedback_markdown", "Markdown"),
    ):
        metadata = exports.get(key)
        if not isinstance(metadata, dict):
            continue
        relative_path = metadata.get("path")
        if not isinstance(relative_path, str) or not (
            Path(workspace_root) / Path(relative_path)
        ).is_file():
            return "metadata exists, but export file is missing"
        present.append((label, str(metadata.get("generated_at", ""))))

    if not present:
        return "not exported"
    latest = max(timestamp for _, timestamp in present)
    labels = " + ".join(label for label, _ in present)
    return f"{labels} exported {latest}".rstrip()

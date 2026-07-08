"""Teacher-facing display helpers for submission, review, and export status."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


def review_status_label(record: dict[str, Any] | None) -> str:
    """Return the teacher-facing review workflow label."""
    if record is None:
        return REVIEW_STATE_LABELS["not_started"]
    state = str(record.get("review_state", "not_started"))
    return REVIEW_STATE_LABELS.get(state, state.replace("_", " "))


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

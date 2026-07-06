"""Student-facing Markdown export from canonical Quillan review records."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.review_record import ReviewRecordError, load_review_record
from quillan.review_record_paths import ReviewRecordPathError, review_record_path
from quillan.storage import assignment_config_path
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_dir,
    submission_manifest_path,
)
from quillan.submission_guidance import missing_submission_guidance


class FeedbackExportError(Exception):
    """Raised when student-facing feedback cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class ExportedFeedback:
    """Information about one generated student-facing feedback artifact."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    feedback_path: Path
    feedback_relative_path: str
    included_comment_count: int
    score_count: int
    created_at: str
    overwrote_existing: bool


def feedback_export_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical student-facing Markdown feedback export path."""
    return (
        submission_dir(workspace_root, class_id, assignment_id, student_id)
        / "exports"
        / "feedback.md"
    )


def export_student_feedback(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedFeedback:
    """Generate student-facing Markdown from one canonical review record."""
    normalized_created_at = _normalize_timestamp(created_at)
    try:
        resolved_workspace_root = Path(workspace_root).resolve(strict=False)
        manifest_path = submission_manifest_path(
            resolved_workspace_root, class_id, assignment_id, student_id
        )
        record_path = review_record_path(
            resolved_workspace_root, class_id, assignment_id, student_id
        )
        output_path = feedback_export_path(
            resolved_workspace_root, class_id, assignment_id, student_id
        )
    except (
        OSError,
        RuntimeError,
        SubmissionManifestPathError,
        ReviewRecordPathError,
    ) as error:
        raise FeedbackExportError(str(error)) from error

    if not manifest_path.exists():
        raise FeedbackExportError(missing_submission_guidance())
    try:
        manifest = load_submission_manifest(manifest_path)
    except (OSError, SubmissionManifestError) as error:
        raise FeedbackExportError(
            f"Could not load submission manifest: {error}"
        ) from error
    _validate_identity(
        manifest,
        record_name="Submission manifest",
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )

    if not record_path.exists():
        raise FeedbackExportError(
            "Review record does not exist for "
            f"class={class_id}, assignment={assignment_id}, student={student_id}."
        )
    try:
        review = load_review_record(record_path)
    except (OSError, ReviewRecordError) as error:
        raise FeedbackExportError(f"Could not load review record: {error}") from error
    _validate_identity(
        review,
        record_name="Review record",
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )

    if review["review_state"] == "returned_without_full_review":
        unmet_requirements = _validated_returned_work_requirements(
            resolved_workspace_root,
            class_id,
            assignment_id,
            review,
        )
        included_comments: list[dict[str, Any]] = []
        ratings: list[dict[str, Any]] = []
        markdown = _render_returned_work_markdown(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            created_at=normalized_created_at,
            outcome=review["minimum_requirement_outcome"],
            unmet_requirements=unmet_requirements,
        )
    else:
        included_comments = _included_feedback_comments(review)
        ratings = review["overall_standard_ratings"]
        markdown = _render_markdown(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            created_at=normalized_created_at,
            ratings=ratings,
            comments=included_comments,
        )
    overwrote_existing = output_path.exists()
    if overwrote_existing and not overwrite:
        raise FeedbackExportError(
            f"Feedback export already exists: {output_path}. "
            "Use --overwrite to replace it."
        )

    _write_feedback(output_path, markdown, overwrite=overwrite)
    return ExportedFeedback(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=record_path,
        review_record_relative_path=_workspace_relative_path(
            record_path, resolved_workspace_root, "review record"
        ),
        feedback_path=output_path,
        feedback_relative_path=_workspace_relative_path(
            output_path, resolved_workspace_root, "feedback"
        ),
        included_comment_count=len(included_comments),
        score_count=len(ratings),
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def _render_markdown(
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    created_at: str,
    ratings: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> str:
    lines = [
        "# Feedback",
        "",
        f"Class: {_plain_text(class_id)}",
        f"Assignment: {_plain_text(assignment_id)}",
        f"Student: {_plain_text(student_id)}",
        f"Generated: {_plain_text(created_at)}",
        "",
        "## Standards Ratings",
        "",
    ]
    if ratings:
        for rating in ratings:
            rendered = (
                f"- {_plain_text(rating['standard_id'])}: "
                f"{_format_number(rating['rating'])}"
            )
            if rating.get("rationale"):
                rendered += f" - {_plain_text(rating['rationale'])}"
            lines.append(rendered)
    else:
        lines.append("No standards ratings recorded.")

    lines.extend(["", "## Feedback Comments", ""])
    if comments:
        lines.extend(f"- {_plain_text(comment['text'])}" for comment in comments)
    else:
        lines.append("No feedback comments selected.")
    lines.append("")
    return "\n".join(lines)


def _render_returned_work_markdown(
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    created_at: str,
    outcome: dict[str, Any],
    unmet_requirements: list[dict[str, Any]],
) -> str:
    lines = [
        "# Returned for Revision",
        "",
        f"Class: {_plain_text(class_id)}",
        f"Assignment: {_plain_text(assignment_id)}",
        f"Student: {_plain_text(student_id)}",
        f"Generated: {_plain_text(created_at)}",
        "",
        (
            "This submission was returned without full standards review because "
            "minimum requirements were not met."
        ),
        "",
        "## Minimum Requirements Not Met",
        "",
    ]
    for requirement in unmet_requirements:
        lines.append(f"- {_plain_text(requirement['label'])}")
        lines.append(f"  Expected: {_plain_text(requirement['expected'])}")
        if note := _non_empty(requirement.get("teacher_note")):
            lines.append(f"  Teacher note: {_plain_text(note)}")
    lines.extend(
        [
            "",
            "## Return Note",
            "",
            _plain_text(outcome["teacher_note"]),
            "",
            "No full standards ratings were completed for this submission.",
            "",
        ]
    )
    return "\n".join(lines)


def _included_feedback_comments(review: dict[str, Any]) -> list[dict[str, Any]]:
    included: list[dict[str, Any]] = []
    for standard_feedback in review["feedback"]["standard_feedback"]:
        included.extend(
            comment
            for comment in standard_feedback["comments"]
            if comment["include_in_feedback"]
        )
    return included


def _validated_returned_work_requirements(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    review: dict[str, Any],
) -> list[dict[str, Any]]:
    outcome = review["minimum_requirement_outcome"]
    if outcome["returned_without_full_review"] is not True:
        raise FeedbackExportError(
            "Returned-work export requires "
            "minimum_requirement_outcome.returned_without_full_review to be true."
        )
    if not _non_empty(outcome.get("teacher_note")):
        raise FeedbackExportError(
            "Returned-work export requires a non-empty outcome teacher note."
        )

    try:
        assignment = load_assignment_config(
            assignment_config_path(workspace_root, class_id, assignment_id)
        )
    except (AssignmentConfigError, OSError) as error:
        raise FeedbackExportError(
            f"Could not load assignment config: {error}"
        ) from error
    configured_keys = _configured_requirement_keys(assignment)
    unmet_requirements = [
        check
        for check in review["minimum_requirement_checks"]
        if check["requirement_key"] in configured_keys and check["met"] is False
    ]
    if not unmet_requirements:
        raise FeedbackExportError(
            "Returned-work export requires at least one checked configured "
            "minimum requirement marked not met."
        )
    return unmet_requirements


def _configured_requirement_keys(assignment: dict[str, Any]) -> set[str]:
    basic_requirements = assignment.get("basic_requirements")
    if not isinstance(basic_requirements, dict):
        return set()
    keys: set[str] = set()
    for key in (
        "paragraphs_min",
        "paragraphs_max",
        "word_count_min",
        "word_count_max",
    ):
        if key in basic_requirements:
            keys.add(key)
    required_elements = basic_requirements.get("required_elements")
    if isinstance(required_elements, list):
        for element in required_elements:
            if isinstance(element, str) and element.strip():
                keys.add(f"required_elements:{element.strip()}")
    return keys


def _write_feedback(path: Path, content: str, *, overwrite: bool) -> None:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise FeedbackExportError(
            f"Could not create feedback export directory {parent}: {error}"
        ) from error
    if not parent.is_dir():
        raise FeedbackExportError(
            f"Feedback export parent is not a directory: {parent}"
        )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        if overwrite:
            os.replace(temporary_path, path)
        else:
            os.link(temporary_path, path)
            temporary_path.unlink()
        temporary_path = None
    except FileExistsError as error:
        raise FeedbackExportError(
            f"Feedback export already exists: {path}. "
            "Use --overwrite to replace it."
        ) from error
    except OSError as error:
        raise FeedbackExportError(
            f"Could not write feedback export {path}: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise FeedbackExportError("created_at datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise FeedbackExportError(
            "created_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise FeedbackExportError(
            "created_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FeedbackExportError(
            "created_at must be a timezone-aware ISO 8601 string."
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
    requested = {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }
    for field, expected in requested.items():
        actual = record[field]
        if actual != expected:
            raise FeedbackExportError(
                f"{record_name} {field} is {actual!r}, expected {expected!r}."
            )


def _plain_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _non_empty(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _format_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    return format(value, "g")


def _workspace_relative_path(
    path: Path, workspace_root: Path, description: str
) -> str:
    try:
        return path.resolve(strict=False).relative_to(workspace_root).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise FeedbackExportError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error

"""Student-facing Markdown export from canonical Quillan review records."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.review_record import ReviewRecordError, load_review_record
from quillan.review_record_paths import ReviewRecordPathError, review_record_path
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

    included_comments = [
        comment
        for comment in review["comments"]
        if comment["include_in_feedback"]
    ]
    markdown = _render_markdown(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        created_at=normalized_created_at,
        scores=review["scores"],
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
        score_count=len(review["scores"]),
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def _render_markdown(
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    created_at: str,
    scores: list[dict[str, Any]],
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
        "## Scores",
        "",
    ]
    if scores:
        for score in scores:
            rendered = (
                f"- {_plain_text(score['label'])}: "
                f"{_format_number(score['score'])} / "
                f"{_format_number(score['max_score'])}"
            )
            if "scale" in score:
                rendered += f" ({_plain_text(score['scale'])})"
            lines.append(rendered)
    else:
        lines.append("No scores recorded.")

    lines.extend(["", "## Feedback Comments", ""])
    if comments:
        lines.extend(f"- {_plain_text(comment['text'])}" for comment in comments)
    else:
        lines.append("No feedback comments selected.")
    lines.append("")
    return "\n".join(lines)


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

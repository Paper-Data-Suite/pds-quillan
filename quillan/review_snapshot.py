"""Read-only terminal snapshot of a student's current review record."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quillan.review_record import ReviewRecordError, load_review_record
from quillan.review_record_paths import review_record_path
from quillan.review_targets import format_review_target


def current_review_details_text(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> str:
    """Return a compact, read-only terminal view of recorded review artifacts."""
    path = review_record_path(Path(workspace_root), class_id, assignment_id, student_id)
    lines: list[str] = []
    if not path.exists():
        lines.append("No review record exists yet for this student.")
        return "\n".join(lines)

    try:
        record = load_review_record(path)
    except (OSError, ReviewRecordError) as error:
        lines.append("Review record: invalid")
        lines.append(f"Review record error: {error}")
        return "\n".join(lines)

    identity_error = _identity_error(record, class_id, assignment_id, student_id)
    if identity_error is not None:
        lines.append("Review record: invalid")
        lines.append(identity_error)
        return "\n".join(lines)

    lines.append("Review record: exists")
    lines.append(f"Review state: {record['review_state']}")
    lines.append("")
    _append_requirement_checks(lines, record)
    _append_tags(lines, record)
    _append_comments(lines, record)
    _append_scores(lines, record)
    _append_notes(lines, record)
    return "\n".join(lines).rstrip()


def _identity_error(
    record: dict[str, Any],
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> str | None:
    for field, expected in {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }.items():
        if record[field] != expected:
            return f"Review record {field} is {record[field]!r}, expected {expected!r}."
    return None


def _append_requirement_checks(lines: list[str], record: dict[str, Any]) -> None:
    lines.append("Requirement Checks")
    checks = _record_list(record, "requirement_checks")
    if not checks:
        lines.append("No requirement checks recorded.")
        lines.append("")
        return
    for check in checks:
        status = "met" if check.get("met") is True else "not met"
        lines.append(f"- {check['label']}: {status}")
        if note := _non_empty(check.get("teacher_note")):
            lines.append(f"  Note: {note}")
    lines.append("")


def _append_tags(lines: list[str], record: dict[str, Any]) -> None:
    lines.append("Tags")
    tags = _record_list(record, "tags")
    if not tags:
        lines.append("No tags recorded.")
        lines.append("")
        return
    for index, tag in enumerate(tags, start=1):
        lines.append(f"{index}. [{tag['polarity']}] {tag['label']}")
        lines.append(f"   Target: {format_review_target(tag)}")
        lines.append(f"   Source: {_format_tag_source(tag)}")
        if note := _non_empty(tag.get("teacher_note")):
            lines.append(f"   Note: {note}")
        lines.append("")


def _append_comments(lines: list[str], record: dict[str, Any]) -> None:
    lines.append("Comments")
    comments = _record_list(record, "comments")
    if not comments:
        lines.append("No comments recorded.")
        lines.append("")
        return
    for index, comment in enumerate(comments, start=1):
        lines.append(f"{index}. {comment['label']}")
        lines.append(f"   Target: {format_review_target(comment)}")
        include = "yes" if comment["include_in_feedback"] else "no"
        lines.append(f"   Include in feedback: {include}")
        lines.append(f"   Feedback: {comment['text']}")
        if source := _format_comment_source(comment):
            lines.append(f"   Source: {source}")
        lines.append("")


def _append_scores(lines: list[str], record: dict[str, Any]) -> None:
    lines.append("Scores")
    scores = _record_list(record, "scores")
    if not scores:
        lines.append("No scores recorded.")
        lines.append("")
        return
    for index, score in enumerate(scores, start=1):
        lines.append(
            f"{index}. {score['label']}: {score['score']:g} / {score['max_score']:g}"
        )
        if note := _non_empty(score.get("teacher_note")):
            lines.append(f"   Note: {note}")
    lines.append("")


def _append_notes(lines: list[str], record: dict[str, Any]) -> None:
    lines.append("Notes")
    notes = _record_list(record, "notes")
    if not notes:
        lines.append("No notes recorded.")
        return
    for index, note in enumerate(notes, start=1):
        lines.append(f"{index}. {note['text']}")


def _record_list(record: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = record.get(field, [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _format_tag_source(tag: dict[str, Any]) -> str:
    if tag.get("source") == "tag_bank":
        return f"{tag.get('tag_bank_id')} / {tag.get('tag_template_id')}"
    if tag.get("source") == "custom":
        return "custom"
    return "not specified"


def _format_comment_source(comment: dict[str, Any]) -> str:
    if comment.get("source") == "comment_bank":
        return f"{comment.get('bank_id')} / {comment.get('comment_id')}"
    if comment.get("source") == "custom":
        return "custom"
    return ""


def _non_empty(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None

"""Read-only terminal snapshot of a student's current review record."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quillan.review_record import ReviewRecordError, load_review_record
from quillan.review_record_paths import review_record_path

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
    _append_review_units(lines, record)
    _append_overall_ratings(lines, record)
    _append_feedback(lines, record)
    _append_private_notes(lines, record)
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
    lines.append("Minimum Requirement Checks")
    checks = _record_list(record, "minimum_requirement_checks")
    unmet_count = sum(1 for check in checks if check.get("met") is False)
    outcome = record.get("minimum_requirement_outcome")
    outcome_status = "not_checked"
    returned = False
    outcome_note = None
    if isinstance(outcome, dict):
        outcome_status = str(outcome.get("status", "not_checked"))
        returned = outcome.get("returned_without_full_review") is True
        outcome_note = _non_empty(outcome.get("teacher_note"))
    lines.append(f"Check completion count: {len(checks)}")
    lines.append(f"Unmet count: {unmet_count}")
    lines.append(f"Outcome status: {outcome_status}")
    lines.append(
        "Returned without full standards review: "
        f"{'yes' if returned else 'no'}"
    )
    if returned:
        lines.append(
            "Minimum-requirements outcome: returned without full standards review"
        )
    if outcome_note:
        lines.append(f"Outcome teacher note: {outcome_note}")
    else:
        lines.append("Outcome teacher note: none")
    if not checks:
        lines.append("No minimum requirement checks recorded.")
        lines.append("")
        return
    for check in checks:
        status = "met" if check.get("met") is True else "not met"
        lines.append(f"- {check['label']}: {status}")
        if note := _non_empty(check.get("teacher_note")):
            lines.append(f"  Note: {note}")
    lines.append("")


def _append_review_units(lines: list[str], record: dict[str, Any]) -> None:
    lines.append("Review Units")
    units = _record_list(record, "review_units")
    if not units:
        lines.append("No review units recorded.")
        lines.append("")
        return
    for unit in units:
        lines.append(f"{unit['sequence']}. {unit['label']} ({unit['unit_type']})")
        for observation in _record_list(unit, "standard_observations"):
            status = "applicable" if observation["applicable"] else "not applicable"
            evidence = _format_evidence_present(observation["evidence_present"])
            include = "yes" if observation["include_in_feedback"] else "no"
            lines.append(
                f"   - {observation['standard_id']}: {status}; "
                f"evidence present: {evidence}; include in feedback: {include}"
            )
            if observation["rating"] is not None:
                lines.append(f"     Rating: {observation['rating']}")
            if rationale := _non_empty(observation.get("rationale")):
                lines.append(f"     Rationale: {rationale}")
        lines.append("")


def _append_overall_ratings(lines: list[str], record: dict[str, Any]) -> None:
    lines.append("Overall Standard Ratings")
    ratings = _record_list(record, "overall_standard_ratings")
    if not ratings:
        lines.append("No overall standard ratings recorded.")
        lines.append("")
        return
    for rating in ratings:
        include = "yes" if rating["include_in_feedback"] else "no"
        lines.append(
            f"- {rating['standard_id']}: {rating['rating']} "
            f"(include in feedback: {include})"
        )
        if rationale := _non_empty(rating.get("rationale")):
            lines.append(f"  Rationale: {rationale}")
    lines.append("")


def _append_feedback(lines: list[str], record: dict[str, Any]) -> None:
    lines.append("Feedback")
    standard_feedback = _record_list(record["feedback"], "standard_feedback")
    if not standard_feedback:
        lines.append("No feedback composed.")
        lines.append("")
        return
    for item in standard_feedback:
        lines.append(f"- {item['standard_id']}")
        comments = _record_list(item, "comments")
        if not comments:
            lines.append("  No comments recorded.")
            continue
        for comment in comments:
            include = "yes" if comment["include_in_feedback"] else "no"
            lines.append(f"  - Include in feedback: {include}")
            lines.append(f"    Feedback: {comment['text']}")
    lines.append("")


def _append_private_notes(lines: list[str], record: dict[str, Any]) -> None:
    lines.append("Private Notes")
    notes = _record_list(record, "private_notes")
    if not notes:
        lines.append("No private notes recorded.")
        return
    for index, note in enumerate(notes, start=1):
        lines.append(f"{index}. {note['text']}")


def _record_list(record: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = record.get(field, [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _non_empty(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _format_evidence_present(value: Any) -> str:
    if value is None:
        return "not applicable"
    return "yes" if value is True else "no"

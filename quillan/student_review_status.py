"""Compact, immutable, read-only status for one student's assignment review."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeAlias, cast

from pds_core.classes import load_class_roster
from pds_core.identifiers import validate_identifier
from pds_core.rosters import RosterError, student_display_name

from quillan.assignment_summary_context import feedback_status, relative_path_for
from quillan.feedback_export import feedback_export_path, feedback_pdf_export_path
from quillan.minimum_requirement_review import configured_requirements
from quillan.plain_paper_submission import is_plain_paper_submission
from quillan.review_status_display import review_progress_status
from quillan.response_page_observations import group_response_page_observations_by_student
from quillan.record_context import (
    InvalidReviewError,
    InvalidSubmissionError,
    MissingSubmissionError,
    OrphanReviewError,
    QuillanRecordContextError,
    RecordIdentityMismatchError,
    ReviewLoadingPolicy,
    load_quillan_assignment_context,
    load_quillan_student_review_context,
    mutable_json_copy,
    student_record_paths,
)
from quillan.work_paths import quillan_work_ref

REVIEW_STATUS_SCHEMA_VERSION: Final = "1"
REVIEW_STATUS_RECORD_TYPE: Final = "quillan_student_review_status"
PAGE_STATES: Final = ("present", "missing", "duplicate", "needs_rescan", "excluded")
EXPORT_KEYS: Final = ("feedback_pdf", "feedback_markdown")

FrozenValue: TypeAlias = str | int | bool | None | "FrozenMapping" | tuple["FrozenValue", ...]


class StudentReviewStatusError(ValueError):
    """Raised when the required assignment context cannot be loaded safely."""


@dataclass(frozen=True, slots=True)
class FrozenMapping(Mapping[str, FrozenValue]):
    """A small deterministic immutable mapping used by the public status model."""

    items_tuple: tuple[tuple[str, FrozenValue], ...]

    def __getitem__(self, key: str) -> FrozenValue:
        for item_key, value in self.items_tuple:
            if item_key == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self.items_tuple)

    def __len__(self) -> int:
        return len(self.items_tuple)


@dataclass(frozen=True, slots=True)
class StudentReviewStatus:
    """Immutable status model shared by text and JSON representations."""

    class_id: str
    assignment_id: str
    student_id: str
    assignment: FrozenMapping
    student: FrozenMapping
    routed_evidence: FrozenMapping
    submission: FrozenMapping
    review: FrozenMapping
    warnings: tuple[str, ...]


def build_student_review_status(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> StudentReviewStatus:
    """Inspect only the selected student's canonical records without writing."""
    try:
        validate_identifier(class_id, "class_id")
        validate_identifier(assignment_id, "assignment_id")
        validate_identifier(student_id, "student_id")
    except ValueError as error:
        raise StudentReviewStatusError(str(error)) from error

    work_ref = quillan_work_ref(class_id, assignment_id)
    try:
        assignment_context = load_quillan_assignment_context(workspace_root, work_ref)
        root = assignment_context.paths.workspace_root
        assignment_path = assignment_context.paths.assignment_path
        assignment = mutable_json_copy(assignment_context.assignment)
        paths = student_record_paths(root, work_ref, student_id)
    except (OSError, QuillanRecordContextError) as error:
        raise StudentReviewStatusError(f"Could not load assignment: {error}") from error

    warnings: list[str] = []
    display_name = student_id
    roster_status = "roster_unavailable"
    try:
        roster = load_class_roster(root, class_id)
    except (OSError, RosterError):
        warnings.append("roster_unavailable")
    else:
        roster_status = "unrostered"
        for student in roster.students:
            if student.student_id == student_id:
                display_name = student_display_name(student)
                roster_status = "rostered"
                break
        if roster_status == "unrostered":
            warnings.append("unrostered_student")

    routed_available = True
    routed_count: int | None
    try:
        observations = group_response_page_observations_by_student(
            root, class_id, assignment_id
        )
        routed_count = len(observations.get(student_id, ()))
    except (OSError, ValueError):
        routed_available = False
        routed_count = None
        warnings.append("routed_evidence_unavailable")

    manifest_path = paths.submission_manifest_path
    review_path = paths.review_record_path
    manifest: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    submission_status = "missing"
    review_status = "missing"
    try:
        record_context = load_quillan_student_review_context(
            root,
            work_ref,
            student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
        )
    except MissingSubmissionError:
        pass
    except OrphanReviewError:
        review_status = "orphaned"
        warnings.append("review_without_valid_submission")
    except InvalidSubmissionError:
        submission_status = "invalid"
        warnings.append("invalid_submission")
    except InvalidReviewError as error:
        submission_status = "valid"
        review_status = "invalid"
        warnings.append("invalid_review")
        if error.submission_record is not None:
            manifest = mutable_json_copy(error.submission_record.value)
    except RecordIdentityMismatchError:
        submission_status = "identity_mismatch"
        review_status = "identity_mismatch"
        warnings.append("identity_mismatch")
    except QuillanRecordContextError:
        submission_status = "invalid"
        review_status = "invalid"
        warnings.append("unsafe_path")
    else:
        manifest = mutable_json_copy(record_context.submission)
        submission_status = "valid"
        if record_context.review is not None:
            review = mutable_json_copy(record_context.review)
            review_status = "valid"
    needs_assembly = None if routed_count is None else bool(routed_count) and manifest is None
    if needs_assembly:
        warnings.append("routed_evidence_needs_assembly")
    if submission_status == "missing":
        warnings.append("missing_submission")
    if review_status == "missing":
        warnings.append("missing_review")
    orphaned = review_status == "orphaned"
    if orphaned:
        warnings.append("review_without_valid_submission")

    requirements = configured_requirements(assignment)
    focus_ids = tuple(str(value) for value in assignment["focus_standard_ids"])
    submission_section = _submission_section(manifest, submission_status, manifest_path, root)
    review_section, review_warnings = _review_section(
        root, class_id, assignment_id, student_id, review, review_status, review_path,
        orphaned, requirements, focus_ids,
    )
    warnings.extend(review_warnings)

    return StudentReviewStatus(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        assignment=_freeze({
            "title": assignment["title"],
            "writing_type": assignment["writing_type"],
            "standards_profile_id": assignment["standards_profile_id"],
            "focus_standard_count": len(focus_ids),
            "configured_requirement_count": len(requirements),
            "path": relative_path_for(assignment_path, root),
        }),
        student=_freeze({"display_name": display_name, "roster_status": roster_status}),
        routed_evidence=_freeze({
            "available": routed_available,
            "present": None if routed_count is None else routed_count > 0,
            "file_count": routed_count,
            "needs_assembly": needs_assembly,
        }),
        submission=_freeze(submission_section),
        review=_freeze(review_section),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _submission_section(
    manifest: dict[str, Any] | None, status: str, path: Path, root: Path
) -> dict[str, Any]:
    unavailable_pages = {
        "available": False, "total": None,
        "states": {state: None for state in PAGE_STATES},
        "present_unselected": None, "with_selected_evidence": None,
        "without_selected_evidence": None,
    }
    unavailable_evidence = {"available": False, "total": None, "selected": None}
    if manifest is None:
        return {
            "status": status, "path": relative_path_for(path, root), "state": None,
            "plain_paper": None, "expected_pages": None, "created_at": None,
            "updated_at": None, "pages": unavailable_pages, "evidence": unavailable_evidence,
        }
    plain_paper = is_plain_paper_submission(manifest)
    pages = manifest["pages"]
    page_states = Counter(str(page["page_state"]) for page in pages)
    evidence_total = sum(len(page["evidence"]) for page in pages)
    selected = sum(page["selected_evidence_id"] is not None for page in pages)
    present = [page for page in pages if page["page_state"] == "present"]
    return {
        "status": "valid", "path": relative_path_for(path, root),
        "state": manifest["submission_state"], "plain_paper": plain_paper,
        "expected_pages": manifest["expected_pages"], "created_at": manifest["created_at"],
        "updated_at": manifest["updated_at"],
        "pages": {
            "available": True, "total": len(pages),
            "states": {state: page_states[state] for state in PAGE_STATES},
            "present_unselected": sum(page["selected_evidence_id"] is None for page in present),
            "with_selected_evidence": selected,
            "without_selected_evidence": len(pages) - selected,
        },
        "evidence": {"available": True, "total": evidence_total, "selected": selected},
    }


def _review_section(
    root: Path, class_id: str, assignment_id: str, student_id: str,
    review: dict[str, Any] | None, status: str, path: Path, orphaned: bool,
    requirements: tuple[Any, ...], focus_ids: tuple[str, ...],
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    configured = set(focus_ids)
    usable = status in {"valid", "missing"}
    missing = status == "missing"
    available = usable
    if review is None and not missing:
        stored: int | None = None
        unavailable_minimum = {
            "available": False, "configured": len(requirements), "stored": None,
            "current": None, "unchecked": None, "met": None, "unmet": None,
            "stale": None, "outcome": None, "returned_without_full_review": None,
            "outcome_note_present": None,
        }
        return _empty_review_section(
            root, class_id, assignment_id, student_id, status, path, orphaned,
            unavailable_minimum, stored,
        ), warnings

    checks = [] if review is None else review["minimum_requirement_checks"]
    requirement_keys = {item.key for item in requirements}
    current_checks = [check for check in checks if check["requirement_key"] in requirement_keys]
    stale_checks = len(checks) - len(current_checks)
    if stale_checks:
        warnings.append("stale_requirement_checks")
    outcome = None if review is None else review["minimum_requirement_outcome"]
    minimum: dict[str, Any] = {
        "available": True, "configured": len(requirements), "stored": len(checks),
        "current": len(current_checks), "unchecked": len(requirements) - len(current_checks),
        "met": sum(check["met"] is True for check in current_checks),
        "unmet": sum(check["met"] is False for check in current_checks), "stale": stale_checks,
        "outcome": "not_checked" if outcome is None else outcome["status"],
        "returned_without_full_review": False if outcome is None else outcome["returned_without_full_review"],
        "outcome_note_present": False if outcome is None else bool(outcome["teacher_note"]),
    }
    units = [] if review is None else review["review_units"]
    observations = [observation for unit in units for observation in unit["standard_observations"]]
    represented = {str(item["standard_id"]) for item in observations} & configured
    stale_observations = sum(str(item["standard_id"]) not in configured for item in observations)
    if stale_observations:
        warnings.append("observations_for_unconfigured_standard")
    ratings = [] if review is None else review["overall_standard_ratings"]
    current_ratings = [item for item in ratings if str(item["standard_id"]) in configured]
    stale_ratings = len(ratings) - len(current_ratings)
    if stale_ratings:
        warnings.append("ratings_for_unconfigured_standard")
    standard_feedback = [] if review is None else review["feedback"]["standard_feedback"]
    current_feedback = [item for item in standard_feedback if str(item["standard_id"]) in configured]
    stale_feedback = len(standard_feedback) - len(current_feedback)
    if stale_feedback:
        warnings.append("feedback_for_unconfigured_standard")
    comments = [comment for item in standard_feedback for comment in item["comments"]]
    feedback = {} if review is None else review["feedback"]
    progress = review_progress_status(review)
    returned = bool(minimum["returned_without_full_review"]) or progress.is_returned_without_full_review

    exports, export_warnings = _exports(root, class_id, assignment_id, student_id, review)
    warnings.extend(export_warnings)
    section = {
        "status": status, "path": relative_path_for(path, root), "orphaned": orphaned,
        "state": None if review is None else review["review_state"],
        "state_label": "no review record" if review is None else progress.review_state_label,
        "created_at": None if review is None else review["created_at"],
        "updated_at": None if review is None else review["updated_at"],
        "progress": {
            "returned_without_full_review": returned,
            "observations_complete": False if review is None else progress.observations_complete,
            "ratings_complete": False if review is None else progress.ratings_complete,
            "feedback_composed": False if review is None else progress.feedback_composed,
            "ready_for_export": False if review is None else progress.ready_for_export,
            "exported": False if review is None else progress.exported,
        },
        "minimum_requirements": minimum,
        "review_units": {
            "available": available, "total": len(units),
            "with_page_targets": sum(unit.get("page_number") is not None for unit in units),
            "with_evidence_ids": sum(unit.get("evidence_id") is not None for unit in units),
            "empty": sum(not unit["standard_observations"] for unit in units),
            "with_observations": sum(bool(unit["standard_observations"]) for unit in units),
        },
        "observations": {
            "available": available, "total": len(observations),
            "applicable": sum(item["applicable"] is True for item in observations),
            "not_applicable": sum(item["applicable"] is False for item in observations),
            "evidence_present": sum(item["evidence_present"] is True for item in observations),
            "evidence_missing": sum(item["evidence_present"] is False for item in observations),
            "evidence_not_applicable": sum(item["evidence_present"] is None for item in observations),
            "with_rating": sum(item["rating"] is not None for item in observations),
            "with_rationale": sum(bool(item["rationale"]) for item in observations),
            "included_for_feedback": sum(item["include_in_feedback"] is True for item in observations),
            "configured_standards_represented": len(represented), "unconfigured": stale_observations,
        },
        "overall_ratings": {
            "available": available, "configured": len(focus_ids), "stored": len(ratings),
            "current": len(current_ratings), "missing": len(focus_ids) - len({str(x['standard_id']) for x in current_ratings}),
            "stale": stale_ratings,
            "included_in_feedback": sum(item["include_in_feedback"] is True for item in ratings),
            "with_rationale": sum(bool(item["rationale"]) for item in ratings),
        },
        "feedback": {
            "available": available, "stored_records": len(standard_feedback),
            "current_records": len(current_feedback),
            "missing_configured_records": len(focus_ids) - len({str(x['standard_id']) for x in current_feedback}),
            "stale_records": stale_feedback,
            "selected_observation_references": sum(len(item["included_observation_ids"]) for item in standard_feedback),
            "include_overall_rating_records": sum(item["include_overall_rating"] is True for item in standard_feedback),
            "include_overall_rationale_records": sum(item["include_overall_rationale"] is True for item in standard_feedback),
            "comments_total": len(comments),
            "comments_included": sum(item["include_in_feedback"] is True for item in comments),
            "comments_excluded": sum(item["include_in_feedback"] is False for item in comments),
            "custom_comments": sum(item["source"] == "custom" for item in comments),
            "reusable_snapshots": sum(item["source"] == "reusable_focus_standard_comment" for item in comments),
            "save_for_reuse": sum(item["save_for_reuse"] is True for item in comments),
            "include_review_unit_observations": bool(feedback.get("include_review_unit_observations", False)),
            "include_overall_standard_ratings": bool(feedback.get("include_overall_standard_ratings", False)),
        },
        "private_notes": {"available": available, "total": 0 if review is None else len(review["private_notes"])},
        "exports": exports,
    }
    return section, warnings


def _empty_review_section(
    root: Path, class_id: str, assignment_id: str, student_id: str, status: str,
    path: Path, orphaned: bool, minimum: dict[str, Any], value: int | None,
) -> dict[str, Any]:
    def group(keys: tuple[str, ...]) -> dict[str, Any]:
        return {"available": False, **{key: value for key in keys}}
    exports, _ = _exports(root, class_id, assignment_id, student_id, None)
    return {
        "status": status, "path": relative_path_for(path, root), "orphaned": orphaned,
        "state": None, "state_label": None, "created_at": None, "updated_at": None,
        "progress": {key: None for key in ("returned_without_full_review", "observations_complete", "ratings_complete", "feedback_composed", "ready_for_export", "exported")},
        "minimum_requirements": minimum,
        "review_units": group(("total", "with_page_targets", "with_evidence_ids", "empty", "with_observations")),
        "observations": group(("total", "applicable", "not_applicable", "evidence_present", "evidence_missing", "evidence_not_applicable", "with_rating", "with_rationale", "included_for_feedback", "configured_standards_represented", "unconfigured")),
        "overall_ratings": group(("configured", "stored", "current", "missing", "stale", "included_in_feedback", "with_rationale")),
        "feedback": group(("stored_records", "current_records", "missing_configured_records", "stale_records", "selected_observation_references", "include_overall_rating_records", "include_overall_rationale_records", "comments_total", "comments_included", "comments_excluded", "custom_comments", "reusable_snapshots", "save_for_reuse", "include_review_unit_observations", "include_overall_standard_ratings")),
        "private_notes": {"available": False, "total": value}, "exports": exports,
    }


def _exports(
    root: Path, class_id: str, assignment_id: str, student_id: str,
    review: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    results: dict[str, Any] = {}
    warnings: list[str] = []
    defaults = {
        "feedback_pdf": feedback_pdf_export_path(root, class_id, assignment_id, student_id),
        "feedback_markdown": feedback_export_path(root, class_id, assignment_id, student_id),
    }
    for key in EXPORT_KEYS:
        relative, status, stale_text, codes = feedback_status(root, review, key, defaults[key])
        metadata = None if review is None else review["exports"].get(key)
        results[key] = {
            "path": relative, "metadata_present": isinstance(metadata, dict),
            "file_present": (root / relative).is_file(), "status": status,
            "stale": stale_text == "true",
            "generated_at": metadata.get("generated_at") if isinstance(metadata, dict) else None,
            "source_review_updated_at": metadata.get("source_review_updated_at") if isinstance(metadata, dict) else None,
        }
        warnings.extend(codes)
    counts = Counter(str(results[key]["status"]) for key in EXPORT_KEYS)
    results["summary"] = {
        "current": counts["present"], "stale": counts["stale"],
        "missing": counts["missing"], "unknown": counts["unknown"],
        "metadata_present": sum(bool(results[key]["metadata_present"]) for key in EXPORT_KEYS),
    }
    return results, warnings


def student_review_status_to_dict(status: StudentReviewStatus) -> dict[str, object]:
    """Serialize the immutable model to the stable schema-version-1 object."""
    return {
        "schema_version": REVIEW_STATUS_SCHEMA_VERSION,
        "record_type": REVIEW_STATUS_RECORD_TYPE,
        "class_id": status.class_id,
        "assignment_id": status.assignment_id,
        "student_id": status.student_id,
        "assignment": _thaw(status.assignment),
        "student": _thaw(status.student),
        "routed_evidence": _thaw(status.routed_evidence),
        "submission": _thaw(status.submission),
        "review": _thaw(status.review),
        "warnings": list(status.warnings),
    }


def format_student_review_status(status: StudentReviewStatus) -> str:
    """Render compact teacher-readable status without review prose."""
    d = student_review_status_to_dict(status)
    assignment = cast(dict[str, Any], d["assignment"])
    student = cast(dict[str, Any], d["student"])
    routed = cast(dict[str, Any], d["routed_evidence"])
    submission = cast(dict[str, Any], d["submission"])
    review = cast(dict[str, Any], d["review"])
    pages, evidence = submission["pages"], submission["evidence"]
    minimum = review["minimum_requirements"]
    units, observations = review["review_units"], review["observations"]
    ratings, feedback = review["overall_ratings"], review["feedback"]
    lines = [
        "Student Review Status", "",
        f"Class: {status.class_id}",
        f"Assignment: {assignment['title']} ({status.assignment_id})",
        f"Student: {student['display_name']} ({status.student_id})",
        f"Roster status: {student['roster_status']}", "",
        "Routed evidence:",
        f"- Available: {_yes_no(routed['available'])}",
        f"- Files: {_value(routed['file_count'])}",
        f"- Needs assembly: {_yes_no(routed['needs_assembly'])}", "",
        "Submission:", f"- Record: {submission['status']}",
        f"- State: {_value(submission['state'])}",
        f"- Plain-paper submission: {_yes_no(submission['plain_paper'])}",
        f"- Expected pages: {_value(submission['expected_pages'])}",
        f"- Digital pages: {_value(pages['total'])}",
        f"- Evidence records: {_value(evidence['total'])}",
        f"- Selected evidence: {_value(evidence['selected'])}",
        f"- Manifest: {submission['path']}",
    ]
    if submission["plain_paper"] is True:
        lines.append("- Physical paper remains outside Quillan")
    lines.extend([
        "", "Review:", f"- Record: {review['status']}",
        f"- Orphaned: {_yes_no(review['orphaned'])}",
        f"- State: {_value(review['state_label'])}", f"- Review record: {review['path']}",
        "", "Minimum requirements:",
        f"- Configured: {minimum['configured']}", f"- Checked: {_value(minimum['current'])}",
        f"- Met: {_value(minimum['met'])}", f"- Unmet: {_value(minimum['unmet'])}",
        f"- Stale checks: {_value(minimum['stale'])}", f"- Outcome: {_value(minimum['outcome'])}",
        "", "Review artifacts:",
        f"- Review units: {_value(units['total'])}", f"- Observations: {_value(observations['total'])}",
        f"- Observations included for feedback: {_value(observations['included_for_feedback'])}",
        f"- Overall ratings: {_value(ratings['current'])}/{ratings['configured']}",
        f"- Feedback records: {_value(feedback['current_records'])}/{assignment['focus_standard_count']}",
        f"- Feedback comments: {_value(feedback['comments_total'])} total; {_value(feedback['comments_included'])} included",
        f"- Private notes: {_value(review['private_notes']['total'])}", "", "Feedback exports:",
        f"- PDF: {review['exports']['feedback_pdf']['status']} — {review['exports']['feedback_pdf']['path']}",
        f"- Markdown: {review['exports']['feedback_markdown']['status']} — {review['exports']['feedback_markdown']['path']}",
        "", "Warnings:",
    ])
    lines.extend(f"- {code}" for code in status.warnings)
    if not status.warnings:
        lines.append("- none")
    return "\n".join(lines)


def _freeze(value: Mapping[str, Any]) -> FrozenMapping:
    def one(item: Any) -> FrozenValue:
        if isinstance(item, Mapping):
            return FrozenMapping(tuple((str(key), one(child)) for key, child in item.items()))
        if isinstance(item, (list, tuple)):
            return tuple(one(child) for child in item)
        return cast(str | int | bool | None, item)
    return cast(FrozenMapping, one(value))


def _thaw(value: FrozenValue) -> Any:
    if isinstance(value, FrozenMapping):
        return {key: _thaw(child) for key, child in value.items_tuple}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


def _value(value: object) -> str:
    return "unavailable" if value is None else str(value)


def _yes_no(value: object) -> str:
    return "unavailable" if value is None else "yes" if value is True else "no"
    ReviewLoadingPolicy,

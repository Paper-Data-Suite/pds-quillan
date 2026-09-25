"""Fresh assignment-level projection of unresolved resubmission evidence."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal, cast

from pds_core.rosters import student_display_name

from quillan.plain_paper_submission import is_plain_paper_submission
from quillan.record_context import (
    InvalidReviewError,
    InvalidSubmissionError,
    MissingSubmissionError,
    OrphanReviewError,
    QuillanRecordContextError,
    RecordIdentityMismatchError,
    ReviewLoadingPolicy,
    load_quillan_student_review_context_from_assignment_context,
    mutable_json_copy,
)
from quillan.response_page_observations import QuillanResponsePageObservation
from quillan.review_read_context import (
    AssignmentReviewReadContext,
    ReviewReadContextError,
    build_assignment_review_read_context,
)
from quillan.submission_evidence_validation import evidence_matches_observation

INBOX_SCHEMA_VERSION: Final = "1"
INBOX_RECORD_TYPE: Final = "quillan_assignment_resubmission_inbox"

TemporalClassification = Literal[
    "new_after_feedback",
    "new_after_review_activity",
    "additional_scanned_evidence",
    "awaiting_assembly",
    "attention_required",
]
TEMPORAL_CLASSIFICATIONS: Final[tuple[TemporalClassification, ...]] = (
    "new_after_feedback",
    "new_after_review_activity",
    "additional_scanned_evidence",
    "awaiting_assembly",
    "attention_required",
)


class ResubmissionInboxError(ValueError):
    """Raised when the resubmission inbox cannot be derived safely."""


@dataclass(frozen=True, slots=True)
class ResubmissionEvidence:
    """Canonical identity and chronology for one evidence observation."""

    evidence_id: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ResubmissionInboxItem:
    """One unresolved candidate, pending observation, or bounded warning."""

    student_id: str
    display_name: str
    roster_status: str
    page_number: int | None
    selected_evidence: ResubmissionEvidence | None
    candidate_evidence: ResubmissionEvidence | None
    temporal_classification: TemporalClassification
    assembly_state: Literal["assembled", "awaiting_assembly", "unavailable"]
    attention_code: str | None = None


@dataclass(frozen=True, slots=True)
class AssignmentResubmissionInbox:
    """Immutable, deterministic assignment-level inbox projection."""

    class_id: str
    assignment_id: str
    assignment_title: str
    items: tuple[ResubmissionInboxItem, ...]
    student_count: int
    page_count: int
    classification_counts: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...]


def build_assignment_resubmission_inbox(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentResubmissionInbox:
    """Build one read-only inbox from a fresh canonical assignment read."""
    try:
        read_context = build_assignment_review_read_context(
            workspace_root, class_id, assignment_id
        )
    except ReviewReadContextError as error:
        raise ResubmissionInboxError(str(error)) from error
    return build_assignment_resubmission_inbox_from_read_context(read_context)


def build_assignment_resubmission_inbox_from_read_context(
    read_context: AssignmentReviewReadContext,
) -> AssignmentResubmissionInbox:
    """Derive the inbox while reusing one #414 redraw-scoped read context."""
    if type(read_context) is not AssignmentReviewReadContext:
        raise ResubmissionInboxError(
            "read_context must be an exact AssignmentReviewReadContext."
        )
    if read_context.observations_by_student is None:
        raise ResubmissionInboxError(
            "Could not verify routed observations: "
            f"{read_context.observations_error or 'unknown observation read failure'}"
        )

    assignment_context = read_context.assignment_context
    assignment = mutable_json_copy(assignment_context.assignment)
    observations_by_student = read_context.observations_by_student
    roster_students = read_context.roster_students
    roster_ids = (
        set() if roster_students is None else {item.student_id for item in roster_students}
    )
    names = (
        {}
        if roster_students is None
        else {
            item.student_id: student_display_name(item)
            for item in roster_students
        }
    )
    roster_order = (
        () if roster_students is None else tuple(item.student_id for item in roster_students)
    )
    ordered_ids = (*roster_order, *sorted(set(observations_by_student) - roster_ids))
    warnings: list[str] = []
    if roster_students is None:
        warnings.append("roster_unavailable")

    items: list[ResubmissionInboxItem] = []
    for student_id in ordered_ids:
        observations = observations_by_student.get(student_id, ())
        if not observations:
            continue
        roster_status = (
            "rostered"
            if student_id in roster_ids
            else "roster_unavailable"
            if roster_students is None
            else "unrostered"
        )
        display_name = names.get(student_id, student_id)
        if roster_status == "unrostered":
            items.append(
                _attention_item(
                    student_id,
                    display_name,
                    roster_status,
                    observations[0].logical_page,
                    "unrostered_student",
                )
            )
            continue

        try:
            student_context = load_quillan_student_review_context_from_assignment_context(
                assignment_context,
                student_id,
                review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
            )
        except MissingSubmissionError:
            items.extend(
                _awaiting_rescan_items(
                    student_id, display_name, roster_status, observations
                )
            )
            continue
        except InvalidReviewError:
            if not _has_rescan_signal(observations):
                continue
            items.append(
                _attention_item(
                    student_id,
                    display_name,
                    roster_status,
                    observations[0].logical_page,
                    "invalid_review",
                )
            )
            continue
        except InvalidSubmissionError:
            if not _has_rescan_signal(observations):
                continue
            items.append(
                _attention_item(
                    student_id,
                    display_name,
                    roster_status,
                    observations[0].logical_page,
                    "invalid_submission",
                )
            )
            continue
        except OrphanReviewError:
            if not _has_rescan_signal(observations):
                continue
            items.append(
                _attention_item(
                    student_id,
                    display_name,
                    roster_status,
                    observations[0].logical_page,
                    "orphan_review",
                )
            )
            continue
        except RecordIdentityMismatchError:
            if not _has_rescan_signal(observations):
                continue
            items.append(
                _attention_item(
                    student_id,
                    display_name,
                    roster_status,
                    observations[0].logical_page,
                    "record_identity_mismatch",
                )
            )
            continue
        except (OSError, QuillanRecordContextError):
            if not _has_rescan_signal(observations):
                continue
            items.append(
                _attention_item(
                    student_id,
                    display_name,
                    roster_status,
                    observations[0].logical_page,
                    "record_or_path_unavailable",
                )
            )
            continue

        manifest = mutable_json_copy(student_context.submission)
        if is_plain_paper_submission(manifest):
            items.append(
                _attention_item(
                    student_id,
                    display_name,
                    roster_status,
                    observations[0].logical_page,
                    "plain_paper_digital_evidence_conflict",
                )
            )
            continue

        review = (
            None
            if student_context.review is None
            else mutable_json_copy(student_context.review)
        )
        items.extend(
            _student_items(
                student_id,
                display_name,
                roster_status,
                manifest,
                review,
                observations,
            )
        )

    rank = {student_id: index for index, student_id in enumerate(ordered_ids)}
    ordered_items = tuple(
        sorted(
            items,
            key=lambda item: (
                rank.get(item.student_id, len(rank)),
                item.page_number or 0,
                "" if item.candidate_evidence is None else item.candidate_evidence.created_at,
                "" if item.candidate_evidence is None else item.candidate_evidence.evidence_id,
                item.attention_code or "",
            ),
        )
    )
    counts = Counter(item.temporal_classification for item in ordered_items)
    return AssignmentResubmissionInbox(
        class_id=read_context.class_id,
        assignment_id=read_context.assignment_id,
        assignment_title=str(assignment["title"]),
        items=ordered_items,
        student_count=len({item.student_id for item in ordered_items}),
        page_count=len(
            {
                (item.student_id, item.page_number)
                for item in ordered_items
                if item.page_number is not None
            }
        ),
        classification_counts=tuple(
            (classification, counts[classification])
            for classification in TEMPORAL_CLASSIFICATIONS
        ),
        warnings=tuple(warnings),
    )


def _student_items(
    student_id: str,
    display_name: str,
    roster_status: str,
    manifest: dict[str, Any],
    review: dict[str, Any] | None,
    observations: tuple[QuillanResponsePageObservation, ...],
) -> tuple[ResubmissionInboxItem, ...]:
    observation_by_id = {item.observation_id: item for item in observations}
    manifest_ids: set[str] = set()
    result: list[ResubmissionInboxItem] = []
    manifest_issuance = manifest["module_details"].get("response_issuance_id")

    for page in cast(list[dict[str, Any]], manifest["pages"]):
        evidence_items = cast(list[dict[str, Any]], page["evidence"])
        manifest_ids.update(str(item["evidence_id"]) for item in evidence_items)
        selected_id = cast(str | None, page["selected_evidence_id"])
        selected_record = next(
            (item for item in evidence_items if item["evidence_id"] == selected_id),
            None,
        )
        selected_observation = (
            None if selected_id is None else observation_by_id.get(selected_id)
        )
        if selected_record is not None and (
            selected_observation is None
            or int(page["page_number"]) != selected_observation.logical_page
            or not evidence_matches_observation(selected_record, selected_observation)
        ):
            result.append(
                _attention_item(
                    student_id,
                    display_name,
                    roster_status,
                    int(page["page_number"]),
                    "selected_evidence_observation_mismatch",
                )
            )
            continue

        selected = (
            None
            if selected_observation is None
            else ResubmissionEvidence(
                selected_observation.observation_id,
                selected_observation.created_at,
            )
        )
        selected_time = (
            None if selected is None else _parse_timestamp(selected.created_at)
        )
        for evidence in evidence_items:
            if evidence["evidence_role"] not in {"candidate", "replacement"}:
                continue
            if evidence["evidence_state"] != "active":
                continue
            evidence_id = str(evidence["evidence_id"])
            observation = observation_by_id.get(evidence_id)
            if (
                observation is None
                or int(page["page_number"]) != observation.logical_page
                or not evidence_matches_observation(evidence, observation)
            ):
                result.append(
                    _attention_item(
                        student_id,
                        display_name,
                        roster_status,
                        int(page["page_number"]),
                        "candidate_evidence_observation_mismatch",
                    )
                )
                continue
            candidate_time = _parse_timestamp(observation.created_at)
            if selected_time is not None and candidate_time <= selected_time:
                continue
            candidate = ResubmissionEvidence(
                observation.observation_id, observation.created_at
            )
            result.append(
                ResubmissionInboxItem(
                    student_id=student_id,
                    display_name=display_name,
                    roster_status=roster_status,
                    page_number=int(page["page_number"]),
                    selected_evidence=selected,
                    candidate_evidence=candidate,
                    temporal_classification=_temporal_classification(
                        candidate_time, review
                    ),
                    assembly_state="assembled",
                )
            )

    for observation in observations:
        if observation.observation_id in manifest_ids:
            continue
        if manifest_issuance != observation.issuance_id:
            result.append(
                _attention_item(
                    student_id,
                    display_name,
                    roster_status,
                    observation.logical_page,
                    "unsupported_issuance_relationship",
                )
            )
            continue
        result.append(
            ResubmissionInboxItem(
                student_id=student_id,
                display_name=display_name,
                roster_status=roster_status,
                page_number=observation.logical_page,
                selected_evidence=None,
                candidate_evidence=ResubmissionEvidence(
                    observation.observation_id, observation.created_at
                ),
                temporal_classification="awaiting_assembly",
                assembly_state="awaiting_assembly",
            )
        )
    return tuple(result)


def _awaiting_rescan_items(
    student_id: str,
    display_name: str,
    roster_status: str,
    observations: tuple[QuillanResponsePageObservation, ...],
) -> tuple[ResubmissionInboxItem, ...]:
    by_page: dict[int, list[QuillanResponsePageObservation]] = {}
    for observation in observations:
        by_page.setdefault(observation.logical_page, []).append(observation)
    later_observations = tuple(
        observation
        for page_number in sorted(by_page)
        for observation in sorted(
            by_page[page_number],
            key=lambda item: (
                item.created_at,
                item.source_scan_id,
                item.source_page_number,
                item.observation_id,
            ),
        )[1:]
    )
    return tuple(
        ResubmissionInboxItem(
            student_id=student_id,
            display_name=display_name,
            roster_status=roster_status,
            page_number=observation.logical_page,
            selected_evidence=None,
            candidate_evidence=ResubmissionEvidence(
                observation.observation_id, observation.created_at
            ),
            temporal_classification="awaiting_assembly",
            assembly_state="awaiting_assembly",
        )
        for observation in later_observations
    )


def _has_rescan_signal(
    observations: tuple[QuillanResponsePageObservation, ...],
) -> bool:
    return any(
        sum(item.logical_page == page for item in observations) > 1
        for page in {item.logical_page for item in observations}
    )


def _attention_item(
    student_id: str,
    display_name: str,
    roster_status: str,
    page_number: int | None,
    code: str,
) -> ResubmissionInboxItem:
    return ResubmissionInboxItem(
        student_id=student_id,
        display_name=display_name,
        roster_status=roster_status,
        page_number=page_number,
        selected_evidence=None,
        candidate_evidence=None,
        temporal_classification="attention_required",
        assembly_state="unavailable",
        attention_code=code,
    )


def _temporal_classification(
    candidate_time: datetime, review: dict[str, Any] | None
) -> TemporalClassification:
    if review is None:
        return "additional_scanned_evidence"
    exports = review["exports"]
    export_times = [
        _parse_timestamp(metadata["generated_at"])
        for metadata in exports.values()
        if isinstance(metadata, dict)
    ]
    if export_times:
        return (
            "new_after_feedback"
            if candidate_time > max(export_times)
            else "additional_scanned_evidence"
        )
    review_time = _parse_timestamp(str(review["updated_at"]))
    return (
        "new_after_review_activity"
        if candidate_time > review_time
        else "additional_scanned_evidence"
    )


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResubmissionInboxError("Canonical timestamp must be timezone-aware.")
    return parsed


def assignment_resubmission_inbox_to_dict(
    inbox: AssignmentResubmissionInbox,
) -> dict[str, object]:
    """Serialize the deterministic privacy-conscious schema-version-1 view."""
    return {
        "schema_version": INBOX_SCHEMA_VERSION,
        "record_type": INBOX_RECORD_TYPE,
        "class_id": inbox.class_id,
        "assignment_id": inbox.assignment_id,
        "assignment_title": inbox.assignment_title,
        "summary": {
            "students_with_new_evidence": inbox.student_count,
            "pages_needing_review": inbox.page_count,
            **dict(inbox.classification_counts),
        },
        "items": [
            {
                "student_id": item.student_id,
                "display_name": item.display_name,
                "roster_status": item.roster_status,
                "page_number": item.page_number,
                "selected_evidence": _evidence_to_dict(item.selected_evidence),
                "candidate_evidence": _evidence_to_dict(item.candidate_evidence),
                "temporal_classification": item.temporal_classification,
                "assembly_state": item.assembly_state,
                "attention_code": item.attention_code,
            }
            for item in inbox.items
        ],
        "warnings": list(inbox.warnings),
    }


def _evidence_to_dict(evidence: ResubmissionEvidence | None) -> object:
    if evidence is None:
        return None
    return {"evidence_id": evidence.evidence_id, "created_at": evidence.created_at}


def format_assignment_resubmission_inbox(
    inbox: AssignmentResubmissionInbox,
) -> str:
    """Render concise teacher-facing inbox text without filesystem paths."""
    counts = dict(inbox.classification_counts)
    lines = [
        "Resubmission / Rescan Review",
        "",
        "Active context",
        f"Class: {inbox.class_id}",
        f"Assignment: {inbox.assignment_id} - {inbox.assignment_title}",
        "",
        f"Students with new scanned evidence: {inbox.student_count}",
        f"Pages needing review: {inbox.page_count}",
        "",
        f"New after recorded feedback export: {counts['new_after_feedback']}",
        f"New after recorded review activity: {counts['new_after_review_activity']}",
        f"Additional scanned evidence: {counts['additional_scanned_evidence']}",
        f"Awaiting assembly: {counts['awaiting_assembly']}",
        f"Attention required: {counts['attention_required']}",
    ]
    if inbox.items:
        lines.append("")
        for index, item in enumerate(inbox.items, start=1):
            identity = (
                item.display_name
                if item.display_name == item.student_id
                else f"{item.display_name} ({item.student_id})"
            )
            page = "page unknown" if item.page_number is None else f"page {item.page_number}"
            label = {
                "new_after_feedback": "new after feedback",
                "new_after_review_activity": "new after recorded review activity",
                "additional_scanned_evidence": "additional scanned evidence",
                "awaiting_assembly": "awaiting assembly",
                "attention_required": "attention required",
            }[item.temporal_classification]
            scanned = (
                ""
                if item.candidate_evidence is None
                else f" - scanned {item.candidate_evidence.created_at}"
            )
            lines.append(f"{index}. {identity} - {page} - {label}{scanned}")
    else:
        lines.extend(("", "No resubmission or rescan evidence currently needs review."))
    if inbox.warnings:
        lines.extend(("", "Warnings: " + ", ".join(inbox.warnings)))
    return "\n".join(lines)


__all__ = [
    "AssignmentResubmissionInbox",
    "INBOX_RECORD_TYPE",
    "INBOX_SCHEMA_VERSION",
    "ResubmissionEvidence",
    "ResubmissionInboxError",
    "ResubmissionInboxItem",
    "assignment_resubmission_inbox_to_dict",
    "build_assignment_resubmission_inbox",
    "build_assignment_resubmission_inbox_from_read_context",
    "format_assignment_resubmission_inbox",
]

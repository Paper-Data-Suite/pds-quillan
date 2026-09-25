"""Explicit teacher resolution of one active submission evidence candidate."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.record_context import (
    MissingSubmissionError,
    QuillanRecordContextError,
    QuillanStudentReviewContext,
    ReviewLoadingPolicy,
    load_quillan_student_review_context_from_assignment_context,
    mutable_json_copy,
)
from quillan.review_record import ReviewRecordError
from quillan.review_record_paths import (
    ReviewRecordPathError,
    update_quillan_review_record,
)
from quillan.review_read_context import (
    ReviewReadContextError,
    build_assignment_review_read_context,
)
from quillan.submission_evidence_validation import (
    evidence_matches_observation,
    selected_evidence_fingerprint,
)
from quillan.submission_manifest import (
    SubmissionManifestError,
    validate_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    update_quillan_submission_manifest,
)


class SubmissionEvidenceResolutionError(ValueError):
    """Raised when an evidence decision cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class ResolvedSubmissionEvidence:
    """Result of one explicit, revision-guarded evidence decision."""

    class_id: str
    assignment_id: str
    student_id: str
    page_number: int
    evidence_id: str
    action: Literal["selected", "dismissed"]
    previous_selected_evidence_id: str | None
    selected_evidence_id: str | None
    updated_at: str


def select_submission_evidence_candidate(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
    evidence_id: str,
    *,
    timestamp: datetime | str | None = None,
) -> ResolvedSubmissionEvidence:
    """Promote one actionable candidate while retaining all prior evidence."""
    return _resolve(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
        page_number,
        evidence_id,
        action="selected",
        timestamp=timestamp,
    )


def dismiss_submission_evidence_candidate(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
    evidence_id: str,
    *,
    timestamp: datetime | str | None = None,
) -> ResolvedSubmissionEvidence:
    """Remove one candidate from active review without deleting provenance."""
    return _resolve(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
        page_number,
        evidence_id,
        action="dismissed",
        timestamp=timestamp,
    )


def _resolve(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    page_number: int,
    evidence_id: str,
    *,
    action: Literal["selected", "dismissed"],
    timestamp: datetime | str | None,
) -> ResolvedSubmissionEvidence:
    _validate_identity(class_id, assignment_id, student_id, evidence_id, page_number)
    try:
        read_context = build_assignment_review_read_context(
            workspace_root, class_id, assignment_id
        )
    except ReviewReadContextError as error:
        raise SubmissionEvidenceResolutionError(
            f"Could not verify assignment evidence: {error}"
        ) from error
    if read_context.observations_by_student is None:
        raise SubmissionEvidenceResolutionError(
            "Could not verify routed observations: "
            f"{read_context.observations_error or 'unknown observation read failure'}"
        )
    observations = read_context.observations_by_student.get(student_id, ())
    observation_by_id = {item.observation_id: item for item in observations}

    try:
        context = load_quillan_student_review_context_from_assignment_context(
            read_context.assignment_context,
            student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
        )
    except MissingSubmissionError as error:
        raise SubmissionEvidenceResolutionError(
            "The candidate is not assembled into a submission manifest."
        ) from error
    except (OSError, QuillanRecordContextError) as error:
        raise SubmissionEvidenceResolutionError(
            f"Could not load the canonical submission: {error}"
        ) from error

    manifest = mutable_json_copy(context.submission)
    page = _page(manifest, page_number)
    evidence = _evidence(page, evidence_id)
    if evidence["evidence_role"] not in {"candidate", "replacement"} or evidence[
        "evidence_state"
    ] != "active":
        raise SubmissionEvidenceResolutionError(
            "The requested evidence is not an active candidate."
        )
    candidate_observation = observation_by_id.get(evidence_id)
    if (
        candidate_observation is None
        or candidate_observation.logical_page != page_number
        or not evidence_matches_observation(evidence, candidate_observation)
    ):
        raise SubmissionEvidenceResolutionError(
            "The candidate does not match one strictly verified observation."
        )
    selected_id = cast(str | None, page["selected_evidence_id"])
    if selected_id is not None:
        selected = _evidence(page, selected_id)
        selected_observation = observation_by_id.get(selected_id)
        if (
            selected_observation is None
            or selected_observation.logical_page != page_number
            or not evidence_matches_observation(selected, selected_observation)
        ):
            raise SubmissionEvidenceResolutionError(
                "The current selection does not match one strictly verified observation."
            )
        if _parsed(candidate_observation.created_at) <= _parsed(
            selected_observation.created_at
        ):
            raise SubmissionEvidenceResolutionError(
                "The requested candidate is not newer than the current selection."
            )
    elif action == "dismissed":
        raise SubmissionEvidenceResolutionError(
            "A candidate cannot be dismissed until the page has authoritative "
            "selected evidence."
        )

    if action == "selected":
        _bind_legacy_feedback_exports_to_selection(context, manifest)

    updated = deepcopy(manifest)
    updated_page = _page(updated, page_number)
    updated_evidence = _evidence(updated_page, evidence_id)
    if action == "selected":
        for item in cast(list[dict[str, Any]], updated_page["evidence"]):
            if item["evidence_role"] == "selected":
                item["evidence_role"] = "candidate"
        updated_evidence["evidence_role"] = "selected"
        updated_evidence["evidence_state"] = "active"
        updated_page["selected_evidence_id"] = evidence_id
    else:
        updated_evidence["evidence_role"] = "excluded"
        updated_evidence["evidence_state"] = "excluded"

    updated_page["page_state"] = _page_state(updated_page)
    updated_at = _timestamp(timestamp)
    updated["updated_at"] = updated_at
    try:
        validate_submission_manifest(updated)
        update_quillan_submission_manifest(context, updated)
    except (SubmissionManifestError, SubmissionManifestPathError, OSError) as error:
        raise SubmissionEvidenceResolutionError(
            f"Evidence decision was not saved: {error}"
        ) from error
    return ResolvedSubmissionEvidence(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        page_number=page_number,
        evidence_id=evidence_id,
        action=action,
        previous_selected_evidence_id=selected_id,
        selected_evidence_id=cast(str | None, updated_page["selected_evidence_id"]),
        updated_at=updated_at,
    )


def _bind_legacy_feedback_exports_to_selection(
    context: QuillanStudentReviewContext,
    manifest: dict[str, Any],
) -> None:
    """Bind otherwise-current legacy feedback before authoritative selection moves."""
    if context.review is None:
        return
    review = mutable_json_copy(context.review)
    current_fingerprint = selected_evidence_fingerprint(manifest)
    changed = False
    exports = cast(dict[str, Any], review["exports"])
    for field in ("feedback_pdf", "feedback_markdown"):
        metadata = exports.get(field)
        if not isinstance(metadata, dict):
            continue
        # Already-stale legacy feedback does not need migration, and an existing
        # binding (valid or malformed) must never be rewritten implicitly.
        if metadata.get("source_review_updated_at") != review["updated_at"]:
            continue
        details = metadata.get("module_details")
        if not isinstance(details, dict):
            raise SubmissionEvidenceResolutionError(
                "Legacy feedback metadata has invalid module_details."
            )
        binding_key = "source_selected_evidence_fingerprint"
        if binding_key in details:
            continue
        details[binding_key] = current_fingerprint
        changed = True
    if not changed:
        return
    try:
        update_quillan_review_record(context, review)
    except (ReviewRecordError, ReviewRecordPathError, OSError) as error:
        raise SubmissionEvidenceResolutionError(
            "Could not bind legacy feedback to the current evidence selection: "
            f"{error}"
        ) from error


def _page(manifest: dict[str, Any], page_number: int) -> dict[str, Any]:
    match = next(
        (
            item
            for item in cast(list[dict[str, Any]], manifest["pages"])
            if item["page_number"] == page_number
        ),
        None,
    )
    if match is None:
        raise SubmissionEvidenceResolutionError(
            f"Page {page_number} is not in the canonical submission."
        )
    return match


def _evidence(page: dict[str, Any], evidence_id: str) -> dict[str, Any]:
    matches = [
        item
        for item in cast(list[dict[str, Any]], page["evidence"])
        if item["evidence_id"] == evidence_id
    ]
    if len(matches) != 1:
        raise SubmissionEvidenceResolutionError(
            f"Evidence {evidence_id!r} does not identify exactly one page candidate."
        )
    return matches[0]


def _page_state(page: dict[str, Any]) -> str:
    evidence = cast(list[dict[str, Any]], page["evidence"])
    if not evidence:
        return "missing"
    if len(evidence) > 1:
        return "duplicate"
    if evidence[0]["evidence_state"] in {"needs_rescan", "damaged"}:
        return "needs_rescan"
    return "present"


def _timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(UTC).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise SubmissionEvidenceResolutionError(
                "timestamp must be timezone-aware."
            )
        return value.isoformat()
    _parsed(value)
    return value


def _parsed(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise SubmissionEvidenceResolutionError(
            "timestamp must be timezone-aware ISO 8601 text."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SubmissionEvidenceResolutionError(
            "timestamp must be timezone-aware ISO 8601 text."
        )
    return parsed


def _validate_identity(
    class_id: str,
    assignment_id: str,
    student_id: str,
    evidence_id: str,
    page_number: int,
) -> None:
    try:
        validate_identifier(class_id, "class_id")
        validate_identifier(assignment_id, "assignment_id")
        validate_identifier(student_id, "student_id")
    except (IdentifierValidationError, TypeError, ValueError) as error:
        raise SubmissionEvidenceResolutionError(str(error)) from error
    if not isinstance(evidence_id, str) or not evidence_id:
        raise SubmissionEvidenceResolutionError("evidence_id must be nonempty text.")
    if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
        raise SubmissionEvidenceResolutionError(
            "page_number must be a positive integer."
        )


__all__ = [
    "ResolvedSubmissionEvidence",
    "SubmissionEvidenceResolutionError",
    "dismiss_submission_evidence_candidate",
    "select_submission_evidence_candidate",
]

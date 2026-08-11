"""Pure privacy policy for Quillan publication projections."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Final, Literal, TypeAlias

from quillan.academic_result_manifest import PublishedText

PUBLICATION_PROJECTION_POLICY_VERSION: Final = "quillan_publication_projection_v1"
PUBLISHED_TEXT_MAX_CHARS: Final = 20_000

PublicationFieldDisposition: TypeAlias = Literal["allowed", "source_only", "prohibited"]

_REVIEW_STATES: Final[frozenset[str]] = frozenset(
    {
        "not_started",
        "requirements_checked",
        "returned_without_full_review",
        "observations_in_progress",
        "observations_complete",
        "ratings_complete",
        "feedback_composed",
        "ready_for_export",
        "exported",
    }
)
_MINIMUM_REQUIREMENT_STATUSES: Final[frozenset[str]] = frozenset(
    {"not_checked", "met", "unmet_continue_review", "returned_without_full_review"}
)
_EVIDENCE_ROLES: Final[frozenset[str]] = frozenset(
    {"candidate", "selected", "replacement", "excluded"}
)

RETURNED_REQUIREMENT_FEEDBACK_FIELDS: Final[frozenset[str]] = frozenset(
    {"label", "expected", "teacher_note"}
)

PUBLIC_PDS2_EVIDENCE_REFERENCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "page_id",
        "evidence_id",
        "observation_id",
        "route_id",
        "issuance_id",
        "generation_id",
        "artifact_id",
        "source_page_number",
        "source_scan_id",
        "source_sha256",
        "routed_evidence_sha256",
    }
)

SOURCE_ONLY_NATIVE_RECORDS: Final[frozenset[str]] = frozenset(
    {"assignment.json", "submission.json", "review.json"}
)

PROHIBITED_PUBLICATION_NATIVE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "review.private_notes",
        "review.module_details",
        "review.exports.feedback_pdf.path",
        "review.exports.feedback_markdown.path",
        "feedback.comments.source",
        "feedback.comments.reusable_comment_id",
        "feedback.comments.save_for_reuse",
        "feedback.comments.module_details",
        "minimum_requirement_checks.requirement_check_id",
        "minimum_requirement_checks.module_details",
        "submission.evidence.routed_evidence_path",
        "submission.evidence.duplicate_number",
        "submission.evidence.retained_source.source_filename",
        "submission.evidence.retained_source.retained_source_path",
        "submission.evidence.module_details",
        "submission.module_details",
        "roster.display_data",
        "class_reports",
        "qr_payload",
        "routing_diagnostics",
    }
)


class QuillanPublicationProjectionPolicyError(ValueError):
    """Raised when privacy-policy inputs are malformed or contradictory."""


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise QuillanPublicationProjectionPolicyError(f"{field} must be a boolean.")
    return value


def _required_text(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or "\x00" in value
        or len(value) > PUBLISHED_TEXT_MAX_CHARS
    ):
        raise QuillanPublicationProjectionPolicyError(
            f"{field} must be nonempty publication text of at most "
            f"{PUBLISHED_TEXT_MAX_CHARS} characters."
        )
    return value


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field)


def _native_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise QuillanPublicationProjectionPolicyError(
            f"{field} must be nonempty native identifier text."
        )
    return value


def _published_text(
    source_text: object,
    *,
    include: bool,
    field: str,
) -> PublishedText:
    text = _optional_text(source_text, field)
    if text is None:
        return PublishedText(disposition="absent", text=None)
    if include:
        return PublishedText(disposition="included", text=text)
    return PublishedText(disposition="withheld", text=None)


def observation_is_selected_for_feedback(
    *,
    include_review_unit_observations: bool,
    observation_id: str,
    standard_id: str,
    included_observation_ids_by_standard: Mapping[str, Collection[str]],
) -> bool:
    """Return whether one observation is explicitly selected for student feedback.

    The native observation-level ``include_in_feedback`` flag is intentionally not
    an input. Current Quillan export semantics require the global feedback switch
    plus same-standard membership in ``included_observation_ids``.
    """
    if not _boolean(
        include_review_unit_observations, "include_review_unit_observations"
    ):
        return False
    observation = _native_id(observation_id, "observation_id")
    standard = _native_id(standard_id, "standard_id")
    selected = included_observation_ids_by_standard.get(standard, ())
    if isinstance(selected, (str, bytes)) or not isinstance(selected, Collection):
        raise QuillanPublicationProjectionPolicyError(
            "included_observation_ids_by_standard values must be collections of IDs."
        )
    for candidate in selected:
        _native_id(candidate, "included_observation_id")
    return observation in selected


def project_observation_rationale(
    rationale: str | None,
    *,
    include_review_unit_observations: bool,
    observation_id: str,
    standard_id: str,
    included_observation_ids_by_standard: Mapping[str, Collection[str]],
) -> PublishedText:
    """Project one observation rationale under current feedback-selection rules."""
    include = observation_is_selected_for_feedback(
        include_review_unit_observations=include_review_unit_observations,
        observation_id=observation_id,
        standard_id=standard_id,
        included_observation_ids_by_standard=included_observation_ids_by_standard,
    )
    return _published_text(
        rationale,
        include=include,
        field="standard_observation.rationale",
    )


def overall_rating_is_selected_for_feedback(
    *,
    include_overall_standard_ratings: bool,
    rating_include_in_feedback: bool,
    standard_feedback_include_overall_rating: bool | None,
    standard_feedback_include_overall_rationale: bool | None,
) -> bool:
    """Return whether an overall rating is selected by native feedback semantics."""
    global_enabled = _boolean(
        include_overall_standard_ratings, "include_overall_standard_ratings"
    )
    fallback_enabled = _boolean(
        rating_include_in_feedback, "rating_include_in_feedback"
    )
    pair = (
        standard_feedback_include_overall_rating,
        standard_feedback_include_overall_rationale,
    )
    if (pair[0] is None) != (pair[1] is None):
        raise QuillanPublicationProjectionPolicyError(
            "per-standard overall-rating and rationale controls must both be present "
            "or both be absent."
        )
    if not global_enabled:
        return False
    if pair[0] is None:
        return fallback_enabled
    return _boolean(pair[0], "standard_feedback.include_overall_rating")


def project_overall_rating_rationale(
    rationale: str | None,
    *,
    include_overall_standard_ratings: bool,
    rating_include_in_feedback: bool,
    standard_feedback_include_overall_rating: bool | None,
    standard_feedback_include_overall_rationale: bool | None,
) -> PublishedText:
    """Project one overall-rating rationale without broadening feedback selection."""
    rating_selected = overall_rating_is_selected_for_feedback(
        include_overall_standard_ratings=include_overall_standard_ratings,
        rating_include_in_feedback=rating_include_in_feedback,
        standard_feedback_include_overall_rating=(
            standard_feedback_include_overall_rating
        ),
        standard_feedback_include_overall_rationale=(
            standard_feedback_include_overall_rationale
        ),
    )
    if standard_feedback_include_overall_rationale is None:
        rationale_selected = rating_selected
    else:
        rationale_selected = rating_selected and _boolean(
            standard_feedback_include_overall_rationale,
            "standard_feedback.include_overall_rationale",
        )
    return _published_text(
        rationale,
        include=rationale_selected,
        field="overall_standard_rating.rationale",
    )


def project_feedback_comment_text(
    text: str,
    *,
    include_in_feedback: bool,
) -> PublishedText | None:
    """Return selected feedback-comment text, or omit an unselected comment."""
    selected = _boolean(include_in_feedback, "feedback_comment.include_in_feedback")
    if not selected:
        return None
    return PublishedText(
        disposition="included",
        text=_required_text(text, "feedback_comment.text"),
    )


def _returned_without_full_review(
    *,
    status: str,
    returned_without_full_review: bool,
    review_state: str,
) -> bool:
    if status not in _MINIMUM_REQUIREMENT_STATUSES:
        raise QuillanPublicationProjectionPolicyError(
            "minimum_requirement_outcome.status is invalid."
        )
    if review_state not in _REVIEW_STATES:
        raise QuillanPublicationProjectionPolicyError("review_state is invalid.")
    returned_flag = _boolean(
        returned_without_full_review, "returned_without_full_review"
    )
    returned_signals = (
        status == "returned_without_full_review",
        returned_flag,
        review_state == "returned_without_full_review",
    )
    if len(set(returned_signals)) != 1:
        raise QuillanPublicationProjectionPolicyError(
            "returned-without-full-review status, flag, and review state must agree."
        )
    return returned_signals[0]


def project_minimum_outcome_teacher_note(
    teacher_note: str | None,
    *,
    status: str,
    returned_without_full_review: bool,
    review_state: str,
) -> PublishedText:
    """Project the minimum-outcome note only for the student-facing return state."""
    returned = _returned_without_full_review(
        status=status,
        returned_without_full_review=returned_without_full_review,
        review_state=review_state,
    )
    return _published_text(
        teacher_note,
        include=returned,
        field="minimum_requirement_outcome.teacher_note",
    )


def returned_requirement_check_is_feedback_publishable(
    *,
    requirement_key: str,
    met: bool,
    configured_requirement_keys: Collection[str],
    status: str,
    returned_without_full_review: bool,
    review_state: str,
) -> bool:
    """Return whether one configured unmet check may appear in return feedback."""
    returned = _returned_without_full_review(
        status=status,
        returned_without_full_review=returned_without_full_review,
        review_state=review_state,
    )
    key = _native_id(requirement_key, "requirement_key")
    checked_met = _boolean(met, "minimum_requirement_check.met")
    if isinstance(configured_requirement_keys, (str, bytes)) or not isinstance(
        configured_requirement_keys, Collection
    ):
        raise QuillanPublicationProjectionPolicyError(
            "configured_requirement_keys must be a collection of requirement keys."
        )
    for configured_key in configured_requirement_keys:
        _native_id(configured_key, "configured_requirement_key")
    return returned and not checked_met and key in configured_requirement_keys


def selected_pds2_evidence_is_publishable(
    *,
    page_selected_evidence_id: str | None,
    evidence_id: str,
    evidence_role: str,
) -> bool:
    """Return whether one PDS2 evidence record is the authoritative page selection.

    Contradiction between the page selection and evidence role fails closed. Native
    submission validation should establish the same invariant before this policy is
    applied, but the projection policy does not silently broaden malformed input.
    """
    evidence = _native_id(evidence_id, "evidence_id")
    if evidence_role not in _EVIDENCE_ROLES:
        raise QuillanPublicationProjectionPolicyError("evidence_role is invalid.")
    selected = (
        None
        if page_selected_evidence_id is None
        else _native_id(page_selected_evidence_id, "page_selected_evidence_id")
    )
    role_selected = evidence_role == "selected"
    id_selected = selected == evidence
    if role_selected != id_selected:
        raise QuillanPublicationProjectionPolicyError(
            "page selected_evidence_id and evidence_role='selected' disagree."
        )
    return role_selected and id_selected


def publication_field_disposition(field_path: str) -> PublicationFieldDisposition:
    """Classify fixed high-risk native fields used by policy audits and callers.

    This is intentionally a closed classifier, not a wildcard allowlist. Unknown
    fields fail rather than becoming public by default.
    """
    field = _native_id(field_path, "field_path")
    if field in PROHIBITED_PUBLICATION_NATIVE_FIELDS:
        return "prohibited"
    if field in SOURCE_ONLY_NATIVE_RECORDS:
        return "source_only"
    if field in PUBLIC_PDS2_EVIDENCE_REFERENCE_FIELDS:
        return "allowed"
    raise QuillanPublicationProjectionPolicyError(
        f"field {field!r} has no declared publication disposition."
    )

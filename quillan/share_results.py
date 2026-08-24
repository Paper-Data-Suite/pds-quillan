"""Read-only orchestration status for sharing Quillan results through Core."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from pds_core.academic_work_registrations import AcademicWorkRegistration

from quillan.academic_result_manifest_generation import (
    AcademicResultManifestGenerationContext,
    QuillanManifestGenerationError,
    build_academic_result_manifest,
    load_academic_result_manifest_generation_context,
)
from quillan.academic_result_publication import (
    QuillanAcademicResultPublicationError,
    QuillanPublicationSeriesState,
    load_quillan_publication_series_status,
)
from quillan.academic_work_registration import (
    ManagedAssignmentRegistrationContext,
    QuillanAcademicWorkRegistrationError,
    build_quillan_academic_work_registration_request,
    load_current_quillan_academic_work_registration,
    load_managed_assignment_registration_context,
)
from quillan.class_review_completion import (
    ClassReviewCompletionError,
    build_class_review_completion_view,
)
from quillan.work_paths import quillan_work_ref

SharePublicationPlan: TypeAlias = Literal[
    "manifest_required",
    "initial_publication",
    "supersede_current",
    "already_current",
    "advanced_republication_required",
    "blocked_inconsistent",
]
ShareNextStep: TypeAlias = Literal[
    "register_academic_work",
    "update_cancelled_registration",
    "resolve_native_result_state",
    "generate_manifest",
    "publish_initial",
    "supersede_current",
    "already_shared_current",
    "advanced_republication_required",
    "resolve_publication_state",
]


class ShareResultsError(Exception):
    """Base error for bounded read-only share-status derivation."""


class ShareResultsIntegrityError(ShareResultsError):
    """Canonical registration/publication state cannot be trusted safely."""


@dataclass(frozen=True, slots=True)
class ShareReviewContext:
    """Optional aggregate #388 context; never a publication authorization."""

    roster_count: int
    complete_count: int
    needs_work_count: int
    attention_count: int
    unrostered_diagnostic_count: int
    warning_count: int


@dataclass(frozen=True, slots=True)
class ShareResultsStatus:
    """One immutable assignment-scoped snapshot for the guided share workflow."""

    class_id: str
    assignment_id: str
    assignment_title: str

    registration_revision: int | None
    registration_title: str | None
    registration_title_stale: bool
    academic_intent: str | None
    lifecycle: str | None

    native_result_state_valid: bool
    represented_native_result_count: int | None
    native_state_matches_producer_head: bool | None

    producer_head_revision: int | None
    producer_head_sha256: str | None

    core_head_publication_id: str | None
    core_head_revision: int | None
    core_head_withdrawn: bool
    current_selectable_publication_id: str | None
    catalog_available: bool

    publication_plan: SharePublicationPlan
    next_step: ShareNextStep
    review_context: ShareReviewContext | None
    warnings: tuple[str, ...]


def build_share_results_status(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> ShareResultsStatus:
    """Build one privacy-minimal status snapshot without writing workspace state."""
    root = Path(workspace_root)

    try:
        assignment = load_managed_assignment_registration_context(
            root, class_id, assignment_id
        )
        registration = load_current_quillan_academic_work_registration(
            root, class_id, assignment_id
        )
        series = load_quillan_publication_series_status(
            root, class_id, assignment_id
        )
    except (
        QuillanAcademicWorkRegistrationError,
        QuillanAcademicResultPublicationError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        raise ShareResultsIntegrityError(
            "Could not establish canonical assignment/publication status."
        ) from error

    warnings: list[str] = []

    registration_revision: int | None = None
    registration_title: str | None = None
    registration_title_stale = False
    academic_intent: str | None = None
    lifecycle: str | None = None

    if registration is not None:
        _validate_registration_shape(assignment, registration)
        registration_revision = registration.registration_revision
        registration_title = registration.title
        registration_title_stale = registration.title != assignment.title
        academic_intent = registration.academic_intent
        lifecycle = registration.lifecycle
        if registration_title_stale:
            warnings.append("registration_title_stale")
        if lifecycle == "cancelled":
            warnings.append("registration_cancelled")

    native_valid = True
    represented_count: int | None
    generation_context = None
    try:
        generation_context = load_academic_result_manifest_generation_context(
            root,
            quillan_work_ref(class_id, assignment_id),
        )
        represented_count = sum(
            1 for item in generation_context.native_students if item.result is not None
        )
    except (QuillanManifestGenerationError, OSError, TypeError, ValueError):
        native_valid = False
        represented_count = None
        warnings.append("native_result_state_unavailable")

    native_matches_head = _native_state_matches_head(
        generation_context,
        series,
    )
    publication_plan = plan_share_publication(series)

    review_context = _load_optional_review_context(
        root,
        class_id,
        assignment_id,
        warnings,
    )

    if not series.derived_catalog_available:
        warnings.append("publication_catalog_unavailable")
    if publication_plan == "blocked_inconsistent":
        warnings.append("publication_state_inconsistent")

    next_step = _derive_next_step(
        registration_present=registration is not None,
        registration_lifecycle=lifecycle,
        native_valid=native_valid,
        native_matches_head=native_matches_head,
        publication_plan=publication_plan,
    )

    head = series.producer_head
    core_head = series.core_head
    current = series.current_selectable_publication
    return ShareResultsStatus(
        class_id=class_id,
        assignment_id=assignment_id,
        assignment_title=assignment.title,
        registration_revision=registration_revision,
        registration_title=registration_title,
        registration_title_stale=registration_title_stale,
        academic_intent=academic_intent,
        lifecycle=lifecycle,
        native_result_state_valid=native_valid,
        represented_native_result_count=represented_count,
        native_state_matches_producer_head=native_matches_head,
        producer_head_revision=None if head is None else head.revision,
        producer_head_sha256=None if head is None else head.sha256,
        core_head_publication_id=(
            None if core_head is None else core_head.publication_id
        ),
        core_head_revision=(
            None if core_head is None else core_head.record_set_revision
        ),
        core_head_withdrawn=series.core_head_withdrawal is not None,
        current_selectable_publication_id=(
            None if current is None else current.publication_id
        ),
        catalog_available=series.derived_catalog_available,
        publication_plan=publication_plan,
        next_step=next_step,
        review_context=review_context,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def plan_share_publication(
    series: QuillanPublicationSeriesState,
) -> SharePublicationPlan:
    """Classify only the stored producer/Core relationship for ordinary sharing."""
    producer = series.producer_head
    core = series.core_head

    if producer is None:
        return "manifest_required"
    if core is None:
        return "initial_publication"
    if series.core_head_withdrawal is not None:
        return "advanced_republication_required"

    if (
        core.record_set_revision == producer.revision
        and core.manifest_path == producer.relative_path
        and core.manifest_digest_algorithm == "sha256"
        and core.manifest_digest == producer.sha256
    ):
        return "already_current"

    if producer.revision > core.record_set_revision:
        return "supersede_current"
    return "blocked_inconsistent"


def _validate_registration_shape(
    assignment: ManagedAssignmentRegistrationContext,
    registration: AcademicWorkRegistration,
) -> None:
    """Validate the current registration's fixed Quillan contract without title."""
    try:
        intent = getattr(registration, "academic_intent")
        lifecycle = getattr(registration, "lifecycle")
        expected = build_quillan_academic_work_registration_request(
            assignment,
            academic_intent=intent,
            lifecycle=lifecycle,
        )
        actual_fields = (
            getattr(registration, "work"),
            getattr(registration, "producer_contract_version"),
            getattr(registration, "work_kind"),
            intent,
            lifecycle,
            getattr(registration, "source_records"),
        )
        expected_fields = (
            expected.work,
            expected.producer_contract_version,
            expected.work_kind,
            expected.academic_intent,
            expected.lifecycle,
            expected.source_records,
        )
    except (AttributeError, QuillanAcademicWorkRegistrationError) as error:
        raise ShareResultsIntegrityError(
            "Current Academic Work Registration is not a valid Quillan registration."
        ) from error
    if actual_fields != expected_fields:
        raise ShareResultsIntegrityError(
            "Current Academic Work Registration contradicts Quillan's contract."
        )


def _native_state_matches_head(
    generation_context: AcademicResultManifestGenerationContext | None,
    series: QuillanPublicationSeriesState,
) -> bool | None:
    """Purely compare current projected native state with the immutable head."""
    head = series.producer_head
    if generation_context is None or head is None:
        return None
    try:
        candidate = build_academic_result_manifest(
            generation_context,
            record_set_revision=head.revision,
            generated_at=head.manifest.generated_at,
        )
    except (QuillanManifestGenerationError, TypeError, ValueError):
        return None
    return candidate == head.manifest


def _load_optional_review_context(
    root: Path,
    class_id: str,
    assignment_id: str,
    warnings: list[str],
) -> ShareReviewContext | None:
    try:
        view = build_class_review_completion_view(root, class_id, assignment_id)
    except (ClassReviewCompletionError, OSError, TypeError, ValueError):
        warnings.append("review_completion_unavailable")
        return None
    return ShareReviewContext(
        roster_count=view.roster_count,
        complete_count=view.complete_count,
        needs_work_count=view.needs_work_count,
        attention_count=view.attention_count,
        unrostered_diagnostic_count=len(view.unrostered_student_ids),
        warning_count=len(view.warnings),
    )


def _derive_next_step(
    *,
    registration_present: bool,
    registration_lifecycle: str | None,
    native_valid: bool,
    native_matches_head: bool | None,
    publication_plan: SharePublicationPlan,
) -> ShareNextStep:
    if native_matches_head is True and publication_plan == "already_current":
        return "already_shared_current"
    if not registration_present:
        return "register_academic_work"
    if registration_lifecycle == "cancelled":
        return "update_cancelled_registration"
    if not native_valid:
        return "resolve_native_result_state"
    if native_matches_head is not True:
        return "generate_manifest"
    if publication_plan == "initial_publication":
        return "publish_initial"
    if publication_plan == "supersede_current":
        return "supersede_current"
    if publication_plan == "advanced_republication_required":
        return "advanced_republication_required"
    if publication_plan == "blocked_inconsistent":
        return "resolve_publication_state"
    if publication_plan == "already_current":
        return "already_shared_current"
    return "generate_manifest"


__all__ = [
    "ShareNextStep",
    "SharePublicationPlan",
    "ShareResultsError",
    "ShareResultsIntegrityError",
    "ShareResultsStatus",
    "ShareReviewContext",
    "build_share_results_status",
    "plan_share_publication",
]

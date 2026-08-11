"""Pure revision policy for Quillan Academic Result Manifest publication history."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Any, Final, Literal, TypeAlias, cast

from quillan.academic_result_manifest import (
    AcademicResultManifest,
    QuillanAcademicResultManifestValidationError,
    StudentSourceSnapshot,
    manifest_to_mapping,
    validate_manifest,
)

PUBLICATION_REVISION_POLICY_VERSION: Final = "quillan_publication_revision_v1"
QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID: Final = "academic_results"

ManifestRevisionDisposition: TypeAlias = Literal[
    "reuse_existing", "create_initial", "create_successor"
]
ManifestRevisionReason: TypeAlias = Literal[
    "exact_replay",
    "initial_publication",
    "native_source_changed",
    "publication_projection_changed",
    "historical_reversion",
    "republication_after_withdrawal",
]


class QuillanPublicationRevisionPolicyError(ValueError):
    """Base error for Quillan publication-revision policy decisions."""


class QuillanPublicationRevisionValidationError(QuillanPublicationRevisionPolicyError):
    """Raised when revision-policy inputs are malformed or cross series."""


class QuillanPublicationRevisionConflictError(QuillanPublicationRevisionPolicyError):
    """Raised when immutable revision history would be contradicted or reused."""


@dataclass(frozen=True, slots=True)
class ManifestRevisionPlan:
    """One immutable producer decision about an Academic Result manifest revision."""

    disposition: ManifestRevisionDisposition
    reason: ManifestRevisionReason
    record_set_id: str
    record_set_revision: int
    reuse_existing_bytes: bool

    @property
    def requires_new_revision(self) -> bool:
        """Return whether the plan requires new immutable manifest bytes."""
        return self.disposition != "reuse_existing"


def _validated_manifest(manifest: AcademicResultManifest) -> AcademicResultManifest:
    try:
        return validate_manifest(manifest)
    except QuillanAcademicResultManifestValidationError as error:
        raise QuillanPublicationRevisionValidationError(
            "manifest must satisfy Quillan Academic Result Manifest v1."
        ) from error


def _validate_boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise QuillanPublicationRevisionValidationError(f"{field} must be a boolean.")
    return value


def _validate_revision(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise QuillanPublicationRevisionValidationError(
            f"{field} must be a positive non-Boolean integer."
        )
    return value


def _validated_allocated_revisions(
    allocated_revisions: Collection[int],
) -> tuple[int, ...]:
    if isinstance(allocated_revisions, (str, bytes)) or not isinstance(
        allocated_revisions, Collection
    ):
        raise QuillanPublicationRevisionValidationError(
            "allocated_revisions must be a collection of positive integers."
        )
    revisions = tuple(
        _validate_revision(value, "allocated_revisions[]")
        for value in allocated_revisions
    )
    if len(set(revisions)) != len(revisions):
        raise QuillanPublicationRevisionConflictError(
            "allocated_revisions must not contain duplicate revision identities."
        )
    return tuple(sorted(revisions))


def _series_identity(manifest: AcademicResultManifest) -> tuple[str, ...]:
    return (
        manifest.record_type,
        manifest.contract_version,
        manifest.producer_module_id,
        manifest.work.module_id,
        manifest.work.class_id,
        manifest.work.work_id,
        manifest.record_set.record_set_id,
    )


def _validate_production_identity(manifest: AcademicResultManifest) -> None:
    if manifest.record_set.record_set_id != QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID:
        raise QuillanPublicationRevisionValidationError(
            "production Quillan Academic Result manifests must use "
            f"record_set_id={QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID!r}."
        )


def _validate_same_series(
    previous: AcademicResultManifest,
    candidate: AcademicResultManifest,
) -> None:
    if _series_identity(previous) != _series_identity(candidate):
        raise QuillanPublicationRevisionValidationError(
            "manifest transition must remain within one Quillan publication series."
        )


def _publication_content_mapping(manifest: AcademicResultManifest) -> dict[str, Any]:
    content = manifest_to_mapping(_validated_manifest(manifest))
    content.pop("generated_at")
    record_set = dict(cast(dict[str, Any], content["record_set"]))
    record_set.pop("revision")
    content["record_set"] = record_set
    return content


def manifests_have_same_publication_content(
    previous: AcademicResultManifest,
    candidate: AcademicResultManifest,
) -> bool:
    """Compare complete publication content while ignoring time and revision only."""
    return _publication_content_mapping(previous) == _publication_content_mapping(
        candidate
    )


def next_record_set_revision(allocated_revisions: Collection[int]) -> int:
    """Return the normal next immutable producer revision, starting at one."""
    revisions = _validated_allocated_revisions(allocated_revisions)
    return 1 if not revisions else revisions[-1] + 1


def validate_manifest_revision_transition(
    previous: AcademicResultManifest,
    candidate: AcademicResultManifest,
) -> None:
    """Validate one explicit immutable same-series successor transition."""
    previous = _validated_manifest(previous)
    candidate = _validated_manifest(candidate)
    _validate_production_identity(previous)
    _validate_production_identity(candidate)
    _validate_same_series(previous, candidate)
    previous_revision = _validate_revision(
        previous.record_set.revision, "previous.record_set.revision"
    )
    candidate_revision = _validate_revision(
        candidate.record_set.revision, "candidate.record_set.revision"
    )
    if candidate_revision == previous_revision:
        raise QuillanPublicationRevisionConflictError(
            "one logical record-set revision cannot identify a second manifest state."
        )
    if candidate_revision < previous_revision:
        raise QuillanPublicationRevisionValidationError(
            "candidate revision must be greater than the predecessor revision."
        )


def _student_sources(
    manifest: AcademicResultManifest,
) -> dict[str, StudentSourceSnapshot]:
    return {
        student.student_id: student.source_snapshot for student in manifest.students
    }


def _native_source_changed(
    previous: AcademicResultManifest,
    candidate: AcademicResultManifest,
) -> bool:
    if previous.source_snapshot != candidate.source_snapshot:
        return True
    previous_students = _student_sources(previous)
    candidate_students = _student_sources(candidate)
    if previous_students.keys() != candidate_students.keys():
        return False
    return any(
        previous_students[student_id] != candidate_students[student_id]
        for student_id in previous_students
    )


def _validate_history(
    *,
    predecessor: AcademicResultManifest,
    historical_manifests: Collection[AcademicResultManifest],
) -> tuple[AcademicResultManifest, ...]:
    if isinstance(historical_manifests, (str, bytes)) or not isinstance(
        historical_manifests, Collection
    ):
        raise QuillanPublicationRevisionValidationError(
            "historical_manifests must be a collection of manifests."
        )
    validated: list[AcademicResultManifest] = []
    seen_revisions: set[int] = set()
    for historical in historical_manifests:
        historical = _validated_manifest(historical)
        _validate_production_identity(historical)
        _validate_same_series(predecessor, historical)
        revision = _validate_revision(
            historical.record_set.revision, "historical.record_set.revision"
        )
        if revision >= predecessor.record_set.revision:
            raise QuillanPublicationRevisionValidationError(
                "historical manifests must precede the current producer head."
            )
        if revision in seen_revisions:
            raise QuillanPublicationRevisionConflictError(
                "historical manifest revisions must be unique."
            )
        seen_revisions.add(revision)
        validated.append(historical)
    return tuple(validated)


def plan_manifest_revision(
    *,
    predecessor: AcademicResultManifest | None,
    candidate: AcademicResultManifest,
    allocated_revisions: Collection[int],
    historical_manifests: Collection[AcademicResultManifest] = (),
    republish_after_withdrawal: bool = False,
) -> ManifestRevisionPlan:
    """Plan exact replay, initial creation, or one immutable successor revision."""
    candidate = _validated_manifest(candidate)
    _validate_production_identity(candidate)
    revisions = _validated_allocated_revisions(allocated_revisions)
    republish = _validate_boolean(
        republish_after_withdrawal, "republish_after_withdrawal"
    )

    if predecessor is None:
        if republish:
            raise QuillanPublicationRevisionValidationError(
                "republication after withdrawal requires an existing predecessor."
            )
        if historical_manifests:
            raise QuillanPublicationRevisionValidationError(
                "historical manifests require an existing predecessor."
            )
        if revisions:
            raise QuillanPublicationRevisionConflictError(
                "initial creation is invalid when producer revisions are allocated."
            )
        return ManifestRevisionPlan(
            disposition="create_initial",
            reason="initial_publication",
            record_set_id=QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
            record_set_revision=1,
            reuse_existing_bytes=False,
        )

    predecessor = _validated_manifest(predecessor)
    _validate_production_identity(predecessor)
    _validate_same_series(predecessor, candidate)
    predecessor_revision = predecessor.record_set.revision
    if predecessor_revision not in revisions:
        raise QuillanPublicationRevisionConflictError(
            "allocated_revisions must include the predecessor revision."
        )
    if not revisions or revisions[-1] != predecessor_revision:
        raise QuillanPublicationRevisionConflictError(
            "predecessor must be the highest allocated producer revision."
        )

    history = _validate_history(
        predecessor=predecessor,
        historical_manifests=historical_manifests,
    )

    if republish:
        return ManifestRevisionPlan(
            disposition="create_successor",
            reason="republication_after_withdrawal",
            record_set_id=QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
            record_set_revision=next_record_set_revision(revisions),
            reuse_existing_bytes=False,
        )

    if manifests_have_same_publication_content(predecessor, candidate):
        return ManifestRevisionPlan(
            disposition="reuse_existing",
            reason="exact_replay",
            record_set_id=predecessor.record_set.record_set_id,
            record_set_revision=predecessor_revision,
            reuse_existing_bytes=True,
        )

    if any(
        manifests_have_same_publication_content(historical, candidate)
        for historical in history
    ):
        reason: ManifestRevisionReason = "historical_reversion"
    elif _native_source_changed(predecessor, candidate):
        reason = "native_source_changed"
    else:
        reason = "publication_projection_changed"

    return ManifestRevisionPlan(
        disposition="create_successor",
        reason=reason,
        record_set_id=QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
        record_set_revision=next_record_set_revision(revisions),
        reuse_existing_bytes=False,
    )

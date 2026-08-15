"""Consumer-neutral reader for Quillan Academic Result Manifest v1."""

from __future__ import annotations

import re
from typing import Literal, TypeAlias

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.academic_result_manifest import (
    AcademicResultManifest,
    EvidenceReference,
    OverallStandardRating,
    QuillanAcademicResultManifestDecodeError,
    QuillanAcademicResultManifestValidationError,
    ReviewUnit,
    SourceRecordSnapshot,
    StandardFeedback,
    StandardObservation,
    StudentResult,
    manifest_from_json_bytes,
    manifest_to_canonical_json_bytes,
    validate_manifest,
)

AcademicResultSourceName: TypeAlias = Literal["assignment", "submission", "review"]

_PDS2_EVIDENCE_ID = re.compile(r"^obs_[0-9a-f]{32}$")
_NATIVE_ID_LIMIT = 500


class QuillanAcademicResultReaderError(Exception):
    """Base failure for public Quillan manifest reading and exact lookup."""


class QuillanAcademicResultReaderValidationError(
    QuillanAcademicResultReaderError, ValueError
):
    """Reader input violates the public consumer-neutral contract."""


class QuillanAcademicResultReaderDecodeError(
    QuillanAcademicResultReaderValidationError
):
    """Immutable bytes are not an exact valid Quillan academic-result manifest."""


class QuillanAcademicResultReaderNotFoundError(
    QuillanAcademicResultReaderError, LookupError
):
    """An exact validated lookup is absent from the supplied manifest."""


def _validated_manifest(manifest: AcademicResultManifest) -> AcademicResultManifest:
    if type(manifest) is not AcademicResultManifest:
        raise QuillanAcademicResultReaderValidationError(
            "manifest must be an AcademicResultManifest."
        )
    try:
        return validate_manifest(manifest)
    except QuillanAcademicResultManifestValidationError as error:
        raise QuillanAcademicResultReaderValidationError(
            "Academic-result manifest model is invalid."
        ) from error


def _safe_student_id(value: object) -> str:
    if not isinstance(value, str):
        raise QuillanAcademicResultReaderValidationError(
            "student_id must be a safe identifier."
        )
    try:
        return validate_identifier(value, "student_id")
    except (IdentifierValidationError, TypeError, ValueError) as error:
        raise QuillanAcademicResultReaderValidationError(
            "student_id must be a safe identifier."
        ) from error


def _native_lookup_id(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > _NATIVE_ID_LIMIT
        or "\x00" in value
    ):
        raise QuillanAcademicResultReaderValidationError(
            f"{field_name} must be bounded nonempty native identifier text."
        )
    return value


def _evidence_id(value: object) -> str:
    if not isinstance(value, str) or _PDS2_EVIDENCE_ID.fullmatch(value) is None:
        raise QuillanAcademicResultReaderValidationError(
            "evidence_id must be an exact Quillan PDS2 evidence identifier."
        )
    return value


def read_academic_result_manifest(value: bytes) -> AcademicResultManifest:
    """Decode, validate, and require exact canonical Quillan manifest bytes."""
    if type(value) is not bytes:
        raise QuillanAcademicResultReaderValidationError(
            "Academic-result manifest input must be immutable bytes."
        )
    try:
        manifest = manifest_from_json_bytes(value)
    except QuillanAcademicResultManifestDecodeError as error:
        raise QuillanAcademicResultReaderDecodeError(
            "Academic-result manifest bytes are invalid."
        ) from error
    try:
        canonical = manifest_to_canonical_json_bytes(manifest)
    except QuillanAcademicResultManifestValidationError as error:
        raise QuillanAcademicResultReaderValidationError(
            "Academic-result manifest could not be validated canonically."
        ) from error
    if canonical != value:
        raise QuillanAcademicResultReaderValidationError(
            "Academic-result manifest bytes are not canonical."
        )
    return manifest


def validate_academic_result_manifest(
    manifest: AcademicResultManifest,
) -> AcademicResultManifest:
    """Validate one existing immutable manifest model without I/O."""
    return _validated_manifest(manifest)


def lookup_academic_result_student(
    manifest: AcademicResultManifest,
    student_id: str,
) -> StudentResult:
    """Return one exact represented student without fabricating absence state."""
    checked = _validated_manifest(manifest)
    target = _safe_student_id(student_id)
    for student in checked.students:
        if student.student_id == target:
            return student
    raise QuillanAcademicResultReaderNotFoundError(
        "Requested student is not represented in this manifest."
    )


def lookup_academic_result_source(
    manifest: AcademicResultManifest,
    source: AcademicResultSourceName,
    *,
    student_id: str | None = None,
) -> SourceRecordSnapshot:
    """Return one exact embedded source snapshot without opening native state."""
    checked = _validated_manifest(manifest)
    if source == "assignment":
        if student_id is not None:
            raise QuillanAcademicResultReaderValidationError(
                "Assignment source lookup must not include student_id."
            )
        return checked.source_snapshot
    if source not in {"submission", "review"}:
        raise QuillanAcademicResultReaderValidationError(
            "source must be assignment, submission, or review."
        )
    if student_id is None:
        raise QuillanAcademicResultReaderValidationError(
            "Student source lookup requires student_id."
        )
    student = lookup_academic_result_student(checked, student_id)
    if source == "submission":
        return student.source_snapshot.submission
    return student.source_snapshot.review


def lookup_academic_result_review_unit(
    manifest: AcademicResultManifest,
    student_id: str,
    unit_id: str,
) -> ReviewUnit:
    """Return one exact native review unit by its producer-owned unit_id."""
    student = lookup_academic_result_student(manifest, student_id)
    target = _native_lookup_id(unit_id, "unit_id")
    for unit in student.review.review_units:
        if unit.unit_id == target:
            return unit
    raise QuillanAcademicResultReaderNotFoundError(
        "Requested review unit is not represented for this student."
    )


def lookup_academic_result_observation(
    manifest: AcademicResultManifest,
    student_id: str,
    observation_id: str,
) -> StandardObservation:
    """Return one exact native standard observation without score inference."""
    student = lookup_academic_result_student(manifest, student_id)
    target = _native_lookup_id(observation_id, "observation_id")
    for unit in student.review.review_units:
        for observation in unit.standard_observations:
            if observation.observation_id == target:
                return observation
    raise QuillanAcademicResultReaderNotFoundError(
        "Requested observation is not represented for this student."
    )


def lookup_academic_result_overall_rating(
    manifest: AcademicResultManifest,
    student_id: str,
    standard_id: str,
) -> OverallStandardRating:
    """Return one exact teacher-entered overall Focus Standard rating."""
    student = lookup_academic_result_student(manifest, student_id)
    target = _native_lookup_id(standard_id, "standard_id")
    for rating in student.review.overall_standard_ratings:
        if rating.standard_id == target:
            return rating
    raise QuillanAcademicResultReaderNotFoundError(
        "Requested overall standard rating is not represented for this student."
    )


def lookup_academic_result_standard_feedback(
    manifest: AcademicResultManifest,
    student_id: str,
    standard_id: str,
) -> StandardFeedback:
    """Return one exact public standard-feedback composition record."""
    student = lookup_academic_result_student(manifest, student_id)
    target = _native_lookup_id(standard_id, "standard_id")
    for feedback in student.review.feedback.standard_feedback:
        if feedback.standard_id == target:
            return feedback
    raise QuillanAcademicResultReaderNotFoundError(
        "Requested standard feedback is not represented for this student."
    )


def lookup_academic_result_evidence_reference(
    manifest: AcademicResultManifest,
    student_id: str,
    evidence_id: str,
) -> EvidenceReference:
    """Return one exact public selected-evidence provenance reference."""
    student = lookup_academic_result_student(manifest, student_id)
    target = _evidence_id(evidence_id)
    provenance = student.submission.digital_provenance
    if provenance is not None:
        for reference in provenance.evidence_references:
            if reference.evidence_id == target:
                return reference
    raise QuillanAcademicResultReaderNotFoundError(
        "Requested evidence reference is not represented for this student."
    )


__all__ = (
    "AcademicResultManifest",
    "AcademicResultSourceName",
    "EvidenceReference",
    "OverallStandardRating",
    "QuillanAcademicResultReaderDecodeError",
    "QuillanAcademicResultReaderError",
    "QuillanAcademicResultReaderNotFoundError",
    "QuillanAcademicResultReaderValidationError",
    "ReviewUnit",
    "SourceRecordSnapshot",
    "StandardFeedback",
    "StandardObservation",
    "StudentResult",
    "lookup_academic_result_evidence_reference",
    "lookup_academic_result_observation",
    "lookup_academic_result_overall_rating",
    "lookup_academic_result_review_unit",
    "lookup_academic_result_source",
    "lookup_academic_result_standard_feedback",
    "lookup_academic_result_student",
    "read_academic_result_manifest",
    "validate_academic_result_manifest",
)

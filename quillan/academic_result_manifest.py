"""Pure immutable contract for Quillan Academic Result Manifest v1."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Final, Literal, NoReturn, TypeAlias, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.pds_contract import ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION

ACADEMIC_RESULT_MANIFEST_RECORD_TYPE: Final = "quillan_academic_result_manifest"
ACADEMIC_RESULT_MANIFEST_PRODUCER_MODULE_ID: Final = "quillan"
ASSIGNMENT_SOURCE_CONTRACT_VERSION: Final = "2"
SUBMISSION_SOURCE_CONTRACT_VERSION: Final = "1"
REVIEW_SOURCE_CONTRACT_VERSION: Final = "2"

ReviewState: TypeAlias = Literal[
    "not_started",
    "requirements_checked",
    "returned_without_full_review",
    "observations_in_progress",
    "observations_complete",
    "ratings_complete",
    "feedback_composed",
    "ready_for_export",
    "exported",
]
MinimumRequirementStatus: TypeAlias = Literal[
    "not_checked", "met", "unmet_continue_review", "returned_without_full_review"
]
TextDisposition: TypeAlias = Literal["absent", "withheld", "included"]
SubmissionEntryMethod: TypeAlias = Literal["pds2_response_pages", "plain_paper_manual"]

_REVIEW_STATES = frozenset(
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
_MINIMUM_STATUSES = frozenset(
    {"not_checked", "met", "unmet_continue_review", "returned_without_full_review"}
)
_SUBMISSION_STATES = frozenset(
    {"unreviewed", "in_progress", "needs_rescan", "reviewed"}
)
_TEXT_DISPOSITIONS = frozenset({"absent", "withheld", "included"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVIEW_UNIT_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_PDS2_TYPED_ID = re.compile(r"^(?P<prefix>iss|gen|art|pg|obs|rt)_[0-9a-f]{32}$")
_MAX_TEXT = 20_000


class QuillanAcademicResultManifestError(Exception):
    """Base error for the public manifest contract."""


class QuillanAcademicResultManifestValidationError(QuillanAcademicResultManifestError):
    """Raised when manifest data violates the v1 contract."""


class QuillanAcademicResultManifestDecodeError(QuillanAcademicResultManifestError):
    """Raised when bytes cannot be decoded as one strict v1 manifest."""


@dataclass(frozen=True, slots=True)
class RecordSet:
    record_set_id: str
    revision: int


@dataclass(frozen=True, slots=True)
class WorkReference:
    module_id: str
    class_id: str
    work_id: str


@dataclass(frozen=True, slots=True)
class SourceRecordSnapshot:
    relative_path: str
    sha256: str
    contract_version: str


@dataclass(frozen=True, slots=True)
class StudentSourceSnapshot:
    submission: SourceRecordSnapshot
    review: SourceRecordSnapshot


@dataclass(frozen=True, slots=True)
class ReviewUnitDefinition:
    type: str
    singular_label: str
    plural_label: str


@dataclass(frozen=True, slots=True)
class RatingScaleLevel:
    value: int
    label: str
    description: str


@dataclass(frozen=True, slots=True)
class RatingScale:
    scale_id: str
    levels: tuple[RatingScaleLevel, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "levels", tuple(self.levels))


@dataclass(frozen=True, slots=True)
class BasicRequirements:
    paragraphs_min: int | None
    paragraphs_max: int | None
    word_count_min: int | None
    word_count_max: int | None
    required_elements: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_elements", tuple(self.required_elements))


@dataclass(frozen=True, slots=True)
class MinimumRequirementPolicy:
    allow_return_without_full_review: bool


@dataclass(frozen=True, slots=True)
class AssignmentSnapshot:
    assignment_id: str
    title: str
    writing_type: str
    student_prompt: str
    standards_profile_id: str
    focus_standard_ids: tuple[str, ...]
    review_unit: ReviewUnitDefinition
    rating_scale: RatingScale
    basic_requirements: BasicRequirements
    minimum_requirement_policy: MinimumRequirementPolicy

    def __post_init__(self) -> None:
        object.__setattr__(self, "focus_standard_ids", tuple(self.focus_standard_ids))


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    page_id: str
    evidence_id: str
    observation_id: str
    route_id: str
    issuance_id: str
    generation_id: str
    artifact_id: str
    source_page_number: int
    source_scan_id: str
    source_sha256: str
    routed_evidence_sha256: str


@dataclass(frozen=True, slots=True)
class DigitalSubmissionProvenance:
    issuance_id: str
    generation_id: str
    artifact_id: str
    expected_page_ids: tuple[str, ...]
    evidence_references: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "expected_page_ids", tuple(self.expected_page_ids))
        object.__setattr__(self, "evidence_references", tuple(self.evidence_references))


@dataclass(frozen=True, slots=True)
class SubmissionSnapshot:
    class_id: str
    assignment_id: str
    student_id: str
    submission_state: str
    entry_method: SubmissionEntryMethod
    expected_pages: int | None
    digital_provenance: DigitalSubmissionProvenance | None


@dataclass(frozen=True, slots=True)
class PublishedText:
    disposition: TextDisposition
    text: str | None


@dataclass(frozen=True, slots=True)
class MinimumRequirementOutcome:
    status: MinimumRequirementStatus
    returned_without_full_review: bool
    updated_at: datetime | None
    teacher_note: PublishedText


@dataclass(frozen=True, slots=True)
class StandardObservation:
    observation_id: str
    standard_id: str
    applicable: bool
    evidence_present: bool | None
    rating: int | None
    rationale: PublishedText
    include_in_feedback: bool
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewUnit:
    unit_id: str
    sequence: int
    label: str
    unit_type: str
    standard_observations: tuple[StandardObservation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "standard_observations", tuple(self.standard_observations)
        )


@dataclass(frozen=True, slots=True)
class OverallStandardRating:
    standard_id: str
    rating: int
    rationale: PublishedText
    include_in_feedback: bool
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class FeedbackComment:
    feedback_comment_id: str
    text: PublishedText
    include_in_feedback: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StandardFeedback:
    standard_id: str
    include_overall_rating: bool
    include_overall_rationale: bool
    included_observation_ids: tuple[str, ...]
    comments: tuple[FeedbackComment, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "included_observation_ids", tuple(self.included_observation_ids)
        )
        object.__setattr__(self, "comments", tuple(self.comments))


@dataclass(frozen=True, slots=True)
class FeedbackComposition:
    include_review_unit_observations: bool
    include_overall_standard_ratings: bool
    standard_feedback: tuple[StandardFeedback, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "standard_feedback", tuple(self.standard_feedback))


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    class_id: str
    assignment_id: str
    student_id: str
    review_state: ReviewState
    minimum_requirement_outcome: MinimumRequirementOutcome
    review_units: tuple[ReviewUnit, ...]
    overall_standard_ratings: tuple[OverallStandardRating, ...]
    feedback: FeedbackComposition

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_units", tuple(self.review_units))
        object.__setattr__(
            self, "overall_standard_ratings", tuple(self.overall_standard_ratings)
        )


@dataclass(frozen=True, slots=True)
class StudentResult:
    student_id: str
    source_snapshot: StudentSourceSnapshot
    submission: SubmissionSnapshot
    review: ReviewSnapshot


@dataclass(frozen=True, slots=True)
class AcademicResultManifest:
    record_type: str
    contract_version: str
    producer_module_id: str
    generated_at: datetime
    record_set: RecordSet
    work: WorkReference
    source_snapshot: SourceRecordSnapshot
    assignment: AssignmentSnapshot
    students: tuple[StudentResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "students", tuple(self.students))


def _fail(message: str) -> NoReturn:
    raise QuillanAcademicResultManifestValidationError(message)


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str):
        _fail(f"{field} must be a safe identifier.")
    try:
        return validate_identifier(value, field)
    except (IdentifierValidationError, TypeError, ValueError) as error:
        raise QuillanAcademicResultManifestValidationError(
            f"{field} must be a safe identifier."
        ) from error


def _native_text_id(value: object, field: str) -> str:
    """Validate one bounded native ID whose producer contract is nonempty text."""
    return _text(value, field, limit=500)


def _review_unit_type(value: object, field: str) -> str:
    if not isinstance(value, str) or _REVIEW_UNIT_TYPE.fullmatch(value.strip()) is None:
        _fail(f"{field} must match the native assignment review-unit type grammar.")
    return value


def _pds2_typed_id(value: object, prefix: str, field: str) -> str:
    if (
        not isinstance(value, str)
        or (match := _PDS2_TYPED_ID.fullmatch(value)) is None
        or match.group("prefix") != prefix
    ):
        _fail(
            f"{field} must be {prefix}_ followed by 32 lowercase hexadecimal characters."
        )
    return value


def _text(value: object, field: str, *, limit: int = _MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        _fail(f"{field} must be nonempty text of at most {limit} characters.")
    if "\x00" in value:
        _fail(f"{field} contains a prohibited null character.")
    return value


def _integer(value: object, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{field} must be an integer.")
    if minimum is not None and value < minimum:
        _fail(f"{field} must be at least {minimum}.")
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{field} must be a boolean.")
    return value


def _timestamp(value: object, field: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        _fail(f"{field} must be a timezone-aware datetime.")
    return value


def _timestamp_json(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc).replace(microsecond=value.microsecond)
    return normalized.isoformat().replace("+00:00", "Z")


def _timestamp_from_json(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        _fail(f"{field} must be a timezone-aware ISO 8601 string.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise QuillanAcademicResultManifestValidationError(
            f"{field} must be a timezone-aware ISO 8601 string."
        ) from error
    return _timestamp(parsed, field)


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail(f"{field} must be an exact lowercase SHA-256 digest.")
    return value


def _source_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        _fail(f"{field} must be a canonical relative POSIX path.")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        _fail(f"{field} must not be absolute or drive-qualified.")
    if value != posix.as_posix() or any(
        part in {"", ".", ".."} for part in posix.parts
    ):
        _fail(f"{field} must not contain empty, dot, or traversal components.")
    return value


def _published_text(value: PublishedText, field: str) -> None:
    if value.disposition not in _TEXT_DISPOSITIONS:
        _fail(f"{field}.disposition is invalid.")
    if value.disposition == "included":
        _text(value.text, f"{field}.text")
    elif value.text is not None:
        _fail(f"{field}.text must be null unless disposition is included.")


def _validate_source(value: SourceRecordSnapshot, field: str, version: str) -> None:
    _source_path(value.relative_path, f"{field}.relative_path")
    _digest(value.sha256, f"{field}.sha256")
    if value.contract_version != version:
        _fail(f"{field}.contract_version must be {version!r}.")


def _validate_manifest(manifest: AcademicResultManifest) -> AcademicResultManifest:
    if not isinstance(manifest, AcademicResultManifest):
        _fail("manifest must be an AcademicResultManifest.")
    if manifest.record_type != ACADEMIC_RESULT_MANIFEST_RECORD_TYPE:
        _fail("record_type is invalid.")
    if manifest.contract_version != ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION:
        _fail("contract_version is invalid.")
    if manifest.producer_module_id != ACADEMIC_RESULT_MANIFEST_PRODUCER_MODULE_ID:
        _fail("producer_module_id must be 'quillan'.")
    _timestamp(manifest.generated_at, "generated_at")
    _identifier(manifest.record_set.record_set_id, "record_set.record_set_id")
    _integer(manifest.record_set.revision, "record_set.revision", minimum=1)
    if manifest.work.module_id != "quillan":
        _fail("work.module_id must be 'quillan'.")
    _identifier(manifest.work.class_id, "work.class_id")
    _identifier(manifest.work.work_id, "work.work_id")
    _validate_source(manifest.source_snapshot, "source_snapshot.assignment", "2")
    if manifest.source_snapshot.relative_path != "assignment.json":
        _fail("assignment source relative_path must be 'assignment.json'.")
    assignment = manifest.assignment
    if assignment.assignment_id != manifest.work.work_id:
        _fail("assignment.assignment_id must equal work.work_id.")
    _identifier(assignment.assignment_id, "assignment.assignment_id")
    _text(assignment.title, "assignment.title", limit=500)
    _text(assignment.writing_type, "assignment.writing_type", limit=200)
    _text(assignment.student_prompt, "assignment.student_prompt")
    _native_text_id(assignment.standards_profile_id, "assignment.standards_profile_id")
    if not assignment.focus_standard_ids:
        _fail("assignment.focus_standard_ids must not be empty.")
    if len(set(assignment.focus_standard_ids)) != len(assignment.focus_standard_ids):
        _fail("assignment.focus_standard_ids contains duplicates.")
    for item in assignment.focus_standard_ids:
        _native_text_id(item, "assignment.focus_standard_ids[]")
    _review_unit_type(assignment.review_unit.type, "assignment.review_unit.type")
    _text(
        assignment.review_unit.singular_label,
        "assignment.review_unit.singular_label",
        limit=200,
    )
    _text(
        assignment.review_unit.plural_label,
        "assignment.review_unit.plural_label",
        limit=200,
    )
    _native_text_id(
        assignment.rating_scale.scale_id, "assignment.rating_scale.scale_id"
    )
    if not assignment.rating_scale.levels:
        _fail("assignment.rating_scale.levels must not be empty.")
    scale_values: set[int] = set()
    for level in assignment.rating_scale.levels:
        rating = _integer(level.value, "assignment.rating_scale.levels[].value")
        _text(level.label, "assignment.rating_scale.levels[].label", limit=200)
        _text(
            level.description,
            "assignment.rating_scale.levels[].description",
            limit=2000,
        )
        if rating in scale_values:
            _fail("assignment rating-scale values must be unique.")
        scale_values.add(rating)
    req = assignment.basic_requirements
    for name in (
        "paragraphs_min",
        "paragraphs_max",
        "word_count_min",
        "word_count_max",
    ):
        item = getattr(req, name)
        if item is not None:
            _integer(item, f"assignment.basic_requirements.{name}", minimum=0)
    if (
        req.paragraphs_min is not None
        and req.paragraphs_max is not None
        and req.paragraphs_min > req.paragraphs_max
    ):
        _fail("paragraphs_min must not exceed paragraphs_max.")
    if (
        req.word_count_min is not None
        and req.word_count_max is not None
        and req.word_count_min > req.word_count_max
    ):
        _fail("word_count_min must not exceed word_count_max.")
    for item in req.required_elements:
        _text(item, "assignment.basic_requirements.required_elements[]", limit=500)
    _boolean(
        assignment.minimum_requirement_policy.allow_return_without_full_review,
        "assignment.minimum_requirement_policy.allow_return_without_full_review",
    )
    student_ids = [student.student_id for student in manifest.students]
    if student_ids != sorted(student_ids) or len(set(student_ids)) != len(student_ids):
        _fail("students must be unique and sorted by student_id.")
    for student in manifest.students:
        _validate_student(student, manifest, scale_values)
    return manifest


def _validate_student(
    student: StudentResult, manifest: AcademicResultManifest, scale: set[int]
) -> None:
    student_id = _identifier(student.student_id, "students[].student_id")
    base = f"submissions/{student_id}"
    _validate_source(
        student.source_snapshot.submission, "students[].source_snapshot.submission", "1"
    )
    _validate_source(
        student.source_snapshot.review, "students[].source_snapshot.review", "2"
    )
    if student.source_snapshot.submission.relative_path != f"{base}/submission.json":
        _fail("student submission source path disagrees with student_id.")
    if student.source_snapshot.review.relative_path != f"{base}/review.json":
        _fail("student review source path disagrees with student_id.")
    submission = student.submission
    expected_identity = (
        manifest.work.class_id,
        manifest.work.work_id,
        student.student_id,
    )
    if (
        submission.class_id,
        submission.assignment_id,
        submission.student_id,
    ) != expected_identity:
        _fail("submission identity disagrees with work or student identity.")
    if submission.submission_state not in _SUBMISSION_STATES:
        _fail("submission.submission_state is invalid.")
    if submission.entry_method == "plain_paper_manual":
        if (
            submission.expected_pages is not None
            or submission.digital_provenance is not None
        ):
            _fail(
                "plain-paper submissions cannot contain digital provenance or expected pages."
            )
    elif submission.entry_method == "pds2_response_pages":
        expected_pages = _integer(
            submission.expected_pages, "submission.expected_pages", minimum=1
        )
        if submission.digital_provenance is None:
            _fail("PDS2 submissions require digital_provenance.")
        _validate_digital(submission.digital_provenance)
        if expected_pages != len(submission.digital_provenance.expected_page_ids):
            _fail("submission expected_pages disagrees with expected_page_ids.")
    else:
        _fail("submission.entry_method is invalid.")
    review = student.review
    if (review.class_id, review.assignment_id, review.student_id) != expected_identity:
        _fail("review identity disagrees with work or student identity.")
    if review.review_state not in _REVIEW_STATES:
        _fail("review.review_state is invalid.")
    outcome = review.minimum_requirement_outcome
    if outcome.status not in _MINIMUM_STATUSES:
        _fail("minimum_requirement_outcome.status is invalid.")
    _boolean(
        outcome.returned_without_full_review,
        "minimum_requirement_outcome.returned_without_full_review",
    )
    if outcome.status == "not_checked":
        if outcome.updated_at is not None:
            _fail("not_checked outcome updated_at must be null.")
    elif outcome.updated_at is None:
        _fail("checked minimum-requirement outcome requires updated_at.")
    else:
        _timestamp(outcome.updated_at, "minimum_requirement_outcome.updated_at")
    returned = outcome.status == "returned_without_full_review"
    if returned != outcome.returned_without_full_review:
        _fail("minimum-requirement return status and flag disagree.")
    if outcome.returned_without_full_review != (
        review.review_state == "returned_without_full_review"
    ):
        _fail("returned-without-full-review outcome and review state disagree.")
    _published_text(outcome.teacher_note, "minimum_requirement_outcome.teacher_note")
    unit_ids: set[str] = set()
    sequences: set[int] = set()
    observation_ids: set[str] = set()
    observation_standard_ids: dict[str, str] = {}
    previous = 0
    focus = set(manifest.assignment.focus_standard_ids)
    for unit in review.review_units:
        uid = _native_text_id(unit.unit_id, "review_units[].unit_id")
        sequence = _integer(unit.sequence, "review_units[].sequence", minimum=1)
        if uid in unit_ids or sequence in sequences:
            _fail("review-unit IDs and sequences must be unique.")
        if sequence <= previous:
            _fail("review_units must be ordered by increasing sequence.")
        previous = sequence
        unit_ids.add(uid)
        sequences.add(sequence)
        _text(unit.label, "review_units[].label", limit=500)
        _native_text_id(unit.unit_type, "review_units[].unit_type")
        if unit.unit_type != manifest.assignment.review_unit.type.strip():
            _fail("review-unit unit_type must equal assignment.review_unit.type.")
        unit_standards: set[str] = set()
        for observation in unit.standard_observations:
            oid = _native_text_id(
                observation.observation_id, "standard_observations[].observation_id"
            )
            sid = _native_text_id(
                observation.standard_id, "standard_observations[].standard_id"
            )
            if oid in observation_ids:
                _fail("observation IDs must be unique in one review.")
            if sid in unit_standards:
                _fail("a review unit cannot repeat a Focus Standard.")
            if sid not in focus:
                _fail("observation standard is not an assignment Focus Standard.")
            observation_ids.add(oid)
            observation_standard_ids[oid] = sid
            unit_standards.add(sid)
            _boolean(observation.applicable, "standard_observations[].applicable")
            if not observation.applicable:
                if (
                    observation.evidence_present is not None
                    or observation.rating is not None
                ):
                    _fail(
                        "non-applicable observations require null evidence_present and rating."
                    )
            else:
                _boolean(
                    observation.evidence_present,
                    "standard_observations[].evidence_present",
                )
                if observation.rating is not None:
                    native_rating = _integer(
                        observation.rating, "standard_observations[].rating"
                    )
                    if native_rating not in scale:
                        _fail(
                            "observation rating is absent from the assignment rating scale."
                        )
            _published_text(observation.rationale, "standard_observations[].rationale")
            _boolean(
                observation.include_in_feedback,
                "standard_observations[].include_in_feedback",
            )
            _timestamp(observation.updated_at, "standard_observations[].updated_at")
    overall_ids: set[str] = set()
    for rating in review.overall_standard_ratings:
        sid = _native_text_id(
            rating.standard_id, "overall_standard_ratings[].standard_id"
        )
        if sid in overall_ids:
            _fail("overall ratings cannot repeat a Focus Standard.")
        if sid not in focus:
            _fail("overall rating standard is not an assignment Focus Standard.")
        native_rating = _integer(rating.rating, "overall_standard_ratings[].rating")
        if native_rating not in scale:
            _fail("overall rating is absent from the assignment rating scale.")
        overall_ids.add(sid)
        _published_text(rating.rationale, "overall_standard_ratings[].rationale")
        _boolean(
            rating.include_in_feedback, "overall_standard_ratings[].include_in_feedback"
        )
        _timestamp(rating.updated_at, "overall_standard_ratings[].updated_at")
    feedback = review.feedback
    _boolean(
        feedback.include_review_unit_observations,
        "feedback.include_review_unit_observations",
    )
    _boolean(
        feedback.include_overall_standard_ratings,
        "feedback.include_overall_standard_ratings",
    )
    seen_feedback: set[str] = set()
    seen_comments: set[str] = set()
    for item in feedback.standard_feedback:
        sid = _native_text_id(
            item.standard_id, "feedback.standard_feedback[].standard_id"
        )
        if sid not in focus or sid in seen_feedback:
            _fail(
                "standard feedback references an invalid or duplicate Focus Standard."
            )
        seen_feedback.add(sid)
        _boolean(
            item.include_overall_rating, "standard_feedback[].include_overall_rating"
        )
        _boolean(
            item.include_overall_rationale,
            "standard_feedback[].include_overall_rationale",
        )
        for reference in item.included_observation_ids:
            _native_text_id(reference, "standard_feedback[].included_observation_ids[]")
        if len(set(item.included_observation_ids)) != len(
            item.included_observation_ids
        ):
            _fail("included observation IDs must be unique.")
        if any(ref not in observation_ids for ref in item.included_observation_ids):
            _fail("standard feedback references an unknown observation.")
        if any(
            observation_standard_ids[ref] != sid
            for ref in item.included_observation_ids
        ):
            _fail(
                "standard feedback can include only observations for its standard_id."
            )
        for comment in item.comments:
            cid = _native_text_id(
                comment.feedback_comment_id, "feedback.comments[].feedback_comment_id"
            )
            if cid in seen_comments:
                _fail("feedback comment IDs must be unique.")
            seen_comments.add(cid)
            _published_text(comment.text, "feedback.comments[].text")
            _boolean(
                comment.include_in_feedback, "feedback.comments[].include_in_feedback"
            )
            _timestamp(comment.created_at, "feedback.comments[].created_at")


def validate_manifest(manifest: AcademicResultManifest) -> AcademicResultManifest:
    """Validate all intrinsic and cross-record v1 invariants."""
    try:
        return _validate_manifest(manifest)
    except QuillanAcademicResultManifestValidationError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise QuillanAcademicResultManifestValidationError(
            "manifest model contains an invalid field value."
        ) from error


def _validate_digital(value: DigitalSubmissionProvenance) -> None:
    _pds2_typed_id(value.issuance_id, "iss", "digital_provenance.issuance_id")
    _pds2_typed_id(value.generation_id, "gen", "digital_provenance.generation_id")
    _pds2_typed_id(value.artifact_id, "art", "digital_provenance.artifact_id")
    if not value.expected_page_ids or len(set(value.expected_page_ids)) != len(
        value.expected_page_ids
    ):
        _fail("digital_provenance.expected_page_ids must be nonempty and unique.")
    for page_id in value.expected_page_ids:
        _pds2_typed_id(page_id, "pg", "digital_provenance.expected_page_ids[]")
    seen: set[str] = set()
    retained_page_ids: dict[tuple[str, int], str] = {}
    retained_scan_digests: dict[str, str] = {}
    for ref in value.evidence_references:
        _pds2_typed_id(ref.page_id, "pg", "evidence_references[].page_id")
        _pds2_typed_id(ref.evidence_id, "obs", "evidence_references[].evidence_id")
        _pds2_typed_id(
            ref.observation_id, "obs", "evidence_references[].observation_id"
        )
        _pds2_typed_id(ref.route_id, "rt", "evidence_references[].route_id")
        _pds2_typed_id(ref.issuance_id, "iss", "evidence_references[].issuance_id")
        _pds2_typed_id(ref.generation_id, "gen", "evidence_references[].generation_id")
        _pds2_typed_id(ref.artifact_id, "art", "evidence_references[].artifact_id")
        if ref.evidence_id != ref.observation_id:
            _fail("PDS2 evidence_id must equal observation_id.")
        if ref.evidence_id in seen:
            _fail("digital evidence references must have unique evidence_id values.")
        seen.add(ref.evidence_id)
        if ref.page_id not in value.expected_page_ids:
            _fail("digital evidence page_id is not an expected page.")
        if (ref.issuance_id, ref.generation_id, ref.artifact_id) != (
            value.issuance_id,
            value.generation_id,
            value.artifact_id,
        ):
            _fail("digital evidence identity disagrees with its provenance envelope.")
        _integer(
            ref.source_page_number,
            "evidence_references[].source_page_number",
            minimum=1,
        )
        _identifier(ref.source_scan_id, "evidence_references[].source_scan_id")
        _digest(ref.source_sha256, "evidence_references[].source_sha256")
        retained_page_key = (ref.source_scan_id, ref.source_page_number)
        previous_page_id = retained_page_ids.setdefault(retained_page_key, ref.page_id)
        if previous_page_id != ref.page_id:
            _fail("one retained source page cannot represent contradictory page IDs.")
        previous_source_digest = retained_scan_digests.setdefault(
            ref.source_scan_id, ref.source_sha256
        )
        if previous_source_digest != ref.source_sha256:
            _fail(
                "one retained source scan cannot assert contradictory SHA-256 values."
            )
        _digest(
            ref.routed_evidence_sha256, "evidence_references[].routed_evidence_sha256"
        )


# Exact JSON field sets. All optional semantics use required keys with null values.
_KEYS: Final[dict[str, frozenset[str]]] = {
    "manifest": frozenset(
        {
            "record_type",
            "contract_version",
            "producer_module_id",
            "generated_at",
            "record_set",
            "work",
            "source_snapshot",
            "assignment",
            "students",
        }
    ),
    "record_set": frozenset({"record_set_id", "revision"}),
    "work": frozenset({"module_id", "class_id", "work_id"}),
    "source": frozenset({"relative_path", "sha256", "contract_version"}),
    "student_sources": frozenset({"submission", "review"}),
    "assignment": frozenset(
        {
            "assignment_id",
            "title",
            "writing_type",
            "student_prompt",
            "standards_profile_id",
            "focus_standard_ids",
            "review_unit",
            "rating_scale",
            "basic_requirements",
            "minimum_requirement_policy",
        }
    ),
    "review_unit_definition": frozenset({"type", "singular_label", "plural_label"}),
    "rating_scale": frozenset({"scale_id", "levels"}),
    "rating_level": frozenset({"value", "label", "description"}),
    "basic_requirements": frozenset(
        {
            "paragraphs_min",
            "paragraphs_max",
            "word_count_min",
            "word_count_max",
            "required_elements",
        }
    ),
    "minimum_policy": frozenset({"allow_return_without_full_review"}),
    "student": frozenset({"student_id", "source_snapshot", "submission", "review"}),
    "submission": frozenset(
        {
            "class_id",
            "assignment_id",
            "student_id",
            "submission_state",
            "entry_method",
            "expected_pages",
            "digital_provenance",
        }
    ),
    "digital": frozenset(
        {
            "issuance_id",
            "generation_id",
            "artifact_id",
            "expected_page_ids",
            "evidence_references",
        }
    ),
    "evidence": frozenset(
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
    ),
    "published_text": frozenset({"disposition", "text"}),
    "review": frozenset(
        {
            "class_id",
            "assignment_id",
            "student_id",
            "review_state",
            "minimum_requirement_outcome",
            "review_units",
            "overall_standard_ratings",
            "feedback",
        }
    ),
    "outcome": frozenset(
        {"status", "returned_without_full_review", "updated_at", "teacher_note"}
    ),
    "review_unit": frozenset(
        {"unit_id", "sequence", "label", "unit_type", "standard_observations"}
    ),
    "observation": frozenset(
        {
            "observation_id",
            "standard_id",
            "applicable",
            "evidence_present",
            "rating",
            "rationale",
            "include_in_feedback",
            "updated_at",
        }
    ),
    "overall": frozenset(
        {"standard_id", "rating", "rationale", "include_in_feedback", "updated_at"}
    ),
    "feedback": frozenset(
        {
            "include_review_unit_observations",
            "include_overall_standard_ratings",
            "standard_feedback",
        }
    ),
    "standard_feedback": frozenset(
        {
            "standard_id",
            "include_overall_rating",
            "include_overall_rationale",
            "included_observation_ids",
            "comments",
        }
    ),
    "comment": frozenset(
        {"feedback_comment_id", "text", "include_in_feedback", "created_at"}
    ),
}


def _mapping(value: object, kind: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{kind} must be an object.")
    actual = set(value)
    if actual != _KEYS[kind]:
        _fail(
            f"{kind} has an invalid key set; missing={sorted(_KEYS[kind] - actual)!r}, unknown={sorted(actual - _KEYS[kind])!r}."
        )
    return cast(Mapping[str, Any], value)


def _array(value: object, field: str) -> tuple[Any, ...]:
    if not isinstance(value, list):
        _fail(f"{field} must be a JSON array.")
    return tuple(value)


def _source_from(value: object) -> SourceRecordSnapshot:
    m = _mapping(value, "source")
    return SourceRecordSnapshot(
        cast(str, m["relative_path"]),
        cast(str, m["sha256"]),
        cast(str, m["contract_version"]),
    )


def _pt_from(value: object) -> PublishedText:
    m = _mapping(value, "published_text")
    return PublishedText(
        cast(TextDisposition, m["disposition"]), cast(str | None, m["text"])
    )


def manifest_from_mapping(value: object) -> AcademicResultManifest:
    """Construct and validate a manifest from an exact JSON-native mapping."""
    try:
        m = _mapping(value, "manifest")
        rs = _mapping(m["record_set"], "record_set")
        w = _mapping(m["work"], "work")
        a = _mapping(m["assignment"], "assignment")
        rud = _mapping(a["review_unit"], "review_unit_definition")
        scale = _mapping(a["rating_scale"], "rating_scale")
        br = _mapping(a["basic_requirements"], "basic_requirements")
        pol = _mapping(a["minimum_requirement_policy"], "minimum_policy")
        assignment = AssignmentSnapshot(
            cast(str, a["assignment_id"]),
            cast(str, a["title"]),
            cast(str, a["writing_type"]),
            cast(str, a["student_prompt"]),
            cast(str, a["standards_profile_id"]),
            tuple(
                cast(str, x)
                for x in _array(a["focus_standard_ids"], "focus_standard_ids")
            ),
            ReviewUnitDefinition(
                cast(str, rud["type"]),
                cast(str, rud["singular_label"]),
                cast(str, rud["plural_label"]),
            ),
            RatingScale(
                cast(str, scale["scale_id"]),
                tuple(
                    RatingScaleLevel(
                        cast(int, (lm := _mapping(x, "rating_level"))["value"]),
                        cast(str, lm["label"]),
                        cast(str, lm["description"]),
                    )
                    for x in _array(scale["levels"], "levels")
                ),
            ),
            BasicRequirements(
                cast(int | None, br["paragraphs_min"]),
                cast(int | None, br["paragraphs_max"]),
                cast(int | None, br["word_count_min"]),
                cast(int | None, br["word_count_max"]),
                tuple(
                    cast(str, x)
                    for x in _array(br["required_elements"], "required_elements")
                ),
            ),
            MinimumRequirementPolicy(
                cast(bool, pol["allow_return_without_full_review"])
            ),
        )
        students = tuple(_student_from(x) for x in _array(m["students"], "students"))
        manifest = AcademicResultManifest(
            cast(str, m["record_type"]),
            cast(str, m["contract_version"]),
            cast(str, m["producer_module_id"]),
            _timestamp_from_json(m["generated_at"], "generated_at"),
            RecordSet(cast(str, rs["record_set_id"]), cast(int, rs["revision"])),
            WorkReference(
                cast(str, w["module_id"]),
                cast(str, w["class_id"]),
                cast(str, w["work_id"]),
            ),
            _source_from(m["source_snapshot"]),
            assignment,
            students,
        )
        return validate_manifest(manifest)
    except QuillanAcademicResultManifestValidationError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise QuillanAcademicResultManifestValidationError(
            "manifest mapping contains an invalid field value."
        ) from error


def _student_from(value: object) -> StudentResult:
    m = _mapping(value, "student")
    ss = _mapping(m["source_snapshot"], "student_sources")
    sub = _mapping(m["submission"], "submission")
    digital = None
    if sub["digital_provenance"] is not None:
        d = _mapping(sub["digital_provenance"], "digital")
        refs = []
        for x in _array(d["evidence_references"], "evidence_references"):
            e = _mapping(x, "evidence")
            refs.append(
                EvidenceReference(
                    cast(str, e["page_id"]),
                    cast(str, e["evidence_id"]),
                    cast(str, e["observation_id"]),
                    cast(str, e["route_id"]),
                    cast(str, e["issuance_id"]),
                    cast(str, e["generation_id"]),
                    cast(str, e["artifact_id"]),
                    cast(int, e["source_page_number"]),
                    cast(str, e["source_scan_id"]),
                    cast(str, e["source_sha256"]),
                    cast(str, e["routed_evidence_sha256"]),
                )
            )
        digital = DigitalSubmissionProvenance(
            cast(str, d["issuance_id"]),
            cast(str, d["generation_id"]),
            cast(str, d["artifact_id"]),
            tuple(
                cast(str, x)
                for x in _array(d["expected_page_ids"], "expected_page_ids")
            ),
            tuple(refs),
        )
    submission = SubmissionSnapshot(
        cast(str, sub["class_id"]),
        cast(str, sub["assignment_id"]),
        cast(str, sub["student_id"]),
        cast(str, sub["submission_state"]),
        cast(SubmissionEntryMethod, sub["entry_method"]),
        cast(int | None, sub["expected_pages"]),
        digital,
    )
    r = _mapping(m["review"], "review")
    o = _mapping(r["minimum_requirement_outcome"], "outcome")
    outcome = MinimumRequirementOutcome(
        cast(MinimumRequirementStatus, o["status"]),
        cast(bool, o["returned_without_full_review"]),
        None
        if o["updated_at"] is None
        else _timestamp_from_json(o["updated_at"], "updated_at"),
        _pt_from(o["teacher_note"]),
    )
    units = []
    for x in _array(r["review_units"], "review_units"):
        u = _mapping(x, "review_unit")
        observations = []
        for y in _array(u["standard_observations"], "standard_observations"):
            z = _mapping(y, "observation")
            observations.append(
                StandardObservation(
                    cast(str, z["observation_id"]),
                    cast(str, z["standard_id"]),
                    cast(bool, z["applicable"]),
                    cast(bool | None, z["evidence_present"]),
                    cast(int | None, z["rating"]),
                    _pt_from(z["rationale"]),
                    cast(bool, z["include_in_feedback"]),
                    _timestamp_from_json(z["updated_at"], "updated_at"),
                )
            )
        units.append(
            ReviewUnit(
                cast(str, u["unit_id"]),
                cast(int, u["sequence"]),
                cast(str, u["label"]),
                cast(str, u["unit_type"]),
                tuple(observations),
            )
        )
    overall = []
    for x in _array(r["overall_standard_ratings"], "overall_standard_ratings"):
        z = _mapping(x, "overall")
        overall.append(
            OverallStandardRating(
                cast(str, z["standard_id"]),
                cast(int, z["rating"]),
                _pt_from(z["rationale"]),
                cast(bool, z["include_in_feedback"]),
                _timestamp_from_json(z["updated_at"], "updated_at"),
            )
        )
    f = _mapping(r["feedback"], "feedback")
    standards = []
    for x in _array(f["standard_feedback"], "standard_feedback"):
        z = _mapping(x, "standard_feedback")
        comments = []
        for y in _array(z["comments"], "comments"):
            c = _mapping(y, "comment")
            comments.append(
                FeedbackComment(
                    cast(str, c["feedback_comment_id"]),
                    _pt_from(c["text"]),
                    cast(bool, c["include_in_feedback"]),
                    _timestamp_from_json(c["created_at"], "created_at"),
                )
            )
        standards.append(
            StandardFeedback(
                cast(str, z["standard_id"]),
                cast(bool, z["include_overall_rating"]),
                cast(bool, z["include_overall_rationale"]),
                tuple(
                    cast(str, q)
                    for q in _array(
                        z["included_observation_ids"], "included_observation_ids"
                    )
                ),
                tuple(comments),
            )
        )
    feedback = FeedbackComposition(
        cast(bool, f["include_review_unit_observations"]),
        cast(bool, f["include_overall_standard_ratings"]),
        tuple(standards),
    )
    review = ReviewSnapshot(
        cast(str, r["class_id"]),
        cast(str, r["assignment_id"]),
        cast(str, r["student_id"]),
        cast(ReviewState, r["review_state"]),
        outcome,
        tuple(units),
        tuple(overall),
        feedback,
    )
    return StudentResult(
        cast(str, m["student_id"]),
        StudentSourceSnapshot(
            _source_from(ss["submission"]), _source_from(ss["review"])
        ),
        submission,
        review,
    )


def _source_to(v: SourceRecordSnapshot) -> dict[str, Any]:
    return {
        "relative_path": v.relative_path,
        "sha256": v.sha256,
        "contract_version": v.contract_version,
    }


def _pt_to(v: PublishedText) -> dict[str, Any]:
    return {"disposition": v.disposition, "text": v.text}


def manifest_to_mapping(manifest: AcademicResultManifest) -> dict[str, Any]:
    """Return the exact JSON-native v1 mapping after validation."""
    validate_manifest(manifest)
    a = manifest.assignment
    return {
        "record_type": manifest.record_type,
        "contract_version": manifest.contract_version,
        "producer_module_id": manifest.producer_module_id,
        "generated_at": _timestamp_json(manifest.generated_at),
        "record_set": {
            "record_set_id": manifest.record_set.record_set_id,
            "revision": manifest.record_set.revision,
        },
        "work": {
            "module_id": manifest.work.module_id,
            "class_id": manifest.work.class_id,
            "work_id": manifest.work.work_id,
        },
        "source_snapshot": _source_to(manifest.source_snapshot),
        "assignment": {
            "assignment_id": a.assignment_id,
            "title": a.title,
            "writing_type": a.writing_type,
            "student_prompt": a.student_prompt,
            "standards_profile_id": a.standards_profile_id,
            "focus_standard_ids": list(a.focus_standard_ids),
            "review_unit": {
                "type": a.review_unit.type,
                "singular_label": a.review_unit.singular_label,
                "plural_label": a.review_unit.plural_label,
            },
            "rating_scale": {
                "scale_id": a.rating_scale.scale_id,
                "levels": [
                    {"value": x.value, "label": x.label, "description": x.description}
                    for x in a.rating_scale.levels
                ],
            },
            "basic_requirements": {
                "paragraphs_min": a.basic_requirements.paragraphs_min,
                "paragraphs_max": a.basic_requirements.paragraphs_max,
                "word_count_min": a.basic_requirements.word_count_min,
                "word_count_max": a.basic_requirements.word_count_max,
                "required_elements": list(a.basic_requirements.required_elements),
            },
            "minimum_requirement_policy": {
                "allow_return_without_full_review": a.minimum_requirement_policy.allow_return_without_full_review
            },
        },
        "students": [_student_to(x) for x in manifest.students],
    }


def _student_to(s: StudentResult) -> dict[str, Any]:
    d = s.submission.digital_provenance
    digital = (
        None
        if d is None
        else {
            "issuance_id": d.issuance_id,
            "generation_id": d.generation_id,
            "artifact_id": d.artifact_id,
            "expected_page_ids": list(d.expected_page_ids),
            "evidence_references": [
                {
                    "page_id": x.page_id,
                    "evidence_id": x.evidence_id,
                    "observation_id": x.observation_id,
                    "route_id": x.route_id,
                    "issuance_id": x.issuance_id,
                    "generation_id": x.generation_id,
                    "artifact_id": x.artifact_id,
                    "source_page_number": x.source_page_number,
                    "source_scan_id": x.source_scan_id,
                    "source_sha256": x.source_sha256,
                    "routed_evidence_sha256": x.routed_evidence_sha256,
                }
                for x in d.evidence_references
            ],
        }
    )
    r = s.review
    return {
        "student_id": s.student_id,
        "source_snapshot": {
            "submission": _source_to(s.source_snapshot.submission),
            "review": _source_to(s.source_snapshot.review),
        },
        "submission": {
            "class_id": s.submission.class_id,
            "assignment_id": s.submission.assignment_id,
            "student_id": s.submission.student_id,
            "submission_state": s.submission.submission_state,
            "entry_method": s.submission.entry_method,
            "expected_pages": s.submission.expected_pages,
            "digital_provenance": digital,
        },
        "review": {
            "class_id": r.class_id,
            "assignment_id": r.assignment_id,
            "student_id": r.student_id,
            "review_state": r.review_state,
            "minimum_requirement_outcome": {
                "status": r.minimum_requirement_outcome.status,
                "returned_without_full_review": r.minimum_requirement_outcome.returned_without_full_review,
                "updated_at": None
                if r.minimum_requirement_outcome.updated_at is None
                else _timestamp_json(r.minimum_requirement_outcome.updated_at),
                "teacher_note": _pt_to(r.minimum_requirement_outcome.teacher_note),
            },
            "review_units": [
                {
                    "unit_id": u.unit_id,
                    "sequence": u.sequence,
                    "label": u.label,
                    "unit_type": u.unit_type,
                    "standard_observations": [
                        {
                            "observation_id": o.observation_id,
                            "standard_id": o.standard_id,
                            "applicable": o.applicable,
                            "evidence_present": o.evidence_present,
                            "rating": o.rating,
                            "rationale": _pt_to(o.rationale),
                            "include_in_feedback": o.include_in_feedback,
                            "updated_at": _timestamp_json(o.updated_at),
                        }
                        for o in u.standard_observations
                    ],
                }
                for u in r.review_units
            ],
            "overall_standard_ratings": [
                {
                    "standard_id": x.standard_id,
                    "rating": x.rating,
                    "rationale": _pt_to(x.rationale),
                    "include_in_feedback": x.include_in_feedback,
                    "updated_at": _timestamp_json(x.updated_at),
                }
                for x in r.overall_standard_ratings
            ],
            "feedback": {
                "include_review_unit_observations": r.feedback.include_review_unit_observations,
                "include_overall_standard_ratings": r.feedback.include_overall_standard_ratings,
                "standard_feedback": [
                    {
                        "standard_id": x.standard_id,
                        "include_overall_rating": x.include_overall_rating,
                        "include_overall_rationale": x.include_overall_rationale,
                        "included_observation_ids": list(x.included_observation_ids),
                        "comments": [
                            {
                                "feedback_comment_id": c.feedback_comment_id,
                                "text": _pt_to(c.text),
                                "include_in_feedback": c.include_in_feedback,
                                "created_at": _timestamp_json(c.created_at),
                            }
                            for c in x.comments
                        ],
                    }
                    for x in r.feedback.standard_feedback
                ],
            },
        },
    }


def manifest_to_canonical_json_bytes(manifest: AcademicResultManifest) -> bytes:
    """Serialize to deterministic UTF-8 JSON with one trailing newline."""
    try:
        return (
            json.dumps(
                manifest_to_mapping(manifest),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                indent=2,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise QuillanAcademicResultManifestValidationError(
            "manifest cannot be serialized as canonical JSON."
        ) from error


def _duplicate_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QuillanAcademicResultManifestDecodeError(
                f"duplicate JSON object key: {key!r}."
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise QuillanAcademicResultManifestDecodeError(
        f"nonfinite JSON number {value!r} is prohibited."
    )


def manifest_from_json_bytes(value: object) -> AcademicResultManifest:
    """Strictly decode UTF-8 JSON bytes and validate the exact v1 contract."""
    if not isinstance(value, bytes):
        raise QuillanAcademicResultManifestDecodeError(
            "manifest JSON input must be bytes."
        )
    try:
        text = value.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise QuillanAcademicResultManifestDecodeError(
            "manifest bytes are not valid UTF-8."
        ) from error
    try:
        decoded = json.loads(
            text, object_pairs_hook=_duplicate_guard, parse_constant=_reject_constant
        )
    except QuillanAcademicResultManifestDecodeError:
        raise
    except (json.JSONDecodeError, RecursionError) as error:
        raise QuillanAcademicResultManifestDecodeError(
            "manifest bytes are not valid JSON."
        ) from error
    try:
        return manifest_from_mapping(decoded)
    except QuillanAcademicResultManifestValidationError as error:
        raise QuillanAcademicResultManifestDecodeError(str(error)) from error


__all__ = [
    "ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION",
    "ACADEMIC_RESULT_MANIFEST_PRODUCER_MODULE_ID",
    "ACADEMIC_RESULT_MANIFEST_RECORD_TYPE",
    "ASSIGNMENT_SOURCE_CONTRACT_VERSION",
    "AcademicResultManifest",
    "AssignmentSnapshot",
    "BasicRequirements",
    "DigitalSubmissionProvenance",
    "EvidenceReference",
    "FeedbackComment",
    "FeedbackComposition",
    "MinimumRequirementOutcome",
    "MinimumRequirementPolicy",
    "OverallStandardRating",
    "PublishedText",
    "QuillanAcademicResultManifestDecodeError",
    "QuillanAcademicResultManifestError",
    "QuillanAcademicResultManifestValidationError",
    "RatingScale",
    "RatingScaleLevel",
    "REVIEW_SOURCE_CONTRACT_VERSION",
    "RecordSet",
    "ReviewSnapshot",
    "ReviewUnit",
    "ReviewUnitDefinition",
    "SourceRecordSnapshot",
    "StandardFeedback",
    "StandardObservation",
    "StudentResult",
    "StudentSourceSnapshot",
    "SubmissionSnapshot",
    "SUBMISSION_SOURCE_CONTRACT_VERSION",
    "WorkReference",
    "manifest_from_json_bytes",
    "manifest_from_mapping",
    "manifest_to_canonical_json_bytes",
    "manifest_to_mapping",
    "validate_manifest",
]

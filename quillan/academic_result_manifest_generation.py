"""Native validation and pure construction for Quillan Academic Result Manifest v1."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.routing_models import ModuleWorkRef
from pds_core.scan_retention import RetainedSourceScan
from pds_core.standards import load_workspace_standards_library

from quillan._path_safety import is_link_like
from quillan.academic_result_manifest import (
    ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
    ACADEMIC_RESULT_MANIFEST_PRODUCER_MODULE_ID,
    ACADEMIC_RESULT_MANIFEST_RECORD_TYPE,
    ASSIGNMENT_SOURCE_CONTRACT_VERSION,
    REVIEW_SOURCE_CONTRACT_VERSION,
    SUBMISSION_SOURCE_CONTRACT_VERSION,
    AcademicResultManifest,
    AssignmentSnapshot,
    BasicRequirements,
    DigitalSubmissionProvenance,
    EvidenceReference,
    FeedbackComment,
    FeedbackComposition,
    MinimumRequirementOutcome,
    MinimumRequirementPolicy,
    MinimumRequirementStatus,
    OverallStandardRating,
    RatingScale,
    RatingScaleLevel,
    RecordSet,
    ReviewSnapshot,
    ReviewState,
    ReviewUnit,
    ReviewUnitDefinition,
    SourceRecordSnapshot,
    StandardFeedback,
    StandardObservation,
    StudentResult,
    StudentSourceSnapshot,
    SubmissionEntryMethod,
    SubmissionSnapshot,
    WorkReference,
    manifest_from_json_bytes,
    manifest_to_canonical_json_bytes,
    validate_manifest,
)
from quillan.atomic_record_io import (
    AtomicRecordConcurrencyError,
    AtomicRecordDurabilityError,
    AtomicRecordError,
    create_exclusive_record,
)
from quillan.assignments import (
    AssignmentConfigError,
    validate_assignment_standards_selection,
)
from quillan.module_errors import (
    QuillanRetainedSourceError,
    QuillanRoutedEvidenceError,
)
from quillan.plain_paper_submission import (
    PLAIN_PAPER_ENTRY_METHOD,
    PLAIN_PAPER_PHYSICAL_EVIDENCE_STATUS,
    PLAIN_PAPER_WORKFLOW,
)
from quillan.publication_projection_policy import (
    QuillanPublicationProjectionPolicyError,
    project_feedback_comment_text,
    project_minimum_outcome_teacher_note,
    project_observation_rationale,
    project_overall_rating_rationale,
    selected_pds2_evidence_is_publishable,
)
from quillan.publication_revision_policy import (
    QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
    ManifestRevisionDisposition,
    ManifestRevisionReason,
    next_record_set_revision,
    plan_manifest_revision,
)
from quillan.record_context import (
    LoadedJsonRecord,
    MissingAssignmentError,
    QuillanRecordContextError,
    ReviewLoadingPolicy,
    canonical_workspace_root,
    load_quillan_assignment_context,
    load_quillan_student_review_context,
    mutable_json_copy,
    student_record_paths,
)
from quillan.module_errors import QuillanObservationValidationError
from quillan.response_page_observations import (
    QuillanResponsePageObservation,
    load_contextual_response_page_observation,
)
from quillan.retained_source import validate_quillan_retained_source
from quillan.routed_evidence import verify_contextual_routed_page_evidence
from quillan.submission_manifest import PDS2_SUBMISSION_ENTRY_METHOD
from quillan.work_paths import (
    academic_result_manifest_relative_path,
    academic_result_manifest_revision_path,
    academic_result_manifests_dir,
    manifest_exports_dir,
    preflight_work_directory_destination,
    preflight_work_file_destination,
    quillan_work_paths,
    quillan_work_ref,
)


class QuillanManifestGenerationError(Exception):
    """Base error for native manifest preparation and generation."""

    def __init__(self, message: str):
        super().__init__(message)
        self._lock_cleanup_failure: ManifestGenerationCleanupFailure | None = None

    @property
    def lock_cleanup_failure(self) -> ManifestGenerationCleanupFailure | None:
        """Describe a producer-lock cleanup failure accompanying this error."""
        return self._lock_cleanup_failure

    def _record_lock_cleanup_failure(
        self, failure: ManifestGenerationCleanupFailure
    ) -> None:
        self._lock_cleanup_failure = failure


class QuillanManifestGenerationValidationError(QuillanManifestGenerationError):
    """Native data or caller input cannot form a valid manifest."""


class QuillanManifestGenerationNotFoundError(QuillanManifestGenerationError):
    """Required managed Quillan state does not exist."""


class QuillanManifestGenerationConflictError(QuillanManifestGenerationError):
    """Validated native state changed during one generation operation."""


class QuillanManifestGenerationIntegrityError(QuillanManifestGenerationError):
    """Persisted native provenance or immutable history contradicts identity."""


class QuillanManifestGenerationWriteError(QuillanManifestGenerationError):
    """Immutable producer storage could not be completed safely."""


@dataclass(frozen=True, slots=True)
class ManifestGenerationCleanupFailure:
    """Privacy-minimized record of an owned generation lock cleanup failure."""

    path: Path
    relative_path: str
    message: str
    error: OSError

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise TypeError("Cleanup failure path must be an absolute Path.")
        if type(self.relative_path) is not str or not self.relative_path:
            raise ValueError("Cleanup failure relative_path must be nonempty text.")
        if type(self.message) is not str or not self.message:
            raise ValueError("Cleanup failure message must be nonempty text.")
        if not isinstance(self.error, OSError):
            raise TypeError("Cleanup failure error must be an OSError.")


@dataclass(frozen=True, slots=True)
class ManifestGenerationPartialSuccessState:
    """Bounded producer metadata for a revision that may already be durable."""

    operation: str
    work: ModuleWorkRef
    revision: int
    path: Path
    relative_path: str
    expected_sha256: str | None
    durable_file_exists: bool
    lock_cleanup_failure: ManifestGenerationCleanupFailure | None = None

    def __post_init__(self) -> None:
        if type(self.operation) is not str or not self.operation:
            raise ValueError("Partial-success operation must be nonempty text.")
        _validate_work_ref(self.work)
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("Partial-success revision must be a positive integer.")
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise TypeError("Partial-success path must be an absolute Path.")
        expected_relative = academic_result_manifest_relative_path(
            self.work, self.revision
        )
        if self.relative_path != expected_relative:
            raise ValueError("Partial-success relative path is not canonical.")
        if self.expected_sha256 is not None and (
            type(self.expected_sha256) is not str
            or len(self.expected_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.expected_sha256)
        ):
            raise ValueError("Partial-success digest must be lowercase SHA-256 text.")
        if type(self.durable_file_exists) is not bool:
            raise TypeError("durable_file_exists must be a Boolean.")
        if (
            self.lock_cleanup_failure is not None
            and type(self.lock_cleanup_failure) is not ManifestGenerationCleanupFailure
        ):
            raise TypeError("lock_cleanup_failure has the wrong type.")


class QuillanManifestGenerationPartialSuccessError(
    QuillanManifestGenerationWriteError
):
    """A manifest revision may be durable although completion failed."""

    def __init__(
        self, message: str, state: ManifestGenerationPartialSuccessState
    ) -> None:
        super().__init__(message)
        self.state = state
        if state.lock_cleanup_failure is not None:
            self._record_lock_cleanup_failure(state.lock_cleanup_failure)


class _DurableManifestCreationError(Exception):
    """Internal signal that immutable installation preceded a later failure."""


@dataclass(frozen=True, slots=True)
class StoredAcademicResultManifest:
    """One exact canonical immutable manifest revision read from producer storage."""

    manifest: AcademicResultManifest
    revision: int
    path: Path
    relative_path: str
    content: bytes
    sha256: str

    def __post_init__(self) -> None:
        _validate_stored_manifest_value(self)


@dataclass(frozen=True, slots=True)
class AcademicResultManifestGenerationResult:
    """One exact replay/creation result with immutable stored bytes."""

    disposition: ManifestRevisionDisposition
    reason: ManifestRevisionReason
    manifest: AcademicResultManifest
    revision: int
    path: Path
    relative_path: str
    content: bytes
    sha256: str

    def __post_init__(self) -> None:
        if self.disposition not in {
            "reuse_existing",
            "create_initial",
            "create_successor",
        }:
            raise QuillanManifestGenerationValidationError(
                "Generation result disposition is invalid."
            )
        if self.reason not in {
            "exact_replay",
            "initial_publication",
            "native_source_changed",
            "publication_projection_changed",
            "historical_reversion",
            "republication_after_withdrawal",
        }:
            raise QuillanManifestGenerationValidationError(
                "Generation result reason is invalid."
            )
        _validate_stored_manifest_value(self)


@dataclass(frozen=True, slots=True)
class NativeRecordByteSnapshot:
    """One exact validated native record bound to work-root-relative source bytes."""

    path: Path
    relative_path: str
    content: bytes
    sha256: str
    contract_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise QuillanManifestGenerationValidationError(
                "Native source path must be an absolute Path."
            )
        if type(self.relative_path) is not str or not self.relative_path:
            raise QuillanManifestGenerationValidationError(
                "Native source relative_path must be nonempty POSIX text."
            )
        relative = PurePosixPath(self.relative_path)
        if (
            relative.is_absolute()
            or relative.as_posix() != self.relative_path
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise QuillanManifestGenerationValidationError(
                "Native source relative_path must be canonical work-root-relative POSIX text."
            )
        if type(self.content) is not bytes:
            raise QuillanManifestGenerationValidationError(
                "Native source content must be exact bytes."
            )
        if self.sha256 != hashlib.sha256(self.content).hexdigest():
            raise QuillanManifestGenerationIntegrityError(
                "Native source digest disagrees with its exact bytes."
            )
        if type(self.contract_version) is not str or not self.contract_version:
            raise QuillanManifestGenerationValidationError(
                "Native source contract_version must be nonempty text."
            )


@dataclass(frozen=True, slots=True)
class ManifestNativeStudentState:
    """Validated direct submission-directory state for one student identity."""

    student_id: str
    submission_source: NativeRecordByteSnapshot | None
    review_source: NativeRecordByteSnapshot | None
    result: StudentResult | None

    def __post_init__(self) -> None:
        try:
            validate_identifier(self.student_id, "student_id")
        except (IdentifierValidationError, TypeError, ValueError) as error:
            raise QuillanManifestGenerationValidationError(
                "Native student state has an invalid student_id."
            ) from error
        if self.review_source is not None and self.submission_source is None:
            raise QuillanManifestGenerationIntegrityError(
                "Native student state cannot contain a review without a submission."
            )
        if self.result is not None:
            if self.submission_source is None or self.review_source is None:
                raise QuillanManifestGenerationIntegrityError(
                    "A represented student requires both native source snapshots."
                )
            if self.result.student_id != self.student_id:
                raise QuillanManifestGenerationIntegrityError(
                    "Represented student identity disagrees with native directory identity."
                )
        elif self.review_source is not None:
            raise QuillanManifestGenerationIntegrityError(
                "A valid submission/review pair must produce a represented result."
            )


@dataclass(frozen=True, slots=True)
class AcademicResultManifestGenerationContext:
    """One immutable, fully validated native snapshot ready for pure construction."""

    workspace_root: Path
    work: ModuleWorkRef
    assignment_source: NativeRecordByteSnapshot
    assignment: AssignmentSnapshot
    submissions_dir_present: bool
    native_students: tuple[ManifestNativeStudentState, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_root, Path) or not self.workspace_root.is_absolute():
            raise QuillanManifestGenerationValidationError(
                "Generation workspace_root must be an absolute Path."
            )
        if Path(os.path.abspath(self.workspace_root)) != self.workspace_root:
            raise QuillanManifestGenerationValidationError(
                "Generation workspace_root must be canonical."
            )
        expected = quillan_work_ref(self.work.class_id, self.work.work_id)
        if self.work != expected:
            raise QuillanManifestGenerationValidationError(
                "Generation work must be an exact Quillan ModuleWorkRef."
            )
        paths = quillan_work_paths(
            self.workspace_root, self.work.class_id, self.work.work_id
        )
        if (
            self.assignment_source.relative_path != "assignment.json"
            or self.assignment_source.path != paths.assignment_path
        ):
            raise QuillanManifestGenerationIntegrityError(
                "Assignment source must be the exact canonical assignment.json."
            )
        if self.assignment_source.contract_version != ASSIGNMENT_SOURCE_CONTRACT_VERSION:
            raise QuillanManifestGenerationIntegrityError(
                "Assignment source contract version is not schema 2."
            )
        if self.assignment.assignment_id != self.work.work_id:
            raise QuillanManifestGenerationIntegrityError(
                "Assignment snapshot identity disagrees with work identity."
            )
        if type(self.submissions_dir_present) is not bool:
            raise QuillanManifestGenerationValidationError(
                "submissions_dir_present must be a Boolean."
            )
        object.__setattr__(self, "native_students", tuple(self.native_students))
        student_ids = tuple(item.student_id for item in self.native_students)
        if student_ids != tuple(sorted(student_ids)) or len(set(student_ids)) != len(
            student_ids
        ):
            raise QuillanManifestGenerationIntegrityError(
                "Native student states must be unique and sorted by student_id."
            )
        if not self.submissions_dir_present and self.native_students:
            raise QuillanManifestGenerationIntegrityError(
                "Native student state cannot exist when the submissions directory is absent."
            )
        for state in self.native_students:
            for source, suffix in (
                (state.submission_source, "submission.json"),
                (state.review_source, "review.json"),
            ):
                if source is None:
                    continue
                expected_relative = f"submissions/{state.student_id}/{suffix}"
                expected_path = paths.work_root.joinpath(
                    *PurePosixPath(expected_relative).parts
                )
                if (
                    source.relative_path != expected_relative
                    or source.path != expected_path
                ):
                    raise QuillanManifestGenerationIntegrityError(
                        "Native student source is not stored at its exact canonical path."
                    )
            if state.result is not None:
                if state.submission_source is None or state.review_source is None:
                    raise QuillanManifestGenerationIntegrityError(
                        "Represented native result is missing an exact source snapshot."
                    )
                if (
                    state.result.source_snapshot.submission
                    != SourceRecordSnapshot(
                        state.submission_source.relative_path,
                        state.submission_source.sha256,
                        state.submission_source.contract_version,
                    )
                    or state.result.source_snapshot.review
                    != SourceRecordSnapshot(
                        state.review_source.relative_path,
                        state.review_source.sha256,
                        state.review_source.contract_version,
                    )
                ):
                    raise QuillanManifestGenerationIntegrityError(
                        "Represented native result source lineage disagrees with captured bytes."
                    )

    @property
    def students(self) -> tuple[StudentResult, ...]:
        """Return only represented results, preserving deterministic student order."""
        return tuple(
            state.result for state in self.native_students if state.result is not None
        )


@dataclass(slots=True)
class _EvidenceValidationCache:
    retained_by_path: dict[str, str]
    retained_by_scan: dict[str, str]
    retained_page_to_page_id: dict[tuple[str, int], str]
    routed_by_path: dict[str, tuple[str, int]]
    verified_retained: set[tuple[str, str]]
    verified_routed: set[tuple[str, str, int]]

    @classmethod
    def empty(cls) -> _EvidenceValidationCache:
        return cls({}, {}, {}, {}, set(), set())


def discover_manifest_student_ids(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
) -> tuple[bool, tuple[str, ...]]:
    """Discover only safe direct submission-directory student identities."""
    try:
        root = canonical_workspace_root(workspace_root)
        work_ref = _validate_work_ref(work_ref)
        assignment_context = load_quillan_assignment_context(root, work_ref)
        directory = assignment_context.paths.submissions_dir
        if not os.path.lexists(directory):
            return False, ()
        if is_link_like(directory) or not directory.is_dir():
            raise QuillanManifestGenerationValidationError(
                "Submission collection must be an ordinary non-link directory."
            )
        student_ids: list[str] = []
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            if is_link_like(child) or not child.is_dir():
                raise QuillanManifestGenerationValidationError(
                    "Submission collection contains an unexpected direct child."
                )
            try:
                student_ids.append(validate_identifier(child.name, "student_id"))
            except (IdentifierValidationError, TypeError, ValueError) as error:
                raise QuillanManifestGenerationValidationError(
                    "Submission collection contains an invalid student directory name."
                ) from error
        return True, tuple(student_ids)
    except QuillanManifestGenerationError:
        raise
    except MissingAssignmentError as error:
        raise QuillanManifestGenerationNotFoundError(
            "Managed Quillan assignment is missing."
        ) from error
    except QuillanRecordContextError as error:
        raise QuillanManifestGenerationValidationError(
            "Managed Quillan assignment context is invalid."
        ) from error
    except OSError as error:
        raise QuillanManifestGenerationValidationError(
            "Could not discover Quillan submission directories."
        ) from error


def load_academic_result_manifest_generation_context(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
) -> AcademicResultManifestGenerationContext:
    """Load and fully validate the native state used by one manifest candidate."""
    try:
        root = canonical_workspace_root(workspace_root)
        work_ref = _validate_work_ref(work_ref)
        assignment_context = load_quillan_assignment_context(root, work_ref)
        assignment_record = assignment_context.assignment_record
        assignment_data = mutable_json_copy(assignment_record.value)
        class_ids = _list(assignment_data["class_ids"], "assignment.class_ids")
        if work_ref.class_id not in class_ids:
            raise QuillanManifestGenerationValidationError(
                f"Class {work_ref.class_id!r} is not included in the assignment."
            )
        try:
            standards_library = load_workspace_standards_library(root)
            selected = validate_assignment_standards_selection(
                assignment_data, standards_library
            )
        except (AssignmentConfigError, OSError, ValueError) as error:
            raise QuillanManifestGenerationValidationError(
                f"Assignment standards are not valid for manifest generation: {error}"
            ) from error
        native_focus = tuple(
            _string(item, "assignment.focus_standard_ids[]")
            for item in _list(
                assignment_data["focus_standard_ids"],
                "assignment.focus_standard_ids",
            )
        )
        if selected != native_focus:
            raise QuillanManifestGenerationIntegrityError(
                "Validated Focus Standard order disagrees with the native assignment."
            )
        assignment = _build_assignment_snapshot(assignment_data)
        assignment_source = _native_record_snapshot(
            assignment_record,
            assignment_context.paths.work_root,
            expected_relative_path="assignment.json",
            expected_contract_version=ASSIGNMENT_SOURCE_CONTRACT_VERSION,
        )
        submissions_present, student_ids = discover_manifest_student_ids(root, work_ref)
        native_students: list[ManifestNativeStudentState] = []
        evidence_cache = _EvidenceValidationCache.empty()
        for student_id in student_ids:
            paths = student_record_paths(root, work_ref, student_id)
            submission_exists = os.path.lexists(paths.submission_manifest_path)
            review_exists = os.path.lexists(paths.review_record_path)
            if not submission_exists and not review_exists:
                native_students.append(
                    ManifestNativeStudentState(student_id, None, None, None)
                )
                continue
            try:
                student_context = load_quillan_student_review_context(
                    root,
                    work_ref,
                    student_id,
                    review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
                )
            except QuillanRecordContextError as error:
                raise QuillanManifestGenerationIntegrityError(
                    "Existing native student result state is invalid."
                ) from error
            submission_source = _native_record_snapshot(
                student_context.submission_record,
                assignment_context.paths.work_root,
                expected_relative_path=f"submissions/{student_id}/submission.json",
                expected_contract_version=SUBMISSION_SOURCE_CONTRACT_VERSION,
            )
            if student_context.review_record is None:
                # The submission is validated but intentionally omitted from the
                # publication result set. Its bytes are not manifest source lineage.
                native_students.append(
                    ManifestNativeStudentState(student_id, None, None, None)
                )
                continue
            review_source = _native_record_snapshot(
                student_context.review_record,
                assignment_context.paths.work_root,
                expected_relative_path=f"submissions/{student_id}/review.json",
                expected_contract_version=REVIEW_SOURCE_CONTRACT_VERSION,
            )
            submission_data = mutable_json_copy(student_context.submission)
            review_value = student_context.review
            if review_value is None:
                raise QuillanManifestGenerationIntegrityError(
                    "Required represented review disappeared from its validated context."
                )
            review_data = mutable_json_copy(review_value)
            submission = _build_submission_snapshot(
                root,
                work_ref,
                submission_data,
                evidence_cache,
            )
            review = _build_review_snapshot(review_data, assignment)
            result = StudentResult(
                student_id=student_id,
                source_snapshot=StudentSourceSnapshot(
                    submission=_source_record_snapshot(submission_source),
                    review=_source_record_snapshot(review_source),
                ),
                submission=submission,
                review=review,
            )
            native_students.append(
                ManifestNativeStudentState(
                    student_id,
                    submission_source,
                    review_source,
                    result,
                )
            )
        context = AcademicResultManifestGenerationContext(
            workspace_root=root,
            work=work_ref,
            assignment_source=assignment_source,
            assignment=assignment,
            submissions_dir_present=submissions_present,
            native_students=tuple(native_students),
        )
        # Validate the projected educational semantics now, before storage orchestration.
        build_academic_result_manifest(
            context,
            record_set_revision=1,
            generated_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        )
        return context
    except QuillanManifestGenerationError:
        raise
    except MissingAssignmentError as error:
        raise QuillanManifestGenerationNotFoundError(
            "Managed Quillan assignment is missing."
        ) from error
    except QuillanRecordContextError as error:
        raise QuillanManifestGenerationValidationError(
            "Managed Quillan record context is invalid."
        ) from error
    except (
        QuillanPublicationProjectionPolicyError,
        QuillanObservationValidationError,
    ) as error:
        raise QuillanManifestGenerationIntegrityError(
            "Native publication projection or selected observation is invalid."
        ) from error
    except (QuillanRetainedSourceError, QuillanRoutedEvidenceError) as error:
        raise QuillanManifestGenerationIntegrityError(
            "Selected publication evidence failed integrity validation."
        ) from error
    except OSError as error:
        raise QuillanManifestGenerationIntegrityError(
            "Could not validate manifest-native evidence."
        ) from error


def verify_generation_context_unchanged(
    context: AcademicResultManifestGenerationContext,
) -> None:
    """Reload all native state and require exact equality with a captured context."""
    if type(context) is not AcademicResultManifestGenerationContext:
        raise QuillanManifestGenerationValidationError(
            "context must be an AcademicResultManifestGenerationContext."
        )
    try:
        current = load_academic_result_manifest_generation_context(
            context.workspace_root, context.work
        )
    except QuillanManifestGenerationError as error:
        raise QuillanManifestGenerationConflictError(
            "Native Quillan state changed or became invalid after the generation snapshot."
        ) from error
    if current != context:
        raise QuillanManifestGenerationConflictError(
            "Native Quillan state changed after the generation snapshot."
        )


def build_academic_result_manifest(
    context: AcademicResultManifestGenerationContext,
    *,
    record_set_revision: int,
    generated_at: datetime,
) -> AcademicResultManifest:
    """Purely construct and validate one existing Quillan manifest-v1 model."""
    if type(context) is not AcademicResultManifestGenerationContext:
        raise QuillanManifestGenerationValidationError(
            "context must be an AcademicResultManifestGenerationContext."
        )
    if isinstance(record_set_revision, bool) or not isinstance(
        record_set_revision, int
    ) or record_set_revision < 1:
        raise QuillanManifestGenerationValidationError(
            "record_set_revision must be a positive non-Boolean integer."
        )
    if (
        not isinstance(generated_at, datetime)
        or generated_at.tzinfo is None
        or generated_at.utcoffset() is None
    ):
        raise QuillanManifestGenerationValidationError(
            "generated_at must be a timezone-aware datetime."
        )
    manifest = AcademicResultManifest(
        record_type=ACADEMIC_RESULT_MANIFEST_RECORD_TYPE,
        contract_version=ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
        producer_module_id=ACADEMIC_RESULT_MANIFEST_PRODUCER_MODULE_ID,
        generated_at=generated_at,
        record_set=RecordSet(
            record_set_id=QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
            revision=record_set_revision,
        ),
        work=WorkReference(
            module_id=context.work.module_id,
            class_id=context.work.class_id,
            work_id=context.work.work_id,
        ),
        source_snapshot=_source_record_snapshot(context.assignment_source),
        assignment=context.assignment,
        students=context.students,
    )
    try:
        return validate_manifest(manifest)
    except Exception as error:
        raise QuillanManifestGenerationValidationError(
            f"Projected native state does not satisfy manifest v1: {error}"
        ) from error


def build_academic_result_manifest_bytes(
    context: AcademicResultManifestGenerationContext,
    *,
    record_set_revision: int,
    generated_at: datetime,
) -> bytes:
    """Purely construct and canonically serialize one manifest candidate."""
    manifest = build_academic_result_manifest(
        context,
        record_set_revision=record_set_revision,
        generated_at=generated_at,
    )
    return manifest_to_canonical_json_bytes(manifest)


def _validate_stored_manifest_value(value: object) -> None:
    manifest = getattr(value, "manifest", None)
    revision = getattr(value, "revision", None)
    path = getattr(value, "path", None)
    relative_path = getattr(value, "relative_path", None)
    content = getattr(value, "content", None)
    digest = getattr(value, "sha256", None)
    if (
        not isinstance(manifest, AcademicResultManifest)
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or revision < 1
        or not isinstance(path, Path)
        or not path.is_absolute()
        or type(relative_path) is not str
        or type(content) is not bytes
        or type(digest) is not str
    ):
        raise QuillanManifestGenerationValidationError(
            "Stored manifest value contains invalid typed fields."
        )
    try:
        decoded = manifest_from_json_bytes(content)
        canonical = manifest_to_canonical_json_bytes(decoded)
        work = quillan_work_ref(
            manifest.work.class_id,
            manifest.work.work_id,
        )
        expected_relative = academic_result_manifest_relative_path(work, revision)
    except Exception as error:
        raise QuillanManifestGenerationIntegrityError(
            "Stored manifest bytes or identity are invalid."
        ) from error
    relative_parts = PurePosixPath(expected_relative).parts
    if (
        decoded != manifest
        or canonical != content
        or manifest.producer_module_id != ACADEMIC_RESULT_MANIFEST_PRODUCER_MODULE_ID
        or manifest.record_set.record_set_id != QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID
        or manifest.record_set.revision != revision
        or manifest.work.module_id != work.module_id
        or relative_path != expected_relative
        or tuple(path.parts[-len(relative_parts) :]) != relative_parts
        or path.name != f"{revision}.json"
        or digest != hashlib.sha256(content).hexdigest()
    ):
        raise QuillanManifestGenerationIntegrityError(
            "Stored manifest fields do not agree."
        )


def _canonical_revision_name(name: str) -> int | None:
    if not name.endswith(".json"):
        return None
    stem = name[:-5]
    if not stem.isdecimal() or stem == "0":
        return None
    try:
        revision = int(stem)
    except ValueError:
        return None
    if str(revision) != stem:
        return None
    return revision


def _load_manifest_history(
    workspace_root: Path,
    work_ref: ModuleWorkRef,
    *,
    allow_generation_lock: bool,
) -> tuple[StoredAcademicResultManifest, ...]:
    root = canonical_workspace_root(workspace_root)
    work = _validate_work_ref(work_ref)
    directory = academic_result_manifests_dir(root, work)
    try:
        preflight_work_directory_destination(
            root,
            work,
            Path("exports") / "manifests" / "academic_results",
        )
    except Exception as error:
        raise QuillanManifestGenerationIntegrityError(
            "Academic-result manifest history path is unsafe."
        ) from error
    if not os.path.lexists(directory):
        return ()
    if is_link_like(directory) or not directory.is_dir():
        raise QuillanManifestGenerationIntegrityError(
            "Academic-result manifest history must be an ordinary non-link directory."
        )
    stored: list[StoredAcademicResultManifest] = []
    try:
        entries = sorted(directory.iterdir(), key=lambda item: item.name)
    except OSError as error:
        raise QuillanManifestGenerationIntegrityError(
            "Could not enumerate immutable manifest history."
        ) from error
    for entry in entries:
        if allow_generation_lock and entry.name == ".write.lock":
            continue
        revision = _canonical_revision_name(entry.name)
        if revision is None:
            raise QuillanManifestGenerationIntegrityError(
                "Manifest history contains an unexpected or noncanonical entry."
            )
        if is_link_like(entry) or not entry.is_file():
            raise QuillanManifestGenerationIntegrityError(
                "Manifest revision must be an ordinary non-link file."
            )
        try:
            content = entry.read_bytes()
            manifest = manifest_from_json_bytes(content)
            canonical = manifest_to_canonical_json_bytes(manifest)
        except Exception as error:
            raise QuillanManifestGenerationIntegrityError(
                f"Manifest revision {revision} is invalid."
            ) from error
        if canonical != content:
            raise QuillanManifestGenerationIntegrityError(
                f"Manifest revision {revision} does not contain canonical bytes."
            )
        if (
            manifest.record_type != ACADEMIC_RESULT_MANIFEST_RECORD_TYPE
            or manifest.contract_version != ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
            or manifest.producer_module_id != ACADEMIC_RESULT_MANIFEST_PRODUCER_MODULE_ID
            or manifest.record_set.record_set_id != QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID
            or manifest.record_set.revision != revision
            or manifest.work.module_id != work.module_id
            or manifest.work.class_id != work.class_id
            or manifest.work.work_id != work.work_id
        ):
            raise QuillanManifestGenerationIntegrityError(
                f"Manifest revision {revision} disagrees with its series or path."
            )
        stored.append(
            StoredAcademicResultManifest(
                manifest=manifest,
                revision=revision,
                path=entry,
                relative_path=academic_result_manifest_relative_path(work, revision),
                content=content,
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )
    revisions = tuple(item.revision for item in stored)
    if len(revisions) != len(set(revisions)):
        raise QuillanManifestGenerationIntegrityError(
            "Manifest history contains duplicate revisions."
        )
    return tuple(sorted(stored, key=lambda item: item.revision))


def list_academic_result_manifest_revisions(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
) -> tuple[StoredAcademicResultManifest, ...]:
    """Read and strictly validate every durable producer revision in one series."""
    try:
        root = canonical_workspace_root(workspace_root)
        work = _validate_work_ref(work_ref)
        return _load_manifest_history(root, work, allow_generation_lock=False)
    except QuillanManifestGenerationError:
        raise
    except QuillanRecordContextError as error:
        raise QuillanManifestGenerationValidationError(
            "Workspace root is invalid for manifest history loading."
        ) from error


def load_academic_result_manifest_revision(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    revision: int,
) -> StoredAcademicResultManifest:
    """Read one exact revision while validating the complete durable series."""
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise QuillanManifestGenerationValidationError(
            "revision must be a positive non-Boolean integer."
        )
    for stored in list_academic_result_manifest_revisions(workspace_root, work_ref):
        if stored.revision == revision:
            return stored
    raise QuillanManifestGenerationNotFoundError(
        f"Academic-result manifest revision {revision} was not found."
    )


def validate_academic_result_manifest_revision(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    revision: int,
) -> StoredAcademicResultManifest:
    """Read-only validation alias for one exact immutable producer revision."""
    return load_academic_result_manifest_revision(workspace_root, work_ref, revision)


def _prepare_manifest_generation_directory(
    workspace_root: Path,
    work_ref: ModuleWorkRef,
) -> Path:
    paths = quillan_work_paths(
        workspace_root, work_ref.class_id, work_ref.work_id
    )
    try:
        preflight_work_file_destination(
            workspace_root, work_ref, "assignment.json"
        )
        preflight_work_directory_destination(
            workspace_root,
            work_ref,
            Path("exports") / "manifests" / "academic_results",
        )
    except Exception as error:
        raise QuillanManifestGenerationValidationError(
            "Managed Quillan generation path is unsafe."
        ) from error
    if (
        not os.path.lexists(paths.work_root)
        or is_link_like(paths.work_root)
        or not paths.work_root.is_dir()
        or not os.path.lexists(paths.assignment_path)
        or is_link_like(paths.assignment_path)
        or not paths.assignment_path.is_file()
    ):
        raise QuillanManifestGenerationNotFoundError(
            "Managed Quillan assignment does not exist as ordinary canonical work."
        )
    manifests = manifest_exports_dir(workspace_root, work_ref)
    directory = academic_result_manifests_dir(workspace_root, work_ref)
    for candidate in (paths.exports_dir, manifests, directory):
        if os.path.lexists(candidate):
            if is_link_like(candidate) or not candidate.is_dir():
                raise QuillanManifestGenerationConflictError(
                    "Manifest generation path contains an unsafe filesystem entry."
                )
            continue
        try:
            candidate.mkdir()
        except FileExistsError:
            if is_link_like(candidate) or not candidate.is_dir():
                raise QuillanManifestGenerationConflictError(
                    "Manifest generation directory was concurrently replaced."
                )
        except OSError as error:
            raise QuillanManifestGenerationWriteError(
                "Could not create the contained manifest generation directory."
            ) from error
        if is_link_like(candidate) or not candidate.is_dir():
            raise QuillanManifestGenerationConflictError(
                "Manifest generation directory changed filesystem type."
            )
    try:
        preflight_work_directory_destination(
            workspace_root,
            work_ref,
            Path("exports") / "manifests" / "academic_results",
        )
    except Exception as error:
        raise QuillanManifestGenerationConflictError(
            "Manifest generation directory became unsafe."
        ) from error
    return directory


def _generation_lock_relative_path(work_ref: ModuleWorkRef) -> str:
    return (
        academic_result_manifest_relative_path(work_ref, 1).rsplit("/", 1)[0]
        + "/.write.lock"
    )


def _acquire_generation_lock(directory: Path) -> tuple[Path, bytes]:
    lock_path = directory / ".write.lock"
    token = b"quillan-manifest-generation-v1\0" + os.urandom(32)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except FileExistsError as error:
        raise QuillanManifestGenerationConflictError(
            "Another manifest generation operation holds .write.lock."
        ) from error
    except OSError as error:
        raise QuillanManifestGenerationWriteError(
            "Could not create the manifest generation lock."
        ) from error
    write_error: OSError | None = None
    try:
        written = os.write(descriptor, token)
        if written != len(token):
            raise OSError("Generation lock token write was incomplete.")
        os.fsync(descriptor)
    except OSError as error:
        write_error = error
    finally:
        try:
            os.close(descriptor)
        except OSError as error:
            if write_error is None:
                write_error = error
    if write_error is not None:
        cleanup: OSError | None = None
        try:
            _release_generation_lock(lock_path, token)
        except OSError as error:
            cleanup = error
        failure = QuillanManifestGenerationWriteError(
            "Could not durably establish the manifest generation lock."
        )
        if cleanup is not None:
            failure.add_note("Owned generation lock cleanup also failed.")
        raise failure from write_error
    return lock_path, token


def _release_generation_lock(lock_path: Path, token: bytes) -> None:
    try:
        if is_link_like(lock_path) or not lock_path.is_file():
            raise OSError("Owned generation lock changed filesystem type.")
        if lock_path.read_bytes() != token:
            raise OSError("Owned generation lock token changed.")
        lock_path.unlink()
    except OSError:
        raise


def _sync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _verify_created_manifest_bytes(
    actual: bytes,
    *,
    expected_manifest: AcademicResultManifest,
    expected_bytes: bytes,
) -> None:
    try:
        decoded = manifest_from_json_bytes(actual)
        canonical = manifest_to_canonical_json_bytes(decoded)
    except Exception as error:
        raise QuillanManifestGenerationIntegrityError(
            "Created manifest bytes are invalid."
        ) from error
    if actual != expected_bytes or canonical != actual or decoded != expected_manifest:
        raise QuillanManifestGenerationIntegrityError(
            "Created manifest bytes contradict the generated candidate."
        )


def _create_immutable_manifest_revision(
    workspace_root: Path,
    work_ref: ModuleWorkRef,
    *,
    revision: int,
    manifest: AcademicResultManifest,
    content: bytes,
) -> Path:
    target = academic_result_manifest_revision_path(
        workspace_root, work_ref, revision
    )
    relative_work_path = (
        Path("exports") / "manifests" / "academic_results" / f"{revision}.json"
    )

    def preflight() -> None:
        try:
            checked = preflight_work_file_destination(
                workspace_root, work_ref, relative_work_path
            )
        except Exception as error:
            raise QuillanManifestGenerationConflictError(
                "Planned manifest revision path became unsafe."
            ) from error
        if checked != target:
            raise QuillanManifestGenerationIntegrityError(
                "Planned manifest revision path is not canonical."
            )

    def verify_bytes(actual: bytes) -> None:
        _verify_created_manifest_bytes(
            actual,
            expected_manifest=manifest,
            expected_bytes=content,
        )

    try:
        result = create_exclusive_record(
            target,
            content,
            preflight=preflight,
            verify_bytes=verify_bytes,
        )
    except AtomicRecordConcurrencyError as error:
        raise QuillanManifestGenerationConflictError(
            "The planned immutable manifest revision already exists or changed."
        ) from error
    except AtomicRecordDurabilityError as error:
        if error.possibly_durable_path is not None:
            raise _DurableManifestCreationError(
                "Manifest revision may be durable after atomic creation failure."
            ) from error
        raise QuillanManifestGenerationWriteError(
            "Manifest revision creation guard cleanup failed before durable creation."
        ) from error
    except AtomicRecordError as error:
        raise QuillanManifestGenerationWriteError(
            "Could not exclusively create the immutable manifest revision."
        ) from error
    if result.status != "created" or result.path != target:
        raise QuillanManifestGenerationIntegrityError(
            "Exclusive manifest writer returned an unexpected result."
        )
    try:
        _sync_directory(target.parent)
    except OSError as error:
        raise _DurableManifestCreationError(
            "Manifest revision is installed but directory sync failed."
        ) from error
    return target


def _clock_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_generation_time(clock: Callable[[], datetime]) -> datetime:
    try:
        value = clock()
    except Exception as error:
        raise QuillanManifestGenerationValidationError(
            "Manifest generation clock failed."
        ) from error
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise QuillanManifestGenerationValidationError(
            "Manifest generation clock must return an aware datetime."
        )
    return value.astimezone(timezone.utc)


def _run_prewrite_verification_hook(
    context: AcademicResultManifestGenerationContext,
) -> None:
    """No-op seam for deterministic concurrency/failure tests."""


def generate_academic_result_manifest(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    republish_after_withdrawal: bool = False,
    clock: Callable[[], datetime] = _clock_now,
) -> AcademicResultManifestGenerationResult:
    """Generate or byte-exactly replay one immutable producer manifest revision."""
    if type(republish_after_withdrawal) is not bool:
        raise QuillanManifestGenerationValidationError(
            "republish_after_withdrawal must be a Boolean."
        )
    if not callable(clock):
        raise QuillanManifestGenerationValidationError("clock must be callable.")
    try:
        root = canonical_workspace_root(workspace_root)
        work = quillan_work_ref(class_id, assignment_id)
        _validate_work_ref(work)
    except QuillanRecordContextError as error:
        raise QuillanManifestGenerationValidationError(
            "workspace_root is invalid."
        ) from error
    except Exception as error:
        raise QuillanManifestGenerationValidationError(
            "class_id and assignment_id must be safe identifiers."
        ) from error

    directory = _prepare_manifest_generation_directory(root, work)
    lock_path, lock_token = _acquire_generation_lock(directory)
    operation_error: BaseException | None = None
    durable_path: Path | None = None
    durable_revision: int | None = None
    expected_digest: str | None = None
    try:
        history = _load_manifest_history(
            root, work, allow_generation_lock=True
        )
        revisions = tuple(item.revision for item in history)
        predecessor = history[-1] if history else None
        context = load_academic_result_manifest_generation_context(root, work)
        candidate_revision = next_record_set_revision(revisions)
        provisional_time = (
            predecessor.manifest.generated_at
            if predecessor is not None
            else _new_generation_time(clock)
        )
        candidate = build_academic_result_manifest(
            context,
            record_set_revision=candidate_revision,
            generated_at=provisional_time,
        )
        plan = plan_manifest_revision(
            predecessor=(predecessor.manifest if predecessor is not None else None),
            candidate=candidate,
            allocated_revisions=revisions,
            historical_manifests=tuple(item.manifest for item in history[:-1]),
            republish_after_withdrawal=republish_after_withdrawal,
        )
        if plan.disposition != "reuse_existing" and predecessor is not None:
            generated_at = _new_generation_time(clock)
            candidate = build_academic_result_manifest(
                context,
                record_set_revision=candidate_revision,
                generated_at=generated_at,
            )
            replanned = plan_manifest_revision(
                predecessor=predecessor.manifest,
                candidate=candidate,
                allocated_revisions=revisions,
                historical_manifests=tuple(item.manifest for item in history[:-1]),
                republish_after_withdrawal=republish_after_withdrawal,
            )
            if (
                replanned.disposition != plan.disposition
                or replanned.reason != plan.reason
                or replanned.record_set_revision != plan.record_set_revision
            ):
                raise QuillanManifestGenerationIntegrityError(
                    "Revision planning changed when only generated_at changed."
                )
            plan = replanned
        _run_prewrite_verification_hook(context)
        verify_generation_context_unchanged(context)
        if plan.disposition == "reuse_existing":
            if predecessor is None or not plan.reuse_existing_bytes:
                raise QuillanManifestGenerationIntegrityError(
                    "Exact replay plan does not identify existing immutable bytes."
                )
            return AcademicResultManifestGenerationResult(
                disposition=plan.disposition,
                reason=plan.reason,
                manifest=predecessor.manifest,
                revision=predecessor.revision,
                path=predecessor.path,
                relative_path=predecessor.relative_path,
                content=predecessor.content,
                sha256=predecessor.sha256,
            )
        if (
            plan.record_set_revision != candidate_revision
            or candidate.record_set.revision != plan.record_set_revision
        ):
            raise QuillanManifestGenerationIntegrityError(
                "Revision planner and candidate revision disagree."
            )
        candidate_bytes = manifest_to_canonical_json_bytes(candidate)
        expected_digest = hashlib.sha256(candidate_bytes).hexdigest()
        target = academic_result_manifest_revision_path(
            root, work, plan.record_set_revision
        )
        relative = academic_result_manifest_relative_path(
            work, plan.record_set_revision
        )
        try:
            _create_immutable_manifest_revision(
                root,
                work,
                revision=plan.record_set_revision,
                manifest=candidate,
                content=candidate_bytes,
            )
        except _DurableManifestCreationError as error:
            durable_path = target
            durable_revision = plan.record_set_revision
            state = ManifestGenerationPartialSuccessState(
                operation="durable_create",
                work=work,
                revision=plan.record_set_revision,
                path=target,
                relative_path=relative,
                expected_sha256=expected_digest,
                durable_file_exists=os.path.lexists(target),
            )
            raise QuillanManifestGenerationPartialSuccessError(
                "Manifest revision may be durable but creation did not finish cleanly.",
                state,
            ) from error
        durable_path = target
        durable_revision = plan.record_set_revision
        try:
            stored_history = _load_manifest_history(
                root, work, allow_generation_lock=True
            )
            stored = next(
                item
                for item in stored_history
                if item.revision == plan.record_set_revision
            )
            if (
                stored.content != candidate_bytes
                or stored.manifest != candidate
                or stored.sha256 != expected_digest
            ):
                raise QuillanManifestGenerationIntegrityError(
                    "Durable manifest revision contradicts the generated candidate."
                )
            result_value = AcademicResultManifestGenerationResult(
                disposition=plan.disposition,
                reason=plan.reason,
                manifest=stored.manifest,
                revision=stored.revision,
                path=stored.path,
                relative_path=stored.relative_path,
                content=stored.content,
                sha256=stored.sha256,
            )
        except Exception as error:
            state = ManifestGenerationPartialSuccessState(
                operation="final_verification",
                work=work,
                revision=plan.record_set_revision,
                path=target,
                relative_path=relative,
                expected_sha256=expected_digest,
                durable_file_exists=os.path.lexists(target),
            )
            raise QuillanManifestGenerationPartialSuccessError(
                "Manifest revision is durable but final verification failed.",
                state,
            ) from error
        return result_value
    except QuillanManifestGenerationError as error:
        operation_error = error
        raise
    except Exception as error:
        normalized = QuillanManifestGenerationIntegrityError(
            "Manifest generation validation or revision planning failed."
        )
        operation_error = normalized
        raise normalized from error
    except BaseException as error:
        operation_error = error
        raise
    finally:
        try:
            _release_generation_lock(lock_path, lock_token)
        except OSError as cleanup_error:
            cleanup_failure = ManifestGenerationCleanupFailure(
                path=lock_path,
                relative_path=_generation_lock_relative_path(work),
                message="Owned manifest generation lock cleanup failed.",
                error=cleanup_error,
            )
            if operation_error is None:
                if durable_path is not None and durable_revision is not None:
                    state = ManifestGenerationPartialSuccessState(
                        operation="lock_cleanup",
                        work=work,
                        revision=durable_revision,
                        path=durable_path,
                        relative_path=academic_result_manifest_relative_path(
                            work, durable_revision
                        ),
                        expected_sha256=expected_digest,
                        durable_file_exists=os.path.lexists(durable_path),
                        lock_cleanup_failure=cleanup_failure,
                    )
                    raise QuillanManifestGenerationPartialSuccessError(
                        "Manifest is durable but generation lock cleanup failed.",
                        state,
                    ) from cleanup_error
                cleanup_failure_error = QuillanManifestGenerationWriteError(
                    "Manifest generation lock cleanup failed."
                )
                cleanup_failure_error._record_lock_cleanup_failure(cleanup_failure)
                raise cleanup_failure_error from cleanup_error
            if isinstance(operation_error, QuillanManifestGenerationError):
                operation_error._record_lock_cleanup_failure(cleanup_failure)
                if isinstance(
                    operation_error, QuillanManifestGenerationPartialSuccessError
                ):
                    operation_error.state = replace(
                        operation_error.state,
                        lock_cleanup_failure=cleanup_failure,
                    )
            else:
                operation_error.add_note(
                    "Owned manifest generation lock cleanup also failed."
                )


def _native_record_snapshot(
    record: LoadedJsonRecord,
    work_root: Path,
    *,
    expected_relative_path: str,
    expected_contract_version: str,
) -> NativeRecordByteSnapshot:
    if type(record) is not LoadedJsonRecord:
        raise QuillanManifestGenerationValidationError(
            "Native source must be a validated LoadedJsonRecord."
        )
    try:
        relative = record.path.relative_to(work_root).as_posix()
    except ValueError as error:
        raise QuillanManifestGenerationIntegrityError(
            "Native record path escapes the selected managed work root."
        ) from error
    if relative != expected_relative_path:
        raise QuillanManifestGenerationIntegrityError(
            "Native source is not stored at its required canonical work-relative path."
        )
    contract = record.value.get("schema_version")
    if contract != expected_contract_version:
        raise QuillanManifestGenerationIntegrityError(
            "Native source has the wrong contract version for manifest generation."
        )
    return NativeRecordByteSnapshot(
        path=record.path,
        relative_path=relative,
        content=record.original_bytes,
        sha256=hashlib.sha256(record.original_bytes).hexdigest(),
        contract_version=expected_contract_version,
    )


def _source_record_snapshot(value: NativeRecordByteSnapshot) -> SourceRecordSnapshot:
    return SourceRecordSnapshot(
        relative_path=value.relative_path,
        sha256=value.sha256,
        contract_version=value.contract_version,
    )


def _build_assignment_snapshot(assignment: dict[str, Any]) -> AssignmentSnapshot:
    review_unit = _mapping(assignment["review_unit"], "assignment.review_unit")
    rating_scale = _mapping(assignment["rating_scale"], "assignment.rating_scale")
    levels = tuple(
        RatingScaleLevel(
            value=_integer(level["value"], "rating_scale.level.value"),
            label=_string(level["label"], "rating_scale.level.label"),
            description=_string(
                level["description"], "rating_scale.level.description"
            ),
        )
        for level in (
            _mapping(item, "assignment.rating_scale.levels[]")
            for item in _list(
                rating_scale["levels"], "assignment.rating_scale.levels"
            )
        )
    )
    basic = _mapping(
        assignment["basic_requirements"], "assignment.basic_requirements"
    )
    policy = _mapping(
        assignment["minimum_requirement_policy"],
        "assignment.minimum_requirement_policy",
    )
    return AssignmentSnapshot(
        assignment_id=_string(assignment["assignment_id"], "assignment.assignment_id"),
        title=_string(assignment["title"], "assignment.title"),
        writing_type=_string(assignment["writing_type"], "assignment.writing_type"),
        student_prompt=_string(
            assignment["student_prompt"], "assignment.student_prompt"
        ),
        standards_profile_id=_string(
            assignment["standards_profile_id"], "assignment.standards_profile_id"
        ),
        focus_standard_ids=tuple(
            _string(item, "assignment.focus_standard_ids[]")
            for item in _list(
                assignment["focus_standard_ids"], "assignment.focus_standard_ids"
            )
        ),
        review_unit=ReviewUnitDefinition(
            type=_string(review_unit["type"], "assignment.review_unit.type"),
            singular_label=_string(
                review_unit["singular_label"], "assignment.review_unit.singular_label"
            ),
            plural_label=_string(
                review_unit["plural_label"], "assignment.review_unit.plural_label"
            ),
        ),
        rating_scale=RatingScale(
            scale_id=_string(rating_scale["scale_id"], "assignment.rating_scale.scale_id"),
            levels=levels,
        ),
        basic_requirements=BasicRequirements(
            paragraphs_min=_optional_integer(basic.get("paragraphs_min")),
            paragraphs_max=_optional_integer(basic.get("paragraphs_max")),
            word_count_min=_optional_integer(basic.get("word_count_min")),
            word_count_max=_optional_integer(basic.get("word_count_max")),
            required_elements=tuple(
                _string(item, "assignment.basic_requirements.required_elements[]")
                for item in _list(
                    basic.get("required_elements", []),
                    "assignment.basic_requirements.required_elements",
                )
            ),
        ),
        minimum_requirement_policy=MinimumRequirementPolicy(
            allow_return_without_full_review=_boolean(
                policy["allow_return_without_full_review"],
                "assignment.minimum_requirement_policy.allow_return_without_full_review",
            )
        ),
    )


def _build_submission_snapshot(
    root: Path,
    work_ref: ModuleWorkRef,
    submission: dict[str, Any],
    cache: _EvidenceValidationCache,
) -> SubmissionSnapshot:
    details = _mapping(submission["module_details"], "submission.module_details")
    entry_method = details.get("submission_entry_method")
    class_id = _string(submission["class_id"], "submission.class_id")
    assignment_id = _string(submission["assignment_id"], "submission.assignment_id")
    student_id = _string(submission["student_id"], "submission.student_id")
    submission_state = _string(
        submission["submission_state"], "submission.submission_state"
    )
    if entry_method == PLAIN_PAPER_ENTRY_METHOD:
        expected_plain_details = {
            "submission_entry_method": PLAIN_PAPER_ENTRY_METHOD,
            "physical_evidence_status": PLAIN_PAPER_PHYSICAL_EVIDENCE_STATUS,
            "created_by_workflow": PLAIN_PAPER_WORKFLOW,
        }
        if details != expected_plain_details:
            raise QuillanManifestGenerationValidationError(
                "Plain-paper native provenance markers are incomplete or contradictory."
            )
        if submission["expected_pages"] is not None or _list(
            submission["pages"], "submission.pages"
        ):
            raise QuillanManifestGenerationValidationError(
                "Plain-paper native submissions require null expected_pages and no page evidence."
            )
        return SubmissionSnapshot(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            submission_state=submission_state,
            entry_method=cast(SubmissionEntryMethod, PLAIN_PAPER_ENTRY_METHOD),
            expected_pages=None,
            digital_provenance=None,
        )
    if entry_method != PDS2_SUBMISSION_ENTRY_METHOD:
        raise QuillanManifestGenerationValidationError(
            "Native submission_entry_method must be 'plain_paper_manual' or "
            "'pds2_response_pages' for publication."
        )
    expected_pages = _positive_integer(
        submission["expected_pages"], "submission.expected_pages"
    )
    issuance_id = _string(details["response_issuance_id"], "response_issuance_id")
    generation_id = _string(details["generation_id"], "generation_id")
    artifact_id = _string(details["artifact_id"], "artifact_id")
    expected_page_ids = tuple(
        _string(item, "expected_page_ids[]")
        for item in _list(details["expected_page_ids"], "expected_page_ids")
    )
    references: list[EvidenceReference] = []
    for page_value in _list(submission["pages"], "submission.pages"):
        page = _mapping(page_value, "submission.pages[]")
        selected_id = page["selected_evidence_id"]
        if selected_id is not None:
            selected_id = _string(selected_id, "page.selected_evidence_id")
        for evidence_value in _list(page["evidence"], "page.evidence"):
            evidence = _mapping(evidence_value, "page.evidence[]")
            try:
                publishable = selected_pds2_evidence_is_publishable(
                    page_selected_evidence_id=selected_id,
                    evidence_id=_string(evidence["evidence_id"], "evidence.evidence_id"),
                    evidence_role=_string(evidence["evidence_role"], "evidence.evidence_role"),
                )
            except QuillanPublicationProjectionPolicyError as error:
                raise QuillanManifestGenerationIntegrityError(str(error)) from error
            if publishable:
                references.append(
                    _build_selected_evidence_reference(
                        root,
                        work_ref,
                        page,
                        evidence,
                        expected_pages=expected_pages,
                        expected_student_id=student_id,
                        cache=cache,
                    )
                )
    provenance = DigitalSubmissionProvenance(
        issuance_id=issuance_id,
        generation_id=generation_id,
        artifact_id=artifact_id,
        expected_page_ids=expected_page_ids,
        evidence_references=tuple(references),
    )
    return SubmissionSnapshot(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        submission_state=submission_state,
        entry_method=cast(SubmissionEntryMethod, PDS2_SUBMISSION_ENTRY_METHOD),
        expected_pages=expected_pages,
        digital_provenance=provenance,
    )


def _build_selected_evidence_reference(
    root: Path,
    work_ref: ModuleWorkRef,
    page: dict[str, Any],
    evidence: dict[str, Any],
    *,
    expected_pages: int,
    expected_student_id: str,
    cache: _EvidenceValidationCache,
) -> EvidenceReference:
    evidence_id = _string(evidence["evidence_id"], "evidence.evidence_id")
    detail = _mapping(evidence["module_details"], "evidence.module_details")
    retained = _mapping(evidence["retained_source"], "evidence.retained_source")
    try:
        observation = load_contextual_response_page_observation(
            root, work_ref, evidence_id
        )
    except (QuillanObservationValidationError, OSError) as error:
        raise QuillanManifestGenerationIntegrityError(
            "Selected evidence has no valid canonical observation."
        ) from error
    _require_observation_agreement(
        observation,
        work_ref=work_ref,
        page=page,
        evidence=evidence,
        detail=detail,
        retained=retained,
        expected_pages=expected_pages,
        expected_student_id=expected_student_id,
    )
    _validate_observation_evidence_files(root, work_ref, observation, cache)
    return EvidenceReference(
        page_id=observation.page_id,
        evidence_id=observation.observation_id,
        observation_id=observation.observation_id,
        route_id=observation.route_id,
        issuance_id=observation.issuance_id,
        generation_id=observation.generation_id,
        artifact_id=observation.artifact_id,
        source_page_number=observation.source_page_number,
        source_scan_id=observation.source_scan_id,
        source_sha256=observation.source_sha256,
        routed_evidence_sha256=observation.routed_evidence_sha256,
    )


def _require_observation_agreement(
    observation: QuillanResponsePageObservation,
    *,
    work_ref: ModuleWorkRef,
    page: dict[str, Any],
    evidence: dict[str, Any],
    detail: dict[str, Any],
    retained: dict[str, Any],
    expected_pages: int,
    expected_student_id: str,
) -> None:
    page_number = _positive_integer(page["page_number"], "page.page_number")
    expected: tuple[tuple[object, object, str], ...] = (
        (observation.class_id, work_ref.class_id, "class_id"),
        (observation.assignment_id, work_ref.work_id, "assignment_id"),
        (observation.student_id, expected_student_id, "student_id"),
        (observation.observation_id, evidence["evidence_id"], "observation_id/evidence_id"),
        (observation.observation_id, detail["observation_id"], "module observation_id"),
        (observation.page_id, detail["page_id"], "page_id"),
        (observation.route_id, detail["route_id"], "route_id"),
        (observation.issuance_id, detail["issuance_id"], "issuance_id"),
        (observation.generation_id, detail["generation_id"], "generation_id"),
        (observation.artifact_id, detail["artifact_id"], "artifact_id"),
        (observation.logical_page, page_number, "logical_page"),
        (observation.logical_page, detail["logical_page"], "module logical_page"),
        (observation.total_pages, expected_pages, "total_pages"),
        (observation.total_pages, detail["total_pages"], "module total_pages"),
        (observation.page_role, detail["page_role"], "page_role"),
        (observation.source_scan_id, retained["source_scan_id"], "source_scan_id"),
        (observation.source_filename, retained["source_filename"], "source_filename"),
        (observation.source_sha256, retained["source_sha256"], "source_sha256"),
        (
            observation.source_page_number,
            retained["source_page_number"],
            "source_page_number",
        ),
        (
            observation.retained_source_path,
            retained["retained_source_path"],
            "retained_source_path",
        ),
        (
            observation.routed_evidence_path,
            evidence["routed_evidence_path"],
            "routed_evidence_path",
        ),
        (
            observation.routed_evidence_sha256,
            detail["routed_evidence_sha256"],
            "routed_evidence_sha256",
        ),
        (
            observation.routed_evidence_kind,
            detail["routed_evidence_kind"],
            "routed_evidence_kind",
        ),
    )
    for actual, native, field in expected:
        if actual != native:
            raise QuillanManifestGenerationIntegrityError(
                f"Selected evidence canonical observation disagrees on {field}."
            )


def _validate_observation_evidence_files(
    root: Path,
    work_ref: ModuleWorkRef,
    observation: QuillanResponsePageObservation,
    cache: _EvidenceValidationCache,
) -> None:
    previous_path_digest = cache.retained_by_path.setdefault(
        observation.retained_source_path, observation.source_sha256
    )
    if previous_path_digest != observation.source_sha256:
        raise QuillanManifestGenerationIntegrityError(
            "One retained-source path identifies contradictory source digests."
        )
    previous_scan_digest = cache.retained_by_scan.setdefault(
        observation.source_scan_id, observation.source_sha256
    )
    if previous_scan_digest != observation.source_sha256:
        raise QuillanManifestGenerationIntegrityError(
            "One source_scan_id identifies contradictory source digests."
        )
    source_page_key = (observation.source_scan_id, observation.source_page_number)
    previous_page_id = cache.retained_page_to_page_id.setdefault(
        source_page_key, observation.page_id
    )
    if previous_page_id != observation.page_id:
        raise QuillanManifestGenerationIntegrityError(
            "One retained source page identifies contradictory page IDs."
        )
    routed_claim = (
        observation.routed_evidence_sha256,
        observation.routed_evidence_size_bytes,
    )
    previous_routed_claim = cache.routed_by_path.setdefault(
        observation.routed_evidence_path, routed_claim
    )
    if previous_routed_claim != routed_claim:
        raise QuillanManifestGenerationIntegrityError(
            "One routed-evidence path identifies contradictory digest or size claims."
        )

    retained_key = (observation.retained_source_path, observation.source_sha256)
    if retained_key not in cache.verified_retained:
        retained_path = root.joinpath(
            *PurePosixPath(observation.retained_source_path).parts
        )
        retained = RetainedSourceScan(
            source_scan_id=observation.source_scan_id,
            source_filename=observation.source_filename,
            source_sha256=observation.source_sha256,
            retained_source_path=retained_path,
            retained_source_relative_path=observation.retained_source_path,
            intake_timestamp=_timestamp(observation.intake_timestamp, "intake_timestamp"),
            intake_date=_date(observation.intake_date, "intake_date"),
        )
        try:
            validate_quillan_retained_source(
                retained,
                workspace_root=root,
                source_page_number=observation.source_page_number,
            )
        except (QuillanRetainedSourceError, ValueError, OSError) as error:
            raise QuillanManifestGenerationIntegrityError(
                "Selected evidence retained-source provenance is invalid."
            ) from error
        digest, _ = _stable_file_digest(retained_path)
        if digest != observation.source_sha256:
            raise QuillanManifestGenerationIntegrityError(
                "Selected evidence retained-source bytes do not match source_sha256."
            )
        cache.verified_retained.add(retained_key)

    routed_key = (
        observation.routed_evidence_path,
        observation.routed_evidence_sha256,
        observation.routed_evidence_size_bytes,
    )
    if routed_key not in cache.verified_routed:
        extension = PurePosixPath(observation.routed_evidence_path).suffix
        try:
            routed_path = verify_contextual_routed_page_evidence(
                root,
                work_ref,
                issuance_id=observation.issuance_id,
                student_id=observation.student_id,
                logical_page=observation.logical_page,
                observation_id=observation.observation_id,
                extension=extension,
                relative_path=observation.routed_evidence_path,
                expected_sha256=observation.routed_evidence_sha256,
                expected_size_bytes=observation.routed_evidence_size_bytes,
            )
        except (QuillanRoutedEvidenceError, OSError) as error:
            raise QuillanManifestGenerationIntegrityError(
                "Selected routed evidence failed canonical size/hash validation."
            ) from error
        digest, size = _stable_file_digest(routed_path)
        if (
            digest != observation.routed_evidence_sha256
            or size != observation.routed_evidence_size_bytes
        ):
            raise QuillanManifestGenerationIntegrityError(
                "Selected routed evidence changed during integrity validation."
            )
        cache.verified_routed.add(routed_key)


def _build_review_snapshot(
    review: dict[str, Any], assignment: AssignmentSnapshot
) -> ReviewSnapshot:
    feedback_data = _mapping(review["feedback"], "review.feedback")
    standard_feedback_values = tuple(
        _mapping(item, "review.feedback.standard_feedback[]")
        for item in _list(
            feedback_data["standard_feedback"],
            "review.feedback.standard_feedback",
        )
    )
    standard_feedback_by_id = {
        _string(item["standard_id"], "standard_feedback.standard_id"): item
        for item in standard_feedback_values
    }
    included_by_standard: Mapping[str, tuple[str, ...]] = {
        standard_id: tuple(
            _string(value, "standard_feedback.included_observation_ids[]")
            for value in _list(
                item["included_observation_ids"],
                "standard_feedback.included_observation_ids",
            )
        )
        for standard_id, item in standard_feedback_by_id.items()
    }
    include_units = _boolean(
        feedback_data["include_review_unit_observations"],
        "feedback.include_review_unit_observations",
    )
    include_overall = _boolean(
        feedback_data["include_overall_standard_ratings"],
        "feedback.include_overall_standard_ratings",
    )
    review_units: list[ReviewUnit] = []
    for unit_value in _list(review["review_units"], "review.review_units"):
        unit = _mapping(unit_value, "review.review_units[]")
        observations: list[StandardObservation] = []
        for observation_value in _list(
            unit["standard_observations"], "review_unit.standard_observations"
        ):
            observation = _mapping(
                observation_value, "review_unit.standard_observations[]"
            )
            observation_id = _string(
                observation["observation_id"], "standard_observation.observation_id"
            )
            standard_id = _string(
                observation["standard_id"], "standard_observation.standard_id"
            )
            rationale = project_observation_rationale(
                _optional_string(observation["rationale"]),
                include_review_unit_observations=include_units,
                observation_id=observation_id,
                standard_id=standard_id,
                included_observation_ids_by_standard=included_by_standard,
            )
            observations.append(
                StandardObservation(
                    observation_id=observation_id,
                    standard_id=standard_id,
                    applicable=_boolean(
                        observation["applicable"], "standard_observation.applicable"
                    ),
                    evidence_present=_optional_boolean(
                        observation["evidence_present"],
                        "standard_observation.evidence_present",
                    ),
                    rating=_optional_integer(observation["rating"]),
                    rationale=rationale,
                    include_in_feedback=_boolean(
                        observation["include_in_feedback"],
                        "standard_observation.include_in_feedback",
                    ),
                    updated_at=_timestamp(
                        observation["updated_at"], "standard_observation.updated_at"
                    ),
                )
            )
        review_units.append(
            ReviewUnit(
                unit_id=_string(unit["unit_id"], "review_unit.unit_id"),
                sequence=_positive_integer(unit["sequence"], "review_unit.sequence"),
                label=_string(unit["label"], "review_unit.label"),
                unit_type=_string(unit["unit_type"], "review_unit.unit_type"),
                standard_observations=tuple(observations),
            )
        )

    overall_ratings: list[OverallStandardRating] = []
    for rating_value in _list(
        review["overall_standard_ratings"], "review.overall_standard_ratings"
    ):
        rating = _mapping(rating_value, "review.overall_standard_ratings[]")
        standard_id = _string(
            rating["standard_id"], "overall_standard_rating.standard_id"
        )
        controls = standard_feedback_by_id.get(standard_id)
        rationale = project_overall_rating_rationale(
            _optional_string(rating["rationale"]),
            include_overall_standard_ratings=include_overall,
            rating_include_in_feedback=_boolean(
                rating["include_in_feedback"],
                "overall_standard_rating.include_in_feedback",
            ),
            standard_feedback_include_overall_rating=(
                None
                if controls is None
                else _boolean(
                    controls["include_overall_rating"],
                    "standard_feedback.include_overall_rating",
                )
            ),
            standard_feedback_include_overall_rationale=(
                None
                if controls is None
                else _boolean(
                    controls["include_overall_rationale"],
                    "standard_feedback.include_overall_rationale",
                )
            ),
        )
        overall_ratings.append(
            OverallStandardRating(
                standard_id=standard_id,
                rating=_integer(rating["rating"], "overall_standard_rating.rating"),
                rationale=rationale,
                include_in_feedback=_boolean(
                    rating["include_in_feedback"],
                    "overall_standard_rating.include_in_feedback",
                ),
                updated_at=_timestamp(
                    rating["updated_at"], "overall_standard_rating.updated_at"
                ),
            )
        )

    standard_feedback: list[StandardFeedback] = []
    for item in standard_feedback_values:
        comments: list[FeedbackComment] = []
        for comment_value in _list(item["comments"], "standard_feedback.comments"):
            comment = _mapping(comment_value, "standard_feedback.comments[]")
            projected = project_feedback_comment_text(
                _string(comment["text"], "feedback_comment.text"),
                include_in_feedback=_boolean(
                    comment["include_in_feedback"],
                    "feedback_comment.include_in_feedback",
                ),
            )
            if projected is None:
                continue
            comments.append(
                FeedbackComment(
                    feedback_comment_id=_string(
                        comment["feedback_comment_id"],
                        "feedback_comment.feedback_comment_id",
                    ),
                    text=projected,
                    include_in_feedback=True,
                    created_at=_timestamp(
                        comment["created_at"], "feedback_comment.created_at"
                    ),
                )
            )
        standard_feedback.append(
            StandardFeedback(
                standard_id=_string(
                    item["standard_id"], "standard_feedback.standard_id"
                ),
                include_overall_rating=_boolean(
                    item["include_overall_rating"],
                    "standard_feedback.include_overall_rating",
                ),
                include_overall_rationale=_boolean(
                    item["include_overall_rationale"],
                    "standard_feedback.include_overall_rationale",
                ),
                included_observation_ids=tuple(
                    _string(value, "standard_feedback.included_observation_ids[]")
                    for value in _list(
                        item["included_observation_ids"],
                        "standard_feedback.included_observation_ids",
                    )
                ),
                comments=tuple(comments),
            )
        )

    outcome_data = _mapping(
        review["minimum_requirement_outcome"],
        "review.minimum_requirement_outcome",
    )
    returned = _boolean(
        outcome_data["returned_without_full_review"],
        "minimum_requirement_outcome.returned_without_full_review",
    )
    if returned and not assignment.minimum_requirement_policy.allow_return_without_full_review:
        raise QuillanManifestGenerationValidationError(
            "Review returns work without full review but assignment policy forbids that outcome."
        )
    review_state = _string(review["review_state"], "review.review_state")
    teacher_note = project_minimum_outcome_teacher_note(
        _optional_string(outcome_data["teacher_note"]),
        status=_string(outcome_data["status"], "minimum_requirement_outcome.status"),
        returned_without_full_review=returned,
        review_state=review_state,
    )
    outcome = MinimumRequirementOutcome(
        status=cast(
            MinimumRequirementStatus,
            _string(outcome_data["status"], "minimum_requirement_outcome.status"),
        ),
        returned_without_full_review=returned,
        updated_at=(
            None
            if outcome_data["updated_at"] is None
            else _timestamp(
                outcome_data["updated_at"], "minimum_requirement_outcome.updated_at"
            )
        ),
        teacher_note=teacher_note,
    )
    return ReviewSnapshot(
        class_id=_string(review["class_id"], "review.class_id"),
        assignment_id=_string(review["assignment_id"], "review.assignment_id"),
        student_id=_string(review["student_id"], "review.student_id"),
        review_state=cast(ReviewState, review_state),
        minimum_requirement_outcome=outcome,
        review_units=tuple(review_units),
        overall_standard_ratings=tuple(overall_ratings),
        feedback=FeedbackComposition(
            include_review_unit_observations=include_units,
            include_overall_standard_ratings=include_overall,
            standard_feedback=tuple(standard_feedback),
        ),
    )


def _stable_file_digest(path: Path) -> tuple[str, int]:
    if is_link_like(path):
        raise QuillanManifestGenerationIntegrityError(
            "Evidence source must not be a symbolic link or junction."
        )
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise QuillanManifestGenerationIntegrityError(
            "Could not open exact evidence bytes."
        ) from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise QuillanManifestGenerationIntegrityError(
                "Evidence source must be an ordinary file."
            )
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
    except OSError as error:
        raise QuillanManifestGenerationIntegrityError(
            "Could not read stable exact evidence bytes."
        ) from error
    finally:
        os.close(descriptor)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or size != before.st_size
    ):
        raise QuillanManifestGenerationConflictError(
            "Evidence changed while being validated."
        )
    return digest.hexdigest(), size


def _validate_work_ref(work_ref: object) -> ModuleWorkRef:
    if not isinstance(work_ref, ModuleWorkRef):
        raise QuillanManifestGenerationValidationError(
            "work_ref must be a ModuleWorkRef."
        )
    expected = quillan_work_ref(work_ref.class_id, work_ref.work_id)
    if work_ref != expected:
        raise QuillanManifestGenerationValidationError(
            "work_ref must be an exact Quillan work reference."
        )
    return work_ref



def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QuillanManifestGenerationValidationError(f"{field} must be an object.")
    return cast(dict[str, Any], value)


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise QuillanManifestGenerationValidationError(f"{field} must be a list.")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuillanManifestGenerationValidationError(
            f"{field} must be nonempty text."
        )
    return value


def _boolean(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise QuillanManifestGenerationValidationError(f"{field} must be a Boolean.")
    return value


def _optional_boolean(value: object, field: str) -> bool | None:
    if value is None:
        return None
    return _boolean(value, field)


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise QuillanManifestGenerationValidationError(f"{field} must be an integer.")
    return value


def _positive_integer(value: object, field: str) -> int:
    result = _integer(value, field)
    if result < 1:
        raise QuillanManifestGenerationValidationError(
            f"{field} must be a positive integer."
        )
    return result


def _optional_integer(value: object) -> int | None:
    if value is None:
        return None
    return _integer(value, "optional integer")


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _string(value, "optional text")


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise QuillanManifestGenerationValidationError(
            f"{field} must be timezone-aware ISO timestamp text."
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise QuillanManifestGenerationValidationError(
            f"{field} must be valid ISO timestamp text."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise QuillanManifestGenerationValidationError(
            f"{field} must be timezone-aware."
        )
    return parsed


def _date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise QuillanManifestGenerationValidationError(
            f"{field} must be ISO date text."
        )
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise QuillanManifestGenerationValidationError(
            f"{field} must be valid ISO date text."
        ) from error


__all__ = [
    "AcademicResultManifestGenerationContext",
    "AcademicResultManifestGenerationResult",
    "ManifestGenerationCleanupFailure",
    "ManifestGenerationPartialSuccessState",
    "ManifestNativeStudentState",
    "NativeRecordByteSnapshot",
    "QuillanManifestGenerationConflictError",
    "QuillanManifestGenerationError",
    "QuillanManifestGenerationIntegrityError",
    "QuillanManifestGenerationNotFoundError",
    "QuillanManifestGenerationPartialSuccessError",
    "QuillanManifestGenerationValidationError",
    "QuillanManifestGenerationWriteError",
    "StoredAcademicResultManifest",
    "build_academic_result_manifest",
    "build_academic_result_manifest_bytes",
    "discover_manifest_student_ids",
    "generate_academic_result_manifest",
    "list_academic_result_manifest_revisions",
    "load_academic_result_manifest_generation_context",
    "load_academic_result_manifest_revision",
    "validate_academic_result_manifest_revision",
    "verify_generation_context_unchanged",
]

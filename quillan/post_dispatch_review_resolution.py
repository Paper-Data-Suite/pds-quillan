"""Append-only resolutions for Quillan-owned post-dispatch occurrences."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Final, Literal, cast
from uuid import uuid4

from pds_core.identifiers import validate_identifier
from pds_core.local_open import LocalOpenError, open_local_path
from pds_core.routing_models import ModuleWorkRef

from quillan.atomic_record_io import (
    AtomicRecordConcurrencyError,
    AtomicRecordDurabilityError,
    AtomicRecordError,
    create_exclusive_record,
)
from quillan.assignment_submission_assembly import AssignmentSubmissionAssemblyResult
from quillan.module_errors import QuillanObservationError
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.post_dispatch_review import (
    POST_DISPATCH_CATEGORIES,
    PersistedPostDispatchReviewOccurrence,
    PostDispatchReviewError,
    PostDispatchReviewOccurrence,
    discover_post_dispatch_review_occurrences,
)
from quillan.record_context import canonical_workspace_root
from quillan.response_page_observations import (
    load_contextual_response_page_observation,
)
from quillan.routed_evidence import verify_contextual_routed_page_evidence
from quillan.submission_manifest import (
    PDS2_SUBMISSION_ENTRY_METHOD,
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_observation_assembly import AssembledQuillanSubmission
from quillan.work_paths import (
    QuillanWorkPathError,
    _is_link_like,
    post_dispatch_review_path,
    post_dispatch_resolution_dir,
    post_dispatch_resolution_path,
    preflight_work_directory_destination,
    preflight_work_file_destination,
    quillan_work_paths,
    quillan_work_ref,
    submission_manifest_path,
)

POST_DISPATCH_RESOLUTION_SCHEMA_VERSION: Final = "1"
POST_DISPATCH_RESOLUTION_RECORD_TYPE: Final = "post_dispatch_review_resolution"
POST_DISPATCH_RESOLUTION_ACTIONS: Final[tuple[str, ...]] = (
    "resolved_after_retry",
    "rescan_needed",
    "record_corrected",
    "cannot_recover",
    "dismissed_duplicate",
    "deferred",
    "other",
)
POST_DISPATCH_GENERIC_RESOLUTION_ACTIONS: Final[tuple[str, ...]] = tuple(
    action
    for action in POST_DISPATCH_RESOLUTION_ACTIONS
    if action != "resolved_after_retry"
)
POST_DISPATCH_RESOLUTION_STATUSES: Final[tuple[str, ...]] = (
    "resolved",
    "deferred",
)

_RESOLUTION_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "record_type",
        "module_id",
        "resolution_id",
        "failure_id",
        "occurrence_path",
        "class_id",
        "assignment_id",
        "status",
        "action",
        "resolved_at",
        "teacher_message",
        "occurrence_identity_snapshot",
        "module_details",
        "retry_provenance",
    }
)

_OCCURRENCE_SNAPSHOT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "failure_id",
        "category",
        "stage",
        "created_at",
        "class_id",
        "assignment_id",
        "student_id",
        "issuance_ids",
        "page_ids",
        "route_ids",
        "observation_ids",
        "source_scan_ids",
        "source_page_numbers",
        "occurrence_sha256",
    }
)

_RETRY_OPERATIONS: Final[tuple[str, ...]] = ("submission_assembly",)
_RETRY_PROVENANCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "operation",
        "class_id",
        "assignment_id",
        "student_id",
        "issuance_ids",
        "assembled_status",
        "manifest_path",
        "assembly_revision",
        "completed_at",
    }
)


class PostDispatchReviewResolutionError(RuntimeError):
    """Raised when a work-local resolution cannot be verified or persisted."""

    def __init__(
        self,
        message: str,
        *,
        possibly_durable_path: Path | None = None,
        possible_lock_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.possibly_durable_path = possibly_durable_path
        self.possible_lock_path = possible_lock_path


@dataclass(frozen=True, slots=True)
class PostDispatchReviewResolution:
    """One exact immutable resolution of a post-dispatch occurrence."""

    resolution_id: str
    failure_id: str
    occurrence_path: str
    class_id: str
    assignment_id: str
    status: Literal["resolved", "deferred"]
    action: str
    resolved_at: str
    teacher_message: str | None
    occurrence_identity_snapshot: Mapping[str, object]
    module_details: Mapping[str, object]
    retry_provenance: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        _identifier(self.resolution_id, "resolution_id")
        _identifier(self.failure_id, "failure_id")
        _identifier(self.class_id, "class_id")
        _identifier(self.assignment_id, "assignment_id")
        _relative_posix(self.occurrence_path, "occurrence_path")
        expected_occurrence_path = post_dispatch_review_path(
            Path(),
            quillan_work_ref(self.class_id, self.assignment_id),
            self.failure_id,
        ).as_posix()
        if self.occurrence_path != expected_occurrence_path:
            raise PostDispatchReviewResolutionError(
                "Resolution occurrence_path is not the exact canonical occurrence path."
            )
        if (
            type(self.status) is not str
            or self.status not in POST_DISPATCH_RESOLUTION_STATUSES
        ):
            raise PostDispatchReviewResolutionError("Resolution status is invalid.")
        if (
            type(self.action) is not str
            or self.action not in POST_DISPATCH_RESOLUTION_ACTIONS
        ):
            raise PostDispatchReviewResolutionError("Resolution action is invalid.")
        if (self.action == "deferred") != (self.status == "deferred"):
            raise PostDispatchReviewResolutionError(
                "Only deferred action may use deferred status."
            )
        if _timestamp(self.resolved_at, "resolved_at") != self.resolved_at:
            raise PostDispatchReviewResolutionError(
                "resolved_at must be normalized UTC timestamp text."
            )
        if self.teacher_message is not None and (
            type(self.teacher_message) is not str
            or not self.teacher_message
            or self.teacher_message != self.teacher_message.strip()
        ):
            raise PostDispatchReviewResolutionError(
                "teacher_message must be nonblank trimmed text or null."
            )
        if self.action == "other" and self.teacher_message is None:
            raise PostDispatchReviewResolutionError(
                "The other action requires a teacher message."
            )
        if (self.action == "resolved_after_retry") != (
            self.retry_provenance is not None
        ):
            raise PostDispatchReviewResolutionError(
                "resolved_after_retry requires exact current retry provenance, and "
                "other actions must not carry retry provenance."
            )
        if self.retry_provenance is not None:
            provenance = _validated_retry_provenance(self.retry_provenance)
            object.__setattr__(self, "retry_provenance", provenance)
            if (
                provenance["class_id"] != self.class_id
                or provenance["assignment_id"] != self.assignment_id
            ):
                raise PostDispatchReviewResolutionError(
                    "Retry provenance disagrees with resolution work identity."
                )
            if datetime.fromisoformat(
                cast(str, provenance["completed_at"])
            ) > datetime.fromisoformat(self.resolved_at):
                raise PostDispatchReviewResolutionError(
                    "Resolution timestamp predates the successful retry."
                )
        snapshot = _frozen_mapping(
            self.occurrence_identity_snapshot,
            "occurrence_identity_snapshot",
            max_keys=16,
        )
        details = _frozen_mapping(self.module_details, "module_details", max_keys=8)
        object.__setattr__(self, "occurrence_identity_snapshot", snapshot)
        object.__setattr__(self, "module_details", details)
        _validate_occurrence_snapshot(self)


@dataclass(frozen=True, slots=True)
class PersistedPostDispatchReviewResolution:
    """A verified work-local resolution and canonical paths."""

    workspace_root: Path
    work_ref: ModuleWorkRef
    resolution: PostDispatchReviewResolution
    path: Path
    relative_path: str

    def __post_init__(self) -> None:
        if type(self.workspace_root) is not type(Path()):
            raise PostDispatchReviewResolutionError(
                "Persisted resolution workspace_root must be an exact Path."
            )
        try:
            canonical_root = canonical_workspace_root(self.workspace_root)
        except (OSError, TypeError, ValueError) as error:
            raise PostDispatchReviewResolutionError(str(error)) from error
        if self.workspace_root != canonical_root:
            raise PostDispatchReviewResolutionError(
                "Persisted resolution workspace_root must be canonical."
            )
        if type(self.work_ref) is not ModuleWorkRef:
            raise PostDispatchReviewResolutionError(
                "Persisted resolution work_ref must be an exact ModuleWorkRef."
            )
        if type(self.resolution) is not PostDispatchReviewResolution:
            raise PostDispatchReviewResolutionError(
                "Persisted resolution has the wrong model type."
            )
        expected_ref = quillan_work_ref(
            self.resolution.class_id, self.resolution.assignment_id
        )
        if self.work_ref != expected_ref:
            raise PostDispatchReviewResolutionError(
                "Persisted resolution work_ref disagrees with its identity."
            )
        if type(self.path) is not type(Path()) or not self.path.is_absolute():
            raise PostDispatchReviewResolutionError(
                "Persisted resolution path must be an exact absolute Path."
            )
        expected_path = post_dispatch_resolution_path(
            self.workspace_root, self.work_ref, self.resolution.resolution_id
        )
        if self.path != expected_path:
            raise PostDispatchReviewResolutionError(
                "Persisted resolution path is not its exact canonical path."
            )
        _relative_posix(self.relative_path, "relative_path")
        if self.relative_path != self.path.relative_to(self.workspace_root).as_posix():
            raise PostDispatchReviewResolutionError(
                "Persisted resolution relative path is not exact."
            )


@dataclass(frozen=True, slots=True)
class PostDispatchReviewItem:
    """One occurrence paired with its deterministic latest resolution."""

    occurrence: PersistedPostDispatchReviewOccurrence
    latest_resolution: PersistedPostDispatchReviewResolution | None

    def __post_init__(self) -> None:
        if type(self.occurrence) is not PersistedPostDispatchReviewOccurrence:
            raise PostDispatchReviewResolutionError(
                "Review item occurrence has the wrong runtime type."
            )
        if self.latest_resolution is not None:
            if type(self.latest_resolution) is not PersistedPostDispatchReviewResolution:
                raise PostDispatchReviewResolutionError(
                    "Review item resolution has the wrong runtime type."
                )
            _verify_resolution_link(
                self.latest_resolution.resolution, self.occurrence
            )

    @property
    def display_status(self) -> str:
        return (
            "unresolved"
            if self.latest_resolution is None
            else self.latest_resolution.resolution.status
        )


@dataclass(frozen=True, slots=True)
class PostDispatchReviewResolutionDiscovery:
    """Filtered post-dispatch items and conservative malformed-record warnings."""

    items: tuple[PostDispatchReviewItem, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.items) is not tuple or any(
            type(item) is not PostDispatchReviewItem for item in self.items
        ):
            raise PostDispatchReviewResolutionError(
                "Discovery items must be an exact review-item tuple."
            )
        if type(self.warnings) is not tuple or any(
            type(item) is not str or not item for item in self.warnings
        ):
            raise PostDispatchReviewResolutionError(
                "Discovery warnings must be nonblank text."
            )
        failure_ids = tuple(
            item.occurrence.occurrence.failure_id for item in self.items
        )
        if len(set(failure_ids)) != len(failure_ids):
            raise PostDispatchReviewResolutionError(
                "Discovery contains duplicate occurrence identities."
            )
        expected = tuple(
            sorted(
                self.items,
                key=lambda item: (
                    item.occurrence.occurrence.created_at,
                    item.occurrence.occurrence.failure_id,
                ),
            )
        )
        if self.items != expected:
            raise PostDispatchReviewResolutionError(
                "Discovery items are not deterministically ordered."
            )


@dataclass(frozen=True, slots=True)
class OpenedPostDispatchPossiblePath:
    """One validated occurrence-owned contextual file opened read-only."""

    workspace_root: Path
    work_ref: ModuleWorkRef
    failure_id: str
    kind: Literal["evidence", "manifest"]
    path: Path
    relative_path: str

    def __post_init__(self) -> None:
        if type(self.workspace_root) is not type(Path()):
            raise PostDispatchReviewResolutionError(
                "Opened contextual workspace_root must be an exact Path."
            )
        try:
            canonical_root = canonical_workspace_root(self.workspace_root)
        except (OSError, TypeError, ValueError) as error:
            raise PostDispatchReviewResolutionError(str(error)) from error
        if self.workspace_root != canonical_root:
            raise PostDispatchReviewResolutionError(
                "Opened contextual workspace_root must be canonical."
            )
        if type(self.work_ref) is not ModuleWorkRef:
            raise PostDispatchReviewResolutionError(
                "Opened contextual work_ref must be an exact ModuleWorkRef."
            )
        canonical_ref = quillan_work_ref(
            self.work_ref.class_id, self.work_ref.work_id
        )
        if self.work_ref != canonical_ref:
            raise PostDispatchReviewResolutionError(
                "Opened contextual work_ref must be an exact Quillan work reference."
            )
        _identifier(self.failure_id, "failure_id")
        if type(self.kind) is not str or self.kind not in {"evidence", "manifest"}:
            raise PostDispatchReviewResolutionError(
                "Opened contextual path kind is invalid."
            )
        if type(self.path) is not type(Path()) or not self.path.is_absolute():
            raise PostDispatchReviewResolutionError(
                "Opened contextual path must be an exact absolute Path."
            )
        _relative_posix(self.relative_path, "relative_path")
        if self.path != self.workspace_root.joinpath(
            *PurePosixPath(self.relative_path).parts
        ):
            raise PostDispatchReviewResolutionError(
                "Opened contextual path and relative_path disagree."
            )
        work_root = quillan_work_paths(
            self.workspace_root, self.work_ref.class_id, self.work_ref.work_id
        ).work_root
        try:
            self.path.relative_to(work_root)
        except ValueError as error:
            raise PostDispatchReviewResolutionError(
                "Opened contextual path escapes its exact Quillan work root."
            ) from error


def discover_post_dispatch_review_items(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    *,
    include_resolved: bool = False,
    category: str | None = None,
    limit: int | None = None,
) -> PostDispatchReviewResolutionDiscovery:
    """Discover occurrences and their latest valid append-only resolutions."""
    root, canonical_ref = _context(workspace_root, work_ref)
    if category is not None and category not in POST_DISPATCH_CATEGORIES:
        raise PostDispatchReviewResolutionError(
            f"Unknown post-dispatch category: {category}"
        )
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
    ):
        raise PostDispatchReviewResolutionError("limit must be a positive integer.")
    try:
        occurrences = discover_post_dispatch_review_occurrences(root, canonical_ref)
    except PostDispatchReviewError as error:
        raise PostDispatchReviewResolutionError(str(error)) from error
    occurrence_by_id = {
        item.occurrence.failure_id: item for item in occurrences.items
    }
    resolutions, resolution_warnings = _discover_resolutions(
        root, canonical_ref, occurrence_by_id
    )
    latest: dict[str, PersistedPostDispatchReviewResolution] = {}
    for persisted in resolutions:
        failure_id = persisted.resolution.failure_id
        current = latest.get(failure_id)
        if current is None or _resolution_order(persisted) > _resolution_order(current):
            latest[failure_id] = persisted

    items: list[PostDispatchReviewItem] = []
    for occurrence in occurrences.items:
        if category is not None and occurrence.occurrence.category != category:
            continue
        resolution = latest.get(occurrence.occurrence.failure_id)
        if (
            resolution is not None
            and resolution.resolution.status == "resolved"
            and not include_resolved
        ):
            continue
        items.append(PostDispatchReviewItem(occurrence, resolution))
    if limit is not None:
        items = items[:limit]
    return PostDispatchReviewResolutionDiscovery(
        tuple(items), (*occurrences.warnings, *resolution_warnings)
    )


def open_post_dispatch_possible_path(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    failure_id: str,
    *,
    kind: Literal["evidence", "manifest"],
    relative_path: str,
) -> OpenedPostDispatchPossiblePath:
    """Validate and open one exact path stored by the selected occurrence."""
    root, canonical_ref = _context(workspace_root, work_ref)
    _identifier(failure_id, "failure_id")
    if type(kind) is not str or kind not in {"evidence", "manifest"}:
        raise PostDispatchReviewResolutionError(
            "Contextual path kind must be evidence or manifest."
        )
    selected_relative = _relative_posix(relative_path, "relative_path")
    discovery = discover_post_dispatch_review_items(
        root, canonical_ref, include_resolved=True
    )
    matches = [
        item
        for item in discovery.items
        if item.occurrence.occurrence.failure_id == failure_id
    ]
    if len(matches) != 1:
        raise PostDispatchReviewResolutionError(
            f"No unique valid post-dispatch occurrence has failure ID {failure_id}."
        )
    persisted = matches[0].occurrence
    _read_occurrence_revision(root, canonical_ref, persisted)
    occurrence = persisted.occurrence
    allowed = (
        occurrence.possible_evidence_paths
        if kind == "evidence"
        else occurrence.possible_manifest_paths
    )
    if selected_relative not in allowed:
        raise PostDispatchReviewResolutionError(
            "Selected path is not stored by this exact occurrence."
        )
    target = root.joinpath(*PurePosixPath(selected_relative).parts)
    work_root = quillan_work_paths(
        root, canonical_ref.class_id, canonical_ref.work_id
    ).work_root
    try:
        work_relative = target.relative_to(work_root)
    except ValueError as error:
        raise PostDispatchReviewResolutionError(
            "Selected path escapes the affected Quillan work root."
        ) from error
    try:
        checked = preflight_work_file_destination(
            root, canonical_ref, work_relative
        )
    except QuillanWorkPathError as error:
        raise PostDispatchReviewResolutionError(str(error)) from error
    if checked != target:
        raise PostDispatchReviewResolutionError(
            "Selected path preflight returned a different path."
        )
    if (
        not os.path.lexists(target)
        or _is_link_like(target)
        or not target.is_file()
    ):
        raise PostDispatchReviewResolutionError(
            "Selected contextual path must be an ordinary non-link file."
        )
    if kind == "manifest":
        _validate_possible_manifest(target, occurrence)
    else:
        _validate_possible_evidence(root, canonical_ref, selected_relative, occurrence)
    try:
        opened = open_local_path(target)
    except LocalOpenError as error:
        raise PostDispatchReviewResolutionError(
            f"Could not open validated contextual path: {error}"
        ) from error
    return OpenedPostDispatchPossiblePath(
        root,
        canonical_ref,
        failure_id,
        kind,
        opened,
        selected_relative,
    )


def _matching_verified_retry_assembly(
    persisted_occurrence: PersistedPostDispatchReviewOccurrence,
    result: AssignmentSubmissionAssemblyResult,
    *,
    completed_at: datetime | str,
) -> AssembledQuillanSubmission | None:
    """Return the exact assembled target only when current durable state proves it."""
    if type(persisted_occurrence) is not PersistedPostDispatchReviewOccurrence:
        raise PostDispatchReviewResolutionError(
            "Retry proof requires an exact persisted occurrence."
        )
    if type(result) is not AssignmentSubmissionAssemblyResult:
        raise PostDispatchReviewResolutionError(
            "Retry proof requires an exact assignment assembly result."
        )
    root, work_ref = _context(
        persisted_occurrence.workspace_root, persisted_occurrence.work_ref
    )
    if root != persisted_occurrence.workspace_root:
        raise PostDispatchReviewResolutionError(
            "Retry occurrence workspace identity is not canonical."
        )
    occurrence = persisted_occurrence.occurrence
    if (
        result.class_id != occurrence.class_id
        or result.assignment_id != occurrence.assignment_id
        or work_ref.class_id != occurrence.class_id
        or work_ref.work_id != occurrence.assignment_id
    ):
        raise PostDispatchReviewResolutionError(
            "Retry result disagrees with the selected occurrence work identity."
        )
    _read_occurrence_revision(root, work_ref, persisted_occurrence)
    if occurrence.category not in {
        "submission_assembly",
        "mixed_issuance",
        "manifest_conflict",
    }:
        return None

    expected_issuances = set(occurrence.issuance_ids)
    if occurrence.student_id is not None:
        relevant_assembled = tuple(
            assembled
            for assembled in result.assembled
            if assembled.student_id == occurrence.student_id
        )
        relevant_failures = tuple(
            failure
            for failure in result.failures
            if failure.student_id == occurrence.student_id
            or bool(expected_issuances.intersection(failure.issuance_ids))
        )
    elif occurrence.category == "mixed_issuance":
        if not expected_issuances:
            return None
        relevant_assembled = tuple(
            assembled
            for assembled in result.assembled
            if assembled.issuance_id in expected_issuances
        )
        relevant_failures = result.failures
    elif occurrence.category == "manifest_conflict":
        relevant_assembled = tuple(
            assembled
            for assembled in result.assembled
            if not expected_issuances
            or assembled.issuance_id in expected_issuances
        )
        relevant_failures = result.failures
    else:
        # An assignment-level assembly failure is proven repaired only by one
        # concrete processed target and a wholly successful assignment retry.
        relevant_assembled = result.assembled
        relevant_failures = result.failures

    if len(relevant_assembled) != 1 or relevant_failures:
        return None
    assembled = relevant_assembled[0]
    if type(assembled) is not AssembledQuillanSubmission:
        return None
    if (
        assembled.workspace_root != root
        or assembled.class_id != occurrence.class_id
        or assembled.assignment_id != occurrence.assignment_id
    ):
        return None
    if expected_issuances:
        if occurrence.category == "mixed_issuance":
            if assembled.issuance_id not in expected_issuances:
                return None
        elif expected_issuances != {assembled.issuance_id}:
            return None

    canonical_manifest = submission_manifest_path(
        root, work_ref, assembled.student_id
    )
    if assembled.manifest_path != canonical_manifest:
        return None
    expected_relative = canonical_manifest.relative_to(root).as_posix()
    if assembled.manifest_relative_path != expected_relative:
        return None
    try:
        checked_manifest = preflight_work_file_destination(
            root,
            work_ref,
            Path("submissions") / assembled.student_id / "submission.json",
        )
        if checked_manifest != canonical_manifest:
            return None
        manifest = load_submission_manifest(checked_manifest)
    except (OSError, QuillanWorkPathError, SubmissionManifestError):
        return None
    details = manifest.get("module_details")
    if (
        manifest.get("class_id") != occurrence.class_id
        or manifest.get("assignment_id") != occurrence.assignment_id
        or manifest.get("student_id") != assembled.student_id
        or type(details) is not dict
        or details.get("submission_entry_method") != PDS2_SUBMISSION_ENTRY_METHOD
        or details.get("response_issuance_id") != assembled.issuance_id
        or details.get("assembly_revision") != assembled.assembly_revision
    ):
        return None
    timestamp = _timestamp(completed_at, "completed_at")
    if datetime.fromisoformat(timestamp) < datetime.fromisoformat(
        occurrence.created_at
    ):
        raise PostDispatchReviewResolutionError(
            "Retry completion timestamp predates the selected occurrence."
        )
    return assembled


def post_dispatch_retry_proves_resolution(
    persisted_occurrence: PersistedPostDispatchReviewOccurrence,
    result: AssignmentSubmissionAssemblyResult,
    *,
    completed_at: datetime | str,
) -> bool:
    """Report whether a current typed retry proves the selected occurrence repaired."""
    try:
        return (
            _matching_verified_retry_assembly(
                persisted_occurrence,
                result,
                completed_at=completed_at,
            )
            is not None
        )
    except PostDispatchReviewResolutionError:
        return False


def _current_occurrence(
    root: Path,
    work_ref: ModuleWorkRef,
    failure_id: str,
) -> tuple[PersistedPostDispatchReviewOccurrence, bytes]:
    try:
        discovery = discover_post_dispatch_review_occurrences(root, work_ref)
    except PostDispatchReviewError as error:
        raise PostDispatchReviewResolutionError(str(error)) from error
    matches = [
        item for item in discovery.items if item.occurrence.failure_id == failure_id
    ]
    if len(matches) != 1:
        suffix = (
            f" Warnings: {'; '.join(discovery.warnings)}"
            if discovery.warnings
            else ""
        )
        raise PostDispatchReviewResolutionError(
            f"No unique valid post-dispatch occurrence has failure ID {failure_id}."
            + suffix
        )
    occurrence = matches[0]
    return occurrence, _read_occurrence_revision(root, work_ref, occurrence)


def resolve_post_dispatch_review_occurrence(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    failure_id: str,
    *,
    action: str,
    message: str | None = None,
    resolved_at: datetime | str | None = None,
    resolution_id: str | None = None,
) -> PersistedPostDispatchReviewResolution:
    """Append and verify one resolution without mutating its occurrence."""
    root, canonical_ref = _context(workspace_root, work_ref)
    _identifier(failure_id, "failure_id")
    if action not in POST_DISPATCH_GENERIC_RESOLUTION_ACTIONS:
        raise PostDispatchReviewResolutionError(
            f"Unsupported post-dispatch resolution action: {action}"
        )
    teacher_message = _message(action, message)
    status: Literal["resolved", "deferred"] = (
        "deferred" if action == "deferred" else "resolved"
    )
    occurrence, occurrence_revision = _current_occurrence(
        root, canonical_ref, failure_id
    )
    timestamp = _timestamp(resolved_at, "resolved_at")
    allocated_id = resolution_id or f"resolution_{uuid4().hex}"
    _identifier(allocated_id, "resolution_id")
    resolution = PostDispatchReviewResolution(
        resolution_id=allocated_id,
        failure_id=failure_id,
        occurrence_path=occurrence.relative_path,
        class_id=canonical_ref.class_id,
        assignment_id=canonical_ref.work_id,
        status=status,
        action=action,
        resolved_at=timestamp,
        teacher_message=teacher_message,
        occurrence_identity_snapshot=_occurrence_snapshot(
            occurrence, occurrence_revision
        ),
        module_details={
            "resolved_by": "teacher",
            "resolution_origin": "quillan_post_dispatch_review",
            "occurrence_category": occurrence.occurrence.category,
            "occurrence_stage": occurrence.occurrence.stage,
        },
        retry_provenance=None,
    )
    return _write_resolution(
        root,
        canonical_ref,
        occurrence,
        occurrence_revision,
        resolution,
    )


def resolve_post_dispatch_after_successful_retry(
    workspace_root: str | Path,
    work_ref: ModuleWorkRef,
    failure_id: str,
    *,
    assembly_result: AssignmentSubmissionAssemblyResult,
    completed_at: datetime | str,
    message: str | None = None,
    resolved_at: datetime | str | None = None,
    resolution_id: str | None = None,
) -> PersistedPostDispatchReviewResolution:
    """Prove one current retry and atomically resolve only its exact occurrence."""
    root, canonical_ref = _context(workspace_root, work_ref)
    _identifier(failure_id, "failure_id")
    occurrence, occurrence_revision = _current_occurrence(
        root, canonical_ref, failure_id
    )
    assembled = _matching_verified_retry_assembly(
        occurrence,
        assembly_result,
        completed_at=completed_at,
    )
    if assembled is None:
        raise PostDispatchReviewResolutionError(
            "The assembly result does not prove that this occurrence was resolved."
        )
    completion_timestamp = _timestamp(completed_at, "completed_at")
    provenance: dict[str, object] = {
        "operation": "submission_assembly",
        "class_id": canonical_ref.class_id,
        "assignment_id": canonical_ref.work_id,
        "student_id": assembled.student_id,
        "issuance_ids": (assembled.issuance_id,),
        "assembled_status": assembled.status,
        "manifest_path": assembled.manifest_relative_path,
        "assembly_revision": assembled.assembly_revision,
        "completed_at": completion_timestamp,
    }
    if _retry_provenance_was_used(root, canonical_ref, provenance):
        raise PostDispatchReviewResolutionError(
            "This successful retry has already authorized another resolution."
        )
    timestamp = _timestamp(resolved_at, "resolved_at")
    allocated_id = resolution_id or f"resolution_{uuid4().hex}"
    _identifier(allocated_id, "resolution_id")
    resolution = PostDispatchReviewResolution(
        resolution_id=allocated_id,
        failure_id=failure_id,
        occurrence_path=occurrence.relative_path,
        class_id=canonical_ref.class_id,
        assignment_id=canonical_ref.work_id,
        status="resolved",
        action="resolved_after_retry",
        resolved_at=timestamp,
        teacher_message=_message("resolved_after_retry", message),
        occurrence_identity_snapshot=_occurrence_snapshot(
            occurrence, occurrence_revision
        ),
        module_details={
            "resolved_by": "teacher",
            "resolution_origin": "quillan_post_dispatch_review",
            "occurrence_category": occurrence.occurrence.category,
            "occurrence_stage": occurrence.occurrence.stage,
        },
        retry_provenance=provenance,
    )
    return _write_resolution(
        root,
        canonical_ref,
        occurrence,
        occurrence_revision,
        resolution,
    )


resolve_post_dispatch_review_item = resolve_post_dispatch_review_occurrence


def _discover_resolutions(
    root: Path,
    work_ref: ModuleWorkRef,
    occurrences: Mapping[str, PersistedPostDispatchReviewOccurrence],
) -> tuple[tuple[PersistedPostDispatchReviewResolution, ...], tuple[str, ...]]:
    directory = post_dispatch_resolution_dir(root, work_ref)
    if not os.path.lexists(directory):
        try:
            preflight_work_directory_destination(
                root,
                work_ref,
                Path("scans") / "review" / "post_dispatch" / "resolutions",
            )
        except QuillanWorkPathError as error:
            return (), (f"Unsafe resolution directory: {error}",)
        return (), ()
    try:
        preflight_work_directory_destination(
            root,
            work_ref,
            Path("scans") / "review" / "post_dispatch" / "resolutions",
        )
        children = tuple(sorted(directory.iterdir(), key=lambda item: item.name))
    except (OSError, QuillanWorkPathError) as error:
        return (), (f"Could not inspect post-dispatch resolutions: {error}",)
    results: list[PersistedPostDispatchReviewResolution] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for path in children:
        if path.suffix != ".json":
            continue
        try:
            preflight_work_file_destination(
                root,
                work_ref,
                Path("scans")
                / "review"
                / "post_dispatch"
                / "resolutions"
                / path.name,
            )
            resolution = _resolution_from_bytes(path.read_bytes())
            if resolution.resolution_id in seen:
                raise PostDispatchReviewResolutionError("duplicate resolution_id")
            seen.add(resolution.resolution_id)
            if path != post_dispatch_resolution_path(
                root, work_ref, resolution.resolution_id
            ):
                raise PostDispatchReviewResolutionError(
                    "filename and resolution_id disagree"
                )
            occurrence = occurrences.get(resolution.failure_id)
            if occurrence is None:
                raise PostDispatchReviewResolutionError(
                    "resolution references no valid occurrence"
                )
            _verify_resolution_link(resolution, occurrence)
            results.append(
                PersistedPostDispatchReviewResolution(
                    root,
                    work_ref,
                    resolution,
                    path,
                    path.relative_to(root).as_posix(),
                )
            )
        except (
            OSError,
            UnicodeError,
            ValueError,
            QuillanWorkPathError,
            PostDispatchReviewResolutionError,
        ) as error:
            warnings.append(f"Skipped malformed resolution {path.name}: {error}")
    return tuple(results), tuple(warnings)


def _retry_provenance_was_used(
    root: Path,
    work_ref: ModuleWorkRef,
    provenance: Mapping[str, object],
) -> bool:
    """Conservatively prevent one current retry proof authorizing two records."""
    try:
        occurrence_discovery = discover_post_dispatch_review_occurrences(
            root, work_ref
        )
    except PostDispatchReviewError as error:
        raise PostDispatchReviewResolutionError(str(error)) from error
    occurrences = {
        item.occurrence.failure_id: item for item in occurrence_discovery.items
    }
    resolutions, warnings = _discover_resolutions(root, work_ref, occurrences)
    if warnings:
        raise PostDispatchReviewResolutionError(
            "Could not verify retry-proof uniqueness: " + "; ".join(warnings)
        )
    expected = dict(_validated_retry_provenance(provenance))
    return any(
        persisted.resolution.retry_provenance is not None
        and dict(persisted.resolution.retry_provenance) == expected
        for persisted in resolutions
    )


def _write_resolution(
    root: Path,
    work_ref: ModuleWorkRef,
    occurrence: PersistedPostDispatchReviewOccurrence,
    expected_occurrence_bytes: bytes,
    resolution: PostDispatchReviewResolution,
) -> PersistedPostDispatchReviewResolution:
    relative_directory = Path("scans") / "review" / "post_dispatch" / "resolutions"
    if type(expected_occurrence_bytes) is not bytes:
        raise PostDispatchReviewResolutionError(
            "Expected occurrence revision must be exact bytes."
        )
    try:
        directory = preflight_work_directory_destination(
            root, work_ref, relative_directory
        )
        directory.mkdir(parents=True, exist_ok=True)
        preflight_work_directory_destination(root, work_ref, relative_directory)
    except (OSError, QuillanWorkPathError) as error:
        raise PostDispatchReviewResolutionError(str(error)) from error
    path = post_dispatch_resolution_path(root, work_ref, resolution.resolution_id)
    data = _resolution_bytes(resolution)

    def preflight() -> None:
        if canonical_workspace_root(root) != root:
            raise PostDispatchReviewResolutionError(
                "Workspace root identity changed."
            )
        current_directory = preflight_work_directory_destination(
            root, work_ref, relative_directory
        )
        if current_directory != directory:
            raise PostDispatchReviewResolutionError(
                "Resolution directory identity changed."
            )
        expected_occurrence_path = post_dispatch_review_path(
            root, work_ref, occurrence.occurrence.failure_id
        )
        if occurrence.path != expected_occurrence_path:
            raise PostDispatchReviewResolutionError(
                "Occurrence path identity changed."
            )
        checked_occurrence_path = preflight_work_file_destination(
            root,
            work_ref,
            Path("scans")
            / "review"
            / "post_dispatch"
            / expected_occurrence_path.name,
        )
        if checked_occurrence_path != expected_occurrence_path:
            raise PostDispatchReviewResolutionError(
                "Occurrence path preflight returned a different path."
            )
        if (
            not os.path.lexists(expected_occurrence_path)
            or _is_link_like(expected_occurrence_path)
            or not expected_occurrence_path.is_file()
        ):
            raise PostDispatchReviewResolutionError(
                "Occurrence must remain an ordinary non-link file."
            )
        try:
            current_occurrence_bytes = expected_occurrence_path.read_bytes()
        except OSError as error:
            raise PostDispatchReviewResolutionError(
                f"Could not re-read immutable occurrence: {error}"
            ) from error
        if current_occurrence_bytes != expected_occurrence_bytes:
            raise PostDispatchReviewResolutionError(
                "Immutable occurrence changed after it was loaded."
            )
        checked_target = preflight_work_file_destination(
            root, work_ref, relative_directory / path.name
        )
        if checked_target != path:
            raise PostDispatchReviewResolutionError(
                "Resolution target preflight returned a different path."
            )

    try:
        create_exclusive_record(
            path,
            data,
            preflight=preflight,
            verify_bytes=lambda value: _verify_resolution_bytes(
                value, resolution, occurrence
            ),
        )
    except AtomicRecordConcurrencyError as error:
        raise PostDispatchReviewResolutionError(
            f"Resolution ID already exists: {resolution.resolution_id}"
        ) from error
    except AtomicRecordDurabilityError as error:
        raise PostDispatchReviewResolutionError(
            str(error),
            possibly_durable_path=error.possibly_durable_path,
            possible_lock_path=error.possible_lock_path,
        ) from error
    except (AtomicRecordError, OSError, QuillanWorkPathError) as error:
        raise PostDispatchReviewResolutionError(
            f"Could not persist post-dispatch resolution: {error}"
        ) from error
    return PersistedPostDispatchReviewResolution(
        root,
        work_ref,
        resolution,
        path,
        path.relative_to(root).as_posix(),
    )


def _verify_resolution_bytes(
    data: bytes,
    expected: PostDispatchReviewResolution,
    occurrence: PersistedPostDispatchReviewOccurrence,
) -> None:
    loaded = _resolution_from_bytes(data)
    if loaded != expected:
        raise PostDispatchReviewResolutionError(
            "Persisted resolution bytes do not equal the requested resolution."
        )
    _verify_resolution_link(loaded, occurrence)


def _verify_resolution_link(
    resolution: PostDispatchReviewResolution,
    occurrence: PersistedPostDispatchReviewOccurrence,
) -> None:
    occurrence_bytes = _read_occurrence_revision(
        occurrence.workspace_root,
        occurrence.work_ref,
        occurrence,
    )
    if (
        resolution.failure_id != occurrence.occurrence.failure_id
        or resolution.occurrence_path != occurrence.relative_path
        or resolution.class_id != occurrence.occurrence.class_id
        or resolution.assignment_id != occurrence.occurrence.assignment_id
        or dict(resolution.occurrence_identity_snapshot)
        != _frozen_mapping(
            _occurrence_snapshot(occurrence, occurrence_bytes),
            "occurrence_identity_snapshot",
            max_keys=16,
        )
    ):
        raise PostDispatchReviewResolutionError(
            "Resolution does not match the immutable occurrence identity."
        )
    if datetime.fromisoformat(resolution.resolved_at) < datetime.fromisoformat(
        occurrence.occurrence.created_at
    ):
        raise PostDispatchReviewResolutionError(
            "Resolution predates its immutable occurrence."
        )


def _occurrence_snapshot(
    occurrence: PersistedPostDispatchReviewOccurrence,
    occurrence_bytes: bytes,
) -> dict[str, object]:
    item = occurrence.occurrence
    return {
        "failure_id": item.failure_id,
        "category": item.category,
        "stage": item.stage,
        "created_at": item.created_at,
        "class_id": item.class_id,
        "assignment_id": item.assignment_id,
        "student_id": item.student_id,
        "issuance_ids": list(item.issuance_ids),
        "page_ids": list(item.page_ids),
        "route_ids": list(item.route_ids),
        "observation_ids": list(item.observation_ids),
        "source_scan_ids": list(item.source_scan_ids),
        "source_page_numbers": list(item.source_page_numbers),
        "occurrence_sha256": hashlib.sha256(occurrence_bytes).hexdigest(),
    }


def _read_occurrence_revision(
    root: Path,
    work_ref: ModuleWorkRef,
    occurrence: PersistedPostDispatchReviewOccurrence,
) -> bytes:
    if type(occurrence) is not PersistedPostDispatchReviewOccurrence:
        raise PostDispatchReviewResolutionError(
            "Selected occurrence has the wrong runtime type."
        )
    expected_path = post_dispatch_review_path(
        root, work_ref, occurrence.occurrence.failure_id
    )
    if occurrence.path != expected_path:
        raise PostDispatchReviewResolutionError(
            "Selected occurrence path is not its exact canonical path."
        )
    try:
        checked_path = preflight_work_file_destination(
            root,
            work_ref,
            Path("scans") / "review" / "post_dispatch" / expected_path.name,
        )
        if checked_path != expected_path:
            raise PostDispatchReviewResolutionError(
                "Occurrence preflight returned a different path."
            )
        if (
            not os.path.lexists(expected_path)
            or _is_link_like(expected_path)
            or not expected_path.is_file()
        ):
            raise PostDispatchReviewResolutionError(
                "Occurrence must be an ordinary non-link file."
            )
        current_bytes = expected_path.read_bytes()
        if current_bytes != occurrence.original_bytes:
            raise PostDispatchReviewResolutionError(
                "Immutable occurrence changed after discovery."
            )
        return current_bytes
    except (OSError, QuillanWorkPathError) as error:
        raise PostDispatchReviewResolutionError(
            f"Could not reload immutable occurrence: {error}"
        ) from error


def _resolution_bytes(resolution: PostDispatchReviewResolution) -> bytes:
    value = {
        "schema_version": POST_DISPATCH_RESOLUTION_SCHEMA_VERSION,
        "record_type": POST_DISPATCH_RESOLUTION_RECORD_TYPE,
        "module_id": QUILLAN_MODULE_ID,
        "resolution_id": resolution.resolution_id,
        "failure_id": resolution.failure_id,
        "occurrence_path": resolution.occurrence_path,
        "class_id": resolution.class_id,
        "assignment_id": resolution.assignment_id,
        "status": resolution.status,
        "action": resolution.action,
        "resolved_at": resolution.resolved_at,
        "teacher_message": resolution.teacher_message,
        "occurrence_identity_snapshot": _thaw(
            resolution.occurrence_identity_snapshot
        ),
        "module_details": _thaw(resolution.module_details),
        "retry_provenance": (
            None
            if resolution.retry_provenance is None
            else _thaw(resolution.retry_provenance)
        ),
    }
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def _resolution_from_bytes(data: bytes) -> PostDispatchReviewResolution:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise PostDispatchReviewResolutionError(
                    f"Duplicate JSON key: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                PostDispatchReviewResolutionError(
                    f"Invalid JSON constant: {value}"
                )
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PostDispatchReviewResolutionError(
            f"Resolution is not strict JSON: {error}"
        ) from error
    if type(value) is not dict or set(value) != _RESOLUTION_FIELDS:
        raise PostDispatchReviewResolutionError("Resolution fields are not exact.")
    mapping = cast(dict[str, Any], value)
    if (
        mapping["schema_version"] != POST_DISPATCH_RESOLUTION_SCHEMA_VERSION
        or mapping["record_type"] != POST_DISPATCH_RESOLUTION_RECORD_TYPE
        or mapping["module_id"] != QUILLAN_MODULE_ID
    ):
        raise PostDispatchReviewResolutionError(
            "Resolution fixed identity is invalid."
        )
    return PostDispatchReviewResolution(
        resolution_id=mapping["resolution_id"],
        failure_id=mapping["failure_id"],
        occurrence_path=mapping["occurrence_path"],
        class_id=mapping["class_id"],
        assignment_id=mapping["assignment_id"],
        status=mapping["status"],
        action=mapping["action"],
        resolved_at=mapping["resolved_at"],
        teacher_message=mapping["teacher_message"],
        occurrence_identity_snapshot=mapping["occurrence_identity_snapshot"],
        module_details=mapping["module_details"],
        retry_provenance=_historical_retry_provenance_from_value(
            mapping["retry_provenance"]
        ),
    )


def _validate_possible_manifest(
    path: Path,
    occurrence: PostDispatchReviewOccurrence,
) -> None:
    try:
        manifest = load_submission_manifest(path)
    except (OSError, SubmissionManifestError) as error:
        raise PostDispatchReviewResolutionError(
            f"Possible manifest is not a valid submission manifest: {error}"
        ) from error
    if (
        manifest.get("class_id") != occurrence.class_id
        or manifest.get("assignment_id") != occurrence.assignment_id
        or occurrence.student_id is None
        or manifest.get("student_id") != occurrence.student_id
    ):
        raise PostDispatchReviewResolutionError(
            "Possible manifest identity disagrees with the occurrence."
        )


def _validate_possible_evidence(
    root: Path,
    work_ref: ModuleWorkRef,
    relative_path: str,
    occurrence: PostDispatchReviewOccurrence,
) -> None:
    matching_observations = []
    try:
        for observation_id in occurrence.observation_ids:
            observation = load_contextual_response_page_observation(
                root, work_ref, observation_id
            )
            if observation.routed_evidence_path == relative_path:
                matching_observations.append(observation)
    except (OSError, QuillanObservationError) as error:
        raise PostDispatchReviewResolutionError(
            f"Could not validate possible evidence metadata: {error}"
        ) from error
    if len(matching_observations) != 1:
        raise PostDispatchReviewResolutionError(
            "Possible evidence has no unique immutable observation validator."
        )
    observation = matching_observations[0]
    extension = PurePosixPath(relative_path).suffix
    try:
        verify_contextual_routed_page_evidence(
            root,
            work_ref,
            issuance_id=observation.issuance_id,
            student_id=observation.student_id,
            logical_page=observation.logical_page,
            observation_id=observation.observation_id,
            extension=extension,
            relative_path=relative_path,
            expected_sha256=observation.routed_evidence_sha256,
            expected_size_bytes=observation.routed_evidence_size_bytes,
        )
    except (OSError, QuillanObservationError) as error:
        raise PostDispatchReviewResolutionError(
            f"Possible evidence failed routed-evidence validation: {error}"
        ) from error


def _context(
    workspace_root: str | Path, work_ref: ModuleWorkRef
) -> tuple[Path, ModuleWorkRef]:
    try:
        root = canonical_workspace_root(workspace_root)
        canonical_ref = quillan_work_ref(work_ref.class_id, work_ref.work_id)
    except (AttributeError, OSError, TypeError, ValueError) as error:
        raise PostDispatchReviewResolutionError(str(error)) from error
    if type(work_ref) is not ModuleWorkRef or work_ref != canonical_ref:
        raise PostDispatchReviewResolutionError(
            "work_ref must be an exact Quillan work reference."
        )
    return root, canonical_ref


def _message(action: str, value: str | None) -> str | None:
    if value is None:
        if action == "other":
            raise PostDispatchReviewResolutionError(
                "The other action requires a nonblank teacher message."
            )
        return None
    if type(value) is not str or not value.strip():
        raise PostDispatchReviewResolutionError(
            "teacher message must be nonblank text when supplied."
        )
    return value.strip()


def _resolution_order(
    item: PersistedPostDispatchReviewResolution,
) -> tuple[datetime, str]:
    return datetime.fromisoformat(item.resolution.resolved_at), item.resolution.resolution_id


def _timestamp(value: datetime | str | None, field: str) -> str:
    selected: datetime | str = datetime.now(timezone.utc) if value is None else value
    if type(selected) is datetime:
        if selected.tzinfo is None or selected.utcoffset() is None:
            raise PostDispatchReviewResolutionError(
                f"{field} must be timezone-aware."
            )
        return selected.astimezone(timezone.utc).isoformat(timespec="microseconds")
    if type(selected) is not str:
        raise PostDispatchReviewResolutionError(f"{field} must be timestamp text.")
    try:
        parsed = datetime.fromisoformat(selected)
    except ValueError as error:
        raise PostDispatchReviewResolutionError(
            f"{field} must be ISO 8601 text."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PostDispatchReviewResolutionError(
            f"{field} must be timezone-aware."
        )
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _identifier(value: object, field: str) -> str:
    if type(value) is not str:
        raise PostDispatchReviewResolutionError(
            f"{field} must be exact identifier text."
        )
    try:
        return validate_identifier(value, field)
    except ValueError as error:
        raise PostDispatchReviewResolutionError(str(error)) from error


def _identifier_tuple(value: object, field: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise PostDispatchReviewResolutionError(f"{field} must be an exact tuple.")
    values = cast(tuple[object, ...], value)
    for item in values:
        _identifier(item, field.removesuffix("s"))
    typed_values = cast(tuple[str, ...], values)
    if typed_values != tuple(sorted(set(typed_values))):
        raise PostDispatchReviewResolutionError(
            f"{field} must be deterministic and unique."
        )
    return typed_values


def _relative_posix(value: object, field: str) -> str:
    if (
        type(value) is not str
        or not value
        or "\\" in value
        or value.startswith("/")
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise PostDispatchReviewResolutionError(
            f"{field} must be canonical workspace-relative POSIX text."
        )
    return value


def _frozen_mapping(
    value: object, field: str, *, max_keys: int
) -> Mapping[str, object]:
    if type(value) is not dict and not isinstance(value, Mapping):
        raise PostDispatchReviewResolutionError(f"{field} must be an object.")
    mapping = dict(cast(Mapping[str, object], value))
    if len(mapping) > max_keys or any(type(key) is not str for key in mapping):
        raise PostDispatchReviewResolutionError(f"{field} is not bounded.")
    try:
        serialized = json.dumps(
            _thaw(mapping), allow_nan=False, sort_keys=True
        )
    except (TypeError, ValueError) as error:
        raise PostDispatchReviewResolutionError(
            f"{field} must contain strict JSON."
        ) from error
    if len(serialized.encode("utf-8")) > 16_384:
        raise PostDispatchReviewResolutionError(f"{field} is too large.")
    return cast(Mapping[str, object], _freeze_json(mapping, field))


def _freeze_json(value: object, field: str) -> object:
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str or key in frozen:
                raise PostDispatchReviewResolutionError(
                    f"{field} contains an invalid object key."
                )
            frozen[key] = _freeze_json(item, field)
        return MappingProxyType(frozen)
    if type(value) in {list, tuple}:
        values = cast(list[object] | tuple[object, ...], value)
        return tuple(_freeze_json(item, field) for item in values)
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        if value != value or abs(value) == float("inf"):
            raise PostDispatchReviewResolutionError(
                f"{field} must contain strict JSON."
            )
        return value
    raise PostDispatchReviewResolutionError(f"{field} must contain strict JSON.")


def _validate_occurrence_snapshot(
    resolution: PostDispatchReviewResolution,
) -> None:
    snapshot = resolution.occurrence_identity_snapshot
    if set(snapshot) != _OCCURRENCE_SNAPSHOT_FIELDS:
        raise PostDispatchReviewResolutionError(
            "Occurrence identity snapshot fields are not exact."
        )
    if (
        snapshot["failure_id"] != resolution.failure_id
        or snapshot["class_id"] != resolution.class_id
        or snapshot["assignment_id"] != resolution.assignment_id
    ):
        raise PostDispatchReviewResolutionError(
            "Occurrence snapshot disagrees with resolution identity."
        )
    _identifier(snapshot["failure_id"], "failure_id")
    _identifier(snapshot["class_id"], "class_id")
    _identifier(snapshot["assignment_id"], "assignment_id")
    student_id = snapshot["student_id"]
    if student_id is not None:
        _identifier(student_id, "student_id")
    for field in (
        "issuance_ids",
        "page_ids",
        "route_ids",
        "observation_ids",
        "source_scan_ids",
    ):
        _identifier_tuple(snapshot[field], field)
    page_numbers = snapshot["source_page_numbers"]
    if type(page_numbers) is not tuple or any(
        type(item) is not int or item < 1 for item in page_numbers
    ):
        raise PostDispatchReviewResolutionError(
            "source_page_numbers must contain exact positive integers."
        )
    typed_page_numbers = cast(tuple[int, ...], page_numbers)
    if typed_page_numbers != tuple(sorted(set(typed_page_numbers))):
        raise PostDispatchReviewResolutionError(
            "source_page_numbers must be deterministic and unique."
        )
    category = snapshot["category"]
    if type(category) is not str or category not in POST_DISPATCH_CATEGORIES:
        raise PostDispatchReviewResolutionError(
            "Occurrence snapshot category is invalid."
        )
    for field in ("stage",):
        value = snapshot[field]
        if type(value) is not str or not value or value != value.strip():
            raise PostDispatchReviewResolutionError(
                f"Occurrence snapshot {field} is invalid."
            )
    created_at = snapshot["created_at"]
    if type(created_at) is not str or _timestamp(created_at, "created_at") != created_at:
        raise PostDispatchReviewResolutionError(
            "Occurrence snapshot timestamp is not normalized UTC text."
        )
    digest = snapshot["occurrence_sha256"]
    if (
        type(digest) is not str
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise PostDispatchReviewResolutionError(
            "Occurrence snapshot SHA-256 is invalid."
        )
    if resolution.retry_provenance is not None:
        provenance = resolution.retry_provenance
        occurrence_issuances = cast(tuple[str, ...], snapshot["issuance_ids"])
        if student_id is not None and provenance["student_id"] != student_id:
            raise PostDispatchReviewResolutionError(
                "Retry provenance disagrees with the occurrence identity snapshot."
            )
        provenance_issuances = cast(tuple[str, ...], provenance["issuance_ids"])
        if occurrence_issuances and not set(provenance_issuances).issubset(
            occurrence_issuances
        ):
            raise PostDispatchReviewResolutionError(
                "Retry provenance disagrees with the occurrence identity snapshot."
            )


def _validated_retry_provenance(
    value: Mapping[str, object],
) -> Mapping[str, object]:
    if set(value) != _RETRY_PROVENANCE_FIELDS:
        raise PostDispatchReviewResolutionError(
            "Retry provenance fields are not exact."
        )
    if value["operation"] != "submission_assembly":
        raise PostDispatchReviewResolutionError("Retry operation is invalid.")
    class_id = _identifier(value["class_id"], "class_id")
    assignment_id = _identifier(value["assignment_id"], "assignment_id")
    student_id = _identifier(value["student_id"], "student_id")
    issuance_ids_value = value["issuance_ids"]
    if type(issuance_ids_value) not in {list, tuple}:
        raise PostDispatchReviewResolutionError(
            "Retry provenance issuance_ids must be an array."
        )
    issuance_ids = tuple(cast(list[str] | tuple[str, ...], issuance_ids_value))
    _identifier_tuple(issuance_ids, "issuance_ids")
    if len(issuance_ids) != 1:
        raise PostDispatchReviewResolutionError(
            "Retry provenance requires one assembled issuance."
        )
    assembled_status = value["assembled_status"]
    if assembled_status not in {"created", "updated", "unchanged"}:
        raise PostDispatchReviewResolutionError("Assembled retry status is invalid.")
    manifest_path = value["manifest_path"]
    _relative_posix(manifest_path, "manifest_path")
    expected_manifest_path = submission_manifest_path(
        Path(),
        quillan_work_ref(class_id, assignment_id),
        student_id,
    ).as_posix()
    if manifest_path != expected_manifest_path:
        raise PostDispatchReviewResolutionError(
            "Retry manifest_path is not the canonical student manifest path."
        )
    assembly_revision = value["assembly_revision"]
    if (
        isinstance(assembly_revision, bool)
        or not isinstance(assembly_revision, int)
        or assembly_revision < 1
    ):
        raise PostDispatchReviewResolutionError(
            "Retry assembly_revision must be a positive integer."
        )
    completed_at = value["completed_at"]
    if type(completed_at) is not str:
        raise PostDispatchReviewResolutionError(
            "Retry completion timestamp must be normalized UTC text."
        )
    if _timestamp(completed_at, "completed_at") != completed_at:
        raise PostDispatchReviewResolutionError(
            "Retry completion timestamp must be normalized UTC text."
        )
    return MappingProxyType(
        {
            "operation": "submission_assembly",
            "class_id": class_id,
            "assignment_id": assignment_id,
            "student_id": student_id,
            "issuance_ids": issuance_ids,
            "assembled_status": assembled_status,
            "manifest_path": manifest_path,
            "assembly_revision": assembly_revision,
            "completed_at": completed_at,
        }
    )


def _historical_retry_provenance_from_value(
    value: object,
) -> Mapping[str, object] | None:
    if value is None:
        return None
    if type(value) is not dict or set(value) != _RETRY_PROVENANCE_FIELDS:
        raise PostDispatchReviewResolutionError(
            "Retry provenance fields are not exact."
        )
    mapping = cast(dict[str, object], value)
    issuance_ids = mapping["issuance_ids"]
    if type(issuance_ids) is not list:
        raise PostDispatchReviewResolutionError(
            "Retry provenance issuance_ids must be an array."
        )
    normalized = dict(mapping)
    normalized["issuance_ids"] = tuple(cast(list[str], issuance_ids))
    return _validated_retry_provenance(normalized)


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


__all__ = [
    "POST_DISPATCH_GENERIC_RESOLUTION_ACTIONS",
    "POST_DISPATCH_RESOLUTION_ACTIONS",
    "POST_DISPATCH_RESOLUTION_RECORD_TYPE",
    "POST_DISPATCH_RESOLUTION_SCHEMA_VERSION",
    "POST_DISPATCH_RESOLUTION_STATUSES",
    "OpenedPostDispatchPossiblePath",
    "PersistedPostDispatchReviewResolution",
    "PostDispatchReviewItem",
    "PostDispatchReviewResolution",
    "PostDispatchReviewResolutionDiscovery",
    "PostDispatchReviewResolutionError",
    "discover_post_dispatch_review_items",
    "open_post_dispatch_possible_path",
    "post_dispatch_retry_proves_resolution",
    "resolve_post_dispatch_after_successful_retry",
    "resolve_post_dispatch_review_item",
    "resolve_post_dispatch_review_occurrence",
]

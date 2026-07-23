"""Issuance-authoritative assembly of observation-backed submissions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal, Mapping, cast

from pds_core.route_registrations import (
    RouteRegistrationPersistenceError,
    load_route_registration,
)
from pds_core.identifiers import validate_identifier
from pds_core.routing_models import PDS2_SCHEMA, RouteLocator

from quillan._path_safety import is_link_like as _shared_is_link_like
from quillan.module_errors import (
    QuillanCategorizedAssemblyError,
    QuillanObservationDiscoveryError,
    QuillanSubmissionObservationAssemblyError,
)
from quillan.plain_paper_submission import is_plain_paper_submission
from quillan.printable_response_persistence import (
    PrintableResponseNotFoundError,
    PrintableResponsePersistenceError,
    load_printable_response_record_set,
)
from quillan.printable_response_records import (
    PrintableResponsePage,
    PrintableResponseRecordSet,
    PrintableResponseRecordValidationError,
    validate_printable_response_record_set,
    validate_issuance_id,
    validate_page_id,
    response_page_target,
)
from quillan.printable_response_routes import printable_response_module_details
from quillan.response_page_observation_persistence import (
    QuillanObservationPersistenceBatch,
)
from quillan.response_page_observations import (
    QuillanResponsePageObservation,
    list_quillan_page_observations,
    validate_observation_id,
)
from quillan.record_context import (
    QuillanRecordContextError,
    QuillanStudentReviewContext,
    ReviewLoadingPolicy,
    load_quillan_assignment_context,
    load_quillan_student_review_context,
    mutable_json_copy,
)
from quillan.submission_manifest import (
    PDS2_SUBMISSION_ENTRY_METHOD,
    SubmissionManifestError,
    validate_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestConcurrencyError,
    SubmissionManifestPathError,
    create_quillan_submission_manifest,
    submission_manifest_path,
    update_quillan_submission_manifest,
)
from quillan.work_paths import quillan_work_ref

ASSEMBLY_FAILURE_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "observation_invalid",
        "observation_missing_evidence",
        "observation_evidence_hash_mismatch",
        "issuance_not_found",
        "issuance_invalid",
        "issuance_not_issued",
        "unexpected_page",
        "identity_conflict",
        "route_conflict",
        "source_page_conflict",
        "mixed_issuances",
        "existing_manifest_issuance_conflict",
        "existing_plain_paper_submission",
        "existing_manifest_invalid",
        "manifest_concurrency_conflict",
        "manifest_write_failed",
        "unexpected_error",
    }
)


@dataclass(frozen=True, slots=True)
class QuillanSubmissionAssemblyFailure:
    category: str
    class_id: str
    assignment_id: str
    student_id: str | None
    issuance_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    page_ids: tuple[str, ...]
    logical_pages: tuple[int, ...]
    source_scan_ids: tuple[str, ...]
    source_page_numbers: tuple[int, ...]
    reason: str
    error: Exception | None = None
    possible_manifest_path: Path | None = None

    def __post_init__(self) -> None:
        if (
            type(self.category) is not str
            or self.category not in ASSEMBLY_FAILURE_CATEGORIES
        ):
            raise ValueError("Unsupported submission assembly failure category.")
        validate_identifier(self.class_id, "class_id")
        validate_identifier(self.assignment_id, "assignment_id")
        if self.student_id is not None:
            validate_identifier(self.student_id, "student_id")
        _validated_tuple(self.issuance_ids, validate_issuance_id, "issuance_ids")
        _validated_tuple(
            self.observation_ids, validate_observation_id, "observation_ids"
        )
        _validated_tuple(
            self.page_ids, validate_page_id, "page_ids", require_unique=False
        )
        _positive_integer_tuple(
            self.logical_pages, "logical_pages", require_unique=False
        )
        _validated_tuple(
            self.source_scan_ids,
            lambda value: validate_identifier(value, "source_scan_id"),
            "source_scan_ids",
            require_unique=False,
        )
        _positive_integer_tuple(
            self.source_page_numbers,
            "source_page_numbers",
            require_unique=False,
        )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be nonempty text.")
        if self.error is not None and not isinstance(self.error, Exception):
            raise ValueError("error must be an Exception or None.")
        if self.possible_manifest_path is not None:
            _absolute_canonical_path(
                self.possible_manifest_path, "possible_manifest_path"
            )


@dataclass(frozen=True, slots=True)
class AssembledQuillanSubmission:
    workspace_root: Path
    class_id: str
    assignment_id: str
    student_id: str
    issuance_id: str
    manifest_path: Path
    manifest_relative_path: str
    status: Literal["created", "updated", "unchanged"]
    assembly_revision: int
    missing_pages: tuple[int, ...]
    duplicate_pages: tuple[int, ...]
    needs_rescan_pages: tuple[int, ...]
    excluded_pages: tuple[int, ...]
    observation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        root = _absolute_canonical_path(self.workspace_root, "workspace_root")
        if _is_link_like(root) or not root.is_dir():
            raise ValueError("workspace_root must be an ordinary non-link directory.")
        validate_identifier(self.class_id, "class_id")
        validate_identifier(self.assignment_id, "assignment_id")
        validate_identifier(self.student_id, "student_id")
        validate_issuance_id(self.issuance_id)
        _absolute_canonical_path(self.manifest_path, "manifest_path")
        _relative_posix(self.manifest_relative_path, "manifest_relative_path")
        try:
            actual_relative = self.manifest_path.relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError("manifest_path must be contained by workspace_root.") from error
        if self.manifest_relative_path != actual_relative:
            raise ValueError("Manifest relative and absolute paths disagree.")
        expected_manifest_path = submission_manifest_path(
            root, self.class_id, self.assignment_id, self.student_id
        )
        if self.manifest_path != expected_manifest_path:
            raise ValueError("manifest_path is not the canonical student destination.")
        if self.status not in {"created", "updated", "unchanged"}:
            raise ValueError("Unsupported assembled submission status.")
        _positive_integer(self.assembly_revision, "assembly_revision")
        state_pages = (
            self.missing_pages,
            self.duplicate_pages,
            self.needs_rescan_pages,
            self.excluded_pages,
        )
        for index, values in enumerate(state_pages):
            _positive_integer_tuple(values, f"page_state_tuple[{index}]")
        flattened = tuple(value for values in state_pages for value in values)
        if len(set(flattened)) != len(flattened):
            raise ValueError("Page-state summary tuples must be disjoint.")
        _validated_tuple(
            self.observation_ids, validate_observation_id, "observation_ids"
        )


@dataclass(frozen=True, slots=True)
class QuillanSubmissionAssemblyBatch:
    assembled: tuple[AssembledQuillanSubmission, ...]
    failures: tuple[QuillanSubmissionAssemblyFailure, ...]

    def __post_init__(self) -> None:
        if type(self.assembled) is not tuple or type(self.failures) is not tuple:
            raise ValueError("Assembly result collections must be tuples.")
        if any(type(item) is not AssembledQuillanSubmission for item in self.assembled):
            raise ValueError("assembled members have the wrong type.")
        if any(
            type(item) is not QuillanSubmissionAssemblyFailure for item in self.failures
        ):
            raise ValueError("failure members have the wrong type.")
        targets = tuple(
            (item.class_id, item.assignment_id, item.student_id, item.issuance_id)
            for item in self.assembled
        )
        if len(set(targets)) != len(targets):
            raise ValueError("Assembled student/issuance targets must be unique.")
        assembled_keys = tuple(_assembled_sort_key(item) for item in self.assembled)
        if assembled_keys != tuple(sorted(assembled_keys)):
            raise ValueError("Assembled results must be deterministically ordered.")
        if any(
            item == earlier
            for index, item in enumerate(self.failures)
            for earlier in self.failures[:index]
        ):
            raise ValueError("Failure members must not be duplicated.")
        failure_occurrences = tuple(
            _failure_occurrence_key(item) for item in self.failures
        )
        if len(set(failure_occurrences)) != len(failure_occurrences):
            raise ValueError("Failure occurrence keys must be unique.")
        failure_keys = tuple(_failure_sort_key(item) for item in self.failures)
        if failure_keys != tuple(sorted(failure_keys)):
            raise ValueError("Assembly failures must be deterministically ordered.")
        failed_targets = {
            (item.class_id, item.assignment_id, item.student_id, issuance_id)
            for item in self.failures
            if item.student_id is not None
            for issuance_id in item.issuance_ids
        }
        if set(targets) & failed_targets:
            raise ValueError(
                "A student/issuance target cannot be both assembled and failed."
            )

    @property
    def created_count(self) -> int:
        return sum(item.status == "created" for item in self.assembled)

    @property
    def updated_count(self) -> int:
        return sum(item.status == "updated" for item in self.assembled)

    @property
    def unchanged_count(self) -> int:
        return sum(item.status == "unchanged" for item in self.assembled)


def merge_submission_manifest_observations(
    existing_manifest: Mapping[str, object] | None,
    *,
    record_set: PrintableResponseRecordSet,
    observations: tuple[QuillanResponsePageObservation, ...],
    timestamp: datetime | str | None = None,
) -> dict[str, Any]:
    """Build or conservatively merge one complete issuance manifest."""
    try:
        validate_printable_response_record_set(record_set)
    except PrintableResponseRecordValidationError as error:
        raise QuillanSubmissionObservationAssemblyError(str(error)) from error
    if type(observations) is not tuple or any(
        type(item) is not QuillanResponsePageObservation for item in observations
    ):
        raise QuillanSubmissionObservationAssemblyError(
            "observations must be an exact immutable observation tuple."
        )
    ordered = tuple(sorted(observations, key=_observation_sort_key))
    _validate_observations_against_record_set(record_set, ordered)
    issuance = record_set.issuance
    now = _timestamp(timestamp)
    top_details = {
        "submission_entry_method": PDS2_SUBMISSION_ENTRY_METHOD,
        "response_issuance_id": issuance.issuance_id,
        "generation_id": issuance.generation_id,
        "artifact_id": issuance.artifact_id,
        "expected_page_ids": list(issuance.page_ids),
        "response_page_contract_version": "1",
        "page_observation_schema_version": "1",
        "assembly_revision": 1,
    }
    by_page = {
        page.page_id: tuple(item for item in ordered if item.page_id == page.page_id)
        for page in record_set.pages
    }
    if existing_manifest is None:
        manifest: dict[str, Any] = {
            "schema_version": "1",
            "module": "quillan",
            "record_type": "submission_manifest",
            "class_id": issuance.class_id,
            "assignment_id": issuance.assignment_id,
            "student_id": issuance.student_id,
            "expected_pages": issuance.page_count,
            "submission_state": "unreviewed",
            "pages": [
                _new_page(page, by_page[page.page_id]) for page in record_set.pages
            ],
            "created_at": now,
            "updated_at": now,
            "module_details": top_details,
        }
        validate_submission_manifest(manifest)
        return manifest

    if not isinstance(existing_manifest, Mapping):
        raise QuillanSubmissionObservationAssemblyError(
            "existing_manifest must be an object or None."
        )
    existing = deepcopy(dict(existing_manifest))
    try:
        validate_submission_manifest(existing)
    except SubmissionManifestError as error:
        raise QuillanSubmissionObservationAssemblyError(
            f"Existing manifest is invalid: {error}"
        ) from error
    if is_plain_paper_submission(existing):
        raise QuillanSubmissionObservationAssemblyError(
            "Existing plain-paper submissions cannot accept digital observations."
        )
    details = existing.get("module_details")
    if (
        not isinstance(details, dict)
        or details.get("submission_entry_method") != PDS2_SUBMISSION_ENTRY_METHOD
    ):
        raise QuillanSubmissionObservationAssemblyError(
            "Existing manifest is not a PDS2 observation-backed submission."
        )
    expected_identity = (
        issuance.class_id,
        issuance.assignment_id,
        issuance.student_id,
        issuance.issuance_id,
        issuance.generation_id,
        issuance.artifact_id,
        list(issuance.page_ids),
    )
    actual_identity = (
        existing.get("class_id"),
        existing.get("assignment_id"),
        existing.get("student_id"),
        details.get("response_issuance_id"),
        details.get("generation_id"),
        details.get("artifact_id"),
        details.get("expected_page_ids"),
    )
    if actual_identity != expected_identity:
        raise QuillanSubmissionObservationAssemblyError(
            "Existing manifest immutable issuance identity is contradictory."
        )
    observation_by_id = {item.observation_id: item for item in ordered}
    changed = False
    existing_pages = cast(list[dict[str, Any]], existing["pages"])
    for page_record, page in zip(record_set.pages, existing_pages, strict=True):
        existing_ids: set[str] = set()
        for evidence in page["evidence"]:
            evidence_id = evidence["evidence_id"]
            observation = observation_by_id.get(evidence_id)
            if observation is None:
                raise QuillanSubmissionObservationAssemblyError(
                    "Existing evidence has no matching persisted observation."
                )
            _validate_existing_evidence_projection(evidence, observation)
            existing_ids.add(evidence_id)
        new_observations = tuple(
            item
            for item in by_page[page_record.page_id]
            if item.observation_id not in existing_ids
        )
        if not new_observations:
            continue
        used_numbers = {
            item["duplicate_number"]
            for item in page["evidence"]
            if item["duplicate_number"] is not None
        }
        next_number = max(used_numbers, default=0) + 1
        for observation in new_observations:
            duplicate_number: int | None
            if not page["evidence"] and len(by_page[page_record.page_id]) == 1:
                duplicate_number = None
            else:
                while next_number in used_numbers:
                    next_number += 1
                duplicate_number = next_number
                used_numbers.add(next_number)
                next_number += 1
            page["evidence"].append(
                _evidence_from_observation(
                    observation,
                    duplicate_number=duplicate_number,
                    evidence_role="candidate",
                    evidence_state="active",
                )
            )
        if page["page_state"] not in {"needs_rescan", "excluded"}:
            if len(page["evidence"]) > 1:
                page["page_state"] = "duplicate"
            elif len(page["evidence"]) == 1:
                page["page_state"] = "present"
                if page["selected_evidence_id"] is None:
                    selected = page["evidence"][0]
                    selected["evidence_role"] = "selected"
                    page["selected_evidence_id"] = selected["evidence_id"]
        changed = True
    if not changed:
        return existing
    details["assembly_revision"] += 1
    existing["updated_at"] = now
    validate_submission_manifest(existing)
    return existing


def _assemble_submission_manifests_uncontained(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    *,
    observation_ids: tuple[str, ...] | None = None,
    timestamp: datetime | str | None = None,
) -> QuillanSubmissionAssemblyBatch:
    """Discover observations and independently assemble affected students."""
    root = Path(workspace_root)
    work_ref = quillan_work_ref(class_id, assignment_id)
    try:
        assignment_context = load_quillan_assignment_context(root, work_ref)
    except QuillanRecordContextError as error:
        return QuillanSubmissionAssemblyBatch(
            (),
            (
                _failure(
                    "identity_conflict",
                    class_id,
                    assignment_id,
                    None,
                    (),
                    f"Canonical assignment context failed: {error}",
                    error,
                ),
            ),
        )
    try:
        all_observations = list_quillan_page_observations(root, class_id, assignment_id)
    except QuillanObservationDiscoveryError as error:
        return QuillanSubmissionAssemblyBatch(
            (),
            (
                _failure(
                    error.category,
                    class_id,
                    assignment_id,
                    None,
                    (),
                    f"Observation discovery failed: {error}",
                    error.original_error,
                ),
            ),
        )
    if observation_ids is not None:
        if type(observation_ids) is not tuple:
            raise ValueError("observation_ids must be a tuple or None.")
        requested = {validate_observation_id(item) for item in observation_ids}
        discovered = {item.observation_id for item in all_observations}
        missing = requested - discovered
        if missing:
            request_error = QuillanSubmissionObservationAssemblyError(
                "Requested observations were not found: " + ", ".join(sorted(missing))
            )
            return QuillanSubmissionAssemblyBatch(
                (),
                (
                    _failure(
                        "observation_invalid",
                        class_id,
                        assignment_id,
                        None,
                        (),
                        str(request_error),
                        request_error,
                    ),
                ),
            )
        affected_students = {
            item.student_id
            for item in all_observations
            if item.observation_id in requested
        }
        observations = tuple(
            item for item in all_observations if item.student_id in affected_students
        )
    else:
        observations = all_observations
    by_student: dict[str, list[QuillanResponsePageObservation]] = {}
    for observation in observations:
        by_student.setdefault(observation.student_id, []).append(observation)
    assembled: list[AssembledQuillanSubmission] = []
    failures: list[QuillanSubmissionAssemblyFailure] = []
    for student_id in sorted(by_student):
        student_observations = tuple(
            sorted(by_student[student_id], key=_observation_sort_key)
        )
        issuance_ids = tuple(
            sorted({item.issuance_id for item in student_observations})
        )
        manifest_path = submission_manifest_path(
            root, class_id, assignment_id, student_id
        )
        existing: dict[str, Any] | None = None
        student_context: QuillanStudentReviewContext | None = None
        existing_issuance_id: str | None = None
        if os.path.lexists(manifest_path):
            try:
                student_context = load_quillan_student_review_context(
                    root,
                    work_ref,
                    student_id,
                    review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
                )
                existing = mutable_json_copy(student_context.submission)
            except (OSError, QuillanRecordContextError) as error:
                failures.append(
                    _failure(
                        "existing_manifest_invalid",
                        class_id,
                        assignment_id,
                        student_id,
                        student_observations,
                        str(error),
                        error,
                        manifest_path,
                    )
                )
                continue
            if is_plain_paper_submission(cast(dict[str, object], existing)):
                failures.append(
                    _failure(
                        "existing_plain_paper_submission",
                        class_id,
                        assignment_id,
                        student_id,
                        student_observations,
                        "Existing canonical manifest is a plain-paper submission.",
                        possible_manifest_path=manifest_path,
                    )
                )
                continue
            existing_details = existing.get("module_details")
            if (
                not isinstance(existing_details, dict)
                or existing_details.get("submission_entry_method")
                != PDS2_SUBMISSION_ENTRY_METHOD
            ):
                failures.append(
                    _failure(
                        "existing_manifest_invalid",
                        class_id,
                        assignment_id,
                        student_id,
                        student_observations,
                        "Existing digital manifest is not observation-backed PDS2 data.",
                        possible_manifest_path=manifest_path,
                    )
                )
                continue
            value = existing_details.get("response_issuance_id")
            existing_issuance_id = value if isinstance(value, str) else None
        if len(issuance_ids) != 1:
            category = (
                "existing_manifest_issuance_conflict"
                if existing_issuance_id is not None
                else "mixed_issuances"
            )
            failures.append(
                _failure(
                    category,
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    "Multiple immutable issuances target one canonical student manifest.",
                    possible_manifest_path=manifest_path,
                )
            )
            continue
        issuance_id = issuance_ids[0]
        if existing_issuance_id is not None and existing_issuance_id != issuance_id:
            failures.append(
                _failure(
                    "existing_manifest_issuance_conflict",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    "Existing digital manifest represents a different issuance.",
                    possible_manifest_path=manifest_path,
                )
            )
            continue
        try:
            record_set = load_printable_response_record_set(
                root,
                quillan_work_ref(class_id, assignment_id),
                issuance_id,
            )
        except PrintableResponseNotFoundError as error:
            failures.append(
                _failure(
                    "issuance_not_found",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    str(error),
                    error,
                )
            )
            continue
        except PrintableResponsePersistenceError as error:
            failures.append(
                _failure(
                    "issuance_invalid",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    str(error),
                    error,
                )
            )
            continue
        if record_set.issuance.lifecycle.status != "issued":
            failures.append(
                _failure(
                    "issuance_not_issued",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    "Authoritative issuance is not issued.",
                )
            )
            continue
        try:
            _validate_observations_against_record_set(record_set, student_observations)
        except QuillanCategorizedAssemblyError as error:
            failures.append(
                _failure(
                    error.category,
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    str(error),
                    error,
                )
            )
            continue
        except QuillanSubmissionObservationAssemblyError as error:
            failures.append(
                _failure(
                    "identity_conflict",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    str(error),
                    error,
                )
            )
            continue
        try:
            _validate_observation_routes(root, record_set, student_observations)
        except QuillanSubmissionObservationAssemblyError as error:
            failures.append(
                _failure(
                    "route_conflict",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    str(error),
                    error,
                )
            )
            continue
        try:
            merged = merge_submission_manifest_observations(
                existing,
                record_set=record_set,
                observations=student_observations,
                timestamp=timestamp,
            )
            if student_context is None:
                persisted = create_quillan_submission_manifest(
                    assignment_context,
                    student_id,
                    merged,
                )
            else:
                persisted = update_quillan_submission_manifest(
                    student_context,
                    merged,
                )
        except SubmissionManifestConcurrencyError as error:
            failures.append(
                _failure(
                    "manifest_concurrency_conflict",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    str(error),
                    error,
                    manifest_path,
                )
            )
            continue
        except QuillanCategorizedAssemblyError as error:
            failures.append(
                _failure(
                    error.category,
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    str(error),
                    error,
                    manifest_path,
                )
            )
            continue
        except QuillanSubmissionObservationAssemblyError as error:
            failures.append(
                _failure(
                    "identity_conflict",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    str(error),
                    error,
                    manifest_path,
                )
            )
            continue
        except (SubmissionManifestPathError, OSError) as error:
            failures.append(
                _failure(
                    "manifest_write_failed",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    str(error),
                    error,
                    manifest_path,
                )
            )
            continue
        assembled.append(
            _assembled(
                root, merged, persisted.status, manifest_path, student_observations
            )
        )
    return QuillanSubmissionAssemblyBatch(tuple(assembled), tuple(failures))


def _assemble_one_student(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    observations: tuple[QuillanResponsePageObservation, ...],
    *,
    timestamp: datetime | str | None,
) -> QuillanSubmissionAssemblyBatch:
    """Assemble one identified student, propagating unexpected exceptions."""
    validate_identifier(student_id, "student_id")
    if type(observations) is not tuple or not observations:
        raise ValueError("observations must be a nonempty tuple.")
    if any(
        type(item) is not QuillanResponsePageObservation
        or item.student_id != student_id
        for item in observations
    ):
        raise ValueError("observations must belong to the exact student.")
    return _assemble_submission_manifests_uncontained(
        workspace_root,
        class_id,
        assignment_id,
        observation_ids=tuple(item.observation_id for item in observations),
        timestamp=timestamp,
    )


def assemble_quillan_submission_manifests(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    *,
    observation_ids: tuple[str, ...] | None = None,
    timestamp: datetime | str | None = None,
) -> QuillanSubmissionAssemblyBatch:
    """Discover observations and independently contain each student's assembly."""
    root = Path(workspace_root)
    try:
        all_observations = list_quillan_page_observations(root, class_id, assignment_id)
    except QuillanObservationDiscoveryError as error:
        return QuillanSubmissionAssemblyBatch(
            (),
            (
                _failure(
                    error.category,
                    class_id,
                    assignment_id,
                    None,
                    (),
                    f"Observation discovery failed: {error}",
                    error.original_error,
                ),
            ),
        )
    if observation_ids is not None:
        if type(observation_ids) is not tuple:
            raise ValueError("observation_ids must be a tuple or None.")
        requested = {validate_observation_id(item) for item in observation_ids}
        discovered = {item.observation_id for item in all_observations}
        missing = requested - discovered
        if missing:
            request_error = QuillanSubmissionObservationAssemblyError(
                "Requested observations were not found: " + ", ".join(sorted(missing))
            )
            return QuillanSubmissionAssemblyBatch(
                (),
                (
                    _failure(
                        "observation_invalid",
                        class_id,
                        assignment_id,
                        None,
                        (),
                        str(request_error),
                        request_error,
                    ),
                ),
            )
        affected_students = {
            item.student_id
            for item in all_observations
            if item.observation_id in requested
        }
        observations = tuple(
            item for item in all_observations if item.student_id in affected_students
        )
    else:
        observations = all_observations
    by_student: dict[str, list[QuillanResponsePageObservation]] = {}
    for observation in observations:
        by_student.setdefault(observation.student_id, []).append(observation)
    assembled: list[AssembledQuillanSubmission] = []
    failures: list[QuillanSubmissionAssemblyFailure] = []
    for student_id in sorted(by_student):
        student_observations = tuple(
            sorted(by_student[student_id], key=_observation_sort_key)
        )
        try:
            result = _assemble_one_student(
                root,
                class_id,
                assignment_id,
                student_id,
                student_observations,
                timestamp=timestamp,
            )
        except Exception as error:
            failures.append(
                _failure(
                    "unexpected_error",
                    class_id,
                    assignment_id,
                    student_id,
                    student_observations,
                    f"Unexpected assembly failure for {student_id}: {error}",
                    error,
                )
            )
            continue
        assembled.extend(result.assembled)
        failures.extend(result.failures)
    return QuillanSubmissionAssemblyBatch(tuple(assembled), tuple(failures))


def assemble_quillan_scan_observations(
    workspace_root: Path,
    persistence_batch: QuillanObservationPersistenceBatch,
    *,
    timestamp: datetime | str | None = None,
) -> QuillanSubmissionAssemblyBatch:
    """Assemble students affected by one observation persistence batch."""
    if type(persistence_batch) is not QuillanObservationPersistenceBatch:
        raise ValueError("persistence_batch has the wrong type.")
    created_or_existing = persistence_batch.persisted
    if not created_or_existing:
        return QuillanSubmissionAssemblyBatch((), ())
    works = {
        (item.observation.class_id, item.observation.assignment_id)
        for item in created_or_existing
    }
    assembled: list[AssembledQuillanSubmission] = []
    failures: list[QuillanSubmissionAssemblyFailure] = []
    for class_id, assignment_id in sorted(works):
        ids = tuple(
            item.observation.observation_id
            for item in created_or_existing
            if (
                item.observation.class_id,
                item.observation.assignment_id,
            )
            == (class_id, assignment_id)
        )
        try:
            result = assemble_quillan_submission_manifests(
                workspace_root,
                class_id,
                assignment_id,
                observation_ids=ids,
                timestamp=timestamp,
            )
        except Exception as error:
            related = tuple(
                item.observation
                for item in created_or_existing
                if (
                    item.observation.class_id,
                    item.observation.assignment_id,
                )
                == (class_id, assignment_id)
            )
            failures.append(
                _failure(
                    "unexpected_error",
                    class_id,
                    assignment_id,
                    None,
                    related,
                    f"Unexpected assembly failure: {error}",
                    error,
                )
            )
            continue
        assembled.extend(result.assembled)
        failures.extend(result.failures)
    return QuillanSubmissionAssemblyBatch(tuple(assembled), tuple(failures))


def _validate_observations_against_record_set(
    record_set: PrintableResponseRecordSet,
    observations: tuple[QuillanResponsePageObservation, ...],
) -> None:
    issuance = record_set.issuance
    pages = {page.page_id: page for page in record_set.pages}
    seen_observations: set[str] = set()
    seen_source_pages: dict[tuple[str, int], str] = {}
    seen_paths: dict[str, str] = {}
    for observation in observations:
        if observation.observation_id in seen_observations:
            raise QuillanSubmissionObservationAssemblyError(
                "Duplicate observation identity supplied to assembly."
            )
        seen_observations.add(observation.observation_id)
        page = pages.get(observation.page_id)
        if page is None:
            raise QuillanCategorizedAssemblyError(
                "unexpected_page",
                "Observation page_id is not a member of its issuance.",
            )
        expected = (
            issuance.issuance_id,
            issuance.generation_id,
            issuance.artifact_id,
            issuance.class_id,
            issuance.assignment_id,
            issuance.student_id,
            page.page_id,
            page.logical_page,
            page.total_pages,
            page.page_role,
        )
        actual = (
            observation.issuance_id,
            observation.generation_id,
            observation.artifact_id,
            observation.class_id,
            observation.assignment_id,
            observation.student_id,
            observation.page_id,
            observation.logical_page,
            observation.total_pages,
            observation.page_role,
        )
        if actual != expected:
            raise QuillanCategorizedAssemblyError(
                "identity_conflict",
                "Observation identity contradicts its authoritative page record.",
            )
        source_key = (observation.source_scan_id, observation.source_page_number)
        previous_page = seen_source_pages.setdefault(source_key, observation.page_id)
        if previous_page != observation.page_id:
            raise QuillanCategorizedAssemblyError(
                "source_page_conflict",
                "One retained source page maps to contradictory page IDs.",
            )
        previous_observation = seen_paths.setdefault(
            observation.routed_evidence_path, observation.observation_id
        )
        if previous_observation != observation.observation_id:
            raise QuillanCategorizedAssemblyError(
                "identity_conflict",
                "One routed evidence path maps to contradictory observations.",
            )


def _validate_observation_routes(
    root: Path,
    record_set: PrintableResponseRecordSet,
    observations: tuple[QuillanResponsePageObservation, ...],
) -> None:
    pages = {page.page_id: page for page in record_set.pages}
    for observation in observations:
        page = pages[observation.page_id]
        locator = RouteLocator(
            schema=PDS2_SCHEMA,
            work=quillan_work_ref(observation.class_id, observation.assignment_id),
            route_id=observation.route_id,
        )
        try:
            registration = load_route_registration(root, locator)
        except RouteRegistrationPersistenceError as error:
            raise QuillanSubmissionObservationAssemblyError(
                f"Could not load observation route {observation.route_id}: {error}"
            ) from error
        if registration.target != response_page_target(
            page
        ) or registration.module_details != printable_response_module_details(page):
            raise QuillanSubmissionObservationAssemblyError(
                "Observation route registration contradicts its authoritative page."
            )


def _new_page(
    page: PrintableResponsePage,
    observations: tuple[QuillanResponsePageObservation, ...],
) -> dict[str, Any]:
    if not observations:
        return {
            "page_number": page.logical_page,
            "page_state": "missing",
            "selected_evidence_id": None,
            "evidence": [],
        }
    evidence: list[dict[str, Any]] = []
    single = len(observations) == 1
    for index, observation in enumerate(observations):
        evidence.append(
            _evidence_from_observation(
                observation,
                duplicate_number=None if index == 0 else index,
                evidence_role="selected" if single else "candidate",
                evidence_state="active",
            )
        )
    return {
        "page_number": page.logical_page,
        "page_state": "present" if single else "duplicate",
        "selected_evidence_id": observations[0].observation_id if single else None,
        "evidence": evidence,
    }


def _evidence_from_observation(
    observation: QuillanResponsePageObservation,
    *,
    duplicate_number: int | None,
    evidence_role: str,
    evidence_state: str,
) -> dict[str, Any]:
    return {
        "evidence_id": observation.observation_id,
        "routed_evidence_path": observation.routed_evidence_path,
        "evidence_role": evidence_role,
        "evidence_state": evidence_state,
        "duplicate_number": duplicate_number,
        "created_at": observation.created_at,
        "retained_source": {
            "source_scan_id": observation.source_scan_id,
            "source_filename": observation.source_filename,
            "source_sha256": observation.source_sha256,
            "retained_source_path": observation.retained_source_path,
            "source_page_number": observation.source_page_number,
        },
        "module_details": {
            "observation_id": observation.observation_id,
            "page_id": observation.page_id,
            "route_id": observation.route_id,
            "issuance_id": observation.issuance_id,
            "generation_id": observation.generation_id,
            "artifact_id": observation.artifact_id,
            "logical_page": observation.logical_page,
            "total_pages": observation.total_pages,
            "page_role": observation.page_role,
            "routed_evidence_sha256": observation.routed_evidence_sha256,
            "routed_evidence_kind": observation.routed_evidence_kind,
        },
    }


def _validate_existing_evidence_projection(
    evidence: dict[str, Any],
    observation: QuillanResponsePageObservation,
) -> None:
    """Validate immutable observation/provenance fields, preserving teacher state."""
    expected = _evidence_from_observation(
        observation,
        duplicate_number=evidence["duplicate_number"],
        evidence_role=evidence["evidence_role"],
        evidence_state=evidence["evidence_state"],
    )
    for field in (
        "evidence_id",
        "routed_evidence_path",
        "created_at",
        "retained_source",
    ):
        if evidence[field] != expected[field]:
            raise QuillanSubmissionObservationAssemblyError(
                f"Existing evidence {field} contradicts its immutable observation."
            )
    actual_details = evidence["module_details"]
    expected_details = expected["module_details"]
    for field, expected_value in expected_details.items():
        if actual_details.get(field) != expected_value:
            raise QuillanSubmissionObservationAssemblyError(
                "Existing evidence immutable module details contradict its observation."
            )


def _timestamp(value: datetime | str | None) -> str:
    candidate: datetime | str = datetime.now(timezone.utc) if value is None else value
    if isinstance(candidate, datetime):
        if candidate.tzinfo is None or candidate.utcoffset() is None:
            raise QuillanSubmissionObservationAssemblyError(
                "Assembly timestamp must be timezone-aware."
            )
        return candidate.isoformat()
    if not isinstance(candidate, str):
        raise QuillanSubmissionObservationAssemblyError(
            "Assembly timestamp must be a datetime or ISO string."
        )
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise QuillanSubmissionObservationAssemblyError(
            "Assembly timestamp must be a timezone-aware ISO string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise QuillanSubmissionObservationAssemblyError(
            "Assembly timestamp must be timezone-aware."
        )
    return candidate


def _observation_sort_key(
    item: QuillanResponsePageObservation,
) -> tuple[object, ...]:
    return (
        item.logical_page,
        item.created_at,
        item.source_scan_id,
        item.source_page_number,
        item.observation_id,
    )


def _failure(
    category: str,
    class_id: str,
    assignment_id: str,
    student_id: str | None,
    observations: tuple[QuillanResponsePageObservation, ...],
    reason: str,
    error: Exception | None = None,
    possible_manifest_path: Path | None = None,
) -> QuillanSubmissionAssemblyFailure:
    return QuillanSubmissionAssemblyFailure(
        category=category,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        issuance_ids=tuple(sorted({item.issuance_id for item in observations})),
        observation_ids=tuple(item.observation_id for item in observations),
        page_ids=tuple(item.page_id for item in observations),
        logical_pages=tuple(item.logical_page for item in observations),
        source_scan_ids=tuple(item.source_scan_id for item in observations),
        source_page_numbers=tuple(item.source_page_number for item in observations),
        reason=reason,
        error=error,
        possible_manifest_path=possible_manifest_path,
    )


def _assembled(
    root: Path,
    manifest: dict[str, Any],
    status: Literal["created", "updated", "unchanged"],
    path: Path,
    observations: tuple[QuillanResponsePageObservation, ...],
) -> AssembledQuillanSubmission:
    def pages_with_state(state: str) -> tuple[int, ...]:
        return tuple(
            page["page_number"]
            for page in manifest["pages"]
            if page["page_state"] == state
        )

    details = manifest["module_details"]
    return AssembledQuillanSubmission(
        workspace_root=root,
        class_id=manifest["class_id"],
        assignment_id=manifest["assignment_id"],
        student_id=manifest["student_id"],
        issuance_id=details["response_issuance_id"],
        manifest_path=path,
        manifest_relative_path=path.relative_to(root).as_posix(),
        status=status,
        assembly_revision=details["assembly_revision"],
        missing_pages=pages_with_state("missing"),
        duplicate_pages=pages_with_state("duplicate"),
        needs_rescan_pages=pages_with_state("needs_rescan"),
        excluded_pages=pages_with_state("excluded"),
        observation_ids=tuple(item.observation_id for item in observations),
    )


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive non-Boolean integer.")
    return value


def _assembled_sort_key(
    item: AssembledQuillanSubmission,
) -> tuple[str, str, str, str]:
    return (item.class_id, item.assignment_id, item.student_id, item.issuance_id)


def _failure_occurrence_key(
    item: QuillanSubmissionAssemblyFailure,
) -> tuple[object, ...]:
    return (
        item.class_id,
        item.assignment_id,
        item.student_id or "",
        item.issuance_ids,
        item.observation_ids,
        tuple(zip(item.source_scan_ids, item.source_page_numbers, strict=True)),
    )


def _failure_sort_key(
    item: QuillanSubmissionAssemblyFailure,
) -> tuple[object, ...]:
    return (*_failure_occurrence_key(item), item.category, item.reason)


def _positive_integer_tuple(
    value: object, field_name: str, *, require_unique: bool = True
) -> tuple[int, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field_name} must be a tuple.")
    for item in value:
        _positive_integer(item, field_name)
    if require_unique and len(set(value)) != len(value):
        raise ValueError(f"{field_name} members must be unique.")
    return cast(tuple[int, ...], value)


def _validated_tuple(
    value: object,
    validator: Any,
    field_name: str,
    *,
    require_unique: bool = True,
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field_name} must be a tuple.")
    for item in value:
        validator(item)
    if require_unique and len(set(value)) != len(value):
        raise ValueError(f"{field_name} members must be unique.")
    return cast(tuple[str, ...], value)


def _absolute_canonical_path(value: object, field_name: str) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        raise ValueError(f"{field_name} must be an absolute Path.")
    if value != Path(os.path.abspath(value)):
        raise ValueError(f"{field_name} must be canonical.")
    return value


def _is_link_like(path: Path) -> bool:
    return _shared_is_link_like(path)


def _relative_posix(value: object, field_name: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field_name} must be canonical relative POSIX text.")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{field_name} must be canonical relative POSIX text.")
    return path


__all__ = [
    "ASSEMBLY_FAILURE_CATEGORIES",
    "AssembledQuillanSubmission",
    "QuillanSubmissionAssemblyBatch",
    "QuillanSubmissionAssemblyFailure",
    "assemble_quillan_scan_observations",
    "assemble_quillan_submission_manifests",
    "merge_submission_manifest_observations",
]

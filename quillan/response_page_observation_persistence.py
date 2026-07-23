"""Transactional persistence for successful Quillan page observations."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Literal

from pds_core.module_dispatch import RouteDispatchSuccess
from pds_core.identifiers import validate_identifier

from quillan._path_safety import is_link_like as _shared_is_link_like
from quillan.module_errors import (
    QuillanObservationAuthorityError,
    QuillanObservationIntegrityError,
    QuillanObservationPersistenceError,
    QuillanObservationValidationError,
    QuillanRoutedEvidenceError,
)
from quillan.pds2_scan_intake import (
    QuillanScanIntakeSummary,
    QuillanScanPageOutcome,
)
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.printable_response_persistence import (
    PrintableResponsePersistenceError,
    load_printable_response_page_context,
)
from quillan.printable_response_records import response_page_target, validate_page_id
from quillan.printable_response_routes import (
    printable_response_module_details,
    validate_route_id,
)
from quillan.response_page_dispatch import (
    QuillanResponsePageDispatchResult,
    validate_quillan_response_page_dispatch_result,
)
from quillan.response_page_observations import (
    OBSERVATION_RECORD_TYPE,
    OBSERVATION_SCHEMA_VERSION,
    QuillanResponsePageObservation,
    canonical_response_page_observation_json,
    derive_observation_id,
    load_contextual_response_page_observation,
)
from quillan.routed_evidence import (
    _PreparedRoutedPageEvidence,
    _prepare_routed_page_evidence,
    verify_routed_page_evidence,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    preflight_work_directory_destination,
    preflight_work_file_destination,
    quillan_work_ref,
    response_page_observation_path,
    routed_evidence_path,
)


@dataclass(frozen=True, slots=True)
class PersistedQuillanPageObservation:
    workspace_root: Path
    observation: QuillanResponsePageObservation
    observation_path: Path
    observation_relative_path: str
    evidence_path: Path
    evidence_relative_path: str
    status: Literal["created", "existing"]

    def __post_init__(self) -> None:
        root = _absolute_canonical_path(self.workspace_root, "workspace_root")
        if _is_link_like(root) or not root.is_dir():
            raise ValueError("workspace_root must be an ordinary non-link directory.")
        if type(self.observation) is not QuillanResponsePageObservation:
            raise ValueError("observation has the wrong type.")
        _absolute_canonical_path(self.observation_path, "observation_path")
        _absolute_canonical_path(self.evidence_path, "evidence_path")
        _relative_posix(self.observation_relative_path, "observation_relative_path")
        _relative_posix(self.evidence_relative_path, "evidence_relative_path")
        if self.status not in {"created", "existing"}:
            raise ValueError("Unsupported persisted observation status.")
        if self.observation_path.name != f"{self.observation.observation_id}.json":
            raise ValueError("observation_path contradicts observation_id.")
        work_ref = quillan_work_ref(
            self.observation.class_id, self.observation.assignment_id
        )
        expected_observation_path = response_page_observation_path(
            root, work_ref, self.observation.observation_id
        )
        expected_evidence_path = routed_evidence_path(
            root,
            work_ref,
            self.observation.issuance_id,
            self.observation.student_id,
            self.observation.logical_page,
            self.observation.observation_id,
            self.evidence_path.suffix,
        )
        if self.observation_path != expected_observation_path:
            raise ValueError(
                "observation_path is not the canonical observation destination."
            )
        if self.evidence_path != expected_evidence_path:
            raise ValueError("evidence_path is not the canonical evidence destination.")
        if _relative_to_root(self.observation_path, root) != self.observation_relative_path:
            raise ValueError("observation relative and absolute paths disagree.")
        if self.evidence_relative_path != self.observation.routed_evidence_path:
            raise ValueError("evidence_relative_path contradicts the observation.")
        if _relative_to_root(self.evidence_path, root) != self.evidence_relative_path:
            raise ValueError("evidence relative and absolute paths disagree.")


@dataclass(frozen=True, slots=True)
class _ExclusiveInstallResult:
    destination_created: bool
    temporary_removed: bool
    cleanup_error: OSError | None = None

    def __post_init__(self) -> None:
        if type(self.destination_created) is not bool:
            raise ValueError("destination_created must be a Boolean.")
        if type(self.temporary_removed) is not bool:
            raise ValueError("temporary_removed must be a Boolean.")
        if not self.destination_created:
            raise ValueError("An install result requires a created destination.")
        if self.temporary_removed != (self.cleanup_error is None):
            raise ValueError("Temporary cleanup state contradicts cleanup_error.")
        if self.cleanup_error is not None and not isinstance(
            self.cleanup_error, OSError
        ):
            raise ValueError("cleanup_error must be an OSError or None.")


@dataclass(frozen=True, slots=True)
class QuillanObservationPersistenceFailure:
    source_scan_id: str
    source_page_number: int
    route_id: str | None
    page_id: str | None
    error: Exception
    possible_observation_path: Path | None
    possible_evidence_path: Path | None

    def __post_init__(self) -> None:
        validate_identifier(self.source_scan_id, "source_scan_id")
        _positive_integer(self.source_page_number, "source_page_number")
        if self.route_id is not None:
            validate_route_id(self.route_id)
        if self.page_id is not None:
            validate_page_id(self.page_id)
        if not isinstance(self.error, Exception):
            raise ValueError("error must be an Exception.")
        for field_name in ("possible_observation_path", "possible_evidence_path"):
            value = getattr(self, field_name)
            if value is not None:
                _absolute_canonical_path(value, field_name)


@dataclass(frozen=True, slots=True)
class QuillanObservationPersistenceBatch:
    intake_summary: QuillanScanIntakeSummary
    persisted: tuple[PersistedQuillanPageObservation, ...]
    failures: tuple[QuillanObservationPersistenceFailure, ...]
    skipped_foreign_success_count: int

    def __post_init__(self) -> None:
        if type(self.intake_summary) is not QuillanScanIntakeSummary:
            raise ValueError("intake_summary has the wrong type.")
        if type(self.persisted) is not tuple or type(self.failures) is not tuple:
            raise ValueError("Persistence collections must be immutable tuples.")
        if any(
            type(item) is not PersistedQuillanPageObservation for item in self.persisted
        ):
            raise ValueError("persisted members have the wrong type.")
        if any(
            type(item) is not QuillanObservationPersistenceFailure
            for item in self.failures
        ):
            raise ValueError("failure members have the wrong type.")
        ids = tuple(item.observation.observation_id for item in self.persisted)
        paths = tuple(item.observation_path for item in self.persisted)
        occurrences = tuple(
            (
                item.observation.source_scan_id,
                item.observation.source_page_number,
                item.observation.route_id,
                item.observation.page_id,
            )
            for item in self.persisted
        )
        failed_occurrences = tuple(
            (item.source_scan_id, item.source_page_number, item.route_id, item.page_id)
            for item in self.failures
        )
        if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
            raise ValueError("Persisted observation IDs and paths must be unique.")
        if len(set(failed_occurrences)) != len(failed_occurrences):
            raise ValueError("Failed observation occurrence keys must be unique.")
        if set(occurrences) & set(failed_occurrences):
            raise ValueError("One occurrence cannot be both persisted and failed.")
        if (
            isinstance(self.skipped_foreign_success_count, bool)
            or not isinstance(self.skipped_foreign_success_count, int)
            or self.skipped_foreign_success_count < 0
        ):
            raise ValueError("skipped_foreign_success_count must be nonnegative.")

    @property
    def created_count(self) -> int:
        return sum(item.status == "created" for item in self.persisted)

    @property
    def existing_count(self) -> int:
        return sum(item.status == "existing" for item in self.persisted)

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def observation_created_count(self) -> int:
        """Count verified new observation records from the paired transaction."""
        return sum(item.status == "created" for item in self.persisted)

    @property
    def observation_existing_count(self) -> int:
        """Count verified existing observation records from the paired transaction."""
        return sum(item.status == "existing" for item in self.persisted)

    @property
    def routed_evidence_created_count(self) -> int:
        """Count verified new evidence files from the paired transaction."""
        return sum(item.status == "created" for item in self.persisted)

    @property
    def routed_evidence_existing_count(self) -> int:
        """Count verified existing evidence files from the paired transaction."""
        return sum(item.status == "existing" for item in self.persisted)

    @property
    def observation_persistence_failure_count(self) -> int:
        """Count paired operations that did not verify observation durability."""
        return len(self.failures)

    @property
    def routed_evidence_persistence_failure_count(self) -> int:
        """Count paired operations that did not verify evidence durability."""
        return len(self.failures)


def persist_quillan_page_observation(
    workspace_root: Path,
    page_outcome: QuillanScanPageOutcome,
) -> PersistedQuillanPageObservation:
    """Persist one exact successful Quillan outcome idempotently."""
    root = _workspace_root(workspace_root)
    result = _authoritative_result(root, page_outcome)
    observation_id = derive_observation_id(
        result.source_scan_id,
        result.source_page_number,
        result.route_id,
        result.page_id,
    )
    prepared = _prepare_routed_page_evidence(root, result, observation_id=observation_id)
    observation = _build_observation(result, prepared)
    work_ref = quillan_work_ref(result.class_id, result.assignment_id)
    observation_path = response_page_observation_path(root, work_ref, observation_id)
    expected_observation_bytes = canonical_response_page_observation_json(observation)
    _preflight_destinations(root, result, observation_path, prepared.path)

    observation_exists = os.path.lexists(observation_path)
    evidence_exists = os.path.lexists(prepared.path)
    if observation_exists and evidence_exists:
        return _validate_existing(
            root,
            observation,
            observation_path,
            prepared,
        )
    if observation_exists:
        raise _integrity_failure(
            "Observation exists without its routed evidence.",
            observation_path,
            prepared.path,
        )
    if evidence_exists:
        raise _integrity_failure(
            "Orphan routed evidence exists without its observation.",
            observation_path,
            prepared.path,
        )

    observation_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.path.parent.mkdir(parents=True, exist_ok=True)
    evidence_temp: Path | None = None
    observation_temp: Path | None = None
    try:
        evidence_temp = _write_temporary(prepared.path, prepared.content)
        observation_temp = _write_temporary(
            observation_path, expected_observation_bytes
        )
        try:
            evidence_install = _install_exclusive(evidence_temp, prepared.path)
        except OSError as error:
            evidence_state = _inspect_destination(
                root, result, prepared.path, prepared.content
            )
            if evidence_state == "contradictory":
                raise _integrity_failure(
                    "Evidence installation left contradictory or uncertain durable state.",
                    None,
                    prepared.path,
                ) from error
            raise _persistence_failure(
                "Evidence installation failed before a durable destination was created."
                if evidence_state == "absent"
                else "Evidence installation reported failure after creating exact durable evidence.",
                None,
                prepared.path if evidence_state == "exact" else None,
            ) from error
        if evidence_install.temporary_removed:
            evidence_temp = None
        else:
            evidence_state = _inspect_destination(
                root, result, prepared.path, prepared.content
            )
            if evidence_state == "contradictory":
                raise _integrity_failure(
                    "Evidence temporary cleanup failed with contradictory durable state.",
                    None,
                    prepared.path,
                ) from evidence_install.cleanup_error
            raise _persistence_failure(
                "Evidence destination was created, but its temporary file could not be removed."
                if evidence_state == "exact"
                else "Evidence temporary cleanup failed and its destination is now absent.",
                None,
                prepared.path if evidence_state == "exact" else None,
            ) from evidence_install.cleanup_error
        try:
            observation_install = _install_exclusive(
                observation_temp, observation_path
            )
        except OSError as error:
            observation_state = _inspect_destination(
                root,
                result,
                observation_path,
                expected_observation_bytes,
            )
            if observation_state == "exact":
                raise _persistence_failure(
                    "Observation installation reported failure after creating the exact durable observation.",
                    observation_path,
                    prepared.path,
                ) from error
            if observation_state == "contradictory":
                raise _integrity_failure(
                    "Observation installation left contradictory or uncertain durable state.",
                    observation_path,
                    prepared.path,
                ) from error
            if not _remove_owned_file(
                root, result, prepared.path, prepared.content
            ):
                raise _persistence_failure(
                    "Observation installation failed and evidence rollback could not be confirmed.",
                    observation_path,
                    prepared.path,
                ) from error
            raise _persistence_failure(
                "Observation installation failed before creating its destination; exact evidence was rolled back.",
                None,
                None,
            ) from error
        if observation_install.temporary_removed:
            observation_temp = None
        else:
            observation_state = _inspect_destination(
                root,
                result,
                observation_path,
                expected_observation_bytes,
            )
            if observation_state == "contradictory":
                raise _integrity_failure(
                    "Observation temporary cleanup failed with contradictory durable state.",
                    observation_path,
                    prepared.path,
                ) from observation_install.cleanup_error
            if observation_state == "absent":
                if not _remove_owned_file(
                    root, result, prepared.path, prepared.content
                ):
                    raise _persistence_failure(
                        "Observation temporary cleanup failed after its destination disappeared; evidence rollback could not be confirmed.",
                        None,
                        prepared.path,
                    ) from observation_install.cleanup_error
                raise _persistence_failure(
                    "Observation temporary cleanup failed after its destination disappeared; exact evidence was rolled back.",
                    None,
                    None,
                ) from observation_install.cleanup_error
            raise _persistence_failure(
                "Observation destination was created, but its temporary file could not be removed.",
                observation_path,
                prepared.path,
            ) from observation_install.cleanup_error
        reloaded = load_contextual_response_page_observation(
            root, work_ref, observation_id
        )
        if reloaded != observation:
            raise _persistence_failure(
                "Reloaded observation differs from the committed model.",
                observation_path,
                prepared.path,
            )
        verify_routed_page_evidence(
            prepared.path,
            expected_sha256=prepared.sha256,
            expected_size_bytes=prepared.size_bytes,
        )
    except QuillanObservationPersistenceError:
        raise
    except FileExistsError as error:
        raise _persistence_failure(
            "Observation transaction lost an exclusive-install collision.",
            observation_path if os.path.lexists(observation_path) else None,
            prepared.path if os.path.lexists(prepared.path) else None,
        ) from error
    except (
        OSError,
        QuillanObservationIntegrityError,
        QuillanObservationValidationError,
        QuillanRoutedEvidenceError,
    ) as error:
        possible_evidence = prepared.path if os.path.lexists(prepared.path) else None
        possible_observation = (
            observation_path if os.path.lexists(observation_path) else None
        )
        raise _persistence_failure(
            f"Could not persist response-page observation: {error}",
            possible_observation,
            possible_evidence,
        ) from error
    finally:
        _remove_temporary(evidence_temp)
        _remove_temporary(observation_temp)

    return PersistedQuillanPageObservation(
        workspace_root=root,
        observation=observation,
        observation_path=observation_path,
        observation_relative_path=observation_path.relative_to(root).as_posix(),
        evidence_path=prepared.path,
        evidence_relative_path=prepared.relative_path,
        status="created",
    )


def persist_quillan_scan_observations(
    workspace_root: Path,
    summary: QuillanScanIntakeSummary,
) -> QuillanObservationPersistenceBatch:
    """Persist all successful Quillan pages in deterministic intake order."""
    if type(summary) is not QuillanScanIntakeSummary:
        raise QuillanObservationAuthorityError(
            "summary must be an exact QuillanScanIntakeSummary."
        )
    persisted: list[PersistedQuillanPageObservation] = []
    failures: list[QuillanObservationPersistenceFailure] = []
    foreign = 0
    for source in summary.source_results:
        for page in source.pages:
            if page.terminal_category != "dispatch_success":
                continue
            outcome = page.dispatch_outcome
            if (
                not isinstance(outcome, RouteDispatchSuccess)
                or type(outcome) is not RouteDispatchSuccess
            ):
                continue
            if outcome.profile.module_id != QUILLAN_MODULE_ID:
                foreign += 1
                continue
            result = outcome.module_result
            route_id: str | None
            page_id: str | None
            if type(result) is QuillanResponsePageDispatchResult:
                source_scan_id = result.source_scan_id
                route_id = result.route_id
                page_id = result.page_id
            else:
                source_scan_id = page.retained_source.source_scan_id
                route_id = page.locator.route_id if page.locator is not None else None
                page_id = None
            try:
                persisted.append(persist_quillan_page_observation(workspace_root, page))
            except Exception as error:
                possible_observation = getattr(error, "possible_observation_path", None)
                possible_evidence = getattr(error, "possible_evidence_path", None)
                failures.append(
                    QuillanObservationPersistenceFailure(
                        source_scan_id=source_scan_id,
                        source_page_number=page.source_page_number,
                        route_id=route_id,
                        page_id=page_id,
                        error=error,
                        possible_observation_path=possible_observation,
                        possible_evidence_path=possible_evidence,
                    )
                )
    return QuillanObservationPersistenceBatch(
        intake_summary=summary,
        persisted=tuple(persisted),
        failures=tuple(failures),
        skipped_foreign_success_count=foreign,
    )


def _authoritative_result(
    root: Path,
    page_outcome: object,
) -> QuillanResponsePageDispatchResult:
    try:
        if type(page_outcome) is not QuillanScanPageOutcome:
            raise ValueError("page_outcome must be an exact QuillanScanPageOutcome.")
        if page_outcome.terminal_category != "dispatch_success":
            raise ValueError("page_outcome must be a dispatch_success.")
        success = page_outcome.dispatch_outcome
        if (
            not isinstance(success, RouteDispatchSuccess)
            or type(success) is not RouteDispatchSuccess
        ):
            raise ValueError("dispatch_success requires an exact Core success.")
        if success.profile.module_id != QUILLAN_MODULE_ID:
            raise ValueError("Core success is owned by a foreign module.")
        if type(success.module_result) is not QuillanResponsePageDispatchResult:
            raise ValueError("Quillan success has the wrong result type.")
        result = validate_quillan_response_page_dispatch_result(success.module_result)
        request = page_outcome.dispatch_request
        if request is None or success.request != request:
            raise ValueError("Core success contradicts the exact dispatch request.")
        if request.retained_source is not page_outcome.retained_source:
            raise ValueError(
                "Dispatch request does not use the page's retained source."
            )
        if request.source_page_number != page_outcome.source_page_number:
            raise ValueError("Dispatch request contradicts the physical source page.")
        if (
            page_outcome.locator != request.locator
            or success.resolution.locator != request.locator
        ):
            raise ValueError("Page, request, and resolution locators disagree.")
        locator = request.locator
        if (
            locator.module_id != QUILLAN_MODULE_ID
            or locator.class_id != result.class_id
            or locator.work_id != result.assignment_id
            or locator.route_id != result.route_id
        ):
            raise ValueError("Dispatch locator contradicts result identity.")
        if (
            result.source_scan_id != page_outcome.retained_source.source_scan_id
            or result.source_page_number != page_outcome.source_page_number
            or result.retained_source_path
            != page_outcome.retained_source.retained_source_path
            or result.retained_source_relative_path
            != page_outcome.retained_source.retained_source_relative_path
            or result.source_sha256 != page_outcome.retained_source.source_sha256
            or result.source_filename != page_outcome.retained_source.source_filename
            or result.intake_timestamp != page_outcome.retained_source.intake_timestamp
            or result.intake_date != page_outcome.retained_source.intake_date
        ):
            raise ValueError("Dispatch result contradicts retained provenance.")
        work_ref = quillan_work_ref(result.class_id, result.assignment_id)
        context = load_printable_response_page_context(root, work_ref, result.page_id)
        page = context.page
        issuance = context.issuance
        if issuance.lifecycle.status != "issued":
            raise ValueError("New observations require an issued issuance.")
        expected = (
            page.page_id,
            page.issuance_id,
            page.generation_id,
            page.artifact_id,
            page.class_id,
            page.assignment_id,
            page.student_id,
            page.logical_page,
            page.total_pages,
            page.page_role,
        )
        actual = (
            result.page_id,
            result.issuance_id,
            result.generation_id,
            result.artifact_id,
            result.class_id,
            result.assignment_id,
            result.student_id,
            result.logical_page,
            result.total_pages,
            result.page_role,
        )
        if actual != expected:
            raise ValueError("Dispatch result contradicts immutable page context.")
        registration = success.resolution.registration
        if registration.target != response_page_target(page):
            raise ValueError("Resolved registration target contradicts the page.")
        if registration.module_details != printable_response_module_details(page):
            raise ValueError("Resolved registration details contradict the page.")
        return result
    except QuillanObservationAuthorityError:
        raise
    except (
        PrintableResponsePersistenceError,
        ValueError,
        TypeError,
        AttributeError,
    ) as error:
        raise QuillanObservationAuthorityError(
            f"Page outcome is not authoritative for observation persistence: {error}"
        ) from error


def _build_observation(
    result: QuillanResponsePageDispatchResult,
    prepared: _PreparedRoutedPageEvidence,
) -> QuillanResponsePageObservation:
    timestamp = result.intake_timestamp.isoformat()
    return QuillanResponsePageObservation(
        schema_version=OBSERVATION_SCHEMA_VERSION,
        observation_id=prepared.observation_id,
        record_type=OBSERVATION_RECORD_TYPE,
        module_id=QUILLAN_MODULE_ID,
        created_at=timestamp,
        class_id=result.class_id,
        assignment_id=result.assignment_id,
        student_id=result.student_id,
        generation_id=result.generation_id,
        artifact_id=result.artifact_id,
        issuance_id=result.issuance_id,
        page_id=result.page_id,
        route_id=result.route_id,
        logical_page=result.logical_page,
        total_pages=result.total_pages,
        page_role=result.page_role,
        source_scan_id=result.source_scan_id,
        source_filename=result.source_filename,
        source_page_number=result.source_page_number,
        retained_source_path=result.retained_source_relative_path,
        source_sha256=result.source_sha256,
        intake_timestamp=timestamp,
        intake_date=result.intake_date.isoformat(),
        routed_evidence_path=prepared.relative_path,
        routed_evidence_sha256=prepared.sha256,
        routed_evidence_size_bytes=prepared.size_bytes,
        routed_evidence_kind=prepared.evidence_kind,
        module_details={},
    )


def _preflight_destinations(
    root: Path,
    result: QuillanResponsePageDispatchResult,
    observation_path: Path,
    evidence_path: Path,
) -> None:
    work_ref = quillan_work_ref(result.class_id, result.assignment_id)
    work_root = (
        root
        / "classes"
        / result.class_id
        / "modules"
        / QUILLAN_MODULE_ID
        / "work"
        / result.assignment_id
    )
    try:
        preflight_work_directory_destination(root, work_ref, "scans/observations")
        preflight_work_directory_destination(
            root, work_ref, Path("scans") / "evidence" / result.issuance_id
        )
        preflight_work_file_destination(
            root, work_ref, observation_path.relative_to(work_root)
        )
        preflight_work_file_destination(
            root, work_ref, evidence_path.relative_to(work_root)
        )
    except (QuillanWorkPathError, ValueError) as error:
        raise _persistence_failure(
            f"Observation destinations failed preflight: {error}",
            observation_path if os.path.lexists(observation_path) else None,
            evidence_path if os.path.lexists(evidence_path) else None,
        ) from error


def _validate_existing(
    root: Path,
    expected: QuillanResponsePageObservation,
    observation_path: Path,
    prepared: _PreparedRoutedPageEvidence,
) -> PersistedQuillanPageObservation:
    try:
        work_ref = quillan_work_ref(expected.class_id, expected.assignment_id)
        existing = load_contextual_response_page_observation(
            root, work_ref, expected.observation_id
        )
        if existing != expected:
            raise QuillanObservationIntegrityError(
                "Existing observation contradicts the expected immutable record."
            )
        verify_routed_page_evidence(
            prepared.path,
            expected_sha256=prepared.sha256,
            expected_size_bytes=prepared.size_bytes,
        )
        if prepared.path.read_bytes() != prepared.content:
            raise QuillanObservationIntegrityError(
                "Existing evidence bytes contradict the expected artifact."
            )
    except (
        OSError,
        QuillanObservationIntegrityError,
        QuillanObservationValidationError,
        QuillanRoutedEvidenceError,
    ) as error:
        if isinstance(error, QuillanObservationIntegrityError):
            conflict = error
        else:
            conflict = QuillanObservationIntegrityError(
                f"Existing observation transaction is invalid: {error}"
            )
        conflict.possible_observation_path = observation_path
        conflict.possible_evidence_path = prepared.path
        raise conflict from error
    return PersistedQuillanPageObservation(
        workspace_root=root,
        observation=existing,
        observation_path=observation_path,
        observation_relative_path=observation_path.relative_to(root).as_posix(),
        evidence_path=prepared.path,
        evidence_relative_path=prepared.relative_path,
        status="existing",
    )


def _write_temporary(destination: Path, content: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    path = Path(name)
    complete = False
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        complete = True
    finally:
        if not complete:
            path.unlink(missing_ok=True)
    return path


def _install_exclusive(
    temporary: Path, destination: Path
) -> _ExclusiveInstallResult:
    os.link(temporary, destination)
    try:
        temporary.unlink()
    except OSError as error:
        return _ExclusiveInstallResult(True, False, error)
    return _ExclusiveInstallResult(True, True)


def _inspect_destination(
    root: Path,
    result: QuillanResponsePageDispatchResult,
    path: Path,
    expected: bytes,
) -> Literal["absent", "exact", "contradictory"]:
    if not os.path.lexists(path):
        return "absent"
    work_ref = quillan_work_ref(result.class_id, result.assignment_id)
    work_root = (
        root
        / "classes"
        / result.class_id
        / "modules"
        / QUILLAN_MODULE_ID
        / "work"
        / result.assignment_id
    )
    try:
        checked = preflight_work_file_destination(
            root, work_ref, path.relative_to(work_root)
        )
        if checked != path or _is_link_like(path) or not path.is_file():
            return "contradictory"
        return "exact" if path.read_bytes() == expected else "contradictory"
    except (OSError, QuillanWorkPathError, ValueError):
        return "contradictory"


def _remove_owned_file(
    root: Path,
    result: QuillanResponsePageDispatchResult,
    path: Path,
    expected: bytes,
) -> bool:
    try:
        if not os.path.lexists(path):
            return True
        work_ref = quillan_work_ref(result.class_id, result.assignment_id)
        work_root = (
            root
            / "classes"
            / result.class_id
            / "modules"
            / QUILLAN_MODULE_ID
            / "work"
            / result.assignment_id
        )
        checked = preflight_work_file_destination(
            root, work_ref, path.relative_to(work_root)
        )
        if checked != path:
            return False
        if _is_link_like(path) or not path.is_file() or path.read_bytes() != expected:
            return False
        path.unlink()
        return not os.path.lexists(path)
    except (OSError, QuillanWorkPathError, ValueError):
        return False


def _remove_temporary(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _workspace_root(value: object) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        raise QuillanObservationPersistenceError(
            "workspace_root must be an absolute Path."
        )
    root = Path(os.path.abspath(value))
    if value != root or _is_link_like(root) or not root.is_dir():
        raise QuillanObservationPersistenceError(
            "workspace_root must be an existing canonical non-link directory."
        )
    return root


def _is_link_like(path: Path) -> bool:
    return _shared_is_link_like(path)


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive non-Boolean integer.")
    return value


def _absolute_canonical_path(value: object, field_name: str) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        raise ValueError(f"{field_name} must be an absolute Path.")
    if value != Path(os.path.abspath(value)):
        raise ValueError(f"{field_name} must be canonical.")
    return value


def _relative_posix(value: object, field_name: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field_name} must be relative POSIX text.")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{field_name} must be canonical relative POSIX text.")
    return path


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("Result path must be contained by workspace_root.") from error


def _integrity_failure(
    message: str,
    observation_path: Path | None,
    evidence_path: Path | None,
) -> QuillanObservationIntegrityError:
    return QuillanObservationIntegrityError(
        message,
        possible_observation_path=observation_path,
        possible_evidence_path=evidence_path,
    )


def _persistence_failure(
    message: str,
    observation_path: Path | None,
    evidence_path: Path | None,
) -> QuillanObservationPersistenceError:
    return QuillanObservationPersistenceError(
        message,
        possible_observation_path=observation_path,
        possible_evidence_path=evidence_path,
    )


__all__ = [
    "PersistedQuillanPageObservation",
    "QuillanObservationPersistenceBatch",
    "QuillanObservationPersistenceFailure",
    "persist_quillan_page_observation",
    "persist_quillan_scan_observations",
]

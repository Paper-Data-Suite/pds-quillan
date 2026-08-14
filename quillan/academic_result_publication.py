"""Explicit Core publication workflows for Quillan Academic Result manifests.

Quillan owns producer manifest selection and publication intent. Core owns every
canonical Publication Record, Publication Withdrawal, identifier, timestamp,
registry write, and the disposable academic catalog. This module deliberately
contains no JSON or SQLite writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NoReturn

from pds_core.academic_catalog import (
    AcademicCatalogBuildError,
    AcademicCatalogBuildResult,
    AcademicCatalogCompatibilityError,
    AcademicCatalogConflictError,
    AcademicCatalogError,
    AcademicCatalogIntegrityError,
    AcademicCatalogNotFoundError,
    AcademicCatalogReadError,
    AcademicCatalogSourceError,
    AcademicCatalogValidationError,
    CatalogPublication,
    PublicationCatalogQuery,
    load_academic_catalog_metadata,
    query_publication_catalog,
    rebuild_academic_catalog,
)
from pds_core.academic_work_registration_storage import (
    AcademicWorkRegistrationStorageError,
    load_academic_work_registration_revision,
    load_current_academic_work_registration,
)
from pds_core.academic_work_registrations import AcademicWorkRegistration
from pds_core.publication_compatibility import (
    PublicationCompatibilityResult,
    evaluate_publication_compatibility,
)
from pds_core.publication_records import (
    PublicationCapability,
    PublicationKind,
    PublicationRecord,
    PublicationRecordError,
    PublicationWithdrawal,
    validate_publication_record_series,
)
from pds_core.publication_storage import (
    PublicationManifestError,
    PublicationManifestIntegrityError,
    PublicationManifestNotFoundError,
    PublicationStorageError,
    list_publication_record_set,
    verify_publication_manifest,
)
from pds_core.registry_services import (
    PublicationManifestRequest,
    PublicationServiceResult,
    PublicationWithdrawalRequest,
    RegistryServiceConflictError,
    RegistryServiceError,
    RegistryServiceIntegrityError,
    RegistryServiceNotFoundError,
    RegistryServicePartialSuccessError,
    RegistryServiceValidationError,
    RegistryServiceWriteError,
    get_canonical_publication_record,
    get_canonical_publication_withdrawal,
    publish_manifest_revision,
    supersede_manifest_revision,
    withdraw_publication,
)
from pds_core.routing_models import ModuleRecordRef, ModuleWorkRef

from quillan.academic_result_manifest_generation import (
    AcademicResultManifestGenerationResult,
    QuillanManifestGenerationError,
    QuillanManifestGenerationPartialSuccessError,
    StoredAcademicResultManifest,
    generate_academic_result_manifest,
    list_academic_result_manifest_revisions,
    load_academic_result_manifest_revision,
)
from quillan.academic_work_registration import (
    QUILLAN_ACADEMIC_WORK_KIND,
    QUILLAN_ASSIGNMENT_SOURCE_CONTRACT_VERSION,
    QUILLAN_ASSIGNMENT_SOURCE_RECORD_KIND,
)
from quillan.pds_contract import (
    ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
    QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION,
    QUILLAN_MODULE_ID,
)
from quillan.pds_publication import get_publication_producer_profile
from quillan.publication_revision_policy import (
    QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
    QuillanPublicationRevisionPolicyError,
    validate_manifest_revision_transition,
)
from quillan.work_paths import academic_result_manifest_relative_path, quillan_work_ref

QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND: PublicationKind = "academic_result_set"
QUILLAN_PUBLICATION_CAPABILITIES: tuple[PublicationCapability, ...] = (
    "standards_ratings",
)

WithdrawalManifestVerification = Literal[
    "verified", "missing", "digest_mismatch_or_unsafe", "unreadable"
]
_WITHDRAWAL_STATES = frozenset(
    {"verified", "missing", "digest_mismatch_or_unsafe", "unreadable"}
)
PublicationOperation = Literal[
    "publish", "supersede", "republish_after_withdrawal", "withdraw"
]


class QuillanAcademicResultPublicationError(Exception):
    """Base error for Quillan's publication-management boundary."""


class QuillanAcademicResultPublicationValidationError(
    QuillanAcademicResultPublicationError, ValueError
):
    """Caller input is malformed."""


class QuillanAcademicResultPublicationNotFoundError(
    QuillanAcademicResultPublicationError
):
    """Required producer or canonical state does not exist."""


class QuillanAcademicResultPublicationConflictError(
    QuillanAcademicResultPublicationError
):
    """Current immutable state conflicts with the requested transition."""


class QuillanAcademicResultPublicationIntegrityError(
    QuillanAcademicResultPublicationError
):
    """Producer, canonical, or derived state is contradictory."""


class QuillanAcademicResultPublicationWriteError(
    QuillanAcademicResultPublicationError
):
    """Core could not safely complete a write or catalog operation."""


@dataclass(frozen=True, slots=True)
class PublicationCatalogReconciliation:
    build: AcademicCatalogBuildResult
    publication: CatalogPublication


@dataclass(frozen=True, slots=True)
class QuillanPublicationSeriesState:
    work: ModuleWorkRef
    publications: tuple[PublicationRecord, ...]
    withdrawals: tuple[PublicationWithdrawal, ...]
    producer_revisions: tuple[int, ...]
    producer_head: StoredAcademicResultManifest | None
    core_head: PublicationRecord | None
    core_head_withdrawal: PublicationWithdrawal | None
    current_selectable_publication: PublicationRecord | None
    derived_catalog_available: bool
    derived_catalog_rows: tuple[CatalogPublication, ...]

    @property
    def head(self) -> PublicationRecord | None:
        return self.core_head

    @property
    def producer_head_revision(self) -> int | None:
        return None if self.producer_head is None else self.producer_head.revision

    @property
    def catalog_available(self) -> bool:
        return self.derived_catalog_available

    @property
    def catalog_rows(self) -> tuple[CatalogPublication, ...]:
        return self.derived_catalog_rows


@dataclass(frozen=True, slots=True)
class AcademicResultPublicationResult:
    operation: PublicationOperation
    disposition: Literal["created", "existing"]
    publication: PublicationRecord
    withdrawal: PublicationWithdrawal | None
    registration: AcademicWorkRegistration
    compatibility: PublicationCompatibilityResult
    catalog: PublicationCatalogReconciliation
    manifest_generation: AcademicResultManifestGenerationResult | None = None


@dataclass(frozen=True, slots=True)
class AcademicResultWithdrawalResult:
    disposition: Literal["created", "existing"]
    publication: PublicationRecord
    withdrawal: PublicationWithdrawal
    catalog: PublicationCatalogReconciliation
    manifest_verification: WithdrawalManifestVerification


@dataclass(frozen=True, slots=True)
class PublicationPartialSuccessState:
    operation: PublicationOperation
    publication: PublicationRecord | None
    withdrawal: PublicationWithdrawal | None
    manifest: StoredAcademicResultManifest | None
    canonical_state: Literal["uncertain", "confirmed"]
    catalog_rebuild_attempted: bool
    catalog_replacement_completed: bool
    catalog_verification_completed: bool
    recommended_next_action: str
    catalog_build: AcademicCatalogBuildResult | None = None
    catalog_error: Exception | None = None
    withdrawal_manifest_verification: WithdrawalManifestVerification | None = None

    @property
    def canonical_state_confirmed(self) -> bool:
        return self.canonical_state == "confirmed"

    @property
    def catalog_installed(self) -> bool:
        return self.catalog_replacement_completed

    @property
    def catalog_verified(self) -> bool:
        return self.catalog_verification_completed


class QuillanAcademicResultPublicationPartialSuccessError(
    QuillanAcademicResultPublicationError
):
    def __init__(self, message: str, state: PublicationPartialSuccessState) -> None:
        super().__init__(message)
        self.state = state


def _work(class_id: str, assignment_id: str) -> ModuleWorkRef:
    try:
        return quillan_work_ref(class_id, assignment_id)
    except (TypeError, ValueError) as error:
        raise QuillanAcademicResultPublicationValidationError(str(error)) from error


def _validate_publication(
    publication: PublicationRecord, work: ModuleWorkRef
) -> PublicationRecord:
    if not isinstance(publication, PublicationRecord):
        raise QuillanAcademicResultPublicationIntegrityError(
            "Canonical publication has the wrong model type."
        )
    try:
        expected_path = academic_result_manifest_relative_path(
            work, publication.record_set_revision
        )
    except (TypeError, ValueError) as error:
        raise QuillanAcademicResultPublicationIntegrityError(
            "Canonical publication has an invalid producer revision."
        ) from error
    registration_revision = publication.academic_work_registration_revision
    if (
        publication.work != work
        or publication.work.module_id != QUILLAN_MODULE_ID
        or publication.publication_kind != QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND
        or publication.record_set_id != QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID
        or publication.source_record is not None
        or publication.manifest_contract_version
        != ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
        or publication.capabilities != QUILLAN_PUBLICATION_CAPABILITIES
        or publication.manifest_path != expected_path
        or publication.manifest_digest_algorithm != "sha256"
        or isinstance(registration_revision, bool)
        or not isinstance(registration_revision, int)
        or registration_revision < 1
    ):
        raise QuillanAcademicResultPublicationIntegrityError(
            "Canonical publication contradicts Quillan's exact production contract."
        )
    return publication


def _series_head(records: tuple[PublicationRecord, ...]) -> PublicationRecord | None:
    try:
        series = validate_publication_record_series(records)
    except PublicationRecordError as error:
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error
    if not series:
        return None
    superseded = {
        item.supersedes_publication_id
        for item in series
        if item.supersedes_publication_id is not None
    }
    heads = tuple(item for item in series if item.publication_id not in superseded)
    if len(heads) != 1:
        raise QuillanAcademicResultPublicationIntegrityError(
            "Canonical publication series does not have exactly one head."
        )
    return heads[0]


def _load_series(root: str | Path, work: ModuleWorkRef) -> tuple[PublicationRecord, ...]:
    try:
        records = list_publication_record_set(
            root,
            work,
            QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
            QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
        )
    except PublicationStorageError as error:
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error
    for record in records:
        _validate_publication(record, work)
    _series_head(records)
    return records


def _logical(
    records: tuple[PublicationRecord, ...], revision: int
) -> PublicationRecord | None:
    matches = tuple(item for item in records if item.record_set_revision == revision)
    if len(matches) > 1:
        raise QuillanAcademicResultPublicationIntegrityError(
            "Canonical logical publication revision is duplicated."
        )
    return matches[0] if matches else None


def _matches_stored(
    publication: PublicationRecord, stored: StoredAcademicResultManifest
) -> bool:
    return (
        publication.record_set_revision == stored.revision
        and publication.manifest_path == stored.relative_path
        and publication.manifest_digest_algorithm == "sha256"
        and publication.manifest_digest == stored.sha256
        and publication.manifest_contract_version
        == ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION
        and publication.capabilities == QUILLAN_PUBLICATION_CAPABILITIES
        and publication.source_record is None
    )


def _expected_source(work: ModuleWorkRef) -> ModuleRecordRef:
    return ModuleRecordRef(
        module_id=QUILLAN_MODULE_ID,
        record_kind=QUILLAN_ASSIGNMENT_SOURCE_RECORD_KIND,
        record_id=work.work_id,
        contract_version=QUILLAN_ASSIGNMENT_SOURCE_CONTRACT_VERSION,
    )


def _validate_registration(
    registration: AcademicWorkRegistration, work: ModuleWorkRef
) -> AcademicWorkRegistration:
    if (
        not isinstance(registration, AcademicWorkRegistration)
        or registration.work != work
        or registration.producer_contract_version
        != QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION
        or registration.work_kind != QUILLAN_ACADEMIC_WORK_KIND
        or registration.source_records != (_expected_source(work),)
    ):
        raise QuillanAcademicResultPublicationIntegrityError(
            "Academic Work Registration contradicts Quillan's exact contract."
        )
    if registration.lifecycle == "cancelled":
        raise QuillanAcademicResultPublicationConflictError(
            "A cancelled Academic Work Registration cannot support publication."
        )
    return registration


def _current_registration(root: str | Path, work: ModuleWorkRef) -> AcademicWorkRegistration:
    try:
        value = load_current_academic_work_registration(root, work)
    except AcademicWorkRegistrationStorageError as error:
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error
    if value is None:
        raise QuillanAcademicResultPublicationNotFoundError(
            "No current Academic Work Registration exists."
        )
    return _validate_registration(value, work)


def _bound_registration(
    root: str | Path, work: ModuleWorkRef, publication: PublicationRecord
) -> AcademicWorkRegistration:
    revision = publication.academic_work_registration_revision
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise QuillanAcademicResultPublicationIntegrityError(
            "Academic publication has no valid registration revision."
        )
    try:
        value = load_academic_work_registration_revision(root, work, revision)
    except AcademicWorkRegistrationStorageError as error:
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error
    return _validate_registration(value, work)


def _producer_head(
    root: str | Path, work: ModuleWorkRef, revision: int
) -> StoredAcademicResultManifest:
    try:
        history = list_academic_result_manifest_revisions(root, work)
    except QuillanManifestGenerationError as error:
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error
    if not history:
        raise QuillanAcademicResultPublicationNotFoundError(
            "No immutable Academic Result Manifest exists."
        )
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise QuillanAcademicResultPublicationValidationError(
            "manifest_revision must be a positive integer."
        )
    if history[-1].revision != revision:
        raise QuillanAcademicResultPublicationConflictError(
            "Selected manifest revision is not the producer head."
        )
    return history[-1]


def _request(
    stored: StoredAcademicResultManifest, registration: AcademicWorkRegistration
) -> PublicationManifestRequest:
    try:
        return PublicationManifestRequest(
            work=registration.work,
            source_record=None,
            publication_kind=QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
            capabilities=QUILLAN_PUBLICATION_CAPABILITIES,
            record_set_id=QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
            record_set_revision=stored.revision,
            manifest_contract_version=ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
            manifest_path=stored.relative_path,
            academic_work_registration_revision=registration.registration_revision,
            expected_manifest_digest=stored.sha256,
        )
    except (RegistryServiceValidationError, TypeError, ValueError) as error:
        raise QuillanAcademicResultPublicationValidationError(str(error)) from error


def _catalog_query(work: ModuleWorkRef) -> PublicationCatalogQuery:
    return PublicationCatalogQuery(
        class_id=work.class_id,
        module_id=work.module_id,
        work_id=work.work_id,
        publication_kind=QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND,
        record_set_id=QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
        state="all",
    )


class _CatalogFailure(Exception):
    def __init__(
        self, error: Exception, build: AcademicCatalogBuildResult | None
    ) -> None:
        super().__init__(str(error))
        self.error = error
        self.build = build


def _raise_catalog(error: AcademicCatalogError) -> NoReturn:
    if isinstance(error, AcademicCatalogValidationError):
        raise QuillanAcademicResultPublicationValidationError(str(error)) from error
    if isinstance(error, AcademicCatalogNotFoundError):
        raise QuillanAcademicResultPublicationNotFoundError(str(error)) from error
    if isinstance(error, AcademicCatalogConflictError):
        raise QuillanAcademicResultPublicationConflictError(str(error)) from error
    if isinstance(
        error,
        (
            AcademicCatalogSourceError,
            AcademicCatalogIntegrityError,
            AcademicCatalogCompatibilityError,
            AcademicCatalogReadError,
        ),
    ):
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error
    if isinstance(error, AcademicCatalogBuildError):
        raise QuillanAcademicResultPublicationWriteError(str(error)) from error
    raise QuillanAcademicResultPublicationWriteError(str(error)) from error


def _reconcile_catalog(
    root: str | Path,
    work: ModuleWorkRef,
    publication: PublicationRecord,
    withdrawal: PublicationWithdrawal | None,
) -> PublicationCatalogReconciliation:
    try:
        build = rebuild_academic_catalog(root)
    except AcademicCatalogError as error:
        raise _CatalogFailure(error, None) from error
    try:
        rows = query_publication_catalog(root, _catalog_query(work))
        matches = tuple(
            row for row in rows if row.publication_id == publication.publication_id
        )
        if len(matches) != 1:
            raise QuillanAcademicResultPublicationIntegrityError(
                "Rebuilt catalog does not contain exactly one publication row."
            )
        row = matches[0]
        head = _series_head(_load_series(root, work))
        is_head = head is not None and head.publication_id == publication.publication_id
        record_values = (
            publication.work,
            publication.source_record,
            publication.publication_kind,
            publication.capabilities,
            publication.record_set_id,
            publication.record_set_revision,
            publication.manifest_contract_version,
            publication.manifest_path,
            publication.manifest_digest_algorithm,
            publication.manifest_digest,
            publication.published_at,
            publication.academic_work_registration_revision,
            publication.supersedes_publication_id,
        )
        row_values = (
            row.work,
            row.source_record,
            row.publication_kind,
            row.capabilities,
            row.record_set_id,
            row.record_set_revision,
            row.manifest_contract_version,
            row.manifest_path,
            row.manifest_digest_algorithm,
            row.manifest_digest,
            row.published_at,
            row.academic_work_registration_revision,
            row.supersedes_publication_id,
        )
        if (
            row_values != record_values
            or row.is_series_head != is_head
            or row.is_withdrawn != (withdrawal is not None)
            or row.withdrawn_at != (withdrawal.withdrawn_at if withdrawal else None)
            or row.is_current_selectable != (is_head and withdrawal is None)
        ):
            raise QuillanAcademicResultPublicationIntegrityError(
                "Rebuilt catalog row disagrees with canonical publication state."
            )
        return PublicationCatalogReconciliation(build, row)
    except Exception as error:
        raise _CatalogFailure(error, build) from error


def load_quillan_publication(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    publication_id: str,
) -> tuple[PublicationRecord, PublicationWithdrawal | None]:
    work = _work(class_id, assignment_id)
    try:
        publication = get_canonical_publication_record(workspace_root, publication_id)
        withdrawal = get_canonical_publication_withdrawal(
            workspace_root, publication_id
        )
    except RegistryServiceError as error:
        _raise_registry(error)
    return _validate_publication(publication, work), withdrawal


def load_quillan_publication_series_status(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> QuillanPublicationSeriesState:
    work = _work(class_id, assignment_id)
    records = _load_series(workspace_root, work)
    try:
        history = list_academic_result_manifest_revisions(workspace_root, work)
    except QuillanManifestGenerationError as error:
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error
    withdrawals = []
    for record in records:
        try:
            item = get_canonical_publication_withdrawal(
                workspace_root, record.publication_id
            )
        except RegistryServiceError as error:
            _raise_registry(error)
        if item is not None:
            withdrawals.append(item)
    try:
        load_academic_catalog_metadata(workspace_root)
        rows = query_publication_catalog(workspace_root, _catalog_query(work))
        available = True
    except AcademicCatalogNotFoundError:
        rows = ()
        available = False
    except AcademicCatalogError as error:
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error
    head = _series_head(records)
    withdrawal_by_id = {item.publication_id: item for item in withdrawals}
    head_withdrawal = (
        None if head is None else withdrawal_by_id.get(head.publication_id)
    )
    return QuillanPublicationSeriesState(
        work=work,
        publications=records,
        withdrawals=tuple(withdrawals),
        producer_revisions=tuple(item.revision for item in history),
        producer_head=history[-1] if history else None,
        core_head=head,
        core_head_withdrawal=head_withdrawal,
        current_selectable_publication=(
            head if head is not None and head_withdrawal is None else None
        ),
        derived_catalog_available=available,
        derived_catalog_rows=rows,
    )


def rebuild_quillan_publication_catalog(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    publication_id: str,
) -> PublicationCatalogReconciliation:
    work = _work(class_id, assignment_id)
    publication, withdrawal = load_quillan_publication(
        workspace_root, class_id, assignment_id, publication_id
    )
    try:
        return _reconcile_catalog(workspace_root, work, publication, withdrawal)
    except _CatalogFailure as failure:
        if isinstance(failure.error, AcademicCatalogError):
            _raise_catalog(failure.error)
        if isinstance(failure.error, QuillanAcademicResultPublicationError):
            raise failure.error from failure
        raise QuillanAcademicResultPublicationIntegrityError(
            "Catalog reconciliation failed."
        ) from failure.error


def rebuild_full_academic_catalog(
    workspace_root: str | Path,
) -> AcademicCatalogBuildResult:
    try:
        return rebuild_academic_catalog(workspace_root)
    except AcademicCatalogError as error:
        _raise_catalog(error)


def _verify_result(
    root: str | Path,
    work: ModuleWorkRef,
    service: PublicationServiceResult,
    stored: StoredAcademicResultManifest,
    operation: PublicationOperation,
    *,
    generation: AcademicResultManifestGenerationResult | None = None,
) -> AcademicResultPublicationResult:
    catalog_attempted = False
    try:
        canonical, withdrawal = load_quillan_publication(
            root, work.class_id, work.work_id, service.publication.publication_id
        )
        if canonical != service.publication or withdrawal != service.withdrawal:
            raise QuillanAcademicResultPublicationIntegrityError(
                "Canonical reload differs from Core's service result."
            )
        if canonical not in validate_publication_record_series(_load_series(root, work)):
            raise QuillanAcademicResultPublicationIntegrityError(
                "Canonical publication is absent from its series."
            )
        if not _matches_stored(canonical, stored):
            raise QuillanAcademicResultPublicationIntegrityError(
                "Canonical publication does not bind the selected producer bytes."
            )
        resolved = verify_publication_manifest(root, canonical)
        if resolved != stored.path.resolve(strict=True):
            raise QuillanAcademicResultPublicationIntegrityError(
                "Core resolved a different manifest path."
            )
        registration = _bound_registration(root, work, canonical)
        compatibility = evaluate_publication_compatibility(
            canonical, get_publication_producer_profile(), registration
        )
        if not compatibility.compatible or compatibility.codes != ():
            raise QuillanAcademicResultPublicationIntegrityError(
                "Publication is incompatible with Quillan's producer profile."
            )
        catalog_attempted = True
        try:
            catalog = _reconcile_catalog(root, work, canonical, withdrawal)
        except _CatalogFailure as failure:
            raise QuillanAcademicResultPublicationPartialSuccessError(
                "Core publication is durable but catalog reconciliation failed.",
                PublicationPartialSuccessState(
                    operation=operation,
                    publication=canonical,
                    withdrawal=withdrawal,
                    manifest=stored,
                    canonical_state="confirmed",
                    catalog_rebuild_attempted=True,
                    catalog_replacement_completed=failure.build is not None,
                    catalog_verification_completed=False,
                    recommended_next_action=(
                        "Replay the exact operation or run rebuild-catalog."
                    ),
                    catalog_build=failure.build,
                    catalog_error=failure.error,
                ),
            ) from failure.error
        return AcademicResultPublicationResult(
            operation,
            service.disposition,
            canonical,
            withdrawal,
            registration,
            compatibility,
            catalog,
            generation,
        )
    except QuillanAcademicResultPublicationPartialSuccessError:
        raise
    except Exception as error:
        raise QuillanAcademicResultPublicationPartialSuccessError(
            "Core publication is durable but post-write verification failed.",
            PublicationPartialSuccessState(
                operation=operation,
                publication=service.publication,
                withdrawal=service.withdrawal,
                manifest=stored,
                canonical_state="confirmed",
                catalog_rebuild_attempted=catalog_attempted,
                catalog_replacement_completed=False,
                catalog_verification_completed=False,
                recommended_next_action=(
                    "Replay the exact operation or run rebuild-catalog."
                ),
                catalog_error=error if catalog_attempted else None,
            ),
        ) from error


def publish_quillan_academic_results(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    manifest_revision: int,
) -> AcademicResultPublicationResult:
    work = _work(class_id, assignment_id)
    stored = _producer_head(workspace_root, work, manifest_revision)
    records = _load_series(workspace_root, work)
    logical = _logical(records, stored.revision)
    if logical is not None:
        if logical.supersedes_publication_id is not None:
            raise QuillanAcademicResultPublicationConflictError(
                "Selected logical revision is a supersession."
            )
        if not _matches_stored(logical, stored):
            raise QuillanAcademicResultPublicationIntegrityError(
                "Existing publication contradicts producer bytes."
            )
        registration = _bound_registration(workspace_root, work, logical)
    else:
        if records:
            raise QuillanAcademicResultPublicationConflictError(
                "Publication series is nonempty; use supersede."
            )
        registration = _current_registration(workspace_root, work)
    try:
        service = publish_manifest_revision(
            workspace_root, _request(stored, registration)
        )
    except RegistryServiceError as error:
        _raise_registry(error, operation="publish", manifest=stored)
    return _verify_result(workspace_root, work, service, stored, "publish")


def supersede_quillan_academic_results(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    manifest_revision: int,
    expected_current_publication_id: str,
) -> AcademicResultPublicationResult:
    work = _work(class_id, assignment_id)
    stored = _producer_head(workspace_root, work, manifest_revision)
    records = _load_series(workspace_root, work)
    expected = next(
        (x for x in records if x.publication_id == expected_current_publication_id),
        None,
    )
    if expected is None:
        raise QuillanAcademicResultPublicationConflictError(
            "Expected publication ID does not belong to the canonical series."
        )
    logical = _logical(records, stored.revision)
    if logical is not None:
        if logical.supersedes_publication_id != expected_current_publication_id:
            raise QuillanAcademicResultPublicationIntegrityError(
                "Existing logical revision has a contradictory predecessor."
            )
        if not _matches_stored(logical, stored):
            raise QuillanAcademicResultPublicationIntegrityError(
                "Existing publication contradicts producer bytes."
            )
        registration = _bound_registration(workspace_root, work, logical)
    else:
        head = _series_head(records)
        if head is None:
            raise QuillanAcademicResultPublicationNotFoundError(
                "Publication series does not exist."
            )
        if head.publication_id != expected_current_publication_id:
            raise QuillanAcademicResultPublicationConflictError(
                "Expected publication ID is not the canonical series head."
            )
        try:
            withdrawal = get_canonical_publication_withdrawal(
                workspace_root, head.publication_id
            )
        except RegistryServiceError as error:
            _raise_registry(error)
        if withdrawal is not None:
            raise QuillanAcademicResultPublicationConflictError(
                "The canonical series head is withdrawn; use republish-after-withdrawal."
            )
        if stored.revision <= head.record_set_revision:
            raise QuillanAcademicResultPublicationConflictError(
                "Successor producer revision must be greater than the canonical head revision."
            )
        registration = _current_registration(workspace_root, work)
    try:
        predecessor = load_academic_result_manifest_revision(
            workspace_root, work, expected.record_set_revision
        )
        validate_manifest_revision_transition(predecessor.manifest, stored.manifest)
    except QuillanManifestGenerationError as error:
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error
    except QuillanPublicationRevisionPolicyError as error:
        raise QuillanAcademicResultPublicationConflictError(str(error)) from error
    try:
        service = supersede_manifest_revision(
            workspace_root,
            _request(stored, registration),
            expected_current_publication_id=expected_current_publication_id,
        )
    except RegistryServiceError as error:
        _raise_registry(error, operation="supersede", manifest=stored)
    return _verify_result(workspace_root, work, service, stored, "supersede")


def _withdrawal_manifest_state(
    root: str | Path, publication: PublicationRecord
) -> WithdrawalManifestVerification:
    try:
        verify_publication_manifest(root, publication)
        return "verified"
    except PublicationManifestNotFoundError:
        return "missing"
    except PublicationManifestIntegrityError:
        return "digest_mismatch_or_unsafe"
    except (PublicationManifestError, OSError):
        return "unreadable"


def withdraw_quillan_academic_result_publication(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    publication_id: str,
    reason: str,
) -> AcademicResultWithdrawalResult:
    publication, _ = load_quillan_publication(
        workspace_root, class_id, assignment_id, publication_id
    )
    verification = _withdrawal_manifest_state(workspace_root, publication)
    try:
        service = withdraw_publication(
            workspace_root,
            PublicationWithdrawalRequest(publication_id=publication_id, reason=reason),
        )
    except RegistryServiceError as error:
        _raise_registry(
            error,
            operation="withdraw",
            withdrawal_manifest_verification=verification,
        )
    try:
        canonical, withdrawal = load_quillan_publication(
            workspace_root, class_id, assignment_id, publication_id
        )
        if (
            canonical != publication
            or canonical != service.publication
            or withdrawal != service.withdrawal
        ):
            raise QuillanAcademicResultPublicationIntegrityError(
                "Canonical withdrawal reload differs from Core's service result."
            )
        try:
            catalog = _reconcile_catalog(
                workspace_root, canonical.work, canonical, withdrawal
            )
        except _CatalogFailure as failure:
            raise QuillanAcademicResultPublicationPartialSuccessError(
                "Core withdrawal is durable but catalog reconciliation failed.",
                PublicationPartialSuccessState(
                    operation="withdraw",
                    publication=canonical,
                    withdrawal=withdrawal,
                    manifest=None,
                    canonical_state="confirmed",
                    catalog_rebuild_attempted=True,
                    catalog_replacement_completed=failure.build is not None,
                    catalog_verification_completed=False,
                    recommended_next_action=(
                        "Replay the exact withdrawal or run rebuild-catalog."
                    ),
                    catalog_build=failure.build,
                    catalog_error=failure.error,
                    withdrawal_manifest_verification=verification,
                ),
            ) from failure.error
        return AcademicResultWithdrawalResult(
            service.disposition, canonical, service.withdrawal, catalog, verification
        )
    except QuillanAcademicResultPublicationPartialSuccessError:
        raise
    except Exception as error:
        raise QuillanAcademicResultPublicationPartialSuccessError(
            "Core withdrawal is durable but post-write verification failed.",
            PublicationPartialSuccessState(
                operation="withdraw",
                publication=service.publication,
                withdrawal=service.withdrawal,
                manifest=None,
                canonical_state="confirmed",
                catalog_rebuild_attempted=False,
                catalog_replacement_completed=False,
                catalog_verification_completed=False,
                recommended_next_action=(
                    "Replay the exact withdrawal or run rebuild-catalog."
                ),
                withdrawal_manifest_verification=verification,
            ),
        ) from error


def republish_quillan_academic_results_after_withdrawal(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    expected_withdrawn_head_publication_id: str,
) -> AcademicResultPublicationResult:
    work = _work(class_id, assignment_id)
    records = _load_series(workspace_root, work)
    head = _series_head(records)
    if head is None:
        raise QuillanAcademicResultPublicationNotFoundError(
            "Publication series does not exist."
        )
    expected = next(
        (x for x in records if x.publication_id == expected_withdrawn_head_publication_id),
        None,
    )
    if expected is None:
        raise QuillanAcademicResultPublicationConflictError(
            "Expected publication ID does not belong to the canonical series."
        )
    exact_core_replay = (
        head.publication_id != expected.publication_id
        and head.supersedes_publication_id == expected.publication_id
    )
    if head.publication_id != expected.publication_id and not exact_core_replay:
        raise QuillanAcademicResultPublicationConflictError(
            "Expected publication is not the withdrawn head or exact retry predecessor."
        )
    try:
        expected_withdrawal = get_canonical_publication_withdrawal(
            workspace_root, expected.publication_id
        )
    except RegistryServiceError as error:
        _raise_registry(error)
    if expected_withdrawal is None:
        raise QuillanAcademicResultPublicationConflictError(
            "The expected predecessor is not withdrawn."
        )
    try:
        predecessor = load_academic_result_manifest_revision(
            workspace_root, work, expected.record_set_revision
        )
        history = list_academic_result_manifest_revisions(workspace_root, work)
    except QuillanManifestGenerationError as error:
        raise QuillanAcademicResultPublicationIntegrityError(
            "Withdrawn predecessor manifest is unavailable or invalid."
        ) from error

    generation: AcademicResultManifestGenerationResult | None = None
    if exact_core_replay:
        try:
            successor_withdrawal = get_canonical_publication_withdrawal(
                workspace_root, head.publication_id
            )
        except RegistryServiceError as error:
            _raise_registry(error)
        if successor_withdrawal is not None:
            raise QuillanAcademicResultPublicationConflictError(
                "The already-created republication successor is itself withdrawn."
            )
        if not history or history[-1].revision != head.record_set_revision:
            raise QuillanAcademicResultPublicationIntegrityError(
                "Canonical republication retry does not match the producer head."
            )
        stored = history[-1]
        if not _matches_stored(head, stored):
            raise QuillanAcademicResultPublicationIntegrityError(
                "Canonical republication retry contradicts producer bytes."
            )
        registration = _bound_registration(workspace_root, work, head)
    elif history and history[-1].revision > expected.record_set_revision:
        stored = history[-1]
        if _logical(records, stored.revision) is not None:
            raise QuillanAcademicResultPublicationIntegrityError(
                "Greater producer head is already represented by Core state."
            )
        registration = _current_registration(workspace_root, work)
    else:
        if not history or history[-1].revision != expected.record_set_revision:
            raise QuillanAcademicResultPublicationIntegrityError(
                "Producer history does not end at the withdrawn predecessor."
            )
        try:
            generation = generate_academic_result_manifest(
                workspace_root,
                class_id,
                assignment_id,
                republish_after_withdrawal=True,
            )
        except QuillanManifestGenerationPartialSuccessError as error:
            raise QuillanAcademicResultPublicationPartialSuccessError(
                "A republication manifest may be durable.",
                PublicationPartialSuccessState(
                    operation="republish_after_withdrawal",
                    publication=None,
                    withdrawal=expected_withdrawal,
                    manifest=None,
                    canonical_state="confirmed",
                    catalog_rebuild_attempted=False,
                    catalog_replacement_completed=False,
                    catalog_verification_completed=False,
                    recommended_next_action=(
                        "Retry republication; any durable producer revision will be reused."
                    ),
                ),
            ) from error
        except QuillanManifestGenerationError as error:
            raise QuillanAcademicResultPublicationWriteError(str(error)) from error
        stored = StoredAcademicResultManifest(
            generation.manifest,
            generation.revision,
            generation.path,
            generation.relative_path,
            generation.content,
            generation.sha256,
        )
        if generation.reason != "republication_after_withdrawal":
            raise QuillanAcademicResultPublicationIntegrityError(
                "Republication did not use the explicit revision-policy reason."
            )
        registration = _current_registration(workspace_root, work)

    if stored.revision <= expected.record_set_revision:
        raise QuillanAcademicResultPublicationConflictError(
            "Republication producer revision must be greater than the withdrawn predecessor."
        )
    try:
        validate_manifest_revision_transition(predecessor.manifest, stored.manifest)
    except QuillanPublicationRevisionPolicyError as error:
        raise QuillanAcademicResultPublicationIntegrityError(str(error)) from error

    try:
        service = supersede_manifest_revision(
            workspace_root,
            _request(stored, registration),
            expected_current_publication_id=expected.publication_id,
        )
    except RegistryServiceError as error:
        try:
            _raise_registry(
                error,
                operation="republish_after_withdrawal",
                manifest=stored,
            )
        except QuillanAcademicResultPublicationPartialSuccessError:
            raise
        except QuillanAcademicResultPublicationError as normalized:
            if generation is None:
                raise
            raise QuillanAcademicResultPublicationPartialSuccessError(
                "A successor manifest is durable but Core publication did not complete.",
                PublicationPartialSuccessState(
                    operation="republish_after_withdrawal",
                    publication=None,
                    withdrawal=expected_withdrawal,
                    manifest=stored,
                    canonical_state="confirmed",
                    catalog_rebuild_attempted=False,
                    catalog_replacement_completed=False,
                    catalog_verification_completed=False,
                    recommended_next_action=(
                        "Retry republication; the durable producer revision will be reused."
                    ),
                ),
            ) from normalized
        raise AssertionError("unreachable")

    return _verify_result(
        workspace_root,
        work,
        service,
        stored,
        "republish_after_withdrawal",
        generation=generation,
    )


def _raise_registry(
    error: Exception,
    *,
    operation: PublicationOperation | None = None,
    manifest: StoredAcademicResultManifest | None = None,
    withdrawal_manifest_verification: WithdrawalManifestVerification | None = None,
) -> NoReturn:
    if isinstance(error, RegistryServicePartialSuccessError):
        core = error.state
        if operation is None:
            operation_map: dict[str, PublicationOperation] = {
                "publish_manifest_revision": "publish",
                "supersede_manifest_revision": "supersede",
                "withdraw_publication": "withdraw",
            }
            local_operation = operation_map.get(core.operation)
            if local_operation is None:
                raise QuillanAcademicResultPublicationIntegrityError(
                    "Unexpected Core partial-success operation at the publication boundary."
                ) from error
        else:
            local_operation = operation
        raise QuillanAcademicResultPublicationPartialSuccessError(
            str(error),
            PublicationPartialSuccessState(
                operation=local_operation,
                publication=core.publication,
                withdrawal=core.withdrawal,
                manifest=manifest,
                canonical_state="uncertain",
                catalog_rebuild_attempted=False,
                catalog_replacement_completed=False,
                catalog_verification_completed=False,
                recommended_next_action=(
                    "Replay the exact operation to reconcile canonical state."
                ),
                withdrawal_manifest_verification=withdrawal_manifest_verification,
            ),
        ) from error
    mappings = (
        (RegistryServiceValidationError, QuillanAcademicResultPublicationValidationError),
        (RegistryServiceNotFoundError, QuillanAcademicResultPublicationNotFoundError),
        (RegistryServiceConflictError, QuillanAcademicResultPublicationConflictError),
        (RegistryServiceIntegrityError, QuillanAcademicResultPublicationIntegrityError),
        (RegistryServiceWriteError, QuillanAcademicResultPublicationWriteError),
    )
    for core_type, local_type in mappings:
        if isinstance(error, core_type):
            raise local_type(str(error)) from error
    raise error


__all__ = [
    "QUILLAN_ACADEMIC_RESULT_PUBLICATION_KIND",
    "QUILLAN_PUBLICATION_CAPABILITIES",
    "AcademicResultPublicationResult",
    "AcademicResultWithdrawalResult",
    "WithdrawalManifestVerification",
    "PublicationCatalogReconciliation",
    "PublicationPartialSuccessState",
    "QuillanPublicationSeriesState",
    "QuillanAcademicResultPublicationError",
    "QuillanAcademicResultPublicationValidationError",
    "QuillanAcademicResultPublicationNotFoundError",
    "QuillanAcademicResultPublicationConflictError",
    "QuillanAcademicResultPublicationIntegrityError",
    "QuillanAcademicResultPublicationWriteError",
    "QuillanAcademicResultPublicationPartialSuccessError",
    "load_quillan_publication_series_status",
    "load_quillan_publication",
    "publish_quillan_academic_results",
    "supersede_quillan_academic_results",
    "republish_quillan_academic_results_after_withdrawal",
    "withdraw_quillan_academic_result_publication",
    "rebuild_quillan_publication_catalog",
    "rebuild_full_academic_catalog",
]

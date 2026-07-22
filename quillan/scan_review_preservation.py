"""Preserve actionable retained-intake failures with Core schema version 2."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from uuid import uuid4

from pds_core.module_dispatch import RouteDispatchFailure, RouteDispatchSuccess
from pds_core.module_profiles import ModuleProfile
from pds_core.routing_models import (
    ModuleRecordRef,
    RouteRegistration,
    RouteResolution,
    validate_module_record_ref,
)
from pds_core.scan_failure_metadata import (
    ROUTING_FAILURE_SCHEMA_VERSION,
    RoutingFailureMetadata,
    RoutingFailureMetadataWriteError,
    load_routing_failure_metadata,
    routing_failure_metadata_from_dispatch_failure,
    routing_failure_metadata_path,
    write_routing_failure_metadata,
)
from pds_core.scan_retention import RetainedSourceScan

from quillan.module_errors import (
    QuillanScanPreflightError,
    QuillanScanReviewPersistenceError,
)
from quillan.pds2_scan_intake import (
    PersistedQuillanScanFailure,
    QuillanFailurePersistenceBatch,
    QuillanFailurePersistenceError,
    QuillanScanPageOutcome,
    QuillanScanSourceResult,
    RoutingReviewRecord,
    validate_scan_workspace,
)

_MAX_FAILURE_ID_ATTEMPTS = 8
_MetadataBuilder = Callable[[str, str], RoutingFailureMetadata]


class _OccurrencePersistenceFailure(Exception):
    def __init__(
        self,
        error: QuillanScanReviewPersistenceError,
        *,
        durable_path: Path | None = None,
    ) -> None:
        super().__init__(str(error))
        self.error = error
        self.durable_path = durable_path


def preserve_quillan_scan_failures(
    workspace_root: Path,
    source_result: QuillanScanSourceResult,
) -> QuillanFailurePersistenceBatch:
    """Persist each actionable post-retention occurrence independently."""
    try:
        root = validate_scan_workspace(workspace_root)
    except QuillanScanPreflightError as error:
        raise QuillanScanReviewPersistenceError(
            f"Invalid scan-review persistence workspace: {error}"
        ) from error
    if not isinstance(source_result, QuillanScanSourceResult):
        raise QuillanScanReviewPersistenceError(
            "source_result must be QuillanScanSourceResult."
        )
    if source_result.retained_source is None:
        return QuillanFailurePersistenceBatch((), ())

    persisted: list[PersistedQuillanScanFailure] = []
    failures: list[QuillanFailurePersistenceError] = []
    if source_result.source_error is not None:
        _persist_occurrence(
            persisted,
            failures,
            None,
            "source_page_loading",
            lambda: _persist_source_error(root, source_result),
        )
    for page in source_result.pages:
        if page.terminal_category == "dispatch_success":
            continue
        origin = _origin_for_page(page)
        _persist_occurrence(
            persisted,
            failures,
            page.source_page_number,
            origin,
            partial(_persist_page, root, page, origin),
        )
    return QuillanFailurePersistenceBatch(tuple(persisted), tuple(failures))


def preserve_and_attach_quillan_scan_failures(
    workspace_root: Path,
    source_result: QuillanScanSourceResult,
) -> QuillanScanSourceResult:
    """Attach persistence outcomes without changing primary terminal states."""
    batch = preserve_quillan_scan_failures(workspace_root, source_result)
    records = {item.source_page_number: item for item in batch.persisted}
    failures = {item.source_page_number: item for item in batch.failures}
    pages = tuple(
        replace(
            page,
            review_record=records.get(page.source_page_number),
            review_error=failures.get(page.source_page_number),
        )
        for page in source_result.pages
    )
    return replace(
        source_result,
        pages=pages,
        scan_review_record=records.get(None),
        scan_review_error=failures.get(None),
    )


def _persist_occurrence(
    persisted: list[PersistedQuillanScanFailure],
    failures: list[QuillanFailurePersistenceError],
    page_number: int | None,
    origin: str,
    operation: Callable[[], RoutingReviewRecord],
) -> None:
    try:
        persisted.append(operation())
    except _OccurrencePersistenceFailure as failure:
        failures.append(
            QuillanFailurePersistenceError(
                page_number,
                origin,
                failure.error,
                failure.durable_path,
            )
        )
    except Exception as error:
        wrapped = _persistence_error(error)
        failures.append(
            QuillanFailurePersistenceError(
                page_number,
                origin,
                wrapped,
            )
        )


def _persist_page(
    root: Path,
    page: QuillanScanPageOutcome,
    origin: str,
) -> RoutingReviewRecord:
    def build(failure_id: str, created_at: str) -> RoutingFailureMetadata:
        if (
            page.terminal_category == "core_dispatch_failure"
            and isinstance(page.dispatch_outcome, RouteDispatchFailure)
        ):
            return routing_failure_metadata_from_dispatch_failure(
                page.dispatch_outcome,
                failure_id=failure_id,
                created_at=created_at,
                detected_payload=page.raw_payload_text,
                module_details={
                    "failure_origin": origin,
                    "failure_owner": "quillan",
                },
            )
        stage = (
            "dispatch_integration"
            if page.failure_stage == "core_outcome_validation"
            else page.failure_stage or "dispatch_integration"
        )
        return RoutingFailureMetadata(
            schema_version=ROUTING_FAILURE_SCHEMA_VERSION,
            failure_id=failure_id,
            scope="page",
            stage=stage,
            created_at=created_at,
            failure_category=page.failure_category or "processing_error",
            failure_message=_failure_message(page.error),
            source_filename=page.retained_source.source_filename,
            source_scan_id=page.retained_source.source_scan_id,
            source_sha256=page.retained_source.source_sha256,
            retained_source_path=(
                page.retained_source.retained_source_relative_path
            ),
            review_copy_path=None,
            source_page_number=page.source_page_number,
            detected_payload=page.raw_payload_text,
            route_locator=page.locator,
            target=_authoritative_target_after_core_validation(page),
            module_details=_module_details(page, origin),
        )

    return _write_fresh(
        root,
        build,
        page.source_page_number,
        origin,
        page.retained_source,
    )


def _persist_source_error(
    root: Path,
    source: QuillanScanSourceResult,
) -> RoutingReviewRecord:
    retained = source.retained_source
    if retained is None or source.source_error is None:
        raise QuillanScanReviewPersistenceError(
            "retained source-level failure is incomplete."
        )

    def build(failure_id: str, created_at: str) -> RoutingFailureMetadata:
        return RoutingFailureMetadata(
            schema_version=ROUTING_FAILURE_SCHEMA_VERSION,
            failure_id=failure_id,
            scope="scan",
            stage="source_page_loading",
            created_at=created_at,
            failure_category="source_unreadable",
            failure_message=_failure_message(source.source_error),
            source_filename=retained.source_filename,
            source_scan_id=retained.source_scan_id,
            source_sha256=retained.source_sha256,
            retained_source_path=retained.retained_source_relative_path,
            review_copy_path=None,
            source_page_number=None,
            detected_payload=None,
            route_locator=None,
            target=None,
            module_details={
                "failure_origin": "source_page_loading",
                "failure_owner": "quillan",
            },
        )

    return _write_fresh(
        root,
        build,
        None,
        "source_page_loading",
        retained,
    )


def _write_fresh(
    root: Path,
    builder: _MetadataBuilder,
    page_number: int | None,
    origin: str,
    retained_source: RetainedSourceScan,
) -> RoutingReviewRecord:
    for _ in range(_MAX_FAILURE_ID_ATTEMPTS):
        failure_id = f"failure_{uuid4().hex}"
        expected = routing_failure_metadata_path(root, failure_id).resolve(
            strict=False
        )
        if os.path.lexists(expected):
            continue
        created_at = datetime.now(timezone.utc).isoformat(
            timespec="microseconds"
        )
        metadata = builder(failure_id, created_at)
        try:
            written = write_routing_failure_metadata(root, metadata).resolve(
                strict=False
            )
        except RoutingFailureMetadataWriteError as error:
            if _exception_chain_contains(error, FileExistsError):
                continue
            wrapped = _persistence_error(error)
            raise _OccurrencePersistenceFailure(
                wrapped,
                durable_path=expected if os.path.lexists(expected) else None,
            ) from error
        except Exception as error:
            wrapped = _persistence_error(error)
            raise _OccurrencePersistenceFailure(
                wrapped,
                durable_path=expected if os.path.lexists(expected) else None,
            ) from error
        try:
            if written != expected:
                raise QuillanScanReviewPersistenceError(
                    "Core writer returned a noncanonical metadata path."
                )
            reloaded = load_routing_failure_metadata(root, failure_id)
            if reloaded != metadata:
                raise QuillanScanReviewPersistenceError(
                    "Reloaded failure metadata differs from the written record."
                )
            return RoutingReviewRecord(
                failure_id,
                metadata,
                written,
                written.relative_to(root).as_posix(),
                page_number,
                origin,
                retained_source,
                root,
            )
        except Exception as error:
            wrapped = _persistence_error(error)
            raise _OccurrencePersistenceFailure(
                wrapped,
                durable_path=(expected if os.path.lexists(expected) else written),
            ) from error
    raise _OccurrencePersistenceFailure(
        QuillanScanReviewPersistenceError(
            "Could not allocate a unique routing failure ID."
        )
    )


def _authoritative_target_after_core_validation(
    page: QuillanScanPageOutcome,
) -> ModuleRecordRef | None:
    if page.failure_stage != "quillan_result_validation":
        return None
    outcome = page.dispatch_outcome
    request = page.dispatch_request
    if (
        type(outcome) is not RouteDispatchSuccess
        or request is None
        or page.locator is None
    ):
        return None
    try:
        if outcome.request != request or outcome.request.retained_source is not request.retained_source:
            return None
        profile = outcome.profile
        if type(profile) is not ModuleProfile:
            return None
        if profile.module_id != page.locator.module_id:
            return None
        resolution = outcome.resolution
        if type(resolution) is not RouteResolution:
            return None
        if resolution.locator != page.locator:
            return None
        registration = resolution.registration
        if type(registration) is not RouteRegistration:
            return None
        if registration.locator != page.locator:
            return None
        target = registration.target
        if type(target) is not ModuleRecordRef:
            return None
        validate_module_record_ref(target)
        if target.module_id != page.locator.module_id:
            return None
        return target
    except Exception:
        return None


def _module_details(
    page: QuillanScanPageOutcome,
    origin: str,
) -> dict[str, str]:
    details = {
        "failure_origin": origin[:100],
        "failure_owner": "quillan",
    }
    if page.decode_method is not None:
        details["decode_method"] = page.decode_method[:200]
    if (
        page.failure_category == "payload_schema_unsupported"
        and page.raw_payload_text is not None
    ):
        details["declared_schema"] = page.raw_payload_text.split("|", 1)[0][:32]
    return details


def _origin_for_page(page: QuillanScanPageOutcome) -> str:
    if page.terminal_category == "core_dispatch_failure":
        return "core_dispatch"
    return page.failure_stage or "dispatch_integration"


def _failure_message(error: Exception | None) -> str:
    text = "Scan intake failed." if error is None else str(error)
    return (" ".join(text.split())[:1000] or "Scan intake failed.")


def _persistence_error(
    error: Exception,
) -> QuillanScanReviewPersistenceError:
    if isinstance(error, QuillanScanReviewPersistenceError):
        return error
    wrapped = QuillanScanReviewPersistenceError(
        f"Could not preserve scan failure: {error}"
    )
    wrapped.__cause__ = error
    return wrapped


def _exception_chain_contains(
    error: BaseException,
    expected: type[BaseException],
) -> bool:
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, expected):
            return True
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return False


__all__ = [
    "PersistedQuillanScanFailure",
    "QuillanFailurePersistenceBatch",
    "QuillanFailurePersistenceError",
    "RoutingReviewRecord",
    "preserve_and_attach_quillan_scan_failures",
    "preserve_quillan_scan_failures",
]

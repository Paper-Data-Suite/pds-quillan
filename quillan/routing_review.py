"""Preserve Quillan scan-routing failures for teacher review."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pds_core.scan_failure_metadata import (
    RoutingFailureMetadata,
    RoutingFailureMetadataError,
    RoutingFailureMetadataWriteError,
    is_routing_failure_category,
    routing_failure_metadata_path,
    write_routing_failure_metadata,
)

from quillan.evidence_filing import (
    EvidenceFilingError,
    RetainedSourceScan,
)
from quillan.payload_validation import ResponsePayloadValidationFailure
from quillan.qr_decode import QrImageDecodeResult
from quillan.route_planning import RouteFailure, RoutePlan

_FAILURE_ID_DIGEST_LENGTH = 12


class RoutingReviewError(RuntimeError):
    """Raised when routing failure metadata cannot be preserved safely."""


@dataclass(frozen=True, slots=True)
class RoutingReviewRecord:
    """Provenance for one preserved routing failure metadata record."""

    failure_id: str
    failure_metadata_path: Path
    failure_metadata_relative_path: str
    failure_category: str
    failure_message: str
    retained_source_relative_path: str | None
    review_copy_relative_path: str | None


def preserve_routing_failure_for_review(
    workspace_root: str | Path,
    *,
    failure_category: str,
    failure_message: str,
    source_filename: str,
    module: str | None = "quillan",
    source_scan_id: str | None = None,
    source_sha256: str | None = None,
    retained_source_path: str | Path | None = None,
    review_copy_path: str | Path | None = None,
    source_page_number: int | None = None,
    detected_payload: str | None = None,
    payload_page_number: int | None = None,
    class_id: str | None = None,
    assignment_id: str | None = None,
    student_id: str | None = None,
    module_details: dict[str, object] | None = None,
    created_at: datetime | None = None,
) -> RoutingReviewRecord:
    """Write one shared routing failure record under ``scans/review/``."""
    root = _resolved_workspace_root(workspace_root)
    if not is_routing_failure_category(failure_category):
        raise RoutingReviewError(
            "failure_category must be a shared routing failure category."
        )

    retained_relative_path = _optional_workspace_relative_path(
        retained_source_path,
        root,
        "retained_source_path",
    )
    review_relative_path = _optional_workspace_relative_path(
        review_copy_path,
        root,
        "review_copy_path",
    )
    timestamp = _normalized_timestamp(created_at)
    failure_id = _build_failure_id(
        timestamp=timestamp,
        source_filename=source_filename,
        failure_category=failure_category,
        detected_payload=detected_payload,
        retained_source_path=retained_relative_path,
    )

    try:
        metadata = RoutingFailureMetadata(
            schema_version="1",
            failure_id=failure_id,
            scope="page",
            stage="quillan_route_review",
            created_at=timestamp.isoformat(timespec="microseconds"),
            failure_category=failure_category,
            failure_message=failure_message,
            source_filename=source_filename,
            module_details=(
                {} if module_details is None else dict(module_details)
            ),
            module=module,
            source_scan_id=source_scan_id,
            source_sha256=source_sha256,
            retained_source_path=retained_relative_path,
            review_copy_path=review_relative_path,
            source_page_number=source_page_number,
            detected_payload=detected_payload,
            payload_page_number=payload_page_number,
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
        )
        expected_path = routing_failure_metadata_path(root, failure_id).resolve(
            strict=False
        )
        written_path = write_routing_failure_metadata(root, metadata).resolve(
            strict=False
        )
    except (
        RoutingFailureMetadataError,
        RoutingFailureMetadataWriteError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        raise RoutingReviewError(
            f"Could not preserve routing failure metadata: {error}"
        ) from error

    if written_path != expected_path:
        raise RoutingReviewError(
            "Shared routing failure writer returned an unexpected path."
        )

    return RoutingReviewRecord(
        failure_id=failure_id,
        failure_metadata_path=written_path,
        failure_metadata_relative_path=_workspace_relative(written_path, root),
        failure_category=failure_category,
        failure_message=failure_message,
        retained_source_relative_path=retained_relative_path,
        review_copy_relative_path=review_relative_path,
    )


def preserve_route_failure_for_review(
    workspace_root: str | Path,
    *,
    route_failure: RouteFailure,
    source_filename: str,
    retained_source: RetainedSourceScan | None = None,
    review_copy_path: str | Path | None = None,
    source_page_number: int | None = None,
    created_at: datetime | None = None,
) -> RoutingReviewRecord:
    """Preserve a route planner failure without re-running route planning."""
    if not isinstance(route_failure, RouteFailure):
        raise RoutingReviewError("route_failure must be a RouteFailure.")

    module_details: dict[str, object] = {"failure_origin": "route_planning"}
    module_details.update(route_failure.module_details)

    return preserve_routing_failure_for_review(
        workspace_root,
        failure_category=route_failure.failure_category,
        failure_message=route_failure.failure_message,
        source_filename=source_filename,
        module=route_failure.module,
        source_scan_id=(
            None if retained_source is None else retained_source.source_scan_id
        ),
        source_sha256=(
            None if retained_source is None else retained_source.source_sha256
        ),
        retained_source_path=(
            None
            if retained_source is None
            else retained_source.retained_source_path
        ),
        review_copy_path=review_copy_path,
        source_page_number=source_page_number,
        detected_payload=route_failure.raw_payload,
        payload_page_number=route_failure.page_number,
        class_id=route_failure.class_id,
        assignment_id=route_failure.assignment_id,
        student_id=route_failure.student_id,
        module_details=module_details,
        created_at=created_at,
    )


def preserve_decode_failure_for_review(
    workspace_root: str | Path,
    *,
    decode_result: QrImageDecodeResult,
    source_filename: str,
    created_at: datetime | None = None,
) -> RoutingReviewRecord:
    """Preserve source/QR decode failure context without invented identity."""
    if not isinstance(decode_result, QrImageDecodeResult):
        raise RoutingReviewError("decode_result must be a QrImageDecodeResult.")

    category = decode_result.failure_category or "processing_error"
    message = decode_result.failure_message or "QR decoding failed."
    return preserve_routing_failure_for_review(
        workspace_root,
        failure_category=category,
        failure_message=message,
        source_filename=source_filename,
        module=None,
        detected_payload=None,
        payload_page_number=None,
        class_id=None,
        assignment_id=None,
        student_id=None,
        module_details={
            "failure_origin": "qr_decode",
            "decode_attempt": decode_result.successful_attempt,
        },
        created_at=created_at,
    )


def preserve_payload_validation_failure_for_review(
    workspace_root: str | Path,
    *,
    failure: ResponsePayloadValidationFailure,
    source_filename: str,
    created_at: datetime | None = None,
) -> RoutingReviewRecord:
    """Preserve decoded-payload validation failure context for review."""
    if not isinstance(failure, ResponsePayloadValidationFailure):
        raise RoutingReviewError(
            "failure must be a ResponsePayloadValidationFailure."
        )

    module_details: dict[str, object] = {
        "failure_origin": "payload_validation",
    }
    module_details.update(failure.module_details)

    return preserve_routing_failure_for_review(
        workspace_root,
        failure_category=failure.failure_category,
        failure_message=failure.failure_message,
        source_filename=source_filename,
        module=failure.module,
        detected_payload=failure.raw_payload,
        payload_page_number=failure.page_number,
        class_id=failure.class_id,
        assignment_id=failure.assignment_id,
        student_id=failure.student_id,
        module_details=module_details,
        created_at=created_at,
    )


def preserve_evidence_filing_error_for_review(
    workspace_root: str | Path,
    *,
    error: EvidenceFilingError,
    route_plan: RoutePlan,
    source_filename: str,
    retained_source: RetainedSourceScan | None = None,
    review_copy_path: str | Path | None = None,
    module_details: dict[str, object] | None = None,
    created_at: datetime | None = None,
) -> RoutingReviewRecord:
    """Preserve a successful-plan evidence filing failure for review."""
    if not isinstance(error, EvidenceFilingError):
        raise RoutingReviewError("error must be an EvidenceFilingError.")
    if not isinstance(route_plan, RoutePlan):
        raise RoutingReviewError("route_plan must be a RoutePlan.")

    details: dict[str, object] = {"failure_origin": "evidence_filing"}
    if module_details is not None:
        details.update(module_details)

    return preserve_routing_failure_for_review(
        workspace_root,
        failure_category="evidence_write_failed",
        failure_message=str(error),
        source_filename=source_filename,
        module="quillan",
        source_scan_id=(
            None if retained_source is None else retained_source.source_scan_id
        ),
        source_sha256=(
            None if retained_source is None else retained_source.source_sha256
        ),
        retained_source_path=(
            None
            if retained_source is None
            else retained_source.retained_source_path
        ),
        review_copy_path=review_copy_path,
        payload_page_number=route_plan.page_number,
        class_id=route_plan.class_id,
        assignment_id=route_plan.assignment_id,
        student_id=route_plan.student_id,
        module_details=details,
        created_at=created_at,
    )


def _resolved_workspace_root(workspace_root: str | Path) -> Path:
    try:
        root = Path(workspace_root).resolve(strict=True)
        if not root.is_dir():
            raise RoutingReviewError(
                f"Workspace root is not an existing directory: {root}"
            )
        return root
    except RoutingReviewError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise RoutingReviewError(f"Invalid workspace root: {error}") from error


def _normalized_timestamp(created_at: datetime | None) -> datetime:
    value = datetime.now(timezone.utc) if created_at is None else created_at
    if not isinstance(value, datetime):
        raise RoutingReviewError("created_at must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise RoutingReviewError("created_at must be timezone-aware.")
    try:
        return value.astimezone(timezone.utc)
    except (OSError, OverflowError, ValueError) as error:
        raise RoutingReviewError(
            f"created_at cannot be represented in UTC: {error}"
        ) from error


def _optional_workspace_relative_path(
    value: str | Path | None,
    root: Path,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    try:
        supplied_path = Path(value)
        path = (
            supplied_path
            if supplied_path.is_absolute()
            else root / supplied_path
        ).resolve(strict=False)
    except (OSError, TypeError, ValueError) as error:
        raise RoutingReviewError(f"Invalid {field_name}: {error}") from error
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise RoutingReviewError(
            f"{field_name} must be inside the workspace root."
        ) from error


def _build_failure_id(
    *,
    timestamp: datetime,
    source_filename: str,
    failure_category: str,
    detected_payload: str | None,
    retained_source_path: str | None,
) -> str:
    timestamp_component = (
        f"{timestamp.year:04d}{timestamp.month:02d}{timestamp.day:02d}"
        f"T{timestamp.hour:02d}{timestamp.minute:02d}{timestamp.second:02d}"
        f"{timestamp.microsecond:06d}Z"
    )
    digest_context = "\0".join(
        (
            timestamp.isoformat(timespec="microseconds"),
            _digest_value(source_filename),
            failure_category,
            _digest_value(detected_payload),
            retained_source_path or "",
        )
    )
    digest = hashlib.sha256(digest_context.encode("utf-8")).hexdigest()
    return (
        f"failure_{timestamp_component}_"
        f"{digest[:_FAILURE_ID_DIGEST_LENGTH]}"
    )


def _digest_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return repr(value)


def _workspace_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise RoutingReviewError(
            "Failure metadata path is outside the workspace root."
        ) from error

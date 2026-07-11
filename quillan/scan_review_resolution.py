"""Discover and resolve Quillan scan-routing review records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from pds_core.scan_failure_metadata import (
    RoutingFailureMetadata,
    RoutingFailureMetadataError,
    routing_failure_metadata_from_dict,
)
from pds_core.scan_resolution_metadata import (
    ScanResolutionMetadata,
    ScanResolutionMetadataError,
    ScanResolutionMetadataWriteError,
    scan_resolution_metadata_dir,
    scan_resolution_metadata_from_dict,
    scan_resolution_metadata_path,
    write_scan_resolution_metadata,
)
from pds_core.scan_routes import routing_review_dir


QUILLAN_RESOLUTION_ACTIONS: Final[tuple[str, ...]] = (
    "rescan_needed",
    "cannot_route",
    "mixed_assignment",
    "evidence_filed",
    "dismissed_duplicate",
    "other",
    "defer",
)

DEFAULT_RESOLUTION_MESSAGES: Final[dict[str, str]] = {
    "rescan_needed": "Teacher marked this scan/page for rescan.",
    "cannot_route": "Teacher marked this scan/page as unable to route safely.",
    "mixed_assignment": "Teacher marked this scan/source as mixed assignment.",
    "evidence_filed": (
        "Teacher marked this evidence as filed outside the automatic route-scan flow."
    ),
    "dismissed_duplicate": "Teacher dismissed this review item as a duplicate.",
    "defer": "Teacher deferred this review item for later.",
}


class ScanReviewResolutionError(RuntimeError):
    """Raised when scan review records cannot be read or resolved safely."""


@dataclass(frozen=True, slots=True)
class QuillanReviewItem:
    """One valid Quillan routing failure plus its latest resolution state."""

    failure_id: str
    failure_metadata_path: Path
    failure_metadata_relative_path: str
    failure_category: str
    failure_message: str
    stage: str
    created_at: str
    module: str | None
    source_filename: str
    retained_source_path: str | None
    review_copy_path: str | None
    source_scan_id: str | None
    source_sha256: str | None
    source_page_number: int | None
    detected_payload: str | None
    payload_page_number: int | None
    class_id: str | None
    assignment_id: str | None
    student_id: str | None
    latest_resolution_status: str | None
    latest_resolution_action: str | None
    latest_resolution_path: str | None

    @property
    def display_status(self) -> str:
        """Return the teacher-facing active state for this item."""
        return self.latest_resolution_status or "unresolved"


@dataclass(frozen=True, slots=True)
class QuillanResolutionResult:
    """Provenance for one newly written shared resolution record."""

    resolution_id: str
    resolution_metadata_path: Path
    resolution_metadata_relative_path: str
    failure_id: str
    resolution_status: str
    resolution_action: str


@dataclass(frozen=True, slots=True)
class QuillanReviewDiscovery:
    """Valid review items and conservative diagnostics from discovery."""

    items: tuple[QuillanReviewItem, ...]
    warnings: tuple[str, ...]


def discover_scan_review_items(
    workspace_root: str | Path,
    *,
    include_resolved: bool = False,
    class_id: str | None = None,
    assignment_id: str | None = None,
    failure_category: str | None = None,
    limit: int | None = None,
) -> QuillanReviewDiscovery:
    """Discover valid Quillan review items without mutating workspace data."""
    root = _workspace_root(workspace_root)
    if limit is not None and (isinstance(limit, bool) or limit < 1):
        raise ScanReviewResolutionError("limit must be a positive integer.")

    failures, failure_warnings = _load_failures(root)
    resolutions, resolution_warnings = _load_resolutions(root)
    latest_by_failure: dict[str, tuple[ScanResolutionMetadata, Path]] = {}
    for resolution_metadata, path in resolutions:
        current = latest_by_failure.get(resolution_metadata.failure_id)
        if current is None or _resolution_order(
            resolution_metadata, path
        ) > _resolution_order(
            current[0], current[1]
        ):
            latest_by_failure[resolution_metadata.failure_id] = (
                resolution_metadata,
                path,
            )

    items: list[QuillanReviewItem] = []
    for failure_metadata, path in failures:
        latest = latest_by_failure.get(failure_metadata.failure_id)
        if latest is not None and latest[0].resolution_status == "resolved":
            if not include_resolved:
                continue
        if class_id is not None and failure_metadata.class_id != class_id:
            continue
        if (
            assignment_id is not None
            and failure_metadata.assignment_id != assignment_id
        ):
            continue
        if (
            failure_category is not None
            and failure_metadata.failure_category != failure_category
        ):
            continue
        items.append(_review_item(root, failure_metadata, path, latest))

    items.sort(key=lambda item: (item.created_at, item.failure_id))
    if limit is not None:
        items = items[:limit]
    return QuillanReviewDiscovery(
        items=tuple(items),
        warnings=tuple((*failure_warnings, *resolution_warnings)),
    )


def list_scan_review_items(
    workspace_root: str | Path,
    *,
    include_resolved: bool = False,
) -> tuple[QuillanReviewItem, ...]:
    """Return only valid review items for simple programmatic callers."""
    return discover_scan_review_items(
        workspace_root, include_resolved=include_resolved
    ).items


def resolve_scan_review_item(
    workspace_root: str | Path,
    failure_id: str,
    *,
    action: str,
    message: str | None = None,
    evidence_path: str | Path | None = None,
    resolved_at: datetime | None = None,
) -> QuillanResolutionResult:
    """Write an immutable Core resolution record for one Quillan failure."""
    root = _workspace_root(workspace_root)
    if action not in QUILLAN_RESOLUTION_ACTIONS:
        raise ScanReviewResolutionError(
            "Unsupported Quillan scan review action: " + str(action)
        )
    normalized_message = _resolution_message(action, message)
    evidence_relative = _evidence_path(evidence_path)
    if evidence_relative is not None and action != "evidence_filed":
        raise ScanReviewResolutionError(
            "evidence_path may only be used with the evidence_filed action."
        )

    discovery = discover_scan_review_items(root, include_resolved=True)
    matches = [item for item in discovery.items if item.failure_id == failure_id]
    if not matches:
        raise ScanReviewResolutionError(
            f"No valid Quillan scan review item has failure ID {failure_id}."
        )
    if len(matches) != 1:
        raise ScanReviewResolutionError(
            f"Multiple Quillan scan review records use failure ID {failure_id}."
        )
    item = matches[0]
    timestamp = _utc_timestamp(resolved_at)
    status = "deferred" if action == "defer" else "resolved"
    metadata_action = "other" if action == "defer" else action
    resolution_id = _resolution_id(
        failure_id=failure_id,
        status=status,
        action=metadata_action,
        message=normalized_message,
        timestamp=timestamp,
    )
    try:
        metadata = ScanResolutionMetadata(
            schema_version="1",
            resolution_id=resolution_id,
            failure_id=item.failure_id,
            failure_metadata_path=item.failure_metadata_relative_path,
            resolution_status=status,
            resolution_action=metadata_action,
            resolved_at=timestamp.isoformat(timespec="microseconds"),
            resolution_message=normalized_message,
            module_details={
                "resolved_by": "teacher",
                "resolution_origin": "quillan_scan_review",
                "original_failure_category": item.failure_category,
                "original_failure_stage": item.stage,
                "teacher_selected_action": action,
            },
            module=item.module or "quillan",
            source_scan_id=item.source_scan_id,
            source_sha256=item.source_sha256,
            source_filename=item.source_filename,
            retained_source_path=item.retained_source_path,
            review_copy_path=item.review_copy_path,
            resolution_evidence_path=evidence_relative,
            source_page_number=item.source_page_number,
            class_id=item.class_id,
            assignment_id=item.assignment_id,
            student_id=item.student_id,
        )
        expected = scan_resolution_metadata_path(root, resolution_id).resolve(
            strict=False
        )
        written = write_scan_resolution_metadata(root, metadata).resolve(strict=False)
    except (
        ScanResolutionMetadataError,
        ScanResolutionMetadataWriteError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        raise ScanReviewResolutionError(
            f"Could not write scan review resolution: {error}"
        ) from error
    if written != expected:
        raise ScanReviewResolutionError(
            "Shared scan resolution writer returned an unexpected path."
        )
    return QuillanResolutionResult(
        resolution_id=resolution_id,
        resolution_metadata_path=written,
        resolution_metadata_relative_path=_relative(written, root),
        failure_id=failure_id,
        resolution_status=status,
        resolution_action=metadata_action,
    )


def _load_failures(
    root: Path,
) -> tuple[list[tuple[RoutingFailureMetadata, Path]], list[str]]:
    records: list[tuple[RoutingFailureMetadata, Path]] = []
    warnings: list[str] = []
    review_dir = routing_review_dir(root)
    if not review_dir.exists():
        return records, warnings
    for path in sorted(review_dir.glob("*.json"), key=lambda value: value.name):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise RoutingFailureMetadataError("record must be a JSON object.")
            metadata = routing_failure_metadata_from_dict(data)
        except (OSError, UnicodeError, json.JSONDecodeError, RoutingFailureMetadataError) as error:
            warnings.append(f"Skipped unreadable review record {path.name}: {error}")
            continue
        if metadata.stage != "quillan_route_review":
            continue
        records.append((metadata, path.resolve(strict=False)))
    return records, warnings


def _load_resolutions(
    root: Path,
) -> tuple[list[tuple[ScanResolutionMetadata, Path]], list[str]]:
    records: list[tuple[ScanResolutionMetadata, Path]] = []
    warnings: list[str] = []
    directory = scan_resolution_metadata_dir(root)
    if not directory.exists():
        return records, warnings
    for path in sorted(directory.glob("*.json"), key=lambda value: value.name):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ScanResolutionMetadataError("record must be a JSON object.")
            metadata = scan_resolution_metadata_from_dict(data)
        except (OSError, UnicodeError, json.JSONDecodeError, ScanResolutionMetadataError) as error:
            warnings.append(f"Skipped unreadable resolution record {path.name}: {error}")
            continue
        records.append((metadata, path.resolve(strict=False)))
    return records, warnings


def _review_item(
    root: Path,
    failure: RoutingFailureMetadata,
    path: Path,
    latest: tuple[ScanResolutionMetadata, Path] | None,
) -> QuillanReviewItem:
    resolution, resolution_path = latest if latest is not None else (None, None)
    return QuillanReviewItem(
        failure_id=failure.failure_id,
        failure_metadata_path=path,
        failure_metadata_relative_path=_relative(path, root),
        failure_category=failure.failure_category,
        failure_message=failure.failure_message,
        stage=failure.stage,
        created_at=failure.created_at,
        module=failure.module,
        source_filename=failure.source_filename,
        retained_source_path=failure.retained_source_path,
        review_copy_path=failure.review_copy_path,
        source_scan_id=failure.source_scan_id,
        source_sha256=failure.source_sha256,
        source_page_number=failure.source_page_number,
        detected_payload=failure.detected_payload,
        payload_page_number=failure.payload_page_number,
        class_id=failure.class_id,
        assignment_id=failure.assignment_id,
        student_id=failure.student_id,
        latest_resolution_status=(None if resolution is None else resolution.resolution_status),
        latest_resolution_action=(None if resolution is None else resolution.resolution_action),
        latest_resolution_path=(
            None if resolution_path is None else _relative(resolution_path, root)
        ),
    )


def _resolution_order(
    metadata: ScanResolutionMetadata, path: Path
) -> tuple[datetime, str]:
    parsed = datetime.fromisoformat(metadata.resolved_at).astimezone(timezone.utc)
    return parsed, path.name


def _workspace_root(value: str | Path) -> Path:
    try:
        root = Path(value).resolve(strict=True)
    except (OSError, TypeError, ValueError) as error:
        raise ScanReviewResolutionError(f"Invalid workspace root: {error}") from error
    if not root.is_dir():
        raise ScanReviewResolutionError(
            f"Workspace root is not an existing directory: {root}"
        )
    return root


def _evidence_path(value: str | Path | None) -> str | None:
    if value is None:
        return None
    try:
        path = Path(value)
    except (TypeError, ValueError) as error:
        raise ScanReviewResolutionError(f"Invalid evidence_path: {error}") from error
    if path.is_absolute():
        raise ScanReviewResolutionError(
            "evidence_path must be relative to the workspace root."
        )
    return path.as_posix()


def _resolution_message(action: str, value: str | None) -> str:
    if value is not None:
        message = value.strip()
        if not message:
            raise ScanReviewResolutionError("message must not be empty.")
        return message
    if action == "other":
        raise ScanReviewResolutionError(
            "A non-empty message is required for the other action."
        )
    return DEFAULT_RESOLUTION_MESSAGES[action]


def _utc_timestamp(value: datetime | None) -> datetime:
    timestamp = datetime.now(timezone.utc) if value is None else value
    if not isinstance(timestamp, datetime):
        raise ScanReviewResolutionError("resolved_at must be a datetime.")
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ScanReviewResolutionError("resolved_at must be timezone-aware.")
    return timestamp.astimezone(timezone.utc)


def _resolution_id(
    *, failure_id: str, status: str, action: str, message: str, timestamp: datetime
) -> str:
    compact = timestamp.strftime("%Y%m%dT%H%M%S") + f"{timestamp.microsecond:06d}Z"
    digest_input = "\0".join(
        (failure_id, status, action, timestamp.isoformat(timespec="microseconds"), message)
    )
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:12]
    return f"resolution_{compact}_{digest}"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except ValueError as error:
        raise ScanReviewResolutionError(
            "Scan review metadata path is outside the workspace root."
        ) from error

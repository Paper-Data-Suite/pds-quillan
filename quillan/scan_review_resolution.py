"""Discover and resolve Quillan-owned Core schema-v2 scan-review records."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.route_registrations import (
    RouteRegistrationPersistenceError,
    load_route_registration,
)
from pds_core.routes import module_routes_dir
from pds_core.routing_models import (
    ModuleRecordRef,
    ModuleWorkRef,
    RouteLocator,
    RoutingModelError,
)
from pds_core.scan_failure_metadata import (
    ROUTING_FAILURE_SCHEMA_VERSION,
    RoutingFailureMetadata,
    RoutingFailureMetadataError,
    load_routing_failure_metadata,
    routing_failure_metadata_path,
)
from pds_core.scan_resolution_metadata import (
    SCAN_RESOLUTION_SCHEMA_VERSION,
    ScanResolutionMetadata,
    ScanResolutionMetadataError,
    ScanResolutionMetadataWriteError,
    create_scan_resolution_metadata,
    scan_resolution_metadata_dir,
    load_scan_resolution_metadata,
    scan_resolution_metadata_path,
    write_scan_resolution_metadata,
)

from pds_core.scan_routes import routing_review_dir

from quillan._path_safety import is_link_like as _shared_is_link_like
from quillan.pds_contract import (
    QUILLAN_MODULE_ID,
    RESPONSE_PAGE_CONTRACT_VERSION,
    RESPONSE_PAGE_RECORD_KIND,
)
from quillan.printable_response_persistence import (
    PrintableResponsePersistenceError,
    load_printable_response_page,
    load_printable_response_page_context,
)
from quillan.printable_response_records import response_page_target
from quillan.printable_response_routes import validate_route_id
from quillan.printable_response_routes import PrintableResponseRouteError
from quillan.work_paths import QuillanWorkPathError, quillan_work_paths
from quillan.work_paths import (
    _preflight_arbitrary_file_destination,
    _preflight_path_chain,
)


QUILLAN_RESOLUTION_ACTIONS: Final[tuple[str, ...]] = (
    "route_selected",
    "route_corrected",
    "evidence_filed",
    "rescan_needed",
    "cannot_route",
    "dismissed_duplicate",
    "deferred",
    "other",
    "defer",
    "mixed_assignment",
)

DEFAULT_RESOLUTION_MESSAGES: Final[dict[str, str]] = {
    "route_selected": "Teacher selected the intended route.",
    "route_corrected": "Teacher corrected the intended route.",
    "rescan_needed": "Teacher marked this scan/page for rescan.",
    "cannot_route": "Teacher marked this scan/page as unable to route safely.",
    "mixed_assignment": "Teacher marked this scan/source as mixed assignment.",
    "evidence_filed": (
        "Teacher marked this evidence as filed outside the automatic route-scan flow."
    ),
    "dismissed_duplicate": "Teacher dismissed this review item as a duplicate.",
    "deferred": "Teacher deferred this review item for later.",
    "defer": "Teacher deferred this review item for later.",
}


class ScanReviewResolutionError(RuntimeError):
    """Raised when scan review records cannot be read or resolved safely."""


@dataclass(frozen=True, slots=True)
class QuillanReviewItem:
    """One validated Quillan-owned Core routing failure and latest resolution."""

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
    """Provenance for one newly written exact Core-v2 resolution record."""

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


@dataclass(frozen=True, slots=True)
class QuillanRouteOption:
    """One current registered Quillan response-page route for teacher selection."""

    locator: RouteLocator
    target: ModuleRecordRef
    student_id: str
    logical_page: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class QuillanRouteDiscovery:
    """Valid route choices and conservative malformed-registration warnings."""

    routes: tuple[QuillanRouteOption, ...]
    warnings: tuple[str, ...]


def discover_scan_review_route_options(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> QuillanRouteDiscovery:
    """List valid current response-page routes within one exact Quillan work."""
    root = _workspace_root(workspace_root)
    work_ref = ModuleWorkRef(QUILLAN_MODULE_ID, class_id, assignment_id)
    directory = module_routes_dir(root, work_ref)
    if not os.path.lexists(directory):
        return QuillanRouteDiscovery((), ())
    try:
        _preflight_path_chain(root=root, target=directory, expect_file=False)
        children = tuple(sorted(directory.iterdir(), key=lambda path: path.name))
    except (OSError, RuntimeError, ValueError) as error:
        return QuillanRouteDiscovery((), (f"Could not inspect route directory: {error}",))
    routes: list[QuillanRouteOption] = []
    warnings: list[str] = []
    for path in children:
        if path.suffix != ".json":
            continue
        try:
            _preflight_arbitrary_file_destination(path)
            route_id = validate_route_id(path.stem)
            locator = RouteLocator("PDS2", work_ref, route_id)
            registration = load_route_registration(root, locator)
            if registration.status != "active":
                continue
            context = load_printable_response_page_context(
                root, work_ref, registration.target.record_id
            )
            if registration.target != response_page_target(context.page):
                raise ScanReviewResolutionError(
                    "registration target contradicts its immutable response page"
                )
            routes.append(
                QuillanRouteOption(
                    locator,
                    registration.target,
                    context.student_id,
                    context.logical_page,
                    context.total_pages,
                )
            )
        except (
            IdentifierValidationError,
            OSError,
            PrintableResponsePersistenceError,
            PrintableResponseRouteError,
            QuillanWorkPathError,
            RouteRegistrationPersistenceError,
            RoutingModelError,
        ) as error:
            warnings.append(f"Skipped invalid route {path.name}: {error}")
    routes.sort(
        key=lambda item: (item.student_id, item.logical_page, item.locator.route_id)
    )
    return QuillanRouteDiscovery(tuple(routes), tuple(warnings))


def discover_scan_review_items(
    workspace_root: str | Path,
    *,
    include_resolved: bool = False,
    class_id: str | None = None,
    assignment_id: str | None = None,
    failure_category: str | None = None,
    limit: int | None = None,
) -> QuillanReviewDiscovery:
    """Discover exact Core-v2 Quillan review items without mutation."""
    root = _workspace_root(workspace_root)
    if class_id is not None:
        validate_identifier(class_id, "class_id")
    if assignment_id is not None:
        validate_identifier(assignment_id, "assignment_id")
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
    ):
        raise ScanReviewResolutionError("limit must be a positive integer.")

    failures, failure_warnings = _load_failures(root)
    resolutions, resolution_warnings = _load_resolutions(root, failures)
    latest_by_failure: dict[str, tuple[ScanResolutionMetadata, Path]] = {}
    for resolution, path in resolutions:
        current = latest_by_failure.get(resolution.failure_id)
        if current is None or _resolution_order(resolution, path) > _resolution_order(
            current[0], current[1]
        ):
            latest_by_failure[resolution.failure_id] = (resolution, path)

    items: list[QuillanReviewItem] = []
    enrichment_warnings: list[str] = []
    for failure, path in failures:
        latest = latest_by_failure.get(failure.failure_id)
        if latest is not None and latest[0].resolution_status == "resolved":
            if not include_resolved:
                continue
        work_ref = _failure_work_ref(failure)
        if class_id is not None and (
            work_ref is None or work_ref.class_id != class_id
        ):
            continue
        if assignment_id is not None and (
            work_ref is None or work_ref.work_id != assignment_id
        ):
            continue
        if failure_category is not None and failure.failure_category != failure_category:
            continue
        student_id, warning = _student_identity(root, failure, work_ref)
        if warning is not None:
            enrichment_warnings.append(warning)
        items.append(_review_item(root, failure, path, latest, work_ref, student_id))

    items.sort(key=lambda item: (item.created_at, item.failure_id))
    if limit is not None:
        items = items[:limit]
    return QuillanReviewDiscovery(
        items=tuple(items),
        warnings=tuple(
            (*failure_warnings, *resolution_warnings, *enrichment_warnings)
        ),
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
    route_locator: RouteLocator | None = None,
    target: ModuleRecordRef | None = None,
    resolved_at: datetime | None = None,
) -> QuillanResolutionResult:
    """Write an immutable exact Core-v2 resolution for one Quillan failure."""
    root = _workspace_root(workspace_root)
    if action not in QUILLAN_RESOLUTION_ACTIONS:
        raise ScanReviewResolutionError(
            "Unsupported Quillan scan review action: " + str(action)
        )
    normalized_message = _resolution_message(action, message)
    status, metadata_action = _mapped_action(action)

    failures, warnings = _load_failures(root)
    matches = [(metadata, path) for metadata, path in failures if metadata.failure_id == failure_id]
    if len(matches) != 1:
        warning_suffix = f" Discovery warnings: {'; '.join(warnings)}" if warnings else ""
        if not matches:
            raise ScanReviewResolutionError(
                f"No valid Quillan scan review item has failure ID {failure_id}."
                + warning_suffix
            )
        raise ScanReviewResolutionError(
            f"Multiple Quillan scan review records use failure ID {failure_id}."
        )
    failure, _ = matches[0]
    work_ref = _failure_work_ref(failure)
    evidence_relative = _evidence_path(root, work_ref, evidence_path)
    if evidence_relative is not None and metadata_action != "evidence_filed":
        raise ScanReviewResolutionError(
            "evidence_path may only be used with the evidence_filed action."
        )

    timestamp = _utc_timestamp(resolved_at)
    resolution_id = _resolution_id(
        failure_id=failure_id,
        status=status,
        action=metadata_action,
        message=normalized_message,
        timestamp=timestamp,
    )
    module_details = {
        "resolved_by": "teacher",
        "resolution_origin": "quillan_scan_review",
        "original_failure_category": failure.failure_category,
        "original_failure_stage": failure.stage,
        "teacher_selected_action": action,
    }
    resolution_locator, resolution_target = _resolution_route(
        root,
        failure,
        action,
        route_locator,
        target,
    )
    try:
        metadata = create_scan_resolution_metadata(
            failure,
            resolution_id=resolution_id,
            resolution_status=status,
            resolution_action=metadata_action,
            resolved_at=timestamp.isoformat(timespec="microseconds"),
            resolution_message=normalized_message,
            route_locator=resolution_locator,
            target=resolution_target,
            resolution_evidence_path=evidence_relative,
            module_details=module_details,
        )
        expected = scan_resolution_metadata_path(root, resolution_id)
        written = write_scan_resolution_metadata(root, metadata)
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
            "Core scan-resolution writer returned an unexpected path."
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
    for path in _json_children(routing_review_dir(root), "review", warnings):
        failure_id = path.stem
        try:
            if routing_failure_metadata_path(root, failure_id) != path:
                raise RoutingFailureMetadataError(
                    "filename is not the exact canonical failure path"
                )
            metadata = load_routing_failure_metadata(root, failure_id)
            if metadata.schema_version != ROUTING_FAILURE_SCHEMA_VERSION:
                raise RoutingFailureMetadataError("failure schema_version is not 2")
            if metadata.failure_id != failure_id:
                raise RoutingFailureMetadataError("filename and failure_id disagree")
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            RoutingFailureMetadataError,
            RuntimeError,
            ValueError,
        ) as error:
            warnings.append(f"Skipped unreadable review record {path.name}: {error}")
            continue
        if not _is_quillan_failure(metadata):
            continue
        records.append((metadata, path))
    return _reject_duplicate_failures(records, warnings), warnings


def _load_resolutions(
    root: Path,
    failures: list[tuple[RoutingFailureMetadata, Path]],
) -> tuple[list[tuple[ScanResolutionMetadata, Path]], list[str]]:
    records: list[tuple[ScanResolutionMetadata, Path]] = []
    warnings: list[str] = []
    directory = scan_resolution_metadata_dir(root)
    failure_by_id = {item.failure_id: item for item, _ in failures}
    for path in _json_children(directory, "resolution", warnings):
        resolution_id = path.stem
        try:
            if scan_resolution_metadata_path(root, resolution_id) != path:
                raise ScanResolutionMetadataError(
                    "filename is not the exact canonical resolution path"
                )
            metadata = load_scan_resolution_metadata(root, resolution_id)
            if metadata.schema_version != SCAN_RESOLUTION_SCHEMA_VERSION:
                raise ScanResolutionMetadataError("resolution schema_version is not 2")
            if metadata.resolution_id != resolution_id:
                raise ScanResolutionMetadataError("filename and resolution_id disagree")
            failure = failure_by_id.get(metadata.failure_id)
            if failure is None:
                raise ScanResolutionMetadataError(
                    "resolution references an absent valid failure"
                )
            _validate_resolution_linkage(root, metadata, failure)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            ScanResolutionMetadataError,
            RuntimeError,
            ValueError,
        ) as error:
            warnings.append(f"Skipped unreadable resolution record {path.name}: {error}")
            continue
        records.append((metadata, path))
    return _reject_duplicate_resolutions(records, warnings), warnings


def _json_children(
    directory: Path, description: str, warnings: list[str]
) -> tuple[Path, ...]:
    if not os.path.lexists(directory):
        return ()
    try:
        _preflight_path_chain(
            root=Path(directory.anchor), target=directory, expect_file=False
        )
    except Exception as error:
        warnings.append(f"Skipped unsafe {description} directory: {error}")
        return ()
    if _is_link_like(directory) or not directory.is_dir():
        warnings.append(
            f"Skipped unsafe {description} directory: {directory}"
        )
        return ()
    try:
        children = tuple(sorted(directory.iterdir(), key=lambda value: value.name))
    except OSError as error:
        warnings.append(f"Could not inspect {description} directory: {error}")
        return ()
    result: list[Path] = []
    for child in children:
        if child.suffix != ".json":
            continue
        try:
            _preflight_arbitrary_file_destination(child)
        except Exception:
            warnings.append(f"Skipped unsafe {description} record {child.name}.")
            continue
        if _is_link_like(child) or not child.is_file():
            warnings.append(f"Skipped unsafe {description} record {child.name}.")
            continue
        result.append(child)
    return tuple(result)


def _reject_duplicate_failures(
    records: list[tuple[RoutingFailureMetadata, Path]], warnings: list[str]
) -> list[tuple[RoutingFailureMetadata, Path]]:
    counts: dict[str, int] = {}
    for metadata, _ in records:
        counts[metadata.failure_id] = counts.get(metadata.failure_id, 0) + 1
    duplicate_ids = {failure_id for failure_id, count in counts.items() if count > 1}
    for failure_id in sorted(duplicate_ids):
        warnings.append(f"Skipped duplicate failure ID {failure_id}.")
    return [item for item in records if item[0].failure_id not in duplicate_ids]


def _reject_duplicate_resolutions(
    records: list[tuple[ScanResolutionMetadata, Path]], warnings: list[str]
) -> list[tuple[ScanResolutionMetadata, Path]]:
    counts: dict[str, int] = {}
    for metadata, _ in records:
        counts[metadata.resolution_id] = counts.get(metadata.resolution_id, 0) + 1
    duplicate_ids = {
        resolution_id for resolution_id, count in counts.items() if count > 1
    }
    for resolution_id in sorted(duplicate_ids):
        warnings.append(f"Skipped duplicate resolution ID {resolution_id}.")
    return [item for item in records if item[0].resolution_id not in duplicate_ids]


def _validate_resolution_linkage(
    root: Path,
    resolution: ScanResolutionMetadata,
    failure: RoutingFailureMetadata,
) -> None:
    expected_failure_path = routing_failure_metadata_path(
        root, failure.failure_id
    ).relative_to(root).as_posix()
    if resolution.failure_metadata_path != expected_failure_path:
        raise ScanResolutionMetadataError(
            "resolution failure_metadata_path is not canonical"
        )
    provenance_fields = (
        "source_filename",
        "source_scan_id",
        "source_sha256",
        "retained_source_path",
        "review_copy_path",
        "source_page_number",
    )
    if any(
        getattr(resolution, field) != getattr(failure, field)
        for field in provenance_fields
    ):
        raise ScanResolutionMetadataError("resolution source provenance is forged")
    resolved_at = datetime.fromisoformat(resolution.resolved_at)
    created_at = datetime.fromisoformat(failure.created_at)
    if resolved_at < created_at:
        raise ScanResolutionMetadataError("resolution predates its failure")


def _is_quillan_failure(failure: RoutingFailureMetadata) -> bool:
    locator = failure.route_locator
    target = failure.target
    if locator is not None or target is not None:
        modules = {
            value.module_id for value in (locator, target) if value is not None
        }
        return modules == {QUILLAN_MODULE_ID}
    details = failure.module_details
    if details.get("failure_owner") != QUILLAN_MODULE_ID:
        return False
    marker = (
        details.get("failure_origin"),
        failure.scope,
        failure.stage,
        failure.failure_category,
    )
    exact_markers = {
        ("source_page_loading", "scan", "source_page_loading", "source_unreadable"),
        ("source_page_loading", "page", "source_page_loading", "source_unreadable"),
        ("qr_detection", "page", "qr_detection", "payload_missing"),
        ("qr_detection", "page", "qr_detection", "payload_unreadable"),
        ("payload_parsing", "page", "payload_parsing", "payload_invalid"),
        (
            "payload_parsing",
            "page",
            "payload_parsing",
            "payload_schema_unsupported",
        ),
        ("payload_parsing", "page", "payload_parsing", "payload_too_large"),
        ("payload_parsing", "page", "payload_parsing", "payload_unreadable"),
    }
    return marker in exact_markers


def _failure_work_ref(failure: RoutingFailureMetadata) -> ModuleWorkRef | None:
    locator = failure.route_locator
    if locator is None or locator.module_id != QUILLAN_MODULE_ID:
        return None
    return locator.work


def _student_identity(
    root: Path,
    failure: RoutingFailureMetadata,
    work_ref: ModuleWorkRef | None,
) -> tuple[str | None, str | None]:
    target = failure.target
    if (
        work_ref is None
        or target is None
        or target.module_id != QUILLAN_MODULE_ID
        or target.record_kind != RESPONSE_PAGE_RECORD_KIND
    ):
        return None, None
    try:
        page = load_printable_response_page(root, work_ref, target.record_id)
    except PrintableResponsePersistenceError as error:
        return None, (
            f"Could not enrich failure {failure.failure_id} from its exact "
            f"response-page target: {error}"
        )
    return page.student_id, None


def _review_item(
    root: Path,
    failure: RoutingFailureMetadata,
    path: Path,
    latest: tuple[ScanResolutionMetadata, Path] | None,
    work_ref: ModuleWorkRef | None,
    student_id: str | None,
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
        module=QUILLAN_MODULE_ID,
        source_filename=failure.source_filename,
        retained_source_path=failure.retained_source_path,
        review_copy_path=failure.review_copy_path,
        source_scan_id=failure.source_scan_id,
        source_sha256=failure.source_sha256,
        source_page_number=failure.source_page_number,
        detected_payload=failure.detected_payload,
        class_id=None if work_ref is None else work_ref.class_id,
        assignment_id=None if work_ref is None else work_ref.work_id,
        student_id=student_id,
        latest_resolution_status=(
            None if resolution is None else resolution.resolution_status
        ),
        latest_resolution_action=(
            None if resolution is None else resolution.resolution_action
        ),
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
        root = Path(os.path.abspath(Path(value)))
    except (OSError, TypeError, ValueError) as error:
        raise ScanReviewResolutionError(f"Invalid workspace root: {error}") from error
    if not os.path.lexists(root) or _is_link_like(root) or not root.is_dir():
        raise ScanReviewResolutionError(
            f"Workspace root is not an ordinary existing directory: {root}"
        )
    return root


def _evidence_path(
    root: Path,
    work_ref: ModuleWorkRef | None,
    value: str | Path | None,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, (str, Path)):
        raise ScanReviewResolutionError("evidence_path must be a string or Path.")
    text = str(value)
    posix = PurePosixPath(text)
    windows = PureWindowsPath(text)
    if (
        not text
        or "\\" in text
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or any(component in {"", ".", ".."} for component in posix.parts)
        or posix.as_posix() != text
    ):
        raise ScanReviewResolutionError(
            "evidence_path must be canonical workspace-relative POSIX text."
        )
    absolute = root.joinpath(*posix.parts)
    try:
        absolute.relative_to(root)
    except ValueError as error:
        raise ScanReviewResolutionError("evidence_path escapes the workspace.") from error
    if not os.path.lexists(absolute) or _is_link_like(absolute) or not absolute.is_file():
        raise ScanReviewResolutionError(
            "evidence_path must name an ordinary existing non-link file."
        )
    try:
        _preflight_arbitrary_file_destination(absolute)
    except Exception as error:
        raise ScanReviewResolutionError(
            f"evidence_path has an unsafe ancestor: {error}"
        ) from error
    if work_ref is not None:
        work_root = quillan_work_paths(
            root, work_ref.class_id, work_ref.work_id
        ).work_root
        try:
            absolute.relative_to(work_root)
        except ValueError as error:
            raise ScanReviewResolutionError(
                "evidence_path is outside the selected Quillan work root."
            ) from error
    return text


def _resolution_route(
    root: Path,
    failure: RoutingFailureMetadata,
    action: str,
    locator: RouteLocator | None,
    target: ModuleRecordRef | None,
) -> tuple[RouteLocator | None, ModuleRecordRef | None]:
    route_action = action in {"route_selected", "route_corrected"}
    if not route_action:
        if locator is not None or target is not None:
            raise ScanReviewResolutionError(
                "route_locator and target are only valid for route actions."
            )
        return None, None
    if type(locator) is not RouteLocator:
        raise ScanReviewResolutionError(
            f"{action} requires an exact Core RouteLocator."
        )
    if type(target) is not ModuleRecordRef:
        raise ScanReviewResolutionError(
            f"{action} requires an exact Core ModuleRecordRef target."
        )
    if locator.schema != "PDS2" or locator.module_id != QUILLAN_MODULE_ID:
        raise ScanReviewResolutionError(
            "route_locator must be an exact PDS2 Quillan locator."
        )
    if (
        target.module_id != QUILLAN_MODULE_ID
        or target.record_kind != RESPONSE_PAGE_RECORD_KIND
        or target.contract_version != RESPONSE_PAGE_CONTRACT_VERSION
    ):
        raise ScanReviewResolutionError(
            "target is not a supported Quillan response-page reference."
        )
    failure_work = _failure_work_ref(failure)
    if failure_work is not None and locator.work != failure_work:
        raise ScanReviewResolutionError(
            "Corrected route crosses the failure's exact class or assignment."
        )
    if action == "route_corrected" and (
        failure.route_locator == locator and failure.target == target
    ):
        raise ScanReviewResolutionError(
            "route_corrected must change the failure's route or target."
        )
    try:
        registration = load_route_registration(root, locator)
    except Exception as error:
        raise ScanReviewResolutionError(
            f"route_locator does not identify a valid canonical route: {error}"
        ) from error
    if registration.locator != locator or registration.target != target:
        raise ScanReviewResolutionError(
            "route_locator and target do not identify the same registered route."
        )
    try:
        page = load_printable_response_page(root, locator.work, target.record_id)
    except PrintableResponsePersistenceError as error:
        raise ScanReviewResolutionError(
            f"route target is not a valid canonical response page: {error}"
        ) from error
    if (
        page.class_id != locator.class_id
        or page.assignment_id != locator.work_id
        or page.page_id != target.record_id
    ):
        raise ScanReviewResolutionError(
            "route target contradicts the selected work identity."
        )
    return locator, target


def _mapped_action(action: str) -> tuple[str, str]:
    if action in {"defer", "deferred"}:
        return "deferred", "deferred"
    if action == "mixed_assignment":
        return "resolved", "other"
    return "resolved", action


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
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise ScanReviewResolutionError(
            "Scan review metadata path is outside the workspace root."
        ) from error


def _is_link_like(path: Path) -> bool:
    return _shared_is_link_like(path)


__all__ = [
    "DEFAULT_RESOLUTION_MESSAGES",
    "QUILLAN_RESOLUTION_ACTIONS",
    "QuillanResolutionResult",
    "QuillanRouteDiscovery",
    "QuillanRouteOption",
    "QuillanReviewDiscovery",
    "QuillanReviewItem",
    "ScanReviewResolutionError",
    "discover_scan_review_items",
    "discover_scan_review_route_options",
    "list_scan_review_items",
    "resolve_scan_review_item",
]

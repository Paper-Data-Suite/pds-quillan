"""Read-only preflight for one teacher-authorized retained scan recovery.

Issue #419 Slice 1 deliberately does not dispatch, persist, assemble, or
write a Core scan-resolution record. Execution will be added in later slices.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal

from pds_core.route_registrations import load_route_registration
from pds_core.routing_models import ModuleRecordRef, RouteLocator
from pds_core.scan_retention import RetainedSourceScan
from pds_core.scan_resolution_metadata import load_scan_resolution_metadata

from quillan.module_errors import QuillanRetainedSourceError, QuillanSourcePageError
from quillan.pds2_scan_intake import validate_scan_workspace
from quillan.pds_module import validate_quillan_registration
from quillan.printable_response_persistence import (
    PrintableResponsePersistenceError,
    load_printable_response_page_context,
)
from quillan.printable_response_records import response_page_target
from quillan.printable_response_routes import (
    PrintableResponseRouteError,
    printable_response_module_details,
)
from quillan.retained_scan_pages import retained_source_page_count
from quillan.retained_source import validate_quillan_retained_source
from quillan.retained_source_provenance import validate_core_retention_event_consistency
from quillan.scan_review_resolution import (
    QuillanReviewItem,
    discover_scan_review_items,
)

_SOURCE_READ_SIZE = 1024 * 1024
_ROUTE_ACTIONS = frozenset({"route_selected", "route_corrected"})


class ScanRecoveryPreflightError(ValueError):
    """The selected physical page cannot safely proceed to recovery."""


@dataclass(frozen=True, slots=True)
class PreparedScanRecovery:
    """Non-authoritative, read-only preview; execution MUST revalidate."""

    failure_id: str
    failure_category: str
    source_filename: str
    retained_source: RetainedSourceScan
    source_page_number: int
    source_page_count: int
    route_locator: RouteLocator
    target: ModuleRecordRef
    class_id: str
    assignment_id: str
    student_id: str
    logical_page: int
    total_pages: int
    page_id: str
    route_origin: Literal["explicit", "recorded"]
    historical_resolution_id: str | None


def prepare_scan_review_recovery(
    workspace_root: str | Path,
    failure_id: str,
    *,
    route_locator: RouteLocator | None = None,
    target: ModuleRecordRef | None = None,
    use_recorded_route: bool = False,
) -> PreparedScanRecovery:
    """Validate one retained physical page and route without writing state.

    An explicit locator and target must be supplied together; alternatively,
    explicitly reuse the latest verified historical route selection. No QR text
    is inferred or re-decoded. The result is a preview, not recovery proof.
    """
    if type(failure_id) is not str or not failure_id:
        raise ScanRecoveryPreflightError("failure_id must be nonempty exact text.")
    if type(use_recorded_route) is not bool:
        raise ScanRecoveryPreflightError("use_recorded_route must be a Boolean.")
    if use_recorded_route:
        if route_locator is not None or target is not None:
            raise ScanRecoveryPreflightError(
                "Recorded-route reuse cannot be combined with an explicit route."
            )
    elif type(route_locator) is not RouteLocator or type(target) is not ModuleRecordRef:
        raise ScanRecoveryPreflightError(
            "An exact RouteLocator and ModuleRecordRef must be supplied together."
        )

    try:
        root = validate_scan_workspace(Path(os.path.abspath(workspace_root)))
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        raise ScanRecoveryPreflightError(f"Invalid workspace: {error}") from error

    # Discovery enforces Core's strict failure/resolution readers, ownership,
    # canonical paths, and historical linkage checks. include_resolved matters:
    # old route decisions were marked resolved without materializing evidence.
    discovery = discover_scan_review_items(root, include_resolved=True)
    matches = [item for item in discovery.items if item.failure_id == failure_id]
    if len(matches) != 1:
        raise ScanRecoveryPreflightError(
            "No unique valid Quillan scan-review failure has the requested ID."
        )
    item = matches[0]
    if item.source_page_number is None:
        raise ScanRecoveryPreflightError(
            "The failure has no exact physical source page to recover."
        )
    if item.retained_source_path is None or item.source_scan_id is None:
        raise ScanRecoveryPreflightError(
            "The failure does not identify an original retained source."
        )
    if item.source_sha256 is None:
        raise ScanRecoveryPreflightError(
            "The failure has no retained-source SHA-256 authority."
        )

    historical_resolution_id: str | None = None
    route_origin: Literal["explicit", "recorded"] = "explicit"
    if use_recorded_route:
        if item.latest_resolution_action not in _ROUTE_ACTIONS:
            raise ScanRecoveryPreflightError(
                "The latest validated decision is not a reusable route selection."
            )
        if item.latest_resolution_path is None:
            raise ScanRecoveryPreflightError("The recorded route decision is missing.")
        resolution_id = PurePosixPath(item.latest_resolution_path).stem
        try:
            resolution = load_scan_resolution_metadata(root, resolution_id)
        except (OSError, ValueError, RuntimeError) as error:
            raise ScanRecoveryPreflightError(
                f"Could not reload the recorded route decision: {error}"
            ) from error
        if (
            resolution.failure_id != failure_id
            or resolution.resolution_status != "resolved"
            or resolution.resolution_action != item.latest_resolution_action
        ):
            raise ScanRecoveryPreflightError(
                "The recorded route decision no longer agrees with discovery."
            )
        route_locator = resolution.route_locator
        target = resolution.target
        historical_resolution_id = resolution_id
        route_origin = "recorded"

    # The original failure may have no validated locator (e.g. unreadable QR),
    # but an already-authoritative work identity must never be crossed.
    if type(route_locator) is not RouteLocator or type(target) is not ModuleRecordRef:
        raise ScanRecoveryPreflightError("The selected route has no exact target.")
    if item.class_id is not None and (
        route_locator.class_id != item.class_id
        or route_locator.work_id != item.assignment_id
    ):
        raise ScanRecoveryPreflightError(
            "Selected route crosses the failure's authoritative class or assignment."
        )
    if route_locator.module_id != "quillan":
        raise ScanRecoveryPreflightError(
            "Only Quillan response-page routes are eligible."
        )

    retained = _reconstruct_retained_source(root, item)
    page_number = item.source_page_number
    try:
        validate_quillan_retained_source(
            retained, workspace_root=root, source_page_number=page_number
        )
        actual_hash = _sha256_file(retained.retained_source_path)
        if actual_hash != retained.source_sha256:
            raise ScanRecoveryPreflightError("Retained source SHA-256 does not match.")
        page_count = retained_source_page_count(retained, workspace_root=root)
    except ScanRecoveryPreflightError:
        raise
    except (
        QuillanRetainedSourceError,
        QuillanSourcePageError,
        OSError,
        ValueError,
        RuntimeError,
    ) as error:
        raise ScanRecoveryPreflightError(
            f"Cannot verify retained source and page: {error}"
        ) from error
    if page_number > page_count:
        raise ScanRecoveryPreflightError(
            f"Physical page {page_number} exceeds retained source page "
            f"count {page_count}."
        )

    try:
        registration = load_route_registration(root, route_locator)
        validate_quillan_registration(registration)
        if registration.locator != route_locator or registration.target != target:
            raise ScanRecoveryPreflightError(
                "Selected locator and target do not match the exact registration."
            )
        context = load_printable_response_page_context(
            root, route_locator.work, target.record_id
        )
        if context.issuance.lifecycle.status != "issued":
            raise ScanRecoveryPreflightError(
                "The target response-page issuance is not currently issued."
            )
        if (
            response_page_target(context.page) != target
            or registration.module_details
            != printable_response_module_details(context.page)
        ):
            raise ScanRecoveryPreflightError(
                "Selected route contradicts immutable response-page authority."
            )
    except ScanRecoveryPreflightError:
        raise
    except (
        PrintableResponsePersistenceError,
        PrintableResponseRouteError,
        OSError,
        ValueError,
        RuntimeError,
    ) as error:
        raise ScanRecoveryPreflightError(
            f"Cannot verify selected registered route: {error}"
        ) from error

    page = context.page
    return PreparedScanRecovery(
        failure_id=failure_id,
        failure_category=item.failure_category,
        source_filename=item.source_filename,
        retained_source=retained,
        source_page_number=page_number,
        source_page_count=page_count,
        route_locator=route_locator,
        target=target,
        class_id=page.class_id,
        assignment_id=page.assignment_id,
        student_id=page.student_id,
        logical_page=page.logical_page,
        total_pages=page.total_pages,
        page_id=page.page_id,
        route_origin=route_origin,
        historical_resolution_id=historical_resolution_id,
    )


def _reconstruct_retained_source(
    root: Path, item: QuillanReviewItem
) -> RetainedSourceScan:
    """Recover Core retention identity from its immutable canonical filename."""
    try:
        relative_text = item.retained_source_path
        if not isinstance(relative_text, str) or "\\" in relative_text:
            raise ValueError("retained source path is not canonical POSIX text")
        relative = PurePosixPath(relative_text)
        if (
            relative.is_absolute()
            or len(relative.parts) != 4
            or relative.parts[:2] != ("scans", "source")
            or relative.as_posix() != relative_text
        ):
            raise ValueError("retained source path is not a canonical Core path")
        source_scan_id = item.source_scan_id
        source_sha256 = item.source_sha256
        if not isinstance(source_scan_id, str) or not isinstance(source_sha256, str):
            raise ValueError("missing retained-source ID or SHA-256")
        intake_date = date.fromisoformat(relative.parts[2])
        stamp = relative.name.split("__", 1)[0]
        intake_timestamp = datetime.strptime(stamp, "%Y%m%dT%H%M%S%fZ").replace(
            tzinfo=timezone.utc
        )
        path = root.joinpath(*relative.parts)
        retained = RetainedSourceScan(
            source_scan_id=source_scan_id,
            source_filename=item.source_filename,
            source_sha256=source_sha256,
            retained_source_path=path,
            retained_source_relative_path=relative_text,
            intake_timestamp=intake_timestamp,
            intake_date=intake_date,
        )
        validate_core_retention_event_consistency(
            source_scan_id=retained.source_scan_id,
            source_filename=retained.source_filename,
            source_sha256=retained.source_sha256,
            retained_source_path=retained.retained_source_path,
            retained_source_relative_path=retained.retained_source_relative_path,
            intake_timestamp=retained.intake_timestamp,
            intake_date=retained.intake_date,
            workspace_root=root,
        )
        return retained
    except (TypeError, AttributeError, OSError, ValueError) as error:
        raise ScanRecoveryPreflightError(
            f"Original retained-source identity is invalid: {error}"
        ) from error


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(_SOURCE_READ_SIZE), b""):
            digest.update(part)
    return digest.hexdigest()


__all__ = [
    "PreparedScanRecovery",
    "ScanRecoveryPreflightError",
    "prepare_scan_review_recovery",
]

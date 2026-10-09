"""Issue #419: explicit Core dispatch of one preflighted retained scan page.

This boundary does not perform QR detection, write evidence/observations, assemble
submissions, or append scan-resolution metadata. The prepared preview is not an
authorization token: source, failure, route and issuance are rechecked before
Core dispatch and again afterward to detect changed durable inputs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pds_core.module_dispatch import (
    ModuleDispatchError,
    RouteDispatchRequest,
    RouteDispatchRequestError,
    RouteDispatchSuccess,
    dispatch_route,
)
from pds_core.module_profiles import ModuleRegistry, UnsupportedModuleError
from pds_core.route_registrations import RouteRegistrationPersistenceError
from pds_core.routing_models import RoutingModelError

from quillan.module_errors import (
    QuillanDispatchResultError,
    QuillanScanRegistryError,
)
from quillan.pds2_scan_intake import (
    build_quillan_scan_registry,
    validate_quillan_scan_registry,
)
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.printable_response_persistence import (
    PrintableResponsePersistenceError,
    load_printable_response_page_context,
)
from quillan.response_page_dispatch import (
    QuillanResponsePageDispatchResult,
    validate_quillan_response_page_dispatch_result,
)
from quillan.scan_recovery_preflight import (
    PreparedScanRecovery,
    ScanRecoveryPreflightError,
    prepare_scan_review_recovery,
)


class ScanRecoveryDispatchError(RuntimeError):
    """The selected retained page could not be dispatched authoritatively."""


@dataclass(frozen=True, slots=True)
class DispatchedScanRecovery:
    """A verified nonpersistent Core success, for later persistence slices.

    Not proof of a saved observation, assembled submission or resolved failure.
    """

    prepared: PreparedScanRecovery
    request: RouteDispatchRequest
    success: RouteDispatchSuccess
    page_result: QuillanResponsePageDispatchResult


def dispatch_prepared_scan_recovery(
    workspace_root: str | Path,
    prepared: PreparedScanRecovery,
    *,
    registry: ModuleRegistry | None = None,
) -> DispatchedScanRecovery:
    """Revalidate a Slice 1 preview; dispatch precisely its physical page.

    The optional registry supports controlled tests and application-provided
    installed registries. Without one, use existing installed module discovery.
    No scan-intake QR detection or Quillan workspace writer is invoked.
    """
    if type(prepared) is not PreparedScanRecovery:
        raise ScanRecoveryDispatchError(
            "Dispatch requires an exact prepared scan recovery preview."
        )

    try:
        root = Path(os.path.abspath(workspace_root))
        if prepared.route_origin == "recorded":
            current = prepare_scan_review_recovery(
                root, prepared.failure_id, use_recorded_route=True
            )
        elif prepared.route_origin == "explicit":
            current = prepare_scan_review_recovery(
                root,
                prepared.failure_id,
                route_locator=prepared.route_locator,
                target=prepared.target,
            )
        else:
            raise ScanRecoveryDispatchError("Unknown recovery route origin.")
    except ScanRecoveryPreflightError as error:
        raise ScanRecoveryDispatchError(
            f"Recovery preflight no longer passes: {error}"
        ) from error
    except (OSError, TypeError, ValueError) as error:
        raise ScanRecoveryDispatchError(
            f"Recovery preflight could not be repeated: {error}"
        ) from error

    if current != prepared:
        raise ScanRecoveryDispatchError(
            "Recovery preview is stale; prepare and confirm the route again."
        )

    try:
        chosen_registry = (
            build_quillan_scan_registry() if registry is None else registry
        )
        chosen_registry = validate_quillan_scan_registry(chosen_registry)
    except QuillanScanRegistryError as error:
        raise ScanRecoveryDispatchError(
            f"Quillan Core dispatch registry is unavailable: {error}"
        ) from error

    request = RouteDispatchRequest(
        locator=current.route_locator,
        retained_source=current.retained_source,
        source_page_number=current.source_page_number,
    )
    try:
        success = dispatch_route(root, chosen_registry, request)
    except (
        RouteDispatchRequestError,
        ModuleDispatchError,
        RouteRegistrationPersistenceError,
        RoutingModelError,
        UnsupportedModuleError,
    ) as error:
        raise ScanRecoveryDispatchError(
            f"Core rejected retained-page recovery dispatch: {error}"
        ) from error

    # Core handles module registration and invokes the installed Quillan route
    # handler. Independently verify the resulting exact Quillan authority,
    # including fields not present in the teacher-facing Slice 1 preview.
    if type(success) is not RouteDispatchSuccess:
        raise ScanRecoveryDispatchError(
            "Core did not return an exact dispatch success."
        )
    if success.request != request or success.resolution.locator != request.locator:
        raise ScanRecoveryDispatchError(
            "Core dispatch request or resolved route contradicts recovery."
        )
    if (
        success.profile is not chosen_registry.require(QUILLAN_MODULE_ID)
        or success.profile.module_id != QUILLAN_MODULE_ID
        or success.resolution.registration.target != current.target
    ):
        raise ScanRecoveryDispatchError(
            "Core dispatch profile or registered target contradicts recovery."
        )
    if type(success.module_result) is not QuillanResponsePageDispatchResult:
        raise ScanRecoveryDispatchError(
            "Core dispatch did not return an exact Quillan response-page result."
        )
    try:
        result = validate_quillan_response_page_dispatch_result(success.module_result)
        context = load_printable_response_page_context(
            root, current.route_locator.work, current.target.record_id
        )
    except (
        QuillanDispatchResultError,
        PrintableResponsePersistenceError,
    ) as error:
        raise ScanRecoveryDispatchError(
            f"Recovery dispatch result could not be verified: {error}"
        ) from error

    page = context.page
    retained = current.retained_source
    expected = (
        current.route_locator.route_id,
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
        retained.source_scan_id,
        retained.source_filename,
        current.source_page_number,
        retained.retained_source_path,
        retained.retained_source_relative_path,
        retained.source_sha256,
        retained.intake_timestamp,
        retained.intake_date,
    )
    actual = (
        result.route_id,
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
        result.source_scan_id,
        result.source_filename,
        result.source_page_number,
        result.retained_source_path,
        result.retained_source_relative_path,
        result.source_sha256,
        result.intake_timestamp,
        result.intake_date,
    )
    if actual != expected or context.issuance.lifecycle.status != "issued":
        raise ScanRecoveryDispatchError(
            "Recovered result or current issuance contradicts immutable page authority."
        )

    # Prevent a success from being passed to a later writer if the original
    # page or recorded decision changed during the synchronous dispatch call.
    try:
        after = (
            prepare_scan_review_recovery(
                root, current.failure_id, use_recorded_route=True
            )
            if current.route_origin == "recorded"
            else prepare_scan_review_recovery(
                root,
                current.failure_id,
                route_locator=current.route_locator,
                target=current.target,
            )
        )
    except ScanRecoveryPreflightError as error:
        raise ScanRecoveryDispatchError(
            f"Recovery authority changed during Core dispatch: {error}"
        ) from error
    if after != current:
        raise ScanRecoveryDispatchError(
            "Recovery inputs changed during Core dispatch; prepare again."
        )

    return DispatchedScanRecovery(
        prepared=current,
        request=request,
        success=success,
        page_result=result,
    )


__all__ = [
    "DispatchedScanRecovery",
    "ScanRecoveryDispatchError",
    "dispatch_prepared_scan_recovery",
]

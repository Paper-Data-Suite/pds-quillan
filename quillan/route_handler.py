"""Defensive one-page handler for resolved Quillan response-page routes."""

from __future__ import annotations

import os
from pathlib import Path

from pds_core.routes import class_dir, class_module_dir, module_work_dir
from pds_core.routing_models import (
    RouteResolution,
    validate_route_locator,
    validate_route_registration,
)
from pds_core.scan_retention import RetainedSourceScan

from quillan._path_safety import is_link_like as _shared_is_link_like
from quillan.module_errors import (
    QuillanDispatchResultError,
    QuillanIssuanceAuthorizationError,
    QuillanRegistrationValidationError,
    QuillanRetainedSourceError,
    QuillanRouteContextError,
    QuillanTargetIntegrityError,
)
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.pds_module import validate_quillan_registration
from quillan.printable_response_persistence import (
    PrintableResponsePersistenceError,
    load_printable_response_page_context,
)
from quillan.printable_response_records import (
    PrintableResponsePageContext,
    PrintableResponseRecordSet,
    PrintableResponseRecordValidationError,
    response_page_target,
    validate_printable_response_record_set,
)
from quillan.printable_response_routes import (
    printable_response_human_fallback,
    printable_response_module_details,
)
from quillan.response_page_dispatch import (
    QuillanResponsePageDispatchResult,
    validate_quillan_response_page_dispatch_result,
)
from quillan.retained_source import (
    ValidatedQuillanRetainedPageProvenance,
    validate_quillan_retained_source,
)


def handle_quillan_response_page_route(
    resolution: RouteResolution,
    retained_source: RetainedSourceScan,
    source_page_number: int,
    /,
) -> QuillanResponsePageDispatchResult:
    """Validate and resolve one retained page without writing workspace state."""
    _validate_handler_arguments(resolution, retained_source, source_page_number)
    workspace_root = _validate_resolution_context(resolution)
    registration = resolution.registration
    try:
        context = load_printable_response_page_context(
            workspace_root,
            resolution.locator.work,
            registration.target.record_id,
        )
    except (
        PrintableResponsePersistenceError,
        PrintableResponseRecordValidationError,
    ) as error:
        raise QuillanTargetIntegrityError(
            "Could not load the registered immutable response-page context."
        ) from error
    _cross_validate_context(resolution, context)
    if context.issuance.lifecycle.status != "issued":
        raise QuillanIssuanceAuthorizationError(
            "The registered response-page issuance is not issued."
        )
    provenance = validate_quillan_retained_source(
        retained_source,
        workspace_root=workspace_root,
        source_page_number=source_page_number,
    )
    page = context.page
    retained = provenance.retained_source
    result = QuillanResponsePageDispatchResult(
        route_id=resolution.locator.route_id,
        page_id=page.page_id,
        issuance_id=page.issuance_id,
        generation_id=page.generation_id,
        artifact_id=page.artifact_id,
        class_id=page.class_id,
        assignment_id=page.assignment_id,
        student_id=page.student_id,
        logical_page=page.logical_page,
        total_pages=page.total_pages,
        page_role=page.page_role,
        source_scan_id=retained.source_scan_id,
        source_filename=retained.source_filename,
        source_page_number=provenance.source_page_number,
        retained_source_path=retained.retained_source_path,
        retained_source_relative_path=retained.retained_source_relative_path,
        source_sha256=retained.source_sha256,
        intake_timestamp=retained.intake_timestamp,
        intake_date=retained.intake_date,
    )
    try:
        validated = validate_quillan_response_page_dispatch_result(result)
    except QuillanDispatchResultError:
        raise
    _cross_validate_result(validated, resolution, context, provenance)
    return validated


def _validate_handler_arguments(
    resolution: object,
    retained_source: object,
    source_page_number: object,
) -> None:
    if not isinstance(resolution, RouteResolution):
        raise QuillanRouteContextError("resolution must be a RouteResolution.")
    if not isinstance(retained_source, RetainedSourceScan):
        raise QuillanRetainedSourceError(
            "retained_source must be a RetainedSourceScan."
        )
    if (
        isinstance(source_page_number, bool)
        or not isinstance(source_page_number, int)
        or source_page_number < 1
    ):
        raise QuillanRetainedSourceError(
            "source_page_number must be a positive non-Boolean integer."
        )


def _validate_resolution_context(resolution: object) -> Path:
    try:
        if not isinstance(resolution, RouteResolution):
            raise ValueError("resolution must be a RouteResolution.")
        validate_route_locator(resolution.locator)
        validate_route_registration(resolution.registration)
        if resolution.locator != resolution.registration.locator:
            raise ValueError("resolution locator does not match its registration.")
        if resolution.locator.module_id != QUILLAN_MODULE_ID:
            raise ValueError("resolution is not owned by Quillan.")
        validate_quillan_registration(resolution.registration)
        workspace_root = resolution.class_root.parent.parent
        expected_class = class_dir(workspace_root, resolution.locator.class_id)
        expected_module = class_module_dir(
            workspace_root, resolution.locator.class_id, QUILLAN_MODULE_ID
        )
        expected_work = module_work_dir(workspace_root, resolution.locator.work)
        if (
            resolution.class_root != expected_class
            or resolution.module_root != expected_module
            or resolution.work_root != expected_work
        ):
            raise ValueError("resolution roots are not canonical Core roots.")
        _validate_root_chain(workspace_root, resolution.work_root)
        return workspace_root
    except QuillanRouteContextError:
        raise
    except QuillanRegistrationValidationError as error:
        raise QuillanRouteContextError(
            "The resolved Quillan registration is invalid."
        ) from error
    except (ValueError, TypeError, AttributeError, OSError) as error:
        raise QuillanRouteContextError(
            f"Invalid Quillan route resolution context: {error}"
        ) from error


def _validate_root_chain(workspace_root: Path, work_root: Path) -> None:
    absolute_workspace = Path(os.path.abspath(workspace_root))
    absolute_work = Path(os.path.abspath(work_root))
    if workspace_root != absolute_workspace or work_root != absolute_work:
        raise ValueError("resolution roots must be absolute and canonical.")
    try:
        relative = absolute_work.relative_to(absolute_workspace)
    except ValueError as error:
        raise ValueError("work_root escapes the derived workspace.") from error
    current = absolute_workspace
    candidates = [current]
    for component in relative.parts:
        current /= component
        candidates.append(current)
    for candidate in candidates:
        if not os.path.lexists(candidate):
            raise ValueError("resolution root chain contains a missing path.")
        if _is_link_like(candidate):
            raise ValueError("resolution root chain contains a symlink or junction.")
        if not candidate.is_dir():
            raise ValueError("resolution root chain contains a non-directory.")


def _is_link_like(path: Path) -> bool:
    return _shared_is_link_like(path)


def _cross_validate_context(
    resolution: RouteResolution,
    context: PrintableResponsePageContext,
) -> None:
    try:
        page = context.page
        issuance = context.issuance
        members = context.member_pages
        registration = resolution.registration
        locator = resolution.locator
        validate_printable_response_record_set(
            PrintableResponseRecordSet(issuance, members)
        )
        if registration.target != response_page_target(page):
            raise ValueError("registration target contradicts the page.")
        if (
            locator.class_id != page.class_id
            or locator.work_id != page.assignment_id
            or issuance.class_id != page.class_id
            or issuance.assignment_id != page.assignment_id
        ):
            raise ValueError("route work identity contradicts immutable records.")
        if registration.created_at != page.created_at:
            raise ValueError("route creation identity contradicts the page.")
        if registration.module_details != printable_response_module_details(page):
            raise ValueError("route module_details contradict the page.")
        if registration.human_fallback != printable_response_human_fallback(page):
            raise ValueError("route human fallback contradicts the page.")
        page_identity = (
            page.issuance_id,
            page.generation_id,
            page.artifact_id,
            page.class_id,
            page.assignment_id,
            page.student_id,
        )
        issuance_identity = (
            issuance.issuance_id,
            issuance.generation_id,
            issuance.artifact_id,
            issuance.class_id,
            issuance.assignment_id,
            issuance.student_id,
        )
        if page_identity != issuance_identity:
            raise ValueError("page provenance contradicts its issuance.")
    except QuillanTargetIntegrityError:
        raise
    except (ValueError, TypeError, AttributeError, IndexError) as error:
        raise QuillanTargetIntegrityError(
            f"Resolved route contradicts immutable response-page context: {error}"
        ) from error


def _cross_validate_result(
    result: QuillanResponsePageDispatchResult,
    resolution: RouteResolution,
    context: PrintableResponsePageContext,
    provenance: ValidatedQuillanRetainedPageProvenance,
) -> None:
    page = context.page
    retained = provenance.retained_source
    expected_identity = (
        resolution.locator.route_id,
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
    actual_identity = (
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
    )
    expected_provenance = (
        retained.source_scan_id,
        retained.source_filename,
        provenance.source_page_number,
        retained.retained_source_path,
        retained.retained_source_relative_path,
        retained.source_sha256,
        retained.intake_timestamp,
        retained.intake_date,
    )
    actual_provenance = (
        result.source_scan_id,
        result.source_filename,
        result.source_page_number,
        result.retained_source_path,
        result.retained_source_relative_path,
        result.source_sha256,
        result.intake_timestamp,
        result.intake_date,
    )
    if actual_identity != expected_identity or actual_provenance != expected_provenance:
        raise QuillanDispatchResultError(
            "Validated dispatch result contradicts its authoritative sources."
        )


__all__ = ["handle_quillan_response_page_route"]

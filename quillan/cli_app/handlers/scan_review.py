"""Direct CLI handlers for Quillan scan review resolution."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pds_core.route_registrations import load_route_registration
from pds_core.routing_models import ModuleRecordRef, ModuleWorkRef, RouteLocator
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.post_dispatch_review_resolution import (
    PostDispatchReviewResolutionError,
    discover_post_dispatch_review_items,
    resolve_post_dispatch_review_occurrence,
)
from quillan.scan_review_resolution import (
    ScanReviewResolutionError,
    discover_scan_review_items,
    resolve_scan_review_item,
)
from quillan.work_paths import quillan_work_ref


def handle_list_scan_review(args: argparse.Namespace) -> int:
    """List unresolved/deferred Quillan routing review records."""
    try:
        root = resolve_workspace_root()
        discovery = discover_scan_review_items(
            root,
            include_resolved=args.include_resolved,
            class_id=args.class_id,
            assignment_id=args.assignment_id,
            failure_category=args.failure_category,
            limit=args.limit,
        )
    except (WorkspaceRootError, ScanReviewResolutionError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Core routing review items")
    print()
    if not discovery.items:
        print("No Core routing review items match this request.")
    for index, item in enumerate(discovery.items, start=1):
        print(f"{index}. {item.failure_id}")
        print(f"   Status: {item.display_status}")
        print(f"   Category: {item.failure_category}")
        print(f"   Source: {item.source_filename}")
        print(f"   Page: {_display(item.source_page_number)}")
        print(f"   Class: {_display(item.class_id)}")
        print(f"   Assignment: {_display(item.assignment_id)}")
        print()
    if discovery.warnings:
        print(
            f"Warning: skipped {len(discovery.warnings)} malformed or unreadable "
            "scan review metadata file(s)."
        )
    return 0


def handle_resolve_scan_review(args: argparse.Namespace) -> int:
    """Resolve or defer one Quillan routing review record."""
    try:
        root = resolve_workspace_root()
        locator, target = _selected_route(root, args)
        result = resolve_scan_review_item(
            root,
            args.failure_id,
            action=args.action,
            message=args.message,
            evidence_path=args.evidence_path,
            route_locator=locator,
            target=target,
        )
    except (WorkspaceRootError, ScanReviewResolutionError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Scan review item {result.resolution_status}.")
    print(f"Failure ID: {result.failure_id}")
    print(f"Action: {result.resolution_action}")
    print(f"Resolution record: {result.resolution_metadata_relative_path}")
    return 0


def handle_list_post_dispatch_review(args: argparse.Namespace) -> int:
    """List one work root's active Quillan post-dispatch occurrences."""
    try:
        root = resolve_workspace_root()
        discovery = discover_post_dispatch_review_items(
            root,
            quillan_work_ref(args.class_id, args.assignment_id),
            include_resolved=args.include_resolved,
            category=args.category,
            limit=args.limit,
        )
    except (WorkspaceRootError, PostDispatchReviewResolutionError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Quillan post-dispatch review occurrences")
    print(f"Class: {args.class_id}")
    print(f"Assignment: {args.assignment_id}")
    print()
    if not discovery.items:
        print("No post-dispatch occurrences match this request.")
    for index, item in enumerate(discovery.items, start=1):
        occurrence = item.occurrence.occurrence
        print(f"{index}. {occurrence.failure_id}")
        print(f"   Status: {item.display_status}")
        print(f"   Category: {occurrence.category}")
        print(f"   Stage: {occurrence.stage}")
        print(f"   Student: {_display(occurrence.student_id)}")
        print(f"   Occurrence: {item.occurrence.relative_path}")
        print()
    if discovery.warnings:
        print(
            f"Warning: skipped {len(discovery.warnings)} malformed or unreadable "
            "post-dispatch record(s)."
        )
    return 0


def handle_resolve_post_dispatch_review(args: argparse.Namespace) -> int:
    """Append one Quillan-owned post-dispatch resolution."""
    try:
        root = resolve_workspace_root()
        result = resolve_post_dispatch_review_occurrence(
            root,
            quillan_work_ref(args.class_id, args.assignment_id),
            args.failure_id,
            action=args.action,
            message=args.message,
        )
    except (WorkspaceRootError, PostDispatchReviewResolutionError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Post-dispatch review item {result.resolution.status}.")
    print(f"Failure ID: {result.resolution.failure_id}")
    print(f"Action: {result.resolution.action}")
    print(f"Resolution record: {result.relative_path}")
    return 0


def _selected_route(
    root: Path, args: argparse.Namespace
) -> tuple[RouteLocator | None, ModuleRecordRef | None]:
    route_action = args.action in {"route_selected", "route_corrected"}
    route_values = (args.route_id, args.route_class_id, args.route_assignment_id)
    if not route_action:
        if any(value is not None for value in route_values):
            raise ScanReviewResolutionError(
                "Route identity arguments are valid only for route_selected or "
                "route_corrected."
            )
        return None, None
    if args.route_id is None:
        raise ScanReviewResolutionError("A route action requires --route-id.")
    discovery = discover_scan_review_items(root, include_resolved=True)
    matches = [item for item in discovery.items if item.failure_id == args.failure_id]
    if len(matches) != 1:
        raise ScanReviewResolutionError(
            "Route selection requires one valid Core routing-review failure."
        )
    item = matches[0]
    class_id = args.route_class_id or item.class_id
    assignment_id = args.route_assignment_id or item.assignment_id
    if class_id is None or assignment_id is None:
        raise ScanReviewResolutionError(
            "An unscoped failure requires --route-class-id and "
            "--route-assignment-id."
        )
    locator = RouteLocator(
        "PDS2",
        ModuleWorkRef("quillan", class_id, assignment_id),
        args.route_id,
    )
    try:
        registration = load_route_registration(root, locator)
    except Exception as error:
        raise ScanReviewResolutionError(
            f"Could not load the exact registered route: {error}"
        ) from error
    return locator, registration.target


def _display(value: object | None) -> str:
    return "—" if value is None else str(value)

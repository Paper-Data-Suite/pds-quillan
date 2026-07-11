"""Direct CLI handlers for Quillan scan review resolution."""

from __future__ import annotations

import argparse

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.scan_review_resolution import (
    ScanReviewResolutionError,
    discover_scan_review_items,
    resolve_scan_review_item,
)


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
        print(f"Error: {error}")
        return 1

    print("Quillan scan review items")
    print()
    if not discovery.items:
        print("No Quillan scan review items match this request.")
    for index, item in enumerate(discovery.items, start=1):
        print(f"{index}. {item.failure_id}")
        print(f"   Status: {item.display_status}")
        print(f"   Category: {item.failure_category}")
        print(f"   Source: {item.source_filename}")
        print(f"   Page: {_display(item.source_page_number)}")
        print(f"   Class: {_display(item.class_id)}")
        print(f"   Assignment: {_display(item.assignment_id)}")
        print(f"   Student: {_display(item.student_id)}")
        print(f"   Review record: {item.failure_metadata_relative_path}")
        if item.retained_source_path is not None:
            print(f"   Retained source: {item.retained_source_path}")
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
        result = resolve_scan_review_item(
            root,
            args.failure_id,
            action=args.action,
            message=args.message,
            evidence_path=args.evidence_path,
        )
    except (WorkspaceRootError, ScanReviewResolutionError) as error:
        print(f"Error: {error}")
        return 1

    print(f"Scan review item {result.resolution_status}.")
    print(f"Failure ID: {result.failure_id}")
    print(f"Action: {result.resolution_action}")
    print(f"Resolution record: {result.resolution_metadata_relative_path}")
    return 0


def _display(value: object | None) -> str:
    return "—" if value is None else str(value)

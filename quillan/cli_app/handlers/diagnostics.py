"""Advanced read-only inspection of Quillan-local diagnostic events."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.diagnostic_events import (
    DiagnosticEvent,
    DiagnosticEventError,
    DiagnosticEventListing,
    list_diagnostic_events,
    load_diagnostic_event,
)


def _event_document(event: DiagnosticEvent) -> dict[str, object]:
    return asdict(event)


def _print_event(event: DiagnosticEvent) -> None:
    print(f"event_id: {event.event_id}")
    print(f"occurred_at: {event.occurred_at}")
    print(f"quillan_version: {event.quillan_version}")
    print(f"core_version: {event.core_version}")
    print(f"component: {event.component}")
    print(f"workflow: {event.workflow}")
    print(f"stage: {event.stage}")
    print(f"outcome: {event.outcome}")
    print(f"category: {event.category}")
    print(f"code: {event.code}")
    print(f"class_id: {event.class_id or 'none'}")
    print(f"assignment_id: {event.assignment_id or 'none'}")
    print(f"exception_type: {event.exception_type or 'none'}")
    print(f"summary: {event.safe_summary}")
    print(f"path_context: {event.path_context or 'none'}")


def _print_listing_text(listing: DiagnosticEventListing) -> None:
    if not listing.events:
        print("diagnostic events: none")
    else:
        print(f"diagnostic events: {len(listing.events)}")
        for index, event in enumerate(listing.events):
            print()
            print(f"[{index + 1}]")
            _print_event(event)
    if listing.warning_codes:
        print()
        print(f"inspection warnings: {len(listing.warning_codes)}")
        for code in listing.warning_codes:
            print(f"- {code}")


def _print_listing_json(listing: DiagnosticEventListing) -> None:
    document = {
        "schema_version": "1",
        "events": [_event_document(event) for event in listing.events],
        "warning_codes": list(listing.warning_codes),
    }
    print(json.dumps(document, ensure_ascii=False, sort_keys=True))


def _error(action: str, error: Exception) -> int:
    print(f"Error: diagnostics {action}: {error}", file=sys.stderr)
    return 1


def handle_diagnostics_list(args: argparse.Namespace) -> int:
    try:
        listing = list_diagnostic_events(
            resolve_workspace_root(),
            limit=args.limit,
        )
    except (DiagnosticEventError, WorkspaceRootError, OSError, ValueError) as error:
        return _error("list failed", error)

    if args.format == "json":
        _print_listing_json(listing)
    else:
        _print_listing_text(listing)
    return 0


def handle_diagnostics_show(args: argparse.Namespace) -> int:
    try:
        event = load_diagnostic_event(
            resolve_workspace_root(),
            args.event_id,
        )
    except (DiagnosticEventError, WorkspaceRootError, OSError, ValueError) as error:
        return _error("show failed", error)

    if args.format == "json":
        print(json.dumps(_event_document(event), ensure_ascii=False, sort_keys=True))
    else:
        _print_event(event)
    return 0


__all__ = [
    "handle_diagnostics_list",
    "handle_diagnostics_show",
]

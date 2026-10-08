"""Issue #419 Slice 8: explicit, safe direct-CLI retained scan recovery.

Do not infer routes, decode QR payloads, select evidence, or write Core
resolution metadata. Mutations require --yes and invoke the existing service.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pds_core.route_registrations import load_route_registration
from pds_core.routing_models import ModuleRecordRef, ModuleWorkRef, RouteLocator
from pds_core.workspace import resolve_workspace_root

from quillan.scan_recovery_completion import (
    CompletedScanRecovery,
    ScanRecoveryExecutionError,
    execute_prepared_scan_recovery,
)
from quillan.scan_recovery_historical import (
    HistoricalScanRecoveryError,
    discover_historical_scan_recoveries,
    replay_historical_scan_recovery,
)
from quillan.scan_recovery_preflight import (
    PreparedScanRecovery,
    prepare_scan_review_recovery,
)
from quillan.scan_review_resolution import discover_scan_review_items

_SCHEMA_VERSION = "1"


def _json_out(document: dict[str, Any], *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    print(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")), file=stream)


def _error(
    args: argparse.Namespace,
    operation: str,
    error: Exception,
    *,
    stage: str | None = None,
    usage: bool = False,
) -> int:
    if getattr(args, "format", "text") == "json":
        payload: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "operation": operation,
            "status": "error",
            "error": str(error),
            "stage": stage,
        }
        if isinstance(error, ScanRecoveryExecutionError):
            payload["verified_observation_id"] = error.verified_observation_id
        _json_out(payload, error=True)
    else:
        print(f"Error: {error}", file=sys.stderr)
    return 2 if usage else 1


def _explicit_route(
    root: Path, args: argparse.Namespace
) -> tuple[RouteLocator, ModuleRecordRef]:
    # The CLI deliberately requires *all* route identity; never substitute an
    # inferred route or a decoded failed QR payload.
    if not all((args.route_id, args.route_class_id, args.route_assignment_id)):
        raise ValueError(
            "Exact registered route requires --route-id, --route-class-id, "
            "and --route-assignment-id together."
        )
    locator = RouteLocator(
        "PDS2",
        ModuleWorkRef("quillan", args.route_class_id, args.route_assignment_id),
        args.route_id,
    )
    return locator, load_route_registration(root, locator).target


def _preview(
    root: Path, args: argparse.Namespace
) -> PreparedScanRecovery:
    if getattr(args, "recorded_route", False):
        if any((args.route_id, args.route_class_id, args.route_assignment_id)):
            raise ValueError("--recorded-route cannot be combined with route identity.")
        return prepare_scan_review_recovery(
            root, args.failure_id, use_recorded_route=True
        )
    locator, target = _explicit_route(root, args)
    return prepare_scan_review_recovery(
        root, args.failure_id, route_locator=locator, target=target
    )


def _preview_document(prepared: PreparedScanRecovery) -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "operation": "preflight",
        "status": "eligible",
        "failure_id": prepared.failure_id,
        "failure_category": prepared.failure_category,
        "physical_page": prepared.source_page_number,
        "physical_page_count": prepared.source_page_count,
        "source_scan_id": prepared.retained_source.source_scan_id,
        "source_sha256": prepared.retained_source.source_sha256,
        "class_id": prepared.class_id,
        "assignment_id": prepared.assignment_id,
        "student_id": prepared.student_id,
        "logical_page": prepared.logical_page,
        "total_pages": prepared.total_pages,
        "route_id": prepared.route_locator.route_id,
        "page_id": prepared.page_id,
        "route_origin": prepared.route_origin,
        "historical_resolution_id": prepared.historical_resolution_id,
    }


def _completion_document(
    result: CompletedScanRecovery, *, operation: str
) -> dict[str, Any]:
    observation = result.persisted.persisted.observation
    return {
        "schema_version": _SCHEMA_VERSION,
        "operation": operation,
        "status": "completed",
        "failure_id": result.failure_id,
        "evidence_id": result.evidence_id,
        "completion_state": result.completion_state,
        "reviewable": result.reviewable,
        "observation_status": result.observation_status,
        "submission_status": result.submission_status,
        "historical_route_reused": result.historical_route_reused,
        "class_id": observation.class_id,
        "assignment_id": observation.assignment_id,
        "student_id": observation.student_id,
        "logical_page": observation.logical_page,
        "source_scan_id": observation.source_scan_id,
        "physical_page": observation.source_page_number,
        "route_id": observation.route_id,
        "page_id": observation.page_id,
    }


def handle_list_scan_recoveries(args: argparse.Namespace) -> int:
    """List active and historical items with provenance-aware states, read-only."""
    try:
        root = resolve_workspace_root()
        scan = discover_scan_review_items(root, include_resolved=True)
        historical = discover_historical_scan_recoveries(root)
        by_failure = {item.failure_id: item for item in historical.items}
        items: list[dict[str, Any]] = []
        for item in scan.items:
            state: str
            if item.latest_resolution_status == "resolved":
                recorded = by_failure.get(item.failure_id)
                if recorded is None:
                    continue  # Other resolved teacher decisions are not routes.
                state = recorded.state
                resolution_id = recorded.resolution_id
                evidence_id = recorded.observation_id
            else:
                state = "route_selection_required"
                resolution_id = None
                evidence_id = None
            items.append({
                "failure_id": item.failure_id,
                "failure_category": item.failure_category,
                "routing_status": item.display_status,
                "recovery_state": state,
                "source_page_number": item.source_page_number,
                "class_id": item.class_id,
                "assignment_id": item.assignment_id,
                "historical_resolution_id": resolution_id,
                "evidence_id": evidence_id,
            })
        warnings = list(dict.fromkeys((*scan.warnings, *historical.warnings)))
    except (OSError, ValueError, RuntimeError) as error:
        return _error(args, "list", error)
    if args.format == "json":
        _json_out({
            "schema_version": _SCHEMA_VERSION,
            "operation": "list",
            "status": "ok",
            "items": items,
            "warnings": warnings,
        })
    else:
        print("Scan recovery inventory (read-only)")
        for row in items:
            print(f"{row['failure_id']}: {row['recovery_state']} "
                  f"(physical page {row['source_page_number']})")
            if row["historical_resolution_id"] is not None:
                print(f"  Recorded route: {row['historical_resolution_id']}")
        if not items:
            print("No eligible scan recovery items.")
        if warnings:
            print(f"Warning: {len(warnings)} invalid scan-review record(s) skipped.")
    return 0


def handle_preflight_scan_recovery(args: argparse.Namespace) -> int:
    """Verify a chosen recorded or explicit route without materialization."""
    try:
        root = resolve_workspace_root()
        prepared = _preview(root, args)
    except (OSError, ValueError, RuntimeError) as error:
        return _error(args, "preflight", error, stage="preflight")
    document = _preview_document(prepared)
    if args.format == "json":
        _json_out(document)
    else:
        print(f"Eligible retained physical page: {document['physical_page']} "
              f"of {document['physical_page_count']}")
        print(f"Failure: {document['failure_id']}")
        print(f"Class: {document['class_id']}; Assignment: {document['assignment_id']}")
        print(f"Student: {document['student_id']}; logical page: "
              f"{document['logical_page']} of {document['total_pages']}")
        print(f"Registered route: {document['route_id']}")
        print(f"Recorded decision: {document['historical_resolution_id'] or 'none'}")
        print("Read-only preflight: no evidence or resolution was written.")
    return 0


def _confirm_mutation(args: argparse.Namespace, operation: str) -> int | None:
    if args.yes:
        return None
    return _error(
        args, operation,
        ValueError("Recovery writes require explicit --yes; no files were changed."),
        stage="confirmation", usage=True,
    )


def _print_completion(args: argparse.Namespace, result: CompletedScanRecovery, *, operation: str) -> None:
    document = _completion_document(result, operation=operation)
    if args.format == "json":
        _json_out(document)
        return
    print(f"Verified evidence ID: {result.evidence_id}")
    print(f"Observation: {result.observation_status}")
    print(f"Submission: {result.submission_status}")
    print(f"Completion: {result.completion_state}")
    if result.completion_state == "ready_for_review":
        print("Recovered evidence is selected and available through Open Evidence.")
    elif result.completion_state == "selection_needed":
        print("Recovered evidence is a candidate; teacher selection is still required.")
    else:
        print("Teacher-controlled page state requires separate action.")
    print("Existing Core routing resolution records were not modified.")


def handle_recover_scan_review(args: argparse.Namespace) -> int:
    """Only materialize an explicitly named registered route with --yes."""
    denied = _confirm_mutation(args, "recover")
    if denied is not None:
        return denied
    try:
        root = resolve_workspace_root()
        prepared = _preview(root, args)
    except (OSError, ValueError, RuntimeError) as error:
        return _error(args, "recover", error, stage="preflight")
    try:
        result = execute_prepared_scan_recovery(root, prepared)
    except ScanRecoveryExecutionError as error:
        return _error(args, "recover", error, stage=error.stage)
    _print_completion(args, result, operation="recover")
    return 0


def handle_replay_scan_recovery(args: argparse.Namespace) -> int:
    """Replay an exact latest historical resolution only with --yes."""
    denied = _confirm_mutation(args, "replay")
    if denied is not None:
        return denied
    try:
        root = resolve_workspace_root()
        result = replay_historical_scan_recovery(
            root, args.failure_id, expected_resolution_id=args.expected_resolution_id
        )
    except ScanRecoveryExecutionError as error:
        return _error(args, "replay", error, stage=error.stage)
    except (OSError, ValueError, RuntimeError, HistoricalScanRecoveryError) as error:
        return _error(args, "replay", error, stage="preflight")
    _print_completion(args, result, operation="replay")
    return 0


__all__ = [
    "handle_list_scan_recoveries",
    "handle_preflight_scan_recovery",
    "handle_recover_scan_review",
    "handle_replay_scan_recovery",
]

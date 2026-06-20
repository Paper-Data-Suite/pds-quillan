"""Command-line interface for Quillan."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from pds_core.pds1 import Pds1PayloadError, parse_pds1_payload
from pds_core.workspace import (
    WorkspaceRootError,
    WorkspaceStatus,
    clear_saved_workspace_root,
    ensure_workspace_root,
    inspect_workspace_root,
    resolve_workspace_root,
    save_workspace_root,
)

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.evidence_filing import (
    EvidenceFilingError,
    RoutedEvidenceFile,
    file_routed_response_evidence,
)
from quillan.menu import launch_menu
from quillan.route_planning import (
    DecodedResponsePage,
    RouteFailure,
    plan_decoded_response_page_route,
)
from quillan.routing_review import (
    RoutingReviewError,
    RoutingReviewRecord,
    preserve_evidence_filing_error_for_review,
    preserve_route_failure_for_review,
    preserve_routing_failure_for_review,
)
from quillan.standards import StandardsProfileError, load_standards_profile

APP_DESCRIPTION = "Quillan: standards-based writing evidence capture"


def main(argv: list[str] | None = None) -> int:
    """Run the Quillan command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-standards":
        _handle_validate_standards(args.path)
        return 0

    if args.command == "validate-assignment":
        _handle_validate_assignment(args.path)
        return 0

    if args.command == "route-scan":
        return _handle_route_scan(args.source_file, args.payload)

    if args.command == "workspace" and args.workspace_command == "show":
        return _handle_workspace_show()

    if args.command == "workspace" and args.workspace_command == "set":
        return _handle_workspace_set(args.path)

    if args.command == "workspace" and args.workspace_command == "validate":
        return _handle_workspace_validate()

    if args.command == "workspace" and args.workspace_command == "reset":
        return _handle_workspace_reset()

    if args.command is None or args.command == "menu":
        return launch_menu(
            _handle_workspace_show,
            _handle_workspace_set,
            _handle_workspace_validate,
            _handle_workspace_reset,
        )

    parser.print_help()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(description=APP_DESCRIPTION)
    subparsers = parser.add_subparsers(dest="command")

    validate_standards_parser = subparsers.add_parser(
        "validate-standards",
        help="Validate a standards profile JSON file.",
    )
    validate_standards_parser.add_argument(
        "path",
        type=Path,
        help="Path to the standards profile JSON file.",
    )

    validate_assignment_parser = subparsers.add_parser(
        "validate-assignment",
        help="Validate an assignment config JSON file.",
    )
    validate_assignment_parser.add_argument(
        "path",
        type=Path,
        help="Path to the assignment config JSON file.",
    )

    route_scan_parser = subparsers.add_parser(
        "route-scan",
        help="Route a scan using an already-decoded Quillan PDS1 payload.",
        description=(
            "Route a scan file using an already-decoded Quillan PDS1 payload. "
            "Exit 0 means the file was routed or safely preserved for review; "
            "exit 1 means the input could not be handled safely."
        ),
    )
    route_scan_parser.add_argument(
        "source_file",
        type=Path,
        help="Path to the selected source scan file.",
    )
    route_scan_parser.add_argument(
        "--payload",
        required=True,
        help="Already-decoded canonical PDS1 payload text.",
    )

    workspace_parser = subparsers.add_parser(
        "workspace",
        help="Manage the shared Paper Data Suite workspace.",
    )
    workspace_subparsers = workspace_parser.add_subparsers(
        dest="workspace_command"
    )
    workspace_subparsers.add_parser(
        "show",
        help="Show the active Paper Data Suite workspace status.",
    )
    workspace_set_parser = workspace_subparsers.add_parser(
        "set",
        help="Validate, create, and save a shared workspace root.",
    )
    workspace_set_parser.add_argument(
        "path",
        type=Path,
        help="Folder to use as the shared Paper Data Suite workspace.",
    )
    workspace_subparsers.add_parser(
        "validate",
        help="Validate or create the currently resolved workspace root.",
    )
    workspace_subparsers.add_parser(
        "reset",
        help="Clear the saved workspace preference without deleting files.",
    )

    subparsers.add_parser(
        "menu",
        help="Launch the teacher-facing interactive menu.",
    )

    return parser


def _handle_validate_standards(path: Path) -> None:
    """Validate a standards profile and print a user-facing result."""
    try:
        profile = load_standards_profile(path)
    except StandardsProfileError as error:
        raise SystemExit(f"Invalid standards profile: {error}") from error

    print(f"Valid standards profile: {profile['profile_id']}")


def _handle_validate_assignment(path: Path) -> None:
    """Validate an assignment config and print a user-facing result."""
    try:
        assignment = load_assignment_config(path)
    except AssignmentConfigError as error:
        raise SystemExit(f"Invalid assignment config: {error}") from error

    print(f"Valid assignment config: {assignment['assignment_id']}")


def _handle_route_scan(source_file: Path, payload_text: str) -> int:
    """Route one source scan from caller-supplied decoded PDS1 text."""
    intake_timestamp = datetime.now(timezone.utc)
    try:
        workspace_root = resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: could not resolve the PDS workspace: {error}")
        return 1
    except Exception as error:
        print(f"Error: unexpected workspace resolution failure: {error}")
        return 1

    if not _validate_route_scan_source_file(source_file):
        return 1

    try:
        payload = parse_pds1_payload(payload_text)
    except Pds1PayloadError as error:
        return _preserve_payload_parse_failure(
            workspace_root,
            source_file=source_file,
            payload_text=payload_text,
            error=error,
            created_at=intake_timestamp,
        )
    except Exception as error:
        print(f"Error: unexpected PDS1 payload parsing failure: {error}")
        return 1

    decoded_page = DecodedResponsePage(
        module=payload.module,
        document_type=payload.metadata.get("doc"),
        class_id=payload.class_id,
        assignment_id=payload.assignment_id,
        student_id=payload.student_id,
        page_number=payload.page,
        raw_payload=payload_text,
    )

    try:
        route_result = plan_decoded_response_page_route(
            workspace_root,
            decoded_page,
        )
        if isinstance(route_result, RouteFailure):
            review_record = preserve_route_failure_for_review(
                workspace_root,
                route_failure=route_result,
                source_filename=source_file.name,
                created_at=intake_timestamp,
            )
            _print_route_failure_review(route_result, review_record)
            return 0

        try:
            filed_evidence = file_routed_response_evidence(
                workspace_root,
                route_plan=route_result,
                source_file_path=source_file,
                intake_timestamp=intake_timestamp,
            )
        except EvidenceFilingError as error:
            review_record = preserve_evidence_filing_error_for_review(
                workspace_root,
                error=error,
                route_plan=route_result,
                source_filename=source_file.name,
                created_at=intake_timestamp,
            )
            _print_evidence_filing_review(error, review_record)
            return 0
    except RoutingReviewError as error:
        print(f"Error: could not preserve scan routing failure for review: {error}")
        return 1
    except Exception as error:
        print(f"Error: unexpected route-scan failure: {error}")
        return 1

    _print_routed_evidence(filed_evidence)
    return 0


def _validate_route_scan_source_file(source_file: Path) -> bool:
    """Return whether the selected scan is an existing readable file."""
    try:
        if not source_file.is_file():
            print(
                "Error: source file must be an existing regular file: "
                f"{source_file}"
            )
            return False
        with source_file.open("rb"):
            pass
    except OSError as error:
        print(f"Error: source file is not readable: {error}")
        return False
    return True


def _preserve_payload_parse_failure(
    workspace_root: Path,
    *,
    source_file: Path,
    payload_text: str,
    error: Pds1PayloadError,
    created_at: datetime,
) -> int:
    """Preserve malformed payload context without inventing route identity."""
    try:
        review_record = preserve_routing_failure_for_review(
            workspace_root,
            failure_category="payload_invalid",
            failure_message=str(error),
            source_filename=source_file.name,
            module="quillan",
            detected_payload=payload_text,
            module_details={
                "failure_origin": "payload_parse",
                "parse_error": str(error),
            },
            created_at=created_at,
        )
    except RoutingReviewError as review_error:
        print(
            "Error: payload was invalid and could not be preserved for review: "
            f"{review_error}"
        )
        return 1
    except Exception as unexpected_error:
        print(
            "Error: unexpected failure while preserving invalid payload: "
            f"{unexpected_error}"
        )
        return 1

    print("Quillan response page was not routed; preserved for review.")
    print(f"Reason: {error}")
    print("Category: payload_invalid")
    print(f"Review record: {review_record.failure_metadata_relative_path}")
    return 0


def _print_routed_evidence(filed_evidence: RoutedEvidenceFile) -> None:
    """Print a concise successful-route summary."""
    duplicate = (
        "no"
        if filed_evidence.duplicate_number is None
        else f"yes (__dup_{filed_evidence.duplicate_number:03d})"
    )
    print("Routed Quillan response page.")
    print(
        "Retained source: "
        f"{filed_evidence.retained_source.retained_source_relative_path}"
    )
    print(f"Routed evidence: {filed_evidence.routed_evidence_relative_path}")
    print(f"Class: {filed_evidence.class_id}")
    print(f"Assignment: {filed_evidence.assignment_id}")
    print(f"Student: {filed_evidence.student_id}")
    print(f"Page: {filed_evidence.page_number}")
    print(f"Duplicate: {duplicate}")


def _print_route_failure_review(
    route_failure: RouteFailure,
    review_record: RoutingReviewRecord,
) -> None:
    """Print a safely preserved route-planning failure summary."""
    print("Quillan response page was not routed; preserved for review.")
    print(f"Reason: {route_failure.failure_message}")
    print(f"Category: {route_failure.failure_category}")
    print(f"Review record: {review_record.failure_metadata_relative_path}")


def _print_evidence_filing_review(
    error: EvidenceFilingError,
    review_record: RoutingReviewRecord,
) -> None:
    """Print a safely preserved evidence-filing failure summary."""
    print("Quillan response page could not be filed; preserved for review.")
    print(f"Reason: {error}")
    print("Category: evidence_write_failed")
    print(f"Review record: {review_record.failure_metadata_relative_path}")


def _handle_workspace_show() -> int:
    """Print the shared Paper Data Suite workspace status."""
    try:
        status = inspect_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return 1

    _print_workspace_status(status)
    return 0


def _handle_workspace_set(path: str | Path) -> int:
    """Validate, create, and save the shared workspace root."""
    try:
        workspace_root = ensure_workspace_root(path)
        saved_root = save_workspace_root(workspace_root)
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return 1

    print("Saved PDS workspace root:")
    print(saved_root)
    print()
    print("This does not move existing Quillan or Paper Data Suite files.")
    print(
        "If PDS_WORKSPACE_ROOT is set, it still takes precedence over "
        "the saved preference."
    )
    return 0


def _handle_workspace_validate() -> int:
    """Validate or create the currently resolved shared workspace root."""
    try:
        workspace_root = resolve_workspace_root()
        validated_root = ensure_workspace_root(workspace_root)
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return 1

    print("Workspace validated successfully:")
    print(validated_root)
    return 0


def _handle_workspace_reset() -> int:
    """Clear the saved shared workspace preference without deleting files."""
    try:
        was_cleared = clear_saved_workspace_root()
        workspace_root = resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return 1

    if was_cleared:
        print("Saved PDS workspace preference cleared.")
    else:
        print("No saved PDS workspace preference was set.")
    print("No workspace files were deleted.")
    print()
    print("Current resolved PDS workspace root:")
    print(workspace_root)
    print()
    print("If PDS_WORKSPACE_ROOT is set, it still takes precedence.")
    return 0


def _print_workspace_status(status: WorkspaceStatus) -> None:
    """Print a stable, user-facing workspace status summary."""
    print("Current PDS workspace root:")
    print(status.root)
    print("\nSource:")
    print(status.source)
    print("\nExists:")
    print(_format_bool(status.exists))
    print("\nDirectory:")
    print(_format_bool(status.is_dir))
    print("\nWritable:")
    print(_format_bool(status.is_writable))
    print("\nConfig file:")
    print(status.config_path)
    print("\nDefault workspace root:")
    print(status.default_root)


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"

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

from quillan.assignment_submission_assembly import (
    AssignmentSubmissionAssemblyResult,
    assemble_assignment_submissions,
)
from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.evidence_filing import (
    EvidenceFilingError,
    RoutedEvidenceFile,
    file_routed_response_evidence,
)
from quillan.evidence_opening import EvidenceOpeningError, open_workspace_evidence
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
from quillan.submission_status import (
    AssignmentSubmissionStatus,
    list_assignment_submission_status,
)
from quillan.submission_review_opening import (
    OpenedSubmissionReview,
    SubmissionReviewOpeningError,
    open_student_submission_for_review,
)
from quillan.submission_review_state import (
    SubmissionReviewStateError,
    UpdatedSubmissionReviewState,
    update_submission_review_state,
)

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

    if args.command == "assemble-submissions":
        return _handle_assemble_submissions(
            args.class_id,
            args.assignment_id,
            expected_pages=args.expected_pages,
            overwrite=args.overwrite,
        )

    if args.command == "list-submissions":
        return _handle_list_submissions(
            args.class_id,
            args.assignment_id,
            expected_pages=args.expected_pages,
        )

    if args.command == "open-evidence":
        return _handle_open_evidence(args.evidence_path)

    if args.command == "open-submission":
        return _handle_open_submission(
            args.class_id,
            args.assignment_id,
            args.student_id,
        )

    if args.command == "set-review-state":
        return _handle_set_review_state(
            args.class_id,
            args.assignment_id,
            args.student_id,
            args.state,
        )

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

    assemble_parser = subparsers.add_parser(
        "assemble-submissions",
        help="Assemble assignment submission manifests from routed evidence.",
        description=(
            "Discover routed response evidence already filed under an "
            "assignment's scans directory and assemble one submission manifest "
            "per student. Existing manifests are skipped unless --overwrite is "
            "given."
        ),
    )
    assemble_parser.add_argument("class_id", help="Class identifier.")
    assemble_parser.add_argument("assignment_id", help="Assignment identifier.")
    assemble_parser.add_argument(
        "--expected-pages",
        type=_positive_integer_argument,
        help="Expected number of response pages per student.",
    )
    assemble_parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Fully regenerate existing manifests without preserving prior "
            "review state or teacher selections."
        ),
    )

    status_parser = subparsers.add_parser(
        "list-submissions",
        help="List read-only assignment submission and evidence status.",
        description=(
            "Load existing submission manifests and discover routed response "
            "evidence without creating or modifying any files."
        ),
    )
    status_parser.add_argument("class_id", help="Class identifier.")
    status_parser.add_argument("assignment_id", help="Assignment identifier.")
    status_parser.add_argument(
        "--expected-pages",
        type=_positive_integer_argument,
        help=(
            "Expected page count used only to show missing pages for students "
            "with routed evidence but no manifest."
        ),
    )

    open_evidence_parser = subparsers.add_parser(
        "open-evidence",
        help="Open a local evidence file from the active PDS workspace.",
        description=(
            "Open one workspace-relative local evidence file with the system "
            "default application. The path must remain inside the active PDS "
            "workspace."
        ),
    )
    open_evidence_parser.add_argument(
        "evidence_path",
        help="Workspace-relative path to an existing local evidence file.",
    )

    open_submission_parser = subparsers.add_parser(
        "open-submission",
        help="Open the selected evidence for one student submission.",
        description=(
            "Load one canonical student submission manifest and open its single "
            "selected routed evidence file. This command is read-only and "
            "requires exactly one selected evidence item."
        ),
    )
    open_submission_parser.add_argument("class_id", help="Class identifier.")
    open_submission_parser.add_argument(
        "assignment_id", help="Assignment identifier."
    )
    open_submission_parser.add_argument("student_id", help="Student identifier.")

    review_state_parser = subparsers.add_parser(
        "set-review-state",
        help="Update one student submission's lightweight review state.",
        description=(
            "Update only submission_state and updated_at in one canonical "
            "student submission manifest."
        ),
    )
    review_state_parser.add_argument("class_id", help="Class identifier.")
    review_state_parser.add_argument(
        "assignment_id", help="Assignment identifier."
    )
    review_state_parser.add_argument("student_id", help="Student identifier.")
    review_state_parser.add_argument(
        "state",
        help=(
            "Review state: unreviewed, in_progress, needs_rescan, or reviewed."
        ),
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


def _handle_assemble_submissions(
    class_id: str,
    assignment_id: str,
    *,
    expected_pages: int | None,
    overwrite: bool,
) -> int:
    """Assemble all routed evidence for one class assignment."""
    try:
        workspace_root = resolve_workspace_root()
        result = assemble_assignment_submissions(
            workspace_root,
            class_id,
            assignment_id,
            expected_pages=expected_pages,
            overwrite=overwrite,
        )
    except Exception as error:
        print(f"Error: could not assemble submission manifests: {error}")
        return 1

    _print_assignment_submission_assembly(result, workspace_root)
    return 0


def _handle_list_submissions(
    class_id: str,
    assignment_id: str,
    *,
    expected_pages: int | None,
) -> int:
    """List read-only status for one class assignment."""
    try:
        workspace_root = resolve_workspace_root()
        result = list_assignment_submission_status(
            workspace_root,
            class_id,
            assignment_id,
            expected_pages=expected_pages,
        )
    except Exception as error:
        print(f"Error: could not list submission status: {error}")
        return 1

    _print_assignment_submission_status(result, workspace_root)
    return 0


def _handle_open_evidence(evidence_path: str | Path) -> int:
    """Open one workspace-relative evidence file with the system viewer."""
    try:
        workspace_root = resolve_workspace_root()
        opened = open_workspace_evidence(workspace_root, evidence_path)
    except (WorkspaceRootError, EvidenceOpeningError) as error:
        print(f"Error: could not open evidence file: {error}")
        return 1

    print("Opened evidence file:")
    print(opened.evidence_relative_path)
    return 0


def _handle_open_submission(
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> int:
    """Open the selected evidence for one canonical student submission."""
    try:
        workspace_root = resolve_workspace_root()
        opened = open_student_submission_for_review(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
    except (WorkspaceRootError, SubmissionReviewOpeningError) as error:
        print(f"Error: could not open student submission: {error}")
        return 1

    _print_opened_submission_review(opened)
    return 0


def _print_opened_submission_review(opened: OpenedSubmissionReview) -> None:
    """Print concise teacher-facing context for opened submission evidence."""
    print("Opened submission evidence for review:")
    print(f"Class: {opened.class_id}")
    print(f"Assignment: {opened.assignment_id}")
    print(f"Student: {opened.student_id}")
    print(f"Submission state: {opened.submission_state}")
    print(f"Page: {opened.page_number}")
    print(f"Page state: {opened.page_state}")
    print(f"Evidence: {opened.evidence_id}")
    print(f"Path: {opened.evidence_relative_path}")
    print(f"Manifest: {opened.manifest_relative_path}")


def _handle_set_review_state(
    class_id: str,
    assignment_id: str,
    student_id: str,
    state: str,
) -> int:
    """Update one canonical submission's lightweight review state."""
    try:
        workspace_root = resolve_workspace_root()
        updated = update_submission_review_state(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            state,
        )
    except (WorkspaceRootError, SubmissionReviewStateError) as error:
        print(f"Error: could not update submission review state: {error}")
        return 1

    _print_updated_submission_review_state(updated)
    return 0


def _print_updated_submission_review_state(
    updated: UpdatedSubmissionReviewState,
) -> None:
    """Print a concise teacher-facing review-state update."""
    print("Updated submission review state:")
    print(f"Class: {updated.class_id}")
    print(f"Assignment: {updated.assignment_id}")
    print(f"Student: {updated.student_id}")
    print(f"Previous state: {updated.previous_state}")
    print(f"New state: {updated.new_state}")
    print(f"Manifest: {updated.manifest_relative_path}")


def _print_assignment_submission_status(
    result: AssignmentSubmissionStatus,
    workspace_root: Path,
) -> None:
    """Print a deterministic teacher-facing assignment status summary."""
    submission_states = (
        "unreviewed",
        "in_progress",
        "needs_rescan",
        "reviewed",
    )
    page_states = ("present", "missing", "duplicate", "needs_rescan", "excluded")
    submission_counts = {
        state: sum(
            status.submission_state == state
            for status in result.student_statuses
        )
        for state in submission_states
    }
    page_counts = {
        state: sum(
            page.page_state == state
            for status in result.student_statuses
            for page in status.pages
        )
        for state in page_states
    }
    page_counts["missing"] += sum(
        len(status.missing_pages)
        for status in result.student_statuses
        if status.manifest_path is None
    )
    unselected_count = sum(
        len(status.unselected_present_pages)
        for status in result.student_statuses
    )

    print(
        f"Submission status for assignment {result.assignment_id}"
    )
    print()
    print(f"Students with manifests: {len(result.students_with_manifests)}")
    print(
        "Students with routed evidence: "
        f"{len(result.students_with_routed_evidence)}"
    )
    print(
        f"Students needing assembly: {len(result.students_without_manifests)}"
    )
    print(
        f"Unassembled routed files: {len(result.unassembled_routed_files)}"
    )
    print(f"Skipped routed files: {len(result.skipped_routed_files)}")
    print()
    print("Submission states:")
    for state in submission_states:
        print(f"- {state}: {submission_counts[state]}")
    print()
    print("Page states:")
    for state in page_states:
        print(f"- {state}: {page_counts[state]}")
    print(f"- present but unselected: {unselected_count}")

    if result.student_statuses:
        print()
        print("Students:")
        for status in result.student_statuses:
            if status.manifest_path is None:
                routed_details = "routed evidence exists; no manifest"
                if status.missing_pages:
                    routed_details += (
                        "; missing="
                        f"{_format_page_numbers(status.missing_pages)}"
                    )
                print(f"- {status.student_id}: {routed_details}")
                continue

            counts = {
                state: sum(page.page_state == state for page in status.pages)
                for state in page_states
            }
            detail_parts = [
                f"{state}={counts[state]}"
                for state in page_states
                if counts[state]
            ]
            if status.unselected_present_pages:
                detail_parts.append(
                    "present-but-unselected="
                    f"{len(status.unselected_present_pages)}"
                )
            suffix = ", ".join(detail_parts) if detail_parts else "no pages"
            print(
                f"- {status.student_id}: {status.submission_state}; {suffix}"
            )

    if result.skipped_routed_files:
        print()
        print("Skipped routed files:")
        for skipped in result.skipped_routed_files:
            print(
                f"- {_workspace_relative_display(skipped.path, workspace_root)}"
                f" — {skipped.reason}"
            )

    if result.unassembled_routed_files:
        print()
        print("Unassembled routed files:")
        for path in result.unassembled_routed_files:
            print(f"- {_workspace_relative_display(path, workspace_root)}")


def _print_assignment_submission_assembly(
    result: AssignmentSubmissionAssemblyResult,
    workspace_root: Path,
) -> None:
    """Print a concise assignment assembly summary."""
    missing = sum(
        len(summary.missing_pages) for summary in result.student_summaries
    )
    duplicate = sum(
        len(summary.duplicate_pages) for summary in result.student_summaries
    )
    needs_rescan = sum(
        len(summary.needs_rescan_pages) for summary in result.student_summaries
    )
    excluded = sum(
        len(summary.excluded_pages) for summary in result.student_summaries
    )

    print(
        "Assembled submission manifests for assignment "
        f"{result.assignment_id}."
    )
    print()
    print(f"Students with routed evidence: {len(result.students_with_evidence)}")
    print(f"Created manifests: {len(result.written_manifests)}")
    print(
        "Skipped existing manifests: "
        f"{len(result.skipped_existing_manifests)}"
    )
    print(f"Skipped files: {len(result.skipped_files)}")
    print(f"Missing pages: {missing}")
    print(f"Duplicate pages: {duplicate}")
    print(f"Needs-rescan pages: {needs_rescan}")
    print(f"Excluded pages: {excluded}")
    print("Failures: 0")

    _print_path_section(
        "Created", result.written_manifests, workspace_root
    )
    _print_path_section(
        "Skipped existing",
        result.skipped_existing_manifests,
        workspace_root,
    )
    if result.skipped_files:
        print()
        print("Skipped files:")
        for skipped in result.skipped_files:
            print(
                f"- {_workspace_relative_display(skipped.path, workspace_root)}"
                f" — {skipped.reason}"
            )

    state_details = [
        (
            summary.student_id,
            summary.missing_pages,
            summary.duplicate_pages,
            summary.needs_rescan_pages,
            summary.excluded_pages,
        )
        for summary in result.student_summaries
        if (
            summary.missing_pages
            or summary.duplicate_pages
            or summary.needs_rescan_pages
            or summary.excluded_pages
        )
    ]
    if state_details:
        print()
        print("Page-state details:")
        for student_id, missing_pages, duplicate_pages, rescan_pages, excluded_pages in (
            state_details
        ):
            details = []
            if missing_pages:
                details.append(f"missing={_format_page_numbers(missing_pages)}")
            if duplicate_pages:
                details.append(
                    f"duplicate={_format_page_numbers(duplicate_pages)}"
                )
            if rescan_pages:
                details.append(
                    f"needs-rescan={_format_page_numbers(rescan_pages)}"
                )
            if excluded_pages:
                details.append(
                    f"excluded={_format_page_numbers(excluded_pages)}"
                )
            print(f"- {student_id}: {', '.join(details)}")


def _print_path_section(
    heading: str, paths: tuple[Path, ...], workspace_root: Path
) -> None:
    if not paths:
        return
    print()
    print(f"{heading}:")
    for path in paths:
        print(f"- {_workspace_relative_display(path, workspace_root)}")


def _workspace_relative_display(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(
            workspace_root.resolve(strict=False)
        ).as_posix()
    except (OSError, ValueError):
        return str(path)


def _format_page_numbers(page_numbers: tuple[int, ...]) -> str:
    return ",".join(str(page_number) for page_number in page_numbers)


def _positive_integer_argument(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


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

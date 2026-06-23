"""Argument parser construction for the Quillan CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from quillan.cli_app.arguments import (
    location_value,
    non_negative_integer,
    non_negative_number,
    positive_integer,
    positive_number,
)
from quillan.cli_app.handlers.exports import (
    handle_export_class_summary,
    handle_export_feedback,
    handle_export_standards_summary,
)
from quillan.cli_app.handlers.decoding import handle_decode_scan
from quillan.cli_app.handlers.review import (
    handle_add_comment,
    handle_add_note,
    handle_add_tag,
    handle_set_score,
)
from quillan.cli_app.handlers.routing import handle_route_scan
from quillan.cli_app.handlers.submissions import (
    handle_assemble_submissions,
    handle_list_submissions,
    handle_open_evidence,
    handle_open_submission,
    handle_set_review_state,
)
from quillan.cli_app.handlers.validation import (
    handle_validate_assignment,
    handle_validate_standards,
)
from quillan.cli_app.handlers.workspace import (
    handle_menu,
    handle_workspace_reset,
    handle_workspace_set,
    handle_workspace_show,
    handle_workspace_validate,
)

APP_DESCRIPTION = "Quillan: standards-based writing evidence capture"


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser and register command handlers."""
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
    validate_standards_parser.set_defaults(handler=handle_validate_standards)

    validate_assignment_parser = subparsers.add_parser(
        "validate-assignment",
        help="Validate an assignment config JSON file.",
    )
    validate_assignment_parser.add_argument(
        "path",
        type=Path,
        help="Path to the assignment config JSON file.",
    )
    validate_assignment_parser.set_defaults(handler=handle_validate_assignment)

    route_scan_parser = subparsers.add_parser(
        "route-scan",
        help="Route one Quillan response scan from payload text or image QR.",
        description=(
            "Route one scan file using either an already-decoded Quillan PDS1 "
            "payload or a QR payload decoded from a supported local image. "
            "Exit 0 means the file was routed or safely preserved for review; "
            "exit 1 means the input could not be handled safely."
        ),
    )
    route_scan_parser.add_argument(
        "source_file",
        type=Path,
        help="Path to the selected source scan file.",
    )
    payload_group = route_scan_parser.add_mutually_exclusive_group(
        required=True
    )
    payload_group.add_argument(
        "--payload",
        help="Already-decoded canonical PDS1 payload text.",
    )
    payload_group.add_argument(
        "--decode-qr",
        action="store_true",
        help="Decode the Quillan response-page QR payload from the source image.",
    )
    route_scan_parser.set_defaults(handler=handle_route_scan)

    decode_scan_parser = subparsers.add_parser(
        "decode-scan",
        help="Decode a Quillan response-page QR payload without routing.",
        description=(
            "Decode one supported local image file, report the raw QR payload "
            "and Quillan response-page identity, and exit without routing, "
            "copying, preserving, assembling, or writing workspace data."
        ),
    )
    decode_scan_parser.add_argument(
        "source_file",
        type=Path,
        help="Path to a supported local image scan file.",
    )
    decode_scan_parser.add_argument(
        "--hide-payload",
        action="store_true",
        help="Suppress raw QR payload text in diagnostic output.",
    )
    decode_scan_parser.set_defaults(handler=handle_decode_scan)

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
        type=positive_integer,
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
    assemble_parser.set_defaults(handler=handle_assemble_submissions)

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
        type=positive_integer,
        help=(
            "Expected page count used only to show missing pages for students "
            "with routed evidence but no manifest."
        ),
    )
    status_parser.set_defaults(handler=handle_list_submissions)

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
    open_evidence_parser.set_defaults(handler=handle_open_evidence)

    open_submission_parser = subparsers.add_parser(
        "open-submission",
        help="Open the selected evidence for one student submission.",
        description=(
            "Load one canonical student submission manifest and open its single "
            "selected routed evidence file. This command is read-only and "
            "requires exactly one selected evidence item."
        ),
    )
    _add_submission_identity_arguments(open_submission_parser)
    open_submission_parser.set_defaults(handler=handle_open_submission)

    review_state_parser = subparsers.add_parser(
        "set-review-state",
        help="Update one student submission's lightweight review state.",
        description=(
            "Update only submission_state and updated_at in one canonical "
            "student submission manifest."
        ),
    )
    _add_submission_identity_arguments(review_state_parser)
    review_state_parser.add_argument(
        "state",
        help=(
            "Review state: unreviewed, in_progress, needs_rescan, or reviewed."
        ),
    )
    review_state_parser.set_defaults(handler=handle_set_review_state)

    add_note_parser = subparsers.add_parser(
        "add-note",
        help="Add a teacher note to one student review record.",
        description=(
            "Append one teacher-entered note to the canonical review.json for "
            "a student submission. Creates review.json when the adjacent "
            "submission.json exists and validates."
        ),
    )
    _add_submission_identity_arguments(add_note_parser)
    add_note_parser.add_argument(
        "--text",
        required=True,
        help="Non-empty teacher note text.",
    )
    add_note_parser.set_defaults(handler=handle_add_note)

    add_tag_parser = subparsers.add_parser(
        "add-tag",
        help="Add a structured teacher tag to one student review record.",
        description=(
            "Append one teacher-entered structured tag to the canonical "
            "review.json for a student submission. Creates review.json when "
            "the adjacent submission.json exists and validates."
        ),
    )
    _add_submission_identity_arguments(add_tag_parser)
    add_tag_parser.add_argument(
        "--label", required=True, help="Teacher tag label."
    )
    add_tag_parser.add_argument(
        "--polarity",
        required=True,
        help="Tag polarity: positive, developing, negative, or neutral.",
    )
    add_tag_parser.add_argument(
        "--standard",
        help="Optional standards-profile code.",
    )
    add_tag_parser.add_argument(
        "--comment-id",
        help="Optional reusable comment ID under --standard.",
    )
    add_tag_parser.add_argument(
        "--severity",
        type=non_negative_integer,
        help="Optional non-negative organizational severity.",
    )
    add_tag_parser.add_argument(
        "--note", help="Optional teacher note for the tag."
    )
    add_tag_parser.add_argument(
        "--page",
        type=positive_integer,
        help="Optional submission page number.",
    )
    add_tag_parser.add_argument(
        "--evidence-id",
        help="Optional evidence ID from submission.json.",
    )
    add_tag_parser.add_argument(
        "--location-type",
        help="Optional controlled location type.",
    )
    add_tag_parser.add_argument(
        "--location-value",
        type=location_value,
        help="Optional positive integer or non-empty location value.",
    )
    add_tag_parser.set_defaults(handler=handle_add_tag)

    add_comment_parser = subparsers.add_parser(
        "add-comment",
        help="Select one reusable comment-bank comment for a student review record.",
        description=(
            "Append one teacher-selected reusable comment from a shared comment "
            "bank to the canonical review.json for a student submission. The "
            "selected comment snapshots label and text so later bank edits do "
            "not alter existing reviews."
        ),
    )
    _add_submission_identity_arguments(add_comment_parser)
    add_comment_parser.add_argument(
        "--bank", required=True, help="Shared comment-bank identifier."
    )
    add_comment_parser.add_argument(
        "--comment-id",
        required=True,
        help="Reusable source comment identifier.",
    )
    add_comment_parser.add_argument(
        "--standard", help="Optional standard code from the source comment."
    )
    feedback_group = add_comment_parser.add_mutually_exclusive_group()
    feedback_group.add_argument(
        "--include-in-feedback",
        dest="include_in_feedback",
        action="store_const",
        const=True,
        default=None,
        help="Include the selected comment in future feedback.",
    )
    feedback_group.add_argument(
        "--exclude-from-feedback",
        dest="include_in_feedback",
        action="store_const",
        const=False,
        help="Exclude the selected comment from future feedback.",
    )
    add_comment_parser.set_defaults(handler=handle_add_comment)

    set_score_parser = subparsers.add_parser(
        "set-score",
        help="Set one teacher-entered criterion score in a student review record.",
        description=(
            "Set or update one teacher-entered criterion score in the canonical "
            "review.json for a student submission. Creates review.json when "
            "the adjacent submission.json exists and validates."
        ),
    )
    _add_submission_identity_arguments(set_score_parser)
    set_score_parser.add_argument(
        "--criterion",
        required=True,
        help="Non-empty criterion identifier.",
    )
    set_score_parser.add_argument(
        "--label",
        required=True,
        help="Teacher-readable criterion label.",
    )
    set_score_parser.add_argument(
        "--score",
        required=True,
        type=non_negative_number,
        help="Finite criterion score greater than or equal to zero.",
    )
    set_score_parser.add_argument(
        "--max-score",
        required=True,
        type=positive_number,
        help="Finite maximum criterion score greater than zero.",
    )
    set_score_parser.add_argument(
        "--scale",
        help="Optional descriptive score scale.",
    )
    set_score_parser.add_argument(
        "--note",
        help="Optional teacher note for this criterion score.",
    )
    set_score_parser.set_defaults(handler=handle_set_score)

    export_feedback_parser = subparsers.add_parser(
        "export-feedback",
        help="Export student-facing feedback from one review record.",
        description=(
            "Generate a student-facing Markdown feedback file from the "
            "canonical review.json for one student submission. The export "
            "includes selected feedback comments and teacher-entered criterion "
            "scores. It does not mutate the review record, submission manifest, "
            "evidence files, or source comment banks."
        ),
    )
    _add_submission_identity_arguments(export_feedback_parser)
    export_feedback_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing exports/feedback.md file.",
    )
    export_feedback_parser.set_defaults(handler=handle_export_feedback)

    export_class_summary_parser = subparsers.add_parser(
        "export-class-summary",
        help="Export a class-level review summary CSV for one assignment.",
        description=(
            "Generate a teacher-facing CSV summary from existing submission "
            "and review records for one class assignment. The export reports "
            "review availability, review state, score totals, selected feedback "
            "counts, tag counts, and note counts. It does not mutate canonical "
            "records or evidence."
        ),
    )
    _add_assignment_identity_arguments(export_class_summary_parser)
    export_class_summary_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing exports/class_summary.csv file.",
    )
    export_class_summary_parser.set_defaults(handler=handle_export_class_summary)

    export_standards_summary_parser = subparsers.add_parser(
        "export-standards-summary",
        help="Export a standards-focused review summary CSV for one assignment.",
        description=(
            "Generate a teacher-facing CSV summary of standards-linked review "
            "tags and selected comments across one class assignment. The "
            "export reads existing review records and does not mutate "
            "canonical records, evidence, or source comment banks."
        ),
    )
    _add_assignment_identity_arguments(export_standards_summary_parser)
    export_standards_summary_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing exports/standards_summary.csv file.",
    )
    export_standards_summary_parser.set_defaults(
        handler=handle_export_standards_summary
    )

    workspace_parser = subparsers.add_parser(
        "workspace",
        help="Manage the shared Paper Data Suite workspace.",
    )
    workspace_subparsers = workspace_parser.add_subparsers(
        dest="workspace_command"
    )
    workspace_show_parser = workspace_subparsers.add_parser(
        "show",
        help="Show the active Paper Data Suite workspace status.",
    )
    workspace_show_parser.set_defaults(handler=handle_workspace_show)
    workspace_set_parser = workspace_subparsers.add_parser(
        "set",
        help="Validate, create, and save a shared workspace root.",
    )
    workspace_set_parser.add_argument(
        "path",
        type=Path,
        help="Folder to use as the shared Paper Data Suite workspace.",
    )
    workspace_set_parser.set_defaults(handler=handle_workspace_set)
    workspace_validate_parser = workspace_subparsers.add_parser(
        "validate",
        help="Validate or create the currently resolved workspace root.",
    )
    workspace_validate_parser.set_defaults(handler=handle_workspace_validate)
    workspace_reset_parser = workspace_subparsers.add_parser(
        "reset",
        help="Clear the saved workspace preference without deleting files.",
    )
    workspace_reset_parser.set_defaults(handler=handle_workspace_reset)

    menu_parser = subparsers.add_parser(
        "menu",
        help="Launch the teacher-facing interactive menu.",
    )
    menu_parser.set_defaults(handler=handle_menu)

    return parser


def _add_assignment_identity_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument("class_id", help="Class identifier.")
    parser.add_argument("assignment_id", help="Assignment identifier.")


def _add_submission_identity_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_assignment_identity_arguments(parser)
    parser.add_argument("student_id", help="Student identifier.")

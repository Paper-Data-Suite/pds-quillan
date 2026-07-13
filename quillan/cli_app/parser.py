"""Argument parser construction for the Quillan CLI."""

from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path

from quillan.cli_app.arguments import nonnegative_integer, positive_integer
from quillan.cli_app.handlers.exports import (
    handle_export_class_summary,
    handle_export_feedback,
    handle_export_student_performance_summary,
    handle_export_standards_summary,
)
from quillan.cli_app.handlers.decoding import handle_decode_scan
from quillan.cli_app.handlers.review import (
    handle_add_note,
)
from quillan.cli_app.handlers.requirements import (
    handle_requirements_list,
    handle_requirements_set_check,
    handle_requirements_set_outcome,
)
from quillan.cli_app.handlers.review_units import (
    handle_review_units_set,
    handle_review_units_show,
)
from quillan.cli_app.handlers.observations import (
    handle_observations_list,
    handle_observations_set,
)
from quillan.cli_app.handlers.ratings import (
    handle_ratings_list,
    handle_ratings_mark_complete,
    handle_ratings_set,
)
from quillan.cli_app.handlers.rosters import (
    handle_roster_add_student,
    handle_roster_create,
    handle_roster_remove_student,
    handle_roster_show,
    handle_roster_update_student,
    handle_roster_validate,
)
from quillan.cli_app.handlers.routing import handle_route_scan
from quillan.cli_app.handlers.scan_review import (
    handle_list_scan_review,
    handle_resolve_scan_review,
)
from quillan.cli_app.handlers.submissions import (
    handle_assemble_submissions,
    handle_create_plain_paper_submission,
    handle_list_submissions,
    handle_open_evidence,
    handle_open_submission,
    handle_set_review_state,
)
from quillan.cli_app.handlers.validation import handle_validate_assignment
from quillan.cli_app.handlers.assignments import (
    handle_assignment_create,
    handle_assignment_show,
    handle_assignment_validate as handle_canonical_assignment_validate,
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

    assignment_parser = subparsers.add_parser(
        "assignment", help="Create, show, and validate canonical assignments."
    )
    assignment_subparsers = assignment_parser.add_subparsers(dest="assignment_command")
    assignment_create_parser = assignment_subparsers.add_parser(
        "create", help="Create a canonical workspace assignment config."
    )
    _add_assignment_identity_arguments(assignment_create_parser)
    assignment_create_parser.add_argument("--title", required=True)
    assignment_create_parser.add_argument("--writing-type", required=True)
    prompt_group = assignment_create_parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file", type=Path)
    assignment_create_parser.add_argument("--standards-profile-id", required=True)
    assignment_create_parser.add_argument("--focus-standard-ids", required=True)
    assignment_create_parser.add_argument("--review-unit-type", default="paragraph")
    assignment_create_parser.add_argument("--review-unit-singular", default="paragraph")
    assignment_create_parser.add_argument("--review-unit-plural", default="paragraphs")
    assignment_create_parser.add_argument("--rating-scale", choices=("default",), default="default")
    assignment_create_parser.add_argument("--paragraphs-min", type=nonnegative_integer)
    assignment_create_parser.add_argument("--paragraphs-max", type=nonnegative_integer)
    assignment_create_parser.add_argument("--word-count-min", type=nonnegative_integer)
    assignment_create_parser.add_argument("--word-count-max", type=nonnegative_integer)
    assignment_create_parser.add_argument("--required-elements")
    assignment_create_parser.add_argument(
        "--allow-return-without-full-review", type=_boolean, default=True
    )
    assignment_create_parser.add_argument("--overwrite", action="store_true")
    confirmation = assignment_create_parser.add_mutually_exclusive_group()
    confirmation.add_argument("--yes", action="store_true")
    confirmation.add_argument("--dry-run", action="store_true")
    assignment_create_parser.set_defaults(handler=handle_assignment_create)

    assignment_show_parser = assignment_subparsers.add_parser(
        "show", help="Show a canonical workspace assignment config."
    )
    _add_assignment_identity_arguments(assignment_show_parser)
    assignment_show_parser.set_defaults(handler=handle_assignment_show)
    assignment_validate_parser = assignment_subparsers.add_parser(
        "validate", help="Validate a canonical assignment and workspace standards."
    )
    _add_assignment_identity_arguments(assignment_validate_parser)
    assignment_validate_parser.set_defaults(handler=handle_canonical_assignment_validate)

    requirements_parser = subparsers.add_parser(
        "requirements",
        help="Review assignment minimum requirements for one assembled submission.",
        description=(
            "List and record teacher-entered minimum-requirement judgments for "
            "one canonical assembled submission. These commands do not inspect "
            "student writing or infer checks or outcomes."
        ),
    )
    requirements_parser.set_defaults(
        handler=partial(_print_parser_help, requirements_parser)
    )
    requirements_subparsers = requirements_parser.add_subparsers(
        dest="requirements_command"
    )
    requirements_list_parser = requirements_subparsers.add_parser(
        "list",
        help="List configured requirements and current teacher-entered status.",
        description=(
            "Read the canonical assignment, assembled submission manifest, and "
            "optional review record without writing any files."
        ),
    )
    _add_submission_identity_arguments(requirements_list_parser)
    requirements_list_parser.set_defaults(handler=handle_requirements_list)

    requirements_check_parser = requirements_subparsers.add_parser(
        "set-check",
        help="Create or update one configured teacher-entered check.",
        description=(
            "Resolve a requirement key from the canonical assignment and record "
            "the teacher's explicit met/not-met judgment in canonical review.json."
        ),
    )
    _add_submission_identity_arguments(requirements_check_parser)
    requirements_check_parser.add_argument(
        "--requirement-key",
        required=True,
        help="Configured key, such as paragraphs_min or required_elements:thesis.",
    )
    requirements_check_parser.add_argument(
        "--met",
        required=True,
        type=_boolean,
        metavar="true|false",
        help="Explicit teacher judgment: true or false.",
    )
    requirements_check_parser.add_argument(
        "--note",
        help="Optional nonblank teacher note; omission clears an earlier note.",
    )
    requirements_check_parser.set_defaults(handler=handle_requirements_set_check)

    requirements_outcome_parser = requirements_subparsers.add_parser(
        "set-outcome",
        help="Set an eligible teacher-selected overall outcome.",
        description=(
            "Set met, unmet_continue_review, or returned_without_full_review "
            "after validating configured checks and canonical assignment policy."
        ),
    )
    _add_submission_identity_arguments(requirements_outcome_parser)
    requirements_outcome_parser.add_argument(
        "--outcome",
        required=True,
        choices=(
            "met",
            "unmet_continue_review",
            "returned_without_full_review",
        ),
        help="Explicit teacher-selected outcome.",
    )
    requirements_outcome_parser.add_argument(
        "--note",
        help=(
            "Optional nonblank teacher note; required when returning without "
            "full standards review."
        ),
    )
    requirements_outcome_parser.set_defaults(handler=handle_requirements_set_outcome)

    review_units_parser = subparsers.add_parser(
        "review-units",
        help="Display or replace review units for one assembled submission.",
        description=(
            "Display or explicitly replace canonical review units without inspecting "
            "student evidence or inferring unit boundaries."
        ),
    )
    review_units_parser.set_defaults(
        handler=partial(_print_parser_help, review_units_parser)
    )
    review_units_subparsers = review_units_parser.add_subparsers(
        dest="review_units_command"
    )
    review_units_show_parser = review_units_subparsers.add_parser(
        "show", help="Display current review units without writing files."
    )
    _add_submission_identity_arguments(review_units_show_parser)
    review_units_show_parser.set_defaults(handler=handle_review_units_show)

    review_units_set_parser = review_units_subparsers.add_parser(
        "set", help="Replace all review units from a count or JSON file."
    )
    _add_submission_identity_arguments(review_units_set_parser)
    review_units_source = review_units_set_parser.add_mutually_exclusive_group(
        required=True
    )
    review_units_source.add_argument(
        "--count",
        type=positive_integer,
        help="Create canonical units with sequences 1 through COUNT.",
    )
    review_units_source.add_argument(
        "--units",
        type=Path,
        help="UTF-8 JSON file containing constrained review-unit definitions.",
    )
    review_units_set_parser.set_defaults(handler=handle_review_units_set)

    observations_parser = subparsers.add_parser(
        "observations",
        help="List and record review-unit Focus Standard observations.",
        description=(
            "List or record explicit teacher-entered Focus Standard observations "
            "without inspecting evidence or inferring judgments."
        ),
    )
    observations_parser.set_defaults(
        handler=partial(_print_parser_help, observations_parser)
    )
    observations_subparsers = observations_parser.add_subparsers(
        dest="observations_command"
    )
    observations_list_parser = observations_subparsers.add_parser(
        "list", help="List all current unit-standard observation pairs."
    )
    _add_submission_identity_arguments(observations_list_parser)
    observations_list_parser.set_defaults(handler=handle_observations_list)

    observations_set_parser = observations_subparsers.add_parser(
        "set", help="Create or replace one teacher-entered observation."
    )
    _add_submission_identity_arguments(observations_set_parser)
    observations_set_parser.add_argument("--unit-id", required=True)
    observations_set_parser.add_argument("--standard-id", required=True)
    observations_set_parser.add_argument(
        "--applicable", required=True, type=_true_false, metavar="true|false"
    )
    observations_set_parser.add_argument(
        "--evidence-present", type=_true_false, metavar="true|false"
    )
    observations_set_parser.add_argument(
        "--rating", type=int, help="Optional assignment-scale unit-level rating."
    )
    observations_set_parser.add_argument("--rationale")
    observations_set_parser.add_argument(
        "--include-in-feedback", type=_true_false, metavar="true|false"
    )
    observations_set_parser.set_defaults(handler=handle_observations_set)

    ratings_parser = subparsers.add_parser(
        "ratings",
        help="List, record, and complete overall Focus Standard ratings.",
        description=(
            "Display or record explicit teacher-entered overall Focus Standard "
            "ratings without inspecting evidence or inferring judgments."
        ),
    )
    ratings_parser.set_defaults(handler=partial(_print_parser_help, ratings_parser))
    ratings_subparsers = ratings_parser.add_subparsers(dest="ratings_command")

    ratings_list_parser = ratings_subparsers.add_parser(
        "list", help="List assignment Focus Standards and current overall ratings."
    )
    _add_submission_identity_arguments(ratings_list_parser)
    ratings_list_parser.set_defaults(handler=handle_ratings_list)

    ratings_set_parser = ratings_subparsers.add_parser(
        "set", help="Create or replace one teacher-entered overall rating."
    )
    _add_submission_identity_arguments(ratings_set_parser)
    ratings_set_parser.add_argument("--standard-id", required=True)
    ratings_set_parser.add_argument(
        "--rating",
        required=True,
        type=int,
        help="Integer value from the assignment-owned rating scale.",
    )
    ratings_set_parser.add_argument(
        "--rationale",
        help="Optional teacher rationale; omission or blank text clears it.",
    )
    ratings_set_parser.add_argument(
        "--include-in-feedback",
        required=True,
        type=_true_false,
        metavar="true|false",
        help="Required explicit teacher choice: true or false.",
    )
    ratings_set_parser.set_defaults(handler=handle_ratings_set)

    ratings_complete_parser = ratings_subparsers.add_parser(
        "mark-complete",
        help="Explicitly mark overall ratings complete, including when ratings are missing.",
    )
    _add_submission_identity_arguments(ratings_complete_parser)
    ratings_complete_parser.add_argument(
        "--yes",
        required=True,
        action="store_true",
        help="Explicitly confirm completion without prompting.",
    )
    ratings_complete_parser.set_defaults(handler=handle_ratings_mark_complete)

    roster_parser = subparsers.add_parser(
        "roster",
        help="Create, show, validate, and modify canonical class rosters.",
        description=(
            "Manage canonical shared class rosters non-interactively. Student IDs "
            "are strings and leading zeros are preserved."
        ),
    )
    roster_parser.set_defaults(handler=partial(_print_parser_help, roster_parser))
    roster_subparsers = roster_parser.add_subparsers(dest="roster_command")

    roster_create_parser = roster_subparsers.add_parser(
        "create",
        help="Create a canonical roster and class metadata from a validated CSV.",
    )
    roster_create_parser.add_argument("class_id", help="Canonical class identifier.")
    roster_create_parser.add_argument(
        "--input", type=Path, required=True, help="Source roster CSV path."
    )
    roster_create_parser.add_argument(
        "--school-year",
        help="Consecutive school year (YYYY-YYYY); defaults to the active year.",
    )
    roster_create_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace both existing roster.csv and class.json; requires --yes.",
    )
    _add_write_confirmation(roster_create_parser)
    roster_create_parser.set_defaults(handler=handle_roster_create)

    roster_show_parser = roster_subparsers.add_parser(
        "show", help="Display every canonical roster column without writing."
    )
    roster_show_parser.add_argument("class_id", help="Canonical class identifier.")
    roster_show_parser.set_defaults(handler=handle_roster_show)

    roster_validate_parser = roster_subparsers.add_parser(
        "validate", help="Validate canonical roster.csv and existing class.json."
    )
    roster_validate_parser.add_argument("class_id", help="Canonical class identifier.")
    roster_validate_parser.set_defaults(handler=handle_roster_validate)

    roster_add_parser = roster_subparsers.add_parser(
        "add-student",
        help="Append one string-ID student; leading zeros are preserved.",
    )
    roster_add_parser.add_argument("class_id", help="Canonical class identifier.")
    roster_add_parser.add_argument(
        "--student-id", required=True, help="String student ID; leading zeros remain."
    )
    roster_add_parser.add_argument("--last-name", required=True)
    roster_add_parser.add_argument("--first-name", required=True)
    roster_add_parser.add_argument("--period", required=True)
    _add_optional_roster_fields(roster_add_parser)
    _add_write_confirmation(roster_add_parser)
    roster_add_parser.set_defaults(handler=handle_roster_add_student)

    roster_update_parser = roster_subparsers.add_parser(
        "update-student",
        help="Update one student while preserving its stable string student_id.",
        description=(
            "Update an active-roster student. The positional student_id is stable "
            "and cannot be changed."
        ),
    )
    roster_update_parser.add_argument("class_id", help="Canonical class identifier.")
    roster_update_parser.add_argument(
        "student_id", help="Stable string student ID; leading zeros remain."
    )
    roster_update_parser.add_argument("--last-name")
    roster_update_parser.add_argument("--first-name")
    roster_update_parser.add_argument("--period")
    _add_optional_roster_fields(roster_update_parser)
    _add_write_confirmation(roster_update_parser)
    roster_update_parser.set_defaults(handler=handle_roster_update_student)

    roster_remove_parser = roster_subparsers.add_parser(
        "remove-student",
        help="Remove one student only from the active roster.csv.",
        description=(
            "Remove a student only from the active roster. Historical evidence and "
            "all other class/module data are retained."
        ),
    )
    roster_remove_parser.add_argument("class_id", help="Canonical class identifier.")
    roster_remove_parser.add_argument(
        "student_id", help="Exact string student ID; leading zeros remain."
    )
    _add_write_confirmation(roster_remove_parser)
    roster_remove_parser.set_defaults(handler=handle_roster_remove_student)

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
        help="Route Quillan response scans from payload text or QR.",
        description=(
            "Route one scan file using either an already-decoded Quillan PDS1 "
            "payload or QR payloads decoded from a supported local image or "
            "PDF. With --decode-qr, a folder path processes supported image "
            "and PDF files directly inside that folder in deterministic order. "
            "PDF files are processed page by page. Exit 0 means all attempted "
            "scan sources were routed or safely preserved for review; exit 1 "
            "means the input or an attempted source could not be handled safely."
        ),
    )
    route_scan_parser.add_argument(
        "source_file",
        type=Path,
        help="Path to the selected source scan file, or a folder with --decode-qr.",
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
        help=(
            "Decode Quillan response-page QR payloads from a source image or "
            "PDF, or from supported image/PDF files directly inside a folder."
        ),
    )
    route_scan_parser.set_defaults(handler=handle_route_scan)

    list_scan_review_parser = subparsers.add_parser(
        "list-scan-review",
        help="List unresolved and deferred Quillan scan review items.",
        description=(
            "List valid Quillan routing-review records. Resolved records are "
            "hidden unless --include-resolved is supplied."
        ),
    )
    list_scan_review_parser.add_argument(
        "--include-resolved",
        action="store_true",
        help="Include review items whose latest resolution is resolved.",
    )
    list_scan_review_parser.add_argument(
        "--limit",
        type=positive_integer,
        help="Show at most this many matching review items.",
    )
    list_scan_review_parser.add_argument("--class-id", help="Filter by class ID.")
    list_scan_review_parser.add_argument(
        "--assignment-id", help="Filter by assignment ID."
    )
    list_scan_review_parser.add_argument(
        "--failure-category", help="Filter by shared failure category."
    )
    list_scan_review_parser.set_defaults(handler=handle_list_scan_review)

    resolve_scan_review_parser = subparsers.add_parser(
        "resolve-scan-review",
        help="Resolve or defer one Quillan scan review item.",
        description=(
            "Write a new immutable shared resolution record for one valid "
            "Quillan routing-review failure."
        ),
    )
    resolve_scan_review_parser.add_argument("failure_id", help="Failure identifier.")
    resolve_scan_review_parser.add_argument(
        "--action",
        required=True,
        choices=(
            "rescan_needed",
            "cannot_route",
            "mixed_assignment",
            "evidence_filed",
            "dismissed_duplicate",
            "other",
            "defer",
        ),
        help="Teacher-selected resolution action.",
    )
    resolve_scan_review_parser.add_argument(
        "--message",
        help="Teacher message. Required for action 'other'; defaults otherwise.",
    )
    resolve_scan_review_parser.add_argument(
        "--evidence-path",
        help=(
            "Optional workspace-relative evidence path for evidence_filed; "
            "the file is not copied or required to exist."
        ),
    )
    resolve_scan_review_parser.set_defaults(handler=handle_resolve_scan_review)

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

    plain_paper_parser = subparsers.add_parser(
        "create-plain-paper-submission",
        help="Create a review-ready submission for physical plain-paper work.",
        description=(
            "Validate and create an evidence-less submission manifest and empty "
            "review record for work completed on physical plain paper."
        ),
    )
    _add_submission_identity_arguments(plain_paper_parser)
    confirmation_group = plain_paper_parser.add_mutually_exclusive_group()
    confirmation_group.add_argument(
        "--yes",
        action="store_true",
        help="Confirm creation without an interactive prompt.",
    )
    confirmation_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report target paths without writing files.",
    )
    plain_paper_parser.set_defaults(handler=handle_create_plain_paper_submission)

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
        help="Open selected evidence pages for one student submission.",
        description=(
            "Open selected evidence pages for one student submission. By "
            "default, opens all selected evidence pages in page-number order. "
            "Use --page to open one logical response page."
        ),
    )
    _add_submission_identity_arguments(open_submission_parser)
    open_submission_parser.add_argument(
        "--page",
        type=positive_integer,
        help="Open only one logical response page number.",
    )
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

    export_feedback_parser = subparsers.add_parser(
        "export-feedback",
        help="Export student-facing feedback from one review record.",
        description=(
            "Generate student-facing feedback from the canonical review.json "
            "for one student submission. PDF export updates feedback export "
            "metadata after a successful write; Markdown remains available for "
            "compatibility."
        ),
    )
    _add_submission_identity_arguments(export_feedback_parser)
    export_feedback_parser.add_argument(
        "--format",
        choices=("markdown", "pdf", "both"),
        default="markdown",
        help="Feedback export format. Defaults to markdown for compatibility.",
    )
    export_feedback_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing feedback export files for the selected format.",
    )
    export_feedback_parser.set_defaults(handler=handle_export_feedback)

    export_class_summary_parser = subparsers.add_parser(
        "export-class-summary",
        aliases=["export-comprehensive-class-summary"],
        help="Export a comprehensive assignment-local class summary CSV for audit/troubleshooting.",
        description=(
            "Generate a comprehensive audit/troubleshooting CSV summary from "
            "existing submission and review records for one class assignment. "
            "The export reports submission/review status, minimum-requirement "
            "outcomes, Focus Standard ratings, and feedback export status. It "
            "does not mutate canonical records or evidence."
        ),
    )
    _add_assignment_identity_arguments(export_class_summary_parser)
    export_class_summary_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing exports/class_summary.csv file.",
    )
    export_class_summary_parser.set_defaults(handler=handle_export_class_summary)

    export_student_performance_parser = subparsers.add_parser(
        "export-student-performance-summary",
        help="Export a compact student-by-Focus-Standard performance summary CSV.",
        description=(
            "Generate the ordinary teacher-facing student performance report with "
            "review status, minimum requirements, and one readable rating column "
            "per assignment Focus Standard."
        ),
    )
    _add_assignment_identity_arguments(export_student_performance_parser)
    export_student_performance_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing exports/student_performance_summary.csv file.",
    )
    export_student_performance_parser.set_defaults(
        handler=handle_export_student_performance_summary
    )

    export_standards_summary_parser = subparsers.add_parser(
        "export-standards-summary",
        help="Export an assignment-local Focus Standard summary CSV.",
        description=(
            "Generate a teacher-facing assignment-local CSV summary of "
            "teacher-entered overall Focus Standard ratings for one class "
            "assignment. The export includes minimum-requirement outcomes and "
            "feedback export status, and does not mutate canonical records or "
            "evidence."
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


def _print_parser_help(parser: argparse.ArgumentParser, _args: argparse.Namespace) -> int:
    parser.print_help()
    return 0


def _add_write_confirmation(parser: argparse.ArgumentParser) -> None:
    confirmation = parser.add_mutually_exclusive_group()
    confirmation.add_argument(
        "--yes", action="store_true", help="Confirm the validated write."
    )
    confirmation.add_argument(
        "--dry-run", action="store_true", help="Validate and report without writing."
    )


def _add_optional_roster_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="COLUMN=VALUE",
        help=(
            "Set an existing optional roster column; repeat for multiple columns. "
            "This cannot add columns or set required fields."
        ),
    )


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def _true_false(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def _add_submission_identity_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    _add_assignment_identity_arguments(parser)
    parser.add_argument("student_id", help="Student identifier.")

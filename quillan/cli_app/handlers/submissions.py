"""Submission and evidence command handlers."""

from __future__ import annotations

import argparse
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignment_submission_assembly import (
    assemble_assignment_submissions,
)
from quillan.cli_app.output import (
    print_assignment_submission_assembly,
    print_assignment_submission_status,
    print_opened_submission_review,
    print_updated_submission_review_state,
)
from quillan.plain_paper_submission import (
    create_plain_paper_submission,
    plan_plain_paper_submission,
)
from quillan.submission_review_opening import (
    SubmissionReviewOpeningError,
    open_student_submission_for_review,
)
from quillan.submission_review_state import (
    SubmissionReviewStateError,
    update_submission_review_state,
)
from quillan.submission_status import list_assignment_submission_status


def handle_create_plain_paper_submission(args: argparse.Namespace) -> int:
    """Validate or create one evidence-less plain-paper submission."""
    if not args.yes and not args.dry_run:
        print(
            "Error: creating a plain-paper submission requires --yes or --dry-run.",
            file=sys.stderr,
        )
        return 1

    try:
        workspace_root = resolve_workspace_root()
        if args.dry_run:
            plan = plan_plain_paper_submission(
                workspace_root, args.class_id, args.assignment_id, args.student_id
            )
        else:
            created = create_plain_paper_submission(
                workspace_root, args.class_id, args.assignment_id, args.student_id
            )
    except Exception as error:
        action = "dry run failed" if args.dry_run else "was not created"
        print(f"Error: plain-paper submission {action}: {error}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Plain-paper submission dry run:")
        print(f"Class: {plan.class_id}")
        print(f"Assignment: {plan.assignment_id}")
        print(f"Student: {plan.student_id}")
        print(
            "Would create submission manifest: "
            f"{plan.submission_manifest_relative_path}"
        )
        print(f"Would create review record: {plan.review_record_relative_path}")
        print("No digital pages, scan records, QR records, or evidence will be created.")
        print("No files were written.")
    else:
        print("Created plain-paper submission:")
        print(f"Class: {created.class_id}")
        print(f"Assignment: {created.assignment_id}")
        print(f"Student: {created.student_id}")
        print(f"Submission manifest: {created.submission_manifest_relative_path}")
        print(f"Review record: {created.review_record_relative_path}")
        print(f"Created at: {created.created_at}")
    return 0


def handle_assemble_submissions(args: argparse.Namespace) -> int:
    """Assemble all routed evidence for one class assignment."""
    try:
        workspace_root = resolve_workspace_root()
        result = assemble_assignment_submissions(
            workspace_root,
            args.class_id,
            args.assignment_id,
        )
    except Exception as error:
        print(
            f"Error: could not assemble submission manifests: {error}",
            file=sys.stderr,
        )
        return 1

    print_assignment_submission_assembly(result, workspace_root)
    return 0 if not result.failures else 1


def handle_list_submissions(args: argparse.Namespace) -> int:
    """List read-only status for one class assignment."""
    try:
        workspace_root = resolve_workspace_root()
        result = list_assignment_submission_status(
            workspace_root,
            args.class_id,
            args.assignment_id,
        )
    except Exception as error:
        print(f"Error: could not list submission status: {error}", file=sys.stderr)
        return 1

    print_assignment_submission_status(
        result,
        workspace_root,
        show_unused_duplicate_files=True,
    )
    return 0


def handle_open_submission(args: argparse.Namespace) -> int:
    """Open selected evidence for one canonical student submission."""
    try:
        workspace_root = resolve_workspace_root()
        identity = (
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
        )
        if args.evidence_id is None:
            opened = open_student_submission_for_review(
                *identity, page_number=args.page
            )
        else:
            opened = open_student_submission_for_review(
                *identity,
                page_number=args.page,
                evidence_id=args.evidence_id,
            )
    except (WorkspaceRootError, SubmissionReviewOpeningError) as error:
        print(f"Error: could not open student submission: {error}", file=sys.stderr)
        return 1

    print_opened_submission_review(opened)
    return 0


def handle_set_review_state(args: argparse.Namespace) -> int:
    """Update one canonical manifest's lightweight submission state."""
    try:
        workspace_root = resolve_workspace_root()
        updated = update_submission_review_state(
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
            args.state,
        )
    except (WorkspaceRootError, SubmissionReviewStateError) as error:
        print(
            f"Error: could not update lightweight submission state: {error}",
            file=sys.stderr,
        )
        return 1

    print_updated_submission_review_state(updated)
    return 0

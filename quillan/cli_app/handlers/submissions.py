"""Submission and evidence command handlers."""

from __future__ import annotations

import argparse

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
from quillan.evidence_opening import EvidenceOpeningError, open_workspace_evidence
from quillan.submission_review_opening import (
    SubmissionReviewOpeningError,
    open_student_submission_for_review,
)
from quillan.submission_review_state import (
    SubmissionReviewStateError,
    update_submission_review_state,
)
from quillan.submission_status import list_assignment_submission_status


def handle_assemble_submissions(args: argparse.Namespace) -> int:
    """Assemble all routed evidence for one class assignment."""
    try:
        workspace_root = resolve_workspace_root()
        result = assemble_assignment_submissions(
            workspace_root,
            args.class_id,
            args.assignment_id,
            expected_pages=args.expected_pages,
            overwrite=args.overwrite,
        )
    except Exception as error:
        print(f"Error: could not assemble submission manifests: {error}")
        return 1

    print_assignment_submission_assembly(result, workspace_root)
    return 0


def handle_list_submissions(args: argparse.Namespace) -> int:
    """List read-only status for one class assignment."""
    try:
        workspace_root = resolve_workspace_root()
        result = list_assignment_submission_status(
            workspace_root,
            args.class_id,
            args.assignment_id,
            expected_pages=args.expected_pages,
        )
    except Exception as error:
        print(f"Error: could not list submission status: {error}")
        return 1

    print_assignment_submission_status(
        result,
        workspace_root,
        show_unused_duplicate_files=True,
    )
    return 0


def handle_open_evidence(args: argparse.Namespace) -> int:
    """Open one workspace-relative evidence file with the system viewer."""
    try:
        workspace_root = resolve_workspace_root()
        opened = open_workspace_evidence(workspace_root, args.evidence_path)
    except (WorkspaceRootError, EvidenceOpeningError) as error:
        print(f"Error: could not open evidence file: {error}")
        return 1

    print("Opened evidence file:")
    print(opened.evidence_relative_path)
    return 0


def handle_open_submission(args: argparse.Namespace) -> int:
    """Open selected evidence for one canonical student submission."""
    try:
        workspace_root = resolve_workspace_root()
        opened = open_student_submission_for_review(
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
            page_number=args.page,
        )
    except (WorkspaceRootError, SubmissionReviewOpeningError) as error:
        print(f"Error: could not open student submission: {error}")
        return 1

    print_opened_submission_review(opened)
    return 0


def handle_set_review_state(args: argparse.Namespace) -> int:
    """Update one canonical submission's lightweight review state."""
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
        print(f"Error: could not update submission review state: {error}")
        return 1

    print_updated_submission_review_state(updated)
    return 0

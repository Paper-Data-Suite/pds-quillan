"""Review-record command handlers."""

from __future__ import annotations

import argparse

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import (
    print_added_review_comment,
    print_added_review_note,
    print_added_review_tag,
    print_updated_review_score,
)
from quillan.review_comments import ReviewCommentError, add_review_comment
from quillan.review_notes import ReviewNoteError, add_review_note
from quillan.review_scores import ReviewScoreError, set_review_score
from quillan.review_tags import ReviewTagError, add_review_tag


def handle_add_note(args: argparse.Namespace) -> int:
    """Append one teacher note to a canonical review record."""
    try:
        workspace_root = resolve_workspace_root()
        added = add_review_note(
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
            args.text,
        )
    except (WorkspaceRootError, ReviewNoteError) as error:
        print(f"Error: could not add teacher note: {error}")
        return 1

    print_added_review_note(added)
    return 0


def handle_add_tag(args: argparse.Namespace) -> int:
    """Append one structured teacher tag to a canonical review record."""
    try:
        workspace_root = resolve_workspace_root()
        added = add_review_tag(
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
            label=args.label,
            polarity=args.polarity,
            standard_id=args.standard_id,
            comment_id=args.comment_id,
            severity=args.severity,
            teacher_note=args.note,
            page_number=args.page,
            evidence_id=args.evidence_id,
            location_type=args.location_type,
            location_value=args.location_value,
        )
    except (WorkspaceRootError, ReviewTagError) as error:
        print(f"Error: could not add review tag: {error}")
        return 1

    print_added_review_tag(added)
    return 0


def handle_add_comment(args: argparse.Namespace) -> int:
    """Select one shared-bank comment into a canonical review record."""
    try:
        workspace_root = resolve_workspace_root()
        added = add_review_comment(
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
            bank_id=args.bank,
            comment_id=args.comment_id,
            standard_id=args.standard_id,
            include_in_feedback=args.include_in_feedback,
        )
    except (WorkspaceRootError, ReviewCommentError) as error:
        print(f"Error: could not select review comment: {error}")
        return 1

    print_added_review_comment(added)
    return 0


def handle_set_score(args: argparse.Namespace) -> int:
    """Set one teacher-entered criterion score in a review record."""
    try:
        workspace_root = resolve_workspace_root()
        updated = set_review_score(
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
            criterion_id=args.criterion,
            label=args.label,
            score=args.score,
            max_score=args.max_score,
            scale=args.scale,
            teacher_note=args.note,
        )
    except (WorkspaceRootError, ReviewScoreError) as error:
        print(f"Error: could not set review score: {error}")
        return 1

    print_updated_review_score(updated)
    return 0

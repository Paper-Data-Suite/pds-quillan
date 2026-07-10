"""Review-record command handlers."""

from __future__ import annotations

import argparse

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import print_added_review_note
from quillan.review_notes import ReviewNoteError, add_review_note


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

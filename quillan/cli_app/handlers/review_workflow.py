"""Review workflow state command handlers."""

from __future__ import annotations

import argparse

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import print_updated_review_workflow_state
from quillan.review_workflow_state import (
    ReviewWorkflowStateError,
    set_review_workflow_state,
)


def handle_review_workflow_set_state(args: argparse.Namespace) -> int:
    """Apply one confirmed, non-interactive review workflow state override."""
    try:
        updated = set_review_workflow_state(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            args.student_id,
            args.state,
        )
    except (WorkspaceRootError, ReviewWorkflowStateError) as error:
        print(f"Error: could not update review workflow state: {error}")
        return 1
    print_updated_review_workflow_state(updated)
    return 0

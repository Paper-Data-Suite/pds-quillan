"""Export command handlers."""

from __future__ import annotations

import argparse

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.class_summary_export import (
    ClassSummaryExportError,
    export_class_review_summary,
)
from quillan.cli_app.output import (
    print_exported_class_summary,
    print_exported_feedback,
    print_exported_standards_summary,
)
from quillan.feedback_export import FeedbackExportError, export_student_feedback
from quillan.standards_summary_export import (
    StandardsSummaryExportError,
    export_standards_summary,
)


def handle_export_feedback(args: argparse.Namespace) -> int:
    """Export one student-facing Markdown feedback artifact."""
    try:
        workspace_root = resolve_workspace_root()
        exported = export_student_feedback(
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
            overwrite=args.overwrite,
        )
    except (WorkspaceRootError, FeedbackExportError) as error:
        print(f"Error: could not export student feedback: {error}")
        return 1

    print_exported_feedback(exported)
    return 0


def handle_export_class_summary(args: argparse.Namespace) -> int:
    """Export one teacher-facing assignment class summary CSV."""
    try:
        workspace_root = resolve_workspace_root()
        exported = export_class_review_summary(
            workspace_root,
            args.class_id,
            args.assignment_id,
            overwrite=args.overwrite,
        )
    except (WorkspaceRootError, ClassSummaryExportError) as error:
        print(f"Error: could not export class review summary: {error}")
        return 1

    print_exported_class_summary(exported)
    return 0


def handle_export_standards_summary(args: argparse.Namespace) -> int:
    """Export one teacher-facing assignment standards summary CSV."""
    try:
        workspace_root = resolve_workspace_root()
        exported = export_standards_summary(
            workspace_root,
            args.class_id,
            args.assignment_id,
            overwrite=args.overwrite,
        )
    except (WorkspaceRootError, StandardsSummaryExportError) as error:
        print(f"Error: could not export standards summary: {error}")
        return 1

    print_exported_standards_summary(exported)
    return 0

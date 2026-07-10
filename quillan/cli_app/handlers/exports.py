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
    print_exported_feedback_pdf,
    print_exported_student_performance_summary,
    print_exported_standards_summary,
)
from quillan.feedback_export import (
    FeedbackExportError,
    export_student_feedback,
    export_student_feedback_pdf,
)
from quillan.standards_summary_export import (
    StandardsSummaryExportError,
    export_standards_summary,
)
from quillan.student_performance_summary_export import (
    StudentPerformanceSummaryExportError,
    export_student_performance_summary,
)


def handle_export_feedback(args: argparse.Namespace) -> int:
    """Export one student-facing feedback artifact."""
    try:
        workspace_root = resolve_workspace_root()
        export_format = getattr(args, "format", "markdown")
        if export_format == "pdf":
            exported_pdf = export_student_feedback_pdf(
                workspace_root,
                args.class_id,
                args.assignment_id,
                args.student_id,
                overwrite=args.overwrite,
            )
            print_exported_feedback_pdf(exported_pdf)
            return 0
        if export_format == "both":
            exported_pdf = export_student_feedback_pdf(
                workspace_root,
                args.class_id,
                args.assignment_id,
                args.student_id,
                overwrite=args.overwrite,
                include_markdown_companion=True,
            )
            print_exported_feedback_pdf(exported_pdf)
            return 0
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
    """Export one comprehensive assignment class summary CSV."""
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


def handle_export_student_performance_summary(args: argparse.Namespace) -> int:
    """Export one compact teacher-facing student performance summary CSV."""
    try:
        workspace_root = resolve_workspace_root()
        exported = export_student_performance_summary(
            workspace_root, args.class_id, args.assignment_id, overwrite=args.overwrite
        )
    except (WorkspaceRootError, StudentPerformanceSummaryExportError) as error:
        print(f"Error: could not export student performance summary: {error}")
        return 1
    print_exported_student_performance_summary(exported)
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

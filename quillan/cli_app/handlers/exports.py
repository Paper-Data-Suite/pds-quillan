"""Export command handlers."""

from __future__ import annotations

import argparse
import sys
from typing import cast

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.batch_feedback_export import (
    BatchFeedbackExportError,
    BatchScope,
    FeedbackFormat,
    OverwritePolicy,
    build_batch_feedback_export_plan,
    execute_batch_feedback_export,
)
from quillan.batch_feedback_assembly import (
    AssemblyOutput,
    AssemblyScope,
    BatchFeedbackAssemblyError,
    build_feedback_assembly_plan,
    execute_feedback_assembly,
)
from quillan.class_summary_export import (
    ClassSummaryExportError,
    export_class_review_summary,
)
from quillan.cli_app.output import (
    print_feedback_assembly_plan,
    print_feedback_assembly_result,
    print_batch_feedback_export_plan,
    print_batch_feedback_export_result,
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
        print(f"Error: could not export student feedback: {error}", file=sys.stderr)
        return 1

    print_exported_feedback(exported)
    return 0


def handle_export_feedback_batch(args: argparse.Namespace) -> int:
    """Plan or explicitly execute one assignment-level feedback batch."""
    try:
        workspace_root = resolve_workspace_root()
        scope: BatchScope = "completed" if args.completed else "selected"
        student_ids = tuple(args.student_id or ())
        plan = build_batch_feedback_export_plan(
            workspace_root,
            args.class_id,
            args.assignment_id,
            scope=scope,
            student_ids=student_ids,
            feedback_format=cast(FeedbackFormat, args.format),
            overwrite_policy=cast(OverwritePolicy, args.overwrite_policy),
        )
    except (WorkspaceRootError, BatchFeedbackExportError) as error:
        print(f"Error: could not plan batch feedback export: {error}", file=sys.stderr)
        return 1

    print_batch_feedback_export_plan(plan)
    if args.dry_run:
        return 0

    try:
        result = execute_batch_feedback_export(workspace_root, plan)
    except BatchFeedbackExportError as error:
        print(f"Error: could not start batch feedback export: {error}", file=sys.stderr)
        return 1
    print_batch_feedback_export_result(result)
    unsuccessful = {
        "blocked_incomplete",
        "blocked_attention",
        "blocked_unknown_state",
        "state_changed",
        "export_failed",
        "verification_failed",
    }
    return 1 if any(item.outcome in unsuccessful for item in result.items) else 0


def handle_assemble_feedback_batch(args: argparse.Namespace) -> int:
    """Plan or explicitly assemble existing current feedback PDFs."""
    try:
        workspace_root = resolve_workspace_root()
        scope: AssemblyScope = "whole_class" if args.whole_class else "selected"
        plan = build_feedback_assembly_plan(
            workspace_root,
            args.class_id,
            args.assignment_id,
            scope=scope,
            student_ids=tuple(args.student_id or ()),
            output=cast(AssemblyOutput, args.output),
            duplex_safe=bool(args.duplex_safe),
        )
    except (WorkspaceRootError, BatchFeedbackAssemblyError) as error:
        print(f"Error: could not plan feedback batch assembly: {error}", file=sys.stderr)
        return 1

    print_feedback_assembly_plan(plan)
    if args.dry_run:
        return 0
    try:
        result = execute_feedback_assembly(workspace_root, plan)
    except BatchFeedbackAssemblyError as error:
        print(f"Error: could not assemble feedback batch: {error}", file=sys.stderr)
        return 1
    print_feedback_assembly_result(result)
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
        print(
            f"Error: could not export class review summary: {error}",
            file=sys.stderr,
        )
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
        print(
            f"Error: could not export student performance summary: {error}",
            file=sys.stderr,
        )
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
        print(f"Error: could not export standards summary: {error}", file=sys.stderr)
        return 1

    print_exported_standards_summary(exported)
    return 0

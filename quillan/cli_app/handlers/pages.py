"""Direct, non-interactive submission page-management handlers."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import (
    print_managed_submission_page,
    print_submission_page_context,
)
from quillan.submission_page_management import (
    ManagedSubmissionPage,
    SubmissionPageManagementError,
    exclude_submission_page,
    load_submission_page_context,
    mark_submission_page_needs_rescan,
    restore_excluded_submission_page,
)


def handle_pages_list(args: argparse.Namespace) -> int:
    """List one canonical submission's page state without writing."""
    try:
        context = load_submission_page_context(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            args.student_id,
        )
    except (WorkspaceRootError, SubmissionPageManagementError, OSError) as error:
        print(f"Error: could not list submission pages: {error}", file=sys.stderr)
        return 1
    print_submission_page_context(context)
    return 0


def handle_pages_exclude(args: argparse.Namespace) -> int:
    """Exclude one page from active review through the shared service."""
    return _mutate(args, exclude_submission_page)


def handle_pages_restore(args: argparse.Namespace) -> int:
    """Restore one excluded page through the shared service."""
    return _mutate(args, restore_excluded_submission_page)


def handle_pages_mark_needs_rescan(args: argparse.Namespace) -> int:
    """Mark one page as needing rescan through the shared service."""
    return _mutate(args, mark_submission_page_needs_rescan)


PageMutation = Callable[[str | Path, str, str, str, int], ManagedSubmissionPage]


def _mutate(args: argparse.Namespace, service: PageMutation) -> int:
    try:
        workspace_root = resolve_workspace_root()
        result = service(
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
            args.page,
        )
    except (WorkspaceRootError, SubmissionPageManagementError, OSError) as error:
        print(f"Error: page change was not saved: {error}", file=sys.stderr)
        return 1
    print_managed_submission_page(result, workspace_root)
    return 0

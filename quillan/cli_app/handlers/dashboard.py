"""Direct assignment review dashboard command handler."""

from __future__ import annotations

import argparse
import json

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.review_dashboard import (
    ReviewDashboardError,
    assignment_review_dashboard_to_dict,
    build_assignment_review_dashboard,
    format_assignment_review_dashboard,
)


def handle_review_dashboard(args: argparse.Namespace) -> int:
    """Print one read-only assignment dashboard as text or JSON."""
    try:
        root = resolve_workspace_root()
        dashboard = build_assignment_review_dashboard(
            root, args.class_id, args.assignment_id
        )
        output = (
            json.dumps(
                assignment_review_dashboard_to_dict(dashboard),
                indent=2,
                ensure_ascii=False,
            )
            if args.format == "json"
            else format_assignment_review_dashboard(dashboard)
        )
    except (WorkspaceRootError, ReviewDashboardError, OSError, TypeError) as error:
        print(f"Error: could not build assignment review dashboard: {error}")
        return 1
    print(output)
    return 0

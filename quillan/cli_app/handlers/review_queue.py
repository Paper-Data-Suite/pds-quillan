"""Direct deterministic assignment review work queue command handler."""

from __future__ import annotations

import argparse
import json
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.review_work_queue import (
    ReviewWorkQueueError,
    assignment_review_work_queue_to_dict,
    build_assignment_review_work_queue,
    format_assignment_review_work_queue,
)


def handle_review_queue(args: argparse.Namespace) -> int:
    """Print one deterministic read-only assignment review work queue."""
    try:
        queue = build_assignment_review_work_queue(
            resolve_workspace_root(), args.class_id, args.assignment_id
        )
        output = (
            json.dumps(
                assignment_review_work_queue_to_dict(queue),
                indent=2,
                ensure_ascii=False,
            )
            if args.format == "json"
            else format_assignment_review_work_queue(queue)
        )
    except (WorkspaceRootError, ReviewWorkQueueError, OSError, TypeError) as error:
        print(
            f"Error: could not build review work queue: {error}",
            file=sys.stderr,
        )
        return 1
    print(output)
    return 0

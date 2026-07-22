"""Direct selected-student review status command handler."""

from __future__ import annotations

import argparse
import json
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.student_review_status import (
    StudentReviewStatusError,
    build_student_review_status,
    format_student_review_status,
    student_review_status_to_dict,
)


def handle_review_status(args: argparse.Namespace) -> int:
    """Print exactly one read-only selected-student status result."""
    try:
        status = build_student_review_status(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id
        )
        output = (
            json.dumps(student_review_status_to_dict(status), indent=2, ensure_ascii=False)
            if args.format == "json"
            else format_student_review_status(status)
        )
    except (WorkspaceRootError, StudentReviewStatusError, OSError, TypeError) as error:
        print(
            f"Error: could not build student review status: {error}",
            file=sys.stderr,
        )
        return 1
    print(output)
    return 0

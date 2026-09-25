"""Direct read-only resubmission inbox command handler."""

from __future__ import annotations

import argparse
import json
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.resubmission_inbox import (
    ResubmissionInboxError,
    assignment_resubmission_inbox_to_dict,
    build_assignment_resubmission_inbox,
    format_assignment_resubmission_inbox,
)


def handle_resubmission_inbox(args: argparse.Namespace) -> int:
    """Print one immutable inbox projection as teacher text or JSON."""
    try:
        root = resolve_workspace_root()
        inbox = build_assignment_resubmission_inbox(
            root, args.class_id, args.assignment_id
        )
        output = (
            json.dumps(
                assignment_resubmission_inbox_to_dict(inbox),
                indent=2,
                ensure_ascii=False,
            )
            if args.format == "json"
            else format_assignment_resubmission_inbox(inbox)
        )
    except (WorkspaceRootError, ResubmissionInboxError, OSError, TypeError) as error:
        print(f"Error: could not build resubmission inbox: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


__all__ = ["handle_resubmission_inbox"]

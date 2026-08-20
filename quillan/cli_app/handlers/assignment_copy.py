"""Direct CLI handler for safe Quillan assignment copying."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignment_copying import commit_assignment_copy, plan_assignment_copy
from quillan.assignment_workflows import format_assignment_summary


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(
            "Canonical assignment path is outside the exact workspace root."
        ) from error


def handle_assignment_copy(args: argparse.Namespace) -> int:
    """Plan, preview, and optionally commit a create-only assignment copy."""
    if not args.yes and not args.dry_run:
        print(
            "Error: assignment was not copied: use --yes to confirm or --dry-run.",
            file=sys.stderr,
        )
        return 1
    try:
        root = resolve_workspace_root()
        prompt = args.prompt
        if args.prompt_file is not None:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        plan = plan_assignment_copy(
            root,
            source_class_id=args.source_class_id,
            source_assignment_id=args.source_assignment_id,
            target_class_ids=args.target_class_id,
            target_assignment_id=args.assignment_id,
            title=args.title,
            student_prompt=prompt,
        )
        print("Assignment copy plan:")
        print(f"Source class: {plan.source_class_id}")
        print(f"Source assignment: {plan.source_assignment_id}")
        print(f"Target classes: {', '.join(plan.target_class_ids)}")
        print(f"Target assignment: {plan.target_assignment_id}")
        print(
            format_assignment_summary(
                plan.assignment, plan.destinations[0].path, root
            )
        )
        print("Destinations:")
        for destination in plan.destinations:
            print(f"- {destination.class_id}: {_relative(destination.path, root)}")
        print(
            "Excluded: submissions, evidence, reviews, exports, printable-page "
            "identities, routes, registrations, manifests, and publications."
        )
        if args.dry_run:
            print("No files were written.")
            return 0
        saved_paths = commit_assignment_copy(plan)
        print("Created copied assignment:")
        for class_id, path in zip(plan.target_class_ids, saved_paths, strict=True):
            print(f"- {class_id}: {_relative(path, root)}")
        return 0
    except (OSError, ValueError, WorkspaceRootError) as error:
        print(f"Error: assignment was not copied: {error}", file=sys.stderr)
        return 1

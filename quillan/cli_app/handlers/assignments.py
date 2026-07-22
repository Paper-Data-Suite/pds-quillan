"""Direct canonical assignment command handlers."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignment_setup import (
    create_assignment,
    load_canonical_assignment,
    plan_assignment_creation,
    validate_canonical_assignment,
)
from quillan.assignment_workflows import (
    format_assignment_summary,
    parse_comma_separated_values,
)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(
            "Canonical assignment path is outside the exact workspace root."
        ) from error


def _error(action: str, error: Exception) -> int:
    print(f"Error: assignment {action}: {error}", file=sys.stderr)
    return 1


def handle_assignment_create(args: argparse.Namespace) -> int:
    """Plan, validate, and optionally write a canonical assignment."""
    if args.overwrite and not args.yes:
        return _error("was not created", ValueError("--overwrite requires --yes."))
    if not args.yes and not args.dry_run:
        return _error(
            "was not created", ValueError("use --yes to confirm or --dry-run.")
        )
    try:
        prompt = args.prompt
        if args.prompt_file is not None:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        requirements = {
            key: value
            for key, value in {
                "paragraphs_min": args.paragraphs_min,
                "paragraphs_max": args.paragraphs_max,
                "word_count_min": args.word_count_min,
                "word_count_max": args.word_count_max,
            }.items()
            if value is not None
        }
        elements = parse_comma_separated_values(args.required_elements or "")
        if elements:
            requirements["required_elements"] = elements
        plan = plan_assignment_creation(
            resolve_workspace_root(),
            class_id=args.class_id,
            assignment_id=args.assignment_id,
            title=args.title,
            writing_type=args.writing_type,
            student_prompt=prompt,
            standards_profile_id=args.standards_profile_id,
            focus_standard_ids=parse_comma_separated_values(args.focus_standard_ids),
            review_unit={
                "type": args.review_unit_type,
                "singular_label": args.review_unit_singular,
                "plural_label": args.review_unit_plural,
            },
            basic_requirements=requirements,
            allow_return_without_full_review=args.allow_return_without_full_review,
        )
        relative_path = _relative(plan.path, plan.workspace_root)
        if args.dry_run:
            print("Assignment creation dry run:")
            print(f"Class: {plan.class_id}")
            print(f"Assignment: {plan.assignment_id}")
            print(f"Would write: {relative_path}")
            print(format_assignment_summary(plan.assignment, relative_path))
            print("No files were written.")
            return 0
        path = create_assignment(plan, overwrite=args.overwrite)
        print("Created assignment:")
        print(f"Class: {plan.class_id}")
        print(f"Assignment: {plan.assignment_id}")
        print(format_assignment_summary(plan.assignment, _relative(path, plan.workspace_root)))
        return 0
    except (OSError, ValueError, WorkspaceRootError) as error:
        return _error("was not created", error)


def handle_assignment_show(args: argparse.Namespace) -> int:
    """Load and show one structurally valid canonical assignment."""
    try:
        plan = load_canonical_assignment(
            resolve_workspace_root(), args.class_id, args.assignment_id
        )
        print("Assignment config is valid.")
        print(format_assignment_summary(plan.assignment, _relative(plan.path, plan.workspace_root)))
        return 0
    except (OSError, ValueError, WorkspaceRootError) as error:
        return _error("could not be shown", error)


def handle_assignment_validate(args: argparse.Namespace) -> int:
    """Validate one canonical assignment and its workspace standards."""
    try:
        plan = load_canonical_assignment(
            resolve_workspace_root(), args.class_id, args.assignment_id
        )
        validate_canonical_assignment(plan)
        print("Valid canonical assignment:")
        print(f"Class: {plan.class_id}")
        print(f"Assignment: {plan.assignment_id}")
        print(f"Standards profile: {plan.assignment['standards_profile_id']}")
        print(f"Focus Standards: {len(plan.assignment['focus_standard_ids'])}")
        print(f"Path: {_relative(plan.path, plan.workspace_root)}")
        return 0
    except (OSError, ValueError, WorkspaceRootError) as error:
        return _error("validation failed", error)

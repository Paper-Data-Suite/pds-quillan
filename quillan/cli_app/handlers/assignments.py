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
    plan_assignment_creation_from_preset,
    validate_canonical_assignment,
)
from quillan.assignment_workflows import (
    format_assignment_summary,
    parse_comma_separated_values,
)

from quillan.review_configuration_presets import (
    require_current_review_configuration_preset_matches,
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

        manual_values = {
            "--writing-type": args.writing_type,
            "--standards-profile-id": args.standards_profile_id,
            "--focus-standard-ids": args.focus_standard_ids,
            "--review-unit-type": args.review_unit_type,
            "--review-unit-singular": args.review_unit_singular,
            "--review-unit-plural": args.review_unit_plural,
            "--rating-scale": args.rating_scale,
            "--paragraphs-min": args.paragraphs_min,
            "--paragraphs-max": args.paragraphs_max,
            "--word-count-min": args.word_count_min,
            "--word-count-max": args.word_count_max,
            "--required-elements": args.required_elements,
            "--allow-return-without-full-review": (
                args.allow_return_without_full_review
            ),
        }
        preset = None
        if args.preset_id is not None:
            conflicts = [
                name for name, value in manual_values.items() if value is not None
            ]
            if conflicts:
                raise ValueError(
                    "--preset-id cannot be combined with manual "
                    "review-configuration options: "
                    + ", ".join(conflicts)
                    + "."
                )
            plan, preset = plan_assignment_creation_from_preset(
                resolve_workspace_root(),
                class_id=args.class_id,
                assignment_id=args.assignment_id,
                title=args.title,
                student_prompt=prompt,
                preset_id=args.preset_id,
            )
        else:
            required = {
                "--writing-type": args.writing_type,
                "--standards-profile-id": args.standards_profile_id,
                "--focus-standard-ids": args.focus_standard_ids,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise ValueError(
                    "manual assignment creation requires "
                    + ", ".join(missing)
                    + ", or use --preset-id."
                )
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
                focus_standard_ids=parse_comma_separated_values(
                    args.focus_standard_ids
                ),
                review_unit={
                    "type": args.review_unit_type or "paragraph",
                    "singular_label": (
                        args.review_unit_singular or "paragraph"
                    ),
                    "plural_label": args.review_unit_plural or "paragraphs",
                },
                basic_requirements=requirements,
                allow_return_without_full_review=(
                    True
                    if args.allow_return_without_full_review is None
                    else args.allow_return_without_full_review
                ),
            )

        relative_path = _relative(plan.path, plan.workspace_root)
        if args.dry_run:
            print("Assignment creation dry run:")
            print(f"Class: {plan.class_id}")
            print(f"Assignment: {plan.assignment_id}")
            if preset is not None:
                print(
                    "Review preset: "
                    f"{preset['title']} ({preset['preset_id']})"
                )
            print(f"Would write: {relative_path}")
            print(format_assignment_summary(plan.assignment, relative_path))
            print("No files were written.")
            return 0
        if preset is not None:
            require_current_review_configuration_preset_matches(
                plan.workspace_root, preset
            )
        path = create_assignment(plan, overwrite=args.overwrite)
        print("Created assignment:")
        print(f"Class: {plan.class_id}")
        print(f"Assignment: {plan.assignment_id}")
        if preset is not None:
            print(
                "Review preset applied by value: "
                f"{preset['title']} ({preset['preset_id']})"
            )
        print(
            format_assignment_summary(
                plan.assignment, _relative(path, plan.workspace_root)
            )
        )
        from quillan.academic_work_menu import (
            print_registration_title_staleness_notices,
        )

        print_registration_title_staleness_notices(
            plan.workspace_root,
            [plan.class_id],
            plan.assignment_id,
            plan.assignment["title"],
        )
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

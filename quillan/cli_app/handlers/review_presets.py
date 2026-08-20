"""Direct CLI handlers for reusable review-configuration presets."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignment_workflows import (
    default_rating_scale,
    default_review_unit,
    parse_comma_separated_values,
)
from quillan.review_configuration_presets import (
    ReviewConfigurationPresetError,
    commit_review_configuration_preset,
    inspect_review_configuration_presets,
    load_current_review_configuration_preset,
    load_review_configuration_preset,
    plan_review_configuration_preset_creation,
    plan_review_configuration_preset_from_assignment,
    review_configuration_preset_path,
)


def _error(action: str, error: Exception) -> int:
    print(f"Error: review preset {action}: {error}", file=sys.stderr)
    return 1


def _require_confirmation(args: argparse.Namespace) -> int | None:
    if args.yes or args.dry_run:
        return None
    return _error(
        "was not created",
        ValueError("use --yes to confirm or --dry-run."),
    )


def _requirements(args: argparse.Namespace) -> dict[str, Any]:
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
    return requirements


def _review_unit(args: argparse.Namespace) -> dict[str, Any]:
    default = default_review_unit()
    return {
        "type": args.review_unit_type or default["type"],
        "singular_label": args.review_unit_singular or default["singular_label"],
        "plural_label": args.review_unit_plural or default["plural_label"],
    }


def _format_preset(preset: dict[str, Any], *, path: Path | None = None) -> str:
    requirements = (
        ", ".join(
            f"{key}={value!r}"
            for key, value in preset["basic_requirements"].items()
        )
        if preset["basic_requirements"]
        else "none"
    )
    lines = [
        f"Preset: {preset['title']} ({preset['preset_id']})",
        f"Writing type: {preset['writing_type']}",
        f"Standards profile: {preset['standards_profile_id']}",
        "Focus Standards: " + ", ".join(preset["focus_standard_ids"]),
        (
            "Review unit: "
            f"{preset['review_unit']['type']} "
            f"({preset['review_unit']['singular_label']} / "
            f"{preset['review_unit']['plural_label']})"
        ),
        f"Rating scale: {preset['rating_scale']['scale_id']}",
        f"Basic requirements: {requirements}",
        (
            "Allow return without full review: "
            f"{preset['minimum_requirement_policy']['allow_return_without_full_review']}"
        ),
    ]
    if path is not None:
        lines.append(f"Path: {path.as_posix()}")
    return "\n".join(lines)


def handle_review_preset_list(args: argparse.Namespace) -> int:
    """List valid, invalid, and stale preset files independently."""
    del args
    try:
        root = resolve_workspace_root()
        items = inspect_review_configuration_presets(root)
        if not items:
            print("No review-configuration presets found.")
            return 0
        print("Review-configuration presets:")
        for item in items:
            if item.preset is None:
                print(f"- {item.path.stem}: invalid")
                if item.structural_error:
                    print(f"  {item.structural_error}")
                continue
            print(
                f"- {item.preset['title']} ({item.preset['preset_id']}): "
                f"{item.status}"
            )
            if item.standards_error:
                print(f"  {item.standards_error}")
        return 0
    except (OSError, ValueError, WorkspaceRootError) as error:
        return _error("could not be listed", error)


def handle_review_preset_show(args: argparse.Namespace) -> int:
    """Show one exact structurally valid preset, including stale status."""
    try:
        root = resolve_workspace_root()
        path = review_configuration_preset_path(root, args.preset_id)
        preset = load_review_configuration_preset(path)
        inspection = next(
            (
                item
                for item in inspect_review_configuration_presets(root)
                if item.path == path
            ),
            None,
        )
        if inspection is None:
            raise ReviewConfigurationPresetError(
                f"Review-configuration preset was not discoverable: {path}"
            )
        print("Review-configuration preset:")
        print(_format_preset(preset, path=path.relative_to(root)))
        print(f"Status: {inspection.status}")
        if inspection.standards_error:
            print(f"Standards validation: {inspection.standards_error}")
        return 0
    except (OSError, ValueError, WorkspaceRootError) as error:
        return _error("could not be shown", error)


def handle_review_preset_validate(args: argparse.Namespace) -> int:
    """Validate one exact preset against current Core standards."""
    try:
        root = resolve_workspace_root()
        preset, path = load_current_review_configuration_preset(
            root, args.preset_id
        )
        print("Valid review-configuration preset:")
        print(f"Preset: {preset['title']} ({preset['preset_id']})")
        print(f"Standards profile: {preset['standards_profile_id']}")
        print(f"Focus Standards: {len(preset['focus_standard_ids'])}")
        print(f"Path: {path.relative_to(root).as_posix()}")
        return 0
    except (OSError, ValueError, WorkspaceRootError) as error:
        return _error("validation failed", error)


def handle_review_preset_create(args: argparse.Namespace) -> int:
    """Plan and optionally persist a directly configured preset."""
    confirmation_error = _require_confirmation(args)
    if confirmation_error is not None:
        return confirmation_error
    try:
        root = resolve_workspace_root()
        plan = plan_review_configuration_preset_creation(
            root,
            preset_id=args.preset_id,
            title=args.title,
            description=args.description,
            writing_type=args.writing_type,
            standards_profile_id=args.standards_profile_id,
            focus_standard_ids=parse_comma_separated_values(
                args.focus_standard_ids
            ),
            review_unit=_review_unit(args),
            rating_scale=default_rating_scale(),
            basic_requirements=_requirements(args),
            minimum_requirement_policy={
                "allow_return_without_full_review": (
                    True
                    if args.allow_return_without_full_review is None
                    else args.allow_return_without_full_review
                )
            },
        )
        relative = plan.path.relative_to(root)
        print("Review-configuration preset plan:")
        print(_format_preset(plan.preset, path=relative))
        if args.dry_run:
            print("No files were written.")
            return 0
        path = commit_review_configuration_preset(plan)
        print(
            "Created review-configuration preset: "
            f"{path.relative_to(root).as_posix()}"
        )
        return 0
    except (OSError, ValueError, WorkspaceRootError) as error:
        return _error("was not created", error)


def handle_review_preset_save_from_assignment(
    args: argparse.Namespace,
) -> int:
    """Plan and optionally save reusable configuration from one assignment."""
    confirmation_error = _require_confirmation(args)
    if confirmation_error is not None:
        return confirmation_error
    try:
        root = resolve_workspace_root()
        plan = plan_review_configuration_preset_from_assignment(
            root,
            source_class_id=args.source_class_id,
            source_assignment_id=args.source_assignment_id,
            preset_id=args.preset_id,
            title=args.title,
            description=args.description,
        )
        relative = plan.path.relative_to(root)
        print("Review-configuration preset plan:")
        print(f"Source: {args.source_class_id}/{args.source_assignment_id}")
        print(_format_preset(plan.preset, path=relative))
        if args.dry_run:
            print("No files were written.")
            return 0
        path = commit_review_configuration_preset(plan)
        print(
            "Created review-configuration preset: "
            f"{path.relative_to(root).as_posix()}"
        )
        return 0
    except (OSError, ValueError, WorkspaceRootError) as error:
        return _error("was not created", error)

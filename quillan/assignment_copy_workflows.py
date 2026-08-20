"""Teacher-facing workflow for safe Quillan assignment copying."""

from __future__ import annotations

from pathlib import Path

from quillan.assignment_copying import (
    AssignmentCopyError,
    commit_assignment_copy,
    plan_assignment_copy,
)
from quillan.assignment_picker import prompt_assignment_choice
from quillan.assignment_setup import load_canonical_assignment
from quillan.assignment_workflows import (
    _prompt_assignment_class_folders,
    format_assignment_summary,
)
from quillan.menu_navigation import (
    NavigationChoice,
    parse_navigation_choice,
    print_navigation_options,
)


def _reuse_or_text(prompt: str, default: str) -> str | None:
    """Return entered text, the default on blank, or None on Back."""
    print_navigation_options()
    print()
    value = input(prompt).strip()
    navigation = parse_navigation_choice(value)
    if navigation is NavigationChoice.BACK:
        return None
    return default if not value else value


def prompt_copy_assignment() -> int:
    """Resolve the workspace and launch the safe teacher copy workflow."""
    from quillan.assignment_workflows import _workspace_root

    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    return _prompt_copy_assignment(workspace_root)


def _prompt_copy_assignment(workspace_root: Path) -> int:
    """Select, preview, and create a fresh assignment from reusable config."""
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Copy Writing Assignment")
    print(
        "Copy reusable assignment configuration into a fresh assignment identity."
    )
    print("Student work, evidence, review history, routes, and exports are not copied.")
    print()

    source_choice = prompt_assignment_choice(workspace_root)
    if source_choice is None:
        return 0
    try:
        source = load_canonical_assignment(
            workspace_root,
            source_choice.class_id,
            source_choice.assignment_id,
        )
    except (OSError, ValueError) as error:
        print(f"Error: could not load source assignment: {error}")
        return 1

    clear_screen()
    print_menu_header("Source Assignment")
    print(f"Source class: {source_choice.class_id}")
    print(f"Source assignment: {source_choice.assignment_id}")
    print()
    print(format_assignment_summary(source.assignment, source.path, workspace_root))
    print()

    clear_screen()
    print_menu_header("Select Copy Target Classes")
    target_folders = _prompt_assignment_class_folders(workspace_root)
    if target_folders is None:
        return 0
    target_class_ids = tuple(folder.class_id for folder in target_folders)

    clear_screen()
    print_menu_header("Copied Assignment Identity")
    print(f"Source: {source_choice.class_id}/{source_choice.assignment_id}")
    print(f"Target classes: {', '.join(target_class_ids)}")
    print()
    print_navigation_options()
    print()
    raw_id = input(
        f"Target assignment ID [{source_choice.assignment_id}]: "
    ).strip()
    navigation = parse_navigation_choice(raw_id)
    if navigation is NavigationChoice.BACK:
        return 0
    target_assignment_id = raw_id or source_choice.assignment_id

    source_title = str(source.assignment["title"])
    target_title = _reuse_or_text(
        "Target title [press Enter to reuse source title]: ",
        source_title,
    )
    if target_title is None:
        return 0
    source_prompt = str(source.assignment["student_prompt"])
    target_prompt = _reuse_or_text(
        "Student-facing prompt [press Enter to reuse source prompt]: ",
        source_prompt,
    )
    if target_prompt is None:
        return 0

    try:
        plan = plan_assignment_copy(
            workspace_root,
            source_class_id=source_choice.class_id,
            source_assignment_id=source_choice.assignment_id,
            target_class_ids=target_class_ids,
            target_assignment_id=target_assignment_id,
            title=target_title,
            student_prompt=target_prompt,
        )
    except AssignmentCopyError as error:
        print(f"Error: {error}")
        return 1

    clear_screen()
    print_menu_header("Review Copied Assignment Before Saving")
    print(f"Source: {plan.source_class_id}/{plan.source_assignment_id}")
    print(f"Target classes: {', '.join(plan.target_class_ids)}")
    print(f"Target assignment: {plan.target_assignment_id}")
    print()
    print(
        format_assignment_summary(
            plan.assignment, plan.destinations[0].path, workspace_root
        )
    )
    print()
    print("Destinations:")
    for destination in plan.destinations:
        relative = destination.path.relative_to(workspace_root).as_posix()
        print(f"- {destination.class_id}: {relative}")
    print()
    print(
        "Only assignment configuration will be copied. Submissions, evidence, "
        "reviews, exports, printable-page identities, routes, registrations, "
        "manifests, and publications are not copied."
    )
    print()
    print_navigation_options()
    print()
    confirmation = input("Save this copied assignment? [Y/n]: ").strip()
    navigation = parse_navigation_choice(confirmation)
    if navigation is NavigationChoice.BACK:
        print("Canceled: copied assignment was not saved.")
        return 0
    if confirmation.casefold() not in {"", "y", "yes"}:
        print("Canceled: copied assignment was not saved.")
        return 0

    try:
        saved_paths = commit_assignment_copy(plan)
    except (OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    clear_screen()
    print_menu_header("Assignment Copy Saved")
    if len(saved_paths) == 1:
        print(
            "Saved copied assignment: "
            f"{saved_paths[0].relative_to(workspace_root).as_posix()}"
        )
    else:
        print(f"Saved copied assignment for {len(saved_paths)} classes:")
        for class_id, path in zip(plan.target_class_ids, saved_paths, strict=True):
            print(f"- {class_id}: {path.relative_to(workspace_root).as_posix()}")
    print()
    print(
        "No student work, evidence, review, route, export, or publication state "
        "was copied."
    )
    return 0

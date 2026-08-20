"""Teacher-facing workflows for reusable review-configuration presets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignment_picker import prompt_assignment_choice
from quillan.menu_navigation import (
    NavigationChoice,
    navigation_hint,
    parse_navigation_choice,
    print_navigation_options,
)
from quillan.review_configuration_presets import (
    ReviewConfigurationPresetInspection,
    commit_review_configuration_preset,
    inspect_review_configuration_presets,
    load_current_review_configuration_preset,
    plan_review_configuration_preset_creation,
    plan_review_configuration_preset_from_assignment,
)


def format_review_configuration_preset_summary(
    preset: dict[str, Any],
    *,
    path: Path | None = None,
) -> str:
    """Return a complete teacher-facing summary of one preset."""
    review_unit = preset["review_unit"]
    rating_scale = preset["rating_scale"]
    requirements = preset["basic_requirements"]
    lines = [
        f"Preset ID: {preset['preset_id']}",
        f"Title: {preset['title']}",
        f"Description: {preset['description']}",
        f"Writing type: {preset['writing_type']}",
        f"Standards profile ID: {preset['standards_profile_id']}",
        (
            f"Focus standard IDs ({len(preset['focus_standard_ids'])}): "
            + ", ".join(preset["focus_standard_ids"])
        ),
        (
            "Review unit: "
            f"{review_unit['type']} "
            f"({review_unit['singular_label']}/{review_unit['plural_label']})"
        ),
        (
            f"Rating scale: {rating_scale['scale_id']} "
            f"({len(rating_scale['levels'])} levels)"
        ),
    ]
    for level in rating_scale["levels"]:
        lines.append(
            f"  {level['value']}: {level['label']} - {level['description']}"
        )
    lines.append(f"Basic requirements: {requirements}")
    lines.append(
        "Minimum requirement policy: "
        f"{preset['minimum_requirement_policy']}"
    )
    if path is not None:
        lines.append(f"Preset path: {path.as_posix()}")
    return "\n".join(lines)


def current_valid_review_configuration_presets(
    workspace_root: Path,
) -> tuple[ReviewConfigurationPresetInspection, ...]:
    """Return current valid presets in deterministic discovery order."""
    return tuple(
        item
        for item in inspect_review_configuration_presets(workspace_root)
        if item.status == "valid" and item.preset is not None
    )


def prompt_assignment_review_configuration(
    workspace_root: Path,
) -> dict[str, Any] | Literal[False] | None:
    """Choose a saved preset or manual configuration.

    Returns a preset dictionary for saved-preset mode, ``False`` for manual
    configuration, and ``None`` when the teacher backs out of preset selection.
    When no current valid presets exist, returns ``False`` without adding a
    redundant prompt to the established manual assignment-creation journey.
    """
    valid = current_valid_review_configuration_presets(workspace_root)
    if not valid:
        return False

    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Review Configuration")
    print("1. Use a saved review preset")
    print("2. Configure review settings manually")
    print_navigation_options()
    print()
    selection = input("Select review configuration: ").strip()
    navigation = parse_navigation_choice(selection)
    if navigation is NavigationChoice.BACK:
        return None
    if selection == "2":
        return False
    if selection != "1":
        print(f"Invalid selection. {navigation_hint()}")
        return None
    return prompt_select_review_configuration_preset(workspace_root)


def prompt_select_review_configuration_preset(
    workspace_root: Path,
) -> dict[str, Any] | None:
    """Select and explicitly accept one exact current valid preset."""
    inspections = inspect_review_configuration_presets(workspace_root)
    valid = tuple(
        item
        for item in inspections
        if item.status == "valid" and item.preset is not None
    )
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Select Review Configuration Preset")
    if not valid:
        print("No current valid review-configuration presets are available.")
        _print_unavailable_presets(inspections)
        return None

    print("Available presets:")
    for index, item in enumerate(valid, start=1):
        assert item.preset is not None
        print(
            f"{index}. {item.preset['title']} "
            f"({item.preset['preset_id']})"
        )
    _print_unavailable_presets(inspections)
    print()
    print_navigation_options()
    print()
    selection = input("Select review preset: ").strip()
    navigation = parse_navigation_choice(selection)
    if navigation is NavigationChoice.BACK:
        return None

    selected: ReviewConfigurationPresetInspection | None = None
    if selection.isdigit() and 1 <= int(selection) <= len(valid):
        selected = valid[int(selection) - 1]
    else:
        for item in valid:
            assert item.preset is not None
            if item.preset["preset_id"] == selection:
                selected = item
                break
    if selected is None or selected.preset is None:
        print(f"Error: review preset not found: {selection}")
        return None

    preset_id = selected.preset["preset_id"]
    preset, path = load_current_review_configuration_preset(
        workspace_root, preset_id
    )
    clear_screen()
    print_menu_header("Review Saved Review Configuration")
    print(format_review_configuration_preset_summary(
        preset,
        path=path.relative_to(workspace_root),
    ))
    print()
    print(
        "Applying this preset copies these values into the new assignment. "
        "The assignment will not depend on the preset afterward."
    )
    print()
    print("1. Use this preset")
    print_navigation_options()
    print()
    confirmation = input("Select an option: ").strip()
    navigation = parse_navigation_choice(confirmation)
    if navigation is NavigationChoice.BACK:
        return None
    if confirmation != "1":
        print(f"Invalid selection. {navigation_hint()}")
        return None
    return preset


def prompt_create_review_configuration_preset() -> int:
    """Create one preset from explicit teacher-entered configuration."""
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1

    from quillan import assignment_workflows as assignments
    from quillan.menu import clear_screen, print_menu_header

    try:
        clear_screen()
        print_menu_header("Create Review Configuration Preset")
        preset_id = assignments._required_input("Preset ID: ", "preset ID")
        title = assignments._required_input("Preset title: ", "preset title")
        description = assignments._required_input(
            "Preset description: ", "preset description"
        )

        assignments._print_assignment_section_header("Preset Writing Type")
        writing_type = assignments._prompt_writing_type()

        assignments._print_assignment_section_header("Preset Standards")
        standards_selection = assignments._prompt_standards_selection(
            workspace_root
        )
        if standards_selection is None:
            return 1
        standards_profile_id, focus_standard_ids = standards_selection

        assignments._print_assignment_section_header("Preset Review Unit")
        review_unit = assignments._prompt_review_unit()
        assignments._print_assignment_section_header("Preset Rating Scale")
        rating_scale = assignments._prompt_rating_scale()
        assignments._print_assignment_section_header("Preset Basic Requirements")
        basic_requirements = assignments._prompt_basic_requirements()
        assignments._print_assignment_section_header(
            "Preset Minimum Requirement Policy"
        )
        minimum_requirement_policy = (
            assignments._prompt_minimum_requirement_policy()
        )

        plan = plan_review_configuration_preset_creation(
            workspace_root,
            preset_id=preset_id,
            title=title,
            description=description,
            writing_type=writing_type,
            standards_profile_id=standards_profile_id,
            focus_standard_ids=focus_standard_ids,
            review_unit=review_unit,
            rating_scale=rating_scale,
            basic_requirements=basic_requirements,
            minimum_requirement_policy=minimum_requirement_policy,
        )
    except (OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    clear_screen()
    print_menu_header("Review Preset Before Saving")
    print(
        format_review_configuration_preset_summary(
            plan.preset,
            path=plan.path.relative_to(workspace_root),
        )
    )
    print()
    if not _confirm_save("Save this review preset?"):
        print("Canceled: review preset was not saved.")
        return 0
    try:
        path = commit_review_configuration_preset(plan)
    except (OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1
    clear_screen()
    print_menu_header("Review Preset Saved")
    print(
        "Saved review preset: "
        f"{path.relative_to(workspace_root).as_posix()}"
    )
    return 0


def prompt_save_review_configuration_preset_from_assignment() -> int:
    """Save reusable configuration from one exact canonical assignment."""
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1

    from quillan import assignment_workflows as assignments
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Save Review Preset from Assignment")
    choice = prompt_assignment_choice(workspace_root)
    if choice is None:
        return 0
    try:
        preset_id = assignments._required_input("Preset ID: ", "preset ID")
        title = assignments._required_input("Preset title: ", "preset title")
        description = assignments._required_input(
            "Preset description: ", "preset description"
        )
        plan = plan_review_configuration_preset_from_assignment(
            workspace_root,
            source_class_id=choice.class_id,
            source_assignment_id=choice.assignment_id,
            preset_id=preset_id,
            title=title,
            description=description,
        )
    except (OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    clear_screen()
    print_menu_header("Review Preset Before Saving")
    print(f"Source assignment: {choice.class_id}/{choice.assignment_id}")
    print()
    print(
        format_review_configuration_preset_summary(
            plan.preset,
            path=plan.path.relative_to(workspace_root),
        )
    )
    print()
    if not _confirm_save("Save this review preset?"):
        print("Canceled: review preset was not saved.")
        return 0
    try:
        path = commit_review_configuration_preset(plan)
    except (OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1
    clear_screen()
    print_menu_header("Review Preset Saved")
    print(
        "Saved review preset: "
        f"{path.relative_to(workspace_root).as_posix()}"
    )
    return 0


def prompt_view_validate_review_configuration_preset() -> int:
    """List all preset files and inspect one exact selection."""
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    inspections = inspect_review_configuration_presets(workspace_root)

    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Review Configuration Presets")
    if not inspections:
        print("No review-configuration presets found.")
        return 0
    for index, item in enumerate(inspections, start=1):
        if item.preset is None:
            print(f"{index}. {item.path.stem} [invalid]")
        else:
            print(
                f"{index}. {item.preset['title']} "
                f"({item.preset['preset_id']}) [{item.status}]"
            )
    print()
    print_navigation_options()
    print()
    selection = input("Select preset to inspect: ").strip()
    navigation = parse_navigation_choice(selection)
    if navigation is NavigationChoice.BACK:
        return 0
    if not selection.isdigit() or not 1 <= int(selection) <= len(inspections):
        print(f"Invalid selection. {navigation_hint()}")
        return 1
    item = inspections[int(selection) - 1]

    clear_screen()
    print_menu_header("Review Preset Validation")
    if item.preset is None:
        print(f"Preset file: {item.path.name}")
        print("Status: invalid")
        print(f"Error: {item.structural_error}")
        return 0
    print(
        format_review_configuration_preset_summary(
            item.preset,
            path=item.path.relative_to(workspace_root),
        )
    )
    print()
    print(f"Status: {item.status}")
    if item.standards_error:
        print(f"Standards validation: {item.standards_error}")
    return 0


def launch_review_configuration_preset_menu() -> int:
    """Launch the teacher-facing preset-management submenu."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Review Configuration Presets")
            print("1. Create review preset")
            print("2. Save review preset from assignment")
            print("3. View/validate review presets")
            print_navigation_options()
            print()
            choice = input("Select an option: ").strip()
            navigation = parse_navigation_choice(choice)
            if navigation is NavigationChoice.BACK:
                return 0
            workflow = {
                "1": prompt_create_review_configuration_preset,
                "2": prompt_save_review_configuration_preset_from_assignment,
                "3": prompt_view_validate_review_configuration_preset,
            }.get(choice)
            if workflow is None:
                print(f"Invalid selection. {navigation_hint()}")
            else:
                workflow()
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting review-preset menu.")
        return 0


def _print_unavailable_presets(
    inspections: tuple[ReviewConfigurationPresetInspection, ...],
) -> None:
    unavailable = tuple(item for item in inspections if item.status != "valid")
    if not unavailable:
        return
    print()
    print("Unavailable preset files:")
    for item in unavailable:
        if item.preset is None:
            print(f"- {item.path.stem}: invalid")
            if item.structural_error:
                print(f"  {item.structural_error}")
        else:
            print(
                f"- {item.preset['title']} ({item.preset['preset_id']}): "
                f"{item.status}"
            )
            if item.standards_error:
                print(f"  {item.standards_error}")


def _confirm_save(label: str) -> bool:
    print("1. Save")
    print_navigation_options()
    print()
    selection = input(f"{label} ").strip()
    navigation = parse_navigation_choice(selection)
    if navigation is NavigationChoice.BACK:
        return False
    if selection == "1":
        return True
    print(f"Invalid selection. {navigation_hint()}")
    return False


def _workspace_root() -> Path | None:
    try:
        return resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return None

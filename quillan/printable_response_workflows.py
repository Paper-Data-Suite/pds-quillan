"""Teacher-facing workflows for printable Quillan response packets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pds_core.classes import ClassFolder, list_class_folders
from pds_core.rosters import RosterError
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignment_discovery import discover_quillan_assignments
from quillan.assignments import AssignmentConfigError
from quillan.generated_output_opening import (
    GeneratedOutputOpeningError,
    open_generated_output_file,
    open_generated_output_folder,
)
from quillan.printable_response import PRINTABLE_RESPONSE_FILENAME
from quillan.storage import assignment_templates_dir


@dataclass(frozen=True)
class AssignmentChoice:
    """One discovered canonical assignment config and its validation state."""

    assignment_id: str
    path: Path
    title: str | None
    class_ids: tuple[str, ...]
    error: str | None = None


def parse_pages_per_student(value: str) -> int:
    """Parse a positive page count, defaulting blank input to one."""
    stripped = value.strip()
    if not stripped:
        return 1
    if not stripped.isdigit():
        raise ValueError("Pages per student must be a positive integer.")
    pages = int(stripped)
    if pages < 1:
        raise ValueError("Pages per student must be a positive integer.")
    return pages


def discover_assignment_configs(
    workspace_root: str | Path,
    class_id: str,
) -> tuple[AssignmentChoice, ...]:
    """Discover canonical assignment configs for one class folder."""
    choices: list[AssignmentChoice] = []
    for discovered in discover_quillan_assignments(workspace_root, class_id):
        if discovered.assignment is None:
            choices.append(
                AssignmentChoice(
                    assignment_id=discovered.assignment_id,
                    path=discovered.path,
                    title=None,
                    class_ids=(),
                    error=discovered.error,
                )
            )
            continue
        assignment = discovered.assignment
        choices.append(
            AssignmentChoice(
                assignment_id=discovered.assignment_id,
                path=discovered.path,
                title=cast(str, assignment["title"]),
                class_ids=tuple(cast(list[str], assignment["class_ids"])),
            )
        )
    return tuple(choices)


def expected_printable_packet_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the stable output path for a combined printable class packet."""
    return (
        assignment_templates_dir(workspace_root, class_id, assignment_id)
        / PRINTABLE_RESPONSE_FILENAME
    )


def _workspace_root() -> Path | None:
    try:
        return resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return None


def _prompt_open_generated_packet(
    workspace_root: Path,
    generated_path: Path,
) -> None:
    from quillan.menu_navigation import (
        NavigationChoice,
        parse_navigation_choice,
    )

    print()
    print("What would you like to do next?")
    print("1. Open generated packet")
    print("2. Open containing folder")
    print("3. Return to Printable Response Pages")
    selection = input("Select an option: ").strip()
    navigation = parse_navigation_choice(selection)
    if (
        selection == ""
        or selection == "3"
        or navigation is NavigationChoice.BACK
    ):
        return

    if selection == "1":
        try:
            opened = open_generated_output_file(workspace_root, generated_path)
        except GeneratedOutputOpeningError as error:
            print(f"Error: could not open generated packet: {error}")
            print("Generated packet remains saved at:")
            print(generated_path)
            return
        print("Opened generated packet:")
        print(opened.path)
        return

    if selection == "2":
        try:
            opened = open_generated_output_folder(workspace_root, generated_path)
        except GeneratedOutputOpeningError as error:
            print(f"Error: could not open containing folder: {error}")
            print("Generated packet remains saved at:")
            print(generated_path)
            return
        print("Opened containing folder:")
        print(opened.path)
        return

    print("Returning to Printable Response Pages.")


def _prompt_class_selection(workspace_root: Path) -> ClassFolder | None:
    from quillan.menu_navigation import (
        NavigationChoice,
        parse_navigation_choice,
        print_navigation_options,
    )

    folders = list_class_folders(workspace_root, require_roster=True)
    if not folders:
        print("No class rosters found. Create a class roster first.")
        return None

    print("Available classes:")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.class_id}")
    print_navigation_options()
    print()
    selection = input("Select class roster: ").strip()
    navigation = parse_navigation_choice(selection)
    if selection == "" or navigation is NavigationChoice.BACK:
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(folders):
        return folders[int(selection) - 1]
    for folder in folders:
        if folder.class_id == selection:
            return folder
    print(f"Error: Class not found: {selection}")
    return None


def _format_assignment_choice(choice: AssignmentChoice) -> str:
    if choice.error is not None:
        return f"{choice.assignment_id} [INVALID: {choice.error}]"
    if choice.title:
        return f"{choice.assignment_id} - {choice.title}"
    return choice.assignment_id


def _prompt_assignment_selection(
    workspace_root: Path,
    class_id: str,
) -> AssignmentChoice | None:
    from quillan.menu_navigation import (
        NavigationChoice,
        parse_navigation_choice,
        print_navigation_options,
    )

    choices = discover_assignment_configs(workspace_root, class_id)
    if not choices:
        print("No assignment configs found for this class. Create an assignment first.")
        return None

    print("Available assignments:")
    for index, choice in enumerate(choices, start=1):
        print(f"{index}. {_format_assignment_choice(choice)}")
    print_navigation_options()
    print()
    selection = input("Select assignment: ").strip()
    navigation = parse_navigation_choice(selection)
    if selection == "" or navigation is NavigationChoice.BACK:
        return None
    selected: AssignmentChoice | None = None
    if selection.isdigit() and 1 <= int(selection) <= len(choices):
        selected = choices[int(selection) - 1]
    else:
        for choice in choices:
            if choice.assignment_id == selection:
                selected = choice
                break
    if selected is None:
        print(f"Error: Assignment not found: {selection}")
        return None
    if selected.error is not None:
        print(f"Error: Assignment config is invalid: {selected.error}")
        return None
    if class_id not in selected.class_ids:
        print(
            f"Error: Assignment '{selected.assignment_id}' does not include "
            f"class '{class_id}' in class_ids."
        )
        return None
    return selected


def prompt_generate_class_packet() -> int:
    """Prompt for roster and assignment selection, then generate one class PDF."""
    from quillan.cli_app.output import print_generated_printable_response_packet
    from quillan.menu import print_menu_header
    from quillan.printable_response_packet import (
        generate_printable_response_packet,
        plan_printable_response_packet,
    )

    print_menu_header("Generate Printable Response Class Packet")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    class_folder = _prompt_class_selection(workspace_root)
    if class_folder is None:
        return 1
    assignment = _prompt_assignment_selection(workspace_root, class_folder.class_id)
    if assignment is None:
        return 1

    try:
        pages_per_student = parse_pages_per_student(
            input("Pages per student [1]: ")
        )
    except ValueError as error:
        print(f"Error: {error}")
        return 1

    try:
        plan = plan_printable_response_packet(
            workspace_root,
            class_folder.class_id,
            assignment.assignment_id,
            pages_per_student=pages_per_student,
        )
    except (AssignmentConfigError, RosterError, OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    overwrite = False
    if plan.target_exists:
        print(f"Printable response packet already exists:\n{plan.output_path}")
        confirmation = input(
            "Type OVERWRITE to replace the existing printable response packet: "
        ).strip()
        if confirmation != "OVERWRITE":
            print("Canceled: existing printable response packet was not changed.")
            return 1
        overwrite = True

    print("Output mode: one class packet PDF")
    try:
        generated = generate_printable_response_packet(
            plan,
            overwrite=overwrite,
        )
    except (AssignmentConfigError, RosterError, OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    print_generated_printable_response_packet(generated)
    print(f"Saved at: {generated.output_path}")
    _prompt_open_generated_packet(workspace_root, generated.output_path)
    return 0


def launch_printable_response_menu() -> int:
    """Launch the teacher-facing printable response pages submenu."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header
    from quillan.menu_navigation import (
        NavigationChoice,
        navigation_hint,
        parse_navigation_choice,
        print_navigation_options,
    )

    try:
        while True:
            clear_screen()
            print_menu_header("Printable Response Pages")
            print("1. Generate class packet")
            print_navigation_options()
            print()
            choice = input("Select an option: ").strip()
            navigation = parse_navigation_choice(choice)
            print()

            if choice == "2" or navigation is NavigationChoice.BACK:
                return 0
            if choice == "1":
                clear_screen()
                prompt_generate_class_packet()
            else:
                print(f"Invalid selection. {navigation_hint()}")
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting printable response menu.")
        return 0

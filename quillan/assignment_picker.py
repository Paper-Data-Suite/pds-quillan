"""Shared teacher-facing class and assignment selection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pds_core.classes import list_class_folders

from quillan.assignment_discovery import discover_quillan_assignments
from quillan.menu_navigation import (
    NavigationChoice,
    navigation_hint,
    parse_navigation_choice,
    print_navigation_options,
)


@dataclass(frozen=True, slots=True)
class AssignmentChoice:
    """A canonical assignment available in one roster-backed class."""

    class_id: str
    assignment_id: str
    title: str | None
    path: Path


def prompt_assignment_choice(workspace_root: Path) -> AssignmentChoice | None:
    """Let a teacher choose a roster class and its canonical assignment."""
    folders = list_class_folders(workspace_root, require_roster=True)
    if not folders:
        print("No classes found in the current workspace.")
        return None

    print("Available classes:")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.class_id}")
    print_navigation_options()
    print()
    while True:
        selection = input("Select class: ").strip()
        navigation = parse_navigation_choice(selection)
        if selection == "" or navigation is NavigationChoice.BACK:
            print("Class selection canceled.")
            return None
        if selection.isdigit() and 1 <= int(selection) <= len(folders):
            class_id = folders[int(selection) - 1].class_id
            break
        class_matches = [
            folder for folder in folders if folder.class_id == selection
        ]
        if class_matches:
            class_id = class_matches[0].class_id
            break
        print(f"Invalid class selection. {navigation_hint()}")

    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Select Assignment")
    print(f"Class: {class_id}")
    print()

    assignments = available_assignments(workspace_root, class_id)
    if not assignments:
        print(f"No valid assignments found for class {class_id}.")
        return None
    print("Assignments:")
    for index, assignment in enumerate(assignments, start=1):
        label = assignment.assignment_id
        if assignment.title:
            label += f" - {assignment.title}"
        print(f"{index}. {label}")
    print_navigation_options()
    print()
    while True:
        selection = input("Select assignment: ").strip()
        navigation = parse_navigation_choice(selection)
        if selection == "" or navigation is NavigationChoice.BACK:
            print("Assignment selection canceled.")
            return None
        if selection.isdigit() and 1 <= int(selection) <= len(assignments):
            return assignments[int(selection) - 1]
        assignment_matches = [
            item for item in assignments if item.assignment_id == selection
        ]
        if assignment_matches:
            return assignment_matches[0]
        print(f"Invalid assignment selection. {navigation_hint()}")


def available_assignments(
    workspace_root: Path, class_id: str
) -> tuple[AssignmentChoice, ...]:
    """Return valid canonical assignment configs for one class."""
    choices: list[AssignmentChoice] = []
    for discovered in discover_quillan_assignments(workspace_root, class_id):
        if discovered.assignment is None:
            continue
        assignment = discovered.assignment
        title = assignment.get("title")
        choices.append(
            AssignmentChoice(
                class_id=class_id,
                assignment_id=discovered.assignment_id,
                title=title if isinstance(title, str) and title.strip() else None,
                path=discovered.path,
            )
        )
    return tuple(choices)

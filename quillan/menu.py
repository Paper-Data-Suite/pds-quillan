"""Teacher-facing interactive menu for Quillan."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

WorkspaceShowHandler = Callable[[], int]
WorkspaceSetHandler = Callable[[str], int]
WorkspaceActionHandler = Callable[[], int]


def clear_screen() -> None:
    """Clear an interactive terminal without affecting captured output."""
    try:
        is_interactive = sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, OSError):
        is_interactive = False

    if is_interactive:
        os.system("cls" if os.name == "nt" else "clear")


def pause_for_user() -> None:
    """Wait for the teacher before returning to a menu."""
    input("Press Enter to continue...")


def print_menu_header(title: str | None = None) -> None:
    """Print the Quillan identity and an optional section title."""
    print("Quillan")
    if title:
        print(title)
    print()


def print_menu_help() -> None:
    """Print concise teacher-facing purpose, safety, and CLI help."""
    print_menu_header("Help")
    print("Quillan is a local-first, teacher-controlled writing-evidence tool.")
    print("It helps teachers organize and validate writing evidence.")
    print("Teacher judgment remains primary; Quillan is not automated grading software.")
    print()
    print("Quillan does not currently implement AI tagging, AI scoring,")
    print("AI feedback, OCR, scan routing, or full teacher-facing review workflows.")
    print()
    print("Use synthetic data only in repository examples and tests.")
    print("Do not commit or post real student data, rosters, scans, writing, grades,")
    print("feedback, reports, screenshots, or workspace artifacts publicly.")
    print()
    print("Current direct CLI commands:")
    print("  quillan --help")
    print("  quillan validate-standards <standards-profile.json>")
    print("  quillan validate-assignment <assignment.json>")
    print("  quillan workspace show")
    print("  quillan workspace set <folder>")
    print("  quillan workspace validate")
    print("  quillan workspace reset")
    print("  quillan menu")


def launch_assignment_menu() -> None:
    """Display the current assignment-management boundary."""
    clear_screen()
    print_menu_header("Assignment Management")
    print("Assignment management workflows are not implemented yet.")
    print("Current direct CLI support:")
    print("  quillan validate-assignment <assignment.json>")
    print()
    pause_for_user()


def launch_roster_menu() -> None:
    """Display the current roster-management boundary."""
    clear_screen()
    print_menu_header("Roster Management")
    print("Roster management workflows are not implemented yet.")
    print("Quillan currently consumes shared pds-core roster records for printable")
    print("response generation, but it does not provide roster management.")
    print()
    pause_for_user()


def launch_printable_response_menu() -> None:
    """Display the current printable-response workflow boundary."""
    clear_screen()
    print_menu_header("Printable Response Pages")
    print("Printable response PDF generation exists as a Python API, but the")
    print("teacher-facing menu workflow is not implemented yet.")
    print("Generated pages use PDS1 Quillan response payloads and shared pds-core")
    print("roster records.")
    print()
    pause_for_user()


def launch_workspace_menu(
    workspace_show: WorkspaceShowHandler,
    workspace_set: WorkspaceSetHandler,
    workspace_validate: WorkspaceActionHandler,
    workspace_reset: WorkspaceActionHandler,
) -> None:
    """Launch the shared Paper Data Suite workspace settings submenu."""
    while True:
        clear_screen()
        print_menu_header("Workspace Settings")
        print("1. Show current workspace")
        print("2. Set workspace folder")
        print("3. Validate/create current workspace")
        print("4. Reset saved workspace preference")
        print("5. Back")
        print()

        choice = input("Select an option: ").strip()
        print()

        if choice == "1":
            clear_screen()
            print_menu_header("Current Workspace")
            workspace_show()
            print()
            pause_for_user()
        elif choice == "2":
            clear_screen()
            print_menu_header("Set Workspace Folder")
            path = input(
                "Workspace folder (leave blank to cancel): "
            ).strip()
            print()
            if path:
                workspace_set(path)
            else:
                print("Workspace selection canceled. No preference was changed.")
            print()
            pause_for_user()
        elif choice == "3":
            clear_screen()
            print_menu_header("Validate Current Workspace")
            workspace_validate()
            print()
            pause_for_user()
        elif choice == "4":
            clear_screen()
            print_menu_header("Reset Workspace Preference")
            workspace_reset()
            print()
            pause_for_user()
        elif choice == "5":
            return
        else:
            print("Invalid selection. Please enter a number from 1 to 5.")
            print()
            pause_for_user()


def launch_menu(
    workspace_show: WorkspaceShowHandler,
    workspace_set: WorkspaceSetHandler,
    workspace_validate: WorkspaceActionHandler,
    workspace_reset: WorkspaceActionHandler,
) -> int:
    """Launch the Quillan teacher-facing menu skeleton."""
    try:
        while True:
            clear_screen()
            print_menu_header()
            print("1. Assignment Management")
            print("2. Roster Management")
            print("3. Printable Response Pages")
            print("4. Workspace Settings")
            print("5. Help")
            print("6. Exit")
            print()

            choice = input("Select an option: ").strip()
            print()

            if choice == "1":
                launch_assignment_menu()
            elif choice == "2":
                launch_roster_menu()
            elif choice == "3":
                launch_printable_response_menu()
            elif choice == "4":
                launch_workspace_menu(
                    workspace_show,
                    workspace_set,
                    workspace_validate,
                    workspace_reset,
                )
            elif choice == "5":
                clear_screen()
                print_menu_help()
                print()
                pause_for_user()
            elif choice == "6":
                print("Goodbye.")
                return 0
            else:
                print("Invalid selection. Please enter a number from 1 to 6.")
                print()
                pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting Quillan.")
        return 0

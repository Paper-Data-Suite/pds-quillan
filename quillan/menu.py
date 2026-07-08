"""Teacher-facing interactive menu for Quillan."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from pds_core.scan_routes import scans_inbox_dir
from quillan.menu_navigation import (
    NavigationChoice,
    QuitQuillan,
    ReturnToMainMenu,
    navigation_hint,
    parse_navigation_choice,
    print_navigation_options,
)

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
    print("\033[32mQuillan\033[0m")
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
    print("AI feedback, OCR, or full teacher-facing review workflows.")
    print("Guided scan intake routes QR-coded response pages only.")
    print()
    print("Use synthetic data only in repository examples and tests.")
    print("Do not commit or post real student data, rosters, scans, writing, grades,")
    print("feedback, reports, screenshots, or workspace artifacts publicly.")
    print()
    print("Current direct CLI commands:")
    print("  quillan --help")
    print("  quillan validate-assignment <assignment.json>")
    print("  quillan workspace show")
    print("  quillan workspace set <folder>")
    print("  quillan workspace validate")
    print("  quillan workspace reset")
    print("  quillan menu")


def launch_assignment_menu() -> None:
    """Launch writing-assignment config workflows."""
    from quillan.assignment_workflows import launch_assignment_menu as launch

    launch()


def launch_roster_menu() -> None:
    """Launch shared-roster teacher workflows."""
    from quillan.roster_workflows import launch_roster_menu as launch

    launch()


def launch_printable_response_menu() -> None:
    """Launch printable response packet workflows."""
    from quillan.printable_response_workflows import (
        launch_printable_response_menu as launch,
    )

    launch()


def _normalize_menu_path(raw_path: str) -> Path | None:
    stripped = raw_path.strip()
    if not stripped:
        return None
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {
        '"',
        "'",
    }:
        stripped = stripped[1:-1].strip()
    if not stripped:
        return None
    return Path(stripped)


def launch_scan_intake_workflow() -> None:
    """Route scans from the shared inbox, with a power-user path fallback."""
    from quillan.assignment_submission_assembly import assemble_assignment_submissions
    from quillan.cli_app.handlers import routing
    from quillan.cli_app.output import print_assignment_submission_assembly
    from quillan.intake_assembly import assembly_targets_from_intake_summary
    from quillan.scan_intake_summary import ScanIntakeSummary

    try:
        workspace_root = routing.resolve_workspace_root()
    except Exception as error:
        clear_screen()
        print_menu_header("Scan Intake / Route Paper Responses")
        print(f"Error: could not resolve the PDS workspace: {error}")
        print()
        pause_for_user()
        return
    inbox = scans_inbox_dir(workspace_root)
    inbox.mkdir(parents=True, exist_ok=True)
    exit_to_main = False

    def post_route(summary: ScanIntakeSummary) -> None:
        nonlocal exit_to_main
        targets = assembly_targets_from_intake_summary(summary)
        if not targets:
            return
        while True:
            print()
            print("Scan routed successfully.")
            print("Routed evidence was filed for:")
            for index, target in enumerate(targets, start=1):
                print(
                    f"{index}. Class: {target.class_id}; "
                    f"Assignment: {target.assignment_id}"
                )
            print()
            print("Submission records are required before review.")
            if len(targets) == 1:
                print("1. Assemble submissions now")
                print("2. View submission status")
                print_navigation_options()
                choice = input("Select an option: ").strip()
                navigation = parse_navigation_choice(choice)
                if navigation is NavigationChoice.BACK:
                    return
                if choice == "1":
                    target = targets[0]
                    result = assemble_assignment_submissions(
                        workspace_root, target.class_id, target.assignment_id
                    )
                    print_assignment_submission_assembly(result, workspace_root)
                    continue
                if choice == "2":
                    from quillan.submission_status import list_assignment_submission_status
                    from quillan.cli_app.output import print_assignment_submission_status

                    target = targets[0]
                    print_assignment_submission_status(
                        list_assignment_submission_status(
                            workspace_root, target.class_id, target.assignment_id
                        ),
                        workspace_root,
                    )
                    continue
                print(f"Invalid selection. {navigation_hint()}")
                continue
            print_navigation_options()
            choice = input("Select target: ").strip()
            navigation = parse_navigation_choice(choice)
            if choice == "" or navigation is NavigationChoice.BACK:
                return
            if choice.isdigit() and 1 <= int(choice) <= len(targets):
                target = targets[int(choice) - 1]
                result = assemble_assignment_submissions(
                    workspace_root, target.class_id, target.assignment_id
                )
                print_assignment_submission_assembly(result, workspace_root)
            else:
                print(
                    f"Invalid selection. {navigation_hint()}"
                )

    while True:
        clear_screen()
        print_menu_header("Scan Intake / Route Paper Responses")
        print(f"Scan inbox:\n{inbox}\n")
        scans = sorted(
            (
                path
                for path in inbox.iterdir()
                if path.is_file()
                and path.suffix.casefold() in routing.SUPPORTED_SCAN_EXTENSIONS
            ),
            key=lambda path: path.name.casefold(),
        )
        if scans:
            print("Available scans:")
            for index, scan in enumerate(scans, start=1):
                print(f"{index}. {scan.name}")
        else:
            print("No supported scans found in scans_inbox.")
            print(f"\nPlace scanned PDFs or images in:\n{inbox}")
        print("C. Choose custom file/folder path")
        print("R. Refresh")
        print_navigation_options()
        print()
        selection = input("Select scan: ").strip()
        navigation = parse_navigation_choice(selection)
        if navigation is NavigationChoice.BACK:
            return
        if selection == "":
            print("Scan intake canceled. No scan files were routed.")
            print()
            pause_for_user()
            return
        selected_inbox_scan = False
        if selection.casefold() == "r":
            continue
        if selection.casefold() == "c":
            source_path = _normalize_menu_path(
                input("Scan file or folder path (leave blank to cancel): ")
            )
            if source_path is None:
                print("Scan intake canceled. No scan files were routed.")
                pause_for_user()
                continue
        elif selection.isdigit() and 1 <= int(selection) <= len(scans):
            source_path = scans[int(selection) - 1]
            selected_inbox_scan = True
        else:
            # Preserve pasted-path convenience for experienced users of earlier menus.
            source_path = _normalize_menu_path(selection)
            if source_path is None:
                print(f"Invalid selection. {navigation_hint()}")
                pause_for_user()
                continue
        print()
        routing.run_qr_scan_intake(
            source_path,
            workspace_root,
            on_summary=post_route if selected_inbox_scan else None,
        )
        print()
        pause_for_user()
        if exit_to_main:
            return


def launch_review_student_work_menu() -> None:
    """Launch the teacher-facing review navigation workflow."""
    from quillan.review_menu import launch_review_student_work_menu as launch

    launch()


def launch_review_materials_menu() -> None:
    """Launch the teacher-facing review materials preparation menu."""
    from quillan.review_materials_menu import launch_review_materials_menu as launch

    launch()


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
        print_navigation_options()
        print()

        choice = input("Select an option: ").strip()
        navigation = parse_navigation_choice(choice)
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
        elif choice == "5" or navigation is NavigationChoice.BACK:
            return
        else:
            print(f"Invalid selection. {navigation_hint()}")
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
            print("2. Review Student Work")
            print("3. Roster Management")
            print("4. Workspace Settings")
            print("5. Help")
            print("Q. Quit")
            print()

            choice = input("Select an option: ").strip()
            navigation = parse_navigation_choice(
                choice, allow_back=False, allow_main_menu=False
            )
            print()

            if choice == "1":
                launch_assignment_menu()
            elif choice == "2":
                launch_review_student_work_menu()
            elif choice == "3":
                launch_roster_menu()
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
            elif choice == "6" or navigation is NavigationChoice.QUIT:
                print("Goodbye.")
                return 0
            else:
                print("Invalid selection. Please choose a listed option or Q.")
                print()
                pause_for_user()
    except ReturnToMainMenu:
        return launch_menu(
            workspace_show,
            workspace_set,
            workspace_validate,
            workspace_reset,
        )
    except QuitQuillan:
        print("Goodbye.")
        return 0
    except KeyboardInterrupt:
        print("\nExiting Quillan.")
        return 0

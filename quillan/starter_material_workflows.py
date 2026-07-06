"""Disabled teacher-facing workflows for legacy starter review materials."""

from __future__ import annotations


def launch_starter_materials_menu() -> int:
    """Launch an informational placeholder for removed starter-material workflows."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Starter Materials")
            print(
                "Legacy starter comment-bank, tag-bank, and rubric installers "
                "are disabled during the standards-based review redesign."
            )
            print()
            print(
                "No starter review-material files can be installed from this "
                "workflow."
            )
            print()
            print("1. Back")
            print()

            choice = input("Select an option: ").strip()
            print()
            if choice in {"", "1"}:
                return 0
            print("Invalid selection. Please enter 1 to go back.")
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting starter materials menu.")
        return 0


def prompt_preview_starter_materials() -> int:
    """Report that legacy starter material preview is disabled."""
    from quillan.menu import print_menu_header

    print_menu_header("Preview Starter Materials")
    _print_starter_materials_disabled()
    return 1


def prompt_validate_starter_materials() -> int:
    """Report that legacy starter material validation is disabled."""
    from quillan.menu import print_menu_header

    print_menu_header("Validate Starter Materials")
    _print_starter_materials_disabled()
    return 1


def prompt_install_all_starter_materials() -> int:
    """Report that legacy starter material installation is disabled."""
    from quillan.menu import print_menu_header

    print_menu_header("Install Starter Materials")
    _print_starter_materials_disabled()
    print("No files were changed.")
    return 1


def prompt_install_selected_starter_materials() -> int:
    """Report that selected legacy starter material installation is disabled."""
    from quillan.menu import print_menu_header

    print_menu_header("Install Selected Starter Materials")
    _print_starter_materials_disabled()
    print("No files were changed.")
    return 1


def _print_starter_materials_disabled() -> None:
    print(
        "Legacy generic starter review materials are disabled for the "
        "standards-based review redesign."
    )
    print(
        "Focus Standard review-material workflows will be introduced in a "
        "later implementation ticket."
    )

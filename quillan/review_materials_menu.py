"""Disabled Review Materials preparation menu."""

from __future__ import annotations


def launch_review_materials_menu() -> int:
    """Launch an informational placeholder for removed legacy review materials."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Review Materials")
            print(
                "Legacy generic comment-bank, tag-bank, and rubric workflows "
                "have been removed from the active review menu."
            )
            print()
            print(
                "Quillan is being updated for the standards-based review "
                "redesign. Focus Standard review workflows will be added in "
                "a later release."
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
        print("\nExiting review materials menu.")
        return 0

"""Disabled Review Materials preparation menu."""

from __future__ import annotations


def launch_review_materials_menu() -> int:
    """Launch an informational placeholder for removed legacy review materials."""
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
            print_navigation_options()
            print()

            choice = input("Select an option: ").strip()
            navigation = parse_navigation_choice(choice)
            print()

            if choice in {"", "1"} or navigation is NavigationChoice.BACK:
                return 0
            print(f"Invalid selection. {navigation_hint()}")
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting review materials menu.")
        return 0

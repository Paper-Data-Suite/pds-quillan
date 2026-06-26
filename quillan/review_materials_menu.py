"""Teacher-facing Review Materials preparation menu."""

from __future__ import annotations


def launch_review_materials_menu() -> int:
    """Launch informational review-material preparation screens."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Review Materials")
            print(
                "Reusable review materials help teachers prepare comments, "
                "tags, and scoring tools before reviewing student work."
            )
            print()
            print("1. Comment Banks")
            print("2. Tag Banks")
            print("3. Rubrics / Scoring Profiles")
            print("4. Starter Materials")
            print("5. Back")
            print()

            choice = input("Select an option: ").strip()
            print()

            if choice in {"", "5"}:
                return 0
            if choice == "1":
                _show_comment_banks_info()
            elif choice == "2":
                _show_tag_banks_info()
            elif choice == "3":
                _show_rubrics_info()
            elif choice == "4":
                _show_starter_materials_info()
            else:
                print("Invalid selection. Please enter a number from 1 to 5.")
                print()
                pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting review materials menu.")
        return 0


def _show_comment_banks_info() -> None:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    clear_screen()
    print_menu_header("Comment Banks")
    print("Comment banks are reusable teacher-authored feedback comments.")
    print(
        "They can be selected during review and copied into a student's "
        "review record."
    )
    print()
    print("Comment bank creation and editing will be implemented in #165.")
    print()
    print("Expected workspace location:")
    print("shared/comment_banks/")
    print()
    print("No files were changed.")
    print()
    pause_for_user()


def _show_tag_banks_info() -> None:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    clear_screen()
    print_menu_header("Tag Banks")
    print(
        "Tag banks will store reusable teacher observations for quick "
        "review tagging."
    )
    print(
        "Tags are teacher-controlled review aids; they are not grades or "
        "automatic mastery judgments."
    )
    print()
    print(
        "Tag-bank creation and review-time tag selection will be "
        "implemented in #166."
    )
    print()
    print("Expected future workspace location:")
    print("shared/tag_banks/")
    print()
    print("No files were changed.")
    print()
    pause_for_user()


def _show_rubrics_info() -> None:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    clear_screen()
    print_menu_header("Rubrics / Scoring Profiles")
    print(
        "Rubrics and scoring profiles will help teachers score prepared "
        "criteria without typing criterion IDs during review."
    )
    print()
    print(
        "Rubric profile creation and enumerated scoring will be implemented "
        "in #167."
    )
    print()
    print("Expected future workspace location:")
    print("shared/rubrics/")
    print()
    print("No files were changed.")
    print()
    pause_for_user()


def _show_starter_materials_info() -> None:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    clear_screen()
    print_menu_header("Starter Materials")
    print(
        "Starter materials will provide optional synthetic examples for "
        "local testing and setup."
    )
    print()
    print("Starter material installation will be implemented in #169.")
    print()
    print("No files were changed.")
    print()
    pause_for_user()

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
                from quillan.comment_bank_workflows import launch_comment_banks_menu

                launch_comment_banks_menu()
            elif choice == "2":
                from quillan.tag_bank_workflows import launch_tag_banks_menu

                launch_tag_banks_menu()
            elif choice == "3":
                from quillan.rubric_workflows import launch_rubrics_menu

                launch_rubrics_menu()
            elif choice == "4":
                _show_starter_materials_info()
            else:
                print("Invalid selection. Please enter a number from 1 to 5.")
                print()
                pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting review materials menu.")
        return 0


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

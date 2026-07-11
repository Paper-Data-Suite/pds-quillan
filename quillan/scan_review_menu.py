"""Teacher-facing menu workflow for resolving Quillan scan review items."""

from __future__ import annotations

from pathlib import Path

from quillan.scan_review_resolution import (
    DEFAULT_RESOLUTION_MESSAGES,
    QuillanReviewItem,
    ScanReviewResolutionError,
    discover_scan_review_items,
    resolve_scan_review_item,
)

_ACTIONS: tuple[tuple[str, str], ...] = (
    ("rescan_needed", "Rescan needed"),
    ("cannot_route", "Cannot route safely"),
    ("mixed_assignment", "Mixed assignment"),
    ("evidence_filed", "Evidence filed elsewhere"),
    ("dismissed_duplicate", "Dismiss duplicate"),
    ("defer", "Defer for later"),
    ("other", "Other"),
)


def launch_scan_review_resolution_menu(workspace_root: Path) -> int:
    """List active review items and write teacher-selected resolutions."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header
    from quillan.menu_navigation import (
        NavigationChoice,
        navigation_hint,
        parse_navigation_choice,
        print_navigation_options,
    )

    while True:
        clear_screen()
        print_menu_header("Resolve Scan Review Items")
        try:
            discovery = discover_scan_review_items(workspace_root)
        except ScanReviewResolutionError as error:
            print(f"Error: {error}")
            print()
            pause_for_user()
            return 1
        if not discovery.items:
            print("There are no unresolved or deferred scan review items.")
            if discovery.warnings:
                print(
                    f"Skipped {len(discovery.warnings)} malformed or unreadable "
                    "metadata file(s)."
                )
            print()
            pause_for_user()
            return 0

        for index, item in enumerate(discovery.items, start=1):
            page = "" if item.source_page_number is None else f", page {item.source_page_number}"
            print(
                f"{index}. {item.source_filename}{page} — "
                f"{item.failure_category} ({item.display_status})"
            )
        if discovery.warnings:
            print(
                f"\nSkipped {len(discovery.warnings)} malformed or unreadable "
                "metadata file(s)."
            )
        print_navigation_options()
        print()
        choice = input("Select a review item: ").strip()
        navigation = parse_navigation_choice(choice)
        if choice == "" or navigation is NavigationChoice.BACK:
            return 0
        if not choice.isdigit() or not 1 <= int(choice) <= len(discovery.items):
            print(f"Invalid selection. {navigation_hint()}")
            print()
            pause_for_user()
            continue

        item = discovery.items[int(choice) - 1]
        action = _prompt_action(item)
        if action is None:
            continue
        message = _prompt_message(action)
        if message is None:
            continue
        evidence_path = _prompt_evidence_path() if action == "evidence_filed" else None

        clear_screen()
        print_menu_header("Scan Review Result")
        try:
            result = resolve_scan_review_item(
                workspace_root,
                item.failure_id,
                action=action,
                message=message,
                evidence_path=evidence_path,
            )
        except ScanReviewResolutionError as error:
            print(f"Could not save the scan review decision: {error}")
        else:
            print(f"Scan review item {result.resolution_status}.")
            print(f"Resolution record: {result.resolution_metadata_relative_path}")
        print()
        pause_for_user()


def _prompt_action(item: QuillanReviewItem) -> str | None:
    from quillan.menu import clear_screen, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    clear_screen()
    print_menu_header("Scan Review Details")
    print(f"Category: {item.failure_category}")
    print(f"What failed: {item.failure_message}")
    print(f"Source: {item.source_filename}")
    print(f"Page: {_display(item.source_page_number)}")
    if item.retained_source_path is not None:
        print(f"Retained source: {item.retained_source_path}")
    if item.review_copy_path is not None:
        print(f"Review evidence: {item.review_copy_path}")
    print(f"Review record: {item.failure_metadata_relative_path}")
    print(f"Class: {_display(item.class_id)}")
    print(f"Assignment: {_display(item.assignment_id)}")
    print(f"Student: {_display(item.student_id)}")
    print()
    input("Press Enter to choose an action...")

    clear_screen()
    print_menu_header("Choose Scan Review Action")
    for index, (_, label) in enumerate(_ACTIONS, start=1):
        print(f"{index}. {label}")
    print("B. Back")
    print()
    choice = input("Select an action: ").strip()
    if parse_navigation_choice(choice) is NavigationChoice.BACK or choice == "":
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(_ACTIONS):
        return _ACTIONS[int(choice) - 1][0]
    return None


def _prompt_message(action: str) -> str | None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Scan Review Note")
    default = DEFAULT_RESOLUTION_MESSAGES.get(action)
    if default is not None:
        print(f"Default note: {default}")
        print()
        value = input("Note (leave blank to use the default): ").strip()
        return value or default
    value = input("Short teacher note (required; leave blank to cancel): ").strip()
    return value or None


def _prompt_evidence_path() -> str | None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Evidence Path")
    print("You may record an existing workspace-relative evidence path.")
    print("No file will be copied or moved.")
    print()
    value = input("Evidence path (optional): ").strip()
    return value or None


def _display(value: object | None) -> str:
    return "—" if value is None else str(value)

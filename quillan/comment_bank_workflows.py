"""Teacher-facing comment-bank creation and editing workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.comment_banks import (
    ALLOWED_POLARITIES,
    CommentBankError,
    load_comment_bank,
)
from quillan.comment_bank_writing import (
    build_comment,
    build_comment_bank,
    build_comment_category,
    current_timestamp,
    ensure_unique_identifier,
    list_comment_bank_files,
    list_valid_comment_banks,
    parse_comma_separated_values,
    summarize_comment_bank,
    suggest_identifier,
    touch_updated_at,
    write_comment_bank,
)

_CATEGORY_SUGGESTIONS: tuple[tuple[str, str], ...] = (
    ("Content Accuracy", "Comments about correctness, accuracy, or completeness."),
    ("Evidence / Support", "Comments about support, examples, sources, or data."),
    ("Reasoning / Explanation", "Comments about reasoning, analysis, or explanation."),
    ("Organization", "Comments about structure, sequence, or transitions."),
    ("Process / Method", "Comments about procedure, process, method, or steps."),
    ("Reflection", "Comments about reflection, insight, or self-assessment."),
    ("Creativity / Design", "Comments about design choices or creative decisions."),
    ("Conventions", "Comments about clarity, grammar, mechanics, or formatting."),
)


def launch_comment_banks_menu() -> int:
    """Launch the teacher-facing Comment Banks submenu."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Comment Banks")
            print("Comment banks store reusable teacher-authored feedback comments.")
            print(
                "They can be selected during review and copied into a "
                "student's review record."
            )
            print()
            print("1. Create comment bank")
            print("2. View comment banks")
            print("3. Edit comment bank")
            print("4. Add category")
            print("5. Add comment")
            print("6. Validate comment bank")
            print("7. Back")
            print()

            choice = input("Select an option: ").strip()
            print()
            if choice in {"", "7"}:
                return 0
            workflows = {
                "1": prompt_create_comment_bank,
                "2": prompt_view_comment_banks,
                "3": prompt_edit_comment_bank,
                "4": prompt_add_category,
                "5": prompt_add_comment,
                "6": prompt_validate_comment_bank,
            }
            workflow = workflows.get(choice)
            if workflow is None:
                print("Invalid selection. Please enter a number from 1 to 7.")
            else:
                clear_screen()
                workflow()
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting comment banks menu.")
        return 0


def prompt_create_comment_bank() -> int:
    """Prompt for and save one complete valid comment bank."""
    from quillan.menu import print_menu_header

    print_menu_header("Create Comment Bank")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1

    try:
        title = _required_input(
            "Bank title:\nExample: General Written Response Comments\n"
        )
        suggestion = suggest_identifier(title)
        print(f"Suggested bank_id:\n{suggestion}")
        bank_id = input("Press Enter to accept, or type a different bank_id: ").strip()
        if not bank_id:
            bank_id = suggestion
        description = input(
            "Description:\n"
            "Example: Reusable comments for written responses across subjects.\n"
        ).strip()
        writing_types = _prompt_writing_types()
        print()
        print("Now add at least one category and one comment before saving.")
        print()
        category = _prompt_new_category(existing_ids=set())
        if category is None:
            print("Create comment bank canceled. No file was created.")
            return 1
        comment = _prompt_new_comment(
            categories=[category],
            bank_writing_types=writing_types,
            existing_ids=set(),
        )
        if comment is None:
            print("Create comment bank canceled. No file was created.")
            return 1
        bank = build_comment_bank(
            bank_id=bank_id,
            title=title,
            description=description,
            writing_types=writing_types,
            categories=[category],
            comments=[comment],
        )
    except (CommentBankError, ValueError) as error:
        print(f"Error: {error}")
        print("No file was created.")
        return 1

    path = Path(workspace_root) / "shared" / "comment_banks" / f"{bank_id}.json"
    print()
    print("Ready to save comment bank:")
    print()
    print(f"Bank ID: {bank['bank_id']}")
    print(f"Title: {bank['title']}")
    print(f"Writing types: {', '.join(bank['writing_types'])}")
    print(f"Categories: {len(bank['categories'])}")
    print(f"Comments: {len(bank['comments'])}")
    print(f"Path: {path}")
    print()
    print("1. Save")
    print("2. Cancel")
    print()
    if input("Select an option: ").strip() != "1":
        print("Create comment bank canceled. No file was created.")
        return 1

    overwrite = False
    if path.exists():
        confirmation = input("Type OVERWRITE to replace it: ").strip()
        if confirmation != "OVERWRITE":
            print("Canceled: existing comment bank was not changed.")
            return 1
        overwrite = True

    try:
        saved_path = write_comment_bank(workspace_root, bank, overwrite=overwrite)
    except (CommentBankError, OSError) as error:
        print(f"Error: {error}")
        return 1
    print(f"Saved comment bank: {saved_path}")
    return 0


def prompt_view_comment_banks() -> int:
    """List comment banks and optionally show one bank summary."""
    from quillan.menu import print_menu_header

    print_menu_header("Comment Banks")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    files = list_comment_bank_files(workspace_root)
    valid = [item for item in files if item.is_valid and item.bank is not None]
    invalid = [item for item in files if not item.is_valid]

    if not valid:
        print("No valid shared comment banks found.")
        print()
        print(
            "Create one from Review Materials -> Comment Banks -> "
            "Create comment bank."
        )
        print()
        print("Expected location:")
        print("shared/comment_banks/")
    else:
        print("Comment Banks")
        print()
        for index, item in enumerate(valid, start=1):
            bank = item.bank
            assert bank is not None
            print(f"{index}. {bank['bank_id']} - {bank['title']}")
            print(f"   Writing types: {', '.join(bank['writing_types'])}")
            print(f"   Categories: {len(bank['categories'])}")
            print(f"   Comments: {len(bank['comments'])}")
            print()
        print("B. Back")
        print()
        selection = input("Select comment bank to view, or Back: ").strip()
        if selection.isdigit() and 1 <= int(selection) <= len(valid):
            item = valid[int(selection) - 1]
            assert item.bank is not None
            print()
            print(summarize_comment_bank(item.bank, item.path))
        elif selection and selection.casefold() != "b":
            print("Invalid selection. Please choose a listed bank or Back.")

    _print_invalid_files(invalid)
    return 0


def prompt_edit_comment_bank() -> int:
    """Safely edit title, description, or writing types for one valid bank."""
    from quillan.menu import print_menu_header

    print_menu_header("Edit Comment Bank")
    selected = _prompt_valid_bank()
    if selected is None:
        return 1
    path, bank = selected
    print()
    print("1. Edit title")
    print("2. Edit description")
    print("3. Edit writing types")
    print("4. Back")
    print()
    choice = input("Select an option: ").strip()
    if choice in {"", "4"}:
        print("Edit comment bank canceled. No file was changed.")
        return 0

    updated = touch_updated_at(bank)
    try:
        if choice == "1":
            updated["title"] = _required_input("Bank title: ")
        elif choice == "2":
            updated["description"] = input("Description: ").strip()
        elif choice == "3":
            updated["writing_types"] = _prompt_writing_types()
        else:
            print("Invalid selection. Please enter a number from 1 to 4.")
            return 1
        write_comment_bank(path.parents[2], updated, overwrite=True)
    except (CommentBankError, ValueError, OSError) as error:
        print(f"Error: {error}")
        print("Existing comment bank was not changed.")
        return 1
    print(f"Saved comment bank: {path}")
    return 0


def prompt_add_category() -> int:
    """Add a category to an existing valid bank."""
    from quillan.menu import print_menu_header

    print_menu_header("Add Category")
    selected = _prompt_valid_bank()
    if selected is None:
        return 1
    path, bank = selected
    print()
    _print_categories(bank)
    existing_ids = {
        str(category["category_id"])
        for category in bank["categories"]
        if isinstance(category, dict)
    }
    try:
        category = _prompt_new_category(existing_ids=existing_ids)
    except (CommentBankError, ValueError) as error:
        print(f"Error: {error}")
        print("Add category canceled. No file was changed.")
        return 1
    if category is None:
        print("Add category canceled. No file was changed.")
        return 1
    updated = touch_updated_at(bank)
    updated["categories"] = [dict(item) for item in bank["categories"]] + [category]
    print()
    print(f"Add category '{category['label']}' to {bank['bank_id']}?")
    print("1. Save")
    print("2. Cancel")
    if input("Select an option: ").strip() != "1":
        print("Add category canceled. No file was changed.")
        return 1
    try:
        write_comment_bank(path.parents[2], updated, overwrite=True)
    except (CommentBankError, OSError) as error:
        print(f"Error: {error}")
        print("Existing comment bank was not changed.")
        return 1
    print(f"Saved comment bank: {path}")
    return 0


def prompt_add_comment() -> int:
    """Add a comment to an existing valid bank."""
    from quillan.menu import print_menu_header

    print_menu_header("Add Comment")
    selected = _prompt_valid_bank()
    if selected is None:
        return 1
    path, bank = selected
    existing_ids = {
        str(comment["comment_id"])
        for comment in bank["comments"]
        if isinstance(comment, dict)
    }
    try:
        comment = _prompt_new_comment(
            categories=list(bank["categories"]),
            bank_writing_types=list(bank["writing_types"]),
            existing_ids=existing_ids,
        )
    except (CommentBankError, ValueError) as error:
        print(f"Error: {error}")
        print("Add comment canceled. No file was changed.")
        return 1
    if comment is None:
        print("Add comment canceled. No file was changed.")
        return 1
    updated = touch_updated_at(bank)
    updated["comments"] = [dict(item) for item in bank["comments"]] + [comment]
    print()
    print(f"Add comment '{comment['label']}' to {bank['bank_id']}?")
    print("1. Save")
    print("2. Cancel")
    if input("Select an option: ").strip() != "1":
        print("Add comment canceled. No file was changed.")
        return 1
    try:
        write_comment_bank(path.parents[2], updated, overwrite=True)
    except (CommentBankError, OSError) as error:
        print(f"Error: {error}")
        print("Existing comment bank was not changed.")
        return 1
    print(f"Saved comment bank: {path}")
    return 0


def prompt_validate_comment_bank() -> int:
    """Validate one existing comment-bank file without modifying it."""
    from quillan.menu import print_menu_header

    print_menu_header("Validate Comment Bank")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    files = list_comment_bank_files(workspace_root)
    if not files:
        print("No comment bank files found.")
        print("Expected location: shared/comment_banks/")
        return 1
    for index, item in enumerate(files, start=1):
        print(f"{index}. {item.path}")
    print("B. Back")
    print()
    selection = input("Select comment bank file: ").strip()
    if selection == "" or selection.casefold() == "b":
        print("Validate comment bank canceled.")
        return 0
    if not selection.isdigit() or not 1 <= int(selection) <= len(files):
        print("Invalid selection. Please choose a listed file or Back.")
        return 1
    path = files[int(selection) - 1].path
    try:
        bank = load_comment_bank(path)
    except (CommentBankError, OSError) as error:
        print("Comment bank is invalid.")
        print()
        print(f"Path: {path}")
        print(f"Error: {error}")
        return 1
    print("Comment bank is valid.")
    print()
    print(f"Bank ID: {bank['bank_id']}")
    print(f"Title: {bank['title']}")
    print(f"Categories: {len(bank['categories'])}")
    print(f"Comments: {len(bank['comments'])}")
    print(f"Path: {path}")
    return 0


def _workspace_root() -> Path | None:
    try:
        return resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return None


def _required_input(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError("This field is required.")
    return value


def _prompt_writing_types() -> list[str]:
    value = input(
        "Writing types, comma-separated:\n"
        "Examples: general, lab_report, reflection, research, constructed_response\n"
    )
    writing_types = parse_comma_separated_values(value)
    if not writing_types:
        raise ValueError("At least one writing type is required.")
    return writing_types


def _prompt_new_category(existing_ids: set[str]) -> dict[str, Any] | None:
    print("Add Category")
    print()
    print("Categories help teachers find comments quickly during review.")
    print()
    print("Suggested categories:")
    for index, (label, _description) in enumerate(_CATEGORY_SUGGESTIONS, start=1):
        print(f"{index}. {label}")
    custom_index = len(_CATEGORY_SUGGESTIONS) + 1
    print(f"{custom_index}. Custom category")
    print("B. Back")
    print()
    selection = input("Select suggestion or choose Custom: ").strip()
    if selection == "" or selection.casefold() == "b":
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(_CATEGORY_SUGGESTIONS):
        label, description = _CATEGORY_SUGGESTIONS[int(selection) - 1]
    elif selection == str(custom_index):
        label = _required_input("Category label:\nExample: Process / Method\n")
        description = input(
            "Description:\n"
            "Example: Comments about procedure, process, method, or steps.\n"
        ).strip()
    else:
        print("Invalid category selection.")
        return None
    suggestion = suggest_identifier(label)
    print(f"Suggested category_id:\n{suggestion}")
    category_id = input(
        "Press Enter to accept, or type a different category_id: "
    ).strip()
    if not category_id:
        category_id = suggestion
    sort_order = _parse_optional_nonnegative_int(
        input("Sort order (leave blank to auto-assign): ")
    )
    if sort_order is None:
        sort_order = len(existing_ids) + 1
    ensure_unique_identifier(category_id, existing_ids, "category_id")
    return build_comment_category(
        category_id=category_id,
        label=label,
        description=description,
        sort_order=sort_order,
    )


def _prompt_new_comment(
    *,
    categories: list[dict[str, Any]],
    bank_writing_types: list[str],
    existing_ids: set[str],
) -> dict[str, Any] | None:
    print()
    print("Add Comment")
    print()
    label = _required_input("Comment label:\nExample: Explanation needs more detail\n")
    suggestion = suggest_identifier(label)
    print(f"Suggested comment_id:\n{suggestion}")
    comment_id = input(
        "Press Enter to accept, or type a different comment_id: "
    ).strip()
    if not comment_id:
        comment_id = suggestion
    ensure_unique_identifier(comment_id, existing_ids, "comment_id")
    text = _required_input(
        "Student-facing feedback text:\n"
        "Example: Your response identifies the idea, but explain your "
        "reasoning more fully.\n"
    )
    category_id = _prompt_category_id(categories)
    if category_id is None:
        return None
    polarity = _prompt_polarity()
    if polarity is None:
        return None
    include_default = _prompt_yes_no(
        "Include in feedback by default?",
        default=True,
    )
    if include_default is None:
        return None
    student_facing = _prompt_yes_no("Student-facing comment?", default=True)
    if student_facing is None:
        return None
    metadata = _prompt_optional_metadata(bank_writing_types)
    if metadata is None:
        return None
    return build_comment(
        comment_id=comment_id,
        label=label,
        text=text,
        category_id=category_id,
        polarity=polarity,
        include_in_feedback_default=include_default,
        student_facing=student_facing,
        module_details={},
        optional_metadata=metadata,
    )


def _prompt_category_id(categories: list[dict[str, Any]]) -> str | None:
    print()
    print("Category:")
    for index, category in enumerate(categories, start=1):
        print(f"{index}. {category['label']}")
    print("B. Back")
    print()
    selection = input("Select category: ").strip()
    if selection == "" or selection.casefold() == "b":
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(categories):
        return str(categories[int(selection) - 1]["category_id"])
    print("Invalid category selection.")
    return None


def _prompt_polarity() -> str | None:
    polarities = ("positive", "developing", "negative", "neutral")
    print()
    print("Polarity:")
    for index, polarity in enumerate(polarities, start=1):
        print(f"{index}. {polarity}")
    print("B. Back")
    print()
    selection = input("Select polarity: ").strip()
    if selection == "" or selection.casefold() == "b":
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(polarities):
        return polarities[int(selection) - 1]
    if selection in ALLOWED_POLARITIES:
        return selection
    print("Invalid polarity selection.")
    return None


def _prompt_yes_no(label: str, *, default: bool) -> bool | None:
    default_label = "Y/n" if default else "y/N"
    print()
    print(f"{label}")
    print(f"1. Yes{' (default)' if default else ''}")
    print(f"2. No{' (default)' if not default else ''}")
    print("B. Back")
    selection = input(f"Select an option ({default_label}): ").strip().lower()
    if selection == "":
        return default
    if selection in {"1", "y", "yes", "true"}:
        return True
    if selection in {"2", "n", "no", "false"}:
        return False
    if selection == "b":
        return None
    print("Invalid selection. Please choose Yes, No, or Back.")
    return None


def _prompt_optional_metadata(bank_writing_types: list[str]) -> dict[str, Any] | None:
    print()
    response = input("Add optional metadata? (y/N): ").strip().lower()
    if response in {"", "n", "no"}:
        return {}
    if response not in {"y", "yes"}:
        print("Invalid selection. Optional metadata skipped by canceling.")
        return None
    metadata: dict[str, Any] = {}
    for field in (
        "short_text",
        "subcategory",
        "teacher_note",
        "follow_up_prompt",
        "revision_action",
    ):
        value = input(f"{field} (leave blank to omit): ").strip()
        if value:
            metadata[field] = value
    writing_types = parse_comma_separated_values(
        input("Comment writing types, comma-separated (leave blank to omit): ")
    )
    if writing_types:
        outside = set(writing_types) - set(bank_writing_types)
        if outside:
            print(
                "Invalid comment writing types. They must be part of the bank "
                f"writing types: {', '.join(bank_writing_types)}."
            )
            return None
        metadata["writing_types"] = writing_types
    for field in ("standard_ids", "criterion_ids", "tags", "hotwords"):
        values = parse_comma_separated_values(
            input(f"{field}, comma-separated (leave blank to omit): ")
        )
        if values:
            metadata[field] = values
    severity = _parse_optional_nonnegative_int(
        input("severity_default (leave blank to omit): ")
    )
    if severity is not None:
        metadata["severity_default"] = severity
    sort_order = _parse_optional_nonnegative_int(
        input("sort_order (leave blank to omit): ")
    )
    if sort_order is not None:
        metadata["sort_order"] = sort_order
    timestamp = current_timestamp()
    metadata["created_at"] = timestamp
    metadata["updated_at"] = timestamp
    return metadata


def _prompt_valid_bank() -> tuple[Path, dict[str, Any]] | None:
    workspace_root = _workspace_root()
    if workspace_root is None:
        return None
    files = list_valid_comment_banks(workspace_root)
    if not files:
        print("No valid shared comment banks found.")
        print(
            "Create one from Review Materials -> Comment Banks -> "
            "Create comment bank."
        )
        return None
    print("Available comment banks:")
    for index, item in enumerate(files, start=1):
        assert item.bank is not None
        print(f"{index}. {item.bank['bank_id']} - {item.bank['title']}")
    print("B. Back")
    print()
    selection = input("Select comment bank: ").strip()
    if selection == "" or selection.casefold() == "b":
        print("Comment bank selection canceled.")
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(files):
        item = files[int(selection) - 1]
        assert item.bank is not None
        return item.path, item.bank
    for item in files:
        assert item.bank is not None
        if item.bank["bank_id"] == selection:
            return item.path, item.bank
    print("Invalid comment bank selection. Please choose a listed bank or Back.")
    return None


def _print_categories(bank: dict[str, Any]) -> None:
    print("Existing categories:")
    for index, category in enumerate(bank["categories"], start=1):
        print(f"{index}. {category['category_id']} - {category['label']}")


def _print_invalid_files(invalid: list[Any]) -> None:
    if not invalid:
        return
    print()
    print("Invalid comment bank files:")
    print()
    for item in invalid:
        print(f"- {item.path}")
        print(f"  Error: {item.error}")


def _parse_optional_nonnegative_int(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError as error:
        raise ValueError("Value must be a non-negative integer.") from error
    if parsed < 0:
        raise ValueError("Value must be a non-negative integer.")
    return parsed

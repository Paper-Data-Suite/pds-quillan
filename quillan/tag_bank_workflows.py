"""Legacy teacher-facing tag-bank creation and editing workflows.

Retained temporarily for compatibility; not exposed through active v0.8.6 menus.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.authoring_prompt_helpers import (
    print_criterion_ids_help,
    print_identifier_guidance,
    print_priority_severity_help,
    print_standard_ids_help,
    prompt_display_order,
    prompt_identifier_with_guidance,
    prompt_writing_assignment_types,
)
from quillan.tag_banks import ALLOWED_POLARITIES, TagBankError, load_tag_bank
from quillan.tag_bank_writing import (
    build_tag_bank,
    build_tag_category,
    build_tag_template,
    current_timestamp,
    ensure_unique_identifier,
    list_tag_bank_files,
    list_valid_tag_banks,
    parse_comma_separated_values,
    summarize_tag_bank,
    suggest_identifier,
    touch_updated_at,
    write_tag_bank,
)

_CATEGORY_SUGGESTIONS: tuple[tuple[str, str], ...] = (
    ("Content Accuracy", "Teacher observations about accuracy or completeness."),
    ("Evidence / Support", "Teacher observations about support, examples, sources, or data."),
    ("Reasoning / Explanation", "Teacher observations about reasoning, analysis, or explanation."),
    ("Organization", "Teacher observations about structure, sequence, or transitions."),
    ("Process / Method", "Teacher observations about procedure, process, method, or steps."),
    ("Reflection", "Teacher observations about reflection, insight, or self-assessment."),
    ("Creativity / Design", "Teacher observations about design choices or creative decisions."),
    ("Conventions", "Teacher observations about clarity, mechanics, or formatting."),
)


def launch_tag_banks_menu() -> int:
    """Launch the teacher-facing Tag Banks submenu."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Tag Banks")
            print("Tag banks store reusable teacher observations for quick review tagging.")
            print("Tags are review aids; they are not grades or automatic mastery judgments.")
            print()
            print("1. Create tag bank")
            print("2. View tag banks")
            print("3. Edit tag bank")
            print("4. Add category")
            print("5. Add reusable tag")
            print("6. Validate tag bank")
            print("7. Back")
            print()
            choice = input("Select an option: ").strip()
            print()
            if choice in {"", "7"}:
                return 0
            workflows = {
                "1": prompt_create_tag_bank,
                "2": prompt_view_tag_banks,
                "3": prompt_edit_tag_bank,
                "4": prompt_add_category,
                "5": prompt_add_tag_template,
                "6": prompt_validate_tag_bank,
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
        print("\nExiting tag banks menu.")
        return 0


def prompt_create_tag_bank() -> int:
    """Prompt for and save one complete valid tag bank."""
    from quillan.menu import print_menu_header

    print_menu_header("Create Tag Bank")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    try:
        title = _required_input("Tag bank title:\nExample: General Written Response Tags\n")
        suggestion = suggest_identifier(title)
        tag_bank_id = prompt_identifier_with_guidance("tag_bank_id", suggestion)
        description = input(
            "Description:\n"
            "Example: Reusable teacher observations for written responses across subjects.\n"
        ).strip()
        writing_types = _prompt_writing_types()
        print()
        print("Now add at least one category and one reusable tag before saving.")
        print()
        category = _prompt_new_category(existing_ids=set())
        if category is None:
            print("Create tag bank canceled. No file was created.")
            return 1
        tag = _prompt_new_tag_template(
            categories=[category],
            bank_writing_types=writing_types,
            existing_ids=set(),
        )
        if tag is None:
            print("Create tag bank canceled. No file was created.")
            return 1
        bank = build_tag_bank(
            tag_bank_id=tag_bank_id,
            title=title,
            description=description,
            writing_types=writing_types,
            categories=[category],
            tags=[tag],
        )
    except (TagBankError, ValueError) as error:
        print(f"Error: {error}")
        print("No file was created.")
        return 1

    path = Path(workspace_root) / "shared" / "tag_banks" / f"{tag_bank_id}.json"
    print()
    print("Ready to save tag bank:")
    print()
    print(f"Tag Bank ID: {bank['tag_bank_id']}")
    print(f"Title: {bank['title']}")
    print(f"Writing assignment types: {', '.join(bank['writing_types'])}")
    print(f"Categories: {len(bank['categories'])}")
    print(f"Tags: {len(bank['tags'])}")
    print(f"Path: {path}")
    print()
    print("1. Save")
    print("2. Cancel")
    print()
    if input("Select an option: ").strip() != "1":
        print("Create tag bank canceled. No file was created.")
        return 1

    overwrite = False
    if path.exists():
        confirmation = input("Type OVERWRITE to replace it: ").strip()
        if confirmation != "OVERWRITE":
            print("Canceled: existing tag bank was not changed.")
            return 1
        overwrite = True
    try:
        saved_path = write_tag_bank(workspace_root, bank, overwrite=overwrite)
    except (TagBankError, OSError) as error:
        print(f"Error: {error}")
        return 1
    print(f"Saved tag bank: {saved_path}")
    _prompt_after_tag_bank_saved(bank["title"])
    return 0


def prompt_view_tag_banks() -> int:
    """List tag banks and optionally show one bank summary."""
    from quillan.menu import print_menu_header

    print_menu_header("Tag Banks")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    files = list_tag_bank_files(workspace_root)
    valid = [item for item in files if item.is_valid and item.bank is not None]
    invalid = [item for item in files if not item.is_valid]
    if not valid:
        print("No valid shared tag banks found.")
        print()
        print(
            "Create one from Review Student Work -> Manage Review Materials "
            "-> Tag Banks -> Create tag bank."
        )
        print()
        print("Expected location:")
        print("shared/tag_banks/")
    else:
        print("Tag Banks")
        print()
        for index, item in enumerate(valid, start=1):
            bank = item.bank
            assert bank is not None
            print(f"{index}. {bank['tag_bank_id']} - {bank['title']}")
            print(f"   Writing assignment types: {', '.join(bank['writing_types'])}")
            print(f"   Categories: {len(bank['categories'])}")
            print(f"   Tags: {len(bank['tags'])}")
            print()
        print("B. Back")
        print()
        selection = input("Select tag bank to view, or Back: ").strip()
        if selection.isdigit() and 1 <= int(selection) <= len(valid):
            item = valid[int(selection) - 1]
            assert item.bank is not None
            print()
            print(summarize_tag_bank(item.bank, item.path))
        elif selection and selection.casefold() != "b":
            print("Invalid selection. Please choose a listed bank or Back.")
    _print_invalid_files(invalid)
    return 0


def prompt_edit_tag_bank() -> int:
    """Safely edit title, description, or writing types for one valid bank."""
    from quillan.menu import print_menu_header

    print_menu_header("Edit Tag Bank")
    selected = _prompt_valid_bank()
    if selected is None:
        return 1
    path, bank = selected
    print()
    print("1. Edit title")
    print("2. Edit description")
    print("3. Edit writing assignment types")
    print("4. Back")
    print()
    choice = input("Select an option: ").strip()
    if choice in {"", "4"}:
        print("Edit tag bank canceled. No file was changed.")
        return 0
    updated = touch_updated_at(bank)
    try:
        if choice == "1":
            updated["title"] = _required_input("Tag bank title: ")
        elif choice == "2":
            updated["description"] = input("Description: ").strip()
        elif choice == "3":
            updated["writing_types"] = _prompt_writing_types()
        else:
            print("Invalid selection. Please enter a number from 1 to 4.")
            return 1
        write_tag_bank(path.parents[2], updated, overwrite=True)
    except (TagBankError, ValueError, OSError) as error:
        print(f"Error: {error}")
        print("Existing tag bank was not changed.")
        return 1
    print(f"Saved tag bank: {path}")
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
    except (TagBankError, ValueError) as error:
        print(f"Error: {error}")
        print("Add category canceled. No file was changed.")
        return 1
    if category is None:
        print("Add category canceled. No file was changed.")
        return 1
    updated = touch_updated_at(bank)
    updated["categories"] = [dict(item) for item in bank["categories"]] + [category]
    print()
    print(f"Add category '{category['label']}' to {bank['tag_bank_id']}?")
    print("1. Save")
    print("2. Cancel")
    if input("Select an option: ").strip() != "1":
        print("Add category canceled. No file was changed.")
        return 1
    try:
        write_tag_bank(path.parents[2], updated, overwrite=True)
    except (TagBankError, OSError) as error:
        print(f"Error: {error}")
        print("Existing tag bank was not changed.")
        return 1
    print(f"Saved tag bank: {path}")
    _prompt_after_category_saved(bank, category)
    return 0


def prompt_add_tag_template() -> int:
    """Add a reusable tag to an existing valid bank."""
    from quillan.menu import print_menu_header

    print_menu_header("Add Reusable Tag")
    selected = _prompt_valid_bank()
    if selected is None:
        return 1
    path, bank = selected
    existing_ids = {
        str(tag["tag_template_id"])
        for tag in bank["tags"]
        if isinstance(tag, dict)
    }
    try:
        tag = _prompt_new_tag_template(
            categories=list(bank["categories"]),
            bank_writing_types=list(bank["writing_types"]),
            existing_ids=existing_ids,
        )
    except (TagBankError, ValueError) as error:
        print(f"Error: {error}")
        print("Add reusable tag canceled. No file was changed.")
        return 1
    if tag is None:
        print("Add reusable tag canceled. No file was changed.")
        return 1
    updated = touch_updated_at(bank)
    updated["tags"] = [dict(item) for item in bank["tags"]] + [tag]
    print()
    print(f"Add reusable tag '{tag['label']}' to {bank['tag_bank_id']}?")
    print("1. Save")
    print("2. Cancel")
    if input("Select an option: ").strip() != "1":
        print("Add reusable tag canceled. No file was changed.")
        return 1
    try:
        write_tag_bank(path.parents[2], updated, overwrite=True)
    except (TagBankError, OSError) as error:
        print(f"Error: {error}")
        print("Existing tag bank was not changed.")
        return 1
    print(f"Saved tag bank: {path}")
    _prompt_after_tag_saved(bank, tag)
    return 0


def prompt_validate_tag_bank() -> int:
    """Validate one existing tag-bank file without modifying it."""
    from quillan.menu import print_menu_header

    print_menu_header("Validate Tag Bank")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    files = list_tag_bank_files(workspace_root)
    if not files:
        print("No tag bank files found.")
        print("Expected location: shared/tag_banks/")
        return 1
    for index, item in enumerate(files, start=1):
        print(f"{index}. {item.path}")
    print("B. Back")
    print()
    selection = input("Select tag bank file: ").strip()
    if selection == "" or selection.casefold() == "b":
        print("Validate tag bank canceled.")
        return 0
    if not selection.isdigit() or not 1 <= int(selection) <= len(files):
        print("Invalid selection. Please choose a listed file or Back.")
        return 1
    path = files[int(selection) - 1].path
    try:
        bank = load_tag_bank(path)
    except (TagBankError, OSError) as error:
        print("Tag bank is invalid.")
        print()
        print(f"Path: {path}")
        print(f"Error: {error}")
        return 1
    print("Tag bank is valid.")
    print()
    print(f"Tag Bank ID: {bank['tag_bank_id']}")
    print(f"Title: {bank['title']}")
    print(f"Categories: {len(bank['categories'])}")
    print(f"Tags: {len(bank['tags'])}")
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
    value = prompt_writing_assignment_types()
    writing_types = parse_comma_separated_values(value)
    if not writing_types:
        raise ValueError("At least one writing assignment type is required.")
    return writing_types


def _prompt_new_category(existing_ids: set[str]) -> dict[str, Any] | None:
    print("Add Category")
    print()
    print("Categories help teachers find tags quickly during review.")
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
            "Example: Teacher observations about procedure, process, method, or steps.\n"
        ).strip()
    else:
        print("Invalid category selection.")
        return None
    suggestion = suggest_identifier(label)
    print_identifier_guidance("category_id", suggestion)
    category_id = input(
        "Press Enter to accept, or type a different category_id: "
    ).strip()
    if not category_id:
        category_id = suggestion
    sort_order = _parse_optional_nonnegative_int(
        prompt_display_order()
    )
    if sort_order is None:
        sort_order = len(existing_ids) + 1
    ensure_unique_identifier(category_id, existing_ids, "category_id")
    return build_tag_category(
        category_id=category_id,
        label=label,
        description=description,
        sort_order=sort_order,
    )


def _prompt_new_tag_template(
    *,
    categories: list[dict[str, Any]],
    bank_writing_types: list[str],
    existing_ids: set[str],
) -> dict[str, Any] | None:
    print()
    print("Add Reusable Tag")
    print()
    label = _required_input("Tag label:\nExample: Explanation needs more detail\n")
    suggestion = suggest_identifier(label)
    print_identifier_guidance("tag_template_id", suggestion)
    tag_template_id = input(
        "Press Enter to accept, or type a different tag_template_id: "
    ).strip()
    if not tag_template_id:
        tag_template_id = suggestion
    ensure_unique_identifier(tag_template_id, existing_ids, "tag_template_id")
    category_id = _prompt_category_id(categories)
    if category_id is None:
        return None
    polarity = _prompt_polarity()
    if polarity is None:
        return None
    metadata = _prompt_optional_metadata(bank_writing_types)
    if metadata is None:
        return None
    return build_tag_template(
        tag_template_id=tag_template_id,
        label=label,
        category_id=category_id,
        polarity=polarity,
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


def _prompt_optional_metadata(bank_writing_types: list[str]) -> dict[str, Any] | None:
    print()
    print("Add optional details for this tag?")
    print()
    print(
        "Optional details can help Quillan sort the tag, link it to standards "
        "or rubric criteria, ask a private note question during review, or "
        "reserve future feedback behavior."
    )
    print()
    print("You can skip these now.")
    print()
    print("1. Add optional details")
    print("2. Skip optional details")
    print("B. Back")
    print()
    response = input("Select an option: ").strip().lower()
    if response in {"", "2", "n", "no"}:
        return {}
    if response not in {"1", "y", "yes"}:
        print("Invalid selection. Optional details canceled.")
        return None
    metadata: dict[str, Any] = {}
    print()
    print("Description helps you remember when to use this tag.")
    print("It is not automatically shown to students.")
    print()
    print("Example:")
    print(
        "Use when the speaker builds credibility through expertise, fairness, "
        "or trustworthiness."
    )
    description = input("Description (leave blank to omit): ").strip()
    if description:
        metadata["description"] = description
    print()
    print("Limit this tag to specific writing assignment types from this tag bank.")
    print("Leave blank if this tag applies to the whole bank.")
    print()
    print("Use lowercase words. For multi-word types, use underscores instead of spaces.")
    print(f"Available writing assignment types: {', '.join(bank_writing_types)}")
    print()
    print("Examples:")
    print("persuasive_speech, argumentative")
    writing_types = parse_comma_separated_values(
        input("Tag writing assignment types, comma-separated (leave blank to omit): ")
    )
    if writing_types:
        outside = set(writing_types) - set(bank_writing_types)
        if outside:
            print(
                "Invalid tag writing types. They must be part of the bank "
                f"writing assignment types: {', '.join(bank_writing_types)}."
            )
            return None
        metadata["writing_types"] = writing_types
    print_standard_ids_help()
    standard_ids = parse_comma_separated_values(
        input("Linked standards (leave blank to omit): ")
    )
    if standard_ids:
        metadata["standard_ids"] = standard_ids
    print_criterion_ids_help()
    criterion_ids = parse_comma_separated_values(
        input("Linked rubric criteria (leave blank to omit): ")
    )
    if criterion_ids:
        metadata["criterion_ids"] = criterion_ids
    print_priority_severity_help()
    severity = _parse_optional_nonnegative_int(
        input("Default priority/severity (leave blank to omit): ")
    )
    if severity is not None:
        metadata["severity_default"] = severity
    print()
    print("Private note question to ask during review (optional)")
    print()
    print("If you enter a question here, Quillan will ask it when you select this tag.")
    print("The teacher's answer is stored as a private note on that tag.")
    print()
    print("Example:")
    print("What makes the speaker seem credible or trustworthy?")
    print()
    teacher_note_prompt = input("Private note question (leave blank to omit): ").strip()
    if teacher_note_prompt:
        metadata["teacher_note_prompt"] = teacher_note_prompt
    sort_order = _parse_optional_nonnegative_int(
        prompt_display_order(within="this category")
    )
    if sort_order is not None:
        metadata["sort_order"] = sort_order
    timestamp = current_timestamp()
    metadata["created_at"] = timestamp
    metadata["updated_at"] = timestamp
    return metadata


def _prompt_after_tag_bank_saved(title: object) -> None:
    print()
    print(f"Tag bank saved: {title}")
    print("Return to the Tag Banks menu to add more categories or reusable tags.")


def _prompt_after_category_saved(
    bank: dict[str, Any], category: dict[str, Any]
) -> None:
    print()
    print(f"Category saved: {category['label']}")
    print("Return to the Tag Banks menu to add more categories or reusable tags.")


def _prompt_after_tag_saved(bank: dict[str, Any], tag: dict[str, Any]) -> None:
    print()
    print(f"Tag saved: {tag['label']}")
    print("Return to the Tag Banks menu to add more categories or reusable tags.")


def _prompt_valid_bank() -> tuple[Path, dict[str, Any]] | None:
    workspace_root = _workspace_root()
    if workspace_root is None:
        return None
    files = list_valid_tag_banks(workspace_root)
    if not files:
        print("No valid shared tag banks found.")
        print(
            "Create one from Review Student Work -> Manage Review Materials "
            "-> Tag Banks -> Create tag bank."
        )
        return None
    print("Available tag banks:")
    for index, item in enumerate(files, start=1):
        assert item.bank is not None
        print(f"{index}. {item.bank['tag_bank_id']} - {item.bank['title']}")
    print("B. Back")
    print()
    selection = input("Select tag bank: ").strip()
    if selection == "" or selection.casefold() == "b":
        print("Tag bank selection canceled.")
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(files):
        item = files[int(selection) - 1]
        assert item.bank is not None
        return item.path, item.bank
    for item in files:
        assert item.bank is not None
        if item.bank["tag_bank_id"] == selection:
            return item.path, item.bank
    print("Invalid tag bank selection. Please choose a listed bank or Back.")
    return None


def _print_categories(bank: dict[str, Any]) -> None:
    print("Existing categories:")
    for index, category in enumerate(bank["categories"], start=1):
        print(f"{index}. {category['category_id']} - {category['label']}")


def _print_invalid_files(invalid: list[Any]) -> None:
    if not invalid:
        return
    print()
    print("Invalid tag bank files:")
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


def _parse_optional_boolean(value: str) -> bool | None:
    text = value.strip().lower()
    if text in {"", "none"}:
        return None
    if text in {"y", "yes", "true", "t", "1"}:
        return True
    if text in {"n", "no", "false", "f", "2"}:
        return False
    raise ValueError("Boolean value must be y/n or blank.")

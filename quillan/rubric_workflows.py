"""Legacy teacher-facing rubric creation and editing workflows.

Retained temporarily for compatibility; not exposed through active v0.8.6 menus.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.authoring_prompt_helpers import (
    print_identifier_guidance,
    print_standard_ids_help,
    prompt_display_order,
    prompt_identifier_with_guidance,
    prompt_writing_assignment_types,
)
from quillan.rubrics import RubricError, load_rubric
from quillan.rubric_writing import (
    build_rubric,
    build_rubric_criterion,
    build_rubric_level,
    ensure_unique_identifier,
    list_rubric_files,
    list_valid_rubrics,
    parse_comma_separated_values,
    summarize_rubric,
    suggest_identifier,
    touch_updated_at,
    write_rubric,
)

_CRITERION_SUGGESTIONS: tuple[tuple[str, str], ...] = (
    ("Content Accuracy", "Score accuracy, completeness, or correctness."),
    ("Evidence / Support", "Score support, examples, sources, or data."),
    ("Reasoning / Explanation", "Score reasoning, analysis, or explanation."),
    ("Organization", "Score structure, sequence, or transitions."),
    ("Process / Method", "Score procedure, process, method, or steps."),
    ("Reflection", "Score reflection, insight, or self-assessment."),
    ("Creativity / Design", "Score design choices or creative decisions."),
    ("Conventions", "Score clarity, mechanics, formatting, or presentation."),
)


def launch_rubrics_menu() -> int:
    """Launch the teacher-facing Rubrics submenu."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Rubrics / Scoring Profiles")
            print(
                "Rubrics and scoring profiles help teachers score prepared "
                "criteria without typing criterion IDs during review."
            )
            print()
            print("1. Create rubric / scoring profile")
            print("2. View rubrics / scoring profiles")
            print("3. Edit rubric / scoring profile")
            print("4. Add criterion")
            print("5. Add level to criterion")
            print("6. Validate rubric / scoring profile")
            print("7. Back")
            print()
            choice = input("Select an option: ").strip()
            print()
            if choice in {"", "7"}:
                return 0
            workflows = {
                "1": prompt_create_rubric,
                "2": prompt_view_rubrics,
                "3": prompt_edit_rubric,
                "4": prompt_add_criterion,
                "5": prompt_add_level,
                "6": prompt_validate_rubric,
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
        print("\nExiting rubrics menu.")
        return 0


def prompt_create_rubric() -> int:
    """Prompt for and save one complete valid rubric."""
    from quillan.menu import print_menu_header

    print_menu_header("Create Rubric / Scoring Profile")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    try:
        title = _required_input(
            "Rubric title:\nExample: General Constructed Response 4-Point Rubric\n"
        )
        suggestion = suggest_identifier(title)
        rubric_id = prompt_identifier_with_guidance("rubric_id", suggestion)
        description = input(
            "Description:\n"
            "Example: Reusable scoring profile for written responses.\n"
        ).strip()
        writing_types = _prompt_writing_types()
        print()
        print("Now add at least one criterion and score level before saving.")
        print()
        criterion = _prompt_new_criterion(existing_ids=set(), criterion_count=0)
        if criterion is None:
            print("Create rubric canceled. No file was created.")
            return 1
        rubric = build_rubric(
            rubric_id=rubric_id,
            title=title,
            description=description,
            writing_types=writing_types,
            criteria=[criterion],
        )
    except (RubricError, ValueError) as error:
        print(f"Error: {error}")
        print("No file was created.")
        return 1

    path = Path(workspace_root) / "shared" / "rubrics" / f"{rubric_id}.json"
    print()
    print("Ready to save rubric / scoring profile:")
    print()
    print(f"Rubric ID: {rubric['rubric_id']}")
    print(f"Title: {rubric['title']}")
    print(f"Writing assignment types: {', '.join(rubric['writing_types'])}")
    print(f"Criteria: {len(rubric['criteria'])}")
    print(f"Levels: {sum(len(item['levels']) for item in rubric['criteria'])}")
    print(f"Path: {path}")
    print()
    print("1. Save")
    print("2. Cancel")
    print()
    if input("Select an option: ").strip() != "1":
        print("Create rubric canceled. No file was created.")
        return 1

    overwrite = False
    if path.exists():
        confirmation = input("Type OVERWRITE to replace it: ").strip()
        if confirmation != "OVERWRITE":
            print("Canceled: existing rubric was not changed.")
            return 1
        overwrite = True
    try:
        saved_path = write_rubric(workspace_root, rubric, overwrite=overwrite)
    except (RubricError, OSError) as error:
        print(f"Error: {error}")
        return 1
    print(f"Saved rubric: {saved_path}")
    return 0


def prompt_view_rubrics() -> int:
    """List rubrics and optionally show one rubric summary."""
    from quillan.menu import print_menu_header

    print_menu_header("Rubrics / Scoring Profiles")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    files = list_rubric_files(workspace_root)
    valid = [item for item in files if item.is_valid and item.rubric is not None]
    invalid = [item for item in files if not item.is_valid]
    if not valid:
        print("No valid shared rubrics found.")
        print()
        print(
            "Create one from Review Student Work -> Manage Review Materials "
            "-> Rubrics / Scoring Profiles -> "
            "Create rubric / scoring profile."
        )
        print()
        print("Expected location:")
        print("shared/rubrics/")
    else:
        print("Rubrics / Scoring Profiles")
        print()
        for index, item in enumerate(valid, start=1):
            rubric = item.rubric
            assert rubric is not None
            criteria = rubric["criteria"]
            levels = sum(len(criterion["levels"]) for criterion in criteria)
            print(f"{index}. {rubric['rubric_id']} - {rubric['title']}")
            print(f"   Writing assignment types: {', '.join(rubric['writing_types'])}")
            print(f"   Criteria: {len(criteria)}")
            print(f"   Levels: {levels}")
            print()
        print("B. Back")
        print()
        selection = input("Select rubric to view, or Back: ").strip()
        if selection.isdigit() and 1 <= int(selection) <= len(valid):
            item = valid[int(selection) - 1]
            assert item.rubric is not None
            print()
            print(summarize_rubric(item.rubric, item.path))
        elif selection and selection.casefold() != "b":
            print("Invalid selection. Please choose a listed rubric or Back.")
    _print_invalid_files(invalid)
    return 0


def prompt_edit_rubric() -> int:
    """Safely edit title, description, or writing types for one valid rubric."""
    from quillan.menu import print_menu_header

    print_menu_header("Edit Rubric / Scoring Profile")
    selected = _prompt_valid_rubric()
    if selected is None:
        return 1
    path, rubric = selected
    print()
    print("1. Edit title")
    print("2. Edit description")
    print("3. Edit writing assignment types")
    print("4. Back")
    print()
    choice = input("Select an option: ").strip()
    if choice in {"", "4"}:
        print("Edit rubric canceled. No file was changed.")
        return 0
    updated = touch_updated_at(rubric)
    try:
        if choice == "1":
            updated["title"] = _required_input("Rubric title: ")
        elif choice == "2":
            updated["description"] = input("Description: ").strip()
        elif choice == "3":
            updated["writing_types"] = _prompt_writing_types()
        else:
            print("Invalid selection. Please enter a number from 1 to 4.")
            return 1
        write_rubric(path.parents[2], updated, overwrite=True)
    except (RubricError, ValueError, OSError) as error:
        print(f"Error: {error}")
        print("Existing rubric was not changed.")
        return 1
    print(f"Saved rubric: {path}")
    return 0


def prompt_add_criterion() -> int:
    """Add a criterion to an existing valid rubric."""
    from quillan.menu import print_menu_header

    print_menu_header("Add Criterion")
    selected = _prompt_valid_rubric()
    if selected is None:
        return 1
    path, rubric = selected
    _print_criteria(rubric)
    existing_ids = {
        str(criterion["criterion_id"])
        for criterion in rubric["criteria"]
        if isinstance(criterion, dict)
    }
    try:
        criterion = _prompt_new_criterion(
            existing_ids=existing_ids,
            criterion_count=len(existing_ids),
        )
    except (RubricError, ValueError) as error:
        print(f"Error: {error}")
        print("Add criterion canceled. No file was changed.")
        return 1
    if criterion is None:
        print("Add criterion canceled. No file was changed.")
        return 1
    updated = touch_updated_at(rubric)
    updated["criteria"] = [dict(item) for item in rubric["criteria"]] + [criterion]
    print()
    print(f"Add criterion '{criterion['label']}' to {rubric['rubric_id']}?")
    print("1. Save")
    print("2. Cancel")
    if input("Select an option: ").strip() != "1":
        print("Add criterion canceled. No file was changed.")
        return 1
    try:
        write_rubric(path.parents[2], updated, overwrite=True)
    except (RubricError, OSError) as error:
        print(f"Error: {error}")
        print("Existing rubric was not changed.")
        return 1
    print(f"Saved rubric: {path}")
    return 0


def prompt_add_level() -> int:
    """Add a score level to an existing rubric criterion."""
    from quillan.menu import print_menu_header

    print_menu_header("Add Level to Criterion")
    selected = _prompt_valid_rubric()
    if selected is None:
        return 1
    path, rubric = selected
    criterion = _prompt_criterion(rubric)
    if criterion is None:
        return 1
    try:
        level = _prompt_new_level(
            max_score=criterion["max_score"],
            existing_scores={level["score"] for level in criterion["levels"]},
            level_count=len(criterion["levels"]),
        )
    except (RubricError, ValueError) as error:
        print(f"Error: {error}")
        print("Add level canceled. No file was changed.")
        return 1
    if level is None:
        print("Add level canceled. No file was changed.")
        return 1
    updated = touch_updated_at(rubric)
    updated_criteria = [dict(item) for item in rubric["criteria"]]
    for item in updated_criteria:
        if item["criterion_id"] == criterion["criterion_id"]:
            item["levels"] = [dict(level_item) for level_item in item["levels"]] + [
                level
            ]
            break
    updated["criteria"] = updated_criteria
    print()
    print(f"Add level '{level['label']}' to {criterion['label']}?")
    print("1. Save")
    print("2. Cancel")
    if input("Select an option: ").strip() != "1":
        print("Add level canceled. No file was changed.")
        return 1
    try:
        write_rubric(path.parents[2], updated, overwrite=True)
    except (RubricError, OSError) as error:
        print(f"Error: {error}")
        print("Existing rubric was not changed.")
        return 1
    print(f"Saved rubric: {path}")
    return 0


def prompt_validate_rubric() -> int:
    """Validate one existing rubric file without modifying it."""
    from quillan.menu import print_menu_header

    print_menu_header("Validate Rubric / Scoring Profile")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    files = list_rubric_files(workspace_root)
    if not files:
        print("No rubric files found.")
        print("Expected location: shared/rubrics/")
        return 1
    for index, item in enumerate(files, start=1):
        print(f"{index}. {item.path}")
    print("B. Back")
    print()
    selection = input("Select rubric file: ").strip()
    if selection == "" or selection.casefold() == "b":
        print("Validate rubric canceled.")
        return 0
    if not selection.isdigit() or not 1 <= int(selection) <= len(files):
        print("Invalid selection. Please choose a listed file or Back.")
        return 1
    path = files[int(selection) - 1].path
    try:
        rubric = load_rubric(path)
    except (RubricError, OSError) as error:
        print("Rubric is invalid.")
        print()
        print(f"Path: {path}")
        print(f"Error: {error}")
        return 1
    print("Rubric is valid.")
    print()
    print(f"Rubric ID: {rubric['rubric_id']}")
    print(f"Title: {rubric['title']}")
    print(f"Criteria: {len(rubric['criteria'])}")
    print(f"Levels: {sum(len(item['levels']) for item in rubric['criteria'])}")
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


def _prompt_new_criterion(
    *,
    existing_ids: set[str],
    criterion_count: int,
) -> dict[str, Any] | None:
    print("Add Criterion")
    print()
    print("Criteria are the parts of student writing you want to score.")
    print()
    print("Suggested criteria:")
    for index, (label, _description) in enumerate(_CRITERION_SUGGESTIONS, start=1):
        print(f"{index}. {label}")
    custom_index = len(_CRITERION_SUGGESTIONS) + 1
    print(f"{custom_index}. Custom criterion")
    print("B. Back")
    print()
    selection = input("Select suggestion or choose Custom: ").strip()
    if selection == "" or selection.casefold() == "b":
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(_CRITERION_SUGGESTIONS):
        label, description = _CRITERION_SUGGESTIONS[int(selection) - 1]
    elif selection == str(custom_index):
        label = _required_input("Criterion label:\nExample: Reasoning / Explanation\n")
        description = input(
            "Description:\n"
            "Example: Score how clearly the response explains its thinking.\n"
        ).strip()
    else:
        print("Invalid criterion selection.")
        return None
    suggestion = suggest_identifier(label)
    print_identifier_guidance("criterion_id", suggestion)
    criterion_id = input(
        "Press Enter to accept, or type a different criterion_id: "
    ).strip()
    if not criterion_id:
        criterion_id = suggestion
    ensure_unique_identifier(criterion_id, existing_ids, "criterion_id")
    max_score = _parse_required_number(input("Max score:\nExample: 4\n"))
    scale = _required_input("Scale:\nExample: 4_point\n")
    print_standard_ids_help()
    standard_ids = parse_comma_separated_values(
        input("Linked standards (leave blank to omit): ")
    )
    sort_order = _parse_optional_nonnegative_int(
        prompt_display_order()
    )
    if sort_order is None:
        sort_order = (criterion_count + 1) * 10
    print()
    print("Add Score Level")
    level = _prompt_new_level(max_score=max_score, existing_scores=set(), level_count=0)
    if level is None:
        return None
    return build_rubric_criterion(
        criterion_id=criterion_id,
        label=label,
        max_score=max_score,
        scale=scale,
        levels=[level],
        description=description,
        standard_ids=standard_ids,
        sort_order=sort_order,
    )


def _prompt_new_level(
    *,
    max_score: int | float,
    existing_scores: set[int | float],
    level_count: int,
) -> dict[str, Any] | None:
    score = _parse_required_number(input("Score:\nExample: 3\n"))
    if score in existing_scores:
        raise RubricError(f"Duplicate level score '{score}'.")
    label = _required_input("Level label:\nExample: Clear explanation\n")
    description = input(
        "Description:\n"
        "Example: The response explains its reasoning clearly with support.\n"
    ).strip()
    student_feedback = input(
        "Student-facing feedback (optional):\n"
        "Example: Your explanation is clear. Add one more specific detail.\n"
    ).strip()
    teacher_note = input("Teacher note (optional, leave blank to omit): ").strip()
    sort_order = _parse_optional_nonnegative_int(
        prompt_display_order(within="this criterion")
    )
    if sort_order is None:
        sort_order = (level_count + 1) * 10
    level = build_rubric_level(
        score=score,
        label=label,
        description=description,
        student_facing_feedback=student_feedback,
        teacher_note=teacher_note,
        sort_order=sort_order,
    )
    probe = build_rubric_criterion(
        criterion_id="temporary_probe",
        label="Temporary Probe",
        max_score=max_score,
        scale="temporary",
        levels=[level],
    )
    # Reuse full criterion validation through a synthetic rubric-shaped build.
    build_rubric(
        rubric_id="temporary_probe",
        title="Temporary Probe",
        description="",
        writing_types=["temporary"],
        criteria=[probe],
    )
    return level


def _prompt_valid_rubric() -> tuple[Path, dict[str, Any]] | None:
    workspace_root = _workspace_root()
    if workspace_root is None:
        return None
    files = list_valid_rubrics(workspace_root)
    if not files:
        print("No valid shared rubrics found.")
        print(
            "Create one from Review Student Work -> Manage Review Materials "
            "-> Rubrics / Scoring Profiles -> "
            "Create rubric / scoring profile."
        )
        return None
    print("Available rubrics / scoring profiles:")
    for index, item in enumerate(files, start=1):
        assert item.rubric is not None
        print(f"{index}. {item.rubric['rubric_id']} - {item.rubric['title']}")
    print("B. Back")
    print()
    selection = input("Select rubric: ").strip()
    if selection == "" or selection.casefold() == "b":
        print("Rubric selection canceled.")
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(files):
        item = files[int(selection) - 1]
        assert item.rubric is not None
        return item.path, item.rubric
    for item in files:
        assert item.rubric is not None
        if item.rubric["rubric_id"] == selection:
            return item.path, item.rubric
    print("Invalid rubric selection. Please choose a listed rubric or Back.")
    return None


def _prompt_criterion(rubric: dict[str, Any]) -> dict[str, Any] | None:
    criteria = _sorted_records(rubric["criteria"])
    print("Criteria:")
    for index, criterion in enumerate(criteria, start=1):
        print(f"{index}. {criterion['label']}")
    print("B. Back")
    print()
    selection = input("Select criterion: ").strip()
    if selection == "" or selection.casefold() == "b":
        print("Criterion selection canceled.")
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(criteria):
        criterion = criteria[int(selection) - 1]
        print()
        print(f"{criterion['label']} levels:")
        for level in _sorted_records(criterion["levels"]):
            print(f"- {level['score']}: {level['label']}")
        return criterion
    print("Invalid criterion selection. Please choose a listed criterion or Back.")
    return None


def _print_criteria(rubric: dict[str, Any]) -> None:
    print("Existing criteria:")
    for index, criterion in enumerate(_sorted_records(rubric["criteria"]), start=1):
        print(f"{index}. {criterion['criterion_id']} - {criterion['label']}")


def _print_invalid_files(invalid: list[Any]) -> None:
    if not invalid:
        return
    print()
    print("Invalid rubric files:")
    print()
    for item in invalid:
        print(f"- {item.path}")
        print(f"  Error: {item.error}")


def _sorted_records(records: list[Any]) -> list[dict[str, Any]]:
    valid = [record for record in records if isinstance(record, dict)]
    return sorted(
        valid,
        key=lambda item: (
            item.get("sort_order")
            if isinstance(item.get("sort_order"), int)
            else 999999,
            str(item.get("label", "")).casefold(),
        ),
    )


def _parse_required_number(value: str) -> int | float:
    text = value.strip()
    if not text:
        raise ValueError("Score value is required.")
    try:
        if "." in text or "e" in text.lower():
            return float(text)
        return int(text)
    except ValueError as error:
        raise ValueError("Score value must be a number.") from error


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

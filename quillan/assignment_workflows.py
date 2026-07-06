"""Teacher-facing workflows for Quillan writing assignment configs."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar

from pds_core.classes import ClassFolder, list_class_folders
from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.standards import StandardsReadError, StandardsValidationError
from pds_core.standards_selection import (
    StandardSelectionItem,
    list_profiles_for_selection,
    list_standards_for_profile_selection,
    load_standards_for_selection,
)
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignments import (
    AssignmentConfigError,
    load_assignment_config,
    validate_assignment_config,
)
from quillan.assignment_picker import prompt_assignment_choice
from quillan.rubrics import RubricError, load_rubric, rubric_path
from quillan.storage import assignment_config_path

_NUMERIC_REQUIREMENTS = (
    "paragraphs_min",
    "paragraphs_max",
    "word_count_min",
    "word_count_max",
)
_DEFAULT_REVIEW_UNIT = {
    "type": "paragraph",
    "singular_label": "paragraph",
    "plural_label": "paragraphs",
}
_DEFAULT_RATING_SCALE = {
    "scale_id": "standards_4_level",
    "levels": [
        {
            "value": 1,
            "label": "Developing",
            "description": (
                "The work shows limited or emerging evidence of the standard."
            ),
        },
        {
            "value": 2,
            "label": "Approaching",
            "description": (
                "The work shows partial evidence of the standard but is uneven, "
                "general, or incomplete."
            ),
        },
        {
            "value": 3,
            "label": "Meeting",
            "description": "The work shows clear and sufficient evidence of the standard.",
        },
        {
            "value": 4,
            "label": "Exceeding",
            "description": (
                "The work shows especially strong, precise, or sophisticated "
                "evidence of the standard."
            ),
        },
    ],
}
_T = TypeVar("_T")


def suggest_assignment_id(title: str) -> str:
    """Suggest a conservative shared identifier from an assignment title."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    suggestion = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_title.strip())
    return suggestion.strip("_-").lower()


def parse_comma_separated_values(value: str) -> list[str]:
    """Return trimmed, nonblank values from comma-separated teacher input."""
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_optional_nonnegative_int(
    value: str,
    field_name: str,
) -> int | None:
    """Parse an optional nonnegative integer requirement."""
    stripped = value.strip()
    if not stripped:
        return None
    try:
        parsed = int(stripped)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a non-negative integer.") from error
    if parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return parsed


def build_assignment_config(
    *,
    assignment_id: str,
    title: str,
    class_id: str,
    writing_type: str,
    student_prompt: str,
    standards_profile_id: str,
    focus_standard_ids: Sequence[str],
    review_unit: Mapping[str, Any],
    rating_scale: Mapping[str, Any],
    basic_requirements: Mapping[str, Any],
    minimum_requirement_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Build and validate a v2 assignment config."""
    assignment: dict[str, Any] = {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": assignment_id,
        "title": title,
        "class_ids": [class_id],
        "writing_type": writing_type,
        "student_prompt": student_prompt,
        "standards_profile_id": standards_profile_id,
        "focus_standard_ids": list(focus_standard_ids),
        "review_unit": dict(review_unit),
        "rating_scale": dict(rating_scale),
        "basic_requirements": dict(basic_requirements),
        "minimum_requirement_policy": dict(minimum_requirement_policy),
    }
    validate_assignment_config(assignment)
    return assignment


def write_assignment_config(
    workspace_root: str | Path,
    class_id: str,
    assignment: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Write a validated assignment config to its canonical shared path."""
    assignment_data = dict(assignment)
    validate_assignment_config(assignment_data)
    if assignment_data["class_ids"] != [class_id]:
        raise AssignmentConfigError(
            "Assignment class_ids must match the selected class_id."
        )
    assignment_id = str(assignment_data["assignment_id"])
    path = assignment_config_path(workspace_root, class_id, assignment_id)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Assignment config already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(assignment_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def format_assignment_summary(
    assignment: Mapping[str, Any],
    assignment_path: str | Path,
    workspace_root: str | Path | None = None,
) -> str:
    """Return a concise human-readable assignment summary."""
    class_ids = ", ".join(str(value) for value in assignment["class_ids"])
    focus_standard_ids = [str(value) for value in assignment["focus_standard_ids"]]
    focus_text = ", ".join(focus_standard_ids)
    review_unit = assignment.get("review_unit", {})
    rating_scale = assignment.get("rating_scale", {})
    lines = [
        f"Assignment path: {Path(assignment_path)}",
        f"Schema version: {assignment['schema_version']}",
        f"Assignment ID: {assignment['assignment_id']}",
        f"Title: {assignment['title']}",
        f"Class IDs: {class_ids}",
        f"Writing type: {assignment['writing_type']}",
        f"Student prompt: {assignment['student_prompt']}",
        f"Standards profile ID: {assignment['standards_profile_id']}",
        f"Focus standard IDs ({len(focus_standard_ids)}): {focus_text}",
    ]
    if isinstance(review_unit, Mapping):
        lines.append(
            "Review unit: "
            f"{review_unit.get('type')} "
            f"({review_unit.get('singular_label')}/"
            f"{review_unit.get('plural_label')})"
        )
    if isinstance(rating_scale, Mapping):
        levels = rating_scale.get("levels")
        if isinstance(levels, Sequence) and not isinstance(levels, (str, bytes)):
            lines.append(
                f"Rating scale: {rating_scale.get('scale_id')} "
                f"({len(levels)} levels)"
            )
            for level in levels:
                if isinstance(level, Mapping):
                    lines.append(
                        "  "
                        f"{level.get('value')}: {level.get('label')} - "
                        f"{level.get('description')}"
                    )
    lines.append(f"Basic requirements: {dict(assignment['basic_requirements'])}")
    policy = assignment["minimum_requirement_policy"]
    lines.append(f"Minimum requirement policy: {dict(policy)}")
    return "\n".join(lines)


def resolve_assignment_rubric(
    workspace_root: str | Path,
    assignment: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Load a valid shared rubric for an assignment, if one resolves."""
    rubric_id = assignment.get("rubric_id")
    if not isinstance(rubric_id, str) or not rubric_id.strip():
        return None
    try:
        return load_rubric(rubric_path(workspace_root, rubric_id))
    except (OSError, RubricError):
        return None


def _workspace_root() -> Path | None:
    try:
        return resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return None


def _available_class_folders(workspace_root: Path) -> tuple[ClassFolder, ...]:
    return list_class_folders(workspace_root, require_roster=True)


def _prompt_class_folder(workspace_root: Path) -> ClassFolder | None:
    folders = _available_class_folders(workspace_root)
    if not folders:
        print("No class rosters found. Create a class roster first.")
        return None

    print("Available classes:")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.class_id}")
    print()
    selection = input("Select class for assignment: ").strip()
    if selection.isdigit() and 1 <= int(selection) <= len(folders):
        return folders[int(selection) - 1]
    for folder in folders:
        if folder.class_id == selection:
            return folder
    print(f"Error: Class not found: {selection}")
    return None


def _required_input(prompt: str, field_name: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError(f"{field_name} is required.")
    return value


def _prompt_basic_requirements() -> dict[str, Any]:
    requirements: dict[str, Any] = {}
    print(
        "Basic requirements (leave blank to omit). These are teacher-entered "
        "requirements, not automatic analysis."
    )
    for field_name in _NUMERIC_REQUIREMENTS:
        parsed = parse_optional_nonnegative_int(
            input(f"  {field_name}: "),
            field_name,
        )
        if parsed is not None:
            requirements[field_name] = parsed
    required_elements = parse_comma_separated_values(
        input("  required_elements, comma-separated: ")
    )
    if required_elements:
        requirements["required_elements"] = required_elements
    return requirements


def _prompt_numbered_selection(
    items: Sequence[_T],
    *,
    prompt: str,
    label: str,
) -> _T | None:
    selection = input(prompt).strip()
    if selection.isdigit() and 1 <= int(selection) <= len(items):
        return items[int(selection) - 1]
    print(f"Error: {label} not found: {selection}")
    return None


def _prompt_standards_selection(
    workspace_root: Path,
) -> tuple[str, list[str]] | None:
    try:
        library = load_standards_for_selection(workspace_root)
    except (OSError, StandardsReadError, StandardsValidationError) as error:
        print(f"Error: could not load pds-core standards library: {error}")
        return None

    profiles = list_profiles_for_selection(library)
    if not profiles:
        print(
            "No pds-core standards profiles found. Create or import standards "
            "through pds-core first."
        )
        return None

    print("Available standards profiles:")
    for index, profile in enumerate(profiles, start=1):
        print(f"{index}. {profile.label}")
    print()
    selected_profile = _prompt_numbered_selection(
        profiles,
        prompt="Select standards profile: ",
        label="standards profile",
    )
    if selected_profile is None:
        return None

    try:
        standards = list_standards_for_profile_selection(
            library,
            selected_profile.profile_id,
        )
    except StandardsValidationError as error:
        print(f"Error: could not list profile standards: {error}")
        return None
    if not standards:
        print(
            "Selected pds-core standards profile has no standards available "
            "for Quillan."
        )
        return None

    print("Available standards:")
    for index, standard in enumerate(standards, start=1):
        print(f"{index}. {standard.label}")
    print()
    selected_standards = _prompt_focus_standards(standards)
    if selected_standards is None:
        return None
    return selected_profile.profile_id, selected_standards


def _prompt_focus_standards(
    standards: Sequence[StandardSelectionItem],
) -> list[str] | None:
    selection = input("Select Focus Standards by number, comma-separated: ").strip()
    if not selection:
        print("Error: at least one Focus Standard is required.")
        return None
    selected_ids: list[str] = []
    seen: set[str] = set()
    for item in parse_comma_separated_values(selection):
        if not item.isdigit() or not 1 <= int(item) <= len(standards):
            print(f"Error: focus standard selection not found: {item}")
            return None
        standard_id = standards[int(item) - 1].standard_id
        if standard_id in seen:
            print(f"Error: duplicate focus standard selection: {item}")
            return None
        seen.add(standard_id)
        selected_ids.append(standard_id)
    return selected_ids


def prompt_create_assignment() -> int:
    """Prompt for and write one validated writing assignment config."""
    from quillan.menu import print_menu_header

    print_menu_header("Create Writing Assignment")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    class_folder = _prompt_class_folder(workspace_root)
    if class_folder is None:
        return 1

    try:
        title = _required_input("Assignment title: ", "assignment title")
        suggested_id = suggest_assignment_id(title)
        if not suggested_id:
            raise ValueError("assignment_id could not be suggested from title.")
        print(f"Suggested assignment ID: {suggested_id}")
        assignment_id = input("Assignment ID [press Enter to accept]: ").strip()
        if not assignment_id:
            assignment_id = suggested_id
        validate_identifier(assignment_id, "assignment_id")

        writing_type = _required_input("Writing type: ", "writing type")
        student_prompt = _prompt_student_prompt()
        standards_selection = _prompt_standards_selection(workspace_root)
        if standards_selection is None:
            return 1
        standards_profile_id, focus_standard_ids = standards_selection
        review_unit = _prompt_review_unit()
        rating_scale = _prompt_rating_scale()
        basic_requirements = _prompt_basic_requirements()
        minimum_requirement_policy = _prompt_minimum_requirement_policy()

        assignment = build_assignment_config(
            assignment_id=assignment_id,
            title=title,
            class_id=class_folder.class_id,
            writing_type=writing_type,
            student_prompt=student_prompt,
            standards_profile_id=standards_profile_id,
            focus_standard_ids=focus_standard_ids,
            review_unit=review_unit,
            rating_scale=rating_scale,
            basic_requirements=basic_requirements,
            minimum_requirement_policy=minimum_requirement_policy,
        )
    except (AssignmentConfigError, IdentifierValidationError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    output_path = assignment_config_path(
        workspace_root,
        class_folder.class_id,
        assignment_id,
    )
    print()
    print("Review assignment config before saving:")
    print(format_assignment_summary(assignment, output_path, workspace_root))
    if not _prompt_yes_no("Save this assignment? [Y/n]: ", default=True):
        print("Canceled: assignment was not saved.")
        return 0

    overwrite = False
    if output_path.exists():
        print(f"Assignment config already exists: {output_path}")
        confirmation = input("Type OVERWRITE to replace it: ").strip()
        if confirmation != "OVERWRITE":
            print("Canceled: existing assignment was not changed.")
            return 1
        overwrite = True

    try:
        saved_path = write_assignment_config(
            workspace_root,
            class_folder.class_id,
            assignment,
            overwrite=overwrite,
        )
    except (AssignmentConfigError, OSError, FileExistsError) as error:
        print(f"Error: {error}")
        return 1
    print(f"Saved assignment: {saved_path}")
    return 0


def _prompt_yes_no(prompt: str, *, default: bool) -> bool:
    response = input(prompt).strip().lower()
    if not response:
        return default
    return response in {"y", "yes"}


def _prompt_student_prompt() -> str:
    return _required_input(
        "Student-facing assignment prompt: ",
        "student-facing assignment prompt",
    )


def _default_review_unit() -> dict[str, str]:
    return dict(_DEFAULT_REVIEW_UNIT)


def _prompt_review_unit() -> dict[str, str]:
    print(
        "Review units are the chunks of student writing the teacher may review "
        "later."
    )
    if _prompt_yes_no("Use default paragraph review units? [Y/n]: ", default=True):
        return _default_review_unit()
    return {
        "type": _required_input("Review-unit type: ", "review-unit type"),
        "singular_label": _required_input(
            "Review-unit singular label: ",
            "review-unit singular label",
        ),
        "plural_label": _required_input(
            "Review-unit plural label: ",
            "review-unit plural label",
        ),
    }


def _default_rating_scale() -> dict[str, Any]:
    return {
        "scale_id": _DEFAULT_RATING_SCALE["scale_id"],
        "levels": [dict(level) for level in _DEFAULT_RATING_SCALE["levels"]],
    }


def _prompt_rating_scale() -> dict[str, Any]:
    print("Rating scale for standards-based review:")
    if _prompt_yes_no("Use default four-level standards scale? [Y/n]: ", default=True):
        return _default_rating_scale()

    scale_id = _required_input("Rating scale ID: ", "rating scale ID")
    level_count = parse_optional_nonnegative_int(
        input("Number of rating levels: "),
        "number of rating levels",
    )
    if level_count is None or level_count <= 0:
        raise ValueError("number of rating levels must be a positive integer.")

    levels: list[dict[str, Any]] = []
    for index in range(1, level_count + 1):
        print(f"Rating level {index}:")
        value = parse_optional_nonnegative_int(
            input("  value: "),
            "rating level value",
        )
        if value is None:
            raise ValueError("rating level value is required.")
        levels.append(
            {
                "value": value,
                "label": _required_input("  label: ", "rating level label"),
                "description": _required_input(
                    "  description: ",
                    "rating level description",
                ),
            }
        )
    return {"scale_id": scale_id, "levels": levels}


def _prompt_minimum_requirement_policy() -> dict[str, bool]:
    allow_return = _prompt_yes_no(
        "Allow teacher to return work without full standards review if minimum "
        "requirements are unmet? [Y/n]: ",
        default=True,
    )
    return {"allow_return_without_full_review": allow_return}


def _normalize_path_input(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "'\"":
        return stripped[1:-1]
    return stripped


def prompt_view_validate_assignment() -> int:
    """Select, load, validate, and summarize a canonical assignment config."""
    from quillan.menu import print_menu_header

    print_menu_header("View/Validate Assignment")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    choice = prompt_assignment_choice(workspace_root)
    if choice is None:
        return 0
    try:
        assignment = load_assignment_config(choice.path)
    except (AssignmentConfigError, OSError) as error:
        print(f"Error: {error}")
        return 1
    print("Assignment config is valid.")
    print(format_assignment_summary(assignment, choice.path, workspace_root))
    return 0


def launch_assignment_menu() -> int:
    """Launch the teacher-facing assignment management submenu."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Assignment Management")
            print("1. Create writing assignment")
            print("2. View/validate assignment")
            print("3. Printable Response Pages")
            print("4. Back")
            print()
            choice = input("Select an option: ").strip()
            print()

            if choice == "4":
                return 0
            workflows = {
                "1": prompt_create_assignment,
                "2": prompt_view_validate_assignment,
            }
            workflow = workflows.get(choice)
            if choice == "3":
                from quillan.printable_response_workflows import (
                    launch_printable_response_menu,
                )

                launch_printable_response_menu()
            elif workflow is None:
                print("Invalid selection. Please enter a number from 1 to 4.")
            else:
                clear_screen()
                workflow()
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting assignment menu.")
        return 0

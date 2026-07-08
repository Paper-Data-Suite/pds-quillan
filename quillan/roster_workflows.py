"""Teacher-facing workflows for shared Paper Data Suite class rosters."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path

from pds_core.classes import (
    ClassFolder,
    list_class_folders,
    load_class_roster,
    write_class_roster,
)
from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.rosters import (
    ROSTER_REQUIRED_COLUMNS,
    Roster,
    RosterError,
    RosterValidationError,
    StudentRecord,
    add_student_record,
    create_roster,
    load_roster,
    remove_student_record,
    replace_student_record,
)
from pds_core.routes import class_roster_path
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

_REQUIRED_STUDENT_FIELDS = ("student_id", "last_name", "first_name", "period")


def optional_roster_columns(roster: Roster) -> tuple[str, ...]:
    """Return existing optional columns in their shared-roster order."""
    return tuple(
        column for column in roster.columns if column not in ROSTER_REQUIRED_COLUMNS
    )


def shared_roster_period(roster: Roster) -> str | None:
    """Return the shared nonblank student period when it is unambiguous."""
    periods = [student.period.strip() for student in roster.students]
    if not periods or any(not period for period in periods):
        return None
    unique_periods = set(periods)
    return next(iter(unique_periods)) if len(unique_periods) == 1 else None


def format_roster_for_display(roster: Roster, roster_path: str | Path) -> str:
    """Return a readable roster summary including all roster columns."""
    columns = tuple(
        column for column in roster.columns if column != "class_id"
    )
    rows = [
        {
            "student_id": student.student_id,
            "last_name": student.last_name,
            "first_name": student.first_name,
            "period": student.period,
            **student.extra_fields,
        }
        for student in roster.students
    ]
    widths = {
        column: max(
            len(column),
            *(len(row.get(column, "")) for row in rows),
        )
        for column in columns
    }
    lines = [
        f"Class ID: {roster.class_id}",
        f"Roster path: {Path(roster_path)}",
        f"Student count: {len(roster.students)}",
        "",
        "  ".join(column.ljust(widths[column]) for column in columns),
    ]
    lines.extend(
        "  ".join(row.get(column, "").ljust(widths[column]) for column in columns)
        for row in rows
    )
    return "\n".join(lines)


def student_record_from_values(
    roster: Roster,
    student_id: str,
    values: Mapping[str, str],
) -> StudentRecord:
    """Build a student record while preserving the roster's optional schema."""
    return StudentRecord(
        class_id=roster.class_id,
        student_id=student_id.strip(),
        last_name=values["last_name"].strip(),
        first_name=values["first_name"].strip(),
        period=values["period"].strip(),
        extra_fields={
            column: values.get(column, "").strip()
            for column in optional_roster_columns(roster)
        },
    )


def create_class_roster(
    workspace_root: str | Path,
    class_id: str,
    students: Sequence[Mapping[str, str]],
    *,
    overwrite: bool = False,
) -> tuple[Roster, Path]:
    """Create and write a validated roster at its canonical shared path."""
    roster = create_roster(class_id, students)
    path = write_class_roster(workspace_root, roster, overwrite=overwrite)
    return roster, path


def validate_roster_file(path: str | Path) -> Roster:
    """Load an explicit roster path through shared validation without writing."""
    return load_roster(path)


def print_roster_validation_error(error: Exception) -> None:
    """Print expected shared roster errors without a traceback."""
    print(f"Error: {error}")
    if isinstance(error, RosterValidationError):
        for issue in error.issues:
            location: list[str] = []
            if issue.row_number is not None:
                location.append(f"row {issue.row_number}")
            if issue.column:
                location.append(f"column {issue.column}")
            prefix = f"  {' / '.join(location)}: " if location else "  "
            print(f"{prefix}[{issue.code}] {issue.message}")


def suggest_class_id(class_label: str) -> str:
    """Suggest a conservative shared identifier from a teacher-facing label."""
    normalized = unicodedata.normalize("NFKD", class_label)
    ascii_label = normalized.encode("ascii", "ignore").decode("ascii")
    suggestion = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_label.strip())
    return suggestion.strip("_-").lower()


def _workspace_root() -> Path | None:
    try:
        return resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return None


def _available_class_folders(workspace_root: Path) -> tuple[ClassFolder, ...]:
    return list_class_folders(workspace_root, require_roster=True)


def _prompt_class_folder(
    workspace_root: Path,
    action: str,
) -> ClassFolder | None:
    folders = _available_class_folders(workspace_root)
    if not folders:
        print("No class rosters found.")
        print("Create a class roster first, then return to this option.")
        return None

    print("Available classes:")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.class_id}")
    from quillan.menu_navigation import (
        NavigationChoice,
        parse_navigation_choice,
        print_navigation_options,
    )

    print_navigation_options()
    print()
    selection = input(f"Select class to {action}: ").strip()
    navigation = parse_navigation_choice(selection)
    if selection == "" or navigation is NavigationChoice.BACK:
        return None
    if selection.isdigit() and 1 <= int(selection) <= len(folders):
        return folders[int(selection) - 1]
    for folder in folders:
        if folder.class_id == selection:
            return folder
    print(f"Error: Class not found: {selection}")
    return None


def _prompt_required(field_name: str, *, default: str | None = None) -> str:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"  {field_name}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        print(f"  Error: {field_name} is required.")


def _print_student_choices(roster: Roster) -> None:
    for index, student in enumerate(roster.students, start=1):
        print(
            f"{index}. {student.student_id} - "
            f"{student.last_name}, {student.first_name} "
            f"(period {student.period})"
        )


def prompt_student_selection(roster: Roster, prompt: str) -> StudentRecord:
    """Select a student by visible number or exact string student ID."""
    selection = input(prompt).strip()
    if selection.isdigit():
        index = int(selection)
        if 1 <= index <= len(roster.students):
            return roster.students[index - 1]
    for student in roster.students:
        if student.student_id == selection:
            return student
    raise ValueError(f"Student not found: {selection}")


def prompt_add_student_to_roster(roster: Roster) -> Roster:
    """Prompt for and stage one shared roster addition."""
    print("Add student")
    values = {
        field: _prompt_required(field)
        for field in _REQUIRED_STUDENT_FIELDS
        if field != "period"
    }
    values["period"] = _prompt_required(
        "period",
        default=shared_roster_period(roster),
    )
    for column in optional_roster_columns(roster):
        values[column] = input(f"  {column} (optional): ").strip()
    student = student_record_from_values(roster, values["student_id"], values)
    return add_student_record(roster, student)


def prompt_edit_student_in_roster(roster: Roster) -> Roster:
    """Prompt for and stage replacement of one stable student identity."""
    print("Edit student")
    _print_student_choices(roster)
    student = prompt_student_selection(
        roster,
        "Select student by number or student_id: ",
    )
    print(f"student_id: {student.student_id} (cannot be changed)")
    print("Press Enter to keep the current value.")
    values = {
        "last_name": _prompt_required("last_name", default=student.last_name),
        "first_name": _prompt_required("first_name", default=student.first_name),
        "period": _prompt_required("period", default=student.period),
    }
    for column in optional_roster_columns(roster):
        current = student.extra_fields.get(column, "")
        entered = input(f"  {column} [{current}]: ").strip()
        values[column] = entered or current
    replacement = student_record_from_values(roster, student.student_id, values)
    return replace_student_record(roster, replacement)


def prompt_remove_student_from_roster(roster: Roster) -> Roster:
    """Prompt for and stage active-roster removal only."""
    print("Remove student from active roster")
    _print_student_choices(roster)
    student = prompt_student_selection(
        roster,
        "Select student by number or student_id: ",
    )
    print(
        f"Selected: {student.student_id} - "
        f"{student.last_name}, {student.first_name} "
        f"(period {student.period})"
    )
    print(
        "Removing a student from the active roster does not delete assignments, "
        "submissions, printable PDFs, scans, reports, tags, scores, feedback, "
        "or historical evidence."
    )
    confirmation = input("Type REMOVE to remove from active roster: ").strip()
    if confirmation != "REMOVE":
        print("Canceled: removal not confirmed.")
        return roster
    return remove_student_record(roster, student.student_id)


def _print_roster_action_header(title: str) -> None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header(title)


def _print_roster_edit_dashboard(
    roster: Roster,
    *,
    dirty: bool,
    last_status: str | None = None,
) -> None:
    _print_roster_action_header("Edit Class Roster")
    print(f"Class ID: {roster.class_id}")
    print(f"Student count: {len(roster.students)}")
    print(f"Unsaved changes: {'yes' if dirty else 'no'}")
    if last_status is not None:
        print(f"Last action: {last_status}")
    print()
    print("1. Add student")
    print("2. Edit student")
    print("3. Remove student from active roster")
    print("4. View current roster")
    print("5. Save changes")
    from quillan.menu_navigation import print_navigation_options

    print_navigation_options()
    print()


def prompt_create_roster() -> int:
    """Create a canonical shared class roster from teacher prompts."""
    from quillan.menu import print_menu_header

    print_menu_header("Create Class Roster")
    class_label = input("Class name or label: ").strip()
    if not class_label:
        print("Error: class name or label is required.")
        return 1

    suggestion = suggest_class_id(class_label)
    if suggestion:
        print(f"Suggested class_id: {suggestion}")
        class_id = input(
            "Press Enter to accept, or type a different class_id: "
        ).strip() or suggestion
    else:
        class_id = input("Enter class_id: ").strip()

    try:
        validate_identifier(class_id, "class_id")
    except IdentifierValidationError as error:
        print(f"Error: {error}")
        return 1

    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    output_path = class_roster_path(workspace_root, class_id)
    overwrite = False
    if output_path.exists():
        print(f"Roster already exists for class '{class_id}':")
        print(output_path)
        confirmation = input("Type OVERWRITE to replace it: ").strip()
        if confirmation != "OVERWRITE":
            print("Canceled: existing roster was not changed.")
            return 1
        overwrite = True

    period = _prompt_required("period")
    students: list[dict[str, str]] = []
    print()
    print("Enter students one at a time.")
    while True:
        print(f"Student #{len(students) + 1}:")
        student_id = input("  student_id (blank when finished): ").strip()
        if not student_id:
            if not students:
                print("  Error: at least one student is required.")
                continue
            break
        last_name = _prompt_required("last_name")
        first_name = _prompt_required("first_name")
        students.append(
            {
                "student_id": student_id,
                "last_name": last_name,
                "first_name": first_name,
                "period": period,
            }
        )
        print(f"  Staged: {student_id} - {last_name}, {first_name}")

    try:
        roster, saved_path = create_class_roster(
            workspace_root,
            class_id,
            students,
            overwrite=overwrite,
        )
    except RosterError as error:
        print_roster_validation_error(error)
        return 1
    print(f"Created roster with {len(roster.students)} students:")
    print(saved_path)
    return 0


def prompt_view_roster() -> int:
    """Display one canonical class roster without modifying it."""
    from quillan.menu import print_menu_header

    print_menu_header("View Class Roster")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    folder = _prompt_class_folder(workspace_root, "view")
    if folder is None:
        return 1
    try:
        roster = load_class_roster(workspace_root, folder.class_id)
    except RosterError as error:
        print_roster_validation_error(error)
        return 1
    print()
    print(format_roster_for_display(roster, folder.roster_path))
    return 0


def prompt_edit_class_roster() -> int:
    """Stage roster mutations and write only after explicit SAVE."""
    _print_roster_action_header("Edit Class Roster")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    folder = _prompt_class_folder(workspace_root, "edit")
    if folder is None:
        return 1
    try:
        staged_roster = load_class_roster(workspace_root, folder.class_id)
    except RosterError as error:
        print_roster_validation_error(error)
        return 1

    dirty = False
    last_status: str | None = None
    from quillan.menu_navigation import (
        NavigationChoice,
        QuitQuillan,
        ReturnToMainMenu,
        parse_navigation_choice,
    )

    def confirm_dirty_navigation(error: Exception) -> None:
        if not dirty:
            raise error
        destination = (
            "Main Menu" if isinstance(error, ReturnToMainMenu) else "quit Quillan"
        )
        _print_roster_action_header("Discard Roster Changes")
        print("Unsaved roster changes will be discarded.")
        print()
        confirmation = input(f"Type DISCARD to {destination}: ").strip()
        if confirmation == "DISCARD":
            raise error

    while True:
        _print_roster_edit_dashboard(
            staged_roster,
            dirty=dirty,
            last_status=last_status,
        )
        last_status = None
        choice = input("Select an option: ").strip()
        print()

        try:
            try:
                navigation = parse_navigation_choice(choice)
            except (ReturnToMainMenu, QuitQuillan) as error:
                confirm_dirty_navigation(error)
                last_status = "discard not confirmed"
                continue
            if navigation is NavigationChoice.BACK:
                choice = "6"
            if choice == "1":
                _print_roster_action_header("Add Student")
                staged_roster = prompt_add_student_to_roster(staged_roster)
                dirty = True
                last_status = "student added"
            elif choice == "2":
                _print_roster_action_header("Edit Student")
                staged_roster = prompt_edit_student_in_roster(staged_roster)
                dirty = True
                last_status = "student updated"
            elif choice == "3":
                _print_roster_action_header("Remove Student")
                updated = prompt_remove_student_from_roster(staged_roster)
                if updated is not staged_roster:
                    staged_roster = updated
                    dirty = True
                    last_status = "student removed from active roster"
                else:
                    last_status = "student removal canceled"
            elif choice == "4":
                _print_roster_action_header("Current Roster")
                print(format_roster_for_display(staged_roster, folder.roster_path))
                if dirty:
                    print("\nUnsaved staged changes are shown above.")
                print()
                input("Press Enter to return to edit menu...")
            elif choice == "5":
                if not dirty:
                    print("No changes to save.")
                    return 0
                _print_roster_action_header("Save Roster Changes")
                print(f"Class ID: {staged_roster.class_id}")
                print(f"Student count: {len(staged_roster.students)}")
                print()
                confirmation = input(
                    "Type SAVE to write staged changes: "
                ).strip()
                if confirmation != "SAVE":
                    last_status = "save not confirmed"
                    continue
                saved_path = write_class_roster(
                    workspace_root,
                    staged_roster,
                    overwrite=True,
                )
                print(f"Saved roster: {saved_path}")
                return 0
            elif choice == "6":
                if dirty:
                    _print_roster_action_header("Discard Roster Changes")
                    print(f"Class ID: {staged_roster.class_id}")
                    print(f"Student count: {len(staged_roster.students)}")
                    print()
                    confirmation = input(
                        "Type DISCARD to discard staged changes: "
                    ).strip()
                    if confirmation != "DISCARD":
                        last_status = "discard not confirmed"
                        continue
                print("Canceled: no roster changes were saved.")
                return 0
            else:
                last_status = "invalid selection"
        except (RosterError, ValueError) as error:
            print_roster_validation_error(error)
            last_status = "action failed"


def _normalize_path_input(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "'\"":
        return stripped[1:-1]
    return stripped


def prompt_validate_roster() -> int:
    """Validate an explicit roster CSV without rewriting it."""
    from quillan.menu import print_menu_header

    print_menu_header("Validate Class Roster")
    roster_path = _normalize_path_input(input("Roster CSV path: "))
    if not roster_path:
        print("Error: roster CSV path is required.")
        return 1
    try:
        roster = validate_roster_file(roster_path)
    except RosterError as error:
        print_roster_validation_error(error)
        return 1
    print("Roster file is valid.")
    print(f"Class ID: {roster.class_id}")
    print(f"Student count: {len(roster.students)}")
    print("First students:")
    for student in roster.students[:5]:
        print(
            f"  {student.student_id}: "
            f"{student.last_name}, {student.first_name}"
        )
    return 0


def launch_roster_menu() -> int:
    """Launch the teacher-facing roster management submenu."""
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
            print_menu_header("Roster Management")
            print("1. Create class roster")
            print("2. View class roster")
            print("3. Edit class roster")
            print("4. Validate class roster")
            print_navigation_options()
            print()
            choice = input("Select an option: ").strip()
            navigation = parse_navigation_choice(choice)
            print()

            if choice == "5" or navigation is NavigationChoice.BACK:
                return 0
            workflows = {
                "1": prompt_create_roster,
                "2": prompt_view_roster,
                "3": prompt_edit_class_roster,
                "4": prompt_validate_roster,
            }
            workflow = workflows.get(choice)
            if workflow is None:
                print(f"Invalid selection. {navigation_hint()}")
            else:
                clear_screen()
                workflow()
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting roster menu.")
        return 0

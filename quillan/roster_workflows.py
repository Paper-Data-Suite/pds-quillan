"""Teacher-facing workflows for shared Paper Data Suite class rosters."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path

from pds_core.class_metadata import (
    ClassMetadata,
    ClassMetadataError,
    class_metadata_path,
    load_class_metadata_for_class,
)
from pds_core.classes import (
    ClassFolder,
    list_class_folders,
    load_class_roster,
    write_class_roster,
)
from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.rosters import (
    Roster,
    RosterError,
    RosterValidationError,
    StudentRecord,
    load_roster,
)
from pds_core.routes import class_roster_path
from pds_core.school_years import (
    SchoolYearStateError,
    SchoolYearValidationError,
    get_active_school_year,
    validate_school_year,
)
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.roster_management import (
    add_student_to_roster,
    optional_roster_columns as managed_optional_roster_columns,
    plan_roster_creation_from_values,
    remove_student_from_roster,
    student_record_from_values as managed_student_record_from_values,
    update_student_in_roster,
    write_roster_creation,
)

_REQUIRED_STUDENT_FIELDS = ("student_id", "last_name", "first_name", "period")


def optional_roster_columns(roster: Roster) -> tuple[str, ...]:
    """Return existing optional columns in their shared-roster order."""
    return managed_optional_roster_columns(roster)


def shared_roster_period(roster: Roster) -> str | None:
    """Return the shared nonblank student period when it is unambiguous."""
    periods = [student.period.strip() for student in roster.students]
    if not periods or any(not period for period in periods):
        return None
    unique_periods = set(periods)
    return next(iter(unique_periods)) if len(unique_periods) == 1 else None


def _metadata_school_year_label(
    metadata: ClassMetadata | None,
    metadata_error: Exception | None,
) -> str:
    if metadata is not None:
        return metadata.school_year
    if metadata_error is not None:
        return "metadata error"
    return "not set"


def format_roster_for_display(
    roster: Roster,
    roster_path: str | Path,
    *,
    metadata: ClassMetadata | None = None,
    metadata_path: str | Path | None = None,
    metadata_error: Exception | None = None,
) -> str:
    """Return a readable roster summary including all roster columns."""
    roster_display_path = Path(roster_path)
    metadata_display_path = (
        roster_display_path.with_name("class.json")
        if metadata_path is None
        else Path(metadata_path)
    )
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
        f"School year: {_metadata_school_year_label(metadata, metadata_error)}",
        f"Roster path: {roster_display_path}",
        f"Class metadata path: {metadata_display_path}",
        f"Student count: {len(roster.students)}",
    ]
    if metadata_error is not None:
        lines.append(f"Metadata error: {metadata_error}")
    lines.extend(
        [
            "",
            "  ".join(column.ljust(widths[column]) for column in columns),
        ]
    )
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
    return managed_student_record_from_values(roster, student_id, values)


def create_class_roster(
    workspace_root: str | Path,
    class_id: str,
    students: Sequence[Mapping[str, str]],
    *,
    school_year: str,
    overwrite: bool = False,
) -> tuple[Roster, Path, ClassMetadata, Path]:
    """Create and write validated roster and metadata artifacts."""
    plan = plan_roster_creation_from_values(
        workspace_root, class_id, students, school_year=school_year
    )
    path, metadata_path = write_roster_creation(plan, overwrite=overwrite)
    return plan.roster, path, plan.metadata, metadata_path


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


def _load_optional_class_metadata(
    workspace_root: Path,
    class_id: str,
) -> tuple[ClassMetadata | None, Exception | None]:
    metadata_path = class_metadata_path(workspace_root, class_id)
    if not metadata_path.is_file():
        return None, None
    try:
        return load_class_metadata_for_class(workspace_root, class_id), None
    except ClassMetadataError as error:
        return None, error


def _prompt_school_year(workspace_root: Path) -> str | None:
    try:
        active_school_year = get_active_school_year(workspace_root)
    except SchoolYearStateError as error:
        print(f"Warning: could not read active school year: {error}")
        active_school_year = None

    if active_school_year is not None:
        print(f"Active school year: {active_school_year}")
        use_active = input("Use this school year for the class roster? [Y/n]: ")
        if use_active.strip().casefold() not in {"n", "no"}:
            return active_school_year
    else:
        print("No active school year is open for this workspace.")

    entered = input("School year for this roster (YYYY-YYYY): ").strip()
    try:
        return validate_school_year(entered)
    except SchoolYearValidationError as error:
        print(f"Error: {error}")
        return None


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
    return add_student_to_roster(roster, student)


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
    return update_student_in_roster(roster, replacement)


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
    return remove_student_from_roster(roster, student.student_id)


def _print_roster_action_header(title: str) -> None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header(title)


def _print_roster_edit_dashboard(
    roster: Roster,
    *,
    school_year_label: str,
    dirty: bool,
    last_status: str | None = None,
) -> None:
    _print_roster_action_header("Edit Class Roster")
    print(f"Class ID: {roster.class_id}")
    print(f"School year: {school_year_label}")
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
    school_year = _prompt_school_year(workspace_root)
    if school_year is None:
        return 1
    output_path = class_roster_path(workspace_root, class_id)
    output_metadata_path = class_metadata_path(workspace_root, class_id)
    overwrite = False
    if output_path.exists() or output_metadata_path.exists():
        if output_path.exists():
            print(f"Roster already exists for class '{class_id}':")
            print(output_path)
        if output_metadata_path.exists():
            if output_path.exists():
                print()
            print("Class metadata already exists:")
            print(output_metadata_path)
        confirmation = input(
            "Type OVERWRITE to replace the roster and class metadata: "
        ).strip()
        if confirmation != "OVERWRITE":
            print("Canceled: existing roster and class metadata were not changed.")
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
        roster, saved_path, _metadata, saved_metadata_path = create_class_roster(
            workspace_root,
            class_id,
            students,
            school_year=school_year,
            overwrite=overwrite,
        )
    except (RosterError, ClassMetadataError, SchoolYearValidationError) as error:
        print_roster_validation_error(error)
        return 1
    print(f"Created roster with {len(roster.students)} students:")
    print(saved_path)
    print(f"Created class metadata: {saved_metadata_path}")
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
    metadata, metadata_error = _load_optional_class_metadata(
        workspace_root,
        folder.class_id,
    )
    print()
    print(
        format_roster_for_display(
            roster,
            folder.roster_path.relative_to(workspace_root).as_posix(),
            metadata=metadata,
            metadata_path=folder.metadata_path.relative_to(workspace_root).as_posix(),
            metadata_error=metadata_error,
        )
    )
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
    metadata, metadata_error = _load_optional_class_metadata(
        workspace_root,
        folder.class_id,
    )

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
            school_year_label=_metadata_school_year_label(metadata, metadata_error),
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
                print(
                    format_roster_for_display(
                        staged_roster,
                        folder.roster_path.relative_to(workspace_root).as_posix(),
                        metadata=metadata,
                        metadata_path=(
                            folder.metadata_path.relative_to(workspace_root).as_posix()
                        ),
                        metadata_error=metadata_error,
                    )
                )
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


def _print_roster_validation_summary(
    roster: Roster,
    roster_path: str | Path,
    *,
    metadata: ClassMetadata | None = None,
    metadata_error: Exception | None = None,
    include_metadata: bool = False,
) -> None:
    print("Roster file is valid.")
    print(f"Class ID: {roster.class_id}")
    if include_metadata:
        print(f"School year: {_metadata_school_year_label(metadata, metadata_error)}")
        if metadata_error is not None:
            print(f"Metadata error: {metadata_error}")
    print(f"Roster path: {Path(roster_path)}")
    print(f"Student count: {len(roster.students)}")
    print("First students:")
    for student in roster.students[:5]:
        print(
            f"  {student.student_id}: "
            f"{student.last_name}, {student.first_name}"
        )


def prompt_validate_roster() -> int:
    """Validate a selected canonical class roster or an explicit CSV path."""
    from quillan.menu import print_menu_header
    from quillan.menu_navigation import (
        NavigationChoice,
        parse_navigation_choice,
        print_navigation_options,
    )

    print_menu_header("Validate Class Roster")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1
    folders = _available_class_folders(workspace_root)
    if folders:
        print("Available classes:")
        for index, folder in enumerate(folders, start=1):
            print(f"{index}. {folder.class_id}")
    else:
        print("No class rosters found.")
        print("Create a class roster first, or choose a custom roster CSV path.")
    print("C. Custom roster CSV path")
    print_navigation_options()
    print()

    selection = input("Select class to validate: ").strip()
    navigation = parse_navigation_choice(selection)
    if selection == "" or navigation is NavigationChoice.BACK:
        return 1

    selected_folder: ClassFolder | None = None
    if selection.isdigit() and 1 <= int(selection) <= len(folders):
        selected_folder = folders[int(selection) - 1]
    else:
        selected_folder = next(
            (folder for folder in folders if folder.class_id == selection),
            None,
        )

    if selected_folder is not None:
        try:
            roster = load_class_roster(workspace_root, selected_folder.class_id)
        except RosterError as error:
            print_roster_validation_error(error)
            return 1
        metadata, metadata_error = _load_optional_class_metadata(
            workspace_root,
            selected_folder.class_id,
        )
        _print_roster_validation_summary(
            roster,
            selected_folder.roster_path,
            metadata=metadata,
            metadata_error=metadata_error,
            include_metadata=True,
        )
        return 0

    if selection.casefold() != "c":
        print(f"Error: Class not found: {selection}")
        return 1

    roster_path = _normalize_path_input(input("Roster CSV path, or B/M/Q: "))
    navigation = parse_navigation_choice(roster_path)
    if roster_path == "" or navigation is NavigationChoice.BACK:
        return 1
    try:
        roster = validate_roster_file(roster_path)
    except RosterError as error:
        print_roster_validation_error(error)
        return 1
    _print_roster_validation_summary(roster, roster_path)
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

            if navigation is NavigationChoice.BACK:
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

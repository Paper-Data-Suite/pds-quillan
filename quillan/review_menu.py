"""Teacher-facing review navigation menu skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pds_core.classes import list_class_folders, load_class_roster
from pds_core.rosters import RosterError
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.cli_app.output import (
    print_assignment_submission_status,
    print_opened_submission_review,
    workspace_relative_display,
)
from quillan.review_record import ReviewRecordError, load_review_record
from quillan.review_record_paths import review_record_path
from quillan.storage import assignment_config_path
from quillan.submission_review_opening import (
    SubmissionReviewOpeningError,
    open_student_submission_for_review,
)
from quillan.submission_status import (
    AssignmentSubmissionStatus,
    StudentSubmissionStatus,
    list_assignment_submission_status,
)


@dataclass(frozen=True, slots=True)
class AssignmentChoice:
    """One assignment available for teacher review navigation."""

    assignment_id: str
    title: str | None


def launch_review_student_work_menu() -> int:
    """Launch the read-only teacher review navigation workflow."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Review Student Work")
            print("1. Select class and assignment")
            print("2. Back")
            print()
            choice = input("Select an option: ").strip()
            print()

            if choice in {"", "2"}:
                return 0
            if choice != "1":
                print("Invalid selection. Please enter a number from 1 to 2.")
                print()
                pause_for_user()
                continue

            clear_screen()
            _run_review_selection_workflow()
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting review menu.")
        return 0


def _run_review_selection_workflow() -> int:
    from quillan.menu import print_menu_header

    print_menu_header("Review Student Work")
    workspace_root = _workspace_root()
    if workspace_root is None:
        return 1

    class_id = _prompt_class_id(workspace_root)
    if class_id is None:
        return 0

    assignment = _prompt_assignment(workspace_root, class_id)
    if assignment is None:
        return 0

    status = _load_submission_status(
        workspace_root,
        class_id,
        assignment.assignment_id,
    )
    if status is None:
        return 1

    print()
    print_assignment_submission_status(status, workspace_root)
    print()

    student_id = _prompt_student_id(workspace_root, class_id, status)
    if student_id is None:
        return 0

    return _launch_selected_student_review(
        workspace_root,
        class_id,
        assignment.assignment_id,
        student_id,
    )


def _workspace_root() -> Path | None:
    try:
        return resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return None


def _prompt_class_id(workspace_root: Path) -> str | None:
    folders = list_class_folders(workspace_root, require_roster=True)
    if not folders:
        print("No classes found in the current workspace.")
        return None

    print("Available classes:")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.class_id}")
    print("B. Back")
    print()

    while True:
        selection = input("Select class: ").strip()
        if selection == "" or selection.casefold() == "b":
            print("Review selection canceled.")
            return None
        if selection.isdigit() and 1 <= int(selection) <= len(folders):
            return folders[int(selection) - 1].class_id
        for folder in folders:
            if folder.class_id == selection:
                return folder.class_id
        print("Invalid class selection. Please choose a listed class or Back.")


def _prompt_assignment(
    workspace_root: Path,
    class_id: str,
) -> AssignmentChoice | None:
    assignments = _available_assignments(workspace_root, class_id)
    if not assignments:
        print(f"No assignments found for class {class_id}.")
        return None

    print()
    print(f"Assignments for {class_id}:")
    for index, assignment in enumerate(assignments, start=1):
        label = assignment.assignment_id
        if assignment.title:
            label += f" - {assignment.title}"
        print(f"{index}. {label}")
    print("B. Back")
    print()

    while True:
        selection = input("Select assignment: ").strip()
        if selection == "" or selection.casefold() == "b":
            print("Assignment selection canceled.")
            return None
        if selection.isdigit() and 1 <= int(selection) <= len(assignments):
            return assignments[int(selection) - 1]
        for assignment in assignments:
            if assignment.assignment_id == selection:
                return assignment
        print(
            "Invalid assignment selection. "
            "Please choose a listed assignment or Back."
        )


def _available_assignments(
    workspace_root: Path,
    class_id: str,
) -> tuple[AssignmentChoice, ...]:
    assignments_dir = workspace_root / "classes" / class_id / "assignments"
    if not assignments_dir.is_dir():
        return ()

    choices: list[AssignmentChoice] = []
    for assignment_dir in sorted(
        (path for path in assignments_dir.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    ):
        config_path = assignment_config_path(
            workspace_root,
            class_id,
            assignment_dir.name,
        )
        if not config_path.is_file():
            continue
        title = _load_assignment_title(config_path)
        choices.append(
            AssignmentChoice(
                assignment_id=assignment_dir.name,
                title=title,
            )
        )
    return tuple(choices)


def _load_assignment_title(config_path: Path) -> str | None:
    try:
        assignment = load_assignment_config(config_path)
    except (AssignmentConfigError, OSError):
        return None
    title = assignment.get("title")
    return title if isinstance(title, str) and title.strip() else None


def _load_submission_status(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentSubmissionStatus | None:
    try:
        return list_assignment_submission_status(
            workspace_root,
            class_id,
            assignment_id,
        )
    except Exception as error:
        print(f"Error: could not list submission status: {error}")
        return None


def _prompt_student_id(
    workspace_root: Path,
    class_id: str,
    status: AssignmentSubmissionStatus,
) -> str | None:
    student_ids = _student_choices(workspace_root, class_id, status)
    if not student_ids:
        print("No students or submissions found for this class assignment.")
        return None

    status_by_student = {
        student_status.student_id: student_status
        for student_status in status.student_statuses
    }
    print("Select student/submission:")
    for index, student_id in enumerate(student_ids, start=1):
        print(
            f"{index}. {student_id}: "
            f"{_student_status_label(status_by_student.get(student_id))}"
        )
    print("B. Back")
    print()

    while True:
        selection = input("Select student/submission: ").strip()
        if selection == "" or selection.casefold() == "b":
            print("Student selection canceled.")
            return None
        if selection.isdigit() and 1 <= int(selection) <= len(student_ids):
            return student_ids[int(selection) - 1]
        if selection in student_ids:
            return selection
        print(
            "Invalid student selection. "
            "Please choose a listed student/submission or Back."
        )


def _student_choices(
    workspace_root: Path,
    class_id: str,
    status: AssignmentSubmissionStatus,
) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()

    try:
        roster = load_class_roster(workspace_root, class_id)
    except RosterError:
        roster = None
    if roster is not None:
        for student in roster.students:
            ordered.append(student.student_id)
            seen.add(student.student_id)

    for student_status in status.student_statuses:
        if student_status.student_id not in seen:
            ordered.append(student_status.student_id)
            seen.add(student_status.student_id)

    return tuple(ordered)


def _student_status_label(status: StudentSubmissionStatus | None) -> str:
    if status is None:
        return "no manifest; no routed evidence"
    if status.manifest_path is None:
        return "routed evidence exists; no manifest"
    evidence_count = sum(page.evidence_count for page in status.pages)
    return (
        f"{status.submission_state}; manifest exists; "
        f"evidence files={evidence_count}"
    )


def _launch_selected_student_review(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> int:
    from quillan.menu import clear_screen, print_menu_header

    while True:
        clear_screen()
        print_menu_header("Selected Student Review")
        _print_review_summary(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
        print()
        print("1. Open submission evidence")
        print("2. Refresh summary")
        print("3. Back")
        print()

        choice = input("Select an option: ").strip()
        print()

        if choice in {"", "3"}:
            return 0
        if choice == "1":
            _open_submission_evidence(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "2":
            continue
        else:
            print("Invalid selection. Please enter a number from 1 to 3.")
            input("Press Enter to continue...")


def _print_review_summary(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    print("Current review summary")
    print()
    print(f"Class: {class_id}")
    print(f"Assignment: {assignment_id}")
    print(f"Student: {student_id}")

    status = _load_submission_status(workspace_root, class_id, assignment_id)
    student_status = None
    if status is not None:
        student_status = next(
            (
                candidate
                for candidate in status.student_statuses
                if candidate.student_id == student_id
            ),
            None,
        )
    if student_status is None:
        print("Submission: not assembled")
        print("Evidence files: 0")
        print("Review state: not_started")
    elif student_status.manifest_path is None:
        print("Submission: not assembled")
        print("Evidence files: routed but not assembled")
        print("Review state: not_started")
    else:
        print("Submission: assembled")
        print(
            "Submission manifest: "
            f"{workspace_relative_display(student_status.manifest_path, workspace_root)}"
        )
        print(
            "Evidence files: "
            f"{sum(page.evidence_count for page in student_status.pages)}"
        )
        print(f"Review state: {student_status.submission_state}")

    _print_review_record_summary(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
    )


def _print_review_record_summary(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    path = review_record_path(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
    )
    if not path.exists():
        print("Review record: not started")
        print("Review record file: missing")
        return

    try:
        record = load_review_record(path)
    except ReviewRecordError as error:
        print("Review record: invalid")
        print(f"Review record error: {error}")
        return

    print("Review record: exists")
    print(f"Review record file: {workspace_relative_display(path, workspace_root)}")
    print(f"Review record state: {record['review_state']}")
    print(f"Notes: {_count_record_items(record, 'notes')}")
    print(f"Tags: {_count_record_items(record, 'tags')}")
    print(f"Comments: {_count_record_items(record, 'comments')}")
    print(f"Scores: {_count_record_items(record, 'scores')}")


def _count_record_items(record: dict[str, Any], field: str) -> int:
    value = record.get(field)
    return len(value) if isinstance(value, list) else 0


def _open_submission_evidence(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    try:
        opened = open_student_submission_for_review(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
    except SubmissionReviewOpeningError as error:
        print(f"Error: could not open student submission: {error}")
        return

    print_opened_submission_review(opened)

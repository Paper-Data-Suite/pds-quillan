"""Teacher-facing review navigation menu skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pds_core.classes import list_class_folders, load_class_roster
from pds_core.rosters import RosterError
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.class_summary_export import (
    ClassSummaryExportError,
    export_class_review_summary,
)
from quillan.cli_app.output import (
    print_added_review_comment,
    print_added_review_note,
    print_added_review_tag,
    print_assignment_submission_status,
    print_exported_class_summary,
    print_exported_feedback,
    print_exported_standards_summary,
    print_opened_submission_review,
    print_updated_review_score,
    print_updated_submission_review_state,
    workspace_relative_display,
)
from quillan.feedback_export import FeedbackExportError, export_student_feedback
from quillan.standards_summary_export import (
    StandardsSummaryExportError,
    export_standards_summary,
)
from quillan.comment_banks import CommentBankError, load_comment_bank
from quillan.review_comments import ReviewCommentError, add_review_comment
from quillan.review_notes import ReviewNoteError, add_review_note
from quillan.review_record import (
    ALLOWED_LOCATION_TYPES,
    ALLOWED_TAG_POLARITIES,
    ReviewRecordError,
    load_review_record,
)
from quillan.review_record_paths import review_record_path
from quillan.review_scores import ReviewScoreError, set_review_score
from quillan.review_tags import ReviewTagError, add_review_tag
from quillan.storage import assignment_config_path
from quillan.submission_review_opening import (
    SubmissionReviewOpeningError,
    open_student_submission_for_review,
)
from quillan.submission_manifest import ALLOWED_SUBMISSION_STATES
from quillan.submission_review_state import (
    SubmissionReviewStateError,
    update_submission_review_state,
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

    return _launch_assignment_review_actions(
        workspace_root,
        class_id,
        assignment.assignment_id,
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
        print("2. Add teacher note")
        print("3. Add structured tag")
        print("4. Select reusable comment")
        print("5. Set criterion score")
        print("6. Update submission review state")
        print("7. Export student feedback")
        print("8. Refresh summary")
        print("9. Back")
        print()

        choice = input("Select an option: ").strip()
        print()

        if choice in {"", "9"}:
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
            _menu_add_review_note(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "3":
            _menu_add_review_tag(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "4":
            _menu_add_review_comment(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "5":
            _menu_set_review_score(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "6":
            _menu_update_submission_review_state(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "7":
            _menu_export_student_feedback(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "8":
            continue
        else:
            print("Invalid selection. Please enter a number from 1 to 9.")
            input("Press Enter to continue...")


def _menu_add_review_note(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    text = input("Teacher note text: ").strip()
    if not text:
        print("Add note canceled. Teacher note text is required.")
        return

    try:
        added = add_review_note(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            text,
        )
    except (ReviewNoteError, OSError) as error:
        print(f"Error: could not add teacher note: {error}")
        return

    print_added_review_note(added)


def _menu_add_review_tag(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    label = input("Tag label: ").strip()
    if not label:
        print("Add tag canceled. Tag label is required.")
        return

    print(
        f"Polarity options: {', '.join(sorted(ALLOWED_TAG_POLARITIES))}"
    )
    polarity = input("Tag polarity: ").strip()
    if polarity not in ALLOWED_TAG_POLARITIES:
        print(
            "Add tag canceled. Invalid polarity. "
            f"Allowed values: {', '.join(sorted(ALLOWED_TAG_POLARITIES))}."
        )
        return

    standard_id = input(
        "Standard ID (leave blank if not applicable): "
    ).strip() or None
    comment_id = None
    if standard_id is not None:
        comment_id = input(
            "Comment ID (leave blank if not applicable): "
        ).strip() or None
    severity = _parse_optional_positive_int(
        input("Severity (leave blank if not applicable): ")
    )
    teacher_note = input(
        "Teacher note (leave blank if not applicable): "
    ).strip() or None
    page_number = _parse_optional_positive_int(
        input("Page number (leave blank if not applicable): ")
    )
    evidence_id = input(
        "Evidence ID (leave blank if not applicable): "
    ).strip() or None
    location_type = input(
        "Location type (leave blank if not applicable): "
    ).strip() or None
    location_value: str | int | None = None
    if location_type:
        if location_type not in ALLOWED_LOCATION_TYPES:
            print(
                "Add tag canceled. Invalid location type. "
                f"Allowed values: {', '.join(sorted(ALLOWED_LOCATION_TYPES))}."
            )
            return
        raw_location = input(
            "Location value (leave blank if not applicable): "
        ).strip()
        if raw_location:
            if location_type in {
                "page",
                "paragraph",
                "sentence",
                "line",
            }:
                try:
                    location_value = int(raw_location)
                except ValueError:
                    print(
                        "Add tag canceled. Location value must be a positive integer "
                        f"for {location_type}."
                    )
                    return
            else:
                location_value = raw_location

    try:
        added = add_review_tag(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            label=label,
            polarity=polarity,
            standard_id=standard_id,
            comment_id=comment_id,
            severity=severity,
            teacher_note=teacher_note,
            page_number=page_number,
            evidence_id=evidence_id,
            location_type=location_type,
            location_value=location_value,
        )
    except (ReviewTagError, OSError) as error:
        print(f"Error: could not add structured tag: {error}")
        return

    print_added_review_tag(added)


def _load_available_comment_banks(
    workspace_root: Path,
) -> tuple[dict[str, Any], ...]:
    comment_banks_dir = (
        Path(workspace_root) / "shared" / "comment_banks"
    )
    if not comment_banks_dir.is_dir():
        return ()

    banks: list[dict[str, Any]] = []
    for bank_path in sorted(
        comment_banks_dir.glob("*.json"), key=lambda path: path.name.casefold()
    ):
        try:
            bank = load_comment_bank(bank_path)
        except (OSError, CommentBankError):
            continue
        banks.append(bank)
    return tuple(banks)


def _prompt_comment_bank(
    banks: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    print("Available comment banks:")
    for index, bank in enumerate(banks, start=1):
        title = bank.get("title")
        label = bank["bank_id"]
        if isinstance(title, str) and title.strip():
            label += f": {title.strip()}"
        print(f"{index}. {label}")
    print("B. Back")
    print()

    while True:
        selection = input("Select comment bank: ").strip()
        if selection == "" or selection.casefold() == "b":
            print("Select comment canceled.")
            return None
        if selection.isdigit():
            index = int(selection) - 1
            if 0 <= index < len(banks):
                return banks[index]
        for bank in banks:
            if bank["bank_id"] == selection:
                return bank
        print(
            "Invalid comment bank selection. "
            "Please choose a listed bank or Back."
        )


def _prompt_comment_from_bank(bank: dict[str, Any]) -> dict[str, Any] | None:
    raw_comments = bank.get("comments")
    if not isinstance(raw_comments, list):
        return None
    comments: list[dict[str, Any]] = [
        comment
        for comment in raw_comments
        if isinstance(comment, dict) and comment.get("student_facing") is True
    ]
    if not comments:
        print(
            "Select comment canceled. "
            "No student-facing comments available in this bank."
        )
        return None

    print("Available comments:")
    for index, comment in enumerate(comments, start=1):
        preview = comment.get("short_text") or comment["text"].splitlines()[0]
        preview = preview.strip()
        if len(preview) > 80:
            preview = preview[:77] + "..."
        print(
            f"{index}. {comment['comment_id']}: {comment['label']} — {preview}"
        )
    print("B. Back")
    print()

    while True:
        selection = input("Select comment: ").strip()
        if selection == "" or selection.casefold() == "b":
            print("Select comment canceled.")
            return None
        if selection.isdigit():
            index = int(selection) - 1
            if 0 <= index < len(comments):
                return comments[index]
        for comment in comments:
            if comment["comment_id"] == selection:
                return comment
        print(
            "Invalid comment selection. "
            "Please choose a listed comment or Back."
        )


def _prompt_optional_standard_id(comment: dict[str, Any]) -> str | None:
    standard_ids = [
        standard_id
        for standard_id in comment.get("standard_ids", [])
        if isinstance(standard_id, str) and standard_id.strip()
    ]
    if len(standard_ids) <= 1:
        return None

    print("Standard ID options:")
    for index, standard_id in enumerate(standard_ids, start=1):
        print(f"{index}. {standard_id}")
    print("B. Back")
    print()

    selection = input(
        "Select standard ID or leave blank to use default: "
    ).strip()
    if selection == "" or selection.casefold() == "b":
        return None
    if selection.isdigit():
        index = int(selection) - 1
        if 0 <= index < len(standard_ids):
            return standard_ids[index]
    if selection in standard_ids:
        return selection

    print(
        "Select comment canceled. "
        "Invalid standard ID selection."
    )
    return None


_CANCEL = object()


def _prompt_optional_boolean(
    prompt: str,
) -> bool | None | object:
    raw = input(prompt)
    normalized = raw.strip().lower()
    if normalized in {"", "none"}:
        return None
    if normalized in {"y", "yes", "true", "t"}:
        return True
    if normalized in {"n", "no", "false", "f"}:
        return False
    print(
        "Select comment canceled. Invalid response. "
        "Use y/n or leave blank to use default."
    )
    return _CANCEL


def _menu_add_review_comment(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    banks = _load_available_comment_banks(workspace_root)
    if not banks:
        print("Select comment canceled. No valid shared comment banks found.")
        return

    bank = _prompt_comment_bank(banks)
    if bank is None:
        return

    comment = _prompt_comment_from_bank(bank)
    if comment is None:
        return

    standard_id = _prompt_optional_standard_id(comment)
    include_in_feedback = _prompt_optional_boolean(
        "Include in feedback? (y/n, leave blank to use default): "
    )
    if include_in_feedback is _CANCEL:
        return

    val_include: bool | None = (
        include_in_feedback if isinstance(include_in_feedback, bool) else None
    )

    try:
        added = add_review_comment(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            bank_id=bank["bank_id"],
            comment_id=comment["comment_id"],
            standard_id=standard_id,
            include_in_feedback=val_include,
        )
    except (ReviewCommentError, OSError) as error:
        print(f"Error: could not select review comment: {error}")
        return

    print_added_review_comment(added)


def _menu_set_review_score(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    criterion_id = input("Criterion ID: ").strip()
    if not criterion_id:
        print("Set score canceled. criterion_id is required.")
        return

    label = input("Criterion label: ").strip()
    if not label:
        print("Set score canceled. label is required.")
        return

    score = _parse_required_number(input("Score: "))
    if score is None:
        print("Set score canceled. score is required and must be a number.")
        return

    max_score = _parse_required_number(input("Max score: "))
    if max_score is None:
        print("Set score canceled. max_score is required and must be a number.")
        return

    scale = input("Scale (leave blank if not applicable): ").strip() or None
    teacher_note = input(
        "Teacher note (leave blank if not applicable): "
    ).strip() or None

    try:
        updated = set_review_score(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            criterion_id=criterion_id,
            label=label,
            score=score,
            max_score=max_score,
            scale=scale,
            teacher_note=teacher_note,
        )
    except (ReviewScoreError, OSError) as error:
        print(f"Error: could not set review score: {error}")
        return

    print_updated_review_score(updated)


def _menu_update_submission_review_state(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    print("Submission review state options:")
    for index, state_opt in enumerate(sorted(ALLOWED_SUBMISSION_STATES), start=1):
        print(f"{index}. {state_opt}")
    print()

    selection = input("Select submission review state: ").strip()
    if not selection:
        print("Update review state canceled.")
        return

    selected_state: str | None = None
    if selection.isdigit():
        index = int(selection) - 1
        selected_state = sorted(ALLOWED_SUBMISSION_STATES)[index] if 0 <= index < len(ALLOWED_SUBMISSION_STATES) else None
    else:
        selected_state = selection

    if selected_state not in ALLOWED_SUBMISSION_STATES:
        print(
            "Update review state canceled. Invalid state selection. "
            f"Allowed values: {', '.join(sorted(ALLOWED_SUBMISSION_STATES))}."
        )
        return

    try:
        updated = update_submission_review_state(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            selected_state,
        )
    except SubmissionReviewStateError as error:
        print(f"Error: could not update submission review state: {error}")
        return

    print_updated_submission_review_state(updated)


def _parse_optional_positive_int(value: str) -> int | None:
    if not value.strip():
        return None
    try:
        parsed = int(value.strip())
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _parse_required_number(value: str) -> int | float | None:
    text = value.strip()
    if not text:
        return None
    try:
        if "." in text or "e" in text.lower():
            parsed = float(text)
        else:
            parsed = int(text)
    except ValueError:
        return None
    return parsed


def _parse_optional_boolean(value: str) -> bool | None:
    text = value.strip().lower()
    if text in {"", "none"}:
        return None
    if text in {"y", "yes", "true", "t"}:
        return True
    if text in {"n", "no", "false", "f"}:
        return False
    return None


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


def _prompt_overwrite_export() -> bool | object:
    response = input("Overwrite existing export if present? (y/N): ").strip().lower()
    if response in {"", "n", "no"}:
        return False
    if response in {"y", "yes"}:
        return True
    print("Export canceled. Please enter y or n.")
    return _CANCEL


def _menu_export_student_feedback(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    overwrite = _prompt_overwrite_export()
    if overwrite is _CANCEL:
        return
    assert isinstance(overwrite, bool)
    try:
        exported = export_student_feedback(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            overwrite=overwrite,
        )
    except (FeedbackExportError, OSError) as error:
        print(f"Error: could not export student feedback: {error}")
        return
    print_exported_feedback(exported)


def _menu_export_class_summary(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> None:
    overwrite = _prompt_overwrite_export()
    if overwrite is _CANCEL:
        return
    assert isinstance(overwrite, bool)
    try:
        exported = export_class_review_summary(
            workspace_root,
            class_id,
            assignment_id,
            overwrite=overwrite,
        )
    except (ClassSummaryExportError, OSError) as error:
        print(f"Error: could not export class review summary: {error}")
        return
    print_exported_class_summary(exported)


def _menu_export_standards_summary(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> None:
    overwrite = _prompt_overwrite_export()
    if overwrite is _CANCEL:
        return
    assert isinstance(overwrite, bool)
    try:
        exported = export_standards_summary(
            workspace_root,
            class_id,
            assignment_id,
            overwrite=overwrite,
        )
    except (StandardsSummaryExportError, OSError) as error:
        print(f"Error: could not export standards summary: {error}")
        return
    print_exported_standards_summary(exported)


def _launch_assignment_review_actions(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> int:
    from quillan.menu import clear_screen, print_menu_header

    while True:
        clear_screen()
        print_menu_header("Assignment Review Actions")

        status = _load_submission_status(
            workspace_root,
            class_id,
            assignment_id,
        )
        if status is None:
            input("Press Enter to continue...")
            return 1

        print_assignment_submission_status(status, workspace_root)
        print()

        print("1. Select student/submission")
        print("2. Export class review summary")
        print("3. Export standards summary")
        print("4. Refresh submission status")
        print("5. Back")
        print()

        choice = input("Select an option: ").strip()
        print()

        if choice in {"", "5"}:
            return 0
        elif choice == "1":
            student_id = _prompt_student_id(workspace_root, class_id, status)
            if student_id is not None:
                _launch_selected_student_review(
                    workspace_root,
                    class_id,
                    assignment_id,
                    student_id,
                )
        elif choice == "2":
            _menu_export_class_summary(workspace_root, class_id, assignment_id)
            input("Press Enter to continue...")
        elif choice == "3":
            _menu_export_standards_summary(workspace_root, class_id, assignment_id)
            input("Press Enter to continue...")
        elif choice == "4":
            continue
        else:
            print("Invalid selection. Please enter a number from 1 to 5.")
            input("Press Enter to continue...")

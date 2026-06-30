"""Teacher-facing review navigation menu skeleton."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pds_core.classes import list_class_folders, load_class_roster
from pds_core.rosters import RosterError
from pds_core.standards import StandardsValidationError
from pds_core.standards_selection import (
    load_standards_for_selection,
    resolve_standard_selection,
)
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.assignment_picker import (
    AssignmentChoice,
    available_assignments,
    prompt_assignment_choice,
)
from quillan.assignment_submission_assembly import assemble_assignment_submissions
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
)
from quillan.feedback_export import (
    FeedbackExportError,
    export_student_feedback,
    feedback_export_path,
)
from quillan.standards_summary_export import (
    StandardsSummaryExportError,
    export_standards_summary,
)
from quillan.comment_banks import CommentBankError, load_comment_bank
from quillan.tag_bank_writing import list_valid_tag_banks
from quillan.review_comments import ReviewCommentError, add_review_comment
from quillan.review_notes import ReviewNoteError, add_review_note
from quillan.review_record import (
    ALLOWED_TAG_POLARITIES,
    ReviewRecordError,
    load_review_record,
)
from quillan.review_record_paths import review_record_path
from quillan.review_snapshot import current_review_details_text
from quillan.review_targets import (
    ReviewTargetError,
    format_review_target,
    parse_paragraph_selection,
)
from quillan.review_requirements import (
    ReviewRequirementError,
    set_requirement_check,
)
from quillan.review_scores import ReviewScoreError, set_review_score
from quillan.rubrics import RubricError, load_rubric, rubric_path
from quillan.review_tags import ReviewTagError, add_review_tag
from quillan.storage import assignment_config_path
from quillan.submission_review_opening import (
    SubmissionReviewOpeningError,
    open_student_submission_for_review,
)
from quillan.submission_manifest import ALLOWED_SUBMISSION_STATES
from quillan.submission_page_management import (
    SubmissionPageManagementError,
    exclude_submission_page,
    mark_submission_page_needs_rescan,
    restore_excluded_submission_page,
)
from quillan.submission_review_state import (
    SubmissionReviewStateError,
    update_submission_review_state,
)
from quillan.submission_status import (
    AssignmentSubmissionStatus,
    StudentSubmissionStatus,
    list_assignment_submission_status,
)

_BACK = object()


def launch_review_student_work_menu() -> int:
    """Launch the read-only teacher review navigation workflow."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        while True:
            clear_screen()
            print_menu_header("Review Student Work")
            print("1. Assignment Review Actions")
            print("2. Scan Intake / Route Paper Responses")
            print("3. Manage Review Materials")
            print("4. Back")
            print()
            choice = input("Select an option: ").strip()
            print()

            if choice in {"", "4"}:
                return 0
            if choice == "1":
                clear_screen()
                _run_review_selection_workflow()
                print()
                pause_for_user()
            elif choice == "2":
                from quillan.menu import launch_scan_intake_workflow

                launch_scan_intake_workflow()
            elif choice == "3":
                from quillan.review_materials_menu import launch_review_materials_menu

                launch_review_materials_menu()
            else:
                print("Invalid selection. Please enter a number from 1 to 4.")
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

    assignment = prompt_assignment_choice(workspace_root)
    if assignment is None:
        return 0

    return _launch_assignment_review_actions(
        workspace_root,
        assignment.class_id,
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
    """Compatibility wrapper for callers of the original review helper."""
    return available_assignments(workspace_root, class_id)


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
    assignment_id: str,
    status: AssignmentSubmissionStatus,
) -> str | None:
    from quillan.menu import clear_screen, print_menu_header

    student_ids = _student_choices(workspace_root, class_id, status)
    if not student_ids:
        print("No students or submissions found for this class assignment.")
        return None

    clear_screen()
    print_menu_header("Select Student/Submission")
    print(f"Class: {class_id}")
    print(f"Assignment: {assignment_id}")
    print()

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
        status = _load_submission_status(workspace_root, class_id, assignment_id)
        student_status = _student_submission_status(status, student_id)
        if student_status is None:
            print("No routed evidence has been found for this student yet.")
            print(
                "Route a scan for this assignment, then assemble submissions "
                "before review."
            )
            print()
            print("1. View routed evidence status")
            print("2. Refresh summary")
            print("3. Back")
            print()
            choice = input("Select an option: ").strip()
            print()
            if choice in {"", "3"}:
                return 0
            if choice in {"1", "2"}:
                continue
            print("Invalid selection. Please enter a number from 1 to 3.")
            input("Press Enter to continue...")
            continue
        if student_status.manifest_path is None:
            print(
                "This student has routed evidence, but the review-ready "
                "submission record has not been assembled yet."
            )
            print(
                "Assemble submissions before reviewing, tagging, scoring, "
                "or exporting."
            )
            print()
            print("1. Assemble this assignment now")
            print("2. View routed evidence status")
            print("3. Refresh summary")
            print("4. Back")
            print()
            choice = input("Select an option: ").strip()
            print()
            if choice in {"", "4"}:
                return 0
            if choice == "1":
                _assemble_assignment(workspace_root, class_id, assignment_id)
                input("Press Enter to continue...")
            elif choice in {"2", "3"}:
                continue
            else:
                print("Invalid selection. Please enter a number from 1 to 4.")
                input("Press Enter to continue...")
            continue
        print("1. Open submission evidence")
        print("2. View current review details")
        print("3. Record minimum requirement checks")
        print("4. Manage submission pages")
        print("5. Add teacher note")
        print("6. Add structured tag")
        print("7. Select reusable comment")
        print("8. Set criterion score")
        print("9. Update submission review state")
        print("10. Export student feedback")
        print("11. Refresh summary")
        print("12. Back")
        print()

        choice = input("Select an option: ").strip()
        print()

        if choice in {"", "12"}:
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
            _menu_view_current_review_details(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "3":
            _menu_record_requirement_checks(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
        elif choice == "4":
            _menu_manage_submission_pages(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "5":
            _menu_add_review_note(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "6":
            _menu_add_review_tag(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "7":
            _menu_add_review_comment(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "8":
            _menu_set_review_score(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "9":
            _menu_update_submission_review_state(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "10":
            _menu_export_student_feedback(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            input("Press Enter to continue...")
        elif choice == "11":
            continue
        else:
            print("Invalid selection. Please enter a number from 1 to 12.")
            input("Press Enter to continue...")


def _student_submission_status(
    status: AssignmentSubmissionStatus | None, student_id: str
) -> StudentSubmissionStatus | None:
    if status is None:
        return None
    return next(
        (item for item in status.student_statuses if item.student_id == student_id),
        None,
    )


def _assemble_assignment(
    workspace_root: Path, class_id: str, assignment_id: str
) -> None:
    """Assemble routed evidence without replacing existing teacher records."""
    from quillan.cli_app.output import print_assignment_submission_assembly

    try:
        result = assemble_assignment_submissions(
            workspace_root, class_id, assignment_id, overwrite=False
        )
    except Exception as error:
        print(f"Error: could not assemble submissions: {error}")
        return
    print_assignment_submission_assembly(result, workspace_root)


def _print_review_action_header(
    title: str,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header(title)
    print(f"Class: {class_id}")
    print(f"Assignment: {assignment_id}")
    print(f"Student: {student_id}")
    print()


def _menu_view_current_review_details(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    _print_review_action_header(
        "Current Review Details", class_id, assignment_id, student_id
    )
    print(current_review_details_text(workspace_root, class_id, assignment_id, student_id))


def _format_secondary_id(value: object) -> str:
    return f"ID: {value}"


def _menu_add_review_note(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    _print_review_action_header("Add Teacher Note", class_id, assignment_id, student_id)
    print(
        "Teacher notes are private review notes. They help you remember what "
        "you noticed while reviewing this student's work."
    )
    print()
    print("They are not automatically student-facing feedback.")
    print()
    print("Example:")
    print("Needs a conference about missing page 2.")
    print()
    text = input("Enter note text, or B to go back: ").strip()
    if text.casefold() == "b":
        print("Add note canceled.")
        return
    if not text:
        print("Add note canceled.")
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
    _print_review_action_header("Add Tag", class_id, assignment_id, student_id)
    print("Tags are short teacher observations used for organization and summaries.")
    print("Choose a reusable tag, or create a one-time custom tag.")
    print()
    print("1. Select reusable tag")
    print("2. Custom tag")
    print("3. Back")
    print()
    choice = input("Select an option: ").strip()
    if choice in {"", "3"}:
        print("Add tag canceled.")
        return
    if choice == "1":
        _menu_add_reusable_review_tag(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
        return
    if choice == "2":
        _menu_add_custom_review_tag(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
        return

    # Compatibility with the prior direct menu prompt sequence: if a caller
    # supplies a tag label immediately after choosing Add structured tag, treat
    # that first response as the custom label.
    _menu_add_custom_review_tag(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
        initial_label=choice,
    )


def _menu_add_custom_review_tag(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    initial_label: str | None = None,
) -> None:
    _print_review_action_header("Custom Tag", class_id, assignment_id, student_id)
    print("Custom Tag")
    print()
    print("Use this when none of the reusable tags fit.")
    print()
    print("Required:")
    print("- label")
    print("- polarity")
    print()
    print("Optional:")
    print("- standard reference")
    print("- severity")
    print("- private teacher note")
    print("- page/evidence/location reference")
    print()
    print("Tag label:")
    print("Example: Good observation but unclear conclusion")
    print()
    label = (
        initial_label
        if initial_label is not None
        else input("Enter tag label, or B to go back: ").strip()
    )
    if label.casefold() == "b":
        print("Add tag canceled.")
        return
    if not label:
        print("Add tag canceled.")
        return

    polarity_values = ("positive", "developing", "negative", "neutral")
    print("Polarity:")
    print()
    for index, value in enumerate(polarity_values, start=1):
        print(f"{index}. {value}")
    print()
    print("B. Back")
    print()
    raw_polarity = input("Select polarity: ").strip()
    if raw_polarity.casefold() == "b" or raw_polarity == "":
        print("Add tag canceled.")
        return
    polarity = raw_polarity
    if raw_polarity.isdigit() and 1 <= int(raw_polarity) <= len(polarity_values):
        polarity = polarity_values[int(raw_polarity) - 1]
    if polarity not in ALLOWED_TAG_POLARITIES:
        print(
            "Add tag canceled. Invalid polarity. "
            f"Allowed values: {', '.join(sorted(ALLOWED_TAG_POLARITIES))}."
        )
        return

    standard_id = None
    comment_id = None
    severity = None
    teacher_note = None
    page_number = None
    evidence_id = None
    location_type = None
    location_value: str | int | list[int] | None = None
    if initial_label is not None or _prompt_yes_no_default_no("Add optional details?"):
        standard_id = input(
            "Standard ID (leave blank if not applicable): "
        ).strip() or None
        if standard_id is not None:
            _print_standard_hint(workspace_root, standard_id)
        comment_id = input(
            "Comment ID (leave blank if not applicable): "
        ).strip() or None
        severity = _parse_optional_positive_int(
            input("Severity (leave blank if not applicable): ")
        )
        teacher_note = input(
            "Private teacher note (leave blank if not applicable): "
        ).strip() or None
        target = _prompt_review_target(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
        if target is _BACK:
            print("Add tag canceled.")
            return
        assert isinstance(target, dict)
        page_number = target.get("page_number")
        evidence_id = target.get("evidence_id")
        location_type = target.get("location_type")
        location_value = target.get("location_value")

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
            source="custom",
        )
    except (ReviewTagError, OSError) as error:
        print(f"Error: could not add structured tag: {error}")
        return

    print_added_review_tag(added)


def _menu_add_reusable_review_tag(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    files = list_valid_tag_banks(workspace_root)
    if not files:
        _print_review_action_header(
            "Select Reusable Tag", class_id, assignment_id, student_id
        )
        print("No valid shared tag banks found.")
        print()
        print("Create one from:")
        print(
            "Review Student Work -> Manage Review Materials -> "
            "Tag Banks -> Create tag bank"
        )
        print()
        print("1. Custom tag")
        print("2. Back")
        selection = input("Select an option: ").strip()
        if selection == "1":
            _menu_add_custom_review_tag(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
        else:
            print("Add tag canceled.")
        return

    while True:
        _print_review_action_header(
            "Select Reusable Tag", class_id, assignment_id, student_id
        )
        bank = _prompt_tag_bank(files)
        if bank is _BACK:
            return
        if bank is None:
            input("Press Enter to continue...")
            continue
        assert isinstance(bank, dict)

        while True:
            _print_tag_context_header(
                "Select Tag Category",
                class_id,
                assignment_id,
                student_id,
                bank=bank,
            )
            category = _prompt_tag_category(bank)
            if category is _BACK:
                break
            if category is None:
                input("Press Enter to continue...")
                continue
            assert isinstance(category, dict)

            while True:
                _print_tag_context_header(
                    "Select Tag",
                    class_id,
                    assignment_id,
                    student_id,
                    bank=bank,
                    category=category,
                )
                tag = _prompt_tag_template(bank, category)
                if tag is _BACK:
                    break
                if tag is None:
                    input("Press Enter to continue...")
                    continue
                if tag is _CUSTOM_TAG:
                    _menu_add_custom_review_tag(
                        workspace_root,
                        class_id,
                        assignment_id,
                        student_id,
                    )
                    return

                assert isinstance(tag, dict)
                _print_tag_context_header(
                    "Reusable Tag Details",
                    class_id,
                    assignment_id,
                    student_id,
                    bank=bank,
                    category=category,
                )
                if _add_selected_reusable_tag(
                    workspace_root,
                    class_id,
                    assignment_id,
                    student_id,
                    bank,
                    tag,
                ):
                    return
                input("Press Enter to continue...")


def _add_selected_reusable_tag(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    bank: dict[str, Any],
    tag: dict[str, Any],
) -> bool:
    standard_id = _prompt_tag_standard_id(tag)
    criterion_id = _prompt_tag_criterion_id(tag)
    teacher_note = _prompt_template_teacher_note(tag)
    severity = tag.get("severity_default")
    severity_value = (
        severity if isinstance(severity, int) and not isinstance(severity, bool) else None
    )
    target = _prompt_review_target(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
    )
    if target is _BACK:
        print("Add tag canceled.")
        return False
    assert isinstance(target, dict)

    try:
        added = add_review_tag(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            label=str(tag["label"]),
            polarity=str(tag["polarity"]),
            standard_id=standard_id,
            criterion_id=criterion_id,
            severity=severity_value,
            teacher_note=teacher_note,
            source="tag_bank",
            tag_bank_id=str(bank["tag_bank_id"]),
            tag_template_id=str(tag["tag_template_id"]),
            **target,
        )
    except (ReviewTagError, OSError) as error:
        if standard_id is not None:
            print("This tag's saved standard IDs are not active for this assignment.")
            print("The tag can still be added without a standard reference.")
            print()
            print("1. Add tag without standard")
            print("2. Back")
            if input("Select an option: ").strip() == "1":
                try:
                    added = add_review_tag(
                        workspace_root,
                        class_id,
                        assignment_id,
                        student_id,
                        label=str(tag["label"]),
                        polarity=str(tag["polarity"]),
                        criterion_id=criterion_id,
                        severity=severity_value,
                        teacher_note=teacher_note,
                        source="tag_bank",
                        tag_bank_id=str(bank["tag_bank_id"]),
                        tag_template_id=str(tag["tag_template_id"]),
                        **target,
                    )
                except (ReviewTagError, OSError) as retry_error:
                    print(f"Error: could not add structured tag: {retry_error}")
                    return False
            else:
                print("Add tag canceled.")
                return False
        else:
            print(f"Error: could not add structured tag: {error}")
            return False

    print_added_review_tag(added)
    return True


def _print_tag_context_header(
    title: str,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    bank: dict[str, Any],
    category: dict[str, Any] | None = None,
) -> None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header(title)
    bank_title = bank.get("title")
    bank_label = (
        bank_title.strip()
        if isinstance(bank_title, str) and bank_title.strip()
        else str(bank["tag_bank_id"])
    )
    print(f"Tag Bank: {bank_label}")
    if category is not None:
        print(f"Category: {category['label']}")
    print(f"Class: {class_id}")
    print(f"Assignment: {assignment_id}")
    print(f"Student: {student_id}")
    print()


def _prompt_tag_bank(files: tuple[Any, ...]) -> dict[str, Any] | object | None:
    print("Available tag banks:")
    print()
    banks: list[dict[str, Any]] = []
    for item in files:
        assert item.bank is not None
        banks.append(item.bank)
    for index, bank in enumerate(banks, start=1):
        title = bank.get("title")
        label = str(title).strip() if isinstance(title, str) and title.strip() else bank["tag_bank_id"]
        print(f"{index}. {label}")
        print(f"   {_format_secondary_id(bank['tag_bank_id'])}")
        writing_types = bank.get("writing_types")
        if isinstance(writing_types, list) and writing_types:
            print(
                "   Writing assignment types: "
                f"{', '.join(str(item) for item in writing_types)}"
            )
    print("B. Back")
    print()
    selection = input("Select tag bank: ").strip()
    if selection == "" or selection.casefold() == "b":
        return _BACK
    if selection.isdigit() and 1 <= int(selection) <= len(banks):
        return banks[int(selection) - 1]
    for bank in banks:
        if bank["tag_bank_id"] == selection:
            return bank
    print("Invalid tag bank selection. Please choose a listed bank or Back.")
    return None


def _prompt_tag_category(bank: dict[str, Any]) -> dict[str, Any] | object | None:
    categories = _sorted_records(bank["categories"])
    print("Categories:")
    for index, category in enumerate(categories, start=1):
        print(f"{index}. {category['label']}")
    print("B. Back")
    print()
    selection = input("Select category: ").strip()
    if selection == "" or selection.casefold() == "b":
        return _BACK
    if selection.isdigit() and 1 <= int(selection) <= len(categories):
        return categories[int(selection) - 1]
    print("Invalid category selection. Please choose a listed category or Back.")
    return None


_CUSTOM_TAG = object()


def _prompt_tag_template(bank: dict[str, Any], category: dict[str, Any]) -> dict[str, Any] | object | None:
    tags = [
        tag
        for tag in _sorted_records(bank["tags"])
        if tag.get("category_id") == category["category_id"]
    ]
    print(f"{category['label']} Tags:")
    print()
    for index, tag in enumerate(tags, start=1):
        print(f"{index}. {tag['label']}")
        secondary: list[str] = []
        polarity = tag.get("polarity")
        if isinstance(polarity, str) and polarity:
            secondary.append(f"Polarity: {polarity}")
        severity = tag.get("severity_default")
        if isinstance(severity, int) and not isinstance(severity, bool):
            secondary.append(f"Severity: {severity}")
        if secondary:
            print(f"   {' | '.join(secondary)}")
        print(f"   {_format_secondary_id(tag['tag_template_id'])}")
    custom_index = len(tags) + 1
    print(f"{custom_index}. Custom tag")
    print("B. Back")
    print()
    selection = input("Select tag: ").strip()
    if selection == "" or selection.casefold() == "b":
        return _BACK
    if selection.isdigit():
        selected = int(selection)
        if 1 <= selected <= len(tags):
            return tags[selected - 1]
        if selected == custom_index:
            return _CUSTOM_TAG
    print("Invalid tag selection. Please choose a listed tag or Back.")
    return None


def _sorted_records(records: list[Any]) -> list[dict[str, Any]]:
    valid = [record for record in records if isinstance(record, dict)]
    return sorted(
        valid,
        key=lambda item: (
            item.get("sort_order") if isinstance(item.get("sort_order"), int) else 999999,
            str(item.get("label", "")).casefold(),
        ),
    )


def _prompt_tag_standard_id(tag: dict[str, Any]) -> str | None:
    standard_ids = [
        standard_id
        for standard_id in tag.get("standard_ids", [])
        if isinstance(standard_id, str) and standard_id.strip()
    ]
    if not standard_ids:
        return None
    if len(standard_ids) == 1:
        return standard_ids[0]
    print("Standard ID options:")
    for index, standard_id in enumerate(standard_ids, start=1):
        print(f"{index}. {standard_id}")
    print(f"{len(standard_ids) + 1}. Skip standard")
    print("B. Back")
    print()
    selection = input("Select standard ID: ").strip()
    if selection == "" or selection.casefold() == "b":
        return None
    if selection.isdigit():
        selected = int(selection)
        if 1 <= selected <= len(standard_ids):
            return standard_ids[selected - 1]
        if selected == len(standard_ids) + 1:
            return None
    if selection in standard_ids:
        return selection
    print("Invalid standard ID selection. Standard omitted.")
    return None


def _prompt_tag_criterion_id(tag: dict[str, Any]) -> str | None:
    criterion_ids = [
        criterion_id
        for criterion_id in tag.get("criterion_ids", [])
        if isinstance(criterion_id, str) and criterion_id.strip()
    ]
    if not criterion_ids:
        return None
    if len(criterion_ids) == 1:
        return criterion_ids[0]
    print("Criterion ID options:")
    for index, criterion_id in enumerate(criterion_ids, start=1):
        print(f"{index}. {criterion_id}")
    print(f"{len(criterion_ids) + 1}. Skip criterion")
    print("B. Back")
    print()
    selection = input("Select criterion ID: ").strip()
    if selection == "" or selection.casefold() == "b":
        return None
    if selection.isdigit():
        selected = int(selection)
        if 1 <= selected <= len(criterion_ids):
            return criterion_ids[selected - 1]
        if selected == len(criterion_ids) + 1:
            return None
    if selection in criterion_ids:
        return selection
    print("Invalid criterion ID selection. Criterion omitted.")
    return None


def _prompt_template_teacher_note(tag: dict[str, Any]) -> str | None:
    prompt = tag.get("teacher_note_prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    print("Teacher note:")
    print(prompt.strip())
    print()
    return input("Leave blank to skip: ").strip() or None


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
) -> dict[str, Any] | object | None:
    print("Available comment banks:")
    print()
    for index, bank in enumerate(banks, start=1):
        title = bank.get("title")
        label = title.strip() if isinstance(title, str) and title.strip() else bank["bank_id"]
        print(f"{index}. {label}")
        print(f"   {_format_secondary_id(bank['bank_id'])}")
        writing_types = bank.get("writing_types")
        if isinstance(writing_types, list) and writing_types:
            print(
                "   Writing assignment types: "
                f"{', '.join(str(item) for item in writing_types)}"
            )
        comments = bank.get("comments")
        if isinstance(comments, list):
            print(f"   Comments: {len(comments)}")
    print("B. Back")
    print()

    while True:
        selection = input("Select comment bank: ").strip()
        if selection == "" or selection.casefold() == "b":
            return _BACK
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


def _prompt_comment_category(bank: dict[str, Any]) -> dict[str, Any] | object | None:
    categories = _sorted_records(bank["categories"])
    print("Categories:")
    print()
    for index, category in enumerate(categories, start=1):
        print(f"{index}. {category['label']}")
    print("B. Back")
    print()
    selection = input("Select category: ").strip()
    if selection == "" or selection.casefold() == "b":
        return _BACK
    if selection.isdigit() and 1 <= int(selection) <= len(categories):
        return categories[int(selection) - 1]
    print("Invalid category selection. Please choose a listed category or Back.")
    return None


def _prompt_comment_from_bank(
    bank: dict[str, Any],
    category: dict[str, Any],
) -> dict[str, Any] | object | None:
    raw_comments = bank.get("comments")
    if not isinstance(raw_comments, list):
        return None
    comments: list[dict[str, Any]] = [
        comment
        for comment in _sorted_records(raw_comments)
        if comment.get("student_facing") is True
        and comment.get("category_id") == category["category_id"]
    ]
    if not comments:
        print("This bank has no student-facing comments.")
        print()
        print("Add one from:")
        print(
            "Review Student Work -> Manage Review Materials -> "
            "Comment Banks -> Add comment"
        )
        print()
        print("1. Choose another bank")
        print("2. Back")
        print()
        input("Select an option: ")
        print("Select comment canceled.")
        return None

    print(f"{category['label']} Comments:")
    print()
    for index, comment in enumerate(comments, start=1):
        preview = comment.get("short_text") or comment["text"].splitlines()[0]
        preview = preview.strip()
        if len(preview) > 80:
            preview = preview[:77] + "..."
        print(f"{index}. {comment['label']}")
        print(f"   {preview}")
        print(f"   {_format_secondary_id(comment['comment_id'])}")
    print("B. Back")
    print()

    while True:
        selection = input("Select comment: ").strip()
        if selection == "" or selection.casefold() == "b":
            return _BACK
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


def _prompt_optional_standard_id(
    workspace_root: Path,
    comment: dict[str, Any],
) -> str | None:
    standard_ids = [
        standard_id
        for standard_id in comment.get("standard_ids", [])
        if isinstance(standard_id, str) and standard_id.strip()
    ]
    if len(standard_ids) <= 1:
        return None

    print("Standard ID options:")
    for index, standard_id in enumerate(standard_ids, start=1):
        print(f"{index}. {_format_standard_display(workspace_root, standard_id)}")
        print(f"   {_format_secondary_id(standard_id)}")
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


def _confirm_comment_selection(
    comment: dict[str, Any],
    include_default: bool,
    target: dict[str, Any],
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> tuple[bool, dict[str, Any]] | object:
    include_in_feedback = include_default
    selected_target = target
    while True:
        print("Add this comment?")
        print()
        print(f"Comment: {comment['label']}")
        print(f"Feedback: {comment['text']}")
        print(f"Target: {_format_prompt_target(selected_target)}")
        print(f"Include in feedback: {_format_yes_no(include_in_feedback)}")
        print()
        print("1. Add comment")
        print("2. Change include-in-feedback setting")
        print("3. Change target")
        print("4. Back")
        print()
        selection = input("Select an option: ").strip()
        if selection == "1":
            return include_in_feedback, selected_target
        if selection == "2":
            include_in_feedback = not include_in_feedback
            continue
        if selection == "3":
            updated_target = _prompt_review_target(
                workspace_root,
                class_id,
                assignment_id,
                student_id,
            )
            if updated_target is _BACK:
                continue
            assert isinstance(updated_target, dict)
            selected_target = updated_target
            continue
        if selection in {"", "4"} or selection.casefold() == "b":
            print("Select comment canceled.")
            return _CANCEL
        print("Invalid selection. Please enter a number from 1 to 4.")


def _menu_add_review_comment(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    _print_review_action_header(
        "Select Reusable Comment", class_id, assignment_id, student_id
    )
    print("Reusable comments are teacher-authored feedback language prepared before review.")
    print("Choose a comment bank, then a category, then a comment.")
    print()
    print("1. Select comment bank")
    print("2. Back")
    print()
    first_choice = input("Select an option: ").strip()
    if first_choice in {"", "2"} or first_choice.casefold() == "b":
        print("Select comment canceled.")
        return
    if first_choice != "1":
        print("Invalid selection. Please enter a number from 1 to 2.")
        return

    banks = _load_available_comment_banks(workspace_root)
    if not banks:
        _print_review_action_header(
            "Select Comment Bank", class_id, assignment_id, student_id
        )
        print("No valid shared comment banks found.")
        print()
        print("Create one from:")
        print(
            "Review Student Work -> Manage Review Materials -> "
            "Comment Banks -> Create comment bank"
        )
        return

    while True:
        _print_review_action_header(
            "Select Comment Bank", class_id, assignment_id, student_id
        )
        bank = _prompt_comment_bank(banks)
        if bank is _BACK:
            return
        if bank is None:
            input("Press Enter to continue...")
            continue
        assert isinstance(bank, dict)

        while True:
            _print_comment_context_header(
                "Select Comment Category",
                class_id,
                assignment_id,
                student_id,
                bank=bank,
            )
            category = _prompt_comment_category(bank)
            if category is _BACK:
                break
            if category is None:
                input("Press Enter to continue...")
                continue
            assert isinstance(category, dict)

            while True:
                _print_comment_context_header(
                    "Select Comment",
                    class_id,
                    assignment_id,
                    student_id,
                    bank=bank,
                    category=category,
                )
                comment = _prompt_comment_from_bank(bank, category)
                if comment is _BACK:
                    break
                if comment is None:
                    input("Press Enter to continue...")
                    continue
                assert isinstance(comment, dict)

                _print_comment_context_header(
                    "Confirm Comment",
                    class_id,
                    assignment_id,
                    student_id,
                    bank=bank,
                    category=category,
                )
                if _add_selected_reusable_comment(
                    workspace_root,
                    class_id,
                    assignment_id,
                    student_id,
                    bank,
                    comment,
                ):
                    return
                input("Press Enter to continue...")


def _add_selected_reusable_comment(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    bank: dict[str, Any],
    comment: dict[str, Any],
) -> bool:
    standard_id = _prompt_optional_standard_id(workspace_root, comment)
    target = _prompt_review_target(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
    )
    if target is _BACK:
        print("Select comment canceled.")
        return False
    assert isinstance(target, dict)
    selection = _confirm_comment_selection(
        comment,
        bool(comment["include_in_feedback_default"]),
        target,
        workspace_root,
        class_id,
        assignment_id,
        student_id,
    )
    if selection is _CANCEL:
        return False
    assert isinstance(selection, tuple)
    include_in_feedback, selected_target = selection

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
            **selected_target,
        )
    except (ReviewCommentError, OSError) as error:
        print(f"Error: could not select review comment: {error}")
        return False

    print_added_review_comment(added)
    return True


def _print_comment_context_header(
    title: str,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    bank: dict[str, Any],
    category: dict[str, Any] | None = None,
) -> None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header(title)
    bank_title = bank.get("title")
    bank_label = (
        bank_title.strip()
        if isinstance(bank_title, str) and bank_title.strip()
        else str(bank["bank_id"])
    )
    print(f"Comment Bank: {bank_label}")
    if category is not None:
        print(f"Category: {category['label']}")
    print(f"Class: {class_id}")
    print(f"Assignment: {assignment_id}")
    print(f"Student: {student_id}")
    print()


def _menu_set_review_score(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    _print_review_action_header("Set Score", class_id, assignment_id, student_id)
    print("Use the assignment rubric, or enter a custom criterion.")
    print()
    print("1. Score from rubric")
    print("2. Custom criterion score")
    print("3. Back")
    print()
    choice = input("Select an option: ").strip()
    if choice in {"", "3"}:
        print("Set score canceled.")
        return
    if choice == "1":
        _menu_set_review_score_from_rubric(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
        return
    if choice == "2":
        _menu_set_custom_review_score(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
        return

    # Compatibility with the prior direct menu prompt sequence: if a caller
    # supplies a criterion ID immediately after choosing Set criterion score,
    # treat that first response as the custom criterion ID.
    _menu_set_custom_review_score(
        workspace_root,
        class_id,
        assignment_id,
        student_id,
        initial_criterion_id=choice,
    )


def _menu_set_review_score_from_rubric(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    assignment = _load_assignment_for_review(workspace_root, class_id, assignment_id)
    if assignment is None:
        return
    rubric_id = assignment.get("rubric_id")
    if not isinstance(rubric_id, str) or not rubric_id.strip():
        _menu_missing_rubric(workspace_root, class_id, assignment_id, student_id, "")
        return
    try:
        rubric = load_rubric(rubric_path(workspace_root, rubric_id))
    except (OSError, RubricError):
        _menu_missing_rubric(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            rubric_id,
        )
        return

    while True:
        _print_review_action_header(
            "Select Score Criterion", class_id, assignment_id, student_id
        )
        criterion = _prompt_score_criterion(rubric)
        if criterion is _BACK:
            return
        if criterion is None:
            input("Press Enter to continue...")
            continue
        assert isinstance(criterion, dict)

        while True:
            _print_score_context_header(
                "Select Score Level",
                class_id,
                assignment_id,
                student_id,
                criterion=criterion,
            )
            level = _prompt_score_level(criterion)
            if level is _BACK:
                break
            if level is None:
                input("Press Enter to continue...")
                continue
            assert isinstance(level, dict)

            _print_score_context_header(
                "Confirm Score",
                class_id,
                assignment_id,
                student_id,
                criterion=criterion,
            )
            teacher_note = _confirm_score_selection(criterion, level)
            if teacher_note is _BACK:
                continue
            if teacher_note is _CANCEL:
                return
            score_teacher_note = (
                teacher_note if isinstance(teacher_note, str) else None
            )
            try:
                updated = set_review_score(
                    workspace_root,
                    class_id,
                    assignment_id,
                    student_id,
                    criterion_id=criterion["criterion_id"],
                    label=criterion["label"],
                    score=level["score"],
                    max_score=criterion["max_score"],
                    scale=criterion["scale"],
                    teacher_note=score_teacher_note,
                )
            except (ReviewScoreError, OSError) as error:
                print(f"Error: could not set review score: {error}")
                input("Press Enter to continue...")
                continue
            print_updated_review_score(updated)
            return


def _menu_missing_rubric(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    rubric_id: str,
) -> None:
    print(
        "This assignment's rubric_id does not resolve to a valid shared "
        "rubric profile."
    )
    print()
    print(f"Rubric ID: {rubric_id}")
    print()
    print(
        "Create or fix the rubric from Review Student Work -> "
        "Manage Review Materials -> "
        "Rubrics / Scoring Profiles."
    )
    print()
    print("1. Custom criterion score")
    print("2. Back")
    print()
    choice = input("Select an option: ").strip()
    if choice == "1":
        _menu_set_custom_review_score(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
    else:
        print("Set score canceled.")


def _load_assignment_for_review(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> dict[str, Any] | None:
    try:
        return load_assignment_config(
            assignment_config_path(workspace_root, class_id, assignment_id)
        )
    except (AssignmentConfigError, OSError) as error:
        print(f"Error: could not load assignment config: {error}")
        return None


def _prompt_score_criterion(rubric: dict[str, Any]) -> dict[str, Any] | object | None:
    criteria = _sorted_records(rubric["criteria"])
    print(f"Rubric: {rubric['title']}")
    print(f"{_format_secondary_id(rubric['rubric_id'])}")
    writing_types = rubric.get("writing_types")
    if isinstance(writing_types, list) and writing_types:
        print(
            "Writing assignment types: "
            f"{', '.join(str(item) for item in writing_types)}"
        )
    print()
    print("Criteria:")
    print()
    for index, criterion in enumerate(criteria, start=1):
        print(f"{index}. {criterion['label']}")
        print(
            f"   Max score: {criterion['max_score']} | "
            f"Scale: {criterion.get('scale', '')}"
        )
        print(f"   {_format_secondary_id(criterion['criterion_id'])}")
    print()
    print("B. Back")
    print()
    selection = input("Select criterion: ").strip()
    if selection == "" or selection.casefold() == "b":
        return _BACK
    if selection.isdigit() and 1 <= int(selection) <= len(criteria):
        return criteria[int(selection) - 1]
    print("Invalid criterion selection. Please choose a listed criterion or Back.")
    return None


def _prompt_score_level(criterion: dict[str, Any]) -> dict[str, Any] | object | None:
    levels = _sorted_records(criterion["levels"])
    print(criterion["label"])
    print()
    for index, level in enumerate(levels, start=1):
        print(f"{index}. {level['score']} - {level['label']}")
        feedback = level.get("student_facing_feedback")
        if isinstance(feedback, str) and feedback.strip():
            print(f"   Feedback preview: {feedback.strip()}")
    print()
    print("B. Back")
    print()
    selection = input("Select score: ").strip()
    if selection == "" or selection.casefold() == "b":
        return _BACK
    if selection.isdigit() and 1 <= int(selection) <= len(levels):
        return levels[int(selection) - 1]
    for level in levels:
        if selection == str(level["score"]):
            return level
    print("Invalid score selection. Please choose a listed score or Back.")
    return None


def _confirm_score_selection(
    criterion: dict[str, Any],
    level: dict[str, Any],
) -> str | None | object:
    while True:
        print("Set this score?")
        print()
        print(f"Criterion: {criterion['label']}")
        print(f"Score: {level['score']} / {criterion['max_score']}")
        print(f"Level: {level['label']}")
        print(f"Scale: {criterion.get('scale', '')}")
        print()
        print("1. Save score")
        print("2. Add teacher note before saving")
        print("3. Back")
        print()
        selection = input("Select an option: ").strip()
        if selection == "1":
            return None
        if selection == "2":
            note = input("Teacher note, or B to go back: ").strip()
            if note.casefold() == "b":
                return _BACK
            return note or None
        if selection in {"", "3"} or selection.casefold() == "b":
            return _BACK
        print("Invalid selection. Please enter a number from 1 to 3.")


def _print_score_context_header(
    title: str,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    criterion: dict[str, Any],
) -> None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header(title)
    print(f"Criterion: {criterion['label']}")
    print(f"Class: {class_id}")
    print(f"Assignment: {assignment_id}")
    print(f"Student: {student_id}")
    print()


def _menu_set_custom_review_score(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    initial_criterion_id: str | None = None,
) -> None:
    _print_review_action_header(
        "Custom Criterion Score", class_id, assignment_id, student_id
    )
    print("Use this when the assignment rubric does not contain the criterion you need.")
    print()
    if initial_criterion_id is not None:
        criterion_id = initial_criterion_id
        label = input("Criterion label: ").strip()
    else:
        print("Criterion label:")
        print("Example: Source Integration")
        print()
        label = input("Enter criterion label, or B to go back: ").strip()
        if label.casefold() == "b" or not label:
            print("Set score canceled.")
            return
        suggested_id = _suggest_identifier(label)
        print()
        print("Suggested criterion_id:")
        print(suggested_id)
        print()
        criterion_id = (
            input("Press Enter to accept, or type a different criterion_id: ").strip()
            or suggested_id
        )
    if not criterion_id:
        print("Set score canceled. criterion_id is required.")
        return
    if not label:
        print("Set score canceled. label is required.")
        return

    print("Score must be between 0 and the max score.")
    print("Example: 3")
    score = _parse_required_number(input("Score: "))
    if score is None:
        print("Set score canceled. score is required and must be a number.")
        return

    print("Example: 4")
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
    _print_review_action_header(
        "Update Review State", class_id, assignment_id, student_id
    )
    print("Use this to mark where this student's submission is in your review workflow.")
    print("This is not a grade.")
    print()
    current_state = _current_submission_state(
        workspace_root, class_id, assignment_id, student_id
    )
    print(f"Current state: {current_state}")
    print()
    states = ("unreviewed", "in_progress", "needs_rescan", "reviewed")
    descriptions = {
        "unreviewed": "Review has not started yet.",
        "in_progress": "Review is underway.",
        "needs_rescan": "The submission needs a corrected scan or page.",
        "reviewed": "Review is complete.",
    }
    for index, state_opt in enumerate(states, start=1):
        print(f"{index}. {state_opt} - {descriptions[state_opt]}")
    print("B. Back")
    print()

    selection = input("Select submission review state: ").strip()
    if not selection or selection.casefold() == "b":
        print("Update review state canceled.")
        return

    selected_state: str | None = None
    if selection.isdigit():
        index = int(selection) - 1
        selected_state = states[index] if 0 <= index < len(states) else None
    else:
        selected_state = selection

    if selected_state not in ALLOWED_SUBMISSION_STATES:
        print(
            "Update review state canceled. Invalid state selection. "
            f"Allowed values: {', '.join(sorted(ALLOWED_SUBMISSION_STATES))}."
        )
        return

    print()
    print(f"Change review state to {selected_state}?")
    print()
    print("1. Save")
    print("2. Back")
    print()
    if input("Select an option: ").strip() != "1":
        print("Update review state canceled.")
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


def _prompt_yes_no_default_no(prompt: str) -> bool:
    response = input(f"{prompt} (y/N): ").strip().casefold()
    return response in {"y", "yes"}


def _format_yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _suggest_identifier(label: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "_"
        for character in label.strip()
    )
    return "_".join(part for part in normalized.split("_") if part) or "criterion"


def _format_standard_display(workspace_root: Path, standard_id: str) -> str:
    try:
        library = load_standards_for_selection(workspace_root)
        item = resolve_standard_selection(library, standard_id)
    except (OSError, StandardsValidationError, ValueError):
        return f"{standard_id} - Metadata unavailable"
    return f"{item.code} - {item.short_name}"


def _print_standard_hint(workspace_root: Path, standard_id: str) -> None:
    print(f"Standard: {_format_standard_display(workspace_root, standard_id)}")
    print(f"{_format_secondary_id(standard_id)}")


def _current_submission_state(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> str:
    status = _load_submission_status(workspace_root, class_id, assignment_id)
    student_status = _student_submission_status(status, student_id)
    if student_status is None:
        return "unreviewed"
    return str(student_status.submission_state)


def _review_record_counts(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> dict[str, int]:
    path = review_record_path(workspace_root, class_id, assignment_id, student_id)
    if not path.exists():
        return {"notes": 0, "tags": 0, "included_comments": 0, "scores": 0}
    try:
        record = load_review_record(path)
    except (OSError, ReviewRecordError):
        return {"notes": 0, "tags": 0, "included_comments": 0, "scores": 0}
    comments = record.get("comments")
    included_comments = (
        sum(1 for comment in comments if comment.get("include_in_feedback"))
        if isinstance(comments, list)
        else 0
    )
    return {
        "notes": _count_record_items(record, "notes"),
        "tags": _count_record_items(record, "tags"),
        "included_comments": included_comments,
        "scores": _count_record_items(record, "scores"),
    }


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
        _print_requirement_check_summary(
            workspace_root,
            class_id,
            assignment_id,
            {},
        )
        return

    try:
        record = load_review_record(path)
    except ReviewRecordError as error:
        print("Review record: invalid")
        print(f"Review record error: {error}")
        return

    print("Review record: exists")
    print(f"Review record state: {record['review_state']}")
    print(f"Notes: {_count_record_items(record, 'notes')}")
    print(f"Tags: {_count_record_items(record, 'tags')}")
    print(f"Comments: {_count_record_items(record, 'comments')}")
    print(f"Scores: {_count_record_items(record, 'scores')}")
    _print_requirement_check_summary(
        workspace_root,
        class_id,
        assignment_id,
        _current_requirement_checks(workspace_root, class_id, assignment_id, student_id),
    )


def _count_record_items(record: dict[str, Any], field: str) -> int:
    value = record.get(field)
    return len(value) if isinstance(value, list) else 0


def _print_requirement_check_summary(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    checks: dict[str, dict[str, Any]],
) -> None:
    assignment = _load_assignment_for_summary(workspace_root, class_id, assignment_id)
    requirements = (
        _requirement_items_from_assignment(assignment)
        if assignment is not None
        else []
    )
    if not requirements:
        print("Minimum requirements: none configured")
        return
    requirement_keys = {str(requirement["key"]) for requirement in requirements}
    relevant_checks = [
        check
        for key, check in checks.items()
        if key in requirement_keys and isinstance(check, dict)
    ]
    unmet_count = sum(1 for check in relevant_checks if check.get("met") is False)
    print(
        "Requirement checks: "
        f"{len(relevant_checks)}/{len(requirements)} complete; "
        f"{unmet_count} unmet"
    )


def _load_assignment_for_summary(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> dict[str, Any] | None:
    try:
        return load_assignment_config(
            assignment_config_path(workspace_root, class_id, assignment_id)
        )
    except (AssignmentConfigError, OSError):
        return None


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


def _menu_record_requirement_checks(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    while True:
        _print_review_action_header(
            "Requirement Checks", class_id, assignment_id, student_id
        )
        assignment = _load_assignment_for_review(
            workspace_root, class_id, assignment_id
        )
        if assignment is None:
            input("Press Enter to continue...")
            return
        requirements = _requirement_items_from_assignment(assignment)
        if not requirements:
            print("Minimum requirements: none configured")
            print()
            print("No review record was changed.")
            input("Press Enter to continue...")
            return

        existing = _current_requirement_checks(
            workspace_root, class_id, assignment_id, student_id
        )
        print("Requirement Checks")
        print()
        for index, requirement in enumerate(requirements, start=1):
            print(
                f"{index}. {requirement['label']}: "
                f"{_requirement_status(existing.get(requirement['key']))}"
            )
        print("B. Back")
        print()
        selection = input("Select requirement: ").strip()
        if selection == "" or selection.casefold() == "b":
            return
        if not selection.isdigit() or not (1 <= int(selection) <= len(requirements)):
            print("Invalid requirement selection. Please choose a listed item or Back.")
            input("Press Enter to continue...")
            continue

        requirement = requirements[int(selection) - 1]
        result = _prompt_and_set_requirement_check(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            requirement,
            existing.get(requirement["key"]),
        )
        if result is _BACK:
            continue
        input("Press Enter to continue...")


def _prompt_and_set_requirement_check(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    requirement: dict[str, Any],
    current_check: dict[str, Any] | None,
) -> object | None:
    _print_review_action_header(
        "Record Requirement Check", class_id, assignment_id, student_id
    )
    print(requirement["question"])
    print()
    print(requirement["detail"])
    print(f"Current value: {_requirement_status(current_check)}")
    print()
    print("1. True / Yes / Met")
    print("2. False / No / Not met")
    print("B. Back")
    print()
    selection = input("Select status: ").strip()
    if selection == "" or selection.casefold() == "b":
        return _BACK
    if selection == "1":
        met = True
    elif selection == "2":
        met = False
    else:
        print("Invalid status. Enter 1 for met or 2 for not met.")
        return None

    teacher_note = input(
        "Teacher note (leave blank if not applicable): "
    ).strip() or None
    try:
        updated = set_requirement_check(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            requirement_key=str(requirement["key"]),
            label=str(requirement["label"]),
            expected=requirement["expected"],
            met=met,
            teacher_note=teacher_note,
        )
    except (ReviewRequirementError, OSError) as error:
        print(f"Error: could not record requirement check: {error}")
        return None

    print()
    print("Recorded requirement check:")
    print(f"Requirement: {updated.requirement_key}")
    print(f"Met: {_format_yes_no(updated.met)}")
    print(f"Action: {'created' if updated.was_created else 'updated'}")
    print(f"Review state: {updated.review_state}")
    print(f"Review record: {updated.review_record_relative_path}")
    return None


def _requirement_items_from_assignment(
    assignment: dict[str, Any],
) -> list[dict[str, Any]]:
    basic_requirements = assignment.get("basic_requirements")
    if not isinstance(basic_requirements, dict):
        return []

    items: list[dict[str, Any]] = []
    numeric_specs = (
        (
            "paragraphs_min",
            "Minimum paragraphs",
            "Does the submission meet the minimum paragraph requirement?",
            "Minimum: {value} paragraphs",
        ),
        (
            "paragraphs_max",
            "Maximum paragraphs",
            "Does the submission stay within the maximum paragraph requirement?",
            "Maximum: {value} paragraphs",
        ),
        (
            "word_count_min",
            "Minimum word count",
            "Does the submission meet the minimum word count?",
            "Minimum: {value} words",
        ),
        (
            "word_count_max",
            "Maximum word count",
            "Does the submission stay within the maximum word count?",
            "Maximum: {value} words",
        ),
    )
    for key, label, question, detail_template in numeric_specs:
        value = basic_requirements.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            items.append(
                {
                    "key": key,
                    "label": label,
                    "expected": value,
                    "question": question,
                    "detail": detail_template.format(value=value),
                }
            )

    required_elements = basic_requirements.get("required_elements")
    if isinstance(required_elements, list):
        for element in required_elements:
            if not isinstance(element, str) or not element.strip():
                continue
            normalized = element.strip()
            items.append(
                {
                    "key": f"required_elements:{normalized}",
                    "label": f"Required element: {normalized}",
                    "expected": normalized,
                    "question": "Does the submission include this required element?",
                    "detail": f"Required element: {normalized}",
                }
            )
    return items


def _current_requirement_checks(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> dict[str, dict[str, Any]]:
    path = review_record_path(workspace_root, class_id, assignment_id, student_id)
    if not path.exists():
        return {}
    try:
        record = load_review_record(path)
    except (OSError, ReviewRecordError):
        return {}
    checks = record.get("requirement_checks")
    if not isinstance(checks, list):
        return {}
    return {
        str(check["requirement_key"]): check
        for check in checks
        if isinstance(check, dict) and isinstance(check.get("requirement_key"), str)
    }


def _requirement_status(check: dict[str, Any] | None) -> str:
    if check is None:
        return "not checked"
    return "met" if check.get("met") is True else "not met"


def _menu_manage_submission_pages(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    _print_review_action_header(
        "Manage Submission Pages", class_id, assignment_id, student_id
    )
    print(
        "Excluded pages are preserved in the submission record but left out "
        "of active review."
    )
    print("Excluding a page does not delete the file.")
    print()
    status = _load_submission_status(workspace_root, class_id, assignment_id)
    student_status = _student_submission_status(status, student_id)
    if student_status is None or student_status.manifest_path is None:
        print("No assembled submission record was found for this student.")
        return

    _print_manageable_pages(student_status.pages)
    print()
    print("Actions:")
    print("1. Exclude page from review")
    print("2. Restore excluded page")
    print("3. Mark page as needs rescan")
    print("4. Back")
    print()
    choice = input("Select an option: ").strip()
    if choice in {"", "4"}:
        print("Manage submission pages canceled.")
        return
    if choice == "1":
        _menu_change_submission_page(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            student_status.pages,
            action="exclude",
        )
    elif choice == "2":
        _menu_change_submission_page(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            student_status.pages,
            action="restore",
        )
    elif choice == "3":
        _menu_change_submission_page(
            workspace_root,
            class_id,
            assignment_id,
            student_id,
            student_status.pages,
            action="needs_rescan",
        )
    else:
        print("Invalid selection. Please enter a number from 1 to 4.")


def _print_manageable_pages(pages: tuple[Any, ...]) -> None:
    print("Pages:")
    for page in pages:
        state = _teacher_page_state_label(page.page_state)
        selected = page.selected_evidence_id or "no selected evidence"
        print(
            f"{page.page_number}. Page {page.page_number} - {state} - "
            f"selected evidence: {selected}"
        )


def _teacher_page_state_label(page_state: str) -> str:
    labels = {
        "excluded": "excluded from active review",
        "needs_rescan": "needs rescan",
    }
    return labels.get(page_state, page_state)


def _menu_change_submission_page(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    pages: tuple[Any, ...],
    *,
    action: str,
) -> None:
    titles = {
        "exclude": "Exclude Page From Review",
        "restore": "Restore Excluded Page",
        "needs_rescan": "Mark Page as Needing Rescan",
    }
    _print_review_action_header(titles[action], class_id, assignment_id, student_id)
    if action == "exclude":
        print("This keeps the evidence file but removes the page from active review.")
        print(
            "Use this for blank pages, wrong pages, accidental scans, or pages "
            "that should not be scored."
        )
    elif action == "restore":
        print("This returns an excluded page to active review.")
        print("It does not change scores, tags, comments, or feedback.")
    else:
        print(
            "Use this when a page is missing, damaged, unreadable, incomplete, "
            "or the wrong page."
        )
    print()
    _print_manageable_pages(pages)
    print("B. Back")
    print()
    page_number = _prompt_page_number("Select page: ")
    if page_number is None:
        print("Page action canceled.")
        return
    if page_number not in {page.page_number for page in pages}:
        print("Page action canceled. Please choose a listed page.")
        return

    confirm_labels = {
        "exclude": f"Exclude page {page_number} from active review?",
        "restore": f"Restore page {page_number} to active review?",
        "needs_rescan": f"Mark page {page_number} as needing rescan?",
    }
    print()
    print(confirm_labels[action])
    print()
    print("1. Save page change")
    print("2. Back")
    print()
    if input("Select an option: ").strip() != "1":
        print("Page action canceled. No file was changed.")
        return

    try:
        if action == "exclude":
            result = exclude_submission_page(
                workspace_root, class_id, assignment_id, student_id, page_number
            )
        elif action == "restore":
            result = restore_excluded_submission_page(
                workspace_root, class_id, assignment_id, student_id, page_number
            )
        else:
            result = mark_submission_page_needs_rescan(
                workspace_root, class_id, assignment_id, student_id, page_number
            )
    except SubmissionPageManagementError as error:
        print(f"Error: page change was not saved: {error}")
        return

    print("Page change saved.")
    print(f"Page: {result.page_number}")
    print(f"State: {_teacher_page_state_label(result.page_state)}")
    print(f"Evidence records preserved: {result.evidence_count}")
    print("Review notes, tags, comments, scores, and feedback were not changed.")


def _prompt_page_number(prompt: str) -> int | None:
    selection = input(prompt).strip()
    if selection == "" or selection.casefold() == "b":
        return None
    try:
        page_number = int(selection)
    except ValueError:
        return None
    return page_number if page_number > 0 else None


def _prompt_review_target(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> dict[str, Any] | object:
    while True:
        _print_review_action_header(
            "Review Target", class_id, assignment_id, student_id
        )
        print("Where does this apply?")
        print()
        print("1. Whole submission")
        print("2. Specific paragraph(s)")
        print("3. Specific page")
        print("4. Specific page and paragraph(s)")
        print("5. Skip location")
        print("B. Back")
        print()
        selection = input("Select target: ").strip()
        if selection == "" or selection.casefold() == "b":
            return _BACK
        if selection == "1":
            return {"location_type": "whole_submission", "location_value": None}
        if selection == "2":
            paragraphs = _prompt_paragraph_numbers()
            if paragraphs is _BACK:
                return _BACK
            return {"location_type": "paragraph", "location_value": paragraphs}
        if selection == "3":
            page_number = _prompt_page_number("Page number: ")
            if page_number is None:
                return _BACK
            return {"page_number": page_number}
        if selection == "4":
            page_number = _prompt_page_number("Page number: ")
            if page_number is None:
                return _BACK
            paragraphs = _prompt_paragraph_numbers()
            if paragraphs is _BACK:
                return _BACK
            return {
                "page_number": page_number,
                "location_type": "paragraph",
                "location_value": paragraphs,
            }
        if selection == "5":
            return {}

        print("Invalid selection. Please enter a number from 1 to 5 or B.")


def _prompt_paragraph_numbers() -> int | list[int] | object:
    print()
    print("Paragraph number(s):")
    print("Examples: 2, 2-4, 2,4,6")
    while True:
        raw = input("Paragraph number(s): ").strip()
        if raw == "" or raw.casefold() == "b":
            return _BACK
        try:
            return parse_paragraph_selection(raw)
        except ReviewTargetError as error:
            print(f"Invalid paragraph target: {error}")


def _format_prompt_target(target: dict[str, Any]) -> str:
    item: dict[str, Any] = {}
    if "page_number" in target:
        item["page_number"] = target["page_number"]
    if "evidence_id" in target:
        item["evidence_id"] = target["evidence_id"]
    if "location_type" in target:
        item["location"] = {
            "type": target["location_type"],
            "value": target.get("location_value"),
        }
    return format_review_target(item)


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
    _print_review_action_header(
        "Export Student Feedback", class_id, assignment_id, student_id
    )
    print("This creates a student feedback export from the current review record.")
    print("It does not rescore work or generate AI feedback.")
    print()
    counts = _review_record_counts(workspace_root, class_id, assignment_id, student_id)
    print("Review contents:")
    print(f"Notes: {counts['notes']}")
    print(f"Tags: {counts['tags']}")
    print(f"Comments included in feedback: {counts['included_comments']}")
    print(f"Scores: {counts['scores']}")
    print()
    print("1. Export feedback")
    print("2. Back")
    print()
    if input("Select an option: ").strip() != "1":
        print("Export canceled.")
        return

    output_path = feedback_export_path(workspace_root, class_id, assignment_id, student_id)
    overwrite: bool
    if output_path.exists():
        print()
        print("A feedback export already exists.")
        print()
        print("1. Keep existing export and cancel")
        print("2. Overwrite existing export")
        print("3. Back")
        print()
        selection = input("Select an option: ").strip()
        if selection == "2":
            overwrite = True
        else:
            print("Export canceled.")
            return
    else:
        overwrite = False

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
        print("2. Assemble routed submissions")
        print("3. Export class review summary")
        print("4. Export standards summary")
        print("5. Refresh submission status")
        print("6. Back")
        print()

        choice = input("Select an option: ").strip()
        print()

        if choice in {"", "6"}:
            return 0
        elif choice == "1":
            student_id = _prompt_student_id(
                workspace_root, class_id, assignment_id, status
            )
            if student_id is not None:
                _launch_selected_student_review(
                    workspace_root,
                    class_id,
                    assignment_id,
                    student_id,
                )
        elif choice == "2":
            _assemble_assignment(workspace_root, class_id, assignment_id)
            input("Press Enter to continue...")
        elif choice == "3":
            _menu_export_class_summary(workspace_root, class_id, assignment_id)
            input("Press Enter to continue...")
        elif choice == "4":
            _menu_export_standards_summary(workspace_root, class_id, assignment_id)
            input("Press Enter to continue...")
        elif choice == "5":
            continue
        else:
            print("Invalid selection. Please enter a number from 1 to 6.")
            input("Press Enter to continue...")

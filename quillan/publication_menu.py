"""Teacher-facing Core publication lifecycle workflow."""

from __future__ import annotations

from pathlib import Path

from pds_core.classes import list_class_folders
from pds_core.publication_records import PublicationRecord, PublicationWithdrawal
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.academic_result_publication import (
    AcademicResultPublicationResult,
    AcademicResultWithdrawalResult,
    QuillanAcademicResultPublicationError,
    QuillanAcademicResultPublicationPartialSuccessError,
    QuillanPublicationSeriesState,
    load_quillan_publication,
    load_quillan_publication_series_status,
    publish_quillan_academic_results,
    rebuild_full_academic_catalog,
    republish_quillan_academic_results_after_withdrawal,
    supersede_quillan_academic_results,
    withdraw_quillan_academic_result_publication,
)
from quillan.assignment_picker import AssignmentChoice, available_assignments
from quillan.menu_navigation import (
    NavigationChoice,
    navigation_hint,
    parse_navigation_choice,
    print_navigation_options,
)


def _optional(value: object | None) -> str:
    return "none" if value is None else str(value)


def _prompt_publication_assignment_choice(
    workspace_root: Path,
) -> AssignmentChoice | None:
    """Select a canonical assignment without requiring a roster."""
    folders = list_class_folders(workspace_root, require_roster=False)
    if not folders:
        print("No classes found in the current workspace.")
        return None

    print("Available classes:")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.class_id}")
    print_navigation_options()
    print()

    while True:
        selection = input("Select class: ").strip()
        navigation = parse_navigation_choice(selection)
        if selection == "" or navigation is NavigationChoice.BACK:
            print("Class selection canceled.")
            return None
        if selection.isdigit() and 1 <= int(selection) <= len(folders):
            class_id = folders[int(selection) - 1].class_id
            break
        class_matches = tuple(
            folder for folder in folders if folder.class_id == selection
        )
        if class_matches:
            class_id = class_matches[0].class_id
            break
        print(f"Invalid class selection. {navigation_hint()}")

    assignments = available_assignments(workspace_root, class_id)
    if not assignments:
        print(f"No valid Quillan assignments found for class {class_id}.")
        return None

    print()
    print(f"Class: {class_id}")
    print("Assignments:")
    for index, assignment in enumerate(assignments, start=1):
        label = assignment.assignment_id
        if assignment.title:
            label += f" - {assignment.title}"
        print(f"{index}. {label}")
    print_navigation_options()
    print()

    while True:
        selection = input("Select assignment: ").strip()
        navigation = parse_navigation_choice(selection)
        if selection == "" or navigation is NavigationChoice.BACK:
            print("Assignment selection canceled.")
            return None
        if selection.isdigit() and 1 <= int(selection) <= len(assignments):
            return assignments[int(selection) - 1]
        assignment_matches = tuple(
            item for item in assignments if item.assignment_id == selection
        )
        if assignment_matches:
            return assignment_matches[0]
        print(f"Invalid assignment selection. {navigation_hint()}")


def _print_state(state: QuillanPublicationSeriesState) -> None:
    print(f"Class: {state.work.class_id}")
    print(f"Assignment: {state.work.work_id}")
    print(
        "Producer head revision: "
        f"{_optional(state.producer_head_revision)}"
    )
    print(f"Publication count: {len(state.publications)}")
    print(f"Withdrawal count: {len(state.withdrawals)}")
    print(
        "Canonical series head: "
        f"{_optional(None if state.core_head is None else state.core_head.publication_id)}"
    )
    print(
        "Current selectable publication: "
        f"{_optional(None if state.current_selectable_publication is None else state.current_selectable_publication.publication_id)}"
    )
    print(
        "Catalog available: "
        f"{'yes' if state.derived_catalog_available else 'no'}"
    )


def _print_publication(
    publication: PublicationRecord,
    withdrawal: PublicationWithdrawal | None,
) -> None:
    print(f"Publication ID: {publication.publication_id}")
    print(f"Producer revision: {publication.record_set_revision}")
    print(f"Published: {publication.published_at.isoformat()}")
    print(
        "Registration revision: "
        f"{_optional(publication.academic_work_registration_revision)}"
    )
    print(f"Manifest path: {publication.manifest_path}")
    print(f"Manifest SHA-256: {publication.manifest_digest}")
    print(
        "Supersedes publication ID: "
        f"{_optional(publication.supersedes_publication_id)}"
    )
    print(f"Withdrawn: {'yes' if withdrawal is not None else 'no'}")
    if withdrawal is not None:
        print(f"Withdrawn at: {withdrawal.withdrawn_at.isoformat()}")


def _print_publication_result(result: AcademicResultPublicationResult) -> None:
    print(f"Operation: {result.operation}")
    print(f"Disposition: {result.disposition}")
    print("Producer compatibility: compatible")
    print("Catalog reconciliation: verified")
    _print_publication(result.publication, result.withdrawal)


def _print_withdrawal_result(result: AcademicResultWithdrawalResult) -> None:
    print("Operation: withdraw")
    print(f"Disposition: {result.disposition}")
    print(
        "Withdrawal manifest verification: "
        f"{result.manifest_verification}"
    )
    print("Catalog reconciliation: verified")
    _print_publication(result.publication, result.withdrawal)


def _print_error(error: Exception) -> None:
    """Render bounded diagnostics without private producer content."""
    print("Error: publication operation did not complete.")
    if isinstance(error, QuillanAcademicResultPublicationPartialSuccessError):
        state = error.state
        print("Warning: immutable producer/Core state may already be durable.")
        print(f"Canonical state: {state.canonical_state}")
        if state.publication is not None:
            print(f"Publication ID: {state.publication.publication_id}")
        if state.manifest is not None:
            print(f"Producer revision: {state.manifest.revision}")
            print(f"Manifest path: {state.manifest.relative_path}")
            print(f"Manifest SHA-256: {state.manifest.sha256}")
        if state.withdrawal is not None:
            print("Withdrawal durable: yes")
            print(f"Withdrawn at: {state.withdrawal.withdrawn_at.isoformat()}")
        if state.withdrawal_manifest_verification is not None:
            print(
                "Withdrawal manifest verification: "
                f"{state.withdrawal_manifest_verification}"
            )
        print(
            "Catalog rebuild attempted: "
            f"{'yes' if state.catalog_rebuild_attempted else 'no'}"
        )
        print(
            "Catalog replacement completed: "
            f"{'yes' if state.catalog_replacement_completed else 'no'}"
        )
        print(
            "Catalog verification completed: "
            f"{'yes' if state.catalog_verification_completed else 'no'}"
        )
        print(f"Next action: {state.recommended_next_action}")


def _prompt_publication_id(state: QuillanPublicationSeriesState) -> str | None:
    if not state.publications:
        print("No canonical publications exist.")
        return None
    print("Canonical publications:")
    for publication in state.publications:
        suffix = ""
        if (
            state.core_head is not None
            and publication.publication_id == state.core_head.publication_id
        ):
            suffix = " [series head]"
        print(
            f"- {publication.publication_id}; "
            f"producer revision {publication.record_set_revision}{suffix}"
        )
    response = input("Publication ID: ").strip()
    navigation = parse_navigation_choice(response)
    if response == "" or navigation is NavigationChoice.BACK:
        return None
    if any(item.publication_id == response for item in state.publications):
        return response
    print("Invalid publication ID.")
    return None


def launch_academic_result_publication_menu() -> int:
    """Run the explicit teacher-controlled Core publication workflow."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        workspace_root = resolve_workspace_root()
    except WorkspaceRootError as error:
        _print_error(error)
        return 1

    try:
        while True:
            clear_screen()
            print_menu_header("Academic Result Publications")
            choice = _prompt_publication_assignment_choice(workspace_root)
            if choice is None:
                return 0

            while True:
                try:
                    state = load_quillan_publication_series_status(
                        workspace_root,
                        choice.class_id,
                        choice.assignment_id,
                    )
                except QuillanAcademicResultPublicationError as error:
                    _print_error(error)
                    print()
                    pause_for_user()
                    break

                clear_screen()
                print_menu_header("Academic Result Publications")
                print(f"Class: {choice.class_id}")
                print(f"Assignment: {choice.assignment_id}")
                if choice.title:
                    print(f"Assignment title: {choice.title}")
                print()
                _print_state(state)
                print()
                print("1. Refresh status")
                print("2. List publications")
                print("3. Show publication")
                print("4. Publish producer head")
                print("5. Supersede exact Core head")
                print("6. Republish after withdrawn head")
                print("7. Withdraw exact publication")
                print("8. Rebuild full Core catalog")
                print("9. Return")
                print_navigation_options()
                action = input("Select an option: ").strip()
                navigation = parse_navigation_choice(action)
                if action == "" or action == "9" or navigation is NavigationChoice.BACK:
                    break

                if action == "1":
                    print()
                    print("Status will be refreshed.")
                    print()
                    pause_for_user()
                    continue

                if action == "2":
                    print()
                    if not state.publications:
                        print("Publications: none")
                    else:
                        withdrawal_by_id = {
                            item.publication_id: item
                            for item in state.withdrawals
                        }
                        for index, publication in enumerate(state.publications):
                            if index:
                                print()
                            _print_publication(
                                publication,
                                withdrawal_by_id.get(
                                    publication.publication_id
                                ),
                            )
                    print()
                    pause_for_user()
                    continue

                if action == "3":
                    print()
                    publication_id = _prompt_publication_id(state)
                    if publication_id is None:
                        print()
                        pause_for_user()
                        continue
                    try:
                        publication, withdrawal = load_quillan_publication(
                            workspace_root,
                            choice.class_id,
                            choice.assignment_id,
                            publication_id,
                        )
                        print()
                        _print_publication(publication, withdrawal)
                    except QuillanAcademicResultPublicationError as error:
                        _print_error(error)
                    print()
                    pause_for_user()
                    continue

                if action == "4":
                    print()
                    if state.producer_head is None:
                        print("No immutable producer head exists.")
                        print()
                        pause_for_user()
                        continue
                    print(
                        "Producer revision to publish: "
                        f"{state.producer_head.revision}"
                    )
                    print(
                        "This creates/reconciles Core publication state. "
                        "It does not calculate a Grade."
                    )
                    confirmation = input("Type PUBLISH to continue: ").strip()
                    if confirmation != "PUBLISH":
                        print("Canceled: publication state was not changed.")
                        print()
                        pause_for_user()
                        continue
                    try:
                        publication_result = publish_quillan_academic_results(
                            workspace_root,
                            choice.class_id,
                            choice.assignment_id,
                            manifest_revision=state.producer_head.revision,
                        )
                        print()
                        _print_publication_result(publication_result)
                    except QuillanAcademicResultPublicationError as error:
                        _print_error(error)
                    print()
                    pause_for_user()
                    continue

                if action == "5":
                    print()
                    if state.core_head is None:
                        print("No Core publication series exists.")
                        print()
                        pause_for_user()
                        continue
                    if state.core_head_withdrawal is not None:
                        print(
                            "The canonical Core head is withdrawn. "
                            "Use Republish after withdrawn head."
                        )
                        print()
                        pause_for_user()
                        continue
                    if state.producer_head is None:
                        print("No immutable producer head exists.")
                        print()
                        pause_for_user()
                        continue
                    print(
                        "Producer revision to supersede with: "
                        f"{state.producer_head.revision}"
                    )
                    print(
                        "Expected Core head: "
                        f"{state.core_head.publication_id}"
                    )
                    print(
                        "This creates/reconciles Core publication state. "
                        "It does not calculate a Grade."
                    )
                    confirmation = input("Type SUPERSEDE to continue: ").strip()
                    if confirmation != "SUPERSEDE":
                        print("Canceled: publication state was not changed.")
                        print()
                        pause_for_user()
                        continue
                    try:
                        publication_result = supersede_quillan_academic_results(
                            workspace_root,
                            choice.class_id,
                            choice.assignment_id,
                            manifest_revision=state.producer_head.revision,
                            expected_current_publication_id=(
                                state.core_head.publication_id
                            ),
                        )
                        print()
                        _print_publication_result(publication_result)
                    except QuillanAcademicResultPublicationError as error:
                        _print_error(error)
                    print()
                    pause_for_user()
                    continue

                if action == "6":
                    print()
                    if state.core_head is None or state.core_head_withdrawal is None:
                        print("The canonical Core head is not withdrawn.")
                        print()
                        pause_for_user()
                        continue
                    print(
                        "Withdrawn Core head: "
                        f"{state.core_head.publication_id}"
                    )
                    print(
                        "Quillan will create or reuse the required greater "
                        "producer successor before Core republication."
                    )
                    print("This does not calculate a Grade.")
                    confirmation = input("Type REPUBLISH to continue: ").strip()
                    if confirmation != "REPUBLISH":
                        print("Canceled: publication state was not changed.")
                        print()
                        pause_for_user()
                        continue
                    try:
                        publication_result = (
                            republish_quillan_academic_results_after_withdrawal(
                                workspace_root,
                                choice.class_id,
                                choice.assignment_id,
                                expected_withdrawn_head_publication_id=(
                                    state.core_head.publication_id
                                ),
                            )
                        )
                        print()
                        _print_publication_result(publication_result)
                    except QuillanAcademicResultPublicationError as error:
                        _print_error(error)
                    print()
                    pause_for_user()
                    continue

                if action == "7":
                    print()
                    publication_id = _prompt_publication_id(state)
                    if publication_id is None:
                        print()
                        pause_for_user()
                        continue
                    reason = input("Withdrawal reason: ").strip()
                    if not reason:
                        print("Canceled: withdrawal reason is required.")
                        print()
                        pause_for_user()
                        continue
                    print()
                    print(f"Publication to withdraw: {publication_id}")
                    print(
                        "Withdrawal preserves the Publication Record and "
                        "producer manifest."
                    )
                    confirmation = input("Type WITHDRAW to continue: ").strip()
                    if confirmation != "WITHDRAW":
                        print("Canceled: publication state was not changed.")
                        print()
                        pause_for_user()
                        continue
                    try:
                        withdrawal_result = withdraw_quillan_academic_result_publication(
                            workspace_root,
                            choice.class_id,
                            choice.assignment_id,
                            publication_id=publication_id,
                            reason=reason,
                        )
                        print()
                        _print_withdrawal_result(withdrawal_result)
                    except QuillanAcademicResultPublicationError as error:
                        _print_error(error)
                    print()
                    pause_for_user()
                    continue

                if action == "8":
                    print()
                    print(
                        "Rebuild Core's full disposable academic catalog from "
                        "canonical registry state."
                    )
                    confirmation = input("Type REBUILD to continue: ").strip()
                    if confirmation != "REBUILD":
                        print("Canceled: catalog was not rebuilt.")
                        print()
                        pause_for_user()
                        continue
                    try:
                        rebuild_full_academic_catalog(workspace_root)
                        print("Catalog rebuild: complete")
                    except QuillanAcademicResultPublicationError as error:
                        _print_error(error)
                    print()
                    pause_for_user()
                    continue

                print(f"Invalid selection. {navigation_hint()}")
                print()
                pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting Academic Result Publications.")
        return 0


__all__ = [
    "launch_academic_result_publication_menu",
]

"""Teacher-facing Academic Work Registration workflow."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TypeVar

from pds_core.academic_work_registrations import AcademicWorkRegistration
from pds_core.registry_services import AcademicWorkRegistrationRequest
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.academic_work_registration import (
    SUPPORTED_ACADEMIC_INTENTS,
    SUPPORTED_ACADEMIC_WORK_LIFECYCLES,
    QuillanAcademicWorkRegistrationError,
    QuillanAcademicWorkRegistrationPartialSuccessError,
    build_quillan_academic_work_registration_request,
    load_current_quillan_academic_work_registration,
    load_managed_assignment_registration_context,
    register_quillan_academic_work,
    update_quillan_academic_work_registration,
)
from quillan.assignment_picker import prompt_assignment_choice
from quillan.menu_navigation import (
    NavigationChoice,
    navigation_hint,
    parse_navigation_choice,
    print_navigation_options,
)

_T = TypeVar("_T", bound=str)


def _print_registration(registration: AcademicWorkRegistration | None) -> None:
    if registration is None:
        print("Registration status: not registered")
        return
    print("Registration status: registered")
    print(f"Registration revision: {registration.registration_revision}")
    print(f"Producer contract: {registration.producer_contract_version}")
    print(f"Title: {registration.title}")
    print(f"Work kind: {registration.work_kind}")
    print(f"Academic intent: {registration.academic_intent}")
    print(f"Lifecycle: {registration.lifecycle}")
    print(f"Created: {registration.created_at.isoformat()}")
    print(f"Updated: {registration.updated_at.isoformat()}")
    print("Source records:")
    for source in registration.source_records:
        version = "null" if source.contract_version is None else source.contract_version
        print(
            "- "
            f"{source.module_id}:{source.record_kind}:{source.record_id} "
            f"contract={version}"
        )


def _print_request(request: AcademicWorkRegistrationRequest) -> None:
    print("Proposed Academic Work Registration:")
    print(
        "Work: "
        f"{request.work.module_id}/{request.work.class_id}/{request.work.work_id}"
    )
    print(f"Producer contract: {request.producer_contract_version}")
    print(f"Title: {request.title}")
    print(f"Work kind: {request.work_kind}")
    print(f"Academic intent: {request.academic_intent}")
    print(f"Lifecycle: {request.lifecycle}")
    print("Source records:")
    for source in request.source_records:
        version = "null" if source.contract_version is None else source.contract_version
        print(
            "- "
            f"{source.module_id}:{source.record_kind}:{source.record_id} "
            f"contract={version}"
        )


def _prompt_choice(label: str, values: Sequence[_T]) -> _T | None:
    print(f"{label}:")
    for index, value in enumerate(values, start=1):
        print(f"{index}. {value}")
    print_navigation_options()
    while True:
        response = input(f"Select {label.lower()}: ").strip()
        navigation = parse_navigation_choice(response)
        if response == "" or navigation is NavigationChoice.BACK:
            return None
        if response.isdigit() and 1 <= int(response) <= len(values):
            return values[int(response) - 1]
        for value in values:
            if response == value:
                return value
        print(f"Invalid selection. {navigation_hint()}")


def _print_error(error: Exception) -> None:
    print(f"Error: {error}")
    if isinstance(error, QuillanAcademicWorkRegistrationPartialSuccessError):
        state = error.state
        print("Warning: durable Core registry state may exist.")
        print(f"Operation: {state.operation}")
        if state.registration is not None:
            print(f"Registration revision: {state.registration.registration_revision}")
        if state.canonical_path is not None:
            print(f"Canonical path: {state.canonical_path}")
        if state.current_selected is not None:
            print(f"Current selected: {'yes' if state.current_selected else 'no'}")
        print("Validate the Core registry before retrying.")


def print_registration_title_staleness_notices(
    workspace_root: str | Path,
    class_ids: Sequence[str],
    assignment_id: str,
    current_title: str,
) -> None:
    """Report stale registration titles without affecting a completed edit."""
    for class_id in class_ids:
        try:
            current = load_current_quillan_academic_work_registration(
                workspace_root, class_id, assignment_id
            )
        except Exception:
            print(
                "Notice: assignment saved, but Academic Work Registration status "
                f"could not be inspected for {class_id}. Registration state was "
                "not changed."
            )
            continue
        if current is not None and current.title != current_title:
            print(
                "Notice: Core Academic Work Registration "
                f"revision {current.registration_revision} for {class_id} still uses "
                f"title {current.title!r}. Use Academic Work Registration -> Update "
                "to record the current assignment title explicitly."
            )


def launch_academic_work_registration_menu() -> int:
    """Run the explicit teacher-controlled registration workflow."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    try:
        workspace_root = resolve_workspace_root()
    except WorkspaceRootError as error:
        _print_error(error)
        return 1

    try:
        while True:
            clear_screen()
            print_menu_header("Academic Work Registration")
            choice = prompt_assignment_choice(workspace_root)
            if choice is None:
                return 0
            try:
                context = load_managed_assignment_registration_context(
                    workspace_root, choice.class_id, choice.assignment_id
                )
                current = load_current_quillan_academic_work_registration(
                    workspace_root, choice.class_id, choice.assignment_id
                )
            except QuillanAcademicWorkRegistrationError as error:
                _print_error(error)
                print()
                pause_for_user()
                continue

            clear_screen()
            print_menu_header("Academic Work Registration")
            print(f"Class: {choice.class_id}")
            print(f"Assignment: {choice.assignment_id}")
            print(f"Current assignment title: {context.title}")
            print()
            _print_registration(current)
            if current is not None and current.title != context.title:
                print()
                print(
                    "Notice: the Core registration title is stale relative to the "
                    "current assignment title. Use Update to create a new registration "
                    "revision if you want Core to reflect the current title."
                )
            print()
            if current is None:
                print("1. Register")
                print("2. View again")
            else:
                print("1. Update")
                print("2. View again")
            print_navigation_options()
            action = input("Select an option: ").strip()
            navigation = parse_navigation_choice(action)
            if action == "" or navigation is NavigationChoice.BACK:
                return 0
            if action == "2":
                print()
                pause_for_user()
                continue
            if action != "1":
                print(f"Invalid selection. {navigation_hint()}")
                print()
                pause_for_user()
                continue

            intent = _prompt_choice("Academic intent", SUPPORTED_ACADEMIC_INTENTS)
            if intent is None:
                print("Canceled: no registration state was changed.")
                print()
                pause_for_user()
                continue
            lifecycle = _prompt_choice(
                "Lifecycle", SUPPORTED_ACADEMIC_WORK_LIFECYCLES
            )
            if lifecycle is None:
                print("Canceled: no registration state was changed.")
                print()
                pause_for_user()
                continue
            request = build_quillan_academic_work_registration_request(
                context,
                academic_intent=intent,
                lifecycle=lifecycle,
            )
            print()
            _print_request(request)
            print()

            confirmation_word = "REGISTER" if current is None else "UPDATE"
            confirmation = input(
                f"Type {confirmation_word} to write this Core registration: "
            ).strip()
            if confirmation != confirmation_word:
                print("Canceled: no registration state was changed.")
                print()
                pause_for_user()
                continue

            try:
                if current is None:
                    result = register_quillan_academic_work(
                        workspace_root,
                        choice.class_id,
                        choice.assignment_id,
                        academic_intent=intent,
                        lifecycle=lifecycle,
                    )
                else:
                    observed_revision = current.registration_revision
                    result = update_quillan_academic_work_registration(
                        workspace_root,
                        choice.class_id,
                        choice.assignment_id,
                        academic_intent=intent,
                        lifecycle=lifecycle,
                        expected_current_revision=observed_revision,
                    )
            except QuillanAcademicWorkRegistrationError as error:
                _print_error(error)
                print()
                pause_for_user()
                continue

            print()
            print(f"Disposition: {result.disposition}")
            print(f"Registration revision: {result.registration.registration_revision}")
            print(f"Title: {result.registration.title}")
            print(f"Academic intent: {result.registration.academic_intent}")
            print(f"Lifecycle: {result.registration.lifecycle}")
            print()
            pause_for_user()
    except KeyboardInterrupt:
        print("\nExiting Academic Work Registration.")
        return 0

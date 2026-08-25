"""Guided teacher workflow for publishing Quillan results for Meridian discovery."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal, TypeAlias, TypeVar

from pds_core.registry_services import AcademicWorkRegistrationRequest

from quillan.diagnostic_events import try_emit_diagnostic_event
from quillan.academic_result_manifest_generation import (
    QuillanManifestGenerationError,
    QuillanManifestGenerationPartialSuccessError,
    generate_academic_result_manifest,
)
from quillan.academic_result_publication import (
    AcademicResultPublicationResult,
    QuillanAcademicResultPublicationError,
    QuillanAcademicResultPublicationPartialSuccessError,
    publish_quillan_academic_results,
    supersede_quillan_academic_results,
)
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
from quillan.menu_navigation import (
    NavigationChoice,
    navigation_hint,
    parse_navigation_choice,
    print_navigation_options,
)
from quillan.share_results import (
    ShareResultsError,
    ShareResultsStatus,
    build_share_results_status,
)

_T = TypeVar("_T", bound=str)
_WorkflowOutcome: TypeAlias = Literal["completed", "cancelled", "stop"]
_ELIGIBLE_SHARE_LIFECYCLES = tuple(
    value
    for value in SUPPORTED_ACADEMIC_WORK_LIFECYCLES
    if value != "cancelled"
)


def launch_share_results_with_meridian_menu(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> int:
    """Guide one exact assignment through ordinary producer/Core sharing."""
    from quillan.menu import clear_screen, print_menu_header

    accepted_stale_revision: int | None = None
    while True:
        try:
            status = build_share_results_status(
                workspace_root,
                class_id,
                assignment_id,
            )
        except ShareResultsError:
            clear_screen()
            print_menu_header("Share Results with Meridian")
            print(f"Class: {class_id}")
            print(f"Assignment: {assignment_id}")
            print()
            print("Share status is unavailable because canonical state could not")
            print("be established safely. No share operation was attempted.")
            print()
            print_navigation_options()
            response = input("Select an option: ").strip()
            navigation = parse_navigation_choice(response)
            if response == "" or navigation is NavigationChoice.BACK:
                return 1
            continue

        clear_screen()
        print_menu_header("Share Results with Meridian")
        _print_share_status(status)

        stale_needs_choice = (
            status.registration_title_stale
            and status.registration_revision is not None
            and accepted_stale_revision != status.registration_revision
            and status.next_step
            not in {
                "already_shared_current",
                "advanced_republication_required",
            }
        )
        if stale_needs_choice:
            print()
            print("The current Core registration title is stale.")
            print("1. Continue using this registration")
            print("2. Update registration before sharing")
            print_navigation_options()
            response = input("Select an option: ").strip()
            navigation = parse_navigation_choice(response)
            if response == "" or navigation is NavigationChoice.BACK:
                return 0
            if response == "1":
                accepted_stale_revision = status.registration_revision
                continue
            if response == "2":
                outcome = _guided_registration(
                    workspace_root,
                    class_id,
                    assignment_id,
                    require_existing=True,
                )
                accepted_stale_revision = None
                if outcome == "stop":
                    return 1
                continue
            print(f"Invalid selection. {navigation_hint()}")
            input("Press Enter to continue...")
            continue

        print()
        action = _action_for_status(status)
        if action is not None:
            print(f"1. {action}")
        print("R. Refresh")
        print_navigation_options()
        print()
        response = input("Select an option: ").strip()
        navigation = parse_navigation_choice(response)
        if response == "" or navigation is NavigationChoice.BACK:
            return 0
        if response.casefold() == "r":
            continue
        if response != "1" or action is None:
            print(f"Invalid selection. {navigation_hint()}")
            input("Press Enter to continue...")
            continue

        if status.next_step == "register_academic_work":
            step_outcome = _guided_registration(
                workspace_root,
                class_id,
                assignment_id,
                require_existing=False,
            )
            accepted_stale_revision = None
        elif status.next_step == "update_cancelled_registration":
            step_outcome = _guided_registration(
                workspace_root,
                class_id,
                assignment_id,
                require_existing=True,
            )
            accepted_stale_revision = None
        elif status.next_step == "generate_manifest":
            step_outcome = _guided_manifest_generation(
                workspace_root,
                class_id,
                assignment_id,
            )
        elif status.next_step == "publish_initial":
            step_outcome = _guided_publication(
                workspace_root,
                class_id,
                assignment_id,
                intended_step="publish_initial",
            )
        elif status.next_step == "supersede_current":
            step_outcome = _guided_publication(
                workspace_root,
                class_id,
                assignment_id,
                intended_step="supersede_current",
            )
        else:
            raise AssertionError(
                f"Unexpected writable Share Results step: {status.next_step!r}"
            )

        if step_outcome == "stop":
            return 1


def _print_share_status(status: ShareResultsStatus) -> None:
    print(f"Class: {status.class_id}")
    print(f"Assignment: {status.assignment_title} ({status.assignment_id})")
    print()
    print(
        "This publishes Quillan's approved academic-result projection through "
        "Core so an authorized compatible Meridian installation can discover it."
    )
    print("It does not calculate a Grade or authorize feedback/student-work access.")
    print()

    if status.registration_revision is None:
        print("Academic Work Registration: not registered")
    else:
        print(
            "Academic Work Registration: "
            f"revision {status.registration_revision}"
        )
        print(f"Academic intent: {status.academic_intent}")
        print(f"Lifecycle: {status.lifecycle}")
        if status.registration_title_stale:
            print("Registration title: stale")
        else:
            print("Registration title: current")

    if status.native_result_state_valid:
        print(
            "Native result records ready: "
            f"{status.represented_native_result_count}"
        )
    else:
        print("Native result records ready: unavailable")

    if status.producer_head_revision is None:
        print("Producer manifest head: none")
    else:
        print(f"Producer manifest head: revision {status.producer_head_revision}")

    if status.core_head_publication_id is None:
        print("Core publication head: none")
    else:
        suffix = " (withdrawn)" if status.core_head_withdrawn else ""
        print(
            "Core publication head: "
            f"{status.core_head_publication_id}{suffix}"
        )
    current = status.current_selectable_publication_id or "none"
    print(f"Current selectable publication: {current}")
    print(
        "Catalog status: "
        + ("available" if status.catalog_available else "unavailable")
    )

    if status.review_context is None:
        print("Review completion context: unavailable")
    else:
        review = status.review_context
        print(
            "Review completion: "
            f"{review.complete_count} / {review.roster_count}"
        )
        print(f"Needs work: {review.needs_work_count}")
        print(f"Attention required: {review.attention_count}")

    print()
    print(f"Next step: {_next_step_label(status)}")
    if status.next_step == "already_shared_current":
        print(
            "The current producer result is already published through Core "
            "and ready for authorized compatible Meridian discovery."
        )
    elif status.next_step == "advanced_republication_required":
        print(
            "The canonical Core head is withdrawn. Use the existing advanced "
            "Academic Result Publications workflow for explicit republication."
        )
    elif status.next_step == "resolve_native_result_state":
        print(
            "Resolve the native Quillan result-state problem before generating "
            "another immutable manifest."
        )
    elif status.next_step == "resolve_publication_state":
        print(
            "Publication history is not safe for an ordinary guided transition. "
            "Use the advanced publication workflow to inspect it."
        )


def _action_for_status(status: ShareResultsStatus) -> str | None:
    labels = {
        "register_academic_work": "Register Academic Work",
        "update_cancelled_registration": "Update Academic Work Registration",
        "generate_manifest": "Generate / exact replay Academic Result Manifest",
        "publish_initial": "Publish first result set",
        "supersede_current": "Supersede current result set",
    }
    return labels.get(status.next_step)


def _next_step_label(status: ShareResultsStatus) -> str:
    labels = {
        "register_academic_work": "Register Academic Work",
        "update_cancelled_registration": "Update cancelled registration",
        "resolve_native_result_state": "Resolve native result state",
        "generate_manifest": "Generate / exact replay manifest",
        "publish_initial": "Publish first result set",
        "supersede_current": "Supersede current result set",
        "already_shared_current": "Already published and current",
        "advanced_republication_required": "Advanced republication required",
        "resolve_publication_state": "Resolve publication state",
    }
    return labels[status.next_step]


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


def _print_registration_request(
    request: AcademicWorkRegistrationRequest,
) -> None:
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


def _guided_registration(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    *,
    require_existing: bool,
) -> _WorkflowOutcome:
    try:
        context = load_managed_assignment_registration_context(
            workspace_root,
            class_id,
            assignment_id,
        )
        current = load_current_quillan_academic_work_registration(
            workspace_root,
            class_id,
            assignment_id,
        )
    except QuillanAcademicWorkRegistrationError:
        print("Academic Work Registration state could not be loaded safely.")
        input("Press Enter to continue...")
        return "stop"

    if require_existing and current is None:
        print("Registration changed concurrently; refresh before continuing.")
        input("Press Enter to continue...")
        return "cancelled"
    if not require_existing and current is not None:
        print("Registration changed concurrently; refresh before continuing.")
        input("Press Enter to continue...")
        return "cancelled"

    intent = _prompt_choice("Academic intent", SUPPORTED_ACADEMIC_INTENTS)
    if intent is None:
        print("Canceled: no registration state was changed.")
        return "cancelled"
    lifecycle = _prompt_choice("Lifecycle", _ELIGIBLE_SHARE_LIFECYCLES)
    if lifecycle is None:
        print("Canceled: no registration state was changed.")
        return "cancelled"

    request = build_quillan_academic_work_registration_request(
        context,
        academic_intent=intent,
        lifecycle=lifecycle,
    )
    print()
    _print_registration_request(request)
    print()
    word = "REGISTER" if current is None else "UPDATE"
    confirmation = input(
        f"Type {word} to write this Core registration: "
    ).strip()
    if confirmation != word:
        print("Canceled: no registration state was changed.")
        return "cancelled"

    try:
        if current is None:
            result = register_quillan_academic_work(
                workspace_root,
                class_id,
                assignment_id,
                academic_intent=intent,
                lifecycle=lifecycle,
            )
        else:
            observed_revision = current.registration_revision
            result = update_quillan_academic_work_registration(
                workspace_root,
                class_id,
                assignment_id,
                academic_intent=intent,
                lifecycle=lifecycle,
                expected_current_revision=observed_revision,
            )
    except QuillanAcademicWorkRegistrationPartialSuccessError as error:
        print("Warning: durable Core registration state may exist.")
        if error.state.registration is not None:
            print(
                "Registration revision: "
                f"{error.state.registration.registration_revision}"
            )
        print("Stop and inspect Academic Work Registration before retrying.")
        return "stop"
    except QuillanAcademicWorkRegistrationError:
        print("Academic Work Registration did not complete.")
        input("Press Enter to continue...")
        return "cancelled"

    print()
    print(f"Disposition: {result.disposition}")
    print(
        "Registration revision: "
        f"{result.registration.registration_revision}"
    )
    print(f"Title: {result.registration.title}")
    print(f"Academic intent: {result.registration.academic_intent}")
    print(f"Lifecycle: {result.registration.lifecycle}")
    return "completed"


def _guided_manifest_generation(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> _WorkflowOutcome:
    print()
    print("Generate / exact replay Academic Result Manifest")
    print()
    print(
        "This validates current canonical Quillan state and either byte-exactly "
        "reuses the producer head or creates the immutable successor required by "
        "Quillan revision policy."
    )
    print("This does not publish through Core.")
    confirmation = input("Type GENERATE to continue: ").strip()
    if confirmation != "GENERATE":
        print("Canceled: no manifest revision was generated.")
        return "cancelled"

    try:
        result = generate_academic_result_manifest(
            workspace_root,
            class_id,
            assignment_id,
        )
    except QuillanManifestGenerationPartialSuccessError as error:
        print("Warning: an immutable manifest revision may already be durable.")
        print(f"Operation: {error.state.operation}")
        print(f"Revision: {error.state.revision}")
        print(f"Manifest path: {error.state.relative_path}")
        if error.state.expected_sha256 is not None:
            print(f"Expected SHA-256: {error.state.expected_sha256}")
        print("Stop and validate producer storage before retrying.")
        return "stop"
    except QuillanManifestGenerationError:
        print("Academic Result Manifest generation did not complete.")
        input("Press Enter to continue...")
        return "cancelled"

    print()
    print(f"Disposition: {result.disposition}")
    print(f"Reason: {result.reason}")
    print(f"Producer revision: {result.revision}")
    print(f"Represented students: {len(result.manifest.students)}")
    print(f"Manifest path: {result.relative_path}")
    print(f"Manifest SHA-256: {result.sha256}")
    return "completed"


def _guided_publication(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    *,
    intended_step: Literal["publish_initial", "supersede_current"],
) -> _WorkflowOutcome:
    """Reload, preview, confirm, recheck, and invoke one exact publication."""
    try:
        preview = build_share_results_status(
            workspace_root,
            class_id,
            assignment_id,
        )
    except ShareResultsError:
        print("Publication status changed or became unavailable before preview.")
        return "cancelled"
    if preview.next_step != intended_step:
        print("Publication status changed before preview; no publication was written.")
        return "cancelled"
    if (
        preview.producer_head_revision is None
        or preview.registration_revision is None
    ):
        print("Publication prerequisites are no longer available.")
        return "cancelled"

    word = "PUBLISH" if intended_step == "publish_initial" else "SUPERSEDE"
    operation = (
        "Publish first result set"
        if intended_step == "publish_initial"
        else "Supersede current result set"
    )
    print()
    print(f"Operation: {operation}")
    print(f"Class: {preview.class_id}")
    print(
        "Assignment: "
        f"{preview.assignment_title} ({preview.assignment_id})"
    )
    print(
        "Academic Work registration revision: "
        f"{preview.registration_revision}"
    )
    print(f"Academic intent: {preview.academic_intent}")
    print(f"Lifecycle: {preview.lifecycle}")
    print(f"Producer manifest revision: {preview.producer_head_revision}")
    print(
        "Represented students: "
        f"{preview.represented_native_result_count}"
    )
    print(f"Manifest SHA-256: {preview.producer_head_sha256}")
    if intended_step == "publish_initial":
        print("Core publication head: none")
    else:
        print(
            "Expected Core publication head: "
            f"{preview.core_head_publication_id}"
        )
    print()
    confirmation = input(
        f"Type {word} to authorize this Core publication: "
    ).strip()
    if confirmation != word:
        print("Canceled: no Core publication operation was started.")
        return "cancelled"

    try:
        fresh = build_share_results_status(
            workspace_root,
            class_id,
            assignment_id,
        )
    except ShareResultsError as error:
        try_emit_diagnostic_event(
            workspace_root,
            component="publication",
            workflow="share_results",
            stage="preflight",
            outcome="blocked",
            code="share_state_changed",
            class_id=class_id,
            assignment_id=assignment_id,
            exception=error,
        )
        print("Publication status changed or became unavailable after confirmation.")
        print("No Core publication operation was started.")
        return "cancelled"

    if not _same_publication_preview(preview, fresh, intended_step):
        try_emit_diagnostic_event(
            workspace_root,
            component="publication",
            workflow="share_results",
            stage="preflight",
            outcome="blocked",
            code="share_state_changed",
            class_id=class_id,
            assignment_id=assignment_id,
        )
        print("Publication state changed after confirmation.")
        print("No Core publication operation was started.")
        return "cancelled"

    manifest_revision = fresh.producer_head_revision
    if manifest_revision is None:
        print("Producer manifest head disappeared before publication.")
        return "cancelled"

    try:
        if intended_step == "publish_initial":
            result = publish_quillan_academic_results(
                workspace_root,
                class_id,
                assignment_id,
                manifest_revision=manifest_revision,
            )
        else:
            expected_id = fresh.core_head_publication_id
            if expected_id is None:
                print("Canonical Core head disappeared before supersession.")
                return "cancelled"
            result = supersede_quillan_academic_results(
                workspace_root,
                class_id,
                assignment_id,
                manifest_revision=manifest_revision,
                expected_current_publication_id=expected_id,
            )
    except QuillanAcademicResultPublicationPartialSuccessError as error:
        _print_publication_partial_success(error)
        return "stop"
    except QuillanAcademicResultPublicationError:
        print("Core publication did not complete.")
        print("Refresh canonical status before deciding whether to retry.")
        return "cancelled"

    return _print_verified_publication_result(
        workspace_root,
        class_id,
        assignment_id,
        result,
    )


def _same_publication_preview(
    before: ShareResultsStatus,
    after: ShareResultsStatus,
    intended_step: Literal["publish_initial", "supersede_current"],
) -> bool:
    return (
        after.next_step == intended_step
        and after.registration_revision == before.registration_revision
        and after.producer_head_revision == before.producer_head_revision
        and after.producer_head_sha256 == before.producer_head_sha256
        and after.core_head_publication_id == before.core_head_publication_id
        and after.core_head_revision == before.core_head_revision
        and after.core_head_withdrawn == before.core_head_withdrawn
    )


def _print_publication_partial_success(
    error: QuillanAcademicResultPublicationPartialSuccessError,
) -> None:
    state = error.state
    print("Warning: a Core publication operation may already be durable.")
    print(f"Operation: {state.operation}")
    print(f"Canonical state: {state.canonical_state}")
    if state.publication is not None:
        print(f"Publication ID: {state.publication.publication_id}")
        print(f"Producer revision: {state.publication.record_set_revision}")
    if state.manifest is not None:
        print(f"Manifest path: {state.manifest.relative_path}")
        print(f"Manifest SHA-256: {state.manifest.sha256}")
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
    print(f"Recommended next action: {state.recommended_next_action}")
    print("Stop and inspect canonical publication status before retrying.")


def _print_verified_publication_result(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    result: AcademicResultPublicationResult,
) -> _WorkflowOutcome:
    try:
        final = build_share_results_status(
            workspace_root,
            class_id,
            assignment_id,
        )
    except ShareResultsError:
        print("Core publication completed, but guided final status is unavailable.")
        print("Inspect Academic Result Publications before retrying anything.")
        return "stop"

    publication_id = result.publication.publication_id
    if (
        final.next_step != "already_shared_current"
        or final.core_head_publication_id != publication_id
        or final.current_selectable_publication_id != publication_id
        or not final.catalog_available
        or not result.catalog.publication.is_series_head
        or not result.catalog.publication.is_current_selectable
    ):
        print("Core publication completed, but final guided reconciliation failed.")
        print("Inspect Academic Result Publications before retrying anything.")
        return "stop"

    print()
    print("Share Results with Meridian")
    print()
    print("Status: published through Core")
    print(f"Disposition: {result.disposition}")
    print(f"Publication ID: {publication_id}")
    print(f"Producer revision: {result.publication.record_set_revision}")
    print(
        "Academic Work registration revision: "
        f"{result.registration.registration_revision}"
    )
    print("Series head: yes")
    print("Current selectable publication: yes")
    print("Catalog reconciliation: verified")
    print()
    print("Meridian handoff:")
    print("Ready for authorized compatible Meridian discovery.")
    return "completed"


__all__ = ["launch_share_results_with_meridian_menu"]

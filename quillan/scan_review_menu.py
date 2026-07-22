"""Teacher-facing menu workflow for resolving Quillan scan review items."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pds_core.classes import list_class_folders
from pds_core.routing_models import ModuleWorkRef

from quillan.assignment_discovery import discover_quillan_assignments
from quillan.assignment_submission_assembly import assemble_assignment_submissions
from quillan.cli_app.output import (
    print_assignment_submission_assembly,
    print_assignment_submission_status,
)
from quillan.post_dispatch_review_resolution import (
    POST_DISPATCH_GENERIC_RESOLUTION_ACTIONS,
    PostDispatchReviewItem,
    PostDispatchReviewResolutionError,
    discover_post_dispatch_review_items,
    open_post_dispatch_possible_path,
    post_dispatch_retry_proves_resolution,
    resolve_post_dispatch_after_successful_retry,
    resolve_post_dispatch_review_occurrence,
)
from quillan.scan_review_resolution import (
    DEFAULT_RESOLUTION_MESSAGES,
    QuillanReviewItem,
    QuillanRouteOption,
    ScanReviewResolutionError,
    discover_scan_review_route_options,
    discover_scan_review_items,
    resolve_scan_review_item,
)
from quillan.student_display import student_display_lookup
from quillan.submission_status import list_assignment_submission_status
from quillan.work_paths import quillan_work_ref

_ACTIONS: tuple[tuple[str, str], ...] = (
    ("route_selected", "Use selected registered route"),
    ("route_corrected", "Correct to selected registered route"),
    ("rescan_needed", "Rescan needed"),
    ("cannot_route", "Cannot route safely"),
    ("evidence_filed", "Evidence filed elsewhere"),
    ("dismissed_duplicate", "Dismiss duplicate"),
    ("deferred", "Defer for later"),
    ("other", "Other"),
)

_POST_ACTION_LABELS = {
    "resolved_after_retry": "Resolved after an explicit successful retry",
    "rescan_needed": "Rescan needed",
    "record_corrected": "Record corrected",
    "cannot_recover": "Cannot recover safely",
    "dismissed_duplicate": "Dismiss duplicate",
    "deferred": "Defer for later",
    "other": "Other",
}


def launch_scan_review_resolution_menu(
    workspace_root: Path,
    class_id: str | None = None,
    assignment_id: str | None = None,
) -> int:
    """Open the coherent Core/post-dispatch Scan Review workflow."""
    if (class_id is None) != (assignment_id is None):
        raise ValueError("class_id and assignment_id must be supplied together.")
    try:
        core = discover_scan_review_items(
            workspace_root,
            class_id=class_id,
            assignment_id=assignment_id,
        )
        if class_id is None or assignment_id is None:
            work_refs = set(_active_scan_review_work_refs(workspace_root))
            for item in core.items:
                if item.class_id is None or item.assignment_id is None:
                    continue
                try:
                    work_refs.add(
                        quillan_work_ref(item.class_id, item.assignment_id)
                    )
                except (TypeError, ValueError):
                    continue
            if not work_refs and not core.items:
                return _launch_core_review_menu(workspace_root)
            return _launch_global_scan_review_menu(
                workspace_root,
                tuple(
                    sorted(
                        work_refs,
                        key=lambda item: (item.class_id, item.work_id),
                    )
                ),
                has_unscoped=any(
                    item.class_id is None or item.assignment_id is None
                    for item in core.items
                ),
                has_core=bool(core.items),
            )
        post = discover_post_dispatch_review_items(
            workspace_root, quillan_work_ref(class_id, assignment_id)
        )
    except (ScanReviewResolutionError, PostDispatchReviewResolutionError) as error:
        from quillan.menu import clear_screen, pause_for_user, print_menu_header

        clear_screen()
        print_menu_header("Scan Review")
        print(f"Error: {error}")
        print()
        pause_for_user()
        return 1
    if not post.items:
        return _launch_core_review_menu(workspace_root, class_id, assignment_id)
    if not core.items:
        return _launch_post_dispatch_review_menu(
            workspace_root, class_id, assignment_id
        )
    return _launch_review_source_menu(workspace_root, class_id, assignment_id)


def _launch_global_scan_review_menu(
    workspace_root: Path,
    work_refs: tuple[ModuleWorkRef, ...],
    *,
    has_unscoped: bool,
    has_core: bool,
) -> int:
    """Keep scoped, unscoped, and global Core review paths reachable."""
    from quillan.menu import clear_screen, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    while True:
        clear_screen()
        print_menu_header("Scan Review")
        if work_refs:
            print("1. Select assignment-scoped problems")
        if has_unscoped:
            print("2. Unscoped Core routing problems")
        if has_core:
            print("3. All Core routing problems")
        print("B. Back")
        print()
        choice = input("Select scan review scope: ").strip()
        if choice == "" or parse_navigation_choice(choice) is NavigationChoice.BACK:
            return 0
        if choice == "1" and work_refs:
            selected = _prompt_scan_review_work(work_refs)
            if selected is not None:
                launch_scan_review_resolution_menu(
                    workspace_root, selected.class_id, selected.work_id
                )
        elif choice == "2" and has_unscoped:
            _launch_core_review_menu(workspace_root, unscoped_only=True)
        elif choice == "3" and has_core:
            _launch_core_review_menu(workspace_root)


def _active_scan_review_work_refs(
    workspace_root: Path,
) -> tuple[ModuleWorkRef, ...]:
    """Return deterministic work refs with active Quillan post-dispatch items."""
    refs: set[ModuleWorkRef] = set()
    for folder in list_class_folders(workspace_root):
        for assignment in discover_quillan_assignments(
            workspace_root, folder.class_id
        ):
            try:
                work_ref = quillan_work_ref(folder.class_id, assignment.assignment_id)
                discovery = discover_post_dispatch_review_items(
                    workspace_root, work_ref
                )
            except PostDispatchReviewResolutionError:
                continue
            if discovery.items:
                refs.add(work_ref)
    return tuple(sorted(refs, key=lambda item: (item.class_id, item.work_id)))


def _prompt_scan_review_work(
    work_refs: tuple[ModuleWorkRef, ...],
) -> ModuleWorkRef | None:
    from quillan.menu import clear_screen, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    if type(work_refs) is not tuple or any(
        type(item) is not ModuleWorkRef for item in work_refs
    ):
        raise ValueError("work_refs must contain exact ModuleWorkRef values.")
    clear_screen()
    print_menu_header("Select Scan Review Assignment")
    for index, work_ref in enumerate(work_refs, start=1):
        print(
            f"{index}. Class: {work_ref.class_id}; "
            f"Assignment: {work_ref.work_id}"
        )
    print("B. Back")
    print()
    choice = input("Select assignment work: ").strip()
    if choice == "" or parse_navigation_choice(choice) is NavigationChoice.BACK:
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(work_refs):
        return work_refs[int(choice) - 1]
    return None


def _launch_review_source_menu(
    workspace_root: Path, class_id: str, assignment_id: str
) -> int:
    from quillan.menu import clear_screen, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    while True:
        clear_screen()
        print_menu_header("Scan Review")
        print(f"Class: {class_id}")
        print(f"Assignment: {assignment_id}")
        print()
        print("1. Core routing problems")
        print("2. Quillan post-dispatch problems")
        print("3. All active problems")
        print("B. Back")
        print()
        choice = input("Select problem source: ").strip()
        if choice == "" or parse_navigation_choice(choice) is NavigationChoice.BACK:
            return 0
        if choice == "1":
            _launch_core_review_menu(workspace_root, class_id, assignment_id)
        elif choice == "2":
            _launch_post_dispatch_review_menu(
                workspace_root, class_id, assignment_id
            )
        elif choice == "3":
            _launch_combined_review_menu(workspace_root, class_id, assignment_id)


def _launch_core_review_menu(
    workspace_root: Path,
    class_id: str | None = None,
    assignment_id: str | None = None,
    *,
    unscoped_only: bool = False,
) -> int:
    """List Core-owned items and write Core-owned resolutions."""
    from quillan.menu import clear_screen, pause_for_user, print_menu_header
    from quillan.menu_navigation import (
        NavigationChoice,
        navigation_hint,
        parse_navigation_choice,
        print_navigation_options,
    )

    while True:
        clear_screen()
        print_menu_header("Resolve Scan Review Items")
        try:
            discovery = discover_scan_review_items(
                workspace_root,
                class_id=class_id,
                assignment_id=assignment_id,
            )
            if unscoped_only:
                discovery = type(discovery)(
                    items=tuple(
                        item
                        for item in discovery.items
                        if item.class_id is None or item.assignment_id is None
                    ),
                    warnings=discovery.warnings,
                )
        except ScanReviewResolutionError as error:
            print(f"Error: {error}")
            print()
            pause_for_user()
            return 1
        if not discovery.items:
            print("There are no unresolved or deferred scan review items.")
            if discovery.warnings:
                print(
                    f"Skipped {len(discovery.warnings)} malformed or unreadable "
                    "metadata file(s)."
                )
            print()
            pause_for_user()
            return 0

        for index, item in enumerate(discovery.items, start=1):
            page = "" if item.source_page_number is None else f", page {item.source_page_number}"
            print(
                f"{index}. {item.source_filename}{page} — "
                f"{item.failure_category} ({item.display_status})"
            )
        if discovery.warnings:
            print(
                f"\nSkipped {len(discovery.warnings)} malformed or unreadable "
                "metadata file(s)."
            )
        print_navigation_options()
        print()
        choice = input("Select a review item: ").strip()
        navigation = parse_navigation_choice(choice)
        if choice == "" or navigation is NavigationChoice.BACK:
            return 0
        if not choice.isdigit() or not 1 <= int(choice) <= len(discovery.items):
            print(f"Invalid selection. {navigation_hint()}")
            print()
            pause_for_user()
            continue

        item = discovery.items[int(choice) - 1]
        _resolve_core_item(workspace_root, item)


def _resolve_core_item(workspace_root: Path, item: QuillanReviewItem) -> None:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    action = _prompt_action(item)
    if action is None:
        return
    route = (
        _prompt_route_option(workspace_root, item)
        if action in {"route_selected", "route_corrected"}
        else None
    )
    if action in {"route_selected", "route_corrected"} and route is None:
        return
    message = _prompt_message(action)
    if message is None:
        return
    evidence_path = _prompt_evidence_path() if action == "evidence_filed" else None
    if not _confirm_core_resolution(item, action, route):
        return
    clear_screen()
    print_menu_header("Core Routing Review Result")
    try:
        result = resolve_scan_review_item(
            workspace_root,
            item.failure_id,
            action=action,
            message=message,
            evidence_path=evidence_path,
            route_locator=None if route is None else route.locator,
            target=None if route is None else route.target,
        )
    except ScanReviewResolutionError as error:
        print(f"Could not save the Core routing-review decision: {error}")
    else:
        print(f"Core routing-review item {result.resolution_status}.")
        print(f"Failure ID: {result.failure_id}")
        print(f"Resolution record: {result.resolution_metadata_relative_path}")
    print()
    pause_for_user()


def _prompt_action(item: QuillanReviewItem) -> str | None:
    from quillan.menu import clear_screen, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    clear_screen()
    print_menu_header("Scan Review Details")
    print(f"Category: {item.failure_category}")
    print(f"What failed: {item.failure_message}")
    print(f"Source: {item.source_filename}")
    print(f"Page: {_display(item.source_page_number)}")
    if item.retained_source_path is not None:
        print(f"Retained source: {item.retained_source_path}")
    if item.review_copy_path is not None:
        print(f"Review evidence: {item.review_copy_path}")
    print(f"Review record: {item.failure_metadata_relative_path}")
    print(f"Class: {_display(item.class_id)}")
    print(f"Assignment: {_display(item.assignment_id)}")
    print(f"Student: {_display(item.student_id)}")
    print()
    input("Press Enter to choose an action...")

    clear_screen()
    print_menu_header("Choose Scan Review Action")
    for index, (_, label) in enumerate(_ACTIONS, start=1):
        print(f"{index}. {label}")
    print("B. Back")
    print()
    choice = input("Select an action: ").strip()
    if parse_navigation_choice(choice) is NavigationChoice.BACK or choice == "":
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(_ACTIONS):
        return _ACTIONS[int(choice) - 1][0]
    return None


def _prompt_route_option(
    workspace_root: Path, item: QuillanReviewItem
) -> QuillanRouteOption | None:
    from quillan.assignment_picker import prompt_assignment_choice
    from quillan.menu import clear_screen, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    class_id, assignment_id = item.class_id, item.assignment_id
    if class_id is None or assignment_id is None:
        clear_screen()
        print_menu_header("Select Route Work")
        chosen_assignment = prompt_assignment_choice(workspace_root)
        if chosen_assignment is None:
            return None
        class_id = chosen_assignment.class_id
        assignment_id = chosen_assignment.assignment_id
    try:
        discovery = discover_scan_review_route_options(
            workspace_root, class_id, assignment_id
        )
    except ScanReviewResolutionError as error:
        clear_screen()
        print_menu_header("Select Registered Route")
        print(f"Could not load route choices: {error}")
        input("Press Enter to return...")
        return None
    clear_screen()
    print_menu_header("Select Registered Route")
    print(f"Class: {class_id}")
    print(f"Assignment: {assignment_id}")
    print()
    labels = student_display_lookup(workspace_root, class_id)
    for index, route in enumerate(discovery.routes, start=1):
        student = labels.get(route.student_id, route.student_id)
        print(
            f"{index}. {student}; page {route.logical_page}/{route.total_pages}; "
            f"route {route.locator.route_id}"
        )
    if discovery.warnings:
        print(f"Skipped invalid routes: {len(discovery.warnings)}")
    if not discovery.routes:
        print("No valid current Quillan routes are available for this assignment.")
        input("Press Enter to return...")
        return None
    print("B. Back")
    print()
    choice = input("Select route: ").strip()
    if choice == "" or parse_navigation_choice(choice) is NavigationChoice.BACK:
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(discovery.routes):
        selected_route = discovery.routes[int(choice) - 1]
    else:
        return None
    clear_screen()
    print_menu_header("Registered Route Details")
    print(
        f"Student: {labels.get(selected_route.student_id, selected_route.student_id)}"
    )
    print(
        f"Logical page: {selected_route.logical_page} of {selected_route.total_pages}"
    )
    print(f"Route ID: {selected_route.locator.route_id}")
    print(f"Page record ID: {selected_route.target.record_id}")
    print()
    confirmation = input("Use this registered route? [y/N]: ").strip().casefold()
    return selected_route if confirmation in {"y", "yes"} else None


def _confirm_core_resolution(
    item: QuillanReviewItem,
    action: str,
    route: QuillanRouteOption | None,
) -> bool:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Confirm Core Routing Review Decision")
    print(f"Failure ID: {item.failure_id}")
    print(f"Action: {action}")
    if route is not None:
        print(f"Selected route: {route.locator.route_id}")
        print(f"Selected page record: {route.target.record_id}")
    print("This appends an immutable Core resolution record.")
    print()
    return input("Save this decision? [y/N]: ").strip().casefold() in {"y", "yes"}


def _launch_post_dispatch_review_menu(
    workspace_root: Path, class_id: str, assignment_id: str
) -> int:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    while True:
        clear_screen()
        print_menu_header("Quillan Post-Dispatch Problems")
        try:
            discovery = discover_post_dispatch_review_items(
                workspace_root, quillan_work_ref(class_id, assignment_id)
            )
        except PostDispatchReviewResolutionError as error:
            print(f"Error: {error}")
            print()
            pause_for_user()
            return 1
        if not discovery.items:
            print("There are no unresolved or deferred post-dispatch problems.")
            print()
            pause_for_user()
            return 0
        for index, item in enumerate(discovery.items, start=1):
            occurrence = item.occurrence.occurrence
            student = occurrence.student_id or "assignment-level"
            print(
                f"{index}. {occurrence.category}; {student}; "
                f"{item.display_status}"
            )
        if discovery.warnings:
            print(f"Skipped malformed records: {len(discovery.warnings)}")
        print("B. Back")
        print()
        choice = input("Select a post-dispatch problem: ").strip()
        if choice == "" or parse_navigation_choice(choice) is NavigationChoice.BACK:
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(discovery.items):
            _resolve_post_dispatch_item(
                workspace_root, discovery.items[int(choice) - 1]
            )


def _resolve_post_dispatch_item(
    workspace_root: Path, item: PostDispatchReviewItem
) -> None:
    from quillan.menu import clear_screen, print_menu_header

    occurrence = item.occurrence.occurrence
    clear_screen()
    print_menu_header("Post-Dispatch Problem Details")
    print(f"Category: {occurrence.category}")
    print(f"Stage: {occurrence.stage}")
    print(f"What failed: {occurrence.failure_message}")
    print(f"Class: {occurrence.class_id}")
    print(f"Assignment: {occurrence.assignment_id}")
    print(f"Student: {occurrence.student_id or 'assignment-level'}")
    print(f"Issuances: {len(occurrence.issuance_ids)}")
    print(f"Pages: {len(occurrence.page_ids)}")
    print(f"Observations: {len(occurrence.observation_ids)}")
    if occurrence.issuance_ids:
        print(f"Issuance IDs: {', '.join(occurrence.issuance_ids)}")
    if occurrence.page_ids:
        print(f"Page IDs: {', '.join(occurrence.page_ids)}")
    if occurrence.route_ids:
        print(f"Route IDs: {', '.join(occurrence.route_ids)}")
    if occurrence.observation_ids:
        print(f"Observation IDs: {', '.join(occurrence.observation_ids)}")
    if occurrence.source_scan_ids:
        print(f"Source scan IDs: {', '.join(occurrence.source_scan_ids)}")
    for path in (
        *occurrence.possible_evidence_paths,
        *occurrence.possible_manifest_paths,
    ):
        print(f"Possible durable path: {path}")
    print(f"Occurrence: {item.occurrence.relative_path}")
    print()
    input("Press Enter to choose an action...")
    _launch_post_dispatch_context_actions(workspace_root, item)


def _launch_post_dispatch_context_actions(
    workspace_root: Path,
    item: PostDispatchReviewItem,
) -> None:
    from quillan.menu import clear_screen, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    occurrence = item.occurrence.occurrence
    retry_supported = occurrence.category in {
        "submission_assembly",
        "mixed_issuance",
        "manifest_conflict",
    }
    actions: list[tuple[str, str]] = []
    if retry_supported:
        actions.append(("retry", "Retry submission assembly"))
    actions.append(("status", "View current submission status"))
    if occurrence.possible_evidence_paths:
        actions.append(("evidence", "Open validated possible evidence"))
    if occurrence.possible_manifest_paths:
        actions.append(("manifest", "Open validated possible manifest"))
    actions.append(("resolve", "Record another resolution"))

    clear_screen()
    print_menu_header("Choose Post-Dispatch Action")
    print(f"Class: {occurrence.class_id}")
    print(f"Assignment: {occurrence.assignment_id}")
    print(f"Failure ID: {occurrence.failure_id}")
    print()
    for index, (_, label) in enumerate(actions, start=1):
        print(f"{index}. {label}")
    print("B. Back")
    print()
    choice = input("Select an action: ").strip()
    if choice == "" or parse_navigation_choice(choice) is NavigationChoice.BACK:
        return
    if not choice.isdigit() or not 1 <= int(choice) <= len(actions):
        return
    action = actions[int(choice) - 1][0]
    if action == "retry":
        _retry_post_dispatch_assembly(workspace_root, item)
    elif action == "status":
        _view_post_dispatch_status(workspace_root, item)
    elif action == "evidence":
        _open_post_dispatch_context_path(workspace_root, item, "evidence")
    elif action == "manifest":
        _open_post_dispatch_context_path(workspace_root, item, "manifest")
    else:
        _record_post_dispatch_resolution(workspace_root, item)


def _record_post_dispatch_resolution(
    workspace_root: Path,
    item: PostDispatchReviewItem,
) -> None:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    occurrence = item.occurrence.occurrence
    actions = tuple(POST_DISPATCH_GENERIC_RESOLUTION_ACTIONS)
    clear_screen()
    print_menu_header("Record Post-Dispatch Resolution")
    for index, action in enumerate(actions, start=1):
        print(f"{index}. {_POST_ACTION_LABELS[action]}")
    print("B. Back")
    print()
    choice = input("Select a resolution: ").strip()
    if choice == "" or parse_navigation_choice(choice) is NavigationChoice.BACK:
        return
    if not choice.isdigit() or not 1 <= int(choice) <= len(actions):
        return
    action = actions[int(choice) - 1]
    clear_screen()
    print_menu_header("Post-Dispatch Review Note")
    prompt = "Teacher message (required): " if action == "other" else "Teacher message (optional): "
    message = input(prompt).strip() or None
    if action == "other" and message is None:
        return
    clear_screen()
    print_menu_header("Confirm Post-Dispatch Decision")
    print(f"Failure ID: {occurrence.failure_id}")
    print(f"Action: {action}")
    print("The occurrence and all durable work records remain unchanged.")
    print()
    if input("Save this decision? [y/N]: ").strip().casefold() not in {"y", "yes"}:
        return
    clear_screen()
    print_menu_header("Post-Dispatch Review Result")
    try:
        result = resolve_post_dispatch_review_occurrence(
            workspace_root,
            item.occurrence.work_ref,
            occurrence.failure_id,
            action=action,
            message=message,
        )
    except PostDispatchReviewResolutionError as error:
        print(f"Could not save the post-dispatch decision: {error}")
    else:
        print(f"Post-dispatch occurrence {result.resolution.status}.")
        print(f"Failure ID: {result.resolution.failure_id}")
        print(f"Resolution record: {result.relative_path}")
    print()
    pause_for_user()


def _retry_post_dispatch_assembly(
    workspace_root: Path,
    item: PostDispatchReviewItem,
) -> None:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    occurrence = item.occurrence.occurrence
    clear_screen()
    print_menu_header("Retry Submission Assembly")
    print(f"Class: {occurrence.class_id}")
    print(f"Assignment: {occurrence.assignment_id}")
    print()
    try:
        result = assemble_assignment_submissions(
            workspace_root,
            occurrence.class_id,
            occurrence.assignment_id,
        )
    except Exception as error:
        clear_screen()
        print_menu_header("Submission Assembly Retry Result")
        print(f"Submission assembly retry failed: {error}")
        print("The occurrence remains active; no resolution was recorded.")
        print()
        pause_for_user()
        return
    clear_screen()
    print_menu_header("Submission Assembly Retry Result")
    print_assignment_submission_assembly(result, workspace_root)
    completed_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    if not post_dispatch_retry_proves_resolution(
        item.occurrence,
        result,
        completed_at=completed_at,
    ):
        print()
        print(
            "The retry completed without an operational failure, but it did not "
            "prove that this occurrence was resolved."
        )
        print("The occurrence remains active; no resolution was recorded.")
        print()
        pause_for_user()
        return
    print()
    print("The retry completed successfully.")
    confirm = input(
        "Record this occurrence as resolved after retry? [y/N]: "
    ).strip().casefold()
    if confirm not in {"y", "yes"}:
        print("No resolution was recorded.")
        print()
        pause_for_user()
        return
    try:
        resolution = resolve_post_dispatch_after_successful_retry(
            workspace_root,
            item.occurrence.work_ref,
            occurrence.failure_id,
            assembly_result=result,
            completed_at=completed_at,
        )
    except PostDispatchReviewResolutionError as error:
        clear_screen()
        print_menu_header("Retry Resolution Result")
        print(f"Could not record the successful retry: {error}")
    else:
        clear_screen()
        print_menu_header("Retry Resolution Result")
        print(f"Resolution record: {resolution.relative_path}")
    print()
    pause_for_user()


def _view_post_dispatch_status(
    workspace_root: Path,
    item: PostDispatchReviewItem,
) -> None:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header

    occurrence = item.occurrence.occurrence
    clear_screen()
    print_menu_header("Current Submission Status")
    print(f"Class: {occurrence.class_id}")
    print(f"Assignment: {occurrence.assignment_id}")
    print()
    try:
        status = list_assignment_submission_status(
            workspace_root, occurrence.class_id, occurrence.assignment_id
        )
    except Exception as error:
        print(f"Could not load current submission status: {error}")
    else:
        print_assignment_submission_status(status, workspace_root)
    print()
    pause_for_user()


def _open_post_dispatch_context_path(
    workspace_root: Path,
    item: PostDispatchReviewItem,
    kind: Literal["evidence", "manifest"],
) -> None:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    occurrence = item.occurrence.occurrence
    paths = (
        occurrence.possible_evidence_paths
        if kind == "evidence"
        else occurrence.possible_manifest_paths
    )
    clear_screen()
    print_menu_header(f"Open Validated Possible {kind.title()}")
    for index, path in enumerate(paths, start=1):
        print(f"{index}. {path}")
    print("B. Back")
    print()
    choice = input(f"Select possible {kind}: ").strip()
    if choice == "" or parse_navigation_choice(choice) is NavigationChoice.BACK:
        return
    if not choice.isdigit() or not 1 <= int(choice) <= len(paths):
        return
    selected = paths[int(choice) - 1]
    clear_screen()
    print_menu_header(f"Open Possible {kind.title()} Result")
    try:
        opened = open_post_dispatch_possible_path(
            workspace_root,
            item.occurrence.work_ref,
            occurrence.failure_id,
            kind=kind,
            relative_path=selected,
        )
    except PostDispatchReviewResolutionError as error:
        print(f"Could not open the possible {kind}: {error}")
    else:
        print(f"Opened validated {kind}: {opened.relative_path}")
        print("The occurrence remains active; no resolution was recorded.")
    print()
    pause_for_user()


def _launch_combined_review_menu(
    workspace_root: Path, class_id: str, assignment_id: str
) -> int:
    from quillan.menu import clear_screen, pause_for_user, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    while True:
        core = discover_scan_review_items(
            workspace_root, class_id=class_id, assignment_id=assignment_id
        )
        post = discover_post_dispatch_review_items(
            workspace_root, quillan_work_ref(class_id, assignment_id)
        )
        combined: tuple[tuple[str, QuillanReviewItem | PostDispatchReviewItem], ...] = (
            *(("Core", item) for item in core.items),
            *(("Post-dispatch", item) for item in post.items),
        )
        clear_screen()
        print_menu_header("All Active Scan Problems")
        if not combined:
            print("There are no active scan problems for this assignment.")
            print()
            pause_for_user()
            return 0
        for index, (source, item) in enumerate(combined, start=1):
            if isinstance(item, QuillanReviewItem):
                label = f"{item.source_filename}; {item.failure_category}"
            else:
                occurrence = item.occurrence.occurrence
                label = f"{occurrence.category}; {occurrence.student_id or 'assignment-level'}"
            print(f"{index}. {source}: {label}")
        print("B. Back")
        print()
        choice = input("Select a problem: ").strip()
        if choice == "" or parse_navigation_choice(choice) is NavigationChoice.BACK:
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(combined):
            _, selected = combined[int(choice) - 1]
            if isinstance(selected, QuillanReviewItem):
                _resolve_core_item(workspace_root, selected)
            else:
                _resolve_post_dispatch_item(workspace_root, selected)


def _prompt_message(action: str) -> str | None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Scan Review Note")
    default = DEFAULT_RESOLUTION_MESSAGES.get(action)
    if default is not None:
        print(f"Default note: {default}")
        print()
        value = input("Note (leave blank to use the default): ").strip()
        return value or default
    value = input("Short teacher note (required; leave blank to cancel): ").strip()
    return value or None


def _prompt_evidence_path() -> str | None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Evidence Path")
    print("You may record an existing workspace-relative evidence path.")
    print("No file will be copied or moved.")
    print()
    value = input("Evidence path (optional): ").strip()
    return value or None


def _display(value: object | None) -> str:
    return "—" if value is None else str(value)

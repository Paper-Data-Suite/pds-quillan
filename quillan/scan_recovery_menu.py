"""Issue #419 Slice 7: explicit, teacher-confirmed Scan Review recovery.

The menu never mistakes a Core route-resolution decision for recovered evidence.
It delegates all durable work to the independently validating Slice 1-6 APIs,
and never chooses a student route or replays historical decisions automatically.
"""

from __future__ import annotations

from pathlib import Path

from quillan.scan_recovery_completion import (
    CompletedScanRecovery,
    ScanRecoveryExecutionError,
    execute_prepared_scan_recovery,
)
from quillan.scan_recovery_historical import (
    HistoricalScanRecoveryError,
    HistoricalScanRecoveryItem,
    discover_historical_scan_recoveries,
    replay_historical_scan_recovery,
)
from quillan.scan_recovery_preflight import (
    PreparedScanRecovery,
    ScanRecoveryPreflightError,
    prepare_scan_review_recovery,
)
from quillan.scan_review_resolution import (
    QuillanReviewItem,
    ScanReviewResolutionError,
    discover_scan_review_items,
)


def launch_scan_recovery_menu(
    workspace_root: Path,
    class_id: str | None = None,
    assignment_id: str | None = None,
    *,
    unscoped_only: bool = False,
) -> int:
    """List failed physical pages and explicitly recover one chosen occurrence.

    Resolved non-route decisions are excluded. Historical recorded routes are
    checked against their latest exact resolution ID on execution, so a newly
    superseded decision cannot be replayed from an old menu screen.
    """
    from quillan.menu import clear_screen, print_menu_header
    from quillan.menu_navigation import NavigationChoice, parse_navigation_choice

    if (class_id is None) != (assignment_id is None):
        raise ValueError("Class and assignment must be supplied together.")
    if unscoped_only and class_id is not None:
        raise ValueError("Unscoped selection cannot specify a class or assignment.")
    while True:
        clear_screen()
        print_menu_header("Recover Retained Scan Pages")
        if class_id is not None:
            print(f"Class: {class_id}; Assignment: {assignment_id}")
        print("Core 'resolved' means a routing decision, not recovered evidence.")
        print()
        try:
            active = discover_scan_review_items(
                workspace_root,
                include_resolved=True,
                class_id=class_id,
                assignment_id=assignment_id,
            )
            history = discover_historical_scan_recoveries(workspace_root)
        except (ScanReviewResolutionError, HistoricalScanRecoveryError) as error:
            print(f"Could not load recoverable scan records: {error}")
            input("Press Enter to return...")
            return 1

        historical = {item.failure_id: item for item in history.items}
        choices: list[tuple[QuillanReviewItem, HistoricalScanRecoveryItem | None]] = []
        for item in active.items:
            if unscoped_only and item.class_id is not None:
                continue
            if item.latest_resolution_status == "resolved":
                old = historical.get(item.failure_id)
                if old is None:
                    continue
                choices.append((item, old))
            else:
                choices.append((item, None))

        for index, (item, old) in enumerate(choices, start=1):
            physical = (
                "page unknown"
                if item.source_page_number is None
                else f"physical page {item.source_page_number}"
            )
            state = (
                f"recorded route: {old.state}"
                if old is not None
                else f"route selection required ({item.display_status})"
            )
            print(
                f"{index}. {item.source_filename}; {physical}; "
                f"{item.failure_category}; {state}"
            )
        if not choices:
            print("No eligible retained Core scan-review pages were found.")
        warning_count = len(active.warnings) + len(history.warnings)
        if warning_count:
            print(f"Review discovery reported {warning_count} warning(s).")
        print("B. Back")
        print()
        choice = input("Select a page to recover: ").strip()
        if not choice or parse_navigation_choice(choice) is NavigationChoice.BACK:
            return 0
        if not choice.isdecimal() or not 1 <= int(choice) <= len(choices):
            print("Invalid selection.")
            input("Press Enter to continue...")
            continue
        item, old = choices[int(choice) - 1]
        if old is None:
            _recover_new_route(workspace_root, item)
        else:
            _recover_recorded_route(workspace_root, item, old)


def _recover_new_route(workspace_root: Path, item: QuillanReviewItem) -> None:
    """Use the existing registered-route picker, followed by exact preflight."""
    from quillan.menu import clear_screen, print_menu_header
    from quillan.scan_review_menu import _prompt_route_option

    route = _prompt_route_option(workspace_root, item)
    if route is None:
        return
    try:
        prepared = prepare_scan_review_recovery(
            workspace_root,
            item.failure_id,
            route_locator=route.locator,
            target=route.target,
        )
    except ScanRecoveryPreflightError as error:
        clear_screen()
        print_menu_header("Scan Recovery Preflight Failed")
        print(f"No evidence was recovered: {error}")
        input("Press Enter to return...")
        return
    if not _confirm_recovery(prepared):
        return
    try:
        result = execute_prepared_scan_recovery(workspace_root, prepared)
    except ScanRecoveryExecutionError as error:
        _show_execution_failure(error)
        return
    _show_completion(result)


def _recover_recorded_route(
    workspace_root: Path,
    item: QuillanReviewItem,
    historical: HistoricalScanRecoveryItem,
) -> None:
    """Replay only an exact, latest verified teacher route-resolution decision."""
    from quillan.menu import clear_screen, print_menu_header

    if historical.state == "blocked":
        clear_screen()
        print_menu_header("Historical Scan Recovery Blocked")
        print(f"Failure ID: {item.failure_id}")
        print(historical.reason or "Current recovery authority cannot be verified.")
        print("No recovery has been attempted.")
        input("Press Enter to return...")
        return
    try:
        prepared = prepare_scan_review_recovery(
            workspace_root, item.failure_id, use_recorded_route=True
        )
    except ScanRecoveryPreflightError as error:
        clear_screen()
        print_menu_header("Historical Scan Recovery Preflight Failed")
        print(f"No evidence was recovered: {error}")
        input("Press Enter to return...")
        return
    if prepared.historical_resolution_id != historical.resolution_id:
        clear_screen()
        print_menu_header("Historical Scan Recovery Changed")
        print("The latest route decision changed. Return and refresh the list.")
        input("Press Enter to return...")
        return
    if not _confirm_recovery(prepared, recorded_state=historical.state):
        return
    try:
        result = replay_historical_scan_recovery(
            workspace_root,
            item.failure_id,
            expected_resolution_id=historical.resolution_id,
        )
    except HistoricalScanRecoveryError as error:
        clear_screen()
        print_menu_header("Historical Scan Recovery Rejected")
        print(str(error))
        print("No successful recovery was reported.")
        input("Press Enter to return...")
        return
    except ScanRecoveryExecutionError as error:
        _show_execution_failure(error)
        return
    _show_completion(result)


def _confirm_recovery(
    prepared: PreparedScanRecovery,
    *,
    recorded_state: str | None = None,
) -> bool:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Confirm Retained Scan Recovery")
    print(f"Failure ID: {prepared.failure_id}")
    print(f"Original file: {prepared.source_filename}")
    print(
        f"Original physical page: {prepared.source_page_number} "
        f"of {prepared.source_page_count}"
    )
    print(f"Class: {prepared.class_id}; Assignment: {prepared.assignment_id}")
    print(f"Student: {prepared.student_id}")
    print(f"Target logical page: {prepared.logical_page} of {prepared.total_pages}")
    print(f"Registered route: {prepared.route_locator.route_id}")
    print(f"Immutable page ID: {prepared.page_id}")
    if prepared.historical_resolution_id is not None:
        print(f"Recorded decision: {prepared.historical_resolution_id}")
    if recorded_state is not None:
        print(f"Previously verified evidence: {recorded_state}")
    print("This will write verified evidence/submission records if needed.")
    print("Existing teacher selections and Core decisions will not be overwritten.")
    print("B. Back")
    print()
    return input("Recover this exact retained page? [y/N]: ").strip().casefold() in {
        "y", "yes"
    }


def _show_execution_failure(error: ScanRecoveryExecutionError) -> None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Scan Recovery Incomplete")
    print(f"Failed stage: {error.stage}")
    print(str(error))
    if error.verified_observation_id is not None:
        print(f"Verified durable observation: {error.verified_observation_id}")
        print("Evidence may already be saved; retry after addressing the failure.")
    else:
        print("No complete recovered observation was verified by this attempt.")
    print("Core resolution status alone does not establish recovery.")
    input("Press Enter to return...")


def _show_completion(result: CompletedScanRecovery) -> None:
    from quillan.menu import clear_screen, print_menu_header

    clear_screen()
    print_menu_header("Scan Recovery Result")
    print(f"Failure ID: {result.failure_id}")
    print(f"Verified evidence ID: {result.evidence_id}")
    print(f"Observation: {result.observation_status}")
    print(f"Submission assembly: {result.submission_status}")
    print(f"Verified page state: {result.completion_state}")
    if result.completion_state == "ready_for_review":
        print("The recovered page is selected and available in Open Evidence.")
    elif result.completion_state == "selection_needed":
        print("The recovered page is a candidate; select it in evidence review.")
    else:
        print("A teacher-controlled page state still requires a separate decision.")
    print("The Core routing resolution history was not changed.")
    input("Press Enter to return...")


__all__ = ["launch_scan_recovery_menu"]

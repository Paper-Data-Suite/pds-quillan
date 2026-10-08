"""Issue #419 Slice 7: teacher-confirmed recovery inside Scan Review menus."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import quillan.scan_recovery_menu as recovery_menu
import quillan.scan_review_menu as scan_review_menu
from quillan.scan_recovery_completion import recover_scan_review_page
from quillan.scan_review_resolution import resolve_scan_review_item
from quillan.submission_manifest import load_submission_manifest
from tests.review_test_support import _write_assignment
from tests.test_scan_recovery_dispatch_issue419 import _registry
from tests.test_scan_recovery_preflight_issue419 import FAILURE_ID, _files, _fixture


def _inputs(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> list[str]:
    remaining: Iterator[str] = iter(responses)
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        try:
            return next(remaining)
        except StopIteration as error:
            raise AssertionError(f"Unexpected menu prompt: {prompt}") from error

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def _ready(tmp_path: Path):
    # Scoped failure keeps route selection within the issued assignment.
    root, retained, locator, target = _fixture(tmp_path, scoped=True)
    _write_assignment(root, class_id=locator.class_id, assignment_id=locator.work_id)
    return root, retained, locator, target


def test_unresolved_scan_requires_confirmation_then_recovers_exact_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, _ = _ready(tmp_path)
    prompts = _inputs(monkeypatch, ["1", "1", "y", "y", "", "b"])
    assert recovery_menu.launch_scan_recovery_menu(root) == 0
    result = capsys.readouterr().out
    assert "Original physical page: 1 of 1" in result
    assert "Core 'resolved' means a routing decision" in result
    assert "ready_for_review" in result
    assert "available in Open Evidence" in result
    assert prompts.count("Recover this exact retained page? [y/N]: ") == 1
    assert len(tuple(root.rglob("obs_*.json"))) == 1
    assert len(tuple(root.rglob("submission.json"))) == 1
    assert not (root / "scans" / "review" / "resolutions").exists()
    assert f"Registered route: {locator.route_id}" in result


def test_unresolved_scan_declined_after_route_choice_has_zero_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _, _ = _ready(tmp_path)
    before = _files(root)
    _inputs(monkeypatch, ["1", "1", "y", "n", "b"])
    assert recovery_menu.launch_scan_recovery_menu(root) == 0
    assert _files(root) == before


def test_back_at_route_picker_does_not_trigger_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _, _ = _ready(tmp_path)
    before = _files(root)
    prompts = _inputs(monkeypatch, ["1", "b", "b"])
    assert recovery_menu.launch_scan_recovery_menu(root) == 0
    assert "Recover this exact retained page? [y/N]: " not in prompts
    assert _files(root) == before


def test_historical_resolved_route_is_exposed_and_replayed_without_new_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, target = _ready(tmp_path)
    resolution = resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    before = resolution.resolution_metadata_path.read_bytes()
    prompts = _inputs(monkeypatch, ["1", "y", "", "b"])
    assert recovery_menu.launch_scan_recovery_menu(root) == 0
    output = capsys.readouterr().out
    assert "recorded route: evidence_missing" in output
    assert f"Recorded decision: {resolution.resolution_id}" in output
    assert "ready_for_review" in output
    assert "Use this registered route? [y/N]: " not in prompts
    assert resolution.resolution_metadata_path.read_bytes() == before
    assert len(tuple(resolution.resolution_metadata_path.parent.glob("*.json"))) == 1
    assert len(tuple(root.rglob("submission.json"))) == 1


def test_historical_already_recovered_status_is_not_mistaken_for_core_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, target = _ready(tmp_path)
    resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    recover_scan_review_page(
        root, FAILURE_ID, use_recorded_route=True, registry=_registry()
    )
    before = _files(root)
    _inputs(monkeypatch, ["1", "n", "b"])
    assert recovery_menu.launch_scan_recovery_menu(root) == 0
    assert "recorded route: ready_for_review" in capsys.readouterr().out
    assert _files(root) == before


def test_blocked_historical_evidence_cannot_be_replayed_from_menu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, retained, locator, target = _ready(tmp_path)
    resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    retained.retained_source_path.write_bytes(b"contradictory source")
    before = _files(root)
    prompts = _inputs(monkeypatch, ["1", "", "b"])
    assert recovery_menu.launch_scan_recovery_menu(root) == 0
    output = capsys.readouterr().out
    assert "recorded route: blocked" in output
    assert "Historical Scan Recovery Blocked" in output
    assert "Recover this exact retained page? [y/N]: " not in prompts
    assert _files(root) == before


def test_result_distinguishes_selection_needed_without_reselecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tests.test_scan_recovery_assembly_issue419 import _prior_selected

    root, _, locator, _ = _ready(tmp_path)
    previous = _prior_selected(root, locator)
    _inputs(monkeypatch, ["1", "1", "y", "y", "", "b"])
    assert recovery_menu.launch_scan_recovery_menu(root) == 0
    output = capsys.readouterr().out
    assert "selection_needed" in output
    manifest_path = next(root.rglob("submission.json"))
    page = load_submission_manifest(manifest_path)["pages"][0]
    assert page["selected_evidence_id"] == previous
    assert len(page["evidence"]) == 2


def test_global_core_menu_links_to_recovery_without_changing_other_choices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, _, _ = _ready(tmp_path)
    _inputs(monkeypatch, ["r", "b", "b"])
    assert scan_review_menu.launch_scan_review_resolution_menu(root) == 0
    output = capsys.readouterr().out
    assert "R. Recover retained Core scan pages" in output
    assert "Recover Retained Scan Pages" in output
    assert "3. All Core routing problems" in output


def test_scoped_core_menu_links_to_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, locator, _ = _ready(tmp_path)
    _inputs(monkeypatch, ["r", "b", "b"])
    assert scan_review_menu._launch_core_review_menu(
        root, locator.class_id, locator.work_id
    ) == 0


def test_resolved_only_core_empty_state_still_reaches_historical_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, target = _ready(tmp_path)
    resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    _inputs(monkeypatch, ["r", "b", ""])
    assert scan_review_menu.launch_scan_review_resolution_menu(root) == 0
    output = capsys.readouterr().out
    assert "There are no unresolved or deferred scan review items." in output
    assert "recorded route: evidence_missing" in output


def test_unscoped_only_recovery_listing_does_not_show_other_scoped_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, _ = _fixture(tmp_path, scoped=True)
    _write_assignment(root, class_id=locator.class_id, assignment_id=locator.work_id)
    _inputs(monkeypatch, ["b"])
    assert recovery_menu.launch_scan_recovery_menu(root, unscoped_only=True) == 0
    output = capsys.readouterr().out
    assert "No eligible retained Core scan-review pages" in output


def test_failure_at_assembly_reports_stage_instead_of_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from quillan.scan_recovery_completion import ScanRecoveryExecutionError

    root, _, _, _ = _ready(tmp_path)
    def fail(*_args: object, **_kwargs: object) -> object:
        cause = RuntimeError("assembly interrupted")
        raise ScanRecoveryExecutionError("assembly", FAILURE_ID, cause) from cause

    monkeypatch.setattr(recovery_menu, "execute_prepared_scan_recovery", fail)
    _inputs(monkeypatch, ["1", "1", "y", "y", "", "b"])
    assert recovery_menu.launch_scan_recovery_menu(root) == 0
    output = capsys.readouterr().out
    assert "Scan Recovery Incomplete" in output
    assert "Failed stage: assembly" in output
    assert "No complete recovered observation was verified" in output
    assert "available in Open Evidence" not in output


def test_scoped_combined_source_menu_offers_recovery_as_distinct_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, _ = _ready(tmp_path)
    _inputs(monkeypatch, ["4", "b", "b"])
    assert scan_review_menu._launch_review_source_menu(
        root, locator.class_id, locator.work_id
    ) == 0
    output = capsys.readouterr().out
    assert "4. Recover retained Core scan pages" in output
    assert "Recover Retained Scan Pages" in output


def test_post_dispatch_only_menu_also_reaches_core_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from quillan.post_dispatch_review import create_post_dispatch_review_occurrence
    from quillan.work_paths import quillan_work_ref

    root, _, locator, _ = _ready(tmp_path)
    create_post_dispatch_review_occurrence(
        root,
        quillan_work_ref(locator.class_id, locator.work_id),
        category="submission_assembly",
        stage="submission_assembly",
        failure_message="Assembly interrupted.",
        student_id="00107",
    )
    _inputs(monkeypatch, ["r", "b", "b"])
    assert scan_review_menu._launch_post_dispatch_review_menu(
        root, locator.class_id, locator.work_id
    ) == 0
    output = capsys.readouterr().out
    assert "Quillan Post-Dispatch Problems" in output
    assert "R. Recover retained Core scan pages" in output
    assert "Recover Retained Scan Pages" in output

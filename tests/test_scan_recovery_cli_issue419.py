"""Issue #419 Slice 8: explicit direct-CLI recovery and contract surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pds_core.routing_models import ModuleRecordRef, RouteLocator
from pds_core.scan_retention import RetainedSourceScan

import pytest

import quillan.cli_app.handlers.scan_recovery as cli_recovery
from quillan.cli import main
from quillan.cli_app.parser import build_parser
from quillan.scan_review_resolution import resolve_scan_review_item
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_page_management import mark_submission_page_needs_rescan
from tests.review_test_support import _write_assignment
from tests.test_scan_recovery_assembly_issue419 import _prior_selected
from tests.test_scan_recovery_preflight_issue419 import FAILURE_ID, _files, _fixture


def _setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, RetainedSourceScan, RouteLocator, ModuleRecordRef]:
    root, retained, locator, target = _fixture(tmp_path)
    _write_assignment(root, class_id=locator.class_id, assignment_id=locator.work_id)
    monkeypatch.setattr(cli_recovery, "resolve_workspace_root", lambda: root)
    return root, retained, locator, target


def _route_flags(locator: RouteLocator) -> list[str]:
    return [
        "--route-id", locator.route_id,
        "--route-class-id", locator.class_id,
        "--route-assignment-id", locator.work_id,
    ]


def _json(text: str) -> dict[str, Any]:
    loaded = json.loads(text)
    assert type(loaded) is dict
    return loaded


def test_parser_exposes_four_explicit_commands() -> None:
    parser = build_parser()
    for name in (
        "list-scan-recoveries", "preflight-scan-recovery",
        "recover-scan-review", "replay-scan-recovery",
    ):
        extra = (
            [] if name == "list-scan-recoveries"
            else [FAILURE_ID, "--expected-resolution-id", "resolution_example"]
            if name == "replay-scan-recovery"
            else [FAILURE_ID, "--route-id", "rt_0123456789abcdef0123456789abcdef",
                  "--route-class-id", "english12_p3", "--route-assignment-id", "essay_01"]
            if name == "recover-scan-review"
            else [FAILURE_ID]
        )
        args = parser.parse_args([name, *extra])
        assert callable(args.handler)


def test_list_unresolved_is_json_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, _, _ = _setup(tmp_path, monkeypatch)
    before = _files(root)
    assert main(["list-scan-recoveries", "--format", "json"]) == 0
    doc = _json(capsys.readouterr().out)
    assert doc["schema_version"] == "1"
    assert doc["status"] == "ok"
    item = doc["items"][0]
    assert item["failure_id"] == FAILURE_ID
    assert item["recovery_state"] == "route_selection_required"
    assert item["historical_resolution_id"] is None
    assert _files(root) == before


def test_exact_preflight_is_json_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, retained, locator, target = _setup(tmp_path, monkeypatch)
    before = _files(root)
    assert main(["preflight-scan-recovery", FAILURE_ID, *_route_flags(locator), "--format", "json"]) == 0
    doc = _json(capsys.readouterr().out)
    assert doc["status"] == "eligible"
    assert doc["source_sha256"] == retained.source_sha256
    assert doc["physical_page"] == 1
    assert doc["student_id"] == "00107"
    assert doc["route_id"] == locator.route_id
    assert doc["page_id"] == target.record_id
    assert _files(root) == before


def test_recorded_preflight_uses_immutable_resolution_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, target = _setup(tmp_path, monkeypatch)
    historical = resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    before = _files(root)
    assert main(["preflight-scan-recovery", FAILURE_ID, "--recorded-route", "--format", "json"]) == 0
    doc = _json(capsys.readouterr().out)
    assert doc["route_origin"] == "recorded"
    assert doc["historical_resolution_id"] == historical.resolution_id
    assert _files(root) == before


def test_mutation_requires_explicit_yes_before_any_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, _ = _setup(tmp_path, monkeypatch)
    before = _files(root)
    assert main(["recover-scan-review", FAILURE_ID, *_route_flags(locator), "--format", "json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    err = _json(captured.err)
    assert err["stage"] == "confirmation"
    assert _files(root) == before


def test_explicit_recovery_and_exact_retry_are_byte_preserving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, retained, locator, _ = _setup(tmp_path, monkeypatch)
    args = ["recover-scan-review", FAILURE_ID, *_route_flags(locator), "--yes", "--format", "json"]
    assert main(args) == 0
    first = _json(capsys.readouterr().out)
    assert first["completion_state"] == "ready_for_review"
    assert first["observation_status"] == "created"
    assert first["submission_status"] == "created"
    assert first["reviewable"] is True
    assert first["historical_route_reused"] is False
    before = _files(root)
    assert main(args) == 0
    again = _json(capsys.readouterr().out)
    assert again["evidence_id"] == first["evidence_id"]
    assert again["observation_status"] == "existing"
    assert again["submission_status"] == "unchanged"
    assert _files(root) == before
    assert retained.retained_source_path.read_bytes() == before[retained.retained_source_relative_path]
    assert not tuple((root / "scans" / "review" / "resolutions").glob("*.json"))


def test_list_identifies_historical_gap_and_replay_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, target = _setup(tmp_path, monkeypatch)
    historical = resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    decision = historical.resolution_metadata_path.read_bytes()
    assert main(["list-scan-recoveries", "--format", "json"]) == 0
    inventory = _json(capsys.readouterr().out)
    item = inventory["items"][0]
    assert item["recovery_state"] == "evidence_missing"
    assert item["historical_resolution_id"] == historical.resolution_id
    args = [
        "replay-scan-recovery", FAILURE_ID, "--expected-resolution-id",
        historical.resolution_id, "--yes", "--format", "json",
    ]
    assert main(args) == 0
    replay = _json(capsys.readouterr().out)
    assert replay["historical_route_reused"] is True
    assert replay["completion_state"] == "ready_for_review"
    assert historical.resolution_metadata_path.read_bytes() == decision
    assert main(args) == 0
    repeat = _json(capsys.readouterr().out)
    assert repeat["observation_status"] == "existing"
    assert repeat["submission_status"] == "unchanged"
    assert historical.resolution_metadata_path.read_bytes() == decision


def test_replay_wrong_resolution_id_fails_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, target = _setup(tmp_path, monkeypatch)
    resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    before = _files(root)
    assert main([
        "replay-scan-recovery", FAILURE_ID, "--expected-resolution-id",
        "res_other", "--yes", "--format", "json",
    ]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert _json(output.err)["status"] == "error"
    assert _files(root) == before


def test_recorded_route_cannot_be_mixed_with_explicit_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, _ = _setup(tmp_path, monkeypatch)
    before = _files(root)
    assert main([
        "preflight-scan-recovery", FAILURE_ID, "--recorded-route", *_route_flags(locator),
        "--format", "json",
    ]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert _json(captured.err)["stage"] == "preflight"
    assert _files(root) == before


def test_selected_evidence_remains_selected_on_cli_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, _ = _setup(tmp_path, monkeypatch)
    previous = _prior_selected(root, locator)
    assert main([
        "recover-scan-review", FAILURE_ID, *_route_flags(locator),
        "--yes", "--format", "json",
    ]) == 0
    done = _json(capsys.readouterr().out)
    assert done["completion_state"] == "selection_needed"
    assert done["reviewable"] is False
    manifest = next(root.rglob("submission.json"))
    assert load_submission_manifest(manifest)["pages"][0]["selected_evidence_id"] == previous


def test_teacher_page_state_remains_authoritative_on_cli_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, _ = _setup(tmp_path, monkeypatch)
    args = ["recover-scan-review", FAILURE_ID, *_route_flags(locator), "--yes", "--format", "json"]
    assert main(args) == 0
    completed = _json(capsys.readouterr().out)
    mark_submission_page_needs_rescan(
        root, locator.class_id, locator.work_id, completed["student_id"], 1
    )
    before = _files(root)
    assert main(args) == 0
    replay = _json(capsys.readouterr().out)
    assert replay["completion_state"] == "teacher_action_needed"
    assert _files(root) == before


def test_missing_route_information_is_a_read_only_preflight_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, locator, _ = _setup(tmp_path, monkeypatch)
    before = _files(root)
    assert main([
        "preflight-scan-recovery", FAILURE_ID, "--route-id", locator.route_id,
        "--format", "json",
    ]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert _json(captured.err)["stage"] == "preflight"
    assert _files(root) == before

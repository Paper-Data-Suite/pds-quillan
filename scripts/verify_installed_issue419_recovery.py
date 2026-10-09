"""Issue #419: independently exercise a noneditable Quillan wheel and Core 0.6.4.

Invoke from an OUTSIDE-source working directory with the exact installed wheel.
The program creates only synthetic temporary workspaces below --workspace.
It deliberately does not import repository ``tests`` or depend on source paths.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata as metadata
import io
import json
import os
from pathlib import Path
from typing import Any, cast

from PIL import Image
from pds_core.module_dispatch import RouteDispatchRequest, dispatch_route
from pds_core.module_profiles import ModuleRegistry
from pds_core.rosters import StudentRecord
from pds_core.route_registrations import write_route_registration
from pds_core.scan_failure_metadata import RoutingFailureMetadata, write_routing_failure_metadata
from pds_core.scan_retention import retain_source_scan

from quillan.cli import main as cli_main
from quillan.evidence_opening import OpenedEvidence
from quillan.pds_module import get_module_profile
from quillan.printable_response_persistence import canonical_printable_response_json
from quillan.printable_response_records import (
    PrintableResponseRecordSet,
    build_printable_response_record_set,
    transition_printable_response_lifecycle,
)
from quillan.printable_response_routes import build_printable_response_page_route
from quillan.response_page_observation_persistence import persist_quillan_dispatch_success
from quillan.scan_recovery_completion import (
    ScanRecoveryExecutionError,
    recover_scan_review_page,
)
from quillan.scan_recovery_historical import (
    HistoricalScanRecoveryError,
    discover_historical_scan_recoveries,
    replay_historical_scan_recovery,
)
from quillan.scan_recovery_menu import launch_scan_recovery_menu
from quillan.scan_review_resolution import resolve_scan_review_item
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_observation_assembly import assemble_quillan_submission_manifests
from quillan.submission_page_management import mark_submission_page_needs_rescan
from quillan.submission_review_opening import open_student_submission_for_review
from quillan.work_paths import quillan_work_paths

CLASS_ID = "issue419_wheel_class"
ASSIGNMENT_ID = "issue419_wheel_assignment"
STUDENT_ID = "00107"
FAILURE_ID = "failure_20260711T120000000000Z_a1b2c3d4e5f6"
ROUTE_ID = "rt_0123456789abcdef0123456789abcdef"
NOW = datetime(2026, 7, 19, 18, 30, tzinfo=timezone.utc)


def _assert_installed(repository: Path, version: str, core_version: str) -> None:
    assert metadata.version("quillan") == version, "wrong Quillan distribution"
    assert metadata.version("pds-core") == core_version, "wrong Core distribution"
    assert core_version == "0.6.4", "qualification requires released Core 0.6.4"
    for name in (
        "quillan", "quillan.scan_recovery_completion",
        "quillan.scan_recovery_historical", "quillan.scan_recovery_menu",
        "quillan.cli_app.handlers.scan_recovery", "pds_core",
    ):
        module = importlib.import_module(name)
        origin = getattr(module, "__file__", None)
        if not isinstance(origin, str) or not origin:
            raise AssertionError(f"missing installed module origin: {name}")
        path = Path(origin).resolve()
        assert not path.is_relative_to(repository), f"source import: {name}"
        assert ("site-packages" in path.parts or "dist-packages" in path.parts), (
            f"not installed in distribution environment: {name}"
        )
    entry = {
        (point.group, point.name, point.value)
        for point in metadata.distribution("quillan").entry_points
    }
    assert ("console_scripts", "quillan", "quillan.cli:main") in entry
    assert (
        "paper_data_suite.modules", "quillan", "quillan.pds_module:get_module_profile"
    ) in entry


def _assignment() -> dict[str, Any]:
    return {
        "schema_version": "2", "module": "quillan", "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID, "title": "Issue 419 Synthetic Scan",
        "class_ids": [CLASS_ID], "writing_type": "argument",
        "student_prompt": "Synthetic installed acceptance only.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["synthetic:W.A"],
        "review_unit": {"type": "paragraph", "singular_label": "paragraph",
                        "plural_label": "paragraphs"},
        "rating_scale": {"scale_id": "synthetic_scale", "levels": [
            {"value": 1, "label": "Developing", "description": "Synthetic"}
        ]},
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": NOW.isoformat(), "updated_at": NOW.isoformat(),
        "module_details": {},
    }


def _files(root: Path) -> dict[str, str]:
    """Snapshot exact files by SHA-256; compare changed and added paths."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def _fixture(root: Path, *, color: str = "white") -> tuple[Any, Any, Path]:
    root.mkdir(parents=True)
    assignment = _assignment()
    records = build_printable_response_record_set(
        CLASS_ID, assignment,
        StudentRecord(CLASS_ID, STUDENT_ID, "Student", "Sample", "2", {}),
        generation_id="gen_0123456789abcdef0123456789abcdef",
        artifact_id="art_0123456789abcdef0123456789abcdef",
        output_kind="class_packet_pdf", reason="initial",
        pages_per_student=1,
        issuance_id="iss_0123456789abcdef0123456789abcdef",
        page_ids=("pg_0123456789abcdef0123456789abcdef",),
        clock=lambda: NOW,
    )
    lifecycle = transition_printable_response_lifecycle(
        records.issuance.lifecycle,
        new_status="issued", timestamp="2026-07-20T00:00:00+00:00",
    )
    records = PrintableResponseRecordSet(
        replace(records.issuance, lifecycle=lifecycle), records.pages
    )
    paths = quillan_work_paths(root, CLASS_ID, ASSIGNMENT_ID)
    paths.response_page_records_dir.mkdir(parents=True)
    paths.response_page_issuances_dir.mkdir(parents=True)
    paths.response_page_records_dir.joinpath(f"{records.pages[0].page_id}.json").write_bytes(
        canonical_printable_response_json(records.pages[0].to_mapping())
    )
    paths.response_page_issuances_dir.joinpath(
        f"{records.issuance.issuance_id}.json"
    ).write_bytes(canonical_printable_response_json(records.issuance.to_mapping()))
    paths.work_root.joinpath("assignment.json").write_text(
        json.dumps(assignment), encoding="utf-8"
    )
    route = build_printable_response_page_route(records.pages[0], ROUTE_ID)
    write_route_registration(root, route.registration)
    source = root.parent / (root.name + "-source.png")
    Image.new("RGB", (30, 20), color).save(source)
    retained = retain_source_scan(root, source)
    write_routing_failure_metadata(
        root,
        RoutingFailureMetadata(
            schema_version="2", failure_id=FAILURE_ID,
            scope="page", stage="qr_detection",
            created_at="2026-07-11T12:00:00+00:00",
            failure_category="payload_missing",
            failure_message="Synthetic unreadable QR; teacher route required.",
            source_filename=retained.source_filename,
            source_scan_id=retained.source_scan_id,
            source_sha256=retained.source_sha256,
            retained_source_path=retained.retained_source_relative_path,
            review_copy_path=None, source_page_number=1,
            detected_payload=None, route_locator=None, target=None,
            module_details={
                "failure_owner": "quillan", "failure_origin": "qr_detection"
            },
        ),
    )
    return route.locator, route.registration.target, retained.retained_source_path


def _cli(root: Path, argv: list[str]) -> tuple[int, str, str]:
    previous = os.environ.get("PDS_WORKSPACE_ROOT")
    os.environ["PDS_WORKSPACE_ROOT"] = str(root)
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            status = cli_main(argv)
    finally:
        if previous is None:
            os.environ.pop("PDS_WORKSPACE_ROOT", None)
        else:
            os.environ["PDS_WORKSPACE_ROOT"] = previous
    return status, out.getvalue(), err.getvalue()


def _route_flags(locator: Any) -> list[str]:
    return ["--route-id", locator.route_id,
            "--route-class-id", locator.class_id,
            "--route-assignment-id", locator.work_id]


def _json_outcome(root: Path, argv: list[str], *, status: int = 0) -> dict[str, Any]:
    code, stdout, stderr = _cli(root, [*argv, "--format", "json"])
    assert code == status, f"CLI exit {code} (expected {status}): {stderr}"
    assert (not stderr if status == 0 else not stdout), "JSON output used wrong stream"
    payload = json.loads(stdout if status == 0 else stderr)
    assert isinstance(payload, dict) and payload["schema_version"] == "1"
    return cast(dict[str, Any], payload)


def _menu(root: Path, responses: list[str]) -> str:
    import builtins
    old_input = builtins.input
    iterator = iter(responses)
    def fake_input(_prompt: object = "") -> str:
        try:
            return next(iterator)
        except StopIteration as error:
            raise AssertionError("installed menu requested unexpected input") from error
    output = io.StringIO()
    builtins.input = fake_input
    try:
        with redirect_stdout(output):
            assert launch_scan_recovery_menu(root) == 0
    finally:
        builtins.input = old_input
    return output.getvalue()


def _explicit_case(root: Path) -> dict[str, object]:
    locator, target, retained_path = _fixture(root)
    before = _files(root)
    retained_bytes = retained_path.read_bytes()
    inventory = _json_outcome(root, ["list-scan-recoveries"])
    assert inventory["items"][0]["recovery_state"] == "route_selection_required"
    preview = _json_outcome(root, ["preflight-scan-recovery", FAILURE_ID,
                                   *_route_flags(locator)])
    assert preview["status"] == "eligible" and preview["student_id"] == STUDENT_ID
    assert _json_outcome(root, ["recover-scan-review", FAILURE_ID,
                               *_route_flags(locator)], status=2)["stage"] == "confirmation"
    assert _files(root) == before, "read-only/denied commands mutated workspace"
    args = ["recover-scan-review", FAILURE_ID, *_route_flags(locator), "--yes"]
    first = _json_outcome(root, args)
    assert (first["completion_state"], first["observation_status"],
            first["submission_status"]) == ("ready_for_review", "created", "created")
    assert retained_path.read_bytes() == retained_bytes, "retained source was modified"
    assert not (root / "scans" / "review" / "resolutions").exists()
    after = _files(root)
    repeated = _json_outcome(root, args)
    assert repeated["evidence_id"] == first["evidence_id"]
    assert (repeated["observation_status"], repeated["submission_status"]) == (
        "existing", "unchanged"
    )
    assert _files(root) == after, "exact replay changed durable bytes"
    manifest = next(root.rglob("submission.json"))
    assert load_submission_manifest(manifest)["pages"][0]["selected_evidence_id"] == first["evidence_id"]
    from quillan import submission_review_opening
    original = getattr(submission_review_opening, "open_workspace_evidence")
    opened: list[Path] = []
    def fake_open(
        workspace_root: str | Path, relative_path: str | Path
    ) -> OpenedEvidence:
        path = Path(workspace_root).joinpath(*Path(relative_path).parts)
        assert path.is_file()
        opened.append(path)
        return OpenedEvidence(
            evidence_path=path, evidence_relative_path=Path(relative_path).as_posix()
        )
    setattr(submission_review_opening, "open_workspace_evidence", fake_open)
    try:
        seen = open_student_submission_for_review(
            root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, page_number=1
        )
    finally:
        setattr(submission_review_opening, "open_workspace_evidence", original)
    assert seen.evidence_id == first["evidence_id"] and len(opened) == 1
    mark_submission_page_needs_rescan(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 1)
    pending = _files(root)
    state = _json_outcome(root, args)
    assert state["completion_state"] == "teacher_action_needed"
    assert _files(root) == pending
    return {"cli_preflight_read_only": True, "explicit_completion": True,
            "exact_retry_byte_preserving": True, "open_evidence": True,
            "teacher_state_preserved": True}


def _historical_case(root: Path) -> dict[str, object]:
    locator, target, retained_path = _fixture(root)
    decision = resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    decision_bytes = decision.resolution_metadata_path.read_bytes()
    before = _files(root)
    items = discover_historical_scan_recoveries(root).items
    assert len(items) == 1 and items[0].state == "evidence_missing"
    assert _json_outcome(root, ["list-scan-recoveries"])["items"][0][
        "recovery_state"
    ] == "evidence_missing"
    assert _json_outcome(root, ["replay-scan-recovery", FAILURE_ID,
                              "--expected-resolution-id", "res_stale", "--yes"],
                         status=1)["status"] == "error"
    assert _files(root) == before
    args = ["replay-scan-recovery", FAILURE_ID,
            "--expected-resolution-id", decision.resolution_id, "--yes"]
    first = _json_outcome(root, args)
    assert first["historical_route_reused"] and first["completion_state"] == "ready_for_review"
    after = _files(root)
    retry = _json_outcome(root, args)
    assert retry["observation_status"] == "existing"
    assert retry["submission_status"] == "unchanged" and _files(root) == after
    assert decision.resolution_metadata_path.read_bytes() == decision_bytes
    assert len(tuple(decision.resolution_metadata_path.parent.glob("*.json"))) == 1
    # The real menu must permit safe cancellation without writing.
    assert "Recover Retained Scan Pages" in _menu(root, ["b"])
    assert _files(root) == after
    assert "Confirm Retained Scan Recovery" in _menu(root, ["1", "n", "b"])
    assert _files(root) == after
    assert "Scan Recovery Result" in _menu(root, ["1", "y", "", "b"])
    assert _files(root) == after
    assert retained_path.is_file()
    resolve_scan_review_item(root, FAILURE_ID, action="deferred")
    superseded = _files(root)
    try:
        replay_historical_scan_recovery(
            root, FAILURE_ID, expected_resolution_id=decision.resolution_id
        )
    except HistoricalScanRecoveryError:
        pass
    else:
        raise AssertionError("superseded decision was replayed")
    assert _files(root) == superseded
    return {"historical_gap": True, "historical_replay": True,
            "no_resolution_mutations": True, "superseded_rejected": True,
            "teacher_menu_confirm_and_back": True}


def _candidate_case(root: Path) -> dict[str, object]:
    locator, target, _ = _fixture(root)
    first_source = root.parent / "already-selected.png"
    Image.new("RGB", (24, 16), "black").save(first_source)
    retained = retain_source_scan(root, first_source)
    registry = ModuleRegistry((get_module_profile(),))
    success = dispatch_route(
        root, registry, RouteDispatchRequest(locator, retained, 1)
    )
    obs = persist_quillan_dispatch_success(root, success)
    batch = assemble_quillan_submission_manifests(
        root, CLASS_ID, ASSIGNMENT_ID,
        observation_ids=(obs.observation.observation_id,),
    )
    assert not batch.failures and len(batch.assembled) == 1
    original_id = obs.observation.observation_id
    result = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=registry
    )
    assert result.completion_state == "selection_needed"
    assert result.evidence_id != original_id
    page = load_submission_manifest(result.assembled.assembled.manifest_path)["pages"][0]
    assert page["selected_evidence_id"] == original_id
    assert len(page["evidence"]) == 2
    return {"duplicate_preserves_selected_evidence": True}


def _interruption_and_integrity_case(root: Path) -> dict[str, object]:
    locator, target, retained_path = _fixture(root)
    from quillan import scan_recovery_completion as completion
    original = getattr(completion, "assemble_persisted_scan_recovery")
    def stopped(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("synthetic installed assembly interruption")
    setattr(completion, "assemble_persisted_scan_recovery", stopped)
    try:
        try:
            recover_scan_review_page(root, FAILURE_ID, route_locator=locator,
                                     target=target, registry=ModuleRegistry((get_module_profile(),)))
        except ScanRecoveryExecutionError as error:
            assert error.stage == "assembly" and error.verified_observation_id
            recovered_id = error.verified_observation_id
        else:
            raise AssertionError("interrupted assembly falsely completed")
    finally:
        setattr(completion, "assemble_persisted_scan_recovery", original)
    assert not tuple(root.rglob("submission.json"))
    complete = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target,
        registry=ModuleRegistry((get_module_profile(),)),
    )
    assert complete.evidence_id == recovered_id
    assert (complete.observation_status, complete.submission_status) == (
        "existing", "created"
    )
    complete.persisted.persisted.evidence_path.write_bytes(b"tampered")
    compromised = _files(root)
    try:
        recover_scan_review_page(root, FAILURE_ID, route_locator=locator,
                                 target=target, registry=ModuleRegistry((get_module_profile(),)))
    except ScanRecoveryExecutionError as error:
        assert error.stage in {"persistence", "assembly"}
    else:
        raise AssertionError("tampered recovered evidence falsely completed")
    assert _files(root) == compromised
    retained_path.write_bytes(b"tampered retained source")
    before = _files(root)
    try:
        recover_scan_review_page(root, FAILURE_ID, route_locator=locator,
                                 target=target, registry=ModuleRegistry((get_module_profile(),)))
    except ScanRecoveryExecutionError:
        pass
    else:
        raise AssertionError("tampered retained source falsely completed")
    assert _files(root) == before
    return {"interrupted_assembly_retries": True, "tampered_evidence_rejected": True,
            "tampered_source_rejected": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--expected-quillan-version", required=True)
    parser.add_argument("--expected-core-version", default="0.6.4")
    arguments = parser.parse_args()
    repository = arguments.repository.resolve(strict=True)
    work = arguments.workspace.resolve()
    if work.is_relative_to(repository) or repository.is_relative_to(work):
        raise AssertionError("installed acceptance must use outside-source workspace")
    if work.exists() and any(work.iterdir()):
        raise AssertionError("installed acceptance requires an empty workspace")
    _assert_installed(repository, arguments.expected_quillan_version,
                      arguments.expected_core_version)
    work.mkdir(parents=True, exist_ok=True)
    checks = {
        **_explicit_case(work / "explicit"),
        **_historical_case(work / "historical"),
        **_candidate_case(work / "duplicate"),
        **_interruption_and_integrity_case(work / "interruption"),
    }
    assert all(checks.values())
    print(json.dumps({
        "status": "PASS", "issue": 419,
        "quillan_version": arguments.expected_quillan_version,
        "core_version": arguments.expected_core_version,
        "checks": checks,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

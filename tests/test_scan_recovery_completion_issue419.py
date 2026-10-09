"""Issue #419 Slice 5: complete recovery, truthful states, restart/retry."""

from __future__ import annotations

from pathlib import Path

import pytest
from pds_core.module_profiles import ModuleRegistry
from pds_core.routing_models import ModuleRecordRef, RouteLocator
from pds_core.scan_retention import RetainedSourceScan

import quillan.pds2_scan_intake as intake
import quillan.scan_recovery_completion as completion
from quillan.scan_recovery_assembly import assemble_persisted_scan_recovery
from quillan.scan_recovery_persistence import (
    PersistedScanRecovery,
    persist_dispatched_scan_recovery,
)
from quillan.scan_recovery_completion import (
    ScanRecoveryExecutionError,
    execute_prepared_scan_recovery,
    recover_scan_review_page,
)
from quillan.scan_recovery_preflight import prepare_scan_review_recovery
from quillan.scan_review_resolution import resolve_scan_review_item
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_page_management import (
    exclude_submission_page,
    mark_submission_page_needs_rescan,
)
from tests.review_test_support import _write_assignment
from tests.test_scan_recovery_assembly_issue419 import _prior_selected
from tests.test_scan_recovery_dispatch_issue419 import _registry
from tests.test_scan_recovery_preflight_issue419 import FAILURE_ID, _files, _fixture


def _setup(
    tmp_path: Path,
) -> tuple[Path, RetainedSourceScan, RouteLocator, ModuleRecordRef]:
    root, retained, locator, target = _fixture(tmp_path)
    _write_assignment(root, class_id=locator.class_id, assignment_id=locator.work_id)
    return root, retained, locator, target


def test_explicit_route_materializes_reviewable_evidence_without_qr_or_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, retained, locator, target = _setup(tmp_path)
    original = retained.retained_source_path.read_bytes()

    def reject_qr(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("manual recovery must not decode the failed QR")

    monkeypatch.setattr(intake, "detect_qr_payload", reject_qr)
    outcome = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    assert outcome.failure_id == FAILURE_ID
    assert outcome.completion_state == "ready_for_review"
    assert outcome.reviewable
    assert outcome.observation_status == "created"
    assert outcome.submission_status == "created"
    assert not outcome.historical_route_reused
    manifest = load_submission_manifest(outcome.assembled.assembled.manifest_path)
    assert manifest["pages"][0]["selected_evidence_id"] == outcome.evidence_id
    assert retained.retained_source_path.read_bytes() == original
    assert not (root / "scans" / "review" / "resolutions").exists()


def test_exact_retry_is_byte_preserving_and_does_not_create_more_records(
    tmp_path: Path,
) -> None:
    root, _, locator, target = _setup(tmp_path)
    first = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    before = _files(root)
    again = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    assert again.evidence_id == first.evidence_id
    assert again.observation_status == "existing"
    assert again.submission_status == "unchanged"
    assert again.completion_state == "ready_for_review"
    assert _files(root) == before


def test_prepared_execution_rechecks_source_before_any_write(tmp_path: Path) -> None:
    root, retained, locator, target = _setup(tmp_path)
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    retained.retained_source_path.write_bytes(b"changed after preflight")
    before = _files(root)
    with pytest.raises(ScanRecoveryExecutionError) as caught:
        execute_prepared_scan_recovery(root, prepared, registry=_registry())
    assert caught.value.stage == "dispatch"
    assert caught.value.verified_observation_id is None
    assert _files(root) == before


def test_missing_explicit_target_fails_in_preflight_without_mutation(
    tmp_path: Path,
) -> None:
    root, _, locator, _ = _setup(tmp_path)
    before = _files(root)
    with pytest.raises(ScanRecoveryExecutionError) as caught:
        recover_scan_review_page(root, FAILURE_ID, route_locator=locator)
    assert caught.value.stage == "preflight"
    assert caught.value.verified_observation_id is None
    assert _files(root) == before


def test_historical_route_recovery_keeps_original_decision_unchanged(
    tmp_path: Path,
) -> None:
    root, _, locator, target = _setup(tmp_path)
    historical = resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    original = historical.resolution_metadata_path.read_bytes()
    completed = recover_scan_review_page(
        root, FAILURE_ID, use_recorded_route=True, registry=_registry()
    )
    assert completed.historical_route_reused
    assert completed.reviewable
    assert historical.resolution_metadata_path.read_bytes() == original
    assert len(tuple(historical.resolution_metadata_path.parent.glob("*.json"))) == 1


def test_existing_selected_page_is_not_reselected_by_recovery(tmp_path: Path) -> None:
    root, _, locator, target = _setup(tmp_path)
    prior_id = _prior_selected(root, locator)
    done = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    assert done.completion_state == "selection_needed"
    assert not done.reviewable
    assert done.assembled.selected_evidence_id == prior_id
    assert done.evidence_id != prior_id
    page = load_submission_manifest(done.assembled.assembled.manifest_path)["pages"][0]
    assert page["selected_evidence_id"] == prior_id
    assert len(page["evidence"]) == 2


@pytest.mark.parametrize("teacher_state", ["needs_rescan", "excluded"])
def test_teacher_decision_is_retained_on_repeat(
    tmp_path: Path, teacher_state: str
) -> None:
    root, _, locator, target = _setup(tmp_path)
    initial = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    observation = initial.assembled.persisted.persisted.observation
    if teacher_state == "needs_rescan":
        mark_submission_page_needs_rescan(
            root, locator.class_id, locator.work_id, observation.student_id, 1
        )
    else:
        exclude_submission_page(
            root, locator.class_id, locator.work_id, observation.student_id, 1
        )
    before = _files(root)
    repeated = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    assert repeated.completion_state == "teacher_action_needed"
    assert not repeated.reviewable
    assert repeated.observation_status == "existing"
    assert repeated.submission_status == "unchanged"
    assert _files(root) == before


def test_persistence_interruption_never_reports_durable_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, locator, target = _setup(tmp_path)
    before = _files(root)
    original = persist_dispatched_scan_recovery

    def interrupted(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("injected persistence interruption")

    monkeypatch.setattr(completion, "persist_dispatched_scan_recovery", interrupted)
    with pytest.raises(ScanRecoveryExecutionError) as caught:
        recover_scan_review_page(
            root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
        )
    assert caught.value.stage == "persistence"
    assert caught.value.verified_observation_id is None
    assert caught.value.__cause__ is not None
    assert _files(root) == before
    monkeypatch.setattr(completion, "persist_dispatched_scan_recovery", original)
    completed = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    assert completed.reviewable


def test_interrupted_assembly_recovers_existing_observation_on_fresh_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, locator, target = _setup(tmp_path)
    original = assemble_persisted_scan_recovery

    def interrupted(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("injected assembly interruption")

    monkeypatch.setattr(completion, "assemble_persisted_scan_recovery", interrupted)
    with pytest.raises(ScanRecoveryExecutionError) as caught:
        recover_scan_review_page(
            root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
        )
    assert caught.value.stage == "assembly"
    assert caught.value.verified_observation_id is not None
    assert caught.value.possible_observation_path is not None
    assert caught.value.possible_observation_path.is_file()
    assert caught.value.possible_evidence_path is not None
    assert caught.value.possible_evidence_path.is_file()
    assert not tuple(root.rglob("submission.json"))
    monkeypatch.setattr(completion, "assemble_persisted_scan_recovery", original)
    recovered = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    assert recovered.evidence_id == caught.value.verified_observation_id
    assert recovered.observation_status == "existing"
    assert recovered.submission_status == "created"
    assert recovered.reviewable


def test_interruption_after_manifest_write_is_idempotently_recovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, locator, target = _setup(tmp_path)
    original = assemble_persisted_scan_recovery

    def after_write(
        workspace_root: str | Path,
        persisted: PersistedScanRecovery,
        *,
        registry: ModuleRegistry | None = None,
    ) -> None:
        original(workspace_root, persisted, registry=registry)
        raise RuntimeError("crash after manifest persistence")

    monkeypatch.setattr(completion, "assemble_persisted_scan_recovery", after_write)
    with pytest.raises(ScanRecoveryExecutionError) as caught:
        recover_scan_review_page(
            root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
        )
    assert caught.value.stage == "assembly"
    before = _files(root)
    assert tuple(root.rglob("submission.json"))
    monkeypatch.setattr(completion, "assemble_persisted_scan_recovery", original)
    recovered = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    assert recovered.submission_status == "unchanged"
    assert recovered.observation_status == "existing"
    assert _files(root) == before


def test_tampered_existing_evidence_never_yields_completion(tmp_path: Path) -> None:
    root, _, locator, target = _setup(tmp_path)
    first = recover_scan_review_page(
        root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
    )
    evidence = first.persisted.persisted.evidence_path
    evidence.write_bytes(b"not the original recovered page")
    before = _files(root)
    with pytest.raises(ScanRecoveryExecutionError) as caught:
        recover_scan_review_page(
            root, FAILURE_ID, route_locator=locator, target=target, registry=_registry()
        )
    assert caught.value.stage == "persistence"
    assert caught.value.verified_observation_id is None
    assert _files(root) == before


def test_invalid_prepared_type_fails_closed(tmp_path: Path) -> None:
    root, _, _, _ = _setup(tmp_path)
    before = _files(root)
    with pytest.raises(ScanRecoveryExecutionError) as caught:
        execute_prepared_scan_recovery(
            root, object(), registry=_registry()  # type: ignore[arg-type]
        )
    assert caught.value.stage == "preflight"
    assert _files(root) == before

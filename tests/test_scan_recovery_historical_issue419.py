"""Issue #419 Slice 6: discover legacy route decisions and safely replay."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.pds2_scan_intake as intake
import quillan.scan_recovery_completion as completion
from quillan.scan_recovery_historical import (
    HistoricalScanRecoveryError,
    discover_historical_scan_recoveries,
    replay_historical_scan_recovery,
)
from quillan.scan_review_resolution import resolve_scan_review_item
from quillan.submission_page_management import (
    exclude_submission_page,
    mark_submission_page_needs_rescan,
)
from tests.review_test_support import _write_assignment
from tests.test_scan_recovery_assembly_issue419 import _prior_selected
from tests.test_scan_recovery_dispatch_issue419 import _registry
from tests.test_scan_recovery_preflight_issue419 import FAILURE_ID, _files, _fixture


def _setup(tmp_path: Path):
    root, retained, locator, target = _fixture(tmp_path)
    _write_assignment(root, class_id=locator.class_id, assignment_id=locator.work_id)
    historical = resolve_scan_review_item(
        root,
        FAILURE_ID,
        action="route_selected",
        route_locator=locator,
        target=target,
    )
    return root, retained, locator, target, historical


def _only(root: Path):
    discovered = discover_historical_scan_recoveries(root)
    assert len(discovered.items) == 1
    return discovered.items[0]


def test_old_resolved_route_is_not_falsely_reported_materialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, retained, _, _, historical = _setup(tmp_path)
    before = _files(root)

    def no_qr(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Historical discovery must not decode QR")

    monkeypatch.setattr(intake, "detect_qr_payload", no_qr)
    found = _only(root)
    assert found.state == "evidence_missing"
    assert found.requires_replay
    assert found.resolution_id == historical.resolution_id
    assert found.failure_id == FAILURE_ID
    assert found.observation_id is not None
    assert found.student_id == "00107"
    assert found.logical_page == 1
    assert retained.retained_source_path.is_file()
    assert _files(root) == before


def test_explicit_historical_replay_creates_reviewable_evidence_and_no_resolution(
    tmp_path: Path,
) -> None:
    root, _, _, _, historical = _setup(tmp_path)
    before_resolution = historical.resolution_metadata_path.read_bytes()
    result = replay_historical_scan_recovery(
        root,
        FAILURE_ID,
        expected_resolution_id=historical.resolution_id,
        registry=_registry(),
    )
    assert result.historical_route_reused
    assert result.observation_status == "created"
    assert result.submission_status == "created"
    assert result.completion_state == "ready_for_review"
    found = _only(root)
    assert found.state == "ready_for_review"
    assert not found.requires_replay
    assert found.selected_evidence_id == result.evidence_id
    assert historical.resolution_metadata_path.read_bytes() == before_resolution
    assert len(tuple(historical.resolution_metadata_path.parent.glob("*.json"))) == 1


def test_exact_replay_repeat_preserves_every_record_byte(tmp_path: Path) -> None:
    root, _, _, _, historical = _setup(tmp_path)
    first = replay_historical_scan_recovery(
        root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
        registry=_registry(),
    )
    before = _files(root)
    again = replay_historical_scan_recovery(
        root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
        registry=_registry(),
    )
    assert again.evidence_id == first.evidence_id
    assert again.observation_status == "existing"
    assert again.submission_status == "unchanged"
    assert _files(root) == before


def test_stale_or_unconfirmed_resolution_is_rejected_without_writes(
    tmp_path: Path,
) -> None:
    root, _, _, _, historical = _setup(tmp_path)
    before = _files(root)
    with pytest.raises(HistoricalScanRecoveryError, match="resolution has changed"):
        replay_historical_scan_recovery(
            root, FAILURE_ID, expected_resolution_id="resolution_stale",
            registry=_registry(),
        )
    with pytest.raises(HistoricalScanRecoveryError, match="exact historical"):
        replay_historical_scan_recovery(
            root, FAILURE_ID, expected_resolution_id="", registry=_registry()
        )
    assert historical.resolution_metadata_path.is_file()
    assert _files(root) == before


def test_assembly_interruption_is_discoverable_and_replayable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, _, _, historical = _setup(tmp_path)
    original = completion.assemble_persisted_scan_recovery

    def interrupted(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("intentional assembly interruption")

    monkeypatch.setattr(completion, "assemble_persisted_scan_recovery", interrupted)
    with pytest.raises(completion.ScanRecoveryExecutionError) as caught:
        replay_historical_scan_recovery(
            root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
            registry=_registry(),
        )
    assert caught.value.stage == "assembly"
    assert caught.value.verified_observation_id is not None
    before = _files(root)
    pending = _only(root)
    assert pending.state == "assembly_pending"
    assert pending.observation_id == caught.value.verified_observation_id
    assert _files(root) == before
    monkeypatch.setattr(completion, "assemble_persisted_scan_recovery", original)
    completed = replay_historical_scan_recovery(
        root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
        registry=_registry(),
    )
    assert completed.observation_status == "existing"
    assert completed.submission_status == "created"
    assert _only(root).state == "ready_for_review"


def test_existing_selection_yields_selection_needed_without_override(
    tmp_path: Path,
) -> None:
    root, _, locator, _, historical = _setup(tmp_path)
    previous_id = _prior_selected(root, locator)
    completed = replay_historical_scan_recovery(
        root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
        registry=_registry(),
    )
    assert completed.completion_state == "selection_needed"
    state = _only(root)
    assert state.state == "selection_needed"
    assert state.selected_evidence_id == previous_id
    assert state.observation_id == completed.evidence_id


@pytest.mark.parametrize("teacher_state", ["needs_rescan", "excluded"])
def test_teacher_controlled_evidence_stays_teacher_controlled(
    tmp_path: Path, teacher_state: str
) -> None:
    root, _, locator, _, historical = _setup(tmp_path)
    first = replay_historical_scan_recovery(
        root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
        registry=_registry(),
    )
    obs = first.persisted.persisted.observation
    if teacher_state == "needs_rescan":
        mark_submission_page_needs_rescan(
            root, locator.class_id, locator.work_id, obs.student_id, 1
        )
    else:
        exclude_submission_page(
            root, locator.class_id, locator.work_id, obs.student_id, 1
        )
    before = _files(root)
    assert _only(root).state == "teacher_action_needed"
    again = replay_historical_scan_recovery(
        root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
        registry=_registry(),
    )
    assert again.completion_state == "teacher_action_needed"
    assert again.observation_status == "existing"
    assert again.submission_status == "unchanged"
    assert _files(root) == before


def test_tampered_saved_evidence_is_blocked_not_counted_as_recovered(
    tmp_path: Path,
) -> None:
    root, _, _, _, historical = _setup(tmp_path)
    saved = replay_historical_scan_recovery(
        root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
        registry=_registry(),
    )
    saved.persisted.persisted.evidence_path.write_bytes(b"damaged artifact")
    before = _files(root)
    blocked = _only(root)
    assert blocked.state == "blocked"
    assert blocked.reason is not None
    assert blocked.observation_id is None
    assert _files(root) == before
    with pytest.raises(completion.ScanRecoveryExecutionError):
        replay_historical_scan_recovery(
            root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
            registry=_registry(),
        )
    assert _files(root) == before


def test_changed_retained_source_is_blocked_without_mutation(tmp_path: Path) -> None:
    root, retained, _, _, _ = _setup(tmp_path)
    retained.retained_source_path.write_bytes(b"changed retained bytes")
    before = _files(root)
    blocked = _only(root)
    assert blocked.state == "blocked"
    assert blocked.reason is not None
    assert _files(root) == before


def test_not_resolved_or_non_route_decision_is_never_replayed(tmp_path: Path) -> None:
    root, _, _, _, historical = _setup(tmp_path)
    deferred = resolve_scan_review_item(root, FAILURE_ID, action="deferred")
    found = discover_historical_scan_recoveries(root)
    assert not found.items
    assert deferred.resolution_id != historical.resolution_id
    before = _files(root)
    with pytest.raises(HistoricalScanRecoveryError):
        replay_historical_scan_recovery(
            root, FAILURE_ID, expected_resolution_id=historical.resolution_id,
            registry=_registry(),
        )
    assert _files(root) == before


def test_read_only_discovery_does_not_call_recovery_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, _, _, _ = _setup(tmp_path)
    before = _files(root)
    monkeypatch.setattr(
        completion, "persist_dispatched_scan_recovery",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("discovery must not persist")
        ),
    )
    assert _only(root).state == "evidence_missing"
    assert _files(root) == before

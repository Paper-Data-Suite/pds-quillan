"""Issue #419 Slice 3: shared transactional persistence for recovered scans."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from pds_core.routing_models import ModuleRecordRef, RouteLocator

import quillan.pds2_scan_intake as intake
import quillan.response_page_observation_persistence as observation_writer
import quillan.routed_evidence as routed_evidence
import quillan.scan_recovery_preflight as preflight
from quillan.module_errors import (
    QuillanObservationIntegrityError,
    QuillanObservationPersistenceError,
)
from quillan.pds2_scan_intake import QuillanScanPageOutcome
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.response_page_observations import list_quillan_page_observations
from quillan.scan_recovery_dispatch import (
    DispatchedScanRecovery,
    dispatch_prepared_scan_recovery,
)
from quillan.scan_recovery_persistence import (
    ScanRecoveryPersistenceError,
    persist_dispatched_scan_recovery,
)
from quillan.scan_recovery_preflight import prepare_scan_review_recovery
from quillan.scan_review_resolution import resolve_scan_review_item
from tests.test_scan_recovery_dispatch_issue419 import _registry
from tests.test_scan_recovery_preflight_issue419 import FAILURE_ID, _files, _fixture


def _dispatched(
    root: Path, locator: RouteLocator, target: ModuleRecordRef
) -> DispatchedScanRecovery:
    prepared = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    return dispatch_prepared_scan_recovery(root, prepared, registry=_registry())


def test_recovery_creates_canonical_evidence_without_assembly_or_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    dispatched = _dispatched(root, locator, target)
    before = _files(root)

    def no_qr(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("manual recovery must never decode the QR")

    monkeypatch.setattr(intake, "detect_qr_payload", no_qr)
    recovered = persist_dispatched_scan_recovery(
        root, dispatched, registry=_registry()
    )

    saved = recovered.persisted
    assert recovered.status == "created"
    assert saved.observation.source_scan_id == retained.source_scan_id
    assert saved.observation.source_page_number == 1
    assert saved.observation.page_id == target.record_id
    assert saved.observation.student_id == "00107"
    assert saved.evidence_path.read_bytes() == retained.retained_source_path.read_bytes()
    assert saved.observation_path.is_file()
    assert list_quillan_page_observations(
        root, saved.observation.class_id, saved.observation.assignment_id
    ) == (saved.observation,)
    changed = set(_files(root)) - set(before)
    assert changed == {
        saved.observation_relative_path,
        saved.evidence_relative_path,
    }
    for filename, content in before.items():
        assert _files(root)[filename] == content
    assert not (root / "scans" / "review" / "resolutions").exists()
    assert not tuple(root.rglob("submission.json"))


def test_exact_retry_is_verified_existing_without_duplicate(
    tmp_path: Path,
) -> None:
    root, _, locator, target = _fixture(tmp_path)
    dispatched = _dispatched(root, locator, target)
    first = persist_dispatched_scan_recovery(root, dispatched, registry=_registry())
    after_first = _files(root)
    second = persist_dispatched_scan_recovery(root, dispatched, registry=_registry())
    assert (first.status, second.status) == ("created", "existing")
    assert second.persisted.observation == first.persisted.observation
    assert _files(root) == after_first


def test_normal_intake_uses_identical_observation_transaction(tmp_path: Path) -> None:
    root, _, locator, target = _fixture(tmp_path)
    dispatched = _dispatched(root, locator, target)
    recovered = persist_dispatched_scan_recovery(
        root, dispatched, registry=_registry()
    )
    # Synthetic normal-intake fixture only, to prove both APIs share the same
    # authoritative writer and deterministic observation identity.
    normal = QuillanScanPageOutcome(
        source_page_number=dispatched.request.source_page_number,
        terminal_category="dispatch_success",
        retained_source=dispatched.request.retained_source,
        raw_payload_text="PDS2 synthetic test fixture",
        locator=dispatched.request.locator,
        dispatch_request=dispatched.request,
        dispatch_outcome=dispatched.success,
    )
    existing = persist_quillan_page_observation(root, normal)
    assert existing.status == "existing"
    assert existing.observation == recovered.persisted.observation
    assert existing.evidence_path == recovered.persisted.evidence_path


def test_historical_resolved_route_can_persist_without_new_resolution(
    tmp_path: Path,
) -> None:
    root, _, locator, target = _fixture(tmp_path)
    old = resolve_scan_review_item(
        root,
        FAILURE_ID,
        action="route_selected",
        route_locator=locator,
        target=target,
    )
    before = old.resolution_metadata_path.read_bytes()
    prepared = prepare_scan_review_recovery(root, FAILURE_ID, use_recorded_route=True)
    dispatched = dispatch_prepared_scan_recovery(
        root, prepared, registry=_registry()
    )
    recovered = persist_dispatched_scan_recovery(
        root, dispatched, registry=_registry()
    )
    assert recovered.status == "created"
    assert old.resolution_metadata_path.read_bytes() == before
    assert tuple(old.resolution_metadata_path.parent.glob("*.json")) == (
        old.resolution_metadata_path,
    )


def test_changed_source_after_dispatch_fails_before_writing(tmp_path: Path) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    dispatched = _dispatched(root, locator, target)
    retained.retained_source_path.write_bytes(b"changed after Core dispatch")
    before = _files(root)
    with pytest.raises(ScanRecoveryPersistenceError, match="reverified"):
        persist_dispatched_scan_recovery(root, dispatched, registry=_registry())
    assert _files(root) == before


def test_removed_registration_after_dispatch_fails_before_writing(
    tmp_path: Path,
) -> None:
    from pds_core.routes import route_registration_path

    root, _, locator, target = _fixture(tmp_path)
    dispatched = _dispatched(root, locator, target)
    route_registration_path(root, locator).unlink()
    before = _files(root)
    with pytest.raises(ScanRecoveryPersistenceError, match="reverified"):
        persist_dispatched_scan_recovery(root, dispatched, registry=_registry())
    assert _files(root) == before


def test_tampered_dispatch_result_cannot_persist(tmp_path: Path) -> None:
    root, _, locator, target = _fixture(tmp_path)
    dispatched = _dispatched(root, locator, target)
    forged = replace(
        dispatched,
        page_result=replace(dispatched.page_result, student_id="other_student"),
    )
    before = _files(root)
    with pytest.raises(ScanRecoveryPersistenceError, match="stale or contradictory"):
        persist_dispatched_scan_recovery(root, forged, registry=_registry())
    assert _files(root) == before


def test_wrong_object_rejected_before_mutation(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)
    with pytest.raises(ScanRecoveryPersistenceError, match="exact dispatched"):
        persist_dispatched_scan_recovery(root, object())  # type: ignore[arg-type]


def test_orphan_existing_evidence_fails_closed(tmp_path: Path) -> None:
    root, _, locator, target = _fixture(tmp_path)
    dispatched = _dispatched(root, locator, target)
    first = persist_dispatched_scan_recovery(root, dispatched, registry=_registry())
    first.persisted.observation_path.unlink()
    with pytest.raises(QuillanObservationIntegrityError, match="Orphan"):
        persist_dispatched_scan_recovery(root, dispatched, registry=_registry())
    assert first.persisted.evidence_path.exists()


def test_persistence_transaction_rolls_back_on_observation_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, retained, locator, target = _fixture(tmp_path)
    dispatched = _dispatched(root, locator, target)
    original_source = retained.retained_source_path.read_bytes()
    original_install = observation_writer._install_exclusive
    count = 0

    def fail_second(temp: Path, dest: Path) -> object:
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("injected observation install failure")
        return original_install(temp, dest)

    monkeypatch.setattr(observation_writer, "_install_exclusive", fail_second)
    with pytest.raises(QuillanObservationPersistenceError, match="rolled back"):
        persist_dispatched_scan_recovery(root, dispatched, registry=_registry())
    assert retained.retained_source_path.read_bytes() == original_source
    assert not tuple(root.rglob("obs_*.json"))
    monkeypatch.undo()
    retried = persist_dispatched_scan_recovery(root, dispatched, registry=_registry())
    assert retried.status == "created"


def test_recovery_pdf_page_two_produces_one_png(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, locator, target = _fixture(
        tmp_path, extension=".pdf", physical_page=2
    )
    monkeypatch.setattr(
        preflight, "retained_source_page_count", lambda *_a, **_k: 3
    )
    physical_pages: list[int] = []

    def render_one(
        _retained: object, number: int, *, workspace_root: Path
    ) -> NDArray[np.uint8]:
        physical_pages.append(number)
        return np.full((16, 16, 3), 255, dtype=np.uint8)

    monkeypatch.setattr(routed_evidence, "load_retained_page_for_qr", render_one)
    dispatched = _dispatched(root, locator, target)
    recovered = persist_dispatched_scan_recovery(
        root, dispatched, registry=_registry()
    )
    assert physical_pages == [2]
    assert recovered.persisted.evidence_path.suffix == ".png"
    assert recovered.persisted.observation.routed_evidence_kind == (
        "rendered_pdf_page_png"
    )
    assert recovered.persisted.observation.source_page_number == 2
    assert not tuple(root.rglob("submission.json"))

"""Issue #419 Slice 4: recovered evidence becomes submission-available."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pds_core.module_dispatch import RouteDispatchRequest, dispatch_route
from pds_core.routing_models import RouteLocator
from pds_core.scan_retention import retain_source_scan

import quillan.scan_recovery_assembly as recovery_assembly
import quillan.submission_review_opening as review_opening
from quillan.printable_response_persistence import (
    load_printable_response_page_context,
)
from quillan.response_page_observation_persistence import (
    persist_quillan_dispatch_success,
)
from quillan.scan_recovery_assembly import (
    ScanRecoveryAssemblyError,
    assemble_persisted_scan_recovery,
)
from quillan.scan_recovery_dispatch import dispatch_prepared_scan_recovery
from quillan.scan_recovery_persistence import persist_dispatched_scan_recovery
from quillan.scan_recovery_preflight import prepare_scan_review_recovery
from quillan.scan_review_resolution import resolve_scan_review_item
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_observation_assembly import (
    assemble_quillan_submission_manifests,
)
from quillan.submission_page_management import (
    exclude_submission_page,
    mark_submission_page_needs_rescan,
)
from tests.review_test_support import _write_assignment
from tests.test_scan_recovery_dispatch_issue419 import _registry
from tests.test_scan_recovery_preflight_issue419 import FAILURE_ID, _files, _fixture


def _setup(tmp_path: Path):
    root, retained, locator, target = _fixture(tmp_path)
    _write_assignment(root, class_id=locator.class_id, assignment_id=locator.work_id)
    preview = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    dispatched = dispatch_prepared_scan_recovery(root, preview, registry=_registry())
    persisted = persist_dispatched_scan_recovery(
        root, dispatched, registry=_registry()
    )
    return root, retained, locator, target, persisted


def _prior_selected(root: Path, locator: RouteLocator) -> str:
    """Create a different valid observation and select it through assembly."""
    selected = root.parent / "prior_scan.png"
    Image.new("RGB", (24, 16), "black").save(selected)
    retained = retain_source_scan(root, selected)
    success = dispatch_route(
        root, _registry(), RouteDispatchRequest(locator, retained, 1)
    )
    previous = persist_quillan_dispatch_success(root, success)
    batch = assemble_quillan_submission_manifests(
        root, locator.class_id, locator.work_id,
        observation_ids=(previous.observation.observation_id,),
    )
    assert not batch.failures
    assert len(batch.assembled) == 1
    manifest = load_submission_manifest(batch.assembled[0].manifest_path)
    assert manifest["pages"][0]["selected_evidence_id"] == (
        previous.observation.observation_id
    )
    return previous.observation.observation_id


def _setup_with_prior_page(
    tmp_path: Path, *, teacher_state: str | None = None
):
    """Assemble a selected original BEFORE persisting the recovered occurrence.

    The assembler discovers every observation belonging to the student even
    when an observation_ids filter is passed. Reversing this setup order would
    create a duplicate page from the outset with no existing selection.
    """
    root, retained, locator, target = _fixture(tmp_path)
    _write_assignment(root, class_id=locator.class_id, assignment_id=locator.work_id)
    previous = _prior_selected(root, locator)
    if teacher_state is not None:
        context = load_printable_response_page_context(
            root, locator.work, target.record_id
        )
        if teacher_state == "needs_rescan":
            mark_submission_page_needs_rescan(
                root, locator.class_id, locator.work_id, context.student_id, 1
            )
        elif teacher_state == "excluded":
            exclude_submission_page(
                root, locator.class_id, locator.work_id, context.student_id, 1
            )
        else:
            raise ValueError("Unknown teacher state in test setup.")
    preview = prepare_scan_review_recovery(
        root, FAILURE_ID, route_locator=locator, target=target
    )
    dispatched = dispatch_prepared_scan_recovery(root, preview, registry=_registry())
    persisted = persist_dispatched_scan_recovery(
        root, dispatched, registry=_registry()
    )
    return root, retained, locator, target, persisted, previous


def test_missing_page_becomes_selected_and_openable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, retained, locator, _, persisted = _setup(tmp_path)
    before_source = retained.retained_source_path.read_bytes()
    opened_paths: list[Path] = []

    def fake_open(workspace_root: Path, relative_path: str):
        path = workspace_root.joinpath(*Path(relative_path).parts)
        assert path.is_file()
        opened_paths.append(path)
        return SimpleNamespace(evidence_path=path, evidence_relative_path=relative_path)

    monkeypatch.setattr(review_opening, "open_workspace_evidence", fake_open)
    result = assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    assert result.reviewable is True
    assert result.evidence_state == "ready_for_review"
    assert result.assembled.status == "created"
    assert result.selected_evidence_id == persisted.persisted.observation.observation_id
    opened = review_opening.open_student_submission_for_review(
        root, locator.class_id, locator.work_id,
        persisted.persisted.observation.student_id,
        page_number=1,
    )
    assert opened.evidence_id == result.recovery_evidence_id
    assert opened_paths == [persisted.persisted.evidence_path]
    assert retained.retained_source_path.read_bytes() == before_source
    assert not (root / "scans" / "review" / "resolutions").exists()


def test_exact_retry_does_not_rewrite_manifest(tmp_path: Path) -> None:
    root, _, _, _, persisted = _setup(tmp_path)
    first = assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    before = _files(root)
    repeated = assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    assert repeated.assembled.status == "unchanged"
    assert repeated.evidence_state == "ready_for_review"
    assert repeated.recovery_evidence_id == first.recovery_evidence_id
    assert _files(root) == before


def test_existing_selected_evidence_is_preserved_and_recovery_is_candidate(
    tmp_path: Path,
) -> None:
    root, _, locator, _, persisted, previous = _setup_with_prior_page(tmp_path)
    assembled = assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    assert assembled.evidence_state == "selection_needed"
    assert assembled.reviewable is False
    assert assembled.selected_evidence_id == previous
    page = load_submission_manifest(assembled.assembled.manifest_path)["pages"][0]
    assert page["page_state"] == "duplicate"
    assert page["selected_evidence_id"] == previous
    assert {item["evidence_id"] for item in page["evidence"]} == {
        previous, assembled.recovery_evidence_id
    }
    assert [item["evidence_role"] for item in page["evidence"]] == [
        "selected", "candidate"
    ]


@pytest.mark.parametrize("teacher_state", ["needs_rescan", "excluded"])
def test_teacher_controlled_state_is_not_overridden(
    tmp_path: Path, teacher_state: str
) -> None:
    root, _, locator, _, persisted, previous = _setup_with_prior_page(
        tmp_path, teacher_state=teacher_state
    )
    result = assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    assert result.evidence_state == "teacher_action_needed"
    assert result.reviewable is False
    assert result.page_state == teacher_state
    assert result.selected_evidence_id is None
    page = load_submission_manifest(result.assembled.manifest_path)["pages"][0]
    assert page["page_state"] == teacher_state
    assert page["selected_evidence_id"] is None
    assert {item["evidence_id"] for item in page["evidence"]} == {
        previous, result.recovery_evidence_id
    }


@pytest.mark.parametrize("teacher_state", ["needs_rescan", "excluded"])
def test_retry_after_teacher_marks_recovered_evidence_inactive(
    tmp_path: Path, teacher_state: str
) -> None:
    root, _, locator, _, persisted = _setup(tmp_path)
    first = assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    assert first.reviewable
    student = persisted.persisted.observation.student_id
    if teacher_state == "needs_rescan":
        mark_submission_page_needs_rescan(
            root, locator.class_id, locator.work_id, student, 1
        )
    else:
        exclude_submission_page(root, locator.class_id, locator.work_id, student, 1)
    before = _files(root)
    repeated = assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    assert repeated.evidence_state == "teacher_action_needed"
    assert not repeated.reviewable
    assert repeated.page_state == teacher_state
    assert repeated.selected_evidence_id is None
    assert repeated.assembled.status == "unchanged"
    assert _files(root) == before


def test_historical_route_assembly_preserves_resolution_bytes(tmp_path: Path) -> None:
    root, _, locator, target = _fixture(tmp_path)
    _write_assignment(root, class_id=locator.class_id, assignment_id=locator.work_id)
    historical = resolve_scan_review_item(
        root, FAILURE_ID, action="route_selected", route_locator=locator, target=target
    )
    preview = prepare_scan_review_recovery(root, FAILURE_ID, use_recorded_route=True)
    dispatched = dispatch_prepared_scan_recovery(root, preview, registry=_registry())
    persisted = persist_dispatched_scan_recovery(root, dispatched, registry=_registry())
    before = historical.resolution_metadata_path.read_bytes()
    result = assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    assert result.reviewable
    assert historical.resolution_metadata_path.read_bytes() == before
    assert len(tuple(historical.resolution_metadata_path.parent.glob("*.json"))) == 1


def test_assembly_failure_keeps_verified_observation_and_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, _, _, persisted = _setup(tmp_path)
    original = recovery_assembly.assemble_quillan_submission_manifests
    observation_before = persisted.persisted.observation_path.read_bytes()
    evidence_before = persisted.persisted.evidence_path.read_bytes()

    def fail(*_args: object, **_kwargs: object):
        raise RuntimeError("simulated assembly interruption")

    monkeypatch.setattr(
        recovery_assembly, "assemble_quillan_submission_manifests", fail
    )
    with pytest.raises(ScanRecoveryAssemblyError, match="assembly failed"):
        assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    assert persisted.persisted.observation_path.read_bytes() == observation_before
    assert persisted.persisted.evidence_path.read_bytes() == evidence_before
    monkeypatch.setattr(
        recovery_assembly, "assemble_quillan_submission_manifests", original
    )
    result = assemble_persisted_scan_recovery(root, persisted, registry=_registry())
    assert result.reviewable


def test_wrong_recovery_type_is_rejected(tmp_path: Path) -> None:
    root, _, _, _, _ = _setup(tmp_path)
    with pytest.raises(ScanRecoveryAssemblyError, match="exact persisted"):
        assemble_persisted_scan_recovery(root, object())  # type: ignore[arg-type]

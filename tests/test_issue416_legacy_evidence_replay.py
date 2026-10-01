"""Issue #416 Slice 5: replay preserves an existing legacy evidence path."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from quillan.module_errors import QuillanObservationIntegrityError
from quillan.pds2_scan_intake import QuillanScanPageOutcome
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.response_page_observations import (
    canonical_response_page_observation_json,
)
from quillan.work_paths import quillan_work_ref, routed_evidence_path
from tests.observation_test_support import successful_image_page


def _legacy_pair(
    tmp_path: Path,
) -> tuple[QuillanScanPageOutcome, Path, Path, bytes, bytes]:
    outcome = successful_image_page(tmp_path)
    persisted = persist_quillan_page_observation(tmp_path, outcome)
    observation = persisted.observation
    bounded_path = persisted.evidence_path
    legacy_name = (
        f"response_{observation.student_id}_pg_{observation.logical_page:03d}__"
        f"{observation.observation_id}{bounded_path.suffix}"
    )
    legacy_path = bounded_path.with_name(legacy_name)
    bounded_path.replace(legacy_path)
    legacy_observation = replace(
        observation,
        routed_evidence_path=legacy_path.relative_to(tmp_path).as_posix(),
    )
    persisted.observation_path.write_bytes(
        canonical_response_page_observation_json(legacy_observation)
    )
    return (
        outcome,
        persisted.observation_path,
        legacy_path,
        persisted.observation_path.read_bytes(),
        legacy_path.read_bytes(),
    )


def test_legacy_pair_replay_returns_existing_without_migration(
    tmp_path: Path,
) -> None:
    (
        outcome,
        observation_path,
        legacy_path,
        observation_bytes,
        evidence_bytes,
    ) = _legacy_pair(tmp_path)

    replay = persist_quillan_page_observation(tmp_path, outcome)

    assert replay.status == "existing"
    assert replay.observation_path == observation_path
    assert replay.evidence_path == legacy_path
    assert replay.evidence_relative_path == replay.observation.routed_evidence_path
    assert observation_path.read_bytes() == observation_bytes
    assert legacy_path.read_bytes() == evidence_bytes

    bounded = routed_evidence_path(
        tmp_path,
        quillan_work_ref(
            replay.observation.class_id,
            replay.observation.assignment_id,
        ),
        replay.observation.issuance_id,
        replay.observation.student_id,
        replay.observation.logical_page,
        replay.observation.observation_id,
        legacy_path.suffix,
    )
    assert not bounded.exists()


def test_legacy_pair_replay_rejects_changed_evidence_without_writing_bounded(
    tmp_path: Path,
) -> None:
    outcome, observation_path, legacy_path, observation_bytes, _ = _legacy_pair(
        tmp_path
    )
    legacy_path.write_bytes(b"changed legacy evidence")
    with pytest.raises(QuillanObservationIntegrityError):
        persist_quillan_page_observation(tmp_path, outcome)

    assert observation_path.read_bytes() == observation_bytes
    assert legacy_path.read_bytes() == b"changed legacy evidence"
    assert not tuple(
        path
        for path in legacy_path.parent.glob("obs_*.*")
        if path != observation_path
    )


def test_legacy_pair_replay_rejects_parallel_bounded_evidence(
    tmp_path: Path,
) -> None:
    outcome, observation_path, legacy_path, observation_bytes, evidence_bytes = (
        _legacy_pair(tmp_path)
    )
    replay_observation_id = observation_path.stem
    bounded = legacy_path.with_name(f"{replay_observation_id}{legacy_path.suffix}")
    bounded.write_bytes(evidence_bytes)

    with pytest.raises(
        QuillanObservationIntegrityError,
        match="unexpected bounded evidence",
    ):
        persist_quillan_page_observation(tmp_path, outcome)

    assert observation_path.read_bytes() == observation_bytes
    assert legacy_path.read_bytes() == evidence_bytes
    assert bounded.read_bytes() == evidence_bytes


def test_legacy_pair_replay_rejects_missing_persisted_evidence_without_repair(
    tmp_path: Path,
) -> None:
    outcome, observation_path, legacy_path, observation_bytes, _ = _legacy_pair(
        tmp_path
    )
    legacy_path.unlink()

    with pytest.raises(QuillanObservationIntegrityError):
        persist_quillan_page_observation(tmp_path, outcome)

    assert observation_path.read_bytes() == observation_bytes
    assert not legacy_path.exists()
    assert not tuple(legacy_path.parent.glob("obs_*.*"))

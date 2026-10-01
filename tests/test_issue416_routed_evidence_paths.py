"""Issue #416 Slice 4: bounded routed-evidence writer and legacy reader."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from quillan.response_page_observation_persistence import (
    PersistedQuillanPageObservation,
    persist_quillan_page_observation,
)
from quillan.response_page_observations import (
    canonical_response_page_observation_json,
    list_quillan_page_observations,
)
from quillan.work_paths import (
    ROUTED_EVIDENCE_FILENAME_MAX_LENGTH,
    QuillanWorkPathError,
    quillan_work_ref,
    resolve_routed_evidence_path,
    routed_evidence_path,
)
from tests.observation_test_support import successful_image_page


ISSUANCE_ID = "iss_" + "1" * 32
OBSERVATION_ID = "obs_" + "2" * 32


def _legacy_relative(
    root: Path,
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    logical_page: int,
    observation_id: str,
    issuance_id: str,
    extension: str,
) -> str:
    return (
        root
        / "classes"
        / class_id
        / "modules"
        / "quillan"
        / "work"
        / assignment_id
        / "scans"
        / "evidence"
        / issuance_id
        / (
            f"response_{student_id}_pg_{logical_page:03d}__"
            f"{observation_id}{extension}"
        )
    ).relative_to(root).as_posix()


def test_new_writer_leaf_is_fixed_bound_and_student_independent(
    tmp_path: Path,
) -> None:
    work_ref = quillan_work_ref("class_a", "assignment_a")
    short = routed_evidence_path(
        tmp_path, work_ref, ISSUANCE_ID, "student_1", 1, OBSERVATION_ID, ".jpeg"
    )
    long = routed_evidence_path(
        tmp_path,
        work_ref,
        ISSUANCE_ID,
        "student_" + "x" * 400,
        1,
        OBSERVATION_ID,
        ".jpeg",
    )

    assert short.name == long.name == f"{OBSERVATION_ID}.jpeg"
    assert len(short.name) == ROUTED_EVIDENCE_FILENAME_MAX_LENGTH
    assert "student" not in short.name


def test_resolver_accepts_bounded_and_legacy_forms(tmp_path: Path) -> None:
    work_ref = quillan_work_ref("class_a", "assignment_a")
    bounded = routed_evidence_path(
        tmp_path, work_ref, ISSUANCE_ID, "student_1", 1, OBSERVATION_ID, ".png"
    )
    bounded_relative = bounded.relative_to(tmp_path).as_posix()
    legacy_relative = _legacy_relative(
        tmp_path,
        class_id="class_a",
        assignment_id="assignment_a",
        student_id="student_1",
        logical_page=1,
        observation_id=OBSERVATION_ID,
        issuance_id=ISSUANCE_ID,
        extension=".png",
    )

    assert resolve_routed_evidence_path(
        tmp_path,
        work_ref,
        ISSUANCE_ID,
        "student_1",
        1,
        OBSERVATION_ID,
        ".png",
        bounded_relative,
    ) == bounded
    assert resolve_routed_evidence_path(
        tmp_path,
        work_ref,
        ISSUANCE_ID,
        "student_1",
        1,
        OBSERVATION_ID,
        ".png",
        legacy_relative,
    ) == tmp_path.joinpath(*Path(legacy_relative).parts)


def test_resolver_rejects_arbitrary_evidence_leaf(tmp_path: Path) -> None:
    work_ref = quillan_work_ref("class_a", "assignment_a")
    relative = (
        "classes/class_a/modules/quillan/work/assignment_a/scans/evidence/"
        f"{ISSUANCE_ID}/arbitrary.png"
    )
    with pytest.raises(QuillanWorkPathError):
        resolve_routed_evidence_path(
            tmp_path,
            work_ref,
            ISSUANCE_ID,
            "student_1",
            1,
            OBSERVATION_ID,
            ".png",
            relative,
        )


def test_new_persistence_uses_bounded_leaf(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )

    assert persisted.evidence_path.name == f"{persisted.observation.observation_id}.png"
    assert persisted.observation.student_id not in persisted.evidence_path.name
    assert len(persisted.evidence_path.name) <= ROUTED_EVIDENCE_FILENAME_MAX_LENGTH


def test_legacy_observation_and_evidence_remain_discoverable(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    legacy_relative = _legacy_relative(
        tmp_path,
        class_id=observation.class_id,
        assignment_id=observation.assignment_id,
        student_id=observation.student_id,
        logical_page=observation.logical_page,
        observation_id=observation.observation_id,
        issuance_id=observation.issuance_id,
        extension=persisted.evidence_path.suffix,
    )
    legacy_path = tmp_path.joinpath(*Path(legacy_relative).parts)
    persisted.evidence_path.replace(legacy_path)
    legacy_observation = replace(observation, routed_evidence_path=legacy_relative)
    persisted.observation_path.write_bytes(
        canonical_response_page_observation_json(legacy_observation)
    )

    loaded = list_quillan_page_observations(
        tmp_path, observation.class_id, observation.assignment_id
    )

    assert loaded == (legacy_observation,)
    assert legacy_path.is_file()
    assert not persisted.evidence_path.exists()

    existing = PersistedQuillanPageObservation(
        workspace_root=tmp_path,
        observation=legacy_observation,
        observation_path=persisted.observation_path,
        observation_relative_path=persisted.observation_relative_path,
        evidence_path=legacy_path,
        evidence_relative_path=legacy_relative,
        status="existing",
    )
    assert existing.evidence_path == legacy_path

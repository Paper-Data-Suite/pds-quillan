"""Read-only status consumes observation-backed manifests and discovery."""

from pathlib import Path

import pytest

from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.submission_observation_assembly import (
    assemble_quillan_submission_manifests,
)
from quillan.submission_manifest import SubmissionManifestError
from quillan.submission_manifest_paths import submission_manifest_path
from quillan.submission_status import list_assignment_submission_status
from tests.observation_test_support import successful_image_page


def test_status_lists_observed_and_assembled_student_without_writes(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert not assembled.failures
    before = assembled.assembled[0].manifest_path.read_bytes()
    status = list_assignment_submission_status(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert status.students_with_manifests == (observation.student_id,)
    assert status.students_with_routed_evidence == (observation.student_id,)
    assert status.unassembled_routed_files == ()
    assert assembled.assembled[0].manifest_path.read_bytes() == before


def test_status_is_empty_without_observations_or_manifests(tmp_path: Path) -> None:
    status = list_assignment_submission_status(
        tmp_path, "class_synthetic", "assignment_synthetic"
    )
    assert status.students_with_manifests == ()
    assert status.students_with_routed_evidence == ()
    assert status.student_statuses == ()


def test_invalid_existing_manifest_remains_a_status_error(tmp_path: Path) -> None:
    path = submission_manifest_path(
        tmp_path, "class_synthetic", "assignment_synthetic", "student_001"
    )
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SubmissionManifestError, match="not valid JSON"):
        list_assignment_submission_status(
            tmp_path, "class_synthetic", "assignment_synthetic"
        )

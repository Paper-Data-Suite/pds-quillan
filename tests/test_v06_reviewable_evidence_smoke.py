"""End-to-end smoke coverage for observation-backed reviewable evidence."""

from pathlib import Path

import pytest

import quillan.submission_assembly as submission_assembly
import quillan.submission_review_opening
from quillan.evidence_opening import OpenedEvidence
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_observation_assembly import (
    assemble_quillan_submission_manifests,
)
from quillan.submission_review_opening import open_student_submission_for_review
from quillan.submission_review_state import update_submission_review_state
from quillan.submission_status import list_assignment_submission_status
from tests.observation_test_support import successful_image_page
from tests.review_test_support import _write_assignment


def test_legacy_caller_metadata_assembly_api_is_absent() -> None:
    assert not hasattr(submission_assembly, "RoutedSubmissionEvidence")
    assert not hasattr(submission_assembly, "build_submission_manifest")
    assert not hasattr(submission_assembly, "assemble_submission_manifest")


def test_observation_backed_evidence_remains_reviewable_and_non_destructive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    evidence_before = persisted.evidence_path.read_bytes()
    assembled = assemble_quillan_submission_manifests(
        tmp_path,
        observation.class_id,
        observation.assignment_id,
        timestamp="2026-07-21T12:00:00+00:00",
    )
    _write_assignment(
        tmp_path,
        class_id=observation.class_id,
        assignment_id=observation.assignment_id,
    )
    assert not assembled.failures
    manifest_path = assembled.assembled[0].manifest_path
    manifest = load_submission_manifest(manifest_path)
    assert manifest["pages"][0]["selected_evidence_id"] == observation.observation_id

    opened_paths: list[Path] = []

    def mock_open_workspace_evidence(
        workspace_root: str | Path,
        evidence_path: str | Path,
    ) -> OpenedEvidence:
        resolved = (Path(workspace_root) / evidence_path).resolve()
        opened_paths.append(resolved)
        return OpenedEvidence(
            evidence_path=resolved,
            evidence_relative_path=resolved.relative_to(tmp_path).as_posix(),
        )

    monkeypatch.setattr(
        quillan.submission_review_opening,
        "open_workspace_evidence",
        mock_open_workspace_evidence,
    )
    opened = open_student_submission_for_review(
        tmp_path,
        observation.class_id,
        observation.assignment_id,
        observation.student_id,
    )
    assert opened.evidence_path == persisted.evidence_path.resolve()
    assert opened_paths == [persisted.evidence_path.resolve()]

    update_submission_review_state(
        tmp_path,
        observation.class_id,
        observation.assignment_id,
        observation.student_id,
        "reviewed",
        updated_at="2026-07-21T12:30:00+00:00",
    )
    status = list_assignment_submission_status(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert status.student_statuses[0].submission_state == "reviewed"
    assert persisted.evidence_path.read_bytes() == evidence_before

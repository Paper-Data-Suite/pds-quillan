"""End-to-end smoke coverage for the v0.6 reviewable-evidence workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.submission_review_opening
from quillan.assignment_submission_assembly import (
    assemble_assignment_submissions,
)
from quillan.evidence_opening import OpenedEvidence
from quillan.submission_manifest import (
    load_submission_manifest,
    validate_submission_manifest,
)
from quillan.submission_review_opening import (
    open_student_submission_for_review,
)
from quillan.submission_review_state import update_submission_review_state
from quillan.submission_status import list_assignment_submission_status

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_IDS = ("00107", "00108")
ASSEMBLED_AT = "2026-06-22T12:00:00+00:00"
REVIEWED_AT = "2026-06-22T12:30:00+00:00"


def test_v06_synthetic_reviewable_evidence_workflow_is_non_destructive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scans_dir = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "scans"
    )
    scans_dir.mkdir(parents=True)
    evidence_paths = {
        student_id: scans_dir / f"response_{student_id}_pg_001.pdf"
        for student_id in STUDENT_IDS
    }
    for student_id, path in evidence_paths.items():
        path.write_bytes(f"synthetic {student_id} page 1 evidence".encode())

    evidence_before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in evidence_paths.values()
    }

    assembly = assemble_assignment_submissions(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        expected_pages=1,
        created_at=ASSEMBLED_AT,
        updated_at=ASSEMBLED_AT,
    )

    expected_manifest_paths = {
        (
            Path("classes")
            / CLASS_ID
            / "modules"
            / "quillan"
            / "work"
            / ASSIGNMENT_ID
            / "submissions"
            / student_id
            / "submission.json"
        )
        for student_id in STUDENT_IDS
    }
    assert assembly.students_with_evidence == STUDENT_IDS
    assert not assembly.skipped_existing_manifests
    assert not assembly.skipped_files
    assert {
        path.relative_to(tmp_path) for path in assembly.written_manifests
    } == expected_manifest_paths

    manifests = {}
    for manifest_path in assembly.written_manifests:
        manifest = load_submission_manifest(manifest_path)
        validate_submission_manifest(manifest)
        manifests[manifest["student_id"]] = manifest
        assert manifest["class_id"] == CLASS_ID
        assert manifest["assignment_id"] == ASSIGNMENT_ID
        assert manifest["submission_state"] == "unreviewed"
        assert manifest["expected_pages"] == 1
        assert len(manifest["pages"]) == 1
        page = manifest["pages"][0]
        assert page["page_state"] == "present"
        assert page["selected_evidence_id"] is not None
        assert len(page["evidence"]) == 1
        assert Path(page["evidence"][0]["routed_evidence_path"]) == (
            evidence_paths[manifest["student_id"]].relative_to(tmp_path)
        )

    status = list_assignment_submission_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        expected_pages=1,
    )
    assert status.students_with_manifests == STUDENT_IDS
    assert status.students_with_routed_evidence == STUDENT_IDS
    assert not status.students_without_manifests
    assert not status.unassembled_routed_files
    assert not status.skipped_routed_files
    assert all(
        student.submission_state == "unreviewed"
        and len(student.pages) == 1
        and student.pages[0].page_state == "present"
        and student.pages[0].selected_evidence_id is not None
        for student in status.student_statuses
    )

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
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_IDS[0],
    )
    assert opened.evidence_path == evidence_paths[STUDENT_IDS[0]].resolve()
    assert opened_paths == [evidence_paths[STUDENT_IDS[0]].resolve()]

    original_manifest = manifests[STUDENT_IDS[0]]
    update_submission_review_state(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_IDS[0],
        "reviewed",
        updated_at=REVIEWED_AT,
    )
    reviewed_manifest = load_submission_manifest(opened.manifest_path)
    unchanged_original = {
        key: value
        for key, value in original_manifest.items()
        if key not in {"submission_state", "updated_at"}
    }
    unchanged_reviewed = {
        key: value
        for key, value in reviewed_manifest.items()
        if key not in {"submission_state", "updated_at"}
    }
    assert unchanged_reviewed == unchanged_original
    assert reviewed_manifest["submission_state"] == "reviewed"
    assert reviewed_manifest["updated_at"] == REVIEWED_AT

    reviewed_status = list_assignment_submission_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        expected_pages=1,
    )
    states = {
        student.student_id: student.submission_state
        for student in reviewed_status.student_statuses
    }
    assert states == {"00107": "reviewed", "00108": "unreviewed"}

    assert {
        path.relative_to(tmp_path): path.read_bytes()
        for path in evidence_paths.values()
    } == evidence_before
    all_files = {
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert all_files == set(evidence_before) | expected_manifest_paths

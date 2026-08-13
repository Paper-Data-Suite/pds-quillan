"""Tests for direct immutable Academic Result Manifest CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)

from quillan.cli import main
import quillan.cli_app.handlers.manifest as handlers
from quillan.review_record import build_empty_review_record, validate_review_record
from quillan.submission_manifest import validate_submission_manifest
from quillan.work_paths import quillan_work_ref, review_record_path, submission_manifest_path
from tests.review_test_support import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    TIMESTAMP,
    _write_assignment,
)

STANDARD_ID = "synthetic:W.A"
PROFILE_ID = "synthetic_profile"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_standards(workspace: Path) -> None:
    write_workspace_standards_library(
        workspace,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_ID,
                    code="W.A",
                    source="synthetic",
                    short_name="Synthetic Writing",
                    description="Synthetic writing standard for manifest CLI tests.",
                ),
            ),
            profiles=(
                StandardsProfile(profile_id=PROFILE_ID, standards=(STANDARD_ID,)),
            ),
        ),
    )


def _plain_submission() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": None,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {
            "submission_entry_method": "plain_paper_manual",
            "physical_evidence_status": "teacher_has_external_plain_paper",
            "created_by_workflow": "plain_paper_submission",
        },
    }


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_assignment(tmp_path)
    _write_standards(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)

    submission = _plain_submission()
    validate_submission_manifest(submission)
    _write_json(submission_manifest_path(tmp_path, work, STUDENT_ID), submission)

    review = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=TIMESTAMP,
    )
    validate_review_record(review)
    _write_json(review_record_path(tmp_path, work, STUDENT_ID), review)

    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _identity() -> list[str]:
    return ["--class-id", CLASS_ID, "--assignment-id", ASSIGNMENT_ID]


def test_manifest_help_surface(capsys: pytest.CaptureFixture[str]) -> None:
    for argv, expected in (
        (["--help"], "manifest"),
        (["manifest", "--help"], "generate"),
        (["manifest", "list", "--help"], "--class-id"),
        (["manifest", "show", "--help"], "--revision"),
        (["manifest", "validate", "--help"], "--revision"),
        (["manifest", "generate", "--help"], "--assignment-id"),
    ):
        with pytest.raises(SystemExit) as error:
            main(argv)
        assert error.value.code == 0
        captured = capsys.readouterr()
        assert expected in captured.out + captured.err


def test_list_generate_replay_show_and_validate(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["manifest", "list", *_identity()]) == 0
    assert "manifest revisions: none" in capsys.readouterr().out

    assert main(["manifest", "generate", *_identity()]) == 0
    created = capsys.readouterr().out
    assert "disposition: create_initial" in created
    assert "reason: initial_publication" in created
    assert "revision: 1" in created
    assert "represented student count: 1" in created
    assert STUDENT_ID not in created

    assert main(["manifest", "generate", *_identity()]) == 0
    replay = capsys.readouterr().out
    assert "disposition: reuse_existing" in replay
    assert "reason: exact_replay" in replay
    assert "revision: 1" in replay

    assert main(["manifest", "list", *_identity()]) == 0
    listed = capsys.readouterr().out
    assert "manifest revisions: 1" in listed
    assert "manifest sha256:" in listed
    assert STUDENT_ID not in listed

    assert main(["manifest", "show", *_identity(), "--revision", "1"]) == 0
    shown = capsys.readouterr().out
    assert "manifest contract: quillan_academic_result_manifest_v1" in shown
    assert "assignment source path: assignment.json" in shown
    assert "represented student count: 1" in shown
    assert STUDENT_ID not in shown

    assert main(["manifest", "validate", *_identity(), "--revision", "1"]) == 0
    validated = capsys.readouterr().out
    assert "valid: yes" in validated
    assert STUDENT_ID not in validated


def test_manifest_cli_rejects_invalid_duplicate_and_unknown_options(
    workspace: Path,
) -> None:
    with pytest.raises(SystemExit) as invalid_revision:
        main(["manifest", "show", *_identity(), "--revision", "0"])
    assert invalid_revision.value.code == 2

    with pytest.raises(SystemExit) as duplicate:
        main(
            [
                "manifest",
                "list",
                *_identity(),
                "--class-id",
                CLASS_ID,
            ]
        )
    assert duplicate.value.code == 2

    with pytest.raises(SystemExit) as unknown:
        main(["manifest", "generate", *_identity(), "--force"])
    assert unknown.value.code == 2


def test_missing_assignment_fails_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    result = main(["manifest", "generate", *_identity()])
    assert result == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    assert "Error: manifest generation failed" in captured.err
    assert not (tmp_path / "registry").exists()

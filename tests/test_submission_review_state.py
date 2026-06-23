"""Tests for teacher-controlled submission review-state updates."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

import quillan.submission_review_state
from quillan.cli import main
import quillan.cli_app.handlers.submissions as cli_submissions
from quillan.submission_manifest import (
    ALLOWED_SUBMISSION_STATES,
    SubmissionManifestError,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
    write_submission_manifest,
)
from quillan.submission_review_state import (
    SubmissionReviewStateError,
    UpdatedSubmissionReviewState,
    update_submission_review_state,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
ORIGINAL_TIMESTAMP = "2026-06-20T12:00:00+00:00"
UPDATED_TIMESTAMP = "2026-06-22T15:30:00+00:00"


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": 1,
        "submission_state": "unreviewed",
        "pages": [
            {
                "page_number": 1,
                "page_state": "present",
                "selected_evidence_id": "evidence_001",
                "evidence": [
                    {
                        "evidence_id": "evidence_001",
                        "routed_evidence_path": (
                            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/"
                            "scans/response_00107_pg_001.pdf"
                        ),
                        "evidence_role": "selected",
                        "evidence_state": "active",
                        "duplicate_number": None,
                        "created_at": ORIGINAL_TIMESTAMP,
                        "retained_source": {
                            "source_scan_id": "scan_001",
                            "source_filename": "source.pdf",
                            "source_sha256": "a" * 64,
                            "retained_source_path": (
                                "routing/source_scans/scan_001/source.pdf"
                            ),
                            "source_page_number": 1,
                        },
                        "module_details": {"source": "synthetic"},
                    }
                ],
            }
        ],
        "created_at": ORIGINAL_TIMESTAMP,
        "updated_at": ORIGINAL_TIMESTAMP,
        "module_details": {"teacher_workflow": "paper"},
    }


def _write_manifest(
    workspace: Path,
    manifest: dict[str, Any] | None = None,
) -> Path:
    path = submission_manifest_path(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    return write_submission_manifest(
        path,
        _manifest() if manifest is None else manifest,
    )


def test_success_updates_state_and_timestamp_only(tmp_path: Path) -> None:
    original = _manifest()
    manifest_path = _write_manifest(tmp_path, original)

    result = update_submission_review_state(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "in_progress",
        updated_at=UPDATED_TIMESTAMP,
    )

    expected_relative_path = (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
        f"{STUDENT_ID}/submission.json"
    )
    assert result == UpdatedSubmissionReviewState(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        manifest_path=manifest_path,
        manifest_relative_path=expected_relative_path,
        previous_state="unreviewed",
        new_state="in_progress",
        updated_at=UPDATED_TIMESTAMP,
    )

    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = copy.deepcopy(original)
    expected["submission_state"] = "in_progress"
    expected["updated_at"] = UPDATED_TIMESTAMP
    assert written == expected
    assert written["pages"] == original["pages"]
    assert written["created_at"] == original["created_at"]
    assert written["module_details"] == original["module_details"]


@pytest.mark.parametrize("state", sorted(ALLOWED_SUBMISSION_STATES))
def test_all_allowed_states_are_accepted(tmp_path: Path, state: str) -> None:
    _write_manifest(tmp_path)

    result = update_submission_review_state(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        state,
        updated_at=UPDATED_TIMESTAMP,
    )

    assert result.new_state == state


def test_invalid_state_raises_without_rewriting(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path)
    original = path.read_bytes()

    with pytest.raises(SubmissionReviewStateError, match="Invalid"):
        update_submission_review_state(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "graded",
        )

    assert path.read_bytes() == original


def test_missing_manifest_raises(tmp_path: Path) -> None:
    with pytest.raises(SubmissionReviewStateError, match="does not exist"):
        update_submission_review_state(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "reviewed",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("class_id", "other_class"),
        ("assignment_id", "other_assignment"),
        ("student_id", "00108"),
    ],
)
def test_manifest_identity_mismatch_raises_without_rewriting(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    manifest = _manifest()
    manifest[field] = value
    path = _write_manifest(tmp_path, manifest)
    original = path.read_bytes()

    with pytest.raises(SubmissionReviewStateError, match=field):
        update_submission_review_state(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "reviewed",
        )

    assert path.read_bytes() == original


def test_invalid_existing_manifest_raises_without_rewriting(tmp_path: Path) -> None:
    path = submission_manifest_path(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    original = path.read_bytes()

    with pytest.raises(SubmissionReviewStateError, match="not valid JSON"):
        update_submission_review_state(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "reviewed",
        )

    assert path.read_bytes() == original


def test_timezone_aware_datetime_is_accepted(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    timestamp = datetime(2026, 6, 22, 11, 30, tzinfo=timezone.utc)

    result = update_submission_review_state(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "reviewed",
        updated_at=timestamp,
    )

    assert result.updated_at == timestamp.isoformat()


def test_naive_datetime_is_rejected_without_rewriting(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path)
    original = path.read_bytes()

    with pytest.raises(SubmissionReviewStateError, match="timezone-aware"):
        update_submission_review_state(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "reviewed",
            updated_at=datetime(2026, 6, 22, 11, 30),
        )

    assert path.read_bytes() == original


def test_invalid_timestamp_string_is_rejected(tmp_path: Path) -> None:
    _write_manifest(tmp_path)

    with pytest.raises(SubmissionReviewStateError, match="Invalid updated_at"):
        update_submission_review_state(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "reviewed",
            updated_at="2026-06-22T11:30:00",
        )


def test_generated_timestamp_is_utc_and_manifest_valid(tmp_path: Path) -> None:
    _write_manifest(tmp_path)

    result = update_submission_review_state(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "reviewed",
    )

    parsed = datetime.fromisoformat(result.updated_at)
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def test_write_failure_is_wrapped_and_original_remains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_manifest(tmp_path)
    original = path.read_bytes()

    def fail_write(*_args: object, **_kwargs: object) -> Path:
        raise SubmissionManifestPathError("synthetic write failure")

    monkeypatch.setattr(
        quillan.submission_review_state,
        "write_submission_manifest",
        fail_write,
    )

    with pytest.raises(SubmissionReviewStateError, match="synthetic write failure"):
        update_submission_review_state(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "reviewed",
        )

    assert path.read_bytes() == original


def test_update_validation_failure_is_wrapped_and_original_remains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_manifest(tmp_path)
    original = path.read_bytes()

    def fail_validation(_manifest: dict[str, Any]) -> None:
        raise SubmissionManifestError("synthetic validation failure")

    monkeypatch.setattr(
        quillan.submission_review_state,
        "validate_submission_manifest",
        fail_validation,
    )

    with pytest.raises(
        SubmissionReviewStateError,
        match="synthetic validation failure",
    ):
        update_submission_review_state(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "reviewed",
        )

    assert path.read_bytes() == original


def test_cli_success_prints_teacher_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    relative_path = (
        "classes/class/assignments/assignment/submissions/00107/submission.json"
    )
    updated = UpdatedSubmissionReviewState(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        manifest_path=tmp_path / "submission.json",
        manifest_relative_path=relative_path,
        previous_state="unreviewed",
        new_state="in_progress",
        updated_at=UPDATED_TIMESTAMP,
    )
    monkeypatch.setattr(
        cli_submissions, "resolve_workspace_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        cli_submissions,
        "update_submission_review_state",
        lambda *_args: updated,
    )

    assert (
        main(
            [
                "set-review-state",
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                "in_progress",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == (
        "Updated submission review state:\n"
        f"Class: {CLASS_ID}\n"
        f"Assignment: {ASSIGNMENT_ID}\n"
        f"Student: {STUDENT_ID}\n"
        "Previous state: unreviewed\n"
        "New state: in_progress\n"
        f"Manifest: {relative_path}\n"
    )


def test_cli_failure_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_submissions, "resolve_workspace_root", lambda: tmp_path
    )

    def fail(*_args: object) -> UpdatedSubmissionReviewState:
        raise SubmissionReviewStateError("manifest is unavailable")

    monkeypatch.setattr(
        cli_submissions, "update_submission_review_state", fail
    )

    assert (
        main(
            [
                "set-review-state",
                CLASS_ID,
                ASSIGNMENT_ID,
                STUDENT_ID,
                "reviewed",
            ]
        )
        == 1
    )
    assert capsys.readouterr().out == (
        "Error: could not update submission review state: "
        "manifest is unavailable\n"
    )

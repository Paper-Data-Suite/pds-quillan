"""Tests for opening selected student submission evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import quillan.cli
import quillan.submission_review_opening
from quillan.cli import main
from quillan.evidence_opening import EvidenceOpeningError, OpenedEvidence
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)
from quillan.submission_review_opening import (
    OpenedSubmissionReview,
    SubmissionReviewOpeningError,
    open_student_submission_for_review,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
EVIDENCE_PATH = (
    f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/scans/"
    "response_00107_pg_001.pdf"
)


def _evidence(
    evidence_id: str = "evidence_001",
    *,
    path: str = EVIDENCE_PATH,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "routed_evidence_path": path,
        "evidence_role": "selected",
        "evidence_state": "active",
        "duplicate_number": None,
        "created_at": "2026-06-22T12:00:00+00:00",
        "retained_source": None,
        "module_details": {},
    }


def _page(
    page_number: int = 1,
    evidence_id: str = "evidence_001",
) -> dict[str, Any]:
    return {
        "page_number": page_number,
        "page_state": "present",
        "selected_evidence_id": evidence_id,
        "evidence": [_evidence(evidence_id)],
    }


def _manifest(*, pages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": 1,
        "submission_state": "unreviewed",
        "pages": [_page()] if pages is None else pages,
        "created_at": "2026-06-22T12:00:00+00:00",
        "updated_at": "2026-06-22T12:00:00+00:00",
        "module_details": {},
    }


def _write_manifest(workspace: Path, manifest: dict[str, Any]) -> Path:
    path = submission_manifest_path(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    return write_submission_manifest(path, manifest)


def test_success_opens_selected_evidence_and_returns_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path, _manifest())
    evidence_path = tmp_path / EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(b"synthetic evidence")
    calls: list[tuple[Path, str | Path]] = []

    def open_evidence(
        workspace_root: str | Path,
        relative_path: str | Path,
    ) -> OpenedEvidence:
        calls.append((Path(workspace_root), relative_path))
        return OpenedEvidence(evidence_path, EVIDENCE_PATH)

    monkeypatch.setattr(
        quillan.submission_review_opening,
        "open_workspace_evidence",
        open_evidence,
    )

    result = open_student_submission_for_review(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )

    assert calls == [(tmp_path.resolve(), EVIDENCE_PATH)]
    assert result == OpenedSubmissionReview(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        manifest_path=manifest_path,
        manifest_relative_path=(
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/submission.json"
        ),
        page_number=1,
        evidence_id="evidence_001",
        evidence_path=evidence_path,
        evidence_relative_path=EVIDENCE_PATH,
        submission_state="unreviewed",
        page_state="present",
    )


def test_missing_manifest_raises(tmp_path: Path) -> None:
    with pytest.raises(SubmissionReviewOpeningError, match="does not exist"):
        open_student_submission_for_review(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("class_id", "other_class"),
        ("assignment_id", "other_assignment"),
        ("student_id", "00108"),
    ],
)
def test_manifest_identity_mismatch_raises(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    manifest = _manifest()
    manifest[field] = value
    _write_manifest(tmp_path, manifest)

    with pytest.raises(SubmissionReviewOpeningError, match=field):
        open_student_submission_for_review(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        )


def test_no_selected_evidence_raises(tmp_path: Path) -> None:
    page = _page()
    page["selected_evidence_id"] = None
    page["evidence"][0]["evidence_role"] = "candidate"
    _write_manifest(tmp_path, _manifest(pages=[page]))

    with pytest.raises(SubmissionReviewOpeningError, match="no selected evidence"):
        open_student_submission_for_review(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        )


def test_multiple_selected_evidence_files_raise(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        _manifest(pages=[_page(), _page(2, "evidence_002")]),
    )

    with pytest.raises(SubmissionReviewOpeningError, match="multiple selected"):
        open_student_submission_for_review(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        )


def test_broken_selected_evidence_reference_is_wrapped(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["pages"][0]["selected_evidence_id"] = "missing_evidence"
    path = submission_manifest_path(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(
        SubmissionReviewOpeningError,
        match="selected_evidence_id does not refer",
    ):
        open_student_submission_for_review(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        )


@pytest.mark.parametrize(
    "message",
    [
        "Evidence file does not exist: missing.pdf",
        "Could not open evidence file: viewer failed",
    ],
)
def test_evidence_opening_failure_is_wrapped(
    tmp_path: Path,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_manifest(tmp_path, _manifest())

    def fail_to_open(
        _workspace_root: str | Path,
        _evidence_path: str | Path,
    ) -> OpenedEvidence:
        raise EvidenceOpeningError(message)

    monkeypatch.setattr(
        quillan.submission_review_opening,
        "open_workspace_evidence",
        fail_to_open,
    )

    with pytest.raises(SubmissionReviewOpeningError, match=message):
        open_student_submission_for_review(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        )


def test_opening_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path, _manifest())
    original_manifest = manifest_path.read_bytes()
    files_before = sorted(
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")
        if path.is_file()
    )

    monkeypatch.setattr(
        quillan.submission_review_opening,
        "open_workspace_evidence",
        lambda _root, _path: OpenedEvidence(
            tmp_path / EVIDENCE_PATH,
            EVIDENCE_PATH,
        ),
    )

    open_student_submission_for_review(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )

    assert manifest_path.read_bytes() == original_manifest
    assert files_before == sorted(
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")
        if path.is_file()
    )


def test_cli_success_prints_teacher_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opened = OpenedSubmissionReview(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        manifest_path=tmp_path / "submission.json",
        manifest_relative_path="classes/class/submissions/00107/submission.json",
        page_number=1,
        evidence_id="evidence_001",
        evidence_path=tmp_path / "evidence.pdf",
        evidence_relative_path="classes/class/scans/evidence.pdf",
        submission_state="unreviewed",
        page_state="present",
    )
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        quillan.cli,
        "open_student_submission_for_review",
        lambda *_args: opened,
    )

    assert (
        main(["open-submission", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0
    )
    output = capsys.readouterr().out
    for expected in (
        f"Class: {CLASS_ID}",
        f"Assignment: {ASSIGNMENT_ID}",
        f"Student: {STUDENT_ID}",
        "Submission state: unreviewed",
        "Page: 1",
        "Page state: present",
        "Evidence: evidence_001",
        "Path: classes/class/scans/evidence.pdf",
        "Manifest: classes/class/submissions/00107/submission.json",
    ):
        assert expected in output
    assert str(tmp_path) not in output


def test_cli_failure_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    def fail(*_args: object) -> OpenedSubmissionReview:
        raise SubmissionReviewOpeningError("manifest is unavailable")

    monkeypatch.setattr(quillan.cli, "open_student_submission_for_review", fail)

    assert (
        main(["open-submission", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 1
    )
    assert capsys.readouterr().out == (
        "Error: could not open student submission: manifest is unavailable\n"
    )


def test_cli_missing_manifest_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    assert (
        main(["open-submission", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 1
    )
    assert "Submission manifest does not exist" in capsys.readouterr().out

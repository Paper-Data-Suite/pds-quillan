"""Tests for the teacher-facing Review Student Work menu skeleton."""

from __future__ import annotations

from collections.abc import Iterator
import csv
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.cli import main
import quillan.review_menu as review_menu
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)
from quillan.submission_review_opening import OpenedSubmissionReview

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "stu_0001"
SECOND_STUDENT_ID = "stu_0002"
TIMESTAMP = "2026-06-22T12:00:00+00:00"
EVIDENCE_RELATIVE_PATH = (
    f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/scans/"
    "response_stu_0001_pg_001.pdf"
)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _menu_input(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str],
) -> None:
    response_iterator: Iterator[str] = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(response_iterator)
        except StopIteration as error:
            raise AssertionError(
                "Menu requested more input than the test provided."
            ) from error

    monkeypatch.setattr("builtins.input", fake_input)


def _write_workspace(root: Path) -> None:
    class_dir = root / "classes" / CLASS_ID
    assignment_dir = class_dir / "assignments" / ASSIGNMENT_ID
    assignment_dir.mkdir(parents=True)

    with (class_dir / "roster.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as roster_file:
        writer = csv.DictWriter(
            roster_file,
            fieldnames=(
                "class_id",
                "student_id",
                "last_name",
                "first_name",
                "period",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": STUDENT_ID,
                "last_name": "Rivera",
                "first_name": "Avery",
                "period": "3",
            }
        )
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": SECOND_STUDENT_ID,
                "last_name": "Patel",
                "first_name": "Mina",
                "period": "3",
            }
        )

    assignment = {
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "standards_profile_id": "synthetic_profile",
        "tagging_mode": "focus",
        "focus_standards": ["njsls-ela:W.1"],
        "basic_requirements": {"paragraphs_min": 1},
        "rubric_id": "synthetic_rubric",
    }
    (assignment_dir / "assignment.json").write_text(
        json.dumps(assignment),
        encoding="utf-8",
    )
    evidence_path = root / EVIDENCE_RELATIVE_PATH
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_bytes(b"synthetic evidence")
    _write_manifest(root)


def _write_manifest(root: Path) -> Path:
    manifest = {
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
                        "routed_evidence_path": EVIDENCE_RELATIVE_PATH,
                        "evidence_role": "selected",
                        "evidence_state": "active",
                        "duplicate_number": None,
                        "created_at": TIMESTAMP,
                        "retained_source": None,
                        "module_details": {},
                    }
                ],
            }
        ],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }
    path = submission_manifest_path(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    return write_submission_manifest(path, manifest)


def _review_record() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_review",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "submission_manifest_path": (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/submission.json"
        ),
        "review_state": "in_progress",
        "notes": [
            {
                "note_id": "note_0001",
                "text": "Teacher observation.",
                "created_at": TIMESTAMP,
                "updated_at": TIMESTAMP,
                "module_details": {},
            }
        ],
        "tags": [],
        "scores": [],
        "comments": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def test_main_menu_shows_and_opens_review_student_work(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["2", "4", "6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "2. Review Student Work" in output
    assert "Review Student Work" in output
    assert "1. Assignment Review Actions" in output
    assert "2. Scan Intake / Route Paper Responses" in output
    assert "3. Manage Review Materials" in output
    assert "Goodbye." in output


def test_review_workflow_selects_context_and_shows_read_only_summary(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = submission_manifest_path(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    manifest_before = manifest_path.read_bytes()
    files_before = sorted(
        path.relative_to(workspace)
        for path in workspace.rglob("*")
        if path.is_file()
    )
    _menu_input(monkeypatch, ["2", "1", "1", "1", "1", "1", "12", "6", "", "4", "6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert f"1. {CLASS_ID}" in output
    assert f"1. {ASSIGNMENT_ID} - Synthetic Essay" in output
    assert f"Submission status for assignment {ASSIGNMENT_ID}" in output
    assert f"1. {STUDENT_ID}: unreviewed; manifest exists; evidence files=1" in output
    assert f"2. {SECOND_STUDENT_ID}: no manifest; no routed evidence" in output
    assert "Selected Student Review" in output
    assert "Current review summary" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert f"Student: {STUDENT_ID}" in output
    assert "Submission: assembled" in output
    assert "Evidence files: 1" in output
    assert "Review record: not started" in output
    assert manifest_path.read_bytes() == manifest_before
    assert files_before == sorted(
        path.relative_to(workspace)
        for path in workspace.rglob("*")
        if path.is_file()
    )


def test_review_summary_includes_existing_review_record_counts(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "review.json"
    )
    review_path.write_text(json.dumps(_review_record()), encoding="utf-8")
    review_before = review_path.read_bytes()
    _menu_input(
        monkeypatch,
        ["2", "1", "1", "1", "1", "1", "12", "6", "", "4", "6"],
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Review record: exists" in output
    assert "Review record state: in_progress" in output
    assert "Notes: 1" in output
    assert "Tags: 0" in output
    assert review_path.read_bytes() == review_before


def test_review_menu_views_current_review_details_read_only(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_record()
    review["tags"] = [
        {
            "tag_id": "tag_0001",
            "label": "Clear evidence",
            "polarity": "positive",
            "location": {"type": "paragraph", "value": 2},
            "created_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    review["comments"] = [
        {
            "comment_record_id": "comment_record_0001",
            "label": "Explain evidence",
            "text": "Explain how this evidence supports the claim.",
            "source": "custom",
            "include_in_feedback": True,
            "location": {"type": "paragraph", "value": [3, 4]},
            "created_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    review_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "review.json"
    )
    review_path.write_text(json.dumps(review), encoding="utf-8")
    review_before = review_path.read_bytes()

    _menu_input(
        monkeypatch,
        ["2", "1", "1", "1", "1", "1", "2", "", "12", "6", "", "4", "6"],
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Current Review Details" in output
    assert "[positive] Clear evidence" in output
    assert "Target: Paragraph 2" in output
    assert "Explain evidence" in output
    assert "Target: Paragraphs 3-4" in output
    assert review_path.read_bytes() == review_before


def test_review_menu_open_submission_uses_existing_safe_opening(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, str, str, str]] = []

    def open_submission(
        workspace_root: str | Path,
        class_id: str,
        assignment_id: str,
        student_id: str,
    ) -> OpenedSubmissionReview:
        calls.append((Path(workspace_root), class_id, assignment_id, student_id))
        return OpenedSubmissionReview(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            manifest_path=workspace / "submission.json",
            manifest_relative_path="classes/class/submissions/submission.json",
            page_number=1,
            evidence_id="evidence_001",
            evidence_path=workspace / "evidence.pdf",
            evidence_relative_path="classes/class/scans/evidence.pdf",
            submission_state="unreviewed",
            page_state="present",
        )

    monkeypatch.setattr(
        review_menu,
        "open_student_submission_for_review",
        open_submission,
    )
    _menu_input(
        monkeypatch,
        ["2", "1", "1", "1", "1", "1", "1", "", "12", "6", "", "4", "6"],
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert calls == [(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)]
    assert "Opened submission evidence for review:" in output
    assert "Path: classes/class/scans/evidence.pdf" in output


def test_review_menu_reports_missing_openable_evidence(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        ["2", "1", "1", "1", "1", "2", "1", "", "6", "", "4", "6"],
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert f"Student: {SECOND_STUDENT_ID}" in output
    assert "Submission: not assembled" in output
    assert "No routed evidence has been found for this student yet." in output
    assert "1. Assemble this assignment now" not in output
    assert not list(workspace.rglob("review.json"))



def test_review_menu_adds_teacher_note_to_review_record(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        [
            "2",
            "1",
            "1",
            "1",
            "1",
            "1",
            "5",
            "This is a test note.",
            "",
            "12",
            "6",
            "",
            "4",
            "6",
        ],
    )

    assert main(["menu"]) == 0

    review_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "review.json"
    )
    assert review_path.exists()
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["notes"][0]["text"] == "This is a test note."
    assert review["review_state"] == "in_progress"


def test_review_menu_updates_submission_review_state(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        [
            "2",
            "1",
            "1",
            "1",
            "1",
            "1",
            "9",
            "in_progress",
            "1",
            "",
            "12",
            "6",
            "",
            "4",
            "6",
        ],
    )

    assert main(["menu"]) == 0

    manifest_path = submission_manifest_path(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["submission_state"] == "in_progress"


def test_review_menu_excludes_submission_page_without_touching_review_record(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "review.json"
    )
    review_path.write_text(json.dumps(_review_record()), encoding="utf-8")
    review_before = review_path.read_bytes()
    evidence_path = workspace / EVIDENCE_RELATIVE_PATH
    evidence_before = evidence_path.read_bytes()
    _menu_input(
        monkeypatch,
        [
            "2",
            "1",
            "1",
            "1",
            "1",
            "1",
            "4",
            "1",
            "1",
            "1",
            "",
            "12",
            "6",
            "",
            "4",
            "6",
        ],
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Manage Submission Pages" in output
    assert "Excluding a page does not delete the file." in output
    assert "Page change saved." in output
    manifest_path = submission_manifest_path(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    page = manifest["pages"][0]
    assert page["page_state"] == "excluded"
    assert page["selected_evidence_id"] is None
    assert page["evidence"][0]["evidence_role"] == "excluded"
    assert page["evidence"][0]["evidence_state"] == "excluded"
    assert evidence_path.read_bytes() == evidence_before
    assert review_path.read_bytes() == review_before


def test_review_menu_no_classes_and_invalid_selection_back_out_safely(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    _menu_input(monkeypatch, ["2", "9", "", "1", "", "4", "6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Invalid selection. Please enter a number from 1 to 4." in output
    assert "No classes found in the current workspace." in output
    assert "Goodbye." in output

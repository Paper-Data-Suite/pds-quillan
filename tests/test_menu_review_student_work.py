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
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)
from quillan.submission_review_opening import (
    OpenedSubmissionEvidencePage,
    OpenedSubmissionReview,
)

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
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Write a synthetic argument.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["njsls-ela:W.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_2_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                }
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
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


def _write_two_page_manifest(root: Path) -> Path:
    path = submission_manifest_path(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    second_evidence_path = (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/scans/"
        "response_stu_0001_pg_002.pdf"
    )
    (root / second_evidence_path).write_bytes(b"synthetic evidence page 2")
    manifest["expected_pages"] = 2
    manifest["pages"].append(
        {
            "page_number": 2,
            "page_state": "present",
            "selected_evidence_id": "evidence_002",
            "evidence": [
                {
                    "evidence_id": "evidence_002",
                    "routed_evidence_path": second_evidence_path,
                    "evidence_role": "selected",
                    "evidence_state": "active",
                    "duplicate_number": None,
                    "created_at": TIMESTAMP,
                    "retained_source": None,
                    "module_details": {},
                }
            ],
        }
    )
    return write_submission_manifest(path, manifest, overwrite=True)


def _review_record() -> dict[str, Any]:
    record = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=TIMESTAMP,
    )
    record["review_state"] = "feedback_composed"
    record["private_notes"] = [
        {
            "private_note_id": "note_0001",
            "text": "Teacher observation.",
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    return record


def test_main_menu_shows_and_opens_review_student_work(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["2", "3", "6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "2. Review Student Work" in output
    assert "Review Student Work" in output
    assert "1. Assignment Review Actions" in output
    assert "2. Scan Intake / Route Paper Responses" in output
    assert "3. Back" in output
    assert "Manage Review Materials" not in output
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
    _menu_input(monkeypatch, ["2", "1", "1", "1", "1", "1", "12", "6", "", "3", "6"])

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
        ["2", "1", "1", "1", "1", "1", "12", "6", "", "3", "6"],
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Review record: exists" in output
    assert "Review record state: feedback_composed" in output
    assert "Private notes: 1" in output
    assert "Review-unit observations: 0" in output
    assert review_path.read_bytes() == review_before


def test_review_menu_defines_review_units(
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
            "4",
            "1",
            "2",
            "1",
            "",
            "4",
            "12",
            "6",
            "",
            "3",
            "6",
        ],
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Review Units and Focus Standard Observations" in output
    assert "Updated review units:" in output
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert [unit["unit_id"] for unit in review["review_units"]] == [
        "paragraph_1",
        "paragraph_2",
    ]
    assert [unit["label"] for unit in review["review_units"]] == [
        "Paragraph 1",
        "Paragraph 2",
    ]
    assert review["review_state"] == "observations_in_progress"


def test_review_menu_records_applicable_focus_standard_observation(
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
            "4",
            "1",
            "1",
            "1",
            "",
            "2",
            "1",
            "1",
            "1",
            "",
            "",
            "Clear evidence.",
            "1",
            "",
            "4",
            "12",
            "6",
            "",
            "3",
            "6",
        ],
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Updated Focus Standard observation:" in output
    assert "Action: created" in output
    assert "Rating:" not in output
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    observation = review["review_units"][0]["standard_observations"][0]
    assert observation["standard_id"] == "njsls-ela:W.1"
    assert observation["applicable"] is True
    assert observation["evidence_present"] is True
    assert observation["rating"] is None
    assert observation["rationale"] == "Clear evidence."
    assert observation["include_in_feedback"] is True
    assert review["overall_standard_ratings"] == []
    assert review["feedback"]["standard_feedback"] == []


def test_review_menu_marks_observations_complete(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_record()
    review["review_state"] = "observations_in_progress"
    review["review_units"] = [
        {
            "unit_id": "paragraph_1",
            "sequence": 1,
            "label": "Paragraph 1",
            "unit_type": "paragraph",
            "standard_observations": [],
            "module_details": {},
        }
    ]
    review_path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    review_path.write_text(json.dumps(review), encoding="utf-8")

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
            "3",
            "1",
            "",
            "4",
            "12",
            "6",
            "",
            "3",
            "6",
        ],
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Marked review-unit observations complete:" in output
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["review_state"] == "observations_complete"
    assert review["overall_standard_ratings"] == []


def test_review_menu_records_and_completes_overall_focus_standard_rating(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_record()
    review["review_state"] = "observations_complete"
    review["review_units"] = [
        {
            "unit_id": "paragraph_1",
            "sequence": 1,
            "label": "Paragraph 1",
            "unit_type": "paragraph",
            "standard_observations": [
                {
                    "observation_id": "observation_0001",
                    "standard_id": "njsls-ela:W.1",
                    "applicable": True,
                    "evidence_present": True,
                    "rating": None,
                    "rationale": "Clear evidence",
                    "include_in_feedback": True,
                    "updated_at": TIMESTAMP,
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    ]
    review_path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    review_path.write_text(json.dumps(review), encoding="utf-8")

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
            "2",
            "1",
            "1",
            "Good work.",
            "",
            "1",
            "",
            "3",
            "1",
            "",
            "4",
            "12",
            "6",
            "",
            "3",
            "6",
        ],
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Overall Focus Standard Ratings" in output
    assert "Rating scale: standards_2_level" in output
    assert "Updated overall Focus Standard rating:" in output
    assert "Marked overall Focus Standard ratings complete:" in output
    assert "recommended" not in output.lower()
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["review_state"] == "ratings_complete"
    assert review["overall_standard_ratings"] == [
        {
            "standard_id": "njsls-ela:W.1",
            "rating": 1,
            "rationale": "Good work.",
            "include_in_feedback": True,
            "updated_at": review["overall_standard_ratings"][0]["updated_at"],
            "module_details": {},
        }
    ]
    assert review["feedback"]["standard_feedback"] == _review_record()["feedback"][
        "standard_feedback"
    ]
    for legacy_field in ("scores", "tags", "comments", "notes"):
        assert legacy_field not in review


def test_review_menu_blocks_observations_for_returned_without_full_review(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=TIMESTAMP,
    )
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Missing required work.",
        "updated_at": TIMESTAMP,
    }
    review_path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    review_path.write_text(json.dumps(review), encoding="utf-8")
    before = review_path.read_bytes()

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
            "4",
            "12",
            "6",
            "",
            "3",
            "6",
        ],
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "returned without full standards review" in output
    assert review_path.read_bytes() == before


def test_review_menu_views_current_review_details_read_only(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_record()
    review["review_units"] = [
        {
            "unit_id": "unit_0001",
            "sequence": 1,
            "label": "Paragraph 2",
            "unit_type": "paragraph",
            "standard_observations": [
                {
                    "observation_id": "observation_0001",
                    "standard_id": "njsls-ela:W.1",
                    "applicable": True,
                    "evidence_present": True,
                    "rating": 1,
                    "rationale": "Clear evidence",
                    "include_in_feedback": True,
                    "updated_at": TIMESTAMP,
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    ]
    review["feedback"]["standard_feedback"] = [
        {
            "standard_id": "njsls-ela:W.1",
            "include_overall_rating": False,
            "include_overall_rationale": False,
            "included_observation_ids": ["observation_0001"],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "custom",
                    "text": "Explain how this evidence supports the claim.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": TIMESTAMP,
                    "module_details": {},
                }
            ],
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
        ["2", "1", "1", "1", "1", "1", "2", "", "12", "6", "", "3", "6"],
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Current Review Details" in output
    assert "Paragraph 2 (paragraph)" in output
    assert (
        "njsls-ela:W.1: applicable; evidence present: yes; "
        "include in feedback: yes"
    ) in output
    assert "Rating: 1" in output
    assert "Explain how this evidence supports the claim." in output
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
        *,
        page_number: int | None = None,
    ) -> OpenedSubmissionReview:
        calls.append((Path(workspace_root), class_id, assignment_id, student_id))
        assert page_number == 1
        return OpenedSubmissionReview(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            manifest_path=workspace / "submission.json",
            manifest_relative_path="classes/class/submissions/submission.json",
            submission_state="unreviewed",
            opened_pages=(
                OpenedSubmissionEvidencePage(
                    page_number=1,
                    evidence_id="evidence_001",
                    evidence_path=workspace / "evidence.pdf",
                    evidence_relative_path="classes/class/scans/evidence.pdf",
                    page_state="present",
                ),
            ),
        )

    monkeypatch.setattr(
        review_menu,
        "open_student_submission_for_review",
        open_submission,
    )
    _menu_input(
        monkeypatch,
        ["2", "1", "1", "1", "1", "1", "1", "", "12", "6", "", "3", "6"],
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert calls == [(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)]
    assert "Opened submission evidence for review:" in output
    assert (
        "- Page 1: present; Evidence: evidence_001; "
        "Path: classes/class/scans/evidence.pdf"
    ) in output


def test_review_menu_multi_page_open_submission_selects_one_page(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_two_page_manifest(workspace)
    calls: list[int | None] = []

    def open_submission(
        _workspace_root: str | Path,
        class_id: str,
        assignment_id: str,
        student_id: str,
        *,
        page_number: int | None = None,
    ) -> OpenedSubmissionReview:
        calls.append(page_number)
        return OpenedSubmissionReview(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            manifest_path=workspace / "submission.json",
            manifest_relative_path="classes/class/submissions/submission.json",
            submission_state="unreviewed",
            opened_pages=(
                OpenedSubmissionEvidencePage(
                    page_number=2,
                    evidence_id="evidence_002",
                    evidence_path=workspace / "evidence_2.pdf",
                    evidence_relative_path="classes/class/scans/evidence_2.pdf",
                    page_state="present",
                ),
            ),
        )

    monkeypatch.setattr(
        review_menu,
        "open_student_submission_for_review",
        open_submission,
    )
    _menu_input(
        monkeypatch,
        ["2", "1", "1", "1", "1", "1", "1", "2", "", "12", "6", "", "3", "6"],
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert calls == [2]
    assert "Open Submission Evidence" in output
    assert "1. Page 1 - present - evidence_001" in output
    assert "2. Page 2 - present - evidence_002" in output
    assert "A. Open all selected pages" in output


def test_review_menu_multi_page_open_submission_opens_all_pages(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_two_page_manifest(workspace)
    calls: list[int | None] = []

    def open_submission(
        _workspace_root: str | Path,
        class_id: str,
        assignment_id: str,
        student_id: str,
        *,
        page_number: int | None = None,
    ) -> OpenedSubmissionReview:
        calls.append(page_number)
        return OpenedSubmissionReview(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            manifest_path=workspace / "submission.json",
            manifest_relative_path="classes/class/submissions/submission.json",
            submission_state="unreviewed",
            opened_pages=(
                OpenedSubmissionEvidencePage(
                    page_number=1,
                    evidence_id="evidence_001",
                    evidence_path=workspace / "evidence.pdf",
                    evidence_relative_path="classes/class/scans/evidence.pdf",
                    page_state="present",
                ),
                OpenedSubmissionEvidencePage(
                    page_number=2,
                    evidence_id="evidence_002",
                    evidence_path=workspace / "evidence_2.pdf",
                    evidence_relative_path="classes/class/scans/evidence_2.pdf",
                    page_state="present",
                ),
            ),
        )

    monkeypatch.setattr(
        review_menu,
        "open_student_submission_for_review",
        open_submission,
    )
    _menu_input(
        monkeypatch,
        ["2", "1", "1", "1", "1", "1", "1", "A", "", "12", "6", "", "3", "6"],
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert calls == [None]
    assert "Pages opened: 2" in output


def test_review_menu_reports_missing_openable_evidence(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        ["2", "1", "1", "1", "1", "2", "1", "", "6", "", "3", "6"],
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
            "8",
            "This is a test note.",
            "",
            "12",
            "6",
            "",
            "3",
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
    assert review["private_notes"][0]["text"] == "This is a test note."
    assert review["review_state"] == "not_started"


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
            "3",
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


def test_review_menu_adds_custom_focus_standard_feedback_comment(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review_path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    review = _review_record()
    review["feedback"]["standard_feedback"] = []
    review_path.write_text(json.dumps(review), encoding="utf-8")

    _menu_input(
        monkeypatch,
        [
            "2",
            "1",
            "1",
            "1",
            "1",
            "1",
            "6",
            "2",
            "1",
            "Focused feedback text.",
            "",
            "n",
            "1",
            "",
            "5",
            "12",
            "6",
            "",
            "3",
            "6",
        ],
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Compose Focus Standard Feedback" in output
    assert "Added Focus Standard feedback comment:" in output
    review = json.loads(review_path.read_text(encoding="utf-8"))
    comment = review["feedback"]["standard_feedback"][0]["comments"][0]
    assert comment["source"] == "custom"
    assert comment["text"] == "Focused feedback text."
    assert comment["include_in_feedback"] is True
    assert not {"comments", "scores", "tags", "notes"} & review.keys()


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
            "7",
            "1",
            "1",
            "1",
            "",
            "12",
            "6",
            "",
            "3",
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
    _menu_input(monkeypatch, ["2", "9", "", "1", "", "3", "6"])

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Invalid selection. Please enter a number from 1 to 3." in output
    assert "No classes found in the current workspace." in output
    assert "Goodbye." in output

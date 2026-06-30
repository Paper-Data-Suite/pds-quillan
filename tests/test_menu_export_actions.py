"""Tests for guided export actions in the Review Student Work menu."""

from __future__ import annotations

from collections.abc import Iterator
import csv
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.cli import main
import quillan.review_menu as review_menu
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "stu_0001"
SECOND_STUDENT_ID = "stu_0002"
TIMESTAMP = "2026-06-22T12:00:00+00:00"


def _menu_input(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> None:
    response_iterator: Iterator[str] = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(response_iterator)
        except StopIteration as error:
            raise AssertionError(
                "Menu requested more input than the test provided."
            ) from error

    monkeypatch.setattr("builtins.input", fake_input)


def _enter_assignment_review_actions() -> list[str]:
    return ["2", "1", "1", "1"]


def _exit_assignment_review_actions_to_main() -> list[str]:
    return ["6", "", "4", "6"]


def _exit_after_assignment_action_to_main() -> list[str]:
    return ["", "6", "", "4", "6"]


def _enter_selected_student(student_choice: str = "1") -> list[str]:
    return _enter_assignment_review_actions() + ["1", student_choice]


def _exit_selected_student_to_main() -> list[str]:
    return ["12"] + _exit_assignment_review_actions_to_main()


def _exit_after_selected_student_action_to_main() -> list[str]:
    return ["", "12"] + _exit_assignment_review_actions_to_main()


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
        json.dumps(assignment), encoding="utf-8"
    )

    evidence_path = (
        root
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "scans"
        / "response_stu_0001_pg_001.pdf"
    )
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
                        "routed_evidence_path": (
                            f"classes/{CLASS_ID}/assignments/"
                            f"{ASSIGNMENT_ID}/scans/"
                            "response_stu_0001_pg_001.pdf"
                        ),
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
        "notes": [],
        "tags": [
            {
                "tag_id": "tag_0001",
                "label": "claim",
                "polarity": "positive",
                "standard_id": "njsls-ela:W.1",
                "created_at": TIMESTAMP,
                "module_details": {},
            }
        ],
        "scores": [
            {
                "score_id": "score_0001",
                "criterion_id": "evidence",
                "label": "Evidence",
                "score": 3,
                "max_score": 4,
                "scale": "4 point",
                "updated_at": TIMESTAMP,
                "module_details": {},
            }
        ],
        "comments": [
            {
                "comment_record_id": "comment_record_0001",
                "label": "Feedback",
                "text": "Good work.",
                "source": "custom",
                "include_in_feedback": True,
                "created_at": TIMESTAMP,
                "module_details": {},
            },
            {
                "comment_record_id": "comment_record_0002",
                "label": "Private note",
                "text": "This should not appear in student feedback.",
                "source": "custom",
                "include_in_feedback": False,
                "created_at": TIMESTAMP,
                "module_details": {},
            },
        ],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def _write_review_record(root: Path, review: dict[str, Any]) -> Path:
    path = review_record_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    return write_review_record(path, review)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def test_assignment_review_actions_menu_includes_export_choices(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions()
        + _exit_assignment_review_actions_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Assignment Review Actions" in output
    assert "2. Assemble routed submissions" in output
    assert "3. Export class review summary" in output
    assert "4. Export standards summary" in output


def test_selected_student_review_menu_includes_feedback_export(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        _enter_selected_student() + _exit_selected_student_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Selected Student Review" in output
    assert "10. Export student feedback" in output


def test_menu_export_student_feedback_creates_feedback_file(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    feedback_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "exports"
        / "feedback.md"
    )
    assert not feedback_path.exists()

    manifest_path = submission_manifest_path(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    manifest_before = manifest_path.read_bytes()
    review_path = review_record_path(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    review_before = review_path.read_bytes()

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["10", "1"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Exported student feedback:" in output
    assert "Overwrote existing: no" in output
    assert feedback_path.is_file()

    feedback_text = feedback_path.read_text(encoding="utf-8")
    assert "- Evidence: 3 / 4 (4 point)" in feedback_text
    assert "- Good work." in feedback_text
    assert "This should not appear in student feedback." not in feedback_text
    assert manifest_path.read_bytes() == manifest_before
    assert review_path.read_bytes() == review_before


def test_menu_export_class_summary_creates_summary_file(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    summary_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "exports"
        / "class_summary.csv"
    )
    assert not summary_path.exists()

    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions()
        + ["3", ""]
        + _exit_after_assignment_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Exported class review summary:" in output
    assert "Overwrote existing: no" in output
    assert summary_path.is_file()


def test_menu_export_standards_summary_creates_summary_file(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    summary_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "exports"
        / "standards_summary.csv"
    )
    assert not summary_path.exists()

    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions()
        + ["4", ""]
        + _exit_after_assignment_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Exported standards summary:" in output
    assert "Overwrote existing: no" in output
    assert summary_path.is_file()


def test_menu_export_feedback_invalid_overwrite_cancels_without_writing(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    feedback_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "exports"
        / "feedback.md"
    )
    assert not feedback_path.exists()

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["10", "2"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Export canceled." in output
    assert not feedback_path.exists()


def test_menu_export_feedback_reports_missing_review_record(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feedback_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "exports"
        / "feedback.md"
    )
    assert not feedback_path.exists()

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["10", "1"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Error: could not export student feedback:" in output
    assert "Review record does not exist" in output
    assert not feedback_path.exists()


def test_menu_export_feedback_requires_overwrite_when_existing(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    feedback_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "exports"
        / "feedback.md"
    )
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    feedback_path.write_text("old feedback", encoding="utf-8")

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["10", "1", "1"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "A feedback export already exists." in output
    assert "Export canceled." in output
    assert feedback_path.read_text(encoding="utf-8") == "old feedback"


def test_menu_export_feedback_overwrites_existing_export(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    feedback_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
        / "exports"
        / "feedback.md"
    )
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    feedback_path.write_text("old feedback", encoding="utf-8")

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["10", "1", "2"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Exported student feedback:" in output
    assert "Overwrote existing: yes" in output
    assert feedback_path.read_text(encoding="utf-8") != "old feedback"


def test_menu_export_class_summary_requires_overwrite_when_existing(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    exports_dir = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "exports"
    )
    exports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = exports_dir / "class_summary.csv"
    summary_path.write_text("old content", encoding="utf-8")

    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions()
        + ["3", ""]
        + _exit_after_assignment_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Error: could not export class review summary:" in output
    assert "Use --overwrite to replace it." in output
    assert summary_path.read_text(encoding="utf-8") == "old content"


def test_menu_export_class_summary_overwrites_existing_export(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    exports_dir = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "exports"
    )
    exports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = exports_dir / "class_summary.csv"
    summary_path.write_text("old content", encoding="utf-8")

    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions()
        + ["3", "y"]
        + _exit_after_assignment_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Exported class review summary:" in output
    assert "Overwrote existing: yes" in output
    assert summary_path.read_text(encoding="utf-8") != "old content"


def test_menu_export_class_summary_invalid_overwrite_cancels_without_writing(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "exports"
        / "class_summary.csv"
    )
    assert not summary_path.exists()

    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions()
        + ["3", "maybe"]
        + _exit_after_assignment_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Export canceled. Please enter y or n." in output
    assert not summary_path.exists()

def test_menu_export_standards_summary_overwrites_existing_export(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    exports_dir = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "exports"
    )
    exports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = exports_dir / "standards_summary.csv"
    summary_path.write_text("old summary", encoding="utf-8")

    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions()
        + ["4", "y"]
        + _exit_after_assignment_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Exported standards summary:" in output
    assert "Overwrote existing: yes" in output
    assert summary_path.read_text(encoding="utf-8") != "old summary"


def test_menu_export_standards_summary_requires_overwrite_when_existing(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_review_record(workspace, _review_record())
    exports_dir = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "exports"
    )
    exports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = exports_dir / "standards_summary.csv"
    summary_path.write_text("old summary", encoding="utf-8")

    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions()
        + ["4", ""]
        + _exit_after_assignment_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Error: could not export standards summary:" in output
    assert "Use --overwrite to replace it." in output
    assert summary_path.read_text(encoding="utf-8") == "old summary"


def test_menu_export_standards_summary_invalid_overwrite_cancels_without_writing(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "exports"
        / "standards_summary.csv"
    )
    assert not summary_path.exists()

    _menu_input(
        monkeypatch,
        _enter_assignment_review_actions()
        + ["4", "maybe"]
        + _exit_after_assignment_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Export canceled. Please enter y or n." in output
    assert not summary_path.exists()

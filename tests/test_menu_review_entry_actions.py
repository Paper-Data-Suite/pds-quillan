"""Tests for retained selected-student review menu entry actions."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.review_menu as review_menu
from quillan.review_record_paths import review_record_path
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
    response_iterator = iter(responses)

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

    with (class_dir / "roster.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=("class_id", "student_id", "last_name", "first_name", "period"),
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
                            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/scans/"
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
    path = submission_manifest_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    return write_submission_manifest(path, manifest)


def _enter_selected_student() -> list[str]:
    return ["2", "1", "1", "1", "1", "1"]


def _exit_selected_student_to_main() -> list[str]:
    return ["9", "6", "", "3", "6"]


def _exit_after_selected_student_action_to_main() -> list[str]:
    return ["", "9", "6", "", "3", "6"]


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def test_review_menu_selected_student_excludes_legacy_review_entry_actions(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, _enter_selected_student() + _exit_selected_student_to_main())

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Selected Student Review" in output
    assert "1. Open submission evidence" in output
    assert "2. View current review details" in output
    assert "3. Record minimum requirement checks" in output
    assert "4. Manage submission pages" in output
    assert "5. Add teacher note" in output
    assert "6. Update submission review state" in output
    assert "7. Export student feedback" in output
    assert "8. Refresh summary" in output
    assert "9. Back" in output
    assert "Add structured tag" not in output
    assert "Select reusable comment" not in output
    assert "Set criterion score" not in output
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


def test_review_menu_records_minimum_requirement_check(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    manifest_before = manifest_path.read_bytes()

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["3", "1", "1", "", "", "b"]
        + _exit_selected_student_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Requirement Checks" in output
    assert "Minimum paragraphs: not checked" in output
    assert "Recorded requirement check:" in output
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert review["requirement_checks"][0]["requirement_key"] == "paragraphs_min"
    assert review["requirement_checks"][0]["met"] is True
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_blank_note_cancels_without_review_record(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    manifest_before = manifest_path.read_bytes()

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["5", ""]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_updates_submission_review_state(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["6", "in_progress", "1"]
        + _exit_after_selected_student_action_to_main(),
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

"""Tests for retained selected-student review menu entry actions."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tests.menu_screen_recorder import MenuScreenRecorder, assert_focused_child_screen

from quillan.cli import main
from quillan.minimum_requirement_review import set_configured_requirement_check
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
    assignment_dir = class_dir / "modules" / "quillan" / "work" / ASSIGNMENT_ID
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
        "basic_requirements": {
            "paragraphs_min": 1,
            "paragraphs_max": 5,
            "word_count_min": 100,
        },
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
        "created_at": "2026-07-13T00:00:00+00:00",
        "updated_at": "2026-07-13T00:00:00+00:00",
        "module_details": {},
    }
    (assignment_dir / "assignment.json").write_text(
        json.dumps(assignment), encoding="utf-8"
    )
    evidence_path = (
        root
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
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
                            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/scans/"
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
    return ["b", "b", "", "b", "q"]


def _exit_after_selected_student_action_to_main() -> list[str]:
    return ["", "b", "b", "", "b", "q"]


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
    assert "3. Review minimum requirements" in output
    assert "4. Review units and Focus Standard observations" in output
    assert "5. Overall Focus Standard ratings" in output
    assert "6. Compose Focus Standard feedback" in output
    assert "7. Manage submission pages" in output
    assert "8. Add teacher note" in output
    assert "9. Update review workflow state" in output
    assert "10. Export student feedback" in output
    assert "11. Refresh summary" in output
    assert "B. Back" in output
    assert "M. Main Menu" in output
    assert "Q. Quit" in output
    assert "Add structured tag" not in output
    assert "Select reusable comment" not in output
    assert "Set criterion score" not in output
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


@pytest.mark.menu_density_workflow("minimum requirements")
def test_review_menu_records_minimum_requirement_check(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    manifest_before = manifest_path.read_bytes()

    recorder = MenuScreenRecorder(
        _enter_selected_student()
        + [
            "3",
            "1",
            "1",
            "1",
            "",
            "",
            "2",
            "2",
            "",
            "",
            "3",
            "1",
            "",
            "",
            "b",
            "4",
        ]
        + _exit_selected_student_to_main(),
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert_focused_child_screen(
        screens,
        heading="Record Requirement Check",
        required_text=(
            f"Student: Avery Rivera ({STUDENT_ID})",
            "Recorded requirement check:",
        ),
        forbidden_parent_text="3. Export returned-work feedback",
        parent_heading="Review Minimum Requirements",
        result_heading="Recorded requirement check:",
        unrelated_previous_text="Minimum paragraphs: not checked",
    )
    assert "Requirement Checks" in output
    assert "Record Requirement Check" in output
    assert "Review Minimum Requirements" in output
    selector_screens = [
        screen.output
        for screen in screens
        if "Record Requirement Check" in screen.output
        and "Requirement Checks" in screen.output
    ]
    assert len(selector_screens) == 4
    expected_statuses = (
        (
            "1. Minimum paragraphs: not checked",
            "2. Maximum paragraphs: not checked",
            "3. Minimum word count: not checked",
        ),
        (
            "1. Minimum paragraphs: met",
            "2. Maximum paragraphs: not checked",
            "3. Minimum word count: not checked",
        ),
        (
            "1. Minimum paragraphs: met",
            "2. Maximum paragraphs: not met",
            "3. Minimum word count: not checked",
        ),
        (
            "1. Minimum paragraphs: met",
            "2. Maximum paragraphs: not met",
            "3. Minimum word count: met",
        ),
    )
    for screen, expected in zip(selector_screens, expected_statuses, strict=True):
        positions = [screen.index(text) for text in expected]
        assert positions == sorted(positions)
    assert "Recorded requirement check:" in output
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert [
        (check["requirement_key"], check["met"])
        for check in review["minimum_requirement_checks"]
    ] == [
        ("paragraphs_min", True),
        ("paragraphs_max", False),
        ("word_count_min", True),
    ]
    assert review["minimum_requirement_outcome"] == {
        "status": "not_checked",
        "returned_without_full_review": False,
        "teacher_note": None,
        "updated_at": None,
    }
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_requirement_status_back_returns_to_selector_without_mutation(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = MenuScreenRecorder(
        _enter_selected_student()
        + ["3", "1", "1", "b", "b", "4"]
        + _exit_selected_student_to_main()
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0
    screens = recorder.screens(capsys.readouterr().out)
    selector_screens = [
        screen
        for screen in screens
        if "Record Requirement Check" in screen.output
        and "Requirement Checks" in screen.output
    ]
    assert len(selector_screens) == 2
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


@pytest.mark.parametrize("invalid_choice", ["99", "invalid"])
def test_review_menu_invalid_requirement_selection_stays_in_workflow_without_mutation(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    invalid_choice: str,
) -> None:
    recorder = MenuScreenRecorder(
        _enter_selected_student()
        + ["3", "1", invalid_choice, "", "b", "4"]
        + _exit_selected_student_to_main()
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert "Invalid requirement selection." in output
    assert sum(
        "Record Requirement Check" in screen.output
        and "Requirement Checks" in screen.output
        for screen in screens
    ) == 2
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


def test_review_menu_invalid_requirement_status_returns_to_selector_without_mutation(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = MenuScreenRecorder(
        _enter_selected_student()
        + ["3", "1", "1", "invalid", "", "b", "4"]
        + _exit_selected_student_to_main()
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert "Invalid status." in output
    assert sum(
        "Record Requirement Check" in screen.output
        and "Requirement Checks" in screen.output
        for screen in screens
    ) == 2
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


def test_feedback_configuration_opens_focused_standard_selector(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_configured_requirement_check(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        requirement_key="paragraphs_min",
        met=True,
    )
    recorder = MenuScreenRecorder(
        _enter_selected_student()
        + ["6", "1", "b", "", "b"]
        + _exit_selected_student_to_main()
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0
    screens = recorder.screens(capsys.readouterr().out)
    focused = [
        screen.output
        for screen in screens
        if "Configure Focus Standard Feedback" in screen.output
    ]
    assert len(focused) == 1
    assert f"Student: {STUDENT_ID}" in focused[0]
    assert "Focus Standards:" in focused[0]
    assert "1. Configure rating/rationale/observation inclusion" not in focused[0]
    assert "2. Add custom Focus Standard comment" not in focused[0]


def test_review_menu_returns_without_full_review_when_policy_allows(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + [
            "3",
            "1",
            "1",
            "2",
            "Too short.",
            "",
            "b",
            "2",
            "2",
            "Add the required paragraph before resubmitting.",
            "",
            "4",
        ]
        + _exit_selected_student_to_main(),
    )

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Return without full standards review" in output
    assert "Selected outcome: Return without full standards review" in output
    assert "Finalized minimum-requirements outcome:" in output
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert review["review_state"] == "returned_without_full_review"
    assert review["minimum_requirement_outcome"]["status"] == (
        "returned_without_full_review"
    )
    assert review["minimum_requirement_outcome"]["returned_without_full_review"] is True
    assert review["minimum_requirement_outcome"]["teacher_note"] == (
        "Add the required paragraph before resubmitting."
    )
    assert "notes" not in review
    assert "tags" not in review
    assert "scores" not in review
    assert "comments" not in review
    assert "requirement_checks" not in review


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
        + ["8", ""]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_updates_review_workflow_state(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["9", "4", "1"]
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
    assert manifest["submission_state"] == "unreviewed"
    review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    assert review["review_state"] == "observations_in_progress"

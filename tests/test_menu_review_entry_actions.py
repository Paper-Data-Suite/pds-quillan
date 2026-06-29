"""Tests for guided selected-student review menu entry actions."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.cli import main
import quillan.comment_bank_workflows as comment_bank_workflows
import quillan.review_menu as review_menu
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.rubric_writing import (
    build_rubric,
    build_rubric_criterion,
    build_rubric_level,
    write_rubric,
)
from quillan.tag_bank_writing import (
    build_tag_bank,
    build_tag_category,
    build_tag_template,
    write_tag_bank,
)
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "stu_0001"
SECOND_STUDENT_ID = "stu_0002"
TIMESTAMP = "2026-06-22T12:00:00+00:00"
BANK_ID = "general_writing_synthetic"
EXAMPLE_BANK_PATH = (
    Path(__file__).parents[1]
    / "examples"
    / "comment_banks"
    / f"{BANK_ID}.json"
)


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
    evidence_path = root / "classes" / CLASS_ID / "assignments" / ASSIGNMENT_ID / "scans" / "response_stu_0001_pg_001.pdf"
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
    path = submission_manifest_path(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    return write_submission_manifest(path, manifest)


def _write_bank(root: Path) -> None:
    bank_path = root / "shared" / "comment_banks" / f"{BANK_ID}.json"
    bank_path.parent.mkdir(parents=True, exist_ok=True)
    bank_path.write_text(EXAMPLE_BANK_PATH.read_text(encoding="utf-8"), encoding="utf-8")


def _write_tag_bank(root: Path) -> None:
    category = build_tag_category(
        category_id="reasoning_explanation",
        label="Reasoning / Explanation",
        description="Teacher observations about reasoning.",
    )
    tag = build_tag_template(
        tag_template_id="explanation_needs_more_detail",
        label="Explanation needs more detail",
        category_id="reasoning_explanation",
        polarity="developing",
        optional_metadata={
            "severity_default": 2,
            "criterion_ids": ["explanation"],
            "teacher_note_prompt": "What part needs more detail?",
        },
    )
    bank = build_tag_bank(
        tag_bank_id="general_written_response_tags",
        title="General Written Response Tags",
        description="Reusable synthetic tag templates.",
        writing_types=["general"],
        categories=[category],
        tags=[tag],
    )
    write_tag_bank(root, bank)


def _write_rubric(root: Path) -> None:
    level = build_rubric_level(score=3, label="Clear explanation")
    criterion = build_rubric_criterion(
        criterion_id="reasoning",
        label="Reasoning / Explanation",
        max_score=4,
        scale="4_point",
        levels=[level],
    )
    rubric = build_rubric(
        rubric_id="synthetic_rubric",
        title="Synthetic Rubric",
        description="Synthetic scoring profile.",
        writing_types=["argument"],
        criteria=[criterion],
    )
    write_rubric(root, rubric)


def _write_review_record(root: Path, review: dict[str, Any]) -> Path:
    path = review_record_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    return write_review_record(path, review)


def _enter_selected_student(student_choice: str = "1") -> list[str]:
    return ["2", "1", "1", "1", "1", student_choice]


def _exit_selected_student_to_main() -> list[str]:
    return ["10", "6", "", "4", "6"]


def _exit_after_selected_student_action_to_main() -> list[str]:
    return ["", "10", "6", "", "4", "6"]


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def test_review_menu_selected_student_shows_review_entry_actions(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, _enter_selected_student() + _exit_selected_student_to_main())

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    assert "Selected Student Review" in output
    assert "1. Open submission evidence" in output
    assert "2. Manage submission pages" in output
    assert "3. Add teacher note" in output
    assert "4. Add structured tag" in output
    assert "5. Select reusable comment" in output
    assert "6. Set criterion score" in output
    assert "7. Update submission review state" in output
    assert "Review record: not started" in output
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


def test_review_menu_blank_note_cancels_without_review_record(
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
        + ["3", ""]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_adds_structured_tag_to_review_record(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + [
            "4",
            "2",
            "claim",
            "1",
            "",
        ]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert review["tags"][0]["label"] == "claim"
    assert review["tags"][0]["polarity"] == "positive"
    assert review["review_state"] == "in_progress"


def test_review_menu_selects_reusable_tag_by_bank_and_category(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_tag_bank(workspace)
    manifest_path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    manifest_before = manifest_path.read_bytes()

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["4", "1", "1", "1", "1", "The explanation names the idea only."]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "General Written Response Tags" in output
    assert "Explanation needs more detail" in output
    review = json.loads(
        review_record_path(
            workspace,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        ).read_text(encoding="utf-8")
    )
    tag = review["tags"][0]
    assert tag["source"] == "tag_bank"
    assert tag["tag_bank_id"] == "general_written_response_tags"
    assert tag["tag_template_id"] == "explanation_needs_more_detail"
    assert tag["label"] == "Explanation needs more detail"
    assert tag["polarity"] == "developing"
    assert tag["severity"] == 2
    assert tag["criterion_id"] == "explanation"
    assert tag["teacher_note"] == "The explanation names the idea only."
    assert "standard_id" not in tag
    assert review["review_state"] == "in_progress"
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_blank_tag_cancels_without_review_record(
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
        + ["4", ""]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_no_comment_banks_returns_safely(
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
        + ["5", "1"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    assert "No valid shared comment banks found" in capsys.readouterr().out
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_selects_reusable_comment_by_number(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_bank(workspace)
    manifest_path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    manifest_before = manifest_path.read_bytes()

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["5", "1", "1", "1", "1", "1"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Selected review comment:" in output
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert review["comments"][0]["bank_id"] == BANK_ID
    assert review["comments"][0]["comment_id"] == "focus_is_clear"
    assert review["review_state"] == "in_progress"
    assert manifest_path.read_bytes() == manifest_before


def test_comment_bank_created_by_workflow_is_selectable_in_review(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        comment_bank_workflows,
        "resolve_workspace_root",
        lambda: workspace,
    )
    _menu_input(
        monkeypatch,
        [
            "General Written Response Comments",
            "",
            "Reusable comments for written responses across subjects.",
            "general",
            "3",
            "",
            "",
            "Explanation needs more detail",
            "",
            "Your response identifies the idea, but explain your reasoning more fully.",
            "1",
            "2",
            "",
            "",
            "",
            "1",
        ],
    )

    assert comment_bank_workflows.prompt_create_comment_bank() == 0

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["5", "1", "1", "1", "1", "1"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "general_written_response_comments" in output
    assert "Explanation needs more detail" in output
    review = json.loads(
        review_record_path(
            workspace,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
        ).read_text(encoding="utf-8")
    )
    comment = review["comments"][0]
    assert comment["source"] == "comment_bank"
    assert comment["bank_id"] == "general_written_response_comments"
    assert comment["comment_id"] == "explanation_needs_more_detail"
    assert comment["label"] == "Explanation needs more detail"
    assert (
        comment["text"]
        == "Your response identifies the idea, but explain your reasoning more fully."
    )


def test_review_menu_sets_criterion_score(
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
        + ["6", "evidence", "Evidence", "3", "4", "", ""]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert review["scores"][0]["criterion_id"] == "evidence"
    assert review["scores"][0]["score"] == 3
    assert review["scores"][0]["max_score"] == 4
    assert review["review_state"] == "in_progress"
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_scores_from_assignment_rubric(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_rubric(workspace)
    manifest_path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    manifest_before = manifest_path.read_bytes()

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["6", "1", "1", "1", "2", "Private score note"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    score = review["scores"][0]
    assert score["criterion_id"] == "reasoning"
    assert score["label"] == "Reasoning / Explanation"
    assert score["score"] == 3
    assert score["max_score"] == 4
    assert score["scale"] == "4_point"
    assert score["teacher_note"] == "Private score note"
    assert manifest_path.read_bytes() == manifest_before
    capsys.readouterr()


def test_review_menu_missing_rubric_keeps_custom_score_available(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["6", "1", "1", "Evidence", "", "2", "4", "", ""]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    review = json.loads(
        review_record_path(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert review["scores"][0]["criterion_id"] == "evidence"
    assert "does not resolve" in capsys.readouterr().out


def test_review_menu_blank_score_cancels_without_review_record(
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
        + ["6", ""]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()
    assert manifest_path.read_bytes() == manifest_before


def test_review_menu_invalid_score_does_not_corrupt_review_record(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = {
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
        "tags": [],
        "scores": [
            {
                "score_id": "score_0001",
                "criterion_id": "evidence",
                "label": "Evidence",
                "score": 3,
                "max_score": 4,
                "updated_at": TIMESTAMP,
                "module_details": {},
            }
        ],
        "comments": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }
    path = _write_review_record(workspace, review)
    before = path.read_bytes()

    _menu_input(
        monkeypatch,
        _enter_selected_student()
        + ["6", "evidence", "Evidence", "5", "4", "", ""]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    assert path.read_bytes() == before
    assert json.loads(path.read_text(encoding="utf-8"))["scores"][0]["score"] == 3


def test_review_menu_invalid_state_does_not_corrupt_manifest(
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
        + ["7", "not_a_state"]
        + _exit_after_selected_student_action_to_main(),
    )

    assert main(["menu"]) == 0
    assert manifest_path.read_bytes() == manifest_before
    assert not review_record_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()

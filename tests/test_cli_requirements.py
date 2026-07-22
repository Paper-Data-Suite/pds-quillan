"""Direct CLI coverage for assignment-aware minimum-requirement review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.cli import main
from quillan.cli_app.handlers import requirements as handlers
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english10_p2"
ASSIGNMENT_ID = "argument_01"
STUDENT_ID = "00107"
TIMESTAMP = "2026-07-13T12:00:00+00:00"


def _assignment() -> dict[str, Any]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Argument",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Make an argument.",
        "standards_profile_id": "ela",
        "focus_standard_ids": ["W.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "two_level",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Developing."}
            ],
        },
        "basic_requirements": {
            "paragraphs_min": 3,
            "paragraphs_max": 6,
            "word_count_min": 400,
            "word_count_max": 900,
            "required_elements": ["thesis", "textual evidence"],
        },
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def _manifest() -> dict[str, Any]:
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
        "module_details": {"submission_entry_method": "plain_paper_manual"},
    }


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    assignment_path = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    assignment_path.parent.mkdir(parents=True)
    assignment_path.write_text(json.dumps(_assignment()), encoding="utf-8")
    write_submission_manifest(
        submission_manifest_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["requirements", "--help"],
        ["requirements", "list", "--help"],
        ["requirements", "set-check", "--help"],
        ["requirements", "set-outcome", "--help"],
    ],
)
def test_requirement_help_exits_successfully(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 0


def test_bare_requirements_prints_help_without_resolving_workspace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        handlers,
        "resolve_workspace_root",
        lambda: pytest.fail("bare namespace resolved the workspace"),
    )
    assert main(["requirements"]) == 0
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "{list,set-check,set-outcome}" in output


def test_list_is_read_only_and_preserves_requirement_order(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "builtins.input", lambda *_args: pytest.fail("direct command prompted")
    )
    assignment_path = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    manifest_path = submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = (assignment_path.read_bytes(), manifest_path.read_bytes())

    assert main(["requirements", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0

    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    keys = [
        "paragraphs_min",
        "paragraphs_max",
        "word_count_min",
        "word_count_max",
        "required_elements:thesis",
        "required_elements:textual evidence",
    ]
    assert [output.index(f"Key: {key}") for key in keys] == sorted(
        output.index(f"Key: {key}") for key in keys
    )
    assert f"Student: {STUDENT_ID}" in output
    assert "Review record exists: no" in output
    assert "Review state: not_started" in output
    assert "Overall outcome: not_checked" in output
    assert output.count("State: not checked") == 6
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()
    assert (assignment_path.read_bytes(), manifest_path.read_bytes()) == before


def test_set_check_uses_assignment_values_and_clears_omitted_note(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["requirements", "set-check", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    assert main(args + ["--requirement-key", "paragraphs_min", "--met", "false", "--note", " Too short. "]) == 0
    assert main(args + ["--requirement-key", "paragraphs_min", "--met", "true"]) == 0

    review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(encoding="utf-8")
    )
    check = review["minimum_requirement_checks"][0]
    assert check["requirement_check_id"] == "requirement_check_0001"
    assert check["label"] == "Minimum paragraphs"
    assert check["expected"] == 3
    assert check["met"] is True
    assert "teacher_note" not in check
    assert len(review["minimum_requirement_checks"]) == 1
    assert "Action: updated" in (lambda captured: captured.out + captured.err)(capsys.readouterr())


def test_unknown_key_and_missing_manifest_fail_without_writing(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command = [
        "requirements", "set-check", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID,
        "--requirement-key", "arbitrary", "--met", "true",
    ]
    assert main(command) == 1
    assert "Valid keys:" in (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()

    submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).unlink()
    assert main(command) == 1
    assert "assemble" in (lambda captured: captured.out + captured.err)(capsys.readouterr()).lower()
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()


def test_outcome_eligibility_and_return_safeguards(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = ["requirements", "set-check", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    assert main(base + ["--requirement-key", "paragraphs_min", "--met", "false"]) == 0
    outcome = ["requirements", "set-outcome", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    assert main(outcome + ["--outcome", "met"]) == 1
    assert main(outcome + ["--outcome", "returned_without_full_review"]) == 1
    assert main(outcome + ["--outcome", "unmet_continue_review"]) == 0
    assert main(outcome + ["--outcome", "returned_without_full_review", "--note", " Revise and resubmit. "]) == 0

    review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(encoding="utf-8")
    )
    assert review["review_state"] == "returned_without_full_review"
    assert review["minimum_requirement_outcome"] == {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Revise and resubmit.",
        "updated_at": review["minimum_requirement_outcome"]["updated_at"],
    }
    assert "Full standards review was not completed." in (lambda captured: captured.out + captured.err)(capsys.readouterr())


def test_met_succeeds_only_after_every_configured_check_is_met(workspace: Path) -> None:
    base = ["requirements", "set-check", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    for key in (
        "paragraphs_min",
        "paragraphs_max",
        "word_count_min",
        "word_count_max",
        "required_elements:thesis",
        "required_elements:textual evidence",
    ):
        assert main(base + ["--requirement-key", key, "--met", "true"]) == 0
    assert main(
        ["requirements", "set-outcome", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID,
         "--outcome", "met"]
    ) == 0
    review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(encoding="utf-8")
    )
    assert review["review_state"] == "requirements_checked"
    assert review["minimum_requirement_outcome"]["status"] == "met"


def test_assignment_policy_cannot_be_overridden(workspace: Path) -> None:
    assignment_path = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    assignment = _assignment()
    assignment["minimum_requirement_policy"]["allow_return_without_full_review"] = False
    assignment_path.write_text(json.dumps(assignment), encoding="utf-8")
    assert main(
        ["requirements", "set-check", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID,
         "--requirement-key", "paragraphs_min", "--met", "false"]
    ) == 0
    assert main(
        ["requirements", "set-outcome", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID,
         "--outcome", "returned_without_full_review", "--note", "Revise."]
    ) == 1


def test_malformed_existing_review_fails_list_without_repair(workspace: Path) -> None:
    path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    path.write_text("{malformed", encoding="utf-8")
    before = path.read_bytes()
    assert main(["requirements", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 1
    assert path.read_bytes() == before


def test_stale_unmet_check_does_not_enable_outcome(workspace: Path) -> None:
    review = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=TIMESTAMP,
    )
    review["minimum_requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "removed_key",
            "label": "Removed",
            "expected": "old",
            "met": False,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    write_review_record(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID), review
    )
    assert main(
        ["requirements", "set-outcome", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID,
         "--outcome", "unmet_continue_review"]
    ) == 1


def test_no_configured_requirements_list_succeeds_but_set_fails(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    assignment = _assignment()
    assignment["basic_requirements"] = {}
    path.write_text(json.dumps(assignment), encoding="utf-8")
    assert main(["requirements", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0
    assert "Minimum requirements: none configured" in (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert main(
        ["requirements", "set-check", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID,
         "--requirement-key", "paragraphs_min", "--met", "true"]
    ) == 1
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()

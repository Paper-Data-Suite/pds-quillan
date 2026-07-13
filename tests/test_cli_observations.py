"""Direct CLI coverage for Focus Standard review-unit observations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.cli import main
from quillan.cli_app.handlers import observations as handlers
from quillan.review_observations import set_review_units
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
        "focus_standard_ids": ["W.1", "L.2"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "unusual",
            "levels": [
                {"value": 0, "label": "Beginning", "description": "Beginning."},
                {"value": 7, "label": "Secure", "description": "Secure."},
            ],
        },
        "basic_requirements": {},
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
        / "assignments"
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


def _set_args(*extra: str) -> list[str]:
    return [
        "observations",
        "set",
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "--unit-id",
        "paragraph_1",
        "--standard-id",
        "W.1",
        *extra,
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["observations", "--help"],
        ["observations", "list", "--help"],
        ["observations", "set", "--help"],
    ],
)
def test_observation_help_exits_successfully(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 0


def test_bare_namespace_prints_help_without_resolving_workspace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        handlers,
        "resolve_workspace_root",
        lambda: pytest.fail("bare namespace resolved the workspace"),
    )
    assert main(["observations"]) == 0
    assert "{list,set}" in capsys.readouterr().out


def test_list_without_review_is_read_only_and_reports_setup_guidance(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assignment_path = (
        workspace / "classes" / CLASS_ID / "assignments" / ASSIGNMENT_ID / "assignment.json"
    )
    manifest_path = submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = assignment_path.read_bytes(), manifest_path.read_bytes()

    assert main(["observations", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0

    output = capsys.readouterr().out
    assert f"Student: {STUDENT_ID}" in output
    assert "Review state: not_started" in output
    assert "Review record exists: no" in output
    assert "Review units: 0" in output
    assert "must be defined before observations" in output
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()
    assert (assignment_path.read_bytes(), manifest_path.read_bytes()) == before


def test_list_orders_units_and_standards_and_reports_matrix_totals(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    set_review_units(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 3, "label": "Conclusion"}, {"sequence": 1, "label": "Opening"}],
        updated_at=TIMESTAMP,
    )
    assert main(_set_args("--applicable", "true", "--evidence-present", "false")) == 0
    record_path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = record_path.read_bytes()
    capsys.readouterr()

    assert main(["observations", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0

    output = capsys.readouterr().out
    assert output.index("1. Opening") < output.index("3. Conclusion")
    first_unit = output[output.index("1. Opening") : output.index("3. Conclusion")]
    assert first_unit.index("Focus Standard: W.1") < first_unit.index("Focus Standard: L.2")
    assert "Expected unit-standard pairs: 4" in output
    assert "Recorded observations: 1" in output
    assert "Unrecorded pairs: 3" in output
    assert "Evidence missing: 1" in output
    assert "Observation ID: observation_0001" in output
    assert "Status: not recorded" in output
    assert record_path.read_bytes() == before


def test_set_applicable_supports_optional_assignment_scale_rating_and_replacement(
    workspace: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    set_review_units(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=TIMESTAMP,
    )
    monkeypatch.setattr("builtins.input", lambda *_args: pytest.fail("CLI prompted"))
    assert main(
        _set_args(
            "--applicable",
            "true",
            "--evidence-present",
            "true",
            "--rating",
            "7",
            "--rationale",
            "  Strong evidence.  ",
            "--include-in-feedback",
            "false",
        )
    ) == 0
    first_output = capsys.readouterr().out
    assert "Unit-level rating: 7 (Secure)" in first_output
    assert "Rationale: present" in first_output

    assert main(_set_args("--applicable", "true", "--evidence-present", "false")) == 0
    review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    observation = review["review_units"][0]["standard_observations"][0]
    assert observation["observation_id"] == "observation_0001"
    assert observation["evidence_present"] is False
    assert observation["rating"] is None
    assert observation["rationale"] is None
    assert observation["include_in_feedback"] is True
    assert review["overall_standard_ratings"] == []
    assert review["feedback"]["standard_feedback"] == []
    assert "Action: updated" in capsys.readouterr().out


def test_set_not_applicable_stores_nulls_and_allows_feedback_override(
    workspace: Path,
) -> None:
    set_review_units(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=TIMESTAMP,
    )
    assert main(
        _set_args(
            "--applicable",
            "false",
            "--rationale",
            "Transition only.",
            "--include-in-feedback",
            "true",
        )
    ) == 0
    review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    observation = review["review_units"][0]["standard_observations"][0]
    assert observation["applicable"] is False
    assert observation["evidence_present"] is None
    assert observation["rating"] is None
    assert observation["include_in_feedback"] is True


@pytest.mark.parametrize(
    "extra,message",
    [
        (("--applicable", "true"), "required when --applicable true"),
        (
            ("--applicable", "false", "--evidence-present", "true"),
            "must be omitted when --applicable false",
        ),
        (("--applicable", "false", "--rating", "7"), "--rating must be omitted"),
        (
            ("--applicable", "true", "--evidence-present", "true", "--rating", "4"),
            "Allowed values: 0, 7",
        ),
    ],
)
def test_invalid_combinations_do_not_change_review(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    extra: tuple[str, ...],
    message: str,
) -> None:
    set_review_units(
        workspace,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=TIMESTAMP,
    )
    record_path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = record_path.read_bytes()
    assert main(_set_args(*extra)) == 1
    assert message in capsys.readouterr().out
    assert record_path.read_bytes() == before


def test_returned_review_can_be_listed_but_not_changed(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=TIMESTAMP,
    )
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
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Missing work.",
        "updated_at": TIMESTAMP,
    }
    record_path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    write_review_record(record_path, review)
    before = record_path.read_bytes()

    assert main(["observations", "list", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0
    assert "Review state: returned_without_full_review" in capsys.readouterr().out
    assert main(_set_args("--applicable", "true", "--evidence-present", "true")) == 1
    assert "Change the minimum-requirements outcome" in capsys.readouterr().out
    assert record_path.read_bytes() == before

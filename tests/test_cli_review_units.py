"""Direct CLI coverage for canonical review-unit management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.cli import main
from quillan.cli_app.handlers import review_units as handlers
from quillan.review_record_paths import review_record_path
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
            "levels": [{"value": 1, "label": "Developing", "description": "Developing."}],
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
        tmp_path / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
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
        ["review-units", "--help"],
        ["review-units", "show", "--help"],
        ["review-units", "set", "--help"],
    ],
)
def test_review_unit_help_exits_successfully(argv: list[str]) -> None:
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
    assert main(["review-units"]) == 0
    assert "{show,set}" in capsys.readouterr().out


def test_show_without_review_is_read_only(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assignment_path = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    manifest_path = submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = assignment_path.read_bytes(), manifest_path.read_bytes()

    assert main(["review-units", "show", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0

    output = capsys.readouterr().out
    assert f"Student: {STUDENT_ID}" in output
    assert "Review-unit type: paragraph" in output
    assert "Review record exists: no" in output
    assert "Review state: not_started" in output
    assert "Total units: 0" in output
    assert "Total observations: 0" in output
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()
    assert (assignment_path.read_bytes(), manifest_path.read_bytes()) == before


def test_count_creates_menu_equivalent_canonical_units(
    workspace: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda *_args: pytest.fail("CLI prompted"))
    assignment_path = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    manifest_path = submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = assignment_path.read_bytes(), manifest_path.read_bytes()
    args = ["review-units", "set", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    assert main(args + ["--count", "2"]) == 0
    review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    assert [(unit["unit_id"], unit["label"]) for unit in review["review_units"]] == [
        ("paragraph_1", "Paragraph 1"),
        ("paragraph_2", "Paragraph 2"),
    ]
    assert all("page_number" not in unit and "evidence_id" not in unit for unit in review["review_units"])
    assert (assignment_path.read_bytes(), manifest_path.read_bytes()) == before
    output = capsys.readouterr().out
    assert "Resulting unit count: 2" in output
    assert "Newly empty units added: 2" in output
    assert "Review state: observations_in_progress" in output


def test_json_units_are_constrained_and_sorted(
    workspace: Path, tmp_path: Path
) -> None:
    units_path = tmp_path / "units.json"
    units_path.write_text(
        json.dumps([{"sequence": 3, "label": "Conclusion"}, {"sequence": 1}]),
        encoding="utf-8",
    )
    args = ["review-units", "set", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    assert main(args + ["--units", str(units_path)]) == 0
    review = json.loads(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    assert [unit["sequence"] for unit in review["review_units"]] == [1, 3]
    assert [unit["label"] for unit in review["review_units"]] == ["Paragraph 1", "Conclusion"]


@pytest.mark.parametrize(
    "value,error_text",
    [
        ({"sequence": 1}, "root must be a JSON array"),
        ([], "must not be empty"),
        ([{"sequence": 1, "unit_id": "injected"}], "prohibited or unknown"),
        ([{"sequence": True}], "positive integer"),
        ([{"sequence": 1, "label": "  "}], "non-empty string"),
    ],
)
def test_invalid_json_input_does_not_create_review(
    workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    value: Any,
    error_text: str,
) -> None:
    units_path = tmp_path / "invalid-units.json"
    units_path.write_text(json.dumps(value), encoding="utf-8")
    args = ["review-units", "set", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    assert main(args + ["--units", str(units_path)]) == 1
    output = capsys.readouterr().out
    assert "Error: " in output
    assert error_text in output
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()

"""Tests for Quillan's teacher-facing assignment config workflows."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pds_core.classes import write_class_roster
from pds_core.rosters import create_roster
import pytest

import quillan.assignment_workflows as workflows
from quillan.assignments import (
    AssignmentConfigError,
    load_assignment_config,
    validate_assignment_config,
)


def _assignment(
    *,
    assignment_id: str = "literary_analysis_essay",
    class_id: str = "english_12_p3",
) -> dict[str, object]:
    return workflows.build_assignment_config(
        assignment_id=assignment_id,
        title="Literary Analysis Essay",
        class_id=class_id,
        writing_type="literary_analysis",
        student_prompt="Analyze how the author develops a central idea.",
        standards_profile_id="synthetic_ela_11_12",
        focus_standard_ids=[
            "njsls-ela:W.AW.11-12.1",
            "njsls-ela:L.KL.11-12.2",
        ],
        review_unit={
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        rating_scale={
            "scale_id": "standards_4_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                },
                {
                    "value": 2,
                    "label": "Meeting",
                    "description": "Clear evidence.",
                },
            ],
        },
        basic_requirements={
            "paragraphs_min": 4,
            "word_count_min": 500,
            "required_elements": ["claim", "textual evidence"],
        },
        minimum_requirement_policy={
            "allow_return_without_full_review": True,
        },
    )


def _write_roster(workspace_root: Path, class_id: str = "english_12_p3") -> None:
    roster = create_roster(
        class_id,
        [
            {
                "student_id": "0001",
                "last_name": "Synthetic",
                "first_name": "Avery",
                "period": "3",
            }
        ],
    )
    write_class_roster(workspace_root, roster)


def _inputs(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str],
) -> list[str]:
    response_iterator: Iterator[str] = iter(responses)
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        try:
            return next(response_iterator)
        except StopIteration as error:
            raise AssertionError("Workflow requested unexpected input.") from error

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def test_build_assignment_config_has_required_v2_fields_and_validates() -> None:
    assignment = _assignment()

    assert list(assignment) == [
        "schema_version",
        "module",
        "record_type",
        "assignment_id",
        "title",
        "class_ids",
        "writing_type",
        "student_prompt",
        "standards_profile_id",
        "focus_standard_ids",
        "review_unit",
        "rating_scale",
        "basic_requirements",
        "minimum_requirement_policy",
    ]
    validate_assignment_config(assignment)


def test_write_assignment_config_uses_canonical_path(tmp_path: Path) -> None:
    assignment = _assignment()

    path = workflows.write_assignment_config(
        tmp_path,
        "english_12_p3",
        assignment,
    )

    assert path == (
        tmp_path
        / "classes"
        / "english_12_p3"
        / "assignments"
        / "literary_analysis_essay"
        / "assignment.json"
    )
    assert load_assignment_config(path) == assignment
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_assignment_config_rejects_class_path_mismatch(
    tmp_path: Path,
) -> None:
    assignment = _assignment(class_id="english_12_p3")

    with pytest.raises(AssignmentConfigError, match="class_ids"):
        workflows.write_assignment_config(
            tmp_path,
            "english_12_p4",
            assignment,
        )

    assert not list(tmp_path.rglob("assignment.json"))


def test_assignment_parsing_helpers() -> None:
    assert workflows.suggest_assignment_id("  Cafe Literary Analysis!  ") == (
        "cafe_literary_analysis"
    )
    assert workflows.parse_comma_separated_values(" A, B ,, C ") == [
        "A",
        "B",
        "C",
    ]
    assert workflows.parse_comma_separated_values("") == []
    assert workflows.parse_optional_nonnegative_int("", "paragraphs_min") is None
    assert workflows.parse_optional_nonnegative_int(" 0 ", "paragraphs_min") == 0
    assert workflows.parse_optional_nonnegative_int("12", "word_count_min") == 12

    with pytest.raises(ValueError, match="non-negative integer"):
        workflows.parse_optional_nonnegative_int("-1", "paragraphs_min")
    with pytest.raises(ValueError, match="non-negative integer"):
        workflows.parse_optional_nonnegative_int("many", "paragraphs_min")


def test_prompt_create_assignment_is_unavailable_pending_v2_workflow(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert workflows.prompt_create_assignment() == 1
    output = capsys.readouterr().out
    assert "temporarily unavailable" in output
    assert "schema_version '2'" in output


def test_view_validate_assignment_prints_v2_summary_without_rewriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    path = workflows.write_assignment_config(
        tmp_path,
        "english_12_p3",
        _assignment(),
    )
    original_bytes = path.read_bytes()
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    prompts = _inputs(monkeypatch, ["1", "1"])

    assert workflows.prompt_view_validate_assignment() == 0
    output = capsys.readouterr().out
    assert "Assignment config is valid." in output
    assert "Schema version: 2" in output
    assert "Assignment ID: literary_analysis_essay" in output
    assert "Title: Literary Analysis Essay" in output
    assert "Class IDs: english_12_p3" in output
    assert "Writing type: literary_analysis" in output
    assert "Standards profile ID: synthetic_ela_11_12" in output
    assert "Focus standard IDs (2)" in output
    assert "Review unit: paragraph" in output
    assert "Rating scale: standards_4_level (2 levels)" in output
    assert "Rubric ID" not in output
    assert "Assignment JSON path" not in prompts
    assert path.read_bytes() == original_bytes


def test_view_validate_assignment_reports_error_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    path = (
        tmp_path
        / "classes"
        / "english_12_p3"
        / "assignments"
        / "invalid"
        / "assignment.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text('{"assignment_id": "incomplete"}', encoding="utf-8")
    original_bytes = path.read_bytes()
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    prompts = _inputs(monkeypatch, ["1"])

    assert workflows.prompt_view_validate_assignment() == 0
    output = capsys.readouterr().out
    assert "No valid assignments found for class english_12_p3." in output
    assert "Assignment JSON path" not in prompts
    assert "Traceback" not in output
    assert path.read_bytes() == original_bytes


def test_assignment_menu_displays_options_and_dispatches(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def record(name: str) -> int:
        calls.append(name)
        return 0

    monkeypatch.setattr(
        workflows,
        "prompt_create_assignment",
        lambda: record("create"),
    )
    monkeypatch.setattr(
        workflows,
        "prompt_view_validate_assignment",
        lambda: record("view"),
    )
    _inputs(monkeypatch, ["1", "", "2", "", "4"])

    assert workflows.launch_assignment_menu() == 0
    output = capsys.readouterr().out
    assert calls == ["create", "view"]
    assert "Create writing assignment" in output
    assert "View/validate assignment" in output
    assert "Printable Response Pages" in output
    assert "Back" in output


def test_assignment_menu_invalid_selection_and_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _inputs(monkeypatch, ["bad", "", "4"])
    assert workflows.launch_assignment_menu() == 0
    assert "Invalid selection" in capsys.readouterr().out

    def interrupt(_prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert workflows.launch_assignment_menu() == 0
    assert "Exiting assignment menu." in capsys.readouterr().out

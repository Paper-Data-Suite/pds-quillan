"""Tests for Quillan's teacher-facing assignment config workflows."""

from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path

from pds_core.classes import write_class_roster
from pds_core.rosters import create_roster
from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)
import pytest

import quillan.assignment_workflows as workflows
from quillan.assignments import (
    AssignmentConfigError,
    load_assignment_config,
    validate_assignment_config,
)
from quillan.rubric_writing import (
    build_rubric,
    build_rubric_criterion,
    build_rubric_level,
    write_rubric,
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
        standards_profile_id="synthetic_ela_11_12",
        tagging_mode="focus",
        focus_standards=[
            "njsls-ela:W.AW.11-12.1",
            "njsls-ela:L.KL.11-12.2",
        ],
        basic_requirements={
            "paragraphs_min": 4,
            "word_count_min": 500,
            "required_elements": ["claim", "textual evidence"],
        },
        rubric_id="synthetic_argument_v1",
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


def _write_standards_library(workspace_root: Path) -> None:
    write_workspace_standards_library(
        workspace_root,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id="njsls-ela:W.AW.11-12.1",
                    code="W.AW.11-12.1",
                    source="NJSLS",
                    short_name="Argument Writing",
                    description="Synthetic argument writing standard.",
                    subject="English Language Arts",
                    course="English 12",
                    domain="Writing",
                    available_modules=("quillan",),
                ),
                StandardDefinition(
                    standard_id="njsls-ela:L.KL.11-12.2",
                    code="L.KL.11-12.2",
                    source="NJSLS",
                    short_name="Language Knowledge",
                    description="Synthetic language knowledge standard.",
                    subject="English Language Arts",
                    course="English 12",
                    domain="Language",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id="synthetic_ela_11_12",
                    standards=(
                        "njsls-ela:W.AW.11-12.1",
                        "njsls-ela:L.KL.11-12.2",
                    ),
                    subject="English Language Arts",
                    course="English 12",
                    source="NJSLS",
                    title="Synthetic ELA 11-12",
                ),
            ),
        ),
    )


def _write_rubric(workspace_root: Path) -> None:
    level = build_rubric_level(score=3, label="Clear explanation")
    criterion = build_rubric_criterion(
        criterion_id="reasoning",
        label="Reasoning / Explanation",
        max_score=4,
        scale="4_point",
        levels=[level],
    )
    rubric = build_rubric(
        rubric_id="general_response",
        title="General Response Rubric",
        description="Synthetic scoring profile.",
        writing_types=["general"],
        criteria=[criterion],
    )
    write_rubric(workspace_root, rubric)


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


def _creation_responses(
    *,
    selection: str = "1",
    assignment_id: str = "",
    paragraphs_min: str = "4",
    overwrite: str | None = None,
) -> list[str]:
    responses = [
        selection,
        "Literary Analysis Essay",
        assignment_id,
        "literary_analysis",
        "1",
        "1, 2",
        "",
        paragraphs_min,
        "",
        "500",
        "",
        "claim, textual evidence",
        "synthetic_argument_v1",
    ]
    if overwrite is not None:
        responses.append(overwrite)
    return responses


def test_build_assignment_config_has_required_fields_and_validates() -> None:
    assignment = _assignment()

    assert list(assignment) == [
        "assignment_id",
        "title",
        "class_ids",
        "writing_type",
        "standards_profile_id",
        "tagging_mode",
        "focus_standards",
        "basic_requirements",
        "rubric_id",
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


def test_prompt_create_assignment_selects_roster_class_and_writes_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, _creation_responses())

    assert workflows.prompt_create_assignment() == 0
    path = (
        tmp_path
        / "classes"
        / "english_12_p3"
        / "assignments"
        / "literary_analysis_essay"
        / "assignment.json"
    )
    assignment = load_assignment_config(path)
    assert assignment["class_ids"] == ["english_12_p3"]
    assert assignment["focus_standards"] == [
        "njsls-ela:W.AW.11-12.1",
        "njsls-ela:L.KL.11-12.2",
    ]
    assert assignment["basic_requirements"] == {
        "paragraphs_min": 4,
        "word_count_min": 500,
        "required_elements": ["claim", "textual evidence"],
    }
    assert "Saved assignment config:" in capsys.readouterr().out


def test_prompt_create_assignment_can_select_shared_rubric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    _write_rubric(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    responses = _creation_responses()
    responses[-1] = "1"
    _inputs(monkeypatch, responses)

    assert workflows.prompt_create_assignment() == 0

    assignment = load_assignment_config(
        tmp_path
        / "classes"
        / "english_12_p3"
        / "assignments"
        / "literary_analysis_essay"
        / "assignment.json"
    )
    assert assignment["rubric_id"] == "general_response"


def test_prompt_create_assignment_accepts_exact_class_id_and_blank_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    responses = _creation_responses(
        selection="english_12_p3",
        assignment_id="custom_assignment",
        paragraphs_min="",
    )
    responses[9] = ""
    responses[11] = ""
    _inputs(monkeypatch, responses)

    assert workflows.prompt_create_assignment() == 0
    assignment = load_assignment_config(
        tmp_path
        / "classes"
        / "english_12_p3"
        / "assignments"
        / "custom_assignment"
        / "assignment.json"
    )
    assert assignment["focus_standards"] == [
        "njsls-ela:W.AW.11-12.1",
        "njsls-ela:L.KL.11-12.2",
    ]
    assert assignment["basic_requirements"] == {}


def test_prompt_create_assignment_requires_existing_roster(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)

    assert workflows.prompt_create_assignment() == 1
    assert "No class rosters found" in capsys.readouterr().out
    assert not (tmp_path / "classes").exists()


def test_prompt_create_assignment_rejects_invalid_teacher_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        ["1", "Synthetic Assignment", "invalid assignment id"],
    )

    assert workflows.prompt_create_assignment() == 1
    assert "Error:" in capsys.readouterr().out
    assert not list(tmp_path.rglob("assignment.json"))


def test_prompt_create_assignment_explains_missing_standards_library(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        ["1", "Synthetic Assignment", "", "argument"],
    )

    assert workflows.prompt_create_assignment() == 1
    assert "Create or import standards through pds-core first" in (
        capsys.readouterr().out
    )
    assert not list(tmp_path.rglob("assignment.json"))


def test_prompt_create_assignment_rejects_invalid_numeric_requirement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        _creation_responses(paragraphs_min="-1")[:8],
    )

    assert workflows.prompt_create_assignment() == 1
    assert "paragraphs_min must be a non-negative integer" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("confirmation", "expected_title"),
    [
        ("no", "Original Synthetic Assignment"),
        ("OVERWRITE", "Literary Analysis Essay"),
    ],
)
def test_prompt_create_assignment_overwrite_requires_exact_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    confirmation: str,
    expected_title: str,
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    existing = _assignment()
    existing["title"] = "Original Synthetic Assignment"
    path = workflows.write_assignment_config(
        tmp_path,
        "english_12_p3",
        existing,
    )
    original_text = path.read_text(encoding="utf-8")
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, _creation_responses(overwrite=confirmation))

    result = workflows.prompt_create_assignment()
    assert result == (0 if confirmation == "OVERWRITE" else 1)
    assert load_assignment_config(path)["title"] == expected_title
    if confirmation != "OVERWRITE":
        assert path.read_text(encoding="utf-8") == original_text


def test_view_validate_assignment_prints_summary_without_rewriting(
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
    assert "Assignment ID: literary_analysis_essay" in output
    assert "Title: Literary Analysis Essay" in output
    assert "Class IDs: english_12_p3" in output
    assert "Writing type: literary_analysis" in output
    assert "Standards profile ID: synthetic_ela_11_12" in output
    assert "Tagging mode: focus" in output
    assert "Focus standards (2)" in output
    assert "Rubric ID: synthetic_argument_v1" in output
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
    path.write_text(json.dumps({"assignment_id": "incomplete"}), encoding="utf-8")
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
    _inputs(monkeypatch, ["1", "", "2", "", "3"])

    assert workflows.launch_assignment_menu() == 0
    output = capsys.readouterr().out
    assert calls == ["create", "view"]
    assert "Create writing assignment" in output
    assert "View/validate assignment" in output
    assert "Back" in output


def test_assignment_menu_invalid_selection_and_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _inputs(monkeypatch, ["bad", "", "3"])
    assert workflows.launch_assignment_menu() == 0
    assert "Invalid selection" in capsys.readouterr().out

    def interrupt(_prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert workflows.launch_assignment_menu() == 0
    assert "Exiting assignment menu." in capsys.readouterr().out

"""Tests for Quillan's teacher-facing assignment config workflows."""

from __future__ import annotations

from collections.abc import Iterator
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
from quillan.menu_navigation import QuitQuillan, ReturnToMainMenu

STANDARD_ID = "njsls-ela:W.AW.11-12.1"
SECOND_STANDARD_ID = "njsls-ela:L.KL.11-12.2"


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
            STANDARD_ID,
            SECOND_STANDARD_ID,
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


def _write_standards_library(workspace_root: Path) -> None:
    write_workspace_standards_library(
        workspace_root,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_ID,
                    code="W.AW.11-12.1",
                    source="NJSLS",
                    short_name="Argument Writing",
                    description="Write arguments supported by evidence.",
                    available_modules=("quillan",),
                ),
                StandardDefinition(
                    standard_id=SECOND_STANDARD_ID,
                    code="L.KL.11-12.2",
                    source="NJSLS",
                    short_name="Language Knowledge",
                    description="Apply knowledge of language.",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id="synthetic_ela_11_12",
                    standards=(STANDARD_ID, SECOND_STANDARD_ID),
                    title="Synthetic ELA 11-12",
                ),
            ),
        ),
    )


def _write_standards_library_without_profiles(workspace_root: Path) -> None:
    write_workspace_standards_library(
        workspace_root,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_ID,
                    code="W.AW.11-12.1",
                    source="NJSLS",
                    short_name="Argument Writing",
                    description="Write arguments supported by evidence.",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(),
        ),
    )


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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("literary analysis", "literary_analysis"),
        ("Literary Analysis", "literary_analysis"),
        ("  literary analysis  ", "literary_analysis"),
        ("research-paper", "research_paper"),
        ("research_paper", "research_paper"),
        ("short response", "short_response"),
        ("compare/contrast", "compare_contrast"),
    ],
)
def test_normalize_writing_type_accepts_teacher_friendly_input(
    value: str,
    expected: str,
) -> None:
    assert workflows.normalize_writing_type(value) == expected


@pytest.mark.parametrize("value", ["", " !?! ", "123 response"])
def test_normalize_writing_type_rejects_unusable_input(value: str) -> None:
    with pytest.raises(ValueError, match="writing type"):
        workflows.normalize_writing_type(value)


def test_prompt_create_assignment_writes_valid_v2_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "1",
            "1",
            "Literary Analysis Essay",
            "",
            "literary analysis",
            "Analyze how the author develops a central idea.",
            "1",
            "1,2",
            "",
            "",
            "4",
            "6",
            "500",
            "900",
            "claim, textual evidence",
            "",
            "",
        ],
    )

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
    assert assignment["schema_version"] == "2"
    assert assignment["writing_type"] == "literary_analysis"
    assert assignment["student_prompt"] == (
        "Analyze how the author develops a central idea."
    )
    assert assignment["focus_standard_ids"] == [STANDARD_ID, SECOND_STANDARD_ID]
    assert assignment["review_unit"] == {
        "type": "paragraph",
        "singular_label": "paragraph",
        "plural_label": "paragraphs",
    }
    assert assignment["rating_scale"]["scale_id"] == "standards_4_level"
    assert assignment["basic_requirements"] == {
        "paragraphs_min": 4,
        "paragraphs_max": 6,
        "word_count_min": 500,
        "word_count_max": 900,
        "required_elements": ["claim", "textual evidence"],
    }
    assert assignment["minimum_requirement_policy"] == {
        "allow_return_without_full_review": True,
    }
    assert "tagging_mode" not in assignment
    assert "focus_standards" not in assignment
    assert "rubric_id" not in assignment
    output = capsys.readouterr().out
    assert "Assignment creation requires an existing PDS Core standards profile." in (
        output
    )
    assert "Standards profiles found: 1" in output
    assert "Select Assignment Class" in output
    assert "Assignment Identity" in output
    assert "Writing Prompt" in output
    assert "Examples: literary_analysis, argument, research_paper, reflection" in output
    assert "Quillan will store lowercase snake_case" in output
    assert "Stored writing type: literary_analysis" in output
    assert "Standards Profile" in output
    assert "Focus Standard Selection" in output
    assert "Review Unit Setup" in output
    assert "Rating Scale Setup" in output
    assert "Basic Requirements" in output
    assert "Minimum Requirement Policy" in output
    assert "Review Assignment Before Saving" in output
    assert "Saved assignment:" in output
    assert "Focus standard IDs (2)" in output


def test_prompt_create_assignment_prerequisite_back_stops_before_class_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    prompts = _inputs(monkeypatch, ["b"])

    assert workflows.prompt_create_assignment() == 1
    output = capsys.readouterr().out
    assert "Assignment creation requires an existing PDS Core standards profile." in (
        output
    )
    assert "Select Assignment Class" not in output
    assert "Assignment title:" not in prompts


@pytest.mark.parametrize(
    ("selection", "expected_exception"),
    [("m", ReturnToMainMenu), ("q", QuitQuillan)],
)
def test_prompt_create_assignment_prerequisite_uses_shared_global_navigation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selection: str,
    expected_exception: type[Exception],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, [selection])

    with pytest.raises(expected_exception):
        workflows.prompt_create_assignment()


def test_prompt_create_assignment_no_profiles_stops_before_assignment_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library_without_profiles(tmp_path)
    original_files = {
        path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()
    }
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    prompts = _inputs(monkeypatch, ["b"])

    assert workflows.prompt_create_assignment() == 1
    output = capsys.readouterr().out
    assert "No standards profiles were found in this workspace." in output
    assert "Create or import standards and standards profiles in PDS Core" in output
    assert "1. Continue" not in output
    assert "Select Assignment Class" not in output
    assert "Assignment title:" not in prompts
    assert "Writing type:" not in prompts
    assert "Student-facing assignment prompt:" not in prompts
    assert not list(tmp_path.rglob("assignment.json"))
    assert {
        path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()
    } == original_files


def test_prompt_create_assignment_standards_load_failure_stops_before_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    standards_path = tmp_path / "standards" / "library.json"
    standards_path.parent.mkdir()
    standards_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    prompts = _inputs(monkeypatch, ["b"])

    assert workflows.prompt_create_assignment() == 1
    output = capsys.readouterr().out
    assert "could not load the PDS Core standards library" in output
    assert "Create or repair standards/profile data in PDS Core" in output
    assert "Error:" in output
    assert "1. Continue" not in output
    assert "Select Assignment Class" not in output
    assert "Assignment title:" not in prompts
    assert "Writing type:" not in prompts
    assert "Student-facing assignment prompt:" not in prompts
    assert not list(tmp_path.rglob("assignment.json"))


def test_prompt_create_assignment_default_rating_scale_has_four_unique_levels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "1",
            "1",
            "Argument Essay",
            "",
            "argument",
            "Write an argument.",
            "1",
            "1",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
    )

    assert workflows.prompt_create_assignment() == 0
    assignment = load_assignment_config(
        tmp_path
        / "classes"
        / "english_12_p3"
        / "assignments"
        / "argument_essay"
        / "assignment.json"
    )
    rating_scale = assignment["rating_scale"]
    levels = rating_scale["levels"]
    values = [level["value"] for level in levels]
    assert rating_scale["scale_id"] == "standards_4_level"
    assert len(levels) == 4
    assert len(values) == len(set(values))
    assert all(level["label"] for level in levels)
    assert all(level["description"] for level in levels)


def test_prompt_create_assignment_writes_declined_minimum_requirement_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "1",
            "1",
            "Argument Essay",
            "",
            "argument",
            "Write an argument.",
            "1",
            "1",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "n",
            "",
        ],
    )

    assert workflows.prompt_create_assignment() == 0
    assignment = load_assignment_config(
        tmp_path
        / "classes"
        / "english_12_p3"
        / "assignments"
        / "argument_essay"
        / "assignment.json"
    )
    assert assignment["minimum_requirement_policy"] == {
        "allow_return_without_full_review": False,
    }


def test_prompt_create_assignment_final_cancel_does_not_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "1",
            "1",
            "Argument Essay",
            "",
            "argument",
            "Write an argument.",
            "1",
            "1",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "n",
        ],
    )

    assert workflows.prompt_create_assignment() == 0
    assert not list(tmp_path.rglob("assignment.json"))
    assert "Canceled: assignment was not saved." in capsys.readouterr().out


def test_prompt_create_assignment_does_not_overwrite_without_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    original = _assignment(assignment_id="argument_essay")
    original_path = workflows.write_assignment_config(
        tmp_path,
        "english_12_p3",
        original,
    )
    original_bytes = original_path.read_bytes()
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "1",
            "1",
            "Argument Essay",
            "",
            "argument",
            "Write a new argument.",
            "1",
            "1",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "nope",
        ],
    )

    assert workflows.prompt_create_assignment() == 1
    assert original_path.read_bytes() == original_bytes
    assert "existing assignment was not changed" in capsys.readouterr().out


def test_prompt_create_assignment_overwrites_with_explicit_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    workflows.write_assignment_config(
        tmp_path,
        "english_12_p3",
        _assignment(assignment_id="argument_essay"),
    )
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "1",
            "1",
            "Argument Essay",
            "",
            "argument",
            "Write a replacement argument.",
            "1",
            "1",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "OVERWRITE",
        ],
    )

    assert workflows.prompt_create_assignment() == 0
    assignment = load_assignment_config(
        tmp_path
        / "classes"
        / "english_12_p3"
        / "assignments"
        / "argument_essay"
        / "assignment.json"
    )
    assert assignment["student_prompt"] == "Write a replacement argument."


def test_prompt_create_assignment_invalid_input_fails_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "1",
            "1",
            "Argument Essay",
            "bad id",
        ],
    )

    assert workflows.prompt_create_assignment() == 1
    output = capsys.readouterr().out
    assert "Error:" in output
    assert "Traceback" not in output
    assert not list(tmp_path.rglob("assignment.json"))


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

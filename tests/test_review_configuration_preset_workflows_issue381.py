"""Interactive preset-workflow acceptance for issue #381."""

from __future__ import annotations

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

from tests.menu_screen_recorder import MenuScreenRecorder

import quillan.assignment_workflows as assignment_workflows
import quillan.review_preset_workflows as preset_workflows
from quillan.menu_navigation import QuitQuillan, ReturnToMainMenu
from quillan.review_configuration_presets import (
    commit_review_configuration_preset,
    plan_review_configuration_preset_creation,
)
from quillan.work_paths import quillan_work_paths

STANDARD_ID = "njsls-ela:W.AW.11-12.1"


def _workspace(root: Path) -> None:
    write_class_roster(
        root,
        create_roster(
            "english_12_p3",
            [
                {
                    "student_id": "synthetic1",
                    "last_name": "Synthetic",
                    "first_name": "Avery",
                    "period": "3",
                }
            ],
        ),
    )
    write_workspace_standards_library(
        root,
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
            profiles=(
                StandardsProfile(
                    profile_id="synthetic_ela_11_12",
                    standards=(STANDARD_ID,),
                    title="Synthetic ELA 11-12",
                ),
            ),
        ),
    )


def _seed_preset(root: Path) -> Path:
    plan = plan_review_configuration_preset_creation(
        root,
        preset_id="literary_analysis_review",
        title="Literary Analysis Review",
        description="Reusable literary-analysis review.",
        writing_type="literary_analysis",
        standards_profile_id="synthetic_ela_11_12",
        focus_standard_ids=[STANDARD_ID],
        review_unit=assignment_workflows.default_review_unit(),
        rating_scale=assignment_workflows.default_rating_scale(),
        basic_requirements={
            "paragraphs_min": 4,
            "word_count_min": 500,
            "required_elements": ["claim", "textual evidence"],
        },
        minimum_requirement_policy={
            "allow_return_without_full_review": True
        },
    )
    return commit_review_configuration_preset(plan)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _workspace(tmp_path)
    monkeypatch.setattr(
        assignment_workflows, "resolve_workspace_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        preset_workflows, "resolve_workspace_root", lambda: tmp_path
    )
    return tmp_path


def test_assignment_preset_path_skips_reusable_configuration_prompts(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_preset(workspace)
    recorder = MenuScreenRecorder(
        [
            "1",  # standards prerequisite
            "1",  # class
            "Preset Essay",
            "",  # suggested assignment ID
            "1",  # use saved preset
            "1",  # select preset
            "1",  # accept reviewed preset
            "Analyze the text.",
            "",  # save assignment
        ]
    )
    recorder.install(monkeypatch)

    assert assignment_workflows.prompt_create_assignment() == 0

    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assignment_path = quillan_work_paths(
        workspace, "english_12_p3", "preset_essay"
    ).assignment_path
    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))

    assert assignment["writing_type"] == "literary_analysis"
    assert assignment["standards_profile_id"] == "synthetic_ela_11_12"
    assert assignment["focus_standard_ids"] == [STANDARD_ID]
    assert assignment["basic_requirements"]["paragraphs_min"] == 4
    assert assignment["module_details"] == {}
    assert "preset_id" not in assignment

    prompts = tuple(item.prompt.strip() for item in recorder.prompts)
    reusable_prompts = (
        "Writing type:",
        "Select standards profile:",
        "Select Focus Standards by number, comma-separated:",
        "Use default paragraph review units? [Y/n]:",
        "Use default four-level standards scale? [Y/n]:",
        "paragraphs_min:",
        "paragraphs_max:",
        "word_count_min:",
        "word_count_max:",
        "required_elements, comma-separated:",
        (
            "Allow teacher to return work without full standards review if "
            "minimum requirements are unmet? [Y/n]:"
        ),
    )
    for prompt in reusable_prompts:
        assert prompt not in prompts

    assert any(
        "Review Saved Review Configuration" in screen.output
        and "Literary Analysis Review" in screen.output
        for screen in screens
    )
    assert any(
        "Review Assignment Before Saving" in screen.output
        and (
            "Review preset applied by value: "
            "Literary Analysis Review (literary_analysis_review)"
            in screen.output
        )
        and "Analyze the text." in screen.output
        for screen in screens
    )


def test_assignment_preset_review_back_cancels_without_assignment(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_preset(workspace)
    recorder = MenuScreenRecorder(
        [
            "1",
            "1",
            "Canceled Essay",
            "",
            "1",
            "1",
            "b",
        ]
    )
    recorder.install(monkeypatch)

    assert assignment_workflows.prompt_create_assignment() == 0

    assert not quillan_work_paths(
        workspace, "english_12_p3", "canceled_essay"
    ).work_root.exists()
    output = capsys.readouterr().out
    recorder.screens(output)
    assert "Canceled: assignment creation was not continued." in output


@pytest.mark.parametrize(
    ("selection", "exception"),
    (("m", ReturnToMainMenu), ("q", QuitQuillan)),
)
def test_assignment_review_configuration_uses_global_navigation(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    selection: str,
    exception: type[Exception],
) -> None:
    _seed_preset(workspace)
    recorder = MenuScreenRecorder(
        [
            "1",
            "1",
            "Navigation Essay",
            "",
            selection,
        ]
    )
    recorder.install(monkeypatch)

    with pytest.raises(exception):
        assignment_workflows.prompt_create_assignment()


def test_no_valid_presets_preserves_existing_manual_prompt_sequence(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = MenuScreenRecorder(
        [
            "1",
            "1",
            "Manual Essay",
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
        ]
    )
    recorder.install(monkeypatch)

    assert assignment_workflows.prompt_create_assignment() == 0

    prompts = tuple(item.prompt.strip() for item in recorder.prompts)
    assert "Select review configuration:" not in prompts
    assert "Writing type:" in prompts
    assert quillan_work_paths(
        workspace, "english_12_p3", "manual_essay"
    ).assignment_path.is_file()


def test_direct_teacher_preset_creation_uses_assignment_configuration_prompts(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = MenuScreenRecorder(
        [
            "argument_review",
            "Argument Review",
            "Reusable argument review.",
            "argument",
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
            "1",
        ]
    )
    recorder.install(monkeypatch)

    assert preset_workflows.prompt_create_review_configuration_preset() == 0

    path = (
        workspace
        / "shared"
        / "review_configuration_presets"
        / "argument_review.json"
    )
    preset = json.loads(path.read_text(encoding="utf-8"))
    assert preset["writing_type"] == "argument"
    assert preset["standards_profile_id"] == "synthetic_ela_11_12"
    assert preset["focus_standard_ids"] == [STANDARD_ID]
    assert preset["module_details"] == {}


def test_save_preset_from_exact_assignment_is_reviewed_before_commit(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignment = assignment_workflows.build_assignment_config(
        assignment_id="source_essay",
        title="Source Essay",
        class_id="english_12_p3",
        writing_type="argument",
        student_prompt="Write an argument.",
        standards_profile_id="synthetic_ela_11_12",
        focus_standard_ids=[STANDARD_ID],
        review_unit=assignment_workflows.default_review_unit(),
        rating_scale=assignment_workflows.default_rating_scale(),
        basic_requirements={"paragraphs_min": 3},
        minimum_requirement_policy={
            "allow_return_without_full_review": True
        },
    )
    assignment_workflows.write_assignment_config(
        workspace, "english_12_p3", assignment
    )
    recorder = MenuScreenRecorder(
        [
            "1",  # source class
            "1",  # source assignment
            "saved_source",
            "Saved Source",
            "Reusable source configuration.",
            "1",  # save after preview
        ]
    )
    recorder.install(monkeypatch)

    assert (
        preset_workflows.prompt_save_review_configuration_preset_from_assignment()
        == 0
    )

    path = (
        workspace
        / "shared"
        / "review_configuration_presets"
        / "saved_source.json"
    )
    assert path.is_file()
    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert any(
        "Review Preset Before Saving" in screen.output
        and "Source assignment: english_12_p3/source_essay" in screen.output
        and "Preset ID: saved_source" in screen.output
        for screen in screens
    )


def test_assignment_menu_exposes_preset_management_without_renumbering_existing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recorder = MenuScreenRecorder(["b"])
    recorder.install(monkeypatch)

    assert assignment_workflows.launch_assignment_menu() == 0

    screens = recorder.screens(capsys.readouterr().out)
    menu_screen = next(
        screen for screen in screens if "Assignment Management" in screen.output
    )
    assert "1. Create writing assignment" in menu_screen.output
    assert "2. Copy writing assignment" in menu_screen.output
    assert "7. Academic Result Publications" in menu_screen.output
    assert "8. Review Configuration Presets" in menu_screen.output

"""Direct CLI and assignment-application acceptance for #381 Slice 2."""

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

from quillan.cli import main
import quillan.cli_app.handlers.assignments as assignment_handler
import quillan.cli_app.handlers.review_presets as preset_handler
from quillan.review_configuration_presets import (
    build_review_configuration_preset,
    commit_review_configuration_preset,
    plan_review_configuration_preset_creation,
    review_configuration_preset_path,
)
from quillan.work_paths import quillan_work_paths

STANDARD_ID = "njsls-ela:W.AW.9-10.1"


def _workspace(root: Path) -> None:
    write_class_roster(
        root,
        create_roster(
            "english10_p2",
            [
                {
                    "student_id": "synthetic1",
                    "last_name": "Synthetic",
                    "first_name": "Avery",
                    "period": "2",
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
                    code="W.AW.9-10.1",
                    source="NJSLS",
                    short_name="Argument",
                    description="Write arguments.",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id="english10_profile",
                    standards=(STANDARD_ID,),
                    title="English 10",
                ),
            ),
        ),
    )


def _preset_args(*extra: str) -> list[str]:
    return [
        "review-preset",
        "create",
        "--preset-id",
        "literary_analysis_review",
        "--title",
        "Literary Analysis Review",
        "--description",
        "Reusable literary-analysis review.",
        "--writing-type",
        "literary_analysis",
        "--standards-profile-id",
        "english10_profile",
        "--focus-standard-ids",
        STANDARD_ID,
        "--paragraphs-min",
        "3",
        *extra,
    ]


def _assignment_preset_args(*extra: str) -> list[str]:
    return [
        "assignment",
        "create",
        "english10_p2",
        "new_analysis",
        "--title",
        "New Analysis",
        "--prompt",
        "Analyze the text.",
        "--preset-id",
        "literary_analysis_review",
        *extra,
    ]


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _workspace(tmp_path)
    monkeypatch.setattr(preset_handler, "resolve_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        assignment_handler, "resolve_workspace_root", lambda: tmp_path
    )
    return tmp_path


def _seed_preset(root: Path) -> Path:
    plan = plan_review_configuration_preset_creation(
        root,
        preset_id="literary_analysis_review",
        title="Literary Analysis Review",
        description="Reusable literary-analysis review.",
        writing_type="literary_analysis",
        standards_profile_id="english10_profile",
        focus_standard_ids=[STANDARD_ID],
        review_unit={
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        rating_scale={
            "scale_id": "standards_4_level",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Limited."},
                {"value": 2, "label": "Approaching", "description": "Partial."},
                {"value": 3, "label": "Meeting", "description": "Clear."},
                {"value": 4, "label": "Exceeding", "description": "Strong."},
            ],
        },
        basic_requirements={"paragraphs_min": 3},
        minimum_requirement_policy={
            "allow_return_without_full_review": True
        },
    )
    return commit_review_configuration_preset(plan)


def test_review_preset_help_surface() -> None:
    with pytest.raises(SystemExit) as error:
        main(["review-preset", "--help"])
    assert error.value.code == 0


def test_review_preset_create_dry_run_is_non_mutating(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(_preset_args("--dry-run")) == 0
    assert not review_configuration_preset_path(
        workspace, "literary_analysis_review"
    ).exists()
    output = capsys.readouterr().out
    assert "Review-configuration preset plan:" in output
    assert "No files were written." in output


def test_review_preset_create_show_validate_and_collision(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(_preset_args("--yes")) == 0
    path = review_configuration_preset_path(
        workspace, "literary_analysis_review"
    )
    original = path.read_bytes()
    assert main(
        ["review-preset", "show", "--preset-id", "literary_analysis_review"]
    ) == 0
    assert main(
        ["review-preset", "validate", "--preset-id", "literary_analysis_review"]
    ) == 0
    assert main(_preset_args("--yes")) == 1
    assert path.read_bytes() == original
    output = capsys.readouterr().out
    assert "Literary Analysis Review (literary_analysis_review)" in output
    assert "Valid review-configuration preset:" in output


def test_review_preset_create_requires_confirmation(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(_preset_args()) == 1
    assert "use --yes to confirm or --dry-run" in capsys.readouterr().err


def test_review_preset_list_reports_valid_invalid_and_stale(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_preset(workspace)
    directory = workspace / "shared" / "review_configuration_presets"
    (directory / "broken.json").write_text("{bad", encoding="utf-8")

    stale = json.loads(
        (directory / "literary_analysis_review.json").read_text(
            encoding="utf-8"
        )
    )
    stale["preset_id"] = "stale"
    stale["title"] = "Stale"
    stale["standards_profile_id"] = "missing_profile"
    (directory / "stale.json").write_text(
        json.dumps(stale, indent=2) + "\n",
        encoding="utf-8",
    )

    assert main(["review-preset", "list"]) == 0
    output = capsys.readouterr().out
    assert "Literary Analysis Review (literary_analysis_review): valid" in output
    assert "broken: invalid" in output
    assert "Stale (stale): stale" in output


def test_assignment_create_from_preset_materializes_snapshot(
    workspace: Path,
) -> None:
    preset_path = _seed_preset(workspace)
    assert main(_assignment_preset_args("--yes")) == 0

    assignment_path = quillan_work_paths(
        workspace, "english10_p2", "new_analysis"
    ).assignment_path
    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))
    assert assignment["writing_type"] == "literary_analysis"
    assert assignment["standards_profile_id"] == "english10_profile"
    assert assignment["focus_standard_ids"] == [STANDARD_ID]
    assert assignment["basic_requirements"] == {"paragraphs_min": 3}
    assert assignment["title"] == "New Analysis"
    assert assignment["student_prompt"] == "Analyze the text."
    assert assignment["module_details"] == {}
    assert "preset_id" not in assignment

    preset_path.unlink()
    assert json.loads(assignment_path.read_text(encoding="utf-8")) == assignment


def test_assignment_create_from_preset_dry_run_writes_nothing(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_preset(workspace)
    assert main(_assignment_preset_args("--dry-run")) == 0
    assert not quillan_work_paths(
        workspace, "english10_p2", "new_analysis"
    ).work_root.exists()
    output = capsys.readouterr().out
    assert (
        "Review preset: Literary Analysis Review "
        "(literary_analysis_review)" in output
    )
    assert "No files were written." in output


@pytest.mark.parametrize(
    "conflict",
    (
        ("--writing-type", "other"),
        ("--standards-profile-id", "other_profile"),
        ("--focus-standard-ids", STANDARD_ID),
        ("--paragraphs-min", "4"),
        ("--review-unit-type", "section"),
        ("--allow-return-without-full-review", "false"),
    ),
)
def test_assignment_preset_mode_rejects_manual_configuration_flags(
    workspace: Path,
    conflict: tuple[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_preset(workspace)
    assert main(_assignment_preset_args(*conflict, "--dry-run")) == 1
    assert "cannot be combined with manual review-configuration options" in (
        capsys.readouterr().err
    )


def test_assignment_manual_mode_still_requires_review_fields(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = [
        "assignment",
        "create",
        "english10_p2",
        "manual",
        "--title",
        "Manual",
        "--prompt",
        "Write.",
        "--dry-run",
    ]
    assert main(argv) == 1
    assert "--writing-type" in capsys.readouterr().err


def test_assignment_manual_mode_keeps_prior_defaults(
    workspace: Path,
) -> None:
    argv = [
        "assignment",
        "create",
        "english10_p2",
        "manual",
        "--title",
        "Manual",
        "--prompt",
        "Write.",
        "--writing-type",
        "literary_analysis",
        "--standards-profile-id",
        "english10_profile",
        "--focus-standard-ids",
        STANDARD_ID,
        "--yes",
    ]
    assert main(argv) == 0
    assignment = json.loads(
        quillan_work_paths(
            workspace, "english10_p2", "manual"
        ).assignment_path.read_text(encoding="utf-8")
    )
    assert assignment["review_unit"]["type"] == "paragraph"
    assert assignment["minimum_requirement_policy"] == {
        "allow_return_without_full_review": True
    }


def test_assignment_create_missing_or_stale_preset_fails_before_write(
    workspace: Path,
) -> None:
    assert main(_assignment_preset_args("--dry-run")) == 1
    assert not quillan_work_paths(
        workspace, "english10_p2", "new_analysis"
    ).work_root.exists()

    preset = build_review_configuration_preset(
        preset_id="literary_analysis_review",
        title="Literary Analysis Review",
        description="Stale.",
        writing_type="literary_analysis",
        standards_profile_id="missing_profile",
        focus_standard_ids=[STANDARD_ID],
        review_unit={
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        rating_scale={
            "scale_id": "single",
            "levels": [
                {"value": 1, "label": "One", "description": "One."}
            ],
        },
        basic_requirements={},
        minimum_requirement_policy={
            "allow_return_without_full_review": True
        },
    )
    path = review_configuration_preset_path(
        workspace, "literary_analysis_review"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preset, indent=2) + "\n", encoding="utf-8")

    assert main(_assignment_preset_args("--dry-run")) == 1
    assert not quillan_work_paths(
        workspace, "english10_p2", "new_analysis"
    ).work_root.exists()

"""Final adversarial acceptance coverage for Quillan issue #381."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

from quillan.cli import main
import quillan.assignment_workflows as assignment_workflows
import quillan.cli_app.handlers.assignments as assignment_handler
import quillan.cli_app.handlers.review_presets as preset_handler
from quillan.review_configuration_presets import (
    commit_review_configuration_preset,
    plan_review_configuration_preset_creation,
    require_current_review_configuration_preset_matches,
)
from quillan.work_paths import quillan_work_paths

STANDARD_ID = "njsls-ela:W.AW.11-12.1"


def _write_workspace(root: Path) -> None:
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
    _write_standards(root)


def _write_standards(root: Path, *, with_profile: bool = True) -> None:
    profiles = (
        (
            StandardsProfile(
                profile_id="synthetic_ela_11_12",
                standards=(STANDARD_ID,),
                title="Synthetic ELA 11-12",
            ),
        )
        if with_profile
        else ()
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
            profiles=profiles,
        ),
        overwrite=True,
    )


def _seed_preset(root: Path) -> Path:
    plan = plan_review_configuration_preset_creation(
        root,
        preset_id="argument_review",
        title="Argument Review",
        description="Reusable argument review configuration.",
        writing_type="argument",
        standards_profile_id="synthetic_ela_11_12",
        focus_standard_ids=[STANDARD_ID],
        review_unit=assignment_workflows.default_review_unit(),
        rating_scale=assignment_workflows.default_rating_scale(),
        basic_requirements={"paragraphs_min": 4},
        minimum_requirement_policy={
            "allow_return_without_full_review": True
        },
    )
    return commit_review_configuration_preset(plan)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path)
    monkeypatch.setattr(
        assignment_handler, "resolve_workspace_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        preset_handler, "resolve_workspace_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        assignment_workflows, "resolve_workspace_root", lambda: tmp_path
    )
    return tmp_path


def _preset_assignment_args(*extra: str) -> list[str]:
    return [
        "assignment",
        "create",
        "english_12_p3",
        "preset_assignment",
        "--title",
        "Preset Assignment",
        "--prompt",
        "Write an argument.",
        "--preset-id",
        "argument_review",
        *extra,
    ]


def test_show_can_inspect_stale_preset_but_validate_fails(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _seed_preset(workspace)
    preset = json.loads(path.read_text(encoding="utf-8"))
    preset["standards_profile_id"] = "removed_profile"
    path.write_text(json.dumps(preset, indent=2) + "\n", encoding="utf-8")

    assert main(
        ["review-preset", "show", "--preset-id", "argument_review"]
    ) == 0
    shown = capsys.readouterr()
    assert "Status: stale" in shown.out
    assert "removed_profile" in shown.out

    assert main(
        ["review-preset", "validate", "--preset-id", "argument_review"]
    ) == 1
    validated = capsys.readouterr()
    assert "validation failed" in validated.err


def test_cli_assignment_fails_if_reviewed_preset_changes_before_write(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _seed_preset(workspace)
    original_check = require_current_review_configuration_preset_matches

    def mutate_then_check(root: Path, reviewed: dict[str, Any]) -> None:
        current = json.loads(path.read_text(encoding="utf-8"))
        current["title"] = "Changed After Planning"
        path.write_text(
            json.dumps(current, indent=2) + "\n",
            encoding="utf-8",
        )
        original_check(root, reviewed)

    monkeypatch.setattr(
        assignment_handler,
        "require_current_review_configuration_preset_matches",
        mutate_then_check,
    )

    assert main(_preset_assignment_args("--yes")) == 1
    assert not quillan_work_paths(
        workspace, "english_12_p3", "preset_assignment"
    ).work_root.exists()


@pytest.mark.parametrize("mutation", ("preset", "standards"))
def test_interactive_assignment_rechecks_preset_after_final_review(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    path = _seed_preset(workspace)

    def authorize_and_mutate(_prompt: str, *, default: bool) -> bool:
        assert default is True
        if mutation == "preset":
            current = json.loads(path.read_text(encoding="utf-8"))
            current["description"] = "Changed after teacher review."
            path.write_text(
                json.dumps(current, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            _write_standards(workspace, with_profile=False)
        return True

    monkeypatch.setattr(
        assignment_workflows, "_prompt_yes_no", authorize_and_mutate
    )
    recorder = MenuScreenRecorder(
        [
            "1",  # standards prerequisite
            "1",  # class
            "Preset Assignment",
            "",  # suggested ID
            "1",  # saved preset path
            "1",  # preset
            "1",  # accept preset
            "Write an argument.",
        ]
    )
    recorder.install(monkeypatch)

    assert assignment_workflows.prompt_create_assignment() == 1
    assert not quillan_work_paths(
        workspace, "english_12_p3", "preset_assignment"
    ).work_root.exists()


def test_preset_operations_do_not_touch_reusable_feedback_comment_state(
    workspace: Path,
) -> None:
    comments = workspace / "shared" / "focus_standard_comments"
    comments.mkdir(parents=True)
    comment_path = comments / "teacher_comments.json"
    comment_bytes = b'{"synthetic":"comment-state-must-remain-untouched"}\n'
    comment_path.write_bytes(comment_bytes)

    _seed_preset(workspace)
    assert main(_preset_assignment_args("--yes")) == 0

    assert comment_path.read_bytes() == comment_bytes


def test_review_preset_create_yes_and_dry_run_are_mutually_exclusive(
    workspace: Path,
) -> None:
    argv = [
        "review-preset",
        "create",
        "--preset-id",
        "argument_review",
        "--title",
        "Argument Review",
        "--description",
        "Reusable.",
        "--writing-type",
        "argument",
        "--standards-profile-id",
        "synthetic_ela_11_12",
        "--focus-standard-ids",
        STANDARD_ID,
        "--yes",
        "--dry-run",
    ]
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 2


def test_preset_backed_assignment_preserves_existing_overwrite_boundary(
    workspace: Path,
) -> None:
    _seed_preset(workspace)
    assert main(_preset_assignment_args("--yes")) == 0
    path = quillan_work_paths(
        workspace, "english_12_p3", "preset_assignment"
    ).assignment_path
    original = path.read_bytes()

    assert main(_preset_assignment_args("--overwrite", "--dry-run")) == 1
    assert path.read_bytes() == original

    assert main(_preset_assignment_args("--overwrite", "--yes")) == 0
    assert path.is_file()

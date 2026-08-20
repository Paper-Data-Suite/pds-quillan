"""Direct CLI acceptance for issue #380 assignment copying."""

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
import quillan.cli_app.handlers.assignment_copy as handler
import quillan.assignment_workflows as workflows
from quillan.work_paths import quillan_work_paths

STANDARD_ID = "njsls-ela:W.AW.9-10.1"


def _write_roster(root: Path, class_id: str) -> None:
    write_class_roster(
        root,
        create_roster(
            class_id,
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


def _workspace(root: Path) -> None:
    _write_roster(root, "english10_p2")
    _write_roster(root, "english10_p4")
    _write_roster(root, "english10_p5")
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
    source = workflows.build_assignment_config(
        assignment_id="literary_analysis",
        title="Literary Analysis",
        class_ids=["english10_p2"],
        writing_type="literary_analysis",
        student_prompt="Analyze the text.",
        standards_profile_id="english10_profile",
        focus_standard_ids=[STANDARD_ID],
        review_unit=workflows.default_review_unit(),
        rating_scale=workflows.default_rating_scale(),
        basic_requirements={"paragraphs_min": 3},
        minimum_requirement_policy={"allow_return_without_full_review": True},
        created_at="2026-08-01T12:00:00+00:00",
    )
    workflows.write_assignment_config(root, "english10_p2", source)


def _copy_args(*extra: str) -> list[str]:
    return [
        "assignment",
        "copy",
        "--source-class-id",
        "english10_p2",
        "--source-assignment-id",
        "literary_analysis",
        "--target-class-id",
        "english10_p4",
        "--assignment-id",
        "literary_analysis",
        *extra,
    ]


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _workspace(tmp_path)
    monkeypatch.setattr(handler, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def test_assignment_copy_help_surface(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["assignment", "copy", "--help"])
    assert error.value.code == 0
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "--source-class-id" in output
    assert "--target-class-id" in output
    assert "--prompt-file" in output
    assert "--dry-run" in output
    assert "--overwrite" not in output


def test_assignment_copy_dry_run_is_non_mutating(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = quillan_work_paths(
        workspace, "english10_p4", "literary_analysis"
    ).work_root

    assert main(_copy_args("--dry-run")) == 0

    assert not target.exists()
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "Assignment copy plan:" in output
    assert "No files were written." in output


def test_assignment_copy_yes_reuses_config_and_allows_overrides(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(
        _copy_args(
            "--title",
            "Literary Analysis - Period 4",
            "--prompt",
            "Analyze a different text.",
            "--yes",
        )
    ) == 0

    target_path = quillan_work_paths(
        workspace, "english10_p4", "literary_analysis"
    ).assignment_path
    target = json.loads(target_path.read_text(encoding="utf-8"))
    assert target["title"] == "Literary Analysis - Period 4"
    assert target["student_prompt"] == "Analyze a different text."
    assert target["writing_type"] == "literary_analysis"
    assert target["focus_standard_ids"] == [STANDARD_ID]
    assert target["basic_requirements"] == {"paragraphs_min": 3}
    assert target["class_ids"] == ["english10_p4"]
    assert target["module_details"] == {}
    assert "Created copied assignment:" in (
        lambda captured: captured.out + captured.err
    )(capsys.readouterr())


def test_assignment_copy_supports_multiple_target_classes(workspace: Path) -> None:
    argv = _copy_args("--target-class-id", "english10_p5", "--yes")
    assert main(argv) == 0

    p4 = quillan_work_paths(
        workspace, "english10_p4", "literary_analysis"
    ).assignment_path
    p5 = quillan_work_paths(
        workspace, "english10_p5", "literary_analysis"
    ).assignment_path
    assert json.loads(p4.read_text(encoding="utf-8"))["class_ids"] == [
        "english10_p4",
        "english10_p5",
    ]
    assert p4.read_bytes() == p5.read_bytes()


def test_assignment_copy_prompt_file_preserves_exact_text(
    workspace: Path,
    tmp_path: Path,
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Line one.\nLine two.\n", encoding="utf-8")

    assert main(_copy_args("--prompt-file", str(prompt_file), "--yes")) == 0

    target = json.loads(
        quillan_work_paths(
            workspace, "english10_p4", "literary_analysis"
        ).assignment_path.read_text(encoding="utf-8")
    )
    assert target["student_prompt"] == "Line one.\nLine two.\n"


def test_assignment_copy_requires_confirmation(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(_copy_args()) == 1
    assert not quillan_work_paths(
        workspace, "english10_p4", "literary_analysis"
    ).work_root.exists()
    assert "use --yes to confirm or --dry-run" in (
        lambda captured: captured.out + captured.err
    )(capsys.readouterr())


def test_assignment_copy_collision_never_overwrites(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(_copy_args("--yes")) == 0
    target_path = quillan_work_paths(
        workspace, "english10_p4", "literary_analysis"
    ).assignment_path
    original = target_path.read_bytes()

    assert main(_copy_args("--yes")) == 1

    assert target_path.read_bytes() == original
    assert "already contains assignment state" in (
        lambda captured: captured.out + captured.err
    )(capsys.readouterr())


def test_assignment_copy_has_no_overwrite_argument() -> None:
    with pytest.raises(SystemExit) as error:
        main(_copy_args("--overwrite", "--yes"))
    assert error.value.code == 2


def test_assignment_copy_prompt_options_are_mutually_exclusive(
    workspace: Path,
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            _copy_args(
                "--prompt",
                "Inline prompt.",
                "--prompt-file",
                "prompt.txt",
                "--dry-run",
            )
        )
    assert error.value.code == 2


def test_assignment_copy_yes_and_dry_run_are_mutually_exclusive(
    workspace: Path,
) -> None:
    with pytest.raises(SystemExit) as error:
        main(_copy_args("--yes", "--dry-run"))
    assert error.value.code == 2


def test_assignment_copy_cli_rejects_exact_source_as_destination(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = [
        "assignment",
        "copy",
        "--source-class-id",
        "english10_p2",
        "--source-assignment-id",
        "literary_analysis",
        "--target-class-id",
        "english10_p2",
        "--assignment-id",
        "literary_analysis",
        "--yes",
    ]

    assert main(argv) == 1

    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "cannot be its own copy destination" in output
    assert "Traceback" not in output


def test_assignment_copy_cli_rejects_missing_source(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = [
        "assignment",
        "copy",
        "--source-class-id",
        "english10_p2",
        "--source-assignment-id",
        "missing_assignment",
        "--target-class-id",
        "english10_p4",
        "--assignment-id",
        "copy_target",
        "--yes",
    ]

    assert main(argv) == 1

    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "Could not load source assignment" in output
    assert "Traceback" not in output


def test_assignment_copy_cli_rejects_missing_target_roster(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = [
        "assignment",
        "copy",
        "--source-class-id",
        "english10_p2",
        "--source-assignment-id",
        "literary_analysis",
        "--target-class-id",
        "missing_class",
        "--assignment-id",
        "copy_target",
        "--yes",
    ]

    assert main(argv) == 1

    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "not roster-ready" in output
    assert "Traceback" not in output


def test_assignment_copy_cli_rejects_duplicate_target_class(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(
        _copy_args(
            "--target-class-id",
            "english10_p4",
            "--yes",
        )
    ) == 1

    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "must be unique" in output
    assert "Traceback" not in output

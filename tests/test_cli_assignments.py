"""Tests for direct canonical assignment CLI commands."""

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
import quillan.cli_app.handlers.assignments as handlers

STANDARD_ID = "njsls-ela:W.AW.9-10.1"
OTHER_STANDARD_ID = "njsls-ela:RL.CR.9-10.1"


def _workspace(root: Path) -> None:
    write_class_roster(
        root,
        create_roster(
            "english10_p2",
            [
                {
                    "student_id": "student1",
                    "last_name": "Doe",
                    "first_name": "A",
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
                StandardDefinition(
                    standard_id=OTHER_STANDARD_ID,
                    code="RL.CR.9-10.1",
                    source="NJSLS",
                    short_name="Reading",
                    description="Read closely.",
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


def _args(*extra: str) -> list[str]:
    return [
        "assignment", "create", "english10_p2", "literary_analysis",
        "--title", "Literary Analysis", "--writing-type", "Literary Analysis",
        "--prompt", "Analyze the text.", "--standards-profile-id",
        "english10_profile", "--focus-standard-ids", STANDARD_ID, *extra,
    ]


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _workspace(tmp_path)
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def test_assignment_help_surface(capsys: pytest.CaptureFixture[str]) -> None:
    for argv, expected in [
        (["--help"], "assignment"),
        (["assignment", "--help"], "create"),
        (["assignment", "create", "--help"], "--prompt-file"),
        (["assignment", "show", "--help"], "class_id"),
        (["assignment", "validate", "--help"], "assignment_id"),
    ]:
        with pytest.raises(SystemExit) as error:
            main(argv)
        assert error.value.code == 0
        assert expected in capsys.readouterr().out


def test_create_show_validate_and_overwrite_safety(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_args("--yes", "--paragraphs-min", "4")) == 0
    path = workspace / "classes/english10_p2/assignments/literary_analysis/assignment.json"
    assignment = json.loads(path.read_text(encoding="utf-8"))
    assert assignment["schema_version"] == "2"
    assert assignment["module"] == "quillan"
    assert assignment["class_ids"] == ["english10_p2"]
    assert assignment["writing_type"] == "literary_analysis"
    assert assignment["basic_requirements"] == {"paragraphs_min": 4}
    assert len(assignment["rating_scale"]["levels"]) == 4
    original = path.read_bytes()
    assert main(_args("--yes")) == 1
    assert path.read_bytes() == original
    assert main(_args("--overwrite")) == 1
    assert path.read_bytes() == original
    assert main(["assignment", "show", "english10_p2", "literary_analysis"]) == 0
    assert main(["assignment", "validate", "english10_p2", "literary_analysis"]) == 0
    output = capsys.readouterr().out
    assert "Assignment config is valid." in output
    assert "Valid canonical assignment:" in output


def test_dry_run_and_prompt_file_preserve_content(
    workspace: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_args("--dry-run")) == 0
    target = workspace / "classes/english10_p2/assignments/literary_analysis"
    assert not target.exists()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Line one.\nLine two.\n", encoding="utf-8")
    argv = _args("--yes")
    prompt_index = argv.index("--prompt")
    argv[prompt_index : prompt_index + 2] = ["--prompt-file", str(prompt_file)]
    assert main(argv) == 0
    assignment = json.loads((target / "assignment.json").read_text(encoding="utf-8"))
    assert assignment["student_prompt"] == "Line one.\nLine two.\n"
    assert "No files were written." in capsys.readouterr().out


def test_invalid_standards_and_path_identity_fail_cleanly(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = _args("--dry-run")
    bad[bad.index(STANDARD_ID)] = OTHER_STANDARD_ID
    assert main(bad) == 1
    assert "assignment was not created" in capsys.readouterr().out
    assert main(_args("--yes")) == 0
    path = workspace / "classes/english10_p2/assignments/literary_analysis/assignment.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["assignment_id"] = "different_id"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["assignment", "validate", "english10_p2", "literary_analysis"]) == 1
    assert "Path assignment_id" in capsys.readouterr().out

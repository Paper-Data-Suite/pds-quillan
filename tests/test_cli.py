"""Tests for the Quillan command-line interface."""

from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path

from pds_core.workspace import WorkspaceRootError, WorkspaceStatus
import pytest

import quillan.cli
from quillan.cli import main


def _menu_input(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str],
) -> None:
    response_iterator: Iterator[str] = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(response_iterator)
        except StopIteration as error:
            raise AssertionError(
                "Menu requested more input than the test provided."
            ) from error

    monkeypatch.setattr("builtins.input", fake_input)


def test_cli_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])

    captured = capsys.readouterr()

    assert error.value.code == 0
    assert "Quillan: standards-based writing evidence capture" in captured.out
    assert "validate-standards" in captured.out
    assert "workspace" in captured.out
    assert "menu" in captured.out

    with pytest.raises(SystemExit) as workspace_error:
        main(["workspace", "--help"])

    workspace_help = capsys.readouterr()

    assert workspace_error.value.code == 0
    assert "show" in workspace_help.out


def test_cli_without_command_preserves_help_only_behavior(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "Quillan: standards-based writing evidence capture" in output
    assert "Launch the teacher-facing interactive menu" in output


def test_cli_validates_standards_profile(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    profile_path = tmp_path / "standards.json"
    profile_data = {
        "profile_id": "english_12_njsls_synthetic",
        "subject": "English Language Arts",
        "course": "English 12",
        "standards": [
            {
                "code": "W.AW.11-12.1",
                "short_name": "Argument Writing",
                "description": "Write arguments using claims, reasoning, and evidence.",
                "comments": [
                    {
                        "comment_id": "clear_claim",
                        "label": "Clear claim",
                        "polarity": "positive",
                    }
                ],
            }
        ],
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    main(["validate-standards", str(profile_path)])

    captured = capsys.readouterr()

    assert "Valid standards profile: english_12_njsls_synthetic" in captured.out


def test_cli_reports_invalid_standards_profile(tmp_path: Path) -> None:
    profile_path = tmp_path / "standards.json"
    profile_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        main(["validate-standards", str(profile_path)])

    assert "Invalid standards profile" in str(error.value)


def test_cli_validates_assignment_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = {
        "assignment_id": "villainy_final_essay_synthetic",
        "title": "Villainy Final Essay",
        "class_ids": ["english12_period3_synthetic"],
        "writing_type": "literary argument essay",
        "standards_profile_id": "english_12_njsls_synthetic",
        "tagging_mode": "focus",
        "focus_standards": [
            "W.AW.11-12.1",
            "W.WP.11-12.4",
        ],
        "basic_requirements": {
            "paragraphs_min": 4,
            "paragraphs_max": 6,
            "word_count_min": 500,
            "required_elements": [
                "thesis",
                "textual evidence",
                "comparative reasoning",
            ],
        },
        "rubric_id": "argument_essay_4pt_synthetic",
    }
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    main(["validate-assignment", str(assignment_path)])

    captured = capsys.readouterr()

    assert "Valid assignment config: villainy_final_essay_synthetic" in captured.out


def test_cli_reports_invalid_assignment_config(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        main(["validate-assignment", str(assignment_path)])

    assert "Invalid assignment config" in str(error.value)


def test_workspace_show_uses_pds_core_status(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = WorkspaceStatus(
        root=tmp_path / "active-workspace",
        source="saved_config",
        exists=True,
        is_dir=True,
        is_writable=True,
        config_path=tmp_path / "config.json",
        default_root=tmp_path / "default-workspace",
    )
    calls = 0

    def inspect_workspace_root() -> WorkspaceStatus:
        nonlocal calls
        calls += 1
        return status

    monkeypatch.setattr(quillan.cli, "inspect_workspace_root", inspect_workspace_root)

    result = main(["workspace", "show"])
    captured = capsys.readouterr()

    assert result == 0
    assert calls == 1
    assert str(status.root) in captured.out
    assert status.source in captured.out
    assert str(status.config_path) in captured.out
    assert str(status.default_root) in captured.out


def test_workspace_show_reports_status_fields(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = WorkspaceStatus(
        root=tmp_path / "workspace",
        source="default",
        exists=False,
        is_dir=False,
        is_writable=True,
        config_path=tmp_path / "config.json",
        default_root=tmp_path / "workspace",
    )
    monkeypatch.setattr(
        quillan.cli,
        "inspect_workspace_root",
        lambda: status,
    )

    assert main(["workspace", "show"]) == 0
    output = capsys.readouterr().out

    assert "Exists:\nno" in output
    assert "Directory:\nno" in output
    assert "Writable:\nyes" in output


def test_workspace_show_rejects_extra_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["workspace", "show", "extra"])

    captured = capsys.readouterr()

    assert error.value.code != 0
    assert "usage:" in captured.err


def test_workspace_show_reports_workspace_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_workspace_error() -> WorkspaceStatus:
        raise WorkspaceRootError("bad workspace")

    monkeypatch.setattr(
        quillan.cli,
        "inspect_workspace_root",
        raise_workspace_error,
    )

    assert main(["workspace", "show"]) != 0
    assert "Error: bad workspace" in capsys.readouterr().out


def test_menu_dispatch_displays_options_and_exits(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out

    assert "Quillan" in output
    assert "Assignment Management" in output
    assert "Roster Management" in output
    assert "Printable Response Pages" in output
    assert "Workspace Settings" in output
    assert "Help" in output
    assert "Exit" in output
    assert "Goodbye." in output


def test_menu_help_explains_teacher_control_and_safe_data(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["5", "", "6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out

    assert "local-first, teacher-controlled" in output
    assert "Teacher judgment remains primary" in output
    assert "not automated grading software" in output
    assert "synthetic data only" in output
    assert "Do not commit or post real student data" in output
    assert "quillan validate-standards" in output
    assert "quillan menu" in output


@pytest.mark.parametrize(
    ("selection", "expected_message"),
    [
        ("1", "Assignment management workflows are not implemented yet."),
        ("2", "Roster management workflows are not implemented yet."),
        (
            "3",
            "teacher-facing menu workflow is not implemented yet.",
        ),
    ],
)
def test_unsupported_menu_sections_are_honest_placeholders(
    selection: str,
    expected_message: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, [selection, "", "6"])

    assert main(["menu"]) == 0
    assert expected_message in capsys.readouterr().out


def test_workspace_menu_reuses_workspace_show_handler(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handle_workspace_show() -> int:
        nonlocal calls
        calls += 1
        print("Synthetic workspace status")
        return 0

    monkeypatch.setattr(quillan.cli, "_handle_workspace_show", handle_workspace_show)
    _menu_input(monkeypatch, ["4", "1", "", "2", "6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out

    assert calls == 1
    assert "Workspace Settings" in output
    assert "Show current workspace" in output
    assert "Synthetic workspace status" in output


def test_menu_handles_keyboard_interrupt(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupt(_prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)

    assert main(["menu"]) == 0
    assert "Exiting Quillan." in capsys.readouterr().out

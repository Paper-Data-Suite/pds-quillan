"""Tests for the Quillan command-line interface."""

from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path

from pds_core.workspace import WorkspaceRootError, WorkspaceStatus
import pytest

from quillan.cli import main
import quillan.cli_app.handlers.workspace as cli_workspace


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


@pytest.mark.parametrize("help_flag", ["--help", "-h"])
def test_cli_prints_help(
    help_flag: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main([help_flag])

    captured = capsys.readouterr()

    assert error.value.code == 0
    assert "Quillan: standards-based writing evidence capture" in captured.out
    assert "validate-standards" not in captured.out
    assert "workspace" in captured.out
    assert "menu" in captured.out

    with pytest.raises(SystemExit) as workspace_error:
        main(["workspace", "--help"])

    workspace_help = capsys.readouterr()

    assert workspace_error.value.code == 0
    assert "show" in workspace_help.out
    assert "set" in workspace_help.out
    assert "validate" in workspace_help.out
    assert "reset" in workspace_help.out


def test_cli_without_command_displays_menu_options_and_exits(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["6"])

    assert main([]) == 0

    output = capsys.readouterr().out
    assert "Quillan" in output
    assert "\033[32mQuillan\033[0m" in output
    assert "1. Assignment Management" in output
    assert "2. Review Student Work" in output
    assert "3. Roster Management" in output
    assert "4. Workspace Settings" in output
    assert "5. Help" in output
    assert "6. Exit" in output
    assert "Printable Response Pages" not in output
    assert "Scan Intake / Route Paper Responses" not in output
    assert "Review Materials" not in output
    assert "Goodbye." in output


def test_cli_validates_assignment_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": "villainy_final_essay_synthetic",
        "title": "Villainy Final Essay",
        "class_ids": ["english12_period3_synthetic"],
        "writing_type": "literary argument essay",
        "student_prompt": "Rank villains using evidence from the texts.",
        "standards_profile_id": "english_12_njsls_synthetic",
        "focus_standard_ids": [
            "njsls-ela:W.AW.11-12.1",
            "njsls-ela:W.WP.11-12.4",
        ],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_2_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                }
            ],
        },
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
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
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

    monkeypatch.setattr(
        cli_workspace, "inspect_workspace_root", inspect_workspace_root
    )

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
        cli_workspace,
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
        cli_workspace,
        "inspect_workspace_root",
        raise_workspace_error,
    )

    assert main(["workspace", "show"]) != 0
    assert "Error: bad workspace" in capsys.readouterr().out


def test_workspace_set_validates_and_saves_shared_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_root = tmp_path / "requested-workspace"
    calls: list[tuple[str, Path]] = []

    def ensure(path: str | Path) -> Path:
        root = Path(path)
        root.mkdir(parents=True)
        calls.append(("ensure", root))
        return root

    def save(path: str | Path) -> Path:
        root = Path(path)
        calls.append(("save", root))
        return root

    monkeypatch.setattr(cli_workspace, "ensure_workspace_root", ensure)
    monkeypatch.setattr(cli_workspace, "save_workspace_root", save)

    assert main(["workspace", "set", str(requested_root)]) == 0
    output = capsys.readouterr().out

    assert calls == [("ensure", requested_root), ("save", requested_root)]
    assert requested_root.is_dir()
    assert str(requested_root) in output
    assert "does not move existing Quillan or Paper Data Suite files" in output
    assert "PDS_WORKSPACE_ROOT" in output
    assert "takes precedence" in output


def test_workspace_validate_uses_current_resolved_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved_root = tmp_path / "active-workspace"
    calls: list[Path] = []

    monkeypatch.setattr(
        cli_workspace,
        "resolve_workspace_root",
        lambda: resolved_root,
    )

    def ensure(path: str | Path) -> Path:
        root = Path(path)
        root.mkdir(parents=True)
        calls.append(root)
        return root

    monkeypatch.setattr(cli_workspace, "ensure_workspace_root", ensure)

    assert main(["workspace", "validate"]) == 0
    output = capsys.readouterr().out

    assert calls == [resolved_root]
    assert resolved_root.is_dir()
    assert "Workspace validated successfully" in output
    assert str(resolved_root) in output


@pytest.mark.parametrize(
    ("was_cleared", "expected_message"),
    [
        (True, "Saved PDS workspace preference cleared."),
        (False, "No saved PDS workspace preference was set."),
    ],
)
def test_workspace_reset_clears_only_saved_preference(
    was_cleared: bool,
    expected_message: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved_root = tmp_path / "resolved-after-reset"
    existing_file = tmp_path / "workspace-file.txt"
    existing_file.write_text("keep me", encoding="utf-8")
    calls = 0

    def clear() -> bool:
        nonlocal calls
        calls += 1
        return was_cleared

    monkeypatch.setattr(cli_workspace, "clear_saved_workspace_root", clear)
    monkeypatch.setattr(
        cli_workspace,
        "resolve_workspace_root",
        lambda: resolved_root,
    )

    assert main(["workspace", "reset"]) == 0
    output = capsys.readouterr().out

    assert calls == 1
    assert existing_file.read_text(encoding="utf-8") == "keep me"
    assert expected_message in output
    assert "No workspace files were deleted." in output
    assert str(resolved_root) in output
    assert "PDS_WORKSPACE_ROOT" in output
    assert "takes precedence" in output


@pytest.mark.parametrize(
    ("command", "patched_name"),
    [
        (["workspace", "set", "bad-root"], "ensure_workspace_root"),
        (["workspace", "validate"], "resolve_workspace_root"),
        (["workspace", "reset"], "clear_saved_workspace_root"),
    ],
)
def test_workspace_commands_report_workspace_errors(
    command: list[str],
    patched_name: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object) -> object:
        raise WorkspaceRootError("bad workspace")

    monkeypatch.setattr(cli_workspace, patched_name, fail)

    assert main(command) != 0
    assert "Error: bad workspace" in capsys.readouterr().out


def test_menu_dispatch_displays_options_and_exits(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out

    assert "Quillan" in output
    assert "\033[32mQuillan\033[0m" in output
    assert "1. Assignment Management" in output
    assert "2. Review Student Work" in output
    assert "3. Roster Management" in output
    assert "4. Workspace Settings" in output
    assert "5. Help" in output
    assert "6. Exit" in output
    assert "Printable Response Pages" not in output
    assert "Scan Intake / Route Paper Responses" not in output
    assert "Review Materials" not in output
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
    assert "quillan validate-standards" not in output
    assert "quillan menu" in output


def test_assignment_management_opens_printable_response_submenu(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["1", "3", "2", "", "4", "6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Printable Response Pages" in output
    assert "Generate class packet" in output
    assert "Back" in output
    assert "Goodbye." in output


def test_main_menu_opens_assignment_management_submenu(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["1", "4", "6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Assignment Management" in output
    assert "\033[32mQuillan\033[0m" in output
    assert "Create writing assignment" in output
    assert "View/validate assignment" in output
    assert "Printable Response Pages" in output
    assert "Back" in output
    assert "Goodbye." in output


def test_main_menu_opens_roster_management_submenu(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["3", "5", "6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Roster Management" in output
    assert "Create class roster" in output
    assert "View class roster" in output
    assert "Edit class roster" in output
    assert "Validate class roster" in output
    assert "Back" in output
    assert "Goodbye." in output


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

    monkeypatch.setattr(cli_workspace, "show_workspace", handle_workspace_show)
    _menu_input(monkeypatch, ["4", "1", "", "5", "6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out

    assert calls == 1
    assert "Workspace Settings" in output
    assert "Show current workspace" in output
    assert "Set workspace folder" in output
    assert "Validate/create current workspace" in output
    assert "Reset saved workspace preference" in output
    assert "Back" in output
    assert "Synthetic workspace status" in output


def test_workspace_menu_sets_workspace_folder(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = tmp_path / "menu-workspace"
    calls: list[str] = []

    def handle_workspace_set(path: str | Path) -> int:
        calls.append(str(path))
        print(f"Saved PDS workspace root:\n{path}")
        print("This does not move existing Quillan or Paper Data Suite files.")
        print("PDS_WORKSPACE_ROOT still takes precedence.")
        return 0

    monkeypatch.setattr(cli_workspace, "set_workspace", handle_workspace_set)
    _menu_input(monkeypatch, ["4", "2", str(workspace_root), "", "5", "6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out

    assert calls == [str(workspace_root)]
    assert str(workspace_root) in output
    assert "does not move existing Quillan or Paper Data Suite files" in output
    assert "PDS_WORKSPACE_ROOT" in output
    assert "takes precedence" in output


def test_workspace_menu_blank_set_cancels_without_change(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handle_workspace_set(_path: str | Path) -> int:
        nonlocal calls
        calls += 1
        return 0

    monkeypatch.setattr(cli_workspace, "set_workspace", handle_workspace_set)
    _menu_input(monkeypatch, ["4", "2", "  ", "", "5", "6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out

    assert calls == 0
    assert "canceled" in output
    assert "No preference was changed" in output


def test_workspace_menu_validates_current_workspace(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handle_workspace_validate() -> int:
        nonlocal calls
        calls += 1
        print("Workspace validated successfully")
        return 0

    monkeypatch.setattr(
        cli_workspace,
        "validate_workspace",
        handle_workspace_validate,
    )
    _menu_input(monkeypatch, ["4", "3", "", "5", "6"])

    assert main(["menu"]) == 0
    assert calls == 1
    assert "Workspace validated successfully" in capsys.readouterr().out


def test_workspace_menu_resets_saved_preference(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handle_workspace_reset() -> int:
        nonlocal calls
        calls += 1
        print("Saved PDS workspace preference cleared.")
        print("No workspace files were deleted.")
        print("Current resolved PDS workspace root: synthetic")
        print("PDS_WORKSPACE_ROOT still takes precedence.")
        return 0

    monkeypatch.setattr(
        cli_workspace,
        "reset_workspace",
        handle_workspace_reset,
    )
    _menu_input(monkeypatch, ["4", "4", "", "5", "6"])

    assert main(["menu"]) == 0
    output = capsys.readouterr().out

    assert calls == 1
    assert "No workspace files were deleted" in output
    assert "Current resolved PDS workspace root" in output
    assert "PDS_WORKSPACE_ROOT" in output


def test_menu_handles_keyboard_interrupt(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupt(_prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)

    assert main(["menu"]) == 0
    assert "Exiting Quillan." in capsys.readouterr().out

"""Focused safety and discoverability tests for menu Help."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from quillan.menu import launch_menu, print_menu_help
from tests.menu_screen_recorder import MenuScreenRecorder, assert_focused_child_screen


def test_menu_help_is_current_concise_and_side_effect_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    before = tuple(tmp_path.rglob("*"))

    def fail_input(*_args: object, **_kwargs: object) -> str:
        pytest.fail("menu Help must not prompt")

    monkeypatch.setattr(builtins, "input", fail_input)
    print_menu_help()
    output = capsys.readouterr().out

    for category in (
        "Assignment setup:",
        "Printable response pages:",
        "Scan intake and review:",
        "Student review:",
        "Feedback and reports:",
        "Workspace settings:",
    ):
        assert category in output
    assert "quillan --help" in output
    assert "Complete direct help" in output
    assert "local-first" in output
    assert "teacher-controlled" in output
    assert "synthetic data" in output
    assert "Do not commit or post real student data" in output
    assert tuple(tmp_path.rglob("*")) == before


@pytest.mark.menu_density_workflow("help")
def test_help_density_recorder_captures_focus_and_parent_redraw(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recorder = MenuScreenRecorder(["5", "", "5", "", "q"])
    recorder.install(monkeypatch)

    def no_op() -> int:
        return 0

    def set_no_op(_path: str) -> int:
        return 0

    assert launch_menu(no_op, set_no_op, no_op, no_op) == 0

    screens = recorder.screens(capsys.readouterr().out)
    assert_focused_child_screen(
        screens,
        heading="Quillan\x1b[0m\nHelp",
        required_text="Assignment setup:",
        forbidden_parent_text="1. Assignment Management",
        parent_heading="1. Assignment Management",
        result_heading="Quillan\x1b[0m\nHelp",
        unrelated_previous_text="4. Workspace Settings",
    )
    for screen in screens:
        print(f"--- CLEAR EVENT {screen.clear_number} ---")
        print(screen.output)

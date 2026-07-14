"""Focused safety and discoverability tests for menu Help."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from quillan.menu import print_menu_help


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

    for entry_point in (
        "review-dashboard",
        "review-status",
        "assignment --help",
        "roster --help",
        "printable-responses --help",
        "requirements --help",
        "review-units --help",
        "observations --help",
        "ratings --help",
        "feedback --help",
        "review-workflow --help",
        "workspace --help",
    ):
        assert entry_point in output
    assert "quillan --help" in output
    assert "complete command surface" in output
    assert "local-first" in output
    assert "teacher-controlled" in output
    assert "synthetic data" in output
    assert tuple(tmp_path.rglob("*")) == before

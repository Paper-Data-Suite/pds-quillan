"""Regression tests for the documented direct CLI surface."""

from __future__ import annotations

import argparse
from pathlib import Path

from quillan.cli_app.parser import build_parser


ROOT = Path(__file__).resolve().parents[1]


def _current_command_surface() -> str:
    contract = (ROOT / "docs" / "cli_contract.md").read_text(encoding="utf-8")
    return contract.split("## Current Command Surface", 1)[1].split("\n## ", 1)[0]


def test_cli_contract_lists_every_registered_top_level_command_and_alias() -> None:
    parser = build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    surface = _current_command_surface()

    missing = sorted(command for command in subparsers.choices if f"quillan {command}" not in surface)
    assert missing == []


def test_cli_contract_surface_excludes_removed_legacy_commands() -> None:
    surface = _current_command_surface()
    for removed in ("add-tag", "add-comment", "set-score"):
        assert f"quillan {removed}" not in surface


def test_readme_treats_command_list_as_representative_and_links_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Common direct CLI entry points include:" in readme
    assert "The direct command surface exposed through argparse is:" not in readme
    assert "docs/cli_contract.md" in readme
    assert "Q. Quit" in readme
    assert "6. Exit" not in readme

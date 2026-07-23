"""Regression tests for the documented direct CLI surface."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

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
    for removed in (
        "add-tag",
        "add-comment",
        "set-score",
        "validate-assignment",
        "open-evidence",
    ):
        assert f"quillan {removed}" not in surface
    for removed_option in ("--expected-pages", "--hide-payload"):
        assert removed_option not in surface


def test_parser_inventory_rejects_retired_raw_path_commands() -> None:
    parser = build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    assert "validate-assignment" not in subparsers.choices
    assert "open-evidence" not in subparsers.choices


def test_contract_records_the_hard_menu_design_rule() -> None:
    contract = (ROOT / "docs" / "cli_contract.md").read_text(encoding="utf-8")
    assert (
        "The menu should look and feel like a modern application menu, not a dump of\n"
        "CLI commands or a legacy operator console."
    ) in contract
    assert (
        "Screen clearing and redrawing after a teacher selects an option is the\n"
        "default. Information remains visible only when it is essential or directly\n"
        "useful for the teacher's current action."
    ) in contract
    for requirement in (
        "parent menus are compact",
        "selection lists are compact",
        "detail appears only after selection",
        "action screens are focused",
        "confirmation screens are concise",
        "result workflows clear before rendering the result",
        "result screens are concise, then pause",
        "returning redraws the parent screen",
        "direct non-interactive CLI commands are exempt",
        "context is retained intentionally only when it is needed",
    ):
        assert requirement in contract


def test_active_teacher_documentation_has_only_reviewed_legacy_matches() -> None:
    documents = (
        "README.md",
        "docs/cli_contract.md",
        "docs/development_plan.md",
        "docs/workspace_lifecycle.md",
        "docs/assignment_reporting_contract.md",
        "docs/prepared_review_workflow.md",
        "docs/printable_response_template.md",
        "docs/pds2_scan_intake.md",
        "docs/scan_routing_design.md",
    )
    pattern = re.compile(
        r"PDS1|--payload|validate-assignment|open-evidence|"
        r"explicit assignment JSON|classes/.*/assignments|"
        r"classes/<class_id>/assignments|expected pages?",
        re.IGNORECASE,
    )
    allowlist = {
        ("docs/cli_contract.md", "identity and path, lightweight submission state, expected page count, manifest"),
        ("docs/cli_contract.md", "or leaves unchanged each canonical student `submission.json`. Expected pages"),
        ("docs/cli_contract.md", "`validate-assignment <path>` and `open-evidence <path>` are not public"),
        ("docs/printable_response_template.md", "profile; submission assembly derives expected pages from issuance membership."),
        ("docs/scan_routing_design.md", "groups by exact issuance ID. It loads all expected pages in issuance order,"),
    }
    matches: set[tuple[str, str]] = set()
    for relative in documents:
        for line in (ROOT / relative).read_text(encoding="utf-8").splitlines():
            if pattern.search(line):
                matches.add((relative, line.strip()))
    assert matches - allowlist == set()
    assert allowlist - matches == set()


def test_readme_treats_command_list_as_representative_and_links_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Common direct CLI entry points include:" in readme
    assert "The direct command surface exposed through argparse is:" not in readme
    assert "docs/cli_contract.md" in readme
    assert "Q. Quit" in readme
    assert "6. Exit" not in readme

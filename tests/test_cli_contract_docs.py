"""Regression tests for the documented direct CLI surface."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
import re
from typing import Any, Callable, cast

import pytest

from quillan.cli_app.inventory import (
    CliInventoryMismatch,
    assert_documented_inventory_matches,
    load_documented_inventory,
    inventory_parser,
)
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


def _documented_inventory() -> dict[str, object]:
    return load_documented_inventory(ROOT / "docs" / "cli_contract_inventory.json")


def test_documented_cli_inventory_equals_recursive_argparse_structure() -> None:
    assert_documented_inventory_matches(build_parser(), _documented_inventory())


InventoryMutation = Callable[[dict[str, Any]], None]


def _nodes(document: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], document["nodes"])


def _wrong_nesting(document: dict[str, Any]) -> None:
    _nodes(document)[2]["path"] = ["quillan", "wrong", "nesting"]


def _missing_command(document: dict[str, Any]) -> None:
    _nodes(document).pop()


def _stale_extra_command(document: dict[str, Any]) -> None:
    stale = copy.deepcopy(_nodes(document)[-1])
    stale["path"] = ["quillan", "stale-extra-command"]
    _nodes(document).append(stale)


def _missing_alias(document: dict[str, Any]) -> None:
    next(node for node in _nodes(document) if node["aliases"])["aliases"] = []


def _option_on_wrong_command(document: dict[str, Any]) -> None:
    source = next(node for node in _nodes(document) if node["arguments"])
    target = next(node for node in _nodes(document) if node is not source)
    target["arguments"].append(source["arguments"].pop())


def _incorrect_required(document: dict[str, Any]) -> None:
    argument = next(node for node in _nodes(document) if node["arguments"])["arguments"][0]
    argument["required"] = not argument["required"]


def _incorrect_choices(document: dict[str, Any]) -> None:
    argument = next(
        argument
        for node in _nodes(document)
        for argument in node["arguments"]
        if argument["choices"]
    )
    argument["choices"] = [*argument["choices"], "stale-choice"]


def _incorrect_default(document: dict[str, Any]) -> None:
    argument = next(node for node in _nodes(document) if node["arguments"])["arguments"][0]
    argument["default"] = "incorrect-public-default"


def _incorrect_help(document: dict[str, Any]) -> None:
    argument = next(node for node in _nodes(document) if node["arguments"])["arguments"][0]
    argument["help"] += " Incorrect help."


def _incorrect_mutex_membership(document: dict[str, Any]) -> None:
    argument = next(
        argument
        for node in _nodes(document)
        for argument in node["arguments"]
        if argument["mutex_group"] is not None
    )
    argument["mutex_group"] = None


def _incorrect_required_mutex(document: dict[str, Any]) -> None:
    group = next(node for node in _nodes(document) if node["mutex_groups"])["mutex_groups"][0]
    group["required"] = not group["required"]


def _incorrect_argument_order(document: dict[str, Any]) -> None:
    arguments = next(node for node in _nodes(document) if len(node["arguments"]) > 1)["arguments"]
    arguments[0], arguments[1] = arguments[1], arguments[0]


def _incorrect_command_short_help(document: dict[str, Any]) -> None:
    node = next(node for node in _nodes(document) if node["short_help"] is not None)
    node["short_help"] += " Incorrect parent-listing help."


@pytest.mark.parametrize(
    "mutation",
    (
        _wrong_nesting,
        _missing_command,
        _stale_extra_command,
        _missing_alias,
        _option_on_wrong_command,
        _incorrect_required,
        _incorrect_choices,
        _incorrect_default,
        _incorrect_help,
        _incorrect_mutex_membership,
        _incorrect_required_mutex,
        _incorrect_argument_order,
        _incorrect_command_short_help,
    ),
    ids=(
        "wrong nesting",
        "missing command",
        "stale extra command",
        "missing alias",
        "option on wrong command",
        "required status",
        "choices",
        "default",
        "help",
        "mutex membership",
        "required mutex",
        "argument order",
        "command short help",
    ),
)
def test_structural_inventory_rejects_documented_parser_drift(
    mutation: InventoryMutation,
) -> None:
    documented = copy.deepcopy(_documented_inventory())
    mutation(documented)
    with pytest.raises(CliInventoryMismatch, match="differs structurally"):
        assert_documented_inventory_matches(build_parser(), documented)


def test_inventory_distinguishes_only_command_level_short_help() -> None:
    def parser_with(help_text: str) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        subparsers.add_parser("child", help=help_text)
        return parser

    first = inventory_parser(parser_with("First parent-listing help."))
    second = inventory_parser(parser_with("Second parent-listing help."))
    assert first[1].description == second[1].description == ""
    assert first[1].short_help == "First parent-listing help."
    assert second[1].short_help == "Second parent-listing help."
    assert first != second


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

"""Deterministic recursive inventory of Quillan's public argparse contract."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, cast, Final


DOCUMENT_SCHEMA_VERSION: Final = "1"
JsonScalar = str | int | float | bool | None


class CliInventoryMismatch(AssertionError):
    """Raised when documented and implemented CLI inventories differ."""


@dataclass(frozen=True)
class ArgumentInventory:
    """One public positional or option argument."""

    names: tuple[str, ...]
    required: bool
    choices: tuple[JsonScalar, ...]
    default: JsonScalar
    help: str
    mutex_group: int | None


@dataclass(frozen=True)
class MutexGroupInventory:
    """One parser-local mutually exclusive group."""

    group: int
    required: bool


@dataclass(frozen=True)
class ParserInventory:
    """One public command path in the recursive parser tree."""

    path: tuple[str, ...]
    aliases: tuple[str, ...]
    short_help: str | None
    description: str
    arguments: tuple[ArgumentInventory, ...]
    mutex_groups: tuple[MutexGroupInventory, ...]


def _normalized_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _json_scalar(value: Any) -> JsonScalar:
    if value in (None, argparse.SUPPRESS):
        return None
    if type(value) in (str, int, float, bool):
        return cast(JsonScalar, value)
    return str(value)


def _mutex_indexes(parser: argparse.ArgumentParser) -> dict[int, int]:
    return {
        id(action): index
        for index, group in enumerate(parser._mutually_exclusive_groups, start=1)
        for action in group._group_actions
    }


def _arguments(parser: argparse.ArgumentParser) -> tuple[ArgumentInventory, ...]:
    mutex = _mutex_indexes(parser)
    values: list[ArgumentInventory] = []
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        values.append(
            ArgumentInventory(
                names=tuple(action.option_strings) or (action.dest,),
                required=bool(action.required),
                choices=tuple(_json_scalar(value) for value in action.choices or ()),
                default=_json_scalar(action.default),
                help=_normalized_text(action.help),
                mutex_group=mutex.get(id(action)),
            )
        )
    return tuple(values)


def _mutex_groups(parser: argparse.ArgumentParser) -> tuple[MutexGroupInventory, ...]:
    return tuple(
        MutexGroupInventory(group=index, required=bool(group.required))
        for index, group in enumerate(parser._mutually_exclusive_groups, start=1)
    )


def inventory_parser(
    parser: argparse.ArgumentParser,
    path: tuple[str, ...] = ("quillan",),
    *,
    _short_help: str | None = None,
) -> tuple[ParserInventory, ...]:
    """Inventory every command, alias, argument, group, default, and help value."""
    current = ParserInventory(
        path=path,
        aliases=(),
        short_help=None if _short_help is None else _normalized_text(_short_help),
        description=_normalized_text(parser.description),
        arguments=_arguments(parser),
        mutex_groups=_mutex_groups(parser),
    )
    descendants: list[ParserInventory] = [current]
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        short_help_by_child: dict[int, str] = {}
        for choice_action in action._choices_actions:
            display_name = str(choice_action.dest)
            canonical_name = next(
                (
                    name
                    for name in action.choices
                    if display_name == name or display_name.startswith(f"{name} (")
                ),
                None,
            )
            if canonical_name is not None:
                short_help_by_child[id(action.choices[canonical_name])] = str(
                    choice_action.help
                )
        seen: set[int] = set()
        for name, child in action.choices.items():
            if id(child) in seen:
                continue
            seen.add(id(child))
            child_aliases = tuple(
                alias
                for alias, candidate in action.choices.items()
                if candidate is child and alias != name
            )
            child_values = inventory_parser(
                child,
                (*path, name),
                _short_help=short_help_by_child.get(id(child)),
            )
            first = child_values[0]
            descendants.append(
                ParserInventory(
                    path=first.path,
                    aliases=child_aliases,
                    short_help=first.short_help,
                    description=first.description,
                    arguments=first.arguments,
                    mutex_groups=first.mutex_groups,
                )
            )
            descendants.extend(child_values[1:])
    return tuple(descendants)


def inventory_document(values: tuple[ParserInventory, ...]) -> dict[str, object]:
    """Return the canonical JSON-compatible documented-inventory value."""
    return {
        "schema_version": DOCUMENT_SCHEMA_VERSION,
        "root_command": "quillan",
        "nodes": [
            {
                "path": list(value.path),
                "aliases": list(value.aliases),
                "short_help": value.short_help,
                "description": value.description,
                "arguments": [
                    {
                        "names": list(argument.names),
                        "required": argument.required,
                        "choices": list(argument.choices),
                        "default": argument.default,
                        "help": argument.help,
                        "mutex_group": argument.mutex_group,
                    }
                    for argument in value.arguments
                ],
                "mutex_groups": [
                    {"group": group.group, "required": group.required}
                    for group in value.mutex_groups
                ],
            }
            for value in values
        ],
    }


def load_documented_inventory(path: Path) -> dict[str, object]:
    """Load a strict UTF-8 JSON inventory without normalizing its structure."""
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if type(value) is not dict:
        raise CliInventoryMismatch("Documented CLI inventory must be a JSON object.")
    return value


def assert_documented_inventory_matches(
    parser: argparse.ArgumentParser, documented: dict[str, object]
) -> None:
    """Require bidirectional structural equality with one parser tree."""
    implemented = inventory_document(inventory_parser(parser))
    if documented == implemented:
        return
    raise CliInventoryMismatch(
        "Documented CLI inventory differs structurally from argparse.\n"
        f"DOCUMENTED:\n{json.dumps(documented, indent=2, sort_keys=True)}\n"
        f"IMPLEMENTED:\n{json.dumps(implemented, indent=2, sort_keys=True)}"
    )


__all__ = [
    "ArgumentInventory",
    "CliInventoryMismatch",
    "DOCUMENT_SCHEMA_VERSION",
    "MutexGroupInventory",
    "ParserInventory",
    "assert_documented_inventory_matches",
    "inventory_document",
    "inventory_parser",
    "load_documented_inventory",
]

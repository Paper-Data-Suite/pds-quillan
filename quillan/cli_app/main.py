"""Top-level execution for the Quillan CLI."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import cast

from quillan.cli_app.arguments import ScoreArgumentError
from quillan.cli_app.handlers.workspace import launch_default_menu
from quillan.cli_app.parser import build_parser


def main(argv: list[str] | None = None) -> int:
    """Run the Quillan command-line interface."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except ScoreArgumentError as error:
        print(f"Error: could not set review score: {error}")
        return 1

    handler = getattr(args, "handler", None)
    if handler is not None:
        command_handler = cast(Callable[[argparse.Namespace], int], handler)
        return command_handler(args)
    if args.command is None:
        return launch_default_menu()

    parser.print_help()
    return 0

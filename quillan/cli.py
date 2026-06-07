"""Command-line interface for Quillan."""

from __future__ import annotations

import argparse
from pathlib import Path

from quillan.standards import StandardsProfileError, load_standards_profile

APP_DESCRIPTION = "Quillan: standards-based writing evidence capture"


def main(argv: list[str] | None = None) -> None:
    """Run the Quillan command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-standards":
        _handle_validate_standards(args.path)
        return

    parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(description=APP_DESCRIPTION)
    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate-standards",
        help="Validate a standards profile JSON file.",
    )
    validate_parser.add_argument(
        "path",
        type=Path,
        help="Path to the standards profile JSON file.",
    )

    return parser


def _handle_validate_standards(path: Path) -> None:
    """Validate a standards profile and print a user-facing result."""
    try:
        profile = load_standards_profile(path)
    except StandardsProfileError as error:
        raise SystemExit(f"Invalid standards profile: {error}") from error

    print(f"Valid standards profile: {profile['profile_id']}")
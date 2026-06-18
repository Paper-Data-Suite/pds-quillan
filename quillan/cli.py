"""Command-line interface for Quillan."""

from __future__ import annotations

import argparse
from pathlib import Path

from pds_core.workspace import (
    WorkspaceRootError,
    WorkspaceStatus,
    clear_saved_workspace_root,
    ensure_workspace_root,
    inspect_workspace_root,
    resolve_workspace_root,
    save_workspace_root,
)

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.menu import launch_menu
from quillan.standards import StandardsProfileError, load_standards_profile

APP_DESCRIPTION = "Quillan: standards-based writing evidence capture"


def main(argv: list[str] | None = None) -> int:
    """Run the Quillan command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-standards":
        _handle_validate_standards(args.path)
        return 0

    if args.command == "validate-assignment":
        _handle_validate_assignment(args.path)
        return 0

    if args.command == "workspace" and args.workspace_command == "show":
        return _handle_workspace_show()

    if args.command == "workspace" and args.workspace_command == "set":
        return _handle_workspace_set(args.path)

    if args.command == "workspace" and args.workspace_command == "validate":
        return _handle_workspace_validate()

    if args.command == "workspace" and args.workspace_command == "reset":
        return _handle_workspace_reset()

    if args.command is None or args.command == "menu":
        return launch_menu(
            _handle_workspace_show,
            _handle_workspace_set,
            _handle_workspace_validate,
            _handle_workspace_reset,
        )

    parser.print_help()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(description=APP_DESCRIPTION)
    subparsers = parser.add_subparsers(dest="command")

    validate_standards_parser = subparsers.add_parser(
        "validate-standards",
        help="Validate a standards profile JSON file.",
    )
    validate_standards_parser.add_argument(
        "path",
        type=Path,
        help="Path to the standards profile JSON file.",
    )

    validate_assignment_parser = subparsers.add_parser(
        "validate-assignment",
        help="Validate an assignment config JSON file.",
    )
    validate_assignment_parser.add_argument(
        "path",
        type=Path,
        help="Path to the assignment config JSON file.",
    )

    workspace_parser = subparsers.add_parser(
        "workspace",
        help="Manage the shared Paper Data Suite workspace.",
    )
    workspace_subparsers = workspace_parser.add_subparsers(
        dest="workspace_command"
    )
    workspace_subparsers.add_parser(
        "show",
        help="Show the active Paper Data Suite workspace status.",
    )
    workspace_set_parser = workspace_subparsers.add_parser(
        "set",
        help="Validate, create, and save a shared workspace root.",
    )
    workspace_set_parser.add_argument(
        "path",
        type=Path,
        help="Folder to use as the shared Paper Data Suite workspace.",
    )
    workspace_subparsers.add_parser(
        "validate",
        help="Validate or create the currently resolved workspace root.",
    )
    workspace_subparsers.add_parser(
        "reset",
        help="Clear the saved workspace preference without deleting files.",
    )

    subparsers.add_parser(
        "menu",
        help="Launch the teacher-facing interactive menu.",
    )

    return parser


def _handle_validate_standards(path: Path) -> None:
    """Validate a standards profile and print a user-facing result."""
    try:
        profile = load_standards_profile(path)
    except StandardsProfileError as error:
        raise SystemExit(f"Invalid standards profile: {error}") from error

    print(f"Valid standards profile: {profile['profile_id']}")


def _handle_validate_assignment(path: Path) -> None:
    """Validate an assignment config and print a user-facing result."""
    try:
        assignment = load_assignment_config(path)
    except AssignmentConfigError as error:
        raise SystemExit(f"Invalid assignment config: {error}") from error

    print(f"Valid assignment config: {assignment['assignment_id']}")


def _handle_workspace_show() -> int:
    """Print the shared Paper Data Suite workspace status."""
    try:
        status = inspect_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return 1

    _print_workspace_status(status)
    return 0


def _handle_workspace_set(path: str | Path) -> int:
    """Validate, create, and save the shared workspace root."""
    try:
        workspace_root = ensure_workspace_root(path)
        saved_root = save_workspace_root(workspace_root)
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return 1

    print("Saved PDS workspace root:")
    print(saved_root)
    print()
    print("This does not move existing Quillan or Paper Data Suite files.")
    print(
        "If PDS_WORKSPACE_ROOT is set, it still takes precedence over "
        "the saved preference."
    )
    return 0


def _handle_workspace_validate() -> int:
    """Validate or create the currently resolved shared workspace root."""
    try:
        workspace_root = resolve_workspace_root()
        validated_root = ensure_workspace_root(workspace_root)
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return 1

    print("Workspace validated successfully:")
    print(validated_root)
    return 0


def _handle_workspace_reset() -> int:
    """Clear the saved shared workspace preference without deleting files."""
    try:
        was_cleared = clear_saved_workspace_root()
        workspace_root = resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return 1

    if was_cleared:
        print("Saved PDS workspace preference cleared.")
    else:
        print("No saved PDS workspace preference was set.")
    print("No workspace files were deleted.")
    print()
    print("Current resolved PDS workspace root:")
    print(workspace_root)
    print()
    print("If PDS_WORKSPACE_ROOT is set, it still takes precedence.")
    return 0


def _print_workspace_status(status: WorkspaceStatus) -> None:
    """Print a stable, user-facing workspace status summary."""
    print("Current PDS workspace root:")
    print(status.root)
    print("\nSource:")
    print(status.source)
    print("\nExists:")
    print(_format_bool(status.exists))
    print("\nDirectory:")
    print(_format_bool(status.is_dir))
    print("\nWritable:")
    print(_format_bool(status.is_writable))
    print("\nConfig file:")
    print(status.config_path)
    print("\nDefault workspace root:")
    print(status.default_root)


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"

"""Workspace command handlers and the interactive-menu bridge."""

from __future__ import annotations

import argparse
from pathlib import Path

from pds_core.workspace import (
    WorkspaceRootError,
    clear_saved_workspace_root,
    ensure_workspace_root,
    inspect_workspace_root,
    resolve_workspace_root,
    save_workspace_root,
)

from quillan.cli_app.output import print_workspace_status
from quillan.menu import launch_menu


def handle_workspace_show(_args: argparse.Namespace) -> int:
    """Print the shared Paper Data Suite workspace status."""
    return show_workspace()


def handle_workspace_set(args: argparse.Namespace) -> int:
    """Validate, create, and save the shared workspace root."""
    return set_workspace(args.path)


def handle_workspace_validate(_args: argparse.Namespace) -> int:
    """Validate or create the currently resolved shared workspace root."""
    return validate_workspace()


def handle_workspace_reset(_args: argparse.Namespace) -> int:
    """Clear the saved shared workspace preference without deleting files."""
    return reset_workspace()


def handle_menu(_args: argparse.Namespace) -> int:
    """Launch the teacher-facing interactive menu."""
    return launch_default_menu()


def launch_default_menu() -> int:
    """Launch the menu with the CLI workspace operations."""
    return launch_menu(
        show_workspace,
        set_workspace,
        validate_workspace,
        reset_workspace,
    )


def show_workspace() -> int:
    """Print the shared Paper Data Suite workspace status."""
    try:
        status = inspect_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: {error}")
        return 1

    print_workspace_status(status)
    return 0


def set_workspace(path: str | Path) -> int:
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


def validate_workspace() -> int:
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


def reset_workspace() -> int:
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

"""Validation command handlers."""

from __future__ import annotations

import argparse

from quillan.assignments import AssignmentConfigError, load_assignment_config


def handle_validate_assignment(args: argparse.Namespace) -> int:
    """Validate an assignment config and print a user-facing result."""
    try:
        assignment = load_assignment_config(args.path)
    except AssignmentConfigError as error:
        raise SystemExit(f"Invalid assignment config: {error}") from error

    print(f"Valid assignment config: {assignment['assignment_id']}")
    return 0

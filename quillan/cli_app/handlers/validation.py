"""Validation command handlers."""

from __future__ import annotations

import argparse

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.standards import StandardsProfileError, load_standards_profile


def handle_validate_standards(args: argparse.Namespace) -> int:
    """Validate a standards profile and print a user-facing result."""
    try:
        profile = load_standards_profile(args.path)
    except StandardsProfileError as error:
        raise SystemExit(f"Invalid standards profile: {error}") from error

    print(f"Valid standards profile: {profile['profile_id']}")
    return 0


def handle_validate_assignment(args: argparse.Namespace) -> int:
    """Validate an assignment config and print a user-facing result."""
    try:
        assignment = load_assignment_config(args.path)
    except AssignmentConfigError as error:
        raise SystemExit(f"Invalid assignment config: {error}") from error

    print(f"Valid assignment config: {assignment['assignment_id']}")
    return 0

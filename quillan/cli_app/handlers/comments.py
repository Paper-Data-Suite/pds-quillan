"""Direct, non-interactive reusable-comment management handlers."""

from __future__ import annotations

import argparse
import math
import re
import sys

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import (
    print_created_manual_reusable_comment,
    print_reusable_comment_inventory,
    print_reusable_comment_set,
)
from quillan.comment_management import (
    create_manual_reusable_comment,
    list_reusable_comments,
    show_reusable_comment_set,
)
from quillan.focus_standard_comments import FocusStandardCommentError


def handle_comments_list(args: argparse.Namespace) -> int:
    """List active, student-facing reusable comments."""
    try:
        inventory = list_reusable_comments(
            resolve_workspace_root(),
            standards_profile_id=_optional_trimmed(args.profile_id, "profile ID"),
            writing_type=_optional_trimmed(args.writing_type, "writing type"),
            standard_id=_optional_trimmed(args.standard_id, "standard ID"),
            rating_value=(
                _number(args.rating_value, "rating value")
                if args.rating_value is not None
                else None
            ),
        )
        print_reusable_comment_inventory(inventory)
        return 1 if inventory.invalid_files else 0
    except (OSError, ValueError, WorkspaceRootError, FocusStandardCommentError) as error:
        return _error(error)


def handle_comments_show(args: argparse.Namespace) -> int:
    """Show one complete reusable comment set."""
    try:
        result = show_reusable_comment_set(resolve_workspace_root(), args.comment_set_id)
        print_reusable_comment_set(result)
        return 0
    except (OSError, ValueError, WorkspaceRootError, FocusStandardCommentError) as error:
        return _error(error)


def handle_comments_create(args: argparse.Namespace) -> int:
    """Create one manually authored reusable comment."""
    try:
        result = create_manual_reusable_comment(
            resolve_workspace_root(),
            comment_set_id=args.comment_set_id,
            standards_profile_id=args.profile_id,
            writing_type=args.writing_type,
            standard_id=args.standard_id,
            label=args.label,
            text=args.text,
            purpose=args.purpose,
            rating_values=_number_list(args.rating_values, "rating values"),
            teacher_tags=_tag_list(args.teacher_tags),
        )
        print_created_manual_reusable_comment(result)
        return 0
    except (OSError, ValueError, WorkspaceRootError, FocusStandardCommentError) as error:
        return _error(error)


def _number_list(value: str | None, label: str) -> list[int | float]:
    if value is None:
        return []
    items = value.split(",")
    if any(not item.strip() for item in items):
        raise FocusStandardCommentError(f"{label} must not contain blank elements.")
    numbers = [_number(item.strip(), label) for item in items]
    seen: set[int | float] = set()
    for number in numbers:
        if number in seen:
            raise FocusStandardCommentError(f"{label} contains duplicate {number!r}.")
        seen.add(number)
    return numbers


def _number(value: str, label: str) -> int | float:
    try:
        number: int | float
        if re.fullmatch(r"[+-]?\d+", value):
            number = int(value)
        else:
            number = float(value)
    except ValueError as error:
        raise FocusStandardCommentError(f"{label} must contain finite numbers.") from error
    if isinstance(number, float) and not math.isfinite(number):
        raise FocusStandardCommentError(f"{label} must contain finite numbers.")
    return number


def _tag_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = value.split(",")
    if any(not item.strip() for item in items):
        raise FocusStandardCommentError(
            "teacher tags must not contain blank elements."
        )
    return [item.strip() for item in items]


def _optional_trimmed(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise FocusStandardCommentError(f"{label} must not be blank.")
    return normalized


def _error(error: Exception) -> int:
    print(f"Error: {error}", file=sys.stderr)
    return 1

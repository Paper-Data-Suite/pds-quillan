"""Direct, non-interactive minimum-requirement review handlers."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.minimum_requirement_review import (
    load_minimum_requirement_review_context,
    set_configured_minimum_requirement_outcome,
    set_configured_requirement_check,
)
from quillan.review_requirements import ReviewRequirementError


def handle_requirements_list(args: argparse.Namespace) -> int:
    """Display configured requirements and current teacher-entered state."""
    try:
        context = load_minimum_requirement_review_context(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id
        )
        review = context.review
        outcome = review["minimum_requirement_outcome"] if review is not None else None
        checks = context.configured_checks
        print("Minimum-requirement review:")
        print(f"Class: {context.class_id}")
        print(f"Assignment: {context.assignment_id}")
        print(f"Student: {context.student_id}")
        print(f"Submission manifest: {context.submission_manifest_relative_path}")
        print(f"Review record: {context.review_record_relative_path}")
        print(f"Review record exists: {_yes_no(review is not None)}")
        print(f"Review state: {review['review_state'] if review is not None else 'not_started'}")
        print()
        if not context.requirements:
            print("Minimum requirements: none configured")
        else:
            print("Minimum requirements:")
            for index, requirement in enumerate(context.requirements, start=1):
                check = checks.get(requirement.key)
                print(f"{index}. {requirement.label}")
                print(f"   Key: {requirement.key}")
                print(f"   Expected: {requirement.expected}")
                print(f"   State: {_check_state(check)}")
                print(f"   Teacher note: {_value_or_none(check, 'teacher_note')}")
                print(f"   Check ID: {_value_or_none(check, 'requirement_check_id')}")
                print(f"   Updated: {_value_or_none(check, 'updated_at')}")
        summary = context.summary
        print()
        print(f"Total configured requirements: {summary.total}")
        print(f"Checked: {summary.checked}")
        print(f"Unchecked: {summary.unchecked}")
        print(f"Met: {summary.met}")
        print(f"Unmet: {summary.unmet}")
        if context.stale_checks:
            print(f"Unrecognized/stale checks: {len(context.stale_checks)}")
        print(f"Overall outcome: {outcome['status'] if outcome is not None else 'not_checked'}")
        returned = outcome is not None and outcome["returned_without_full_review"] is True
        print(f"Returned without full standards review: {_yes_no(returned)}")
        print(f"Outcome teacher note: {_value_or_none(outcome, 'teacher_note')}")
        print(f"Outcome updated: {_value_or_none(outcome, 'updated_at')}")
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewRequirementError) as error:
        return _error(error)


def handle_requirements_set_check(args: argparse.Namespace) -> int:
    """Record one explicit teacher-entered configured requirement check."""
    try:
        result = set_configured_requirement_check(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            args.student_id,
            requirement_key=args.requirement_key,
            met=args.met,
            teacher_note=args.note,
        )
        update = result.update
        print("Recorded minimum-requirement check:")
        print(f"Requirement key: {result.requirement.key}")
        print(f"Label: {result.requirement.label}")
        print(f"Expected: {result.requirement.expected}")
        print(f"Met: {_yes_no(update.met)}")
        print(f"Action: {'created' if update.was_created else 'updated'}")
        print(f"Teacher note: {result.teacher_note or 'none'}")
        print(f"Review state: {update.review_state}")
        print(f"Review record: {update.review_record_relative_path}")
        print(f"Updated: {update.updated_at}")
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewRequirementError) as error:
        return _error(error)


def handle_requirements_set_outcome(args: argparse.Namespace) -> int:
    """Record one explicit teacher-selected assignment-aware outcome."""
    try:
        result = set_configured_minimum_requirement_outcome(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            args.student_id,
            status=args.outcome,
            teacher_note=args.note,
        )
        print("Finalized minimum-requirements outcome:")
        print(f"Outcome: {result.status}")
        print(
            "Returned without full standards review: "
            f"{_yes_no(result.returned_without_full_review)}"
        )
        print(f"Teacher note: {result.teacher_note or 'none'}")
        print(f"Review state: {result.review_state}")
        print(f"Review record: {result.review_record_relative_path}")
        print(f"Updated: {result.updated_at}")
        if result.returned_without_full_review:
            print("Full standards review was not completed.")
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewRequirementError) as error:
        return _error(error)


def _check_state(check: dict[str, Any] | None) -> str:
    if check is None:
        return "not checked"
    return "met" if check["met"] is True else "not met"


def _value_or_none(record: dict[str, Any] | None, key: str) -> Any:
    if record is None:
        return "none"
    value = record.get(key)
    return value if value is not None else "none"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _error(error: Exception) -> int:
    print(f"Error: {error}", file=sys.stderr)
    return 1

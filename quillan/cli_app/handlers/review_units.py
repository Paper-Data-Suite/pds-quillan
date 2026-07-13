"""Direct, non-interactive review-unit management handlers."""

from __future__ import annotations

import argparse

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import print_updated_review_units
from quillan.review_observations import ReviewObservationError, set_review_units
from quillan.review_unit_management import (
    ReviewUnitManagementError,
    load_review_unit_context,
    load_review_unit_definitions_file,
)


def handle_review_units_show(args: argparse.Namespace) -> int:
    """Display assignment configuration and current review units without writing."""
    try:
        context = load_review_unit_context(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id
        )
        print("Review units:")
        print(f"Class: {context.class_id}")
        print(f"Assignment: {context.assignment_id}")
        print(f"Student: {context.student_id}")
        print(f"Review-unit type: {context.unit_type}")
        print(f"Singular label: {context.singular_label}")
        print(f"Plural label: {context.plural_label}")
        print(f"Submission manifest: {context.submission_manifest_relative_path}")
        print(f"Review record: {context.review_record_relative_path}")
        print(f"Review record exists: {'yes' if context.review is not None else 'no'}")
        print(f"Review state: {context.review_state}")
        print(f"Total units: {len(context.units)}")
        print(f"Total observations: {context.observation_count}")
        for unit in context.units:
            details = (
                f"- {unit.sequence}. {unit.label} ({unit.unit_id}); "
                f"type: {unit.unit_type}; observations: {unit.observation_count}"
            )
            if unit.page_number is not None:
                details += f"; page: {unit.page_number}"
            if unit.evidence_id is not None:
                details += f"; evidence: {unit.evidence_id}"
            print(details)
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewUnitManagementError) as error:
        return _error(error)


def handle_review_units_set(args: argparse.Namespace) -> int:
    """Replace review units from an explicit count or constrained JSON file."""
    try:
        workspace_root = resolve_workspace_root()
        if args.count is not None:
            units = [{"sequence": sequence} for sequence in range(1, args.count + 1)]
        else:
            units = load_review_unit_definitions_file(args.units)
        updated = set_review_units(
            workspace_root, args.class_id, args.assignment_id, args.student_id, units
        )
        print_updated_review_units(updated)
        return 0
    except (
        OSError,
        ValueError,
        WorkspaceRootError,
        ReviewObservationError,
        ReviewUnitManagementError,
    ) as error:
        return _error(error)


def _error(error: Exception) -> int:
    print(f"Error: {error}")
    return 1

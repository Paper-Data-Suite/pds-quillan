"""Direct, non-interactive Focus Standard observation handlers."""

from __future__ import annotations

import argparse

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import (
    print_completed_review_unit_observations,
    print_updated_review_unit_observation,
)
from quillan.observation_management import (
    ObservationContext,
    ObservationManagementError,
    UnitStandardObservationStatus,
    load_observation_context,
)
from quillan.review_observations import (
    ReviewObservationError,
    mark_observations_complete,
    set_review_unit_observation,
)


def handle_observations_list(args: argparse.Namespace) -> int:
    """Display all active unit-standard observation pairs without writing."""
    try:
        context = load_observation_context(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id
        )
        _print_observation_context(context)
        return 0
    except (
        OSError,
        ValueError,
        WorkspaceRootError,
        ObservationManagementError,
    ) as error:
        return _error(error)


def handle_observations_set(args: argparse.Namespace) -> int:
    """Record one complete teacher-entered unit-standard judgment."""
    try:
        if args.applicable and args.evidence_present is None:
            raise ReviewObservationError(
                "--evidence-present true|false is required when --applicable true."
            )
        if not args.applicable and args.evidence_present is not None:
            raise ReviewObservationError(
                "--evidence-present must be omitted when --applicable false."
            )
        if not args.applicable and args.rating is not None:
            raise ReviewObservationError(
                "--rating must be omitted when --applicable false."
            )
        updated = set_review_unit_observation(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            args.student_id,
            unit_id=args.unit_id,
            standard_id=args.standard_id,
            applicable=args.applicable,
            evidence_present=args.evidence_present,
            rating=args.rating,
            rationale=args.rationale,
            include_in_feedback=args.include_in_feedback,
        )
        print_updated_review_unit_observation(updated)
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewObservationError) as error:
        return _error(error)


def handle_observations_mark_complete(args: argparse.Namespace) -> int:
    """Explicitly mark review-unit observations complete without prompting."""
    try:
        completed = mark_observations_complete(
            resolve_workspace_root(),
            args.class_id,
            args.assignment_id,
            args.student_id,
        )
        print_completed_review_unit_observations(completed)
        if completed.missing_focus_standard_pairs:
            print(
                "Warning: Observations were marked complete with "
                f"{completed.missing_focus_standard_pairs} unobserved "
                "unit-standard pair(s); no observations were created."
            )
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewObservationError) as error:
        return _error(error)


def _print_observation_context(context: ObservationContext) -> None:
    summary = context.summary
    print("Focus Standard observations:")
    print(f"Class: {context.class_id}")
    print(f"Assignment: {context.assignment_id}")
    print(f"Student: {context.student_id}")
    print(f"Review state: {context.review_state}")
    print(f"Submission manifest: {context.submission_manifest_relative_path}")
    print(f"Review record: {context.review_record_relative_path}")
    print(f"Review record exists: {_yes_no(context.review_exists)}")
    print(f"Review units: {context.unit_count}")
    print(f"Focus Standards: {len(context.focus_standard_ids)}")
    print(f"Expected unit-standard pairs: {summary.expected_pair_count}")
    print(f"Recorded observations: {summary.recorded_count}")
    print(f"Unrecorded pairs: {summary.unrecorded_count}")
    print(f"Applicable: {summary.applicable_count}")
    print(f"Not applicable: {summary.not_applicable_count}")
    print(f"Evidence present: {summary.evidence_present_count}")
    print(f"Evidence missing: {summary.evidence_missing_count}")
    print(f"Unit-level observation ratings: {summary.rating_count}")
    print(f"Included for feedback: {summary.included_for_feedback_count}")
    print(f"Assignment rating scale: {context.rating_scale_id}")
    for level in context.rating_scale_levels:
        print(f"- {level.value}: {level.label}")

    if context.unit_count == 0:
        print()
        print("Review units must be defined before observations can be recorded.")
        return

    print()
    print("Unit-standard matrix:")
    for pair in context.pairs:
        _print_pair(pair)


def _print_pair(pair: UnitStandardObservationStatus) -> None:
    if pair.observation_id is None:
        status = "not recorded"
        observation_id = "not recorded"
        evidence = "not recorded"
        rating = "not recorded"
        rationale = "none"
        feedback = "not recorded"
        updated = "not recorded"
    else:
        status = "applicable" if pair.applicable else "not applicable"
        observation_id = pair.observation_id
        if pair.applicable:
            evidence = _yes_no(pair.evidence_present is True)
            rating = (
                "none"
                if pair.rating is None
                else f"{pair.rating} ({pair.rating_label})"
            )
        else:
            evidence = "not applicable"
            rating = "not applicable"
        rationale = pair.rationale or "none"
        feedback = _yes_no(pair.include_in_feedback is True)
        updated = pair.updated_at or "none"
    print(f"{pair.unit_sequence}. {pair.unit_label} ({pair.unit_id})")
    print(f"   Focus Standard: {pair.standard_id}")
    print(f"   Status: {status}")
    print(f"   Observation ID: {observation_id}")
    print(f"   Evidence present: {evidence}")
    print(f"   Unit-level rating: {rating}")
    print(f"   Rationale: {rationale}")
    print(f"   Include in feedback: {feedback}")
    print(f"   Updated: {updated}")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _error(error: Exception) -> int:
    print(f"Error: {error}")
    return 1

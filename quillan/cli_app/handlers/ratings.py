"""Direct, non-interactive overall Focus Standard rating handlers."""

from __future__ import annotations

import argparse

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import (
    print_completed_overall_standard_ratings,
    print_updated_overall_standard_rating,
)
from quillan.rating_management import (
    OverallRatingContext,
    OverallRatingSummary,
    RatingManagementError,
    load_overall_rating_context,
)
from quillan.review_ratings import (
    ReviewRatingError,
    mark_overall_ratings_complete,
    set_overall_standard_rating,
)


def handle_ratings_list(args: argparse.Namespace) -> int:
    """Display teacher-entered overall ratings without writing."""
    try:
        context = load_overall_rating_context(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id
        )
        _print_rating_context(context)
        return 0
    except (OSError, ValueError, WorkspaceRootError, RatingManagementError) as error:
        return _error(error)


def handle_ratings_set(args: argparse.Namespace) -> int:
    """Create or replace one complete teacher-entered overall rating."""
    try:
        workspace_root = resolve_workspace_root()
        context = load_overall_rating_context(
            workspace_root, args.class_id, args.assignment_id, args.student_id
        )
        if not context.review_exists:
            raise ReviewRatingError(
                "A review record must exist before recording or completing ratings."
            )
        selected = next(
            (item for item in context.standards if item.standard_id == args.standard_id),
            None,
        )
        updated = set_overall_standard_rating(
            workspace_root,
            args.class_id,
            args.assignment_id,
            args.student_id,
            standard_id=args.standard_id,
            rating=args.rating,
            rationale=args.rationale,
            include_in_feedback=args.include_in_feedback,
        )
        if selected is not None:
            _print_observation_warning(selected, context.observations_complete)
        print_updated_overall_standard_rating(updated)
        return 0
    except (
        OSError,
        ValueError,
        WorkspaceRootError,
        RatingManagementError,
        ReviewRatingError,
    ) as error:
        return _error(error)


def handle_ratings_mark_complete(args: argparse.Namespace) -> int:
    """Explicitly mark overall ratings complete without prompting."""
    try:
        workspace_root = resolve_workspace_root()
        context = load_overall_rating_context(
            workspace_root, args.class_id, args.assignment_id, args.student_id
        )
        if not context.review_exists:
            raise ReviewRatingError(
                "A review record must exist before recording or completing ratings."
            )
        if context.missing_rating_count:
            print(
                "Warning: "
                f"{context.missing_rating_count} assignment Focus Standard rating(s) "
                "are missing; explicit completion will not create them."
            )
        completed = mark_overall_ratings_complete(
            workspace_root, args.class_id, args.assignment_id, args.student_id
        )
        print_completed_overall_standard_ratings(completed)
        if completed.missing_rating_count:
            print(
                "Warning: Ratings were marked complete with "
                f"{completed.missing_rating_count} missing rating(s); none were created."
            )
        return 0
    except (
        OSError,
        ValueError,
        WorkspaceRootError,
        RatingManagementError,
        ReviewRatingError,
    ) as error:
        return _error(error)


def _print_rating_context(context: OverallRatingContext) -> None:
    print("Overall Focus Standard ratings:")
    print(f"Class: {context.class_id}")
    print(f"Assignment: {context.assignment_id}")
    print(f"Student: {context.student_id}")
    print(f"Submission manifest: {context.submission_manifest_relative_path}")
    print(f"Review record: {context.review_record_relative_path}")
    print(f"Review record exists: {_yes_no(context.review_exists)}")
    print(f"Review state: {context.review_state}")
    print(f"Observations complete: {_yes_no(context.observations_complete)}")
    print(f"Overall ratings complete: {_yes_no(context.ratings_complete)}")
    if context.review_state == "returned_without_full_review":
        print("Completed workflow applicability: overall ratings not applicable")
        print("Stored ratings are shown below for audit visibility.")
    print(f"Assignment rating scale: {context.rating_scale_id}")
    for level in context.rating_scale_levels:
        print(f"- {level.value}: {level.label}")
    print(f"Assignment Focus Standards: {len(context.standards)}")
    print(f"Ratings recorded: {context.rating_count}")
    print(f"Ratings missing: {context.missing_rating_count}")
    if context.review_exists and all(
        item.observation_count == 0 for item in context.standards
    ):
        print("Warning: No supporting observations are recorded; ratings remain teacher-entered.")
    print()
    print("Assignment Focus Standards (configured order):")
    for item in context.standards:
        _print_standard(item)
    if context.stale_ratings:
        print()
        print("Unrecognized or stale stored ratings (audit only):")
        for stale_rating in context.stale_ratings:
            print(
                f"- {stale_rating.standard_id}: {stale_rating.rating}; "
                f"updated {stale_rating.updated_at}"
            )


def _print_standard(item: OverallRatingSummary) -> None:
    rating = (
        "not rated"
        if item.rating is None
        else f"{item.rating} ({item.rating_label or 'unrecognized assignment value'})"
    )
    feedback = (
        "not recorded"
        if item.include_in_feedback is None
        else _yes_no(item.include_in_feedback)
    )
    print(f"- Focus Standard: {item.standard_id}")
    print(f"  Overall rating: {rating}")
    print(f"  Rationale: {item.rationale or 'none'}")
    print(f"  Include in feedback: {feedback}")
    print(f"  Rating updated: {item.updated_at or 'not recorded'}")
    print(f"  Total review units: {item.total_review_units}")
    print(f"  Recorded observations: {item.observation_count}")
    print(f"  Applicable observations: {item.applicable_count}")
    print(f"  Not-applicable observations: {item.not_applicable_count}")
    print(f"  Evidence-present observations: {item.evidence_present_count}")
    print(f"  Evidence-missing observations: {item.evidence_missing_count}")
    print(f"  Observations marked for feedback: {item.included_for_feedback_count}")


def _print_observation_warning(
    selected: OverallRatingSummary, observations_complete: bool
) -> None:
    if selected.observation_count == 0:
        print(
            "Warning: No supporting observations are recorded for this Focus Standard; "
            "the teacher-entered rating was still recorded."
        )
    if not observations_complete:
        print(
            "Warning: Observations are not marked complete; this does not block an "
            "overall teacher-entered rating."
        )


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _error(error: Exception) -> int:
    print(f"Error: {error}")
    return 1

"""Direct, non-interactive Focus Standard feedback handlers."""

from __future__ import annotations

import argparse

from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import (
    print_added_feedback_comment,
    print_completed_feedback_composition,
    print_selected_reusable_feedback_comment,
    print_updated_standard_feedback_options,
)
from quillan.feedback_management import (
    FeedbackCompositionContext,
    FeedbackManagementError,
    FeedbackObservation,
    load_feedback_composition_context,
)
from quillan.focus_standard_comments import ALLOWED_PURPOSES
from quillan.review_feedback import (
    ReviewFeedbackError,
    add_custom_feedback_comment,
    mark_feedback_composed,
    select_reusable_feedback_comment,
    set_standard_feedback_options,
)


def handle_feedback_show(args: argparse.Namespace) -> int:
    try:
        context = load_feedback_composition_context(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id
        )
        _print_context(context)
        return 0
    except (OSError, ValueError, WorkspaceRootError, FeedbackManagementError) as error:
        return _error(error)


def handle_feedback_set_options(args: argparse.Namespace) -> int:
    try:
        result = set_standard_feedback_options(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id,
            standard_id=args.standard_id,
            include_overall_rating=args.include_overall_rating,
            include_overall_rationale=args.include_overall_rationale,
            included_observation_ids=_comma_separated(args.observation_ids, "observation IDs"),
        )
        print_updated_standard_feedback_options(result)
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewFeedbackError) as error:
        return _error(error)


def handle_feedback_add_comment(args: argparse.Namespace) -> int:
    try:
        reusable_values = (
            args.reusable_label,
            args.reusable_text,
            args.purpose,
            args.teacher_tags,
            args.tag_current_rating,
        )
        if not args.save_for_reuse and any(value is not None for value in reusable_values):
            raise ReviewFeedbackError(
                "Reusable-comment options require --save-for-reuse."
            )
        if args.save_for_reuse and args.reusable_label is None:
            raise ReviewFeedbackError("--reusable-label is required with --save-for-reuse.")
        purpose = args.purpose or "general"
        if purpose not in ALLOWED_PURPOSES:
            raise ReviewFeedbackError(
                f"purpose {purpose!r} is invalid; choose one of: "
                + ", ".join(sorted(ALLOWED_PURPOSES))
            )
        rating_values: list[int | float] | None = (
            None if args.tag_current_rating is True else []
        )
        result = add_custom_feedback_comment(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id,
            standard_id=args.standard_id,
            text=args.text,
            include_in_feedback=args.include_in_feedback,
            save_for_reuse=args.save_for_reuse,
            reusable_label=args.reusable_label,
            reusable_text=args.reusable_text,
            purpose=purpose,
            teacher_tags=(
                _comma_separated(args.teacher_tags, "teacher tags")
                if args.teacher_tags is not None else None
            ),
            rating_values=rating_values,
        )
        print_added_feedback_comment(result)
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewFeedbackError) as error:
        return _error(error)


def handle_feedback_use_reusable_comment(args: argparse.Namespace) -> int:
    try:
        result = select_reusable_feedback_comment(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id,
            standard_id=args.standard_id,
            comment_set_id=args.comment_set_id,
            comment_id=args.comment_id,
            include_in_feedback=args.include_in_feedback,
        )
        print_selected_reusable_feedback_comment(result)
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewFeedbackError) as error:
        return _error(error)


def handle_feedback_mark_composed(args: argparse.Namespace) -> int:
    try:
        if not args.yes:
            raise ReviewFeedbackError("--yes is required to mark feedback composed.")
        result = mark_feedback_composed(
            resolve_workspace_root(), args.class_id, args.assignment_id, args.student_id
        )
        print_completed_feedback_composition(result)
        if result.missing_standard_feedback_count:
            print("Warning: Feedback records are missing for one or more Focus Standards.")
        if result.missing_rating_count:
            print("Warning: Overall ratings are missing for one or more Focus Standards.")
        if result.selected_observation_count == 0:
            print("Warning: No review-unit observations are currently selected.")
        if result.included_comment_count == 0:
            print("Warning: No feedback comments are currently included.")
        if result.student_facing_content_count == 0:
            print("Warning: No student-facing feedback content is currently included.")
        return 0
    except (OSError, ValueError, WorkspaceRootError, ReviewFeedbackError) as error:
        return _error(error)


def _comma_separated(value: str | None, label: str) -> list[str]:
    if value is None or value == "":
        return []
    items = [item.strip() for item in value.split(",")]
    if any(not item for item in items):
        raise ReviewFeedbackError(f"{label} must not contain blank elements.")
    seen: set[str] = set()
    for item in items:
        if item in seen:
            raise ReviewFeedbackError(f"{label} contains duplicate {item!r}.")
        seen.add(item)
    return items


def _print_context(context: FeedbackCompositionContext) -> None:
    print("Focus Standard feedback composition:")
    print(f"Class: {context.class_id}")
    print(f"Assignment: {context.assignment_id}")
    print(f"Student: {context.student_id}")
    print(f"Submission manifest: {context.submission_manifest_relative_path}")
    print(f"Review record: {context.review_record_relative_path}")
    print(f"Review record exists: {_yes_no(context.review_exists)}")
    print(f"Review state: {context.review_state}")
    print(f"Ratings complete: {_yes_no(context.ratings_complete)}")
    print(f"Feedback composed: {_yes_no(context.feedback_composed)}")
    print(f"Focus Standards: {len(context.standards)}")
    print(f"Configured feedback records: {context.configured_feedback_count}")
    print(f"Missing feedback records: {context.missing_feedback_count}")
    print(f"Stale feedback records: {context.stale_feedback_count}")
    print(f"Comments: {context.comment_count}")
    print(f"Included comments: {context.included_comment_count}")
    print(f"Selected observations: {context.selected_observation_count}")
    print(f"Include review-unit observations: {_yes_no(context.include_review_unit_observations)}")
    print(f"Include overall standard ratings: {_yes_no(context.include_overall_standard_ratings)}")
    if context.returned_without_full_review:
        print("Notice: Full Focus Standard feedback composition is unavailable until the minimum-requirements outcome changes.")
    for index, standard in enumerate(context.standards, start=1):
        print()
        print(f"{index}. Focus Standard: {standard.standard_id}")
        rating = "not rated" if standard.rating is None else f"{standard.rating} ({standard.rating_label})"
        print(f"   Overall rating: {rating}")
        print(f"   Overall rationale: {standard.rationale or 'none'}")
        print(f"   Rating include in feedback: {_optional_bool(standard.rating_include_in_feedback)}")
        print(f"   Feedback record exists: {_yes_no(standard.has_feedback_record)}")
        print(f"   Include overall rating: {_optional_bool(standard.include_overall_rating)}")
        print(f"   Include overall rationale: {_optional_bool(standard.include_overall_rationale)}")
        print("   Selected observations:")
        _print_observations(standard.selected_observations)
        print("   Candidate observations:")
        _print_observations(standard.candidate_observations)
        print("   Existing comments:")
        if not standard.comments:
            print("   - none")
        for feedback_comment in standard.comments:
            print(f"   - {feedback_comment.feedback_comment_id} [{feedback_comment.source}]")
            print(f"     Text: {feedback_comment.text}")
            print(f"     Reusable comment set: {feedback_comment.reusable_comment_set_id or 'none'}")
            print(f"     Reusable comment: {feedback_comment.reusable_comment_id or 'none'}")
            print(f"     Save for reuse: {_yes_no(feedback_comment.save_for_reuse)}")
            print(f"     Include in feedback: {_yes_no(feedback_comment.include_in_feedback)}")
            print(f"     Created: {feedback_comment.created_at}")
        print("   Compatible reusable comments:")
        if not standard.reusable_comments:
            print("   - none")
        for reusable_comment in standard.reusable_comments:
            print(f"   - {reusable_comment.comment_set_id} / {reusable_comment.comment_id}: {reusable_comment.label}")
            print(f"     Text: {reusable_comment.text}")
            print(f"     Purpose: {reusable_comment.purpose}")
            print(f"     Writing types: {', '.join(reusable_comment.writing_types) or 'all'}")
            print(f"     Rating values: {', '.join(map(str, reusable_comment.rating_values)) or 'all'}")


def _print_observations(items: tuple[FeedbackObservation, ...]) -> None:
    if not items:
        print("   - none")
    for item in items:
        print(f"   - {item.observation_id}: {item.unit_label} ({item.unit_id})")
        print(f"     Applicable: {_yes_no(item.applicable)}")
        evidence = "not applicable" if item.evidence_present is None else _yes_no(item.evidence_present)
        print(f"     Evidence present: {evidence}")
        print(f"     Unit-level rating: {item.rating if item.rating is not None else 'none'}")
        print(f"     Rationale: {item.rationale or 'none'}")
        print(f"     Include in feedback: {_yes_no(item.include_in_feedback)}")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _optional_bool(value: bool | None) -> str:
    return "not configured" if value is None else _yes_no(value)


def _error(error: Exception) -> int:
    print(f"Error: {error}")
    return 1

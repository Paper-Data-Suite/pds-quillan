"""Immutable, read-only context for Focus Standard feedback composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quillan.focus_standard_comments import (
    FocusStandardCommentError,
    ReusableFocusStandardComment,
    lookup_comments,
)
from quillan.review_status_display import review_progress_status
from quillan.review_unit_management import (
    ReviewUnitManagementError,
    load_review_unit_context,
)


class FeedbackManagementError(ValueError):
    """Raised when feedback composition context cannot be loaded safely."""


@dataclass(frozen=True, slots=True)
class FeedbackObservation:
    observation_id: str
    unit_id: str
    unit_label: str
    applicable: bool
    evidence_present: bool | None
    rating: int | None
    rationale: str | None
    include_in_feedback: bool


@dataclass(frozen=True, slots=True)
class FeedbackComment:
    feedback_comment_id: str
    source: str
    text: str
    reusable_comment_id: str | None
    reusable_comment_set_id: str | None
    save_for_reuse: bool
    include_in_feedback: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class FocusStandardFeedback:
    standard_id: str
    rating: int | None
    rating_label: str | None
    rationale: str | None
    rating_include_in_feedback: bool | None
    has_feedback_record: bool
    include_overall_rating: bool | None
    include_overall_rationale: bool | None
    selected_observations: tuple[FeedbackObservation, ...]
    candidate_observations: tuple[FeedbackObservation, ...]
    comments: tuple[FeedbackComment, ...]
    reusable_comments: tuple[ReusableFocusStandardComment, ...]


@dataclass(frozen=True, slots=True)
class FeedbackCompositionContext:
    workspace_root: Path
    class_id: str
    assignment_id: str
    student_id: str
    submission_manifest_relative_path: str
    review_record_relative_path: str
    review_exists: bool
    review_state: str
    ratings_complete: bool
    feedback_composed: bool
    returned_without_full_review: bool
    standards: tuple[FocusStandardFeedback, ...]
    configured_feedback_count: int
    missing_feedback_count: int
    stale_feedback_count: int
    comment_count: int
    included_comment_count: int
    selected_observation_count: int
    include_review_unit_observations: bool
    include_overall_standard_ratings: bool


def load_feedback_composition_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> FeedbackCompositionContext:
    """Load feedback choices and compatible reusable comments without writing."""
    try:
        loaded = load_review_unit_context(
            workspace_root, class_id, assignment_id, student_id
        )
    except ReviewUnitManagementError as error:
        raise FeedbackManagementError(str(error)) from error

    assignment = loaded.assignment
    review = loaded.review
    standard_ids = tuple(assignment["focus_standard_ids"])
    rating_labels = {
        item["value"]: item["label"] for item in assignment["rating_scale"]["levels"]
    }
    ratings = {
        item["standard_id"]: item
        for item in (review["overall_standard_ratings"] if review else [])
    }
    feedback_records = review["feedback"]["standard_feedback"] if review else []
    feedback_by_standard = {item["standard_id"]: item for item in feedback_records}
    observations: dict[str, FeedbackObservation] = {}
    observations_by_standard: dict[str, list[FeedbackObservation]] = {}
    if review:
        for unit in sorted(review["review_units"], key=lambda item: item["sequence"]):
            for item in unit["standard_observations"]:
                observation = FeedbackObservation(
                    observation_id=item["observation_id"],
                    unit_id=unit["unit_id"],
                    unit_label=unit["label"],
                    applicable=item["applicable"],
                    evidence_present=item["evidence_present"],
                    rating=item["rating"],
                    rationale=item["rationale"],
                    include_in_feedback=item["include_in_feedback"],
                )
                observations[observation.observation_id] = observation
                observations_by_standard.setdefault(item["standard_id"], []).append(
                    observation
                )

    standards: list[FocusStandardFeedback] = []
    for standard_id in standard_ids:
        rating = ratings.get(standard_id)
        feedback = feedback_by_standard.get(standard_id)
        rating_value = rating["rating"] if rating else None
        try:
            reusable = lookup_comments(
                loaded.workspace_root,
                standards_profile_id=assignment["standards_profile_id"],
                writing_type=assignment["writing_type"],
                standard_id=standard_id,
                rating_value=rating_value,
            )
        except (OSError, FocusStandardCommentError) as error:
            raise FeedbackManagementError(str(error)) from error
        comments = tuple(
            FeedbackComment(
                feedback_comment_id=item["feedback_comment_id"],
                source=item["source"],
                text=item["text"],
                reusable_comment_id=item["reusable_comment_id"],
                reusable_comment_set_id=item["module_details"].get("comment_set_id"),
                save_for_reuse=item["save_for_reuse"],
                include_in_feedback=item["include_in_feedback"],
                created_at=item["created_at"],
            )
            for item in (feedback["comments"] if feedback else [])
        )
        selected = tuple(
            observations[item]
            for item in (feedback["included_observation_ids"] if feedback else [])
        )
        candidates = tuple(
            item
            for item in observations_by_standard.get(standard_id, [])
            if item.include_in_feedback
        )
        standards.append(
            FocusStandardFeedback(
                standard_id=standard_id,
                rating=rating_value,
                rating_label=rating_labels.get(rating_value),
                rationale=rating["rationale"] if rating else None,
                rating_include_in_feedback=rating["include_in_feedback"] if rating else None,
                has_feedback_record=feedback is not None,
                include_overall_rating=feedback["include_overall_rating"] if feedback else None,
                include_overall_rationale=feedback["include_overall_rationale"] if feedback else None,
                selected_observations=selected,
                candidate_observations=candidates,
                comments=comments,
                reusable_comments=reusable,
            )
        )

    configured = set(standard_ids)
    configured_count = sum(item["standard_id"] in configured for item in feedback_records)
    progress = review_progress_status(review)
    return FeedbackCompositionContext(
        workspace_root=loaded.workspace_root,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        submission_manifest_relative_path=loaded.submission_manifest_relative_path,
        review_record_relative_path=loaded.review_record_relative_path,
        review_exists=review is not None,
        review_state=loaded.review_state,
        ratings_complete=progress.ratings_complete,
        feedback_composed=progress.feedback_composed,
        returned_without_full_review=loaded.review_state == "returned_without_full_review",
        standards=tuple(standards),
        configured_feedback_count=configured_count,
        missing_feedback_count=len(standard_ids) - configured_count,
        stale_feedback_count=sum(item["standard_id"] not in configured for item in feedback_records),
        comment_count=sum(len(item["comments"]) for item in feedback_records),
        included_comment_count=sum(
            comment["include_in_feedback"]
            for item in feedback_records
            for comment in item["comments"]
        ),
        selected_observation_count=sum(
            len(item["included_observation_ids"]) for item in feedback_records
        ),
        include_review_unit_observations=(
            review["feedback"]["include_review_unit_observations"] if review else False
        ),
        include_overall_standard_ratings=(
            review["feedback"]["include_overall_standard_ratings"] if review else False
        ),
    )

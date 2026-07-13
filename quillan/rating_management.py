"""Immutable, read-only context for overall Focus Standard ratings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quillan.review_status_display import review_progress_status
from quillan.review_unit_management import (
    ReviewUnitManagementError,
    load_review_unit_context,
)


class RatingManagementError(ValueError):
    """Raised when overall-rating context cannot be loaded safely."""


@dataclass(frozen=True, slots=True)
class RatingScaleLevel:
    """One assignment-owned rating-scale level."""

    value: int
    label: str


@dataclass(frozen=True, slots=True)
class OverallRatingSummary:
    """Current rating and advisory observation counts for one Focus Standard."""

    standard_id: str
    rating: int | None
    rating_label: str | None
    rationale: str | None
    include_in_feedback: bool | None
    updated_at: str | None
    total_review_units: int
    observation_count: int
    applicable_count: int
    not_applicable_count: int
    evidence_present_count: int
    evidence_missing_count: int
    included_for_feedback_count: int


@dataclass(frozen=True, slots=True)
class StaleOverallRating:
    """A stored overall rating no longer configured by the assignment."""

    standard_id: str
    rating: int
    rationale: str | None
    include_in_feedback: bool
    updated_at: str


@dataclass(frozen=True, slots=True)
class OverallRatingContext:
    """Validated canonical read model for direct overall-rating display."""

    workspace_root: Path
    class_id: str
    assignment_id: str
    student_id: str
    submission_manifest_path: Path
    submission_manifest_relative_path: str
    review_record_path: Path
    review_record_relative_path: str
    review_exists: bool
    review_state: str
    observations_complete: bool
    ratings_complete: bool
    rating_scale_id: str
    rating_scale_levels: tuple[RatingScaleLevel, ...]
    standards: tuple[OverallRatingSummary, ...]
    stale_ratings: tuple[StaleOverallRating, ...]
    rating_count: int
    missing_rating_count: int


def load_overall_rating_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> OverallRatingContext:
    """Load overall ratings and observation counts without writing or scoring."""
    try:
        loaded = load_review_unit_context(
            workspace_root, class_id, assignment_id, student_id
        )
    except ReviewUnitManagementError as error:
        raise RatingManagementError(str(error)) from error

    assignment = loaded.assignment
    review = loaded.review
    focus_standard_ids = tuple(assignment["focus_standard_ids"])
    levels = tuple(
        RatingScaleLevel(value=level["value"], label=level["label"])
        for level in assignment["rating_scale"]["levels"]
    )
    labels = {level.value: level.label for level in levels}
    ratings = review["overall_standard_ratings"] if review is not None else []
    ratings_by_standard = {item["standard_id"]: item for item in ratings}
    units = review["review_units"] if review is not None else []

    standards: list[OverallRatingSummary] = []
    for standard_id in focus_standard_ids:
        observations = [
            observation
            for unit in units
            for observation in unit["standard_observations"]
            if observation["standard_id"] == standard_id
        ]
        applicable = [item for item in observations if item["applicable"]]
        current = ratings_by_standard.get(standard_id)
        rating = current["rating"] if current is not None else None
        standards.append(
            OverallRatingSummary(
                standard_id=standard_id,
                rating=rating,
                rating_label=labels.get(rating) if rating is not None else None,
                rationale=current["rationale"] if current is not None else None,
                include_in_feedback=(
                    current["include_in_feedback"] if current is not None else None
                ),
                updated_at=current["updated_at"] if current is not None else None,
                total_review_units=len(units),
                observation_count=len(observations),
                applicable_count=len(applicable),
                not_applicable_count=sum(not item["applicable"] for item in observations),
                evidence_present_count=sum(
                    item["evidence_present"] is True for item in applicable
                ),
                evidence_missing_count=sum(
                    item["evidence_present"] is False for item in applicable
                ),
                included_for_feedback_count=sum(
                    item["include_in_feedback"] for item in observations
                ),
            )
        )

    configured = set(focus_standard_ids)
    stale = tuple(
        StaleOverallRating(
            standard_id=item["standard_id"],
            rating=item["rating"],
            rationale=item["rationale"],
            include_in_feedback=item["include_in_feedback"],
            updated_at=item["updated_at"],
        )
        for item in ratings
        if item["standard_id"] not in configured
    )
    rating_count = sum(item.rating is not None for item in standards)
    progress = review_progress_status(review) if review is not None else None
    return OverallRatingContext(
        workspace_root=loaded.workspace_root,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        submission_manifest_path=loaded.submission_manifest_path,
        submission_manifest_relative_path=loaded.submission_manifest_relative_path,
        review_record_path=loaded.review_record_path,
        review_record_relative_path=loaded.review_record_relative_path,
        review_exists=review is not None,
        review_state=loaded.review_state,
        observations_complete=(progress.observations_complete if progress else False),
        ratings_complete=(progress.ratings_complete if progress else False),
        rating_scale_id=assignment["rating_scale"]["scale_id"],
        rating_scale_levels=levels,
        standards=tuple(standards),
        stale_ratings=stale,
        rating_count=rating_count,
        missing_rating_count=len(standards) - rating_count,
    )

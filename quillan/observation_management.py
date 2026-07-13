"""Read-only assignment-aware context for review-unit observations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quillan.review_unit_management import (
    ReviewUnitManagementError,
    load_review_unit_context,
)


class ObservationManagementError(ValueError):
    """Raised when observation context cannot be loaded safely."""


@dataclass(frozen=True, slots=True)
class ObservationRatingLevel:
    """One assignment-owned rating-scale level."""

    value: int
    label: str


@dataclass(frozen=True, slots=True)
class UnitStandardObservationStatus:
    """One deterministic review-unit and Focus Standard pair."""

    unit_sequence: int
    unit_id: str
    unit_label: str
    standard_id: str
    observation_id: str | None
    applicable: bool | None
    evidence_present: bool | None
    rating: int | None
    rating_label: str | None
    rationale: str | None
    include_in_feedback: bool | None
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class ObservationSummary:
    """Counts for active unit-standard observation pairs."""

    expected_pair_count: int
    recorded_count: int
    unrecorded_count: int
    applicable_count: int
    not_applicable_count: int
    evidence_present_count: int
    evidence_missing_count: int
    rating_count: int
    included_for_feedback_count: int


@dataclass(frozen=True, slots=True)
class ObservationContext:
    """Validated, read-only observation list context."""

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
    focus_standard_ids: tuple[str, ...]
    rating_scale_id: str
    rating_scale_levels: tuple[ObservationRatingLevel, ...]
    unit_count: int
    pairs: tuple[UnitStandardObservationStatus, ...]
    summary: ObservationSummary


def load_observation_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> ObservationContext:
    """Load every active unit-standard pair without writing or inspecting evidence."""
    try:
        loaded = load_review_unit_context(
            workspace_root, class_id, assignment_id, student_id
        )
    except ReviewUnitManagementError as error:
        raise ObservationManagementError(str(error)) from error

    assignment = loaded.assignment
    focus_standard_ids = tuple(str(value) for value in assignment["focus_standard_ids"])
    rating_levels = tuple(
        ObservationRatingLevel(value=level["value"], label=level["label"])
        for level in assignment["rating_scale"]["levels"]
    )
    rating_labels = {level.value: level.label for level in rating_levels}
    units: list[dict[str, Any]] = []
    if loaded.review is not None:
        units = sorted(loaded.review["review_units"], key=lambda unit: unit["sequence"])

    pairs: list[UnitStandardObservationStatus] = []
    for unit in units:
        observations = {
            observation["standard_id"]: observation
            for observation in unit["standard_observations"]
        }
        for standard_id in focus_standard_ids:
            observation = observations.get(standard_id)
            pairs.append(
                UnitStandardObservationStatus(
                    unit_sequence=unit["sequence"],
                    unit_id=unit["unit_id"],
                    unit_label=unit["label"],
                    standard_id=standard_id,
                    observation_id=(
                        observation["observation_id"] if observation is not None else None
                    ),
                    applicable=(observation["applicable"] if observation is not None else None),
                    evidence_present=(
                        observation["evidence_present"] if observation is not None else None
                    ),
                    rating=observation["rating"] if observation is not None else None,
                    rating_label=(
                        rating_labels.get(observation["rating"])
                        if observation is not None and observation["rating"] is not None
                        else None
                    ),
                    rationale=observation["rationale"] if observation is not None else None,
                    include_in_feedback=(
                        observation["include_in_feedback"]
                        if observation is not None
                        else None
                    ),
                    updated_at=observation["updated_at"] if observation is not None else None,
                )
            )

    recorded = [pair for pair in pairs if pair.observation_id is not None]
    applicable = [pair for pair in recorded if pair.applicable is True]
    summary = ObservationSummary(
        expected_pair_count=len(pairs),
        recorded_count=len(recorded),
        unrecorded_count=len(pairs) - len(recorded),
        applicable_count=len(applicable),
        not_applicable_count=sum(pair.applicable is False for pair in recorded),
        evidence_present_count=sum(pair.evidence_present is True for pair in applicable),
        evidence_missing_count=sum(pair.evidence_present is False for pair in applicable),
        rating_count=sum(pair.rating is not None for pair in applicable),
        included_for_feedback_count=sum(
            pair.include_in_feedback is True for pair in recorded
        ),
    )
    return ObservationContext(
        workspace_root=loaded.workspace_root,
        class_id=loaded.class_id,
        assignment_id=loaded.assignment_id,
        student_id=loaded.student_id,
        submission_manifest_path=loaded.submission_manifest_path,
        submission_manifest_relative_path=loaded.submission_manifest_relative_path,
        review_record_path=loaded.review_record_path,
        review_record_relative_path=loaded.review_record_relative_path,
        review_exists=loaded.review is not None,
        review_state=loaded.review_state,
        focus_standard_ids=focus_standard_ids,
        rating_scale_id=str(assignment["rating_scale"]["scale_id"]),
        rating_scale_levels=rating_levels,
        unit_count=len(units),
        pairs=tuple(pairs),
        summary=summary,
    )

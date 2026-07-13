"""Workspace-aware services for canonical Quillan assignment configs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pds_core.classes import load_class_roster
from pds_core.identifiers import validate_identifier
from pds_core.standards import load_workspace_standards_library

from quillan.assignments import (
    AssignmentConfigError,
    load_assignment_config,
    validate_assignment_standards_selection,
)
from quillan.assignment_workflows import (
    build_assignment_config,
    default_rating_scale,
    default_review_unit,
    normalize_writing_type,
    write_assignment_config,
)
from quillan.storage import assignment_config_path


@dataclass(frozen=True)
class AssignmentPlan:
    """A validated assignment and its canonical output path."""

    workspace_root: Path
    class_id: str
    assignment_id: str
    path: Path
    assignment: dict[str, Any]


def plan_assignment_creation(
    workspace_root: str | Path,
    *,
    class_id: str,
    assignment_id: str,
    title: str,
    writing_type: str,
    student_prompt: str,
    standards_profile_id: str,
    focus_standard_ids: list[str],
    review_unit: dict[str, Any] | None = None,
    rating_scale: dict[str, Any] | None = None,
    basic_requirements: dict[str, Any] | None = None,
    allow_return_without_full_review: bool = True,
) -> AssignmentPlan:
    """Validate creation inputs without creating directories or files."""
    root = Path(workspace_root).resolve(strict=False)
    validate_identifier(class_id, "class_id")
    validate_identifier(assignment_id, "assignment_id")
    load_class_roster(root, class_id)
    assignment = build_assignment_config(
        assignment_id=assignment_id,
        title=title,
        class_id=class_id,
        writing_type=normalize_writing_type(writing_type),
        student_prompt=student_prompt,
        standards_profile_id=standards_profile_id,
        focus_standard_ids=focus_standard_ids,
        review_unit=review_unit or default_review_unit(),
        rating_scale=rating_scale or default_rating_scale(),
        basic_requirements=basic_requirements or {},
        minimum_requirement_policy={
            "allow_return_without_full_review": allow_return_without_full_review
        },
    )
    library = load_workspace_standards_library(root)
    validate_assignment_standards_selection(assignment, library)
    return AssignmentPlan(
        workspace_root=root,
        class_id=class_id,
        assignment_id=assignment_id,
        path=assignment_config_path(root, class_id, assignment_id),
        assignment=assignment,
    )


def create_assignment(plan: AssignmentPlan, *, overwrite: bool = False) -> Path:
    """Write one prevalidated assignment to its canonical path."""
    return write_assignment_config(
        plan.workspace_root,
        plan.class_id,
        plan.assignment,
        overwrite=overwrite,
    )


def load_canonical_assignment(
    workspace_root: str | Path, class_id: str, assignment_id: str
) -> AssignmentPlan:
    """Load and check one canonical assignment's path identity."""
    root = Path(workspace_root).resolve(strict=False)
    validate_identifier(class_id, "class_id")
    validate_identifier(assignment_id, "assignment_id")
    path = assignment_config_path(root, class_id, assignment_id)
    assignment = load_assignment_config(path)
    if assignment["assignment_id"] != assignment_id:
        raise AssignmentConfigError(
            "Path assignment_id does not match assignment config assignment_id."
        )
    if class_id not in assignment["class_ids"]:
        raise AssignmentConfigError(
            "Path class_id is not included in assignment config class_ids."
        )
    return AssignmentPlan(root, class_id, assignment_id, path, assignment)


def validate_canonical_assignment(plan: AssignmentPlan) -> None:
    """Validate a canonical assignment against workspace standards."""
    library = load_workspace_standards_library(plan.workspace_root)
    validate_assignment_standards_selection(plan.assignment, library)

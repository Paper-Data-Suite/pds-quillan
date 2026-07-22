"""Assignment-aware minimum-requirement review application services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quillan.review_requirements import (
    ReviewRequirementError,
    UpdatedMinimumRequirementOutcome,
    UpdatedRequirementCheck,
    set_minimum_requirement_outcome,
    set_requirement_check,
)
from quillan.submission_guidance import missing_submission_guidance
from quillan.record_context import (
    MissingSubmissionError,
    QuillanRecordContextError,
    ReviewLoadingPolicy,
    load_quillan_student_review_context,
    mutable_json_copy,
)
from quillan.work_paths import quillan_work_ref

ExpectedValue = str | int | float
OUTCOME_STATUSES = (
    "met",
    "unmet_continue_review",
    "returned_without_full_review",
)


@dataclass(frozen=True, slots=True)
class ConfiguredRequirement:
    """One canonical requirement derived from an assignment."""

    key: str
    label: str
    expected: ExpectedValue
    question: str
    detail: str


@dataclass(frozen=True, slots=True)
class MinimumRequirementReviewSummary:
    """Counts for currently configured requirements only."""

    total: int
    checked: int
    unchecked: int
    met: int
    unmet: int


@dataclass(frozen=True, slots=True)
class MinimumRequirementReviewContext:
    """Validated canonical assignment, submission, and optional review context."""

    workspace_root: Path
    class_id: str
    assignment_id: str
    student_id: str
    assignment_path: Path
    submission_manifest_path: Path
    review_record_path: Path
    assignment: dict[str, Any]
    requirements: tuple[ConfiguredRequirement, ...]
    review: dict[str, Any] | None
    checks: tuple[dict[str, Any], ...]
    summary: MinimumRequirementReviewSummary
    allow_return_without_full_review: bool

    @property
    def review_record_relative_path(self) -> str:
        return _workspace_relative_path(
            self.review_record_path, self.workspace_root, "review record"
        )

    @property
    def submission_manifest_relative_path(self) -> str:
        return _workspace_relative_path(
            self.submission_manifest_path, self.workspace_root, "submission manifest"
        )

    @property
    def configured_checks(self) -> dict[str, dict[str, Any]]:
        keys = {requirement.key for requirement in self.requirements}
        return {
            str(check["requirement_key"]): check
            for check in self.checks
            if check.get("requirement_key") in keys
        }

    @property
    def stale_checks(self) -> tuple[dict[str, Any], ...]:
        keys = {requirement.key for requirement in self.requirements}
        return tuple(
            check for check in self.checks if check.get("requirement_key") not in keys
        )


@dataclass(frozen=True, slots=True)
class SetConfiguredRequirementCheckResult:
    """Assignment-aware result for a requirement-check write."""

    requirement: ConfiguredRequirement
    update: UpdatedRequirementCheck
    teacher_note: str | None


def configured_requirements(
    assignment: dict[str, Any],
) -> tuple[ConfiguredRequirement, ...]:
    """Derive canonical configured requirements in teacher-facing order."""
    basic = assignment.get("basic_requirements")
    if not isinstance(basic, dict):
        return ()
    specs = (
        (
            "paragraphs_min",
            "Minimum paragraphs",
            "Does the submission meet the minimum paragraph requirement?",
            "Minimum: {value} paragraphs",
        ),
        (
            "paragraphs_max",
            "Maximum paragraphs",
            "Does the submission stay within the maximum paragraph requirement?",
            "Maximum: {value} paragraphs",
        ),
        (
            "word_count_min",
            "Minimum word count",
            "Does the submission meet the minimum word count?",
            "Minimum: {value} words",
        ),
        (
            "word_count_max",
            "Maximum word count",
            "Does the submission stay within the maximum word count?",
            "Maximum: {value} words",
        ),
    )
    items: list[ConfiguredRequirement] = []
    for key, label, question, detail_template in specs:
        value = basic.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            items.append(
                ConfiguredRequirement(
                    key=key,
                    label=label,
                    expected=value,
                    question=question,
                    detail=detail_template.format(value=value),
                )
            )
    elements = basic.get("required_elements")
    if isinstance(elements, list):
        for element in elements:
            if isinstance(element, str) and element.strip():
                value = element.strip()
                items.append(
                    ConfiguredRequirement(
                        key=f"required_elements:{value}",
                        label=f"Required element: {value}",
                        expected=value,
                        question="Does the submission include this required element?",
                        detail=f"Required element: {value}",
                    )
                )
    return tuple(items)


def summarize_minimum_requirements(
    requirements: tuple[ConfiguredRequirement, ...] | list[ConfiguredRequirement],
    checks: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> MinimumRequirementReviewSummary:
    """Summarize checks that still correspond to configured requirements."""
    keys = {requirement.key for requirement in requirements}
    relevant = [check for check in checks if check.get("requirement_key") in keys]
    checked = len(relevant)
    return MinimumRequirementReviewSummary(
        total=len(requirements),
        checked=checked,
        unchecked=len(requirements) - checked,
        met=sum(check.get("met") is True for check in relevant),
        unmet=sum(check.get("met") is False for check in relevant),
    )


def available_minimum_requirement_outcomes(
    summary: MinimumRequirementReviewSummary,
    *,
    allow_return_without_full_review: bool,
) -> tuple[str, ...]:
    """Return assignment-aware outcomes currently available to a teacher."""
    outcomes: list[str] = []
    if summary.total and summary.checked == summary.total and summary.unmet == 0:
        outcomes.append("met")
    if summary.unmet:
        outcomes.append("unmet_continue_review")
        if allow_return_without_full_review:
            outcomes.append("returned_without_full_review")
    return tuple(outcomes)


def allows_return_without_full_review(assignment: dict[str, Any]) -> bool:
    """Return the canonical assignment-policy decision for returned work."""
    policy = assignment.get("minimum_requirement_policy")
    return (
        isinstance(policy, dict)
        and policy.get("allow_return_without_full_review") is True
    )


def load_minimum_requirement_review_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> MinimumRequirementReviewContext:
    """Load and validate canonical assignment, submission, and optional review."""
    try:
        loaded = load_quillan_student_review_context(
            workspace_root,
            quillan_work_ref(class_id, assignment_id),
            student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
        )
    except MissingSubmissionError as error:
        raise ReviewRequirementError(missing_submission_guidance()) from error
    except QuillanRecordContextError as error:
        raise ReviewRequirementError(str(error)) from error
    root = loaded.paths.workspace_root
    assignment_path = loaded.assignment_context.paths.assignment_path
    manifest_path = loaded.paths.submission_manifest_path
    record_path = loaded.paths.review_record_path
    assignment = mutable_json_copy(loaded.assignment_context.assignment)
    review = None if loaded.review is None else mutable_json_copy(loaded.review)
    checks: tuple[dict[str, Any], ...] = ()
    if review is not None:
        checks = tuple(review["minimum_requirement_checks"])

    requirements = configured_requirements(assignment)
    allow_return = allows_return_without_full_review(assignment)
    return MinimumRequirementReviewContext(
        workspace_root=root,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        assignment_path=assignment_path,
        submission_manifest_path=manifest_path,
        review_record_path=record_path,
        assignment=assignment,
        requirements=requirements,
        review=review,
        checks=checks,
        summary=summarize_minimum_requirements(requirements, checks),
        allow_return_without_full_review=allow_return,
    )


def set_configured_requirement_check(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    requirement_key: str,
    met: bool,
    teacher_note: str | None = None,
) -> SetConfiguredRequirementCheckResult:
    """Resolve and set one currently configured teacher-entered check."""
    context = load_minimum_requirement_review_context(
        workspace_root, class_id, assignment_id, student_id
    )
    if not context.requirements:
        raise ReviewRequirementError("This assignment has no configured minimum requirements.")
    requirement = next(
        (item for item in context.requirements if item.key == requirement_key), None
    )
    if requirement is None:
        valid = ", ".join(item.key for item in context.requirements)
        raise ReviewRequirementError(
            f"Unknown or unconfigured requirement key {requirement_key!r}. Valid keys: {valid}."
        )
    update = set_requirement_check(
        context.workspace_root,
        class_id,
        assignment_id,
        student_id,
        requirement_key=requirement.key,
        label=requirement.label,
        expected=requirement.expected,
        met=met,
        teacher_note=teacher_note,
    )
    normalized_note = teacher_note.strip() if teacher_note is not None else None
    return SetConfiguredRequirementCheckResult(requirement, update, normalized_note)


def set_configured_minimum_requirement_outcome(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    status: str,
    teacher_note: str | None = None,
) -> UpdatedMinimumRequirementOutcome:
    """Validate assignment-aware eligibility and set the selected outcome."""
    context = load_minimum_requirement_review_context(
        workspace_root, class_id, assignment_id, student_id
    )
    if status not in OUTCOME_STATUSES:
        raise ReviewRequirementError(
            "status must be one of: met, unmet_continue_review, returned_without_full_review."
        )
    if not context.requirements:
        raise ReviewRequirementError("This assignment has no configured minimum requirements.")
    available = available_minimum_requirement_outcomes(
        context.summary,
        allow_return_without_full_review=context.allow_return_without_full_review,
    )
    if status not in available:
        if status == "met":
            reason = "every configured requirement must be checked and met"
        elif status == "unmet_continue_review":
            reason = "at least one configured requirement must be checked and not met"
        elif not context.allow_return_without_full_review:
            reason = "assignment policy does not allow returning without full review"
        else:
            reason = "at least one configured requirement must be checked and not met"
        raise ReviewRequirementError(f"Outcome {status!r} is unavailable: {reason}.")
    return set_minimum_requirement_outcome(
        context.workspace_root,
        class_id,
        assignment_id,
        student_id,
        status=status,
        teacher_note=teacher_note,
        allow_return_without_full_review=context.allow_return_without_full_review,
    )


def _validate_identity(
    record: dict[str, Any],
    name: str,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    for field, expected in (
        ("class_id", class_id),
        ("assignment_id", assignment_id),
        ("student_id", student_id),
    ):
        if record[field] != expected:
            raise ReviewRequirementError(
                f"{name} {field} is {record[field]!r}, expected {expected!r}."
            )


def _workspace_relative_path(path: Path, root: Path, description: str) -> str:
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise ReviewRequirementError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error

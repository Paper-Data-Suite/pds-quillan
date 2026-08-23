"""Safe assignment-level planning and execution for student feedback batches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from quillan.feedback_export import (
    FeedbackExportError,
    export_student_feedback,
    export_student_feedback_pdf,
)
from quillan.review_work_queue import (
    AssignmentReviewWorkQueue,
    ReviewWorkQueueError,
    ReviewWorkQueueItem,
    build_assignment_review_work_queue,
)
from quillan.student_review_status import (
    StudentReviewStatusError,
    build_student_review_status,
    student_review_status_to_dict,
)

BatchScope = Literal["completed", "selected"]
FeedbackFormat = Literal["pdf", "markdown", "both"]
OverwritePolicy = Literal["none", "stale", "all"]
PlanAction = Literal[
    "create",
    "replace",
    "skip_current",
    "blocked_incomplete",
    "blocked_attention",
    "blocked_conflict",
    "blocked_unknown_state",
]
ResultOutcome = Literal[
    "created",
    "replaced",
    "skipped_current",
    "skipped_by_policy",
    "blocked_incomplete",
    "blocked_attention",
    "blocked_unknown_state",
    "state_changed",
    "export_failed",
    "verification_failed",
]

EXPORT_CAPABLE_CATEGORIES: Final = frozenset({"export_pending", "complete"})
_REQUESTED_EXPORT_KEYS: Final = {
    "pdf": ("feedback_pdf",),
    "markdown": ("feedback_markdown",),
    "both": ("feedback_pdf", "feedback_markdown"),
}
_ALLOWED_STATUSES: Final = frozenset({"present", "stale", "missing", "unknown"})


class BatchFeedbackExportError(ValueError):
    """Raised when a batch cannot be planned or started safely."""


@dataclass(frozen=True, slots=True)
class BatchFeedbackExportStudentPlan:
    """One roster student's read-only batch-export decision."""

    student_id: str
    display_name: str
    category: str
    reason_code: str
    warnings: tuple[str, ...]
    review_updated_at: str | None
    requested_export_statuses: tuple[tuple[str, str], ...]
    action: PlanAction


@dataclass(frozen=True, slots=True)
class BatchFeedbackExportPlan:
    """Immutable preview of one exact assignment-level export batch."""

    class_id: str
    assignment_id: str
    assignment_title: str
    scope: BatchScope
    feedback_format: FeedbackFormat
    overwrite_policy: OverwritePolicy
    roster_count: int
    excluded_incomplete_count: int
    excluded_attention_count: int
    items: tuple[BatchFeedbackExportStudentPlan, ...]

    @property
    def writable_count(self) -> int:
        return sum(item.action in {"create", "replace"} for item in self.items)


@dataclass(frozen=True, slots=True)
class BatchFeedbackExportStudentResult:
    """One student's bounded execution or skip outcome."""

    student_id: str
    display_name: str
    outcome: ResultOutcome
    message: str
    artifact_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BatchFeedbackExportResult:
    """Immutable result for one confirmed batch execution."""

    class_id: str
    assignment_id: str
    feedback_format: FeedbackFormat
    overwrite_policy: OverwritePolicy
    items: tuple[BatchFeedbackExportStudentResult, ...]

    @property
    def failure_count(self) -> int:
        return sum(
            item.outcome
            in {"state_changed", "export_failed", "verification_failed"}
            for item in self.items
        )


@dataclass(frozen=True, slots=True)
class _StudentExportSnapshot:
    """Current bounded export state for one exact student."""

    review_updated_at: str | None
    statuses: tuple[tuple[str, str], ...]
    file_present: tuple[tuple[str, bool], ...]
    metadata_present: tuple[tuple[str, bool], ...]
    source_review_updated_at: tuple[tuple[str, str | None], ...]
    paths: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...]


def build_batch_feedback_export_plan(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    scope: BatchScope,
    feedback_format: FeedbackFormat,
    overwrite_policy: OverwritePolicy = "none",
    student_ids: tuple[str, ...] = (),
) -> BatchFeedbackExportPlan:
    """Build a deterministic, read-only batch preview from canonical state."""
    _validate_options(scope, feedback_format, overwrite_policy, student_ids)
    try:
        queue = build_assignment_review_work_queue(
            workspace_root, class_id, assignment_id
        )
    except (ReviewWorkQueueError, OSError, ValueError) as error:
        raise BatchFeedbackExportError(str(error)) from error

    selected_ids = _selected_ids(queue, scope=scope, student_ids=student_ids)
    selected_set = set(selected_ids)
    queue_by_id = {item.student_id: item for item in queue.items}
    items: list[BatchFeedbackExportStudentPlan] = []
    for student_id in selected_ids:
        queue_item = queue_by_id[student_id]
        items.append(
            _plan_student(
                workspace_root,
                queue_item,
                feedback_format=feedback_format,
                overwrite_policy=overwrite_policy,
            )
        )

    if scope == "completed":
        excluded = [item for item in queue.items if item.student_id not in selected_set]
        excluded_attention = sum(
            item.category == "attention_required" for item in excluded
        )
        excluded_incomplete = len(excluded) - excluded_attention
    else:
        excluded_attention = 0
        excluded_incomplete = 0

    return BatchFeedbackExportPlan(
        class_id=queue.class_id,
        assignment_id=queue.assignment_id,
        assignment_title=queue.assignment_title,
        scope=scope,
        feedback_format=feedback_format,
        overwrite_policy=overwrite_policy,
        roster_count=queue.roster_count,
        excluded_incomplete_count=excluded_incomplete,
        excluded_attention_count=excluded_attention,
        items=tuple(items),
    )


def execute_batch_feedback_export(
    workspace_root: str | Path,
    plan: BatchFeedbackExportPlan,
) -> BatchFeedbackExportResult:
    """Execute only the confirmed writable plan items, isolating student failures."""
    root = Path(workspace_root)
    try:
        initial_queue = build_assignment_review_work_queue(
            root, plan.class_id, plan.assignment_id
        )
    except (ReviewWorkQueueError, OSError, ValueError) as error:
        raise BatchFeedbackExportError(
            f"Batch execution preflight failed: {error}"
        ) from error
    if initial_queue.assignment_title != plan.assignment_title:
        raise BatchFeedbackExportError(
            "Batch execution preflight failed: assignment context changed."
        )

    results: list[BatchFeedbackExportStudentResult] = []
    for item in plan.items:
        if item.action not in {"create", "replace"}:
            results.append(_non_write_result(item))
            continue

        try:
            current_item = _current_queue_item(root, plan, item.student_id)
            current_snapshot = _load_student_export_snapshot(
                root,
                plan.class_id,
                plan.assignment_id,
                item.student_id,
            )
        except (BatchFeedbackExportError, OSError, ValueError) as error:
            results.append(
                _result(item, "state_changed", f"state changed: {error}")
            )
            continue

        if not _matches_confirmed_state(item, current_item, current_snapshot):
            results.append(
                _result(
                    item,
                    "state_changed",
                    "state changed after preview; export was not attempted",
                )
            )
            continue

        try:
            _run_student_export(root, plan, item)
        except (FeedbackExportError, OSError, RuntimeError, ValueError) as error:
            results.append(_result(item, "export_failed", str(error)))
            continue

        try:
            paths = _verify_student_export(root, plan, item.student_id)
        except (BatchFeedbackExportError, OSError, ValueError) as error:
            results.append(_result(item, "verification_failed", str(error)))
            continue

        outcome: ResultOutcome = "replaced" if item.action == "replace" else "created"
        results.append(
            BatchFeedbackExportStudentResult(
                student_id=item.student_id,
                display_name=item.display_name,
                outcome=outcome,
                message="verified current canonical feedback export",
                artifact_paths=paths,
            )
        )

    return BatchFeedbackExportResult(
        class_id=plan.class_id,
        assignment_id=plan.assignment_id,
        feedback_format=plan.feedback_format,
        overwrite_policy=plan.overwrite_policy,
        items=tuple(results),
    )


def _validate_options(
    scope: str,
    feedback_format: str,
    overwrite_policy: str,
    student_ids: tuple[str, ...],
) -> None:
    if scope not in {"completed", "selected"}:
        raise BatchFeedbackExportError(f"Unsupported batch scope: {scope!r}")
    if feedback_format not in _REQUESTED_EXPORT_KEYS:
        raise BatchFeedbackExportError(
            f"Unsupported feedback format: {feedback_format!r}"
        )
    if overwrite_policy not in {"none", "stale", "all"}:
        raise BatchFeedbackExportError(
            f"Unsupported overwrite policy: {overwrite_policy!r}"
        )
    if scope == "completed" and student_ids:
        raise BatchFeedbackExportError(
            "Completed scope does not accept explicit student IDs."
        )
    if scope == "selected" and not student_ids:
        raise BatchFeedbackExportError(
            "Selected scope requires at least one explicit student ID."
        )
    if len(set(student_ids)) != len(student_ids):
        raise BatchFeedbackExportError("Explicit student IDs must be unique.")


def _selected_ids(
    queue: AssignmentReviewWorkQueue,
    *,
    scope: BatchScope,
    student_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if scope == "completed":
        return tuple(
            item.student_id
            for item in queue.items
            if item.category in EXPORT_CAPABLE_CATEGORIES
        )

    known = {item.student_id for item in queue.items}
    unknown = tuple(student_id for student_id in student_ids if student_id not in known)
    if unknown:
        joined = ", ".join(unknown)
        raise BatchFeedbackExportError(
            f"Explicit selection contains unknown roster student IDs: {joined}"
        )
    requested = set(student_ids)
    return tuple(
        item.student_id for item in queue.items if item.student_id in requested
    )


def _plan_student(
    workspace_root: str | Path,
    item: ReviewWorkQueueItem,
    *,
    feedback_format: FeedbackFormat,
    overwrite_policy: OverwritePolicy,
) -> BatchFeedbackExportStudentPlan:
    if item.category == "attention_required":
        return _student_plan(item, action="blocked_attention")
    if item.category not in EXPORT_CAPABLE_CATEGORIES:
        return _student_plan(item, action="blocked_incomplete")

    try:
        snapshot = _load_student_export_snapshot(
            workspace_root,
            item.class_id,
            item.assignment_id,
            item.student_id,
        )
    except (BatchFeedbackExportError, OSError, ValueError):
        return _student_plan(item, action="blocked_unknown_state")

    requested = _requested_statuses(snapshot, feedback_format)
    action = _planned_action(
        feedback_format,
        overwrite_policy,
        tuple(status for _, status in requested),
    )
    return BatchFeedbackExportStudentPlan(
        student_id=item.student_id,
        display_name=item.display_name,
        category=item.category,
        reason_code=item.reason_code,
        warnings=tuple(dict.fromkeys((*item.warnings, *snapshot.warnings))),
        review_updated_at=snapshot.review_updated_at,
        requested_export_statuses=requested,
        action=action,
    )


def _student_plan(
    item: ReviewWorkQueueItem,
    *,
    action: PlanAction,
) -> BatchFeedbackExportStudentPlan:
    return BatchFeedbackExportStudentPlan(
        student_id=item.student_id,
        display_name=item.display_name,
        category=item.category,
        reason_code=item.reason_code,
        warnings=item.warnings,
        review_updated_at=None,
        requested_export_statuses=(),
        action=action,
    )


def _planned_action(
    feedback_format: FeedbackFormat,
    overwrite_policy: OverwritePolicy,
    statuses: tuple[str, ...],
) -> PlanAction:
    if not statuses or any(status not in _ALLOWED_STATUSES for status in statuses):
        return "blocked_unknown_state"
    if "unknown" in statuses:
        return "blocked_unknown_state"

    all_missing = all(status == "missing" for status in statuses)
    all_present = all(status == "present" for status in statuses)
    any_stale = "stale" in statuses
    any_existing = any(status in {"present", "stale"} for status in statuses)

    if all_missing:
        return "create"
    if overwrite_policy == "all" and any_existing:
        return "replace"
    if overwrite_policy == "stale" and any_stale:
        return "replace"
    if all_present:
        return "skip_current"

    # A combined export is coupled: a current companion plus a missing companion
    # cannot be updated safely without replacing the existing companion too.
    if feedback_format == "both":
        return "blocked_conflict"
    if any_stale or any_existing:
        return "blocked_conflict"
    return "blocked_unknown_state"


def _load_student_export_snapshot(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> _StudentExportSnapshot:
    try:
        status = build_student_review_status(
            workspace_root, class_id, assignment_id, student_id
        )
    except StudentReviewStatusError as error:
        raise BatchFeedbackExportError(str(error)) from error
    document = student_review_status_to_dict(status)
    if (
        document["class_id"] != class_id
        or document["assignment_id"] != assignment_id
        or document["student_id"] != student_id
    ):
        raise BatchFeedbackExportError("Student review status identity mismatch.")

    review = cast(dict[str, Any], document["review"])
    exports = cast(dict[str, Any], review["exports"])
    statuses: list[tuple[str, str]] = []
    file_present: list[tuple[str, bool]] = []
    metadata_present: list[tuple[str, bool]] = []
    sources: list[tuple[str, str | None]] = []
    paths: list[tuple[str, str]] = []
    for key in ("feedback_pdf", "feedback_markdown"):
        export = cast(dict[str, Any], exports[key])
        statuses.append((key, str(export["status"])))
        file_present.append((key, bool(export["file_present"])))
        metadata_present.append((key, bool(export["metadata_present"])))
        source = export["source_review_updated_at"]
        sources.append((key, None if source is None else str(source)))
        paths.append((key, str(export["path"])))
    warnings = cast(list[str], document["warnings"])
    updated_at = review["updated_at"]
    return _StudentExportSnapshot(
        review_updated_at=None if updated_at is None else str(updated_at),
        statuses=tuple(statuses),
        file_present=tuple(file_present),
        metadata_present=tuple(metadata_present),
        source_review_updated_at=tuple(sources),
        paths=tuple(paths),
        warnings=tuple(str(value) for value in warnings),
    )


def _requested_statuses(
    snapshot: _StudentExportSnapshot,
    feedback_format: FeedbackFormat,
) -> tuple[tuple[str, str], ...]:
    status_by_key = dict(snapshot.statuses)
    return tuple(
        (key, status_by_key[key]) for key in _REQUESTED_EXPORT_KEYS[feedback_format]
    )


def _current_queue_item(
    workspace_root: Path,
    plan: BatchFeedbackExportPlan,
    student_id: str,
) -> ReviewWorkQueueItem:
    try:
        queue = build_assignment_review_work_queue(
            workspace_root, plan.class_id, plan.assignment_id
        )
    except (ReviewWorkQueueError, OSError, ValueError) as error:
        raise BatchFeedbackExportError(str(error)) from error
    current = next(
        (item for item in queue.items if item.student_id == student_id),
        None,
    )
    if current is None:
        raise BatchFeedbackExportError(
            f"Student is no longer in the canonical roster: {student_id}"
        )
    return current


def _matches_confirmed_state(
    planned: BatchFeedbackExportStudentPlan,
    current_item: ReviewWorkQueueItem,
    current_snapshot: _StudentExportSnapshot,
) -> bool:
    if current_item.category != planned.category:
        return False
    if current_item.category not in EXPORT_CAPABLE_CATEGORIES:
        return False
    if current_snapshot.review_updated_at != planned.review_updated_at:
        return False
    planned_statuses = dict(planned.requested_export_statuses)
    current_statuses = dict(current_snapshot.statuses)
    return all(
        current_statuses.get(key) == value
        for key, value in planned_statuses.items()
    )


def _run_student_export(
    workspace_root: Path,
    plan: BatchFeedbackExportPlan,
    item: BatchFeedbackExportStudentPlan,
) -> None:
    overwrite = item.action == "replace"
    if plan.feedback_format == "markdown":
        export_student_feedback(
            workspace_root,
            plan.class_id,
            plan.assignment_id,
            item.student_id,
            overwrite=overwrite,
        )
        return
    export_student_feedback_pdf(
        workspace_root,
        plan.class_id,
        plan.assignment_id,
        item.student_id,
        overwrite=overwrite,
        include_markdown_companion=plan.feedback_format == "both",
    )


def _verify_student_export(
    workspace_root: Path,
    plan: BatchFeedbackExportPlan,
    student_id: str,
) -> tuple[str, ...]:
    snapshot = _load_student_export_snapshot(
        workspace_root, plan.class_id, plan.assignment_id, student_id
    )
    status_by_key = dict(snapshot.statuses)
    file_by_key = dict(snapshot.file_present)
    metadata_by_key = dict(snapshot.metadata_present)
    source_by_key = dict(snapshot.source_review_updated_at)
    path_by_key = dict(snapshot.paths)
    requested_keys = _REQUESTED_EXPORT_KEYS[plan.feedback_format]
    for key in requested_keys:
        if status_by_key.get(key) != "present":
            raise BatchFeedbackExportError(
                f"Post-export verification found {key} status "
                f"{status_by_key.get(key)!r}, expected 'present'."
            )
        if not file_by_key.get(key) or not metadata_by_key.get(key):
            raise BatchFeedbackExportError(
                f"Post-export verification found incomplete {key} artifact metadata."
            )
        if source_by_key.get(key) != snapshot.review_updated_at:
            raise BatchFeedbackExportError(
                f"Post-export verification found stale {key} source metadata."
            )
    return tuple(path_by_key[key] for key in requested_keys)


def _non_write_result(
    item: BatchFeedbackExportStudentPlan,
) -> BatchFeedbackExportStudentResult:
    mapping: dict[PlanAction, ResultOutcome] = {
        "skip_current": "skipped_current",
        "blocked_conflict": "skipped_by_policy",
        "blocked_incomplete": "blocked_incomplete",
        "blocked_attention": "blocked_attention",
        "blocked_unknown_state": "blocked_unknown_state",
        "create": "export_failed",
        "replace": "export_failed",
    }
    return _result(item, mapping[item.action], item.action.replace("_", " "))


def _result(
    item: BatchFeedbackExportStudentPlan,
    outcome: ResultOutcome,
    message: str,
) -> BatchFeedbackExportStudentResult:
    return BatchFeedbackExportStudentResult(
        student_id=item.student_id,
        display_name=item.display_name,
        outcome=outcome,
        message=message,
    )

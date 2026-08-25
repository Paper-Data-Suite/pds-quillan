"""Privacy-minimal read-only Quillan attention projection for Core operations v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from pds_core.classes import list_class_folders
from pds_core.module_operations import (
    ModuleAttentionReport,
    ModuleAttentionSummary,
    ModuleOperationsNotice,
    ModuleOperationsRequest,
    ModuleOwnerActionRef,
    validate_module_attention_report,
)
from pds_core.routing_models import ModuleWorkRef

from quillan.assignment_discovery import (
    DiscoveredAssignment,
    discover_quillan_assignments,
)
from quillan.class_review_completion import (
    ClassReviewCompletionError,
    ClassReviewCompletionView,
    build_class_review_completion_view,
)
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.post_dispatch_review_resolution import (
    PostDispatchReviewResolutionError,
    discover_post_dispatch_review_items,
)
from quillan.record_context import (
    QuillanRecordContextError,
    canonical_workspace_root,
)
from quillan.scan_review_resolution import (
    QuillanReviewItem,
    ScanReviewResolutionError,
    discover_scan_review_items,
)
from quillan.share_results import (
    ShareResultsError,
    ShareResultsStatus,
    build_share_results_status,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    preflight_quillan_work_collection,
    quillan_work_ref,
)

_PARTIAL_NOTICE_CODE: Final = "quillan_attention_partial"
_UNAVAILABLE_NOTICE_CODE: Final = "quillan_attention_unavailable"

_REVIEW_CATEGORY_CODES: Final[dict[str, str]] = {
    "needs_assembly": "quillan_needs_assembly",
    "minimum_requirements_pending": "quillan_minimum_requirements_pending",
    "observations_pending": "quillan_observations_pending",
    "ratings_pending": "quillan_ratings_pending",
    "feedback_pending": "quillan_feedback_pending",
    "export_pending": "quillan_feedback_export_pending",
    "attention_required": "quillan_review_state_attention",
}

_SHARE_STEP_CODES: Final[dict[str, str]] = {
    "register_academic_work": "quillan_results_registration_pending",
    "update_cancelled_registration": "quillan_results_registration_update",
    "resolve_native_result_state": "quillan_results_native_state_attention",
    "generate_manifest": "quillan_results_manifest_pending",
    "publish_initial": "quillan_results_publication_pending",
    "supersede_current": "quillan_results_supersession_pending",
    "advanced_republication_required": "quillan_results_republication_attention",
    "resolve_publication_state": "quillan_results_publication_state_attention",
}

_SHARE_STEPS_REQUIRING_COMPLETE_REVIEW: Final[frozenset[str]] = frozenset(
    {
        "register_academic_work",
        "update_cancelled_registration",
        "resolve_native_result_state",
        "generate_manifest",
        "publish_initial",
        "supersede_current",
    }
)


@dataclass(frozen=True, slots=True)
class _AttentionDefinition:
    code: str
    label: str
    action_id: str


_ATTENTION_DEFINITIONS: Final[tuple[_AttentionDefinition, ...]] = (
    _AttentionDefinition(
        "quillan_scan_review",
        "Returned-paper routing review needs attention",
        "open_scan_review",
    ),
    _AttentionDefinition(
        "quillan_post_dispatch_review",
        "Post-dispatch recovery needs attention",
        "open_post_dispatch_review",
    ),
    _AttentionDefinition(
        "quillan_needs_assembly",
        "Routed evidence awaits submission assembly",
        "open_review_queue",
    ),
    _AttentionDefinition(
        "quillan_minimum_requirements_pending",
        "Minimum-requirement review is pending",
        "open_review_queue",
    ),
    _AttentionDefinition(
        "quillan_observations_pending",
        "Review observations are pending",
        "open_review_queue",
    ),
    _AttentionDefinition(
        "quillan_ratings_pending",
        "Focus Standard ratings are pending",
        "open_review_queue",
    ),
    _AttentionDefinition(
        "quillan_feedback_pending",
        "Teacher feedback is pending",
        "open_review_queue",
    ),
    _AttentionDefinition(
        "quillan_feedback_export_pending",
        "Feedback export is missing or stale",
        "open_feedback_export",
    ),
    _AttentionDefinition(
        "quillan_review_state_attention",
        "Review state needs teacher inspection",
        "open_review_queue",
    ),
    _AttentionDefinition(
        "quillan_results_registration_pending",
        "Academic Work registration is pending for completed results",
        "open_share_results",
    ),
    _AttentionDefinition(
        "quillan_results_registration_update",
        "Academic Work registration needs review before sharing results",
        "open_share_results",
    ),
    _AttentionDefinition(
        "quillan_results_native_state_attention",
        "Completed result state needs inspection before sharing",
        "open_share_results",
    ),
    _AttentionDefinition(
        "quillan_results_manifest_pending",
        "A current Academic Result manifest is pending",
        "open_share_results",
    ),
    _AttentionDefinition(
        "quillan_results_publication_pending",
        "Completed results are ready for explicit first publication",
        "open_share_results",
    ),
    _AttentionDefinition(
        "quillan_results_supersession_pending",
        "Completed results are ready for explicit supersession",
        "open_share_results",
    ),
    _AttentionDefinition(
        "quillan_results_republication_attention",
        "Withdrawn publication state needs advanced teacher review",
        "open_share_results",
    ),
    _AttentionDefinition(
        "quillan_results_publication_state_attention",
        "Publication state needs teacher inspection",
        "open_share_results",
    ),
)

_DEFINITION_BY_CODE: Final[dict[str, _AttentionDefinition]] = {
    definition.code: definition for definition in _ATTENTION_DEFINITIONS
}


@dataclass(slots=True)
class _Aggregate:
    count: int = 0
    class_ids: set[str] = field(default_factory=set)
    work_refs: set[ModuleWorkRef] = field(default_factory=set)
    class_context_complete: bool = True
    work_context_complete: bool = True

    def add(
        self,
        count: int,
        *,
        class_id: str | None,
        work_ref: ModuleWorkRef | None,
    ) -> None:
        if count <= 0:
            return
        self.count += count
        if class_id is None:
            self.class_context_complete = False
        else:
            self.class_ids.add(class_id)
        if work_ref is None:
            self.work_context_complete = False
        else:
            self.work_refs.add(work_ref)


class _AttentionAccumulator:
    def __init__(self) -> None:
        self._aggregates: dict[str, _Aggregate] = {}

    def add(
        self,
        code: str,
        count: int,
        *,
        class_id: str | None = None,
        work_ref: ModuleWorkRef | None = None,
    ) -> None:
        if code not in _DEFINITION_BY_CODE:
            raise ValueError(f"Unknown Quillan attention code: {code}")
        if count <= 0:
            return
        aggregate = self._aggregates.setdefault(code, _Aggregate())
        aggregate.add(count, class_id=class_id, work_ref=work_ref)

    def summaries(
        self,
        request: ModuleOperationsRequest,
    ) -> tuple[ModuleAttentionSummary, ...]:
        summaries: list[ModuleAttentionSummary] = []
        for definition in _ATTENTION_DEFINITIONS:
            aggregate = self._aggregates.get(definition.code)
            if aggregate is None or aggregate.count <= 0:
                continue
            class_id, work_ref = _summary_context(aggregate, request)
            summaries.append(
                ModuleAttentionSummary(
                    code=definition.code,
                    label=definition.label,
                    count=aggregate.count,
                    class_id=class_id,
                    work_ref=work_ref,
                    action=ModuleOwnerActionRef(
                        module_id=QUILLAN_MODULE_ID,
                        action_id=definition.action_id,
                    ),
                )
            )
        return tuple(summaries)


def evaluate_quillan_attention(
    request: ModuleOperationsRequest,
    /,
) -> ModuleAttentionReport:
    """Evaluate current Quillan teacher attention without writing workspace state."""
    if not isinstance(request, ModuleOperationsRequest):
        raise TypeError("request must be a ModuleOperationsRequest.")

    if request.workspace_root is None:
        return _unavailable_report(
            "Quillan attention requires an explicit workspace."
        )

    try:
        root = canonical_workspace_root(request.workspace_root)
    except (OSError, QuillanRecordContextError):
        return _unavailable_report(
            "The supplied workspace cannot be inspected safely for Quillan attention."
        )

    try:
        class_ids = _class_ids(root, request.class_id)
    except OSError:
        return _unavailable_report(
            "Quillan class scope cannot be inspected safely."
        )

    accumulator = _AttentionAccumulator()
    partial = False

    try:
        scan_discovery = discover_scan_review_items(
            root,
            class_id=request.class_id,
        )
    except (OSError, ScanReviewResolutionError, ValueError):
        partial = True
    else:
        if scan_discovery.warnings:
            partial = True
        _add_scan_review_attention(accumulator, scan_discovery.items)

    for class_id in class_ids:
        try:
            assignments = _assignment_entries(root, class_id)
        except (OSError, QuillanWorkPathError):
            if request.class_id is not None:
                return _unavailable_report(
                    "The requested Quillan class work scope cannot be inspected safely."
                )
            partial = True
            continue

        for discovered in assignments:
            try:
                work_ref = quillan_work_ref(class_id, discovered.assignment_id)
            except (TypeError, ValueError):
                partial = True
                continue

            try:
                post_dispatch = discover_post_dispatch_review_items(root, work_ref)
            except (OSError, PostDispatchReviewResolutionError, ValueError):
                partial = True
            else:
                if post_dispatch.warnings:
                    partial = True
                accumulator.add(
                    "quillan_post_dispatch_review",
                    len(post_dispatch.items),
                    class_id=class_id,
                    work_ref=work_ref,
                )

            if discovered.assignment is None:
                partial = True
                continue

            try:
                completion = build_class_review_completion_view(
                    root,
                    class_id,
                    discovered.assignment_id,
                )
            except (OSError, ClassReviewCompletionError, TypeError, ValueError):
                partial = True
            else:
                _add_review_attention(accumulator, completion, work_ref)

            try:
                share_status = build_share_results_status(
                    root,
                    class_id,
                    discovered.assignment_id,
                )
            except (OSError, ShareResultsError, TypeError, ValueError):
                partial = True
            else:
                _add_share_attention(accumulator, share_status, work_ref)

    notices: tuple[ModuleOperationsNotice, ...] = ()
    if partial:
        notices = (
            ModuleOperationsNotice(
                code=_PARTIAL_NOTICE_CODE,
                summary=(
                    "Some Quillan attention sources could not be inspected safely; "
                    "available summaries are partial."
                ),
            ),
        )

    report = ModuleAttentionReport(
        evaluation="evaluated",
        summaries=accumulator.summaries(request),
        notices=notices,
    )
    return validate_module_attention_report(
        report,
        expected_module_id=QUILLAN_MODULE_ID,
    )


def _class_ids(root: Path, requested_class_id: str | None) -> tuple[str, ...]:
    if requested_class_id is not None:
        return (requested_class_id,)
    return tuple(folder.class_id for folder in list_class_folders(root))


def _assignment_entries(
    root: Path,
    class_id: str,
) -> tuple[DiscoveredAssignment, ...]:
    preflight_quillan_work_collection(root, class_id)
    return discover_quillan_assignments(root, class_id)


def _add_scan_review_attention(
    accumulator: _AttentionAccumulator,
    items: tuple[QuillanReviewItem, ...],
) -> None:
    for item in items:
        work_ref: ModuleWorkRef | None = None
        if item.class_id is not None and item.assignment_id is not None:
            try:
                work_ref = quillan_work_ref(item.class_id, item.assignment_id)
            except (TypeError, ValueError):
                work_ref = None
        accumulator.add(
            "quillan_scan_review",
            1,
            class_id=item.class_id,
            work_ref=work_ref,
        )


def _add_review_attention(
    accumulator: _AttentionAccumulator,
    view: ClassReviewCompletionView,
    work_ref: ModuleWorkRef,
) -> None:
    counts = dict(view.category_counts)
    for category, code in _REVIEW_CATEGORY_CODES.items():
        accumulator.add(
            code,
            counts.get(category, 0),
            class_id=view.class_id,
            work_ref=work_ref,
        )


def _add_share_attention(
    accumulator: _AttentionAccumulator,
    status: ShareResultsStatus,
    work_ref: ModuleWorkRef,
) -> None:
    next_step = status.next_step
    code = _SHARE_STEP_CODES.get(next_step)
    if code is None:
        return

    if next_step in _SHARE_STEPS_REQUIRING_COMPLETE_REVIEW:
        review = status.review_context
        if (
            review is None
            or review.roster_count < 1
            or review.needs_work_count != 0
        ):
            return

    accumulator.add(
        code,
        1,
        class_id=status.class_id,
        work_ref=work_ref,
    )


def _summary_context(
    aggregate: _Aggregate,
    request: ModuleOperationsRequest,
) -> tuple[str | None, ModuleWorkRef | None]:
    class_id: str | None = None
    if request.class_id is not None:
        class_id = request.class_id
    elif aggregate.class_context_complete and len(aggregate.class_ids) == 1:
        class_id = next(iter(aggregate.class_ids))

    work_ref: ModuleWorkRef | None = None
    if aggregate.work_context_complete and len(aggregate.work_refs) == 1:
        work_ref = next(iter(aggregate.work_refs))
        if class_id is None:
            class_id = work_ref.class_id

    return class_id, work_ref


def _unavailable_report(summary: str) -> ModuleAttentionReport:
    return ModuleAttentionReport(
        evaluation="unavailable",
        summaries=(),
        notices=(
            ModuleOperationsNotice(
                code=_UNAVAILABLE_NOTICE_CODE,
                summary=summary,
            ),
        ),
    )


__all__ = ["evaluate_quillan_attention"]

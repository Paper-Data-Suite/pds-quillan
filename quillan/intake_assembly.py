"""Post-dispatch observation persistence and submission assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pds_core.module_dispatch import RouteDispatchSuccess

from quillan.pds2_scan_intake import QuillanScanIntakeSummary
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.post_dispatch_review import (
    PersistedPostDispatchReviewOccurrence,
    create_post_dispatch_review_occurrence,
)
from quillan.response_page_dispatch import QuillanResponsePageDispatchResult
from quillan.response_page_observation_persistence import (
    QuillanObservationPersistenceBatch,
    persist_quillan_scan_observations,
)
from quillan.submission_observation_assembly import (
    QuillanSubmissionAssemblyBatch,
    assemble_quillan_scan_observations,
)
from quillan.work_paths import quillan_work_ref

@dataclass(frozen=True, slots=True)
class IntakeAssemblyTarget:
    class_id: str
    assignment_id: str
    routed_page_count: int


@dataclass(frozen=True, slots=True)
class PostDispatchReviewPreservationBatch:
    """Best-effort occurrence writes and explicit preservation diagnostics."""

    persisted: tuple[PersistedPostDispatchReviewOccurrence, ...] = ()
    failures: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.persisted) is not tuple or type(self.failures) is not tuple:
            raise ValueError("Post-dispatch preservation collections must be tuples.")
        if any(
            type(item) is not PersistedPostDispatchReviewOccurrence
            for item in self.persisted
        ):
            raise ValueError("Post-dispatch persisted members have the wrong type.")
        if any(not isinstance(item, str) or not item for item in self.failures):
            raise ValueError("Post-dispatch preservation failures must be text.")


@dataclass(frozen=True, slots=True)
class QuillanPostDispatchPersistenceResult:
    intake_summary: QuillanScanIntakeSummary
    observation_persistence: QuillanObservationPersistenceBatch
    submission_assembly: QuillanSubmissionAssemblyBatch
    review_preservation: PostDispatchReviewPreservationBatch = field(
        default_factory=PostDispatchReviewPreservationBatch
    )

    def __post_init__(self) -> None:
        if type(self.intake_summary) is not QuillanScanIntakeSummary:
            raise ValueError("intake_summary has the wrong type.")
        if type(self.observation_persistence) is not QuillanObservationPersistenceBatch:
            raise ValueError("observation_persistence has the wrong type.")
        if type(self.submission_assembly) is not QuillanSubmissionAssemblyBatch:
            raise ValueError("submission_assembly has the wrong type.")
        if type(self.review_preservation) is not PostDispatchReviewPreservationBatch:
            raise ValueError("review_preservation has the wrong type.")
        if self.observation_persistence.intake_summary != self.intake_summary:
            raise ValueError("Persistence batch belongs to a different intake summary.")
        processed = len(self.observation_persistence.persisted) + len(
            self.observation_persistence.failures
        )
        if processed != self.intake_summary.quillan_success_count:
            raise ValueError(
                "Persistence members do not account for every Quillan success."
            )

    @property
    def complete_success(self) -> bool:
        return (
            self.intake_summary.complete_success
            and not self.observation_persistence.failures
            and not self.submission_assembly.failures
            and len(self.observation_persistence.persisted)
            == self.intake_summary.quillan_success_count
        )


def assembly_targets_from_intake_summary(
    summary: QuillanScanIntakeSummary,
) -> tuple[IntakeAssemblyTarget, ...]:
    """Return deterministic immutable work targets from Quillan successes."""
    counts: dict[tuple[str, str], int] = {}
    for page in summary.pages:
        if page.terminal_category != "dispatch_success":
            continue
        outcome = page.dispatch_outcome
        if (
            not isinstance(outcome, RouteDispatchSuccess)
            or type(outcome) is not RouteDispatchSuccess
            or outcome.profile.module_id != QUILLAN_MODULE_ID
            or type(outcome.module_result) is not QuillanResponsePageDispatchResult
        ):
            continue
        result = outcome.module_result
        key = (result.class_id, result.assignment_id)
        counts[key] = counts.get(key, 0) + 1
    return tuple(
        IntakeAssemblyTarget(class_id, assignment_id, counts[(class_id, assignment_id)])
        for class_id, assignment_id in sorted(counts)
    )


def persist_and_assemble_quillan_scan_successes(
    workspace_root: Path,
    intake_summary: QuillanScanIntakeSummary,
) -> QuillanPostDispatchPersistenceResult:
    """Run the durable #339 layer without mutating #338 outcomes."""
    persistence = persist_quillan_scan_observations(workspace_root, intake_summary)
    assembly = assemble_quillan_scan_observations(workspace_root, persistence)
    preservation = preserve_post_dispatch_review_occurrences(
        workspace_root, intake_summary, persistence, assembly
    )
    return QuillanPostDispatchPersistenceResult(
        intake_summary=intake_summary,
        observation_persistence=persistence,
        submission_assembly=assembly,
        review_preservation=preservation,
    )


def preserve_post_dispatch_review_occurrences(
    workspace_root: Path,
    intake_summary: QuillanScanIntakeSummary,
    persistence: QuillanObservationPersistenceBatch,
    assembly: QuillanSubmissionAssemblyBatch,
) -> PostDispatchReviewPreservationBatch:
    """Preserve every attributable post-dispatch failure without masking siblings."""
    persisted: list[PersistedPostDispatchReviewOccurrence] = []
    failures: list[str] = []
    outcomes: dict[
        tuple[str, int, str | None, str | None],
        QuillanResponsePageDispatchResult,
    ] = {
        (
            result.source_scan_id,
            result.source_page_number,
            result.route_id,
            result.page_id,
        ): result
        for page in intake_summary.pages
        if page.terminal_category == "dispatch_success"
        and isinstance(page.dispatch_outcome, RouteDispatchSuccess)
        and type(page.dispatch_outcome) is RouteDispatchSuccess
        and page.dispatch_outcome.profile.module_id == QUILLAN_MODULE_ID
        and type(page.dispatch_outcome.module_result)
        is QuillanResponsePageDispatchResult
        for result in (page.dispatch_outcome.module_result,)
    }
    for observation_failure in persistence.failures:
        key = (
            observation_failure.source_scan_id,
            observation_failure.source_page_number,
            observation_failure.route_id,
            observation_failure.page_id,
        )
        result = outcomes.get(key)
        if result is None:
            failures.append(
                "Could not attribute observation persistence failure to an exact "
                f"Quillan work identity: {key!r}"
            )
            continue
        try:
            persisted.append(
                create_post_dispatch_review_occurrence(
                    workspace_root,
                    quillan_work_ref(result.class_id, result.assignment_id),
                    category="observation_persistence",
                    stage="observation_persistence",
                    failure_message=str(observation_failure.error),
                    student_id=result.student_id,
                    issuance_id=result.issuance_id,
                    page_id=result.page_id,
                    route_id=result.route_id,
                    source_scan_id=result.source_scan_id,
                    source_page_number=result.source_page_number,
                    possible_observation_path=(
                        observation_failure.possible_observation_path
                    ),
                    possible_evidence_path=observation_failure.possible_evidence_path,
                    module_details={
                        "failure_type": type(observation_failure.error).__name__
                    },
                )
            )
        except Exception as error:
            failures.append(
                f"Could not preserve observation failure {key!r}: {error}"
            )
    for assembly_failure in assembly.failures:
        category = _post_dispatch_assembly_category(assembly_failure.category)
        try:
            persisted.append(
                create_post_dispatch_review_occurrence(
                    workspace_root,
                    quillan_work_ref(
                        assembly_failure.class_id, assembly_failure.assignment_id
                    ),
                    category=category,
                    stage="submission_assembly",
                    failure_message=assembly_failure.reason,
                    student_id=assembly_failure.student_id,
                    issuance_ids=assembly_failure.issuance_ids,
                    page_ids=assembly_failure.page_ids,
                    observation_ids=assembly_failure.observation_ids,
                    source_scan_ids=assembly_failure.source_scan_ids,
                    source_page_numbers=assembly_failure.source_page_numbers,
                    possible_manifest_path=assembly_failure.possible_manifest_path,
                    module_details={
                        "assembly_category": assembly_failure.category,
                        "failure_type": (
                            type(assembly_failure.error).__name__
                            if assembly_failure.error is not None
                            else None
                        ),
                    },
                )
            )
        except Exception as error:
            failures.append(
                "Could not preserve submission assembly failure "
                f"{assembly_failure.class_id}/{assembly_failure.assignment_id}/"
                f"{assembly_failure.student_id or 'unknown'}: {error}"
            )
    return PostDispatchReviewPreservationBatch(tuple(persisted), tuple(failures))


def _post_dispatch_assembly_category(category: str) -> str:
    if category == "mixed_issuances":
        return "mixed_issuance"
    if "manifest" in category or category in {"existing_plain_paper_submission"}:
        return "manifest_conflict"
    return "submission_assembly"


def format_post_dispatch_persistence_result(
    result: QuillanPostDispatchPersistenceResult,
) -> str:
    """Return deterministic post-dispatch persistence and assembly counts."""
    persistence = result.observation_persistence
    assembly = result.submission_assembly
    lines = [
        "Quillan post-dispatch persistence summary",
        f"Quillan dispatch successes: {result.intake_summary.quillan_success_count}",
        f"Observations created: {persistence.created_count}",
        f"Observations already present: {persistence.existing_count}",
        f"Observation persistence failures: {persistence.failure_count}",
        f"Routed evidence created: {persistence.created_count}",
        f"Submission manifests created: {assembly.created_count}",
        f"Submission manifests updated: {assembly.updated_count}",
        f"Submission manifests unchanged: {assembly.unchanged_count}",
        f"Submission assembly failures: {len(assembly.failures)}",
        f"Post-dispatch review occurrences: {len(result.review_preservation.persisted)}",
        f"Post-dispatch preservation failures: {len(result.review_preservation.failures)}",
    ]
    for failure in persistence.failures:
        lines.append(
            "Observation failure: "
            f"{failure.source_scan_id} page {failure.source_page_number}; "
            f"route={failure.route_id}; page_id={failure.page_id}; error={failure.error}"
        )
    for assembly_failure in assembly.failures:
        lines.append(
            "Submission failure: "
            f"student={assembly_failure.student_id or 'unknown'}; "
            f"category={assembly_failure.category}; reason={assembly_failure.reason}"
        )
    lines.extend(
        f"Post-dispatch preservation failure: {failure}"
        for failure in result.review_preservation.failures
    )
    return "\n".join(lines)


__all__ = [
    "IntakeAssemblyTarget",
    "PostDispatchReviewPreservationBatch",
    "QuillanPostDispatchPersistenceResult",
    "assembly_targets_from_intake_summary",
    "format_post_dispatch_persistence_result",
    "persist_and_assemble_quillan_scan_successes",
    "preserve_post_dispatch_review_occurrences",
]

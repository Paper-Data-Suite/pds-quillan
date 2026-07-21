"""Post-dispatch observation persistence and submission assembly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pds_core.module_dispatch import RouteDispatchSuccess

from quillan.pds2_scan_intake import QuillanScanIntakeSummary
from quillan.response_page_dispatch import QuillanResponsePageDispatchResult
from quillan.response_page_observation_persistence import (
    QuillanObservationPersistenceBatch,
    persist_quillan_scan_observations,
)
from quillan.submission_observation_assembly import (
    QuillanSubmissionAssemblyBatch,
    assemble_quillan_scan_observations,
)


@dataclass(frozen=True, slots=True)
class IntakeAssemblyTarget:
    class_id: str
    assignment_id: str
    routed_page_count: int


@dataclass(frozen=True, slots=True)
class QuillanPostDispatchPersistenceResult:
    intake_summary: QuillanScanIntakeSummary
    observation_persistence: QuillanObservationPersistenceBatch
    submission_assembly: QuillanSubmissionAssemblyBatch

    def __post_init__(self) -> None:
        if type(self.intake_summary) is not QuillanScanIntakeSummary:
            raise ValueError("intake_summary has the wrong type.")
        if type(self.observation_persistence) is not QuillanObservationPersistenceBatch:
            raise ValueError("observation_persistence has the wrong type.")
        if type(self.submission_assembly) is not QuillanSubmissionAssemblyBatch:
            raise ValueError("submission_assembly has the wrong type.")
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
            or outcome.profile.module_id != "quillan"
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
    return QuillanPostDispatchPersistenceResult(
        intake_summary=intake_summary,
        observation_persistence=persistence,
        submission_assembly=assembly,
    )


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
    return "\n".join(lines)


__all__ = [
    "IntakeAssemblyTarget",
    "QuillanPostDispatchPersistenceResult",
    "assembly_targets_from_intake_summary",
    "format_post_dispatch_persistence_result",
    "persist_and_assemble_quillan_scan_successes",
]

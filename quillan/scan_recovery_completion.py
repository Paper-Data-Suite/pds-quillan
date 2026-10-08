"""Issue #419 Slice 5: one explicit recovery attempt with truthful completion.

Coordinate existing validated stages without creating a second writer, changing
teacher decisions, or treating an old Core route-resolution as materialization.
Each retry begins with fresh authority checks, and only verified assembly can
produce a completion receipt. No Core scan-resolution metadata is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pds_core.module_profiles import ModuleRegistry
from pds_core.routing_models import ModuleRecordRef, RouteLocator

from quillan.scan_recovery_assembly import (
    AssembledScanRecovery,
    assemble_persisted_scan_recovery,
)
from quillan.scan_recovery_dispatch import dispatch_prepared_scan_recovery
from quillan.scan_recovery_persistence import (
    PersistedScanRecovery,
    persist_dispatched_scan_recovery,
)
from quillan.scan_recovery_preflight import (
    PreparedScanRecovery,
    prepare_scan_review_recovery,
)

RecoveryExecutionStage = Literal[
    "preflight", "dispatch", "persistence", "assembly"
]
RecoveryCompletionState = Literal[
    "ready_for_review", "selection_needed", "teacher_action_needed"
]


class ScanRecoveryExecutionError(RuntimeError):
    """A recovery attempt failed at a named stage; never a success receipt.

    If ``verified_observation_id`` is set, the preceding persistence call
    returned a verified durable observation/evidence pair. If unset, possible
    paths are *diagnostic only* and may represent partial or uncertain writes.
    The original exception is preserved as ``__cause__`` by the caller.
    """

    def __init__(
        self,
        stage: RecoveryExecutionStage,
        failure_id: str | None,
        cause: Exception,
        *,
        persisted: PersistedScanRecovery | None = None,
    ) -> None:
        self.stage = stage
        self.failure_id = failure_id
        self.verified_observation_id = (
            persisted.persisted.observation.observation_id
            if persisted is not None
            else None
        )
        self.possible_observation_path = (
            persisted.persisted.observation_path
            if persisted is not None
            else _possible_path(cause, "possible_observation_path")
        )
        self.possible_evidence_path = (
            persisted.persisted.evidence_path
            if persisted is not None
            else _possible_path(cause, "possible_evidence_path")
        )
        super().__init__(
            f"Scan recovery did not complete ({stage}): {cause}"
        )


@dataclass(frozen=True, slots=True)
class CompletedScanRecovery:
    """A read-back-verified result, not a Core routing-failure resolution.

    Even with a valid observation and submission, teacher selection may still
    be required. The receipt reflects the state at verification, not a lock on
    future teacher changes or a claim that a viewer was actually opened.
    """

    persisted: PersistedScanRecovery
    assembled: AssembledScanRecovery

    @property
    def failure_id(self) -> str:
        return self.assembled.persisted.dispatched.prepared.failure_id

    @property
    def evidence_id(self) -> str:
        return self.assembled.recovery_evidence_id

    @property
    def completion_state(self) -> RecoveryCompletionState:
        return self.assembled.evidence_state

    @property
    def reviewable(self) -> bool:
        """Recovered evidence is currently selected and active for review."""
        return self.assembled.reviewable

    @property
    def observation_status(self) -> Literal["created", "existing"]:
        return self.persisted.persisted.status

    @property
    def submission_status(self) -> Literal["created", "updated", "unchanged"]:
        return self.assembled.assembled.status

    @property
    def historical_route_reused(self) -> bool:
        return (
            self.assembled.persisted.dispatched.prepared.route_origin == "recorded"
        )


def execute_prepared_scan_recovery(
    workspace_root: str | Path,
    prepared: PreparedScanRecovery,
    *,
    registry: ModuleRegistry | None = None,
) -> CompletedScanRecovery:
    """Execute one previously selected and preflighted recovery route.

    The prepared object is not an authorization token: Core dispatch, evidence
    persistence, and assembly each repeat the necessary current-state checks.
    A retry must use the same explicit route or prepare a newly chosen route.
    No QR detection, evidence selection, or Core resolution write occurs here.
    """
    if type(prepared) is not PreparedScanRecovery:
        error = TypeError("An exact PreparedScanRecovery is required.")
        raise ScanRecoveryExecutionError("preflight", None, error) from error

    try:
        dispatched = dispatch_prepared_scan_recovery(
            workspace_root, prepared, registry=registry
        )
    except Exception as error:
        raise ScanRecoveryExecutionError(
            "dispatch", prepared.failure_id, error
        ) from error

    try:
        persisted = persist_dispatched_scan_recovery(
            workspace_root, dispatched, registry=registry
        )
    except Exception as error:
        raise ScanRecoveryExecutionError(
            "persistence", prepared.failure_id, error
        ) from error

    try:
        assembled = assemble_persisted_scan_recovery(
            workspace_root, persisted, registry=registry
        )
    except Exception as error:
        raise ScanRecoveryExecutionError(
            "assembly", prepared.failure_id, error, persisted=persisted
        ) from error

    if assembled.persisted.persisted.observation != persisted.persisted.observation:
        mismatch_error = ValueError(
            "Assembly returned a different recovered observation."
        )
        raise ScanRecoveryExecutionError(
            "assembly", prepared.failure_id, mismatch_error, persisted=persisted
        ) from mismatch_error
    return CompletedScanRecovery(persisted=persisted, assembled=assembled)


def recover_scan_review_page(
    workspace_root: str | Path,
    failure_id: str,
    *,
    route_locator: RouteLocator | None = None,
    target: ModuleRecordRef | None = None,
    use_recorded_route: bool = False,
    registry: ModuleRegistry | None = None,
) -> CompletedScanRecovery:
    """Explicit-route convenience entry point for first run or fresh retry.

    Supply the exact route+target together, or deliberately opt into the latest
    verified historical route. Neither a QR guess nor an automatic fallback is
    allowed. Interactive confirmation and menu wiring belong to Slice 7.
    """
    try:
        prepared = prepare_scan_review_recovery(
            workspace_root,
            failure_id,
            route_locator=route_locator,
            target=target,
            use_recorded_route=use_recorded_route,
        )
    except Exception as error:
        raise ScanRecoveryExecutionError(
            "preflight", failure_id if type(failure_id) is str else None, error
        ) from error
    return execute_prepared_scan_recovery(
        workspace_root, prepared, registry=registry
    )


def _possible_path(error: Exception, field: str) -> Path | None:
    value = getattr(error, field, None)
    return value if isinstance(value, Path) else None


__all__ = [
    "CompletedScanRecovery",
    "RecoveryCompletionState",
    "RecoveryExecutionStage",
    "ScanRecoveryExecutionError",
    "execute_prepared_scan_recovery",
    "recover_scan_review_page",
]

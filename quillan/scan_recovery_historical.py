"""Issue #419 Slice 6: truthful read-only historical recovery discovery.

A Core 'resolved' routing decision only records the teacher's selected route.
It never proves that the retained physical page became reviewable evidence.
Discovery has no writes; replay requires a fresh exact resolution-id match and
passes through the Slice 5 reauthorizing pipeline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pds_core.module_profiles import ModuleRegistry

from quillan.pds2_scan_intake import validate_scan_workspace
from quillan.printable_response_persistence import (
    load_printable_response_page_context,
)
from quillan.record_context import (
    MissingSubmissionError,
    ReviewLoadingPolicy,
    load_quillan_student_review_context,
    mutable_json_copy,
)
from quillan.response_page_observations import (
    derive_observation_id,
    load_contextual_response_page_observation,
)
from quillan.routed_evidence import verify_contextual_routed_page_evidence
from quillan.scan_recovery_completion import (
    CompletedScanRecovery,
    execute_prepared_scan_recovery,
)
from quillan.scan_recovery_preflight import (
    PreparedScanRecovery,
    prepare_scan_review_recovery,
)
from quillan.scan_review_resolution import discover_scan_review_items
from quillan.submission_evidence_validation import evidence_matches_observation
from quillan.submission_manifest import PDS2_SUBMISSION_ENTRY_METHOD
from quillan.work_paths import (
    preflight_work_file_destination,
    quillan_work_ref,
    response_page_observation_path,
)

_HISTORICAL_ACTIONS = frozenset({"route_selected", "route_corrected"})

HistoricalEvidenceState = Literal[
    "evidence_missing",
    "assembly_pending",
    "ready_for_review",
    "selection_needed",
    "teacher_action_needed",
    "blocked",
]


class HistoricalScanRecoveryError(RuntimeError):
    """The selected historical decision cannot safely be replayed."""


@dataclass(frozen=True, slots=True)
class HistoricalScanRecoveryItem:
    """Read-only status for one *latest* recorded route selection."""

    failure_id: str
    resolution_id: str
    resolution_action: str
    state: HistoricalEvidenceState
    observation_id: str | None
    class_id: str | None
    assignment_id: str | None
    student_id: str | None
    logical_page: int | None
    selected_evidence_id: str | None
    reason: str | None

    @property
    def requires_replay(self) -> bool:
        """A missing observation or missing submission assembly can be retried."""
        return self.state in {"evidence_missing", "assembly_pending"}


@dataclass(frozen=True, slots=True)
class HistoricalScanRecoveryInventory:
    """Ordered historical route decisions with conservative discovery warnings."""

    items: tuple[HistoricalScanRecoveryItem, ...]
    warnings: tuple[str, ...]


def discover_historical_scan_recoveries(
    workspace_root: str | Path,
) -> HistoricalScanRecoveryInventory:
    """Inspect routed historical failures without producing or changing files.

    Only the latest verified *resolved route* decision is eligible. A teacher's
    other decisions (dismissal, rescan, deferral, etc.) are never replayed.
    Broken authority or contradictory evidence is reported as blocked, not as
    a successfully recovered scan or a safe-to-retry pending observation.
    """
    try:
        root = validate_scan_workspace(Path(os.path.abspath(workspace_root)))
        discovery = discover_scan_review_items(root, include_resolved=True)
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        raise HistoricalScanRecoveryError(
            f"Could not discover historical Quillan failures: {error}"
        ) from error

    items: list[HistoricalScanRecoveryItem] = []
    for failure in discovery.items:
        if (
            failure.latest_resolution_status != "resolved"
            or failure.latest_resolution_action is None
            or failure.latest_resolution_action not in _HISTORICAL_ACTIONS
            or failure.latest_resolution_path is None
        ):
            continue
        action = failure.latest_resolution_action
        resolution_id = PurePosixPath(failure.latest_resolution_path).stem
        state: HistoricalEvidenceState
        selected: str | None
        observation_id: str | None
        class_id: str | None
        assignment_id: str | None
        student_id: str | None
        logical_page: int | None
        reason: str | None
        try:
            prepared = prepare_scan_review_recovery(
                root, failure.failure_id, use_recorded_route=True
            )
            if prepared.historical_resolution_id != resolution_id:
                raise HistoricalScanRecoveryError(
                    "Latest historical route decision changed during discovery."
                )
            state, selected = _read_evidence_state(root, prepared)
            reason = None
            observation_id = derive_observation_id(
                prepared.retained_source.source_scan_id,
                prepared.source_page_number,
                prepared.route_locator.route_id,
                prepared.page_id,
            )
            class_id, assignment_id = prepared.class_id, prepared.assignment_id
            student_id, logical_page = prepared.student_id, prepared.logical_page
        except Exception as error:
            # One damaged historical item must not conceal other recoverable
            # items or be presented as successfully materialized evidence.
            state, selected, observation_id = "blocked", None, None
            class_id, assignment_id = failure.class_id, failure.assignment_id
            student_id, logical_page = failure.student_id, None
            reason = f"Historical recovery authority or evidence is invalid: {error}"
        items.append(
            HistoricalScanRecoveryItem(
                failure_id=failure.failure_id,
                resolution_id=resolution_id,
                resolution_action=action,
                state=state,
                observation_id=observation_id,
                class_id=class_id,
                assignment_id=assignment_id,
                student_id=student_id,
                logical_page=logical_page,
                selected_evidence_id=selected,
                reason=reason,
            )
        )
    return HistoricalScanRecoveryInventory(tuple(items), discovery.warnings)


def _read_evidence_state(
    root: Path, prepared: PreparedScanRecovery
) -> tuple[HistoricalEvidenceState, str | None]:
    """Require exact observation provenance, evidence bytes and manifest projection."""
    work_ref = quillan_work_ref(prepared.class_id, prepared.assignment_id)
    obs_id = derive_observation_id(
        prepared.retained_source.source_scan_id,
        prepared.source_page_number,
        prepared.route_locator.route_id,
        prepared.page_id,
    )
    obs_path = response_page_observation_path(root, work_ref, obs_id)
    preflight_work_file_destination(
        root, work_ref, Path("scans") / "observations" / f"{obs_id}.json"
    )
    if not os.path.lexists(obs_path):
        return "evidence_missing", None

    observation = load_contextual_response_page_observation(root, work_ref, obs_id)
    page_context = load_printable_response_page_context(
        root, prepared.route_locator.work, prepared.page_id
    )
    retained = prepared.retained_source
    actual = (
        observation.class_id,
        observation.assignment_id,
        observation.student_id,
        observation.page_id,
        observation.route_id,
        observation.source_scan_id,
        observation.source_page_number,
        observation.retained_source_path,
        observation.source_sha256,
        observation.source_filename,
        observation.logical_page,
        observation.total_pages,
        observation.issuance_id,
        observation.generation_id,
        observation.artifact_id,
        observation.page_role,
        observation.intake_timestamp,
        observation.intake_date,
    )
    expected = (
        prepared.class_id,
        prepared.assignment_id,
        prepared.student_id,
        prepared.page_id,
        prepared.route_locator.route_id,
        retained.source_scan_id,
        prepared.source_page_number,
        retained.retained_source_relative_path,
        retained.source_sha256,
        retained.source_filename,
        prepared.logical_page,
        prepared.total_pages,
        page_context.page.issuance_id,
        page_context.page.generation_id,
        page_context.page.artifact_id,
        page_context.page.page_role,
        retained.intake_timestamp.isoformat(),
        retained.intake_date.isoformat(),
    )
    if actual != expected:
        raise HistoricalScanRecoveryError(
            "Persisted observation contradicts the historical route or physical page."
        )
    verify_contextual_routed_page_evidence(
        root,
        work_ref,
        issuance_id=observation.issuance_id,
        student_id=observation.student_id,
        logical_page=observation.logical_page,
        observation_id=obs_id,
        extension=PurePosixPath(observation.routed_evidence_path).suffix,
        relative_path=observation.routed_evidence_path,
        expected_sha256=observation.routed_evidence_sha256,
        expected_size_bytes=observation.routed_evidence_size_bytes,
    )
    try:
        context = load_quillan_student_review_context(
            root,
            work_ref,
            prepared.student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
        )
    except MissingSubmissionError:
        return "assembly_pending", None

    manifest = mutable_json_copy(context.submission)
    details = manifest.get("module_details")
    if (
        not isinstance(details, dict)
        or details.get("submission_entry_method") != PDS2_SUBMISSION_ENTRY_METHOD
        or details.get("response_issuance_id") != observation.issuance_id
    ):
        raise HistoricalScanRecoveryError(
            "Current submission is not the same observation-backed issuance."
        )
    pages = tuple(
        page for page in manifest["pages"]
        if page["page_number"] == observation.logical_page
    )
    if len(pages) != 1:
        raise HistoricalScanRecoveryError("Historical logical page is not unique.")
    page = pages[0]
    evidence = tuple(
        item for item in page["evidence"]
        if item["evidence_id"] == obs_id
    )
    if not evidence:
        return "assembly_pending", page["selected_evidence_id"]
    if len(evidence) != 1 or not evidence_matches_observation(evidence[0], observation):
        raise HistoricalScanRecoveryError(
            "Submission evidence contradicts the original observation."
        )
    candidate = evidence[0]
    selected_id = page["selected_evidence_id"]
    if page["page_state"] in {"needs_rescan", "excluded"}:
        return "teacher_action_needed", selected_id
    if candidate["evidence_state"] != "active":
        raise HistoricalScanRecoveryError("Recovered evidence is not active.")
    if selected_id == obs_id:
        if candidate["evidence_role"] != "selected":
            raise HistoricalScanRecoveryError(
                "Recovered selection contradicts evidence role."
            )
        return "ready_for_review", selected_id
    if candidate["evidence_role"] not in {"candidate", "replacement"}:
        raise HistoricalScanRecoveryError(
            "Unselected evidence has an invalid review role."
        )
    return "selection_needed", selected_id


def replay_historical_scan_recovery(
    workspace_root: str | Path,
    failure_id: str,
    *,
    expected_resolution_id: str,
    registry: ModuleRegistry | None = None,
) -> CompletedScanRecovery:
    """Explicitly replay one exact currently authoritative recorded route.

    Never automatically batch-replay an inventory; reject stale selections.
    All authorization, source checks, and durable writes are delegated to the
    previously validated Slice 1-5 pipeline. No Core resolution is appended.
    """
    if type(expected_resolution_id) is not str or not expected_resolution_id:
        raise HistoricalScanRecoveryError(
            "Replay requires the exact historical resolution ID shown to the teacher."
        )
    try:
        prepared = prepare_scan_review_recovery(
            workspace_root, failure_id, use_recorded_route=True
        )
    except Exception as error:
        raise HistoricalScanRecoveryError(
            f"Historical route is no longer eligible for recovery: {error}"
        ) from error
    if prepared.historical_resolution_id != expected_resolution_id:
        raise HistoricalScanRecoveryError(
            "Historical resolution has changed; inspect and confirm the latest route."
        )
    return execute_prepared_scan_recovery(
        workspace_root, prepared, registry=registry
    )


__all__ = [
    "HistoricalEvidenceState",
    "HistoricalScanRecoveryError",
    "HistoricalScanRecoveryInventory",
    "HistoricalScanRecoveryItem",
    "discover_historical_scan_recoveries",
    "replay_historical_scan_recovery",
]

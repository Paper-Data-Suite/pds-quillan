"""Issue #419 Slice 4: assemble one persisted recovery into its submission.

Reuse issuance-authoritative Quillan assembly; do not modify teacher choices,
open desktop applications, or append Core scan resolution metadata.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pds_core.module_profiles import ModuleRegistry

from quillan.module_errors import QuillanRoutedEvidenceError
from quillan.pds2_scan_intake import validate_scan_workspace
from quillan.routed_evidence import verify_contextual_routed_page_evidence
from quillan.scan_recovery_persistence import (
    PersistedScanRecovery,
    persist_dispatched_scan_recovery,
)
from quillan.submission_observation_assembly import (
    AssembledQuillanSubmission,
    assemble_quillan_submission_manifests,
)
from quillan.submission_review_opening import (
    SubmissionReviewOpeningError,
    list_submission_evidence_candidates,
)
from quillan.work_paths import quillan_work_ref


class ScanRecoveryAssemblyError(RuntimeError):
    """Durable evidence exists, but correct submission availability is unproved."""


RecoveryEvidenceState = Literal[
    "ready_for_review", "selection_needed", "teacher_action_needed"
]


@dataclass(frozen=True, slots=True)
class AssembledScanRecovery:
    """Verified submission outcome, not a new Core resolution decision."""

    persisted: PersistedScanRecovery
    assembled: AssembledQuillanSubmission
    evidence_state: RecoveryEvidenceState
    page_state: str
    selected_evidence_id: str | None

    @property
    def recovery_evidence_id(self) -> str:
        return self.persisted.persisted.observation.observation_id

    @property
    def reviewable(self) -> bool:
        """True only when this recovered evidence is selected and active."""
        return self.evidence_state == "ready_for_review"


def assemble_persisted_scan_recovery(
    workspace_root: str | Path,
    persisted: PersistedScanRecovery,
    *,
    registry: ModuleRegistry | None = None,
) -> AssembledScanRecovery:
    """Reverify, assemble, and confirm one exact recovered observation.

    The targeted assembler is responsible for preserving existing teacher
    decisions, preventing mixed-issuance writes and enforcing manifest CAS.
    It may append an active candidate without changing an existing selection.
    Read-only verification confirms evidence bytes and the final page state;
    opening a viewer and selecting candidates are separate teacher actions.

    If assembly fails, the previously valid observation/evidence stay durable.
    The caller may retry the exact persisted recovery after repairing the
    underlying assembly problem; no false success is returned.
    """
    if type(persisted) is not PersistedScanRecovery:
        raise ScanRecoveryAssemblyError(
            "Assembly requires an exact persisted scan recovery."
        )
    try:
        root = validate_scan_workspace(Path(os.path.abspath(workspace_root)))
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        raise ScanRecoveryAssemblyError(
            f"Invalid recovery assembly workspace: {error}"
        ) from error

    # Reuse Slice 3's same reauthorization and canonical idempotent writer.
    # Never trust a stale persisted receipt merely because files exist.
    fresh = persist_dispatched_scan_recovery(
        root, persisted.dispatched, registry=registry
    )
    if (
        fresh.persisted.observation != persisted.persisted.observation
        or fresh.persisted.observation_path != persisted.persisted.observation_path
        or fresh.persisted.evidence_path != persisted.persisted.evidence_path
    ):
        raise ScanRecoveryAssemblyError(
            "Persisted recovery identity changed before assembly."
        )

    observation = fresh.persisted.observation
    try:
        batch = assemble_quillan_submission_manifests(
            root,
            observation.class_id,
            observation.assignment_id,
            observation_ids=(observation.observation_id,),
        )
    except (OSError, ValueError, RuntimeError) as error:
        raise ScanRecoveryAssemblyError(
            f"Recovery evidence is persisted, but assembly failed: {error}"
        ) from error

    if batch.failures:
        summary = "; ".join(
            f"{failure.category}: {failure.reason}" for failure in batch.failures
        )
        raise ScanRecoveryAssemblyError(
            "Recovery evidence is persisted, but submission assembly is "
            f"incomplete: {summary}"
        )
    if len(batch.assembled) != 1:
        raise ScanRecoveryAssemblyError(
            "Recovery assembly did not return exactly one affected submission."
        )
    assembled = batch.assembled[0]
    if (
        assembled.class_id != observation.class_id
        or assembled.assignment_id != observation.assignment_id
        or assembled.student_id != observation.student_id
        or assembled.issuance_id != observation.issuance_id
        or observation.observation_id not in assembled.observation_ids
    ):
        raise ScanRecoveryAssemblyError(
            "Assembly result contradicts the recovered observation identity."
        )

    try:
        inventory = list_submission_evidence_candidates(
            root,
            observation.class_id,
            observation.assignment_id,
            observation.student_id,
        )
        if inventory.plain_paper:
            raise ScanRecoveryAssemblyError(
                "Recovered digital observation cannot enter plain-paper submission."
            )
        if inventory.manifest_relative_path != assembled.manifest_relative_path:
            raise ScanRecoveryAssemblyError(
                "Verified manifest path differs from assembly result."
            )
        pages = tuple(
            page for page in inventory.pages
            if page.page_number == observation.logical_page
        )
        if len(pages) != 1:
            raise ScanRecoveryAssemblyError(
                "The recovered logical page is not unique in the submission."
            )
        page = pages[0]
        candidates = tuple(
            candidate for candidate in page.candidates
            if candidate.evidence_id == observation.observation_id
        )
        if len(candidates) != 1:
            raise ScanRecoveryAssemblyError(
                "Recovered evidence was not assembled exactly once."
            )
        evidence = candidates[0]
        if (
            evidence.relative_path != observation.routed_evidence_path
            or evidence.relative_path != fresh.persisted.evidence_relative_path
        ):
            raise ScanRecoveryAssemblyError(
                "Assembled recovered evidence has a mismatched path."
            )
        # A teacher may have marked an already-assembled occurrence for rescan
        # or excluded it before retry. That state is authoritative: verify the
        # retained evidence, but report pending teacher action rather than
        # rejecting a valid durable observation or reactivating the evidence.
        allowed_states = {
            "needs_rescan": frozenset({"active", "needs_rescan"}),
            "excluded": frozenset({"active", "excluded"}),
        }.get(page.page_state, frozenset({"active"}))
        if evidence.evidence_state not in allowed_states:
            raise ScanRecoveryAssemblyError(
                "Recovered evidence state contradicts the page's "
                "teacher-controlled state."
            )
        verified_path = verify_contextual_routed_page_evidence(
            root,
            quillan_work_ref(observation.class_id, observation.assignment_id),
            issuance_id=observation.issuance_id,
            student_id=observation.student_id,
            logical_page=observation.logical_page,
            observation_id=observation.observation_id,
            extension=fresh.persisted.evidence_path.suffix,
            relative_path=evidence.relative_path,
            expected_sha256=observation.routed_evidence_sha256,
            expected_size_bytes=observation.routed_evidence_size_bytes,
        )
        if verified_path != fresh.persisted.evidence_path:
            raise ScanRecoveryAssemblyError(
                "Recovered evidence resolved to an unexpected absolute path."
            )
    except (SubmissionReviewOpeningError, QuillanRoutedEvidenceError) as error:
        raise ScanRecoveryAssemblyError(
            f"Recovery evidence was persisted, but availability failed: {error}"
        ) from error

    if page.page_state in {"needs_rescan", "excluded"}:
        state: RecoveryEvidenceState = "teacher_action_needed"
    elif page.selected_evidence_id == observation.observation_id:
        if evidence.evidence_role != "selected" or not evidence.selected:
            raise ScanRecoveryAssemblyError(
                "Recovered evidence selection state is inconsistent."
            )
        state = "ready_for_review"
    else:
        if evidence.evidence_role not in {"candidate", "replacement"}:
            raise ScanRecoveryAssemblyError(
                "Unselected recovered evidence is not a reviewable candidate."
            )
        state = "selection_needed"
    return AssembledScanRecovery(
        persisted=fresh,
        assembled=assembled,
        evidence_state=state,
        page_state=page.page_state,
        selected_evidence_id=page.selected_evidence_id,
    )


__all__ = [
    "AssembledScanRecovery",
    "RecoveryEvidenceState",
    "ScanRecoveryAssemblyError",
    "assemble_persisted_scan_recovery",
]

"""Compatibility facade for observation-authoritative evidence persistence."""

from __future__ import annotations

from pathlib import Path

from quillan.module_errors import QuillanObservationError
from quillan.pds2_scan_intake import QuillanScanPageOutcome
from quillan.response_page_observation_persistence import (
    PersistedQuillanPageObservation,
    persist_quillan_page_observation,
)


class EvidenceFilingError(RuntimeError):
    """Raised when observation-backed evidence cannot be persisted."""


RoutedEvidenceFile = PersistedQuillanPageObservation


def file_routed_response_evidence(
    workspace_root: str | Path,
    *,
    page_outcome: QuillanScanPageOutcome,
) -> PersistedQuillanPageObservation:
    """Persist evidence only through an exact successful page outcome."""
    try:
        return persist_quillan_page_observation(Path(workspace_root), page_outcome)
    except QuillanObservationError as error:
        raise EvidenceFilingError(str(error)) from error


__all__ = [
    "EvidenceFilingError",
    "RoutedEvidenceFile",
    "file_routed_response_evidence",
]

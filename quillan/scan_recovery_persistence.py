"""Issue #419 Slice 3: persist one verified manually recovered page.

This boundary does not assemble submissions, select evidence, or append Core
scan-resolution records. It rechecks an earlier Core dispatch before the
existing Quillan evidence/observation transaction is allowed to write.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pds_core.module_profiles import ModuleRegistry

from quillan.pds2_scan_intake import validate_scan_workspace
from quillan.response_page_observation_persistence import (
    PersistedQuillanPageObservation,
    persist_quillan_dispatch_success,
)
from quillan.scan_recovery_dispatch import (
    DispatchedScanRecovery,
    ScanRecoveryDispatchError,
    dispatch_prepared_scan_recovery,
)


class ScanRecoveryPersistenceError(RuntimeError):
    """Previously dispatched recovery cannot safely enter the durable writer."""


@dataclass(frozen=True, slots=True)
class PersistedScanRecovery:
    """Verified persisted observation, not proof of submission assembly."""

    dispatched: DispatchedScanRecovery
    persisted: PersistedQuillanPageObservation

    @property
    def status(self) -> str:
        """Indicate whether the canonical transaction was new or existing."""
        return self.persisted.status


def persist_dispatched_scan_recovery(
    workspace_root: str | Path,
    dispatched: DispatchedScanRecovery,
    *,
    registry: ModuleRegistry | None = None,
) -> PersistedScanRecovery:
    """Reauthorize one exact Core success and persist canonical page evidence.

    Original retained bytes, route, failure decision, and issuance are
    revalidated through Slice 2 before entering the existing transactional
    writer. Expected write/integrity errors retain their original Quillan
    types and possible durable-artifact paths for later retry handling.
    """
    if type(dispatched) is not DispatchedScanRecovery:
        raise ScanRecoveryPersistenceError(
            "Persistence requires an exact dispatched scan recovery."
        )
    try:
        root = validate_scan_workspace(Path(os.path.abspath(workspace_root)))
        fresh = dispatch_prepared_scan_recovery(
            root, dispatched.prepared, registry=registry
        )
    except (OSError, TypeError, ValueError, ScanRecoveryDispatchError) as error:
        raise ScanRecoveryPersistenceError(
            f"Recovery dispatch must be reverified before persistence: {error}"
        ) from error

    if (
        fresh.request != dispatched.request
        or fresh.page_result != dispatched.page_result
        or fresh.success.resolution != dispatched.success.resolution
        or fresh.success.profile != dispatched.success.profile
        or fresh.success.module_result != dispatched.success.module_result
    ):
        raise ScanRecoveryPersistenceError(
            "The earlier recovery dispatch is stale or contradictory; "
            "prepare and dispatch the page again."
        )

    # Reuse exactly the same transaction as normal QR intake. In particular,
    # neither a fake QR payload nor a fake QuillanScanPageOutcome is created.
    persisted = persist_quillan_dispatch_success(root, fresh.success)
    return PersistedScanRecovery(dispatched=fresh, persisted=persisted)


__all__ = [
    "PersistedScanRecovery",
    "ScanRecoveryPersistenceError",
    "persist_dispatched_scan_recovery",
]

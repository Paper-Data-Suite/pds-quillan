"""Assignment-level observation-authoritative submission assembly."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from quillan.submission_observation_assembly import (
    QuillanSubmissionAssemblyBatch,
    assemble_quillan_submission_manifests,
)


def assemble_assignment_submissions(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    created_at: datetime | str | None = None,
    updated_at: datetime | str | None = None,
) -> QuillanSubmissionAssemblyBatch:
    """Assemble current observations using immutable issuance page identity."""
    timestamp = updated_at if updated_at is not None else created_at
    return assemble_quillan_submission_manifests(
        Path(workspace_root),
        class_id,
        assignment_id,
        timestamp=timestamp,
    )


__all__ = ["assemble_assignment_submissions"]

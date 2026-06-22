"""Safely open local Quillan evidence from the active PDS workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from pds_core.local_open import LocalOpenError, open_local_path


class EvidenceOpeningError(Exception):
    """Raised when Quillan evidence cannot be opened safely."""


@dataclass(frozen=True, slots=True)
class OpenedEvidence:
    """Information about a local evidence file opened for review."""

    evidence_path: Path
    evidence_relative_path: str


def resolve_workspace_evidence_path(
    workspace_root: str | Path,
    evidence_path: str | Path,
) -> Path:
    """Resolve a workspace-relative evidence path that stays in the workspace."""
    raw_evidence_path = str(evidence_path)
    stripped_evidence_path = raw_evidence_path.strip()

    if not stripped_evidence_path:
        raise EvidenceOpeningError("Evidence path must not be empty.")
    if stripped_evidence_path.lower().startswith(
        ("http://", "https://", "file://")
    ):
        raise EvidenceOpeningError("Evidence path must be a local path, not a URL.")

    candidate = Path(raw_evidence_path)
    if candidate.is_absolute() or PureWindowsPath(raw_evidence_path).drive:
        raise EvidenceOpeningError(
            "Evidence path must be relative to the PDS workspace."
        )

    try:
        resolved_workspace_root = _resolve_workspace_root(workspace_root)
        resolved_evidence_path = (
            resolved_workspace_root / candidate
        ).resolve(strict=False)
        resolved_evidence_path.relative_to(resolved_workspace_root)
    except (OSError, RuntimeError, ValueError) as error:
        raise EvidenceOpeningError(
            "Evidence path must remain inside the PDS workspace."
        ) from error

    return resolved_evidence_path


def open_workspace_evidence(
    workspace_root: str | Path,
    evidence_path: str | Path,
) -> OpenedEvidence:
    """Open one existing local evidence file inside the active PDS workspace."""
    resolved_workspace_root = _resolve_workspace_root(workspace_root)
    resolved_evidence_path = resolve_workspace_evidence_path(
        resolved_workspace_root,
        evidence_path,
    )

    if not resolved_evidence_path.exists():
        raise EvidenceOpeningError(
            f"Evidence file does not exist: "
            f"{resolved_evidence_path.relative_to(resolved_workspace_root).as_posix()}"
        )
    if not resolved_evidence_path.is_file():
        raise EvidenceOpeningError("Evidence path must identify a file.")

    try:
        opened_path = open_local_path(resolved_evidence_path)
    except LocalOpenError as error:
        raise EvidenceOpeningError(f"Could not open evidence file: {error}") from error

    return OpenedEvidence(
        evidence_path=opened_path.resolve(strict=False),
        evidence_relative_path=resolved_evidence_path.relative_to(
            resolved_workspace_root
        ).as_posix(),
    )


def _resolve_workspace_root(workspace_root: str | Path) -> Path:
    """Resolve the workspace root with a Quillan-owned error boundary."""
    try:
        return Path(workspace_root).resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise EvidenceOpeningError(
            f"Could not resolve the PDS workspace root: {error}"
        ) from error

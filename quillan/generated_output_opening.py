"""Safely open generated Quillan outputs from the active PDS workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pds_core.local_open import LocalOpenError, open_local_path


class GeneratedOutputOpeningError(Exception):
    """Raised when generated output cannot be opened safely."""


@dataclass(frozen=True, slots=True)
class OpenedGeneratedOutput:
    """Information about a generated output path opened for the teacher."""

    path: Path
    relative_path: str


def resolve_generated_output_path(
    workspace_root: str | Path,
    output_path: str | Path,
) -> Path:
    """Resolve a generated output path that stays in the PDS workspace."""
    raw_output_path = str(output_path)
    stripped_output_path = raw_output_path.strip()

    if not stripped_output_path:
        raise GeneratedOutputOpeningError("Generated output path must not be empty.")
    if stripped_output_path.lower().startswith(
        ("http://", "https://", "file://")
    ):
        raise GeneratedOutputOpeningError(
            "Generated output path must be a local path, not a URL."
        )

    try:
        resolved_workspace_root = _resolve_workspace_root(workspace_root)
        candidate = Path(raw_output_path)
        if candidate.is_absolute():
            resolved_output_path = candidate.resolve(strict=False)
        else:
            resolved_output_path = (
                resolved_workspace_root / candidate
            ).resolve(strict=False)
        resolved_output_path.relative_to(resolved_workspace_root)
    except (OSError, RuntimeError, ValueError) as error:
        raise GeneratedOutputOpeningError(
            "Generated output path must remain inside the PDS workspace."
        ) from error

    return resolved_output_path


def open_generated_output_file(
    workspace_root: str | Path,
    output_path: str | Path,
) -> OpenedGeneratedOutput:
    """Open one existing generated file inside the active PDS workspace."""
    resolved_workspace_root = _resolve_workspace_root(workspace_root)
    resolved_output_path = resolve_generated_output_path(
        resolved_workspace_root,
        output_path,
    )

    if not resolved_output_path.exists():
        raise GeneratedOutputOpeningError(
            f"Generated output file does not exist: "
            f"{resolved_output_path.relative_to(resolved_workspace_root).as_posix()}"
        )
    if not resolved_output_path.is_file():
        raise GeneratedOutputOpeningError(
            "Generated output path must identify a file."
        )

    try:
        opened_path = open_local_path(resolved_output_path)
    except LocalOpenError as error:
        raise GeneratedOutputOpeningError(
            f"Could not open generated output file: {error}"
        ) from error

    return OpenedGeneratedOutput(
        path=opened_path.resolve(strict=False),
        relative_path=resolved_output_path.relative_to(
            resolved_workspace_root
        ).as_posix(),
    )


def open_generated_output_folder(
    workspace_root: str | Path,
    output_path: str | Path,
) -> OpenedGeneratedOutput:
    """Open the containing folder for an existing generated file."""
    resolved_workspace_root = _resolve_workspace_root(workspace_root)
    resolved_output_path = resolve_generated_output_path(
        resolved_workspace_root,
        output_path,
    )

    if not resolved_output_path.exists():
        raise GeneratedOutputOpeningError(
            f"Generated output file does not exist: "
            f"{resolved_output_path.relative_to(resolved_workspace_root).as_posix()}"
        )
    if not resolved_output_path.is_file():
        raise GeneratedOutputOpeningError(
            "Generated output path must identify a file."
        )

    containing_folder = resolved_output_path.parent
    if not containing_folder.exists():
        raise GeneratedOutputOpeningError(
            f"Generated output folder does not exist: "
            f"{containing_folder.relative_to(resolved_workspace_root).as_posix()}"
        )
    if not containing_folder.is_dir():
        raise GeneratedOutputOpeningError(
            "Generated output folder path must identify a directory."
        )

    try:
        opened_path = open_local_path(containing_folder)
    except LocalOpenError as error:
        raise GeneratedOutputOpeningError(
            f"Could not open generated output folder: {error}"
        ) from error

    return OpenedGeneratedOutput(
        path=opened_path.resolve(strict=False),
        relative_path=containing_folder.relative_to(
            resolved_workspace_root
        ).as_posix(),
    )


def _resolve_workspace_root(workspace_root: str | Path) -> Path:
    """Resolve the workspace root with a Quillan-owned error boundary."""
    try:
        return Path(workspace_root).resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise GeneratedOutputOpeningError(
            f"Could not resolve the PDS workspace root: {error}"
        ) from error

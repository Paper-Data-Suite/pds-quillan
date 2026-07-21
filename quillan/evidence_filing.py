"""Conservative retained-source and routed-evidence filing."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from pds_core.scan_retention import (
    RetainedSourceScan as RetainedSourceScan,
)

_COPY_BUFFER_SIZE: Final[int] = 1024 * 1024
_MAX_DUPLICATE_ATTEMPTS: Final[int] = 10_000
_SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".jpeg", ".jpg", ".pdf", ".png", ".tif", ".tiff"}
)


class EvidenceFilingError(RuntimeError):
    """Raised when retained source or routed evidence cannot be filed safely."""


@dataclass(frozen=True, slots=True)
class RoutedEvidenceFile:
    """Provenance for one successfully filed Quillan response page."""

    class_id: str
    assignment_id: str
    student_id: str
    page_number: int
    retained_source: RetainedSourceScan
    routed_evidence_path: Path
    routed_evidence_relative_path: str
    duplicate_number: int | None


def file_routed_response_evidence(
    workspace_root: str | Path,
    *,
    route_plan: object,
    source_file_path: str | Path,
    intake_timestamp: datetime,
    intake_date: date | str | None = None,
    routed_source_file_path: str | Path | None = None,
    routed_extension: str | None = None,
) -> RoutedEvidenceFile:
    """Reject the removed pre-#339 routed-evidence filing boundary."""
    _ = (
        workspace_root, route_plan, source_file_path, intake_timestamp,
        intake_date, routed_source_file_path, routed_extension,
    )
    raise EvidenceFilingError(
        "Routed-evidence filing is unavailable until the #339 observation contract."
    )


def _resolved_workspace_root(workspace_root: str | Path) -> Path:
    try:
        root = Path(workspace_root).resolve(strict=False)
        if not root.is_dir():
            raise EvidenceFilingError(
                f"Workspace root is not an existing directory: {root}"
            )
        return root
    except (OSError, TypeError, ValueError) as error:
        raise EvidenceFilingError(f"Invalid workspace root: {error}") from error


def _validated_route_plan(root: Path, route_plan: object) -> tuple[Path, int]:
    _ = (root, route_plan)
    raise EvidenceFilingError(
        "Legacy routed-evidence filing is disabled; PDS2 intake does not write evidence."
    )


def _readable_regular_file(value: str | Path, field_name: str) -> Path:
    try:
        path = Path(value)
        if not path.is_file():
            raise EvidenceFilingError(
                f"{field_name} must identify an existing regular file: {path}"
            )
        with path.open("rb"):
            pass
        return path
    except EvidenceFilingError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise EvidenceFilingError(f"Could not read {field_name}: {error}") from error


def _copy_exclusive(source: Path, destination: Path) -> None:
    destination_created = False
    try:
        with source.open("rb") as source_file:
            with destination.open("xb") as destination_file:
                destination_created = True
                shutil.copyfileobj(
                    source_file,
                    destination_file,
                    length=_COPY_BUFFER_SIZE,
                )
    except FileExistsError:
        raise
    except OSError:
        if destination_created:
            _remove_incomplete_copy(destination)
        raise


def _copy_routed_evidence(
    source: Path,
    routed_dir: Path,
    student_id: str,
    page_number: int,
    extension: str,
) -> tuple[Path, int | None]:
    base_name = f"response_{student_id}_pg_{page_number:03d}"
    for duplicate_number in range(_MAX_DUPLICATE_ATTEMPTS):
        duplicate_suffix = (
            "" if duplicate_number == 0 else f"__dup_{duplicate_number:03d}"
        )
        candidate = (routed_dir / f"{base_name}{duplicate_suffix}{extension}").resolve(
            strict=False
        )
        _require_contained(candidate, routed_dir, "routed evidence path")
        try:
            _copy_exclusive(source, candidate)
        except FileExistsError:
            continue
        except OSError as error:
            raise EvidenceFilingError(
                f"Could not copy routed evidence to {candidate}: {error}"
            ) from error
        return candidate, duplicate_number or None

    raise EvidenceFilingError(
        "Could not choose an available routed evidence filename after "
        f"{_MAX_DUPLICATE_ATTEMPTS} attempts."
    )


def _normalized_extension(extension: str) -> str:
    if not isinstance(extension, str):
        raise EvidenceFilingError("routed_extension must be a string.")
    normalized = extension.lower()
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    if normalized not in _SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
        raise EvidenceFilingError(
            f"Unsupported routed evidence extension; expected one of: {allowed}."
        )
    return normalized


def _create_directory(path: Path, root: Path, description: str) -> None:
    _require_contained(path, root, description)
    try:
        path.mkdir(parents=True, exist_ok=True)
        resolved_path = path.resolve(strict=True)
    except OSError as error:
        raise EvidenceFilingError(f"Could not create {description}: {error}") from error
    _require_contained(resolved_path, root, description)
    if not resolved_path.is_dir():
        raise EvidenceFilingError(f"{description.capitalize()} is not a directory.")


def _require_contained(path: Path, parent: Path, description: str) -> None:
    if path == parent or path.is_relative_to(parent):
        return
    raise EvidenceFilingError(f"{description.capitalize()} escapes its allowed root.")


def _workspace_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise EvidenceFilingError("Filed path is outside the workspace root.") from error


def _remove_incomplete_copy(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

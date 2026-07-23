"""Nonwriting validation for one retained Quillan source page."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from pds_core.scan_retention import RetainedSourceScan

from quillan._path_safety import is_link_like as _shared_is_link_like
from quillan.module_errors import QuillanRetainedSourceError
from quillan.retained_source_provenance import (
    validate_core_retention_event_consistency,
)


@dataclass(frozen=True, slots=True)
class ValidatedQuillanRetainedPageProvenance:
    retained_source: RetainedSourceScan
    source_page_number: int


def validate_quillan_retained_source(
    retained_source: object,
    *,
    workspace_root: Path,
    source_page_number: object,
) -> ValidatedQuillanRetainedPageProvenance:
    """Validate exact retained provenance and one source-page meaning."""
    try:
        if not isinstance(retained_source, RetainedSourceScan):
            raise ValueError("retained_source must be a RetainedSourceScan.")
        if not isinstance(workspace_root, Path):
            raise ValueError("workspace_root must be a Path.")
        page_number = _positive_integer(source_page_number, "source_page_number")
        validate_core_retention_event_consistency(
            source_scan_id=retained_source.source_scan_id,
            source_filename=retained_source.source_filename,
            source_sha256=retained_source.source_sha256,
            retained_source_path=retained_source.retained_source_path,
            retained_source_relative_path=(
                retained_source.retained_source_relative_path
            ),
            intake_timestamp=retained_source.intake_timestamp,
            intake_date=retained_source.intake_date,
            workspace_root=workspace_root,
        )
        _validate_file_chain(workspace_root, retained_source.retained_source_path)
        if retained_source.retained_source_path.suffix.lower() != ".pdf" and page_number != 1:
            raise ValueError("image retained sources contain only source page 1.")
        return ValidatedQuillanRetainedPageProvenance(
            retained_source=retained_source,
            source_page_number=page_number,
        )
    except QuillanRetainedSourceError:
        raise
    except (ValueError, TypeError, AttributeError, OSError) as error:
        raise QuillanRetainedSourceError(
            f"Invalid Quillan retained-source provenance: {error}"
        ) from error


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive non-Boolean integer.")
    return value


def _validate_file_chain(workspace_root: Path, retained_path: Path) -> None:
    absolute_root = Path(os.path.abspath(workspace_root))
    absolute_path = Path(os.path.abspath(retained_path))
    if workspace_root != absolute_root or retained_path != absolute_path:
        raise ValueError("workspace and retained paths must be absolute and canonical.")
    try:
        relative = absolute_path.relative_to(absolute_root)
    except ValueError as error:
        raise ValueError("retained source escapes the workspace.") from error
    current = absolute_root
    candidates = [current]
    for component in relative.parts:
        current /= component
        candidates.append(current)
    for candidate in candidates:
        if not os.path.lexists(candidate):
            raise ValueError("retained source path has a missing component.")
        if _is_link_like(candidate):
            raise ValueError("retained source path contains a symlink or junction.")
    if not absolute_root.is_dir():
        raise ValueError("workspace_root must be an existing directory.")
    if not absolute_path.is_file():
        raise ValueError("retained source must be an ordinary file.")
    if not os.access(absolute_path, os.R_OK):
        raise ValueError("retained source must be readable.")


def _is_link_like(path: Path) -> bool:
    return _shared_is_link_like(path)


__all__ = [
    "ValidatedQuillanRetainedPageProvenance",
    "validate_quillan_retained_source",
]

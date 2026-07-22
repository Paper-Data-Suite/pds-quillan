"""Shared safe direct-child discovery for Quillan assignment work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.work_paths import (
    QuillanWorkPathError,
    _is_link_like,
    preflight_quillan_work_collection,
    preflight_work_file_destination,
    quillan_work_paths,
)


@dataclass(frozen=True, slots=True)
class DiscoveredAssignment:
    """One ordinary direct work child and its validated assignment record."""

    assignment_id: str
    path: Path
    assignment: dict[str, Any] | None
    error: str | None


def discover_quillan_assignments(
    workspace_root: str | Path,
    class_id: str,
) -> tuple[DiscoveredAssignment, ...]:
    """Inspect only safe direct children of one Quillan work collection."""
    try:
        collection = preflight_quillan_work_collection(workspace_root, class_id)
    except QuillanWorkPathError:
        return ()
    try:
        entries = sorted(collection.iterdir(), key=lambda entry: entry.name)
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return ()

    discovered: list[DiscoveredAssignment] = []
    for entry in entries:
        try:
            validate_identifier(entry.name, "assignment_id")
        except IdentifierValidationError as error:
            discovered.append(
                DiscoveredAssignment(
                    entry.name,
                    entry / "assignment.json",
                    None,
                    f"Invalid direct assignment child ID: {error}",
                )
            )
            continue
        path = quillan_work_paths(
            workspace_root, class_id, entry.name
        ).assignment_path
        try:
            if _is_link_like(entry) or not entry.is_dir():
                raise AssignmentConfigError(
                    "Assignment work child is not an ordinary non-link directory."
                )
            preflight_work_file_destination(
                workspace_root,
                quillan_work_paths(workspace_root, class_id, entry.name).work_ref,
                "assignment.json",
            )
            if _is_link_like(path) or not path.is_file():
                raise AssignmentConfigError("Assignment config is missing.")
            assignment = load_assignment_config(path)
        except (AssignmentConfigError, QuillanWorkPathError, OSError) as error:
            discovered.append(
                DiscoveredAssignment(entry.name, path, None, str(error))
            )
            continue
        if assignment["assignment_id"] != entry.name:
            discovered.append(
                DiscoveredAssignment(
                    entry.name,
                    path,
                    None,
                    "Path assignment_id does not match assignment config "
                    "assignment_id.",
                )
            )
            continue
        if class_id not in assignment["class_ids"]:
            discovered.append(
                DiscoveredAssignment(
                    entry.name,
                    path,
                    None,
                    "Assignment config class_ids does not include its containing class.",
                )
            )
            continue
        discovered.append(DiscoveredAssignment(entry.name, path, assignment, None))
    return tuple(discovered)


__all__ = ["DiscoveredAssignment", "discover_quillan_assignments"]

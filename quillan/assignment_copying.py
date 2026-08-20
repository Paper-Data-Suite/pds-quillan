"""Safe planning and persistence for fresh Quillan assignment copies."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from pds_core.classes import load_class_roster
from pds_core.identifiers import validate_identifier
from pds_core.rosters import RosterError
from pds_core.standards import load_workspace_standards_library

from quillan._path_safety import is_link_like
from quillan.assignments import (
    AssignmentConfigError,
    validate_assignment_standards_selection,
)
from quillan.assignment_workflows import (
    AssignmentBatchWriteError,
    build_assignment_config,
    write_assignment_configs,
)
from quillan.record_context import (
    canonical_workspace_root,
    load_quillan_assignment_context,
    mutable_json_copy,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    QuillanWorkPaths,
    preflight_managed_work_layout,
    quillan_work_paths,
    quillan_work_ref,
)


class AssignmentCopyError(AssignmentConfigError):
    """A safe assignment copy could not be planned or committed."""


@dataclass(frozen=True, slots=True)
class AssignmentCopyDestination:
    """One create-only target for a planned assignment copy."""

    class_id: str
    path: Path


@dataclass(frozen=True, slots=True)
class AssignmentCopyPlan:
    """A fully validated, non-mutating assignment copy plan."""

    workspace_root: Path
    source_class_id: str
    source_assignment_id: str
    source_path: Path
    source_original_bytes: bytes
    target_class_ids: tuple[str, ...]
    target_assignment_id: str
    target_assignment_json: str
    destinations: tuple[AssignmentCopyDestination, ...]

    @property
    def assignment(self) -> dict[str, Any]:
        """Return an isolated mutable copy of the planned target assignment."""
        value = json.loads(self.target_assignment_json)
        if not isinstance(value, dict):
            raise AssignmentCopyError("Planned target assignment is not an object.")
        return cast(dict[str, Any], value)


def plan_assignment_copy(
    workspace_root: str | Path,
    *,
    source_class_id: str,
    source_assignment_id: str,
    target_class_ids: Sequence[str],
    target_assignment_id: str,
    title: str | None = None,
    student_prompt: str | None = None,
    created_at: datetime | str | None = None,
) -> AssignmentCopyPlan:
    """Plan a fresh assignment copy without creating or changing filesystem state."""
    root = canonical_workspace_root(workspace_root)
    try:
        validate_identifier(source_class_id, "source_class_id")
        validate_identifier(source_assignment_id, "source_assignment_id")
        validate_identifier(target_assignment_id, "assignment_id")
    except ValueError as error:
        raise AssignmentCopyError(str(error)) from error

    source_ref = quillan_work_ref(source_class_id, source_assignment_id)
    try:
        source_context = load_quillan_assignment_context(root, source_ref)
    except (OSError, ValueError) as error:
        raise AssignmentCopyError(
            f"Could not load source assignment: {error}"
        ) from error
    source = mutable_json_copy(source_context.assignment)

    try:
        standards_library = load_workspace_standards_library(root)
        validate_assignment_standards_selection(source, standards_library)
    except (OSError, ValueError) as error:
        raise AssignmentCopyError(
            f"Source assignment standards are not valid in this workspace: {error}"
        ) from error

    selected_classes = tuple(target_class_ids)
    if not selected_classes:
        raise AssignmentCopyError("At least one target class is required.")
    if len(set(selected_classes)) != len(selected_classes):
        raise AssignmentCopyError("Target class IDs must be unique.")

    for class_id in selected_classes:
        try:
            validate_identifier(class_id, "target_class_id")
            load_class_roster(root, class_id)
        except (OSError, ValueError, RosterError) as error:
            raise AssignmentCopyError(
                f"Target class {class_id!r} is not roster-ready: {error}"
            ) from error
        if class_id == source_class_id and target_assignment_id == source_assignment_id:
            raise AssignmentCopyError(
                "The exact source work identity cannot be its own copy destination."
            )

    target_title = source["title"] if title is None else title
    target_prompt = (
        source["student_prompt"] if student_prompt is None else student_prompt
    )
    if not isinstance(target_title, str):
        raise AssignmentCopyError("Source assignment title is not reusable text.")
    if not isinstance(target_prompt, str):
        raise AssignmentCopyError("Source student prompt is not reusable text.")

    try:
        target = build_assignment_config(
            assignment_id=target_assignment_id,
            title=target_title,
            class_ids=selected_classes,
            writing_type=cast(str, source["writing_type"]),
            student_prompt=target_prompt,
            standards_profile_id=cast(str, source["standards_profile_id"]),
            focus_standard_ids=cast(list[str], source["focus_standard_ids"]),
            review_unit=cast(dict[str, Any], source["review_unit"]),
            rating_scale=cast(dict[str, Any], source["rating_scale"]),
            basic_requirements=cast(dict[str, Any], source["basic_requirements"]),
            minimum_requirement_policy=cast(
                dict[str, Any], source["minimum_requirement_policy"]
            ),
            created_at=created_at,
        )
        validate_assignment_standards_selection(target, standards_library)
    except (AssignmentConfigError, ValueError) as error:
        raise AssignmentCopyError(f"Target assignment is invalid: {error}") from error

    destinations: list[AssignmentCopyDestination] = []
    for class_id in selected_classes:
        paths = quillan_work_paths(root, class_id, target_assignment_id)
        _require_clean_copy_destination(paths)
        _require_no_academic_registration(
            root, class_id, target_assignment_id
        )
        destinations.append(
            AssignmentCopyDestination(class_id=class_id, path=paths.assignment_path)
        )

    target_json = json.dumps(target, ensure_ascii=False, separators=(",", ":"))
    return AssignmentCopyPlan(
        workspace_root=root,
        source_class_id=source_class_id,
        source_assignment_id=source_assignment_id,
        source_path=source_context.paths.assignment_path,
        source_original_bytes=source_context.assignment_record.original_bytes,
        target_class_ids=selected_classes,
        target_assignment_id=target_assignment_id,
        target_assignment_json=target_json,
        destinations=tuple(destinations),
    )


def commit_assignment_copy(plan: AssignmentCopyPlan) -> tuple[Path, ...]:
    """Commit a reviewed copy plan using create-only guarded assignment writes."""
    if not isinstance(plan, AssignmentCopyPlan):
        raise AssignmentCopyError("plan must be an AssignmentCopyPlan.")

    source_ref = quillan_work_ref(plan.source_class_id, plan.source_assignment_id)
    try:
        current_source = load_quillan_assignment_context(
            plan.workspace_root, source_ref
        )
    except (OSError, ValueError) as error:
        raise AssignmentCopyError(
            f"Source assignment changed or became unavailable after planning: {error}"
        ) from error
    if (
        current_source.paths.assignment_path != plan.source_path
        or current_source.assignment_record.original_bytes != plan.source_original_bytes
    ):
        raise AssignmentCopyError(
            "Source assignment changed after preview; plan the copy again "
            "before saving."
        )

    current_source_assignment = mutable_json_copy(current_source.assignment)
    target_assignment = plan.assignment
    try:
        standards_library = load_workspace_standards_library(plan.workspace_root)
        validate_assignment_standards_selection(
            current_source_assignment, standards_library
        )
        validate_assignment_standards_selection(target_assignment, standards_library)
    except (OSError, ValueError) as error:
        raise AssignmentCopyError(
            "Assignment standards changed after preview; plan the copy again: "
            f"{error}"
        ) from error

    for class_id in plan.target_class_ids:
        try:
            load_class_roster(plan.workspace_root, class_id)
        except (OSError, ValueError, RosterError) as error:
            raise AssignmentCopyError(
                f"Target class {class_id!r} changed after preview: {error}"
            ) from error
        _require_clean_copy_destination(
            quillan_work_paths(
                plan.workspace_root,
                class_id,
                plan.target_assignment_id,
            )
        )
        _require_no_academic_registration(
            plan.workspace_root, class_id, plan.target_assignment_id
        )

    try:
        return write_assignment_configs(
            plan.workspace_root,
            plan.target_class_ids,
            target_assignment,
            overwrite=False,
        )
    except AssignmentBatchWriteError:
        raise
    except (OSError, ValueError) as error:
        raise AssignmentCopyError(
            f"Assignment copy was not committed: {error}"
        ) from error


def _require_no_academic_registration(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
) -> None:
    """Reject a target identity that already has explicit Core academic state."""
    from quillan.academic_work_registration import (
        load_current_quillan_academic_work_registration,
    )

    try:
        registration = load_current_quillan_academic_work_registration(
            workspace_root, class_id, assignment_id
        )
    except Exception as error:
        raise AssignmentCopyError(
            "Could not verify target Academic Work Registration state: "
            f"{error}"
        ) from error
    if registration is not None:
        raise AssignmentCopyError(
            "Copy target already has Core Academic Work Registration state: "
            f"{class_id}/{assignment_id}"
        )


def _require_clean_copy_destination(paths: QuillanWorkPaths) -> None:
    """Reject any target state beyond Quillan's empty static directory skeleton."""
    try:
        preflight_managed_work_layout(paths)
    except QuillanWorkPathError as error:
        raise AssignmentCopyError(str(error)) from error

    root = paths.work_root
    if not os.path.lexists(root):
        return
    if is_link_like(root) or not root.is_dir():
        raise AssignmentCopyError(
            f"Copy target work root is not an ordinary directory: {root}"
        )

    allowed_directories = {
        paths.work_root,
        paths.response_pages_dir,
        paths.response_page_issuances_dir,
        paths.response_page_records_dir,
        paths.templates_dir,
        paths.scans_dir,
        paths.submissions_dir,
        paths.exports_dir,
    }
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            children = tuple(directory.iterdir())
        except OSError as error:
            raise AssignmentCopyError(
                f"Could not inspect copy target {directory}: {error}"
            ) from error
        for child in children:
            if is_link_like(child):
                raise AssignmentCopyError(
                    "Copy target contains a symlink, junction, or reparse point: "
                    f"{child}"
                )
            if not child.is_dir():
                raise AssignmentCopyError(
                    f"Copy target already contains assignment state: {child}"
                )
            if child not in allowed_directories:
                raise AssignmentCopyError(
                    "Copy target already contains assignment state in an "
                    f"unexpected directory: {child}"
                )
            pending.append(child)

"""Storage paths for Quillan assignment data."""

from __future__ import annotations

from pathlib import Path

from quillan.work_paths import (
    quillan_work_paths,
    student_submission_dir as work_student_submission_dir,
)


def assignment_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the module-qualified work root for a Quillan assignment."""
    return quillan_work_paths(root, class_id, assignment_id).work_root


def assignment_config_path(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the module-qualified Quillan assignment configuration path."""
    return quillan_work_paths(root, class_id, assignment_id).assignment_path


def assignment_submissions_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the module-qualified submissions directory for an assignment."""
    return quillan_work_paths(root, class_id, assignment_id).submissions_dir


def assignment_scans_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the module-qualified routed-evidence directory for an assignment."""
    return quillan_work_paths(root, class_id, assignment_id).scans_dir


def assignment_templates_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the module-qualified templates directory for an assignment."""
    return quillan_work_paths(root, class_id, assignment_id).templates_dir


def student_submission_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the module-qualified directory for a student's submission."""
    paths = quillan_work_paths(root, class_id, assignment_id)
    return work_student_submission_dir(root, paths.work_ref, student_id)

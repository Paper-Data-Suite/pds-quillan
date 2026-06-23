"""Storage paths for Quillan assignment data."""

from __future__ import annotations

from pathlib import Path

from pds_core.routes import (
    assignment_config_path as pds_assignment_config_path,
    assignment_dir as pds_assignment_dir,
    assignment_scans_dir as pds_assignment_scans_dir,
    assignment_submissions_dir as pds_assignment_submissions_dir,
    assignment_templates_dir as pds_assignment_templates_dir,
    student_submission_dir as pds_student_submission_dir,
)


def assignment_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the shared PDS directory for a Quillan assignment."""
    return pds_assignment_dir(root, class_id, assignment_id)


def assignment_config_path(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the shared PDS assignment configuration path."""
    return pds_assignment_config_path(root, class_id, assignment_id)


def assignment_submissions_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the shared PDS submissions directory for an assignment."""
    return pds_assignment_submissions_dir(root, class_id, assignment_id)


def assignment_scans_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the shared PDS routed-evidence directory for an assignment."""
    return pds_assignment_scans_dir(root, class_id, assignment_id)


def assignment_templates_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the shared PDS templates directory for an assignment."""
    return pds_assignment_templates_dir(root, class_id, assignment_id)


def student_submission_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the shared PDS directory for a student's submission."""
    return pds_student_submission_dir(root, class_id, assignment_id, student_id)

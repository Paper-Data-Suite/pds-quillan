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


def submission_text_path(
    root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the plain-text submission path for a student."""
    return (
        student_submission_dir(root, class_id, assignment_id, student_id)
        / "submission.txt"
    )


def requirements_path(
    root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the requirements-check path for a student submission."""
    return (
        student_submission_dir(root, class_id, assignment_id, student_id)
        / "requirements.json"
    )


def tags_path(
    root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the evidence-tags path for a student submission."""
    return (
        student_submission_dir(root, class_id, assignment_id, student_id) / "tags.json"
    )


def scores_path(
    root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the scores path for a student submission."""
    return (
        student_submission_dir(root, class_id, assignment_id, student_id)
        / "scores.json"
    )


def feedback_path(
    root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the feedback path for a student submission."""
    return (
        student_submission_dir(root, class_id, assignment_id, student_id)
        / "feedback.md"
    )


def reports_dir(
    root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return Quillan's assignment-local reports directory."""
    return assignment_dir(root, class_id, assignment_id) / "reports"

"""Resilient teacher-facing student labels."""

from __future__ import annotations

from pathlib import Path

from pds_core.classes import load_class_roster
from pds_core.rosters import RosterError, student_display_name, student_lookup


def student_display_lookup(
    workspace_root: str | Path,
    class_id: str,
) -> dict[str, str]:
    """Return name-and-ID labels, or an empty mapping when a roster is unavailable."""
    try:
        roster = load_class_roster(workspace_root, class_id)
        students = student_lookup(roster)
    except (RosterError, OSError, ValueError, TypeError):
        return {}

    labels: dict[str, str] = {}
    for student_id, student in students.items():
        try:
            name = student_display_name(student).strip()
        except (RosterError, AttributeError, TypeError, ValueError):
            continue
        if name:
            labels[student_id] = f"{name} ({student_id})"
    return labels


def student_review_label(
    workspace_root: str | Path,
    class_id: str,
    student_id: str,
) -> str:
    """Return a teacher-friendly label with a safe ID-only fallback."""
    return student_display_lookup(workspace_root, class_id).get(student_id, student_id)

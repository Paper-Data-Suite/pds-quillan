"""Shared synthetic review records used by active export and snapshot tests."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
TIMESTAMP = "2026-06-22T14:20:00+00:00"


def _write_assignment(
    workspace: Path,
    *,
    class_id: str = CLASS_ID,
    assignment_id: str = ASSIGNMENT_ID,
) -> Path:
    """Write the canonical assignment required by contextual review services."""
    path = (
        workspace
        / "classes"
        / class_id
        / "modules"
        / "quillan"
        / "work"
        / assignment_id
        / "assignment.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    assignment = {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": assignment_id,
        "title": "Synthetic Essay",
        "class_ids": [class_id],
        "writing_type": "argument",
        "student_prompt": "Write a synthetic argument.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["synthetic:W.A"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_2_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                }
            ],
        },
        "basic_requirements": {"paragraphs_min": 5},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }
    path.write_text(json.dumps(assignment), encoding="utf-8")
    return path


def _manifest(student_id: str = STUDENT_ID) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": student_id,
        "expected_pages": 1,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def _review(
    state: str = "ready_for_export", student_id: str = STUDENT_ID
) -> dict[str, Any]:
    record = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=student_id,
        created_at=TIMESTAMP,
    )
    record["review_state"] = state
    record["updated_at"] = TIMESTAMP
    return record


def _write_manifest(workspace: Path) -> Path:
    return write_submission_manifest(
        submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )


def _write_review(workspace: Path, review: dict[str, Any]) -> Path:
    return write_review_record(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
    )

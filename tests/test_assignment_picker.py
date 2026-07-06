"""Tests for assignment picker discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quillan.assignment_picker import available_assignments


CLASS_ID = "english_12_p3"


def _assignment(
    assignment_id: str,
    *,
    title: str = "Synthetic Assignment",
) -> dict[str, Any]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": assignment_id,
        "title": title,
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Write a synthetic argument.",
        "standards_profile_id": "synthetic_ela",
        "focus_standard_ids": ["synthetic:W.1"],
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
        "basic_requirements": {},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
    }


def _write_assignment(
    workspace_root: Path,
    assignment_id: str,
    assignment: dict[str, Any],
) -> None:
    path = (
        workspace_root
        / "classes"
        / CLASS_ID
        / "assignments"
        / assignment_id
        / "assignment.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(assignment), encoding="utf-8")


def test_available_assignments_lists_valid_v2_assignments(tmp_path: Path) -> None:
    _write_assignment(
        tmp_path,
        "valid_assignment",
        _assignment("valid_assignment", title="Visible Title"),
    )

    choices = available_assignments(tmp_path, CLASS_ID)

    assert [choice.assignment_id for choice in choices] == ["valid_assignment"]
    assert choices[0].title == "Visible Title"


def test_available_assignments_skips_invalid_and_legacy_configs(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path, "valid_assignment", _assignment("valid_assignment"))
    _write_assignment(tmp_path, "invalid_assignment", {"assignment_id": "incomplete"})
    _write_assignment(
        tmp_path,
        "legacy_assignment",
        {
            "assignment_id": "legacy_assignment",
            "title": "Legacy",
            "class_ids": [CLASS_ID],
            "writing_type": "argument",
            "standards_profile_id": "synthetic_ela",
            "tagging_mode": "focus",
            "focus_standards": ["synthetic:W.1"],
            "basic_requirements": {},
            "rubric_id": "legacy",
        },
    )

    choices = available_assignments(tmp_path, CLASS_ID)

    assert [choice.assignment_id for choice in choices] == ["valid_assignment"]

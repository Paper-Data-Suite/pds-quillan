"""Tests for reusable Focus Standard comment runtime support."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.focus_standard_comments import (
    FocusStandardCommentError,
    append_saved_comment,
    focus_standard_comment_set_path,
    load_comment_set,
    lookup_comments,
    validate_comment_set,
)

TIMESTAMP = "2026-07-02T00:00:00+00:00"


def _comment_set() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "focus_standard_comment_set",
        "comment_set_id": "synthetic_argument_focus_comments",
        "title": "Synthetic Argument Focus Comments",
        "description": "Reusable teacher-authored Focus Standard comments.",
        "standards_profile_id": "synthetic_profile",
        "writing_types": ["argument"],
        "grade_band": None,
        "comments": [
            {
                "comment_id": "claim_next_step",
                "standard_id": "njsls-ela:W.1",
                "writing_types": ["argument"],
                "rating_values": [1],
                "label": "Develop claim explanation",
                "text": "Explain how your evidence supports the claim.",
                "purpose": "next_step",
                "student_facing": True,
                "active": True,
                "created_at": TIMESTAMP,
                "updated_at": TIMESTAMP,
                "source": {
                    "type": "manual",
                    "class_id": None,
                    "assignment_id": None,
                    "student_id": None,
                    "review_path": None,
                    "feedback_comment_id": None,
                    "saved_at": TIMESTAMP,
                },
                "usage": {"times_used": 0, "last_used_at": None},
                "module_details": {},
            }
        ],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def test_valid_comment_set_loads(tmp_path: Path) -> None:
    path = focus_standard_comment_set_path(tmp_path, "synthetic_argument_focus_comments")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(_comment_set()), encoding="utf-8")

    loaded = load_comment_set(path)

    assert loaded["comment_set_id"] == "synthetic_argument_focus_comments"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("schema", "schema_version"),
        ("module", "module"),
        ("record_type", "record_type"),
        ("duplicate", "Duplicate comment_id"),
        ("purpose", "purpose"),
        ("source", "source.type"),
        ("usage", "times_used"),
    ],
)
def test_invalid_comment_sets_are_rejected(mutation: str, message: str) -> None:
    data = _comment_set()
    if mutation == "schema":
        data["schema_version"] = "2"
    elif mutation == "module":
        data["module"] = "other"
    elif mutation == "record_type":
        data["record_type"] = "comment_bank"
    elif mutation == "duplicate":
        data["comments"].append(copy.deepcopy(data["comments"][0]))
    elif mutation == "purpose":
        data["comments"][0]["purpose"] = "score"
    elif mutation == "source":
        data["comments"][0]["source"]["type"] = "generated"
    elif mutation == "usage":
        data["comments"][0]["usage"]["times_used"] = -1

    with pytest.raises(FocusStandardCommentError, match=message):
        validate_comment_set(data)


def test_path_helper_uses_focus_standard_comments_not_legacy_comment_banks(
    tmp_path: Path,
) -> None:
    path = focus_standard_comment_set_path(tmp_path, "synthetic_argument_focus_comments")

    assert path == tmp_path / "shared" / "focus_standard_comments" / (
        "synthetic_argument_focus_comments.json"
    )
    assert "comment_banks" not in path.parts


def test_lookup_filters_standard_writing_type_rating_active_and_student_facing(
    tmp_path: Path,
) -> None:
    data = _comment_set()
    hidden_wrong_standard = copy.deepcopy(data["comments"][0])
    hidden_wrong_standard["comment_id"] = "wrong_standard"
    hidden_wrong_standard["standard_id"] = "njsls-ela:L.2"
    hidden_wrong_type = copy.deepcopy(data["comments"][0])
    hidden_wrong_type["comment_id"] = "wrong_type"
    hidden_wrong_type["writing_types"] = ["narrative"]
    hidden_wrong_rating = copy.deepcopy(data["comments"][0])
    hidden_wrong_rating["comment_id"] = "wrong_rating"
    hidden_wrong_rating["rating_values"] = [2]
    inactive = copy.deepcopy(data["comments"][0])
    inactive["comment_id"] = "inactive"
    inactive["active"] = False
    teacher_only = copy.deepcopy(data["comments"][0])
    teacher_only["comment_id"] = "teacher_only"
    teacher_only["student_facing"] = False
    data["comments"].extend(
        [hidden_wrong_standard, hidden_wrong_type, hidden_wrong_rating, inactive, teacher_only]
    )
    path = focus_standard_comment_set_path(tmp_path, data["comment_set_id"])
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")

    matches = lookup_comments(
        tmp_path,
        standards_profile_id="synthetic_profile",
        writing_type="argument",
        standard_id="njsls-ela:W.1",
        rating_value=1,
    )

    assert [match.comment_id for match in matches] == ["claim_next_step"]


def test_saving_reusable_comment_creates_default_set_with_teacher_text(
    tmp_path: Path,
) -> None:
    saved = append_saved_comment(
        tmp_path,
        standards_profile_id="synthetic_profile",
        writing_type="argument",
        standard_id="njsls-ela:W.1",
        label="Reusable next step",
        text="Teacher-approved reusable text.",
        purpose="next_step",
        rating_values=[1],
        source={
            "type": "teacher_saved_from_feedback",
            "class_id": "english12_p3_synthetic",
            "assignment_id": "essay_01_synthetic",
            "student_id": "00107",
            "review_path": (
                "classes/english12_p3_synthetic/modules/quillan/work/essay_01_synthetic/"
                "submissions/00107/review.json"
            ),
            "feedback_comment_id": "feedback_comment_0001",
            "saved_at": TIMESTAMP,
        },
        created_at=TIMESTAMP,
    )

    loaded = load_comment_set(saved.path)
    assert saved.comment_set_id == "synthetic_profile_argument_focus_comments"
    assert loaded["comments"][0]["source"]["type"] == "teacher_saved_from_feedback"
    assert loaded["comments"][0]["text"] == "Teacher-approved reusable text."


def test_teacher_tags_are_normalized_without_affecting_lookup(tmp_path: Path) -> None:
    saved = append_saved_comment(
        tmp_path,
        standards_profile_id="synthetic_profile",
        writing_type="narrative",
        standard_id="njsls-ela:W.3",
        label="Develop the scene",
        text="Develop the scene through dialogue and sensory details.",
        purpose="general",
        teacher_tags=["Character", "Scene Development", "dialogue", "character"],
        rating_values=[],
        source={
            "type": "manual",
            "class_id": None,
            "assignment_id": None,
            "student_id": None,
            "review_path": None,
            "feedback_comment_id": None,
            "saved_at": TIMESTAMP,
        },
        created_at=TIMESTAMP,
    )

    loaded = load_comment_set(saved.path)
    assert loaded["comments"][0]["module_details"] == {
        "teacher_tags": ["character", "scene_development", "dialogue"]
    }
    matches = lookup_comments(
        tmp_path,
        standards_profile_id="synthetic_profile",
        writing_type="narrative",
        standard_id="njsls-ela:W.3",
    )
    assert [match.comment_id for match in matches] == [saved.comment_id]


def test_existing_comment_without_teacher_tags_remains_valid() -> None:
    validate_comment_set(_comment_set())

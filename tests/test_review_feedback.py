"""Tests for Focus Standard feedback composition helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.focus_standard_comments import (
    focus_standard_comment_set_path,
    load_comment_set,
)
from quillan.review_feedback import (
    ReviewFeedbackError,
    add_custom_feedback_comment,
    mark_feedback_composed,
    select_reusable_feedback_comment,
    set_standard_feedback_options,
)
from quillan.review_record_paths import review_record_path
from tests.test_review_ratings import (
    ASSIGNMENT_ID,
    CLASS_ID,
    FIRST_TIMESTAMP,
    ORIGINAL_TIMESTAMP,
    SECOND_TIMESTAMP,
    STUDENT_ID,
    _review_record,
    _write_workspace,
)


def _read_review(root: Path) -> dict[str, Any]:
    return json.loads(
        review_record_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )


def _fresh_review() -> dict[str, Any]:
    review = _review_record()
    review["feedback"]["standard_feedback"] = []
    review["feedback"]["include_review_unit_observations"] = False
    return review


def _write_fresh_workspace(root: Path) -> None:
    _write_workspace(root, _fresh_review())


def _write_comment_set(root: Path) -> None:
    path = focus_standard_comment_set_path(root, "synthetic_argument_focus_comments")
    path.parent.mkdir(parents=True)
    data = {
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
                "rating_values": [2],
                "label": "Explain evidence",
                "text": "Explain why this evidence supports your claim.",
                "purpose": "next_step",
                "student_facing": True,
                "active": True,
                "created_at": ORIGINAL_TIMESTAMP,
                "updated_at": ORIGINAL_TIMESTAMP,
                "source": {
                    "type": "manual",
                    "class_id": None,
                    "assignment_id": None,
                    "student_id": None,
                    "review_path": None,
                    "feedback_comment_id": None,
                    "saved_at": ORIGINAL_TIMESTAMP,
                },
                "usage": {"times_used": 0, "last_used_at": None},
                "module_details": {},
            }
        ],
        "created_at": ORIGINAL_TIMESTAMP,
        "updated_at": ORIGINAL_TIMESTAMP,
        "module_details": {},
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_setting_standard_feedback_options_creates_record(tmp_path: Path) -> None:
    _write_fresh_workspace(tmp_path)

    result = set_standard_feedback_options(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        include_overall_rating=True,
        include_overall_rationale=False,
        included_observation_ids=["observation_0001"],
        updated_at=FIRST_TIMESTAMP,
    )

    review = _read_review(tmp_path)
    feedback = review["feedback"]["standard_feedback"][0]
    assert result.was_created is True
    assert feedback["standard_id"] == "njsls-ela:W.1"
    assert feedback["include_overall_rating"] is True
    assert feedback["include_overall_rationale"] is False
    assert feedback["included_observation_ids"] == ["observation_0001"]
    assert review["feedback"]["include_review_unit_observations"] is True


def test_setting_standard_feedback_options_preserves_existing_comments(
    tmp_path: Path,
) -> None:
    review = _review_record()
    review["feedback"]["standard_feedback"] = [
        {
            "standard_id": "njsls-ela:W.1",
            "include_overall_rating": True,
            "include_overall_rationale": True,
            "included_observation_ids": [],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "custom",
                    "text": "Existing comment.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": ORIGINAL_TIMESTAMP,
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    ]
    _write_workspace(tmp_path, review)

    set_standard_feedback_options(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        include_overall_rating=False,
        include_overall_rationale=False,
        included_observation_ids=[],
        updated_at=FIRST_TIMESTAMP,
    )

    comments = _read_review(tmp_path)["feedback"]["standard_feedback"][0]["comments"]
    assert comments[0]["text"] == "Existing comment."


@pytest.mark.parametrize(
    ("standard_id", "observation_ids", "message"),
    [
        ("missing:standard", [], "not a Focus Standard"),
        ("njsls-ela:W.1", ["missing"], "unknown observation_id"),
        ("njsls-ela:W.1", ["observation_0002"], "does not belong"),
    ],
)
def test_feedback_options_validate_standard_and_observations(
    tmp_path: Path, standard_id: str, observation_ids: list[str], message: str
) -> None:
    _write_fresh_workspace(tmp_path)

    with pytest.raises(ReviewFeedbackError, match=message):
        set_standard_feedback_options(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            standard_id=standard_id,
            include_overall_rating=True,
            include_overall_rationale=True,
            included_observation_ids=observation_ids,
            updated_at=FIRST_TIMESTAMP,
        )


def test_returned_without_full_review_rejects_feedback_composition(
    tmp_path: Path,
) -> None:
    review = _review_record()
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Return and revise.",
        "updated_at": ORIGINAL_TIMESTAMP,
    }
    _write_workspace(tmp_path, review)

    with pytest.raises(ReviewFeedbackError, match="returned without full"):
        add_custom_feedback_comment(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            standard_id="njsls-ela:W.1",
            text="Student-facing text.",
            include_in_feedback=True,
            save_for_reuse=False,
            created_at=FIRST_TIMESTAMP,
        )


def test_custom_comments_are_sequential_and_can_be_excluded(tmp_path: Path) -> None:
    _write_fresh_workspace(tmp_path)

    first = add_custom_feedback_comment(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        text="Included custom comment.",
        include_in_feedback=True,
        save_for_reuse=False,
        created_at=FIRST_TIMESTAMP,
    )
    second = add_custom_feedback_comment(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        text="Excluded custom comment.",
        include_in_feedback=False,
        save_for_reuse=False,
        created_at=SECOND_TIMESTAMP,
    )

    comments = _read_review(tmp_path)["feedback"]["standard_feedback"][0]["comments"]
    assert first.feedback_comment_id == "feedback_comment_0001"
    assert second.feedback_comment_id == "feedback_comment_0002"
    assert [comment["include_in_feedback"] for comment in comments] == [True, False]
    assert not (tmp_path / "shared" / "focus_standard_comments").exists()


def test_custom_comment_can_be_saved_for_reuse_with_approved_text(
    tmp_path: Path,
) -> None:
    review = _fresh_review()
    review["overall_standard_ratings"] = [
        {
            "standard_id": "njsls-ela:W.1",
            "rating": 2,
            "rationale": "Clear claim.",
            "include_in_feedback": True,
            "updated_at": ORIGINAL_TIMESTAMP,
            "module_details": {},
        }
    ]
    _write_workspace(tmp_path, review)

    result = add_custom_feedback_comment(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        text="Student-specific custom text.",
        include_in_feedback=True,
        save_for_reuse=True,
        reusable_label="General claim next step",
        reusable_text="Reusable teacher-approved text.",
        purpose="next_step",
        created_at=FIRST_TIMESTAMP,
    )

    assert result.saved_reusable_comment is not None
    saved = load_comment_set(result.saved_reusable_comment.path)
    assert saved["comments"][0]["text"] == "Reusable teacher-approved text."
    assert saved["comments"][0]["rating_values"] == [2]
    assert _read_review(tmp_path)["feedback"]["standard_feedback"][0]["comments"][0][
        "text"
    ] == "Student-specific custom text."


def test_selected_reusable_comment_is_snapshotted_and_usage_updates(
    tmp_path: Path,
) -> None:
    review = _fresh_review()
    review["overall_standard_ratings"] = [
        {
            "standard_id": "njsls-ela:W.1",
            "rating": 2,
            "rationale": "Clear claim.",
            "include_in_feedback": True,
            "updated_at": ORIGINAL_TIMESTAMP,
            "module_details": {},
        }
    ]
    _write_workspace(tmp_path, review)
    _write_comment_set(tmp_path)

    result = select_reusable_feedback_comment(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        comment_set_id="synthetic_argument_focus_comments",
        comment_id="claim_next_step",
        include_in_feedback=True,
        created_at=FIRST_TIMESTAMP,
    )

    comment = _read_review(tmp_path)["feedback"]["standard_feedback"][0]["comments"][0]
    assert result.feedback_comment_id == "feedback_comment_0001"
    assert comment["source"] == "reusable_focus_standard_comment"
    assert comment["text"] == "Explain why this evidence supports your claim."
    loaded = load_comment_set(
        focus_standard_comment_set_path(tmp_path, "synthetic_argument_focus_comments")
    )
    loaded["comments"][0]["text"] = "Changed later."
    assert comment["text"] != loaded["comments"][0]["text"]
    assert loaded["comments"][0]["usage"]["times_used"] == 1


def test_mark_feedback_composed_is_explicit(tmp_path: Path) -> None:
    _write_fresh_workspace(tmp_path)
    add_custom_feedback_comment(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        text="Included custom comment.",
        include_in_feedback=True,
        save_for_reuse=False,
        created_at=FIRST_TIMESTAMP,
    )

    before = _read_review(tmp_path)
    assert before["review_state"] == "observations_complete"
    completed = mark_feedback_composed(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        updated_at=SECOND_TIMESTAMP,
    )

    after = _read_review(tmp_path)
    assert completed.review_state == "feedback_composed"
    assert after["review_state"] == "feedback_composed"
    assert not {"comments", "scores", "tags", "notes"} & after.keys()
    assert after["overall_standard_ratings"] == before["overall_standard_ratings"]
    assert after["review_units"] == before["review_units"]

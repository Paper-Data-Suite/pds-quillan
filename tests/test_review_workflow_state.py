"""Focused coverage for canonical review workflow state updates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.review_record import ALLOWED_REVIEW_STATES, build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.review_workflow_state import (
    REVIEW_WORKFLOW_STATES,
    ReviewWorkflowStateError,
    set_review_workflow_state,
)
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english10_p2"
ASSIGNMENT_ID = "argument_01"
STUDENT_ID = "00107"
CREATED = "2026-07-13T12:00:00+00:00"
UPDATED = "2026-07-13T13:00:00+00:00"


def _assignment() -> dict[str, Any]:
    return {
        "schema_version": "2", "module": "quillan", "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID, "title": "Argument", "class_ids": [CLASS_ID],
        "writing_type": "argument", "student_prompt": "Make an argument.",
        "standards_profile_id": "ela", "focus_standard_ids": ["W.1"],
        "review_unit": {"type": "paragraph", "singular_label": "paragraph", "plural_label": "paragraphs"},
        "rating_scale": {"scale_id": "two", "levels": [{"value": 1, "label": "Developing", "description": "Developing."}]},
        "basic_requirements": {"paragraphs_min": 3, "required_elements": []},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": CREATED, "updated_at": CREATED, "module_details": {},
    }


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": "1", "module": "quillan", "record_type": "submission_manifest",
        "class_id": CLASS_ID, "assignment_id": ASSIGNMENT_ID, "student_id": STUDENT_ID,
        "expected_pages": None, "submission_state": "unreviewed", "pages": [],
        "created_at": CREATED, "updated_at": CREATED,
        "module_details": {"submission_entry_method": "plain_paper_manual"},
    }


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    assignment_path = tmp_path / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    assignment_path.parent.mkdir(parents=True)
    assignment_path.write_text(json.dumps(_assignment()), encoding="utf-8")
    write_submission_manifest(
        submission_manifest_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )
    return tmp_path


def _review() -> dict[str, Any]:
    review = build_empty_review_record(
        class_id=CLASS_ID, assignment_id=ASSIGNMENT_ID, student_id=STUDENT_ID,
        created_at=CREATED,
    )
    review["private_notes"] = [{
        "private_note_id": "private_note_0001", "text": "Keep this.",
        "created_at": CREATED, "updated_at": CREATED, "module_details": {},
    }]
    return review


def test_ordered_states_match_schema() -> None:
    assert frozenset(REVIEW_WORKFLOW_STATES) == ALLOWED_REVIEW_STATES


@pytest.mark.parametrize("state", ["not_started", "observations_in_progress", "exported"])
def test_missing_review_is_created_without_changing_plain_paper_manifest(
    workspace: Path, state: str
) -> None:
    manifest_path = submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = manifest_path.read_bytes()
    result = set_review_workflow_state(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, state, updated_at=UPDATED
    )
    review = json.loads(result.review_record_path.read_text(encoding="utf-8"))
    assert result.review_was_created is True
    assert result.previous_state is None
    assert review["review_state"] == state
    assert review["created_at"] == review["updated_at"] == UPDATED
    assert review["exports"] == {"feedback_pdf": None, "feedback_markdown": None}
    assert manifest_path.read_bytes() == before


def test_existing_update_preserves_every_field_except_state_and_timestamp(workspace: Path) -> None:
    path = write_review_record(review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID), _review())
    before = json.loads(path.read_text(encoding="utf-8"))
    result = set_review_workflow_state(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "feedback_composed", updated_at=UPDATED
    )
    after = json.loads(path.read_text(encoding="utf-8"))
    assert result.previous_state == "not_started"
    for key in before:
        if key not in {"review_state", "updated_at"}:
            assert after[key] == before[key]


def test_returned_entry_and_coherent_exit_are_guarded(workspace: Path) -> None:
    path = write_review_record(review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID), _review())
    before = path.read_bytes()
    with pytest.raises(ReviewWorkflowStateError, match="requirements set-outcome"):
        set_review_workflow_state(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "returned_without_full_review", updated_at=UPDATED)
    assert path.read_bytes() == before

    returned = _review()
    returned["minimum_requirement_checks"] = [{
        "requirement_check_id": "requirement_check_0001", "requirement_key": "paragraphs_min",
        "label": "Minimum paragraphs", "expected": 3, "met": False,
        "updated_at": CREATED, "module_details": {},
    }]
    returned["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review", "returned_without_full_review": True,
        "teacher_note": "Please revise.", "updated_at": CREATED,
    }
    returned["review_state"] = "returned_without_full_review"
    write_review_record(path, returned, overwrite=True)
    before = path.read_bytes()
    with pytest.raises(ReviewWorkflowStateError, match="minimum-requirement outcome"):
        set_review_workflow_state(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "not_started", updated_at=UPDATED)
    assert path.read_bytes() == before


def test_invalid_and_naive_timestamps_write_nothing(workspace: Path) -> None:
    path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    with pytest.raises(ReviewWorkflowStateError, match="Allowed states"):
        set_review_workflow_state(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "bogus")
    with pytest.raises(ReviewWorkflowStateError, match="timezone-aware"):
        set_review_workflow_state(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, "not_started", updated_at="2026-07-13T13:00:00")
    assert not path.exists()

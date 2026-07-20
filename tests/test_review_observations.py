"""Tests for review-unit Focus Standard observation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from quillan.review_observations import (
    ReviewObservationError,
    mark_observations_complete,
    set_review_unit_observation,
    set_review_units,
)
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
ORIGINAL_TIMESTAMP = "2026-06-20T12:00:00+00:00"
FIRST_TIMESTAMP = "2026-07-02T12:00:00+00:00"
SECOND_TIMESTAMP = "2026-07-02T13:00:00+00:00"
THIRD_TIMESTAMP = "2026-07-02T14:00:00+00:00"


def _assignment() -> dict[str, Any]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Write an argument.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["njsls-ela:W.1", "njsls-ela:L.2"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_2_level",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Limited."},
                {"value": 2, "label": "Secure", "description": "Clear."},
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
        "created_at": ORIGINAL_TIMESTAMP,
        "updated_at": ORIGINAL_TIMESTAMP,
        "module_details": {},
    }


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": 1,
        "submission_state": "unreviewed",
        "pages": [
            {
                "page_number": 1,
                "page_state": "present",
                "selected_evidence_id": "evidence_001",
                "evidence": [
                    {
                        "evidence_id": "evidence_001",
                        "routed_evidence_path": (
                            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
                            "scans/response_00107_pg_001.pdf"
                        ),
                        "evidence_role": "selected",
                        "evidence_state": "active",
                        "duplicate_number": None,
                        "created_at": ORIGINAL_TIMESTAMP,
                        "retained_source": None,
                        "module_details": {},
                    }
                ],
            }
        ],
        "created_at": ORIGINAL_TIMESTAMP,
        "updated_at": ORIGINAL_TIMESTAMP,
        "module_details": {},
    }


def _write_workspace(root: Path) -> None:
    assignment_dir = root / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID
    assignment_dir.mkdir(parents=True)
    (assignment_dir / "assignment.json").write_text(
        json.dumps(_assignment()),
        encoding="utf-8",
    )
    write_submission_manifest(
        submission_manifest_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )


def _read_review(root: Path) -> dict[str, Any]:
    data = json.loads(
        review_record_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(data, dict)
    return cast(dict[str, Any], data)


def test_setting_review_units_creates_v2_record_with_assignment_unit_type(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)

    result = set_review_units(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}, {"sequence": 2, "page_number": 1, "evidence_id": "evidence_001"}],
        updated_at=FIRST_TIMESTAMP,
    )

    review = _read_review(tmp_path)
    assert result.unit_count == 2
    assert review["schema_version"] == "2"
    assert review["created_at"] == FIRST_TIMESTAMP
    assert review["updated_at"] == FIRST_TIMESTAMP
    assert review["review_state"] == "observations_in_progress"
    assert review["review_units"][0] == {
        "unit_id": "paragraph_1",
        "sequence": 1,
        "label": "Paragraph 1",
        "unit_type": "paragraph",
        "standard_observations": [],
        "module_details": {},
    }
    assert review["review_units"][1]["unit_id"] == "paragraph_2"
    assert review["review_units"][1]["label"] == "Paragraph 2"
    assert review["review_units"][1]["unit_type"] == "paragraph"
    assert review["review_units"][1]["page_number"] == 1
    assert review["review_units"][1]["evidence_id"] == "evidence_001"
    assert review["overall_standard_ratings"] == []
    assert review["feedback"]["standard_feedback"] == []
    for legacy_field in ("notes", "tags", "scores", "comments", "requirement_checks"):
        assert legacy_field not in review


def test_replacing_review_units_preserves_matching_unit_observations(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)
    set_review_units(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=FIRST_TIMESTAMP,
    )
    first = set_review_unit_observation(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        unit_id="paragraph_1",
        standard_id="njsls-ela:W.1",
        applicable=True,
        evidence_present=True,
        rationale="Clear claim.",
        include_in_feedback=True,
        updated_at=SECOND_TIMESTAMP,
    )

    set_review_units(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}, {"sequence": 2}],
        updated_at=THIRD_TIMESTAMP,
    )

    review = _read_review(tmp_path)
    observations = review["review_units"][0]["standard_observations"]
    assert observations[0]["observation_id"] == first.observation_id
    assert observations[0]["standard_id"] == "njsls-ela:W.1"
    assert review["review_units"][1]["standard_observations"] == []
    assert review["created_at"] == FIRST_TIMESTAMP
    assert review["updated_at"] == THIRD_TIMESTAMP


def test_setting_observations_writes_applicable_and_not_applicable_shapes(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)
    set_review_units(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=FIRST_TIMESTAMP,
    )

    first = set_review_unit_observation(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        unit_id="paragraph_1",
        standard_id="njsls-ela:W.1",
        applicable=True,
        evidence_present=True,
        rationale="Relevant evidence is present.",
        include_in_feedback=True,
        updated_at=SECOND_TIMESTAMP,
    )
    second = set_review_unit_observation(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        unit_id="paragraph_1",
        standard_id="njsls-ela:L.2",
        applicable=False,
        evidence_present=True,
        rationale="This unit is only a transition.",
        include_in_feedback=None,
        updated_at=THIRD_TIMESTAMP,
    )

    review = _read_review(tmp_path)
    observations = review["review_units"][0]["standard_observations"]
    assert first.was_created is True
    assert second.was_created is True
    assert observations[0] == {
        "observation_id": "observation_0001",
        "standard_id": "njsls-ela:W.1",
        "applicable": True,
        "evidence_present": True,
        "rating": None,
        "rationale": "Relevant evidence is present.",
        "include_in_feedback": True,
        "updated_at": SECOND_TIMESTAMP,
        "module_details": {},
    }
    assert observations[1] == {
        "observation_id": "observation_0002",
        "standard_id": "njsls-ela:L.2",
        "applicable": False,
        "evidence_present": None,
        "rating": None,
        "rationale": "This unit is only a transition.",
        "include_in_feedback": False,
        "updated_at": THIRD_TIMESTAMP,
        "module_details": {},
    }
    assert review["review_state"] == "observations_in_progress"
    assert review["updated_at"] == THIRD_TIMESTAMP
    assert review["overall_standard_ratings"] == []
    assert review["feedback"]["standard_feedback"] == []


def test_updating_existing_observation_preserves_observation_id(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)
    set_review_units(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=FIRST_TIMESTAMP,
    )
    created = set_review_unit_observation(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        unit_id="paragraph_1",
        standard_id="njsls-ela:W.1",
        applicable=True,
        evidence_present=True,
        rationale=None,
        include_in_feedback=True,
        updated_at=SECOND_TIMESTAMP,
    )

    updated = set_review_unit_observation(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        unit_id="paragraph_1",
        standard_id="njsls-ela:W.1",
        applicable=True,
        evidence_present=False,
        rationale="Evidence is attempted but missing.",
        include_in_feedback=False,
        updated_at=THIRD_TIMESTAMP,
    )

    observation = _read_review(tmp_path)["review_units"][0]["standard_observations"][0]
    assert updated.was_created is False
    assert updated.observation_id == created.observation_id
    assert observation["observation_id"] == "observation_0001"
    assert observation["evidence_present"] is False
    assert observation["rating"] is None
    assert observation["include_in_feedback"] is False


def test_observation_requires_existing_unit_and_assignment_focus_standard(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)

    with pytest.raises(ReviewObservationError, match="Review units"):
        set_review_unit_observation(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            unit_id="paragraph_1",
            standard_id="njsls-ela:W.1",
            applicable=True,
            evidence_present=True,
            updated_at=FIRST_TIMESTAMP,
        )

    set_review_units(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=FIRST_TIMESTAMP,
    )
    with pytest.raises(ReviewObservationError, match="not a Focus Standard"):
        set_review_unit_observation(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            unit_id="paragraph_1",
            standard_id="njsls-ela:W.MISSING",
            applicable=True,
            evidence_present=True,
            updated_at=SECOND_TIMESTAMP,
        )
    with pytest.raises(ReviewObservationError, match="Review unit not found"):
        set_review_unit_observation(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            unit_id="paragraph_99",
            standard_id="njsls-ela:W.1",
            applicable=True,
            evidence_present=True,
            updated_at=SECOND_TIMESTAMP,
        )


def test_observation_rating_uses_assignment_scale_and_remains_optional(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)
    set_review_units(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=FIRST_TIMESTAMP,
    )
    record_path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = record_path.read_bytes()
    with pytest.raises(ReviewObservationError, match="Allowed values"):
        set_review_unit_observation(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            unit_id="paragraph_1",
            standard_id="njsls-ela:W.1",
            applicable=True,
            evidence_present=True,
            rating=99,
            updated_at=SECOND_TIMESTAMP,
        )
    assert record_path.read_bytes() == before

    updated = set_review_unit_observation(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        unit_id="paragraph_1",
        standard_id="njsls-ela:W.1",
        applicable=True,
        evidence_present=True,
        rating=2,
        updated_at=SECOND_TIMESTAMP,
    )
    assert updated.rating == 2
    assert updated.rating_label == "Secure"

def test_mark_observations_complete_sets_state_without_creating_ratings(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)
    set_review_units(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=FIRST_TIMESTAMP,
    )

    result = mark_observations_complete(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        updated_at=SECOND_TIMESTAMP,
    )

    review = _read_review(tmp_path)
    assert result.review_state == "observations_complete"
    assert result.missing_focus_standard_pairs == 2
    assert review["review_state"] == "observations_complete"
    assert review["overall_standard_ratings"] == []
    assert review["feedback"]["standard_feedback"] == []


def test_returned_without_full_review_records_cannot_be_modified(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)
    review = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=ORIGINAL_TIMESTAMP,
    )
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Missing required work.",
        "updated_at": FIRST_TIMESTAMP,
    }
    write_review_record(
        review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
    )

    with pytest.raises(ReviewObservationError, match="returned without full standards review"):
        set_review_units(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            [{"sequence": 1}],
            updated_at=SECOND_TIMESTAMP,
        )

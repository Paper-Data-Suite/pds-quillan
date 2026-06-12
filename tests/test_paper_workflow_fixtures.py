"""Validation and consistency tests for synthetic paper workflow fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from quillan.assignments import load_assignment_config
from quillan.standards import load_standards_profile
from quillan.submissions import load_submission_metadata

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "paper_workflow"
SUBMISSION_DIR = FIXTURE_DIR / "submissions" / "stu_0001"


def _load_students() -> list[dict[str, Any]]:
    """Load the minimal synthetic student display fixture."""
    students = json.loads((FIXTURE_DIR / "students.json").read_text(encoding="utf-8"))
    assert isinstance(students, list)
    assert all(isinstance(student, dict) for student in students)
    return cast(list[dict[str, Any]], students)


def test_assignment_fixture_is_valid() -> None:
    assignment = load_assignment_config(FIXTURE_DIR / "assignment.json")

    assert assignment["assignment_id"] == "literary_argument_synthetic"


def test_standards_profile_fixture_is_valid_and_has_review_comment() -> None:
    profile = load_standards_profile(FIXTURE_DIR / "standards_profile.json")

    assert profile["standards"]
    assert any(standard["comments"] for standard in profile["standards"])


def test_submission_fixture_is_valid_and_text_exists() -> None:
    submission = load_submission_metadata(SUBMISSION_DIR / "submission.json")
    text_path = SUBMISSION_DIR / cast(str, submission["text_file"])

    assert text_path.is_file()
    assert text_path.read_text(encoding="utf-8").strip()


def test_students_fixture_has_synthetic_display_data() -> None:
    students = _load_students()

    assert students
    for student in students:
        assert isinstance(student.get("student_id"), str)
        assert student["student_id"].strip()
        assert isinstance(student.get("student_display_name"), str)
        assert student["student_display_name"].strip()
        assert isinstance(student.get("class_id"), str)
        assert student["class_id"].strip()


def test_fixture_ids_are_internally_consistent() -> None:
    assignment = load_assignment_config(FIXTURE_DIR / "assignment.json")
    profile = load_standards_profile(FIXTURE_DIR / "standards_profile.json")
    submission = load_submission_metadata(SUBMISSION_DIR / "submission.json")
    students = _load_students()
    matching_students = [
        student
        for student in students
        if student.get("student_id") == submission["student_id"]
    ]

    assert submission["assignment_id"] == assignment["assignment_id"]
    assert submission["class_id"] in assignment["class_ids"]
    assert assignment["standards_profile_id"] == profile["profile_id"]
    assert matching_students
    assert all(
        isinstance(student.get("student_display_name"), str)
        and student["student_display_name"].strip()
        for student in matching_students
    )
    assert all(
        student["class_id"] == submission["class_id"] for student in matching_students
    )

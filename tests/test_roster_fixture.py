"""Tests for the canonical synthetic roster example."""

from pathlib import Path

from pds_core.rosters import (
    load_roster,
    student_display_name,
    student_sort_name,
)

ROSTER_PATH = (
    Path(__file__).parent.parent
    / "examples"
    / "rosters"
    / "english12_p3_synthetic.csv"
)
REQUIRED_COLUMNS = (
    "class_id",
    "student_id",
    "last_name",
    "first_name",
    "period",
)


def test_synthetic_roster_fixture_loads_with_pds_core() -> None:
    roster = load_roster(ROSTER_PATH)

    assert roster.class_id == "english12_p3"
    assert len(roster.students) == 3
    assert roster.columns == REQUIRED_COLUMNS
    for student in roster.students:
        assert student.class_id == roster.class_id
        assert all(
            isinstance(getattr(student, field), str) and getattr(student, field)
            for field in REQUIRED_COLUMNS
        )


def test_synthetic_roster_preserves_student_ids_as_strings() -> None:
    roster = load_roster(ROSTER_PATH)

    assert [student.student_id for student in roster.students] == [
        "01001",
        "01002",
        "01003",
    ]
    assert all(isinstance(student.student_id, str) for student in roster.students)


def test_synthetic_roster_uses_shared_student_display_helper() -> None:
    roster = load_roster(ROSTER_PATH)

    assert student_display_name(roster.students[0]) == "Jane Doe"


def test_synthetic_roster_uses_shared_student_sort_helper() -> None:
    roster = load_roster(ROSTER_PATH)

    assert student_sort_name(roster.students[0]) == "Doe, Jane"

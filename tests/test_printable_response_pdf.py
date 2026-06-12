"""Tests for printable Quillan writing-response PDFs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pds_core.routes import assignment_templates_dir
from pypdf import PdfReader

from quillan.printable_response import (
    PRINTABLE_RESPONSE_FILENAME,
    build_response_page_context,
    generate_printable_response_pdf,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "paper_workflow"


def _load_assignment() -> dict[str, Any]:
    assignment = json.loads(
        (FIXTURE_DIR / "assignment.json").read_text(encoding="utf-8")
    )
    assert isinstance(assignment, dict)
    return cast(dict[str, Any], assignment)


def _load_students() -> list[dict[str, str]]:
    students = json.loads((FIXTURE_DIR / "students.json").read_text(encoding="utf-8"))
    assert isinstance(students, list)
    assert all(isinstance(student, dict) for student in students)
    return cast(list[dict[str, str]], students)


def test_build_response_page_context_uses_fixture_identity() -> None:
    assignment = _load_assignment()
    student = _load_students()[0]

    context = build_response_page_context(
        class_id=student["class_id"],
        assignment_id=cast(str, assignment["assignment_id"]),
        assignment_title=cast(str, assignment["title"]),
        student_id=student["student_id"],
        student_display_name=student["student_display_name"],
        page_number=2,
    )

    assert context.class_id == "english12_p4_synthetic"
    assert context.class_label == "english12_p4_synthetic"
    assert context.assignment_id == "literary_argument_synthetic"
    assert context.assignment_title == "Literary Argument Response"
    assert context.student_id == "stu_0001"
    assert context.student_display_name == student["student_display_name"]
    assert context.page_number == 2
    assert context.payload == (
        "PDS1|module=quillan|class=english12_p4_synthetic|"
        "aid=literary_argument_synthetic|sid=stu_0001|page=2|doc=response"
    )
    assert context.student_display_name not in context.payload


def test_generate_printable_response_pdf_uses_templates_route(
    tmp_path: Path,
) -> None:
    assignment = _load_assignment()
    students = _load_students()
    class_id = students[0]["class_id"]
    assignment_id = cast(str, assignment["assignment_id"])

    output_path = generate_printable_response_pdf(
        tmp_path,
        class_id=class_id,
        assignment_id=assignment_id,
        assignment_title=cast(str, assignment["title"]),
        students=students,
    )

    assert output_path == (
        assignment_templates_dir(tmp_path, class_id, assignment_id)
        / PRINTABLE_RESPONSE_FILENAME
    )
    assert output_path.is_file()
    assert output_path.stat().st_size > 1_000
    assert output_path.read_bytes().startswith(b"%PDF")


def test_generate_printable_response_pdf_supports_multiple_students_and_pages(
    tmp_path: Path,
) -> None:
    assignment = _load_assignment()
    students = _load_students()
    students.append(
        {
            "student_id": "stu_0002",
            "student_display_name": "Jordan Example",
            "class_id": students[0]["class_id"],
        }
    )

    output_path = generate_printable_response_pdf(
        tmp_path,
        class_id=students[0]["class_id"],
        assignment_id=cast(str, assignment["assignment_id"]),
        assignment_title=cast(str, assignment["title"]),
        students=students,
        pages_per_student=2,
    )

    reader = PdfReader(str(output_path))
    assert len(reader.pages) == 4


@pytest.mark.parametrize("pages_per_student", [0, -1, True, 1.5, "1"])
def test_generate_printable_response_pdf_rejects_invalid_page_counts(
    tmp_path: Path,
    pages_per_student: object,
) -> None:
    assignment = _load_assignment()
    students = _load_students()

    with pytest.raises(
        ValueError, match="pages_per_student must be a positive integer"
    ):
        generate_printable_response_pdf(
            tmp_path,
            class_id=students[0]["class_id"],
            assignment_id=cast(str, assignment["assignment_id"]),
            assignment_title=cast(str, assignment["title"]),
            students=students,
            pages_per_student=pages_per_student,  # type: ignore[arg-type]
        )


def test_generate_printable_response_pdf_rejects_empty_students(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="at least one student"):
        generate_printable_response_pdf(
            tmp_path,
            class_id="english12_p4_synthetic",
            assignment_id="literary_argument_synthetic",
            students=[],
        )

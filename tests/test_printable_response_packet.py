"""Tests for shared printable response packet application services."""

from __future__ import annotations

import json
from pathlib import Path

from pds_core.classes import write_class_roster
from pds_core.rosters import RosterError, create_roster
from pypdf import PdfReader
import pytest

from quillan.printable_response_packet import (
    generate_printable_response_packet,
    plan_printable_response_packet,
)

CLASS_ID = "synthetic_english_p3"
ASSIGNMENT_ID = "synthetic_response"


def write_packet_workspace(root: Path) -> tuple[Path, Path]:
    roster_path = write_class_roster(
        root,
        create_roster(
            CLASS_ID,
            [
                {
                    "student_id": "00107",
                    "last_name": "Zulu",
                    "first_name": "Avery",
                    "period": "3",
                },
                {
                    "student_id": "00002",
                    "last_name": "Alpha",
                    "first_name": "Morgan",
                    "period": "3",
                },
            ],
        ),
    )
    assignment_path = (
        root / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    )
    assignment_path.parent.mkdir(parents=True, exist_ok=True)
    assignment_path.write_text(json.dumps(valid_assignment()), encoding="utf-8")
    return assignment_path, roster_path


def valid_assignment() -> dict[str, object]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Writing Response",
        "class_ids": [CLASS_ID],
        "writing_type": "synthetic_response",
        "student_prompt": "Private synthetic directions must not be printed.",
        "standards_profile_id": "missing_but_not_needed_for_printing",
        "focus_standard_ids": ["synthetic:W.SYN.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "synthetic_scale",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Synthetic."},
                {"value": 2, "label": "Meeting", "description": "Synthetic."},
            ],
        },
        "basic_requirements": {},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
        "created_at": "2026-07-13T00:00:00+00:00",
        "updated_at": "2026-07-13T00:00:00+00:00",
        "module_details": {},
    }


def test_plan_validates_without_writing_and_reports_canonical_paths(
    tmp_path: Path,
) -> None:
    assignment_path, roster_path = write_packet_workspace(tmp_path)
    plan = plan_printable_response_packet(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, pages_per_student=3
    )

    assert plan.student_count == 2
    assert plan.pages_per_student == 3
    assert plan.total_page_count == 6
    assert plan.assignment_path == assignment_path
    assert plan.roster_path == roster_path
    assert plan.assignment_relative_path.endswith("/assignment.json")
    assert plan.roster_relative_path.endswith("/roster.csv")
    assert plan.output_relative_path == (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/templates/"
        "printable_response_pages.pdf"
    )
    assert not plan.target_exists
    assert not plan.output_path.parent.exists()


def test_generate_reuses_renderer_and_rejects_unexpected_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    unexpected = tmp_path / "unexpected.pdf"
    monkeypatch.setattr(
        "quillan.printable_response_packet.generate_printable_responses_for_roster",
        lambda *_args, **_kwargs: unexpected,
    )

    with pytest.raises(ValueError, match="unexpected output path"):
        generate_printable_response_packet(plan)


def test_generation_counts_pages_and_preserves_inputs(tmp_path: Path) -> None:
    assignment_path, roster_path = write_packet_workspace(tmp_path)
    untouched_paths = [
        tmp_path / "classes" / CLASS_ID / "class.json",
        tmp_path / "classes" / CLASS_ID / "modules" / "quillan" / "work" / "sibling" / "assignment.json",
        assignment_path.parent / "submissions" / "synthetic_student" / "submission.json",
        assignment_path.parent / "submissions" / "synthetic_student" / "review.json",
        assignment_path.parent / "scans" / "synthetic_evidence.txt",
        assignment_path.parent / "exports" / "synthetic_report.csv",
        tmp_path / "shared" / "focus_standard_comments" / "synthetic.json",
        tmp_path / "scans" / "review" / "synthetic.json",
    ]
    for index, path in enumerate(untouched_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic sentinel {index}".encode())
    untouched_bytes = {path: path.read_bytes() for path in untouched_paths}
    assignment_bytes = assignment_path.read_bytes()
    roster_bytes = roster_path.read_bytes()
    plan = plan_printable_response_packet(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, pages_per_student=2
    )

    result = generate_printable_response_packet(plan)

    assert result.total_page_count == 4
    assert result.output_path.read_bytes().startswith(b"%PDF")
    reader = PdfReader(str(result.output_path))
    assert len(reader.pages) == 4
    first_student_text = reader.pages[0].extract_text()
    second_student_text = reader.pages[2].extract_text()
    assert "Avery Zulu" in first_student_text
    assert "Student ID: 00107" in first_student_text
    assert "Morgan Alpha" in second_student_text
    assert "Student ID: 00002" in second_student_text
    assert "Synthetic Writing Response" in first_student_text
    assert f"Assignment ID: {ASSIGNMENT_ID}" in first_student_text
    assert all(
        "Private synthetic directions" not in page.extract_text()
        for page in reader.pages
    )
    assert assignment_path.read_bytes() == assignment_bytes
    assert roster_path.read_bytes() == roster_bytes
    assert {path: path.read_bytes() for path in untouched_paths} == untouched_bytes


def test_existing_packet_requires_explicit_overwrite(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    plan.output_path.parent.mkdir(parents=True)
    plan.output_path.write_bytes(b"existing synthetic packet")
    original_stat = plan.output_path.stat()

    with pytest.raises(FileExistsError, match="--overwrite --yes"):
        generate_printable_response_packet(plan)

    assert plan.output_path.read_bytes() == b"existing synthetic packet"
    assert plan.output_path.stat().st_mtime_ns == original_stat.st_mtime_ns
    replaced = generate_printable_response_packet(plan, overwrite=True)
    assert replaced.replaced_existing
    assert plan.output_path.read_bytes().startswith(b"%PDF")


def test_empty_roster_fails_before_templates_directory(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    roster_path = tmp_path / "classes" / CLASS_ID / "roster.csv"
    roster_path.write_text(
        "class_id,student_id,last_name,first_name,period\n", encoding="utf-8"
    )

    with pytest.raises(RosterError, match="at least one student"):
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert not (
        tmp_path / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "templates"
    ).exists()


@pytest.mark.parametrize("value", [0, -1, True])
def test_plan_rejects_invalid_page_counts(tmp_path: Path, value: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        plan_printable_response_packet(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, pages_per_student=value
        )

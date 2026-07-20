"""End-to-end smoke test for roster-aware printable response generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from quillan.storage import assignment_templates_dir
from pypdf import PdfReader

import quillan.printable_response as printable_response


def test_roster_to_printable_response_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    input_dir = workspace_root / "inputs"
    input_dir.mkdir(parents=True)

    class_id = "english12_p4_smoke"
    assignment_id = "literary_argument_smoke"
    assignment_path = input_dir / "assignment.json"
    assignment_path.write_text(
        json.dumps(
            {
                "schema_version": "2",
                "module": "quillan",
                "record_type": "assignment",
                "assignment_id": assignment_id,
                "title": "Synthetic Literary Argument",
                "class_ids": [class_id],
                "writing_type": "literary argument essay",
                "student_prompt": "Write a literary argument using evidence.",
                "standards_profile_id": "english_12_smoke",
                "focus_standard_ids": ["W.AW.11-12.1"],
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
                "basic_requirements": {
                    "paragraphs_min": 3,
                    "word_count_min": 300,
                    "required_elements": ["claim", "evidence", "reasoning"],
                },
                "minimum_requirement_policy": {
                    "allow_return_without_full_review": True,
                },
                "created_at": "2026-07-13T00:00:00+00:00",
                "updated_at": "2026-07-13T00:00:00+00:00",
                "module_details": {},
            }
        ),
        encoding="utf-8",
    )

    roster_path = input_dir / "roster.csv"
    roster_path.write_text(
        "\n".join(
            [
                "class_id,student_id,last_name,first_name,period",
                f"{class_id},01001,Doe,Jane,4",
                f"{class_id},01002,Smith,Marcus,4",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payloads: list[str] = []
    make_qr_image = printable_response._make_qr_image

    def record_payload(payload: str) -> object:
        payloads.append(payload)
        return make_qr_image(payload)

    monkeypatch.setattr(printable_response, "_make_qr_image", record_payload)

    output_path = printable_response.generate_printable_responses_for_roster(
        workspace_root,
        assignment_path=assignment_path,
        roster_path=roster_path,
        pages_per_student=2,
        class_label="English 12 - Period 4",
    )

    expected_output_path = (
        assignment_templates_dir(workspace_root, class_id, assignment_id)
        / printable_response.PRINTABLE_RESPONSE_FILENAME
    )
    assert output_path == expected_output_path
    assert output_path.is_file()
    assert output_path.read_bytes().startswith(b"%PDF")
    assert output_path.stat().st_size > 0

    reader = PdfReader(str(output_path))
    assert len(reader.pages) == 4

    leading_zero_context = printable_response.build_response_page_context(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id="01001",
        student_display_name="Jane Doe",
        page_number=1,
        assignment_title="Synthetic Literary Argument",
        class_label="English 12 - Period 4",
    )

    assert leading_zero_context.student_id == "01001"
    assert leading_zero_context.student_display_name == "Jane Doe"
    assert leading_zero_context.page_number == 1
    assert leading_zero_context.payload == (
        "PDS1|module=quillan|class=english12_p4_smoke|"
        "aid=literary_argument_smoke|sid=01001|page=1|doc=response"
    )

    assert payloads == [
        (
            "PDS1|module=quillan|class=english12_p4_smoke|"
            "aid=literary_argument_smoke|sid=01001|page=1|doc=response"
        ),
        (
            "PDS1|module=quillan|class=english12_p4_smoke|"
            "aid=literary_argument_smoke|sid=01001|page=2|doc=response"
        ),
        (
            "PDS1|module=quillan|class=english12_p4_smoke|"
            "aid=literary_argument_smoke|sid=01002|page=1|doc=response"
        ),
        (
            "PDS1|module=quillan|class=english12_p4_smoke|"
            "aid=literary_argument_smoke|sid=01002|page=2|doc=response"
        ),
    ]
    assert all("Jane" not in payload for payload in payloads)
    assert all("Marcus" not in payload for payload in payloads)

"""End-to-end smoke test for roster-aware managed PDS2 packet generation."""

from pathlib import Path

from pypdf import PdfReader

from quillan.printable_response_packet import (
    generate_printable_response_packet,
    plan_printable_response_packet,
)
from tests.test_printable_response_packet import (
    ASSIGNMENT_ID,
    CLASS_ID,
    write_packet_workspace,
)


def test_roster_to_printable_response_workflow(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    result = generate_printable_response_packet(
        plan_printable_response_packet(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, pages_per_student=2
        )
    )
    assert result.success and result.installed
    assert len(result.issuance_ids) == 2
    assert len(result.page_ids) == len(result.route_ids) == 4
    reader = PdfReader(str(result.output_path))
    assert len(reader.pages) == 4
    first_text = reader.pages[0].extract_text()
    assert "Student ID: 00107" in first_text
    assert result.page_ids[0] in first_text
    assert result.route_ids[0] in first_text

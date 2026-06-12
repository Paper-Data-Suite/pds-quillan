"""Tests for Quillan PDS1 response payloads."""

from __future__ import annotations

import pytest
from pds_core.pds1 import PDS1_SCHEMA, parse_pds1_payload
from pds_core.qr_payload import QrPayloadValidationError

from quillan.payloads import build_response_payload


def test_build_response_payload() -> None:
    payload = build_response_payload(
        class_id="english12_p4",
        assignment_id="personal_narrative",
        student_id="1001",
        page=1,
    )

    assert payload == (
        "PDS1|module=quillan|class=english12_p4|aid=personal_narrative|"
        "sid=1001|page=1|doc=response"
    )


@pytest.mark.parametrize("page", [0, -1, True, 1.5, "1"])
def test_build_response_payload_rejects_invalid_pages(page: object) -> None:
    with pytest.raises(ValueError, match="page must be a positive integer"):
        build_response_payload(
            class_id="english12_p4",
            assignment_id="personal_narrative",
            student_id="1001",
            page=page,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("class_id", "english 12"),
        ("assignment_id", "personal/narrative"),
        ("student_id", ""),
    ],
)
def test_build_response_payload_delegates_identifier_validation(
    field_name: str,
    field_value: str,
) -> None:
    identifiers = {
        "class_id": "english12_p4",
        "assignment_id": "personal_narrative",
        "student_id": "1001",
    }
    identifiers[field_name] = field_value

    with pytest.raises(QrPayloadValidationError, match=field_name):
        build_response_payload(**identifiers, page=1)


def test_response_payload_round_trip() -> None:
    payload_text = build_response_payload(
        class_id="english12_p4",
        assignment_id="personal_narrative",
        student_id="1001",
        page=2,
    )

    parsed = parse_pds1_payload(payload_text)

    assert parsed.schema == PDS1_SCHEMA
    assert parsed.module == "quillan"
    assert parsed.class_id == "english12_p4"
    assert parsed.assignment_id == "personal_narrative"
    assert parsed.student_id == "1001"
    assert parsed.page == 2
    assert parsed.metadata == {"doc": "response"}

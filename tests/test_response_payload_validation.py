"""Tests for decoded Quillan response-payload validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.payload_validation import (
    ResponsePayloadValidationFailure,
    decoded_payload_to_response_page,
)
from quillan.payloads import build_response_payload
from quillan.route_planning import DecodedResponsePage


def test_valid_quillan_response_payload_converts_to_decoded_response_page() -> None:
    payload = build_response_payload(
        class_id="english12_p4",
        assignment_id="personal_narrative",
        student_id="stu_0001",
        page=2,
    )

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, DecodedResponsePage)
    assert result.module == "quillan"
    assert result.document_type == "response"
    assert result.class_id == "english12_p4"
    assert result.assignment_id == "personal_narrative"
    assert result.student_id == "stu_0001"
    assert result.page_number == 2
    assert result.raw_payload == payload


def test_none_payload_gives_payload_missing() -> None:
    result = decoded_payload_to_response_page(None)

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "payload_missing"
    assert result.raw_payload is None


def test_empty_payload_gives_payload_missing() -> None:
    result = decoded_payload_to_response_page("")

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "payload_missing"


def test_whitespace_only_payload_gives_payload_missing() -> None:
    result = decoded_payload_to_response_page("  \n\t  ")

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "payload_missing"


def test_non_pds1_text_gives_payload_schema_unsupported() -> None:
    payload = "not a pds payload"

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "payload_schema_unsupported"
    assert result.raw_payload == payload


def test_legacy_schema_gives_payload_schema_unsupported() -> None:
    payload = "OMR1|class=english12|aid=essay|sid=stu_0001|page=1"

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "payload_schema_unsupported"


def test_malformed_pds1_gives_payload_invalid() -> None:
    payload = "PDS1|module=quillan"

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "payload_invalid"
    assert result.failure_message
    assert result.raw_payload == payload


def test_wrong_module_gives_module_unsupported_with_identity_fields() -> None:
    payload = "PDS1|module=scoreform|class=english12|aid=essay|sid=stu_0001|page=1"

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "module_unsupported"
    assert result.module == "scoreform"
    assert result.class_id == "english12"
    assert result.assignment_id == "essay"
    assert result.student_id == "stu_0001"
    assert result.page_number == 1
    assert result.module_details["expected_module"] == "quillan"


def test_missing_doc_metadata_gives_payload_invalid() -> None:
    payload = "PDS1|module=quillan|class=english12|aid=essay|sid=stu_0001|page=1"

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "payload_invalid"
    assert result.module == "quillan"
    assert result.document_type is None
    assert result.module_details["reason"] == "document_type_missing"


def test_wrong_doc_metadata_gives_payload_invalid() -> None:
    payload = (
        "PDS1|module=quillan|class=english12|aid=essay|sid=stu_0001|"
        "page=1|doc=cover"
    )

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "payload_invalid"
    assert result.document_type == "cover"
    assert result.module_details["reason"] == "document_type_invalid"


def test_invalid_page_fails_cleanly() -> None:
    payload = (
        "PDS1|module=quillan|class=english12|aid=essay|sid=stu_0001|"
        "page=nope|doc=response"
    )

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category == "payload_invalid"
    assert result.failure_message


def test_invalid_identifier_fails_cleanly() -> None:
    payload = (
        "PDS1|module=quillan|class=english 12|aid=essay|sid=stu_0001|"
        "page=1|doc=response"
    )

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, ResponsePayloadValidationFailure)
    assert result.failure_category in {"identifier_invalid", "payload_invalid"}
    assert result.failure_message


def test_validation_does_not_route_or_mutate_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.rglob("*"))
    payload = build_response_payload(
        class_id="english12_p4",
        assignment_id="personal_narrative",
        student_id="stu_0001",
        page=1,
    )

    result = decoded_payload_to_response_page(payload)

    assert isinstance(result, DecodedResponsePage)
    assert set(tmp_path.rglob("*")) == before

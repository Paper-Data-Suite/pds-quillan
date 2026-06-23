"""Validate decoded QR payload text as Quillan response-page identity data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pds_core.identifiers import IdentifierValidationError
from pds_core.pds1 import Pds1PayloadError, parse_pds1_payload
from pds_core.qr_payload import QrPayloadValidationError
from pds_core.scan_failure_metadata import is_routing_failure_category

from quillan.route_planning import DecodedResponsePage


@dataclass(frozen=True, slots=True)
class ResponsePayloadValidationFailure:
    """Structured failure from decoded response-page payload validation."""

    failure_category: str
    failure_message: str
    raw_payload: str | None
    module: str | None = None
    document_type: str | None = None
    class_id: str | None = None
    assignment_id: str | None = None
    student_id: str | None = None
    page_number: int | None = None
    module_details: dict[str, object] = field(default_factory=dict)


def decoded_payload_to_response_page(
    payload_text: str | None,
) -> DecodedResponsePage | ResponsePayloadValidationFailure:
    """Validate decoded QR text as a Quillan response-page payload."""
    if payload_text is None or payload_text.strip() == "":
        return _failure(
            "payload_missing",
            "Decoded QR payload text is missing.",
            raw_payload=payload_text,
        )

    if not payload_text.startswith("PDS1"):
        return _failure(
            "payload_schema_unsupported",
            "Decoded QR payload is not a PDS1 payload.",
            raw_payload=payload_text,
            reason="payload_schema_unsupported",
            expected_schema="PDS1",
        )

    try:
        payload = parse_pds1_payload(payload_text)
    except Pds1PayloadError as error:
        return _failure(
            _parse_failure_category(error),
            f"Decoded QR payload is not valid PDS1: {error}",
            raw_payload=payload_text,
            reason="payload_parse_failed",
            parse_error=str(error),
        )

    document_type = payload.metadata.get("doc")
    page_number = payload.page

    if payload.module != "quillan":
        return _failure(
            "module_unsupported",
            "Decoded PDS1 payload is not for the Quillan module.",
            raw_payload=payload_text,
            module=payload.module,
            document_type=document_type,
            class_id=payload.class_id,
            assignment_id=payload.assignment_id,
            student_id=payload.student_id,
            page_number=page_number,
            reason="module_unsupported",
            expected_module="quillan",
            actual_module=payload.module,
        )

    if document_type is None:
        return _failure(
            "payload_invalid",
            "Decoded Quillan payload is missing doc=response metadata.",
            raw_payload=payload_text,
            module=payload.module,
            document_type=document_type,
            class_id=payload.class_id,
            assignment_id=payload.assignment_id,
            student_id=payload.student_id,
            page_number=page_number,
            reason="document_type_missing",
            field="doc",
            expected_document_type="response",
        )

    if document_type != "response":
        return _failure(
            "payload_invalid",
            "Decoded Quillan payload is not a response page.",
            raw_payload=payload_text,
            module=payload.module,
            document_type=document_type,
            class_id=payload.class_id,
            assignment_id=payload.assignment_id,
            student_id=payload.student_id,
            page_number=page_number,
            reason="document_type_invalid",
            field="doc",
            expected_document_type="response",
            actual_document_type=document_type,
        )

    if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
        return _failure(
            "payload_invalid",
            "Decoded Quillan response page has an invalid page number.",
            raw_payload=payload_text,
            module=payload.module,
            document_type=document_type,
            class_id=payload.class_id,
            assignment_id=payload.assignment_id,
            student_id=payload.student_id,
            page_number=page_number,
            reason="page_number_invalid",
            field="page",
        )

    return DecodedResponsePage(
        module="quillan",
        document_type="response",
        class_id=payload.class_id,
        assignment_id=payload.assignment_id,
        student_id=payload.student_id,
        page_number=page_number,
        raw_payload=payload_text,
    )


def _parse_failure_category(error: Pds1PayloadError) -> str:
    cause = error.__cause__
    if isinstance(cause, QrPayloadValidationError) and isinstance(
        cause.__cause__,
        IdentifierValidationError,
    ):
        return "identifier_invalid"
    return "payload_invalid"


def _failure(
    category: str,
    message: str,
    *,
    raw_payload: str | None,
    module: str | None = None,
    document_type: str | None = None,
    class_id: str | None = None,
    assignment_id: str | None = None,
    student_id: str | None = None,
    page_number: int | None = None,
    **module_details: object,
) -> ResponsePayloadValidationFailure:
    if not is_routing_failure_category(category):
        raise ValueError(f"Unsupported routing failure category: {category}")
    return ResponsePayloadValidationFailure(
        failure_category=category,
        failure_message=message,
        raw_payload=raw_payload,
        module=module,
        document_type=document_type,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        page_number=page_number,
        module_details=dict(module_details),
    )

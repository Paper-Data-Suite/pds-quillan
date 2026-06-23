"""Decode-only scan diagnostic command handler."""

from __future__ import annotations

import argparse
from pathlib import Path

from quillan.payload_validation import (
    ResponsePayloadValidationFailure,
    decoded_payload_to_response_page,
)
from quillan.qr_decode import decode_qr_payload_from_image_path
from quillan.route_planning import DecodedResponsePage


def handle_decode_scan(args: argparse.Namespace) -> int:
    """Decode and validate one scan image without routing or writing data."""
    source_file: Path = args.source_file
    hide_payload: bool = args.hide_payload

    print("Quillan scan decode diagnostic")
    print()
    print(f"Source: {source_file}")

    try:
        decode_result = decode_qr_payload_from_image_path(source_file)
    except Exception as error:
        print("QR decode: failed")
        print("Category: processing_error")
        print(f"Reason: Unexpected QR image decoding failure: {error}")
        return 1

    if decode_result.payload_text is None:
        print("QR decode: failed")
        print(f"Category: {decode_result.failure_category}")
        print(f"Reason: {decode_result.failure_message}")
        return 2

    print("QR decode: success")
    print(f"Decode attempt: {decode_result.successful_attempt}")
    _print_payload(decode_result.payload_text, hide_payload=hide_payload)
    print()

    try:
        validation_result = decoded_payload_to_response_page(
            decode_result.payload_text
        )
    except Exception as error:
        print("Payload validation: failed")
        print("Category: payload_invalid")
        print(f"Reason: Unexpected payload validation failure: {error}")
        return 1

    if isinstance(validation_result, ResponsePayloadValidationFailure):
        _print_validation_failure(validation_result)
        return 3

    _print_response_page(validation_result)
    return 0


def _print_payload(payload_text: str, *, hide_payload: bool) -> None:
    if hide_payload:
        print("Payload: hidden")
        return
    print(f"Payload: {payload_text}")


def _print_response_page(page: DecodedResponsePage) -> None:
    print("Payload validation: success")
    print(f"Module: {page.module}")
    print(f"Document type: {page.document_type}")
    print(f"Class ID: {page.class_id}")
    print(f"Assignment ID: {page.assignment_id}")
    print(f"Student ID: {page.student_id}")
    print(f"Page number: {page.page_number}")


def _print_validation_failure(
    failure: ResponsePayloadValidationFailure,
) -> None:
    print("Payload validation: failed")
    print(f"Category: {failure.failure_category}")
    print(f"Reason: {failure.failure_message}")
    _print_optional_field("Module", failure.module)
    _print_optional_field("Document type", failure.document_type)
    _print_optional_field("Class ID", failure.class_id)
    _print_optional_field("Assignment ID", failure.assignment_id)
    _print_optional_field("Student ID", failure.student_id)
    _print_optional_field("Page number", failure.page_number)


def _print_optional_field(label: str, value: object | None) -> None:
    if value is not None:
        print(f"{label}: {value}")

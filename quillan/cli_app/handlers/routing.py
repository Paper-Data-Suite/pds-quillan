"""Scan-routing command handler."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from pds_core.pds1 import Pds1PayloadError, parse_pds1_payload
from pds_core.workspace import WorkspaceRootError, resolve_workspace_root

from quillan.cli_app.output import (
    print_evidence_filing_review,
    print_route_failure_review,
    print_routed_evidence,
)
from quillan.evidence_filing import (
    EvidenceFilingError,
    file_routed_response_evidence,
)
from quillan.payload_validation import (
    ResponsePayloadValidationFailure,
    decoded_payload_to_response_page,
)
from quillan.qr_decode import (
    QrImageDecodeResult,
    decode_qr_payload_from_image_path,
)
from quillan.route_planning import (
    DecodedResponsePage,
    RouteFailure,
    plan_decoded_response_page_route,
)
from quillan.routing_review import (
    RoutingReviewRecord,
    RoutingReviewError,
    preserve_evidence_filing_error_for_review,
    preserve_route_failure_for_review,
    preserve_routing_failure_for_review,
)


def handle_route_scan(args: argparse.Namespace) -> int:
    """Route one source scan from caller-supplied payload text or image QR."""
    source_file: Path = args.source_file
    intake_timestamp = datetime.now(timezone.utc)
    try:
        workspace_root = resolve_workspace_root()
    except WorkspaceRootError as error:
        print(f"Error: could not resolve the PDS workspace: {error}")
        return 1
    except Exception as error:
        print(f"Error: unexpected workspace resolution failure: {error}")
        return 1

    if args.decode_qr:
        decoded_result = _decoded_page_from_source_qr(
            workspace_root,
            source_file=source_file,
            created_at=intake_timestamp,
        )
    else:
        if not _validate_source_file(source_file):
            return 1
        decoded_result = _decoded_page_from_payload_text(
            workspace_root,
            source_file=source_file,
            payload_text=args.payload,
            created_at=intake_timestamp,
        )

    if isinstance(decoded_result, int):
        return decoded_result
    return _route_decoded_page(
        workspace_root,
        source_file=source_file,
        decoded_page=decoded_result,
        created_at=intake_timestamp,
    )


def _decoded_page_from_payload_text(
    workspace_root: Path,
    *,
    source_file: Path,
    payload_text: str,
    created_at: datetime,
) -> DecodedResponsePage | int:
    """Convert caller-supplied PDS1 text into a decoded response page."""
    try:
        payload = parse_pds1_payload(payload_text)
    except Pds1PayloadError as error:
        return _preserve_payload_parse_failure(
            workspace_root,
            source_file=source_file,
            payload_text=payload_text,
            error=error,
            created_at=created_at,
        )
    except Exception as error:
        print(f"Error: unexpected PDS1 payload parsing failure: {error}")
        return 1

    decoded_page = DecodedResponsePage(
        module=payload.module,
        document_type=payload.metadata.get("doc"),
        class_id=payload.class_id,
        assignment_id=payload.assignment_id,
        student_id=payload.student_id,
        page_number=payload.page,
        raw_payload=payload_text,
    )
    return decoded_page


def _decoded_page_from_source_qr(
    workspace_root: Path,
    *,
    source_file: Path,
    created_at: datetime,
) -> DecodedResponsePage | int:
    """Decode and validate a Quillan response-page QR from one image."""
    try:
        decode_result = decode_qr_payload_from_image_path(source_file)
    except Exception as error:
        decode_result = QrImageDecodeResult(
            payload_text=None,
            failure_category="processing_error",
            failure_message=f"Unexpected QR decode failure: {error}",
        )

    if decode_result.payload_text is None:
        return _preserve_decode_failure(
            workspace_root,
            source_file=source_file,
            decode_result=decode_result,
            created_at=created_at,
        )

    validation_result = decoded_payload_to_response_page(
        decode_result.payload_text
    )
    if isinstance(validation_result, ResponsePayloadValidationFailure):
        return _preserve_payload_validation_failure(
            workspace_root,
            source_file=source_file,
            failure=validation_result,
            created_at=created_at,
        )

    return validation_result


def _route_decoded_page(
    workspace_root: Path,
    *,
    source_file: Path,
    decoded_page: DecodedResponsePage,
    created_at: datetime,
) -> int:
    """Plan and file one already-decoded Quillan response page."""
    try:
        route_result = plan_decoded_response_page_route(
            workspace_root,
            decoded_page,
        )
        if isinstance(route_result, RouteFailure):
            review_record = preserve_route_failure_for_review(
                workspace_root,
                route_failure=route_result,
                source_filename=source_file.name,
                created_at=created_at,
            )
            print_route_failure_review(route_result, review_record)
            return 0

        try:
            filed_evidence = file_routed_response_evidence(
                workspace_root,
                route_plan=route_result,
                source_file_path=source_file,
                intake_timestamp=created_at,
            )
        except EvidenceFilingError as error:
            review_record = preserve_evidence_filing_error_for_review(
                workspace_root,
                error=error,
                route_plan=route_result,
                source_filename=source_file.name,
                created_at=created_at,
            )
            print_evidence_filing_review(error, review_record)
            return 0
    except RoutingReviewError as error:
        print(f"Error: could not preserve scan routing failure for review: {error}")
        return 1
    except Exception as error:
        print(f"Error: unexpected route-scan failure: {error}")
        return 1

    print_routed_evidence(filed_evidence)
    return 0


def _validate_source_file(source_file: Path) -> bool:
    """Return whether the selected scan is an existing readable file."""
    try:
        if not source_file.is_file():
            print(
                "Error: source file must be an existing regular file: "
                f"{source_file}"
            )
            return False
        with source_file.open("rb"):
            pass
    except OSError as error:
        print(f"Error: source file is not readable: {error}")
        return False
    return True


def _preserve_payload_parse_failure(
    workspace_root: Path,
    *,
    source_file: Path,
    payload_text: str,
    error: Pds1PayloadError,
    created_at: datetime,
) -> int:
    """Preserve malformed payload context without inventing route identity."""
    try:
        review_record = preserve_routing_failure_for_review(
            workspace_root,
            failure_category="payload_invalid",
            failure_message=str(error),
            source_filename=source_file.name,
            module="quillan",
            detected_payload=payload_text,
            module_details={
                "failure_origin": "payload_parse",
                "parse_error": str(error),
            },
            created_at=created_at,
        )
    except RoutingReviewError as review_error:
        print(
            "Error: payload was invalid and could not be preserved for review: "
            f"{review_error}"
        )
        return 1
    except Exception as unexpected_error:
        print(
            "Error: unexpected failure while preserving invalid payload: "
            f"{unexpected_error}"
        )
        return 1

    print("Quillan response page was not routed; preserved for review.")
    print(f"Reason: {error}")
    print("Category: payload_invalid")
    print(f"Review record: {review_record.failure_metadata_relative_path}")
    return 0


def _preserve_decode_failure(
    workspace_root: Path,
    *,
    source_file: Path,
    decode_result: QrImageDecodeResult,
    created_at: datetime,
) -> int:
    """Preserve source/QR decode failure context for teacher review."""
    category = decode_result.failure_category or "processing_error"
    message = decode_result.failure_message or "QR decoding failed."
    try:
        review_record = preserve_routing_failure_for_review(
            workspace_root,
            failure_category=category,
            failure_message=message,
            source_filename=source_file.name,
            module=None,
            detected_payload=None,
            module_details={
                "failure_origin": "qr_decode",
                "decode_attempt": decode_result.successful_attempt,
            },
            created_at=created_at,
        )
    except RoutingReviewError as review_error:
        print(
            "Error: QR decode failure could not be preserved for review: "
            f"{review_error}"
        )
        return 1
    except Exception as unexpected_error:
        print(
            "Error: unexpected failure while preserving QR decode failure: "
            f"{unexpected_error}"
        )
        return 1

    _print_preserved_intake_failure(
        reason=message,
        category=category,
        review_record=review_record,
    )
    return 0


def _preserve_payload_validation_failure(
    workspace_root: Path,
    *,
    source_file: Path,
    failure: ResponsePayloadValidationFailure,
    created_at: datetime,
) -> int:
    """Preserve decoded-payload validation failure context for review."""
    module_details: dict[str, object] = {
        "failure_origin": "payload_validation",
    }
    module_details.update(failure.module_details)
    try:
        review_record = preserve_routing_failure_for_review(
            workspace_root,
            failure_category=failure.failure_category,
            failure_message=failure.failure_message,
            source_filename=source_file.name,
            module=failure.module,
            detected_payload=failure.raw_payload,
            payload_page_number=failure.page_number,
            class_id=failure.class_id,
            assignment_id=failure.assignment_id,
            student_id=failure.student_id,
            module_details=module_details,
            created_at=created_at,
        )
    except RoutingReviewError as review_error:
        print(
            "Error: decoded payload failure could not be preserved for review: "
            f"{review_error}"
        )
        return 1
    except Exception as unexpected_error:
        print(
            "Error: unexpected failure while preserving decoded payload failure: "
            f"{unexpected_error}"
        )
        return 1

    _print_preserved_intake_failure(
        reason=failure.failure_message,
        category=failure.failure_category,
        review_record=review_record,
    )
    return 0


def _print_preserved_intake_failure(
    *,
    reason: str,
    category: str,
    review_record: RoutingReviewRecord,
) -> None:
    print("Quillan response page was not routed; preserved for review.")
    print(f"Reason: {reason}")
    print(f"Category: {category}")
    print(f"Review record: {review_record.failure_metadata_relative_path}")

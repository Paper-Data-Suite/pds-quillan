"""Scan-routing command handler."""

from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import cv2
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
from quillan.pdf_pages import (
    PdfPageConversionError,
    PdfPageConversionFailure,
    PdfPageImage,
    iter_pdf_page_images,
)
from quillan.qr_decode import (
    ImageArray,
    QrImageDecodeResult,
    decode_qr_payload_from_image,
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
    preserve_decode_failure_for_review,
    preserve_evidence_filing_error_for_review,
    preserve_payload_validation_failure_for_review,
    preserve_route_failure_for_review,
    preserve_routing_failure_for_review,
)


@dataclass(frozen=True, slots=True)
class _PageRouteOutcome:
    page_number: int
    status: str
    category: str | None = None


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
        if not _validate_source_file(source_file):
            return 1
        if source_file.suffix.lower() == ".pdf":
            return _route_source_pdf_qr(
                workspace_root,
                source_file=source_file,
                created_at=intake_timestamp,
            )
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


def _decoded_page_from_qr_image(
    workspace_root: Path,
    *,
    source_file: Path,
    image: object,
    source_page_number: int,
    created_at: datetime,
) -> DecodedResponsePage | int:
    """Decode and validate a Quillan response-page QR from one loaded image."""
    try:
        decode_result = decode_qr_payload_from_image(image)
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
            source_page_number=source_page_number,
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
            source_page_number=source_page_number,
        )

    return validation_result


def _route_decoded_page(
    workspace_root: Path,
    *,
    source_file: Path,
    decoded_page: DecodedResponsePage,
    created_at: datetime,
    routed_source_file_path: Path | None = None,
    routed_extension: str | None = None,
    source_page_number: int | None = None,
    print_success: bool = True,
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
                source_page_number=source_page_number,
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
                routed_source_file_path=routed_source_file_path,
                routed_extension=routed_extension,
            )
        except EvidenceFilingError as error:
            review_record = preserve_evidence_filing_error_for_review(
                workspace_root,
                error=error,
                route_plan=route_result,
                source_filename=source_file.name,
                source_page_number=source_page_number,
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

    if print_success:
        print_routed_evidence(filed_evidence)
    return 0


def _route_source_pdf_qr(
    workspace_root: Path,
    *,
    source_file: Path,
    created_at: datetime,
) -> int:
    """Convert and route each page of a QR-bearing PDF scan independently."""
    print(f"Processing PDF: {source_file}")
    try:
        pages = list(iter_pdf_page_images(source_file))
    except PdfPageConversionError as error:
        return _preserve_pdf_conversion_failure(
            workspace_root,
            source_file=source_file,
            failure=error.failure,
            created_at=created_at,
        )
    except Exception as error:
        failure = PdfPageConversionFailure(
            failure_category="processing_error",
            failure_message=f"Unexpected PDF conversion failure: {error}",
            module_details={"failure_origin": "pdf_conversion"},
        )
        return _preserve_pdf_conversion_failure(
            workspace_root,
            source_file=source_file,
            failure=failure,
            created_at=created_at,
        )

    if not pages:
        failure = PdfPageConversionFailure(
            failure_category="source_unreadable",
            failure_message="PDF did not contain any pages to process.",
            module_details={
                "failure_origin": "pdf_conversion",
                "reason": "zero_pages",
            },
        )
        return _preserve_pdf_conversion_failure(
            workspace_root,
            source_file=source_file,
            failure=failure,
            created_at=created_at,
        )

    print(f"Pages: {len(pages)}")
    print()
    outcomes: list[_PageRouteOutcome] = []
    with tempfile.TemporaryDirectory(prefix="quillan-pdf-pages-") as temp_dir:
        temp_root = Path(temp_dir)
        for page in pages:
            outcome = _route_pdf_page_qr(
                workspace_root,
                source_file=source_file,
                page=page,
                created_at=created_at
                + timedelta(microseconds=page.page_number - 1),
                temp_root=temp_root,
            )
            outcomes.append(outcome)
            if outcome.status == "routed":
                print(f"Page {outcome.page_number}: routed")
            else:
                print(
                    f"Page {outcome.page_number}: preserved for review"
                    f" - {outcome.category}"
                )

    routed = sum(1 for outcome in outcomes if outcome.status == "routed")
    preserved = sum(1 for outcome in outcomes if outcome.status == "preserved")
    failed = sum(1 for outcome in outcomes if outcome.status == "failed")
    print()
    print("Summary:")
    print(f"Pages processed: {len(outcomes)}")
    print(f"Routed: {routed}")
    print(f"Preserved for review: {preserved}")
    print(f"Failed: {failed}")
    return 1 if failed else 0


def _route_pdf_page_qr(
    workspace_root: Path,
    *,
    source_file: Path,
    page: PdfPageImage,
    created_at: datetime,
    temp_root: Path,
) -> _PageRouteOutcome:
    decoded_result = _decoded_page_from_qr_image(
        workspace_root,
        source_file=source_file,
        image=page.image,
        source_page_number=page.page_number,
        created_at=created_at,
    )
    if isinstance(decoded_result, int):
        return _PageRouteOutcome(
            page_number=page.page_number,
            status="preserved" if decoded_result == 0 else "failed",
            category=_latest_review_category(workspace_root),
        )

    page_image_path = temp_root / f"page_{page.page_number:03d}.png"
    try:
        written = cv2.imwrite(str(page_image_path), cast(ImageArray, page.image))
    except cv2.error as error:
        print(f"Error: could not prepare PDF page image for routing: {error}")
        return _PageRouteOutcome(page.page_number, "failed", "processing_error")
    if not written:
        print("Error: could not prepare PDF page image for routing.")
        return _PageRouteOutcome(page.page_number, "failed", "processing_error")

    return _route_pdf_decoded_page(
        workspace_root,
        source_file=source_file,
        decoded_page=decoded_result,
        created_at=created_at,
        routed_source_file_path=page_image_path,
        source_page_number=page.page_number,
    )


def _route_pdf_decoded_page(
    workspace_root: Path,
    *,
    source_file: Path,
    decoded_page: DecodedResponsePage,
    created_at: datetime,
    routed_source_file_path: Path,
    source_page_number: int,
) -> _PageRouteOutcome:
    """Plan and file one decoded PDF page, returning a page summary outcome."""
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
                source_page_number=source_page_number,
                created_at=created_at,
            )
            return _PageRouteOutcome(
                source_page_number,
                "preserved",
                review_record.failure_category,
            )

        try:
            # The existing filing layer retains the original source for each
            # page route. The routed artifact itself is the extracted page PNG,
            # so assignment evidence is never the whole multi-page PDF.
            file_routed_response_evidence(
                workspace_root,
                route_plan=route_result,
                source_file_path=source_file,
                intake_timestamp=created_at,
                routed_source_file_path=routed_source_file_path,
                routed_extension=".png",
            )
        except EvidenceFilingError as error:
            review_record = preserve_evidence_filing_error_for_review(
                workspace_root,
                error=error,
                route_plan=route_result,
                source_filename=source_file.name,
                source_page_number=source_page_number,
                created_at=created_at,
            )
            return _PageRouteOutcome(
                source_page_number,
                "preserved",
                review_record.failure_category,
            )
    except RoutingReviewError as error:
        print(f"Error: could not preserve scan routing failure for review: {error}")
        return _PageRouteOutcome(
            source_page_number,
            "failed",
            "review_preservation_failed",
        )
    except Exception as error:
        print(f"Error: unexpected route-scan failure: {error}")
        return _PageRouteOutcome(source_page_number, "failed", "processing_error")

    return _PageRouteOutcome(source_page_number, "routed")


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
            module=None,
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
    source_page_number: int | None = None,
) -> int:
    """Preserve source/QR decode failure context for teacher review."""
    try:
        review_record = preserve_decode_failure_for_review(
            workspace_root,
            decode_result=decode_result,
            source_filename=source_file.name,
            source_page_number=source_page_number,
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
        reason=review_record.failure_message,
        category=review_record.failure_category,
        review_record=review_record,
    )
    return 0


def _preserve_payload_validation_failure(
    workspace_root: Path,
    *,
    source_file: Path,
    failure: ResponsePayloadValidationFailure,
    created_at: datetime,
    source_page_number: int | None = None,
) -> int:
    """Preserve decoded-payload validation failure context for review."""
    try:
        review_record = preserve_payload_validation_failure_for_review(
            workspace_root,
            source_filename=source_file.name,
            failure=failure,
            source_page_number=source_page_number,
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


def _preserve_pdf_conversion_failure(
    workspace_root: Path,
    *,
    source_file: Path,
    failure: PdfPageConversionFailure,
    created_at: datetime,
) -> int:
    """Preserve a whole-PDF conversion failure as one review record."""
    try:
        review_record = preserve_routing_failure_for_review(
            workspace_root,
            failure_category=failure.failure_category,
            failure_message=failure.failure_message,
            source_filename=source_file.name,
            module=None,
            source_page_number=failure.source_page_number,
            detected_payload=None,
            payload_page_number=None,
            class_id=None,
            assignment_id=None,
            student_id=None,
            module_details={
                "failure_origin": "pdf_conversion",
                **failure.module_details,
            },
            created_at=created_at,
        )
    except RoutingReviewError as review_error:
        print(
            "Error: PDF conversion failure could not be preserved for review: "
            f"{review_error}"
        )
        return 1
    except Exception as unexpected_error:
        print(
            "Error: unexpected failure while preserving PDF conversion failure: "
            f"{unexpected_error}"
        )
        return 1

    print("PDF could not be converted; preserved for review.")
    print(f"Category: {review_record.failure_category}")
    print(f"Review record: {review_record.failure_metadata_relative_path}")
    return 0


def _latest_review_category(workspace_root: Path) -> str | None:
    review_dir = workspace_root / "scans" / "review"
    try:
        records = sorted(
            review_dir.glob("*.json"),
            key=lambda path: path.stat().st_mtime_ns,
        )
    except OSError:
        return None
    if not records:
        return None
    try:
        import json

        loaded = json.loads(records[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(loaded, dict):
        return None
    category = loaded.get("failure_category")
    return category if isinstance(category, str) else None

"""Scan-routing command handler."""

from __future__ import annotations

import argparse
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, cast

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
    RoutedEvidenceFile,
    file_routed_response_evidence,
)
from quillan.intake_assembly import (
    IntakeAssemblyTarget,
    assembly_targets_from_intake_summary,
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
    SUPPORTED_IMAGE_EXTENSIONS,
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
from quillan.scan_intake_summary import (
    ScanIntakePageResult,
    ScanIntakeSourceResult,
    ScanIntakeSummary,
    format_scan_intake_summary,
)

SUPPORTED_SCAN_EXTENSIONS = frozenset({*SUPPORTED_IMAGE_EXTENSIONS, ".pdf"})


def handle_route_scan(args: argparse.Namespace) -> int:
    """Route source scans from caller-supplied payload text or QR."""
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
        if source_file.is_dir():
            return _route_source_folder_qr(
                workspace_root,
                source_folder=source_file,
                created_at=intake_timestamp,
            )
        if not _validate_source_file(source_file):
            return 1
        return _route_source_file_qr(
            workspace_root,
            source_file=source_file,
            created_at=intake_timestamp,
        )
    else:
        if source_file.is_dir():
            print(
                "Error: --payload route-scan mode requires a source file, "
                "not a folder."
            )
            return 1
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


def _route_source_file_qr(
    workspace_root: Path,
    *,
    source_file: Path,
    created_at: datetime,
) -> int:
    source_result = _intake_source_file_qr(
        workspace_root,
        source_file=source_file,
        created_at=created_at,
    )
    summary = ScanIntakeSummary((source_result,))
    print()
    print(format_scan_intake_summary(summary))
    _print_submission_assembly_next_steps(summary)
    return 1 if summary.has_failures else 0


def _route_source_folder_qr(
    workspace_root: Path,
    *,
    source_folder: Path,
    created_at: datetime,
) -> int:
    if not _validate_source_folder(source_folder):
        return 1

    supported_files, skipped_unsupported_count = _discover_supported_scan_files(
        source_folder
    )
    if not supported_files:
        print(f"Error: no supported scan files found in folder: {source_folder}")
        if skipped_unsupported_count:
            print(f"Skipped unsupported files: {skipped_unsupported_count}")
        return 1

    print(f"Processing folder: {source_folder}")
    print(f"Supported scan files: {len(supported_files)}")
    if skipped_unsupported_count:
        print(f"Skipped unsupported files: {skipped_unsupported_count}")
    print()

    source_results: list[ScanIntakeSourceResult] = []
    for source_index, source_file in enumerate(supported_files):
        print(f"Source {source_index + 1}: {source_file.name}")
        source_results.append(
            _intake_source_file_qr(
                workspace_root,
                source_file=source_file,
                created_at=created_at + timedelta(seconds=source_index),
                route_image_as_png=True,
            )
        )
        print()

    summary = ScanIntakeSummary(
        tuple(source_results),
        skipped_unsupported_count=skipped_unsupported_count,
    )
    print(format_scan_intake_summary(summary))
    _print_submission_assembly_next_steps(summary)
    return 1 if summary.has_failures else 0


def _print_submission_assembly_next_steps(summary: ScanIntakeSummary) -> None:
    targets = assembly_targets_from_intake_summary(summary)
    if not targets:
        return

    print()
    if summary.requires_review:
        print("Review required before intake is complete.")
        print(
            "You may assemble submissions for routed evidence now, but "
            "preserved failures should be reviewed before treating the batch "
            "as complete."
        )
        print()
    print("Next step:" if len(targets) == 1 else "Next steps:")
    print("Run submission assembly for newly routed evidence:")
    if len(targets) == 1:
        target = targets[0]
        line = _format_assembly_command(target)
        if target.routed_page_count != 1:
            line = f"{line}  ({target.routed_page_count} routed pages)"
        print(line)
        return
    for target in targets:
        print(
            f"- {_format_assembly_command(target)}  "
            f"({target.routed_page_count} routed pages)"
        )


def _format_assembly_command(target: IntakeAssemblyTarget) -> str:
    return (
        "quillan assemble-submissions "
        f"{target.class_id} {target.assignment_id}"
    )


def _intake_source_file_qr(
    workspace_root: Path,
    *,
    source_file: Path,
    created_at: datetime,
    route_image_as_png: bool = False,
) -> ScanIntakeSourceResult:
    if source_file.suffix.lower() == ".pdf":
        return _intake_source_pdf_qr(
            workspace_root,
            source_file=source_file,
            created_at=created_at,
        )
    return _intake_source_image_qr(
        workspace_root,
        source_file=source_file,
        created_at=created_at,
        route_as_png=route_image_as_png,
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
) -> DecodedResponsePage | ScanIntakePageResult:
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
) -> DecodedResponsePage | ScanIntakePageResult:
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


def _intake_source_image_qr(
    workspace_root: Path,
    *,
    source_file: Path,
    created_at: datetime,
    route_as_png: bool = False,
) -> ScanIntakeSourceResult:
    """Decode and route one QR-bearing image."""
    decoded_result = _decoded_page_from_source_qr(
        workspace_root,
        source_file=source_file,
        created_at=created_at,
    )
    if isinstance(decoded_result, ScanIntakePageResult):
        page_result = decoded_result
    else:
        if route_as_png and source_file.suffix.lower() != ".png":
            page_result = _route_decoded_image_page_as_png_result(
                workspace_root,
                source_file=source_file,
                decoded_page=decoded_result,
                created_at=created_at,
            )
        else:
            page_result = _route_decoded_page_result(
                workspace_root,
                source_file=source_file,
                decoded_page=decoded_result,
                created_at=created_at,
            )
    return _source_result_from_pages(
        source_file=source_file,
        source_type="image",
        page_results=(page_result,),
    )


def _route_decoded_image_page_as_png_result(
    workspace_root: Path,
    *,
    source_file: Path,
    decoded_page: DecodedResponsePage,
    created_at: datetime,
) -> ScanIntakePageResult:
    with tempfile.TemporaryDirectory(prefix="quillan-image-route-") as temp_dir:
        routed_image_path = Path(temp_dir) / "source.png"
        try:
            image = cv2.imread(str(source_file), cv2.IMREAD_COLOR)
            written = (
                False
                if image is None
                else cv2.imwrite(str(routed_image_path), image)
            )
        except cv2.error as error:
            print(f"Error: could not prepare source image for routing: {error}")
            return _failed_page_result(
                source_filename=source_file.name,
                source_page_number=None,
                payload_page_number=decoded_page.page_number,
                failure_category="processing_error",
                failure_message=str(error),
                decoded_page=decoded_page,
            )
        if not written:
            print("Error: could not prepare source image for routing.")
            return _failed_page_result(
                source_filename=source_file.name,
                source_page_number=None,
                payload_page_number=decoded_page.page_number,
                failure_category="processing_error",
                failure_message="Could not prepare source image for routing.",
                decoded_page=decoded_page,
            )

        return _route_decoded_page_result(
            workspace_root,
            source_file=source_file,
            decoded_page=decoded_page,
            created_at=created_at,
            routed_source_file_path=routed_image_path,
            routed_extension=".png",
        )


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
    page_result = _route_decoded_page_result(
        workspace_root,
        source_file=source_file,
        decoded_page=decoded_page,
        created_at=created_at,
        routed_source_file_path=routed_source_file_path,
        routed_extension=routed_extension,
        source_page_number=source_page_number,
        print_success=print_success,
    )
    return 1 if page_result.status == "failed" else 0


def _route_decoded_page_result(
    workspace_root: Path,
    *,
    source_file: Path,
    decoded_page: DecodedResponsePage,
    created_at: datetime,
    routed_source_file_path: Path | None = None,
    routed_extension: str | None = None,
    source_page_number: int | None = None,
    print_success: bool = True,
) -> ScanIntakePageResult:
    """Plan and file one decoded Quillan response page."""
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
            return _page_result_from_review_record(
                source_filename=source_file.name,
                source_page_number=source_page_number,
                status="preserved",
                review_record=review_record,
                payload_page_number=route_result.page_number,
                class_id=route_result.class_id,
                assignment_id=route_result.assignment_id,
                student_id=route_result.student_id,
            )

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
            return _page_result_from_review_record(
                source_filename=source_file.name,
                source_page_number=source_page_number,
                status="preserved",
                review_record=review_record,
                payload_page_number=route_result.page_number,
                class_id=route_result.class_id,
                assignment_id=route_result.assignment_id,
                student_id=route_result.student_id,
            )
    except RoutingReviewError as error:
        print(f"Error: could not preserve scan routing failure for review: {error}")
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=source_page_number,
            payload_page_number=decoded_page.page_number,
            failure_category="review_preservation_failed",
            failure_message=str(error),
            decoded_page=decoded_page,
        )
    except Exception as error:
        print(f"Error: unexpected route-scan failure: {error}")
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=source_page_number,
            payload_page_number=decoded_page.page_number,
            failure_category="processing_error",
            failure_message=str(error),
            decoded_page=decoded_page,
        )

    if print_success:
        print_routed_evidence(filed_evidence)
    return _page_result_from_filed_evidence(
        source_filename=source_file.name,
        source_page_number=source_page_number,
        filed_evidence=filed_evidence,
    )


def _intake_source_pdf_qr(
    workspace_root: Path,
    *,
    source_file: Path,
    created_at: datetime,
) -> ScanIntakeSourceResult:
    """Convert and route each page of a QR-bearing PDF scan independently."""
    print(f"Processing PDF: {source_file}")
    try:
        pages = list(iter_pdf_page_images(source_file))
    except PdfPageConversionError as error:
        return _pdf_conversion_failure_source_result(
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
        return _pdf_conversion_failure_source_result(
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
        return _pdf_conversion_failure_source_result(
            workspace_root,
            source_file=source_file,
            failure=failure,
            created_at=created_at,
        )

    print(f"Pages: {len(pages)}")
    print()
    page_results: list[ScanIntakePageResult] = []
    with tempfile.TemporaryDirectory(prefix="quillan-pdf-pages-") as temp_dir:
        temp_root = Path(temp_dir)
        for page in pages:
            page_result = _route_pdf_page_qr(
                workspace_root,
                source_file=source_file,
                page=page,
                created_at=created_at
                + timedelta(microseconds=page.page_number - 1),
                temp_root=temp_root,
            )
            page_results.append(page_result)
            page_number = page_result.source_page_number
            if page_result.status == "routed":
                print(f"Page {page_number}: routed")
            else:
                print(
                    f"Page {page_number}: {page_result.status}"
                    f" - {page_result.failure_category}"
                )

    return _source_result_from_pages(
        source_file=source_file,
        source_type="pdf",
        page_results=tuple(page_results),
    )


def _route_pdf_page_qr(
    workspace_root: Path,
    *,
    source_file: Path,
    page: PdfPageImage,
    created_at: datetime,
    temp_root: Path,
) -> ScanIntakePageResult:
    decoded_result = _decoded_page_from_qr_image(
        workspace_root,
        source_file=source_file,
        image=page.image,
        source_page_number=page.page_number,
        created_at=created_at,
    )
    if isinstance(decoded_result, ScanIntakePageResult):
        return decoded_result

    page_image_path = temp_root / f"page_{page.page_number:03d}.png"
    try:
        written = cv2.imwrite(str(page_image_path), cast(ImageArray, page.image))
    except cv2.error as error:
        print(f"Error: could not prepare PDF page image for routing: {error}")
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=page.page_number,
            payload_page_number=decoded_result.page_number,
            failure_category="processing_error",
            failure_message=str(error),
            decoded_page=decoded_result,
        )
    if not written:
        print("Error: could not prepare PDF page image for routing.")
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=page.page_number,
            payload_page_number=decoded_result.page_number,
            failure_category="processing_error",
            failure_message="Could not prepare PDF page image for routing.",
            decoded_page=decoded_result,
        )

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
) -> ScanIntakePageResult:
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
            return _page_result_from_review_record(
                source_filename=source_file.name,
                source_page_number=source_page_number,
                status="preserved",
                review_record=review_record,
                payload_page_number=route_result.page_number,
                class_id=route_result.class_id,
                assignment_id=route_result.assignment_id,
                student_id=route_result.student_id,
            )

        try:
            # The existing filing layer retains the original source for each
            # page route. The routed artifact itself is the extracted page PNG,
            # so assignment evidence is never the whole multi-page PDF.
            filed_evidence = file_routed_response_evidence(
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
            return _page_result_from_review_record(
                source_filename=source_file.name,
                source_page_number=source_page_number,
                status="preserved",
                review_record=review_record,
                payload_page_number=route_result.page_number,
                class_id=route_result.class_id,
                assignment_id=route_result.assignment_id,
                student_id=route_result.student_id,
            )
    except RoutingReviewError as error:
        print(f"Error: could not preserve scan routing failure for review: {error}")
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=source_page_number,
            payload_page_number=decoded_page.page_number,
            failure_category="review_preservation_failed",
            failure_message=str(error),
            decoded_page=decoded_page,
        )
    except Exception as error:
        print(f"Error: unexpected route-scan failure: {error}")
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=source_page_number,
            payload_page_number=decoded_page.page_number,
            failure_category="processing_error",
            failure_message=str(error),
            decoded_page=decoded_page,
        )

    return _page_result_from_filed_evidence(
        source_filename=source_file.name,
        source_page_number=source_page_number,
        filed_evidence=filed_evidence,
    )


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


def _validate_source_folder(source_folder: Path) -> bool:
    """Return whether the selected scan folder is an existing directory."""
    try:
        if not source_folder.is_dir():
            print(
                "Error: scan folder must be an existing directory: "
                f"{source_folder}"
            )
            return False
        list(source_folder.iterdir())
    except OSError as error:
        print(f"Error: scan folder is not readable: {error}")
        return False
    return True


def _discover_supported_scan_files(source_folder: Path) -> tuple[list[Path], int]:
    """Return direct child scan files in deterministic order and skip count."""
    supported_files: list[Path] = []
    skipped_unsupported_count = 0
    for child in source_folder.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() in SUPPORTED_SCAN_EXTENSIONS:
            supported_files.append(child)
        else:
            skipped_unsupported_count += 1
    supported_files.sort(key=lambda path: (path.name.lower(), path.name))
    return supported_files, skipped_unsupported_count


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
) -> ScanIntakePageResult:
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
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=source_page_number,
            payload_page_number=None,
            failure_category="review_preservation_failed",
            failure_message=str(review_error),
        )
    except Exception as unexpected_error:
        print(
            "Error: unexpected failure while preserving QR decode failure: "
            f"{unexpected_error}"
        )
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=source_page_number,
            payload_page_number=None,
            failure_category="processing_error",
            failure_message=str(unexpected_error),
        )

    _print_preserved_intake_failure(
        reason=review_record.failure_message,
        category=review_record.failure_category,
        review_record=review_record,
    )
    return _page_result_from_review_record(
        source_filename=source_file.name,
        source_page_number=source_page_number,
        status="preserved",
        review_record=review_record,
    )


def _preserve_payload_validation_failure(
    workspace_root: Path,
    *,
    source_file: Path,
    failure: ResponsePayloadValidationFailure,
    created_at: datetime,
    source_page_number: int | None = None,
) -> ScanIntakePageResult:
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
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=source_page_number,
            payload_page_number=failure.page_number,
            failure_category="review_preservation_failed",
            failure_message=str(review_error),
            class_id=failure.class_id,
            assignment_id=failure.assignment_id,
            student_id=failure.student_id,
        )
    except Exception as unexpected_error:
        print(
            "Error: unexpected failure while preserving decoded payload failure: "
            f"{unexpected_error}"
        )
        return _failed_page_result(
            source_filename=source_file.name,
            source_page_number=source_page_number,
            payload_page_number=failure.page_number,
            failure_category="processing_error",
            failure_message=str(unexpected_error),
            class_id=failure.class_id,
            assignment_id=failure.assignment_id,
            student_id=failure.student_id,
        )

    _print_preserved_intake_failure(
        reason=failure.failure_message,
        category=failure.failure_category,
        review_record=review_record,
    )
    return _page_result_from_review_record(
        source_filename=source_file.name,
        source_page_number=source_page_number,
        status="preserved",
        review_record=review_record,
        payload_page_number=failure.page_number,
        class_id=failure.class_id,
        assignment_id=failure.assignment_id,
        student_id=failure.student_id,
    )


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


def _pdf_conversion_failure_source_result(
    workspace_root: Path,
    *,
    source_file: Path,
    failure: PdfPageConversionFailure,
    created_at: datetime,
) -> ScanIntakeSourceResult:
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
        return ScanIntakeSourceResult(
            source_filename=source_file.name,
            source_path=source_file,
            source_type="pdf",
            status="failed",
            pages_attempted=0,
            routed_count=0,
            preserved_count=0,
            failed_count=1,
            page_results=(),
            source_failure_category="review_preservation_failed",
            source_failure_message=str(review_error),
        )
    except Exception as unexpected_error:
        print(
            "Error: unexpected failure while preserving PDF conversion failure: "
            f"{unexpected_error}"
        )
        return ScanIntakeSourceResult(
            source_filename=source_file.name,
            source_path=source_file,
            source_type="pdf",
            status="failed",
            pages_attempted=0,
            routed_count=0,
            preserved_count=0,
            failed_count=1,
            page_results=(),
            source_failure_category="processing_error",
            source_failure_message=str(unexpected_error),
        )

    print("PDF could not be converted; preserved for review.")
    print(f"Category: {review_record.failure_category}")
    print(f"Review record: {review_record.failure_metadata_relative_path}")
    return ScanIntakeSourceResult(
        source_filename=source_file.name,
        source_path=source_file,
        source_type="pdf",
        status="preserved",
        pages_attempted=0,
        routed_count=0,
        preserved_count=1,
        failed_count=0,
        page_results=(),
        source_failure_category=review_record.failure_category,
        source_failure_message=review_record.failure_message,
        review_metadata_relative_path=(
            review_record.failure_metadata_relative_path
        ),
    )


def _page_result_from_filed_evidence(
    *,
    source_filename: str,
    source_page_number: int | None,
    filed_evidence: RoutedEvidenceFile,
) -> ScanIntakePageResult:
    return ScanIntakePageResult(
        source_filename=source_filename,
        source_page_number=source_page_number,
        payload_page_number=filed_evidence.page_number,
        status="routed",
        class_id=filed_evidence.class_id,
        assignment_id=filed_evidence.assignment_id,
        student_id=filed_evidence.student_id,
        routed_evidence_relative_path=(
            filed_evidence.routed_evidence_relative_path
        ),
        retained_source_relative_path=(
            filed_evidence.retained_source.retained_source_relative_path
        ),
    )


def _page_result_from_review_record(
    *,
    source_filename: str,
    source_page_number: int | None,
    status: Literal["routed", "preserved", "failed"],
    review_record: RoutingReviewRecord,
    payload_page_number: int | None = None,
    class_id: str | None = None,
    assignment_id: str | None = None,
    student_id: str | None = None,
) -> ScanIntakePageResult:
    return ScanIntakePageResult(
        source_filename=source_filename,
        source_page_number=source_page_number,
        payload_page_number=payload_page_number,
        status=status,
        failure_category=review_record.failure_category,
        failure_message=review_record.failure_message,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        retained_source_relative_path=review_record.retained_source_relative_path,
        review_metadata_relative_path=(
            review_record.failure_metadata_relative_path
        ),
    )


def _failed_page_result(
    *,
    source_filename: str,
    source_page_number: int | None,
    payload_page_number: int | None,
    failure_category: str,
    failure_message: str,
    decoded_page: DecodedResponsePage | None = None,
    class_id: str | None = None,
    assignment_id: str | None = None,
    student_id: str | None = None,
) -> ScanIntakePageResult:
    return ScanIntakePageResult(
        source_filename=source_filename,
        source_page_number=source_page_number,
        payload_page_number=payload_page_number,
        status="failed",
        failure_category=failure_category,
        failure_message=failure_message,
        class_id=class_id if decoded_page is None else decoded_page.class_id,
        assignment_id=(
            assignment_id if decoded_page is None else decoded_page.assignment_id
        ),
        student_id=student_id if decoded_page is None else decoded_page.student_id,
    )


def _source_result_from_pages(
    *,
    source_file: Path,
    source_type: Literal["image", "pdf"],
    page_results: tuple[ScanIntakePageResult, ...],
) -> ScanIntakeSourceResult:
    routed = sum(1 for page in page_results if page.status == "routed")
    preserved = sum(1 for page in page_results if page.status == "preserved")
    failed = sum(1 for page in page_results if page.status == "failed")
    if failed and routed == 0 and preserved == 0:
        status = "failed"
    elif preserved or failed:
        status = "partial" if routed else "preserved"
    else:
        status = "completed"
    return ScanIntakeSourceResult(
        source_filename=source_file.name,
        source_path=source_file,
        source_type=source_type,
        status=cast(Literal["completed", "partial", "failed", "preserved"], status),
        pages_attempted=len(page_results),
        routed_count=routed,
        preserved_count=preserved,
        failed_count=failed,
        page_results=page_results,
    )

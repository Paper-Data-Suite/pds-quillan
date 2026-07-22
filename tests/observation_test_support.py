"""Synthetic PDS2 success fixtures for observation persistence tests."""

from pathlib import Path

from pds_core.module_dispatch import RouteDispatchRequest, RouteDispatchSuccess
from pds_core.scan_retention import retain_source_scan
from pds_core.route_registrations import write_route_registration
from reportlab.pdfgen import canvas

from quillan.pds2_scan_intake import QuillanScanPageOutcome
from quillan.pds_module import get_module_profile
from quillan.route_handler import handle_quillan_response_page_route
from tests.test_route_handler import route_context
from tests.review_test_support import _write_assignment


def successful_image_page(root: Path, *, pages: int = 1) -> QuillanScanPageOutcome:
    resolution, _ = route_context(root, pages=pages)
    _write_assignment(
        root,
        class_id=resolution.locator.class_id,
        assignment_id=resolution.locator.work_id,
    )
    write_route_registration(root, resolution.registration)
    selected = root / "selected.png"
    selected.write_bytes(b"synthetic retained image bytes")
    retained = retain_source_scan(root, selected)
    result = handle_quillan_response_page_route(resolution, retained, 1)
    request = RouteDispatchRequest(resolution.locator, retained, 1)
    success = RouteDispatchSuccess(
        request=request,
        profile=get_module_profile(),
        resolution=resolution,
        module_result=result,
    )
    return QuillanScanPageOutcome(
        source_page_number=1,
        terminal_category="dispatch_success",
        retained_source=retained,
        raw_payload_text="PDS2 synthetic",
        locator=resolution.locator,
        decode_method="synthetic",
        dispatch_request=request,
        dispatch_outcome=success,
    )


def successful_pdf_pages(
    root: Path,
    *,
    source_page_numbers: tuple[int, ...] = (1, 2),
) -> tuple[QuillanScanPageOutcome, ...]:
    resolution, _ = route_context(root)
    _write_assignment(
        root,
        class_id=resolution.locator.class_id,
        assignment_id=resolution.locator.work_id,
    )
    write_route_registration(root, resolution.registration)
    selected = root / "selected.pdf"
    document = canvas.Canvas(str(selected), pagesize=(200, 200))
    for number in range(1, max(source_page_numbers) + 1):
        document.drawString(20, 100, f"Synthetic physical page {number}")
        document.showPage()
    document.save()
    retained = retain_source_scan(root, selected)
    outcomes: list[QuillanScanPageOutcome] = []
    for source_page_number in source_page_numbers:
        result = handle_quillan_response_page_route(
            resolution, retained, source_page_number
        )
        request = RouteDispatchRequest(resolution.locator, retained, source_page_number)
        success = RouteDispatchSuccess(
            request=request,
            profile=get_module_profile(),
            resolution=resolution,
            module_result=result,
        )
        outcomes.append(
            QuillanScanPageOutcome(
                source_page_number=source_page_number,
                terminal_category="dispatch_success",
                retained_source=retained,
                raw_payload_text="PDS2 synthetic",
                locator=resolution.locator,
                decode_method="synthetic",
                dispatch_request=request,
                dispatch_outcome=success,
            )
        )
    return tuple(outcomes)

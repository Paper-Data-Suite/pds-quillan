"""Managed PDF renderer for persisted and verified PDS2 response pages."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import re
from typing import Final

import qrcode
from pds_core.routing_models import ModuleWorkRef, RoutingModelError
from qrcode.constants import ERROR_CORRECT_M
from qrcode.image.pil import PilImage
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from quillan.printable_response_records import (
    PrintableResponseRecordSet,
    PrintableResponseRecordValidationError,
    validate_printable_response_record_set,
)
from quillan.printable_response_persistence import (
    PersistedPrintableResponseRecordSet,
    PrintableResponsePersistenceError,
)
from quillan.printable_response_routes import (
    PersistedPrintableResponseRouteSet,
    PrintableResponseRouteError,
    RegisteredPrintableResponsePageRoute,
    validate_registered_printable_response_route_set,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    _is_link_like,
    preflight_work_file_destination,
    quillan_work_paths,
    quillan_work_ref,
)

PRINTABLE_RESPONSE_FILENAME: Final[str] = "printable_response_pages.pdf"
_TEMPORARY_FILENAME = re.compile(
    r"^\.printable_response_pages\.[0-9a-f]{16}\.tmp\.pdf$"
)


class PrintableResponseRenderError(ValueError):
    """Raised when managed printable-response render input is invalid."""


def render_printable_response_pdf(
    workspace_root: str | Path,
    work_ref: object,
    destination: str | Path,
    packets: object,
) -> Path:
    """Render ordered immutable records using only persisted verified routes."""
    root, validated_work, output = _validate_render_authority(
        workspace_root, work_ref, destination
    )
    if not isinstance(packets, tuple) or not packets:
        raise PrintableResponseRenderError("packets must be a nonempty tuple.")
    validated: list[
        tuple[
            PrintableResponseRecordSet,
            tuple[RegisteredPrintableResponsePageRoute, ...],
        ]
    ] = []
    for packet in packets:
        if not isinstance(packet, tuple) or len(packet) != 2:
            raise PrintableResponseRenderError(
                "Each render packet must contain persisted records and routes."
            )
        persisted_records, persisted_routes = packet
        if not isinstance(persisted_records, PersistedPrintableResponseRecordSet):
            raise PrintableResponseRenderError(
                "Rendering requires a PersistedPrintableResponseRecordSet."
            )
        if not isinstance(persisted_routes, PersistedPrintableResponseRouteSet):
            raise PrintableResponseRenderError(
                "Rendering requires a PersistedPrintableResponseRouteSet."
            )
        if persisted_routes.record_set != persisted_records.record_set:
            raise PrintableResponseRenderError(
                "Persisted record and route sets do not identify the same records."
            )
        try:
            verified = validate_registered_printable_response_route_set(
                root, validated_work, persisted_routes
            )
            validate_printable_response_record_set(verified.record_set)
        except (
            PrintableResponsePersistenceError,
            PrintableResponseRecordValidationError,
            PrintableResponseRouteError,
            OSError,
        ) as error:
            raise PrintableResponseRenderError(str(error)) from error
        validated.append((verified.record_set, verified.routes))

    pdf = Canvas(str(output), pagesize=letter)
    pdf.setTitle("Quillan Printable Writing Response Pages")
    for record_set, routes in validated:
        for route in routes:
            _draw_response_page(pdf, record_set, route)
            pdf.showPage()
    pdf.save()
    return output


def _validate_render_authority(
    workspace_root: str | Path,
    work_ref: object,
    destination: str | Path,
) -> tuple[Path, ModuleWorkRef, Path]:
    if not isinstance(workspace_root, (str, Path)):
        raise PrintableResponseRenderError(
            "workspace_root must be a string or Path."
        )
    supplied_root = Path(workspace_root)
    if not supplied_root.is_absolute():
        raise PrintableResponseRenderError(
            "workspace_root must be an absolute path."
        )
    root = Path(os.path.abspath(supplied_root))
    if not isinstance(work_ref, ModuleWorkRef):
        raise PrintableResponseRenderError("work_ref must be a ModuleWorkRef.")
    try:
        validated_work = quillan_work_ref(work_ref.class_id, work_ref.work_id)
    except (RoutingModelError, ValueError, TypeError, AttributeError) as error:
        raise PrintableResponseRenderError(str(error)) from error
    if work_ref != validated_work:
        raise PrintableResponseRenderError("work_ref must identify exact Quillan work.")
    if not isinstance(destination, (str, Path)):
        raise PrintableResponseRenderError("destination must be a string or Path.")
    supplied = Path(destination)
    if not supplied.is_absolute():
        raise PrintableResponseRenderError("destination must be an absolute path.")
    output = Path(os.path.abspath(supplied))
    paths = quillan_work_paths(root, validated_work.class_id, validated_work.work_id)
    if output.parent != paths.templates_dir or _TEMPORARY_FILENAME.fullmatch(output.name) is None:
        raise PrintableResponseRenderError(
            "destination must be a governed immediate temporary child of templates/."
        )
    try:
        canonical = preflight_work_file_destination(
            root, validated_work, Path("templates") / output.name
        )
    except QuillanWorkPathError as error:
        raise PrintableResponseRenderError(str(error)) from error
    if canonical != output:
        raise PrintableResponseRenderError("destination is not canonical.")
    if not os.path.lexists(output) or _is_link_like(output) or not output.is_file():
        raise PrintableResponseRenderError(
            "destination must be an existing ordinary non-link temporary file."
        )
    return root, validated_work, output


def _draw_response_page(
    pdf: Canvas,
    record_set: PrintableResponseRecordSet,
    route: RegisteredPrintableResponsePageRoute,
) -> None:
    issuance = record_set.issuance
    page = route.page
    page_width, page_height = letter
    margin = 0.5 * inch
    qr_size = 1.0 * inch
    qr_x = page_width - margin - qr_size
    qr_y = page_height - margin - qr_size
    text_width = qr_x - margin - 0.2 * inch

    pdf.setFillColor(HexColor("#111111"))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(
        margin,
        page_height - margin - 14,
        _fit_text(
            issuance.assignment_snapshot.title,
            "Helvetica-Bold",
            14,
            text_width,
        ),
    )
    class_text = (
        f"Class: {issuance.class_label} ({page.class_id})"
        if issuance.class_label != page.class_id
        else f"Class: {page.class_id}"
    )
    identity_lines = (
        f"Student: {issuance.student_snapshot.display_name}",
        f"Student ID: {page.student_id}",
        class_text,
        f"Assignment ID: {page.assignment_id}",
    )
    pdf.setFont("Helvetica", 9)
    line_y = page_height - margin - 31
    for identity_line in identity_lines:
        pdf.drawString(margin, line_y, _fit_text(identity_line, "Helvetica", 9, text_width))
        line_y -= 12

    pdf.drawImage(
        _make_qr_image(route.payload_text),
        qr_x,
        qr_y,
        width=qr_size,
        height=qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )
    header_bottom = page_height - margin - qr_size - 0.2 * inch
    pdf.setFillColor(HexColor("#333333"))
    pdf.setFont("Helvetica", 6)
    pdf.drawString(margin, header_bottom + 14, f"Page ID: {page.page_id}")
    pdf.drawString(margin, header_bottom + 6, f"Route ID: {route.locator.route_id}")
    pdf.setStrokeColor(HexColor("#555555"))
    pdf.setLineWidth(0.8)
    pdf.line(margin, header_bottom, page_width - margin, header_bottom)

    writing_top = header_bottom - 0.3 * inch
    writing_bottom = margin + 0.35 * inch
    writing_left = margin + 0.2 * inch
    writing_right = page_width - margin
    pdf.setStrokeColor(HexColor("#C8C8C8"))
    pdf.setLineWidth(0.35)
    line_y = writing_top
    while line_y >= writing_bottom:
        pdf.line(writing_left, line_y, writing_right, line_y)
        line_y -= 0.32 * inch
    pdf.setStrokeColor(HexColor("#C98888"))
    pdf.setLineWidth(0.5)
    pdf.line(writing_left, writing_bottom, writing_left, writing_top)

    pdf.setFillColor(HexColor("#333333"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(margin, margin - 6, "Quillan writing response")
    pdf.drawRightString(
        page_width - margin,
        margin - 6,
        f"Page {page.logical_page} of {page.total_pages}",
    )


def _make_qr_image(payload: str) -> ImageReader:
    qr = qrcode.QRCode[PilImage](
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=8,
        border=4,
        image_factory=PilImage,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    image_data = BytesIO()
    image.save(image_data, format="PNG")
    image_data.seek(0)
    return ImageReader(image_data)


def _fit_text(text: str, font_name: str, font_size: int, max_width: float) -> str:
    if stringWidth(text, font_name, font_size) <= max_width:
        return text
    ellipsis = "..."
    candidate = text
    while candidate and stringWidth(candidate + ellipsis, font_name, font_size) > max_width:
        candidate = candidate[:-1]
    return candidate + ellipsis


__all__ = [
    "PRINTABLE_RESPONSE_FILENAME",
    "PrintableResponseRenderError",
    "render_printable_response_pdf",
]

"""Printable PDF generation for Quillan writing-response pages."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final, Mapping, Sequence, TypeAlias, cast

from pds_core.rosters import StudentRecord, load_roster, student_display_name
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from qrcode.image.pil import PilImage
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from quillan.assignments import load_assignment_config
from quillan.payloads import build_response_payload
from quillan.storage import assignment_templates_dir

PRINTABLE_RESPONSE_FILENAME: Final = "printable_response_pages.pdf"
StudentInput: TypeAlias = StudentRecord | Mapping[str, str]


@dataclass(frozen=True)
class ResponsePageContext:
    """Validated identity and payload data for one printable response page."""

    class_id: str
    class_label: str
    assignment_id: str
    assignment_title: str
    student_id: str
    student_display_name: str
    page_number: int
    payload: str


def build_response_page_context(
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    student_display_name: str,
    page_number: int,
    assignment_title: str | None = None,
    class_label: str | None = None,
) -> ResponsePageContext:
    """Build validated display and routing data for one response page."""
    display_name = _require_display_text(student_display_name, "student_display_name")
    resolved_assignment_title = _optional_display_text(
        assignment_title, assignment_id, "assignment_title"
    )
    resolved_class_label = _optional_display_text(class_label, class_id, "class_label")
    payload = build_response_payload(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        page=page_number,
    )

    return ResponsePageContext(
        class_id=class_id,
        class_label=resolved_class_label,
        assignment_id=assignment_id,
        assignment_title=resolved_assignment_title,
        student_id=student_id,
        student_display_name=display_name,
        page_number=page_number,
        payload=payload,
    )


def generate_printable_response_pdf(
    workspace_root: str | Path,
    *,
    class_id: str,
    assignment_id: str,
    students: Sequence[StudentInput],
    pages_per_student: int = 1,
    assignment_title: str | None = None,
    class_label: str | None = None,
) -> Path:
    """Generate one assignment PDF containing student-specific response pages."""
    _validate_page_count(pages_per_student)
    if not students:
        raise ValueError("students must contain at least one student.")

    page_contexts = [
        build_response_page_context(
            class_id=class_id,
            assignment_id=assignment_id,
            assignment_title=assignment_title,
            class_label=class_label,
            student_id=_student_id(student),
            student_display_name=_student_name(student),
            page_number=page_number,
        )
        for student in students
        for page_number in range(1, pages_per_student + 1)
    ]

    output_dir = assignment_templates_dir(workspace_root, class_id, assignment_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / PRINTABLE_RESPONSE_FILENAME

    pdf = Canvas(str(output_path), pagesize=letter)
    pdf.setTitle("Quillan Printable Writing Response Pages")
    for context in page_contexts:
        _draw_response_page(pdf, context, pages_per_student)
        pdf.showPage()
    pdf.save()

    return output_path


def generate_printable_responses_for_roster(
    workspace_root: str | Path,
    *,
    assignment_path: str | Path,
    roster_path: str | Path,
    pages_per_student: int = 1,
    class_label: str | None = None,
) -> Path:
    """Generate printable response pages from validated shared roster records."""
    assignment = load_assignment_config(assignment_path)
    roster = load_roster(roster_path)
    assignment_class_ids = cast(list[str], assignment["class_ids"])

    if roster.class_id not in assignment_class_ids:
        raise ValueError(
            f"Roster class_id '{roster.class_id}' is not included in assignment "
            f"class_ids: {', '.join(assignment_class_ids)}."
        )

    return generate_printable_response_pdf(
        workspace_root,
        class_id=roster.class_id,
        assignment_id=cast(str, assignment["assignment_id"]),
        assignment_title=cast(str, assignment["title"]),
        class_label=class_label,
        students=roster.students,
        pages_per_student=pages_per_student,
    )


def _draw_response_page(
    pdf: Canvas,
    context: ResponsePageContext,
    pages_per_student: int,
) -> None:
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
        _fit_text(context.assignment_title, "Helvetica-Bold", 14, text_width),
    )

    identity_lines = (
        f"Student: {context.student_display_name}",
        f"Student ID: {context.student_id}",
        f"Class: {context.class_label} ({context.class_id})"
        if context.class_label != context.class_id
        else f"Class: {context.class_id}",
        f"Assignment ID: {context.assignment_id}",
    )
    pdf.setFont("Helvetica", 9)
    line_y = page_height - margin - 31
    for identity_line in identity_lines:
        pdf.drawString(
            margin,
            line_y,
            _fit_text(identity_line, "Helvetica", 9, text_width),
        )
        line_y -= 12

    pdf.drawImage(
        _make_qr_image(context.payload),
        qr_x,
        qr_y,
        width=qr_size,
        height=qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )

    header_bottom = page_height - margin - qr_size - 0.2 * inch
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
    pdf.drawString(
        margin,
        margin - 6,
        "Quillan writing response",
    )
    pdf.drawRightString(
        page_width - margin,
        margin - 6,
        f"Page {context.page_number} of {pages_per_student}",
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
    while (
        candidate
        and stringWidth(candidate + ellipsis, font_name, font_size) > max_width
    ):
        candidate = candidate[:-1]
    return candidate + ellipsis


def _student_id(student: StudentInput) -> str:
    if isinstance(student, StudentRecord):
        return _require_display_text(student.student_id, "student_id")
    return _student_field(student, "student_id")


def _student_name(student: StudentInput) -> str:
    if isinstance(student, StudentRecord):
        return _require_display_text(
            student_display_name(student), "student_display_name"
        )
    return _student_field(student, "student_display_name")


def _student_field(student: Mapping[str, str], field: str) -> str:
    try:
        value = student[field]
    except KeyError as error:
        raise ValueError(f"student is missing required field '{field}'.") from error
    return _require_display_text(value, field)


def _optional_display_text(
    value: str | None,
    fallback: str,
    field: str,
) -> str:
    if value is None:
        return fallback
    return _require_display_text(value, field)


def _require_display_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _validate_page_count(pages_per_student: int) -> None:
    if (
        isinstance(pages_per_student, bool)
        or not isinstance(pages_per_student, int)
        or pages_per_student < 1
    ):
        raise ValueError("pages_per_student must be a positive integer.")

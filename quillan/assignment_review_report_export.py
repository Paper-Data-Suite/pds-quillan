"""Supervisor-ready assignment review PDF from one reporting snapshot."""

from __future__ import annotations

import html
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from quillan.assignment_reporting_snapshot import (
    AssignmentReportingSnapshot,
    AssignmentReportingSnapshotError,
    ReportingStandard,
    ReportingStandardSummary,
    ReportingStudent,
    build_assignment_reporting_snapshot,
)
from quillan.assignment_summary_context import relative_path_for
from quillan.work_paths import (
    QuillanWorkPathError,
    assignment_review_report_path,
    preflight_work_file_destination,
    quillan_work_ref,
)


class AssignmentReviewReportExportError(Exception):
    """Raised when an assignment review report cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class ExportedAssignmentReviewReport:
    """Information about one generated assignment review PDF."""

    class_id: str
    assignment_id: str
    report_path: Path
    report_relative_path: str
    student_count: int
    standard_count: int
    created_at: str
    overwrote_existing: bool


def assignment_review_report_export_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the canonical assignment-local review-report PDF path."""
    _validate_identifier(class_id, "class_id")
    _validate_identifier(assignment_id, "assignment_id")
    return assignment_review_report_path(
        workspace_root,
        quillan_work_ref(class_id, assignment_id),
    )


def export_assignment_review_report(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedAssignmentReviewReport:
    """Build one reporting snapshot and render its supervisor-ready PDF."""
    normalized_created_at = _normalize_timestamp(created_at)
    try:
        snapshot = build_assignment_reporting_snapshot(
            workspace_root,
            class_id,
            assignment_id,
        )
    except AssignmentReportingSnapshotError as error:
        raise AssignmentReviewReportExportError(str(error)) from error
    return _export_assignment_review_report_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_created_at=normalized_created_at,
    )


def export_assignment_review_report_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedAssignmentReviewReport:
    """Render the PDF from an already-loaded reporting snapshot."""
    return _export_assignment_review_report_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_created_at=_normalize_timestamp(created_at),
    )


def _export_assignment_review_report_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool,
    normalized_created_at: str,
) -> ExportedAssignmentReviewReport:
    try:
        path = assignment_review_report_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        )
        expected = preflight_work_file_destination(
            snapshot.workspace_root,
            quillan_work_ref(snapshot.class_id, snapshot.assignment_id),
            Path("exports") / "assignment_review_report.pdf",
        )
        if path != expected:
            raise AssignmentReviewReportExportError(
                "Assignment review report path is not canonical."
            )
    except (
        OSError,
        RuntimeError,
        ValueError,
        QuillanWorkPathError,
        AssignmentReviewReportExportError,
    ) as error:
        raise AssignmentReviewReportExportError(str(error)) from error

    existed = path.exists()
    if existed and not overwrite:
        raise AssignmentReviewReportExportError(
            f"Assignment review report already exists: {path}. "
            "Use --overwrite to replace it."
        )

    _write_pdf(
        path,
        snapshot,
        normalized_created_at,
        overwrite=overwrite,
    )
    return ExportedAssignmentReviewReport(
        class_id=snapshot.class_id,
        assignment_id=snapshot.assignment_id,
        report_path=path,
        report_relative_path=relative_path_for(path, snapshot.workspace_root),
        student_count=len(snapshot.students),
        standard_count=len(snapshot.focus_standards),
        created_at=normalized_created_at,
        overwrote_existing=existed,
    )


def _write_pdf(
    path: Path,
    snapshot: AssignmentReportingSnapshot,
    created_at: str,
    *,
    overwrite: bool,
) -> None:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise AssignmentReviewReportExportError(
            f"Could not create assignment report directory {parent}: {error}"
        ) from error
    if not parent.is_dir():
        raise AssignmentReviewReportExportError(
            f"Assignment report parent is not a directory: {parent}"
        )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        _render_pdf_to_path(temporary_path, snapshot, created_at)
        if overwrite:
            os.replace(temporary_path, path)
        else:
            os.link(temporary_path, path)
            temporary_path.unlink()
        temporary_path = None
    except FileExistsError as error:
        raise AssignmentReviewReportExportError(
            f"Assignment review report already exists: {path}. "
            "Use --overwrite to replace it."
        ) from error
    except OSError as error:
        raise AssignmentReviewReportExportError(
            f"Could not write assignment review report {path}: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _render_pdf_to_path(
    path: Path,
    snapshot: AssignmentReportingSnapshot,
    created_at: str,
) -> None:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="AssignmentReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AssignmentReportSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#1F2937"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="AssignmentReportStandard",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            spaceBefore=7,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AssignmentReportBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AssignmentReportSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.3,
            leading=9,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=3,
        )
    )
    title_style = cast(ParagraphStyle, styles["AssignmentReportTitle"])
    section_style = cast(ParagraphStyle, styles["AssignmentReportSection"])
    standard_style = cast(ParagraphStyle, styles["AssignmentReportStandard"])
    body_style = cast(ParagraphStyle, styles["AssignmentReportBody"])
    small_style = cast(ParagraphStyle, styles["AssignmentReportSmall"])

    story: list[Any] = [
        Paragraph("Assignment Review Report", title_style),
        _assignment_overview_table(snapshot, created_at, body_style),
        Spacer(1, 0.08 * inch),
        Paragraph(
            "This report summarizes teacher-confirmed state for one Quillan "
            "assignment. Descriptive percentages use rated students only; they "
            "are not Grades or proficiency determinations.",
            small_style,
        ),
        Paragraph("Review and Completion Overview", section_style),
        _completion_overview_table(snapshot, body_style),
        Paragraph("Focus Standard Performance", section_style),
    ]

    for standard, summary in zip(
        snapshot.focus_standards,
        snapshot.standard_summaries,
        strict=True,
    ):
        story.extend(
            _standard_story(
                snapshot,
                standard,
                summary,
                standard_style,
                body_style,
                small_style,
            )
        )

    story.extend(
        [
            PageBreak(),
            Paragraph("Student Detail", section_style),
            Paragraph(
                "Ratings shown below are teacher-entered overall Focus Standard "
                "ratings. Missing ratings remain explicitly unrated.",
                small_style,
            ),
            _student_detail_table(snapshot, body_style, small_style),
            Paragraph("Attention and Data Quality", section_style),
        ]
    )
    story.extend(_attention_story(snapshot, body_style, small_style))
    story.append(Spacer(1, 0.08 * inch))
    story.append(
        Paragraph(
            "Quillan assignment-local reporting - generated from one immutable "
            "reporting snapshot.",
            small_style,
        )
    )

    document = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.6 * inch,
        title="Assignment Review Report",
        author="Quillan",
    )
    document.build(
        story,
        onFirstPage=_draw_footer,
        onLaterPages=_draw_footer,
    )


def _assignment_overview_table(
    snapshot: AssignmentReportingSnapshot,
    created_at: str,
    style: ParagraphStyle,
) -> Table:
    rating_scale = "; ".join(
        f"{level.value} - {level.label}" for level in snapshot.rating_levels
    )
    standards = "<br/>".join(
        _escape_text(_standard_heading(standard))
        for standard in snapshot.focus_standards
    )
    rows = (
        ("Class", snapshot.class_id),
        ("Assignment", snapshot.assignment_title),
        ("Assignment ID", snapshot.assignment_id),
        ("Writing type", snapshot.writing_type.replace("_", " ").title()),
        ("Generated", created_at),
        ("Rating scale", rating_scale),
    )
    data: list[list[Any]] = [
        [
            Paragraph(f"<b>{_escape_text(label)}:</b>", style),
            Paragraph(_escape_text(value), style),
        ]
        for label, value in rows
    ]
    data.append(
        [
            Paragraph("<b>Focus Standards:</b>", style),
            Paragraph(standards or "None configured", style),
        ]
    )
    table = Table(
        data,
        colWidths=(1.25 * inch, 5.65 * inch),
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
            ]
        )
    )
    return table


def _completion_overview_table(
    snapshot: AssignmentReportingSnapshot,
    style: ParagraphStyle,
) -> Table:
    summary = snapshot.assignment_summary
    rows = [
        ("Rostered students", summary.rostered_students),
        ("Unrostered submissions", summary.unrostered_submissions),
        ("Valid submissions", summary.students_with_submissions),
        ("No submission", summary.students_without_submissions),
        ("Valid reviews", summary.students_with_valid_reviews),
        ("Reviewed - ratings complete or later", summary.students_reviewed),
        ("Review in progress", summary.students_in_progress),
        ("Not reviewed", summary.students_not_reviewed),
        (
            "Returned without full standards review",
            summary.students_returned_without_full_review,
        ),
        ("Attention required", summary.attention_required),
        ("Feedback PDF current", summary.feedback_pdf_current),
        ("Feedback PDF stale", summary.feedback_pdf_stale),
        (
            "Feedback PDF missing / unknown",
            summary.feedback_pdf_missing_or_unknown,
        ),
    ]
    midpoint = (len(rows) + 1) // 2
    left = rows[:midpoint]
    right = rows[midpoint:]
    data: list[list[Any]] = []
    for index in range(midpoint):
        left_item = left[index]
        right_item = right[index] if index < len(right) else ("", "")
        data.append(
            [
                Paragraph(_escape_text(left_item[0]), style),
                Paragraph(f"<b>{left_item[1]}</b>", style),
                Paragraph(_escape_text(right_item[0]), style),
                Paragraph(
                    "" if right_item[0] == "" else f"<b>{right_item[1]}</b>",
                    style,
                ),
            ]
        )
    table = Table(
        data,
        colWidths=(2.2 * inch, 0.45 * inch, 2.65 * inch, 0.45 * inch),
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [
                    colors.white,
                    colors.HexColor("#F9FAFB"),
                ]),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
            ]
        )
    )
    return table


def _standard_story(
    snapshot: AssignmentReportingSnapshot,
    standard: ReportingStandard,
    summary: ReportingStandardSummary,
    standard_style: ParagraphStyle,
    body_style: ParagraphStyle,
    small_style: ParagraphStyle,
) -> list[Any]:
    labels = {level.value: level.label for level in snapshot.rating_levels}
    story: list[Any] = [
        Paragraph(_escape_text(_standard_heading(standard)), standard_style),
    ]
    table_data: list[list[Any]] = [
        [
            Paragraph("<b>Rating</b>", body_style),
            Paragraph("<b>Count</b>", body_style),
            Paragraph("<b>% of rated students</b>", body_style),
        ]
    ]
    for value, count in summary.rating_counts:
        percent = (
            "-"
            if summary.rated_count == 0
            else f"{(count / summary.rated_count) * 100.0:.1f}%"
        )
        label = labels.get(value)
        rendered = str(value) if label is None else f"{value} - {label}"
        table_data.append(
            [
                Paragraph(_escape_text(rendered), body_style),
                Paragraph(str(count), body_style),
                Paragraph(percent, body_style),
            ]
        )
    table = Table(
        table_data,
        colWidths=(3.7 * inch, 0.8 * inch, 1.75 * inch),
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    story.append(
        Paragraph(
            "Rated denominator: "
            f"{summary.rated_count}; unrated: {summary.unrated_count}; "
            "returned without full review: "
            f"{summary.returned_without_full_review_count}; "
            "excluded because of invalid/attention-required state: "
            f"{summary.excluded_invalid_or_attention_count}.",
            small_style,
        )
    )
    warnings = tuple(
        dict.fromkeys(
            (
                *summary.warnings,
                *(("standard_metadata_missing",) if standard.metadata_missing else ()),
            )
        )
    )
    if warnings:
        story.append(
            Paragraph(
                "<b>Interpretation note:</b> "
                + _escape_text(", ".join(_friendly_warning(item) for item in warnings)),
                small_style,
            )
        )
    story.append(Spacer(1, 0.06 * inch))
    return story


def _student_detail_table(
    snapshot: AssignmentReportingSnapshot,
    body_style: ParagraphStyle,
    small_style: ParagraphStyle,
) -> Table:
    data: list[list[Any]] = [
        [
            Paragraph("<b>Student</b>", body_style),
            Paragraph("<b>Review status</b>", body_style),
            Paragraph("<b>Minimum requirements</b>", body_style),
            Paragraph("<b>Focus Standard ratings</b>", body_style),
        ]
    ]
    for student in snapshot.students:
        identity = (
            f"{_escape_text(student.display_name)}"
            f"<br/><font size='7'>ID: {_escape_text(student.student_id)}</font>"
        )
        ratings = _student_ratings(snapshot, student)
        data.append(
            [
                Paragraph(identity, body_style),
                Paragraph(_escape_text(_review_status(student)), body_style),
                Paragraph(_escape_text(_minimum_requirements(student)), body_style),
                Paragraph(ratings, small_style),
            ]
        )
    table = Table(
        data,
        colWidths=(1.45 * inch, 1.35 * inch, 1.35 * inch, 2.85 * inch),
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#F9FAFB"),
                ]),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _student_ratings(
    snapshot: AssignmentReportingSnapshot,
    student: ReportingStudent,
) -> str:
    if student.returned_without_full_review is True:
        return "Not applicable - returned without full standards review"
    ratings = {
        rating.standard_id: rating
        for rating in student.overall_standard_ratings
    }
    lines: list[str] = []
    for standard in snapshot.focus_standards:
        rating = ratings.get(standard.standard_id)
        heading = standard.display_code or standard.standard_id
        if rating is None:
            rendered = "Unrated"
        elif rating.label is None:
            rendered = str(rating.value)
        else:
            rendered = f"{rating.value} - {rating.label}"
        lines.append(
            f"<b>{_escape_text(heading)}:</b> {_escape_text(rendered)}"
        )
    return "<br/>".join(lines) if lines else "No Focus Standards configured"


def _attention_story(
    snapshot: AssignmentReportingSnapshot,
    body_style: ParagraphStyle,
    small_style: ParagraphStyle,
) -> list[Any]:
    counts: dict[str, int] = {}
    for student in snapshot.students:
        for warning in dict.fromkeys(
            (
                *student.warnings,
                *student.feedback_pdf.warnings,
                *student.feedback_markdown.warnings,
            )
        ):
            counts[warning] = counts.get(warning, 0) + 1

    story: list[Any] = []
    if not counts and not snapshot.warnings:
        story.append(
            Paragraph(
                "No assignment-level data-quality warnings were detected.",
                body_style,
            )
        )
        return story

    if counts:
        data: list[list[Any]] = [
            [
                Paragraph("<b>Condition</b>", body_style),
                Paragraph("<b>Students affected</b>", body_style),
            ]
        ]
        for warning, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            data.append(
                [
                    Paragraph(_escape_text(_friendly_warning(warning)), body_style),
                    Paragraph(str(count), body_style),
                ]
            )
        table = Table(
            data,
            colWidths=(5.65 * inch, 1.2 * inch),
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    assignment_only = [
        warning for warning in snapshot.warnings if warning not in counts
    ]
    if assignment_only:
        story.append(Spacer(1, 0.05 * inch))
        story.append(
            Paragraph(
                "<b>Assignment-level notes:</b> "
                + _escape_text(
                    ", ".join(
                        _friendly_warning(warning)
                        for warning in assignment_only
                    )
                ),
                small_style,
            )
        )
    return story


def _review_status(student: ReportingStudent) -> str:
    if _student_attention(student):
        return "Needs attention"
    if student.returned_without_full_review is True:
        return "Returned without full standards review"
    if not student.review_valid:
        return "Not reviewed"
    state = student.review_state or "not_started"
    labels = {
        "not_started": "Not reviewed",
        "requirements_checked": "Requirements checked",
        "observations_in_progress": "Observations in progress",
        "observations_complete": "Observations complete",
        "ratings_complete": "Ratings complete",
        "feedback_composed": "Feedback composed",
        "ready_for_export": "Ready for export",
        "exported": "Exported",
    }
    return labels.get(state, state.replace("_", " ").title())


def _minimum_requirements(student: ReportingStudent) -> str:
    if student.returned_without_full_review is True:
        return "Not met - returned"
    status = student.minimum_requirement_status
    if status is None:
        return "Not checked"
    labels = {
        "met": "Met",
        "not_met": "Not met",
        "not_checked": "Not checked",
        "unmet_continue_review": "Not met - review continued",
        "returned_without_full_review": "Not met - returned",
    }
    return labels.get(status, status.replace("_", " ").title())


def _student_attention(student: ReportingStudent) -> bool:
    attention = {
        "invalid_submission",
        "invalid_review",
        "identity_mismatch",
        "unsafe_path",
        "orphan_review",
    }
    return bool(attention.intersection(student.warnings))


def _standard_heading(standard: ReportingStandard) -> str:
    if standard.display_code and standard.display_name:
        return f"{standard.display_code} - {standard.display_name}"
    return standard.display_code or standard.standard_id


def _friendly_warning(value: str) -> str:
    labels = {
        "missing_submission": "Missing submission",
        "missing_review": "Missing review",
        "invalid_submission": "Invalid submission",
        "invalid_review": "Invalid review",
        "identity_mismatch": "Record identity mismatch",
        "unsafe_path": "Unsafe or invalid managed path",
        "orphan_review": "Review record without a valid submission",
        "unrostered_submission": "Submission for a student not in the roster",
        "rating_for_non_assignment_standard": (
            "Rating references a standard outside this assignment"
        ),
        "unknown_rating_value": "Rating value is outside the configured scale",
        "standard_metadata_missing": "Focus Standard display metadata is missing",
        "feedback_pdf_stale": "Feedback PDF is stale",
        "feedback_markdown_stale": "Feedback Markdown is stale",
        "feedback_pdf_file_missing": "Feedback PDF metadata points to a missing file",
        "feedback_markdown_file_missing": (
            "Feedback Markdown metadata points to a missing file"
        ),
    }
    return labels.get(value, value.replace("_", " ").capitalize())


def _escape_text(value: object) -> str:
    return html.escape(str(value), quote=False)


def _draw_footer(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(
        document.leftMargin,
        0.32 * inch,
        "Quillan assignment review report",
    )
    canvas.drawRightString(
        letter[0] - document.rightMargin,
        0.32 * inch,
        f"Page {document.page}",
    )
    canvas.restoreState()


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise AssignmentReviewReportExportError(
                "created_at datetime must be timezone-aware."
            )
        return value.isoformat()
    if not isinstance(value, str):
        raise AssignmentReviewReportExportError(
            "created_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise AssignmentReviewReportExportError(
            "created_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AssignmentReviewReportExportError(
            "created_at must be a timezone-aware ISO 8601 string."
        )
    return value


def _validate_identifier(value: str, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise AssignmentReviewReportExportError(str(error)) from error

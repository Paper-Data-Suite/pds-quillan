"""Student-facing feedback exports from canonical Quillan review records."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from pds_core.classes import load_class_roster
from pds_core.rosters import RosterError, student_display_name
from pds_core.standards import StandardsValidationError, find_standard_definition
from pds_core.standards_selection import (
    load_standards_for_selection,
    resolve_standard_selection,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from quillan.review_record import (
    ReviewRecordError,
    validate_review_record,
)
from quillan.review_record_paths import (
    ReviewRecordPathError,
    persist_quillan_review_record,
)
from quillan.record_context import (
    MissingReviewError,
    MissingSubmissionError,
    QuillanRecordContextError,
    ReviewLoadingPolicy,
    load_quillan_student_review_context,
    mutable_json_copy,
)
from quillan.submission_guidance import missing_submission_guidance
from quillan.work_paths import (
    QuillanWorkPathError,
    feedback_markdown_path,
    feedback_pdf_path,
    preflight_work_file_destination,
    quillan_work_ref,
)


class FeedbackExportError(Exception):
    """Raised when student-facing feedback cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class ExportedFeedback:
    """Information about one generated student-facing feedback artifact."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    feedback_path: Path
    feedback_relative_path: str
    included_comment_count: int
    score_count: int
    created_at: str
    overwrote_existing: bool


@dataclass(frozen=True, slots=True)
class ExportedFeedbackPdf:
    """Information about one generated student-facing PDF feedback artifact."""

    class_id: str
    assignment_id: str
    student_id: str
    student_display_name: str
    assignment_title: str
    review_record_path: Path
    review_record_relative_path: str
    feedback_pdf_path: Path
    feedback_pdf_relative_path: str
    feedback_markdown_path: Path | None
    feedback_markdown_relative_path: str | None
    included_standard_rating_count: int
    included_comment_count: int
    included_observation_count: int
    created_at: str
    overwrote_existing: bool


@dataclass(frozen=True, slots=True)
class _StudentFeedback:
    class_id: str
    assignment_id: str
    student_id: str
    student_display_name: str
    assignment_title: str
    class_display: str
    created_at: str
    ratings: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    standard_sections: list[_FocusStandardFeedbackSection]
    returned_work: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class _StandardDisplay:
    standard_id: str
    code: str | None
    short_name: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class _FocusStandardFeedbackSection:
    display: _StandardDisplay
    rating: dict[str, Any] | None
    comments: list[dict[str, Any]]
    observations: list[dict[str, Any]]


def feedback_export_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical student-facing Markdown feedback export path."""
    return feedback_markdown_path(
        workspace_root, quillan_work_ref(class_id, assignment_id), student_id
    )


def feedback_pdf_export_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical student-facing PDF feedback export path."""
    return feedback_pdf_path(
        workspace_root, quillan_work_ref(class_id, assignment_id), student_id
    )


def export_student_feedback(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedFeedback:
    """Generate student-facing Markdown from one canonical review record."""
    normalized_created_at = _normalize_timestamp(created_at)
    context = _load_export_context(
        workspace_root, class_id, assignment_id, student_id, normalized_created_at
    )
    output_path = feedback_export_path(
        context["workspace_root"], class_id, assignment_id, student_id
    )
    _preflight_feedback_destination(
        context["workspace_root"], class_id, assignment_id, student_id, output_path
    )
    feedback = _assemble_student_feedback(context)
    markdown = _render_feedback_markdown(feedback)
    included_comments = feedback.comments
    ratings = feedback.ratings
    overwrote_existing = output_path.exists()
    if overwrote_existing and not overwrite:
        raise FeedbackExportError(
            f"Feedback export already exists: {output_path}. "
            "Use --overwrite to replace it."
        )

    _write_feedback(output_path, markdown, overwrite=overwrite)
    return ExportedFeedback(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        feedback_path=output_path,
        feedback_relative_path=_workspace_relative_path(
            output_path, context["workspace_root"], "feedback"
        ),
        included_comment_count=len(included_comments),
        score_count=len(ratings),
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def export_student_feedback_pdf(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
    include_markdown_companion: bool = False,
) -> ExportedFeedbackPdf:
    """Generate student-facing PDF feedback from one canonical review record."""
    normalized_created_at = _normalize_timestamp(created_at)
    context = _load_export_context(
        workspace_root, class_id, assignment_id, student_id, normalized_created_at
    )
    pdf_path = feedback_pdf_export_path(
        context["workspace_root"], class_id, assignment_id, student_id
    )
    markdown_path = (
        feedback_export_path(context["workspace_root"], class_id, assignment_id, student_id)
        if include_markdown_companion
        else None
    )
    _preflight_feedback_destination(
        context["workspace_root"], class_id, assignment_id, student_id, pdf_path
    )
    if markdown_path is not None:
        _preflight_feedback_destination(
            context["workspace_root"],
            class_id,
            assignment_id,
            student_id,
            markdown_path,
        )
    existing_paths = [
        path for path in (pdf_path, markdown_path) if path is not None and path.exists()
    ]
    overwrote_existing = bool(existing_paths)
    if existing_paths and not overwrite:
        joined = ", ".join(str(path) for path in existing_paths)
        raise FeedbackExportError(
            f"Feedback export already exists: {joined}. "
            "Use --overwrite to replace it."
        )

    feedback = _assemble_student_feedback(context)
    _write_feedback_pdf(pdf_path, feedback, overwrite=overwrite)
    if markdown_path is not None:
        _write_feedback(
            markdown_path,
            _render_feedback_markdown(feedback),
            overwrite=overwrite,
        )
    _update_export_metadata(
        context,
        created_at=normalized_created_at,
        feedback_pdf_path=pdf_path,
        feedback_markdown_path=markdown_path,
    )

    markdown_relative_path = (
        _workspace_relative_path(markdown_path, context["workspace_root"], "feedback")
        if markdown_path is not None
        else None
    )
    return ExportedFeedbackPdf(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        student_display_name=feedback.student_display_name,
        assignment_title=feedback.assignment_title,
        review_record_path=context["record_path"],
        review_record_relative_path=_workspace_relative_path(
            context["record_path"], context["workspace_root"], "review record"
        ),
        feedback_pdf_path=pdf_path,
        feedback_pdf_relative_path=_workspace_relative_path(
            pdf_path, context["workspace_root"], "feedback PDF"
        ),
        feedback_markdown_path=markdown_path,
        feedback_markdown_relative_path=markdown_relative_path,
        included_standard_rating_count=len(feedback.ratings),
        included_comment_count=len(feedback.comments),
        included_observation_count=len(feedback.observations),
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def _load_export_context(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    created_at: str,
) -> dict[str, Any]:
    try:
        work_ref = quillan_work_ref(class_id, assignment_id)
        loaded = load_quillan_student_review_context(
            workspace_root,
            work_ref,
            student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_REQUIRED,
        )
    except MissingSubmissionError as error:
        raise FeedbackExportError(missing_submission_guidance()) from error
    except MissingReviewError as error:
        raise FeedbackExportError(
            "Review record does not exist for "
            f"class={class_id}, assignment={assignment_id}, student={student_id}."
        ) from error
    except (OSError, RuntimeError, ValueError, QuillanRecordContextError) as error:
        raise FeedbackExportError(str(error)) from error
    assert loaded.review is not None
    resolved_workspace_root = loaded.paths.workspace_root
    record_path = loaded.paths.review_record_path
    return {
        "record_context": loaded,
        "workspace_root": resolved_workspace_root,
        "work_ref": work_ref,
        "manifest_path": loaded.paths.submission_manifest_path,
        "record_path": record_path,
        "manifest": mutable_json_copy(loaded.submission),
        "review": mutable_json_copy(loaded.review),
        "assignment": mutable_json_copy(loaded.assignment_context.assignment),
        "created_at": created_at,
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }


def _assemble_student_feedback(context: dict[str, Any]) -> _StudentFeedback:
    review = context["review"]
    assignment = context["assignment"]
    class_id = context["class_id"]
    assignment_id = context["assignment_id"]
    student_id = context["student_id"]
    if review["review_state"] == "returned_without_full_review":
        unmet_requirements = _validated_returned_work_requirements(
            review,
            assignment,
        )
        returned_work = {
            "outcome": review["minimum_requirement_outcome"],
            "unmet_requirements": unmet_requirements,
        }
        ratings: list[dict[str, Any]] = []
        comments: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
    else:
        ratings = _included_standard_ratings(review)
        comments = _included_feedback_comments(review)
        observations = _included_review_unit_observations(review)
        returned_work = None
    ratings_with_labels = _with_rating_labels(ratings, assignment)
    return _StudentFeedback(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        student_display_name=_student_name(context["workspace_root"], class_id, student_id),
        assignment_title=_assignment_title(assignment, assignment_id),
        class_display=class_id,
        created_at=context["created_at"],
        ratings=ratings_with_labels,
        comments=comments,
        observations=observations,
        standard_sections=_focus_standard_sections(
            context["workspace_root"],
            assignment,
            ratings_with_labels,
            comments,
            observations,
        ),
        returned_work=returned_work,
    )


def _focus_standard_sections(
    workspace_root: Path,
    assignment: dict[str, Any] | None,
    ratings: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[_FocusStandardFeedbackSection]:
    ordered_ids = list(assignment.get("focus_standard_ids", [])) if assignment else []
    selected_ids = [
        str(item["standard_id"])
        for items in (ratings, comments, observations)
        for item in items
    ]
    for standard_id in selected_ids:
        if standard_id not in ordered_ids:
            ordered_ids.append(standard_id)
    displays = _standard_display_map(workspace_root, ordered_ids)
    ratings_by_id = {str(item["standard_id"]): item for item in ratings}
    return [
        _FocusStandardFeedbackSection(
            display=displays[standard_id],
            rating=ratings_by_id.get(standard_id),
            comments=[item for item in comments if item["standard_id"] == standard_id],
            observations=[
                item for item in observations if item["standard_id"] == standard_id
            ],
        )
        for standard_id in ordered_ids
        if standard_id in selected_ids
    ]


def _standard_display_map(
    workspace_root: Path, standard_ids: list[str]
) -> dict[str, _StandardDisplay]:
    fallback = {
        standard_id: _StandardDisplay(standard_id, None, None, None)
        for standard_id in standard_ids
    }
    try:
        library = load_standards_for_selection(workspace_root)
    except (OSError, StandardsValidationError, ValueError):
        return fallback
    for standard_id in standard_ids:
        try:
            item = resolve_standard_selection(library, standard_id)
        except (StandardsValidationError, ValueError):
            continue
        definition = find_standard_definition(library, standard_id)
        fallback[standard_id] = _StandardDisplay(
            standard_id=standard_id,
            code=_non_empty(item.code),
            short_name=_non_empty(item.short_name),
            description=(
                _non_empty(definition.description) if definition is not None else None
            ),
        )
    return fallback


def _render_feedback_markdown(feedback: _StudentFeedback) -> str:
    if feedback.returned_work is not None:
        return _render_returned_work_markdown(
            class_id=feedback.class_id,
            assignment_id=feedback.assignment_id,
            student_id=feedback.student_id,
            created_at=feedback.created_at,
            outcome=feedback.returned_work["outcome"],
            unmet_requirements=feedback.returned_work["unmet_requirements"],
        )
    return _render_markdown(
        class_id=feedback.class_id,
        assignment_id=feedback.assignment_id,
        student_id=feedback.student_id,
        created_at=feedback.created_at,
        standard_sections=feedback.standard_sections,
    )


def _render_markdown(
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    created_at: str,
    standard_sections: list[_FocusStandardFeedbackSection],
) -> str:
    lines = [
        "# Feedback",
        "",
        f"Class: {_plain_text(class_id)}",
        f"Assignment: {_plain_text(assignment_id)}",
        f"Student: {_plain_text(student_id)}",
        f"Generated: {_plain_text(created_at)}",
        "",
        "---",
        "",
        "## Focus Standard Feedback",
        "",
    ]
    if not standard_sections:
        lines.append("No Focus Standard feedback selected.")
    for index, section in enumerate(standard_sections):
        if index:
            lines.extend(["", "---", ""])
        lines.extend([f"### {_plain_text(_standard_heading(section.display))}", ""])
        if section.display.description:
            lines.extend(
                ["Standard:", _plain_text(section.display.description), ""]
            )
        if section.rating:
            value = _format_number(section.rating["rating"])
            label = section.rating.get("rating_label")
            label_suffix = f" ({_plain_text(label)})" if label else ""
            lines.extend([f"Rating: {value}{label_suffix}", ""])
            if section.rating.get("rationale"):
                lines.extend(
                    ["Rationale:", _plain_text(section.rating["rationale"]), ""]
                )
        if section.comments:
            lines.append("Feedback:")
            lines.extend(f"- {_plain_text(item['text'])}" for item in section.comments)
            lines.append("")
        if section.observations:
            lines.append("Review-unit observations:")
            for observation in section.observations:
                unit = observation.get("unit_label") or "Review unit"
                rationale = _non_empty(observation.get("rationale"))
                rendered = f"- {_plain_text(unit)}"
                if rationale:
                    rendered += f": {_plain_text(rationale)}"
                lines.append(rendered)
    lines.append("")
    return "\n".join(lines)


def _standard_heading(display: _StandardDisplay) -> str:
    if display.code and display.short_name:
        return f"{display.code} — {display.short_name}"
    return display.code or display.standard_id


def _render_returned_work_markdown(
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    created_at: str,
    outcome: dict[str, Any],
    unmet_requirements: list[dict[str, Any]],
) -> str:
    lines = [
        "# Returned for Revision",
        "",
        f"Class: {_plain_text(class_id)}",
        f"Assignment: {_plain_text(assignment_id)}",
        f"Student: {_plain_text(student_id)}",
        f"Generated: {_plain_text(created_at)}",
        "",
        (
            "This submission was returned without full standards review because "
            "minimum requirements were not met."
        ),
        "",
        "## Minimum Requirements Not Met",
        "",
    ]
    for requirement in unmet_requirements:
        lines.append(f"- {_plain_text(requirement['label'])}")
        lines.append(f"  Expected: {_plain_text(requirement['expected'])}")
        if note := _non_empty(requirement.get("teacher_note")):
            lines.append(f"  Teacher note: {_plain_text(note)}")
    lines.extend(
        [
            "",
            "## Return Note",
            "",
            _plain_text(outcome["teacher_note"]),
            "",
            "No full standards ratings were completed for this submission.",
            "",
        ]
    )
    return "\n".join(lines)


def _included_feedback_comments(review: dict[str, Any]) -> list[dict[str, Any]]:
    included: list[dict[str, Any]] = []
    for standard_feedback in review["feedback"]["standard_feedback"]:
        for comment in standard_feedback["comments"]:
            if comment["include_in_feedback"]:
                rendered = dict(comment)
                rendered["standard_id"] = standard_feedback["standard_id"]
                included.append(rendered)
    return included


def _included_standard_ratings(review: dict[str, Any]) -> list[dict[str, Any]]:
    if not review["feedback"]["include_overall_standard_ratings"]:
        return []
    feedback_by_standard = {
        item["standard_id"]: item for item in review["feedback"]["standard_feedback"]
    }
    included: list[dict[str, Any]] = []
    for rating in review["overall_standard_ratings"]:
        standard_feedback = feedback_by_standard.get(rating["standard_id"])
        if standard_feedback is None:
            if not rating["include_in_feedback"]:
                continue
            included.append(rating)
            continue
        if not standard_feedback["include_overall_rating"]:
            continue
        rendered = dict(rating)
        if not standard_feedback["include_overall_rationale"]:
            rendered["rationale"] = None
        included.append(rendered)
    return included


def _included_review_unit_observations(review: dict[str, Any]) -> list[dict[str, Any]]:
    if not review["feedback"]["include_review_unit_observations"]:
        return []
    selected_by_standard: dict[str, set[str]] = {}
    for standard_feedback in review["feedback"]["standard_feedback"]:
        selected_by_standard[standard_feedback["standard_id"]] = set(
            standard_feedback["included_observation_ids"]
        )
    included: list[dict[str, Any]] = []
    for unit in review["review_units"]:
        for observation in unit["standard_observations"]:
            if observation["observation_id"] not in selected_by_standard.get(
                observation["standard_id"], set()
            ):
                continue
            item = dict(observation)
            item["unit_id"] = unit["unit_id"]
            item["unit_label"] = unit["label"]
            included.append(item)
    return included


def _validated_returned_work_requirements(
    review: dict[str, Any],
    assignment: dict[str, Any],
) -> list[dict[str, Any]]:
    outcome = review["minimum_requirement_outcome"]
    if outcome["returned_without_full_review"] is not True:
        raise FeedbackExportError(
            "Returned-work export requires "
            "minimum_requirement_outcome.returned_without_full_review to be true."
        )
    if not _non_empty(outcome.get("teacher_note")):
        raise FeedbackExportError(
            "Returned-work export requires a non-empty outcome teacher note."
        )

    configured_keys = _configured_requirement_keys(assignment)
    unmet_requirements = [
        check
        for check in review["minimum_requirement_checks"]
        if check["requirement_key"] in configured_keys and check["met"] is False
    ]
    if not unmet_requirements:
        raise FeedbackExportError(
            "Returned-work export requires at least one checked configured "
            "minimum requirement marked not met."
        )
    return unmet_requirements


def _write_feedback_pdf(path: Path, feedback: _StudentFeedback, *, overwrite: bool) -> None:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise FeedbackExportError(
            f"Could not create feedback export directory {parent}: {error}"
        ) from error
    if not parent.is_dir():
        raise FeedbackExportError(
            f"Feedback export parent is not a directory: {parent}"
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
        _render_pdf_to_path(temporary_path, feedback)
        if overwrite:
            os.replace(temporary_path, path)
        else:
            os.link(temporary_path, path)
            temporary_path.unlink()
        temporary_path = None
    except FileExistsError as error:
        raise FeedbackExportError(
            f"Feedback export already exists: {path}. "
            "Use --overwrite to replace it."
        ) from error
    except OSError as error:
        raise FeedbackExportError(
            f"Could not write feedback export {path}: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _render_pdf_to_path(path: Path, feedback: _StudentFeedback) -> None:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="FeedbackTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FeedbackSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FeedbackBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            spaceAfter=5,
        )
    )
    title_style = cast(ParagraphStyle, styles["FeedbackTitle"])
    section_style = cast(ParagraphStyle, styles["FeedbackSection"])
    body_style = cast(ParagraphStyle, styles["FeedbackBody"])
    story: list[Any] = []
    title = "Returned for Revision" if feedback.returned_work else "Student Feedback"
    story.append(Paragraph(title, title_style))
    story.append(_metadata_table(feedback, body_style))
    story.append(Spacer(1, 0.08 * inch))
    if feedback.returned_work is not None:
        _append_returned_work_pdf(story, section_style, body_style, feedback)
    else:
        _append_standard_feedback_pdf(story, section_style, body_style, feedback)
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        Paragraph(
            "Quillan student feedback export",
            body_style,
        )
    )

    document = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=title,
    )
    document.build(story, onFirstPage=_draw_pdf_footer, onLaterPages=_draw_pdf_footer)


def _metadata_table(feedback: _StudentFeedback, style: ParagraphStyle) -> Table:
    data = [
        ("Student", feedback.student_display_name),
        ("Student ID", feedback.student_id),
        ("Class", feedback.class_display),
        ("Assignment", feedback.assignment_title),
        ("Assignment ID", feedback.assignment_id),
        ("Generated", feedback.created_at),
    ]
    table = Table(
        [
            [
                Paragraph(f"<b>{_escape_pdf_text(label)}:</b>", style),
                Paragraph(_escape_pdf_text(value), style),
            ]
            for label, value in data
        ],
        colWidths=(1.15 * inch, 5.0 * inch),
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#333333")),
            ]
        )
    )
    return table


def _append_standard_feedback_pdf(
    story: list[Any],
    section_style: ParagraphStyle,
    body_style: ParagraphStyle,
    feedback: _StudentFeedback,
) -> None:
    story.append(Paragraph("Focus Standard Feedback", section_style))
    if not feedback.standard_sections:
        story.append(Paragraph("No Focus Standard feedback selected.", body_style))
    for index, section in enumerate(feedback.standard_sections):
        if index:
            story.append(Spacer(1, 0.08 * inch))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
            story.append(Spacer(1, 0.04 * inch))
        story.append(
            Paragraph(
                f"<b>{_escape_pdf_text(_standard_heading(section.display))}</b>",
                section_style,
            )
        )
        if section.display.description:
            story.append(Paragraph("<b>Standard:</b>", body_style))
            story.append(
                Paragraph(_escape_pdf_text(section.display.description), body_style)
            )
        if section.rating:
            value = _format_number(section.rating["rating"])
            label = section.rating.get("rating_label")
            label_suffix = f" ({_plain_text(label)})" if label else ""
            story.append(
                Paragraph(
                    f"<b>Rating:</b> {_escape_pdf_text(value + label_suffix)}",
                    body_style,
                )
            )
            if section.rating.get("rationale"):
                story.append(
                    Paragraph(
                        f"<b>Rationale:</b> "
                        f"{_escape_pdf_text(section.rating['rationale'])}",
                        body_style,
                    )
                )
        if section.comments:
            story.append(Paragraph("<b>Feedback:</b>", body_style))
        for comment in section.comments:
            story.append(
                Paragraph(f"• {_escape_pdf_text(comment['text'])}", body_style)
            )
        if section.observations:
            story.append(Paragraph("<b>Review-unit observations:</b>", body_style))
        for observation in section.observations:
            unit = observation.get("unit_label") or "Review unit"
            text = f"• {_plain_text(unit)}"
            if observation.get("rationale"):
                text += f": {_plain_text(observation['rationale'])}"
            story.append(Paragraph(_escape_pdf_text(text), body_style))


def _append_returned_work_pdf(
    story: list[Any],
    section_style: ParagraphStyle,
    body_style: ParagraphStyle,
    feedback: _StudentFeedback,
) -> None:
    assert feedback.returned_work is not None
    story.append(
        Paragraph(
            "This submission was returned without full standards review because "
            "minimum requirements were not met.",
            body_style,
        )
    )
    story.append(Paragraph("Minimum Requirements Not Met", section_style))
    for requirement in feedback.returned_work["unmet_requirements"]:
        story.append(
            Paragraph(
                f"<b>{_escape_pdf_text(requirement['label'])}</b>",
                body_style,
            )
        )
        story.append(
            Paragraph(
                f"Expected: {_escape_pdf_text(requirement['expected'])}",
                body_style,
            )
        )
        if note := _non_empty(requirement.get("teacher_note")):
            story.append(
                Paragraph(f"Teacher note: {_escape_pdf_text(note)}", body_style)
            )
    story.append(Paragraph("Return Note", section_style))
    story.append(
        Paragraph(
            _escape_pdf_text(feedback.returned_work["outcome"]["teacher_note"]),
            body_style,
        )
    )
    story.append(
        Paragraph(
            "No full Focus Standard ratings were completed for this submission.",
            body_style,
        )
    )


def _draw_pdf_footer(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(0.65 * inch, 0.35 * inch, "Quillan student feedback export")
    canvas.drawRightString(
        letter[0] - 0.65 * inch,
        0.35 * inch,
        f"Page {document.page}",
    )
    canvas.restoreState()


def _update_export_metadata(
    context: dict[str, Any],
    *,
    created_at: str,
    feedback_pdf_path: Path,
    feedback_markdown_path: Path | None,
) -> None:
    review = dict(context["review"])
    review["exports"] = dict(review["exports"])
    review["exports"]["feedback_pdf"] = {
        "path": _workspace_relative_path(
            feedback_pdf_path, context["workspace_root"], "feedback PDF"
        ),
        "generated_at": created_at,
        "source_review_updated_at": created_at,
        "module_details": {},
    }
    if feedback_markdown_path is not None:
        review["exports"]["feedback_markdown"] = {
            "path": _workspace_relative_path(
                feedback_markdown_path, context["workspace_root"], "feedback Markdown"
            ),
            "generated_at": created_at,
            "source_review_updated_at": created_at,
            "module_details": {},
        }
    # Returned work remains a distinct terminal workflow state under the v2
    # contract, even when its return feedback has been exported.
    if review["review_state"] != "returned_without_full_review":
        review["review_state"] = "exported"
    review["updated_at"] = created_at
    try:
        validate_review_record(review)
        persist_quillan_review_record(context["record_context"], review)
    except (ReviewRecordError, ReviewRecordPathError, OSError, ValueError) as error:
        raise FeedbackExportError(f"Could not update review export metadata: {error}") from error


def _student_name(workspace_root: Path, class_id: str, student_id: str) -> str:
    try:
        roster = load_class_roster(workspace_root, class_id)
    except (RosterError, OSError):
        return student_id
    for student in roster.students:
        if student.student_id == student_id:
            return student_display_name(student)
    return student_id


def _assignment_title(assignment: dict[str, Any] | None, assignment_id: str) -> str:
    if assignment is None:
        return assignment_id
    return _plain_text(assignment["title"])


def _with_rating_labels(
    ratings: list[dict[str, Any]], assignment: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if assignment is None:
        return ratings
    labels = {
        level["value"]: level["label"]
        for level in assignment["rating_scale"]["levels"]
    }
    rendered: list[dict[str, Any]] = []
    for rating in ratings:
        item = dict(rating)
        if item["rating"] in labels:
            item["rating_label"] = labels[item["rating"]]
        rendered.append(item)
    return rendered


def _configured_requirement_keys(assignment: dict[str, Any]) -> set[str]:
    basic_requirements = assignment.get("basic_requirements")
    if not isinstance(basic_requirements, dict):
        return set()
    keys: set[str] = set()
    for key in (
        "paragraphs_min",
        "paragraphs_max",
        "word_count_min",
        "word_count_max",
    ):
        if key in basic_requirements:
            keys.add(key)
    required_elements = basic_requirements.get("required_elements")
    if isinstance(required_elements, list):
        for element in required_elements:
            if isinstance(element, str) and element.strip():
                keys.add(f"required_elements:{element.strip()}")
    return keys


def _write_feedback(path: Path, content: str, *, overwrite: bool) -> None:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise FeedbackExportError(
            f"Could not create feedback export directory {parent}: {error}"
        ) from error
    if not parent.is_dir():
        raise FeedbackExportError(
            f"Feedback export parent is not a directory: {parent}"
        )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        if overwrite:
            os.replace(temporary_path, path)
        else:
            os.link(temporary_path, path)
            temporary_path.unlink()
        temporary_path = None
    except FileExistsError as error:
        raise FeedbackExportError(
            f"Feedback export already exists: {path}. "
            "Use --overwrite to replace it."
        ) from error
    except OSError as error:
        raise FeedbackExportError(
            f"Could not write feedback export {path}: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _preflight_feedback_destination(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    path: Path,
) -> None:
    work_ref = quillan_work_ref(class_id, assignment_id)
    filename = "feedback.pdf" if path.suffix == ".pdf" else "feedback.md"
    try:
        expected = preflight_work_file_destination(
            workspace_root,
            work_ref,
            Path("submissions") / student_id / "exports" / filename,
        )
    except QuillanWorkPathError as error:
        raise FeedbackExportError(str(error)) from error
    if path != expected:
        raise FeedbackExportError("Feedback export path is not canonical.")


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise FeedbackExportError("created_at datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise FeedbackExportError(
            "created_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise FeedbackExportError(
            "created_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FeedbackExportError(
            "created_at must be a timezone-aware ISO 8601 string."
        )
    return value


def _validate_identity(
    record: dict[str, Any],
    *,
    record_name: str,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    requested = {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }
    for field, expected in requested.items():
        actual = record[field]
        if actual != expected:
            raise FeedbackExportError(
                f"{record_name} {field} is {actual!r}, expected {expected!r}."
            )


def _plain_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _escape_pdf_text(value: object) -> str:
    text = _plain_text(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _non_empty(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _format_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    return format(value, "g")


def _workspace_relative_path(
    path: Path, workspace_root: Path, description: str
) -> str:
    try:
        return path.resolve(strict=False).relative_to(workspace_root).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise FeedbackExportError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error

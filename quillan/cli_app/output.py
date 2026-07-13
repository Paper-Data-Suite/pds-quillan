"""Stable user-facing output formatting for CLI command results."""

from __future__ import annotations

from pathlib import Path

from pds_core.workspace import WorkspaceStatus

from quillan.assignment_submission_assembly import (
    AssignmentSubmissionAssemblyResult,
)
from quillan.class_summary_export import ExportedClassSummary
from quillan.comment_management import (
    CreatedManualReusableComment,
    ReusableCommentInventory,
    ReusableCommentSetStatus,
    ReusableCommentStatus,
)
from quillan.evidence_filing import EvidenceFilingError, RoutedEvidenceFile
from quillan.feedback_export import ExportedFeedback, ExportedFeedbackPdf
from quillan.focus_standard_comments import SavedReusableFocusStandardComment
from quillan.review_feedback import (
    AddedFeedbackComment,
    CompletedFeedbackComposition,
    SelectedReusableFeedbackComment,
    UpdatedStandardFeedbackOptions,
)
from quillan.review_notes import AddedReviewNote
from quillan.review_observations import (
    CompletedReviewUnitObservations,
    UpdatedReviewUnitObservation,
    UpdatedReviewUnits,
)
from quillan.review_ratings import (
    CompletedOverallStandardRatings,
    UpdatedOverallStandardRating,
)
from quillan.route_planning import RouteFailure
from quillan.routing_review import RoutingReviewRecord
from quillan.standards_summary_export import ExportedStandardsSummary
from quillan.student_performance_summary_export import (
    ExportedStudentPerformanceSummary,
)
from quillan.submission_review_opening import OpenedSubmissionReview
from quillan.submission_review_state import UpdatedSubmissionReviewState
from quillan.submission_page_management import (
    ManagedSubmissionPage,
    SubmissionPageContext,
)
from quillan.submission_status import AssignmentSubmissionStatus


def print_reusable_comment_inventory(inventory: ReusableCommentInventory) -> None:
    """Print deterministic reusable-comment list results and invalid files."""
    if not inventory.comments:
        print("No reusable Focus Standard comments matched.")
    for index, comment in enumerate(inventory.comments, start=1):
        if index > 1:
            print()
        print(f"Reusable comment {index}:")
        _print_reusable_comment(comment, include_inspection_fields=False)
    if inventory.invalid_files:
        print("\nInvalid reusable Focus Standard comment sets:")
        for invalid in inventory.invalid_files:
            print(f"- {invalid.relative_path}: {invalid.error}")


def print_reusable_comment_set(result: ReusableCommentSetStatus) -> None:
    """Print one complete reusable-comment source set."""
    print("Reusable Focus Standard comment set:")
    print(f"Comment set ID: {result.comment_set_id}")
    print(f"Title: {result.title}")
    print(f"Description: {result.description}")
    print(f"Standards profile ID: {result.standards_profile_id}")
    print(f"Writing types: {_values(result.writing_types, 'all')}")
    print(f"Grade band: {result.grade_band or 'none'}")
    print(f"Comment count: {len(result.comments)}")
    print(f"Created: {result.created_at}")
    print(f"Updated: {result.updated_at}")
    print(f"Path: {result.relative_path}")
    print(f"Module details: {result.module_details}")
    if not result.comments:
        print("\nComments: none")
    for index, comment in enumerate(result.comments, start=1):
        print(f"\nComment {index}:")
        _print_reusable_comment(comment, include_inspection_fields=True)


def print_created_manual_reusable_comment(
    result: CreatedManualReusableComment,
) -> None:
    """Print the result of creating one manual reusable comment."""
    print("Created manual reusable Focus Standard comment:")
    print(f"Comment set ID: {result.comment_set_id}")
    print(f"Comment ID: {result.comment_id}")
    print(f"Comment set: {'created' if result.set_was_created else 'already existed'}")
    print(f"Standards profile ID: {result.standards_profile_id}")
    print(f"Writing type: {result.writing_type}")
    print(f"Standard ID: {result.standard_id}")
    print(f"Label: {result.label}")
    print(f"Purpose: {result.purpose}")
    print(f"Rating values: {_values(result.rating_values, 'all')}")
    print(f"Teacher tags: {_values(result.teacher_tags, 'none')}")
    print(f"Active: {format_bool(result.active)}")
    print(f"Student-facing: {format_bool(result.student_facing)}")
    print(f"Usage count: {result.times_used}")
    print(f"Path: {result.relative_path}")
    print(f"Created: {result.created_at}")


def _print_reusable_comment(
    comment: ReusableCommentStatus, *, include_inspection_fields: bool
) -> None:
    print(f"Comment set ID: {comment.comment_set_id}")
    print(f"Comment set title: {comment.comment_set_title}")
    print(f"Standards profile ID: {comment.standards_profile_id}")
    print(f"Comment ID: {comment.comment_id}")
    print(f"Standard ID: {comment.standard_id}")
    print(f"Label: {comment.label}")
    print(f"Text: {comment.text}")
    print(f"Purpose: {comment.purpose}")
    print(f"Writing types: {_values(comment.writing_types, 'all')}")
    print(f"Rating values: {_values(comment.rating_values, 'all')}")
    print(f"Teacher tags: {_values(comment.teacher_tags, 'none')}")
    print(f"Usage count: {comment.times_used}")
    print(f"Last used: {comment.last_used_at or 'never'}")
    print(f"Path: {comment.relative_path}")
    if include_inspection_fields:
        print(f"Student-facing: {format_bool(comment.student_facing)}")
        print(f"Active: {format_bool(comment.active)}")
        print(f"Source type: {comment.source.type}")
        print(f"Source class ID: {comment.source.class_id or 'none'}")
        print(f"Source assignment ID: {comment.source.assignment_id or 'none'}")
        print(f"Source student ID: {comment.source.student_id or 'none'}")
        print(f"Source review path: {comment.source.review_path or 'none'}")
        print(
            "Source feedback comment ID: "
            f"{comment.source.feedback_comment_id or 'none'}"
        )
        print(f"Source saved: {comment.source.saved_at}")
        print(f"Created: {comment.created_at}")
        print(f"Updated: {comment.updated_at}")
        print(f"Module details: {comment.module_details}")


def _values(values: tuple[object, ...], empty: str) -> str:
    return ", ".join(str(value) for value in values) if values else empty


def print_opened_submission_review(opened: OpenedSubmissionReview) -> None:
    """Print concise teacher-facing context for opened submission evidence."""
    print("Opened submission evidence for review:")
    print(f"Class: {opened.class_id}")
    print(f"Assignment: {opened.assignment_id}")
    print(f"Student: {opened.student_id}")
    print(f"Submission state: {opened.submission_state}")
    print(f"Pages opened: {len(opened.opened_pages)}")
    for page in opened.opened_pages:
        print(
            f"- Page {page.page_number}: {page.page_state}; "
            f"Evidence: {page.evidence_id}; Path: {page.evidence_relative_path}"
        )
    print(f"Manifest: {opened.manifest_relative_path}")


def print_updated_submission_review_state(
    updated: UpdatedSubmissionReviewState,
) -> None:
    """Print a concise teacher-facing review-state update."""
    print("Updated submission review state:")
    print(f"Class: {updated.class_id}")
    print(f"Assignment: {updated.assignment_id}")
    print(f"Student: {updated.student_id}")
    print(f"Previous state: {updated.previous_state}")
    print(f"New state: {updated.new_state}")
    print(f"Manifest: {updated.manifest_relative_path}")


def print_submission_page_context(context: SubmissionPageContext) -> None:
    """Print manifest-only status for one selected student's pages."""
    print("Submission pages:")
    print(f"Class: {context.class_id}")
    print(f"Assignment: {context.assignment_id}")
    print(f"Student: {context.student_id}")
    print(f"Manifest: {context.manifest_relative_path}")
    print(f"Submission state: {context.submission_state}")
    print(
        "Expected pages: "
        f"{context.expected_pages if context.expected_pages is not None else 'not specified'}"
    )
    print(f"Plain-paper submission: {format_bool(context.plain_paper)}")
    if context.plain_paper:
        print(f"Entry method: {context.plain_paper_entry_method or 'plain-paper manual'}")
        print("Physical paper remains outside Quillan; there are zero digital pages.")
    print(f"Total pages: {len(context.pages)}")
    print(f"Present pages: {context.present_count}")
    print(f"Missing pages: {context.missing_count}")
    print(f"Duplicate pages: {context.duplicate_count}")
    print(f"Needs-rescan pages: {context.needs_rescan_count}")
    print(f"Excluded pages: {context.excluded_count}")
    print(
        "Pages lacking selected evidence: "
        f"{format_page_numbers(context.pages_without_selected_evidence) or 'none'}"
    )
    print(f"Created: {context.created_at}")
    print(f"Updated: {context.updated_at}")
    if not context.pages:
        print("Digital pages: none")
        return
    for page in context.pages:
        print()
        print(f"Page {page.page_number}:")
        print(f"  State: {_teacher_page_state(page.page_state)}")
        print(f"  Selected evidence: {page.selected_evidence_id or 'none'}")
        print(f"  Evidence count: {len(page.evidence)}")
        for evidence in page.evidence:
            print(f"  Evidence {evidence.evidence_id}:")
            print(f"    Role: {evidence.evidence_role}")
            print(f"    State: {evidence.evidence_state}")
            print(f"    Routed path: {evidence.routed_evidence_path}")
            print(
                "    Duplicate number: "
                f"{evidence.duplicate_number if evidence.duplicate_number is not None else 'none'}"
            )
            print(
                "    Retained source present: "
                f"{format_bool(evidence.retained_source_present)}"
            )
            if (
                evidence.pre_exclusion_role is not None
                or evidence.pre_exclusion_state is not None
            ):
                print(
                    "    Pre-exclusion role: "
                    f"{evidence.pre_exclusion_role or 'none'}"
                )
                print(
                    "    Pre-exclusion state: "
                    f"{evidence.pre_exclusion_state or 'none'}"
                )


def print_managed_submission_page(
    result: ManagedSubmissionPage, workspace_root: Path
) -> None:
    """Print one successful page-management mutation."""
    print("Submission page updated:")
    print(f"Class: {result.class_id}")
    print(f"Assignment: {result.assignment_id}")
    print(f"Student: {result.student_id}")
    print(f"Action: {result.action}")
    print(f"Page: {result.page_number}")
    print(f"Previous state: {_teacher_page_state(result.previous_page_state)}")
    print(f"Resulting state: {_teacher_page_state(result.page_state)}")
    print(
        "Previous selected evidence: "
        f"{result.previous_selected_evidence_id or 'none'}"
    )
    print(f"Resulting selected evidence: {result.selected_evidence_id or 'none'}")
    print(f"Evidence records preserved: {result.evidence_count}")
    if result.restore_source is not None:
        print(f"Restore source: {result.restore_source}")
    print(
        "Manifest: "
        f"{workspace_relative_display(result.manifest_path, workspace_root)}"
    )
    print(f"Updated: {result.updated_at}")


def _teacher_page_state(state: str) -> str:
    return {
        "excluded": "excluded from active review",
        "needs_rescan": "needs rescan",
    }.get(state, state)


def print_added_review_note(added: AddedReviewNote) -> None:
    """Print a concise teacher-facing note summary."""
    print("Added teacher note:")
    print(f"Class: {added.class_id}")
    print(f"Assignment: {added.assignment_id}")
    print(f"Student: {added.student_id}")
    print(f"Note: {added.note_id}")
    print(f"Review state: {added.review_state}")
    print(f"Review record: {added.review_record_relative_path}")


def print_updated_review_units(updated: UpdatedReviewUnits) -> None:
    """Print a concise teacher-facing review-unit summary."""
    print("Updated review units:")
    print(f"Class: {updated.class_id}")
    print(f"Assignment: {updated.assignment_id}")
    print(f"Student: {updated.student_id}")
    print(f"Review-unit type: {updated.unit_type}")
    print(f"Previous unit count: {updated.previous_unit_count}")
    print(f"Resulting unit count: {updated.unit_count}")
    print(f"Observations preserved: {updated.observations_preserved}")
    print(f"Observations removed: {updated.observations_removed}")
    print(f"Newly empty units added: {updated.empty_units_added}")
    print(
        "Stale feedback observation references removed: "
        f"{updated.stale_feedback_references_removed}"
    )
    print(f"Review state: {updated.review_state}")
    print(f"Review record: {updated.review_record_relative_path}")
    print(f"Updated: {updated.updated_at}")


def print_updated_review_unit_observation(
    updated: UpdatedReviewUnitObservation,
) -> None:
    """Print a concise teacher-facing observation summary."""
    print("Updated Focus Standard observation:")
    print(f"Class: {updated.class_id}")
    print(f"Assignment: {updated.assignment_id}")
    print(f"Student: {updated.student_id}")
    print(f"Unit: {updated.unit_label} ({updated.unit_id})")
    print(f"Standard: {updated.standard_id}")
    print(f"Observation: {updated.observation_id}")
    print(f"Applicable: {format_bool(updated.applicable)}")
    evidence = "not applicable"
    if updated.evidence_present is not None:
        evidence = format_bool(updated.evidence_present)
    print(f"Evidence present: {evidence}")
    if not updated.applicable:
        rating = "not applicable"
    elif updated.rating is None:
        rating = "none"
    else:
        rating = f"{updated.rating} ({updated.rating_label})"
    print(f"Unit-level rating: {rating}")
    print(f"Rationale: {'present' if updated.rationale is not None else 'none'}")
    print(f"Include in feedback: {format_bool(updated.include_in_feedback)}")
    print(f"Action: {'created' if updated.was_created else 'updated'}")
    print(f"Review state: {updated.review_state}")
    print(f"Review record: {updated.review_record_relative_path}")
    print(f"Updated: {updated.updated_at}")


def print_completed_review_unit_observations(
    completed: CompletedReviewUnitObservations,
) -> None:
    """Print a concise teacher-facing observation-completion summary."""
    print("Marked review-unit observations complete:")
    print(f"Class: {completed.class_id}")
    print(f"Assignment: {completed.assignment_id}")
    print(f"Student: {completed.student_id}")
    print(f"Units: {completed.unit_count}")
    print(f"Observations: {completed.observation_count}")
    print(f"Unobserved unit-standard pairs: {completed.missing_focus_standard_pairs}")
    print(f"Review state: {completed.review_state}")
    print(f"Review record: {completed.review_record_relative_path}")


def print_updated_overall_standard_rating(
    updated: UpdatedOverallStandardRating,
) -> None:
    """Print a concise teacher-facing overall Focus Standard rating summary."""
    print("Updated overall Focus Standard rating:")
    print(f"Class: {updated.class_id}")
    print(f"Assignment: {updated.assignment_id}")
    print(f"Student: {updated.student_id}")
    print(f"Standard: {updated.standard_id}")
    print(f"Rating: {updated.rating} - {updated.rating_label}")
    print(f"Rationale: {'present' if updated.rationale is not None else 'none'}")
    print(f"Include in feedback: {format_bool(updated.include_in_feedback)}")
    print(f"Action: {'created' if updated.was_created else 'updated'}")
    print(f"Review state: {updated.review_state}")
    print(f"Review record: {updated.review_record_relative_path}")
    print(f"Updated: {updated.updated_at}")


def print_completed_overall_standard_ratings(
    completed: CompletedOverallStandardRatings,
) -> None:
    """Print a concise teacher-facing overall-ratings completion summary."""
    print("Marked overall Focus Standard ratings complete:")
    print(f"Class: {completed.class_id}")
    print(f"Assignment: {completed.assignment_id}")
    print(f"Student: {completed.student_id}")
    print(f"Focus Standards: {completed.focus_standard_count}")
    print(f"Ratings recorded: {completed.rating_count}")
    print(f"Missing ratings: {completed.missing_rating_count}")
    print(f"Review state: {completed.review_state}")
    print(f"Review record: {completed.review_record_relative_path}")
    print(f"Updated: {completed.updated_at}")


def print_updated_standard_feedback_options(
    updated: UpdatedStandardFeedbackOptions,
) -> None:
    """Print a concise Focus Standard feedback options summary."""
    print("Updated Focus Standard feedback options:")
    print(f"Class: {updated.class_id}")
    print(f"Assignment: {updated.assignment_id}")
    print(f"Student: {updated.student_id}")
    print(f"Standard: {updated.standard_id}")
    print(f"Include overall rating: {format_bool(updated.include_overall_rating)}")
    print(
        "Include overall rationale: "
        f"{format_bool(updated.include_overall_rationale)}"
    )
    print(f"Included observations: {updated.included_observation_count}")
    print(
        "Include review-unit observations: "
        f"{format_bool(updated.include_review_unit_observations)}"
    )
    print(f"Action: {'created' if updated.was_created else 'updated'}")
    print(f"Review state: {updated.review_state}")
    print(f"Review record: {updated.review_record_relative_path}")
    print(f"Updated: {updated.updated_at}")


def print_added_feedback_comment(added: AddedFeedbackComment) -> None:
    """Print a concise custom Focus Standard feedback comment summary."""
    print("Added Focus Standard feedback comment:")
    print(f"Class: {added.class_id}")
    print(f"Assignment: {added.assignment_id}")
    print(f"Student: {added.student_id}")
    print(f"Standard: {added.standard_id}")
    print(f"Feedback comment: {added.feedback_comment_id}")
    print(f"Include in feedback: {format_bool(added.include_in_feedback)}")
    print(f"Saved for reuse: {format_bool(added.save_for_reuse)}")
    print(f"Review state: {added.review_state}")
    print(f"Review record: {added.review_record_relative_path}")
    if added.saved_reusable_comment is not None:
        print_saved_reusable_focus_standard_comment(added.saved_reusable_comment)
    print(f"Created: {added.created_at}")


def print_selected_reusable_feedback_comment(
    selected: SelectedReusableFeedbackComment,
) -> None:
    """Print a concise reusable Focus Standard comment selection summary."""
    print("Selected reusable Focus Standard comment:")
    print(f"Class: {selected.class_id}")
    print(f"Assignment: {selected.assignment_id}")
    print(f"Student: {selected.student_id}")
    print(f"Standard: {selected.standard_id}")
    print(f"Comment set: {selected.comment_set_id}")
    print(f"Reusable comment: {selected.reusable_comment_id}")
    print(f"Feedback comment: {selected.feedback_comment_id}")
    print(f"Include in feedback: {format_bool(selected.include_in_feedback)}")
    print(f"Review state: {selected.review_state}")
    print(f"Review record: {selected.review_record_relative_path}")
    print(f"Created: {selected.created_at}")


def print_completed_feedback_composition(
    completed: CompletedFeedbackComposition,
) -> None:
    """Print a concise feedback-composed summary."""
    print("Marked Focus Standard feedback composed:")
    print(f"Class: {completed.class_id}")
    print(f"Assignment: {completed.assignment_id}")
    print(f"Student: {completed.student_id}")
    print(f"Focus Standards: {completed.focus_standard_count}")
    print(f"Standards with feedback: {completed.standard_feedback_count}")
    print(f"Missing feedback records: {completed.missing_standard_feedback_count}")
    print(f"Ratings recorded: {completed.rating_count}")
    print(f"Missing ratings: {completed.missing_rating_count}")
    print(f"Selected observations: {completed.selected_observation_count}")
    print(f"Included comments: {completed.included_comment_count}")
    print(f"Review state: {completed.review_state}")
    print(f"Review record: {completed.review_record_relative_path}")
    print(f"Updated: {completed.updated_at}")


def print_saved_reusable_focus_standard_comment(
    saved: SavedReusableFocusStandardComment,
) -> None:
    """Print a concise saved reusable Focus Standard comment summary."""
    print("Saved reusable Focus Standard comment:")
    print(f"Comment set: {saved.comment_set_id}")
    print(f"Reusable comment: {saved.comment_id}")
    print(f"Standard: {saved.standard_id}")
    print(f"Purpose: {saved.purpose}")


def print_exported_feedback(exported: ExportedFeedback) -> None:
    """Print a concise student-feedback export summary."""
    print("Exported student feedback:")
    print(f"Class: {exported.class_id}")
    print(f"Assignment: {exported.assignment_id}")
    print(f"Student: {exported.student_id}")
    print(f"Included comments: {exported.included_comment_count}")
    print(f"Scores: {exported.score_count}")
    print(f"Overwrote existing: {format_bool(exported.overwrote_existing)}")
    print(f"Feedback file: {exported.feedback_relative_path}")


def print_exported_feedback_pdf(exported: ExportedFeedbackPdf) -> None:
    """Print a concise student-feedback PDF export summary."""
    print("Exported student feedback PDF:")
    print(f"Class: {exported.class_id}")
    print(f"Assignment: {exported.assignment_id}")
    print(f"Student: {exported.student_id}")
    print(f"Student name: {exported.student_display_name}")
    print(f"Focus Standard ratings: {exported.included_standard_rating_count}")
    print(f"Included comments: {exported.included_comment_count}")
    print(f"Included observations: {exported.included_observation_count}")
    print(f"Overwrote existing: {format_bool(exported.overwrote_existing)}")
    print(f"PDF file: {exported.feedback_pdf_relative_path}")
    if exported.feedback_markdown_relative_path is not None:
        print(f"Markdown file: {exported.feedback_markdown_relative_path}")
        export_formats = "PDF + Markdown"
    else:
        export_formats = "PDF"
    print(f"Feedback export: {export_formats} exported {exported.created_at}")


def print_exported_class_summary(exported: ExportedClassSummary) -> None:
    """Print a concise teacher-facing class summary export result."""
    print("Exported assignment-local class summary: Comprehensive Class Summary")
    print("Purpose: audit/troubleshooting")
    print(f"Class: {exported.class_id}")
    print(f"Assignment: {exported.assignment_id}")
    print(f"Rows: {exported.row_count}")
    print(f"Valid reviews: {exported.ready_count}")
    print(f"Missing review: {exported.missing_review_count}")
    print(f"Invalid review: {exported.invalid_review_count}")
    print(f"Missing submission: {exported.missing_submission_count}")
    print(f"Invalid submission: {exported.invalid_submission_count}")
    print(f"Identity mismatch: {exported.identity_mismatch_count}")
    print(
        "Returned without full review: "
        f"{exported.returned_without_full_review_count}"
    )
    print(f"Feedback PDF present: {exported.feedback_pdf_present_count}")
    print(f"Feedback PDF stale: {exported.feedback_pdf_stale_count}")
    print(f"Overwrote existing: {format_bool(exported.overwrote_existing)}")
    print(f"Summary file: {exported.summary_relative_path}")


def print_exported_student_performance_summary(
    exported: ExportedStudentPerformanceSummary,
) -> None:
    """Print a concise student performance summary export result."""
    print("Exported Student Performance Summary:")
    print(f"Class: {exported.class_id}")
    print(f"Assignment: {exported.assignment_id}")
    print(f"Rows: {exported.row_count}")
    print(f"Reviewed: {exported.reviewed_count}")
    print(f"Returned without full review: {exported.returned_without_full_review_count}")
    print(f"Missing submission: {exported.missing_submission_count}")
    print(f"Missing review: {exported.missing_review_count}")
    print(f"Overwrote existing: {format_bool(exported.overwrote_existing)}")
    print(f"Summary file: {exported.summary_relative_path}")


def print_exported_standards_summary(
    exported: ExportedStandardsSummary,
) -> None:
    """Print a concise teacher-facing standards summary export result."""
    missing_reviews = exported.missing_review_count + exported.invalid_review_count
    print("Exported assignment-local Focus Standard summary:")
    print(f"Class: {exported.class_id}")
    print(f"Assignment: {exported.assignment_id}")
    print(f"Standards: {exported.standard_count}")
    print(f"Expected students: {exported.student_count}")
    print(f"Valid reviews: {exported.review_count}")
    print(f"Missing reviews: {missing_reviews}")
    print(
        "Returned without full review: "
        f"{exported.returned_without_full_review_count}"
    )
    print(f"Missing review: {exported.missing_review_count}")
    print(f"Invalid review: {exported.invalid_review_count}")
    print(f"Missing submission: {exported.missing_submission_count}")
    print(f"Invalid submission: {exported.invalid_submission_count}")
    print(f"Identity mismatch: {exported.identity_mismatch_count}")
    print(f"Overwrote existing: {format_bool(exported.overwrote_existing)}")
    print(f"Summary file: {exported.summary_relative_path}")


def print_assignment_submission_status(
    result: AssignmentSubmissionStatus,
    workspace_root: Path,
    *,
    show_unused_duplicate_files: bool = False,
) -> None:
    """Print a deterministic teacher-facing assignment status summary."""
    submission_states = (
        "unreviewed",
        "in_progress",
        "needs_rescan",
        "reviewed",
    )
    page_states = ("present", "missing", "duplicate", "needs_rescan", "excluded")
    page_state_labels = {
        "present": "present",
        "missing": "missing",
        "duplicate": "duplicate",
        "needs_rescan": "needs rescan",
        "excluded": "excluded from active review",
    }
    submission_counts = {
        state: sum(
            status.submission_state == state
            for status in result.student_statuses
        )
        for state in submission_states
    }
    page_counts = {
        state: sum(
            page.page_state == state
            for status in result.student_statuses
            for page in status.pages
        )
        for state in page_states
    }
    page_counts["missing"] += sum(
        len(status.missing_pages)
        for status in result.student_statuses
        if status.manifest_path is None
    )
    unselected_count = sum(
        len(status.unselected_present_pages)
        for status in result.student_statuses
    )

    print(f"Submission status for assignment {result.assignment_id}")
    print()
    print(f"Students with manifests: {len(result.students_with_manifests)}")
    print(
        "Students with routed evidence: "
        f"{len(result.students_with_routed_evidence)}"
    )
    print(f"Students needing assembly: {len(result.students_without_manifests)}")
    print(f"Unassembled routed files: {len(result.unassembled_routed_files)}")
    if show_unused_duplicate_files:
        print(
            "Duplicate routed files not used: "
            f"{len(result.unused_duplicate_routed_files)}"
        )
    print(f"Skipped routed files: {len(result.skipped_routed_files)}")
    print()
    print("Submission states:")
    for state in submission_states:
        print(f"- {state}: {submission_counts[state]}")
    print()
    print("Page states:")
    for state in page_states:
        print(f"- {page_state_labels[state]}: {page_counts[state]}")
    print(f"- present but unselected: {unselected_count}")

    if result.student_statuses:
        print()
        print("Students:")
        for status in result.student_statuses:
            if status.manifest_path is None:
                routed_details = "routed evidence exists; no manifest"
                if status.missing_pages:
                    routed_details += (
                        "; missing="
                        f"{format_page_numbers(status.missing_pages)}"
                    )
                print(f"- {status.student_id}: {routed_details}")
                continue

            counts = {
                state: sum(page.page_state == state for page in status.pages)
                for state in page_states
            }
            detail_parts = [
                f"{page_state_labels[state]}={counts[state]}"
                for state in page_states
                if counts[state]
            ]
            if status.unselected_present_pages:
                detail_parts.append(
                    "present-but-unselected="
                    f"{len(status.unselected_present_pages)}"
                )
            suffix = ", ".join(detail_parts) if detail_parts else "no pages"
            print(f"- {status.student_id}: {status.submission_state}; {suffix}")

    if result.skipped_routed_files:
        print()
        print("Skipped routed files:")
        for skipped in result.skipped_routed_files:
            print(
                f"- {workspace_relative_display(skipped.path, workspace_root)}"
                f" — {skipped.reason}"
            )

    if result.unassembled_routed_files:
        print()
        print("Unassembled routed files:")
        for path in result.unassembled_routed_files:
            print(f"- {workspace_relative_display(path, workspace_root)}")

    if show_unused_duplicate_files and result.unused_duplicate_routed_files:
        print()
        print("Duplicate routed files not used:")
        for path in result.unused_duplicate_routed_files:
            print(f"- {workspace_relative_display(path, workspace_root)}")


def print_assignment_submission_assembly(
    result: AssignmentSubmissionAssemblyResult,
    workspace_root: Path,
) -> None:
    """Print a concise assignment assembly summary."""
    missing = sum(
        len(summary.missing_pages) for summary in result.student_summaries
    )
    duplicate = sum(
        len(summary.duplicate_pages) for summary in result.student_summaries
    )
    needs_rescan = sum(
        len(summary.needs_rescan_pages) for summary in result.student_summaries
    )
    excluded = sum(
        len(summary.excluded_pages) for summary in result.student_summaries
    )

    print(
        "Assembled submission manifests for assignment "
        f"{result.assignment_id}."
    )
    print()
    print(f"Students with routed evidence: {len(result.students_with_evidence)}")
    print(f"Created manifests: {len(result.written_manifests)}")
    print(
        "Skipped existing manifests: "
        f"{len(result.skipped_existing_manifests)}"
    )
    print(f"Skipped files: {len(result.skipped_files)}")
    print(f"Missing pages: {missing}")
    print(f"Duplicate pages: {duplicate}")
    print(f"Needs-rescan pages: {needs_rescan}")
    print(f"Excluded pages: {excluded}")
    print("Failures: 0")

    _print_path_section("Created", result.written_manifests, workspace_root)
    _print_path_section(
        "Skipped existing",
        result.skipped_existing_manifests,
        workspace_root,
    )
    if result.skipped_files:
        print()
        print("Skipped files:")
        for skipped in result.skipped_files:
            print(
                f"- {workspace_relative_display(skipped.path, workspace_root)}"
                f" — {skipped.reason}"
            )

    state_details = [
        (
            summary.student_id,
            summary.missing_pages,
            summary.duplicate_pages,
            summary.needs_rescan_pages,
            summary.excluded_pages,
        )
        for summary in result.student_summaries
        if (
            summary.missing_pages
            or summary.duplicate_pages
            or summary.needs_rescan_pages
            or summary.excluded_pages
        )
    ]
    if state_details:
        print()
        print("Page-state details:")
        for (
            student_id,
            missing_pages,
            duplicate_pages,
            rescan_pages,
            excluded_pages,
        ) in state_details:
            details = []
            if missing_pages:
                details.append(f"missing={format_page_numbers(missing_pages)}")
            if duplicate_pages:
                details.append(
                    f"duplicate={format_page_numbers(duplicate_pages)}"
                )
            if rescan_pages:
                details.append(
                    f"needs-rescan={format_page_numbers(rescan_pages)}"
                )
            if excluded_pages:
                details.append(
                    f"excluded={format_page_numbers(excluded_pages)}"
                )
            print(f"- {student_id}: {', '.join(details)}")


def print_routed_evidence(filed_evidence: RoutedEvidenceFile) -> None:
    """Print a concise successful-route summary."""
    duplicate = (
        "no"
        if filed_evidence.duplicate_number is None
        else f"yes (__dup_{filed_evidence.duplicate_number:03d})"
    )
    print("Routed Quillan response page.")
    print(
        "Retained source: "
        f"{filed_evidence.retained_source.retained_source_relative_path}"
    )
    print(f"Routed evidence: {filed_evidence.routed_evidence_relative_path}")
    print(f"Class: {filed_evidence.class_id}")
    print(f"Assignment: {filed_evidence.assignment_id}")
    print(f"Student: {filed_evidence.student_id}")
    print(f"Page: {filed_evidence.page_number}")
    print(f"Duplicate: {duplicate}")


def print_route_failure_review(
    route_failure: RouteFailure,
    review_record: RoutingReviewRecord,
) -> None:
    """Print a safely preserved route-planning failure summary."""
    print("Quillan response page was not routed; preserved for review.")
    print(f"Reason: {route_failure.failure_message}")
    print(f"Category: {route_failure.failure_category}")
    print(f"Review record: {review_record.failure_metadata_relative_path}")


def print_evidence_filing_review(
    error: EvidenceFilingError,
    review_record: RoutingReviewRecord,
) -> None:
    """Print a safely preserved evidence-filing failure summary."""
    print("Quillan response page could not be filed; preserved for review.")
    print(f"Reason: {error}")
    print("Category: evidence_write_failed")
    print(f"Review record: {review_record.failure_metadata_relative_path}")


def print_workspace_status(status: WorkspaceStatus) -> None:
    """Print a stable, user-facing workspace status summary."""
    print("Current PDS workspace root:")
    print(status.root)
    print("\nSource:")
    print(status.source)
    print("\nExists:")
    print(format_bool(status.exists))
    print("\nDirectory:")
    print(format_bool(status.is_dir))
    print("\nWritable:")
    print(format_bool(status.is_writable))
    print("\nConfig file:")
    print(status.config_path)
    print("\nDefault workspace root:")
    print(status.default_root)


def format_bool(value: bool) -> str:
    """Format a boolean for stable CLI output."""
    return "yes" if value else "no"


def format_number(value: int | float) -> str:
    """Format an integer or floating-point score compactly."""
    return f"{value:g}"


def format_page_numbers(page_numbers: tuple[int, ...]) -> str:
    """Format page numbers as a comma-separated list."""
    return ",".join(str(page_number) for page_number in page_numbers)


def workspace_relative_display(path: Path, workspace_root: Path) -> str:
    """Display a path relative to the workspace when possible."""
    try:
        return path.resolve(strict=False).relative_to(
            workspace_root.resolve(strict=False)
        ).as_posix()
    except (OSError, ValueError):
        return str(path)


def _print_path_section(
    heading: str,
    paths: tuple[Path, ...],
    workspace_root: Path,
) -> None:
    if not paths:
        return
    print()
    print(f"{heading}:")
    for path in paths:
        print(f"- {workspace_relative_display(path, workspace_root)}")

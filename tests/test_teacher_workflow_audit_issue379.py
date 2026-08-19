"""Whole-journey recorder coverage for Quillan issue #379."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.menu_screen_recorder import MenuScreenRecorder, assert_focused_child_screen
from tests.test_assignment_workflows import _write_roster, _write_standards_library
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    SECOND_STUDENT_ID,
    STUDENT_ID,
    _write_workspace,
)
from quillan.review_record_paths import review_record_path
from quillan.submission_review_opening import (
    OpenedSubmissionEvidencePage,
    OpenedSubmissionReview,
)

import quillan.assignment_workflows as assignment_workflows
from quillan.cli import main
import quillan.review_menu as review_menu


def _assignment_creation_responses(
    *,
    title: str,
    writing_type: str,
    student_prompt: str,
) -> list[str]:
    return [
        "1",  # Assignment Management -> Create writing assignment.
        "1",  # Standards-profile prerequisite -> Continue.
        "1",  # Class selection.
        title,
        "",  # Accept suggested assignment ID.
        writing_type,
        student_prompt,
        "1",  # Standards profile.
        "1,2",  # Focus Standards.
        "",  # Default paragraph review units.
        "",  # Default four-level rating scale.
        "4",  # paragraphs_min.
        "6",  # sentences_per_paragraph_min.
        "500",  # word_count_min.
        "900",  # word_count_max.
        "claim, textual evidence",
        "",  # Default minimum-requirement return policy.
        "",  # Save assignment.
        "",  # Parent-menu pause after the workflow returns.
    ]


@pytest.mark.menu_density_workflow("repeated assignment creation")
def test_repeated_assignment_creation_audit_uses_real_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Measure the present cost of creating a second substantially similar task."""
    _write_roster(tmp_path)
    _write_standards_library(tmp_path)
    monkeypatch.setattr(
        assignment_workflows,
        "resolve_workspace_root",
        lambda: tmp_path,
    )
    responses = [
        *_assignment_creation_responses(
            title="Literary Analysis Essay",
            writing_type="literary analysis",
            student_prompt="Analyze how the author develops a central idea.",
        ),
        *_assignment_creation_responses(
            title="Comparative Analysis Essay",
            writing_type="literary analysis",
            student_prompt="Compare how two authors develop a central idea.",
        ),
        "b",
    ]
    recorder = MenuScreenRecorder(responses)
    recorder.install(monkeypatch)

    assert assignment_workflows.launch_assignment_menu() == 0

    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert_focused_child_screen(
        screens,
        heading="Create Writing Assignment",
        required_text=(
            "Assignment creation requires an existing PDS Core standards profile.",
            "Standards profiles found: 1",
        ),
        forbidden_parent_text="3. Printable Response Pages",
        parent_heading="Assignment Management",
        result_heading="Assignment Saved",
        unrelated_previous_text="View/validate assignment",
    )

    saved = sorted(tmp_path.rglob("assignment.json"))
    assert len(saved) == 2
    assert {path.parent.name for path in saved} == {
        "literary_analysis_essay",
        "comparative_analysis_essay",
    }
    assert output.count("Assignment Saved") == 2


@pytest.mark.menu_density_workflow("class-set student handoff")
def test_class_set_student_handoff_audit_uses_real_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Measure the current parent-menu round trip required between students."""
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)
    original_files = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    recorder = MenuScreenRecorder(
        [
            "2",  # Main menu -> Review Student Work.
            "1",  # Review Student Work -> Assignment Review Actions.
            "1",  # Class selection.
            "1",  # Assignment selection.
            "1",  # Assignment Review Actions -> Select student/submission.
            "1",  # First roster student.
            "b",  # Back from first student's review.
            "1",  # Re-enter Select student/submission from assignment dashboard.
            "2",  # Second roster student, which currently has no digital submission.
            "b",  # Back from second student's review.
            "b",  # Back from Assignment Review Actions.
            "",  # Pause before redrawing Review Student Work.
            "b",  # Back to Quillan main menu.
            "q",  # Quit.
        ]
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert_focused_child_screen(
        screens,
        heading="Select Student/Submission",
        required_text=(
            f"Avery Rivera ({STUDENT_ID})",
            f"Mina Patel ({SECOND_STUDENT_ID})",
        ),
        forbidden_parent_text="5. View full diagnostic dashboard",
        parent_heading="Assignment Review Actions",
        result_heading="Selected Student Review",
        unrelated_previous_text="Assembly needed:",
    )

    assert output.count("Select Student/Submission") >= 2
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert f"Class: {CLASS_ID}" in output
    assert "Student: Avery Rivera" in output
    assert "Student: Mina Patel" in output
    assert "No digital submission evidence has been found for this student." in output
    assert {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    } == original_files


@pytest.mark.menu_density_workflow("complete individual review")
def test_complete_individual_review_audit_uses_one_real_teacher_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Measure one continuous teacher-facing review from evidence through export."""
    _write_workspace(tmp_path)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)

    opened: list[tuple[str, str, str, int | None, str | None]] = []

    def open_submission(
        _workspace_root: str | Path,
        class_id: str,
        assignment_id: str,
        student_id: str,
        *,
        page_number: int | None = None,
        evidence_id: str | None = None,
    ) -> OpenedSubmissionReview:
        opened.append(
            (class_id, assignment_id, student_id, page_number, evidence_id)
        )
        return OpenedSubmissionReview(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            manifest_path=tmp_path / "synthetic-submission.json",
            manifest_relative_path=(
                f"classes/{class_id}/modules/quillan/work/{assignment_id}/"
                f"submissions/{student_id}/submission.json"
            ),
            submission_state="unreviewed",
            opened_pages=(
                OpenedSubmissionEvidencePage(
                    page_number=1,
                    evidence_id="evidence_001",
                    evidence_path=tmp_path / "synthetic-evidence.pdf",
                    evidence_relative_path=(
                        f"classes/{class_id}/modules/quillan/work/{assignment_id}/"
                        "scans/response_stu_0001_pg_001.pdf"
                    ),
                    page_state="present",
                ),
            ),
        )

    monkeypatch.setattr(
        review_menu,
        "open_student_submission_for_review",
        open_submission,
    )

    recorder = MenuScreenRecorder(
        [
            # Establish class/assignment/student context.
            "2",
            "1",
            "1",
            "1",
            "1",
            "1",
            # Open the selected evidence safely.
            "1",
            "1",
            "1",
            "y",
            "",
            # Inspect the current review details.
            "2",
            "",
            # Record the one configured minimum requirement as met.
            "3",
            "1",
            "1",
            "1",
            "",
            "",
            "b",
            # Finalize the minimum-requirements outcome as met.
            "2",
            "1",
            "",
            "",
            "b",
            # Define one paragraph review unit and record one observation.
            "4",
            "1",
            "1",
            "1",
            "",
            "2",
            "1",
            "1",
            "1",
            "",
            "",
            "Synthetic observation rationale.",
            "1",
            "",
            "B",
            # Mark observations complete and return to the student screen.
            "3",
            "1",
            "",
            "4",
            # Record and complete the overall Focus Standard rating.
            "5",
            "2",
            "1",
            "1",
            "Synthetic overall rating rationale.",
            "",
            "1",
            "",
            "B",
            "3",
            "1",
            "",
            "4",
            # Add teacher-authored feedback and mark composition complete.
            "6",
            "2",
            "1",
            "Synthetic student feedback.",
            "",
            "n",
            "1",
            "",
            "4",
            "1",
            "",
            "b",
            # Export the completed review as Markdown.
            "10",
            "2",
            "",
            # Exit without changing any additional review state.
            "b",
            "b",
            "",
            "b",
            "q",
        ]
    )
    recorder.install(monkeypatch)

    assert main(["menu"]) == 0

    output = capsys.readouterr().out
    screens = recorder.screens(output)
    assert_focused_child_screen(
        screens,
        heading="Select Submission Page",
        required_text=f"Student: Avery Rivera ({STUDENT_ID})",
        forbidden_parent_text="11. Refresh summary",
        parent_heading="Selected Student Review",
        result_heading="Submission Evidence Opened",
        unrelated_previous_text="Current review summary",
    )

    assert opened == [
        (CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 1, "evidence_001")
    ]
    for expected in (
        "Current Review Details",
        "Finalized minimum-requirements outcome:",
        "Updated Focus Standard observation:",
        "Marked review-unit observations complete:",
        "Updated overall Focus Standard rating:",
        "Marked overall Focus Standard ratings complete:",
        "Added Focus Standard feedback comment:",
        "Review: feedback composed",
        "Exported student feedback:",
    ):
        assert expected in output

    review_path = review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["review_state"] == "exported"
    assert review["minimum_requirement_outcome"]["status"] == "met"
    assert len(review["review_units"]) == 1
    assert len(review["review_units"][0]["standard_observations"]) == 1
    assert len(review["overall_standard_ratings"]) == 1
    assert len(review["feedback"]["standard_feedback"]) == 1
    assert review["feedback"]["standard_feedback"][0]["comments"][0]["text"] == (
        "Synthetic student feedback."
    )
    assert review["exports"]["feedback_markdown"] is not None
    feedback_path = review_path.parent / "exports" / "feedback.md"
    assert feedback_path.is_file()
    assert "Synthetic student feedback." in feedback_path.read_text(encoding="utf-8")

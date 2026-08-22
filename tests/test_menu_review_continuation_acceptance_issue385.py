"""Recorder-backed acceptance for Quillan issue #385 Continue Review."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import quillan.review_menu as review_menu
from quillan.cli import main
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path
from quillan.submission_review_opening import (
    OpenedSubmissionEvidencePage,
    OpenedSubmissionReview,
)
from tests.menu_screen_recorder import MenuScreenRecorder
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    _write_workspace,
)


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def test_continue_review_canceled_rating_input_does_not_advance_or_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)

    review = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at="2026-08-22T12:00:00+00:00",
    )
    review["review_state"] = "observations_complete"
    review["minimum_requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 1,
            "met": True,
            "updated_at": "2026-08-22T12:00:00+00:00",
            "module_details": {},
        }
    ]
    review["minimum_requirement_outcome"] = {
        "status": "met",
        "returned_without_full_review": False,
        "teacher_note": None,
        "updated_at": "2026-08-22T12:00:00+00:00",
    }
    review["review_units"] = [
        {
            "unit_id": "paragraph_1",
            "sequence": 1,
            "label": "Paragraph 1",
            "unit_type": "paragraph",
            "standard_observations": [],
            "module_details": {},
        }
    ]
    path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review), encoding="utf-8")
    before = path.read_bytes()

    responses = iter(
        (
            "c",  # Selected Student Review -> ratings child.
            "2",  # Record/update a rating.
            "1",  # Focus Standard.
            "",  # Cancel before choosing a rating; loop remains in entry workflow.
            "1",  # Focus Standard again.
            "1",  # Rating.
            "Unsaved rationale",
            "",  # Default include-in-feedback.
            "2",  # Decline save/confirmation.
            "B",  # Leave rating-entry workflow.
            "4",  # Back from ratings submenu.
            "b",  # Back from selected-student root.
        )
    )

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(responses)
        except StopIteration as error:
            raise AssertionError("Menu requested more input than supplied.") from error

    monkeypatch.setattr("builtins.input", fake_input)

    assert review_menu._launch_selected_student_review(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ) == 0

    output = capsys.readouterr().out
    assert output.count(
        "C. Continue Review — Overall Focus Standard ratings"
    ) >= 2
    assert "Unsaved rationale" not in path.read_text(encoding="utf-8")
    assert path.read_bytes() == before


def test_continue_review_complete_individual_review_uses_real_teacher_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise one full review while C replaces repeated root stage selection."""
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
            # Evidence opening remains an explicit auxiliary action.
            "1",
            "1",
            "1",
            "y",
            "",
            # Current details remains an explicit auxiliary action.
            "2",
            "",
            # C -> minimum requirements.
            "c",
            "1",
            "1",
            "1",
            "",
            "",
            "b",
            "2",
            "1",
            "",
            "",
            "b",
            # C -> review units / observations.
            "c",
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
            "3",
            "1",
            "",
            "4",
            # C -> overall Focus Standard ratings.
            "c",
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
            # C -> Focus Standard feedback.
            "c",
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
            # C -> feedback export.
            "c",
            "2",
            "",
            # Root is freshly complete; leave without another mutation.
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
    selected_root_choices = [
        prompt.choice.casefold()
        for prompt in recorder.prompts
        if prompt.prompt == "Select an option: "
        and prompt.choice.casefold() in {"c", "3", "4", "5", "6", "10"}
    ]

    assert opened == [
        (CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, 1, "evidence_001")
    ]
    assert selected_root_choices.count("c") == 5

    continuation_labels = (
        "C. Continue Review — Review minimum requirements",
        "C. Continue Review — Review units and Focus Standard observations",
        "C. Continue Review — Overall Focus Standard ratings",
        "C. Continue Review — Compose Focus Standard feedback",
        "C. Continue Review — Export student feedback",
        "C. Continue Review — complete",
    )
    positions = [output.index(label) for label in continuation_labels]
    assert positions == sorted(positions)

    for expected in (
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
    assert (review_path.parent / "exports" / "feedback.md").is_file()

    # The acceptance test demonstrates the new route; #379 remains an unchanged
    # historical before-state rather than an exact-count invariant for this workflow.
    assert any("Selected Student Review" in screen.output for screen in screens)

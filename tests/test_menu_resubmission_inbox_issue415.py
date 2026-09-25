"""Issue #415 assignment menu placement and navigation regression tests."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.review_menu as review_menu
from quillan.resubmission_inbox import (
    AssignmentResubmissionInbox,
    ResubmissionEvidence,
    ResubmissionInboxItem,
)
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    _write_workspace,
)


def test_assignment_action_eight_opens_focused_inbox_without_renumbering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_workspace(tmp_path)
    responses = iter(("8", "b", "b"))
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert review_menu._launch_assignment_review_actions(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ) == 0

    output = capsys.readouterr().out
    ordered = (
        "1. Select student/submission",
        "2. View submission status",
        "3. Review scan problems",
        "4. Export reports",
        "5. View full diagnostic dashboard",
        "6. Refresh",
        "7. Review class progress",
        "8. Review resubmissions / rescans",
    )
    positions = tuple(output.index(label) for label in ordered)
    assert positions == tuple(sorted(positions))
    assert "Resubmission / Rescan Review" in output
    assert "No resubmission or rescan evidence currently needs review." in output
    assert "F. Batch Feedback Export" in output
    assert "G. Prepare Feedback for Printing / Sharing" in output


def test_canceling_candidate_selection_does_not_call_resolution_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = ResubmissionInboxItem(
        student_id="00107",
        display_name="Avery Rivera",
        roster_status="rostered",
        page_number=1,
        selected_evidence=ResubmissionEvidence(
            "obs_11111111111111111111111111111111",
            "2026-09-16T12:00:00+00:00",
        ),
        candidate_evidence=ResubmissionEvidence(
            "obs_22222222222222222222222222222222",
            "2026-09-23T12:00:00+00:00",
        ),
        temporal_classification="new_after_feedback",
        assembly_state="assembled",
    )
    inbox = AssignmentResubmissionInbox(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        items=(item,),
        student_count=1,
        page_count=1,
        classification_counts=(
            ("new_after_feedback", 1),
            ("new_after_review_activity", 0),
            ("additional_scanned_evidence", 0),
            ("awaiting_assembly", 0),
            ("attention_required", 0),
        ),
        warnings=(),
    )
    responses = iter(("3", "n", ""))
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr(
        review_menu,
        "select_submission_evidence_candidate",
        lambda *_args, **_kwargs: pytest.fail("resolution service was called"),
    )
    monkeypatch.setattr(
        review_menu,
        "build_assignment_resubmission_inbox",
        lambda *_args, **_kwargs: inbox,
    )

    review_menu._review_resubmission_item(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, inbox, item
    )

    assert not any(tmp_path.rglob("*"))


def test_detail_stays_open_while_teacher_compares_both_scans(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = ResubmissionInboxItem(
        student_id="00107",
        display_name="Avery Rivera",
        roster_status="rostered",
        page_number=1,
        selected_evidence=ResubmissionEvidence(
            "obs_11111111111111111111111111111111",
            "2026-09-16T12:00:00+00:00",
        ),
        candidate_evidence=ResubmissionEvidence(
            "obs_22222222222222222222222222222222",
            "2026-09-23T12:00:00+00:00",
        ),
        temporal_classification="new_after_feedback",
        assembly_state="assembled",
    )
    inbox = AssignmentResubmissionInbox(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        items=(item,),
        student_count=1,
        page_count=1,
        classification_counts=(
            ("new_after_feedback", 1),
            ("new_after_review_activity", 0),
            ("additional_scanned_evidence", 0),
            ("awaiting_assembly", 0),
            ("attention_required", 0),
        ),
        warnings=(),
    )
    responses = iter(("1", "2", "b"))
    opened: list[str] = []
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr(
        review_menu,
        "_open_exact_resubmission_evidence",
        lambda _root, _class, _assignment, _item, evidence_id: opened.append(
            evidence_id
        ),
    )
    redraws = 0

    def rebuild(*_args: object, **_kwargs: object) -> AssignmentResubmissionInbox:
        nonlocal redraws
        redraws += 1
        return inbox

    monkeypatch.setattr(
        review_menu,
        "build_assignment_resubmission_inbox",
        rebuild,
    )

    review_menu._review_resubmission_item(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, inbox, item
    )

    selected_evidence = item.selected_evidence
    candidate_evidence = item.candidate_evidence
    assert selected_evidence is not None
    assert candidate_evidence is not None
    assert opened == [
        selected_evidence.evidence_id,
        candidate_evidence.evidence_id,
    ]
    assert redraws == 3


def test_detail_does_not_offer_dismissal_without_current_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    item = ResubmissionInboxItem(
        student_id="00107",
        display_name="Avery Rivera",
        roster_status="rostered",
        page_number=1,
        selected_evidence=None,
        candidate_evidence=ResubmissionEvidence(
            "obs_22222222222222222222222222222222",
            "2026-09-23T12:00:00+00:00",
        ),
        temporal_classification="additional_scanned_evidence",
        assembly_state="assembled",
    )
    inbox = AssignmentResubmissionInbox(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        items=(item,),
        student_count=1,
        page_count=1,
        classification_counts=(
            ("new_after_feedback", 0),
            ("new_after_review_activity", 0),
            ("additional_scanned_evidence", 1),
            ("awaiting_assembly", 0),
            ("attention_required", 0),
        ),
        warnings=(),
    )
    responses = iter(("4", "", "b"))
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr(
        review_menu,
        "dismiss_submission_evidence_candidate",
        lambda *_args, **_kwargs: pytest.fail("dismissal service was called"),
    )
    monkeypatch.setattr(
        review_menu,
        "build_assignment_resubmission_inbox",
        lambda *_args, **_kwargs: inbox,
    )

    review_menu._review_resubmission_item(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, inbox, item
    )

    assert "4. Dismiss new candidate" not in capsys.readouterr().out

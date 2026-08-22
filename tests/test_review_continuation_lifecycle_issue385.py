"""Issue #385 lifecycle acceptance for deterministic Continue Review guidance."""

from __future__ import annotations

import json
from pathlib import Path

from quillan.feedback_export import export_student_feedback
from quillan.review_continuation import ReviewContinuation, derive_review_continuation
from quillan.review_feedback import add_custom_feedback_comment, mark_feedback_composed
from quillan.review_notes import add_review_note
from quillan.review_observations import mark_observations_complete, set_review_units
from quillan.review_ratings import mark_overall_ratings_complete
from quillan.review_record_paths import review_record_path
from quillan.review_requirements import (
    set_minimum_requirement_outcome,
    set_requirement_check,
)
from quillan.review_student_navigation import build_review_student_navigation
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    _write_workspace,
)

T1 = "2026-08-22T12:00:00+00:00"
T2 = "2026-08-22T12:01:00+00:00"
T3 = "2026-08-22T12:02:00+00:00"
T4 = "2026-08-22T12:03:00+00:00"
T5 = "2026-08-22T12:04:00+00:00"
T6 = "2026-08-22T12:05:00+00:00"
T7 = "2026-08-22T12:06:00+00:00"
T8 = "2026-08-22T12:07:00+00:00"
T9 = "2026-08-22T12:08:00+00:00"


def _continuation(root: Path) -> ReviewContinuation:
    navigation = build_review_student_navigation(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )
    return derive_review_continuation(navigation.current)


def _assert_stage(
    root: Path,
    *,
    category: str,
    target: str | None,
    status: str = "available",
) -> ReviewContinuation:
    continuation = _continuation(root)
    assert continuation.source_category == category
    assert continuation.target == target
    assert continuation.status == status
    assert continuation.class_id == CLASS_ID
    assert continuation.assignment_id == ASSIGNMENT_ID
    assert continuation.student_id == STUDENT_ID
    return continuation


def _read_review(root: Path) -> dict[str, object]:
    path = review_record_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _complete_review_through_feedback(root: Path) -> None:
    set_requirement_check(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        requirement_key="paragraphs_min",
        label="Minimum paragraphs",
        expected=1,
        met=True,
        updated_at=T1,
    )
    set_minimum_requirement_outcome(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        status="met",
        updated_at=T2,
    )
    set_review_units(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=T3,
    )
    mark_observations_complete(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        updated_at=T4,
    )
    mark_overall_ratings_complete(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        updated_at=T5,
    )
    add_custom_feedback_comment(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        text="Synthetic student feedback.",
        include_in_feedback=True,
        save_for_reuse=False,
        created_at=T6,
    )
    mark_feedback_composed(
        root,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        updated_at=T7,
    )


def test_real_services_advance_continuation_exactly_by_explicit_phase_state(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)

    _assert_stage(
        tmp_path,
        category="minimum_requirements_pending",
        target="minimum_requirements",
    )

    set_requirement_check(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        requirement_key="paragraphs_min",
        label="Minimum paragraphs",
        expected=1,
        met=True,
        updated_at=T1,
    )
    # A check alone is not an inferred minimum-requirements outcome.
    _assert_stage(
        tmp_path,
        category="minimum_requirements_pending",
        target="minimum_requirements",
    )

    set_minimum_requirement_outcome(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        status="met",
        updated_at=T2,
    )
    _assert_stage(
        tmp_path,
        category="observations_pending",
        target="review_unit_observations",
    )

    set_review_units(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        [{"sequence": 1}],
        updated_at=T3,
    )
    # Defining units does not infer that observations are complete.
    _assert_stage(
        tmp_path,
        category="observations_pending",
        target="review_unit_observations",
    )

    mark_observations_complete(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        updated_at=T4,
    )
    _assert_stage(
        tmp_path,
        category="ratings_pending",
        target="overall_focus_standard_ratings",
    )

    # Explicit completion is authoritative even with no synthesized rating.
    assert _read_review(tmp_path)["overall_standard_ratings"] == []
    mark_overall_ratings_complete(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        updated_at=T5,
    )
    _assert_stage(
        tmp_path,
        category="feedback_pending",
        target="focus_standard_feedback",
    )
    assert _read_review(tmp_path)["overall_standard_ratings"] == []

    add_custom_feedback_comment(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        text="Synthetic student feedback.",
        include_in_feedback=True,
        save_for_reuse=False,
        created_at=T6,
    )
    # Teacher-authored content alone does not infer phase completion.
    _assert_stage(
        tmp_path,
        category="feedback_pending",
        target="focus_standard_feedback",
    )

    mark_feedback_composed(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        updated_at=T7,
    )
    _assert_stage(
        tmp_path,
        category="export_pending",
        target="feedback_export",
    )

    before_read = review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).read_bytes()
    first = _continuation(tmp_path)
    second = _continuation(tmp_path)
    assert first == second
    assert review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).read_bytes() == before_read

    export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=T8,
    )
    _assert_stage(tmp_path, category="complete", target=None, status="complete")


def test_returned_without_full_review_routes_directly_to_export_then_complete(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)

    set_requirement_check(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        requirement_key="paragraphs_min",
        label="Minimum paragraphs",
        expected=1,
        met=False,
        teacher_note="Synthetic requirement not met.",
        updated_at=T1,
    )
    set_minimum_requirement_outcome(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        status="returned_without_full_review",
        teacher_note="Revise the synthetic response before standards review.",
        updated_at=T2,
        allow_return_without_full_review=True,
    )

    continuation = _assert_stage(
        tmp_path,
        category="export_pending",
        target="feedback_export",
    )
    assert continuation.source_reason_code == "feedback_export_missing"
    review = _read_review(tmp_path)
    assert review["review_state"] == "returned_without_full_review"
    assert review["review_units"] == []
    assert review["overall_standard_ratings"] == []
    feedback = review["feedback"]
    assert isinstance(feedback, dict)
    assert feedback["standard_feedback"] == []

    export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=T3,
    )
    complete = _assert_stage(
        tmp_path,
        category="complete",
        target=None,
        status="complete",
    )
    assert complete.source_reason_code == "current_feedback_export_present"
    review = _read_review(tmp_path)
    # Export metadata is separate from the alternate review path.
    assert review["review_state"] == "returned_without_full_review"
    assert review["review_units"] == []
    assert review["overall_standard_ratings"] == []


def test_export_freshness_moves_complete_to_pending_and_back_to_complete(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)
    _complete_review_through_feedback(tmp_path)

    exported = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=T8,
    )
    _assert_stage(tmp_path, category="complete", target=None, status="complete")

    add_review_note(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "Synthetic private note added after export.",
        created_at=T9,
    )
    stale = _assert_stage(
        tmp_path,
        category="export_pending",
        target="feedback_export",
    )
    assert stale.source_reason_code == "feedback_export_stale"

    export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        overwrite=True,
        created_at="2026-08-22T12:09:00+00:00",
    )
    _assert_stage(tmp_path, category="complete", target=None, status="complete")

    exported.feedback_path.unlink()
    missing = _assert_stage(
        tmp_path,
        category="export_pending",
        target="feedback_export",
    )
    assert missing.source_reason_code != "current_feedback_export_present"

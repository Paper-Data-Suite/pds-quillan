"""Issue #417 Slice 6 terminal-stage unwind tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import quillan.review_menu as review_menu
from quillan.review_observations import ReviewObservationError
from tests.test_menu_review_student_work import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID


def _inputs(
    monkeypatch: pytest.MonkeyPatch,
    responses: tuple[str, ...],
) -> list[str]:
    iterator = iter(responses)
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        try:
            return next(iterator)
        except StopIteration as error:
            raise AssertionError("Menu requested more input than supplied.") from error

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def test_terminal_completion_helpers_return_completed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = {
        "review_state": "ratings_complete",
        "review_units": [{"unit_id": "paragraph_1"}],
        "overall_standard_ratings": [
            {"standard_id": "synthetic:W.A", "rating": 1}
        ],
        "feedback": {
            "standard_feedback": [
                {
                    "standard_id": "synthetic:W.A",
                    "comments": [{"include_in_feedback": True}],
                }
            ]
        },
    }
    monkeypatch.setattr(
        review_menu,
        "_current_review_record",
        lambda *_args, **_kwargs: record,
    )
    monkeypatch.setattr(
        review_menu,
        "mark_observations_complete",
        lambda *_args, **_kwargs: SimpleNamespace(
            missing_focus_standard_pairs=0
        ),
    )
    monkeypatch.setattr(
        review_menu,
        "mark_overall_ratings_complete",
        lambda *_args, **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        review_menu,
        "mark_feedback_composed",
        lambda *_args, **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        review_menu,
        "print_completed_review_unit_observations",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "print_completed_overall_standard_ratings",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "print_completed_feedback_composition",
        lambda *_args, **_kwargs: None,
    )
    assignment = {"focus_standard_ids": ["synthetic:W.A"]}

    _inputs(monkeypatch, ("1",))
    assert (
        review_menu._menu_mark_observations_complete(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        )
        is review_menu.ReviewStageActionResult.COMPLETED
    )

    _inputs(monkeypatch, ("1",))
    assert (
        review_menu._menu_mark_overall_ratings_complete(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            assignment,
        )
        is review_menu.ReviewStageActionResult.COMPLETED
    )

    _inputs(monkeypatch, ("1",))
    assert (
        review_menu._menu_mark_feedback_composed(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            assignment,
        )
        is review_menu.ReviewStageActionResult.COMPLETED
    )


def test_observation_terminal_distinguishes_cancel_failure_and_no_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_menu,
        "_current_review_record",
        lambda *_args, **_kwargs: {"review_units": [{"unit_id": "paragraph_1"}]},
    )
    _inputs(monkeypatch, ("2",))
    assert (
        review_menu._menu_mark_observations_complete(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        )
        is review_menu.ReviewStageActionResult.CANCELED
    )

    monkeypatch.setattr(
        review_menu,
        "mark_observations_complete",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ReviewObservationError("synthetic failure")
        ),
    )
    _inputs(monkeypatch, ("1",))
    assert (
        review_menu._menu_mark_observations_complete(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        )
        is review_menu.ReviewStageActionResult.FAILED
    )

    monkeypatch.setattr(
        review_menu,
        "_current_review_record",
        lambda *_args, **_kwargs: None,
    )
    assert (
        review_menu._menu_mark_observations_complete(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        )
        is review_menu.ReviewStageActionResult.NO_CHANGE
    )


def test_completed_child_terminal_unwinds_without_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_menu,
        "_print_review_action_header",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "_load_assignment_for_review",
        lambda *_args, **_kwargs: {"focus_standard_ids": ["synthetic:W.A"]},
    )
    monkeypatch.setattr(
        review_menu,
        "_print_review_observation_status",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "_menu_mark_observations_complete",
        lambda *_args, **_kwargs: review_menu.ReviewStageActionResult.COMPLETED,
    )

    prompts = _inputs(monkeypatch, ("3",))
    review_menu._menu_review_unit_observations(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    assert prompts == ["Select an option: "]


def test_noncompleted_child_terminal_stays_in_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        review_menu,
        "_print_review_action_header",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "_load_assignment_for_review",
        lambda *_args, **_kwargs: {"focus_standard_ids": ["synthetic:W.A"]},
    )
    monkeypatch.setattr(
        review_menu,
        "_print_review_observation_status",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "_menu_mark_observations_complete",
        lambda *_args, **_kwargs: review_menu.ReviewStageActionResult.CANCELED,
    )

    prompts = _inputs(monkeypatch, ("3", "", "b"))
    review_menu._menu_review_unit_observations(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    assert prompts == [
        "Select an option: ",
        "Press Enter to continue...",
        "Select an option: ",
    ]

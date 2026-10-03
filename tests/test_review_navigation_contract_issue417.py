"""Issue #417 Slice 7 regressions for canonical review navigation."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

import quillan.review_menu as review_menu
from quillan.menu_navigation import ReturnToMainMenu
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
)


def _inputs(
    monkeypatch: pytest.MonkeyPatch,
    responses: tuple[str, ...],
) -> None:
    iterator = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration as error:
            raise AssertionError("Menu requested more input than supplied.") from error

    monkeypatch.setattr("builtins.input", fake_input)


def test_review_menu_source_has_no_numbered_or_hand_copied_back_entries() -> None:
    source = inspect.getsource(review_menu)

    assert re.search(r'print\("\d+\. Back"\)', source) is None
    assert 'print("B. Back")' not in source
    assert 'choice in {"", "4"}' not in source
    assert 'choice in {"", "5"}' not in source
    assert 'selection in {"", "4"}' not in source
    assert 'choice in {"", "3"}' not in source


def test_legacy_numeric_back_is_rejected_in_reusable_comment_prompt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _inputs(monkeypatch, ("3", "b"))

    result = review_menu._prompt_reusable_comment_text("Reusable default.")

    assert result is review_menu._BACK
    output = capsys.readouterr().out
    assert "B. Back" in output
    assert "M. Main Menu" in output
    assert "Q. Quit" in output
    assert "Invalid selection. Please choose a listed option, B, M, or Q." in output


def test_confirmation_navigation_uses_shared_main_menu_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _inputs(monkeypatch, ("m",))

    with pytest.raises(ReturnToMainMenu):
        review_menu._prompt_confirm_review_action()


def test_hidden_numeric_parent_back_no_longer_exits_ratings_menu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        review_menu,
        "_print_review_action_header",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "_load_assignment_for_review",
        lambda *_args, **_kwargs: {"focus_standard_ids": []},
    )
    monkeypatch.setattr(
        review_menu,
        "_current_review_record",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "_print_overall_rating_status",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        review_menu,
        "_print_overall_rating_warnings",
        lambda *_args, **_kwargs: None,
    )
    _inputs(monkeypatch, ("4", "", "b"))

    review_menu._menu_overall_focus_standard_ratings(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )

    output = capsys.readouterr().out
    assert "Invalid selection. Please choose a listed option, B, M, or Q." in output
    assert "4. Back" not in output
    assert "B. Back" in output
    assert "M. Main Menu" in output
    assert "Q. Quit" in output

"""Issue #414 selected-review redraw integration and read-count regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.review_menu as review_menu
import quillan.review_read_context as read_context_module
from tests.test_menu_review_student_work import (
    ASSIGNMENT_ID,
    CLASS_ID,
    SECOND_STUDENT_ID,
    STUDENT_ID,
    _write_workspace,
)


def _inputs(monkeypatch: pytest.MonkeyPatch, responses: tuple[str, ...]) -> None:
    iterator = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration as error:
            raise AssertionError("Menu requested more input than supplied.") from error

    monkeypatch.setattr("builtins.input", fake_input)


def _prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_workspace(tmp_path)
    monkeypatch.setattr("quillan.menu.clear_screen", lambda: None)
    monkeypatch.setattr(review_menu, "resolve_workspace_root", lambda: tmp_path)


def test_selected_root_uses_one_assignment_level_read_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare(tmp_path, monkeypatch)
    counts = {"assignment": 0, "roster": 0, "observations": 0}

    original_assignment = read_context_module.load_quillan_assignment_context
    original_roster = read_context_module.load_class_roster
    original_observations = (
        read_context_module.group_response_page_observations_by_student
    )

    def counted_assignment(*args: object, **kwargs: object):
        counts["assignment"] += 1
        return original_assignment(*args, **kwargs)  # type: ignore[arg-type]

    def counted_roster(*args: object, **kwargs: object):
        counts["roster"] += 1
        return original_roster(*args, **kwargs)  # type: ignore[arg-type]

    def counted_observations(*args: object, **kwargs: object):
        counts["observations"] += 1
        return original_observations(*args, **kwargs)  # type: ignore[arg-type]

    def unexpected_legacy_read(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Selected root invoked a legacy redundant read path")

    monkeypatch.setattr(
        read_context_module,
        "load_quillan_assignment_context",
        counted_assignment,
    )
    monkeypatch.setattr(read_context_module, "load_class_roster", counted_roster)
    monkeypatch.setattr(
        read_context_module,
        "group_response_page_observations_by_student",
        counted_observations,
    )
    monkeypatch.setattr(
        review_menu,
        "list_assignment_submission_status",
        unexpected_legacy_read,
    )
    monkeypatch.setattr(
        review_menu,
        "build_student_review_status",
        unexpected_legacy_read,
    )
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation",
        unexpected_legacy_read,
    )
    monkeypatch.setattr(
        review_menu,
        "print_active_context",
        unexpected_legacy_read,
    )
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    ) == 0

    assert counts == {"assignment": 1, "roster": 1, "observations": 1}


def test_navigation_redraw_discards_context_and_builds_fresh_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare(tmp_path, monkeypatch)
    contexts: list[object] = []
    status_contexts: list[object] = []
    navigation_contexts: list[object] = []

    original_context = review_menu.build_assignment_review_read_context
    original_status = review_menu.build_student_review_status_from_read_context
    original_navigation = (
        review_menu.build_review_student_navigation_from_read_context
    )

    def counted_context(*args: object, **kwargs: object):
        context = original_context(*args, **kwargs)  # type: ignore[arg-type]
        contexts.append(context)
        return context

    def counted_status(context, student_id):
        status_contexts.append(context)
        return original_status(context, student_id)

    def counted_navigation(context, student_id):
        navigation_contexts.append(context)
        return original_navigation(context, student_id)

    monkeypatch.setattr(
        review_menu,
        "build_assignment_review_read_context",
        counted_context,
    )
    monkeypatch.setattr(
        review_menu,
        "build_student_review_status_from_read_context",
        counted_status,
    )
    monkeypatch.setattr(
        review_menu,
        "build_review_student_navigation_from_read_context",
        counted_navigation,
    )
    _inputs(monkeypatch, ("n", "b"))

    assert review_menu._launch_selected_student_review(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    ) == 0

    assert len(contexts) == 2
    assert contexts[0] is not contexts[1]
    assert status_contexts == contexts
    assert navigation_contexts == contexts
    assert SECOND_STUDENT_ID != STUDENT_ID


def test_selected_root_active_context_uses_validated_assignment_title(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(
        review_menu,
        "print_active_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("selected root rediscovered active assignment")
        ),
    )
    _inputs(monkeypatch, ("b",))

    assert review_menu._launch_selected_student_review(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    ) == 0

    output = capsys.readouterr().out
    assert "Active context" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID} - Synthetic Essay" in output

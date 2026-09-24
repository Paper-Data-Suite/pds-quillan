"""Issue #414 tests for redraw-scoped assignment review reads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pds_core.rosters import RosterError

import quillan.review_read_context as read_context_module
from quillan.review_read_context import (
    ReviewReadContextError,
    build_assignment_review_read_context,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import _write_assignment, _write_roster


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def test_builder_reads_assignment_roster_and_strict_observations_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    before = _snapshot(tmp_path)
    calls = {"assignment": 0, "roster": 0, "observations": 0}

    read_context_hooks: Any = read_context_module
    original_assignment = read_context_hooks.load_quillan_assignment_context
    original_roster = read_context_hooks.load_class_roster
    original_observations = (
        read_context_hooks.group_response_page_observations_by_student
    )

    def counted_assignment(*args: Any, **kwargs: Any) -> Any:
        calls["assignment"] += 1
        return original_assignment(*args, **kwargs)

    def counted_roster(*args: Any, **kwargs: Any) -> Any:
        calls["roster"] += 1
        return original_roster(*args, **kwargs)

    def counted_observations(*args: Any, **kwargs: Any) -> Any:
        calls["observations"] += 1
        return original_observations(*args, **kwargs)

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

    context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    assert calls == {"assignment": 1, "roster": 1, "observations": 1}
    assert context.class_id == CLASS_ID
    assert context.assignment_id == ASSIGNMENT_ID
    assert context.workspace_root == tmp_path
    assert context.roster_available is True
    assert context.roster_error is None
    assert context.observations_available is True
    assert context.observations_error is None
    assert context.observations_by_student == {}
    assert _snapshot(tmp_path) == before


def test_roster_failure_is_captured_without_repeating_or_masking_other_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)

    def unavailable_roster(*_args: object, **_kwargs: object) -> object:
        raise RosterError("synthetic roster unavailable")

    monkeypatch.setattr(
        read_context_module,
        "load_class_roster",
        unavailable_roster,
    )

    context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    assert context.roster_available is False
    assert context.roster_students is None
    assert context.roster_error == "synthetic roster unavailable"
    assert context.observations_available is True


def test_observation_failure_is_captured_after_one_strict_discovery_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    calls = 0

    def unavailable_observations(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise ValueError("synthetic routed evidence failure")

    monkeypatch.setattr(
        read_context_module,
        "group_response_page_observations_by_student",
        unavailable_observations,
    )

    context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    assert calls == 1
    assert context.observations_available is False
    assert context.observations_by_student is None
    assert context.observations_error == "synthetic routed evidence failure"
    assert context.roster_available is True


def test_observation_mapping_is_detached_and_immutable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    source: dict[str, tuple[object, ...]] = {}

    monkeypatch.setattr(
        read_context_module,
        "group_response_page_observations_by_student",
        lambda *_args, **_kwargs: source,
    )

    context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    source["later"] = ()

    assert context.observations_by_student is not None
    assert tuple(context.observations_by_student) == ()
    with pytest.raises(TypeError):
        context.observations_by_student["later"] = ()  # type: ignore[index]


@pytest.mark.parametrize(
    ("class_id", "assignment_id"),
    (
        ("", ASSIGNMENT_ID),
        (CLASS_ID, ""),
        ("../unsafe", ASSIGNMENT_ID),
        (CLASS_ID, "../unsafe"),
    ),
)
def test_invalid_identity_fails_before_assignment_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    class_id: str,
    assignment_id: str,
) -> None:
    calls = 0

    def unexpected_assignment_read(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("invalid identity reached assignment loading")

    monkeypatch.setattr(
        read_context_module,
        "load_quillan_assignment_context",
        unexpected_assignment_read,
    )

    with pytest.raises(ReviewReadContextError):
        build_assignment_review_read_context(tmp_path, class_id, assignment_id)

    assert calls == 0


def test_missing_assignment_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ReviewReadContextError, match="Could not load assignment"):
        build_assignment_review_read_context(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
        )

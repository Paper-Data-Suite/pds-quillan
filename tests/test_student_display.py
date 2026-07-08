"""Tests for resilient teacher-facing student labels."""

from pathlib import Path

from pds_core.rosters import RosterError
import pytest

import quillan.student_display as student_display


def test_student_review_label_uses_core_display_name(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    student = object()
    roster = object()
    monkeypatch.setattr(student_display, "load_class_roster", lambda *_: roster)
    monkeypatch.setattr(
        student_display, "student_lookup", lambda value: {"10002": student}
    )
    monkeypatch.setattr(
        student_display, "student_display_name", lambda value: "Eli Brooks"
    )

    assert (
        student_display.student_review_label(tmp_path, "english10", "10002")
        == "Eli Brooks (10002)"
    )


def test_student_review_label_falls_back_when_roster_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        student_display,
        "load_class_roster",
        lambda *_: (_ for _ in ()).throw(RosterError("missing")),
    )

    assert (
        student_display.student_review_label(tmp_path, "english10", "10002")
        == "10002"
    )


def test_student_review_label_falls_back_for_missing_roster_row(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(student_display, "load_class_roster", lambda *_: object())
    monkeypatch.setattr(student_display, "student_lookup", lambda _: {})

    assert (
        student_display.student_review_label(tmp_path, "english10", "19999")
        == "19999"
    )

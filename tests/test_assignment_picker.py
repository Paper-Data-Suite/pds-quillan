"""Tests for assignment picker discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.assignment_picker import (
    available_assignments,
    prompt_assignment_choice,
)


CLASS_ID = "english_12_p3"


def _assignment(
    assignment_id: str,
    *,
    title: str = "Synthetic Assignment",
) -> dict[str, Any]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": assignment_id,
        "title": title,
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Write a synthetic argument.",
        "standards_profile_id": "synthetic_ela",
        "focus_standard_ids": ["synthetic:W.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_2_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                }
            ],
        },
        "basic_requirements": {},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
        "created_at": "2026-07-13T00:00:00+00:00",
        "updated_at": "2026-07-13T00:00:00+00:00",
        "module_details": {},
    }


def _write_assignment(
    workspace_root: Path,
    assignment_id: str,
    assignment: dict[str, Any],
) -> None:
    path = (
        workspace_root
        / "classes"
        / CLASS_ID
        / "assignments"
        / assignment_id
        / "assignment.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(assignment), encoding="utf-8")


def _write_roster(workspace_root: Path) -> None:
    path = workspace_root / "classes" / CLASS_ID / "roster.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "class_id,student_id,last_name,first_name,period\n"
        f"{CLASS_ID},student_001,Student,Synthetic,3\n",
        encoding="utf-8",
    )


def test_available_assignments_lists_valid_v2_assignments(tmp_path: Path) -> None:
    _write_assignment(
        tmp_path,
        "valid_assignment",
        _assignment("valid_assignment", title="Visible Title"),
    )

    choices = available_assignments(tmp_path, CLASS_ID)

    assert [choice.assignment_id for choice in choices] == ["valid_assignment"]
    assert choices[0].title == "Visible Title"


def test_available_assignments_skips_invalid_and_legacy_configs(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path, "valid_assignment", _assignment("valid_assignment"))
    _write_assignment(tmp_path, "invalid_assignment", {"assignment_id": "incomplete"})
    _write_assignment(
        tmp_path,
        "legacy_assignment",
        {
            "assignment_id": "legacy_assignment",
            "title": "Legacy",
            "class_ids": [CLASS_ID],
            "writing_type": "argument",
            "standards_profile_id": "synthetic_ela",
            "tagging_mode": "focus",
            "focus_standards": ["synthetic:W.1"],
            "basic_requirements": {},
            "rubric_id": "legacy",
        },
    )

    choices = available_assignments(tmp_path, CLASS_ID)

    assert [choice.assignment_id for choice in choices] == ["valid_assignment"]


def test_prompt_assignment_choice_clears_and_reframes_after_class_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_assignment(
        tmp_path,
        "valid_assignment",
        _assignment("valid_assignment", title="Visible Title"),
    )
    events: list[str] = []
    responses = iter(("1", "1"))

    def fake_input(prompt: str = "") -> str:
        events.append(prompt)
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(
        "quillan.menu.clear_screen", lambda: events.append("clear")
    )

    choice = prompt_assignment_choice(tmp_path)

    assert choice is not None
    assert choice.assignment_id == "valid_assignment"
    assert events == ["Select class: ", "clear", "Select assignment: "]
    output = capsys.readouterr().out
    assert "Select Assignment" in output
    assert f"Class: {CLASS_ID}" in output
    assert "Assignments:\n" in output
    assert "1. valid_assignment - Visible Title" in output
    assert f"Assignments for {CLASS_ID}:" not in output


def test_prompt_assignment_choice_reframes_when_class_has_no_assignments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    clear_calls: list[str] = []
    monkeypatch.setattr("builtins.input", lambda _prompt="": "1")
    monkeypatch.setattr(
        "quillan.menu.clear_screen", lambda: clear_calls.append("clear")
    )

    assert prompt_assignment_choice(tmp_path) is None

    assert clear_calls == ["clear"]
    output = capsys.readouterr().out
    assert "Select Assignment" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"No valid assignments found for class {CLASS_ID}." in output

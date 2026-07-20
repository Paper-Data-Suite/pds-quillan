"""Tests for assignment picker discovery."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from quillan.assignment_picker import (
    available_assignments,
    prompt_assignment_choice,
)
from quillan.work_paths import QuillanWorkPathError, _is_link_like


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
        / "modules"
        / "quillan"
        / "work"
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


def _create_windows_junction(link: Path, target: Path) -> None:
    result = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(
            "Windows junction creation unavailable: "
            f"exit {result.returncode}: {result.stderr.strip()}"
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


def test_available_assignments_skips_unsafe_non_direct_and_mismatched_entries(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path, "valid_assignment", _assignment("valid_assignment"))
    _write_assignment(tmp_path, "bad assignment", _assignment("valid_assignment"))
    _write_assignment(
        tmp_path, "mismatched_assignment", _assignment("different_assignment")
    )
    work = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
    )
    directory_record = work / "directory_record" / "assignment.json"
    directory_record.mkdir(parents=True)
    nested_record = work / "nested_only" / "nested" / "assignment.json"
    nested_record.parent.mkdir(parents=True)
    nested_record.write_text(
        json.dumps(_assignment("nested_only")), encoding="utf-8"
    )

    choices = available_assignments(tmp_path, CLASS_ID)

    assert [choice.assignment_id for choice in choices] == ["valid_assignment"]


def test_available_assignments_rejects_symlinked_assignment_file(
    tmp_path: Path,
) -> None:
    work = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / "linked_assignment"
    )
    work.mkdir(parents=True)
    outside = tmp_path / "outside-assignment.json"
    outside.write_text(
        json.dumps(_assignment("linked_assignment")), encoding="utf-8"
    )
    try:
        os.symlink(outside, work / "assignment.json")
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    assert available_assignments(tmp_path, CLASS_ID) == ()
    assert outside.read_text(encoding="utf-8") == json.dumps(
        _assignment("linked_assignment")
    )


def test_available_assignments_has_deterministic_link_detection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path, "linked_assignment", _assignment("linked_assignment"))
    monkeypatch.setattr(
        "quillan.assignment_discovery._is_link_like",
        lambda path: path.name == "assignment.json" or _is_link_like(path),
    )

    assert available_assignments(tmp_path, CLASS_ID) == ()


def test_available_assignments_handles_collection_preflight_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path, "external_assignment", _assignment("external_assignment"))

    def reject_collection(_workspace_root: Path, _class_id: str) -> Path:
        raise QuillanWorkPathError("synthetic link-like ancestor")

    monkeypatch.setattr(
        "quillan.assignment_discovery.preflight_quillan_work_collection",
        reject_collection,
    )

    assert available_assignments(tmp_path, CLASS_ID) == ()


def test_available_assignments_wrong_type_modules_ancestor_is_safe(
    tmp_path: Path,
) -> None:
    modules = tmp_path / "classes" / CLASS_ID / "modules"
    modules.parent.mkdir(parents=True)
    modules.write_bytes(b"wrong-type-unchanged")

    assert available_assignments(tmp_path, CLASS_ID) == ()
    assert modules.read_bytes() == b"wrong-type-unchanged"
    assert list(modules.parent.iterdir()) == [modules]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_available_assignments_rejects_intermediate_modules_junction(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside-modules"
    assignment_path = (
        outside
        / "quillan"
        / "work"
        / "external_assignment"
        / "assignment.json"
    )
    assignment_path.parent.mkdir(parents=True)
    assignment_path.write_text(
        json.dumps(_assignment("external_assignment")), encoding="utf-8"
    )
    original_bytes = assignment_path.read_bytes()
    modules = workspace / "classes" / CLASS_ID / "modules"
    modules.parent.mkdir(parents=True)
    _create_windows_junction(modules, outside)

    try:
        assert available_assignments(workspace, CLASS_ID) == ()
        assert assignment_path.read_bytes() == original_bytes
        assert list(modules.parent.iterdir()) == [modules]
    finally:
        os.rmdir(modules)

    assert outside.is_dir()
    assert assignment_path.read_bytes() == original_bytes


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_available_assignments_rejects_direct_collection_junction(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside-work"
    assignment_path = outside / "external_assignment" / "assignment.json"
    assignment_path.parent.mkdir(parents=True)
    assignment_path.write_text(
        json.dumps(_assignment("external_assignment")), encoding="utf-8"
    )
    original_bytes = assignment_path.read_bytes()
    work = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work"
    work.parent.mkdir(parents=True)
    _create_windows_junction(work, outside)

    try:
        assert available_assignments(workspace, CLASS_ID) == ()
        assert assignment_path.read_bytes() == original_bytes
        assert list(work.parent.iterdir()) == [work]
    finally:
        os.rmdir(work)

    assert outside.is_dir()
    assert assignment_path.read_bytes() == original_bytes


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

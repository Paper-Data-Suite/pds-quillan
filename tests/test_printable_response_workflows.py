"""Tests for teacher-facing printable response packet workflows."""

from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path

from pds_core.classes import write_class_roster
from pds_core.rosters import create_roster
from pypdf import PdfReader
import pytest

import quillan.printable_response_workflows as workflows


CLASS_ID = "synthetic_english_p3"
ASSIGNMENT_ID = "synthetic_response"


def _inputs(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str],
) -> list[str]:
    response_iterator: Iterator[str] = iter(responses)
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        try:
            return next(response_iterator)
        except StopIteration as error:
            raise AssertionError("Workflow requested unexpected input.") from error

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def _write_roster(workspace_root: Path, class_id: str = CLASS_ID) -> Path:
    roster = create_roster(
        class_id,
        [
            {
                "student_id": "0001",
                "last_name": "Example",
                "first_name": "Avery",
                "period": "3",
            },
            {
                "student_id": "0002",
                "last_name": "Sample",
                "first_name": "Morgan",
                "period": "3",
            },
        ],
    )
    return write_class_roster(workspace_root, roster)


def _assignment(class_ids: list[str] | None = None) -> dict[str, object]:
    return {
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Writing Response",
        "class_ids": class_ids or [CLASS_ID],
        "writing_type": "synthetic_response",
        "standards_profile_id": "synthetic_ela",
        "tagging_mode": "focus",
        "focus_standards": ["synthetic:W.SYN.1"],
        "basic_requirements": {"paragraphs_min": 1},
        "rubric_id": "synthetic_rubric",
    }


def _write_assignment(
    workspace_root: Path,
    assignment: dict[str, object] | None = None,
) -> Path:
    path = (
        workspace_root
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(assignment or _assignment()),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5"])
def test_parse_pages_per_student_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        workflows.parse_pages_per_student(value)


def test_parse_pages_per_student_defaults_blank_and_accepts_integer() -> None:
    assert workflows.parse_pages_per_student("") == 1
    assert workflows.parse_pages_per_student(" 2 ") == 2


def test_generate_class_packet_happy_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    roster_path = _write_roster(tmp_path)
    assignment_path = _write_assignment(tmp_path)
    roster_bytes = roster_path.read_bytes()
    assignment_bytes = assignment_path.read_bytes()
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["1", "1", "2"])

    assert workflows.prompt_generate_class_packet() == 0

    output_path = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "templates"
        / "printable_response_pages.pdf"
    )
    assert output_path.is_file()
    assert output_path.read_bytes().startswith(b"%PDF")
    assert len(PdfReader(str(output_path)).pages) == 4
    assert roster_path.read_bytes() == roster_bytes
    assert assignment_path.read_bytes() == assignment_bytes

    output = capsys.readouterr().out
    assert "Output mode: one class packet PDF" in output
    assert "Generated printable response packet:" in output
    assert str(output_path) in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert "Pages per student: 2" in output


def test_generate_class_packet_accepts_exact_ids_and_blank_page_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_roster(tmp_path)
    _write_assignment(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, [CLASS_ID, ASSIGNMENT_ID, ""])

    assert workflows.prompt_generate_class_packet() == 0
    output_path = workflows.expected_printable_packet_path(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert len(PdfReader(str(output_path)).pages) == 2


def test_generate_class_packet_requires_roster(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)

    assert workflows.prompt_generate_class_packet() == 1
    assert "No class rosters found. Create a class roster first." in (
        capsys.readouterr().out
    )
    assert not list(tmp_path.rglob("*.pdf"))


def test_generate_class_packet_requires_assignment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["1"])

    assert workflows.prompt_generate_class_packet() == 1
    assert "No assignment configs found for this class" in capsys.readouterr().out
    assert not list(tmp_path.rglob("*.pdf"))


def test_generate_class_packet_rejects_invalid_assignment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_assignment(tmp_path, {"assignment_id": ASSIGNMENT_ID})
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["1", "1"])

    assert workflows.prompt_generate_class_packet() == 1
    output = capsys.readouterr().out
    assert "[INVALID:" in output
    assert "Assignment config is invalid" in output
    assert not list(tmp_path.rglob("*.pdf"))


def test_generate_class_packet_rejects_assignment_class_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_assignment(tmp_path, _assignment(["different_synthetic_class"]))
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["1", "1"])

    assert workflows.prompt_generate_class_packet() == 1
    output = capsys.readouterr().out
    assert "does not include" in output
    assert CLASS_ID in output
    assert not list(tmp_path.rglob("*.pdf"))


def test_generate_class_packet_reports_invalid_pages_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_roster(tmp_path)
    _write_assignment(tmp_path)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["1", "1", "0"])

    assert workflows.prompt_generate_class_packet() == 1
    output = capsys.readouterr().out
    assert "Pages per student must be a positive integer" in output
    assert "Traceback" not in output
    assert not list(tmp_path.rglob("*.pdf"))


@pytest.mark.parametrize("confirmation", ["", "overwrite", "no"])
def test_generate_class_packet_does_not_overwrite_without_exact_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    confirmation: str,
) -> None:
    _write_roster(tmp_path)
    _write_assignment(tmp_path)
    output_path = workflows.expected_printable_packet_path(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    output_path.parent.mkdir(parents=True)
    original_bytes = b"existing synthetic PDF bytes"
    output_path.write_bytes(original_bytes)
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["1", "1", "1", confirmation])

    assert workflows.prompt_generate_class_packet() == 1
    assert output_path.read_bytes() == original_bytes


def test_generate_class_packet_overwrites_after_exact_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_roster(tmp_path)
    _write_assignment(tmp_path)
    output_path = workflows.expected_printable_packet_path(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"old")
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(monkeypatch, ["1", "1", "1", "OVERWRITE"])

    assert workflows.prompt_generate_class_packet() == 0
    assert output_path.read_bytes().startswith(b"%PDF")


def test_printable_response_menu_displays_options_and_dispatches(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = 0

    def generate() -> int:
        nonlocal calls
        calls += 1
        return 0

    monkeypatch.setattr(workflows, "prompt_generate_class_packet", generate)
    _inputs(monkeypatch, ["1", "", "2"])

    assert workflows.launch_printable_response_menu() == 0
    output = capsys.readouterr().out
    assert calls == 1
    assert "Generate class packet" in output
    assert "Back" in output


def test_printable_response_menu_invalid_selection_and_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _inputs(monkeypatch, ["bad", "", "2"])
    assert workflows.launch_printable_response_menu() == 0
    assert "Invalid selection" in capsys.readouterr().out

    def interrupt(_prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert workflows.launch_printable_response_menu() == 0
    assert "Exiting printable response menu." in capsys.readouterr().out

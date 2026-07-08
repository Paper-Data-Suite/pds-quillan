"""Tests for Quillan's shared-roster teacher workflows."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pds_core.classes import load_class_roster, write_class_roster
from pds_core.rosters import (
    Roster,
    RosterValidationError,
    StudentRecord,
    add_student_record,
    create_roster,
    remove_student_record,
    replace_student_record,
)
import pytest

from quillan.menu_navigation import QuitQuillan, ReturnToMainMenu
import quillan.roster_workflows as workflows


def _roster(class_id: str = "synthetic_class") -> Roster:
    return create_roster(
        class_id,
        [
            {
                "student_id": "0012",
                "last_name": "Example",
                "first_name": "Avery",
                "period": "3",
                "preferred_name": "Ari",
                "notes": "synthetic",
            },
            {
                "student_id": "0042",
                "last_name": "Sample",
                "first_name": "Morgan",
                "period": "3",
                "preferred_name": "",
                "notes": "",
            },
        ],
    )


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


def test_create_class_roster_uses_canonical_path_and_preserves_zero_id(
    tmp_path: Path,
) -> None:
    roster, path = workflows.create_class_roster(
        tmp_path,
        "english_12_p3",
        [
            {
                "student_id": "0007",
                "last_name": "Synthetic",
                "first_name": "Jordan",
                "period": "3",
            }
        ],
    )

    assert path == tmp_path / "classes" / "english_12_p3" / "roster.csv"
    assert roster.students[0].student_id == "0007"
    assert load_class_roster(tmp_path, "english_12_p3").students[0].student_id == "0007"


def test_prompt_create_roster_writes_canonical_roster_and_preserves_zero_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "English 10 Period 2",
            "",
            "2",
            "0008",
            "Synthetic",
            "Riley",
            "",
        ],
    )

    assert workflows.prompt_create_roster() == 0

    class_id = "english_10_period_2"
    roster_path = tmp_path / "classes" / class_id / "roster.csv"
    assert roster_path.is_file()

    roster = load_class_roster(tmp_path, class_id)
    assert roster.class_id == class_id
    assert len(roster.students) == 1
    assert roster.students[0].student_id == "0008"
    assert roster.students[0].last_name == "Synthetic"
    assert roster.students[0].first_name == "Riley"
    assert roster.students[0].period == "2"


def test_prompt_create_roster_does_not_overwrite_without_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_class_roster(tmp_path, _roster())
    original = load_class_roster(tmp_path, "synthetic_class")
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "Synthetic Class",
            "",
            "no",
        ],
    )

    assert workflows.prompt_create_roster() == 1
    assert load_class_roster(tmp_path, "synthetic_class") == original


def test_format_roster_includes_required_and_optional_columns() -> None:
    output = workflows.format_roster_for_display(
        _roster(),
        Path("classes/synthetic_class/roster.csv"),
    )

    assert "Student count: 2" in output
    assert "student_id" in output
    assert "last_name" in output
    assert "first_name" in output
    assert "period" in output
    assert "preferred_name" in output
    assert "notes" in output
    assert "0012" in output


def test_add_and_edit_student_preserve_optional_schema_and_values() -> None:
    roster = _roster()
    added = add_student_record(
        roster,
        workflows.student_record_from_values(
            roster,
            "0099",
            {
                "last_name": "Person",
                "first_name": "Taylor",
                "period": "3",
                "preferred_name": "Tay",
                "notes": "",
            },
        ),
    )
    edited = replace_student_record(
        added,
        workflows.student_record_from_values(
            added,
            "0012",
            {
                "last_name": "Example",
                "first_name": "Avery",
                "period": "4",
                "preferred_name": "Ari",
                "notes": "synthetic",
            },
        ),
    )

    assert edited.columns == roster.columns
    assert edited.students[-1].extra_fields == {
        "preferred_name": "Tay",
        "notes": "",
    }
    assert edited.students[0].extra_fields == roster.students[0].extra_fields
    assert edited.students[0].period == "4"


def test_add_student_accepts_shared_period_default_and_preserves_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roster = _roster()
    prompts = _inputs(
        monkeypatch,
        ["0099", "Person", "Taylor", "", "Tay", ""],
    )

    updated = workflows.prompt_add_student_to_roster(roster)

    added = updated.students[-1]
    assert "  period [3]: " in prompts
    assert added.student_id == "0099"
    assert isinstance(added.student_id, str)
    assert added.period == "3"
    assert added.extra_fields == {
        "preferred_name": "Tay",
        "notes": "",
    }


def test_add_student_can_override_shared_period_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _inputs(monkeypatch, ["0099", "Person", "Taylor", "4", "Tay", ""])

    updated = workflows.prompt_add_student_to_roster(_roster())

    assert updated.students[-1].period == "4"


def test_add_student_requires_period_when_existing_periods_are_mixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _roster()
    roster = replace_student_record(
        original,
        workflows.student_record_from_values(
            original,
            "0042",
            {
                "last_name": "Sample",
                "first_name": "Morgan",
                "period": "4",
                "preferred_name": "",
                "notes": "",
            },
        ),
    )
    prompts = _inputs(
        monkeypatch,
        ["0099", "Person", "Taylor", "5", "Tay", ""],
    )

    updated = workflows.prompt_add_student_to_roster(roster)

    assert workflows.shared_roster_period(roster) is None
    assert "  period: " in prompts
    assert not any(prompt.startswith("  period [") for prompt in prompts)
    assert updated.students[-1].period == "5"


def test_remove_is_in_memory_only_and_does_not_touch_evidence(
    tmp_path: Path,
) -> None:
    roster = _roster()
    evidence = (
        tmp_path
        / "classes"
        / roster.class_id
        / "assignments"
        / "essay"
        / "submissions"
        / "0012"
        / "feedback.md"
    )
    evidence.parent.mkdir(parents=True)
    evidence.write_text("keep historical evidence", encoding="utf-8")

    staged = remove_student_record(roster, "0012")

    assert [student.student_id for student in staged.students] == ["0042"]
    assert len(roster.students) == 2
    assert evidence.read_text(encoding="utf-8") == "keep historical evidence"


def test_edit_cancel_discard_does_not_write_staged_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_class_roster(tmp_path, _roster())
    original = load_class_roster(tmp_path, "synthetic_class")
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "1",
            "1",
            "0099",
            "Person",
            "Taylor",
            "3",
            "Tay",
            "",
            "6",
            "DISCARD",
        ],
    )

    assert workflows.prompt_edit_class_roster() == 0
    output = capsys.readouterr().out
    assert "Class ID: synthetic_class" in output
    assert "Student count: 2" in output
    assert "Unsaved changes: no" in output
    assert "Last action: student added" in output
    assert "Discard Roster Changes" in output
    saved = load_class_roster(tmp_path, "synthetic_class")
    assert saved == original


@pytest.mark.parametrize(
    ("command", "error_type", "destination"),
    [
        ("m", ReturnToMainMenu, "Main Menu"),
        ("q", QuitQuillan, "quit Quillan"),
    ],
)
def test_dirty_edit_global_navigation_requires_discard_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    error_type: type[Exception],
    destination: str,
) -> None:
    write_class_roster(tmp_path, _roster())
    original = load_class_roster(tmp_path, "synthetic_class")
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    prompts = _inputs(
        monkeypatch,
        [
            "1",
            "1",
            "0099",
            "Person",
            "Taylor",
            "3",
            "Tay",
            "",
            command,
            "KEEP",
            command,
            "DISCARD",
        ],
    )

    with pytest.raises(error_type):
        workflows.prompt_edit_class_roster()
    output = capsys.readouterr().out
    assert output.count("Unsaved roster changes will be discarded.") == 2
    assert f"Type DISCARD to {destination}: " in prompts
    assert load_class_roster(tmp_path, "synthetic_class") == original


def test_edit_view_current_roster_is_explicit_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_class_roster(tmp_path, _roster())
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    prompts = _inputs(monkeypatch, ["1", "4", "", "6"])

    assert workflows.prompt_edit_class_roster() == 0
    output = capsys.readouterr().out
    assert "Current Roster" in output
    assert "Roster path:" in output
    assert "0012" in output
    assert "Press Enter to return to edit menu..." in prompts


def test_edit_save_requires_confirmation_then_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_class_roster(tmp_path, _roster())
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: tmp_path)
    _inputs(
        monkeypatch,
        [
            "1",
            "2",
            "1",
            "",
            "",
            "4",
            "",
            "",
            "5",
            "no",
            "5",
            "SAVE",
        ],
    )

    assert workflows.prompt_edit_class_roster() == 0
    saved = load_class_roster(tmp_path, "synthetic_class")
    assert saved.students[0].period == "4"
    assert saved.students[0].student_id == "0012"
    assert saved.students[0].extra_fields["preferred_name"] == "Ari"


def test_validate_roster_summary_and_structured_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_path = write_class_roster(tmp_path, _roster())
    _inputs(monkeypatch, [str(valid_path)])
    assert workflows.prompt_validate_roster() == 0
    valid_output = capsys.readouterr().out
    assert "Roster file is valid." in valid_output
    assert "Student count: 2" in valid_output
    assert "0012" in valid_output

    invalid_path = tmp_path / "invalid.csv"
    invalid_path.write_text(
        "class_id,student_id,last_name,first_name,period\n"
        "synthetic_class,0001,Example,,3\n",
        encoding="utf-8",
    )
    _inputs(monkeypatch, [str(invalid_path)])
    assert workflows.prompt_validate_roster() == 1
    invalid_output = capsys.readouterr().out
    assert "[blank_required_value]" in invalid_output
    assert "row 2" in invalid_output
    assert "column first_name" in invalid_output


def test_shared_validation_rejects_duplicate_student_id() -> None:
    roster = _roster()
    duplicate = StudentRecord(
        class_id=roster.class_id,
        student_id="0012",
        last_name="Duplicate",
        first_name="Synthetic",
        period="3",
        extra_fields={"preferred_name": "", "notes": ""},
    )

    with pytest.raises(RosterValidationError):
        add_student_record(roster, duplicate)


def test_roster_menu_displays_options_and_dispatches(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def record(name: str) -> int:
        calls.append(name)
        return 0

    monkeypatch.setattr(
        workflows,
        "prompt_create_roster",
        lambda: record("create"),
    )
    monkeypatch.setattr(
        workflows,
        "prompt_view_roster",
        lambda: record("view"),
    )
    monkeypatch.setattr(
        workflows,
        "prompt_edit_class_roster",
        lambda: record("edit"),
    )
    monkeypatch.setattr(
        workflows,
        "prompt_validate_roster",
        lambda: record("validate"),
    )
    _inputs(monkeypatch, ["1", "", "2", "", "3", "", "4", "", "5"])

    assert workflows.launch_roster_menu() == 0
    output = capsys.readouterr().out
    assert calls == ["create", "view", "edit", "validate"]
    assert "Create class roster" in output
    assert "View class roster" in output
    assert "Edit class roster" in output
    assert "Validate class roster" in output
    assert "Back" in output


def test_roster_menu_invalid_selection_and_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _inputs(monkeypatch, ["bad", "", "5"])
    assert workflows.launch_roster_menu() == 0
    assert "Invalid selection" in capsys.readouterr().out

    def interrupt(_prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert workflows.launch_roster_menu() == 0
    assert "Exiting roster menu." in capsys.readouterr().out

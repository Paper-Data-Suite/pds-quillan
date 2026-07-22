from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pds_core.class_metadata import (
    create_class_metadata,
    load_class_metadata_for_class,
    write_class_metadata_for_class,
)
from pds_core.classes import load_class_roster, write_class_roster
from pds_core.rosters import create_roster
from pds_core.school_years import open_school_year

from quillan.cli import main
from quillan.cli_app.handlers import rosters as handlers
from quillan import roster_management


def _source_csv(path: Path, *, class_id: str = "english_10_p2") -> Path:
    path.write_text(
        "class_id,student_id,last_name,first_name,period,preferred_name,notes\n"
        f"{class_id},0007,Example,Avery,2,Ari,\n"
        f"{class_id},0042,Sample,Morgan,2,,synthetic\n",
        encoding="utf-8",
    )
    return path


def _canonical_roster(workspace: Path) -> Path:
    roster = create_roster(
        "english_10_p2",
        [
            {
                "student_id": "0007",
                "last_name": "Example",
                "first_name": "Avery",
                "period": "2",
                "preferred_name": "Ari",
                "notes": "",
            },
            {
                "student_id": "0042",
                "last_name": "Sample",
                "first_name": "Morgan",
                "period": "2",
                "preferred_name": "",
                "notes": "synthetic",
            },
        ],
    )
    return write_class_roster(workspace, roster)


def _use_workspace(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: workspace)


def test_roster_help_and_bare_namespace_do_not_resolve_workspace(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_workspace() -> Path:
        raise AssertionError("workspace must not be resolved for roster help")

    monkeypatch.setattr(handlers, "resolve_workspace_root", fail_workspace)
    assert main(["roster"]) == 0
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    for command in (
        "create",
        "show",
        "validate",
        "add-student",
        "update-student",
        "remove-student",
    ):
        assert command in output
    with pytest.raises(SystemExit) as help_exit:
        main(["roster", "update-student", "--help"])
    assert help_exit.value.code == 0
    assert "cannot be changed" in (lambda captured: captured.out + captured.err)(capsys.readouterr())


@pytest.mark.parametrize(
    "command",
    ["create", "show", "validate", "add-student", "update-student", "remove-student"],
)
def test_each_roster_subcommand_help_exits_successfully(command: str) -> None:
    with pytest.raises(SystemExit) as help_exit:
        main(["roster", command, "--help"])
    assert help_exit.value.code == 0


def test_create_preserves_ids_columns_blanks_order_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    source = _source_csv(tmp_path / "source.csv")
    _use_workspace(monkeypatch, workspace)

    assert main(
        [
            "roster",
            "create",
            "english_10_p2",
            "--input",
            str(source),
            "--school-year",
            "2026-2027",
            "--yes",
        ]
    ) == 0

    roster = load_class_roster(workspace, "english_10_p2")
    assert roster.columns == (
        "class_id",
        "student_id",
        "last_name",
        "first_name",
        "period",
        "preferred_name",
        "notes",
    )
    assert [student.student_id for student in roster.students] == ["0007", "0042"]
    assert roster.students[0].extra_fields["notes"] == ""
    assert load_class_metadata_for_class(
        workspace, "english_10_p2"
    ).school_year == "2026-2027"


def test_create_uses_active_year_and_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = tmp_path / "workspace"
    open_school_year(
        workspace,
        "2027-2028",
        opened_at=datetime.now(timezone.utc),
    )
    source = _source_csv(tmp_path / "source.csv")
    _use_workspace(monkeypatch, workspace)

    assert main(
        [
            "roster",
            "create",
            "english_10_p2",
            "--input",
            str(source),
            "--dry-run",
        ]
    ) == 0
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "School year: 2027-2028" in output
    assert "No files were written." in output
    assert not (workspace / "classes").exists()


@pytest.mark.parametrize(
    "extra_args", [[], ["--yes"], ["--overwrite", "--dry-run"]]
)
def test_create_safety_failures_write_nothing(
    extra_args: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    source = _source_csv(tmp_path / "source.csv", class_id="different_class")
    _use_workspace(monkeypatch, workspace)
    args = [
        "roster",
        "create",
        "english_10_p2",
        "--input",
        str(source),
        "--school-year",
        "2026-2027",
        *extra_args,
    ]
    assert main(args) == 1
    assert not (workspace / "classes").exists()


def test_create_refuses_existing_pair_without_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    original_path = _canonical_roster(workspace)
    original = original_path.read_bytes()
    source = _source_csv(tmp_path / "source.csv")
    _use_workspace(monkeypatch, workspace)

    assert main(
        [
            "roster",
            "create",
            "english_10_p2",
            "--input",
            str(source),
            "--school-year",
            "2026-2027",
            "--yes",
        ]
    ) == 1
    assert original_path.read_bytes() == original


def test_new_paired_creation_cleans_up_if_metadata_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    source = _source_csv(tmp_path / "source.csv")
    plan = roster_management.plan_roster_creation(
        workspace, "english_10_p2", source, school_year="2026-2027"
    )

    def fail_metadata(*_args: object, **_kwargs: object) -> Path:
        raise OSError("synthetic metadata failure")

    monkeypatch.setattr(
        roster_management, "write_class_metadata_for_class", fail_metadata
    )
    with pytest.raises(OSError, match="synthetic metadata failure"):
        roster_management.write_roster_creation(plan)
    assert not plan.roster_path.exists()
    assert not plan.metadata_path.exists()
    assert not plan.roster_path.parent.exists()


def test_show_and_validate_are_read_only_and_report_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = tmp_path / "workspace"
    roster_path = _canonical_roster(workspace)
    before = roster_path.read_bytes()
    _use_workspace(monkeypatch, workspace)

    assert main(["roster", "show", "english_10_p2"]) == 0
    shown = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "0007" in shown
    assert "preferred_name" in shown
    assert "School year: not set" in shown
    assert main(["roster", "validate", "english_10_p2"]) == 0
    assert "Canonical roster is valid." in (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert roster_path.read_bytes() == before
    assert not (roster_path.parent / "class.json").exists()


def test_validate_rejects_invalid_existing_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = tmp_path / "workspace"
    roster_path = _canonical_roster(workspace)
    (roster_path.parent / "class.json").write_text("{}\n", encoding="utf-8")
    _use_workspace(monkeypatch, workspace)

    assert main(["roster", "validate", "english_10_p2"]) == 1
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert output.startswith("Error:")
    assert "Traceback" not in output


def test_validate_prints_structured_roster_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = tmp_path / "workspace"
    path = workspace / "classes" / "english_10_p2" / "roster.csv"
    path.parent.mkdir(parents=True)
    path.write_text(
        "class_id,student_id,last_name,first_name,period\n"
        "english_10_p2,0007,Example,,2\n",
        encoding="utf-8",
    )
    _use_workspace(monkeypatch, workspace)

    assert main(["roster", "validate", "english_10_p2"]) == 1
    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "[blank_required_value]" in output
    assert "row 2" in output
    assert "column first_name" in output
    assert "Traceback" not in output


def test_add_and_update_preserve_schema_order_values_and_stable_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    _canonical_roster(workspace)
    _use_workspace(monkeypatch, workspace)

    assert main(
        [
            "roster",
            "add-student",
            "english_10_p2",
            "--student-id",
            "0099",
            "--last-name",
            "Person",
            "--first-name",
            "Taylor",
            "--period",
            "3",
            "--field",
            "preferred_name=Tay",
            "--yes",
        ]
    ) == 0
    added = load_class_roster(workspace, "english_10_p2")
    assert added.students[-1].student_id == "0099"
    assert added.students[-1].extra_fields == {"preferred_name": "Tay", "notes": ""}

    assert main(
        [
            "roster",
            "update-student",
            "english_10_p2",
            "0007",
            "--period",
            "4",
            "--field",
            "notes=updated",
            "--field",
            "preferred_name=",
            "--yes",
        ]
    ) == 0
    updated = load_class_roster(workspace, "english_10_p2")
    assert [student.student_id for student in updated.students] == [
        "0007",
        "0042",
        "0099",
    ]
    assert updated.students[0].period == "4"
    assert updated.students[0].extra_fields == {
        "preferred_name": "",
        "notes": "updated",
    }


@pytest.mark.parametrize(
    "fields",
    [
        ["--field", "unknown=value"],
        ["--field", "student_id=12"],
        ["--field", "notes=a", "--field", "notes=b"],
    ],
)
def test_add_rejects_invalid_optional_fields_without_writing(
    fields: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    roster_path = _canonical_roster(workspace)
    before = roster_path.read_bytes()
    _use_workspace(monkeypatch, workspace)
    assert main(
        [
            "roster",
            "add-student",
            "english_10_p2",
            "--student-id",
            "0099",
            "--last-name",
            "Person",
            "--first-name",
            "Taylor",
            "--period",
            "3",
            *fields,
            "--yes",
        ]
    ) == 1
    assert roster_path.read_bytes() == before


def test_remove_changes_only_roster_and_preserves_evidence_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = tmp_path / "workspace"
    roster_path = _canonical_roster(workspace)
    metadata = create_class_metadata(
        "english_10_p2", "2026-2027", created_at=datetime.now(timezone.utc)
    )
    metadata_path = write_class_metadata_for_class(workspace, metadata)
    evidence = roster_path.parent / "modules" / "quillan" / "work" / "essay" / "submissions" / "0007" / "feedback.md"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("retain", encoding="utf-8")
    metadata_before = metadata_path.read_bytes()
    _use_workspace(monkeypatch, workspace)

    assert main(
        ["roster", "remove-student", "english_10_p2", "0007", "--yes"]
    ) == 0
    assert [
        student.student_id
        for student in load_class_roster(workspace, "english_10_p2").students
    ] == ["0042"]
    assert metadata_path.read_bytes() == metadata_before
    assert evidence.read_text(encoding="utf-8") == "retain"
    assert "does not delete" in (lambda captured: captured.out + captured.err)(capsys.readouterr())


def test_mutation_dry_run_and_missing_confirmation_do_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    roster_path = _canonical_roster(workspace)
    before = roster_path.read_bytes()
    _use_workspace(monkeypatch, workspace)

    base = [
        "roster",
        "remove-student",
        "english_10_p2",
        "0007",
    ]
    assert main([*base, "--dry-run"]) == 0
    assert main(base) == 1
    assert roster_path.read_bytes() == before

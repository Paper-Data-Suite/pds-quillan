"""Issue #390 direct diagnostics CLI contract tests."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from quillan.cli import main
from quillan.diagnostic_events import (
    build_diagnostic_event,
    diagnostic_events_dir,
    record_diagnostic_event,
)


@pytest.fixture(autouse=True)
def _fixed_core_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quillan.diagnostic_events._installed_core_version",
        lambda: "0.6.3",
    )


@pytest.fixture
def cli_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    monkeypatch.setattr(
        "quillan.cli_app.handlers.diagnostics.resolve_workspace_root",
        lambda: tmp_path,
    )
    return tmp_path


def _record(
    root: Path,
    *,
    event_id: str,
    occurred_at: datetime,
) -> None:
    event = build_diagnostic_event(
        component="assembly",
        workflow="assemble_submission",
        stage="verify_record",
        outcome="success",
        code="assembly_succeeded",
        class_id="class_a",
        assignment_id="assignment_a",
        occurred_at=occurred_at,
        event_id=event_id,
    )
    record_diagnostic_event(root, event)


def test_diagnostics_list_missing_directory_is_read_only(
    cli_workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["diagnostics", "list"]) == 0
    output = capsys.readouterr()
    assert output.out == "diagnostic events: none\n"
    assert output.err == ""
    assert not diagnostic_events_dir(cli_workspace).exists()


def test_diagnostics_list_is_newest_first_and_bounded(
    cli_workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _record(
        cli_workspace,
        event_id="diag_00000000000000000000000000000001",
        occurred_at=datetime(2026, 8, 24, 20, 0, tzinfo=timezone.utc),
    )
    _record(
        cli_workspace,
        event_id="diag_00000000000000000000000000000002",
        occurred_at=datetime(2026, 8, 24, 20, 1, tzinfo=timezone.utc),
    )
    assert main(["diagnostics", "list", "--limit", "1"]) == 0
    output = capsys.readouterr()
    assert "diagnostic events: 1" in output.out
    assert "diag_00000000000000000000000000000002" in output.out
    assert "diag_00000000000000000000000000000001" not in output.out
    assert "class_id: class_a" in output.out
    assert "assignment_id: assignment_a" in output.out


def test_diagnostics_list_json_contains_only_safe_event_model(
    cli_workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _record(
        cli_workspace,
        event_id="diag_00000000000000000000000000000003",
        occurred_at=datetime(2026, 8, 24, 20, 2, tzinfo=timezone.utc),
    )
    assert main(["diagnostics", "list", "--format", "json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["schema_version"] == "1"
    assert document["warning_codes"] == []
    assert len(document["events"]) == 1
    event = document["events"][0]
    assert event["core_version"] == "0.6.3"
    assert set(event) == {
        "schema_version",
        "module",
        "record_type",
        "event_id",
        "occurred_at",
        "quillan_version",
        "core_version",
        "component",
        "workflow",
        "stage",
        "outcome",
        "category",
        "code",
        "class_id",
        "assignment_id",
        "exception_type",
        "safe_summary",
        "path_context",
    }


def test_diagnostics_show_exact_event_text(
    cli_workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event_id = "diag_00000000000000000000000000000004"
    _record(
        cli_workspace,
        event_id=event_id,
        occurred_at=datetime(2026, 8, 24, 20, 3, tzinfo=timezone.utc),
    )
    assert main(["diagnostics", "show", "--event-id", event_id]) == 0
    output = capsys.readouterr()
    assert f"event_id: {event_id}" in output.out
    assert "outcome: success" in output.out
    assert "path_context: none" in output.out
    assert output.err == ""


def test_diagnostics_show_json_is_exact_safe_event(
    cli_workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event_id = "diag_00000000000000000000000000000005"
    _record(
        cli_workspace,
        event_id=event_id,
        occurred_at=datetime(2026, 8, 24, 20, 4, tzinfo=timezone.utc),
    )
    assert (
        main(
            [
                "diagnostics",
                "show",
                "--event-id",
                event_id,
                "--format",
                "json",
            ]
        )
        == 0
    )
    event = json.loads(capsys.readouterr().out)
    assert event["event_id"] == event_id
    assert (
        event["safe_summary"]
        == "Submission assembly completed and was verified."
    )
    assert "warning_codes" not in event


def test_diagnostics_show_invalid_or_missing_event_is_concise_nonzero(
    cli_workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["diagnostics", "show", "--event-id", "not-safe"]) == 1
    first = capsys.readouterr()
    assert first.out == ""
    assert "Error: diagnostics show failed:" in first.err
    assert "Traceback" not in first.err

    missing = "diag_00000000000000000000000000000006"
    assert main(["diagnostics", "show", "--event-id", missing]) == 1
    second = capsys.readouterr()
    assert "Diagnostic event was not found." in second.err
    assert "Traceback" not in second.err


def test_diagnostics_list_rejects_limit_above_hard_max(
    cli_workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["diagnostics", "list", "--limit", "201"]) == 1
    output = capsys.readouterr()
    assert "Error: diagnostics list failed:" in output.err
    assert "limit" in output.err
    assert not diagnostic_events_dir(cli_workspace).exists()


def test_diagnostics_help_has_no_mutating_or_streaming_subcommands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["diagnostics"]) == 0
    output = capsys.readouterr().out.casefold()
    assert "list" in output
    assert "show" in output
    for forbidden in (
        "delete",
        "clear",
        "upload",
        "send",
        "watch",
        "tail",
        "stream",
    ):
        assert forbidden not in output

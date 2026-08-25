from __future__ import annotations

import pytest
from pathlib import Path

import quillan.cli_app.handlers.routing as routing
from quillan.diagnostic_events import (
    diagnostic_event_path,
    list_diagnostic_events,
)
from quillan.cli_app.parser import build_parser


def test_route_scan_has_no_direct_payload_option() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["route-scan", "scan.png", "--payload", "PDS3"])
    args = parser.parse_args(["route-scan", "scan.png"])
    assert args.source_file.name == "scan.png"


def test_direct_route_scan_missing_source_writes_only_local_diagnostic_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "builtins.input",
        lambda *_args, **_kwargs: pytest.fail("direct route-scan must not prompt"),
    )
    before = tuple(tmp_path.rglob("*"))
    assert before == ()

    assert routing.run_qr_scan_intake(tmp_path / "missing.png", tmp_path) == 1
    output = capsys.readouterr().out
    assert "source failures" in output.casefold()
    assert "Batch status: source_failure" in output

    diagnostic_listing = list_diagnostic_events(tmp_path)
    assert diagnostic_listing.warning_codes == ()
    assert len(diagnostic_listing.events) == 1
    event = diagnostic_listing.events[0]
    assert event.component == "paper_intake"
    assert event.workflow == "route_returned_paper"
    assert event.outcome == "failure"
    assert event.code == "dispatch_failed"
    assert event.class_id is None
    assert event.assignment_id is None
    assert event.path_context is None

    created_files = {
        path.resolve()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert created_files == {
        diagnostic_event_path(tmp_path, event.event_id).resolve()
    }

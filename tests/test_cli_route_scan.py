from __future__ import annotations

import pytest
from pathlib import Path

import quillan.cli_app.handlers.routing as routing
from quillan.cli_app.parser import build_parser


def test_route_scan_has_no_direct_payload_option() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["route-scan", "scan.png", "--payload", "PDS3"])
    args = parser.parse_args(["route-scan", "scan.png"])
    assert args.source_file.name == "scan.png"


def test_direct_route_scan_missing_source_is_noninteractive_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "builtins.input",
        lambda *_args, **_kwargs: pytest.fail("direct route-scan must not prompt"),
    )
    before = tuple(tmp_path.rglob("*"))
    assert routing.run_qr_scan_intake(tmp_path / "missing.png", tmp_path) == 1
    output = capsys.readouterr().out
    assert "source failures" in output.casefold()
    assert "Batch status: source_failure" in output
    assert tuple(tmp_path.rglob("*")) == before

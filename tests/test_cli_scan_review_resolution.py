"""CLI tests for listing and resolving Quillan scan review items."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.scan_review as cli_scan_review
from quillan.cli_app.parser import build_parser
from tests.test_scan_review_resolution import FAILURE_ID, _write_failure


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cli_scan_review, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def test_route_resolution_parser_accepts_exact_registered_route_identity() -> None:
    args = build_parser().parse_args(
        [
            "resolve-scan-review",
            FAILURE_ID,
            "--action",
            "route_selected",
            "--route-id",
            "rt_0123456789abcdef0123456789abcdef",
            "--route-class-id",
            "english12_p3",
            "--route-assignment-id",
            "essay_01",
        ]
    )
    assert args.route_id == "rt_0123456789abcdef0123456789abcdef"
    assert args.route_class_id == "english12_p3"
    assert args.route_assignment_id == "essay_01"


def test_list_and_resolve_scan_review_commands(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    failure_path = _write_failure(workspace)
    before = failure_path.read_bytes()

    assert main(["list-scan-review"]) == 0
    listed = capsys.readouterr().out
    assert FAILURE_ID in listed
    assert "Status: unresolved" in listed
    assert "Source: teacher_scan.pdf" in listed

    assert main(
        [
            "resolve-scan-review",
            FAILURE_ID,
            "--action",
            "rescan_needed",
            "--message",
            "Needs rescan",
        ]
    ) == 0
    resolved = capsys.readouterr().out
    assert "Scan review item resolved." in resolved
    assert "scans/review/resolutions/" in resolved
    assert failure_path.read_bytes() == before

    assert main(["list-scan-review"]) == 0
    assert "No Core routing review items" in capsys.readouterr().out
    assert main(["list-scan-review", "--include-resolved"]) == 0
    assert "Status: resolved" in capsys.readouterr().out


def test_cli_defer_remains_visible(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_failure(workspace)
    assert main(["resolve-scan-review", FAILURE_ID, "--action", "defer"]) == 0
    capsys.readouterr()
    assert main(["list-scan-review"]) == 0
    assert "Status: deferred" in capsys.readouterr().out


def test_cli_reports_malformed_and_invalid_requests(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review_dir = workspace / "scans" / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "bad.json").write_text("bad", encoding="utf-8")
    assert main(["list-scan-review"]) == 0
    assert "skipped 1 malformed or unreadable" in capsys.readouterr().out

    assert main(
        ["resolve-scan-review", "failure_missing", "--action", "other", "--message", "x"]
    ) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error:" in captured.err


def test_cli_writes_only_json_resolution_metadata(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_failure(workspace)
    evidence = (
        workspace
        / "classes"
        / "english12_p3"
        / "modules"
        / "quillan"
        / "work"
        / "essay_01"
        / "handled"
        / "source.pdf"
    )
    evidence.parent.mkdir(parents=True)
    evidence.write_bytes(b"evidence")
    relative_evidence = evidence.relative_to(workspace).as_posix()
    assert main(
        [
            "resolve-scan-review",
            FAILURE_ID,
            "--action",
            "evidence_filed",
            "--evidence-path",
            relative_evidence,
        ]
    ) == 0
    capsys.readouterr()
    files = list((workspace / "scans" / "review" / "resolutions").iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".json"
    assert (
        json.loads(files[0].read_text(encoding="utf-8"))[
            "resolution_evidence_path"
        ]
        == relative_evidence
    )

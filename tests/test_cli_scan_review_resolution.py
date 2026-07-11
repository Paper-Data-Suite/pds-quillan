"""CLI tests for listing and resolving Quillan scan review items."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.scan_review as cli_scan_review
from tests.test_scan_review_resolution import FAILURE_ID, _write_failure


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cli_scan_review, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def test_list_and_resolve_scan_review_commands(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    failure_path = _write_failure(workspace)
    before = failure_path.read_bytes()

    assert main(["list-scan-review"]) == 0
    listed = capsys.readouterr().out
    assert FAILURE_ID in listed
    assert "Status: unresolved" in listed
    assert "Retained source:" in listed

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
    assert "No Quillan scan review items" in capsys.readouterr().out
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
    assert "Error:" in capsys.readouterr().out


def test_cli_writes_only_json_resolution_metadata(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_failure(workspace)
    assert main(
        ["resolve-scan-review", FAILURE_ID, "--action", "evidence_filed", "--evidence-path", "handled/source.pdf"]
    ) == 0
    capsys.readouterr()
    files = list((workspace / "scans" / "review" / "resolutions").iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".json"
    assert json.loads(files[0].read_text(encoding="utf-8"))["resolution_evidence_path"] == "handled/source.pdf"

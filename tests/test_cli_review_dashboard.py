"""Direct CLI tests for the read-only review dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.dashboard as cli_dashboard
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import _write_assignment


def test_cli_review_dashboard_text_and_json_are_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignment = _write_assignment(tmp_path)
    original = assignment.read_bytes()
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    monkeypatch.setattr(cli_dashboard, "resolve_workspace_root", lambda: tmp_path)

    assert main(["review-dashboard", CLASS_ID, ASSIGNMENT_ID]) == 0
    assert "Assignment Review Dashboard" in (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert main(["review-dashboard", CLASS_ID, ASSIGNMENT_ID, "--format", "json"]) == 0
    document = json.loads((lambda captured: captured.out + captured.err)(capsys.readouterr()))

    assert document["schema_version"] == "1"
    assert document["assignment"]["path"].startswith("classes/")
    assert assignment.read_bytes() == original
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before


def test_cli_review_dashboard_help_and_expected_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as help_exit:
        main(["review-dashboard", "--help"])
    assert help_exit.value.code == 0
    assert "--format" in (lambda captured: captured.out + captured.err)(capsys.readouterr())

    monkeypatch.setattr(cli_dashboard, "resolve_workspace_root", lambda: tmp_path)
    assert main(["review-dashboard", CLASS_ID, ASSIGNMENT_ID]) == 1
    assert "Error: could not build" in (lambda captured: captured.out + captured.err)(capsys.readouterr())

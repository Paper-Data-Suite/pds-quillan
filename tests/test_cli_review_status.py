"""CLI registration and representation tests for review-status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.cli import main
from quillan.cli_app.handlers import review_status as cli_review_status
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import _write_assignment


def test_help_is_registered(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["review-status", "--help"])
    assert exit_info.value.code == 0
    assert "student_id" in capsys.readouterr().out


def test_json_is_one_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _write_assignment(tmp_path)
    monkeypatch.setattr(cli_review_status, "resolve_workspace_root", lambda: tmp_path)
    assert main(["review-status", CLASS_ID, ASSIGNMENT_ID, "00100", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["record_type"] == "quillan_student_review_status"


def test_text_is_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _write_assignment(tmp_path)
    monkeypatch.setattr(cli_review_status, "resolve_workspace_root", lambda: tmp_path)
    assert main(["review-status", CLASS_ID, ASSIGNMENT_ID, "00100"]) == 0
    assert capsys.readouterr().out.startswith("Student Review Status\n")

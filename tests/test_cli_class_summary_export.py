"""CLI tests for teacher-facing class review summary export."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from quillan.class_summary_export import class_summary_export_path
from quillan.cli import main
import quillan.cli_app.handlers.exports as cli_exports
from tests.test_class_summary_export import _student_dir, _write_assignment, _write_records
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID


def test_cli_exports_ready_and_non_ready_rows_and_prints_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_assignment(tmp_path)
    manifest_path, review_path, _ = _write_records(tmp_path, "00100")
    _student_dir(tmp_path, "00200").mkdir(parents=True)
    originals = {
        manifest_path: manifest_path.read_bytes(),
        review_path: review_path.read_bytes(),
    }
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)

    assert main(["export-class-summary", CLASS_ID, ASSIGNMENT_ID]) == 0

    output = capsys.readouterr().out
    assert "Exported assignment-local class summary:" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert "Rows: 2" in output
    assert "Valid reviews: 1" in output
    assert "Missing review: 0" in output
    assert "Invalid review: 0" in output
    assert "Missing submission: 1" in output
    assert "Invalid submission: 0" in output
    assert "Identity mismatch: 0" in output
    assert "Returned without full review: 0" in output
    assert "Feedback PDF present: 0" in output
    assert "Feedback PDF stale: 0" in output
    assert "Overwrote existing: no" in output
    relative = (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/exports/"
        "class_summary.csv"
    )
    assert f"Summary file: {relative}" in output
    summary_path = class_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    with summary_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["review_valid"] for row in rows] == ["true", "false"]
    assert "missing_submission" in rows[1]["warnings"]
    for path, original in originals.items():
        assert path.read_bytes() == original


def test_cli_missing_submissions_directory_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    assert main(["export-class-summary", CLASS_ID, ASSIGNMENT_ID]) == 1
    assert "assignment config" in capsys.readouterr().out


def test_cli_overwrite_flag_controls_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_assignment(tmp_path)
    manifest_path, review_path, _ = _write_records(tmp_path, "00100")
    originals = {
        manifest_path: manifest_path.read_bytes(),
        review_path: review_path.read_bytes(),
    }
    output_path = class_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    output_path.parent.mkdir(parents=True)
    output_path.write_text("manual edit", encoding="utf-8")
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    command = ["export-class-summary", CLASS_ID, ASSIGNMENT_ID]

    assert main(command) == 1
    assert output_path.read_text(encoding="utf-8") == "manual edit"
    assert main([*command, "--overwrite"]) == 0

    output = capsys.readouterr().out
    assert "Use --overwrite" in output
    assert "Overwrote existing: yes" in output
    assert "review_valid" in output_path.read_text(encoding="utf-8")
    for path, original in originals.items():
        assert path.read_bytes() == original

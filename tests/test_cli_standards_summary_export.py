"""CLI tests for teacher-facing standards summary CSV export."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.exports as cli_exports
from quillan.standards_summary_export import standards_summary_export_path
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import STANDARD_A, _write_assignment
from tests.test_standards_summary_export import _rating, _write_review


def test_cli_exports_standards_rows_and_prints_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignment_path = _write_assignment(tmp_path)
    manifest_path, review_path, _ = _write_review(
        tmp_path,
        "00100",
        ratings=[_rating(STANDARD_A, 3)],
    )
    originals = {
        assignment_path: assignment_path.read_bytes(),
        manifest_path: manifest_path.read_bytes(),
        review_path: review_path.read_bytes(),
    }
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)

    assert main(["export-standards-summary", CLASS_ID, ASSIGNMENT_ID]) == 0

    output = capsys.readouterr().out
    assert "Exported assignment-local Focus Standard summary:" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert "Standards: 2" in output
    assert "Expected students: 1" in output
    assert "Valid reviews: 1" in output
    assert "Missing reviews: 0" in output
    assert "Returned without full review: 0" in output
    assert "Missing review: 0" in output
    assert "Invalid review: 0" in output
    assert "Missing submission: 0" in output
    assert "Invalid submission: 0" in output
    assert "Identity mismatch: 0" in output
    assert "Overwrote existing: no" in output
    relative = (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/exports/"
        "standards_summary.csv"
    )
    assert f"Summary file: {relative}" in output
    with standards_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ).open("r", encoding="utf-8", newline="") as file:
        assert list(csv.DictReader(file))[0]["standard_id"] == STANDARD_A
    for path, original in originals.items():
        assert path.read_bytes() == original


def test_cli_handles_missing_directory_and_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    command = ["export-standards-summary", CLASS_ID, ASSIGNMENT_ID]
    assert main(command) == 1
    assert "assignment config" in capsys.readouterr().out

    _write_assignment(tmp_path)
    _write_review(
        tmp_path,
        "00100",
        ratings=[_rating(STANDARD_A, 3)],
    )
    output_path = standards_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    output_path.parent.mkdir(parents=True)
    output_path.write_text("manual edit", encoding="utf-8")

    assert main(command) == 1
    assert output_path.read_text(encoding="utf-8") == "manual edit"
    assert main([*command, "--overwrite"]) == 0
    output = capsys.readouterr().out
    assert "Use --overwrite" in output
    assert "Overwrote existing: yes" in output


def test_cli_writes_header_only_when_no_standard_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_review(
        tmp_path,
        "00100",
        ratings=[],
    )
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)

    assert main(["export-standards-summary", CLASS_ID, ASSIGNMENT_ID]) == 0

    with standards_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ).open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 2
    assert all(row["students_reviewed_for_standard"] == "0" for row in rows)

"""CLI tests for teacher-facing standards summary CSV export."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

import quillan.cli
from quillan.cli import main
from quillan.standards_summary_export import standards_summary_export_path
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID
from tests.test_standards_summary_export import _tag, _write_review


def test_cli_exports_standards_rows_and_prints_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_review(
        tmp_path,
        "00100",
        tags=[_tag("tag_1", "W.A", "positive")],
        comments=[],
    )
    originals = {path: path.read_bytes() for path in paths}
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    assert main(["export-standards-summary", CLASS_ID, ASSIGNMENT_ID]) == 0

    output = capsys.readouterr().out
    assert "Exported standards summary:" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert "Rows: 1" in output
    assert "Standards: 1" in output
    assert "Valid reviews: 1" in output
    assert "Missing review: 0" in output
    assert "Invalid review: 0" in output
    assert "Missing submission: 0" in output
    assert "Invalid submission: 0" in output
    assert "Identity mismatch: 0" in output
    assert "Overwrote existing: no" in output
    relative = (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/exports/"
        "standards_summary.csv"
    )
    assert f"Summary file: {relative}" in output
    with standards_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ).open("r", encoding="utf-8", newline="") as file:
        assert list(csv.DictReader(file))[0]["standard_code"] == "W.A"
    for path, original in originals.items():
        assert path.read_bytes() == original


def test_cli_handles_missing_directory_and_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)
    command = ["export-standards-summary", CLASS_ID, ASSIGNMENT_ID]
    assert main(command) == 1
    assert "submissions directory does not exist" in capsys.readouterr().out

    _write_review(
        tmp_path,
        "00100",
        tags=[_tag("tag_1", "W.A", "positive")],
        comments=[],
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
    _write_review(
        tmp_path,
        "00100",
        tags=[_tag("tag_1", None, "neutral")],
        comments=[],
    )
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    assert main(["export-standards-summary", CLASS_ID, ASSIGNMENT_ID]) == 0

    with standards_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ).open("r", encoding="utf-8", newline="") as file:
        assert list(csv.DictReader(file)) == []

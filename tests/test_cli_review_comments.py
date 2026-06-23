"""CLI tests for reusable shared-bank comment selection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import quillan.cli
from quillan.cli import main
from quillan.review_record_paths import review_record_path
from tests.test_review_comments import BANK_ID, _write_bank
from tests.test_review_scores import _write_manifest
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID


def test_cli_selects_comment_and_prints_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    _write_bank(tmp_path)
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "add-comment",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--bank",
            BANK_ID,
            "--comment-id",
            "evidence_needs_explanation",
            "--exclude-from-feedback",
            "--standard",
            "W.AW.11-12.1",
        ]
    ) == 0

    output = capsys.readouterr().out
    for expected in (
        "Selected review comment:",
        f"Class: {CLASS_ID}",
        f"Assignment: {ASSIGNMENT_ID}",
        f"Student: {STUDENT_ID}",
        f"Bank: {BANK_ID}",
        "Source comment: evidence_needs_explanation",
        "Review comment: comment_record_0001",
        "Include in feedback: no",
        "Review state: in_progress",
        "review.json",
    ):
        assert expected in output
    written = json.loads(
        review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert written["comments"][0]["include_in_feedback"] is False
    assert written["comments"][0]["standard_code"] == "W.AW.11-12.1"


def test_cli_handled_failure_returns_one_without_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    _write_bank(tmp_path)
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "add-comment",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--bank",
            BANK_ID,
            "--comment-id",
            "missing",
        ]
    ) == 1
    assert "could not select review comment" in capsys.readouterr().out
    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()

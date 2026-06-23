"""CLI tests for structured teacher review tags."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.review as cli_review
from quillan.review_record_paths import review_record_path
from tests.test_review_tags import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    _manifest,
    _review,
    _write_manifest,
    _write_review,
)


def test_cli_success_creates_tag_and_prints_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    monkeypatch.setattr(cli_review, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "add-tag",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--label",
            "Evidence needs explanation",
            "--polarity",
            "developing",
            "--severity",
            "2",
            "--note",
            "Explain the connection.",
            "--page",
            "1",
            "--evidence-id",
            "evidence_001",
            "--location-type",
            "paragraph",
            "--location-value",
            "2",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "Added review tag:" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert f"Student: {STUDENT_ID}" in output
    assert "Tag: tag_0001" in output
    assert "Polarity: developing" in output
    assert "Review state: in_progress" in output
    assert (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
        f"{STUDENT_ID}/review.json"
    ) in output
    written = json.loads(
        review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert written["tags"][0]["location"] == {
        "type": "paragraph",
        "value": 2,
    }
    assert written["tags"][0]["evidence_id"] == "evidence_001"


@pytest.mark.parametrize(
    ("prepare_submission", "label", "polarity"),
    [
        (True, " ", "neutral"),
        (True, "A tag", "mixed"),
        (False, "A tag", "neutral"),
    ],
)
def test_cli_handled_failure_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    prepare_submission: bool,
    label: str,
    polarity: str,
) -> None:
    if prepare_submission:
        _write_manifest(tmp_path)
    monkeypatch.setattr(cli_review, "resolve_workspace_root", lambda: tmp_path)

    result = main(
        [
            "add-tag",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--label",
            label,
            "--polarity",
            polarity,
        ]
    )

    assert result == 1
    assert "Error: could not add review tag:" in capsys.readouterr().out


def test_cli_append_preserves_existing_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_manifest(tmp_path)
    original = _review("ready_for_export")
    path = _write_review(tmp_path, copy.deepcopy(original))
    monkeypatch.setattr(cli_review, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "add-tag",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--label",
            "CLI append",
            "--polarity",
            "positive",
            "--location-type",
            "whole_submission",
        ]
    ) == 0

    written = json.loads(path.read_text(encoding="utf-8"))
    for field in ("notes", "scores", "comments", "module_details"):
        assert written[field] == original[field]
    assert written["tags"][:-1] == original["tags"]
    assert written["review_state"] == "ready_for_export"


def test_cli_does_not_mutate_submission_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path, _manifest())
    original = manifest_path.read_bytes()
    monkeypatch.setattr(cli_review, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "add-tag",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--label",
            "Page tag",
            "--polarity",
            "neutral",
            "--page",
            "2",
        ]
    ) == 0
    assert manifest_path.read_bytes() == original

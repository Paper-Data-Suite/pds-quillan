"""CLI tests for teacher-entered criterion review scores."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.review as cli_review
from quillan.review_record_paths import review_record_path
from tests.test_review_scores import _write_manifest, _write_review
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID, _review


def test_cli_success_creates_score_and_prints_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    monkeypatch.setattr(cli_review, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "set-score",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--criterion",
            "evidence",
            "--label",
            "Evidence",
            "--score",
            "3",
            "--max-score",
            "4",
            "--scale",
            "4_point",
            "--note",
            "Relevant but not fully explained.",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "Set review score:" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert f"Student: {STUDENT_ID}" in output
    assert "Criterion: evidence" in output
    assert "Score: 3 / 4" in output
    assert "Score record: score_0001" in output
    assert "Action: created" in output
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
    assert written["scores"][0]["criterion_id"] == "evidence"
    assert written["scores"][0]["scale"] == "4_point"


def test_cli_update_replaces_matching_criterion_and_preserves_other_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    original = _review("exported")
    original["scores"].append(
        {
            "score_id": "score_0002",
            "criterion_id": "organization",
            "label": "Organization",
            "score": 2,
            "max_score": 4,
            "updated_at": original["updated_at"],
            "module_details": {"preserve": True},
        }
    )
    path = _write_review(tmp_path, copy.deepcopy(original))
    monkeypatch.setattr(cli_review, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "set-score",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--criterion",
            "evidence",
            "--label",
            "Use of Evidence",
            "--score",
            "4",
            "--max-score",
            "5",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "Score record: score_0001" in output
    assert "Action: updated" in output
    written = json.loads(path.read_text(encoding="utf-8"))
    assert [item["criterion_id"] for item in written["scores"]].count("evidence") == 1
    assert written["scores"][0]["score_id"] == "score_0001"
    assert written["scores"][0]["score"] == 4
    assert written["scores"][1] == original["scores"][1]
    for field in ("notes", "tags", "comments", "module_details"):
        assert written[field] == original[field]
    assert written["review_state"] == "exported"


@pytest.mark.parametrize(
    ("score", "max_score"),
    [
        ("-1", "4"),
        ("nan", "4"),
        ("inf", "4"),
        ("not-a-number", "4"),
        ("3", "0"),
        ("3", "-1"),
        ("3", "nan"),
        ("3", "not-a-number"),
        ("5", "4"),
    ],
)
def test_cli_invalid_score_returns_one_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    score: str,
    max_score: str,
) -> None:
    _write_manifest(tmp_path)
    path = _write_review(tmp_path, _review())
    original = path.read_bytes()
    monkeypatch.setattr(cli_review, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "set-score",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--criterion",
            "evidence",
            "--label",
            "Evidence",
            "--score",
            score,
            "--max-score",
            max_score,
        ]
    ) == 1

    assert "Error: could not set review score:" in capsys.readouterr().out
    assert path.read_bytes() == original


@pytest.mark.parametrize(("criterion", "label"), [(" ", "Evidence"), ("evidence", " ")])
def test_cli_blank_text_and_missing_submission_return_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    criterion: str,
    label: str,
) -> None:
    _write_manifest(tmp_path)
    monkeypatch.setattr(cli_review, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "set-score",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--criterion",
            criterion,
            "--label",
            label,
            "--score",
            "3",
            "--max-score",
            "4",
        ]
    ) == 1
    assert "Error: could not set review score:" in capsys.readouterr().out


def test_cli_missing_submission_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_review, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "set-score",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--criterion",
            "evidence",
            "--label",
            "Evidence",
            "--score",
            "3",
            "--max-score",
            "4",
        ]
    ) == 1
    assert "does not exist" in capsys.readouterr().out

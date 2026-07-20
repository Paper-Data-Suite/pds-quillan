"""CLI tests for student-facing feedback export."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.cli import main
import quillan.cli_app.handlers.exports as cli_exports
from quillan.feedback_export import feedback_export_path, feedback_pdf_export_path
from tests.review_test_support import _write_manifest, _write_review
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID, _review


def test_cli_exports_feedback_and_prints_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    review = _review()
    review["overall_standard_ratings"].append(
        {
            "standard_id": "synthetic:W.A",
            "rating": 3,
            "rationale": "Uses evidence.",
            "include_in_feedback": True,
            "updated_at": review["updated_at"],
            "module_details": {},
        }
    )
    review["feedback"]["standard_feedback"].append(
        {
            "standard_id": "synthetic:W.A",
            "include_overall_rating": True,
            "include_overall_rationale": True,
            "included_observation_ids": [],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "custom",
                    "text": "Existing selected language.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": review["created_at"],
                    "module_details": {},
                },
                {
                    "feedback_comment_id": "feedback_comment_0002",
                    "source": "custom",
                    "text": "Excluded comment.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": False,
                    "created_at": review["created_at"],
                    "module_details": {},
                },
            ],
            "module_details": {},
        }
    )
    review_path = _write_review(tmp_path, review)
    review_before = review_path.read_bytes()
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        ["export-feedback", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    ) == 0

    output = capsys.readouterr().out
    assert "Exported student feedback:" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert f"Student: {STUDENT_ID}" in output
    assert "Included comments: 1" in output
    assert "Scores: 1" in output
    assert "Overwrote existing: no" in output
    relative = (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/submissions/"
        f"{STUDENT_ID}/exports/feedback.md"
    )
    assert f"Feedback file: {relative}" in output
    content = feedback_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).read_text(encoding="utf-8")
    assert "Existing selected language." in content
    assert "Excluded comment." not in content
    assert "### synthetic:W.A" in content
    assert "Rating: 3" in content
    assert "Rationale:\nUses evidence." in content
    assert review_path.read_bytes() == review_before


def test_cli_missing_review_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    assert main(
        ["export-feedback", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    ) == 1
    assert "Review record does not exist" in capsys.readouterr().out


def test_cli_exports_pdf_feedback_and_prints_pdf_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    _write_review(tmp_path, _review("feedback_composed"))
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "export-feedback",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--format",
            "pdf",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "Exported student feedback PDF:" in output
    assert "Focus Standard ratings:" in output
    assert "PDF file:" in output
    assert feedback_pdf_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).is_file()


def test_cli_overwrite_flag_controls_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    review_path = _write_review(tmp_path, _review())
    review_before = review_path.read_bytes()
    output_path = feedback_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    output_path.parent.mkdir(parents=True)
    output_path.write_text("manual edit", encoding="utf-8")
    monkeypatch.setattr(cli_exports, "resolve_workspace_root", lambda: tmp_path)
    command = ["export-feedback", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]

    assert main(command) == 1
    assert output_path.read_text(encoding="utf-8") == "manual edit"
    assert main([*command, "--overwrite"]) == 0

    output = capsys.readouterr().out
    assert "Use --overwrite" in output
    assert "Overwrote existing: yes" in output
    assert output_path.read_text(encoding="utf-8").startswith("# Feedback")
    assert review_path.read_bytes() == review_before

"""Direct CLI coverage for Focus Standard feedback composition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.cli import main
from quillan.cli_app.handlers import feedback as handlers
from quillan.review_record_paths import review_record_path
from quillan.review_record_paths import write_review_record
from tests.test_review_feedback import _fresh_review, _write_comment_set
from tests.test_review_ratings import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    _write_workspace,
)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_workspace(tmp_path, None)
    review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).unlink()
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _write_review(workspace: Path, review: dict[str, Any]) -> Path:
    return write_review_record(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID), review
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["feedback", "--help"],
        ["feedback", "show", "--help"],
        ["feedback", "set-options", "--help"],
        ["feedback", "add-comment", "--help"],
        ["feedback", "use-reusable-comment", "--help"],
        ["feedback", "mark-composed", "--help"],
    ],
)
def test_feedback_help_exits_successfully(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 0


def test_bare_feedback_prints_help_without_resolving_workspace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        handlers, "resolve_workspace_root", lambda: pytest.fail("resolved workspace")
    )
    assert main(["feedback"]) == 0
    output = capsys.readouterr().out
    assert "{show,set-options,add-comment,use-reusable-comment,mark-composed}" in output


def test_show_without_review_is_ordered_read_only(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assignment = workspace / "classes" / CLASS_ID / "modules" / "quillan" / "work" / ASSIGNMENT_ID / "assignment.json"
    submission = assignment.parent / "submissions" / STUDENT_ID / "submission.json"
    before = assignment.read_bytes(), submission.read_bytes()
    assert main(["feedback", "show", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]) == 0
    output = capsys.readouterr().out
    assert "Review state: not_started" in output
    assert "Configured feedback records: 0" in output
    assert "Missing feedback records: 2" in output
    assert output.index("njsls-ela:W.1") < output.index("njsls-ela:L.2")
    assert output.count("Feedback record exists: no") == 2
    assert not review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()
    assert (assignment.read_bytes(), submission.read_bytes()) == before


def test_set_options_replaces_selection_and_rejects_excluded_observation(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_review(workspace, _fresh_review())
    path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    base = [
        "feedback", "set-options", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID,
        "--standard-id", "njsls-ela:W.1", "--include-overall-rating", "true",
        "--include-overall-rationale", "false",
    ]
    assert main([*base, "--observation-ids", "observation_0001"]) == 0
    assert "Action: created" in capsys.readouterr().out
    assert main(base) == 0
    review = json.loads(path.read_text(encoding="utf-8"))
    assert review["feedback"]["standard_feedback"][0]["included_observation_ids"] == []
    before = path.read_bytes()
    assert main([*base, "--observation-ids", "observation_0003"]) == 1
    assert "excluded from feedback eligibility" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_add_comment_preserves_exact_inner_text_and_requires_reuse_scope(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_review(workspace, _fresh_review())
    args = [
        "feedback", "add-comment", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID,
        "--standard-id", "njsls-ela:W.1", "--text", "  Keep\nTHIS punctuation!  ",
        "--include-in-feedback", "false",
    ]
    assert main(args) == 0
    path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    review = json.loads(path.read_text(encoding="utf-8"))
    assert review["feedback"]["standard_feedback"][0]["comments"][0]["text"] == "Keep\nTHIS punctuation!"
    before = path.read_bytes()
    assert main([*args, "--purpose", "general"]) == 1
    assert "require --save-for-reuse" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_reusable_selection_is_snapshot_and_increments_usage(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review = _fresh_review()
    review["overall_standard_ratings"] = [{
        "standard_id": "njsls-ela:W.1", "rating": 2, "rationale": None,
        "include_in_feedback": True, "updated_at": review["updated_at"], "module_details": {},
    }]
    _write_review(workspace, review)
    _write_comment_set(workspace)
    args = [
        "feedback", "use-reusable-comment", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID,
        "--standard-id", "njsls-ela:W.1", "--comment-set-id", "synthetic_argument_focus_comments",
        "--comment-id", "claim_next_step", "--include-in-feedback", "true",
    ]
    assert main(args) == 0
    assert "feedback_comment_0001" in capsys.readouterr().out
    review = json.loads(review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(encoding="utf-8"))
    assert review["feedback"]["standard_feedback"][0]["comments"][0]["text"] == "Explain why this evidence supports your claim."
    comment_set = json.loads((workspace / "shared" / "focus_standard_comments" / "synthetic_argument_focus_comments.json").read_text(encoding="utf-8"))
    assert comment_set["comments"][0]["usage"]["times_used"] == 1


def test_mark_composed_requires_yes_without_argparse_prompt(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_review(workspace, _fresh_review())
    path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    before = path.read_bytes()
    base = ["feedback", "mark-composed", CLASS_ID, ASSIGNMENT_ID, STUDENT_ID]
    assert main(base) == 1
    assert "--yes is required" in capsys.readouterr().out
    assert path.read_bytes() == before
    assert main([*base, "--yes"]) == 0
    assert json.loads(path.read_text(encoding="utf-8"))["review_state"] == "feedback_composed"

"""Tests for direct reusable Focus Standard comment management commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import quillan.cli_app.handlers.comments as cli_comments
from quillan.cli import main
from quillan.comment_management import create_manual_reusable_comment
from quillan.focus_standard_comments import (
    FocusStandardCommentError,
    focus_standard_comment_set_path,
    load_comment_set,
)

TIMESTAMP = "2026-07-13T12:00:00+00:00"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cli_comments, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


def _create(
    workspace: Path,
    *,
    comment_set_id: str = "argument_comments",
    profile_id: str = "profile_a",
    writing_type: str = "argument",
    standard_id: str = "W.1",
    label: str = "Explain evidence",
    text: str = "Explain how the evidence supports your claim.",
    purpose: str = "next_step",
    ratings: list[int | float] | None = None,
    tags: list[str] | None = None,
) -> None:
    create_manual_reusable_comment(
        workspace,
        comment_set_id=comment_set_id,
        standards_profile_id=profile_id,
        writing_type=writing_type,
        standard_id=standard_id,
        label=label,
        text=text,
        purpose=purpose,
        rating_values=ratings,
        teacher_tags=tags,
        created_at=TIMESTAMP,
    )


def test_comments_help_and_bare_namespace_do_not_resolve_workspace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_if_called() -> Path:
        raise AssertionError("workspace resolution must not run for namespace help")

    monkeypatch.setattr(cli_comments, "resolve_workspace_root", fail_if_called)

    assert main(["comments"]) == 0
    namespace_help = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert all(command in namespace_help for command in ("list", "show", "create"))
    for arguments in (
        ["--help"],
        ["comments", "--help"],
        ["comments", "list", "--help"],
        ["comments", "show", "--help"],
        ["comments", "create", "--help"],
    ):
        with pytest.raises(SystemExit) as result:
            main(arguments)
        assert result.value.code == 0


def test_empty_list_is_successful_and_does_not_create_directory(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = workspace / "shared" / "focus_standard_comments"

    assert main(["comments", "list"]) == 0

    assert "No reusable Focus Standard comments matched." in (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert not directory.exists()


def test_show_missing_set_fails_without_creating_files(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["comments", "show", "missing_set"]) == 1
    assert "Error:" in (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert not (workspace / "shared").exists()


def test_create_new_set_preserves_text_and_normalizes_metadata(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(
        [
            "comments",
            "create",
            "argument_comments",
            "--profile-id",
            " profile_a ",
            "--writing-type",
            " argument ",
            "--standard-id",
            " W.1 ",
            "--label",
            " Explain Evidence ",
            "--text",
            "  Keep THIS punctuation!\nAnd this line.  ",
            "--purpose",
            "evidence",
            "--rating-values=-1,0,2.5",
            "--teacher-tags",
            "Scene Development,Dialogue,scene development",
        ]
    ) == 0

    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "Comment set: created" in output
    assert "Comment ID: explain_evidence" in output
    assert "Rating values: -1, 0, 2.5" in output
    assert "Teacher tags: scene_development, dialogue" in output
    path = focus_standard_comment_set_path(workspace, "argument_comments")
    data = load_comment_set(path)
    comment = data["comments"][0]
    assert data["description"] == (
        "Reusable teacher-authored Focus Standard comments managed by Quillan."
    )
    assert data["standards_profile_id"] == "profile_a"
    assert data["writing_types"] == ["argument"]
    assert data["grade_band"] is None
    assert comment["text"] == "Keep THIS punctuation!\nAnd this line."
    assert comment["source"] == {
        "type": "manual",
        "class_id": None,
        "assignment_id": None,
        "student_id": None,
        "review_path": None,
        "feedback_comment_id": None,
        "saved_at": comment["created_at"],
    }
    assert comment["active"] is True
    assert comment["student_facing"] is True
    assert comment["usage"] == {"times_used": 0, "last_used_at": None}
    assert sorted(path.parent.iterdir()) == [path]


def test_create_appends_collision_safe_id_and_preserves_existing_data(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create(workspace)
    path = focus_standard_comment_set_path(workspace, "argument_comments")
    before = load_comment_set(path)

    assert main(
        [
            "comments",
            "create",
            "argument_comments",
            "--profile-id",
            "profile_a",
            "--writing-type",
            "argument",
            "--standard-id",
            "W.1",
            "--label",
            "Explain evidence",
            "--text",
            "A second reusable comment.",
        ]
    ) == 0

    assert "Comment ID: explain_evidence_2" in (lambda captured: captured.out + captured.err)(capsys.readouterr())
    after = load_comment_set(path)
    assert after["comments"][0] == before["comments"][0]
    assert after["created_at"] == before["created_at"]
    assert len(after["comments"]) == 2


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--profile-id", "other_profile", "standards_profile_id"),
        ("--writing-type", "narrative", "writing_type"),
    ],
)
def test_incompatible_append_is_byte_for_byte_unchanged(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    option: str,
    value: str,
    message: str,
) -> None:
    _create(workspace)
    path = focus_standard_comment_set_path(workspace, "argument_comments")
    before = path.read_bytes()
    arguments = [
        "comments",
        "create",
        "argument_comments",
        "--profile-id",
        "profile_a",
        "--writing-type",
        "argument",
        "--standard-id",
        "W.1",
        "--label",
        "Another",
        "--text",
        "Another comment.",
    ]
    arguments[arguments.index(option) + 1] = value

    assert main(arguments) == 1

    assert message in (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert path.read_bytes() == before


def test_list_filters_visibility_order_and_reports_invalid_files(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create(
        workspace,
        comment_set_id="z_set",
        ratings=[2.5],
        tags=["Evidence"],
        text="Z text.",
    )
    _create(
        workspace,
        comment_set_id="a_set",
        ratings=[],
        text="A first text.",
    )
    _create(
        workspace,
        comment_set_id="a_set",
        label="Second stored",
        text="A second text.",
    )
    a_path = focus_standard_comment_set_path(workspace, "a_set")
    data: dict[str, Any] = json.loads(a_path.read_text(encoding="utf-8"))
    data["comments"][1]["active"] = False
    a_path.write_text(json.dumps(data), encoding="utf-8")
    invalid_path = a_path.parent / "broken.json"
    invalid_path.write_text("{", encoding="utf-8")
    before = {path: path.read_bytes() for path in a_path.parent.iterdir()}

    assert main(
        [
            "comments",
            "list",
            "--profile-id",
            "profile_a",
            "--writing-type",
            "argument",
            "--standard-id",
            "W.1",
            "--rating-value",
            "2.5",
        ]
    ) == 1

    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert output.index("Comment set ID: a_set") < output.index("Comment set ID: z_set")
    assert "A first text." in output
    assert "A second text." not in output
    assert "Z text." in output
    assert "Purpose: next_step" in output
    assert "Teacher tags: evidence" in output
    assert "Usage count: 0" in output
    assert "shared/focus_standard_comments/z_set.json" in output
    assert "Invalid reusable Focus Standard comment sets:" in output
    assert "broken.json" in output
    assert {path: path.read_bytes() for path in a_path.parent.iterdir()} == before


def test_show_includes_inactive_teacher_only_and_is_read_only(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create(workspace)
    path = focus_standard_comment_set_path(workspace, "argument_comments")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["comments"][0]["active"] = False
    data["comments"][0]["student_facing"] = False
    path.write_text(json.dumps(data), encoding="utf-8")
    before = path.read_bytes()

    assert main(["comments", "show", "argument_comments"]) == 0

    output = (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert "Description:" in output
    assert "Comment count: 1" in output
    assert "Student-facing: no" in output
    assert "Active: no" in output
    assert "Source type: manual" in output
    assert "Source student ID: none" in output
    assert "Usage count: 0" in output
    assert "Module details:" in output
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "rating_values", ["1,1", "1,,2", "text", "NaN", "inf", "-inf"]
)
def test_create_rejects_invalid_rating_lists_without_writing(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
    rating_values: str,
) -> None:
    result = main(
        [
            "comments",
            "create",
            "argument_comments",
            "--profile-id",
            "profile_a",
            "--writing-type",
            "argument",
            "--standard-id",
            "W.1",
            "--label",
            "Label",
            "--text",
            "Text",
            f"--rating-values={rating_values}",
        ]
    )

    assert result == 1
    assert "Error:" in (lambda captured: captured.out + captured.err)(capsys.readouterr())
    assert not (workspace / "shared").exists()


def test_manual_service_rejects_blank_and_unusable_values(tmp_path: Path) -> None:
    with pytest.raises(FocusStandardCommentError, match="label"):
        _create(tmp_path, label=" ")
    with pytest.raises(FocusStandardCommentError, match="letters or numbers"):
        _create(tmp_path, tags=["---"])

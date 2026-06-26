"""Tests for teacher-facing comment-bank workflows."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import quillan.comment_bank_workflows as workflows
from quillan.comment_banks import load_comment_bank
from quillan.comment_bank_writing import (
    build_comment,
    build_comment_bank,
    build_comment_category,
    write_comment_bank,
)


def _menu_input(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> None:
    response_iterator: Iterator[str] = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(response_iterator)
        except StopIteration as error:
            raise AssertionError(
                "Menu requested more input than the test provided."
            ) from error

    monkeypatch.setattr("builtins.input", fake_input)


def _patch_workspace(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: root)


def _sample_bank(bank_id: str = "general_comments") -> dict[str, Any]:
    category = build_comment_category(
        category_id="reasoning",
        label="Reasoning / Explanation",
        description="Comments about reasoning.",
    )
    comment = build_comment(
        comment_id="explain_more",
        label="Explain more",
        text="Explain your reasoning more fully.",
        category_id="reasoning",
        polarity="developing",
    )
    return build_comment_bank(
        bank_id=bank_id,
        title="General Comments",
        description="Reusable synthetic comments.",
        writing_types=["general", "reflection"],
        categories=[category],
        comments=[comment],
    )


def test_create_comment_bank_writes_valid_minimal_bank(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "General Written Response Comments",
            "",
            "Reusable comments for written responses across subjects.",
            "general, constructed_response",
            "5",
            "",
            "",
            "Explanation needs more detail",
            "",
            "Your response identifies the idea, but explain your reasoning more fully.",
            "1",
            "2",
            "",
            "",
            "",
            "1",
        ],
    )

    assert workflows.prompt_create_comment_bank() == 0

    path = (
        tmp_path
        / "shared"
        / "comment_banks"
        / "general_written_response_comments.json"
    )
    bank = load_comment_bank(path)
    assert bank["bank_id"] == path.stem
    assert bank["categories"]
    assert bank["comments"]
    assert bank["comments"][0]["polarity"] == "developing"
    assert bank["comments"][0]["include_in_feedback_default"] is True
    assert bank["comments"][0]["student_facing"] is True
    assert bank["created_at"].endswith("+00:00")
    assert bank["updated_at"].endswith("+00:00")
    output = capsys.readouterr().out
    assert "Saved comment bank" in output


def test_create_cancel_before_save_writes_no_partial_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "General Written Response Comments",
            "",
            "Reusable comments.",
            "general",
            "1",
            "",
            "",
            "Useful detail",
            "",
            "This detail helps the reader follow your thinking.",
            "1",
            "1",
            "",
            "",
            "",
            "2",
        ],
    )

    assert workflows.prompt_create_comment_bank() == 1

    capsys.readouterr()
    assert not (tmp_path / "shared" / "comment_banks").exists()


def test_create_existing_bank_requires_exact_overwrite_confirmation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = _sample_bank("general_written_response_comments")
    path = write_comment_bank(tmp_path, existing)
    before = path.read_bytes()
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "General Written Response Comments",
            "",
            "New description.",
            "general",
            "1",
            "",
            "",
            "New comment",
            "",
            "A new comment text.",
            "1",
            "4",
            "",
            "",
            "",
            "1",
            "overwrite",
        ],
    )

    assert workflows.prompt_create_comment_bank() == 1

    output = capsys.readouterr().out
    assert "existing comment bank was not changed" in output
    assert path.read_bytes() == before


def test_view_comment_banks_lists_valid_and_invalid_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_comment_bank(tmp_path, _sample_bank())
    invalid = tmp_path / "shared" / "comment_banks" / "draft.json"
    invalid.write_text(json.dumps({"bank_id": "draft"}), encoding="utf-8")
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1"])

    assert workflows.prompt_view_comment_banks() == 0

    output = capsys.readouterr().out
    assert "general_comments - General Comments" in output
    assert "Invalid comment bank files" in output
    assert "draft.json" in output
    assert "Comments: 1" in output


def test_edit_comment_bank_updates_title_and_preserves_created_at(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_comment_bank(tmp_path, _sample_bank())
    before = load_comment_bank(path)
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1", "1", "Updated General Comments"])

    assert workflows.prompt_edit_comment_bank() == 0

    after = load_comment_bank(path)
    assert after["title"] == "Updated General Comments"
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] >= before["updated_at"]
    capsys.readouterr()


def test_add_category_rejects_duplicate_without_changing_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_comment_bank(tmp_path, _sample_bank())
    before = path.read_bytes()
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1", "3", "reasoning", ""])

    assert workflows.prompt_add_category() == 1

    output = capsys.readouterr().out
    assert "Duplicate category_id" in output
    assert path.read_bytes() == before


def test_add_comment_stores_required_fields_and_validates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_comment_bank(tmp_path, _sample_bank())
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "1",
            "Needs clearer evidence",
            "",
            "Add a specific example or detail to support this point.",
            "1",
            "2",
            "2",
            "1",
            "",
            "1",
        ],
    )

    assert workflows.prompt_add_comment() == 0

    bank = load_comment_bank(path)
    added = bank["comments"][-1]
    assert added["comment_id"] == "needs_clearer_evidence"
    assert added["polarity"] == "developing"
    assert added["include_in_feedback_default"] is False
    assert added["student_facing"] is True
    assert added["module_details"] == {}
    capsys.readouterr()


def test_validate_comment_bank_reports_invalid_without_modifying_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "shared" / "comment_banks"
    directory.mkdir(parents=True)
    invalid = directory / "draft.json"
    invalid.write_text("{", encoding="utf-8")
    before = invalid.read_bytes()
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1"])

    assert workflows.prompt_validate_comment_bank() == 1

    output = capsys.readouterr().out
    assert "Comment bank is invalid." in output
    assert "not valid JSON" in output
    assert invalid.read_bytes() == before

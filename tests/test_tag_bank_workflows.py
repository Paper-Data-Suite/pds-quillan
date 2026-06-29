"""Tests for teacher-facing tag-bank workflows."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import quillan.tag_bank_workflows as workflows
from quillan.tag_banks import load_tag_bank
from quillan.tag_bank_writing import (
    build_tag_bank,
    build_tag_category,
    build_tag_template,
    write_tag_bank,
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


def _sample_bank(tag_bank_id: str = "general_tags") -> dict[str, Any]:
    category = build_tag_category(
        category_id="reasoning",
        label="Reasoning / Explanation",
        description="Teacher observations about reasoning.",
    )
    tag = build_tag_template(
        tag_template_id="explain_more",
        label="Explain more",
        category_id="reasoning",
        polarity="developing",
    )
    return build_tag_bank(
        tag_bank_id=tag_bank_id,
        title="General Tags",
        description="Reusable synthetic tags.",
        writing_types=["general", "reflection"],
        categories=[category],
        tags=[tag],
    )


def test_create_tag_bank_writes_valid_minimal_bank(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "General Written Response Tags",
            "",
            "Reusable observations for written responses across subjects.",
            "general, constructed_response",
            "3",
            "",
            "",
            "Explanation needs more detail",
            "",
            "1",
            "2",
            "",
            "1",
        ],
    )

    assert workflows.prompt_create_tag_bank() == 0

    path = tmp_path / "shared" / "tag_banks" / "general_written_response_tags.json"
    bank = load_tag_bank(path)
    assert bank["tag_bank_id"] == path.stem
    assert bank["categories"]
    assert bank["tags"]
    assert bank["tags"][0]["polarity"] == "developing"
    assert bank["created_at"].endswith("+00:00")
    assert "Saved tag bank" in capsys.readouterr().out


def test_create_cancel_before_save_writes_no_partial_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "General Written Response Tags",
            "",
            "Reusable observations.",
            "general",
            "1",
            "",
            "",
            "Useful detail",
            "",
            "1",
            "1",
            "",
            "2",
        ],
    )

    assert workflows.prompt_create_tag_bank() == 1

    capsys.readouterr()
    assert not (tmp_path / "shared" / "tag_banks").exists()


def test_create_existing_bank_requires_exact_overwrite_confirmation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = _sample_bank("general_written_response_tags")
    path = write_tag_bank(tmp_path, existing)
    before = path.read_bytes()
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "General Written Response Tags",
            "",
            "New description.",
            "general",
            "1",
            "",
            "",
            "New tag",
            "",
            "1",
            "4",
            "",
            "1",
            "overwrite",
        ],
    )

    assert workflows.prompt_create_tag_bank() == 1

    output = capsys.readouterr().out
    assert "existing tag bank was not changed" in output
    assert path.read_bytes() == before


def test_view_tag_banks_lists_valid_and_invalid_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_tag_bank(tmp_path, _sample_bank())
    invalid = tmp_path / "shared" / "tag_banks" / "draft.json"
    invalid.write_text(json.dumps({"tag_bank_id": "draft"}), encoding="utf-8")
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1"])

    assert workflows.prompt_view_tag_banks() == 0

    output = capsys.readouterr().out
    assert "general_tags - General Tags" in output
    assert "Invalid tag bank files" in output
    assert "draft.json" in output
    assert "Tags: 1" in output


def test_add_tag_template_stores_optional_metadata(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_tag_bank(tmp_path, _sample_bank())
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "1",
            "Needs clearer evidence",
            "",
            "1",
            "2",
            "y",
            "Evidence description.",
            "general",
            "standard-1",
            "criterion_1",
            "2",
            "What evidence needs clarification?",
            "10",
            "1",
        ],
    )

    assert workflows.prompt_add_tag_template() == 0

    bank = load_tag_bank(path)
    added = bank["tags"][-1]
    assert added["tag_template_id"] == "needs_clearer_evidence"
    assert added["standard_ids"] == ["standard-1"]
    assert added["criterion_ids"] == ["criterion_1"]
    assert added["severity_default"] == 2
    assert added["teacher_note_prompt"] == "What evidence needs clarification?"
    assert "student_facing_default" not in added
    capsys.readouterr()


def test_tag_bank_menu_uses_teacher_facing_language(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _menu_input(monkeypatch, ["7"])

    assert workflows.launch_tag_banks_menu() == 0

    output = capsys.readouterr().out
    assert "Add reusable tag" in output
    assert "Add tag template" not in output
    assert "Implemented in #166" not in output
    assert "Opening this screen" not in output


def test_validate_tag_bank_reports_invalid_without_modifying_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "shared" / "tag_banks"
    directory.mkdir(parents=True)
    invalid = directory / "draft.json"
    invalid.write_text("{", encoding="utf-8")
    before = invalid.read_bytes()
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1"])

    assert workflows.prompt_validate_tag_bank() == 1

    output = capsys.readouterr().out
    assert "Tag bank is invalid." in output
    assert "not valid JSON" in output
    assert invalid.read_bytes() == before

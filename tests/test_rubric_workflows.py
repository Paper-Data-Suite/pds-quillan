"""Tests for teacher-facing rubric workflows."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import quillan.rubric_workflows as workflows
from quillan.rubrics import load_rubric
from quillan.rubric_writing import (
    build_rubric,
    build_rubric_criterion,
    build_rubric_level,
    write_rubric,
)


def _menu_input(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> None:
    response_iterator: Iterator[str] = iter(responses)

    def fake_input(_prompt: str = "") -> str:
        try:
            return next(response_iterator)
        except StopIteration as error:
            raise AssertionError("Menu requested unexpected input.") from error

    monkeypatch.setattr("builtins.input", fake_input)


def _patch_workspace(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(workflows, "resolve_workspace_root", lambda: root)


def _sample_rubric(rubric_id: str = "general_response") -> dict[str, Any]:
    level = build_rubric_level(score=3, label="Clear")
    criterion = build_rubric_criterion(
        criterion_id="reasoning",
        label="Reasoning / Explanation",
        max_score=4,
        scale="4_point",
        levels=[level],
    )
    return build_rubric(
        rubric_id=rubric_id,
        title="General Response",
        description="Synthetic rubric.",
        writing_types=["general"],
        criteria=[criterion],
    )


def test_create_rubric_writes_valid_minimal_rubric(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "General Constructed Response 4-Point Rubric",
            "",
            "Reusable scoring profile.",
            "general, constructed_response",
            "3",
            "",
            "4",
            "4_point",
            "",
            "",
            "3",
            "Clear explanation",
            "Clear reasoning.",
            "Your explanation is clear.",
            "",
            "",
            "1",
        ],
    )

    assert workflows.prompt_create_rubric() == 0

    path = (
        tmp_path
        / "shared"
        / "rubrics"
        / "general_constructed_response_4-point_rubric.json"
    )
    rubric = load_rubric(path)
    assert rubric["rubric_id"] == path.stem
    assert rubric["criteria"]
    assert rubric["criteria"][0]["levels"]
    assert "Saved rubric" in capsys.readouterr().out


def test_create_cancel_before_save_writes_no_partial_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(
        monkeypatch,
        [
            "General Rubric",
            "",
            "Reusable scoring profile.",
            "general",
            "1",
            "",
            "4",
            "4_point",
            "",
            "",
            "3",
            "Accurate",
            "",
            "",
            "",
            "",
            "2",
        ],
    )

    assert workflows.prompt_create_rubric() == 1

    capsys.readouterr()
    assert not (tmp_path / "shared" / "rubrics").exists()


def test_view_rubrics_lists_valid_and_invalid_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_rubric(tmp_path, _sample_rubric())
    invalid = tmp_path / "shared" / "rubrics" / "draft.json"
    invalid.write_text(json.dumps({"rubric_id": "draft"}), encoding="utf-8")
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1"])

    assert workflows.prompt_view_rubrics() == 0

    output = capsys.readouterr().out
    assert "general_response - General Response" in output
    assert "Invalid rubric files" in output
    assert "draft.json" in output
    assert "Levels: 1" in output


def test_add_level_rejects_duplicate_without_modifying_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_rubric(tmp_path, _sample_rubric())
    before = path.read_bytes()
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1", "1", "3"])

    assert workflows.prompt_add_level() == 1

    assert "Duplicate level score" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_validate_rubric_reports_invalid_without_modifying_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "shared" / "rubrics"
    directory.mkdir(parents=True)
    invalid = directory / "draft.json"
    invalid.write_text("{", encoding="utf-8")
    before = invalid.read_bytes()
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1"])

    assert workflows.prompt_validate_rubric() == 1

    output = capsys.readouterr().out
    assert "Rubric is invalid." in output
    assert "not valid JSON" in output
    assert invalid.read_bytes() == before

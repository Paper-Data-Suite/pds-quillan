"""Tests for synthetic starter review materials."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

import quillan.starter_material_workflows as workflows
from quillan.assignment_workflows import resolve_assignment_rubric
from quillan.comment_bank_writing import list_valid_comment_banks
from quillan.comment_banks import load_comment_bank
from quillan.rubric_writing import list_valid_rubrics
from quillan.rubrics import load_rubric
from quillan.starter_materials import (
    discover_starter_materials,
    install_starter_materials,
    summarize_install_impact,
    target_path_for_material,
    validate_all_starter_materials,
)
from quillan.tag_bank_writing import list_valid_tag_banks
from quillan.tag_banks import load_tag_bank


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


def _file_tree(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
    entries: list[tuple[str, str, bytes | None]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            entries.append(("file", relative, path.read_bytes()))
        elif path.is_dir():
            entries.append(("dir", relative, None))
    return tuple(entries)


def test_every_starter_material_validates_and_id_matches_filename() -> None:
    materials = discover_starter_materials()

    assert len(materials) == 15
    assert all(result.is_valid for result in validate_all_starter_materials(materials))
    for material in materials:
        if material.kind == "comment_bank":
            data = load_comment_bank(material.source_path)
            assert data["bank_id"] == material.source_path.stem
        elif material.kind == "tag_bank":
            data = load_tag_bank(material.source_path)
            assert data["tag_bank_id"] == material.source_path.stem
        else:
            data = load_rubric(material.source_path)
            assert data["rubric_id"] == material.source_path.stem
        assert "Synthetic starter" in data["description"]
        assert not any("standard_ids" in item for item in data.get("comments", []))
        assert not any("standard_ids" in item for item in data.get("tags", []))
        assert not any("standard_ids" in item for item in data.get("criteria", []))


def test_starter_materials_avoid_obvious_real_or_placeholder_content() -> None:
    forbidden_fragments = (
        "@",
        "TODO",
        "real student",
        "real teacher",
        "class roster",
        "student name",
        "school district",
        "english12_p3",
        "villainy",
    )

    for material in discover_starter_materials():
        text = material.source_path.read_text(encoding="utf-8")
        folded = text.casefold()
        assert all(fragment.casefold() not in folded for fragment in forbidden_fragments)


def test_install_all_copies_only_review_material_files(tmp_path: Path) -> None:
    materials = discover_starter_materials()

    result = install_starter_materials(tmp_path, materials)

    assert len(result.installed) == 15
    assert not result.skipped_existing
    assert len(list_valid_comment_banks(tmp_path)) == 5
    assert len(list_valid_tag_banks(tmp_path)) == 5
    assert len(list_valid_rubrics(tmp_path)) == 5
    assert sorted(path.relative_to(tmp_path).parts[:2] for path in result.installed) == [
        ("shared", "comment_banks"),
        ("shared", "comment_banks"),
        ("shared", "comment_banks"),
        ("shared", "comment_banks"),
        ("shared", "comment_banks"),
        ("shared", "rubrics"),
        ("shared", "rubrics"),
        ("shared", "rubrics"),
        ("shared", "rubrics"),
        ("shared", "rubrics"),
        ("shared", "tag_banks"),
        ("shared", "tag_banks"),
        ("shared", "tag_banks"),
        ("shared", "tag_banks"),
        ("shared", "tag_banks"),
    ]
    assert not (tmp_path / "classes").exists()
    assert not (tmp_path / "assignments").exists()
    assert not (tmp_path / "scans").exists()
    assert not (tmp_path / "exports").exists()
    assert not (tmp_path / "shared" / "standards").exists()
    assert not list(tmp_path.rglob("submission.json"))
    assert not list(tmp_path.rglob("review.json"))


def test_install_skips_existing_by_default_and_exact_overwrite_replaces(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    material = discover_starter_materials()[0]
    target = target_path_for_material(tmp_path, material)
    target.parent.mkdir(parents=True)
    target.write_text('{"existing": true}\n', encoding="utf-8")
    before = target.read_bytes()

    result = install_starter_materials(tmp_path, (material,))

    assert result.installed == ()
    assert result.skipped_existing == (target,)
    assert target.read_bytes() == before

    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1", "2", "overwrite"])

    assert workflows.prompt_install_selected_starter_materials() == 1
    assert target.read_bytes() == before
    assert "Overwrite canceled" in capsys.readouterr().out

    _menu_input(monkeypatch, ["1", "2", "OVERWRITE"])

    assert workflows.prompt_install_selected_starter_materials() == 0
    assert target.read_bytes() != before
    assert load_comment_bank(target)["bank_id"] == material.material_id


def test_install_summary_counts_existing_files(tmp_path: Path) -> None:
    materials = discover_starter_materials()[:3]
    target_path_for_material(tmp_path, materials[0]).parent.mkdir(parents=True)
    target_path_for_material(tmp_path, materials[0]).write_text("{}", encoding="utf-8")

    summary = summarize_install_impact(tmp_path, materials)

    assert summary.new_files == 2
    assert summary.existing_files == 1
    assert summary.overwrite_files == 1


def test_install_selected_one_of_each_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1,6,11", "1"])

    assert workflows.prompt_install_selected_starter_materials() == 0

    assert len(list((tmp_path / "shared" / "comment_banks").glob("*.json"))) == 1
    assert len(list((tmp_path / "shared" / "tag_banks").glob("*.json"))) == 1
    assert len(list((tmp_path / "shared" / "rubrics").glob("*.json"))) == 1


def test_invalid_selected_install_is_rejected_without_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    before = _file_tree(tmp_path)
    _menu_input(monkeypatch, ["1,99"])

    assert workflows.prompt_install_selected_starter_materials() == 1

    assert _file_tree(tmp_path) == before
    assert "Invalid selection" in capsys.readouterr().out


def test_cancel_paths_create_no_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    before = _file_tree(tmp_path)
    _menu_input(monkeypatch, ["2"])

    assert workflows.prompt_install_all_starter_materials() == 1

    _menu_input(monkeypatch, ["b"])

    assert workflows.prompt_install_selected_starter_materials() == 1
    assert _file_tree(tmp_path) == before


def test_preview_and_validate_workflows_report_material_groups(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)

    assert workflows.prompt_preview_starter_materials() == 0
    assert workflows.prompt_validate_starter_materials() == 0

    output = capsys.readouterr().out
    assert "Comment Banks" in output
    assert "Tag Banks" in output
    assert "Rubrics / Scoring Profiles" in output
    assert "OK general_written_response.json" in output
    assert "OK general_written_response_tags.json" in output
    assert "OK general_constructed_response.json" in output


def test_starter_materials_submenu_preview_and_back(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    _menu_input(monkeypatch, ["1", "", "5"])

    assert workflows.launch_starter_materials_menu() == 0

    output = capsys.readouterr().out
    assert "Preview starter materials" in output
    assert "General Written Response Comments" in output


def test_installed_materials_are_discoverable_by_review_helpers(
    tmp_path: Path,
) -> None:
    install_starter_materials(tmp_path, discover_starter_materials())

    comment_bank_ids = {
        item.bank["bank_id"]
        for item in list_valid_comment_banks(tmp_path)
        if item.bank is not None
    }
    tag_bank_ids = {
        item.bank["tag_bank_id"]
        for item in list_valid_tag_banks(tmp_path)
        if item.bank is not None
    }
    rubric_ids = {
        item.rubric["rubric_id"]
        for item in list_valid_rubrics(tmp_path)
        if item.rubric is not None
    }

    assert "general_written_response" in comment_bank_ids
    assert "general_written_response_tags" in tag_bank_ids
    assert "general_constructed_response" in rubric_ids
    assignment = {
        "rubric_id": "general_constructed_response",
        "assignment_id": "synthetic_assignment",
        "class_ids": ["synthetic_class"],
        "standards_profile_id": "synthetic_profile",
    }
    resolved = resolve_assignment_rubric(tmp_path, assignment)
    assert resolved is not None
    assert resolved["rubric_id"] == "general_constructed_response"


def test_installed_json_matches_sources_exactly(tmp_path: Path) -> None:
    materials = discover_starter_materials()
    install_starter_materials(tmp_path, materials)

    for material in materials:
        target = target_path_for_material(tmp_path, material)
        assert json.loads(target.read_text(encoding="utf-8")) == json.loads(
            material.source_path.read_text(encoding="utf-8")
        )

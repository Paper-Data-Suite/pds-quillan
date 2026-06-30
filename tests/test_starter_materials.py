"""Tests for synthetic starter review materials."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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

NJ_FAMILY_STEMS = (
    "ela10_argument_writing",
    "ela10_informational_writing",
    "ela10_literary_analysis",
    "ela10_research_writing",
    "ela10_narrative_creative_writing",
    "ela10_reflection_short_response",
    "ela12_argument_writing",
    "ela12_informational_writing",
    "ela12_literary_analysis",
    "ela12_research_writing",
    "ela12_narrative_creative_writing",
    "ela12_reflection_short_response",
)
NJ_COMMENT_FILES = {f"{stem}.json" for stem in NJ_FAMILY_STEMS}
NJ_TAG_FILES = {f"{stem}_tags.json" for stem in NJ_FAMILY_STEMS}
NJ_RUBRIC_FILES = {f"{stem}_rubric.json" for stem in NJ_FAMILY_STEMS}
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


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


def _load_material_source(material_source: Path) -> dict[str, Any]:
    if "comment_banks" in material_source.parts:
        return load_comment_bank(material_source)
    if "tag_banks" in material_source.parts:
        return load_tag_bank(material_source)
    return load_rubric(material_source)


def _standard_ids(data: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for field in ("comments", "tags", "criteria"):
        for item in data.get(field, []):
            if isinstance(item, dict):
                values.update(str(value) for value in item.get("standard_ids", []))
    return values


def test_every_starter_material_validates_and_id_matches_filename() -> None:
    materials = discover_starter_materials()

    assert len(materials) == 51
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
        if material.material_id.startswith("ela"):
            assert "2023 NJSLS-ELA" in data["description"]
            assert _standard_ids(data)
        else:
            assert "Synthetic starter" in data["description"]
            assert not any("standard_ids" in item for item in data.get("comments", []))
            assert not any("standard_ids" in item for item in data.get("tags", []))
            assert not any("standard_ids" in item for item in data.get("criteria", []))


def test_nj_ela_starter_materials_are_discovered_by_type() -> None:
    materials = discover_starter_materials()

    comment_files = {
        material.source_path.name
        for material in materials
        if material.kind == "comment_bank"
    }
    tag_files = {
        material.source_path.name for material in materials if material.kind == "tag_bank"
    }
    rubric_files = {
        material.source_path.name for material in materials if material.kind == "rubric"
    }

    assert NJ_COMMENT_FILES <= comment_files
    assert NJ_TAG_FILES <= tag_files
    assert NJ_RUBRIC_FILES <= rubric_files


def test_nj_ela_metadata_is_structural_and_grade_appropriate() -> None:
    for material in discover_starter_materials():
        if not material.material_id.startswith("ela"):
            continue
        data = _load_material_source(material.source_path)
        assert data["scope"] == "shared"
        assert data["module_details"]["starter_pack"] == "nj_ela_2023"
        assert all(
            SNAKE_CASE_PATTERN.fullmatch(writing_type)
            for writing_type in data["writing_types"]
        )

        if material.kind == "comment_bank":
            assert data["categories"]
            assert len(data["comments"]) >= 24
            bank_writing_types = set(data["writing_types"])
            for comment in data["comments"]:
                assert set(comment.get("writing_types", bank_writing_types)) <= (
                    bank_writing_types
                )
        elif material.kind == "tag_bank":
            assert data["categories"]
            assert len(data["tags"]) >= 20
            bank_writing_types = set(data["writing_types"])
            for tag in data["tags"]:
                assert set(tag.get("writing_types", bank_writing_types)) <= (
                    bank_writing_types
                )
        else:
            assert data["criteria"]
            assert all(criterion["levels"] for criterion in data["criteria"])

        standard_ids = _standard_ids(data)
        assert all(standard_id.startswith("njsls-ela:") for standard_id in standard_ids)
        if material.material_id.startswith("ela10"):
            assert not any("11-12" in standard_id for standard_id in standard_ids)
            assert any("9-10" in standard_id for standard_id in standard_ids)
        else:
            assert not any("9-10" in standard_id for standard_id in standard_ids)
            assert any("11-12" in standard_id for standard_id in standard_ids)


def test_nj_ela_comment_tag_criterion_ids_match_family_rubrics() -> None:
    materials_by_name = {
        material.source_path.name: material for material in discover_starter_materials()
    }

    for stem in NJ_FAMILY_STEMS:
        rubric = load_rubric(materials_by_name[f"{stem}_rubric.json"].source_path)
        rubric_criteria = {
            criterion["criterion_id"] for criterion in rubric["criteria"]
        }

        bank = load_comment_bank(materials_by_name[f"{stem}.json"].source_path)
        for comment in bank["comments"]:
            assert set(comment.get("criterion_ids", [])) <= rubric_criteria

        tag_bank = load_tag_bank(materials_by_name[f"{stem}_tags.json"].source_path)
        for tag in tag_bank["tags"]:
            assert set(tag.get("criterion_ids", [])) <= rubric_criteria


def test_nj_ela_core_category_smoke_coverage() -> None:
    required_by_family = {
        "argument_writing": {"claim", "evidence", "reasoning", "organization"},
        "informational_writing": {
            "focus_topic",
            "development",
            "evidence_examples",
            "organization",
        },
        "literary_analysis": {
            "textual_evidence",
            "analysis_explanation",
            "comparative_claim",
            "synthesis",
        },
        "research_writing": {
            "research_question",
            "source_quality",
            "source_integration",
            "citation",
        },
        "narrative_creative_writing": {
            "sequence_pacing",
            "style_voice",
            "line_breaks",
            "sound",
        },
        "reflection_short_response": {
            "text_connection",
            "evidence",
            "reflection",
            "depth",
        },
    }

    materials_by_name = {
        material.source_path.name: material for material in discover_starter_materials()
    }
    for stem in NJ_FAMILY_STEMS:
        family = stem.removeprefix("ela10_").removeprefix("ela12_")
        required = required_by_family[family]
        bank = load_comment_bank(materials_by_name[f"{stem}.json"].source_path)
        tag_bank = load_tag_bank(materials_by_name[f"{stem}_tags.json"].source_path)

        bank_categories = {category["category_id"] for category in bank["categories"]}
        tag_categories = {
            category["category_id"] for category in tag_bank["categories"]
        }
        assert required <= bank_categories
        assert required <= tag_categories


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

    assert len(result.installed) == 51
    assert not result.skipped_existing
    assert len(list_valid_comment_banks(tmp_path)) == 17
    assert len(list_valid_tag_banks(tmp_path)) == 17
    assert len(list_valid_rubrics(tmp_path)) == 17
    assert {
        path.relative_to(tmp_path).parts[:2] for path in result.installed
    } == {
        ("shared", "comment_banks"),
        ("shared", "tag_banks"),
        ("shared", "rubrics"),
    }
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
    materials = discover_starter_materials()
    comment_count = sum(1 for material in materials if material.kind == "comment_bank")
    tag_count = sum(1 for material in materials if material.kind == "tag_bank")
    selections = f"1,{comment_count + 1},{comment_count + tag_count + 1}"
    _menu_input(monkeypatch, [selections, "1"])

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

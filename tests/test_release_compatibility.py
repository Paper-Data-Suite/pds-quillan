from __future__ import annotations

import ast
from pathlib import Path

import pytest

import scripts.verify_release_compatibility as compatibility


def test_release_compatibility_passes_current_tree() -> None:
    compatibility.validate_release_compatibility()


def test_release_version_and_historical_boundary_are_exact() -> None:
    assert compatibility.RELEASE_VERSION == "0.10.1"
    assert compatibility.PREVIOUS_RELEASE_VERSION == "0.10.0"
    assert compatibility.HISTORICAL_PREVIOUS_RELEASE_FILES == (
        Path("docs/v0.10.0_installed_class_set_acceptance.md"),
        Path("docs/physical_acceptance_v0.10.0.md"),
    )


def test_active_release_surfaces_name_v0101() -> None:
    for relative in compatibility.ACTIVE_VERSION_FILES:
        assert compatibility.RELEASE_VERSION in compatibility._read(relative)


def test_historical_previous_files_remain_identified() -> None:
    for relative in compatibility.HISTORICAL_PREVIOUS_RELEASE_FILES:
        assert compatibility.PREVIOUS_RELEASE_VERSION in compatibility._read(relative)


def test_core_floor_and_upper_bound_are_exact() -> None:
    specifier = compatibility.EXPECTED_CORE_SPECIFIER
    assert "0.6.2" in specifier
    assert "0.6.3" in specifier
    assert "0.6.1" not in specifier
    assert "0.6.0" not in specifier
    assert "0.5.0" not in specifier
    assert "0.7.0" not in specifier


def test_import_root_extracts_imports() -> None:
    tree = ast.parse(
        "import meridian.adapters\nfrom vitrine.models import Candidate\n"
    )
    assert [
        root
        for node in ast.walk(tree)
        for root in compatibility._import_root(node)
    ] == ["meridian", "vitrine"]


def test_sibling_import_audit_rejects_runtime_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "quillan"
    package.mkdir()
    (package / "bad.py").write_text("import meridian\n", encoding="utf-8")
    monkeypatch.setattr(compatibility, "PROJECT_ROOT", tmp_path)
    with pytest.raises(compatibility.ReleaseCompatibilityError, match="sibling"):
        compatibility.validate_sibling_import_isolation()


def test_operations_profile_is_part_of_release_boundary() -> None:
    compatibility.validate_routing_publication_and_operations_profiles()

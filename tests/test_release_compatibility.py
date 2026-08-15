from __future__ import annotations

import ast
from pathlib import Path

import pytest

import scripts.verify_release_compatibility as compatibility


def test_release_compatibility_passes_current_tree() -> None:
    compatibility.validate_release_compatibility()


def test_release_version_is_unique() -> None:
    assert compatibility.RELEASE_VERSION == "0.9.0"
    assert compatibility.LEGACY_VERSION == "0.8.9"
    assert compatibility.LEGACY_ALLOWED_LINES == {
        Path("docs/v0.9.0_release_compatibility.md"): (
            "v0.8.9 remains the Core 0.5 PDS2 release.",
        ),
        Path("docs/release_checklist.md"): (
            "Quillan 0.9.0 while v0.8.9 history remains unchanged.",
        ),
    }


def test_active_legacy_mentions_are_exactly_bounded() -> None:
    for relative in compatibility.ACTIVE_VERSION_FILES:
        compatibility._validate_active_legacy_mentions(
            relative, compatibility._read(relative)
        )


def test_unexpected_active_legacy_mention_is_rejected() -> None:
    text = (
        "Quillan 0.9.0 while v0.8.9 history remains unchanged.\n"
        "Current release is 0.8.9.\n"
    )
    with pytest.raises(
        compatibility.ReleaseCompatibilityError,
        match="unexpected 0.8.9 context",
    ):
        compatibility._validate_active_legacy_mentions(
            Path("docs/release_checklist.md"), text
        )


def test_historical_release_evidence_is_explicitly_pinned() -> None:
    assert compatibility.HISTORICAL_RELEASE_FILES == (
        Path("docs/releases/v0.8.9.md"),
        Path("docs/releases/v0.8.9_acceptance_matrix.md"),
        Path("docs/physical_acceptance_v0.8.9.md"),
    )
    for relative in compatibility.HISTORICAL_RELEASE_FILES:
        assert compatibility.LEGACY_VERSION in compatibility._read(relative)


def test_core_05_and_07_are_outside_supported_range() -> None:
    specifier = compatibility.EXPECTED_CORE_SPECIFIER
    assert "0.6.0" in specifier
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

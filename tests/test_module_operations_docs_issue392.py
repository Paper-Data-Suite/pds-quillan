from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_module_operations_document_defines_readiness_semantics() -> None:
    text = (ROOT / "docs" / "module_operations.md").read_text(encoding="utf-8")
    required = (
        "attention_provider = present",
        "readiness_provider = present",
        "quillan_readiness_unavailable",
        "quillan_class_not_ready",
        "ready = true",
        "ready = false",
        "ready = null",
        "readiness.ready = true",
        "attention.summaries != empty",
        "`pdftoppm`",
        "not a global Quillan `ready = false` condition",
    )
    for value in required:
        assert value in text


def test_module_operations_document_preserves_semantic_independence() -> None:
    text = (ROOT / "docs" / "module_operations.md").read_text(encoding="utf-8")
    required = (
        "Readiness also does not derive meaning from #390 diagnostic events",
        "Readiness is not launchability",
        "Suite release",
        "publication authorization",
        "grouping-signal",
        "Readiness evaluation does not emit a diagnostic event",
    )
    for value in required:
        assert value in text


def test_module_operations_document_defines_launcher_and_mixed_intake_boundary() -> None:
    text = (ROOT / "docs" / "module_operations.md").read_text(encoding="utf-8")
    required = (
        "The operations profile is not launcher authority.",
        "quillan = quillan.cli:main",
        "Paper Data Suite owns exact release compatibility",
        "Unified mixed-module paper intake is likewise Suite-owned orchestration",
        "Core selects the profile by locator.module_id",
        "foreign/unsupported routes remain foreign failures",
        "Core routing contract = 1",
        "QR schema = PDS2",
        "route-registration schema = 1",
    )
    for value in required:
        assert value in text


def test_readme_describes_attention_and_readiness_without_suite_conflation() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Core v1 attention and readiness integration" in text
    assert "independent read-only attention and readiness providers" in text
    assert "workspace/class context is structurally usable" in text
    assert "not launcher or Suite release-compatibility authority" in text
    assert "readiness absent until #392" not in text

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_artifacts_require_readiness_provider() -> None:
    source = (ROOT / "scripts" / "inspect_release_artifacts.py").read_text(
        encoding="utf-8"
    )
    assert '"quillan/readiness_provider.py"' in source
    assert '"quillan/attention_provider.py"' in source
    assert '"quillan/pds_operations.py"' in source


def test_installed_operations_acceptance_exercises_readiness_states() -> None:
    source = (
        ROOT / "scripts" / "verify_installed_operations_acceptance.py"
    ).read_text(encoding="utf-8")

    required = (
        "invoke_module_readiness",
        "ModuleReadinessReport",
        "Quillan readiness provider is absent",
        "module_operations.evaluation_unavailable",
        "issue392-missing-workspace",
        "issue392_acceptance",
        "issue392_missing_class",
        "workspace_unchanged_by_operations",
    )
    for value in required:
        assert value in source


def test_installed_operations_acceptance_verifies_launcher_independently() -> None:
    source = (
        ROOT / "scripts" / "verify_installed_operations_acceptance.py"
    ).read_text(encoding="utf-8")
    assert 'metadata.entry_points(group="console_scripts")' in source
    assert 'entry.name == "quillan"' in source
    assert 'launcher.value != "quillan.cli:main"' in source
    assert '"launcher_target": launcher.value' in source


def test_installed_operations_acceptance_preserves_source_shadowing_checks() -> None:
    source = (
        ROOT / "scripts" / "verify_installed_operations_acceptance.py"
    ).read_text(encoding="utf-8")
    assert "installed Quillan import is source-shadowed" in source
    assert "installed Core import is source-shadowed" in source
    assert "provider.valid" in source
    assert "invoke_module_attention" in source

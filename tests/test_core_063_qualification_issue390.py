"""Issue #390 Core 0.6.3 qualification and dependency-boundary contracts."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
import tomllib

from quillan.diagnostic_events import build_diagnostic_event


ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def test_issue391_raises_core_floor_only_to_module_operations_release() -> None:
    document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = document["project"]["dependencies"]
    assert "pds-core>=0.6.2,<0.7" in dependencies
    assert "pds-core>=0.6,<0.7" not in dependencies
    assert not any(
        str(item).startswith("pds-core>=0.6.3")
        for item in dependencies
    )


def test_ci_qualifies_new_minimum_062_and_retains_exact_063_endpoint_matrix() -> None:
    source = CI.read_text(encoding="utf-8")

    assert "Download released Core 0.6.2" in source
    assert "pds_core-0.6.2-py3-none-any.whl" in source
    assert "--core-version 0.6.2" in source
    assert "Download released Core 0.6.0" not in source

    assert "core-063-qualification:" in source
    assert 'python: ["3.11", "3.14"]' in source
    assert "windows-latest" in source
    assert "ubuntu-latest" in source
    assert "Download released Core 0.6.3" in source
    assert "pds_core-0.6.3-py3-none-any.whl" in source
    assert "--core-version 0.6.3" in source
    assert 'component="assembly"' in source
    assert 'workflow="assemble_submission"' in source
    assert 'stage="verify_record"' in source
    assert 'code="assembly_succeeded"' in source
    assert "diagnostic_retention_pruned" not in source
    assert (
        "98d7596ce0eed26e4d56a17bbbbd644db3014259b56a45783a173fe8237af5e5"
        in (ROOT / "scripts" / "verify_core_wheel.py").read_text(encoding="utf-8")
    )


def test_release_candidate_keeps_explicit_historical_core_060_contract() -> None:
    source = (
        ROOT / "scripts" / "validate_release_candidate.ps1"
    ).read_text(encoding="utf-8")
    assert source.count("'--core-version', '0.6.0'") == 2
    assert "'--expected-core-version', '0.6.0'" in source


def test_diagnostic_event_reports_actual_installed_core_version() -> None:
    installed = importlib.metadata.version("pds-core")
    event = build_diagnostic_event(
        component="assembly",
        workflow="assemble_submission",
        stage="verify_record",
        outcome="success",
        code="assembly_succeeded",
    )
    assert event.core_version == installed

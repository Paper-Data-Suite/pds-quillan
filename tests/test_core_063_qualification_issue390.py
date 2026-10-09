"""Issue #390 Core 0.6.3 qualification and dependency-boundary contracts."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
import tomllib

from quillan.diagnostic_events import build_diagnostic_event


ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def test_historical_core_063_is_superseded_by_current_065_reader_floor() -> None:
    document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = document["project"]["dependencies"]
    assert "pds-core>=0.6.5,<0.7" in dependencies
    assert "pds-core>=0.6.2,<0.7" not in dependencies

def test_core_063_wheel_identity_remains_historical() -> None:
    source = CI.read_text(encoding="utf-8")
    assert "Download released Core 0.6.5" in source
    assert "core-063-qualification:" not in source
    assert "98d7596ce0eed26e4d56a17bbbbd644db3014259b56a45783a173fe8237af5e5" in (
        ROOT / "scripts/verify_core_wheel.py"
    ).read_text(encoding="utf-8")

def test_release_candidate_uses_only_core_065() -> None:
    source = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    assert "'--core-version', '0.6.5'" in source
    assert "$PdsCore063Wheel" not in source

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

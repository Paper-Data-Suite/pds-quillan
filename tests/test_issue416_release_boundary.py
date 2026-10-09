"""Historical Issue #416 and current Core 0.6.4 release-boundary contracts."""

from __future__ import annotations

from pathlib import Path

from scripts.verify_core_wheel import (
    CORE_064_FILENAME,
    CORE_064_SHA256,
    CORE_064_VERSION,
    known_core_wheel_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def test_released_core_064_is_pinned_exactly() -> None:
    contract = known_core_wheel_contract("0.6.4")
    assert CORE_064_FILENAME == "pds_core-0.6.4-py3-none-any.whl"
    assert CORE_064_VERSION == "0.6.4"
    assert CORE_064_SHA256 == "48cea9317f2967bdc0f2d4c14349a56677c7c3f8211f0f33978ccb1a1c75859b"
    assert contract.filename == CORE_064_FILENAME
    assert contract.sha256 == CORE_064_SHA256
    assert contract.version == CORE_064_VERSION


def test_issue416_harness_remains_historical_and_not_an_active_release_gate() -> None:
    candidate = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    historical = (ROOT / "docs/v0.10.4_installed_scan_path_acceptance.md").read_text(encoding="utf-8")
    assert "verify_installed_issue416_scan_paths.py" not in candidate
    assert "Core 0.6.4" in historical

def test_new_candidate_authenticates_current_core_065() -> None:
    candidate = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    assert "$PdsCore065Wheel" in candidate
    assert "'--core-version', '0.6.5'" in candidate

def test_issue416_historical_evidence_keeps_original_candidate_identity() -> None:
    historical = (ROOT / "docs/v0.10.4_installed_scan_path_acceptance.md").read_text(encoding="utf-8")
    assert "2e47734" in historical
    assert "201e651f4b9aad0bfeb1565b37f425982513f2fb616b86a8835a10f4dcd7db62" in historical
    assert "qualification endpoint" in historical
    assert "not a\nnew runtime floor" in historical

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


def test_release_candidate_qualifies_core_064_and_preserves_issue416_harness() -> None:
    source = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert "$PdsCore064Wheel" in source
    assert "'--core-version', '0.6.4'" in source
    assert "@{ Version = '0.6.4'; Wheel = $Core064Wheel }" in source
    assert "verify_installed_issue416_scan_paths.py" in source
    assert "if ($CoreVersion -eq '0.6.4')" in source
    assert "'--expected-quillan-version', '0.10.5'" in source
    assert "'--expected-core-version', $CoreVersion" in source
    assert "quillan-0.10.5-py3-none-any.whl" in source
    assert "quillan-0.10.5.tar.gz" in source


def test_release_candidate_uses_released_core_064_for_sdist_smoke() -> None:
    source = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert "Install released Core 0.6.4 for sdist smoke" in source
    assert "'-m', 'pip', 'install', $Core064Wheel" in source
    assert "'--expected-core-version', '0.6.4'" in source


def test_issue416_historical_evidence_keeps_original_candidate_identity() -> None:
    process = (ROOT / "docs" / "release_process.md").read_text(encoding="utf-8")
    historical = (
        ROOT / "docs" / "v0.10.4_installed_scan_path_acceptance.md"
    ).read_text(encoding="utf-8")

    assert "pds-core>=0.6.2,<0.7" in process
    assert "48cea9317f2967bdc0f2d4c14349a56677c7c3f8211f0f33978ccb1a1c75859b" in process
    assert "released Core 0.6.4" in process
    assert "2e47734" in historical
    assert "201e651f4b9aad0bfeb1565b37f425982513f2fb616b86a8835a10f4dcd7db62" in historical
    assert "qualification endpoint" in historical
    assert "not a\nnew runtime floor" in historical

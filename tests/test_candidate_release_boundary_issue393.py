from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_candidate_validator_builds_once_and_qualifies_core_065() -> None:
    source = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    assert "$PdsCore065Wheel" in source
    assert "$PdsCore062Wheel" not in source
    assert "$PdsCore063Wheel" not in source
    assert "$PdsCore064Wheel" not in source
    assert "quillan-0.10.6-py3-none-any.whl" in source
    assert "quillan-0.10.6.tar.gz" in source
    assert "verify_installed_issue421_reader_contract.py" in source
    assert "verify_installed_issue419_recovery.py" in source
    assert source.count("Build exact release wheel and sdist") == 1

def test_candidate_validator_has_no_active_v090_or_core060_assumption() -> None:
    text = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert "quillan-0.9.0" not in text
    assert "'--core-version', '0.6.0'" not in text
    assert "'--expected-core-version', '0.6.0'" not in text


def test_physical_document_cannot_claim_automated_pass() -> None:
    text = (ROOT / "docs" / "physical_acceptance_v0.10.0.md").read_text(
        encoding="utf-8"
    )
    assert "PENDING OWNER" in text
    assert "Automation must never replace `PENDING OWNER` with PASS." in text
    assert "real paper" in text.lower()


def test_installed_class_set_document_preserves_suite_boundary() -> None:
    text = (
        ROOT / "docs" / "v0.10.0_installed_class_set_acceptance.md"
    ).read_text(encoding="utf-8")
    assert "Core 0.6.2" in text
    assert "Core 0.6.3" in text
    assert "pds-core>=0.6.2,<0.7" in text
    assert "Unified mixed-paper intake UI remains Paper Data Suite work." in text
    assert "attention and readiness" in text


def test_candidate_validator_reuses_full_ci_gate() -> None:
    source = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    assert source.count("run_tests.ps1") == 1
    assert "[switch]$SkipRepositoryDevelopmentChecks" in source
    assert "Repository checks reused from passing CI" in source

def test_candidate_has_one_source_isolated_venv() -> None:
    source = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    assert "New-Item -ItemType Directory -Path $Artifacts, $Outside" in source
    assert "'--core-version', '0.6.5'" in source

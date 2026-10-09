"""Issue #421: short reader-contract release gate is explicit and source-isolated."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_one_core_one_candidate_and_no_historical_matrix() -> None:
    gate = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    assert "$PdsCore065Wheel" in gate
    assert gate.count("'--core-version', '0.6.5'") >= 1
    assert gate.count("'Build exact release wheel and sdist'") == 1
    assert "$PdsCore062Wheel" not in gate
    assert "$PdsCore063Wheel" not in gate
    assert "$PdsCore064Wheel" not in gate
    assert "-SkipRepositoryDevelopmentChecks" not in gate  # switch, not an inert flag
    assert "[switch]$SkipRepositoryDevelopmentChecks" in gate
    assert "run_tests.ps1" in gate
    assert "full pytest not repeated" in gate


def test_publication_recovery_and_reader_are_source_isolated() -> None:
    gate = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    for value in (
        "verify_core_wheel.py",
        "verify_installed_issue421_reader_contract.py",
        "verify_installed_issue419_recovery.py",
        "verify_installed_producer_acceptance.py",
        "run_installed_acceptance.py",
        "inspect_release_artifacts.py",
        "persist_release_artifacts.py",
        "pip', 'check",
    ):
        assert value in gate
    assert "twine" in gate
    assert "Release authorization: NOT GRANTED" in gate


def test_old_release_evidence_unmodified_and_no_consumer_dependency() -> None:
    process = (ROOT / "docs/release_process.md").read_text(encoding="utf-8")
    assert "pds-core>=0.6.5,<0.7" in process
    assert "Meridian #111" in process
    assert "Vitrine #103" in process
    assert (ROOT / "docs/v0.10.5_installed_reporting_review_acceptance.md").exists()
    assert (ROOT / "docs/v0.10.4_installed_scan_path_acceptance.md").exists()

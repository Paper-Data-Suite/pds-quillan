from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_candidate_validator_builds_v0103_once_and_qualifies_both_core_endpoints() -> None:
    text = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert "$PdsCore062Wheel" in text
    assert "$PdsCore063Wheel" in text
    assert "'--core-version', '0.6.2'" in text
    assert "'--core-version', '0.6.3'" in text
    assert "quillan-0.10.3-py3-none-any.whl" in text
    assert "quillan-0.10.3.tar.gz" in text
    assert text.count('"Build one wheel and sdist"') == 1
    assert "verify_installed_producer_acceptance.py" in text
    assert "verify_installed_operations_acceptance.py" in text
    assert "verify_installed_selected_review_reads.py" in text
    assert "Installed selected-review reads Core $CoreVersion" in text
    assert "'--expected-quillan-version', '0.10.3'" in text
    assert "'--version', '0.10.3'" in text
    assert "'--expected-core-version', $CoreVersion" in text
    assert "v0.10.0 physical acceptance remains applicable: NOT REPEATED" in text


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


def test_candidate_validator_runs_repository_full_gate_once() -> None:
    text = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert text.count("run_tests.ps1") == 1
    assert 'Invoke-Required "Source pytest"' not in text
    assert 'Invoke-Required "Ruff"' not in text
    assert 'Invoke-Required "mypy"' not in text
    assert 'Invoke-Required "pip check"' not in text
    assert 'Invoke-Required "Documentation"' not in text
    assert 'Invoke-Required "Release compatibility"' not in text
    assert 'Invoke-Required "Diff whitespace"' not in text
    assert 'Invoke-Required "compileall"' in text


def test_candidate_validator_can_reuse_completed_repository_gate() -> None:
    text = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert "[switch]$SkipRepositoryDevelopmentChecks" in text
    assert "if ($SkipRepositoryDevelopmentChecks)" in text
    assert "full pytest is not being repeated." in text
    assert text.count("(Join-Path $Repository 'run_tests.ps1')") == 1

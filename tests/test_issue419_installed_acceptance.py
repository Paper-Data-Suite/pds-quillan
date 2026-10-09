"""Issue #419: installed-wheel acceptance contract and release-gate wiring."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_standalone_qualification_is_python_and_does_not_import_source_tests() -> None:
    content = (ROOT / "scripts/verify_installed_issue419_recovery.py").read_text(
        encoding="utf-8"
    )
    ast.parse(content)
    assert "from tests" not in content
    assert "import tests" not in content
    assert '"site-packages"' in content
    assert "importlib.metadata" in content
    assert "--expected-quillan-version" in content
    assert "--expected-core-version" in content
    assert "open_student_submission_for_review" in content
    assert "discover_historical_scan_recoveries" in content
    assert "replay_historical_scan_recovery" in content
    assert "_files(root) == after" in content


def test_acceptance_covers_cli_menu_and_failure_invariants() -> None:
    content = (ROOT / "scripts/verify_installed_issue419_recovery.py").read_text(
        encoding="utf-8"
    )
    for name in (
        '"list-scan-recoveries"',
        '"preflight-scan-recovery"',
        '"recover-scan-review"',
        '"replay-scan-recovery"',
        "launch_scan_recovery_menu",
        '"selection_needed"',
        '"teacher_action_needed"',
        "synthetic installed assembly interruption",
        'b"tampered"',
        "superseded decision was replayed",
    ):
        assert name in content


def test_release_candidate_qualifies_419_once_at_released_core_065() -> None:
    candidate = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    assert "verify_installed_issue419_recovery.py" in candidate
    assert "'--expected-core-version', '0.6.5'" in candidate
    assert "'--expected-quillan-version', '0.10.6'" in candidate
    assert "quillan-0.10.6-py3-none-any.whl" in candidate

def test_standalone_runner_authenticates_exact_core_and_does_not_touch_repo() -> None:
    source = (ROOT / "scripts/run_issue419_wheel_acceptance.ps1").read_text(
        encoding="utf-8"
    )
    assert "verify_core_wheel.py" in source
    assert "'--verify-installed'" in source
    assert "verify_installed_issue419_recovery.py" in source
    assert "outside-source" in source
    assert "--expected-quillan-version" in source
    assert "quillan-$Version-py3-none-any.whl" in source
    assert "-m', 'pip', 'check'" in source

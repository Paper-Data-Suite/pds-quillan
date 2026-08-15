"""Source-level contract for the clean-wheel producer acceptance."""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.verify_installed_producer_acceptance as acceptance


SCRIPT = Path("scripts/verify_installed_producer_acceptance.py")
RELEASE = Path("scripts/validate_release_candidate.ps1")


def test_dedicated_harness_has_bounded_deterministic_stages() -> None:
    assert SCRIPT.is_file()
    assert acceptance.STAGES == tuple(dict.fromkeys(acceptance.STAGES))
    assert acceptance.STAGES[0] == "installed provenance"
    assert acceptance.STAGES[-1] == "immutability"
    with pytest.raises(ValueError, match="single line"):
        acceptance.AcceptanceFailure("installed provenance", "unsafe\npayload")


def test_main_returns_nonzero_without_rendering_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        acceptance,
        "run_acceptance",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            acceptance.AcceptanceFailure("installed provenance", "bounded failure.")
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["verify", "--workspace", ".", "--repository", "."],
    )
    assert acceptance.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "FAILED: installed provenance: bounded failure.\n"
    assert "Traceback" not in captured.err


def test_installed_provenance_checks_exact_distribution_origins_and_core() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for token in (
        'metadata.version("quillan")',
        'metadata.version("pds-core")',
        'pds_core.__version__',
        '"pds_core.registry_audit"',
        '"quillan.academic_result_artifacts"',
        '"site-packages"',
        '"PYTHONPATH" not in os.environ',
        'discover_publication_producer_profiles()',
    ):
        assert token in source


def test_lifecycle_uses_only_public_producer_and_core_surfaces() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for token in (
        "register_quillan_academic_work(",
        "update_quillan_academic_work_registration(",
        "generate_academic_result_manifest(",
        "publish_quillan_academic_results(",
        "supersede_quillan_academic_results(",
        "withdraw_quillan_academic_result_publication(",
        "query_publication_catalog(",
        "evaluate_publication_compatibility(",
        "verify_publication_manifest(",
        "read_academic_result_manifest(",
        "read_authorized_academic_result_artifacts(",
        "audit_academic_registry(",
    ):
        assert token in source
    for forbidden in (
        "unittest.mock",
        "monkeypatch",
        "sqlite3",
        "write_publication_record",
        "write_publication_withdrawal",
        "write_academic_work_registration",
    ):
        assert forbidden not in source


def test_harness_does_not_import_sibling_products() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for sibling in ("from meridian", "from vitrine", "from scoreform", "from concord", "from portia"):
        assert sibling not in source


def test_release_harness_orders_no_side_effect_acceptance_before_wheel_producer() -> None:
    source = RELEASE.read_text(encoding="utf-8")
    ordinary = source.index('Invoke-Required "Installed acceptance ($Mode)"')
    producer = source.index('Invoke-Required "Installed producer acceptance (wheel)"')
    persistence = source.index('Invoke-Required "Persist exact tested artifacts"')
    assert ordinary < producer < persistence
    assert "verify_installed_producer_acceptance.py" in source
    assert "acceptance\\workflow-workspace" in source
    assert "if ($Mode -eq 'wheel')" in source
    assert "if ($Mode -eq 'wheel') { $AcceptanceArguments += '--full-workflow' }" in source
    assert "Remove-Item Env:PYTHONPATH" in source
    assert 'Write-Host "Release authorization: NOT GRANTED"' in source


def test_manifest_authorization_precedes_core_verification_and_read() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("def _core_verified(")
    end = source.index("\n\nclass _ExactGate", start)
    body = source[start:end]
    authorization = body.index("manifest_read_authorized =")
    authorization_check = body.index("_require(\n        manifest_read_authorized", authorization)
    verification = body.index("verify_publication_manifest(")
    byte_read = body.index("path.read_bytes()")
    assert authorization < authorization_check < verification < byte_read


def test_reader_and_artifact_acceptance_asserts_privacy_and_exact_formats() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for token in (
        "b'\"private_notes\"' not in content",
        "b'\"retained_source_path\"' not in content",
        "b'\"routed_evidence_path\"' not in content",
        'len(feedback.comments) == 1',
        'len(references) == 2',
        '== getattr(item, "evidence_reference").routed_evidence_sha256',
        'getattr(pdf[0], "artifact_kind") == "feedback_pdf"',
        'getattr(markdown[0], "artifact_kind") == "feedback_markdown"',
        'getattr(pdf[0], "source_review_updated_at") == review_updated_at',
    ):
        assert token in source


def test_ordinary_acceptance_preserves_no_academic_state_handoff() -> None:
    source = Path("scripts/run_installed_acceptance.py").read_text(encoding="utf-8")
    full_workflow = source.index("_run_full_workflow(workflow_workspace")
    no_state = source.index("_assert_no_academic_state(workflow_workspace)", full_workflow)
    output = source.index('"academic_registry_side_effects": False', no_state)
    assert full_workflow < no_state < output

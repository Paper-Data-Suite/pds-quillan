from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _script() -> str:
    return (ROOT / "scripts" / "verify_installed_release_edges.py").read_text(
        encoding="utf-8"
    )


def test_release_edge_verifier_checks_all_four_installed_entry_point_roles() -> None:
    text = _script()
    for value in (
        "quillan.cli:main",
        "quillan.pds_module:get_module_profile",
        "quillan.pds_publication:get_publication_producer_profile",
        "quillan.pds_operations:get_module_operations_profile",
    ):
        assert value in text


def test_release_edge_verifier_binds_final_publication_lifecycle() -> None:
    text = _script()
    assert "list_publication_record_set" in text
    assert "get_current_publication_record" in text
    assert "load_publication_withdrawal" in text
    assert "len(series) != 2" in text
    assert "head.record_set_revision != 2" in text
    assert "publication_current_selectable" in text


def test_release_edge_verifier_proves_mixed_routing_without_test_imports() -> None:
    text = _script()
    for value in (
        "dispatch_routes",
        "RouteDispatchFailure",
        "RouteDispatchSuccess",
        "ModuleRegistry",
        "write_route_registration",
        "retain_source_scan",
        "foreign_fallback_to_quillan",
        "quillan_route_after_foreign_failure",
    ):
        assert value in text
    assert "tests." not in text
    assert "monkeypatch" not in text


def test_release_edge_verifier_preserves_real_handler_authority_boundary() -> None:
    text = _script()
    assert "return replace(original, route_handler=track_quillan)" in text
    assert "registration_validator" not in (
        text[text.index("return replace(original"):text.index(
            "def _file_snapshot"
        )]
    )
    assert "already-proven route-handler" in text


def test_release_edge_verifier_checks_diagnostic_privacy() -> None:
    text = _script()
    assert "list_diagnostic_events" in text
    assert "diagnostic_privacy" in text
    for secret in (
        "Synthetic teacher feedback.",
        "Synthetic matrix feedback.",
        "Synthetic private teacher note.",
        "foreign-private-payload-must-remain-opaque",
    ):
        assert secret in text
    assert "forbidden in rendered" in text


def test_candidate_validator_runs_release_edge_for_each_core_endpoint() -> None:
    text = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert "verify_installed_release_edges.py" in text
    assert "Installed release-edge acceptance Core $CoreVersion" in text
    assert "(Join-Path $Acceptance 'workflow-workspace')" in text
    assert "'--expected-core-version', $CoreVersion" in text


def test_installed_acceptance_docs_explain_release_edge_authority() -> None:
    text = (
        ROOT / "docs" / "v0.10.0_installed_class_set_acceptance.md"
    ).read_text(encoding="utf-8")
    assert "## Release-edge binding" in text
    assert "no fallback of foreign work to Quillan" in text
    assert "real Quillan handler itself successfully handled PDS2" in text


def test_release_edge_verifier_reuses_installed_printable_packet() -> None:
    text = _script()
    assert 'issue393-mixed-routing-source.bin' not in text
    assert 'printable_response_pages.pdf' in text
    assert 'source.write_bytes' not in text
    assert 'installed full workflow produced no printable response packet' in text

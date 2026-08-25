"""Issue #390 publication-chain diagnostic instrumentation contracts."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import quillan.academic_result_manifest_generation as manifest_generation
import quillan.academic_result_publication as publication
import quillan.academic_work_registration as registration
import quillan.diagnostic_events as diagnostics
import quillan.share_results_menu as share_results_menu


@pytest.fixture(autouse=True)
def _fixed_core_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quillan.diagnostic_events._installed_core_version",
        lambda: "0.6.3",
    )


@pytest.mark.parametrize(
    ("code", "expected_summary"),
    (
        (
            "registration_partial_success",
            "Academic Work Registration may already be durable",
        ),
        (
            "manifest_revision_created",
            "Academic Result manifest revision was created and verified",
        ),
        (
            "share_state_changed",
            "Share Results canonical state changed after teacher authorization",
        ),
    ),
)
def test_slice2b_new_codes_are_fixed_privacy_safe_contracts(
    tmp_path: Path,
    code: str,
    expected_summary: str,
) -> None:
    event = diagnostics.build_diagnostic_event(
        component="publication",
        workflow=(
            "register_academic_work"
            if code == "registration_partial_success"
            else "generate_result_manifest"
            if code == "manifest_revision_created"
            else "share_results"
        ),
        stage="write_record" if code != "share_state_changed" else "preflight",
        outcome=(
            "partial_success"
            if code == "registration_partial_success"
            else "success"
            if code == "manifest_revision_created"
            else "blocked"
        ),
        code=code,
        class_id="class_a",
        assignment_id="assignment_a",
    )

    assert expected_summary in event.safe_summary
    assert "PRIVATE-SENTINEL" not in event.safe_summary


def test_registration_instruments_only_service_conflict_or_partial_success() -> None:
    register_source = inspect.getsource(registration.register_quillan_academic_work)
    update_source = inspect.getsource(
        registration.update_quillan_academic_work_registration
    )
    helper = inspect.getsource(registration._record_registration_service_error)

    assert "_record_registration_service_error(" in register_source
    assert "_record_registration_service_error(" in update_source
    assert "RegistryServicePartialSuccessError" in helper
    assert "registration_partial_success" in helper
    assert "RegistryServiceConflictError" in helper
    assert "registration_conflict" in helper
    assert 'outcome="success"' not in helper


def test_manifest_generation_records_new_durable_revision_not_exact_replay() -> None:
    source = inspect.getsource(
        manifest_generation.generate_academic_result_manifest
    )

    replay_at = source.index('if plan.disposition == "reuse_existing":')
    replay_return = source.index(
        "return AcademicResultManifestGenerationResult(", replay_at
    )
    durable_result = source.index(
        "result_value = AcademicResultManifestGenerationResult("
    )
    success_event = source.index('code="manifest_revision_created"')

    assert replay_return < durable_result < success_event
    assert 'code="manifest_partial_success"' in source
    assert "_record_manifest_generation_error(root, work, error)" in source


def test_publication_success_event_follows_catalog_reconciliation() -> None:
    source = inspect.getsource(publication._verify_result)

    reconcile_at = source.index("catalog = _reconcile_catalog(")
    result_at = source.index("result = AcademicResultPublicationResult(")
    event_at = source.index("try_emit_diagnostic_event(", result_at)
    return_at = source.index("return result")

    assert reconcile_at < result_at < event_at < return_at
    assert '"publication_verified"' in source
    assert '"supersession_verified"' in source
    assert '"catalog_reconciliation_failed"' in source
    assert '"publication_partial_success"' in source


def test_publication_service_errors_use_non_throwing_diagnostics() -> None:
    helper = inspect.getsource(publication._record_publication_service_error)
    publish_source = inspect.getsource(
        publication.publish_quillan_academic_results
    )
    supersede_source = inspect.getsource(
        publication.supersede_quillan_academic_results
    )

    assert "RegistryServicePartialSuccessError" in helper
    assert "publication_partial_success" in helper
    assert "RegistryServiceConflictError" in helper
    assert "publication_conflict" in helper
    assert "_record_publication_service_error(" in publish_source
    assert "_record_publication_service_error(" in supersede_source
    assert "record_diagnostic_event(" not in helper


def test_share_results_only_logs_post_authorization_freshness_block() -> None:
    source = inspect.getsource(share_results_menu._guided_publication)

    confirmation_at = source.index("confirmation = input(")
    fresh_at = source.index(
        "fresh = build_share_results_status(", confirmation_at
    )
    first_event = source.index("try_emit_diagnostic_event(", fresh_at)
    service_at = min(
        source.index("publish_quillan_academic_results(", first_event),
        source.index("supersede_quillan_academic_results(", first_event),
    )

    assert confirmation_at < fresh_at < first_event < service_at
    assert source.count('code="share_state_changed"') == 2
    assert 'workflow="share_results"' in source


def test_publication_chain_modules_never_call_strict_diagnostic_writer() -> None:
    modules = (
        registration,
        manifest_generation,
        publication,
        share_results_menu,
    )
    for module in modules:
        source = inspect.getsource(module)
        assert "try_emit_diagnostic_event" in source
        assert "record_diagnostic_event(" not in source
        assert "build_diagnostic_event(" not in source

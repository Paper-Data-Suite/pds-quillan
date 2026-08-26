from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _script() -> str:
    return (
        ROOT / "scripts" / "verify_installed_class_set_acceptance.py"
    ).read_text(encoding="utf-8")


def test_class_set_acceptance_uses_installed_production_services() -> None:
    text = _script()
    required = (
        "plan_assignment_copy",
        "commit_assignment_copy",
        "plan_review_configuration_preset_from_assignment",
        "commit_review_configuration_preset",
        "MenuSessionContext",
        "revalidate_menu_context",
        "build_assignment_review_work_queue",
        "build_review_student_navigation",
        "derive_review_continuation",
        "build_batch_feedback_export_plan",
        "execute_batch_feedback_export",
        "build_class_review_completion_view",
    )
    for value in required:
        assert value in text
    assert "tests." not in text
    assert "monkeypatch" not in text


def test_class_set_acceptance_reuses_canonical_installed_workflow_fixture() -> None:
    text = _script()
    assert 'CLASS_ID = "synthetic_release_class"' in text
    assert 'ASSIGNMENT_ID = "synthetic_release_digital"' in text
    assert '("00107", "00208")' in text
    assert '"complete",' in text
    assert '"minimum_requirements_pending",' in text
    assert '"minimum_requirement_outcome_not_checked"' in text
    assert 'files == ("assignment.json",)' in text


def test_class_set_acceptance_preserves_teacher_controlled_boundaries() -> None:
    text = _script()
    assert 'all(item.action == "skip_current"' in text
    assert 'all(item.outcome == "skipped_current"' in text
    assert 'continuation.status == "complete"' in text
    assert '"student_prompt"' in text
    assert "for forbidden in" in text


def test_candidate_validator_runs_class_set_for_each_core_endpoint() -> None:
    text = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    assert "verify_installed_class_set_acceptance.py" in text
    assert "Installed class-set acceptance Core $CoreVersion" in text
    assert "'--expected-core-version', $CoreVersion" in text
    assert "(Join-Path $Acceptance 'workflow-workspace')" in text


def test_class_set_acceptance_is_source_isolated_and_version_exact() -> None:
    text = _script()
    assert 'EXPECTED_QUILLAN_VERSION = "0.10.0"' in text
    assert 'choices=("0.6.2", "0.6.3")' in text
    assert "quillan_source_isolated" in text
    assert "core_source_isolated" in text
    assert "is_relative_to(repository)" in text


def test_class_set_acceptance_builds_real_heterogeneous_matrix() -> None:
    text = _script()
    required = (
        'MATRIX_CLASS_ID = "synthetic_matrix_class"',
        '"m001_no_submission"',
        '"m002_minimum"',
        '"m003_observations"',
        '"m004_ratings"',
        '"m005_feedback"',
        '"m006_export_missing"',
        '"m007_export_stale"',
        '"m008_complete"',
        "create-plain-paper-submission",
        "requirements",
        "observations",
        "ratings",
        "feedback",
        "export-feedback",
    )
    for value in required:
        assert value in text


def test_class_set_matrix_asserts_every_review_stage_and_stale_export() -> None:
    text = _script()
    for category in (
        "no_submission",
        "minimum_requirements_pending",
        "observations_pending",
        "ratings_pending",
        "feedback_pending",
        "export_pending",
        "complete",
    ):
        assert category in text
    assert "feedback_export_missing" in text
    assert "feedback_export_stale" in text
    assert "current_feedback_export_present" in text


def test_class_set_matrix_executes_missing_and_stale_batch_exports() -> None:
    text = _script()
    assert 'overwrite_policy="none"' in text
    assert 'overwrite_policy="stale"' in text
    assert 'missing_plan.items[0].action == "create"' in text
    assert 'missing_result.items[0].outcome == "created"' in text
    assert 'stale_plan.items[0].action == "replace"' in text
    assert 'stale_result.items[0].outcome == "replaced"' in text


def test_class_set_matrix_proves_attention_readiness_independence() -> None:
    text = _script()
    assert "invoke_module_readiness" in text
    assert "invoke_module_attention" in text
    assert "readiness.report.ready is True" in text
    assert "attention.report.summaries" in text
    assert "batch_export_verified" in text
    assert "list_diagnostic_events" in text

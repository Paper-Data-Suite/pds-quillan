from __future__ import annotations

import ast
import inspect

import pytest

import quillan.publication_projection_policy as policy_module

from quillan.publication_projection_policy import (
    PROHIBITED_PUBLICATION_NATIVE_FIELDS,
    PUBLICATION_PROJECTION_POLICY_VERSION,
    PUBLIC_PDS2_EVIDENCE_REFERENCE_FIELDS,
    RETURNED_REQUIREMENT_FEEDBACK_FIELDS,
    SOURCE_ONLY_NATIVE_RECORDS,
    QuillanPublicationProjectionPolicyError,
    observation_is_selected_for_feedback,
    overall_rating_is_selected_for_feedback,
    project_feedback_comment_text,
    project_minimum_outcome_teacher_note,
    project_observation_rationale,
    project_overall_rating_rationale,
    publication_field_disposition,
    returned_requirement_check_is_feedback_publishable,
    selected_pds2_evidence_is_publishable,
)


def assert_text(value: object, disposition: str, text: str | None) -> None:
    assert getattr(value, "disposition") == disposition
    assert getattr(value, "text") == text


def test_policy_version_is_stable() -> None:
    assert PUBLICATION_PROJECTION_POLICY_VERSION == "quillan_publication_projection_v1"


def test_observation_selected_by_global_and_same_standard_reference() -> None:
    assert observation_is_selected_for_feedback(
        include_review_unit_observations=True,
        observation_id="observation_0001",
        standard_id="njsls-ela:RL.CR.9-10.1",
        included_observation_ids_by_standard={
            "njsls-ela:RL.CR.9-10.1": ("observation_0001",),
        },
    )


def test_observation_global_disable_withholds_rationale() -> None:
    result = project_observation_rationale(
        "Selected teacher explanation.",
        include_review_unit_observations=False,
        observation_id="observation_0001",
        standard_id="std:1",
        included_observation_ids_by_standard={"std:1": ("observation_0001",)},
    )
    assert_text(result, "withheld", None)


def test_observation_unselected_withholds_rationale() -> None:
    result = project_observation_rationale(
        "Private observation explanation.",
        include_review_unit_observations=True,
        observation_id="observation_0002",
        standard_id="std:1",
        included_observation_ids_by_standard={"std:1": ("observation_0001",)},
    )
    assert_text(result, "withheld", None)


def test_observation_selected_in_other_standard_does_not_publish() -> None:
    result = project_observation_rationale(
        "Wrong-standard selection must not broaden disclosure.",
        include_review_unit_observations=True,
        observation_id="observation_0001",
        standard_id="std:1",
        included_observation_ids_by_standard={"std:2": ("observation_0001",)},
    )
    assert_text(result, "withheld", None)


def test_observation_selected_includes_exact_rationale() -> None:
    result = project_observation_rationale(
        "Keep this exact text.",
        include_review_unit_observations=True,
        observation_id="observation_0001",
        standard_id="std:1",
        included_observation_ids_by_standard={"std:1": ("observation_0001",)},
    )
    assert_text(result, "included", "Keep this exact text.")


def test_missing_observation_rationale_is_absent_even_when_selected() -> None:
    result = project_observation_rationale(
        None,
        include_review_unit_observations=True,
        observation_id="observation_0001",
        standard_id="std:1",
        included_observation_ids_by_standard={"std:1": ("observation_0001",)},
    )
    assert_text(result, "absent", None)


def test_overall_global_disable_withholds_rationale() -> None:
    result = project_overall_rating_rationale(
        "Teacher rationale.",
        include_overall_standard_ratings=False,
        rating_include_in_feedback=True,
        standard_feedback_include_overall_rating=True,
        standard_feedback_include_overall_rationale=True,
    )
    assert_text(result, "withheld", None)


def test_overall_per_standard_rating_and_rationale_include() -> None:
    result = project_overall_rating_rationale(
        "Teacher rationale.",
        include_overall_standard_ratings=True,
        rating_include_in_feedback=False,
        standard_feedback_include_overall_rating=True,
        standard_feedback_include_overall_rationale=True,
    )
    assert_text(result, "included", "Teacher rationale.")


def test_overall_per_standard_rationale_disable_withholds() -> None:
    result = project_overall_rating_rationale(
        "Teacher rationale.",
        include_overall_standard_ratings=True,
        rating_include_in_feedback=True,
        standard_feedback_include_overall_rating=True,
        standard_feedback_include_overall_rationale=False,
    )
    assert_text(result, "withheld", None)


def test_overall_per_standard_rating_disable_withholds_rationale() -> None:
    result = project_overall_rating_rationale(
        "Teacher rationale.",
        include_overall_standard_ratings=True,
        rating_include_in_feedback=True,
        standard_feedback_include_overall_rating=False,
        standard_feedback_include_overall_rationale=True,
    )
    assert_text(result, "withheld", None)


def test_overall_fallback_preserves_native_rating_include_flag() -> None:
    assert overall_rating_is_selected_for_feedback(
        include_overall_standard_ratings=True,
        rating_include_in_feedback=True,
        standard_feedback_include_overall_rating=None,
        standard_feedback_include_overall_rationale=None,
    )
    result = project_overall_rating_rationale(
        "Fallback rationale.",
        include_overall_standard_ratings=True,
        rating_include_in_feedback=True,
        standard_feedback_include_overall_rating=None,
        standard_feedback_include_overall_rationale=None,
    )
    assert_text(result, "included", "Fallback rationale.")


def test_overall_fallback_false_withholds() -> None:
    result = project_overall_rating_rationale(
        "Not selected.",
        include_overall_standard_ratings=True,
        rating_include_in_feedback=False,
        standard_feedback_include_overall_rating=None,
        standard_feedback_include_overall_rationale=None,
    )
    assert_text(result, "withheld", None)


def test_overall_missing_rationale_is_absent() -> None:
    result = project_overall_rating_rationale(
        None,
        include_overall_standard_ratings=True,
        rating_include_in_feedback=True,
        standard_feedback_include_overall_rating=None,
        standard_feedback_include_overall_rationale=None,
    )
    assert_text(result, "absent", None)


def test_partial_per_standard_overall_controls_fail_closed() -> None:
    with pytest.raises(QuillanPublicationProjectionPolicyError):
        project_overall_rating_rationale(
            "Teacher rationale.",
            include_overall_standard_ratings=True,
            rating_include_in_feedback=True,
            standard_feedback_include_overall_rating=True,
            standard_feedback_include_overall_rationale=None,
        )


def test_selected_feedback_comment_is_included_exactly() -> None:
    result = project_feedback_comment_text(
        "Use this exact copied review text.", include_in_feedback=True
    )
    assert result is not None
    assert_text(result, "included", "Use this exact copied review text.")


def test_unselected_feedback_comment_is_omitted() -> None:
    assert (
        project_feedback_comment_text("Do not publish me.", include_in_feedback=False)
        is None
    )


def test_returned_work_outcome_note_is_included() -> None:
    result = project_minimum_outcome_teacher_note(
        "Add the required textual evidence and resubmit.",
        status="returned_without_full_review",
        returned_without_full_review=True,
        review_state="returned_without_full_review",
    )
    assert_text(result, "included", "Add the required textual evidence and resubmit.")


@pytest.mark.parametrize("status", ["met", "unmet_continue_review", "not_checked"])
def test_non_return_outcome_notes_are_withheld(status: str) -> None:
    result = project_minimum_outcome_teacher_note(
        "Teacher-only outcome note.",
        status=status,
        returned_without_full_review=False,
        review_state="requirements_checked",
    )
    assert_text(result, "withheld", None)


def test_missing_minimum_outcome_note_is_absent() -> None:
    result = project_minimum_outcome_teacher_note(
        None,
        status="met",
        returned_without_full_review=False,
        review_state="requirements_checked",
    )
    assert_text(result, "absent", None)


def test_returned_work_signals_must_agree() -> None:
    with pytest.raises(QuillanPublicationProjectionPolicyError):
        project_minimum_outcome_teacher_note(
            "Contradictory source.",
            status="returned_without_full_review",
            returned_without_full_review=False,
            review_state="returned_without_full_review",
        )



def test_returned_work_only_publishes_configured_unmet_requirement() -> None:
    assert returned_requirement_check_is_feedback_publishable(
        requirement_key="required_elements:textual evidence",
        met=False,
        configured_requirement_keys={"required_elements:textual evidence"},
        status="returned_without_full_review",
        returned_without_full_review=True,
        review_state="returned_without_full_review",
    )


def test_returned_work_does_not_publish_met_or_unconfigured_requirement() -> None:
    assert not returned_requirement_check_is_feedback_publishable(
        requirement_key="paragraphs_min",
        met=True,
        configured_requirement_keys={"paragraphs_min"},
        status="returned_without_full_review",
        returned_without_full_review=True,
        review_state="returned_without_full_review",
    )
    assert not returned_requirement_check_is_feedback_publishable(
        requirement_key="word_count_min",
        met=False,
        configured_requirement_keys={"paragraphs_min"},
        status="returned_without_full_review",
        returned_without_full_review=True,
        review_state="returned_without_full_review",
    )


def test_requirement_check_not_publishable_outside_returned_work() -> None:
    assert not returned_requirement_check_is_feedback_publishable(
        requirement_key="paragraphs_min",
        met=False,
        configured_requirement_keys={"paragraphs_min"},
        status="unmet_continue_review",
        returned_without_full_review=False,
        review_state="requirements_checked",
    )

def test_selected_pds2_evidence_is_publishable() -> None:
    assert selected_pds2_evidence_is_publishable(
        page_selected_evidence_id="obs_01",
        evidence_id="obs_01",
        evidence_role="selected",
    )


@pytest.mark.parametrize("role", ["candidate", "replacement", "excluded"])
def test_unselected_pds2_evidence_is_not_publishable(role: str) -> None:
    assert not selected_pds2_evidence_is_publishable(
        page_selected_evidence_id="obs_selected",
        evidence_id="obs_other",
        evidence_role=role,
    )


def test_page_without_selected_evidence_publishes_no_candidate() -> None:
    assert not selected_pds2_evidence_is_publishable(
        page_selected_evidence_id=None,
        evidence_id="obs_candidate",
        evidence_role="candidate",
    )


@pytest.mark.parametrize(
    ("selected_id", "evidence_id", "role"),
    [
        ("obs_01", "obs_01", "candidate"),
        ("obs_02", "obs_01", "selected"),
        (None, "obs_01", "selected"),
    ],
)
def test_selected_evidence_disagreement_fails_closed(
    selected_id: str | None, evidence_id: str, role: str
) -> None:
    with pytest.raises(QuillanPublicationProjectionPolicyError):
        selected_pds2_evidence_is_publishable(
            page_selected_evidence_id=selected_id,
            evidence_id=evidence_id,
            evidence_role=role,
        )


def test_field_classifier_has_closed_high_risk_allowlist() -> None:
    assert publication_field_disposition("route_id") == "allowed"
    assert publication_field_disposition("review.json") == "source_only"
    assert publication_field_disposition("review.private_notes") == "prohibited"
    with pytest.raises(QuillanPublicationProjectionPolicyError):
        publication_field_disposition("future.unknown_field")


def test_field_sets_preserve_expected_privacy_boundary() -> None:
    assert "source_filename" not in PUBLIC_PDS2_EVIDENCE_REFERENCE_FIELDS
    assert "retained_source_path" not in PUBLIC_PDS2_EVIDENCE_REFERENCE_FIELDS
    assert "review.private_notes" in PROHIBITED_PUBLICATION_NATIVE_FIELDS
    assert "submission.json" in SOURCE_ONLY_NATIVE_RECORDS
    assert RETURNED_REQUIREMENT_FEEDBACK_FIELDS == {
        "label",
        "expected",
        "teacher_note",
    }


def test_overlong_selected_text_fails_instead_of_truncating() -> None:
    with pytest.raises(QuillanPublicationProjectionPolicyError):
        project_feedback_comment_text("x" * 20_001, include_in_feedback=True)

@pytest.mark.parametrize(
    "field",
    [
        "feedback.comments.source",
        "feedback.comments.reusable_comment_id",
        "feedback.comments.save_for_reuse",
        "feedback.comments.module_details",
    ],
)
def test_reusable_comment_provenance_fields_are_prohibited(field: str) -> None:
    assert publication_field_disposition(field) == "prohibited"


@pytest.mark.parametrize(
    "field",
    [
        "review.private_notes",
        "review.module_details",
        "minimum_requirement_checks.module_details",
        "submission.evidence.routed_evidence_path",
        "submission.evidence.retained_source.source_filename",
        "class_reports",
        "routing_diagnostics",
    ],
)
def test_private_operational_and_classwide_fields_are_prohibited(field: str) -> None:
    assert publication_field_disposition(field) == "prohibited"


def test_selected_evidence_reference_allowlist_is_exact() -> None:
    assert PUBLIC_PDS2_EVIDENCE_REFERENCE_FIELDS == {
        "page_id",
        "evidence_id",
        "observation_id",
        "route_id",
        "issuance_id",
        "generation_id",
        "artifact_id",
        "source_page_number",
        "source_scan_id",
        "source_sha256",
        "routed_evidence_sha256",
    }


def test_unselected_duplicate_alternative_is_not_publishable() -> None:
    assert not selected_pds2_evidence_is_publishable(
        page_selected_evidence_id="obs_selected",
        evidence_id="obs_duplicate_alternative",
        evidence_role="candidate",
    )


def test_source_only_native_record_allowlist_is_exact() -> None:
    assert SOURCE_ONLY_NATIVE_RECORDS == {
        "assignment.json",
        "submission.json",
        "review.json",
    }


def test_unknown_roster_extension_fails_closed() -> None:
    with pytest.raises(QuillanPublicationProjectionPolicyError):
        publication_field_disposition("roster.guardian_email")


def test_policy_module_imports_only_pure_contract_dependencies() -> None:
    tree = ast.parse(inspect.getsource(policy_module))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    assert imported_modules == {
        "__future__",
        "collections.abc",
        "typing",
        "quillan.academic_result_manifest",
    }


def test_policy_module_has_no_direct_file_or_dynamic_execution_calls() -> None:
    tree = ast.parse(inspect.getsource(policy_module))
    prohibited_calls = {"open", "exec", "eval", "__import__"}
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint(prohibited_calls)


def test_policy_functions_have_no_privacy_bypass_parameters() -> None:
    function_names = [
        "observation_is_selected_for_feedback",
        "project_observation_rationale",
        "overall_rating_is_selected_for_feedback",
        "project_overall_rating_rationale",
        "project_feedback_comment_text",
        "project_minimum_outcome_teacher_note",
        "returned_requirement_check_is_feedback_publishable",
        "selected_pds2_evidence_is_publishable",
        "publication_field_disposition",
    ]
    forbidden_parameters = {
        "include_private",
        "teacher_mode",
        "admin_mode",
        "include_all",
        "debug",
        "role",
        "audience",
        "actor",
        "authorization",
        "workspace_root",
        "catalog",
        "publication_record",
        "manifest_path",
        "source_path",
        "artifact_path",
    }
    for name in function_names:
        parameters = set(inspect.signature(getattr(policy_module, name)).parameters)
        assert parameters.isdisjoint(forbidden_parameters)


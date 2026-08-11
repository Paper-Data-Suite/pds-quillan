from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast

import pytest

from quillan.academic_result_manifest import (
    AcademicResultManifest,
    manifest_from_json_bytes,
    manifest_from_mapping,
    manifest_to_mapping,
)
from quillan.publication_revision_policy import (
    PUBLICATION_REVISION_POLICY_VERSION,
    QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
    ManifestRevisionPlan,
    QuillanPublicationRevisionConflictError,
    QuillanPublicationRevisionValidationError,
    manifests_have_same_publication_content,
    next_record_set_revision,
    plan_manifest_revision,
    validate_manifest_revision_transition,
)

FIXTURE = Path("tests/fixtures/publication/quillan_academic_result_manifest_v1.json")


def _mapping(*, revision: int = 1) -> dict[str, Any]:
    mapping = manifest_to_mapping(manifest_from_json_bytes(FIXTURE.read_bytes()))
    mapping["record_set"] = {
        "record_set_id": QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID,
        "revision": revision,
    }
    return mapping


def _manifest(*, revision: int = 1) -> AcademicResultManifest:
    return manifest_from_mapping(_mapping(revision=revision))


def _with_revision(mapping: dict[str, Any], revision: int) -> dict[str, Any]:
    updated = copy.deepcopy(mapping)
    updated["record_set"]["revision"] = revision
    return updated


def _student(mapping: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return cast(dict[str, Any], mapping["students"][index])


def _review(mapping: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return cast(dict[str, Any], _student(mapping, index)["review"])


def _overall_rating(mapping: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], _review(mapping)["overall_standard_ratings"][0])


def _successor_plan(
    predecessor: AcademicResultManifest,
    candidate: AcademicResultManifest,
    *,
    history: tuple[AcademicResultManifest, ...] = (),
    republish_after_withdrawal: bool = False,
) -> ManifestRevisionPlan:
    return plan_manifest_revision(
        predecessor=predecessor,
        candidate=candidate,
        allocated_revisions=(predecessor.record_set.revision,),
        historical_manifests=history,
        republish_after_withdrawal=republish_after_withdrawal,
    )


def test_policy_identity_is_stable() -> None:
    assert PUBLICATION_REVISION_POLICY_VERSION == "quillan_publication_revision_v1"
    assert QUILLAN_ACADEMIC_RESULT_RECORD_SET_ID == "academic_results"


def test_initial_plan_uses_revision_one() -> None:
    plan = plan_manifest_revision(
        predecessor=None,
        candidate=_manifest(revision=99),
        allocated_revisions=(),
    )
    assert plan == ManifestRevisionPlan(
        disposition="create_initial",
        reason="initial_publication",
        record_set_id="academic_results",
        record_set_revision=1,
        reuse_existing_bytes=False,
    )
    assert plan.requires_new_revision is True


def test_plan_is_frozen() -> None:
    plan = plan_manifest_revision(
        predecessor=None,
        candidate=_manifest(),
        allocated_revisions=(),
    )
    with pytest.raises(FrozenInstanceError):
        plan.record_set_revision = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("allocated", "expected"),
    [
        ((), 1),
        ((1,), 2),
        ((1, 3), 4),
        ((8, 2, 5), 9),
    ],
)
def test_next_record_set_revision_uses_highest_allocated_plus_one(
    allocated: tuple[int, ...], expected: int
) -> None:
    assert next_record_set_revision(allocated) == expected


@pytest.mark.parametrize("invalid", [(True,), (0,), (-1,), (1.0,)])
def test_next_revision_rejects_invalid_revision_values(invalid: object) -> None:
    with pytest.raises(QuillanPublicationRevisionValidationError):
        next_record_set_revision(cast(Any, invalid))


@pytest.mark.parametrize("invalid", [None, 1, 1.5])
def test_next_revision_rejects_noncollection_allocations(invalid: object) -> None:
    with pytest.raises(
        QuillanPublicationRevisionValidationError, match="collection"
    ):
        next_record_set_revision(cast(Any, invalid))


def test_next_revision_rejects_duplicate_allocations() -> None:
    with pytest.raises(QuillanPublicationRevisionConflictError, match="duplicate"):
        next_record_set_revision((1, 2, 2))


def test_initial_plan_rejects_existing_allocated_history() -> None:
    with pytest.raises(QuillanPublicationRevisionConflictError, match="initial"):
        plan_manifest_revision(
            predecessor=None,
            candidate=_manifest(),
            allocated_revisions=(1,),
        )


def test_content_comparison_ignores_only_generated_at_and_revision() -> None:
    previous = _mapping(revision=1)
    candidate = copy.deepcopy(previous)
    candidate["generated_at"] = "2026-08-11T20:00:00Z"
    candidate["record_set"]["revision"] = 17
    assert manifests_have_same_publication_content(
        manifest_from_mapping(previous), manifest_from_mapping(candidate)
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m["record_set"].update(record_set_id="other_results"),
        lambda m: m["work"].update(work_id="other_assignment"),
        lambda m: m["source_snapshot"].update(sha256="a" * 64),
        lambda m: m["assignment"].update(title="Corrected title"),
        lambda m: m["students"].pop(),
        lambda m: m["students"][0]["source_snapshot"]["submission"].update(
            sha256="b" * 64
        ),
        lambda m: m["students"][0]["source_snapshot"]["review"].update(
            sha256="c" * 64
        ),
        lambda m: m["students"][0]["submission"].update(submission_state="in_progress"),
        lambda m: m["students"][0]["review"].update(review_state="exported"),
        lambda m: m["students"][0]["review"]["overall_standard_ratings"][0].update(
            rating=2
        ),
        lambda m: m["students"][0]["review"]["feedback"].update(
            include_review_unit_observations=False
        ),
        lambda m: m["students"][0]["submission"]["digital_provenance"][
            "evidence_references"
        ][0].update(source_sha256="d" * 64),
    ],
)
def test_content_comparison_keeps_all_other_manifest_content_significant(
    mutate: Any,
) -> None:
    previous = _mapping(revision=1)
    candidate = copy.deepcopy(previous)
    mutate(candidate)
    if candidate["work"]["work_id"] == "other_assignment":
        candidate["assignment"]["assignment_id"] = "other_assignment"
        for student in candidate["students"]:
            student["submission"]["assignment_id"] = "other_assignment"
            student["review"]["assignment_id"] = "other_assignment"
    assert not manifests_have_same_publication_content(
        manifest_from_mapping(previous), manifest_from_mapping(candidate)
    )


def test_exact_replay_reuses_predecessor_revision_and_bytes() -> None:
    predecessor = _manifest(revision=4)
    candidate_mapping = _mapping(revision=91)
    candidate_mapping["generated_at"] = "2026-08-11T20:00:00Z"
    plan = plan_manifest_revision(
        predecessor=predecessor,
        candidate=manifest_from_mapping(candidate_mapping),
        allocated_revisions=(1, 2, 4),
    )
    assert plan.disposition == "reuse_existing"
    assert plan.reason == "exact_replay"
    assert plan.record_set_revision == 4
    assert plan.reuse_existing_bytes is True
    assert plan.requires_new_revision is False


def test_predecessor_must_be_highest_allocated_producer_revision() -> None:
    with pytest.raises(QuillanPublicationRevisionConflictError, match="highest"):
        plan_manifest_revision(
            predecessor=_manifest(revision=2),
            candidate=_manifest(revision=9),
            allocated_revisions=(1, 2, 3),
        )


def test_allocations_must_include_predecessor_revision() -> None:
    with pytest.raises(QuillanPublicationRevisionConflictError, match="include"):
        plan_manifest_revision(
            predecessor=_manifest(revision=2),
            candidate=_manifest(revision=9),
            allocated_revisions=(1, 3),
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: _overall_rating(m).update(rating=2),
        lambda m: _overall_rating(m)["rationale"].update(
            disposition="included", text="Corrected rationale."
        ),
        lambda m: _overall_rating(m).update(include_in_feedback=False),
        lambda m: _review(m)["overall_standard_ratings"].clear(),
        lambda m: _review(m).update(review_state="exported"),
        lambda m: _review(m)["feedback"].update(
            include_review_unit_observations=False
        ),
        lambda m: _student(m)["submission"]["digital_provenance"][
            "evidence_references"
        ][0].update(source_sha256="a" * 64),
        lambda m: m["assignment"].update(title="Corrected assignment title"),
        lambda m: m["students"].pop(),
    ],
)
def test_changed_publication_projection_requires_successor(mutate: Any) -> None:
    predecessor = _manifest(revision=1)
    candidate_mapping = _mapping(revision=77)
    mutate(candidate_mapping)
    candidate = manifest_from_mapping(candidate_mapping)
    plan = _successor_plan(predecessor, candidate)
    assert plan.disposition == "create_successor"
    assert plan.record_set_revision == 2
    assert plan.reuse_existing_bytes is False
    assert plan.requires_new_revision is True


def test_rating_removal_preserves_historical_low_rating_without_coercion() -> None:
    predecessor = _manifest(revision=1)
    assert predecessor.students[0].review.overall_standard_ratings[0].rating == 0

    candidate_mapping = _mapping(revision=2)
    _review(candidate_mapping)["overall_standard_ratings"] = []
    candidate = manifest_from_mapping(candidate_mapping)
    assert candidate.students[0].review.overall_standard_ratings == ()

    plan = _successor_plan(predecessor, candidate)
    assert plan.disposition == "create_successor"
    assert predecessor.students[0].review.overall_standard_ratings[0].rating == 0
    assert candidate.students[0].review.overall_standard_ratings == ()


@pytest.mark.parametrize(
    "source_mutation",
    [
        lambda m: m["source_snapshot"].update(sha256="a" * 64),
        lambda m: _student(m)["source_snapshot"]["submission"].update(
            sha256="b" * 64
        ),
        lambda m: _student(m)["source_snapshot"]["review"].update(sha256="c" * 64),
    ],
)
def test_exact_native_source_change_requires_successor_with_private_safe_reason(
    source_mutation: Any,
) -> None:
    predecessor = _manifest(revision=1)
    candidate_mapping = _mapping(revision=2)
    source_mutation(candidate_mapping)
    plan = _successor_plan(predecessor, manifest_from_mapping(candidate_mapping))
    assert plan.disposition == "create_successor"
    assert plan.reason == "native_source_changed"


def test_source_hash_reason_does_not_name_private_field() -> None:
    predecessor = _manifest(revision=1)
    candidate_mapping = _mapping(revision=2)
    _student(candidate_mapping)["source_snapshot"]["review"]["sha256"] = "f" * 64
    plan = _successor_plan(predecessor, manifest_from_mapping(candidate_mapping))
    assert plan.reason == "native_source_changed"
    assert "private" not in plan.reason
    assert "note" not in plan.reason


def test_projection_only_change_uses_projection_reason() -> None:
    predecessor = _manifest(revision=1)
    candidate_mapping = _mapping(revision=2)
    _overall_rating(candidate_mapping)["rating"] = 2
    plan = _successor_plan(predecessor, manifest_from_mapping(candidate_mapping))
    assert plan.reason == "publication_projection_changed"


def test_historical_reversion_allocates_new_revision_instead_of_reusing_old_one(
) -> None:
    state_a = _mapping(revision=1)
    state_b = copy.deepcopy(state_a)
    state_b["record_set"]["revision"] = 2
    _overall_rating(state_b)["rating"] = 2
    candidate = _with_revision(state_a, 99)

    plan = plan_manifest_revision(
        predecessor=manifest_from_mapping(state_b),
        candidate=manifest_from_mapping(candidate),
        allocated_revisions=(1, 2),
        historical_manifests=(manifest_from_mapping(state_a),),
    )
    assert plan.disposition == "create_successor"
    assert plan.reason == "historical_reversion"
    assert plan.record_set_revision == 3


def test_historical_reversion_does_not_mutate_prior_manifest() -> None:
    old = _manifest(revision=1)
    current_mapping = _mapping(revision=2)
    _overall_rating(current_mapping)["rating"] = 2
    current = manifest_from_mapping(current_mapping)
    candidate = _manifest(revision=20)
    old_before = manifest_to_mapping(old)

    plan_manifest_revision(
        predecessor=current,
        candidate=candidate,
        allocated_revisions=(1, 2),
        historical_manifests=(old,),
    )
    assert manifest_to_mapping(old) == old_before


def test_republication_after_withdrawal_forces_successor_even_when_content_matches(
) -> None:
    predecessor = _manifest(revision=7)
    plan = plan_manifest_revision(
        predecessor=predecessor,
        candidate=_manifest(revision=100),
        allocated_revisions=(1, 3, 7),
        republish_after_withdrawal=True,
    )
    assert plan.disposition == "create_successor"
    assert plan.reason == "republication_after_withdrawal"
    assert plan.record_set_revision == 8
    assert plan.reuse_existing_bytes is False


def test_republication_after_withdrawal_requires_predecessor() -> None:
    with pytest.raises(QuillanPublicationRevisionValidationError, match="predecessor"):
        plan_manifest_revision(
            predecessor=None,
            candidate=_manifest(),
            allocated_revisions=(),
            republish_after_withdrawal=True,
        )


def test_republication_flag_must_be_boolean() -> None:
    with pytest.raises(QuillanPublicationRevisionValidationError, match="boolean"):
        plan_manifest_revision(
            predecessor=_manifest(),
            candidate=_manifest(revision=2),
            allocated_revisions=(1,),
            republish_after_withdrawal=cast(Any, 1),
        )


def test_explicit_transition_accepts_greater_noncontiguous_revision() -> None:
    validate_manifest_revision_transition(_manifest(revision=2), _manifest(revision=8))


def test_explicit_transition_rejects_same_logical_revision() -> None:
    previous = _manifest(revision=2)
    candidate_mapping = _mapping(revision=2)
    _overall_rating(candidate_mapping)["rating"] = 2
    with pytest.raises(QuillanPublicationRevisionConflictError, match="logical"):
        validate_manifest_revision_transition(
            previous, manifest_from_mapping(candidate_mapping)
        )


def test_explicit_transition_rejects_lower_revision() -> None:
    with pytest.raises(QuillanPublicationRevisionValidationError, match="greater"):
        validate_manifest_revision_transition(
            _manifest(revision=3), _manifest(revision=2)
        )


def test_cross_work_transition_is_rejected() -> None:
    candidate_mapping = _mapping(revision=2)
    candidate_mapping["work"]["work_id"] = "different_assignment"
    candidate_mapping["assignment"]["assignment_id"] = "different_assignment"
    for student in candidate_mapping["students"]:
        student["submission"]["assignment_id"] = "different_assignment"
        student["review"]["assignment_id"] = "different_assignment"
    with pytest.raises(QuillanPublicationRevisionValidationError, match="series"):
        validate_manifest_revision_transition(
            _manifest(revision=1), manifest_from_mapping(candidate_mapping)
        )


def test_cross_record_set_transition_is_rejected() -> None:
    candidate_mapping = _mapping(revision=2)
    candidate_mapping["record_set"]["record_set_id"] = "other_results"
    candidate = manifest_from_mapping(candidate_mapping)
    with pytest.raises(
        QuillanPublicationRevisionValidationError, match="academic_results"
    ):
        validate_manifest_revision_transition(_manifest(revision=1), candidate)


def test_planner_rejects_nonproduction_record_set_identity() -> None:
    candidate_mapping = _mapping(revision=1)
    candidate_mapping["record_set"]["record_set_id"] = "synthetic_results"
    with pytest.raises(
        QuillanPublicationRevisionValidationError, match="academic_results"
    ):
        plan_manifest_revision(
            predecessor=None,
            candidate=manifest_from_mapping(candidate_mapping),
            allocated_revisions=(),
        )


@pytest.mark.parametrize("invalid", [None, 1, 1.5])
def test_planner_rejects_noncollection_historical_manifests(invalid: object) -> None:
    with pytest.raises(
        QuillanPublicationRevisionValidationError, match="collection"
    ):
        plan_manifest_revision(
            predecessor=_manifest(revision=1),
            candidate=_manifest(revision=2),
            allocated_revisions=(1,),
            historical_manifests=cast(Any, invalid),
        )


def test_historical_manifest_must_precede_current_head() -> None:
    with pytest.raises(QuillanPublicationRevisionValidationError, match="precede"):
        plan_manifest_revision(
            predecessor=_manifest(revision=2),
            candidate=_manifest(revision=3),
            allocated_revisions=(1, 2),
            historical_manifests=(_manifest(revision=3),),
        )


def test_historical_manifest_must_be_same_series() -> None:
    historical_mapping = _mapping(revision=1)
    historical_mapping["work"]["work_id"] = "other_assignment"
    historical_mapping["assignment"]["assignment_id"] = "other_assignment"
    for student in historical_mapping["students"]:
        student["submission"]["assignment_id"] = "other_assignment"
        student["review"]["assignment_id"] = "other_assignment"
    with pytest.raises(QuillanPublicationRevisionValidationError, match="series"):
        plan_manifest_revision(
            predecessor=_manifest(revision=2),
            candidate=_manifest(revision=3),
            allocated_revisions=(1, 2),
            historical_manifests=(manifest_from_mapping(historical_mapping),),
        )


def test_policy_decisions_do_not_mutate_candidate_or_predecessor() -> None:
    predecessor = _manifest(revision=1)
    candidate_mapping = _mapping(revision=44)
    _overall_rating(candidate_mapping)["rating"] = 2
    candidate = manifest_from_mapping(candidate_mapping)
    previous_before = manifest_to_mapping(predecessor)
    candidate_before = manifest_to_mapping(candidate)

    _successor_plan(predecessor, candidate)

    assert manifest_to_mapping(predecessor) == previous_before
    assert manifest_to_mapping(candidate) == candidate_before


def test_minimum_requirement_correction_requires_successor_without_numeric_coercion(
) -> None:
    predecessor_mapping = _mapping(revision=1)
    current_mapping = _mapping(revision=2)
    returned_review = _review(current_mapping, 1)
    returned_review["review_state"] = "not_started"
    outcome = returned_review["minimum_requirement_outcome"]
    outcome["status"] = "not_checked"
    outcome["returned_without_full_review"] = False
    outcome["teacher_note"] = {"disposition": "absent", "text": None}
    outcome["updated_at"] = None

    predecessor = manifest_from_mapping(predecessor_mapping)
    candidate = manifest_from_mapping(current_mapping)
    plan = _successor_plan(predecessor, candidate)

    assert plan.disposition == "create_successor"
    assert candidate.students[1].review.review_state == "not_started"
    assert candidate.students[1].review.overall_standard_ratings == ()


def test_historical_rating_keeps_its_own_assignment_scale_meaning() -> None:
    predecessor = _manifest(revision=1)
    assert predecessor.assignment.rating_scale.levels[0].label == "Beginning"
    assert predecessor.students[0].review.overall_standard_ratings[0].rating == 0

    candidate_mapping = _mapping(revision=2)
    candidate_mapping["assignment"]["rating_scale"]["levels"][0]["label"] = (
        "Needs Development"
    )
    candidate = manifest_from_mapping(candidate_mapping)
    plan = _successor_plan(predecessor, candidate)

    assert plan.disposition == "create_successor"
    assert predecessor.assignment.rating_scale.levels[0].label == "Beginning"
    assert candidate.assignment.rating_scale.levels[0].label == "Needs Development"


def test_adding_represented_student_requires_complete_successor_snapshot() -> None:
    predecessor_mapping = _mapping(revision=1)
    predecessor_mapping["students"] = predecessor_mapping["students"][:1]
    predecessor = manifest_from_mapping(predecessor_mapping)

    candidate = _manifest(revision=2)
    plan = _successor_plan(predecessor, candidate)

    assert plan.disposition == "create_successor"
    assert len(predecessor.students) == 1
    assert len(candidate.students) == 2


def test_normative_manifest_fixture_remains_byte_exact() -> None:
    from quillan.academic_result_manifest import manifest_to_canonical_json_bytes

    fixture = FIXTURE.read_bytes()
    manifest = manifest_from_json_bytes(fixture)
    assert manifest_to_canonical_json_bytes(manifest) == fixture


def test_policy_module_imports_only_contract_and_standard_library() -> None:
    import ast
    import inspect

    import quillan.publication_revision_policy as policy_module

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
        "dataclasses",
        "typing",
        "quillan.academic_result_manifest",
    }


def test_policy_module_has_no_io_hashing_or_dynamic_execution_calls() -> None:
    import ast
    import inspect

    import quillan.publication_revision_policy as policy_module

    tree = ast.parse(inspect.getsource(policy_module))
    prohibited_names = {
        "open",
        "exec",
        "eval",
        "__import__",
        "Path",
        "sha256",
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint(prohibited_names)


def test_policy_public_functions_have_no_workspace_core_or_consumer_parameters(
) -> None:
    import inspect

    import quillan.publication_revision_policy as policy_module

    function_names = [
        "manifests_have_same_publication_content",
        "next_record_set_revision",
        "validate_manifest_revision_transition",
        "plan_manifest_revision",
    ]
    forbidden = {
        "workspace_root",
        "manifest_path",
        "source_path",
        "catalog",
        "registry",
        "publication_record",
        "withdrawal",
        "authorization",
        "audience",
        "grade",
        "proficiency",
        "portfolio",
    }
    for name in function_names:
        parameters = set(inspect.signature(getattr(policy_module, name)).parameters)
        assert parameters.isdisjoint(forbidden)

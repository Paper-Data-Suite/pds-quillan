"""Constructor corruption coverage for the public #339 result models."""

from dataclasses import replace
from pathlib import Path
from collections.abc import Callable
from types import MappingProxyType
from typing import Any

import pytest

from quillan.intake_assembly import QuillanPostDispatchPersistenceResult
from quillan.assignment_submission_assembly import (
    assemble_assignment_submissions,
    discover_assignment_routed_evidence_status,
)
from quillan.pds2_scan_intake import QuillanScanIntakeSummary, QuillanScanSourceResult
from quillan.response_page_observation_persistence import (
    PersistedQuillanPageObservation,
    QuillanObservationPersistenceBatch,
    QuillanObservationPersistenceFailure,
    persist_quillan_page_observation,
    persist_quillan_scan_observations,
)
import quillan.response_page_observation_persistence as persistence_service
from quillan.response_page_observations import (
    discover_quillan_page_observations_status,
)
from quillan.submission_observation_assembly import (
    AssembledQuillanSubmission,
    QuillanSubmissionAssemblyBatch,
    QuillanSubmissionAssemblyFailure,
    assemble_quillan_submission_manifests,
)
from quillan.submission_manifest_paths import submission_manifest_path
from tests.observation_test_support import successful_image_page


def _models(
    root: Path,
) -> tuple[
    PersistedQuillanPageObservation,
    QuillanObservationPersistenceFailure,
    QuillanObservationPersistenceBatch,
    QuillanSubmissionAssemblyFailure,
    AssembledQuillanSubmission,
    QuillanSubmissionAssemblyBatch,
    QuillanPostDispatchPersistenceResult,
]:
    outcome = successful_image_page(root)
    persisted = persist_quillan_page_observation(root, outcome)
    observation = persisted.observation
    source = QuillanScanSourceResult(
        source_path=root / observation.source_filename,
        source_filename=observation.source_filename,
        source_type="image",
        retained_source=outcome.retained_source,
        pages=(outcome,),
        registry_module_ids=("quillan",),
    )
    summary = QuillanScanIntakeSummary((source,), ("quillan",))
    failure = QuillanObservationPersistenceFailure(
        observation.source_scan_id,
        observation.source_page_number,
        observation.route_id,
        observation.page_id,
        ValueError("expected"),
        persisted.observation_path,
        persisted.evidence_path,
    )
    persistence = QuillanObservationPersistenceBatch(summary, (persisted,), (), 0)
    assembly = assemble_quillan_submission_manifests(
        root, observation.class_id, observation.assignment_id
    )
    assembled = assembly.assembled[0]
    assembly_failure = QuillanSubmissionAssemblyFailure(
        "observation_invalid",
        observation.class_id,
        observation.assignment_id,
        observation.student_id,
        (observation.issuance_id,),
        (observation.observation_id,),
        (observation.page_id,),
        (observation.logical_page,),
        (observation.source_scan_id,),
        (observation.source_page_number,),
        "expected failure",
        ValueError("expected"),
        assembled.manifest_path,
    )
    post = QuillanPostDispatchPersistenceResult(summary, persistence, assembly)
    return persisted, failure, persistence, assembly_failure, assembled, assembly, post


def test_every_public_result_model_rejects_constructor_corruption(
    tmp_path: Path,
) -> None:
    persisted, failure, persistence, assembly_failure, assembled, assembly, post = (
        _models(tmp_path)
    )
    unsafe_replace: Any = replace
    corruptions: tuple[Callable[[], object], ...] = (
        lambda: unsafe_replace(persisted, status="invalid"),
        lambda: unsafe_replace(failure, source_page_number=True),
        lambda: unsafe_replace(persistence, persisted=[persisted]),
        lambda: unsafe_replace(assembly_failure, category="invented"),
        lambda: unsafe_replace(assembled, assembly_revision=False),
        lambda: unsafe_replace(assembly, assembled=(assembled, assembled)),
        lambda: unsafe_replace(
            post,
            intake_summary=QuillanScanIntakeSummary((), ("quillan",)),
        ),
    )
    for corrupt in corruptions:
        with pytest.raises(ValueError):
            corrupt()


def test_result_collections_reject_overlap_duplicates_and_nonexceptions(
    tmp_path: Path,
) -> None:
    persisted, failure, persistence, assembly_failure, assembled, assembly, _ = _models(
        tmp_path
    )
    unsafe_replace: Any = replace
    with pytest.raises(ValueError, match="both persisted and failed"):
        replace(persistence, failures=(failure,))
    with pytest.raises(ValueError, match="unique"):
        replace(persistence, persisted=(persisted, persisted))
    with pytest.raises(ValueError, match="Exception"):
        unsafe_replace(failure, error="not an exception")
    with pytest.raises(ValueError, match="tuples"):
        unsafe_replace(assembly, failures=[assembly_failure])
    with pytest.raises(ValueError, match="disjoint"):
        replace(assembled, missing_pages=(1,), duplicate_pages=(1,))


def test_persisted_result_requires_exact_canonical_absolute_relative_paths(
    tmp_path: Path,
) -> None:
    persisted, _, _, _, _, _, _ = _models(tmp_path)
    sibling = tmp_path.parent / f"{tmp_path.name}-sibling"
    sibling.mkdir()
    outside_observation = sibling.joinpath(
        *Path(persisted.observation_relative_path).parts
    )
    outside_evidence = sibling.joinpath(*Path(persisted.evidence_relative_path).parts)
    other_class_observation = tmp_path.joinpath(
        *Path(persisted.observation_relative_path).parts
    )
    other_class_observation = Path(
        str(other_class_observation).replace(
            persisted.observation.class_id, "different_class", 1
        )
    )
    noncanonical = persisted.observation_path.parent / ".." / persisted.observation_path.name
    unsafe_replace: Any = replace
    corruptions: tuple[dict[str, object], ...] = (
        {"observation_path": outside_observation},
        {"evidence_path": outside_evidence},
        {
            "observation_path": other_class_observation,
            "observation_relative_path": other_class_observation.relative_to(
                tmp_path
            ).as_posix(),
        },
        {"observation_relative_path": persisted.observation_relative_path.replace("/", "\\")},
        {"observation_relative_path": str(persisted.observation_path)},
        {"observation_relative_path": f"./{persisted.observation_relative_path}"},
        {"evidence_relative_path": f"../{persisted.evidence_relative_path}"},
        {"observation_path": noncanonical},
    )
    for changes in corruptions:
        with pytest.raises(ValueError):
            unsafe_replace(persisted, **changes)


def test_assembled_result_requires_exact_canonical_absolute_relative_path(
    tmp_path: Path,
) -> None:
    _, _, _, _, assembled, _, _ = _models(tmp_path)
    sibling = tmp_path.parent / f"{tmp_path.name}-sibling"
    sibling.mkdir()
    sibling_manifest = sibling.joinpath(*Path(assembled.manifest_relative_path).parts)
    different = submission_manifest_path(
        tmp_path,
        "different_class",
        assembled.assignment_id,
        assembled.student_id,
    )
    noncanonical = assembled.manifest_path.parent / ".." / assembled.manifest_path.name
    unsafe_replace: Any = replace
    corruptions: tuple[dict[str, object], ...] = (
        {"manifest_path": sibling_manifest},
        {
            "manifest_path": different,
            "manifest_relative_path": different.relative_to(tmp_path).as_posix(),
        },
        {"manifest_relative_path": assembled.manifest_relative_path.replace("/", "\\")},
        {"manifest_relative_path": str(assembled.manifest_path)},
        {"manifest_relative_path": f"./{assembled.manifest_relative_path}"},
        {"manifest_relative_path": f"../{assembled.manifest_relative_path}"},
        {"manifest_path": noncanonical},
    )
    for changes in corruptions:
        with pytest.raises(ValueError):
            unsafe_replace(assembled, **changes)


def test_assembly_batch_enforces_ordering_occurrence_and_target_invariants(
    tmp_path: Path,
) -> None:
    _, _, _, failure, assembled, _, _ = _models(tmp_path)
    second_student = "student_z"
    second_manifest = submission_manifest_path(
        tmp_path, assembled.class_id, assembled.assignment_id, second_student
    )
    second_assembled = replace(
        assembled,
        student_id=second_student,
        manifest_path=second_manifest,
        manifest_relative_path=second_manifest.relative_to(tmp_path).as_posix(),
    )
    second_failure = replace(
        failure,
        student_id=second_student,
        possible_manifest_path=second_manifest,
    )
    with pytest.raises(ValueError, match="deterministically ordered"):
        QuillanSubmissionAssemblyBatch((second_assembled, assembled), ())
    with pytest.raises(ValueError, match="deterministically ordered"):
        QuillanSubmissionAssemblyBatch((), (second_failure, failure))
    with pytest.raises(ValueError, match="duplicated"):
        QuillanSubmissionAssemblyBatch((), (failure, failure))
    with pytest.raises(ValueError, match="occurrence keys"):
        QuillanSubmissionAssemblyBatch(
            (), (failure, replace(failure, reason="a different reason"))
        )
    with pytest.raises(ValueError, match="both assembled and failed"):
        QuillanSubmissionAssemblyBatch((assembled,), (failure,))


def test_persistence_batch_contains_original_unexpected_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, _, _, _, _, post = _models(tmp_path)
    original = RuntimeError("programming failure")
    monkeypatch.setattr(
        persistence_service,
        "persist_quillan_page_observation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(original),
    )
    result = persist_quillan_scan_observations(tmp_path, post.intake_summary)
    assert result.failure_count == 1
    assert result.failures[0].error is original


def test_new_public_discovery_and_assignment_models_reject_corruption(
    tmp_path: Path,
) -> None:
    persisted, _, _, _, _, _, _ = _models(tmp_path)
    observation = persisted.observation
    discovery = discover_quillan_page_observations_status(
        tmp_path, observation.class_id, observation.assignment_id
    )
    grouped = discover_assignment_routed_evidence_status(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assignment = assemble_assignment_submissions(
        tmp_path, observation.class_id, observation.assignment_id
    )
    summary = assignment.student_summaries[0]
    unsafe_replace: Any = replace
    corruptions: tuple[Callable[[], object], ...] = (
        lambda: unsafe_replace(discovery, observations=list(discovery.observations)),
        lambda: replace(discovery, observation_paths=()),
        lambda: replace(
            discovery,
            observations=(discovery.observations[0], discovery.observations[0]),
            observation_paths=(discovery.observation_paths[0],) * 2,
        ),
        lambda: unsafe_replace(grouped, evidence_by_student=dict(grouped.evidence_by_student)),
        lambda: unsafe_replace(
            grouped,
            evidence_by_student=MappingProxyType(
                {observation.student_id: [observation]}
            ),
        ),
        lambda: unsafe_replace(summary, status="failed"),
        lambda: unsafe_replace(summary, missing_pages=[1]),
        lambda: replace(
            assignment,
            written_manifests=assignment.skipped_existing_manifests,
        ),
        lambda: unsafe_replace(assignment, failures=list(assignment.failures)),
        lambda: replace(
            assignment,
            students_with_evidence=(observation.student_id,) * 2,
        ),
    )
    for corrupt in corruptions:
        with pytest.raises(ValueError):
            corrupt()

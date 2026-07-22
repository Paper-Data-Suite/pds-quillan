"""Issuance-based observation assembly and conservative idempotency."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from collections.abc import Callable
from typing import Any

import pytest
from pds_core.scan_routes import build_retained_source_filename

from quillan.module_errors import (
    QuillanCategorizedAssemblyError,
    QuillanSubmissionObservationAssemblyError,
)
from quillan.pds2_scan_intake import QuillanScanIntakeSummary
from quillan.printable_response_persistence import (
    PrintableResponseNotFoundError,
    PrintableResponsePersistenceError,
    load_printable_response_record_set,
)
import quillan.submission_observation_assembly as observation_assembly
from quillan.response_page_observation_persistence import (
    QuillanObservationPersistenceBatch,
    persist_quillan_page_observation,
)
from quillan.response_page_observations import (
    canonical_response_page_observation_json,
    derive_observation_id,
)
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
    validate_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestConcurrencyError,
    SubmissionManifestPathError,
    persist_submission_manifest,
    write_submission_manifest,
)
from quillan.submission_observation_assembly import (
    ASSEMBLY_FAILURE_CATEGORIES,
    QuillanSubmissionAssemblyBatch,
    assemble_quillan_scan_observations,
    assemble_quillan_submission_manifests,
)
from quillan.submission_page_management import mark_submission_page_needs_rescan
from quillan.work_paths import (
    quillan_work_ref,
    response_page_observation_path,
    routed_evidence_path,
)
from tests.observation_test_support import successful_image_page, successful_pdf_pages
from tests.review_test_support import _write_assignment


def test_observation_assembly_creates_then_leaves_manifest_unchanged(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    first = assemble_quillan_submission_manifests(
        tmp_path,
        observation.class_id,
        observation.assignment_id,
        timestamp="2026-07-21T00:00:00+00:00",
    )
    assert not first.failures
    assert first.assembled[0].status == "created"
    manifest = load_submission_manifest(first.assembled[0].manifest_path)
    assert manifest["module_details"]["response_issuance_id"] == observation.issuance_id
    assert manifest["pages"][0]["selected_evidence_id"] == observation.observation_id
    original = first.assembled[0].manifest_path.read_bytes()
    second = assemble_quillan_submission_manifests(
        tmp_path,
        observation.class_id,
        observation.assignment_id,
        timestamp="2026-07-22T00:00:00+00:00",
    )
    assert second.assembled[0].status == "unchanged"
    assert second.assembled[0].manifest_path.read_bytes() == original


def test_complete_issuance_membership_preserves_missing_pages(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path, pages=3)
    )
    observation = persisted.observation
    result = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest = load_submission_manifest(result.assembled[0].manifest_path)
    assert [page["page_state"] for page in manifest["pages"]] == [
        "present",
        "missing",
        "missing",
    ]
    assert result.assembled[0].missing_pages == (2, 3)


def test_two_physical_occurrences_remain_duplicate_candidates(tmp_path: Path) -> None:
    outcomes = successful_pdf_pages(tmp_path)
    persisted = tuple(
        persist_quillan_page_observation(tmp_path, outcome) for outcome in outcomes
    )
    observation = persisted[0].observation
    result = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest = load_submission_manifest(result.assembled[0].manifest_path)
    page = manifest["pages"][0]
    assert page["page_state"] == "duplicate"
    assert page["selected_evidence_id"] is None
    assert [item["evidence_id"] for item in page["evidence"]] == [
        item.observation.observation_id for item in persisted
    ]
    assert [item["duplicate_number"] for item in page["evidence"]] == [None, 1]


def test_new_duplicate_preserves_teacher_needs_rescan_state(tmp_path: Path) -> None:
    first_outcome, second_outcome = successful_pdf_pages(tmp_path)
    first = persist_quillan_page_observation(tmp_path, first_outcome)
    observation = first.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    _write_assignment(
        tmp_path,
        class_id=observation.class_id,
        assignment_id=observation.assignment_id,
    )
    assert assembled.assembled[0].status == "created"
    mark_submission_page_needs_rescan(
        tmp_path,
        observation.class_id,
        observation.assignment_id,
        observation.student_id,
        1,
    )

    second = persist_quillan_page_observation(tmp_path, second_outcome)
    updated = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest = load_submission_manifest(updated.assembled[0].manifest_path)
    page = manifest["pages"][0]
    assert updated.assembled[0].status == "updated"
    assert page["page_state"] == "needs_rescan"
    assert page["selected_evidence_id"] is None
    assert page["evidence"][0]["evidence_state"] == "needs_rescan"
    assert page["evidence"][0]["evidence_role"] == "candidate"
    assert page["evidence"][1]["evidence_id"] == second.observation.observation_id
    assert page["evidence"][1]["evidence_state"] == "active"


def test_new_duplicate_preserves_existing_selection(tmp_path: Path) -> None:
    first_outcome, second_outcome = successful_pdf_pages(tmp_path)
    first = persist_quillan_page_observation(tmp_path, first_outcome)
    observation = first.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    original = load_submission_manifest(assembled.assembled[0].manifest_path)
    assert original["pages"][0]["selected_evidence_id"] == observation.observation_id

    second = persist_quillan_page_observation(tmp_path, second_outcome)
    assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    page = load_submission_manifest(assembled.assembled[0].manifest_path)["pages"][0]
    assert page["page_state"] == "duplicate"
    assert page["selected_evidence_id"] == observation.observation_id
    assert [item["evidence_role"] for item in page["evidence"]] == [
        "selected",
        "candidate",
    ]
    assert page["evidence"][1]["evidence_id"] == second.observation.observation_id


@pytest.mark.parametrize("teacher_role", ["candidate", "replacement"])
def test_new_duplicate_preserves_existing_teacher_role(
    tmp_path: Path, teacher_role: str
) -> None:
    first_outcome, second_outcome = successful_pdf_pages(tmp_path)
    first = persist_quillan_page_observation(tmp_path, first_outcome)
    observation = first.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest_path = assembled.assembled[0].manifest_path
    manifest = load_submission_manifest(manifest_path)
    page = manifest["pages"][0]
    page["page_state"] = "needs_rescan"
    page["selected_evidence_id"] = None
    page["evidence"][0]["evidence_role"] = teacher_role
    page["evidence"][0]["evidence_state"] = "needs_rescan"
    write_submission_manifest(manifest_path, manifest, overwrite=True)

    persist_quillan_page_observation(tmp_path, second_outcome)
    assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    page = load_submission_manifest(manifest_path)["pages"][0]
    assert page["page_state"] == "needs_rescan"
    assert page["selected_evidence_id"] is None
    assert page["evidence"][0]["evidence_role"] == teacher_role
    assert page["evidence"][0]["evidence_state"] == "needs_rescan"


def test_mixed_issuances_are_a_typed_conflict_and_preserve_artifacts(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    first = persisted.observation
    second_timestamp = datetime.fromisoformat(first.intake_timestamp) + timedelta(
        microseconds=1
    )
    second_retained_name = build_retained_source_filename(
        intake_timestamp=second_timestamp,
        original_filename=first.source_filename,
        sha256_hex=first.source_sha256,
    )
    second_scan_id = f"scan_{Path(second_retained_name).stem}"
    second_id = derive_observation_id(
        second_scan_id, first.source_page_number, first.route_id, first.page_id
    )
    second_issuance = "iss_ffffffffffffffffffffffffffffffff"
    work_ref = quillan_work_ref(first.class_id, first.assignment_id)
    second_evidence_path = routed_evidence_path(
        tmp_path,
        work_ref,
        second_issuance,
        first.student_id,
        first.logical_page,
        second_id,
        Path(first.routed_evidence_path).suffix,
    )
    second_evidence_path.parent.mkdir(parents=True)
    second_evidence_path.write_bytes(persisted.evidence_path.read_bytes())
    retained_relative = f"scans/source/{first.intake_date}/{second_retained_name}"
    second_retained_path = tmp_path.joinpath(*Path(retained_relative).parts)
    second_retained_path.write_bytes(
        tmp_path.joinpath(*Path(first.retained_source_path).parts).read_bytes()
    )
    second = replace(
        first,
        observation_id=second_id,
        issuance_id=second_issuance,
        source_scan_id=second_scan_id,
        retained_source_path=retained_relative,
        created_at=second_timestamp.isoformat(),
        intake_timestamp=second_timestamp.isoformat(),
        routed_evidence_path=second_evidence_path.relative_to(tmp_path).as_posix(),
    )
    second_observation_path = response_page_observation_path(
        tmp_path, work_ref, second_id
    )
    second_observation_path.write_bytes(
        canonical_response_page_observation_json(second)
    )

    result = assemble_quillan_submission_manifests(
        tmp_path, first.class_id, first.assignment_id
    )
    assert not result.assembled
    assert len(result.failures) == 1
    assert result.failures[0].category == "mixed_issuances"
    assert set(result.failures[0].issuance_ids) == {
        first.issuance_id,
        second_issuance,
    }
    assert persisted.observation_path.is_file()
    assert persisted.evidence_path.is_file()
    assert second_observation_path.is_file()
    assert second_evidence_path.is_file()


def test_stale_manifest_update_preserves_original_bytes(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest_path = assembled.assembled[0].manifest_path
    original = manifest_path.read_bytes()
    changed = deepcopy(load_submission_manifest(manifest_path))
    changed["updated_at"] = "2026-07-22T00:00:00+00:00"
    changed["module_details"]["assembly_revision"] += 1
    validate_submission_manifest(changed)

    with pytest.raises(SubmissionManifestConcurrencyError):
        persist_submission_manifest(
            manifest_path,
            changed,
            expected_original_bytes=b"stale original bytes",
        )
    assert manifest_path.read_bytes() == original
    assert not tuple(manifest_path.parent.glob("*.tmp"))
    assert not tuple(manifest_path.parent.glob("*.lock"))


def test_existing_different_issuance_is_a_typed_conflict(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest_path = assembled.assembled[0].manifest_path
    other = deepcopy(load_submission_manifest(manifest_path))
    other["module_details"]["response_issuance_id"] = (
        "iss_ffffffffffffffffffffffffffffffff"
    )
    for page in other["pages"]:
        page["page_state"] = "missing"
        page["selected_evidence_id"] = None
        page["evidence"] = []
    write_submission_manifest(manifest_path, other, overwrite=True)

    result = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert not result.assembled
    assert result.failures[0].category == "existing_manifest_issuance_conflict"
    assert persisted.observation_path.is_file()
    assert persisted.evidence_path.is_file()


def test_existing_plain_paper_manifest_blocks_digital_merge(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest_path = assembled.assembled[0].manifest_path
    plain_paper: dict[str, Any] = {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": observation.class_id,
        "assignment_id": observation.assignment_id,
        "student_id": observation.student_id,
        "expected_pages": None,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": "2026-07-21T00:00:00+00:00",
        "updated_at": "2026-07-21T00:00:00+00:00",
        "module_details": {
            "submission_entry_method": "plain_paper_manual",
            "physical_evidence_status": "teacher_has_external_plain_paper",
            "created_by_workflow": "plain_paper_submission",
        },
    }
    write_submission_manifest(manifest_path, plain_paper, overwrite=True)

    result = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert not result.assembled
    assert result.failures[0].category == "existing_plain_paper_submission"
    assert persisted.observation_path.is_file()
    assert persisted.evidence_path.is_file()


@pytest.mark.parametrize(
    "reserved",
    [
        {"evidence_role": "selected"},
        {"evidence_role": "selected", "evidence_state": "active", "extra": True},
        {"evidence_role": "immutable", "evidence_state": "active"},
        {"evidence_role": "selected", "evidence_state": "immutable"},
        {
            "evidence_role": "selected",
            "evidence_state": "active",
            "observation_id": "obs_" + "f" * 32,
        },
    ],
)
def test_reserved_teacher_namespace_is_exact_and_cannot_modify_identity(
    tmp_path: Path, reserved: dict[str, object]
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest = load_submission_manifest(assembled.assembled[0].manifest_path)
    manifest["pages"][0]["evidence"][0]["module_details"][
        "quillan_before_page_exclusion"
    ] = reserved
    with pytest.raises(SubmissionManifestError):
        validate_submission_manifest(manifest)


def test_unknown_pds2_evidence_module_detail_is_rejected(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    manifest = load_submission_manifest(assembled.assembled[0].manifest_path)
    manifest["pages"][0]["evidence"][0]["module_details"]["unknown"] = True
    with pytest.raises(SubmissionManifestError):
        validate_submission_manifest(manifest)


@pytest.mark.parametrize(
    ("corruption", "category"),
    [
        ("malformed", "observation_invalid"),
        ("missing", "observation_missing_evidence"),
        ("hash", "observation_evidence_hash_mismatch"),
    ],
)
def test_discovery_failures_emit_exact_categories(
    tmp_path: Path, corruption: str, category: str
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    if corruption == "malformed":
        persisted.observation_path.write_bytes(b"{")
    elif corruption == "missing":
        persisted.evidence_path.unlink()
    else:
        content = persisted.evidence_path.read_bytes()
        persisted.evidence_path.write_bytes(bytes([content[0] ^ 1]) + content[1:])
    result = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert result.failures[0].category == category


def test_observation_page_absent_from_issuance_emits_unexpected_page(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    original = persisted.observation
    page_id = "pg_" + "f" * 32
    observation_id = derive_observation_id(
        original.source_scan_id,
        original.source_page_number,
        original.route_id,
        page_id,
    )
    work_ref = quillan_work_ref(original.class_id, original.assignment_id)
    evidence_path = routed_evidence_path(
        tmp_path,
        work_ref,
        original.issuance_id,
        original.student_id,
        original.logical_page,
        observation_id,
        persisted.evidence_path.suffix,
    )
    evidence_path.write_bytes(persisted.evidence_path.read_bytes())
    persisted.evidence_path.unlink()
    changed = replace(
        original,
        page_id=page_id,
        observation_id=observation_id,
        routed_evidence_path=evidence_path.relative_to(tmp_path).as_posix(),
    )
    changed_path = response_page_observation_path(tmp_path, work_ref, observation_id)
    changed_path.write_bytes(canonical_response_page_observation_json(changed))
    persisted.observation_path.unlink()
    result = assemble_quillan_submission_manifests(
        tmp_path, original.class_id, original.assignment_id
    )
    assert result.failures[0].category == "unexpected_page"


@pytest.mark.parametrize(
    "category",
    [
        "issuance_not_found",
        "issuance_invalid",
        "issuance_not_issued",
        "source_page_conflict",
        "identity_conflict",
        "route_conflict",
        "manifest_concurrency_conflict",
        "manifest_write_failed",
    ],
)
def test_typed_student_stage_failures_emit_their_public_category(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    category: str,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation

    def raise_error(error: Exception) -> Callable[..., None]:
        def injected(*_args: object, **_kwargs: object) -> None:
            raise error

        return injected

    if category == "issuance_not_found":
        monkeypatch.setattr(
            observation_assembly,
            "load_printable_response_record_set",
            raise_error(PrintableResponseNotFoundError("missing")),
        )
    elif category == "issuance_invalid":
        monkeypatch.setattr(
            observation_assembly,
            "load_printable_response_record_set",
            raise_error(PrintableResponsePersistenceError("invalid")),
        )
    elif category == "issuance_not_issued":
        not_issued = SimpleNamespace(
            issuance=SimpleNamespace(lifecycle=SimpleNamespace(status="prepared"))
        )
        monkeypatch.setattr(
            observation_assembly,
            "load_printable_response_record_set",
            lambda *_args, **_kwargs: not_issued,
        )
    elif category in {"source_page_conflict", "identity_conflict"}:
        error: Exception = (
            QuillanCategorizedAssemblyError(category, "conflict")
            if category == "source_page_conflict"
            else QuillanSubmissionObservationAssemblyError("conflict")
        )
        monkeypatch.setattr(
            observation_assembly,
            "_validate_observations_against_record_set",
            raise_error(error),
        )
    elif category == "route_conflict":
        monkeypatch.setattr(
            observation_assembly,
            "_validate_observation_routes",
            raise_error(QuillanSubmissionObservationAssemblyError("route")),
        )
    elif category == "manifest_concurrency_conflict":
        monkeypatch.setattr(
            observation_assembly,
                "create_quillan_submission_manifest",
            raise_error(SubmissionManifestConcurrencyError("concurrent")),
        )
    else:
        monkeypatch.setattr(
            observation_assembly,
                "create_quillan_submission_manifest",
            raise_error(SubmissionManifestPathError("write")),
        )
    result = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert result.failures[0].category == category


def test_same_source_occurrence_for_two_issuance_pages_is_source_conflict(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path, pages=2)
    )
    first = persisted.observation
    record_set = load_printable_response_record_set(
        tmp_path,
        quillan_work_ref(first.class_id, first.assignment_id),
        first.issuance_id,
    )
    page = record_set.pages[1]
    second_id = derive_observation_id(
        first.source_scan_id, first.source_page_number, first.route_id, page.page_id
    )
    second = replace(
        first,
        observation_id=second_id,
        page_id=page.page_id,
        logical_page=page.logical_page,
        total_pages=page.total_pages,
        page_role=page.page_role,
        routed_evidence_path=first.routed_evidence_path.replace(
            first.observation_id, second_id
        ),
    )
    with pytest.raises(QuillanCategorizedAssemblyError) as caught:
        observation_assembly._validate_observations_against_record_set(
            record_set, (first, second)
        )
    assert caught.value.category == "source_page_conflict"


def test_invalid_existing_manifest_emits_exact_category(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    assembled = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assembled.assembled[0].manifest_path.write_bytes(b"{")
    result = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert result.failures[0].category == "existing_manifest_invalid"


def test_single_assembly_propagates_runtime_and_scan_batch_contains_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    original = RuntimeError("programming failure")
    monkeypatch.setattr(
        observation_assembly,
        "list_quillan_page_observations",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(original),
    )
    with pytest.raises(RuntimeError) as caught:
        assemble_quillan_submission_manifests(
            tmp_path, observation.class_id, observation.assignment_id
        )
    assert caught.value is original

    batch = QuillanObservationPersistenceBatch(
        QuillanScanIntakeSummary((), ("quillan",)), (persisted,), (), 0
    )
    contained = assemble_quillan_scan_observations(tmp_path, batch)
    assert contained.failures[0].category == "unexpected_error"
    assert contained.failures[0].error is original


def test_route_validation_propagates_unexpected_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    original = RuntimeError("programming failure")
    monkeypatch.setattr(
        observation_assembly,
        "load_route_registration",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(original),
    )
    result = assemble_quillan_submission_manifests(
        tmp_path, observation.class_id, observation.assignment_id
    )
    assert not result.assembled
    assert len(result.failures) == 1
    assert result.failures[0].category == "unexpected_error"
    assert result.failures[0].student_id == observation.student_id
    assert result.failures[0].error is original


def test_three_student_unexpected_error_continues_and_preserves_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation_a = persisted.observation
    baseline = assemble_quillan_submission_manifests(
        tmp_path, observation_a.class_id, observation_a.assignment_id
    ).assembled[0]
    observation_b = replace(observation_a, student_id="response_00108")
    observation_c = replace(observation_a, student_id="response_00109")
    observations = (observation_a, observation_b, observation_c)
    manifest_c = baseline.manifest_path.parent.parent / "response_00109" / "submission.json"
    assembled_c = replace(
        baseline,
        student_id=observation_c.student_id,
        manifest_path=manifest_c,
        manifest_relative_path=manifest_c.relative_to(tmp_path).as_posix(),
    )
    original = RuntimeError("programming failure")
    attempted: list[str] = []
    observation_bytes = persisted.observation_path.read_bytes()
    evidence_bytes = persisted.evidence_path.read_bytes()

    def assemble_one(
        _root: Path,
        _class_id: str,
        _assignment_id: str,
        student_id: str,
        _observations: tuple[object, ...],
        *,
        timestamp: object,
    ) -> QuillanSubmissionAssemblyBatch:
        del timestamp
        attempted.append(student_id)
        if student_id == observation_b.student_id:
            raise original
        assembled = baseline if student_id == observation_a.student_id else assembled_c
        return QuillanSubmissionAssemblyBatch((assembled,), ())

    monkeypatch.setattr(
        observation_assembly, "list_quillan_page_observations", lambda *_args: observations
    )
    monkeypatch.setattr(observation_assembly, "_assemble_one_student", assemble_one)
    result = assemble_quillan_submission_manifests(
        tmp_path, observation_a.class_id, observation_a.assignment_id
    )
    assert attempted == [
        observation_a.student_id,
        observation_b.student_id,
        observation_c.student_id,
    ]
    assert [item.student_id for item in result.assembled] == [
        observation_a.student_id,
        observation_c.student_id,
    ]
    assert result.failures[0].student_id == observation_b.student_id
    assert result.failures[0].category == "unexpected_error"
    assert result.failures[0].error is original
    assert baseline in result.assembled
    assert baseline.manifest_path.is_file()
    assert persisted.observation_path.read_bytes() == observation_bytes
    assert persisted.evidence_path.read_bytes() == evidence_bytes


def test_earlier_durable_student_result_survives_later_unexpected_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation_a = persisted.observation
    baseline = assemble_quillan_submission_manifests(
        tmp_path, observation_a.class_id, observation_a.assignment_id
    ).assembled[0]
    durable_bytes = baseline.manifest_path.read_bytes()
    baseline.manifest_path.unlink()
    observation_b = replace(observation_a, student_id="response_00108")
    observation_c = replace(observation_a, student_id="response_00109")
    observations = (observation_a, observation_b, observation_c)
    original = RuntimeError("programming failure")
    attempted: list[str] = []

    def assemble_one(
        _root: Path,
        _class_id: str,
        _assignment_id: str,
        student_id: str,
        _observations: tuple[object, ...],
        *,
        timestamp: object,
    ) -> QuillanSubmissionAssemblyBatch:
        del timestamp
        attempted.append(student_id)
        if student_id == observation_a.student_id:
            baseline.manifest_path.write_bytes(durable_bytes)
            return QuillanSubmissionAssemblyBatch((baseline,), ())
        if student_id == observation_b.student_id:
            raise original
        manifest_c = baseline.manifest_path.parent.parent / student_id / "submission.json"
        assembled_c = replace(
            baseline,
            student_id=student_id,
            manifest_path=manifest_c,
            manifest_relative_path=manifest_c.relative_to(tmp_path).as_posix(),
        )
        return QuillanSubmissionAssemblyBatch((assembled_c,), ())

    monkeypatch.setattr(
        observation_assembly, "list_quillan_page_observations", lambda *_args: observations
    )
    monkeypatch.setattr(observation_assembly, "_assemble_one_student", assemble_one)
    result = assemble_quillan_submission_manifests(
        tmp_path, observation_a.class_id, observation_a.assignment_id
    )
    assert attempted[-1] == observation_c.student_id
    assert result.assembled[0] == baseline
    assert result.failures[0].error is original
    assert baseline.manifest_path.read_bytes() == durable_bytes


def test_declared_category_vocabulary_is_closed() -> None:
    assert ASSEMBLY_FAILURE_CATEGORIES == {
        "observation_invalid",
        "observation_missing_evidence",
        "observation_evidence_hash_mismatch",
        "issuance_not_found",
        "issuance_invalid",
        "issuance_not_issued",
        "unexpected_page",
        "identity_conflict",
        "route_conflict",
        "source_page_conflict",
        "mixed_issuances",
        "existing_manifest_issuance_conflict",
        "existing_plain_paper_submission",
        "existing_manifest_invalid",
        "manifest_concurrency_conflict",
        "manifest_write_failed",
        "unexpected_error",
    }

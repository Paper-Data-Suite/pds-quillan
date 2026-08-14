from __future__ import annotations

from pathlib import Path

import pytest
from pds_core.registry_services import AcademicWorkRegistrationServiceResult

import quillan.academic_result_publication as publication_module
from quillan.academic_result_manifest_generation import (
    AcademicResultManifestGenerationResult,
    generate_academic_result_manifest,
)
from quillan.academic_result_publication import (
    QUILLAN_PUBLICATION_CAPABILITIES,
    QuillanAcademicResultPublicationConflictError,
    load_quillan_publication_series_status,
    publish_quillan_academic_results,
    republish_quillan_academic_results_after_withdrawal,
    supersede_quillan_academic_results,
    withdraw_quillan_academic_result_publication,
)
from quillan.academic_work_registration import (
    register_quillan_academic_work,
    update_quillan_academic_work_registration,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, _write_assignment
from tests.test_academic_result_manifest_generation import _prepare_plain_pair


def _registered_manifest(
    tmp_path: Path,
) -> tuple[AcademicWorkRegistrationServiceResult, AcademicResultManifestGenerationResult]:
    _prepare_plain_pair(tmp_path)
    registration = register_quillan_academic_work(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="summative",
        lifecycle="active",
    )
    manifest = generate_academic_result_manifest(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    return registration, manifest


def _new_revision(tmp_path: Path) -> AcademicResultManifestGenerationResult:
    assignment = _write_assignment(tmp_path)
    assignment.write_bytes(assignment.read_bytes() + b"\n")
    return generate_academic_result_manifest(tmp_path, CLASS_ID, ASSIGNMENT_ID)


def test_initial_publication_exact_contract_and_catalog(tmp_path: Path) -> None:
    registration, manifest = _registered_manifest(tmp_path)
    result = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=manifest.revision
    )
    publication = result.publication
    assert result.disposition == "created"
    assert publication.work.module_id == "quillan"
    assert publication.publication_kind == "academic_result_set"
    assert publication.record_set_id == "academic_results"
    assert publication.source_record is None
    assert publication.capabilities == QUILLAN_PUBLICATION_CAPABILITIES
    assert publication.capabilities == ("standards_ratings",)
    assert publication.manifest_contract_version == "quillan_academic_result_manifest_v1"
    assert publication.manifest_path == manifest.relative_path
    assert publication.manifest_digest == manifest.sha256
    assert publication.manifest_digest_algorithm == "sha256"
    assert publication.academic_work_registration_revision == 1
    assert publication.supersedes_publication_id is None
    assert result.compatibility.compatible is True
    assert result.compatibility.codes == ()
    assert result.catalog.publication.is_series_head is True
    assert result.catalog.publication.is_current_selectable is True
    assert registration.registration.registration_revision == 1


def test_first_publication_may_start_above_revision_one(tmp_path: Path) -> None:
    _registered_manifest(tmp_path)
    second = _new_revision(tmp_path)
    result = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=second.revision
    )
    assert second.revision == 2
    assert result.publication.record_set_revision == 2
    assert result.publication.supersedes_publication_id is None
    state = load_quillan_publication_series_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert state.producer_revisions == (1, 2)
    assert tuple(item.record_set_revision for item in state.publications) == (2,)


def test_exact_publish_replay_preserves_historical_registration(tmp_path: Path) -> None:
    registration, manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=manifest.revision
    )
    update_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="formative",
        lifecycle="active",
        expected_current_revision=registration.registration.registration_revision,
    )
    replay = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=manifest.revision
    )
    assert replay.disposition == "existing"
    assert replay.publication.publication_id == first.publication.publication_id
    assert replay.publication.published_at == first.publication.published_at
    assert replay.publication.academic_work_registration_revision == 1
    assert replay.registration.registration_revision == 1


def test_historical_producer_revision_is_not_publishable(tmp_path: Path) -> None:
    _, first = _registered_manifest(tmp_path)
    second = _new_revision(tmp_path)
    assert second.revision == 2
    with pytest.raises(QuillanAcademicResultPublicationConflictError):
        publish_quillan_academic_results(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=first.revision
        )


def test_supersession_binds_new_registration_and_replay_preserves_it(
    tmp_path: Path,
) -> None:
    registration, first_manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=first_manifest.revision
    )
    updated = update_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="formative",
        lifecycle="active",
        expected_current_revision=registration.registration.registration_revision,
    )
    second_manifest = _new_revision(tmp_path)
    second = supersede_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=second_manifest.revision,
        expected_current_publication_id=first.publication.publication_id,
    )
    assert second.disposition == "created"
    assert second.publication.supersedes_publication_id == first.publication.publication_id
    assert second.publication.academic_work_registration_revision == 2
    assert updated.registration.registration_revision == 2

    update_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="diagnostic",
        lifecycle="active",
        expected_current_revision=2,
    )
    replay = supersede_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=second_manifest.revision,
        expected_current_publication_id=first.publication.publication_id,
    )
    assert replay.disposition == "existing"
    assert replay.publication.publication_id == second.publication.publication_id
    assert replay.publication.academic_work_registration_revision == 2
    assert replay.registration.registration_revision == 2


def test_stale_expected_head_cannot_branch_series(tmp_path: Path) -> None:
    _, first_manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=first_manifest.revision
    )
    second_manifest = _new_revision(tmp_path)
    second = supersede_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=second_manifest.revision,
        expected_current_publication_id=first.publication.publication_id,
    )
    assignment = _write_assignment(tmp_path)
    assignment.write_bytes(assignment.read_bytes() + b"\n\n")
    third = generate_academic_result_manifest(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    with pytest.raises(QuillanAcademicResultPublicationConflictError):
        supersede_quillan_academic_results(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            manifest_revision=third.revision,
            expected_current_publication_id=first.publication.publication_id,
        )
    state = load_quillan_publication_series_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert state.core_head == second.publication
    assert len(state.publications) == 2


def test_head_withdrawal_preserves_head_and_removes_selectable(tmp_path: Path) -> None:
    _, manifest = _registered_manifest(tmp_path)
    published = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=manifest.revision
    )
    withdrawn = withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=published.publication.publication_id,
        reason="temporary publication hold",
    )
    assert withdrawn.disposition == "created"
    assert withdrawn.manifest_verification == "verified"
    assert withdrawn.catalog.publication.is_series_head is True
    assert withdrawn.catalog.publication.is_withdrawn is True
    assert withdrawn.catalog.publication.is_current_selectable is False
    state = load_quillan_publication_series_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert state.core_head == published.publication
    assert state.current_selectable_publication is None


def test_withdrawal_replay_same_reason_and_conflict_different_reason(
    tmp_path: Path,
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    published = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=manifest.revision
    )
    first = withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=published.publication.publication_id,
        reason="privacy review",
    )
    replay = withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=published.publication.publication_id,
        reason="privacy review",
    )
    assert replay.disposition == "existing"
    assert replay.withdrawal == first.withdrawal
    with pytest.raises(QuillanAcademicResultPublicationConflictError):
        withdraw_quillan_academic_result_publication(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            publication_id=published.publication.publication_id,
            reason="different reason",
        )


def test_missing_manifest_does_not_block_withdrawal(tmp_path: Path) -> None:
    _, manifest = _registered_manifest(tmp_path)
    published = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=manifest.revision
    )
    manifest.path.unlink()
    withdrawn = withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=published.publication.publication_id,
        reason="bound bytes unavailable",
    )
    assert withdrawn.manifest_verification == "missing"
    assert withdrawn.catalog.publication.is_withdrawn is True


def test_ordinary_supersession_rejects_withdrawn_head(tmp_path: Path) -> None:
    _, first_manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=first_manifest.revision
    )
    withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=first.publication.publication_id,
        reason="hold",
    )
    second = _new_revision(tmp_path)
    with pytest.raises(
        QuillanAcademicResultPublicationConflictError,
        match="republish-after-withdrawal",
    ):
        supersede_quillan_academic_results(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            manifest_revision=second.revision,
            expected_current_publication_id=first.publication.publication_id,
        )


def test_explicit_republication_creates_greater_successor_and_replays(
    tmp_path: Path,
) -> None:
    _, first_manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, manifest_revision=first_manifest.revision
    )
    withdrawn = withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=first.publication.publication_id,
        reason="temporary hold",
    )
    created = republish_quillan_academic_results_after_withdrawal(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        expected_withdrawn_head_publication_id=first.publication.publication_id,
    )
    assert created.operation == "republish_after_withdrawal"
    assert created.disposition == "created"
    assert created.manifest_generation is not None
    assert created.manifest_generation.reason == "republication_after_withdrawal"
    assert created.publication.record_set_revision == first_manifest.revision + 1
    assert created.publication.supersedes_publication_id == first.publication.publication_id
    assert created.catalog.publication.is_current_selectable is True

    replay = republish_quillan_academic_results_after_withdrawal(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        expected_withdrawn_head_publication_id=first.publication.publication_id,
    )
    assert replay.disposition == "existing"
    assert replay.publication.publication_id == created.publication.publication_id
    assert replay.publication.published_at == created.publication.published_at
    first_after, withdrawal_after = publication_module.load_quillan_publication(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, first.publication.publication_id
    )
    assert first_after == first.publication
    assert withdrawal_after == withdrawn.withdrawal


def test_read_only_status_does_not_create_catalog(tmp_path: Path) -> None:
    _registered_manifest(tmp_path)
    catalog = tmp_path / "registry" / "catalog.sqlite"
    assert not catalog.exists()
    state = load_quillan_publication_series_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert state.publications == ()
    assert state.catalog_available is False
    assert not catalog.exists()


def test_publication_module_has_no_direct_registry_or_sqlite_writer() -> None:
    source = Path(publication_module.__file__).read_text(encoding="utf-8")
    for token in (
        "write_publication_record",
        "write_publication_withdrawal",
        "import sqlite3",
        "sqlite3.",
        "_new_publication_id",
        "uuid.",
    ):
        assert token not in source

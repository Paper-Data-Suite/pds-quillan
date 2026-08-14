"""Adversarial qualification for Quillan's Core publication lifecycle."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import pytest
from pds_core.academic_catalog import (
    AcademicCatalogBuildError,
    CatalogPublication,
    query_publication_catalog as core_query_publication_catalog,
    rebuild_academic_catalog as core_rebuild_academic_catalog,
)
from pds_core.publication_storage import PublicationManifestError
from pds_core.registry_services import (
    PublicationManifestRequest,
    RegistryServiceConflictError,
    RegistryServicePartialState,
    RegistryServicePartialSuccessError,
    RegistryServiceWriteError,
    supersede_manifest_revision as core_supersede_manifest_revision,
)

import quillan.academic_result_publication as publication_module
import quillan.pds_publication as profile_module
from quillan.academic_result_manifest_generation import (
    AcademicResultManifestGenerationResult,
    list_academic_result_manifest_revisions,
)
from quillan.academic_result_publication import (
    AcademicResultPublicationResult,
    QuillanAcademicResultPublicationConflictError,
    QuillanAcademicResultPublicationPartialSuccessError,
    load_quillan_publication_series_status,
    publish_quillan_academic_results,
    republish_quillan_academic_results_after_withdrawal,
    supersede_quillan_academic_results,
    withdraw_quillan_academic_result_publication,
)
from quillan.academic_work_registration import (
    update_quillan_academic_work_registration,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_academic_result_publication import (
    _new_revision,
    _registered_manifest,
)


def _publish_initial(
    tmp_path: Path,
) -> tuple[AcademicResultManifestGenerationResult, AcademicResultPublicationResult]:
    _, manifest = _registered_manifest(tmp_path)
    published = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    return manifest, published


def test_historical_withdrawal_does_not_disturb_later_head(tmp_path: Path) -> None:
    first_manifest, first = _publish_initial(tmp_path)
    second_manifest = _new_revision(tmp_path)
    second = supersede_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=second_manifest.revision,
        expected_current_publication_id=first.publication.publication_id,
    )

    withdrawn = withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=first.publication.publication_id,
        reason="historical publication should no longer be selectable",
    )

    assert first_manifest.revision == 1
    assert withdrawn.catalog.publication.is_series_head is False
    assert withdrawn.catalog.publication.is_withdrawn is True
    assert withdrawn.catalog.publication.is_current_selectable is False

    state = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert state.core_head == second.publication
    assert state.current_selectable_publication == second.publication
    assert state.core_head_withdrawal is None
    assert tuple(item.publication_id for item in state.withdrawals) == (
        first.publication.publication_id,
    )


def test_digest_mismatch_does_not_block_withdrawal(tmp_path: Path) -> None:
    manifest, published = _publish_initial(tmp_path)
    manifest.path.write_bytes(b"tampered immutable manifest\n")

    withdrawn = withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=published.publication.publication_id,
        reason="withdraw despite damaged producer evidence",
    )

    assert withdrawn.manifest_verification == "digest_mismatch_or_unsafe"
    assert withdrawn.publication == published.publication
    assert withdrawn.catalog.publication.is_withdrawn is True


def test_unreadable_manifest_diagnostic_does_not_block_withdrawal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, published = _publish_initial(tmp_path)

    def unreadable(*_args: object, **_kwargs: object) -> NoReturn:
        raise PublicationManifestError("simulated unreadable manifest")

    monkeypatch.setattr(publication_module, "verify_publication_manifest", unreadable)

    withdrawn = withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=published.publication.publication_id,
        reason="withdraw even when diagnostic verification cannot read bytes",
    )

    assert withdrawn.manifest_verification == "unreadable"
    assert withdrawn.catalog.publication.is_withdrawn is True


def test_existing_publication_replay_survives_new_current_cancellation(
    tmp_path: Path,
) -> None:
    registration, manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    update_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="summative",
        lifecycle="cancelled",
        expected_current_revision=registration.registration.registration_revision,
    )

    replay = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )

    assert replay.disposition == "existing"
    assert replay.publication.publication_id == first.publication.publication_id
    assert replay.registration.registration_revision == 1
    assert replay.registration.lifecycle == "active"


def test_cancelled_current_registration_blocks_new_supersession(tmp_path: Path) -> None:
    registration, manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    update_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="summative",
        lifecycle="cancelled",
        expected_current_revision=registration.registration.registration_revision,
    )
    second = _new_revision(tmp_path)

    with pytest.raises(
        QuillanAcademicResultPublicationConflictError,
        match="cancelled",
    ):
        supersede_quillan_academic_results(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            manifest_revision=second.revision,
            expected_current_publication_id=first.publication.publication_id,
        )


def test_withdrawal_does_not_require_current_registration_to_remain_active(
    tmp_path: Path,
) -> None:
    registration, manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    update_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="summative",
        lifecycle="cancelled",
        expected_current_revision=registration.registration.registration_revision,
    )

    withdrawn = withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=first.publication.publication_id,
        reason="withdraw historical state after registration cancellation",
    )

    assert withdrawn.disposition == "created"
    assert withdrawn.publication.academic_work_registration_revision == 1


def test_core_partial_success_maps_to_local_publish_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )

    state = RegistryServicePartialState(
        operation="publish_manifest_revision",
        registration=None,
        publication=first.publication,
        withdrawal=None,
        canonical_path=None,
        current_selected=None,
        message="simulated Core publication partial success",
    )

    def partial(
        _workspace_root: object,
        _request: PublicationManifestRequest,
    ) -> NoReturn:
        raise RegistryServicePartialSuccessError(state.message, state)

    monkeypatch.setattr(publication_module, "publish_manifest_revision", partial)

    with pytest.raises(
        QuillanAcademicResultPublicationPartialSuccessError,
    ) as caught:
        publish_quillan_academic_results(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            manifest_revision=manifest.revision,
        )

    local = caught.value.state
    assert local.operation == "publish"
    assert local.canonical_state == "uncertain"
    assert local.publication == first.publication
    assert local.manifest is not None
    assert local.manifest.revision == manifest.revision
    assert local.catalog_rebuild_attempted is False


def test_catalog_build_failure_after_durable_publish_replays_one_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    real_rebuild = core_rebuild_academic_catalog

    def fail_rebuild(*_args: object, **_kwargs: object) -> NoReturn:
        raise AcademicCatalogBuildError("simulated catalog build failure")

    monkeypatch.setattr(publication_module, "rebuild_academic_catalog", fail_rebuild)

    with pytest.raises(
        QuillanAcademicResultPublicationPartialSuccessError,
    ) as caught:
        publish_quillan_academic_results(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            manifest_revision=manifest.revision,
        )

    partial = caught.value.state
    assert partial.operation == "publish"
    assert partial.canonical_state == "confirmed"
    assert partial.publication is not None
    durable_publication_id = partial.publication.publication_id
    assert partial.catalog_rebuild_attempted is True
    assert partial.catalog_replacement_completed is False
    assert partial.catalog_verification_completed is False

    monkeypatch.setattr(publication_module, "rebuild_academic_catalog", real_rebuild)

    replay = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    assert replay.disposition == "existing"
    assert replay.publication.publication_id == durable_publication_id

    state = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert len(state.publications) == 1


def test_catalog_row_verification_failure_records_completed_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    real_query = core_query_publication_catalog

    def no_rows(*_args: object, **_kwargs: object) -> tuple[CatalogPublication, ...]:
        return ()

    monkeypatch.setattr(publication_module, "query_publication_catalog", no_rows)

    with pytest.raises(
        QuillanAcademicResultPublicationPartialSuccessError,
    ) as caught:
        publish_quillan_academic_results(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            manifest_revision=manifest.revision,
        )

    partial = caught.value.state
    assert partial.operation == "publish"
    assert partial.canonical_state == "confirmed"
    assert partial.publication is not None
    durable_publication_id = partial.publication.publication_id
    assert partial.catalog_rebuild_attempted is True
    assert partial.catalog_replacement_completed is True
    assert partial.catalog_build is not None
    assert partial.catalog_verification_completed is False

    monkeypatch.setattr(publication_module, "query_publication_catalog", real_query)

    replay = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    assert replay.disposition == "existing"
    assert replay.publication.publication_id == durable_publication_id


def test_republication_reuses_durable_unpublished_successor_after_core_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, first = _publish_initial(tmp_path)
    withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=first.publication.publication_id,
        reason="temporary hold before explicit republication",
    )
    real_supersede = core_supersede_manifest_revision

    def fail_supersede(
        _workspace_root: object,
        _request: PublicationManifestRequest,
        *,
        expected_current_publication_id: str,
    ) -> NoReturn:
        assert expected_current_publication_id == first.publication.publication_id
        raise RegistryServiceWriteError("simulated Core publication write failure")

    monkeypatch.setattr(
        publication_module,
        "supersede_manifest_revision",
        fail_supersede,
    )

    with pytest.raises(
        QuillanAcademicResultPublicationPartialSuccessError,
    ) as caught:
        republish_quillan_academic_results_after_withdrawal(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            expected_withdrawn_head_publication_id=first.publication.publication_id,
        )

    partial = caught.value.state
    assert partial.operation == "republish_after_withdrawal"
    assert partial.publication is None
    assert partial.manifest is not None
    assert partial.manifest.revision == manifest.revision + 1
    assert tuple(
        item.revision
        for item in list_academic_result_manifest_revisions(
            tmp_path,
            first.publication.work,
        )
    ) == (1, 2)

    monkeypatch.setattr(
        publication_module,
        "supersede_manifest_revision",
        real_supersede,
    )

    retry = republish_quillan_academic_results_after_withdrawal(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        expected_withdrawn_head_publication_id=first.publication.publication_id,
    )
    assert retry.disposition == "created"
    assert retry.publication.record_set_revision == 2
    assert retry.manifest_generation is None
    assert tuple(
        item.revision
        for item in list_academic_result_manifest_revisions(
            tmp_path,
            first.publication.work,
        )
    ) == (1, 2)


def test_core_supersession_conflict_after_precheck_does_not_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, first = _publish_initial(tmp_path)
    second = _new_revision(tmp_path)

    def concurrent_conflict(
        _workspace_root: object,
        _request: PublicationManifestRequest,
        *,
        expected_current_publication_id: str,
    ) -> NoReturn:
        assert expected_current_publication_id == first.publication.publication_id
        raise RegistryServiceConflictError(
            "simulated canonical head movement after producer precheck"
        )

    monkeypatch.setattr(
        publication_module,
        "supersede_manifest_revision",
        concurrent_conflict,
    )

    with pytest.raises(QuillanAcademicResultPublicationConflictError):
        supersede_quillan_academic_results(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            manifest_revision=second.revision,
            expected_current_publication_id=first.publication.publication_id,
        )

    state = load_quillan_publication_series_status(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assert state.core_head == first.publication
    assert len(state.publications) == 1
    assert state.producer_head_revision == 2


def test_publication_boundary_remains_explicit_and_consumer_neutral() -> None:
    publication_source = Path(publication_module.__file__).read_text(encoding="utf-8")
    profile_source = Path(profile_module.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "pds_meridian",
        "pds-meridian",
        "vitrine.",
        "pds_vitrine",
        "sqlite3",
        "write_publication_record",
        "write_publication_withdrawal",
    ):
        assert forbidden not in publication_source

    for lifecycle_callback in (
        "publish_quillan_academic_results",
        "supersede_quillan_academic_results",
        "republish_quillan_academic_results_after_withdrawal",
        "withdraw_quillan_academic_result_publication",
        "rebuild_academic_catalog",
    ):
        assert lifecycle_callback not in profile_source

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import quillan.share_results as share_module
from quillan.academic_result_manifest_generation import (
    QuillanManifestGenerationValidationError,
    generate_academic_result_manifest,
)
from quillan.academic_result_publication import (
    publish_quillan_academic_results,
    withdraw_quillan_academic_result_publication,
)
from quillan.academic_work_registration import (
    register_quillan_academic_work,
    update_quillan_academic_work_registration,
)
from quillan.share_results import (
    ShareResultsIntegrityError,
    build_share_results_status,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, _write_assignment
from tests.test_academic_result_manifest_generation import _prepare_plain_pair
from tests.test_academic_result_publication import _registered_manifest


def _tree_snapshot(root: Path) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def _change_assignment_bytes(root: Path) -> None:
    path = _write_assignment(root)
    path.write_bytes(path.read_bytes() + b"\n")


def test_unregistered_status_requires_registration(tmp_path: Path) -> None:
    _prepare_plain_pair(tmp_path)

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.registration_revision is None
    assert status.native_result_state_valid is True
    assert status.represented_native_result_count == 1
    assert status.native_state_matches_producer_head is None
    assert status.producer_head_revision is None
    assert status.publication_plan == "manifest_required"
    assert status.next_step == "register_academic_work"
    assert status.review_context is None
    assert "review_completion_unavailable" in status.warnings


def test_registered_without_manifest_routes_to_generation(tmp_path: Path) -> None:
    _prepare_plain_pair(tmp_path)
    registration = register_quillan_academic_work(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="summative",
        lifecycle="active",
    )

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.registration_revision == (
        registration.registration.registration_revision
    )
    assert status.academic_intent == "summative"
    assert status.lifecycle == "active"
    assert status.publication_plan == "manifest_required"
    assert status.next_step == "generate_manifest"


def test_generated_head_plans_initial_publication(tmp_path: Path) -> None:
    _, manifest = _registered_manifest(tmp_path)

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.native_state_matches_producer_head is True
    assert status.producer_head_revision == manifest.revision
    assert status.producer_head_sha256 == manifest.sha256
    assert status.core_head_publication_id is None
    assert status.publication_plan == "initial_publication"
    assert status.next_step == "publish_initial"


def test_current_publication_is_no_write_already_shared(tmp_path: Path) -> None:
    _, manifest = _registered_manifest(tmp_path)
    publication = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.native_state_matches_producer_head is True
    assert status.publication_plan == "already_current"
    assert status.next_step == "already_shared_current"
    assert status.core_head_publication_id == publication.publication.publication_id
    assert (
        status.current_selectable_publication_id
        == publication.publication.publication_id
    )


def test_native_change_requires_generation_before_more_publication(
    tmp_path: Path,
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    _change_assignment_bytes(tmp_path)

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.publication_plan == "already_current"
    assert status.native_state_matches_producer_head is False
    assert status.next_step == "generate_manifest"


def test_new_generated_head_plans_exact_supersession(tmp_path: Path) -> None:
    _, first_manifest = _registered_manifest(tmp_path)
    first = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=first_manifest.revision,
    )
    _change_assignment_bytes(tmp_path)
    second_manifest = generate_academic_result_manifest(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert second_manifest.revision > first_manifest.revision
    assert status.native_state_matches_producer_head is True
    assert status.publication_plan == "supersede_current"
    assert status.next_step == "supersede_current"
    assert status.core_head_publication_id == first.publication.publication_id


def test_withdrawn_head_routes_to_advanced_republication(tmp_path: Path) -> None:
    _, manifest = _registered_manifest(tmp_path)
    published = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    withdraw_quillan_academic_result_publication(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        publication_id=published.publication.publication_id,
        reason="synthetic hold",
    )

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.core_head_withdrawn is True
    assert status.current_selectable_publication_id is None
    assert status.publication_plan == "advanced_republication_required"
    assert status.next_step == "advanced_republication_required"


def test_cancelled_current_registration_does_not_retroactively_unshare(
    tmp_path: Path,
) -> None:
    registration, manifest = _registered_manifest(tmp_path)
    published = publish_quillan_academic_results(
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
        expected_current_revision=(
            registration.registration.registration_revision
        ),
    )

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.lifecycle == "cancelled"
    assert "registration_cancelled" in status.warnings
    assert status.native_state_matches_producer_head is True
    assert status.publication_plan == "already_current"
    assert status.next_step == "already_shared_current"
    assert (
        status.current_selectable_publication_id
        == published.publication.publication_id
    )


def test_cancelled_registration_blocks_new_publication_progress(
    tmp_path: Path,
) -> None:
    registration, first = _registered_manifest(tmp_path)
    publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=first.revision,
    )
    update_quillan_academic_work_registration(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="summative",
        lifecycle="cancelled",
        expected_current_revision=(
            registration.registration.registration_revision
        ),
    )
    _change_assignment_bytes(tmp_path)
    generate_academic_result_manifest(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.publication_plan == "supersede_current"
    assert status.native_state_matches_producer_head is True
    assert status.next_step == "update_cancelled_registration"


def test_stale_registration_title_is_visible_but_not_silently_changed(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    registration = register_quillan_academic_work(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        academic_intent="formative",
        lifecycle="active",
    )
    assignment = _write_assignment(tmp_path)
    data = json.loads(assignment.read_text(encoding="utf-8"))
    data["title"] = "Revised Synthetic Title"
    assignment.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.registration_revision == (
        registration.registration.registration_revision
    )
    assert status.registration_title != status.assignment_title
    assert status.registration_title_stale is True
    assert "registration_title_stale" in status.warnings


def test_manifest_context_failure_is_bounded_and_does_not_leak_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_plain_pair(tmp_path)
    secret = "SECRET-STUDENT-CONTENT"

    def fail(*_args: object, **_kwargs: object) -> object:
        raise QuillanManifestGenerationValidationError(secret)

    monkeypatch.setattr(
        share_module,
        "load_academic_result_manifest_generation_context",
        fail,
    )

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.native_result_state_valid is False
    assert status.represented_native_result_count is None
    assert "native_result_state_unavailable" in status.warnings
    assert secret not in repr(status)


def test_optional_review_context_uses_only_aggregate_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_plain_pair(tmp_path)
    fake = SimpleNamespace(
        roster_count=24,
        complete_count=8,
        needs_work_count=16,
        attention_count=1,
        unrostered_student_ids=("synthetic_unrostered",),
        warnings=("bounded_warning",),
    )
    monkeypatch.setattr(
        share_module,
        "build_class_review_completion_view",
        lambda *_args, **_kwargs: fake,
    )

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.review_context is not None
    assert status.review_context.roster_count == 24
    assert status.review_context.complete_count == 8
    assert status.review_context.needs_work_count == 16
    assert status.review_context.attention_count == 1
    assert status.review_context.unrostered_diagnostic_count == 1
    assert status.review_context.warning_count == 1
    assert "synthetic_unrostered" not in repr(status)


def test_status_read_does_not_create_catalog_or_change_workspace(
    tmp_path: Path,
) -> None:
    _registered_manifest(tmp_path)
    catalog = tmp_path / "registry" / "catalog.sqlite"
    assert not catalog.exists()
    before = _tree_snapshot(tmp_path)

    status = build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert status.catalog_available is False
    assert "publication_catalog_unavailable" in status.warnings
    assert _tree_snapshot(tmp_path) == before
    assert not catalog.exists()


def test_invalid_current_registration_contract_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_plain_pair(tmp_path)
    fake = SimpleNamespace(
        registration_revision=1,
        title="Synthetic",
        academic_intent="summative",
        lifecycle="active",
        work=SimpleNamespace(module_id="other"),
        producer_contract_version="wrong",
        work_kind="assignment",
        source_records=(),
    )
    monkeypatch.setattr(
        share_module,
        "load_current_quillan_academic_work_registration",
        lambda *_args, **_kwargs: fake,
    )

    with pytest.raises(ShareResultsIntegrityError):
        build_share_results_status(tmp_path, CLASS_ID, ASSIGNMENT_ID)

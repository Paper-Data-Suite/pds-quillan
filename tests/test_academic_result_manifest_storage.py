from __future__ import annotations

import hashlib
import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pds_core.routing_models import ModuleWorkRef

import quillan.academic_result_manifest_generation as generation
from quillan.academic_result_manifest_generation import (
    QuillanManifestGenerationConflictError,
    QuillanManifestGenerationIntegrityError,
    QuillanManifestGenerationNotFoundError,
    QuillanManifestGenerationPartialSuccessError,
    generate_academic_result_manifest,
    list_academic_result_manifest_revisions,
    load_academic_result_manifest_revision,
)
from quillan.work_paths import (
    academic_result_manifest_revision_path,
    academic_result_manifests_dir,
    quillan_work_ref,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, _write_assignment
from tests.test_academic_result_manifest_generation import (
    _prepare_plain_pair,
    _write_standards,
)

UTC_1 = datetime(2026, 8, 12, 20, 0, tzinfo=timezone.utc)
UTC_2 = datetime(2026, 8, 12, 21, 0, tzinfo=timezone.utc)
UTC_3 = datetime(2026, 8, 12, 22, 0, tzinfo=timezone.utc)


def test_initial_creation_and_exact_replay_preserve_exact_bytes(tmp_path: Path) -> None:
    _prepare_plain_pair(tmp_path)

    first = generate_academic_result_manifest(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        clock=lambda: UTC_1,
    )
    original = first.path.read_bytes()
    original_mtime = first.path.stat().st_mtime_ns

    def replay_clock_must_not_run() -> datetime:
        raise AssertionError("exact replay must not call the clock")

    replay = generate_academic_result_manifest(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        clock=replay_clock_must_not_run,
    )

    assert first.disposition == "create_initial"
    assert first.reason == "initial_publication"
    assert first.revision == 1
    assert first.sha256 == hashlib.sha256(original).hexdigest()
    assert replay.disposition == "reuse_existing"
    assert replay.reason == "exact_replay"
    assert replay.revision == 1
    assert replay.content == original
    assert replay.sha256 == first.sha256
    assert replay.manifest.generated_at == first.manifest.generated_at
    assert replay.path.read_bytes() == original
    assert replay.path.stat().st_mtime_ns == original_mtime
    assert not (first.path.parent / ".write.lock").exists()


def test_formatting_only_assignment_change_creates_native_source_successor(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    first = generate_academic_result_manifest(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_1
    )
    assignment = _write_assignment(tmp_path)
    original_semantics = assignment.read_bytes()
    assignment.write_bytes(original_semantics + b"\n")

    second = generate_academic_result_manifest(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_2
    )

    assert first.revision == 1
    assert second.disposition == "create_successor"
    assert second.reason == "native_source_changed"
    assert second.revision == 2
    assert second.manifest.source_snapshot.sha256 != first.manifest.source_snapshot.sha256
    assert first.path.read_bytes() == first.content


def test_historical_reversion_allocates_new_greater_revision(tmp_path: Path) -> None:
    _prepare_plain_pair(tmp_path)
    assignment = _write_assignment(tmp_path)
    original = assignment.read_bytes()
    first = generate_academic_result_manifest(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_1
    )
    assignment.write_bytes(original + b"\n")
    second = generate_academic_result_manifest(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_2
    )
    assignment.write_bytes(original)

    third = generate_academic_result_manifest(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_3
    )

    assert (first.revision, second.revision, third.revision) == (1, 2, 3)
    assert third.disposition == "create_successor"
    assert third.reason == "historical_reversion"
    assert third.content != first.content
    assert third.manifest.generated_at == UTC_3


def test_history_loader_rejects_unexpected_and_noncanonical_entries(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    created = generate_academic_result_manifest(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_1
    )
    unexpected = created.path.parent / "latest.json"
    unexpected.write_text("{}\n", encoding="utf-8")

    with pytest.raises(
        QuillanManifestGenerationIntegrityError, match="unexpected or noncanonical"
    ):
        list_academic_result_manifest_revisions(tmp_path, work)

    unexpected.unlink()
    noncanonical = created.path.parent / "01.json"
    noncanonical.write_bytes(created.content)
    with pytest.raises(
        QuillanManifestGenerationIntegrityError, match="unexpected or noncanonical"
    ):
        list_academic_result_manifest_revisions(tmp_path, work)


def test_history_loader_rejects_semantically_valid_noncanonical_bytes(
    tmp_path: Path,
) -> None:
    _prepare_plain_pair(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    created = generate_academic_result_manifest(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_1
    )
    created.path.write_bytes(created.content.replace(b"  ", b"    ", 1))

    with pytest.raises(QuillanManifestGenerationIntegrityError):
        list_academic_result_manifest_revisions(tmp_path, work)


def test_read_only_list_does_not_create_manifest_storage(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_standards(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    directory = academic_result_manifests_dir(tmp_path, work)

    assert list_academic_result_manifest_revisions(tmp_path, work) == ()
    assert not directory.exists()
    with pytest.raises(QuillanManifestGenerationNotFoundError):
        load_academic_result_manifest_revision(tmp_path, work, 1)
    assert not directory.exists()


def test_preexisting_generation_lock_blocks_generation(tmp_path: Path) -> None:
    _prepare_plain_pair(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    directory = academic_result_manifests_dir(tmp_path, work)
    directory.mkdir(parents=True)
    lock = directory / ".write.lock"
    lock.write_bytes(b"someone-else")

    with pytest.raises(QuillanManifestGenerationConflictError, match="write.lock"):
        generate_academic_result_manifest(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_1
        )

    assert lock.read_bytes() == b"someone-else"
    assert not academic_result_manifest_revision_path(tmp_path, work, 1).exists()


def test_failure_before_durable_creation_consumes_no_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_plain_pair(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)

    def fail_before_write(
        context: generation.AcademicResultManifestGenerationContext,
    ) -> None:
        raise QuillanManifestGenerationConflictError("synthetic prewrite conflict")

    monkeypatch.setattr(generation, "_run_prewrite_verification_hook", fail_before_write)
    with pytest.raises(QuillanManifestGenerationConflictError):
        generate_academic_result_manifest(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_1
        )

    assert not academic_result_manifest_revision_path(tmp_path, work, 1).exists()
    assert not (academic_result_manifests_dir(tmp_path, work) / ".write.lock").exists()


def test_concurrent_target_creation_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_plain_pair(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    target = academic_result_manifest_revision_path(tmp_path, work, 1)
    intruder = b"concurrently-created\n"

    def create_target(
        context: generation.AcademicResultManifestGenerationContext,
    ) -> None:
        target.write_bytes(intruder)

    monkeypatch.setattr(generation, "_run_prewrite_verification_hook", create_target)
    with pytest.raises(QuillanManifestGenerationConflictError):
        generate_academic_result_manifest(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_1
        )

    assert target.read_bytes() == intruder


def test_post_durable_verification_failure_preserves_revision_as_partial_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_plain_pair(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    original = generation._load_manifest_history
    calls = 0

    def fail_second_history_load(
        workspace_root: Path,
        work_ref: ModuleWorkRef,
        *,
        allow_generation_lock: bool,
    ) -> tuple[generation.StoredAcademicResultManifest, ...]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise QuillanManifestGenerationIntegrityError(
                "synthetic final verification failure"
            )
        return original(
            workspace_root,
            work_ref,
            allow_generation_lock=allow_generation_lock,
        )

    monkeypatch.setattr(generation, "_load_manifest_history", fail_second_history_load)
    with pytest.raises(QuillanManifestGenerationPartialSuccessError) as captured:
        generate_academic_result_manifest(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_1
        )

    error = captured.value
    target = academic_result_manifest_revision_path(tmp_path, work, 1)
    assert error.state.operation == "final_verification"
    assert error.state.revision == 1
    assert error.state.durable_file_exists is True
    assert target.is_file()
    assert not (target.parent / ".write.lock").exists()


def test_lock_cleanup_failure_after_creation_is_partial_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_plain_pair(tmp_path)
    work = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)

    def fail_cleanup(lock_path: Path, token: bytes) -> None:
        raise OSError("synthetic cleanup failure")

    monkeypatch.setattr(generation, "_release_generation_lock", fail_cleanup)
    with pytest.raises(QuillanManifestGenerationPartialSuccessError) as captured:
        generate_academic_result_manifest(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, clock=lambda: UTC_1
        )

    error = captured.value
    target = academic_result_manifest_revision_path(tmp_path, work, 1)
    assert error.state.operation == "lock_cleanup"
    assert error.state.lock_cleanup_failure is not None
    assert target.is_file()
    assert (target.parent / ".write.lock").is_file()


def test_storage_source_has_no_revision_update_or_delete_primitive() -> None:
    source = inspect.getsource(generation)
    assert "revision_guarded_update(" not in source
    assert "def delete_academic_result_manifest" not in source
    assert '"latest.json"' not in source
    assert '"current.json"' not in source

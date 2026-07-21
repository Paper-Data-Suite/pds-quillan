"""Transactional observation persistence and strict discovery."""

from pathlib import Path
from dataclasses import replace
import os
import subprocess
import sys

import pytest
from pds_core.module_dispatch import RouteDispatchSuccess

from quillan.module_errors import (
    QuillanObservationIntegrityError,
    QuillanObservationPersistenceError,
    QuillanRoutedEvidenceIntegrityError,
)
import quillan.response_page_observation_persistence as observation_persistence
from quillan.pds2_scan_intake import QuillanScanPageOutcome
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.response_page_dispatch import QuillanResponsePageDispatchResult
from quillan.response_page_observations import (
    list_quillan_page_observations,
    load_response_page_observation,
)
from tests.observation_test_support import successful_image_page


def _dispatch_result(
    outcome: QuillanScanPageOutcome,
) -> QuillanResponsePageDispatchResult:
    success = outcome.dispatch_outcome
    assert type(success) is RouteDispatchSuccess
    result = success.module_result
    assert type(result) is QuillanResponsePageDispatchResult
    return result


def test_exact_retry_is_idempotent(tmp_path: Path) -> None:
    outcome = successful_image_page(tmp_path)
    first = persist_quillan_page_observation(tmp_path, outcome)
    observation_bytes = first.observation_path.read_bytes()
    evidence_bytes = first.evidence_path.read_bytes()
    second = persist_quillan_page_observation(tmp_path, outcome)
    assert (first.status, second.status) == ("created", "existing")
    assert second.observation_path.read_bytes() == observation_bytes
    assert second.evidence_path.read_bytes() == evidence_bytes
    assert list_quillan_page_observations(
        tmp_path, first.observation.class_id, first.observation.assignment_id
    ) == (first.observation,)


def test_partial_existing_evidence_is_never_claimed(tmp_path: Path) -> None:
    outcome = successful_image_page(tmp_path)
    first = persist_quillan_page_observation(tmp_path, outcome)
    first.observation_path.unlink()
    with pytest.raises(QuillanObservationIntegrityError, match="Orphan"):
        persist_quillan_page_observation(tmp_path, outcome)


def test_observation_without_evidence_is_never_claimed(tmp_path: Path) -> None:
    outcome = successful_image_page(tmp_path)
    first = persist_quillan_page_observation(tmp_path, outcome)
    first.evidence_path.unlink()
    with pytest.raises(QuillanObservationIntegrityError, match="without") as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    assert caught.value.possible_observation_path == first.observation_path
    assert caught.value.possible_evidence_path == first.evidence_path


@pytest.mark.parametrize("target", ["observation", "evidence-bytes", "evidence-hash"])
def test_existing_transaction_contradictions_are_typed(
    tmp_path: Path, target: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    first = persist_quillan_page_observation(tmp_path, outcome)
    if target == "observation":
        data = first.observation_path.read_bytes()
        first.observation_path.write_bytes(
            data.replace(
                b'"module_details": {}', b'"module_details": {"changed": true}'
            )
        )
    elif target == "evidence-bytes":
        original = first.evidence_path.read_bytes()
        first.evidence_path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    else:

        def fail_hash(*args: object, **kwargs: object) -> None:
            raise QuillanRoutedEvidenceIntegrityError("hash contradiction")

        monkeypatch.setattr(
            observation_persistence, "verify_routed_page_evidence", fail_hash
        )
    with pytest.raises(QuillanObservationIntegrityError) as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    assert caught.value.possible_observation_path == first.observation_path
    assert caught.value.possible_evidence_path == first.evidence_path


@pytest.mark.parametrize(
    ("failure_call", "error_type"),
    [(0, OSError), (1, FileExistsError), (2, FileExistsError)],
    ids=["temporary-write", "evidence-collision", "observation-collision"],
)
def test_transaction_install_failure_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_call: int,
    error_type: type[OSError],
) -> None:
    outcome = successful_image_page(tmp_path)
    if failure_call == 0:
        monkeypatch.setattr(
            observation_persistence,
            "_write_temporary",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("temporary failure")
            ),
        )
    else:
        install = observation_persistence._install_exclusive
        calls = 0

        def injected(
            temporary: Path, destination: Path
        ) -> observation_persistence._ExclusiveInstallResult:
            nonlocal calls
            calls += 1
            if calls == failure_call:
                raise error_type("exclusive collision")
            return install(temporary, destination)

        monkeypatch.setattr(observation_persistence, "_install_exclusive", injected)
    with pytest.raises(QuillanObservationPersistenceError) as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    assert isinstance(caught.value.__cause__, OSError)
    assert not tuple(tmp_path.rglob("*.tmp"))


def test_evidence_install_filesystem_failure_is_typed_and_leaves_no_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    monkeypatch.setattr(
        observation_persistence,
        "_install_exclusive",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("evidence installation failed")
        ),
    )
    with pytest.raises(QuillanObservationPersistenceError) as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    assert isinstance(caught.value.__cause__, OSError)
    assert caught.value.possible_observation_path is None
    assert caught.value.possible_evidence_path is None
    assert not tuple(tmp_path.rglob("*.tmp"))


def test_evidence_post_link_cleanup_failure_preserves_orphan_and_reports_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_bytes(b"keep")
    cleanup_error = OSError("evidence temporary unlink failed")

    def post_link_failure(
        temporary: Path, destination: Path
    ) -> observation_persistence._ExclusiveInstallResult:
        os.link(temporary, destination)
        return observation_persistence._ExclusiveInstallResult(
            True, False, cleanup_error
        )

    monkeypatch.setattr(
        observation_persistence, "_install_exclusive", post_link_failure
    )
    with pytest.raises(QuillanObservationPersistenceError) as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    error = caught.value
    assert error.__cause__ is cleanup_error
    assert error.possible_observation_path is None
    assert error.possible_evidence_path is not None
    evidence = error.possible_evidence_path
    assert evidence.is_file()
    assert evidence.read_bytes() == outcome.retained_source.retained_source_path.read_bytes()
    assert not tuple(tmp_path.rglob("obs_*.json"))
    assert unrelated.read_bytes() == b"keep"
    assert not tuple(tmp_path.rglob("*.tmp"))
    monkeypatch.undo()
    with pytest.raises(QuillanObservationIntegrityError, match="Orphan"):
        persist_quillan_page_observation(tmp_path, outcome)


def test_observation_post_link_cleanup_failure_preserves_pair_and_retry_validates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    install = observation_persistence._install_exclusive
    cleanup_error = OSError("observation temporary unlink failed")
    calls = 0

    def post_link_failure(
        temporary: Path, destination: Path
    ) -> observation_persistence._ExclusiveInstallResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return install(temporary, destination)
        os.link(temporary, destination)
        return observation_persistence._ExclusiveInstallResult(
            True, False, cleanup_error
        )

    monkeypatch.setattr(
        observation_persistence, "_install_exclusive", post_link_failure
    )
    with pytest.raises(QuillanObservationPersistenceError) as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    error = caught.value
    assert error.__cause__ is cleanup_error
    assert error.possible_observation_path is not None
    assert error.possible_evidence_path is not None
    observation_bytes = error.possible_observation_path.read_bytes()
    evidence_bytes = error.possible_evidence_path.read_bytes()
    assert not tuple(tmp_path.rglob("*.tmp"))
    monkeypatch.undo()
    retry = persist_quillan_page_observation(tmp_path, outcome)
    assert retry.status == "existing"
    assert retry.observation_path.read_bytes() == observation_bytes
    assert retry.evidence_path.read_bytes() == evidence_bytes


def test_contradictory_observation_post_link_state_preserves_both_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    install = observation_persistence._install_exclusive
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_bytes(b"keep")
    cleanup_error = OSError("observation cleanup failed")
    calls = 0

    def contradict_after_link(
        temporary: Path, destination: Path
    ) -> observation_persistence._ExclusiveInstallResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return install(temporary, destination)
        os.link(temporary, destination)
        destination.write_bytes(b"contradictory observation bytes")
        return observation_persistence._ExclusiveInstallResult(
            True, False, cleanup_error
        )

    monkeypatch.setattr(
        observation_persistence, "_install_exclusive", contradict_after_link
    )
    with pytest.raises(QuillanObservationIntegrityError) as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    error = caught.value
    assert error.possible_observation_path is not None
    assert error.possible_evidence_path is not None
    assert error.possible_observation_path.read_bytes() == b"contradictory observation bytes"
    assert error.possible_evidence_path.is_file()
    assert unrelated.read_bytes() == b"keep"
    assert not tuple(tmp_path.rglob("*.tmp"))


def test_changed_owned_evidence_refuses_rollback_and_reports_durable_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    install = observation_persistence._install_exclusive
    calls = 0
    installed_evidence: Path | None = None

    def injected(
        temporary: Path, destination: Path
    ) -> observation_persistence._ExclusiveInstallResult:
        nonlocal calls, installed_evidence
        calls += 1
        if calls == 1:
            installed = install(temporary, destination)
            installed_evidence = destination
            return installed
        assert installed_evidence is not None
        installed_evidence.write_bytes(b"changed by another actor")
        raise OSError("observation installation failed")

    monkeypatch.setattr(observation_persistence, "_install_exclusive", injected)
    with pytest.raises(QuillanObservationPersistenceError, match="rollback") as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    assert caught.value.possible_evidence_path == installed_evidence
    assert (
        installed_evidence is not None
        and installed_evidence.read_bytes() == b"changed by another actor"
    )


def test_rollback_filesystem_failure_is_not_destructive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("keep", encoding="utf-8")
    install = observation_persistence._install_exclusive
    calls = 0

    def fail_second(
        temporary: Path, destination: Path
    ) -> observation_persistence._ExclusiveInstallResult:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("observation failure")
        return install(temporary, destination)

    monkeypatch.setattr(observation_persistence, "_install_exclusive", fail_second)
    monkeypatch.setattr(
        observation_persistence, "_remove_owned_file", lambda *_args: False
    )
    with pytest.raises(QuillanObservationPersistenceError, match="rollback"):
        persist_quillan_page_observation(tmp_path, outcome)
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_reload_mismatch_and_evidence_reload_failure_are_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    original_load = load_response_page_observation
    monkeypatch.setattr(
        observation_persistence,
        "load_contextual_response_page_observation",
        lambda _root, _work_ref, _observation_id: replace(
            original_load(
                next(tmp_path.rglob(f"{_observation_id}.json"))
            ),
            module_details={"unexpected": True},
        ),
    )
    with pytest.raises(
        QuillanObservationPersistenceError, match="Reloaded observation"
    ) as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    assert caught.value.possible_observation_path is not None
    assert caught.value.possible_evidence_path is not None


def test_evidence_reload_mismatch_reports_both_durable_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    monkeypatch.setattr(
        observation_persistence,
        "verify_routed_page_evidence",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            QuillanRoutedEvidenceIntegrityError("reload hash mismatch")
        ),
    )
    with pytest.raises(QuillanObservationPersistenceError) as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    assert caught.value.possible_observation_path is not None
    assert caught.value.possible_evidence_path is not None


def test_unexpected_runtime_propagates_from_single_persistence_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    monkeypatch.setattr(
        observation_persistence,
        "_write_temporary",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("programming failure")
        ),
    )
    with pytest.raises(RuntimeError, match="programming failure"):
        persist_quillan_page_observation(tmp_path, outcome)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
@pytest.mark.parametrize("component", ["observations", "evidence", "issuance"])
def test_real_windows_junctions_in_new_observation_paths_are_rejected(
    tmp_path: Path, component: str
) -> None:
    outcome = successful_image_page(tmp_path)
    result = _dispatch_result(outcome)
    work = (
        tmp_path
        / "classes"
        / result.class_id
        / "modules"
        / "quillan"
        / "work"
        / result.assignment_id
    )
    if component == "observations":
        junction = work / "scans" / "observations"
    elif component == "evidence":
        junction = work / "scans" / "evidence"
    else:
        junction = work / "scans" / "evidence" / result.issuance_id
    junction.parent.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / f"outside-{component}"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    created = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    try:
        with pytest.raises(QuillanObservationPersistenceError, match="preflight"):
            persist_quillan_page_observation(tmp_path, outcome)
        assert sentinel.read_text(encoding="utf-8") == "keep"
    finally:
        os.rmdir(junction)


def test_observation_directory_symlink_is_rejected_without_external_write(
    tmp_path: Path,
) -> None:
    outcome = successful_image_page(tmp_path)
    result = _dispatch_result(outcome)
    work = (
        tmp_path
        / "classes"
        / result.class_id
        / "modules"
        / "quillan"
        / "work"
        / result.assignment_id
    )
    link = work / "scans" / "observations"
    outside = tmp_path / "outside-observations"
    outside.mkdir()
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("symlink creation unavailable: WinError 1314")
        raise
    with pytest.raises(QuillanObservationPersistenceError, match="preflight"):
        persist_quillan_page_observation(tmp_path, outcome)
    assert not tuple(outside.iterdir())


def test_destination_replacement_collision_preserves_unowned_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    install = observation_persistence._install_exclusive

    def race(
        temporary: Path, destination: Path
    ) -> observation_persistence._ExclusiveInstallResult:
        destination.write_bytes(b"unowned racing file")
        return install(temporary, destination)

    monkeypatch.setattr(observation_persistence, "_install_exclusive", race)
    with pytest.raises(QuillanObservationPersistenceError) as caught:
        persist_quillan_page_observation(tmp_path, outcome)
    assert isinstance(caught.value.__cause__, FileExistsError)
    durable = caught.value.possible_evidence_path
    assert durable is not None and durable.read_bytes() == b"unowned racing file"


@pytest.mark.parametrize("component", ["observations", "evidence", "issuance"])
def test_file_where_new_observation_directory_is_expected_is_rejected(
    tmp_path: Path, component: str
) -> None:
    outcome = successful_image_page(tmp_path)
    result = _dispatch_result(outcome)
    work = (
        tmp_path
        / "classes"
        / result.class_id
        / "modules"
        / "quillan"
        / "work"
        / result.assignment_id
    )
    if component == "observations":
        wrong = work / "scans" / "observations"
    elif component == "evidence":
        wrong = work / "scans" / "evidence"
    else:
        wrong = work / "scans" / "evidence" / result.issuance_id
    wrong.parent.mkdir(parents=True, exist_ok=True)
    wrong.write_text("wrong type", encoding="utf-8")
    with pytest.raises(QuillanObservationPersistenceError, match="preflight"):
        persist_quillan_page_observation(tmp_path, outcome)


@pytest.mark.parametrize("target", ["observation", "evidence"])
def test_directory_where_new_observation_file_is_expected_is_rejected(
    tmp_path: Path, target: str
) -> None:
    outcome = successful_image_page(tmp_path)
    persisted = persist_quillan_page_observation(tmp_path, outcome)
    path = (
        persisted.observation_path
        if target == "observation"
        else persisted.evidence_path
    )
    path.unlink()
    path.mkdir()
    with pytest.raises(QuillanObservationPersistenceError):
        persist_quillan_page_observation(tmp_path, outcome)


def test_observation_install_failure_rolls_back_only_current_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    retained_path = outcome.retained_source.retained_source_path
    retained_bytes = retained_path.read_bytes()
    install = observation_persistence._install_exclusive
    calls = 0

    def fail_observation_install(
        temporary: Path, destination: Path
    ) -> observation_persistence._ExclusiveInstallResult:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected observation install failure")
        return install(temporary, destination)

    monkeypatch.setattr(
        observation_persistence, "_install_exclusive", fail_observation_install
    )
    with pytest.raises(
        QuillanObservationPersistenceError,
        match="rolled back",
    ):
        persist_quillan_page_observation(tmp_path, outcome)

    assert retained_path.read_bytes() == retained_bytes
    assert not tuple(tmp_path.rglob("obs_*.json"))
    assert not tuple(
        path for path in tmp_path.rglob("response_*__obs_*.*") if path.is_file()
    )

"""Immutable Quillan response-page observation contracts."""

from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from quillan.module_errors import (
    QuillanObservationDiscoveryError,
    QuillanObservationValidationError,
)
import quillan.response_page_observations as observation_service
import quillan.routed_evidence as routed_evidence_service
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.response_page_observations import (
    QuillanResponsePageObservation,
    canonical_response_page_observation_json,
    derive_observation_id,
    list_quillan_page_observations,
    load_contextual_response_page_observation,
    load_response_page_observation,
    response_page_observation_from_mapping,
    response_page_observation_to_mapping,
)
from quillan.submission_manifest_paths import submission_manifest_path
from quillan.submission_observation_assembly import (
    assemble_quillan_submission_manifests,
)
import quillan.work_paths as work_paths_service
from quillan.work_paths import quillan_work_ref
from tests.observation_test_support import successful_image_page


def _mutated_observation(
    observation: QuillanResponsePageObservation, **changes: object
) -> QuillanResponsePageObservation:
    mapping = dict[str, object](response_page_observation_to_mapping(observation))
    mapping.update(changes)
    return response_page_observation_from_mapping(mapping)


def test_observation_id_is_deterministic_and_occurrence_specific() -> None:
    values = ("scan_synthetic", 1, "rt_" + "1" * 32, "pg_" + "2" * 32)
    first = derive_observation_id(*values)
    assert first == derive_observation_id(*values)
    assert first.startswith("obs_") and len(first) == 36
    assert first != derive_observation_id(values[0], 2, values[2], values[3])


def test_persisted_observation_round_trips_without_mutable_mapping_leakage(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    loaded = load_response_page_observation(persisted.observation_path)
    assert loaded == persisted.observation
    assert (
        response_page_observation_from_mapping(
            response_page_observation_to_mapping(loaded)
        )
        == loaded
    )
    with pytest.raises(TypeError):
        loaded.module_details["mutate"] = True  # type: ignore[index]


def test_strict_loader_rejects_duplicate_keys_and_filename_mismatch(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    mapping = response_page_observation_to_mapping(persisted.observation)
    wrong = persisted.observation_path.with_name("obs_" + "f" * 32 + ".json")
    wrong.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(QuillanObservationValidationError, match="filename"):
        load_response_page_observation(wrong)
    duplicate = persisted.observation_path.with_name("duplicate.json")
    duplicate.write_text(
        '{"schema_version":"1","schema_version":"1"}', encoding="utf-8"
    )
    with pytest.raises(QuillanObservationValidationError, match="Duplicate"):
        load_response_page_observation(duplicate)


def test_public_observation_loader_rejects_bad_path_types_missing_and_directory(
    tmp_path: Path,
) -> None:
    with pytest.raises(QuillanObservationValidationError, match="str or Path"):
        load_response_page_observation(42)  # type: ignore[arg-type]
    with pytest.raises(QuillanObservationValidationError, match="missing"):
        load_response_page_observation(tmp_path / "missing.json")
    with pytest.raises(QuillanObservationValidationError, match="ordinary non-link file"):
        load_response_page_observation(tmp_path)


def test_public_observation_loader_rejects_fabricated_link_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation_path = persisted.observation_path
    original_link_check = observation_service._path_is_link_like
    monkeypatch.setattr(
        observation_service,
        "_path_is_link_like",
        lambda path: path == observation_path or original_link_check(path),
    )
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path == observation_path:
            pytest.fail("observation bytes were read before link rejection")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    with pytest.raises(QuillanObservationValidationError, match="non-link"):
        load_response_page_observation(observation_path)


def test_public_observation_loader_rejects_real_external_symlink_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    external = tmp_path.parent / f"{tmp_path.name}-external-observation.json"
    external.write_bytes(persisted.observation_path.read_bytes())
    sentinel = tmp_path.parent / f"{tmp_path.name}-external-sentinel.txt"
    sentinel.write_bytes(b"external sentinel")
    link = tmp_path / f"{persisted.observation.observation_id}.json"
    try:
        link.symlink_to(external)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("symlink creation unavailable: WinError 1314")
        raise
    external_bytes = external.read_bytes()
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path == link:
            pytest.fail("external observation was read through its symbolic link")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    with pytest.raises(QuillanObservationValidationError, match="link-like"):
        load_response_page_observation(link)
    assert original_read_bytes(external) == external_bytes
    assert original_read_bytes(sentinel) == b"external sentinel"
    assert persisted.observation_path.is_file()
    assert persisted.evidence_path.is_file()
    assert not submission_manifest_path(
        tmp_path,
        persisted.observation.class_id,
        persisted.observation.assignment_id,
        persisted.observation.student_id,
    ).exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_contextual_observation_loader_rejects_real_junctioned_parent_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    observations_directory = persisted.observation_path.parent
    outside = tmp_path.parent / f"{tmp_path.name}-outside-observations"
    shutil.move(str(observations_directory), str(outside))
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"external sentinel")
    created = subprocess.run(
        [
            "cmd.exe",
            "/c",
            "mklink",
            "/J",
            str(observations_directory),
            str(outside),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    external_observation = outside / persisted.observation_path.name
    external_observation_bytes = external_observation.read_bytes()
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path == persisted.observation_path:
            pytest.fail("junctioned observation bytes were read before ancestor rejection")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    try:
        with pytest.raises(QuillanObservationValidationError):
            load_contextual_response_page_observation(
                tmp_path,
                quillan_work_ref(observation.class_id, observation.assignment_id),
                observation.observation_id,
            )
        assert original_read_bytes(sentinel) == b"external sentinel"
        assert original_read_bytes(external_observation) == external_observation_bytes
        assert persisted.evidence_path.is_file()
        assert not submission_manifest_path(
            tmp_path,
            observation.class_id,
            observation.assignment_id,
            observation.student_id,
        ).exists()
    finally:
        os.rmdir(observations_directory)


def test_model_rejects_noncanonical_observation_identity(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    with pytest.raises(QuillanObservationValidationError, match="observation_id"):
        replace(persisted.observation, observation_id="obs_" + "f" * 32)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2"),
        ("record_type", "wrong"),
        ("module_id", "other"),
        ("generation_id", "generation"),
        ("artifact_id", "artifact"),
        ("issuance_id", "issuance"),
        ("page_id", "page"),
        ("route_id", "route"),
        ("class_id", "bad class"),
        ("assignment_id", "bad assignment"),
        ("student_id", "bad student"),
        ("logical_page", 0),
        ("total_pages", True),
        ("page_role", "back"),
        ("source_page_number", False),
        ("source_sha256", "A" * 64),
        ("created_at", "2026-07-21"),
        ("intake_timestamp", "2026-07-21"),
        ("intake_date", "2026-99-99"),
        ("routed_evidence_path", "/absolute.png"),
        ("routed_evidence_sha256", "f" * 63),
        ("routed_evidence_size_bytes", 0),
        ("routed_evidence_kind", "unknown"),
        ("module_details", {"bad": object()}),
    ],
)
def test_every_observation_field_family_is_strict(
    tmp_path: Path, field: str, value: object
) -> None:
    observation = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    ).observation
    with pytest.raises((QuillanObservationValidationError, ValueError)):
        _mutated_observation(observation, **{field: value})


def test_observation_cross_field_and_json_freeze_matrix(tmp_path: Path) -> None:
    observation = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path, pages=2)
    ).observation
    mutations = (
        {"logical_page": 2},
        {"logical_page": 3, "total_pages": 2},
        {"created_at": "2026-07-22T00:00:00+00:00"},
        {
            "routed_evidence_path": observation.routed_evidence_path.replace(
                observation.issuance_id, "iss_" + "f" * 32
            )
        },
        {
            "routed_evidence_path": observation.routed_evidence_path.replace(
                observation.observation_id, "obs_" + "f" * 32
            )
        },
    )
    for changes in mutations:
        with pytest.raises(QuillanObservationValidationError):
            _mutated_observation(observation, **changes)

    nested = _mutated_observation(
        observation,
        module_details={"values": [None, True, 1, 1.5, "text", {"nested": [2]}]},
    )
    assert nested.module_details["values"] == (
        None,
        True,
        1,
        1.5,
        "text",
        {"nested": (2,)},
    )
    assert response_page_observation_to_mapping(nested)["module_details"] == {
        "values": [None, True, 1, 1.5, "text", {"nested": [2]}]
    }
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(QuillanObservationValidationError, match="finite"):
            _mutated_observation(observation, module_details={"number": value})


def test_mapping_and_loader_reject_unknown_missing_constants_and_utf8(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    mapping = response_page_observation_to_mapping(persisted.observation)
    for corrupt in (
        {key: value for key, value in mapping.items() if key != "page_id"},
        {**mapping, "unknown": True},
    ):
        with pytest.raises(QuillanObservationValidationError):
            response_page_observation_from_mapping(corrupt)
    persisted.observation_path.write_bytes(b"\xff\xfe")
    with pytest.raises(QuillanObservationValidationError):
        load_response_page_observation(persisted.observation_path)
    persisted.observation_path.write_bytes(
        canonical_response_page_observation_json(persisted.observation).replace(
            b'"module_details": {}', b'"module_details": {"bad": NaN}'
        )
    )
    with pytest.raises(QuillanObservationValidationError, match="constant"):
        load_response_page_observation(persisted.observation_path)


def test_core_retention_components_are_one_identity(tmp_path: Path) -> None:
    observation = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    ).observation
    path = observation.retained_source_path
    filename = Path(path).name
    timestamp = "2026-07-20T00:00:00+00:00"
    cases = (
        {"source_scan_id": "scan_arbitrary_safe"},
        {"source_filename": "different.png"},
        {"source_filename": "selected.jpg"},
        {"source_sha256": "f" * 64},
        {"created_at": timestamp, "intake_timestamp": timestamp},
        {"intake_date": "2026-07-20"},
        {
            "retained_source_path": path.replace(
                f"/{observation.intake_date}/", "/2000-01-01/"
            )
        },
        {"retained_source_path": path.replace(filename, "arbitrary.png")},
        {"retained_source_path": path.replace("scans/source", "scans//source")},
        {"retained_source_path": "/" + path},
        {"retained_source_path": path.replace("/", "\\")},
    )
    for changes in cases:
        with pytest.raises(QuillanObservationValidationError):
            _mutated_observation(observation, **changes)


def test_explicit_core_intake_date_override_is_valid_at_model_level(
    tmp_path: Path,
) -> None:
    observation = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    ).observation
    overridden = _mutated_observation(
        observation,
        intake_date="2000-01-01",
        retained_source_path=observation.retained_source_path.replace(
            f"/{observation.intake_date}/", "/2000-01-01/"
        ),
    )
    assert overridden.intake_date == "2000-01-01"


def test_discovery_rejects_link_like_retained_source(tmp_path: Path) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    retained = tmp_path.joinpath(
        *Path(persisted.observation.retained_source_path).parts
    )
    target = retained.with_name("target.png")
    target.write_bytes(retained.read_bytes())
    retained.unlink()
    try:
        retained.symlink_to(target)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("symlink creation unavailable: WinError 1314")
        raise
    with pytest.raises(QuillanObservationDiscoveryError):
        list_quillan_page_observations(
            tmp_path,
            persisted.observation.class_id,
            persisted.observation.assignment_id,
        )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_discovery_rejects_real_junctioned_retained_source_ancestor(
    tmp_path: Path,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    retained = tmp_path.joinpath(*Path(observation.retained_source_path).parts)
    date_directory = retained.parent
    outside = tmp_path / "outside-retained-date"
    shutil.move(str(date_directory), str(outside))
    created = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(date_directory), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    try:
        with pytest.raises(QuillanObservationDiscoveryError):
            list_quillan_page_observations(
                tmp_path, observation.class_id, observation.assignment_id
            )
    finally:
        os.rmdir(date_directory)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
@pytest.mark.parametrize("component", ["evidence", "issuance"])
def test_discovery_rejects_real_routed_evidence_ancestor_junction_without_read(
    tmp_path: Path,
    component: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    observation = persisted.observation
    evidence = persisted.evidence_path
    ancestor = evidence.parents[1] if component == "evidence" else evidence.parent
    outside = tmp_path / f"outside-{component}"
    shutil.move(str(ancestor), str(outside))
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"external sentinel")
    created = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(ancestor), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    reads: list[Path] = []
    original_read = routed_evidence_service._read_exact_bytes

    def record_read(path: Path) -> bytes:
        reads.append(path)
        return original_read(path)

    monkeypatch.setattr(routed_evidence_service, "_read_exact_bytes", record_read)
    manifest = submission_manifest_path(
        tmp_path,
        observation.class_id,
        observation.assignment_id,
        observation.student_id,
    )
    try:
        with pytest.raises(QuillanObservationDiscoveryError) as caught:
            list_quillan_page_observations(
                tmp_path, observation.class_id, observation.assignment_id
            )
        assert caught.value.category == "observation_invalid"
        assembled = assemble_quillan_submission_manifests(
            tmp_path, observation.class_id, observation.assignment_id
        )
        assert not assembled.assembled
        assert assembled.failures[0].category == "observation_invalid"
        assert not reads
        assert sentinel.read_bytes() == b"external sentinel"
        assert persisted.observation_path.is_file()
        assert outside.joinpath(*evidence.relative_to(ancestor).parts).is_file()
        assert not manifest.exists()
    finally:
        os.rmdir(ancestor)


@pytest.mark.parametrize("component", ["evidence", "issuance", "file"])
def test_each_routed_evidence_link_like_branch_is_rejected_before_read(
    tmp_path: Path,
    component: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    evidence = persisted.evidence_path
    target = {
        "evidence": evidence.parents[1],
        "issuance": evidence.parent,
        "file": evidence,
    }[component]
    original_link_check = work_paths_service._is_link_like
    monkeypatch.setattr(
        work_paths_service,
        "_is_link_like",
        lambda path: path == target or original_link_check(path),
    )
    monkeypatch.setattr(
        routed_evidence_service,
        "_read_exact_bytes",
        lambda _path: pytest.fail("evidence bytes were read before path preflight"),
    )
    with pytest.raises(QuillanObservationDiscoveryError) as caught:
        list_quillan_page_observations(
            tmp_path,
            persisted.observation.class_id,
            persisted.observation.assignment_id,
        )
    assert caught.value.category == "observation_invalid"
    assert persisted.observation_path.is_file()
    assert evidence.is_file()


@pytest.mark.parametrize("component", ["evidence", "issuance"])
def test_discovery_rejects_routed_evidence_ancestor_symlink_without_read(
    tmp_path: Path,
    component: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted = persist_quillan_page_observation(
        tmp_path, successful_image_page(tmp_path)
    )
    evidence = persisted.evidence_path
    ancestor = evidence.parents[1] if component == "evidence" else evidence.parent
    outside = tmp_path / f"outside-symlink-{component}"
    shutil.move(str(ancestor), str(outside))
    try:
        ancestor.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("symlink creation unavailable: WinError 1314")
        raise
    monkeypatch.setattr(
        routed_evidence_service,
        "_read_exact_bytes",
        lambda _path: pytest.fail("external evidence bytes were read"),
    )
    try:
        with pytest.raises(QuillanObservationDiscoveryError) as caught:
            list_quillan_page_observations(
                tmp_path,
                persisted.observation.class_id,
                persisted.observation.assignment_id,
            )
        assert caught.value.category == "observation_invalid"
        assert persisted.observation_path.is_file()
        assert outside.joinpath(*evidence.relative_to(ancestor).parts).is_file()
    finally:
        os.rmdir(ancestor)

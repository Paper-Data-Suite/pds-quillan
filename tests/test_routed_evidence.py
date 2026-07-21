"""Routed evidence is derived only from Core-retained page bytes."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pds_core.module_dispatch import RouteDispatchSuccess

import quillan.routed_evidence as routed_evidence
from quillan.module_errors import QuillanRoutedEvidenceError
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.response_page_dispatch import QuillanResponsePageDispatchResult
from tests.observation_test_support import successful_image_page, successful_pdf_pages


def test_image_evidence_preserves_exact_retained_bytes(tmp_path: Path) -> None:
    outcome = successful_image_page(tmp_path)
    persisted = persist_quillan_page_observation(tmp_path, outcome)
    assert (
        persisted.evidence_path.read_bytes()
        == outcome.retained_source.retained_source_path.read_bytes()
    )
    assert persisted.observation.routed_evidence_kind == "retained_image_copy"
    assert persisted.evidence_path.suffix == ".png"


def test_pdf_evidence_renders_only_requested_pages_as_distinct_pngs(
    tmp_path: Path,
) -> None:
    first_outcome, second_outcome = successful_pdf_pages(tmp_path)
    first = persist_quillan_page_observation(tmp_path, first_outcome)
    second = persist_quillan_page_observation(tmp_path, second_outcome)
    assert first.observation.routed_evidence_kind == "rendered_pdf_page_png"
    assert second.observation.routed_evidence_kind == "rendered_pdf_page_png"
    assert first.evidence_path.suffix == second.evidence_path.suffix == ".png"
    assert first.evidence_path.read_bytes().startswith(b"\x89PNG")
    assert first.evidence_path.read_bytes() != second.evidence_path.read_bytes()


def test_prepare_routed_evidence_propagates_unexpected_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = successful_image_page(tmp_path)
    success = outcome.dispatch_outcome
    assert type(success) is RouteDispatchSuccess
    result = success.module_result
    assert type(result) is QuillanResponsePageDispatchResult
    monkeypatch.setattr(
        routed_evidence,
        "validate_quillan_retained_source",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("programming failure")
        ),
    )
    with pytest.raises(RuntimeError, match="programming failure"):
        routed_evidence._prepare_routed_page_evidence(
            tmp_path, result, observation_id="obs_" + "f" * 32
        )


def _prepared_evidence(
    tmp_path: Path,
) -> tuple[QuillanResponsePageDispatchResult, routed_evidence._PreparedRoutedPageEvidence]:
    outcome = successful_image_page(tmp_path)
    success = outcome.dispatch_outcome
    assert type(success) is RouteDispatchSuccess
    result = success.module_result
    assert type(result) is QuillanResponsePageDispatchResult
    prepared = routed_evidence._prepare_routed_page_evidence(
        tmp_path, result, observation_id="obs_" + "a" * 32
    )
    return result, prepared


def test_private_installer_rejects_every_forged_destination_before_mutation(
    tmp_path: Path,
) -> None:
    result, prepared = _prepared_evidence(tmp_path)
    work = (
        tmp_path
        / "classes"
        / result.class_id
        / "modules"
        / "quillan"
        / "work"
        / result.assignment_id
    )
    destinations = (
        work / "arbitrary.png",
        work / "assignment.json",
        work / "submissions" / result.student_id / "forged.png",
        prepared.path.parent.parent / ("iss_" + "f" * 32) / prepared.path.name,
    )
    forged: list[routed_evidence._PreparedRoutedPageEvidence] = [
        replace(prepared, observation_id="obs_" + "b" * 32),
        replace(prepared, evidence_kind="rendered_pdf_page_png"),
    ]
    for destination, relative_path in (
        *((destination, destination.relative_to(tmp_path).as_posix()) for destination in destinations),
        (prepared.path, "classes/contradiction.png"),
    ):
        item = object.__new__(routed_evidence._PreparedRoutedPageEvidence)
        for name, value in (
            ("workspace_root", prepared.workspace_root),
            ("observation_id", prepared.observation_id),
            ("path", destination),
            ("relative_path", relative_path),
            ("sha256", prepared.sha256),
            ("size_bytes", prepared.size_bytes),
            ("extension", prepared.extension),
            ("evidence_kind", prepared.evidence_kind),
            ("content", prepared.content),
        ):
            object.__setattr__(item, name, value)
        forged.append(item)
    sentinel = work / "sentinel.txt"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_bytes(b"keep")
    assignment_path = work / "assignment.json"
    assignment_path.write_bytes(b"assignment sentinel")
    submission_directory = work / "submissions" / result.student_id
    submission_directory.mkdir(parents=True)
    for item in forged:
        with pytest.raises(QuillanRoutedEvidenceError):
            routed_evidence._install_prepared_routed_page_evidence(
                tmp_path, result, item
            )
    assert sentinel.read_bytes() == b"keep"
    assert assignment_path.read_bytes() == b"assignment sentinel"
    assert submission_directory.is_dir()
    assert not (submission_directory / "forged.png").exists()
    assert not destinations[0].exists()
    assert not destinations[3].exists()
    assert not prepared.path.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sha256", "f" * 64),
        ("size_bytes", 999),
        ("extension", ".jpg"),
        ("evidence_kind", "unknown"),
        ("content", bytearray(b"mutable")),
    ],
)
def test_prepared_evidence_rejects_field_contradictions(
    tmp_path: Path, field: str, value: object
) -> None:
    _, prepared = _prepared_evidence(tmp_path)
    unsafe_replace: Any = replace
    with pytest.raises(QuillanRoutedEvidenceError):
        unsafe_replace(prepared, **{field: value})
    assert not prepared.path.exists()


def test_private_installer_rejects_subclass_and_impostor(tmp_path: Path) -> None:
    result, prepared = _prepared_evidence(tmp_path)

    class Subclass(routed_evidence._PreparedRoutedPageEvidence):
        pass

    subclass = Subclass(
        prepared.workspace_root,
        prepared.observation_id,
        prepared.path,
        prepared.relative_path,
        prepared.sha256,
        prepared.size_bytes,
        prepared.extension,
        prepared.evidence_kind,
        prepared.content,
    )
    for value in (subclass, object()):
        with pytest.raises(QuillanRoutedEvidenceError):
            routed_evidence._install_prepared_routed_page_evidence(
                tmp_path, result, value  # type: ignore[arg-type]
            )
    assert not prepared.path.exists()


def test_public_installed_evidence_model_rejects_constructor_corruption(
    tmp_path: Path,
) -> None:
    _, prepared = _prepared_evidence(tmp_path)
    installed = routed_evidence._installed_result(prepared, created=False)
    sibling = tmp_path.parent / f"{tmp_path.name}-sibling"
    sibling.mkdir()
    unsafe_replace: Any = replace
    for changes in (
        {"workspace_root": sibling},
        {"path": sibling.joinpath(*Path(installed.relative_path).parts)},
        {"observation_id": "obs_" + "z" * 32},
        {"path": Path("relative.png")},
        {"relative_path": "../escape.png"},
        {"sha256": "A" * 64},
        {"size_bytes": True},
        {"extension": ".jpg"},
        {"evidence_kind": "unknown"},
        {"created_by_current_operation": 1},
    ):
        with pytest.raises(QuillanRoutedEvidenceError):
            unsafe_replace(installed, **changes)

"""Managed PDS2 packet transaction tests."""

from dataclasses import fields, replace
import importlib
from pathlib import Path
import subprocess
import sys
from typing import Any, cast

import pytest
from pds_core.classes import write_class_roster
from pds_core.rosters import create_roster
from quillan.printable_response_generation import (
    IdentityGenerators,
    PrintableResponseArtifactPlan,
    PrintableResponseGenerationError,
    build_printable_response_artifact_plan,
    execute_printable_response_artifact,
    select_printable_response_predecessors,
)
from quillan.printable_response_packet import (
    generate_printable_response_packet,
    plan_printable_response_packet,
)
from quillan.printable_response_persistence import (
    PrintableResponsePersistenceError,
    PrintableResponseRollbackError,
    load_printable_response_issuance,
    transition_printable_response_issuance,
)
from quillan.work_paths import quillan_work_ref
from tests.test_printable_response_packet import (
    ASSIGNMENT_ID,
    CLASS_ID,
    write_packet_workspace,
)

generation: Any = importlib.import_module("quillan.printable_response_generation")
route_service: Any = importlib.import_module("quillan.printable_response_routes")


def artifact_plan(tmp_path: Path) -> tuple[Any, PrintableResponseArtifactPlan]:
    packet_plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    predecessors = select_printable_response_predecessors(
        packet_plan.workspace_root, packet_plan.work_ref, packet_plan.students
    )
    artifact = build_printable_response_artifact_plan(
        workspace_root=packet_plan.workspace_root,
        work_ref=packet_plan.work_ref,
        assignment=packet_plan.assignment,
        students=packet_plan.students,
        pages_per_student=packet_plan.pages_per_student,
        output_path=packet_plan.output_path,
        predecessors=predecessors,
    )
    return packet_plan, artifact


@pytest.mark.parametrize("invalid_root", [None, object(), 42, []])
def test_predecessor_selection_rejects_wrong_root_types_as_generation_errors(
    tmp_path: Path,
    invalid_root: object,
) -> None:
    with pytest.raises(PrintableResponseGenerationError, match="workspace_root"):
        select_printable_response_predecessors(invalid_root, object(), object())  # type: ignore[arg-type]
    assert tuple(tmp_path.iterdir()) == ()


def unsafe_replace(value: Any, **changes: Any) -> Any:
    forged = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            forged, field.name, changes.get(field.name, getattr(value, field.name))
        )
    return forged


def assert_artifact_preflight_failure(
    packet_plan: Any, artifact: PrintableResponseArtifactPlan
) -> None:
    before = {
        path: path.read_bytes()
        for path in packet_plan.workspace_root.rglob("*")
        if path.is_file()
    }
    with pytest.raises(PrintableResponseGenerationError):
        execute_printable_response_artifact(
            artifact,
            output_relative_path=packet_plan.output_relative_path,
            expected_output_digest=packet_plan.output_sha256,
            overwrite=packet_plan.target_exists,
        )
    assert {
        path: path.read_bytes()
        for path in packet_plan.workspace_root.rglob("*")
        if path.is_file()
    } == before
    assert not artifact.temporary_path.exists()


@pytest.mark.parametrize(
    "forge",
    [
        lambda artifact: replace(artifact, assignment={}),
        lambda artifact: replace(
            artifact,
            assignment={**artifact.assignment, "assignment_id": "wrong_assignment"},
        ),
        lambda artifact: replace(
            artifact,
            assignment={**artifact.assignment, "class_ids": ["wrong_class"]},
        ),
        lambda artifact: replace(artifact, assignment_title="forged title"),
        lambda artifact: replace(
            artifact,
            record_sets=(
                unsafe_replace(
                    artifact.record_sets[0],
                    issuance=unsafe_replace(
                        artifact.record_sets[0].issuance,
                        assignment_snapshot=unsafe_replace(
                            artifact.record_sets[0].issuance.assignment_snapshot,
                            title="forged snapshot title",
                        ),
                    ),
                ),
                artifact.record_sets[1],
            ),
        ),
        lambda artifact: replace(
            artifact,
            record_sets=(
                unsafe_replace(
                    artifact.record_sets[0],
                    issuance=unsafe_replace(
                        artifact.record_sets[0].issuance,
                        assignment_snapshot=unsafe_replace(
                            artifact.record_sets[0].issuance.assignment_snapshot,
                            schema_version="1",
                        ),
                    ),
                ),
                artifact.record_sets[1],
            ),
        ),
        lambda artifact: replace(
            artifact,
            assignment={**artifact.assignment, "updated_at": "2030-01-01T00:00:00+00:00"},
        ),
        lambda artifact: replace(
            artifact,
            record_sets=(
                unsafe_replace(
                    artifact.record_sets[0],
                    issuance=unsafe_replace(
                        artifact.record_sets[0].issuance,
                        student_snapshot=unsafe_replace(
                            artifact.record_sets[0].issuance.student_snapshot,
                            first_name="Forged",
                        ),
                    ),
                ),
                artifact.record_sets[1],
            ),
        ),
        lambda artifact: replace(
            artifact,
            record_sets=(
                artifact.record_sets[0],
                unsafe_replace(
                    artifact.record_sets[1],
                    issuance=unsafe_replace(
                        artifact.record_sets[1].issuance, page_count=2
                    ),
                ),
            ),
        ),
    ],
    ids=[
        "invalid-assignment",
        "assignment-id",
        "assignment-class-membership",
        "assignment-title",
        "assignment-snapshot-title",
        "assignment-snapshot-schema",
        "assignment-timestamp",
        "student-snapshot",
        "heterogeneous-page-count",
    ],
)
def test_artifact_semantic_contradictions_fail_before_mutation(
    tmp_path: Path, forge: Any
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    assert_artifact_preflight_failure(packet_plan, forge(artifact))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"output_relative_path": "wrong/output.pdf"}, "output_relative_path"),
        ({"expected_output_digest": "0" * 64}, "non-replacement"),
        ({"overwrite": "yes"}, "overwrite"),
    ],
)
def test_public_execution_arguments_fail_before_mutation(
    tmp_path: Path, kwargs: dict[str, Any], message: str
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    arguments: dict[str, Any] = {
        "output_relative_path": packet_plan.output_relative_path,
        "expected_output_digest": None,
        "overwrite": False,
    }
    arguments.update(kwargs)
    with pytest.raises(PrintableResponseGenerationError, match=message):
        execute_printable_response_artifact(artifact, **arguments)
    assert not artifact.temporary_path.exists()
    assert not artifact.output_path.parent.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_output_digest": "0" * 64},
        {"overwrite": False},
        {"output_relative_path": "wrong/output.pdf"},
    ],
)
def test_replacement_execution_arguments_must_match_governed_artifact(
    tmp_path: Path, changes: dict[str, Any]
) -> None:
    write_packet_workspace(tmp_path)
    output = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID).output_path
    output.parent.mkdir(parents=True)
    output.write_bytes(b"governed prior output")
    packet_plan, artifact = artifact_plan(tmp_path)
    arguments: dict[str, Any] = {
        "output_relative_path": artifact.output_relative_path,
        "expected_output_digest": artifact.expected_output_digest,
        "overwrite": True,
    }
    arguments.update(changes)
    before = output.read_bytes()
    with pytest.raises(PrintableResponseGenerationError):
        execute_printable_response_artifact(artifact, **arguments)
    assert output.read_bytes() == before
    assert not artifact.temporary_path.exists()


@pytest.mark.parametrize(
    "change",
    [
        lambda artifact, root: replace(
            artifact, output_path=root / "outside.pdf"
        ),
        lambda artifact, root: replace(
            artifact, temporary_path=root / ".printable_response_pages.0123456789abcdef.tmp.pdf"
        ),
        lambda artifact, _root: replace(
            artifact, output_path=artifact.output_path.parents[4] / "sibling" / "templates" / artifact.output_path.name
        ),
        lambda artifact, _root: replace(
            artifact, output_path=artifact.output_path.parent.parent.parent / "wrong_assignment" / "templates" / artifact.output_path.name
        ),
        lambda artifact, _root: replace(
            artifact, output_path=artifact.output_path.with_name("alternate.pdf")
        ),
        lambda artifact, _root: replace(artifact, students=("wrong-model",)),
        lambda artifact, _root: replace(artifact, route_sets=("wrong-model",)),
    ],
    ids=[
        "external-output",
        "external-temporary",
        "sibling-module",
        "wrong-assignment",
        "alternate-filename",
        "wrong-student-model",
        "wrong-route-model",
    ],
)
def test_fabricated_artifact_is_rejected_before_mutation(
    tmp_path: Path, change: Any
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    fabricated = change(artifact, tmp_path.resolve())
    with pytest.raises(PrintableResponseGenerationError):
        execute_printable_response_artifact(
            fabricated,
            output_relative_path=packet_plan.output_relative_path,
            expected_output_digest=None,
            overwrite=False,
        )
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before
    assert not artifact.temporary_path.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_execution_rejects_templates_junction_before_external_mutation(
    tmp_path: Path,
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"unchanged")
    templates = artifact.output_path.parent
    templates.parent.mkdir(parents=True, exist_ok=True)
    created = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(templates), str(outside)],
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip(f"Windows junction creation unavailable: {created.stderr}")
    try:
        with pytest.raises(PrintableResponseGenerationError, match="junction"):
            execute_printable_response_artifact(
                artifact,
                output_relative_path=packet_plan.output_relative_path,
                expected_output_digest=None,
                overwrite=False,
            )
        assert sentinel.read_bytes() == b"unchanged"
        assert tuple(outside.iterdir()) == (sentinel,)
    finally:
        templates.rmdir()


def test_temporary_open_failure_creates_no_records_or_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    monkeypatch.setattr(
        generation.os,
        "open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("synthetic temporary open failure")
        ),
    )
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=packet_plan.output_relative_path,
        expected_output_digest=None,
        overwrite=False,
    )
    assert result.failure_stage == "preflight"
    assert "synthetic temporary open failure" in (result.error or "")
    assert result.created_route_count == 0
    assert not artifact.temporary_path.exists()


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_temporary_close_failure_owns_and_cleans_created_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_fails: bool,
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    original_close = generation.os.close

    def close_then_raise(descriptor: int) -> None:
        original_close(descriptor)
        raise OSError("synthetic descriptor close failure")

    monkeypatch.setattr(
        generation.os,
        "close",
        close_then_raise,
    )
    if cleanup_fails:
        original_unlink = Path.unlink

        def fail_temp_cleanup(path: Path, *args: Any, **kwargs: Any) -> None:
            if path == artifact.temporary_path:
                raise OSError("synthetic close cleanup failure")
            original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", fail_temp_cleanup)
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=packet_plan.output_relative_path,
        expected_output_digest=None,
        overwrite=False,
    )
    assert result.failure_stage == "preflight"
    assert result.error == "synthetic descriptor close failure"
    assert result.created_route_count == 0
    if cleanup_fails:
        assert artifact.temporary_path.is_file()
        assert any("synthetic close cleanup failure" in item for item in result.warnings)
    else:
        assert not artifact.temporary_path.exists()


def test_record_persistence_failure_after_one_set_cancels_completed_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    original = generation.write_printable_response_record_set
    calls = 0

    def fail_second(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise generation.PrintableResponsePersistenceError(
                "synthetic record persistence failure"
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(generation, "write_printable_response_record_set", fail_second)
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert not result.success and not result.installed
    assert result.failure_stage == "record_persistence"
    assert "synthetic record persistence failure" in (result.error or "")
    assert result.created_route_count == 0
    first = load_printable_response_issuance(
        tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), result.issuance_ids[0]
    )
    assert first.lifecycle.status == "cancelled"
    assert not any(artifact.name.endswith(".tmp.pdf") for artifact in tmp_path.rglob("*"))


@pytest.mark.parametrize(
    "error_type",
    [
        PrintableResponsePersistenceError,
        PrintableResponseRollbackError,
    ],
    ids=["before-first-record", "rollback-integrity"],
)
def test_first_record_persistence_failure_is_governed_and_nonrouting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: Any
) -> None:
    write_packet_workspace(tmp_path)
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    monkeypatch.setattr(
        generation,
        "write_printable_response_record_set",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            error_type("synthetic first-record failure")
        ),
    )
    result = generate_printable_response_packet(plan)
    assert not result.success and not result.installed
    assert result.failure_stage == "record_persistence"
    assert "synthetic first-record failure" in (result.error or "")
    assert result.created_route_count == result.verified_route_count == 0
    assert not plan.output_path.exists()
    assert not any(path.name.endswith(".tmp.pdf") for path in tmp_path.rglob("*"))


@pytest.mark.parametrize("contents", [b"", b"not a pdf"], ids=["empty", "non-pdf"])
def test_invalid_renderer_output_invalidates_issuances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contents: bytes
) -> None:
    write_packet_workspace(tmp_path)

    def invalid_render(
        _root: Any, _work: Any, destination: Path, _packets: Any
    ) -> Path:
        destination.write_bytes(contents)
        return destination

    monkeypatch.setattr(generation, "render_printable_response_pdf", invalid_render)
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert not result.installed and result.failure_stage == "pdf_rendering"
    assert all(
        load_printable_response_issuance(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )
    assert not result.output_path.exists()


def test_finalization_failure_after_one_transition_invalidates_actual_revisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    original = generation.transition_printable_response_issuance
    issued_calls = 0

    def fail_second_issue(*args: Any, **kwargs: Any) -> Any:
        nonlocal issued_calls
        if kwargs.get("new_status") == "issued":
            issued_calls += 1
            if issued_calls == 2:
                raise generation.PrintableResponsePersistenceError(
                    "synthetic issuance finalization failure"
                )
        return original(*args, **kwargs)

    monkeypatch.setattr(generation, "transition_printable_response_issuance", fail_second_issue)
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert not result.installed and result.failure_stage == "issuance_finalization"
    assert "synthetic issuance finalization failure" in (result.error or "")
    assert all(
        load_printable_response_issuance(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )


def test_finalization_failure_before_first_transition_invalidates_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    original = generation.transition_printable_response_issuance

    def fail_first_issue(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("new_status") == "issued":
            raise generation.PrintableResponsePersistenceError(
                "synthetic first finalization failure"
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(generation, "transition_printable_response_issuance", fail_first_issue)
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert not result.installed and result.failure_stage == "issuance_finalization"
    assert "synthetic first finalization failure" in (result.error or "")
    assert all(
        load_printable_response_issuance(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )
    assert result.failure_stage == "issuance_finalization" and not result.installed
    assert all(
        load_printable_response_issuance(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )


def test_compensation_failure_warns_without_masking_render_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    original_transition = generation.transition_printable_response_issuance
    monkeypatch.setattr(
        generation,
        "render_printable_response_pdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            generation.PrintableResponseRenderError("primary render failure")
        ),
    )

    def fail_compensation(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("new_status") == "invalidated" and args[2]:
            raise generation.PrintableResponsePersistenceError(
                "synthetic compensation failure"
            )
        return original_transition(*args, **kwargs)

    monkeypatch.setattr(
        generation, "transition_printable_response_issuance", fail_compensation
    )
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert result.failure_stage == "pdf_rendering"
    assert result.error == "primary render failure"
    assert len(result.warnings) == 2
    assert all("attempted invalidated" in warning for warning in result.warnings)
    assert all("primary stage pdf_rendering" in warning for warning in result.warnings)
    assert all("synthetic compensation failure" in warning for warning in result.warnings)


def test_temporary_cleanup_failure_is_reported_separately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    original_unlink = Path.unlink
    monkeypatch.setattr(
        generation,
        "render_printable_response_pdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            generation.PrintableResponseRenderError("primary render failure")
        ),
    )

    def fail_owned_temp_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path.name.endswith(".tmp.pdf"):
            raise OSError("synthetic temporary cleanup failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_owned_temp_unlink)
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert result.error == "primary render failure"
    assert any("Temporary cleanup failed" in warning for warning in result.warnings)
    assert any("synthetic temporary cleanup failure" in warning for warning in result.warnings)


def test_pdf_replace_failure_preserves_prior_output_and_invalidates_new_issuances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    output = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID).output_path
    output.parent.mkdir(parents=True)
    prior = b"prior packet"
    output.write_bytes(prior)
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    original_replace = generation.os.replace

    def fail_pdf_replace(source: Any, destination: Any) -> None:
        if str(source).endswith(".tmp.pdf"):
            raise OSError("synthetic replace failure")
        original_replace(source, destination)

    monkeypatch.setattr(generation.os, "replace", fail_pdf_replace)
    result = generate_printable_response_packet(plan, overwrite=True)
    assert not result.installed and result.failure_stage == "pdf_installation"
    assert output.read_bytes() == prior
    assert all(
        load_printable_response_issuance(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )


def test_initial_packet_and_regeneration_use_fresh_identity(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    first = generate_printable_response_packet(
        plan_printable_response_packet(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, pages_per_student=2
        )
    )
    first_pdf = first.output_path.read_bytes()
    first_routes = {
        path: path.read_bytes() for path in first.created_registration_paths
    }
    assert first.success
    second_plan = plan_printable_response_packet(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, pages_per_student=2
    )
    assert second_plan.predecessor_count == 2
    second = generate_printable_response_packet(second_plan, overwrite=True)
    assert second.success and second.replaced_existing
    assert first.generation_id != second.generation_id
    assert first.artifact_id != second.artifact_id
    assert set(first.issuance_ids).isdisjoint(second.issuance_ids)
    assert set(first.page_ids).isdisjoint(second.page_ids)
    assert set(first.route_ids).isdisjoint(second.route_ids)
    assert {path: path.read_bytes() for path in first_routes} == first_routes
    assert second.output_path.read_bytes() != first_pdf
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    assert all(
        load_printable_response_issuance(tmp_path, work_ref, issuance_id).lifecycle.status
        == "superseded"
        for issuance_id in first.issuance_ids
    )
    assert all(
        load_printable_response_issuance(tmp_path, work_ref, issuance_id).lifecycle.status
        == "issued"
        for issuance_id in second.issuance_ids
    )


def test_forged_predecessor_model_fails_artifact_preflight(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    packet_plan, artifact = artifact_plan(tmp_path)
    predecessor = artifact.predecessors[0]
    assert predecessor is not None
    forged = unsafe_replace(predecessor, class_label="forged")
    fabricated = replace(
        artifact,
        predecessors=(forged, artifact.predecessors[1]),
    )
    assert_artifact_preflight_failure(packet_plan, fabricated)


def test_predecessor_changed_after_artifact_planning_fails_before_mutation(
    tmp_path: Path,
) -> None:
    write_packet_workspace(tmp_path)
    generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    packet_plan, artifact = artifact_plan(tmp_path)
    predecessor = artifact.predecessors[0]
    assert predecessor is not None
    transition_printable_response_issuance(
        tmp_path,
        packet_plan.work_ref,
        predecessor.issuance_id,
        expected_revision=predecessor.lifecycle.revision,
        new_status="invalidated",
        timestamp="2035-01-01T00:00:00+00:00",
        reason="synthetic stale predecessor",
    )
    before = set(tmp_path.rglob("*"))
    with pytest.raises(PrintableResponseGenerationError, match="predecessor"):
        execute_printable_response_artifact(
            artifact,
            output_relative_path=artifact.output_relative_path,
            expected_output_digest=artifact.expected_output_digest,
            overwrite=True,
        )
    assert set(tmp_path.rglob("*")) == before
    assert not artifact.temporary_path.exists()


def test_result_construction_uses_validated_fields_after_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    assert isinstance(artifact.assignment, dict)
    assignment_mapping = cast(dict[str, Any], artifact.assignment)
    original_replace = generation.os.replace

    def install_then_clear_mapping(source: Any, destination: Any) -> None:
        original_replace(source, destination)
        if str(source).endswith(".tmp.pdf"):
            assignment_mapping.clear()

    monkeypatch.setattr(generation.os, "replace", install_then_clear_mapping)
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=artifact.output_relative_path,
        expected_output_digest=None,
        overwrite=False,
    )
    assert result.success and result.installed
    assert result.assignment_title == artifact.assignment_title
    assert result.pages_per_student == artifact.pages_per_student
    assert result.output_relative_path == artifact.output_relative_path


def test_missing_canonical_pdf_does_not_erase_regeneration_lineage(
    tmp_path: Path,
) -> None:
    write_packet_workspace(tmp_path)
    first = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    first.output_path.unlink()
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert not plan.target_exists and plan.predecessor_count == 2
    second = generate_printable_response_packet(plan)
    assert second.success and second.predecessor_count == 2
    assert second.superseded_predecessor_count == 2


def test_legacy_pdf_without_issuances_creates_initial_pds2_records(
    tmp_path: Path,
) -> None:
    write_packet_workspace(tmp_path)
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    plan.output_path.parent.mkdir(parents=True)
    plan.output_path.write_bytes(b"obsolete pre-PDS2 development packet")
    replacement = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert replacement.target_exists and replacement.predecessor_count == 0
    result = generate_printable_response_packet(replacement, overwrite=True)
    assert result.success and result.predecessor_count == 0
    assert result.superseded_predecessor_count == 0


def test_roster_transition_mixes_regeneration_and_initial_and_preserves_removed(
    tmp_path: Path,
) -> None:
    write_packet_workspace(tmp_path)
    first = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    write_class_roster(
        tmp_path,
        create_roster(
            CLASS_ID,
            [
                {
                    "student_id": "00107",
                    "last_name": "Zulu",
                    "first_name": "Avery",
                    "period": "3",
                },
                {
                    "student_id": "00003",
                    "last_name": "New",
                    "first_name": "Student",
                    "period": "3",
                },
            ],
        ),
        overwrite=True,
    )
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert plan.predecessor_count == 1
    assert plan.regeneration_issuance_count == 1
    assert plan.initial_issuance_count == 1
    result = generate_printable_response_packet(plan, overwrite=True)
    assert result.success and result.superseded_predecessor_count == 1
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    assert load_printable_response_issuance(
        tmp_path, work_ref, first.issuance_ids[0]
    ).lifecycle.status == "superseded"
    assert load_printable_response_issuance(
        tmp_path, work_ref, first.issuance_ids[1]
    ).lifecycle.status == "issued"


def test_predecessor_change_after_dry_plan_forces_replanning(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    stale = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    current = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    generate_printable_response_packet(current, overwrite=True)
    with pytest.raises(ValueError, match="lineage changed"):
        generate_printable_response_packet(stale, overwrite=True)


def test_dry_plan_never_calls_identity_generators(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert plan.planned_issuance_count == 2
    assert plan.planned_route_count == 2
    assert not plan.output_path.parent.exists()


def test_identity_collision_retries_before_mutation(tmp_path: Path) -> None:
    write_packet_workspace(tmp_path)
    values = iter(
        [
            "gen_0123456789abcdef0123456789abcdef",
            "art_0123456789abcdef0123456789abcdef",
            "iss_0123456789abcdef0123456789abcdef",
            "iss_0123456789abcdef0123456789abcdef",
            "iss_1123456789abcdef0123456789abcdef",
        ]
    )
    # Issuance collision is reserved and retried within the same artifact.
    generators = IdentityGenerators(
        generation=lambda: next(values),
        artifact=lambda: next(values),
        issuance=lambda: next(values),
    )
    # The remaining page/route generators retain secure defaults.
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID),
        generators=generators,
    )
    assert result.success
    assert result.issuance_ids == (
        "iss_0123456789abcdef0123456789abcdef",
        "iss_1123456789abcdef0123456789abcdef",
    )


@pytest.mark.parametrize(
    "family",
    ["generation", "artifact", "issuance", "page", "route"],
)
def test_historical_identity_family_collision_retries_with_fresh_id(
    tmp_path: Path, family: str
) -> None:
    write_packet_workspace(tmp_path)
    first = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    colliding = {
        "generation": first.generation_id,
        "artifact": first.artifact_id,
        "issuance": first.issuance_ids[0],
        "page": first.page_ids[0],
        "route": first.route_ids[0],
    }[family]
    prefix = {
        "generation": "gen",
        "artifact": "art",
        "issuance": "iss",
        "page": "pg",
        "route": "rt",
    }[family]
    values = iter(
        (
            colliding,
            f"{prefix}_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            f"{prefix}_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
    )
    generators = IdentityGenerators(**{family: lambda: next(values)})
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID),
        overwrite=True,
        generators=generators,
    )
    identities = {
        "generation": (result.generation_id,),
        "artifact": (result.artifact_id,),
        "issuance": result.issuance_ids,
        "page": result.page_ids,
        "route": result.route_ids,
    }[family]
    assert colliding not in identities
    assert identities[0] == f"{prefix}_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


@pytest.mark.parametrize(
    "family",
    ["generation", "artifact", "issuance", "page", "route"],
)
def test_identity_family_collision_exhaustion_is_nonmutating(
    tmp_path: Path, family: str
) -> None:
    write_packet_workspace(tmp_path)
    first = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    packet = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    predecessors = select_printable_response_predecessors(
        packet.workspace_root, packet.work_ref, packet.students
    )
    colliding = {
        "generation": first.generation_id,
        "artifact": first.artifact_id,
        "issuance": first.issuance_ids[0],
        "page": first.page_ids[0],
        "route": first.route_ids[0],
    }[family]
    kwargs: dict[str, Any] = {family: lambda: colliding}
    generators = IdentityGenerators(**kwargs)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    with pytest.raises(PrintableResponseGenerationError, match="fresh"):
        build_printable_response_artifact_plan(
            workspace_root=packet.workspace_root,
            work_ref=packet.work_ref,
            assignment=packet.assignment,
            students=packet.students,
            pages_per_student=1,
            output_path=packet.output_path,
            predecessors=predecessors,
            generators=generators,
            max_attempts=2,
        )
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("family", ["issuance", "page", "route"])
def test_current_artifact_collision_is_burned_and_retried(
    tmp_path: Path, family: str
) -> None:
    write_packet_workspace(tmp_path)
    prefixes = {"issuance": "iss", "page": "pg", "route": "rt"}
    prefix = prefixes[family]
    repeated = f"{prefix}_0123456789abcdef0123456789abcdef"
    fresh = f"{prefix}_1123456789abcdef0123456789abcdef"
    values = iter((repeated, repeated, fresh))
    kwargs: dict[str, Any] = {family: lambda: next(values)}
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID),
        generators=IdentityGenerators(**kwargs),
    )
    identities = {
        "issuance": result.issuance_ids,
        "page": result.page_ids,
        "route": result.route_ids,
    }[family]
    assert identities == (repeated, fresh)


def test_first_route_write_failure_cancels_all_issuances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    monkeypatch.setattr(
        route_service,
        "write_route_registration",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("synthetic first route failure")
        ),
    )
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert not result.installed
    assert result.created_route_count == 0
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    assert all(
        load_printable_response_issuance(tmp_path, work_ref, item).lifecycle.status
        == "cancelled"
        for item in result.issuance_ids
    )


def test_later_route_write_failure_invalidates_all_issuances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    original = route_service.write_route_registration
    calls = 0

    def fail_later(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic later route failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(route_service, "write_route_registration", fail_later)
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert result.created_route_count == 1
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    assert all(
        load_printable_response_issuance(tmp_path, work_ref, item).lifecycle.status
        == "invalidated"
        for item in result.issuance_ids
    )
    assert result.created_registration_paths[0].exists()


def test_route_write_that_creates_then_raises_invalidates_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    original = route_service.write_route_registration

    def write_then_raise(*args: Any, **kwargs: Any) -> Path:
        path = Path(original(*args, **kwargs))
        raise OSError(f"synthetic post-write failure at {path}")

    monkeypatch.setattr(route_service, "write_route_registration", write_then_raise)
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert result.failure_stage == "route_persistence"
    assert result.created_route_count == result.verified_route_count == 0
    assert result.created_registration_paths == ()
    assert all(
        load_printable_response_issuance(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )


def test_noncanonical_core_return_after_durable_creation_invalidates_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    original = route_service.write_route_registration

    def write_then_return_other(*args: Any, **kwargs: Any) -> Path:
        original(*args, **kwargs)
        return tmp_path / "noncanonical-return.json"

    monkeypatch.setattr(
        route_service, "write_route_registration", write_then_return_other
    )
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert result.failure_stage == "route_persistence" and not result.installed
    assert result.created_route_count == 1
    assert result.created_registration_paths[0].is_file()
    assert all(
        load_printable_response_issuance(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )
    assert not result.output_path.exists()


def test_noncanonical_core_return_without_durable_creation_cancels_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    monkeypatch.setattr(
        route_service,
        "write_route_registration",
        lambda *_args, **_kwargs: tmp_path / "noncanonical-return.json",
    )
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert result.failure_stage == "route_persistence" and not result.installed
    assert result.created_route_count == 0
    assert all(
        load_printable_response_issuance(
            tmp_path, quillan_work_ref(CLASS_ID, ASSIGNMENT_ID), issuance_id
        ).lifecycle.status
        == "cancelled"
        for issuance_id in result.issuance_ids
    )


def test_concurrent_exact_route_collision_invalidates_without_claiming_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    planned_route = artifact.route_sets[0][0]
    planned_path = generation.route_registration_path(
        tmp_path, planned_route.locator
    )
    original_persist = generation.persist_printable_response_route_set
    competing_bytes: list[bytes] = []

    def compete_then_persist(*args: Any, **kwargs: Any) -> Any:
        route_service.write_route_registration(args[0], planned_route.registration)
        competing_bytes.append(planned_path.read_bytes())
        return original_persist(*args, **kwargs)

    monkeypatch.setattr(
        generation, "persist_printable_response_route_set", compete_then_persist
    )
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=packet_plan.output_relative_path,
        expected_output_digest=packet_plan.output_sha256,
        overwrite=packet_plan.target_exists,
    )
    assert result.failure_stage == "route_persistence" and not result.installed
    assert result.created_route_count == 0
    assert competing_bytes and planned_path.read_bytes() == competing_bytes[0]
    assert any(str(planned_path) in warning for warning in result.warnings)
    assert all(
        load_printable_response_issuance(
            tmp_path, artifact.work_ref, issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )


def test_post_preflight_exclusive_route_collision_is_not_claimed_as_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    planned_route = artifact.route_sets[0][0]
    planned_path = generation.route_registration_path(
        tmp_path, planned_route.locator
    )
    core_write = route_service.write_route_registration
    competing_bytes: list[bytes] = []
    captured_errors: list[route_service.PrintableResponseRoutePersistenceError] = []

    def compete_during_core_write(*args: Any, **kwargs: Any) -> Path:
        core_write(*args, **kwargs)
        competing_bytes.append(planned_path.read_bytes())
        return cast(Path, core_write(*args, **kwargs))

    original_persist = generation.persist_printable_response_route_set

    def capture_route_error(*args: Any, **kwargs: Any) -> Any:
        try:
            return original_persist(*args, **kwargs)
        except route_service.PrintableResponseRoutePersistenceError as error:
            captured_errors.append(error)
            raise

    monkeypatch.setattr(
        route_service, "write_route_registration", compete_during_core_write
    )
    monkeypatch.setattr(
        generation, "persist_printable_response_route_set", capture_route_error
    )
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=packet_plan.output_relative_path,
        expected_output_digest=packet_plan.output_sha256,
        overwrite=packet_plan.target_exists,
    )
    assert result.failure_stage == "route_persistence" and not result.installed
    assert result.created_route_count == result.verified_route_count == 0
    assert result.created_registration_paths == ()
    assert competing_bytes and planned_path.read_bytes() == competing_bytes[0]
    assert captured_errors and captured_errors[0].current_path == planned_path
    assert captured_errors[0].created_paths == ()
    assert captured_errors[0].verified_routes == ()
    assert captured_errors[0].failed_page_id == planned_route.page.page_id
    assert any(str(planned_path) in warning for warning in result.warnings)
    assert all(
        load_printable_response_issuance(
            tmp_path, artifact.work_ref, issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )
    assert not result.output_path.exists()


def test_concurrent_wrong_type_route_destination_invalidates_and_preserves_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    planned_route = artifact.route_sets[0][0]
    planned_path = generation.route_registration_path(
        tmp_path, planned_route.locator
    )
    original_persist = generation.persist_printable_response_route_set

    def compete_then_persist(*args: Any, **kwargs: Any) -> Any:
        planned_path.mkdir(parents=True)
        return original_persist(*args, **kwargs)

    monkeypatch.setattr(
        generation, "persist_printable_response_route_set", compete_then_persist
    )
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=packet_plan.output_relative_path,
        expected_output_digest=packet_plan.output_sha256,
        overwrite=packet_plan.target_exists,
    )
    assert result.failure_stage == "route_persistence" and not result.installed
    assert result.created_route_count == 0 and planned_path.is_dir()
    assert any(str(planned_path) in warning for warning in result.warnings)
    assert all(
        load_printable_response_issuance(
            tmp_path, artifact.work_ref, issuance_id
        ).lifecycle.status
        == "invalidated"
        for issuance_id in result.issuance_ids
    )


def _replace_temporary_after_routes(
    monkeypatch: pytest.MonkeyPatch,
    artifact: PrintableResponseArtifactPlan,
    replacement: Any,
) -> list[bool]:
    original = generation.persist_printable_response_route_set
    calls = 0
    replaced: list[bool] = []

    def persist_then_replace(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if calls == len(artifact.route_sets):
            artifact.temporary_path.unlink()
            replacement(artifact.temporary_path)
            replaced.append(True)
        return result

    monkeypatch.setattr(
        generation, "persist_printable_response_route_set", persist_then_replace
    )
    return replaced


def test_temporary_replacement_before_render_is_preserved_and_not_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    competing = b"competing temporary before render"
    replaced = _replace_temporary_after_routes(
        monkeypatch, artifact, lambda path: path.write_bytes(competing)
    )
    renderer_called = False

    def unexpected_renderer(*_args: Any, **_kwargs: Any) -> None:
        nonlocal renderer_called
        renderer_called = True

    monkeypatch.setattr(generation, "render_printable_response_pdf", unexpected_renderer)
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=packet_plan.output_relative_path,
        expected_output_digest=packet_plan.output_sha256,
        overwrite=packet_plan.target_exists,
    )
    assert replaced and not renderer_called and not result.installed
    assert result.failure_stage == "pdf_rendering"
    assert artifact.temporary_path.read_bytes() == competing
    assert "ownership was lost" in (result.error or "")
    assert any("preserved an entry" in warning for warning in result.warnings)


@pytest.mark.parametrize("replacement_kind", ["directory", "symlink"])
def test_wrong_type_temporary_replacement_before_render_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement_kind: str,
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    link_target = tmp_path / "competing-link-target.txt"
    link_target.write_bytes(b"external competing target")

    def replace_path(path: Path) -> None:
        if replacement_kind == "directory":
            path.mkdir()
            return
        try:
            path.symlink_to(link_target)
        except OSError as error:
            pytest.skip(f"symlink creation unavailable: {error}")

    _replace_temporary_after_routes(monkeypatch, artifact, replace_path)
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=packet_plan.output_relative_path,
        expected_output_digest=packet_plan.output_sha256,
        overwrite=packet_plan.target_exists,
    )
    assert result.failure_stage == "pdf_rendering" and not result.installed
    assert artifact.temporary_path.exists()
    assert artifact.temporary_path.is_dir() if replacement_kind == "directory" else artifact.temporary_path.is_symlink()
    assert any("preserved an entry" in warning for warning in result.warnings)


def test_temporary_replacement_after_render_is_preserved_before_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    original = generation.render_printable_response_pdf
    competing = b"competing temporary after render"

    def render_then_replace(*args: Any, **kwargs: Any) -> Any:
        rendered = original(*args, **kwargs)
        artifact.temporary_path.unlink()
        artifact.temporary_path.write_bytes(competing)
        return rendered

    monkeypatch.setattr(generation, "render_printable_response_pdf", render_then_replace)
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=packet_plan.output_relative_path,
        expected_output_digest=packet_plan.output_sha256,
        overwrite=packet_plan.target_exists,
    )
    assert result.failure_stage == "pdf_rendering" and not result.installed
    assert artifact.temporary_path.read_bytes() == competing
    assert any("preserved an entry" in warning for warning in result.warnings)


def test_primary_render_failure_retained_when_temporary_ownership_is_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    packet_plan, artifact = artifact_plan(tmp_path)
    competing = b"competing replacement during failed render"

    def replace_then_fail(*_args: Any, **_kwargs: Any) -> None:
        artifact.temporary_path.unlink()
        artifact.temporary_path.write_bytes(competing)
        raise generation.PrintableResponseRenderError("synthetic primary render failure")

    monkeypatch.setattr(generation, "render_printable_response_pdf", replace_then_fail)
    result = execute_printable_response_artifact(
        artifact,
        output_relative_path=packet_plan.output_relative_path,
        expected_output_digest=packet_plan.output_sha256,
        overwrite=packet_plan.target_exists,
    )
    assert result.error == "synthetic primary render failure"
    assert artifact.temporary_path.read_bytes() == competing
    assert any("preserved an entry" in warning for warning in result.warnings)


def test_concurrent_output_change_prevents_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    original = generation.render_printable_response_pdf
    concurrent = b"concurrent teacher output"

    def render_then_compete(
        workspace_root: Any, work_ref: Any, destination: Any, packets: Any
    ) -> Path:
        rendered = Path(original(workspace_root, work_ref, destination, packets))
        Path(destination).parent.joinpath("printable_response_pages.pdf").write_bytes(
            concurrent
        )
        return rendered

    monkeypatch.setattr(generation, "render_printable_response_pdf", render_then_compete)
    result = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    assert not result.installed
    assert result.failure_stage == "pdf_installation"
    assert result.output_path.read_bytes() == concurrent


@pytest.mark.parametrize("mode", ["deletion", "replacement"])
def test_concurrent_existing_output_change_preserves_competing_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    write_packet_workspace(tmp_path)
    output = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID).output_path
    output.parent.mkdir(parents=True)
    output.write_bytes(b"planned prior output")
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    original = generation.render_printable_response_pdf

    def render_then_change(root: Any, work: Any, destination: Any, packets: Any) -> Path:
        rendered = Path(original(root, work, destination, packets))
        output.unlink()
        if mode == "replacement":
            output.write_bytes(b"competing replacement")
        return rendered

    monkeypatch.setattr(generation, "render_printable_response_pdf", render_then_change)
    result = generate_printable_response_packet(plan, overwrite=True)
    assert not result.installed and result.failure_stage == "pdf_installation"
    if mode == "deletion":
        assert not output.exists()
    else:
        assert output.read_bytes() == b"competing replacement"


def test_predecessor_supersession_failure_is_installed_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    first = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    original = generation.transition_printable_response_issuance

    def fail_one_predecessor(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("new_status") == "superseded" and args[2] == first.issuance_ids[0]:
            raise OSError("synthetic supersession failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        generation, "transition_printable_response_issuance", fail_one_predecessor
    )
    result = generate_printable_response_packet(plan, overwrite=True)
    assert result.installed and result.partial_success and not result.success
    assert result.failure_stage == "predecessor_supersession"
    assert result.failed_predecessor_ids == (first.issuance_ids[0],)


def test_later_predecessor_supersession_failure_reports_exact_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packet_workspace(tmp_path)
    first = generate_printable_response_packet(
        plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    plan = plan_printable_response_packet(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    original = generation.transition_printable_response_issuance

    def fail_second_predecessor(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("new_status") == "superseded" and args[2] == first.issuance_ids[1]:
            raise generation.PrintableResponsePersistenceError(
                "synthetic later supersession failure"
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(
        generation, "transition_printable_response_issuance", fail_second_predecessor
    )
    result = generate_printable_response_packet(plan, overwrite=True)
    assert result.installed and not result.success
    assert result.failure_stage == "predecessor_supersession"
    assert result.failed_predecessor_ids == (first.issuance_ids[1],)
    assert result.superseded_predecessor_count == 1

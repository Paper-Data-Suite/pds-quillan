"""Tests for append-only Quillan post-dispatch resolutions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
import json
import inspect
import os
from pathlib import Path
import subprocess
from typing import cast
from types import SimpleNamespace

import pytest

from quillan.cli import main
from quillan.assignment_submission_assembly import (
    AssignmentSubmissionAssemblyResult,
    assemble_assignment_submissions,
)
from quillan.atomic_record_io import (
    AtomicRecordDurabilityError,
    AtomicRecordResult,
    create_exclusive_record,
)
import quillan.cli_app.handlers.scan_review as cli_scan_review
import quillan.post_dispatch_review as post_dispatch_review
import quillan.post_dispatch_review_resolution as resolution_service
import quillan.work_paths as work_paths
from quillan.post_dispatch_review import (
    PersistedPostDispatchReviewOccurrence,
    create_post_dispatch_review_occurrence,
)
from quillan.post_dispatch_review_resolution import (
    POST_DISPATCH_GENERIC_RESOLUTION_ACTIONS,
    PostDispatchReviewResolutionError,
    discover_post_dispatch_review_items,
    open_post_dispatch_possible_path,
    resolve_post_dispatch_after_successful_retry,
    resolve_post_dispatch_review_occurrence,
)
from quillan.response_page_observation_persistence import (
    persist_quillan_page_observation,
)
from quillan.submission_observation_assembly import QuillanSubmissionAssemblyFailure
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)
from quillan.submission_manifest import load_submission_manifest
from quillan.work_paths import quillan_work_ref
from tests.observation_test_support import successful_image_page, successful_pdf_pages

CLASS_ID = "english12_p3"
ASSIGNMENT_ID = "essay_01"


def _occurrence(
    root: Path, *, assignment_id: str = ASSIGNMENT_ID
) -> PersistedPostDispatchReviewOccurrence:
    return create_post_dispatch_review_occurrence(
        root,
        quillan_work_ref(CLASS_ID, assignment_id),
        category="submission_assembly",
        stage="submission_assembly",
        failure_message="Synthetic manifest conflict.",
        student_id="student_01",
        issuance_id="iss_" + "a" * 32,
        page_id="pg_" + "b" * 32,
        observation_id="obs_" + "c" * 32,
        source_scan_id="scan_01",
        source_page_number=1,
        created_at="2026-07-21T12:00:00+00:00",
    )


def _manifest_occurrence(
    root: Path,
) -> tuple[PersistedPostDispatchReviewOccurrence, Path]:
    manifest_path = submission_manifest_path(
        root, CLASS_ID, ASSIGNMENT_ID, "student_01"
    )
    write_submission_manifest(
        manifest_path,
        {
            "schema_version": "1",
            "module": "quillan",
            "record_type": "submission_manifest",
            "class_id": CLASS_ID,
            "assignment_id": ASSIGNMENT_ID,
            "student_id": "student_01",
            "expected_pages": 1,
            "submission_state": "unreviewed",
            "pages": [],
            "created_at": "2026-07-21T12:00:00+00:00",
            "updated_at": "2026-07-21T12:00:00+00:00",
            "module_details": {},
        },
    )
    occurrence = create_post_dispatch_review_occurrence(
        root,
        quillan_work_ref(CLASS_ID, ASSIGNMENT_ID),
        category="manifest_conflict",
        stage="submission_assembly",
        failure_message="Synthetic manifest conflict.",
        student_id="student_01",
        possible_manifest_path=manifest_path,
        created_at="2026-07-21T12:00:01+00:00",
    )
    return occurrence, manifest_path


@pytest.mark.parametrize("action", POST_DISPATCH_GENERIC_RESOLUTION_ACTIONS)
def test_each_action_appends_quillan_owned_resolution(
    tmp_path: Path, action: str
) -> None:
    occurrence = _occurrence(tmp_path)
    before = occurrence.path.read_bytes()

    result = resolve_post_dispatch_review_occurrence(
        tmp_path,
        occurrence.work_ref,
        occurrence.occurrence.failure_id,
        action=action,
        message="Teacher decision." if action == "other" else None,
        resolved_at=datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc),
        resolution_id=f"resolution_{action}",
    )

    data = json.loads(result.path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1"
    assert data["record_type"] == "post_dispatch_review_resolution"
    assert data["module_id"] == "quillan"
    assert data["failure_id"] == occurrence.occurrence.failure_id
    assert data["occurrence_path"] == occurrence.relative_path
    assert data["status"] == ("deferred" if action == "deferred" else "resolved")
    assert occurrence.path.read_bytes() == before
    assert not (tmp_path / "scans" / "resolutions").exists()


def _retry_case(
    root: Path,
    *,
    status: str = "created",
) -> tuple[PersistedPostDispatchReviewOccurrence, AssignmentSubmissionAssemblyResult]:
    if status == "updated":
        first_outcome, second_outcome = successful_pdf_pages(root)
        persisted = persist_quillan_page_observation(root, first_outcome)
    else:
        second_outcome = None
        persisted = persist_quillan_page_observation(
            root, successful_image_page(root)
        )
    observation = persisted.observation
    occurrence = create_post_dispatch_review_occurrence(
        root,
        quillan_work_ref(observation.class_id, observation.assignment_id),
        category="submission_assembly",
        stage="submission_assembly",
        failure_message="Synthetic retry target.",
        student_id=observation.student_id,
        issuance_id=observation.issuance_id,
        created_at="2026-07-21T12:00:00+00:00",
    )
    result = assemble_assignment_submissions(
        root, observation.class_id, observation.assignment_id
    )
    if status == "unchanged":
        result = assemble_assignment_submissions(
            root, observation.class_id, observation.assignment_id
        )
    elif status == "updated":
        assert second_outcome is not None
        persist_quillan_page_observation(root, second_outcome)
        result = assemble_assignment_submissions(
            root, observation.class_id, observation.assignment_id
        )
    assert result.assembled[0].status == status
    return occurrence, result


def test_generic_resolution_api_cannot_write_resolved_after_retry(
    tmp_path: Path,
) -> None:
    occurrence, _assembly = _retry_case(tmp_path)
    assert "retry_provenance" not in inspect.signature(
        resolve_post_dispatch_review_occurrence
    ).parameters
    with pytest.raises(PostDispatchReviewResolutionError, match="Unsupported"):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="resolved_after_retry",
        )
    with pytest.raises(TypeError):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="resolved_after_retry",
            retry_provenance={"result_status": "success"},  # type: ignore[call-arg]
        )

    assert not hasattr(resolution_service, "_PostDispatchRetryProvenance")
    assert "PostDispatchRetryProvenance" not in resolution_service.__all__
    assert not hasattr(resolution_service, "_create")


def _assembly_failure(
    assembly: AssignmentSubmissionAssemblyResult,
    *,
    student_id: str,
    issuance_id: str,
) -> QuillanSubmissionAssemblyFailure:
    return QuillanSubmissionAssemblyFailure(
        category="unexpected_error",
        class_id=assembly.class_id,
        assignment_id=assembly.assignment_id,
        student_id=student_id,
        issuance_ids=(issuance_id,),
        observation_ids=(),
        page_ids=(),
        logical_pages=(),
        source_scan_ids=(),
        source_page_numbers=(),
        reason="Synthetic relevant failure.",
    )


def test_empty_retry_result_does_not_prove_resolution(tmp_path: Path) -> None:
    occurrence, assembly = _retry_case(tmp_path)
    empty = replace(
        assembly,
        written_manifests=(),
        student_summaries=(),
        assembled=(),
    )
    with pytest.raises(PostDispatchReviewResolutionError, match="does not prove"):
        resolve_post_dispatch_after_successful_retry(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            assembly_result=empty,
            completed_at="2026-07-21T13:00:00.000000+00:00",
        )


def test_unrelated_student_or_issuance_does_not_prove_resolution(
    tmp_path: Path,
) -> None:
    _occurrence_value, assembly = _retry_case(tmp_path)
    assembled = assembly.assembled[0]
    for student_id, issuance_id in (
        ("other_student", assembled.issuance_id),
        (assembled.student_id, "iss_" + "f" * 32),
    ):
        occurrence = create_post_dispatch_review_occurrence(
            tmp_path,
            quillan_work_ref(assembled.class_id, assembled.assignment_id),
            category="submission_assembly",
            stage="submission_assembly",
            failure_message="Unrelated retry target.",
            student_id=student_id,
            issuance_id=issuance_id,
        )
        with pytest.raises(PostDispatchReviewResolutionError, match="does not prove"):
            resolve_post_dispatch_after_successful_retry(
                tmp_path,
                occurrence.work_ref,
                occurrence.occurrence.failure_id,
                assembly_result=assembly,
                completed_at="2026-07-21T13:00:00.000000+00:00",
            )


def test_matching_student_or_issuance_failure_blocks_retry_proof(
    tmp_path: Path,
) -> None:
    occurrence, assembly = _retry_case(tmp_path)
    assembled = assembly.assembled[0]
    failures = (
        _assembly_failure(
            assembly,
            student_id=assembled.student_id,
            issuance_id="iss_" + "e" * 32,
        ),
        _assembly_failure(
            assembly,
            student_id="other_student",
            issuance_id=assembled.issuance_id,
        ),
    )
    for failure in failures:
        contradictory = replace(assembly, failures=(failure,))
        with pytest.raises(PostDispatchReviewResolutionError, match="does not prove"):
            resolve_post_dispatch_after_successful_retry(
                tmp_path,
                occurrence.work_ref,
                occurrence.occurrence.failure_id,
                assembly_result=contradictory,
                completed_at="2026-07-21T13:00:00.000000+00:00",
            )


def test_missing_or_contradictory_manifest_blocks_retry_proof(tmp_path: Path) -> None:
    occurrence, assembly = _retry_case(tmp_path)
    manifest_path = assembly.assembled[0].manifest_path
    original = manifest_path.read_bytes()
    manifest_path.unlink()
    with pytest.raises(PostDispatchReviewResolutionError, match="does not prove"):
        resolve_post_dispatch_after_successful_retry(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            assembly_result=assembly,
            completed_at="2026-07-21T13:00:00.000000+00:00",
        )
    manifest_path.write_bytes(original)
    manifest = load_submission_manifest(manifest_path)
    manifest["module_details"]["assembly_revision"] += 1
    write_submission_manifest(manifest_path, manifest, overwrite=True)
    with pytest.raises(PostDispatchReviewResolutionError, match="does not prove"):
        resolve_post_dispatch_after_successful_retry(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            assembly_result=assembly,
            completed_at="2026-07-21T13:00:00.000000+00:00",
        )


@pytest.mark.parametrize("status", ["created", "updated", "unchanged"])
def test_exact_retry_create_update_and_unchanged_are_proven(
    tmp_path: Path, status: str
) -> None:
    occurrence, assembly = _retry_case(tmp_path, status=status)
    assembled = assembly.assembled[0]
    result = resolve_post_dispatch_after_successful_retry(
        tmp_path,
        occurrence.work_ref,
        occurrence.occurrence.failure_id,
        assembly_result=assembly,
        completed_at="2026-07-21T13:00:00.000000+00:00",
        resolved_at="2026-07-21T13:00:01.000000+00:00",
    )
    provenance = result.resolution.retry_provenance
    assert provenance is not None
    assert provenance["assembled_status"] == status
    assert provenance["manifest_path"] == assembled.manifest_relative_path
    assert provenance["assembly_revision"] == assembled.assembly_revision


def test_successful_retry_and_loaded_history_cannot_be_reused(
    tmp_path: Path,
) -> None:
    first, assembly = _retry_case(tmp_path)
    assembled = assembly.assembled[0]
    second = create_post_dispatch_review_occurrence(
        tmp_path,
        first.work_ref,
        category="submission_assembly",
        stage="submission_assembly",
        failure_message="Second occurrence for the same retry target.",
        student_id=assembled.student_id,
        issuance_id=assembled.issuance_id,
        created_at="2026-07-21T12:00:01+00:00",
    )
    resolve_post_dispatch_after_successful_retry(
        tmp_path,
        first.work_ref,
        first.occurrence.failure_id,
        assembly_result=assembly,
        completed_at="2026-07-21T13:00:00.000000+00:00",
        resolved_at="2026-07-21T13:00:01.000000+00:00",
    )
    loaded = discover_post_dispatch_review_items(
        tmp_path, first.work_ref, include_resolved=True
    )
    historical = next(
        item.latest_resolution.resolution.retry_provenance
        for item in loaded.items
        if item.occurrence.occurrence.failure_id == first.occurrence.failure_id
        and item.latest_resolution is not None
    )
    assert historical is not None
    with pytest.raises(TypeError):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            second.work_ref,
            second.occurrence.failure_id,
            action="resolved_after_retry",
            retry_provenance=historical,  # type: ignore[call-arg]
        )
    with pytest.raises(PostDispatchReviewResolutionError, match="already authorized"):
        resolve_post_dispatch_after_successful_retry(
            tmp_path,
            second.work_ref,
            second.occurrence.failure_id,
            assembly_result=assembly,
            completed_at="2026-07-21T13:00:00.000000+00:00",
            resolved_at="2026-07-21T13:00:02.000000+00:00",
        )


def test_resolved_hidden_deferred_visible_and_latest_is_deterministic(
    tmp_path: Path,
) -> None:
    occurrence = _occurrence(tmp_path)
    resolve_post_dispatch_review_occurrence(
        tmp_path,
        occurrence.work_ref,
        occurrence.occurrence.failure_id,
        action="deferred",
        resolved_at="2026-07-21T13:00:00+00:00",
        resolution_id="resolution_deferred",
    )
    deferred = discover_post_dispatch_review_items(tmp_path, occurrence.work_ref)
    assert deferred.items[0].display_status == "deferred"

    resolve_post_dispatch_review_occurrence(
        tmp_path,
        occurrence.work_ref,
        occurrence.occurrence.failure_id,
        action="rescan_needed",
        resolved_at="2026-07-21T14:00:00+00:00",
        resolution_id="resolution_resolved",
    )
    assert discover_post_dispatch_review_items(tmp_path, occurrence.work_ref).items == ()
    included = discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref, include_resolved=True
    )
    assert included.items[0].latest_resolution is not None
    assert included.items[0].latest_resolution.resolution.action == "rescan_needed"


def test_resolution_rejects_cross_work_and_duplicate_id(tmp_path: Path) -> None:
    occurrence = _occurrence(tmp_path)
    with pytest.raises(PostDispatchReviewResolutionError, match="No unique"):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            quillan_work_ref(CLASS_ID, "other_assignment"),
            occurrence.occurrence.failure_id,
            action="cannot_recover",
        )
    resolve_post_dispatch_review_occurrence(
        tmp_path,
        occurrence.work_ref,
        occurrence.occurrence.failure_id,
        action="cannot_recover",
        resolution_id="resolution_fixed",
    )
    with pytest.raises(PostDispatchReviewResolutionError, match="already exists"):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="rescan_needed",
            resolution_id="resolution_fixed",
        )


def test_other_requires_message_and_malformed_resolution_warns(tmp_path: Path) -> None:
    occurrence = _occurrence(tmp_path)
    with pytest.raises(PostDispatchReviewResolutionError, match="requires"):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="other",
        )
    directory = occurrence.path.parent / "resolutions"
    directory.mkdir()
    (directory / "malformed.json").write_text("{bad", encoding="utf-8")
    discovery = discover_post_dispatch_review_items(tmp_path, occurrence.work_ref)
    assert len(discovery.items) == 1
    assert len(discovery.warnings) == 1


def test_resolution_with_unknown_field_is_reported_as_malformed(
    tmp_path: Path,
) -> None:
    occurrence = _occurrence(tmp_path)
    persisted = resolve_post_dispatch_review_occurrence(
        tmp_path,
        occurrence.work_ref,
        occurrence.occurrence.failure_id,
        action="record_corrected",
    )
    value = json.loads(persisted.path.read_text(encoding="utf-8"))
    value["unknown_field"] = True
    persisted.path.write_text(json.dumps(value), encoding="utf-8")

    discovery = discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref, include_resolved=True
    )

    assert discovery.items[0].latest_resolution is None
    assert len(discovery.warnings) == 1
    assert "fields are not exact" in discovery.warnings[0]


def test_direct_commands_list_and_resolve_exact_work_occurrence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence = _occurrence(tmp_path)
    before = occurrence.path.read_bytes()
    monkeypatch.setattr(cli_scan_review, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        ["list-post-dispatch-review", CLASS_ID, ASSIGNMENT_ID]
    ) == 0
    listed = capsys.readouterr().out
    assert occurrence.occurrence.failure_id in listed
    assert "submission_assembly" in listed

    assert main(
        [
            "resolve-post-dispatch-review",
            CLASS_ID,
            ASSIGNMENT_ID,
            occurrence.occurrence.failure_id,
            "--action",
            "record_corrected",
        ]
    ) == 0
    resolved = capsys.readouterr().out
    assert "Post-dispatch review item resolved." in resolved
    assert "/scans/review/post_dispatch/resolutions/" in resolved
    assert occurrence.path.read_bytes() == before


def test_generic_direct_cli_rejects_resolved_after_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    occurrence = _occurrence(tmp_path)
    monkeypatch.setattr(cli_scan_review, "resolve_workspace_root", lambda: tmp_path)
    with pytest.raises(SystemExit) as captured:
        main(
            [
                "resolve-post-dispatch-review",
                CLASS_ID,
                ASSIGNMENT_ID,
                occurrence.occurrence.failure_id,
                "--action",
                "resolved_after_retry",
            ]
        )
    assert captured.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert not occurrence.path.parent.joinpath("resolutions").exists()


def test_resolution_models_are_deeply_immutable_and_reject_corruption(
    tmp_path: Path,
) -> None:
    occurrence = _occurrence(tmp_path)
    persisted = resolve_post_dispatch_review_occurrence(
        tmp_path,
        occurrence.work_ref,
        occurrence.occurrence.failure_id,
        action="record_corrected",
        resolved_at="2026-07-21T13:00:00.000000+00:00",
    )
    nested = replace(
        persisted.resolution,
        module_details={"nested": {"items": ["one", {"two": [2]}]}},
    )
    nested_mapping = cast(Mapping[str, object], nested.module_details["nested"])
    nested_items = cast(tuple[object, ...], nested_mapping["items"])
    assert nested_items[0] == "one"
    assert cast(Mapping[str, object], nested_items[1])["two"] == (2,)
    with pytest.raises(TypeError):
        nested_mapping["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        nested.occurrence_identity_snapshot["issuance_ids"] = ()  # type: ignore[index]
    with pytest.raises(PostDispatchReviewResolutionError):
        replace(persisted.resolution, status="deferred")
    with pytest.raises(PostDispatchReviewResolutionError, match="canonical occurrence"):
        replace(persisted.resolution, occurrence_path="wrong/occurrence.json")
    with pytest.raises(PostDispatchReviewResolutionError, match="category"):
        replace(
            persisted.resolution,
            occurrence_identity_snapshot={
                **dict(persisted.resolution.occurrence_identity_snapshot),
                "category": "invented_category",
            },
        )
    with pytest.raises(PostDispatchReviewResolutionError):
        replace(persisted, relative_path="wrong/path.json")


@pytest.mark.parametrize("replacement", ["directory", "deleted", "changed"])
def test_occurrence_is_repreflighted_after_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement: str,
) -> None:
    occurrence = _occurrence(tmp_path)
    discovery = post_dispatch_review.discover_post_dispatch_review_occurrences(
        tmp_path, occurrence.work_ref
    )
    if replacement == "directory":
        occurrence.path.unlink()
        occurrence.path.mkdir()
    elif replacement == "deleted":
        occurrence.path.unlink()
    else:
        occurrence.path.write_bytes(b"changed after discovery")
    monkeypatch.setattr(
        resolution_service,
        "discover_post_dispatch_review_occurrences",
        lambda *_args, **_kwargs: discovery,
    )
    called = False

    def forbidden_writer(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True
        pytest.fail("resolution writer must not run after occurrence preflight fails")

    monkeypatch.setattr(
        "quillan.post_dispatch_review_resolution.create_exclusive_record",
        forbidden_writer,
    )
    with pytest.raises(PostDispatchReviewResolutionError):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="record_corrected",
        )
    assert called is False


def test_occurrence_replaced_by_symlink_is_rejected_before_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    occurrence = _occurrence(tmp_path)
    discovery = post_dispatch_review.discover_post_dispatch_review_occurrences(
        tmp_path, occurrence.work_ref
    )
    monkeypatch.setattr(
        resolution_service,
        "discover_post_dispatch_review_occurrences",
        lambda *_args, **_kwargs: discovery,
    )
    monkeypatch.setattr(
        "quillan.post_dispatch_review_resolution._is_link_like",
        lambda path: path == occurrence.path,
    )
    with pytest.raises(PostDispatchReviewResolutionError, match="symlink|non-link"):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="record_corrected",
        )


def test_no_occurrence_read_when_link_preflight_rejects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    occurrence = _occurrence(tmp_path)
    discovery = post_dispatch_review.discover_post_dispatch_review_occurrences(
        tmp_path, occurrence.work_ref
    )
    monkeypatch.setattr(
        resolution_service,
        "discover_post_dispatch_review_occurrences",
        lambda *_args, **_kwargs: discovery,
    )
    monkeypatch.setattr(
        resolution_service,
        "_is_link_like",
        lambda path: path == occurrence.path,
    )
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path == occurrence.path:
            pytest.fail("occurrence bytes were read after link preflight rejected it")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    with pytest.raises(PostDispatchReviewResolutionError, match="non-link"):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="record_corrected",
        )


@pytest.mark.parametrize("replacement", ["file", "link_like"])
def test_resolution_directory_wrong_type_or_link_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement: str,
) -> None:
    occurrence = _occurrence(tmp_path)
    directory = occurrence.path.parent / "resolutions"
    if replacement == "file":
        directory.write_text("wrong type", encoding="utf-8")
    else:
        directory.mkdir()
        original_link_check = getattr(work_paths, "_is_link_like")
        monkeypatch.setattr(
            work_paths,
            "_is_link_like",
            lambda path: path == directory or original_link_check(path),
        )
    with pytest.raises(PostDispatchReviewResolutionError):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="record_corrected",
        )


def _create_windows_junction(link: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.fail(
            "Could not create the required Windows junction fixture: "
            f"{completed.stderr or completed.stdout}"
        )


def test_occurrence_parent_windows_junction_is_rejected(
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        return
    occurrence = _occurrence(tmp_path)
    directory = occurrence.path.parent
    junction_target = tmp_path / "junction-target-occurrences"
    directory.rename(junction_target)
    _create_windows_junction(directory, junction_target)
    try:
        with pytest.raises(PostDispatchReviewResolutionError, match="junction"):
            resolve_post_dispatch_review_occurrence(
                tmp_path,
                occurrence.work_ref,
                occurrence.occurrence.failure_id,
                action="record_corrected",
            )
    finally:
        os.rmdir(directory)
        junction_target.rename(directory)


def test_resolution_directory_windows_junction_is_rejected(
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        return
    occurrence = _occurrence(tmp_path)
    directory = occurrence.path.parent / "resolutions"
    junction_target = tmp_path / "junction-target-resolutions"
    _create_windows_junction(directory, junction_target)
    try:
        with pytest.raises(PostDispatchReviewResolutionError, match="junction"):
            resolve_post_dispatch_review_occurrence(
                tmp_path,
                occurrence.work_ref,
                occurrence.occurrence.failure_id,
                action="record_corrected",
            )
    finally:
        os.rmdir(directory)


def test_link_like_resolution_child_is_rejected_before_atomic_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    occurrence = _occurrence(tmp_path)
    resolution_id = "resolution_link_like"
    target = occurrence.path.parent / "resolutions" / f"{resolution_id}.json"
    original_link_check = getattr(work_paths, "_is_link_like")
    monkeypatch.setattr(
        work_paths,
        "_is_link_like",
        lambda path: path == target or original_link_check(path),
    )
    with pytest.raises(PostDispatchReviewResolutionError, match="symlink|junction"):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="record_corrected",
            resolution_id=resolution_id,
        )


def test_occurrence_revision_race_immediately_before_atomic_installation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    occurrence = _occurrence(tmp_path)
    real_writer = create_exclusive_record

    def racing_writer(
        path: Path,
        replacement_bytes: bytes,
        *,
        preflight: Callable[[], None],
        verify_bytes: Callable[[bytes], None],
    ) -> AtomicRecordResult:
        occurrence.path.write_bytes(b"raced")
        return real_writer(
            path,
            replacement_bytes,
            preflight=preflight,
            verify_bytes=verify_bytes,
        )

    monkeypatch.setattr(
        "quillan.post_dispatch_review_resolution.create_exclusive_record",
        racing_writer,
    )
    with pytest.raises(PostDispatchReviewResolutionError, match="changed"):
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="record_corrected",
        )
    assert not tuple(occurrence.path.parent.joinpath("resolutions").glob("*.json"))


def test_resolution_durability_and_lock_paths_are_propagated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    occurrence = _occurrence(tmp_path)
    durable_path = occurrence.path.parent / "resolutions" / "possibly.json"
    lock_path = occurrence.path.parent / "resolutions" / ".possibly.lock"

    def durability_failure(*_args: object, **_kwargs: object) -> None:
        raise AtomicRecordDurabilityError(
            "durability uncertain",
            possibly_durable_path=durable_path,
            possible_lock_path=lock_path,
        )

    monkeypatch.setattr(resolution_service, "create_exclusive_record", durability_failure)
    with pytest.raises(PostDispatchReviewResolutionError) as captured:
        resolve_post_dispatch_review_occurrence(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            action="record_corrected",
        )
    assert captured.value.possibly_durable_path == durable_path
    assert captured.value.possible_lock_path == lock_path


def test_contextual_manifest_opening_is_occurrence_and_work_scoped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    occurrence, manifest_path = _manifest_occurrence(tmp_path)
    monkeypatch.setattr(resolution_service, "open_local_path", lambda path: path)
    relative = manifest_path.relative_to(tmp_path).as_posix()

    opened = open_post_dispatch_possible_path(
        tmp_path,
        occurrence.work_ref,
        occurrence.occurrence.failure_id,
        kind="manifest",
        relative_path=relative,
    )
    assert opened.path == manifest_path
    assert opened.relative_path == relative
    assert discover_post_dispatch_review_items(
        tmp_path, occurrence.work_ref
    ).items

    for substitution in (
        relative.replace(ASSIGNMENT_ID, "other_assignment", 1),
        relative.replace("/modules/quillan/", "/modules/scoreform/", 1),
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/student_01/submission.json",
    ):
        with pytest.raises(PostDispatchReviewResolutionError, match="not stored"):
            open_post_dispatch_possible_path(
                tmp_path,
                occurrence.work_ref,
                occurrence.occurrence.failure_id,
                kind="manifest",
                relative_path=substitution,
            )


def test_contextual_manifest_opening_rejects_stale_and_symlink_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    occurrence, manifest_path = _manifest_occurrence(tmp_path)
    relative = manifest_path.relative_to(tmp_path).as_posix()
    manifest_bytes = manifest_path.read_bytes()
    manifest_path.unlink()
    with pytest.raises(PostDispatchReviewResolutionError, match="ordinary non-link"):
        open_post_dispatch_possible_path(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            kind="manifest",
            relative_path=relative,
        )

    manifest_path.write_bytes(manifest_bytes)
    monkeypatch.setattr(
        resolution_service,
        "_is_link_like",
        lambda path: path == manifest_path,
    )
    monkeypatch.setattr(resolution_service, "open_local_path", lambda path: path)
    with pytest.raises(PostDispatchReviewResolutionError, match="symlink|non-link"):
        open_post_dispatch_possible_path(
            tmp_path,
            occurrence.work_ref,
            occurrence.occurrence.failure_id,
            kind="manifest",
            relative_path=relative,
        )


def test_contextual_evidence_opening_uses_occurrence_observation_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_ref = quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)
    observation_id = "obs_" + "d" * 32
    evidence_path = (
        work_paths.quillan_work_paths(tmp_path, CLASS_ID, ASSIGNMENT_ID).work_root
        / "scans"
        / "evidence"
        / "response_student_01_page_1.png"
    )
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(b"validated evidence")
    relative = evidence_path.relative_to(tmp_path).as_posix()
    occurrence = create_post_dispatch_review_occurrence(
        tmp_path,
        work_ref,
        category="routed_evidence_persistence",
        stage="routed_evidence_persistence",
        failure_message="Evidence installation was uncertain.",
        student_id="student_01",
        observation_id=observation_id,
        possible_evidence_path=evidence_path,
        created_at="2026-07-21T12:00:00+00:00",
    )
    observation = SimpleNamespace(
        routed_evidence_path=relative,
        issuance_id="iss_" + "e" * 32,
        student_id="student_01",
        logical_page=1,
        observation_id=observation_id,
        routed_evidence_sha256="a" * 64,
        routed_evidence_size_bytes=len(b"validated evidence"),
    )
    monkeypatch.setattr(
        resolution_service,
        "load_contextual_response_page_observation",
        lambda *_args, **_kwargs: observation,
    )
    validated: list[str] = []
    monkeypatch.setattr(
        resolution_service,
        "verify_contextual_routed_page_evidence",
        lambda *_args, **kwargs: validated.append(cast(str, kwargs["relative_path"])),
    )
    monkeypatch.setattr(resolution_service, "open_local_path", lambda path: path)

    opened = open_post_dispatch_possible_path(
        tmp_path,
        work_ref,
        occurrence.occurrence.failure_id,
        kind="evidence",
        relative_path=relative,
    )

    assert opened.path == evidence_path
    assert opened.failure_id == occurrence.occurrence.failure_id
    assert validated == [relative]
    assert discover_post_dispatch_review_items(tmp_path, work_ref).items

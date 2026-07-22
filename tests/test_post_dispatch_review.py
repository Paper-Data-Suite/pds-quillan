"""Tests for append-only work-scoped post-dispatch review occurrences."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile

import pytest
from pds_core.routing_models import ModuleWorkRef

from quillan.post_dispatch_review import (
    PersistedPostDispatchReviewOccurrence,
    PostDispatchReviewError,
    QuillanReviewSource,
    create_post_dispatch_review_occurrence,
    discover_quillan_owned_review_items,
    discover_post_dispatch_review_occurrences,
)
from quillan.work_paths import post_dispatch_review_dir, quillan_work_ref
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID
import quillan.post_dispatch_review as post_dispatch_review


def _ref() -> ModuleWorkRef:
    return quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)


def test_occurrences_are_append_only_unique_and_discoverable(tmp_path: Path) -> None:
    evidence = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "scans"
        / "evidence"
        / "iss_0123456789abcdef0123456789abcdef"
        / f"response_{STUDENT_ID}_pg_001__obs_0123456789abcdef0123456789abcdef.png"
    )
    first = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="routed_evidence_persistence",
        stage="observation_persistence",
        failure_message="synthetic disk failure",
        student_id=STUDENT_ID,
        source_scan_id="scan_001",
        source_page_number=1,
        possible_evidence_path=evidence,
    )
    second = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="submission_assembly",
        stage="submission_assembly",
        failure_message="synthetic assembly failure",
        student_id=STUDENT_ID,
    )

    discovery = discover_post_dispatch_review_occurrences(tmp_path, _ref())

    assert first.path != second.path
    assert len(discovery.items) == 2
    assert not discovery.warnings
    assert all(item.path.read_bytes() for item in discovery.items)
    stored = json.loads(first.path.read_text(encoding="utf-8"))
    assert stored["class_id"] == CLASS_ID
    assert stored["assignment_id"] == ASSIGNMENT_ID
    assert stored["possible_evidence_paths"][0].startswith(
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
    )


def test_possible_durable_path_cannot_escape_affected_work(tmp_path: Path) -> None:
    with pytest.raises(PostDispatchReviewError, match="affected Quillan work root"):
        create_post_dispatch_review_occurrence(
            tmp_path,
            _ref(),
            category="post_dispatch_integrity",
            stage="verification",
            failure_message="uncertain write",
            possible_manifest_path=tmp_path / "outside.json",
        )


def test_discovery_reports_malformed_records_without_hiding_valid_items(
    tmp_path: Path,
) -> None:
    created = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="manifest_conflict",
        stage="submission_assembly",
        failure_message="conflict",
    )
    malformed = post_dispatch_review_dir(tmp_path, _ref()) / "failure_bad.json"
    malformed.write_text("{not-json", encoding="utf-8")

    discovery = discover_post_dispatch_review_occurrences(tmp_path, _ref())

    assert [item.path for item in discovery.items] == [created.path]
    assert len(discovery.warnings) == 1
    assert "failure_bad.json" in discovery.warnings[0]


def test_combined_discovery_keeps_post_dispatch_schema_typed(tmp_path: Path) -> None:
    created = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="post_dispatch_integrity",
        stage="verification",
        failure_message="uncertain durable state",
    )

    discovery = discover_quillan_owned_review_items(
        tmp_path, _ref(), source=QuillanReviewSource.POST_DISPATCH
    )

    assert discovery.items == (created,)
    assert discovery.core_warnings == ()


def test_multi_identity_failure_provenance_is_not_collapsed(tmp_path: Path) -> None:
    created = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="mixed_issuance",
        stage="submission_assembly",
        failure_message="mixed",
        issuance_ids=(
            "iss_0123456789abcdef0123456789abcdef",
            "iss_1123456789abcdef0123456789abcdef",
        ),
        observation_ids=(
            "obs_0123456789abcdef0123456789abcdef",
            "obs_1123456789abcdef0123456789abcdef",
        ),
        source_page_numbers=(1, 2),
    )
    assert len(created.occurrence.issuance_ids) == 2
    assert created.occurrence.issuance_id is None
    stored = json.loads(created.path.read_text(encoding="utf-8"))
    assert len(stored["observation_ids"]) == 2


def test_temporary_allocation_failure_is_translated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        tempfile,
        "mkstemp",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("allocation failed")),
    )
    with pytest.raises(PostDispatchReviewError, match="allocation failed"):
        create_post_dispatch_review_occurrence(
            tmp_path,
            _ref(),
            category="post_dispatch_integrity",
            stage="verification",
            failure_message="failure",
        )


def test_reload_failure_reports_exact_possibly_durable_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        post_dispatch_review,
        "_verify_occurrence_bytes",
        lambda *_args: (_ for _ in ()).throw(PostDispatchReviewError("reload failed")),
    )
    with pytest.raises(PostDispatchReviewError) as captured:
        create_post_dispatch_review_occurrence(
            tmp_path,
            _ref(),
            category="post_dispatch_integrity",
            stage="verification",
            failure_message="failure",
        )
    assert captured.value.possibly_durable_path is not None
    assert captured.value.possibly_durable_path.is_file()


def test_persisted_occurrence_carries_exact_workspace_and_work_authority(
    tmp_path: Path,
) -> None:
    created = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="post_dispatch_integrity",
        stage="verification",
        failure_message="failure",
    )

    assert created.workspace_root == tmp_path.absolute()
    assert created.work_ref == _ref()
    assert created.path == (
        created.workspace_root / Path(created.relative_path)
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "wrong/path.json",
        "C:/absolute/path.json",
        ".",
        "../outside.json",
        "classes/../outside.json",
        r"classes\wrong\path.json",
    ],
)
def test_persisted_occurrence_rejects_nonexact_relative_paths(
    tmp_path: Path,
    relative_path: str,
) -> None:
    created = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="post_dispatch_integrity",
        stage="verification",
        failure_message="failure",
    )

    with pytest.raises(PostDispatchReviewError):
        PersistedPostDispatchReviewOccurrence(
            created.workspace_root,
            created.work_ref,
            created.occurrence,
            created.path,
            relative_path,
        )


@pytest.mark.parametrize(
    "path_kind",
    ["another_workspace", "another_class", "another_assignment", "sibling_module", "wrong_filename"],
)
def test_persisted_occurrence_rejects_alternative_absolute_destinations(
    tmp_path: Path,
    path_kind: str,
) -> None:
    created = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="post_dispatch_integrity",
        stage="verification",
        failure_message="failure",
    )
    if path_kind == "another_workspace":
        alternative = tmp_path / "another_workspace" / Path(created.relative_path)
    elif path_kind == "another_class":
        alternative = Path(
            str(created.path).replace(CLASS_ID, "english10_p9", 1)
        )
    elif path_kind == "another_assignment":
        alternative = Path(
            str(created.path).replace(ASSIGNMENT_ID, "other_assignment", 1)
        )
    elif path_kind == "sibling_module":
        relative_parts = list(Path(created.relative_path).parts)
        module_index = relative_parts.index("modules") + 1
        relative_parts[module_index] = "scoreform"
        alternative = created.workspace_root.joinpath(*relative_parts)
    else:
        alternative = created.path.with_name("failure_wrong.json")

    with pytest.raises(PostDispatchReviewError, match="canonical destination"):
        PersistedPostDispatchReviewOccurrence(
            created.workspace_root,
            created.work_ref,
            created.occurrence,
            alternative,
            alternative.relative_to(tmp_path).as_posix(),
        )


@pytest.mark.parametrize(
    "module_details",
    [{1: "numeric"}, {1: "numeric", "1": "text"}],
)
def test_module_details_rejects_non_string_and_colliding_keys(
    tmp_path: Path,
    module_details: dict[object, object],
) -> None:
    created = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="post_dispatch_integrity",
        stage="verification",
        failure_message="failure",
    )

    with pytest.raises(PostDispatchReviewError, match="keys must be exact strings"):
        replace(created.occurrence, module_details=module_details)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", " verification"),
        ("stage", "verification "),
        ("failure_message", " failure"),
        ("failure_message", "failure "),
    ],
)
def test_occurrence_rejects_stage_and_message_outer_whitespace(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    created = create_post_dispatch_review_occurrence(
        tmp_path,
        _ref(),
        category="post_dispatch_integrity",
        stage="verification",
        failure_message="failure",
    )

    with pytest.raises(PostDispatchReviewError):
        replace(created.occurrence, **{field: value})  # type: ignore[arg-type]

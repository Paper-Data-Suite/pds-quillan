"""Tests for canonical immutable Quillan record contexts."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from pds_core.routing_models import ModuleWorkRef

from quillan.record_context import (
    InvalidReviewError,
    MissingReviewError,
    OrphanReviewError,
    ReviewAlreadyExistsError,
    ReviewLoadingPolicy,
    load_quillan_assignment_context,
    load_quillan_student_review_context,
    mutable_json_copy,
)
from quillan.review_record_paths import (
    ReviewRecordConcurrencyError,
    ReviewRecordPathError,
    update_quillan_review_record,
)
import quillan.atomic_record_io as atomic_record_io
from quillan.work_paths import quillan_work_ref
from tests.review_test_support import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    TIMESTAMP,
    _review,
    _write_assignment,
    _write_manifest,
    _write_review,
)


def _ref() -> ModuleWorkRef:
    return quillan_work_ref(CLASS_ID, ASSIGNMENT_ID)


def test_assignment_context_uses_only_module_qualified_record(tmp_path: Path) -> None:
    canonical = _write_assignment(tmp_path)
    legacy = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{not-json", encoding="utf-8")

    context = load_quillan_assignment_context(tmp_path, _ref())

    assert context.paths.assignment_path == canonical
    assert context.assignment["assignment_id"] == ASSIGNMENT_ID


def test_student_context_is_recursively_immutable(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_manifest(tmp_path)
    _write_review(tmp_path, _review())

    context = load_quillan_student_review_context(
        tmp_path, _ref(), STUDENT_ID, review_policy=ReviewLoadingPolicy.REVIEW_REQUIRED
    )

    with pytest.raises(TypeError):
        context.submission["student_id"] = "changed"  # type: ignore[index]
    assert isinstance(context.submission["pages"], tuple)
    assert context.paths.submission_relative_path.startswith(
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
    )


def test_review_presence_policies_are_explicit(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_manifest(tmp_path)

    with pytest.raises(MissingReviewError):
        load_quillan_student_review_context(
            tmp_path,
            _ref(),
            STUDENT_ID,
            review_policy=ReviewLoadingPolicy.REVIEW_REQUIRED,
        )

    _write_review(tmp_path, _review())
    with pytest.raises(ReviewAlreadyExistsError):
        load_quillan_student_review_context(
            tmp_path,
            _ref(),
            STUDENT_ID,
            review_policy=ReviewLoadingPolicy.REVIEW_MUST_BE_ABSENT,
        )


def test_orphan_review_is_distinguished(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_review(tmp_path, _review())

    with pytest.raises(OrphanReviewError):
        load_quillan_student_review_context(tmp_path, _ref(), STUDENT_ID)


def test_noncanonical_feedback_export_metadata_is_rejected(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_manifest(tmp_path)
    review = _review()
    review["exports"]["feedback_markdown"] = {
        "path": "elsewhere/feedback.md",
        "generated_at": TIMESTAMP,
        "source_review_updated_at": TIMESTAMP,
        "module_details": {},
    }
    path = _write_review(tmp_path, review)
    assert json.loads(path.read_text(encoding="utf-8"))["exports"]

    with pytest.raises(InvalidReviewError, match="feedback_markdown.path"):
        load_quillan_student_review_context(tmp_path, _ref(), STUDENT_ID)


def test_snapshot_bytes_and_immutable_model_are_exactly_bound(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_manifest(tmp_path)
    _write_review(tmp_path, _review())
    context = load_quillan_student_review_context(
        tmp_path,
        _ref(),
        STUDENT_ID,
        review_policy=ReviewLoadingPolicy.REVIEW_REQUIRED,
    )
    assert context.review_record is not None
    assert json.loads(context.review_record.original_bytes) == mutable_json_copy(
        context.review_record.value
    )
    with pytest.raises(ValueError, match="does not agree"):
        replace(context.review_record, original_bytes=b"{}")


def test_concurrent_edit_after_context_load_is_preserved(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_manifest(tmp_path)
    path = _write_review(tmp_path, _review())
    context = load_quillan_student_review_context(
        tmp_path,
        _ref(),
        STUDENT_ID,
        review_policy=ReviewLoadingPolicy.REVIEW_REQUIRED,
    )
    updated = _review()
    updated["module_details"] = {"writer": "service"}
    concurrent = _review()
    concurrent["module_details"] = {"writer": "concurrent"}
    concurrent_bytes = (json.dumps(concurrent, indent=2) + "\n").encode()
    path.write_bytes(concurrent_bytes)

    with pytest.raises(ReviewRecordConcurrencyError):
        update_quillan_review_record(context, updated)
    assert path.read_bytes() == concurrent_bytes


def test_concurrent_edit_immediately_before_displacement_is_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_assignment(tmp_path)
    _write_manifest(tmp_path)
    path = _write_review(tmp_path, _review())
    context = load_quillan_student_review_context(
        tmp_path,
        _ref(),
        STUDENT_ID,
        review_policy=ReviewLoadingPolicy.REVIEW_REQUIRED,
    )
    updated = _review()
    updated["module_details"] = {"writer": "service"}
    concurrent = _review()
    concurrent["module_details"] = {"writer": "concurrent-before-replace"}
    concurrent_bytes = (json.dumps(concurrent, indent=2) + "\n").encode()
    original_replace = os.replace

    def inject_before_replace(source: str | Path, target: str | Path) -> None:
        if Path(source) == path and str(target).endswith(".displaced"):
            path.write_bytes(concurrent_bytes)
        original_replace(source, target)

    monkeypatch.setattr(os, "replace", inject_before_replace)
    with pytest.raises(ReviewRecordConcurrencyError):
        update_quillan_review_record(context, updated)
    assert path.read_bytes() == concurrent_bytes


def test_concurrent_edit_after_install_is_not_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_assignment(tmp_path)
    _write_manifest(tmp_path)
    path = _write_review(tmp_path, _review())
    context = load_quillan_student_review_context(
        tmp_path,
        _ref(),
        STUDENT_ID,
        review_policy=ReviewLoadingPolicy.REVIEW_REQUIRED,
    )
    updated = _review()
    updated["module_details"] = {"writer": "service"}
    concurrent = _review()
    concurrent["module_details"] = {"writer": "concurrent-after-install"}
    concurrent_bytes = (json.dumps(concurrent, indent=2) + "\n").encode()
    original_verify = atomic_record_io._verify_installed

    def inject_before_verify(*args: object, **kwargs: object) -> None:
        path.write_bytes(concurrent_bytes)
        original_verify(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(atomic_record_io, "_verify_installed", inject_before_verify)
    with pytest.raises(ReviewRecordPathError) as captured:
        update_quillan_review_record(context, updated)
    assert captured.value.possibly_durable_path == path
    assert path.read_bytes() == concurrent_bytes

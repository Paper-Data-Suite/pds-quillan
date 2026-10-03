"""Issue #417 Slice 3 tests for assignment results JSON reporting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

import quillan.assignment_reporting_snapshot as snapshot_module
from quillan.assignment_reporting_snapshot import build_assignment_reporting_snapshot
from quillan.assignment_results_manifest_export import (
    AssignmentResultsManifestExportError,
    export_assignment_results_manifest_from_snapshot,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_assignment_reporting_snapshot_issue417 import _prepare_workspace
from tests.test_class_summary_export import (
    STANDARD_A,
    STANDARD_B,
    TIMESTAMP,
    _write_json,
    _write_records,
)


def _read(path: Path) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(path.read_text(encoding="utf-8")),
    )


def test_manifest_serializes_snapshot_aggregates_with_explicit_denominators(
    tmp_path: Path,
) -> None:
    _prepare_workspace(tmp_path)

    _, returned_path, returned = _write_records(tmp_path, "00200")
    returned["review_state"] = "returned_without_full_review"
    returned["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "PRIVATE RETURN NOTE",
        "updated_at": returned["updated_at"],
    }
    returned["overall_standard_ratings"] = []
    _write_json(returned_path, returned)

    _, partial_path, partial = _write_records(tmp_path, "00300")
    partial["review_state"] = "observations_in_progress"
    partial["minimum_requirement_outcome"]["status"] = "met"
    partial["minimum_requirement_outcome"]["updated_at"] = partial["updated_at"]
    partial["overall_standard_ratings"] = []
    partial["private_notes"] = [
        {
            "private_note_id": "private_0001",
            "text": "PRIVATE TEACHER NOTE MUST NOT LEAK",
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    _write_json(partial_path, partial)

    source_files = {
        path: path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    snapshot = build_assignment_reporting_snapshot(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    result = export_assignment_results_manifest_from_snapshot(
        snapshot,
        generated_at=TIMESTAMP,
    )
    payload = _read(result.manifest_path)

    assert payload["schema_version"] == "1"
    assert payload["module"] == "quillan"
    assert payload["record_type"] == "assignment_results_manifest"
    assert payload["generated_at"] == TIMESTAMP
    assert payload["class"] == {"class_id": CLASS_ID}
    assert payload["assignment"]["assignment_id"] == ASSIGNMENT_ID
    assert payload["assignment"]["title"] == "Synthetic Essay"
    assert payload["assignment"]["writing_type"] == "argument"
    assert [item["standard_id"] for item in payload["focus_standards"]] == [
        STANDARD_A,
        STANDARD_B,
    ]

    summary = payload["assignment_summary"]
    assert summary["students_expected"] >= 3
    assert summary["students_returned_without_full_review"] == 1
    assert summary["students_in_progress"] >= 1

    standard_a = payload["standard_summaries"][0]
    assert standard_a["standard_id"] == STANDARD_A
    assert standard_a["rated_count"] == 1
    assert standard_a["returned_without_full_review_count"] == 1
    rating_three = next(
        item for item in standard_a["rating_distribution"] if item["value"] == 3
    )
    assert rating_three == {
        "value": 3,
        "label": "Secure",
        "count": 1,
        "percent_of_rated": 100.0,
        "denominator": "rated_students",
        "denominator_count": 1,
    }

    text = result.manifest_path.read_text(encoding="utf-8")
    assert "PRIVATE TEACHER NOTE MUST NOT LEAK" not in text
    assert "PRIVATE RETURN NOTE" not in text
    assert "Teacher-entered rationale." not in text
    assert "student_prompt" not in text
    assert "mastery" not in text.lower()

    for path, original in source_files.items():
        assert path.read_bytes() == original


def test_manifest_from_snapshot_does_not_reread_canonical_reporting_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_workspace(tmp_path)
    snapshot = build_assignment_reporting_snapshot(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    def fail_if_reloaded(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("canonical reporting source was reloaded after snapshot")

    monkeypatch.setattr(snapshot_module, "load_assignment", fail_if_reloaded)
    monkeypatch.setattr(snapshot_module, "discover_students", fail_if_reloaded)
    monkeypatch.setattr(snapshot_module, "load_student_record", fail_if_reloaded)
    monkeypatch.setattr(
        snapshot_module,
        "load_workspace_standards_library",
        fail_if_reloaded,
    )
    monkeypatch.setattr(snapshot_module, "feedback_status", fail_if_reloaded)

    result = export_assignment_results_manifest_from_snapshot(
        snapshot,
        generated_at=TIMESTAMP,
    )
    payload = _read(result.manifest_path)
    assert payload["assignment"]["assignment_id"] == ASSIGNMENT_ID
    inventory = {
        item["artifact"]: item
        for item in payload["generated_artifacts"]
    }
    assert inventory["assignment_results_manifest_json"]["status"] == "generated"


def test_manifest_is_create_only_and_explicit_overwrite(
    tmp_path: Path,
) -> None:
    _prepare_workspace(tmp_path)
    snapshot = build_assignment_reporting_snapshot(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    first = export_assignment_results_manifest_from_snapshot(
        snapshot,
        generated_at=TIMESTAMP,
    )
    original = first.manifest_path.read_bytes()

    with pytest.raises(AssignmentResultsManifestExportError, match="--overwrite"):
        export_assignment_results_manifest_from_snapshot(
            snapshot,
            generated_at="2026-10-02T22:00:00+00:00",
        )
    assert first.manifest_path.read_bytes() == original

    second = export_assignment_results_manifest_from_snapshot(
        snapshot,
        overwrite=True,
        generated_at="2026-10-02T22:00:00+00:00",
    )
    assert second.overwrote_existing is True
    payload = _read(second.manifest_path)
    assert payload["generated_at"] == "2026-10-02T22:00:00+00:00"

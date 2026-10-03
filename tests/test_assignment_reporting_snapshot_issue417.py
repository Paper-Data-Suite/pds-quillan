"""Issue #417 Slice 2 tests for the shared assignment reporting snapshot."""

from __future__ import annotations

import csv
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)

import quillan.assignment_reporting_snapshot as snapshot_module
from quillan.assignment_reporting_snapshot import (
    build_assignment_reporting_snapshot,
)
from quillan.class_summary_export import (
    export_class_review_summary_from_snapshot,
)
from quillan.report_csv import REPORT_CSV_ENCODING
from quillan.standards_summary_export import (
    export_standards_summary_from_snapshot,
)
from quillan.student_performance_summary_export import (
    export_student_performance_summary_from_snapshot,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import (
    STANDARD_A,
    STANDARD_B,
    TIMESTAMP,
    _write_assignment,
    _write_json,
    _write_records,
    _write_roster,
)


def _write_standards_library(workspace: Path) -> None:
    write_workspace_standards_library(
        workspace,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_A,
                    code="W.NW.11-12.3.D",
                    source="Synthetic NJSLS-ELA",
                    short_name="Narrative Writing",
                    description="Use precise narrative technique.",
                    available_modules=("quillan",),
                ),
                StandardDefinition(
                    standard_id=STANDARD_B,
                    code="RL.TS.11-12.4",
                    source="Synthetic NJSLS-ELA",
                    short_name="Text Structure",
                    description="Analyze structural choices.",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id="synthetic_profile",
                    standards=(STANDARD_A, STANDARD_B),
                ),
            ),
        ),
    )


def _prepare_workspace(workspace: Path) -> tuple[Path, Path, Path, Path]:
    assignment_path = _write_assignment(workspace)
    roster_path = _write_roster(workspace)
    manifest_path, review_path, review = _write_records(workspace, "00100")
    review["minimum_requirement_outcome"] = {
        "status": "met",
        "returned_without_full_review": False,
        "teacher_note": None,
        "updated_at": review["updated_at"],
    }
    review["overall_standard_ratings"] = [
        {
            "standard_id": STANDARD_A,
            "rating": 3,
            "rationale": "Teacher-entered rationale.",
            "include_in_feedback": True,
            "updated_at": review["updated_at"],
            "module_details": {},
        }
    ]
    _write_json(review_path, review)
    _write_standards_library(workspace)
    return assignment_path, roster_path, manifest_path, review_path


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding=REPORT_CSV_ENCODING, newline="") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or ()), list(reader)


def test_snapshot_is_immutable_reportable_state_and_does_not_mutate_sources(
    tmp_path: Path,
) -> None:
    source_paths = _prepare_workspace(tmp_path)
    originals = {path: path.read_bytes() for path in source_paths}

    snapshot = build_assignment_reporting_snapshot(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    assert snapshot.class_id == CLASS_ID
    assert snapshot.assignment_id == ASSIGNMENT_ID
    assert snapshot.assignment_title == "Synthetic Essay"
    assert snapshot.standards_profile_id == "synthetic_profile"
    assert snapshot.focus_standard_ids == (STANDARD_A, STANDARD_B)
    assert snapshot.rating_values == (1, 2, 3)
    assert [standard.display_code for standard in snapshot.focus_standards] == [
        "W.NW.11-12.3.D",
        "RL.TS.11-12.4",
    ]
    assert isinstance(snapshot.students, tuple)

    first = snapshot.students[0]
    assert first.student_id == "00100"
    assert first.submission_valid is True
    assert first.review_valid is True
    assert first.minimum_requirement_status == "met"
    assert first.returned_without_full_review is False
    assert len(first.overall_standard_ratings) == 1
    assert first.overall_standard_ratings[0].standard_id == STANDARD_A
    assert first.overall_standard_ratings[0].value == 3
    assert first.overall_standard_ratings[0].label == "Secure"

    with pytest.raises(FrozenInstanceError):
        setattr(snapshot, "class_id", "changed")

    for path, original in originals.items():
        assert path.read_bytes() == original


def test_snapshot_loads_canonical_reporting_inputs_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_workspace(tmp_path)
    counts: dict[str, int] = {
        "assignment": 0,
        "discover": 0,
        "student": 0,
        "standards": 0,
        "feedback": 0,
    }

    real_assignment = snapshot_module.load_assignment
    real_discover = snapshot_module.discover_students
    real_student = snapshot_module.load_student_record
    real_standards = snapshot_module.load_workspace_standards_library
    real_feedback = snapshot_module.feedback_status

    def counted_assignment(*args: Any, **kwargs: Any) -> Any:
        counts["assignment"] += 1
        return real_assignment(*args, **kwargs)

    def counted_discover(*args: Any, **kwargs: Any) -> Any:
        counts["discover"] += 1
        return real_discover(*args, **kwargs)

    def counted_student(*args: Any, **kwargs: Any) -> Any:
        counts["student"] += 1
        return real_student(*args, **kwargs)

    def counted_standards(*args: Any, **kwargs: Any) -> Any:
        counts["standards"] += 1
        return real_standards(*args, **kwargs)

    def counted_feedback(*args: Any, **kwargs: Any) -> Any:
        counts["feedback"] += 1
        return real_feedback(*args, **kwargs)

    monkeypatch.setattr(snapshot_module, "load_assignment", counted_assignment)
    monkeypatch.setattr(snapshot_module, "discover_students", counted_discover)
    monkeypatch.setattr(snapshot_module, "load_student_record", counted_student)
    monkeypatch.setattr(
        snapshot_module,
        "load_workspace_standards_library",
        counted_standards,
    )
    monkeypatch.setattr(snapshot_module, "feedback_status", counted_feedback)

    snapshot = build_assignment_reporting_snapshot(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    assert counts == {
        "assignment": 1,
        "discover": 1,
        "student": len(snapshot.students),
        "standards": 1,
        "feedback": len(snapshot.students) * 2,
    }


def test_one_snapshot_drives_all_existing_csv_renderers_without_source_reread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_paths = _prepare_workspace(tmp_path)
    originals = {path: path.read_bytes() for path in source_paths}
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

    student_result = export_student_performance_summary_from_snapshot(
        snapshot,
        created_at=TIMESTAMP,
    )
    class_result = export_class_review_summary_from_snapshot(
        snapshot,
        created_at=TIMESTAMP,
    )
    standards_result = export_standards_summary_from_snapshot(
        snapshot,
        created_at=TIMESTAMP,
    )

    student_fields, student_rows = _read_csv(student_result.summary_path)
    class_fields, class_rows = _read_csv(class_result.summary_path)
    standards_fields, standards_rows = _read_csv(standards_result.summary_path)

    assert student_fields[:4] == [
        "student_id",
        "student_display_name",
        "review_status",
        "minimum_requirements",
    ]
    assert student_rows[0]["student_id"] == "00100"
    assert "class_id" in class_fields
    assert class_rows[0]["student_id"] == "00100"
    assert standards_fields[0] == "class_id"
    assert [row["standard_id"] for row in standards_rows] == [
        STANDARD_A,
        STANDARD_B,
    ]

    for path, original in originals.items():
        assert path.read_bytes() == original

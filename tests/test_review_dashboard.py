"""Contract tests for the shared assignment review dashboard."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, cast

from quillan.review_dashboard import (
    assignment_review_dashboard_to_dict,
    build_assignment_review_dashboard,
    format_assignment_review_dashboard,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, _manifest, _review
from tests.test_class_summary_export import (
    _student_dir,
    _write_assignment,
    _write_json,
    _write_roster,
)


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def test_dashboard_unions_students_isolates_invalid_records_and_is_read_only(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    manifest = copy.deepcopy(_manifest())
    manifest["student_id"] = "00100"
    manifest["submission_state"] = "reviewed"
    review = copy.deepcopy(_review("feedback_composed"))
    review["student_id"] = "00100"
    review["submission_manifest_path"] = (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/submissions/"
        "00100/submission.json"
    )
    _write_json(_student_dir(tmp_path, "00100") / "submission.json", manifest)
    _write_json(_student_dir(tmp_path, "00100") / "review.json", review)
    invalid = _student_dir(tmp_path, "00300") / "submission.json"
    invalid.parent.mkdir(parents=True)
    invalid.write_text("{", encoding="utf-8")
    routed = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "scans"
        / "response_00400_pg_001.pdf"
    )
    routed.parent.mkdir(parents=True)
    routed.write_bytes(b"not inspected")
    before = _snapshot(tmp_path)

    dashboard = build_assignment_review_dashboard(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    document = cast(dict[str, Any], assignment_review_dashboard_to_dict(dashboard))

    assert [student["student_id"] for student in document["students"]] == [
        "00100",
        "00200",
        "00900",
        "00300",
    ]
    assert document["schema_version"] == "1"
    assert document["record_type"] == "quillan_assignment_review_dashboard"
    assert document["summary"]["submissions"]["valid"] == 1
    assert document["summary"]["submissions"]["invalid"] == 1
    assert document["summary"]["submissions"]["missing"] == 2
    assert document["summary"]["reviews"]["missing"] == 0
    assert document["summary"]["routed_evidence"]["students_needing_assembly"] == 0
    assert document["students"][0]["display_name"] == "Avery Rivera"
    assert document["students"][-1]["needs_assembly"] is False
    assert _snapshot(tmp_path) == before


def test_dashboard_json_shape_and_text_have_fixed_empty_groups(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    dashboard = build_assignment_review_dashboard(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    document = cast(dict[str, Any], assignment_review_dashboard_to_dict(dashboard))

    assert list(document) == [
        "schema_version",
        "record_type",
        "class_id",
        "assignment_id",
        "assignment",
        "summary",
        "students",
        "unassembled_routed_files",
        "unused_duplicate_routed_files",
        "skipped_routed_files",
        "scan_review_items",
        "warnings",
    ]
    assert list(document["summary"]["submissions"]["states"]) == [
        "unreviewed",
        "in_progress",
        "needs_rescan",
        "reviewed",
    ]
    assert list(document["summary"]["reviews"]["states"]) == [
        "not_started",
        "requirements_checked",
        "returned_without_full_review",
        "observations_in_progress",
        "observations_complete",
        "ratings_complete",
        "feedback_composed",
        "ready_for_export",
        "exported",
    ]
    assert document["students"] == []
    text = format_assignment_review_dashboard(dashboard)
    assert "Assignment Review Dashboard" in text
    assert "Submission intake:" in text
    assert "Review progress:" in text
    assert "Scan review:" in text

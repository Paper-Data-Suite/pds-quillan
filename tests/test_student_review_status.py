"""Focused contract tests for selected-student review status."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

from quillan.student_review_status import (
    build_student_review_status,
    format_student_review_status,
    student_review_status_to_dict,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, _manifest, _review
from tests.test_class_summary_export import _student_dir, _write_assignment, _write_json, _write_roster


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _document(root: Path, student_id: str = "00100") -> dict[str, Any]:
    status = build_student_review_status(root, CLASS_ID, ASSIGNMENT_ID, student_id)
    return cast(dict[str, Any], student_review_status_to_dict(status))


def test_missing_records_have_null_and_zero_semantics_and_are_read_only(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    before = _snapshot(tmp_path)
    document = _document(tmp_path)
    assert document["schema_version"] == "1"
    assert document["record_type"] == "quillan_student_review_status"
    assert document["submission"]["status"] == "missing"
    assert document["submission"]["pages"] == {
        "available": False,
        "total": None,
        "states": {state: None for state in ("present", "missing", "duplicate", "needs_rescan", "excluded")},
        "present_unselected": None,
        "with_selected_evidence": None,
        "without_selected_evidence": None,
    }
    assert document["review"]["status"] == "missing"
    assert document["review"]["state"] is None
    assert document["review"]["review_units"]["total"] == 0
    assert document["review"]["overall_ratings"]["missing"] == 2
    assert _snapshot(tmp_path) == before


def test_valid_review_counts_notes_without_exposing_prose(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    manifest = copy.deepcopy(_manifest("00100"))
    review = copy.deepcopy(_review("feedback_composed", "00100"))
    secret = "DISTINCTIVE_PRIVATE_SECRET"
    review["private_notes"] = [{"private_note_id": "note_1", "text": secret, "created_at": review["created_at"], "updated_at": review["updated_at"], "module_details": {}}]
    _write_json(_student_dir(tmp_path, "00100") / "submission.json", manifest)
    _write_json(_student_dir(tmp_path, "00100") / "review.json", review)
    status = build_student_review_status(tmp_path, CLASS_ID, ASSIGNMENT_ID, "00100")
    document = cast(dict[str, Any], student_review_status_to_dict(status))
    rendered = json.dumps(document) + format_student_review_status(status)
    assert document["review"]["private_notes"]["total"] == 1
    assert secret not in rendered
    assert "private_note_id" not in rendered


def test_invalid_sibling_is_isolated_and_output_is_deterministic(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_json(_student_dir(tmp_path, "00999") / "review.json", "not a record")
    assert _document(tmp_path) == _document(tmp_path)
    assert "invalid_review" not in _document(tmp_path)["warnings"]


def test_orphaned_review_is_rejected_by_canonical_context(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_json(_student_dir(tmp_path, "00100") / "review.json", _review("not_started", "00100"))
    document = _document(tmp_path)
    assert document["review"]["status"] == "orphaned"
    assert document["review"]["orphaned"] is True
    assert "review_without_valid_submission" in document["warnings"]

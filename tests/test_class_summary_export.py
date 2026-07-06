"""Tests for teacher-facing class review summary CSV export."""

from __future__ import annotations

import copy
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from quillan.class_summary_export import (
    CSV_COLUMNS,
    ClassSummaryExportError,
    ExportedClassSummary,
    class_summary_export_path,
    export_class_review_summary,
)
from tests.test_review_tags import (
    ASSIGNMENT_ID,
    CLASS_ID,
    _manifest,
    _review,
)

TIMESTAMP = "2026-06-23T12:30:00+00:00"


def _student_dir(workspace: Path, student_id: str) -> Path:
    return (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / student_id
    )


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _records(student_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = copy.deepcopy(_manifest())
    manifest["student_id"] = student_id
    review = copy.deepcopy(_review("ready_for_export"))
    review["student_id"] = student_id
    review["submission_manifest_path"] = (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
        f"{student_id}/submission.json"
    )
    return manifest, review


def _write_records(
    workspace: Path, student_id: str
) -> tuple[Path, Path, dict[str, Any]]:
    manifest, review = _records(student_id)
    student_dir = _student_dir(workspace, student_id)
    manifest_path = _write_json(student_dir / "submission.json", manifest)
    review_path = _write_json(student_dir / "review.json", review)
    return manifest_path, review_path, review


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_exports_sorted_ready_rows_with_stable_schema_and_totals(
    tmp_path: Path,
) -> None:
    second_manifest, second_review_path, second_review = _write_records(
        tmp_path, "00200"
    )
    first_manifest, first_review_path, first_review = _write_records(
        tmp_path, "00100"
    )
    first_review["overall_standard_ratings"].extend(
        [
            {
                "standard_id": "synthetic:W.A",
                "rating": 3,
                "rationale": "Clear evidence.",
                "include_in_feedback": True,
                "updated_at": first_review["updated_at"],
                "module_details": {},
            },
            {
                "standard_id": "synthetic:W.B",
                "rating": 3,
                "rationale": None,
                "include_in_feedback": False,
                "updated_at": first_review["updated_at"],
                "module_details": {},
            },
        ]
    )
    first_review["review_units"].append(
        {
            "unit_id": "unit_0001",
            "sequence": 1,
            "label": "Paragraph 1",
            "unit_type": "paragraph",
            "standard_observations": [
                {
                    "observation_id": "observation_0001",
                    "standard_id": "synthetic:W.A",
                    "applicable": True,
                    "evidence_present": True,
                    "rating": 3,
                    "rationale": "Relevant evidence.",
                    "include_in_feedback": True,
                    "updated_at": first_review["updated_at"],
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    )
    first_review["feedback"]["standard_feedback"].append(
        {
            "standard_id": "synthetic:W.A",
            "include_overall_rating": True,
            "include_overall_rationale": True,
            "included_observation_ids": ["observation_0001"],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "custom",
                    "text": "Good evidence.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": first_review["created_at"],
                    "module_details": {},
                },
                {
                    "feedback_comment_id": "feedback_comment_0002",
                    "source": "custom",
                    "text": "Not for feedback.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": False,
                    "created_at": first_review["created_at"],
                    "module_details": {},
                },
            ],
            "module_details": {},
        }
    )
    first_review["private_notes"].append(
        {
            "private_note_id": "note_0001",
            "text": "Private note.",
            "created_at": first_review["created_at"],
            "updated_at": first_review["updated_at"],
            "module_details": {},
        }
    )
    _write_json(first_review_path, first_review)
    feedback_path = _student_dir(tmp_path, "00100") / "exports" / "feedback.md"
    feedback_path.parent.mkdir()
    feedback_path.write_text("existing feedback", encoding="utf-8")
    evidence_path = tmp_path / "never-read-evidence.pdf"
    comment_bank_path = tmp_path / "comment_banks" / "never-read.json"
    evidence_path.write_bytes(b"evidence")
    comment_bank_path.parent.mkdir()
    comment_bank_path.write_text("comment bank", encoding="utf-8")
    originals = {
        first_manifest: first_manifest.read_bytes(),
        first_review_path: first_review_path.read_bytes(),
        second_manifest: second_manifest.read_bytes(),
        second_review_path: second_review_path.read_bytes(),
        evidence_path: evidence_path.read_bytes(),
        comment_bank_path: comment_bank_path.read_bytes(),
    }

    result = export_class_review_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    expected_path = class_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    assert result == ExportedClassSummary(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        summary_path=expected_path,
        summary_relative_path=(
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/exports/"
            "class_summary.csv"
        ),
        row_count=2,
        ready_count=2,
        missing_review_count=0,
        invalid_review_count=0,
        missing_submission_count=0,
        invalid_submission_count=0,
        identity_mismatch_count=0,
        created_at=TIMESTAMP,
        overwrote_existing=False,
    )
    with expected_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        assert tuple(reader.fieldnames or ()) == CSV_COLUMNS
        rows = list(reader)
    assert [row["student_id"] for row in rows] == ["00100", "00200"]
    first = rows[0]
    assert first["row_status"] == "ready"
    assert first["review_state"] == "ready_for_export"
    assert first["submission_state"] == "unreviewed"
    assert first["score_count"] == "2"
    assert first["total_score"] == "6"
    assert first["total_max_score"] == ""
    assert first["included_comment_count"] == "1"
    assert first["selected_comment_count"] == "2"
    assert first["tag_count"] == "1"
    assert first["note_count"] == "1"
    assert first["feedback_export_exists"] == "true"
    assert first["submission_manifest_path"].endswith(
        "/submissions/00100/submission.json"
    )
    assert first["review_record_path"].endswith(
        "/submissions/00100/review.json"
    )
    assert first["feedback_export_path"].endswith(
        "/submissions/00100/exports/feedback.md"
    )
    assert first["error"] == ""
    assert rows[1]["feedback_export_exists"] == "false"
    for path, original in originals.items():
        assert path.read_bytes() == original


def test_status_rows_cover_missing_invalid_and_identity_mismatch(
    tmp_path: Path,
) -> None:
    _student_dir(tmp_path, "00100").mkdir(parents=True)
    _write_json(
        _student_dir(tmp_path, "00200") / "submission.json", {"invalid": True}
    )
    manifest, _ = _records("00300")
    _write_json(_student_dir(tmp_path, "00300") / "submission.json", manifest)
    manifest, _ = _records("00400")
    _write_json(_student_dir(tmp_path, "00400") / "submission.json", manifest)
    (_student_dir(tmp_path, "00400") / "review.json").write_text(
        "{", encoding="utf-8"
    )
    manifest, review = _records("other_student")
    _write_json(_student_dir(tmp_path, "00500") / "submission.json", manifest)
    _write_json(_student_dir(tmp_path, "00500") / "review.json", review)

    result = export_class_review_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )
    rows = _read_rows(result.summary_path)

    assert [row["row_status"] for row in rows] == [
        "missing_submission",
        "invalid_submission",
        "missing_review",
        "invalid_review",
        "identity_mismatch",
    ]
    assert all(row["error"] for row in rows)
    assert rows[0]["submission_state"] == ""
    assert rows[2]["submission_state"] == "unreviewed"
    assert all(row["review_state"] == "" for row in rows)
    assert all(row["score_count"] == "" for row in rows)
    assert result.missing_submission_count == 1
    assert result.invalid_submission_count == 1
    assert result.missing_review_count == 1
    assert result.invalid_review_count == 1
    assert result.identity_mismatch_count == 1


def test_empty_submissions_directory_writes_header_only(tmp_path: Path) -> None:
    submissions = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
    )
    submissions.mkdir(parents=True)

    result = export_class_review_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    assert result.row_count == 0
    assert _read_rows(result.summary_path) == []
    assert result.summary_path.read_text(encoding="utf-8").splitlines() == [
        ",".join(CSV_COLUMNS)
    ]


def test_missing_submissions_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ClassSummaryExportError, match="does not exist"):
        export_class_review_summary(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
        )


def test_overwrite_policy_replaces_only_derived_csv(tmp_path: Path) -> None:
    manifest_path, review_path, _ = _write_records(tmp_path, "00100")
    originals = {
        manifest_path: manifest_path.read_bytes(),
        review_path: review_path.read_bytes(),
    }
    first = export_class_review_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )
    first.summary_path.write_text("manual edit", encoding="utf-8")

    with pytest.raises(ClassSummaryExportError, match="--overwrite"):
        export_class_review_summary(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
        )
    assert first.summary_path.read_text(encoding="utf-8") == "manual edit"

    second = export_class_review_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        overwrite=True,
        created_at=TIMESTAMP,
    )
    assert second.overwrote_existing is True
    assert _read_rows(second.summary_path)[0]["row_status"] == "ready"
    for path, original in originals.items():
        assert path.read_bytes() == original


@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-time",
        "2026-06-23T12:30:00",
        datetime(2026, 6, 23, 12, 30),
        123,
    ],
)
def test_invalid_timestamp_is_rejected(
    tmp_path: Path, timestamp: object
) -> None:
    with pytest.raises(ClassSummaryExportError, match="timezone-aware"):
        export_class_review_summary(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            created_at=timestamp,  # type: ignore[arg-type]
        )


def test_aware_datetime_is_normalized(tmp_path: Path) -> None:
    submissions = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
    )
    submissions.mkdir(parents=True)
    timestamp = datetime(2026, 6, 23, 12, 30, tzinfo=timezone.utc)
    result = export_class_review_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=timestamp
    )
    assert result.created_at == timestamp.isoformat()

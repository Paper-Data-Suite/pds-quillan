"""Tests for teacher-facing assignment-local class summary CSV export."""

from __future__ import annotations

import copy
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from quillan.class_summary_export import (
    BASE_CSV_COLUMNS,
    ClassSummaryExportError,
    ExportedClassSummary,
    class_summary_export_path,
    export_class_review_summary,
)
from tests.review_test_support import (
    ASSIGNMENT_ID,
    CLASS_ID,
    _manifest,
    _review,
)

TIMESTAMP = "2026-06-23T12:30:00+00:00"
STANDARD_A = "synthetic:W.A"
STANDARD_B = "synthetic:W.B"
STANDARD_A_KEY = "synthetic_W_A"
STANDARD_B_KEY = "synthetic_W_B"


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


def _write_assignment(workspace: Path) -> Path:
    return _write_json(
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "assignment.json",
        {
            "schema_version": "2",
            "module": "quillan",
            "record_type": "assignment",
            "assignment_id": ASSIGNMENT_ID,
            "title": "Synthetic Essay",
            "class_ids": [CLASS_ID],
            "writing_type": "argument",
            "student_prompt": "Write a synthetic argument.",
            "standards_profile_id": "synthetic_profile",
            "focus_standard_ids": [STANDARD_A, STANDARD_B],
            "review_unit": {
                "type": "paragraph",
                "singular_label": "paragraph",
                "plural_label": "paragraphs",
            },
            "rating_scale": {
                "scale_id": "synthetic_scale",
                "levels": [
                    {"value": 1, "label": "Starting", "description": "Early work."},
                    {"value": 2, "label": "Growing", "description": "Developing work."},
                    {"value": 3, "label": "Secure", "description": "Consistent work."},
                ],
            },
            "basic_requirements": {"paragraphs_min": 1},
            "minimum_requirement_policy": {
                "allow_return_without_full_review": True
            },
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "module_details": {},
        },
    )


def _write_roster(workspace: Path) -> Path:
    path = workspace / "classes" / CLASS_ID / "roster.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "class_id,student_id,last_name,first_name,period\n"
        f"{CLASS_ID},00100,Rivera,Avery,3\n"
        f"{CLASS_ID},00200,Patel,Mina,3\n"
        f"{CLASS_ID},00900,Missing,Student,3\n",
        encoding="utf-8",
    )
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


def test_exports_assignment_local_rows_with_focus_standard_ratings(
    tmp_path: Path,
) -> None:
    assignment_path = _write_assignment(tmp_path)
    roster_path = _write_roster(tmp_path)
    second_manifest, second_review_path, second_review = _write_records(
        tmp_path, "00200"
    )
    first_manifest, first_review_path, first_review = _write_records(
        tmp_path, "00100"
    )
    unrostered_manifest, unrostered_review_path, unrostered_review = _write_records(
        tmp_path, "00300"
    )
    first_review["minimum_requirement_outcome"] = {
        "status": "met",
        "returned_without_full_review": False,
        "teacher_note": None,
        "updated_at": first_review["updated_at"],
    }
    first_review["overall_standard_ratings"] = [
        {
            "standard_id": STANDARD_A,
            "rating": 3,
            "rationale": "Uses evidence clearly.",
            "include_in_feedback": True,
            "updated_at": first_review["updated_at"],
            "module_details": {},
        },
        {
            "standard_id": STANDARD_B,
            "rating": 9,
            "rationale": "Unknown scale value.",
            "include_in_feedback": False,
            "updated_at": first_review["updated_at"],
            "module_details": {},
        },
    ]
    first_review["private_notes"].append(
        {
            "private_note_id": "note_0001",
            "text": "Private note must not leak.",
            "created_at": first_review["created_at"],
            "updated_at": first_review["updated_at"],
            "module_details": {},
        }
    )
    first_review["feedback"]["standard_feedback"].append(
        {
            "standard_id": STANDARD_A,
            "include_overall_rating": True,
            "include_overall_rationale": True,
            "included_observation_ids": [],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "custom",
                    "text": "Feedback text must not leak.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": first_review["created_at"],
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    )
    pdf_path = _student_dir(tmp_path, "00100") / "exports" / "feedback.pdf"
    md_path = _student_dir(tmp_path, "00100") / "exports" / "feedback.md"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF")
    md_path.write_text("feedback markdown", encoding="utf-8")
    first_review["exports"]["feedback_pdf"] = {
        "path": (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            "00100/exports/feedback.pdf"
        ),
        "generated_at": TIMESTAMP,
        "source_review_updated_at": first_review["updated_at"],
        "module_details": {},
    }
    first_review["exports"]["feedback_markdown"] = {
        "path": (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            "00100/exports/feedback.md"
        ),
        "generated_at": TIMESTAMP,
        "source_review_updated_at": "2026-06-20T12:30:00+00:00",
        "module_details": {},
    }
    _write_json(first_review_path, first_review)
    unrostered_review["overall_standard_ratings"] = [
        {
            "standard_id": "synthetic:outside",
            "rating": 1,
            "rationale": None,
            "include_in_feedback": False,
            "updated_at": unrostered_review["updated_at"],
            "module_details": {},
        }
    ]
    _write_json(unrostered_review_path, unrostered_review)
    originals = {
        assignment_path: assignment_path.read_bytes(),
        roster_path: roster_path.read_bytes(),
        first_manifest: first_manifest.read_bytes(),
        first_review_path: first_review_path.read_bytes(),
        second_manifest: second_manifest.read_bytes(),
        second_review_path: second_review_path.read_bytes(),
        unrostered_manifest: unrostered_manifest.read_bytes(),
        unrostered_review_path: unrostered_review_path.read_bytes(),
        pdf_path: pdf_path.read_bytes(),
        md_path: md_path.read_bytes(),
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
        row_count=4,
        ready_count=3,
        missing_review_count=0,
        invalid_review_count=0,
        missing_submission_count=1,
        invalid_submission_count=0,
        identity_mismatch_count=0,
        returned_without_full_review_count=0,
        feedback_pdf_present_count=1,
        feedback_pdf_stale_count=0,
        created_at=TIMESTAMP,
        overwrote_existing=False,
    )
    with expected_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)
    assert fieldnames[: len(BASE_CSV_COLUMNS) - 1] == BASE_CSV_COLUMNS[:-1]
    assert "score_count" not in fieldnames
    assert "total_score" not in fieldnames
    assert "tag_count" not in fieldnames
    assert f"rating__{STANDARD_A_KEY}" in fieldnames
    assert f"rating_label__{STANDARD_B_KEY}" in fieldnames
    assert [row["student_id"] for row in rows] == ["00100", "00200", "00900", "00300"]

    first = rows[0]
    assert first["student_display_name"] == "Avery Rivera"
    assert first["roster_status"] == "rostered"
    assert first["submission_state"] == "unreviewed"
    assert first["submission_valid"] == "true"
    assert first["review_state"] == "ready_for_export"
    assert first["review_valid"] == "true"
    assert first["minimum_requirement_status"] == "met"
    assert first["returned_without_full_review"] == "false"
    assert first["feedback_pdf_status"] == "present"
    assert first["feedback_pdf_stale"] == "false"
    assert first["feedback_markdown_status"] == "stale"
    assert first["feedback_markdown_stale"] == "true"
    assert first[f"rating__{STANDARD_A_KEY}"] == "3"
    assert first[f"rating_label__{STANDARD_A_KEY}"] == "Secure"
    assert first[f"rating_included_in_feedback__{STANDARD_A_KEY}"] == "true"
    assert first[f"rating_missing__{STANDARD_A_KEY}"] == "false"
    assert first[f"rating__{STANDARD_B_KEY}"] == "9"
    assert first[f"rating_label__{STANDARD_B_KEY}"] == ""
    assert "unknown_rating_value" in first["warnings"]

    missing = rows[2]
    assert missing["student_display_name"] == "Student Missing"
    assert missing["submission_valid"] == "false"
    assert missing[f"rating_missing__{STANDARD_A_KEY}"] == "true"
    assert "missing_submission" in missing["warnings"]

    unrostered = rows[3]
    assert unrostered["roster_status"] == "unrostered_submission"
    assert "unrostered_submission" in unrostered["warnings"]
    assert "rating_for_non_assignment_standard" in unrostered["warnings"]
    csv_text = expected_path.read_text(encoding="utf-8")
    assert "Private note must not leak" not in csv_text
    assert "Feedback text must not leak" not in csv_text
    assert "feedback_comment_id" not in csv_text
    assert "module_details" not in csv_text
    for path, original in originals.items():
        assert path.read_bytes() == original


def test_status_rows_cover_missing_invalid_identity_and_returned(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path)
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
    manifest, review = _records("00600")
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": None,
        "updated_at": review["updated_at"],
    }
    _write_json(_student_dir(tmp_path, "00600") / "submission.json", manifest)
    _write_json(_student_dir(tmp_path, "00600") / "review.json", review)

    result = export_class_review_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )
    rows = _read_rows(result.summary_path)

    assert [";".join(row["warnings"].split(";")[:1]) for row in rows] == [
        "missing_submission",
        "invalid_submission",
        "missing_review",
        "invalid_review",
        "identity_mismatch",
        "",
    ]
    assert rows[-1]["minimum_requirement_status"] == "returned_without_full_review"
    assert rows[-1]["returned_without_full_review"] == "true"
    assert result.missing_submission_count == 1
    assert result.invalid_submission_count == 1
    assert result.missing_review_count == 1
    assert result.invalid_review_count == 1
    assert result.identity_mismatch_count == 1
    assert result.returned_without_full_review_count == 1


def test_no_roster_and_no_submissions_writes_header_only(tmp_path: Path) -> None:
    _write_assignment(tmp_path)

    result = export_class_review_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    assert result.row_count == 0
    assert _read_rows(result.summary_path) == []


def test_missing_assignment_config_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ClassSummaryExportError, match="assignment config"):
        export_class_review_summary(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
        )


def test_overwrite_policy_replaces_only_derived_csv(tmp_path: Path) -> None:
    assignment_path = _write_assignment(tmp_path)
    manifest_path, review_path, _ = _write_records(tmp_path, "00100")
    originals = {
        assignment_path: assignment_path.read_bytes(),
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
    assert _read_rows(second.summary_path)[0]["review_valid"] == "true"
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
    _write_assignment(tmp_path)
    timestamp = datetime(2026, 6, 23, 12, 30, tzinfo=timezone.utc)
    result = export_class_review_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=timestamp
    )
    assert result.created_at == timestamp.isoformat()

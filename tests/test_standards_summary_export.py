"""Tests for teacher-facing standards summary CSV export."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from quillan.standards_summary_export import (
    CSV_COLUMNS,
    ExportedStandardsSummary,
    StandardsSummaryExportError,
    export_standards_summary,
    standards_summary_export_path,
)
from tests.test_class_summary_export import _records, _student_dir, _write_json
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID

TIMESTAMP = "2026-06-23T13:00:00+00:00"


def _tag(
    tag_id: str, standard_id: str | None, polarity: str
) -> dict[str, Any]:
    tag = {
        "tag_id": tag_id,
        "label": f"{polarity} tag",
        "polarity": polarity,
        "created_at": TIMESTAMP,
        "module_details": {},
    }
    if standard_id is not None:
        tag["standard_id"] = standard_id
    return tag


def _comment(
    comment_id: str, standard_id: str | None, included: bool
) -> dict[str, Any]:
    comment = {
        "comment_record_id": comment_id,
        "label": "Selected comment",
        "text": "Snapshotted teacher-selected language.",
        "source": "custom",
        "include_in_feedback": included,
        "created_at": TIMESTAMP,
        "module_details": {},
    }
    if standard_id is not None:
        comment.update(
            {
                "source": "comment_bank",
                "bank_id": "general_writing",
                "comment_id": f"source_{comment_id}",
                "standard_id": standard_id,
            }
        )
    return comment


def _write_review(
    workspace: Path,
    student_id: str,
    *,
    tags: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> tuple[Path, Path]:
    manifest, review = _records(student_id)
    observations = []
    observation_ids_by_standard: dict[str, list[str]] = {}
    for index, tag in enumerate(tags, start=1):
        standard_id = tag.get("standard_id")
        if standard_id is None:
            continue
        observation_id = f"observation_{index:04d}"
        observations.append(
            {
                "observation_id": observation_id,
                "standard_id": standard_id,
                "applicable": True,
                "evidence_present": True,
                "rating": 1,
                "rationale": tag["label"],
                "include_in_feedback": True,
                "updated_at": TIMESTAMP,
                "module_details": {"legacy_polarity": tag["polarity"]},
            }
        )
        observation_ids_by_standard.setdefault(standard_id, []).append(observation_id)
    if observations:
        review["review_units"] = [
            {
                "unit_id": f"unit_{index:04d}",
                "sequence": index,
                "label": f"Whole submission {index}",
                "unit_type": "whole_submission",
                "standard_observations": [observation],
                "module_details": {},
            }
            for index, observation in enumerate(observations, start=1)
        ]
    comments_by_standard: dict[str, list[dict[str, Any]]] = {}
    for index, comment in enumerate(comments, start=1):
        standard_id = comment.get("standard_id")
        if standard_id is None:
            continue
        comments_by_standard.setdefault(standard_id, []).append(
            {
                "feedback_comment_id": f"feedback_comment_{index:04d}",
                "source": "custom",
                "text": comment["text"],
                "reusable_comment_id": None,
                "save_for_reuse": False,
                "include_in_feedback": comment["include_in_feedback"],
                "created_at": TIMESTAMP,
                "module_details": {},
            }
        )
    review["feedback"]["standard_feedback"] = [
        {
            "standard_id": standard_id,
            "include_overall_rating": False,
            "include_overall_rationale": False,
            "included_observation_ids": observation_ids_by_standard.get(standard_id, []),
            "comments": standard_comments,
            "module_details": {},
        }
        for standard_id, standard_comments in sorted(comments_by_standard.items())
    ]
    student_dir = _student_dir(workspace, student_id)
    return (
        _write_json(student_dir / "submission.json", manifest),
        _write_json(student_dir / "review.json", review),
    )


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_aggregates_standards_in_sorted_stable_rows_without_mutation(
    tmp_path: Path,
) -> None:
    first_paths = _write_review(
        tmp_path,
        "00100",
        tags=[
            _tag("tag_1", "synthetic:W.Z", "positive"),
            _tag("tag_2", "synthetic:W.A", "developing"),
            _tag("tag_3", "synthetic:W.A", "negative"),
            _tag("tag_4", None, "neutral"),
        ],
        comments=[
            _comment("comment_1", "synthetic:W.A", True),
            _comment("comment_2", "synthetic:W.A", False),
            _comment("comment_3", None, True),
        ],
    )
    second_paths = _write_review(
        tmp_path,
        "00200",
        tags=[
            _tag("tag_1", "synthetic:W.A", "neutral"),
            _tag("tag_2", "synthetic:W.A", "positive"),
        ],
        comments=[
            _comment("comment_1", "synthetic:W.A", True),
            _comment("comment_2", "synthetic:W.Z", False),
        ],
    )
    evidence = tmp_path / "evidence.pdf"
    evidence.write_bytes(b"never read")
    bank = tmp_path / "comment_banks" / "bank.json"
    bank.parent.mkdir()
    bank.write_text("{not json", encoding="utf-8")
    originals = {
        path: path.read_bytes()
        for path in (*first_paths, *second_paths, evidence, bank)
    }

    result = export_standards_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    expected_path = standards_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    assert result == ExportedStandardsSummary(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        summary_path=expected_path,
        summary_relative_path=(
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/exports/"
            "standards_summary.csv"
        ),
        row_count=2,
        standard_count=2,
        student_count=2,
        review_count=2,
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
    assert [row["standard_id"] for row in rows] == ["synthetic:W.A", "synthetic:W.Z"]
    first = rows[0]
    assert first["student_count"] == "2"
    assert first["tag_student_count"] == "2"
    assert first["comment_student_count"] == "2"
    assert first["tag_count"] == "4"
    assert first["positive_tag_count"] == "1"
    assert first["developing_tag_count"] == "1"
    assert first["negative_tag_count"] == "1"
    assert first["neutral_tag_count"] == "1"
    assert first["selected_comment_count"] == "3"
    assert first["included_comment_count"] == "2"
    assert first["excluded_comment_count"] == "1"
    assert first["review_count"] == "2"
    assert first["source"] == "review_record_v2"
    assert rows[1]["student_count"] == "2"
    assert rows[1]["tag_student_count"] == "1"
    assert rows[1]["comment_student_count"] == "1"
    for path, original in originals.items():
        assert path.read_bytes() == original


def test_non_ready_counts_repeat_on_rows_and_do_not_abort(tmp_path: Path) -> None:
    _write_review(
        tmp_path,
        "00100",
        tags=[_tag("tag_1", "synthetic:W.A", "positive")],
        comments=[],
    )
    _student_dir(tmp_path, "00200").mkdir(parents=True)
    manifest, _ = _records("00300")
    _write_json(_student_dir(tmp_path, "00300") / "submission.json", manifest)
    manifest, _ = _records("00400")
    _write_json(_student_dir(tmp_path, "00400") / "submission.json", manifest)
    (_student_dir(tmp_path, "00400") / "review.json").write_text(
        "{", encoding="utf-8"
    )
    _write_json(
        _student_dir(tmp_path, "00500") / "submission.json", {"invalid": True}
    )
    manifest, review = _records("other_student")
    _write_json(_student_dir(tmp_path, "00600") / "submission.json", manifest)
    _write_json(_student_dir(tmp_path, "00600") / "review.json", review)

    result = export_standards_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    assert result.review_count == 1
    assert result.missing_submission_count == 1
    assert result.missing_review_count == 1
    assert result.invalid_review_count == 1
    assert result.invalid_submission_count == 1
    assert result.identity_mismatch_count == 1
    row = _read_rows(result.summary_path)[0]
    assert row["missing_submission_count"] == "1"
    assert row["missing_review_count"] == "1"
    assert row["invalid_review_count"] == "1"
    assert row["invalid_submission_count"] == "1"
    assert row["identity_mismatch_count"] == "1"


def test_no_linked_artifacts_writes_header_only(tmp_path: Path) -> None:
    _write_review(
        tmp_path,
        "00100",
        tags=[_tag("tag_1", None, "neutral")],
        comments=[_comment("comment_1", None, True)],
    )

    result = export_standards_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    assert result.row_count == result.standard_count == 0
    assert result.review_count == 1
    assert _read_rows(result.summary_path) == []
    assert result.summary_path.read_text(encoding="utf-8").splitlines() == [
        ",".join(CSV_COLUMNS)
    ]


def test_no_valid_reviews_writes_header_only_with_counts(tmp_path: Path) -> None:
    _student_dir(tmp_path, "00100").mkdir(parents=True)

    result = export_standards_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    assert result.row_count == result.review_count == 0
    assert result.missing_submission_count == 1
    assert _read_rows(result.summary_path) == []


def test_missing_submissions_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(StandardsSummaryExportError, match="does not exist"):
        export_standards_summary(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
        )


def test_overwrite_replaces_only_the_derived_csv(tmp_path: Path) -> None:
    paths = _write_review(
        tmp_path,
        "00100",
        tags=[_tag("tag_1", "synthetic:W.A", "positive")],
        comments=[],
    )
    originals = {path: path.read_bytes() for path in paths}
    first = export_standards_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )
    first.summary_path.write_text("manual edit", encoding="utf-8")

    with pytest.raises(StandardsSummaryExportError, match="--overwrite"):
        export_standards_summary(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
        )
    assert first.summary_path.read_text(encoding="utf-8") == "manual edit"

    second = export_standards_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        overwrite=True,
        created_at=TIMESTAMP,
    )
    assert second.overwrote_existing is True
    assert _read_rows(second.summary_path)[0]["standard_id"] == "synthetic:W.A"
    for path, original in originals.items():
        assert path.read_bytes() == original


@pytest.mark.parametrize(
    "timestamp",
    ["not-a-time", "2026-06-23T13:00:00", datetime(2026, 6, 23, 13), 123],
)
def test_invalid_timestamp_is_rejected(
    tmp_path: Path, timestamp: object
) -> None:
    with pytest.raises(StandardsSummaryExportError, match="timezone-aware"):
        export_standards_summary(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            created_at=timestamp,  # type: ignore[arg-type]
        )

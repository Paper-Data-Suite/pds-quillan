"""Tests for submission metadata loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.submissions import (
    SubmissionMetadataError,
    load_submission_metadata,
)


def _valid_submission_metadata() -> dict[str, object]:
    """Return valid synthetic submission metadata."""
    return {
        "submission_id": "sub_stu_0001_v1",
        "assignment_id": "villainy_final_essay_synthetic",
        "class_id": "english12_period3_synthetic",
        "student_id": "stu_0001",
        "source_type": "manual_entry",
        "text_file": "submission.txt",
        "captured_at": "2026-06-07T12:00:00",
        "status": "captured",
        "version": 1,
    }


def _write_metadata(tmp_path: Path, metadata: object) -> Path:
    """Write metadata to the test submission path."""
    metadata_path = tmp_path / "submission.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return metadata_path


def test_load_valid_submission_metadata(tmp_path: Path) -> None:
    metadata = _valid_submission_metadata()

    assert load_submission_metadata(_write_metadata(tmp_path, metadata)) == metadata


def test_missing_required_field_raises_error(tmp_path: Path) -> None:
    metadata = _valid_submission_metadata()
    del metadata["captured_at"]

    with pytest.raises(
        SubmissionMetadataError, match="Missing required field 'captured_at'"
    ):
        load_submission_metadata(_write_metadata(tmp_path, metadata))


def test_invalid_json_raises_error(tmp_path: Path) -> None:
    metadata_path = tmp_path / "submission.json"
    metadata_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(SubmissionMetadataError, match="not valid JSON"):
        load_submission_metadata(metadata_path)


def test_valid_json_that_is_not_object_raises_error(tmp_path: Path) -> None:
    with pytest.raises(SubmissionMetadataError, match="must be a JSON object"):
        load_submission_metadata(_write_metadata(tmp_path, []))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_type", "email"),
        ("status", "auto_graded"),
    ],
)
def test_invalid_allowed_value_raises_error(
    tmp_path: Path, field: str, value: str
) -> None:
    metadata = _valid_submission_metadata()
    metadata[field] = value

    with pytest.raises(SubmissionMetadataError, match=field):
        load_submission_metadata(_write_metadata(tmp_path, metadata))


@pytest.mark.parametrize(
    "field",
    ["submission_id", "assignment_id", "class_id", "student_id"],
)
def test_invalid_identifier_raises_error(tmp_path: Path, field: str) -> None:
    metadata = _valid_submission_metadata()
    metadata[field] = "../unsafe"

    with pytest.raises(SubmissionMetadataError, match=field):
        load_submission_metadata(_write_metadata(tmp_path, metadata))


@pytest.mark.parametrize(
    "field",
    [
        "submission_id",
        "assignment_id",
        "class_id",
        "student_id",
        "source_type",
        "text_file",
        "captured_at",
        "status",
    ],
)
def test_empty_required_string_raises_error(tmp_path: Path, field: str) -> None:
    metadata = _valid_submission_metadata()
    metadata[field] = ""

    with pytest.raises(SubmissionMetadataError, match=field):
        load_submission_metadata(_write_metadata(tmp_path, metadata))


@pytest.mark.parametrize(
    "text_file",
    [
        "/absolute/submission.txt",
        r"C:\absolute\submission.txt",
        r"C:drive-relative\submission.txt",
        r"\root-relative\submission.txt",
    ],
)
def test_absolute_text_file_raises_error(tmp_path: Path, text_file: str) -> None:
    metadata = _valid_submission_metadata()
    metadata["text_file"] = text_file

    with pytest.raises(SubmissionMetadataError, match="relative path"):
        load_submission_metadata(_write_metadata(tmp_path, metadata))


@pytest.mark.parametrize(
    "text_file",
    [
        "../submission.txt",
        "drafts/../../submission.txt",
        r"..\submission.txt",
    ],
)
def test_parent_traversal_in_text_file_raises_error(
    tmp_path: Path, text_file: str
) -> None:
    metadata = _valid_submission_metadata()
    metadata["text_file"] = text_file

    with pytest.raises(SubmissionMetadataError, match="parent-directory traversal"):
        load_submission_metadata(_write_metadata(tmp_path, metadata))


@pytest.mark.parametrize("version", [0, -1])
def test_non_positive_version_raises_error(tmp_path: Path, version: int) -> None:
    metadata = _valid_submission_metadata()
    metadata["version"] = version

    with pytest.raises(SubmissionMetadataError, match="positive integer"):
        load_submission_metadata(_write_metadata(tmp_path, metadata))


@pytest.mark.parametrize("version", [1.5, "1", None])
def test_non_integer_version_raises_error(tmp_path: Path, version: object) -> None:
    metadata = _valid_submission_metadata()
    metadata["version"] = version

    with pytest.raises(SubmissionMetadataError, match="positive integer"):
        load_submission_metadata(_write_metadata(tmp_path, metadata))


def test_boolean_version_raises_error(tmp_path: Path) -> None:
    metadata = _valid_submission_metadata()
    metadata["version"] = True

    with pytest.raises(SubmissionMetadataError, match="positive integer"):
        load_submission_metadata(_write_metadata(tmp_path, metadata))


def test_missing_file_raises_error() -> None:
    with pytest.raises(SubmissionMetadataError, match="Submission metadata not found"):
        load_submission_metadata("missing_submission.json")

"""Tests for standards profile loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.standards import StandardsProfileError, load_standards_profile


def test_load_valid_standards_profile(tmp_path: Path) -> None:
    profile_path = tmp_path / "standards.json"
    profile_data = {
        "profile_id": "english_12_njsls_synthetic",
        "subject": "English Language Arts",
        "course": "English 12",
        "standards": [
            {
                "code": "W.AW.11-12.1",
                "short_name": "Argument Writing",
                "description": "Write arguments using claims, reasoning, and evidence.",
                "comments": [
                    {
                        "comment_id": "clear_claim",
                        "label": "Clear claim",
                        "polarity": "positive",
                    }
                ],
            }
        ],
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    loaded_profile = load_standards_profile(profile_path)

    assert loaded_profile == profile_data


def test_missing_top_level_field_raises_error(tmp_path: Path) -> None:
    profile_path = tmp_path / "standards.json"
    profile_data = {
        "profile_id": "english_12_njsls_synthetic",
        "subject": "English Language Arts",
        "standards": [],
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    with pytest.raises(StandardsProfileError, match="Missing required field 'course'"):
        load_standards_profile(profile_path)


def test_empty_standards_list_raises_error(tmp_path: Path) -> None:
    profile_path = tmp_path / "standards.json"
    profile_data = {
        "profile_id": "english_12_njsls_synthetic",
        "subject": "English Language Arts",
        "course": "English 12",
        "standards": [],
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    with pytest.raises(StandardsProfileError, match="must not be empty"):
        load_standards_profile(profile_path)


def test_invalid_comment_polarity_raises_error(tmp_path: Path) -> None:
    profile_path = tmp_path / "standards.json"
    profile_data = {
        "profile_id": "english_12_njsls_synthetic",
        "subject": "English Language Arts",
        "course": "English 12",
        "standards": [
            {
                "code": "W.AW.11-12.1",
                "short_name": "Argument Writing",
                "description": "Write arguments using claims, reasoning, and evidence.",
                "comments": [
                    {
                        "comment_id": "clear_claim",
                        "label": "Clear claim",
                        "polarity": "strong",
                    }
                ],
            }
        ],
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    with pytest.raises(StandardsProfileError, match="Invalid polarity"):
        load_standards_profile(profile_path)


def test_missing_file_raises_clear_error() -> None:
    with pytest.raises(StandardsProfileError, match="Standards profile not found"):
        load_standards_profile("missing_standards_file.json")


def test_invalid_json_raises_clear_error(tmp_path: Path) -> None:
    profile_path = tmp_path / "standards.json"
    profile_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(StandardsProfileError, match="not valid JSON"):
        load_standards_profile(profile_path)
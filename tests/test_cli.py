"""Tests for the Quillan command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.cli import main


def test_cli_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])

    captured = capsys.readouterr()

    assert error.value.code == 0
    assert "Quillan: standards-based writing evidence capture" in captured.out
    assert "validate-standards" in captured.out


def test_cli_validates_standards_profile(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
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

    main(["validate-standards", str(profile_path)])

    captured = capsys.readouterr()

    assert "Valid standards profile: english_12_njsls_synthetic" in captured.out


def test_cli_reports_invalid_standards_profile(tmp_path: Path) -> None:
    profile_path = tmp_path / "standards.json"
    profile_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        main(["validate-standards", str(profile_path)])

    assert "Invalid standards profile" in str(error.value)

def test_cli_validates_assignment_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = {
        "assignment_id": "villainy_final_essay_synthetic",
        "title": "Villainy Final Essay",
        "class_ids": ["english12_period3_synthetic"],
        "writing_type": "literary argument essay",
        "standards_profile_id": "english_12_njsls_synthetic",
        "tagging_mode": "focus",
        "focus_standards": [
            "W.AW.11-12.1",
            "W.WP.11-12.4",
        ],
        "basic_requirements": {
            "paragraphs_min": 4,
            "paragraphs_max": 6,
            "word_count_min": 500,
            "required_elements": [
                "thesis",
                "textual evidence",
                "comparative reasoning",
            ],
        },
        "rubric_id": "argument_essay_4pt_synthetic",
    }
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    main(["validate-assignment", str(assignment_path)])

    captured = capsys.readouterr()

    assert "Valid assignment config: villainy_final_essay_synthetic" in captured.out


def test_cli_reports_invalid_assignment_config(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        main(["validate-assignment", str(assignment_path)])

    assert "Invalid assignment config" in str(error.value)
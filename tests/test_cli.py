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
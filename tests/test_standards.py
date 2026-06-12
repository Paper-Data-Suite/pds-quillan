"""Tests for standards profile loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.standards import StandardsProfileError, load_standards_profile


def _valid_profile() -> dict[str, Any]:
    """Return a valid synthetic standards profile."""
    return {
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
                        "comment_id": "evidence_needs_explanation",
                        "label": "Evidence needs more explanation",
                        "polarity": "developing",
                        "severity_default": 2,
                        "feedback_template": (
                            "Explain how the evidence supports the claim."
                        ),
                        "subskills": ["reasoning", "evidence_explanation"],
                        "hotwords": ["because", "this shows"],
                    }
                ],
            }
        ],
    }


def _write_profile(tmp_path: Path, profile: object) -> Path:
    """Write a JSON value to a temporary standards profile."""
    profile_path = tmp_path / "standards.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    return profile_path


def test_load_valid_standards_profile(tmp_path: Path) -> None:
    profile = _valid_profile()

    assert load_standards_profile(_write_profile(tmp_path, profile)) == profile


def test_optional_lists_may_be_empty_or_omitted(tmp_path: Path) -> None:
    profile = _valid_profile()
    comment = profile["standards"][0]["comments"][0]
    comment.pop("severity_default")
    comment.pop("feedback_template")
    comment["subskills"] = []
    comment["hotwords"] = []

    assert load_standards_profile(_write_profile(tmp_path, profile)) == profile


def test_standard_comments_may_be_empty(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"] = []

    assert load_standards_profile(_write_profile(tmp_path, profile)) == profile


def test_duplicate_standard_codes_are_rejected(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["standards"].append(
        {
            "code": "W.AW.11-12.1",
            "short_name": "Argument Writing Duplicate",
            "description": "Duplicate standard code.",
            "comments": [],
        }
    )

    with pytest.raises(StandardsProfileError, match="Duplicate standard code"):
        load_standards_profile(_write_profile(tmp_path, profile))


def test_duplicate_comment_ids_within_standard_are_rejected(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"].append(
        {
            "comment_id": "evidence_needs_explanation",
            "label": "Evidence needs more explanation duplicate",
            "polarity": "developing",
        }
    )

    with pytest.raises(StandardsProfileError, match="Duplicate comment_id"):
        load_standards_profile(_write_profile(tmp_path, profile))


def test_duplicate_comment_ids_under_different_standards_are_allowed(
    tmp_path: Path,
) -> None:
    profile = _valid_profile()
    profile["standards"].append(
        {
            "code": "W.WP.11-12.4",
            "short_name": "Writing Process",
            "description": "Develop and strengthen writing through revision.",
            "comments": [
                {
                    "comment_id": "evidence_needs_explanation",
                    "label": "Revision needs more explanation",
                    "polarity": "developing",
                }
            ],
        }
    )

    assert load_standards_profile(_write_profile(tmp_path, profile)) == profile


def test_missing_file_raises_clear_error() -> None:
    with pytest.raises(StandardsProfileError, match="Standards profile not found"):
        load_standards_profile("missing_standards_file.json")


def test_invalid_json_raises_clear_error(tmp_path: Path) -> None:
    profile_path = tmp_path / "standards.json"
    profile_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(StandardsProfileError, match="not valid JSON"):
        load_standards_profile(profile_path)


def test_valid_json_that_is_not_object_raises_error(tmp_path: Path) -> None:
    with pytest.raises(StandardsProfileError, match="must be a JSON object"):
        load_standards_profile(_write_profile(tmp_path, []))


@pytest.mark.parametrize("field", ["profile_id", "subject", "course", "standards"])
def test_missing_top_level_field_raises_error(tmp_path: Path, field: str) -> None:
    profile = _valid_profile()
    del profile[field]

    with pytest.raises(StandardsProfileError, match=f"required field '{field}'"):
        load_standards_profile(_write_profile(tmp_path, profile))


def test_invalid_profile_identifier_raises_error(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["profile_id"] = "../unsafe"

    with pytest.raises(StandardsProfileError, match="profile_id"):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("field", ["subject", "course"])
@pytest.mark.parametrize("value", ["", "   ", 123])
def test_profile_string_must_be_non_empty(
    tmp_path: Path, field: str, value: object
) -> None:
    profile = _valid_profile()
    profile[field] = value

    with pytest.raises(StandardsProfileError, match=field):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("value", ["W.AW.11-12.1", {}, None])
def test_standards_must_be_list(tmp_path: Path, value: object) -> None:
    profile = _valid_profile()
    profile["standards"] = value

    with pytest.raises(StandardsProfileError, match="standards.*list"):
        load_standards_profile(_write_profile(tmp_path, profile))


def test_standards_must_not_be_empty(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["standards"] = []

    with pytest.raises(StandardsProfileError, match="standards.*not be empty"):
        load_standards_profile(_write_profile(tmp_path, profile))


def test_standard_must_be_object(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["standards"] = ["W.AW.11-12.1"]

    with pytest.raises(StandardsProfileError, match="standard must be an object"):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("field", ["code", "short_name", "description", "comments"])
def test_missing_standard_field_raises_error(tmp_path: Path, field: str) -> None:
    profile = _valid_profile()
    del profile["standards"][0][field]

    with pytest.raises(StandardsProfileError, match=f"required field '{field}'"):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("field", ["code", "short_name", "description"])
@pytest.mark.parametrize("value", ["", "   ", 123])
def test_standard_string_must_be_non_empty(
    tmp_path: Path, field: str, value: object
) -> None:
    profile = _valid_profile()
    profile["standards"][0][field] = value

    with pytest.raises(StandardsProfileError, match=field):
        load_standards_profile(_write_profile(tmp_path, profile))


def test_comments_must_be_list(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"] = {}

    with pytest.raises(StandardsProfileError, match="Comments.*must be a list"):
        load_standards_profile(_write_profile(tmp_path, profile))


def test_comment_must_be_object(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"] = ["clear_claim"]

    with pytest.raises(StandardsProfileError, match="comment.*must be an object"):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("field", ["comment_id", "label", "polarity"])
def test_missing_comment_field_raises_error(tmp_path: Path, field: str) -> None:
    profile = _valid_profile()
    del profile["standards"][0]["comments"][0][field]

    with pytest.raises(StandardsProfileError, match=f"required field '{field}'"):
        load_standards_profile(_write_profile(tmp_path, profile))


def test_invalid_comment_identifier_raises_error(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"][0]["comment_id"] = "Clear Claim"

    with pytest.raises(StandardsProfileError, match="comment_id"):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("value", ["", "   ", 123])
def test_comment_label_must_be_non_empty(tmp_path: Path, value: object) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"][0]["label"] = value

    with pytest.raises(StandardsProfileError, match="label"):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("value", ["strong", "", 1, ["positive"]])
def test_invalid_comment_polarity_raises_error(tmp_path: Path, value: object) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"][0]["polarity"] = value

    with pytest.raises(StandardsProfileError, match="polarity"):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("value", [-1, 1.5, "2", None])
def test_invalid_severity_default_raises_error(tmp_path: Path, value: object) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"][0]["severity_default"] = value

    with pytest.raises(StandardsProfileError, match="severity_default"):
        load_standards_profile(_write_profile(tmp_path, profile))


def test_boolean_severity_default_raises_error(tmp_path: Path) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"][0]["severity_default"] = True

    with pytest.raises(StandardsProfileError, match="severity_default"):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("value", ["", "   ", 123])
def test_feedback_template_must_be_non_empty(tmp_path: Path, value: object) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"][0]["feedback_template"] = value

    with pytest.raises(StandardsProfileError, match="feedback_template"):
        load_standards_profile(_write_profile(tmp_path, profile))


@pytest.mark.parametrize("field", ["subskills", "hotwords"])
@pytest.mark.parametrize("value", ["claim", [""], ["   "], [1]])
def test_teacher_metadata_must_be_list_of_non_empty_strings(
    tmp_path: Path, field: str, value: object
) -> None:
    profile = _valid_profile()
    profile["standards"][0]["comments"][0][field] = value

    with pytest.raises(StandardsProfileError, match=field):
        load_standards_profile(_write_profile(tmp_path, profile))

"""Tests for assignment standards selection against pds-core libraries."""

from __future__ import annotations

import pytest

from pds_core.standards import StandardDefinition, StandardsLibrary, StandardsProfile

from quillan.assignments import (
    AssignmentConfigError,
    validate_assignment_config,
    validate_assignment_standards_selection,
)


def _valid_assignment_config() -> dict[str, object]:
    return {
        "assignment_id": "villainy_final_essay_synthetic",
        "title": "Villainy Final Essay",
        "class_ids": ["english12_period3_synthetic"],
        "writing_type": "literary argument essay",
        "standards_profile_id": "english12_2023_njsls",
        "tagging_mode": "focus",
        "focus_standards": [
            "nj_ela_2023_rl_cr_11_12_1",
            "nj_ela_2023_w_aw_11_12_1",
        ],
        "basic_requirements": {
            "paragraphs_min": 4,
            "paragraphs_max": 6,
            "word_count_min": 500,
            "required_elements": ["thesis", "textual evidence"],
        },
        "rubric_id": "argument_essay_4pt_synthetic",
    }


def _standards_library() -> StandardsLibrary:
    standards = (
        StandardDefinition(
            standard_id="nj_ela_2023_rl_cr_11_12_1",
            code="RL.CR.11-12.1",
            source="NJSLS-ELA 2023",
            short_name="Close Reading Evidence",
            description="Cite strong and thorough textual evidence.",
        ),
        StandardDefinition(
            standard_id="nj_ela_2023_w_aw_11_12_1",
            code="W.AW.11-12.1",
            source="NJSLS-ELA 2023",
            short_name="Argument Writing",
            description="Write arguments supported by evidence.",
        ),
        StandardDefinition(
            standard_id="nj_ela_2023_l_vi_11_12_4",
            code="L.VI.11-12.4",
            source="NJSLS-ELA 2023",
            short_name="Vocabulary in Context",
            description="Determine or clarify meaning of unknown words.",
        ),
    )
    profiles = (
        StandardsProfile(
            profile_id="english12_2023_njsls",
            standards=(
                "nj_ela_2023_rl_cr_11_12_1",
                "nj_ela_2023_w_aw_11_12_1",
            ),
        ),
        StandardsProfile(
            profile_id="english12_2023_language",
            standards=("nj_ela_2023_l_vi_11_12_4",),
        ),
    )
    return StandardsLibrary(standards=standards, profiles=profiles)


def test_assignment_standards_selection_accepts_valid_profile_and_focus() -> None:
    assert validate_assignment_standards_selection(
        _valid_assignment_config(),
        _standards_library(),
    ) == (
        "nj_ela_2023_rl_cr_11_12_1",
        "nj_ela_2023_w_aw_11_12_1",
    )


def test_assignment_standards_selection_returns_normalized_focus_ids() -> None:
    assignment = _valid_assignment_config()
    assignment["standards_profile_id"] = " english12_2023_njsls "
    assignment["focus_standards"] = [" nj_ela_2023_rl_cr_11_12_1 "]

    assert validate_assignment_standards_selection(
        assignment,
        _standards_library(),
    ) == ("nj_ela_2023_rl_cr_11_12_1",)


def test_assignment_standards_selection_rejects_missing_profile_id() -> None:
    assignment = _valid_assignment_config()
    del assignment["standards_profile_id"]

    with pytest.raises(AssignmentConfigError, match="standards_profile_id"):
        validate_assignment_standards_selection(assignment, _standards_library())


def test_assignment_standards_selection_rejects_unknown_profile_id() -> None:
    assignment = _valid_assignment_config()
    assignment["standards_profile_id"] = "missing_profile"

    with pytest.raises(
        AssignmentConfigError,
        match="standards_profile_id.*missing_profile",
    ):
        validate_assignment_standards_selection(assignment, _standards_library())


def test_assignment_standards_selection_rejects_unknown_focus_standard() -> None:
    assignment = _valid_assignment_config()
    assignment["focus_standards"] = ["nj_ela_2023_missing"]

    with pytest.raises(
        AssignmentConfigError,
        match="focus_standards.*nj_ela_2023_missing",
    ):
        validate_assignment_standards_selection(assignment, _standards_library())


def test_assignment_standards_selection_rejects_standard_outside_profile() -> None:
    assignment = _valid_assignment_config()
    assignment["focus_standards"] = ["nj_ela_2023_l_vi_11_12_4"]

    with pytest.raises(
        AssignmentConfigError,
        match="focus_standards.*nj_ela_2023_l_vi_11_12_4",
    ):
        validate_assignment_standards_selection(assignment, _standards_library())


def test_assignment_standards_selection_rejects_duplicate_focus_standards() -> None:
    assignment = _valid_assignment_config()
    assignment["focus_standards"] = [
        "nj_ela_2023_rl_cr_11_12_1",
        " nj_ela_2023_rl_cr_11_12_1 ",
    ]

    with pytest.raises(AssignmentConfigError, match="duplicate standard IDs"):
        validate_assignment_standards_selection(assignment, _standards_library())


def test_assignment_standards_selection_accepts_empty_focus_standards() -> None:
    assignment = _valid_assignment_config()
    assignment["focus_standards"] = []

    assert validate_assignment_standards_selection(
        assignment,
        _standards_library(),
    ) == ()


def test_structural_assignment_validation_accepts_valid_config_without_library() -> None:
    validate_assignment_config(_valid_assignment_config())


def test_structural_assignment_validation_rejects_malformed_config_without_library() -> None:
    assignment = _valid_assignment_config()
    assignment["focus_standards"] = "nj_ela_2023_rl_cr_11_12_1"

    with pytest.raises(AssignmentConfigError, match="focus_standards.*list"):
        validate_assignment_config(assignment)

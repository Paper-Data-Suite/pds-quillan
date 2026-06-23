"""Tests for shared PDS assignment storage paths."""

from __future__ import annotations

from pathlib import Path

from pds_core.routes import (
    assignment_config_path as pds_assignment_config_path,
    assignment_dir as pds_assignment_dir,
    assignment_scans_dir as pds_assignment_scans_dir,
    assignment_submissions_dir as pds_assignment_submissions_dir,
    assignment_templates_dir as pds_assignment_templates_dir,
    student_submission_dir as pds_student_submission_dir,
)

from quillan.storage import (
    assignment_config_path,
    assignment_dir,
    assignment_scans_dir,
    assignment_submissions_dir,
    assignment_templates_dir,
    student_submission_dir,
)

CLASS_ID = "english12_period3_synthetic"
ASSIGNMENT_ID = "villainy_final_essay_synthetic"
STUDENT_ID = "stu_0001"


def test_assignment_paths_use_shared_pds_routes(tmp_path: Path) -> None:
    expected_dir = tmp_path / "classes" / CLASS_ID / "assignments" / ASSIGNMENT_ID

    assert assignment_dir(tmp_path, CLASS_ID, ASSIGNMENT_ID) == expected_dir
    assert assignment_dir(tmp_path, CLASS_ID, ASSIGNMENT_ID) == pds_assignment_dir(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    assert assignment_config_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ) == pds_assignment_config_path(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert assignment_submissions_dir(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ) == pds_assignment_submissions_dir(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert assignment_scans_dir(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ) == pds_assignment_scans_dir(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    assert assignment_templates_dir(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    ) == pds_assignment_templates_dir(tmp_path, CLASS_ID, ASSIGNMENT_ID)


def test_student_submission_dir_uses_shared_pds_route(tmp_path: Path) -> None:
    expected_dir = pds_student_submission_dir(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    )

    assert (
        student_submission_dir(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
        == expected_dir
    )

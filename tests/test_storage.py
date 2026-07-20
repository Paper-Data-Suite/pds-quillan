"""Tests for module-qualified Quillan assignment storage paths."""

from __future__ import annotations

import inspect
from pathlib import Path

import quillan.printable_response_workflows as printable_workflows
import quillan.storage as storage
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


def test_path_modules_do_not_import_removed_assignment_helpers() -> None:
    storage_source = inspect.getsource(storage)
    discovery_source = inspect.getsource(printable_workflows)

    assert "from pds_core.routes import" not in storage_source
    assert "class_assignments_dir" not in discovery_source
    assert ' / "assignments"' not in storage_source
    assert ' / "assignments"' not in discovery_source


def test_assignment_paths_use_module_qualified_work(tmp_path: Path) -> None:
    workspace = tmp_path / "absent"
    expected_dir = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
    )

    assert assignment_dir(workspace, CLASS_ID, ASSIGNMENT_ID) == expected_dir
    assert assignment_config_path(workspace, CLASS_ID, ASSIGNMENT_ID) == (
        expected_dir / "assignment.json"
    )
    assert assignment_submissions_dir(workspace, CLASS_ID, ASSIGNMENT_ID) == (
        expected_dir / "submissions"
    )
    assert assignment_scans_dir(workspace, CLASS_ID, ASSIGNMENT_ID) == (
        expected_dir / "scans"
    )
    assert assignment_templates_dir(workspace, CLASS_ID, ASSIGNMENT_ID) == (
        expected_dir / "templates"
    )
    assert not workspace.exists()


def test_student_submission_dir_uses_module_qualified_work(tmp_path: Path) -> None:
    workspace = tmp_path / "absent"
    expected_dir = (
        assignment_submissions_dir(workspace, CLASS_ID, ASSIGNMENT_ID) / STUDENT_ID
    )

    assert (
        student_submission_dir(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
        == expected_dir
    )
    assert not workspace.exists()

"""Installed acceptance for Issue #414 selected-review read boundaries."""

from __future__ import annotations

import argparse
import builtins
import importlib
import importlib.metadata as metadata
import json
from pathlib import Path
from typing import Any

from pds_core.classes import write_class_roster
from pds_core.rosters import create_roster

import quillan.review_dashboard as dashboard_module
import quillan.review_menu as review_menu
import quillan.review_read_context as read_context_module
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "issue414_installed_class"
ASSIGNMENT_ID = "issue414_installed_assignment"
STUDENT_IDS = tuple(f"{index:05d}" for index in range(1, 31))
TIMESTAMP = "2026-09-23T12:00:00+00:00"


def _module_origin(module_name: str) -> Path:
    module = importlib.import_module(module_name)
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw:
        raise AssertionError(f"{module_name} has no import origin")
    return Path(raw).resolve()


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _assignment() -> dict[str, Any]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Issue 414 Installed Review",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Synthetic installed acceptance.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["synthetic:W.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "synthetic_scale",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Synthetic level.",
                }
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def _manifest(student_id: str) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": student_id,
        "expected_pages": 1,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def _prepare(workspace: Path) -> None:
    if workspace.exists() and any(workspace.iterdir()):
        raise AssertionError("selected-review acceptance workspace must be empty")
    workspace.mkdir(parents=True, exist_ok=True)
    students = tuple(
        {
            "student_id": student_id,
            "last_name": f"Student{index:02d}",
            "first_name": f"Synthetic{index:02d}",
            "period": "3",
        }
        for index, student_id in enumerate(STUDENT_IDS, start=1)
    )
    write_class_roster(workspace, create_roster(CLASS_ID, students))
    assignment_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "modules"
        / "quillan"
        / "work"
        / ASSIGNMENT_ID
        / "assignment.json"
    )
    assignment_path.parent.mkdir(parents=True, exist_ok=True)
    assignment_path.write_text(
        json.dumps(_assignment(), sort_keys=True),
        encoding="utf-8",
    )
    for student_id in STUDENT_IDS:
        write_submission_manifest(
            submission_manifest_path(
                workspace,
                CLASS_ID,
                ASSIGNMENT_ID,
                student_id,
            ),
            _manifest(student_id),
        )
        review = build_empty_review_record(
            class_id=CLASS_ID,
            assignment_id=ASSIGNMENT_ID,
            student_id=student_id,
            created_at=TIMESTAMP,
        )
        write_review_record(
            review_record_path(
                workspace,
                CLASS_ID,
                ASSIGNMENT_ID,
                student_id,
            ),
            review,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-quillan-version", required=True)
    parser.add_argument("--expected-core-version", required=True)
    args = parser.parse_args()

    repository = args.repository.resolve()
    if metadata.version("quillan") != args.expected_quillan_version:
        raise AssertionError("installed Quillan version mismatch")
    if metadata.version("pds-core") != args.expected_core_version:
        raise AssertionError("installed Core version mismatch")
    for module_name in ("quillan", "pds_core"):
        if _module_origin(module_name).is_relative_to(repository):
            raise AssertionError(f"{module_name} import is source-shadowed")

    workspace = args.workspace.resolve()
    _prepare(workspace)
    before = _snapshot(workspace)
    counts = {"assignment": 0, "roster": 0, "observations": 0}

    read_context_hooks: Any = read_context_module
    dashboard_hooks: Any = dashboard_module
    review_menu_hooks: Any = review_menu
    original_assignment = read_context_hooks.load_quillan_assignment_context
    original_roster = read_context_hooks.load_class_roster
    original_observations = (
        read_context_hooks.group_response_page_observations_by_student
    )
    original_input = builtins.input

    def counted_assignment(*call_args: Any, **call_kwargs: Any) -> Any:
        counts["assignment"] += 1
        return original_assignment(*call_args, **call_kwargs)

    def counted_roster(*call_args: Any, **call_kwargs: Any) -> Any:
        counts["roster"] += 1
        return original_roster(*call_args, **call_kwargs)

    def counted_observations(*call_args: Any, **call_kwargs: Any) -> Any:
        counts["observations"] += 1
        return original_observations(*call_args, **call_kwargs)

    def forbidden_legacy(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("installed selected root invoked redundant legacy read")

    def forbidden_scan(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("installed routine navigation invoked scan diagnostics")

    read_context_hooks.load_quillan_assignment_context = counted_assignment
    read_context_hooks.load_class_roster = counted_roster
    read_context_hooks.group_response_page_observations_by_student = (
        counted_observations
    )
    dashboard_hooks.discover_scan_review_items = forbidden_scan
    review_menu_hooks.list_assignment_submission_status = forbidden_legacy
    review_menu_hooks.build_student_review_status = forbidden_legacy
    review_menu_hooks.build_review_student_navigation = forbidden_legacy
    review_menu_hooks.print_active_context = forbidden_legacy
    import quillan.menu as menu_module

    menu_module.clear_screen = lambda: None
    builtins.input = lambda _prompt="": "b"
    try:
        result = review_menu._launch_selected_student_review(
            workspace,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_IDS[0],
        )
    finally:
        builtins.input = original_input

    if result != 0:
        raise AssertionError("installed selected-review root returned failure")
    if counts != {"assignment": 1, "roster": 1, "observations": 1}:
        raise AssertionError(f"unexpected installed read counts: {counts}")
    if _snapshot(workspace) != before:
        raise AssertionError("installed selected-review redraw wrote workspace state")

    print(
        json.dumps(
            {
                "status": "PASS",
                "quillan_version": args.expected_quillan_version,
                "core_version": args.expected_core_version,
                "roster_students": len(STUDENT_IDS),
                "assignment_loads": counts["assignment"],
                "roster_loads": counts["roster"],
                "strict_observation_group_passes": counts["observations"],
                "workspace_writes": 0,
                "scan_review_discovery": 0,
                "assignment_submission_status_rebuilds": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
